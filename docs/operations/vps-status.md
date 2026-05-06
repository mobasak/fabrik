# VPS Status

**Last Updated:** 2026-05-07 UTC+3
**Host:** vps1.ocoron.com (172.93.160.197)
**Location:** Los Angeles, CA, USA (Psychz Networks AS32421)
**SSH:** `ssh vps` (ozgur user, key-only Ed25519 auth)
**Uptime:** 48 days

---

## System Overview

| Component | Value |
|---|---|
| **OS** | Ubuntu 24.04 LTS |
| **CPU** | 6 vCores |
| **Memory** | 11GB total, ~4.5GB available, 2GB swap (1.7GB used) |
| **Disk** | 108GB total, 38GB used, 70GB free (35%) |
| **Docker Images** | 14.2GB (all active — no reclaimable after 2026-05-06 prune) |
| **Docker Volumes** | 3.6GB |
| **Build Cache** | 0B (cleared 2026-05-06) |
| **Load Average** | 1.89 / 2.96 / 3.36 (5m/10m/15m) |

### Storage Notes
- No local backup retention — all backups go to Backblaze B2 via Backrest
- Monitor `/var/lib/docker` growth; run `docker image prune -af` monthly
- PostgreSQL data at `/data/coolify/databases/`
- Alert threshold: 70% disk usage

---

## Security Status

| Component | Status | Notes |
|---|---|---|
| **SSH** | ✅ | Root disabled, password auth disabled, Ed25519 key only |
| **UFW** | ✅ | Active — see Firewall section below |
| **Port 8000 (Coolify raw)** | ✅ BLOCKED | DENY rule added 2026-05-06; use `coolify.vps1.ocoron.com` |
| **Traefik dashboard** | ✅ | Bound to `127.0.0.1:8080` only |
| **Coolify UI** | ✅ | Behind Traefik + Authelia on `coolify.vps1.ocoron.com` |
| **OpenVPN** | ✅ | Port 1194/tcp, kernel service |
| **Authelia SSO** | ✅ | Forward-auth on all admin dashboards |
| **Service API keys** | ✅ | proxy, captcha, image-broker, translator all require `X-API-Key` |
| **Site-provisioner** | ✅ | IP allowlist middleware (VPS IP + internal Docker ranges only) |

### Firewall (UFW) — current rules

| Port | Action | Protocol | Purpose |
|---|---|---|---|
| 22/tcp | ALLOW | TCP | SSH |
| 80/tcp | ALLOW | TCP | HTTP → redirects to HTTPS via Traefik |
| 443/tcp | ALLOW | TCP | HTTPS + OpenVPN |
| 1194/tcp | ALLOW | TCP | OpenVPN (redundant with 443, kept for compatibility) |
| 6001/tcp | ALLOW | TCP | Coolify Realtime (Soketi WebSocket — Coolify UI log streaming) |
| 6002/tcp | ALLOW | TCP | Coolify Realtime (Soketi WebSocket) |
| 8000/tcp | **DENY** | TCP | Coolify raw dashboard — blocked, use HTTPS domain instead |

---

## Container Status (40 running — 2026-05-07)

### Coolify Platform (5 containers)

| Container | Status | Notes |
|---|---|---|
| `coolify` | ✅ Up 2 weeks | Dashboard via `coolify.vps1.ocoron.com` (Authelia-gated) |
| `coolify-proxy` | ✅ Up 2 weeks | Traefik v3.6 reverse proxy |
| `coolify-realtime` | ✅ Up 2 weeks | Soketi WebSocket (Coolify UI live logs) |
| `coolify-db` | ✅ Up 2 weeks | Coolify internal PostgreSQL |
| `coolify-redis` | ✅ Up 2 weeks | Coolify internal Redis |
| `coolify-sentinel` | ✅ Up | Redis sentinel |

### Infrastructure Services (14 containers)

| Container | Status | URL | Auth |
|---|---|---|---|
| `authelia` | ✅ healthy | `auth.vps1.ocoron.com` | SSO/2FA gate |
| `traefik` | ✅ Up 2 weeks | `127.0.0.1:8080` (local only) | — |
| `postgres-main` | ✅ healthy | internal only | app credentials |
| `redis-main` | ✅ healthy | internal only | — |
| `gatus` | ✅ Up | `status.vps1.ocoron.com` | open (read-only) |
| `grafana` | ✅ healthy | `monitor.vps1.ocoron.com` | Authelia |
| `prometheus` | ✅ healthy | internal only | — |
| `loki` | ✅ healthy | internal only | — |
| `promtail` | ✅ Up | internal only | — |
| `cadvisor` | ✅ healthy | internal only | — |
| `node-exporter` | ✅ Up | internal only | — |
| `alertmanager` | ✅ healthy | internal only | — |
| `netdata` | ✅ healthy | `netdata.vps1.ocoron.com` | Authelia |
| `backrest` | ✅ Up | `backup.vps1.ocoron.com` | Authelia |

