#!/usr/bin/env python3
# AFTER-EDIT: docs/DEPLOYMENT.md, docs/OPERATIONS.md | none
# Status: DRAFT · Version: v0 · Date: —
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

import importlib.util
import json
import os
import re
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

_HEADER_RE = re.compile(
    r"^# Status:\s*(?P<status>DRAFT|FROZEN)\s*·\s*Version:\s*(?P<version>v\d+)\s*·\s*"
    r"Date:\s*(?P<date>[^·\n]+?)\s*(?:·\s*Mode:\s*[^\n]*?)?\s*$",  # a trailing `· Mode: …` (pre-2026-09-02 freeze) is tolerated and dropped
    re.M,
)

# The declared exclusion set — DATA, with the ruling that made it (a `D-NNN` from docs/DECISIONS.md)
# beside every entry, so the runner and a reader see what was excluded and why.
EXCLUSIONS: list[dict[str, str]] = [
    # {"item": "sales/activities/invoices history", "ruling": "D-017"},
]

#: Rows a `shape:` flag switches OFF (e.g. `is_admin_dashboard: false` → no Authelia row obligated). They
#: stay VISIBLE as rows and leave the parity denominator — the ONLY thing that removes a row.
NOT_OBLIGATED: frozenset[str] = frozenset()

#: Where a row can be EXECUTED. `hub` (default): the public surface, reachable from the operator's box.
#: `host`: the VPS host (docker ps, volume paths). `container`: inside the app container (the database,
#: redis, the internal network). /fabrik-deploy-verify runs one leg per site where it can reach and merges
#: the legs with `--verdict --rows-from`; a leg it cannot reach is emitted UNVERIFIABLE via `--unreachable`,
#: never dropped (tryton-crm's first freeze: 15 of 27 rows were container/host rows and could never resolve
#: from the hub, so the contract could never be CONFIRMED where the runner ran it).
SITES = ("hub", "host", "container")

#: WHICH container the `container` leg runs in — the compose SERVICE that can reach the database, redis
#: and the internal network. Empty = this project's own app service (the compose service named after
#: the project). Declare it when the DB-reaching container is NOT the app (tryton-crm: a deliberately
#: DB-free FastAPI bridge in front of `trytond` — the leg must exec in `trytond`); the runner reads it
#: from `--header` and never guesses. That container must carry the comparator's runtime deps
#: (`httpx` — `libs/health_probe` imports it at module level; python-dotenv only for its `load_env()`,
#: which `_health_probe()` calls when the project has a `.env` — without python-dotenv that load is
#: a no-op, so the leg then sees only the container's own environment).
CONTAINER_LEG_SERVICE: str = ""


def site(name: str) -> Callable[[Callable[[], dict[str, Any]]], Callable[[], dict[str, Any]]]:
    """Declare the site a row must run at: `@site("container")`. Undeclared rows are `hub` rows."""
    if name not in SITES:
        raise ValueError(f"unknown site {name!r} — one of {SITES}")

    def _mark(fn: Callable[[], dict[str, Any]]) -> Callable[[], dict[str, Any]]:
        fn._parity_site = name  # type: ignore[attr-defined]
        return fn

    return _mark


def row_site(fn: Callable[[], dict[str, Any]]) -> str:
    return str(getattr(fn, "_parity_site", "hub"))


def parse_header(path: Path | None = None) -> dict[str, str]:
    """The machine-readable header block (first lines of THIS file). Missing → DRAFT, fail closed."""
    text = (path or Path(__file__)).read_text(encoding="utf-8", errors="replace")
    m = _HEADER_RE.search(text[:2000])
    if not m:
        return {"status": "DRAFT", "version": "v0", "date": "—", "parsed": "false"}
    return {**m.groupdict(), "parsed": "true"}


