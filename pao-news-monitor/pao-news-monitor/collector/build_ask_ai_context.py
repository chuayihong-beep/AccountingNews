"""Regenerates supabase/functions/ask-ai/capa_context.ts from capa_context.py, so the
guidelines text is edited in one place. Run this, then `supabase functions deploy ask-ai`,
whenever capa_context.py changes.

    python -m collector.build_ask_ai_context
"""
import json
from pathlib import Path

from .capa_context import COLLABORATION_GUIDELINES
from .common import ROOT

OUT = ROOT / "supabase" / "functions" / "ask-ai" / "capa_context.ts"


def main():
    OUT.write_text(
        "// Generated from collector/capa_context.py - do not edit directly.\n"
        "// To change this text: edit capa_context.py, then run\n"
        "//   python -m collector.build_ask_ai_context\n"
        "// and redeploy: supabase functions deploy ask-ai\n\n"
        f"export const COLLABORATION_GUIDELINES = {json.dumps(COLLABORATION_GUIDELINES)};\n",
        encoding="utf-8",
    )
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
