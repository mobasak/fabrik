#!/usr/bin/env python3
# AFTER-EDIT: tests/test_decisions_helper.py, docs/reference/decision-ledger.md, scripts/docs_updater.py (keep MERGE_OWNER_RE identical) | NOT the 2026-08-30 design spec: it is a FROZEN CONVERGED artifact, so a behaviour change is recorded in a D-row, never by editing it
"""Fleet decision-ledger query — grep every repo's docs/DECISIONS.md in one command.

The read half of the decision ledger (spec: docs/superpowers/specs/
2026-08-30-decision-ledger-v2-design.md). The operator's directive: agents ALWAYS query the
ledger before answering "where is X / did we decide Y / why is Z like this" — this is the
fleet-wide query the duty names.

Usage:
    python3 scripts/decisions.py <term>            # case-insensitive substring over all ledgers
    python3 scripts/decisions.py <term> --root /opt
    python3 scripts/decisions.py --check           # mechanical integrity: every
                                                   # `supersedes D-NNN` pointer must resolve
                                                   # to an existing row id in the same ledger,
                                                   # and no id appears on two rows;
                                                   # exit 1 on a dangling pointer or duplicate

Output: `repo · D-NNN · when · who · what · why · where` per matching row. A repo without a ledger is
silently skipped (adoption is rolling). Query always exits 0; only --check has a failing exit.
"""

from __future__ import annotations

import argparse
import contextlib
import fcntl
import json
import re
import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path

# Case-insensitive + normalized to upper in _rows(): a lowercase-minted `| d-003 |` row
# must not be invisible to the integrity checks (review 2026-08-30).
ROW_RE = re.compile(r"^\|\s*(D-\d+)\s*\|", re.IGNORECASE)
SUPERSEDES_RE = re.compile(r"supersedes\s+(D-\d+)", re.IGNORECASE)
MERGE_OWNER_RE = re.compile(r"^\**\s*MERGE OWNER:\s*([A-Za-z0-9][A-Za-z0-9_.@-]*)", re.I)


def _say(line: str) -> None:
    # UTF-8 straight through — the ledger is saturated with ·/—/§ and printing their
    # backslash escapes made every real row unreadable (manifesto-binding review,
    # 2026-08-30/31). The fallback
    # keeps the tool alive on a non-UTF-8 stdout instead of crashing.
    # Library callers (import + main()) bypass the __main__ SIGPIPE guard — a closed
    # downstream (`| head`) is a clean exit, never a traceback, on BOTH print paths
    # (a non-UTF-8 stdout routes EVERY row through the fallback print).
    try:
        print(line)
    except UnicodeEncodeError:
        try:
            print(line.encode("ascii", "backslashreplace").decode("ascii"))
        except BrokenPipeError:
            raise SystemExit(0) from None
    except BrokenPipeError:
        raise SystemExit(0) from None


def _ledgers(root: Path) -> list[tuple[str, Path]]:
    """(repo-name, ledger-path) for every repo under root with a ledger, root's own included."""
    out: list[tuple[str, Path]] = []
    own = root / "docs" / "DECISIONS.md"
    if own.is_file():
        out.append((root.name, own))
    try:
        for entry in sorted(root.iterdir()):
            p = entry / "docs" / "DECISIONS.md"
            if entry.is_dir() and p.is_file():
                out.append((entry.name, p))
    except OSError:
        pass
    return out


def _code_span_ranges(s: str) -> list[tuple[int, int]]:
    """Half-open ``(start, end)`` ranges of the CommonMark §6.1 code spans in *s*.

    A run of N backticks opens a span that only a run of EXACTLY N closes; an unclosed run is
    literal text and opens nothing.

    ⚠ The ENCODER and the DECODER both call this — they do not each implement the rule. A byte of
    disagreement between them makes ``read(append(x)) != x``, which is the one failure a writer
    whose whole purpose is round-tripping cannot have.
    """
    spans: list[tuple[int, int]] = []
    i, n = 0, len(s)
    while i < n:
        if s[i] != "`":
            i += 1
            continue
        j = i
        while j < n and s[j] == "`":
            j += 1
        run = j - i
        k = j
        while k < n:
            if s[k] != "`":
                k += 1
                continue
            m = k
            while m < n and s[m] == "`":
                m += 1
            if m - k == run:
                spans.append((i, m))
                i = m
                break
            k = m
        else:
            i = j  # unclosed run: literal, opens nothing
    return spans