def _comparator_root() -> tuple[Path | None, Path, Path, str | None]:
    """Where the vendored comparator is loaded from — the PRECEDENCE the runner's recipes rely on
    (W-82cff1ac): (1) this script's own clone when `<clone>/libs/health_probe/health_probe.py` exists
    (the documented `python scripts/verify_prod_parity.py` run, and the container leg's `/app`);
    (2) a FLAT `health_probe/` copy BESIDE the script — where `/fabrik-deploy-verify`'s host leg stages
    it (`scp -r libs/health_probe <vps>:/tmp/health_probe` next to `/tmp/verify_prod_parity.py`, the
    script run from `/tmp` with cwd `/opt/<project>`, whose checkout never holds the gitignored
    comparator) — accepted only when that directory AND the module file are owned by this user and writable by nobody
    else (a shared `/tmp` lets another local user plant a directory, or write one file in yours); (3) neither → None, and the stub fails closed
    with its message and its `.env` location unchanged. The marker is the MODULE the loader needs,
    never the directory (an empty or `__pycache__`-only leftover does not qualify). Never the cwd — a
    hub-cwd run would load the hub's module under the project's row names — and never an environment
    knob. The module is loaded BY FILE PATH (`importlib.util.spec_from_file_location`), never by a
    `sys.path` name lookup, so neither an installed distribution named `health_probe` nor a stray
    module earlier on `sys.path` can stand in for the staged copy.

    Returns (the module path chosen or None, the clone path looked for, the beside path looked for,
    and why a present beside copy was refused, or None)."""
    here = Path(__file__).resolve().parent
    clone = here.parent
    in_clone = clone / "libs" / "health_probe" / "health_probe.py"
    beside = here / "health_probe" / "health_probe.py"
    if in_clone.is_file():
        return in_clone, in_clone, beside, None
    if beside.is_file():
        for node, what in (
            (beside.parent, "the staged copy's directory"),
            (beside, "the staged copy"),
        ):
            st = node.stat()
            if st.st_uid != os.geteuid():
                return None, in_clone, beside, f"{what} is not owned by this user"
            if st.st_mode & 0o022:
                return None, in_clone, beside, f"{what} is writable by others"
        return beside, in_clone, beside, None
    return None, in_clone, beside, None


_COMPARATOR: tuple[Any | None, str | None] | None = (
    None  # (module, failure) — resolved ONCE per process
)


def _load_comparator() -> tuple[Any | None, str | None]:
    """The vendored comparator module, or (None, why). Resolved once per process (a run serves one
    project; the row runner calls `_health_probe()` per row). A chosen file that fails to import or
    lacks the vendored API is reported as FOUND BUT UNUSABLE, never as 'not vendored'."""
    global _COMPARATOR
    if _COMPARATOR is not None:
        return _COMPARATOR
    chosen, in_clone, beside, refused = _comparator_root()
    if chosen is None:
        why = (
            f"health_probe not vendored — looked for {in_clone} and {beside}"
            + (f" ({refused})" if refused else "")
            + "; vendor libs/health_probe or stage it beside the script"
        )
        _COMPARATOR = (None, why)
        return _COMPARATOR
    try:
        spec = importlib.util.spec_from_file_location("_parity_health_probe", chosen)
        if spec is None or spec.loader is None:
            raise ImportError("no loader for the module path")
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
    except Exception as exc:  # noqa: BLE001 — a syntax error or a missing dependency is a row detail, never a crash
        sys.modules.pop("_parity_health_probe", None)
        _COMPARATOR = (
            None,
            f"health_probe found at {chosen} but unusable ({type(exc).__name__}: {exc})",
        )
        return _COMPARATOR
    if not callable(getattr(module, "compare", None)):
        _COMPARATOR = (
            None,
            f"health_probe found at {chosen} but unusable (not the vendored comparator: no compare())",
        )
        return _COMPARATOR
    _COMPARATOR = (module, None)
    return _COMPARATOR


def _not_vendored_detail() -> str:
    _, why = _load_comparator()
    return why or "health_probe unavailable"


