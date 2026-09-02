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

Flags: `--help` (usage) · `--json` (print the row list) · `--verdict` (the verdict algebra EXECUTED over the rows: the
`PARITY:` and `VERDICT:` lines the runner copies, exit 0/1/2) · `--self-check` (the FREEZE CHECKLIST: header parses, every row
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
    """The vendored `libs/health_probe` module, or None when it is not (yet) vendored here.

    Run as documented (`python scripts/verify_prod_parity.py …`) `sys.path[0]` is `scripts/`, not the
    project root, so `libs` is invisible unless the root is put back first (review 2026-09-02: the
    precondition row read UNVERIFIABLE on every vendored project, masked by a PYTHONPATH-injecting rig)."""
    root = str(Path(__file__).resolve().parent.parent)
    if root not in sys.path:
        sys.path.insert(0, root)
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
_PRECONDITION_ROW = (
    "l0_health_probe_vendored"  # the one row the seeded stub carries; never a contract on its own
)


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
        elif re.match(r"^UNVERIFIABLE \(\s*\)$", str(row.get("detail", ""))):
            misses.append(f"{fn.__name__}: UNVERIFIABLE without a why")
    if all(fn.__name__ == _PRECONDITION_ROW for fn in ROWS):
        misses.append(
            "only the precondition row is authored — no corpus row; freezing this certifies nothing"
            " (run /fabrik-deploy-checklist to derive the rows)"
        )
    for ex in EXCLUSIONS:
        if not re.match(r"^D-\d{3}$", str(ex.get("ruling", ""))):
            misses.append(f"exclusion {ex.get('item')!r} names no ruling (D-NNN)")
    return misses


_COMPARISON_KEYS = (
    "expected",
    "actual",
    "match",
)  # the vendored CLI's own disjunction (health_probe.py:552)


def is_parity_row(row: dict[str, Any]) -> bool:
    """A row carrying ANY comparison key is a comparison row — a disjunction on purpose: a hand-built
    row carrying only `match` was invisible to an `expected AND actual` test and exited 0 (fabrik-lib)."""
    return any(k in row for k in _COMPARISON_KEYS)


def verdict(
    rows: list[dict[str, Any]],
    hdr: dict[str, str],
    *,
    not_obligated: frozenset[str] = frozenset(),
) -> dict[str, Any]:
    """The verdict algebra (spec § Verdict algebra, Amendments 2+3), EXECUTED:

    - no FROZEN contract ⇒ `UNVERIFIED` (terminal, never CONFIRMED);
    - a parity row is any row carrying a comparison key; `match is True` = numerator; `False` = denies
      CONFIRMED; `None` on a parity row = ATTEMPTED-BUT-UNRESOLVED = fail closed (denies CONFIRMED);
      a row carrying none of the keys is a liveness row, outside the parity denominator;
    - `not obligated` (a `shape:` flag) removes a row from the denominator — the ONLY thing that does;
    - NO comparison row AUTHORED at all fails closed — "0 of 0" never certifies (a check that cannot
      fail is a defect; review 2026-09-02). Rows that exist but are ALL `not obligated` keep the prior
      reading (CONFIRMED with `N not obligated` printed — the exemption is explicit data the reader sees);
    - exit precedence: 1 (a critical DOWN) over 2 (disagrees or unresolved) over 0 — liveness wins,
      and precedence never upgrades a verdict.
    """
    if hdr.get("status") != "FROZEN":
        return {"verdict": "UNVERIFIED", "exit": 2, "reasons": ["no FROZEN contract"], "parity": {}}
    parity_all = [r for r in rows if is_parity_row(r)]
    parity = [r for r in parity_all if str(r.get("system")) not in not_obligated]
    agree = sum(1 for r in parity if r.get("match") is True)
    disagree = sum(1 for r in parity if r.get("match") is False)
    unresolved = sum(1 for r in parity if r.get("match") is None)
    unverifiable = sum(1 for r in parity if str(r.get("detail", "")).startswith("UNVERIFIABLE"))
    down = [str(r.get("system")) for r in rows if r.get("status") == "DOWN"]
    reasons: list[str] = []
    if down:
        reasons.append(f"DOWN: {', '.join(down)}")
    if disagree:
        reasons.append(f"{disagree} disagree")
    if unresolved:
        reasons.append(f"{unresolved} attempted-unresolved (fail closed)")
    if not parity_all:  # nothing AUTHORED — distinct from "every row exempted by shape:", which stays visible as N not obligated
        reasons.append(
            "empty parity denominator — no comparison row (a check that cannot fail is a defect)"
        )
    code = 1 if down else (2 if (disagree or unresolved or not parity_all) else 0)
    v = "CONFIRMED" if not reasons else "VERIFICATION FAILED"
    return {
        "verdict": v,
        "exit": code,
        "reasons": reasons,
        "parity": {
            "agree": agree,
            "disagree": disagree,
            "unresolved": unresolved,
            "unverifiable": unverifiable,
            "denominator": len(parity),
            "not_obligated": len(not_obligated),
        },
    }


def _exit_code(rows: list[dict[str, Any]], hdr: dict[str, str]) -> int:
    """ONE exit algebra: the default/`--json` run exits exactly as `--verdict` would (`verdict()` is the
    single source — a second hand-written precedence here was the retired-rule class)."""
    return int(verdict(rows, hdr)["exit"])


_FLAGS = ("--json", "--verdict", "--self-check", "--header", "--help", "-h")
_USAGE = (
    "usage: verify_prod_parity.py [--json | --verdict | --self-check | --header | --help]\n"
    "  (no flag)     run the contract rows, print `STATUS system: detail` per row; exit as --verdict\n"
    "  --json        the row list as JSON (the shape /fabrik-deploy-verify consumes)\n"
    "  --verdict     the verdict algebra EXECUTED: the PARITY:/VERDICT: lines; exit 0 confirmed · 2 denied/DRAFT · 1 on a DOWN\n"
    "  --self-check  the FREEZE CHECKLIST; exit 0 when the contract may be frozen\n"
    "  --header      the parsed Status/Version/Date/Mode header as JSON\n"
)


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if "--help" in args or "-h" in args:
        print(_USAGE, end="")
        return 0
    unknown = [a for a in args if a not in _FLAGS]
    if unknown:
        print(f"unknown flag(s): {' '.join(unknown)}\n{_USAGE}", end="", file=sys.stderr)
        return 64  # EX_USAGE — a typo must never fall through to a contract run
    hdr = parse_header()
    if "--header" in args:
        print(json.dumps(hdr))
        return 0
    if "--verdict" in args:
        rows = run_rows()
        v = verdict(rows, hdr)
        p = v["parity"]
        if p:
            print(
                f"PARITY: {p['agree']} agree / {p['disagree']} disagree / {p['unresolved']} unresolved"
                f" / {p['unverifiable']} UNVERIFIABLE of {p['denominator']} (contract {hdr.get('version')},"
                f" Mode {hdr.get('mode')}, {p['not_obligated']} not obligated)"
            )
        print(
            f"VERDICT: {v['verdict']}" + (f" — {'; '.join(v['reasons'])}" if v["reasons"] else "")
        )
        return int(v["exit"])
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
