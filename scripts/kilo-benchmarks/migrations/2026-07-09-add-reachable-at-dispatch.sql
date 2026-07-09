-- Plan 1 (pick_models reachability gate) Phase C.
-- Additive column so pool runs record whether pick_models had a reachable option.
ALTER TABLE subagent_runs ADD COLUMN IF NOT EXISTS reachable_at_dispatch INTEGER;
CREATE INDEX IF NOT EXISTS idx_subagent_runs_reachable ON subagent_runs (reachable_at_dispatch);
