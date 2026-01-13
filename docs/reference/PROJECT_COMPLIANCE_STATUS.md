# Fabrik Project Compliance Status

**Generated:** 2026-01-13
**Purpose:** Guide for Cascade agents to make projects 100% Fabrik-compliant

---

## What is Fabrik?

Fabrik is a development framework that ensures all projects follow consistent patterns for:
- **Environment portability** — Code works in WSL, Docker, VPS without changes
- **AI agent readability** — Documentation enables any AI agent to understand and work on the project
- **Deployment readiness** — Projects ship as Docker Compose apps to Coolify on ARM64 VPS
- **Code quality** — Pre-commit hooks, tests, and automated reviews

---

## 100% Compliance Checklist

A project is **100% Fabrik-compliant** when ALL of the following are true:

### Infrastructure Files (REQUIRED)

| File | Purpose | Source |
|------|---------|--------|
| `.windsurfrules` | Symlink to Fabrik rules | `ln -s /opt/fabrik/windsurfrules .windsurfrules` |
| `AGENTS.md` | AI agent instructions | `cp /opt/fabrik/templates/scaffold/AGENTS.md .` |
| `.pre-commit-config.yaml` | Code quality hooks | `cp /opt/fabrik/templates/scaffold/pre-commit-config.yaml .` |
| `scripts/sync_cascade_backup.sh` | Cascade backup reminder | `cp /opt/fabrik/scripts/sync_cascade_backup.sh scripts/` |
| `scripts/sync_extensions.sh` | Extensions sync | `cp /opt/fabrik/scripts/sync_extensions.sh scripts/` |

### Documentation Files (REQUIRED for AI Understanding)

| File | Purpose | Content Requirements |
|------|---------|---------------------|
| `README.md` | Project overview | Must have: Purpose, Quick Start, Architecture, Configuration, Deployment |
| `CHANGELOG.md` | Version history | Track all changes |
| `docs/` | Documentation folder | Must exist |
| `docs/INDEX.md` | Documentation map | List all docs |
| `docs/trajectories/` | Saved Cascade conversations | For valuable sessions |

### Deployment Files (REQUIRED for Services)

| File | Purpose | Requirements |
|------|---------|--------------|
| `Dockerfile` | Container build | Use `python:3.12-slim-bookworm` (NOT Alpine) |
| `compose.yaml` | Docker Compose | Include healthcheck, coolify network |
| `.env.example` | Environment template | All required vars documented |

### Code Quality (REQUIRED)

| Item | Purpose |
|------|---------|
| `tests/` | Test directory with actual tests |
| `requirements.txt` or `pyproject.toml` | Dependencies |
| Health endpoint | Must test actual dependencies, not just return `{"status": "ok"}` |

### Code Standards (REQUIRED - Zero Violations)

| Violation | Fix |
|-----------|-----|
| Hardcoded `localhost` | Use `os.getenv('DB_HOST', 'localhost')` |
| `/tmp/` directory | Use project `.tmp/` directory |
| `tempfile` module | Use project `.tmp/` directory |
| Alpine base images | Use `python:3.12-slim-bookworm` |
| Class-level config | Use function-level config loading |

---

## Current Compliance Status

### Summary Table

| Project | Infrastructure | Documentation | Deployment | Code Quality | Violations |
|---------|----------------|---------------|------------|--------------|------------|
| captcha | 1/5 | 3/5 | 3/3 ✅ | 2/2 ✅ | 78 ❌ |
| dns-manager | 1/5 | 3/5 | 3/3 ✅ | 2/2 ✅ | 80 ❌ |
| emailgateway | 1/5 | 3/5 | 2/3 | 1/2 | 3 ❌ |
| file-api | 1/5 | 1/5 | 2/3 | 0/2 | 1 ❌ |
| file-worker | 1/5 | 0/5 | 2/3 | 1/2 | 2 ❌ |
| image-broker | 1/5 | 3/5 | 3/3 ✅ | 2/2 ✅ | 83 ❌ |
| proposal-creator | 2/5 | 3/5 | 3/3 ✅ | 3/3 ✅ | 180 ❌ |
| proxy | 2/5 | 3/5 | 3/3 ✅ | 2/2 ✅ | 13 ❌ |
| translator | 1/5 | 3/5 | 3/3 ✅ | 2/2 ✅ | 130 ❌ |
| youtube | 2/5 | 3/5 | 1/3 | 2/2 ✅ | 59 ❌ |

