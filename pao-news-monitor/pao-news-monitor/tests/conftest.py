"""Tests never wait on real clocks: Google News requests are not spaced out or retried slowly."""
import pytest

from collector import news_search


@pytest.fixture(autouse=True)
def fast_google_gate(monkeypatch):
    monkeypatch.setattr(news_search, "GATE", news_search.GoogleGate(gap=0, backoff=(0, 0), sleep=lambda s: None))
