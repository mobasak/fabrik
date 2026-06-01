# VPS Fleet — Status Snapshot

**Last Updated:** 2026-06-01 (post-W1 + post-W9 ship — UFW active on spokes; `/opt/fabrik/.env` mirrored to private GitHub via inotify+cron; Lesson 68 captured)
**Snapshot taken:** 2026-05-31 ~14:48 UTC (live `ssh` against all three hosts)
**Hosts:** vps1 (LA, hub) · vps2 (Coventry UK, spoke) · vps3 (Coventry UK, spoke)
**Deploy model:** SSH + Docker Compose (no Coolify — removed 2026-05-30)

> Companion docs: [`vps-complete-inventory.md`](vps-complete-inventory.md) for what runs where (architectural source of truth) · [`vps-urls.md`](vps-urls.md) for how to reach things. This file is a point-in-time *health* snapshot.

---

## Fleet at a glance

| Host | Role | Public IP | Mesh IP | RAM | Disk | Containers | Uptime |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| vps1 | Hub (LA) | 172.93.160.197 | 10.99.0.1 | 11.6 Gi (3.4 Gi used) | 108 GB (28 GB / 26 %) | 29 | 16 h 24 m |
| vps2 | Spoke (Coventry UK) | 96.9.214.128 | 10.99.0.2 | 7.7 Gi (787 Mi used) | 58 GB (5.5 GB / 10 %) | 4 | 2 h 13 m |
| vps3 | Spoke (Coventry UK) | 104.128.190.151 | 10.99.0.3 | 7.7 Gi (778 Mi used) | 58 GB (5.5 GB / 10 %) | 4 | 2 h 14 m |

| Health signal | State |
| :--- | :--- |
| Wireguard mesh | ✅ both spokes handshaking in the last ~2 min |
| Cross-Atlantic mesh RTT | ✅ 133–134 ms, 0 % loss |
| Prometheus scrape targets | ✅ 18 / 18 up across 15 jobs (12 vps1 + 3 spoke job-groups) |
| Mesh-bound shared infra on vps1 (`5432, 6379, 8000, 9091, 3100`) | ✅ all 5 listening on `10.99.0.1` |
| Spoke DNS resolving | ✅ `vps2.ocoron.com`, `*.vps2`, `vps3.ocoron.com`, `*.vps3` all return correct A records |
| Cloudflare API token in `/opt/fabrik/.env` | ✅ verified active (refreshed today) |
| Authelia access-control rules | 10 (live in `/opt/authelia/config/configuration.yml`) |
| site-provisioner | ⚠ running healthy on vps1, but **interim manual stand-up** — `fabrik apply` pipeline not yet ready |
| Backrest plans | 🟡 **0 active plans by intent**; B2 bucket empty; restoring once data lands (W2 of fleet-hardening plan) |
| Credential recovery (`/opt/fabrik/.env`) | ✅ **W9 shipped 2026-06-01.** Inotify + systemd watcher (`fabrik-dr-watcher.service`) pushes every change to private `mobasak/fabrik-dr-store` within seconds; daily safety-net cron + reboot catch-up + weekly self-test. See [`docs/operations/credential-recovery.md`](../operations/credential-recovery.md). |
| Backups | 🟡 same as above |

---

## Today's significant changes (2026-05-31, full day)

### Afternoon batch

1. **Cloudflare API token refreshed** in `/opt/fabrik/.env` by syncing from the local site-provisioner's `.env` (pre-edit backup at `backups/.env.backup.20260531-155948`). Verified active via `https://api.cloudflare.com/client/v4/user/tokens/verify`.
2. **Spoke DNS records created** on Cloudflare (zone `ocoron.com`):
   - `vps2.ocoron.com` `A` 96.9.214.128
   - `*.vps2.ocoron.com` `A` 96.9.214.128
   - `vps3.ocoron.com` `A` 104.128.190.151
   - `*.vps3.ocoron.com` `A` 104.128.190.151
