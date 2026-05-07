# VPS Complete Service Inventory

**Last Updated:** 2026-05-07 13:00 UTC+3
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
| Port | Action | Purpose |
|---|---|---|
| 22/tcp | ALLOW | SSH — Ed25519 key only, root disabled |
| 80/tcp | ALLOW | HTTP → Traefik → HTTPS |
| 443/tcp | ALLOW | HTTPS + OpenVPN |
| 1194/tcp | ALLOW | OpenVPN (kernel service) |
| 6001-6002/tcp | ALLOW | Coolify Realtime / Soketi WebSocket |
| 8000/tcp | **DENY** | Coolify raw port — use `coolify.vps1.ocoron.com` |
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

---

## Complete Container Inventory

<!-- AUTO:container_inventory -->
### 1. Coolify Platform (6)
| Container | Memory | Notes |
|---|---|---|
| `coolify` | — | UI: `coolify.vps1.ocoron.com`; 8000 UFW-blocked |
| `coolify-proxy` (Traefik v3.6) | — | 80, 443, 127.0.0.1:8080 |
| `coolify-realtime` (Soketi) | — | 6001-6002 |
| `coolify-db` | — | Internal PostgreSQL |
| `coolify-redis` | — | Internal Redis |
| `coolify-sentinel` | — | Redis Sentinel |

### 2. Security (1)
| Container | Memory | URL |
|---|---|---|
| `authelia` | 512m | `auth.vps1.ocoron.com` |

### 3. Observability (9)
| Container | Memory | Notes |
|---|---|---|
| `grafana` | 512m | `monitor.vps1.ocoron.com` (Authelia) |
| `prometheus` | 1g | 30d+5GB; `--web.enable-lifecycle`; `/opt/prometheus/compose.yaml` |
| `loki` | 512m | 7-day; `loki:3100` |
| `promtail` | 128m | Ships logs → Loki |
| `cadvisor` | 512m | `--docker_only=true --disable_metrics=sched,tcp,udp,percpu,advtcp,hugetlb,...` |
| `node-exporter` | 128m | Host metrics |
| `alertmanager` | 256m | Telegram; group_by alertname+container |
| `netdata` | 768m | 512MB/7d; `netdata.vps1.ocoron.com` |
| `gatus` | 256m | `status.vps1.ocoron.com` (open) |

### 4. Shared Data (2)
| Container | Memory | Address |
|---|---|---|
| `postgres-main` | 2g | `postgres-main:5432` |
| `redis-main` | 512m | `redis-main:6379` |

### 5. Fabrik Services (11)
| Container | Memory | URL | Auth | DB |
|---|---|---|---|---|
| `fabrik-proxy` | 512m | `proxy.vps1.ocoron.com` | X-Internal-Token | `proxy_management` |
| `fabrik-captcha` | 512m | `captcha.vps1.ocoron.com` | X-Internal-Token | — |
| `fabrik-image-broker` | 512m | `images.vps1.ocoron.com` | X-Internal-Token | — |
| `fabrik-translator` | 512m | `translator.vps1.ocoron.com` | X-Internal-Token | `translator_service` |
| `fabrik-emailgateway` | 512m | `emailgateway.vps1.ocoron.com` | X-Internal-Token + legacy Bearer | — |
| `fabrik-file-api` | 1g | `files-api.vps1.ocoron.com` | Supabase Bearer JWT | external |
| `fabrik-file-worker` | 1g | internal | — | — |
| `fabrik-site-provisioner` | 512m | `provision.vps1.ocoron.com` | IP allowlist | — |
| `fabrik-n8n` | 2g | `auto.vps1.ocoron.com` | Authelia | — |
| `fabrik-glitchtip-web` | 512m | `errors.vps1.ocoron.com` | Authelia | — |
| `fabrik-glitchtip-worker` | 512m | internal | — | — |

### 6. Utilities (3)
| Container | Memory | URL |
|---|---|---|
| `apprise` | 512m | `notify.vps1.ocoron.com` (Authelia) |
| `backrest` | 512m | `backup.vps1.ocoron.com` (Authelia) |
| `meilisearch` | 512m | `search.vps1.ocoron.com` |

### 7. Other (2)
| Container | Memory | URL |
|---|---|---|
| `browserless` | 2g | `browser.vps1.ocoron.com` |
| `pdf-service` | 512m | `pdf.vps1.ocoron.com` |

### 8. WordPress — ocoron.com (5)
| Container | Memory |
|---|---|
| `ocoron-com-nginx-1` | 256m |
| `ocoron-com-wordpress-1` | 512m |
| `ocoron-com-db-1` (MariaDB) | 1g |
| `ocoron-com-redis-1` | 256m |
| `ocoron-com-backup-1` | — |
<!-- /AUTO -->

---

## Resource Limits Reference

<!-- AUTO:limits_summary -->
**Two mechanisms:**
| Mechanism | Applies to | Survives reboot | Script |
|---|---|---|---|
| Coolify API `limits_memory`/`limits_cpus` | Fabrik applications | ✅ yes | `fabrik apply` |
| `docker update --memory` | Infra service stacks | ❌ no | `scripts/vps_apply_limits.sh` |

**Why docker update for infra:** Coolify v4 rejects `limits_memory` for service stacks (422 — can't target sub-containers).

**After any VPS reboot:** `ssh vps "bash /opt/fabrik/scripts/vps_apply_limits.sh"`
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
| Layer | Status | Notes |
|---|---|---|
| SSH | ✅ | Ed25519 key-only, root disabled |
| UFW | ✅ | 8000 DENY, minimal rules |
| Traefik | ✅ | Dashboard localhost-only |
| Authelia | ✅ | TOTP 2FA, Redis sessions, 8 rules, no stale test rules |
| M2M auth | ✅ | X-Internal-Token on all 5 API services |
| Resource limits | ✅ | All 40 containers |
| .dockerignore | ✅ | All projects |
| Coolify CVEs | ✅ | beta.459 |
| Observability retention | ✅ | Prometheus 30d+5GB, Loki 7d, Netdata 512MB/7d |
| Business metrics | 🔵 | Scaffold emits metrics.py; wire existing services manually |
| SSL | ⚠️ | Per-service HTTP challenge — TODO wildcard Cloudflare |
| Gzip | ✅ | Registered; scaffold wires to new services |
<!-- /AUTO -->

---

## Pending Actions

| # | Action | Priority |
|---|---|---|
| 1 | Wildcard SSL → Coolify → Proxy → Cloudflare DNS resolver | Low |
| 2 | Add `/metrics` to 5 existing deployed services | Low (on next touch) |
| 3 | Monitor swap usage (~1.7GB/2GB) | Watch |
