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
| Coolify | coolify | 443 | coolify.vps1.ocoron.com | Deployment control plane |
| PostgreSQL | postgres-main | 5432 | - | Shared database |
| Redis | redis-main | 6379 | - | Caching (optional) |
| Uptime Kuma | uptime-kuma | 3001 | status.vps1.ocoron.com | Monitoring |
| Image Broker | image-broker | 8010 | images.vps1.ocoron.com | Stock image API |

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
uptime-kuma     Up 2 days
image-broker    Up 1 hour (healthy)
```
