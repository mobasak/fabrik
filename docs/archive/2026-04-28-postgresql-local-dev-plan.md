# PostgreSQL Local Dev Implementation Plan

**Date:** 2026-04-12
**Status:** Ready for Implementation
**Target:** Native WSL PostgreSQL for all python-api projects

---

## Executive Summary

**Current:** PostgreSQL 16 running natively on WSL at `localhost:5432`
**Goal:** All scaffolded python-api projects auto-configured for local PostgreSQL dev
**Impact:** 6 existing projects + all future projects

---

## Files to Modify

### 1. `/opt/fabrik/src/fabrik/scaffold.py`

#### Change A: `_scaffold_shared()` - Update .env.example (line 560)

**Current:**
```python
(project_dir / ".env.example").write_text(
    f"# {name} Configuration\n# Required\nPORT=8000\nLOG_LEVEL=INFO\n\n# Optional - uncomment if using database\n# DATABASE_URL=postgresql://user:pass@localhost:5432/{name}_dev\n"
)
```

**Replace with:**
```python
# .env.example — VPS/production template (not committed with real values)
(project_dir / ".env.example").write_text(
    f"# {name} Configuration (VPS/Production)\n"
    f"PORT=8000\n"
    f"LOG_LEVEL=INFO\n"
    f"SERVICE_NAME={name}\n\n"
    f"# Database (managed by Coolify on VPS)\n"
    f"# Set via Coolify secrets: POSTGRES_PASSWORD\n"
    f"DATABASE_URL=postgresql://postgres:${{POSTGRES_PASSWORD}}@postgres-main:5432/{name}\n"
)

# Add .env.local to .gitignore
gitignore_path = project_dir / ".gitignore"
if gitignore_path.exists():
    with open(gitignore_path, "a") as f:
        f.write("\n# Local development overrides\n.env.local\n")
```

#### Change B: `_scaffold_python_api()` - Add .env.local + DB creation (after line 870)

**Insert after SERVICE_NAME append to .env.example:**

```python
# .env.local — WSL local development configuration
db_name_dev = name.replace("-", "_") + "_dev"
(project_dir / ".env.local").write_text(
    f"# {name} Local Development (WSL)\n"
    f"LOG_LEVEL=DEBUG\n"
    f"SERVICE_NAME={name}\n\n"
    f"# Native PostgreSQL on WSL\n"
    f"DATABASE_URL=postgresql://postgres@localhost:5432/{db_name_dev}\n"
)

# Auto-create development database
try:
    # Check if database exists
    check_result = subprocess.run(
        ["sudo", "-u", "postgres", "psql", "-lqt"],
        capture_output=True,
        timeout=5,
        text=True
    )

    if db_name_dev not in check_result.stdout:
        # Create database
        create_result = subprocess.run(
            ["sudo", "-u", "postgres", "psql", "-c", f"CREATE DATABASE {db_name_dev};"],
            capture_output=True,
            timeout=5
        )
        if create_result.returncode == 0:
            click.echo(f"✅ Created PostgreSQL database: {db_name_dev}")
        else:
            click.echo(f"⚠️  Could not create database. Run manually:")
            click.echo(f"    sudo -u postgres psql -c 'CREATE DATABASE {db_name_dev};'")
    else:
        click.echo(f"✅ PostgreSQL database exists: {db_name_dev}")

except Exception as e:
    click.echo(f"⚠️  Database auto-creation failed. Create manually:")
    click.echo(f"    sudo -u postgres psql -c 'CREATE DATABASE {db_name_dev};'")
```

#### Change C: `_scaffold_chrome_extension()` - Same .env.local + DB logic

**Insert after line 2030 (after .env.example write for backend):**

