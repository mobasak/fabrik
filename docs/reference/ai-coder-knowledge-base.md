# AI Coder Pre-Implementation Knowledge Base

**Last Updated:** 2026-03-21
**Purpose:** Reference document for planning and human documentation.
**Usage:** NOT injected into agent prompts. Agents read AGENTS.md (Kilo CLI) or .windsurf/rules/ (Cascade).
**Used by:** Traycer (planning decisions), humans (onboarding, reference).

---

## Why This Document Exists

This is a **reference-only** document — it is NOT loaded into agent prompts (too large: ~11k tokens).

Agents get their rules from:
- **Kilo CLI agents** → `AGENTS.md` sections `[CODER]`, `[FIXER]`, `[REVIEWER]`, `[ALL AGENTS]`
- **Windsurf Cascade** → `.windsurf/rules/*.md` (auto-loaded by IDE)

This document exists for:
1. **Traycer planning** — full context for infrastructure decisions
2. **Human reference** — onboarding, debugging, understanding conventions
3. **Shift-left documentation** — knowing what gates will check

**Knowledge Categories:**
1. **Automated Enforcement** — What `final_gate.py` will check
2. **Production Patterns** — How to write resilient code
3. **Code Conventions** — Language-specific patterns
4. **Infrastructure Awareness** — Available services and constraints
5. **Project Structure** — Where files go, naming conventions

---

# 1. AUTOMATED ENFORCEMENT (final_gate.py)

All code passes through `final_gate.py` before commit. Know these checks upfront.

---

## Phase 1: AUTO-FIX (Applied Automatically)

| Check | Tool | What It Does |
|-------|------|--------------|
| Trailing whitespace | Built-in | Removes trailing spaces from all lines |
| EOF newlines | Built-in | Ensures files end with single newline |
| Python formatting | `ruff format` | Applies Black-compatible formatting |
| Python import sort | `ruff --select I --fix` | Sorts imports (isort-compatible) |

**Agent implication:** Don't worry about formatting — focus on logic. But DO follow import conventions (stdlib → third-party → local).

---

## Phase 2: STATIC ANALYSIS (Must Pass)

### Python Quality

| Check | Tool | Severity | What It Catches |
|-------|------|----------|-----------------|
| Lint | `ruff check` | ERROR | Style violations, unused imports, complexity |
| Type checking | `mypy --strict` | ERROR | Type errors, missing annotations |
| Security | `bandit -r` | ERROR | SQL injection, hardcoded passwords, exec() |
| SAST | `semgrep` | ERROR | Security patterns, common vulnerabilities |
| Dead code | `vulture` | ERROR | Unused functions, variables, classes |

### Other Languages

| Check | Tool | Severity | What It Catches |
|-------|------|----------|-----------------|
| SQL lint | `sqlfluff lint` | ERROR | SQL syntax, style issues |
| YAML syntax | `yaml.safe_load` | ERROR | Invalid YAML structure |
| JSON syntax | `json.loads` | ERROR | Invalid JSON structure |

---

## Phase 3: CONSISTENCY CHECKS (Custom Enforcement Scripts)

### Environment Variables (`check_env_vars.py`)

**Severity:** ERROR

**Forbidden Patterns:**
```python
# WRONG - breaks in Docker/VPS
DB_HOST = "localhost"
API_URL = "http://127.0.0.1:8000"
host = "localhost:5432"

# CORRECT - works everywhere
DB_HOST = os.getenv("DB_HOST", "localhost")
API_URL = os.getenv("API_URL", "http://localhost:8000")
```

**Allowed Contexts:**
- Default values in `os.getenv()` calls
- Comments
- `.env.example` files

---

### Secrets Detection (`check_secrets.py`)

**Severity:** ERROR

