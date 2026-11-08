"""Weekly brief: AI fallback chain + brief assembly (offline, fake AI)."""
import json
from datetime import datetime, timezone

import pytest

from collector import ai, brief
from collector.store import JsonStore


class FakeResp:
    def __init__(self, status, payload=None, text=""):
        self.status_code, self._payload, self.text = status, payload, text or json.dumps(payload or {})

    def json(self):
        if self._payload is None:
            raise ValueError
        return self._payload


def answer(text):
    return FakeResp(200, {"choices": [{"message": {"content": text}}]})


class FakeHTTP:
    """Replies by model name: a list of responses per model (popped in order)."""
    def __init__(self, plan):
        self.plan, self.calls = plan, []

    def post(self, url, json=None, **kw):
        self.calls.append(json["model"])
        q = self.plan.get(json["model"]) or [FakeResp(404, text="unknown model")]
        return q.pop(0) if len(q) > 1 else q[0]


ENV = {"GITHUB_TOKEN": "t", "AI_MODELS_FAST": "github:m1,github:m2,gemini:g1", "AI_MODELS_SMART": "github:big,github:m2"}


def test_chain_falls_back_on_quota_and_remembers():
    http = FakeHTTP({"m1": [FakeResp(429, text="rate limited")], "m2": [answer("hello")]})
    c = ai.Chain(env=ENV, session=http, sleep=lambda s: None)
    assert c.ask("fast", "s", "u") == ("hello", "github:m2")
    assert c.ask("fast", "s", "u") == ("hello", "github:m2")
    assert http.calls == ["m1", "m2", "m2"]          # m1 not retried after its quota ran out
    assert "github:m1" in c.dead and c.used == ["github:m2", "github:m2"]


def test_chain_skips_providers_without_keys_and_retries_5xx_once():
    http = FakeHTTP({"m1": [FakeResp(503, text="busy"), answer("ok")]})
    c = ai.Chain(env=ENV, session=http, sleep=lambda s: None)   # no GEMINI_API_KEY: g1 not in chain
    assert [s for s, *_ in c.chain("fast")] == ["github:m1", "github:m2"]
    assert c.ask("fast", "s", "u") == ("ok", "github:m1")


def test_chain_all_fail():
    c = ai.Chain(env={"GITHUB_TOKEN": "t", "AI_MODELS_FAST": "github:x"}, session=FakeHTTP({}), sleep=lambda s: None)
    with pytest.raises(ai.AIUnavailable):
        c.ask("fast", "s", "u")
    with pytest.raises(ai.AIUnavailable, match="no keys"):
        ai.Chain(env={}, session=FakeHTTP({})).ask("fast", "s", "u")


def test_parse_json_tolerates_fences():
    assert ai.parse_json('```json\n[{"n": 1}]\n```') == [{"n": 1}]
    assert ai.parse_json('Sure! Here it is: [{"n": 2}] hope that helps') == [{"n": 2}]
    assert ai.parse_json("nonsense") is None


# ---------- brief ----------
NOW = datetime(2026, 10, 19, 0, 0, tzinfo=timezone.utc)


def make_store(tmp_path):
    s = JsonStore(tmp_path / "local.json")
    s.data["paos"] = {
        "icai": dict(id="icai", grp="Member", jurisdiction="India", name="ICAI", abbr="ICAI", active=True, sort_order=1),
        "iesba": dict(id="iesba", grp="Stakeholder", jurisdiction="Global", name="IESBA", abbr="IESBA", active=True, sort_order=2),
        "sia": dict(id="sia", grp="Member", jurisdiction="Samoa", name="Samoa Institute", abbr="SIA", active=True, sort_order=3),
    }
    def item(i, pao, title, **kw):
        return {"id": i, "pao_id": pao, "source": "website", "title": title, "url": f"https://x.org/{i}",
                "first_seen_at": "2026-10-16T00:00:00+00:00", "published_at": "2026-10-15T00:00:00+00:00",
                "is_baseline": False, "relevance": None, "kind": "news", **kw}
    s.data["items"] = {
        "a": item("a", "icai", "ICAI launches AI audit toolkit for members"),
        "b": item("b", "iesba", "IESBA consultation on technology-related ethics, comments due 30 Nov"),
        "c": item("c", "icai", "Exam dates announced", relevance="none"),
        "d": item("d", "icai", "Old link", is_baseline=True),
        "e": item("e", "icai", "Leadership changed on website: + CA X | President", source="page_watch", kind="leadership"),
        "old": item("old", "icai", "Last month", first_seen_at="2026-09-01T00:00:00+00:00", published_at="2026-09-01T00:00:00+00:00"),
    }
    return s


