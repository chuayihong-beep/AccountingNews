/* Ask AI - a view inside the tracker (index.html#ask): real-time Q&A about one PAO or the whole region,
   via the ask-ai Supabase Edge Function (see supabase/functions/ask-ai).
   It reuses the tracker's sign-in, database connection, PAO list and permissions, so switching tabs
   doesn't reload anything, and a conversation is still there when you come back to the tab. */
(() => {
  "use strict";
  const A = window.PAOApp;
  const $ = (s, el = document) => el.querySelector(s);
  const esc = A.esc;

  let ready = false, threadId = null, messages = [], sending = false;

  function show(id) {
    for (const x of ["#ai-demo", "#ai-no-perm", "#ai-main"]) $(x).hidden = x !== id;
  }

  // Runs each time the tab opens; fills the PAO picker the first time.
  function setup() {
    if (A.DEMO) return show("#ai-demo");
    if (!A.can("ask_ai")) return show("#ai-no-perm");
    if (!ready) {
      const paos = A.state.paos.filter((p) => p.id !== "_unmatched_email" && p.active !== false);
      $("#ai-pao").innerHTML = `<option value="_region">Whole region (all PAOs)</option>` +
        paos.map((p) => `<option value="${esc(p.id)}">${esc(p.abbr || p.name)}${p.jurisdiction ? ` (${esc(p.jurisdiction)})` : ""}</option>`).join("");
      $("#ai-pao").value = paos[0]?.id || "_region";   // a single PAO first, as before
      placeholder();
      render();
      ready = true;
    }
    show("#ai-main");
  }

  function open() {
    for (const sel of [".filters", ".layout", "#brief-view", "#admin-view", "#status-view"]) document.querySelector(sel).hidden = true;
    $("#ask-view").hidden = false;
    setup();
    window.scrollTo(0, 0);
  }
  function close() {
    $("#ask-view").hidden = true;
    for (const sel of [".filters", ".layout"]) document.querySelector(sel).hidden = false;
  }

  $("#ask-nav").addEventListener("click", open);
  $("#ask-back").addEventListener("click", close);
  $("#ai-new").addEventListener("click", () => { threadId = null; messages = []; $("#ai-new").disabled = true; render(); });
  $("#ai-download").addEventListener("click", download);
  $("#ai-pao").addEventListener("change", () => { threadId = null; messages = []; placeholder(); render(); });
  $("#ai-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    if (sending) return;
    const q = $("#ai-question").value.trim();
    if (!q) return;
    sending = true;
    $("#ai-ask").disabled = true; $("#ai-ask").textContent = "Asking…";
    messages.push({ role: "user", content: q, at: new Date().toISOString() });
    render();
    $("#ai-question").value = "";
    try {
      // never spin forever: give up after 2 minutes with a clear message
      const timeout = new Promise((_, fail) => setTimeout(() => fail(new Error("No answer after 2 minutes - the AI services may be busy. Please try again.")), 120_000));
      const { data, error } = await Promise.race([
        A.db.functions.invoke("ask-ai", { body: { pao_id: $("#ai-pao").value, thread_id: threadId, question: q } }),
        timeout,
      ]);
      if (error) {
        // The function sends back a readable reason (e.g. "AI providers all failed"); show that, not the generic wrapper.
        let detail = "";
        try { detail = (await error.context.json()).error || ""; } catch { /* no readable body */ }
        throw new Error(detail || error.message);
      }
      if (data?.error) throw new Error(data.error);
      threadId = data.thread_id;
      messages.push({ role: "assistant", content: data.answer, cited_item_ids: data.cited_item_ids, sources: data.sources || [], model: data.model, at: new Date().toISOString() });
      $("#ai-new").disabled = false;
    } catch (err) {
      messages.push({ role: "error", content: err.message || "Something went wrong." });
    }
    sending = false;
    $("#ai-ask").disabled = false; $("#ai-ask").textContent = "Ask";
    render();
    $("#ai-question").focus();
  });

  function render() {
    $("#ai-thread").innerHTML = messages.map((m) => {
      if (m.role === "user") return `<div class="ai-msg ai-user">${esc(m.content)}</div>`;
      if (m.role === "error") return `<div class="ai-msg ai-error">${esc(m.content)}</div>`;
      const n = m.cited_item_ids?.length || 0;
      const meta = [n ? `Cited ${n} collected item${n === 1 ? "" : "s"}` : "", m.model ? `answered by ${m.model}` : ""].filter(Boolean).join(" · ");
      const cited = meta ? `<p class="muted small">${esc(meta)}</p>` : "";
      return `<div class="ai-msg ai-assistant">${escMd(m.content, m.sources)}${sourcesList(m.sources)}${cited}</div>`;
    }).join("") || `<p class="empty-note">Ask a question about the selected PAO - e.g. "What's changed recently?" or "What are possible routes of collaboration?"</p>`;
    $("#ai-download").disabled = !messages.some((m) => m.role === "assistant");
    $("#ai-note").textContent = threadId ? "Replies continue this conversation. Start a new question to begin a fresh one." : "";
    // bring the newest message into view from its top, so a long answer is read from the start
    const last = $("#ai-thread").lastElementChild;
    if (last && messages.length) last.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  // Download the conversation as a text file, with each answer's sources listed under it.
  // Plain text opens in Word, so no Word-specific file is needed.
  function download() {
    const pao = $("#ai-pao").selectedOptions[0]?.textContent || "";
    const lines = [`CAPA Ask AI - ${pao}`, `Downloaded ${new Date().toLocaleString("en-GB", { timeZone: "Asia/Kuala_Lumpur" })} (MYT)`,
      "Answers are based on collected items and background on file. Check sources before use.", ""];
    for (const m of messages) {
      if (m.role === "user") lines.push("YOU:", m.content, "");
      else if (m.role === "assistant") {
        lines.push("ANSWER" + (m.model ? ` (${m.model})` : "") + ":", m.content, "");
        (m.sources || []).forEach((src, i) => lines.push(`  [${i + 1}] ${src.title || ""} - ${src.url || ""}`.trimEnd()));
        if ((m.sources || []).length) lines.push("");
      }
    }
    const blob = new Blob(["\ufeff" + lines.join("\r\n")], { type: "text/plain;charset=utf-8" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `capa-ask-ai-${new Date().toISOString().slice(0, 10)}.txt`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  }

  // Only ever link to http(s) addresses - never javascript: or other schemes.
  const safeUrl = (u) => (/^https?:\/\//i.test(u || "") ? u : "");

  function placeholder() {
    $("#ai-question").placeholder = $("#ai-pao").value === "_region"
      ? "e.g. How are PAOs across the region approaching AI adoption, and what concerns are they raising?"
      : "e.g. What are possible routes of collaboration with this PAO?";
  }

  // Sources list under an answer: every article the AI cited, numbered as in the text.
  function sourcesList(sources) {
    if (!sources?.length) return "";
    const li = sources.map((x) => {
      const url = safeUrl(x.url);
      const title = url ? `<a href="${esc(url)}" target="_blank" rel="noopener">${esc(x.title || url)}</a>` : esc(x.title || "(untitled)");
      return `<li value="${Number(x.n)}">${title} <span class="muted small">${esc([x.pao, x.source, x.date].filter(Boolean).join(" · "))}</span></li>`;
    }).join("");
    return `<details class="ai-sources"><summary>Sources (${sources.length})</summary><ol>${li}</ol></details>`;
  }

  // Light markdown for AI answers: headings (#..####), bullets (* / -), numbered lists, tables,
  // --- dividers, **bold**, *italic*, and [n] citations turned into links to the article.
  // Everything is HTML-escaped first, so nothing in an answer can inject markup.
  function escMd(s, sources) {
    const byN = new Map((sources || []).map((x) => [Number(x.n), x]));
    const cite = (n) => {
      const x = byN.get(Number(n)), url = x && safeUrl(x.url);
      return url ? `<a class="ai-cite" href="${esc(url)}" target="_blank" rel="noopener" title="${esc(x.title || "")}">${n}</a>` : n;
    };
    const inline = (t) => t
      .replace(/\*\*(.+?)\*\*/g, "<b>$1</b>")
      .replace(/(^|[\s(])\*(?!\s)(.+?)\*(?=[\s).,;:!?]|$)/g, "$1<i>$2</i>")
      .replace(/\[(\d+(?:\s*[,/]\s*\d+)*)\]/g, (_, inner) => `[${inner.replace(/\d+/g, cite)}]`);
    const cells = (row) => row.replace(/^\|/, "").replace(/\|$/, "").split("|").map((c) => c.trim());
    const out = [];
    let list = null, para = [], table = [];
    const flushPara = () => { if (para.length) { out.push(`<p>${para.map(inline).join("<br>")}</p>`); para = []; } };
    const closeList = () => { if (list) { out.push(`</${list}>`); list = null; } };
    const flushTable = () => {
      if (!table.length) return;
      const rows = table.filter((r) => !/^\|?\s*:?-{2,}/.test(r));   // drop the |---|---| separator line
      const [head, ...body] = rows;
      out.push(`<div class="ai-table"><table><thead><tr>${cells(head).map((c) => `<th>${inline(c)}</th>`).join("")}</tr></thead><tbody>${
        body.map((r) => `<tr>${cells(r).map((c) => `<td>${inline(c)}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`);
      table = [];
    };
    // models sometimes write HTML line breaks: turn them into real breaks (a space inside table rows)
    const fixed = String(s ?? "").split("\n").map((l) => l.replace(/[ \t]*<br\s*\/?>[ \t]*/gi, l.trimStart().startsWith("|") ? " " : "\n")).join("\n");
    for (const raw of esc(fixed).split("\n")) {
      const line = raw.trim();
      let m;
      if (line.startsWith("|")) { flushPara(); closeList(); table.push(line); continue; }
      flushTable();
      if (!line) { flushPara(); closeList(); continue; }
      if (/^(-{3,}|\*{3,}|_{3,})$/.test(line)) { flushPara(); closeList(); out.push("<hr>"); continue; }
      if ((m = line.match(/^(#{1,4})\s+(.*)$/))) { flushPara(); closeList(); const h = m[1].length <= 3 ? "h3" : "h4"; out.push(`<${h}>${inline(m[2])}</${h}>`); continue; }
      const bullet = line.match(/^[*\-•]\s+(.*)$/), numbered = line.match(/^\d+[.)]\s+(.*)$/);
      if (bullet || numbered) {
        flushPara();
        const kind = bullet ? "ul" : "ol";
        if (list !== kind) { closeList(); out.push(`<${kind}>`); list = kind; }
        out.push(`<li>${inline((bullet || numbered)[1])}</li>`);
        continue;
      }
      closeList();
      para.push(line);
    }
    flushTable(); flushPara(); closeList();
    return out.join("");
  }

  // exposed for the test page only (renders an answer without calling the AI)
  A.askAiRender = escMd;
})();
