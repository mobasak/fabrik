# VPS Status

**Last Updated:** 2026-05-07 13:00 UTC+3
**Host:** vps1.ocoron.com (172.93.160.197)
**Provider:** Psychz Networks (AS32421) — Los Angeles, CA, USA
**SSH:** `ssh vps` (ozgur@vps1.ocoron.com, Ed25519 key-only, root disabled)
**Coolify:** v4.0.0-beta.459 (fully patched — CVEs fixed in beta.451+)

---

## System Overview

<!-- AUTO:system_overview -->
| **Containers running** | 40 |
| **Disk** | 108G total, 39G used, 69G free (37%) |
| **Memory** | 11GB total, ~5GB available |
| **Uptime** | up 7 weeks |
| **Last snapshot** | 2026-05-07 13:00 UTC |
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
| Port | Action | Purpose |
|---|---|---|
| 22/tcp | ALLOW | SSH — Ed25519 key only |
| 80/tcp | ALLOW | HTTP → Traefik → HTTPS |
| 443/tcp | ALLOW | HTTPS + OpenVPN |
| 1194/tcp | ALLOW | OpenVPN (kernel service) |
| 6001/tcp | ALLOW | Coolify Realtime / Soketi WebSocket |
| 6002/tcp | ALLOW | Coolify Realtime / Soketi WebSocket |
| 8000/tcp | **DENY** | Coolify raw — use `coolify.vps1.ocoron.com` |
<!-- /AUTO -->

---

## Container Status (40 running)

<!-- AUTO:container_status -->
### Coolify Platform (6)
| Container | Status | Notes |
|---|---|---|
| `coolify` | ✅ Up 2 weeks | UI via `coolify.vps1.ocoron.com` (Authelia + TOTP) |
| `coolify-proxy` (Traefik v3.6) | ✅ Up 2 weeks | 80, 443, 127.0.0.1:8080 |
| `coolify-realtime` (Soketi) | ✅ Up 2 weeks | 6001-6002, Coolify UI live logs |
| `coolify-db` | ✅ Up 2 weeks | Internal Coolify PostgreSQL |
| `coolify-redis` | ✅ Up 2 weeks | Internal Coolify Redis |
| `coolify-sentinel` | ✅ healthy | Redis Sentinel |

### Security (1)
| Container | Status | Limit | URL |
|---|---|---|---|
| `authelia` | ✅ healthy | 512m | `auth.vps1.ocoron.com` |

### Observability (9)
| Container | Status | Limit | Notes |
|---|---|---|---|
| `grafana` | ✅ healthy | 512m | `monitor.vps1.ocoron.com` (Authelia) |
| `prometheus` | ✅ healthy | 1g | 30d + 5GB retention; `--web.enable-lifecycle` |
| `loki` | ✅ healthy | 512m | 7-day retention; `loki:3100` |
| `promtail` | ✅ Up | 128m | Ships logs → Loki |
| `cadvisor` | ✅ healthy | 512m | `--docker_only=true`; fixed stale cgroup noise |
| `node-exporter` | ✅ Up | 128m | Host metrics |
| `alertmanager` | ✅ healthy | 256m | Telegram receiver; `group_by: [alertname, container]` |
| `netdata` | ✅ healthy | 768m | 512MB disk / 7-day retention; `netdata.vps1.ocoron.com` |
| `gatus` | ✅ Up | 256m | `status.vps1.ocoron.com` (open) |

### Shared Data (2)
| Container | Status | Limit | Address |
|---|---|---|---|
| `postgres-main` | ✅ healthy | 2g | `postgres-main:5432` |
| `redis-main` | ✅ healthy | 512m | `redis-main:6379` (Authelia sessions on DB 3) |

### Fabrik Services (11)
| Container | Status | Limit | Auth | URL |
|---|---|---|---|---|
| `fabrik-proxy` | ✅ healthy | 512m | X-Internal-Token | `proxy.vps1.ocoron.com` |
| `fabrik-captcha` | ✅ healthy | 512m | X-Internal-Token | `captcha.vps1.ocoron.com` |
| `fabrik-image-broker` | ✅ healthy | 512m | X-Internal-Token | `images.vps1.ocoron.com` |
| `fabrik-translator` | ✅ healthy | 512m | X-Internal-Token | `translator.vps1.ocoron.com` |
| `fabrik-emailgateway` | ✅ healthy | 512m | X-Internal-Token + legacy Bearer | `emailgateway.vps1.ocoron.com` |
| `fabrik-file-api` | ✅ Up | 1g | Supabase Bearer JWT | `files-api.vps1.ocoron.com` |
| `fabrik-file-worker` | ✅ Up | 1g | — | internal |
| `fabrik-site-provisioner` | ✅ healthy | 512m | IP allowlist | `provision.vps1.ocoron.com` |
| `fabrik-n8n` | ✅ healthy | 2g | Authelia | `auto.vps1.ocoron.com` |
| `fabrik-glitchtip-web` | ✅ Up | 512m | Authelia | `errors.vps1.ocoron.com` |
| `fabrik-glitchtip-worker` | ✅ Up | 512m | — | internal |