**Legend:** ✅ = Complete, ❌ = Has issues

---

## Detailed Status Per Project

### captcha
**Location:** `/opt/captcha`

**Infrastructure (1/5):**
- ✅ `.windsurfrules`
- ❌ `AGENTS.md`
- ❌ `.pre-commit-config.yaml`
- ❌ `scripts/sync_cascade_backup.sh`
- ❌ `scripts/sync_extensions.sh`

**Documentation (3/5):**
- ✅ `README.md`
- ✅ `CHANGELOG.md`
- ✅ `docs/`
- ❌ `docs/INDEX.md`
- ❌ `docs/trajectories/`

**Deployment (3/3):** ✅ Complete
- ✅ `Dockerfile` (bookworm-slim)
- ✅ `compose.yaml`
- ✅ `.env.example`

**Code Quality (2/2):** ✅ Complete
- ✅ `tests/`
- ✅ `requirements.txt`

**Code Violations (78 total):**
- ❌ 38 hardcoded localhost
- ❌ 3 /tmp/ usage
- ❌ 37 tempfile module

---

### dns-manager
**Location:** `/opt/dns-manager`

**Infrastructure (1/5):**
- ✅ `.windsurfrules`
- ❌ `AGENTS.md`
- ❌ `.pre-commit-config.yaml`
- ❌ `scripts/sync_cascade_backup.sh`
- ❌ `scripts/sync_extensions.sh`

**Documentation (3/5):**
- ✅ `README.md`
- ✅ `CHANGELOG.md`
- ✅ `docs/`
- ❌ `docs/INDEX.md`
- ❌ `docs/trajectories/`

**Deployment (3/3):** ✅ Complete
- ✅ `Dockerfile` (bookworm-slim)
- ✅ `compose.yaml`
- ✅ `.env.example`

**Code Quality (2/2):** ✅ Complete
- ✅ `tests/`
- ✅ `requirements.txt`

**Code Violations (80 total):**
- ❌ 38 hardcoded localhost
- ❌ 3 /tmp/ usage
- ❌ 39 tempfile module

---

### emailgateway
**Location:** `/opt/emailgateway`

**Infrastructure (1/5):**
- ✅ `.windsurfrules`
- ❌ `AGENTS.md`
- ❌ `.pre-commit-config.yaml`
- ❌ `scripts/sync_cascade_backup.sh`
- ❌ `scripts/sync_extensions.sh`

**Documentation (3/5):**
- ✅ `README.md`
- ✅ `CHANGELOG.md`
- ✅ `docs/`
- ❌ `docs/INDEX.md`
- ❌ `docs/trajectories/`

**Deployment (2/3):**
- ❌ `Dockerfile` (uses Alpine - MUST change to bookworm-slim)
- ✅ `compose.yaml`
- ✅ `.env.example`

**Code Quality (1/2):**
- ✅ `tests/`
- ❌ `requirements.txt`

**Code Violations (3 total):**
- ❌ 1 /tmp/ usage
- ❌ 2 Alpine in Dockerfile

---

### file-api
**Location:** `/opt/file-api`

**Infrastructure (1/5):**
- ✅ `.windsurfrules`
- ❌ `AGENTS.md`
- ❌ `.pre-commit-config.yaml`
- ❌ `scripts/sync_cascade_backup.sh`
- ❌ `scripts/sync_extensions.sh`

**Documentation (1/5):**
- ✅ `README.md`
- ❌ `CHANGELOG.md`
- ❌ `docs/`
- ❌ `docs/INDEX.md`
- ❌ `docs/trajectories/`

**Deployment (2/3):**
- ❌ `Dockerfile` (uses Alpine - MUST change to bookworm-slim)
- ✅ `compose.yaml`
- ❌ `.env.example`

**Code Quality (0/2):**
- ❌ `tests/`
- ❌ `requirements.txt`

**Code Violations (1 total):**
- ❌ 1 Alpine in Dockerfile

---

### file-worker
**Location:** `/opt/file-worker`

**Infrastructure (1/5):**
- ✅ `.windsurfrules`
- ❌ `AGENTS.md`
- ❌ `.pre-commit-config.yaml`
- ❌ `scripts/sync_cascade_backup.sh`
- ❌ `scripts/sync_extensions.sh`