def _health_probe() -> Any | None:
    """The vendored `libs/health_probe` module, or None when it is not (yet) usable here.

    `_comparator_root()` picks the module file by its stated precedence and `_load_comparator()` loads
    it by path once per process (review 2026-09-02: the precondition row read UNVERIFIABLE on every
    vendored project because the module was looked up by name from `scripts/`; review 2026-10-11: a
    by-name import also let an installed or planted `health_probe` stand in for the staged copy). The
    project `.env` is always the CLONE's, whichever rung supplied the module."""
    health_probe, _ = _load_comparator()
    if health_probe is None:
        return None
    clone = Path(__file__).resolve().parent.parent
    root = str(clone)
    # Since fabrik-lib cfd9215f importing the module no longer loads the project `.env`; rows that
    # read os.environ after this import relied on it, so load THIS project's `.env` here once, by
    # explicit path (its default search reads the cwd under `python -c`) — a real variable still
    # wins (override=False). A broken `.env` is reported and the rows carry on.
    global _ENV_LOADED
    load_env = getattr(health_probe, "load_env", None)
    dotenv = Path(root) / ".env"
    if load_env is not None and not _ENV_LOADED and dotenv.is_file():
        _ENV_LOADED = True
        before = set(os.environ)
        try:
            loaded = load_env(str(dotenv))
        except (OSError, UnicodeDecodeError) as exc:
            print(
                f"verify_prod_parity: .env not loaded ({type(exc).__name__}: {_why(exc)})",
                file=sys.stderr,
            )
        except ValueError as exc:
            # a key or value os.environ refuses (a NUL byte, or "=" in a quoted key): python-dotenv
            # has already set some keys by then, and which ones does not follow line order, so
            # name what changed (key names only — never a value from `.env`)
            got = sorted(set(os.environ) - before)
            print(
                f"verify_prod_parity: .env {'only partly loaded' if got else 'not loaded'} "
                f"({type(exc).__name__}: {_why(exc)}); set before the error: {', '.join(got) or 'none'}",
                file=sys.stderr,
            )
        else:
            if not loaded:
                print(
                    "verify_prod_parity: .env loaded nothing (it sets no variable, python-dotenv is not "
                    "installed, or PYTHON_DOTENV_DISABLED is truthy — 1/true/t/yes/y), so rows that read it "
                    "see only the real environment",
                    file=sys.stderr,
                )
    return health_probe


_ENV_LOADED = False  # `_health_probe()` runs per row; the project `.env` is loaded once


def _why(exc: Exception) -> object:
    """The reason for a `.env` load error, never its text: a UnicodeError's text quotes the
    offending byte or character of a `.env` value (a non-UTF-8 file, or a non-UTF-8 locale)."""
    return exc.reason if isinstance(exc, UnicodeError) else exc


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
        return unverifiable(system, _not_vendored_detail())
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


def run_rows(
    rows: list[Callable[[], dict[str, Any]]] | None = None,
    *,
    site: str | None = None,
    unreachable: str | None = None,
) -> list[dict[str, Any]]:
    """Execute the rows (all, or one site's). `unreachable` emits the selected rows as UNVERIFIABLE
    WITHOUT running them — the runner's way to keep a leg it could not reach in the denominator."""
    out: list[dict[str, Any]] = []
    for fn in ROWS if rows is None else rows:
        if site is not None and row_site(fn) != site:
            continue
        if unreachable is not None:
            out.append(unverifiable(fn.__name__, f"{row_site(fn)} leg not run — {unreachable}"))
            continue
        try:
            row = fn()
        except Exception as exc:  # noqa: BLE001 — a row that raises is UNVERIFIABLE, never a crash
            out.append(unverifiable(fn.__name__, f"row raised {type(exc).__name__}: {exc}"))
            continue
        if not isinstance(row, dict) or row.get("system") != fn.__name__:
            # The id convention ENFORCED where rows are made (review 2026-10-13, S1): a corpus row is named by
            # its function — the id this loop writes for an --unreachable leg and the id `check_leg_rows`
            # expects in a merge. A row that names itself otherwise would make every merge refuse forever;
            # it reads UNVERIFIABLE here instead, on the first `--json` run, naming the cause.
            got = row.get("system") if isinstance(row, dict) else type(row).__name__
            out.append(
                unverifiable(
                    fn.__name__,
                    f"row returned system {got!r} — a corpus row is named by its function ({fn.__name__!r})",
                )
            )
            continue
        defects = _row_defects(row)
        if defects:
            # The same per-row rules the merge applies (`check_leg_rows`), applied where the row is MADE, so a
            # direct `--verdict` run and the merge of its own legs always agree (review 2026-10-13, O8/O11).
            out.append(
                unverifiable(
                    fn.__name__,
                    "row "
                    + "; ".join(defects)
                    + " — build rows with compare_row()/liveness_row(), never by hand",
                )
            )
            continue
        try:
            json.dumps(row)
        except (TypeError, ValueError) as exc:
            # The fifth axis, serialisability (review 2026-10-13, O12): a Decimal or a date in expected/actual crashed
            # the `--json` leg (exit 1, read as a DOWN) while the direct run confirmed the row — UNVERIFIABLE where made,
            # so both paths agree and the leg file is always written.
            out.append(
                unverifiable(
                    fn.__name__,
                    f"row not JSON-serialisable ({type(exc).__name__}: {str(exc)[:120]}) — compare plain"
                    " values (str, int, float, bool, None, list, dict)",
                )
            )
            continue
        out.append(row)
    return out


