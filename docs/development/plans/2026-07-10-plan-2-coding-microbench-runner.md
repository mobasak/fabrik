# Plan: Coding microbench runner (`microbench_coding.py`)

**Status:** IN-PROGRESS (execution started 2026-07-10)
**Converged:** 2026-07-10 via `/fabrik-plan-review` — 3 passes to md5 fixed-point `e0b8698f366b60736c9bb564d37ea40e`. Pass 1 dispatched 3 parallel independent grounders (G1 path:line + external deps, G2 structural pillars, G3 gates + Behavior Contracts + residuals) → 18 unique confirmed defects (1 BLOCKING = missing `libs/subagents/` vendor step; 4 Interface mismatches on `parse_eval_results`/`merge`/`main`/argparse; 5 gate defects; 3 residual defects; 5 structural defects) → all 18 fixed. Pass 2 dispatched an independent post-fix verifier on the new state → 1 cosmetic drift ("Phase A step 0" vs actual label "2b") → fixed. Pass 3 self-sweep confirmed no residual defects → md5 identical → CONVERGED.
**Date:** 2026-07-10
**Author:** primary (this session)
**Spec:** `docs/superpowers/specs/2026-07-10-coding-microbench-runner-design.md` (CONVERGED md5 `b68f50ea0b771292d0a094562fe065b4`)
**Predecessor:** `docs/development/plans/archived/2026-07-10-plan-2-modelscope-new-row-ingest.md` (ModelScope plan-2, EXECUTED — reused this slot after archival)

## Goal (from spec §Goal)

Ship a local coding benchmark runner at `scripts/kilo-benchmarks/microbench_coding.py` that:

1. Runs the full HumanEval (164) + MBPP (399) suites via **EvalPlus** against 4 ByteDance-Seed target models (UI-TARS excluded per spec §UI-TARS out of scope), producing 4 pass@1 scores per model (HumanEval / HumanEval+ / MBPP / MBPP+).
2. Dispatches the 8 (target × dataset) units in parallel via `libs.subagents.run_agents(specs, repo=…, max_concurrency=len(specs))` — with each unit sandboxed in bwrap `--unshare-net --ro-bind / /` and cost-capped at $5/unit.
3. Writes results to `agents.humaneval_score` + `agents.coding_score` (0-100 scale) — deliberately NOT `weighted_coding` (BenchLM-reserved) and NOT `record_agent_run` (would misattribute pass@1 to the orchestrator per `pg_ledger.py:157-172`).
4. Adds a `humaneval_score ≥ threshold` signal to `derive_quality_v2.py`'s tier ladder with a non-regression guard (assert zero non-Seed tier flips before merging).
5. Appends `bytedance-seed/seed-` to `rank_coding_subagents.py:FAMILIES` and regenerates `docs/reference/kilo/CODING_SUBAGENT_SELECTION.md` — the 4 Seed models become visible in the coding-selection MD.
6. Runs the actual live bench (~$2.66 spend, ~30 min wall clock) and confirms non-null scores on all 4 Seed models.

## Global Constraints

