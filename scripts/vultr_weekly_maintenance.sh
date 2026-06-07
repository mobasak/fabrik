#!/usr/bin/env bash
# Phase 6 — weekly Vultr maintenance (orphan cleanup + cost report).
# Install in WSL crontab, e.g.:
#   0 7 * * 1 /opt/fabrik/scripts/vultr_weekly_maintenance.sh >> /var/log/fabrik-vultr.log 2>&1
#
# - `fabrik vultr cleanup --yes` destroys disposable instances past destroy_after
#   (orphan recovery for any drill the try/finally missed) + GCs old records.
# - `fabrik vultr cost` reports this month's charges + tracked run-rate.
set -euo pipefail

cd /opt/fabrik
echo "=== fabrik vultr weekly maintenance $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="

echo "--- cleanup (destroy overdue disposables) ---"
python3 -m fabrik.cli vultr cleanup --yes || echo "cleanup failed"

echo "--- cost ---"
python3 -m fabrik.cli vultr cost || echo "cost failed"

echo "--- reconcile (drift check) ---"
python3 -m fabrik.cli vultr reconcile || echo "reconcile failed"
