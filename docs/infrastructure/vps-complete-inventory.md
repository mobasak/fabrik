# VPS Complete Service Inventory

**Last Updated:** 2026-05-07 12:00 UTC+3
**Method:** SSH + docker ps + Coolify API + live verification
**Total Containers:** 40 running
**VPS:** vps1.ocoron.com (172.93.160.197) — Ubuntu 24.04 LTS, 6 vCores (x86_64), 11GB RAM, 108GB disk
**Coolify:** v4.0.0-beta.459 — fully patched (CVEs fixed in beta.451+)

---

## How to Re-verify This Document

```bash
ssh vps "sudo docker ps --format '{{.Names}}\t{{.Status}}\t{{.Ports}}' | sort"
ssh vps "sudo docker inspect \$(sudo docker ps -q) --format '{{.Name}} {{.HostConfig.Memory}}' | sort"
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
    │                  ├─► authelia-forward@docker (TOTP 2FA for admin UIs)
    │                  ├─► coolify.vps1.ocoron.com    Admin UI
    │                  ├─► monitor / netdata / auto    Observability + automation
    │                  ├─► errors / backup / notify    Ops tools
    │                  ├─► auth.vps1.ocoron.com       Authelia SSO
    │                  ├─► proxy/captcha/images/translator/emailgateway  X-Internal-Token
    │                  ├─► files-api                  Supabase Bearer JWT
    │                  ├─► provision                  IP allowlist
    │                  └─► ocoron.com / www            WordPress
    ├─ 80/tcp ───► Traefik → HTTPS redirect
    ├─ 22/tcp ───► SSH (Ed25519 key, root disabled)
    ├─ 1194/tcp ─► OpenVPN
    ├─ 6001-6002 ► Coolify Realtime/Soketi (Coolify UI live logs)
    └─ 8000/tcp ─► UFW DENY
```

### Docker Networks
| Network | Subnet | Purpose |
|---|---|---|
| `coolify` | 10.0.1.0/24 | All Coolify-managed containers |
| Host | 172.93.160.197 | Public IP — Traefik on 80/443 only |

---

## Traefik Configuration

**Version:** v3.6 | **Config:** `/data/coolify/proxy/` | **Dynamic config:** `/data/coolify/proxy/dynamic/`
**SSL:** Let's Encrypt HTTP challenge | `acme.json`: `/data/coolify/proxy/acme.json`
**Gzip config:** `/data/coolify/proxy/dynamic/gzip.yaml` (hot-reload)

### Middlewares
<!-- AUTO:traefik_middlewares -->
| Middleware | Type | Purpose |
|---|---|---|
| `authelia-forward@docker` | forwardauth | → `http://authelia:9091/api/authz/forward-auth` |
| `gzip@docker` | compress | Global gzip — wire per-router in Coolify settings |
| `redirect-to-https@docker` | redirectscheme | HTTP → HTTPS |
| `site-provisioner-ipallowlist@docker` | ipallowlist | VPS + internal Docker ranges only |
| `ocoron-com-rate-limit@docker` | ratelimit | WordPress rate limiting |
| `ocoron-com-block-xmlrpc@docker` | replacepathregex | WordPress xmlrpc protection |
| `ocoron-com-www-redirect@docker` | redirectregex | www → non-www |
<!-- /AUTO -->

---

## Firewall (UFW)

<!-- AUTO:ufw_rules -->
| Port | Action | Purpose |
|---|---|---|
| 22/tcp | ALLOW | SSH — Ed25519 key only, root disabled |
| 80/tcp | ALLOW | HTTP → Traefik → HTTPS redirect |
| 443/tcp | ALLOW | HTTPS + OpenVPN |
| 1194/tcp | ALLOW | OpenVPN (kernel service) |
| 6001-6002/tcp | ALLOW | Coolify Realtime / Soketi WebSocket |
| 8000/tcp | **DENY** | Coolify raw port — use `coolify.vps1.ocoron.com` |
<!-- /AUTO -->

---

## Authelia Configuration

**Container:** `authelia-hks48k8sg8o4co4co08co00o`
**Config:** `/var/lib/docker/volumes/hks48k8sg8o4co4co08co00o_authelia-config/_data/configuration.yml`
**Sessions:** `redis-main:6379` DB index 3 (persistent across restarts)
**TOTP:** `ocoron.com`, 30s period
**Storage:** SQLite `/config/db.sqlite3`