**Detected Patterns:**
| Pattern | Description |
|---------|-------------|
| `AKIA[0-9A-Z]{16}` | AWS Access Key ID |
| `sk-[a-zA-Z0-9]{32,}` | OpenAI API Key |
| `sk-ant-[a-zA-Z0-9-]{32,}` | Anthropic API Key |
| `ghp_[a-zA-Z0-9]{36}` | GitHub PAT |
| `sk_live_*`, `rk_live_*` | Stripe Keys |
| `postgresql://user:pass@` | DB URL with password |
| `-----BEGIN PRIVATE KEY-----` | Private keys |
| `password = "..."` | Hardcoded credentials |

**Fix:** Use environment variables. Store in `.env`, document in `.env.example`.

---

### Environment Example Completeness (`check_env_example.py`)

**Severity:** WARN

**Trigger:** New `os.getenv()` or `os.environ[]` calls in staged Python files.

**Requirement:** Every new environment variable must be documented in `.env.example`.

```bash
# .env.example
DB_HOST=localhost
DB_PORT=5432
NEW_API_KEY=your-api-key-here  # Document new vars
```

---

### Docker Conventions (`check_docker.py`)

**Severity:** ERROR for Alpine, WARN for others

| Check | Requirement |
|-------|-------------|
| Base images | `python:3.12-slim-bookworm` or `node:22-bookworm-slim` — **never Alpine** |
| Health check | Must include `HEALTHCHECK` instruction |
| Port consistency | `EXPOSE` port must match `compose.yaml` port |

**Why no Alpine?** ARM64 compatibility issues on VPS deployment.

---

### Port Registration (`check_ports.py`)

**Severity:** WARN

| Technology | Port Range |
|------------|------------|
| Python services | 8000-8099 |
| Frontend apps | 3000-3099 |

**Requirement:** Register all ports in `PORTS.md` to avoid conflicts.

---

### Health Endpoints (`check_health.py`)

**Severity:** WARN

**Requirements:**
1. Health endpoints must test actual dependencies (DB, Redis, etc.)
2. Projects with `/health` endpoint should have `tests/test_health.py`

```python
# WRONG - lies about health
@app.get("/health")
async def health():
    return {"status": "ok"}

# CORRECT - tests dependencies
@app.get("/health")
async def health():
    await db.execute("SELECT 1")
    return {"status": "ok", "db": "connected"}
```

---

### Changelog Updates (`check_changelog.py`)

**Severity:** ERROR

**Triggers (requires CHANGELOG.md update):**
- Changes in `src/`, `scripts/`, `templates/`, `.windsurf/`, `.github/`
- New files created
- Changes exceeding 10 lines

**Skipped:**
- Test files (`test_*.py`, `*_test.py`)
- Documentation-only changes
- Config files (`.json`, `.yaml`, `.toml`)
- Small changes (<10 lines)

**Quality Check:** Entry must not be empty or placeholder like "Updated code".

---

### Database Schema Sync (`check_schema_sync.py`)

**Severity:** ERROR

**Trigger:** Changes to model files (`src/**/models.py`, `src/**/entities.py`)

**Requirement:** When DB models change, you must EITHER:
1. Update `db/schema.sql` with the new schema, OR
2. Add a new migration file in `migrations/`

**Detected Changes:**
- `Column`, `relationship`, `ForeignKey` definitions
- Table definitions
- Index definitions

---

### Project Structure (`check_structure.py`)

**Severity:** ERROR for violations, WARN for legacy

**Root-level .md files allowed:**
- `README.md`, `INDEX.md`, `CHANGELOG.md`
- `AGENTS.md`, `PORTS.md`, `CONTRIBUTING.md`, `LICENSE.md`
- `CLAUDE.md`, `CURSORRULES.md`, `CODEOWNERS.md`

**Forbidden locations for .md files:**
- `src/` — code only
- `scripts/` — code only
- `tests/` — code only
- `.droid/` — system files only

**Required docs/ subdirectories:**
- `docs/guides/` — how-to guides
- `docs/reference/` — technical reference
- `docs/operations/` — runbooks, deployment
- `docs/development/` — dev setup, contributing
- `docs/archive/` — deprecated docs

---

## Quick Reference: What AI Coder Must Do

