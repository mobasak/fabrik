# Coding-performance benchmark (LiveCodeBench, direct dispatch) — build + wire into coding-subagent selection

Status: CONVERGED
Date: 2026-07-19
Spec: docs/superpowers/specs/2026-07-19-coding-benchmark-livecodebench-direct-design.md (CONVERGED)
Owner-agent: primary

Build a **contamination-free, uniform `pass@1`** coding ranking of the same 57 models already graded for
review, then wire the measured signal into coding-subagent selection so `pick_models("code")` ranks on
**measured ability**, not the current sparse proxy patchwork. The tool is an on-demand CLI
(`microbench_coding_direct.py`), parallel to the shipped `microbench_review.py`; the real ~$12–18 57-model
run is an **operator action after the build** (like the review bench's real $3.28 run) — **this plan builds +
tests + wires with mocked dispatch and a tiny fixture corpus, spending $0**.

---

## Global Constraints (every phase inherits — verbatim)

- **Isolation (spec:110-111):** all new code in `scripts/kilo-benchmarks/microbench_coding_direct.py`. **Do
  NOT touch `microbench_coding.py`** (the pool-coupled EvalPlus bench, 27,924 B — a sibling's/prior file).
  Format **only files this plan owns** — never `ruff format <glob>` (it contaminates sibling files; a shared-tree violation hit live last session).
- **Transport = VENDOR `fabrik-lib/ai-consult` `run()`/`run_many()` (spec:32-37, 80-81).** Never a direct
  vendor SDK; never re-implement dispatch (the `_direct_call`/`run_direct` reinvention in `microbench_review.py`
  is tracked tech-debt — do not copy it). Send `body={"usage": {"include": True}}` → real billed
  `Result.cost_usd`.
- **Grading = VENDOR (external) LiveCodeBench `lcb_runner` (spec:80).** Do not reimplement sandboxed test
  execution. Model-generated code is **untrusted** — it runs ONLY inside `lcb_runner`'s own sandbox harness.
- **DB = the existing hub-local `kilo_agents.db`** (`scripts/kilo-benchmarks/kilo_agents.db`, sqlite). This is a
  **WSL-only analytics store for a CLI that deploys nowhere** — 12-Factor X ("no SQLite") does **not** bind
  (spec:99-102); it is the established pattern across the `kilo-benchmarks` scripts. No `postgres-main` here.
- **No deps-file edits.** `lcb_runner` installs into a **sibling venv** (`scripts/kilo-benchmarks/.lcb-venv/`),
  NOT the project `.venv` / `pyproject.toml` (heavy transitive deps; keeps the project env clean). The plan
  never edits `pyproject.toml`/`requirements.txt`/`uv.lock`.
- **Cost discipline (spec:44-45, 108-109).** Tests spend **$0** (mocked `ai-consult` + a 1–2 problem fixture).
  `--cost-cap` is wired to `ai-consult` `run_many(max_cost_usd=…)` — the **vendor's shared-budget dispatch gate**
  (`run.py:417,447-453`), NOT a re-implemented sum-and-abort (that reinvention is exactly what the spec warns
  against, spec:85-91). `--probe` (1–2 problems × models, real tokens) sizes the real run first. **No unattended
  unbounded spend.**
- **Heavy local jobs are capped** — the `lcb_runner` install + any real grading run wraps in
  `systemd-run --scope -p CPUQuota=… -p MemoryMax=…` (no `--user` bus in WSL); never `pkill -f` on this shared box.
- **Secrets from env** — `OPENROUTER_API_KEY` via `os.getenv` (ai-consult reads it); never hardcoded.
- **Naming = kebab-case** for files (Python module snake_case exception); tables snake_case.
- **Provenance:** every commit this plan makes carries `Agent-Role` + `Agent-Phase` + `Agent-Context` trailers
  (standalone execution → `orchestrator`/`review-fix` roles per phase; see the closing sequence).

---

## Context Ledger

| Source | What binds | Grounded ref |
|---|---|---|
| **spec** (CONVERGED) | goal, approach, vendor verdict, cost discipline, rejected alternatives | `docs/superpowers/specs/2026-07-19-coding-benchmark-livecodebench-direct-design.md:1-145` |
| `fabrik-lib/ai-consult` `run()` | single call → `Result(text, model, provider, usage, cost_usd, error)`; kwargs incl. `body`, `max_cost_usd` | `ai_consult/run.py:316-333` (run sig), `:68-92` (`Result`) |
| `fabrik-lib/ai-consult` `run_many()` | sync fan-out over `arun_many`, ordered, partial-tolerant (`Result(error=…)` per failed slot) | `ai_consult/run.py:518-519`, docstring `:10-18` |
| `fabrik-lib/ai-consult` `Call` | one batch member: `Call(model, messages, body=None, liveness=None, tags=None, persist=True)` | `ai_consult/run.py:97-104` |
| **LiveCodeBench `lcb_runner`** (external VENDOR) | contamination-free window (`--release_version release_v1..v6`); `pass@1` via real sandboxed test execution; grade externally-produced generations via `lcb_runner/runner/custom_evaluator.py --custom_output_file` = a JSON `list` len==len(benchmark), ordered by question_id (exact per-item shape — `list[str]` vs `list[dict]` with `code_list`+`question_id` — read from source at Phase A step 4); install = git-clone + `pip install -e .` | spec:71 (grounded live 2026-07-19: github.com/LiveCodeBench/LiveCodeBench README + custom_evaluator.py + parser.py) |
| `microbench_review.py` (parallel to mirror) | `ModelScore` (grade cuts, cost_per_1k, tokens_per_s, median_latency, is_measured), `persist_metrics` (`model_review_metrics` DDL), `report_stored`, argparse | `microbench_review.py:290-352` (ModelScore), `:662-722` (persist_metrics + DDL), `:725-765` (report_stored) |
| `build_task_baselines.py` | `model_task_baseline` DDL (PK model_id,task_type; baseline 0-5, pass_rate 0-1, source); `load_review_metrics` (latest-per-model JOIN) + `review_eligible`; `build()` currently sources task_type='code' from `tbench_leaderboard_results` | `build_task_baselines.py:59-71` (DDL), `:108-158` (load/eligible), `:161-201` (build) |
| `rank_coding_subagents.py` | emits `CODING_SUBAGENT_SELECTION.md`; overrides the Doc↔Code grade with the measured **review** grade (`†`, `doc_grade_measured`); sorts by `-score` | `:287-346` (`_rows_from_db` + sort), `:388` (grade legend), `:51` (OUT_PATH) |
| `AGENTS.md` — subagent pool / flywheel | `pick_models("code")` reads `model_task_baseline(task_type='code')` as its prior; measured > scraped | agents-fabrik map + `62-using-subagents.md` |
| `.windsurf/rules/core/45-testing-strategy.md` | one test per user-observable behavior, risk-ordered, TDD the risky path | ACTIVE (per `select_rules.py`) |
| `.windsurf/rules/core/10-python.md` | stdout-only logging, env config, no silent failures | ACTIVE |

**fabrik-lib consult:** transport → **VENDOR ai-consult** (no build). Corpus+grading → **VENDOR (external) lcb_runner**
(no fabrik-lib module; the contamination-free standard). Persistence/report → **BUILD (thin)**, project-specific
benchmark schema → **not** a fabrik-lib candidate (spec:82). No new fabrik-lib module proposed.

---

## Design decisions settled here (spec goal resolves them; each flagged — say if you'd rather otherwise)

1. **Model set = the same models review measured** → default to `SELECT DISTINCT model_id FROM
   model_review_metrics` (apples-to-apples with the shipped review table **by construction** — whatever review
   measured; today exactly **57**, verified 2026-07-19). ⚠️ The table holds only `is_measured` review models
   (`microbench_review.py:676` skips unmeasured), so the count tracks the review run, not a hardcoded 57 — the
   tool **logs the resolved model count at start** and warns if it differs from the review table's row count, so
   a shortfall is never silent. `--models …` overrides for an explicit set. *Say if you'd rather pin an explicit
   canonical list.*
2. **`pass@1 → grade`** reuses review's exact mapping: `score5 = pass@1 * 5` → the existing letter cuts
   (`microbench_review.py:317-332`). One scale across both tables.
3. **`pick_models("code")` ranks on measured coding ability (the spec's explicit goal, spec:13):** the bench
   writes `model_task_baseline(task_type='code')` from measured `pass@1` (`source='livecodebench:<window>'`),
   and `build_task_baselines` gives that measured baseline **precedence over the terminal-bench scraped
   `code` baseline** (else the daily refresh clobbers it — parallel to how review is handled).
4. **CODING_SUBAGENT_SELECTION.md surfaces the measured CODING grade (`†`) + a `pass@1 %` column — display,
   not a re-sort.** ⚠️ **Grounded (Pass 1/2):** the doc's sort key is `_compose_score(d)`
   (`rank_coding_subagents.py:329,346`), **not** `doc_grade`, and `_compose_score` (`:208-243`) reads only the
   `agents`-table benchmark columns — so overriding the displayed grade does NOT re-rank, and re-ranking would
   be an unscoped rewrite of `_compose_score` affecting all ~245 rows. **Leaner + spec-sufficient: leave the
   doc's sort untouched; the measured coding grade (`†`) + `pass@1 %` column make the signal VISIBLE, and the
   AUTHORITATIVE ranking that governs dispatch is `model_task_baseline(task_type='code')` (D3) — which
   `pick_models("code")` reads (the spec goal, spec:13).** The doc is the human-facing view of D3, not the
   selector. *Say if you'd rather ALSO re-sort the doc on measured coding (a larger `_compose_score` change).*
5. **Build/test now, spend later.** The plan delivers the tool + wiring + tests (mocked dispatch, fixture
   corpus, $0). The real 57-model run is a documented **operator** step, not a plan step.

---

## Phase A — Vendor + provision LiveCodeBench `lcb_runner` (the env-preflight that otherwise stalls execution)

**Goal:** `lcb_runner`'s `custom_evaluator` is importable + runnable in an isolated sibling venv, proven by a
probe — so no later phase discovers a missing toolchain at runtime.

### Interfaces
- **Produces:** `scripts/kilo-benchmarks/.lcb-venv/` (a Python venv with `lcb_runner` editable-installed);
  a documented invocation `"<.lcb-venv>/bin/python -m lcb_runner.runner.custom_evaluator --help"`; a
  gitignore entry for `.lcb-venv/` + the clone dir. **Consumes:** nothing.

### Steps
1. **Probe first (env preflight):** `test -d scripts/kilo-benchmarks/.lcb-venv || echo "absent → provision"`.
2. Clone + install **inside a resource-capped scope** (heavy deps):
   `systemd-run --scope -p CPUQuota=200% -p MemoryMax=4G bash -c 'git clone --depth 1 https://github.com/LiveCodeBench/LiveCodeBench scripts/kilo-benchmarks/.lcb-src && python -m venv scripts/kilo-benchmarks/.lcb-venv && scripts/kilo-benchmarks/.lcb-venv/bin/pip install -e scripts/kilo-benchmarks/.lcb-src'`
   — run via `Bash run_in_background=true` (a >30s job).
3. Add `.lcb-venv/` and `.lcb-src/` to `scripts/kilo-benchmarks/.gitignore` (never commit the vendored external
   tree or the venv).
4. **Grounding step (do before Phase B wires against it):** read `.lcb-src/lcb_runner/runner/custom_evaluator.py`
   + `lcb_runner/benchmarks/code_generation.py` and record the EXACT: `--custom_output_file` JSON schema, the
   `--release_version` flag + valid values, how a benchmark problem exposes its prompt + `question_id`, and the
   `pass@1` output location. Capture these as `path:line` into Phase B's Evidence.

### Validation gate (runnable, WSL dev)
```bash
scripts/kilo-benchmarks/.lcb-venv/bin/python -m lcb_runner.runner.custom_evaluator --help  # exit 0, prints usage
```
Expected: usage text incl. `--custom_output_file` and `--release_version`. **If the module path differs from
the spec's grounding, the Phase-A grounding step (4) captures the real one before any wiring — that is the
whole point of doing this phase first.**

### Behavior Contract (Phase A)
- **Given** a 1-problem `--custom_output_file` with one correct solution and one wrong (smallest release
  window), **When** `custom_evaluator` runs, **Then** pass@1 == 1.0 for the correct and 0.0 for the wrong
  (`tests/test_lcb_smoke.py`).
- **Given** `.lcb-venv` is absent, **When** the smoke test is collected, **Then** it skips cleanly
  (`pytest.mark.skipif`) so CI without the vendored tool stays green.
- **Mocked:** nothing — this exercises the REAL `lcb_runner` evaluator (skipped, not mocked, when the sibling venv is absent).

### Closing sequence (every phase — literal steps)
1. Run the Phase-A gate → green.
2. `python scripts/enforcement/check_doc_sync.py` — resolve any WARNING whose trigger file is in this phase's diff.
3. **`/fabrik-review`** on the changed surface (the `.gitignore` + `test_lcb_smoke.py`) — pool `minimax/minimax-m3`
   finders (`fanout("review", …, mode="read_only")`, `set_quality` back-fill) + native `fabrik-reviewer`/Opus
   (this phase touches no auth/schema — native optional but run ≥1 Opus finder per floor); refute → prove-before-fix;
   iterate to a `found:0, fixed:0` no-op.
4. Commit (explicit paths) with `Agent-Role: orchestrator`, `Agent-Phase: A`. Stage the plan file (mark Phase A ✅).

---

## Phase B — `microbench_coding_direct.py`: corpus → direct generate → grade → `pass@1`

**Goal:** the benchmark CLI produces one `pass@1` per model over a fixed LiveCodeBench window via
direct `ai-consult` dispatch with real billed cost, mockably testable at $0.

### Interfaces
- **Consumes:** `lcb_runner` (Phase A) — `custom_evaluator` + benchmark loader; `ai-consult` `run_many`/`Call`/`Result`.
- **Produces:** `scripts/kilo-benchmarks/microbench_coding_direct.py` exposing:
  - `load_corpus(release_version: str, limit: int|None) -> list[Problem]` (`Problem(question_id, prompt)`),
  - `generate(models: list[str], corpus, *, cost_cap: float, max_tokens: int, max_concurrency: int) -> dict[str, list[Result]]`
    (via `run_many([Call(model, messages=[{"role":"user","content":prompt}], body={"usage":{"include":True}})…], max_cost_usd=cost_cap, max_concurrency=max_concurrency)`),
  - `grade(gens: dict[str,list[Result]], corpus) -> dict[str, CodingScore]` (writes each model's ordered
    `--custom_output_file`, invokes `.lcb-venv` `custom_evaluator`, parses `pass@1`),
  - `CodingScore` dataclass — `pass_at_1: float`, `score5` (`pass_at_1*5`), `grade` (reuse review's cuts),
    `cost_usd`, `cost_per_1k`, `p50_latency_s`, `tokens_per_s`, `n_problems`, `n_err`, `is_measured`
    (`n_problems - n_err >= 3`),
  - CLI: `--models`, `--release-version`, `--limit`, `--probe`, `--cost-cap`, `--all`, `--report`.

### Steps (highest-risk TDD first)
1. **TDD the grading contract (highest risk — the external `custom_output_file` format):** write
   `tests/test_microbench_coding_direct.py::test_grade_formats_custom_output_file` — feed a stub of 2 problems
   + 2 generations, assert `grade()` writes a JSON `list` of length 2 ordered by `question_id` (per the Phase-A
   grounded schema) and parses the evaluator's `pass@1`. Run it **red first** (evaluator mocked), implement
   `grade()` to green.
2. Implement `load_corpus` (delegates to the `.lcb-venv` benchmark loader for the chosen `--release-version`;
   `--limit` slices to ~50).
3. Implement `generate` via `ai-consult.run_many(calls, max_cost_usd=cost_cap, max_concurrency=N)` with
   `body={"usage":{"include":True}}`. **The cap is the vendor's shared-budget DISPATCH GATE (`run.py:417,447-453`),
   NOT a re-implemented sum-and-abort** — that reinvention is impossible with one blocking `run_many` (it returns
   only after all dispatch, `:502-515`) and is the `_direct_call` anti-pattern the spec warns against. Overshoot
   is bounded by `≤ max_concurrency` in-flight calls (`:444-446`); cap-stopped calls return
   `Result(error='cost_cap_exhausted')` (`:449-452`). Exclude errored/cap-stopped slots from `n_problems`
   (count `n_err`, never `pass=0` — a 404/timeout/cap-stop is not a wrong answer; mirror `microbench_review`
   MIN_MEASURED at `:291-303`).
4. Implement `CodingScore` reusing review's `grade()` cuts + `cost_per_1k`/`tokens_per_s`/`median_latency`
   shapes (`microbench_review.py:317-352`).
5. Implement `--probe` (1–2 problems × models → print real tokens+cost/model → estimated full-run total) and
   `--report` (print the latest stored table).

### Validation gate
```bash
.venv/bin/python -m pytest scripts/kilo-benchmarks/tests/test_microbench_coding_direct.py -q   # all green, $0
.venv/bin/python scripts/kilo-benchmarks/microbench_coding_direct.py --help                    # exit 0
```

### Behavior Contract (Phase B) — one behavior per acceptance criterion
- **Given** some generations returned as errored/empty (`Result.error` set), **When** `grade()` runs, **Then** those slots count as `n_err` (never `pass=0` — a model we failed to reach ≠ a wrong answer) and `is_measured` is gated at `< 3` measured problems.
- **Given** a `--cost-cap` passed to `run_many(max_cost_usd=…)` and the budget is exceeded, **When** the batch runs, **Then** cap-stopped slots come back `Result(error='cost_cap_exhausted')`, the partial set still grades, and those slots count as `n_err`.
- **Given** a model's `pass@1`, **When** `CodingScore.grade` maps it (`score5 = pass@1*5` + review cuts), **Then** `1.0→A+` and `0.0→F` (parametrized on the cut boundaries).
- **Given** N generations for a model, **When** `grade()` writes the `--custom_output_file`, **Then** it is a JSON list of length N ordered by benchmark `question_id`.
- **Given** `--probe`, **When** the tool runs, **Then** it dispatches ≤ 2 problems/model and prints a real-token cost estimate (assert call count + output shape).
- **Given** the default model source, **When** the tool resolves the set, **Then** it logs the resolved count and warns if it is below the review table's row count (never a silent under-run).
- **Mocked:** `ai-consult` dispatch (`run_many`/`arun_many`) + the `lcb_runner` evaluator are mocked with a 1–2 problem fixture corpus → **$0, no `.lcb-venv` needed**. Real: the grading-format assembly + scoring/persistence logic.

### Closing sequence
1. Phase-B gate → green.
2. `check_doc_sync.py` — resolve in-diff WARNINGs.
3. **`/fabrik-review`** on `microbench_coding_direct.py` + its tests — pool `minimax/minimax-m3` finders
   (record + `set_quality`) **AND ≥1 native `fabrik-reviewer`/Opus** (this phase owns cost-cap + external-format
   correctness — real-money + contract risk → the authoritative Opus pass applies); refute → prove-before-fix
   (kept regression test) → iterate to `found:0, fixed:0`.
4. **`/fabrik-generate-tests`** on this phase's Behavior Contract — pool authors one test per behavior the
   implementer did not already TDD (`fanout("code", mode="write")`, disjoint `owned_paths`, sandbox self-verify);
   review test-quality + `git apply` survivors → re-run gate.
5. Commit (explicit paths), `Agent-Phase: B`. Stage plan file (Phase B ✅).

---

## Phase C — Wire the measured signal into coding-subagent selection

**Goal:** persist to `model_coding_metrics` + `model_task_baseline(task_type='code')` with measured precedence,
and surface the measured coding grade + `pass@1` in `CODING_SUBAGENT_SELECTION.md`.

### Interfaces
- **Consumes:** `CodingScore` (Phase B); `build_task_baselines` DDL + `load_review_metrics` pattern; `rank_coding_subagents._rows_from_db`.
- **Produces:**
  - `microbench_coding_direct.persist_metrics(scores) -> Path` — `model_coding_metrics` table (PK
    `model_id, built_at`; columns: `pass_at_1, score5, grade, out_price_mtok, cost_usd, cost_per_1k,
    p50_latency_s, tokens_per_s, n_problems, n_err, window, built_at`) + dated JSON artifact
    (`.microbench_cache/coding_metrics_<date>.json`), mirroring `microbench_review.py:662-722`,
  - `microbench_coding_direct.persist_baseline(scores)` — `INSERT OR REPLACE INTO model_task_baseline`
    with `task_type='code'`, `baseline=pass@1*5`, `pass_rate=pass@1`, `source='livecodebench:<window>'`,
  - `build_task_baselines.load_coding_metrics(db) -> dict[str,dict]` (latest-per-model JOIN, fail-soft `{}`)
    + **precedence:** the `code` baseline path prefers measured LiveCodeBench over `tbench_leaderboard_results`
    (a measured `model_task_baseline(code)` row with `source LIKE 'livecodebench:%'` is not overwritten by the
    scraped build),
  - `rank_coding_subagents._rows_from_db` — override the *displayed* Doc↔Code grade with the measured
    **coding** grade (`doc_grade_measured` via `load_coding_metrics`), add a `pass@1 %` column, fix the
    legend (`:388`, currently "review capability"). **Sort (`_compose_score`, `:329,346`) left unchanged —
    display only (D4).**

### Steps
1. **Grounding step first:** read `rank_coding_subagents.py:287-346` to confirm exactly how `score`/`doc_grade`
   drive the sort (line 346 sorts by `-score`) before changing the override source — capture `path:line`.
2. Implement `persist_metrics` + `persist_baseline` in `microbench_coding_direct.py`; wire `--all`/`--persist`.
3. Add `load_coding_metrics(db)` (latest-per-model JOIN, fail-soft `{}`) to `build_task_baselines.py`, mirroring
   `load_review_metrics` (`:108-142`). **Precedence seam (exact):** `main()` builds `task_type='code'` from the
   terminal-bench `software-engineering` category (`:47,239-241`) and `persist()` does `INSERT OR REPLACE` on PK
   (model_id,task_type) (`:204-214`) — which WOULD clobber a measured row. Guard it in the `code` branch:
   **exclude any model present in `load_coding_metrics()` from the terminal-bench `build('code')` set**, so a
   measured LiveCodeBench `code` baseline (`source LIKE 'livecodebench:%'`) is never overwritten by the scraped build.
4. Update `rank_coding_subagents.py`: (a) override the *displayed* Doc↔Code grade with the measured coding grade
   via `load_coding_metrics` (`†`); (b) add a `pass@1 %` column; (c) fix the grade legend (`:388`). **Do NOT touch
   `_compose_score`/the sort — display only per D4** (re-ranking would be an unscoped rewrite for all rows; the
   authoritative ranking is D3's `model_task_baseline`, which `pick_models("code")` reads). Regenerate
   `docs/reference/kilo/CODING_SUBAGENT_SELECTION.md` (its `AFTER-EDIT` header, `:2`).

### Validation gate
```bash
.venv/bin/python -m pytest scripts/kilo-benchmarks/tests/test_coding_baselines.py -q            # green
.venv/bin/python scripts/kilo-benchmarks/build_task_baselines.py --help                          # exit 0
.venv/bin/python scripts/kilo-benchmarks/rank_coding_subagents.py > /dev/null && echo "doc regenerated"
```

### Behavior Contract (Phase C)
- **Given** a `CodingScore`, **When** `persist_metrics` writes it and `report_stored` reads back, **Then** the `model_coding_metrics` row round-trips (latest-per-model).
- **Given** a measured `livecodebench:` `code` baseline AND terminal-bench data for the same model, **When** the daily `build_task_baselines` build runs, **Then** the measured row survives (the precedence guard — seed both, assert not clobbered).
- **Given** a model with a coding metric vs. one without, **When** `rank_coding_subagents` renders, **Then** the first shows the measured coding grade with `†` + a `pass@1 %` value and the second falls back to the heuristic.
- **Given** the `model_coding_metrics` table is absent, **When** `load_coding_metrics` is called, **Then** it returns `{}` fail-soft (the daily pipeline must not crash).
- **Mocked:** none needed — these run against a temp sqlite `kilo_agents.db` seeded in-test; no network, no spend.

### Closing sequence
1. Phase-C gate → green.
2. `check_doc_sync.py` — this phase changes selection docs → update `CHANGELOG.md`, `docs/FEATURES.md`,
   `INDEX.md` (new `microbench_coding_direct.py` + tests), and re-generate `CODING_SUBAGENT_SELECTION.md`.
3. **`/fabrik-review`** on all Phase-C surfaces — pool finders (record + `set_quality`) **AND native
   `fabrik-reviewer`/Opus** (this phase mutates the DB precedence + the selection doc that governs which models
   get dispatched — high-blast-radius → authoritative Opus pass); refute → prove-before-fix → `found:0, fixed:0`.
4. **`/fabrik-generate-tests`** on the Behavior Contract → review + apply → re-run gate.
5. Commit (explicit paths), `Agent-Phase: C`. Stage plan file (Phase C ✅).

---

## Final phase — docs convergence + full gate

1. **`/fabrik-docs-review`** — this run shipped a new tool + a schema (`model_coding_metrics`) + a selection-doc
   change → converge `CHANGELOG.md`, `INDEX.md`, `docs/FEATURES.md`, `docs/reference/kilo/CODING_SUBAGENT_SELECTION.md`
   to a truthful fixed point (touch-on-change proves presence; this proves correctness).
2. **`docs/LESSONS_LEARNT.md`** — add the vendor-ladder lesson (build vendored ai-consult, not a second
   `_direct_call` reinvention) OR confirm `none`.
3. **FULL gate (Tier 2, never `--lean`):**
   ```bash
   .venv/bin/python scripts/final_gate.py --json         # expect {"status":"success"}
   .venv/bin/python scripts/enforcement/check_convergence.py
   ```
   Fix to `success`. Baseline: a red already red at start is a sibling's, not this plan's.
4. **Whole-plan `/fabrik-review`** over the cumulative diff → no-op. Then requirements coverage (every "What we
   agreed" item → its delivering phase). Release scope lock; set `Status: EXECUTED`; archive to
   `docs/development/plans/archived/`. Offer push/hold.

> **Green gate is necessary, NOT sufficient** — it proves citations/format/lint, not that `pass@1` is measured
> correctly. The real proof is the Evidence below + the mocked Behavior-Contract tests + the operator's probe run.

---

## File Scope (owned paths)

```
scripts/kilo-benchmarks/microbench_coding_direct.py           # NEW (Phase B, C)
scripts/kilo-benchmarks/build_task_baselines.py               # MODIFY (Phase C — load_coding_metrics + precedence)
scripts/kilo-benchmarks/rank_coding_subagents.py              # MODIFY (Phase C — measured coding grade + pass@1 col)
scripts/kilo-benchmarks/tests/test_lcb_smoke.py               # NEW (Phase A)
scripts/kilo-benchmarks/tests/test_microbench_coding_direct.py# NEW (Phase B)
scripts/kilo-benchmarks/tests/test_coding_baselines.py        # NEW (Phase C)
scripts/kilo-benchmarks/.gitignore                            # MODIFY (Phase A — ignore .lcb-venv/.lcb-src)
# scripts/kilo-benchmarks/kilo_agents.db  — GITIGNORED as of 2026-07-19 (untracked); NOT committed. The build
#   writes NO real db data (Behavior Contracts use temp sqlite); the operator's real run populates it on disk, untracked.
docs/reference/kilo/CODING_SUBAGENT_SELECTION.md              # regenerated artifact (Phase C)
CHANGELOG.md · INDEX.md · docs/FEATURES.md · docs/LESSONS_LEARNT.md   # doc-sync (append-only; never reset [Unreleased])
```
Disjoint-check: `microbench_coding.py` is **explicitly excluded** (must-not-touch). If a sibling plan is active
on `build_task_baselines.py`/`rank_coding_subagents.py`, those two are the serialization points — Phase C runs
solo, not parallel to another plan touching them.

## Evidence

**Phase A** — `lcb_runner` grounded live 2026-07-19 (spec:71): github.com/LiveCodeBench/LiveCodeBench —
`custom_evaluator.py --custom_output_file` = JSON list len==benchmark, ordered by question_id;
`--release_version release_v1..v6` temporal filter. Install = git-clone + `pip install -e`.
```
spec:71  | LiveCodeBench | ... custom_evaluator.py --custom_output_file (a JSON list of outputs in benchmark order) ... install = git-clone + pip install -e . |
```

**Phase B** — ai-consult transport grounded in real source:
```
ai_consult/run.py:68   class Result:  text / model / provider / usage / cost_usd / error
ai_consult/run.py:97   class Call:    model / messages / body=None / liveness / tags / persist
ai_consult/run.py:316  def run(model, messages, *, body=None, ..., max_cost_usd=None) -> Result
ai_consult/run.py:518  def run_many(calls: list[Call], **kw) -> list[Result]   # partial-tolerant, ordered
ai_consult/run.py:411-419  arun_many(*, max_concurrency=4, max_cost_usd=None)  — the VENDOR cost gate (do not re-sum)
ai_consult/run.py:447-453  dispatch-gate: Result(error='cost_cap_exhausted') once budget spent (overshoot <= max_concurrency)
microbench_review.py:291-303  MIN_MEASURED_MUTANTS=3 / is_measured  (the errored-not-zero pattern to mirror)
microbench_review.py:317-352  grade() cuts + cost_per_1k + tokens_per_s + median_latency (reused verbatim)
```

**Phase C** — persistence + wiring parallels grounded:
```
microbench_review.py:662-722  persist_metrics + model_review_metrics DDL (13 cols) — the shape to parallel
build_task_baselines.py:59-71 model_task_baseline DDL (PK model_id,task_type; baseline 0-5, pass_rate, source)
build_task_baselines.py:108-158 load_review_metrics (latest-per-model JOIN) + review_eligible — parallel for coding
build_task_baselines.py:47   TASK_CATEGORIES["code"] = ("software-engineering",)
build_task_baselines.py:239-241 main() loops TASK_CATEGORIES -> build('code') + persist() (the daily 'code' write)
build_task_baselines.py:204-214 persist() INSERT OR REPLACE on PK (model_id,task_type) — CONFIRMED clobber the D3 guard prevents
rank_coding_subagents.py:329  d["score"] = _compose_score(d)  — the SORT key (:346 -score)
rank_coding_subagents.py:333  doc_grade override is DISPLAY-only, does NOT re-rank (the D4 correction)
rank_coding_subagents.py:388  grade legend currently = "review capability" (corrected in D4)
```
Config confirmed: `DB_PATH = scripts/kilo-benchmarks/kilo_agents.db` (build_task_baselines.py:41);
`microbench_coding.py` exists (27,924 B) and is out of scope; `model_review_metrics` holds **exactly 57**
distinct models (verified 2026-07-19 → the "same 57" default is exact, D1).

## Self-audit

- **Grounding done directly** (not fanned out): the units are local files this session's owner authored last
  turn (`microbench_review.py`, `build_task_baselines.py`, `rank_coding_subagents.py`) plus the vendored
  `ai-consult` source — authoritative path:line reads where cheap-model grounding hallucinates (the "native
  catches what pool misses" lesson). Execution-phase fan-out **is** pool-default (review finders + test authors),
  where the flywheel-relevant gradeable work lives.
- **Coverage — every "What we agreed" → its phase:** uniform pass@1 of 57 → Phase B (+D1 model set); LiveCodeBench
  contamination-free → Phase A/B; direct ai-consult (no reinvention) → Phase B + Global Constraints; grade via
  custom_evaluator → Phase A/B; new `model_coding_metrics` + dated JSON → Phase C; feed `pick_models("code")` →
  Phase C (D3 baseline + precedence); cost discipline (probe + cap) → Phase B; isolation / no-touch / no-glob →
  Global Constraints. **No gap.**
- **Cross-phase signature consistency:** `CodingScore` (B) is consumed by `persist_metrics`/`persist_baseline`
  (C) under the same name; `load_coding_metrics` (C) parallels `load_review_metrics` verbatim. No name drift.
- **Converged 2026-07-19** via `/fabrik-plan-review` (3 passes: self-grounding + a native-Opus authoritative
  grounder → md5-verified content no-op). Fixed: the `--cost-cap` vendor-ladder reinvention (now
  `run_many(max_cost_usd=…)`), the D4 doc-ranking overstatement (now display-only; authoritative ranking = D3),
  the "same 57" hardcoded guarantee (now logged + shortfall-warned). D3 precedence guard + all LiveCodeBench
  citations verified sound.

## Residual unknowns

- **RESOLVED (build-time, self-service):** exact `custom_output_file` schema + `--release_version` values +
  benchmark loader API → Phase A step 4 reads them from the vendored source before Phase B wires against them
  (a build-step probe, not a runtime discovery — no execution stall).
- **RESOLVED (self-service):** whether `ai-consult.run()` reaches every model → it sends no `max_price` (the
  fixed pool-404 root cause), so Phase B's `--probe` confirms "no endpoints found" never appears before the full run.
- **OPEN (non-blocking, operator-owned, NOT a plan step):** the real ~$12–18 57-model run — sized by `--probe`,
  triggered by the operator after the build (like the review bench's real run). The plan spends $0.
- **OPEN (accepted, spec:141-144):** ~50-problem window → `pass@1` sampling noise (~±7%) → tiers reliable,
  adjacent rows are noise; LiveCodeBench measures algorithmic (not multi-library) coding — an accepted scope choice.
- **Cross-repo (out of scope, tracked upstream):** the hub's vendored `libs/subagents` still needs the
  governance re-sync to inherit `fabrik-lib 764df76`; the coding bench uses ai-consult **directly** so it does
  **not** depend on that sync landing.
