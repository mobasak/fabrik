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

BLOCKING since 2026-09-04, which is the second half of the D-057 sequencing this check landed
under ("WARN-first, after wef's repair reply"). That reply arrived (01M1MDXY6N6DD0CEAZ9M3778AH:
wef3 renumbered its side and relayed the rest to wef1), and the promotion was re-measured before
flipping rather than assumed: **0 duplicate ids across 49 fleet ledgers today**, so blocking reds
no repo at the moment it lands — the same denominator that justified landing it WARN-first, now
re-derived at the moment it decides something. Fire rate that earned the tier: 4 collisions in one
day across two lanes of one repo.
The proposal's other half (WARN when a minted id <= origin/HEAD max) is deliberately absent:
it needs a network fetch and the gate stays offline-fast — pull-before-mint discipline is the
prevention, this is the detection. Repair discipline when it fires: the INBOUND-REFERENCED
side keeps the id, the other side renumbers to fresh ids, references fixed in the same commit
(hub D-057; the wef repair proved BOTH-CITED is common — tiebreak: first-committed keeps).

Exit codes:
    0 — no ledger, or every id unique.
    1 — at least one duplicate id. A duplicate silently breaks every citation of that id
        ("grep DECISIONS.md first" returns two contradictory rows for one key), and it
        survived every gate for as long as this was advisory. Repair, then re-run: the
        INBOUND-REFERENCED side keeps the id, the other renumbers, references fixed in the
        same commit (D-057; tiebreak when both are cited: first-committed keeps).
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

LEDGER = Path("docs/DECISIONS.md")
_ID_CELL = re.compile(r"^\|\s*\**(D-\d+)\**\s*\|")


def find_duplicates(text: str) -> dict[str, int]:
    ids = [m.group(1) for line in text.splitlines() if (m := _ID_CELL.match(line))]
    return {i: n for i, n in Counter(ids).items() if n > 1}


def main() -> int:
    if not LEDGER.exists():
        return 0
    dups = find_duplicates(LEDGER.read_text(encoding="utf-8"))
    for i, n in sorted(dups.items()):
        print(
            f"✗ docs/DECISIONS.md id {i} appears {n}x — rows are addressable by id; "
            f"renumber per the D-057 repair discipline (referenced side keeps; references "
            f"fixed in the same commit)"
        )
    if dups:
        print(
            f"✗ {len(dups)} duplicate decision id(s) — citations of these ids now "
            f"resolve to two rows each"
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
