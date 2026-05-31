# VPS Fleet — Complete Service Inventory

**Last Updated:** 2026-05-31 (post-unification batch — mesh exposures + spoke Traefik + Grafana host filter + spoke alerts)
**Hosts:** **vps1** (LA, hub) · **vps2** (Coventry UK, spoke) · **vps3** (Coventry UK, spoke)
**Network:** Wireguard mesh `10.99.0.0/24` over UDP `51820`, MTU `1420`, hub-and-spoke topology
**Deploy model:** SSH + Docker Compose (no Coolify; removed 2026-05-30 — see `docs/development/plans/2026-05-30-coolify-residue-cleanup.md`)

## Quick state (post-unification)

- **vps1:** 28 containers; 4 shared infra services (postgres-main, redis-main, glitchtip-web, authelia) + loki are now bound to `10.99.0.1:<port>` mesh IPs so spokes can reach them
- **vps2:** **4 containers** — monitoring agents (node-exporter / cadvisor / promtail) + Traefik (public TLS for `*.vps2.ocoron.com`, when DNS lands)
- **vps3:** 4 containers — same as vps2
- **Mesh handshakes:** active, cross-Atlantic RTT 133–134 ms, 0 % loss
- **Cross-host shared infra reachable:** postgres `5432` / redis `6379` / glitchtip `8000` / authelia `9091` / loki `3100` — all verified from vps2 via `10.99.0.1:<port>`
- **Spoke Traefik:** listening on 80 + 443 on each spoke's public IP; `authelia-vps1@file` middleware ready (forward-auth → `http://10.99.0.1:9091/api/verify`)
- **Loki ingest:** spokes pushing logs successfully (`host` label values: `["vps1","vps2","vps3"]`)
- **Prometheus:** scraping 20 active targets (14 vps1 + 6 spoke); every series now carries `host` label
- **Grafana:** all 5 dashboards have `host` template variable (regex `/^vps/`)
- **Alert rules:** new `spoke_health` group — `SpokeDown` / `SpokeHighCPU` / `SpokeHighRAM`
- **AI sysadmin:** `proactive-check.sh` now tags every anomaly with originating host (`cpu_high[vps2]`)
- **Backups:** B2 bucket empty (intentional — Backrest plans deleted 2026-05-31; nothing material to back up yet)

## Re-verify / Update This Document

```bash
# Container counts per host
ssh vps  'sudo docker ps --format "{{.Names}}" | wc -l'   # expect 28
ssh vps2 'sudo docker ps --format "{{.Names}}" | wc -l'   # expect 3
ssh vps3 'sudo docker ps --format "{{.Names}}" | wc -l'   # expect 3

# Mesh handshake state
ssh vps 'sudo wg show'

# Prometheus targets across hosts
ssh vps 'sudo docker exec prometheus wget -qO- http://localhost:9090/api/v1/targets' \
  | python3 -c 'import json,sys; d=json.load(sys.stdin)["data"]["activeTargets"]; up=sum(1 for t in d if t["health"]=="up"); print(f"{up}/{len(d)} up")'

# UFW per host
ssh vps  'sudo ufw status numbered'
ssh vps2 'sudo ufw status numbered'
ssh vps3 'sudo ufw status numbered'
```

---

## vps1 — Hub (LA)

**Provider:** GreenCloudVPS (`12th Birthday Sale - 1212 LA`) — Ubuntu 24.04 LTS
**Specs:** 6 vCores (x86_64 EPYC Genoa), 11.6 GB RAM, 108 GB disk
**Public IP:** 172.93.160.197
**Mesh IP:** 10.99.0.1
**Hostname:** vps1.ocoron.com
**SSH:** ozgur user, key auth only (root disabled, password auth disabled)

### Container inventory (28 running)

