"""Source 1: each PAO's own website.

No per-site code. For each site, in order:
  1. use feed_url from paos.csv if set (RSS/Atom feed),
  2. otherwise look for a feed advertised on the homepage,
  3. otherwise read the news page(s) - news_url from paos.csv, or pages found
     automatically from homepage links like "News", "Press", "公告", "お知らせ" -
     and collect every article-looking link on them.

Besides news pages, each site's Publications and Events pages are scanned
too, and every item is labelled news / events / publications (from the page it
was found on, refined by its address, e.g. /event/ or .pdf).

Every link not seen before becomes an item. Nothing is filtered by topic:
your team decides what matters in the web page.

news_url can list pages of any type; start one with a type to label it, e.g.
    https://x.org/news|publications>https://x.org/library|events>https://x.org/cpd

If a site's results are too noisy, put a CSS selector in the link_selector
column of paos.csv (e.g. ".news-list a") and only those links are used.
"""
import re
from datetime import datetime, timezone
from urllib.parse import urljoin, urlsplit

import feedparser
from bs4 import BeautifulSoup

from .common import (Item, SourceResult, base_domain, clean, fetch, guess_date, iso,
                     log, make_id, normalize_url)

SOURCE = "website"

# Words that mark a link to a news / announcements section (many languages).
NEWS_WORDS = [
    "news", "press", "media", "announcement", "notice", "circular", "update", "latest",
    "bulletin", "newsroom", "release", "whats-new", "what's new",
    "新闻", "新聞", "公告", "通知", "动态", "動態", "资讯", "資訊", "最新",
    "お知らせ", "ニュース", "新着", "뉴스", "공지", "소식", "알림",
    "tin tức", "tin-tuc", "thông báo", "thong-bao",
    "actualité", "actualite", "communiqué", "communique", "presse",
    "мэдээ", "समाचार", "सूचना",
]
_NEWS_RX = re.compile("|".join(re.escape(w) for w in NEWS_WORDS), re.I)

PUBLICATION_WORDS = [
    "publication", "journal", "magazine", "e-book", "ebook", "resources", "library",
    "research", "reports",
    "刊物", "出版", "期刊", "杂志", "雜誌", "会刊", "會刊", "刊行物", "出版物", "간행물", "발간", "출판",
    "ấn phẩm", "an-pham", "tạp chí", "tap-chi", "publications", "revue", "प्रकाशन", "पत्रिका",
]
EVENT_WORDS = [
    "event", "seminar", "webinar", "conference", "calendar", "workshop", "forum", "cpd", "cpe",
    "summit", "congress",
    "活动", "活動", "研讨会", "研討會", "讲座", "講座", "イベント", "セミナー", "研修", "행사", "세미나", "교육",
    "sự kiện", "su-kien", "hội thảo", "hoi-thao", "événement", "evenement", "congrès", "कार्यक्रम",
]
ARTICLE_WORDS = [
    "newsletter", "e-newsletter", "enewsletter", "article", "blog", "insights", "thought leadership", "opinion",
    "column", "perspectives", "viewpoint", "feature", "bulletin board",
    "通讯", "通訊", "简报", "簡報", "专栏", "專欄", "文章", "コラム", "ニュースレター", "칼럼", "뉴스레터", "bản tin", "ban-tin",
]
_PUB_RX = re.compile("|".join(re.escape(w) for w in PUBLICATION_WORDS), re.I)
_ARTICLE_RX = re.compile("|".join(re.escape(w) for w in ARTICLE_WORDS), re.I)
_EVENT_RX = re.compile("|".join(re.escape(w) for w in EVENT_WORDS), re.I)
# item addresses that clearly say what they are
_ITEM_EVENT_RX = re.compile(r"/(events?|seminars?|webinars?|conferences?|workshops?|cpd|cpe)(/|-|_|\b)", re.I)
_ITEM_PUB_RX = re.compile(r"/(publications?|journals?|magazines?|reports?|library|resources)(/|-|_|\b)|\.pdf($|\?)", re.I)
_ITEM_ARTICLE_RX = re.compile(r"/(newsletters?|e-?newsletters?|articles?|blogs?|insights?|opinions?|columns?)(/|-|_|\b)", re.I)
KINDS = ("news", "publications", "events", "articles")
MAX_PAGES = {"news": 3, "publications": 2, "events": 2, "articles": 2}