```python
# .env.local — WSL local development for backend
db_name_dev = name.replace("-", "_") + "_dev"
env_local_path = project_dir / ".env.local"
env_local_path.write_text(
    f"# {name} Backend Local Development (WSL)\n"
    f"LOG_LEVEL=DEBUG\n"
    f"SERVICE_NAME={name}\n"
    f"CORS_ORIGINS=chrome-extension://*\n\n"
    f"# Native PostgreSQL on WSL\n"
    f"DATABASE_URL=postgresql://postgres@localhost:5432/{db_name_dev}\n"
)

# Auto-create development database (same logic as python-api)
try:
    check_result = subprocess.run(
        ["sudo", "-u", "postgres", "psql", "-lqt"],
        capture_output=True,
        timeout=5,
        text=True
    )

    if db_name_dev not in check_result.stdout:
        create_result = subprocess.run(
            ["sudo", "-u", "postgres", "psql", "-c", f"CREATE DATABASE {db_name_dev};"],
            capture_output=True,
            timeout=5
        )
        if create_result.returncode == 0:
            click.echo(f"✅ Created PostgreSQL database: {db_name_dev}")
        else:
            click.echo(f"⚠️  Could not create database. Run manually:")
            click.echo(f"    sudo -u postgres psql -c 'CREATE DATABASE {db_name_dev};'")
    else:
        click.echo(f"✅ PostgreSQL database exists: {db_name_dev}")

except Exception:
    click.echo(f"⚠️  Database auto-creation failed. Create manually:")
    click.echo(f"    sudo -u postgres psql -c 'CREATE DATABASE {db_name_dev};'")
```

---

### 2. `/opt/fabrik/templates/scaffold/docs/QUICKSTART_TEMPLATE.md`

**Insert after line 23 (before "## Quick Start"):**

```markdown
## Local Development (WSL)

### Database Setup

This project uses PostgreSQL. WSL development uses native PostgreSQL at `localhost:5432`.

**Auto-created during scaffold:**
```bash
# Database: {project-name}_dev
# Connection: postgresql://postgres@localhost:5432/{project-name}_dev
```

**If database was not auto-created:**
```bash
sudo -u postgres psql -c "CREATE DATABASE {project-name}_dev;"
```

### Running Locally

```bash
cd /opt/{project-name}

# Use local development config
cp .env.local .env

# Run migrations (if using Alembic)
.venv/bin/alembic upgrade head

# Start development server
.venv/bin/uvicorn src.{package}.main:app --reload --port [PORT]
```

### Database Access

```bash
# Connect with psql
psql -U postgres -d {project-name}_dev

# Useful commands
\dt              # List tables
\d table_name    # Describe table
\q               # Quit
```

---

## Quick Start (Docker - VPS Deployment)
```

---

### 3. `/opt/fabrik/.windsurf/rules/25-data-postgres.md`

**Insert after line 10 (before "## Migration Discipline"):**

```markdown
## Local Development Setup

### WSL PostgreSQL Configuration

- Native PostgreSQL 16 runs at `localhost:5432` on WSL
- Each project gets a dedicated development database: `{project_name}_dev`
- Scaffold auto-creates databases during `fabrik scaffold`
- Connection: `postgresql://postgres@localhost:5432/{project_name}_dev`

### Environment Files

- `.env.local` → WSL development (gitignored, auto-generated)
- `.env.example` → VPS template (committed, references `postgres-main`)
- `.env` → Active config (gitignored, copy from `.env.local` for dev)

### Manual Database Creation

If scaffold fails to auto-create:

```bash
sudo -u postgres psql -c "CREATE DATABASE my_project_dev;"
```

Or use helper script:

```bash
/opt/fabrik/scripts/create_pg_dev_db.sh my-project
```

### Connecting from Code

SQLAlchemy reads `DATABASE_URL` from environment:

```python
from sqlalchemy.ext.asyncio import create_async_engine
import os

# Works in both WSL and VPS - just swap env var
engine = create_async_engine(os.getenv("DATABASE_URL"))
```

**WSL:** `DATABASE_URL=postgresql://postgres@localhost:5432/my_project_dev`
**VPS:** `DATABASE_URL=postgresql://postgres:${POSTGRES_PASSWORD}@postgres-main:5432/my_project`

No code changes needed between environments.

