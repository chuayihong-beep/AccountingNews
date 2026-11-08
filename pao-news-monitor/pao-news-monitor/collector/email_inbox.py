"""Source 4: press releases emailed to the monitor inbox (Gmail via IMAP).

Needs two secrets: GMAIL_ADDRESS and GMAIL_APP_PASSWORD (a Google
"app password", not the normal password). Read-only: nothing is deleted
or marked as read.

Each email is matched to a PAO by:
  1. the sender's domain matching the PAO's website domain, otherwise
  2. the PAO's full name or abbreviation appearing in the subject/body.
Emails that match nobody go to the "Unmatched emails" section.

The monitor's own briefs are skipped: the brief is emailed To the same inbox (everyone else is in BCC),
and it names many PAOs, so without this it would come back as an "email" item under each of them.
They are recognised by the X-PAO-Monitor header the sender adds, the brief's subject line (also when
someone forwards or replies to it), or being sent from the monitor's own address.
"""
import email
import imaplib
import os
import re
from datetime import timedelta
from email.header import decode_header, make_header
from email.utils import parseaddr, parsedate_to_datetime
from urllib.parse import quote

from bs4 import BeautifulSoup

from .common import Item, SourceResult, base_domain, clean, iso, log, make_id, now_utc, session

SOURCE = "email"
UNMATCHED_ID = "_unmatched_email"
MAX_MESSAGES = 300
FIRST_RUN_DAYS = 35
OWN_HEADER = "X-PAO-Monitor"
OWN_SUBJECT = re.compile(r"^\s*((re|fwd?|fw)\s*:\s*)*CAPA\b.*\b(intelligence brief|recap)\b", re.I)


def is_own_brief(msg, subject, sender, own_address=""):
    """The monitor's own brief coming back into its inbox (or a forward / reply of it)."""
    return bool(msg.get(OWN_HEADER) or OWN_SUBJECT.match(subject or "")
                or (own_address and sender.strip().lower() == own_address.strip().lower()))


def _decode(value):
    try:
        return str(make_header(decode_header(value or "")))
    except Exception:  # noqa: BLE001
        return value or ""


def body_text(msg):
    plain, html = [], []
    parts = msg.walk() if msg.is_multipart() else [msg]
    for part in parts:
        if part.get_content_maintype() == "multipart" or part.get("Content-Disposition", "").startswith("attachment"):
            continue
        ctype = part.get_content_type()
        if ctype not in ("text/plain", "text/html"):
            continue
        payload = part.get_payload(decode=True) or b""
        charset = part.get_content_charset() or "utf-8"
        try:
            text = payload.decode(charset, errors="replace")
        except LookupError:
            text = payload.decode("utf-8", errors="replace")
        (plain if ctype == "text/plain" else html).append(text)
    if plain:
        return "\n".join(plain)
    if html:
        return BeautifulSoup("\n".join(html), "lxml").get_text("\n")
    return ""


def _mentions(p, hay):
    n = hay.lower().count(p.name.lower()) if p.name and len(p.name) > 8 else 0
    if p.abbr and len(p.abbr) >= 3:
        n += len(re.findall(rf"(?<![A-Za-z]){re.escape(p.abbr)}(?![A-Za-z])", hay))
    return n


def match_paos(sender, subject, body, paos):
    domain = base_domain(sender.split("@")[-1]) if "@" in sender else ""
    by_domain = [p for p in paos if p.website and domain and base_domain(p.website) == domain]
    hay = f"{subject}\n{body[:20000]}"
    if by_domain:
        # Several PAOs can share one website (IASB and ISSB are both ifrs.org). One email must stay ONE item,
        # otherwise each copy is rated, edited and briefed separately: pick the one the email talks about most
        # (the first listed if it names none).
        if len(by_domain) > 1:
            by_domain = [max(by_domain, key=lambda p: _mentions(p, hay))]
        return by_domain
    hits = []
    for p in paos:
        if p.name and len(p.name) > 8 and p.name.lower() in hay.lower():
            hits.append(p)
        elif p.abbr and len(p.abbr) >= 4 and re.search(rf"(?<![A-Za-z]){re.escape(p.abbr)}(?![A-Za-z])", hay):
            hits.append(p)
    return hits


# Things in an email that are never "the story": unsubscribe / preferences / social / "view in browser" links
NOT_THE_STORY = re.compile(r"unsubscri|opt[-_ ]?out|preferences|manage (your )?(subscription|email|profile)|privacy|"
                           r"view (this )?(email )?(in|online)|in your browser|forward|contact us|facebook|twitter|"
                           r"linkedin|instagram|youtube|whatsapp|mailto:|\.(png|jpe?g|gif|svg)(\?|$)", re.I)
URL_RE = re.compile(r"https?://[^\s<>\"'\])]+")


def link_from_html(html):
    """The first real link in the email's HTML: has readable text and isn't a footer / social link."""
    for a in BeautifulSoup(html, "lxml").find_all("a", href=True):
        href, text = a["href"].strip(), clean(a.get_text())
        if href.startswith(("http://", "https://")) and len(text) >= 3 and not NOT_THE_STORY.search(href + " " + text):
            return href
    return ""


