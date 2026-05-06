# VPS Complete Service Inventory

**Date:** 2026-05-07 (updated 21:00 UTC+3)
**Method:** SSH docker ps + Coolify API + live verification
**Total Containers:** 40 running
**VPS:** vps1.ocoron.com (172.93.160.197) — Ubuntu 24.04, 6 vCores, 11GB RAM, 108GB disk

---

## How to re-verify this document

```bash
# Container inventory
ssh vps "sudo docker ps --format '{{.Names}}\t{{.Status}}\t{{.Ports}}' | sort"

# Firewall rules
ssh vps "sudo ufw status"

# Traefik routers + middlewares
ssh vps "sudo docker exec traefik wget -qO- http://localhost:8080/api/http/routers | python3 -m json.tool"
ssh vps "sudo docker exec traefik wget -qO- http://localhost:8080/api/http/middlewares | python3 -m json.tool"

# Resource limits
ssh vps "sudo docker inspect \$(sudo docker ps -q) --format '{{.Name}} Memory={{.HostConfig.Memory}} CPU={{.HostConfig.NanoCPUs}}'"

# Disk usage
ssh vps "sudo docker system df && df -h /"

# Fabrik audit
cd /opt/fabrik && python3 scripts/vps_sync.py --verify
```

---

## Network Topology

| Network | Subnet | Purpose |
|---|---|---|
| `coolify` | 10.0.1.0/24 | All Coolify-managed containers |
| `bridge` | 172.17.0.0/16 | Docker default (unused by services) |
| Host | 172.93.160.197 | Public IP — Traefik only on 80/443 |

All inter-service communication uses Docker network DNS (`service-name:port`). No containers expose ports directly to host except Traefik (80/443), Coolify Realtime (6001/6002), and OpenVPN (1194).

---

## Traefik Configuration

**Version:** v3.6  
**Config:** `/data/coolify/proxy/` (mounted into container as `/traefik`)  
**Dynamic config dir:** `/data/coolify/proxy/dynamic/` (hot-reload, file watching enabled)  
**SSL:** Let's Encrypt via HTTP challenge (`letsencrypt` certresolver) — `acme.json` at `/data/coolify/proxy/acme.json`

### Entrypoints
| Entrypoint | Port | Notes |
|---|---|---|
| `http` | :80 | HTTP→HTTPS redirect |
| `https` | :443 | TLS, HTTP/2, max 250 concurrent streams |

### Middlewares (active)
| Name | Type | Notes |
|---|---|---|
| `authelia-forward@docker` | forwardauth | → `http://authelia:9091/api/authz/forward-auth` |
| `gzip@docker` | compress | Global gzip; wire per-router as needed |
| `redirect-to-https@docker` | redirectscheme | HTTP → HTTPS |
| `site-provisioner-ipallowlist@docker` | ipallowlist | VPS + internal ranges only |
| `ocoron-com-rate-limit@docker` | ratelimit | WordPress protection |
| `ocoron-com-block-xmlrpc@docker` | replacepathregex | WordPress xmlrpc block |

---

## Firewall (UFW)

| Rule | Port | Action | Reason |
|---|---|---|---|
| SSH | 22/tcp | ALLOW | Admin access |
| HTTP | 80/tcp | ALLOW | Traefik (→ HTTPS) |
| HTTPS | 443/tcp | ALLOW | Traefik + OpenVPN |
| OpenVPN | 1194/tcp | ALLOW | VPN server |
| Soketi | 6001-6002/tcp | ALLOW | Coolify Realtime WebSocket |
| Coolify raw | 8000/tcp | **DENY** | Use `coolify.vps1.ocoron.com` |

iptables `DOCKER-USER` chain: static rules blocking raw host port access from internet; Traefik is the only entry point for Docker services.

---

## Complete Container Inventory

### 1. Coolify Platform

| Container | Image | Ports | CPU Limit | Mem Limit |
|---|---|---|---|---|
| `coolify` | `ghcr.io/coollabsio/coolify` | 8000→8080 (UFW DENY) | — | — |
| `coolify-proxy` | `traefik:v3.6` | 80, 443, 127.0.0.1:8080 | — | — |
| `coolify-realtime` | `ghcr.io/coollabsio/coolify-realtime:1.0.13` | 0.0.0.0:6001-6002 | — | — |
| `coolify-db` | `postgres` | internal | — | — |
| `coolify-redis` | `redis` | internal | — | — |
| `coolify-sentinel` | `redis` | internal | — | — |

### 2. Security & Auth

| Container | Image | URL | Middleware | Limits |
|---|---|---|---|---|
| `authelia` | `authelia/authelia` | `auth.vps1.ocoron.com` | self | — |

### 3. Observability Stack

| Container | URL | Traefik route | Middleware | Limits |
|---|---|---|---|---|
| `grafana` | `monitor.vps1.ocoron.com` | ✅ | Authelia | — |
| `prometheus` | internal | ✅ internal | — | — |
| `loki` | internal | ✅ internal | — | — |
| `promtail` | internal | — | — | — |
| `cadvisor` | internal | — | — | — |
| `node-exporter` | internal | — | — | — |
| `alertmanager` | internal | — | — | — |
| `netdata` | `netdata.vps1.ocoron.com` | ✅ | Authelia | — |
| `gatus` | `status.vps1.ocoron.com` | ✅ | none (read-only) | — |

### 4. Data Services