### Always
- [ ] Use `os.getenv('VAR', 'default')` for all config
- [ ] Add new env vars to `.env.example`
- [ ] Update `CHANGELOG.md` for code changes
- [ ] Update `db/schema.sql` for model changes
- [ ] Use approved base images in Dockerfiles
- [ ] Test dependencies in health endpoints

### Never
- [ ] Hardcode `localhost` or `127.0.0.1`
- [ ] Hardcode API keys, passwords, tokens
- [ ] Use Alpine base images
- [ ] Put .md files in `src/`, `scripts/`, `tests/`
- [ ] Create fake health endpoints that don't test deps
- [ ] Skip CHANGELOG for significant changes

---

## Running Enforcement Locally

```bash
# Full gate check
python /opt/fabrik/scripts/final_gate.py

# Individual enforcement scripts
python -m scripts.enforcement.check_env_vars <file>
python -m scripts.enforcement.check_secrets <file>
python -m scripts.enforcement.check_docker <file>
python -m scripts.enforcement.validate_conventions <file>
```

---

# 2. PRODUCTION PATTERNS (Python)

**Source:** `templates/scaffold/PYTHON_PRODUCTION_STANDARDS.md`

Every production script must handle:
- Network failures with automatic retry
- Disk space exhaustion
- Permission errors
- Rate limiting
- Concurrent access
- Data corruption
- System crashes

## 2.1 Standard Config Block

```python
# ========== FEATURE FLAGS (KILL SWITCHES) ==========
ENABLE_NETWORK_MONITOR = True      # Can disable if breaks
ENABLE_RECOVERY = True              # Can disable if breaks
ENABLE_ATOMIC_WRITES = True         # Can disable if breaks
DRY_RUN_MODE = False                # Test mode - no writes

# ========== PATHS ==========
BASE_DIR = Path(os.environ.get('APP_BASE_DIR', '/app'))
DB_FILE = BASE_DIR / "db" / "app.db"
LOG_FILE = BASE_DIR / "logs" / "app.log"
TEMP_DIR = BASE_DIR / ".tmp"  # Project-local, NOT /tmp

# ========== WORKERS & CONCURRENCY ==========
MAX_WORKERS = int(os.getenv('MAX_WORKERS', '4'))
MAX_BATCH_SIZE = 100
MAX_CONCURRENT_TASKS = 10

# ========== RETRY LOGIC ==========
MAX_RETRIES = 3
RETRY_DELAYS = [300, 900, 1800]    # 5min, 15min, 30min
MAX_CONSECUTIVE_FAILURES = 5

# ========== SAFETY LIMITS ==========
MIN_DISK_SPACE_GB = 1.0
TASK_TIMEOUT_SECONDS = 300
```

## 2.2 Database Patterns

```python
from contextlib import contextmanager

@contextmanager
def get_db():
    """Context manager for database connections"""
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

# Versioned migrations
def init_database():
    with get_db() as conn:
        current = get_schema_version(conn)
        if current < 1: _migrate_to_v1(conn)
        if current < 2: _migrate_to_v2(conn)
```

## 2.3 Atomic File Operations

```python
def atomic_write(content: str, target_path: Path) -> tuple[bool, str | None]:
    """Write via temp file, then atomic rename"""
    temp_file = target_path.parent / f".tmp_{uuid.uuid4().hex[:8]}_{target_path.name}"

    if not check_disk_space(target_path.parent):
        return False, "Insufficient disk space"

    temp_file.write_text(content, encoding='utf-8')

    if temp_file.stat().st_size < 50:
        temp_file.unlink()
        return False, "Output too small (likely corrupted)"

    temp_file.replace(target_path)  # Atomic on POSIX
    return True, None
```

## 2.4 Error Categorization

