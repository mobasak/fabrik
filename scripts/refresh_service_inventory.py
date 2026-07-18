#!/usr/bin/env python3
# AFTER-EDIT: scripts/gather_envs.py scripts/classify_services.py scripts/registry_sync.py
"""Automation orchestrator for the External Services Registry (Phase D) — the cron entry-point.

Under a flock (no overlapping runs): refresh the consolidation (cheap, always), classify ONLY
genuinely-NEW flagged providers (paid — batch-bounded per run + a seen-set so stuck unknowns are
never re-billed), sync the registry (+ credits), and alert on new-found / failure. Idempotent +
resilient. Cron (documented, operator-installed — NOT auto-installed):

  0 * * * * cd /opt/fabrik && timeout 600 systemd-run --scope -p CPUQuota=50% -p MemoryMax=1G \
      .venv/bin/python scripts/refresh_service_inventory.py >> logs/refresh-services.log 2>&1
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
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

MAX_NEW_PER_RUN = 10  # bound the paid classify per tick; with the pool's per-unit max_cost_usd
#                       ($0.20) this caps spend at ~$2/run — the real budget bound (the vendored
#                       cost-budget module needs a wal_path + caps not provisioned for this host tool).

try:
    from libs.alerting import send_alert
except Exception:  # noqa: BLE001 - alerting is best-effort
    send_alert = None


def _seen() -> set[str]:
    try:
        return set(json.loads(SEEN.read_text(encoding="utf-8")))
    except Exception:  # noqa: BLE001 - missing/corrupt seen-file => treat as empty
        return set()


def _mark_seen(names: list[str]) -> None:
    SEEN.parent.mkdir(parents=True, exist_ok=True)
    tmp = SEEN.with_name(SEEN.name + ".tmp")  # atomic write
    tmp.write_text(json.dumps(sorted(_seen() | set(names))), encoding="utf-8")
    os.replace(tmp, SEEN)


def _alert(title: str, body: str) -> None:
    if send_alert:
        try:
            send_alert(title, body, "info")
        except Exception:  # noqa: BLE001
            pass


def run(dry: bool = False) -> int:
    if not dry:  # --dry-run must NOT mutate all-envs.env — detect against the existing file
        subprocess.run([PY, "scripts/gather_envs.py", "--apply"], cwd=REPO, check=False)
    new = sorted(set(flagged_providers(ALL_ENVS)) - _seen())
    if dry:
        print(f"[dry-run] {len(new)} new flagged providers would be classified: {new}")
        return 0
    if new:
        batch = new[:MAX_NEW_PER_RUN]  # bound the paid run
        cp = subprocess.run(
            [PY, "scripts/classify_services.py", "--apply", "--only", ",".join(batch)],
            cwd=REPO,
            check=False,
        )
        if cp.returncode == 0:  # mark seen ONLY on success — a crashed classify retries next tick
            subprocess.run([PY, "scripts/gather_envs.py", "--apply"], cwd=REPO, check=False)
            _mark_seen(batch)
            _alert(
                "service-registry: new providers", f"classified {len(batch)}: {', '.join(batch)}"
            )
        else:
            _alert(
                "service-registry: classify FAILED",
                f"exit {cp.returncode}; {len(batch)} providers left for retry",
            )
    # prune=True is deliberate: the hourly job keeps the registry consistent with all-envs.env
    # (orphans from renamed providers deleted). Safe: gather writes atomically (os.replace) and
    # this whole run holds the flock, so a partial file is never observable.
    try:
        stats = registry_sync.sync_registry(fetch_credits=True, prune=True)
    except Exception as exc:  # noqa: BLE001 - the cron must ALERT, not die silently every hour
        # Most likely the bounded-prune refusal (a legitimate >20% recatalog trips it too).
        # Alert the operator with the escape hatch instead of wedging quietly in a logfile.
        _alert(
            "service-registry: sync FAILED",
            f"{exc} — if this is a legitimate mass recatalog, re-run once with "
            "REGISTRY_PRUNE_FORCE=1 python scripts/registry_sync.py",
        )
        print(f"sync FAILED: {exc}")
        return 1
    print(
        f"refresh: {len(new)} new flagged | synced {stats['services']} services, "
        f"{stats['credit_snapshots']} credit snapshots"
    )
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--dry-run", action="store_true", help="detect only; write nothing, classify nothing"
    )
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
