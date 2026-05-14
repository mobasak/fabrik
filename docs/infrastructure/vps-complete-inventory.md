# VPS Complete Service Inventory

**Last Updated:** 2026-05-10 19:06 UTC
**VPS:** vps1.ocoron.com (172.93.160.197) — Ubuntu 24.04 LTS, 6 vCores (x86_64), 11GB RAM, 108GB disk
**Coolify:** v4.0.0-beta.459 — fully patched (CVEs fixed in beta.451+)
**Total containers:** 40 running

---

## Re-verify This Document

```bash
ssh vps "sudo docker ps --format '{{.Names}}\t{{.Status}}' | sort"
ssh vps "sudo docker inspect \$(sudo docker ps -q) --format '{{.Name}} {{.HostConfig.Memory}}' | sed 's|/||' | sort"
ssh vps "sudo ufw status numbered"
ssh vps "sudo docker exec traefik wget -qO- http://localhost:8080/api/http/middlewares | python3 -m json.tool"
ssh vps "sudo cat /var/lib/docker/volumes/hks48k8sg8o4co4co08co00o_authelia-config/_data/configuration.yml"
cd /opt/fabrik && python3 scripts/vps_sync.py --verify
```

---

## Network Architecture

```
Internet
    │
    ├─ 443/tcp ──► Traefik (coolify-proxy)
    │                  ├─► authelia-forward@docker + gzip@docker (admin UIs)
    │                  ├─► gzip@docker only (API services — app-layer X-Internal-Token)
    │                  ├─► coolify.vps1.ocoron.com    Coolify UI
    │                  ├─► monitor / netdata / auto / errors / backup / notify / auth
    │                  ├─► proxy/captcha/images/translator/emailgateway  X-Internal-Token
    │                  ├─► files-api                  Supabase Bearer JWT
    │                  ├─► provision                  IP allowlist
    │                  └─► ocoron.com / www            WordPress
    ├─ 80/tcp ───► Traefik → HTTPS redirect
    ├─ 22/tcp ───► SSH (Ed25519 key, root disabled)
    ├─ 1194/tcp ─► OpenVPN (kernel service)
    ├─ 6001-6002 ► Coolify Realtime / Soketi (Coolify UI live logs)
    └─ 8000/tcp ─► UFW DENY
```

### Docker Networks
| Network | Subnet | Purpose |
|---|---|---|
| `coolify` | 10.0.1.0/24 | All Coolify-managed containers |
| Host | 172.93.160.197 | Traefik on 80/443 only |

---

## Traefik Configuration

**Version:** v3.6 | **Config:** `/data/coolify/proxy/` | **Dynamic:** `/data/coolify/proxy/dynamic/`
**Gzip:** `/data/coolify/proxy/dynamic/gzip.yaml` (hot-reload)
**SSL:** Let's Encrypt HTTP challenge | `acme.json`: `/data/coolify/proxy/acme.json`

### Middlewares
<!-- AUTO:traefik_middlewares -->
| Middleware | Type | Purpose |
|---|---|---|
| `authelia-forward@docker` | forwardauth | → `http://authelia:9091/api/authz/forward-auth` |
| `gzip@docker` | compress | All routes — scaffold wires automatically |
| `redirect-to-https@docker` | redirectscheme | HTTP → HTTPS |
| `site-provisioner-ipallowlist@docker` | ipallowlist | VPS + internal Docker ranges |
| `ocoron-com-rate-limit@docker` | ratelimit | WordPress rate limiting |
| `ocoron-com-block-xmlrpc@docker` | replacepathregex | WordPress xmlrpc block |
| `ocoron-com-www-redirect@docker` | redirectregex | www → non-www |
<!-- /AUTO -->

### Traefik Label Patterns (by service type)
| Service type | Middlewares | Source |
|---|---|---|
| Admin dashboard | `authelia-forward@docker,gzip@docker` | scaffold emits |
| API service (X-Internal-Token) | `gzip@docker` | scaffold emits |
| Public service | none | scaffold emits |

---

## Firewall (UFW)

