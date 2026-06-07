# Plan: PostgreSQL 16 → 18 Upgrade (WSL + VPS)

**Created:** 2026-05-25
**Status:** Planned — not started
**Priority:** Medium (no blocking issue on PG16, but PG18 native `uuidv7()` eliminates app-side generation)

---

## Why Upgrade

- **PG18 native `uuidv7()`** — currently generating UUIDs app-side via `uuid_utils.compat.uuid7`. PG18 has `DEFAULT uuidv7()` at schema level.
- **Performance improvements** — PG18 has incremental backup, improved HNSW index performance in pgvector, better parallel query execution.
- **Our docs say PG18** — multiple rule packs reference "PostgreSQL 18" but actual installed version is 16.14. Need to match reality.

## What We Have

| Environment | Current version | Data | Who controls upgrades |
| --- | --- | --- | --- |
| WSL (local dev) | PostgreSQL 16.14 | Dev databases per project (~40 DBs) | Us — direct `apt` upgrade |
| VPS (postgres-main) | PostgreSQL 16.x (Docker, Fabrik-managed since 2026-05-30 Coolify removal) | Production data for all deployed services | Us — compose image bump + dump/restore |
| Supabase (`trade-intelligence`) | PostgreSQL **17.6** | Trade-intelligence app data | **Supabase manages** — we can't choose PG18; we move when they move (note 2026-06-02) |

## Constraint added 2026-06-02 — Supabase pins our upper bound

Supabase's managed Postgres for `trade-intelligence` is at 17.6 today. Supabase rolls Postgres major-version upgrades on their own cadence (currently 17.x; 18.x not yet GA on their platform as of this note). **The fleet can run PG18 on WSL + postgres-main even while Supabase stays on 17.6 — wire compatibility is fine across 16 ↔ 17 ↔ 18 for the queries we issue** — but anywhere our code uses PG18-only features (the headline `uuidv7()` DEFAULT, certain JSON path operators added in 17/18) it must degrade gracefully when the connection is to Supabase. Practical rule: **PG18-only features stay opt-in per service**; the cross-env code uses PG17-compatible constructs (e.g. `uuid_utils.compat.uuid7()` app-side, the very thing we wanted to retire).

This means the upgrade is still worth doing — WSL + postgres-main move together to PG18, and we keep the app-side UUID generator for the Supabase code path until Supabase's PG version catches up. Re-evaluate Supabase pinning at every Supabase major-version bump.

## Risks

- **Data loss** if backup/restore fails
- **Extension compatibility** — pgvector, pg_trgm, pg_cron must support PG18
- **Application compatibility** — asyncpg driver must support PG18 (and PG17 since we'll talk to Supabase 17.6 in parallel)
- **Downtime** — VPS services unavailable during migration
- **Cross-version drift** — services that talk to Supabase must not regress to PG18-only syntax that PG17 can't parse

---

## Phase 1: WSL (local dev) — do first

### Pre-flight

- [ ] Verify pgvector supports PG18 (`apt list postgresql-18-pgvector` or compile from source)
- [ ] Verify pg_trgm bundled with PG18 (it's a contrib module — should be automatic)
- [ ] Verify asyncpg supports PG18 (`pip show asyncpg` — check release notes)
- [ ] List all dev databases: `sudo -u postgres psql -c "\l"`

### Execute

```bash
# 1. Dump all databases
sudo -u postgres pg_dumpall > /tmp/pg16_full_dump_$(date +%Y%m%d).sql

# 2. Stop PG16
sudo systemctl stop postgresql

# 3. Add PG18 repo (PostgreSQL Global Development Group)
sudo sh -c 'echo "deb http://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" > /etc/apt/sources.list.d/pgdg.list'
wget --quiet -O - https://www.postgresql.org/media/keys/ACCC4CF8.asc | sudo apt-key add -
sudo apt update

# 4. Install PG18
sudo apt install postgresql-18 postgresql-18-pgvector

# 5. Verify PG18 is running
sudo -u postgres psql -c "SELECT version();"

# 6. Restore all databases
sudo -u postgres psql -f /tmp/pg16_full_dump_$(date +%Y%m%d).sql

# 7. Enable extensions per database
sudo -u postgres psql -d <db> -c "CREATE EXTENSION IF NOT EXISTS vector;"
sudo -u postgres psql -d <db> -c "CREATE EXTENSION IF NOT EXISTS pg_trgm;"

# 8. Verify
sudo -u postgres psql -c "\l"
sudo -u postgres psql -d <test_db> -c "SELECT uuidv7();"  -- should work on PG18
```

### Validate

- [ ] All dev databases restored
- [ ] pgvector extension loads
- [ ] pg_trgm extension loads
- [ ] `uuidv7()` function available natively
- [ ] Run `pytest` on youtube project (exercises asyncpg + pgvector)
- [ ] Run `pytest` on one other project

### Rollback

```bash
# PG16 is still installed — switch back
sudo systemctl stop postgresql@18-main
sudo systemctl start postgresql@16-main
```

---

## Phase 2: VPS (production) — do after WSL is proven

### Pre-flight

- [ ] WSL Phase 1 complete and validated
- [ ] Full Backrest backup verified (check `backup.vps1.ocoron.com`)
- [ ] Notify via Telegram: "Maintenance window — all services down for PG upgrade"
- [ ] Document all databases: `docker exec postgres-main psql -U postgres -c "\l"`
- [ ] Document all extensions per database
- [ ] Dump all databases inside the container

### Execute

- [ ] Stop all Coolify services that use postgres-main
- [ ] `pg_dumpall` inside postgres-main container → save to VPS filesystem
- [ ] Update Coolify postgres-main service to PG18 image (`postgres:18-bookworm`)
- [ ] Start postgres-main with PG18 image
- [ ] Restore from dump
- [ ] Enable pgvector + pg_trgm on all databases
- [ ] Verify `uuidv7()` available
- [ ] Restart all Coolify services
- [ ] Run `fabrik audit-registrars` — verify all services healthy

### Validate

- [ ] All services healthy on Gatus (`status.vps1.ocoron.com`)
- [ ] No errors in GlitchTip (`errors.vps1.ocoron.com`)
- [ ] Prometheus scraping all targets
- [ ] Test one API endpoint per deployed service
- [ ] Test youtube search (exercises pgvector HNSW)

### Rollback

- [ ] Keep PG16 dump on VPS filesystem for 7 days
- [ ] If PG18 fails: revert Coolify postgres-main to `postgres:16-bookworm`, restore from dump

---

## Phase 3: Update docs (after both environments upgraded)

- [ ] `25-data-postgres.md` line 20: update WSL version reference
- [ ] Remove "PG18 available since Sep 2025" caveat — it's now the installed version
- [ ] Simplify UUIDv7 section: `DEFAULT uuidv7()` at schema level is now the primary pattern, app-side `uuid_utils.compat.uuid7` is the fallback for PG16 compatibility
- [ ] `fabrik-lifecycle.md`: confirm "PostgreSQL 18" (already says this)
- [ ] `technology-stack-decision-guide.md`: confirm "PostgreSQL 18" (already says this)
- [ ] Run sync to push updated docs to all projects

---

## Estimated Time

- WSL: ~1 hour (dump + install + restore + test)
- VPS: ~2 hours (includes maintenance window + full validation)
- Docs: ~30 minutes
- **Total: ~3.5 hours in a dedicated session**
