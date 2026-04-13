# PostgreSQL Local Dev - Final Implementation Plan

**Date:** 2026-04-12
**Reviewed:** 3 iterations
**Status:** READY TO IMPLEMENT

---

## TL;DR

✅ **Use existing native PostgreSQL on WSL** (localhost:5432)
✅ **Update 1 file:** `src/fabrik/scaffold.py` (3 functions)
✅ **Update 2 docs:** `QUICKSTART_TEMPLATE.md`, `25-data-postgres.md`
✅ **Create 1 script:** `scripts/create_pg_dev_db.sh` (done)
✅ **Time:** ~1 hour low-risk work
✅ **Impact:** All future python-api projects auto-configured

---

## What Changes

### 1. scaffold.py - 3 Functions Modified

**`_scaffold_shared()` (line 560):**
- Update `.env.example` → reference `postgres-main` for VPS
- Add `.env.local` to `.gitignore`

**`_scaffold_python_api()` (after line 870):**
- Generate `.env.local` → `postgresql://postgres@localhost:5432/{name}_dev`
- Auto-create database: `sudo -u postgres psql -c "CREATE DATABASE ..."`
- Output success/failure message

**`_scaffold_chrome_extension()` (after line 2030):**
- Same as python-api (backend uses same pattern)

### 2. QUICKSTART_TEMPLATE.md

Add **"Local Development (WSL)"** section:
- Database auto-created during scaffold
- `cp .env.local .env` to activate local config
- `psql` connection instructions
- Alembic migration commands

### 3. 25-data-postgres.md

Add **"Local Development Setup"** section at top:
- Native PostgreSQL 16 at localhost:5432
- Database naming: `{project_name}_dev`
- Environment file mapping
- Manual DB creation fallback

### 4. create_pg_dev_db.sh

✅ Already created - helper script for manual database creation

---

## Environment File Matrix

| File | Purpose | DATABASE_URL |
|------|---------|--------------|
| `.env.local` | WSL dev (auto-generated, gitignored) | `postgresql://postgres@localhost:5432/{name}_dev` |
| `.env.example` | VPS template (committed) | `postgresql://postgres:${POSTGRES_PASSWORD}@postgres-main:5432/{name}` |
| `.env` | Active config (gitignored) | Copy from `.env.local` for dev |

---

## Workflow After Implementation

### New Project (Auto)
```bash
fabrik scaffold my-api --type python-api
# ✅ .env.local created with localhost DB
# ✅ my_api_dev database created
# ✅ .env.example has postgres-main for VPS

cd /opt/my-api
cp .env.local .env
.venv/bin/alembic upgrade head
.venv/bin/uvicorn src.my_api.main:app --reload
```

### Existing Project (Manual Migration)
```bash
cd /opt/existing-project
# Create .env.local manually or copy from template
sudo -u postgres psql -c "CREATE DATABASE existing_project_dev;"
cp .env.local .env
.venv/bin/alembic upgrade head
```

### Deploy to VPS (Unchanged)
```bash
fabrik apply my-api
# Coolify injects POSTGRES_PASSWORD
# Service connects to postgres-main:5432
# Alembic migrations run on startup
```

---

## Implementation Steps

1. **Modify scaffold.py** (3 functions)
2. **Update QUICKSTART_TEMPLATE.md** (add local dev section)
3. **Update 25-data-postgres.md** (add setup section)
4. **chmod +x scripts/create_pg_dev_db.sh**
5. **Test with new project**
6. **Update CHANGELOG.md**

---

## Testing Checklist

```bash
# 1. Create new project
fabrik scaffold test-pg-dev --type python-api

# 2. Verify files created
ls -la /opt/test-pg-dev/.env.local      # Should exist
ls -la /opt/test-pg-dev/.env.example    # Should exist

# 3. Verify content
grep localhost /opt/test-pg-dev/.env.local          # Should match
grep postgres-main /opt/test-pg-dev/.env.example    # Should match

# 4. Verify database
sudo -u postgres psql -l | grep test_pg_dev  # Should show database

# 5. Test local dev
cd /opt/test-pg-dev
cp .env.local .env
.venv/bin/uvicorn src.test_pg_dev.main:app --reload --port 8000
curl http://localhost:8000/health  # Should return 200

# 6. Cleanup
rm -rf /opt/test-pg-dev
sudo -u postgres psql -c "DROP DATABASE test_pg_dev;"
```

---

## Projects That Benefit

### Immediate (Auto)
- All NEW `python-api` projects
- All NEW `chrome-extension` projects

### Optional Backfill (6 existing projects)
- youtube
- proposal-creator
- seo (already has seo_dev, update .env.local)
- job-agent
- triggered-content-orchestration
- translator

---

## Why This Works

1. ✅ **Zero production changes** - VPS uses postgres-main unchanged
2. ✅ **Zero code changes** - SQLAlchemy reads DATABASE_URL from env
3. ✅ **Native PG faster** than Docker for local dev
4. ✅ **Same PG version** - 16 on both WSL and VPS
5. ✅ **Auto-created DBs** - developer doesn't think about it
6. ✅ **Alembic works** - same migrations dev → prod

---

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| DB auto-creation fails | Fallback message with manual command |
| sudo requires password | Script shows manual command |
| Database already exists | Check before create, skip if exists |
| Wrong DATABASE_URL format | Template enforced in code |

**Overall Risk:** LOW - Non-breaking, VPS unchanged, rollback trivial

---

## Full Details

See `/opt/fabrik/docs/reference/POSTGRESQL_LOCAL_DEV_PLAN.md` for:
- Complete code snippets with line numbers
- Full documentation templates
- Migration guide for existing projects
- Verification commands
- Rollback procedures

---

## Decision: APPROVED ✅

This plan is:
- ✅ Factual (based on existing WSL PostgreSQL)
- ✅ Minimal (3 functions, 2 docs, 1 script)
- ✅ Low-risk (no production impact)
- ✅ High-value (auto-config for all future projects)

**Ready to implement.**