### Access Control (8 rules)
| Domain | Policy | Note |
|---|---|---|
| `ocoron.com`, `www.ocoron.com` | bypass | WordPress public |
| `wp-test.vps1.ocoron.com`, `status.vps1.ocoron.com` | bypass | Public read-only |
| `*.vps1.ocoron.com` | bypass | `/health`, `/healthz`, `/metrics`, `/api/health` paths |
| API services (11 domains) | bypass | `pdf, browser, search, images, captcha, proxy, translator, files-api, emailgateway, dns, errors` |
| `coolify.vps1.ocoron.com`, `monitor.vps1.ocoron.com` | bypass | `^/api/` paths only |
| `*.vps1.ocoron.com` | two_factor | Everything else |

**⚠️ Authelia does NOT hot-reload on SIGHUP — it exits.**
After any config change: `ssh vps "sudo docker restart authelia-hks48k8sg8o4co4co08co00o"`

---

## M2M Authentication (Option A — 2026-05-07)

| Component | Value |
|---|---|
| Header | `X-Internal-Token` |
| Env var | `SERVICE_INTERNAL_SECRET_KEY` |
| Key location | `/opt/fabrik/.env` |
| Module | `internal_auth.py` in each service's `app/` or `src/` |
| Python import | `from app.internal_auth import require_internal_token` (if `uvicorn app.main:app`) |
| Python import | `from internal_auth import require_internal_token` (if `uvicorn api:app` from root) |
| Node.js | `timingSafeEqual` in middleware against `process.env.SERVICE_INTERNAL_SECRET_KEY` |
| Validation | constant-time (hmac.compare_digest / timingSafeEqual) |

**Deployed:** captcha, image-broker, translator, proxy, emailgateway
**Exempt:** file-api (Supabase user auth), site-provisioner (IP allowlist)
**Pre-placed:** `internal_auth.py` in 35 FastAPI projects under `/opt`

---

## Complete Container Inventory

<!-- AUTO:container_inventory -->
### 1. Coolify Platform (6)
| Container | Memory | Notes |
|---|---|---|
| `coolify` | — | UI via `coolify.vps1.ocoron.com`, raw 8000 UFW-blocked |
| `coolify-proxy` (Traefik v3.6) | — | 80, 443, 127.0.0.1:8080 |
| `coolify-realtime` (Soketi) | — | 6001-6002, Coolify UI live logs |
| `coolify-db` | — | Internal Coolify PostgreSQL |
| `coolify-redis` | — | Internal Coolify Redis |
| `coolify-sentinel` | — | Redis Sentinel |

### 2. Security (1)
| Container | Memory | URL |
|---|---|---|
| `authelia` | 512m | `auth.vps1.ocoron.com` |

### 3. Observability (9)
| Container | Memory | Access |
|---|---|---|
| `grafana` | 512m | `monitor.vps1.ocoron.com` (Authelia) |
| `prometheus` | 1g | internal — scrapes all containers |
| `loki` | 512m | internal `loki:3100` |
| `promtail` | 128m | internal — ships logs to Loki |
| `cadvisor` | 512m | internal — container metrics; flags: `--docker_only=true --disable_metrics=sched,tcp,udp,percpu,advtcp,hugetlb,...` |
| `node-exporter` | 128m | internal — host metrics |
| `alertmanager` | 256m | internal — receives Prometheus alerts |
| `netdata` | 768m | `netdata.vps1.ocoron.com` (Authelia) |
| `gatus` | 256m | `status.vps1.ocoron.com` (open) |

### 4. Data Services (2)
| Container | Memory | Address | Databases |
|---|---|---|---|
| `postgres-main` | 2g | `postgres-main:5432` | `proxy_management`, `translator_service`, etc. |
| `redis-main` | 512m | `redis-main:6379` | cache + Authelia sessions (DB 3) |