| Container | Memory limit | Purpose |
| :--- | :--- | :--- |
| `traefik` | — | Public HTTPS termination, Let's Encrypt, Authelia forward-auth dispatch |
| `authelia` | 512m | SSO + 2FA forward-auth for all `*.vps1.ocoron.com` admin dashboards |
| `postgres-main` | 2g | Shared PostgreSQL 16 — multi-tenant, one DB per service via registrar |
| `redis-main` | — | Shared Redis 7 — one logical DB per service |
| `postgres-exporter` | — | Postgres metrics for Prometheus |
| `redis-exporter` | — | Redis metrics for Prometheus |
| `prometheus` | 1g | Time-series store + alert evaluator. 30 d / 5 GB retention. |
| `grafana` | — | Dashboards (Prometheus + Loki sources, pre-provisioned) |
| `loki` | — | Log aggregator. Now bound to `10.99.0.1:3100` for spoke pushes. 7 d retention. |
| `promtail` | — | Ships vps1 container stdout to Loki |
| `alertmanager` | — | Routes Prometheus alerts → Apprise → Telegram |
| `cadvisor` | — | Container metrics for vps1's Prometheus |
| `node-exporter` | — | Host metrics for vps1's Prometheus |
| `pushgateway` | 64m | Short-lived metric pushes (used by `audit_all_registrars.py` cron) |
| `gatus` | 256m | Synthetic health probes for all services |
| `apprise` | 768m | Notification dispatcher (Alertmanager → Telegram) — gunicorn workers 2 |
| `backrest` | 512m | restic-based backups → B2 (currently 0 active plans, intentional) |
| `glitchtip-web` | 512m | Self-hosted Sentry-compat error tracker. UI at `errors.vps1.ocoron.com` |
| `glitchtip-worker` | 512m | GlitchTip background worker (Celery) |
| `meilisearch` | 512m | Shared search engine, per-service index via registrar |
| `n8n` | 2g | Visual workflow automation (`auto.vps1.ocoron.com`) |
| `browserless` | 2g | Headless Chrome HTTP API |
| `gotenberg` | 512m | LibreOffice + Chrome → PDF service |
| `ocoron-com-nginx-1` | — | Tenant: ocoron.com WordPress front-end |
| `ocoron-com-wordpress-1` | — | Tenant: WordPress PHP-FPM |
| `ocoron-com-db-1` | — | Tenant: MariaDB (WP-specific, not on shared postgres-main) |
| `ocoron-com-redis-1` | — | Tenant: per-WP Redis cache |
| `ocoron-com-backup-1` | — | Tenant: nightly mysqldump sidecar |

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

### Container inventory — vps2 (4 running)

| Container | Bind | Purpose |
| :--- | :--- | :--- |
| `traefik` | `0.0.0.0:80,443` (public) | Public TLS termination for future `*.vps2.ocoron.com` services; `authelia-vps1@file` middleware ready |
| `node-exporter` | `10.99.0.2:9100` (mesh-only) | Host metrics → vps1's Prometheus over mesh |
| `cadvisor` | `10.99.0.2:8080` (mesh-only) | Container metrics → vps1's Prometheus over mesh |
| `promtail` | `10.99.0.2:9080` (mesh-only) | Ships container stdout → vps1's Loki at `10.99.0.1:3100` |

### `/opt` structure on vps2

```text
/opt/
├── containerd/
├── monitoring-agent/        — compose.yaml + promtail.yaml (rendered by bootstrap-vps.sh)
└── traefik/                 — compose.yaml + traefik.yml + acme.json + dynamic/authelia.yml
```

Awaiting tenant SaaS — DNS for `*.vps2.ocoron.com` is the next gate (blocked on Cloudflare API token refresh).

---

## vps3 — Coventry UK spoke

**Provider:** GreenCloudVPS (`BudgetKVMCUK-3` SKU)
**Specs:** 4 vCores (EPYC Rome), 8 GB RAM, 60 GB NVMe RAID-10, 8 TB BW
**Public IP:** 104.128.190.151
**Mesh IP:** 10.99.0.3
**Hostname:** vps3.ocoron.com (corrected via `hostnamectl` during bootstrap — initial typo `vpse.ocoron.com`)
**SSH:** ozgur user, key auth only

### Container inventory — vps3 (4 running)

Identical to vps2: `traefik` (public 80+443), `node-exporter` / `cadvisor` / `promtail` all bound to their respective mesh IP (10.99.0.3).

### `/opt` structure on vps3

Identical to vps2: `containerd/` + `monitoring-agent/` + `traefik/`.

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

#### vps1 UFW

```text
[ 1] 22/tcp                     ALLOW   # SSH
[ 2] 80/tcp                     ALLOW   # HTTP
[ 3] 443/tcp                    ALLOW   # HTTPS
[ 4] 1194/tcp                   ALLOW   # OpenVPN (legacy — user's personal VPN)
[ 5] 6001/tcp                   ALLOW   # ⚠ Coolify Realtime — stale, can drop
[ 6] 6002/tcp                   ALLOW   # ⚠ Coolify Realtime — stale, can drop
[ 7] 8000/tcp                   DENY    # ⚠ stale comment refers to coolify.vps1; rule itself is fine
[ 8] 51820/udp                  ALLOW   # Wireguard mesh
```

#### vps2 / vps3 UFW (matching, applied by bootstrap)