<!-- AUTO:ufw_rules -->
| Rule | Notes |
|---|---|
| `22/tcp                     ALLOW IN    Anywhere                   # SSH` | |
| `80/tcp                     ALLOW IN    Anywhere                   # HTTP` | |
| `443/tcp                    ALLOW IN    Anywhere                   # HTTPS+OpenVPN` | |
| `1194/tcp                   ALLOW IN    Anywhere` | |
| `6001/tcp                   ALLOW IN    Anywhere` | |
| `6002/tcp                   ALLOW IN    Anywhere` | |
| `8000/tcp                   DENY IN     Anywhere                   # Coolify raw port — use coolify.vps1.ocoron.com instead` | |
| `22/tcp (v6)                ALLOW IN    Anywhere (v6)              # SSH` | |
| `80/tcp (v6)                ALLOW IN    Anywhere (v6)              # HTTP` | |
| `443/tcp (v6)               ALLOW IN    Anywhere (v6)              # HTTPS+OpenVPN` | |
| `1194/tcp (v6)              ALLOW IN    Anywhere (v6)` | |
| `6001/tcp (v6)              ALLOW IN    Anywhere (v6)` | |
| `6002/tcp (v6)              ALLOW IN    Anywhere (v6)` | |
| `8000/tcp (v6)              DENY IN     Anywhere (v6)              # Coolify raw port — use coolify.vps1.ocoron.com instead` | |
<!-- /AUTO -->

---

## Authelia Configuration

**Container:** `authelia-hks48k8sg8o4co4co08co00o`
**Config:** `/var/lib/docker/volumes/hks48k8sg8o4co4co08co00o_authelia-config/_data/configuration.yml`
**Sessions:** `redis-main:6379` DB index 3 — survives restarts
**TOTP:** `ocoron.com`, 30s period
**Storage:** SQLite `/config/db.sqlite3`

### Access Control (8 rules — live as of 2026-05-07)
| Domain | Policy | Path/note |
|---|---|---|
| `ocoron.com`, `www.ocoron.com` | bypass | all |
| `wp-test.vps1.ocoron.com`, `status.vps1.ocoron.com` | bypass | all |
| `*.vps1.ocoron.com` | bypass | `/health`, `/healthz`, `/metrics`, `/api/health` |
| 11 API service domains | bypass | all (app-layer auth: X-Internal-Token) |
| `coolify.vps1.ocoron.com`, `monitor.vps1.ocoron.com` | bypass | `^/api/` only |
| `*.vps1.ocoron.com` | two_factor | all other paths |

**CRITICAL:** Authelia exits on SIGHUP — does NOT hot-reload.
After any config change: `ssh vps "sudo docker restart authelia-hks48k8sg8o4co4co08co00o"`

---

## M2M Authentication Architecture

| Component | Value |
|---|---|
| Header | `X-Internal-Token` |
| Env var | `SERVICE_INTERNAL_SECRET_KEY` (one shared key) |
| Key location | `/opt/fabrik/.env` |
| Python import | `from app.internal_auth import require_internal_token` (if `uvicorn app.main:app`) |
| Python import | `from internal_auth import require_internal_token` (if `uvicorn api:app` from root) |
| Node.js | `src/internal_auth.js` → `requireInternalToken` via `timingSafeEqual` |
| Validation | constant-time always |
| `/metrics` | Authelia-bypassed (`*.vps1.ocoron.com → /metrics`); no auth needed for Prometheus scraping |

**Scaffold auto-emits:** `internal_auth.py` (Python) + `src/internal_auth.js` (Node.js) + `metrics.py`
**Deployed:** captcha, image-broker, translator, proxy, emailgateway
**Pre-placed:** 35 projects under `/opt`

---

## Observability Architecture

### Prometheus
- **Compose:** `/opt/prometheus/compose.yaml` (standalone — outside Coolify service management)
- **Config:** `/opt/monitoring/configs/prometheus/prometheus.yml`
- **Rules:** `/opt/monitoring/configs/prometheus/rules/alerts.yml` (10 rules)
- **Retention:** `--storage.tsdb.retention.time=30d --storage.tsdb.retention.size=5GB`
- **Reload:** `ssh vps "cd /opt/prometheus && sudo docker compose restart"`
- **Scrape jobs:** prometheus, node, cadvisor, loki, netdata, alertmanager, gatus, fabrik-services (30s, targets TBD)

### Loki
- **Config:** `/opt/monitoring/configs/loki/loki-config.yaml`
- **Retention:** `limits_config.retention_period: 168h` (7 days); compactor enabled
- **Reload:** `ssh vps "sudo docker restart loki-..."`

