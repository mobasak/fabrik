# WSL environment — operations runbook

Owner: ozgur · Last reviewed: 2026-07-19 (crontab inventory reconciled vs live `crontab -l` — 6 entries added since the prior review)

This is the WSL-side counterpart to [deployment.md](deployment.md) (VPS) and [fabrik-lifecycle.md](fabrik-lifecycle.md) (runtime behavior). It documents everything that runs on your local Windows-WSL2 development host — crontab, bashrc-sourced startup chain, lockfile and PID conventions, project-cron lifecycle policy, recovery.

If a script runs on the VPS, document it in [deployment.md](deployment.md) or [vps-complete-inventory.md](../infrastructure/vps-complete-inventory.md) instead — not here.

## Why WSL has cron at all

WSL2 doesn't ship with a traditional init system. Fabrik operates on the local host because:
- `/opt/fabrik` is the canonical source for AI catalog data, governance rules, and credentials — the VPS pulls from here, not the other way around
- Some workloads (Backblaze proxy tunnel, daily catalog refresh) are inherently WSL-local
- DR-mirror of credentials must originate from the WSL canonical source

Cron is preferred over systemd on WSL2 because systemd support requires `systemd=true` in `/etc/wsl.conf` + WSL 0.67.6+ and is occasionally flaky after Windows updates. On the VPS, systemd is fine and is used (e.g. `fabrik-dr-watcher.service`).

## Crontab inventory

Run `crontab -l` to view. Every entry is documented below. **Schedule cell shows local Istanbul time (UTC+3)** unless noted.

### Fabrik-owned (stays on WSL)

| Schedule | Target | Purpose |
|---|---|---|
| `0 6 * * *` (06:00 local = 03:00 UTC) | `/opt/fabrik/scripts/kilo-benchmarks/daily_refresh.sh` | AI catalog refresh + browser regen. ~30 steps, instrumented with per-step `[timing]` lines + `[timing] TOTAL: Ns` at end. See [AI_MODELS_BROWSER_OPS.md](AI_MODELS_BROWSER_OPS.md). |
| `0 * * * *` | `/opt/fabrik/scripts/audit_all_registrars.py` | Hourly drift audit: walks every spec under `specs/services/*.yaml`, runs 9 registrars × N specs, emits Prometheus text metrics → pushgateway → Alertmanager → Telegram on drift. T4-04 G-G5. |
| `0 6 * * 1` (Mon 06:00) | `/opt/fabrik/scripts/audit_authelia_gates.py` | Weekly Authelia drift audit. Detects when Traefik isn't applying `authelia-forward@docker` middleware to admin-dashboard routers (2FA-bypass detection). Driven by Lesson 32 incident. |
| `30 3 * * *` (03:30 daily) | `/opt/fabrik/scripts/dr_env_backup.sh` | DR mirror of credentials (`/opt/fabrik/.env`, `vps:.env.sysadmin`, `vps2/vps3:.env` + `.restic-password`) to private GitHub repo at `/opt/fabrik-dr-store`. W9 of fleet-hardening. Also triggered change-driven by `fabrik-dr-watcher.service`. |
| `@reboot` (+60s sleep) | `/opt/fabrik/scripts/dr_env_backup.sh` | Catch-up DR backup after WSL boots. |
| `0 4 * * 0` (Sun 04:00) | `/opt/fabrik/scripts/dr_env_recovery_test.sh` | Weekly self-test: reads `/opt/fabrik-dr-store/env/latest`, extracts restic + B2 creds, confirms B2 restic repo is readable via Backrest's in-container restic. |
| `59 11 * * *` (11:59 daily) | `cd /opt/fabrik && python3 scripts/kilo_model_sync.py --sync` | Daily Kilo model sync (added 2026-03-09). |
| `0 3 * * 0` (Sun 03:00) | `/home/ozgur/.local/bin/cache-prune.sh` | Weekly cache cap — clears regenerable download/build caches only when they exceed a threshold; never touches `~/.local` or source/data. |
| `17 5 * * *` | `find ~/.claude-youtube-headless/projects -type f -mtime +1 -delete` | Prunes headless-Claude session files older than 1 day. |

### Project-owned (will move to project's VPS deployment when deployed)

These run on WSL today because the projects are pre-deploy. **Lifecycle policy: when a project deploys to VPS, its WSL cron entries move to a scheduler container or beat task within the project's compose stack — they do NOT stay on WSL.** See [project-cron-lifecycle](#project-cron-lifecycle-policy) below.

