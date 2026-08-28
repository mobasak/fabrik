#!/usr/bin/env python3
# AFTER-EDIT: tests/test_check_subagent_flywheel.py
"""Subagent-pool enforcement gate — two layers.

LAYER 1 (BLOCKING — "pool-or-declare"): a substantial CODE change (committed + staged) with ZERO pool
subagent runs THIS cycle FAILS the gate (exit 1) — unless the work declares a native-only exception via
a `NO-POOL: <reason>` line in ANY in-cycle commit message (`base..HEAD`) or a `FABRIK_NO_POOL` env var
(pre-commit staged work, whose commit doesn't exist yet, uses the env var). This is the teeth
that make `62-using-subagents.md` § Dispatch policy's pool-default real across EVERY agent
(Kilo / Cascade / Claude) — prose can't be enforced, a gate can. Operator-approved 2026-07-10.

LAYER 2 (ADVISORY — never blocks): reconciles the local pool ledger vs receipts and WARNs on any pool
run that ran but was never `record_agent_run`-recorded.

⚠️ FAIL-SAFE INVARIANT: the block fires ONLY when {code files > threshold, zero in-cycle pool rows, no
NO-POOL declaration} are ALL confidently determined. ANY git failure, parse error, or exception in any
helper degrades to EXIT 0 — never a false block. A blocking gate that false-blocks the whole fleet is
worse than one that occasionally lets a violation through, so every ambiguous case leans no-block.
One deliberate addition to the blocking set (2026-08-28): in-cycle rows found ONLY at the nested
repo=<name> trap path ALSO block — the pool ran, but into a location this gate and pick_models never
read, and a broken recording location is repaired now (message names the 30-second merge), never
papered green.

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
    """AUTHOR time (epoch seconds) of the merge-base = the start of this cycle. None on failure → the
    in-cycle filter counts ALL ledger rows (lenient / fail-safe). We use ``%at`` (author date), NOT
    ``%ct`` (committer date): a rebase / ``--amend`` of the base commit ADVANCES its committer date,
    which would push ``since_epoch`` past legitimate this-cycle pool runs and filter them out → a false
    block (the direction the fail-safe forbids). Author date is preserved across rebase, and if it's
    skewed it skews OLD (→ counts more rows → false-pass, the tolerated direction)."""
    base = _resolve_base()
    if base is None:
        return None
    try:
        return float((_git(["show", "-s", "--format=%at", base]) or "").strip())
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
            if not isinstance(rec, dict):
                # a non-object JSON line (e.g. `[]`, `123`, `"x"`) has no .get — count it leniently
                # and move on, rather than letting the AttributeError escape to the 1_000_000 sentinel
                # (which would silently disable the block for the ENTIRE run, not just this line).
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
    ``NO-POOL:`` trailer in ANY commit message across THIS cycle (``base..HEAD``, not just HEAD). The
    surface (:func:`_changed_code_files`) spans every commit since the merge-base, and the documented
    workflow commits PER PHASE (CLAUDE.md) — so a declaration made on phase A's commit must still count
    when HEAD is phase C. Reading only ``git log -1`` (HEAD) missed it → a false block. When the base
    can't be resolved we scan ALL reachable commit messages (symmetric with the epoch/ledger check,
    which counts ALL rows when the cycle can't be bounded — both go maximally lenient). A git failure to
    READ → True (fail-safe: never block on a git failure). Any other error → True."""
    try:
        if os.environ.get("FABRIK_NO_POOL", "").strip():
            return True
        base = _resolve_base()
        # Scan EVERY in-cycle commit message, not just HEAD (per-phase commits declare once, on an
        # earlier commit). `base..HEAD` is "" when HEAD == base (nothing committed this cycle) → the
        # env var is then the only escape, which is correct (an unwritten commit message can't be read).
        # When base can't be resolved we scan ALL reachable commit messages (`git log --format=%B`, no
        # range) — SYMMETRIC with _merge_base_epoch/None → _in_cycle_pool_runs counting ALL ledger rows:
        # if the cycle can't be bounded, both the pool-run check and the declaration check go maximally
        # lenient (lean no-block), so an earlier commit's declaration is never missed into a false block.
        args = (
            ["log", "--format=%B", f"{base}..HEAD"] if base is not None else ["log", "--format=%B"]
        )
        msg = _git(args)
        if msg is None:
            return True  # couldn't read the commits (git failure) → fail-safe, don't block
        # Case-INSENSITIVE, hyphen-OR-underscore: recognizes `NO-POOL:`, `no-pool:`, `NO_POOL:` (mirrors
        # the FABRIK_NO_POOL env var's own spelling), `Docs: NO-POOL:`, `NO-POOL :` — but NOT `ANO-POOL:`
        # (left context must be start-of-string or whitespace). Lenient on the escape (lean no-block).
        return bool(re.search(r"(?:^|\s)NO[-_]POOL\s*:", msg, re.IGNORECASE))
    except Exception:  # noqa: BLE001
        return True


