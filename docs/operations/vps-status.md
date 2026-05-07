# VPS Status

**Last Updated:** 2026-05-07 12:00 UTC+3
**Host:** vps1.ocoron.com (172.93.160.197)
**Provider:** Psychz Networks (AS32421) — Los Angeles, CA, USA
**SSH:** `ssh vps` (ozgur@vps1.ocoron.com, Ed25519 key-only, root disabled)
**Coolify:** v4.0.0-beta.459 (fully patched — CVEs fixed in beta.451+)

---

## System Overview

<!-- AUTO:system_overview -->
| **Containers running** | 40 |
| **Disk** | 108G total, 39G used, 69G free (37%) |
| **Memory** | 11GB total, ~5GB available, 2GB swap |
| **Uptime** | up 7 weeks |
| **Last snapshot** | 2026-05-07 12:00 UTC |
<!-- /AUTO -->

| **OS** | Ubuntu 24.04 LTS |
| **CPU** | 6 vCores (x86_64) |
| **Docker** | Engine (not Desktop), cgroupv2 |
| **Coolify** | v4.0.0-beta.459 |

### Storage Notes
- All backups → Backblaze B2 via Backrest (Restic)
- Build cache cleared 2026-05-06 (775MB reclaimable as of 2026-05-07)
- Monitor `/var/lib/docker` — run `docker image prune -af` monthly
- Alert threshold: 70% disk usage

---

## Security Posture

| Layer | Status | Detail |
|---|---|---|
| **SSH** | ✅ | Ed25519 key-only; root login disabled; password auth disabled |
| **UFW** | ✅ | Active; port 8000 DENY; minimal rules |
| **Traefik dashboard** | ✅ | Bound to `127.0.0.1:8080` — localhost only |
| **Coolify UI (8000)** | ✅ BLOCKED | UFW DENY; use `coolify.vps1.ocoron.com` via Traefik |
| **Authelia** | ✅ | Forward-auth on all admin dashboards; TOTP 2FA enforced |
| **Redis sessions** | ✅ | Authelia sessions on `redis-main` DB index 3 (survive restarts) |
| **API services M2M** | ✅ | `X-Internal-Token` header + `SERVICE_INTERNAL_SECRET_KEY` |
| **file-api** | ✅ | Supabase Bearer JWT (user auth, not M2M) |
| **site-provisioner** | ✅ | Traefik IP allowlist (VPS + internal Docker nets only) |
| **Resource limits** | ✅ | All 40 containers limited (Coolify API + docker update) |
| **Gzip compression** | ✅ | `gzip@docker` middleware registered in Traefik dynamic config |
| **SSL** | ⚠️ | Per-service Let's Encrypt HTTP challenge; TODO: Cloudflare DNS wildcard |
| **CrowdSec** | — | Not deployed; acceptable for solo operator; revisit at first public product |
| **Coolify CVEs** | ✅ | Running beta.459 (CVEs in beta.451 and earlier fixed) |

### Firewall (UFW)

<!-- AUTO:ufw_rules -->
| Port | Action | Purpose |
|---|---|---|
| 22/tcp | ALLOW | SSH (Ed25519 key only) |
| 80/tcp | ALLOW | HTTP → Traefik → redirects to HTTPS |
| 443/tcp | ALLOW | HTTPS + OpenVPN |
| 1194/tcp | ALLOW | OpenVPN (kernel service) |
| 6001/tcp | ALLOW | Coolify Realtime WebSocket (Soketi — Coolify UI log streaming) |
| 6002/tcp | ALLOW | Coolify Realtime WebSocket |
| 8000/tcp | **DENY** | Coolify raw port — blocked; use `coolify.vps1.ocoron.com` |
<!-- /AUTO -->

---

## Container Status

<!-- AUTO:container_status -->
### Coolify Platform (6 containers)
| Container | Status | Notes |
|---|---|---|
| `coolify` | ✅ Up 2 weeks | Accessible via `coolify.vps1.ocoron.com` (Authelia-gated) |
| `coolify-proxy` | ✅ Up 2 weeks | Traefik v3.6 reverse proxy |
| `coolify-realtime` | ✅ Up 2 weeks | Soketi WebSocket (Coolify UI live logs on 6001-6002) |
| `coolify-db` | ✅ Up 2 weeks | Coolify internal PostgreSQL |
| `coolify-redis` | ✅ Up 2 weeks | Coolify internal Redis |
| `coolify-sentinel` | ✅ Up | Redis Sentinel |

