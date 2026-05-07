# VPS1 Service URLs

**Last Updated:** 2026-05-07 12:00 UTC+3
**VPS:** vps1.ocoron.com (172.93.160.197) — Los Angeles, CA
**Access pattern:** All services via HTTPS through Traefik. HTTP always redirects to HTTPS.

---

<!-- AUTO:coolify_apps -->
## Admin Dashboards (Authelia SSO + TOTP required)

| URL | Service | Notes |
|---|---|---|
| `https://coolify.vps1.ocoron.com` | Coolify | Infrastructure management |
| `https://monitor.vps1.ocoron.com` | Grafana | Metrics & dashboards |
| `https://netdata.vps1.ocoron.com` | Netdata | Real-time system metrics |
| `https://errors.vps1.ocoron.com` | GlitchTip | Error tracking (Sentry-compatible) |
| `https://auto.vps1.ocoron.com` | n8n | Workflow automation |
| `https://backup.vps1.ocoron.com` | Backrest | Backblaze B2 backup UI |
| `https://notify.vps1.ocoron.com` | Apprise | Multi-channel notification hub |
| `https://auth.vps1.ocoron.com` | Authelia | SSO/2FA portal |

## Public Services (No Auth)

| URL | Service | Notes |
|---|---|---|
| `https://status.vps1.ocoron.com` | Gatus | Service health — read-only |
| `https://www.ocoron.com` | WordPress | Ocoron corporate site |
| `https://ocoron.com` | WordPress | Redirects to www |

## API Services (X-Internal-Token required)

| URL | Service | Header | Env var location |
|---|---|---|---|
| `https://proxy.vps1.ocoron.com` | Proxy Manager | `X-Internal-Token` | `SERVICE_INTERNAL_SECRET_KEY` in `/opt/fabrik/.env` |
| `https://captcha.vps1.ocoron.com` | Captcha Solver | `X-Internal-Token` | same shared key |
| `https://images.vps1.ocoron.com` | Image Broker | `X-Internal-Token` | same shared key |
| `https://translator.vps1.ocoron.com` | Translator | `X-Internal-Token` | same shared key |
| `https://emailgateway.vps1.ocoron.com` | Email Gateway | `X-Internal-Token` (or legacy Bearer) | same shared key |

## API Services (Other Auth)

| URL | Service | Auth |
|---|---|---|
| `https://files-api.vps1.ocoron.com` | File API | `Authorization: Bearer <supabase-jwt>` |
| `https://search.vps1.ocoron.com` | MeiliSearch | Master key (internal use) |

## IP-Allowlisted Services

| URL | Service | Allowed from |
|---|---|---|
| `https://provision.vps1.ocoron.com` | Site Provisioner | `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`, `172.93.160.197/32`, `31.206.44.18/32` |

## Internal-Only Services (No Public Route)

| Service | Internal address | Purpose |
|---|---|---|
| PostgreSQL (main) | `postgres-main:5432` | Shared app DB — databases: `proxy_management`, `translator_service`, etc. |
| Redis (main) | `redis-main:6379` | Shared cache; Authelia sessions on DB index 3 |
| Prometheus | `prometheus:9090` | Metrics scraping |
| Loki | `loki:3100` | Log aggregation |
| cAdvisor | `cadvisor:8080` | Container metrics |
| Traefik dashboard | `127.0.0.1:8080` | SSH tunnel only: `ssh vps -L 8080:localhost:8080` |
<!-- /AUTO -->

---

## DNS Records (Cloudflare — all A → 172.93.160.197)

All `*.vps1.ocoron.com` subdomains proxied through Cloudflare.
Active records: `auth`, `auto`, `backup`, `browser`, `captcha`, `coolify`, `emailgateway`, `errors`, `files-api`, `images`, `monitor`, `netdata`, `notify`, `pdf`, `provision`, `proxy`, `search`, `status`, `translator`

Plus: `ocoron.com`, `www.ocoron.com`

---

## Port Reference

| Port | Binding | Status | Purpose |
|---|---|---|---|
| 22/tcp | `0.0.0.0:22` | ✅ ALLOW | SSH |
| 80/tcp | `0.0.0.0:80` | ✅ ALLOW | HTTP → Traefik → HTTPS redirect |
| 443/tcp | `0.0.0.0:443` | ✅ ALLOW | HTTPS + OpenVPN |
| 1194/tcp | `0.0.0.0:1194` | ✅ ALLOW | OpenVPN (kernel service) |
| 6001-6002/tcp | `0.0.0.0:6001-6002` | ✅ ALLOW | Coolify Realtime (Soketi — Coolify UI live logs) |
| 8000/tcp | `0.0.0.0:8000` | ❌ DENY | Coolify raw port — blocked by UFW; use domain |
| 8080/tcp | `127.0.0.1:8080` | localhost only | Traefik API dashboard |

---

## Connection Strings (Docker network)

All inter-service connections use Docker network DNS names — **never `localhost`**:

```bash
# Database
DATABASE_URL=postgresql+asyncpg://postgres:<pass>@postgres-main:5432/<dbname>
DB_HOST=postgres-main
DB_PORT=5432

# Cache / Authelia sessions
REDIS_URL=redis://redis-main:6379
# Authelia uses: redis-main:6379 DB index 3

# Prometheus scrape targets (internal)
cadvisor:8080
prometheus:9090
loki:3100
```

---

## Maintenance Commands

```bash
# After VPS reboot — reapply infra memory limits (docker update resets on reboot)
ssh vps "bash /opt/fabrik/scripts/vps_apply_limits.sh"

# Full health + residue audit (checks limits drift, stale Authelia rules, etc.)
cd /opt/fabrik && python3 scripts/vps_sync.py --verify

# Update VPS docs manually (also runs automatically post-deploy)
cd /opt/fabrik && python3 scripts/update_vps_docs.py

# Deploy a new service
cd /opt/fabrik && fabrik apply specs/services/<name>.yaml

# Redeploy existing service (MUST git commit + push first — Coolify pulls from GitHub)
cd /opt/<service> && git add -A && git commit -m "..." && git push
cd /opt/fabrik && fabrik redeploy fabrik-<name>

# Weekly disk cleanup
ssh vps "sudo docker image prune -f && sudo docker builder prune -f"

# Restart Authelia after config edit (NEVER use SIGHUP — Authelia exits on SIGHUP)
ssh vps "sudo docker restart authelia-hks48k8sg8o4co4co08co00o"
```
