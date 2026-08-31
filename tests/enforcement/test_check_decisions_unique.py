"""Decision-ledger duplicate-id guard (D-057 sequencing; upstream 01M1CBJWQS).

Concurrent lanes minting max+1 from their own trees collided 4x/day at wef; the check
detects the collision at the gate. The load-bearing property, learned from wef's hand
repair (01M1CW4S): it keys on the ID CELL of a table row and NEVER counts prose
mentions — repos carry 20+ legitimate prose references to ids, including narrative
about past collisions, and a naive matcher reds on all of them.
"""

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
