# VPS Fleet — Complete Service Inventory

**Last Updated:** 2026-06-01 (post-W1 ship — UFW installed + active on vps2/vps3; Lesson 68 captured; probe reports tracked under `docs/infrastructure/probe-reports/`)
**Last probe report:** [`probe-reports/infra-probe-2026-05-31T23-07Z.yaml`](probe-reports/infra-probe-2026-05-31T23-07Z.yaml)
**Hosts:** **vps1** (LA, hub) · **vps2** (Coventry UK, spoke) · **vps3** (Coventry UK, spoke)
**Network:** Wireguard mesh `10.99.0.0/24` over UDP `51820`, MTU `1420`, hub-and-spoke topology
**Deploy model:** SSH + Docker Compose (no Coolify; removed 2026-05-30 — see `docs/development/plans/2026-05-30-coolify-residue-cleanup.md`)

## Quick state (current)

- **vps1:** 29 containers — the original 28 shared-infra services plus `site-provisioner` (running but **interim manual stand-up**, not yet redeployable via `fabrik apply` — see "site-provisioner status" below). 4 shared infra services (postgres-main, redis-main, glitchtip-web, authelia) + loki are bound to `10.99.0.1:<port>` mesh IPs so spokes can reach them.
- **vps2:** 4 containers — monitoring agents (node-exporter / cadvisor / promtail) + Traefik (public TLS for `*.vps2.ocoron.com`). DNS is **live** as of 2026-05-31 afternoon.
- **vps3:** 4 containers — same as vps2. DNS is **live** as of 2026-05-31 afternoon.
- **Mesh handshakes:** active, cross-Atlantic RTT 133–134 ms, 0 % loss
- **Cross-host shared infra reachable:** postgres `5432` / redis `6379` / glitchtip `8000` / authelia `9091` / loki `3100` — all verified from vps2 via `10.99.0.1:<port>`
- **Spoke DNS (NEW today):** `vps2.ocoron.com` + `*.vps2.ocoron.com` → `96.9.214.128`; `vps3.ocoron.com` + `*.vps3.ocoron.com` → `104.128.190.151`. Wildcards cover `auth.vpsN`, `<tenant>.vpsN`, etc. Apex + wildcard each, no per-service A records needed.
- **Spoke Traefik:** listening on 80 + 443 on each spoke's public IP; `authelia-vps1@file` middleware ready (forward-auth → `http://10.99.0.1:9091/api/verify`). Public TLS via Let's Encrypt will issue on first tenant deploy.
- **Loki ingest:** spokes pushing logs successfully (`host` label values: `["vps1","vps2","vps3"]`)
- **Prometheus:** scraping **18 active targets across 15 jobs** (12 vps1 + 6 spoke), all up; every series carries `host` label
- **Grafana:** all 5 dashboards have `host` template variable (regex `/^vps/`)
- **Alert rules:** `spoke_health` group active — `SpokeDown` / `SpokeHighCPU` / `SpokeHighRAM`
- **AI sysadmin:** `proactive-check.sh` tags every anomaly with originating host (`cpu_high[vps2]`)
- **Backups:** B2 bucket empty (intentional — Backrest plans deleted 2026-05-31; nothing material to back up yet)
- **Cloudflare API token (`/opt/fabrik/.env`):** refreshed 2026-05-31 afternoon by syncing the working token from the local site-provisioner instance (`/opt/site-provisioner/.env`). Pre-edit backup at `backups/.env.backup.20260531-155948`. Verified active via `curl /user/tokens/verify`.
- **DNS state (post-residue-cleanup, evening):** 17 A records in CF zone `ocoron.com`. vps1 has 12 live subdomains (auth, auto, backup, browser, errors, monitor, notify, pdf, **provision** [new — was never in CF; site-provisioner had a Traefik router but no public DNS — created during the cleanup], search, status, vps1 apex). vps2 + vps3 each have apex + wildcard. **6 stale subdomains deleted** (`coolify`, `control`, `dns`, `fabrik-e2e-timing`, `images`, `netdata`).
- **`fabrik apply --target-vps`:** shipped this evening as W-Multi M4. Specs gain optional `target_vps: vps1|vps2|vps3` field (regex-validated). CLI `--target-vps` flag overrides spec. Deployer env-swaps `FABRIK_VPS_SSH_HOST` around the deploy block so ~30 SSH call sites route to the spoke without per-site changes. DNS provisioner picks the right IP from the `VPS_IPS` map. Hub-side registrars (postgres, redis, gatus, glitchtip, authelia, grafana, meilisearch) stay on vps1 by design. 3 new tests + 4 pre-existing tests fixed; all 103 deployer/spec tests pass. CLI: `.venv/bin/fabrik apply specs/services/<id>.yaml --target-vps vps2`.

