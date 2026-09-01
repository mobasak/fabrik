---
activation: glob
globs: ["**/*.py"]
description: Python/FastAPI patterns, typing, environment handling
trigger: glob
---
<!-- CONSUMER: Coding agents (Claude Code + dispatched subagents)
     GOAL: Python/FastAPI implementation patterns — typing, config, error handling, async, Docker
     TRAYCER USAGE: Injects as Context File in tickets touching Python code. References specific sections in ticket ACs.
     AGENT USAGE: Follow verbatim when writing Python. Activated by glob on *.py files. -->

# Python Rules

**Activation:** Glob `**/*.py`
**Purpose:** FastAPI patterns, typing, environment handling

---

## Package Manager

**`uv`** is the mandated Python package manager. Never use raw `pip`, `pip install`, `poetry`, or `pipenv`.

```bash
uv sync                         # Install from lock
uv add httpx                    # Add dependency
uv run pytest                   # Run via uv
```

Dependencies live in `pyproject.toml` + `uv.lock`. Do not modify these files unless the ticket authorises it.

**Pinning policy:** `uv.lock` IS the pin — `pyproject.toml` uses `>=` floors, no routine upper
bounds (caps only for a documented breakage). Upgrades are DELIBERATE: `uv lock --upgrade` in
its own reviewed commit, never as a side effect of unrelated work.

---

## FastAPI Patterns

### Entry Point
```python
# src/main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI
from sqlalchemy import text
from src.database import engine, async_session

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: engine connects lazily — ping once to fail fast on bad config
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    yield
    # Shutdown: dispose the connection pool
    await engine.dispose()

app = FastAPI(title="ServiceName", lifespan=lifespan)

@app.get("/healthz")
async def healthz():
    # LIVENESS: dep-free by contract — Docker HEALTHCHECK targets THIS endpoint.
    # A dep-checking probe here restart-storms every container when postgres-main
    # blips (the shared-VPS failure mode); see 30-ops.md § HEALTHCHECK.
    return {"status": "alive"}

@app.get("/health")
async def health():
    # READINESS: MUST hit the real DB. A bare SQL string raises in modern
    # SQLAlchemy — use text(). Gatus + deploy-verify probe this one.
    async with async_session() as session:
        await session.execute(text("SELECT 1"))
    return {"status": "ok"}
```

**Note:** Use `lifespan` context manager, not deprecated `@app.on_event("startup")`. Imports resolve against the Async Database Session section below.

### Router Structure

