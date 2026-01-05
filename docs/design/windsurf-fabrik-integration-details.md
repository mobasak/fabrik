# Windsurf + Fabrik Integration - Implementation Details

**Companion to:** windsurf-fabrik-integration.md

---

## Rule File Templates

### 01-critical.md (Always On)

```markdown
---
trigger: always
---

# Critical Fabrik Conventions

## Environment Variables - NEVER Hardcode

```python
# ✅ CORRECT
DB_HOST = os.getenv('DB_HOST', 'localhost')

# ❌ WRONG
DB_HOST = 'localhost'
```

## Config Loading - Runtime Only

```python
# ✅ CORRECT
def get_db_url():
    return f"postgresql://{os.getenv('DB_USER')}:..."

# ❌ WRONG - class level
class Config:
    DB_URL = f"postgresql://{os.getenv('DB_USER')}:..."
```

## Health Checks - Test Dependencies

```python
# ✅ CORRECT
@app.get("/health")
async def health():
    await db.execute("SELECT 1")
    return {"status": "ok", "db": "connected"}

# ❌ WRONG
@app.get("/health")
async def health():
    return {"status": "ok"}
```

## Passwords - CSPRNG 32 chars

```python
import secrets, string
password = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(32))
```

## Docker - ARM64 Compatible

```dockerfile
FROM python:3.12-slim-bookworm  # ✅
FROM python:3.12-alpine         # ❌
```
```

---

### 02-python.md (Glob: **/*.py)

```markdown
---
trigger: glob
globs: ["**/*.py"]
---

# Python Conventions

## FastAPI Router Pattern

```python
router = APIRouter(prefix="/api/v1", tags=["resource"])

@router.post("/", response_model=Response)
async def create(data: Request, db = Depends(get_db)):
    ...
```

## Dependency Injection

```python
async def get_db():
    async with async_session() as session:
        yield session
```

## Structured Logging

```python
import structlog
logger = structlog.get_logger()
logger.info("event", key=value)
```
```

---

## Workflow Templates

### /new-project

```markdown
---
name: new-project
description: Scaffold new Fabrik project
---

## Steps

1. **Determine type:** API / SaaS / Worker / Library
2. **Scaffold:**
   - API: `python -c "from fabrik.scaffold import create_project; create_project('NAME', 'DESC')"`
   - SaaS: `cp -r /opt/fabrik/templates/saas-skeleton /opt/NAME`
3. **Configure:** Copy .env.example, generate passwords
4. **Verify:** Run tests, check health endpoint
5. **Git init:** Initial commit
```

### /deploy-vps

```markdown
---
name: deploy-vps
description: Deploy to VPS via Coolify
---

## Pre-flight Checklist
- [ ] compose.yaml valid
- [ ] Dockerfile builds
- [ ] Health endpoint works
- [ ] No hardcoded localhost
- [ ] ARM64 compatible images

## Steps
1. `docker compose build && docker compose up -d`
2. `curl http://localhost:8000/health`
3. `git push origin main`
4. Deploy in Coolify dashboard
5. Verify: `curl https://service.vps1.ocoron.com/health`
```

---

## Hook Scripts

### validate_conventions.py

```python
#!/usr/bin/env python3
import sys, json, re
from pathlib import Path

VIOLATIONS = [
    ("Hardcoded localhost", r"['\"](?:localhost|127\.0\.0\.1)['\"]", "error"),
    ("Class-level env", r"class \w+:.*os\.getenv", "error"),
    ("Weak password", r"password\s*=\s*['\"][^'\"]{1,16}['\"]", "warning"),
]

def main():
    data = json.loads(sys.stdin.read())
    if data.get("agent_action_name") != "pre_write_code":
        return

    file_path = data.get("tool_info", {}).get("file_path", "")
    edits = data.get("tool_info", {}).get("edits", [])

    errors, warnings = [], []
    for edit in edits:
        content = edit.get("new_string", "")
        for name, pattern, severity in VIOLATIONS:
            if re.search(pattern, content):
                (errors if severity == "error" else warnings).append(name)

    for w in warnings:
        print(f"⚠️ {w}", file=sys.stdout)
    if errors:
        for e in errors:
            print(f"❌ {e}", file=sys.stderr)
        sys.exit(2)  # Block action

if __name__ == "__main__":
    main()
```

---

## MCP Configuration

```json
{
  "mcpServers": {
    "github": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"],
      "env": {"GITHUB_PERSONAL_ACCESS_TOKEN": "${env:GITHUB_TOKEN}"}
    }
  }
}
```

---

## Droid + Cascade Task Sharing

| Task Type | Best Tool | Why |
|-----------|-----------|-----|
| Interactive coding | Cascade | Real-time awareness, visual |
| Batch refactoring | droid exec | Autonomy levels, hooks |
| Code review | Both | Dual-model for thoroughness |
| Deployment | droid exec | CI/CD integration |
| Documentation | Cascade | Context-aware |
| Scaffolding | Either | Both have templates |

### Example: Parallel Work

```
User in Cascade: "Add user authentication"
  └── Cascade creates auth module, tests

Meanwhile in terminal:
$ droid exec --auto medium "Update docs for auth feature"
  └── droid updates documentation

Both tools read AGENTS.md → Same conventions enforced
```

---

## Questions for AI Review

1. Is the source-of-truth hierarchy (AGENTS.md → Rules → Hooks) correct?
2. Should hooks block violations or just warn?
3. Are the rule activation modes (always/glob/manual) well-chosen?
4. Is there a simpler architecture that achieves the same goals?
5. How should conflicts between AGENTS.md and Rules be resolved?
6. What's missing from this design?
