# Docker Templates

Templates for container-first development.

## Files

| Template | Copy To | Purpose |
|----------|---------|---------|
| `Dockerfile.python` | `Dockerfile` | Multi-stage Python FastAPI build |
| `Dockerfile.node` | `Dockerfile` | Multi-stage Node.js build |
| `compose.yaml.template` | `compose.yaml` | Production-like compose (VPS deploy via `fabrik apply`) |
| `compose.dev.yaml.template` | `compose.dev.yaml` | Dev overrides (hot reload) |
| `dockerignore.template` | `.dockerignore` | Exclude files from build |
| `Makefile.python` | `Makefile` | Python project commands |
| `Makefile.node` | `Makefile` | Node.js project commands |

## Usage

```bash
# Files are already included when using 'fabrik scaffold'
# If you need to regenerate, use:
fabrik scaffold <project-name> --type python-api
```

## Container-First Principle

**Container-first but not container-only:**

- Write code with local tooling (venv/npm) for **speed**
- Keep a working Dockerfile + compose from **day 1**
- Use Docker as the **truth for production parity**

## Two-Mode Compose Pattern

- `compose.yaml` → Production-like (no bind mounts, no dev tools)
- `compose.dev.yaml` → Dev overrides (hot reload, debug)

```bash
# Production test
docker compose up --build

# Development (hot reload)
docker compose -f compose.yaml -f compose.dev.yaml up --build
```

## Standard Makefile Commands

| Command | Purpose |
|---------|---------|
| `make dev` | Local development with hot reload |
| `make test` | Run tests |
| `make lint` | Lint code |
| `make docker-smoke` | Build + run + health check (before push) |
| `make docker-dev` | Run in container with dev overrides |

## Related Templates

- `docs/DEPLOYMENT_TEMPLATE.md` → Deployment documentation
- `python/pyproject.toml.template` → Python project config
- `scripts/watchdog_template.sh` → Service watchdog
- `pre-commit-config.yaml` → Pre-commit hooks
