"""Guards for the accessibility fixes in web/ (the full axe-core audit is run by hand; these stop the easy regressions)."""
import re
from pathlib import Path

WEB = Path(__file__).resolve().parent.parent / "web"
HTML = (WEB / "index.html").read_text(encoding="utf-8")
CSS = (WEB / "style.css").read_text(encoding="utf-8")


def test_page_has_one_main_landmark_and_one_h1():
    app = HTML[HTML.index('<div id="app"'):]          # the sign-in screen has its own h1; only one screen shows at a time
    assert len(re.findall(r"<main\b", HTML)) == 1 and len(re.findall(r"<h1\b", app)) == 1
    assert "<aside" not in HTML          # a sidebar nested in <main> is flagged; the brief list is a plain panel


def test_table_headers_are_never_empty():
    for name in ("manage.js", "app.js", "index.html"):
        assert "<th></th>" not in (WEB / name).read_text(encoding="utf-8"), name


def test_role_pickers_have_names():
    assert 'data-role-for="${esc(p.email)}" aria-label=' in (WEB / "manage.js").read_text(encoding="utf-8")


def test_amber_text_uses_the_dark_ink():
    """#b7791f on the pale amber background is only 3.2:1; text must use --warn-ink (5.3:1)."""
    for line in CSS.splitlines():
        if re.search(r"(^|[;{ ])color: var\(--warn\)", line):
            raise AssertionError(f"amber text must use var(--warn-ink): {line.strip()}")


def test_controls_are_finger_sized_on_phones():
    assert re.search(r"@media \(pointer: coarse\), \(max-width: 640px\)[^}]*min-height: 40px", CSS, re.S)