def _in_span(idx: int, spans: list[tuple[int, int]]) -> bool:
    return any(a <= idx < b for a, b in spans)


def _escape_cell(text: str) -> str:
    """One authored field as a table cell, escaped exactly as :func:`_rows` decodes it.

    OUTSIDE a code span ``\\`` then ``|`` are escaped. INSIDE one only ``|`` is — a code span
    decodes nothing else, so an unconditional backslash-doubling puts a LITERAL second backslash
    into the rendered ledger. Executed on a real web-ecommerce-factory regex row: every ``\\d``
    became ``\\\\d`` on GitHub, breaking both halves of the round trip
    (``read(append(x)) == x`` AND ``render(append(x)) == x``).
    """
    spans = _code_span_ranges(text)
    out: list[str] = []
    for idx, ch in enumerate(text):
        if ch == "|":
            out.append("\\|")
        elif ch == "\\" and not _in_span(idx, spans):
            out.append("\\\\")
        else:
            out.append(ch)
    return "".join(out)


def _rows(path: Path) -> list[tuple[str, list[str]]]:
    """(id, cells) per data row; header/separator rows carry no D-NNN id and never match."""
    rows: list[tuple[str, list[str]]] = []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return rows
    for line in text.splitlines():
        m = ROW_RE.match(line.strip())
        if not m:
            continue
        # GFM: `\X` is literal X, so `\|` is CONTENT and `\\|` is a literal backslash
        # followed by a REAL separator. A fixed-width lookbehind cannot count backslashes and
        # mis-parsed the second shape, dropping a column; this scan consumes the escape.
        cells: list[str] = []
        buf: list[str] = []
        s = line.strip().strip("|")
        # Code spans decode NOTHING but `\|` — the separator must still be escapable inside one or
        # a cell could not carry a pipe in code. Same helper the writer uses, so the two agree.
        spans = _code_span_ranges(s)
        i = 0
        while i < len(s):
            if s[i] == "\\" and i + 1 < len(s) and s[i + 1] == "|":
                buf.append("|")
                i += 2
            elif (
                s[i] == "\\"
                and i + 1 < len(s)
                and s[i + 1] in _ESCAPABLE
                and not _in_span(i, spans)
            ):
                buf.append(s[i + 1])
                i += 2
            elif s[i] == "\\" and i + 1 < len(s):
                # NOT escapable: GFM escapes ASCII punctuation only, so the backslash is
                # LITERAL here. Eating it deleted `\d`/`\s`/`\n` from code spans and made
                # the row unfindable by its own text (executed: 6 rows, 2 repos).
                buf.append(s[i])
                buf.append(s[i + 1])
                i += 2
            elif s[i] == "|":
                cells.append("".join(buf).strip())
                buf = []
                i += 1
            else:
                buf.append(s[i])
                i += 1
        cells.append("".join(buf).strip())
        rows.append((m.group(1).upper(), cells))
    return rows


_ESCAPABLE = frozenset("""!"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~""")  # GFM: punctuation only
_MALFORMED = "⚠ MALFORMED ROW — column missing; read the ledger"


