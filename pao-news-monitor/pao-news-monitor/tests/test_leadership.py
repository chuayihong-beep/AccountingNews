"""Leadership: finding the President when a site never says "leadership", and the names-only leaders list."""
from collector import pagewatch
from tests.test_collector import fake_fetch, pao

FILLER = "<p>" + "Some text about the institute. " * 40 + "</p>"
HOME_NO_LINKS = """<html><body><nav><a href="/news">News</a><a href="/cpd">CPD</a><a href="/members">Members</a></nav>
""" + FILLER + "</body></html>"
OFFICE_HOLDERS = """<html><body><h1>Council 2026</h1>
 <div><h4>Dr Aisha Rahman</h4><p>President</p></div>
 <div><h4>Mr Tan Wei Ming</h4><p>Vice President</p></div>
 <div><h4>Ms Some Member</h4><p>Council Member</p></div></body></html>"""
SEARCH_RESULTS = """<html><body><h1>Search results for president</h1><ul>
 <li><a href="/page/2026-council">Our President and Council</a></li>
 <li><a href="/news/2025/president-message">President's message on CPD</a></li></ul></body></html>"""


def site(pages):
    return fake_fetch(dict(sorted(pages.items(), key=lambda kv: -len(kv[0]))))


def recording(pages):
    seen = []
    inner = site(pages)

    def _fetch(url, **kw):
        seen.append(url)
        return inner(url, **kw)
    return _fetch, seen


def mia(**kw):
    return pao(id="mia", name="Malaysian Institute of Accountants", abbr="MIA", website="https://mia.org.my",
               news_locale="en-MY", **kw)


def test_finds_president_through_site_search():
    res = pagewatch.collect(mia(), {}, fetcher=site({
        "https://mia.org.my/?s=president": SEARCH_RESULTS,
        "https://mia.org.my/page/2026-council": OFFICE_HOLDERS,
        "https://mia.org.my": HOME_NO_LINKS,
    }))
    lead = [p for p in res.pages if p["kind"] == "leadership"]
    assert [p["url"] for p in lead] == ["https://mia.org.my/page/2026-council"]
    assert "Dr Aisha Rahman | President" in lead[0]["snapshot"]
    assert "searching the site for 'president'" in res.message
    assert "no leadership page found" not in res.message


def test_falls_back_to_common_addresses():
    res = pagewatch.collect(mia(), {}, fetcher=site({
        "https://mia.org.my/about-us/council": OFFICE_HOLDERS,
        "https://mia.org.my": HOME_NO_LINKS,          # also answers the search with the homepage (no results)
    }))
    lead = [p for p in res.pages if p["kind"] == "leadership"]
    assert [p["url"] for p in lead] == ["https://mia.org.my/about-us/council"]


def test_misses_while_searching_are_not_reported():
    res = pagewatch.collect(mia(), {}, fetcher=site({"https://mia.org.my": HOME_NO_LINKS}))
    assert "returned error" not in res.message
    assert "no leadership page found" in res.message
    assert not [p for p in res.pages if p["kind"] == "leadership"]


def test_no_search_when_staff_chose_the_page():
    fetch, seen = recording({"https://mia.org.my/our-council": "<html><body>Under maintenance</body></html>",
                             "https://mia.org.my": HOME_NO_LINKS})
    pagewatch.collect(mia(leadership_url="https://mia.org.my/our-council"), {}, fetcher=fetch)
    assert not any("president" in u for u in seen)


def test_reuses_a_page_that_worked_before():
    prev = {("mia", "https://mia.org.my/page/2026-council", "leadership"):
            {"snapshot": "Dr Aisha Rahman | President", "pao_id": "mia"}}
    fetch, seen = recording({"https://mia.org.my/page/2026-council": OFFICE_HOLDERS,
                             "https://mia.org.my": HOME_NO_LINKS})
    res = pagewatch.collect(mia(), prev, fetcher=fetch)
    assert [p["url"] for p in res.pages if p["kind"] == "leadership"] == ["https://mia.org.my/page/2026-council"]
    assert not any("?s=president" in u for u in seen)             # no need to search again


# ---------- leaders on file (names only) ----------
import json
from datetime import datetime, timezone

from collector import leaders
from collector.ai import AIUnavailable
from collector.store import JsonStore

