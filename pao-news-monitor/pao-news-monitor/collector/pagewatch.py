"""Source 5: page watch - spots silent leadership and contact changes.

Some PAOs change President or move office without any press release. Every
run, for each PAO this reads:
  - its leadership page(s): President, Vice-President, CEO / Executive
    Director / Secretary-General (council members and lower are ignored),
  - its contact page: address, phone numbers, emails.

Only those lines are kept (not the whole page), so unrelated edits don't
raise alarms. When they differ from last time, an item appears on the web page
under the PAO showing what was removed and what was added.

Pages are found automatically from the site's menu. If the wrong page is
picked, set leadership_url / contact_url in paos.csv (several: separate with |).
The first time a page is read, it's just remembered - nothing is reported.
"""
import hashlib
import re
from datetime import timezone
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup

from .common import Item, SourceResult, base_domain, clean, fetch, iso, make_id, now_utc

SOURCE = "page_watch"
BLOCKED_STATUSES = {401, 403, 406, 429, 503}
MAX_LEADERSHIP_PAGES = 3

# ---- which lines matter ----
ROLE_WORDS = [
    r"president", r"vice[\s-]?president", r"deputy president", r"chief executive", r"\bceo\b",
    r"executive director", r"secretary[\s-]general", r"director[\s-]general", r"chairman", r"chairperson",
    r"\bchair\b", r"managing director", r"registrar",
    "会长", "會長", "理事长", "理事長", "主席", "秘书长", "秘書長", "総裁", "会長", "회장", "사무총장",
    "chủ tịch", "tổng thư ký", "président", "présidente", "directeur général", "directrice générale",
    r"\bketua\b", r"\bpresiden\b", "अध्यक्ष", "ерөнхийлөгч",
]
ROLE_RX = re.compile("|".join(ROLE_WORDS), re.I)
EMAIL_RX = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE_RX = re.compile(r"(?:\+|\b)\d[\d\s().-]{7,}\d")
ADDRESS_RX = re.compile(
    r"\b(street|st\.|road|rd\.|avenue|ave\.|lane|drive|building|bldg|tower|floor|level|suite|unit|block|"
    r"p\.?\s?o\.?\s?box|jalan|lorong|district|city|postal|postcode|zip)\b|"
    r"[0-9]+号|路|街|楼|樓|대로|빌딩|đường|phường|quận|rue|boulevard",
    re.I)

# ---- noise that changes on its own (never a real leadership/contact change) ----
# Page-view counters ("Hits: 947", "Views 1,203", "1203 visitors"), "Last updated <date>" stamps and
# "online now" counts. Stripped from every watched line - old and new copies alike - before comparing.
_N = r"\d[\d,.\s]*"
NOISE_RX = re.compile(
    rf"^(?:(?:hits?|views?|page\s?views?|visitors?|visits?|reads?|online(?:\s+(?:now|users?))?|"
    rf"访问量|浏览|點閱|瀏覽|조회수?|lượt xem)\s*[:：]?\s*{_N}"
    rf"|{_N}\s*(?:hits?|views?|visitors?|visits?|reads?)"
    rf"|(?:last\s+)?(?:updated|modified)(?:\s+on)?\s*[:：]?.*)$",
    re.I)


def denoise(line):
    """Drop counter / last-updated pieces from a watched line ("Hits: 947 | VP | Name" -> "VP | Name")."""
    parts = [p for p in line.split(" | ") if not NOISE_RX.match(p.strip())]
    return " | ".join(parts)


def denoise_all(lines):
    return sorted({d for d in (denoise(x) for x in lines) if d})


# ---- which pages to read ----
LEADERSHIP_LINK = [
    (0, r"president|office[\s-]?bearers?|leadership|our leaders|chief executive|\bceo\b|executive director|"
        r"secretary[\s-]general|会长|會長|理事长|理事長|役員|임원|lãnh đạo|président|gouvernance"),
    (1, r"governance|board|council|management|executive|secretariat|our people|our team|"
        r"领导|領導|理事会|理事會|組織|ban chấp hành|bureau"),
    (2, r"about|who we are|organi[sz]ation|关于|關於|概要|소개|giới thiệu|à propos|qui sommes"),
]
CONTACT_LINK = re.compile(r"contact|联系|聯絡|聯繫|お問い合わせ|アクセス|연락|오시는|liên hệ|nous contacter|reach us|location", re.I)
NOT_A_PAGE = re.compile(r"\.(pdf|jpg|jpeg|png|gif|zip|docx?|xlsx?)($|\?)|mailto:|tel:|javascript:|facebook|linkedin|twitter|youtube|instagram", re.I)
LEADERSHIP_SKIP = re.compile(r"past[\s-]?president|former[\s-]?president|message|communiqu|news|speech|event|award", re.I)

