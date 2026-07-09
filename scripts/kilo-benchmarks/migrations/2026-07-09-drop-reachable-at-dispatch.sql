-- Reverts scripts/kilo-benchmarks/migrations/2026-07-09-add-reachable-at-dispatch.sql
-- per fabrik-lib source-of-truth AI decision (2026-07-09).
--
-- Rationale: the ADD migration and its consuming `_INSERT` extension were a
-- vendored-copy fork of canonical subagents at /opt/fabrik-lib. Canonical is
-- 11-col (13 total incl. id+ts) and does NOT adopt `reachable_at_dispatch`
-- because: (a) canonical has no reachable-set pre-filter to record "fell
-- through", (b) the reachability outcome is already carried by `status`
-- (capped/error) per (model, provider), (c) any pre-filter is superseded by
-- plan-1 provider routing (`provider_max_price` + content-stall detection).
--
-- Sequenced correctly: canonical was re-vendored FIRST (11-col _INSERT), then
-- every code reference to reachable_at_dispatch removed, then this drop. So no
-- forked 12-col INSERT exists to silent-fail once the column is gone.
--
-- Idempotent: safe to re-run.
--
-- PF3 fix (post-Pass-1 review): wrap in BEGIN/COMMIT so DROP INDEX + DROP
-- COLUMN commit atomically. IF EXISTS only swallows "object doesn't exist";
-- lock timeouts, FK dependencies, replication-slot pinning, or privilege
-- errors on the ALTER would otherwise leave the table with the column
-- present but the index gone — an inconsistent shape that requires manual
-- investigation. PostgreSQL supports transactional DDL; a two-statement
-- transaction gives all-or-nothing semantics for future re-runs on other
-- environments (staging, fresh provision, DR restore).

BEGIN;
DROP INDEX IF EXISTS idx_subagent_runs_reachable;
ALTER TABLE subagent_runs DROP COLUMN IF EXISTS reachable_at_dispatch;
COMMIT;