| Schedule | Target | Project | Status |
|---|---|---|---|
| `0 2 * * 0` (Sun 02:00) | `/opt/calendar-orchestration-engine/scripts/run_pipeline.sh` | calendar-orchestration-engine | **Remove when deployed** — VPS scheduler container will own it |
| `*/5 * * * *` | `/opt/youtube/scripts/recovery_sweep.py --json` | youtube | Will move to VPS when youtube deploys |
| `@reboot` | `/opt/youtube/scripts/start_all.sh` | youtube | Starts 7 services (Flask dashboard, transcript poll_workers, comments poll_workers, FastAPI, Celery Beat, Celery Worker, docs-site). Will move to VPS systemd unit when youtube deploys. |
| `0 9 * * 1` (Mon 09:00) | `/opt/youtube/scripts/update_financials.py --write` | youtube | Writes `FINANCIALS.md` from local postgres. Will move to VPS when youtube deploys. |
| `@reboot` | `/opt/youtube/scripts/b2_socks_tunnel.sh` | youtube | **STAYS on WSL** — Turkish ISP blocks Backblaze, this routes via VPS SOCKS5. WSL-specific workaround; VPS doesn't need it. |
| `0 12 * * *` | `/opt/trade-intelligence/scripts/supabase_keepalive.sh` | trade-intelligence | **REMOVED 2026-06-30** — trade-intelligence is paused per operator memory; keepalive no longer needed |
| `0 3 * * *` | `/opt/site-provisioner/scripts/watchlist_check.py` | site-provisioner | Daily WHOIS check. Move to VPS when deployed. |
| `0 4 * * *` | `/opt/site-provisioner/scripts/drop_feed.py` | site-provisioner | Daily drop-feed scrape. Move to VPS when deployed. |
| `0 20 * * *` | `/opt/site-provisioner/scripts/drop_feed.py` | site-provisioner | Evening catch-up drop scrape. Move to VPS when deployed. |
| `0 * * * *` | `/opt/site-provisioner/scripts/dns_recheck.py` | site-provisioner | Hourly DNS availability recheck. Move to VPS when deployed. |
| `30 3 * * *` | `/opt/youtube/scripts/rag_daily_index.py --limit 2500 --source-type transcripts` | youtube | Daily RAG transcript indexing. Will move to VPS when youtube deploys. |
| `0 * * * *` | `/opt/youtube/scripts/rag_claim_index.py --limit 42` | youtube | Hourly RAG claim indexing. Will move to VPS when youtube deploys. |
| `*/5 * * * *` | `/opt/youtube/scripts/start_all.sh ensure` | youtube | Keeps the 7 youtube services up (restart-if-dead sweep). Will move to VPS when youtube deploys. |
| `30 5 * * *` | `/opt/trade-intelligence/scripts/gtip/run_refresh_once.sh` | trade-intelligence | Daily single-pass GTIP tax refresh against the self-hosted `trade_intelligence` Postgres. Move to VPS when deployed. |

### Removed cleanup (2026-06-30)

For audit history. These crontab entries were removed because their target paths no longer exist:

| Removed entry | Reason |
|---|---|
| `0 6 * * * /opt/consult/simple-daily-update.sh` | `/opt/consult/` deleted entirely (not even in `/opt/archived/`); failed silently every day |
| `@reboot /opt/translator/scripts/start_service.sh` | `/opt/translator/` archived 2026-05-20 to `/opt/archived/translator/` |
| `*/5 * * * * /opt/translator/scripts/watchdog.sh` | Same — was firing curl→fail→docker-restart-ENOENT every 5 min for ~41 days (~11,800 silent failures) |
| `@reboot /opt/youtube/workers/start_all_workers.sh` | Workers dir empty; entrypoint superseded by `start_all.sh` (kept). The dead entry was orphaned alongside the working one. |
| `0 12 * * * /opt/trade-intelligence/scripts/supabase_keepalive.sh` | Project paused per operator memory |

Backup of pre-cleanup crontab: `~/.crontab.backup.20260630-105542Z`.

## Bashrc-sourced startup chain

`~/.bashrc:213` sources `/opt/fabrik/scripts/wsl_startup_hook.sh` on every interactive shell open. The hook runs:

1. **Env watcher** (persistent process; not daily): starts `watch_env_changes.sh` if not already running. Monitors `/opt/*/.env` for changes and logs violations.
2. **Daily pipeline** (lockfile-gated; once per UTC day):
   - Project registry sync: `project.yaml` from every `/opt/*/project.yaml` → merged into `data/projects.yaml` + updates `BUSINESS_MODEL.md` + `PORTS.md`
   - Cascade backup freshness check
   - Health summary
   - **Kilo agent workflow** (also now in cron daily_refresh.sh): kilo_agents_db.py, update_kilo_benchmarks.py, scrape_artificial_analysis.py, role_mapper.py, export_traycer_registry.py, generate_kilo_agents.py
   - **Embedding selection pipeline** (also now in cron): embedding_models_db.py, embedding_pre_filter.py, embedding_role_mapper.py, embedding_export_markdown.py
   - **OpenRouter category routing** (also now in cron)

