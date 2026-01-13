# Cascade Rules Export - WORKSPACE RULES (Part 1 of 4)

**Exported:** 2026-01-13
**Type:** WORKSPACE RULES (apply to /opt/fabrik workspace only)
**Location:** `.windsurf/rules/`

---

## How to Import

1. On new machine, create `/opt/fabrik/.windsurf/rules/` directory
2. Copy each rule file to the same location
3. OR: In Windsurf settings, add these as workspace rules

---

# FILE: .windsurf/rules/00-critical.md

```markdown
---
activation: always_on
description: Critical Fabrik rules - ALWAYS enforced
trigger: always_on
---

# Critical Rules (ALWAYS ACTIVE)

## ⚠️ MANDATORY WORKFLOW

**Before ANY code change, I MUST:**
1. Read `AGENTS.md` for conventions
2. After editing, run: `python3 -m scripts.enforcement.validate_conventions --strict <files>`
3. After editing, trigger review: `droid exec "Review <files>" # Uses default model from config/models.yaml`
4. Update documentation if code changed

**If I skip these steps, the user should call me out.**
---
## Before Creating New Scripts (MANDATORY)

Before writing ANY new script, I MUST:
1. `grep_search` for similar functionality in scripts/
2. Check if droid_core.py, droid-review.sh, or existing wrappers handle it
3. If existing code can be extended → extend it, don't create new

**Violation:** Creating duplicate functionality.
---

## Environment Variables (CRITICAL)

**NEVER hardcode these values:**
- `localhost`, `127.0.0.1`
- Database connection strings
- API keys, tokens, passwords

**ALWAYS use:**
```python
# CORRECT
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = int(os.getenv('DB_PORT', '5432'))

# WRONG - breaks in Docker/VPS
DB_HOST = 'localhost'
```

---

## Target Environments

Code MUST work in ALL environments without modification:

| Environment | Database | Config Source |
|-------------|----------|---------------|
| WSL (dev) | PostgreSQL localhost | `.env` file |
| VPS Docker | postgres-main container | compose.yaml |
| Supabase | Supabase PostgreSQL | env vars |

---

## Health Checks (MUST Test Dependencies)

```python
# CORRECT - tests actual DB
@app.get("/health")
async def health():
    await db.execute("SELECT 1")
    return {"status": "ok", "db": "connected"}

# WRONG - hides failures
@app.get("/health")
async def health():
    return {"status": "ok"}  # Lies!
```

---

## Security Gates

### Credentials Storage (TWO PLACES)
1. Project `.env` - local use
2. `/opt/fabrik/.env` - master backup

### Password Policy (CSPRNG)
- Length: 32 characters
- Characters: `[a-zA-Z0-9]`
- Generator: `secrets.choice()`
- **FORBIDDEN:** `postgres`, `admin`, `password123`

---

## Forbidden Actions

| Action | Use Instead |
|--------|-------------|
| `/tmp/` directory | Project `.tmp/` |
| Hardcoded localhost | `os.getenv()` |
| Alpine base images | `python:3.12-slim-bookworm` |
| Class-level config | Function-level loading |
---

## Cascade Behavior Rules (STRICT)

| Rule | Description |
|------|-------------|
| **Check before create** | ALWAYS verify file exists (`ls`, `find`, `read_file`) before `write_to_file` |
| **Present before execute** | Present solution/plan first, wait for user approval, then execute |
| **No unsolicited advice** | Never suggest breaks, lifestyle tips, or non-task commentary |

**Violations:**
- Attempting to create a file that already exists = STOP, acknowledge error
- Executing commands without presenting plan first = violation
- Suggesting breaks or personal advice = violation

---

## Port Management

| Range | Purpose |
|-------|---------|
| 8000-8099 | Python services |
| 3000-3099 | Frontend apps |

**Before using a port:** Check PORTS.md, register new ports.

---

## Self-Check Before Responding

