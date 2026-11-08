"""Tests for update 2: news/events/publications, per-page first scan,
leadership & contact page watch, Google News language."""
from collector import main, news_search, pagewatch, websites
from collector.store import JsonStore
from tests.test_collector import GOOGLE_RSS, fake_fetch, pao

FILLER = "<p>" + "Some text about the institute. " * 40 + "</p>"

HOME = """<html><body><nav>
 <a href="/news">News</a><a href="/publications">Publications</a><a href="/events-calendar">Events</a>
 <a href="/about-us/council">Council</a><a href="/contact-us">Contact Us</a></nav>
 <ul><li><a href="/news/2026/agm-held">Annual general meeting held in Mumbai</a></li></ul>""" + FILLER + "</body></html>"
NEWS = """<html><body><ul>
 <li><a href="/news/2026/new-standard">New auditing standard issued for members</a> 2026-10-01</li>
 <li><a href="/events/2026/tax-webinar">Tax webinar for members on 5 November</a></li>
</ul>""" + FILLER + "</body></html>"
PUBS = """<html><body><ul>
 <li><a href="/publications/journal-oct-2026">The Accountant Journal October 2026 issue</a></li>
 <li><a href="/files/annual-report-2026.pdf">Annual Report 2025-26 of the Institute</a></li>
</ul>""" + FILLER + "</body></html>"
EVENTS = """<html><body><ul>
 <li><a href="/event/2026/national-conference">National Conference 2026 registration open</a></li>
</ul>""" + FILLER + "</body></html>"


def site(pages):
    # most specific first: fake_fetch matches by prefix
    return fake_fetch(dict(sorted(pages.items(), key=lambda kv: -len(kv[0]))))


SITE = {"https://www.icai.org/news": NEWS, "https://www.icai.org/publications": PUBS,
        "https://www.icai.org/events-calendar": EVENTS, "https://www.icai.org": HOME}


def test_page_kind_words():
    assert websites.page_kind("Publications") == "publications"
    assert websites.page_kind("Upcoming Events") == "events"
    assert websites.page_kind("News & Events") == "news"
    assert websites.page_kind("刊物") == "publications"
    assert websites.page_kind("Our Team") is None


def test_item_kind_from_address():
    assert websites.item_kind("https://x.org/events/2026/a", "news") == "events"
    assert websites.item_kind("https://x.org/docs/report.pdf", "news") == "publications"
    assert websites.item_kind("https://x.org/news/1", "events") == "events"
    assert websites.item_kind("https://x.org/news/1", "news") == "news"


def test_page_spec():
    assert websites.parse_page_spec("events>https://x.org/cpd") == ("events", "https://x.org/cpd")
    assert websites.parse_page_spec("https://x.org/news") == ("news", "https://x.org/news")


def test_scans_publications_and_events_pages(monkeypatch):
    monkeypatch.setattr(websites, "fetch", site(SITE))
    res = websites.collect(pao())
    kinds = {i.title: i.kind for i in res.items}
    assert kinds["The Accountant Journal October 2026 issue"] == "publications"
    assert kinds["Annual Report 2025-26 of the Institute"] == "publications"
    assert kinds["National Conference 2026 registration open"] == "events"
    assert kinds["Tax webinar for members on 5 November"] == "events"   # found on news page, address says event
    assert kinds["New auditing standard issued for members"] == "news"
    assert {p["kind"] for p in res.pages} == {"listing:news", "listing:publications", "listing:events"}
    assert "1 publications" in res.message and "1 events" in res.message