# items reach the tagger most useful first: page-watch change (e), then website items a, b
TAGS = json.dumps([
    {"n": 1, "summary": "ICAI announced a new president on its website.", "themes": ["other"], "importance": 3, "leadership": True},
    {"n": 2, "summary": "ICAI launched an AI audit toolkit.", "themes": ["ai_digital"], "importance": 3, "leadership": False},
    {"n": 3, "summary": "IESBA consults on technology ethics; comments due 30 Nov.", "themes": ["ethics_standards", "ai_digital"], "importance": 3},
])
EXPLAIN = json.dumps([{"n": 1, "text": "ICAI launched an AI audit toolkit. Other PAOs may want to compare notes."},
                      {"n": 2, "text": "IESBA is consulting on technology ethics; comments are due on 30 November."}])


class Page:
    def __init__(self, status=404, text=""):
        self.status, self.text = status, text


def no_pages(url):
    return Page()


def build(store, http=None, env=ENV, fetcher=no_pages):
    chain = ai.Chain(env=env, session=http or FakeHTTP({}), sleep=lambda s: None)
    return brief.build(store, days=7, chain=chain, now=NOW, fetcher=fetcher)


def test_recap_with_ai(tmp_path):
    store = make_store(tmp_path)
    row = build(store, FakeHTTP({"m1": [answer(TAGS)], "big": [answer(EXPLAIN)]}))
    c = row["content"]
    assert row["status"] == "draft" and row["stats"]["items"] == 3          # not_relevant, baseline and old excluded
    assert row["stats"]["tagged"] == 3 and row["models_used"] == "github:m1, github:big"
    assert c.startswith("# Weekly recap\n**12 Oct – 18 Oct 2026**")
    for section in ("## Highlights", "## Other high", "## Medium", "## No news found\nSIA."):
        assert section in c
    # titles link straight to the page; no numbered citations or source list
    assert "### [ICAI launches AI audit toolkit for members](https://x.org/a)" in c
    assert "ICAI launched an AI audit toolkit. Other PAOs may want to compare notes." in c
    assert "[1]" not in c and "## Sources" not in c
    # the page-watch notice is listed but never leads (its title is a diff)
    hl = c.split("## Other high")[0]
    assert "x.org/e" not in hl and "x.org/e" in c
    assert {s["item_id"] for s in row["sources"]} == {"a", "b", "e"}
    assert store.data["items"]["a"]["ai_themes"] == ["ai_digital"]


def test_recap_without_ai_uses_the_excerpt(tmp_path):
    store = make_store(tmp_path)
    store.data["items"]["a"]["snippet"] = "The toolkit helps auditors test AI systems."
    store.data["items"]["a"]["ai_relevance"] = "high"
    row = build(store, env={})
    c = row["content"]
    assert row["models_used"] == "none" and "No AI model was available" in c
    assert "The toolkit helps auditors test AI systems." in c
    assert any("stopped" in n for n in row["stats"]["notes"])


def test_recap_when_explanations_fail_uses_summaries(tmp_path):
    store = make_store(tmp_path)
    http = FakeHTTP({"m1": [answer(TAGS)], "big": [FakeResp(429, text="quota")], "m2": [FakeResp(429, text="quota")]})
    row = build(store, http)
    assert "ICAI launched an AI audit toolkit." in row["content"] and row["stats"]["tagged"] == 3
    assert any("highlight explanations stopped" in n for n in row["stats"]["notes"])


def test_highlights_get_the_article_text(tmp_path):
    store = make_store(tmp_path)
    store.data["items"]["a"]["relevance"] = "high"
    seen = []

    def fetcher(url):
        seen.append(url)
        return Page(200, "<html><body><nav>Menu</nav><p>" + "The toolkit covers model risk, data quality and audit trails. " * 3
                    + "</p><footer><p>Copyright notice that is long enough to count as a paragraph here.</p></footer></body></html>")
    http = FakeHTTP({"m1": [answer(TAGS)], "big": [answer(EXPLAIN)]})
    build(store, http, fetcher=fetcher)
    assert "https://x.org/a" in seen
    sent = [c for c in http.calls]
    assert "big" in sent


