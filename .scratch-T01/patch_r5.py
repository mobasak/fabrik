import pathlib

P = pathlib.Path("scripts/enforcement/check_review_coverage.py")
s = P.read_text(encoding="utf-8")


def sub(old, new, label):
    global s
    n = s.count(old)
    assert n == 1, f"{label}: {n} hits"
    s = s.replace(old, new)
    print(label, "applied")


sub(
    '''_PASS_HEAD_TOK = re.compile(r"(?<![\\w-])\\**Pass\\s*\\d", re.I)''',
    '''_PASS_HEAD_TOK = re.compile(r"(?<![\\w-])\\**Pass\\s*\\d", re.I)
# A head CELL — a cell whose WHOLE content is the head, which is what a real row STARTS with.
# `Pass 3: found: 7 issues remain` narrated inside a method cell is prose, not a row start.
_HEAD_CELL = re.compile(r"\\**Pass\\s*\\d+[a-z]?\\**", re.I)
# The counters, counted LOOSELY for "how many rows are on this line" — `found: 5 issues` IS a
# counter for that question even though `_FOUND_TOK` rightly refuses to READ it. Keying detection
# on the strict token alone was a fail-OPEN: one word-trailed counter made a genuinely joined line
# invisible and the receipt graded quiet off its SECOND half.
_LOOSE_FOUND = re.compile(r"(?<![\\w-])found:\\s*\\d")
_LOOSE_FIXED = re.compile(r"(?<![\\w-])fixed:\\s*\\d")


def _cells(line: str) -> list[str]:
    """The row's CELLS — `|`-split, with the fragments outside the outer pipes dropped (GFM lets
    the closing pipe go). Empty for a line that is not written in cells."""
    body = _ROW_LEAD.sub("", line, count=1).strip()
    if not body.startswith("|"):
        return []
    parts = body.split("|")
    return parts[1:-1] if body.endswith("|") else parts[1:]''',
    "structural-toks",
)

sub(
    '''    covered (a Pass-headed pair, and a cell-anchored pair with no head at all), on the
    list-marker-stripped text so a bulleted row is read like a bare one. A row that both NAMES
    another round and cites its counter (`| Pass 4 | … | re-ran as Pass 3 | found: 3 |`) is
    refused as joined — the adjudicated fail-CLOSED choice: it is indistinguishable from a real
    join, and fencing the citation is a one-keystroke repair while a missed join grades a
    receipt quiet off its own first half.
    """
    body = _ROW_LEAD.sub("", line, count=1)
    if len(_PASS_HEAD_TOK.findall(body)) >= 2 and len(_FOUND_TOK.findall(body)) >= 2:
        return True
    return len(_CELL_FOUND.findall(body)) >= 2''',
    '''    Detected on the ROW STRUCTURE, because a join duplicates a STRUCTURE — never on the counter
    tokens alone, which reads prose that merely QUOTES a counter as a second row. Four arms, each
    an unambiguous signature of a shape the others miss:
      * two HEAD CELLS (a cell whose whole content is `Pass N`) + two loose `found:` — the
        Pass-headed pair in any cell layout, whether or not its counters are readable;
      * an EMPTY CELL (what `| … |<U+2028>| … |` leaves behind once normalised) + two loose
        `found:` + two loose `fixed:` — the HEAD-LESS pair;
      * two Pass HEADS + two strict `found:` tokens — the PROSE pair, which has no cells at all;
      * two strict `| found:` CELL openings — a head-less pair whose second row states no
        `fixed:`.

    ⚠️ THE COST, named: these arms cannot see a join whose second row has neither a head cell,
    an empty cell, nor a readable counter. That residual is deliberate — the counter-only version
    refused two COMMITTED receipts (a row quoting its own verdict verbatim, and a method cell
    narrating another round's example line), and repairing history to fit a gate is not on the
    table. Measured: 0 of the 275 committed receipts are refused by any arm. They are also NOT
    subsets of `_FOUND_TOK`, so a joined line can have no readable first run — which is why the
    caller's no-first-run branch is reachable and load-bearing, not decoration.
    """
    cells = _cells(line)
    if len(_LOOSE_FOUND.findall(line)) >= 2:
        if sum(1 for c in cells if _HEAD_CELL.fullmatch(c.strip())) >= 2:
            return True
        if any(not c.strip() for c in cells) and len(_LOOSE_FIXED.findall(line)) >= 2:
            return True
    if len(_PASS_HEAD_TOK.findall(line)) >= 2 and len(_FOUND_TOK.findall(line)) >= 2:
        return True
    return len(_CELL_FOUND.findall(line)) >= 2


def _second_row_pos(line: str) -> int | None:
    """Where the SECOND row on a joined line begins — the bound on the FIRST row's counters.

    Without it `_first_run` reaches past the join and keeps the SECOND row's counters, which is
    how a joined line yields a quiet row: exactly the fail-open the refusal exists to close.
    """
    heads = [m.start() for m in _PASS_HEAD_TOK.finditer(line)]
    if len(heads) >= 2:
        return heads[1]
    founds = [m.start() for m in _LOOSE_FOUND.finditer(line)]
    return founds[1] if len(founds) >= 2 else None''',
    "joined-row",
)