def _six(cells: list[str]) -> list[str]:
    """The six columns the contract promises, from a row that may not carry exactly six.

    A row with an UNESCAPED `|` inside its prose (a real enum like `capped | done | error`)
    parses long, and the old code padded with `[""] * (6 - len(cells))` — which is `[]` when the
    row is long, so `padded[4]`/`padded[5]` printed FRAGMENTS of `what` where `why` and `where`
    belong. A SHORT row was silently filled with blanks instead, so the tool the contract makes
    the FIRST stop for "where is X / why is Z" answered blank and sent the reader into the wider
    hunt the rule exists to prevent (measured: 6 of 265 hub rows long, 5 of 39 short in
    iterative_image_editor; 01M2JQYM9PGQK6Q53GJ3SGP3TV).

    A long row is read from BOTH ENDS — `where` is the last cell and `why` the one before it,
    which held for 6 of 6 long rows on this ledger — and the middle is rejoined as `what` with
    the separator restored. A SHORT row is never fabricated: the missing columns are marked so the
    reader opens the file instead of trusting a blank.

    ⚠ Validated FLEET-WIDE (49 ledgers, 944 rows, 14 long, 64 short) — an earlier cut measured the
    hub's 265 alone, took a trailing HTML provenance comment for the `where`, and REGRESSED four
    fabrik-lib rows that had been correct. Such a comment is peeled before the both-ends read.

    ⚠ COBRA (D-253): the cheapest way to silence the marker WITHOUT recording anything is to pad
    the row with two empty cells `| |`, restoring exactly the pre-fix silent blank. That is why an
    EMPTY reconstructed `why`/`where` is marked too — padding buys nothing.
    """
    while len(cells) > 6 and cells[-1].startswith("<!--"):
        cells = cells[:-1]
    if len(cells) > 6:
        six = [*cells[:3], " | ".join(cells[3:-2]), cells[-2], cells[-1]]
    else:
        six = cells + [_MALFORMED] * (6 - len(cells))
    # BOTH branches, so padding a short row with `| |` to silence the marker buys nothing.
    return [c if c or n < 4 else _MALFORMED for n, c in enumerate(six)]


def _query(root: Path, term: str) -> None:
    needle = term.lower()
    hits = 0
    for repo, path in _ledgers(root):
        for rid, cells in _rows(path):
            if needle in " ".join(cells).lower():
                padded = _six(cells)
                # ALL six cells — the duty this tool serves promises "what+why+where is
                # the full answer", and WHY was the one field the output omitted
                # (review 2026-08-31; the D-000 directive is ABOUT the why).
                _say(
                    f"{repo} · {rid} · {padded[1]} · {padded[2]} · {padded[3]} · "
                    f"{padded[4]} · {padded[5]}"
                )
                hits += 1
    if not hits:
        _say(
            f"no ledger row matches {term!r} — the wider hunt is legitimate now "
            "(and its answer belongs in a new row)"
        )


def _check(root: Path) -> int:
    bad = 0
    for repo, path in _ledgers(root):
        rows = _rows(path)
        ids = {rid for rid, _ in rows}
        seen: set[str] = set()
        for rid, _cells in rows:
            # Concurrent sessions minting from stale max-id reads produce two rows with one
            # id (live case: two D-041s, 2026-08-30) — every `supersedes` to it is ambiguous.
            if rid in seen:
                _say(
                    f"DUPLICATE: {repo} has more than one {rid} row in {path} — "
                    "renumber the later-minted row to the next free id"
                )
                bad += 1
            seen.add(rid)
        for rid, cells in rows:
            for target in SUPERSEDES_RE.findall(" ".join(cells)):
                target = target.upper()  # the IGNORECASE capture preserves source case
                if target not in ids:
                    _say(f"DANGLING: {repo} {rid} supersedes {target} which has no row in {path}")
                    bad += 1
    if bad:
        _say(
            f"-> {bad} ledger integrity defect(s) — a superseded row is never deleted "
            "(restore it or fix the pointer); a duplicated id gets renumbered"
        )
        return 1
    return 0


# --- id reservation, box-local (spec delta §2) -------------------------------------------------
_RESERVE_TTL_DAYS = 7
_LOCK_TRIES, _LOCK_WAIT_S = 50, 0.1


def _repo_key(target: Path) -> str:
    """The reservation key for *target*: the basename of the repo the ledger belongs to.

    ⚠ The key is the GIT COMMON DIR ALONE — the ledger's own path must NOT enter it. Both shapes
    that tempt you present identically (one common-dir, the repo-relative path ``docs/DECISIONS.md``):
    ``/opt/fabrik-lib`` + ``-account`` + ``-review`` are worktrees of ONE repo carrying THREE separate
    ledgers, while ``/opt/fabrik`` has 18 registered worktrees whose ledger is the SAME one at an older
    commit. A path-keyed file hands that stale worktree its own high-water (D-155) and it mints D-156,
    an id already live on master. No path-based key separates the first case while unifying the second,
    so the key unifies and the SEED separates (see :func:`_allocate`).

    ``git rev-parse`` runs against the TARGET, never the cwd — ``--next-id .`` is the contract-mandated
    spelling and ``Path('.').name`` is ``''``, which would put all 49 repos in one file.
    """
    probe = target if target.is_dir() else target.parent
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
            cwd=probe,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        if out.returncode == 0 and out.stdout.strip():
            return Path(out.stdout.strip()).parent.name or "_root"
    except (OSError, subprocess.SubprocessError):
        pass
    return probe.resolve().name or "_root"