**Documentation (0/5):**
- ❌ `README.md`
- ❌ `CHANGELOG.md`
- ❌ `docs/`
- ❌ `docs/INDEX.md`
- ❌ `docs/trajectories/`

**Deployment (2/3):**
- ✅ `Dockerfile` (bookworm-slim)
- ✅ `compose.yaml`
- ❌ `.env.example`

**Code Quality (1/2):**
- ❌ `tests/`
- ✅ `requirements.txt`

**Code Violations (2 total):**
- ❌ 2 tempfile module

---

### image-broker
**Location:** `/opt/image-broker`

**Infrastructure (1/5):**
- ✅ `.windsurfrules`
- ❌ `AGENTS.md`
- ❌ `.pre-commit-config.yaml`
- ❌ `scripts/sync_cascade_backup.sh`
- ❌ `scripts/sync_extensions.sh`

**Documentation (3/5):**
- ✅ `README.md`
- ✅ `CHANGELOG.md`
- ✅ `docs/`
- ❌ `docs/INDEX.md`
- ❌ `docs/trajectories/`

**Deployment (3/3):** ✅ Complete
- ✅ `Dockerfile` (bookworm-slim)
- ✅ `compose.yaml`
- ✅ `.env.example`

**Code Quality (2/2):** ✅ Complete
- ✅ `tests/`
- ✅ `requirements.txt`

**Code Violations (83 total):**
- ❌ 34 hardcoded localhost
- ❌ 6 /tmp/ usage
- ❌ 43 tempfile module

---

### proposal-creator
**Location:** `/opt/proposal-creator`

**Infrastructure (2/5):**
- ✅ `.windsurfrules`
- ❌ `AGENTS.md`
- ✅ `.pre-commit-config.yaml`
- ❌ `scripts/sync_cascade_backup.sh`
- ❌ `scripts/sync_extensions.sh`

**Documentation (3/5):**
- ✅ `README.md`
- ✅ `CHANGELOG.md`
- ✅ `docs/`
- ❌ `docs/INDEX.md`
- ❌ `docs/trajectories/`

**Deployment (3/3):** ✅ Complete
- ✅ `Dockerfile` (bookworm-slim)
- ✅ `compose.yaml`
- ✅ `.env.example`

**Code Quality (3/3):** ✅ Complete
- ✅ `tests/`
- ✅ `requirements.txt`
- ✅ `pyproject.toml`

**Code Violations (180 total):**
- ❌ 68 hardcoded localhost
- ❌ 25 /tmp/ usage
- ❌ 87 tempfile module

---

### proxy
**Location:** `/opt/proxy`

**Infrastructure (2/5):**
- ✅ `.windsurfrules`
- ✅ `AGENTS.md`
- ❌ `.pre-commit-config.yaml`
- ❌ `scripts/sync_cascade_backup.sh`
- ❌ `scripts/sync_extensions.sh`

**Documentation (3/5):**
- ✅ `README.md`
- ✅ `CHANGELOG.md`
- ✅ `docs/`
- ❌ `docs/INDEX.md`
- ❌ `docs/trajectories/`

**Deployment (3/3):** ✅ Complete
- ✅ `Dockerfile` (bookworm-slim)
- ✅ `compose.yaml`
- ✅ `.env.example`

**Code Quality (2/2):** ✅ Complete
- ✅ `tests/`
- ✅ `requirements.txt`

**Code Violations (13 total):**
- ❌ 7 hardcoded localhost
- ❌ 5 /tmp/ usage
- ❌ 1 tempfile module

---

### translator
**Location:** `/opt/translator`

**Infrastructure (1/5):**
- ✅ `.windsurfrules`
- ❌ `AGENTS.md`
- ❌ `.pre-commit-config.yaml`
- ❌ `scripts/sync_cascade_backup.sh`
- ❌ `scripts/sync_extensions.sh`

**Documentation (3/5):**
- ✅ `README.md`
- ✅ `CHANGELOG.md`
- ✅ `docs/`
- ❌ `docs/INDEX.md`
- ❌ `docs/trajectories/`

**Deployment (3/3):** ✅ Complete
- ✅ `Dockerfile` (bookworm-slim)
- ✅ `compose.yaml`
- ✅ `.env.example`

**Code Quality (2/2):** ✅ Complete
- ✅ `tests/`
- ✅ `requirements.txt`

