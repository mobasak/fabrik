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

import json
import os
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import NamedTuple

if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
import _fences  # noqa: E402  (same-dir sibling, synced fleet-wide)

LEDGER = Path("docs/DECISIONS.md")
# A row: a pipe, then an id cell that OPENS with D-<digits> — text after the id inside the cell
# (`| D-12 (amended) |`) is allowed, while `D-1x`, `D-1.5`, `D-1-2` and `D-1/2` are no id
# (W-c25fd20f gap 7). The number is ASCII digits of any length (`\d` also takes non-ASCII digits),
# keyed by `_key` with no `int()` — which refuses a string over 4,300 digits and crashed the run
# before any line printed. Its leading whitespace is read by `_parse`.
_ROW = re.compile(r"^([ \t]*)\|[ \t]*\**(D-([0-9]+))(?![\w./-])")


def _key(digits: str) -> str:
    """The id's number without its leading zeros: `D-1` and `D-001` are one id."""
    return digits.lstrip("0") or "0"


# A table body goes on while a line is indented at most 3 spaces, is not blank, holds a pipe and
# starts no other block — GFM's rule (markdown-it, executed 2026-10-29 over 39 shapes): a row with
# no leading pipe continues the table; a tab or a 4-space indent (an indented code block), a
# heading, a quote, a list item, a fence or an HTML block of CommonMark types 1-6 ends it. Type 7
# (any other tag, `<span>`) cannot interrupt, so it continues the table.
_HTML_BLOCK_TAGS = (
    "address|article|aside|base|basefont|blockquote|body|caption|center|col|colgroup|dd|details|"
    "dialog|dir|div|dl|dt|fieldset|figcaption|figure|footer|form|frame|frameset|h1|h2|h3|h4|h5|h6|"
    "head|header|hr|html|iframe|legend|li|link|main|menu|menuitem|nav|noframes|ol|optgroup|option|"
    "p|param|search|section|summary|table|tbody|td|tfoot|th|thead|title|tr|track|ul"
)
_BLOCK_START = (
    r"#{1,6}(?:[ \t]|$)|>|[-*+](?:[ \t]|$)|[0-9]{1,9}[.)](?:[ \t]|$)|```|~~~"
    r"|<(?:script|pre|style|textarea)(?:[ \t>]|$)|<!--|<\?|<![A-Za-z]|<!\[CDATA\["
    rf"|</?(?:{_HTML_BLOCK_TAGS})(?:[ \t/>]|$)"
)
_BODY = re.compile(rf"^ {{0,3}}(?!{_BLOCK_START})(?=\S).*\|", re.IGNORECASE)
_INDENTED_CODE = re.compile(r"^(?: {4}| {0,3}\t)")


class _Row(NamedTuple):
    lineno: int  # 1-based, in the ledger as written
    did: str  # the id as written: `D-001`
    key: str  # the id's number, `_key`: `D-1` and `D-001` are one id
    in_ledger: bool  # inside the ledger table's body
    counted: bool  # a row the duplicate leg reads: unindented, or in any table body
    line: str


class _Ledger(NamedTuple):
    header: str | None  # the ledger table's header row, None when no table holds a D-row
    header_lineno: int  # 1-based line of that header, 0 with none
    rows: list[_Row]