def _reserve_path(key: str) -> Path:
    return Path.home() / ".claude" / "state" / "decision-ids" / f"{key}.jsonl"


@contextlib.contextmanager
def _locked(path: Path) -> Iterator[bool]:
    """flock *path*.lock. Yields True when held, False when it could not be taken.

    The CALLER decides the failure direction, because the two legs differ: a lock TIMEOUT fails
    CLOSED (see :func:`_allocate`) while an unwritable state dir fails OPEN. An earlier draft let the
    timeout fall open to ``max+1``; executed, agent B then minted the exact id agent A was holding —
    a collision generator in precisely the two-agent condition the reservation exists for.
    """
    lock = path.with_suffix(path.suffix + ".lock")
    fh = None
    try:
        lock.parent.mkdir(parents=True, exist_ok=True)
        fh = lock.open("a+")
    except OSError:
        yield False
        return
    try:
        for _ in range(_LOCK_TRIES):
            try:
                fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError:
                time.sleep(_LOCK_WAIT_S)
        else:
            yield False
            return
        yield True
    finally:
        if fh is not None:
            try:
                fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
            except OSError:
                pass
            fh.close()


def _live_reservations(path: Path) -> list[int]:
    """Reserved ids not older than the TTL. A pruned id is NEVER re-issued — allocation is a
    monotonic high-water mark, so the hole it leaves is permanent, which is what makes pruning safe."""
    cutoff = time.time() - _RESERVE_TTL_DAYS * 86400
    out: list[int] = []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return out
    for line in text.splitlines():
        try:
            row = json.loads(line)
            if float(row.get("at", 0)) >= cutoff:
                out.append(int(row["id"]))
        except (ValueError, TypeError, KeyError):
            continue
    return out


def _ledger_of(target: Path) -> Path:
    return target / "docs" / "DECISIONS.md" if target.is_dir() else target


def _ledger_ids(ledger: Path) -> list[int]:
    try:
        text = ledger.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    return [int(m) for m in re.findall(r"^\|\s*D-(\d+)\s*\|", text, re.M)]


def _merge_base_ids(ledger: Path) -> list[int]:
    """Ids in the ledger as it stands on the INTEGRATION branch, not just in this checkout.

    Spec delta §3. An agent on a three-day-old branch reads a ledger that is missing every row
    master gained meanwhile, so ``max(ledger)+1`` there re-issues ids already live. Unioning the
    integration branch's ids into the pool makes the allocation correct from a stale branch without
    needing that branch to be up to date.

    ⚠ Fails OPEN and SILENT: no git, no upstream, a detached head or a fresh repo all return [] and
    the caller falls back to the working ledger alone — the same answer as before this existed. The
    high-water mark absorbs the caveat the cited sources raise, that a merge-base "next free" shifts
    across rebases: a shifting FLOOR cannot lower an id that is already the max of a wider pool.
    """
    rel = "docs/DECISIONS.md"
    probe = ledger.parent.parent if ledger.name == "DECISIONS.md" else ledger.parent
    for ref in ("origin/HEAD", "origin/master", "origin/main", "master", "main"):
        try:
            out = subprocess.run(
                ["git", "show", f"{ref}:{rel}"],
                cwd=probe,
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            return []
        if out.returncode == 0 and out.stdout:
            return [int(m) for m in re.findall(r"^\|\s*D-(\d+)\s*\|", out.stdout, re.M)]
    return []


def _allocate(ledger: Path, key: str, *, reserve: bool) -> tuple[int | None, str]:
    """Next id as a MONOTONIC HIGH-WATER MARK, optionally reserving it. Returns (id, note).

    ``max(THIS ledger's rows ∪ THIS key's reservations) + 1`` — never a first-free scan. A first-free
    scan backfills gaps (executed: it returns D-011 in fabrik-lib, which has 31, and D-003 in
    web-ecommerce-factory), re-issuing retired numbers so every ``supersedes D-011`` resolves to the
    wrong row. Gaps are normal and correct.

    The SEED is the ledger being written, which is what lets ONE common-dir key serve worktrees that
    share a ledger AND sibling checkouts that do not: a stale hub worktree is seeded from master's
    reservations and cannot re-issue a live id, while fabrik-lib-account's 1-row ledger gets an id
    above fabrik-lib's high-water instead of D-002.

    FAILURE DIRECTIONS, deliberately different: a lock TIMEOUT fails CLOSED (returns None — a refused
    allocation costs a retry, a colliding one costs the duplicate). An unwritable state dir fails OPEN
    (returns max+1 with a note) because then NOBODY can reserve, so degradation is uniform and no id
    is stolen from a holder that does not exist.
    """
    ids = _ledger_ids(ledger)
    path = _reserve_path(key)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        base = max(ids) + 1 if ids else 1
        return base, f"decisions: reservation dir unwritable ({exc}) — not reserved\n"
    if not reserve:
        with _locked(path) as held:
            if not held:
                return None, "decisions: could not take the reservation lock — no id issued\n"
            pool = ids + _live_reservations(path) + _merge_base_ids(ledger)
            return (max(pool) + 1 if pool else 1), ""
    with _locked(path) as held:
        if not held:
            return None, "decisions: could not take the reservation lock — no id issued\n"
        pool = ids + _live_reservations(path) + _merge_base_ids(ledger)
        nid = max(pool) + 1 if pool else 1
        try:
            with path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps({"id": nid, "at": time.time()}) + "\n")
        except OSError as exc:
            return nid, f"decisions: reservation not written ({exc})\n"
        return nid, ""


