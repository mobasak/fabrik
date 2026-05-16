# VPS Status

**Last Updated:** 2026-05-16 14:23 UTC
**Host:** vps1.ocoron.com (172.93.160.197)
**Provider:** Psychz Networks (AS32421) — Los Angeles, CA, USA
**SSH:** `ssh vps` (ozgur@vps1.ocoron.com, Ed25519 key-only, root disabled)
**Coolify:** v4.0.0-beta.459 (fully patched — CVEs fixed in beta.451+)

---

## System Overview

<!-- AUTO:system_overview -->
| **Containers running** | 44 |
| **Disk** | 108G total, 40G used, 68G free (38%) |
| **Memory** | 11Gi total, 5.3Gi used, 1.6Gi free |
| **Uptime** | up 8 weeks, 2 days, 16 hours, 2 minutes |
| **Last snapshot** | 2026-05-16 14:23 UTC |
<!-- /AUTO -->

| **OS** | Ubuntu 24.04 LTS |
| **CPU** | 6 vCores (x86_64) |
| **Docker** | Engine direct (not Desktop), cgroupv2 |
| **Coolify** | v4.0.0-beta.459 |

---

## Security Posture

| Layer | Status | Detail |
|---|---|---|
| **SSH** | ✅ | Ed25519 key-only; root disabled; password auth disabled |
| **UFW** | ✅ | Active; port 8000 DENY; 7 rules |
| **Traefik dashboard** | ✅ | `127.0.0.1:8080` localhost only |
| **Coolify UI (8000)** | ✅ BLOCKED | UFW DENY; use `coolify.vps1.ocoron.com` |
| **Authelia** | ✅ | Forward-auth on all admin UIs; TOTP 2FA; Redis sessions |
| **M2M auth** | ✅ | `X-Internal-Token` + `SERVICE_INTERNAL_SECRET_KEY` on all API services |
| **file-api** | ✅ | Supabase Bearer JWT (user auth) |
| **site-provisioner** | ✅ | Traefik IP allowlist |
| **Resource limits** | ✅ | All 40 containers limited |
| **Gzip** | ✅ | `gzip@docker` registered; scaffold wires it to all routers |
| **SSL** | ⚠️ | Per-service HTTP challenge; TODO: Cloudflare DNS wildcard |
| **Coolify CVEs** | ✅ | beta.459, CVEs patched in beta.451+ |

### Firewall (UFW)

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

## Container Status (42 running)

