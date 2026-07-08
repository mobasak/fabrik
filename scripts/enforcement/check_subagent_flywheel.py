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

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
# so `from libs.subagents import …` resolves when run as a bare script (sys.path[0] is this dir)
sys.path.insert(0, str(PROJECT_ROOT))

DEFAULT_LEDGER = PROJECT_ROOT / ".tmp" / "subagents" / "ledger.jsonl"


def check(ledger_path: Path) -> int:
    if not ledger_path.exists():
        # no pool use (native-only / no run_agents dispatch) → nothing to reconcile
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

    unrecorded = audit_unrecorded(str(ledger_path))
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
