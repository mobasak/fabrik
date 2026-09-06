#!/usr/bin/env python3
# AFTER-EDIT: tests/test_decisions_helper.py, docs/reference/decision-ledger.md, docs/superpowers/specs/2026-08-30-decision-ledger-v2-design.md
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
import re
import sys
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
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        rows.append((m.group(1).upper(), cells))
    return rows


def _query(root: Path, term: str) -> None:
    needle = term.lower()
    hits = 0
    for repo, path in _ledgers(root):
        for rid, cells in _rows(path):
            if needle in " ".join(cells).lower():
                padded = cells + [""] * (6 - len(cells))
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
    args = parser.parse_args(argv)
    root = Path(args.root)
    if args.merge_owner:
        return _merge_owner(Path(args.merge_owner))
    if args.next_id:
        return _next_id(Path(args.next_id))
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