### Promtail (log shipping)
- **Config:** `/opt/monitoring/configs/promtail/promtail-config.yaml`
- **Source:** `/var/lib/docker/containers/*/*log` (all Docker JSON logs)
- **Pipeline:** JSON parse → extract `container_name` → drop noise → label → ship to Loki
- **Noise filter (drop stage):** `coolify-db`, `coolify-redis`, `coolify-realtime`, `coolify-sentinel`, `ocoron-com-backup-1`
- **Reload:** `sudo docker restart promtail-w0000ckgsgg048w0848okk08` after config edit

### Grafana (dashboards + provisioning)
- **Bind mount:** `/opt/monitoring/configs/grafana/provisioning -> /etc/grafana/provisioning:ro` (added to Coolify service compose)
- **Datasources file:** `/opt/monitoring/configs/grafana/provisioning/datasources/fabrik.yaml`
- **Provisioned datasources:** Prometheus (default, `http://prometheus:9090`), Loki (`http://loki:3100`)
- **Why bind mount:** Grafana reads provisioning from `/etc/grafana/provisioning`, NOT from the data volume `/var/lib/grafana`. Without this mount, datasources only exist in SQLite (`grafana.db`) and are lost on volume wipe or fresh redeploy.

### Alertmanager
- **Config:** `/opt/monitoring/configs/alertmanager/alertmanager.yml`
- **Receiver:** Telegram (native `telegram_configs`)
- **grouping:** `group_by: [alertname, container]`; `repeat_interval: 4h`; critical: 30m
- **Reload:** `sudo docker restart alertmanager-...`

### Netdata
- **Retention:** `NETDATA_DBENGINE_DISK_SPACE_MB=512`, `NETDATA_DBENGINE_RETENTION_DAYS=7`
- **Was:** unbounded — grew to 2.2GB before fixed 2026-05-07

### Business Metrics (/metrics endpoint)
- `prometheus-client>=0.21.0` now in scaffold `requirements.txt`
- `metrics.py` emitted by scaffold (REQUEST_COUNT, ERROR_COUNT, PROCESSING_COUNT, ACTIVE_JOBS)
- `/metrics` mounted in scaffolded `main.py` automatically
- Prometheus `fabrik-services` job ready — uncomment targets as services add `/metrics`
- To add to existing service: add `prometheus-client`, copy `metrics.py`, mount `/metrics`, uncomment in `prometheus.yml`

### Error Reporting (GlitchTip) — Live since 2026-05-08

**Architecture:**
- GlitchTip 6.1.5 deployed via Coolify (web + worker containers, 512MB limits each)
- Storage: `glitchtip` database on shared `postgres-main` (PostgreSQL 16.11)
- Public URL: `https://errors.vps1.ocoron.com` (Authelia-protected)
- Internal SDK ingestion: `http://glitchtip-web:8000` (stable Docker DNS alias on `coolify` network)
- DSN host rewrite: provisioner replaces public host with internal alias so SDK events bypass Authelia/TLS

**Scaffold integration (auto-emitted, every project):**
- `python-api` / `file-worker`: `src/{pkg}/glitchtip_init.py` — `init_glitchtip()` with FastApiIntegration; wired BEFORE `app = FastAPI()`. Dependency: `sentry-sdk[fastapi]>=2.18`.
- `node-api` / `file-api`: `src/glitchtip_init.js` — `Sentry.init()` from `@sentry/node`; wired via `require('./glitchtip_init')` BEFORE `http.createServer`. Dependency: `@sentry/node`.
- Both: zero-overhead no-op when `GLITCHTIP_DSN` env var is unset/empty. ImportError-safe (graceful no-op if SDK package missing).

**Provisioner script:** `scripts/provision_glitchtip_project.sh <name> [--platform <p>] [--coolify-uuid <uuid>]`
- Idempotent (GET first, POST on 404, refetch DSN on existing)
- WSL-aware (auto re-execs on VPS via SSH with creds from `/opt/fabrik/.env`)
- Optional `--coolify-uuid` flag pushes DSN straight to Coolify service env

**Capture discipline (enforced by `.windsurf/rules/55-observability.md § Error Reporting`):**
- Unhandled exceptions auto-report to GlitchTip when `GLITCHTIP_DSN` is set — do nothing extra
- DO NOT call `logger.exception()` with full tracebacks for unhandled errors (duplicates GlitchTip event AND wastes Loki retention)
- Use `sentry_sdk.capture_exception(e)` (Python) / `Sentry.captureException(e)` (Node) ONLY for caught-then-rethrown control flow

**Runbook:** `docs/infrastructure/glitchtip-sdk-integration-setup.md`

