#!/usr/bin/env python3
# AFTER-EDIT: docs/DEPLOYMENT.md, docs/OPERATIONS.md | none
# Status: DRAFT · Version: v0 · Date: — · Mode: —
# Frozen — no agent adds, removes or re-derives a row not listed here. Any change = bump Version
# + re-freeze via `/fabrik-deploy-checklist`.
"""The deployment-verification CONTRACT for this project — one runnable check + expected result per
corpus row, so a deploy is certified against what was BUILT rather than against liveness alone.

Seeded by the scaffolder as a `Status: DRAFT` stub: an unfilled contract FAILS CLOSED (exit 2 — the
same "disagrees / unresolved" code a filled contract uses for a mismatch), so a verify run reads it as
UNVERIFIED, never as CONFIRMED. `/fabrik-deploy-checklist` authors the rows and flips the header to
FROZEN; `/fabrik-deploy-verify` executes `--json` against the LIVE service and applies the verdict
algebra; `/fabrik-release`'s VPS path reads the header and BLOCKS on DRAFT.

Row shape = the vendored `health-probe` comparison row — `{system, status, detail, expected, actual,
match, compare_error}` — produced by its `compare()` so the tri-state `match` means exactly what the
runner expects: `True` agrees · `False` disagrees · `None` ATTEMPTED-BUT-UNRESOLVED (fail closed). A
LIVENESS row (reachability, no declared value) carries NONE of the comparison keys. The module is
imported lazily so a project that skips Layers 2–4 never loads it; a missing vendored copy is itself
reported as an `UNVERIFIABLE` row (exit 2), never a traceback.

Flags: `--json` (print the row list) · `--self-check` (the FREEZE CHECKLIST: header parses, every row
returns the shape, every UNVERIFIABLE carries a why, the exclusion list names a ruling) · `--header`
(print the parsed header as JSON). Read-only against the target by contract: a row that would mutate
the deployed service is written `UNVERIFIABLE (mutating — needs a scoped payload + the operator's go)`.
"""

from __future__ import annotations

import json
import re
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

_HEADER_RE = re.compile(
    r"^# Status:\s*(?P<status>DRAFT|FROZEN)\s*·\s*Version:\s*(?P<version>v\d+)\s*·\s*"
    r"Date:\s*(?P<date>[^·]+?)\s*·\s*Mode:\s*(?P<mode>.+?)\s*$",
    re.M,
)

# The declared exclusion set — DATA, with the ruling that made it (a `D-NNN` from docs/DECISIONS.md)
# beside every entry, so the runner and a reader see what was excluded and why.
EXCLUSIONS: list[dict[str, str]] = [
    # {"item": "sales/activities/invoices history", "ruling": "D-017"},
]


def parse_header(path: Path | None = None) -> dict[str, str]:
    """The machine-readable header block (first lines of THIS file). Missing → DRAFT, fail closed."""
    text = (path or Path(__file__)).read_text(encoding="utf-8", errors="replace")
    m = _HEADER_RE.search(text[:2000])
    if not m:
        return {"status": "DRAFT", "version": "v0", "date": "—", "mode": "—", "parsed": "false"}
    return {**m.groupdict(), "parsed": "true"}


def _health_probe() -> Any | None:
    """The vendored `libs/health_probe` module, or None when it is not (yet) vendored here."""
    try:
        from libs.health_probe import (
            health_probe,  # noqa: PLC0415 — lazy on purpose (see module doc)
        )
    except ImportError:
        return None
    return health_probe


def unverifiable(system: str, why: str) -> dict[str, Any]:
    """A row the contract could not assert — counted in the denominator, never dropped, fails closed."""
    return {
        "system": system,
        "status": "SKIP",
        "detail": f"UNVERIFIABLE ({why})",
        "expected": None,
        "actual": None,
        "match": None,
        "compare_error": None,
    }