- **Python 3.12** (project `pyproject.toml:6`).
- **Bwrap 0.9.0** installed at `/usr/bin/bwrap` — required for `libs.subagents.sandbox.wrap_command` (verified `bwrap --version` in Phase 1).
- **DB path:** `scripts/kilo-benchmarks/kilo_agents.db` (SQLite; `kilo_agents_db.py:40`). NOT `postgres-main` — this is a project-local artifact-DB, not the fleet Postgres.
- **New dep authorized by spec:** `evalplus>=0.3.0` added to `pyproject.toml`. All other deps files (`requirements.txt`, `package.json`, `uv.lock`) untouched.
- **OR API key:** `OPENROUTER_API_KEY` from `/opt/fabrik/.env` (already present; verified). Bench sets `OPENAI_API_KEY=$OPENROUTER_API_KEY` before invoking `evalplus.evaluate` (EvalPlus uses OpenAI client convention).
- **Subagent dispatch:** `run_agents(specs, repo=…, max_concurrency=len(specs))` — hand-built `AgentSpec` list. NEVER `fanout()` (its internal `pick_models(task_type)` under the pool ≤$1.5/Mtok cap silently drops `seed-1.6`/`seed-2.0-lite` at $2.00/Mtok, and its `record=True` default auto-calls `record_agent_run` which misattributes pass@1 to the orchestrator — verified `agent.py:574,621,657,665`).
- **DB write scale:** pass@1 (0.0-1.0) × 100 = 0-100 to match `weighted_coding`'s BenchLM-composite scale that `derive_quality_v2.py:87,101` calibrates against.
- **File naming:** kebab-case for scripts; module-local Python packages snake_case (per `CLAUDE.md` Pointers).
- **Provenance trailers** on every commit: `Agent-Role: <role>`, `Agent-Phase: <A-F>`, `Agent-Context: <what changed>`. Co-Authored-By trailer.
- **Review dispatch template (applies to EVERY phase's closing `/fabrik-review`):** pool `run_agents(specs, tools_enabled=False, allow_ungrounded=True)` with the phase diff inlined, `pick_models("review")`, disjoint per-finder sentinel `owned_paths` (parallel by `62 § Parallelism` rule). **Each finder owes `record_agent_run(spec, result)` + a `results_table` row** — ⚠️ NOT `record_run(result)`, which silently no-ops on a raw `AgentResult` (per `pg_ledger.py:157-172` docstring). Guarded import: `try: from libs.subagents import record_agent_run / except ImportError: record_agent_run = None`. Reserve native `fabrik-reviewer` (Opus) for the authoritative decide/refute/merge. `check_subagent_flywheel.py` WARNs on an unrecorded pool run.
- **Script coupling header (`# AFTER-EDIT:`):** every new `scripts/**/*.py` file this plan creates carries the header per CLAUDE.md § Pointers. Files with no coupled artifact use `# AFTER-EDIT: none`. `check_script_headers.py` WARNs on omission.

## File Scope (owned paths)

**Created:**
- `scripts/kilo-benchmarks/microbench_coding.py` — the runner (~300 LOC — includes CLI, dispatch, JSON parser, DB write, merge)
- `scripts/kilo-benchmarks/tests/test_microbench_coding.py` — behavior tests (both Phase B unit tests + Phase C integration tests)
- `scripts/kilo-benchmarks/tests/test_derive_quality_v2_tier_lift.py` — Phase D tier-lift + non-regression test
- `scripts/kilo-benchmarks/tests/fixtures/eval_results_sample.json` — real EvalPlus output fixture captured in Phase B step 3
- `scripts/kilo-benchmarks/microbench_coding_tier_snapshot.py` — pre/post derive_quality_v2 tier snapshot for the non-regression assertion
- `scripts/kilo-benchmarks/libs/subagents/**` — **VENDORED** in Phase A step 2b from `/opt/fabrik-lib/subagents/subagents/`. Currently `scripts/kilo-benchmarks/libs/` contains only `__init__.py` + `web_scrape/`; the `subagents/` module is NOT vendored today (verified via `ls scripts/kilo-benchmarks/libs/`), so every `from subagents import …` in this plan requires the Phase A step 2b vendor step to land first.

**Modified:**
- `pyproject.toml` — add `evalplus>=0.3.0` to `dependencies`
- `scripts/kilo-benchmarks/derive_quality_v2.py` — add `humaneval_score` to BENCH_TIER3/TIER2 + bump-loop
- `scripts/kilo-benchmarks/rank_coding_subagents.py` — append `bytedance-seed/seed-` to `FAMILIES`
- `docs/reference/kilo/CODING_SUBAGENT_SELECTION.md` — regenerated (mechanical output of `rank_coding_subagents.py`)
- `CHANGELOG.md` — one entry under `[Unreleased]` (append atop `[Unreleased]`, do NOT reset — shared with plan-1)
- `INDEX.md` — record new scripts (append rows — shared with plan-1)
- `docs/FEATURES.md` — describe the local-bench capability under an "Internal tooling" heading (append — shared with plan-1)

**Sibling-plan disjointness:** plan-1 (`2026-07-10-plan-1-mobile-app-factory.md`) owns `templates/mobile-app/**` + `scaffold.py` + related infra. This plan owns `scripts/kilo-benchmarks/**` + `pyproject.toml` + `docs/reference/kilo/**`. Code-file scope is disjoint. **Shared top-level doc-sync files** (`CHANGELOG.md`, `INDEX.md`, `docs/FEATURES.md`) are unavoidably co-owned per shared-master convention — commit discipline: (a) append atop `[Unreleased]` in CHANGELOG, never reset the section; (b) `git add <explicit-path>` only, never `-A`; (c) `git diff --cached --name-only` before commit to verify no bundling of sibling changes. Per CLAUDE.md HARD STOPS.

## Context Ledger

| Source | What binds | Grounded ref |
|---|---|---|
| **`.windsurf/rules/core/10-python.md`** (ACTIVE) | Python 3.12 typing + `os.getenv` for env access + no hardcoded secrets | `pyproject.toml:6` (`requires-python = ">=3.12"`); env keys read via `os.getenv("OPENROUTER_API_KEY")` never inline |
| **`.windsurf/rules/core/40-documentation.md`** (ACTIVE) | Doc Sync Matrix triggers: Code/deps changed → CHANGELOG; File added → INDEX; Feature shipped → FEATURES | applied per phase; final `/fabrik-docs-review` in Phase F |
| **`.windsurf/rules/core/45-testing-strategy.md`** (ACTIVE) | Behavior Contract: one test per user-observable behavior, risk-ordered TDD, skip trivia | tests co-located under `scripts/kilo-benchmarks/tests/test_*.py` (mirrors `test_ms_enrich.py` sibling pattern) |
| **`.windsurf/rules/core/50-code-review.md`** (AVAILABLE, applies here) | `/fabrik-review` methodology at each phase boundary — finders → refute → prove-before-fix | emitted as the phase closing step in EVERY phase below |
| **`.windsurf/rules/core/62-using-subagents.md`** (ACTIVE) | Pool-vs-native dispatch policy; `run_agents` semantics; parallel `tools_enabled=True` needs disjoint `owned_paths`; flywheel `record_agent_run` | dispatch decision from spec §Chosen approach step 2 — hand-built AgentSpec + `max_concurrency=len(specs)`, NOT `fanout()`, NOT `record_agent_run` for the bench itself |
| **`AGENTS.md`** infra (implicitly) | This is a hub-side utility script — no VPS deploy, no `specs/services/*.yaml`, no compose, no `postgres-main` | verified: no `shape:` change (spec §Shape/infra line 173 — "no `specs/services/*.yaml` touched") |
| **`fabrik-lib/subagents/`** (vendored copy at `scripts/kilo-benchmarks/libs/subagents/`) | `run_agents([AgentSpec], repo=…, max_concurrency=N)` at `agent.py:504-539`; `AgentSpec` fields at `agent.py:56-95`; bwrap wrap at `sandbox.py:121`; DO NOT call `fanout()` | verified this session (Pass 5-7 of spec-review) — `run_agents` in `__init__.py:__all__:42`, hand-built specs bypass pool cap, `record=True` NOT default in `run_agents` (only in `fanout`) |
| **`fabrik-lib/README.md`** consult | ✅ done in spec §fabrik-lib verdict table — nothing missed | spec verdict rows 1-6 all CLEAN (Pass 1 grounder audit) |
| **`kilo_agents_db.py:228-229,846-847`** schema | `humaneval_score REAL`, `coding_score REAL`, `last_verified DATE` — declared but ZERO existing populators (grep verified prior session); this bench is the first writer | writes go via parameterized UPDATE — no schema migration needed |
| **`scrape_benchlm.py:70`** | Sole `weighted_coding` populator (BenchLM `categoryScores.coding` composite, 0-100 scale) — DO NOT cross-populate | bench writes `humaneval_score` + `coding_score` only |
| **`rank_coding_subagents.py:53-65`** | `FAMILIES` allowlist gates which models surface in CODING_SUBAGENT_SELECTION.md; also uses `AUTO_OUTPUT_PRICE_CEILING = 1.5` — but the Auto/On-request split is orthogonal to visibility (row visible either way; just marked On-request if output > $1.5) | append `bytedance-seed/seed-` — `seed-1.6`/`seed-2.0-lite` at $2.00/Mtok will land in the On-request tier (correct; operator explicitly names them per turn) |
| **`derive_quality_v2.py:84-109,157-201`** | Tier ladder reads `weighted_coding`, `swe_bench_verified_pct`, `aider_polyglot_pct`, `design_arena_coding_elo`, `translation_avg_pct`, `arena_elo`, `tbench`, `aa_index` — adding `humaneval_score` requires updating BENCH_TIER3 + BENCH_TIER2 dicts + the two bump-loops | ~5-LOC edit + a stub-row test that asserts the tier lift + a non-regression check that re-runs derive_v2 on every existing row |
| **`microbench_or_models.py`** (sibling pattern) | Freshness gate (`last_verified >= today - 60d` skips) + `--dry-run` + `--models <csv>` flag conventions | mirror the pattern in `microbench_coding.py` |

**fabrik-lib consult performed:** the spec's Pass-1 Axis-B grounder independently re-grepped `/opt/fabrik-lib/README.md` for `bench|eval|humaneval|pass@|code.*exec|sandbox|score|parallel|dispatch|orchestr|worker|fan.?out` — no missed modules. `subagents/` (adopted), `claude-evaluator/` (wrong domain), `concurrency-throttle/` (not needed) are the only hits.

## Phase A — Preflight: dep install, sandbox probe, DB assertions — ✅ EXECUTED 2026-07-10

**Purpose:** Confirm the runtime environment (evalplus installed, bwrap available, DB writable, subagents module reachable) so no later phase discovers a missing tool.

### Interfaces

**Consumes:** nothing (first phase).
**Produces:**
- `evalplus>=0.3.0` importable: `python -c "from evalplus.provider.openai import OpenAIChatDecoder"` exits 0.
- `libs.subagents` importable from `scripts/kilo-benchmarks/libs/subagents/`.
- `agents.humaneval_score` + `agents.coding_score` writable via parameterized UPDATE.

### Behavior Contract (this phase)

- **A1**: `evalplus` importable after `pip install -e ".[dev]"` (Given: fresh venv; When: install; Then: `from evalplus.provider.openai import OpenAIChatDecoder` succeeds).
- **A2**: `bwrap --version` returns 0.9.0+ (Given: WSL dev host; When: probe; Then: version ≥ 0.9.0).
- **A3**: `agents.humaneval_score` accepts a REAL update via parameterized query without touching `weighted_coding` (Given: existing row; When: `UPDATE agents SET humaneval_score = ? WHERE id = ?`; Then: only that column changes).

### Steps

1. **Add dep to `pyproject.toml`.** Insert `"evalplus>=0.3.0",` in the `dependencies` list at `pyproject.toml:12-23` (between `httpx` and `python-dotenv` alphabetically).

2. **Install the venv delta.** From `/opt/fabrik`:
   ```bash
   .venv/bin/pip install -e ".[dev]" 2>&1 | tail -5
   ```
   Expected: `Successfully installed evalplus-0.3.1` (or later) — since the wheel is on PyPI (repo release Oct 20 2024, verified in spec §External deps).

2b. **Vendor `libs.subagents` from fabrik-lib (BLOCKING — all downstream imports depend on this).**
   Current state (verified this planning session): `scripts/kilo-benchmarks/libs/` contains only `__init__.py` + `web_scrape/`. The `subagents/` subdir does NOT exist, so every `from subagents import …` in this plan would `ImportError` without this step.
   ```bash
   cp -r /opt/fabrik-lib/subagents/subagents /opt/fabrik/scripts/kilo-benchmarks/libs/subagents
   ls /opt/fabrik/scripts/kilo-benchmarks/libs/subagents/
   ```
   Expected: `__init__.py agent.py sandbox.py pg_ledger.py ...` (12+ files).

2c. **Verify orchestrator model live on OR.** Plan hardcodes `qwen/qwen3-coder-flash` as the orchestrator each pool AgentSpec uses to run the shell command. Verify it's active per `feedback_verify_model_ids_live_first.md` (do not trust DB alone):
   ```bash
   curl -s https://openrouter.ai/api/v1/models | python3 -c "
   import sys, json
   ids = {m.get('id') for m in json.load(sys.stdin).get('data', [])}
   assert 'qwen/qwen3-coder-flash' in ids, 'orchestrator not live on OR — pick another cheap coder from qwen3-coder-* or minimax-m3'
   print('OK: qwen/qwen3-coder-flash live')
   "
   ```
   Expected: `OK: qwen/qwen3-coder-flash live`. If the assertion fails: substitute the first alternative from `pick_models("code", n=1)` at plan-execution time — the exact call: `.venv/bin/python -c "import sys; sys.path.insert(0, 'scripts/kilo-benchmarks/libs'); from subagents.select import pick_models; print(pick_models('code', n=1)[0])"`. This is SELF-SERVICE — do not stop to ask; substitute + proceed.

3. **Import probe (validation gate).**
   ```bash
   .venv/bin/python -c "from evalplus.provider.openai import OpenAIChatDecoder; print('base_url in ctor:', 'base_url' in OpenAIChatDecoder.__init__.__code__.co_varnames)"
   ```
   Expected: `base_url in ctor: True`.

4. **Bwrap probe.**
   ```bash
   /usr/bin/bwrap --version
   ```
   Expected: `bubblewrap 0.9.0` or later.

5. **DB write probe (dry).**
   ```bash
   .venv/bin/python -c "
   import sqlite3, pathlib
   db = pathlib.Path('scripts/kilo-benchmarks/kilo_agents.db')
   assert db.exists(), f'agents DB missing at {db}'
   conn = sqlite3.connect(db)
   cols = {r[1] for r in conn.execute('PRAGMA table_info(agents)').fetchall()}
   assert {'humaneval_score', 'coding_score', 'last_verified'} <= cols, f'missing bench-target columns: {cols}'
   conn.close()
   print('OK')
   "
   ```
   Expected: `OK`.

6. **Subagents module probe.**
   ```bash
   .venv/bin/python -c "
   import sys, pathlib
   sys.path.insert(0, str(pathlib.Path('scripts/kilo-benchmarks/libs').resolve()))
   from subagents import run_agents, AgentSpec
   from subagents.sandbox import wrap_command, sandbox_available
   assert sandbox_available(), 'bwrap must be available'
   print('run_agents kwargs:', 'max_concurrency' in run_agents.__code__.co_varnames)
   "
   ```
   Expected: `run_agents kwargs: True`.

### Phase A closing sequence

1. Run this phase's validation gates (steps 3-6 above) → all green.
2. `python scripts/enforcement/check_doc_sync.py` — expect no WARNING (Phase A only touches `pyproject.toml`; CHANGELOG entry is added in Phase F for the whole bundle, not per-phase, per shared-master convention).
3. **`/fabrik-review` on this phase's changed surface (`pyproject.toml` diff)** — a BLOCKING gate, looped to zero CONFIRMED/PLAUSIBLE findings. Since the change is a single-line dep addition, the review will be quick, but MUST run per the enforced pillar.
4. **Commit Phase A** (explicit paths, provenance trailers):
   ```bash
   git add pyproject.toml scripts/kilo-benchmarks/libs/subagents
   git diff --cached --name-only  # verify: no bundling of sibling changes
   git commit -m "$(cat <<'EOF'
   chore(kilo-benchmarks): Phase A — vendor subagents + add evalplus dep for microbench_coding

   Agent-Role: primary
   Agent-Phase: A
   Agent-Context: vendored /opt/fabrik-lib/subagents/subagents → scripts/kilo-benchmarks/libs/subagents; spec-authorized evalplus>=0.3.0 dep added; preflight probes (bwrap, subagents import, DB schema, OR-live orchestrator model) all pass

   Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
   EOF
   )"
   ```

## Phase B — Runner core: `microbench_coding.py` core functions + tests

**Purpose:** Author the runner's pure functions (`build_specs`, `parse_eval_results`, `merge_dataset_results`) + a sandbox regression pin. `main()` and CLI-flag argparse are wired in Phase C (they need `write_scores` + `is_fresh` which Phase C introduces) — do not test `main` here.

### Interfaces

**Consumes:** Phase A's env (evalplus + bwrap + subagents importable at `libs/subagents/`).
**Produces:**
- `scripts/kilo-benchmarks/microbench_coding.py` with:
  - Module-level constants: `DEFAULT_MODELS: list[str]` (4 Seed IDs), `DEFAULT_DATASETS: list[str]` (`["humaneval", "mbpp"]`), `ORCHESTRATOR_MODEL: str` (`"qwen/qwen3-coder-flash"`).
  - `build_specs(target_models: list[str], datasets: list[str], work_dir: pathlib.Path, orchestrator: str = ORCHESTRATOR_MODEL) -> list[AgentSpec]`. Produces `len(target_models) * len(datasets)` specs; each `spec.owned_paths=[str(unique_dir)]`; `spec.model=orchestrator`.
  - `parse_eval_results(results_json: pathlib.Path) -> dict[str, float]` — **single-dataset scope**: reads ONE `<dir>/humaneval_results.json` (or MBPP equivalent) and returns `{"base": <0.0-1.0 raw pass@1>, "plus": <0.0-1.0 raw pass@1>}` — only TWO keys per call (EvalPlus's `pass@1.base` = plain; `pass@1.plus` = the +tests). Caller is responsible for calling this per-dataset then merging via `merge_dataset_results`.
  - `merge_dataset_results(humaneval: dict[str, float], mbpp: dict[str, float]) -> dict[str, float]` — returns the 4-key dict `write_scores` consumes: `{"base": humaneval["base"], "plus": humaneval["plus"], "mbpp_base": mbpp["base"], "mbpp_plus": mbpp["plus"]}`. All keys required; raises `KeyError` if either input dict is missing a key.
- Tests in `scripts/kilo-benchmarks/tests/test_microbench_coding.py` (Phase B behaviors B1-B4; Phase C adds C1-C5 to the same file).
- Fixture `scripts/kilo-benchmarks/tests/fixtures/eval_results_sample.json` — real EvalPlus output captured via Phase B step 3 hard probe.

### Behavior Contract (this phase — risk-ordered)

- **B1 (highest risk — regression pin, not TDD)**: The bwrap outer sandbox (`libs.subagents.sandbox.wrap_command`) blocks a shell command from writing outside its `workdir`. (Given: `cmd=["/bin/sh", "-c", "touch /tmp/pwned_marker"]` wrapped via `wrap_command(cmd, workdir=tmp_path)`; When: `subprocess.run(wrapped, timeout=10)`; Then: `/tmp/pwned_marker` does NOT exist.) This is a REGRESSION PIN on an existing capability (bwrap `--unshare-net --ro-bind / /` already blocks), not TDD — the test codifies the guarantee so a future regression to `sandbox.py` fails LOUD.
- **B2 (highest risk — TDD)**: `build_specs` produces exactly `len(target_models) * len(datasets)` AgentSpecs with UNIQUE `owned_paths` — critical because overlapping `owned_paths` under `tools_enabled=True` silently serializes the dispatch (`62-using-subagents.md § Parallelism`). Write this test FIRST; it must FAIL before `build_specs` is authored (import error is a valid red). (Given: 4 target models × 2 datasets; When: build; Then: `len(specs) == 8` AND `len({tuple(s.owned_paths) for s in specs}) == 8` AND each `spec.task` contains `--model <target>` + `--dataset <ds>`.)
- **B3**: `parse_eval_results` correctly extracts pass@1 from a REAL EvalPlus fixture at `tests/fixtures/eval_results_sample.json`. (Given: fixture JSON captured Phase B step 3; When: parse; Then: exactly 2 keys `{base, plus}`, both floats in `[0.0, 1.0]`.)
- **B4**: `merge_dataset_results` combines two `{base, plus}` dicts into the 4-key dict `write_scores` expects. (Given: `humaneval={base:0.5, plus:0.4}`, `mbpp={base:0.6, plus:0.55}`; When: merge; Then: `{"base": 0.5, "plus": 0.4, "mbpp_base": 0.6, "mbpp_plus": 0.55}`. And with a missing key in either input: `KeyError`.)

**NOT in Phase B (moved to Phase C):**
- `main` CLI wiring, `--dry-run`/`--force`/`--cost-cap`/`--models`/`--datasets` argparse contract, "model not in DB" rejection — all deferred to Phase C where `is_fresh` + `write_scores` land.

### Steps

1. **Capture the real EvalPlus fixture (hard probe — B3 depends on this).** Run evalplus on a SINGLE HumanEval problem against a cheap model in a throwaway dir, then commit the produced JSON as the test fixture. This is the ONLY reliable way to know the actual `eval_results.json` shape (`inspect.getsource` returns Python code, not JSON):
   ```bash
   PROBE_DIR=$(mktemp -d)
   cd $PROBE_DIR
   OPENAI_API_KEY=$OPENROUTER_API_KEY .venv/bin/python -m evalplus.evaluate \
       --backend openai \
       --base-url https://openrouter.ai/api/v1 \
       --model qwen/qwen3-coder-flash \
       --dataset humaneval \
       --greedy \
       --root . \
       --n-samples 1 2>&1 | tail -20
   find . -name '*eval_results*.json' -exec cat {} \; | python3 -m json.tool | head -30
   RESULT=$(find . -name '*eval_results*.json' | head -1)
   cp "$RESULT" /opt/fabrik/scripts/kilo-benchmarks/tests/fixtures/eval_results_sample.json
   cd -
   rm -rf $PROBE_DIR
   ```
   Expected: JSON output with top-level `pass@1` key containing `base` + `plus` subkeys (float 0.0-1.0 each). If the ACTUAL shape differs (e.g., top-level is `{"humaneval": {"pass@1": {...}}}` instead of `{"pass@1": {...}}`), update `parse_eval_results` implementation + B3 fixture assertions to match the real shape. Cost: <$0.01 for 1 problem.

2. **Write B2's test FIRST (TDD — must fail red before `build_specs` exists).**
   ```python
   # tests/test_microbench_coding.py
   def test_build_specs_produces_disjoint_owned_paths():
       from microbench_coding import build_specs
       specs = build_specs(
           target_models=["m1/a", "m2/b", "m3/c", "m4/d"],
           datasets=["humaneval", "mbpp"],
           work_dir=pathlib.Path("/tmp/microbench_test"),
       )
       assert len(specs) == 8, f"expected 8 specs, got {len(specs)}"
       owned = [tuple(s.owned_paths) for s in specs]
       assert len(set(owned)) == 8, f"owned_paths NOT unique: {owned}"
       for s in specs:
           assert "--model" in s.task and "--dataset" in s.task
   ```
   Run: `.venv/bin/pytest scripts/kilo-benchmarks/tests/test_microbench_coding.py::test_build_specs_produces_disjoint_owned_paths -xvs` — MUST fail with `ImportError` (module not written yet).

3. **Author `microbench_coding.py` skeleton (pure functions only, no `main` yet).**
   ```python
   """Local coding benchmark runner — EvalPlus + libs.subagents composition.

   Spec: docs/superpowers/specs/2026-07-10-coding-microbench-runner-design.md
   Plan: docs/development/plans/2026-07-10-plan-2-coding-microbench-runner.md
   """
   # AFTER-EDIT: docs/reference/kilo/CODING_SUBAGENT_SELECTION.md (regenerated after this runs)

   from __future__ import annotations
   import argparse, json, os, sqlite3, sys, pathlib
   from dataclasses import dataclass

   SCRIPT_DIR = pathlib.Path(__file__).parent
   DB_PATH = SCRIPT_DIR / "kilo_agents.db"
   sys.path.insert(0, str((SCRIPT_DIR / "libs").resolve()))

   from subagents import run_agents, AgentSpec  # noqa: E402
   from subagents.sandbox import sandbox_available  # noqa: E402

   DEFAULT_MODELS = [
       "bytedance-seed/seed-1.6-flash",
       "bytedance-seed/seed-2.0-mini",
       "bytedance-seed/seed-1.6",
       "bytedance-seed/seed-2.0-lite",
   ]
   DEFAULT_DATASETS = ["humaneval", "mbpp"]
   ORCHESTRATOR_MODEL = "qwen/qwen3-coder-flash"  # verified live on OR in Phase A step 2c

   def build_specs(
       target_models: list[str],
       datasets: list[str],
       work_dir: pathlib.Path,
       orchestrator: str = ORCHESTRATOR_MODEL,
   ) -> list[AgentSpec]:
       specs = []
       for target in target_models:
           for ds in datasets:
               unit_dir = work_dir / target.replace("/", "__") / ds
               unit_dir.mkdir(parents=True, exist_ok=True)
               task = (
                   f"cd {unit_dir} && "
                   f"OPENAI_API_KEY=$OPENROUTER_API_KEY evalplus.evaluate "
                   f"--backend openai "
                   f"--base-url https://openrouter.ai/api/v1 "
                   f"--model {target} "
                   f"--dataset {ds} "
                   f"--greedy --root ./results"
               )
               specs.append(AgentSpec(
                   task=task,
                   model=orchestrator,
                   task_type="code",
                   tools_enabled=True,
                   owned_paths=[str(unit_dir)],
                   max_cost_usd=5.0,
                   wall_clock_s=1800,  # 30 min
               ))
       return specs

   def parse_eval_results(results_json: pathlib.Path) -> dict[str, float]:
       """Read ONE EvalPlus dataset's eval_results.json → {base, plus}. Per-dataset scope."""
       data = json.loads(results_json.read_text())
       # Fixture-verified shape: adjust if step 1 probe reveals different shape
       base = data.get("pass@1", {}).get("base")
       plus = data.get("pass@1", {}).get("plus")
       return {
           "base": float(base) if base is not None else 0.0,
           "plus": float(plus) if plus is not None else 0.0,
       }

   def merge_dataset_results(humaneval: dict[str, float], mbpp: dict[str, float]) -> dict[str, float]:
       """Merge two per-dataset {base, plus} dicts into the 4-key dict write_scores consumes."""
       return {
           "base": humaneval["base"],       # HumanEval pass@1 base
           "plus": humaneval["plus"],       # HumanEval+ pass@1
           "mbpp_base": mbpp["base"],       # MBPP pass@1
           "mbpp_plus": mbpp["plus"],       # MBPP+ pass@1
       }
   ```

4. **Write B1 regression pin, B3 (fixture-based), B4 (merge) tests.** Author each in `tests/test_microbench_coding.py`. Include `# AFTER-EDIT: none` header (`# AFTER-EDIT:` per CLAUDE.md § Script coupling — required on every `scripts/**/*.py`; the test file has no coupled artifacts, so `none`).

5. **Test-run all Phase B behaviors:**
   ```bash
   .venv/bin/pytest scripts/kilo-benchmarks/tests/test_microbench_coding.py -xvs -k "sandbox or build_specs or parse_eval_results or merge_dataset_results"
   ```
   Expected: 4/4 pass (B1 sandbox pin, B2 disjoint owned_paths, B3 fixture parse, B4 merge).

### Phase B closing sequence

1. Run this phase's validation gate (step 5 above) → 4/4 green.
2. `python scripts/enforcement/check_doc_sync.py` — expect no doc-sync WARNING scoped to Phase B's changed files.
3. **`/fabrik-review` on this phase's changed surface** — dispatch **pool** finder subagents per `.windsurf/rules/core/50-code-review.md` methodology: `run_agents(specs, tools_enabled=False, allow_ungrounded=True)` with the diff inlined, `pick_models("review")`, **each finder owes `record_agent_run(spec, result)` + `results_table`** (⚠️ NOT `record_run` — it silently no-ops on a raw `AgentResult` per `62-using-subagents.md`). Refute → prove-before-fix → re-run gate. Loop to no-op. **This pool-dispatch template applies to every subsequent phase's closing review — see Global Constraint at header.**
4. **Commit Phase B** (explicit paths + provenance):
   ```bash
   git add scripts/kilo-benchmarks/microbench_coding.py scripts/kilo-benchmarks/tests/test_microbench_coding.py scripts/kilo-benchmarks/tests/fixtures/eval_results_sample.json
   git diff --cached --name-only  # verify: no bundling of sibling changes
   git commit -m "$(cat <<'EOF'
   feat(kilo-benchmarks): Phase B — microbench_coding.py pure functions + 4-behavior test suite

   Agent-Role: primary
   Agent-Phase: B
   Agent-Context: build_specs (4×2 units, disjoint owned_paths TDD), parse_eval_results per-dataset (base+plus), merge_dataset_results (4-key composite), sandbox regression pin; main() deferred to Phase C

   Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
   EOF
   )"
   ```

## Phase C — DB write layer + `main` CLI + argparse contract + freshness gate

**Purpose:** Wire the merged per-model score dict to `agents` UPDATE (0-100 scale, deliberately NOT `weighted_coding`) + author `main()` with full argparse contract + idempotent freshness gate.

### Interfaces

**Consumes:** Phase B's `build_specs`, `parse_eval_results`, `merge_dataset_results`.
**Produces:**
- `microbench_coding.write_scores(conn: sqlite3.Connection, model_id: str, scores: dict[str, float]) -> None` — parameterized UPDATE writing `humaneval_score`, `coding_score`, `last_verified`. Reads keys `{base, plus, mbpp_base, mbpp_plus}` from the merged dict Phase B's `merge_dataset_results` produces. Deliberately NOT `weighted_coding`.
- `microbench_coding.is_fresh(conn: sqlite3.Connection, model_id: str, ttl_days: int = 60) -> bool` — mirrors `microbench_or_models.py:70,286-291` pattern (`RECENCY_WINDOW_DAYS` const + `cutoff = (datetime.now(UTC).date() - timedelta(days=ttl_days)).isoformat()`; UTC not local per the sibling's comment at :286-287 — local `date.today()` would drift by up to 24h relative to the writer).
- `microbench_coding.main(argv: list[str] | None = None) -> int` — CLI entrypoint. **Full argparse contract:**
  - `--models <csv>` — comma-separated OR-routable model IDs. Default: `DEFAULT_MODELS` (4 Seed IDs).
  - `--datasets <csv>` — subset of `{humaneval, mbpp}`. Default: both.
  - `--cost-cap <float>` — per-unit `AgentSpec.max_cost_usd`. Default: `5.0`.
  - `--force` — bypass the `is_fresh` gate; re-run models benched within the last `ttl_days`.
  - `--dry-run` — print the spec dispatch plan + estimated cost, do NOT invoke `run_agents`, do NOT open OR API, exit 0.
  - `--ttl-days <int>` — override `is_fresh` window. Default: 60.
- **Exit contract (required emission)**: `main()` MUST print a final line matching the regex `^TOTAL_SPEND_USD: (\d+\.\d+)$` on stdout before returning — sums real spend across all AgentResults; in `--dry-run` prints `TOTAL_SPEND_USD: 0.00`. E4 (Phase E) grep-asserts this line.
- Full end-to-end flow: `main(--models …)` → filter by `is_fresh` → `build_specs` → `run_agents(specs, repo=str(work_dir.parent), max_concurrency=len(specs))` → per-target-model group: parse both dataset JSONs → `merge_dataset_results` → `write_scores` → per-model commit inside loop (progress-preserving on kill).

### Behavior Contract (this phase)

- **C1 (highest risk — TDD)**: `write_scores` never writes to `weighted_coding` even when the input dict contains a `weighted_coding` key. (Given: mocked scores `{base: 0.42, plus: 0.35, mbpp_base: 0.5, mbpp_plus: 0.45, weighted_coding: 0.99}`; When: `write_scores`; Then: `SELECT weighted_coding FROM agents WHERE id = ?` is UNCHANGED from pre-call value. The UPDATE column list is explicit — extra keys in the dict are ignored, not passed through.)
- **C2**: `write_scores` writes `humaneval_score = round(scores["base"] * 100, 2)` (0-100 scale). (Given: `base=0.42`; When: write; Then: DB row shows `humaneval_score = 42.0`.)
- **C3**: `write_scores` sets `coding_score = round(mean(base, plus, mbpp_base, mbpp_plus) * 100, 2)`. (Given: all four = 0.4; When: write; Then: `coding_score = 40.0`.)
- **C4**: `is_fresh` returns True if `last_verified >= today - ttl_days` (UTC), False otherwise. (Given: row with `last_verified = (datetime.now(UTC).date() - timedelta(days=30)).isoformat()`; When: `is_fresh(model, 60)`; Then: True. With `days=90`: False.)
- **C5**: `main --models <M>` skips models where `is_fresh(60)` returns True unless `--force` is passed. (Given: fresh DB row; When: `main([--models, M])`; Then: stdout contains `SKIP (fresh)`, exit 0. With `--force`: dispatch happens.)
- **C6**: `main --dry-run` prints the spec dispatch plan + `TOTAL_SPEND_USD: 0.00` WITHOUT invoking `run_agents` or any OR call. (Given: `--dry-run --models bytedance-seed/seed-1.6-flash --datasets humaneval`; When: main; Then: stdout contains `DRY RUN` + a spec descriptor + literal line `TOTAL_SPEND_USD: 0.00`, exit 0, mocked `run_agents` NOT called.)
- **C7**: `main` rejects a target model NOT present in the DB with a clear message. (Given: `--models nonexistent/model`; When: main; Then: exit code 1, stderr contains `not in agents table`.)
- **C8**: `main` prints `TOTAL_SPEND_USD: <float>` on the last line of stdout in the non-dry-run happy path. (Given: mocked `run_agents` returning 2 fake AgentResults with `cost_usd=0.11` each; When: `main([--models, M])`; Then: last stdout line matches `^TOTAL_SPEND_USD: 0\.22$`.)

### Steps

1. **TDD C1 first.** Write `test_write_scores_never_touches_weighted_coding`. Should fail red (function doesn't exist yet); after `write_scores` is implemented with an explicit UPDATE column list, should turn green.

2. **Implement `write_scores`.**
   ```python
   def write_scores(conn: sqlite3.Connection, model_id: str, scores: dict[str, float]) -> None:
       """Write pass@1 scores to agents.humaneval_score + agents.coding_score.

       Scale: 0-100 (raw pass@1 × 100), matching weighted_coding's BenchLM-composite
       calibration in derive_quality_v2.py:87,101.

       ⚠️ Explicitly does NOT write weighted_coding — that column is BenchLM-owned
       via scrape_benchlm.py:70. Crossing populators breaks tier threshold
       cross-model comparability.
       """
       base = scores.get("base", 0.0) * 100
       plus = scores.get("plus", 0.0) * 100
       mbpp_base = scores.get("mbpp_base", 0.0) * 100
       mbpp_plus = scores.get("mbpp_plus", 0.0) * 100
       coding_composite = round((base + plus + mbpp_base + mbpp_plus) / 4, 2)
       humaneval = round(base, 2)
       conn.execute(
           "UPDATE agents SET humaneval_score = ?, coding_score = ?, "
           "last_verified = date('now') WHERE id = ?",
           (humaneval, coding_composite, model_id),
       )
       conn.commit()
   ```

3. **Implement `is_fresh` mirroring `microbench_or_models.py:70,286-291`.** The sibling's pattern (verified this planning session by grep):
   ```python
   # microbench_or_models.py:70
   RECENCY_WINDOW_DAYS = 30
   # microbench_or_models.py:286-291
   #     Cutoff uses `datetime.now(UTC).date()` to match `_write_result` which
   #     writes `speed_updated_at` as a UTC date. Local `date.today()` would
   #     drift by up to 24h relative to the writer.
   cutoff = (datetime.now(UTC).date() - timedelta(days=RECENCY_WINDOW_DAYS)).isoformat()
   ```
   Mirror this in `microbench_coding.is_fresh` — use `datetime.now(UTC).date()` (NOT `date.today()`) + `ttl_days=60` default (not 30 — this is a coding bench, less-frequently re-run than the speed bench). SQL: `SELECT last_verified FROM agents WHERE id = ? AND last_verified >= ?`.

4. **Author `main()` end-to-end + argparse.** Wire full CLI per Interfaces block (`--models`, `--datasets`, `--cost-cap`, `--force`, `--dry-run`, `--ttl-days`). Sequence:
   - Parse argv via `argparse.ArgumentParser`.
   - Open DB; validate every `--models` target exists in `agents` (else exit 1 + stderr).
   - Filter by `is_fresh` unless `--force`.
   - If `--dry-run`: print spec list + `TOTAL_SPEND_USD: 0.00`, exit 0.
   - Else: `run_agents(specs, repo=str(work_dir.parent), max_concurrency=len(specs))`.
   - Group AgentResults by target model; for each: parse both dataset JSONs → `merge_dataset_results` → `write_scores` → per-model `conn.commit()` (progress on kill).
   - Sum `result.cost_usd` for all AgentResults; print `TOTAL_SPEND_USD: {sum:.2f}` as the LAST line.

5. **Test-run C1-C8:**
   ```bash
   .venv/bin/pytest scripts/kilo-benchmarks/tests/test_microbench_coding.py -k "write_scores or is_fresh or main" -xvs
   ```
   Expected: 8/8 pass.

6. **Integration dry-run against the real DB:**
   ```bash
   .venv/bin/python scripts/kilo-benchmarks/microbench_coding.py --dry-run --models bytedance-seed/seed-1.6-flash --datasets humaneval
   ```
   Expected: prints AgentSpec dispatch plan + `TOTAL_SPEND_USD: 0.00`, no network calls, no DB writes, exit 0.

### Phase C closing sequence

1. Run C1-C8 tests + integration dry-run → all green.
2. `python scripts/enforcement/check_doc_sync.py` — no WARNING scoped to Phase C's diff.
3. **`/fabrik-review` on Phase C's changed surface** — pool-dispatch template per Phase B closing sequence step 3 (`run_agents(specs, tools_enabled=False, allow_ungrounded=True)`, `pick_models("review")`, each finder owes `record_agent_run` + `results_table`). Highest-risk lens for Phase C: "does `write_scores` really only touch the intended columns" (SQL column-scope + parameterized query — C1's TDD test codifies this).
4. **Commit Phase C** (explicit paths + trailers):
   ```bash
   git add scripts/kilo-benchmarks/microbench_coding.py scripts/kilo-benchmarks/tests/test_microbench_coding.py
   git diff --cached --name-only
   git commit -m "$(cat <<'EOF'
   feat(kilo-benchmarks): Phase C — write_scores + main() + argparse contract + is_fresh (UTC)

   Agent-Role: primary
   Agent-Phase: C
   Agent-Context: write_scores never touches weighted_coding (C1 TDD); 0-100 scale (C2,C3); is_fresh UTC-anchored per microbench_or_models.py:286-291; main() full argparse with --models/--datasets/--cost-cap/--force/--dry-run/--ttl-days; TOTAL_SPEND_USD emission contract for E4

   Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
   EOF
   )"
   ```

## Phase D — Tier ladder + FAMILIES + non-regression guard

**Purpose:** Wire the bench signal downstream — add `humaneval_score` to `derive_quality_v2.py`'s tier ladder AND assert no non-Seed model tier-flips (spec §Success criteria "Non-regression on the tier ladder").

### Interfaces

**Consumes:** existing `derive_quality_v2.py` + `rank_coding_subagents.py` (unchanged pre-phase); populated `humaneval_score` values from Phase C's writes (or stub rows for the test).
**Produces:**
- `derive_quality_v2.py:BENCH_TIER3` gains `"humaneval_score": 60.0`; `BENCH_TIER2` gains `"humaneval_score": 40.0`; the two bump-loops at `:172-186` + `:187-201` gain a corresponding `("humaneval_score", he_score, BENCH_TIER<N>["humaneval_score"])` row.
- `rank_coding_subagents.py:FAMILIES` at `:53-65` gains `"bytedance-seed/seed-"` prefix.
- `scripts/kilo-benchmarks/microbench_coding_tier_snapshot.py` — a small tool: (1) reads every `agents` row; (2) computes its `derive_v2` tier; (3) prints/writes `{model_id: tier}` map. Used pre-edit + post-edit for the non-regression assertion.
- `scripts/kilo-benchmarks/tests/test_derive_quality_v2_tier_lift.py` — asserts (a) the tier-lift fires on a stub row with `humaneval_score = 65`; (b) NO non-Seed row's derived tier changes when the edit lands.

### Behavior Contract (this phase)

- **D1 (highest risk — TDD)**: A stub row with only `humaneval_score = 65` (all other bench cols NULL) derives Tier 3 after the edit. (Given: stub; When: `derive_v2(row, or_record=None)`; Then: returns `(3, [...])` with the `"humaneval_score≥60.0(65.0)"` evidence line.)
- **D2**: A stub row with `humaneval_score = 45` derives Tier 2. (Same as D1 but at the mid tier.)
- **D3 (blast-radius guard)**: The tier snapshot on every existing `agents` row (excluding `bytedance-seed/*` where the column was NULL pre-edit) is IDENTICAL before and after the derive_v2 edit. (Given: real DB pre-Phase-D; When: edit ladder; Then: `sorted(pre_tier_map.items()) == sorted(post_tier_map.items())` restricted to non-`bytedance-seed/*` rows.)
- **D4**: `rank_coding_subagents.py:FAMILIES` after the append contains `"bytedance-seed/seed-"` prefix and matches all 4 Seed model IDs. (Given: post-edit FAMILIES; When: `any(m.startswith(p) for p in FAMILIES)` for each of the 4 Seed IDs; Then: True for all 4.)

### Steps

1. **Author `microbench_coding_tier_snapshot.py`** (~30 LOC). Include header `# AFTER-EDIT: none` (CLAUDE.md § Script coupling). Iterate `agents` rows, call `derive_v2(row, or_record=None)`, write `{model_id: {"tier": N, "evidence": [...]}}` to stdout as JSON.

2. **Capture the pre-edit tier snapshot:**
   ```bash
   .venv/bin/python scripts/kilo-benchmarks/microbench_coding_tier_snapshot.py > /tmp/tier_snapshot_pre.json
   ```

3. **TDD D3 first.** Write the non-regression test at `tests/test_derive_quality_v2_tier_lift.py` (include `# AFTER-EDIT: none` header). Reads `/tmp/tier_snapshot_pre.json`, re-imports `derive_v2` after the module reload, computes the post-edit snapshot in-process, asserts equality on the subset `{k: v for k, v in snapshot.items() if not k.startswith("bytedance-seed/")}`. Fail red (edit hasn't happened) → will turn green after step 4.

4. **Edit `derive_quality_v2.py`** — 3 additions:
   - `BENCH_TIER3["humaneval_score"] = 60.0` at line ~84
   - `BENCH_TIER2["humaneval_score"] = 40.0` at line ~98
   - Two lines in the bump loops at ~183 and ~199: `("humaneval_score", row.get("humaneval_score") or 0, BENCH_TIER<N>["humaneval_score"])`

5. **Write D1 + D2 stub-row tests** in `tests/test_derive_quality_v2_tier_lift.py`.

6. **Run D1-D4:**
   ```bash
   .venv/bin/pytest scripts/kilo-benchmarks/tests/test_derive_quality_v2_tier_lift.py -xvs
   ```
   Expected: 4/4 pass.

7. **If D3 fails (non-Seed tier flip detected) — SELF-SERVICE threshold recalibration with a floor.** Lower `BENCH_TIER3["humaneval_score"]` by 5, keeping `BENCH_TIER2 = BENCH_TIER3 - 20`. Re-run D1-D4. Repeat until D3 passes.
   **Floor (no spiral):** if `BENCH_TIER3["humaneval_score"] < 25` (i.e., dropped below Tier 3 = 25 / Tier 2 = 5), STOP and report `BLOCKED: humaneval_score thresholds cannot satisfy both D1/D2 (tier lift) and D3 (non-regression) — the existing tier ladder is already sensitive to models with pass@1 ≥ 25, which means an unrelated column is co-signalling and needs isolation`. Do NOT proceed to step 8 until the floor issue is understood + resolved (either as a fresh design decision the user makes, or by identifying which existing column is co-signalling and gating it).

8. **Append `bytedance-seed/seed-` to `FAMILIES`.** Edit `rank_coding_subagents.py:53-65`. Test D4 confirms match.

9. **Regenerate `CODING_SUBAGENT_SELECTION.md`:**
   ```bash
   .venv/bin/python scripts/kilo-benchmarks/rank_coding_subagents.py
   ```
   Expected: 4 new rows for Seed models — but their `humaneval_score` is still NULL until Phase E. Rows appear at the bottom of the coding-selection MD until Phase E rerun.

### Phase D closing sequence

1. Run D1-D4 → 4/4 green (D3 gating; step 7 self-service if needed).
2. `check_doc_sync.py` scoped to Phase D → CODING_SUBAGENT_SELECTION.md is auto-updated, no new WARN.
3. **`/fabrik-review` on Phase D's diff** — pool-dispatch template per Phase B closing sequence step 3. Highest-risk lens: (a) tier threshold picks (60/40 or the recalibrated floor) — did the review surface any edge case D3 didn't cover? (b) FAMILIES prefix boundary — does `bytedance-seed/seed-` accidentally match non-Seed IDs? (c) is the snapshot tool deterministic (row iteration order can shift results between runs)?
4. **Commit Phase D** (explicit paths + trailers):
   ```bash
   git add scripts/kilo-benchmarks/derive_quality_v2.py scripts/kilo-benchmarks/rank_coding_subagents.py scripts/kilo-benchmarks/microbench_coding_tier_snapshot.py scripts/kilo-benchmarks/tests/test_derive_quality_v2_tier_lift.py docs/reference/kilo/CODING_SUBAGENT_SELECTION.md
   git diff --cached --name-only
   git commit -m "$(cat <<'EOF'
   feat(kilo-benchmarks): Phase D — humaneval_score tier ladder + bytedance-seed FAMILIES + non-regression guard

   Agent-Role: primary
   Agent-Phase: D
   Agent-Context: BENCH_TIER3/TIER2 add humaneval_score threshold; D3 asserts zero non-Seed tier flips (blast-radius guard); FAMILIES appends bytedance-seed/seed- prefix; CODING_SUBAGENT_SELECTION.md regenerated with 4 Seed rows (scores still NULL until Phase E)

   Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
   EOF
   )"
   ```

## Phase E — Live bench run against 4 Seed models

**Purpose:** The actual ~$2.66 spend + ~30 min wall clock — invoke the runner against the 4 Seed targets and populate their `humaneval_score` + `coding_score`.

### Interfaces

**Consumes:** Phases A-D (runner + DB write path + tier ladder all wired).
**Produces:** 4 rows in `agents` with non-NULL `humaneval_score` (0-100 scale), non-NULL `coding_score`, non-NULL `last_verified = date('now')`.

### Behavior Contract (this phase)

- **E1**: After the bench run, all 4 Seed models have `humaneval_score IS NOT NULL AND humaneval_score BETWEEN 0 AND 100`. (Given: post-run DB; When: SELECT; Then: 4 rows meet the criterion.)
- **E2**: `coding_score` is populated on the same 4 rows and ≈ mean of the 4 pass@1 sub-scores. (Given: post-run DB; When: SELECT; Then: `coding_score BETWEEN 0 AND 100` on all 4 rows.)
- **E3**: `CODING_SUBAGENT_SELECTION.md` after re-running `rank_coding_subagents.py` contains all 4 Seed model rows.
- **E4**: Total OR spend for the run (via `openrouter.ai/api/v1/generations` audit trail) is ≤ $5 (well above the projected $2.66 but under the sum of per-model cost caps).

### Steps

1. **Silence any noisy watchdogs / alerts** (per feedback rule: silence alerts before downtime > 2 min). Skip this if no downtime alerts fire on this box for `microbench_or_models.py`-class runs (they don't — hub is stateless from an alerting POV).

2. **Confirm evalplus CLI runnable:**
   ```bash
   .venv/bin/python -m evalplus.evaluate --help 2>&1 | head -5
   ```
   Expected: usage line printed.

3. **Live run (background, per CLAUDE.md — foreground commands likely >30s use `run_in_background=true`):**
   ```bash
   .venv/bin/python scripts/kilo-benchmarks/microbench_coding.py \
       --models bytedance-seed/seed-1.6-flash,bytedance-seed/seed-2.0-mini,bytedance-seed/seed-1.6,bytedance-seed/seed-2.0-lite \
       --datasets humaneval,mbpp \
       --cost-cap 5 \
       2>&1 | tee /tmp/microbench_coding_$(date +%s).log
   ```
   Expected wall clock: ~30 min. Monitor the tail of the log; the runner should print progress per unit as `run_agents` returns each.

4. **Validation gate — DB inspection (E1 + E2):**
   ```bash
   .venv/bin/python -c "
   import sqlite3
   from datetime import datetime, UTC
   conn = sqlite3.connect('scripts/kilo-benchmarks/kilo_agents.db')
   rows = conn.execute(
       'SELECT id, humaneval_score, coding_score, last_verified FROM agents '
       \"WHERE id LIKE 'bytedance-seed/%'\"
   ).fetchall()
   for r in rows:
       print(r)
   assert len(rows) == 4, f'expected 4 Seed rows, got {len(rows)}'
   today_utc = datetime.now(UTC).date().isoformat()
   for id_, he, cs, lv in rows:
       assert he is not None, f'{id_}: humaneval_score still NULL'
       assert 0 <= he <= 100, f'{id_}: humaneval_score {he} out of 0-100 range'
       assert cs is not None, f'{id_}: coding_score still NULL'
       assert 0 <= cs <= 100, f'{id_}: coding_score {cs} out of 0-100 range'
       assert lv == today_utc, f'{id_}: last_verified {lv} != {today_utc} (UTC)'
   print('E1+E2 PASS')
   "
   ```
   Expected: `E1+E2 PASS`.

5. **Regenerate the selection MD (E3):**
   ```bash
   .venv/bin/python scripts/kilo-benchmarks/rank_coding_subagents.py
   grep -c 'bytedance-seed/seed-' docs/reference/kilo/CODING_SUBAGENT_SELECTION.md
   ```
   Expected: 4 matches.

6. **Cost audit (E4).** Grep the runner's log for the `TOTAL_SPEND_USD:` emission (contracted by Phase C main() step 4):
   ```bash
   grep -oE '^TOTAL_SPEND_USD: [0-9]+\.[0-9]+$' /tmp/microbench_coding_*.log | tail -1 | awk '{print $2}' | python3 -c "
   import sys
   spend = float(sys.stdin.read().strip())
   assert spend <= 5.0, f'TOTAL_SPEND_USD {spend} exceeds \$5 cap'
   print(f'E4 PASS — total spend \${spend:.2f}')
   "
   ```
   Expected: `E4 PASS — total spend $<n.nn>`. If the grep matches ZERO lines, main() failed to emit the contracted line — treat as a Phase C regression, not a Phase E issue.

### Phase E closing sequence

1. Run E1-E4 validation → all green.
2. `check_doc_sync.py` on Phase E's diff (CODING_SUBAGENT_SELECTION.md regenerated) — no WARN.
3. **`/fabrik-review` on Phase E's diff** — pool-dispatch template per Phase B closing sequence step 3. Highest-risk lens for Phase E (data-only phase): (a) does the observed pass@1 distribution suggest memorization vs generalization (any Seed model scoring >0.95 on plain HumanEval is a red flag); (b) did the tier reach actually happen as predicted at Phase D's threshold picks, or does the observed range indicate the thresholds need retuning; (c) any AgentResult with an ERROR/timeout status the runner silently swallowed.
4. **Commit Phase E** — commit the regenerated `CODING_SUBAGENT_SELECTION.md` + a tabular summary of the bench results in the commit body:
   ```bash
   git add docs/reference/kilo/CODING_SUBAGENT_SELECTION.md
   git diff --cached --name-only
   git commit -m "$(cat <<'EOF'
   feat(kilo-benchmarks): Phase E — live bench populates 4 Seed models

   Agent-Role: primary
   Agent-Phase: E
   Agent-Context: humaneval_score + coding_score populated for seed-1.6-flash, seed-2.0-mini, seed-1.6, seed-2.0-lite via microbench_coding.py; CODING_SUBAGENT_SELECTION.md regenerated with 4 Seed rows now visible in ranking; total spend $<n.nn> (≤ $5 cap)

   Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
   EOF
   )"
   ```

## Phase F — Docs + convergence

**Purpose:** Doc Sync Matrix triggers + `/fabrik-docs-review` to prove correctness (not just presence).

### Interfaces

**Consumes:** all prior phases' deliverables.
**Produces:** updated CHANGELOG, INDEX, FEATURES, and a docs-review no-op pass.

### Behavior Contract (this phase)

- **F1**: `CHANGELOG.md` under `## [Unreleased]` gains a new `### Added — Coding microbench runner (2026-07-10)` entry APPENDED atop `[Unreleased]` (do NOT reset the section — plan-1 also targets `[Unreleased]`).
- **F2**: `INDEX.md` gains a row for each new script created by this plan (`microbench_coding.py`, `microbench_coding_tier_snapshot.py`, plus their test files).
- **F3**: `docs/FEATURES.md` gains a one-line entry for the local-coding-bench capability under an "Internal tooling" section (create the section if absent).
- **F4**: `/fabrik-docs-review` reaches a no-op pass — verified by grepping the final review's last-line status marker (see step 5).

### Steps

1. Write CHANGELOG entry citing spec + plan file. Append atop `[Unreleased]`, do NOT reset the section.
2. Add INDEX rows for each new script.
3. Add FEATURES line under "Internal tooling" heading (grep first — if absent, create the heading).
4. Run `python scripts/enforcement/check_doc_sync.py` → expect success.
5. Invoke `/fabrik-docs-review scripts/kilo-benchmarks/microbench_coding.py docs/reference/kilo/CODING_SUBAGENT_SELECTION.md CHANGELOG.md INDEX.md docs/FEATURES.md` via the Skill tool. **No-op signal:** the review reaches convergence when its final message (per `fabrik-docs-review` skill contract) includes a Pass Ledger row with `edits: 0` AND `md5(start) == md5(end)` on the last pass. If it makes edits, iterate — the skill self-loops per its own termination contract.

### Phase F closing sequence

1. `check_doc_sync.py` → success.
2. `/fabrik-docs-review` → md5-identical no-op pass (see step 5).
3. **`/fabrik-review` on Phase F's doc diff** — pool-dispatch template per Phase B closing sequence step 3. Highest-risk lens: stale claim / dead link / misattributed fact / any new `.py` file missing the `# AFTER-EDIT:` header (`scripts/enforcement/check_script_headers.py` WARNs).
4. **Commit Phase F** (explicit paths + trailers):
   ```bash
   git add CHANGELOG.md INDEX.md docs/FEATURES.md
   git diff --cached --name-only  # verify shared files carry ONLY this plan's rows, not plan-1's
   git commit -m "$(cat <<'EOF'
   docs(kilo-benchmarks): Phase F — CHANGELOG + INDEX + FEATURES + docs-review no-op

   Agent-Role: primary
   Agent-Phase: F
   Agent-Context: Doc Sync Matrix triggers landed; fabrik-docs-review converged to md5-identical no-op

   Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
   EOF
   )"
   ```
5. **Full-plan final gate:**
   ```bash
   python scripts/final_gate.py --json | python -c "import sys, json; d=json.load(sys.stdin); print(d['status']); sys.exit(0 if d['status']=='success' else 1)"
   ```
   Expected: `success`.
6. Run `python scripts/enforcement/check_convergence.py` → success.

## Evidence (grounded citations from this session)

Per-phase real `path:line` reads + command-output blocks:

**Phase A:**
- `pyproject.toml:12-23` — dep list location (verified this session)
- `/usr/bin/bwrap --version → bubblewrap 0.9.0` (verified this session)
- `scripts/kilo-benchmarks/kilo_agents_db.py:228-229` — `humaneval_score` + `coding_score` declared REAL (verified this session)

```
$ /usr/bin/bwrap --version
bubblewrap 0.9.0
$ ls /opt/fabrik/scripts/kilo-benchmarks/libs/
__init__.py  web_scrape
# ⚠️ subagents/ is MISSING — must be vendored in Phase A step 2b
```

**Phase B:**
- `libs/subagents/subagents/agent.py:504-539` — `run_agents(specs, *, repo, max_concurrency=4, ...)` sync signature (G1 grounder verified)
- `libs/subagents/subagents/agent.py:509` — `run_agents`'s `max_concurrency: int = 4` default (line 431 is the same default on `arun_agents`, the async twin — both = 4)
- `libs/subagents/subagents/sandbox.py:121` — `wrap_command(argv: list[str], workdir: str) -> list[str]` (G1 verified)
- `libs/subagents/subagents/__init__.py:42` — `run_agents` first entry in `__all__` (G1 verified)

```
$ grep -n 'def run_agents\|def wrap_command\|"run_agents"' /opt/fabrik-lib/subagents/subagents/*.py | head -5
/opt/fabrik-lib/subagents/subagents/__init__.py:42:    "run_agents",
/opt/fabrik-lib/subagents/subagents/agent.py:504:def run_agents(specs: list[AgentSpec], *, repo: str, ledger_path: str | None = None, max_concurrency: int = 4, ...
/opt/fabrik-lib/subagents/subagents/sandbox.py:121:def wrap_command(argv: list[str], workdir: str) -> list[str]:
```

**Phase C:**
- `scripts/kilo-benchmarks/microbench_or_models.py:70` — `RECENCY_WINDOW_DAYS = 30` (freshness-window sibling constant)
- `scripts/kilo-benchmarks/microbench_or_models.py:286-291` — UTC cutoff comment + `cutoff = (datetime.now(UTC).date() - timedelta(days=RECENCY_WINDOW_DAYS)).isoformat()` (mirror this in `is_fresh`)
- `scripts/kilo-benchmarks/scrape_benchlm.py:70` — sole `weighted_coding` source (`category_scores.get("coding")`)

```
$ grep -n 'RECENCY_WINDOW\|datetime.now(UTC).date' /opt/fabrik/scripts/kilo-benchmarks/microbench_or_models.py | head -5
70:RECENCY_WINDOW_DAYS = 30
286:    Cutoff uses `datetime.now(UTC).date()` to match `_write_result` which
291:    cutoff = (datetime.now(UTC).date() - timedelta(days=RECENCY_WINDOW_DAYS)).isoformat()
$ grep -n 'weighted_coding' /opt/fabrik/scripts/kilo-benchmarks/scrape_benchlm.py
70:    weighted_coding = category_scores.get("coding")
```

**Phase D:**
- `scripts/kilo-benchmarks/derive_quality_v2.py:84-97` — `BENCH_TIER3` dict; `derive_quality_v2.py:98-109` — `BENCH_TIER2` dict (G1 verified — actual span is :84-109; note the ranges divide at line 98)
- `scripts/kilo-benchmarks/derive_quality_v2.py:172-202` — the two bump loops (Tier-3 loop :172-186, Tier-2 loop :187-202; G1 verified — actual end line is 202, plan text says :172-201 within 5-line drift window)
- `scripts/kilo-benchmarks/rank_coding_subagents.py:53-65` — `FAMILIES` tuple (5 current prefixes: z-ai/glm-, moonshotai/kimi-, minimax/minimax-, deepseek/, qwen/qwen3-coder-)
- `scripts/kilo-benchmarks/rank_coding_subagents.py:98` — `AUTO_OUTPUT_PRICE_CEILING = 1.5`

```
$ sed -n '84,86p;98,100p' /opt/fabrik/scripts/kilo-benchmarks/derive_quality_v2.py
BENCH_TIER3 = {
    "arena_elo": 1500,
    "tbench": 78.0,
BENCH_TIER2 = {
    "arena_elo": 1400,
    "tbench": 60.0,
$ grep -n 'AUTO_OUTPUT_PRICE_CEILING\|^FAMILIES = ' /opt/fabrik/scripts/kilo-benchmarks/rank_coding_subagents.py
53:FAMILIES = (
98:AUTO_OUTPUT_PRICE_CEILING = 1.5
```

**Phase E:**
- Live OR API verified this session at `https://openrouter.ai/api/v1/models` (G1 external-dep verification returned OK; also verified `qwen/qwen3-coder-flash` orchestrator model is live)
- 4 Seed model pricing (G1 verified live): seed-1.6-flash $0.075/$0.30; seed-2.0-mini $0.10/$0.40; seed-1.6 $0.25/$2.00; seed-2.0-lite $0.25/$2.00 — all `via_openrouter=1 AND status='active'`

```
$ curl -s https://openrouter.ai/api/v1/models | python3 -c "
import sys, json
ids = {m['id'] for m in json.load(sys.stdin)['data']}
targets = {'bytedance-seed/seed-1.6-flash','bytedance-seed/seed-2.0-mini','bytedance-seed/seed-1.6','bytedance-seed/seed-2.0-lite','qwen/qwen3-coder-flash'}
missing = targets - ids
print('all_live:', not missing, 'missing:', missing)
"
all_live: True missing: set()
```

**Phase F:**
- `CLAUDE.md` Doc Sync Matrix — triggers: new file → INDEX, feature → FEATURES, code/deps → CHANGELOG; script coupling header `# AFTER-EDIT:` required on every `scripts/**/*.py`

```
$ grep -c '^| ' /opt/fabrik/CLAUDE.md | head -1  # count Doc Sync Matrix rows
14
$ grep -n 'AFTER-EDIT' /opt/fabrik/CLAUDE.md | head -1
121:- **Script coupling header:** every `scripts/**/*.py` carries a `# AFTER-EDIT: <files to update when this script changes | none>` line
```

## Self-audit

**(a) Coverage — every "What we already agreed" mapped to a phase:**

| Spec §Goal / §Success criterion | Delivered by |
|---|---|
| Runs HumanEval + MBPP via EvalPlus | Phase A (dep install + fixture probe) + Phase B (build_specs → shell → evalplus.evaluate) |
| 4 Seed target models (UI-TARS excluded) | Phase B `DEFAULT_MODELS` const |
| Parallel dispatch via `run_agents(specs, repo=…, max_concurrency=len(specs))` | Phase B `build_specs` (spec construction) + Phase C `main` (dispatch call) |
| Vendored `libs.subagents` reachable at `scripts/kilo-benchmarks/libs/subagents/` | Phase A step 2b (vendor `cp -r`) |
| Bwrap sandbox layer | Phase A probe (step 4) + Phase B B1 regression pin (`wrap_command` end-to-end) |
| Cost cap $5/model | Phase B `AgentSpec.max_cost_usd=5.0` + Phase C `--cost-cap 5` argparse default + Phase E E4 log-grep |
| Idempotent 60-day freshness | Phase C `is_fresh` (UTC-anchored) + C4/C5 tests |
| Writes `humaneval_score` + `coding_score`, NOT `weighted_coding` | Phase C `write_scores` + C1 TDD (explicit column-scope) |
| 0-100 scale | Phase C C2/C3 tests |
| `parse_eval_results` per-dataset + `merge_dataset_results` composite | Phase B (both authored; B3 + B4 tests) |
| Total-spend emission `TOTAL_SPEND_USD:` | Phase C main() step 4 + C8 test (mocked-cost path) + Phase E E4 log grep |
| `main` argparse contract (--models/--datasets/--cost-cap/--force/--dry-run/--ttl-days) | Phase C Interfaces block + C6 test (--dry-run) + C7 test (model rejection) |
| `derive_quality_v2` tier lift | Phase D BENCH_TIER dict edits + D1/D2 stub-row tests |
| Non-regression on non-Seed models | Phase D snapshot tool (`microbench_coding_tier_snapshot.py`) + D3 test + step-7 self-service floor |
| `FAMILIES` append + CODING_SUBAGENT_SELECTION.md regen | Phase D D4 + Phase E E3 |
| Orchestrator model live-verify (`qwen/qwen3-coder-flash`) | Phase A step 2c live curl probe |
| Live bench run + per-model cost audit | Phase E E1 + E2 + E4 |
| Docs sync (Doc Sync Matrix triggers) | Phase F F1-F4 |
| `/fabrik-docs-review` md5-identical no-op | Phase F step 5 + F4 |

Zero gaps.

**(b) Cross-phase signature consistency:**
- `build_specs(target_models, datasets, work_dir, orchestrator=ORCHESTRATOR_MODEL) → list[AgentSpec]` — produced Phase B, consumed Phase C `main` — consistent (orchestrator has a default so `main` can call without repeating it).
- `parse_eval_results(results_json) → dict[str, float]` with keys `{base, plus}` — produced Phase B (per-dataset scope), consumed Phase C `main` per-dataset before merge. **Signature scope corrected in this review round** (was previously claimed to return 4 keys — now correctly documented as 2 keys per dataset).
- `merge_dataset_results(humaneval, mbpp) → dict[str, float]` with keys `{base, plus, mbpp_base, mbpp_plus}` — **newly added in this review round** to bridge the per-dataset → composite gap that would have forced Phase C's `main` to invent an ad-hoc merge.
- `write_scores(conn, model_id, scores) → None` — reads keys `{base, plus, mbpp_base, mbpp_plus}` from the merged dict, produced Phase C, consumed Phase E's live run — consistent with `merge_dataset_results` output.
- `is_fresh(conn, model_id, ttl_days=60) → bool` — Phase C new function, mirrors `microbench_or_models.py:70,286-291` UTC-anchored pattern (NOT `date.today()`).
- `main(argv=None) → int` — produced Phase C (moved from Phase B in this review round; Phase B behaviors tested `main --dry-run` before `main` was authored, which was a Phase-order defect).
- `derive_v2(row, or_record) → (tier, evidence)` — existing function; Phase D adds `humaneval_score` bump-loop rows without changing signature; snapshot tool + D3 test consume unchanged.

No signature drift after this review round's Interface corrections.

**Grounding passes run:**
- **Plan drafting (turn 1):** `select_rules.py` → 19 ACTIVE + 31 AVAILABLE; picked 6 relevant packs into Context Ledger. Verified `pyproject.toml` python floor, `kilo_agents_db.py` schema (columns REAL, ZERO existing writers), `derive_quality_v2.py:84-109,172-201` structure, `rank_coding_subagents.py:53-65,98`, `libs.subagents.run_agents` signature (via spec-review Pass 7 grounder, same session), `bwrap 0.9.0` installed, `evalplus` NOT installed.
- **`/fabrik-plan-review` Pass 1 (this turn):** 3 parallel independent grounders (G1 path:line + external deps, G2 structural pillars + Doc Sync Matrix, G3 gates + Behavior Contracts + residuals) — merged 18 unique confirmed defects (1 BLOCKING = missing `libs/subagents/` vendor step; 4 Interface mismatches on `parse_eval_results`/`merge`/`main`/argparse; 5 gate defects; 3 residual defects; 5 structural defects). All 18 fixed in this round.
- Refuted 1 finding as false positive (G1: agent.py:431 vs :509 — both defaults = 4, semantic claim held; kept :509 as the more precise cite for `run_agents`).

Fixed point: **not yet — Pass 1 made 18 edits + I owe Pass 2.** Pass 2 will run after this batch lands.

## Residual unknowns

### Resolved (during this plan drafting)

- **Phase F FEATURES.md entry vs `docs/FEATURES.md` triggering criterion.** The Doc Sync Matrix says "Feature shipped → `docs/FEATURES.md`". A local-bench utility is arguably infrastructure, not a shipping feature. Resolution: include a one-line entry under an "Internal tooling" section (self-service default per CLAUDE.md Question bar — cosmetic, reversible).
- **Orchestrator model for the pool AgentSpec.** `AgentSpec.model` field must be set for `run_agents`. Chose `qwen/qwen3-coder-flash` (cheap Auto-tier code model per `rank_coding_subagents.py` current output; ~$0.10/Mtok output). Any other cheap Auto-tier `pick_models("code")` result is fine; hardcoded for reproducibility.

### Still-open (each has a self-service resolution step — none block execution)

1. **Phase D threshold calibration (60 / 40).** Spec §Still-open residual 2. **Self-service resolution at Phase D step 7:** if D3 (non-regression) fails because thresholds cause tier flips on non-Seed rows, lower `BENCH_TIER3["humaneval_score"]` by 5, keep `BENCH_TIER2 = BENCH_TIER3 - 20`, re-run tests. Iterate until D3 passes. **Floor:** if `BENCH_TIER3 < 25`, halt with `BLOCKED` — signals an unrelated column is co-signalling and needs isolation before the tier lift can be sensibly added. Do NOT proceed until the co-signal is understood.

2. **`docs/FEATURES.md` structure.** File may or may not have an "Internal tooling" section. **Self-service resolution at Phase F step 3:** `grep -n '^## Internal tooling' docs/FEATURES.md` — append under it if the heading exists; else create a new heading at the file's end. No user question needed.

3. **EvalPlus fixture shape drift.** Spec assumes `{"pass@1": {"base": ..., "plus": ...}}` — Pass 1's Phase B step 1 HARD PROBE (run evalplus on 1 problem, cat the JSON, commit as fixture) resolves it authoritatively; if the shape differs, adjust `parse_eval_results` + fixture together, re-run B3. Cost: <$0.01. **Self-service, non-blocking.**

**Zero cross-AI dependencies, zero unanswered execution-blocking questions.**

## Handoff

**Next command (this turn, automatic):** `/fabrik-plan-review docs/development/plans/2026-07-10-plan-2-coding-microbench-runner.md`.

**After convergence:** `/fabrik-execute-plan docs/development/plans/2026-07-10-plan-2-coding-microbench-runner.md` — user-triggered per plan-lifecycle convention.
