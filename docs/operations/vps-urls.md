# VPS1 Service URLs

<!-- AUTO-UPDATE: Run `python3 scripts/snapshot_vps_state.py` to refresh -->

**Last Updated:** 2026-05-07
**VPS:** vps1.ocoron.com (172.93.160.197) — Los Angeles, CA

All services use HTTPS via Traefik (Coolify-managed). HTTP redirects to HTTPS automatically.

---

## Public Services (Authelia SSO required)

| URL | Service | Notes |
|---|---|---|
| `https://coolify.vps1.ocoron.com` | Coolify dashboard | Infra management |
| `https://monitor.vps1.ocoron.com` | Grafana | Metrics & dashboards |
| `https://netdata.vps1.ocoron.com` | Netdata | Real-time system metrics |
| `https://errors.vps1.ocoron.com` | GlitchTip | Error tracking |
| `https://auto.vps1.ocoron.com` | n8n | Workflow automation |
| `https://backup.vps1.ocoron.com` | Backrest | Backup management UI |
| `https://notify.vps1.ocoron.com` | Apprise | Notification hub |
| `https://auth.vps1.ocoron.com` | Authelia | SSO/2FA portal |

## Public Services (Open)

| URL | Service | Notes |
|---|---|---|
| `https://status.vps1.ocoron.com` | Gatus | Service health dashboard — read-only |
| `https://www.ocoron.com` | WordPress | Ocoron corporate site |

## API Services (X-API-Key header required)

| URL | Service | Key Location |
|---|---|---|
| `https://proxy.vps1.ocoron.com` | Proxy Manager | `/opt/proxy/.env` → `PROXY_API_KEY` |
| `https://captcha.vps1.ocoron.com` | Captcha Solver | `/opt/captcha/.env` → `SERVICE_API_KEY` |
| `https://images.vps1.ocoron.com` | Image Broker | `/opt/image-broker/.env` → `SERVICE_API_KEY` |
| `https://translator.vps1.ocoron.com` | Translator | `/opt/translator/.env` → `SERVICE_API_KEY` |

## API Services (Other Auth)

| URL | Service | Auth Method |
|---|---|---|
| `https://files-api.vps1.ocoron.com` | File API | Bearer token (Supabase JWT) |
| `https://emailgateway.vps1.ocoron.com` | Email Gateway | App-layer auth middleware |
| `https://search.vps1.ocoron.com` | MeiliSearch | Master key (internal use) |

## IP-Allowlisted (VPS + internal Docker networks only)

| URL | Service | Allowed IPs |
|---|---|---|
| `https://provision.vps1.ocoron.com` | Site Provisioner | `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`, `172.93.160.197/32`, `31.206.44.18/32` |

## Internal Only (no public route)

| Service | Internal address | Purpose |
|---|---|---|
| PostgreSQL (main) | `postgres-main:5432` | Shared app database |
| Redis (main) | `redis-main:6379` | Shared cache |
| Prometheus | `prometheus:9090` | Metrics scraping |
| Loki | `loki:3100` | Log aggregation |
| cAdvisor | `cadvisor:8080` | Container metrics |
| Traefik dashboard | `127.0.0.1:8080` | SSH tunnel only |

---

## DNS Records (Cloudflare — all A records → 172.93.160.197)

`auth`, `auto`, `backup`, `browser`, `captcha`, `coolify`, `dns`, `emailgateway`, `errors`, `files-api`, `images`, `monitor`, `netdata`, `notify`, `pdf`, `provision`, `proxy`, `search`, `status`, `translator` — all under `vps1.ocoron.com`

Plus: `www.ocoron.com`, `ocoron.com`

---

## Port Reference

| Port | Binding | Purpose |
|---|---|---|
| 80 | `0.0.0.0:80` | HTTP (Traefik — redirects to HTTPS) |
| 443 | `0.0.0.0:443` | HTTPS (Traefik) + OpenVPN |
| 1194 | `0.0.0.0:1194` | OpenVPN TCP |
| 6001-6002 | `0.0.0.0:6001-6002` | Coolify Realtime (Soketi WebSocket) |
| 8000 | **UFW DENY** | Coolify raw — blocked, use domain |
| 8080 | `127.0.0.1:8080` | Traefik dashboard (localhost only) |
