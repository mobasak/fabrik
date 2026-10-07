# Fabrik (hub) — Services

**Last Updated:** 2026-10-07 (converged against the code: the live drivers and their env keys, the repo-of-record composes under `infra/`, the box-local machinery; retired services collapsed into one table)

What the hub runs, what it depends on, and where each piece is documented in depth.

## Services This Project Runs

**The hub ships no deployed service of its own.** `fabrik` is a CLI (`src/fabrik/cli.py`) run from WSL: each command
executes and exits, and deploys reach the VPS fleet through `fabrik apply specs/services/<id>.yaml` (SSH + Docker
Compose). The hub does, however, run **box-local machinery on the WSL workstation** — systemd units, cron jobs and
Claude Code hooks. Each has its own document; this file links them rather than restating them.

| What | Where it runs | Documented in |
|------|---------------|---------------|
| `fabrik` CLI | WSL, on demand | `docs/QUICKSTART.md` · `docs/reference/fabrik-cli-reference.md` |
| systemd units (Postgres, Redis, Docker, the Fabrik MCP and citation services, the DR and env watchers) | WSL, at boot | `docs/workstation/wsl-startup-inventory.md` § A |
| Cron jobs and timers (account rotation tick, WIP backup, DR env backup and recovery test, CI-fix dispatcher, weekly catch-up audits, registry reconcile) | WSL crontab | `docs/workstation/wsl-startup-inventory.md` § C |
| Claude account rotation and the `QUOTA:` posture | WSL cron, every 5 min | `docs/workstation/claude-account-rotation.md` · `docs/workstation/quota-dashboard.md` |
| fabrik-mail (repo-to-repo mail, the dispatcher and watchers) | WSL, `/opt/fabrik-mail/` | `docs/reference/fabrik-mail.md` |
| Claude Code hooks, the self-watch and the death/revival mesh | WSL, per session | `docs/workstation/hooks-index.md` |
| Liveness audit (proves the cron and systemd machinery actually runs) | WSL, on demand | `docs/workstation/liveness.md` |

None of these exposes a health endpoint; `scripts/sysadmin/liveness_audit.py` is the check that they run.

## External Dependencies

### Core infrastructure — what `fabrik apply` and the registrars call

Each row is a driver under `src/fabrik/drivers/` that the orchestrator or CLI imports today.

| Dependency | Driver | Env keys read | Used for | Failure |
|---|---|---|---|---|
| **SSH to the VPS fleet** | `ssh.py` | `FABRIK_VPS_SSH_HOST` (default alias `vps`, `src/fabrik/drivers/ssh.py:31`) | every deploy, registrar and probe | fatal — nothing deploys |
| **GitHub** | (git over SSH on the VPS) | — | the VPS `git pull`s the app; commit → push → redeploy | redeploy ships the old commit |
| **PostgreSQL** `postgres-main` | `postgres.py` | — (runs over SSH) | per-service database + role | registrar failure, recorded in `.fabrik/state/<id>.json` |
| **Redis** `redis-main` | `redis.py` | — (over SSH) | per-service logical DB index | registrar failure |
| **Cloudflare** | `cloudflare.py` | `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`, `VPS_IP` | DNS records | DNS step fails; `--keep-on-failure` keeps the app |
| **site-provisioner** | `dns.py` | `SITE_PROVISIONER_URL` (fallback `DNS_MANAGER_URL`, `src/fabrik/config.py:113-114`), `SITE_PROVISIONER_API_KEY`, `SITE_PROVISIONER_INTERNAL_URL`, `SITE_PROVISIONER_CONTAINER*` | the DNS provider behind `DNS_PROVIDER=site-provisioner` (`src/fabrik/config.py:112`) | DNS step fails |
| **Backrest** (restic → Backblaze B2) | `backrest.py` | `FABRIK_VPS_SSH_HOST` | backup-coverage check for `has_persistent_data` (warns, never writes a plan) | warning only |
| **Gatus** | `gatus.py` | — (SSH + scp) | health-monitor endpoints | registrar failure |
| **Prometheus** | `prometheus.py` | — (over SSH) | scrape targets for `exposes_metrics` | registrar failure |
| **GlitchTip** | `glitchtip.py` | `GLITCHTIP_URL`, `GLITCHTIP_AUTH_TOKEN`, `GLITCHTIP_ORG_SLUG`, `GLITCHTIP_TEAM_SLUG` | per-project error tracking | registrar failure |
| **Grafana** | `grafana.py` | `GRAFANA_SERVICE_ACCOUNT_TOKEN` | deploy annotations | non-fatal, decorative |
| **Authelia** | `authelia.py` | — (over SSH) | access rules for `is_admin_dashboard` | registrar failure |
| **Meilisearch** | `meilisearch.py` | — (over SSH) | indexes for `has_search_feature` | registrar failure |
| **Watchdog sidecar** | `watchdog.py` | `FABRIK_VPS_CLAUDE_HOME` (`watchdog.py:146`); the `WATCHDOG_*` keys are read by the sidecar's own bootstrap, which the driver writes and configures | per-project image build + compose overlay | registrar failure |

Registrar failures are non-fatal: the CLI exits 2, prints them, and records them in the state file (D-644).

### On-demand services — called only by the command that needs them

