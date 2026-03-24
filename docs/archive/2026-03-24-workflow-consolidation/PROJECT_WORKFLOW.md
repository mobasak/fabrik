# Project Workflow Guide

**Last Updated:** 2026-01-04

**Start here** for any new or existing project in `/opt/`.

---

## Step 1: Decide Project Type

Before creating a project, answer: **Does it need to run continuously?**

| Project Type | Runs 24/7? | Container? | Deploy Method |
|--------------|------------|------------|---------------|
| **Service** (API, web app) | ✅ Yes | ✅ Yes | `fabrik apply` → Coolify |
| **Worker** (queue processor) | ✅ Yes | ✅ Yes | Same compose.yaml |
| **Library** | ❌ No | ❌ No | `pip install` on VPS |
| **CLI Tool** | ❌ No | ❌ No | `rsync` to VPS |
| **Script** | ❌ No | ❌ No | Run locally or rsync |

### Quick Decision

```
Listens on a port OR runs 24/7?
├── YES → Container (Dockerfile + compose.yaml + Coolify)
└── NO  → No container (just sync code to VPS)
```

---

## Step 2: Create Project

### Services (need container)

```bash
fabrik scaffold my-api -d "REST API for users"
cd /opt/my-api

# Add Docker files from templates
cp /opt/fabrik/templates/scaffold/docker/Dockerfile.python Dockerfile
cp /opt/fabrik/templates/scaffold/docker/compose.yaml.template compose.yaml
cp /opt/fabrik/templates/scaffold/docker/dockerignore.template .dockerignore
```

### Libraries/Tools (no container)

```bash
fabrik scaffold my-tool -d "CLI utility"
cd /opt/my-tool
# Just code - no Docker files needed
```

---

## Step 3: Develop Locally

```bash
# Fast local dev (all project types)
uv venv && source .venv/bin/activate
uv pip install -e .

# For services: verify Docker works before deploy
docker build -t my-api . && docker run -p 8000:8000 my-api
```

---

## Step 4: Deploy

### Services → Coolify

```bash
fabrik new my-api --template python-api --domain api.example.com
fabrik apply specs/my-api.yaml
```

### Libraries/Tools → Direct Sync

```bash
rsync -avz --exclude='.venv' /opt/my-tool vps:/opt/
```

---

## Existing Projects

```bash
# Check compliance
fabrik validate /opt/my-project

# Fix missing files automatically
fabrik fix /opt/my-project --dry-run  # Preview
fabrik fix /opt/my-project            # Apply

# Add rules if missing manually
ln -s /opt/fabrik/windsurfrules /opt/my-project/.windsurfrules
```

---

## What windsurfrules Enforces

- **All projects**: Documentation structure, .env.example, no hardcoded localhost
- **Services only**: Dockerfile, compose.yaml, health endpoint, 0.0.0.0 binding

The rules assume services by default. For libraries/tools, ignore Docker sections.