# When a site's links don't say "leadership", look for the President another way (quietly - misses
# here are expected and are not reported as errors): the site's own search for "president", then
# a few common page addresses. A page only counts if it really names a top role.
PRESIDENT_SEARCHES = ("/?s=president", "/search?q=president", "/search?query=president", "/search?keyword=president")
COMMON_LEADERSHIP_PATHS = (
    "/about-us/leadership", "/about/leadership", "/leadership", "/about-us/council", "/about/council", "/council",
    "/about-us/office-bearers", "/office-bearers", "/about-us/board", "/about/board", "/president",
)
SEARCH_URL = re.compile(r"[?&](s|q|query|keyword|search)=", re.I)


def page_lines(html, keep_footer=False):
    """Visible text, one line per block element."""
    soup = BeautifulSoup(html, "lxml")
    drop = ["script", "style", "noscript", "nav", "svg", "form", "iframe"]
    if not keep_footer:
        drop += ["header", "footer"]
    for bad in soup(drop):
        bad.decompose()
    text = soup.get_text("\n")
    return [clean(x) for x in text.split("\n") if clean(x)]


def leadership_lines(html):
    """Short lines naming a top role, joined with their neighbours (which usually hold the name)."""
    lines = page_lines(html)
    out = []
    for i, line in enumerate(lines):
        if len(line) > 160 or not ROLE_RX.search(line):
            continue
        if re.search(r"past[\s-]?presidents?|former[\s-]?presidents?|president'?s message|from the president", line, re.I):
            continue
        block = [x for x in lines[max(0, i - 1): i + 2] if len(x) <= 90]
        out.append(" | ".join(block))
    return denoise_all(out)


def contact_lines(html):
    lines = page_lines(html, keep_footer=True)
    out = []
    for line in lines:
        if len(line) > 200:
            continue
        if NOISE_RX.match(line):
            continue
        if EMAIL_RX.search(line) or PHONE_RX.search(line) or ADDRESS_RX.search(line):
            out.append(line)
    return denoise_all(out)


def _same_site(url, domain):
    host = (urlsplit(url).hostname or "").lower().removeprefix("www.")
    return bool(host) and (host == domain or host.endswith("." + domain))


def find_pages(html, base_url):
    """(leadership pages, contact page) from a page's links."""
    soup = BeautifulSoup(html, "lxml")
    domain = base_domain(base_url)
    ranked, contact = [], None
    seen = set()
    for a in soup.find_all("a", href=True):
        href = urljoin(base_url, a["href"]).split("#")[0]
        if not href.startswith("http") or NOT_A_PAGE.search(href) or not _same_site(href, domain):
            continue
        text = clean(a.get_text(" "))
        if len(text) > 50:
            continue
        hay = f"{text} {urlsplit(href).path}"
        key = href.rstrip("/").lower()
        if key in seen or key == base_url.rstrip("/").lower():
            continue
        if contact is None and CONTACT_LINK.search(hay):
            contact = href
            seen.add(key)
            continue
        if LEADERSHIP_SKIP.search(hay):
            continue
        for rank, rx in LEADERSHIP_LINK:
            if re.search(rx, hay, re.I):
                ranked.append((rank, len(href), href))
                seen.add(key)
                break
    ranked.sort()
    return [h for _, _, h in ranked], contact


def search_for_leadership(peek, website):
    """Leadership pages for a site whose links never say "leadership": first the site's own search for
    "president", then a few common addresses. A page is only kept if it names a top role.
    peek(url) returns a response, or None for anything that didn't open."""
    parts = urlsplit(website)
    root = f"{parts.scheme or 'https'}://{parts.netloc}"
    found = []

    def names_a_leader(url):
        r = peek(url)
        if r is not None and leadership_lines(r.text):
            key = r.url.rstrip("/").lower()
            if key not in {u.rstrip("/").lower() for u in found}:
                found.append(r.url)

    for path in PRESIDENT_SEARCHES:
        r = peek(root + path)
        if r is None:
            continue
        candidates = [u for u in find_pages(r.text, r.url)[0] if not SEARCH_URL.search(u)]
        for url in candidates[:3]:
            names_a_leader(url)
            if len(found) >= MAX_LEADERSHIP_PAGES:
                break
        break   # one search page that opened is enough (many sites ignore the query and show the homepage)
    if not found:
        for path in COMMON_LEADERSHIP_PATHS:
            names_a_leader(root + path)
            if found:
                break
    return found[:MAX_LEADERSHIP_PAGES]


def snapshot_hash(lines):
    return hashlib.sha1("\n".join(lines).encode("utf-8")).hexdigest()[:16]


def diff(old_lines, new_lines):
    old, new = set(old_lines), set(new_lines)
    return sorted(old - new), sorted(new - old)


def describe(kind, removed, added):
    what = "Leadership" if kind == "leadership" else "Contact details"
    parts = []
    if removed:
        parts.append("Removed:\n" + "\n".join("  - " + x for x in removed[:12]))
    if added:
        parts.append("Added:\n" + "\n".join("  + " + x for x in added[:12]))
    first = (added or removed)[0]
    title = f"{what} changed on website: {'+ ' if added else '- '}{first}"
    return clean(title, 300), "\n".join(parts)