3. **site-provisioner interim stand-up** on vps1 — alembic migrations applied, `/health` 200, CF + Postgres connectivity verified.
4. **GitHub host-key trust** added to vps1's `/root/.ssh/known_hosts` (was missing — the Coolify removal cleanup wiped it).
5. **Permanent fixes in code:**
   - [`src/fabrik/orchestrator/deployer_ssh.py`](../../src/fabrik/orchestrator/deployer_ssh.py) — new `_extract_git_host()` + `ssh-keyscan` pre-step inside `_deploy_git()`. First-ever git-source deploy on a fresh host no longer trips on missing trust.
   - [`scripts/bootstrap/bootstrap-vps.sh`](../../scripts/bootstrap/bootstrap-vps.sh) — step_03 (after Docker install) now pre-seeds `github.com` into `/root/.ssh/known_hosts` on every new spoke.
6. **site-provisioner spec updated:** [`specs/services/site-provisioner.yaml`](../../specs/services/site-provisioner.yaml) now declares all 21 `${VAR}` references its upstream `compose.yaml` interpolates (13 env literals incl. `DATABASE_URL` placeholder + 9 from-env secrets). Was 13 → 22 declared vars.
7. **`/opt/fabrik/.env` secrets sync:** added `BING_WEBMASTER_API_KEY`; `API_KEY` overwritten with vps1's live value (preserves existing callers). Pre-edit backup at `backups/.env.backup.20260531-163701`.
8. **Postgres user `site_provisioner` password rotated** (32-char a-zA-Z0-9 via `secrets.choice`) — was unknown (not in fabrik state); now reflected in vps1's `/opt/site-provisioner/.env` and `DATABASE_URL`.

### Evening batch (residue cleanup + spoke-routing ship)

1. **Dry-run validate of `fabrik apply specs/services/site-provisioner.yaml`** — clean. State file shows 3 applicable registrars (`postgres`, `gatus`, `glitchtip`) all `status: "dry_run"`; container untouched; shape-gated registrars (`backrest`, `authelia`, `meilisearch`, `redis`, `prometheus`) correctly skipped. Pipeline is wired for site-provisioner.
2. **Residue cleanup pass** — `ContainerDown` alert silenced first (Lesson 11), 30-min sweep:
    - 6 stale CF A records deleted: `coolify`, `control`, `dns`, `fabrik-e2e-timing`, `images`, `netdata`.vps1.ocoron.com
    - 1 missing CF A record created: `provision.vps1.ocoron.com` (site-provisioner had a Traefik router but had never been in CF)
    - Authelia rule #6 trimmed from 10 hosts to 4 alive; rule #7 dropped `coolify.vps1`. Backup at `/opt/authelia/config/configuration.yml.bak.20260531-171950`. Authelia restarted via watcher in ~7 s.
    - Postgres orphan role `proxy_user` dropped.
    - Filesystem: `rm -rf /opt/prometheus`, `rm /opt/opt.code-workspace`.
    - UFW: deleted ports `6001/tcp` + `6002/tcp` (Coolify Realtime).
    - fabrik state: moved 6 orphan/test state files to `.fabrik/state/_destroyed/`.
    - Gatus: deleted 2 stale `.bak` config files.
3. **`fabrik apply --target-vps` shipped** (W-Multi M4). 5 source files + 2 test files:
    - [`src/fabrik/spec_loader.py`](../../src/fabrik/spec_loader.py) — new optional `target_vps: str | None` field on `Spec` (regex `^vps[1-9][0-9]?$`)
    - [`src/fabrik/orchestrator/context.py`](../../src/fabrik/orchestrator/context.py) — new `target_vps: str = "vps1"` on `DeploymentContext`
    - [`src/fabrik/orchestrator/__init__.py`](../../src/fabrik/orchestrator/__init__.py) — `deploy()` accepts `target_vps` kwarg (CLI > spec > "vps1"); `_provision_dns` resolves IP via `VPS_IPS = {"vps1": "172.93.160.197", "vps2": "96.9.214.128", "vps3": "104.128.190.151"}`. `target_vps` wins over the legacy `VPS_IP` env var.
    - [`src/fabrik/orchestrator/deployer_ssh.py`](../../src/fabrik/orchestrator/deployer_ssh.py) — `deploy()` env-swaps `FABRIK_VPS_SSH_HOST` around the deploy block when target_vps ≠ vps1, restoring on exit. All ~30 nested SSH calls inherit automatically.
    - [`src/fabrik/cli.py`](../../src/fabrik/cli.py) — new `--target-vps [vps1|vps2|vps3]` option on `apply`, threaded into orchestrator.
    - [`tests/orchestrator/test_deployer_ssh.py`](../../tests/orchestrator/test_deployer_ssh.py) — 3 new tests for env-swap behavior; 3 fixes for pre-existing-test drift (rename + ssh-keyscan).
    - [`tests/orchestrator/test_integration.py`](../../tests/orchestrator/test_integration.py) — DNS test updated for new VPS_IPS map precedence.
    - **103/103** deployer/spec tests pass.

