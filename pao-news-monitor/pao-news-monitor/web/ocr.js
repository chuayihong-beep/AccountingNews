/* Screenshots -> items. OCR runs in the browser (Tesseract.js); images never leave the computer.
 * Output: Excel / CSV in the tracker's Import format, or saved straight to the tracker.
 */
(() => {
  "use strict";
  const CFG = window.PAO_CONFIG || {};
  const DEMO = !CFG.SUPABASE_URL || !CFG.SUPABASE_ANON_KEY;
  const SUPABASE_JS = "https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2.116.0/dist/umd/supabase.js";
  const TESSERACT_JS = "https://cdn.jsdelivr.net/npm/tesseract.js@5.1.1/dist/tesseract.min.js";
  const XLSX_JS = "https://cdnjs.cloudflare.com/ajax/libs/xlsx/0.18.5/xlsx.full.min.js";
  const GROUPS = ["Member", "Associate", "Affiliate", "Stakeholder", "Regional network"];
  const TYPES = { news: "News", events: "Event", publications: "Publication", articles: "Newsletter / article", comment: "Opportunity to comment" };
  // Google News edition / language -> OCR language(s); English is always added for names and dates
  const OCR_LANG = { zh: "chi_sim", "zh-HK": "chi_tra", "zh-TW": "chi_tra", ja: "jpn", ko: "kor", vi: "vie", fr: "fra",
    mn: "mon", ne: "nep", bn: "ben", th: "tha", id: "ind", ms: "msa", hi: "hin", si: "sin", ur: "urd", km: "khm", lo: "lao", my: "mya" };

  const $ = (s, el = document) => el.querySelector(s);
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  let db = null, user = null, role = "team", canSave = true, paos = [];
  const rows = [];   // { key, file, url, pao, kind, date, poster, link, title, content, status, progress }
  let nextKey = 1;

  function toast(msg, bad) {
    const t = $("#toast"); t.textContent = msg; t.className = "toast" + (bad ? " bad" : ""); t.hidden = false;
    clearTimeout(toast.t); toast.t = setTimeout(() => (t.hidden = true), 4000);
  }
  function loadScript(src) {
    if (document.querySelector(`script[src="${src}"]`)) return Promise.resolve();
    return new Promise((ok, fail) => {
      const s = document.createElement("script"); s.src = src; s.onload = ok;
      s.onerror = () => fail(new Error("Could not load " + src)); document.head.appendChild(s);
    });
  }

  // ---------- sign-in + PAO list (same as the tracker) ----------
  async function init() {
    if (DEMO) {
      const d = await (await fetch("demo-data.json")).json();
      paos = d.paos.filter((p) => p.id !== "_unmatched_email");
      user = { email: "demo@example.org" }; role = "admin";
      return true;
    }
    await loadScript(SUPABASE_JS);
    db = window.supabase.createClient(CFG.SUPABASE_URL, CFG.SUPABASE_ANON_KEY);
    const { data } = await db.auth.getSession();
    user = data.session?.user || null;
    if (!user) return false;
    const r = await db.rpc("my_role");
    role = r.error ? "team" : (r.data || "team");
    document.querySelector("#signout").addEventListener("click", async () => { await db.auth.signOut(); location.href = "index.html"; });
    if (role === "admin") document.querySelector("#admin-link").hidden = false;
    const p = await db.rpc("my_permissions");
    canSave = role === "admin" || (!p.error && Array.isArray(p.data) ? p.data.includes("add_items") : role === "team");
    const { data: list, error } = await db.from("paos").select("*").eq("active", true).neq("id", "_unmatched_email").order("sort_order");
    if (error) throw error;
    paos = list;
    return true;
  }
  const paoById = (id) => paos.find((p) => p.id === id);
  const paoLabel = (p) => (p.abbr && p.abbr !== p.name ? `${p.abbr} - ${p.name}` : p.name);
  function paoOptions(selected) {
    return GROUPS.map((g) => {
      const list = paos.filter((p) => (p.grp || "Member") === g);
      return list.length ? `<optgroup label="${g}s">${list.map((p) => `<option value="${esc(p.id)}"${p.id === selected ? " selected" : ""}>${esc(paoLabel(p))}</option>`).join("")}</optgroup>` : "";
    }).join("");
  }
  function ocrLang(p) {
    const loc = p?.news_locale || p?.lang || "en";
    const code = OCR_LANG[loc] || OCR_LANG[loc.split("-")[0]];
    return code ? `${code}+eng` : "eng";
  }

  // ---------- OCR ----------
  const workers = {};
  async function worker(lang) {
    await loadScript(TESSERACT_JS);
    if (!workers[lang]) {
      workers[lang] = window.Tesseract.createWorker(lang, 1, {
        logger: (m) => { if (m.status === "recognizing text" && worker.current) worker.current(m.progress); },
      });
    }
    return workers[lang];
  }
  // small text (e.g. "2d • Edited") reads much better enlarged
  async function upscale(file) {
    try {
      const bmp = await createImageBitmap(file);
      const scale = bmp.width < 1400 ? Math.min(3, 1800 / bmp.width) : 1;
      if (scale <= 1.05) return file;
      const c = document.createElement("canvas");
      c.width = Math.round(bmp.width * scale); c.height = Math.round(bmp.height * scale);
      const g = c.getContext("2d"); g.imageSmoothingQuality = "high"; g.drawImage(bmp, 0, 0, c.width, c.height);
      return c;
    } catch { return file; }
  }
  let queue = Promise.resolve();
  function enqueue(row) {
    queue = queue.then(() => readRow(row)).catch(() => {});
  }
  async function readRow(row) {
    if (!rows.includes(row)) return;
    row.status = "reading"; draw(row);
    try {
      const w = await worker(ocrLang(paoById(row.pao)));
      worker.current = (p) => { row.progress = p; const bar = document.querySelector(`[data-key="${row.key}"] progress`); if (bar) bar.value = p; };
      const { data } = await w.recognize(await upscale(row.file));
      worker.current = null;
      const read = interpret(data.text || "", row.file.lastModified || Date.now());
      if (!read.date || row.dateSetByHand) read.date = row.date;    // keep a typed / batch date when the screenshot has none
      Object.assign(row, read);
      row.status = "done";
    } catch (e) {
      row.status = "error"; row.error = e.message || String(e);
    }
    draw(row); updateButtons();
  }

  // Lines that are buttons / counters on LinkedIn, Facebook, X etc., not the post
  const JUNK = /^(like|comment|comments|repost|reposts|share|shares|send|follow|\+ ?follow|following|reply|replies|see translation|translate|see more|…\s*more|\.\.\.\s*more|view analytics|promoted|sponsored|edited|celebrate|support|love|insightful|funny|write a comment|add a comment|most relevant|all reactions)\b.*$|^[\d.,]+\s*[kKmM]?\s*(comments?|reposts?|reactions?|likes?|shares?|views?|followers?)\b.*$|^[\W\d_]{0,3}$/i;
  const MONTHS = "jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec";
  const REL = /\b(\d+)\s*(m|min|mins|minutes?|h|hr|hrs|hours?|d|days?|w|wk|wks|weeks?|mo|mos|months?|y|yr|yrs|years?)\b(\s*ago)?/i;

  function guessDate(text, base) {
    const t = text.replace(/\s+/g, " ");
    let m = t.match(new RegExp(`\\b(\\d{1,2})(?:st|nd|rd|th)?\\s+(${MONTHS})[a-z]*\\.?,?\\s+(20\\d\\d)\\b`, "i"));
    if (m) return ymd(new Date(Date.UTC(+m[3], monthIdx(m[2]), +m[1])));
    m = t.match(new RegExp(`\\b(${MONTHS})[a-z]*\\.?\\s+(\\d{1,2})(?:st|nd|rd|th)?,?\\s+(20\\d\\d)\\b`, "i"));
    if (m) return ymd(new Date(Date.UTC(+m[3], monthIdx(m[1]), +m[2])));
    m = t.match(/\b(20\d\d)[-/.年](\d{1,2})[-/.月](\d{1,2})/);
    if (m) return ymd(new Date(Date.UTC(+m[1], m[2] - 1, +m[3])));
    m = t.match(/\b(\d{1,2})[/.](\d{1,2})[/.](20\d\d)\b/);
    if (m) return ymd(new Date(Date.UTC(+m[3], m[2] - 1, +m[1])));
    m = t.match(new RegExp(`\\b(\\d{1,2})\\s+(${MONTHS})[a-z]*\\b|\\b(${MONTHS})[a-z]*\\s+(\\d{1,2})\\b`, "i"));   // "18 Oct" / "Oct 18" (this year)
    if (m) {
      const y = new Date(base).getFullYear();
      const d = m[1] ? new Date(Date.UTC(y, monthIdx(m[2]), +m[1])) : new Date(Date.UTC(y, monthIdx(m[3]), +m[4]));
      if (d.getTime() > base + 864e5) d.setUTCFullYear(y - 1);
      return ymd(d);
    }
    if (/\byesterday\b/i.test(t)) return ymd(new Date(base - 864e5));
    if (/\b(just now|today|now)\b/i.test(t)) return ymd(new Date(base));
    m = t.match(REL);
    if (m) {
      const n = +m[1], u = m[2].toLowerCase();
      const ms = /^(m|min)/.test(u) && !/^mo/.test(u) ? 6e4 : /^h/.test(u) ? 36e5 : /^d/.test(u) ? 864e5
        : /^w/.test(u) ? 6048e5 : /^mo/.test(u) ? 2592e6 : 31536e6;
      return ymd(new Date(base - n * ms));
    }
    return "";
  }
  const monthIdx = (s) => MONTHS.split("|").indexOf(s.slice(0, 3).toLowerCase());
  const ymd = (d) => d.toISOString().slice(0, 10);

  function interpret(raw, base) {
    const lines = raw.split("\n").map((l) => l.replace(/\s+/g, " ").trim()).filter((l) => l && !JUNK.test(l));
    const date = guessDate(lines.slice(0, 6).join(" ") + " " + raw, base);
    // poster: first short line that isn't a date / "2d •" line
    let poster = "", start = 0;
    for (let i = 0; i < Math.min(lines.length, 4); i++) {
      const l = lines[i];
      if (l.length <= 70 && !REL.test(l) && !/\b(20\d\d|yesterday)\b/i.test(l) && /[A-Za-zÀ-￿]{2}/.test(l)) { poster = l; start = i + 1; break; }
    }
    // skip follower counts / "2d • Edited" lines right under the name
    const meta = (l) => l.length < 50 && (REL.test(l) || /followers|connections|edited|•|·|\bago\b|\+\s*$|visible to/i.test(l));
    while (start < lines.length && start < 5 && meta(lines[start])) start++;
    const body = lines.slice(start).join("\n").trim();
    // title: first sentence of the post (lines in a screenshot wrap mid-sentence)
    const flat = body.replace(/\s*\n\s*/g, " ");
    const sentence = (flat.match(/^.{10,}?[.!?。！？](\s|$)/) || [flat])[0].trim();
    const title = sentence.length > 160 ? sentence.slice(0, 157).replace(/\s+\S*$/, "") + "…" : sentence;
    return { date, poster, title, content: body };
  }

  // ---------- table ----------
  function addFiles(files) {
    const pao = $("#pao").value;
    for (const f of files) {
      if (!f.type.startsWith("image/")) continue;
      const row = { key: nextKey++, file: f, url: URL.createObjectURL(f), pao, kind: "news", date: $("#batch-date").value || "", poster: "",
        link: "", title: "", content: "", status: "waiting", progress: 0 };
      rows.push(row);
      $("#rows").insertAdjacentHTML("beforeend", `<li class="ocr-row" data-key="${row.key}"></li>`);
      draw(row);
      enqueue(row);
    }
    updateButtons();
  }
  function draw(row) {
    const li = document.querySelector(`[data-key="${row.key}"]`);
    if (!li) return;
    const busy = row.status === "waiting" || row.status === "reading";
    li.innerHTML = `
      <button class="thumb" type="button" data-zoom title="Show full size"><img src="${row.url}" alt="Screenshot ${row.key}"></button>
      <div class="ocr-fields">
        <div class="ocr-line">
          <select data-f="pao" aria-label="PAO">${paoOptions(row.pao)}</select>
          <select data-f="kind" aria-label="Type">${Object.entries(TYPES).map(([k, v]) => `<option value="${k}"${row.kind === k ? " selected" : ""}>${v}</option>`).join("")}</select>
          <input data-f="date" type="date" value="${esc(row.date)}" aria-label="Date">
          <input data-f="poster" value="${esc(row.poster)}" placeholder="Posted by" aria-label="Posted by">
          <button class="link small" data-remove type="button">Remove</button>
        </div>
        ${busy ? `<p class="muted small">${row.status === "waiting" ? "Waiting…" : "Reading text…"} <progress max="1" value="${row.progress}"></progress></p>` : ""}
        ${row.status === "error" ? `<p class="error-box small">Couldn't read this image: ${esc(row.error)} <button class="link small" data-retry type="button">Try again</button></p>` : ""}
        <input data-f="title" value="${esc(row.title)}" placeholder="Title / headline" aria-label="Title">
        <textarea data-f="content" rows="4" placeholder="Post text" aria-label="Post text">${esc(row.content)}</textarea>
        <input data-f="link" type="url" value="${esc(row.link)}" placeholder="Link to the post (optional - paste it if you have it)" aria-label="Link">
      </div>`;
  }
  function updateButtons() {
    const ready = rows.filter((r) => r.status === "done" || r.title || r.content);
    for (const id of ["#dl-xlsx", "#dl-csv"]) $(id).disabled = !ready.length;
    $("#save").disabled = !ready.length || !canSave;
    $("#save").title = canSave ? "" : "Your role can download but not save to the tracker";
    $("#clear").disabled = !rows.length;
    $("#apply-date").disabled = !rows.length || !$("#batch-date").value;
    $("#empty").hidden = rows.length > 0;
    const waiting = rows.filter((r) => r.status === "waiting" || r.status === "reading").length;
    $("#count").textContent = rows.length ? `${rows.length} screenshot(s)${waiting ? `, ${waiting} still reading` : ""}` : "";
  }

  // ---------- output ----------
  function records() {
    const abbrCount = {};
    for (const p of paos) abbrCount[(p.abbr || "").toLowerCase()] = (abbrCount[(p.abbr || "").toLowerCase()] || 0) + 1;
    return rows.filter((r) => r.title || r.content).map((r) => {
      const p = paoById(r.pao);
      const paoName = p && p.abbr && abbrCount[p.abbr.toLowerCase()] === 1 ? p.abbr : r.pao;
      return { PAO: paoName, Date: r.date, Type: TYPES[r.kind], Title: r.title || r.content.split("\n")[0].slice(0, 300),
        Content: r.content, "Posted by": r.poster, Link: r.link, Language: (p?.news_locale || p?.lang || "en").split("-")[0] };
    });
  }
  async function download(kind) {
    await loadScript(XLSX_JS);
    const ws = window.XLSX.utils.json_to_sheet(records(), { header: ["PAO", "Date", "Type", "Title", "Content", "Posted by", "Link", "Language"] });
    ws["!cols"] = [{ wch: 12 }, { wch: 11 }, { wch: 12 }, { wch: 50 }, { wch: 80 }, { wch: 24 }, { wch: 40 }, { wch: 9 }];
    const name = `screenshots-${new Date().toISOString().slice(0, 10)}`;
    if (kind === "csv") {
      const csv = window.XLSX.utils.sheet_to_csv(ws);
      const a = document.createElement("a");
      a.href = URL.createObjectURL(new Blob(["﻿" + csv], { type: "text/csv;charset=utf-8" }));
      a.download = name + ".csv"; a.click(); URL.revokeObjectURL(a.href);
    } else {
      const wb = window.XLSX.utils.book_new();
      window.XLSX.utils.book_append_sheet(wb, ws, "Items");
      window.XLSX.writeFile(wb, name + ".xlsx");
    }
  }
  async function sha(text) {
    const buf = await crypto.subtle.digest("SHA-1", new TextEncoder().encode(text));
    return [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, "0")).join("").slice(0, 24);
  }
  async function saveToTracker() {
    const now = new Date().toISOString();
    const items = [];
    for (const r of rows.filter((x) => x.title || x.content)) {
      const p = paoById(r.pao);
      const title = (r.title || r.content.split("\n")[0]).slice(0, 300);
      const published = r.date ? new Date(r.date + "T00:00:00Z").toISOString() : null;
      items.push({
        id: "import-" + await sha([r.pao, title, r.content, published || ""].join("|")),
        pao_id: r.pao, source: "manual", title, url: r.link || null, published_at: published,
        snippet: r.content.slice(0, 500) || null, content: r.content || null,
        source_name: r.poster || `Screenshot by ${user?.email || "team"}`,
        language: (p?.news_locale || p?.lang || "en").split("-")[0], kind: r.kind, first_seen_at: now, is_baseline: false,
      });
    }
    if (DEMO) return toast(`Demo mode: ${items.length} item(s) would be saved`);
    $("#save").disabled = true;
    try {
      let res = await db.from("items").upsert(items, { onConflict: "id", ignoreDuplicates: true }).select("id");
      if (res.error && /kind/.test(res.error.message)) {
        res = await db.from("items").upsert(items.map(({ kind, ...rest }) => rest), { onConflict: "id", ignoreDuplicates: true }).select("id");
      }
      if (res.error) throw res.error;
      const n = res.data.length;
      toast(`Saved ${n} item(s) to the tracker` + (n < items.length ? ` (${items.length - n} were already there)` : "") + ". They're under each PAO as \"Added by team\".");
    } catch (e) {
      toast("Couldn't save: " + e.message, true);
    }
    updateButtons();
  }

  // ---------- wiring ----------
  function wire() {
    $("#files").addEventListener("change", (e) => { addFiles(e.target.files); e.target.value = ""; });
    const drop = $("#drop");
    drop.addEventListener("dragover", (e) => { e.preventDefault(); drop.classList.add("over"); });
    drop.addEventListener("dragleave", () => drop.classList.remove("over"));
    drop.addEventListener("drop", (e) => { e.preventDefault(); drop.classList.remove("over"); addFiles(e.dataTransfer.files); });
    document.addEventListener("paste", (e) => {
      const files = [...(e.clipboardData?.items || [])].filter((i) => i.type.startsWith("image/")).map((i) => {
        const f = i.getAsFile();
        return new File([f], `pasted-${Date.now()}.png`, { type: f.type, lastModified: Date.now() });
      });
      if (files.length) { e.preventDefault(); addFiles(files); }
    });
    $("#rows").addEventListener("input", (e) => {
      const li = e.target.closest("[data-key]"), f = e.target.dataset.f;
      if (!li || !f) return;
      const row = rows.find((r) => r.key === +li.dataset.key);
      row[f] = e.target.value;
      if (f === "date") row.dateSetByHand = true;
      updateButtons();
    });
    $("#rows").addEventListener("click", (e) => {
      const li = e.target.closest("[data-key]");
      if (!li) return;
      const row = rows.find((r) => r.key === +li.dataset.key);
      if (e.target.closest("[data-remove]")) {
        rows.splice(rows.indexOf(row), 1); URL.revokeObjectURL(row.url); li.remove(); updateButtons();
      } else if (e.target.closest("[data-retry]")) {
        row.status = "waiting"; draw(row); enqueue(row);
      } else if (e.target.closest("[data-zoom]")) {
        $("#zoom img").src = row.url; $("#zoom").showModal();
      }
    });
    $("#dl-xlsx").addEventListener("click", () => download("xlsx").catch((e) => toast(e.message, true)));
    $("#dl-csv").addEventListener("click", () => download("csv").catch((e) => toast(e.message, true)));
    $("#save").addEventListener("click", saveToTracker);
    $("#batch-date").addEventListener("input", updateButtons);
    $("#apply-date").addEventListener("click", () => {
      const d = $("#batch-date").value;
      if (!d) return;
      for (const r of rows) { r.date = d; r.dateSetByHand = true; const el = document.querySelector(`[data-key="${r.key}"] [data-f="date"]`); if (el) el.value = d; }
      toast(`Date set to ${d} on all ${rows.length} row(s)`);
    });
    $("#clear").addEventListener("click", () => {
      if (!confirm("Remove all screenshots from this page? (Anything not downloaded or saved is lost.)")) return;
      rows.splice(0).forEach((r) => URL.revokeObjectURL(r.url));
      $("#rows").innerHTML = ""; updateButtons();
    });
    window.addEventListener("beforeunload", (e) => { if (rows.length) { e.preventDefault(); e.returnValue = ""; } });
  }

  init().then((ok) => {
    if (!ok) { $("#signin-needed").hidden = false; return; }
    $("#ocr").hidden = false;
    $("#user").textContent = user.email + (role !== "team" ? ` (${role})` : "");
    $("#pao").innerHTML = paoOptions("");
    try { const last = localStorage.getItem("ocr-last-pao"); if (last && paoById(last)) $("#pao").value = last; } catch { /* ignore */ }
    $("#pao").addEventListener("change", () => { try { localStorage.setItem("ocr-last-pao", $("#pao").value); } catch { /* ignore */ } });
    wire(); updateButtons();
  }).catch((e) => { document.body.insertAdjacentHTML("beforeend", `<p class="error-box">Couldn't start: ${esc(e.message)}</p>`); });

  window.__ocrTest = { interpret, guessDate };   // used by tests
})();
