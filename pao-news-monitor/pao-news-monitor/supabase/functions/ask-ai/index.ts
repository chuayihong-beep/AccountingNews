// Ask AI - real-time Q&A about one PAO (or the whole region), grounded only in collected items.
// Deploy: supabase functions deploy ask-ai   (see README "Ask AI setup")
// Secrets needed (set once): supabase secrets set GROQ_API_KEY=... GEMINI_API_KEY=... (etc.)
//
// Why this exists as an Edge Function and not a schedule job: see
// _bmad-output/planning-artifacts/architecture/ask-ai-architecture.md
//
// Guardrails (do not loosen without re-reading the architecture doc):
//  - Answers are grounded ONLY in the PAO's collected items + the CAPA context below (plus, on file, the
//    PAO's background profile and - for leadership questions - its names-only leaders list and saved leadership page).
//  - No tool call claims web research - these providers, called this way, cannot browse.
//  - Every material claim must cite [n] matching the numbered item list given to the model.
//  - Thread length is capped (MAX_TURNS) so one conversation can't grow without bound.

import { createClient } from "jsr:@supabase/supabase-js@2";
import { COLLABORATION_GUIDELINES } from "./capa_context.ts";
import { dedupe, type Item, pickForTopic, questionWindowDays, rank, when, withinDays } from "./select.ts";
import { isLeadershipQuestion, type Leader, type LeaderPage, leadersBlock, regionLeadersBlock } from "./leaders.ts";

// Evidence rules (added after a whole-region answer invented a membership count and called an item "today"):
// the model may only assert what the numbered items say, and must use their dates.
const EVIDENCE_RULES = `Evidence rules: state only what the numbered items say (and, when a "Background on file" or "Leaders on file" section is \
given, what that section says). Do not add figures, counts, membership \
numbers or background facts that no item supports (for example how many organisations a development affects, or what \
a publication "usually" leads to). If you add general knowledge, put it under the heading "General background (not from \
the items)". Use the dates shown in the item list; do not call an item "today" or "yesterday" unless its date says so. \
Write plain text, lists and tables. Never write HTML tags such as <br>.`;

// Staff-written background on one PAO (who they are, leaders, recent activity), kept apart from the numbered news
// items. It is on file, not a live fact: say how old it is, and never give it an item number.
function profileBlock(pao: { name: string; profile?: string | null; profile_checked?: string | null }): string {
  if (!pao.profile?.trim()) return "";
  return `
Background on file about ${pao.name} (written by CAPA staff from public sources, last checked ${pao.profile_checked ?? "on an unknown date"}; \
it may be out of date). Use it for questions about who the organisation is, its leaders and its usual activity. When you \
use it, say "(background on file)" instead of an item number, mention the last-checked date if the answer depends on a \
name or a figure, and say plainly when the question needs something it does not cover (see its NOT KNOWN line).
${pao.profile.trim()}
`;
}

const REGION = "_region";   // pao_id the page sends for "Whole region (all PAOs)"
const MAX_TURNS = 15;        // user+assistant pairs per thread before the UI must start a new one
// Prompt size matters: Groq's free tier caps tokens per minute, and an oversized prompt is refused
// outright, pushing every question onto Gemini's much smaller daily quota. So: fewer items, short
// excerpts, no URLs (citations are matched back to items by number, so the model doesn't need links).
// Groq free tier (2026): gpt-oss-120b 8,000 tokens/min, llama-3.3-70b 12,000 tokens/min - prompt AND
// answer combined. Guidelines incl. CAPA realism rules (~3k tokens) + 30 short items (~2.8k) + answer must fit under those.
const MAX_ITEMS = 30;        // most recent items fed in
const SNIPPET_CHARS = 140;   // excerpt length per item
// Answers need room: "thinking" models spend part of this budget reasoning before they write.
// Per-provider overrides below keep Groq requests inside its per-minute token cap.
const MAX_OUTPUT_TOKENS = 4000;
const GROQ_URL = "https://api.groq.com/openai/v1/chat/completions";
const GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions";
const CF_URL = (account: string) => `https://api.cloudflare.com/client/v4/accounts/${account}/ai/v1/chat/completions`;
const OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions";

