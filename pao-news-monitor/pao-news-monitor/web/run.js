/* Start the two GitHub Actions jobs from the page (admins only), via the run-workflow Edge Function:
 *   Update news   (News tab)  -> Collect news
 *   Create brief  (Brief tab) -> Brief, for the From / To dates picked
 * The page never holds a GitHub token; the function checks you are an admin first (supabase/functions/run-workflow).
 */
(() => {
  "use strict";
  const A = window.PAOApp;
  if (!A) return;
  const $ = (s, el = document) => el.querySelector(s);
  const $$ = (s, el = document) => [...el.querySelectorAll(s)];
  const ymd = (d) => d.toISOString().slice(0, 10);
  const isAdmin = () => A.state.role === "admin";
  const POLL_MS = 15_000, GIVE_UP_MS = 30 * 60_000;

  const JOBS = {
    collect: { btn: "#run-news", status: "#run-news-status", idle: "Update news", busy: "Updating…", name: "News update", after: () => A.reload && A.reload() },
    brief: { btn: "#bc-run", status: "#bc-status", idle: "Create brief", busy: "Creating…", name: "Brief",
             after: () => document.dispatchEvent(new CustomEvent("pao:brief-ready")) },
  };
  const watching = {};

  async function call(body) {
    const { data, error } = await A.db.functions.invoke("run-workflow", { body });
    if (error) {
      let d = {};
      try { d = await error.context.json(); } catch { /* no readable body */ }
      const e = new Error(d.error || error.message);
      e.running = !!d.running;
      throw e;
    }
    if (data?.error) throw new Error(data.error);
    return data;
  }

  function show(wf, text, kind, link) {
    const el = $(JOBS[wf].status);
    el.hidden = !text;
    el.className = "run-status small" + (kind ? " " + kind : "");
    el.innerHTML = "";
    el.append(document.createTextNode(text || ""));
    if (link) {
      const a = document.createElement("a");
      a.href = link; a.target = "_blank"; a.rel = "noopener"; a.textContent = " See the run";
      el.append(a);
    }
  }
  function busy(wf, on) {
    const b = $(JOBS[wf].btn);
    b.disabled = on;
    b.textContent = on ? JOBS[wf].busy : JOBS[wf].idle;
  }
  const clock = (iso) => new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

  // follow the newest run until it finishes. `startedAt` = when we pressed (so an older finished run isn't mistaken for it)
  function watch(wf, startedAt) {
    clearTimeout(watching[wf]);
    const t0 = Date.now();
    busy(wf, true);
    const tick = async () => {
      let run = null;
      try { run = (await call({ action: "status" }))[wf]; } catch (e) { /* try again next tick */ }
      const fresh = run && (!startedAt || Date.parse(run.created_at) >= Date.parse(startedAt) - 60_000);
      if (!fresh) show(wf, "Starting… (waiting for GitHub)", "");
      else if (run.status !== "completed") show(wf, `${JOBS[wf].name} running, started ${clock(run.created_at)}. This usually takes ${wf === "brief" ? "3–8" : "5–15"} minutes.`, "", run.url);
      else if (run.conclusion === "success") { show(wf, `${JOBS[wf].name} finished at ${new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}.`, "ok"); busy(wf, false); JOBS[wf].after(); return; }
      else { show(wf, `${JOBS[wf].name} did not finish (${run.conclusion || run.status}).`, "bad", run.url); busy(wf, false); return; }
      if (Date.now() - t0 > GIVE_UP_MS) { show(wf, "Still not finished after 30 minutes - check the run on GitHub (Actions).", "bad"); busy(wf, false); return; }
      watching[wf] = setTimeout(tick, POLL_MS);
    };
    watching[wf] = setTimeout(tick, 5000);
  }

  async function start(wf, extra) {
    if (A.DEMO) { A.toast("Demo mode: this would start the " + JOBS[wf].name.toLowerCase() + "."); return; }
    busy(wf, true);
    show(wf, "Starting…", "");
    try {
      const r = await call({ action: "start", workflow: wf, ...extra });
      watch(wf, r.started_at);
    } catch (e) {
      if (e.running) { watch(wf, null); return; }
      busy(wf, false);
      show(wf, e.message, "bad");
    }
  }

  // ---- Brief dates ----
  function preset(kind) {
    const now = new Date(), y = now.getUTCFullYear(), m = now.getUTCMonth(), day = 864e5;
    let a = now, b = now;
    if (kind === "yesterday") a = b = new Date(now - day);
    else if (kind === "month") a = new Date(Date.UTC(y, m, 1));
    else if (kind === "lastmonth") { a = new Date(Date.UTC(y, m - 1, 1)); b = new Date(Date.UTC(y, m, 0)); }
    else if (kind !== "today") a = new Date(now - (Number(kind) - 1) * day);
    $("#bc-from").value = ymd(a); $("#bc-to").value = ymd(b);
  }
  function createBrief() {
    let a = $("#bc-from").value, b = $("#bc-to").value || a;
    if (!a) { show("brief", "Pick the first date.", "bad"); return; }
    if (a > b) { [a, b] = [b, a]; $("#bc-from").value = a; $("#bc-to").value = b; }
    const today = ymd(new Date());
    if (a > today) { show("brief", "That start date is in the future.", "bad"); return; }
    if (b > today) { b = today; $("#bc-to").value = b; }
    if ((Date.parse(b) - Date.parse(a)) / 864e5 + 1 > 92) { show("brief", "Pick at most 92 days at a time.", "bad"); return; }
    start("brief", { from: a, to: b });
  }

  // ---- wiring ----
  let attached = false;
  function roleKnown() {
    const on = isAdmin();
    $("#run-news").hidden = !on;
    $("#brief-create").hidden = !on;
    if (!on || attached) return;
    attached = true;
    if (matchMedia("(max-width: 760px)").matches) $("#brief-create").open = false;   // phones: the brief itself comes first
    if (!$("#bc-from").value) preset("7");
    // if one is already running (started earlier, or by the schedule), pick it up
    if (!A.DEMO) call({ action: "status" }).then((s) => {
      for (const wf of Object.keys(JOBS)) if (s[wf] && s[wf].status !== "completed") { show(wf, "", ""); watch(wf, null); }
    }).catch(() => { /* not set up yet: the buttons explain when pressed */ });
  }
  $("#run-news").addEventListener("click", () => start("collect"));
  $("#bc-run").addEventListener("click", createBrief);
  for (const b of $$("[data-bc-preset]")) b.addEventListener("click", () => preset(b.dataset.bcPreset));
  new MutationObserver(roleKnown).observe(document.body, { attributes: true, attributeFilter: ["data-role"] });
  roleKnown();
})();
