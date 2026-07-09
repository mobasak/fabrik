-- Plan 1 (pick_models reachability gate) Phase C.
-- Additive column so pool runs record whether pick_models had a reachable option.
--
-- ADD COLUMN with no DEFAULT + no NOT NULL is a metadata-only operation in
-- PostgreSQL 11+ (verified against pg 16 on WSL) — instant, no table rewrite,
-- AccessExclusiveLock held only for the DDL itself (< 1ms in practice).
ALTER TABLE subagent_runs ADD COLUMN IF NOT EXISTS reachable_at_dispatch INTEGER;
--
-- IMPORTANT (Pass-2 review PF1 fix — sync-lock risk on hot tables):
-- Non-CONCURRENT CREATE INDEX takes a SHARE lock that blocks concurrent
-- INSERTs on the table. For this specific migration the subagent_runs table
-- was small (~ dozens of rows at ship time), so the sync lock was <100 ms
-- and the risk was accepted. For every future index on subagent_runs (which
-- will grow large as the fleet flywheel accumulates rows), use:
--   CREATE INDEX CONCURRENTLY IF NOT EXISTS ...
-- which builds without blocking writes (at the cost of not being runnable
-- inside a transaction — the migration tool must support DDL autocommit).
CREATE INDEX IF NOT EXISTS idx_subagent_runs_reachable ON subagent_runs (reachable_at_dispatch);
