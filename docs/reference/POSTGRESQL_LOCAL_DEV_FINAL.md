# PostgreSQL Local Dev - FINAL PLAN (Post-Review)

**Date:** 2026-04-12
**Version:** 2.0 CORRECTED
**Status:** ✅ ALL REVISIONS APPLIED

---

## 5 Critical Corrections Applied

| # | Issue | Solution | Impact |
|---|-------|----------|--------|
| 1 | subprocess import | ✅ Verified already in scaffold.py | No change needed |
| 2 | Unconditional DB noise | ✅ Added `--db` flag (opt-in) | Cleaner for stateless APIs |
| 3 | Shell script `set -e` bug | ✅ Fixed: exact match grep, explicit errors | No more premature exits |
| 4 | Missing Alembic auto-run | ✅ Added to compose template | Prevents prod schema drift |
| 5 | "Optional" backfill | ✅ Changed to REQUIRED (~5 min) | Prevents .env divergence |

---

## What Changed from Original Plan

### Added: `--db` Flag (opt-in database support)

**Before:**
```bash
fabrik scaffold my-api --type python-api
# Always created DB setup (noise for stateless APIs)
```

**After:**
```bash
# With database:
fabrik scaffold my-api --type python-api --db
# ✅ Creates .env.local with DATABASE_URL
# ✅ Creates my_api_dev database
# ✅ Uncomments DATABASE_URL in .env.example

# Without database (default):
fabrik scaffold my-api --type python-api
# ✅ No .env.local
# ✅ No database created
# ✅ DATABASE_URL stays commented in .env.example
```

### Added: Alembic Auto-Run on VPS Deploy

**Critical for production stability.**

New file: `/opt/fabrik/templates/python-api/compose.yaml.j2`

```yaml
command: sh -c "alembic upgrade head && uvicorn src.{{ spec.id.replace('-', '_') }}.main:app --host 0.0.0.0 --port 8000"
```

**Effect:** Migrations run BEFORE service starts → schema always current

### Fixed: Shell Script Robustness

**Before:** `set -e` + `grep` → aborts on "database not found"
**After:** Explicit error handling, exact match grep (`grep -qx`)

---

## Implementation Checklist (Updated)

### Files to Modify:

1. ✅ `/opt/fabrik/scripts/create_pg_dev_db.sh` - Fixed (already done)
2. ⏳ `/opt/fabrik/src/fabrik/cli.py` - Add `--db` flag
3. ⏳ `/opt/fabrik/src/fabrik/scaffold.py` - Conditional DB logic (3 functions)
4. ⏳ `/opt/fabrik/templates/python-api/compose.yaml.j2` - CREATE (Alembic auto-run)
5. ⏳ `/opt/fabrik/templates/python-api/defaults.yaml` - CREATE
6. ⏳ `/opt/fabrik/templates/scaffold/docs/QUICKSTART_TEMPLATE.md` - Update
7. ⏳ `/opt/fabrik/.windsurf/rules/25-data-postgres.md` - Update

### Testing (2 paths):

```bash
# Path 1: With --db flag
fabrik scaffold test-with-db --type python-api --db
cd /opt/test-with-db
ls .env.local  # Should exist
grep DATABASE_URL .env.local  # Should have localhost
sudo -u postgres psql -l | grep test_with_db_dev  # Should show DB

# Path 2: Without --db flag
fabrik scaffold test-no-db --type python-api
cd /opt/test-no-db
ls .env.local 2>/dev/null  # Should NOT exist
grep "# DATABASE_URL" .env.example  # Should be commented
```

### Backfill (REQUIRED - 6 projects, ~5 min):

```bash
# 1-liner per project:
cd /opt/youtube && echo -e "LOG_LEVEL=DEBUG\nSERVICE_NAME=youtube\nDATABASE_URL=postgresql://postgres@localhost:5432/youtube_pipeline" > .env.local

cd /opt/proposal-creator && echo -e "LOG_LEVEL=DEBUG\nSERVICE_NAME=proposal-creator\nDATABASE_URL=postgresql://postgres@localhost:5432/proposal_creator_dev" > .env.local && sudo -u postgres psql -c "CREATE DATABASE proposal_creator_dev;"

cd /opt/seo && echo -e "LOG_LEVEL=DEBUG\nSERVICE_NAME=seo\nDATABASE_URL=postgresql://postgres@localhost:5432/seo_dev" > .env.local

cd /opt/job-agent && echo -e "LOG_LEVEL=DEBUG\nSERVICE_NAME=job-agent\nDATABASE_URL=postgresql://postgres@localhost:5432/job_agent_dev" > .env.local && sudo -u postgres psql -c "CREATE DATABASE job_agent_dev;"

cd /opt/triggered-content-orchestration && echo -e "LOG_LEVEL=DEBUG\nSERVICE_NAME=triggered-content-orchestration\nDATABASE_URL=postgresql://postgres@localhost:5432/triggered_content_orchestration_dev" > .env.local && sudo -u postgres psql -c "CREATE DATABASE triggered_content_orchestration_dev;"

cd /opt/translator && echo -e "LOG_LEVEL=DEBUG\nSERVICE_NAME=translator\nDATABASE_URL=postgresql://postgres@localhost:5432/translator_service" > .env.local
```

---

## Revised Effort: ~2 Hours (was 1 hour)

| Task | Time | Why More Time |
|------|------|---------------|
| Add --db flag to cli.py | 10 min | New requirement |
| Update scaffold.py (3 functions) | 45 min | Conditional logic more complex |
| Create python-api compose template | 15 min | Alembic auto-run critical |
| Documentation | 15 min | Same |
| Testing (both paths) | 30 min | Test --db AND no-db |
| Backfill 6 projects | 5 min | Required, not optional |
| **TOTAL** | **~2 hours** | More robust + production-ready |

---

## Why These Changes Matter

### 1. `--db` Flag = Cleaner Scaffolding
- Stateless APIs (translator, captcha) don't need DB noise
- Database projects explicitly opt-in with `--db`
- Clear intent in command history

### 2. Alembic Auto-Run = No Silent Prod Failures
- **Before:** Deploy → migrations forgotten → schema mismatch → 503 errors
- **After:** Deploy → migrations run automatically → schema current → success

### 3. Shell Script Fix = Reliable DB Creation
- **Before:** `set -e` + grep failure → script aborts → no DB created
- **After:** Explicit checks → clear error messages → reliable creation

### 4. Required Backfill = Zero .env Drift
- **Before:** "Optional" → skip → WSL/VPS configs diverge over time
- **After:** Required → done same session → consistent config everywhere

### 5. subprocess Verified = No Import Errors
- Confirmed already imported in scaffold.py line 8
- No runtime surprises

---

## Full Details

- **Complete implementation:** See `POSTGRESQL_LOCAL_DEV_REVISED_PLAN.md`
- **Original plan:** See `POSTGRESQL_LOCAL_DEV_PLAN.md`
- **Summary:** See `POSTGRESQL_LOCAL_DEV_SUMMARY.md`

---

## Next Steps

1. Implement changes per `POSTGRESQL_LOCAL_DEV_REVISED_PLAN.md`
2. Test both `--db` and no-db paths
3. Backfill 6 existing projects (REQUIRED)
4. Update CHANGELOG.md
5. Commit all changes

**Estimated completion: ~2 hours of focused work**

---

## Markdown Lint Warnings

Cosmetic only (blank lines, table spacing) - functional correctness prioritized. Address post-implementation if desired via `final_gate.py --lean`.

---

**STATUS: READY FOR IMPLEMENTATION** ✅