PAGE = "Dr Aisha Rahman | President\nMr Tan Wei Ming | Vice-President\nDatuk Lee Chong | Deputy President"
NOW = datetime(2026, 11, 2, tzinfo=timezone.utc)


class FakeChain:
    def __init__(self, answers):
        self.answers = list(answers)
        self.calls = []

    def chain(self, kind):
        return ["fake:model"]

    def ask(self, kind, system, user, max_tokens=1500, temperature=0.2):
        self.calls.append(user)
        a = self.answers.pop(0)
        if isinstance(a, Exception):
            raise a
        return (a if isinstance(a, str) else json.dumps(a)), "fake:model"


def test_extract_keeps_only_names_on_the_page():
    chain = FakeChain([{"leaders": [
        {"role": "President", "name": "Dr Aisha Rahman"},
        {"role": "Vice-President", "name": "Mr  Tan Wei Ming"},          # spacing differs: still on the page
        {"role": "Deputy President", "name": "Datuk Lee Chong"},
        {"role": "President", "name": "Someone Invented"},              # not on the page
        {"role": "Treasurer", "name": "Dr Aisha Rahman"},               # not a role we keep
        {"role": "Vice President", "name": "call +60 3 1234 5678"},     # not a name
    ]}])
    got, _ = leaders.extract(chain, {"id": "mia", "name": "MIA"}, PAGE)
    assert got == [{"role": "President", "name": "Dr Aisha Rahman"},
                   {"role": "Vice President", "name": "Mr Tan Wei Ming"},
                   {"role": "Deputy President", "name": "Datuk Lee Chong"}]


def test_extract_unreadable_answer():
    got, _ = leaders.extract(FakeChain(["sorry, I can't help"]), {"id": "mia"}, PAGE)
    assert got is None


def _store(tmp_path, checked=None):
    s = JsonStore(tmp_path / "local.json")
    s.data["paos"] = {"mia": {"id": "mia", "name": "Malaysian Institute of Accountants", "abbr": "MIA",
                              "leaders_checked_at": checked}}
    return s


def page_row(**kw):
    return dict({"pao_id": "mia", "url": "https://mia.org.my/council", "kind": "leadership", "snapshot": PAGE}, **kw)


def test_update_saves_names_with_page_and_date(tmp_path):
    s = _store(tmp_path)
    chain = FakeChain([{"leaders": [{"role": "President", "name": "Dr Aisha Rahman"}]}])
    note = leaders.update(s, [page_row(first_seen_at="2026-11-02T00:00:00Z")], chain=chain, now=NOW)
    assert note.startswith("Leaders: updated 1")
    assert s.data["leaders"] == [{"role": "President", "name": "Dr Aisha Rahman", "source_url": "https://mia.org.my/council",
                                  "pao_id": "mia", "as_of": "2026-11-02", "updated_by": "page watch",
                                  "updated_at": "2026-11-02T00:00:00+00:00"}]
    assert s.data["paos"]["mia"]["leaders_checked_at"]


def test_update_skips_unchanged_recently_checked(tmp_path):
    s = _store(tmp_path, checked="2026-10-30T00:00:00+00:00")
    chain = FakeChain([])
    assert leaders.update(s, [page_row()], chain=chain, now=NOW) == "Leaders: up to date"
    assert not chain.calls


def test_update_rereads_after_a_change_and_keeps_names_if_none_found(tmp_path):
    s = _store(tmp_path, checked="2026-10-30T00:00:00+00:00")
    s.data["leaders"] = [{"pao_id": "mia", "role": "President", "name": "Dr Aisha Rahman"}]
    chain = FakeChain([{"leaders": []}])
    note = leaders.update(s, [page_row(last_changed_at="2026-11-02T00:00:00Z")], chain=chain, now=NOW)
    assert "kept what was on file" in note
    assert s.data["leaders"] == [{"pao_id": "mia", "role": "President", "name": "Dr Aisha Rahman"}]


def test_update_stops_quietly_when_ai_is_out(tmp_path):
    s = _store(tmp_path)
    note = leaders.update(s, [page_row()], chain=FakeChain([AIUnavailable("quota")]), now=NOW)
    assert "stopped" in note and "leaders" not in s.data
