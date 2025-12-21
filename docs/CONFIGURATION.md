# Configuration

All Fabrik configuration options.

## Environment Variables

### VPS Connection

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `VPS_HOST` | Yes | VPS IP or hostname | `172.93.160.197` |
| `VPS_USER` | Yes | SSH user | `deploy` |
| `VPS_SSH_KEY` | No | Path to SSH key | `~/.ssh/id_rsa` |

### Coolify API

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `COOLIFY_API_URL` | Yes | Coolify dashboard URL | `https://coolify.example.com` |
| `COOLIFY_API_TOKEN` | Yes | API token from Coolify | `token_xxx` |

### Namecheap DNS

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `NAMECHEAP_API_USER` | Yes | API username | `youruser` |
| `NAMECHEAP_API_KEY` | Yes | API key | `xxx` |
| `NAMECHEAP_CLIENT_IP` | Yes | Your whitelisted IP | `1.2.3.4` |

### Cloudflare DNS (Phase 4+)

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `CLOUDFLARE_API_TOKEN` | No | API token | `xxx` |
| `CLOUDFLARE_ZONE_ID` | No | Zone ID | `xxx` |

### Backblaze B2 (Backups)

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `B2_KEY_ID` | Yes | Application key ID | `xxx` |
| `B2_APPLICATION_KEY` | Yes | Application key | `xxx` |
| `B2_BUCKET_NAME` | Yes | Bucket for backups | `fabrik-backups` |

### Logging

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `LOG_LEVEL` | No | `INFO` | DEBUG, INFO, WARNING, ERROR |
| `LOG_FORMAT` | No | `json` | `json` or `text` |

## Config Files

### config/platform.yaml

Main platform configuration:

```yaml
vps:
  host: ${VPS_HOST}
  user: ${VPS_USER}

coolify:
  url: ${COOLIFY_API_URL}
  
dns:
  provider: namecheap  # or cloudflare
  
backup:
  provider: b2
  schedule: "0 2 * * *"  # 2 AM daily
```

### specs/*.yaml

App specification files. See [Deployment](DEPLOYMENT.md) for spec format.

## File Locations

| Path | Purpose |
|------|---------|
| `.env` | Environment variables (gitignored) |
| `.env.example` | Template for .env |
| `config/` | YAML configuration files |
| `specs/` | App specification files |
| `templates/` | Compose templates |