```text
22/tcp                     ALLOW   # SSH
80/tcp                     ALLOW   # HTTP
443/tcp                    ALLOW   # HTTPS
51820/udp                  ALLOW   # Wireguard mesh
```

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

- vps1: `/opt/traefik/acme.json` (mode 600)
- vps2/vps3: TODO — first tenant deploy auto-generates

### Traefik label patterns (used by scaffold-emitted compose templates)

| Service type | Middlewares | Source |
| :--- | :--- | :--- |
| Admin dashboard | `authelia-forward@docker,gzip@docker` | scaffold emits |
| API service (X-Internal-Token) | `gzip@docker` | scaffold emits |
| Public service (no auth) | (none) | scaffold emits |

For services on vps2/vps3 that need Authelia, the forward-auth middleware will point at `http://10.99.0.1:9091/api/verify` (over mesh) — but this requires binding Authelia to the mesh IP first (see TODO list above).

---

## Authelia

**Container:** `authelia` (stable name; no UUID suffix)
**Config:** `/opt/authelia/config/configuration.yml` (working copy) + `/var/lib/docker/volumes/.../configuration.yml` (live config Authelia reads)
**Sync:** `authelia-config-sync.service` (systemd, inotify-driven) — watches the working copy, copies to volume, restarts container on save. ~2 s reaction time.
**Sessions:** `redis-main:6379` DB index 3 — survives Authelia restarts
**TOTP:** `ocoron.com` issuer, 30 s period
**Storage:** SQLite `/config/db.sqlite3` (named volume)

### Access control rules (live, as of 2026-05-31)

| Domain | Policy | Note |
| :--- | :--- | :--- |
| `ocoron.com`, `www.ocoron.com` | bypass | Public WP site |
| `wp-test.vps1.ocoron.com`, `status.vps1.ocoron.com` | bypass | Public probes |
| `*.vps1.ocoron.com` | bypass | `/health`, `/healthz`, `/metrics`, `/api/health` paths only |
| 9 API service domains (pdf, browser, search, captcha, proxy, translator, files-api, emailgateway, dns) | bypass | All paths (app-layer X-Internal-Token auth) |
| `coolify.vps1.ocoron.com`, `monitor.vps1.ocoron.com` | bypass | `^/api/` only (admin dashboards need API access without 2FA) |
| `images.vps1.ocoron.com` | bypass | `^/api/` only (paired-pattern; T1-04) |
| `*.vps1.ocoron.com` | two_factor | catch-all for everything else |

Rule precedence: Authelia is first-match-wins. Specific `^/api/` bypasses for admin-dashboard hosts MUST come BEFORE the `*.vps1 two_factor` catchall. `src/fabrik/drivers/authelia.py::_compute_insert_index` makes this automatic for future paired-pattern services.

**CRITICAL:** Authelia exits on SIGHUP — does NOT hot-reload. The `authelia-config-sync.service` handles the restart correctly. Manual reload: `ssh vps "sudo docker restart authelia"` (just the container name now — no UUID suffix).

**Cross-host pattern (not yet wired):** for `*.vps2.ocoron.com` admin dashboards, the plan is to add `auth.vps2.ocoron.com` as a CNAME → vps1 and let vps1's Authelia issue cookies scoped to `*.vps2.ocoron.com`. See `docs/development/plans/2026-05-30-platform-to-a-plus.md` § W-Multi M7.

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
**Deployed services using this:** captcha, image-broker, translator, proxy, emailgateway

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

### Prometheus scrape targets (20 live)

- vps1-local (14 targets): prometheus self, node-exporter, cadvisor, loki, alertmanager, gatus, traefik, grafana, authelia, postgres-exporter, redis-exporter, pushgateway, fabrik-drift, glitchtip-web
- vps2 (3 targets): `10.99.0.2:9100` (node), `10.99.0.2:8080` (cadvisor), `10.99.0.2:9080` (promtail)
- vps3 (3 targets): `10.99.0.3:9100`, `10.99.0.3:8080`, `10.99.0.3:9080`

Scrape jobs for spokes: `node-spokes`, `cadvisor-spokes`, `promtail-spokes` (added to `/opt/monitoring/configs/prometheus/prometheus.yml` on 2026-05-31). Reload: `ssh vps "sudo docker kill -s HUP prometheus"`.

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

**Status (as of 2026-05-31):** **0 active plans.** B2 bucket `vps1-ocoron-backups` is empty.

This is intentional. Per the session 2026-05-31 cleanup:

- All prior plans deleted (3 active + 5 stale test plans, ~94 failures in 30 days were mostly the stale test plans)
- B2 bucket emptied; bucket itself preserved for reuse
- Restic password + B2 keys saved off-VPS to `/opt/fabrik/.env` on the dev machine (`BACKREST_RESTIC_PASSWORD`, `B2_KEY_ID`, `B2_APPLICATION_KEY`) — closes the "credentials only on vps1" DR weakness

When backups are reconfigured:

- Active plans: `postgres-dumps` (`/opt/backups/pg_dump_*.sql`), `docker-volumes` (`/var/lib/docker/volumes/`), `opt-configs` (`/opt/<svc>/{compose.yaml,.env}`)
- Failure hook URL needs to be `apprise:8000` (NOT the old Coolify UUID-suffix hostname `apprise-lcocgs4gs8ksg4g08w40ows8` — that's why prior failure alerts never reached Telegram)
- Schedule postgres-dumps AFTER the host's pg_dump cron completes (prior 44 % failure rate was due to the race)

Spoke backups (vps2/vps3): not yet configured. Pattern when needed: Backrest on vps1 has SSH access to spokes via `ssh vps2`/`ssh vps3` (mesh + key auth); plan paths can include `vps2:/opt/` etc.

Full runbook: `docs/operations/disaster-recovery.md`

---

## Resource limits (vps1, current)

| Container | Memory limit |
| :--- | :--- |
| `apprise` | 768m |
| `authelia` | 512m |
| `backrest` | 512m |
| `browserless` | 2g |
| `gatus` | 256m |
| `glitchtip-web` | 512m |
| `glitchtip-worker` | 512m |
| `gotenberg` | 512m |
| `meilisearch` | 512m |
| `n8n` | 2g |
| `postgres-main` | 2g |
| `prometheus` | 1g |
| `pushgateway` | 64m |

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

---

## Pending actions (current TODO list)

| # | Action | Priority | Blocking | Status |
| :--- | :--- | :--- | :--- | :--- |
| 1 | Refresh `CLOUDFLARE_API_TOKEN` in `/opt/fabrik/.env` | High | DNS provisioning + site-provisioner deploy | **OPEN** |
| 2 | Redeploy `site-provisioner` on vps1 (M0b) | High | Blocked on #1 | **OPEN** |
| 3 | Bind `postgres-main` to `10.99.0.1:5432` for spoke access | High | Unblocks spoke tenant DB use | ✓ done 2026-05-31 (commit `f853a50`) |
| 4 | Bind `redis-main` to `10.99.0.1:6379` for spoke access | High | Unblocks spoke tenant cache use | ✓ done 2026-05-31 |
| 5 | Bind `glitchtip-web` to `10.99.0.1:8000` for spoke ingestion | Medium | Future spoke tenants | ✓ done 2026-05-31 |
| 6 | Bind `authelia` to `10.99.0.1:9091` for cross-host forward-auth | Medium | First spoke admin dashboard | ✓ done 2026-05-31 |
| 7 | Deploy `traefik` on vps2 and vps3 (public TLS termination) | Medium | First spoke tenant | ✓ done 2026-05-31 (`authelia-vps1@file` middleware ready) |
| 8 | Add `host` template variable to all Grafana dashboards | Low | Cosmetic | ✓ done 2026-05-31 (5/5 dashboards, regex `/^vps/`) |
| 9 | Reconfigure Backrest plans (postgres-dumps, docker-volumes, opt-configs) with correct `apprise:8000` hook URL | Low | When data lands worth backing up | **OPEN** |
| 10 | AI sysadmin scripts query spoke metrics too (currently vps1-only) | Low | Future | ✓ done 2026-05-31 (`prom_hosts()` + spoke alert rules) |
| 11 | Fabrik spec gains `target_vps` field + `fabrik apply --target-vps` flag (W-Multi M4/M5) | Low | Big code change | **OPEN** |
| 12 | Clean stale UFW rules on vps1 (6001, 6002, the "8000 DENY" Coolify comment) | Trivial | — | **OPEN** |
| 13 | Authelia access-control rules for `*.vps2.ocoron.com` / `*.vps3.ocoron.com` admin dashboards | Medium | Needs first such dashboard + DNS (blocks #2) | **OPEN** |
| 14 | Backrest spoke backups (`docker-volumes-vps2`, `opt-configs-vps2`, etc.) | Low | Per #9 — defer until backups re-enabled | **OPEN** |

**Net after this batch:** 8 items closed (3, 4, 5, 6, 7, 8, 10 plus 9 still open). DNS (#1, #2) is the gating-prerequisite blocker for everything else.

---

## Known issues (current)

### Issue 1: Backrest failure-notification webhook is broken

`/opt/backrest/config/config.json` plan hooks reference `http://apprise-lcocgs4gs8ksg4g08w40ows8:8000/notify/alerts` — the old Coolify-era UUID-suffix container name. After the W1 container-name standardization on 2026-05-30, `apprise` is the stable name. **Effect:** if any future backup plan fails, the failure alert never reaches Telegram. Currently irrelevant (zero plans), but fix on next plan creation: replace `apprise-lcocgs4gs8ksg4g08w40ows8` with `apprise`.

### Issue 2: `errors.vps1.ocoron.com` predates T2-08 Part A in `audit_authelia_gates.py`

The Authelia gating audit cron flags the `errors.vps1` middleware as "unexpected" every Monday 06:00. Cosmetic (exit 0; log shows `1 GAP`); update the inventory in `scripts/audit_authelia_gates.py` when convenient.

### Issue 3: `/opt/prometheus/compose.yaml` is a stale leftover

Pre-fabrik-network-rename. Real Prometheus runs from `/opt/monitoring/compose.yaml`. Delete `/opt/prometheus/` to avoid confusion.

### Issue 4: Cloudflare API token in `/opt/fabrik/.env` is invalid

Returns `Invalid access token` on first use after the session 2026-05-31 cleanup. Blocks M0b (site-provisioner redeploy) and all subsequent DNS work. Refresh required.

---

## AI Sysadmin (host process on vps1, not a container)

The AI sysadmin runs as a **systemd service** on vps1, not a Docker container. Does not appear in `docker ps`.

| Component | Type | Status |
| :--- | :--- | :--- |
| `vps-sysadmin-bot.service` | systemd, `Restart=always` | Active — Telegram bot, spawns Claude Opus on demand |
| `/etc/cron.d/vps-sysadmin` | cron | Active — 5 scheduled routines (proactive / morning / security / maintenance / backup) |
| Health endpoint | HTTP `:8017/health` | Active — bound locally, blocked from Docker via `DOCKER-USER` |

Logs: `/var/log/vps-sysadmin-bot.log`, `/var/log/sysadmin-proactive.log`
Action log: `/opt/fabrik/logs/sysadmin-actions.jsonl`
Shift notes: `/opt/fabrik/logs/sysadmin-shift-notes.md`

**The AI sysadmin already queries Prometheus directly** via `scripts/sysadmin/proactive-check.sh::prom_query()` — see Lesson noted during the 2026-05-30 plan audit. It currently scopes to vps1 metrics only; broadening to include `host="vps2"` / `host="vps3"` is on the pending list.

Full reference: `docs/infrastructure/vps-ai-sysadmin.md`.

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

Headline numbers from the most recent audit (2026-05-09):

- Postgres: 4 app DBs across 4 services
- Redis: 2 logical DBs in use (authelia=db3, glitchtip=db4); 14 indexes free
- Gatus: 28 endpoints across 14 config files
- Backrest: 0 repo + 0 plans **(now 0 after 2026-05-31 wipe; original had 1 repo + 4 plans)**
- GlitchTip: 7 active projects
- Grafana: 9 dashboards (5 Fabrik + 4 community)
- Authelia: 8 access control rules
- Meilisearch: 0 indexes (no consumers yet)
- Prometheus: 20 scrape jobs (was 13 — added 3 spoke job sets on 2026-05-31), all up

---

## Verified working end-to-end (2026-05-31)

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
- Prometheus `spoke_health` alert group active (SpokeDown / SpokeHighCPU / SpokeHighRAM)
- AI sysadmin proactive-check.sh emits host-tagged anomaly names (`cpu_high[vps2]`)

---

## References

- DR runbook: `docs/operations/disaster-recovery.md`
- Bootstrap script: `scripts/bootstrap/bootstrap-vps.sh` + templates in `scripts/bootstrap/templates/`
- Platform-to-A+ plan: `docs/development/plans/2026-05-30-platform-to-a-plus.md`
- W1 Coolify residue cleanup: `docs/development/plans/2026-05-30-coolify-residue-cleanup.md`
- Lessons learnt (latest = 65): `docs/LESSONS_LEARNT.md`
- GlitchTip integration: `docs/infrastructure/glitchtip-sdk-integration-setup.md`
- AI sysadmin reference: `docs/infrastructure/vps-ai-sysadmin.md`
- VPS residue policy: `docs/infrastructure/vps-residue-policy.md`