def _parse(text: str) -> _Ledger:
    """The one population every leg reads (W-c25fd20f).

    CRLF is read as LF (`_fences` admits no `\\r` in a closer, so a CRLF fence was never blanked;
    line numbers do not move). Fenced code blocks are blanked (`_fences.fence_blocks`, backtick
    fences — a row quoted in an example is not a row) unless a block holds a table's header and
    delimiter: an unclosed fence above the ledger pairs with any later fence line, and blanking
    that would silence every leg (fail closed — such a block's rows count). A table is a confirmed
    delimiter (a `_DELIMITER` line directly under a `_HEADER_ROW`, outside any earlier table's
    body) plus the `_BODY` lines below it. THE LEDGER TABLE is the one holding the most D-rows, at
    least one, ties to the LAST (the ledger table closes its file: 293 of the 293 ledgers holding
    one, 2026-10-29, whichever end new rows are written at): keying on the first delimiter let a
    header and delimiter typed above a stray row hide it.

    A D-row-shaped line is read by where it sits: in any table body it is a row (duplicates read
    it); outside every table, unindented it is a row too, indented 1-3 spaces it is prose to the
    duplicate leg (test_prose_mentions_never_count) yet a row nobody sees to the stray leg, and
    indented 4 spaces or a tab it is an indented code block — an example, like a fence. No table
    holding a D-row means no ledger table — the table-reading legs then report nothing, and
    duplicates are still read line by line.

    Measured before it decided anything (2026-10-29, 298 ledgers — the 51 /opt/*/docs/DECISIONS.md
    plus 247 worktree copies; the row count moves as they grow): of the 293 holding a ledger table,
    0 rows outside it; 0 rows in fences, 0 indented, 0 annotated id cells, 0 ids whose number
    repeats under another spelling; every leg's verdict on all 298 is unchanged. The other 5 —
    fabrik-lib's ledger and 4 worktree copies of it — have a header with no delimiter under it, so
    no table: their duplicates are still read, and no row of theirs is ever a stray.
    """
    text = text.replace("\r\n", "\n")
    blank = list(text)
    for block in _fences.fence_blocks(text):
        held = text[block.start : block.end].split("\n")
        if any(
            _DELIMITER.match(ln.strip()) and k and _HEADER_ROW.match(held[k - 1].strip())
            for k, ln in enumerate(held)
        ):
            continue  # this block would swallow a whole table: its rows count (fail closed)
        for i in range(block.start, block.end):
            if blank[i] != "\n":
                blank[i] = " "
    lines = "".join(blank).split("\n")
    tables: list[tuple[int, int, int]] = []  # (delimiter index, body end, D-rows in the body)
    for i, ln in enumerate(lines):
        if tables and i < tables[-1][1]:
            continue  # a delimiter-shaped line inside a body is a row of that table
        if _DELIMITER.match(ln.strip()) and i and _HEADER_ROW.match(lines[i - 1].strip()):
            end = i + 1
            while end < len(lines) and _BODY.match(lines[end]):
                end += 1
            tables.append((i, end, sum(1 for k in range(i + 1, end) if _ROW.match(lines[k]))))
    held = [t for t in tables if t[2]]
    ledger = max(held, key=lambda t: (t[2], t[0])) if held else None
    rows: list[_Row] = []
    for k, ln in enumerate(lines):
        m = _ROW.match(ln)
        if not m:
            continue
        in_table = any(t[0] < k < t[1] for t in tables)
        if not in_table and _INDENTED_CODE.match(ln):
            continue  # an indented code block: an example, like a fence
        inside = ledger is not None and ledger[0] < k < ledger[1]
        counted = in_table or not m.group(1)
        rows.append(_Row(k + 1, m.group(2), _key(m.group(3)), inside, counted, ln))
    return _Ledger(lines[ledger[0] - 1] if ledger else None, ledger[0] if ledger else 0, rows)


def find_duplicates(text: str) -> dict[str, int]:
    first: dict[str, str] = {}  # the first spelling seen names the id
    ids = [first.setdefault(r.key, r.did) for r in _parse(text).rows if r.counted]
    return {i: n for i, n in Counter(ids).items() if n > 1}


# A GFM delimiter is the line immediately BELOW a header row, and every cell is dashes (with
# optional alignment colons). Keying on "the first dash-ish line anywhere" let a two-character
# `| |` — an empty data row — be taken as the delimiter, which silences this check for every row
# below it. Executed: with `| |` above a stray row the check reported nothing; moved below it, the
# stray was found. A blocking check whose cheapest satisfaction is typing two characters is the
# cobra shape — see the note on the finder below, and `_parse` for which table is the ledger's.
_DELIMITER = re.compile(r"^\|(?:\s*:?-{1,}:?\s*\|)+$")
_HEADER_ROW = re.compile(r"^\|(?:[^|]*\|){2,}$")


def find_rows_outside_the_table(text: str) -> list[tuple[int, str]]:
    """`| D-NNN |` rows outside the ledger table — above it, in another table, or after it (T12.12).

    This file is a LINE regex by design: it must not red on the dozens of legitimate prose
    mentions of ids a repo carries. The cost of that design is that it had no idea where the table
    IS, so a row placed outside it — invisible to every markdown renderer and to anyone reading the
    rendered page — counted as a row and was blessed (brand-identity-creator's reported shape,
    01M295S5G/01M1T1134). `_parse` now finds the ledger table and every leg reads its rows.

    Uniqueness is not the only thing addressability needs: a row nobody can SEE is not addressable
    either. Reported per-row with its line number; no table holding a D-row means no table to be
    outside of, and that is a different defect this check does not claim to own.

    ⚠️ THE CHEAPEST WAY TO SATISFY THIS WITHOUT THE OUTCOME (cobra-effect — you get the behavior you
    measure): wrap the stray row in a table of its own instead of moving the row. Keyed on the
    FIRST delimiter, a header and delimiter typed above the stray did exactly that (W-c25fd20f);
    keyed on the table holding the most D-rows, the fake table's rows are reported in turn, unless
    the fake holds MORE rows than the ledger — and then the ledger's own rows red. A table of
    strays therefore no longer goes quiet, and neither does indenting a stray 1-3 spaces (still
    reported). Three moves still do: deleting the row; wrapping the LAST rows of the table in a
    closed ``` fence that holds no header and delimiter; and indenting a stray 4 spaces or a tab
    (an indented code block — an example, like a fence). A fenced or indented row in the middle
    of the table strands the rows below it, which red. A reviewer who sees a row vanish, a fence
    appear or a row gain four spaces in the ledger, in the same commit as a stray-row or duplicate
    fix, should read that commit rather than the green.
    """
    parsed = _parse(text)
    if parsed.header is None:
        return []
    return [(r.lineno, r.did) for r in parsed.rows if not r.in_ledger]


