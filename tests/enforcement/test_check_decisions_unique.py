"""Decision-ledger duplicate-id guard (D-057 sequencing; upstream 01M1CBJWQS).

Concurrent lanes minting max+1 from their own trees collided 4x/day at wef; the check
detects the collision at the gate. The load-bearing property, learned from wef's hand
repair (01M1CW4S): it keys on the ID CELL of a table row and NEVER counts prose
mentions — repos carry 20+ legitimate prose references to ids, including narrative
about past collisions, and a naive matcher reds on all of them.
"""

from pathlib import Path

from scripts.enforcement.check_decisions_unique import find_duplicates, main


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


def test_failure_lines_carry_the_gate_prefix(tmp_path, monkeypatch, capsys):
    # The visibility contract, now at the BLOCKING tier (promoted 2026-09-04, the second half of
    # the D-057 sequencing): failure lines carry ✗ so they reach --json's failures. The original
    # defect this pins is unchanged in shape — a bare "WARN:"/unprefixed line is JSON-invisible.
    import scripts.enforcement.check_decisions_unique as mod

    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "DECISIONS.md").write_text("| D-001 | a |\n| D-001 | b |\n")
    monkeypatch.setattr(mod, "LEDGER", tmp_path / "docs" / "DECISIONS.md")
    assert mod.main() == 1
    out = capsys.readouterr().out
    assert out.count("✗") >= 2
    assert "WARN:" not in out and "⚠" not in out


def test_gate_registers_the_check_as_blocking():
    # Promoted from warn_only on 2026-09-04 after wef's repair reply landed and the fleet was
    # re-measured (0 duplicates in 49 ledgers, so blocking reds no repo). A regression to
    # warn_only reopens the hole the finding named: a duplicate id survives every gate.
    gate = (Path(__file__).resolve().parents[2] / "scripts" / "final_gate.py").read_text(
        encoding="utf-8"
    )
    block = gate[gate.index("check_decisions_unique.py") :]
    assert "warn_only" not in block[:300], "the duplicate-id check blocks; it does not advise"


def test_a_duplicate_id_now_reds_the_gate_not_just_warns(tmp_path, monkeypatch):
    """This landed WARN-first per the D-057 sequencing, explicitly "after wef's repair reply". That
    reply arrived (01M1MDXY6N6DD0CEAZ9M3778AH) and the promotion was re-measured before flipping:
    0 duplicate ids across 49 fleet ledgers, so blocking reds no repo at landing. A duplicate id
    breaks every citation of it, and while this was advisory it survived every gate."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "docs").mkdir()
    led = tmp_path / "docs" / "DECISIONS.md"

    led.write_text("| D-001 | a |\n| D-002 | b |\n", encoding="utf-8")
    assert main() == 0, "unique ids stay green"

    led.write_text("| D-001 | a |\n| D-002 | b |\n| D-002 | c |\n", encoding="utf-8")
    assert main() == 1, "a duplicate id must RED the gate, not merely warn"

    led.write_text(
        "| D-001 | a |\n\nSee D-001 and D-001 again in this narrative about D-001.\n",
        encoding="utf-8",
    )
    assert main() == 0, "prose occurrences are not id cells — the wef repair report's own lesson"

    led.unlink()
    assert main() == 0, "no ledger is not a failure"