def page_kind(text, path=""):
    """What kind of listing a menu link points to (None if not a listing)."""
    for hay in (text, path):
        if not hay:
            continue
        art = _ARTICLE_RX.search(hay)
        rest = _ARTICLE_RX.sub(" ", hay)          # "newsletter" must not count as "news"
        pub, ev, news = _PUB_RX.search(rest), _EVENT_RX.search(rest), _NEWS_RX.search(rest)
        if art and not news:
            return "articles"
        if pub and not news:
            return "publications"
        if ev and not news:
            return "events"
        if news:
            return "news"
    return None


def item_kind(url, page_kind_):
    """Refine an item's kind from its own address."""
    path = urlsplit(url).path
    if _ITEM_EVENT_RX.search(path):
        return "events"
    if _ITEM_ARTICLE_RX.search(path):
        return "articles"
    if _ITEM_PUB_RX.search(url):
        return "publications"
    return page_kind_ or "news"


def parse_page_spec(spec):
    """'events>https://...' -> ('events', url); plain url -> ('news', url)."""
    head, sep, rest = spec.partition(">")
    if sep and head.strip().lower() in KINDS and "//" not in head:
        return head.strip().lower(), rest.strip()
    return "news", spec.strip()

# Links that are never news.
SKIP_RX = re.compile(
    r"login|log-in|signin|sign-in|register|cart|checkout|password|privacy|cookie|terms|"
    r"sitemap|contact|about-us|career|jobs|search|facebook\.com|twitter\.com|x\.com|"
    r"linkedin\.com|youtube\.com|instagram\.com|whatsapp|wa\.me|tel:|mailto:|javascript:",
    re.I)
SKIP_EXT = re.compile(r"\.(jpg|jpeg|png|gif|svg|webp|css|js|ico|zip|mp4|mp3)(\?|$)", re.I)
ARTICLE_HINT = re.compile(r"(20\d\d|/\d{3,}|news|press|media|notice|circular|announce|article|post|detail|view|\.pdf)", re.I)

MAX_LINKS_PER_PAGE = 80
MAX_NEWS_PAGES = 3
_CJK = re.compile(r"[぀-ヿ㐀-鿿가-힯]")


def _title_ok(text, relaxed=False):
    if not text:
        return False
    if _CJK.search(text):
        return len(text) >= (6 if relaxed else 5)
    if relaxed:  # no URL hint to lean on, so ask for a more headline-like title
        return len(text) >= 25 and len(text.split()) >= 4
    return len(text) >= 18 and len(text.split()) >= 3


def _same_site(url, site_domain):
    host = (urlsplit(url).hostname or "").lower()
    return bool(host) and (host.removeprefix("www.") == site_domain or host.endswith("." + site_domain))


def parse_feed(content, pao, base_url):
    feed = feedparser.parse(content)
    items = []
    for e in feed.entries[:100]:
        link = e.get("link") or ""
        title = clean(e.get("title"))
        if not link or not title:
            continue
        link = urljoin(base_url, link)
        published = None
        for key in ("published_parsed", "updated_parsed"):
            if e.get(key):
                published = datetime(*e[key][:6], tzinfo=timezone.utc)
                break
        summary = clean(BeautifulSoup(e.get("summary", ""), "lxml").get_text(" "), 500) if e.get("summary") else ""
        items.append(Item(id=make_id(pao.id, SOURCE, normalize_url(link)), pao_id=pao.id, source=SOURCE,
                          title=title, url=link, published_at=iso(published), snippet=summary,
                          source_name="Website feed", language=pao.language,
                          kind=item_kind(link, "news"), found_on=base_url))
    return items


def find_feed_links(soup, base_url):
    out = []
    for link in soup.find_all("link", rel=lambda v: v and "alternate" in v):
        t = (link.get("type") or "").lower()
        if ("rss" in t or "atom" in t) and link.get("href"):
            out.append(urljoin(base_url, link["href"]))
    return out


