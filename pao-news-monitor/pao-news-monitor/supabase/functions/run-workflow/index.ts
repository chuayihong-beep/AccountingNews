// Run-from-the-site: lets an ADMIN start two GitHub Actions workflows from the tracker's pages:
//   "collect" = Update news  (.github/workflows/collect.yml)
//   "brief"   = Create brief (.github/workflows/brief.yml), optionally for a From/To date range
// and see whether the latest run is still going.
//
// Why a function: the page is public static files, so it can never hold a GitHub token. The token lives only
// here, as a secret, and this function checks the caller is a signed-in admin before using it.
//
// Deploy:  supabase functions deploy run-workflow --project-ref <ref>
// Secrets (once):  supabase secrets set GH_DISPATCH_TOKEN=<fine-grained token> --project-ref <ref>
//   optional:      GH_REPO=owner/repo (default below)   GH_REF=main (default)
// The token: GitHub -> Settings -> Developer settings -> Fine-grained tokens, repository = this repo only,
// permission "Actions: Read and write" (nothing else). See README "Run from the site".

import { createClient } from "jsr:@supabase/supabase-js@2";

const DEFAULT_REPO = "bot8cyh-CAPA/pao-news-monitor";
const FILES: Record<string, string> = { collect: "collect.yml", brief: "brief.yml" };
const MAX_RANGE_DAYS = 92;   // same cap as collector/brief.py

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};
const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { ...CORS, "Content-Type": "application/json" } });

const ymd = (d: Date) => d.toISOString().slice(0, 10);

// "2026-10-02" -> a real UTC date, or null
function parseDay(s: unknown): Date | null {
  if (typeof s !== "string" || !/^\d{4}-\d{2}-\d{2}$/.test(s)) return null;
  const d = new Date(s + "T00:00:00Z");
  return Number.isNaN(d.getTime()) || ymd(d) !== s ? null : d;
}

// Returns the dates to send, or a readable reason they are not allowed.
export function checkRange(from: unknown, to: unknown, today = new Date()): { from: string; to: string } | { error: string } {
  const a = parseDay(from), b0 = parseDay(to ?? from);
  if (!a || !b0) return { error: "Dates must look like 2026-10-02" };
  if (b0 < a) return { error: "The 'to' date is before the 'from' date" };
  const t = parseDay(ymd(today))!;
  if (a > t) return { error: "The 'from' date is in the future" };
  const b = b0 > t ? t : b0;
  if ((b.getTime() - a.getTime()) / 864e5 + 1 > MAX_RANGE_DAYS) return { error: `Pick at most ${MAX_RANGE_DAYS} days at a time` };
  return { from: ymd(a), to: ymd(b) };
}

type Run = { status: string; conclusion: string | null; created_at: string; html_url: string; run_number: number };

async function gh(path: string, init: RequestInit = {}) {
  const token = Deno.env.get("GH_DISPATCH_TOKEN");
  if (!token) throw new Error("Not set up yet: the GH_DISPATCH_TOKEN secret is missing (see README: Run from the site).");
  const repo = Deno.env.get("GH_REPO") || DEFAULT_REPO;
  const res = await fetch(`https://api.github.com/repos/${repo}${path}`, {
    ...init,
    headers: {
      Authorization: `Bearer ${token}`, Accept: "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28",
      "User-Agent": "pao-news-monitor", "Content-Type": "application/json", ...(init.headers ?? {}),
    },
  });
  if (res.status === 401) throw new Error("GitHub rejected the token (expired or wrong). Make a new one and set GH_DISPATCH_TOKEN again.");
  if (res.status === 403 || res.status === 404)
    throw new Error("GitHub says no: the token needs access to this repository with the 'Actions: Read and write' permission.");
  return res;
}

async function latestRuns(workflow: string, n = 5): Promise<Run[]> {
  const res = await gh(`/actions/workflows/${FILES[workflow]}/runs?per_page=${n}`);
  const all = res.ok ? (await res.json()).workflow_runs : [];
  return (all ?? []) as Run[];
}

const ACTIVE = new Set(["queued", "in_progress", "waiting", "requested", "pending"]);
const brief = (r?: Run) => r ? { status: r.status, conclusion: r.conclusion, created_at: r.created_at, url: r.html_url, number: r.run_number } : null;

async function handle(req: Request): Promise<Response> {
  let body: { action?: string; workflow?: string; from?: string; to?: string };
  try { body = await req.json(); } catch { return json({ error: "Bad request body" }, 400); }

  // who is asking: their own session, then the database's own idea of "admin"
  const userClient = createClient(Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_ANON_KEY")!, {
    global: { headers: { Authorization: req.headers.get("Authorization") ?? "" } },
  });
  const { data: userData, error: authError } = await userClient.auth.getUser();
  if (authError || !userData?.user?.email) return json({ error: "Sign in required" }, 401);
  const { data: isAdmin } = await userClient.rpc("is_admin");
  if (!isAdmin) return json({ error: "Only admins can start these" }, 403);

  if (body.action === "status") {
    const [collect, brf] = await Promise.all([latestRuns("collect", 1), latestRuns("brief", 1)]);
    return json({ collect: brief(collect[0]), brief: brief(brf[0]) });
  }

  if (body.action !== "start" || !body.workflow || !(body.workflow in FILES)) return json({ error: "Unknown request" }, 400);

  const inputs: Record<string, string> = {};
  if (body.workflow === "brief" && body.from) {
    const r = checkRange(body.from, body.to);
    if ("error" in r) return json({ error: r.error }, 400);
    inputs.from_date = r.from;
    inputs.to_date = r.to;
  }

  // one at a time: a second press while it runs would only queue behind it
  const running = (await latestRuns(body.workflow, 5)).find((r) => ACTIVE.has(r.status));
  if (running) return json({ error: "It is already running - wait for it to finish.", running: true, run: brief(running) }, 409);

  const startedAt = new Date().toISOString();
  const res = await gh(`/actions/workflows/${FILES[body.workflow]}/dispatches`, {
    method: "POST",
    body: JSON.stringify({ ref: Deno.env.get("GH_REF") || "main", ...(Object.keys(inputs).length ? { inputs } : {}) }),
  });
  if (res.status !== 204) {
    const t = await res.text();
    return json({ error: `GitHub did not start it (${res.status}): ${t.slice(0, 200)}` }, 502);
  }
  return json({ ok: true, started_at: startedAt, ...inputs });
}

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: CORS });
  if (req.method !== "POST") return new Response("POST only", { status: 405, headers: CORS });
  try {
    return await handle(req);
  } catch (e) {
    return json({ error: (e as Error).message }, 500);
  }
});
