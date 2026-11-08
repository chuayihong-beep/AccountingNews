"""AI with a fallback chain: when one model runs out of free quota (or fails),
the next one is tried. All providers speak the same (OpenAI-style) language.

Order (each step only if its key is available as a repository secret):
  1. Google Gemini (free tier)              - GEMINI_API_KEY
  2. Groq (free plan)                       - GROQ_API_KEY
  3. Cloudflare Workers AI (free allowance) - CF_ACCOUNT_ID + CF_AI_TOKEN
  4. OpenRouter free models (last resort)   - OPENROUTER_API_KEY
(GitHub Models was retired by GitHub on 30 July 2026; "github:" entries only work if
 put back via AI_MODELS_* for a compatible endpoint.)
If all fail, callers fall back to a no-AI result (e.g. a plain list).

Model lists can be changed without code via the AI_MODELS_FAST / AI_MODELS_SMART
environment variables ("provider:model,provider:model,...").
"""
import json
import os
import re
import time

import requests

from .common import log

GITHUB_URL = "https://models.github.ai/inference/chat/completions"
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
CF_URL = "https://api.cloudflare.com/client/v4/accounts/{account}/ai/v1/chat/completions"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

# "fast" = tagging many items (cheap models, bigger free quotas); "smart" = writing the brief
DEFAULT_CHAINS = {
    "fast": ["gemini:gemini-3.5-flash-lite", "gemini:gemini-3.1-flash-lite", "gemini:gemini-3.8-flash", "gemini:gemini-flash-latest",
             "groq:openai/gpt-oss-120b", "groq:qwen/qwen3.8-27b",
             "cloudflare:@cf/meta/llama-3.3-70b-instruct-fp8-fast",
             "openrouter:nvidia/nemotron-3-super-120b-a12b:free", "openrouter:nvidia/nemotron-3.5-lightning:free"],
    "smart": ["gemini:gemini-3.8-flash", "gemini:gemini-3.6-flash", "gemini:gemini-flash-latest",
              "groq:openai/gpt-oss-120b", "groq:qwen/qwen3.8-27b",
              "cloudflare:@cf/meta/llama-3.3-70b-instruct-fp8-fast",
              "openrouter:nvidia/nemotron-3-super-120b-a12b:free", "openrouter:nvidia/nemotron-3.5-lightning:free"],
}


class AIUnavailable(Exception):
    """Every model in the chain failed or ran out of quota."""


def _int(v):
    try:
        return max(0, int(v))
    except (TypeError, ValueError):
        return 0


