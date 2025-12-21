# Fabrik

**Deployment automation CLI for AI-powered infrastructure.**

Fabrik enables spec-driven deployment of Python APIs, WordPress sites, and AI-integrated applications via Coolify.

## Overview

- **Spec-driven:** Define apps in YAML → `fabrik apply` → deployed with HTTPS, DNS, backups
- **DNS automation:** Namecheap/Cloudflare record management without destroying existing records
- **WordPress automation:** Themes, plugins, content management via CLI
- **AI integration:** Windsurf agents can generate and publish content

## Quick Start

```bash
# Deploy a Python API
fabrik new python-api my-api
fabrik plan my-api
fabrik apply my-api

# Deploy a WordPress site
fabrik new wordpress my-site
fabrik apply my-site
```

See [docs/QUICKSTART.md](docs/QUICKSTART.md) for detailed setup instructions.

## Architecture

```text
WSL (Dev)                    VPS (Production)
┌─────────────┐              ┌─────────────────┐
│  Windsurf   │──── SSH ────▶│    Coolify      │
│  Fabrik CLI │              │  Docker Compose │
└─────────────┘              └─────────────────┘
```

## Project Status

**Phase 1: Foundation** — In Progress

See [tasks.md](tasks.md) for current progress.

## Documentation

- [Quick Start](docs/QUICKSTART.md)
- [Configuration](docs/CONFIGURATION.md)
- [Deployment](docs/DEPLOYMENT.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)
- [Roadmap](docs/reference/roadmap.md)

## Tech Stack

| Component | Technology |
|-----------|------------|
| CLI | Python (Click/Typer) |
| Deployment | Coolify API |
| DNS | Namecheap API / Cloudflare API |
| Database | PostgreSQL 16 |
| Containers | Docker Compose |

## License

Proprietary — All rights reserved.
