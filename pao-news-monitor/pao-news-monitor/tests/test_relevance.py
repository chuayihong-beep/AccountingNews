"""AI-suggested relevance: labels new items, keeps staff decisions separate, feeds the brief."""
import json
from datetime import datetime, timezone

from collector import brief, relevance
from collector.store import JsonStore

NOW = datetime(2026, 10, 26, 0, 0, tzinfo=timezone.utc)


class FakeChain:
    def __init__(self, answers):
        self.answers, self.calls = list(answers), []

    def chain(self, kind):
        return [("fake:model", "u", "k", "model")]

    def ask(self, kind, system, user, **kw):
        self.calls.append((system, user))
        return self.answers.pop(0), "fake:model"


def store_with(tmp_path, items):
    s = JsonStore(tmp_path / "local.json")
    s.data["paos"] = {"ifrs": {"id": "ifrs", "abbr": "IFRS", "name": "IFRS Foundation", "jurisdiction": "International", "grp": "Stakeholder"},
                      "icai": {"id": "icai", "abbr": "ICAI", "name": "Institute of Chartered Accountants of India", "jurisdiction": "India", "grp": "Member"}}
    for it in items:
        s.data["items"][it["id"]] = {"source": "website", "is_baseline": False, "first_seen_at": "2026-10-22T00:00:00+00:00",
                                     "published_at": "2026-10-22T00:00:00+00:00", "relevance": None, **it}
    return s


def test_labels_new_items_and_skips_reviewed_and_baseline(tmp_path):
    s = store_with(tmp_path, [
        {"id": "a", "pao_id": "ifrs", "title": "ISSB consults on its proposals for nature-related disclosures", "kind": "comment"},
        {"id": "b", "pao_id": "icai", "title": "CA Final exam results declared"},
        {"id": "c", "pao_id": "icai", "title": "Already tagged by staff", "relevance": "medium"},
        {"id": "d", "pao_id": "icai", "title": "Old first-scan link", "is_baseline": True},
        {"id": "e", "pao_id": "icai", "title": "Found long ago", "first_seen_at": "2026-09-01T00:00:00+00:00"},
    ])
    chain = FakeChain([json.dumps([
        {"n": 1, "relevance": "high", "reason": "Open ISSB consultation affecting PAOs region-wide."},
        {"n": 2, "relevance": "Low", "reason": "Routine exam results."}])])
    msg = relevance.suggest(s, chain=chain, now=NOW)
    items = s.data["items"]
    assert items["a"]["ai_relevance"] == "high" and "ISSB" in items["a"]["ai_relevance_reason"]
    assert items["b"]["ai_relevance"] == "low" and items["b"]["ai_relevance_model"] == "fake:model"
    assert "ai_relevance" not in items["c"] and "ai_relevance" not in items["d"] and "ai_relevance" not in items["e"]
    assert items["c"]["relevance"] == "medium"          # staff decision untouched
    assert "labelled 2" in msg and "1 high" in msg and "1 low" in msg
    system, user = chain.calls[0]
    assert "Examinations" in system and "webinars" in system and "IFRS: IFRS Foundation" in system
    assert "opportunity to comment" in user and "[IFRS | website" in user
    # next run: nothing left
    assert relevance.suggest(s, chain=FakeChain([]), now=NOW) == "AI relevance: nothing new to label"


def test_bad_answers_and_missing_column_never_break_the_run(tmp_path):
    s = store_with(tmp_path, [{"id": "a", "pao_id": "ifrs", "title": "Something"}])
    msg = relevance.suggest(s, chain=FakeChain(["not json at all"]), now=NOW)
    assert "labelled 0" in msg and "1 left" in msg and "ai_relevance" not in s.data["items"]["a"]

    class OldDb:
        def items_needing_relevance(self, *a):
            raise RuntimeError('Supabase GET /items failed 400: column items.ai_relevance does not exist')
    assert "update-14" in relevance.suggest(OldDb(), chain=FakeChain([]), now=NOW)


def test_brief_uses_staff_label_else_ai_suggestion(tmp_path):
    s = store_with(tmp_path, [
        {"id": "a", "pao_id": "ifrs", "title": "AI says high", "ai_relevance": "high"},
        {"id": "b", "pao_id": "icai", "title": "AI says low", "ai_relevance": "low"},
        {"id": "c", "pao_id": "icai", "title": "AI says none but staff say medium", "ai_relevance": "none", "relevance": "medium"},
        {"id": "d", "pao_id": "icai", "title": "AI says high but staff say low", "ai_relevance": "high", "relevance": "low"},
    ])
    got = {i["id"] for i in brief.gather(s, datetime(2026, 10, 19, tzinfo=timezone.utc))}
    assert got == {"a", "c"}
    assert brief.tier(s.data["items"]["a"]) == "high" and brief.tier(s.data["items"]["c"]) == "medium"