---

## site-provisioner status

**Running:** ✅ container `site-provisioner` on vps1, healthy. Migrations applied. CF + DB connectivity ok. `/health` returns 200.

**But not pipeline-ready.** This is an interim manual stand-up done specifically to unblock today's spoke DNS work. Gaps remaining:

| Gap | Today's mitigation | What's still needed |
| :--- | :--- | :--- |
| Upstream `mobasak/site-provisioner@main` `compose.yaml` still references the legacy `coolify` Docker network | Hand-patched on the VPS only; commit also staged locally on the dev WSL at `/opt/site-provisioner/compose.yaml` | Push the staged commit to `main` — awaiting user authorization |
| Spec was missing 3 secrets + 5 env literals | Updated, parses cleanly | One clean `fabrik apply` end-to-end after the push above to confirm |
| Postgres user password not in fabrik state | Manually set + reflected in live `.env`; `DATABASE_URL` works | The postgres registrar will overwrite this cleanly on the next full `fabrik apply` cycle |

**Do not** `fabrik redeploy site-provisioner` until the upstream `compose.yaml` push lands — the git pull would overwrite the on-VPS hand-patch back to `coolify` and `docker compose up` would fail with "network coolify not found". To restart the running instance safely today:

```bash
ssh vps "cd /opt/site-provisioner && sudo docker compose up -d"
```

---

## Containers — per host

### vps1 (29 running)

```text
site-provisioner       healthy  (NEW today — interim manual; see § site-provisioner status)
authelia               healthy
glitchtip-web          running  (bound to 10.99.0.1:8000 for spoke ingest)
glitchtip-worker       running
redis-main             healthy  (bound to 10.99.0.1:6379)
postgres-main          healthy  (bound to 10.99.0.1:5432)
postgres-exporter      healthy
redis-exporter         running
loki                   healthy  (bound to 10.99.0.1:3100)
promtail               running
prometheus             healthy
alertmanager           healthy
grafana                healthy
gatus                  running
cadvisor               healthy
node-exporter          running
pushgateway            healthy
apprise                healthy
backrest               running  (0 plans by design)
n8n                    running
gotenberg              running
browserless            running
meilisearch            running
traefik                running
ocoron-com-nginx-1     running    (WP tenant)
ocoron-com-wordpress-1 running    (WP tenant)
ocoron-com-db-1        healthy    (WP tenant — MariaDB)
ocoron-com-redis-1     healthy    (WP tenant)
ocoron-com-backup-1    running    (WP tenant — nightly mysqldump sidecar)
```

### vps2 (4 running)

```text
traefik                running  (public 80+443; authelia-vps1@file middleware ready)
node-exporter          running  (10.99.0.2:9100)
cadvisor               healthy  (10.99.0.2:8080)
promtail               running  (10.99.0.2:9080 → pushes to 10.99.0.1:3100)
```

### vps3 (4 running)

```text
traefik                running
node-exporter          running  (10.99.0.3:9100)
cadvisor               healthy  (10.99.0.3:8080)
promtail               running  (10.99.0.3:9080)
```

---

## Network posture (per host)

### vps1