def test_unreadable_200_skips_model():
    """A retired endpoint answering 200 'OK' must not be retried all run."""
    class Plain(FakeResp):
        headers = {"content-type": "text/plain"}
    http = FakeHTTP({"m1": [Plain(200, None, text="OK")], "m2": [answer("fine")]})
    c = ai.Chain(env=ENV, session=http, sleep=lambda s: None)
    assert c.ask("fast", "s", "u") == ("fine", "github:m2")
    assert c.ask("fast", "s", "u") == ("fine", "github:m2")
    assert http.calls == ["m1", "m2", "m2"]


def test_default_chain_uses_free_providers_with_keys():
    c = ai.Chain(env={"GEMINI_API_KEY": "g", "GROQ_API_KEY": "q", "CF_ACCOUNT_ID": "a", "CF_AI_TOKEN": "t", "OPENROUTER_API_KEY": "o"})
    order = [s.split(":")[0] for s, *_ in c.chain("smart")]
    firsts = [p for i, p in enumerate(order) if p not in order[:i]]
    assert firsts == ["gemini", "groq", "cloudflare", "openrouter"]     # OpenRouter is the last resort
    assert "github" not in order


def test_cut_off_answer_retried_with_more_room_then_next_model():
    cut = FakeResp(200, {"choices": [{"message": {"content": "## Headlines\n- half"}, "finish_reason": "length"}]})
    http = FakeHTTP({"big": [cut, cut], "m2": [answer("complete brief")]})
    c = ai.Chain(env=ENV, session=http, sleep=lambda s: None)
    assert c.ask("smart", "s", "u", max_tokens=100) == ("complete brief", "github:m2")
    assert http.calls == ["big", "big", "m2"]
    assert any("cut off at 100" in l for l in c.log) and any("cut off at 300" in l for l in c.log)


def test_duplicate_headlines_merged_and_old_drafts_replaced(tmp_path):
    store = make_store(tmp_path)
    store.data["items"]["dup"] = dict(store.data["items"]["a"], id="dup", source="google_news")
    assert len(brief.gather(store, NOW - __import__("datetime").timedelta(days=7))) == 3
    chain = lambda: ai.Chain(env={}, session=FakeHTTP({}))
    store.save_brief(brief.build(store, chain=chain(), now=NOW))
    store.data["briefs"][0]["edited_by"] = None
    kept = dict(brief.build(store, chain=chain(), now=NOW), edited_by="me@capa")
    store.save_brief(kept)
    store.save_brief(brief.build(store, chain=chain(), now=NOW))
    assert len(store.data["briefs"]) == 2 and store.data["briefs"][0]["edited_by"] == "me@capa"


def test_ai_check_reports_each_model(monkeypatch):
    calls = []

    def fake_post(self, url, json=None, **kw):
        calls.append(json["model"])
        return answer("OK") if json["model"] == "gemini-3.8-flash" else FakeResp(429, text="quota")
    monkeypatch.setattr(ai.requests.Session, "post", fake_post)
    rows = ai.check(env={"GEMINI_API_KEY": "g", "AI_MODELS_SMART": "gemini:gemini-3.8-flash,gemini:x", "AI_MODELS_FAST": "gemini:x"})
    assert ("gemini:gemini-3.8-flash", True, "OK") in rows
    assert any(spec == "gemini:x" and not ok for spec, ok, _ in rows)


def test_only_items_published_in_the_week(tmp_path):
    store = make_store(tmp_path)
    # found this week, but published in June -> out; found this week with no date -> in
    store.data["items"]["june"] = dict(store.data["items"]["a"], id="june", title="ICAB elects leaders",
                                       published_at="2026-06-10T00:00:00+00:00", first_seen_at="2026-10-17T00:00:00+00:00")
    store.data["items"]["nodate"] = dict(store.data["items"]["a"], id="nodate", title="Undated notice",
                                         published_at=None, first_seen_at="2026-10-17T00:00:00+00:00")
    got = {i["id"] for i in brief.gather(store, NOW - __import__("datetime").timedelta(days=7))}
    assert "june" not in got and "nodate" in got and "a" in got


