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

---

## `fabrik-compose-boot.service` — reboot-race safety net (ALL fleet hosts)

**System-level** (root) oneshot that reconciles every `/opt/*/compose.yaml` stack to running on boot.

## Why it exists

Docker's `restart: unless-stopped` does **not** resume a container that had already fully exited
(non-zero) at the moment `dockerd` stopped. On **2026-07-08** vps1's `alertmanager` exited `255` during a
kernel-upgrade reboot and stayed down **4 days** — silently, because the down service *was* the alert
pipeline (Prometheus → Alertmanager → Telegram). Its five sibling monitoring containers, still running at
shutdown, were resumed normally. `docker compose up -d` restores any not-running stack member and is a no-op
for those already up, so this unit closes the race deterministically fleet-wide.

## Files

- `fabrik-compose-boot.service` — `Type=oneshot`, `After=docker.service`, `WantedBy=multi-user.target`
  (mirrors the `iptables-docker-user.service` pattern from `bootstrap-vps.sh`).
- `fabrik-compose-boot.sh` — installed to `/usr/local/bin/`; brings up shared-infra stacks first
  (postgres, redis, traefik, authelia, meilisearch, monitoring[-agent]) then every other stack. Never fails
  the boot transaction (warnings are journaled). Supports `--dry-run` (log discovery, no `up -d`).
- `install-compose-boot.sh <ssh-host> [--dry-run|--run]` — idempotent installer for any fleet host.

## Install / verify

```bash
# hub + spokes (from /opt/fabrik):
scripts/systemd/install-compose-boot.sh vps  --dry-run   # install+enable, then verify stack discovery
scripts/systemd/install-compose-boot.sh vps2 --dry-run
scripts/systemd/install-compose-boot.sh vps3 --dry-run

# spokes ALSO get it automatically from bootstrap-vps.sh step 16 on any rebuild.

ssh vps 'systemctl is-enabled fabrik-compose-boot.service'          # → enabled
ssh vps 'sudo /usr/local/bin/fabrik-compose-boot.sh --dry-run'      # list stacks it would reconcile
ssh vps 'sudo systemctl start fabrik-compose-boot.service && journalctl -u fabrik-compose-boot.service -n 30'
```

A live `up -d` sweep is a no-op unless a live compose file has drifted from its running container (then it
recreates that one to match — the correct reconciliation). Confirm safety first with
`docker compose -f /opt/<svc>/compose.yaml up -d --dry-run` (shows `Running` for a no-op).
