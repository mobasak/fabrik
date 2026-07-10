#!/usr/bin/env python3
# AFTER-EDIT: tests/test_check_subagent_flywheel.py
"""Subagent-pool enforcement gate — two layers.

LAYER 1 (BLOCKING — "pool-or-declare"): a substantial CODE change (committed + staged) with ZERO pool
subagent runs THIS cycle FAILS the gate (exit 1) — unless the work declares a native-only exception via
a `NO-POOL: <reason>` line in the HEAD commit message or a `FABRIK_NO_POOL` env var. This is the teeth
that make `62-using-subagents.md` § Dispatch policy's pool-default real across EVERY agent
(Kilo / Cascade / Claude) — prose can't be enforced, a gate can. Operator-approved 2026-07-10.

LAYER 2 (ADVISORY — never blocks): reconciles the local pool ledger vs receipts and WARNs on any pool
run that ran but was never `record_agent_run`-recorded.

⚠️ FAIL-SAFE INVARIANT: the block fires ONLY when {code files > threshold, zero in-cycle pool rows, no
NO-POOL declaration} are ALL confidently determined. ANY git failure, parse error, or exception in any
helper degrades to EXIT 0 — never a false block. A blocking gate that false-blocks the whole fleet is
worse than one that occasionally lets a violation through, so every ambiguous case leans no-block.

Only COMMITTED (since the merge-base) + STAGED files count as "this cycle's work" — NOT the unstaged
working tree, which in a shared clone carries other agents' WIP + build artifacts (would false-block).

The `subagent_runs` writer role is INSERT-only (the gate cannot SELECT), so "this cycle's pool use" is
read from the LOCAL ledger, filtered to entries newer than the merge-base commit (fixes the stale-ledger
self-disable: a pool run from a PRIOR cycle does not satisfy THIS cycle).

Usage: `python scripts/enforcement/check_subagent_flywheel.py [ledger.jsonl]`
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
# so `from libs.subagents import …` resolves when run as a bare script (sys.path[0] is this dir)
sys.path.insert(0, str(PROJECT_ROOT))

DEFAULT_LEDGER = PROJECT_ROOT / ".tmp" / "subagents" / "ledger.jsonl"

# Above this many changed CODE files, a cycle with ZERO pool runs and no NO-POOL declaration is a
# blocking violation. Docs / config / data files are excluded (they need no pool review).
_BLOCK_CODE_THRESHOLD = 8
_CODE_EXTS = frozenset(
    {
        ".py",
        ".js",
        ".ts",
        ".tsx",
        ".jsx",
        ".mjs",
        ".cjs",
        ".go",
        ".rs",
        ".java",
        ".kt",
        ".swift",
        ".rb",
        ".php",
        ".sql",
        ".sh",
        ".bash",
        ".c",
        ".cc",
        ".cpp",
        ".h",
        ".hpp",
        ".cs",
        ".scala",
        ".clj",
        ".cljs",
        ".ex",
        ".exs",
        ".lua",
        ".dart",
        ".jl",
        ".r",
        ".vue",
        ".svelte",
        ".m",
        ".mm",
    }
)


def _git(args: list[str]) -> str | None:
    """Run a git command from PROJECT_ROOT; stdout on success, else None (fail-safe)."""
    try:
        r = subprocess.run(["git", *args], capture_output=True, text=True, cwd=PROJECT_ROOT)
        return r.stdout if r.returncode == 0 else None
    except Exception:  # noqa: BLE001 — a git failure must never crash the gate
        return None


def _resolve_base() -> str | None:
    """The merge-base to diff committed work against — origin/master, else origin/main. None if neither
    resolves (caller then counts only STAGED work — fail-safe: on a non-master/main repo a MISS beats a
    false-block). `@{upstream}` is deliberately NOT a fallback: a distant tracked upstream yields an ancient
    merge-base that over-counts the surface → false-block (the direction the fail-safe forbids)."""
    for ref in ("origin/master", "origin/main"):
        mb = (_git(["merge-base", "HEAD", ref]) or "").strip()
        if mb:
            return mb
    return None


def _changed_code_files() -> int | None:
    """Count changed CODE files that are part of THIS cycle's work: committed-since-merge-base ∪ STAGED.
    Unstaged working-tree files are EXCLUDED (other agents' WIP / build artifacts would false-block).
    Returns None if git can't be interrogated — the caller then does NOT block (fail-safe)."""
    names: set[str] = set()
    staged = _git(["diff", "--cached", "--name-only"])  # the imminent commit
    if staged is None:
        return None  # git failure → unknown surface → fail-safe no-block
    names.update(line.strip() for line in staged.splitlines() if line.strip())
    base = _resolve_base()
    if base is not None:  # committed since the branch point
        committed = _git(["diff", "--name-only", base, "HEAD"])
        if committed is None:
            return None
        names.update(line.strip() for line in committed.splitlines() if line.strip())
    return sum(1 for f in names if Path(f).suffix in _CODE_EXTS)


def _merge_base_epoch() -> float | None:
    """Commit time (epoch seconds) of the merge-base = the start of this cycle. None on failure → the
    in-cycle filter counts ALL ledger rows (lenient / fail-safe)."""
    base = _resolve_base()
    if base is None:
        return None
    try:
        return float((_git(["show", "-s", "--format=%ct", base]) or "").strip())
    except (TypeError, ValueError):
        return None


def _in_cycle_pool_runs(ledger_path: Path, since_epoch: float | None) -> int:
    """Pool ledger rows whose ts is at/after ``since_epoch`` (this cycle). ``since_epoch=None`` counts
    every row (can't bound the cycle → lenient). Corrupt lines / unparseable ts COUNT (a real run must
    never be undercounted → lean no-block). Any read trouble → a large sentinel (no block)."""
    try:
        if not ledger_path.exists():
            return 0
        n = 0
        for line in ledger_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except Exception:  # noqa: BLE001 — a corrupt line might be a real run → count it (lenient)
                n += 1
                continue
            if since_epoch is None:
                n += 1
                continue
            ts = rec.get("ts")
            try:
                if isinstance(ts, str):
                    dt = datetime.fromisoformat(ts)
                    if (
                        dt.tzinfo is None
                    ):  # naive ISO ts is AMBIGUOUS (UTC? local?) — count it (lenient)
                        n += 1
                        continue
                    row_epoch = dt.timestamp()
                else:
                    row_epoch = float(ts)
            except Exception:  # noqa: BLE001 — unparseable ts → count it (lenient)
                n += 1
                continue
            if row_epoch >= since_epoch:
                n += 1
        return n
    except Exception:  # noqa: BLE001 — unexpected trouble → large sentinel → no block
        return 1_000_000


def _declared_no_pool() -> bool:
    """True if the work consciously declared a native-only exception: a ``FABRIK_NO_POOL`` env var, or a
    line-anchored ``NO-POOL:`` trailer in the HEAD commit message. A git failure to READ the message → True
    (fail-safe: never block on a git failure). Any other error → True."""
    try:
        if os.environ.get("FABRIK_NO_POOL", "").strip():
            return True
        msg = _git(["log", "-1", "--format=%B"])
        if msg is None:
            return True  # couldn't read the commit (git failure) → fail-safe, don't block
        # word-boundary match: recognizes `NO-POOL:`, `Docs: NO-POOL:`, `NO-POOL :` — but NOT `ANO-POOL:`.
        # Lenient on the escape (lean no-block): a declaration anywhere at a word boundary counts.
        return bool(re.search(r"(?:^|\s)NO-POOL\s*:", msg))
    except Exception:  # noqa: BLE001
        return True


def _pool_available() -> bool:
    """The gate enforces pool use ONLY where the pool can actually be dispatched. The subagents pool is a
    DEV-TIME tool (review / test-authoring) — never app runtime (zero runtime callers), so agents use it
    straight from the canonical hub module ``/opt/fabrik-lib/subagents`` (always present where the coding
    agents run — no per-project vendor or fleet-sync needed) OR a local vendor copy. Present in NEITHER
    (e.g. a CI/container gate off the dev host) → don't block (fail-safe: can't dispatch → can't enforce)."""
    return (
        Path("/opt/fabrik-lib/subagents/subagents/__init__.py").is_file()
        or (PROJECT_ROOT / "libs" / "subagents" / "__init__.py").is_file()
    )


def _pool_or_declare(ledger_path: Path) -> int:
    """LAYER 1 (blocking). Returns 1 to FAIL the gate, else 0. Every branch fail-safes to 0."""
    if not _pool_available():
        return 0  # project isn't pool-equipped (no libs/subagents) → can't dispatch → don't block
    code = _changed_code_files()
    if code is None or code <= _BLOCK_CODE_THRESHOLD:
        return 0  # git unknown, or not a substantial code change → not a violation
    if _declared_no_pool():
        print(
            f"SUBAGENT FLYWHEEL: {code} code files changed with no pool run this cycle, but a NO-POOL "
            "declaration is present — allowed (native-only, on the record)."
        )
        return 0
    if _in_cycle_pool_runs(ledger_path, _merge_base_epoch()) > 0:
        return 0  # the pool WAS dispatched this cycle
    print(
        f"SUBAGENT FLYWHEEL (BLOCKING): {code} code files changed this cycle but ZERO OpenRouter pool "
        "subagent runs were recorded — the pool-default review/implement fan-out was skipped "
        "(62-using-subagents.md § Dispatch policy). Agent-agnostic: Kilo, Cascade, and Claude all hit it.\n"
        "Fix ONE of:\n"
        "  • dispatch the pool for this work — a review/implement fan-out via fanout(...) / run_agents(...) "
        "imported from the hub module (no vendor needed): "
        "sys.path.insert(0, '/opt/fabrik-lib/subagents'); from subagents import fanout, pick_models "
        "(it records to the flywheel), then re-run the gate; OR\n"
        "  • if this work is genuinely native-only (mechanical rename, trivial fix, GUI-only), declare it: "
        "a `NO-POOL: <reason>` line in the commit message, or `FABRIK_NO_POOL='<reason>'`."
    )
    return 1


def _warn_unrecorded(ledger_path: Path) -> None:
    """LAYER 2 (advisory, never blocks): WARN on any pool run never record_agent_run-recorded."""
    if not ledger_path.exists():
        return
    try:
        from libs.subagents import audit_unrecorded
    except ImportError:
        return
    try:
        unrecorded = audit_unrecorded(str(ledger_path))
    except Exception:  # noqa: BLE001 — corrupt/unreadable ledger → skip (advisory never blocks)
        return
    if not unrecorded:
        return
    print(
        f"SUBAGENT FLYWHEEL (advisory): {len(unrecorded)} pool run(s) ran but were never "
        "scored+recorded (ledger − receipts) — each owes record_agent_run(spec, result):"
    )
    for e in unrecorded:
        print(
            f"  - {e.get('agent_id', '?')} (model={e.get('model', '?')}, task_type={e.get('task_type', '?')})"
        )


def check(ledger_path: Path) -> int:
    # LAYER 1 — blocking pool-or-declare (its own bug never blocks the gate).
    try:
        verdict = _pool_or_declare(ledger_path)
    except Exception:  # noqa: BLE001 — fail-safe: never false-block on the check's own error
        verdict = 0
    # LAYER 2 — advisory unrecorded-run reconciliation (never affects the verdict).
    try:
        _warn_unrecorded(ledger_path)
    except Exception:  # noqa: BLE001
        pass
    return verdict


def main(argv: list[str]) -> int:
    ledger_path = Path(argv[1]) if len(argv) > 1 else DEFAULT_LEDGER
    return check(ledger_path)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