Lockfile coordination: bashrc-hook and daily_refresh.sh share `/tmp/.fabrik_daily_$(date -u +%Y%m%d)`. Whichever fires first (typically cron at 03:00 UTC) wins the day; the other path sees the lockfile and exits at the gate. Lockfile rolls over cleanly at 00:00 UTC.

Manual override: `rm /tmp/.fabrik_daily_$(date -u +%Y%m%d)` to re-run within the same UTC day.

## Lockfiles + PID files

| Path | Owner | Purpose |
|---|---|---|
| `/tmp/.fabrik_daily_YYYYMMDD` | daily_refresh.sh + wsl_startup_hook.sh | Day-scoped pipeline lockfile (UTC date). Rolls over at 00:00 UTC. |
| `/tmp/fabrik-sync-enforcement.lock` | daily_refresh.sh (via `flock -w 0`) | Serializes the sync_enforcement step against manual operator runs. `-w 0` = "skip this run if held" rather than block cron. |
| `/tmp/b2_socks_tunnel.pid` | b2_socks_tunnel.sh | Single-instance guard for the SOCKS5 tunnel. Auto-cleaned on SIGTERM. |
| `~/.cache/pre-commit/patch*` | pre-commit hooks | Restored automatically after hook run. |

## Project-cron lifecycle policy

When a project transitions from local-only to VPS-deployed, its WSL cron entries MUST move with it:

1. **VPS path** — the project's compose stack adds a `companion_services:` block (see deploy-readiness-gaps plan Phase 4) for scheduler/worker containers, OR a beat task in the existing Celery/equivalent worker.
2. **Remove the WSL crontab line** at the same change. Document the removal here under "Removed cleanup".
3. **The WSL state stays consistent** — no orphaned cron entries pointing at projects that now run elsewhere.

Exception: workloads that are inherently WSL-local (Backblaze proxy tunnel, DR-mirror of canonical creds, AI catalog refresh) stay on WSL forever.

## Recovery

### "WSL won't boot"

1. Most fabrik state is in `/opt/fabrik` (git, recoverable from GitHub) and `/opt/fabrik-dr-store` (git, mirrored to private GitHub).
2. Credential restoration: the daily DR mirror at `/opt/fabrik-dr-store/env/latest` carries `/opt/fabrik/.env` + the 6 VPS-side credential files. `git clone` the DR repo to a fresh WSL, copy `env/latest` to `/opt/fabrik/.env`.
3. See [credential-recovery.md](credential-recovery.md) for the full procedure.

### "Cron job stopped firing"

Two ways to detect:
1. **Heartbeat alert** — daily_refresh.sh writes `scripts/kilo-benchmarks/cache/daily_refresh_last_success.txt` at end of every successful run. `check_daily_refresh_freshness.py` (first step inside daily_refresh.sh) compares to wall-clock; >36h old fires a Telegram alert. **First-run condition is silent** (no false positives on fresh installs).
2. **Per-step timing** — every step now emits `[timing] <name>: Ns (exit=<rc>)` to `cache/update.log`. After-the-fact: `grep '\[timing\]' update.log | sort -k2 -t: -n | tail -10` shows the slowest 10 steps from the most recent run. Use this to find regressions.

Recovery: manually trigger `bash /opt/fabrik/scripts/kilo-benchmarks/daily_refresh.sh` after removing the lockfile if needed.

### "Backblaze SOCKS tunnel down"

```bash
# Check if running
cat /tmp/b2_socks_tunnel.pid && kill -0 $(cat /tmp/b2_socks_tunnel.pid) && echo "alive" || echo "dead"

# Restart manually (the script handles single-instance + auto-reconnect)
rm -f /tmp/b2_socks_tunnel.pid
/opt/youtube/scripts/b2_socks_tunnel.sh &
```

### "Crontab corrupted or accidentally edited"

Backups live at `~/.crontab.backup.YYYYMMDD-HHMMSSZ`. Restore with: `crontab ~/.crontab.backup.YYYYMMDD-HHMMSSZ`.

## See also

- [AI_MODELS_BROWSER_OPS.md](AI_MODELS_BROWSER_OPS.md) — daily_refresh.sh deep-dive
- [deployment.md](deployment.md) — VPS-side counterpart
- [disaster-recovery.md](disaster-recovery.md) — fleet-level DR
- [credential-recovery.md](credential-recovery.md) — restore-from-DR procedure
- [fabrik-lifecycle.md](fabrik-lifecycle.md) — runtime behavior
- [../infrastructure/vps-complete-inventory.md](../infrastructure/vps-complete-inventory.md) — what runs on the VPS
