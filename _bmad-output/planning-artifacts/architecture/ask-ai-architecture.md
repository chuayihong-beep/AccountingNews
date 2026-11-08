---
title: Architecture Decision - Ask AI (real-time PAO Q&A)
created: 2026-10-21
updated: 2026-10-21
status: final
---

# Architecture Decision: Ask AI

## 1. Why this needed a decision

Every other part of the monitor runs on a schedule (GitHub Actions cron): collect news at 05:40, draft the brief at 07:45, send approved briefs every ~30 minutes. Nothing today runs *in response to a user action*. Ask AI needs an answer back within seconds of a staff member clicking a button, which a cron job can't do. This is the system's first on-demand, server-side compute.

## 2. Options considered

| Option | Verdict |
| --- | --- |
| **Supabase Edge Function** | **Chosen.** Already have Supabase; function reuses the same auth/roles; keys never reach the browser; free tier (500K calls/month) is far beyond 7 users asking a few questions a day. |
| Cloudflare Worker with an API route | Rejected for now. Would split "backend logic" across two platforms (Supabase + Cloudflare) instead of one, and means re-implementing permission checks that Supabase already enforces via RLS/`has_perm`. Revisit only if Edge Functions prove unworkable. |
| Browser calls the AI provider directly | Rejected. Would expose the AI API key in the page source - a hard no per the project's own security rules (secrets never in client code). |
| New standalone server (e.g. a small Node app) | Rejected. New hosting, new account, new recurring cost risk, and another thing to hand over - against the brief's "minimal additional infrastructure" guidance. |

## 3. How it works

```
Browser (ask-ai.html)
  -> supabase.functions.invoke('ask-ai', { pao_id, thread_id?, question })
       -> Edge Function (Deno, runs on Supabase's infrastructure):
            1. Reads the caller's identity from their Supabase session (same login as the rest of the site)
            2. Calls has_perm('ask_ai') - refuses if false
            3. Loads: that PAO's items, the CAPA context file, the thread's prior messages (if continuing)
            4. Calls Groq gpt-oss-120b, then Groq llama-3.3-70b, then Gemini, Cloudflare, OpenRouter; 30s limit per provider, ~110s overall
            5. Saves the question + answer to ask_ai_threads (service role, bypasses RLS by design -
               the function itself already checked the permission)
            6. Returns the answer + which items it cited
  <- Browser shows the answer, offers "Ask a follow-up" or "End chat"
```

## 4. Data

New table `ask_ai_threads`: one row per conversation. `pao_id`, `started_by`, `started_at`, `ended_at` (null while still open), `messages` (jsonb array of `{role, content, cited_item_ids}`). Shared visibility: anyone with the `ask_ai` permission can read any PAO's threads, same as everyone already sees the same tagged items - this builds a shared record of what's been asked, not a private chat.

## 5. Guardrails (carried over from the user's collaboration-guidelines document)

- Answers are drawn **only from that PAO's collected items** plus the CAPA context file - no live web search. The free AI providers used have no real internet access when called this way; asking them to "research externally" would risk invented sources. If the collection doesn't have enough, the AI says so rather than guessing.
- Every claim in an answer cites the item(s) it came from, same `[1][2]` style as the brief.
- Output follows the structure in the user's collaboration-guidelines document (rationale, potential roles, mutual benefit, first step, timing, evidence/confidence) - never a flat "do X" claim.
- A thread is capped at 15 exchanges; past that, the UI asks the user to start a new one. Keeps each request's size bounded and avoids runaway token growth in a long back-and-forth.
- Scope stays separate from the weekly brief - the brief's "Suggested CAPA actions" line is untouched.

## 6. Cost and limits

- Groq free tier covers 10-20 messages/day across 7 users, but its binding limit is tokens per MINUTE (gpt-oss-120b 8,000; llama-3.3-70b 12,000, prompt + answer combined). The prompt is therefore capped at the 35 most recent items (by publish date, falling back to found date; Removed and staff-tagged Not relevant items excluded) with 150-character excerpts and no URLs (~5.7k tokens worst case). Long follow-up threads may exceed gpt-oss's cap and fall to llama-3.3. Gemini (~20 requests/day free) is a last resort only.
- Revised 2026-10-21 after first live tests: original 120-item prompt exceeded Groq's per-minute cap, and a 1,800-token answer limit was consumed by model reasoning, truncating answers.
- Supabase Edge Functions: 500K invocations/month free - not a realistic constraint at this scale.
- No new paid service, no new account to create.

## 7. Deployment (new type of step for this project)

Unlike the SQL updates (pasted into Supabase's SQL editor) and the web page (auto-deploys on push), the Edge Function needs **one extra manual step**: `supabase functions deploy ask-ai` from a machine with the Supabase CLI logged into the project, and the AI provider keys set once via `supabase secrets set`. This is documented in the README under "Ask AI setup" so it survives handover.

## 8. What this does NOT change

- The daily collector, brief generation and sending are untouched - same cron jobs, same logic.
- No member data moves anywhere new; the function reads items already in Supabase.
- No change to who can sign in or what Team/Viewer can already do, beyond the new `ask_ai` permission being available to tick.

## 9. Addendum (2026-10-26): whole-region mode and item clean-up
- **Whole region (all PAOs):** the page sends `pao_id = "_region"`. Items come from all PAOs (last 12 months), scored against the question by the brief's theme tags (`ai_themes`) plus keyword overlap, High/Medium first, max 4 per PAO, max 30 total (same token budget as single-PAO mode). A question matching nothing falls back to the most important recent items. Each item line carries the PAO abbreviation; sources list shows it too.
- **Stable citations on follow-ups:** the first user message of a region thread stores `item_ids`; follow-ups reuse that exact numbered list so [n] keeps meaning the same article. Region threads are saved with `pao_id` null (`update-15.sql` drops NOT NULL; without it, region answers work but don't continue).
- **Cleaner item pool (both modes):** first-scan links excluded; Low/No by staff *or* by the AI suggestion when unreviewed (`update-14.sql`, falls back to staff-only labels); repeats with the same headline per PAO collapsed (reviewed copy kept).
- Selection logic lives in `supabase/functions/ask-ai/select.ts` (no Deno APIs) so it can be tested with Node.