## site-provisioner status — INTERIM, not pipeline-ready

`site-provisioner` is running on vps1 at `provision.vps1.ocoron.com` (container healthy, alembic migrations applied, Cloudflare + Postgres connectivity verified, `/health` returns 200) — but **do not treat it as a production-deployable service yet**. It was brought up manually this afternoon to unblock the spoke DNS step. The proper `fabrik apply` pipeline for it has known gaps that must close before redeploy via fabrik is safe:

| Gap | What's done today | What's still needed |
| :--- | :--- | :--- |
| Upstream repo's `compose.yaml` still references the legacy `coolify` Docker network | **RESOLVED** — committed in `fa32d61` (bundled into a docs commit) and pushed to `mobasak/site-provisioner@main`. Local + origin in sync. | none |
| Spec `secrets.from_env` was missing 3 keys + 5 env literals referenced by the repo's compose.yaml at interpolation time | [`specs/services/site-provisioner.yaml`](../../specs/services/site-provisioner.yaml) now declares all 21 `${VAR}` references (13 literals incl. `DATABASE_URL` placeholder + 9 from-env secrets) | Verify a full `fabrik apply` once the compose.yaml push lands |
| `/opt/fabrik/.env` was missing `BING_WEBMASTER_API_KEY` and had a different `API_KEY` than vps1's live value | Synced both from vps1's live `.env`; preserved vps1's API_KEY value so existing callers do not break | None |
| GitHub host-key trust missing on vps1's root SSH (post-Coolify-removal cleanup wiped it) | Added `github.com` to `/root/.ssh/known_hosts` on vps1; **and** patched the deployer + bootstrap so this re-creates itself going forward (see "Permanent fixes shipped today" below) | None |
| Postgres user `site_provisioner` password was unknown (not in fabrik state) | Rotated to a fresh 32-char a-zA-Z0-9 password; live `.env` on vps1 updated; `DATABASE_URL` resolved | The new password is not yet captured in fabrik state — when `fabrik apply` runs end-to-end the postgres registrar will overwrite it cleanly |

**Operational implication:** until the upstream `compose.yaml` push happens and one clean `fabrik apply` cycle is verified, treat the running container as a one-off. Do not `fabrik redeploy site-provisioner` — it will git-pull the repo (still says `coolify`) and `docker compose up` will fail. To restart the running instance safely today: `ssh vps "cd /opt/site-provisioner && sudo docker compose up -d"` (uses the locally-patched compose.yaml that exists only on the VPS).

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
ssh vps2 'sudo docker ps --format "{{.Names}}" | wc -l'   # expect 4
ssh vps3 'sudo docker ps --format "{{.Names}}" | wc -l'   # expect 4

# Mesh handshake state
ssh vps 'sudo wg show'

# Prometheus targets across hosts (expect 18/18 up across 15 jobs)
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

### Container inventory (29 running)

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
| `backrest` | 512m | restic-based backups → B2 (currently 0 active plans, intentional) |
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