---

## Complete Container Inventory

<!-- AUTO:container_inventory -->
| Container | Status | Memory limit |
|---|---|---|
| `alertmanager-zw4swgkwk0s4s8kg048gw80o` | ✅ Up 2 weeks (healthy) | 256m |
| `apprise-lcocgs4gs8ksg4g08w40ows8` | ✅ Up 2 weeks (healthy) | 512m |
| `authelia-hks48k8sg8o4co4co08co00o` | ✅ Up 45 hours (healthy) | — |
| `backrest-l48000k44wc4gk8os88s8k0c` | ✅ Up 7 days | 512m |
| `bs0wo48k4gwo440gcowscoc8-211159651770` | ✅ Up 46 hours (healthy) | 512m |
| `cadvisor-r08sog4gwws88og048ows448` | ✅ Up 3 days (healthy) | — |
| `captcha-j8gg4ggskkossc4gkwowk4os-191229303949` | ✅ Up 2 days (healthy) | — |
| `coolify` | ✅ Up 2 weeks (healthy) | — |
| `coolify-db` | ✅ Up 2 weeks (healthy) | — |
| `coolify-proxy` | ✅ Up 2 weeks (healthy) | — |
| `coolify-realtime` | ✅ Up 2 weeks (healthy) | — |
| `coolify-redis` | ✅ Up 2 weeks (healthy) | — |
| `coolify-sentinel` | ✅ Up 7 minutes (healthy) | — |
| `e04k4sco44ow04ccc0o0k00k-210433823748` | ✅ Up 46 hours (healthy) | 512m |
| `emailgateway-w4oocckkwko8kowggsw8sogc-192134804476` | ✅ Up 2 days (healthy) | — |
| `fabrik-proxy-zsccsksoc8sssc8k00sgcc08-135717735508` | ✅ Up 5 hours (healthy) | — |
| `file-api-bsswwg4kg480c000gksw004k-192212486944` | ✅ Up 2 days (healthy) | — |
| `file-worker-nwcckwggw0o0g40gwskk8kk8-191323299257` | ✅ Up 2 days (healthy) | 512m |
| `gatus-v8s4cokcwg0co4w8okkccc0w` | ✅ Up 4 days | 256m |
| `glitchtip-web-z00kkck8c8cwo800kk440csk` | ✅ Up 2 weeks | 512m |
| `glitchtip-worker-msgo0sg8gsgo4w4sscckc84g` | ✅ Up 2 weeks | 512m |
| `grafana-loc484owg8gsw04owo0go8kc` | ✅ Up 45 hours (healthy) | — |
| `image-broker-zo4ggs4g880skwkocwwkscgk-191233590054` | ✅ Up 2 days (healthy) | — |
| `loki-r48swckog008wosgwcs4g0g0` | ✅ Up 2 weeks (healthy) | 512m |
| `n8n-s8gwccsws0ccssw0wwgwsoks` | ✅ Up 2 weeks (healthy) | 2g |
| `netdata-kk4kcw4csksc48848go4o0wo` | ✅ Up 3 days (healthy) | — |
| `node-exporter-doc8c8gkcgs88s8ckggw84o4` | ✅ Up 2 weeks | 128m |
| `ocoron-com-backup-1` | ✅ Up 2 weeks | — |
| `ocoron-com-db-1` | ✅ Up 2 weeks (healthy) | 1g |
| `ocoron-com-nginx-1` | ✅ Up 2 weeks | 256m |
| `ocoron-com-redis-1` | ✅ Up 2 weeks (healthy) | 256m |
| `ocoron-com-wordpress-1` | ✅ Up 2 weeks | 512m |
| `postgres-exporter` | ✅ Up 46 hours (healthy) | — |
| `postgres-main-l0k4gk0kggc8okcwk0s4c8s8` | ✅ Up 2 weeks (healthy) | 2g |
| `prometheus` | ✅ Up 3 days (healthy) | — |
| `promtail-w0000ckgsgg048w0848okk08` | ✅ Up 3 days | 128m |
| `redis-exporter` | ✅ Up 44 hours | — |
| `redis-main` | ✅ Up 2 weeks (healthy) | 512m |
| `rkock48gg4044kggwkwocwsc` | ✅ Up 1 second | — |
| `site-provisioner-qokoksogwsk0c04gcs4swwgs-200230906082` | ✅ Up 47 hours (healthy) | — |
| `traefik` | ✅ Up 2 weeks | 256m |
| `translator-kgws0s4cscsosw8gg848cwgw-191255149559` | ✅ Up 2 days (healthy) | — |
| `vckgs8c00o40o884k48cgow8-210454442421` | ✅ Up 46 hours | 2g |
<!-- /AUTO -->

