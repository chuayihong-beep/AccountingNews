/* The brief's Edit screen: story cards instead of raw text.
 *   BriefEditor.mount(element, markdown, { esc, items, abbr, toast }) -> { markdown(), dirty() }
 * Each story is a card (title, link, details, and a summary for highlights) that can be moved up/down, moved to
 * another section, deleted, or added from the tracker. Reading and writing the stored text is brief-blocks.js. */
(() => {
  "use strict";
  const B = window.BriefBlocks;
  if (!B) return;

  const SECTIONS = {
    hl: { name: "Highlights", hint: "The two lead stories. They fill Highlight 1 and Highlight 2 in the email.", one: "Highlight" },
    other: { name: "Other key news", hint: "", one: "Story" },
    medium: { name: "Also worth knowing", hint: "", one: "Story" },
  };
  const ORDER = ["hl", "other", "medium"];

  function mount(el, markdown, opts) {
    const esc = opts.esc;
    let m = B.parse(markdown);
    if (!m) return null;
    const original = B.serialize(m);
    let undo = [], adding = null, query = "";

    const snapshot = () => { undo.push(JSON.stringify(m)); if (undo.length > 50) undo.shift(); };
    const full = () => m.hl.filter((s) => (s.title || s.url || "").trim()).length >= B.MAX_HIGHLIGHTS;
    const usedUrls = () => new Set(ORDER.flatMap((k) => m[k]).map((s) => (s.url || "").trim()).filter(Boolean));

    function card(sec, i, s) {
      const isHl = sec === "hl";
      const moves = ORDER.filter((k) => k !== sec).map((k) =>
        `<option value="${k}"${k === "hl" && full() ? " disabled" : ""}>${esc(SECTIONS[k].name)}${k === "hl" && full() ? " (full)" : ""}</option>`).join("");
      return `<div class="be-card" data-sec="${sec}" data-i="${i}">
        <div class="be-card-head"><b>${isHl ? `Highlight ${i + 1}` : `Story ${i + 1}`}</b>
          <span class="be-tools">
            <button type="button" class="btn small ghost" data-act="up" title="Move up"${i === 0 ? " disabled" : ""}>▲</button>
            <button type="button" class="btn small ghost" data-act="down" title="Move down"${i === m[sec].length - 1 ? " disabled" : ""}>▼</button>
            <select data-act="move" aria-label="Move to another section"><option value="">Move to…</option>${moves}</select>
            <button type="button" class="btn small ghost danger" data-act="del">Delete</button></span></div>
        <label>Title<input data-f="title" value="${esc(s.title)}"></label>
        <label>Details<input data-f="${isHl ? "meta" : "details"}" value="${esc(isHl ? s.meta : s.details)}" placeholder="ICAI · 5 Nov 2026"></label>
        <label>Link<span class="be-link"><input data-f="url" value="${esc(s.url)}" placeholder="https://…">${s.url ? `<a href="${esc(s.url)}" target="_blank" rel="noopener" title="Open the link">open</a>` : ""}</span></label>
        ${isHl ? `<label>Summary<textarea data-f="text" rows="4">${esc(s.text)}</textarea></label>` : ""}
      </div>`;
    }

    function results() {
      const q = query.trim().toLowerCase(), used = usedUrls();
      const rows = (opts.items() || []).filter((it) => !it.removed_at && it.title && it.url)
        .filter((it) => !q || `${it.title} ${opts.abbr(it.pao_id)}`.toLowerCase().includes(q))
        // not-yet-used stories first (newest first), so a full page of "already in the brief" never hides the rest
        .sort((a, b) => (used.has(a.url) - used.has(b.url)) || (b.published_at || b.first_seen_at || "").localeCompare(a.published_at || a.first_seen_at || ""))
        .slice(0, 20);
      return rows.length ? rows.map((it) => {
        const day = (it.published_at || it.first_seen_at || "").slice(0, 10);
        const dup = used.has(it.url);
        return `<button type="button" class="be-result" data-act="pick" data-id="${esc(it.id)}"${dup ? " disabled" : ""}>
          <span class="be-result-meta">${esc(opts.abbr(it.pao_id))} · ${esc(day)}${dup ? " · already in the brief" : ""}</span>${esc(it.title)}</button>`;
      }).join("") : `<p class="muted small">Nothing matches. Only news already loaded in the tracker is searched.</p>`;
    }

    function section(sec) {
      const meta = SECTIONS[sec], isFull = sec === "hl" && full();
      return `<section class="be-sec" data-sec="${sec}"><h3>${esc(meta.name)}${meta.hint ? ` <small class="muted">${esc(meta.hint)}</small>` : ""}</h3>
        ${m[sec].map((s, i) => card(sec, i, s)).join("") || `<p class="muted small">No stories here yet.</p>`}
        ${isFull ? `<p class="muted small">Highlights are full (two). Move one out to make room.</p>`
          : `<button type="button" class="btn small" data-act="add">${adding === sec ? "Close" : "+ Add a story"}</button>`}
        ${adding === sec ? `<div class="be-add"><input type="search" class="be-search" placeholder="Search the tracker's news…" value="${esc(query)}">
          <div class="be-results">${results()}</div>
          <button type="button" class="btn small ghost" data-act="blank">Write one myself</button></div>` : ""}
      </section>`;
    }

    function render() {
      el.innerHTML = `<div class="be">
        <div class="be-top">
          <label>Title<input data-top="title" value="${esc(m.title)}"></label>
          <label>Dates<input data-top="date" value="${esc(m.date)}"></label>
          <button type="button" class="btn small ghost" data-act="undo"${undo.length ? "" : " disabled"}>Undo</button>
        </div>
        ${ORDER.map(section).join("")}
        <section class="be-sec"><h3>No news found <small class="muted">Organisations with nothing this period (leave empty to hide)</small></h3>
          <input data-top="quiet" aria-label="Organisations with no news this period" value="${esc(m.quiet)}"></section>
        ${m.extra.length ? `<p class="muted small">This brief also has ${m.extra.length} line(s) of extra text. They are kept as they are; use <b>Edit as text</b> to change them.</p>` : ""}
      </div>`;
    }

    const at = (node) => { const c = node.closest(".be-card"); return c ? [c.dataset.sec, Number(c.dataset.i)] : [null, -1]; };
    const focusCard = (sec, i) => el.querySelector(`.be-card[data-sec="${sec}"][data-i="${i}"] input`)?.focus();

    function addStory(sec, story) {
      if (sec === "hl" && full()) { opts.toast("Highlights are full (two). Move one out first.", true); return false; }
      snapshot();
      m[sec].push(sec === "hl" ? B.toHighlight(story) : B.toListItem(story));
      adding = null; query = "";
      render(); focusCard(sec, m[sec].length - 1);
      return true;
    }

    el.addEventListener("input", (e) => {
      const t = e.target;
      if (t.classList.contains("be-search")) { query = t.value; el.querySelector(".be-results").innerHTML = results(); return; }
      if (t.dataset.top) { m[t.dataset.top] = t.value; return; }
      const [sec, i] = at(t);
      if (sec && t.dataset.f) m[sec][i][t.dataset.f] = t.value;
    });

    el.addEventListener("change", (e) => {
      const t = e.target;
      if (t.dataset.act !== "move" || !t.value) return;
      const [sec, i] = at(t), to = t.value;
      if (to === "hl" && full()) { opts.toast("Highlights are full (two). Move one out first.", true); t.value = ""; return; }
      snapshot();
      const [s] = m[sec].splice(i, 1);
      m[to].push(to === "hl" ? B.toHighlight(s) : B.toListItem(s));
      render();
      opts.toast(`Moved to ${SECTIONS[to].name}`);
    });

    el.addEventListener("click", (e) => {
      const b = e.target.closest("[data-act]");
      if (!b || b.tagName === "SELECT") return;
      const act = b.dataset.act, [sec, i] = at(b);
      if (act === "undo") { if (undo.length) { m = JSON.parse(undo.pop()); render(); } return; }
      if (act === "add") { const s = b.closest(".be-sec").dataset.sec; adding = adding === s ? null : s; query = ""; render(); el.querySelector(".be-search")?.focus(); return; }
      if (act === "blank") { addStory(b.closest(".be-sec").dataset.sec, { title: "", url: "", details: "", meta: "", text: "" }); return; }
      if (act === "pick") {
        const it = (opts.items() || []).find((x) => String(x.id) === b.dataset.id);
        if (it) addStory(b.closest(".be-sec").dataset.sec, B.fromItem(it, opts.abbr(it.pao_id)));
        return;
      }
      if (!sec) return;
      if (act === "del") { snapshot(); m[sec].splice(i, 1); render(); opts.toast("Deleted - Undo brings it back"); }
      else if (act === "up" || act === "down") {
        const j = act === "up" ? i - 1 : i + 1;
        if (j < 0 || j >= m[sec].length) return;
        snapshot();
        [m[sec][i], m[sec][j]] = [m[sec][j], m[sec][i]];
        render(); focusCard(sec, j);
      }
    });

    render();
    return { markdown: () => B.serialize(m), dirty: () => B.serialize(m) !== original };
  }

  window.BriefEditor = { mount };
})();