def test_staff_tags_steer_the_recap(tmp_path):
    store = make_store(tmp_path)
    store.data["items"]["a"]["relevance"] = "medium"
    store.data["items"]["b"]["relevance"] = "high"
    store.data["items"]["f"] = dict(store.data["items"]["a"], id="f", title="ICAI consults on CPD rules", kind="comment",
                                    relevance=None, url="https://x.org/f")
    lead, other, mid = brief.lay_out(brief.gather(store, NOW - __import__("datetime").timedelta(days=7)))
    assert lead[0]["id"] == "b"                                   # staff High leads
    assert "e" in {i["id"] for i in other}                        # leadership change counts as high, never leads
    assert "a" in {i["id"] for i in lead + mid}                   # staff Medium fills a highlight or goes under Medium
    comment = next(i for i in lead + other if i["id"] == "f")     # opportunities to comment count as high
    assert "Open for comment" in brief.meta(comment, store.data["paos"])


def test_headline_links_and_escapes(tmp_path):
    it = {"title": "PAO [draft] response (2026)", "url": "https://x.org/a b(1)", "language": "en"}
    assert brief.headline(it) == "[PAO (draft) response (2026)](https://x.org/a%20b%281%29)"
    jp = {"title": "日本公認会計士協会のお知らせ", "url": "https://x.org/j", "language": "ja", "ai_summary": "JICPA announced new CPD rules."}
    assert brief.headline(jp) == "[JICPA announced new CPD rules.](https://x.org/j)"
    assert brief.headline({"title": "Email only", "url": ""}) == "Email only"


def test_low_and_no_relevance_stay_out_of_the_brief(tmp_path):
    store = make_store(tmp_path)
    store.data["items"]["a"]["relevance"] = "low"
    store.data["items"]["b"]["relevance"] = "none"
    got = {i["id"] for i in brief.gather(store, NOW - __import__("datetime").timedelta(days=7))}
    assert "a" not in got and "b" not in got


def test_removed_items_stay_out_of_the_brief(tmp_path):
    store = make_store(tmp_path)
    store.data["items"]["a"]["removed_at"] = "2026-10-17T00:00:00+00:00"
    got = {i["id"] for i in brief.gather(store, NOW - __import__("datetime").timedelta(days=7))}
    assert "a" not in got and "b" in got


def test_earlier_briefs_from_the_inbox_stay_out(tmp_path):
    store = make_store(tmp_path)
    store.data["items"]["own"] = dict(store.data["items"]["a"], id="own", source="email",
                                      title="CAPA weekly intelligence brief: 11 Oct 2026 – 18 Oct 2026")
    got = {i["id"] for i in brief.gather(store, NOW - __import__("datetime").timedelta(days=7))}
    assert "own" not in got and "a" in got


def test_same_story_from_two_sources_appears_once():
    a = {"id": "a", "pao_id": "mia", "title": "Ahmad Shahazan Yacob elected MIA's new president, former Bursa chief Umar Swift is VP",
         "relevance": "high", "url": "https://x.org/a", "kind": "news", "published_at": "2026-10-29T00:00:00+00:00"}
    b = dict(a, id="b", title="MIA appoints Ahmad Syahazan Yaacob as president", relevance=None, ai_relevance="high",
             url="https://x.org/b", published_at="2026-10-30T00:00:00+00:00")
    c = dict(a, id="c", title="ICAI to issue Audit Guidance for Multi-disciplinary firms", pao_id="icai", url="https://x.org/c")
    d = dict(a, id="d", title="ICAI issues guidance on sustainability assurance", pao_id="icai", url="https://x.org/d")
    lead, other, mid = brief.lay_out([a, b, c, d])
    ids = [i["id"] for i in lead + other + mid]
    assert "a" in ids and "b" not in ids                    # staff-reviewed version kept, the repeat dropped
    assert "c" in ids and "d" in ids                        # different stories that share a few words both stay
    assert not brief.same_story({"title": "AI raises the stakes for auditor judgement"},
                                {"title": "How CPAs are putting AI to work in audits"})


def test_teaser_text_cut_from_titles():
    t = ("Asia Pacific builds a sustainable future 28th Oct 2026 This report explores how Asia Pacific can turn its lead "
         "in sustainability reporting into resilience across economy, environment and society. Lear")
    assert brief.tidy_title(t) == "Asia Pacific builds a sustainable future"
    long = "A very long headline " * 10
    assert len(brief.tidy_title(long)) <= 121 and brief.tidy_title(long).endswith("…")
    assert brief.tidy_title("ICAI elects new President") == "ICAI elects new President"