// Groq first (cheap, generous free tier) - see ask-ai-architecture.md for why, unlike the
// brief/tagging chain in collector/ai.py which tries Gemini first.
function chain(env: Record<string, string | undefined>) {
  const steps: { url: string; key: string; model: string; extra?: Record<string, unknown> }[] = [];
  if (env.GROQ_API_KEY) {
    // gpt-oss "thinks" before answering; keep that short so it's fast and doesn't eat the answer's token budget
    steps.push({ url: GROQ_URL, key: env.GROQ_API_KEY, model: "openai/gpt-oss-120b", extra: { reasoning_effort: "low", max_tokens: 2000 } });
    // same key, bigger per-minute allowance, no thinking step - keeps Gemini's small daily quota as a last resort
    steps.push({ url: GROQ_URL, key: env.GROQ_API_KEY, model: "llama-3.3-70b-versatile", extra: { max_tokens: 3000 } });
  }
  if (env.GEMINI_API_KEY) steps.push({ url: GEMINI_URL, key: env.GEMINI_API_KEY, model: "gemini-3.8-flash", extra: { reasoning_effort: "low" } });
  if (env.CF_ACCOUNT_ID && env.CF_AI_TOKEN)
    steps.push({ url: CF_URL(env.CF_ACCOUNT_ID), key: env.CF_AI_TOKEN, model: "@cf/meta/llama-3.3-70b-instruct-fp8-fast" });
  if (env.OPENROUTER_API_KEY) steps.push({ url: OPENROUTER_URL, key: env.OPENROUTER_API_KEY, model: "nvidia/nemotron-3-super-120b-a12b:free" });
  return steps;
}

// Time limits: a stalled provider must never hang the page. Each provider gets PER_PROVIDER_MS,
// and we stop starting new attempts once TOTAL_MS has passed (Supabase kills functions at ~150s).
const PER_PROVIDER_MS = 30_000;
const TOTAL_MS = 110_000;

