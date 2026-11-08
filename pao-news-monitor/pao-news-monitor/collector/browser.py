"""Real-browser fallback (headless Chrome via Playwright).

Used only for websites that blocked the normal download (error 403 etc.),
didn't answer, or showed no links because they build the page with
JavaScript. Slower, so it runs after everything else, one site at a time.
If Playwright isn't installed, the collector simply skips this step.
"""
import os

from .common import USER_AGENT, log

PAGE_TIMEOUT_MS = 45_000
SETTLE_MS = 6_000


class PageResult:
    """Same shape as common.FetchResult, so websites.py can't tell the difference."""

    def __init__(self, url, status, html):
        self.url, self.status, self.text = url, status, html
        self.content = html.encode("utf-8")
        self.insecure = False


def available():
    try:
        import playwright.sync_api  # noqa: F401
        return True
    except ImportError:
        return False


class Browser:
    def __enter__(self):
        from playwright.sync_api import sync_playwright
        self._pw = sync_playwright().start()
        exe = os.environ.get("PW_CHROMIUM_PATH") or None
        self._browser = self._pw.chromium.launch(executable_path=exe, args=["--disable-blink-features=AutomationControlled"])
        self._ctx = self._browser.new_context(
            user_agent=USER_AGENT, locale="en-US", ignore_https_errors=True,
            viewport={"width": 1366, "height": 900})
        return self

    def __exit__(self, *exc):
        for closer in (self._ctx.close, self._browser.close, self._pw.stop):
            try:
                closer()
            except Exception as e:  # noqa: BLE001
                log.info("browser close: %s", e)

    def fetch(self, url, **_):
        if url.startswith("http://"):
            try:
                r = self._open("https://" + url[7:])
                if r.status < 400:
                    return r
            except Exception:  # noqa: BLE001
                pass
        return self._open(url)

    def _open(self, url):
        page = self._ctx.new_page()
        try:
            resp = page.goto(url, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT_MS)
            try:  # give JavaScript time to fill the page in
                page.wait_for_load_state("networkidle", timeout=SETTLE_MS)
            except Exception:  # noqa: BLE001
                pass
            return PageResult(page.url, resp.status if resp else 200, page.content())
        finally:
            page.close()