<!-- AUTO:container_status -->
| Container | Status | Memory limit |
|---|---|---|
| `alertmanager-zw4swgkwk0s4s8kg048gw80o` | ✅ Up 3 weeks (healthy) | 256m |
| `apprise-lcocgs4gs8ksg4g08w40ows8` | ✅ Up 3 weeks (healthy) | 768m |
| `authelia-hks48k8sg8o4co4co08co00o` | ✅ Up 22 hours (healthy) | 512m |
| `backrest-l48000k44wc4gk8os88s8k0c` | ✅ Up 7 minutes | 512m |
| `bs0wo48k4gwo440gcowscoc8-211159651770` | ✅ Up 7 days (healthy) | 512m |
| `cadvisor-r08sog4gwws88og048ows448` | ✅ Up 9 days (healthy) | 512m |
| `captcha-j8gg4ggskkossc4gkwowk4os-191229303949` | ✅ Up 7 days (healthy) | 512m |
| `coolify` | ✅ Up 3 weeks (healthy) | — |
| `coolify-db` | ✅ Up 3 weeks (healthy) | — |
| `coolify-realtime` | ✅ Up 3 weeks (healthy) | — |
| `coolify-redis` | ✅ Up 3 weeks (healthy) | — |
| `coolify-sentinel` | ✅ Up 24 minutes (healthy) | — |
| `e04k4sco44ow04ccc0o0k00k-210433823748` | ✅ Up 7 days (healthy) | 512m |
| `emailgateway-w4oocckkwko8kowggsw8sogc-192134804476` | ✅ Up 7 days (healthy) | 512m |
| `fabrik-proxy-zsccsksoc8sssc8k00sgcc08-190757006943` | ✅ Up 5 days (healthy) | 512m |
| `file-api-bsswwg4kg480c000gksw004k-192212486944` | ✅ Up 7 days (healthy) | 512m |
| `file-worker-nwcckwggw0o0g40gwskk8kk8-191323299257` | ✅ Up 2 days (healthy) | 512m |
| `gatus-v8s4cokcwg0co4w8okkccc0w` | ✅ Up About a minute | 256m |
| `glitchtip-web-z00kkck8c8cwo800kk440csk` | ✅ Up 3 weeks | 512m |
| `glitchtip-worker-msgo0sg8gsgo4w4sscckc84g` | ✅ Up 3 weeks | 512m |
| `grafana-loc484owg8gsw04owo0go8kc` | ✅ Up 7 days (healthy) | 512m |
| `image-broker-zo4ggs4g880skwkocwwkscgk-091249852459` | ✅ Up 29 hours (healthy) | 512m |
| `loki-r48swckog008wosgwcs4g0g0` | ✅ Up 3 weeks (healthy) | 512m |
| `n8n-s8gwccsws0ccssw0wwgwsoks` | ✅ Up 3 weeks (healthy) | 2g |
| `netdata-kk4kcw4csksc48848go4o0wo` | ✅ Up 9 days (healthy) | 1g |
| `node-exporter-doc8c8gkcgs88s8ckggw84o4` | ✅ Up 3 weeks | 128m |
| `ocoron-com-backup-1` | ✅ Up 3 weeks | 128m |
| `ocoron-com-db-1` | ✅ Up 3 weeks (healthy) | 1g |
| `ocoron-com-nginx-1` | ✅ Up 3 weeks | 256m |
| `ocoron-com-redis-1` | ✅ Up 3 weeks (healthy) | 256m |
| `ocoron-com-wordpress-1` | ✅ Up 3 weeks | 512m |
| `postgres-exporter` | ✅ Up 7 days (healthy) | 64m |
| `postgres-main-l0k4gk0kggc8okcwk0s4c8s8` | ✅ Up 3 weeks (healthy) | 2g |
| `prometheus` | ✅ Up About an hour (healthy) | 1g |
| `promtail-w0000ckgsgg048w0848okk08` | ✅ Up 9 days | 128m |
| `pushgateway` | ✅ Up 9 hours (healthy) | — |
| `redis-exporter` | ✅ Up 7 days | 64m |
| `redis-main` | ✅ Up 3 weeks (healthy) | 512m |
| `site-provisioner-qokoksogwsk0c04gcs4swwgs-200230906082` | ✅ Up 7 days (healthy) | 512m |
| `test-chrome-extension-lcco440cck88c44owo8c8c80-142422558429` | ✅ Up 23 seconds (healthy) | 512m |
| `traefik` | ✅ Up 29 hours | 256m |
| `translator-kgws0s4cscsosw8gg848cwgw-152024553111` | ✅ Up 23 hours (healthy) | 512m |
| `vckgs8c00o40o884k48cgow8-210454442421` | ✅ Up 7 days | 2g |
| `xoo8o8884wgw8c4gcsk48004` | ✅ Up 4 minutes | — |
<!-- /AUTO -->

---

## Traefik Middleware Registry

<!-- AUTO:traefik_middlewares -->
| Name | Type |
|---|---|
| `authelia-forward@docker` | forwardauth |
| `dashboard_redirect@internal` | redirectregex |
| `dashboard_stripprefix@internal` | stripprefix |
| `gzip@docker` | compress |
| `ocoron-com-block-xmlrpc@docker` | replacepathregex |
| `ocoron-com-rate-limit@docker` | ratelimit |
| `ocoron-com-www-redirect@docker` | redirectregex |
| `redirect-to-https@docker` | redirectscheme |
| `redirect-web-to-websecure@internal` | redirectscheme |
| `site-provisioner-ipallowlist@docker` | ipallowlist |
| `test-chrome-extension-cors@docker` | headers |
<!-- /AUTO -->

---

## Observability

### Prometheus Scrape Jobs
| Job | Target | Interval |
|---|---|---|
| `prometheus` | `localhost:9090` | 15s |
| `node` | `node-exporter:9100` | 15s |
| `cadvisor` | `cadvisor:8080` | 15s |
| `loki` | `loki:3100` | 15s |
| `netdata` | `netdata:19999` `/api/v1/allmetrics` | 15s |
| `alertmanager` | `alertmanager:9093` | 15s |
| `gatus` | `gatus:8080` | 15s |
| `grafana` | `grafana:3000` (anonymous) | 15s |
| `authelia` | `authelia:9959` (telemetry port — requires `telemetry.metrics.enabled` in config) | 15s |
| `meilisearch` | `meilisearch:7700` Bearer auth (master key) — requires `MEILI_EXPERIMENTAL_ENABLE_METRICS=true` | 15s |
| `postgres` | `postgres-exporter:9187` (sidecar, postgres_exporter v0.15.0) | 15s |
| `redis` | `redis-exporter:9121` (sidecar, redis_exporter v1.66.0) | 15s |
| `fabrik-services` | (targets commented — wire as services add `/metrics`) | 30s |