def _append_row(ledger: Path, fields: list[str], key: str) -> int:
    """Allocate an id and write the row atop the table — BOTH inside ONE lock (spec delta §1).

    ⚠ Allocation and the write are one critical section. Two concurrent ``--append`` calls that each
    computed ``max(...)+1`` outside a lock would produce exactly the duplicate this exists to prevent,
    through the SANCTIONED path.
    """
    for f in fields:
        if "\n" in f or "\r" in f:
            sys.stderr.write("decisions: a field contains a newline — refused, nothing written\n")
            return 2
    path = _reserve_path(key)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    with _locked(path) as held:
        if not held:
            sys.stderr.write("decisions: could not take the lock — nothing written\n")
            return 1
        ids = _ledger_ids(ledger)
        pool = ids + _live_reservations(path) + _merge_base_ids(ledger)
        nid = max(pool) + 1 if pool else 1
        try:
            lines = ledger.read_text(encoding="utf-8", errors="replace").split("\n")
        except OSError as exc:
            sys.stderr.write(f"decisions: cannot read {ledger} ({exc})\n")
            return 1
        sep = next(
            (
                n
                for n, ln in enumerate(lines)
                if re.match(r"^\|[\s:|-]+\|\s*$", ln.strip())
                and n
                and lines[n - 1].lstrip().startswith("|")
            ),
            None,
        )
        if sep is None:
            sys.stderr.write(f"decisions: no table header found in {ledger}\n")
            return 1
        row = "| " + " | ".join([f"D-{nid:03d}", *(_escape_cell(f) for f in fields)]) + " |"
        lines.insert(sep + 1, row)
        try:
            ledger.write_text("\n".join(lines), encoding="utf-8")
        except OSError as exc:
            sys.stderr.write(f"decisions: cannot write {ledger} ({exc})\n")
            return 1
        try:
            with path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps({"id": nid, "at": time.time()}) + "\n")
        except OSError:
            pass
        print(f"D-{nid:03d}")
        return 0


def _next_id(repo: Path) -> int:
    """Print the next free ``D-NNN`` for *repo*'s ledger, derived from the file right now.

    Removes the HAND-derivation error, which is a real and repeated one: deriving "the next
    number" by eye picks up a stale maximum whenever a sibling appended while you were reading —
    it happened twice in one day here (a D-084 collision between two hub sessions, and a D-107
    already taken by the time a row was written), and three concurrent agents in another repo
    produced a duplicate D-006 the same way (mail 01M1KR2ANYTRZR80WF1H29399T).

    It does NOT make allocation atomic, and saying so is the point: two agents calling this in
    the same window still get the same number. The race is closed at the OTHER end — by minting
    the id in the same change as the row (contract § the decision ledger) so the window is
    seconds rather than a work session, and by ``--check`` / the gate's Decision Ledger check,
    which refuses a duplicate before it can be pushed. Use this to read, not to reserve.
    """
    ledger = repo / "docs" / "DECISIONS.md" if repo.is_dir() else repo
    try:
        text = ledger.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        sys.stderr.write(f"decisions: cannot read {ledger} ({exc})\n")
        return 1
    ids = [int(m) for m in re.findall(r"^\|\s*D-(\d+)\s*\|", text, re.M)]
    if not ids:
        # A ledger with no rows yet starts at D-001, not D-000: every existing ledger's first
        # row is 001, and a zeroth row would sort oddly against them.
        print("D-001")
        return 0
    print(f"D-{max(ids) + 1:03d}")
    return 0


