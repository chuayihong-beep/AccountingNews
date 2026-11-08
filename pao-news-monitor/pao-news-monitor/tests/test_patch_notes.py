"""Admin > Patch notes must list every CHANGES.md entry."""
from tests.make_patch_notes import CHANGES, OUT, notes, render


def test_reads_date_and_title_from_headings():
    text = "# Changes\n\n## 2026-11-03 — Patch notes on the Admin tab\n- detail\n\n## 2026-11-02 - Older fix\n"
    assert notes(text) == [{"date": "2026-11-03", "title": "Patch notes on the Admin tab"},
                           {"date": "2026-11-02", "title": "Older fix"}]


def test_patch_notes_file_is_up_to_date():
    assert OUT.read_text(encoding="utf-8") == render(CHANGES.read_text(encoding="utf-8")), \
        "CHANGES.md has changed: run  python tests/make_patch_notes.py"
