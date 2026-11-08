"""Builds web/patch-notes.json (Admin > Patch notes) from the headings in CHANGES.md.
Run after adding a CHANGES.md entry: python tests/make_patch_notes.py"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent          # pao-news-monitor/pao-news-monitor
CHANGES = ROOT.parent.parent / "CHANGES.md"
OUT = ROOT / "web" / "patch-notes.json"
HEADING = re.compile(r"^## (\d{4}-\d{2}-\d{2})\s+[—-]+\s+(.+?)\s*$")


def notes(text):
    """[{date, title}] newest first, in CHANGES.md order."""
    out = []
    for line in text.splitlines():
        m = HEADING.match(line)
        if m:
            out.append({"date": m.group(1), "title": m.group(2)})
    return out


def render(text):
    return json.dumps(notes(text), ensure_ascii=False, indent=1) + "\n"


if __name__ == "__main__":
    OUT.write_text(render(CHANGES.read_text(encoding="utf-8")), encoding="utf-8")
    print(f"wrote {OUT} ({len(notes(CHANGES.read_text(encoding='utf-8')))} changes)")
