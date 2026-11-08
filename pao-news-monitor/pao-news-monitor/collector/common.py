"""Shared helpers: the PAO list, web requests, IDs, dates."""
import csv
import hashlib
import logging
import re
import warnings
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

import requests

log = logging.getLogger("collector")

ROOT = Path(__file__).resolve().parent.parent
PAO_FILE = ROOT / "config" / "paos.csv"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"
)
BROWSER_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Upgrade-Insecure-Requests": "1",
}
TIMEOUT = 25


@dataclass
class PAO:
    id: str
    group: str
    jurisdiction: str
    name: str
    abbr: str
    website: str = ""
    news_url: str = ""
    feed_url: str = ""
    search_terms: str = ""
    news_locale: str = "en-US"
    link_selector: str = ""
    active: str = "yes"
    notes: str = ""
    facebook: str = ""          # shown as a manual-check button (Facebook isn't scraped)
    leadership_url: str = ""    # page(s) listing the President / CEO; found automatically if blank
    contact_url: str = ""       # contact / address page; found automatically if blank
    extra: dict = field(default_factory=dict)

    @property
    def is_active(self):
        return self.active.strip().lower() not in ("no", "n", "false", "0")

    @property
    def language(self):
        return (self.news_locale or "en").split("-")[0].lower()

    def split(self, value):
        return [v.strip() for v in (value or "").split("|") if v.strip()]


def load_paos(path=PAO_FILE):
    paos = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            row = {k.strip(): (v or "").strip() for k, v in row.items() if k}
            if not row.get("id"):
                continue
            known = {k: row.pop(k) for k in list(row) if k in PAO.__dataclass_fields__ and k != "extra"}
            paos.append(PAO(**known, extra=row))
    ids = [p.id for p in paos]
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    if dupes:
        raise ValueError(f"Duplicate ids in paos.csv: {dupes}")
    return paos


# ---------- web requests ----------

_session = None


def session():
    global _session
    if _session is None:
        s = requests.Session()
        s.headers.update(BROWSER_HEADERS)
        _session = s
    return _session


class FetchResult:
    def __init__(self, resp, insecure=False):
        self.resp = resp
        self.insecure = insecure
        self.url = resp.url
        self.status = resp.status_code
        self.content = resp.content

    @property
    def text(self):
        r = self.resp
        if not r.encoding or r.encoding.lower() == "iso-8859-1":
            r.encoding = r.apparent_encoding
        return r.text


def _get(url, **kw):
    """GET a URL. If the site's security certificate is broken (common on
    small sites) retry without checking it - we only read public pages."""
    try:
        return FetchResult(session().get(url, timeout=kw.pop("timeout", TIMEOUT), **kw))
    except requests.exceptions.SSLError:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            return FetchResult(session().get(url, timeout=TIMEOUT, verify=False, **kw), insecure=True)


def fetch(url, **kw):
    """Like _get, but for old http:// addresses try https:// first -
    many sites no longer answer on plain http."""
    if url.startswith("http://"):
        try:
            r = _get("https://" + url[7:], timeout=15, **kw)
            if r.status < 400:
                return r
        except requests.exceptions.RequestException:
            pass
    return _get(url, **kw)


# ---------- ids, urls, dates ----------

_TRACKING = re.compile(r"^(utm_|fbclid|gclid|mc_|_ga)", re.I)


def normalize_url(url):
    p = urlsplit(url.strip())
    query = urlencode([(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True) if not _TRACKING.match(k)])
    path = p.path.rstrip("/") or "/"
    return urlunsplit((p.scheme.lower(), p.netloc.lower().removeprefix("www."), path, query, ""))


def make_id(*parts):
    return hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()[:24]


def base_domain(url_or_host):
    host = urlsplit(url_or_host).netloc if "//" in url_or_host else url_or_host
    host = host.lower().split(":")[0].removeprefix("www.")
    if re.fullmatch(r"[\d.]+", host):  # bare IP address
        return host
    parts = host.split(".")
    # keep 3 labels for things like icmab.gov.bd / sia.org.ws / cpaaustralia.com.au
    if len(parts) >= 3 and len(parts[-1]) == 2 and parts[-2] in ("com", "org", "gov", "edu", "net", "or", "co", "ac"):
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


def now_utc():
    return datetime.now(timezone.utc)


def iso(dt):
    return dt.astimezone(timezone.utc).isoformat() if dt else None


_DATE_PATTERNS = [
    (re.compile(r"\b(20\d\d)[-/.](\d{1,2})[-/.](\d{1,2})\b"), ("y", "m", "d")),
    (re.compile(r"\b(\d{1,2})[-/.](\d{1,2})[-/.](20\d\d)\b"), ("d", "m", "y")),
    (re.compile(r"(20\d\d)年(\d{1,2})月(\d{1,2})日"), ("y", "m", "d")),
    (re.compile(r"(20\d\d)\.\s?(\d{1,2})\.\s?(\d{1,2})"), ("y", "m", "d")),
]
_MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}
_TEXT_DATE = re.compile(
    r"\b(\d{1,2})(?:st|nd|rd|th)?\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?,?\s+(20\d\d)\b"
    r"|\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(20\d\d)\b",
    re.I)


def guess_date(text):
    """Find a date like 2026-07-28, 28/07/2026, 28 July 2026 or 2026年7月28日."""
    if not text:
        return None
    m = _TEXT_DATE.search(text)
    if m:
        if m.group(1):
            d, mon, y = int(m.group(1)), _MONTHS[m.group(2).lower()[:3]], int(m.group(3))
        else:
            mon, d, y = _MONTHS[m.group(4).lower()[:3]], int(m.group(5)), int(m.group(6))
        try:
            return datetime(y, mon, d, tzinfo=timezone.utc)
        except ValueError:
            pass
    for rx, order in _DATE_PATTERNS:
        m = rx.search(text)
        if m:
            vals = dict(zip(order, map(int, m.groups())))
            try:
                dt = datetime(vals["y"], vals["m"], vals["d"], tzinfo=timezone.utc)
            except ValueError:
                continue
            if dt <= now_utc():
                return dt
    return None


def clean(text, limit=None):
    text = re.sub(r"\s+", " ", text or "").strip()
    return text[:limit] if limit else text


@dataclass
class Item:
    id: str
    pao_id: str
    source: str            # website | google_news | newsapi | email
    title: str
    url: str = ""
    published_at: str = None
    snippet: str = ""
    content: str = ""
    source_name: str = ""
    language: str = ""
    is_baseline: bool = False
    kind: str = "news"     # news | events | publications | leadership | contact
    found_on: str = ""     # listing page the link was found on (not saved)
    via: str = ""          # "pattern" if a website link was picked up only by page-pattern matching (not saved)

    NOT_SAVED = ("found_on", "via")

    def row(self):
        return {k: getattr(self, k) for k in self.__dataclass_fields__ if k not in self.NOT_SAVED}


@dataclass
class SourceResult:
    """What one source found for one PAO, plus whether it worked."""
    pao_id: str
    source: str
    items: list = field(default_factory=list)
    ok: bool = True
    message: str = ""
    skipped: bool = False
    needs_browser: bool = False   # website blocked us or needs JavaScript: retry in a real browser
    pages: list = field(default_factory=list)  # watched_pages rows to save (listing pages, page-watch snapshots)