### Infrastructure (14 containers)
| Container | Status | Limit | Auth | URL |
|---|---|---|---|---|
| `authelia` | ✅ healthy | 512m | — | `auth.vps1.ocoron.com` |
| `traefik` | ✅ Up | 256m | — | `127.0.0.1:8080` (local only) |
| `postgres-main` | ✅ healthy | 2g | app credentials | internal only |
| `redis-main` | ✅ healthy | 512m | — | internal only |
| `grafana` | ✅ healthy | 512m | Authelia | `monitor.vps1.ocoron.com` |
| `prometheus` | ✅ healthy | 1g | — | internal only |
| `loki` | ✅ healthy | 512m | — | internal only |
| `promtail` | ✅ Up | 128m | — | internal only |
| `cadvisor` | ✅ healthy | 512m | — | internal only |
| `node-exporter` | ✅ Up | 128m | — | internal only |
| `alertmanager` | ✅ healthy | 256m | — | internal only |
| `netdata` | ✅ healthy | 768m | Authelia | `netdata.vps1.ocoron.com` |
| `gatus` | ✅ Up | 256m | open (read-only) | `status.vps1.ocoron.com` |
| `backrest` | ✅ Up | 512m | Authelia | `backup.vps1.ocoron.com` |

### Fabrik Services (11 containers)
| Container | Status | Limit | Auth | URL |
|---|---|---|---|---|
| `fabrik-proxy` | ✅ healthy | 512m | X-Internal-Token | `proxy.vps1.ocoron.com` |
| `fabrik-captcha` | ✅ healthy | 512m | X-Internal-Token | `captcha.vps1.ocoron.com` |
| `fabrik-image-broker` | ✅ healthy | 512m | X-Internal-Token | `images.vps1.ocoron.com` |
| `fabrik-translator` | ✅ healthy | 512m | X-Internal-Token | `translator.vps1.ocoron.com` |
| `fabrik-emailgateway` | ✅ healthy | 512m | X-Internal-Token | `emailgateway.vps1.ocoron.com` |
| `fabrik-file-api` | ✅ Up | 1g | Bearer (Supabase JWT) | `files-api.vps1.ocoron.com` |
| `fabrik-file-worker` | ✅ Up | 1g | — | internal only |
| `fabrik-site-provisioner` | ✅ healthy | 512m | IP allowlist | `provision.vps1.ocoron.com` |
| `fabrik-n8n` | ✅ healthy | 2g | Authelia | `auto.vps1.ocoron.com` |
| `fabrik-glitchtip-web` | ✅ Up | 512m | Authelia | `errors.vps1.ocoron.com` |
| `fabrik-glitchtip-worker` | ✅ Up | 512m | — | internal only |

### Other Services (5 containers)
| Container | Status | Limit | URL |
|---|---|---|---|
| `meilisearch` | ✅ healthy | 512m | `search.vps1.ocoron.com` |
| `browserless` | ✅ Up | 2g | `browser.vps1.ocoron.com` |
| `apprise` | ✅ healthy | 512m | `notify.vps1.ocoron.com` (Authelia) |
| `pdf-service` | ✅ healthy | 512m | `pdf.vps1.ocoron.com` |
| `n8n` (standalone) | ✅ healthy | 2g | `auto.vps1.ocoron.com` |

### WordPress Stack — ocoron.com (5 containers)
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
| `gzip@docker` | compress | Available globally — wire per-router as needed |
| `redirect-to-https@docker` | redirectscheme | All HTTP → HTTPS |
| `site-provisioner-ipallowlist@docker` | ipallowlist | site-provisioner only |
| `ocoron-com-rate-limit@docker` | ratelimit | WordPress protection |
| `ocoron-com-block-xmlrpc@docker` | replacepathregex | WordPress xmlrpc block |
| `ocoron-com-www-redirect@docker` | redirectregex | www → non-www |
<!-- /AUTO -->

---

## Resource Limits

<!-- AUTO:limits_summary -->
### Fabrik Applications (Coolify API — persistent through redeploys)
| Service | Memory | CPU |
|---|---|---|
| fabrik-proxy | 512m | 0.5 |
| fabrik-captcha | 512m | 0.5 |
| fabrik-image-broker | 512m | 0.5 |
| fabrik-emailgateway | 512m | 0.5 |
| fabrik-translator | 512m | 0.5 |
| fabrik-file-api | 1g | 1.0 |
| fabrik-file-worker | 1g | 1.0 |
| fabrik-site-provisioner | 512m | 0.5 |
| browserless | 2g | 1.0 |