**DNS live as of 2026-05-31 afternoon:** `vps2.ocoron.com` + `*.vps2.ocoron.com` → `96.9.214.128` (Cloudflare, unproxied). Wildcard covers `auth.vps2`, `<tenant>.vps2`, etc. Awaiting first tenant deploy; first Let's Encrypt issuance will happen on that deploy.

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
[ 4] 1194/tcp                   ALLOW   # OpenVPN (legacy — user's personal VPN)
[ 5] 8000/tcp                   DENY    # belt-and-suspenders (stale Coolify comment, rule retained)
[ 6] 51820/udp                  ALLOW   # Wireguard mesh
```

(Plus IPv6 duplicates of each rule.) The previously-stale `6001/tcp` + `6002/tcp` ALLOW rules (Coolify Realtime) were removed in the cleanup sweep.

#### vps2 / vps3 UFW (verified live 2026-05-31 22:36 UTC — installed and active)

UFW was installed + enabled by W1 of the fleet-hardening plan on 2026-05-31 evening. Package status `ii` (installed), service active, 8 ALLOW rules each (4 IPv4 + 4 IPv6 mirrors), default policy `deny (incoming) / allow (outgoing) / deny (routed)`. Verified via `data/infra-probe-2026-05-31T22-36Z.yaml`.

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

### Access control rules — 10 rules live (verified against `/opt/authelia/config/configuration.yml`, post-cleanup)

| # | Policy | Domain(s) | Resources (path regex) |
| :--- | :--- | :--- | :--- |
| 1 | bypass | `ocoron.com` | (all) |
| 2 | bypass | `www.ocoron.com` | (all) |
| 3 | bypass | `wp-test.vps1.ocoron.com` | (all) |
| 4 | bypass | `status.vps1.ocoron.com` | (all) |
| 5 | bypass | `*.vps1.ocoron.com` | `^/health$`, `^/healthz$`, `^/metrics$`, `^/api/health$` |
| 6 | bypass | 4 hosts: `pdf`, `browser`, `search`, `errors`.vps1.ocoron.com | (all paths — public or app-layer-protected) |
| 7 | bypass | `monitor.vps1.ocoron.com` | `^/api/` only |
| 8 | bypass | `images.vps1.ocoron.com` | `^/api/` only (paired-pattern with #9) |
| 9 | two_factor | `images.vps1.ocoron.com` | (all paths) |
| 10 | two_factor | `*.vps1.ocoron.com` | (catch-all for everything else) |

**Cleaned 2026-05-31 evening:** rule #6 went from 10 dormant hosts (incl. 5 dead microservices + `dns` stale alias) down to 4 live hosts; rule #7 dropped `coolify.vps1.ocoron.com` (Coolify removed 2026-05-30). Backup at `/opt/authelia/config/configuration.yml.bak.20260531-171950`. Authelia restarted cleanly via `authelia-config-sync.service` (~7 s).

**Note on `errors.vps1.ocoron.com` in rule #6:** the GlitchTip UI is reachable *without* Authelia. A prior session note claimed T2-08 Part A removed it; the change never landed and after review it stays — GlitchTip is a public error-report UI used cross-tenant. If you want it 2FA-protected later, move it out of rule #6 into the catch-all `two_factor`.

Rule precedence: Authelia is first-match-wins. Specific `^/api/` bypasses for admin-dashboard hosts MUST come BEFORE the catch-all `two_factor`. `src/fabrik/drivers/authelia.py::_compute_insert_index` enforces this automatically for future paired-pattern services.

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
**Deployed services using this:** **none currently.** The 7 microservices that previously consumed this pattern (`captcha`, `image-broker`, `translator`, `proxy`, `emailgateway`, `file-api`, `file-worker`) are not currently deployed on vps1 — no `/opt/<svc>/` directory, no container, no Traefik router. The pattern is available the moment any new spec opts into it.

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

### Prometheus scrape targets (18 live across 15 jobs — verified `/api/v1/targets` 2026-05-31)

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

Spokes (3 jobs / 6 targets):

| Job | Targets |
| :--- | :--- |
| `node-spokes` | `10.99.0.2:9100`, `10.99.0.3:9100` |
| `cadvisor-spokes` | `10.99.0.2:8080`, `10.99.0.3:8080` |
| `promtail-spokes` | `10.99.0.2:9080`, `10.99.0.3:9080` |

**Not scraped (intentionally or by gap):**

- `traefik` — no metrics endpoint job; routing health is observed via Gatus + Loki.
- `glitchtip-web` — `django-prometheus` not bundled by default in GlitchTip 6.x.
- `fabrik-drift` — placeholder job referenced in earlier docs; no live job by this name.
- 7 ex-microservices (`captcha`, `image-broker`, `translator`, `proxy`, `emailgateway`, `file-api`, `file-worker`) — not deployed, so no `/metrics` to scrape. When/if redeployed, scaffold-emitted `metrics.py` re-enables.

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

**Status (live, 2026-05-31 afternoon):** Backrest config has **1 repo retained + 0 plans**. B2 bucket `vps1-ocoron-backups` exists but is empty.

| Repo ID | URI | Flags |
| :--- | :--- | :--- |
| `b2-vps1` | `s3:https://s3.us-west-004.backblazeb2.com/vps1-ocoron-backups` | `--compression=auto` |