class Chain:
    def __init__(self, env=None, session=None, sleep=time.sleep):
        self.env = env if env is not None else os.environ
        self.http = session or requests.Session()
        self.sleep = sleep
        self.dead = set()     # "provider:model" that failed for good this run (quota, no access, unknown model)
        self.used = []        # models that answered, in order
        self.log = []         # what happened, for the run summary
        self.usage = []       # one row per answer: feature, model, tokens in/out (saved by flush_usage)

    # ---- configuration ----
    def chain(self, kind):
        custom = self.env.get(f"AI_MODELS_{kind.upper()}", "").strip()
        specs = [s.strip() for s in custom.split(",") if s.strip()] if custom else DEFAULT_CHAINS[kind]
        out = []
        for spec in specs:
            provider, _, model = spec.partition(":")
            target = self._target(provider, model)
            if target:
                out.append((spec, *target))
        return out

    def _target(self, provider, model):
        e = self.env
        if provider == "github" and e.get("GITHUB_TOKEN"):
            return GITHUB_URL, e["GITHUB_TOKEN"], model
        if provider == "gemini" and e.get("GEMINI_API_KEY"):
            return GEMINI_URL, e["GEMINI_API_KEY"], model
        if provider == "cloudflare" and e.get("CF_ACCOUNT_ID") and e.get("CF_AI_TOKEN"):
            return CF_URL.format(account=e["CF_ACCOUNT_ID"]), e["CF_AI_TOKEN"], model
        if provider == "groq" and e.get("GROQ_API_KEY"):
            return GROQ_URL, e["GROQ_API_KEY"], model
        if provider == "openrouter" and e.get("OPENROUTER_API_KEY"):
            return OPENROUTER_URL, e["OPENROUTER_API_KEY"], model
        return None

    # ---- calling ----
    def ask(self, kind, system, user, max_tokens=1500, temperature=0.2, feature=None):
        """Returns (text, model_spec). Raises AIUnavailable if nothing answers.
        An answer that was cut off (ran out of length) counts as a failure: the same model
        is asked once more with 3x the room, then the next model is tried."""
        tried = []
        for spec, url, key, model in self.chain(kind):
            if spec in self.dead:
                continue
            tried.append(spec)
            budget = max_tokens
            for attempt in range(3):
                try:
                    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json",
                               "Accept": "application/json", "User-Agent": "pao-news-monitor/1.0"}
                    if url == GITHUB_URL:   # GitHub's API wants its own Accept + version headers
                        headers.update({"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"})
                    r = self.http.post(url, timeout=120, headers=headers,
                        json={"model": model, "temperature": temperature, "max_tokens": budget,
                              "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]})
                except requests.RequestException as e:
                    self.log.append(f"{spec}: {type(e).__name__}")
                    if attempt == 0:
                        self.sleep(5)
                        continue
                    break
                if r.status_code == 200:
                    try:
                        body = r.json()
                        choice = body["choices"][0]
                        text = choice["message"]["content"] or ""
                        finish = choice.get("finish_reason")
                    except (ValueError, KeyError, IndexError, TypeError):
                        ct = r.headers.get("content-type", "") if hasattr(r, "headers") else ""
                        self.log.append(f"{spec}: unreadable answer ({ct}) {r.text[:160]!r}")
                        self.dead.add(spec)
                        break
                    if finish == "length":   # cut off mid-answer (thinking models use part of the budget)
                        self.log.append(f"{spec}: answer cut off at {budget} tokens")
                        if attempt < 2 and budget < max_tokens * 3:
                            budget = max_tokens * 3
                            continue
                        break
                    if text.strip():
                        self.used.append(spec)
                        self._note_usage(feature or kind, spec, body)
                        return text, spec
                    self.log.append(f"{spec}: empty answer")
                    break
                if r.status_code >= 500 and attempt < 2:
                    self.sleep(5)
                    continue
                # 429 = free quota used up; 401/403/404/400 = no access or unknown model: skip for the rest of the run
                self.log.append(f"{spec}: HTTP {r.status_code} {r.text[:120]!r}")
                if r.status_code in (400, 401, 403, 404, 413, 422, 429) or r.status_code >= 500:
                    self.dead.add(spec)
                break
        raise AIUnavailable("no AI model answered (tried: " + (", ".join(tried) or "none - no keys available") + ")")

    # ---- usage log ----
    def _note_usage(self, feature, spec, body):
        u = body.get("usage") if isinstance(body, dict) else None
        u = u if isinstance(u, dict) else {}
        self.usage.append({"feature": feature, "model": spec,
                           "prompt_tokens": _int(u.get("prompt_tokens")), "completion_tokens": _int(u.get("completion_tokens"))})

    def flush_usage(self, store):
        """Save the usage rows collected so far. Never raises: a missing table (update-22.sql not run) just logs."""
        rows, self.usage = self.usage, []
        if not rows:
            return
        try:
            store.log_ai_usage(rows)
        except Exception as e:  # noqa: BLE001
            self.log.append(f"usage log not saved: {type(e).__name__}")


def parse_json(text):
    """JSON from a model answer, tolerating ```json fences and chatter around it."""
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t)
    try:
        return json.loads(t)
    except ValueError:
        pass
    for open_, close in (("[", "]"), ("{", "}")):
        a, b = t.find(open_), t.rfind(close)
        if a != -1 and b > a:
            try:
                return json.loads(t[a:b + 1])
            except ValueError:
                continue
    log.info("could not parse AI JSON: %s", t[:200])
    return None


def check(env=None):
    """Ping every provider that has a key with a one-line prompt; report which models answer."""
    chain = Chain(env=env)
    results = []
    seen_providers = set()
    for kind in ("smart", "fast"):
        for spec, url, key, model in chain.chain(kind):
            provider = spec.split(":")[0]
            if spec in {r[0] for r in results}:
                continue
            one = Chain(env=env)
            one.chain = lambda k, _s=(spec, url, key, model): [_s]
            try:
                text, _ = one.ask("smart", "Reply with the single word OK.", "Say OK.", max_tokens=200)
                results.append((spec, True, text.strip()[:40]))
                seen_providers.add(provider)
            except AIUnavailable:
                results.append((spec, False, "; ".join(one.log)[-200:]))
    return results


if __name__ == "__main__":
    rows = check()
    if not rows:
        print("::error title=AI check::No AI keys found (add GEMINI_API_KEY etc. as repository secrets)")
    for spec, ok, detail in rows:
        level = "notice" if ok else "warning"
        print(f"::{level} title=AI check::{'OK  ' if ok else 'FAIL'} {spec} - {detail}")