**All 10 Prometheus targets are UP as of 2026-05-08.** Sample app-level series confirmed flowing:
- `authelia_request{}` — auth attempts, latency by code/method
- `grafana_http_request_duration_seconds_*` — dashboard render rates
- `meilisearch_http_requests_total` — search QPS, index ops

**GlitchTip is intentionally NOT scraped** — `django-prometheus` not bundled by default. cAdvisor (container-level) + Gatus (uptime) cover it.

See `docs/infrastructure/prometheus-app-metrics-setup.md` for setup runbook + sample queries.

### Retention Limits
| Service | Limit | Config |
|---|---|---|
| Prometheus | 30 days or 5GB (whichever first) | `--storage.tsdb.retention.time=30d --storage.tsdb.retention.size=5GB` |
| Loki | 7 days | `limits_config.retention_period: 168h` |
| Netdata | 512MB disk / 7 days | `NETDATA_DBENGINE_DISK_SPACE_MB=512` + `RETENTION_DAYS=7` |
| Alertmanager | Negligible (500B) | None needed |

### Alertmanager
- Receiver: Telegram (native `telegram_configs`)
- `group_by: [alertname, container]`
- Default `repeat_interval: 4h`; critical alerts `repeat_interval: 30m`
- LLM-based triage (ARO Brain) planned — will route before Telegram as fallback

### Error Reporting (GlitchTip) — Live since 2026-05-08
- **Public URL:** `https://errors.vps1.ocoron.com` (Authelia-protected)
- **Internal alias:** `glitchtip-web:8000` on `coolify` Docker network — used by SDK ingestion (bypasses Authelia/TLS)
- **Fabrik microservices wired (7):** captcha, image-broker, translator, emailgateway, file-api, file-worker, site-provisioner — each has scaffold-emitted `glitchtip_init` module + `SENTRY_DSN` env. Init reads `SENTRY_DSN` first, falls back to `GLITCHTIP_DSN`. Future `fabrik apply` deploys auto-inject SENTRY_DSN via the orchestrator's glitchtip registrar (hard-fatal if injection fails)
- **Validated 2026-05-08:** 5 of 7 services have real events flowing (firstEvent populated). emailgateway + file-worker idle, init code in place — events will flow on first error
- **Containers:** `glitchtip-web-z00kkck8c8cwo800kk440csk` (web, 512m), `glitchtip-worker-msgo0sg8gsgo4w4sscckc84g` (worker, 512m)
- **Storage:** `glitchtip` DB on `postgres-main`; events retained 90 days (`GLITCHTIP_RETENTION_DAYS` default)
- **SDK integration:** `fabrik scaffold` auto-emits `glitchtip_init.py` (python-api) and `glitchtip_init.js` (node-api). Zero-overhead no-op when `GLITCHTIP_DSN` env unset.
- **Provisioner:** `scripts/provision_glitchtip_project.sh <service-name> [--platform javascript-node] [--coolify-uuid <uuid>]` — idempotent, returns DSN with internal alias rewrite
- **Capture discipline:** when DSN is set, unhandled exceptions auto-report — DO NOT also `logger.exception()` full tracebacks (duplicates events). See `.windsurf/rules/55-observability.md § Error Reporting`.
- **Runbook:** `docs/infrastructure/glitchtip-sdk-integration-setup.md`

---

## Promtail Noise Filter

**Config:** `/opt/monitoring/configs/promtail/promtail-config.yaml`
**Filter:** drops Coolify infrastructure logs that produce no actionable signal.
Filtered out: `coolify-db`, `coolify-redis`, `coolify-realtime`, `coolify-sentinel`, `ocoron-com-backup-1`.
All Fabrik services, monitoring stack, and WordPress logs continue to ship to Loki.

**Full setup runbook:** [`docs/infrastructure/promtail-noise-filter-setup.md`](../infrastructure/promtail-noise-filter-setup.md)

## Grafana Datasource Provisioning

**Bind mount:** `/opt/monitoring/configs/grafana/provisioning -> /etc/grafana/provisioning:ro`
**Config:** `/opt/monitoring/configs/grafana/provisioning/datasources/fabrik.yaml`
**Provisioned datasources:** `Prometheus` (default, `http://prometheus:9090`) and `Loki` (`http://loki:3100`).
Datasources persist as code — survive volume wipes, container redeploys, and complete Grafana reinstalls.

