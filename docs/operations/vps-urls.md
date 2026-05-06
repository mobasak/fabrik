# VPS1 Service URLs

<!-- AUTO-UPDATE: Run `python3 scripts/snapshot_vps_state.py` to refresh -->

**Last Updated:** 2026-05-03
All services deployed on VPS1 (172.93.160.197) with HTTPS via Traefik (Coolify-managed).

## DNS Records (Cloudflare)

| Subdomain | Type | IP | Service |
|-----------|------|-----|---------|
| `vps1.ocoron.com` | A | 172.93.160.197 | Base domain |
| `auth.vps1.ocoron.com` | A | 172.93.160.197 | Authelia SSO/2FA |
| `auto.vps1.ocoron.com` | A | 172.93.160.197 | n8n automation |
| `backup.vps1.ocoron.com` | A | 172.93.160.197 | Backrest backup UI |
| `browser.vps1.ocoron.com` | A | 172.93.160.197 | Browserless headless Chrome |
| `captcha.vps1.ocoron.com` | A | 172.93.160.197 | Anti-Captcha solver |
| `coolify.vps1.ocoron.com` | A | 172.93.160.197 | Coolify dashboard |
| `dns.vps1.ocoron.com` | A | 172.93.160.197 | Site Provisioner (DNS Manager) |
| `emailgateway.vps1.ocoron.com` | A | 172.93.160.197 | Email Gateway API |
| `errors.vps1.ocoron.com` | A | 172.93.160.197 | GlitchTip error tracking |
| `files-api.vps1.ocoron.com` | A | 172.93.160.197 | File API |
| `images.vps1.ocoron.com` | A | 172.93.160.197 | Image Broker API |
| `monitor.vps1.ocoron.com` | A | 172.93.160.197 | Grafana dashboards |
| `netdata.vps1.ocoron.com` | A | 172.93.160.197 | Netdata real-time metrics |
| `notify.vps1.ocoron.com` | A | 172.93.160.197 | Apprise notifications |
| `pdf.vps1.ocoron.com` | A | 172.93.160.197 | Gotenberg PDF conversion |
| `proxy.vps1.ocoron.com` | A | 172.93.160.197 | Proxy management API |
| `search.vps1.ocoron.com` | A | 172.93.160.197 | MeiliSearch |
| `status.vps1.ocoron.com` | A | 172.93.160.197 | Gatus uptime monitor |
| `translator.vps1.ocoron.com` | A | 172.93.160.197 | Translation API |

## Service URLs

### Infrastructure (Authelia-protected unless noted)

| Service | URL | Auth | Purpose |
|---------|-----|------|---------|
| **Coolify** | `https://coolify.vps1.ocoron.com` | Authelia + Login | Container deployment |
| **Grafana** | `https://monitor.vps1.ocoron.com` | Authelia + Login | Dashboards (Prometheus + Loki) |
| **Netdata** | `https://netdata.vps1.ocoron.com` | Authelia | Real-time server metrics |
| **Backrest** | `https://backup.vps1.ocoron.com` | Authelia | Restic backup UI → Backblaze B2 |
| **n8n** | `https://auto.vps1.ocoron.com` | Authelia | Workflow automation |
| **Apprise** | `https://notify.vps1.ocoron.com` | Authelia | Multi-channel notifications |
| **GlitchTip** | `https://errors.vps1.ocoron.com` | App-layer TOTP | Error tracking |
| **Gatus** | `https://status.vps1.ocoron.com` | Public | Uptime monitoring (30 endpoints) |
| **Authelia** | `https://auth.vps1.ocoron.com` | — | SSO/2FA forward-auth |

### APIs (Fabrik Microservices)

| Service | URL | Health Check | Port | Purpose |
|---------|-----|--------------|------|---------|
| **Proxy** | `https://proxy.vps1.ocoron.com` | `/health` | 18013 | Webshare.io proxy management |
| **Captcha** | `https://captcha.vps1.ocoron.com` | `/health` | 18011 | Anti-Captcha solving |
| **Translator** | `https://translator.vps1.ocoron.com` | `/health` | 18012 | DeepL + Azure translation |
| **Site Provisioner** | `https://dns.vps1.ocoron.com` | `/health` | 18014 | Domain/DNS management |
| **Image Broker** | `https://images.vps1.ocoron.com` | `/api/v1/health` | 18016 | Stock image API |
| **Email Gateway** | `https://emailgateway.vps1.ocoron.com` | `/health` | 18017 | Resend + SES email |
| **File API** | `https://files-api.vps1.ocoron.com` | `/health` | 18015 | File operations |
| **File Worker** | (internal) | — | 8007 | Background file processing |
| **Browserless** | `https://browser.vps1.ocoron.com` | `/pressure` | 3000 | Headless Chrome |
| **Gotenberg** | `https://pdf.vps1.ocoron.com` | `/health` | 3000 | HTML/PDF conversion |
| **MeiliSearch** | `https://search.vps1.ocoron.com` | `/health` | 7700 | Full-text search |

### Websites

| Service | URL | Purpose |
|---------|-----|---------|
| **ocoron.com** | `https://ocoron.com` | WordPress (nginx + php-fpm + MariaDB + Redis) |

## Quick Health Checks

```bash
for url in \
  "https://proxy.vps1.ocoron.com/health" \
  "https://captcha.vps1.ocoron.com/health" \
  "https://dns.vps1.ocoron.com/health" \
  "https://images.vps1.ocoron.com/api/v1/health" \
  "https://emailgateway.vps1.ocoron.com/health" \
  "https://translator.vps1.ocoron.com/health" \
  "https://browser.vps1.ocoron.com/pressure" \
  "https://status.vps1.ocoron.com"; do
  echo -n "$url: "
  curl -s -o /dev/null -w "%{http_code}\n" "$url" --max-time 5
done
```
