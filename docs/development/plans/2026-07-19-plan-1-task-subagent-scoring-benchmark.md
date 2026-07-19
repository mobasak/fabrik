# Task-Subagent Scoring Benchmark — Implementation Plan

Status: IN-PROGRESS
Date: 2026-07-19
Spec: [docs/superpowers/specs/2026-07-19-task-subagent-scoring-benchmark-design.md](../../superpowers/specs/2026-07-19-task-subagent-scoring-benchmark-design.md) (CONVERGED)
Scope: hub-internal `scripts/kilo-benchmarks/` tool — parallel to `microbench_review.py` + `microbench_coding_direct.py`

---

## What we already agreed (from the CONVERGED spec + this session)

- **One harness** `microbench_judged.py` (coding-bench skeleton) scoring the ~57 pool models on `docs`/`research`/`plan`/`spec`, so `pick_models()` + the selection MD files get a measured prior where today there is **none**.
- **Two grader families:** **A** — objective, judge-free, torch-free correctness (research = normalized EM/token-F1 on fabrik-private/fresh Q&A; docs = bidirectional git-grounded recall/precision reusing `doc_reconcile.py`). **B** — plan/spec = free structural filter + correlated cold-start prior + flywheel primary; **PoLL judge DEFERRED** (not built now).
- **The load-bearing persistence fix:** the benchmark writes **BOTH** `model_task_baseline` rows (the prior) **AND** `subagent_runs` rows (one per dispatch, `quality_score=score5`) — because `rank_task_subagents` only surfaces a model that clears `HAVING COUNT(*) >= 3`/90d; a baseline alone never surfaces a cold model. The baseline **consumption** (`_tier_baseline`) stays unchanged.
- **The selection-doc DISPLAY pattern (mirror review/code, shipped 2026-07-19 — this DOES modify `build_task_baselines`+`rank_task_subagents`):** each of docs/research/plan/spec gets a `<task>_eligible()` gate (mirroring `review_eligible`/`code_eligible`) that FILTERS its `### <task>` router section so `pick_models("<task>")` returns the shortlist, a `_full_<task>_results_table()` (mirroring `_full_review_results_table`/`_full_coding_results_table`), and a `_selected_shortlists()` entry. So "zero ranker change" holds for the *prior consumption* only, NOT the display.
- **Vendor `fabrik-lib/claude-evaluator`** for the research EM-near-miss tiebreak (`model="haiku"`, $0 OpenRouter, abstention-aware). It is **Claude-only** → it is NOT the diverse PoLL panel (that leg, if ever built, stays the pool).
- **All corpora fabrik-private + post-cutoff** → contamination-free. Grading **tool-free on provided context** (agentic tool-use quality stays the flywheel's job).
- **Default scope = all ~57** (operator intent: "score all / don't cap"); `--auto-tier` opt-in restricts to the 27 selectable models.
- **Build order:** research → docs → plan+spec → wire the selection MD files.
- User quote (this turn): *"evaluate these roles and put into our md files coding, task md files properly."* → the deliverable ends by regenerating `TASK_SUBAGENT_SELECTION.md` populated for the four task types.

**Branch: RICH** — the spec pins goal + approach; no brainstorming. This plan grounds the build.

---

## Global Constraints (every phase inherits verbatim)

- **Python** ≥ 3.11, full type hints; env via `os.getenv("K", default)` — no hardcoded secrets/hosts (`core/10-python`).
- **12-Factor:** logs = unbuffered JSON to **stdout only, never a logfile** (XI); config = granular env vars (III); **same backing services dev/prod** — this tool writes the real `kilo_agents.db` (sqlite, hub-local) + the real `subagent_runs` (`postgres-main`), never a substitute (X).
- **Torch-free main tool** — AlignScore, if ever added, is isolated to a `.align-venv` sibling (like `.lcb-venv`); the primary `microbench_judged.py` path imports no torch.
- **LLM gateway = OpenRouter only** via the vendored `libs.subagents._transport.run`; the judge tiebreak = `claude-evaluator` (subscription, no OpenRouter).
- **Cost safety (inherit the coding bench's proven mechanics):** balance guard clamps cost-cap to ~90% of live balance; per-call cap; running-total dispatch gate; **batched incremental persist + resume** (`_measured_models`). Default cap ≥ balance (no silent coverage cap).
- **No deps-file edits** without authorization — the EM/F1 normalizer is stdlib (~15 lines); `claude-evaluator` + `libs.subagents` are vendored/present.
- **Naming** kebab-case; Python modules snake_case; new `.md` only in allowlisted locations.
- **Shared-tree commits:** explicit pathspec only (`git commit -- <paths>`), never `git add -A`; provenance trailers.

---

## Context Ledger

| Source | What binds | Grounded ref |
|---|---|---|
| `core/10-python.md` (ACTIVE) | typing, `os.getenv` env handling, no hardcoded config | `.windsurf/rules/core/10-python.md` |
| `core/45-testing-strategy.md` (ACTIVE) | one test per user-observable behavior; risk-ordered; temp-sqlite, no-network unit tests | `.windsurf/rules/core/45-testing-strategy.md` |
| `core/30-ops.md` (ACTIVE) | stdout logging, no logfiles (12F XI) | `.windsurf/rules/core/30-ops.md` |
| `microbench_coding_direct.py` (VENDOR pattern) | dispatch→grade→persist_metrics/persist_baseline→batched-resume `main()`; cost caps | `generate` [:205], `CodingScore` [:271], `persist_metrics` [:352], `persist_baseline` [:387], `_measured_models` [:439], `main` [:516] |
| `microbench_review.py` (VENDOR pattern) | `ModelScore` recall/precision→`score5`, grade cuts, `is_measured`; **`record_flywheel`** | `persist` [:571], `record_flywheel` [:607] |
| `libs.subagents` (VENDOR as-is) | dispatch + flywheel API | `AgentSpec` [agent.py:147], `AgentResult` [agent.py:210], `run_agents` [agent.py:665], `record_agent_run` [pg_ledger.py:211], `set_quality` [pg_ledger.py:269], `_transport.run` [_transport.py:231] |
| `scripts/doc_reconcile.py` (VENDOR + ENHANCE) | docs precision plumbing; ENHANCE = add recall axis | `_added_lines` [:118], `_extract_tokens` [:139], `_codebase_haystack` [:148], `_default_verify` [:174] |
| `scripts/kilo-benchmarks/build_task_baselines.py` (**MODIFIED** — Phase E adds `<task>_eligible()`) | `model_task_baseline` DDL + sqlite location; ADD a `<task>_eligible()` per new task type mirroring `review_eligible`/`code_eligible` | `DB_PATH` [:41], `ensure_table` [:74], `review_eligible` [:150], `code_eligible` [:234] |
| `scripts/kilo-benchmarks/rank_task_subagents.py` (**MODIFIED** — Phase E adds gate filter + display fns) | prior consumption (`_tier_baseline` [:91], `HAVING >= MIN_RUNS` [:154-164]) UNCHANGED; ADD a `### <task>` gate filter (mirror the code gate), `_full_<task>_results_table()`, and `_selected_shortlists` entries per task | `_full_review_results_table` [:440], `_full_coding_results_table` [:502], `_selected_shortlists` [:598] |
| `fabrik-lib/claude-evaluator` (VENDOR as-is) | judge tiebreak / deferred calibration | `ClaudeEvaluator(EvalConfig(model=…, confidence_field=…, confidence_threshold=…))` → `evaluate_sync(items) → .scored/.abstained/.failed` (`/opt/fabrik-lib/claude-evaluator/README.md`) |
| `pick_models` / `methodology` (VENDOR as-is) | task_type support | `TASK_KINDS`/`METHODOLOGY_KINDS` include `spec,plan,code,review,docs,research` ([select.py:31], [methodology.py:19]) |

**fabrik-lib consult:** done — `claude-evaluator` vendored for the judge leg; no module covers the benchmark harness or EM/F1 grading (grepped `fabrik-lib/README.md`) → building those in `scripts/kilo-benchmarks/` is correct. **🆕 fabrik-lib candidate:** none (hub-internal, extends an existing family).

**Shape/infra:** none — no deployed service, no `specs/services/*.yaml`, no `shape:` flags, no compose/ports.

---

## Phase A — Shared harness: dispatch + persistence + flywheel recording — ✅ EXECUTED 2026-07-20

**Files:** create `scripts/kilo-benchmarks/microbench_judged.py` (+ `scripts/kilo-benchmarks/tests/test_judged_harness.py`). One responsibility: the task-agnostic spine + a grader-registry seam that Phases B–D fill.

**Steps**
1. **(TDD, highest risk first) `record_flywheel` — the surface-a-cold-model fix.** Write `test_record_flywheel_writes_subagent_runs` FIRST (temp store / monkeypatched `record_agent_run`): assert one row per successful dispatch with `quality_score=score5`, **`task_type` == the benchmark task** (docs/research/plan/spec — `record_agent_run` derives the row's `task_type` from `spec.task_type`, so the dispatch `AgentSpec.task_type` MUST be set to the benchmark task, or the row surfaces under the wrong/no task_type — verified `record_agent_run` [pg_ledger.py:211]), errored calls skipped. Confirm RED, then implement `record_flywheel(rows)` mirroring [microbench_review.py:607] (`record_agent_run(spec, res, quality_score=score5, project="microbench")`). Confirm GREEN.
2. `TaskScore` dataclass mirroring `CodingScore` [:271]: `score5` (0–5), `grade` (A+≥4.5…F cuts), `is_measured` (`n_graded >= MIN_MEASURED(3)`), `cost_per_1k`, `p50_latency`.
3. `generate(models, corpus, task_type, ...)` — adapt coding `generate` [:205]: dispatch via raw `_transport.run` (reaches **all 57** — the coding bench uses raw transport precisely because the pool 404s some models), `body={"usage":{"include":True},"max_tokens":MAX_TOKENS}`, per-call cap, running-total dispatch gate, `_bill()` unknown-cost estimate. **⚠️ Raw `_transport.run` yields NO `AgentSpec`** (unlike review's `run_agents` path), yet `record_flywheel`→`record_agent_run` needs one. So `generate` must **build a lightweight `AgentSpec(model=m, task_type=task_type, task=<prompt>)`** ([agent.py:147]) per successful call and return `(spec, result)` tuples — that is what carries `task_type` into the flywheel row (step 1). Grade + `record_flywheel` both consume these tuples.
4. `GRADERS: dict[str, Grader]` registry keyed by `task_type`; Phase A ships the `Grader` protocol (`grade(gens, corpus) -> dict[str, TaskScore]`) + a passthrough stub so the harness runs end-to-end.
5. `persist_metrics(scores, task_type, window)` → `model_<task>_metrics` table (mirror [:352]); `persist_baseline(scores, task_type, window)` → `model_task_baseline` rows `source='microbench_judged:<task>'` (mirror [:387], INSERT-OR-REPLACE precedence guard).
6. `_measured_models(task_type, window)` resume-skip (mirror [:439]); `main()` batched-resume with balance guard + `--task`, `--all`/`--auto-tier`, `--cost-cap`, `--concurrency`, `--report`, `--fresh` (mirror [:516]).

**Interfaces — Produces:** `TaskScore`, `GRADERS` registry + `Grader` protocol, `generate()`, `persist_metrics()`, `persist_baseline()`, `record_flywheel()`, `_measured_models()`, `main()`. **Consumes:** `libs.subagents._transport.run`, `record_agent_run`, `pick_models`, `methodology`; `build_task_baselines.ensure_table`.

**Behavior Contract (temp sqlite, no network, no spend):** (a) `record_flywheel` writes one `subagent_runs` row/success with `score5` [TDD]; (b) `persist_metrics` round-trips + grade cut; (c) `persist_baseline` writes the `task_type` prior with the right `source`; (d) unmeasured (`<3` graded) model is NOT persisted; (e) `_measured_models` drives resume-skip (window-scoped).

**Closing sequence:** phase gate (`pytest tests/test_judged_harness.py -q` green; `python scripts/final_gate.py --check --json` → `"status":"success"`) → `check_doc_sync.py` → **`/fabrik-review` on the changed surface, looped to a no-op** (pool finders + ≥1 native Opus) → commit (`git commit -- scripts/kilo-benchmarks/microbench_judged.py scripts/kilo-benchmarks/tests/test_judged_harness.py` + trailers).

---

## Phase B — research grader (EM/F1 + claude-evaluator tiebreak) + corpus  *(parallelizable with C, D after A)* — ✅ EXECUTED 2026-07-20

**Files:** `scripts/kilo-benchmarks/research_grader.py` (flat) + `scripts/kilo-benchmarks/corpora/research_qa.json` + `scripts/kilo-benchmarks/vendor/claude_evaluator/**` + `tests/test_research_grader.py`.

**Steps**
0. **Vendor-copy** `claude_evaluator` into the tree: `cp -r /opt/fabrik-lib/claude-evaluator/claude_evaluator scripts/kilo-benchmarks/vendor/claude_evaluator` (the module dir is **hyphenated** `claude-evaluator/`, the importable package **underscored** `claude_evaluator/` inside it — verified `/opt/fabrik-lib/claude-evaluator/claude_evaluator/{__init__,core}.py`). Add `scripts/kilo-benchmarks/vendor/__init__.py` (empty) so `from vendor.claude_evaluator import ClaudeEvaluator, EvalConfig` resolves (both exported via `__init__.__all__`; the grader calls `evaluate_sync(items)` — `core.py:108`). Pure-stdlib + subprocess (`npx @anthropic-ai/claude-code --print` — no OpenRouter dep, no new `.venv` package).
1. Vendor the HotpotQA `normalize_answer` (lowercase, strip articles/punct, fix whitespace) + `f1_score`/`exact_match_score` (verified live at `github.com/hotpotqa/hotpot/blob/master/hotpot_evaluate_v1.py` / the `reconsider` mirror) — ~15 lines, stdlib only.
2. **(TDD)** `test_em_f1_normalization` FIRST — "Sasha and Malia" vs "Malia and Sasha", article/punct variants → EM after normalization; partial → token-F1. RED→implement→GREEN.
3. `research_grade(gens, corpus) -> dict[str, TaskScore]`: per item, normalized EM (1.0) else token-F1; on EM near-miss (F1 in a band) escalate to a **`claude-evaluator`** tiebreak — `ClaudeEvaluator(EvalConfig(model="haiku", confidence_field="confidence", confidence_threshold=3))`, `.abstained` items excluded from the denominator (like an errored call). `score5 = mean(item_scores) * 5`.
4. Author the corpus: ~30–50 fabrik-private + fresh Q&A, each `{question, context (inlined), gold, aliases[]}` — pool-authored draft (`fanout("research")`) then **operator/native-curated** for canonical gold (a wrong gold poisons every model equally).
5. Register `"research"` in `GRADERS`.

**Interfaces — Consumes:** Phase A `TaskScore`, `GRADERS`. **Produces:** `research_grade`, `normalize_answer`, `corpora/research_qa.json` schema `{question,context,gold,aliases}`.

**Behavior Contract:** (a) normalization equates ordering/article/punct variants [TDD]; (b) token-F1 on partial; (c) tiebreak fires only in the near-miss band + abstention excluded; (d) end-to-end `--task research` on a 2-item temp corpus persists baseline + flywheel rows.

**Closing sequence:** gate → doc-sync → `/fabrik-review` no-op → commit (explicit paths).

---

## Phase C — docs grader (bidirectional git-grounded recall/precision) + corpus  *(parallelizable)* — ✅ EXECUTED 2026-07-20

**Files:** `scripts/kilo-benchmarks/docs_grader.py` (flat) + `scripts/kilo-benchmarks/mine_docs_corpus.py` (flat) + generated `scripts/kilo-benchmarks/corpora/docs_pairs.json` (data) + `tests/test_docs_grader.py`.

**Steps**
1. `mine_docs_corpus.py`: scan fabrik git history for commits touching **code + a doc together**; emit `{stale_doc (doc@parent), diff (code hunk), ground_truth (doc@commit)}` triples. Freeze ~15–20 to `docs_pairs.json` (deterministic, re-runnable).
2. **(TDD)** `test_docs_precision_recall` FIRST: a patch adding a hallucinated symbol → precision < 1; a patch omitting a required edit OR leaving a removed symbol → recall < 1; the ground-truth patch → `score5 ≈ 5`. RED→implement→GREEN.
3. `docs_grade`: **precision** = `_extract_tokens(_added_lines(patch))` resolve in `_codebase_haystack` (reuse [doc_reconcile.py:118-197], `skip_md=True`); **recall** = required-edit tokens present + removed-symbol tokens absent from the reconciled doc, vs the git ground truth. `score5 = f1(recall, precision) * 5`. **Torch-free.**
4. Register `"docs"` in `GRADERS`.

**Interfaces — Consumes:** Phase A `TaskScore`/`GRADERS`; `doc_reconcile._extract_tokens/_added_lines/_codebase_haystack` (import, do not fork). **⚠️ `doc_reconcile.py` lives in `scripts/`, one level ABOVE `scripts/kilo-benchmarks/`** — the grader must `sys.path.insert(0, str(Path(__file__).resolve().parent.parent))` (the `scripts/` dir) before `import doc_reconcile`, in addition to the flat `SCRIPT_DIR` sibling-import path. **Produces:** `docs_grade`, `mine_docs_corpus.main`, `corpora/docs_pairs.json` schema.

**Behavior Contract:** (a) hallucinated added symbol → precision penalty [TDD]; (b) missing required edit → recall penalty; (c) removed symbol still present → recall penalty; (d) ground-truth patch scores ~A+; (e) end-to-end `--task docs` persists baseline + flywheel.

**Closing sequence:** gate → doc-sync → `/fabrik-review` no-op → commit.

---

## Phase D — plan+spec structural filter + correlated prior + flywheel wiring  *(parallelizable)* — ✅ EXECUTED 2026-07-20

**Files:** `scripts/kilo-benchmarks/structural_grader.py` (flat) + `scripts/kilo-benchmarks/correlated_prior.py` (flat) + `tests/test_structural_grader.py`.

**Steps**
1. **(TDD)** `test_structural_filter` FIRST: a plan missing runnable gates / with an unresolvable `path:line` / no test-per-behavior → fails; a well-formed plan → passes. Same for spec (required sections / `shape:` flags / enums / citations resolve). RED→implement→GREEN.
2. `structural_grade(gens, corpus, kind)` — deterministic checks: **plan** = phases present, each gate parseable (regex for a fenced command), **path:line citations resolve to a real repo line**, ≥1 test/behavior, evidence blocks; **spec** = required sections present, `shape:` flags + enums/constraints complete, citations resolve. Continuous `score5` = weighted fraction of checks passed; a hard-fail (no gates at all) disqualifies.
3. `correlated_prior.py`: seed `plan` `model_task_baseline` from each model's `code`+`review` metrics, `spec` from `docs`+`plan` (read existing metrics, write correlated priors, `source='correlated:<from>'`). No generation cost. **⚠️ Build the module here, but INVOKE it at Phase E** (not during parallel B/C/D): `spec`'s prior reads `docs` metrics that **Phase C produces concurrently** — running it inside Phase D would race C and seed an incomplete `spec` prior. `correlated_prior.build()` is idempotent (re-runnable) and runs once all four source metrics exist.
4. Register `"plan"`,`"spec"` in `GRADERS`. **PoLL judge NOT built** — leave a documented `# DEFERRED` seam: a `claude-evaluator` (`model="opus"`) calibration/audit stub + a note that the flywheel is the primary signal.

**Interfaces — Consumes:** Phase A `TaskScore`/`GRADERS`; `model_task_baseline` + `model_review_metrics`/`model_coding_metrics`. **Produces:** `structural_grade`, `correlated_prior.build`.

**Behavior Contract:** (a) plan without runnable gates → disqualified [TDD]; (b) unresolvable path:line → penalty; (c) spec missing a required section → penalty; (d) `correlated_prior` writes a plan prior derived from code+review; (e) the flywheel-primary path documented + `structural_grade` registered.

**Closing sequence:** gate → doc-sync → `/fabrik-review` no-op → commit.

---

## Phase E — populate the selection MD files + docs + smoke  *(depends on A–D)*

**Files (modify):** `scripts/kilo-benchmarks/build_task_baselines.py` (add `<task>_eligible()` per task), `scripts/kilo-benchmarks/rank_task_subagents.py` (gate filter + `_full_<task>_results_table()` + `_selected_shortlists` extension), `scripts/kilo-benchmarks/tests/test_review_eligibility.py` (per-task render tests), `docs/reference/kilo/TASK_SUBAGENT_SELECTION.md` (regenerated), `CHANGELOG.md`, `docs/FEATURES.md`, `INDEX.md`, `scripts/kilo-benchmarks/daily_refresh.sh` (add the judged bench to the refresh) + a runbook note.

**Steps**
1. **Smoke (no paid run in the autonomous plan):** `python scripts/kilo-benchmarks/microbench_judged.py --task research --smoke` on a **≥3-item temp corpus** + a stub/echo model → asserts baseline + `subagent_runs` rows land and `rank_task_subagents` **surfaces** the model. **⚠️ The corpus MUST be ≥3 items** so the model gets ≥3 flywheel rows and clears `HAVING COUNT(*) >= MIN_RUNS(3)` ([rank_task_subagents.py:47,163](../../scripts/kilo-benchmarks/rank_task_subagents.py#L47)) — a 2-item smoke would land 2 rows, never surface, and *falsely* look like the fix failed. This is exactly the fix being proven end-to-end. *(The real paid 57-model run is an operator step post-plan — mirrors how the coding bench was built then run; documented in the runbook, not executed autonomously.)*
2. **Selection-doc gate + display (mirror review/code — the pattern the spec's § Persistence now mandates):**
   - **Gate:** add `<task>_eligible()` to `build_task_baselines.py` for each of docs/research/plan/spec, mirroring `review_eligible` [build_task_baselines.py:150](../../scripts/kilo-benchmarks/build_task_baselines.py#L150) / `code_eligible` [:234](../../scripts/kilo-benchmarks/build_task_baselines.py#L234). **research/docs** gate on quality+cost+latency (`score5` floor + `$/1k` + `p50`); **plan/spec** gate on quality/structural only (`score5` floor + structural-checks-passed — **no cost/latency**, there is no generation).
   - **Filter:** wire each `### <task>` router section to its gate in `render()`, mirroring the `code_gate` filter (`if task_type == "<task>" and <task>_bench_ran: task_rows = [r for r in task_rows if r[1] in <task>_gate]`), so `pick_models("<task>")` returns exactly the eligible shortlist.
   - **Leaderboard:** add `_full_<task>_results_table()` mirroring `_full_review_results_table` [rank_task_subagents.py:440](../../scripts/kilo-benchmarks/rank_task_subagents.py#L440) / `_full_coding_results_table` [:502](../../scripts/kilo-benchmarks/rank_task_subagents.py#L502) — research/docs columns `score5·grade·(recall·precision)·$/1k·$/run·p50·tok/s·eligible`; plan/spec columns `score5·grade·structural-checks·eligible` (no cost/latency).
   - **Headline:** extend `_selected_shortlists()` [:598](../../scripts/kilo-benchmarks/rank_task_subagents.py#L598) to add the 4 new task types alongside reviewers + coders.
3. **Invoke `correlated_prior.build()`** (from Phase D) now that `code`/`review`/`docs`/`plan` metrics all exist → writes the `plan`/`spec` correlated priors. THEN regenerate `TASK_SUBAGENT_SELECTION.md` via `rank_task_subagents.py` → confirm the `## ✅ Selected subagents` headline + `### docs/research/plan/spec` sections + full-leaderboard tables reflect the gated shortlists.
4. Wire `daily_refresh.sh` to run the judged bench (resume-safe) alongside the coding/review benches.
5. Doc sync: `CHANGELOG.md` (Added), `docs/FEATURES.md` (new capability), `INDEX.md` (new files), a runbook entry for the paid-run procedure (`--task <t> --all`, cost/time, resume).
6. **`/fabrik-docs-review`** → converge docs to a truthful fixed point.

**Behavior Contract:** (a) smoke run surfaces a seeded model in `TASK_SUBAGENT_SELECTION.md` [proves the fix]; (b) `daily_refresh.sh` invokes the judged bench resume-safely; (c) **per new task type, a render test proving the `### <task>` gate drops an ineligible row** (mirror `test_render_code_section_gated_by_code_eligible` in `tests/test_review_eligibility.py`) — with the gate's monkeypatchable `<task>_bench_ran`/`<task>_benchmark_models` so the test controls it (as `_code_bench_ran` does).

**Closing sequence:** gate → doc-sync → `/fabrik-review` no-op → `/fabrik-docs-review` → **full** `python scripts/final_gate.py --json` `"status":"success"` → commit.

---

## Subagents + parallelism (enforced pillars)

- **Phases B, C, D are independent** (disjoint files: `research_grader`+corpus / `docs_grader`+corpus / `structural_grader`+`correlated_prior`) → after Phase A they **fan out in parallel**; merge at Phase E.
- **Pool-default** (`fanout`, records to the flywheel) for: the research corpus draft (`fanout("research")`), per-behavior test authoring (`fanout("code", mode="write")`, disjoint `owned_paths`), and each phase's `/fabrik-review` finder breadth. **Native Opus** for: grader logic (higher-judgment), gold-answer curation, and the `/fabrik-review` authoritative pass + decide/merge.
- **`/fabrik-review` at every phase boundary** — a BLOCKING no-op-looped gate (written into each phase's closing sequence above).

---

## File Scope (owned paths)

```
scripts/kilo-benchmarks/microbench_judged.py
scripts/kilo-benchmarks/research_grader.py                      # FLAT module (sibling import convention)
scripts/kilo-benchmarks/docs_grader.py
scripts/kilo-benchmarks/structural_grader.py
scripts/kilo-benchmarks/correlated_prior.py
scripts/kilo-benchmarks/mine_docs_corpus.py
scripts/kilo-benchmarks/vendor/__init__.py                     # Phase B: makes vendor/ a package
scripts/kilo-benchmarks/vendor/claude_evaluator/**             # Phase B: vendored (copied) from /opt/fabrik-lib/claude-evaluator/claude_evaluator
scripts/kilo-benchmarks/corpora/research_qa.json               # data (read by path, not imported)
scripts/kilo-benchmarks/corpora/docs_pairs.json
scripts/kilo-benchmarks/tests/test_judged_harness.py
scripts/kilo-benchmarks/tests/test_research_grader.py
scripts/kilo-benchmarks/tests/test_docs_grader.py
scripts/kilo-benchmarks/tests/test_structural_grader.py
scripts/kilo-benchmarks/build_task_baselines.py   # Phase E: add <task>_eligible() — SHARED w/ review/code gates → SERIALIZE
scripts/kilo-benchmarks/rank_task_subagents.py    # Phase E: gate filter + _full_<task>_results_table() + _selected_shortlists — SHARED → SERIALIZE
scripts/kilo-benchmarks/tests/test_review_eligibility.py  # Phase E: per-task render tests (shared w/ review/code gate tests)
scripts/kilo-benchmarks/daily_refresh.sh          # Phase E (shared w/ coding bench — serialize with any coding-bench run)
docs/reference/kilo/TASK_SUBAGENT_SELECTION.md     # Phase E (regenerated output)
CHANGELOG.md · docs/FEATURES.md · INDEX.md          # Phase E doc sync (append-only, shared-tree care)
```
Grader `.py` modules are **FLAT** in `scripts/kilo-benchmarks/` (imported like the siblings: `sys.path.insert(0, SCRIPT_DIR); import research_grader` — verified against `tests/test_coding_baselines.py:13-16`), NOT in a `graders/` subdir. `doc_reconcile.py` + `libs/subagents/**` are **read/import only — not modified**. **`rank_task_subagents.py` + `build_task_baselines.py` ARE modified** in Phase E (add the `<task>_eligible()` gate + `_full_<task>_results_table()` + `_selected_shortlists` entries, mirroring review/code) — they are owned paths below; only the baseline *consumption* (`_tier_baseline`) is unchanged.

---

## Evidence (per phase — grounded Phase-1 reads + captured output)

- **A:** `record_flywheel` pattern to mirror — [microbench_review.py:607] (`record_agent_run(spec, res, quality_score=5.0 if correct else 0.0, project="review")`, errored calls skipped). Persist targets — `persist_metrics` [:352], `persist_baseline` [:387]; `main` batched-resume [:516].
  ```
  $ grep -n "def persist_metrics\|def persist_baseline\|def _measured_models\|def main" scripts/kilo-benchmarks/microbench_coding_direct.py
  352:def persist_metrics  387:def persist_baseline  439:def _measured_models  516:def main
  ```
- **B:** HotpotQA grader verified live (native Opus, 2026-07-19): `normalize_answer` + `f1_score` + `exact_match_score` present at `github.com/hotpotqa/hotpot/blob/master/hotpot_evaluate_v1.py`. `claude-evaluator` API — `ClaudeEvaluator(EvalConfig)` → `evaluate_sync → .scored/.abstained/.failed` (`/opt/fabrik-lib/claude-evaluator/README.md`).
- **C:** `doc_reconcile` precision plumbing exists: `_added_lines` [:118], `_extract_tokens` [:139], `_codebase_haystack` [:148], `_default_verify` [:174] (added-symbol-only → recall axis genuinely absent = the ENHANCE).
- **D:** ranker consumes the prior unchanged + the surfacing gate:
  ```
  $ grep -n "HAVING COUNT" scripts/kilo-benchmarks/rank_task_subagents.py
  163:HAVING COUNT(*) >= {MIN_RUNS}
  ```
- **E:** `pick_models`/`methodology` support all four task_types — `TASK_KINDS` [select.py:31], `METHODOLOGY_KINDS` [methodology.py:19]. Display pattern to mirror (verified this run): `review_eligible`/`code_eligible` [build_task_baselines.py:150,234], `_full_review_results_table`/`_full_coding_results_table` [rank_task_subagents.py:440,502], `_selected_shortlists` [:598], and the code-gate render test `test_render_code_section_gated_by_code_eligible` [tests/test_review_eligibility.py:250].

---

## Self-audit

- **Grounding passes:** three research/code agents this session (external methods + internal infra) + native-Opus citation verify (7/7 HOLD) + direct signature reads above.
- **Coverage** (each "What we agreed" → phase): one harness → A; two grader families → B (research), C (docs), D (plan/spec); BOTH baseline + flywheel persist → A(`record_flywheel`)+B/C/D(wire)+E(smoke proves surfacing); `claude-evaluator` vendor → B; contamination-free corpora → B/C; default all-57 → A(`main` flags); build order → phase order; "into the MD files" → E; **selection-doc gate+display pattern (`<task>_eligible()` filter + `_full_<task>_results_table` + `_selected_shortlists`, mirroring review/code) → E (step 2)**.
- **Cross-phase signature consistency:** `TaskScore`, `GRADERS`/`Grader`, `generate`, `persist_*`, `record_flywheel` are defined in A and consumed by B–E under the same names; graders all return `dict[str, TaskScore]`.
- **Fixed-point:** re-converged 2026-07-19 against the updated spec + current code — added the eligibility-gate + full-leaderboard + selected-shortlist display pattern (mirroring the review/code work shipped the same day). `Status: CONVERGED`.

---

## Residual unknowns

**Resolved:** grading methods (spec); ranker consumption + the surfacing-gate fix (verified); reusable APIs (read at file:line); tiebreak model (`claude-evaluator` haiku).

**Still open (each self-service — none blocks execution):**
- **Corpus authoring volume** — *Resolution:* Phases B/C build the corpora (docs git-mined via `mine_docs_corpus.py`; research pool-drafted + curated); sized small (`is_measured` needs only ≥3).
- **The paid 57-model scoring run** — *Resolution:* intentionally OUT of the autonomous plan (spends money, hours). Phase E ships a $0 smoke that proves surfacing; the real run is an operator step per the runbook (`--task <t> --all`), mirroring the coding bench.
- **PoLL judge for plan/spec** — *Resolution:* DEFERRED by design; Phase D leaves a documented `claude-evaluator` calibration seam. Build only if flywheel sparsity proves it necessary (a future spec).

---

## Status → next

`Status: CONVERGED` (Pass 3 md5-verified no-op). Next: `/fabrik-execute-plan <this file>` is the **user's** call (it mutates code). The paid scoring run remains a separate operator step after the harness lands.

## Behavior Contract

Gate-index restatement of the per-phase contracts above (one Given/When/Then per behavior; the phase text is authoritative):

- **Given** a temp sqlite DB, **When** `record_flywheel` runs on a success, **Then** exactly one `subagent_runs` row with `score5` is written [Phase A(a), TDD].
- **Given** persisted metrics, **When** `persist_metrics` round-trips, **Then** values + grade cut survive intact [A(b)].
- **Given** a completed run, **When** `persist_baseline` fires, **Then** the `task_type` prior carries the right `source` [A(c)].
- **Given** a model with `<3` graded results, **When** persistence runs, **Then** it is NOT persisted [A(d)].
- **Given** a prior window, **When** resuming, **Then** `_measured_models` drives the skip (window-scoped) [A(e)].
- **Given** answer variants (ordering/article/punct), **When** normalized, **Then** they compare equal [B(a), TDD].
- **Given** a partial answer, **When** graded, **Then** token-F1 scores it [B(b)].
- **Given** a near-miss-band score, **When** the tiebreak evaluates, **Then** it fires only there and abstentions are excluded [B(c)].
- **Given** a 2-item temp corpus, **When** `--task research` runs end-to-end, **Then** baseline + flywheel rows persist [B(d)].
- **Given** a hallucinated added symbol, **When** the docs grader scores, **Then** precision is penalised [C(a), TDD].
- **Given** a missing required edit, **When** scored, **Then** recall is penalised [C(b)].
- **Given** a removed symbol still present, **When** scored, **Then** recall is penalised [C(c)].
- **Given** the ground-truth patch, **When** scored, **Then** it grades ~A+ [C(d)].
- **Given** `--task docs` end-to-end, **When** it completes, **Then** baseline + flywheel persist [C(e)].
- **Given** a plan without runnable gates, **When** structurally graded, **Then** it is disqualified [D(a), TDD].
- **Given** an unresolvable path:line, **When** graded, **Then** a penalty applies [D(b)].
- **Given** a spec missing a required section, **When** graded, **Then** a penalty applies [D(c)].
- **Given** code+review priors, **When** `correlated_prior` runs, **Then** a plan prior is written [D(d)].
- **Given** the flywheel-primary path, **When** registered, **Then** `structural_grade` is documented + registered [D(e)].
- **Given** a seeded model, **When** the smoke run completes, **Then** it surfaces in `TASK_SUBAGENT_SELECTION.md` [E(a)].
- **Given** `daily_refresh.sh`, **When** it invokes the judged bench, **Then** the invocation is resume-safe [E(b)].
