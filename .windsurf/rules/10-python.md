---
activation: glob
globs: ["**/*.py"]
description: Python/FastAPI patterns, typing, environment handling
trigger: glob
---

# Python Rules

**Activation:** Glob `**/*.py`
**Purpose:** FastAPI patterns, typing, environment handling

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
router = APIRouter(prefix="/items", tags=["items"])

@router.get("/")
async def list_items(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Item))
    return result.scalars().all()
```

**Note:** Use either sync SQLAlchemy or `sqlalchemy.ext.asyncio` — do not mix `async def` with sync `.query().all()`.

---

## Config Loading (CRITICAL)

```python
# PREFERRED - Pydantic BaseSettings (FastAPI-idiomatic)
from functools import lru_cache
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "app"

    class Config:
        env_file = ".env"

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
    host = os.getenv('DB_HOST', 'localhost')
    port = os.getenv('DB_PORT', '5432')
    return f"postgresql://{host}:{port}/db"

# WRONG - class-level (env not set at import time)
class Config:
    DB_URL = f"postgresql://{os.getenv('DB_HOST')}:..."  # Fails!
```

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

# Specific exceptions
raise HTTPException(status_code=404, detail="Item not found")

# Logging errors
import logging
logger = logging.getLogger(__name__)
logger.exception("Failed to process item")
```

---

## Testing

```bash
pytest tests/                    # Run all
pytest -x --tb=short            # Stop on first failure
pytest -k "test_health"         # Run specific
```

---

## Quality Gates

```bash
ruff check .                    # Lint
ruff format .                   # Format
mypy .                          # Type check
```

---

## Port Range

Python services: **8000-8099**

```python
# Default port
PORT = int(os.getenv('PORT', '8000'))
uvicorn.run(app, host="0.0.0.0", port=PORT)
```