### Infra Services (`docker update` — reapply after VPS reboot)
| Service | Memory | Notes |
|---|---|---|
| postgres-main | 2g | Shared DB |
| n8n | 2g | Automation |
| netdata | 768m | High RSS service |
| authelia | 512m | |
| backrest | 512m | |
| grafana | 512m | |
| loki | 512m | |
| redis-main | 512m | |
| prometheus | 1g | Scrapes 40 containers |
| apprise | 512m | High RSS — was OOM-prone at 256m |
| cadvisor | 512m | Was OOM-prone at 256m |
| alertmanager | 256m | |
| gatus | 256m | |
| node-exporter | 128m | |
| promtail | 128m | |
| traefik | 256m | |
| ocoron-com-db-1 | 1g | WordPress MariaDB |
| ocoron-com-wordpress-1 | 512m | |
| ocoron-com-nginx-1 | 256m | |
| ocoron-com-redis-1 | 256m | |

⚠️ **After any VPS reboot:** `ssh vps "bash /opt/fabrik/scripts/vps_apply_limits.sh"`
<!-- /AUTO -->

---

## Authelia Access Control (8 rules)

| Domain | Policy | Notes |
|---|---|---|
| `ocoron.com`, `www.ocoron.com` | bypass | WordPress — public |
| `wp-test.vps1.ocoron.com`, `status.vps1.ocoron.com` | bypass | Public read-only |
| `*.vps1.ocoron.com` | bypass | `/health`, `/healthz`, `/metrics`, `/api/health` paths only |
| `pdf`, `browser`, `search`, `images`, `captcha`, `proxy`, `translator`, `files-api`, `emailgateway`, `dns`, `errors` `.vps1.ocoron.com` | bypass | API services — auth handled at app layer (X-Internal-Token) |
| `coolify.vps1.ocoron.com`, `monitor.vps1.ocoron.com` | bypass | `/api/` paths only (machine access) |
| `*.vps1.ocoron.com` | two_factor | All other subdomains require TOTP 2FA |

**Critical:** Authelia does NOT support SIGHUP hot-reload. After editing `configuration.yml`, always use:
```bash
ssh vps "sudo docker restart authelia-hks48k8sg8o4co4co08co00o"
```

---

## M2M Authentication (Option A — implemented 2026-05-07)

All Fabrik API services use canonical M2M auth:
- **Header:** `X-Internal-Token`
- **Env var:** `SERVICE_INTERNAL_SECRET_KEY` (one shared secret, all services)
- **Module:** `internal_auth.py` in each service's `app/` or `src/` dir
- **Validation:** `hmac.compare_digest` (Python) / `timingSafeEqual` (Node.js) — constant-time

| Service | Auth method | Notes |
|---|---|---|
| captcha, image-broker, translator, proxy | `X-Internal-Token` → `require_internal_token` | Python FastAPI, `from app.internal_auth import` |
| emailgateway | `X-Internal-Token` (priority) + legacy `Authorization: Bearer` | Node.js Fastify |
| file-api | `Authorization: Bearer <supabase-jwt>` | User auth, not M2M — leave unchanged |
| site-provisioner | Traefik IP allowlist only | No app-level auth needed |

`internal_auth.py` placed in **35 projects** under `/opt` (deployed + not-yet-deployed FastAPI services).

---

## Known Issues

| # | Issue | Status |
|---|---|---|
| 1 | cadvisor logs `unknown container` for its own cgroup scope | **Fixed** — cadvisor restarted with `--docker_only=true --disable_metrics=...` flags 2026-05-07 |
| 2 | Swap usage ~85% (1.7GB/2GB) | Monitor; caused by memory pressure from 40 containers |
| 3 | Wildcard SSL via Cloudflare DNS challenge | TODO — currently per-service HTTP challenge |
| 4 | Gzip middleware not wired to routers | `gzip@docker` registered; wire per-service in Coolify UI |

---

## Maintenance Procedures

```bash
# After VPS reboot — restore infra memory limits
ssh vps "bash /opt/fabrik/scripts/vps_apply_limits.sh"

# Full health + residue audit
cd /opt/fabrik && python3 scripts/vps_sync.py --verify

# Update VPS docs from live state (runs automatically after deploy)
cd /opt/fabrik && python3 scripts/update_vps_docs.py

# Check all container statuses
ssh vps "sudo docker ps --format '{{.Names}}\t{{.Status}}' | sort"

# Check memory pressure
ssh vps "sudo docker stats --no-stream --format '{{.Name}}\t{{.MemUsage}}\t{{.MemPerc}}' | sort -t$'\t' -k3 -rn | head -10"

# Weekly disk cleanup
ssh vps "sudo docker image prune -f && sudo docker builder prune -f"

# Redeploy a service (must git push first)
cd /opt/<service> && git push && cd /opt/fabrik && fabrik redeploy fabrik-<name>

# Restart Authelia after config edit (never use SIGHUP — it exits)
ssh vps "sudo docker restart authelia-hks48k8sg8o4co4co08co00o"
```
