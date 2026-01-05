# Deployment

How Fabrik deploys applications to production.

## Architecture

```text
┌─────────────────┐      ┌─────────────────┐      ┌─────────────────┐
│   Spec File     │ ──▶  │   Fabrik CLI    │ ──▶  │    Coolify      │
│  (specs/*.yaml) │      │  plan → apply   │      │  Docker Compose │
└─────────────────┘      └─────────────────┘      └─────────────────┘
                                │
                                ▼
                         ┌─────────────────┐
                         │   DNS Provider  │
                         │ Namecheap/CF    │
                         └─────────────────┘
```

## Spec File Format

### Python API

```yaml
# specs/my-api.yaml
name: my-api
type: python-api
domain: api.example.com

environment:
  DATABASE_URL: ${DATABASE_URL:?}
  LOG_LEVEL: ${LOG_LEVEL:-info}

resources:
  cpu: 1
  memory: 512M

healthcheck:
  path: /health
  interval: 30s
```

### WordPress Site

```yaml
# specs/my-site.yaml
name: my-site
type: wordpress
domain: www.example.com

wordpress:
  title: "My Site"
  admin_user: admin
  admin_email: admin@example.com

plugins:
  - contact-form-7
  - yoast-seo

theme: flavor
```

## CLI Commands

### Create New App

```bash
# From template
fabrik new python-api my-api
fabrik new wordpress my-site

# Lists available templates
fabrik templates
```

### Preview Changes

```bash
# Shows what will be created/modified
fabrik plan my-api
```

Output:

```text
Plan: my-api
──────────────────────────────
+ DNS: api.example.com → 172.93.160.197
+ Coolify: Create application "my-api"
+ Coolify: Deploy from template python-api
+ SSL: Request Let's Encrypt certificate

Apply with: fabrik apply my-api
```

### Apply Changes

```bash
# Deploy/update
fabrik apply my-api

# Force redeploy
fabrik apply my-api --force
```

### Status & Logs

```bash
# Check status
fabrik status my-api

# View logs
fabrik logs my-api
fabrik logs my-api --follow
```

## Ports

Fabrik assigns ports automatically. Check `/opt/fabrik/PORTS.md` for allocations.

| Range | Purpose |
|-------|---------|
| 8000-8099 | Python APIs |
| 8100-8199 | Workers |
| 3000-3099 | Frontend apps |

## Backups

Database backups are configured via Coolify:

- Schedule: Daily at 2 AM
- Retention: 7 days
- Destination: Backblaze B2

```bash
# Manual backup
fabrik backup my-api

# List backups
fabrik backups my-api

# Restore
fabrik restore my-api --backup 2024-12-21
```

## SSL/HTTPS

Coolify handles SSL via Let's Encrypt automatically when:

1. Domain DNS points to VPS IP
2. Ports 80/443 are open
3. Domain is configured in spec

No manual certificate management needed.

---

## Build & Deploy Strategy

### Option 1: Coolify Builds from GitHub (Current)

Coolify pulls repo and builds Docker image using Dockerfile or Docker Compose build pack.

```
GitHub Push → Coolify Pull → Build on VPS → Deploy
```

**Pros:**
- No registry needed
- Source-of-truth stays in GitHub
- Simple setup

**Cons:**
- Builds happen on VPS (slower for heavy images)
- VPS must have enough resources for builds

**Use when:** Standard services, early stage, non-ML workloads.

### Option 2: GHCR Registry (Future - ML/Heavy Builds)

GitHub Actions builds image, pushes to GHCR, Coolify pulls pre-built image.

```
GitHub Push → Actions Build → GHCR Push → Coolify Pull → Deploy
```

**Pros:**
- Faster deploys (no build on VPS)
- Repeatable builds
- Easy rollbacks via image tags

**Cons:**
- More complex setup
- Need multi-arch builds for ARM64

**Use when:** ML models, large dependencies, need quick rollbacks.

### ARM64 Consideration

**VPS is ARM64 (aarch64).** When using Option 2 (GHCR), builds need:

```yaml
# .github/workflows/build.yaml
- name: Build and push
  uses: docker/build-push-action@v5
  with:
    platforms: linux/arm64
    push: true
    tags: ghcr.io/${{ github.repository }}:${{ github.sha }}
```

### Decision Matrix

| Factor | Option 1 (Coolify Build) | Option 2 (GHCR) |
|--------|--------------------------|-----------------|
| Setup complexity | Low | Medium |
| Build time | On VPS | On GitHub runners |
| Best for | Standard apps | ML, heavy deps |
| Rollback | Redeploy from Git | Pull previous tag |

### Current Fabrik Default

All services use **Option 1** until a specific project needs Option 2.

Criteria to switch:
- Build takes >10 minutes on VPS
- Image size >2GB
- Need instant rollbacks