| Layer | Status |
| :--- | :--- |
| SSH | ✅ `ozgur` user, Ed25519 key only, root disabled, password disabled, fail2ban active |
| UFW | ✅ active; 22 / 80 / 443 / 1194 ALLOW; 51820/udp ALLOW; 8000 DENY (stale Coolify comment) |
| Mesh-only ports | ✅ `10.99.0.1:5432,6379,8000,9091,3100` listening on wg0 only |
| DOCKER-USER iptables chain | ✅ accepts `wg0`, drops mesh-only port list from public iface |
| Traefik dashboard | ✅ `127.0.0.1:8080` localhost only |
| Authelia | ✅ forward-auth on `*.vps1.ocoron.com` admin dashboards; TOTP 2FA; Redis-backed sessions (`redis-main:6379/3`) |
| M2M auth | 🟡 pattern intact (`X-Internal-Token` + `SERVICE_INTERNAL_SECRET_KEY`); **no live service consuming it** today — the 7 microservices that used it are not currently deployed |
| GitHub host-key trust for root SSH | ✅ added today (`/root/.ssh/known_hosts`) — deployer + bootstrap now keep this in place automatically |
| Resource limits | ✅ enforced via compose `deploy.resources.limits.memory` on every service; gate validates |

### vps2 / vps3 (identical posture)

**Last probe report:** [`probe-reports/infra-probe-2026-05-31T23-07Z.yaml`](probe-reports/infra-probe-2026-05-31T23-07Z.yaml)

| Layer | Status |
| :--- | :--- |
| SSH | ✅ matches vps1 (no root, no password, `ozgur` key only) — Lesson 65 takeaway |
| UFW | ✅ installed (`dpkg ii`) + active; 8 ALLOW rules (22/80/443/51820 IPv4+IPv6); default policy `deny (incoming) / allow (outgoing) / deny (routed)` — shipped by W1 2026-05-31 evening; pre-W1 was `rc` state (Lesson 68) |
| Mesh-only ports | ✅ `10.99.0.<N>:9100,8080,9080` listening on wg0 only; mesh-only port DROP verified via tcpdump (SYN arrives, no SYN-ACK) |
| DOCKER-USER chain | ✅ applied by bootstrap step_10; unchanged by W1 |
| Traefik | ✅ public 80 + 443, `authelia-vps1@file` middleware in `dynamic/authelia.yml` |
| Tenants | None yet (DNS ready) |

---

## Observability snapshot

### Prometheus — 18 / 18 targets up across 15 jobs

vps1-local (12 jobs / 12 targets — verified against `/api/v1/targets`): `alertmanager`, `authelia`, `cadvisor`, `gatus`, `grafana`, `loki`, `meilisearch`, `node`, `postgres`, `prometheus`, `pushgateway`, `redis`.

Spokes (3 jobs / 6 targets): `node-spokes` (2), `cadvisor-spokes` (2), `promtail-spokes` (2).

Not scraped: `traefik` (no metrics scrape job — health observed via Gatus + Loki), `glitchtip-web` (django-prometheus not bundled). Every active series carries a `host` label (`vps1`, `vps2`, or `vps3`). Reload: `ssh vps "sudo docker kill -s HUP prometheus"`.

### Retention

| Datastore | Retention | Configured via |
| :--- | :--- | :--- |
| Prometheus | 30 d or 5 GB | `--storage.tsdb.retention.time=30d --storage.tsdb.retention.size=5GB` |
| Loki | 7 d (168 h) | `limits_config.retention_period: 168h` + compactor enabled |
| Alertmanager | minutes | — |

### Loki — multi-host ingest

- Bound to `10.99.0.1:3100` on vps1 (mesh ingest).
- Both spokes' promtail successfully pushing — `host` label values `["vps1","vps2","vps3"]` visible in Grafana's Loki explore.

### Grafana

- 5 Fabrik-folder dashboards (overview, databases, containers, authelia, meilisearch) — all carry a `$host` template variable (regex `/^vps/`) so you can scope spoke vs hub.
- Datasources provisioned from `/opt/monitoring/configs/grafana/provisioning/datasources/fabrik.yaml`.

### Alerting

- **Alertmanager → Apprise → Telegram** for vps1 alerts.
- **`spoke_health` rule group active** — `SpokeDown`, `SpokeHighCPU`, `SpokeHighRAM`. Group joins use `on(host)` to avoid the many-to-many trap that surfaced when the `host` label was added.
- **Discipline (Lesson 11):** silence the `ContainerDown` rule before any planned op that takes containers down > 2 min, or Telegram floods.