Routers live under `src/api/`, one file per resource, `APIRouter(prefix=..., tags=[...])`.
The one RULE: use SQLAlchemy async consistently — never mix `async def` with sync
`.query().all()` (the Banned table row; the full session pattern is `25-data-postgres.md`'s).

### Async Database Session

The canonical `engine`, `async_session`, and `get_db` are defined in `src/database.py` — owned by `25-data-postgres.md`. Import from there, never redefine:

```python
# src/database.py — see 25-data-postgres.md § Transactions & Sessions for the full definition
from src.database import engine, async_session, get_db
```

---

## Config Loading (CRITICAL)

```python
# PREFERRED - Pydantic BaseSettings (FastAPI-idiomatic)
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    database_url: str                          # required — fail fast if unset
    redis_url: str = "redis://redis-main:6379/0"
    service_internal_secret_key: str           # required where internal_auth.py is wired
    # (35-security-auth) — a defaulted-empty secret is fail-OPEN; delete the field
    # entirely if this service exposes no internal API.
    # No discrete db_host/db_port/db_name. The env provides the full URL
    # (localhost in WSL, postgres-main on VPS). See 30-ops.md compose template.

@lru_cache
def get_settings() -> Settings:
    return Settings()

# Usage in routes
@app.get("/items")
async def list_items(settings: Settings = Depends(get_settings)):
    ...
```

```python
# WRONG - class-level (env not set at import time)
class Config:
    DB_URL = f"postgresql://{os.getenv('DB_HOST')}:..."  # Fails!

# WRONG - discrete vars assembled in code
def get_db_url() -> str:
    host = os.getenv('DB_HOST', 'postgres-main')  # banned — use DATABASE_URL directly
    ...
```

**Config convention:** apps read a complete `DATABASE_URL` (`postgresql+asyncpg://user:pass@host:port/db`) and `REDIS_URL` from env. Discrete `DB_HOST`/`DB_PORT`/`DB_NAME`/`DB_USER`/`DB_PASSWORD` for the app to assemble are **banned**. The env supplies the complete URL — `localhost` in WSL, `postgres-main` on VPS — so the host concern is an env-layer responsibility, never code logic. See `30-ops.md` compose template for how discrete vars are interpolated into `DATABASE_URL` at the compose level.

---

## Project Local Temp

```python
# CORRECT — per-project isolation in shared WSL dev + one path in both envs
from pathlib import Path
PROJECT_ROOT = Path(__file__).parent.parent
TEMP_DIR = PROJECT_ROOT / ".tmp"
TEMP_DIR.mkdir(exist_ok=True)

# WRONG in WSL dev — /tmp is box-global there: cross-project collisions + tmpwatch
import tempfile
temp_dir = tempfile.gettempdir()
```

**Ephemeral vs persistent — the real split:** `.tmp` contents are DISPOSABLE by contract (in a
container the writable layer dies on recreate exactly like `/tmp` does — that is fine, that is
what temp means). Anything that must SURVIVE a restart is not temp: it goes on a **named
volume** (`30-ops.md` § Volumes), never in `.tmp` and never in `/tmp`.

---

## Typing Standards

- Use type hints for all function signatures
- Use `list[str]` not `List[str]`; use `str | None` not `Optional[str]` — the typing module's
  capitalized generics and `Optional` are legacy forms on every Python this fleet runs
- Use Pydantic for request/response models

---

## Error Handling

```python
from fastapi import HTTPException
from {package}.logger import get_logger  # scaffolded structlog — see 55-observability.md

logger = get_logger(__name__)

# Specific exceptions
raise HTTPException(status_code=404, detail="Item not found")

# Logging handled errors (short event + context, not full traceback)
logger.error("item_processing_failed", item_id=item_id)
```

### FastAPI exception handling

**Default: NO try/except in routes.** Let exceptions propagate — the ONE global handler
(`15-api-contracts.md` § Error Schema) converts them to ProblemDetails and GlitchTip captures
the traceback. A blanket per-route catch is boilerplate that hides the original error.

**When you genuinely must catch** (cleanup, added context), the ORDER is critical — re-raise
`HTTPException` **before** any generic `except Exception` (`HTTPException` subclasses
`Exception`, so a bare catch silently converts your 403/404 responses into 500s) — and chain
the cause:

```python
try:
    result = await service.do_work()
except HTTPException:
    raise  # let FastAPI handle the response (preserves status code)
except Exception as exc:
    # Short event + correlation_id only — GlitchTip auto-captures the full traceback.
    # Do NOT use logger.exception() here — it duplicates the stacktrace in Loki.
    logger.error("do_work_failed", correlation_id=correlation_id)
    raise HTTPException(status_code=500, detail="internal error") from exc
```

**GlitchTip discipline:** unhandled exceptions (FastAPI 500s) are auto-captured by GlitchTip with full stacktraces. In the `except Exception` branch, log a **short event name + correlation_id** — never `logger.exception()` (that duplicates the traceback in Loki AND GlitchTip). See `55-observability.md` § Error Reporting for the full rule.

**Note:** `HTTPException` produces FastAPI's default `{"detail": "..."}` JSON. A global exception handler (see `15-api-contracts.md` § Error Schema) converts this into RFC 9457 `ProblemDetails` with `Content-Type: application/problem+json`. Raising `HTTPException` here is correct — the handler reshapes it on the way out.

**Note:** Use the scaffolded logger: `from {package}.logger import get_logger` (see `55-observability.md` § Pre-Scaffolded Logging). Do not use `structlog.get_logger()` directly or `logging.getLogger(__name__)`.

---

## Async Discipline (beyond the DB)

- **Never a bare `asyncio.create_task()`** — an unreferenced task is silently garbage-collected
  and its exceptions vanish. Hold the reference and await it, or use `asyncio.TaskGroup`.
- **One shared `httpx.AsyncClient`**, created in `lifespan`, closed on shutdown — per-request
  client construction burns connections. Timeouts/retries on every outbound call are owned by
  `58-resilience.md`.
- **`datetime.now(UTC)`, never `datetime.utcnow()`** — deprecated and naive; naive datetimes
  are a real cross-service defect class.

---

## Testing

Testing strategy, depth and the behavior-contract bar are owned by `45-testing-strategy.md` —
this pack only fixes the runner:

```bash
uv run pytest tests/             # Run all
uv run pytest -x --tb=short     # Stop on first failure
uv run pytest -k "test_health"  # Run specific
```

---

## Quality Gates

```bash
uv run ruff check .              # Lint
uv run ruff format .             # Format
uv run mypy .                    # Type check
```

Ruff's selected rule-sets MUST include `ASYNC` (blocking IO in async code — machine-enforces
this pack's hardest-to-review rule), `B` (bugbear) and `S` (bandit) alongside the defaults;
configured in `pyproject.toml`, emitted by the scaffolder.

---

## Running in Production

Production services run via `uvicorn` CLI in the Dockerfile, not `uvicorn.run()` in code. Base image is always `python:<version>-slim-bookworm` on `linux/amd64` (the Debian variant is pinned fleet-wide in `30-ops.md` § Base Images — change it THERE, never per-repo). Never use Alpine — musllinux wheels exist now (PEP 656) but coverage is still partial, source builds are dramatically slower, and musl's allocator/stack defaults degrade CPython; the trade never pays on this fleet.

```dockerfile
FROM python:<!--v:python_stable-->3.14<!--/v-->-slim-<!--v:debian_codename-->trixie<!--/v-->    # machine-injected from .windsurf/rules/versions.yaml (D-062) — never hand-edit the number
# ...
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

`uvicorn.run()` is for local development only. Never ship it in production code.

**One process per container is the RULE, not an accident of the example** — no `--workers`:
containers are memory-capped on a shared VPS and Traefik owns routing; CPU-bound saturation is
a fleet scaling decision (more containers), never a per-app flag.

---

## Port Range

Python services: **8000-8099**

```python
# Dev-only entry point (if __name__ block)
if __name__ == "__main__":
    import uvicorn
    PORT = int(os.getenv('PORT', '8000'))
    uvicorn.run("src.main:app", host="0.0.0.0", port=PORT, reload=True)
```

---

## 12-Factor: config, logs, migrations (CRITICAL)

These three fire in `**/*.py` — the only glob that catches where config is loaded, loggers are configured, and startup hooks are written.

**Factor III — Config.** Config lives in **env vars** (Pydantic Settings; see § Config Loading). The litmus test, verbatim from 12factor.net: *"whether the codebase could be made open source at any moment, without compromising any credentials."* Apply it to every change.
**BANNED: grouped/named env config sets.** 12F is explicit — *"env vars are granular controls, each fully orthogonal to other env vars"* — so a `config/production.yml`, a `settings.production` group, or a `config/{dev,staging,prod}.yaml` tree is a violation. Env vars are granular and set **per deploy**, never batched into a named "environment".

**Factor XI — Logs.** Structured JSON, **unbuffered**, to `stdout` — and nothing else (`PYTHONUNBUFFERED=1`).
**BANNED:** `logging.FileHandler`, `logging.handlers.RotatingFileHandler`, `TimedRotatingFileHandler`, `loguru` file sinks, any `*.log` file write, any in-app log rotation/retention/cleanup. The app never decides where logs are stored or routed — Docker → Promtail → Loki does. Full rule: `55-observability.md` § Logs.

**Factor XII — Admin processes. NEVER migrate from app startup.**
**BANNED: `alembic upgrade head` in FastAPI's `lifespan`, in an `@app.on_event("startup")`, or as an import side-effect.** With more than one replica (or a restart storm) two containers run `upgrade head` **concurrently** → they race the Alembic version table → duplicate DDL → **wedged deploy**. Migrations are a **one-off admin process against the deployed release**: `docker compose run --rm <svc> alembic upgrade head` (see `30-ops.md` § Release & Admin Processes).

---

## Banned Patterns

| Pattern | Use Instead |
|---------|-------------|
| `alembic upgrade head` in `lifespan` / startup hook | One-off admin process against the deployed release: `docker compose run --rm <svc> alembic upgrade head` (concurrent replicas race the version table) |
| `logging.FileHandler` / `RotatingFileHandler` / loguru file sink / any `*.log` write | Structured JSON → `stdout`, unbuffered (`PYTHONUNBUFFERED=1`). The platform routes logs, not the app |
| `config/production.yml` / `settings.production` grouped env sets | Granular, orthogonal env vars set per deploy (12-Factor III) |
| `pip` / `poetry` / `pipenv` | `uv` (`uv sync`, `uv add`, `uv run`) |
| Class-level config (`os.getenv` at import time) | Pydantic `BaseSettings` or function-level loading |
| `localhost` for DB/Redis host | `postgres-main` / `redis-main` via `DATABASE_URL` / `REDIS_URL` |
| Discrete `DB_HOST`/`DB_PORT`/`DB_NAME` env vars for the app | Single `DATABASE_URL` — env provides the full URL |
| `tempfile.gettempdir()` / `/tmp` | Project-relative `.tmp` (volume-mounted if persistence needed) |
| `List[str]` / `Optional[str]` | `list[str]` / `str \| None` |
| `async def` mixed with sync `.query().all()` | SQLAlchemy async: `select()` + `await session.execute()` |
| Bare-string `.execute("SELECT 1")` | `text("SELECT 1")` (modern SQLAlchemy requires it) |
| Sync HTTP/IO in an async route (blocks the event loop) | `httpx.AsyncClient`; `run_in_executor` for unavoidable sync libs |
| `@app.on_event("startup")` | `lifespan` async context manager |
| `logging.getLogger(__name__)` / `print()` | `structlog.get_logger()` imported from scaffold `logger.py` |
| Generic `except Exception` before re-raising `HTTPException` | Re-raise `HTTPException` first, then catch generic (and only when you must catch at all — the global handler is the default) |
| Bare `asyncio.create_task()` (unreferenced) | Hold the reference and await, or `asyncio.TaskGroup` |
| `datetime.utcnow()` | `datetime.now(UTC)` — deprecated and naive |
| Per-request `httpx.AsyncClient()` construction | One shared client in `lifespan`, closed on shutdown |
| `uvicorn.run()` in production code | `uvicorn` CLI in the Dockerfile |
| Alpine base image | `python:<version>-slim-bookworm` on `linux/amd64` |
| Editing `pyproject.toml` / `uv.lock` unprompted | Only when the ticket authorises it |

---

## Related Rule Packs

- `25-data-postgres.md` — PostgreSQL patterns, migrations, async sessions
- `30-ops.md` — Dockerfile, compose, Traefik, resource limits, deployment
- `55-observability.md` — structlog setup, `/health` + `/metrics`, GlitchTip
- `58-resilience.md` — timeout/retry/circuit-breaker for async external calls

---

## Done When

- [ ] All dependencies via `uv` — no `pip`/`poetry`/`pipenv`; `pyproject.toml` + `uv.lock` only.
- [ ] Config via Pydantic `BaseSettings` (or function-level) — DB host defaults to `postgres-main`, not `localhost`.
- [ ] `lifespan` context manager (not `on_event`); `/healthz` dep-free (HEALTHCHECK's target); `/health` runs `text("SELECT 1")` against the real DB.
- [ ] SQLAlchemy async used consistently — no sync `.query()` in `async def`; no blocking IO in async routes.
- [ ] Type hints on all signatures; `list[]` / `str | None`; Pydantic for request/response models.
- [ ] `HTTPException` re-raised before any generic `except Exception`.
- [ ] `structlog.get_logger()` from scaffold `logger.py` — no stdlib logging, no `print()`.
- [ ] `ruff check` (rule-sets incl. `ASYNC`/`B`/`S`), `ruff format`, `mypy` all pass.
- [ ] No bare `create_task`, no `datetime.utcnow()`, shared `AsyncClient` in `lifespan`.
- [ ] Production runs via `uvicorn` CLI in Dockerfile (`slim-bookworm`, `linux/amd64`) — no `uvicorn.run()`, no Alpine.
- [ ] Python service port within 8000-8099; registered in `PORTS.md`.