Before I finish ANY coding task, I MUST verify:
- [ ] No hardcoded localhost/secrets
- [ ] Documentation updated if code changed
- [ ] Enforcement check passed
- [ ] Review triggered or manually done

---

## Fast Context (Windsurf RAG)

**Force quick codebase search:** `Cmd+Enter` (Mac) / `Ctrl+Enter` (Win/Linux)

Uses SWE-grep models for parallel code retrieval (up to 8 tool calls/turn).

**Optimize indexing with `.codeiumignore`:**
- Project-level: `/opt/fabrik/.codeiumignore`
- Global: `~/.codeium/.codeiumignore`

Excluded from index: `.venv/`, `node_modules/`, `.droid/` queues, build artifacts.
```

---

# FILE: .windsurf/rules/10-python.md

```markdown
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
from fastapi import FastAPI
app = FastAPI(title="ServiceName")

@app.get("/health")
async def health():
    # MUST test actual dependencies
    await db.execute("SELECT 1")
    return {"status": "ok"}
```

### Router Structure
```python
# src/api/items.py
from fastapi import APIRouter, Depends
router = APIRouter(prefix="/items", tags=["items"])

@router.get("/")
async def list_items(db: Session = Depends(get_db)):
    return await db.query(Item).all()
```

---

## Config Loading (CRITICAL)

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
```

---

# FILE: .windsurf/rules/20-typescript.md

```markdown
---
activation: glob
globs: ["**/*.ts", "**/*.tsx"]
description: Next.js patterns, React components, API routes
trigger: glob
---

# TypeScript Rules

**Activation:** Glob `**/*.ts`, `**/*.tsx`
**Purpose:** Next.js patterns, React components, API routes

---

## SaaS Projects (MANDATORY)

**Always start from the SaaS skeleton:**
```bash
cp -r /opt/fabrik/templates/saas-skeleton /opt/<project-name>
cd /opt/<project-name>
npm install
cp .env.example .env
npm run dev
```

**Template includes:**
- Next.js 14 + TypeScript + Tailwind CSS
- Marketing pages (landing, pricing, FAQ)
- App pages (dashboard, settings)
- SSE streaming + ChatUI

---

## Environment Variables

```typescript
// CORRECT - runtime access
const apiUrl = process.env.NEXT_PUBLIC_API_URL;
const dbHost = process.env.DB_HOST || 'localhost';

// Server-side only (no NEXT_PUBLIC_ prefix)
const secretKey = process.env.SECRET_KEY;
```

---

## Component Patterns

```tsx
// Functional components with TypeScript
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

---

## API Routes (App Router)

```typescript
// app/api/items/route.ts
import { NextRequest, NextResponse } from 'next/server';

export async function GET(request: NextRequest) {
  const items = await fetchItems();
  return NextResponse.json(items);
}

export async function POST(request: NextRequest) {
  const body = await request.json();
  const item = await createItem(body);
  return NextResponse.json(item, { status: 201 });
}
```

---

## Styling

- Use Tailwind CSS for all styling
- Use shadcn/ui components
- Use Lucide icons

```tsx
import { Button } from "@/components/ui/button";
import { Plus } from "lucide-react";

<Button variant="outline" size="sm">
  <Plus className="w-4 h-4 mr-2" />
  Add Item
</Button>
```

---

## Port Range

Frontend apps: **3000-3099**

```bash
npm run dev -- --port 3000
```

---

## Quality

```bash
npm run lint          # ESLint
npm run type-check    # TypeScript
npm run build         # Production build
```

## Visual Design Workflow (SaaS/Web/Mobile)

For UI-heavy projects, use this iterative design-to-code workflow:

### Step 1: Provide Design Reference
- Screenshot of mockup/Figma design
- Or detailed description of desired UI

### Step 2: AI Generates Code
```bash
# Describe the component
"Create a pricing card component matching this design: [paste screenshot or describe]"
---
```
