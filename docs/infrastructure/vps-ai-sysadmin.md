# VPS AI System Administrator — Reference

**Last Updated:** 2026-06-02 (post-W14 sweep — probe report refreshed; deployer + rollback honor `target_vps` end-to-end)
**Last probe report:** [`probe-reports/infra-probe-2026-06-01T22-50Z.yaml`](probe-reports/infra-probe-2026-06-01T22-50Z.yaml)
**Status:** Live since 2026-05-20
**Service:** `vps-sysadmin-bot.service` (systemd, `Restart=always`)
**Bot:** Telegram (`@ocoron_bot`), same bot as Alertmanager notifications
**Brain:** Claude Code v2.1.144 at `/usr/local/bin/claude` (Max subscription, authenticated via `claude auth login`)

---

## What It Is

An on-demand AI system administrator. Not a monitoring tool — a thinking sysadmin that runs locally on the VPS, queries all infrastructure APIs directly, diagnoses root causes, acts autonomously on safe operations, and reports what it did.

**On-demand, not persistent.** Dormant 99% of the time. Zero tokens unless triggered. Session starts when you message or when a proactive check detects an anomaly. Session ends on "done" or 10 minutes of silence.

### Two AI layers in the platform — do not confuse them

The platform is gaining a **second** AI layer that is distinct from the host-level sysadmin described in this document. New readers conflate the two; this section disambiguates.

| Layer | Where it runs | Scope | Lifecycle | Auth | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Host-level AI sysadmin** (this doc) | `vps-sysadmin-bot.service` on vps1 only — a systemd unit, NOT a container | Whole-VPS infrastructure: containers, mesh, backups, alerts | One persistent systemd service; spawns Claude Code sessions on demand | Claude Code Max subscription via `claude auth login` on vps1 | ✅ LIVE since 2026-05-20 |
| **Per-project watchdog sidecar** (T-P2 watchdog platform) | One sidecar **container** injected next to every project app at `fabrik apply` time | One project's health: its own containers, its own DB, its own cost-budget | Per-project; lives as long as the project's compose stack does | Inherits host OAuth via a mount of the VPS user's `~/.claude/` (path configurable via `FABRIK_VPS_CLAUDE_HOME`, defaults `/home/ozgur/.claude`); can also fall back to OpenRouter API key | ✅ **T-P1+T-P2+T-P3+T-P4 complete (2026-06-03).** Sidecar (`/opt/fabrik-lib/watchdog/sidecar/` ~2,134 lines) + orchestrator wiring (`infrastructure.py` registrar + `drivers/watchdog.py` 387-line driver) + operator surface (emitter library, rule pack `60-watchdog.md`, fabrik-lib README row, test spec `specs/services/watchdog-test.yaml`, self-healing rule pack `core/self-healing.md`, universal-coverage overlay in `02-epic-decomposition-command.md` + 03 Metadata sync). End-to-end verified through `spec_loader → resolver → driver` chain. Subplans for P2 + P4 archived. ⏳ **T-P5 — defensive sub-plan r1 staged 2026-06-03** at [`docs/development/plans/2026-06-03-watchdog-P5-subplan.md`](../development/plans/2026-06-03-watchdog-P5-subplan.md): runs only Sub-goal B (runtime dogfood Steps 5–9 against `specs/services/watchdog-test.yaml`); Sub-goal A (Traycer GUI dogfood) deferred per owner Q1. One small pre-T-P5 driver code-fix dependency (sub-plan §14): add `env_file: ['.env']` to the watchdog service block in `_push_overlay` so `WATCHDOG_OPENROUTER_KEY` propagates from `/opt/<project>/.env` to the sidecar runtime env. T-P5 execution begins after the §14 fix lands. |

Concretely:

