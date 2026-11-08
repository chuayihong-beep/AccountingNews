"""Offline tests: fake websites, feeds and emails. Run with:  python -m pytest -q"""
import json
from email.message import EmailMessage

import pytest

from collector import common, email_inbox, main, news_search, websites
from collector.common import PAO, guess_date, base_domain, load_paos

HOME = """<html><head><title>ICAI</title></head><body>
<nav><a href="/login">Member Login</a><a href="/news">News &amp; Updates</a><a href="/about-us">About</a></nav>
<div class="latest"><ul>
 <li><a href="/post/new-president-elected-2026">CA Ranjeet Kumar elected President for 2026-27 term</a> <span>12 Feb 2026</span></li>
 <li><a href="https://www.facebook.com/icai">Follow us on Facebook today please</a></li>
</ul></div></body></html>"""

NEWS = """<html><body><h1>News</h1><ul>
 <li><a href="/post/announcement-cpd-hours-2026">Announcement regarding CPD hours for the year 2026</a> 03/03/2026</li>
 <li><a href="/post/new-president-elected-2026?utm_source=x">CA Ranjeet Kumar elected President for 2026-27 term</a></li>
 <li><a href="/docs/circular-12.pdf">Circular No. 12 on revised audit standards for members</a> 2026-03-10</li>
 <li><a href="/contact">Contact the institute secretariat office now</a></li>
</ul></body></html>"""

JP_NEWS = """<html><body><ul>
 <li><a href="/news/2026/0301.html">新会長の就任について</a><span>2026年3月1日</span></li>
 <li><a href="/news/2026/0215.html">お知らせ</a></li>
</ul></body></html>"""

GOOGLE_RSS = """<?xml version="1.0"?><rss version="2.0"><channel><title>x</title>
<item><title>ICAI announces new president - The Hindu</title><link>https://news.google.com/rss/articles/abc</link>
<guid>abc</guid><pubDate>Tue, 10 Mar 2026 08:00:00 GMT</pubDate><source url="https://thehindu.com">The Hindu</source></item>
<item><title>ICAI exam dates out - Mint</title><link>https://news.google.com/rss/articles/def</link>
<guid>def</guid><pubDate>Wed, 11 Mar 2026 08:00:00 GMT</pubDate><source url="https://livemint.com">Mint</source></item>
</channel></rss>"""

RSS_FEED = """<?xml version="1.0"?><rss version="2.0"><channel><title>Feed</title>
<item><title>PICPA welcomes new national president</title><link>https://picpa.com.ph/news/1</link>
<pubDate>Mon, 28 Jul 2026 00:00:00 GMT</pubDate><description>&lt;p&gt;Hello&lt;/p&gt;</description></item>
</channel></rss>"""


class FakeResp:
    def __init__(self, url, body, status=200):
        self.url, self.status_code = url, status
        self.content = body.encode("utf-8")
        self.encoding = "utf-8"
        self.apparent_encoding = "utf-8"
        self.text = body


def fake_fetch(pages):
    def _fetch(url, **kw):
        for key, body in pages.items():
            if url.startswith(key):
                return common.FetchResult(FakeResp(url, body))
        return common.FetchResult(FakeResp(url, "not found", 404))
    return _fetch


def pao(**kw):
    base = dict(id="icai", group="Member", jurisdiction="India", name="Institute of Chartered Accountants of India",
                abbr="ICAI", website="https://www.icai.org", search_terms='"Institute of Chartered Accountants of India"',
                news_locale="en-IN")
    base.update(kw)
    return PAO(**base)


def test_pao_file_loads():
    paos = load_paos()
    assert len(paos) >= 50
    ids = {p.id for p in paos}
    assert {"icai", "picpa", "jicpa", "acca", "icaew", "ifac"} <= ids
    acca = next(p for p in paos if p.id == "acca")
    assert acca.abbr == "ACCA" and acca.name.startswith("Association")


def test_dates():
    assert guess_date("12 Feb 2026").day == 12
    assert guess_date("March 3, 2026").month == 3
    assert guess_date("2026年3月1日").month == 3
    assert guess_date("posted 03/03/2026").year == 2026
    assert guess_date("nothing here") is None


def test_base_domain():
    assert base_domain("https://www.icmab.gov.bd/x") == "icmab.gov.bd"
    assert base_domain("http://www.cpaaustralia.com.au") == "cpaaustralia.com.au"
    assert base_domain("mail.icai.org") == "icai.org"


