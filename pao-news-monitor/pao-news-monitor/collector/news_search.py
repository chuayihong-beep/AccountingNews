"""Sources 2 and 3: news coverage *about* each PAO from other outlets.

Google News: free, no key, covers local and non-English press. One search per
term in the search_terms column of paos.csv. Terms are separated by "|".
A term can start with a locale to search another country's edition, e.g.
    zh-HK>香港會計師公會
Otherwise the row's news_locale is used (e.g. en-IN = Google News India).

NewsAPI: optional backup (set the NEWSAPI_KEY secret). Uses the first
plain term only, one request per PAO, to stay inside the free 100/day.
"""
import os
import random
import threading
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

import feedparser

from .common import Item, SourceResult, clean, fetch, iso, log, make_id, now_utc, session

LOOKBACK_DAYS = 30


class GoogleGate:
    """Google News answers a burst of searches from GitHub's servers with error 503 (it looks like a robot).
    The collector asks for ~60 searches on 8 threads at once, so nearly all of them were refused.
    This spaces the requests out, backs off together when Google pushes back, retries, and gives up
    early (so the run isn't held up for an hour) if Google keeps refusing."""

    def __init__(self, gap=1.5, backoff=(20, 45), give_up_after=4, sleep=time.sleep):
        self.gap, self.backoff, self.give_up_after, self.sleep = gap, backoff, give_up_after, sleep
        self.lock, self.next, self.failed_in_a_row, self.tripped = threading.Lock(), 0.0, 0, False

    def wait(self):
        with self.lock:
            now = time.monotonic()
            at = max(now, self.next)
            self.next = at + self.gap + (random.uniform(0, self.gap / 3) if self.gap else 0)
        if at > now:
            self.sleep(at - now)

    def push_back(self, seconds):
        with self.lock:   # everyone waits, not just the thread that was refused
            self.next = max(self.next, time.monotonic() + seconds)

    def get(self, url):
        """Returns the response (any status), or None when Google has been refusing for a while."""
        if self.tripped:
            return None
        r = None
        for attempt in range(len(self.backoff) + 1):
            self.wait()
            r = fetch(url)
            if r.status not in (429, 503):
                self.failed_in_a_row = 0
                return r
            if attempt < len(self.backoff):
                self.push_back(self.backoff[attempt])
        self.failed_in_a_row += 1
        if self.failed_in_a_row >= self.give_up_after:
            self.tripped = True
        return r


GATE = GoogleGate()


def parse_term(term, default_locale):
    if ">" in term.split('"')[0]:
        loc, _, t = term.partition(">")
        return loc.strip(), t.strip()
    return default_locale, term


def google_params(locale):
    lang, _, cc = (locale or "en-US").partition("-")
    lang, cc = lang.lower(), (cc or "US").upper()
    if lang == "zh":
        script = "zh-Hans" if cc in ("CN", "SG") else "zh-Hant"
        return f"zh-{cc}", cc, f"{cc}:{script}"
    if lang == "en":
        return f"en-{cc}", cc, f"{cc}:en"
    return lang, cc, f"{cc}:{lang}"


def google_news_url(term, locale):
    hl, gl, ceid = google_params(locale)
    q = quote(f"{term} when:{LOOKBACK_DAYS}d")
    return f"https://news.google.com/rss/search?q={q}&hl={hl}&gl={gl}&ceid={ceid}"


def parse_google_feed(content, pao, term, language=""):
    feed = feedparser.parse(content)
    out = []
    for e in feed.entries:
        title = clean(e.get("title"))
        link = e.get("link", "")
        if not title or not link:
            continue
        src = ""
        if e.get("source"):
            src = e.source.get("title", "")
        if src and title.endswith(" - " + src):
            title = title[: -len(src) - 3]
        published = None
        if e.get("published_parsed"):
            published = datetime(*e.published_parsed[:6], tzinfo=timezone.utc)
        out.append(Item(
            id=make_id(pao.id, "google_news", e.get("id") or link), pao_id=pao.id, source="google_news",
            title=title, url=link, published_at=iso(published), source_name=src,
            snippet=f'Search: {term}', language=language))
    return out


def collect_google(pao):
    res = SourceResult(pao.id, "google_news")
    terms = pao.split(pao.search_terms)
    if not terms:
        res.skipped, res.message = True, "No search terms set"
        return res
    errors = []
    for raw in terms:
        locale, term = parse_term(raw, pao.news_locale)
        try:
            r = GATE.get(google_news_url(term, locale))
            if r is None:
                errors.append(f"{term}: skipped, Google News has been refusing requests")
                continue
            if r.status >= 400:
                errors.append(f"{term}: error {r.status}")
                continue
            res.items += parse_google_feed(r.content, pao, term, (locale or "en").split("-")[0].lower())
        except Exception as e:  # noqa: BLE001
            errors.append(f"{term}: {type(e).__name__}")
    uniq = {}
    for it in res.items:
        uniq.setdefault(it.id, it)
    res.items = list(uniq.values())
    if errors and len(errors) == len(terms):
        res.ok = False
    res.message = f"{len(terms)} search(es)" + (f"; failed: {'; '.join(errors)}" if errors else "")
    if GATE.tripped and errors:
        res.message += " | Google is refusing searches from GitHub right now; run Update news again in an hour"
    return res


class NewsAPI:
    URL = "https://newsapi.org/v2/everything"
    MAX_REQUESTS_PER_RUN = 90  # free plan allows 100 per day

    def __init__(self, key=None):
        self.key = key if key is not None else os.environ.get("NEWSAPI_KEY", "").strip()
        self.used = 0
        self.blocked = ""

    def collect(self, pao):
        res = SourceResult(pao.id, "newsapi")
        if not self.key:
            res.skipped, res.message = True, "NEWSAPI_KEY not set"
            return res
        plain = [t for t in pao.split(pao.search_terms) if ">" not in t.split('"')[0]]
        if not plain:
            res.skipped, res.message = True, "No plain search term"
            return res
        if self.blocked:
            res.skipped, res.message = True, self.blocked
            return res
        if self.used >= self.MAX_REQUESTS_PER_RUN:
            res.skipped, res.message = True, "Daily request budget used up"
            return res
        since = (now_utc() - timedelta(days=LOOKBACK_DAYS - 1)).date().isoformat()
        try:
            self.used += 1
            r = session().get(self.URL, timeout=25, headers={"X-Api-Key": self.key},
                              params={"q": plain[0], "from": since, "sortBy": "publishedAt", "pageSize": 50})
            data = r.json()
            if data.get("status") != "ok":
                code = data.get("code", "")
                if code in ("rateLimited", "apiKeyInvalid", "apiKeyDisabled", "apiKeyExhausted"):
                    self.blocked = f"NewsAPI stopped: {code}"
                res.ok, res.message = False, f"NewsAPI: {code} {clean(data.get('message'), 150)}"
                return res
            for a in data.get("articles", []):
                if not a.get("url") or not a.get("title") or a["title"] == "[Removed]":
                    continue
                res.items.append(Item(
                    id=make_id(pao.id, "newsapi", a["url"]), pao_id=pao.id, source="newsapi",
                    title=clean(a["title"]), url=a["url"], published_at=a.get("publishedAt"),
                    snippet=clean(a.get("description"), 500),
                    source_name=(a.get("source") or {}).get("name", "")))
            res.message = f"Search: {plain[0]}"
        except Exception as e:  # noqa: BLE001
            log.info("newsapi %s: %s", pao.id, e)
            res.ok, res.message = False, f"{type(e).__name__}: {clean(str(e), 150)}"
        return res
