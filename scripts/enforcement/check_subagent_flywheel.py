#!/usr/bin/env python3
# AFTER-EDIT: none
"""Advisory flywheel gate — WARN when the OpenRouter subagent POOL ran work it never recorded.

Every `run_agents` pool worker appends to `<repo>/.tmp/subagents/ledger.jsonl`; `record_agent_run`
writes a local receipt to `receipts.jsonl` **only on a confirmed DB write**. This check reconciles
the two LOCALLY (the `subagent_runs` writer role is INSERT-only, so the gate cannot SELECT the table)
and surfaces any ledger entry with no matching receipt = a pool run that ran but was never
scored+recorded. Native Claude Task subagents never write the ledger, so they are out of scope
(no false positives on GUI / authoritative work).

ADVISORY: this ALWAYS exits 0 (it never blocks the gate); a finding is printed to stdout, which
`final_gate.py`'s `run_optional_check(..., advisory=True)` preserves as a WARN. Escalation to a hard
fail is a dated operator decision (see the registration in final_gate.py).

Usage: `python scripts/enforcement/check_subagent_flywheel.py [ledger.jsonl]`
(default ledger: `<repo>/.tmp/subagents/ledger.jsonl`; receipts co-locate with the ledger).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
# so `from libs.subagents import …` resolves when run as a bare script (sys.path[0] is this dir)
sys.path.insert(0, str(PROJECT_ROOT))

DEFAULT_LEDGER = PROJECT_ROOT / ".tmp" / "subagents" / "ledger.jsonl"

# Above this many changed files, a review that ran ZERO pool subagents is worth an advisory nudge — the
# all-native failure mode (native-only, skipping the pool breadth layer) the ledger↔receipt reconciliation
# is structurally blind to (no pool runs → no ledger → nothing to reconcile). Per 62 § Dispatch policy a
# substantial review runs the pool breadth layer AND native on top, not native-only.
_REVIEW_SURFACE_THRESHOLD = 8


def _changed_file_count() -> int:
    """Files changed since the merge-base with origin/master (this cycle's surface). Fail-safe → 0."""
    try:
        base = (
            subprocess.run(
                ["git", "merge-base", "HEAD", "origin/master"],
                capture_output=True,
                text=True,
                cwd=PROJECT_ROOT,
            ).stdout.strip()
            or "HEAD~1"
        )
        out = subprocess.run(
            ["git", "diff", "--name-only", base, "HEAD"],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
        ).stdout
        return sum(1 for line in out.splitlines() if line.strip())
    except Exception:  # noqa: BLE001 — advisory: a git failure never blocks the gate
        return 0


def _warn_all_native_gap() -> None:
    """Advisory nudge: a substantial changed surface with ZERO pool runs → the pool breadth layer was
    likely skipped (the all-native miss the ledger↔receipt reconciliation cannot see)."""
    changed = _changed_file_count()
    if changed > _REVIEW_SURFACE_THRESHOLD:
        print(
            f"SUBAGENT FLYWHEEL (advisory): {changed} files changed but ZERO pool subagent runs this "
            "cycle — was the pool breadth layer skipped? A substantial review / repo-review / rules-audit "
            "runs pool finders (recall + they record) AND native on top, not native-only "
            "(62-using-subagents.md § Dispatch policy). All-native lands nothing in the flywheel."
        )


def check(ledger_path: Path) -> int:
    if not ledger_path.exists():
        # no pool use at all (native-only / no run_agents dispatch) → nothing to reconcile. But an absent
        # ledger on a BIG changed surface is exactly the all-native gap (a substantial review with no pool
        # breadth layer) the ledger↔receipt reconciliation is structurally blind to. Nudge on it.
        _warn_all_native_gap()
        return 0
    try:
        from libs.subagents import audit_unrecorded
    except ImportError:
        # the receipt/audit ENHANCE isn't vendored in this project yet — skip rather than error,
        # so the fleet-synced check ships everywhere and activates once a project re-vendors.
        print(
            "SUBAGENT FLYWHEEL (advisory): libs.subagents.audit_unrecorded not available "
            "(re-vendor the subagents module to enable this check) — skipping."
        )
        return 0

    try:
        unrecorded = audit_unrecorded(str(ledger_path))
    except Exception as exc:  # noqa: BLE001 — advisory MUST never block the gate: an unreadable /
        # corrupt / bad-encoding ledger (read_text can raise OSError/UnicodeDecodeError) must degrade
        # to a skip, not a non-zero exit that run_optional_check would treat as a blocking failure.
        print(
            "SUBAGENT FLYWHEEL (advisory): could not reconcile the pool ledger "
            f"({type(exc).__name__}) — skipping."
        )
        return 0
    if not unrecorded:
        return 0

    print(
        f"SUBAGENT FLYWHEEL (advisory): {len(unrecorded)} pool run(s) ran but were never "
        "scored+recorded (ledger − receipts):"
    )
    for e in unrecorded:
        agent_id = e.get("agent_id", "?")
        model = e.get("model", "?")
        task_type = e.get("task_type", "?")
        print(
            f"  - {agent_id} (model={model}, task_type={task_type}) — "
            "owed record_agent_run(spec, result) after you scored it"
        )
    print(
        "Fix: every run_agents pool worker owes record_agent_run(spec, result) + results_table "
        "(see 62-using-subagents.md § Report every pool run). A native Task subagent produces no "
        "AgentResult and is never in this list."
    )
    return 0


def main(argv: list[str]) -> int:
    ledger_path = Path(argv[1]) if len(argv) > 1 else DEFAULT_LEDGER
    return check(ledger_path)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