---
```

---

### 4. `/opt/fabrik/scripts/create_pg_dev_db.sh`

**Status:** ✅ Already created above

Make executable:
```bash
chmod +x /opt/fabrik/scripts/create_pg_dev_db.sh
```

---

## Implementation Checklist

### Phase 1: Core Changes
- [ ] Modify `_scaffold_shared()` - Update .env.example, add .gitignore entry
- [ ] Modify `_scaffold_python_api()` - Add .env.local generation + DB creation
- [ ] Modify `_scaffold_chrome_extension()` - Add .env.local generation + DB creation
- [ ] Make `create_pg_dev_db.sh` executable

### Phase 2: Documentation
- [ ] Update `QUICKSTART_TEMPLATE.md` with local dev section
- [ ] Update `25-data-postgres.md` with local dev setup
- [ ] Update `CHANGELOG.md` with changes

### Phase 3: Testing
- [ ] Test scaffold new python-api project
- [ ] Verify .env.local created
- [ ] Verify .env.example has postgres-main
- [ ] Verify database auto-created
- [ ] Test `cp .env.local .env && uvicorn` works
- [ ] Test existing projects can adopt pattern manually

### Phase 4: Backfill Existing Projects (Optional)
- [ ] youtube → Create .env.local
- [ ] proposal-creator → Create .env.local
- [ ] seo → Update DATABASE_URL in .env.local
- [ ] job-agent → Create .env.local
- [ ] triggered-content-orchestration → Create .env.local
- [ ] translator → Create .env.local (if using DB)

---

## Environment Variable Matrix

| Environment | File | DATABASE_URL Value |
|-------------|------|-------------------|
| **WSL Dev** | `.env.local` | `postgresql://postgres@localhost:5432/{name}_dev` |
| **VPS Prod** | Coolify secret | `postgresql://postgres:${POSTGRES_PASSWORD}@postgres-main:5432/{name}` |
| **Template** | `.env.example` | `postgresql://postgres:${POSTGRES_PASSWORD}@postgres-main:5432/{name}` |

---

## Migration Guide for Existing Projects

### For Projects Without .env.local Yet:

```bash
cd /opt/my-project

# Create .env.local
cat > .env.local << 'EOF'
# my-project Local Development (WSL)
LOG_LEVEL=DEBUG
SERVICE_NAME=my-project

# Native PostgreSQL on WSL
DATABASE_URL=postgresql://postgres@localhost:5432/my_project_dev
EOF

# Create database
sudo -u postgres psql -c "CREATE DATABASE my_project_dev;"

# Use local config
cp .env.local .env

# Run migrations
.venv/bin/alembic upgrade head
```

---

## Deployment Flow (No Changes Needed)

1. **Scaffold** → Creates .env.local (WSL dev) + .env.example (VPS template)
2. **Local Dev** → `cp .env.local .env` + run migrations + uvicorn
3. **Deploy** → `fabrik apply` → Coolify injects `POSTGRES_PASSWORD` → connects to `postgres-main`
4. **Migrations** → Run via Alembic in container startup (future: add to deploy template)

---

## Verification Commands

```bash
# After scaffold
ls -la /opt/my-new-api/.env.local     # Should exist
grep DATABASE_URL /opt/my-new-api/.env.local   # Should be localhost
grep DATABASE_URL /opt/my-new-api/.env.example # Should be postgres-main

# After database creation
sudo -u postgres psql -l | grep my_new_api_dev  # Should show database

# After local start
curl http://localhost:8000/health   # Should return 200 with db:connected
```

---

## Estimated Effort

| Phase | Time | Complexity |
|-------|------|------------|
| Code changes | 30 min | Low |
| Documentation | 15 min | Low |
| Testing | 20 min | Low |
| TOTAL | **~1 hour** | **Low Risk** |

---

## Rollback Plan

If issues arise:

1. Revert `scaffold.py` changes
2. Delete `/opt/fabrik/scripts/create_pg_dev_db.sh`
3. Projects continue using manual .env configuration

No production impact - VPS unchanged.

---

## Success Criteria

- [ ] `fabrik scaffold my-api --type python-api` creates `.env.local` with localhost DB URL
- [ ] Database `my_api_dev` auto-created on WSL PostgreSQL
- [ ] `cp .env.local .env && uvicorn src.my_api.main:app` works immediately
- [ ] `.env.example` references `postgres-main` for VPS deploy
- [ ] `fabrik apply` deploys to VPS with zero manual DB config
- [ ] Alembic migrations work in both WSL and VPS without code changes

---

## Notes

- Native PostgreSQL is FASTER than Docker for local dev
- No port conflicts (5432 already owned by native PG)
- Same PostgreSQL 16 version as VPS `postgres-main`
- Existing projects can adopt pattern gradually (not breaking)
- Future: Add Alembic migration auto-run to deploy templates