The repo is retained so plan reconfiguration only needs new plans (not also re-pairing a repo). The plan count was zeroed deliberately in the morning cleanup. Per the session 2026-05-31 cleanup:

- All prior plans deleted (3 active + 5 stale test plans, ~94 failures in 30 days were mostly the stale test plans)
- B2 bucket emptied; bucket + the `b2-vps1` Backrest repo entry preserved for reuse
- Restic password + B2 keys saved off-VPS to `/opt/fabrik/.env` on the dev machine — closes the "credentials only on vps1" DR weakness. **Verified present:** `BACKREST_RESTIC_PASSWORD` ✓, `B2_KEY_ID` ✓, `B2_APPLICATION_KEY` ✓. (`B2_ACCOUNT_ID` not stored; the master `B2_KEY_ID` is sufficient for restic's S3 driver against the B2 endpoint.)

When backups are reconfigured:

- Active plans: `postgres-dumps` (`/opt/backups/pg_dump_*.sql`), `docker-volumes` (`/var/lib/docker/volumes/`), `opt-configs` (`/opt/<svc>/{compose.yaml,.env}`)
- Failure hook URL needs to be `apprise:8000` (NOT the old Coolify UUID-suffix hostname `apprise-lcocgs4gs8ksg4g08w40ows8` — that's why prior failure alerts never reached Telegram)
- Schedule postgres-dumps AFTER the host's pg_dump cron completes (prior 44 % failure rate was due to the race)

Spoke backups (vps2/vps3): not yet configured. Pattern when needed: Backrest on vps1 has SSH access to spokes via `ssh vps2`/`ssh vps3` (mesh + key auth); plan paths can include `vps2:/opt/` etc.

Full runbook: `docs/operations/disaster-recovery.md`

---

## Microservices status — none currently deployed

Seven application microservices were running pre-Coolify-removal. As of 2026-05-31 afternoon, **none are deployed on vps1**: no `/opt/<svc>/` directory, no container, no Traefik router. Their fabrik specs still exist in `specs/services/` and can be redeployed via `fabrik apply` once the deploy pipeline reaches feature parity (see [§ Pending actions](#pending-actions-current-todo-list) items 2a and 11).

| Service | Spec | DNS still exists? | Traefik router? | Container? | GlitchTip project still in DB? |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `captcha` | yes | no | no | no | yes (id=65) |
| `image-broker` | yes | `images.vps1` exists (stale) | no | no | yes (id=66) |
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
| 9 | Reconfigure Backrest plans (postgres-dumps, docker-volumes, opt-configs) with correct `apprise:8000` hook URL | Low | When data lands worth backing up | **OPEN** |
| 10 | AI sysadmin scripts query spoke metrics too (currently vps1-only) | Low | Future | ✓ done 2026-05-31 (`prom_hosts()` + spoke alert rules) |
| 11 | Fabrik spec gains `target_vps` field + `fabrik apply --target-vps` flag (W-Multi M4) | Low | Big code change | ✓ done 2026-05-31 evening — see § Permanent fixes shipped today; spec field + CLI flag + DNS routing + deployer env-swap + 3 new tests + 4 pre-existing-test fixes; 103/103 deployer/spec tests pass. `fabrik destroy --target-vps` + `fabrik redeploy --target-vps` follow-ups still open. |
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
| 22 | `fabrik destroy --target-vps` + `fabrik redeploy --target-vps` (same env-swap pattern as W-Multi M4) | Low | Symmetric ops for spoke services | **OPEN** — ~5–10 min each |
| 23 | First real spoke deploy (e.g. tiny test spec with `target_vps: vps2`, domain `<svc>.vps2.ocoron.com`) | Medium | Exercises spoke Traefik's Let's Encrypt issuance for the first time | **OPEN** |

**Net after the full day's work (morning + afternoon + evening):** 11 items closed today (1, 3, 4, 5, 6, 7, 8, 10, 11, 12, 15, 16, 17, 18, 19, 20, 21 plus 2/2a marked done after the upstream push). The remaining `--target-vps` symmetry items (#22) + first-real-spoke-deploy (#23) are the natural next steps.

---

## Known issues (current)

### Issue 1: Backrest failure-notification webhook is broken

`/opt/backrest/config/config.json` plan hooks reference `http://apprise-lcocgs4gs8ksg4g08w40ows8:8000/notify/alerts` — the old Coolify-era UUID-suffix container name. After the W1 container-name standardization on 2026-05-30, `apprise` is the stable name. **Effect:** if any future backup plan fails, the failure alert never reaches Telegram. Currently irrelevant (zero plans), but fix on next plan creation: replace `apprise-lcocgs4gs8ksg4g08w40ows8` with `apprise`.

### Issue 2: `errors.vps1.ocoron.com` predates T2-08 Part A in `audit_authelia_gates.py`

The Authelia gating audit cron flags the `errors.vps1` middleware as "unexpected" every Monday 06:00. Cosmetic (exit 0; log shows `1 GAP`); update the inventory in `scripts/audit_authelia_gates.py` when convenient.

### Issue 3: `/opt/prometheus/compose.yaml` is a stale leftover

Pre-fabrik-network-rename. Real Prometheus runs from `/opt/monitoring/compose.yaml`. Delete `/opt/prometheus/` to avoid confusion.

### Issue 4: Cloudflare API token in `/opt/fabrik/.env` was invalid — RESOLVED 2026-05-31 afternoon

Was returning `Invalid access token` after the session 2026-05-31 morning cleanup. Resolved by syncing the working token from the local site-provisioner instance's `.env` (`/opt/site-provisioner/.env` on the dev WSL) — that token had stayed in sync with Cloudflare. Pre-edit backup at `backups/.env.backup.20260531-155948`. Verified active via `https://api.cloudflare.com/client/v4/user/tokens/verify`.

### Issue 5: site-provisioner upstream `compose.yaml` still says `coolify` network — OPEN

The repo `mobasak/site-provisioner@main` declares `networks: [coolify]` in `compose.yaml`. The Docker network was renamed to `fabrik` on 2026-05-31 (commit `89879e4`). On the VPS today, `compose.yaml` was hand-patched (`sed -i s/coolify/fabrik/g`) so the running container is fine, but the next `git pull` (e.g. via `fabrik redeploy`) will overwrite it back to `coolify` and `docker compose up` will fail with "network coolify not found". Fix: push the locally-staged commit on `/opt/site-provisioner` to `mobasak/site-provisioner@main`. Awaiting user authorization.

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
- Gatus: ~28 endpoints across 15 config files (`apps/` 13 + `core/` 5 + `data/` 3 + `external/` 5 + `observability/` 4 + 1 empty `services.yaml`). Includes endpoints probing services that are no longer deployed — see "Stale/residue" section below.
- Backrest: **1 repo retained** (`b2-vps1`) + **0 plans**.
- GlitchTip: 7 project IDs retained from Coolify-era audit (captcha=65, image-broker=66, translator=67, emailgateway=68, file-api=69, file-worker=70, site-provisioner=24). Six of those projects no longer have a corresponding live service emitting events.
- Grafana: 5 Fabrik-folder dashboards (overview, databases, containers, authelia, meilisearch) + community dashboards. Every dashboard now has `$host` template variable.
- Authelia: **10 access control rules** (see § Authelia access control rules above).
- Meilisearch: 0 indexes (no consumers).
- Prometheus: **18 active targets / 15 jobs**, all up. (Was 13 jobs in Coolify-era; added 3 spoke jobs on 2026-05-31.)

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
- Prometheus `spoke_health` alert group active (SpokeDown / SpokeHighCPU / SpokeHighRAM)
- AI sysadmin proactive-check.sh emits host-tagged anomaly names (`cpu_high[vps2]`)
- **Spoke DNS resolving** at Cloudflare authoritative NS: `vps2.ocoron.com`, `*.vps2.ocoron.com`, `vps3.ocoron.com`, `*.vps3.ocoron.com` all return correct A records
- **Cloudflare API token** in `/opt/fabrik/.env` verified active
- **site-provisioner container** healthy on vps1 (alembic migrations applied, `/health` 200, CF + Postgres connectivity ok) — **but as an interim manual stand-up; not yet redeployable via `fabrik apply`** (see "site-provisioner status" earlier)
- **vps1 root `/root/.ssh/known_hosts`** now trusts `github.com`; deployer + bootstrap will keep it that way for any future host (Fix shipped today in `deployer_ssh.py` and `bootstrap-vps.sh` step 03)

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
