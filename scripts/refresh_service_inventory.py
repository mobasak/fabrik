#!/usr/bin/env python3
# AFTER-EDIT: scripts/gather_envs.py scripts/classify_services.py scripts/registry_sync.py
"""Automation orchestrator for the External Services Registry (Phase D) — the cron entry-point.

Under a flock (no overlapping runs): refresh the consolidation (cheap, always), classify ONLY
genuinely-NEW flagged providers (paid — cost-budget-guarded + a seen-set so stuck unknowns are
never re-billed), sync the registry (+ credits), and alert on new-found / failure. Idempotent +
resilient. Cron (documented, operator-installed — NOT auto-installed):

  0 * * * * cd /opt/fabrik && timeout 600 systemd-run --scope -p CPUQuota=50% -p MemoryMax=1G \
      .venv/bin/python scripts/refresh_service_inventory.py >> logs/refresh-services.log 2>&1
"""

from __future__ import annotations

import argparse
import fcntl
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

import registry_sync  # noqa: E402
from classify_services import ALL_ENVS, flagged_providers  # noqa: E402

LOCK = REPO / ".tmp" / "refresh-services.lock"
SEEN = REPO / "secrets" / ".classified-seen.json"
PY = str(REPO / ".venv" / "bin" / "python")

try:
    from libs.alerting import send_alert
except Exception:  # noqa: BLE001 - alerting is best-effort
    send_alert = None
try:
    from libs.cost_budget import check_caps
except Exception:  # noqa: BLE001
    check_caps = None


def _seen() -> set[str]:
    try:
        return set(json.loads(SEEN.read_text(encoding="utf-8")))
    except Exception:  # noqa: BLE001 - missing/corrupt seen-file => treat as empty
        return set()


def _mark_seen(names: list[str]) -> None:
    SEEN.parent.mkdir(parents=True, exist_ok=True)
    SEEN.write_text(json.dumps(sorted(_seen() | set(names))), encoding="utf-8")


def _alert(title: str, body: str) -> None:
    if send_alert:
        try:
            send_alert(title, body, "info")
        except Exception:  # noqa: BLE001
            pass


def _over_budget() -> bool:
    """Defensive cost-budget probe — over only if check_caps clearly says so; else proceed
    (each classify run is independently hard-bounded by the pool's max_cost_usd)."""
    if not check_caps:
        return False
    try:
        res = check_caps(project="service-catalog", pg_conn=None)
        return bool(res and getattr(res, "over_cap", getattr(res, "over", False)))
    except Exception:  # noqa: BLE001
        return False


def run(dry: bool = False) -> int:
    subprocess.run([PY, "scripts/gather_envs.py", "--apply"], cwd=REPO, check=False)
    new = sorted(set(flagged_providers(ALL_ENVS)) - _seen())
    if new and not dry:
        if _over_budget():
            _alert("service-registry: budget cap", f"skipped classify of {len(new)} new providers")
        else:
            subprocess.run(
                [PY, "scripts/classify_services.py", "--apply", "--only", ",".join(new)],
                cwd=REPO, check=False,
            )
            subprocess.run([PY, "scripts/gather_envs.py", "--apply"], cwd=REPO, check=False)
            _mark_seen(new)
            _alert("service-registry: new providers", f"classified {len(new)}: {', '.join(new)}")
    if dry:
        print(f"[dry-run] {len(new)} new flagged providers would be classified: {new}")
        return 0
    stats = registry_sync.sync_registry(fetch_credits=True)
    print(f"refresh: {len(new)} new flagged | synced {stats['services']} services, "
          f"{stats['credit_snapshots']} credit snapshots")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true", help="detect only; write nothing, classify nothing")
    args = ap.parse_args()
    LOCK.parent.mkdir(parents=True, exist_ok=True)
    with open(LOCK, "w", encoding="utf-8") as lf:
        try:
            fcntl.flock(lf, fcntl.LOCK_EX | fcntl.LOCK_NB)  # no-overlap run-lock
        except BlockingIOError:
            print("another refresh is running — skipping (no overlap)")
            return 0
        return run(dry=args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