def test_website_news_page(monkeypatch):
    monkeypatch.setattr(websites, "fetch", fake_fetch({"https://www.icai.org/news": NEWS, "https://www.icai.org": HOME}))
    res = websites.collect(pao())
    titles = {i.title for i in res.items}
    assert res.ok
    assert "Announcement regarding CPD hours for the year 2026" in titles
    assert "Circular No. 12 on revised audit standards for members" in titles
    assert not any("Facebook" in t or "Contact" in t or "Login" in t for t in titles)
    # same article on homepage and news page (one with utm tag) -> one item
    assert sum("Ranjeet" in t for t in titles) == 1
    pdf = next(i for i in res.items if i.url.endswith(".pdf"))
    assert pdf.published_at.startswith("2026-03-10")


def test_website_selector_and_cjk(monkeypatch):
    p = pao(id="jicpa", website="https://jicpa.or.jp", news_url="https://jicpa.or.jp/news/", news_locale="ja-JP")
    monkeypatch.setattr(websites, "fetch", fake_fetch({"https://jicpa.or.jp/news/": JP_NEWS, "https://jicpa.or.jp": "<html></html>"}))
    res = websites.collect(p)
    assert [i.title for i in res.items] == ["新会長の就任について"]
    assert res.items[0].language == "ja" and res.items[0].published_at.startswith("2026-03-01")


def test_website_feed(monkeypatch):
    p = pao(id="picpa", website="https://picpa.com.ph", feed_url="https://picpa.com.ph/feed")
    monkeypatch.setattr(websites, "fetch", fake_fetch({"https://picpa.com.ph/feed": RSS_FEED}))
    res = websites.collect(p)
    assert len(res.items) == 1 and res.items[0].snippet == "Hello"


def test_website_down(monkeypatch):
    monkeypatch.setattr(websites, "fetch", fake_fetch({}))
    res = websites.collect(pao())
    assert not res.ok and "404" in res.message


def test_google_news(monkeypatch):
    assert news_search.google_params("zh-HK") == ("zh-HK", "HK", "HK:zh-Hant")
    assert news_search.google_params("en-IN") == ("en-IN", "IN", "IN:en")
    assert news_search.google_params("ja-JP") == ("ja", "JP", "JP:ja")
    assert news_search.parse_term('zh-HK>香港會計師公會', "en-HK") == ("zh-HK", "香港會計師公會")
    assert news_search.parse_term('"A>B" thing', "en-US") == ("en-US", '"A>B" thing')
    monkeypatch.setattr(news_search, "fetch", fake_fetch({"https://news.google.com": GOOGLE_RSS}))
    res = news_search.collect_google(pao(search_terms='"ICAI" president|"Institute of Chartered Accountants of India"'))
    assert res.ok and len(res.items) == 2  # same articles from 2 searches -> deduped
    assert res.items[0].title == "ICAI announces new president" and res.items[0].source_name == "The Hindu"


def test_newsapi_budget_and_errors(monkeypatch):
    calls = []

    class S:
        def get(self, url, **kw):
            calls.append(kw["params"]["q"])
            body = {"status": "ok", "articles": [{"url": "https://x.com/a", "title": "ICAI news", "source": {"name": "X"},
                                                  "publishedAt": "2026-03-01T00:00:00Z", "description": "d"}]}
            return type("R", (), {"json": lambda self: body})()
    monkeypatch.setattr(news_search, "session", lambda: S())
    api = news_search.NewsAPI(key="k")
    res = api.collect(pao(search_terms='zh-HK>中文|"Institute of Chartered Accountants of India"'))
    assert calls == ['"Institute of Chartered Accountants of India"'] and len(res.items) == 1
    assert news_search.NewsAPI(key="").collect(pao()).skipped


def make_email(sender, subject, body):
    m = EmailMessage()
    m["From"], m["Subject"], m["Message-ID"] = sender, subject, "<abc123@mail.example>"
    m["Date"] = "Tue, 28 Jul 2026 10:00:00 +0800"
    m.set_content(body)
    return m.as_bytes()


def test_email_matching():
    paos = [pao(), pao(id="picpa", name="Philippine Institute of Certified Public Accountants", abbr="PICPA",
                        website="https://picpa.com.ph")]
    by_domain = email_inbox.parse_message(make_email("Comms <press@picpa.com.ph>", "Press release", "New president"), paos)
    assert [i.pao_id for i in by_domain] == ["picpa"]
    by_name = email_inbox.parse_message(make_email("x@gmail.com", "Update", "The PICPA board met today"), paos)
    assert [i.pao_id for i in by_name] == ["picpa"]
    nobody = email_inbox.parse_message(make_email("x@gmail.com", "Hello", "nothing relevant"), paos)
    assert [i.pao_id for i in nobody] == [email_inbox.UNMATCHED_ID]
    assert "rfc822msgid" in nobody[0].url and nobody[0].published_at.startswith("2026-07-28")