```python
def categorize_error(exception) -> str:
    """Categorize for retry strategy"""
    error_str = str(exception).lower()

    if any(k in error_str for k in ['connection', 'timeout', 'network']):
        return 'network'       # Retry with backoff
    if any(k in error_str for k in ['rate limit', '429', 'quota']):
        return 'rate_limit'    # Wait longer
    if any(k in error_str for k in ['blocked', '403']):
        return 'blocked'       # Wait much longer
    if any(k in error_str for k in ['permission', 'disk full']):
        return 'critical'      # Stop immediately
    if any(k in error_str for k in ['not found', '404']):
        return 'permanent'     # Skip, don't retry

    return 'unknown'           # Retry with caution
```

## 2.5 Network Monitoring

```python
import threading

network_online = threading.Event()
network_online.set()

def wait_for_network(timeout=None) -> bool:
    """Block until network available"""
    return network_online.wait(timeout=timeout)
```

## 2.6 Startup Sequence

```python
def startup_checks() -> bool:
    """Run before any work"""
    init_logging()

    if not check_disk_space(BASE_DIR):
        return False

    init_database()

    if not verify_database_integrity():
        return False

    recover_incomplete_tasks()
    backup_database()

    return True
```

---

# 3. CODE CONVENTIONS

## 3.1 Python (FastAPI)

**Entry Point:**
```python
# src/main.py
from fastapi import FastAPI
app = FastAPI(title="ServiceName")

@app.get("/health")
async def health():
    await db.execute("SELECT 1")  # MUST test dependencies
    return {"status": "ok"}
```

**Router Structure:**
```python
# src/api/items.py
from fastapi import APIRouter, Depends
router = APIRouter(prefix="/items", tags=["items"])

@router.get("/")
async def list_items(db: Session = Depends(get_db)):
    return await db.query(Item).all()
```

**Config Loading (CRITICAL):**
```python
# CORRECT - load at runtime
def get_db_url() -> str:
    host = os.getenv('DB_HOST', 'localhost')
    port = os.getenv('DB_PORT', '5432')
    return f"postgresql://{host}:{port}/db"

# WRONG - class-level (env not set at import time)
class Config:
    DB_URL = f"postgresql://{os.getenv('DB_HOST')}:..."  # Fails!
```

**Typing Standards:**
- Use `list[str]` not `List[str]` (Python 3.9+)
- Use `str | None` not `Optional[str]` (Python 3.10+)
- Type hints on all function signatures
- Pydantic for request/response models

**Temp Directory:**
```python
# CORRECT - project-local
TEMP_DIR = Path(__file__).parent.parent / ".tmp"
TEMP_DIR.mkdir(exist_ok=True)

# WRONG - shared system temp, deleted on restart
import tempfile
temp_dir = tempfile.gettempdir()  # /tmp
```

## 3.2 TypeScript (Next.js)

**Environment Variables:**
```typescript
// Client-side (must prefix with NEXT_PUBLIC_)
const apiUrl = process.env.NEXT_PUBLIC_API_URL;

// Server-side only
const secretKey = process.env.SECRET_KEY;
```

**Component Pattern:**
```tsx
interface Props {
  title: string;
  count?: number;
}

export function Card({ title, count = 0 }: Props) {
  return (
    <div className="p-4 rounded-lg border">
      <h2>{title}</h2>
      <span>{count}</span>
    </div>
  );
}
```

**API Routes:**
```typescript
// app/api/items/route.ts
import { NextRequest, NextResponse } from 'next/server';

export async function GET(request: NextRequest) {
  const items = await fetchItems();
  return NextResponse.json(items);
}
```

**Styling:** Tailwind CSS + shadcn/ui + Lucide icons

## 3.3 Docker

**Base Images (MANDATORY):**
| Use Case | Image |
|----------|-------|
| Python | `python:3.12-slim-bookworm` |
| Node.js | `node:22-bookworm-slim` |
| General | `debian:bookworm-slim` |

**Never use Alpine** — ARM64 compatibility issues.

**Template:**
```dockerfile
FROM python:3.12-slim-bookworm AS builder
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

FROM python:3.12-slim-bookworm
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 curl && rm -rf /var/lib/apt/lists/*
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH
COPY . .

# HEALTHCHECK is REQUIRED
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8000}/health || exit 1

EXPOSE ${PORT:-8000}
CMD ["sh", "-c", "uvicorn src.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
```