def test_newly_scanned_page_is_first_scan(monkeypatch):
    """Upgrading must not flood old publications in as 'new'."""
    monkeypatch.setattr(websites, "fetch", site(SITE))
    res = websites.collect(pao())
    store = JsonStore(path="/dev/null/none")  # never saved here
    store.existing_ids = lambda ids: set()
    health = {("icai", "website"): {"last_success_at": "2026-10-01T00:00:00+00:00"}}
    # first run with page tracking: news pages are known, publications/events are new
    main.apply_baseline(res, health, store, known_pages={})
    hidden = {i.title for i in res.items if i.is_baseline}
    shown = {i.title for i in res.items if not i.is_baseline}
    assert "The Accountant Journal October 2026 issue" in hidden
    assert "National Conference 2026 registration open" in hidden
    assert "New auditing standard issued for members" in shown
    # next run: all pages known, a new publication shows up normally
    res2 = websites.collect(pao())
    known = {("icai", p["url"], p["kind"]): {} for p in res.pages}
    main.apply_baseline(res2, health, store, known_pages=known)
    assert not any(i.is_baseline for i in res2.items)


def test_google_news_items_get_language(monkeypatch):
    monkeypatch.setattr(news_search, "fetch", fake_fetch({"https://news.google.com": GOOGLE_RSS}))
    res = news_search.collect_google(pao(id="cncc", search_terms='"Compagnie nationale"', news_locale="fr-FR"))
    assert res.items and all(i.language == "fr" for i in res.items)


# ---------- page watch ----------

COUNCIL_V1 = """<html><body><nav><a href="/president-message">President's Message</a></nav>
<div class="people">
 <div><h4>CA Ranjeet Kumar Agarwal</h4><p>President</p></div>
 <div><h4>CA Charanjot Singh Nanda</h4><p>Vice-President</p></div>
 <div><h4>CA Some Member</h4><p>Central Council Member</p></div>
 <div><h4>Mr Rakesh Sehgal</h4><p>Secretary</p></div>
</div><p>Past Presidents list is on another page.</p></body></html>"""
COUNCIL_V2 = COUNCIL_V1.replace("CA Ranjeet Kumar Agarwal", "CA Charanjot Singh Nanda ").replace(
    "<h4>CA Charanjot Singh Nanda</h4><p>Vice-President", "<h4>CA Prasanna Kumar D</h4><p>Vice-President")
CONTACT_V1 = """<html><body><h1>Contact us</h1><p>ICAI Bhawan, Indraprastha Marg, New Delhi 110002</p>
<p>Phone: +91 11 3989 3989</p><p>Email: info@icai.in</p><p>We usually reply within a week.</p>
<footer><p>Level 5, ICAI Tower, Indraprastha Marg</p></footer></body></html>"""
CONTACT_V2 = CONTACT_V1.replace("+91 11 3989 3989", "+91 11 3011 0444")
PW_HOME = """<html><body><nav><a href="/about-us/council">Council</a><a href="/president-message">President's message</a>
<a href="/contact-us">Contact Us</a><a href="/news">News</a></nav>""" + FILLER + "</body></html>"


def test_leadership_lines_only_top_roles():
    lines = pagewatch.leadership_lines(COUNCIL_V1)
    joined = "\n".join(lines)
    assert "CA Ranjeet Kumar Agarwal | President" in joined
    assert "Vice-President" in joined
    assert "Central Council Member" not in "".join(l.split(" | ")[1] for l in lines if " | " in l)
    assert "Past Presidents" not in joined


def test_contact_lines():
    lines = pagewatch.contact_lines(CONTACT_V1)
    assert "Phone: +91 11 3989 3989" in lines and "Email: info@icai.in" in lines
    assert "Level 5, ICAI Tower, Indraprastha Marg" in lines          # footer kept on contact pages
    assert not any("reply within a week" in l for l in lines)


def test_find_pages():
    lead, contact = pagewatch.find_pages(PW_HOME, "https://www.icai.org")
    assert lead == ["https://www.icai.org/about-us/council"]          # "President's message" skipped
    assert contact == "https://www.icai.org/contact-us"


def _watch(pages, prev):
    return pagewatch.collect(pao(), prev, fetcher=site(pages))


