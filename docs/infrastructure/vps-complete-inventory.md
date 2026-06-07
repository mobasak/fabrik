# VPS Fleet — Complete Service Inventory

**Last Updated:** 2026-06-07 (Trio Phase 1+2+3+4 LIVE across the FULL FLEET since 2026-06-06; **Phase 5.1.a operator-reversal cron LIVE on full fleet 2026-06-07** via `detect_reversals.py` + `*/5 min` cron; **rate-limited 429 wakes now tracked** via `aro_wake_requests_total{status="rate_limited"}` + `AroWakeLowSuccessRate` denominator excludes them; **stale netdata scrape job removed** (caused 24× Telegram flood overnight); **6 bootstrap defenses shipped** including preflight SSH-user-transition trap detection; **DR drill MEASURED end-to-end 2026-06-07**: bootstrap-vps.sh on Vultr → 3m 13s wall-clock, 9.3× under the ≤30 min target, 15/15 substantive end-state checks.)
**Last probe report:** [`probe-reports/infra-probe-2026-06-07T20-20Z.yaml`](probe-reports/infra-probe-2026-06-07T20-20Z.yaml)
**Hosts:** **vps1** (LA, hub) · **vps2** (Coventry UK, spoke) · **vps3** (Coventry UK, spoke)
**Network:** Wireguard mesh `10.99.0.0/24` over UDP `51820`, MTU `1420`, hub-and-spoke topology
**Deploy model:** SSH + Docker Compose (no Coolify; removed 2026-05-30 — see `docs/development/plans/archived/2026-05-30-coolify-residue-cleanup.md`)

## Quick state (current)