---

# 4. INFRASTRUCTURE AWARENESS

## 4.1 Available Services (VPS)

| Service | URL | Purpose |
|---------|-----|--------|
| PostgreSQL | (internal) | Shared database |
| Redis | (internal) | Shared cache |
| Browserless | browser.vps1.ocoron.com | Headless Chrome |
| Gotenberg | pdf.vps1.ocoron.com | PDF generation |
| MinIO | s3.vps1.ocoron.com | Object storage |
| MeiliSearch | search.vps1.ocoron.com | Full-text search |
| Apprise | notify.vps1.ocoron.com | Notifications |

**Check `docs/reference/prebuilt-app-containers.md` before building custom solutions.**

## 4.2 Port Ranges

| Technology | Range |
|------------|-------|
| Python services | 8000-8099 |
| Frontend apps | 3000-3099 |

**Register new ports in `PORTS.md`.**

## 4.3 Microservice URLs

| Environment | Pattern |
|-------------|--------|
| WSL (dev) | `http://localhost:PORT` |
| VPS Internal | `http://service-name:PORT` |
| VPS External | `https://service.vps1.ocoron.com` |

## 4.4 Deployment

- **Target:** ARM64 (aarch64) Ubuntu VPS
- **Orchestration:** Coolify (Docker Compose)
- **Network:** coolify network (external)
- **SSL:** Traefik + Let's Encrypt

---

# 5. PROJECT STRUCTURE

## 5.1 Standard Layout

```
/opt/<project>/
├── src/                    # Application code
│   ├── main.py             # Entry point
│   ├── api/                # Route handlers
│   ├── models/             # Pydantic/SQLAlchemy models
│   └── services/           # Business logic
├── tests/                  # Test files
│   └── test_health.py      # Required if /health exists
├── scripts/                # Utility scripts
│   ├── final_gate.py       # Copied from fabrik
│   └── enforcement/        # Enforcement scripts
├── db/
│   └── schema.sql          # Database schema (source of truth)
├── docs/
│   ├── guides/             # How-to guides
│   ├── reference/          # Technical reference
│   ├── operations/         # Runbooks
│   └── development/        # Dev setup
├── .tmp/                   # Project-local temp (gitignored)
├── .env                    # Local env (gitignored)
├── .env.example            # Env documentation (committed)
├── CHANGELOG.md            # Change history
├── README.md               # Project overview
├── AGENTS.md               # AI agent instructions
├── PORTS.md                # Port allocations
├── Dockerfile              # Container build
├── compose.yaml            # Service definition
└── pyproject.toml          # Python config
```

## 5.2 File Placement Rules

**Root .md files allowed:**
- README.md, CHANGELOG.md, AGENTS.md, PORTS.md
- INDEX.md, CONTRIBUTING.md, LICENSE.md

**Forbidden .md locations:**
- `src/` — code only
- `scripts/` — code only
- `tests/` — code only

---

# 6. QUICK REFERENCE CHECKLIST

## Before Writing Code
- [ ] Read task requirements completely
- [ ] Check existing code patterns in project
- [ ] Check if Fabrik microservice already exists
- [ ] Check prebuilt containers before custom code

## While Writing Code
- [ ] Use `os.getenv()` for ALL config
- [ ] Use project-local `.tmp/` not system `/tmp`
- [ ] Test dependencies in health endpoints
- [ ] Use context managers for DB/file operations
- [ ] Categorize errors for retry strategy
- [ ] Add type hints to all functions

## Before Self-Review
- [ ] New env vars added to `.env.example`
- [ ] DB changes added to `db/schema.sql`
- [ ] CHANGELOG.md updated for code changes
- [ ] Port registered in PORTS.md if new
- [ ] Dockerfile uses bookworm-slim base
- [ ] HEALTHCHECK instruction present

## Never Do
- [ ] Hardcode localhost/127.0.0.1
- [ ] Hardcode API keys/passwords
- [ ] Use Alpine base images
- [ ] Use class-level config loading
- [ ] Use system /tmp directory
- [ ] Create fake health endpoints
- [ ] Skip CHANGELOG for significant changes