def test_page_watch_first_time_then_change():
    v1 = {"https://www.icai.org/about-us/council": COUNCIL_V1, "https://www.icai.org/contact-us": CONTACT_V1,
          "https://www.icai.org": PW_HOME}
    first = _watch(v1, {})
    assert first.ok and not first.items                                 # first look: just remembered
    assert {p["kind"] for p in first.pages} == {"leadership", "contact"}
    prev = {(p["pao_id"], p["url"], p["kind"]): p for p in first.pages}

    same = _watch(v1, prev)
    assert not same.items

    v2 = {**v1, "https://www.icai.org/about-us/council": COUNCIL_V2, "https://www.icai.org/contact-us": CONTACT_V2}
    changed = _watch(v2, prev)
    kinds = sorted(i.kind for i in changed.items)
    assert kinds == ["contact", "leadership"]
    lead = next(i for i in changed.items if i.kind == "leadership")
    assert "Leadership changed" in lead.title
    assert "CA Ranjeet Kumar Agarwal" in lead.snippet and "Removed" in lead.snippet
    assert "CA Prasanna Kumar D" in lead.snippet and "Added" in lead.snippet
    assert lead.source == "page_watch" and lead.url.endswith("/about-us/council")
    contact = next(i for i in changed.items if i.kind == "contact")
    assert "+91 11 3011 0444" in contact.snippet
    assert "2 change(s) found" in changed.message


def test_page_watch_ignores_broken_page():
    v1 = {"https://www.icai.org/about-us/council": COUNCIL_V1, "https://www.icai.org/contact-us": CONTACT_V1,
          "https://www.icai.org": PW_HOME}
    prev = {(p["pao_id"], p["url"], p["kind"]): p for p in _watch(v1, {}).pages}
    broken = {**v1, "https://www.icai.org/about-us/council": "<html><body>Under maintenance</body></html>"}
    res = _watch(broken, prev)
    assert not res.items
    row = next(p for p in res.pages if p["kind"] == "leadership")
    assert row["status"] == "warning" and "snapshot" not in row        # old snapshot kept


def test_page_watch_uses_urls_from_csv():
    p = pao(website="https://www.icai.org", leadership_url="https://www.icai.org/council-2026",
            contact_url="https://www.icai.org/reach")
    res = pagewatch.collect(p, {}, fetcher=site({"https://www.icai.org/council-2026": COUNCIL_V1,
                                                 "https://www.icai.org/reach": CONTACT_V1}))
    assert sorted(r["url"] for r in res.pages) == ["https://www.icai.org/council-2026", "https://www.icai.org/reach"]


def test_dry_run_end_to_end(monkeypatch, tmp_path):
    """Whole run with page watch, saved to a local file."""
    import collector.store as store_mod
    path = tmp_path / "local.json"
    monkeypatch.setattr(store_mod, "get_store", lambda dry_run=False: JsonStore(path))
    monkeypatch.setattr(main, "get_store", lambda dry_run=False: JsonStore(path))
    monkeypatch.setattr(main, "load_paos", lambda: [pao()])
    pages = {**SITE, "https://www.icai.org/about-us/council": COUNCIL_V1, "https://www.icai.org/contact-us": CONTACT_V1}
    monkeypatch.setattr(websites, "fetch", site(pages))
    monkeypatch.setattr(pagewatch, "fetch", site(pages))
    s1 = main.run(only={"icai"}, sources=["website", "page_watch"], dry_run=True)
    assert s1["errors"] == 0
    pages2 = {**pages, "https://www.icai.org/about-us/council": COUNCIL_V2}
    monkeypatch.setattr(pagewatch, "fetch", site(pages2))
    monkeypatch.setattr(websites, "fetch", site(pages2))
    s2 = main.run(only={"icai"}, sources=["website", "page_watch"], dry_run=True)
    assert s2["changes"] == 1


# ---------- member list lives in the database ----------