def compare_row(
    system: str,
    expected: Any,
    actual: Any,
    *,
    comparator: Callable[[Any, Any], bool] | None = None,
) -> dict[str, Any]:
    """One comparison row through the VENDORED `compare()` — never a hand-built dict (a row carrying
    only `match` is invisible to an `expected AND actual` test; the vendored predicate is a disjunction)."""
    hp = _health_probe()
    if hp is None:
        return unverifiable(system, "health_probe not vendored — run the fleet sync")
    row: dict[str, Any] = dict(hp.compare(system, expected, actual, comparator=comparator))
    return row


def liveness_row(system: str, ok: bool, detail: str) -> dict[str, Any]:
    """A reachability row: three keys, NONE of the comparison keys."""
    return {"system": system, "status": "OK" if ok else "DOWN", "detail": detail}


# ── the corpus rows: ONE function per corpus id, named by it (l1_…, l2_…, l3_…, l4_… — lowercase: the hub's ruff N802 refuses capitalised function names) ──────────────
# The DRAFT stub carries exactly one row — the contract's own precondition. `/fabrik-deploy-checklist`
# derives the rest from CODE + SPEC + DEV (never PROD) and replaces this list.


def l0_health_probe_vendored() -> dict[str, Any]:
    """The comparison rows need the vendored module; report its presence as a row, not a crash."""
    return compare_row("l0_health_probe_vendored", True, _health_probe() is not None)


ROWS: list[Callable[[], dict[str, Any]]] = [l0_health_probe_vendored]


def run_rows() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for fn in ROWS:
        try:
            out.append(fn())
        except Exception as exc:  # noqa: BLE001 — a row that raises is UNVERIFIABLE, never a crash
            out.append(unverifiable(fn.__name__, f"row raised {type(exc).__name__}: {exc}"))
    return out


def self_check() -> list[str]:
    """The FREEZE CHECKLIST — every miss is one line; empty means the contract may be frozen."""
    misses: list[str] = []
    hdr = parse_header()
    if hdr.get("parsed") != "true":
        misses.append("header does not parse (Status · Version · Date · Mode)")
    for fn in ROWS:
        row = fn()
        if not isinstance(row, dict) or "system" not in row or "status" not in row:
            misses.append(f"{fn.__name__}: not a row (needs at least system + status)")
        elif (
            row.get("detail", "").startswith("UNVERIFIABLE") and row["detail"] == "UNVERIFIABLE ()"
        ):
            misses.append(f"{fn.__name__}: UNVERIFIABLE without a why")
    for ex in EXCLUSIONS:
        if not re.match(r"^D-\d{3}$", str(ex.get("ruling", ""))):
            misses.append(f"exclusion {ex.get('item')!r} names no ruling (D-NNN)")
    return misses


def _exit_code(rows: list[dict[str, Any]], hdr: dict[str, str]) -> int:
    """LIVENESS WINS, then the comparison verdict, then 0 — and a DRAFT header is never 0."""
    if any(r.get("status") == "DOWN" for r in rows):
        return 1
    keys = ("expected", "actual", "match")
    if any(any(k in r for k in keys) and r.get("match") is not True for r in rows):
        return 2
    return 2 if hdr.get("status") != "FROZEN" else 0


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    hdr = parse_header()
    if "--header" in args:
        print(json.dumps(hdr))
        return 0
    if "--self-check" in args:
        misses = self_check()
        for m in misses:
            print(f"SELF-CHECK MISS: {m}")
        print("self-check: OK" if not misses else f"self-check: {len(misses)} miss(es)")
        return 0 if not misses else 2
    rows = run_rows()
    if "--json" in args:
        print(json.dumps(rows, indent=1))
    else:
        for r in rows:
            print(f"{r.get('status', '?'):5} {r.get('system')}: {r.get('detail', '')}")
    if hdr.get("status") != "FROZEN":
        print(
            "parity contract not yet authored — Status: DRAFT — run /fabrik-deploy-checklist",
            file=sys.stderr,
        )
    return _exit_code(rows, hdr)


if __name__ == "__main__":
    sys.exit(main())