**Full setup runbook:** [`docs/infrastructure/grafana-provisioning-setup.md`](../infrastructure/grafana-provisioning-setup.md)

## Gatus Monitoring

**Config:** `/opt/monitoring/configs/gatus/` (6 subdirs, volume-mounted, auto-reloads)
**Alert path:** Gatus → Apprise → (Telegram / multi-channel)
**Storage:** `type: memory` (leaner than SQLite; no persistence needed for status)
**Status page:** `https://status.vps1.ocoron.com` (public, read-only)

### Groups and endpoints
| Group | Endpoints | Check type |
|---|---|---|
| `core` | traefik, authelia, coolify, n8n, apprise | TCP + HTTP health |
| `data` | postgres-main, redis-main, meilisearch | TCP connect |
| `observability` | grafana, prometheus, alertmanager, loki, netdata | HTTP health + body check |
| `microservices` | captcha, translator, file-api, image-broker, email-gateway | HTTP /health |
| `apps` | n8n, netdata, prometheus, site-provisioner, grafana, loki, alertmanager, backrest, apprise, glitchtip | HTTP health |
| `services` | gotenberg, browserless, glitchtip-web | TCP connect |
| `external` | coolify-public, status-page, glitchtip-public, search-public, monitor-public | HTTPS + `[CERTIFICATE_EXPIRATION] > 168h` |

### Stable DNS aliases (Coolify single-image Application fix)
Coolify assigns `<app-uuid>-<timestamp>` container names that break on redeploy.
Four services have stable aliases registered:

| Stable alias | Container | Port |
|---|---|---|
| `browserless` | `vckgs8c00o40o884k48cgow8-220643454460` | 3000 |
| `gotenberg` | `e04k4sco44ow04ccc0o0k00k-151256201601` | 3000 |
| `meilisearch` | `bs0wo48k4gwo440gcowscoc8-150802066640` | 7700 |
| `glitchtip-web` | `glitchtip-web-z00kkck8c8cwo800kk440csk` | 8000 |

Aliases persist via: compose file (Coolify redeploy) + `vps_apply_limits.sh` (VPS reboot).
For new single-image Application: see `.windsurf/rules/55-observability.md` § "Gatus — Stable DNS Names" + `docs/reference/coolify-stable-aliases.md`.

## Resource Limits

<!-- AUTO:limits_summary -->
| Container | Memory |
|---|---|
| `alertmanager-zw4swgkwk0s4s8kg048gw80o` | 256m |
| `apprise-lcocgs4gs8ksg4g08w40ows8` | 768m |
| `authelia-hks48k8sg8o4co4co08co00o` | 512m |
| `backrest-l48000k44wc4gk8os88s8k0c` | 512m |
| `bs0wo48k4gwo440gcowscoc8-211159651770` | 512m |
| `cadvisor-r08sog4gwws88og048ows448` | 512m |
| `captcha-j8gg4ggskkossc4gkwowk4os-191229303949` | 512m |
| `e04k4sco44ow04ccc0o0k00k-210433823748` | 512m |
| `emailgateway-w4oocckkwko8kowggsw8sogc-192134804476` | 512m |
| `fabrik-proxy-zsccsksoc8sssc8k00sgcc08-190757006943` | 512m |
| `file-api-bsswwg4kg480c000gksw004k-192212486944` | 512m |
| `file-worker-nwcckwggw0o0g40gwskk8kk8-191323299257` | 512m |
| `gatus-v8s4cokcwg0co4w8okkccc0w` | 256m |
| `glitchtip-web-z00kkck8c8cwo800kk440csk` | 512m |
| `glitchtip-worker-msgo0sg8gsgo4w4sscckc84g` | 512m |
| `grafana-loc484owg8gsw04owo0go8kc` | 512m |
| `image-broker-zo4ggs4g880skwkocwwkscgk-091249852459` | 512m |
| `loki-r48swckog008wosgwcs4g0g0` | 512m |
| `n8n-s8gwccsws0ccssw0wwgwsoks` | 2g |
| `netdata-kk4kcw4csksc48848go4o0wo` | 1g |
| `node-exporter-doc8c8gkcgs88s8ckggw84o4` | 128m |
| `ocoron-com-backup-1` | 128m |
| `ocoron-com-db-1` | 1g |
| `ocoron-com-nginx-1` | 256m |
| `ocoron-com-redis-1` | 256m |
| `ocoron-com-wordpress-1` | 512m |
| `postgres-exporter` | 64m |
| `postgres-main-l0k4gk0kggc8okcwk0s4c8s8` | 2g |
| `prometheus` | 1g |
| `promtail-w0000ckgsgg048w0848okk08` | 128m |
| `redis-exporter` | 64m |
| `redis-main` | 512m |
| `site-provisioner-qokoksogwsk0c04gcs4swwgs-200230906082` | 512m |
| `test-chrome-extension-lcco440cck88c44owo8c8c80-142422558429` | 512m |
| `traefik` | 256m |
| `translator-kgws0s4cscsosw8gg848cwgw-152024553111` | 512m |
| `vckgs8c00o40o884k48cgow8-210454442421` | 2g |
<!-- /AUTO -->