def test_email_without_credentials(monkeypatch):
    monkeypatch.delenv("GMAIL_ADDRESS", raising=False)
    res, items = email_inbox.collect([])
    assert res.skipped and items == []


def test_full_run_baseline_then_new(monkeypatch, tmp_path):
    """First run: website links are baseline. Second run: only genuinely new links appear, not as baseline."""
    from collector import store as store_mod
    monkeypatch.setattr(store_mod, "ROOT", tmp_path)
    monkeypatch.setattr(main, "load_paos", lambda: [pao()])
    monkeypatch.delenv("GMAIL_ADDRESS", raising=False)
    monkeypatch.delenv("NEWSAPI_KEY", raising=False)
    pages = {"https://www.icai.org/news": NEWS, "https://www.icai.org": HOME, "https://news.google.com": GOOGLE_RSS}
    monkeypatch.setattr(websites, "fetch", fake_fetch(pages))
    monkeypatch.setattr(news_search, "fetch", fake_fetch(pages))
    from collector import pagewatch
    monkeypatch.setattr(pagewatch, "fetch", fake_fetch(pages))

    s1 = main.run(dry_run=True)
    data = json.loads((tmp_path / "data" / "local.json").read_text())
    web = [i for i in data["items"].values() if i["source"] == "website"]
    assert web and all(i["is_baseline"] for i in web)
    gn = [i for i in data["items"].values() if i["source"] == "google_news"]
    assert gn and not any(i["is_baseline"] for i in gn)
    assert "_unmatched_email" in data["paos"] and data["health"]["icai::website"]["status"] == "ok"

    pages["https://www.icai.org/news"] = NEWS.replace(
        "<ul>", '<ul><li><a href="/post/council-election-results-2026">Results of the Council election 2026 announced today</a></li>', 1)
    s2 = main.run(dry_run=True)
    data = json.loads((tmp_path / "data" / "local.json").read_text())
    new = [i for i in data["items"].values() if "Council election" in i["title"]]
    assert len(new) == 1 and new[0]["is_baseline"] is False
    assert s2["new"] == 1 and data["health"]["icai::website"]["items_new"] == 1
    assert data["health"]["icai::google_news"]["items_new"] == 0


# ---- page-pattern matching (adaptive link detection) ----
# A site whose article addresses have no news-like hint (no "news", dates or ids), with a
# repeated card list, a plain menu-like block of short links, and one <time> tag per card.
SLUG_HOME = """<html><body>
<div class="quick"><ul class="links">
 <li><a href="/join">Become a member</a></li><li><a href="/member-benefits">Member benefits</a></li>
 <li><a href="/exams">Exams</a></li><li><a href="/shop">Shop</a></li>
</ul></div>
<section class="latest"><div class="cards">
 <div class="card"><time datetime="2026-10-20T09:00:00+08:00">20 Oct</time>
   <h3><a href="/stories/institute-releases-guidance-on-sustainability-reporting">Institute releases guidance on sustainability reporting</a></h3></div>
 <div class="card"><time datetime="2026-10-14">14 Oct</time>
   <h3><a href="/stories/council-appoints-chief-executive-officer">Council appoints a new chief executive officer</a></h3></div>
 <div class="card"><time datetime="2026-10-02">2 Oct</time>
   <h3><a href="/stories/members-invited-to-comment-on-ethics-code">Members invited to comment on revised ethics code</a></h3></div>
</div></section></body></html>"""


def test_pattern_matching_finds_slug_articles(monkeypatch):
    p = pao(id="slug", website="https://slug.org.example")
    monkeypatch.setattr(websites, "fetch", fake_fetch({"https://slug.org.example": SLUG_HOME}))
    res = websites.collect(p)
    titles = {i.title for i in res.items}
    assert titles == {"Institute releases guidance on sustainability reporting",
                      "Council appoints a new chief executive officer",
                      "Members invited to comment on revised ethics code"}
    assert all(i.via == "pattern" for i in res.items)
    assert "loose link matching" not in res.message and "page-pattern matching" in res.message
    dates = sorted(i.published_at[:10] for i in res.items)
    assert dates == ["2026-10-02", "2026-10-14", "2026-10-20"]
    assert any(pg["kind"] == "pattern:news" for pg in res.pages)