def link_from_text(text):
    """Same for a plain-text email, where links appear as 'Some words (https://...)'."""
    for m in URL_RE.finditer(text or ""):
        before = (text or "")[max(0, m.start() - 80):m.start()]
        url = m.group(0).rstrip(".,;:")
        if not NOT_THE_STORY.search(url + " " + before):
            return url
    return ""


def main_link(msg):
    """The link a reader would click: HTML anchors first, then the plain text."""
    html = []
    for part in (msg.walk() if msg.is_multipart() else [msg]):
        if part.get_content_type() == "text/html" and not part.get("Content-Disposition", "").startswith("attachment"):
            payload = part.get_payload(decode=True) or b""
            html.append(payload.decode(part.get_content_charset() or "utf-8", errors="replace"))
    return (link_from_html("\n".join(html)) if html else "") or link_from_text(body_text(msg))


class Resolver:
    """Newsletter links are tracking redirects (hubspotlinks.com, list-manage.com ...). Follow one to the page it
    leads to, so the item links straight to the real article. Falls back to the tracking link when that fails."""

    def __init__(self, limit=40):
        self.left, self.cache = limit, {}

    def __call__(self, url):
        if url in self.cache or self.left <= 0:
            return self.cache.get(url, url)
        self.left -= 1
        final = url
        try:
            r = session().get(url, timeout=8, stream=True, allow_redirects=True)
            if r.status_code < 400 and r.url and not NOT_THE_STORY.search(r.url):
                final = r.url
            r.close()
        except Exception as e:  # noqa: BLE001
            log.info("could not follow %s: %s", url[:80], e)
        self.cache[url] = final
        return final


def relink(store, resolve=None, limit=200):
    """Emails collected before links were read still point at Gmail: take the link from the saved text."""
    fixed = 0
    for row in store.email_items_to_relink(limit):
        link = link_from_text(row.get("content") or "")
        if link:
            store.set_item_url(row["id"], resolve(link) if resolve else link)
            fixed += 1
    return fixed


def parse_message(raw, paos, own_address="", resolve=None):
    msg = email.message_from_bytes(raw)
    subject = clean(_decode(msg.get("Subject"))) or "(no subject)"
    from_name, sender = parseaddr(_decode(msg.get("From")))
    if is_own_brief(msg, subject, sender, own_address):
        return []
    msgid = (msg.get("Message-ID") or "").strip()
    try:
        date = parsedate_to_datetime(msg.get("Date"))
    except Exception:  # noqa: BLE001
        date = None
    text = clean(body_text(msg))
    targets = match_paos(sender, subject, text, paos) or [None]
    # the link to the story itself; only if the email has none, a Gmail search (works for the inbox owner only)
    link = main_link(msg)
    if link and resolve:
        link = resolve(link)
    if not link and msgid:
        link = f"https://mail.google.com/mail/#search/rfc822msgid%3A{quote(msgid.strip('<>'))}"
    items = []
    for p in targets:
        pid = p.id if p else UNMATCHED_ID
        items.append(Item(
            id=make_id(pid, SOURCE, msgid or f"{sender}|{subject}|{date}"), pao_id=pid, source=SOURCE,
            title=subject, url=link, published_at=iso(date), snippet=text[:600],
            content=text[:20000], source_name=f"{from_name} <{sender}>".strip(),
            language=p.language if p else ""))
    return items


def collect(paos, since=None):
    """Returns one SourceResult per PAO that got mail, plus an overall status."""
    address = os.environ.get("GMAIL_ADDRESS", "").strip()
    password = os.environ.get("GMAIL_APP_PASSWORD", "").replace(" ", "").strip()
    overall = SourceResult("_inbox", SOURCE)
    if not address or not password:
        overall.skipped, overall.message = True, "GMAIL_ADDRESS / GMAIL_APP_PASSWORD not set"
        return overall, []
    since = since or (now_utc() - timedelta(days=FIRST_RUN_DAYS))
    since = since - timedelta(days=2)  # small overlap; duplicates are ignored
    items, skipped, resolver = [], 0, Resolver()
    try:
        imap = imaplib.IMAP4_SSL("imap.gmail.com", 993)
        imap.login(address, password)
        imap.select("INBOX", readonly=True)
        status, data = imap.search(None, "SINCE", since.strftime("%d-%b-%Y"))
        ids = data[0].split()[-MAX_MESSAGES:] if status == "OK" and data and data[0] else []
        for num in ids:
            status, parts = imap.fetch(num, "(BODY.PEEK[])")
            if status != "OK" or not parts or not isinstance(parts[0], tuple):
                continue
            try:
                got = parse_message(parts[0][1], paos, own_address=address, resolve=resolver)
                skipped += not got
                items += got
            except Exception as e:  # noqa: BLE001
                log.info("email %s parse failed: %s", num, e)
        imap.logout()
        overall.message = f"Read {len(ids)} email(s) since {since.date()}" + (f"; skipped {skipped} of the monitor's own brief(s)" if skipped else "")
    except imaplib.IMAP4.error as e:
        overall.ok = False
        overall.message = f"Gmail login/read failed: {clean(str(e), 200)} (check the app password)"
    except Exception as e:  # noqa: BLE001
        overall.ok = False
        overall.message = f"{type(e).__name__}: {clean(str(e), 200)}"
    return overall, items
