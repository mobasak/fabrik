# Fabrik systemd units

User-installable systemd timers + services for operator-side recurring jobs.

## Installation

These are **user-mode** systemd units (run as the operator, not root) — they
need the operator's RunPod API key from `~/.fabrik/.env.sysadmin` or
`/opt/fabrik/.env.sysadmin`.

```bash
# 1. Copy to user unit directory
mkdir -p ~/.config/systemd/user
cp /opt/fabrik/scripts/systemd/fabrik-gpu-reaper.{service,timer} ~/.config/systemd/user/

# 2. Reload + enable + start the timer
systemctl --user daemon-reload
systemctl --user enable --now fabrik-gpu-reaper.timer

# 3. Verify
systemctl --user list-timers fabrik-gpu-reaper.timer
systemctl --user status fabrik-gpu-reaper.timer
journalctl --user -u fabrik-gpu-reaper.service -n 20
```

## What the reaper does

Every 10 minutes (Phase 4 default):

1. Calls `fabrik gpu reconcile --auto-destroy`. This:
   - Destroys any active sessions past their `max_lifetime_hours`.
   - Destroys orphan pods carrying our `FABRIK_SESSION_ID` env tag (state
     drift — the create succeeded but state file write didn't).
   - Retries previously-failed destroys (`destroy_pending=True`).
   - **NEVER touches pods without our env tag** (Constraint C4: foreign pods stay alive).
2. Writes Prometheus metrics to `logs/gpu-rent-metrics.prom` for the
   node-exporter textfile collector.

## Monitoring

After installing:

- `journalctl --user -u fabrik-gpu-reaper.service -f` — live reaper log
- `tail -f /opt/fabrik/logs/gpu-rent-history.jsonl` — every reaper run
  appends one line
- `cat /opt/fabrik/logs/gpu-rent-metrics.prom` — current metric state

Grafana panels suggested:
- `gpu_rent_active{provider="runpod"}` — currently-active rentals
- `rate(gpu_rent_cost_usd_total[1d])` — daily spend rate
- `gpu_rent_destroy_pending` — orphan risk indicator (should always be 0)
- `gpu_rent_last_reconcile_age_seconds` — alert if > 3600 (1 hour)

## See also

- `docs/development/plans/2026-06-16-fabrik-gpu-rent.md` — implementation plan
- `docs/operations/gpu-rent.md` — operator runbook
- `.windsurf/rules/core/76-gpu-workers.md` — GPU lifecycle rule