---

# 7. TESTING PATTERNS

## 7.1 Required Tests

| Endpoint/Feature | Required Test File |
|------------------|-------------------|
| `/health` endpoint | `tests/test_health.py` |
| API routes | `tests/test_api.py` |
| Business logic | `tests/test_services.py` |
| Database operations | `tests/test_db.py` |

## 7.2 Test Structure

```python
# tests/conftest.py
import pytest
from fastapi.testclient import TestClient
from src.main import app

@pytest.fixture
def client():
    return TestClient(app)

@pytest.fixture
def db_session():
    """Provide test database session"""
    # Setup
    session = create_test_session()
    yield session
    # Teardown
    session.rollback()
    session.close()
```

```python
# tests/test_health.py
def test_health_returns_ok(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

def test_health_checks_database(client, mocker):
    mocker.patch("src.db.execute", side_effect=Exception("DB down"))
    response = client.get("/health")
    assert response.status_code == 503
```

## 7.3 Running Tests

```bash
pytest tests/                    # Run all
pytest -x --tb=short            # Stop on first failure
pytest -k "test_health"         # Run specific
pytest --cov=src --cov-report=term-missing  # Coverage
```

---

# 8. LOGGING PATTERNS

## 8.1 Standard Setup

```python
import logging
from logging.handlers import RotatingFileHandler

def setup_logging(name: str = "app") -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    # Console handler
    console = logging.StreamHandler()
    console.setFormatter(logging.Formatter(
        '[%(asctime)s] %(levelname)s: %(message)s'
    ))
    logger.addHandler(console)

    # File handler with rotation
    file_handler = RotatingFileHandler(
        "logs/app.log",
        maxBytes=10*1024*1024,  # 10MB
        backupCount=3
    )
    file_handler.setFormatter(logging.Formatter(
        '[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s'
    ))
    logger.addHandler(file_handler)

    return logger

logger = setup_logging()
```

## 8.2 What to Log

| Level | Use For |
|-------|---------|
| DEBUG | Detailed diagnostic info (disabled in prod) |
| INFO | Normal operations, milestones |
| WARNING | Unexpected but handled situations |
| ERROR | Errors that need attention |
| CRITICAL | System failures requiring immediate action |

```python
# Good logging
logger.info(f"Processing task {task_id}")
logger.warning(f"Retry {retry_count}/{MAX_RETRIES} for {task_id}")
logger.error(f"Failed to process {task_id}: {error}", exc_info=True)

# Bad logging - don't log sensitive data
logger.info(f"User {user_id} logged in with password {password}")  # NEVER
logger.info(f"API key: {api_key}")  # NEVER
```

---

# 9. API PATTERNS

## 9.1 Standard Error Response

```python
from fastapi import HTTPException
from pydantic import BaseModel

class ErrorResponse(BaseModel):
    error: str
    detail: str | None = None
    code: str | None = None

# Usage
raise HTTPException(
    status_code=404,
    detail={"error": "Item not found", "code": "ITEM_NOT_FOUND"}
)

raise HTTPException(
    status_code=400,
    detail={"error": "Validation failed", "detail": "Email is invalid"}
)
```

## 9.2 HTTP Status Codes

| Code | Use For |
|------|---------|
| 200 | Success (GET, PUT) |
| 201 | Created (POST) |
| 204 | No Content (DELETE) |
| 400 | Bad Request (validation error) |
| 401 | Unauthorized (not logged in) |
| 403 | Forbidden (not permitted) |
| 404 | Not Found |
| 409 | Conflict (duplicate) |
| 422 | Unprocessable Entity (Pydantic validation) |
| 429 | Too Many Requests (rate limit) |
| 500 | Internal Server Error |
| 503 | Service Unavailable |

## 9.3 Pagination