### Utilities (3)
| Container | Status | Limit | URL |
|---|---|---|---|
| `apprise` | ✅ healthy | 512m | `notify.vps1.ocoron.com` (Authelia) |
| `backrest` | ✅ Up | 512m | `backup.vps1.ocoron.com` (Authelia) |
| `meilisearch` | ✅ healthy | 512m | `search.vps1.ocoron.com` |

### Other (2)
| Container | Status | Limit | URL |
|---|---|---|---|
| `browserless` | ✅ Up | 2g | `browser.vps1.ocoron.com` |
| `pdf-service` | ✅ healthy | 512m | `pdf.vps1.ocoron.com` |

### WordPress — ocoron.com (5)
| Container | Status | Limit |
|---|---|---|
| `ocoron-com-nginx-1` | ✅ Up | 256m |
| `ocoron-com-wordpress-1` | ✅ Up | 512m |
| `ocoron-com-db-1` (MariaDB) | ✅ healthy | 1g |
| `ocoron-com-redis-1` | ✅ healthy | 256m |
| `ocoron-com-backup-1` | ✅ Up | — |
<!-- /AUTO -->

---

## Traefik Middleware Registry

<!-- AUTO:traefik_middlewares -->
| Middleware | Type | Applied to |
|---|---|---|
| `authelia-forward@docker` | forwardauth | All admin dashboards |
| `gzip@docker` | compress | All routes (scaffold wires automatically) |
| `redirect-to-https@docker` | redirectscheme | All HTTP → HTTPS |
| `site-provisioner-ipallowlist@docker` | ipallowlist | site-provisioner only |
| `ocoron-com-rate-limit@docker` | ratelimit | WordPress protection |
| `ocoron-com-block-xmlrpc@docker` | replacepathregex | WordPress xmlrpc block |
| `ocoron-com-www-redirect@docker` | redirectregex | www → non-www |
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
| `fabrik-services` | (targets commented — wire as services add `/metrics`) | 30s |

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

---

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
For new single-image Application: see `CROSS_CUTTING_REQUIREMENTS.md §9`.

## Resource Limits

<!-- AUTO:limits_summary -->
**Two mechanisms — Coolify API (persists through redeploys) for Fabrik apps; `docker update` (resets on reboot) for infra.**

After any VPS reboot: `ssh vps "bash /opt/fabrik/scripts/vps_apply_limits.sh"`

| Service | Memory | Mechanism |
|---|---|---|
| fabrik-proxy, captcha, image-broker, emailgateway, translator, site-provisioner | 512m | Coolify API |
| fabrik-file-api, file-worker | 1g | Coolify API |
| fabrik-n8n | 2g | Coolify API |
| glitchtip-web, glitchtip-worker, grafana, loki, authelia, backrest, apprise, meilisearch | 512m | docker update |
| postgres-main | 2g | docker update |
| netdata | 768m | docker update |
| redis-main | 512m | docker update |
| prometheus | 1g | docker update |
| alertmanager, gatus, traefik | 256m | docker update |
| node-exporter, promtail | 128m | docker update |
| ocoron-com-db-1 | 1g | docker update |
| ocoron-com-wordpress-1 | 512m | docker update |
| ocoron-com-nginx-1, ocoron-com-redis-1 | 256m | docker update |
| browserless | 2g | Coolify API |
<!-- /AUTO -->

---

## Authelia Access Control (8 rules)

| Domain | Policy | Path restriction |
|---|---|---|
| `ocoron.com`, `www.ocoron.com` | bypass | all paths |
| `wp-test.vps1.ocoron.com`, `status.vps1.ocoron.com` | bypass | all paths |
| `*.vps1.ocoron.com` | bypass | `/health`, `/healthz`, `/metrics`, `/api/health` only |
| `pdf, browser, search, images, captcha, proxy, translator, files-api, emailgateway, dns, errors` `.vps1.ocoron.com` | bypass | all paths (app-layer auth) |
| `coolify.vps1.ocoron.com`, `monitor.vps1.ocoron.com` | bypass | `^/api/` only |
| `*.vps1.ocoron.com` | two_factor | everything else |

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

## Known Issues

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