sub(
    '''def _first_run(line: str) -> tuple[int, int] | None:
    """The FIRST run's `(found, fixed)` on a joined line — the counters the refused row KEEPS.

    A refused row is never dropped (dropping it hands the exit to the previous round, the
    fail-open this whole guard exists to close), so it stays in `ordered` with the counters a
    reader can see first. `fixed:` defaults to 0 when the first run has none — the refusal
    itself, reported by all three readers, is what the author acts on; the counter is only
    there so the row is not inert.
    """
    f = _FOUND_TOK.search(line)
    if f is None:
        return None
    x = _FIXED_TOK.search(line, f.end())
    return int(f.group(1)), (int(x.group(1)) if x else 0)''',
    '''def _first_run(line: str, stop: int | None = None) -> tuple[int, int] | None:
    """The FIRST row's `(found, fixed)` on a joined line — the counters the refused row KEEPS,
    read STRICTLY and only BEFORE `stop` (where the second row begins).

    A refused row is kept rather than dropped (dropping it hands the exit to the previous round,
    the fail-open this whole guard exists to close). `None` means the first row states no
    READABLE counter — a word-trailed `found: 5 issues` — and the caller then keeps nothing at
    all rather than borrow the SECOND row's numbers. `fixed:` defaults to 0 when the first row
    has none: the refusal itself, reported by all three readers, is what the author acts on.
    """
    seg = line if stop is None else line[:stop]
    f = _FOUND_TOK.search(seg)
    if f is None:
        return None
    x = _FIXED_TOK.search(seg, f.end())
    return int(f.group(1)), (int(x.group(1)) if x else 0)''',
    "first-run",
)

sub(
    '''            # ⚠️ The KEPT ROW IS THE PRECONDITION, not a nicety: a "joined" line with no first
            # run would refuse, keep nothing AND skip the flush below — silently dropped, with
            # two adjacent tables merged into one group and the multi-group guard disarmed. Both
            # detectors are subsets of `_FOUND_TOK` now, so this cannot happen; when it does the
            # line is simply NOT joined and takes the ordinary path.
            joined = _first_run(line) if _joined_row(line) else None
            if joined is not None:
                refusals.append(f"{_JOINED_REASON}{line.strip()[:90]}")
                row = (joined[0], None, joined[1], None, line)
                current.append(row)
                ordered.append(row)
                continue''',
    '''            # ⚠️ A joined line with NO readable first run (its counters word-trailed) is a LIVE
            # case, not a theoretical one — the structural arms deliberately reach past
            # `_FOUND_TOK`. It is refused by name like any other join, keeps NOTHING (borrowing
            # the second row's counters is the quiet-off-the-second-half fail-open), and is never
            # handed to the ordinary path below: `_MEGA_ROW` is lazy and would match the SECOND
            # row's cells. It ends the table exactly as any unparsed line does, so no two ledgers
            # merge into one group and no author is accused of a decoy.
            if _joined_row(line):
                refusals.append(f"{_JOINED_REASON}{line.strip()[:90]}")
                pair = _first_run(line, _second_row_pos(line))
                if pair is not None:
                    row = (pair[0], None, pair[1], None, line)
                    current.append(row)
                    ordered.append(row)
                elif current:
                    tables.append(current)
                    current = []
                continue''',
    "table-branch",
)

sub(
    '''            joined = _first_run(line) if _joined_row(line) else None
            if joined is not None:
                # the same refusal on the prose path — `Pass 9: … <U+2028>Pass 10: …` is one
                # physical line to every reader here, and `_pass_counters` refuses it silently
                refusals.append(f"{_JOINED_REASON}{line.strip()[:90]}")
                row = (joined[0], None, joined[1], None, line)
                p_run.append(row)
                ordered.append(row)
            elif pc:''',
    '''            if _joined_row(line):
                # the same refusal on the prose path — `Pass 9: … <U+2028>Pass 10: …` is one
                # physical line to every reader here, and `_pass_counters` refuses it silently.
                # No readable first row ⇒ nothing is kept (never the second row's counters).
                refusals.append(f"{_JOINED_REASON}{line.strip()[:90]}")
                pair = _first_run(line, _second_row_pos(line))
                if pair is not None:
                    row = (pair[0], None, pair[1], None, line)
                    p_run.append(row)
                    ordered.append(row)
            elif pc:''',
    "prose-branch",
)

P.write_text(s, encoding="utf-8")
print("written")