def test_member_list_seeded_once_then_database_wins(monkeypatch, tmp_path):
    store = JsonStore(tmp_path / "local.json")
    csv = [pao(), pao(id="picpa", abbr="PICPA", name="Philippine Institute of CPAs", website="https://picpa.com.ph")]
    monkeypatch.setattr(main, "load_paos", lambda: csv)
    first = main.member_list(store, problems=[])
    assert [p.id for p in first] == ["icai", "picpa"]
    rows = store.load_pao_rows()
    assert all(r.get("config_seeded") for r in rows if r["id"] != "_unmatched_email")
    assert any(r["id"] == "_unmatched_email" for r in rows)

    # an admin edits ICAI, deactivates PICPA and adds a new member on the tracker
    store.data["paos"]["icai"]["website"] = "https://www.icai.org/new"
    store.data["paos"]["picpa"]["active"] = False
    store.data["paos"]["tia"] = dict(id="tia", grp="Associate", name="Test Institute", abbr="TIA", website="https://tia.example.org",
                                     active=True, search_terms='"Test Institute"', news_locale="en-MY", sort_order=99)
    # ...and someone also edits paos.csv: ignored now
    csv[0] = pao(website="https://from-csv.example")
    second = {p.id: p for p in main.member_list(store, problems=[])}
    assert second["icai"].website == "https://www.icai.org/new"
    assert not second["picpa"].is_active
    assert second["tia"].group == "Associate" and second["tia"].news_locale == "en-MY" and second["tia"].is_active


def test_member_list_falls_back_to_csv_before_db_update(monkeypatch, tmp_path):
    store = JsonStore(tmp_path / "local.json")
    monkeypatch.setattr(main, "load_paos", lambda: [pao()])
    got = main.member_list(store, problems=["paos member-list columns"])
    assert [p.id for p in got] == ["icai"]
    assert "config_seeded" not in store.data["paos"]["icai"]


def test_newsletter_and_article_type():
    assert websites.page_kind("Newsletter") == "articles"
    assert websites.page_kind("Insights & Articles") == "articles"
    assert websites.page_kind("Publications") == "publications"
    assert websites.page_kind("News & Insights") == "news"
    assert websites.item_kind("https://x.org/newsletter/oct-2026", "news") == "articles"
    assert websites.item_kind("https://x.org/blog/ai-and-audit", "news") == "articles"
    assert websites.item_kind("https://x.org/library/report.pdf", "news") == "publications"


SIA_V1 = """<html><body><h1>Council members</h1><p>Lauano Dennis Chan Tung, President</p>
<p>Hits: 933</p><p>Vice President of the Council</p><p>Tagaloa Faafouina Su'a</p>
<p>Contact: Level 2, Lotemau Centre, Apia</p><p>Visitors: 10,512</p></body></html>"""


def test_page_watch_ignores_hit_counters():
    """SIA's council page has a visit counter next to the VP's title - that alone is not a change."""
    url = "https://www.icai.org/about-us/council"
    v1 = {url: SIA_V1, "https://www.icai.org/contact-us": CONTACT_V1, "https://www.icai.org": PW_HOME}
    first = _watch(v1, {})
    assert not any("Hits" in p.get("snapshot", "") for p in first.pages)
    prev = {(p["pao_id"], p["url"], p["kind"]): p for p in first.pages}
    bumped = {**v1, url: SIA_V1.replace("933", "947").replace("10,512", "10,604")}
    assert not _watch(bumped, prev).items
    # a snapshot saved before this fix (still containing the counter) doesn't raise one last false alarm
    old_style = {k: dict(v, snapshot=v["snapshot"].replace("Vice President of the Council", "Hits: 933 | Vice President of the Council", 1))
                 for k, v in prev.items()}
    assert not _watch(bumped, old_style).items
    # a real change next to the counter is still caught
    changed = {**v1, url: SIA_V1.replace("947", "950").replace("Tagaloa Faafouina Su'a", "New Person")}
    assert [i.kind for i in _watch(changed, prev).items] == ["leadership"]
