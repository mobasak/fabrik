# Terminal-Bench runner — home-bench Linux-sysadmin capability into kilo-benchmarks

**Status:** EXECUTED 2026-07-13
**Executed:** 2026-07-13 — Phases A (`f7a335be`), B (`b5e07c53`), C (`5dc86e25`), format (`231d77da`). Fresh Tier-2 gate success; 30 tests green; whole-plan review no-op; all 8 behaviors covered; OpenRouter routing + writeback live-verified end-to-end.
**Date:** 2026-07-13
**Converged:** 2026-07-13 (`/fabrik-plan-review` — 2 passes to an edit-free md5-verified no-op; grounded all 4 `microbench_coding.py` path:lines + all 9 NULL-ranking sites' per-site classification, live-verified the OpenRouter `/api/v1/credits` cost-cap endpoint + surfaced the ~$0.19 balance precondition, corrected the pyproject Evidence quote; md5 `f4537bdf0a818879123244c6fce65b77`)
**Design spec:** [docs/superpowers/specs/2026-07-13-terminal-bench-runner-design.md](../../superpowers/specs/2026-07-13-terminal-bench-runner-design.md) (CONVERGED, md5 `700978dd72c3076f0c958aeef9ef4458`)
**Scaffold type:** fabrik hub itself (kilo-benchmarks dev/hub CLI tool — not a deployed service)
**Author:** primary (this session)

## Goal

Give kilo-benchmarks the ability to **generate** Terminal-Bench (sysadmin-capability) scores itself instead of only scraping the public leaderboard. Build `microbench_terminal.py` — a thin adapter that runs the official Terminal-Bench harness against OpenRouter-routed models and writes each model's task-resolution pass-rate to `agents.tbench_accuracy`, mirroring how `microbench_coding.py` runs EvalPlus and writes `humaneval_score`. First real use: bench the three unbenched sysadmin candidates (`minimax/minimax-m3`, `z-ai/glm-5.2`, `deepseek/deepseek-v4-pro`) so the operator's OpenRouter-sysadmin-agent decision rests on data, not a guess.

## Global Constraints

- **Python 3.11+**, project venv `/opt/fabrik/.venv/bin/python`. DB: `/opt/fabrik/scripts/kilo-benchmarks/kilo_agents.db` (SQLite).
- **OpenRouter is the only LLM gateway** — the harness routes via LiteLLM `openrouter/<id>` strings + `OPENROUTER_API_KEY` (from `.env` via `load_dotenv()`). `terminus-2` agent + `--model openrouter/<id>` pins ALL model traffic through OpenRouter. No direct vendor SDK.
- **Cost-budget mandate** (`core/cost-budget.md`): this is an unattended paid-LLM loop → every real run MUST be cost-bounded. Enforced by a pre/post OpenRouter balance-delta check per model + a task-count cap (`--task-filter`) + a mandatory `--dry-run` estimate.
- **Shell-out safety**: model_id comes from the DB and is interpolated into a subprocess argv → MUST pass a fail-closed validator (mirror `microbench_coding.py:48 _validate_model_id`) before use. Never `shell=True`.
- **Logs = unbuffered stdout only** (`core/55-observability.md` / 12F-XI). The runner `print()`s progress + a JSON summary to stdout; **never writes or rotates a logfile.**
- **Dev/test parity** (12F-X): tests use the real SQLite `agents.db` schema via a temp-copy fixture — no substitute backing store. (SQLite IS the catalog's real store here; not a Postgres stand-in.)
- **No migration**: `agents.tbench_accuracy REAL` already exists — the runner only writes it.
- **Deps edit is authorized by THIS plan** (CLAUDE.md deps rule): add `terminal-bench` to `pyproject.toml:12 dependencies`. No other manifest edits.
- **On-demand only** — NOT wired into `daily_refresh.sh` (a full core-set run is minutes + dollars per model). Operator-triggered.
- **Naming**: snake_case Python; `microbench_terminal.py` matches the `microbench_*` sibling convention.
- **Script coupling header**: `# AFTER-EDIT: <files | none>` in first ~25 lines of the new script (gate-enforced).

## Context Ledger

| Source | What binds | Grounded ref |
|---|---|---|
| `.windsurf/rules/core/10-python.md` (ACTIVE) | Python/typing/env-handling; `os.getenv` + `load_dotenv`, no secrets in code | `.windsurf/rules/core/10-python.md` |
| `.windsurf/rules/core/30-ops.md` (ACTIVE) | Docker standards — the harness runs its own per-task containers on the local daemon | `.windsurf/rules/core/30-ops.md` |
| `.windsurf/rules/core/45-testing-strategy.md` (ACTIVE) | Behavior Contract — test per behavior, TDD the risky path | `.windsurf/rules/core/45-testing-strategy.md` |
| `.windsurf/rules/core/55-observability.md` (ACTIVE) | Structured logs **to stdout only, no logfiles** | `.windsurf/rules/core/55-observability.md` |
| `.windsurf/rules/core/cost-budget.md` (ACTIVE) | Cost cap mandatory for any paid-LLM loop | `.windsurf/rules/core/cost-budget.md` |
| `.windsurf/rules/core/62-using-subagents.md` (ACTIVE) | fanout pool-default for gradeable fan-out; native for authoritative/decide | `.windsurf/rules/core/62-using-subagents.md` |
| `fabrik-lib/README.md` — vendor consult | **No module runs terminal-agent Docker evals.** `subagents/` = OpenRouter parallel-subagent runtime (used by microbench_coding for dispatch, but TB's own `--n-concurrent` parallelizes tasks; outer per-model loop stays serial to bound Docker load). `claude-evaluator/` = LLM-as-judge via Claude Code (wrong tool — not agentic Docker eval, routes via Claude Code not the model-under-test). **VENDOR the external `terminal-bench` pip package** per spec verdict. | `/opt/fabrik-lib/README.md` (checked this session) |
| `terminal-bench` pip pkg (VENDOR, external) | The `tb`/`harbor` CLI harness (Apache-2.0) runs Docker tasks + LiteLLM routing + programmatic scorers | spec External-deps table; `github.com/laude-institute/terminal-bench` + `github.com/laude-institute/harbor` (live 2026-07-13) |
| `microbench_coding.py` (precedent — the pattern to mirror) | argparse `--models`/`--cost-cap`/`--dry-run`; fail-closed shell-metachar validators; `subprocess.run`; parse results JSON; `UPDATE agents SET <score>, last_verified WHERE id`; freshness gate | `scripts/kilo-benchmarks/microbench_coding.py:48,57,94,165,216,265` (read this session) |
| `pyproject.toml` (deps — authorized) | add `terminal-bench` alongside `evalplus>=0.3.0` | `/opt/fabrik/pyproject.toml:12` |
| `agents.db` schema | `tbench_accuracy REAL` exists — write-only, no migration | `sqlite3 kilo_agents.db "pragma_table_info(agents)"` (verified) |
| NULL-ranking fix sites (Phase C) | the `COALESCE(tbench,0)`/`none_to_zero(tbench)` **sort** sites bury unbenched models; the `>=70` hard-min filters + composite score are NOT bugs | `compute_assignments.py:29,60,87,98` · `category_selector.py:119` · `llm_selector.py:183` (sort — fix) · `compute_assignments.py:26,57` · `pre_filter.py:136` (filter/composite — leave) |
| **Data contract** | N/A — writes an existing internal catalog column; no user-facing field, no new entity | spec § Shape/infra |
| **UI design** | N/A — hub-side CLI tool, no GUI | spec § Handoff |
| `specs/services` `shape:` | N/A — not a deployed service; no `shape:` flags flip | spec § Shape/infra |

## Behavior Contract (whole plan)

Risk-ordered; TDD the top two:

1. **Shell-out injection is blocked** — a model_id containing shell metachars / `..` / leading `-` is rejected by the validator before it reaches `subprocess.run`. *(highest risk: we shell out with a DB-sourced value)*
2. **Cost cap aborts a runaway** — if a model's OpenRouter spend-delta exceeds `--cost-cap`, the runner stops that model and does NOT proceed to the next task/model unbounded. *(paid-LLM loop safety)*
3. **Pass-rate parse is correct** — given a real `tb run` output dir, the parser returns `resolved/total` as a 0–100 float matching the harness's own reported score.
4. **DB writeback** — a successful bench writes `tbench_accuracy` (0–100) + `last_verified` to the right `agents.id`, and only that column (explicit UPDATE column list).
5. **`--dry-run` calls no model** — prints the dispatch plan + estimated cost/time and makes zero OpenRouter calls.
6. **Cohort selection** — default cohort = `via_openrouter=1 AND status='active' AND has_tools=1`; `--models` overrides with an explicit list.
7. **Freshness gate** — a row benched within the TTL is skipped unless `--force` (mirror `microbench_coding.is_fresh`).
8. **NULL-ranking fix (Phase C)** — after the fix, a tbench-ordered ranking places an unbenched (NULL) model as *unranked/last-explicit*, NOT tied with a real 0-scorer; the `>=70` hard-min filters and the composite score are unchanged.

Trivia skipped: argparse `--help`, docstring format, print wording.

---

## Phase A — Deps + harness smoke-test + pin CLI/dataset-version + ground output schema — ✅ EXECUTED 2026-07-13

**GROUNDED CONSTANTS (Phase A output for Phase B):**
- `TB_CLI = "tb"` (terminal-bench 0.2.18; no `harbor` binary — `tb run` is the harness entry).
- `TB_DATASET = "terminal-bench-core==0.1.1"` — passed as `tb run -d terminal-bench-core==0.1.1` (the `-d name==version` form, NOT the spec's assumed `--dataset-name`/`--dataset-version`).
- **Agent** `terminus-2` confirmed valid (enum: `oracle|naive|terminus|terminus-1|terminus-2|mini-swe-agent|opencode|aider|codex|cursor|gemini|goose`).
- **Real `tb run` flags** (corrected from spec's assumptions): `-m openrouter/<id>` · `-a terminus-2` · `-d name==version` · `--task-id`/`-t <glob>` OR `--n-tasks <N>` (NOT `--task-filter`) · `--n-attempts <N>` (= trials) · `--output-path <dir>` · `--no-upload-results` · `--cleanup` · `--n-concurrent <N>` (default 4).
- `TB_OUTPUT_SCHEMA`: top-level `<output-path>/<run-id>/results.json` → **`accuracy` (0.0–1.0) is the pass-rate** → `tbench_accuracy = accuracy * 100`; also `n_resolved`, `n_unresolved`, `resolved_ids`, `unresolved_ids`, per-trial `results[].is_resolved`. **⚠️ `total_input_tokens`/`total_output_tokens` are `0`** even on a real model run (terminus-2 doesn't populate them) → **cost MUST be measured via the OpenRouter balance-delta, NOT token counts** (validates the plan's cost-cap choice).
- **OpenRouter routing CONFIRMED end-to-end**: `tb run -a terminus-2 -m openrouter/deepseek/deepseek-v3.2-exp` consumed OR credit (`$10.19 → $10.1786`, ~$0.011 for one task) — routing works, not just doc-grounded.

**Deliverable:** `terminal-bench` installed; the exact CLI (`tb` vs `harbor`), dataset-version, and output-JSON schema are pinned as grounded constants for Phase B.

**Files:**
- MODIFY `pyproject.toml` (add `terminal-bench` to `dependencies` — authorized).
- CREATE `scripts/kilo-benchmarks/cache/tb_smoke_output/` (a throwaway run dir — gitignored via `cache/`).
- No production code yet — this phase produces **grounded constants** recorded in the plan's Evidence + a short `docs/reference/terminal-bench-runner.md` note (created Phase C; Phase A appends the raw findings to the plan Evidence).

### Interfaces

**Produces** (grounded facts Phase B consumes):
- `TB_CLI: str` — `"tb"` or `"harbor"` (whichever `run --model openrouter/...` the installed pkg exposes).
- `TB_DATASET_NAME = "terminal-bench-core"`, `TB_DATASET_VERSION: str` — the pinned newest stable version.
- `TB_OUTPUT_SCHEMA` — the real JSON path + keys the harness writes for `resolved`/`total`/pass-rate (for Phase B's parser).

### Steps

**A.1 — Authorize + install the dep.**
1. Edit `pyproject.toml:12` — add `"terminal-bench",` to `dependencies` (below `evalplus>=0.3.0`).
2. Run: `/opt/fabrik/.venv/bin/pip install terminal-bench 2>&1 | tail -5`. **Expected:** installs; `pip show terminal-bench` returns a version.
3. Gate: `/opt/fabrik/.venv/bin/pip show terminal-bench | grep -i version`. **Expected:** a version string.

**A.2 — Preflight the toolchain (probe, don't assume).**
1. Run: `docker --version && docker ps >/dev/null 2>&1 && echo docker-ok; uv --version; grep -q '^OPENROUTER_API_KEY=' /opt/fabrik/.env && echo key-ok`. **Expected:** `docker-ok` + a uv version + `key-ok`. (Verified this session: Docker 29.1.3, uv 0.11.16, key present — re-probe at execution in case env drifted.)

**A.3 — Pin the CLI + dataset version.**
1. Run: `tb --help 2>&1 | head -20; harbor --help 2>&1 | head -20`. Record which binary exists and exposes `run`.
2. Run: `<cli> datasets list 2>&1 | head` (or read the harness dataset registry). Record available `terminal-bench-core` versions; pin the newest stable → `TB_DATASET_VERSION`.
3. Record `TB_CLI` + `TB_DATASET_VERSION` in the plan Evidence (append the real command output).

**A.4 — Smoke-run one task to ground the output schema (highest-value grounding).**
1. Run a single cheap task against a cheap model, cost-bounded by task count:
   `<cli> run --agent terminus-2 --model openrouter/deepseek/deepseek-v3.2-exp --dataset-name terminal-bench-core --dataset-version <pinned> --n-concurrent 1 --task-filter <one-task-id> --output-path scripts/kilo-benchmarks/cache/tb_smoke_output` (task-id from `<cli> tasks list`).
   **Expected:** completes; writes a results file under the output path.
2. Run: `find scripts/kilo-benchmarks/cache/tb_smoke_output -name '*.json' | head; cat <the-results-json> | python3 -m json.tool | head -40`. **Capture the real JSON shape** → `TB_OUTPUT_SCHEMA` (the exact keys for resolved/total/pass-rate). Record in Evidence.

**A.5 — Phase gate + review + commit.**
1. Gate: `python scripts/final_gate.py --check --json | jq '.status'`. **Expected:** `"success"` (baseline: pre-existing reds owned by siblings are not yours).
2. `python scripts/enforcement/check_doc_sync.py` — resolve any WARN for files touched this phase (pyproject change → note in CHANGELOG at Phase C; A adds no user-facing doc trigger beyond the dep).
3. **`/fabrik-review` — BLOCKING, looped to no-op** on Phase A's diff (pyproject + the grounded constants). Pool-default breadth via `fanout("review", …, mode="read_only", allow_ungrounded=True, project="tbench-plan1")` + `set_quality` back-fill; **native `fabrik-reviewer` Opus** for the deps change (supply-chain surface). Iterate to zero CONFIRMED/PLAUSIBLE.
4. Commit (explicit paths + provenance trailers): `pyproject.toml` + the plan file (flip `Status: DRAFT → IN-PROGRESS`, mark `Phase A ✅ EXECUTED <date> (<commit>)`). Message `feat(kilo-benchmarks): Phase A — terminal-bench dep + harness grounding`, `Agent-Role: orchestrator`, `Agent-Phase: A`.

---

## Phase B — `microbench_terminal.py` (cohort → dispatch → parse → writeback + cost-cap + dry-run) — ✅ EXECUTED 2026-07-13

**Execution notes:** 24 behavior tests green. Live-verified end-to-end (deepseek-v4-pro, 2 tasks, $0.2051 < $2 cap → wrote tbench then reset the 2-task artifact to NULL to keep the catalog honest). **Two implementation-discovered corrections:** (1) freshness keys on `tbench_accuracy` presence, NOT `last_verified` — the latter is overloaded (price scrapers stamp it on 305 never-tbench'd OR models, which would wrongly skip them); (2) `openrouter_balance` failures are graceful (core/58-resilience) — a completed paid-for bench's score is never lost to a credits-API blip (regression test `test_score_survives_balance_check_failure`).

**Deliverable:** a runnable, cost-capped, injection-safe adapter that benches a cohort and writes `tbench_accuracy`.

**Files:**
- CREATE `scripts/kilo-benchmarks/microbench_terminal.py` — one responsibility: bench a cohort against Terminal-Bench, write scores.
- CREATE `scripts/kilo-benchmarks/tests/test_microbench_terminal.py` — behaviors 1–7.

### Interfaces

**Consumes:** `TB_CLI`, `TB_DATASET_NAME`, `TB_DATASET_VERSION`, `TB_OUTPUT_SCHEMA` (Phase A); `agents.db`; `OPENROUTER_API_KEY`.
**Produces:**
- `_validate_model_id(model_id: str) -> str` — fail-closed on shell metachars/`..`/leading `-` (mirror `microbench_coding.py:48`).
- `select_cohort(conn, models: list[str] | None) -> list[str]` — the default `via_openrouter=1 AND status='active' AND has_tools=1` query, or the `--models` override.
- `run_one(cli, model_id, dataset_version, n_concurrent, task_filter, out_dir) -> pathlib.Path` — subprocess dispatch (argv list, never `shell=True`), returns the results dir.
- `parse_tbench_output(results_dir: pathlib.Path) -> float` — per `TB_OUTPUT_SCHEMA`, returns pass-rate × 100 (0–100).
- `write_tbench_score(conn, model_id: str, score: float) -> None` — `UPDATE agents SET tbench_accuracy = ?, last_verified = ? WHERE id = ?` (explicit column list, mirror `microbench_coding.py:216`).
- `openrouter_balance() -> float` + cost-cap: read balance before/after each model via `GET https://openrouter.ai/api/v1/credits` (or `/auth/key`); abort the model when `spent >= cost_cap`.
- `is_fresh(conn, model_id, ttl_days) -> bool` (mirror `microbench_coding.py`), skipped by `--force`.
- `main(argv) -> int` — flags: `--models`, `--cost-cap` (default e.g. 5.0), `--trials` (default 1), `--task-filter`, `--n-concurrent` (default from A.4 measurement), `--force`, `--dry-run`.

### Steps

**B.1 — TDD the injection guard (behavior 1 — highest risk).**
1. Add `test_microbench_terminal.py::test_validate_model_id_rejects_metachars` — parametrize `"m; rm -rf /"`, `"../etc"`, `"-x"`, `"a/b\nc"` → each raises; a clean `"minimax/minimax-m3"` passes.
2. Run → **RED** (module missing). Confirm RED for the right reason.
3. Implement `_validate_model_id` mirroring `microbench_coding.py:48` (allowlist regex, fail-closed).
4. Run → **GREEN**.

**B.2 — TDD the cost-cap abort (behavior 2).**
1. Add `test_cost_cap_aborts_when_spend_exceeds` — monkeypatch `openrouter_balance` to simulate a spend-delta over `cost_cap`; assert the loop stops the model and does not dispatch further tasks for it.
2. Run → RED. 3. Implement the balance-delta check around `run_one`. 4. → GREEN.

**B.3 — TDD parse + writeback (behaviors 3, 4).**
1. Add `test_parse_tbench_output` using a fixture JSON copied from Phase A's real smoke output (`tests/fixtures/tb_output.json`) → asserts the exact pass-rate.
2. Add `test_write_tbench_score_updates_only_that_column` — temp-copy `agents.db`, write a score, assert `tbench_accuracy` + `last_verified` set on the right id and no other column changed.
3. Run → RED. 4. Implement `parse_tbench_output` (per `TB_OUTPUT_SCHEMA`) + `write_tbench_score`. 5. → GREEN.

**B.4 — cohort + dry-run + freshness (behaviors 5, 6, 7).**
1. Add tests: `test_default_cohort_query` (tool-capable OR models), `test_models_flag_overrides`, `test_dry_run_calls_no_model` (assert `run_one` never invoked under `--dry-run`), `test_is_fresh_skips_recent`.
2. Run → RED. 3. Implement `select_cohort`, `is_fresh`, and `main()` argparse + the `--dry-run` estimate path. 4. → GREEN.

**B.5 — Live one-model verification (real, cost-capped).**
1. Run: `python scripts/kilo-benchmarks/microbench_terminal.py --models deepseek/deepseek-v3.2-exp --task-filter <small-subset> --cost-cap 2.0 --dry-run`. **Expected:** prints plan + estimate, zero OR calls.
2. Run it for real (small subset, capped): drop `--dry-run`. **Expected:** completes, prints a pass-rate, `sqlite3 kilo_agents.db "SELECT tbench_accuracy,last_verified FROM agents WHERE id='deepseek/deepseek-v3.2-exp'"` shows the written score + today's date.

**B.6 — Doc updates.**
1. `CHANGELOG.md` — `### Added — microbench_terminal.py: home-run Terminal-Bench scoring for OpenRouter models (2026-07-13)`.
2. `INDEX.md` — add the new script + test rows.

**B.7 — Phase gate + review + commit.**
1. `python scripts/final_gate.py --check --json | jq '.status'` → `"success"`.
2. `python -m pytest scripts/kilo-benchmarks/tests/test_microbench_terminal.py -v` → all pass.
3. `python scripts/enforcement/check_doc_sync.py` → no WARN for Phase B's diff.
4. **`/fabrik-review` — BLOCKING, looped to no-op** on the runner + tests. Pool-default breadth + **native `fabrik-reviewer` Opus** for the subprocess/shell-out + cost-cap logic (injection + unbounded-spend surface). Prove-before-fix, iterate to zero CONFIRMED/PLAUSIBLE.
5. Commit — `Agent-Role: orchestrator`, `Agent-Phase: B`; stage the plan-file `Phase B ✅ EXECUTED` marker.

---

## Phase C — NULL-ranking per-site fix + docs convergence — ✅ EXECUTED 2026-07-13

**Execution notes:** Per-site adjudication (from reading `compute_assignments.py` fully) refined the plan's classification: **:29, :60 operate on already-`>=70`-filtered pools** (no NULL reaches them) — fixed for consistency but behavior-neutral; **:87, :98 are the real bugs** (the testing-role pool is only `has_tools AND is_agentic`-filtered, so NULL reached the sort and tied with real 0). SQL fix = drop `COALESCE(...,0)` → `tbench_accuracy DESC` (SQLite sorts NULL last, verified empirically). Extracted `_null_last`/`filter_ge70`/`rank_testing_pool` module-level helpers for testability. `>=70` filters (`:26,:57`) + `pre_filter.py:136` composite left unchanged (NULL→0 correct there), guarded by `test_hard_min_filter_still_excludes_unbenched`. `docs/README.md` didn't exist → the reference doc was indexed in `INDEX.md` (the canonical file index) instead. 6 null-ranking tests + 24 runner tests = 30 green.

**Deliverable:** tbench-ordered ranking no longer buries unbenched models as tied-with-0; hard-min filters + composite score left correct; docs converged.

**Files:**
- MODIFY `scripts/kilo-benchmarks/category_selector.py` (line 119 sort clause).
- MODIFY `scripts/kilo-benchmarks/llm_selector.py` (line 183 sort clause).
- MODIFY `scripts/kilo-benchmarks/compute_assignments.py` (sort sites 29,60,87,98 — NOT the `>=70` filters at 26,57).
- CREATE `scripts/kilo-benchmarks/tests/test_tbench_null_ranking.py`.
- CREATE `docs/reference/terminal-bench-runner.md` (usage + the "home score ≠ leaderboard score" caveat + the pinned CLI/dataset-version).

### Interfaces

**Consumes:** the 9 grounded sites (Context Ledger). **Produces:** ranking that sorts NULL-tbench as unranked-last-explicit (e.g. `WHERE tbench_accuracy IS NOT NULL` before a tbench-ordered pick, or `ORDER BY tbench_accuracy DESC NULLS LAST` semantics in SQLite via `tbench_accuracy IS NULL, tbench_accuracy DESC`), leaving `>=70` hard-mins and the `pre_filter.py:136` composite untouched.

### Steps

**C.1 — Adjudicate each of the 9 sites (audit, don't blanket-replace).**
1. Run: `grep -rnE "COALESCE\([a-z._]*tbench_accuracy[^)]*,\s*0\)|none_to_zero\([^)]*tbench" scripts/kilo-benchmarks/*.py`. Confirm the 9 sites match the Context Ledger. Classify each: **SORT (fix)** vs **HARD-MIN/COMPOSITE (leave)**. Record the classification in the plan Evidence.

**C.2 — TDD the sort fix (behavior 8).**
1. Add `test_tbench_null_ranking.py::test_unbenched_sorts_after_real_zero` — seed a temp `agents.db` with one model `tbench=0.0` (real benched zero) and one `tbench=NULL` (unbenched); assert the ranking puts the NULL model *after* the real-0 model (unranked-last), not tied.
2. Add `test_hard_min_filter_still_excludes_null` — assert an unbenched model is still excluded from the `>=70` pool (that behavior is unchanged/correct).
3. Run → RED (current COALESCE→0 ties them). Confirm RED.
4. Fix ONLY the sort sites: `category_selector.py:119`, `llm_selector.py:183`, `compute_assignments.py:29,60,87,98` → NULLS-LAST semantics. Leave `compute_assignments.py:26,57` (`>=70` filter) and `pre_filter.py:136` (composite) as-is.
5. Run → GREEN.

**C.3 — Docs (per Doc Sync Matrix).**
1. CREATE `docs/reference/terminal-bench-runner.md` — how to run, the pinned `TB_CLI`/`TB_DATASET_VERSION`, cost-cap usage, and the **"home score ≠ public leaderboard score"** caveat (different harness runs).
2. `CHANGELOG.md` — `### Fixed — tbench NULL-ranking: unbenched models no longer tie with real 0-scorers in selection sorts (2026-07-13)`.
3. `docs/README.md` (docs index) — add the new reference doc row.

**C.4 — Final gate + full-plan review + docs convergence.**
1. `python scripts/final_gate.py --json | jq '.status'` (Tier 2, full) → `"success"` (baseline attribution per Phase A).
2. `python -m pytest scripts/kilo-benchmarks/tests/test_tbench_null_ranking.py scripts/kilo-benchmarks/tests/test_microbench_terminal.py -v` → all pass.
3. `python scripts/enforcement/check_convergence.py` → success. `python scripts/enforcement/check_subagent_flywheel.py` → no WARN (all pool review dispatches recorded).
4. **`/fabrik-review` — BLOCKING, looped to no-op** on Phase C's diff AND the whole-plan cumulative diff.
5. **`/fabrik-docs-review`** — converge `CHANGELOG.md` + `INDEX.md` + `docs/reference/terminal-bench-runner.md` + `docs/README.md` to a truthful fixed point.
6. Commit — `Agent-Role: orchestrator`, `Agent-Phase: C`; stage the plan-file `Phase C ✅ EXECUTED` + flip `Status: IN-PROGRESS → EXECUTED <date>`.

---

## Subagent strategy

| Fan-out | Where | Recipe | Records |
|---|---|---|---|
| `/fabrik-review` breadth finders | A.5.3 / B.7.4 / C.4.4 | `fanout("review", units=[dims], mode="read_only", allow_ungrounded=True, project="tbench-plan1")` + `set_quality` back-fill | `subagent_runs` |
| Native Opus review | A.5.3 (deps/supply-chain), B.7.4 (subprocess/shell-out/cost-cap) | `Agent(subagent_type="fabrik-reviewer", model="opus")` — decide/merge you own | none (native) |
| Behavior-test authoring | B.1–B.4, C.2 | `fanout("code", units=[test_specs], mode="write", owned_paths=[disjoint], project="tbench-plan1")`; you `git apply` survivors + re-run gate | `subagent_runs` |
| Docs reconciliation | C.4.5 (`/fabrik-docs-review`) | `fanout("docs", units=[per-file], mode="read_only")` + `set_quality` | `subagent_runs` |

**Parallelism:** A→B strictly sequential (B needs A's pinned CLI + output schema). **C is independent of B** (different files: selectors vs the new runner) — C MAY run in parallel with B after A, if the executor holds a scope lock over both file sets. Default: A→B→C sequential (simpler; C's value is realized once B produces scores anyway).

## File Scope (owned paths)

- MODIFY `pyproject.toml` (add `terminal-bench` to dependencies — **serialization point**: shared with any other in-flight plan touching deps; check lock)
- CREATE `scripts/kilo-benchmarks/microbench_terminal.py`
- CREATE `scripts/kilo-benchmarks/tests/test_microbench_terminal.py`
- CREATE `scripts/kilo-benchmarks/tests/test_tbench_null_ranking.py`
- CREATE `scripts/kilo-benchmarks/tests/fixtures/tb_output.json`
- MODIFY `scripts/kilo-benchmarks/category_selector.py` (line 119 only)
- MODIFY `scripts/kilo-benchmarks/llm_selector.py` (line 183 only)
- MODIFY `scripts/kilo-benchmarks/compute_assignments.py` (sort sites 29,60,87,98 only)
- MODIFY `scripts/kilo-benchmarks/kilo_agents.db` (writes `tbench_accuracy` for benched rows)
- MODIFY `scripts/kilo-benchmarks/cache/**` (gitignored throwaway run dirs)
- CREATE `docs/reference/terminal-bench-runner.md`
- MODIFY `CHANGELOG.md`, `INDEX.md`, `docs/README.md`
- MODIFY `docs/development/plans/2026-07-13-plan-1-terminal-bench-runner.md` (Status + phase markers)

**Disjoint from the WaveSpeed plan** (`2026-07-12-plan-1-wavespeed-integration.md`): that plan owns `scrape_wavespeed_catalog.py`/`add_via_wavespeed_column.py`/`export_models_browser.py`/`models_browser.html`/`seed_specialty_catalog.py`/`daily_refresh.sh`; this one owns `microbench_terminal.py` + the 3 selector files + `pyproject.toml`. Only `kilo_agents.db` + `CHANGELOG.md`/`INDEX.md` overlap — both are append/row-level, flagged as serialization points (don't run the two plans' DB-writing phases literally concurrently).

## Evidence

### Phase A — grounded in

- `pyproject.toml:12` `dependencies = [ "click>=8.1.0", "evalplus>=0.3.0", "fastapi>=0.115.0", "httpx>=0.25.0", "python-dotenv>=1.0.0", … ]` (read this session — the insertion point; `terminal-bench` is added to this list, and `httpx` is already present for the OpenRouter balance calls).
- Live env probe: `Docker version 29.1.3` · `uv 0.11.16` · `OPENROUTER_API_KEY` present in `.env`.
- terminal-bench: `pip install terminal-bench` → `tb` CLI, Apache-2.0, Docker+uv deps ([github.com/laude-institute/terminal-bench](https://github.com/laude-institute/terminal-bench), live 2026-07-13).
- OpenRouter routing: LiteLLM `openrouter/<provider>/<model>` + `OPENROUTER_API_KEY` ([docs.litellm.ai/docs/providers/openrouter](https://docs.litellm.ai/docs/providers/openrouter), re-verified 2026-07-13: "supports ALL OpenRouter models").
- Harbor `terminus-2` default agent + `harbor run --model "openrouter/..."` example ([github.com/laude-institute/harbor](https://github.com/laude-institute/harbor)).

### Phase B — grounded in

- Adapter pattern: `microbench_coding.py:48` `_validate_model_id` (shell-metachar fail-closed) · `:94` `build_units` · `:165` `parse_eval_results` · `:216` `write_scores` (`UPDATE agents SET … WHERE id`, explicit column list) · `:265` argparse `--models`/`--cost-cap`/`--dry-run` — all read this session.
  ```
  216:def write_scores(conn, model_id, scores):
  237:    "UPDATE agents SET humaneval_score = ?, coding_score = ?, last_verified = ? WHERE id = ?"
  ```
- Column exists: `sqlite3 kilo_agents.db "pragma_table_info(agents)"` → `tbench_accuracy|REAL`.

### Phase C — grounded in

- The 9 NULL-ranking sites (verbatim grep output this session):
  ```
  compute_assignments.py:26,57  none_to_zero(...tbench...) >= 70.0     ← HARD-MIN (leave)
  compute_assignments.py:29,60,87,98  sort key none_to_zero(tbench)    ← SORT (fix)
  category_selector.py:119  "COALESCE(a.tbench_accuracy, 0) DESC"      ← SORT (fix)
  llm_selector.py:183  "COALESCE(tbench_accuracy, 0) DESC, "           ← SORT (fix)
  pre_filter.py:136  COALESCE(tbench_accuracy,0)/100.0 + ...           ← COMPOSITE (leave)
  ```

## Self-audit

### Grounding passes

- Pass 1 (this turn, solo). Read: spec (full), `select_rules.py` ACTIVE packs, `microbench_coding.py` (symbols at :48/:94/:165/:216/:265), all 9 tbench-ranking sites (4 files), `pyproject.toml:12`, agents.db schema. Live re-verified: terminal-bench GitHub + LiteLLM OpenRouter docs + Harbor. Env probe: Docker/uv/key.
- **Finding — spec sharpened**: the spec said "fix the COALESCE(tbench,0) NULL-ranking bug" as one thing; grounding shows it's **9 sites, only 6 are the bug** (the `>=70` hard-min filters + the composite score correctly treat NULL as 0). Plan Phase C adjudicates per-site + tests that the filters stay unchanged — avoids breaking the assignment pool.
- **Finding — cost-cap mechanism named**: microbench_coding caps via the pool's `max_cost_usd`; our runner shells out to a harness we don't control the inner calls of, so the cap is enforced via OpenRouter balance-delta (`/api/v1/credits`) + a task-count bound. Named in Phase B, not hand-waved.

### (a) Coverage — every "What we already agreed" → a phase

- `microbench_terminal.py` (cohort/dispatch/parse/writeback) → Phase B. Deps + harness grounding → Phase A. NULL-ranking fix → Phase C. Cost-cap → Phase B (balance-delta). On-demand-not-daily → Global Constraints (not added to daily_refresh). No-migration → confirmed (column exists). OpenRouter-only → Global Constraints + `terminus-2`+`openrouter/` pin. First-use (bench m3/glm-5.2/deepseek-v4-pro) → enabled by B.5's `--models` path (operator runs post-merge).

### (b) Cross-phase signature consistency

- `TB_CLI`/`TB_DATASET_VERSION`/`TB_OUTPUT_SCHEMA` — Phase A Produces → Phase B Consumes. Names match.
- `_validate_model_id`, `parse_tbench_output`, `write_tbench_score`, `select_cohort` — Phase B Produces, used within B. Consistent.
- The 9 ranking sites — Context Ledger names = Phase C Interfaces = Evidence grep. Consistent.

Fixed-point claim: DRAFT is fully grounded (every path:line read, every URL re-verified, the spec's one fuzzy item sharpened into a per-site plan). Convergence is `/fabrik-plan-review`'s job.

## Residual unknowns

### Resolved during drafting

1. OpenRouter routing works → yes (LiteLLM, re-verified). 2. Docker/uv/key present → yes (probed). 3. No migration → confirmed. 4. NULL-ranking scope → sharpened to 6 sort sites (not the filters). 5. Adapter pattern → `microbench_coding.py` symbols grounded at path:line.

### Still-open (self-service)

1. **[SELF-SERVICE — Phase A.3/A.4]** Exact `TB_CLI` (`tb` vs `harbor`), `TB_DATASET_VERSION`, and `TB_OUTPUT_SCHEMA`. Resolution: the `--help` + `datasets list` + one smoke run in Phase A produce all three before Phase B needs them. Not blocking — Phase A is dedicated to producing them.
2. **[SELF-SERVICE — Phase B.5, measured]** Real per-model cost/time envelope for tuning `--cost-cap` default + `--n-concurrent`. Resolution: the `--dry-run` estimate + one capped real run in B.5 establishes it.
3. **[SELF-SERVICE — Phase A]** Whether `terminal-bench` pins a heavy transitive dep that conflicts with the venv. Resolution: `pip install` in A.1 surfaces any conflict immediately; if it does, pin a compatible version or record a BLOCKED with the conflict (not expected — evalplus already coexists).
4. **[OPERATIONAL PRECONDITION — before any real B.5 run]** The OpenRouter account balance was **~$0.19 remaining** on 2026-07-13 (`/api/v1/credits`: `total_credits 75`, `total_usage 74.81`). A real Terminal-Bench run (agentic loops × tasks) needs credit headroom or it 402s mid-run. Resolution: the operator tops up OR before running B.5 for real (dev-only precondition, not a code change); the `--dry-run` estimate + `--cost-cap` bound the spend once topped up. Phase A/B unit tests + `--dry-run` need **zero** credit (no model calls), so this does NOT block plan execution — only the single live B.5 verification and the operator's later real bench runs.

## Handoff

**Next:** `/fabrik-plan-review docs/development/plans/2026-07-13-plan-1-terminal-bench-runner.md` — converge to a fixed point, flip `Status: DRAFT → CONVERGED`.

**Then (user-triggered):** `/fabrik-execute-plan docs/development/plans/2026-07-13-plan-1-terminal-bench-runner.md`.

**💡 fabrik-lib candidates:** none. Project-local to kilo-benchmarks (matches the `microbench_*` precedents).
