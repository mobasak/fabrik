# Subagent-Runs Telemetry — Lean Implementation Plan

**Status:** EXECUTED 2026-07-06 (commit `5e402a42`; final_gate lean green; Phase A ✅ Phase B ✅ Phase C ✅)
**Date:** 2026-07-06
**Design spec:** [docs/superpowers/specs/2026-07-06-subagent-runs-telemetry-design.md](../../superpowers/specs/2026-07-06-subagent-runs-telemetry-design.md) (DRAFT — lean version, review skipped by user direction for speed)
**Handoff:** `/fabrik-execute-plan docs/development/plans/2026-07-06-plan-1-subagent-runs-lean.md`

## What we already agreed

- Personal fleet, single operator. Postgres superuser is fine (matches `cost_ledger` convention at `fabrik/drivers/postgres.py:1006`).
- WSL-local postgres now; VPS `postgres-main` later. Same DSN shape.
- DDL imported verbatim from module — `python -c "from subagents import SUBAGENT_RUNS_DDL"` at `/opt/fabrik-lib/subagents/subagents/pg_ledger.py:35`.
- Value formula `success × quality / cost` (cost in denominator; mirrors `select.py:126` `rank_weight / price`).
- Skip per-project roles, skip rule-pack update, skip `pick_models` reader (all follow-ups).

## File Scope (owned paths)

```
scripts/kilo-benchmarks/rank_task_subagents.py                   [CREATE, Phase B]
scripts/kilo-benchmarks/apply_subagent_runs_ddl.sh               [CREATE, Phase A — one-shot DDL applier]
scripts/kilo-benchmarks/daily_refresh.sh                         [MODIFY, Phase B — 4 lines added]
scripts/kilo-benchmarks/tests/test_rank_task_subagents.py        [CREATE, Phase B]
docs/reference/kilo/TASK_SUBAGENT_SELECTION.md                   [CREATE by Phase B script on first run]
/opt/fabrik-lib/subagents/UPSTREAM_FEEDBACK.md                   [APPEND, Phase C — doc format for pick_models reader]
CHANGELOG.md                                                     [APPEND, Phase C]
INDEX.md                                                         [APPEND, Phase C — 2 new files]
```

## Global Constraints

- Explicit `git add <path>` only — never `-A`/`.`
- No new pip deps (aggregator uses stdlib `csv` + `subprocess` for `psql -A -F,`)
- Fail-soft: aggregator crash never wedges `daily_refresh.sh`
- DDL never authored locally — always imported from module (single source of truth)
- Env inject deferred: user adds `SUBAGENT_RUNS_DSN` + `SUBAGENT_PROJECT` to each project's `.env.local` manually when ready. Skipping the scaffolder change for now — user's "lean" direction.

## Phase A — Apply DDL to local postgres

**A.1.** Create `scripts/kilo-benchmarks/apply_subagent_runs_ddl.sh`:

```bash
#!/bin/bash
# AFTER-EDIT: none (one-shot DDL applier)
# Imports SUBAGENT_RUNS_DDL from the vendored subagents module + applies to local WSL postgres.
# Idempotent (CREATE TABLE IF NOT EXISTS).
set -euo pipefail
DDL=$(cd /opt/fabrik-lib/subagents && python -c "from subagents import SUBAGENT_RUNS_DDL; print(SUBAGENT_RUNS_DDL)")
# Ensure fabrik_analytics exists (cost_ledger already lives here).
psql -h localhost -U postgres -tAc "SELECT 1 FROM pg_database WHERE datname='fabrik_analytics'" | grep -q 1 \
  || psql -h localhost -U postgres -c "CREATE DATABASE fabrik_analytics"
echo "$DDL" | psql -h localhost -U postgres -d fabrik_analytics
echo "OK — subagent_runs applied to fabrik_analytics"
```

**Gate A.1:**
```bash
bash scripts/kilo-benchmarks/apply_subagent_runs_ddl.sh
psql -h localhost -U postgres -d fabrik_analytics -c "\d subagent_runs" | grep -qE "task_type|quality_score" \
  && echo "A gate OK" || { echo "table missing"; exit 1; }
```

## Phase B — Aggregator + wire daily_refresh

