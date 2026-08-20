# T07 — outcome tier: rework miner + fleet-health sweep + premature-stop

Depends: T06
Parallel: ⚡ (with T08)
Complexity: complex (pool coder permitted; the sweep's clean-worktree isolation reviewed native)
## Scope
The numbers ceremony cannot move, per the spec (docs/superpowers/specs/2026-08-16-kaizen-closed-loop-v2-design.md:139-148): rework from provenance trailers, the clean-worktree fleet sweep, and the premature-stop oracle (stop_block events). The sweep's cron rides the stamp-check pattern (scripts/sysadmin/weekly_catchup.sh:1-28).

## Touches
- scripts/sysadmin/kaizen_outcomes.py
- tests/test_kaizen_outcomes.py

## Context Files
- docs/superpowers/specs/2026-08-16-kaizen-closed-loop-v2-design.md
- CLAUDE.md
- scripts/sysadmin/weekly_catchup.sh
- scripts/sysadmin/kaizen_collect_v2.py



## Interfaces

Consumes: T06 `read_rows()` + `metric_registry` (registers its metrics WITH pairs:
rework_rate ⟂ review_rounds; fleet_health ⟂ sweep_coverage; premature_stop ⟂ stop_block_causes).
Produces:
- `rework_rate` — per repo: commits whose files are re-touched within `KAIZEN_REWORK_DAYS`
  (default 7) by a later commit whose subject matches fix-shape (`fix(`/`revert`/`hotfix`) —
  mined from `git log --format` + `--name-only` across `/opt/*` repos READ-ONLY; denominator
  printed with every rate; repos without trailers reported `—` with reason.
- `fleet_health_sweep` — `--sweep` mode: for each pilot project — the set is CONFIG, not heuristic guesswork:
  `KAIZEN_SWEEP_PROJECTS` (comma list, DEFAULT `fabrik` — the hub pilots alone); a listed
  project's test command detects as: `pyproject.toml`/`pytest.ini` present → `uv run pytest`
  if `.venv` exists, else compile-only; `package.json` with a `test` script → skipped in the
  pilot (node runtimes vary) and reported `—` with reason, create a CLEAN worktree from HEAD in a temp dir
  (NEVER the live tree), run install-less checks only (compile/pytest-if-venv-exists/
  final_gate --check where synced) under a per-project timeout (`KAIZEN_SWEEP_TIMEOUT_S`, default
  300); emit `fleet_health` events; report `swept n/46 — the rest —` with reasons (no venv, no
  tests, timeout). Wake-proof nightly cron entry AUTHORED but NOT installed here — T09 installs.
- `premature_stop_rate` — from `stop_block` events per session (T02's oracle, finally read).

## Steps

1. TDD: fixture git repo with a trailer'd commit + a fix-shaped re-touch → rework counted; a
   non-fix re-touch → not counted; fixture project tree → sweep runs in a temp worktree and the
   LIVE tree's mtime set is untouched (asserted); timeout → honest `—`. RUN RED first.
2. Implement (subprocess git only; every repo probe read-only; the sweep refuses to run in a dirty
   target — clean clones only per spec).
3. Register the three metrics with their pairs in T06's registry (the unpaired-refusal test
   already guards the shape).
4. Gate: `uv run pytest tests/test_kaizen_outcomes.py -q` green + a live `--sweep --only fabrik`
   run completing under timeout with the event emitted.

## Behavior Contract

- **Given** commits across /opt repos with provenance trailers, **When** the rework miner runs,
  **Then** rework rate = commits whose files are re-touched by a fix-shaped commit within N days,
  reported with its denominator (scripts/sysadmin/kaizen_outcomes.py).

Docs: metric rows ride T01's schema doc §Metrics; sweep runbook rides T09's kaizen.md pass.
Gate: `uv run pytest tests/test_kaizen_outcomes.py -q` + the live single-project sweep smoke.
