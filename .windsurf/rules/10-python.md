---
activation: glob
globs: ["**/*.py"]
description: Python/FastAPI patterns, typing, environment handling
trigger: glob
---
<!-- CONSUMER: Coding agents (Claude Code, Windsurf Cascade, Kilo CLI)
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

---

## FastAPI Patterns

### Entry Point
```python
# src/main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: connect DB, load models, etc.
    await db.connect()
    yield
    # Shutdown: cleanup
    await db.disconnect()

app = FastAPI(title="ServiceName", lifespan=lifespan)

@app.get("/health")
async def health():
    # MUST test actual dependencies
    await db.execute("SELECT 1")
    return {"status": "ok"}
```

**Note:** Use `lifespan` context manager, not deprecated `@app.on_event("startup")`.

### Router Structure
```python
# src/api/items.py
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/items", tags=["items"])

@router.get("/")
async def list_items(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Item))
    return result.scalars().all()
```

**Note:** Use either sync SQLAlchemy or `sqlalchemy.ext.asyncio` — do not mix `async def` with sync `.query().all()`.

### Async Database Session
```python
# src/database.py
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from src.config import get_settings

engine = create_async_engine(get_settings().database_url, echo=False)
async_session = async_sessionmaker(engine, expire_on_commit=False)

async def get_db() -> AsyncSession:
    async with async_session() as session:
        yield session
```

---

## Config Loading (CRITICAL)

```python
# PREFERRED - Pydantic BaseSettings (FastAPI-idiomatic)
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    db_host: str = "postgres-main"
    db_port: int = 5432
    db_name: str = "app"

    @property
    def database_url(self) -> str:
        return f"postgresql+asyncpg://{self.db_host}:{self.db_port}/{self.db_name}"

@lru_cache
def get_settings() -> Settings:
    return Settings()

# Usage in routes
@app.get("/items")
async def list_items(settings: Settings = Depends(get_settings)):
    ...
```

```python
# ALSO CORRECT - simple function-level loading
def get_db_url() -> str:
    host = os.getenv('DB_HOST', 'postgres-main')
    port = os.getenv('DB_PORT', '5432')
    return f"postgresql://{host}:{port}/db"

# WRONG - class-level (env not set at import time)
class Config:
    DB_URL = f"postgresql://{os.getenv('DB_HOST')}:..."  # Fails!
```

**CRITICAL:** Default DB host is `postgres-main`, not `localhost`. Default Redis host is `redis-main`. `localhost` inside a container points to the container itself, not the shared database.

---

## Project Local Temp

```python
# CORRECT
from pathlib import Path
PROJECT_ROOT = Path(__file__).parent.parent
TEMP_DIR = PROJECT_ROOT / ".tmp"
TEMP_DIR.mkdir(exist_ok=True)

# WRONG - data loss on restart
import tempfile
temp_dir = tempfile.gettempdir()  # /tmp - shared, deleted
```

---

## Typing Standards

- Use type hints for all function signatures
- Use `list[str]` not `List[str]` (Python 3.9+)
- Use `str | None` not `Optional[str]` (Python 3.10+)
- Use Pydantic for request/response models

---

## Error Handling

```python
from fastapi import HTTPException
import structlog

logger = structlog.get_logger()

# Specific exceptions
raise HTTPException(status_code=404, detail="Item not found")

# Logging errors (structlog, not stdlib logging)
logger.exception("Failed to process item", item_id=item_id)
```

### FastAPI exception order (CRITICAL)

Always re-raise `HTTPException` **before** any generic `except Exception` — `HTTPException` is a subclass of `Exception`, so a bare catch silently converts your 403/404 responses into 500s.

```python
try:
    result = await service.do_work()
except HTTPException:
    raise  # let FastAPI handle the response (preserves status code)
except Exception:
    logger.exception("Unexpected error in do_work")
    raise HTTPException(status_code=500, detail="internal error")
```

For logging/GlitchTip capture inside the `except Exception` branch, see `55-observability.md` § Error Reporting — `logger.exception()` here would duplicate GlitchTip's traceback.

**Note:** Use `structlog.get_logger()`, not `logging.getLogger(__name__)`. The scaffold emits a pre-configured structlog setup in `logger.py` — import from there, do not create your own.

---

## Testing

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

---

## Running in Production

Production services run via `uvicorn` CLI in the Dockerfile, not `uvicorn.run()` in code. Base image is always `python:<version>-slim-bookworm` on `linux/amd64`. Never use Alpine (musl libc breaks wheels).

```dockerfile
FROM python:3.12-slim-bookworm
# ...
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

`uvicorn.run()` is for local development only. Never ship it in production code.

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