def collect(pao, prev_pages, fetcher=None, browser_mode=False):
    """prev_pages: {(pao_id, url, kind): row} from the watched_pages table."""
    fetcher = fetcher or fetch
    res = SourceResult(pao.id, SOURCE)
    if not pao.website and not pao.leadership_url and not pao.contact_url:
        res.skipped, res.message = True, "No website listed"
        return res
    now = now_utc()
    notes, blocked = [], False

    def get(url):
        nonlocal blocked
        try:
            r = fetcher(url)
        except Exception as e:  # noqa: BLE001
            blocked = True
            notes.append(f"couldn't open {url} ({type(e).__name__})")
            return None
        if r.status >= 400:
            blocked = blocked or r.status in BLOCKED_STATUSES
            notes.append(f"{url} returned error {r.status}")
            return None
        return r

    # which pages to watch
    lead_pages = pao.split(pao.leadership_url)
    contact_pages = pao.split(pao.contact_url)
    if (not lead_pages or not contact_pages) and pao.website:
        home = get(pao.website)
        if home is None:
            res.ok = False
            res.needs_browser = not browser_mode and blocked
            res.message = "; ".join(notes) or "homepage not reachable"
            return res
        found_lead, found_contact = find_pages(home.text, home.url)
        # leadership pages are often one level down, under "About us"
        if found_lead and not any(re.search(LEADERSHIP_LINK[0][1], u, re.I) for u in found_lead[:3]):
            about = get(found_lead[0])
            if about is not None:
                more, c2 = find_pages(about.text, about.url)
                found_lead = more + [u for u in found_lead if u not in more]
                found_contact = found_contact or c2
        lead_pages = lead_pages or found_lead[:MAX_LEADERSHIP_PAGES]
        contact_pages = contact_pages or ([found_contact] if found_contact else [])

    # no leadership link found: pages that worked before (saved snapshots) beat guessing again
    if not lead_pages:
        lead_pages = [u for (pid, u, kind), row in prev_pages.items()
                      if pid == pao.id and kind == "leadership" and (row or {}).get("snapshot")][:MAX_LEADERSHIP_PAGES]

    def peek(url):
        """Like get(), but a miss is expected and not reported (used when hunting for the President)."""
        try:
            r = fetcher(url)
        except Exception:  # noqa: BLE001
            return None
        return r if r.status < 400 else None

    checked = {"leadership": 0, "contact": 0}

    def watch(kind, url, extract):
        r = get(url)
        if r is None:
            return
        lines = extract(r.text)
        prev = prev_pages.get((pao.id, url, kind))
        old_lines = (prev or {}).get("snapshot", "").split("\n") if (prev or {}).get("snapshot") else []
        # older snapshots were saved before counters were ignored - clean them the same way
        old_lines = denoise_all(old_lines)
        row = {"pao_id": pao.id, "url": url, "kind": kind, "last_checked_at": iso(now),
               "status": "ok", "message": f"{len(lines)} line(s) watched"}
        if not lines:
            # nothing recognisable: keep the old snapshot rather than report everything as removed
            row.update(status="warning", message="no names/contact lines found on this page")
            if not prev:
                row.update(snapshot="", first_seen_at=iso(now))
            res.pages.append(row)
            return
        checked[kind] += 1
        row["snapshot"] = "\n".join(lines)
        if not prev or not old_lines:
            row["first_seen_at"] = iso(now)
            res.pages.append(row)
            return
        removed, added = diff(old_lines, lines)
        if removed or added:
            title, body = describe(kind, removed, added)
            res.items.append(Item(
                id=make_id(pao.id, SOURCE, url, snapshot_hash(lines)), pao_id=pao.id, source=SOURCE,
                title=title, url=url, published_at=iso(now.astimezone(timezone.utc)), snippet=body,
                content=f"Before:\n{chr(10).join(old_lines)}\n\nNow:\n{chr(10).join(lines)}",
                source_name=urlsplit(r.url).netloc, language=pao.language, kind=kind))
            row["last_changed_at"] = iso(now)
        res.pages.append(row)

    for url in lead_pages:
        watch("leadership", url, leadership_lines)
    # The site doesn't call it "leadership" (or those pages name nobody): search the site for "president".
    # Skipped when staff set leadership_url themselves - they chose the page.
    if not checked["leadership"] and not pao.leadership_url and pao.website:
        found = [u for u in search_for_leadership(peek, pao.website) if u not in lead_pages]
        for url in found:
            watch("leadership", url, leadership_lines)
        if checked["leadership"]:
            lead_pages = lead_pages + found
            notes.append("leadership page found by searching the site for 'president'")
    for url in contact_pages:
        watch("contact", url, contact_lines)

    if not lead_pages:
        notes.append("no leadership page found - set leadership_url in paos.csv")
    if not contact_pages:
        notes.append("no contact page found - set contact_url in paos.csv")
    if not checked["leadership"] and not checked["contact"] and (lead_pages or contact_pages):
        res.needs_browser = not browser_mode and blocked
        if blocked:
            res.ok = False
    summary = f"Watching {checked['leadership']} leadership + {checked['contact']} contact page(s)"
    if res.items:
        summary = f"{len(res.items)} change(s) found. " + summary
    res.message = "; ".join([summary] + notes)
    return res
