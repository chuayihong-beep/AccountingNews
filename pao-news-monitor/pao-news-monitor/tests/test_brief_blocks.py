"""The Edit screen's story cards (web/brief-blocks.js) must read and write the exact Markdown the brief is stored as.
Runs the real JavaScript with Node; skipped where Node isn't installed."""
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pytest

from collector import brief

JS = Path(__file__).resolve().parent.parent / "web" / "brief-blocks.js"
pytestmark = pytest.mark.skipif(not shutil.which("node"), reason="Node.js not installed")


def run_js(body, **data):
    script = f"const B = require({json.dumps(str(JS))}); const D = {json.dumps(data)}; {body}"
    out = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=30)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


PAOS = {"icai": {"id": "icai", "abbr": "ICAI", "name": "ICAI"}, "kicpa": {"id": "kicpa", "abbr": "KICPA", "name": "KICPA"}}


def item(i, pao, title, **kw):
    return {"id": i, "pao_id": pao, "title": title, "url": f"https://x.org/{i}", "published_at": "2026-11-05T01:00:00+00:00",
            "source": "website", **kw}


def recap(lead, other, mid, quiet=()):
    start = datetime(2026, 11, 5, tzinfo=timezone.utc)
    return brief.compose("Daily recap", start, datetime(2026, 11, 6, tzinfo=timezone.utc), lead,
                         {i["id"]: f"Summary of {i['title']}." for i in lead}, other, mid, quiet, PAOS, "Draft written by AI - please review.")


def test_cards_round_trip_exactly():
    a, b, c, d = (item("a", "icai", "ICAI AI toolkit"), item("b", "kicpa", "Korea cuts CPA intake (again)"),
                  item("c", "icai", "Third story with a - dash"), item("d", "kicpa", "Fourth"))
    samples = [recap([a, b], [c], [d], [PAOS["kicpa"]]), recap([a], [], [d]), recap([], [], []), recap([a, b], [c, d], [])]
    got = run_js("console.log(JSON.stringify(D.s.map(m => B.serialize(B.parse(m)) === m)))", s=samples)
    assert got == [True] * len(samples)


def test_edits_write_back_in_the_stored_format():
    a, b, c = item("a", "icai", "ICAI AI toolkit"), item("b", "kicpa", "Korea cuts CPA intake"), item("c", "icai", "Third")
    md = recap([a], [b], [c])
    out = run_js("""
      const m = B.parse(D.md);
      m.title = 'Brief for 2 - 5 Nov';                                   // retitle
      m.hl[0].text = 'A new\\nsummary [with brackets].';                  // summary: one line, no brackets
      m.medium.push(B.toListItem(B.parse(D.md).hl[0]));                  // highlight demoted into a list
      m.other.unshift({title: 'Added by hand', url: 'https://y.org/z (1)', details: 'CAPA'});
      m.hl.push({title: '', url: '', meta: '', text: ''});               // a blank card is dropped
      console.log(JSON.stringify({md: B.serialize(m), back: B.parse(B.serialize(m))}))""", md=md)
    text, back = out["md"], out["back"]
    assert text.startswith("# Brief for 2 - 5 Nov\n")
    assert "A new summary (with brackets)." in text and "[with" not in text
    assert "- [Added by hand](https://y.org/z%20%281%29) · CAPA" in text
    assert "- [ICAI AI toolkit](https://x.org/a) · ICAI · 5 Nov 2026" in text.split("## Medium")[1]
    assert [s["title"] for s in back["hl"]] == ["ICAI AI toolkit"] and len(back["other"]) == 2
    assert "> Draft written by AI - please review." in text                  # the staff note is kept
    # and the page itself still reads it as a recap
    assert "## Highlights" in text and text.endswith("\n")


def test_unknown_text_is_kept_not_lost():
    md = ("# Daily recap\n**5 Nov 2026**\n\n> note\n\n## Highlights\nNothing stood out in this period.\n\n## Other high\n"
          "- [A](https://x.org/a) · ICAI\nA stray line staff typed\n\n## Medium\nNone this time.\n\n## Staff section\nKeep me\n")
    out = run_js("console.log(JSON.stringify(B.serialize(B.parse(D.md))))", md=md)
    assert "A stray line staff typed" in out and "## Staff section\nKeep me" in out


def test_older_briefs_are_not_cards():
    assert run_js("console.log(JSON.stringify(B.parse(D.md)))", md="# Weekly brief\nSome text [1]\n") is None


def test_tracker_item_becomes_a_story():
    out = run_js("console.log(JSON.stringify(B.fromItem(D.i, 'KICPA')))",
                 i={"title": "  Korea cuts   CPA intake ", "url": "https://x.org/k", "published_at": "2026-11-05T01:00:00Z", "language": "ko", "ai_summary": "Korea plans to cut the CPA intake."})
    assert out["title"] == "Korea plans to cut the CPA intake."          # non-English: the English summary, like the brief does
    assert out["details"] == "KICPA · 5 Nov 2026" and out["url"] == "https://x.org/k"
