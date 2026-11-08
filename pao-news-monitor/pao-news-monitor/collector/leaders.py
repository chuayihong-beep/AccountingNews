"""Leaders on file: each organisation's President, Deputy President(s) and Vice President(s) - names only.

Read from the leadership pages that page watch already saves (the organisation's own public pages).
Only the role, the name exactly as the page shows it, the page address and the date are stored -
nothing else about the person. Ask AI uses this list for questions like "who is their president?".

Safety: a name is kept only if it appears word for word in the saved page text, so the AI cannot add
a name the page doesn't show. If the AI finds nobody, the names already on file are kept.

A PAO is read again when its leadership page changes, or at least every REFRESH_DAYS days.
Needs supabase/update-19.sql; without it (or without an AI key) this step is skipped and the
collection carries on as normal.
"""
import re
from datetime import datetime, timedelta

from .ai import AIUnavailable, Chain, parse_json
from .common import clean, iso, log, now_utc

ROLES = ("President", "Deputy President", "Vice President")
LIMITS = {"President": 1, "Deputy President": 3, "Vice President": 6}
MAX_PER_RUN = 15        # organisations per run (stays inside free AI quotas; the rest follow next run)
REFRESH_DAYS = 30
MAX_PAGE_CHARS = 4000

SYSTEM = """You read lines saved from a professional accountancy organisation's own leadership page.
List its CURRENT President, Deputy President(s) and Vice President(s). Names only.
Rules:
- Copy each name exactly as it is written in the lines (keep titles such as Dr, CA or Datuk when they are written with the name).
- Ignore past or former presidents, council or board members, CEOs, secretaries, treasurers, committee chairs and everyone else.
- "Vice-President" and "Senior Vice President" count as "Vice President". A "President-elect" is not the President.
- If the lines do not clearly name someone in a role, leave that role out. Never guess.
Reply with JSON only: {"leaders": [{"role": "President" | "Deputy President" | "Vice President", "name": "<name>"}]}"""


def norm_role(role):
    r = re.sub(r"[\s_-]+", " ", str(role or "")).strip().lower()
    if r == "president":
        return "President"
    if r.startswith("deputy president"):
        return "Deputy President"
    if r.endswith("vice president"):
        return "Vice President"
    return None


def _squash(s):
    return re.sub(r"\s+", " ", s or "").strip().lower()


def valid_name(name, page_text):
    """The name as written, if it looks like a person's name and is on the page; else None."""
    name = clean(str(name or ""), 120)
    if len(name) < 3 or len(name.split()) > 8 or re.search(r"\d|@|https?:|www\.|[<>{}|]", name):
        return None
    return name if _squash(name) in _squash(page_text) else None


def extract(chain, pao, text):
    """[{role, name}] read from one organisation's page text, or None if the answer was unreadable."""
    user = f"Organisation: {pao.get('name') or pao['id']} ({pao.get('abbr') or pao['id']})\n\n" \
           f"Lines from its leadership page(s):\n{text}"
    answer, model = chain.ask("fast", SYSTEM, user, max_tokens=1500)
    data = parse_json(answer)
    if isinstance(data, dict):
        data = data.get("leaders")
    if not isinstance(data, list):
        return None, model
    out, seen, counts = [], set(), {}
    for obj in data:
        if not isinstance(obj, dict):
            continue
        role, name = norm_role(obj.get("role")), valid_name(obj.get("name"), text)
        if not role or not name or (role, name.lower()) in seen or counts.get(role, 0) >= LIMITS[role]:
            continue
        seen.add((role, name.lower()))
        counts[role] = counts.get(role, 0) + 1
        out.append({"role": role, "name": name})
    return out, model


def _when(value):
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def update(store, page_rows, chain=None, now=None):
    """page_rows: the watched-page rows saved in this run. Returns a one-line summary (never raises)."""
    now = now or now_utc()
    try:
        if not store.leaders_ready():
            return "Leaders: skipped (run supabase/update-19.sql)"
    except Exception as e:  # noqa: BLE001
        return f"Leaders: skipped ({type(e).__name__})"

    pages = {}
    for row in page_rows:
        if row.get("kind") == "leadership" and row.get("snapshot"):
            pages.setdefault(row["pao_id"], []).append(row)
    if not pages:
        return "Leaders: no leadership pages saved this run"
    paos = {p["id"]: p for p in store.load_pao_rows()}

    def due(pid):
        changed = any(r.get("last_changed_at") or r.get("first_seen_at") for r in pages[pid])
        checked = _when(paos.get(pid, {}).get("leaders_checked_at"))
        return changed or checked is None or checked < now - timedelta(days=REFRESH_DAYS)

    todo = [pid for pid in sorted(pages) if pid in paos and due(pid)]
    if not todo:
        return "Leaders: up to date"
    chain = chain or Chain()
    if not chain.chain("fast"):
        return "Leaders: skipped (no AI key available to the collector)"

    found = kept = 0
    note = ""
    for pid in todo[:MAX_PER_RUN]:
        rows = sorted(pages[pid], key=lambda r: r["url"])
        text = "\n".join(r["snapshot"] for r in rows)[:MAX_PAGE_CHARS]
        try:
            leaders, model = extract(chain, paos[pid], text)
        except AIUnavailable as e:
            note = f"; stopped: {str(e)[:120]}"
            break
        if leaders is None:
            continue                       # unreadable answer: try again next run
        if leaders:
            for ld in leaders:             # the page the name is on
                ld["source_url"] = next((r["url"] for r in rows if _squash(ld["name"]) in _squash(r["snapshot"])),
                                        rows[0]["url"])
            store.replace_leaders(pid, [dict(ld, pao_id=pid, as_of=now.date().isoformat(), updated_by="page watch",
                                             updated_at=iso(now)) for ld in leaders])
            found += 1
        else:
            kept += 1                      # nobody named: keep what's on file
        store.mark_leaders_checked(pid, iso(now))
    left = max(0, len(todo) - MAX_PER_RUN)
    log.info("leaders: %s updated, %s unchanged, %s left", found, kept, left)
    return (f"Leaders: updated {found} organisation(s)" + (f", {kept} with no names found (kept what was on file)" if kept else "")
            + (f"; {left} left for next run" if left else "") + note)