---

## Gatus Monitoring Architecture

**Config dir:** `/opt/monitoring/configs/gatus/` (volume-mounted at `/config` in container)
**Auto-reload:** Gatus watches config dir, reloads within 30s of any file change — no container restart needed.
**Alert chain:** Gatus → custom alerter → Apprise (`http://apprise:8000/notify/alerts`) → Telegram + others
**Alerting defaults:** `failure-threshold: 3`, `success-threshold: 2`, `send-on-resolved: true`
**Storage:** `type: memory` (no persistence; status dashboard only)
**Connectivity check:** `1.1.1.1:53` (external DNS — VPS network health signal)

### Config file structure
```
/opt/monitoring/configs/gatus/
├── _base.yaml          # Global: alerting, storage, UI, connectivity
├── core/infra.yaml     # traefik, authelia, coolify, n8n, apprise
├── data/databases.yaml # postgres-main, redis-main, meilisearch
├── observability/stack.yaml  # grafana, prometheus, alertmanager, loki, netdata
├── apps/               # Per-service files (17 files, one per service)
├── services/services.yaml    # gotenberg, browserless, glitchtip-web
└── external/public.yaml      # 5 external HTTPS + SSL cert checks
```

### Stable DNS aliases — critical architecture rule
Coolify single-image Applications (`/data/coolify/applications/<uuid>/`) use
`container_name: <app-uuid>-<timestamp>`. The **timestamp changes on every redeploy**,
silently breaking all `tcp://` or `http://` URLs that reference it.

**Three-layer permanent fix implemented 2026-05-07:**
1. Compose: `networks.coolify.aliases` contains both UUID and stable name
2. Live: `docker network disconnect/connect --alias <stable>` (zero-downtime)
3. Reboot: `scripts/vps_apply_limits.sh` `apply_alias()` function

| Stable alias | UUID container | Port | Coolify app UUID |
|---|---|---|---|
| `browserless` | `vckgs8c00o40o884k48cgow8-220643454460` | 3000 | `vckgs8c00o40o884k48cgow8` |
| `gotenberg` | `e04k4sco44ow04ccc0o0k00k-151256201601` | 3000 | `e04k4sco44ow04ccc0o0k00k` |
| `meilisearch` | `bs0wo48k4gwo440gcowscoc8-150802066640` | 7700 | `bs0wo48k4gwo440gcowscoc8` |
| `glitchtip-web` | `glitchtip-web-z00kkck8c8cwo800kk440csk` | 8000 | Coolify service (stable) |

**Coolify Service stacks** (`/data/coolify/services/<uuid>/`) use `container_name: <service>-<coolify-service-uuid>`. The UUID here is the **Coolify service ID** — does NOT change on redeploy. These are already stable (authelia, loki, netdata, gatus, etc.).

**For every new single-image Application:** see `.windsurf/rules/55-observability.md` § "Gatus — Stable DNS Names" + `docs/reference/coolify-stable-aliases.md`.

## Resource Limits Reference

<!-- AUTO:limits_summary -->
| Container | Memory |
|---|---|
| `alertmanager-zw4swgkwk0s4s8kg048gw80o` | 256m |
| `apprise-lcocgs4gs8ksg4g08w40ows8` | 512m |
| `backrest-l48000k44wc4gk8os88s8k0c` | 512m |
| `bs0wo48k4gwo440gcowscoc8-211159651770` | 512m |
| `e04k4sco44ow04ccc0o0k00k-210433823748` | 512m |
| `file-worker-nwcckwggw0o0g40gwskk8kk8-191323299257` | 512m |
| `gatus-v8s4cokcwg0co4w8okkccc0w` | 256m |
| `glitchtip-web-z00kkck8c8cwo800kk440csk` | 512m |
| `glitchtip-worker-msgo0sg8gsgo4w4sscckc84g` | 512m |
| `loki-r48swckog008wosgwcs4g0g0` | 512m |
| `n8n-s8gwccsws0ccssw0wwgwsoks` | 2g |
| `node-exporter-doc8c8gkcgs88s8ckggw84o4` | 128m |
| `ocoron-com-db-1` | 1g |
| `ocoron-com-nginx-1` | 256m |
| `ocoron-com-redis-1` | 256m |
| `ocoron-com-wordpress-1` | 512m |
| `postgres-main-l0k4gk0kggc8okcwk0s4c8s8` | 2g |
| `promtail-w0000ckgsgg048w0848okk08` | 128m |
| `redis-main` | 512m |
| `traefik` | 256m |
| `vckgs8c00o40o884k48cgow8-210454442421` | 2g |
<!-- /AUTO -->

