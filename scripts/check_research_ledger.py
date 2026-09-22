#!/usr/bin/env python3
# AFTER-EDIT: none
"""Refuse a research ledger that leaves a returned fact undispositioned.

A research fan-out returns facts to the lead session only; a fact the lead does not carry into its synthesis leaves
no trace (2026-09-23: 162 facts and cards across two days, 111 of them never dispositioned, one source judged from a
single quoted line). A ledger at ``docs/reference/research/*-ledger.md`` files EVERY returned fact as a table row
``| <id> | <source> | <fact, verbatim> | <url> | <disposition> |`` and this check refuses the commit while any row's
disposition is not one of:

  ``USED → <where it landed>``                       the fact is in the synthesis, and where
  ``DUPLICATE of <id>``                              another row of THIS ledger carries it
  ``REJECTED — read whole: <reason, ≥ 5 words>``     the source was read in full and does not bear on the question
  ``UNREACHABLE — <error>; tried <engines>``         no engine could fetch it

``OPEN`` or an empty cell is refused. COBRA (D-253): the cheapest way to satisfy this without reading is to mark every
row ``REJECTED — read whole`` with a stock reason; the counter is that the reason must be at least five words and the
row stays reviewable in git beside the source URL — a dispositioned-by-stamp ledger is visible to the next reader, and
the rule the dispatcher follows (``CLAUDE.md`` § External Knowledge) makes reading the source the obligation, not the
cell. Exit 0 clean, 1 on any refused row, 2 on usage error.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROW_ID = re.compile(r"^[a-z0-9][a-z0-9.-]*-\d{1,3}$")
USED = re.compile(r"^USED\s*(?:→|->)\s*\S.*$")
DUP = re.compile(r"^DUPLICATE of\s+(\S+)$")
REJ = re.compile(r"^REJECTED\s*[—-]+\s*read whole:\s*(.+)$")
UNR = re.compile(r"^UNREACHABLE\s*[—-]+\s*.+;\s*tried\s+\S.*$")


CELL_SPLIT = re.compile(r"(?<!\\)\|")
SEPARATOR = re.compile(r"^\|(\s*:?-{3,}:?\s*\|)+\s*$")


def _rows(text: str) -> list[list[str]]:
    """Every table row after a header+separator pair is a FACT row — never filtered by its id, because a row the check
    skips is exactly the undispositioned fact it exists to catch (review of 2026-09-23: an uppercase or unnumbered id
    made its row invisible). A literal pipe inside a cell is written `\\|`."""
    rows, lines = [], text.splitlines()
    in_table = False
    for i, line in enumerate(lines):
        if SEPARATOR.match(line.strip()):
            in_table = True
            continue
        if not line.startswith("|"):
            in_table = False
            continue
        if in_table and not (i + 1 < len(lines) and SEPARATOR.match(lines[i + 1].strip())):
            rows.append([c.strip() for c in CELL_SPLIT.split(line.strip().strip("|"))])
    return rows


def check(path: Path) -> list[str]:
    """Every refused row of one ledger, as `path: id: why`."""
    rows = _rows(path.read_text(encoding="utf-8"))
    if not rows:
        return [
            f"{path}: no fact rows — a ledger files every returned fact as `| <id> | … | <disposition> |`"
        ]
    ids = {r[0] for r in rows}
    bad = []
    for r in rows:
        if not ROW_ID.match(r[0]):
            bad.append(
                f"{path}: {r[0] or '(empty id)'}: malformed id — must match `[a-z0-9][a-z0-9.-]*-<1–3 digits>` (lowercase letters, digits, dots, hyphens)"
            )
            continue
        disp = r[-1] if len(r) >= 5 else ""
        if USED.match(disp) or UNR.match(disp):
            continue
        m = DUP.match(disp)
        if m:
            if m.group(1) not in ids or m.group(1) == r[0]:
                bad.append(f"{path}: {r[0]}: DUPLICATE of an id not in this ledger ({m.group(1)})")
            continue
        m = REJ.match(disp)
        if m:
            if len(m.group(1).split()) < 5:
                bad.append(f"{path}: {r[0]}: REJECTED needs a reason of at least five words")
            continue
        bad.append(
            f"{path}: {r[0]}: undispositioned ({disp or 'empty'}) — USED → · DUPLICATE of · "
            "REJECTED — read whole: · UNREACHABLE — …; tried …"
        )
    return bad


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    paths = [Path(a) for a in args] or sorted(Path("docs/reference/research").glob("*-ledger.md"))
    missing = [p for p in paths if not p.is_file()]
    if missing:
        print(
            f"check_research_ledger: no such file: {', '.join(map(str, missing))}", file=sys.stderr
        )
        return 2
    bad = [b for p in paths for b in check(p)]
    for b in bad:
        print(b)
    rows = sum(len(_rows(p.read_text(encoding="utf-8"))) for p in paths)
    print(f"check_research_ledger: {len(bad)} refused of {rows} rows across {len(paths)} ledger(s)")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
