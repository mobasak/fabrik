# Coolify Real-time WebSocket Fix

> **📌 ARCHIVED 2026-06-06.** Historical document preserved as-is for context. Frozen at the time of original ship. For current fleet state see [`vps-status.md`](../vps-status.md), [`vps-complete-inventory.md`](../vps-complete-inventory.md), and [`vps-fleet-architecture.md`](../vps-fleet-architecture.md). Do NOT update the content below — that would defeat the archive.

**Date:** 2026-04-17
**Issue:** Coolify real-time service warning: "Cannot connect to real-time service"
**Root Cause:** Soketi WebSocket (ports 6001/6002) not accessible via HTTPS

## Solution: Traefik WebSocket Routing

### Implementation Steps

#### 1. Backup Current Configuration

```bash
ssh vps "sudo cp /data/coolify/source/docker-compose.yml /data/coolify/source/docker-compose.yml.backup.$(date +%Y%m%d)"
```

#### 2. Add Traefik Labels to Soketi Container

Edit `/data/coolify/source/docker-compose.yml` on VPS:

```yaml
soketi:
  container_name: coolify-realtime
  extra_hosts:
    - host.docker.internal:host-gateway
  restart: always
  networks:
    - coolify
  labels:
    - "traefik.enable=true"
    # WebSocket endpoint (port 6001)
    - "traefik.http.routers.coolify-ws.rule=Host(`coolify.vps1.ocoron.com`) && PathPrefix(`/app/`)"
    - "traefik.http.routers.coolify-ws.entrypoints=websecure"
    - "traefik.http.routers.coolify-ws.tls=true"
    - "traefik.http.routers.coolify-ws.tls.certresolver=letsencrypt"
    - "traefik.http.services.coolify-ws.loadbalancer.server.port=6001"
    # Terminal endpoint (port 6002)
    - "traefik.http.routers.coolify-terminal.rule=Host(`coolify.vps1.ocoron.com`) && PathPrefix(`/terminal/`)"
    - "traefik.http.routers.coolify-terminal.entrypoints=websecure"
    - "traefik.http.routers.coolify-terminal.tls=true"
    - "traefik.http.routers.coolify-terminal.tls.certresolver=letsencrypt"
    - "traefik.http.services.coolify-terminal.loadbalancer.server.port=6002"
```

#### 3. Restart Coolify Stack

```bash
ssh vps "cd /data/coolify/source && sudo docker compose down && sudo docker compose up -d"
```

Wait 30 seconds for services to stabilize.

#### 4. Verify WebSocket Connectivity

```bash
# Check Traefik routes
ssh vps "sudo docker logs traefik --tail=50 | grep coolify-ws"

# Test WebSocket endpoint
curl -I https://coolify.vps1.ocoron.com/app/
```

Expected: HTTP 101 Switching Protocols or 200 OK

#### 5. Clear Browser Cache

In Coolify UI:
1. Hard refresh (Ctrl+Shift+R)
2. Check browser console for WebSocket connection
3. Warning should disappear

## Security Benefits

✓ **SSL/TLS encrypted** - WebSocket traffic secured via HTTPS
✓ **No exposed ports** - 6001/6002 remain internal-only
✓ **Firewall compliant** - No iptables changes required
✓ **Authelia compatible** - Can add 2FA middleware if needed

## Troubleshooting

### Issue: Warning Still Appears

**Check Coolify environment variables:**

```bash
ssh vps "sudo docker exec coolify env | grep -E 'PUSHER|SOKETI'"
```

If `PUSHER_HOST` is set to `localhost` or `127.0.0.1`, update Coolify's `.env`:

```bash
PUSHER_HOST=coolify.vps1.ocoron.com
PUSHER_PORT=443
PUSHER_SCHEME=https
PUSHER_ENCRYPTED=true
```

Then restart: `ssh vps "cd /data/coolify/source && sudo docker compose restart coolify"`

### Issue: WebSocket Connection Refused

**Check Traefik routing:**

```bash
ssh vps "sudo docker logs traefik --tail=100 | grep -E 'coolify-ws|error'"
```

**Verify Soketi is running:**

```bash
ssh vps "sudo docker logs coolify-realtime --tail=20"
```

Expected output: "Server is up and running!"

### Issue: SSL Certificate Error

Wait 1-2 minutes for Let's Encrypt certificate generation.

Check certificate status:

```bash
ssh vps "sudo docker logs traefik --tail=50 | grep -i acme"
```

## Rollback Procedure

If issues occur:

```bash
# Restore backup
ssh vps "sudo cp /data/coolify/source/docker-compose.yml.backup.YYYYMMDD /data/coolify/source/docker-compose.yml"

# Restart
ssh vps "cd /data/coolify/source && sudo docker compose down && sudo docker compose up -d"
```

The warning will reappear, but Coolify core functionality remains intact.

## Alternative: Subdomain Approach

For cleaner routing, use a dedicated subdomain:

### 1. Add DNS Record

```bash
# Via Cloudflare API
curl -X POST "https://api.cloudflare.com/client/v4/zones/<REDACTED-CF-ZONE-ID>/dns_records" \
  -H "Authorization: Bearer <REDACTED-CF-API-TOKEN>" \
  -H "Content-Type: application/json" \
  --data '{"type":"A","name":"ws.coolify.vps1","content":"172.93.160.197","ttl":300,"proxied":false}'
```

### 2. Update Traefik Labels

```yaml
labels:
  - "traefik.enable=true"
  - "traefik.http.routers.coolify-ws.rule=Host(`ws.coolify.vps1.ocoron.com`)"
  - "traefik.http.routers.coolify-ws.entrypoints=websecure"
  - "traefik.http.routers.coolify-ws.tls=true"
  - "traefik.http.routers.coolify-ws.tls.certresolver=letsencrypt"
  - "traefik.http.services.coolify-ws.loadbalancer.server.port=6001"
```

### 3. Update Coolify Environment

```bash
PUSHER_HOST=ws.coolify.vps1.ocoron.com
```

## References

- **Coolify Docs:** https://coolify.io/docs
- **Traefik WebSocket:** https://doc.traefik.io/traefik/routing/routers/#websocket
- **Soketi:** https://docs.soketi.app/
- **VPS File:** `/data/coolify/source/docker-compose.yml`