---

## Operational Lessons (Hard-Won — All Codified in Governance)

| # | Incident | Rule |
|---|---|---|
| 1 | `localhost` in DATABASE_URL crashed translator | Always `postgres-main:5432`, `redis-main:6379` |
| 2 | SIGHUP to Authelia → exits → all Traefik routes 404 | `docker restart <authelia>` after config changes |
| 3 | cadvisor OOM at 256m (91% RSS) | 512m + `--docker_only=true --disable_metrics=...` |
| 4 | prometheus OOM at 512m (93% RSS, 40 containers) | 1g minimum |
| 5 | netdata cache unbounded → 2.2GB | 512MB cap + 7-day retention |
| 6 | apprise OOM-prone at 256m | 512m |
| 7 | `yaml.dump` corrupted Authelia regex patterns | Use targeted replacements, never full YAML roundtrip |
| 8 | governance hook injected bare `internal_auth` imports | Rule files propagate docs, not code imports |
| 9 | `fabrik redeploy` without git push deploys stale code | `git commit → git push → fabrik redeploy` always |
| 10 | Per-service X-API-Key chaos | One key: `SERVICE_INTERNAL_SECRET_KEY`; one header: `X-Internal-Token` |
| 11 | import path must match uvicorn module path | `uvicorn app.main:app` → `from app.internal_auth import` |
| 12 | Authelia `^/api/` bypass needed for Coolify API token access | Already in config; verify after any Authelia edit |

---

## Security Posture Summary

<!-- AUTO:coolify_apps -->
| Name | FQDN | Status |
|---|---|---|
| `alertmanager` | internal | ⚠️ running:healthy |
| `apprise` | internal | ⚠️ running:healthy |
| `authelia` | internal | ⚠️ running:healthy |
| `backrest` | internal | ⚠️ running:unknown |
| `browserless` | https://browser.vps1.ocoron.com | ⚠️ running:unknown |
| `cadvisor` | internal | ⚠️ running:healthy |
| `fabrik-captcha` | internal | ⚠️ running:healthy |
| `fabrik-emailgateway` | internal | ⚠️ running:healthy |
| `fabrik-file-api` | internal | ⚠️ running:healthy |
| `fabrik-file-worker` | internal | ⚠️ running:healthy |
| `fabrik-image-broker` | internal | ⚠️ running:healthy |
| `fabrik-proxy` | https://proxy.vps1.ocoron.com | ⚠️ running:healthy |
| `fabrik-translator` | internal | ⚠️ running:healthy |
| `gatus` | internal | ⚠️ running:unknown |
| `glitchtip-web` | internal | ⚠️ running:unknown |
| `glitchtip-worker-v10` | internal | ⚠️ running:unknown |
| `gotenberg` | https://pdf.vps1.ocoron.com | ⚠️ running:healthy |
| `grafana` | internal | ⚠️ running:healthy |
| `loki` | internal | ⚠️ running:healthy |
| `meilisearch` | https://search.vps1.ocoron.com | ⚠️ running:healthy |
| `n8n` | internal | ⚠️ running:healthy |
| `netdata` | internal | ⚠️ running:healthy |
| `node-exporter` | internal | ⚠️ running:unknown |
| `postgres-main` | internal | ⚠️ running:healthy |
| `promtail` | internal | ⚠️ running:unknown |
| `site-provisioner` | internal | ⚠️ running:healthy |
<!-- /AUTO -->

---

## Pending Actions

| # | Action | Priority |
|---|---|---|
| 1 | Wildcard SSL → Coolify → Proxy → Cloudflare DNS resolver | Low |
| 2 | Add `/metrics` to 5 existing deployed services | Low (on next touch) |
| 3 | Monitor swap usage (~1.7GB/2GB) | Watch |

## Known Operational Issues — discovered 2026-05-08

### Issue 1: Coolify drops user-defined network aliases on redeploy