def test_rating_one_copy_of_an_email_low_mutes_its_twins(tmp_path):
    """IASB and ISSB share ifrs.org, so one email used to be stored twice: rate one Low, the other still got in."""
    store = make_store(tmp_path)
    base = dict(store.data["items"]["a"], source="email", source_name="IFRS Foundation <no-reply@news.ifrs.org>",
                published_at="2026-10-20T00:00:00+00:00", relevance=None, ai_relevance="high", is_baseline=False)
    store.data["items"]["t1"] = dict(base, id="t1", pao_id="iasb", title="IASB Podcast, IFRIC Updates, Agendas",
                                     original_title="IFRS Foundation news alert", relevance="low")   # staff: Low + edited title
    store.data["items"]["t2"] = dict(base, id="t2", pao_id="issb", title="IFRS Foundation news alert")  # untouched twin
    got = {i["id"] for i in brief.gather(store, NOW - __import__("datetime").timedelta(days=7))}
    assert "t1" not in got and "t2" not in got


def test_email_twins_appear_once_and_the_reviewed_copy_wins(tmp_path):
    store = make_store(tmp_path)
    base = dict(store.data["items"]["a"], source="email", source_name="IFRS Foundation <no-reply@news.ifrs.org>",
                published_at="2026-10-20T00:00:00+00:00", relevance=None, ai_relevance="high", is_baseline=False)
    store.data["items"]["t1"] = dict(base, id="t1", pao_id="iasb", title="IASB Podcast, IFRIC Updates, Agendas",
                                     original_title="IFRS Foundation news alert", relevance="high")
    store.data["items"]["t2"] = dict(base, id="t2", pao_id="issb", title="IFRS Foundation news alert")
    got = {i["id"] for i in brief.gather(store, NOW - __import__("datetime").timedelta(days=7))}
    assert "t1" in got and "t2" not in got


def test_date_window_for_a_picked_range():
    today = datetime(2026, 11, 5).date()
    start, end, days = brief.date_window("2026-10-02", "2026-10-05", today)
    assert (start.isoformat(), end.isoformat(), days) == ("2026-10-02T00:00:00+00:00", "2026-10-06T00:00:00+00:00", 4)
    assert brief.date_window("2026-10-02", None, today)[2] == 1                       # one date = that day
    assert brief.date_window("2026-11-01", "2026-12-31", today)[2] == 5               # future end is cut to today
    for bad in (("2026-10-05", "2026-10-02"), ("2026-11-09", "2026-11-10"), ("2026-01-01", "2026-11-05"), ("nope", "2026-11-05")):
        with pytest.raises(ValueError):
            brief.date_window(*bad, today)


def test_a_past_period_stops_at_its_end_date(tmp_path):
    store = make_store(tmp_path)
    td = __import__("datetime").timedelta
    store.data["items"]["inside"] = dict(store.data["items"]["a"], id="inside", title="Inside the range story alpha",
                                         published_at="2026-10-04T10:00:00+00:00")
    store.data["items"]["after"] = dict(store.data["items"]["a"], id="after", title="After the range story bravo",
                                        published_at="2026-10-06T10:00:00+00:00")
    start, end, _ = brief.date_window("2026-10-02", "2026-10-05", NOW.date())
    got = {i["id"] for i in brief.gather(store, start, end)}
    assert "inside" in got and "after" not in got
    assert "after" in {i["id"] for i in brief.gather(store, start)}                    # no end date: runs to now, as before


def test_build_for_a_picked_range_titles_and_dates_it(tmp_path):
    store = make_store(tmp_path)
    start, end, _ = brief.date_window("2026-10-02", "2026-10-05", NOW.date())

    class NoAI:
        used, log = [], []
        def ask(self, *a, **k):
            raise ai.AIUnavailable("none")

    row = brief.build(store, chain=NoAI(), fetcher=lambda *a, **k: None, window=(start, end))
    assert row["content"].startswith("# 4-day recap\n**2 Oct – 5 Oct 2026**")
    assert row["period_start"].startswith("2026-10-02") and row["period_end"].startswith("2026-10-06")
