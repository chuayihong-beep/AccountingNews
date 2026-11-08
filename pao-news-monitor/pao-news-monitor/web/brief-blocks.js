/* The recap as editable blocks.
 *
 * A recap is stored as plain Markdown (see collector/brief.py compose()). This file turns that text into a small
 * model - title, date, highlight cards, "Other key news" and "Also worth knowing" lists - and back again, so the
 * Edit screen can show story cards instead of raw text. Saving writes the SAME Markdown format, so the page, the
 * Outlook copy, the Word file and the mailing-list email all keep working unchanged.
 *
 * Nothing is thrown away: lines this file doesn't understand (a staff note, extra sections, stray text) are kept
 * and written back where they were. No DOM in here, so it can be tested with plain Node.
 */
(() => {
  "use strict";

  const SECTIONS = ["hl", "other", "medium"];
  const MAX_HIGHLIGHTS = 2;                       // the layout has two highlight boxes
  const EMPTY_HL = "Nothing stood out in this period.";
  const EMPTY_LIST = "None this time.";

  const LINK = /^\[([^\]]*)\]\(([^)]*)\)$/;
  const splitLink = (s) => { const m = (s || "").trim().match(LINK); return m ? { title: m[1], url: m[2] } : { title: (s || "").trim(), url: "" }; };
  // "[title](url) · ICAI · 1 Nov 2026" -> title link + details (same split the page uses)
  const splitBullet = (s) => { const m = s.match(/^(\[[^\]]+\]\([^)]+\)|[^·]+?)\s*·\s*(.*)$/); return m ? [m[1], m[2]] : [s, ""]; };

  const oneLine = (t) => (t || "").replace(/\s+/g, " ").trim();
  const mdText = (t) => oneLine((t || "").replace(/\[/g, "(").replace(/\]/g, ")"));     // no brackets or line breaks inside [text]
  const mdUrl = (u) => (u || "").trim().replace(/\s/g, "%20").replace(/\(/g, "%28").replace(/\)/g, "%29");
  const link = (title, url) => (mdUrl(url) ? `[${mdText(title)}](${mdUrl(url)})` : mdText(title));

  function emptyModel() {
    return { title: "", date: "", note: [], hl: [], other: [], medium: [], quiet: "", extra: [], loose: { hl: [], other: [], medium: [] } };
  }

  // Markdown -> model. Returns null for older briefs that aren't in the recap layout.
  function parse(md) {
    if (!/^##\s+Highlights\s*$/im.test(md || "")) return null;
    const m = emptyModel();
    let sec = "head", cur = null, hit;
    for (const raw of md.replace(/\r/g, "").split("\n")) {
      const line = raw.trim();
      if ((hit = line.match(/^##\s+(.*)$/))) {
        const t = hit[1].toLowerCase();
        sec = t.startsWith("highlight") ? "hl" : t.startsWith("other") ? "other" : /^(medium|mid|also)/.test(t) ? "medium"
          : t.startsWith("no news") ? "quiet" : "extra";
        if (sec === "extra") m.extra.push(raw);
        cur = null;
        continue;
      }
      if (sec === "head") {
        if ((hit = line.match(/^#\s+(.*)$/))) m.title = hit[1];
        else if ((hit = line.match(/^\*\*(.+)\*\*$/)) && !m.date) m.date = hit[1];
        else if (line) m.note.push(raw);
      } else if (sec === "hl") {
        if ((hit = line.match(/^###\s+(.*)$/))) { cur = { ...splitLink(hit[1]), meta: "", text: "" }; m.hl.push(cur); }
        else if (line && line === EMPTY_HL) continue;
        else if (line && cur) { if (!cur.meta) cur.meta = line; else cur.text += (cur.text ? " " : "") + line; }
        else if (line) m.loose.hl.push(raw);
      } else if (sec === "other" || sec === "medium") {
        if ((hit = line.match(/^[-*•]\s+(.*)$/))) { const [t, d] = splitBullet(hit[1]); m[sec].push({ ...splitLink(t), details: d }); }
        else if (line && line !== EMPTY_LIST) m.loose[sec].push(raw);
      } else if (sec === "quiet") {
        if (line) m.quiet += (m.quiet ? " " : "") + line;
      } else m.extra.push(raw);
    }
    return m;
  }

  // model -> Markdown, in exactly the shape compose() writes
  function serialize(m) {
    const hl = m.hl.filter((s) => (s.title || "").trim() || (s.url || "").trim());
    const list = (rows) => rows.filter((s) => (s.title || "").trim() || (s.url || "").trim())
      .map((s) => `- ${link(s.title, s.url)}${(s.details || "").trim() ? ` · ${oneLine(s.details)}` : ""}`);
    const out = [`# ${oneLine(m.title)}`, `**${oneLine(m.date)}**`, ""];
    if (m.note.length) out.push(...m.note, "");
    out.push("## Highlights");
    if (!hl.length) out.push(EMPTY_HL);
    for (const s of hl) {
      const text = mdText(s.text);   // like compose(): one line, no [brackets] (they would read as links or [n] citations)
      // the first line under a highlight is its details line: keep one there even if emptied, so the summary can't slide up into it
      out.push(`### ${link(s.title, s.url)}`, oneLine(s.meta) || (text ? "—" : ""), text, "");
    }
    out.push(...m.loose.hl);
    for (const [head, key] of [["## Other high", "other"], ["## Medium", "medium"]]) {
      const rows = list(m[key]);
      out.push(...(key === "other" ? [] : [""]), head, ...(rows.length ? rows : [EMPTY_LIST]), ...m.loose[key]);
    }
    if (oneLine(m.quiet)) out.push("", "## No news found", oneLine(m.quiet));
    if (m.extra.length) out.push("", ...m.extra);
    return out.join("\n").replace(/\n{3,}/g, "\n\n").trim() + "\n";
  }

  // A tracker item -> a story block. `abbr` is the organisation's short name.
  function fromItem(item, abbr) {
    const english = !item.language || /^en/i.test(item.language);
    let title = oneLine(!english && item.ai_summary ? item.ai_summary : item.title);
    if (title.length > 140) title = title.slice(0, 140).replace(/\s+\S*$/, "").replace(/[,;:\-–]+$/, "") + "…";
    const when = item.published_at || item.first_seen_at;
    const day = when ? new Date(when).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" }) : "";
    const details = [abbr || "", day].filter(Boolean).join(" · ");
    return { title, url: item.url || "", details, meta: details, text: oneLine(item.ai_summary) };
  }

  // Moving a story between sections: highlights carry meta + text, the lists carry details.
  function toHighlight(s) { return { title: s.title, url: s.url, meta: s.meta ?? s.details ?? "", text: s.text || "" }; }
  function toListItem(s) { return { title: s.title, url: s.url, details: s.details ?? s.meta ?? "" }; }

  const api = { parse, serialize, fromItem, toHighlight, toListItem, emptyModel, MAX_HIGHLIGHTS, SECTIONS };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else window.BriefBlocks = api;
})();