| Container | Internal address | Type | Notes |
|---|---|---|---|
| `postgres-main` | `postgres-main:5432` | PostgreSQL | Shared app DB; hosts `proxy_management`, others |
| `redis-main` | `redis-main:6379` | Redis | Shared app cache |
| `meilisearch` | `search.vps1.ocoron.com` | MeiliSearch | Full-text search |

### 5. Fabrik Application Services

| Container | URL | Auth | CPU | Mem | Notes |
|---|---|---|---|---|---|
| `fabrik-proxy` | `proxy.vps1.ocoron.com` | X-API-Key | 0.5 | 512m | Webshare proxy manager; DB: `proxy_management` |
| `fabrik-captcha` | `captcha.vps1.ocoron.com` | X-API-Key | 0.5 | 512m | AntiCaptcha solver |
| `fabrik-image-broker` | `images.vps1.ocoron.com` | X-API-Key | 0.5 | 512m | Pexels/Pixabay broker |
| `fabrik-translator` | `translator.vps1.ocoron.com` | X-API-Key | 0.5 | 512m | ⚠️ Restarting — investigate |
| `fabrik-emailgateway` | `emailgateway.vps1.ocoron.com` | app-layer | 0.5 | 512m | Fastify email service |
| `fabrik-file-api` | `files-api.vps1.ocoron.com` | Bearer (Supabase) | 1.0 | 1g | Node.js file upload/download |
| `fabrik-file-worker` | internal | — | 1.0 | 1g | Background file processing |
| `fabrik-site-provisioner` | `provision.vps1.ocoron.com` | IP allowlist | 0.5 | 512m | DNS/domain provisioning |
| `fabrik-n8n` | `auto.vps1.ocoron.com` | Authelia | — | — | n8n automation |
| `fabrik-glitchtip-web` | `errors.vps1.ocoron.com` | Authelia | — | — | Error tracking (Sentry-compatible) |
| `fabrik-glitchtip-worker` | internal | — | — | — | GlitchTip background worker |

### 6. Other Services

| Container | URL | Auth | Notes |
|---|---|---|---|
| `browserless` | `browser.vps1.ocoron.com` | — | Headless Chrome; 2GB/1CPU |
| `apprise` | `notify.vps1.ocoron.com` | Authelia | Multi-channel notification hub |
| `pdf-service` | `pdf.vps1.ocoron.com` | — | PDF generation |
| `backrest` | `backup.vps1.ocoron.com` | Authelia | Backblaze B2 backup via Restic |

### 7. Infrastructure Automation

| Container | URL | Notes |
|---|---|---|
| `promtail` | internal | Ships container logs → Loki |

### 8. WordPress Stack (ocoron.com)

| Container | Notes |
|---|---|
| `ocoron-com-nginx-1` | Nginx frontend, port 80 behind Traefik |
| `ocoron-com-wordpress-1` | PHP-FPM 9000 |
| `ocoron-com-db-1` | MariaDB 3306 |
| `ocoron-com-redis-1` | Redis object cache |
| `ocoron-com-backup-1` | Backup cron |

---

## Security Posture Summary (2026-05-07)

| Layer | Status | Detail |
|---|---|---|
| **SSH** | ✅ | Ed25519 key only; root disabled |
| **UFW** | ✅ | Minimal rules; port 8000 DENY |
| **Traefik** | ✅ | Dashboard localhost-only; no raw ports |
| **Authelia** | ✅ | Forward-auth on all admin dashboards |
| **API services** | ✅ | proxy/captcha/image-broker/translator: X-API-Key |
| **File API** | ✅ | Supabase Bearer auth |
| **Site-provisioner** | ✅ | Traefik IP allowlist |
| **Resource limits** | ✅ complete | All 40 containers limited. Fabrik apps: Coolify API. Infra: `docker update` via `scripts/vps_apply_limits.sh` |
| **Wildcard SSL** | ⚠️ | Per-service HTTP challenge; TODO: Cloudflare DNS challenge |
| **Gzip compression** | ✅ | `gzip@docker` middleware registered; wire per-router as needed |
| **Docker images** | ✅ | Pruned 2026-05-06; build cache cleared |
| **.dockerignore** | ✅ | Added to all 21 projects missing it |
| **Coolify CVEs** | ✅ | Running v4.0.0-beta.459 (CVEs fixed in beta.451+) |

---

## Resource Limits Reference

**Two mechanisms apply — do not confuse them:**

| Type | Mechanism | Persists through | Managed by |
|---|---|---|---|
| Fabrik applications | `limits_memory`/`limits_cpus` via Coolify API | Redeploys ✅ | `fabrik apply` / `update_application()` |
| Infra services (stacks) | `docker update` | Container restarts ✅, VPS reboot ❌ | `scripts/vps_apply_limits.sh` |

**After VPS reboot:**
```bash
ssh vps "bash /opt/fabrik/scripts/vps_apply_limits.sh"
```

**Why Coolify API fails for services:** Coolify v4 service stacks are multi-container templates — the API rejects `limits_memory` with 422 because it cannot determine which sub-container to target. `docker update` bypasses this cleanly.

---

## Pending Actions

| # | Action | Where | Priority |
|---|---|---|---|
| 1 | Migrate SSL to Cloudflare DNS challenge (wildcard) | Coolify → Proxy → Add resolver | Low |
| 2 | Wire `gzip@docker` middleware to high-traffic routers | Coolify → each app → Traefik config | Low |

**Completed 2026-05-07:**
- ✅ Resource limits set on all 40 containers (Coolify API for apps, `docker update` for infra)
- ✅ translator crash loop fixed (DATABASE_URL localhost→postgres-main)