def self_check() -> list[str]:
    """The FREEZE CHECKLIST — every miss is one line; empty means the contract may be frozen.

    STATIC by contract: it never executes a row. The shape of a row is proven by the `--json` runs the
    see-red phase performs; a checklist that fired every probe (tryton-crm's first freeze: 20 HTTPS
    requests and a failed-login POST at production per `--self-check`) was the wrong instrument."""
    misses: list[str] = []
    hdr = parse_header()
    if hdr.get("parsed") != "true":
        misses.append("header does not parse (Status · Version · Date)")
    for fn in ROWS:
        if not callable(fn) or not re.match(r"^l\d", fn.__name__):
            misses.append(
                f"{getattr(fn, '__name__', fn)!s}: not a corpus row (a callable named l<layer>_…)"
            )
        elif row_site(fn) not in SITES:
            misses.append(f"{fn.__name__}: unknown site {row_site(fn)!r}")
    names = [fn.__name__ for fn in ROWS if callable(fn)]
    for name in sorted({n for n in names if names.count(n) > 1}):
        misses.append(
            f"{name}: listed {names.count(name)} times in ROWS — one function per corpus id (its own legs"
            " would always be refused as a doubled row)"
        )
    for name in NOT_OBLIGATED:
        if name not in {fn.__name__ for fn in ROWS}:
            misses.append(f"NOT_OBLIGATED names {name!r}, which is not a row")
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
)  # the vendored CLI's own disjunction (health_probe.py `_COMPARISON_KEYS`)


def is_parity_row(row: dict[str, Any]) -> bool:
    """A row carrying ANY comparison key is a comparison row — a disjunction on purpose: a hand-built
    row carrying only `match` was invisible to an `expected AND actual` test and exited 0 (fabrik-lib)."""
    return any(k in row for k in _COMPARISON_KEYS)


#: The status alphabet every row builder here and the vendored comparator write (`health_probe.py`:
#: `OK, DOWN, WARN, SKIP`). `verdict()` reads a DOWN by exact string, so any other spelling hides one.
_ROW_STATUSES = frozenset({"OK", "DOWN", "WARN", "SKIP"})


class _LegRefusedError(Exception):
    """A `--rows-from` merge the script must refuse — EX_USAGE (64), the exit a flag typo takes: an input
    defect, never a verdict (exit 2 would read as "denied", exit 1 as a DOWN, and 0 as CONFIRMED)."""

    def __init__(self, misses: list[str]) -> None:
        super().__init__("; ".join(misses))
        self.misses = misses


def _row_defects(r: dict[str, Any]) -> list[str]:
    """The per-row rules ONE place owns — `run_rows` applies them where a row is made, `check_leg_rows` where legs
    are merged: the three comparison keys all or none, `match` tri-state, `status` from the vendored alphabet."""
    defects: list[str] = []
    present = [k for k in _COMPARISON_KEYS if k in r]
    if present and len(present) != len(_COMPARISON_KEYS):
        defects.append(
            f"carries {len(present)} of {len(_COMPARISON_KEYS)} comparison keys {present} — all three or none"
        )
    if "match" in r and not (r["match"] is None or isinstance(r["match"], bool)):
        defects.append(
            f"match is {r['match']!r} ({type(r['match']).__name__}) — True, False or None only"
        )
    status = r.get("status")
    if (
        not isinstance(status, str) or status not in _ROW_STATUSES
    ):  # a non-str is unhashable: type first
        defects.append(f"status {status!r} is not one of {', '.join(sorted(_ROW_STATUSES))}")
    return defects


