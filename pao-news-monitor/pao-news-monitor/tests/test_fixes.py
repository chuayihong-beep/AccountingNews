"""Tests for fixes after the first live run: https upgrade, loose link matching,
blocked/JS sites handed to a real browser."""
import http.server
import os
import threading

import pytest
import requests

from collector import browser, common, main, websites
from collector.common import PAO, SourceResult
from tests.test_collector import FakeResp, fake_fetch, pao


def test_http_tries_https_first(monkeypatch):
    calls = []

    def fake_get(url, **kw):
        calls.append(url)
        return common.FetchResult(FakeResp(url, "<html>ok</html>"))
    monkeypatch.setattr(common, "_get", fake_get)
    common.fetch("http://www.icai.org")
    assert calls == ["https://www.icai.org"]


def test_http_falls_back_when_https_fails(monkeypatch):
    calls = []

    def fake_get(url, **kw):
        calls.append(url)
        if url.startswith("https"):
            raise requests.exceptions.ConnectTimeout("no")
        return common.FetchResult(FakeResp(url, "<html>ok</html>"))
    monkeypatch.setattr(common, "_get", fake_get)
    assert common.fetch("http://old.example.org").status == 200
    assert calls == ["https://old.example.org", "http://old.example.org"]


SLUG_NEWS = """<html><body><h1>Latest</h1><div class="list">
 <a href="/ican-celebrates-fifty-years-of-service">ICAN celebrates fifty years of service to the profession</a>
 <a href="/council-meeting-outcome-for-members">Outcome of the 312th council meeting for members</a>
 <a href="/our-team">Our team</a>
 <a href="/members">Members area</a>
</div>""" + "<p>filler text</p>" * 200 + "</body></html>"


def test_loose_matching_finds_slug_links(monkeypatch):
    p = pao(id="ican", website="https://ican.org.np", news_url="https://ican.org.np/news")
    monkeypatch.setattr(websites, "fetch", fake_fetch({"https://ican.org.np/news": SLUG_NEWS, "https://ican.org.np": "<html><body>" + "x " * 600 + "</body></html>"}))
    res = websites.collect(p)
    titles = sorted(i.title for i in res.items)
    assert titles == ["ICAN celebrates fifty years of service to the profession",
                      "Outcome of the 312th council meeting for members"]
    assert "loose" in res.message and not res.needs_browser


def test_blocked_site_flags_browser(monkeypatch):
    monkeypatch.setattr(websites, "fetch", lambda url, **kw: common.FetchResult(FakeResp(url, "denied", 403)))
    res = websites.collect(pao())
    assert not res.ok and res.needs_browser and res.message == "Blocks crawlers (error 403)"


def test_unreachable_site_flags_browser(monkeypatch):
    def boom(url, **kw):
        raise requests.exceptions.ConnectTimeout("timed out")
    monkeypatch.setattr(websites, "fetch", boom)
    res = websites.collect(pao())
    assert not res.ok and res.needs_browser and "not reachable" in res.message


def test_empty_js_page_flags_browser(monkeypatch):
    monkeypatch.setattr(websites, "fetch", fake_fetch({"https://www.icai.org": "<html><body><div id=app></div><script>x()</script></body></html>"}))
    res = websites.collect(pao())
    assert res.needs_browser and "JavaScript" in res.message


def test_retry_keeps_old_result_when_browser_finds_nothing(monkeypatch):
    class FakeBrowser:
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def fetch(self, url, **kw): return browser.PageResult(url, 403, "denied")
    monkeypatch.setattr(browser, "available", lambda: True)
    monkeypatch.setattr(browser, "Browser", FakeBrowser)
    r = SourceResult("icai", "website", ok=False, message="Blocks crawlers (error 403)", needs_browser=True)
    results = [r]
    main.retry_in_browser(results, {"icai": pao()})
    assert results[0] is r
    assert r.message == "Blocks crawlers (error 403), even a real browser. Google News still covers it."


# ---- real headless browser against a local test site ----

JS_SITE = """<html><head><title>JS site</title></head><body><div id="news"></div>
<script>
document.getElementById('news').innerHTML =
  '<ul><li><a href="/news/2026/new-president-installed">New President installed at annual general meeting</a> 2026-09-30</li>' +
  '<li><a href="/news/2026/exam-results">Professional examination results for September 2026</a></li></ul>';
</script></body></html>"""


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        ua = self.headers.get("User-Agent", "")
        # pretend to be a site that blocks non-browsers: requests has no "sec-ch-ua" header
        if "HeadlessChrome" not in ua and not self.headers.get("sec-ch-ua"):
            self.send_response(403); self.end_headers(); self.wfile.write(b"denied"); return
        self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8"); self.end_headers()
        self.wfile.write(JS_SITE.encode())

    def log_message(self, *a):
        pass


def _chromium():
    for path in ("/opt/pw-browsers/chromium_headless_shell-1194/chrome-linux/headless_shell",):
        if os.path.exists(path):
            return path
    return os.environ.get("PW_CHROMIUM_PATH")


@pytest.mark.skipif(not browser.available(), reason="playwright not installed")
def test_real_browser_reads_blocked_js_site(monkeypatch):
    exe = _chromium()
    if exe:
        monkeypatch.setenv("PW_CHROMIUM_PATH", exe)
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    site = f"http://127.0.0.1:{srv.server_port}"
    p = pao(id="testpao", website=site)
    try:
        first = websites.collect(p)                     # plain download: blocked
        assert first.needs_browser and "403" in first.message
        results = [first]
        main.retry_in_browser(results, {"testpao": p})  # real browser: JS runs, links appear
    finally:
        srv.shutdown()
    got = results[0]
    assert got.ok and "real browser" in got.message.lower()
    assert sorted(i.title for i in got.items) == [
        "New President installed at annual general meeting",
        "Professional examination results for September 2026"]
