# Subagent-Runs Telemetry — Lean Spec (WSL-dev-first)

**Status:** DRAFT
**Date:** 2026-07-06
**Supersedes:** the CONVERGED-but-overkill version at this same path earlier today. Rewritten per user direction ("throw away my current spec — overkill") to the minimum viable flywheel.
**Scope:** Local WSL postgres for now (`postgresql://postgres@localhost:5432/fabrik_analytics`); postgres-main on VPS comes later when we deploy.

## Goal (plain English)

Every subagent run writes one row to a shared table. A nightly script reads the table and emits a ranked-model-per-task-type markdown doc. The subagents module's `pick_models()` will eventually consume that doc (upstream work, out of scope here).

## The 4 tiny changes

1. **Apply DDL to local postgres.** Verbatim from the module's exported `SUBAGENT_RUNS_DDL` (see below). Ensures `fabrik_analytics` DB exists first, then creates `subagent_runs` table + 2 indexes. Idempotent (`CREATE TABLE IF NOT EXISTS` + `CREATE INDEX IF NOT EXISTS`).
2. **Fleet-wide env injection.** Add two lines to every project's `.env.local` (dev) and, later, the VPS `.env` (prod):
   - `SUBAGENT_RUNS_DSN=postgresql://postgres@localhost:5432/fabrik_analytics` (dev; swap to `postgres-main` on VPS)
   - `SUBAGENT_PROJECT=<project-id>` (project's own name)
   Uses the `postgres` superuser same as `cost_ledger` does today (see `fabrik/drivers/postgres.py:1006` comment: "Currently v1 callers don't pass a role — projects use the postgres superuser, which already has all privileges"). No new roles. Personal fleet, single operator.
3. **New script `scripts/kilo-benchmarks/rank_task_subagents.py`** (~80 lines). Reads the table, groups by `(task_type, model)`, computes `value = success_rate × avg_quality_score / avg_cost_usd`, emits `docs/reference/kilo/TASK_SUBAGENT_SELECTION.md`. Includes only pairs with ≥3 runs in last 90 days.
4. **One line into `daily_refresh.sh`** — insert `_step "rank_task_subagents" "$VENV_PY" "$KB/rank_task_subagents.py" \` + `|| echo "[daily_refresh] rank_task_subagents failed (non-fatal)"` between the existing `rank_coding_subagents` at `:344` and `export_models_browser` at `:355`.

## Where things live

| Thing | Location |
|---|---|
| DB (dev) | Local postgres in WSL, `localhost:5432` |
| DB (later, VPS deploy) | `postgres-main` container, same DSN structure |
| Database name | `fabrik_analytics` (already exists — hosts `cost_ledger`) |
| Table | `subagent_runs` (new) |
| Role | `postgres` superuser (personal fleet — no separate roles for dev) |
| Aggregator | `/opt/fabrik/scripts/kilo-benchmarks/rank_task_subagents.py` (hub-side) |
| Aggregator connection | Direct `psql -h localhost -d fabrik_analytics` via subprocess (WSL) or existing `_run_sql` at `fabrik/drivers/postgres.py:111` (VPS-mode) |
| Output doc | `docs/reference/kilo/TASK_SUBAGENT_SELECTION.md` (governance-synced to every project via `fabrik_synced_manifest.py:69`) |

## DDL (verbatim from module export)

Source: `python -c "from subagents import SUBAGENT_RUNS_DDL; print(SUBAGENT_RUNS_DDL)"` at `/opt/fabrik-lib/subagents/subagents/pg_ledger.py:35`. Do **not** author DDL locally — always import from the module so the schema stays a single source of truth.

```sql
CREATE TABLE IF NOT EXISTS subagent_runs (
    id            BIGSERIAL PRIMARY KEY,
    ts            TIMESTAMPTZ NOT NULL DEFAULT now(),
    project       TEXT NOT NULL,
    agent_id      TEXT NOT NULL,
    task_type     TEXT NOT NULL,
    model         TEXT NOT NULL,
    provider      TEXT,
    status        TEXT NOT NULL,
    cost_usd      DOUBLE PRECISION,
    turns         INTEGER,
    latency_s     DOUBLE PRECISION,
    quality_score REAL,
    tool_calls    JSONB
);
CREATE INDEX IF NOT EXISTS subagent_runs_task_model_idx ON subagent_runs (task_type, model);
CREATE INDEX IF NOT EXISTS subagent_runs_ts_idx ON subagent_runs (ts);
```

## Ranking (in the aggregator)

```sql
SELECT task_type, model,
       COUNT(*) AS n,
       AVG(cost_usd) AS avg_cost,
       AVG(quality_score) AS avg_quality,
       SUM(CASE WHEN status='done' THEN 1.0 ELSE 0.0 END) / COUNT(*) AS success_rate
FROM subagent_runs
WHERE ts > NOW() - INTERVAL '90 days'
GROUP BY task_type, model
HAVING COUNT(*) >= 3;
```

`value = success_rate × avg_quality / max(avg_cost, 1e-9)` (cost-in-denominator = "value per dollar" — matches `select.py:349`'s `prefer="value"` `rank_weight / price` pattern). Constant at the top of the script, invert to `× avg_cost` if the user's original shorthand meant literal multiplication.

Output shape (mirrors the module's `_TABLE: dict[str, list[str]]` at `select.py:119`):

```markdown
Last refresh: 2026-07-06
Formula: success × quality / cost | Window: 90 days | Min runs: 3

### spec (n_total=127)
| rank | model | value | success | avg_cost | avg_quality | n |
|---:|---|---:|---:|---:|---:|---:|
| 1 | z-ai/glm-5 | 4.82 | 0.94 | 0.32 | 1.64 | 47 |
| 2 | minimax/minimax-m2.5 | 4.21 | 0.91 | 0.28 | 1.30 | 62 |

### plan (n_total=…)
…
```

Empty-pool (no rows yet or none meet ≥3 threshold): emit a stub with a "No aggregated runs yet — `pick_models` continues to use vendored `_TABLE` default." line. Never crashes daily_refresh.

## Explicitly out of scope

- **Per-project INSERT-only roles.** ~~Same postgres superuser as `cost_ledger`.~~ **RESOLVED 2026-07-07** — `create_subagent_ins_role()` provisions a per-project `{project}_subagent_ins` role (INSERT + sequence USAGE only) and `_provision_postgres` injects `SUBAGENT_RUNS_DSN` unconditionally into every DB-bearing project. Least-privilege proven live on vps1 (`INSERT` ok, `SELECT/UPDATE/DELETE` denied).
- **VPS deploy of the table.** ~~For now WSL-local.~~ **RESOLVED 2026-07-07** — `ensure_shared_analytics_db()` Step 2b (landed 2026-07-06) reads `SUBAGENT_RUNS_DDL` hub-side and applies it to `postgres-main` on `fabrik apply`; the table is now **live** on vps1 `fabrik_analytics` (13 cols + 2 indexes, types match the module DDL). Was code-complete but un-applied until a one-shot provisioning run on 2026-07-07 (see CHANGELOG).
- **Rule pack update.** `.windsurf/rules/ai/00-ai-model-selection.md` gets `TASK_SUBAGENT_SELECTION.md` added to its selection MDs table — but only after the file has real data. Follow-up.
- **`pick_models` reader.** Upstream module work. My reply to fabrik-lib AI (below) proposes the doc format.
- **`/fabrik-spec-review`, `/fabrik-data-contract`, `/fabrik-plan-review`.** Skipped for speed. Schema comes from module DDL export (no negotiation); doc format is simple markdown; the whole thing is ~100 lines. Full pipeline discipline returns on the next non-trivial spec.

## Handoff

Skip the review skills. This is small enough to execute inline. When you approve, I:

1. Write a ~30-line runnable checklist (not a formal plan) to `docs/development/plans/2026-07-06-plan-1-subagent-runs-lean.md`.
2. On your `execute`, do the 4 changes above in one turn — spawn one subagent for the aggregator script, do the DDL apply + `daily_refresh.sh` edit inline, verify with a smoke test.
3. Ship.

Estimate: 45 minutes to green.
