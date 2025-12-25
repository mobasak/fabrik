# VPS1 Service URLs

All services deployed on VPS1 (172.93.160.197) with HTTPS via Traefik.

## DNS Records (Cloudflare)

| Subdomain | Type | IP | Service |
|-----------|------|-----|---------|
| `vps1.ocoron.com` | A | 172.93.160.197 | Base domain |
| `backup.vps1.ocoron.com` | A | 172.93.160.197 | Duplicati backup UI |
| `captcha.vps1.ocoron.com` | A | 172.93.160.197 | Anti-Captcha proxy |
| `dns.vps1.ocoron.com` | A | 172.93.160.197 | DNS Manager API |
| `files-api.vps1.ocoron.com` | A | 172.93.160.197 | File API service |
| `images.vps1.ocoron.com` | A | 172.93.160.197 | Image Broker API |
| `netdata.vps1.ocoron.com` | A | 172.93.160.197 | Netdata monitoring |
| `status.vps1.ocoron.com` | A | 172.93.160.197 | Uptime Kuma |
| `translator.vps1.ocoron.com` | A | 172.93.160.197 | Translation API |
| `wp-test.vps1.ocoron.com` | A | 172.93.160.197 | WordPress test site |

## Service URLs

### Infrastructure

| Service | URL | Auth | Purpose |
|---------|-----|------|---------|
| **Coolify** | `https://vps1.ocoron.com:8000` | Login | Container deployment |
| **Netdata** | `https://netdata.vps1.ocoron.com` | None | System monitoring |
| **Uptime Kuma** | `https://status.vps1.ocoron.com` | Login | Service monitoring |
| **Duplicati** | `https://backup.vps1.ocoron.com` | Password | Backup management |

### APIs

| Service | URL | Health Check | Purpose |
|---------|-----|--------------|---------|
| **Image Broker** | `https://images.vps1.ocoron.com` | `/api/v1/health` | Stock image API |
| **DNS Manager** | `https://dns.vps1.ocoron.com` | `/health` | DNS record management |
| **Translator** | `https://translator.vps1.ocoron.com` | `/health` | Translation API |
| **Captcha** | `https://captcha.vps1.ocoron.com` | `/health` | Anti-Captcha proxy |
| **File API** | `https://files-api.vps1.ocoron.com` | `/health` | File storage API |

### Applications

| Service | URL | Purpose |
|---------|-----|---------|
| **WP Test** | `https://wp-test.vps1.ocoron.com` | WordPress test site |

## Quick Health Checks

```bash
# All services
for url in \
  "https://images.vps1.ocoron.com/api/v1/health" \
  "https://dns.vps1.ocoron.com/health" \
  "https://translator.vps1.ocoron.com/health" \
  "https://captcha.vps1.ocoron.com/health" \
  "https://status.vps1.ocoron.com"; do
  echo -n "$url: "
  curl -s -o /dev/null -w "%{http_code}\n" "$url" --max-time 5
done
```

## DNS Management

DNS records are managed via the DNS Manager API at `https://dns.vps1.ocoron.com`.

### Add Subdomain

```bash
curl -X POST "https://dns.vps1.ocoron.com/api/cloudflare/dns/ocoron.com/subdomain" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $DNS_API_KEY" \
  -d '{"subdomain": "myservice.vps1", "type": "A", "ip": "172.93.160.197"}'
```

### List Records

```bash
curl -s "https://dns.vps1.ocoron.com/api/cloudflare/dns/ocoron.com" \
  -H "X-API-Key: $DNS_API_KEY"
```

## Container to URL Mapping

| Container | Port | URL |
|-----------|------|-----|
| `coolify` | 8000 | `https://vps1.ocoron.com:8000` |
| `netdata` | 19999 | `https://netdata.vps1.ocoron.com` |
| `uptime-kuma` | 3001 | `https://status.vps1.ocoron.com` |
| `duplicati` | 8200 | `https://backup.vps1.ocoron.com` |
| `image-broker` | 8010 | `https://images.vps1.ocoron.com` |
| `dns-manager` | 8001 | `https://dns.vps1.ocoron.com` |
| `translator` | 8002 | `https://translator.vps1.ocoron.com` |
| `captcha` | 8003 | `https://captcha.vps1.ocoron.com` |
| `file-api` | 8004 | `https://files-api.vps1.ocoron.com` |
| `wp-test-wordpress` | 80 | `https://wp-test.vps1.ocoron.com` |