def _pool_available() -> bool:
    """The gate enforces pool use ONLY where the pool can actually be dispatched. The subagents pool is
    **vendored** into a project (``libs/subagents/`` — copied from ``/opt/fabrik-lib/subagents`` per the
    flywheel workflow, `.windsurf/workflows/subagent-runs-flywheel.md`), and the commands import it as
    ``from libs.subagents import …``. So "dispatchable here" == "vendored here": a project (or the hub,
    which carries its own ``libs/subagents``) that has NOT vendored the module can't ``from libs.subagents
    import`` → don't block (fail-safe: can't dispatch → can't enforce)."""
    return (PROJECT_ROOT / "libs" / "subagents" / "__init__.py").is_file()


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
        # Partial-split edge (review 2026-08-28): rows in BOTH ledgers pass on the real
        # ones — but the nested rows would strand silently until the next zero cycle.
        # The ⚠ prefix routes this into final_gate --json `warnings` on a green exit.
        stray = PROJECT_ROOT / PROJECT_ROOT.name / ".tmp" / "subagents" / "ledger.jsonl"
        if stray.exists():
            print(
                f"⚠ SUBAGENT FLYWHEEL: gate passes on the real ledger, but a nested stray "
                f"exists at {stray} — rows there are invisible to this gate and to "
                f"pick_models. Merge them into the real ledger and delete the stray dir "
                f"(repo= misuse trap, 01M0Z2B420)."
            )
        return 0  # the pool WAS dispatched this cycle
    # The nested-path trap BEFORE the zero-claim: `fanout(repo="<name>")` called from inside
    # the repo resolves the ledger to <root>/<name>/.tmp/subagents/ — the runs HAPPEN, this
    # gate reads the real path, and "ZERO recorded" pushes the agent toward a false NO-POOL
    # declaration (job-agent 01M0Z2B420; fleet sweep found live strays in fabrik, transdoc,
    # tryton-crm). When in-cycle rows exist at the nested path, say THAT — the remedy is a
    # 30-second merge, not a declaration.
    nested = PROJECT_ROOT / PROJECT_ROOT.name / ".tmp" / "subagents" / "ledger.jsonl"
    if nested.exists() and _in_cycle_pool_runs(nested, _merge_base_epoch()) > 0:
        real = PROJECT_ROOT / ".tmp" / "subagents" / "ledger.jsonl"
        print(
            f"SUBAGENT FLYWHEEL (BLOCKING): pool runs WERE recorded this cycle — into the "
            f"nested-path trap {nested}, which this gate does not read. Cause: a dispatch "
            f'passed repo="{PROJECT_ROOT.name}" (a bare name, joined to CWD) instead of the '
            f"project ROOT path. Recover: append the nested rows to {real}, delete the stray "
            f"{nested.parent.parent.parent} directory, and pass repo= as an absolute root "
            "from now on. Do NOT declare NO-POOL — the pool ran."
        )
        return 1
    print(
        f"SUBAGENT FLYWHEEL (BLOCKING): {code} code files changed this cycle but ZERO OpenRouter pool "
        "subagent runs were recorded — the pool-default review/implement fan-out was skipped "
        "(62-using-subagents.md § Dispatch policy). Agent-agnostic: Kilo, Cascade, and Claude all hit it.\n"
        "Fix ONE of:\n"
        "  • dispatch the pool for this work — a review/implement fan-out via "
        "`from libs.subagents import fanout, run_agents, pick_models` (vendor it first if absent: "
        "`cp -r /opt/fabrik-lib/subagents/subagents/. ./libs/subagents/` — see "
        "`.windsurf/workflows/subagent-runs-flywheel.md`); it records to the flywheel — then re-run the gate; OR\n"
        "  • if this work is genuinely native-only (mechanical rename, trivial fix, GUI-only), declare it: "
        "a `NO-POOL: <reason>` line in the commit message, or `FABRIK_NO_POOL='<reason>'`."
    )
    return 1