**Code Violations (130 total):**
- ❌ 75 hardcoded localhost
- ❌ 5 /tmp/ usage
- ❌ 50 tempfile module

---

### youtube
**Location:** `/opt/youtube`

**Infrastructure (2/5):**
- ✅ `.windsurfrules`
- ✅ `AGENTS.md`
- ❌ `.pre-commit-config.yaml`
- ❌ `scripts/sync_cascade_backup.sh`
- ❌ `scripts/sync_extensions.sh`

**Documentation (3/5):**
- ✅ `README.md`
- ✅ `CHANGELOG.md`
- ✅ `docs/`
- ❌ `docs/INDEX.md`
- ❌ `docs/trajectories/`

**Deployment (1/3):**
- ❌ `Dockerfile`
- ❌ `compose.yaml`
- ✅ `.env.example`

**Code Quality (2/2):** ✅ Complete
- ✅ `tests/`
- ✅ `requirements.txt`

**Code Violations (59 total):**
- ❌ 16 hardcoded localhost
- ❌ 42 /tmp/ usage
- ❌ 1 tempfile module

---

## Instructions for Cascade Agent

When you open a project, execute these steps IN ORDER:

### Step 1: Run Compliance Check
```bash
# Run from project root
echo "=== Infrastructure ==="
[ -e .windsurfrules ] && echo "✅ .windsurfrules" || echo "❌ .windsurfrules"
[ -f AGENTS.md ] && echo "✅ AGENTS.md" || echo "❌ AGENTS.md"
[ -f .pre-commit-config.yaml ] && echo "✅ .pre-commit-config.yaml" || echo "❌ .pre-commit-config.yaml"
[ -f scripts/sync_cascade_backup.sh ] && echo "✅ sync_cascade_backup.sh" || echo "❌ sync_cascade_backup.sh"
[ -f scripts/sync_extensions.sh ] && echo "✅ sync_extensions.sh" || echo "❌ sync_extensions.sh"

echo ""
echo "=== Documentation ==="
[ -f README.md ] && echo "✅ README.md" || echo "❌ README.md"
[ -f CHANGELOG.md ] && echo "✅ CHANGELOG.md" || echo "❌ CHANGELOG.md"
[ -d docs ] && echo "✅ docs/" || echo "❌ docs/"
[ -f docs/INDEX.md ] && echo "✅ docs/INDEX.md" || echo "❌ docs/INDEX.md"
[ -d docs/trajectories ] && echo "✅ docs/trajectories/" || echo "❌ docs/trajectories/"

echo ""
echo "=== Deployment ==="
[ -f Dockerfile ] && echo "✅ Dockerfile" || echo "❌ Dockerfile"
[ -f compose.yaml ] || [ -f docker-compose.yaml ] && echo "✅ compose.yaml" || echo "❌ compose.yaml"
[ -f .env.example ] && echo "✅ .env.example" || echo "❌ .env.example"

echo ""
echo "=== Code Quality ==="
[ -d tests ] && echo "✅ tests/" || echo "❌ tests/"
[ -f requirements.txt ] || [ -f pyproject.toml ] && echo "✅ dependencies" || echo "❌ dependencies"

echo ""
echo "=== Code Violations ==="
echo "Hardcoded localhost: $(grep -r 'localhost' --include='*.py' . 2>/dev/null | grep -v '.git' | grep -v '# ' | grep -v 'os.getenv' | wc -l)"
echo "/tmp/ usage: $(grep -r '/tmp/' --include='*.py' --include='*.sh' . 2>/dev/null | grep -v '.git' | wc -l)"
echo "tempfile module: $(grep -r 'tempfile\.' --include='*.py' . 2>/dev/null | grep -v '.git' | wc -l)"
if [ -f Dockerfile ]; then
  echo "Alpine usage: $(grep -i 'alpine' Dockerfile | wc -l)"
fi
```

### Step 2: Add Missing Infrastructure Files
```bash
# Add .windsurfrules symlink (if missing)
[ -e .windsurfrules ] || ln -s /opt/fabrik/windsurfrules .windsurfrules

# Add AGENTS.md (if missing)
[ -f AGENTS.md ] || cp /opt/fabrik/templates/scaffold/AGENTS.md .

# Add pre-commit config (if missing)
[ -f .pre-commit-config.yaml ] || cp /opt/fabrik/templates/scaffold/pre-commit-config.yaml .pre-commit-config.yaml

# Add scripts (if missing)
mkdir -p scripts
[ -f scripts/sync_cascade_backup.sh ] || cp /opt/fabrik/scripts/sync_cascade_backup.sh scripts/
[ -f scripts/sync_extensions.sh ] || cp /opt/fabrik/scripts/sync_extensions.sh scripts/
chmod +x scripts/*.sh
```

