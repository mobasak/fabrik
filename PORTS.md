# Fabrik Port Allocations

**Last Updated:** 2026-01-04

This document tracks port allocations for all Fabrik services to prevent conflicts.

---

## Port Ranges

| Range | Purpose | Environment |
|-------|---------|-------------|
| 3000-3099 | Frontend apps (Node.js) | WSL & VPS |
| 5000-5099 | Python services (misc) | WSL only |
| 8000-8099 | Python APIs (FastAPI) | WSL & VPS |
| 8100-8199 | Workers & background services | WSL & VPS |
| 8200-8299 | Management tools | VPS only |
| 19999 | Netdata monitoring | VPS only |

---

## Current Allocations

### Infrastructure Services (VPS)

| Port | Service | Project | URL |
|------|---------|---------|-----|
| 8000 | Coolify | coolify | https://coolify.vps1.ocoron.com |
| 3001 | Uptime Kuma | uptime-kuma | https://status.vps1.ocoron.com |
| 8200 | Duplicati | duplicati | https://backup.vps1.ocoron.com |
| 19999 | Netdata | netdata | https://netdata.vps1.ocoron.com |

### Fabrik Microservices (VPS)

| Port | Service | Project | URL |
|------|---------|---------|-----|
| 8000 | Translator API | /opt/translator | https://translator.vps1.ocoron.com |
| 8000 | Captcha Solver | /opt/captcha | https://captcha.vps1.ocoron.com |
| 8000 | Proxy Manager | /opt/proxy | https://proxy.vps1.ocoron.com |
| 8001 | DNS Manager | /opt/dns-manager | https://dns.vps1.ocoron.com |
| 8004 | File API | /opt/file-api | https://files-api.vps1.ocoron.com |
| 8010 | Image Broker | /opt/image-broker | https://images.vps1.ocoron.com |
| 3000 | Email Gateway | /opt/emailgateway | https://email.vps1.ocoron.com |

### Development Services (WSL Only)

| Port | Service | Project | Notes |
|------|---------|---------|-------|
| 5050 | Email Reader | /opt/email-reader | Gmail/M365 integration |
| 8000 | Local dev server | varies | Default FastAPI port |

---

## Port Conflict Resolution

If you encounter a port conflict:

1. Check this file for existing allocations
2. Choose the next available port in the appropriate range
3. Update this file with the new allocation
4. Update the service's `.env` and `compose.yaml`

---

## Notes

- **VPS services use Traefik reverse proxy** — External access is via HTTPS (port 443)
- **Internal container ports** — May differ from external ports (Traefik handles routing)
- **WSL ports** — Accessible directly via `localhost:<port>`
- **Docker networks** — Services communicate via container names, not ports

---

## Adding a New Service

1. Choose port from appropriate range
2. Add entry to this file
3. Configure in service's `.env`:
   ```
   PORT=8xxx
   ```
4. Configure in `compose.yaml`:
   ```yaml
   ports:
     - "8xxx:8xxx"
   ```
5. Add Traefik labels for external access (VPS only)
