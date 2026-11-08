"""AI usage log: tokens are noted per answer, saved in one go, and a missing table never breaks a run."""

from collector import ai
from collector.store import JsonStore

from tests.test_brief import FakeHTTP, FakeResp

ENV = {"GITHUB_TOKEN": "t", "AI_MODELS_FAST": "github:m1"}


def with_usage(text, p, c):
    return FakeResp(200, {"choices": [{"message": {"content": text}}], "usage": {"prompt_tokens": p, "completion_tokens": c}})


def test_each_answer_is_noted_with_its_job_and_tokens():
    http = FakeHTTP({"m1": [with_usage("a", 1200, 80), with_usage("b", 3000, 400)]})
    c = ai.Chain(env=ENV, session=http, sleep=lambda s: None)
    c.ask("fast", "s", "u", feature="relevance")
    c.ask("fast", "s", "u")                       # no feature given: falls back to the kind
    assert c.usage == [
        {"feature": "relevance", "model": "github:m1", "prompt_tokens": 1200, "completion_tokens": 80},
        {"feature": "fast", "model": "github:m1", "prompt_tokens": 3000, "completion_tokens": 400},
    ]


def test_answer_without_usage_counts_as_zero_tokens_and_failures_are_not_logged():
    plan = {"m1": [FakeResp(429, text="quota")], "m2": [FakeResp(200, {"choices": [{"message": {"content": "x"}}]})]}
    c = ai.Chain(env={"GITHUB_TOKEN": "t", "AI_MODELS_FAST": "github:m1,github:m2"}, session=FakeHTTP(plan), sleep=lambda s: None)
    c.ask("fast", "s", "u", feature="tagging")
    assert c.usage == [{"feature": "tagging", "model": "github:m2", "prompt_tokens": 0, "completion_tokens": 0}]


def test_flush_saves_once_and_clears(tmp_path):
    store = JsonStore(str(tmp_path / "local.json"))
    c = ai.Chain(env=ENV, session=FakeHTTP({"m1": [with_usage("a", 10, 5)]}), sleep=lambda s: None)
    c.ask("fast", "s", "u", feature="explain")
    c.flush_usage(store)
    c.flush_usage(store)                          # nothing left: no duplicate rows
    assert store.data["ai_usage"] == [{"feature": "explain", "model": "github:m1", "prompt_tokens": 10, "completion_tokens": 5}]
    assert c.usage == []


def test_missing_table_never_breaks_the_run():
    class NoTable:
        def log_ai_usage(self, rows):
            raise RuntimeError('relation "ai_usage" does not exist')

    c = ai.Chain(env=ENV, session=FakeHTTP({"m1": [with_usage("a", 10, 5)]}), sleep=lambda s: None)
    c.ask("fast", "s", "u")
    c.flush_usage(NoTable())                      # must not raise
    assert any("usage log not saved" in line for line in c.log)
