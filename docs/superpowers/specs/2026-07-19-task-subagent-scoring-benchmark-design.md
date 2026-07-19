# Task-Subagent Scoring Benchmark — Design Spec

Status: CONVERGED
Date: 2026-07-19
Author: primary (Claude Opus 4.8)
Topic: benchmark harness scoring the pool models on `docs` / `research` / `plan` / `spec`

---

## Goal

Give `pick_models(task_type)` a **measured, contamination-free baseline** for the four task types that today
have **none** — `docs`, `research`, `plan`, `spec` — parallel to the benchmarks that already cover `review`
([microbench_review.py](../../scripts/kilo-benchmarks/microbench_review.py)) and `code`
([microbench_coding_direct.py](../../scripts/kilo-benchmarks/microbench_coding_direct.py)).

**Why it matters:** `rank_task_subagents._tier_baseline` ([rank_task_subagents.py:91-137](../../scripts/kilo-benchmarks/rank_task_subagents.py#L91))
resolves a model's prior in precedence order: **(1) a `model_task_baseline` benchmark row for THIS (model,
task_type)** → (2) a task-*blind* `quality_tier` column → (3) raw average. Only `ops`+`code`
([build_task_baselines.py:45](../../scripts/kilo-benchmarks/build_task_baselines.py#L45)) and `review`
(written separately by [microbench_review.py:persist](../../scripts/kilo-benchmarks/microbench_review.py#L571))
have a real benchmark prior today. `docs`/`research`/`plan`/`spec` fall through to the single blind tier —
every model looks identical for these tasks until the flywheel slowly accumulates real runs. This benchmark
emits the missing priors.

**⚠️ Grounded caveat (verified this session):** the baseline is consumed **only as the shrinkage prior** for
`(model, task_type)` rows that the flywheel query already surfaces — `GROUP BY task_type, model HAVING
COUNT(*) >= MIN_RUNS(3)` over `WINDOW_DAYS(90)` ([rank_task_subagents.py:154-164](../../scripts/kilo-benchmarks/rank_task_subagents.py#L154)).
A benchmark baseline **alone does not surface a cold model** — it re-weights models that already have flywheel
presence. Therefore the benchmark **must also record each dispatch to `subagent_runs`** (exactly as
[microbench_review.record_flywheel](../../scripts/kilo-benchmarks/microbench_review.py#L607) does), so its own
runs satisfy the `>= 3` gate *and* the baseline supplies the prior — together surfacing the model with **zero
ranker code change**.

**Scope:** **all ~57 flywheel pool models by default** (research/docs outputs are short → a full run is cheap,
and full coverage matches how the coding/review benches score), with `--auto-tier` as an opt-in cost lever to
restrict to the 27 selectable models (`out ≤ $1.5/Mtok` — the only ones `pick_models` can auto-select).
Grading is **tool-free on provided context** — it measures synthesis/planning-from-context (the load-bearing,
deterministic half); true agentic tool-use quality stays the **flywheel's** job (real `fanout` runs scored via
`set_quality`).

**Out of scope:** the live agentic/tool-grounded research quality (flywheel owns it); a deployed service (this
is a hub-internal `scripts/` tool like the sibling benchmarks — no `shape:`, no compose, no `fabrik apply`);
re-ranking logic (unchanged — we only feed it data).

---

## Chosen approach — one harness, two grader families, judge-deferred

Copy the [microbench_coding_direct.py](../../scripts/kilo-benchmarks/microbench_coding_direct.py) skeleton
(dispatch → grade → `persist_metrics`/`persist_baseline` → batched-resume `main()` with balance-guard, per-call
+ workload cost caps, `_measured_models()` resume) and the [microbench_review.py](../../scripts/kilo-benchmarks/microbench_review.py)
`ModelScore` recall/precision + grade-cut pattern (A+ ≥4.5 … F, `is_measured` ≥ MIN_MEASURED). A new
`microbench_judged.py` (working name) parameterizes the corpus + grader per task_type; everything else is shared.

All four corpora are **fabrik-private + post-cutoff** → **contamination-free by construction** (the same
property that made LiveCodeBench the right coding set — a model cannot have memorized answers to questions
about our own repo). This is the design's backbone and why it is defensible.

### Family A — claim/answer correctness (research, docs): objective, ~$0 grading

**`research`** — *fixed Q&A with short canonical GOLD answers, graded programmatically.*
- Corpus: ~30–50 questions, each with the **retrieved context inlined** (RAG-style) + a short canonical gold
  answer. Half fabrik-private (facts about our repo/infra I can verify), half fresh/time-sensitive.
- Grade: **normalized exact-match + token-F1** — vendor the HotpotQA `normalize_answer` normalization
  (lowercase, strip articles/punct/whitespace; set-sort list answers) — deterministic, **$0/item**. A
  **cheap tiebreak via `claude-evaluator` (`model="haiku"`)** resolves only the ~10–20% EM near-misses (the
  "Sasha and Malia" ordering/synonymy problem) — subscription-billed → **$0 OpenRouter**, with built-in
  abstention (a genuinely-unresolvable near-miss routes to `.abstained`, excluded from the denominator like an
  errored call). **No citation-verifier** — correctness is the anchor; citations are orthogonal.

**`docs`** — *reconcile a stale doc to a code diff; grade bidirectional edit recall/precision.*
- Corpus: ~15–20 pairs **mined from real fabrik commits that changed code + its doc together** — revert the
  doc = the stale-doc input; the code change = the diff; the human's doc update = ground truth.
- Grade (**torch-free, continuous 0–5, like the review bench's mutmut recall/precision**), reusing
  [doc_reconcile.py](../../scripts/doc_reconcile.py) plumbing:
  - **precision** = every symbol the model's patch *adds* resolves in the codebase (no hallucination) —
    `_extract_tokens(_added_lines(patch))` ∩ `_codebase_haystack` ([doc_reconcile.py:118-197](../../scripts/doc_reconcile.py#L118)).
  - **recall** = required edits made **+ removed symbols gone from the doc** (the omission axis
    `_default_verify` alone misses) — checked against the git ground-truth update.
  - `score5 = f1(recall, precision) × 5`.
- **AlignScore** (entailment faithfulness) is an **optional isolated bolt-on** in its own `.align-venv`
  (mirroring `.lcb-venv`) — **never primary**, because it reintroduces torch + a 1.3 GB checkpoint into a tool
  we deliberately keep torch-free. Ship without it; add only if the programmatic recall/precision proves too
  coarse.

### Family B — structural filter + correlated prior + flywheel (plan, spec): ~$0, judge deferred

Plan/spec quality is genuinely semi-subjective; a paid LLM-judge on 3–4 k-token plans × a panel × candidates
is both the **least reliable** signal and the **biggest cost tail**. Invert it:

- **Structural filter** (free, deterministic, objective — the disqualifier): `plan` = phases present, each gate
  parseable/runnable, **path:line citations resolve to real repo lines**, ≥1 test/behavior, evidence blocks;
  `spec` = required sections present, `shape:` flags + enums/constraints complete, citations resolve. A
  plan/spec failing this is disqualified regardless of any judge.
- **Correlated cold-start prior**: seed `plan`'s `model_task_baseline` from the model's `code`+`review` scores,
  `spec`'s from `docs`+`plan` (correlated capabilities) — no generation cost, a defensible non-blind prior for
  the ranker to shrink against.
- **Flywheel = primary ranking signal**: plan/spec are exactly where *real* usage grading is trustworthy — the
  orchestrator already adjudicates real plans via `set_quality` into `subagent_runs`; `rank_task_subagents`
  shrinkage (`SHRINKAGE_K=10`, 90-day/min-3) ranks them.
- **PoLL judge built ONLY if flywheel sparsity forces it.** If built: absolute rubric **0–5 (not pairwise →
  kills position bias)**, a **per-candidate family-excluded 3-judge panel** from the **auto-tier pool** (never
  let a model judge its own family — Verga 2024 self-preference; the panel must be diverse OpenRouter families,
  which is why it uses the pool, **not** `claude-evaluator` — the latter is Claude-only). Its **upfront
  calibration vs a ~10-item Opus gold set** (trust the panel only if κ holds) and **~10% Opus audit** run via
  `claude-evaluator` (`EvalConfig(model="opus")`, subscription-billed, abstention-aware) — **1 pass, not 3×
  sampling**.

### Persistence + selection-doc display (reuse the review/code pattern shipped 2026-07-19)

Each task benchmark writes, per model:
- `persist_baseline()` → `model_task_baseline` rows (`task_type ∈ {docs,research,plan,spec}`,
  `source='microbench_judged:<task>'`, INSERT-OR-REPLACE precedence guard) in
  [kilo_agents.db](../../scripts/kilo-benchmarks/build_task_baselines.py#L41) — the **shrinkage prior**,
  consumed by `rank_task_subagents._tier_baseline` **unchanged**.
- **`record_flywheel()` → one `subagent_runs` row per dispatch** (`quality_score=score5`, `task_type` set on
  the dispatch `AgentSpec`) — mirroring [microbench_review.py:607](../../scripts/kilo-benchmarks/microbench_review.py#L607).
  **Load-bearing**: it clears the ranker's `HAVING COUNT(*) >= 3` gate so a cold model surfaces (the baseline
  only re-weights it).
- `persist_metrics()` → a per-task `model_<task>_metrics` table (mirroring `model_review_metrics`/
  `model_coding_metrics`) — the source for the full leaderboard + the `eligible` flag.

**Selection-doc display — reuse the review/code pattern (this DOES touch `rank_task_subagents`, so it is
NOT "zero ranker change" for the display; only the baseline *consumption* is unchanged):**
- **Per-task eligibility gate** — a `<task>_eligible()` in `build_task_baselines.py`, mirroring
  [`review_eligible` :150](../../scripts/kilo-benchmarks/build_task_baselines.py#L150) /
  [`code_eligible` :234](../../scripts/kilo-benchmarks/build_task_baselines.py#L234), that **filters the
  `### <task>` router section** (fail-closed once the benchmark ran) so `pick_models("<task>")` returns the shortlist.
- **Full leaderboard per task** — a `_full_<task>_results_table()` mirroring
  [`_full_review_results_table` :440](../../scripts/kilo-benchmarks/rank_task_subagents.py#L440) /
  [`_full_coding_results_table` :502](../../scripts/kilo-benchmarks/rank_task_subagents.py#L502).
- **Selected-subagents headline** — extend
  [`_selected_shortlists` :598](../../scripts/kilo-benchmarks/rank_task_subagents.py#L598) to add the 4 new
  task types alongside reviewers + coders.

**Per-task columns — they DIFFER by grader family (do not paper over it):**
- **research / docs** (generation-based): `score5 · grade · $/1k · $/run · p50 · tok/s` (docs adds `recall ·
  precision`; `score5 = f1(recall,precision)×5`).
- **plan / spec** (structural filter, **no paid generation**): `score5 · grade · structural-checks-passed` —
  **no `$/1k` / `$/run` / `p50`** (nothing is timed or billed; it is a free structural filter + correlated
  prior + flywheel). Their eligibility gate is quality-only (`score5` floor + structural pass), not cost/latency.

### Build order

1. **research** — context-synthesis EM/F1, judge-free → proves the shared harness end-to-end.
2. **docs** — bidirectional git-grounded recall/precision, torch-free → reuses `doc_reconcile` plumbing.
3. **plan + spec** — structural filter + correlated prior + flywheel wiring; PoLL judge deferred.

---

## Rejected alternatives (+ why)

| Rejected | Why |
|---|---|
| **FActScore as the primary docs grader** | Dozens of LLM calls per doc (atomic-fact decomposition + per-fact verification) — the expensive tail we avoid. VeriFastScore/OpenFActScore exist *specifically* to cut its call count. Programmatic symbol recall/precision + optional AlignScore is far cheaper. [FActScore](https://www.emergentmind.com/topics/factscore) |
| **Public QA sets (SimpleQA/HotpotQA/GAIA) as the research corpus** | Training-contaminated → measures memorized trivia, not research skill. We vendor HotpotQA's *grader* (`normalize_answer`), not its *questions*; questions are fabrik-private/fresh. [SimpleQA](https://arxiv.org/html/2411.04368v1) |
| **Grading research/plan single-shot tool-free as "agentic research/planning"** | In real fabrik these run *with* tools (`fanout(... web_tools=[...])`). Tool-free grades parametric recall, not exploration. We scope it honestly to synthesis-from-provided-context; the flywheel measures live tool-use. |
| **AlignScore (or any torch metric) as the primary docs grader** | Reintroduces torch + a 1.3 GB checkpoint into a deliberately torch-free tool. Kept as an isolated optional `.align-venv` bolt-on. [AlignScore](https://aclanthology.org/2023.acl-long.634.pdf) |
| **A PoLL LLM-judge benchmark for plan/spec, built first** | Least reliable + most expensive signal; needs calibration before it can be trusted fleet-wide. Structural filter (objective) + correlated prior + flywheel (trustworthy real-usage grading for these tasks) covers it at ~$0. Judge deferred until sparsity proves it necessary. [PoLL](https://arxiv.org/abs/2404.18796) |
| **VAL-style formal plan validation (PlanBench)** | Objective only because classical planning has a formal domain model (typed predicates, pre/post-conditions). A natural-language software plan has none — VAL doesn't transfer. The transferable idea (mechanical-structure vs soft-quality split) is what the structural filter implements. [PlanBench](https://arxiv.org/abs/2206.10498) |

---

## External dependencies (grounded this session, 2026-07-19)

All are **method/pattern references** (algorithms we vendor as code, or evidence for a design choice) — **no new
runtime vendor, no API key, no new package beyond what the sibling benchmarks already use**.

| Dep | Use | Grounded source (fetched 2026-07-19) |
|---|---|---|
| HotpotQA `normalize_answer` / EM+F1 | the research grader (vendor the ~15-line normalization) | https://github.com/facebookresearch/reconsider/blob/main/hotpot_evaluate_v1.py |
| GAIA exact-match | precedent for programmatic normalized-string grading | https://www.emergentmind.com/topics/gaia-and-webwalkerqa-benchmarks |
| SimpleQA | evidence that free-form short answers need an LLM tiebreak (not pure EM). *Grader detail is in the body/blog, not the arXiv abstract* | https://arxiv.org/html/2411.04368v1 · https://openai.com/index/introducing-simpleqa |
| cheap-grader economics | GPT-4o-mini ≈ **$1.01/1k judgments @ 96.6% ECR@1**. *Scope: a Gherkin test-coverage-grading study; "reliability" = first-attempt valid-JSON rate — cite as directional, not general-QA accuracy* | https://arxiv.org/html/2512.01232v1 |
| FActScore (rejected primary) | atomic-fact decomposition + per-fact verification = many LLM calls/response | https://arxiv.org/abs/2305.14251 · https://www.emergentmind.com/topics/factscore |
| AlignScore (optional bolt-on) | RoBERTa-355M local faithfulness scorer, ACL 2023 | https://aclanthology.org/2023.acl-long.634.pdf · https://github.com/yuh-zha/AlignScore |
| PoLL (deferred judge) | 3 cheap disjoint-family judges > 1 GPT-4 judge @ ~1/7 cost (Pearson 0.917 vs 0.817) | https://arxiv.org/abs/2404.18796 |
| PlanBench/VAL (rejected) | paper grounds: VAL validates only because classical planning has a formal PDDL domain. *The "doesn't transfer to NL software plans" step is our design inference, not a paper claim* | https://arxiv.org/abs/2206.10498 |
| rubric-reliability / reference-guided judging | if PoLL is built: 1-and-5 anchors ≈ full rubric; anchoring rescues cheap judges | https://arxiv.org/html/2506.13639v1 |

---

## Internal reuse verdict (vendor-first — nothing built from scratch that already exists)

| Capability | Verdict | Module / ref (verified this session) |
|---|---|---|
| Model dispatch (paid generation) | **VENDOR** | `libs.subagents._transport.run` (raw transport, as coding bench uses) + `pick_models(task_type)` / `methodology()` / `fanout` / `set_quality` |
| Benchmark skeleton (dispatch→grade→persist→resume, cost caps, balance guard) | **VENDOR (copy pattern)** | [microbench_coding_direct.py](../../scripts/kilo-benchmarks/microbench_coding_direct.py) |
| `ModelScore` recall/precision + grade cuts + `is_measured` | **VENDOR (copy pattern)** | [microbench_review.py](../../scripts/kilo-benchmarks/microbench_review.py) |
| Docs claim-check (added-symbol resolution, token extraction, codebase haystack) | **VENDOR + ENHANCE** | `reconcile_doc` / `_default_verify` / `_extract_tokens` / `_codebase_haystack` / `_added_lines` / `_quality` ([doc_reconcile.py:118-362](../../scripts/doc_reconcile.py#L118)). **Enhance:** add the *removed-symbol / required-edit recall* axis `_default_verify` lacks. Not a core fork — an added grader path; note in the script if any `doc_reconcile` core fn is touched. |
| Baseline store + ranker consumption | **VENDOR as-is** | `model_task_baseline` in `kilo_agents.db` ([build_task_baselines.py:41-78](../../scripts/kilo-benchmarks/build_task_baselines.py#L41)); consumed by `rank_task_subagents._tier_baseline` **unchanged** |
| Selection-doc eligibility gate + full-leaderboard + selected-shortlist display | **VENDOR (copy pattern)** | mirror `review_eligible`/`code_eligible` ([build_task_baselines.py:150,234](../../scripts/kilo-benchmarks/build_task_baselines.py#L150)), `_full_review_results_table`/`_full_coding_results_table` ([rank_task_subagents.py:440,502](../../scripts/kilo-benchmarks/rank_task_subagents.py#L440)), and `_selected_shortlists` ([:598](../../scripts/kilo-benchmarks/rank_task_subagents.py#L598)) — a `<task>_eligible()` + `_full_<task>_results_table()` + a `_selected_shortlists` extension per new task type. **This DOES modify `rank_task_subagents`** (unlike the baseline consumption above). |
| Flywheel (plan/spec primary signal) | **VENDOR as-is** | `subagent_runs` + `record_agent_run` / `set_quality` on `postgres-main` |
| LLM-judge grading — research tiebreak + deferred plan/spec calibration/audit | **VENDOR as-is** | `fabrik-lib/claude-evaluator` — `ClaudeEvaluator(EvalConfig(model=…))` → `evaluate(items) → .scored/.abstained/.failed`; batch→scored-JSON, **subscription-billed (`npx claude-code --print`, $0 OpenRouter)**, built-in abstention (`confidence_field`/`confidence_threshold`) + defensive parse. `model="haiku"` for the research tiebreak; `model="opus"` for plan/spec calibration + audit. **Caveat:** Claude-only → **cannot** serve as the diverse-family PoLL panel (that leg stays the pool). |
| Faithfulness entailment scorer (docs, optional) | **BUILD (isolated, deferred)** | AlignScore in a `.align-venv` — only if programmatic recall/precision proves too coarse. Not a fabrik-lib candidate (single-tool, grading-only). |

**🆕 fabrik-lib candidate:** none — this is a hub-internal benchmark extending an existing family; the reusable
grading helpers live with their sibling benchmarks in `scripts/kilo-benchmarks/`, not as a cross-project module.

---

## Shape / infra implications

**None.** Hub-internal `scripts/kilo-benchmarks/` tool, run manually/by `daily_refresh.sh` (like the sibling
benchmarks). No deployed service, no `specs/services/<id>.yaml`, no `shape:` flags, no compose, no Traefik, no
new port. Writes to the existing `kilo_agents.db` (sqlite, hub-local) and the existing `subagent_runs`
(`postgres-main`). Grading runs locally ($0). Paid generation goes through the already-configured OpenRouter
transport with the same balance-guard + cost-cap safety the coding bench proved.

---

## Constraints

- **LLM gateway = OpenRouter only** (via the vendored transport) — satisfied.
- **Torch-free main tool** — AlignScore isolated to an optional sibling venv; primary path is programmatic.
- **Cost safety** — inherit the coding bench's balance guard (90% of live balance), per-call cap, running-total
  dispatch gate, batched incremental persist + resume. Default cap ≥ balance so a full run never silently caps
  coverage (lesson from the coding run's self-imposed cap).
- **Contamination-free corpora** — all fabrik-private / post-cutoff; no public QA questions.
- **No new package in the main `.venv`** beyond what the sibling benchmarks already import (deps-file changes
  need authorization; the EM/F1 normalizer is ~15 lines of stdlib).

---

## Open / blocking unknowns

**Resolved this session:**
- Grading methods per task — grounded via live research (Family A objective/cheap; Family B structural+flywheel).
- Ranker consumption — verified zero-change (`_tier_baseline` reads `model_task_baseline` by task_type).
- Reusable internal plumbing — verified at file:line.

**Still open (each with a resolution step — none blocks writing the plan):**
- **Corpus authoring effort** — the ~30–50 research Q&A, ~15–20 docs pairs, ~10–15 plan/spec goals must be
  hand-curated/git-mined. *Resolution:* the plan's Phase 1 is corpus construction; docs pairs are git-mined
  (scriptable), research/plan/spec are authored from fabrik-private material. Sized small deliberately
  (`is_measured` needs only ≥3).
- **Default model scope** — *Resolved:* default = **all ~57** (matches operator intent + the coding/review
  benches; cheap for short research/docs outputs); `--auto-tier` opt-in restricts to the 27 selectable models
  as a cost lever. Operator-overridable.
- **Cheap-LLM tiebreak model choice (research)** — *Resolved:* `claude-evaluator` with `model="haiku"`
  (subscription-billed, $0 OpenRouter, abstention-aware) — not a metered pool call.

---

## Success criteria

1. `microbench_judged.py --all --task research` and `--task docs` produce **both** `model_task_baseline` rows
   (the prior) **and** `subagent_runs` rows (one per dispatch, `quality_score=score5`) with the right
   `task_type`; a model with ≥3 recorded runs surfaces in `TASK_SUBAGENT_SELECTION.md`, prior-weighted. (The
   baseline *consumption* is unchanged; the recorded runs clear the `HAVING COUNT(*) >= 3` gate — verified
   against `rank_task_subagents.py:154-164`.)
2. Grading is deterministic (research EM/F1, docs recall/precision) — a re-run on the same generations yields
   the same scores.
3. The main tool imports **no torch**; a full run respects the balance guard + resumes after interruption.
4. `plan`/`spec` get a non-blind `model_task_baseline` prior (correlated seed) + the structural filter runs;
   the flywheel is wired as their primary signal.
5. Behavior Contract: one test per grader behavior (EM/F1 normalization, docs recall/precision incl. the
   removed-symbol axis, resume-skip, structural-filter pass/fail, correlated-prior write) against a temp
   sqlite — no network, no spend.
6. **Selection-doc pattern (mirrors review/code, per § Persistence):** each of docs/research/plan/spec has a
   `<task>_eligible()` gate in `build_task_baselines.py` that **filters its `### <task>` router section** so
   `pick_models("<task>")` returns exactly the eligible shortlist; a `_full_<task>_results_table()` is appended
   (research/docs with cost/latency columns, plan/spec structural-only); and `_selected_shortlists()` lists the
   four new task types under the `✅ Selected subagents` headline. A render test **proving the gate drops an
   ineligible row** (mirroring `test_render_code_section_gated_by_code_eligible`) is required per task type.