_SHAPE_BASELINE = Path(__file__).resolve().parents[2] / ".fabrik" / "decision-shape-baseline.json"


def _all_row_ids(text: str) -> list[tuple[int, str]]:
    """(lineno, id) for every row of the ledger table — the ledger's actual population."""
    return [(r.lineno, r.did) for r in _parse(text).rows if r.in_ledger]


_WORD = re.compile(r"\w")


def _masked(line: str) -> str:
    """The row with every pipe that is TEXT replaced by NUL: one written `\\|` (both characters
    become one NUL) and one inside a code span (intel 01M4405E: six well-formed rows read as
    malformed because their code spans held `a|b`). The spans are `_fences.blank_code_spans`'s — a
    run of N backticks closes only on a run of exactly N, and an odd backslash run escapes only the
    run's first backtick (CommonMark parity, W-753040b8); the
    one-backtick regex this replaced split D-1159 (a quoted triple-backtick closer) into 4 cells
    (W-27db8c35). tests/test_decisions_table_shape.py counts its bare pipes from this same string.

    STATED COST: spans are found over the WHOLE row, before the split, so a backtick run left
    open in one cell pairs with an equal run in a later cell and hides the pipes between them
    (0 of 2896 D-rows across the 51 /opt/*/docs/DECISIONS.md ledgers changed cell count on
    2026-10-24; pinned by test_a_long_run_pairs_across_cells_by_design).
    """
    blank = _fences.blank_code_spans(line)
    out: list[str] = []
    i = 0
    while i < len(line):
        if line[i] == "\\" and line[i + 1 : i + 2] == "|":
            out.append("\0")
            i += 2
            continue
        out.append("\0" if line[i] == "|" and blank[i] != "|" else line[i])
        i += 1
    return "".join(out)


def _cells(line: str) -> list[str]:
    """The row's cells, split on the bare pipes `_masked` leaves."""
    return [c.replace("\0", "|").strip() for c in _masked(line).strip().strip("|").split("|")]


def malformed_ids(text: str) -> dict[str, str]:
    """``{id: reason}`` for every row whose SHAPE or CONTENT makes it unreadable.

    A row is malformed when its cell count differs from the header, OR when its ``why`` or ``where``
    cell is empty. **Content, not shape alone** — and that is the counter-measure, not a nicety:
    padding a short row to six EMPTY cells is cheaper than repairing it and restores exactly the blank
    the reader cannot use, so a shape-only rule rewards the cheapest wrong move.

    The content test reads the six-column schema's why and where cells, so a header of fewer than
    six cells gets the cell-count test alone (it raised IndexError before the blocking legs could
    print — W-c25fd20f gap 6).
    """
    parsed = _parse(text)
    if parsed.header is None:
        return {}
    width = len(_cells(parsed.header))
    out: dict[str, str] = {}
    for r in parsed.rows:
        if not r.in_ledger:
            continue
        cells = _cells(r.line)
        if len(cells) != width:
            out[r.did] = f"{len(cells)} cells, header has {width}"
        elif width >= 6 and (not _WORD.search(cells[4]) or not _WORD.search(cells[5])):
            # a cell with no word at all (`—`, `-`, `…`) is the one-character padding (addendum)
            out[r.did] = "why/where empty — a padded row answers blank"
    return out