```python
from pydantic import BaseModel

class PaginatedResponse(BaseModel):
    items: list
    total: int
    page: int
    page_size: int
    has_more: bool

@router.get("/items")
async def list_items(
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db)
):
    offset = (page - 1) * page_size
    items = await db.query(Item).offset(offset).limit(page_size + 1).all()

    has_more = len(items) > page_size
    if has_more:
        items = items[:-1]

    total = await db.query(Item).count()

    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        has_more=has_more
    )
```

## 9.4 Validation (Pydantic)

```python
from pydantic import BaseModel, Field, EmailStr, validator

class CreateUserRequest(BaseModel):
    email: EmailStr
    name: str = Field(..., min_length=1, max_length=100)
    age: int = Field(..., ge=0, le=150)

    @validator('name')
    def name_must_not_be_empty(cls, v):
        if not v.strip():
            raise ValueError('Name cannot be empty')
        return v.strip()

class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    created_at: datetime

    class Config:
        from_attributes = True  # For SQLAlchemy models
```

---

# 10. BACKGROUND JOBS

## 10.1 PostgreSQL Jobs Table Pattern

```python
# Default pattern - simple and sufficient for most cases

# db/schema.sql
CREATE TABLE IF NOT EXISTS jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_type VARCHAR(100) NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}',
    status VARCHAR(20) DEFAULT 'pending',
    attempts INTEGER DEFAULT 0,
    max_attempts INTEGER DEFAULT 3,
    error_message TEXT,
    scheduled_at TIMESTAMPTZ DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_jobs_pending ON jobs(status, scheduled_at)
    WHERE status = 'pending';
```

```python
# Worker pattern
async def process_jobs():
    while True:
        job = await db.execute("""
            UPDATE jobs
            SET status = 'processing', started_at = NOW()
            WHERE id = (
                SELECT id FROM jobs
                WHERE status = 'pending' AND scheduled_at <= NOW()
                ORDER BY scheduled_at
                FOR UPDATE SKIP LOCKED
                LIMIT 1
            )
            RETURNING *
        """)

        if not job:
            await asyncio.sleep(5)
            continue

        try:
            await execute_job(job)
            await db.execute("""
                UPDATE jobs SET status = 'completed', completed_at = NOW()
                WHERE id = $1
            """, job['id'])
        except Exception as e:
            await db.execute("""
                UPDATE jobs SET
                    status = CASE WHEN attempts >= max_attempts THEN 'failed' ELSE 'pending' END,
                    attempts = attempts + 1,
                    error_message = $2,
                    scheduled_at = NOW() + INTERVAL '5 minutes'
                WHERE id = $1
            """, job['id'], str(e))
```

## 10.2 When to Use What

| Pattern | Use When |
|---------|----------|
| PostgreSQL jobs table | < 100 jobs/minute, simple retry logic |
| Redis Queue (RQ) | 100-1000 jobs/minute, need prioritization |
| Celery | > 1000 jobs/minute, complex workflows |
| APScheduler | Cron-like scheduled tasks |

---

# 11. CACHING (Redis)

```python
import redis
import json
from functools import wraps

redis_client = redis.Redis(
    host=os.getenv('REDIS_HOST', 'localhost'),
    port=int(os.getenv('REDIS_PORT', '6379')),
    decode_responses=True
)

def cache(ttl_seconds: int = 300):
    """Simple cache decorator"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            cache_key = f"{func.__name__}:{hash(str(args) + str(kwargs))}"

            cached = redis_client.get(cache_key)
            if cached:
                return json.loads(cached)

            result = await func(*args, **kwargs)
            redis_client.setex(cache_key, ttl_seconds, json.dumps(result))
            return result
        return wrapper
    return decorator

# Usage
@cache(ttl_seconds=60)
async def get_user(user_id: str):
    return await db.query(User).filter(User.id == user_id).first()

# Invalidation
def invalidate_user_cache(user_id: str):
    pattern = f"get_user:*{user_id}*"
    for key in redis_client.scan_iter(pattern):
        redis_client.delete(key)
```

---

# 12. WATCHDOG SCRIPTS

**Every service MUST have a watchdog script** (from 30-ops.md).