### Step 3: Add Missing Documentation

**Create docs structure:**
```bash
mkdir -p docs/trajectories
```

**Create docs/INDEX.md (if missing):**
```markdown
# Documentation Index

**Last Updated:** YYYY-MM-DD

## Structure

- `README.md` - Project overview and quick start
- `CHANGELOG.md` - Version history
- `AGENTS.md` - AI agent instructions

## docs/
- `INDEX.md` - This file
- `trajectories/` - Saved Cascade conversations
```

**Create CHANGELOG.md (if missing):**
```markdown
# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added
- Fabrik compliance (YYYY-MM-DD)
```

**Verify README.md has required sections:**
1. **Purpose** - What does this project do?
2. **Quick Start** - How to run locally
3. **Architecture** - Main components and how they interact
4. **Configuration** - Environment variables required
5. **Deployment** - How to deploy to production

If any section is missing, ADD IT.

### Step 4: Fix Deployment Files

**If Dockerfile uses Alpine, REPLACE with:**
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

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8000}/health || exit 1

ENV PORT=8000
EXPOSE ${PORT}
CMD ["sh", "-c", "uvicorn src.main:app --host 0.0.0.0 --port ${PORT}"]
```

**If .env.example is missing, create it** with all required environment variables.

### Step 5: Fix Code Violations

**Replace hardcoded localhost:**
```python
# WRONG
DB_HOST = "localhost"
REDIS_HOST = "localhost"

# CORRECT
DB_HOST = os.getenv("DB_HOST", "localhost")
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
```

**Replace /tmp/ and tempfile usage:**
```python
# WRONG
import tempfile
fd, path = tempfile.mkstemp()
# or
path = "/tmp/myfile.txt"

# CORRECT
from pathlib import Path
import uuid
project_tmp = Path(__file__).parent.parent / ".tmp"
project_tmp.mkdir(exist_ok=True)
path = project_tmp / f"file_{uuid.uuid4().hex}.txt"
```

### Step 6: Add Missing Code Quality

**If tests/ doesn't exist:**
```bash
mkdir -p tests
```
Create at least one test file with a basic test.

**If requirements.txt doesn't exist:**
```bash
pip freeze > requirements.txt
```

### Step 7: Commit Changes
```bash
git add -A
git commit -m "Add Fabrik compliance

- Added infrastructure files (AGENTS.md, pre-commit, backup scripts)
- Added documentation (docs/INDEX.md, docs/trajectories/)
- Fixed Dockerfile to use bookworm-slim (if applicable)
- Fixed code violations (localhost, /tmp/, tempfile)"
```

### Step 8: Before Closing Session
1. Download trajectory if this was a valuable session
2. Save to `docs/trajectories/YYYY-MM-DD-fabrik-compliance.md`

---

## Priority Order for Fixing Projects

Based on violation count and completeness:

| Priority | Project | Reason |
|----------|---------|--------|
| 1 | file-worker | Most incomplete (0/5 docs) |
| 2 | file-api | Missing many basics |
| 3 | emailgateway | Alpine Dockerfile |
| 4 | youtube | Missing Dockerfile/compose |
| 5 | proxy | Few violations, almost complete |
| 6-10 | Others | High violation counts, need code fixes |

---

## Reference Files in Fabrik

| File | Purpose |
|------|---------|
| `/opt/fabrik/windsurfrules` | Symlink target for .windsurfrules |
| `/opt/fabrik/templates/scaffold/AGENTS.md` | Template AGENTS.md |
| `/opt/fabrik/templates/scaffold/pre-commit-config.yaml` | Template pre-commit config |
| `/opt/fabrik/scripts/sync_cascade_backup.sh` | Cascade backup script |
| `/opt/fabrik/scripts/sync_extensions.sh` | Extensions sync script |
| `/opt/fabrik/.windsurf/rules/00-critical.md` | Critical rules reference |
| `/opt/fabrik/.windsurf/rules/30-ops.md` | Deployment rules reference |