def find_listing_pages(soup, base_url, site_domain):
    """Menu links to news, publications and events pages: {kind: [url, ...]}."""
    found = {k: [] for k in KINDS}
    seen = {normalize_url(base_url)}
    for a in soup.find_all("a", href=True):
        href = urljoin(base_url, a["href"])
        text = clean(a.get_text(" "))
        if not _same_site(href, site_domain) or SKIP_RX.search(href) or SKIP_EXT.search(href):
            continue
        if len(text) > 40:
            continue
        kind = page_kind(text, urlsplit(href).path)
        n = normalize_url(href)
        if kind and n not in seen:
            seen.add(n)
            found[kind].append(href)
    prefer = {"news": r"news|press|media|公告|お知らせ|뉴스", "publications": r"publication|journal|magazine",
              "articles": r"newsletter|article|insight|blog",
              "events": r"event|seminar|webinar"}
    for kind, urls in found.items():
        urls.sort(key=lambda u: (0 if re.search(prefer[kind], u, re.I) else 1, len(u)))
        del urls[MAX_PAGES[kind]:]
    return found


def find_news_pages(soup, base_url, site_domain):
    """News pages only (kept for older callers)."""
    return find_listing_pages(soup, base_url, site_domain)["news"]


PATTERN_MIN_LINKS = 3        # a repeated block needs at least this many different article links
PATTERN_HEADLINE_SHARE = 0.6  # ...and most of its link texts must look like headlines
_TIME_ATTR = re.compile(r"(20\d\d)-(\d{1,2})-(\d{1,2})")


def _signature(a):
    """Where a link sits in the page: its own tag/classes plus three levels of parents.
    Links in the same repeated list (news cards, rows of a table) share a signature."""
    parts, node = [], a
    for _ in range(4):
        if node is None or node.name in (None, "body", "html", "[document]"):
            break
        classes = sorted(c for c in (node.get("class") or []) if not re.search(r"\d", c))
        parts.append(node.name + ("." + ".".join(classes) if classes else ""))
        node = node.parent
    return "/".join(parts)


def _headline_like(title):
    if _CJK.search(title):
        return len(title) >= 6
    return len(title) >= 20 and len(title.split()) >= 3


def _article_like_url(url):
    """Deeper than a menu link: /section/item, a long slug, or a PDF."""
    path = urlsplit(url).path.rstrip("/")
    segments = [s for s in path.split("/") if s]
    return path.lower().endswith(".pdf") or len(segments) >= 2 or (segments and len(segments[-1]) >= 15)


def pattern_links(soup, page_url, site_domain):
    """Adaptive matching: find the page's repeated list of articles by its structure,
    so links count even when their address has no news-like hint (e.g. /stories/new-cpd-rules).
    Works on whatever layout the page has today, so a redesign doesn't need new settings.
    Returns the normalised addresses of links in those lists."""
    groups = {}
    page_key = normalize_url(page_url)
    for a in soup.find_all("a", href=True):
        url = urljoin(page_url, a["href"])
        if not url.startswith("http") or SKIP_RX.search(url) or SKIP_EXT.search(url):
            continue
        if not (_same_site(url, site_domain) or url.lower().split("?")[0].endswith(".pdf")):
            continue
        key = normalize_url(url)
        if key == page_key:
            continue
        title = clean(a.get_text(" ")) or clean(a.get("title"))
        groups.setdefault(_signature(a), {}).setdefault(key, (url, title))
    keep = set()
    for links in groups.values():
        if len(links) < PATTERN_MIN_LINKS:
            continue
        values = list(links.values())
        headlines = sum(1 for _, t in values if t and _headline_like(t))
        deep = sum(1 for u, _ in values if _article_like_url(u))
        if headlines / len(values) >= PATTERN_HEADLINE_SHARE and deep / len(values) >= PATTERN_HEADLINE_SHARE:
            keep.update(links)
    return keep


def _link_date(a, url):
    """Date for a link: a <time> tag in its own list item/card first, then any date text nearby, then the address."""
    ctx = a.find_parent(["li", "tr", "article", "div"]) or a
    times = ctx.find_all("time") if hasattr(ctx, "find_all") else []
    if len(times) == 1:  # only trust it if it clearly belongs to this one item
        m = _TIME_ATTR.search(times[0].get("datetime") or "")
        if m:
            try:
                return datetime(*map(int, m.groups()), tzinfo=timezone.utc)
            except ValueError:
                pass
        d = guess_date(clean(times[0].get_text(" ")))
        if d:
            return d
    return guess_date(clean(ctx.get_text(" "), 400)) or guess_date(url)


