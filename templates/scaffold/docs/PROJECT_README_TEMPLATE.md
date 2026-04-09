# [Project Name]

[One-line description]

**Type:** {python-api | node-api | saas-skeleton | chrome-extension | mobile-app | desktop-app | static-site}
**Port:** {PORT}

---

<!-- 2–3 sentences: what this project does, who it's for, what problem it solves. -->

## Features

<!-- Replace with actual features. Delete placeholder lines. -->

- **Feature 1** — Brief description
- **Feature 2** — Brief description
- **Feature 3** — Brief description

## Quick Start

```bash
cd /opt/[project]
cp .env.example .env
# Edit .env — fill required values

docker compose up -d
curl http://localhost:8000/health
```

<!-- For non-Docker local dev: -->
<!-- python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt -->
<!-- uvicorn src.<package_name>.main:app --reload --port 8000 -->

→ Full integration guide (endpoints, SDK modules, Docker wiring): [docs/QUICKSTART.md](docs/QUICKSTART.md)

## Documentation

| Document | Purpose |
|----------|---------|
| [QUICKSTART.md](docs/QUICKSTART.md) | Integration contract — endpoints, SDKs, Docker wiring, error handling |
| [CONFIGURATION.md](docs/CONFIGURATION.md) | All environment variables, defaults, examples |
| [FEATURES.md](docs/FEATURES.md) | Detailed feature documentation |
| [TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) | Common issues and solutions |
| [BUSINESS_MODEL.md](docs/BUSINESS_MODEL.md) | Go-to-market, pricing, positioning |
| [INDEX.md](INDEX.md) | Master file index — every file's purpose |
| [CHANGELOG.md](CHANGELOG.md) | Change history |

## Configuration

Key environment variables (see [CONFIGURATION.md](docs/CONFIGURATION.md) for full reference):

```bash
PORT=8000
LOG_LEVEL=INFO
# DATABASE_URL=postgresql://user:pass@postgres-main:5432/[project]_dev
```

## Tech Stack

<!-- Replace with actual stack. Delete lines that don't apply. -->

- **Runtime:** Python 3.12 / Node 22
- **Framework:** FastAPI / Next.js / Hono
- **Database:** PostgreSQL (shared `postgres-main:5432`)
- **Cache:** Redis (`redis:6379`)
- **Deployment:** Docker → Coolify → VPS

## Requirements

- Docker + Docker Compose
- `.env` configured from `.env.example`
