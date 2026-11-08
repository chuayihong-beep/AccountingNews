"""update-17: PAO background profiles. The SQL names PAOs by id; a typo would silently update zero rows,
so check every id exists in paos.csv, the file is safe to re-run, and Ask AI actually reads the new columns."""
import re
from pathlib import Path

from collector.common import load_paos

ROOT = Path(__file__).resolve().parent.parent
SQL = (ROOT / "supabase" / "update-17.sql").read_text()
ASK = (ROOT / "supabase" / "functions" / "ask-ai" / "index.ts").read_text()


def test_every_profiled_pao_exists():
    ids = set(re.findall(r"where id = '([^']+)'", SQL))
    assert len(ids) == 31 and {"cpa-australia", "ca-sri-lanka", "fica", "iaasb", "safa"} <= ids
    assert ids <= {p.id for p in load_paos()}


def test_sql_is_safe_to_run_twice():
    assert "add column if not exists profile " in SQL and "add column if not exists profile_checked" in SQL
    assert "drop " not in SQL.lower() and "delete " not in SQL.lower()


def test_every_card_has_sources_and_a_checked_date():
    cards = re.findall(r"\$card\$(.*?)\$card\$", SQL, flags=re.S)
    assert len(cards) == 31
    for c in cards:
        assert "SOURCES:" in c and "NOT KNOWN:" in c
    assert SQL.count("profile_checked = date '2026-10-30'") == 31


def test_staff_provided_fact_is_labelled_as_such():
    assert "Priya Terumalay" in SQL and "per CAPA staff" in SQL


def test_ask_ai_reads_and_labels_the_profile():
    assert "profile,profile_checked" in ASK and "profileBlock(pao!)" in ASK
    assert '"(background on file)"' in ASK or "(background on file)" in ASK


def test_fica_has_the_2026_president():
    assert "Ravinesh Singh became President" in SQL


def test_capa_background_reaches_ask_ai_but_not_tagging():
    from collector import capa_context
    assert "Jhun Yong-Sok" in capa_context.COLLABORATION_GUIDELINES
    assert "Jhun Yong-Sok" not in capa_context.CAPA_PROFILE          # tagging prompt stays short
    assert "Jhun Yong-Sok" in (ROOT / "supabase" / "functions" / "ask-ai" / "capa_context.ts").read_text()