def extract_links(html, page_url, pao, site_domain, selector="", relaxed=False, kind="news"):
    """Collect article-looking links. Strict mode wants a news-like URL
    (dates, ids, 'news', .pdf...) or a link in the page's repeated article list
    (pattern matching). Relaxed mode drops both and relies on headline-like link
    text instead - used when strict finds almost nothing."""
    soup = BeautifulSoup(html, "lxml")
    for bad in soup(["script", "style", "noscript", "header", "footer", "nav"]):
        if not selector:
            bad.decompose()
    anchors = soup.select(selector) if selector else soup.find_all("a", href=True)
    in_pattern = pattern_links(soup, page_url, site_domain) if not selector and not relaxed else set()
    items, seen = [], set()
    for a in anchors:
        if a.name != "a":
            a = a.find("a", href=True) or a
        href = a.get("href")
        if not href:
            continue
        url = urljoin(page_url, href)
        if not url.startswith("http") or SKIP_RX.search(url) or SKIP_EXT.search(url):
            continue
        is_pdf = url.lower().split("?")[0].endswith(".pdf")
        if not (_same_site(url, site_domain) or is_pdf):
            continue
        title = clean(a.get_text(" ")) or clean(a.get("title"))
        if not selector and not _title_ok(title, relaxed):
            continue
        key = normalize_url(url)
        via = ""
        if not selector and not relaxed and not ARTICLE_HINT.search(url) and not _CJK.search(title):
            if key not in in_pattern:
                continue
            via = "pattern"
        if key in seen or key == normalize_url(page_url):
            continue
        seen.add(key)
        date = _link_date(a, url)
        items.append(Item(id=make_id(pao.id, SOURCE, key), pao_id=pao.id, source=SOURCE,
                          title=title[:300] or url, url=url, published_at=iso(date),
                          source_name=urlsplit(page_url).netloc, language=pao.language,
                          kind=item_kind(url, kind), found_on=page_url, via=via))
        if len(items) >= MAX_LINKS_PER_PAGE:
            break
    return items


BLOCKED_STATUSES = {401, 403, 406, 429, 503}
MIN_STRICT_LINKS = 3