def test_pattern_matching_ignores_menu_blocks():
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(SLUG_HOME, "lxml")
    keep = websites.pattern_links(soup, "https://slug.org.example/", "slug.org.example")
    assert keep and not any(k.endswith(("/join", "/member-benefits", "/exams", "/shop")) for k in keep)


def test_pattern_links_not_flagged_when_hint_present(monkeypatch):
    # the ordinary rules already catch these, so they keep behaving exactly as before
    monkeypatch.setattr(websites, "fetch", fake_fetch({"https://www.icai.org/news": NEWS, "https://www.icai.org": HOME}))
    res = websites.collect(pao())
    assert not any(i.via == "pattern" for i in res.items)
    assert not any(pg["kind"].startswith("pattern:") for pg in res.pages)


def test_pattern_first_finds_saved_as_first_scan(monkeypatch, tmp_path):
    """Day 1 of pattern matching on an existing site: its older articles are hidden as first scan.
    Day 2: a genuinely new article found the same way shows up as new."""
    from collector import store as store_mod
    monkeypatch.setattr(store_mod, "ROOT", tmp_path)
    p = pao(id="slug", website="https://slug.org.example", search_terms="")
    monkeypatch.setattr(main, "load_paos", lambda: [p])
    monkeypatch.delenv("GMAIL_ADDRESS", raising=False)
    old_home = SLUG_HOME.replace('<section class="latest">', '<section class="latest"><a href="/press/2026/old-one">Old style news link from last year here</a>')
    pages = {"https://slug.org.example": old_home}
    monkeypatch.setattr(websites, "fetch", fake_fetch(pages))
    from collector import pagewatch
    monkeypatch.setattr(pagewatch, "fetch", fake_fetch(pages))
    main.run(dry_run=True, sources=["website"])          # first scan of the site: everything baseline
    # simulate a site that was already tracked before pattern matching existed
    data = json.loads((tmp_path / "data" / "local.json").read_text())
    data["items"] = {k: v for k, v in data["items"].items() if "old-one" in v["url"]}
    data["pages"] = {k: v for k, v in data["pages"].items() if "::pattern:" not in k}
    (tmp_path / "data" / "local.json").write_text(json.dumps(data))

    main.run(dry_run=True, sources=["website"])
    data = json.loads((tmp_path / "data" / "local.json").read_text())
    stories = [i for i in data["items"].values() if "/stories/" in i["url"]]
    assert len(stories) == 3 and all(i["is_baseline"] for i in stories)

    pages["https://slug.org.example"] = old_home.replace(
        '<div class="cards">', '<div class="cards"><div class="card"><time datetime="2026-10-22">22 Oct</time>'
        '<h3><a href="/stories/annual-conference-programme-announced">Annual conference programme announced for members</a></h3></div>', 1)
    s = main.run(dry_run=True, sources=["website"])
    data = json.loads((tmp_path / "data" / "local.json").read_text())
    fresh = [i for i in data["items"].values() if "annual-conference" in i["url"]]
    assert len(fresh) == 1 and fresh[0]["is_baseline"] is False and s["new"] == 1


def test_own_brief_emails_are_skipped():
    paos = [pao(), pao(id="acca", name="Association of Chartered Certified Accountants", abbr="ACCA", website="https://accaglobal.com")]
    body = "This brief covers ICAI and ACCA news this week."
    by_subject = make_email("CAPA News Monitor <capanewsapi@gmail.com>", "CAPA weekly intelligence brief: 11 Oct 2026 – 18 Oct 2026", body)
    assert email_inbox.parse_message(by_subject, paos) == []
    assert email_inbox.parse_message(make_email("boss@capa-apac.org", "Fwd: CAPA Weekly recap: 26 Oct – 1 Nov 2026", body), paos) == []
    assert email_inbox.parse_message(make_email("capanewsapi@gmail.com", "Anything", body), paos, own_address="CapaNewsApi@gmail.com") == []
    m = EmailMessage()
    m["From"], m["Subject"], m["X-PAO-Monitor"] = "x@gmail.com", "Weekly news", "brief"
    m.set_content(body)
    assert email_inbox.parse_message(m.as_bytes(), paos) == []
    # a real email that mentions CAPA is still collected
    real = make_email("press@accaglobal.com", "ACCA and CAPA sign a partnership", body)
    assert [i.pao_id for i in email_inbox.parse_message(real, paos, own_address="capanewsapi@gmail.com")] == ["acca"]


def make_html_email(sender, subject, html, text=""):
    m = EmailMessage()
    m["From"], m["Subject"], m["Message-ID"] = sender, subject, "<n1@mail.example>"
    m["Date"] = "Wed, 04 Nov 2026 09:00:00 +0000"
    m.set_content(text or "plain version")
    m.add_alternative(html, subtype="html")
    return m.as_bytes()