def check_row_shape(text: str) -> None:
    """ADVISORY row-integrity ratchet over the SET of malformed ids. Never touches the exit code.

    ⚠ This check has been BLOCKING since 2026-09-04 for duplicates and stray rows, so this leg must
    print and return nothing: 79 rows across 49 ledgers are malformed today and a blocking day one
    would red every repo at once. Promotion follows the same WARN-first sequencing D-057 documents.

    The baseline stores the SET OF IDS, not a count. An aggregate count is defeated by three moves,
    all built and executed against a baseline of malformed=1 / total=4 — and the cheapest is not the
    obvious one:
      · delete the malformed row                       → count ratchet REFUSES (total also fell)
      · delete it AND record any new decision           → count ratchet PASSES  ✗
      · pad the row to six empty cells (an edit, no
        deletion, total never moves)                    → count ratchet PASSES  ✗  ← cheapest
      · repair it properly                              → both pass             ✓
    Identity refuses all three: an id in the baseline must still be PRESENT and now well-formed.
    """
    now = malformed_ids(text)
    try:
        base = set(json.loads(_SHAPE_BASELINE.read_text(encoding="utf-8"))["malformed_ids"])
    except (OSError, ValueError, KeyError, TypeError):
        print(
            f"⚠ decision-shape: seeding baseline with {len(now)} malformed row(s) — advisory, "
            f"nothing blocked. Write {_SHAPE_BASELINE} with "
            f'{{"malformed_ids": {sorted(now)}}} to arm the ratchet.'
        )
        return
    present = {i for _, i in _all_row_ids(text)}
    unrepaired = sorted(base & set(now))
    regressed = sorted(set(now) - base)
    # ABSENT means gone from the LEDGER, not merely gone from the malformed set — a REPAIRED row
    # leaves the malformed set, which is the success case. Deriving absence from `now` instead of
    # from the ledger reported every repair as a deletion (caught by the fixture pair, not by review).
    gone = sorted(base - present)
    if regressed:
        print(
            f"⚠ decision-shape: {len(regressed)} row(s) became malformed since the baseline: "
            f"{', '.join(regressed)} — the set may only shrink, and only by REPAIR"
        )
    for did in unrepaired:
        print(f"⚠ decision-shape: {did} still malformed — {now[did]}")
    if gone:
        print(
            f"⚠ decision-shape: {len(gone)} baseline row(s) are ABSENT rather than repaired "
            f"({', '.join(gone)}) — a deleted row is not a repair; restore it and fix its cells"
        )
    if not (regressed or unrepaired or gone):
        print(f"decision-shape: OK — {len(base)} baseline row(s) all repaired or absent-by-design")


def _ledger_path() -> Path:
    """`LEDGER` under the cwd when it is there, else at the root of the cwd's git work tree.

    A cwd-relative read alone found no ledger from `docs/` and passed (W-c25fd20f gap 5). The cwd
    is asked FIRST, so every run that found a ledger before reads the same one — a fixture nested in
    another repo keeps its own. Git is asked with the hook variables removed (a hook exports
    GIT_DIR, under which `--show-toplevel` answers the cwd itself); outside a work tree, or when git
    is missing or fails, the cwd answers as before: a pass that was a pass, never an outage. An
    absolute `LEDGER` is used as is."""
    if LEDGER.is_absolute() or LEDGER.exists():
        return LEDGER
    env = {k: v for k, v in os.environ.items() if k not in _GIT_LOCATION_VARS}
    try:
        top = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=30,
            env=env,
        )
    except (OSError, subprocess.SubprocessError):
        return LEDGER
    root = top.stdout.strip()
    return Path(root) / LEDGER if top.returncode == 0 and root else LEDGER


# the variables that move git's idea of the repo away from the cwd; a hook exports the first
_GIT_LOCATION_VARS = ("GIT_DIR", "GIT_WORK_TREE", "GIT_COMMON_DIR")


def main() -> int:
    ledger = _ledger_path()
    if not ledger.exists():
        return 0
    text = ledger.read_text(encoding="utf-8")
    dups = find_duplicates(text)
    stray = find_rows_outside_the_table(text)
    head = _parse(text).header_lineno
    for lineno, did in stray:
        where = (
            "sits ABOVE the table delimiter — it is outside the table"
            if lineno < head
            else "sits outside the ledger table (after it, or in another table)"
        )
        print(
            f"✗ docs/DECISIONS.md:{lineno} row {did} {where}, so no renderer shows it in the ledger "
            "and no reader finds it. Move it into the ledger table's body (this is a placement fix, "
            "not a content edit: the row's cells are immutable)"
        )
    spellings: dict[str, list[str]] = {}
    for r in _parse(text).rows:
        if r.counted and r.did not in spellings.setdefault(r.key, []):
            spellings[r.key].append(r.did)
    for i, n in sorted(dups.items()):
        written = spellings.get(_key(i[2:]), [i])
        also = f" (written {' and '.join(written)})" if len(written) > 1 else ""
        print(
            f"✗ docs/DECISIONS.md id {i} appears {n}x{also} — rows are addressable by id; "
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
    # ADVISORY — prints only, never reaches the exit code; after the blocking lines, so an advisory
    # failure can no longer hide them (W-c25fd20f gap 6)
    check_row_shape(text)
    return 1 if (dups or stray) else 0


if __name__ == "__main__":
    raise SystemExit(main())