### 5. Fabrik Services (11)
| Container | Memory | URL | Auth |
|---|---|---|---|
| `fabrik-proxy` | 512m | `proxy.vps1.ocoron.com` | X-Internal-Token |
| `fabrik-captcha` | 512m | `captcha.vps1.ocoron.com` | X-Internal-Token |
| `fabrik-image-broker` | 512m | `images.vps1.ocoron.com` | X-Internal-Token |
| `fabrik-translator` | 512m | `translator.vps1.ocoron.com` | X-Internal-Token |
| `fabrik-emailgateway` | 512m | `emailgateway.vps1.ocoron.com` | X-Internal-Token + legacy Bearer |
| `fabrik-file-api` | 1g | `files-api.vps1.ocoron.com` | Supabase Bearer JWT |
| `fabrik-file-worker` | 1g | internal | — |
| `fabrik-site-provisioner` | 512m | `provision.vps1.ocoron.com` | IP allowlist |
| `fabrik-n8n` | 2g | `auto.vps1.ocoron.com` | Authelia |
| `fabrik-glitchtip-web` | 512m | `errors.vps1.ocoron.com` | Authelia |
| `fabrik-glitchtip-worker` | 512m | internal | — |

### 6. Utilities (3)
| Container | Memory | URL | Notes |
|---|---|---|---|
| `apprise` | 512m | `notify.vps1.ocoron.com` (Authelia) | Notification hub |
| `backrest` | 512m | `backup.vps1.ocoron.com` (Authelia) | Restic → Backblaze B2 |
| `meilisearch` | 512m | `search.vps1.ocoron.com` | Full-text search |

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

## Resource Limits

<!-- AUTO:limits_summary -->
**Two mechanisms — never confuse:**
| Mechanism | Applies to | Survives reboot | Script |
|---|---|---|---|
| Coolify API `limits_memory`/`limits_cpus` | Fabrik applications | ✅ yes | `fabrik apply` |
| `docker update --memory` | Infra service stacks | ❌ no | `scripts/vps_apply_limits.sh` |

**Why docker update for infra:** Coolify v4 rejects `limits_memory` for service stacks (422) — can't target sub-containers. `docker update` is the correct path.

**After any VPS reboot:** `ssh vps "bash /opt/fabrik/scripts/vps_apply_limits.sh"`
<!-- /AUTO -->

---

## Operational Lessons (Hard-Won)

| # | Incident | Rule codified in governance |
|---|---|---|
| 1 | translator crash: `localhost` in DATABASE_URL | `DB_HOST=postgres-main`, `REDIS_URL=redis://redis-main:6379` everywhere |
| 2 | SIGHUP to Authelia → exits → all Traefik routes 404 | `docker restart <authelia>` after config changes — never SIGHUP |
| 3 | cadvisor OOM at 256m (91% RSS) | 512m + `--docker_only=true --disable_metrics=...` |
| 4 | prometheus OOM at 512m (93% RSS) | 1g minimum |
| 5 | apprise OOM-prone at 256m | 512m |
| 6 | `yaml.dump` corrupted Authelia regex patterns | Use targeted replacements, never roundtrip full YAML |
| 7 | governance hook injected bare `internal_auth` imports | Rule files propagate docs, not code imports |
| 8 | `fabrik redeploy` without git push deploys stale code | `git commit → git push → fabrik redeploy` always |
| 9 | Per-service X-API-Key chaos with different env var names | One key: `SERVICE_INTERNAL_SECRET_KEY`; one header: `X-Internal-Token` |
| 10 | import path must match uvicorn module path | `uvicorn app.main:app` → `from app.internal_auth import` |

---

## Security Posture Summary

<!-- AUTO:coolify_apps -->
| Layer | Status | Detail |
|---|---|---|
| SSH | ✅ | Ed25519 key-only, root disabled, password auth off |
| UFW | ✅ | 8000 DENY, minimal rules |
| Traefik | ✅ | Dashboard localhost-only |
| Authelia | ✅ | TOTP 2FA, Redis sessions, 8 rules (no stale test rules) |
| M2M auth | ✅ | X-Internal-Token + SERVICE_INTERNAL_SECRET_KEY |
| Resource limits | ✅ | All 40 containers |
| .dockerignore | ✅ | Added to all projects |
| Coolify CVEs | ✅ | beta.459, patched |
| SSL | ⚠️ | Per-service HTTP challenge — TODO wildcard via Cloudflare DNS |
| Gzip | ✅ | Registered; wire to routers |
<!-- /AUTO -->

---

## Pending Actions

| # | Action | Priority |
|---|---|---|
| 1 | Wildcard SSL → Coolify → Proxy → Cloudflare DNS challenge resolver | Low |
| 2 | Wire `gzip@docker` to high-traffic routers in Coolify UI | Low |
| 3 | Monitor swap (currently ~85%, 1.7GB/2GB) | Watch |