def test_email_links_to_the_story_not_to_gmail():
    html = ('<a href="https://t.example/view">View in browser</a><img src="x"><a href="https://t.example/logo"><img src="logo.png"></a>'
            '<h2><a href="https://t.example/Ctc/abc">October 2026 IASB Update and podcast</a></h2>'
            '<a href="https://t.example/unsub">Unsubscribe</a>')
    got = email_inbox.parse_message(make_html_email("IFRS <no-reply@news.ifrs.org>", "IFRS Foundation news alert", html), [pao()])
    assert got[0].url == "https://t.example/Ctc/abc"
    # plain-text emails show links as 'words (https://...)'
    txt = ("Manage your preferences (https://t.example/prefs)\n04 November 2026 October 2026 IASB Update and podcast "
           "(https://t.example/Ctc/xyz)\nUnsubscribe (https://t.example/u)")
    assert email_inbox.link_from_text(txt) == "https://t.example/Ctc/xyz"
    # no link at all: falls back to the Gmail search
    assert "mail.google.com" in email_inbox.parse_message(make_email("x@gmail.com", "Hello", "no links here"), [pao()])[0].url
    # a tracking link is followed to the real page when a resolver is given
    got = email_inbox.parse_message(make_html_email("a@b.org", "s", html), [pao()], resolve=lambda u: "https://www.ifrs.org/news/x")
    assert got[0].url == "https://www.ifrs.org/news/x"


def test_one_email_is_one_item_when_paos_share_a_website():
    iasb = pao(id="iasb", name="International Accounting Standards Board (IFRS Foundation)", abbr="IASB", website="https://www.ifrs.org/")
    issb = pao(id="issb", name="International Sustainability Standards Board (IFRS Foundation)", abbr="ISSB", website="https://www.ifrs.org/")
    for subject, body, want in (("IFRS Foundation news alert", "October 2026 IASB Update and podcast", "iasb"),
                                ("IFRS Foundation news alert", "October 2026 ISSB Update and podcast", "issb"),
                                ("IFRS Foundation news alert", "nothing specific", "iasb")):
        got = email_inbox.parse_message(make_email("IFRS <no-reply@news.ifrs.org>", subject, body), [iasb, issb])
        assert [i.pao_id for i in got] == [want]


def test_relink_old_emails(tmp_path):
    from collector.store import JsonStore
    store = JsonStore(tmp_path / "s.json")
    store.data["items"]["e1"] = {"id": "e1", "source": "email", "url": "https://mail.google.com/mail/#search/x",
                                 "content": "Headline words (https://t.example/story) Unsubscribe (https://t.example/u)"}
    store.data["items"]["e2"] = {"id": "e2", "source": "email", "url": "https://mail.google.com/mail/#search/y", "content": "no links"}
    assert email_inbox.relink(store) == 1
    assert store.data["items"]["e1"]["url"] == "https://t.example/story"
    assert store.data["items"]["e2"]["url"].startswith("https://mail.google.com")


def test_google_news_retries_when_google_says_503(monkeypatch):
    seen = []
    def flaky(url, **kw):
        seen.append(url)
        if len(seen) < 3:
            return type("R", (), {"status": 503, "content": b"", "url": url})()
        return fake_fetch({"https://news.google.com": GOOGLE_RSS})(url, **kw)
    monkeypatch.setattr(news_search, "fetch", flaky)
    res = news_search.collect_google(pao(search_terms='"ICAI" president'))
    assert len(seen) == 3 and res.ok and res.items          # two refusals, then the third try works


def test_google_news_gives_up_early_when_google_keeps_refusing(monkeypatch):
    seen = []
    def refuse(url, **kw):
        seen.append(url)
        return type("R", (), {"status": 503, "content": b"", "url": url})()
    monkeypatch.setattr(news_search, "fetch", refuse)
    results = [news_search.collect_google(pao(id=f"p{i}", search_terms='"X" news')) for i in range(10)]
    assert all(not r.ok for r in results)
    assert len(seen) == 4 * 3 and news_search.GATE.tripped   # 4 searches x 3 tries, then it stops asking
    assert "refusing" in results[-1].message
    # a healthy search spaces requests apart
    gate = news_search.GoogleGate(gap=1.5, sleep=lambda s: waits.append(s))
    waits = []
    for _ in range(3):
        gate.wait()
    assert len(waits) == 2 and all(w >= 1.4 for w in waits)
