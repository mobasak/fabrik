"""/fabrik-flows feedback queue answered in one pass (D-735, D-772).

The commit rule (a ledger carrier now) quotes check_doc_index.py's own error for an untracked doc; the test checks both
halves of that quote are the script's message strings.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_the_index_row_rule_quotes_the_checkers_own_messages() -> None:
    """Row 1790700641. The command's wording is a ledger carrier (commands/_rules/fabrik-flows.yaml)."""
    checker = (ROOT / "scripts" / "enforcement" / "check_doc_index.py").read_text()
    assert "live doc not in INDEX.md: " in checker
    assert "(untracked — the run that creates a doc owes its INDEX row)" in checker


def test_the_tier_claim_is_the_gates_own_registration() -> None:
    """Review round 1: lean registers the check warn_only with --untracked-only; Tier 2 blocks."""
    gate = (ROOT / "scripts" / "final_gate.py").read_text()
    lean = gate[gate.index('"INDEX.md ↔ new docs (untracked, this run)"') :][:200]
    assert '"--untracked-only"' in lean and "warn_only=True" in lean
    full = gate[gate.index('"INDEX.md ↔ docs tree drift"') :][:1200]
    assert "warn_only" not in full.split("results.append")[0]