- **vps1:** 31 containers — the 29 documented below plus `watchdog-test` + `watchdog-test-watchdog` (T-P5 dogfood test running since 2026-06-03; sidecar self-heals nginx via Claude Code Opus diagnose + `restart_container` Tier A action; verified end-to-end 2026-06-04 with 34s incident→action close time). 4 shared infra services (postgres-main, redis-main, glitchtip-web, authelia) + loki are bound to `10.99.0.1:<port>` mesh IPs so spokes can reach them.
- **vps2:** 5 containers — monitoring agents (node-exporter / cadvisor / promtail) + Traefik (public TLS for `*.vps2.ocoron.com`). DNS is **live** as of 2026-05-31 afternoon.
- **vps3:** 5 containers — same as vps2. DNS is **live** as of 2026-05-31 afternoon.
- **Mesh handshakes:** active, cross-Atlantic RTT 133–134 ms, 0 % loss
- **Cross-host shared infra reachable:** postgres `5432` / redis `6379` / glitchtip `8000` / authelia `9091` / loki `3100` — all verified from vps2 via `10.99.0.1:<port>`
- **Spoke DNS (NEW today):** `vps2.ocoron.com` + `*.vps2.ocoron.com` → `96.9.214.128`; `vps3.ocoron.com` + `*.vps3.ocoron.com` → `104.128.190.151`. Wildcards cover `auth.vpsN`, `<tenant>.vpsN`, etc. Apex + wildcard each, no per-service A records needed.
- **Spoke Traefik:** listening on 80 + 443 on each spoke's public IP; `authelia-vps1@file` middleware ready (forward-auth → `http://10.99.0.1:9091/api/verify`). Public TLS via Let's Encrypt will issue on first tenant deploy.
- **Loki ingest:** spokes pushing logs successfully (`host` label values: `["vps1","vps2","vps3"]`)
- **Prometheus:** scraping **14 active targets across 12 jobs (verified 2026-06-07T20:20Z via /api/v1/targets)** (12 vps1 + 6 spoke), all up; every series carries `host` label
- **Grafana:** all 5 dashboards have `host` template variable (regex `/^vps/`)
- **Alert rules:** ~~`spoke_health` group~~ — **NOT in alerts.yml as of 2026-06-07T20:20Z**. The 5 live groups: aro_wake (2 rules), container_health (6), host_health (3), service_health (1), fabrik-registrar-drift (1).
- **AI sysadmin:** `proactive-check.sh` tags every anomaly with originating host (`cpu_high[vps2]`)
- **Backups:** B2 bucket holds restic repo `a256277c45` with **4 plans live** (`postgres-dumps`, `docker-volumes`, `opt-configs`, `host-state`) since 2026-06-01. First snapshots: 117 MiB on B2 (612 MiB uncompressed, 5.23× compression). Path-preserving bind mounts on the Backrest container — see [`vps-hub-rebuild.md`](vps-hub-rebuild.md) for the rebuild contract.
- **Cloudflare API token (`/opt/fabrik/.env`):** refreshed 2026-05-31 afternoon by syncing the working token from the local site-provisioner instance (`/opt/site-provisioner/.env`). Pre-edit backup at `backups/.env.backup.20260531-155948`. Verified active via `curl /user/tokens/verify`.
- **DNS state (post-residue-cleanup, evening):** 17 A records in CF zone `ocoron.com`. vps1 has 12 live subdomains (auth, auto, backup, browser, errors, monitor, notify, pdf, **provision** [new — was never in CF; site-provisioner had a Traefik router but no public DNS — created during the cleanup], search, status, vps1 apex). vps2 + vps3 each have apex + wildcard. **6 stale subdomains deleted** (`coolify`, `control`, `dns`, `fabrik-e2e-timing`, `images`, `netdata`).
- **`fabrik apply --target-vps`:** shipped 2026-05-31 as W-Multi M4; **destroy + redeploy parity** shipped 2026-06-02 as W3; **`inject_env` + compose rollback parity** shipped 2026-06-02 as W14. Specs gain optional `target_vps: vps1|vps2|vps3` field (regex-validated). CLI `--target-vps` flag overrides spec for all three verbs. A single `contextlib.contextmanager` `_target_vps_env(ctx)` in `deployer_ssh.py` env-swaps `FABRIK_VPS_SSH_HOST` around (a) the app deploy block, (b) post-deploy DSN/Redis-URL injection, and (c) compose rollback (reads `target_vps` from the resource record's metadata). DNS provisioner picks the right IP from the `VPS_IPS` map. Hub-side registrars (postgres, redis, gatus, glitchtip, authelia, grafana, meilisearch) run **outside** the swap and stay on vps1 by design. 130/130 deployer + integration + rollback tests pass after W14. CLI: `.venv/bin/fabrik apply specs/services/<id>.yaml --target-vps vps2`.
- **First spoke deploy attempted 2026-06-02 (W14 live-verify):** `specs/services/spoke-canary.yaml` (`nginx:alpine`, target_vps=vps2). Container deployed healthy on vps2 (`Up (healthy)`), hub-side registrars stayed on vps1, but **verifier returned 404 from `https://canary.vps2.ocoron.com/`** because vps2's Traefik has no `gzip@docker` middleware defined (the orchestrator emits `traefik.http.routers.<svc>.middlewares=gzip@docker` on every service deploy; on vps1 that middleware is defined as a label on the `meilisearch` container, on spokes no carrier exists). Rollback correctly tore the canary down on vps2 (not the hub). **W15 in the active plan** is the remediation: declare `traefik.http.middlewares.gzip.compress=true` on the spoke Traefik container itself in `bootstrap-vps.sh` step_03.

## site-provisioner status — INTERIM, not pipeline-ready

`site-provisioner` is running on vps1 at `provision.vps1.ocoron.com` (container healthy, alembic migrations applied, Cloudflare + Postgres connectivity verified, `/health` returns 200) — but **do not treat it as a production-deployable service yet**. It was brought up manually this afternoon to unblock the spoke DNS step. The proper `fabrik apply` pipeline for it has known gaps that must close before redeploy via fabrik is safe:

| Gap | What's done today | What's still needed |
| :--- | :--- | :--- |
| Upstream repo's `compose.yaml` still references the legacy `coolify` Docker network | **RESOLVED** — committed in `fa32d61` (bundled into a docs commit) and pushed to `mobasak/site-provisioner@main`. Local + origin in sync. | none |
| Spec `secrets.from_env` was missing 3 keys + 5 env literals referenced by the repo's compose.yaml at interpolation time | [`specs/services/site-provisioner.yaml`](../../specs/services/site-provisioner.yaml) now declares all 21 `${VAR}` references (13 literals incl. `DATABASE_URL` placeholder + 9 from-env secrets) | One clean end-to-end `fabrik apply` round-trip (pending — gated on operator authorization since the deploy would rotate the postgres password) |
| `/opt/fabrik/.env` was missing `BING_WEBMASTER_API_KEY` and had a different `API_KEY` than vps1's live value | Synced both from vps1's live `.env`; preserved vps1's API_KEY value so existing callers do not break | None |
| GitHub host-key trust missing on vps1's root SSH (post-Coolify-removal cleanup wiped it) | Added `github.com` to `/root/.ssh/known_hosts` on vps1; **and** patched the deployer + bootstrap so this re-creates itself going forward (see "Permanent fixes shipped today" below) | None |
| Postgres user `site_provisioner` password was unknown (not in fabrik state) | Rotated to a fresh 32-char a-zA-Z0-9 password; live `.env` on vps1 updated; `DATABASE_URL` resolved | The new password is not yet captured in fabrik state — when `fabrik apply` runs end-to-end the postgres registrar will overwrite it cleanly |

**Operational implication (as of 2026-06-02):** the upstream `compose.yaml` rename push HAS landed — `vps:/opt/site-provisioner/compose.yaml` now declares `networks: [fabrik]` (verified live, no `coolify` references). What remains: one clean end-to-end `fabrik apply` round-trip to confirm the postgres-registrar password handoff cleanly captures into fabrik state. Until then, treat the running container as a one-off; safest restart is `ssh vps "cd /opt/site-provisioner && sudo docker compose up -d"`.

## Permanent fixes shipped today (deployer + bootstrap)

These prevent today's failure modes from recurring:

| Fix | Where | Effect |
| :--- | :--- | :--- |
| Deployer auto-trusts the git host before clone | [`src/fabrik/orchestrator/deployer_ssh.py`](../../src/fabrik/orchestrator/deployer_ssh.py) — new `_extract_git_host()` + `ssh-keyscan` pre-step inside `_deploy_git()` | First-ever git-source `fabrik apply` on a fresh host no longer fails with "Host key verification failed" |
| Bootstrap pre-seeds `github.com` host key on spokes | [`scripts/bootstrap/bootstrap-vps.sh`](../../scripts/bootstrap/bootstrap-vps.sh) step 03 (after Docker install + `fabrik` network create) | New spokes are ready for git-source deploys from minute one; `fabrik apply --target-vps vpsN` (when that ships) won't trip on missing trust |

## Re-verify / Update This Document

```bash
# Container counts per host
ssh vps  'sudo docker ps --format "{{.Names}}" | wc -l'   # expect 29 (28 shared + site-provisioner interim)
ssh vps2 'sudo docker ps --format "{{.Names}}" | wc -l'   # expect 5
ssh vps3 'sudo docker ps --format "{{.Names}}" | wc -l'   # expect 5

# Mesh handshake state
ssh vps 'sudo wg show'

# Prometheus targets across hosts (expect 14/14 up across 12 jobs as of 2026-06-07T20:20Z; was 18/15 briefly on 2026-05-31 when spoke scrape jobs were added, dropped at some point)
ssh vps 'sudo docker exec prometheus wget -qO- http://localhost:9090/api/v1/targets' \
  | python3 -c 'import json,sys; d=json.load(sys.stdin)["data"]["activeTargets"]; up=sum(1 for t in d if t["health"]=="up"); print(f"{up}/{len(d)} up")'

# UFW per host
ssh vps  'sudo ufw status numbered'
ssh vps2 'sudo ufw status numbered'
ssh vps3 'sudo ufw status numbered'

# Spoke DNS resolves (auth NS — bypass caching)
NS=$(dig +short NS ocoron.com | head -1)
for h in vps2.ocoron.com test.vps2.ocoron.com vps3.ocoron.com test.vps3.ocoron.com; do
  echo "$h -> $(dig +short @"$NS" "$h")"
done

# Cloudflare API token in /opt/fabrik/.env is active
CF_TOKEN=$(grep '^CLOUDFLARE_API_TOKEN=' /opt/fabrik/.env | cut -d= -f2-)
curl -s -H "Authorization: Bearer $CF_TOKEN" https://api.cloudflare.com/client/v4/user/tokens/verify \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d.get("messages",[{}])[0].get("message","?"))'

# site-provisioner interim health
ssh vps 'sudo docker exec site-provisioner curl -sf http://localhost:8001/health' | head -c 200
```

---

## vps1 — Hub (LA)

**Provider:** GreenCloudVPS (`12th Birthday Sale - 1212 LA`) — Ubuntu 24.04 LTS
**Specs:** 6 vCores (x86_64 EPYC Genoa), 11.6 GB RAM, 108 GB disk
**Public IP:** 172.93.160.197
**Mesh IP:** 10.99.0.1
**Hostname:** vps1.ocoron.com
**SSH:** ozgur user, key auth only (root disabled, password auth disabled)

### Container inventory (31 running — 29 platform + 2 watchdog dogfood)

| Container | Memory limit | Purpose |
| :--- | :--- | :--- |
| `traefik` | — | Public HTTPS termination, Let's Encrypt, Authelia forward-auth dispatch |
| `authelia` | 512m | SSO + 2FA forward-auth for all `*.vps1.ocoron.com` admin dashboards |
| `postgres-main` | 2g | Shared PostgreSQL 16 — multi-tenant, one DB per service via registrar |
| `redis-main` | — | Shared Redis 7 — one logical DB per service |
| `postgres-exporter` | — | Postgres metrics for Prometheus |
| `redis-exporter` | — | Redis metrics for Prometheus |
| `prometheus` | 1.5g | Time-series store + alert evaluator. 30 d / 5 GB retention. |
| `grafana` | — | Dashboards (Prometheus + Loki sources, pre-provisioned) |
| `loki` | — | Log aggregator. Bound to `10.99.0.1:3100` for spoke pushes. 7 d retention. |
| `promtail` | — | Ships vps1 container stdout to Loki |
| `alertmanager` | — | Routes Prometheus alerts → Apprise → Telegram |
| `cadvisor` | — | Container metrics for vps1's Prometheus |
| `node-exporter` | — | Host metrics for vps1's Prometheus |
| `pushgateway` | 64m | Short-lived metric pushes (used by `audit_all_registrars.py` cron) |
| `gatus` | 256m | Synthetic health probes for all services |
| `apprise` | 768m | Notification dispatcher (Alertmanager → Telegram) — gunicorn workers 2 |
| `backrest` | 512m | restic-based backups → B2 (4 plans live since 2026-06-01: `postgres-dumps`, `docker-volumes`, `opt-configs`, `host-state`). Path-preserving bind mounts: `/opt`, `/etc`, `/usr/local/bin`, `/root/.ssh`, `/home/ozgur/.ssh`, `/var/lib/docker/volumes` all RO. Restic repo `a256277c45`. See [`vps-hub-rebuild.md`](vps-hub-rebuild.md). |
| `glitchtip-web` | 512m | Self-hosted Sentry-compat error tracker. UI at `errors.vps1.ocoron.com` |
| `glitchtip-worker` | 512m | GlitchTip background worker (Celery) |
| `meilisearch` | 512m | Shared search engine, per-service index via registrar |
| `n8n` | 2g | Visual workflow automation (`auto.vps1.ocoron.com`) |
| `browserless` | 2g | Headless Chrome HTTP API |
| `gotenberg` | 512m | LibreOffice + Chrome → PDF service |
| `site-provisioner` | 512m | **INTERIM** — DNS / domain registrar API (Namecheap + Cloudflare + DomainNameAPI). Stood up manually 2026-05-31; `fabrik apply` pipeline not yet ready — see "site-provisioner status" above |
| `ocoron-com-nginx-1` | — | Tenant: ocoron.com WordPress front-end |
| `ocoron-com-wordpress-1` | — | Tenant: WordPress PHP-FPM |
| `ocoron-com-db-1` | — | Tenant: MariaDB (WP-specific, not on shared postgres-main) |
| `ocoron-com-redis-1` | — | Tenant: per-WP Redis cache |
| `ocoron-com-backup-1` | — | Tenant: nightly mysqldump sidecar |
| `watchdog-test` | 64m | T-P5 dogfood — nginx:alpine target. Container the sidecar watches. |
| `watchdog-test-watchdog` | 1024m | T-P5 dogfood — per-project Claude-driven watchdog sidecar. Bind-mounts `~/.claude/` + `~/.claude.json` from host (`FABRIK_VPS_CLAUDE_HOME`), `/var/run/docker.sock`, project tree RO. Self-heals via Tier A `restart_container` when the main container exits. Verified end-to-end 2026-06-04: `docker kill watchdog-test` → detection in 60s → Opus diagnose → restart → resolved in 3s. |

### `/opt` service stacks on vps1

```text
/opt/
├── apprise/         — Notification dispatcher
├── authelia/        — SSO + 2FA (config + named volume sync via authelia-config-sync.service)
├── authelia-config-sync/ — inotify watcher: /opt/authelia/config → named volume → docker restart authelia
├── backrest/        — Backup service (config at /opt/backrest/config/config.json — restic password lives HERE)
├── browserless/     — Headless Chrome
├── containerd/      — Docker runtime state
├── fabrik/          — Symlink or placeholder (Fabrik runs on WSL, not vps)
├── gatus/           — Synthetic checks
├── glitchtip/       — Error tracker
├── gotenberg/       — PDF service
├── meilisearch/     — Search engine
├── monitoring/      — Prometheus + Grafana + Loki + Alertmanager + cAdvisor + exporters stack
├── n8n/             — Automation
├── ocoron-com/      — WordPress tenant
├── postgres/        — Shared PostgreSQL 16
├── prometheus/      — (stale leftover from pre-fabrik-network rename; real one is in /opt/monitoring)
├── redis/           — Shared Redis 7
├── site-provisioner/ — INTERIM git-clone of mobasak/site-provisioner@main (compose.yaml hand-patched coolify→fabrik on the VPS; upstream push pending). Container "site-provisioner" runs from here.
├── traefik/         — Reverse proxy + Let's Encrypt
├── backups/         — pg_dump nightly target (referenced by Backrest postgres-dumps plan)
└── manually_installed.txt — Provenance log
```

---

## vps2 — Coventry UK spoke

**Provider:** GreenCloudVPS (`BudgetKVMCUK-3` SKU)
**Specs:** 4 vCores (EPYC Rome), 8 GB RAM, 60 GB NVMe RAID-10, 8 TB BW
**Public IP:** 96.9.214.128
**Mesh IP:** 10.99.0.2
**Hostname:** vps2.ocoron.com
**SSH:** ozgur user, key auth only (root + password disabled — matches vps1)
**Bootstrap commit:** `c838a03` via `scripts/bootstrap/bootstrap-vps.sh`

### Container inventory — vps2 (5 running)

| Container | Bind | Purpose |
| :--- | :--- | :--- |
| `traefik` | `0.0.0.0:80,443` (public) | Public TLS termination for `*.vps2.ocoron.com`. `authelia-vps1@file` middleware ready. **`gzip@docker` middleware now defined (W15 ship 2026-06-02)** via labels on the Traefik container itself. First Let's Encrypt cert issued live (for `canary.vps2.ocoron.com`) confirms the routing path works end-to-end. |
| `node-exporter` | `10.99.0.2:9100` (mesh-only) | Host metrics → vps1's Prometheus over mesh |
| `cadvisor` | `10.99.0.2:8080` (mesh-only) | Container metrics → vps1's Prometheus over mesh |
| `promtail` | `10.99.0.2:9080` (mesh-only) | Ships container stdout → vps1's Loki at `10.99.0.1:3100` |
| `backrest` | no public/mesh bind | W11 — writes backups to own restic repo at `b2:vps1-ocoron-backups/spokes/vps2/`. 2 plans: `host-state` + `opt-configs`. Restic password mirrored to DR-store as `vps2-restic-password-latest`. |

### `/opt` structure on vps2

```text
/opt/
├── containerd/
├── monitoring-agent/        — compose.yaml + promtail.yaml (rendered by bootstrap-vps.sh)
├── traefik/                 — compose.yaml + traefik.yml + acme.json + dynamic/authelia.yml
└── backrest/                — compose.yaml + .env.backrest + config/config.json + .restic-password (W11)
```

**DNS live as of 2026-05-31 afternoon:** `vps2.ocoron.com` + `*.vps2.ocoron.com` → `96.9.214.128` (Cloudflare, unproxied). Wildcard covers `auth.vps2`, `<tenant>.vps2`, etc. Awaiting first tenant deploy; first Let's Encrypt issuance will happen on that deploy.

---

## vps3 — Coventry UK spoke

**Provider:** GreenCloudVPS (`BudgetKVMCUK-3` SKU)
**Specs:** 4 vCores (EPYC Rome), 8 GB RAM, 60 GB NVMe RAID-10, 8 TB BW
**Public IP:** 104.128.190.151
**Mesh IP:** 10.99.0.3
**Hostname:** vps3.ocoron.com (corrected via `hostnamectl` during bootstrap — initial typo `vpse.ocoron.com`)
**SSH:** ozgur user, key auth only

### Container inventory — vps3 (5 running)

Identical to vps2: `traefik` (public 80+443, with the W15 `labels:` block now in place), `node-exporter` / `cadvisor` / `promtail` bound to mesh IP (10.99.0.3), and `backrest` (W11) writing to its own restic repo at `b2:vps1-ocoron-backups/spokes/vps3/`.

### `/opt` structure on vps3

Identical to vps2: `containerd/` + `monitoring-agent/` + `traefik/` + `backrest/`.

**DNS live as of 2026-05-31 afternoon:** `vps3.ocoron.com` + `*.vps3.ocoron.com` → `104.128.190.151` (Cloudflare, unproxied). Wildcard covers `auth.vps3`, `<tenant>.vps3`, etc.

---

## Network Architecture

### Public ingress (each host independently)

```text
Internet
  ├─► vps1:443 ─► Traefik (vps1) ─► all *.vps1.ocoron.com services
  ├─► vps1:80  ─► Traefik HTTP → HTTPS redirect
  ├─► vps2:443 ─► Traefik (vps2) ─► (no tenants yet — when deployed: *.vps2.ocoron.com)
  ├─► vps3:443 ─► Traefik (vps3) ─► (no tenants yet — when deployed: *.vps3.ocoron.com)
  ├─► vpsN:22  ─► SSH (Ed25519 key, root disabled, password disabled, fail2ban active)
  └─► vpsN:51820/udp ─► Wireguard mesh
```

### Mesh (private, VPS-to-VPS)

```text
                   wg0 = 10.99.0.0/24, UDP 51820

           vps1 (10.99.0.1, hub) ◄─────────────── vps2 (10.99.0.2, spoke)
                  ▲
                  └──────────────────────────────── vps3 (10.99.0.3, spoke)

           (spoke-to-spoke is NOT routed; AllowedIPs scoped to 10.99.0.0/24
            on the hub-side peer config, /32 on the spoke side. Spoke A
            traffic to spoke B would have to bounce off the hub — disabled.)
```

### Mesh-exposed services on vps1 (reachable by spokes)

| Service | Bind | Verified from spoke | Notes |
| :--- | :--- | :--- | :--- |
| Wireguard | `0.0.0.0:51820/udp` | n/a (hub listener) | |
| Loki | `10.99.0.1:3100` | ✓ (spoke promtail pushing) | Added 2026-05-31 batch 1 |
| postgres-main | `10.99.0.1:5432` | ✓ (vps2 `pg_isready`) | Added 2026-05-31 batch 2 |
| redis-main | `10.99.0.1:6379` | ✓ (vps2 `redis-cli ping`) | Added 2026-05-31 batch 2 |
| glitchtip-web | `10.99.0.1:8000` | ✓ (vps2 HTTP 200) | Added 2026-05-31 batch 2 |
| authelia | `10.99.0.1:9091` | ✓ (vps2 `/api/health` 200) | Added 2026-05-31 batch 2; forward-auth target for spoke Traefik |

All host-port bindings use `10.99.0.1:<port>:<port>` syntax so traffic from the public internet cannot reach these ports — only mesh peers can. Belt-and-suspenders: `DOCKER-USER` chain blocks these ports on the public iface anyway.

Pattern for adding a mesh-exposed service: add `ports: ["10.99.0.1:<port>:<port>"]` to its compose file on vps1, recreate. Binds the host-side port ONLY to the wg0 interface — public internet cannot reach it.

### Docker networks per host

| Host | Network | Subnet | Purpose |
| :--- | :--- | :--- | :--- |
| vps1 | `fabrik` (bridge) | (default) | Shared by all platform services on vps1 |
| vps1 | `ocoron-com_ocoron-com-internal` | (default) | Tenant-private network for ocoron.com WP stack |
| vps2 | `fabrik` (bridge) | (default) | Created by bootstrap; empty until first tenant deploys |
| vps3 | `fabrik` (bridge) | (default) | Same |

**Naming note:** the network was renamed from `coolify` to `fabrik` on 2026-05-31 (commit `89879e4`). Some legacy comments may still reference `coolify` — they're historical artifacts; the actual network is `fabrik` everywhere now.

### Firewall (per host)

#### vps1 UFW (post-cleanup 2026-05-31 evening)

```text
[ 1] 22/tcp                     ALLOW   # SSH
[ 2] 80/tcp                     ALLOW   # HTTP
[ 3] 443/tcp                    ALLOW   # HTTPS
[ 4] 1194/tcp                   ALLOW   # OpenVPN — out-of-platform-scope (operator's personal VPN); W5 documented, no probe required
[ 5] 8000/tcp                   DENY    # belt-and-suspenders (stale Coolify comment, rule retained)
[ 6] 51820/udp                  ALLOW   # Wireguard mesh
```

(Plus IPv6 duplicates of each rule.) The previously-stale `6001/tcp` + `6002/tcp` ALLOW rules (Coolify Realtime) were removed in the cleanup sweep.

#### vps2 / vps3 UFW (verified live 2026-06-01 — installed and active)

UFW was installed + enabled by W1 of the fleet-hardening plan on 2026-05-31 evening. Package status `ii` (installed, version `0.36.2-6`), service active, 8 ALLOW rules each (4 IPv4 + 4 IPv6 mirrors), default policy `deny (incoming) / allow (outgoing) / deny (routed)`. Verified via [`probe-reports/infra-probe-2026-06-07T20-20Z.yaml`](probe-reports/infra-probe-2026-06-07T20-20Z.yaml) (W6) plus W5's rule-by-rule IPv4↔IPv6 mirror check (2026-06-01T00:43Z).

```text
22/tcp                     ALLOW   # SSH
80/tcp                     ALLOW   # HTTP
443/tcp                    ALLOW   # HTTPS
51820/udp                  ALLOW   # Wireguard mesh
```

**Pre-W1 footnote (Lesson 68):** before W1, UFW was in package status `rc` ("removed but config files remain") on both spokes — `systemctl is-active ufw` reported "active" because the init script remained, but the `ufw` binary was missing so rules were never applied. Front-line firewall was DOCKER-USER chain only. W1 reinstalled the package (`rc → ii`) and ran `ufw --force enable`, which applied the pre-existing `/etc/ufw/user.rules` content.

Plus on every host: `DOCKER-USER` iptables chain (`/etc/iptables/rules.v4`, loaded at boot via `netfilter-persistent.service`). Rules:

- `ACCEPT -i wg0` (trust everything from the mesh — handshake established trust)
- `DROP -i <public-iface> -p tcp -m multiport --dports 5432,6379,9090,9091,9100,8080,3100,7700,8000` (block mesh-only ports from public)

`DOCKER-USER` is the only firewall layer Docker honors before its own auto-rules. UFW alone cannot block Docker-exposed ports because Docker inserts DNAT rules in PREROUTING before UFW's INPUT chain runs.

---

## Traefik

Each host runs its own Traefik (`v2.11`). They do NOT share state — each terminates TLS independently for its own subdomain block:

- vps1: `*.vps1.ocoron.com` + `ocoron.com` (the WP tenant)
- vps2: `*.vps2.ocoron.com` (when tenants land)
- vps3: `*.vps3.ocoron.com` (when tenants land)

ACME (Let's Encrypt) state per host:

- vps1: `/opt/traefik/acme.json` (mode 600) — populated; many subdomains served
- vps2: `/opt/traefik/acme.json` (mode 600) **populated 2026-06-02** during W15 live-verify — first LE cert issued for `canary.vps2.ocoron.com` (`Issuer: Let's Encrypt YR2`, `notAfter: Aug 30 2026 GMT`). Even though the canary was destroyed after verification, the cert sits in acme.json until rotation.
- vps3: `/opt/traefik/acme.json` (mode 600) **still empty** — no spec has targeted vps3 yet. The W15 fix is in place so the first spoke deploy targeting vps3 will issue its cert cleanly.

### Traefik label patterns (used by scaffold-emitted compose templates)

| Service type | Middlewares | Source |
| :--- | :--- | :--- |
| Admin dashboard | `authelia-forward@docker,gzip@docker` | scaffold emits |
| API service (X-Internal-Token) | `gzip@docker` | scaffold emits |
| Public service (no auth) | (none) | scaffold emits |

**Middleware definition prerequisites (per host):**

- On **vps1**, `gzip@docker` is defined by a label on the `meilisearch` container (`traefik.http.middlewares.gzip.compress=true`). Meilisearch already has Traefik routers so `traefik.enable=true` is implicit, and the docker provider picks up the middleware definition automatically.
- On **vps2 / vps3** (as of W15, 2026-06-02), the `gzip` middleware is defined by labels on the **Traefik container itself** in `/opt/traefik/compose.yaml`. Because spoke `traefik.yml` has `providers.docker.exposedByDefault: false`, the Traefik container's own labels are normally ignored — so the fix had to add **both** labels:

  ```yaml
  services:
    traefik:
      container_name: traefik
      labels:
        - "traefik.enable=true"                                  # required to make the docker provider read this container's labels
        - "traefik.http.middlewares.gzip.compress=true"          # publishes gzip@docker
  ```

  The Traefik container does NOT get any router labels of its own, so `traefik.enable=true` has no public-routing side effects — it only unlocks label discovery. Both spokes were live-verified by re-deploying spoke-canary, which then returned HTTP 200 with a Let's Encrypt cert (first LE issuance on a spoke ever).
- **W16 shipped 2026-06-02:** spoke Traefik is now templated in `scripts/bootstrap/templates/{traefik.compose.yaml,traefik.yml,traefik-dynamic-authelia.yml}.template` and brought up by `step_12_install_spoke_traefik()` in `bootstrap-vps.sh`. The compose template carries the W15 `labels:` block (verified byte-perfect against live vps2 modulo an explainer comment). A fresh spoke gets the gzip-middleware definition on first bootstrap with no manual edit.

For services on vps2/vps3 that need Authelia, the forward-auth middleware will point at `http://10.99.0.1:9091/api/verify` (over mesh) — but this requires binding Authelia to the mesh IP first (see TODO list above). The Authelia rule registrar itself is FQDN-pattern-agnostic and handles `*.vps2 / *.vps3` patterns without code change (W13 verified 2026-06-02).

---

## Authelia

**Container:** `authelia` (stable name; no UUID suffix)
**Config:** `/opt/authelia/config/configuration.yml` (working copy) + `/var/lib/docker/volumes/.../configuration.yml` (live config Authelia reads)
**Sync:** `authelia-config-sync.service` (systemd, inotify-driven) — watches the working copy, copies to volume, restarts container on save. ~2 s reaction time.
**Sessions:** `redis-main:6379` DB index 3 — survives Authelia restarts
**TOTP:** `ocoron.com` issuer, 30 s period
**Storage:** SQLite `/config/db.sqlite3` (named volume)

### Access control rules — 8 rules live (verified against `/opt/authelia/config/configuration.yml`, post-cleanup 2026-06-02)

| # | Policy | Domain(s) | Resources (path regex) |
| :--- | :--- | :--- | :--- |
| 1 | bypass | `ocoron.com` | (all) |
| 2 | bypass | `www.ocoron.com` | (all) |
| 3 | bypass | `wp-test.vps1.ocoron.com` | (all) |
| 4 | bypass | `status.vps1.ocoron.com` | (all) |
| 5 | bypass | `*.vps1.ocoron.com` | `^/health$`, `^/healthz$`, `^/metrics$`, `^/api/health$` |
| 6 | bypass | 4 hosts: `pdf`, `browser`, `search`, `errors`.vps1.ocoron.com | (all paths — public or app-layer-protected) |
| 7 | bypass | `monitor.vps1.ocoron.com` | `^/api/` only |
| 8 | two_factor | `*.vps1.ocoron.com` | (catch-all for everything else) |

**Cleaned 2026-05-31 evening:** rule #6 went from 10 dormant hosts (incl. 5 dead microservices + `dns` stale alias) down to 4 live hosts; rule #7 dropped `coolify.vps1.ocoron.com` (Coolify removed 2026-05-30). Backup at `/opt/authelia/config/configuration.yml.bak.20260531-171950`. Authelia restarted cleanly via `authelia-config-sync.service` (~7 s).

**Cleaned 2026-06-02 evening:** removed 2 rules for `images.vps1.ocoron.com` (bypass `^/api/` + 2FA catch-all). The image-broker spec was orphaned post-Coolify (no `/opt/image-broker/`, no container, NXDOMAIN) and the spec + state + infra files were deleted; the Authelia rules that survived from a prior registration were cleaned in the same pass. Backup at `/opt/authelia/config/configuration.yml.backup.20260602-205402`. Authelia restarted via `docker restart authelia` (5s start → healthy). Rule count went 10 → 8.

**Note on `errors.vps1.ocoron.com` in rule #6:** the GlitchTip UI is reachable *without* Authelia. A prior session note claimed T2-08 Part A removed it; the change never landed and after review it stays — GlitchTip is a public error-report UI used cross-tenant. If you want it 2FA-protected later, move it out of rule #6 into the catch-all `two_factor`.

Rule precedence: Authelia is first-match-wins. Specific `^/api/` bypasses for admin-dashboard hosts MUST come BEFORE the catch-all `two_factor`. `src/fabrik/drivers/authelia.py::_compute_insert_index` enforces this automatically for future paired-pattern services.

**CRITICAL:** Authelia exits on SIGHUP — does NOT hot-reload. The `authelia-config-sync.service` handles the restart correctly. Manual reload: `ssh vps "sudo docker restart authelia"` (just the container name now — no UUID suffix).

**Cross-host pattern (not yet wired):** for `*.vps2.ocoron.com` admin dashboards, the plan is to add `auth.vps2.ocoron.com` as a CNAME → vps1 and let vps1's Authelia issue cookies scoped to `*.vps2.ocoron.com`. See `docs/development/plans/archived/2026-05-30-platform-to-a-plus.md` § W-Multi M7.

---

## M2M Authentication

| Property | Value |
| :--- | :--- |
| Header | `X-Internal-Token` |
| Env var | `SERVICE_INTERNAL_SECRET_KEY` (one shared key across all services) |
| Key location | `/opt/fabrik/.env` (WSL) — injected into each service's `.env` by the SSH deployer |
| Python import | `from app.internal_auth import require_internal_token` (when entrypoint is `uvicorn app.main:app`) |
| Python import | `from internal_auth import require_internal_token` (when entrypoint is `uvicorn api:app` from root) |
| Node.js | `src/internal_auth.js` → `requireInternalToken` via `crypto.timingSafeEqual` |
| Validation timing | Constant-time always |
| `/metrics` endpoint | Authelia-bypassed by the global `*.vps1.ocoron.com → /metrics` rule; no auth required (Prometheus scrapes anonymously) |

**Scaffold auto-emits:** `internal_auth.py` (Python), `src/internal_auth.js` (Node), `metrics.py`
**Deployed services using this:** **none currently.** The 6 microservices that previously consumed this pattern (`captcha`, `translator`, `proxy`, `emailgateway`, `file-api`, `file-worker`) are not currently deployed on vps1 — no `/opt/<svc>/` directory, no container, no Traefik router. The pattern is available the moment any new spec opts into it. (The 7th, `image-broker`, was removed 2026-06-02 — spec + state + infra + Authelia rules deleted; never re-deployed under SSH+Compose after the Coolify rip.)

---

## Observability — Centralized on vps1, agents on spokes

### Topology

```text
                        ┌──────────────────────────────────────────┐
                        │ vps1 — central observability             │
                        │                                          │
                        │  Prometheus (scrapes mesh-IP exporters)  │
                        │  Loki (10.99.0.1:3100, accepts pushes)   │
                        │  Grafana (UI for both)                   │
                        │  Alertmanager → Apprise → Telegram       │
                        └────────────────▲─────────────────────────┘
                                         │ mesh
                  ┌──────────────────────┼──────────────────────┐
                  │                                             │
       ┌──────────┴─────────────┐                  ┌────────────┴──────────┐
       │ vps2 (10.99.0.2)       │                  │ vps3 (10.99.0.3)      │
       │                        │                  │                       │
       │  node-exporter:9100    │ ─ scrapes ─▶     │  node-exporter:9100   │
       │  cadvisor:8080         │ ─ scrapes ─▶     │  cadvisor:8080        │
       │  promtail:9080         │ ◀─ pushes logs   │  promtail:9080        │
       │                        │      to vps1     │                       │
       └────────────────────────┘                  └───────────────────────┘
```

### Prometheus scrape targets (**14 live across 12 jobs** — verified `/api/v1/targets` 2026-06-07T20:20Z; was 18/15 briefly on 2026-05-31 when the 3 spoke jobs were added — those spoke jobs were dropped at some point and are not in live config today)

vps1-local (12 jobs / 12 targets):

| Job | Target |
| :--- | :--- |
| `prometheus` | self |
| `node` | `node-exporter:9100` |
| `cadvisor` | `cadvisor:8080` |
| `loki` | `loki:3100` |
| `alertmanager` | `alertmanager:9093` |
| `gatus` | `gatus:8080` |
| `grafana` | `grafana:3000` |
| `authelia` | `authelia:9959` (telemetry) |
| `meilisearch` | `meilisearch:7700` (Bearer auth) |
| `postgres` | `postgres-exporter:9187` |
| `redis` | `redis-exporter:9121` |
| `pushgateway` | `pushgateway:9091` |

Spokes — **`node-spokes`/`cadvisor-spokes`/`promtail-spokes` jobs NOT in `prometheus.yml`** (verified 2026-06-07T20:20Z). Live spoke coverage is via the `aro-wake` job (3 targets — vps1, vps2, vps3) only. The spoke-side agents (`node-exporter`, `cadvisor`, `promtail`) are running at `/opt/monitoring-agent/` on each spoke with mesh + UFW permissive, but the corresponding scrape blocks aren't currently configured. Promtail log shipping (push-based) works — Loki has `host=vps1|vps2|vps3` streams.

Historical / NOT live (preserved as a recipe to restore):

| Job | Targets | Live? |
| :--- | :--- | :--- |
| `node-spokes` | `10.99.0.2:9100`, `10.99.0.3:9100` | ❌ |
| `cadvisor-spokes` | `10.99.0.2:8080`, `10.99.0.3:8080` | ❌ |
| `promtail-spokes` | `10.99.0.2:9080`, `10.99.0.3:9080` | ❌ |

**Not scraped (intentionally or by gap):**

- `traefik` — no metrics endpoint job; routing health is observed via Gatus + Loki.
- `glitchtip-web` — `django-prometheus` not bundled by default in GlitchTip 6.x.
- `fabrik-drift` — placeholder job referenced in earlier docs; no live job by this name.
- 6 ex-microservices (`captcha`, `translator`, `proxy`, `emailgateway`, `file-api`, `file-worker`) — not deployed, so no `/metrics` to scrape. When/if redeployed, scaffold-emitted `metrics.py` re-enables. (`image-broker` was the 7th in this list; its spec was removed 2026-06-02.)

Reload: `ssh vps "sudo docker kill -s HUP prometheus"`.

### Loki

- **Config:** `/opt/monitoring/configs/loki/loki-config.yaml`
- **Retention:** `168h` (7 days) via `limits_config.retention_period`; compactor enabled
- **Mesh exposure:** added 2026-05-31 — `ports: ["10.99.0.1:3100:3100"]` in `/opt/monitoring/compose.yaml`. Internal-only on vps1 prior to that.
- **Spoke pushes:** verified working — `host` label values include `["vps2","vps3"]`

### Promtail (per host)

- **vps1:** ships `/var/lib/docker/containers/*/*log` to local `loki:3100` (Docker DNS on `fabrik` network)
- **vps2/vps3:** same path, but ships to `http://10.99.0.1:3100/loki/api/v1/push` over mesh
- **Per-host labels:** every line tagged with `host: vps1` / `vps2` / `vps3` so Grafana can filter

### Grafana

- **Datasources:** Prometheus (`http://prometheus:9090`), Loki (`http://loki:3100`) — bind-mounted from `/opt/monitoring/configs/grafana/provisioning/datasources/fabrik.yaml`
- **TODO:** dashboards don't yet have a `host` template variable for filtering spoke vs hub metrics. Cosmetic but useful.

### Alertmanager → Telegram

- Receiver: native `telegram_configs`
- Grouping: `[alertname, container]`
- Repeat: 4 h (critical: 30 m)
- Apprise webhook used for some custom routes (e.g., Backrest failure hooks would target `http://apprise:8000/notify/alerts` — but those are currently broken with the old UUID-suffix hostname — see "Known Issues" below)

### GlitchTip (error tracking)

- **Architecture:** GlitchTip 6.1.5 (`web` + `worker` containers, both 512 MB limit each)
- **Storage:** `glitchtip` database on shared `postgres-main`
- **Public URL:** `https://errors.vps1.ocoron.com` (Authelia-protected)
- **Internal DSN host:** `glitchtip-web:8000` (Docker DNS on `fabrik` network) — used by services on vps1
- **TODO** cross-host: bind `glitchtip-web` to `10.99.0.1:8000` so spoke tenants can ingest over mesh
- Full runbook: `docs/infrastructure/glitchtip-sdk-integration-setup.md`

---

## Gatus monitoring

**Config:** `/opt/monitoring/configs/gatus/` (volume-mounted at `/config`). Auto-reload within 30 s.
**Alert chain:** Gatus → custom alerter → Apprise → Telegram + others
**Alerting defaults:** `failure-threshold: 3`, `success-threshold: 2`, `send-on-resolved: true`
**Storage:** `type: memory` (no persistence; status dashboard only)
**Connectivity check:** external DNS `1.1.1.1:53` (VPS network health signal)

### Config tree

```text
/opt/monitoring/configs/gatus/
├── _base.yaml           — Global: alerting, storage, UI, connectivity
├── core/infra.yaml      — traefik, authelia, n8n, apprise
├── data/databases.yaml  — postgres-main, redis-main, meilisearch
├── observability/stack.yaml — grafana, prometheus, alertmanager, loki
├── apps/                — Per-service files
├── services/services.yaml — gotenberg, browserless, glitchtip-web
└── external/public.yaml — External HTTPS + SSL cert checks
```

**TODO:** add probes for spoke tenants. Pattern: `https://<service>.vps2.ocoron.com/health` (public) or `http://10.99.0.2:<port>/health` (mesh) — registrar `_provision_gatus()` handles this automatically when specs declare it.

---

## Backups (Backrest)

**Status (live, 2026-06-02 — post-W2 + W11 ship):** Backrest is the front-end for restic; restic writes to Backblaze B2. Verified live on vps1: `plans=4 repos=1; plan ids: ['postgres-dumps','docker-volumes','opt-configs','host-state']`. All 4 hub plans had their first snapshot 2026-06-01 (W2 ship) — combined 612 MiB uncompressed → 117 MiB on B2 (5.23× compression). Each spoke runs its own Backrest container against its own restic repo at a bucket-prefix path.

| Host | Restic repo | Plans live | First snapshot |
| :--- | :--- | :--- | :--- |
| vps1 (hub) | `b2-vps1` → `s3:https://s3.us-west-004.backblazeb2.com/vps1-ocoron-backups` | 4: `postgres-dumps`, `docker-volumes`, `opt-configs`, `host-state` | 2026-06-01 (W2) |
| vps2 (spoke) | `b2-vps2` → `s3:.../vps1-ocoron-backups/spokes/vps2/` | 2: `host-state`, `opt-configs` | 2026-06-01 (W11) |
| vps3 (spoke) | `b2-vps3` → `s3:.../vps1-ocoron-backups/spokes/vps3/` | 2: `host-state`, `opt-configs` | 2026-06-01 (W11) |

Each repo has its own restic password — **immutable post-init** (Lesson 67), so re-keying means re-init. Hub password lives in `/opt/backrest/.restic-password` on vps1 + `BACKREST_RESTIC_PASSWORD` in `/opt/fabrik/.env` (dev WSL canonical). Spoke passwords live in `/opt/backrest/.restic-password` on the spoke + mirrored to the DR-store as `vps{2,3}-restic-password-latest` (W9 extension shipped with W11).

**Bind mounts are path-preserving (`:ro`).** Plan paths mount the actual host directory at the same path inside the Backrest container (`/opt`, `/etc`, `/usr/local/bin`, `/root/.ssh`, `/home/ozgur/.ssh`, plus `/opt/backups` for pg dumps and `/var/lib/docker/volumes` for docker-volumes). A restic restore lands files at the exact path the OS expects — no path translation. Spoke plans mirror the pattern at smaller scope (no PG, no Docker volumes yet — those join when the first tenant ships under W4).

**Offsite credentials** (W9 shipped 2026-06-01, extended 2026-06-01 for W11): `/opt/fabrik/.env` and `/opt/fabrik/.env.sysadmin` plus the 4 spoke files (`vps{2,3}-backrest-env-latest`, `vps{2,3}-restic-password-latest`) mirror to private GitHub repo `mobasak/fabrik-dr-store` within seconds of every change via `fabrik-dr-watcher.service` (inotify) + daily safety-net cron + `@reboot` catch-up + weekly recovery self-test. Repo hardened: no Issues/Projects/Wiki/Discussions/Actions/collaborators. One-command recovery on a fresh WSL: `gh repo clone mobasak/fabrik-dr-store && sudo cp fabrik-dr-store/env/latest /opt/fabrik/.env`. Full runbook: [`docs/operations/credential-recovery.md`](../operations/credential-recovery.md).

**Known cosmetic issue (Issue 1 below):** plan failure hooks in `/opt/backrest/config/config.json` still reference the Coolify-era UUID-suffix container name `apprise-lcocgs4gs8ksg4g08w40ows8` instead of the stable `apprise`. **Effect:** if a plan fails, the Telegram failure alert never reaches the operator. The 4 hub plans have been running 24 h without failure as of 2026-06-02 — low-risk; fix on next config edit.

Spoke tenant backups (`docker-volumes-vpsN`, `postgres-dumps-vpsN`) defer to W4 — zero tenants on spokes yet.

DR runbooks: [`vps-hub-rebuild.md`](vps-hub-rebuild.md) (hub, ≤ 90 min undrilled) · [`vps-spoke-rebuild.md`](vps-spoke-rebuild.md) (spoke, ≤ 30 min undrilled) · [`docs/operations/disaster-recovery.md`](../operations/disaster-recovery.md) (cross-cutting).

---

## Microservices status — none currently deployed

Seven application microservices were running pre-Coolify-removal. As of 2026-05-31 afternoon, **none are deployed on vps1**: no `/opt/<svc>/` directory, no container, no Traefik router. Their fabrik specs still exist in `specs/services/` and can be redeployed via `fabrik apply` once the deploy pipeline reaches feature parity (see [§ Pending actions](#pending-actions-current-todo-list) items 2a and 11).

| Service | Spec | DNS still exists? | Traefik router? | Container? | GlitchTip project still in DB? |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `captcha` | yes | no | no | no | yes (id=65) |
| `image-broker` | **removed 2026-06-02** | no (was stale) | no | no | id=66 (orphaned; can be deleted in GlitchTip UI) |
| `translator` | yes | no | no | no | yes (id=67) |
| `proxy` (fabrik-proxy) | yes | no | no | no | — |
| `emailgateway` | yes | no | no | no | yes (id=68) |
| `file-api` | yes | no | no | no | yes (id=69) |
| `file-worker` | yes | no | no | no | yes (id=70) |
| `site-provisioner` | yes | `provision.vps1` ✓ | ✓ | ✓ (interim) | yes (id=24) |

Implication for current ops: most of the "service URL", "M2M auth", "metrics" content in older docs describes a Coolify-era fleet that doesn't currently exist. The platform infrastructure (postgres-main, redis-main, traefik, authelia, monitoring stack, etc.) is fully live and ready to host these or new services.

---

## Resource limits (vps1, verified live via `docker inspect`)

| Container | Memory limit |
| :--- | :--- |
| `postgres-main` | 2g |
| `n8n` | 2g |
| `browserless` | 2g |
| `prometheus` | 1.5g |
| `apprise` | 768m |
| `site-provisioner` | 512m (interim) |
| `meilisearch` | 512m |
| `gotenberg` | 512m |
| `glitchtip-worker` | 512m |
| `glitchtip-web` | 512m |
| `backrest` | 512m |
| `authelia` | 512m |
| `gatus` | 256m |
| `pushgateway` | 64m |

Containers without a memory limit (unbounded, by design or oversight): `alertmanager`, `cadvisor`, `grafana`, `loki`, `node-exporter`, `postgres-exporter`, `promtail`, `redis-exporter`, `redis-main`, `traefik`, all 5 WP tenant containers. Limits are reapplied on reboot via `scripts/vps_apply_limits.sh`.

vps2/vps3 limits per monitoring agent (set by `monitoring-agent.compose.yaml.template`):

| Container | Memory limit | CPU limit |
| :--- | :--- | :--- |
| `node-exporter` | 64m | 0.25 |
| `cadvisor` | 256m | 0.5 |
| `promtail` | 96m | 0.25 |

---

## Operational lessons — currently active

| # | Incident | Rule |
| :--- | :--- | :--- |
| 1 | `localhost` in `DATABASE_URL` crashed translator | Always `postgres-main:5432`, `redis-main:6379` on the local Docker network; or `10.99.0.1:5432` over mesh once we bind it |
| 2 | SIGHUP to Authelia → exits → all routes 404 | `docker restart authelia` after config changes; `authelia-config-sync.service` does this automatically on file save |
| 3 | cadvisor OOM at 256m (91% RSS) | 512m + `--docker_only=true --disable_metrics=...` |
| 4 | prometheus OOM at 512m (93% RSS, 40 containers) | 1g minimum |
| 5 | apprise OOM-prone at 256m AND 13 gunicorn workers (default = 2×CPU+1) | 768m limit + `APPRISE_WORKER_COUNT=2` env var (reduced 619 MB → 127 MB on 2026-05-30) |
| 6 | `yaml.dump` corrupted Authelia regex patterns | Use targeted string replacements, never full YAML roundtrip |
| 7 | `fabrik redeploy` without git push deploys stale code | `git commit → git push → fabrik redeploy` always |
| 8 | Per-service X-API-Key chaos | One key: `SERVICE_INTERNAL_SECRET_KEY`; one header: `X-Internal-Token` |
| 9 | `import path must match uvicorn module path` | `uvicorn app.main:app` ↔ `from app.internal_auth import` |
| 10 | bootstrap-vps.sh shipped 3 bugs in one session (Lesson 65) | Create sudoer FIRST, scan multiple SSH key candidates, no process substitution over SSH |
| 11 | Alert spam during planned downtime | Silence the `ContainerDown` rule before any op that takes containers down >2 min (Telegram floods otherwise) |
| 12 | "Security theater" pattern on single-operator dev VPS | Don't propose perm changes / credential rotations without naming a realistic attacker |
| 13 | Watchdog sidecar's docker probes silently returned empty due to docker.sock GID mismatch (T-P5 dogfood) | Driver injects `group_add: [<host docker.sock gid>]` into the compose overlay at apply time (auto-detected via `stat -c %g`). Pairs with `DOCKER_API_VERSION` env to handle CLI/daemon API skew. |
| 14 | Claude Code `-p` mode + `--effort <level>` exits 0 with EMPTY stdout AND stderr (silent death) in 2.1.144 | Don't pass `--effort` to non-interactive Claude. Use default effort + `--model opus` for Opus-class diagnosis. Re-evaluate when Anthropic ships `-p`+`--effort` compatibility. |
| 15 | Per-call `--max-budget-usd` on sysadmin LLM calls breaks the diagnose loop (session-init cache cost alone exceeds any sane cap) | No per-call $ caps on watchdog / sysadmin agents. Subscription is the budget. Daily-cap + invocations-cap via the WAL kill-switch remain as soft circuit-breakers. Operator directive 2026-06-03. |
| 16 | Bind-mounted `~/.claude/.credentials.json` (RO) goes stale every ~4 days; sidecar can't write back the refreshed token → 401 → fallback to OpenRouter / rule-only mode | On a stale-token symptom, run `claude -p hi` ONCE on the host (refreshes the file in place; RO mount picks up the new contents on next read). Permanent fix would be a credentials-refresh sidecar or RW-mount of just `.credentials.json`. |
| 17 | OpenRouter routes Anthropic models through Amazon Bedrock by default, and Bedrock-served Claude IGNORES `response_format: json_schema` — returns plain text | Don't depend on `response_format` for Anthropic-via-OpenRouter. Instruct JSON via the system prompt + parse defensively (plain → ```json fenced → greedy `{...}` regex). Same pattern as Claude Code CLI 2.1.144 with `--json-schema`. |

---

## Pending actions (current TODO list)

| # | Action | Priority | Blocking | Status |
| :--- | :--- | :--- | :--- | :--- |
| 1 | Refresh `CLOUDFLARE_API_TOKEN` in `/opt/fabrik/.env` | High | DNS provisioning + site-provisioner deploy | ✓ done 2026-05-31 afternoon (synced from local site-provisioner `.env`; verified active) |
| 2 | Stand up `site-provisioner` on vps1 so spoke DNS work could proceed | High | Was blocked on #1 | ⚠ partial — interim manual stand-up running healthy; `fabrik apply` pipeline NOT yet ready (see "site-provisioner status" earlier) |
| 2a | Push `compose.yaml` network rename to `mobasak/site-provisioner@main` (coolify → fabrik) | High | Re-deployability via `fabrik apply` | ✓ done 2026-05-31 evening — committed in `fa32d61` (bundled with docs commit by coder AI) and pushed to `origin/main`. Verified `git diff origin/main..HEAD -- compose.yaml` is empty. |
| 3 | Bind `postgres-main` to `10.99.0.1:5432` for spoke access | High | Unblocks spoke tenant DB use | ✓ done 2026-05-31 (commit `f853a50`) |
| 4 | Bind `redis-main` to `10.99.0.1:6379` for spoke access | High | Unblocks spoke tenant cache use | ✓ done 2026-05-31 |
| 5 | Bind `glitchtip-web` to `10.99.0.1:8000` for spoke ingestion | Medium | Future spoke tenants | ✓ done 2026-05-31 |
| 6 | Bind `authelia` to `10.99.0.1:9091` for cross-host forward-auth | Medium | First spoke admin dashboard | ✓ done 2026-05-31 |
| 7 | Deploy `traefik` on vps2 and vps3 (public TLS termination) | Medium | First spoke tenant | ✓ done 2026-05-31 (`authelia-vps1@file` middleware ready) |
| 8 | Add `host` template variable to all Grafana dashboards | Low | Cosmetic | ✓ done 2026-05-31 (5/5 dashboards, regex `/^vps/`) |
| 9 | Reconfigure Backrest plans (postgres-dumps, docker-volumes, opt-configs) with correct `apprise:8000` hook URL | Low | When data lands worth backing up | **CLOSED 2026-06-01** — DR-in-hours track shipped 4 plans (added `host-state`); first snapshot per plan committed 2026-06-01 to B2 repo `a256277c45` (1 snapshot per plan from first run; more accumulate via daily cron). Hook URL still references the Coolify-era UUID-suffix `apprise-lcoc...` — deferred to next config edit (see Issue 1). See [`vps-hub-rebuild.md`](vps-hub-rebuild.md). |
| 10 | AI sysadmin scripts query spoke metrics too (currently vps1-only) | Low | Future | ✓ done 2026-05-31 (`prom_hosts()` + spoke alert rules) |
| 11 | Fabrik spec gains `target_vps` field + `fabrik apply --target-vps` flag (W-Multi M4) | Low | Big code change | ✓ done 2026-05-31 evening — see § Permanent fixes shipped today; spec field + CLI flag + DNS routing + deployer env-swap + 3 new tests + 4 pre-existing-test fixes; 103/103 deployer/spec tests pass. Symmetric `--target-vps` for destroy + redeploy shipped 2026-06-02 (W3). Env-swap extended to `inject_env` + compose rollback 2026-06-02 (W14). |
| 12 | Clean stale UFW rules on vps1 (6001, 6002 Coolify Realtime) | Trivial | — | ✓ done 2026-05-31 evening (UFW rules 6001 + 6002 removed; 8000 DENY rule kept as belt-and-suspenders even with stale Coolify comment) |
| 13 | Authelia access-control rules for `*.vps2.ocoron.com` / `*.vps3.ocoron.com` admin dashboards | Medium | Needs first such dashboard | **OPEN** (no longer blocked on DNS — DNS landed today) |
| 14 | Backrest spoke backups (`docker-volumes-vps2`, `opt-configs-vps2`, etc.) | Low | Per #9 — defer until backups re-enabled | **OPEN** |
| 15 | Spoke DNS records — `vps2.ocoron.com` + `*.vps2.ocoron.com` → 96.9.214.128; `vps3` → 104.128.190.151 | High | Spoke tenant TLS issuance | ✓ done 2026-05-31 afternoon (4 A records via CF API) |
| 16 | Deployer auto-trusts the git host before clone (`ssh-keyscan` pre-step) | Medium | Reliable first-time git-source `fabrik apply` | ✓ done 2026-05-31 afternoon (`_extract_git_host()` + ssh-keyscan in `_deploy_git`) |
| 17 | Bootstrap step 03 pre-seeds `github.com` in `/root/.ssh/known_hosts` | Medium | New-spoke readiness for git-source deploys | ✓ done 2026-05-31 afternoon |
| 18 | `site-provisioner` spec declares all 21 `${VAR}` references its upstream `compose.yaml` interpolates | High | `fabrik apply site-provisioner` actually parses | ✓ done 2026-05-31 afternoon (5 env literals incl. `DATABASE_URL` placeholder + 3 new from-env secrets) |
| 19 | `/opt/fabrik/.env` carries the secrets the site-provisioner spec now expects (`API_KEY` synced from vps1 live value; `BING_WEBMASTER_API_KEY` added) | High | Same as #18 | ✓ done 2026-05-31 afternoon (backup at `backups/.env.backup.20260531-163701`) |
| 20 | Dry-run validate `fabrik apply specs/services/site-provisioner.yaml` end-to-end (proves all 4 fixes wire together cleanly) | Medium | Trust in the pipeline for the first post-Coolify spec | ✓ done 2026-05-31 evening — clean dry-run; state file shows `postgres`, `gatus`, `glitchtip` registrars as `status: "dry_run"`; container untouched; shape-gated registrars (backrest, authelia, meilisearch, redis, prometheus) correctly skipped |
| 21 | Create `provision.vps1.ocoron.com` DNS record (discovered missing during residue sweep) | Medium | External reach to site-provisioner | ✓ done 2026-05-31 evening |
| 22 | `fabrik destroy --target-vps` + `fabrik redeploy --target-vps` (same env-swap pattern as W-Multi M4) | Low | Symmetric ops for spoke services | ✓ done 2026-06-02 (W3) — CLI flag on both commands; resolution order CLI > state-file > spec > vps1; live-verified destroy on vps2 |
| 23 | First real spoke deploy (e.g. tiny test spec with `target_vps: vps2`, domain `<svc>.vps2.ocoron.com`) | Medium | Exercises spoke Traefik's Let's Encrypt issuance for the first time | ✓ done 2026-06-02 — `spoke-canary` (nginx:alpine) deployed clean on vps2, `curl https://canary.vps2.ocoron.com` returned HTTP 200, LE cert issued (`Let's Encrypt YR2`, expires Aug 30 2026). Container destroyed cleanly afterwards. |
| 24 | Spoke Traefik defines the `gzip` middleware so `traefik.http.routers.<svc>.middlewares=gzip@docker` resolves | Medium | First end-to-end spoke deploy | ✓ done 2026-06-02 (W15) — added `traefik.enable=true` + `traefik.http.middlewares.gzip.compress=true` labels to the Traefik container in `/opt/traefik/compose.yaml` on both spokes. Verified live via item 23. Future-spoke template work tracked separately as item 27 below. |
| 25 | `SSHDeployer.inject_env()` env-swaps to `ctx.target_vps` | Low | Glitchtip DSN / Redis URL injection on spoke apps | ✓ done 2026-06-02 (W14) |
| 26 | Compose rollback honors `target_vps` from the resource record | Low | Failed spoke deploy cleans up on the spoke, not the hub | ✓ done 2026-06-02 (W14) |
| 27 | Bake spoke Traefik compose (with the W15 `labels:` block) into `bootstrap-vps.sh` so future spokes get the `gzip` middleware on first bootstrap | Medium | Fresh-spoke automation | ✓ done 2026-06-02 (W16) — `step_12_install_spoke_traefik()` + 3 templates; rendered output diffed byte-perfect against live vps2; idempotency proven by re-running step 12 against vps2 with no recreate. |

**Net after the full day's work (morning + afternoon + evening):** 11 items closed 2026-05-31; 2026-06-02 closed items 22 (W3), 23 + 24 (W14 + W15 together), 25 + 26 (W14), 27 (W16 Traefik), and the DNS step in `bootstrap-vps.sh` (now step 13) shipped end-to-end via site-provisioner under the W16 second pass (idempotent `ensure_record()` calls, live-verified on vps2 + vps3). Open: item 13 (Authelia spoke rules — registrar verified pattern-agnostic by W13 but no live dashboard exists yet); items 9/14 (spoke tenant backups, gated on actual tenant data).

---

## Known issues (current)

### Issue 1: Backrest failure-notification webhook is broken

`/opt/backrest/config/config.json` plan hooks reference `http://apprise-lcocgs4gs8ksg4g08w40ows8:8000/notify/alerts` — the old Coolify-era UUID-suffix container name. After the 2026-05-30 container-name standardization, the stable name is `apprise`. **Effect:** if any of the 4 live hub plans (or 2 per-spoke plans) fails, the failure alert never reaches Telegram via the hook path. The 24 h since W2/W11 ship had zero failures, but the gap is real. Fix on next config edit: replace `apprise-lcocgs4gs8ksg4g08w40ows8` with `apprise` (one place per spoke + one place on hub).

### Issue 2: `errors.vps1.ocoron.com` predates T2-08 Part A in `audit_authelia_gates.py`

The Authelia gating audit cron flags the `errors.vps1` middleware as "unexpected" every Monday 06:00. Cosmetic (exit 0; log shows `1 GAP`); update the inventory in `scripts/audit_authelia_gates.py` when convenient.

### Issue 3: `/opt/prometheus/compose.yaml` is a stale leftover

Pre-fabrik-network-rename. Real Prometheus runs from `/opt/monitoring/compose.yaml`. Delete `/opt/prometheus/` to avoid confusion.

### Issue 4: Cloudflare API token in `/opt/fabrik/.env` was invalid — RESOLVED 2026-05-31 afternoon

Was returning `Invalid access token` after the session 2026-05-31 morning cleanup. Resolved by syncing the working token from the local site-provisioner instance's `.env` (`/opt/site-provisioner/.env` on the dev WSL) — that token had stayed in sync with Cloudflare. Pre-edit backup at `backups/.env.backup.20260531-155948`. Verified active via `https://api.cloudflare.com/client/v4/user/tokens/verify`.

### Issue 5: site-provisioner upstream `compose.yaml` `coolify` → `fabrik` rename — RESOLVED

`mobasak/site-provisioner@main` originally declared `networks: [coolify]`. Resolved by commit `fa32d61` (rename to `fabrik`), pushed 2026-05-31 evening. Verified live on vps1 2026-06-02: `/opt/site-provisioner/compose.yaml` declares `networks: [fabrik]`, no `coolify` references. A `fabrik redeploy` would now `git pull` a `fabrik`-network compose cleanly. The remaining gate before declaring the pipeline production-grade is one clean end-to-end `fabrik apply` round-trip — see § site-provisioner status.

---

## Signal → AI wake-up matrix (verified live 2026-06-04)

This table answers "when X breaks, what wakes up an AI to look at it?" — and lists what currently does NOT trigger AI. Verified against live state on all three hosts.

### Signal sources (things that detect problems)

| Source | What it observes | Where the signal lands | Wakes an AI? |
| :--- | :--- | :--- | :--- |
| `prometheus` (vps1) | 14 active targets across 12 jobs (verified 2026-06-07T20:20Z): node-exporter, cAdvisor, postgres-exporter, redis-exporter, pushgateway, gatus, blackbox, fabrik-registrar, glitchtip-web, plus `aro-wake` job with 3 targets (vps1+vps2+vps3 over mesh). Spoke metrics: covered via the `aro-wake` job only — dedicated `node-spokes`/`cadvisor-spokes`/`promtail-spokes` jobs were referenced in older docs but are NOT present in live `prometheus.yml`. | `alertmanager` → Telegram **AND** queried by `proactive-check.sh` cron | ✅ via `proactive-check.sh` (every 15 min, rate-limited 5 Claude wakes/h) |
| `alertmanager` (vps1) | Prometheus rule alerts from 5 live groups: `aro_wake` (2), `container_health` (6), `host_health` (3 — fires on host=vps1\|vps2\|vps3 labels), `service_health` (1), `fabrik-registrar-drift` (1, separate `rules/fabrik-drift.yml`). No `spoke_health` group exists (was planned, never landed). | Native `telegram_configs` → Telegram | ❌ (operator-in-loop by design; ARO-Brain receiver stub in config but not built) |
| `loki` (vps1) | logs from promtail on all 3 hosts (`host` label vps1/vps2/vps3) | Grafana dashboards; **no ruler / log-alert wiring** | ❌ |
| `gatus` (vps1) | 21 synthetic endpoints across 16 config files (apps/core/data/observability/external) | Custom alerter → Apprise → Telegram | ❌ |
| `glitchtip-web` + `glitchtip-worker` (vps1) | Sentry-compat exception ingest from instrumented apps; 7 retained projects | DSN → web UI; per-project alerts → Apprise → Telegram | ❌ |
| `backrest` (each host) | backup plan run results | container logs only; failure hook in `config.json` is **currently broken** — points at stale Coolify-UUID Apprise hostname (Known Issue 1) | ❌ |
| `traefik` (each host) | HTTP traffic, 5xx ratios | scraped by Prometheus (when enabled) → Alertmanager → Telegram | indirectly via Prometheus path |
| **emitter library** (per-project) | application code calls `from watchdog_emitter import emit(name, severity, details)` to push structured events to its sidecar's `state.db emitter_inbox` | sidecar drains inbox each tick → `_handle_incident()` → Claude diagnose | ✅ when project has a watchdog sidecar (today: only `watchdog-test`) |
| **per-project sidecar** rule pass (T-P5 dogfood) | per-project: 60s `docker inspect` + `docker logs --tail 200 --since 120s` against the main container; container-state pass (`status != running`, RestartCount delta) + log-trigger pass (`oom_kill`, `panic`, `traceback`, `http_5xx_spike` regex) | Claude Code Opus diagnose subprocess → Tier A action (`actions.execute`) → state.db + cost_ledger | ✅ for projects with `watchdog.enabled: true` |

### AI wake mechanisms (the actual triggers, verified live)

| # | Mechanism | Implemented as | Cadence | Scope today |
| :--- | :--- | :--- | :--- | :--- |
| 1 | **Host-level AI sysadmin — Telegram-driven Q&A** | `vps-sysadmin-bot.service` (systemd on vps1, NOT a container) — `bot.py` polls `getUpdates` ~10s, spawns `claude -p ... --model opus --permission-mode bypassPermissions --session-id ... --system-prompt ...`. Pattern doc: [`scripts/sysadmin/bot.py`](../../scripts/sysadmin/bot.py). | On operator message | **vps1 only**. Can act with `sudo docker` directly. The watchdog sidecar's `llm_client.py` (T-P5, 2026-06-04) now mirrors this exact pattern. |
| 2 | **Host-level AI sysadmin — proactive cron** | `/etc/cron.d/vps-sysadmin` → `proactive-check.sh` (every 15 min) — pure-bash PromQL threshold pre-checks; on anomaly, wakes Claude with bypassPermissions + Apprise → Telegram report. Spoke-aware: queries `up{host="vps2"}`, `up{host="vps3"}`, etc. Rate limit: 5 Claude wakes / hour (`/tmp/sysadmin-proactive-rate`). | Every 15 min | **vps1 only**. Reads Prometheus metrics for all 3 hosts; **acts via local `sudo docker` so cannot fix vps2/vps3 directly** — there's no SSH-out path from this cron. |
| 3 | **Host-level AI sysadmin — scheduled routines** | Same cron file: `morning-report.sh` (08:00 daily), `weekly-security.sh` (Mon 08:30), `weekly-maintenance.sh` (Sun 03:00), `monthly-backup-verify.sh` (1st of month 04:00). | per their schedules | **vps1 only**. Each can wake Claude; Telegram report-back. |
| 4 | **Per-project watchdog sidecar — poll loop** | `<project>-watchdog` container running `agent.py` on a 60s loop; rule-based `detect_anomalies()` (container-state + log triggers) → Claude Code Opus diagnose → Tier A action (`restart_container` / `clear_redis_cache` / `rotate_logs`) | Every 60s | **One project (`watchdog-test`) on vps1.** Default `watchdog.enabled: True` in `WatchdogConfig` means every future spec gets a sidecar unless opted out. Per-project `state.db` isolates blast radius. |
| 5 | **Per-project watchdog sidecar — emitter inbox** | Project code calls `emit(name, severity, details)` → SQLite write to its sidecar's `state.db.emitter_inbox` → sidecar drains each tick → same diagnose path as rule fires | Bounded by sidecar tick (60s) | Same scope as mech #4 — projects with sidecar opted in. |
| 6 | **Per-project watchdog sidecar — deadman bleed-stop** | `DeadmanTimer` — if Tier C escalation stays unacknowledged for `deadman_timeout_seconds` (default 120s, watchdog-test 120s), sidecar fires `docker restart <main>` + re-alerts with `[DEADMAN-TIMEOUT]` prefix | One-shot per unack incident, after timeout | Same scope as mech #4. Safety net when LLM diagnose is unavailable (e.g. stale OAuth token, OpenRouter credit exhaustion). |
| 7 | **aro-wake push-trigger endpoint (trio Phase 3 — LIVE on FULL FLEET since 2026-06-06)** | systemd-managed FastAPI on each host. Three HTTP endpoints: `POST /wake`, `GET /health`, `GET /metrics` (Prometheus exposition, added 2026-06-06). `/wake` accepts: `source=consult` (peer asks "what do you see?", LIVE — real cross-host vps2→vps1 + vps3→vps1 verified 2026-06-06), `source=alertmanager` (Alertmanager webhook, LIVE on vps1 with async 202-response pattern), `source=manual` (operator curl, LIVE). Spawns Claude with this host's veteran-sysadmin prompt; returns the result. **4 in-memory loop-prevention guards (added 2026-06-06):** (1) trace-id dedup 5-min LRU drops same-trace replays via `_dedup_trace()`; (2) hop cap drops `len(seen_by) > _HOP_LIMIT` (default = `len(PEER_HOSTS)+1` = 3); (3) forward-target intersection (PRIMARY) — `_try_forward` refuses to send to a host already in `payload.seen_by`, and the alertmanager handler's cycle pre-check at `main.py:788` ALSO emits `M_FWD_SUPPR{reason="seen_by"}` for the optimized fall-through path; (4) per-target storm breaker trips at 8 forwards / 10 min, first trip logs ERROR "operator should investigate runaway origin", subsequent trips inside window are deduped. **Binds `0.0.0.0:8201`** (changed 2026-06-05 batch-6 from mesh-only — Alertmanager's docker container can't reach the host's wg0 IP from its network namespace). UFW + iptables enforce access: explicit allow `from 10.0.0.0/8` (docker bridge for Alertmanager + other containers) + `from 10.99.0.0/24` (wg0 peer consults) + default-deny incoming for public. Reachability matrix verified live: container on `fabrik` net ✓, host loopback ✓, peer over wg0 ✓, public timeout ✓. Thread-safe rate limiter (20/h per `(source, topic)`) + per-(source,topic) Claude session reuse (effective `session_id` from envelope). Defensive envelope parse handles dict + event-list Claude shapes. Pending-queue at `/var/lib/aro-wake/pending.jsonl` (24h TTL, 1000-entry cap) for failed cross-host forwards. `ARO_WAKE_PEER_HOSTS` uses CSV format (NOT JSON — systemd strips embedded quotes; verified via round-trip batch-3). **Async response pattern (alertmanager only):** returns 202 Accepted in ~36ms, processes Claude in background `asyncio.Task` (held in module-level `_bg_tasks` set so event loop doesn't GC mid-execution) — avoids Alertmanager's webhook timeout retry storm. consult + manual paths stay synchronous. **Response shapes:** consult → `{ok, from_host, trace_id, seen_by, view, correlation, no_action: true}` (peer-protocol.md §2.1); alertmanager → `{ok, accepted: true, from_host, trace_id, scope: "local"\|"forwarded_to": <peer>}`; manual → `{ok, from_host, trace_id, seen_by, result, no_action: false}`. `[<host>]` Telegram-prefix stripped from consult `view` so peer consumers see clean text. | On push: consult / alertmanager webhook / manual curl | **LIVE on vps1 since 2026-06-05.** Verified end-to-end: (1) synthetic vps3→vps1 consult → Claude queried Prometheus + Alertmanager + wg0 handshakes, returned correct peer-protocol §2.1 shape, honored `no_action: true`; (2) synthetic `Phase4WiringTest` via `amtool` + REAL `ContainerHighMemory` alert both caught and processed within seconds (Phase 4 wire). ~32MB RAM idle, 0% CPU when not waking. Total subscription burn 2026-06-05: ~$0.65 across 6 wakes (cold-cache first session ~$0.39, subsequent warm $0.005-0.03). **LIVE on vps2 + vps3 since 2026-06-06** after operator delivered @BotFather tokens + `claude auth login`. Real cross-host consults from each spoke to vps1 returned rich diagnostic responses (mesh handshake age, Prometheus `up`, Loki ingest, RTT). Spoke↔spoke wg0 routing also LIVE (single `ufw route allow in on wg0 out on wg0` on vps1 — vps2↔vps3 reach via hub-hop, 266ms). **Prometheus SLI metrics LIVE on full fleet 2026-06-06**: 8 metrics at `/metrics`, scraped by job `aro-wake` in `prometheus.yml` (vps1 via docker-bridge `10.0.1.1:8201` @ 1.4ms; vps2/vps3 via wg0 `10.99.0.{2,3}:8201` @ ~270ms; cross-mesh NAT verified via tcpdump — docker MASQUERADE rewrites Prometheus container's source to vps1's wg0 IP `10.99.0.1`, which spokes' UFW already permits). Two alert rules in `aro_wake` group: `AroWakeLowSuccessRate` + `AroWakeCostBurnHigh`, both per-host via `by (host)`. **Known limitation**: Claude-only fallback chain — no OpenRouter (watchdog sidecar's chain at `fabrik-lib/watchdog/sidecar/llm_client.py` is not shared with aro-wake). If Claude primary returns non-zero: consult returns 503 (caller's 5s timeout falls through to "peer unreachable" annotated report); alertmanager async skips logging (Alertmanager's `continue: true` route preserves telegram fallback). Phase 5 deferred. |
| 8 | **Per-host AI sysadmin (trio Phase 2 — LIVE on FULL FLEET since 2026-06-06)** | Same `vps-sysadmin-bot.service` + `/etc/cron.d/vps-sysadmin` pack vps1 has, now deployed and ACTIVE on vps2 + vps3. Hash-stable cron-minute slots per host (sha1sum of HOST_NAME mod 30 + mod 60) so digest + keepalive don't fire concurrently across the fleet. Each host's bot reads `/opt/fabrik/.env.sysadmin` for its own Telegram bot token (three @BotFather bots: vps1=existing `@ocoron_bot`, vps2=`SysAdminVPS2`, vps3=`SysAdminVPS3`). System prompt rendered with `{{ HOST_NAME }}`, `{{ HOST_IP }}`, `{{ PEER_HOSTS }}` for THAT host; bots prefix every Telegram reply with `[vpsN]`. **Spoke deps now baked into `bootstrap-vps.sh` as of 2026-06-07** (step_02 apt: `python3-venv` + `python3-pip`; step_14a: Node.js 22 + Claude Code CLI via npm; step_14b: `python-telegram-bot==22.7` via pip; step_14 mkdir: `/opt/fabrik` ownership reset to `ozgur:ozgur`). All 4 deps validated end-to-end via DR drill #2 on Vultr 2026-06-07 (3m 13s wall-clock, 15/15 substantive checks). | Telegram-driven Q&A + hash-staggered cron | **LIVE on FULL FLEET since 2026-06-06.** Operator delivered prerequisites; deploy ran inline (step_14 + step_15 logic) — now all baked into `bootstrap-vps.sh` for future spoke installs. |
| 9 | **Operator-reversal detection cron (trio Phase 5.1.a — LIVE on FULL FLEET since 2026-06-07)** | `/opt/fabrik/scripts/sysadmin/detect_reversals.py` runs as `*/5 min` cron on every host. Correlates AI actions (watchdog sidecar `state.db` actions + `/opt/fabrik/logs/sysadmin-actions.jsonl`) against subsequent operator-issued `sudo docker (restart\|stop\|kill\|rm\|up)` commands within a 5-minute window. Matches → `/opt/fabrik/logs/lessons-pending.jsonl` for weekly review. Idempotency by `(ai_source, ai_ts, operator_ts)` tuple; defensive design (cron-grade) — 10–15s subprocess timeouts, parse errors skip rows, never crashes the cron job. Reversal classes detected today: `restart_container`. Scaffolded for `clear_redis_cache` + `rotate_logs` once sidecar gains those verbs. | Cron `*/5 min` reads journald `_COMM=sudo` + state.db | **LIVE on FULL FLEET since 2026-06-07.** End-to-end test verified live on vps1: `docker kill watchdog-test` → 90s wait → sidecar autonomous `restart_container` lands in state.db → `sudo docker restart watchdog-test` simulates operator reversal → detector wrote 1 entry to lessons-pending.jsonl with class=restart_container, delta_seconds=41.6. Re-running 2× → 0 new entries (idempotency confirmed). |

### What is NOT yet wired to wake an AI (the gaps — updated 2026-06-04 evening)

Several rows from the previous version of this table moved from "GAP" to "code shipped, operator-gated for live deploy" — see the matrix rows #7 + #8 above. The remaining true gaps:

| Gap | Impact | Smallest path to close |
| :--- | :--- | :--- |
| Alertmanager → aro-wake (trio Phase 4) | ALL Prometheus rule alerts still go to Telegram. aro-wake's `source=alertmanager` handler exists in main.py as a placeholder but the Alertmanager webhook receiver isn't wired yet (trio plan Phase 4 — separate ship). | Add one `webhook_configs` block in `alertmanager.yml` pointing at `http://aro-wake-router:8201/wake?source=alertmanager`; `continue: true` on the route so existing telegram fallback stays. One config change + Alertmanager restart. |
| Apprise → aro-wake (trio Phase 5 deferred) | Gatus, GlitchTip, per-service push notifications still go straight to Telegram. AI never sees them. | Apprise pre-route via aro-wake. Deferred to Phase 5 — add when first incident proves Alertmanager-only triage misses something. |
| Loki ruler not configured (trio Phase 5 deferred) | Log-pattern alerts not generated at all. Sidecars catch their own container's logs; cross-container log signals on vps1 aren't observed. | Configure Loki ruler with a small set of starting rules → Alertmanager → aro-wake (post-Phase-4) → AI. Deferred until incidents teach which rules matter. |
| Per-project watchdog on vps2 + vps3 apps | Watchdog driver supports `target_vps`; capability untested on a real spoke tenant since none exist yet with `watchdog.enabled: true`. | When the first spoke tenant deploys with watchdog enabled, dogfood it the same way T-P5 dogfooded `watchdog-test` on vps1. |
| Backrest failure → AI | Webhook URL stale (Known Issue 1). **Live-state probe 2026-06-04 evening: vps1/vps2/vps3 Backrest configs contain ZERO `apprise*` references today** — Known Issue 1 is already resolved in live state (either Backrest config was regenerated cleanly at some point, or plan hooks were never live-configured). `step_14_install_sysadmin_pack` retains the defensive sed as a no-op safety net: future Backrest reconfiguration that re-introduces the cruft would be auto-fixed on next bootstrap. | When plan hooks are configured in the future, point them at aro-wake instead of telegram. Phase 5 deferred. |
| `propose` / `ack` peer-protocol verbs | Cross-host destructive actions bridge via operator Telegram `reply "go"` (trio plan §1.6). | Build out propose/ack endpoints in aro-wake when first incident proves consult-only is insufficient. Trio Phase 5. |
| Cross-container correlation | Each watchdog sidecar sees one container; host sysadmin sees Prometheus. Neither sees "service A 5xx burst correlates with service B restart 10s prior." | Future host-level correlator over Loki + Prometheus + sidecar streams. Out of scope. |
| Kernel panic / Docker daemon death | Both AI layers require Docker. If daemon dies, sidecars die; host sysadmin systemd survives but can't `sudo docker`. | Out of scope. Needs out-of-band path (IPMI, neighboring-host failover). |

### One-line summary (updated 2026-06-04 evening)

> **Today (LIVE on FULL FLEET, 2026-06-07): AI auto-action covers (a) ALL Prometheus signals across vps1+vps2+vps3 via the 15-min `proactive-check.sh` cron on EACH host (each acts locally on its own host's authority); (b) one project's container-state + log triggers on vps1 via the per-project watchdog sidecar with canonical 354-line veteran-sysadmin prompt (trio Phase 1.3); (c) aro-wake push-trigger endpoint on EVERY host at `10.0.1.1:8201` (vps1 docker-bridge) / `10.99.0.{1,2,3}:8201` (mesh) accepts peer `consult` (LIVE — real cross-host vps2→vps1 + vps3→vps1 verified) + Alertmanager webhooks (LIVE on vps1) + manual ops; (d) Alertmanager wired on vps1: every firing alert with severity=critical|warning routes to aro-wake-routed receiver FIRST with `continue: true` preserving telegram fallback; (e) per-host AI sysadmin pack LIVE on vps2 + vps3 (`SysAdminVPS2` + `SysAdminVPS3` bots polling Telegram) — spoke deps now baked into `bootstrap-vps.sh` 2026-06-07; (f) spoke↔spoke wg0 routing LIVE via single `ufw route allow in on wg0 out on wg0` on vps1 — direct vps2↔vps3 reach at 266ms via hub-hop; (g) 4 in-memory loop-prevention guards in aro-wake; (h) Prometheus SLI metrics LIVE on all 3 hosts via job `aro-wake` with 2 alert rules per-host — `aro_wake_requests_total` now has 3 status values incl. `rate_limited` since 2026-06-07, `AroWakeLowSuccessRate` denominator excludes `rate_limited`; (i) **operator-reversal detection cron LIVE on full fleet 2026-06-07** via `detect_reversals.py` + `*/5 min` cron writing to `/opt/fabrik/logs/lessons-pending.jsonl` (trio Phase 5.1.a); (j) **DR drill MEASURED 2026-06-07**: `bootstrap-vps.sh --skip-mesh --skip-dns` on Vultr → 3m 13s, 9.3× under target, 15/15 substantive checks. Remaining Phase 5 work: Apprise pre-route / Loki ruler integration / `propose`+`ack` peer-protocol verbs / repeated-flag-no-action detector — all explicitly deferred until incident-driven per `docs/STRATEGIC_BACKLOG.md`.**

---

## AI Sysadmin (host process on vps1, not a container)

The AI sysadmin runs as a **systemd service** on vps1, not a Docker container. Does not appear in `docker ps`.

| Component | Type | Status |
| :--- | :--- | :--- |
| `vps-sysadmin-bot.service` | systemd, `Restart=always` | Active — Telegram bot, spawns Claude Opus on demand |
| `/etc/cron.d/vps-sysadmin` | cron | Active — 5 scheduled routines (proactive / morning / security / maintenance / backup) |
| Health endpoint | HTTP `:8017/health` | **Bound `127.0.0.1:8017`** since W5 ship 2026-06-01 (`SYSADMIN_HEALTH_HOST` env var added to [`bot.py`](../../scripts/sysadmin/bot.py); default `127.0.0.1`). Local loopback returns `{"status":"ok",...}`. External probes from off-mesh nodes (vps2, vps3) confirm filtered/timeout. The aspirational "for Gatus monitoring" comment is currently a no-op — no Gatus endpoint or Prometheus job actually consumes it; if a future need arises, set `SYSADMIN_HEALTH_HOST=10.99.0.1` via systemd `Environment=` to expose on the mesh interface (still off-public). |

Logs: `/var/log/vps-sysadmin-bot.log`, `/var/log/sysadmin-proactive.log`
Action log: `/opt/fabrik/logs/sysadmin-actions.jsonl`
Shift notes: `/opt/fabrik/logs/sysadmin-shift-notes.md`

**The AI sysadmin already queries Prometheus directly** via `scripts/sysadmin/proactive-check.sh::prom_query()` — see Lesson noted during the 2026-05-30 plan audit. It currently scopes to vps1 metrics only; broadening to include `host="vps2"` / `host="vps3"` is on the pending list.

Full reference: `docs/infrastructure/vps-ai-sysadmin.md`.

### Per-project watchdog sidecars (T-P2 — ✅ COMPLETE 2026-06-03, all 15 artifacts shipped)

A **second** AI layer distinct from the host-level sysadmin above. The host sysadmin watches the platform; per-project watchdog sidecars watch one tenant each. With T-P2 complete, every spec carrying `watchdog: { enabled: true }` (the WatchdogConfig default) will gain a `<project_id>-watchdog` container at `fabrik apply` time — the registrar resolves the applicability, the driver builds the per-project image from `/opt/fabrik-lib/watchdog/sidecar/`, writes `compose.watchdog.yaml` next to the spec's `compose.yaml`, and brings the sidecar up via `docker compose -f compose.yaml -f compose.watchdog.yaml up -d watchdog`.

| Layer | Artifacts | Where | Lines |
| :--- | :--- | :--- | :--- |
| **Sidecar code** (in-container) | claude-settings template + PreToolUse hook + Dockerfile + llm_client + actions + state + agent + vendored cost_budget + (inline) SQLite schema | [`/opt/fabrik-lib/watchdog/sidecar/`](../../../fabrik-lib/watchdog/sidecar/) | ~2,134 |
| **Orchestrator wire-up** | `_register_watchdog` resolver + dispatch in [`infrastructure.py`](../../src/fabrik/orchestrator/infrastructure.py) + 387-line driver at [`drivers/watchdog.py`](../../src/fabrik/drivers/watchdog.py) | `/opt/fabrik/src/fabrik/` | 387 + 63 |
| **Spec field** | `WatchdogConfig` Pydantic class with 13 fields (10 base + 3 amendment) + 22 tests | [`src/fabrik/spec_loader.py`](../../src/fabrik/spec_loader.py) + [`tests/test_spec_loader.py`](../../tests/test_spec_loader.py) | 190 |
| **Operator surface** | emitter library + rule pack + fabrik-lib README row + test spec | [`fabrik-lib/watchdog/emitter/`](../../../fabrik-lib/watchdog/emitter/), [`.windsurf/rules/core/60-watchdog.md`](../../.windsurf/rules/core/60-watchdog.md), [`/opt/fabrik-lib/README.md`](../../../fabrik-lib/README.md), [`specs/services/watchdog-test.yaml`](../../specs/services/watchdog-test.yaml) | 143 (rule pack) + 58 (emitter) + 2 (README rows) + 80 (test spec) |

End-to-end wire-up verified via the `spec_loader.load_spec` → `resolve_applicability` → `WatchdogDriver().provision(dry_run=True)` chain — returns `watchdog: RUNS (spec.watchdog.enabled=true)` and `{'status': 'dry-run', 'image_tag': 'fabrik/watchdog:watchdog-test'}`. 40/40 orchestrator tests green. Cross-process emitter→sidecar integration smoke (emit 5 → read 5 → mark processed → next read 0) confirms the shared `state.db` contract holds. Subplan archived to [`archived/2026-05-30-ai-watchdog-platform-P2-subplan.md`](../development/plans/archived/2026-05-30-ai-watchdog-platform-P2-subplan.md) on T-P2 close.

Default applicability: `WatchdogConfig.enabled` defaults to True, so every spec gets a sidecar unless the operator sets `watchdog: { enabled: false }`. Shape-kind-driven recommendation (operator discipline, NOT encoded in the registrar) lives in [`.windsurf/rules/core/60-watchdog.md`](../../.windsurf/rules/core/60-watchdog.md) — on for `service`/`worker`/`wordpress`; off for `static-site`/`docusaurus`. Hub-side P1 plumbing (`fabrik_analytics` DB + `cost_ledger` table) is live and consumed by the sidecar's vendored `cost_budget.py`.

**Phases shipped 2026-06-03:** T-P3 (`core/self-healing.md` rule pack — 8-row escalation ladder + 5 anti-patterns + signup-flood worked example) and T-P4 (universal-coverage overlay into `docs/traycer/mega-epic-breakdown/02-epic-decomposition-command.md` via 12 surgical edits totaling ~84 lines, plus 1-line sync to `03-expand-epic-files-command.md`'s Metadata block). Both subplans archived.

**T-P5 progress (2026-06-03 → 2026-06-04) — dogfood E2E live:** `specs/services/watchdog-test.yaml` (docker-source `nginx:alpine` + watchdog enabled) deployed on vps1. Steps 5–6 surfaced **five** silent-failure modes in the sidecar's docker-probe + Claude subprocess paths — all root-caused, fixed, and committed to `mobasak/fabrik-lib` + the watchdog driver. End-to-end self-heal verified live 2026-06-04: `docker kill watchdog-test` → 60s tick → rule fires `container_not_running` urgent → Claude Opus returns Tier A `restart_container` → `_restart_main` → `state.resolve_incident("auto")`. **Detection to resolution: 3 s** (with one 60 s tick wait). T-P5 subplan: [`2026-06-03-watchdog-P5-subplan.md`](../development/plans/2026-06-03-watchdog-P5-subplan.md). Parent plan: [`2026-05-30-ai-watchdog-platform.md`](../development/plans/2026-05-30-ai-watchdog-platform.md).

The five failure modes (all visible only with the sidecar dogfooded against a real Docker daemon — none surfaced in unit tests):

| # | Symptom | Root cause | Fix |
| :--- | :--- | :--- | :--- |
| 1 | `gather_snapshot()` returned `{container, ts}` only — no `status`, `health`, `restart_count`. Every tick saw `detect_anomalies() == []`. | `docker.sock` owned by `root:988` mode 660; sidecar runs as UID/GID 1000 (no `docker` group membership) → "permission denied" on every probe → exit 1 silently swallowed. | `src/fabrik/drivers/watchdog.py::_detect_docker_sock_gid()` runs `stat -c %g /var/run/docker.sock` on the hub at apply time and emits `group_add: [<gid>]` in `compose.watchdog.yaml`. |
| 2 | After fixing #1, `docker inspect` exited 1 with `"client version 1.41 is too old. Minimum supported API version is 1.44"`. | Debian Bookworm ships `docker.io` CLI 1.41; hub runs Docker engine 29.0.2 with `MinAPIVersion: 1.44`. | `Dockerfile`: `ENV DOCKER_API_VERSION=1.44`. Forward-compatible until hub bumps MinAPI. |
| 3 | Claude exited 1 with `"sandbox required but unavailable: bubblewrap (bwrap) not installed, socat not installed · sandbox.failIfUnavailable is set"`. | Claude Code 2.1.144 wraps tool calls in a `bwrap`+`socat` sandbox on Linux; sidecar's image lacked the binaries. Operator's `sandbox.failIfUnavailable: true` posture is correct for a watchdog running arbitrary shell — install the deps, don't relax the policy. | `Dockerfile`: add `bubblewrap` + `socat` to the apt install list (~2 MB combined). |
| 4 | After #3, Claude exited 1 with `"Claude configuration file not found at: /home/watchdog/.claude.json"`. | The CLI's per-user config file lives **alongside** `~/.claude/`, not inside it. Driver only bind-mounted the dir. | `src/fabrik/drivers/watchdog.py::_push_overlay()` adds a second bind-mount: `{VPS_CLAUDE_HOME}.json:/home/watchdog/.claude.json:ro`. |
| 5 | After #1–4, claude exited 0 / 1 / timed out depending on flag combo; **the killer** was `--max-budget-usd $X` (any X ≤ ~$0.30 on Opus). Session-init `cache_creation` cost on Opus already exceeds any sane per-call cap before any diagnose tokens are spent — error JSON went to stdout, non-zero rc swallowed it. | Per-call $ caps are wrong for a sysadmin-class agent. Operator directive 2026-06-03: `"do not set budgets for sysadmin why are you doing this"`. | Drop `--max-budget-usd` entirely. Also drop `--effort <level>` (incompatible with `-p` in 2.1.144 — silent rc=0 empty-stdout death) and `--json-schema` (Claude 2.1.144 puts structured output in a separate envelope field and tool-use changes the result shape). Rewrite `_invoke_claude_code` to mirror the **production sysadmin pattern** at [`scripts/sysadmin/bot.py::_run_claude`](../../scripts/sysadmin/bot.py): `--model opus`, `--permission-mode bypassPermissions`, `--session-id <uuid>` first call + `--resume <id>` subsequent (warm cache), `cwd=/project`, `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1`, parse `data["result"]` as plain text with defensive JSON extraction. 300s timeout. Daily-cap + invocations-cap remain as soft circuit-breakers via the WAL kill-switch — that's the only ceiling worth keeping for sysadmin work. |

Net code surface this added (committed):
- `mobasak/fabrik-lib`: 6 commits — agent.py container-state pass, Dockerfile API-version pin + bwrap/socat, llm_client.py drop --effort, llm_client.py drop --max-budget + structured-output parse, llm_client.py timeout 60→300s, llm_client.py adopt sysadmin pattern + defensive JSON parse.
- `mobasak/fabrik` (this repo): watchdog driver gained `_detect_docker_sock_gid()` + `group_add` injection + second `.claude.json` bind-mount; watchdog-test spec bumped `daily_budget_usd 0.50 → 5.00`, `per_incident_budget_usd 0.05 → 1.00`, `daily_invocations_cap 20 → 50` (no per-call CLI enforcement now; values feed only the cost_budget WAL bookkeeping).

---

## Postgres allocation registry

`/opt/monitoring/configs/postgres/allocations.json` on vps1 is the source of truth for "who owns each postgres DB on `postgres-main`". Schema:

```json
{
  "version": 1,
  "last_updated": "<ISO-8601>",
  "allocations": {
    "<db_name>": {
      "owner": "fabrik" | "manual" | "infrastructure",
      "spec_id": "<id>" | null,
      "user": "<role>",
      "notes": ""
    }
  }
}
```

Audit via `fabrik audit-registrars`; cross-references live `pg_database` and emits `drift` for orphan DBs or stale registry entries.

### Live Postgres state (verified 2026-05-31 afternoon)

| Database | Size | Owner / consumer | DB user |
| :--- | :--- | :--- | :--- |
| `glitchtip` | 80 MB | `glitchtip-web` + `glitchtip-worker` | `postgres` |
| `site_provisioner` | 8 MB | `site-provisioner` (interim) | `site_provisioner` |
| `postgres` | 8 MB | system DB | `postgres` |

DB users (`pg_user`, verified live post-cleanup): `postgres` (super), `ozgur` (super, shell admin), `site_provisioner`. The orphan `proxy_user` role was dropped 2026-05-31 evening (its `proxy_management` DB had been removed with the fabrik-proxy service).

**Headline numbers — live (2026-05-31 afternoon):**

- Postgres: **2 app DBs** (glitchtip, site_provisioner) on `postgres-main`. Reduced from the Coolify-era 4 (`translator` + `proxy_management` removed with those services).
- Redis: 2 logical DBs in use (`db3` = authelia, 26 keys with TTL; `db4` = glitchtip, 8 keys); 14 indexes free.
- Gatus: **21 endpoints across 16 config files** (re-verified 2026-06-02 live; `apps/` gained 1 file since the prior count). Top-level breakdown: `apps/` 11 files / 8 endpoints; `core/` 1 file / 5 endpoints; `data/` 1 file / 3 endpoints; `external/` 1 file / 5 endpoints; `observability/` 1 file / 0 endpoints. Some `apps/` files probe services no longer deployed — see "Stale/residue" section below. Endpoint count is the stable signal; file count drifts as endpoints are split into per-service files.
- Backrest (hub): **1 repo** (`b2-vps1`) + **4 plans live** (postgres-dumps, docker-volumes, opt-configs, host-state) — first ship 2026-06-01 (W2). Each spoke runs its own Backrest container with own repo + 2 plans (W11).
- GlitchTip: 7 project IDs retained from Coolify-era audit (captcha=65, image-broker=66, translator=67, emailgateway=68, file-api=69, file-worker=70, site-provisioner=24). Six of those projects no longer have a corresponding live service emitting events; project id=66 in particular is orphaned after the 2026-06-02 image-broker removal and can be deleted in the GlitchTip UI when convenient.
- Grafana: 5 Fabrik-folder dashboards (overview, databases, containers, authelia, meilisearch) + community dashboards. Every dashboard now has `$host` template variable.
- Authelia: **8 access control rules** (see § Authelia access control rules above; was 10, dropped to 8 on 2026-06-02 when the orphaned image-broker rules were removed).
- Meilisearch: 0 indexes (no consumers).
- Prometheus: **14 active targets across 12 jobs**, all up. (Was 13 jobs in Coolify-era; added 3 spoke jobs on 2026-05-31.)

### Stale / residue inventory (vps1) — CLEARED 2026-05-31 evening

The full residue sweep happened in the evening. All items below were resolved in a single SSH session (~30 min) with `ContainerDown` alerts silenced first per Lesson 11.

| Surface | Action taken | Outcome |
| :--- | :--- | :--- |
| DNS | Deleted 6 stale subdomains via CF API (`coolify`, `control`, `dns`, `fabrik-e2e-timing`, `images`, `netdata`) | 17 A records remain (was 22 + 1 added = 23 then –6 = 17) |
| DNS | Created `provision.vps1.ocoron.com` — discovered it was never in CF | site-provisioner now externally reachable |
| Authelia rule #6 | Trimmed from 10 hosts (incl. 5 dead microservices + `dns` alias) to 4 alive (`pdf`, `browser`, `search`, `errors`) | dormant bypasses gone |
| Authelia rule #7 | Removed `coolify.vps1.ocoron.com` | only `monitor.vps1` left |
| Postgres | `DROP USER proxy_user` | 3 users remain: `postgres`, `ozgur`, `site_provisioner` |
| Filesystem | `rm -rf /opt/prometheus` (pre-rename leftover) | gone — real Prometheus in `/opt/monitoring/` |
| Filesystem | `rm /opt/opt.code-workspace` (stray VS Code workspace) | gone |
| UFW | `ufw delete allow 6001/tcp` + `6002/tcp` (Coolify Realtime) | 5 ALLOW + 1 DENY + Wireguard remain |
| fabrik state | Moved 6 orphan/test state files to `.fabrik/state/_destroyed/` (`image-broker.json`, `fabrik-e2e-test.json`, `id-based-app.json`, `integration-test.json`, `no-glitchtip-smoke.json`, `refresh-test.json`) | `.fabrik/state/` clean live; `_destroyed/` is the graveyard (21 files now from cumulative cleanup) |
| Gatus | Deleted 2 stale `.bak` config files (`fabrik-microservices.yaml.bak-20260530-221739`, `observability/stack.yaml.bak-20260530-224220`) | 28 live endpoints, no residue |
| Alertmanager | Created + expired silence ID `59686216-98be-48b2-b461-f9fe624b998c` for `ContainerDown` during the sweep window | no false Telegram alerts |

**Test runs regenerate state files:** the post-sweep `.fabrik/state/` may contain regenerated test artifacts (`id-based-app.json`, `integration-test.json`, etc.) any time tests against the real orchestrator run. These are benign — they get recreated by the test suite and don't represent live deployments. Not residue.

---

## Verified working end-to-end (2026-05-31, full day inclusive of evening batch)

- vps1 mesh hub up, 2 peers (vps2 + vps3) with active handshakes
- Cross-Atlantic mesh RTT 133-134 ms, 0 % packet loss
- vps1's Prometheus scraping 20 targets across 3 hosts (14 vps1 + 6 spoke), all up
- vps2 + vps3 promtail pushing logs to vps1's Loki: `host` label values include both
- vps2 reaches vps1's postgres-main, redis-main, glitchtip-web, authelia all over mesh (verified)
- Spoke Traefik instances live on vps2 + vps3, ready for tenant deploy
- `authelia-vps1@file` middleware defined on each spoke Traefik for cross-host SSO
- All 3 hosts on stable container names (no UUID suffixes anywhere)
- All 3 hosts on `fabrik` Docker network (renamed from `coolify` on 2026-05-31)
- vps2/vps3 SSH posture matches vps1: no root login, no password auth, ozgur sudoer
- Grafana host filter live on all 5 dashboards
- ~~Prometheus `spoke_health` alert group~~ — **NOT in alerts.yml as of 2026-06-07T20:20Z**; the host_health group does fire on host labels including spoke hosts.
- AI sysadmin proactive-check.sh emits host-tagged anomaly names (`cpu_high[vps2]`)
- **Spoke DNS resolving** at Cloudflare authoritative NS: `vps2.ocoron.com`, `*.vps2.ocoron.com`, `vps3.ocoron.com`, `*.vps3.ocoron.com` all return correct A records
- **Cloudflare API token** in `/opt/fabrik/.env` verified active
- **site-provisioner container** healthy on vps1 (alembic migrations applied, `/health` 200, CF + Postgres connectivity ok) — **but as an interim manual stand-up; not yet redeployable via `fabrik apply`** (see "site-provisioner status" earlier)
- **vps1 root `/root/.ssh/known_hosts`** now trusts `github.com`; deployer + bootstrap will keep it that way for any future host (Fix shipped today in `deployer_ssh.py` and `bootstrap-vps.sh` step 03)

---

## References

- DR runbook: `docs/operations/disaster-recovery.md`
- Bootstrap script: `scripts/bootstrap/bootstrap-vps.sh` + templates in `scripts/bootstrap/templates/`
- Platform-to-A+ plan: `docs/development/plans/archived/2026-05-30-platform-to-a-plus.md`
- W1 Coolify residue cleanup: `docs/development/plans/archived/2026-05-30-coolify-residue-cleanup.md`
- Lessons learnt (latest = 65): `docs/LESSONS_LEARNT.md`
- GlitchTip integration: `docs/infrastructure/glitchtip-sdk-integration-setup.md`
- AI sysadmin reference: `docs/infrastructure/vps-ai-sysadmin.md`
- VPS residue policy: `docs/infrastructure/vps-residue-policy.md`