async function askModel(env: Record<string, string | undefined>, messages: unknown[]): Promise<{ text: string; model: string }> {
  let lastError = "no AI provider has a key set";
  const started = Date.now();
  const tried: string[] = [];
  for (const step of chain(env)) {
    const left = TOTAL_MS - (Date.now() - started);
    if (left < 5_000) { lastError = `ran out of time (tried: ${tried.join(", ")})`; break; }
    tried.push(step.model);
    try {
      const r = await fetch(step.url, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${step.key}` },
        body: JSON.stringify({ model: step.model, messages, temperature: 0.3, max_tokens: MAX_OUTPUT_TOKENS, ...(step.extra || {}) }),
        signal: AbortSignal.timeout(Math.min(PER_PROVIDER_MS, left)),
      });
      if (!r.ok) {
        const detail = (await r.text().catch(() => "")).slice(0, 200);
        console.error(`ask-ai: ${step.model} failed ${r.status}: ${detail}`);
        lastError = `${step.model} failed ${r.status}`;
        continue;
      }
      const data = await r.json();
      const choice = data?.choices?.[0];
      const text = choice?.message?.content;
      if (typeof text === "string" && text.trim()) {
        // ran out of room mid-answer: say so plainly rather than silently stopping mid-sentence
        const cut = choice?.finish_reason === "length";
        if (cut) console.error(`ask-ai: ${step.model} hit the output limit`);
        return { text: cut ? `${text.trimEnd()}\n\n*(This answer was cut short. Reply "continue" for the rest.)*` : text, model: step.model };
      }
      lastError = `${step.model} returned no usable text`;
      console.error(`ask-ai: ${lastError}`);
    } catch (e) {
      const timedOut = (e as Error).name === "TimeoutError";
      lastError = timedOut ? `${step.model} took too long` : `${step.model} error: ${(e as Error).message}`;
      console.error(`ask-ai: ${lastError}`);
    }
  }
  throw new Error(`All AI providers failed or were too slow - try again in a minute. (Last: ${lastError})`);
}

// The tracker site lives on a different domain from Supabase, so the browser first asks
// "may I call you?" (a CORS preflight). Every response must carry these headers or the
// browser blocks the call with "Failed to send a request to the Edge Function".
const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: CORS });
  if (req.method !== "POST") return new Response("POST only", { status: 405, headers: CORS });
  try {
    return await handle(req);
  } catch (e) {
    return json({ error: `Ask AI failed: ${(e as Error).message}` }, 500);
  }
});

async function handle(req: Request): Promise<Response> {

  let body: { pao_id?: string; thread_id?: number; question?: string };
  try { body = await req.json(); } catch { return json({ error: "Bad request body" }, 400); }
  const { pao_id, question } = body;
  if (!pao_id || !question?.trim()) return json({ error: "pao_id and question are required" }, 400);

  // The caller's own session - RLS applies, so this can only ever see what they're allowed to.
  const authHeader = req.headers.get("Authorization") ?? "";
  const userClient = createClient(Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_ANON_KEY")!, {
    global: { headers: { Authorization: authHeader } },
  });
  const { data: userData, error: authError } = await userClient.auth.getUser();
  if (authError || !userData?.user?.email) return json({ error: "Sign in required" }, 401);
  const email = userData.user.email;

  const { data: canAsk } = await userClient.rpc("has_perm", { p: "ask_ai" });
  if (!canAsk) return json({ error: "You don't have permission to use Ask AI" }, 403);

  // Service role from here, now that permission is confirmed - needed to write the thread
  // (writes are function-only, see update-11.sql: table grants SELECT only to authenticated).
  const svc = createClient(Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!);

  const region = pao_id === REGION;
  const { data: pao } = region
    ? { data: null }
    : await svc.from("paos").select("id,name,abbr,jurisdiction,grp,website,profile,profile_checked").eq("id", pao_id).single();
  if (!region && !pao) return json({ error: "Unknown PAO" }, 404);

  type Thread = { id: number; messages: { role: string; content: string; cited_item_ids?: string[]; item_ids?: string[]; at: string }[] };
  let thread: Thread | null = null;
  if (body.thread_id) {
    const { data } = await svc.from("ask_ai_threads").select("id,messages,ended_at").eq("id", body.thread_id).single();
    if (data && !data.ended_at) thread = data as Thread;
  }
  const priorTurns = thread ? thread.messages.filter((m) => m.role !== "system").length / 2 : 0;
  if (priorTurns >= MAX_TURNS) return json({ error: "This conversation has reached its limit - please start a new one." }, 400);

  // Which items the AI sees. Left out: Removed items, first-scan links (old), and anything rated
  // Low / No relevance - by staff, or by the AI suggestion when staff haven't reviewed it
  // (update-14.sql; older databases fall back to staff labels only). Repeats of the same story
  // (same headline) count once. High first, then Medium, then unrated; newest first within each.
  const COLS = "id,pao_id,title,snippet,url,published_at,first_seen_at,source,kind,relevance,category";
  const poolQuery = async (withAi: boolean) => {
    let q = svc.from("items").select(COLS + (withAi ? ",ai_relevance,ai_summary,ai_themes" : ""))
      .is("removed_at", null).not("is_baseline", "is", true)
      .or(withAi
        ? "relevance.in.(high,medium),and(relevance.is.null,or(ai_relevance.is.null,ai_relevance.in.(high,medium)))"
        : "relevance.is.null,relevance.in.(high,medium)")
      .order("first_seen_at", { ascending: false });
    q = region ? q.gte("first_seen_at", new Date(Date.now() - 365 * 864e5).toISOString()).limit(3000) : q.eq("pao_id", pao_id).limit(300);
    return await q;
  };
  let res = await poolQuery(true);
  if (res.error) res = await poolQuery(false);   // update-14.sql not run yet
  // "past 24 hours", "this week"...: only items from that period (a follow-up keeps the first question's period)
  const firstQ = thread?.messages.find((m) => m.role === "user")?.content;
  const windowDays = questionWindowDays(question) ?? (firstQ ? questionWindowDays(firstQ) : null);
  const pool: Item[] = withinDays(dedupe((res.data ?? []) as Item[]), windowDays);

  const { data: paoRows } = await svc.from("paos").select("id,name,abbr");
  const abbr = new Map((paoRows ?? []).map((p) => [p.id, p.abbr || p.name || p.id]));

  let items: Item[];
  const earlier = thread?.messages.find((m) => m.role === "user" && m.item_ids?.length)?.item_ids;
  if (region && earlier) {
    // follow-up in a whole-region conversation: keep the same numbered items so [n] still means the same article
    const byId = new Map(pool.map((it) => [it.id, it]));
    const missing = earlier.filter((id) => !byId.has(id));
    if (missing.length) {
      const { data } = await svc.from("items").select(COLS).in("id", missing);
      for (const it of (data ?? []) as Item[]) byId.set(it.id, it);
    }
    items = earlier.map((id) => byId.get(id)).filter(Boolean) as Item[];
  } else if (region) {
    const topic = [question, ...(thread?.messages ?? []).filter((m) => m.role === "user").map((m) => m.content)].join(" ");
    items = pickForTopic(pool, topic, MAX_ITEMS);
  } else {
    items = pool.sort((a, b) => rank(a) - rank(b) || when(b).localeCompare(when(a))).slice(0, MAX_ITEMS);
  }
  items.sort((a, b) => when(b).localeCompare(when(a)));

  const numbered = items.map((it, i) => {
    const date = when(it).slice(0, 10);
    const org = region ? `${abbr.get(it.pao_id) ?? it.pao_id} | ` : "";
    const rel = it.relevance ? ` | staff-tagged: ${it.relevance}` : it.ai_relevance ? ` | AI-rated: ${it.ai_relevance}` : "";
    return `[${i + 1}] ${org}${date} | ${it.source}${it.kind && it.kind !== "news" ? ` (${it.kind === "comment" ? "opportunity to comment" : it.kind})` : ""}${rel} | ${it.title}${it.snippet ? `\n    ${short(it.snippet)}` : ""}`;
  });

  // "Who is their president?" and the like: add the names-only leaders list (and, for one PAO, the lines saved
  // from its leadership page). Missing table (update-19.sql not run) = nothing added.
  let leaders = "";
  if (isLeadershipQuestion(question, firstQ)) {
    const LEADER_COLS = "pao_id,role,name,source_url,as_of";
    if (region) {
      const { data } = await svc.from("pao_leaders").select(LEADER_COLS);
      leaders = regionLeadersBlock((data ?? []) as Leader[], abbr);
    } else {
      const [ld, pg] = await Promise.all([
        svc.from("pao_leaders").select(LEADER_COLS).eq("pao_id", pao_id),
        svc.from("watched_pages").select("url,snapshot,last_checked_at").eq("pao_id", pao_id).eq("kind", "leadership"),
      ]);
      leaders = leadersBlock(pao!.name, (ld.data ?? []) as Leader[], (pg.data ?? []) as LeaderPage[]);
    }
  }

  const system = region
    ? `You are answering questions for CAPA staff about developments across CAPA's network - its member \
PAOs and key stakeholders in Asia-Pacific and international bodies such as IFAC and the standard-setters.

${COLLABORATION_GUIDELINES}

${EVIDENCE_RULES}
${leaders}
Whole-region questions: where the guidelines above talk about "the PAO", apply them across the organisations in \
the items. Compare and contrast: name which organisations are doing what, note common patterns and differences, and \
say where only one or two organisations show evidence. Each item starts with the organisation's abbreviation.
The items below were selected for the question from everything collected ${windowDays ? `in the last ${windowDays} day(s) (the period the question asks about)` : "in the last 12 months"}; they are a sample, \
not a complete picture of the region (and say nothing about countries outside CAPA's network). Say so when the \
evidence is thin, rather than generalising.

Collected items (most recent first, numbered for citation; this is ALL the evidence you have - you cannot browse the web):
${numbered.length ? numbered.join("\n\n") : windowDays ? "(Nothing was collected in that period. Say so plainly.)" : "(No collected items matched this question.)"}
`
    : `You are answering questions for CAPA staff about one specific organisation: \
${pao!.name} (${pao!.abbr ?? pao!.id}), ${pao!.grp ?? "Member"}, ${pao!.jurisdiction ?? "jurisdiction unknown"}.

${COLLABORATION_GUIDELINES}

${EVIDENCE_RULES}
${profileBlock(pao!)}${leaders}
Collected items about ${pao!.name} (most recent first, numbered for citation; this is ALL the \
evidence you have - you cannot browse the web):
${numbered.length ? numbered.join("\n\n") : windowDays ? "(Nothing was collected for this PAO in the period the question asks about. Say so plainly.)" : "(No items collected yet for this PAO.)"}
`;

  const history = (thread?.messages ?? []).map((m) => ({ role: m.role, content: m.content }));
  const messages = [{ role: "system", content: system }, ...history, { role: "user", content: question }];

  let answer: { text: string; model: string };
  try {
    answer = await askModel(
      {
        GROQ_API_KEY: Deno.env.get("GROQ_API_KEY"),
        GEMINI_API_KEY: Deno.env.get("GEMINI_API_KEY"),
        CF_ACCOUNT_ID: Deno.env.get("CF_ACCOUNT_ID"),
        CF_AI_TOKEN: Deno.env.get("CF_AI_TOKEN"),
        OPENROUTER_API_KEY: Deno.env.get("OPENROUTER_API_KEY"),
      },
      messages,
    );
  } catch (e) {
    return json({ error: `No AI model was available right now (${(e as Error).message}). Try again shortly.` }, 503);
  }

  // Citation numbers -> the actual articles, so the page can turn [5] into a link and list sources.
  // Handles [5], [2][5] and [19, 33] / [19/33] styles.
  const citedNums = [...new Set(
    [...answer.text.matchAll(/\[(\d+(?:\s*[,/]\s*\d+)*)\]/g)]
      .flatMap((m) => m[1].split(/[,/]/).map((x) => Number(x.trim())))
      .filter((n) => n >= 1 && n <= items.length),
  )].sort((a, b) => a - b);
  const citedIds = citedNums.map((n) => items[n - 1].id);
  const sources = citedNums.map((n) => {
    const it = items[n - 1];
    return { n, id: it.id, title: it.title, url: it.url, source: it.source, date: when(it).slice(0, 10), ...(region ? { pao: abbr.get(it.pao_id) ?? it.pao_id } : {}) };
  });

  const now = new Date().toISOString();
  const newMessages = [
    ...(thread?.messages ?? []),
    { role: "user", content: question, at: now, ...(region && !earlier ? { item_ids: items.map((it) => it.id) } : {}) },
    { role: "assistant", content: answer.text, cited_item_ids: citedIds, sources, at: now, model: answer.model },
  ];

  let threadId = thread?.id;
  if (threadId) {
    await svc.from("ask_ai_threads").update({ messages: newMessages }).eq("id", threadId);
  } else {
    const { data: created } = await svc
      .from("ask_ai_threads")
      .insert({ pao_id: region ? null : pao_id, started_by: email, messages: newMessages })   // null = whole region (update-15.sql)
      .select("id")
      .single();
    threadId = created?.id;
  }

  return json({ thread_id: threadId, answer: answer.text, model: answer.model, cited_item_ids: citedIds, sources });
}

function short(s: string) {
  const t = s.replace(/\s+/g, " ").trim();
  return t.length > SNIPPET_CHARS ? `${t.slice(0, SNIPPET_CHARS).replace(/\s+\S*$/, "")}…` : t;
}

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { ...CORS, "Content-Type": "application/json" } });
}