| Dependency | Driver / caller | Env keys read | Used for |
|---|---|---|---|
| **Vultr** | `vultr.py` · `orchestrator/vultr_drill.py` | `VULTR_API_KEY` | the manual DR drill (`fabrik vultr drill`) — `docs/operations/disaster-recovery.md` |
| **RunPod** · **Modal** · **Vast.ai** | `runpod.py` · `modal_provider.py` · `vast_provider.py` | `RUNPOD_API_KEY` · `MODAL_TOKEN_ID`, `MODAL_TOKEN_SECRET` · `VAST_API_KEY` | `fabrik gpu rent` — `docs/operations/gpu-rent.md` |
| **SEO service** | `seo.py` (via `cli.py`) | `SEO_API_URL`, `SEO_API_KEY` | `fabrik seo site-register` |
| **Claude Code, headless** (`claude -p`) | `scripts/ci_fix_dispatcher.py`, `scripts/sysadmin/claude_broker.py`, `scripts/rivals_run.py` and others | the active account (rotation) | the CI-fix dispatcher, the VPS broker, research runs |

The OpenRouter subagent pool is OFF by ruling (D-181/D-182); nothing calls it.

### Service Status Summary (2026-10-07)

Not wired: `r2.py`, `tco.py`, `supabase.py` and `image_broker.py` are imported only by `src/fabrik/drivers/__init__.py`,
and `compose_updater.py`, `preflight.py` and `uptime_kuma.py` by nothing at all; no command calls any of the seven.
The Coolify driver and deployer are still imported (`coolify.py`, `orchestrator/deployer_coolify.py`) although Coolify
was decommissioned on 2026-05-30 (`coolify.py:4`); their retirement is backlog item W-00485146.

## VPS services (managed by `fabrik apply`, SSH + Docker Compose)

The repo of record for each shared service is its compose file under `infra/`; the live state (ports, URLs,
versions, what is actually running) is `docs/infrastructure/vps-complete-inventory.md`, and every URL is in
`docs/infrastructure/vps-urls.md`. Shared infrastructure runs on the hub (vps1) only; the spokes reach it over
WireGuard at `10.99.0.1:<port>`.

| Host | Compose (repo of record) | Services |
|---|---|---|
| vps1 | `infra/vps1/postgres/` | `postgres-main` — still PostgreSQL 16 on `postgres-data` until the PG18 hub window; the repo compose pins 18.6 on `postgres18-data` (D-647) |
| vps1 | `infra/vps1/redis/` | `redis-main` |
| vps1 | `infra/vps1/traefik/` | `traefik` |
| vps1 | `infra/vps1/authelia/` | `authelia` |
| vps1 | `infra/vps1/backrest/` | `backrest` |
| vps1 | `infra/vps1/gatus/` | `gatus` |
| vps1 | `infra/vps1/glitchtip/` | `glitchtip-web`, `glitchtip-worker` |
| vps1 | `infra/vps1/monitoring/` | `prometheus`, `alertmanager`, `grafana`, `loki`, `promtail`, `node-exporter`, `cadvisor`, `postgres-exporter`, `redis-exporter`, `pushgateway` |
| vps1 | `infra/vps1/meilisearch/` | `meilisearch` |
| vps1 | `infra/vps1/gotenberg/` | `gotenberg` |
| vps1 | `infra/vps1/browserless/` | `browserless` |
| vps1 | `infra/vps1/apprise/` | `apprise` |
| vps1 | `infra/vps1/n8n/` | `n8n` |
| vps1 | `infra/vps1/site-provisioner/` | `site-provisioner` |
| vps1 | `infra/vps1/ocoron-com/` | `wordpress`, `nginx`, `db`, `redis`, `backup` (the ocoron.com tenant stack) |
| vps1 | `infra/vps1/watchdog-test/` | `watchdog-test` |
| vps2, vps3 | `infra/vps{2,3}/traefik/`, `backrest/`, `monitoring-agent/` | `traefik`, `backrest`, `node-exporter`, `cadvisor`, `promtail` |

Every service sits on the external `fabrik` network behind Traefik and declares a memory limit
(`deployer_ssh._validate_compose()`); mesh-only services bind to `10.99.0.1`.

### Retired services

| Service | Retired | Replaced by |
|---|---|---|
| Coolify | 2026-05-30 | standalone compose stacks deployed by `fabrik apply`; the `coolify` Docker network was renamed `fabrik` on 2026-05-31 |
| Netdata | 2026-05-30 | node-exporter + cAdvisor → Prometheus → Grafana |
| Image Broker | 2026-06-02 | — (spec retired) |
| DNS Manager | not deployed | the Cloudflare and site-provisioner DNS drivers |
| Translator · Captcha · File API · MinIO | not deployed | — (object storage goes to Backblaze B2 / Cloudflare R2 directly) |
| Duplicati | 2026-04-17 | Backrest |

Their `*.vps1.ocoron.com` names no longer resolve.

## Service Management (Docker)

```bash
# Container status on a host (every docker command on the VPS needs sudo)
ssh vps "sudo docker ps --format 'table {{.Names}}\t{{.Status}}'"
# Restart one service
ssh vps "sudo docker restart <container>"
# Tail logs
ssh vps "sudo docker logs --tail 100 -f <container>"
```

## Quick Verification

```bash
# The shared database answers
ssh vps "sudo docker exec postgres-main pg_isready -U postgres"
# Every Gatus monitor, fleet-wide
curl -s https://status.vps1.ocoron.com
# What a spec would provision, before applying it (hub-side, read-only)
fabrik plan specs/services/<id>.yaml
# Registrars a deployed service is missing, and failures the last apply recorded
fabrik audit-registrars
```

## Troubleshooting

- **A deploy exits 2:** a registrar failed (non-fatal). The CLI printed it, `fabrik audit-registrars` lists it,
  and `.fabrik/state/<id>.json` records it; fix the cause and re-run `fabrik apply`.
- **SSH fails:** check the `vps` alias in `~/.ssh/config` and the WireGuard mesh; every deploy goes through it.
- **A redeploy ships old code:** the VPS pulls from GitHub — commit and push before `fabrik redeploy`.