def _pg_driver_importable() -> bool:
    """Can THIS interpreter import the pg sink's lazy optional driver? Approximates the
    recorder's interpreter (the gate runs under the project's venv, same as fanout does).
    Fail-open: an unexpected probe error reads as importable — never a false diagnosis."""
    try:
        import importlib.util

        return importlib.util.find_spec("psycopg") is not None
    except Exception:  # noqa: BLE001 — a broken probe proves nothing
        return True


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

    # Name the CAUSE when it is the environment, not the agent: a repo whose .env carries no
    # SUBAGENT_RUNS_DSN cannot record ANY run — record_agent_run fail-opens False silently, so
    # every dispatch lands here and score() later refuses with a misleading "project=None"
    # (job-agent 01M12K8RRD; fleet survey 2026-08-28: the DSN is provisioned in some repos,
    # absent in others). Telling the agent to "score each run" in that state is unactionable.
    # The DSN is recordable if it resolves via ANY layer the runtime's load_env() honors, in its
    # precedence order: process env → the repo .env (nearest, walking up) → the fleet-wide USER-level
    # file (~/.config/fabrik/subagents.env, or $SUBAGENTS_ENV_FILE). The last layer is the one this
    # check used to MISS: a repo with a clean .env still records because the operator set the DSN once
    # in the shared file (_dotenv.py: "set it there ONCE and EVERY project's pool picks it up"). Omitting
    # it made this advisory fire "UNRECORDABLE — ask infra" at every fallback-provisioned repo — a false
    # alarm that cost a cross-agent finding (intel 01M12SZVRD, 2026-08-28: transdoc has no .env yet 64
    # rows recorded that day via the fallback). We reuse the module's OWN path resolver so the check and
    # the runtime can never drift on where the shared file lives.
    def _dsn_in_env_file(path) -> bool:
        try:
            # Normalize each line the way the runtime parser does (_dotenv.py::_parse_env_text): strip
            # a leading BOM (review round 1: a BOM broke startswith and read a provisioned repo as
            # unrecordable) + surrounding whitespace + a leading `export `. Without this the check
            # disagrees with what load_env actually loads: `export SUBAGENT_RUNS_DSN=…` or an indented
            # line records fine at runtime yet the raw startswith misses it, re-firing the exact false
            # "UNRECORDABLE" this advisory exists to avoid (native review 2026-08-28).
            for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
                line = raw.lstrip("﻿").strip()
                if line.startswith("export "):
                    line = line[len("export ") :].lstrip()
                if line.startswith("SUBAGENT_RUNS_DSN="):
                    val = line.split("=", 1)[1].strip()
                    # A value that is empty or begins with `#` is NOT loaded by the runtime
                    # (_parse_env_text treats a `#`-leading value as a commented-out placeholder →
                    # empty → skipped), so it is genuinely unrecordable — do not count it as present.
                    if val and not val.startswith("#"):
                        return True
            return False
        except OSError:
            return True  # unreadable file proves nothing — do not claim absence

    # Resolve the fleet-wide file inline — mirrors libs/subagents/_dotenv.py::_shared_env_path
    # ($SUBAGENTS_ENV_FILE override, else ${XDG_CONFIG_HOME:-~/.config}/fabrik/subagents.env). Inlined,
    # not imported, on purpose: this enforcement check must not hard-depend on the runtime package being
    # importable (the flywheel tests mock libs.subagents), and the path convention is stable.
    shared = None
    try:
        override = os.environ.get("SUBAGENTS_ENV_FILE")
        if override:
            shared = Path(override)
        else:
            xdg = os.environ.get("XDG_CONFIG_HOME") or os.path.join(
                os.path.expanduser("~"), ".config"
            )
            shared = Path(xdg) / "fabrik" / "subagents.env"
    except (
        KeyError,
        RuntimeError,
    ):  # HOME unset + no passwd entry (minimal container) → skip layer
        shared = None
    env_file = PROJECT_ROOT / ".env"
    has_dsn = (
        bool(os.environ.get("SUBAGENT_RUNS_DSN", "").strip())
        or (env_file.exists() and _dsn_in_env_file(env_file))
        or (shared is not None and shared.is_file() and _dsn_in_env_file(shared))
    )
    if not has_dsn:
        print(
            f"SUBAGENT FLYWHEEL (advisory): {len(unrecorded)} pool run(s) are UNRECORDABLE, not "
            "unscored — this repo's .env has no SUBAGENT_RUNS_DSN, so record_agent_run fail-opens "
            "False on every call and batch.score() refuses each unit as an orphan. Scoring harder "
            "cannot fix this: provision the DSN (hub-side: the fabrik_analytics per-project "
            "INSERT-only role — ask infra), then re-score from the ledger."
            # Both-absent (review 2026-08-28 round 1): fixing the DSN alone would still not
            # record — say so now, not on the next red run.
            + (
                ""
                if _pg_driver_importable()
                else " NOTE: `psycopg` is ALSO missing from this "
                "interpreter — provisioning the DSN alone will not make runs recordable."
            )
        )
        return
    # Third checkable cause, the one two prior diagnoses missed because no message listed it
    # (job-agent 01M13YGMJC): the DSN resolves but the OPTIONAL pg driver is not installed in
    # this interpreter — pg_ledger's sink lazy-imports psycopg (pg_ledger.py:323) and
    # fail-opens without it. Cheapest check of all, so it is named before "score each run".
    if not _pg_driver_importable():
        print(
            f"SUBAGENT FLYWHEEL (advisory): {len(unrecorded)} pool run(s) are UNRECORDABLE, not "
            "unscored — the DSN resolves but `psycopg` is not importable in this interpreter, so "
            "pg_ledger's sink fail-opens on every record_agent_run call. No DSN or database state "
            "can matter until the driver exists: add `psycopg` to this project's deps (a deps "
            "change needs its owner's authorization), then re-score from the ledger."
        )
        return
    print(
        f"SUBAGENT FLYWHEEL (advisory): {len(unrecorded)} pool run(s) ran but were never "
        "scored+recorded (ledger − receipts) — each owes record_agent_run(spec, result). "
        "A dispatch is guaranteed, the back-fill is not: skipped scoring is the flywheel's "
        "single largest leak (done-rows measured 40.9% scored, 2026-08-12), and /fabrik-review's "
        "round-close now REQUIRES the back-fill before a round counts as closed. (This stays "
        "WARN-tier: ledger rows carry no session id, so an ERROR would red one session's gate "
        "on a sibling's rows — escalation lands when the module stamps session identity, "
        "requested upstream 2026-08-12.)"
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