**B.1.** TDD: write `scripts/kilo-benchmarks/tests/test_rank_task_subagents.py` FIRST with a tmp-DB seeded fixture proving:
- Empty-pool → stub MD, exit 0
- ≥3 rows per (task, model) → correct value = `success × quality / cost` ranking
- <3 rows in a pair → excluded from output

**Gate B.1 (must FAIL RED first):**
```bash
cd scripts/kilo-benchmarks && python -m pytest tests/test_rank_task_subagents.py -x 2>&1 | tail -5
# Expected: 3 FAILED (module not found) — red for the right reason.
```

**B.2.** Implement `scripts/kilo-benchmarks/rank_task_subagents.py`. Pattern-clone `rank_coding_subagents.py` for `_atomic_write`, `_safe_md_id`, `_fmt_or_dash`. Header: `# AFTER-EDIT: scripts/kilo-benchmarks/tests/test_rank_task_subagents.py`. Query via `subprocess.run(["psql", "-h", "localhost", "-U", "postgres", "-d", "fabrik_analytics", "-A", "-F,", "--tuples-only", "-c", QUERY], …)`. Parse CSV with stdlib. Formula constant at top: `VALUE_FORMULA_COST_IN_DENOMINATOR = True`.

**Gate B.2:**
```bash
cd scripts/kilo-benchmarks && python -m pytest tests/test_rank_task_subagents.py -x 2>&1 | tail -5
# Expected: 3 passed
python scripts/kilo-benchmarks/rank_task_subagents.py
test -f docs/reference/kilo/TASK_SUBAGENT_SELECTION.md
head -1 docs/reference/kilo/TASK_SUBAGENT_SELECTION.md | grep -qE "^Last refresh: [0-9]{4}"
# On empty DB (initial state) expect: stub file with "No aggregated runs yet" line.
grep -q "No aggregated runs yet" docs/reference/kilo/TASK_SUBAGENT_SELECTION.md && echo "B gate OK — stub emitted on empty pool"
```

**B.3.** Wire `daily_refresh.sh` (insert after `:344` where `rank_coding_subagents` runs, before `:355` where `export_models_browser` runs):
```bash
  _step "rank_task_subagents" "$VENV_PY" "$KB/rank_task_subagents.py" \
    || echo "[daily_refresh] rank_task_subagents failed (non-fatal)"
```

**Gate B.3:**
```bash
bash -n scripts/kilo-benchmarks/daily_refresh.sh && echo "syntax OK"
grep -c "_step \"rank_task_subagents\"" scripts/kilo-benchmarks/daily_refresh.sh | awk '$1 == 1 { exit 0 } { exit 1 }' && echo "wired OK"
```

## Phase C — Upstream note + changelog + docs

**C.1.** Append to `/opt/fabrik-lib/subagents/UPSTREAM_FEEDBACK.md` (create if absent) with the exact `TASK_SUBAGENT_SELECTION.md` shape the aggregator emits, so a future `pick_models` reader knows the parse contract. Content per lean spec § "Ranking (in the aggregator)".

**C.2.** `CHANGELOG.md` under `## [Unreleased]`:
```
### Added — subagent-runs flywheel v1 (2026-07-06)
Lean 3-phase wiring: DDL applied to local fabrik_analytics, rank_task_subagents.py aggregator emits
TASK_SUBAGENT_SELECTION.md nightly via daily_refresh.sh. Env injection + per-project roles + rule pack
update deferred as follow-ups. UPSTREAM_FEEDBACK.md documents the doc format for pick_models reader.
```

**C.3.** `INDEX.md` — add rows for `apply_subagent_runs_ddl.sh`, `rank_task_subagents.py`, `TASK_SUBAGENT_SELECTION.md`.

**Gate C:**
```bash
grep -q "TASK_SUBAGENT_SELECTION" /opt/fabrik-lib/subagents/UPSTREAM_FEEDBACK.md
grep -q "subagent-runs flywheel v1" CHANGELOG.md
grep -q "TASK_SUBAGENT_SELECTION.md" INDEX.md
python scripts/final_gate.py --lean --json 2>&1 | grep -q '"status": "success"'
echo "C gate OK"
```

