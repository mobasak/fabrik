# Quick Start

**Last Updated:** 2026-01-07

Get Fabrik running in 5 minutes.

## Prerequisites

Before starting, ensure you have:

- [ ] VPS with SSH access configured
- [ ] SSH key pair (public key on VPS)
- [ ] Namecheap account with API access
- [ ] Backblaze B2 account
- [ ] A domain you control

## Installation

```bash
# Clone/navigate to project
cd /opt/fabrik

# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -e .
```

## Configuration

```bash
# Copy example environment file
cp .env.example .env

# Edit with your credentials
nano .env
```

Required variables:

```bash
# VPS
VPS_HOST=your-vps-ip
VPS_USER=deploy

# Coolify
COOLIFY_API_URL=https://coolify.yourdomain.com
COOLIFY_API_TOKEN=your-token

# DNS Manager
DNS_MANAGER_URL=https://dns.vps1.ocoron.com

# Or use Cloudflare (optional)
# CLOUDFLARE_API_TOKEN=your-token
# CLOUDFLARE_ZONE_ID=your-zone-id

# Backblaze B2 (backups)
B2_KEY_ID=your-key-id
B2_APPLICATION_KEY=your-app-key
B2_BUCKET_NAME=your-bucket
```

## First Deployment

```bash
# Create a new Python API spec
fabrik new python-api hello-api

# Preview what will be deployed
fabrik plan hello-api

# Deploy
fabrik apply hello-api
```

## Verify

```bash
# Check deployment status
fabrik status hello-api

# Test endpoint
curl https://hello-api.yourdomain.com/health
```

## Next Steps

- [Configuration Reference](CONFIGURATION.md) — All settings explained
- [Deployment Guide](DEPLOYMENT.md) — Detailed deployment options
- [VPS Status](operations/vps-status.md) — Current VPS state and configuration