### Fabrik Application Services (11 containers)

| Container | Status | URL | Auth |
|---|---|---|---|
| `fabrik-proxy` | ✅ healthy | `proxy.vps1.ocoron.com` | X-API-Key |
| `fabrik-captcha` | ✅ healthy | `captcha.vps1.ocoron.com` | X-API-Key |
| `fabrik-image-broker` | ✅ healthy | `images.vps1.ocoron.com` | X-API-Key |
| `fabrik-translator` | ⚠️ Restarting | `translator.vps1.ocoron.com` | X-API-Key |
| `fabrik-emailgateway` | ✅ Up | `emailgateway.vps1.ocoron.com` | app-layer auth |
| `fabrik-file-api` | ✅ Up | `files-api.vps1.ocoron.com` | Bearer (Supabase) |
| `fabrik-file-worker` | ✅ Up | internal only | — |
| `fabrik-site-provisioner` | ✅ healthy | `provision.vps1.ocoron.com` | IP allowlist |
| `fabrik-n8n` | ✅ healthy | `auto.vps1.ocoron.com` | Authelia |
| `fabrik-glitchtip-web` | ✅ Up | `errors.vps1.ocoron.com` | Authelia |
| `fabrik-glitchtip-worker` | ✅ Up | internal only | — |

### Other Services (4 containers)

| Container | Status | URL | Notes |
|---|---|---|---|
| `meilisearch` | ✅ healthy | `search.vps1.ocoron.com` | Coolify-managed |
| `browserless` | ✅ Up | `browser.vps1.ocoron.com` | 2GB/1CPU limit |
| `apprise` | ✅ healthy | `notify.vps1.ocoron.com` | Authelia; notification hub |
| `pdf-service` | ✅ healthy | `pdf.vps1.ocoron.com` | — |

### WordPress Stack (ocoron.com) — 4 containers

| Container | Status | Notes |
|---|---|---|
| `ocoron-com-nginx-1` | ✅ Up | Nginx frontend |
| `ocoron-com-wordpress-1` | ✅ Up | WordPress PHP-FPM |
| `ocoron-com-db-1` | ✅ healthy | MariaDB |
| `ocoron-com-redis-1` | ✅ healthy | Redis cache |
| `ocoron-com-backup-1` | ✅ Up | Backup cron |

---

## Known Issues (2026-05-07)

| # | Service | Issue | Action |
|---|---|---|---|
| 1 | `fabrik-translator` | Restarting (exit code 3) | Investigate logs — `docker logs translator-*` |
| 2 | Swap | 1.7GB / 2GB used | Memory pressure; monitor closely |
| 3 | Resource limits | Infra services (cadvisor, alertmanager, etc.) have no limits | Set manually via Coolify dashboard |
| 4 | Wildcard SSL | Per-service Let's Encrypt HTTP challenge | Migrate to Cloudflare DNS challenge in Coolify for wildcard |

---

## Traefik Middleware Registry

| Middleware | Type | Used by |
|---|---|---|
| `authelia-forward@docker` | forwardauth | All admin dashboards |
| `gzip@docker` | compress | Available globally (added 2026-05-06) — wire per-service |
| `site-provisioner-ipallowlist@docker` | ipallowlist | site-provisioner only |
| `redirect-to-https@docker` | redirectscheme | All HTTP → HTTPS |
| `ocoron-com-rate-limit@docker` | ratelimit | ocoron.com WordPress |
| `ocoron-com-block-xmlrpc@docker` | replacepathregex | ocoron.com WordPress |

---

## Resource Limits (Fabrik apps — set 2026-05-06)

| Service | Memory | CPU |
|---|---|---|
| fabrik-proxy | 512m | 0.5 |
| fabrik-captcha | 512m | 0.5 |
| fabrik-image-broker | 512m | 0.5 |
| fabrik-emailgateway | 512m | 0.5 |
| fabrik-file-api | 1g | 1.0 |
| fabrik-file-worker | 1g | 1.0 |
| fabrik-translator | 512m | 0.5 |
| browserless | 2g | 1.0 |
| fabrik-n8n | 2g | 2.0 (pending) |
| Infra services | ⚠️ none | Set via Coolify dashboard |

---

## Maintenance Procedures

```bash
# Weekly cleanup (cron or manual)
ssh vps "sudo docker image prune -f && sudo docker builder prune -f"

# Check all service health
cd /opt/fabrik && python3 scripts/vps_sync.py --verify

# Full status
ssh vps "sudo docker ps --format '{{.Names}}\t{{.Status}}' | sort"

# Restart a specific service
cd /opt/fabrik && fabrik redeploy <service-name>

# Check translator crash
ssh vps "sudo docker logs \$(sudo docker ps -a --filter name=translator --format '{{.Names}}' | head -1) --tail 50"
```