def _merge_owner(repo: Path) -> int:
    ledger = repo / "docs" / "DECISIONS.md" if repo.is_dir() else repo
    try:
        ledger.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        sys.stderr.write(f"decisions: cannot read {ledger} ({exc})\n")
        return 1
    owner: str | None = None
    for _rid, cells in _rows(ledger):
        if len(cells) > 3:
            match = MERGE_OWNER_RE.match(cells[3])
            if match:
                owner = match.group(1)
    if owner is None:
        print("UNDECLARED")
        return 3
    print(owner)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Query every repo's docs/DECISIONS.md at once.")
    parser.add_argument("term", nargs="?", help="case-insensitive substring to find")
    parser.add_argument("--root", default="/opt", help="fleet root (default: /opt)")
    parser.add_argument(
        "--check",
        action="store_true",
        help="ledger integrity: supersede pointers resolve + no duplicate ids; exit 1 on either",
    )
    parser.add_argument(
        "--merge-owner",
        metavar="REPO_DIR",
        help="print the declared merge owner for that repo ledger",
    )
    parser.add_argument(
        "--next-id",
        metavar="REPO_DIR",
        help="print the next free D- id for that repo's docs/DECISIONS.md, read AT THIS INSTANT "
        "(mint it in the same change as the row — see _next_id)",
    )
    parser.add_argument(
        "--reserve-id",
        metavar="REPO_DIR",
        help="allocate AND RESERVE the next D- id for that repo's ledger (box-local, flocked). "
        "Unlike --next-id this is atomic against a sibling: two concurrent callers get two ids.",
    )
    parser.add_argument(
        "--append",
        metavar="REPO_DIR",
        help="allocate an id and WRITE the row atop that repo's ledger, under one lock; "
        "needs --when --who --what --why --where. The id is allocated by the tool, never by you.",
    )
    for _f in ("when", "who", "what", "why", "where"):
        parser.add_argument(f"--{_f}", help=f"--append: the {_f} cell")
    args = parser.parse_args(argv)

    if args.append:
        target = Path(args.append)
        missing = [f for f in ("when", "who", "what", "why", "where") if not getattr(args, f)]
        if missing:
            sys.stderr.write(f"decisions: --append needs {', '.join('--' + m for m in missing)}\n")
            return 2
        return _append_row(
            _ledger_of(target),
            [args.when, args.who, args.what, args.why, args.where],
            _repo_key(target),
        )
    root = Path(args.root)
    if args.merge_owner:
        return _merge_owner(Path(args.merge_owner))
    if args.next_id:
        return _next_id(Path(args.next_id))
    if args.reserve_id:
        target = Path(args.reserve_id)
        nid, note = _allocate(_ledger_of(target), _repo_key(target), reserve=True)
        if note:
            sys.stderr.write(note)
        if nid is None:
            return 1  # the lock leg fails CLOSED: no id is printed, so none can be minted
        print(f"D-{nid:03d}")
        return 0
    if args.check:
        return _check(root)
    if not args.term:
        parser.error("a query term is required unless --check")
    _query(root, args.term)
    return 0


if __name__ == "__main__":  # pragma: no cover
    # Die silently on a closed pipe (`decisions.py <term> | head`) like every other
    # well-behaved filter — Python's default SIGPIPE handling tracebacks instead.
    import contextlib
    import signal

    with contextlib.suppress(ValueError, OSError, AttributeError):
        signal.signal(signal.SIGPIPE, signal.SIG_DFL)
    raise SystemExit(main(sys.argv[1:]))