**Symptom:** Friendly Docker network aliases like `meilisearch`, `glitchtip-web`, `gotenberg`, `browserless` disappear after any Coolify redeploy. Services that depend on these aliases (Prometheus scraping, Gatus monitoring, Fabrik microservices) start failing with `no such host` errors until the alias is manually re-added.

**Root cause:** Coolify renders its own docker-compose from the Application config and runs `docker compose up -d` on each redeploy. The new container is created with only the aliases declared in that compose file (default: `<uuid>-<timestamp>`). Any aliases added later via `docker network connect --alias` are container-instance attributes, not part of the spec — they die with the old container.

**Affected services on this VPS:** `meilisearch`, `gotenberg`, `browserless`, `glitchtip-web`. Any redeploy of these breaks downstream consumers.

**Temporary fix (already applied for meilisearch 2026-05-08):**
```bash
sudo docker network disconnect coolify <new-container-name>
sudo docker network connect --alias meilisearch coolify <new-container-name>
```

**Permanent fix options (none yet applied):**
1. **Compose-level aliases (recommended)**: in each Coolify Application UI → "Custom Docker Compose Block" → declare `networks: { coolify: { aliases: [meilisearch] } }`. ~5 min per service.
2. **Watcher script**: systemd timer that polls every 60s and re-applies aliases when missing. ~30 min.
3. **Migrate off Coolify** for these 4 services to a hand-managed compose (like Prometheus already is).

**Tracking:** flagged for next observability/hardening sprint.

### Issue 2: Authelia config drift between working copy and live volume

**Symptom:** Edits to `/opt/authelia/config/configuration.yml` had no effect on Authelia's behavior even after restart.

**Root cause:** `/opt/authelia/config/` is a working copy / convention. The actual config Authelia reads is in a Docker named volume:
```
/var/lib/docker/volumes/hks48k8sg8o4co4co08co00o_authelia-config/_data/configuration.yml
```

The two had drifted (`/opt/authelia/config/` was the older version). On 2026-05-08 they were re-synced.

**To make a config change correctly:**
1. Edit BOTH files (working copy + volume), OR
2. Edit the volume only and `cp` it to the working copy after
3. `docker restart authelia-...` (NEVER SIGHUP — Authelia exits on SIGHUP)
4. Verify: `docker logs --since 30s authelia-... | grep "Listening"` shows expected addresses

**Status: RESOLVED 2026-05-08** — `authelia-config-sync.service` (systemd, event-driven via `inotifywait`) at `/opt/authelia-config-sync/`. Watches `/opt/authelia/config/configuration.yml`; on save, copies to volume and restarts Authelia container. Reaction time ~2s. See `ops/authelia-config-sync/README.md` for details. Drift no longer possible.
### Issue 3: Coolify maintains duplicate prod/preview env rows for every key

**Symptom:** When rotating an env value via the Coolify UI or API, the production deploy picks up the new value but the preview environment still uses the old value (or vice-versa).

**Root cause:** Coolify's data model stores production and preview env vars as **separate rows** in `environment_variables` table, both with the same key but different `is_preview` flags. Calling `PATCH /api/v1/applications/<uuid>/envs` with `{"key": K, "value": V}` only updates the row matching the `is_preview` flag in the request body (defaults to `false` = production only).

**Affected services** (any with non-trivial env footprint): every Coolify Application. Confirmed seen on `fabrik-proxy` (`WEBSHARE_API_KEY` had 2 rows: prod + preview).

**Fix when rotating:**
```python
# Iterate over ALL existing env rows and PATCH each separately:
for e in current_envs:
    if e["key"] == TARGET_KEY:
        body = {"key": TARGET_KEY, "value": NEW_VALUE,
                "is_preview": e["is_preview"], "is_literal": True}
        # PATCH /api/v1/applications/<uuid>/envs with body
```

Single-call updates miss the duplicate. Bulk-update endpoint behaves the same.

**Tracking:** captured in `deployment.md` Gotcha 7. Future Fabrik orchestrator env-injection should iterate over all rows by default.

### Issue 4: `/opt/monitoring/compose.yaml` is a HYBRID file — partly aggregated reference, partly source of truth

**Discovered:** 2026-05-08 during Grafana dashboard deployment + redis-exporter healthcheck fix.

**The reality is hybrid.** The 198-line file at `/opt/monitoring/compose.yaml` contains ~16 service definitions, but they fall into **two categories** with different deployment lifecycles:

#### Category A — Coolify-managed (the majority)
For these, the disk file is a **wishful aggregated reference** for human readability. Coolify stores its own `docker_compose_raw` per Service in its DB. Editing the disk file changes nothing.