def check_leg_rows(rows: list[Any], *, expected_ids: frozenset[str]) -> list[str]:
    """The leg-file threat model (kaizen D-769): a `--rows-from` merge once trusted the files whole, so a leg
    could reach CONFIRMED through four axes. One line per miss, naming its axis; empty = the merge is sound.

    1. WHICH ids appear — every `system` is a row of this contract (`ROWS`, named by function: the id
       `run_rows` itself writes for an `--unreachable` leg);
    2. HOW MANY times each appears — exactly once: the runner emits one leg per site and never drops a row
       (an unreachable leg is emitted UNVERIFIABLE), so a duplicate counts twice in PARITY and a missing id
       shrinks the denominator;
    3. WHICH comparison keys a row carries — all three (`expected`, `actual`, `match`: the vendored
       `compare()` shape, `unverifiable()` included) or none (a liveness row); a partial row is a hand edit;
    4. WHAT `match` holds — `True`, `False` or `None`: `verdict()` tests identity, so a string "true" sits in
       the denominator and is counted nowhere.
    Plus the status alphabet (`verdict()` reads a DOWN by exact string) and that every row is an object
    carrying a `system`. NOT checked: `detail`, extra keys, agreement between `detail` and `match` — the
    verdict reads none of those for its counts.

    Cobra check (D-253): the cheapest way past this check is a hand-written leg carrying every id once, all
    keys and `match: true` — this script cannot tell a forged complete leg from a real one. The counter-measure
    is the runner: `/fabrik-deploy-verify` produces the three leg files itself and merges only those. This
    check closes the SILENT axes (a stale, truncated, re-serialised or doubled leg), not forgery.
    """
    misses: list[str] = []
    counts: dict[str, int] = {}
    for i, r in enumerate(rows):
        if not isinstance(r, dict) or not isinstance(r.get("system"), str):
            misses.append(f"row {i}: not a row object carrying a `system`")
            continue
        sid = r["system"]
        counts[sid] = counts.get(sid, 0) + 1
        if sid not in expected_ids:
            misses.append(
                f"{sid!r}: not a row of this contract (ROWS — a row is named by its function; a leg's"
                " `--json` run already reads a misnamed row UNVERIFIABLE)"
            )
        misses.extend(f"{sid!r}: {d}" for d in _row_defects(r))
    for sid, n in counts.items():
        if n > 1:
            misses.append(f"{sid!r}: appears {n} times (every contract row exactly once per merge)")
    for sid in sorted(expected_ids - counts.keys()):
        misses.append(
            f"{sid!r}: missing from the merge (a leg dropped it — emit it with --unreachable, never drop)"
        )
    return misses


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
    return int(verdict(rows, hdr, not_obligated=NOT_OBLIGATED)["exit"])


_FLAGS = ("--json", "--verdict", "--self-check", "--header", "--help", "-h")
_VALUE_FLAGS = {
    "--site": 1,
    "--unreachable": 1,
    "--rows-from": -1,
}  # -1: every following non-flag token


def _parse(args: list[str]) -> tuple[list[str], dict[str, Any], list[str]]:
    """(flags, values, unknown) — hand-rolled on purpose: the stub carries no argparse so a project that
    strips its dev deps still runs it, and an unknown token must never fall through to a contract run."""
    flags: list[str] = []
    values: dict[str, Any] = {}
    unknown: list[str] = []
    i = 0
    while i < len(args):
        a = args[i]
        if a in _FLAGS:
            flags.append(a)
        elif a in _VALUE_FLAGS:
            n = _VALUE_FLAGS[a]
            vals: list[str] = []
            j = i + 1
            while j < len(args) and not args[j].startswith("--") and (n < 0 or len(vals) < n):
                vals.append(args[j])
                j += 1
            if n >= 0 and vals and not vals[0].strip():
                vals = []  # a BLANK value is no value: `--unreachable ""` is the shape the
            if not vals:  # runner's own `--unreachable "<why>"` placeholder produces unsubstituted
                unknown.append(f"{a} (needs a value)")
                if n >= 0:  # record NO value at all — `run_rows` sentinels on `is not None`, so
                    i = j  # any recorded value yields `UNVERIFIABLE (<site> leg not run — )`,
                    continue  # the why-less row this module's contract forbids (see the docstring)
            values[a] = vals if n < 0 else vals[0]
            i = j
            continue
        else:
            unknown.append(a)
        i += 1
    return flags, values, unknown


