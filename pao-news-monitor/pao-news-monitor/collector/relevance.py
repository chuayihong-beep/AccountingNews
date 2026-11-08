"""AI-suggested relevance (Automated Article Relevance Framework v2.0).

After each daily collection, every new item gets a suggested relevance label -
High / Medium / Low / No - and a one-sentence reason. The suggestion is saved in
its own columns (ai_relevance, ai_relevance_reason, ...) and is never overwritten
by staff: when someone clicks a relevance button, that goes in `relevance` as
before, so the original suggestion and the reviewer's decision are both kept.

Everything that uses relevance (tracker filters, weekly brief, Ask AI) uses the
staff label when there is one, otherwise the AI's suggestion.

Needs supabase/update-14.sql. Without it (or without any AI key) this step is
skipped and the collection carries on as normal.
"""
from datetime import timedelta

from .ai import AIUnavailable, Chain, parse_json
from .capa_context import CAPA_PROFILE
from .common import clean, iso, log, now_utc

LEVELS = ("high", "medium", "low", "none")
BATCH = 25
MAX_PER_RUN = 300      # backlog cap per run (keeps within free AI quotas)
LOOKBACK_DAYS = 14     # unlabelled items older than this are left for staff

KIND_TEXT = {"news": "news", "events": "event", "publications": "publication", "articles": "newsletter/article",
             "comment": "opportunity to comment", "leadership": "leadership change on website",
             "contact": "contact details change on website"}

RULES = """You suggest how relevant each collected item is to CAPA. Staff review every suggestion.

""" + CAPA_PROFILE + """

Judge the substance of the item against CAPA's remit: the organisations listed below (CAPA's member PAOs and
key stakeholders), CAPA's themes (AI & digitalisation; talent attraction & retention; sustainability; ethics &
standards incl. IAASB, IESBA, ISSB; other notable regional activity), PAO initiatives and relevant professional
standards. A name or keyword match alone is not enough. If the item is not really about the organisation it was
filed under (an irrelevant name match), it is "none".

Relevance levels:
- high: a direct, material consequence for CAPA priorities, a PAO's capability or mandate, applicable standards,
  or the regional profession is shown (e.g. a standard-setter consultation or new standard, a regulatory change
  affecting the profession, a major PAO initiative with regional reach). A change of President / CEO /
  Secretary-General at a member PAO is high.
- medium: a clear but indirect professional consequence, a practice other PAOs could learn from, or a credible
  emerging signal.
- low: the link is peripheral or routine, or offers little new consequence or transferable value.
- none: no substantive connection to CAPA's remit or relevant professional activity.

Caps (apply by default):
- Examinations (dates, results, pass lists), awards, webinars, event promotion, ceremonial meetings, routine
  appointments (other than a PAO's top leader), generic corporate news, and local tax, market or political
  stories without a wider professional consequence: "low" at most. Use "none" when they are routine,
  ceremonial, promotional or unrelated.
- Raise above the cap only when the item shows a substantive change or impact; then say why in the reason.
- CAPA is regional: one country's domestic matter is low unless it has a clear regional or profession-wide angle.

Reply with JSON only: a list of {"n": <item number>, "relevance": "high"|"medium"|"low"|"none",
"reason": "<one sentence, max 25 words, on the practical consequence for CAPA or why it is low/none>"}.
One entry per item, in order."""


def register(paos):
    lines = []
    for p in paos:
        if p.get("id") == "_unmatched_email" or p.get("active") is False:
            continue
        lines.append(f"- {p.get('abbr') or p['id']}: {p.get('name') or ''} ({p.get('jurisdiction') or ''}; {p.get('grp') or ''})")
    return "Organisations (abbreviation: name (jurisdiction; group)):\n" + "\n".join(lines)


def item_line(n, it, paos):
    p = paos.get(it["pao_id"], {})
    date = (it.get("published_at") or it.get("first_seen_at") or "")[:10]
    snippet = it.get("snippet") or ""
    snippet = "" if snippet.startswith("Search: ") else clean(snippet, 200)
    kind = KIND_TEXT.get(it.get("kind") or "news", "news")
    return (f"{n}. [{p.get('abbr') or it['pao_id']} | {it.get('source')} | {kind} | {date}] {clean(it.get('title'), 240)}"
            + (f" - {snippet}" if snippet else ""))


def classify(chain, items, paos_by_id, system):
    """Ask the AI in batches. Returns {item_id: (level, reason, model)}; stops quietly if no model answers."""
    out = {}
    for start in range(0, len(items), BATCH):
        batch = items[start:start + BATCH]
        user = "\n".join(item_line(n, it, paos_by_id) for n, it in enumerate(batch, 1))
        try:
            text, model = chain.ask("fast", system, user, max_tokens=4000, temperature=0.1, feature="relevance")
        except AIUnavailable as e:
            log.warning("relevance suggestions stopped: %s", e)
            break
        data = parse_json(text)
        if not isinstance(data, list):
            log.info("relevance batch %d: unreadable answer from %s", start // BATCH + 1, model)
            continue
        for obj in data:
            try:
                it = batch[int(obj["n"]) - 1]
            except (KeyError, ValueError, IndexError, TypeError):
                continue
            level = str(obj.get("relevance") or "").strip().lower()
            level = {"no": "none", "med": "medium", "not relevant": "none"}.get(level, level)
            if level in LEVELS:
                out[it["id"]] = (level, clean(str(obj.get("reason") or ""), 300) or None, model)
    return out


def suggest(store, chain=None, now=None):
    """Label unlabelled items from the last LOOKBACK_DAYS. Returns a one-line summary (never raises)."""
    now = now or now_utc()
    try:
        items = store.items_needing_relevance(iso(now - timedelta(days=LOOKBACK_DAYS)), MAX_PER_RUN)
    except Exception as e:  # noqa: BLE001  (column missing = update-14.sql not run yet)
        log.warning("relevance suggestions skipped: %s", e)
        return "AI relevance: skipped (run supabase/update-14.sql)" if "ai_relevance" in str(e) else f"AI relevance: skipped ({type(e).__name__})"
    if not items:
        return "AI relevance: nothing new to label"
    chain = chain or Chain()
    if not chain.chain("fast"):
        return "AI relevance: skipped (no AI key available to the collector)"
    paos = store.load_pao_rows()
    paos_by_id = {p["id"]: p for p in paos}
    system = RULES + "\n\n" + register(paos)
    got = classify(chain, items, paos_by_id, system)
    getattr(chain, "flush_usage", lambda _s: None)(store)
    if got:
        at = iso(now_utc())
        by_id = {it["id"]: it for it in items}
        store.save_item_ai([
            {"id": i, "pao_id": by_id[i]["pao_id"], "source": by_id[i]["source"], "title": by_id[i]["title"],
             "ai_relevance": level, "ai_relevance_reason": reason, "ai_relevance_model": model, "ai_relevance_at": at}
            for i, (level, reason, model) in got.items()])
    counts = {lv: sum(1 for v in got.values() if v[0] == lv) for lv in LEVELS}
    left = len(items) - len(got)
    return (f"AI relevance: labelled {len(got)} item(s) - {counts['high']} high, {counts['medium']} medium, "
            f"{counts['low']} low, {counts['none']} none" + (f"; {left} left for next run" if left else ""))
