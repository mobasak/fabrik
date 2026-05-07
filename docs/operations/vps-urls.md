# VPS1 Service URLs

**Last Updated:** 2026-05-07 13:00 UTC+3
**VPS:** vps1.ocoron.com (172.93.160.197) — Los Angeles, CA
**Pattern:** All services via HTTPS through Traefik. HTTP auto-redirects to HTTPS.

---

<!-- AUTO:coolify_apps -->
## Admin Dashboards (Authelia SSO + TOTP)

| URL | Service | Notes |
|---|---|---|
| `https://coolify.vps1.ocoron.com` | Coolify | Infrastructure management |
| `https://monitor.vps1.ocoron.com` | Grafana | Metrics + Prometheus data |
| `https://netdata.vps1.ocoron.com` | Netdata | Real-time system metrics (512MB/7d retention) |
| `https://errors.vps1.ocoron.com` | GlitchTip | Error tracking (Sentry-compatible) |
| `https://auto.vps1.ocoron.com` | n8n | Workflow automation |
| `https://backup.vps1.ocoron.com` | Backrest | Backblaze B2 backup UI |
| `https://notify.vps1.ocoron.com` | Apprise | Multi-channel notification hub |
| `https://auth.vps1.ocoron.com` | Authelia | SSO/TOTP portal |

## Public Services (No Auth)

| URL | Service | Notes |
|---|---|---|
| `https://status.vps1.ocoron.com` | Gatus | Service uptime — read-only |
| `https://www.ocoron.com` | WordPress | Ocoron corporate site |

## API Services — X-Internal-Token Required

Send header `X-Internal-Token: <SERVICE_INTERNAL_SECRET_KEY>` on every request.
Key stored in `/opt/fabrik/.env` → push to Coolify env for each service.

| URL | Service | Notes |
|---|---|---|
| `https://proxy.vps1.ocoron.com` | Proxy Manager | Webshare proxy pool; DB: `proxy_management` |
| `https://captcha.vps1.ocoron.com` | Captcha Solver | AntiCaptcha integration |
| `https://images.vps1.ocoron.com` | Image Broker | Pexels/Pixabay |
| `https://translator.vps1.ocoron.com` | Translator | DB: `translator_service` |
| `https://emailgateway.vps1.ocoron.com` | Email Gateway | Also accepts legacy `Authorization: Bearer` |

## API Services — Other Auth

| URL | Service | Auth |
|---|---|---|
| `https://files-api.vps1.ocoron.com` | File API | `Authorization: Bearer <supabase-jwt>` (user auth) |
| `https://search.vps1.ocoron.com` | MeiliSearch | Master key (internal use only) |

## IP-Allowlisted Services

| URL | Service | Allowed from |
|---|---|---|
| `https://provision.vps1.ocoron.com` | Site Provisioner | `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`, `172.93.160.197/32`, `31.206.44.18/32` |

## Internal-Only (No Public Route)

| Service | Address | Purpose |
|---|---|---|
| PostgreSQL (main) | `postgres-main:5432` | Shared app DB — `proxy_management`, `translator_service`, etc. |
| Redis (main) | `redis-main:6379` | Shared cache; Authelia sessions on DB index 3 |
| Prometheus | `prometheus:9090` | Metrics; reload via `docker compose restart` in `/opt/prometheus` |
| Loki | `loki:3100` | Log aggregation; 7-day retention |
| cAdvisor | `cadvisor:8080` | Container metrics → Prometheus |
| Alertmanager | `alertmanager:9093` | Alert routing → Telegram |
| Traefik dashboard | `127.0.0.1:8080` | SSH tunnel: `ssh vps -L 8080:localhost:8080` |
<!-- /AUTO -->

---

## DNS Records (Cloudflare — all A → 172.93.160.197)

Active subdomains under `*.vps1.ocoron.com`:
`auth`, `auto`, `backup`, `browser`, `captcha`, `coolify`, `emailgateway`, `errors`, `files-api`, `images`, `monitor`, `netdata`, `notify`, `pdf`, `provision`, `proxy`, `search`, `status`, `translator`

Plus: `ocoron.com`, `www.ocoron.com`

---

## Port Reference

| Port | Binding | Status | Purpose |
|---|---|---|---|
| 22/tcp | `0.0.0.0:22` | ✅ ALLOW | SSH |
| 80/tcp | `0.0.0.0:80` | ✅ ALLOW | HTTP → Traefik → HTTPS |
| 443/tcp | `0.0.0.0:443` | ✅ ALLOW | HTTPS + OpenVPN |
| 1194/tcp | `0.0.0.0:1194` | ✅ ALLOW | OpenVPN |
| 6001-6002/tcp | `0.0.0.0:6001-6002` | ✅ ALLOW | Coolify Realtime / Soketi |
| 8000/tcp | `0.0.0.0:8000` | ❌ DENY | Coolify raw — blocked by UFW |
| 8080/tcp | `127.0.0.1:8080` | localhost only | Traefik API dashboard |

---

## Docker Connection Strings — Always Use These

```bash
# Database — NEVER localhost inside a container
DATABASE_URL=postgresql+asyncpg://postgres:<pass>@postgres-main:5432/<dbname>
DB_HOST=postgres-main
DB_PORT=5432

# Cache + Authelia sessions
REDIS_URL=redis://redis-main:6379/0
# Authelia uses: redis-main:6379 DB index 3

# Prometheus scrape targets (internal)
# prometheus:9090 → cadvisor:8080 → node-exporter:9100 → loki:3100 → netdata:19999
```

---

## Calling Another Service (M2M Pattern)

```python
import os, httpx
headers = {"X-Internal-Token": os.environ["SERVICE_INTERNAL_SECRET_KEY"]}
resp = httpx.get("https://translator.vps1.ocoron.com/api/translate", headers=headers)
```

```javascript
const headers = { 'X-Internal-Token': process.env.SERVICE_INTERNAL_SECRET_KEY };
const resp = await fetch('https://translator.vps1.ocoron.com/api/translate', { headers });
```

---

## Maintenance Commands

```bash
# After VPS reboot — reapply infra memory limits
ssh vps "bash /opt/fabrik/scripts/vps_apply_limits.sh"

# Full health audit
cd /opt/fabrik && python3 scripts/vps_sync.py --verify

# Deploy new service
cd /opt/fabrik && fabrik apply specs/services/<name>.yaml

# Redeploy (git push FIRST — Coolify pulls from GitHub not local /opt/)
cd /opt/<service> && git add -A && git commit -m "..." && git push
cd /opt/fabrik && fabrik redeploy fabrik-<name>

# Restart Authelia after config change (NEVER SIGHUP)
ssh vps "sudo docker restart authelia-hks48k8sg8o4co4co08co00o"

# Reload Prometheus after editing /opt/monitoring/configs/prometheus/prometheus.yml
ssh vps "cd /opt/prometheus && sudo docker compose restart"

# Weekly cleanup
ssh vps "sudo docker image prune -f && sudo docker builder prune -f"
```