- The host sysadmin watches **the platform**. It restarts containers, silences alerts during planned ops, knows about Wireguard mesh state, etc.
- The watchdog sidecar watches **one tenant**. It diagnoses why `acme-saas` is throwing 500s, runs cost-budgeted LLM calls for triage, escalates to the operator if it can't fix the issue, and writes audit-log rows so the operator can review.
- They share **Apprise → Telegram** as the escalation channel by default (`watchdog.escalation_channel: "apprise"`). They share Claude Code as the LLM (the watchdog sidecar inherits the host's OAuth via a read-only mount).
- They do NOT share state. Watchdog cost ledgers live in `fabrik_analytics.cost_ledger` (a shared Postgres table created by the T-P1 ship). Host-sysadmin proactive logs live in `/var/log/sysadmin-proactive.log`.

Per-project enablement is controlled by the `watchdog:` block in each spec (`src/fabrik/spec_loader.py::WatchdogConfig`). Defaults are computed by the dispatcher from `shape.kind`: service/worker/wordpress get `enabled=True`; static sites get `enabled=False`. The operator can override per-spec. See [`docs/development/plans/2026-05-30-ai-watchdog-platform-P2-subplan.md`](../development/plans/2026-05-30-ai-watchdog-platform-P2-subplan.md) for the full architecture.

**Per-project watchdog capability scope (v1, locked 2026-06-02 during artifact 2 review):**

| Capability | What Claude can do | Defense-in-depth |
| :--- | :--- | :--- |
| Container introspection | `docker logs/inspect/stats` on `<main_container>` AND `<project_prefix>*` (multi-container projects) | Restart/stop/kill is surgical: ONLY `<main_container>`. Sibling containers are read-only. |
| Runtime introspection | `docker exec <main_container>` for `ps`, `df`, `cat /proc/*`, `head /proc/*`, `tail /proc/*` | No shell escape: `sh*`, `bash*`, `/bin/sh*`, `/bin/bash*`, `rm` denied. |
| Logs + metrics | `tail/head/grep/cat` on `/opt/<id>/logs/*` (any flag); `curl localhost:*/{metrics,health}` | Path-constrained; only project logs. |
| Self-diagnostics | `free`, `df`, `uptime`, `uname` for sidecar's own state | Read-only. |
| State queries | `sqlite3 -readonly /var/lib/watchdog/state.db` for incident/action history | Triple defense: `-readonly` flag + keyword deny (UPDATE/DELETE/DROP/etc.) + sandbox denyWrite. |
| Env visibility | `printenv \| cut -d= -f1`, `compgen -e` — KEY names only | Raw `printenv`, `env`, `cat .env`, `cat secrets/*` denied. Hard-deny: "Never read or print environment variable VALUES." Defends against prompt-injection exfil. |
| External docs | `WebSearch` always; `WebFetch` restricted to 29-domain allow-list (python/django/fastapi/redis/postgres/aws/gcp/azure/MDN/stripe/github/stackoverflow/readthedocs/pypi/npmjs/k8s/nginx/traefik/docker/anthropic/openrouter/hashicorp) | Direct `curl http://*`/`https://*` denied. |
| Tier B log redaction | Detect leakage → call `actions.py::install_log_drop_rule(pattern, severity)` which validates regex + restarts Promtail | Sidecar never edits Promtail config directly. Opt-in per project via `auto_tier_b: true`. |
| Tier C code-fix proposals | Open a PR on `watchdog/<incident_id>` branch using `/var/lib/watchdog/proposed/<project_id>/` workspace. `Edit`/`Write` allowed in workspace; safe git subcommands allowed | NEVER push to `main`/`master`/`develop`/`staging`/`production`; force-push, reset, rebase, tag, config, remote — all denied. Operator reviews + merges. Opt-in per project via `propose_fix_prs: true`. |
| Deadman timer | If Tier C escalation unresponded > 300s (default), `agent.py` restarts `<main_container>` as bleed-stop + re-alerts with `[DEADMAN-TIMEOUT]` prefix | Bleed-stop is read-only deescalation; no new permission needed. Timeout configurable via `WatchdogConfig.deadman_timeout_seconds` (60–3600s). |

Full settings template lives at [`/opt/fabrik-lib/watchdog/sidecar/claude-settings.json.template`](../../../fabrik-lib/watchdog/sidecar/claude-settings.json.template) (200 lines, 50 allow / 55 deny / 12-line autoMode.environment / 11-line hardDeny / 29 allowed-domains).

The rest of this document covers the **host-level layer only**.

## Architecture

```
┌────────────────────────────────────────────────────────────┐
│  VPS (all local, no SSH, no external LLM API)               │
│                                                             │
│  PATH 1: You message Telegram                               │
│  ┌──────────┐  message  ┌───────────────────────────────┐  │
│  │ Telegram  │─────────▶│  sysadmin-bot.py (systemd)    │  │
│  │ (phone)   │◀─────────│  spawns claude -p on demand   │  │
│  └──────────┘  response │  kills after "done" / timeout │  │
│                          └──────────────┬────────────────┘  │
│                                         │                    │
│  PATH 2: Alert fires                    │                    │
│  ┌──────────────┐  already   ┌─────────▼─────────┐         │
│  │ Alertmanager │──works────▶│ Apprise→Telegram   │         │
│  └──────────────┘            └───────────────────┘         │
│  You reply to investigate → Path 1                          │
│                                                             │
│  PATH 3: Proactive cron (every 15 min)                      │
│  ┌───────────────────────────────────────────┐              │
│  │  proactive-check.sh                       │              │
│  │  Stage 1: bash curls Prometheus (free)    │              │
│  │  Stage 2: claude -p (only if anomaly)     │              │
│  │  → acts autonomously + reports to Telegram│              │
│  └───────────────────────────────────────────┘              │
│                                                             │
│  Claude Code runs LOCALLY when triggered:                   │
│  - queries Prometheus, Loki, Gatus, GlitchTip, Netdata    │
│  - runs sudo docker stats/logs/restart/inspect              │
│  - runs sudo bash scripts/audit/*.sh                        │
│  - reads docs/infrastructure/*.md, specs/services/*.yaml   │
│  - Max subscription (zero additional cost)                  │
└────────────────────────────────────────────────────────────┘
```

## Infrastructure APIs (queried locally)

Claude Code reaches these from inside the Docker `fabrik` network via `sudo docker exec` or `sudo docker run --rm --network fabrik curlimages/curl:latest`.

| Service | URL | What the sysadmin gets |
|---|---|---|
| Prometheus | `prometheus:9090` | Container + host metrics, 13 alert rules, scrape target health |
| Loki | `loki:3100` | All container logs — errors, stack traces, crash messages |
| Grafana | `grafana:3000` | Dashboard + datasource health (8 dashboards, 2 datasources) |
| Alertmanager | `alertmanager:9093` | Active firing alerts, silences |
| Gatus | `gatus:8080` | Uptime status for 30+ endpoints |
| GlitchTip | `glitchtip-web:8000` | Application errors, unhandled exceptions |
| Apprise | `apprise:8000` | Send notifications to Telegram |
| Netdata | `netdata:19999` | Real-time per-second system metrics |
| Pushgateway | `pushgateway:9091` | Drift audit metrics from hourly fabrik cron |
| Meilisearch | `meilisearch:7700` | Search index health |
| Docker | local CLI | Container lifecycle — ps, stats, logs, restart, update, inspect |
| Node exporter | via Prometheus | Host CPU, RAM, disk, network |
| cAdvisor | via Prometheus | Per-container resource metrics |
| Postgres exporter | via Prometheus | Database connections, query rates, sizes |
| Redis exporter | via Prometheus | Cache memory, hit rate, clients |

## Alert Coverage (what triggers detection)

**Layer 1: Prometheus alert rules (13) → Alertmanager → Telegram**

| Rule | Catches | Source |
|---|---|---|
| ContainerDown | Container disappeared | cAdvisor |
| ContainerHighCPU | CPU >80% sustained | cAdvisor |
| ContainerHighMemory | Memory >80% of limit | cAdvisor |
| ContainerMemoryHighOfHost | Container using too much host RAM | cAdvisor + node-exporter |
| ContainerOOMKilled | OOM kill event | cAdvisor |
| ContainerRestarting | >3 restarts in 15min | cAdvisor |
| HostHighCPU | Host CPU >80% | node-exporter |
| HostHighMemory | Host RAM >90% | node-exporter |
| HostDiskFull | Disk >85% | node-exporter |
| ServiceUnhealthy | Prometheus target down | Prometheus |
| PromtailNotShipping | Log pipeline broken | Promtail |
| PromtailDroppingEntries | Loki rejecting logs | Promtail |
| FabrikRegistrarDrift | Infrastructure drift | Pushgateway |

**Layer 2: Proactive cron (11 checks, every 15 min) → Claude acts if anomaly**

| Check | Threshold | Catches BEFORE alerts fire |
|---|---|---|
| Memory rising | >5MB/min growth | Memory leak before 80% |
| Container restarted | Any restart in 15min | Single restart (alert needs >3) |
| CPU sustained | >70% for 15min | Creeping load before 80% |
| Disk | >75% | Before 85% alert |
| Host RAM | >80% | Before 90% alert |
| Load average | >2x CPU count (dynamic) | CPU saturation |
| OOM kill | Any in 15min | Immediate backup check |
| Disk prediction | Full within 7 days | Trend-based, not threshold |
| Prometheus target down | Any target `up == 0` | Matches alert, backup detection |
| Log pipeline dead | Loki ingestion rate = 0 | Matches alert, backup detection |
| TLS cert expiry | <14 days on 5 domains | Auto-renewal may have failed |

### Layer 3 — Spoke-aware checks (added 2026-05-31)

`proactive-check.sh` now tags every anomaly with the originating host (e.g. `cpu_high[vps2]` instead of `cpu_high`). A new `prom_hosts()` helper extracts the unique `host` label values from each PromQL result. All existing queries naturally cover vps1 + vps2 + vps3 because Prometheus on vps1 scrapes spoke `node-exporter` / `cadvisor` / `promtail` over the Wireguard mesh — no per-host check duplication needed.

New Prometheus alert rules in group `spoke_health`:

| Rule | Catches | Condition |
| :--- | :--- | :--- |
| SpokeDown | Spoke target stops reporting | `up{job=~"node-spokes\|cadvisor-spokes\|promtail-spokes"} == 0` for 5 m |
| SpokeHighCPU | Spoke vCPU > 85 % sustained | for 10 m, warning |
| SpokeHighRAM | Spoke RAM > 85 % sustained | for 10 m, warning |

Routed via Alertmanager → Apprise → Telegram with the existing config; bot is notified through the same channel.

### Layer 4 — Self-watched chain (W10, 2026-06-01)

`proactive-check.sh` now monitors the automation chain itself — surfaces that don't crash anything but silently stop working. Each watcher feeds the existing tier-A/B/C anomaly pipeline.

| Watcher | What it sees | Anomaly emit | Threshold |
| :--- | :--- | :--- | :--- |
| `backup_health` | Hub Backrest restic snapshot age per plan (`postgres-dumps`, `docker-volumes`, `opt-configs`, `host-state`) | `backup_stale[hub:<plan>:<h>h]` or `backup_missing[hub:<plan>]` | > 36 h since last snapshot |
| `mesh_health` | Hub-side `wg show wg0 latest-handshakes` per peer | `mesh_degraded[<pk>:<m>m]` at 5–15 m, `mesh_broken[<pk>:<m>m]` > 15 m, `mesh_no_handshake[<pk>]` if peer never handshook | 5 m / 15 m |
| `dr_store` | GitHub API `commits?per_page=1` on `mobasak/fabrik-dr-store` (W9 mirror) | `dr_store_stale[<d>d]` if last commit > 30 d ago | 30 d |
| `cert_expiry` (existing, scrubbed in W10) | `openssl s_client` against domain list (now: `ocoron.com`, `status/monitor/errors.vps1.ocoron.com`; dropped stale `coolify.vps1.ocoron.com`) | `cert_expiring:<domain>:<d>d` | < 14 d to expiry |

**`dr_store` token requirement:** the watcher reads `GITHUB_TOKEN` (or `GH_TOKEN`) from `/opt/fabrik/.env.sysadmin` (preferred — it's root-readable and already in scope) or `/opt/fabrik/.env`. Token scope: fine-grained PAT with `Contents: Read` on `mobasak/fabrik-dr-store` only. **Until a token is added, the watcher logs a one-per-hour `WARN: dr_store watcher dormant` line to `/var/log/sysadmin-proactive.log` so the operator knows it's not running.** Adding it:

```bash
ssh vps 'sudo bash -c "echo GITHUB_TOKEN=ghp_xxx >> /opt/fabrik/.env.sysadmin"'
# Next proactive-check tick activates the watcher; W9 cron mirrors the file to private repo within 24h.
```

**Wall-clock impact:** the W10 additions take ~3 s (1 restic call + 1 wg show + 1 curl). Total `proactive-check.sh` runtime ≈ 6 s on the live hub — well within the 15-min cron interval.

**Live-state at W10 ship (2026-06-01 evening):** all watchers green. Hub backups 2 h old, mesh handshakes < 1 min, no certs < 14 d, dr_store dormant (no token yet). Action log file `/opt/fabrik/logs/sysadmin-actions.jsonl` does not exist — bot has never autonomously acted since 2026-05-20 deployment (safe default).

## Multi-host scope (2026-05-31)

The sysadmin operates from vps1 but has **read + restart access on vps2 and vps3** via SSH (`ssh vps2`, `ssh vps3` as `ozgur` with NOPASSWD sudo). Container actions on spokes use the same patterns:

```bash
ssh vps2 'sudo docker ps'              # list spoke containers
ssh vps2 'sudo docker stats --no-stream'
ssh vps2 'sudo docker logs <name> --tail 100'
ssh vps2 'cd /opt/<svc> && sudo docker compose restart <name>'
```

Metric + log queries stay local to vps1 (Prometheus + Loki contain fleet-wide data via the mesh — see `grafana-dashboards-setup.md § Multi-host considerations`).

Container classification on spokes (post-bootstrap):

| Category | Spoke containers | Permissions |
| :--- | :--- | :--- |
| critical-infra | traefik | READ ONLY |
| monitoring agents | node-exporter, cadvisor, promtail | READ ONLY |
| application | (future spoke tenants) | Full autonomous |

## Container Classification

| Category | Containers (vps1 + spokes) | Claude's permissions |
|---|---|---|
| **critical-infra** | traefik (every host), postgres-main, redis-main, wg0 (mesh) | READ ONLY. Never restart/stop/scale. |
| **monitoring** | prometheus, grafana, loki, promtail (every host), alertmanager, cadvisor (every host), node-exporter (every host), gatus, pushgateway, exporters | READ ONLY. Touching these blinds Claude. (`netdata` is in this list pattern but **not deployed today**.) |
| **platform** | authelia, apprise, backrest, n8n, glitchtip-web/worker, meilisearch, gotenberg, browserless | Restart autonomously. Report after. |
| **application** | site-provisioner (interim, vps1), ocoron-com-* (vps1), any spoke tenants deployed via `fabrik apply --target-vps vpsN` | Full autonomous management. |

**Note (2026-05-31, updated 2026-06-02):** the 6 historical microservices (captcha, translator, proxy, emailgateway, file-api, file-worker) are **not deployed** — they show in old runbooks as examples. Same rules apply when they're redeployed. The 7th historical service, `image-broker`, was retired 2026-06-02 (spec + state + infra deleted).

## Operating Mode

Default: **autonomous**. Acts first, reports after.

| Action | Autonomous | Ask first | NEVER |
|---|---|---|---|
| Restart application/platform | ✅ act + report | | |
| Scale memory UP (cap 4GB) | ✅ act + report | | |
| Scale memory DOWN | | ✅ | |
| Stop a container | | ✅ | |
| Delete container/volume/data | | | ❌ |
| Modify env vars | | | ❌ |
| Touch networking/firewall/boot | | | ❌ |
| Touch Docker daemon/fstab | | | ❌ |

## Token Economics

| Scenario | Claude wakes? | Cost |
|---|---|---|
| Quiet day, proactive all-clear | No | $0 |
| Proactive detects anomaly | Yes, fire-and-forget | ~$0.01-0.05 |
| You message "status" | Yes, session until "done" | ~$0.02-0.10 |
| Full audit on demand | Yes, long session | ~$0.20-0.50 |
| **Monthly typical** | | **$5-15** (included in Max) |

## Components

### Bot + System Prompt (always running)

| File | Location (VPS) | Purpose |
|---|---|---|
| `bot.py` | `/opt/fabrik/scripts/sysadmin/bot.py` | Telegram bot (332 lines) — spawns Claude Opus per message, JSON output parsing, session management, action logging, health endpoint `:8017` |
| `system-prompt.txt` | `/opt/fabrik/scripts/sysadmin/system-prompt.txt` | Sysadmin brain (232 lines) — role, APIs, classification, playbooks, shift notes, criticality tiers, communication protocol, safety rules |
| `.env.sysadmin` | `/opt/fabrik/.env.sysadmin` | Required: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_OWNER_ID`. Optional (with defaults): `SYSADMIN_PROJECT_DIR=/opt/fabrik`, `SYSADMIN_HEALTH_PORT=8017`, **`SYSADMIN_HEALTH_HOST=127.0.0.1`** (added W5 2026-06-01 — set to `10.99.0.1` to expose `:8017` on the WG mesh interface for future Gatus/Prometheus), `SYSADMIN_MODEL=opus`. |
| Service unit | `/etc/systemd/system/vps-sysadmin-bot.service` | systemd service (`Restart=always`, `After=network.target docker.service`) |

### Scheduled Routines (cron — `/etc/cron.d/vps-sysadmin`)

| Script | Schedule | Uses Claude? | Purpose |
|---|---|---|---|
| `proactive-check.sh` | Every 15 min | Only on anomaly | 11 checks (10 PromQL + Prometheus connectivity) + cert expiry. Bash prefilter (zero tokens when healthy). Claude wakes, diagnoses, acts, reports only when something is wrong. |
| `morning-report.sh` | Daily 08:00 | Always | Collects system state + trends + shift notes + yesterday's actions. Claude formats a concise morning briefing for Telegram. |
| `weekly-security.sh` | Monday 08:30 | Always | Runs `scripts/audit/03-security.sh`, Claude analyzes against `audit-prompts/03-security-hardening.md` checklist. Reports GREEN/YELLOW/RED. |
| `weekly-maintenance.sh` | Sunday 03:00 | Never | Pure bash — checks dangling images/volumes, journal size, backup freshness, restart counts, stale containers, cert expiry. Reports what it found. |
| `monthly-backup-verify.sh` | 1st of month 04:00 | Always | Runs `scripts/audit/06-backup.sh`, Claude analyzes against `audit-prompts/06-backup-disaster-recovery.md` checklist. Reports coverage gaps + recovery confidence. |

### Operational Records (persistent across sessions)

| File | Purpose |
|---|---|
| `logs/sysadmin-actions.jsonl` | Every Telegram conversation logged — timestamp, session ID, message, response preview. Survives between sessions. |
| `logs/sysadmin-shift-notes.md` | Carry-forward notes Claude writes at end of each significant session. Read at start of next session. Gives memory between conversations. |

## Survives Reboot?

**Yes.** The service is `enabled` in systemd:

```
systemctl is-enabled vps-sysadmin-bot  → enabled
```

On VPS boot: `systemd` → `network.target` + `docker.service` start → `vps-sysadmin-bot.service` starts (After=network.target docker.service).

## Restart Policy

```
Restart=always
RestartSec=30
StartLimitIntervalSec=300
StartLimitBurst=5
```

- Crashes → restarts after 30 seconds
- Max 5 restarts in 5 minutes → then systemd stops trying
- To reset after hitting the limit: `sudo systemctl reset-failed vps-sysadmin-bot && sudo systemctl start vps-sysadmin-bot`

## Monitoring

### Automated (three layers)

1. **Systemd `Restart=always`** — crashes auto-recover in 30 seconds. Max 5 restarts in 5 minutes before giving up.
2. **Daily heartbeat** — bot sends a "💚 Sysadmin Bot — Daily Heartbeat" to Telegram at 08:00 local time with uptime, model, call stats. If you don't see it, the bot is dead.
3. **Health endpoint** — `:8017/health` returns JSON with status, uptime, model, call counts. Available for local checks (`curl localhost:8017/health`). **Since W5 of fleet-hardening plan (2026-06-01), bound to `127.0.0.1` only via `SYSADMIN_HEALTH_HOST` env var (default `127.0.0.1`)** — not reachable from anywhere except the vps1 host loopback. Prior to W5 the bind was `0.0.0.0:8017` and the bot WAS externally reachable on the public IP; the previously-stated "DOCKER-USER chain blocks host ports from forwarded traffic" was true only for *container→host* traffic, not for internet→host. Override the bind to the mesh interface (`10.99.0.1`) by setting `SYSADMIN_HEALTH_HOST=10.99.0.1` in `/opt/fabrik/.env.sysadmin` if a future Gatus/Prometheus integration needs it.
4. **Proactive cron is independent** — `proactive-check.sh` runs as root cron, NOT through the bot. If the bot dies, proactive checks still detect issues and alert via Apprise.

### Manual check

```bash
# Service status
sudo systemctl status vps-sysadmin-bot

# Recent logs
sudo tail -50 /var/log/vps-sysadmin-bot.log

# Is Claude Code working?
claude --version

# Proactive check logs
sudo tail -20 /var/log/sysadmin-proactive.log
```

## Firewall Architecture

The VPS has a two-layer firewall. The sysadmin must understand both but **NEVER modify either**.

**Layer 1: UFW** — host-level, controls SSH + direct ports:

```text
22/tcp     ALLOW (SSH, key-only, no root)
80/tcp     ALLOW (HTTP)
443/tcp    ALLOW (HTTPS)
1194/tcp   ALLOW (OpenVPN — user's personal VPN)
51820/udp  ALLOW (Wireguard mesh)
6001-6002  ALLOW (stale Coolify Realtime — pending cleanup, harmless)
8000/tcp   DENY (stale comment, rule itself is fine)
```

**Layer 2: DOCKER-USER iptables chain** — Docker bypasses UFW. This is the REAL perimeter for container traffic:

```text
Rule 1:    RETURN ESTABLISHED,RELATED (don't break existing sessions)
Rule 2:    ACCEPT -i wg0 (trust everything from the Wireguard mesh)
Rule 3:    RETURN 10.0.0.0/8 (container→container traffic)
Rule 4:    RETURN 172.16.0.0/12 (Docker internal)
Rule 5:    RETURN 192.168.0.0/16 (private ranges)
Rule 6:    RETURN tcp dport 80 (Traefik HTTP)
Rule 7:    RETURN tcp dport 443 (Traefik HTTPS)
Rule 8:    DROP   -i ens3 -p tcp -m multiport --dports 5432,6379,9090,9091,9100,8080,3100,7700,8000 (mesh-only ports blocked from public)
Final:     fall through to DROP (catch-all — blocks everything else from external)
```

Mesh-only services (postgres-main, redis-main, glitchtip-web, authelia, loki, etc.) bind their host ports to `10.99.0.1:<port>` and are reachable only via wg0 — the DOCKER-USER rules block public attempts as belt-and-suspenders.

**Script:** `/etc/iptables/add-docker-user-rules.sh` (re-applied on boot by `iptables-docker-user.service`)

**Why the health endpoint (:8017) can't be reached from anywhere except the host:** Since W5 (2026-06-01), the listener binds `127.0.0.1:8017` only — neither containers nor the public internet can reach it; only `curl http://127.0.0.1:8017/health` from the vps1 host shell works. The DOCKER-USER chain (rule 9 DROP on host-port range) still provides defense-in-depth for the container→host path, but the binding itself is now the primary control. Pre-W5 history: bind was `0.0.0.0:8017`; DOCKER-USER blocked the container→host path but NOT internet→host, so the bot WAS reachable from the public internet via vps1's public IP — a security gap caught by W6 probing and closed by W5.

## Common Operations

### Restart the bot

```bash
sudo systemctl restart vps-sysadmin-bot
```

### Stop the bot (maintenance)

```bash
sudo systemctl stop vps-sysadmin-bot
# Start again:
sudo systemctl start vps-sysadmin-bot
```

### Update the system prompt

Edit `/opt/fabrik/scripts/sysadmin/system-prompt.txt` on VPS, then restart the bot: `sudo systemctl restart vps-sysadmin-bot`. The bot loads the system prompt once at startup (module-level), NOT per-session. Cron scripts (proactive, morning, weekly, monthly) load it fresh each run — no restart needed for those.

### Update the bot code

```bash
# From WSL:
scp scripts/sysadmin/bot.py vps:/opt/fabrik/scripts/sysadmin/
ssh vps 'sudo systemctl restart vps-sysadmin-bot'
```

### View active Claude sessions

```bash
# Check if Claude is currently running (spawned by bot)
ps aux | grep "claude -p" | grep -v grep
```

### Disable all scheduled routines

```bash
sudo rm /etc/cron.d/vps-sysadmin
```

### Re-enable all scheduled routines

Reinstall from Step 6 of the Replication section below, or run:
```bash
bash scripts/sync-vps-sysadmin.sh  # from WSL — syncs scripts
# Then SSH to VPS and reinstall the cron file (see Step 6)
```

### Disable only proactive checks (keep morning report, weekly, monthly)

```bash
ssh vps 'sudo sed -i "/proactive-check/d" /etc/cron.d/vps-sysadmin'
```

## Troubleshooting

### Bot doesn't respond to Telegram messages

1. Check service is running: `sudo systemctl status vps-sysadmin-bot`
2. Check logs: `sudo tail -30 /var/log/vps-sysadmin-bot.log`
3. Check Claude Code auth: `claude --version` (should not say "auth required")
4. Check env file: `cat /opt/fabrik/.env.sysadmin` (token + owner ID set?)
5. Restart: `sudo systemctl restart vps-sysadmin-bot`

### Bot responds with "Claude error" or "timed out"

- Claude Code may have lost auth: `claude auth login` (re-authenticate)
- Claude Code may be rate-limited: wait 5 minutes, try again
- Subprocess timeout (5min): try a simpler question like "status"

### Proactive checks flooding Telegram

- Rate limit is 5 Claude wakes per hour — if exceeded, check `/var/log/sysadmin-proactive.log`
- If a threshold is too sensitive, edit the PromQL in `proactive-check.sh`
- Temporarily disable: `sudo rm /etc/cron.d/vps-proactive-check`

### Service hits StartLimitBurst (won't restart)

```bash
sudo systemctl reset-failed vps-sysadmin-bot
sudo systemctl start vps-sysadmin-bot
# Check what's causing crashes:
sudo tail -100 /var/log/vps-sysadmin-bot.log
```

### Alertmanager + bot conflict?

They don't conflict. Alertmanager sends via HTTP POST to `api.telegram.org` (native `telegram_configs`). The bot uses long-polling. Different mechanisms, same Telegram chat. Both work independently.

## Security

- **Owner-only:** Bot silently ignores all messages not from `TELEGRAM_OWNER_ID`
- **No secrets in chat:** Claude never sends API keys, passwords, or env values over Telegram (enforced in system prompt)
- **Docker socket:** Not mounted. Claude uses `sudo docker` CLI commands, not the socket
- **Claude Code auth:** Max subscription via `claude auth login` — no API key stored on VPS
- **Env file:** `/opt/fabrik/.env.sysadmin` contains only Telegram token + owner ID (not app secrets)

## Log Rotation

Bot log: `/var/log/vps-sysadmin-bot.log` — grows over time. Add logrotate:

```bash
sudo tee /etc/logrotate.d/vps-sysadmin-bot << 'EOF'
/var/log/vps-sysadmin-bot.log {
    weekly
    rotate 4
    compress
    missingok
    notifempty
    copytruncate
}
EOF
```

Proactive log: `/var/log/sysadmin-proactive.log` — same treatment:

```bash
sudo tee /etc/logrotate.d/vps-sysadmin-proactive << 'EOF'
/var/log/sysadmin-proactive.log {
    weekly
    rotate 4
    compress
    missingok
    notifempty
    copytruncate
}
EOF
```

## Session Model

Each Telegram conversation is a Claude Code session with continuity:

```
Message 1: "status"
  → bot spawns: claude -p "status" --session-id {new_uuid} --system-prompt {role}
  → response → Telegram
  → session_id saved, last_activity = now

Message 2: "restart site-provisioner" (within 10 min)
  → bot runs: claude -p "restart site-provisioner" --resume {same_uuid}
  → Claude has context from message 1
  → response → Telegram

Message 3: "done" (or 10 min silence)
  → session_id cleared → "Session ended. ✅"

Message 4: "check disk" (new conversation)
  → bot spawns: new UUID, fresh session, no history
```

- `claude -p` (print mode) — each message is a subprocess. No PTY, no stdin pipe.
- `--output-format json` — bot parses the JSON `result` field to extract Claude's text response. Using `text` format loses content when Claude interleaves tool calls with text responses.
- `--resume` — follow-ups resume same session. Claude remembers context.
- `--system-prompt` — injects sysadmin role. NOT from CLAUDE.md (that's for WSL development).
- `--permission-mode bypassPermissions` — Claude runs docker commands without tool-permission prompts.
- Subprocess timeout: 300s (5 min) per call. If exceeded → kill + "timed out" notification.

### Key design decisions (learned from live testing)

1. **`--output-format json`, not `text`** — Claude interleaves text with tool calls during investigation. The `text` format only captures the final text fragment. JSON wraps the complete response in a `result` field that bot.py extracts via `json.loads()`.
2. **`docker events` always needs `--until now`** — without it, `docker events` streams indefinitely. Claude spawns it as a subprocess that never exits, causing 5-minute timeouts and zombie processes. The system prompt explicitly warns about this.
3. **Communication protocol at top of system prompt** — Claude's default behavior is to write findings to shift notes and return minimal text. The system prompt's first paragraph now states: "Your text response is the ONLY output the owner ever sees." This ensures the Telegram user gets the full investigation report, not just "shift note saved."

## Knowledge Sync (WSL → VPS)

The sysadmin's knowledge files live in the fabrik repo on WSL. They're synced to VPS via:

```bash
bash scripts/sync-vps-sysadmin.sh
```

**When to run:** after any `fabrik apply`, `fabrik destroy`, doc edit, spec change, audit prompt update, or system prompt change.

**What gets synced:**

| Source (WSL) | Destination (VPS) | Purpose |
|---|---|---|
| `docs/infrastructure/*.md` | same path | Inventory, runbooks, audit prompts |
| `docs/operations/fabrik-lifecycle.md` | same path | Deployment lifecycle rules |
| `docs/reference/architecture.md` | same path | System architecture reference |
| `scripts/audit/*.sh` | same path | Diagnostic scripts |
| `scripts/sysadmin/*` | same path | Bot, proactive check, system prompt |
| `specs/services/*.yaml` | same path | Deployment specs (shape, domains, limits) |
| `scripts/vps_apply_limits.sh` | same path | Memory limits + alias script |
| `scripts/generate_vps_inventory.py` | same path | Inventory auto-generator |

**What is NOT synced (intentionally):**
- Root `CLAUDE.md` — that's for WSL Claude Code (development), not VPS sysadmin
- `.env` files — secrets stay per-environment
- `src/` — fabrik source code is for WSL dev, not VPS operations
- `node_modules/`, `.venv/`, build artifacts

**Does the VPS sysadmin know about new deployments automatically?**
- **Containers:** Yes — `docker ps` always shows current state (live query)
- **Specs:** Yes, after sync — `specs/services/*.yaml` tells Claude each service's purpose and shape
- **Docs:** Yes, after sync — `vps-complete-inventory.md` is regenerated on every `fabrik apply/destroy`
- **Config changes done on VPS directly:** Claude discovers them when it runs diagnostics (proactive cron or your message)

## Notification Templates

Claude formats Telegram messages using these templates (enforced in system-prompt.txt):

**Action taken:**
```
**Target:** glitchtip-web
**Issue:** Memory at 89% of 512MB limit (4 weeks since last restart)
**Action:** sudo docker restart glitchtip-web
**Result:** ✅ Memory 456MB → 89MB. Container healthy.
```

(Container names are stable post-Coolify-removal — `glitchtip-web`, not the old `glitchtip-web-<24chars>` UUID-suffix form. Same applies to every other container name in templates and prompts below.)

**Proactive finding:**
```
🔍 Proactive Check

📈 Disk trending: 29% → predicted 45% in 7 days
📦 Top consumers: overlay2 28GB, Netdata cache 2.3GB
💡 Netdata cache exceeds DBENGINE_DISK_SPACE_MB=512 setting
🔕 No action taken — informational only.
```

**Needs owner approval:**
```
⚠️ Need approval

**Target:** n8n
**Issue:** Memory at 412MB, no limit set, growing 3MB/min
**Proposed:** sudo docker update --memory 512m n8n-...
**Why ask:** Scale down not in autonomous permissions

Reply "do it" to approve.
```

## System Prompt

The sysadmin's identity, rules, APIs, and communication format live in:

```
/opt/fabrik/scripts/sysadmin/system-prompt.txt
```

This is injected via `--system-prompt` flag on every `claude -p` call. It is NOT in CLAUDE.md (which is the WSL development ruleset — different purpose, different audience).

To update the prompt: edit the file on WSL → run `bash scripts/sync-vps-sysadmin.sh` → restart the bot: `ssh vps 'sudo systemctl restart vps-sysadmin-bot'`. The bot loads the system prompt once at startup. Cron scripts (proactive, morning, weekly, monthly) load it fresh each run — no restart needed for those.

The system prompt defines:
- Role and context (local VPS admin, user `ozgur`, Ubuntu 24.04)
- Initialization (what to read silently before responding)
- All infrastructure API URLs and how to reach them
- Container classification (critical-infra / monitoring / platform / application)
- Knowledge sources (docs, specs, audit scripts)
- Permission boundaries (autonomous / ask first / never)
- Communication protocol (templates, emoji, conciseness)
- Error handling (retry once, then stop and report)

---

## Replication — Set Up on a New VPS from Scratch

Complete recipe. Assumes fresh Ubuntu 24.04 with Docker, the `fabrik` Docker network, and the monitoring stack (`/opt/monitoring/compose.yaml`) already deployed via `scripts/bootstrap/bootstrap-vps.sh` + manual hub setup.

### Step 1: Install Node.js + Claude Code

```bash
# Node.js (required by Claude Code)
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
sudo apt-get install -y nodejs

# Claude Code
sudo npm install -g @anthropic-ai/claude-code
claude --version  # should print version

# Authenticate (interactive — must be done manually)
claude auth login
# Opens URL → authorize in browser → paste code → done
# Uses Max subscription — no API key needed
```

### Step 2: Install Python dependency

```bash
sudo pip3 install --break-system-packages python-telegram-bot
```

### Step 3: Deploy bot files

From WSL (where fabrik repo lives):

```bash
# Create directory on VPS
ssh vps 'mkdir -p /opt/fabrik/scripts/sysadmin'

# Copy files
scp scripts/sysadmin/bot.py vps:/opt/fabrik/scripts/sysadmin/
scp scripts/sysadmin/proactive-check.sh vps:/opt/fabrik/scripts/sysadmin/
scp scripts/sysadmin/system-prompt.txt vps:/opt/fabrik/scripts/sysadmin/
scp ops/vps-sysadmin-bot.service vps:/tmp/

# Make executable
ssh vps 'chmod +x /opt/fabrik/scripts/sysadmin/bot.py /opt/fabrik/scripts/sysadmin/proactive-check.sh'
```

### Step 4: Configure Telegram credentials

```bash
ssh vps 'cat > /opt/fabrik/.env.sysadmin << EOF
# Required
TELEGRAM_BOT_TOKEN=<your-bot-token-from-botfather>
TELEGRAM_OWNER_ID=<your-numeric-telegram-user-id>

# Optional — uncomment to override defaults
# SYSADMIN_HEALTH_HOST=127.0.0.1   # set to 10.99.0.1 to expose health on WG mesh (W5, 2026-06-01)
# SYSADMIN_HEALTH_PORT=8017
# SYSADMIN_MODEL=opus
# SYSADMIN_PROJECT_DIR=/opt/fabrik
EOF'
```

To get your Telegram user ID: message `@userinfobot` on Telegram.

To create a bot: message `@BotFather` → `/newbot` → copy the token.

If reusing an existing bot (e.g. the one Alertmanager uses), get the token from Alertmanager config:
```bash
ssh vps 'grep bot_token /opt/monitoring/configs/alertmanager/alertmanager.yml'
ssh vps 'grep chat_id /opt/monitoring/configs/alertmanager/alertmanager.yml'
```

### Step 5: Install systemd service

```bash
ssh vps 'sudo cp /tmp/vps-sysadmin-bot.service /etc/systemd/system/ && \
         sudo systemctl daemon-reload && \
         sudo systemctl enable --now vps-sysadmin-bot'
```

### Step 6: Install all scheduled routines (single cron file)

```bash
ssh vps 'sudo tee /etc/cron.d/vps-sysadmin > /dev/null << "EOF"
# VPS AI Sysadmin — scheduled routines

# Proactive health check — every 15 min
*/15 * * * * root /opt/fabrik/scripts/sysadmin/proactive-check.sh >> /var/log/sysadmin-proactive.log 2>&1

# Morning report — daily 08:00
0 8 * * * root /opt/fabrik/scripts/sysadmin/morning-report.sh >> /var/log/sysadmin-proactive.log 2>&1

# Weekly security patrol — Monday 08:30
30 8 * * 1 root /opt/fabrik/scripts/sysadmin/weekly-security.sh >> /var/log/sysadmin-proactive.log 2>&1

# Weekly maintenance — Sunday 03:00
0 3 * * 0 root /opt/fabrik/scripts/sysadmin/weekly-maintenance.sh >> /var/log/sysadmin-proactive.log 2>&1

# Monthly backup verification — 1st of month 04:00
0 4 1 * * root /opt/fabrik/scripts/sysadmin/monthly-backup-verify.sh >> /var/log/sysadmin-proactive.log 2>&1
EOF'
```

### Step 7: Install log rotation

```bash
ssh vps 'sudo tee /etc/logrotate.d/vps-sysadmin-bot > /dev/null << "EOF"
/var/log/vps-sysadmin-bot.log {
    weekly
    rotate 4
    compress
    missingok
    notifempty
    copytruncate
}
EOF

sudo tee /etc/logrotate.d/vps-sysadmin-proactive > /dev/null << "EOF"
/var/log/sysadmin-proactive.log {
    weekly
    rotate 4
    compress
    missingok
    notifempty
    copytruncate
}
EOF'
```

### Step 8: Test

1. Send "status" on Telegram → should get VPS status within 30s
2. Send "how many containers are running?" → should get count
3. Wait 15 min → proactive check should run silently (check `/var/log/sysadmin-proactive.log`)
4. Send "done" → should confirm session ended

### Step 9: Verify after reboot

```bash
ssh vps 'sudo reboot'
# Wait 2 minutes
ssh vps 'systemctl is-active vps-sysadmin-bot'  # should be "active"
```

Send "status" on Telegram to confirm it survived.

## Files Manifest (for backup/replication)

Everything needed to rebuild the sysadmin bot from scratch:

| File | Repo location (WSL) | VPS location | Purpose |
|---|---|---|---|
| `scripts/sysadmin/bot.py` | `/opt/fabrik/scripts/sysadmin/bot.py` | same | Telegram bot + session management |
| `scripts/sysadmin/proactive-check.sh` | `/opt/fabrik/scripts/sysadmin/proactive-check.sh` | same | Two-stage cron script |
| `scripts/sysadmin/system-prompt.txt` | `/opt/fabrik/scripts/sysadmin/system-prompt.txt` | same | Claude Code role + rules |
| `ops/vps-sysadmin-bot.service` | `/opt/fabrik/ops/vps-sysadmin-bot.service` | `/etc/systemd/system/` | Systemd service unit |
| `.env.sysadmin` | — (VPS only, not in git) | `/opt/fabrik/.env.sysadmin` | Telegram token + owner ID |
| Cron | — (VPS only) | `/etc/cron.d/vps-sysadmin` | All 5 scheduled routines (proactive, morning, security, maintenance, backup) |
| Logrotate | — (VPS only) | `/etc/logrotate.d/vps-sysadmin-*` | Log rotation |

## Capabilities & Limitations

**Assessed via live testing on 2026-05-20.** Tested: status checks, OOM investigation, restart-loop triage, disk pressure, multi-issue P0-P4 triage, multi-turn session with autonomous action (bumped Apprise memory live), morning report, weekly security, monthly backup verify.

### What it does (proven in testing)

| Capability | Evidence |
|---|---|
| Triages by P0-P4 severity tiers | Multi-issue test: sorted cert (P0) → redis-exporter (P3) → apprise (P4) |
| Correlates metrics with logs before acting | OOM test: checked docker events, docker stats, Prometheus failcnt, dmesg, container logs — all before concluding "no OOM" |
| Tracks patterns across sessions | Detected 4th consecutive false-positive OOM report via shift notes, flagged "upstream prompt source needs investigation" |
| Backs up before modifying | Apprise memory bump: saved compose backup before editing |
| Warns about downstream risks | After editing compose: "remember to `git commit && git push` before `fabrik redeploy` so the VPS-side `git pull` picks it up" |
| Knows when NOT to act | Restart-loop playbook: "Do NOT restart a container that's already restart-looping" |
| Reports with evidence tables | OOM report included 8-row evidence table with specific values |
| Finds real issues proactively | Monthly backup verify found: postgres-dumps hook broken (exit 127), stale e2e plan, recovery confidence LOW |

### What it doesn't do (known gaps)

| Gap | What a production fleet would have | What we have | Priority to add |
|---|---|---|---|
| Trending/history | "Memory grew 20% this week" — day-over-day comparison | Single-point-in-time checks only | High — morning report could compare to yesterday |
| Cross-service correlation | "Postgres slow → GlitchTip queue → worker memory rising" | Investigates containers in isolation | Medium |
| Capacity planning | "At this growth rate, upgrade VPS in 3 months" | Only `predict_linear` for disk | Medium |
| Post-incident review | Structured RCA, tracks recurrence, verifies fix stuck | Shift notes — no structured follow-up | Low |
| Runbook evolution | "Last time X happened, Y didn't work, so now we do Z" | Playbooks are static in system prompt | Low |
| Proactive maintenance | "Schedule Netdata cache cleanup for Sunday 3am" | Only reacts, doesn't propose scheduled work | Low |
| Multi-VPS awareness | "This pattern happened on VPS2 last month" | Single VPS only | Future (when VPS2 exists) |

### Honest rating

**15-year solo sysadmin, not a fleet of 20-year veterans.** For a solo dev running one VPS with ~36 containers, this covers 90%+ of what's actually needed. The gaps above matter at scale (50+ servers). The sysadmin catches issues before alerts fire, acts autonomously when safe, reports concisely for phone reading, and costs $0 on quiet days.

## Architecture Reference

- **Archived plan:** `docs/archive/2026-05-20-vps-ai-sysadmin-plan-executed.md` — original design rationale + comparison with old ARO Brain plan
- **Audit prompts:** `docs/infrastructure/audit-prompts/*.md` — the analysis checklists Claude uses when you ask for audits
- **Audit scripts:** `scripts/audit/*.sh` — the diagnostic scripts Claude runs locally
- **VPS inventory:** `docs/infrastructure/vps-complete-inventory.md` — what Claude reads to understand the current stack
- **Hardening checklist:** `docs/infrastructure/audit-prompts/08-hardening-remediation.md` — post-audit remediation guide