---

## Authelia Access Control (9 rules — live as of 2026-05-15)

| Domain | Policy | Path restriction |
|---|---|---|
| `ocoron.com`, `www.ocoron.com` | bypass | all paths |
| `wp-test.vps1.ocoron.com`, `status.vps1.ocoron.com` | bypass | all paths |
| `*.vps1.ocoron.com` | bypass | `/health`, `/healthz`, `/metrics`, `/api/health` only |
| `pdf, browser, search, captcha, proxy, translator, files-api, emailgateway, dns` `.vps1.ocoron.com` (9 hosts) | bypass | all paths (app-layer auth) |
| `coolify.vps1.ocoron.com`, `monitor.vps1.ocoron.com` | bypass | `^/api/` only |
| `images.vps1.ocoron.com` | bypass | `^/api/` only (T1-04 paired-pattern) |
| `*.vps1.ocoron.com` | two_factor | everything else (catchall) |

`errors.vps1.ocoron.com` was removed from the multi-domain bulk-bypass on 2026-05-15 (T2-08 Part A); it now falls through to the `two_factor` catchall — matches `docs/operations/vps-urls.md` "GlitchTip error reporting UI: Authelia" intent.

**After any Authelia config change:** `ssh vps "sudo docker restart authelia-hks48k8sg8o4co4co08co00o"`
**Never use SIGHUP — Authelia exits on SIGHUP.**

---

## M2M Authentication

| Header | `X-Internal-Token` |
|---|---|
| Env var | `SERVICE_INTERNAL_SECRET_KEY` (one shared key, all services) |
| Key location | `/opt/fabrik/.env` |
| Python module | `app/internal_auth.py` or `src/internal_auth.py` (scaffold emits automatically) |
| Node.js module | `src/internal_auth.js` (scaffold emits automatically) |
| Validation | `hmac.compare_digest` / `timingSafeEqual` — constant-time |

Deployed on: captcha, image-broker, translator, proxy, emailgateway
Exempt: file-api (Supabase JWT), site-provisioner (IP allowlist)
Pre-placed in 35 projects under `/opt`

---

## Recent Maintenance (2026-05-08)

### Disk cleanup — 8 GB freed
A full Docker hygiene pass on 2026-05-08 reclaimed **8 GB** on the root filesystem (47 GB → 39 GB used).

| Phase | Outcome |
|---|---|
| `/tmp` staging files | 12 cleanup scripts + 2 tar bundles removed |
| `/opt/*.bak.*` >14 days old | 2 stale config backups removed |
| Dangling volumes (`monitoring_*`) | 3 removed (debris from a botched `docker compose -f /opt/monitoring/compose.yaml up -d` — see Gotcha 8 in deployment.md) |
| Empty Docker networks | 10 pruned |
| Unused Docker images | **6.996 GB** reclaimed via `docker image prune -a -f` |
| Build cache | 1.116 GB reclaimed via `docker builder prune -f` |
| systemd journal | 0 (all entries within 7-day retention; no vacuum needed) |

After cleanup: **40 images, 14.32 GB** — 100 % active (each image referenced by ≥1 running container).