def collect(pao, fetcher=None, browser_mode=False):
    """fetcher: how pages are downloaded - plain requests by default, or a
    real browser (browser.py) for sites that block bots or need JavaScript."""
    fetcher = fetcher or fetch
    res = SourceResult(pao.id, SOURCE)
    if not pao.website and not pao.news_url and not pao.feed_url:
        res.skipped, res.message = True, "No website listed"
        return res
    notes = []
    found = {}          # item id -> Item
    have_feed = False
    try:
        # 1. explicit feed (covers the news; publications/events pages are still scanned below)
        if not browser_mode:
            for feed_url in pao.split(pao.feed_url):
                r = fetch(feed_url)
                for it in parse_feed(r.content, pao, r.url):
                    found.setdefault(it.id, it)
            if found:
                have_feed = True
                notes.append(f"Feed: {len(found)} entries")

        explicit = [parse_page_spec(x) for x in pao.split(pao.news_url)]
        home_url = pao.website or (explicit[0][1] if explicit else "")
        try:
            home = fetcher(home_url)
        except Exception as e:  # noqa: BLE001  (timeouts, refused connections)
            if have_feed:
                res.items = list(found.values())
                res.message = "; ".join(notes + [f"homepage not reachable ({type(e).__name__}), publications/events not checked"])
                return res
            res.ok, res.needs_browser = False, not browser_mode
            res.message = f"Website not reachable ({type(e).__name__}): {clean(str(e), 150)}"
            return res
        if home.status >= 400:
            if have_feed:
                res.items = list(found.values())
                res.message = "; ".join(notes + [f"homepage error {home.status}, publications/events not checked"])
                return res
            res.ok = False
            res.needs_browser = not browser_mode and (home.status in BLOCKED_STATUSES)
            res.message = (f"Blocks crawlers (error {home.status})" if home.status in BLOCKED_STATUSES
                           else f"Website returned error {home.status}")
            return res
        if home.insecure:
            notes.append("site's security certificate is broken (read anyway)")
        if base_domain(home.url) != base_domain(home_url):
            notes.append(f"website now redirects to {urlsplit(home.url).netloc} - update the website column")
        site_domain = base_domain(home.url)
        soup = BeautifulSoup(home.text, "lxml")
        visible_text = len(clean(soup.get_text(" ")))

        # 2. advertised feed
        if not have_feed and not pao.link_selector and not browser_mode:
            for feed_url in find_feed_links(soup, home.url)[:2]:
                try:
                    r = fetch(feed_url)
                    got = parse_feed(r.content, pao, r.url)
                except Exception as e:  # noqa: BLE001
                    log.info("%s feed %s failed: %s", pao.id, feed_url, e)
                    continue
                if got:
                    for it in got:
                        found.setdefault(it.id, it)
                    have_feed = True
                    notes.insert(0, f"Feed found automatically: {feed_url}")
                    break

        # 3. listing pages: news (unless a feed covers it), publications, events
        discovered = find_listing_pages(soup, home.url, site_domain)
        explicit_kinds = {k for k, _ in explicit}
        pages = list(explicit)
        for kind in KINDS:
            if kind in explicit_kinds or (kind == "news" and (have_feed or explicit)):
                continue
            pages += [(kind, u) for u in discovered[kind]]
        fetched = []  # (url, html, kind)
        for kind, page_url in pages:
            try:
                r = fetcher(page_url)
                if r.status >= 400:
                    # a page we guessed can be a dead menu link - only flag pages you set yourself
                    notes.append(f"{kind} page error {r.status}: {page_url}" if (kind, page_url) in explicit
                                 else f"skipped a dead link ({r.status})")
                    continue
                fetched.append((r.url, r.text, kind))
            except Exception as e:  # noqa: BLE001
                notes.append(f"{kind} page failed ({type(e).__name__}): {page_url}")
        if not have_feed:
            fetched.append((home.url, home.text, "news"))  # homepage itself often lists the latest news

        def gather(relaxed):
            out = {}
            for url, html, kind in fetched:
                for it in extract_links(html, url, pao, site_domain, pao.link_selector, relaxed, kind):
                    if it.id not in out or (out[it.id].via == "pattern" and not it.via):
                        out[it.id] = it   # prefer the copy found the ordinary way
            return out

        strict = gather(relaxed=False)
        if len(strict) < MIN_STRICT_LINKS and not pao.link_selector and not have_feed:
            loose = gather(relaxed=True)
            if len(loose) > len(strict):
                notes.append("used loose link matching (review for junk links)")
                strict = {**loose, **strict}
        for k, it in strict.items():
            found.setdefault(k, it)
        res.items = list(found.values())
        res.pages = [{"pao_id": pao.id, "url": url, "kind": "listing:" + kind} for url, _, kind in fetched]
        # remember which pages pattern matching has already read, so its first finds there are
        # saved as "first scan" (old articles) rather than shown as new - see main.apply_baseline
        by_pattern = [it for it in res.items if it.via == "pattern"]
        kind_of_page = {url: kind for url, _, kind in fetched}
        res.pages += [{"pao_id": pao.id, "url": u, "kind": "pattern:" + kind_of_page.get(u, "news")}
                      for u in sorted({it.found_on for it in by_pattern})]
        if by_pattern:
            notes.append(f"{len(by_pattern)} link(s) found by page-pattern matching")

        if not res.items:
            if visible_text < 800:
                notes.append("page is nearly empty - the site needs JavaScript")
            elif browser_mode:
                notes.append("no article links found even in a real browser - set news_url (or link_selector) in paos.csv")
            else:
                notes.append("no article links found - set news_url (or link_selector) in paos.csv")
            res.needs_browser = not browser_mode
        counts = {k: sum(1 for _, _, kk in fetched if kk == k) for k in KINDS}
        if not have_feed:
            counts["news"] -= 1  # the homepage
        scanned = ", ".join(f"{n} {k}" for k, n in counts.items() if n)
        pages_note = (f"Scanned {scanned} page(s)" + ("" if have_feed else " + homepage")) if scanned \
            else ("Scanned homepage only (no news page found)" if not have_feed else "")
        res.message = "; ".join(x for x in [pages_note] + notes if x)
    except Exception as e:  # noqa: BLE001
        res.ok = False
        res.message = f"{type(e).__name__}: {clean(str(e), 200)}"
    return res
