"""docs/DECISIONS.md is a GFM table read by humans and by `scripts/decisions.py`: a bare `|` in a
cell (D-099, "user-test | service-test", 2026-09-03) splits the row and misaligns every column
after it. Every `D-` row must carry no MORE than the separator's pipe count once escaped pipes and
code spans are removed (a short row renders blank cells and is only reported) (review 2026-09-02-external-services-chain, pass 56)."""

from __future__ import annotations

import re
from pathlib import Path

LEDGER = Path(__file__).resolve().parents[1] / "docs" / "DECISIONS.md"


def _bare_pipes(line: str) -> int:
    return re.sub(r"`[^`]*`", "", line.replace("\\|", "")).count("|")


def test_every_decision_row_has_the_separator_column_count():
    lines = LEDGER.read_text(encoding="utf-8").splitlines()
    separator = next(ln for ln in lines if ln.startswith("|---"))
    want = separator.count("|")
    rows = [ln for ln in lines if ln.startswith("| D-")]
    assert rows, "no decision rows found"
    extra = [(ln[:40], _bare_pipes(ln)) for ln in rows if _bare_pipes(ln) > want]
    short = [(ln[:40], _bare_pipes(ln)) for ln in rows if _bare_pipes(ln) < want]
    # a bare pipe SHIFTS every later column (the table-corrupting class); a short row only
    # renders blank cells — reported in the message, never a red on its own
    assert not extra, (
        f"{len(extra)} of {len(rows)} rows carry a bare pipe (want {want}): {extra}; short rows: {short}"
    )
