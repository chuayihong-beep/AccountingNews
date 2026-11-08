/* Brief page: list of briefs, read, edit (team), approve (admin), copy for Outlook, download Word. */
(() => {
  "use strict";
  const A = window.PAOApp;
  if (!A) return;
  const $ = (s, el = document) => el.querySelector(s);
  const esc = A.esc;
  let briefs = [], current = null, editing = false;
  let editor = null, draftMd = null, textMode = false;   // Edit screen: story cards (default) or plain text

  const canEdit = () => A.can("edit_briefs");
  const canApprove = () => A.can("approve_briefs");
  const canSend = () => A.can("send_briefs");
  const fmt = (iso) => (iso ? new Date(iso).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" }) : "");

  // ---------- safe Markdown -> HTML (everything is escaped first) ----------
  function inline(text, sources) {
    let h = esc(text);
    h = h.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>").replace(/(^|[^*])\*(?!\s)(.+?)\*(?!\*)/g, "$1<em>$2</em>");
    // [title](https://...) - recap titles link straight to the page
    h = h.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, (m, text, url) => `<a href="${url}" target="_blank" rel="noopener">${text}</a>`);
    h = h.replace(/\[(\d{1,3}(?:\s*[,;]\s*\d{1,3})+)\]/g, (m, list) => list.split(/[,;]/).map((n) => `[${n.trim()}]`).join(""));  // [3, 5] -> [3][5]
    h = h.replace(/\[(\d{1,3})\]/g, (m, n) => {
      const s = sources[n];
      return s && s.url ? `<a class="cite" href="${esc(s.url)}" target="_blank" rel="noopener" title="${esc(s.pao + ": " + s.title)}">[${n}]</a>`
        : `<span class="cite" title="${s ? esc(s.pao + ": " + s.title) : ""}">[${n}]</span>`;
    });
    h = h.replace(/(^|\s)(https?:\/\/[^\s<]+)/g, (m, sp, url) => `${sp}<a href="${url}" target="_blank" rel="noopener">${url.length > 70 ? url.slice(0, 67) + "…" : url}</a>`);
    return h;
  }
  function render(md, sourceList) {
    const sources = {};
    for (const s of sourceList || []) sources[s.n] = s;
    const out = [];
    let list = null, para = [];
    const flushPara = () => { if (para.length) { out.push(`<p>${inline(para.join(" "), sources)}</p>`); para = []; } };
    const flushList = () => { if (list) { out.push(`<ul>${list.join("")}</ul>`); list = null; } };
    for (const raw of (md || "").split("\n")) {
      const line = raw.trimEnd();
      let m;
      if (!line.trim()) { flushPara(); flushList(); continue; }
      if ((m = line.match(/^(#{1,4})\s+(.*)$/))) { flushPara(); flushList(); const lv = Math.min(4, m[1].length + 1); out.push(`<h${lv}>${inline(m[2], sources)}</h${lv}>`); continue; }
      if ((m = line.match(/^\s*[-*•]\s+(.*)$/))) { flushPara(); (list ||= []).push(`<li>${inline(m[1], sources)}</li>`); continue; }
      if ((m = line.match(/^>\s?(.*)$/))) { flushPara(); flushList(); out.push(`<blockquote>${inline(m[1], sources)}</blockquote>`); continue; }
      if ((m = line.match(/^\[(\d+)\]\s+(.*)$/))) { flushPara(); (list ||= []).push(`<li class="src-line">${inline(`[${m[1]}] ` + m[2], sources)}</li>`); continue; }
      flushList(); para.push(line.trim());
    }
    flushPara(); flushList();
    return out.join("\n");
  }

  // ---------- recap layout (newsletter template) ----------
  // The recap is stored as plain Markdown with fixed sections, so staff can edit it as text:
  //   # Title / **date** / > staff note / ## Highlights (### [title](url), meta line, text) /
  //   ## Other high (- bullets) / ## Medium (- bullets) / ## No news found
  // Older briefs (numbered [n] citations) have no "## Highlights" and keep the old rendering.
  const LABELS = { other: "Other key news", medium: "Also worth knowing" };
  const HEADER_IMAGE = "recap-header.jpg";   // replace this file to change the recap's header (see README)
  const BRAND = "#D1204E";
  function parseRecap(md) {
    if (!/^##\s+Highlights\s*$/im.test(md || "")) return null;
    const r = { title: "", date: "", highlights: [], other: [], medium: [], quiet: "", extra: [] };
    let sec = "", cur = null;
    for (const raw of md.split("\n")) {
      const line = raw.trim();
      let m;
      if ((m = line.match(/^#\s+(.*)$/))) { r.title = m[1]; continue; }
      if ((m = line.match(/^##\s+(.*)$/))) {
        const t = m[1].toLowerCase();
        sec = t.startsWith("highlight") ? "hl" : t.startsWith("other") ? "other" : /^(medium|mid|also)/.test(t) ? "medium"
          : t.startsWith("no news") ? "quiet" : "extra";
        if (sec === "extra") r.extra.push(line);
        cur = null; continue;
      }
      if (!sec) { if ((m = line.match(/^\*\*(.+)\*\*$/))) r.date = m[1]; continue; }   // title block; staff note skipped
      if (sec === "hl") {
        if ((m = line.match(/^###\s+(.*)$/))) { cur = { title: m[1], meta: "", text: [] }; r.highlights.push(cur); }
        else if (cur && line) { if (!cur.meta) cur.meta = line; else cur.text.push(line); }
      } else if (sec === "other" || sec === "medium") {
        if ((m = line.match(/^[-*•]\s+(.*)$/))) r[sec].push(m[1]);
      } else if (sec === "quiet") { if (line) r.quiet += (r.quiet ? " " : "") + line; }
      else r.extra.push(raw);
    }
    return r;
  }
  // "[title](url) · ICAI · 1 Nov 2026" -> title link + grey details
  function splitLine(s) {
    const m = s.match(/^(\[[^\]]+\]\([^)]+\)|[^·]+?)\s*·\s*(.*)$/);
    return m ? [m[1], m[2]] : [s, ""];
  }
  function recapHtml(r) {
    const box = (label, inner, cls) => `<section class="recap-box ${cls}"><h2>${esc(label)}</h2><div class="recap-body">${inner}</div></section>`;
    const hl = (h) => h ? `<h3>${inline(h.title, {})}</h3><p class="recap-meta">${inline(h.meta, {})}</p><p>${inline(h.text.join(" "), {})}</p>` : `<p class="muted">Nothing stood out in this period.</p>`;
    const list = (rows) => rows.length ? `<ul>${rows.map((x) => { const [t, d] = splitLine(x); return `<li>${inline(t, {})}${d ? `<span class="recap-meta">${inline(d, {})}</span>` : ""}</li>`; }).join("")}</ul>` : `<p class="muted">None this time.</p>`;
    // the header picture is one file (web/recap-header.jpg), shown whole; swap the file to change it
    return `<header class="recap-head"><img class="recap-banner" src="${HEADER_IMAGE}" alt="CAPA - Confederation of Asian and Pacific Accountants">
        <p class="recap-date">${inline(r.date, {})}</p><h1 class="recap-title">${esc(r.title || "Recap")}</h1></header>
      <div class="recap-grid">${box("Highlight 1", hl(r.highlights[0]), "hl1")}${box("Highlight 2", hl(r.highlights[1]), "hl2")}
        ${box(LABELS.other, list(r.other), "other")}${box(LABELS.medium, list(r.medium), "mid")}</div>
      ${r.extra.length ? render(r.extra.join("\n"), []) : ""}
      ${r.quiet ? `<p class="recap-quiet"><b>No news found:</b> ${esc(r.quiet)}</p>` : ""}`;
  }
  // Same layout for Outlook and Word: tables and inline styles only (email clients ignore page CSS).
  function recapEmailHtml(r, headerSrc) {
    const font = "font-family:'Century Gothic',Poppins,Arial,sans-serif";
    const a = (h) => h.replace(/<a href=/g, `<a style="color:#1d1d1f;text-decoration:underline;text-decoration-color:${BRAND}" href=`);
    const head = (label) => `<div style="background:${BRAND};color:#fff;${font};font-weight:700;font-size:17px;text-align:center;padding:10px 8px">${esc(label)}</div>`;
    const cell = (inner, extra = "") => `<td valign="top" style="border:1px solid #d9d9de;padding:0;${extra}">${inner}</td>`;
    const hl = (h) => `<div style="padding:12px 14px">${h ? `<p style="margin:0 0 6px;${font};font-size:16px;font-weight:700;line-height:1.3">${a(inline(h.title, {}))}</p>
        <p style="margin:0 0 8px;font-size:12px;color:#6e6e73">${inline(h.meta, {})}</p><p style="margin:0;font-size:14px;line-height:1.5">${a(inline(h.text.join(" "), {}))}</p>`
      : `<p style="margin:0;color:#6e6e73">Nothing stood out in this period.</p>`}</div>`;
    const list = (rows) => `<div style="padding:10px 14px">${rows.length ? rows.map((x) => { const [t, d] = splitLine(x);
      return `<p style="margin:0 0 10px;font-size:14px;line-height:1.4">${a(inline(t, {}))}${d ? `<br><span style="font-size:12px;color:#6e6e73">${inline(d, {})}</span>` : ""}</p>`; }).join("")
      : `<p style="margin:0;color:#6e6e73">None this time.</p>`}</div>`;
    return `<table role="presentation" width="760" cellpadding="0" cellspacing="0" style="width:760px;max-width:100%;border-collapse:collapse;font-family:Calibri,Arial,sans-serif;color:#1d1d1f">
      ${headerSrc ? `<tr><td colspan="3" style="padding:0"><img src="${headerSrc}" width="760" alt="CAPA - Confederation of Asian and Pacific Accountants" style="display:block;width:100%;max-width:760px;height:auto;border:0"></td></tr>` : ""}
      <tr><td colspan="3" style="padding:12px 0 16px"><p style="margin:0;${font};font-size:15px;font-weight:700">${inline(r.date, {})}</p>
        <p style="margin:2px 0 0;${font};font-size:40px;font-weight:800;color:${BRAND};letter-spacing:.5px;line-height:1.1">${esc((r.title || "Recap").toUpperCase())}</p></td></tr>
      <tr>${cell(head("Highlight 1") + hl(r.highlights[0]), "width:33%")}${cell(head("Highlight 2") + hl(r.highlights[1]), "width:33%")}
        <td rowspan="2" valign="top" style="border:1px solid #d9d9de;padding:0;width:34%">${head(LABELS.other) + list(r.other)}</td></tr>
      <tr><td colspan="2" valign="top" style="border:1px solid #d9d9de;padding:0">${head(LABELS.medium) + list(r.medium)}</td></tr>
      ${r.quiet ? `<tr><td colspan="3" style="padding:12px 0 0;font-size:12px;color:#6e6e73"><b>No news found:</b> ${esc(r.quiet)}</td></tr>` : ""}
      <tr><td colspan="3" style="padding:12px 0 0;font-size:12px;color:#6e6e73">This recap was prepared with AI assistance from public sources and reviewed by CAPA staff. Titles link to the original pages.</td></tr>
    </table>`;
  }
  const asset = (name) => new URL(name, location.href).href;
  const recapForEmail = (r) => recapEmailHtml(r, asset(HEADER_IMAGE));

  // ---------- data ----------
  async function load() {
    if (A.DEMO) { briefs = (A.api.demo?.briefs || []).slice(); return; }
    const { data, error } = await A.db.from("briefs").select("*").order("created_at", { ascending: false }).limit(52);
    if (error) throw error;
    briefs = data;
  }

  // an admin just created one from the page: show the new draft
  document.addEventListener("pao:brief-ready", () => {
    if ($("#brief-view").hidden) return;
    load().then(() => { current = briefs[0] || null; editing = false; draw(); }).catch(() => {});
  });

  // ---------- view ----------
  function open() {
    for (const sel of [".filters", ".layout", "#admin-view", "#status-view", "#ask-view"]) document.querySelector(sel).hidden = true;
    $("#brief-view").hidden = false;
    window.scrollTo(0, 0);
    $("#brief-list").innerHTML = "<li class='muted'>Loading…</li>";
    load().then(() => { current = current && briefs.find((b) => b.id === current.id) || briefs[0] || null; editing = false; draw(); })
      .catch((e) => {
        $("#brief-list").innerHTML = "";
        $("#brief-body").innerHTML = `<p class="error-box">${esc(/briefs|schema cache|does not exist/i.test(e.message)
          ? "The database needs updating: paste supabase/update-4.sql into Supabase > SQL Editor and Run." : e.message)}</p>`;
      });
  }
  function close() {
    $("#brief-view").hidden = true;
    document.querySelector(".filters").hidden = false;
    document.querySelector(".layout").hidden = false;
    document.querySelector("#search-wrap").hidden = false;
  }
  function draw() {
    $("#brief-list").innerHTML = briefs.length ? briefs.map((b) => `<li><button type="button" data-brief="${b.id}" class="${current && b.id === current.id ? "active" : ""}">
        <span>${fmt(b.period_start)} – ${fmt(b.period_end)}</span>
        <span class="brief-status ${b.status}">${b.status === "approved" ? "Approved" : "Draft"}</span></button></li>`).join("")
      : `<li class="muted small">No briefs yet. One is written every day at noon, or admins can create one now with Create a brief above.</li>`;
    const t = $("#brief-tools"), body = $("#brief-body");
    if (!current) { t.innerHTML = ""; body.innerHTML = ""; return; }
    const meta = `<p class="muted small">Written ${new Date(current.created_at).toLocaleString()} by ${esc(current.models_used || "?")}
      · ${current.stats?.items ?? "?"} items in this period${current.edited_by ? ` · edited by ${esc(current.edited_by)} ${fmt(current.edited_at)}` : ""}
      ${current.status === "approved" ? ` · <b>approved</b> by ${esc(current.approved_by || "")} ${fmt(current.approved_at)}` : ""}
      ${current.sent_at ? ` · <b>sent</b> to ${current.sent_to ?? "?"} people by ${esc(current.sent_by || "")} ${fmt(current.sent_at)}` : ""}</p>
      ${current.send_requested_at && !current.sent_at ? `<p class="send-state">Sending: queued by ${esc(current.send_requested_by || "")} at ${new Date(current.send_requested_at).toLocaleTimeString()}. It goes out within about 10 minutes - refresh to check.</p>` : ""}
      ${current.send_error ? `<p class="send-state bad">Sending failed: ${esc(current.send_error)}. Fix it and press Send to mailing list again.</p>` : ""}`;
    if (!editing) { editor = null; draftMd = null; textMode = false; }
    if (editing) {
      const md = draftMd ?? current.content ?? "";
      const asCards = !textMode && window.BriefEditor && parseRecap(md);
      t.innerHTML = `<button class="btn primary" id="brief-save" type="button">Save</button><button class="btn ghost" id="brief-cancel" type="button">Cancel</button>`
        + (parseRecap(md) ? `<button class="btn ghost" id="brief-textmode" type="button">${asCards ? "Edit as text" : "Back to story cards"}</button>` : "");
      if (asCards) {
        body.innerHTML = meta + `<p class="muted small">Edit each story in its card. Use the arrows to reorder, <b>Move to…</b> to change section, and <b>+ Add a story</b> to pull one in from the tracker. Nothing is saved until you press <b>Save</b>.</p><div id="brief-blocks"></div>`;
        editor = window.BriefEditor.mount($("#brief-blocks"), md, {
          esc, toast: A.toast, items: () => A.state.items,
          abbr: (id) => { const p = A.state.paos.find((x) => x.id === id); return p ? (p.abbr || p.name) : ""; },
        });
        return;
      }
      editor = null;
      body.innerHTML = meta + `<p class="muted small">${parseRecap(md)
          ? "Plain text. Keep the section headings (<code>## Highlights</code>, <code>## Other high</code>, <code>## Medium</code>). Each highlight is <code>### [title](link)</code>, then a details line, then the summary. Other stories are <code>- [title](link) · details</code>. The first line (<code># ...</code>) is the title."
          : "Plain text with simple formatting: <code>## Heading</code>, <code>- bullet</code>, <code>**bold**</code>. Keep the [n] numbers - they link to the sources."}</p>
        <textarea id="brief-text" spellcheck="true">${esc(md)}</textarea>`;
      return;
    }
    t.innerHTML = [
      canEdit() ? `<button class="btn" id="brief-edit" type="button">Edit</button>` : "",
      canApprove() ? `<button class="btn ${current.status === "approved" ? "ghost" : "primary"}" id="brief-approve" type="button">${current.status === "approved" ? "Back to draft" : "Approve"}</button>` : "",
      canSend() && current.status === "approved" && current.send_requested_at && !current.sent_at
        ? `<button class="btn" id="brief-cancel-send" type="button">Cancel sending</button>`
        : canSend() && current.status === "approved" ? `<button class="btn primary" id="brief-send" type="button">${current.sent_at ? "Send again…" : "Send to mailing list…"}</button>` : "",
      `<button class="btn ghost" id="brief-copy" type="button" title="Copy with formatting, then paste into an Outlook email">Copy for email</button>`,
      `<button class="btn ghost" id="brief-word" type="button">Download Word</button>`,
      canApprove() ? `<button class="btn ghost danger" id="brief-delete" type="button" title="Delete this brief">Delete</button>` : "",
    ].join("");
    const recap = parseRecap(current.content);
    body.innerHTML = meta + (recap
      ? `<article class="brief-doc recap" id="brief-doc">${recapHtml(recap)}</article>`
      : `<article class="brief-doc" id="brief-doc">${render(current.content, current.sources)}</article>`);
  }

  // ---------- actions ----------
  const isDirty = () => !editing ? false : editor ? editor.dirty() : ($("#brief-text") ? $("#brief-text").value !== (current.content || "") : false);
  async function save() {
    const content = editor ? editor.markdown() : $("#brief-text").value;
    const patch = { content, edited_by: A.state.user?.email || null, edited_at: new Date().toISOString() };
    try {
      if (!A.DEMO) { const { error } = await A.db.from("briefs").update(patch).eq("id", current.id); if (error) throw error; }
      Object.assign(current, patch); editing = false; draw(); A.toast("Saved");
    } catch (e) { A.toast("Couldn't save: " + e.message, true); }
  }
  async function remove() {
    const queued = current.send_requested_at && !current.sent_at;
    if (queued) return A.toast("This brief is queued to send - press Cancel sending first", true);
    const label = `${fmt(current.period_start)} – ${fmt(current.period_end)}`;
    if (!confirm(`Delete the brief for ${label}?${current.sent_at ? " It was already emailed; that email isn't affected." : ""} This can't be undone.`)) return;
    try {
      if (!A.DEMO) { const { error } = await A.db.rpc("delete_brief", { brief_id: current.id }); if (error) throw error; }
      briefs = briefs.filter((b) => b.id !== current.id);
      current = briefs[0] || null; editing = false; draw(); A.toast("Brief deleted");
    } catch (e) {
      A.toast(/delete_brief|function/i.test(e.message) ? "Deleting needs a quick database update (supabase/update-21.sql) - ask your admin" : "Couldn't delete: " + e.message, true);
    }
  }
  async function approve() {
    const next = current.status === "approved" ? "draft" : "approved";
    if (next === "approved" && !confirm("Approve this brief? Do this once you've checked the facts against the sources.")) return;
    try {
      if (!A.DEMO) { const { error } = await A.db.rpc("set_brief_status", { brief_id: current.id, new_status: next }); if (error) throw error; }
      Object.assign(current, { status: next, approved_by: next === "approved" ? A.state.user?.email : null, approved_at: next === "approved" ? new Date().toISOString() : null });
      draw(); A.toast(next === "approved" ? "Approved" : "Back to draft");
    } catch (e) { A.toast("Couldn't change: " + e.message, true); }
  }
  const DOC_CSS = "body{font-family:Calibri,Arial,sans-serif;font-size:11pt;line-height:1.4}h1{font-size:18pt}h2{font-size:14pt;margin-top:14pt}" +
    "h3{font-size:12pt}blockquote{color:#555;border-left:3px solid #ccc;margin:0;padding-left:8px}a{color:#0e5a57}li{margin:2pt 0}";
  // the "draft written by AI - please review" banner is for staff, not recipients
  function forRecipients() {
    const doc = $("#brief-doc").cloneNode(true);
    doc.querySelectorAll("blockquote").forEach((q) => { if (/Draft written by AI|No AI model was available/.test(q.textContent)) q.remove(); });
    doc.insertAdjacentHTML("beforeend", '<p style="font-size:9pt;color:#777">This briefing was prepared with AI assistance from public sources and reviewed by CAPA staff.</p>');
    return doc;
  }
  async function copy() {
    const recap = parseRecap(current.content);
    const doc = forRecipients();
    const html = recap ? recapForEmail(recap) : doc.innerHTML;
    try {
      await navigator.clipboard.write([new ClipboardItem({
        "text/html": new Blob([`<div style="font-family:Calibri,Arial,sans-serif">${html}</div>`], { type: "text/html" }),
        "text/plain": new Blob([doc.innerText], { type: "text/plain" }),
      })]);
      A.toast("Copied - paste into a new Outlook email (Ctrl+V)");
    } catch {
      const r = document.createRange(); r.selectNodeContents($("#brief-doc"));
      const s = getSelection(); s.removeAllRanges(); s.addRange(r);
      A.toast("Selected - press Ctrl+C, then paste into Outlook");
    }
  }
  function word() {
    const recap = parseRecap(current.content);
    const inner = recap ? recapForEmail(recap) : $("#brief-doc").innerHTML;
    const html = `<html xmlns:o="urn:schemas-microsoft-com:office:office" xmlns:w="urn:schemas-microsoft-com:office:word"><head><meta charset="utf-8"><style>${DOC_CSS}</style></head><body>${inner}</body></html>`;
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob(["﻿" + html], { type: "application/msword" }));
    a.download = `CAPA-${recap ? "recap" : "weekly-brief"}-${(current.period_end || "").slice(0, 10)}.doc`;
    a.click(); URL.revokeObjectURL(a.href);
  }

  // ---------- send to mailing list (from the user's own Outlook, everyone in BCC) ----------
  let sendList = [];
  const subject = () => { const r = parseRecap(current.content);
    return r ? `CAPA ${r.title || "recap"}: ${r.date.replace(/\*/g, "")}` : `CAPA weekly intelligence brief: ${fmt(current.period_start)} – ${fmt(current.period_end)}`; };
  async function openSend() {
    try { sendList = (await A.loadMailingList()).filter((m) => m.active).map((m) => m.email); }
    catch (e) { return A.toast(/mailing_list|schema cache|does not exist/i.test(e.message) ? "Database needs updating: run supabase/update-5.sql" : e.message, true); }
    if (!sendList.length) return A.toast("The mailing list is empty - add people on the Admin tab first", true);
    const bcc = sendList.join(";"), subj = encodeURIComponent(subject());
    const owa = `https://outlook.office.com/mail/deeplink/compose?bcc=${encodeURIComponent(bcc)}&subject=${subj}`;
    const mailto = `mailto:?bcc=${encodeURIComponent(sendList.join(","))}&subject=${subj}`;
    const tooLong = owa.length > 1900;
    $("#send-summary").innerHTML = `To <b>${sendList.length}</b> ${sendList.length === 1 ? "person" : "people"} on the mailing list. Subject: <i>${esc(subject())}</i>`
      + (current.sent_at ? `<br><span class="warn-text">Already sent ${fmt(current.sent_at)} by ${esc(current.sent_by || "")}.</span>` : "");
    $("#send-owa").href = tooLong ? `https://outlook.office.com/mail/deeplink/compose?subject=${subj}` : owa;
    $("#send-mailto").href = tooLong ? `mailto:?subject=${subj}` : mailto;
    $("#send-long").hidden = !tooLong;
    $("#send-dialog").showModal();
  }
  async function sendNow() {
    if (current.sent_at && !confirm(`This brief was already sent ${fmt(current.sent_at)}. Send it again to everyone?`)) return;
    try {
      if (!A.DEMO) { const { error } = await A.db.rpc("request_brief_send", { brief_id: current.id }); if (error) throw error; }
      Object.assign(current, { send_requested_at: new Date().toISOString(), send_requested_by: A.state.user?.email, send_error: null, sent_at: null });
      $("#send-dialog").close(); draw(); A.toast("Queued - it will be emailed within about 10 minutes");
    } catch (e) {
      A.toast(/request_brief_send|schema cache|does not exist/i.test(e.message) ? "Database needs updating: run supabase/update-6.sql" : "Couldn't send: " + e.message, true);
    }
  }
  async function cancelSend() {
    try {
      if (!A.DEMO) { const { error } = await A.db.rpc("cancel_brief_send", { brief_id: current.id }); if (error) throw error; }
      Object.assign(current, { send_requested_at: null, send_requested_by: null }); draw(); A.toast("Sending cancelled");
    } catch (e) { A.toast("Couldn't cancel: " + e.message, true); }
  }
  $("#send-now").addEventListener("click", sendNow);
  $("#send-copy").addEventListener("click", copy);
  $("#send-copy-bcc").addEventListener("click", async () => {
    try { await navigator.clipboard.writeText(sendList.join("; ")); A.toast("Addresses copied - paste into BCC"); }
    catch { prompt("Copy these addresses into BCC:", sendList.join("; ")); }
  });
  $("#send-done").addEventListener("click", async () => {
    try {
      if (!A.DEMO) { const { error } = await A.db.rpc("mark_brief_sent", { brief_id: current.id, recipients: sendList.length }); if (error) throw error; }
      Object.assign(current, { sent_at: new Date().toISOString(), sent_by: A.state.user?.email, sent_to: sendList.length });
      $("#send-dialog").close(); draw(); A.toast("Recorded as sent");
    } catch (e) { A.toast("Couldn't record: " + e.message, true); }
  });
  $("#send-close").addEventListener("click", () => $("#send-dialog").close());

  $("#brief-btn").addEventListener("click", open);
  $("#brief-back").addEventListener("click", close);
  $("#brief-view").addEventListener("click", (e) => {
    const b = e.target.closest("[data-brief]");
    if (b) {
      if (editing && isDirty() && !confirm("Discard your unsaved changes?")) return;
      current = briefs.find((x) => String(x.id) === b.dataset.brief); editing = false; return draw();
    }
    const id = e.target.id;
    if (id === "brief-edit") { editing = true; draw(); $("#brief-text")?.focus(); }
    else if (id === "brief-cancel") { if (isDirty() && !confirm("Discard your unsaved changes?")) return; editing = false; draw(); }
    else if (id === "brief-textmode") {
      const md = editor ? editor.markdown() : $("#brief-text").value;
      if (textMode && !parseRecap(md)) return A.toast("That text no longer has the ## Highlights heading, so it can't be shown as cards", true);
      draftMd = md; textMode = !textMode; draw();
    }
    else if (id === "brief-save") save();
    else if (id === "brief-approve") approve();
    else if (id === "brief-copy") copy();
    else if (id === "brief-word") word();
    else if (id === "brief-send") openSend();
    else if (id === "brief-cancel-send") cancelSend();
    else if (id === "brief-delete") remove();
  });
  // leaving other views closes this one
  for (const sel of ["#admin-btn"]) document.querySelector(sel)?.addEventListener("click", () => { $("#brief-view").hidden = true; });
  A.renderBrief = render;   // for tests
  A.parseRecap = parseRecap; A.recapEmailHtml = recapEmailHtml;
})();