| Container | Coolify Service UUID | Compose lifecycle |
|---|---|---|
| `grafana-loc484owg8gsw04owo0go8kc` | `loc484owg8gsw04owo0go8kc` | Coolify Service → `docker_compose_raw` in DB |
| `loki-r48swckog008wosgwcs4g0g0` | `r48swckog008wosgwcs4g0g0` | Coolify Service → `docker_compose_raw` in DB |
| `prometheus` | (separate Coolify project) | Coolify Service → `docker_compose_raw` in DB |
| `promtail-w0000ckgsgg048w0848okk08` | `w0000ckgsgg048w0848okk08` | Coolify Service → `docker_compose_raw` in DB |
| `alertmanager`, `gatus`, `cadvisor`, `netdata`, `node-exporter` | (each its own Coolify Service) | Coolify Service → `docker_compose_raw` in DB |
| `meilisearch`, `gotenberg`, `browserless` | (each is a Coolify **Application**, not Service) | Coolify Application → git build pipeline |

#### Category B — Host-managed sidecars (the minority — 2 services)
These were added as plain `docker compose` containers from `/opt/monitoring/compose.yaml`, not via Coolify. **For these, the disk file IS the source of truth** and edits propagate via `docker compose up -d --no-deps --force-recreate <name>`.

| Container | Project label | Compose lifecycle |
|---|---|---|
| `postgres-exporter` | `monitoring` | Plain docker compose, `restart: unless-stopped` |
| `redis-exporter` | `monitoring` | Plain docker compose, `restart: unless-stopped` |

**How to tell them apart:**
```bash
sudo docker inspect <container> --format '{{ index .Config.Labels "coolify.serviceId" }} | {{ index .Config.Labels "com.docker.compose.project" }}'
```
Empty serviceId + `com.docker.compose.project=monitoring` → Category B (host-managed). Otherwise → Category A (Coolify-managed).

**Why the hybrid is acceptable:**
- Postgres & Redis exporters are simple read-only sidecars, no persistent state, no migration risk.
- `restart: unless-stopped` survives reboots; behavior matches Coolify-managed containers in practice.
- Migrating them under Coolify management would require creating Coolify Services and is not strictly necessary.

**Operational cautions when working with the file:**
1. Bind-mount edits in the file ONLY apply to Category B services. For Category A, look at running container's actual mounts via `docker inspect`.
2. `docker compose -f /opt/monitoring/compose.yaml up -d <svc>` for Category A creates **competing standalone containers and volumes** alongside the Coolify-managed ones (project=`monitoring`). This was hit during this session: `up -d grafana` created an orphan `loki` container + 3 dangling `monitoring_*` volumes. Cleaned up.
3. Use `--no-deps --force-recreate` to scope changes precisely when targeting Category B services.

**Tracking:** captured in `deployment.md` Gotcha 8.


## Service integration audit (2026-05-09 — corrected)

**Correction:** An earlier note claimed registrar drivers were "not implemented." That was wrong. The 9 driver files in `src/fabrik/drivers/` ARE implemented (8 of 9 are 9-20KB; redis.py is a 1KB stub) and ARE dispatched by `DeploymentOrchestrator` during `fabrik apply`. The actual gap is that all 8 services currently running on the VPS were deployed under pre-G1 specs without `shape:` blocks, so the registrar architecture has never executed for them — their cross-service wiring was done manually instead. Detailed analysis: `docs/operations/deployment.md` "Phase 4 Registrar Coverage Status (corrected 2026-05-09)".

Cross-service integration map (which container connects to which shared platform component) is captured in `docs/operations/vps-status.md` under "Service Integration Map (audited 2026-05-09)". Phase 4 registrar implementation status is captured in `docs/operations/deployment.md` under "Phase 4 Registrar Coverage Status".

Headline numbers from that audit:
- Postgres: 4 app DBs across 4 services
- Redis: 2 logical DBs in use (authelia=db3, glitchtip-web=db4); 14 indexes free
- Gatus: 28 endpoints across 14 config files
- Backrest: 1 repo, 4 plans
- GlitchTip: 7 active projects
- Grafana: 9 dashboards (5 Fabrik + 4 community)
- Authelia: 8 access control rules
- Meilisearch: 0 indexes (no consumers yet)
- Prometheus: 13 scrape jobs, 12 active targets, SIGHUP reload pattern
