"""docs/DECISIONS.md is a GFM table read by humans and by `scripts/decisions.py`: a bare `|` in a
cell (D-099, "user-test | service-test", 2026-09-03) splits the row and misaligns every column
after it. Every `D-` row must carry EXACTLY the separator's pipe count once escaped pipes and code
spans are removed: an extra pipe shifts every later column, and a short row drops its why/where
(review 2026-09-02-external-services-chain, pass 56; short rows red since e777836d1, 2026-09-03).
A short row is repaired from its own text — its folded why/where MOVED into their own cells, or,
where none can move, a verbatim excerpt of the same row copied in — never by padding with an empty
or bare "—" cell (D-561, W-61380819)."""

from __future__ import annotations

import re
from pathlib import Path

LEDGER = Path(__file__).resolve().parents[1] / "docs" / "DECISIONS.md"


def _bare_pipes(line: str) -> int:
    return re.sub(r"`[^`]*`", "", line.replace("\\|", "")).count("|")


def test_every_decision_row_has_the_separator_column_count():
    lines = LEDGER.read_text(encoding="utf-8").splitlines()
    header_i = next(
        i for i, ln in enumerate(lines) if ln.startswith("| id ") or ln.startswith("| ID ")
    )
    separator = lines[
        header_i + 1
    ]  # the LEDGER's separator, never the first table's in the file (L-C11)
    assert separator.startswith("|-") or separator.startswith("| -"), separator
    want = separator.count("|")
    rows = [ln for ln in lines if ln.startswith("| D-")]
    assert rows, "no decision rows found"
    extra = [(ln[:40], _bare_pipes(ln)) for ln in rows if _bare_pipes(ln) > want]
    short = [(ln[:40], _bare_pipes(ln)) for ln in rows if _bare_pipes(ln) < want]
    # A bare pipe SHIFTS every later column; a SHORT row silently drops the why/where a reader
    # needs (D-096, 2026-09-03: 4 cells against the separator's 6 — the why and where were written
    # INSIDE the what cell, so no reader saw them as columns and no check said so). Both are red as
    # of 2026-09-03: measured 1 short row in 107 at the moment the bar moved, so the check fires on
    # a real defect and on nothing else.
    assert not extra, f"{len(extra)} of {len(rows)} rows carry a bare pipe (want {want}): {extra}"
    assert not short, (
        f"{len(short)} of {len(rows)} rows are SHORT (want {want} pipes — the why/where columns "
        f"render blank): {short}"
    )
