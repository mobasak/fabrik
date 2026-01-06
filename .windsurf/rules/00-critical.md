---
activation: always_on
description: Critical Fabrik rules - ALWAYS enforced
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
