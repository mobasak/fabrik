# Required Services

Services Fabrik needs to function.

## Services This Project Runs

| Service | Port | Health Endpoint | Watchdog | Purpose |
|---------|------|-----------------|----------|---------|
| Fabrik CLI | - | - | - | Command-line tool (not a daemon) |

*Note: Fabrik is a CLI tool, not a long-running service. It calls external services.*

## External Dependencies

| Service | Required | Purpose | Fallback |
|---------|----------|---------|----------|
| **Coolify** | Yes | Container deployment | None |
| **PostgreSQL** | Yes | Database (via Coolify) | None |
| **Namecheap API** | Yes* | DNS management | Cloudflare (Phase 4) |
| **Backblaze B2** | Yes | Backup storage | None |
| **Redis** | Optional | Caching | Works without |

*Required until Phase 4 Cloudflare migration.

## VPS Services (Managed by Coolify)

| Service | Container | Port | URL | Purpose |
|---------|-----------|------|-----|---------|
| Coolify | coolify | 8000 | `https://vps1.ocoron.com:8000` | Deployment control plane |
| PostgreSQL | postgres-main | 5432 | - | Shared database |
| Redis | redis-main | 6379 | - | Caching (optional) |
| Netdata | netdata | 19999 | `https://netdata.vps1.ocoron.com` | System monitoring |
| Uptime Kuma | uptime-kuma | 3001 | `https://status.vps1.ocoron.com` | Service monitoring |
| Duplicati | duplicati | 8200 | `https://backup.vps1.ocoron.com` | Backup management |
| Image Broker | image-broker | 8010 | `https://images.vps1.ocoron.com` | Stock image API |
| DNS Manager | dns-manager | 8001 | `https://dns.vps1.ocoron.com` | DNS record management |
| Translator | translator | 8002 | `https://translator.vps1.ocoron.com` | Translation API |
| Captcha | captcha | 8003 | `https://captcha.vps1.ocoron.com` | Anti-Captcha proxy |
| File API | file-api | 8004 | `https://files-api.vps1.ocoron.com` | File storage API |

See [docs/reference/vps-urls.md](reference/vps-urls.md) for complete URL reference.

## Startup Order

For VPS setup (one-time):

1. Docker (system service)
2. Coolify (self-managing)
3. postgres-main (Coolify database)
4. redis-main (Coolify database)
5. Uptime Kuma (Coolify application)

For Fabrik usage (each run):

1. Ensure VPS is accessible
2. Ensure Coolify API is reachable
3. Run `fabrik` commands

## Health Checks

### Coolify

```bash
curl -s https://coolify.yourdomain.com/api/health
```

### PostgreSQL

```bash
ssh deploy@vps "docker exec postgres-main pg_isready"
```

### Uptime Kuma

```bash
curl -s https://status.vps1.ocoron.com
```

### Image Broker

```bash
curl -s https://images.vps1.ocoron.com/api/v1/health
```

### Netdata

```bash
curl -s https://netdata.vps1.ocoron.com
```

### DNS Manager

```bash
curl -s https://dns.vps1.ocoron.com/health
```

## Quick Status Check

```bash
# From WSL
ssh deploy@vps "docker ps --format 'table {{.Names}}\t{{.Status}}'"
```

Expected output:

```text
NAMES           STATUS
coolify         Up 2 days
postgres-main   Up 2 days
redis-main      Up 2 days
netdata         Up 2 days
uptime-kuma     Up 2 days
duplicati       Up 2 days
image-broker    Up 1 hour (healthy)
dns-manager     Up 2 days
translator      Up 2 days
captcha         Up 2 days
file-api        Up 2 days
```
