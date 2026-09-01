"""Decision-ledger duplicate-id guard (D-057 sequencing; upstream 01M1CBJWQS).

Concurrent lanes minting max+1 from their own trees collided 4x/day at wef; the check
detects the collision at the gate. The load-bearing property, learned from wef's hand
repair (01M1CW4S): it keys on the ID CELL of a table row and NEVER counts prose
mentions — repos carry 20+ legitimate prose references to ids, including narrative
about past collisions, and a naive matcher reds on all of them.
"""

from pathlib import Path

from scripts.enforcement.check_decisions_unique import find_duplicates


def test_duplicate_id_cells_detected():
    text = (
        "| id | when |\n"
        "|---|---|\n"
        "| D-023 | 2026-08-31 | operator | approve |\n"
        "| D-023 | 2026-08-31 | agent | identity |\n"
        "| D-024 | 2026-08-31 | agent | briefs |\n"
    )
    assert find_duplicates(text) == {"D-023": 2}


def test_prose_mentions_never_count():
    # The collision narrative itself mentions ids — the wef repair kept those
    # lines verbatim on purpose; the matcher must not see them.
    text = (
        "| D-023 | 2026-08-31 | operator | approve |\n"
        "The collision (D-023 · D-023 · D-023) was repaired; supersedes D-023's half.\n"
        "  | D-023 | indented, not a row start |\n"
    )
    assert find_duplicates(text) == {}


def test_clean_ledger_is_silent():
    text = "| D-001 | x |\n| D-002 | y |\n"
    assert find_duplicates(text) == {}


def test_padded_and_bold_id_cells_still_match():
    # Nothing enforces the ledger's cell spacing; a table formatter's padding
    # or a bold id must not become a silent false negative (review finding).
    text = "|  D-003  | padded |\n| **D-003** | bold |\n"
    assert find_duplicates(text) == {"D-003": 2}


def test_warn_lines_carry_the_gate_prefix(tmp_path, monkeypatch, capsys):
    # The visibility contract: bare "WARN:" under advisory=True is INVISIBLE in
    # --json (warnings filters on the ⚠ prefix; advisory_rows on warn_only
    # registration) — the defect this check itself shipped with for one commit.
    import scripts.enforcement.check_decisions_unique as mod

    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "DECISIONS.md").write_text("| D-001 | a |\n| D-001 | b |\n")
    monkeypatch.setattr(mod, "LEDGER", tmp_path / "docs" / "DECISIONS.md")
    assert mod.main() == 0
    out = capsys.readouterr().out
    assert out.count("⚠") >= 2
    assert "WARN:" not in out


def test_gate_registers_the_check_warn_only():
    # warn_only=True is what routes the row into --json's advisory list; a
    # regression to bare advisory=True silently reopens the invisibility.
    gate = (Path(__file__).resolve().parents[2] / "scripts" / "final_gate.py").read_text(
        encoding="utf-8"
    )
    block = gate[gate.index("check_decisions_unique.py") :]
    assert "warn_only=True" in block[:300]
