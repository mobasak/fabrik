#!/usr/bin/env python3
# AFTER-EDIT: scripts/sysadmin/kaizen_shrink_audit.py, tests/test_kaizen_shrink_audit.py | none
"""The M0 immune registry — artifacts EXCLUDED from deletion candidacy.

Spec § M0 (final-panel amendment, operator-approved): rarely-fired safety machinery
presents as "unused" precisely because it works. A Stop hook that never blocks, a DR
backup nobody restores, a decommission runbook run twice a year — zero usage-evidence is
what SUCCESS looks like for these, so the audit must never auto-mark them ``candidate``.

Immunity blocks AUTO-candidacy only. Every immune row still renders with its full
evidence in the report, and the operator's ruling pass remains the final say on
everything — including immune rows (the plan's still-open item 1 resolution).

Members and their one-line justifications live in ``JUSTIFICATIONS``; ``IMMUNE`` is its
key set. Two membership sources, both enumerable:

- NAMED entries — reviewed by hand below.
- The never-route class — every ``scripts/enforcement/check_*.py`` stem, enumerated at
  import time from the directory itself (``check_plan_tickets.py::NEVER_ROUTE_PREFIXES``
  puts the whole dir under never-route). Enumerated live rather than copied because a
  frozen 57-name list drifts the day check #58 lands (Ground-governance-enumerations
  rule: copy from the registry, never memory).
"""

from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

_NEVER_ROUTE_JUSTIFICATION = (
    "under never-route prefix scripts/enforcement/ (check_plan_tickets.py"
    "::NEVER_ROUTE_PREFIXES) — gate machinery; usage-evidence cannot prove a guard useless"
)

_NAMED: dict[str, str] = {
    # rare-by-design commands (plan § Phase B step 1)
    "fabrik-decommission": "rare-by-design destructive runbook — invoked only when a service dies",
    "fabrik-upstream": "rare-by-design — fires only when a vendored fabrik-lib fix must go upstream",
    # the Stop hook: the enforcement backbone (hooks-index.md § 1)
    "final_gate_stop.py": "the Stop hook — blocks unfinished exits; firing rarely IS its success",
    # never-route named script (check_plan_tickets.py::NEVER_ROUTE_PREFIXES)
    "final_gate.py": "never-route named path — the completion gate every task runs through",
    # DR / backup / guard crons (crontab -l, 2026-08-19; census keys = the matched path)
    "/opt/fabrik/scripts/dr_env_backup.sh": "DR backup — restore-day machinery; unused = healthy",
    "/opt/fabrik/scripts/dr_env_recovery_test.sh": "DR recovery drill — proves the backup restores",
    "/opt/fabrik/scripts/dr_claude_backup.sh": "DR backup of ~/.claude to the private store",
    "/opt/fabrik/scripts/wip_backup.sh": "the wip-net — the only protection for uncommitted work",
    "/opt/fabrik/scripts/sysadmin/sync-claude-accounts-to-fleet.sh": (
        "credential DR sync to the VPS fleet — loss surface, not a usage surface"
    ),
    "/opt/fabrik/scripts/sysadmin/liveness_audit.py": (
        "the guard's guard — proves the scheduled surfaces themselves are alive"
    ),
}


def _never_route_stems() -> dict[str, str]:
    d = REPO / "scripts" / "enforcement"
    if not d.is_dir():
        return {}
    return {f.stem: _NEVER_ROUTE_JUSTIFICATION for f in d.glob("check_*.py")}


def _with_basename_aliases(entries: dict[str, str]) -> dict[str, str]:
    """Path-shaped entries also register under their basename — census cron keys drift
    between absolute (`/opt/fabrik/scripts/x.sh`) and relative (`scripts/x.sh`) forms
    depending on how the crontab line names the script (live false positive:
    liveness_audit.py listed as a candidate past its own absolute-path entry)."""
    out = dict(entries)
    for k, v in entries.items():
        if "/" in k:
            out.setdefault(Path(k).name, v)
    return out


JUSTIFICATIONS: dict[str, str] = _with_basename_aliases({**_never_route_stems(), **_NAMED})
IMMUNE: frozenset[str] = frozenset(JUSTIFICATIONS)