### GlitchTip

- Public UI: `https://errors.vps1.ocoron.com` (Authelia 2FA).
- Internal alias for SDKs: `http://glitchtip-web:8000/<project_id>` (Docker DNS on `fabrik` network).
- Mesh ingest for spoke tenants: `http://10.99.0.1:8000/<project_id>` (bound today).
- Storage: `glitchtip` DB on `postgres-main`; events retained 90 d.
- Project IDs unchanged from Coolify-era audit (captcha 65, image-broker 66, translator 67, emailgateway 68, file-api 69, file-worker 70, site-provisioner 24).

### Gatus

- Status page: `https://status.vps1.ocoron.com` (public, no auth).
- Config tree at `/opt/monitoring/configs/gatus/` (volume-mounted, auto-reloads ~30 s).
- Stable container names everywhere — no more UUID-alias maintenance.
- Alerter: native `failure-threshold: 3`, `success-threshold: 2`, `send-on-resolved: true` → Apprise → Telegram.

---

## Authelia — 10 access-control rules (live, verified via `yaml.safe_load`)

| # | Policy | Domain(s) | Resources |
| :--- | :--- | :--- | :--- |
| 1 | bypass | `ocoron.com` | (all) |
| 2 | bypass | `www.ocoron.com` | (all) |
| 3 | bypass | `wp-test.vps1.ocoron.com` | (all) |
| 4 | bypass | `status.vps1.ocoron.com` | (all) |
| 5 | bypass | `*.vps1.ocoron.com` | `^/health$`, `^/healthz$`, `^/metrics$`, `^/api/health$` |
| 6 | bypass | `pdf`, `browser`, `search`, `captcha`, `proxy`, `translator`, `files-api`, `emailgateway`, `dns`, **`errors`**`.vps1.ocoron.com` (10 hosts) | (all) |
| 7 | bypass | `coolify.vps1.ocoron.com`, `monitor.vps1.ocoron.com` | `^/api/` only |
| 8 | bypass | `images.vps1.ocoron.com` | `^/api/` only (paired with #9) |
| 9 | two_factor | `images.vps1.ocoron.com` | (all) |
| 10 | two_factor | `*.vps1.ocoron.com` | (catch-all) |

**Cosmetic-but-noteworthy:**

- Rule #6 includes `errors.vps1.ocoron.com` — a prior session noted this was removed by T2-08 Part A; that change is not reflected live, so `errors.vps1` is reaching GlitchTip without Authelia today.
- Rule #6 lists 5 hosts (`captcha`, `proxy`, `translator`, `files-api`, `emailgateway`) for services that **don't exist** today. Bypass is dormant — harmless until those domains route somewhere.
- Rule #6 lists `dns.vps1.ocoron.com` — stale DNS alias, no router.
- Rule #7 still bypasses `coolify.vps1.ocoron.com` — fully stale (Coolify removed 2026-05-30).
- `provision.vps1.ocoron.com` (site-provisioner) is NOT in this list — it's protected at the Traefik layer by IP allowlist + at the app layer by bearer `API_KEY`, never reaches Authelia.

**Critical:** Authelia **exits** on SIGHUP — it does NOT hot-reload. The systemd watcher `authelia-config-sync.service` saves config to the named volume and `docker restart authelia` automatically on edit. Manual restart: `ssh vps "sudo docker restart authelia"`.

**Cross-host SSO for spoke admin dashboards** (when they exist): spoke Traefik uses the `authelia-vps1@file` middleware to forward-auth via mesh (`http://10.99.0.1:9091/api/verify`). Cookie-domain plumbing for true SSO across hosts is W-Multi M7 backlog.

---

## Backups

**Live state:** Backrest config has **1 repo retained + 0 plans**. B2 bucket `vps1-ocoron-backups` is empty (preserved for reuse). Intentional, post-2026-05-31 cleanup.

| Item | Detail |
| :--- | :--- |
| Repo ID | `b2-vps1` |
| Repo URI | `s3:https://s3.us-west-004.backblazeb2.com/vps1-ocoron-backups` |
| Repo flags | `--compression=auto` |
| Plans | 0 |
| Container | `backrest` (running, 512 MB limit) |
| Off-VPS creds in `/opt/fabrik/.env` | `BACKREST_RESTIC_PASSWORD` ✓, `B2_KEY_ID` ✓, `B2_APPLICATION_KEY` ✓ |

Closing the "credentials only on vps1" DR weakness means the dev WSL can stand backups back up from scratch.

**Credential off-site mirror (W9 shipped 2026-06-01).** The dev WSL was itself a single point of failure until W9: `/opt/fabrik/.env` (including the irrecoverable `BACKREST_RESTIC_PASSWORD`) existed only on disk there. Now mirrored to **`mobasak/fabrik-dr-store`** (private GitHub repo) within seconds of every change via `fabrik-dr-watcher.service` (inotify) + daily safety-net cron + `@reboot` catch-up + weekly recovery self-test. One-command recovery on a fresh WSL: `gh repo clone mobasak/fabrik-dr-store && sudo cp fabrik-dr-store/env/latest /opt/fabrik/.env`. Full runbook: [`docs/operations/credential-recovery.md`](../operations/credential-recovery.md).

When backups are reconfigured:

- Plans to recreate: `postgres-dumps` (`/opt/backups/pg_dump_*.sql`), `docker-volumes` (`/var/lib/docker/volumes/`), `opt-configs` (`/opt/<svc>/{compose.yaml,.env}`).
- Failure-hook URL: `http://apprise:8000/notify/<tag>` (the old `apprise-<uuid>:8000` hostname is broken; Issue 1 in inventory).
- Schedule postgres-dumps AFTER the host pg_dump cron, not concurrent (44 % race-condition failures previously).
- Spoke backups: defer until vps2/vps3 actually hold non-replicated data.

---

## Recent maintenance & lessons (active)

| # | Source | Rule |
| :--- | :--- | :--- |
| 11 | Lesson 11 | Silence `ContainerDown` before any planned downtime > 2 min on vps1, otherwise Telegram floods |
| 22 | Lesson 22 | Container names are stable across all hosts (`container_name:` in every compose) — no UUID-alias maintenance |
| 31 | Lesson 31 | Env-var verification on distroless images uses `docker inspect`, never `docker exec printenv` |
| 36 | Lesson 36 | git-source `fabrik redeploy` pulls from the GitHub remote, not your local `/opt/`. Push first, then redeploy. |
| 50 | Lesson 50 | `SourceType.LOCAL` exists in 13 production specs — the SSH deployer handles it explicitly (was being silently coerced to TEMPLATE under Coolify) |
| 62 | Lesson 62 | Coolify had 3 deployment types with different fix paths; SSH deployer has 1 (compose). Confirmed simplification. |
| 64 | Lesson 64 | Live-state probes are authoritative — re-verify on the actual VPS after implementation, don't trust paper-correct |
| 65 | Lesson 65 | bootstrap-vps.sh bugs from initial vps2/vps3 deploys — create sudoer first, scan multiple SSH key candidates, no process substitution over SSH |
| — | Today | Spec-vs-upstream `compose.yaml` interpolation: every `${VAR}` in the upstream compose must be declared in the spec's `env` or `secrets.from_env` — otherwise `docker compose up` fails before the container starts |
| — | Today | First-ever git-source deploy on a fresh host needs the git host in `/root/.ssh/known_hosts`. Deployer + bootstrap now keep this in place; not something to handle manually anymore. |

Full log: [`docs/LESSONS_LEARNT.md`](../LESSONS_LEARNT.md).

---

## Maintenance commands

```bash
# Full health + residue audit
cd /opt/fabrik && python3 scripts/vps_sync.py --verify

# After VPS reboot — reapply memory limits
ssh vps "bash /opt/fabrik/scripts/vps_apply_limits.sh"

# Restart Authelia after config edit (NEVER SIGHUP)
ssh vps "sudo docker restart authelia"

# Reload Prometheus config
ssh vps "sudo docker kill -s HUP prometheus"

# Spoke health snapshot
for host in vps vps2 vps3; do
  echo "=== $host ==="
  ssh "$host" 'sudo docker ps --format "{{.Names}}\t{{.Status}}" | head -10; uptime; df -h / | tail -1'
done

# Weekly disk cleanup per host
ssh vps "sudo docker image prune -f && sudo docker builder prune -f"
```

---

## Known issues / residue (active)

After the evening cleanup batch, the active list is short. The struck-through rows are kept for one snapshot so a reader sees what was just fixed.

| # | Issue | Impact | Fix path |
| :--- | :--- | :--- | :--- |
| 1 | Backrest failure-notification hook references the old Coolify-era apprise UUID hostname | Cosmetic until backup plans exist; backup-failure alerts wouldn't reach Telegram | Fix on next plan creation: replace `apprise-<uuid>` with `apprise` |
| 2 | `errors.vps1.ocoron.com` remains in Authelia bypass rule #6 (intentional — GlitchTip is the cross-tenant error UI) | GlitchTip UI is reachable without 2FA | Accepted as intentional; move to `two_factor` if/when this changes |
| ~~3~~ | ~~`/opt/prometheus/` on vps1~~ | **RESOLVED** evening | `rm -rf` |
| ~~4~~ | ~~site-provisioner upstream `compose.yaml` says `coolify` network~~ | **RESOLVED** | `fa32d61` pushed to `mobasak/site-provisioner@main` |
| ~~5~~ | ~~Stale UFW 6001, 6002 (Coolify Realtime)~~ | **RESOLVED** evening | `ufw delete allow {6001,6002}/tcp`; 8000 DENY rule kept as belt-and-suspenders |
| ~~6~~ | ~~6 stale `*.vps1` DNS A records~~ | **RESOLVED** evening | Deleted via CF API |
| ~~7~~ | ~~Authelia rule #6 lists 5 dead microservice domains + `dns`~~ | **RESOLVED** evening | Trimmed to 4 alive (`pdf`, `browser`, `search`, `errors`) |
| ~~8~~ | ~~Authelia rule #7 bypasses `coolify.vps1`~~ | **RESOLVED** evening | Dropped; rule #7 now only `monitor.vps1` |
| ~~9~~ | ~~Orphan Postgres role `proxy_user`~~ | **RESOLVED** evening | `DROP USER` done |
| ~~10~~ | ~~Stray `/opt/opt.code-workspace`~~ | **RESOLVED** evening | Deleted |
| ~~11~~ | ~~6 orphan fabrik state files~~ | **RESOLVED** evening | Moved to `.fabrik/state/_destroyed/` |
| ~~12~~ | ~~2 stale `.bak` Gatus configs~~ | **RESOLVED** evening | Deleted |

(Issue 4 — Cloudflare token invalid — from earlier docs is RESOLVED. The struck-through rows will drop from this table in the next snapshot.)

---

## Pending work (high-level)

The full table lives in [`vps-complete-inventory.md` § Pending actions](vps-complete-inventory.md). Current top of stack after today's evening batch:

1. **`fabrik destroy --target-vps` + `fabrik redeploy --target-vps`** — symmetry with `apply --target-vps` (W-Multi M4). Same env-swap pattern; ~5–10 min each.
2. **First real spoke deploy** — tiny test spec with `target_vps: vps2` and `domain: <svc>.vps2.ocoron.com` to exercise spoke Traefik's Let's Encrypt issuance for the first time.
3. **Backrest plan re-create** (when data lands worth backing up).
4. **Authelia rules for spoke admin dashboards** (when one exists).
5. **Spoke backups** (depends on #3 + actual tenant data).

---

## Cross-references

- Architectural inventory: [`vps-complete-inventory.md`](vps-complete-inventory.md)
- Service URLs: [`vps-urls.md`](vps-urls.md)
- Deployment mechanics: `docs/operations/deployment.md`
- Disaster recovery: `docs/operations/disaster-recovery.md`
- AI sysadmin reference: [`vps-ai-sysadmin.md`](vps-ai-sysadmin.md)
- Bootstrap a new spoke: [`vps-bootstrap-plan.md`](vps-bootstrap-plan.md)
- Residue policy: [`vps-residue-policy.md`](vps-residue-policy.md)
- Lessons learnt: [`../LESSONS_LEARNT.md`](../LESSONS_LEARNT.md)
