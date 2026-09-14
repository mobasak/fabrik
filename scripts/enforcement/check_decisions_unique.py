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


# A GFM delimiter is the line immediately BELOW a header row, and every cell is dashes (with
# optional alignment colons). Keying on "the first dash-ish line anywhere" let a two-character
# `| |` — an empty data row — be taken as the delimiter, which silences this check for every row
# below it. Executed: with `| |` above a stray row the check reported nothing; moved below it, the
# stray was found. Direction is a MISS, never a false RED (`next()` takes the first match, so a
# fake delimiter can only appear ABOVE the real one), but a blocking check whose cheapest
# satisfaction is typing two characters is the cobra shape — see the note on the finder below.
_DELIMITER = re.compile(r"^\|(?:\s*:?-{1,}:?\s*\|)+$")
_HEADER_ROW = re.compile(r"^\|(?:[^|]*\|){2,}$")


def find_rows_outside_the_table(text: str) -> list[tuple[int, str]]:
    """`| D-NNN |` rows sitting ABOVE the header delimiter — i.e. outside the table (T12.12).

    This file is a LINE regex by design: it must not red on the dozens of legitimate prose
    mentions of ids a repo carries. The cost of that design is that it has no idea where the table
    IS, so a row placed above the `|---|` delimiter — outside the table, invisible to every
    markdown renderer and to anyone reading the rendered page — counted as a row and was blessed
    (brand-identity-creator's reported shape, 01M295S5G/01M1T1134).

    Uniqueness is not the only thing addressability needs: a row nobody can SEE is not addressable
    either. Reported per-row with its line number; no delimiter at all means no table to be outside
    of, and that is a different defect this check does not claim to own.

    ⚠️ THE CHEAPEST WAY TO SATISFY THIS WITHOUT THE OUTCOME (cobra-effect — you get the behavior you
    measure): type a fake delimiter above the stray row instead of moving the row. The row is then
    "inside a table" that renders as nonsense, and the check goes quiet. The delimiter pattern is
    therefore anchored to a real header row above it, which makes the fake cost as much as the fix
    — but it does not make it impossible, and a reviewer who sees a delimiter appear in the same
    commit as a stray-row fix should read that commit rather than the check's green.
    """
    lines = text.splitlines()
    delim = next(
        (
            i
            for i, ln in enumerate(lines)
            if _DELIMITER.match(ln.strip()) and i and _HEADER_ROW.match(lines[i - 1].strip())
        ),
        None,
    )
    if delim is None:
        return []
    return [(i + 1, m.group(1)) for i, ln in enumerate(lines[:delim]) if (m := _ID_CELL.match(ln))]


def main() -> int:
    if not LEDGER.exists():
        return 0
    text = LEDGER.read_text(encoding="utf-8")
    dups = find_duplicates(text)
    stray = find_rows_outside_the_table(text)
    for lineno, did in stray:
        print(
            f"✗ docs/DECISIONS.md:{lineno} row {did} sits ABOVE the table delimiter — it is "
            "outside the table, so no renderer shows it and no reader finds it. Move it below "
            "the `|---|` line (this is a placement fix, not a content edit: the row's cells are "
            "immutable)"
        )
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
    if stray:
        print(
            f"✗ {len(stray)} decision row(s) outside the table — addressability needs a row to be "
            f"FINDABLE, not only unique"
        )
    return 1 if (dups or stray) else 0


if __name__ == "__main__":
    raise SystemExit(main())
