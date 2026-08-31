#!/usr/bin/env python3
# AFTER-EDIT: none
"""Duplicate decision-id guard for docs/DECISIONS.md (upstream 01M1CBJWQS, D-057 sequencing).

Concurrent lanes each derive "max+1" from their own working tree, so two lanes minting within
one push window collide — measured 4 collisions/day under 3 lanes at web-ecommerce-factory,
and the ledger's whole contract is addressability: two rows sharing one id silently break
every citation ("grep DECISIONS.md first" returns contradictory rows for one key).

Keyed on the ID CELL of a table row (``^| D-NNN |``) — NEVER any prose occurrence: repos carry
dozens of legitimate prose mentions of ids, including narrative ABOUT past collisions, and a
naive matcher reds on all of them (wef repair report 01M1CW4S named this from experience).

WARN-tier at landing per the D-057 sequencing (lands WARN-first, after wef's repair reply);
fleet fire rate at landing: 0 duplicates in 49 ledgers, so this cannot red any repo today.
The proposal's other half (WARN when a minted id <= origin/HEAD max) is deliberately absent:
it needs a network fetch and the gate stays offline-fast — pull-before-mint discipline is the
prevention, this is the detection. Repair discipline when it fires: the INBOUND-REFERENCED
side keeps the id, the other side renumbers to fresh ids, references fixed in the same commit
(hub D-057; the wef repair proved BOTH-CITED is common — tiebreak: first-committed keeps).

Exit codes:
    0 always (advisory) — prints WARN lines when duplicates exist.
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

LEDGER = Path("docs/DECISIONS.md")
_ID_CELL = re.compile(r"^\| (D-\d+) \|")


def find_duplicates(text: str) -> dict[str, int]:
    ids = [m.group(1) for line in text.splitlines() if (m := _ID_CELL.match(line))]
    return {i: n for i, n in Counter(ids).items() if n > 1}


def main() -> int:
    if not LEDGER.exists():
        return 0
    dups = find_duplicates(LEDGER.read_text(encoding="utf-8"))
    for i, n in sorted(dups.items()):
        print(
            f"WARN: docs/DECISIONS.md id {i} appears {n}x — rows are addressable by id; "
            f"renumber per the D-057 repair discipline (referenced side keeps; references "
            f"fixed in the same commit)"
        )
    if dups:
        print(
            f"WARN: {len(dups)} duplicate decision id(s) — citations of these ids now "
            f"resolve to two rows each"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