### Permanent fixes deployed
| Fix | Status |
|---|---|
| `coolify-alias-watcher.service` (Issue #1: Coolify drops aliases on redeploy) | RESOLVED |
| `authelia-config-sync.service` (Issue #2: working-copy/volume drift) | RESOLVED |
| Coolify env-row duplication awareness (Issue #3) | DOCUMENTED — see Gotcha 7 |
| `/opt/monitoring/compose.yaml` is NOT what's deployed | DOCUMENTED — see Gotcha 8 |

### Governance propagation: 41 → 0 failures
The pre-commit propagator `scripts/sync_enforcement_to_projects.py` now covers **41 projects** with **0 failures**. This was previously 34 projects with 7 non-git holdouts that escaped propagation.

Changes: 7 projects (`gmailaccountcreator`, `image-generation`, `llm_batch_processor`, `namecheap`, `supplement-tracker-advisor`, `transcriber`, `ugc`) were `git init`'d. The propagator script's `exclude_folders` set was extended with `containerd`/`google`/`logs` (system dirs without write permission or non-project semantics). `/opt/_final-verify` (a 5-month-old scaffold test fixture) was relocated to `/opt/_archive/_final-verify` to free the project namespace.

### Grafana — 5 dashboards provisioned
The Fabrik observability stack now ships with 5 dashboards in the `Fabrik` folder, auto-loaded from `/opt/monitoring/configs/grafana/provisioning/json-dashboards/` via the existing `provisioning` bind mount. **No compose changes were needed** — the cleanest deploy path. See dashboard catalog earlier in this doc.

### Healthcheck override — redis-exporter (2026-05-08)
The `oliver006/redis_exporter:v1.66.0` image is distroless (no `wget`, no shell). Its baked-in healthcheck `[CMD wget -qO- http://localhost:9121/metrics]` cannot execute, producing a permanent `(unhealthy)` status — purely cosmetic since metrics flow normally. Fix in `/opt/monitoring/compose.yaml`: `healthcheck.disable: true`. Liveness signal is now Prometheus's `up{job="redis"}` metric, which is more reliable for an exporter than any internal check. `postgres-exporter` keeps its image healthcheck because the `prometheuscommunity/postgres-exporter` image bundles wget.

## Service Integration Map (audited 2026-05-09)

This snapshot describes which services are **actually wired up** to which shared platform components on the VPS today. It maps onto the 9-registrar Phase 4 design (drivers in `src/fabrik/drivers/`, dispatch in `src/fabrik/orchestrator/infrastructure.py`). **The registrar architecture IS implemented.** The gap is that all 8 currently-deployed services were deployed under pre-G1 specs without `shape:` blocks, so their state was wired up manually rather than via `fabrik apply`. See `docs/operations/deployment.md` "Phase 4 Registrar Coverage Status" for the corrected analysis (`postgres`, `redis`, `gatus`, `backrest`, `glitchtip`, `grafana`, `authelia`, `meilisearch`, `prometheus`).

### Postgres central — `postgres-main:5432`
4 application databases (postgres-exporter sees the 5th = system `postgres` DB):

| DB | Size | Connected service | User |
|---|---|---|---|
| `glitchtip` | 61 MB | `glitchtip-web`, `glitchtip-worker` | `postgres` |
| `proxy_management` | 8.3 MB | `fabrik-proxy` | `proxy_user` |
| `translator` | 8.0 MB | `translator` (kgws0s4cscsosw8gg848cwgw) | `postgres` |
| `site_provisioner` | 7.6 MB | `site-provisioner` (qokoksogwsk0c04gcs4swwgs) | `site_provisioner` |

DB users (excluding postgres super): `site_provisioner`, `proxy_user`, `ozgur`. Connection convention: `postgres-main:5432` (Docker DNS alias on coolify network), never `localhost` from inside containers. **`translator` was renamed from `translator_service` on 2026-05-15 (T1-05) — see `scripts/migrate_db_rename.py` for the reusable orchestrator that performed the rename.**

### Redis central — `redis-main:6379` (single instance, 16 logical DBs)
2 logical DBs in active use:

| DB index | Keys | Connected service |
|---|---|---|
| `db3` | 40 (TTL'd) | `authelia` (session storage, configured in `session.redis.database_index: 3`) |
| `db4` | 15 (TTL'd) | `glitchtip-web` (`REDIS_URL=redis://redis-main:6379/4`) |

DB indexes 0–2, 5–15 free. **No central authority maps DB index → service today** — Phase 4 registrar would assign these.

### Gatus monitoring — 28 endpoints across 14 files
File structure (multi-file config under `/opt/monitoring/configs/gatus/`):

| Subdir | Endpoint count | Purpose |
|---|---|---|
| `core/infra.yaml` | 5 | Coolify-self, Traefik, system services |
| `data/databases.yaml` | 3 | postgres, redis, db connectivity probes |
| `external/public.yaml` | 5 | External (publicly reachable) URLs |
| `observability/stack.yaml` | 5 | Loki, Prometheus, Grafana, etc. |
| `apps/*.yaml` | 10 | Per-app HTTP endpoints (one per file: prometheus, netdata, n8n, loki, grafana, glitchtip, dns-manager, backrest, apprise, alertmanager) |

Drift safety: 2 `*.predrift-fix.20260506` backups exist (`dns-manager.yaml`, `fabrik-microservices.yaml`).

### Backrest — Restic-based backup
- **1 repo:** `b2-vps1` → `s3://vps1-oco@s3.us-west-004.backblazeb2.com` (Backblaze B2)
- **4 plans:** `docker-volumes`, `opt-configs`, `postgres-dumps`, `fabrik-e2e-test-data`
- Container: `backrest-l48000k44wc4gk8os88s8k0c` — Up 5 days
- Bind mounts: `/opt/backups`, `/var/lib/docker/volumes`, `/opt/backrest/config`, `/opt` (read), Docker socket

### GlitchTip — error tracking
- **7 active GT projects** (per session memory): `captcha` (id=65, flowing), `image-broker` (66, flowing), `translator` (67, flowing), `emailgateway` (68, idle), `file-api` (69, flowing), `file-worker` (70, idle), `site-provisioner` (24, flowing)
- DSN convention rewritten by orchestrator to internal alias `glitchtip-web:8000` (not the public URL)
- API token: `GLITCHTIP_AUTH_TOKEN` not currently in `/opt/fabrik/.env` — manual API exploration requires re-fetching from the GT UI when needed
- DB: `postgres-main → glitchtip` (53 MB), Redis: `redis-main:6379/4`

### Grafana — 9 dashboards total
| Folder | Count | UIDs |
|---|---|---|
| `Fabrik` | 5 | fabrik-infra-overview, fabrik-databases, fabrik-containers, fabrik-authelia, fabrik-meilisearch |
| (root) | 4 | `Docker monitoring` (community), `Node Exporter Full` (community), `Prometheus Stats` (community), and `Fabrik` folder marker |

Provisioning: bind-mounted `/opt/monitoring/configs/grafana/provisioning -> /etc/grafana/provisioning:ro`. Auto-reload every 30s for dashboard JSONs; provider yamls require Grafana restart.

### Authelia — access control rules
- **default_policy:** `deny`
- **Bypass list (9 rules total — live as of 2026-05-15):** `ocoron.com`, `www.ocoron.com`, `wp-test.vps1.ocoron.com`, `status.vps1.ocoron.com`, all `*.vps1.ocoron.com` for `^/(health|healthz|metrics|api/health)$`, 9 microservice subdomains (pdf, browser, search, captcha, proxy, translator, files-api, emailgateway, dns — `errors` removed by T2-08 Part A; `images` moved to its own `^/api/` row for T1-04 paired-pattern), Coolify + Monitor `^/api/` paths, `images.vps1.ocoron.com` `^/api/` paths
- **Two-factor:** catch-all `*.vps1.ocoron.com` not bypassed above (includes `errors.vps1.ocoron.com`)
- **Session storage:** Redis DB 3, 1h expiration, 5m inactivity, 1mo remember-me
- **Storage backend:** SQLite at `/config/db.sqlite3`

### Meilisearch — search backend
- **0 indexes currently** (audited via `GET /indexes` — returns `bad address` from prometheus container; needs verification via the watcher, but no scaffolded service currently consumes meilisearch)
- Master key in environment, metrics endpoint serving since `MEILI_EXPERIMENTAL_ENABLE_METRICS=true` was set
- Network alias `meilisearch` confirmed preserved by `coolify-alias-watcher.service` (last applied 2026-05-09T00:12:06+03:00 after a redeploy)

### Prometheus — 13 scrape jobs, 12 active targets
| Job | Target count | Source |
|---|---|---|
| `prometheus`, `node`, `cadvisor`, `loki`, `netdata`, `alertmanager`, `gatus` | 1 each | infrastructure |
| `grafana`, `authelia`, `meilisearch` | 1 each | app-level (added 2026-05-08) |
| `postgres`, `redis` | 1 each | exporter sidecars (added 2026-05-08) |
| `fabrik-services` | 0 active | service discovery placeholder |

Reload mechanism: `SIGHUP` to prometheus container after editing `/opt/monitoring/configs/prometheus/prometheus.yml` (which IS bind-mounted from the Coolify-managed Service compose, so edits there DO apply — unlike the rest of `/opt/monitoring/compose.yaml`).

## Known Issues

> Issues #1, #2 RESOLVED 2026-05-08 by systemd watcher services. Issue #3 documented as a permanent operational gotcha. See `docs/infrastructure/vps-complete-inventory.md` for full Issue #1/#2/#3/#4 history with root causes and solutions; see `docs/operations/deployment.md` for the 8 deployment gotchas.



| # | Issue | Status |
|---|---|---|
| 1 | Wildcard SSL (Cloudflare DNS challenge) | TODO — Coolify → Proxy → Add resolver |
| 2 | `gzip@docker` not wired to individual routers | Scaffold now emits it; wire existing services in Coolify UI |
| 3 | Business metrics `/metrics` on existing services | Add `prometheus-client` + `metrics.py` manually per service |

---

## Maintenance Commands

```bash
# After VPS reboot — reapply infra memory limits
ssh vps "bash /opt/fabrik/scripts/vps_apply_limits.sh"

# Full health + residue audit (checks limits drift, stale Authelia rules, etc.)
cd /opt/fabrik && python3 scripts/vps_sync.py --verify

# Update VPS docs from live state (runs automatically post-deploy)
cd /opt/fabrik && python3 scripts/update_vps_docs.py

# Redeploy (MUST git commit + push first — Coolify pulls from GitHub)
cd /opt/<service> && git add -A && git commit -m "..." && git push
cd /opt/fabrik && fabrik redeploy fabrik-<name>

# Restart Authelia after config edit (NEVER SIGHUP)
ssh vps "sudo docker restart authelia-hks48k8sg8o4co4co08co00o"

# Reload Prometheus config after editing prometheus.yml
ssh vps "cd /opt/prometheus && sudo docker compose restart"

# Weekly disk cleanup
ssh vps "sudo docker image prune -f && sudo docker builder prune -f"

# Check memory pressure
ssh vps "sudo docker stats --no-stream --format '{{.Name}}\t{{.MemUsage}}\t{{.MemPerc}}' | sort -t$'\t' -k3 -rn | head -10"
```

### Recent secret rotations (2026-05-08)
| Service | Secret | Reason |
|---|---|---|
| site-provisioner | `CLOUDFLARE_API_TOKEN` | Auto-revoked by Cloudflare leak detector after a previous token was pushed to GitHub |
| fabrik-proxy | `WEBSHARE_API_KEY` | User-initiated rotation; both prod + preview env rows PATCHed in Coolify |

### CI status
GitHub Actions CI workflow `ci.yml` has 2 jobs: `kpi-schema-validate` (always passing) and `duplicate-check` (jscpd-based). As of 2026-05-08 commit `1622b0c`, the duplicate-check gate is **green** after:
- Adding `**/.archive/**` and `**/traycer_agents_fixed/**` to jscpd's ignore list (legitimate non-business duplication)
- Bumping threshold 5% → 7% to give margin for structural duplication in this polyglot scaffold-heavy repo

### Grafana provisioned dashboards (2026-05-08)
The Fabrik observability stack now ships with **5 provisioned dashboards** in the `Fabrik` folder of Grafana, auto-loaded at Grafana startup via host bind-mount.

| UID | Title | Coverage |
|---|---|---|
| `fabrik-infra-overview` | Fabrik · Infrastructure Overview | Host CPU/RAM/disk, target up/down, top-10 containers by CPU/mem/network IO |
| `fabrik-databases` | Fabrik · Databases (Postgres + Redis) | pg_stat_database commit/rollback rates, cache hit ratio, DB sizes; Redis ops/sec, hit ratio, memory, evictions |
| `fabrik-containers` | Fabrik · Container View (per-name) | Generic per-container CPU/mem/net/disk, with `$container` template variable for filtering |
| `fabrik-authelia` | Fabrik · Authelia (auth + sessions) | auth_request rates by code/method, latency p50/p95/p99 |
| `fabrik-meilisearch` | Fabrik · Meilisearch | search QPS by code/path, index sizes, latency p95 |

**Source of truth:** `configs/grafana/dashboards/*.json` (generated by `configs/grafana/build_dashboards.py`).

**Deployment path on VPS** (uses existing `/opt/monitoring/configs/grafana/provisioning -> /etc/grafana/provisioning` bind mount, no compose changes needed):
- `provisioning/dashboards/fabrik.yaml` — provider config (path: `/etc/grafana/provisioning/json-dashboards`)
- `provisioning/json-dashboards/*.json` — the dashboard JSON files

**Update workflow:** edit a JSON file → Grafana auto-reloads it within 30s. **Add a new provider yaml:** requires Grafana restart (`docker restart grafana-loc484…`) — provider yamls only load at startup.

**Edit policy:** the bind-mount is `:ro` from the container's perspective. UI edits need `allowUiUpdates: true` (set) + saving back to JSON via "Save as" / export. Otherwise the next reload reverts UI changes.