def _rows_for(values: dict[str, Any]) -> list[dict[str, Any]]:
    """The rows a verdict is computed from: run here, or merged from `--rows-from` leg files — and a merge
    is checked (`check_leg_rows`) before anything reads it; a miss raises `_LegRefusedError` (exit 64)."""
    files = values.get("--rows-from")
    if not files:
        return run_rows(site=values.get("--site"), unreachable=values.get("--unreachable"))
    merged: list[dict[str, Any]] = []
    misses: list[str] = []
    for f in files:
        try:
            rows = json.loads(Path(f).read_text(encoding="utf-8"))
        except (
            OSError,
            ValueError,
            RecursionError,
        ) as exc:  # JSONDecodeError and UnicodeDecodeError are ValueErrors; a deeply nested file recurses
            misses.append(f"{f}: not a readable JSON file ({type(exc).__name__}: {str(exc)[:200]})")
            continue
        if not isinstance(rows, list):
            misses.append(f"{f}: expected a JSON list of row objects (a leg's --json output)")
            continue
        for j, r in enumerate(
            rows
        ):  # named by FILE and in-file index — three legs, one operator reading
            if not isinstance(r, dict) or not isinstance(r.get("system"), str):
                misses.append(f"{f}: row {j}: not a row object carrying a `system`")
            else:
                merged.append(r)
    misses.extend(check_leg_rows(merged, expected_ids=frozenset(fn.__name__ for fn in ROWS)))
    if misses:
        raise _LegRefusedError(misses)
    return merged


def _refuse_legs(exc: _LegRefusedError) -> int:
    print(
        f"--rows-from refused ({len(exc.misses)} miss(es)) — the merge is not this contract's legs"
        " (every contract row once, the comparison keys all or none, a tri-state match, a known status):",
        file=sys.stderr,
    )
    for m in exc.misses:
        print(f"  {m}", file=sys.stderr)
    return 64  # EX_USAGE — a bad leg file must never fall through to a verdict


_USAGE = (
    "usage: verify_prod_parity.py [--json | --verdict | --self-check | --header | --help] [--site NAME] [--unreachable WHY] [--rows-from F…]\n"
    "  (no flag)     run the contract rows, print `STATUS system: detail` per row; exit as --verdict\n"
    "  --json        the row list as JSON (the shape /fabrik-deploy-verify consumes)\n"
    "  --verdict     the verdict algebra EXECUTED: the PARITY:/VERDICT: lines; exit 0 confirmed · 2 denied/DRAFT · 1 on a DOWN\n"
    "  --self-check  the FREEZE CHECKLIST; exit 0 when the contract may be frozen\n"
    "  --header      the parsed Status/Version/Date header as JSON (+ container_leg_service)\n"
    "  --site NAME   run only the rows declared for that site (hub | host | container) — one leg of a multi-site run\n"
    "  --unreachable WHY   with --site: emit that site's rows as UNVERIFIABLE without running them (the leg could not be reached)\n"
    "  --rows-from F [F…]  with --verdict/--json: use the row lists in these JSON files (the legs' outputs) instead of running rows;\n"
    "                      refused (exit 64) unless every contract row appears exactly once, with the comparison keys all or none,\n"
    "                      a tri-state match and a known status\n"
)


def main(argv: list[str] | None = None) -> int:
    args, values, unknown = _parse(list(sys.argv[1:] if argv is None else argv))
    if "--help" in args or "-h" in args:
        print(_USAGE, end="")
        return 0
    if "--site" in values and values["--site"] not in SITES:
        unknown.append(f"--site {values['--site']!r} (one of {', '.join(SITES)})")
    if "--unreachable" in values and "--site" not in values:
        unknown.append(
            "--unreachable needs --site (it marks ONE leg unverifiable, never the whole contract)"
        )
    if unknown:
        print(f"unknown flag(s): {' '.join(unknown)}\n{_USAGE}", end="", file=sys.stderr)
        return 64  # EX_USAGE — a typo must never fall through to a contract run
    hdr = parse_header()
    if "--header" in args:
        print(json.dumps({**hdr, "container_leg_service": CONTAINER_LEG_SERVICE}))
        return 0
    if "--verdict" in args:
        try:
            rows = _rows_for(values)
        except _LegRefusedError as exc:
            return _refuse_legs(exc)
        v = verdict(rows, hdr, not_obligated=NOT_OBLIGATED)
        p = v["parity"]
        if p:
            print(
                f"PARITY: {p['agree']} agree / {p['disagree']} disagree / {p['unresolved']} unresolved"
                f" / {p['unverifiable']} UNVERIFIABLE of {p['denominator']} (contract {hdr.get('version')},"
                f" {p['not_obligated']} not obligated)"
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
    try:
        rows = _rows_for(values)
    except _LegRefusedError as exc:
        return _refuse_legs(exc)
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