```bash
#!/bin/bash
# scripts/watchdog.sh

SERVICE_NAME="${SERVICE_NAME:-myservice}"
HEALTH_URL="${HEALTH_URL:-http://localhost:8000/health}"
MAX_FAILURES=${MAX_FAILURES:-3}
CHECK_INTERVAL=${CHECK_INTERVAL:-30}

failures=0

while true; do
    if curl -sf "$HEALTH_URL" > /dev/null 2>&1; then
        failures=0
    else
        ((failures++))
        echo "Health check failed ($failures/$MAX_FAILURES)"

        if [ $failures -ge $MAX_FAILURES ]; then
            echo "Max failures reached, restarting..."
            docker compose restart "$SERVICE_NAME" || systemctl restart "$SERVICE_NAME"
            failures=0
        fi
    fi
    sleep "$CHECK_INTERVAL"
done
```

---

# 13. DECISION TREES

## 13.1 Database Choice

```
Need managed auth/realtime/pgvector?
├── Yes → Supabase
└── No → PostgreSQL on VPS (default)
```

## 13.2 Background Jobs

```
Jobs per minute?
├── < 100 → PostgreSQL jobs table
├── 100-1000 → Redis Queue (RQ)
└── > 1000 → Celery + RabbitMQ
```

## 13.3 Search

```
Simple full-text search?
├── Yes → PostgreSQL FTS
└── No →
    ├── Vector search needed? → pgvector
    └── Complex search? → MeiliSearch
```

## 13.4 File Storage

```
Temporary files?
├── Yes → project/.tmp/ (NOT /tmp)
└── No →
    ├── Hot storage → MinIO (s3.vps1.ocoron.com)
    └── Cold storage → Backblaze B2
```

---

# 14. COMMON ANTI-PATTERNS

## 14.1 Code Anti-Patterns

| Anti-Pattern | Problem | Solution |
|--------------|---------|----------|
| Sync in async | Blocks event loop | Use `asyncio.to_thread()` |
| N+1 queries | Performance | Use `selectinload()` / `joinedload()` |
| No timeouts | Hanging requests | Always set `timeout=` |
| Catching bare Exception | Hides bugs | Catch specific exceptions |
| Mutable default args | Shared state | Use `None` then assign |

## 14.2 Architecture Anti-Patterns

| Anti-Pattern | Problem | Solution |
|--------------|---------|----------|
| Building what exists | Wasted effort | Check prebuilt containers first |
| Over-engineering | Complexity | Start simple, evolve if needed |
| No health check | Silent failures | Always implement `/health` |
| Sync job processing | Request timeout | Use background jobs |
| Direct DB in handlers | Hard to test | Use service layer |

---

# 15. FABRIK-SPECIFIC KNOWLEDGE

## 15.1 Things Only Fabrik Knows

These are NOT in your training data — always follow these:

| Topic | Fabrik Rule |
|-------|------------|
| Base images | `python:3.12-slim-bookworm` NEVER Alpine |
| Temp files | Project `.tmp/` NEVER system `/tmp` |
| Config loading | Runtime functions NEVER class-level |
| Port ranges | Python 8000-8099, Frontend 3000-3099 |
| DB changes | Must update `db/schema.sql` |
| Deployment | ARM64 VPS via Coolify |
| Network | Docker services use `coolify` network |

## 15.2 Available Microservices (Don't Rebuild)

| Need | Use | Don't Build |
|------|-----|-------------|
| PDF generation | Gotenberg (pdf.vps1.ocoron.com) | Custom PDF code |
| Headless Chrome | Browserless (browser.vps1.ocoron.com) | Puppeteer setup |
| Object storage | MinIO (s3.vps1.ocoron.com) | File system |
| Full-text search | MeiliSearch (search.vps1.ocoron.com) | Custom search |
| Notifications | Apprise (notify.vps1.ocoron.com) | Direct API calls |
| Translation | Translator service (port 8000) | DeepL direct |
| Image generation | Image Broker (port 8010) | FLUX direct |
