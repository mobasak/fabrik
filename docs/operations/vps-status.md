# VPS Status

**Last Updated:** 2026-05-08 16:52 UTC
**Host:** vps1.ocoron.com (172.93.160.197)
**Provider:** Psychz Networks (AS32421) — Los Angeles, CA, USA
**SSH:** `ssh vps` (ozgur@vps1.ocoron.com, Ed25519 key-only, root disabled)
**Coolify:** v4.0.0-beta.459 (fully patched — CVEs fixed in beta.451+)

---

## System Overview

<!-- AUTO:system_overview -->
| **Containers running** | 40 |
| **Disk** | 108G total, 39G used, 69G free (36%) |
| **Memory** | 11Gi total, 4.3Gi used, 480Mi free |
| **Uptime** | up 7 weeks, 1 day, 18 hours, 32 minutes |
| **Last snapshot** | 2026-05-08 16:52 UTC |
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

## Container Status (40 running)

<!-- AUTO:container_status -->
| Container | Status | Memory limit |
|---|---|---|
| `alertmanager-zw4swgkwk0s4s8kg048gw80o` | ✅ Up 2 weeks (healthy) | 256m |
| `apprise-lcocgs4gs8ksg4g08w40ows8` | ✅ Up 2 weeks (healthy) | 512m |
| `authelia-hks48k8sg8o4co4co08co00o` | ✅ Up 31 hours (healthy) | — |
| `backrest-l48000k44wc4gk8os88s8k0c` | ✅ Up 4 days | 512m |
| `bs0wo48k4gwo440gcowscoc8-150802066640` | ✅ Up 2 weeks (healthy) | 512m |
| `cadvisor-r08sog4gwws88og048ows448` | ✅ Up 32 hours (healthy) | — |
| `captcha-j8gg4ggskkossc4gkwowk4os-084910621771` | ✅ Up 32 hours (healthy) | — |
| `coolify` | ✅ Up 2 weeks (healthy) | — |
| `coolify-db` | ✅ Up 2 weeks (healthy) | — |
| `coolify-proxy` | ✅ Up 2 weeks (healthy) | — |
| `coolify-realtime` | ✅ Up 2 weeks (healthy) | — |
| `coolify-redis` | ✅ Up 2 weeks (healthy) | — |
| `coolify-sentinel` | ✅ Up 53 minutes (healthy) | — |
| `e04k4sco44ow04ccc0o0k00k-151256201601` | ✅ Up 2 weeks (healthy) | 512m |
| `emailgateway-w4oocckkwko8kowggsw8sogc-083819438364` | ✅ Up 32 hours (healthy) | — |
| `fabrik-proxy-zsccsksoc8sssc8k00sgcc08-105616821752` | ✅ Up 30 hours (healthy) | — |
| `file-api-bsswwg4kg480c000gksw004k-140449896537` | ✅ Up 2 weeks | 1g |
| `file-worker-nwcckwggw0o0g40gwskk8kk8-154849864122` | ✅ Up 4 days | 1g |
| `gatus-v8s4cokcwg0co4w8okkccc0w` | ✅ Up 2 days | 256m |
| `glitchtip-web-z00kkck8c8cwo800kk440csk` | ✅ Up 2 weeks | 512m |
| `glitchtip-worker-msgo0sg8gsgo4w4sscckc84g` | ✅ Up 2 weeks | 512m |
| `grafana-loc484owg8gsw04owo0go8kc` | ✅ Up 29 hours (healthy) | — |
| `image-broker-zo4ggs4g880skwkocwwkscgk-084711841807` | ✅ Up 32 hours (healthy) | — |
| `loki-r48swckog008wosgwcs4g0g0` | ✅ Up 2 weeks (healthy) | 512m |
| `n8n-s8gwccsws0ccssw0wwgwsoks` | ✅ Up 2 weeks (healthy) | 2g |
| `netdata-kk4kcw4csksc48848go4o0wo` | ✅ Up 31 hours (healthy) | — |
| `node-exporter-doc8c8gkcgs88s8ckggw84o4` | ✅ Up 2 weeks | 128m |
| `ocoron-com-backup-1` | ✅ Up 2 weeks | — |
| `ocoron-com-db-1` | ✅ Up 2 weeks (healthy) | 1g |
| `ocoron-com-nginx-1` | ✅ Up 2 weeks | 256m |
| `ocoron-com-redis-1` | ✅ Up 2 weeks (healthy) | 256m |
| `ocoron-com-wordpress-1` | ✅ Up 2 weeks | 512m |
| `postgres-main-l0k4gk0kggc8okcwk0s4c8s8` | ✅ Up 2 weeks (healthy) | 2g |
| `prometheus` | ✅ Up 31 hours (healthy) | — |
| `promtail-w0000ckgsgg048w0848okk08` | ✅ Up 29 hours | 128m |
| `redis-main` | ✅ Up 2 weeks (healthy) | 512m |
| `site-provisioner-qokoksogwsk0c04gcs4swwgs-143727579258` | ✅ Up 2 weeks (healthy) | 512m |
| `traefik` | ✅ Up 2 weeks | 256m |
| `translator-kgws0s4cscsosw8gg848cwgw-084335048255` | ✅ Up 32 hours (healthy) | — |
| `vckgs8c00o40o884k48cgow8-220643454460` | ✅ Up 4 days | 2g |
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
For new single-image Application: see `CROSS_CUTTING_REQUIREMENTS.md §9`.

## Resource Limits

<!-- AUTO:limits_summary -->
| Container | Memory |
|---|---|
| `alertmanager-zw4swgkwk0s4s8kg048gw80o` | 256m |
| `apprise-lcocgs4gs8ksg4g08w40ows8` | 512m |
| `backrest-l48000k44wc4gk8os88s8k0c` | 512m |
| `bs0wo48k4gwo440gcowscoc8-150802066640` | 512m |
| `e04k4sco44ow04ccc0o0k00k-151256201601` | 512m |
| `file-api-bsswwg4kg480c000gksw004k-140449896537` | 1g |
| `file-worker-nwcckwggw0o0g40gwskk8kk8-154849864122` | 1g |
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
| `site-provisioner-qokoksogwsk0c04gcs4swwgs-143727579258` | 512m |
| `traefik` | 256m |
| `vckgs8c00o40o884k48cgow8-220643454460` | 2g |
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