## Commit (single commit — small scope)

```bash
git add scripts/kilo-benchmarks/apply_subagent_runs_ddl.sh \
        scripts/kilo-benchmarks/rank_task_subagents.py \
        scripts/kilo-benchmarks/tests/test_rank_task_subagents.py \
        scripts/kilo-benchmarks/daily_refresh.sh \
        docs/reference/kilo/TASK_SUBAGENT_SELECTION.md \
        docs/superpowers/specs/2026-07-06-subagent-runs-telemetry-design.md \
        docs/development/plans/2026-07-06-plan-1-subagent-runs-lean.md \
        CHANGELOG.md INDEX.md
# UPSTREAM_FEEDBACK.md is at /opt/fabrik-lib/subagents/ — a SEPARATE repo. Committed there
# separately by the operator (or via a fabrik-lib sync utility) — do not attempt from this repo.
git commit -m "$(cat <<'EOF'
feat(kilo-benchmarks): subagent-runs flywheel v1 — lean 3-phase wiring

Agent-Role: primary
Agent-Phase: A+B+C
Agent-Context: DDL apply + rank_task_subagents.py aggregator + daily_refresh wire + upstream note. WSL-local for now; VPS postgres-main + env injection + per-project roles deferred as follow-ups per lean spec.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

## Success criteria

1. `psql -h localhost -U postgres -d fabrik_analytics -c "\d subagent_runs"` shows all 13 columns from `SUBAGENT_RUNS_DDL`.
2. `python scripts/kilo-benchmarks/rank_task_subagents.py` exits 0 on empty DB with stub MD emitted.
3. Seeding 3+ rows per (task, model) produces ranked table in `TASK_SUBAGENT_SELECTION.md` sorted by `value` desc.
4. `daily_refresh.sh` re-runs cleanly with the new `_step "rank_task_subagents"` line.
5. `python scripts/final_gate.py --lean --json` returns `"status": "success"`.

## Evidence

- `/opt/fabrik-lib/subagents/subagents/pg_ledger.py:35` — `SUBAGENT_RUNS_DDL` string source of truth.
- `/opt/fabrik-lib/subagents/subagents/__init__.py:21` — `SUBAGENT_RUNS_DDL` + `record_run` export.
- `/opt/fabrik-lib/subagents/subagents/select.py:58` — `_TABLE: dict[str, list[str]]` shape the emitted MD mirrors.
- `scripts/kilo-benchmarks/rank_coding_subagents.py:345` — `_atomic_write` cloned into the new ranker.
- `scripts/kilo-benchmarks/daily_refresh.sh:344,355` — insertion window.
- `src/fabrik/drivers/postgres.py:1006` — comment justifying "postgres superuser is fine for v1" convention.

## Self-audit

- Every "What we already agreed" item maps to a phase step. ✓
- No `TBD`/`TODO` placeholders. ✓
- Doc-sync triggers: new files → INDEX.md ✓; feature ship → CHANGELOG.md ✓; upstream fabrik-lib bug/enhancement note → UPSTREAM_FEEDBACK.md ✓.
- Fixed-point claim: skipped formal review-loop per user direction ("i need it fast to use"). Scope + DDL-from-module + zero external deps makes drift risk trivial.

## Residual unknowns

- **Env injection deferred.** User adds `SUBAGENT_RUNS_DSN=postgresql://postgres@localhost:5432/fabrik_analytics` + `SUBAGENT_PROJECT=<name>` to each project's `.env.local` manually. Automating via `deployer.inject_env` at `orchestrator/infrastructure.py:506` is a follow-up ticket when the personal-fleet convenience threshold hits.
- **VPS deploy.** Not this ticket. Extend `ensure_shared_analytics_db()` at `postgres.py:990` when ready to push table to `postgres-main`.
- **Rule pack update.** `.windsurf/rules/ai/00-ai-model-selection.md` gets `TASK_SUBAGENT_SELECTION.md` as a 6th selection MD row once the file has real data (post-first-nightly-with-real-runs).
- **`pick_models` reader.** Upstream module work — my UPSTREAM_FEEDBACK.md note in Phase C documents the format they build against.
