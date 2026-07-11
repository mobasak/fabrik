# Local coding-quality microbench runner — design spec

**Status:** CONVERGED
**Date:** 2026-07-10
**Author:** primary (this session)
**Converged:** 2026-07-10 via `/fabrik-spec-review` — reached via multi-pass all-axes grounding; the final round made zero edits (md5 fixed-point). Two material corrections this convergence produced:
1. **Flywheel misattribution avoided.** `record_agent_run(spec, result)` schemas the `subagent_runs` row's `model` off `spec.model` (verified `pg_ledger.py:157-172`), so recording pass@1 against the bench's orchestrator model would mislabel the target's coding capability — the bench therefore writes pass@1 directly to `agents.humaneval_score` + `agents.coding_score` (0-100 scale) and does NOT call `record_agent_run`. Downstream reach into `pick_models("code")` is preserved: `derive_quality_v2.py`'s weight-of-evidence tier folds those columns into `quality_tier`, which is what pool code-dispatch (e.g. `fabrik-review.md:step 3` — pool authors writing test files with `task_type="code"`) picks from.
2. **`weighted_coding` reserved for BenchLM composite.** Writer-side grep confirmed `scrape_benchlm.py:70` is the sole `weighted_coding` populator (BenchLM's own multi-benchmark composite, calibrated to `derive_quality_v2.py:87,101` thresholds ≥88/≥70). Crossing populators with the bench's HumanEval+MBPP composite would break cross-model comparability of the tier signal — spec explicitly does NOT write to it.
3. **UI-TARS out of scope.** GUI-agent model (browser/desktop action-prediction, not code synthesis) — benching it against HumanEval is misleading. Target list narrowed 5 → 4 ByteDance-Seed models; UI-TARS deferred to a separate GUI-bench follow-up plan.

External claims re-verified live this session: EvalPlus repo alive (v0.3.1 Oct 2024, master Oct 2025), `OpenAIChatDecoder.base_url` signature confirmed, all 4 subagents public symbols verified at real path:line, bwrap installed here (`bubblewrap 0.9.0`), all 5 originally-motivated OR models active + priced as claimed (bench targets 4, UI-TARS excluded).

> **Revision 2** (2026-07-10): user pushback flagged two omissions from Revision 1 — (a) I was reinventing HumanEval scoring from scratch when EvalPlus (1774 stars, actively maintained Oct 2025) already does HumanEval + HumanEval+ + MBPP + MBPP+ with OR-compatible `--backend openai --base-url` support out of the box; (b) I dismissed `subagents/` when its `run_agents([AgentSpec])` runtime is the right primitive for parallel model×dataset dispatch — owned-paths-disjoint, bwrap-sandboxed, cost-capped. (Pass 1 correction to Revision 2: I initially claimed the composition also fed the flywheel via `record_agent_run` — verified against `pg_ledger.py:157-172` that the row's `model` schemas off `spec.model` = the ORCHESTRATOR, not the bench's target. Direct writes to `agents.humaneval_score` etc. are the right place for the target-model signal; `pick_models("code")` reaches it via `derive_quality_v2.py`'s tier derivation.) Rewritten below.
**Motivating gap:** live-verified 2026-07-10 that `bytedance-seed/*` (4 active OR models) + `bytedance/ui-tars-1.5-7b` have `NULL` on every coding-quality column in `agents` (`coding_score`, `weighted_coding`, `humaneval_score`, `livecodebench`, `swe_bench_pro`, `swe_bench_verified_pct`, `aider_polyglot_pct`, `aa_intelligence_index`, `arena_elo`). No external aggregator (BenchLM, SWE-bench Verified, Aider Polyglot, Artificial Analysis) covers them as of today's live check. Because `rank_coding_subagents.py` filters on a `FAMILIES` allowlist AND scores by these columns, the models are invisible in `CODING_SUBAGENT_SELECTION.md`.

## Goal

Ship a local coding benchmark runner (`scripts/kilo-benchmarks/microbench_coding.py`) that, given a list of OR-routable model IDs, runs the full HumanEval suite (164 problems) + MBPP (399 problems) via EvalPlus, sandbox-executes each returned solution against the reference test cases, computes `pass@1` for HumanEval / HumanEval+ / MBPP / MBPP+, and writes back to `agents.humaneval_score` + `agents.coding_score`. Solves the "OR route exists but no external benchmark scored it" gap for any current-or-future model — starting with the 4 ByteDance-Seed targets (UI-TARS is a GUI-agent model, deferred to a separate GUI-bench follow-up plan).

## Success criteria

- **Correctness:** invoked against `bytedance-seed/seed-2.0-mini`, produces a `humaneval_score` value on the 0-100 scale based on actual test-pass ratio (not derived, not stubbed, not zero) — matching the scale of `weighted_coding` used by `derive_quality_v2.py`.
- **Coverage:** works against any `via_openrouter=1` model in the DB with a single `--models <csv>` flag.
- **Safety:** solutions never escape the sandbox — a HumanEval problem that returns `os.system("rm -rf /")` cannot delete anything (verified by a defensive test).
- **Cost bounded:** each per-model run has a hard cost cap (`--cost-cap 5` = $5 default, well above the $1.13 max on any single Seed model; catches only runaway loops); overrun by at most one problem's worth (~$0.005).
- **Idempotent:** re-running the same `(model, dataset_version)` skips models benched within the last 60 days (matches the `microbench_or_models.py` freshness gate).
- **Wired downstream:** after ingest, `bytedance-seed/seed-` prefix appears in `rank_coding_subagents.py:FAMILIES` and the 4 Seed models appear in `CODING_SUBAGENT_SELECTION.md`. UI-TARS is NOT added (it's a GUI-agent model, out of scope for coding selection).
- **Tier ladder wired:** `derive_quality_v2.py` reads `agents.humaneval_score` and lifts tier when it clears the configured threshold (this is a runnable code fact — a unit test with a stub row asserts the tier lift fires, independent of what the real Seed pass@1 turns out to be). Whether any Seed model actually clears the threshold is a data OBSERVATION, not a criterion the runner can guarantee.
- **Non-regression on the tier ladder:** the new `humaneval_score` threshold change to `derive_quality_v2.py` (Phase F, ~5 LOC) is fleet-wide by nature — the threshold reads for EVERY model, not just Seed. Before merging Phase F, re-run `derive_quality_v2` on all existing rows and assert zero tier-flips for non-Seed models (a one-shot script comparing pre/post `quality_tier` per row). Prevents "Seed benched → half the fleet tier-changes because ~5-LOC edit was wrong".

## Chosen approach

**Compose two proven pieces: EvalPlus for the benchmark orchestration (datasets + sandboxing + eval loop) + the vendored `libs.subagents` module for parallel dispatch (owned-paths, bwrap outer sandbox, cost caps).** Zero custom sandboxing, zero reinvented benchmark runner. Concretely:

### The composition

1. **EvalPlus (external, `pip install evalplus` — grounded live 2026-07-10)** — 1774 GitHub stars, actively maintained (`master` last push Oct 2025), NeurIPS 2023 & COLM 2024. Handles:
   - **4 datasets in one tool**: HumanEval (164), HumanEval+ (same 164 completions but 80× the tests — mitigates trivial-pass), MBPP (399), MBPP+ (378). One completion generation, four scores.
   - **OpenAI-compatible endpoint**: `evalplus.evaluate --backend openai --base-url https://openrouter.ai/api/v1 --model <id>` — confirmed by inspecting `evalplus/provider/openai.py:OpenAIChatDecoder` on GitHub, `base_url` is a constructor param.
   - **Sandboxing**: default is subprocess with `unsafe_execute` from the same `human-eval/execution.py` pattern (multiprocessing.Process + rlimit); optional Docker sandbox via `ganler/evalplus` image for higher trust. Default is fine here because (a) HumanEval + MBPP problems are audited pure-Python (canonical + community-curated for years), AND (b) we run each `evalplus.evaluate` call inside the `libs.subagents` bwrap outer sandbox `--unshare-net --ro-bind / /` — defense in depth, not a single trust boundary.
   - **Contamination-cognizant**: MBPP+ upgraded to `v0.2.0` after `v0.3.0` removed broken tasks; EvalPlus documents ground-truth solution improvements. Trust the tool.

2. **`libs.subagents.run_agents(specs, repo=…, max_concurrency=len(specs))`** — vendored fabrik-lib module, already in `scripts/kilo-benchmarks/libs/subagents/`. **Do NOT use `fanout()`** here — verified at `agent.py:574` that `fanout(task_type, units, ...)` picks models INTERNALLY via `pick_models(task_type)` under the pool ≤$1.5/Mtok cap (`:657`, `:665`) AND defaults `record=True` calling `record_agent_run` per unit (`:621`). Both wrong for this bench: (a) `seed-1.6` + `seed-2.0-lite` are $2.00/Mtok output (above the pool cap), so pool picking would silently drop them; (b) auto-record contradicts §step 3 below (would misattribute pass@1 to orchestrator). Hand-build one `AgentSpec` per unit + pass `max_concurrency=len(specs)` to override `run_agents`' default of 4 (`agent.py:431`):
   - **Parallelism**: dispatch one `AgentSpec` per `(model_id, dataset)` pair (4 Seed models × 2 real datasets = 8 units — HumanEval+ and MBPP+ reuse HumanEval/MBPP completions, so 2 real completion runs, not 4). Owned-paths-disjoint via unique output paths per unit → parallel dispatch.
   - **Bwrap sandbox layer**: each agent's `run_command evalplus.evaluate …` runs inside `bwrap --unshare-net --ro-bind / /` (verified in `subagents/subagents/sandbox.py:121 wrap_command`) — read-only-root + no-network + confined-worktree, so a rogue EvalPlus regression still can't escape.
   - **Cost caps**: `AgentSpec.max_cost_usd` per agent — hard-caps runaway spend.
   - **Provenance ledger**: JSONL append per run; audit trail for free.

3. **NOT using `record_agent_run` for the bench itself** (Revision 2 correction). The flywheel row's `model` + `task_type` live on `AgentSpec` (verified in `pg_ledger.py:157-172`) — the ORCHESTRATOR model that runs `evalplus`, not the TARGET model being benched. Recording `pass@1 * 5` against the orchestrator would attribute the target's coding capability to the wrong model in `subagent_runs`. Correct place for the pass@1 signal is DIRECT WRITES to `agents.humaneval_score` + `agents.coding_score` (0-100 scale), plus a new `humaneval_score` threshold added to `derive_quality_v2.py`'s tier ladder (Phase F, ~5 LOC). `weighted_coding` is deliberately NOT touched — it's reserved for BenchLM's own multi-benchmark composite via `scrape_benchlm.py:70`, and crossing populators would break the tier threshold's cross-model comparability (Tier 3 ≥88 / Tier 2 ≥70 was calibrated to BenchLM's composite scale, not a HumanEval-only pass@1 percentage). Downstream `pick_models("code")` uses the derived tier, so the bench data flows through automatically without a subagent_runs row that misattributes. The flywheel keeps its clean semantic: "how well did THIS model do on THIS task type" — populated only by production task-authoring pool runs (test generation, implementation), not by bench orchestration.

### Data flow

```
per-model-dataset AgentSpec (8 total = 4 Seed models × HumanEval + MBPP)
    ↓ run_agents (parallel via owned_paths)
    │  each agent: cd $worktree
    │             evalplus.evaluate --backend openai
    │                --base-url https://openrouter.ai/api/v1
    │                --model <mid> --dataset <humaneval|mbpp>
    │                --greedy --root ./results
    │  → writes results/<mid>_temp_0.0.jsonl (completions)
    │  → writes results/<mid>_temp_0.0.eval_results.json (scores)
    ↓ post-run per agent
parse pass@1 for HumanEval + HumanEval+ + MBPP + MBPP+ from eval_results.json
    ↓
UPDATE agents SET humaneval_score = pass_humaneval * 100,   -- 0-100 scale
                  coding_score = mean(4 pass@1 scores) * 100, -- 0-100 scale
                  -- weighted_coding UNTOUCHED (BenchLM-owned via scrape_benchlm.py:70;
                  -- crossing populators would collide the tier threshold semantic).
                  last_verified = date('now')
             WHERE id = <mid>
    ↓
append "bytedance-seed/seed-" to
       rank_coding_subagents.py:FAMILIES
       (NOT "bytedance/ui-tars" — UI-TARS is GUI-agent, not a code LLM;
        follow-up plan will bench it against GUI benchmarks + populate a
        separate screenspot_score / gui_agent_score column instead.)
    ↓
add humaneval_score to derive_quality_v2.py's tier ladder
       (Tier 3 threshold ≥ 60, Tier 2 threshold ≥ 40 as an initial pick —
        finalized during Phase F review against the observed Seed
        HumanEval+/MBPP+ distribution. ~5-line addition to
        BENCH_TIER3/BENCH_TIER2 + the bump-loop.)
    ↓
re-run rank_coding_subagents.py
    → CODING_SUBAGENT_SELECTION.md gains the 4 Seed rows
```

### Why this composition wins

- **No sandbox to build.** EvalPlus + subagents both sandbox. Two independent layers of defense with zero custom code.
- **No dataset caching to build.** EvalPlus vendors its datasets internally.
- **No completion loop to build.** EvalPlus's `evalplus.evaluate` handles the OR call + retries + JSON extraction.
- **No parallelism to build.** `run_agents` is proven, owned_paths-safe, cost-capped, wall-clock-capped — 4 Seed models × 2 datasets = 8 units × ~30 min serial (~4 h) → parallel dispatch (~30 min wall clock). ⚠️ **`run_agents` defaults to `max_concurrency=4` (`agent.py:431`)** — 8 units at default = 2 waves = ~60 min. The runner MUST pass `max_concurrency=len(specs)` explicitly to `run_agents` to get single-wave dispatch. (Note: `fanout()` is NOT usable here — it picks models internally under the pool ≤$1.5/Mtok cap and auto-records to the flywheel; both wrong for this bench. See §Chosen approach step 2 for the full rationale.)
- **Downstream reach without misattribution.** `pick_models("code")` consumes `derive_quality_v2.py`'s quality tier. This bench writes `humaneval_score` + `coding_score` (0-100 scale) and adds a new `humaneval_score` signal to the tier ladder (Phase F, ~5 LOC), so bench data reaches the code-selection flywheel by the *right* path (per-target-model column) rather than a `subagent_runs` row that would misattribute pass@1 to the bench orchestrator. `weighted_coding` is deliberately left alone (BenchLM-owned via `scrape_benchlm.py:70`).
- **4 datasets for one cost.** HumanEval + HumanEval+ share the same completions (HumanEval+ just runs more test assertions); MBPP + MBPP+ same. One `evalplus.evaluate --dataset humaneval` gives us both HumanEval and HumanEval+ scores; same for MBPP.

### Cost estimate (updated — 4 Seed models, 4 datasets, still cheap)

Real LLM cost = 2 completion runs (HumanEval + MBPP) per model × ~1000 tokens/problem output:

| Model | Output $/Mtok | HumanEval 164 | MBPP 399 | Combined 563 problems | Cost |
|---|---:|---:|---:|---:|---:|
| `bytedance-seed/seed-1.6-flash` | 0.30 | 164K | 399K | 563K tokens | $0.17 |
| `bytedance-seed/seed-2.0-mini` | 0.40 | 164K | 399K | 563K tokens | $0.23 |
| `bytedance-seed/seed-1.6` | 2.00 | 164K | 399K | 563K tokens | $1.13 |
| `bytedance-seed/seed-2.0-lite` | 2.00 | 164K | 399K | 563K tokens | $1.13 |
| **Total (4 Seed models × 2 datasets → 4 scores each)** | | | | | **~$2.66** |

UI-TARS excluded — GUI-agent model, out of scope for coding-selection MD. Delta vs Revision 1 (HumanEval-only): +$1.85 for 4× the benchmark coverage + HumanEval+ contamination mitigation + MBPP as a second independent dataset. Worth it.

### CLI

```bash
python scripts/kilo-benchmarks/microbench_coding.py \
    --models bytedance-seed/seed-1.6-flash,bytedance-seed/seed-2.0-mini,bytedance-seed/seed-1.6,bytedance-seed/seed-2.0-lite \
    --datasets humaneval,mbpp \
    --cost-cap 5 \
    [--dry-run]
```

Default: full HumanEval + MBPP against the 4 ByteDance-Seed target models; per-model cost cap $5.

### Best-practice grounding (1c — re-verified)

- **EvalPlus** (Liu et al., NeurIPS 2023 & COLM 2024) is the current industry-standard extension of HumanEval — 80× more tests catches trivial-pass, `--greedy` matches pass@1 semantics, actively maintained. GitHub: 1774 stars, last push 2025-10-02 (`https://github.com/evalplus/evalplus`, HTTP 200 verified this session).
- **subagents composition** — `run_agents` with `owned_paths`-disjoint agents matches `.windsurf/rules/core/62-using-subagents.md` § Parallelism (verified this session by module inspection at `sandbox.py:121`, module description in `/opt/fabrik-lib/README.md`).
- **HumanEval + MBPP as a dual-benchmark baseline** — Chen et al. 2021 (HumanEval) + Austin et al. 2021 (MBPP) — every code-LLM paper since evaluates on both. Cited via EvalPlus's README (fetched `master/README.md` HTTP 200 this session).

## Rejected alternatives

- **Build a custom HumanEval runner from scratch (Revision 1 approach)** — REJECTED after live-verifying EvalPlus (1774 stars, actively maintained Oct 2025, NeurIPS 2023 & COLM 2024, native OpenRouter support via `--backend openai --base-url`). Reinventing what a well-maintained industry-standard tool already provides is the exact anti-pattern the fabrik-lib vendor→enhance→build ladder exists to prevent — apply the same principle to external tools.

- **Skip `libs.subagents` and just call `evalplus.evaluate` 8 times in a `for` loop** — REJECTED: loses parallelism (8 serial ~30-min runs = ~4 h wall clock; `run_agents(specs, max_concurrency=len(specs))` dispatch = ~30 min) and loses the bwrap outer-sandbox layer + cost-cap + wall-clock-cap that `AgentSpec` gives for free. A hand-rolled loop rebuilds those or ships without them; the vendored module already has them tested.

- **`claude-evaluator/` fabrik-lib module** — REJECTED (unchanged from Rev 1): different domain (Claude-CLI-based rater for existing artifacts, not code executor).

- **Run in Docker containers via `ganler/evalplus`** — REJECTED for the DEFAULT path: EvalPlus's non-docker default (multiprocessing + rlimit) is adequate because the problem set is audited pure-Python AND we already run it inside the subagents bwrap outer sandbox (defense in depth). Docker mode remains available via `--sandbox docker` if a future dataset warrants harder isolation. Don't force it as the default.

- **Skip MBPP, HumanEval-only** — REJECTED after live-verifying EvalPlus covers both in one tool with almost the same per-model wall-clock. Two independent datasets = more robust ranking signal for ~2× the LLM cost.

- **Wait for BenchLM / AA to score Seed** — REJECTED per motivating gap: live-verified 2026-07-10 that neither has Seed coverage. `microbench_coding.py` closes the gap actively for any current-or-future model without external benchmark coverage.

## External dependencies (all grounded live 2026-07-10)

| Dependency | Grounded fact | Source URL (fetched date) |
|---|---|---|
| **EvalPlus (Python package)** | v0.3.0+ (MBPP+ upgraded to v0.2.0). Repo: 1774 stars, actively maintained, last push 2025-10-02, NeurIPS 2023 & COLM 2024. Provides `evalplus.evaluate` CLI with `--backend openai --base-url --model --dataset humaneval` (or `mbpp`) flags. `OpenAIChatDecoder` class exposes `base_url` (compatible with any OpenAI-compatible endpoint including OR). Datasets bundled internally. Default sandbox: multiprocessing + rlimit (same as OpenAI's `human-eval/execution.py`). Optional Docker sandbox via `ganler/evalplus`. Handles HumanEval (164 tasks), HumanEval+ (same 164, 80× tests), MBPP (399 tasks), MBPP+ (378 tasks post-cleanup). | `https://github.com/evalplus/evalplus` (HTTP 200 verified this session) + `evalplus/provider/openai.py:OpenAIChatDecoder` (inspected this session) + `master/README.md` (backend openai example verified) |
| **HumanEval + MBPP datasets (canonical)** | HumanEval: 164 problems, MIT license (Chen et al., arXiv:2107.03374, 2021). MBPP: 399 problems (Austin et al., arXiv:2108.07732, 2021). Both bundled inside EvalPlus — no separate fetch needed. | Cited via EvalPlus README + `raw.githubusercontent.com/openai/human-eval/master/data/HumanEval.jsonl.gz` (HTTP 200 + 164-count verified this session) |
| **OpenRouter `/api/v1/chat/completions` via EvalPlus** | EvalPlus passes `base_url` + `api_key` to OpenAI client. Set `--base-url https://openrouter.ai/api/v1` + `OPENAI_API_KEY=$OPENROUTER_API_KEY` (env var name is what OpenAI client expects). Endpoint stable. | Live curl to OR + inspection of `evalplus/provider/openai.py` (2026-07-10) |
| **OpenRouter pricing for the 4 bench target models** | seed-1.6-flash $0.075/$0.30 in/out; seed-2.0-mini $0.10/$0.40; seed-1.6 $0.25/$2.00; seed-2.0-lite $0.25/$2.00. All 4 Seed models `context_length: 262144` (~256K). All 4 live-verified `via_openrouter=1 AND status='active'`. (Reference-only, NOT a bench target: `bytedance/ui-tars-1.5-7b` (128K, $0.10/$0.20) is also OR-active — excluded per residual-2 because it's a GUI-agent model, not a code LLM; separate follow-up plan.) | Live curl to `https://openrouter.ai/api/v1/models` (2026-07-10) |
| **`libs.subagents` (vendored fabrik-lib module)** | Public API: `run_agents([AgentSpec], repo=…) → [AgentResult]`. `AgentSpec` fields: `task`, `model`, `system`, `task_type`, `tools_enabled`, `owned_paths`, `max_turns`, `max_cost_usd`, `wall_clock_s`. Bwrap sandbox via `sandbox.py:wrap_command(argv, workdir)`. `record_agent_run(spec, result, quality_score, project)` exists but this bench does NOT call it (row would misattribute pass@1 to `spec.model` = orchestrator, not target — see `pg_ledger.py:157-172`). Already vendored at `scripts/kilo-benchmarks/libs/subagents/`. | `/opt/fabrik-lib/README.md` module description + `subagents/subagents/sandbox.py` (public API inspected this session — `wrap_command`, `sandbox_available`, `SandboxUnavailable`) + `subagents/subagents/pg_ledger.py:157-172` (record_agent_run signature) |
| **`agents` table schema** | Columns exist: `humaneval_score REAL`, `coding_score REAL`, `weighted_coding REAL`, `last_verified DATE`. `id TEXT PRIMARY KEY`. UPDATE writes are safe. | `PRAGMA table_info(agents)` verified this session |

## fabrik-lib verdict table (vendor→enhance→build)

| Capability | Verdict | Module + why | Upstream note |
|---|---|---|---|
| Benchmark orchestration (datasets + LLM calls + sandbox + eval) | **external dep — install `evalplus`** | EvalPlus (v0.3.0+, 1774★, actively maintained). One `pip install evalplus` gives HumanEval + HumanEval+ + MBPP + MBPP+ + OpenAI-compatible client + sandboxing. Ordinarily "no new deps" is a hard rule — this spec authorizes it (`pyproject.toml` adds `evalplus>=0.3.0`) because reinventing 4 datasets + sandbox + eval loop from scratch is the exact anti-pattern the fabrik-lib vendor→enhance→build ladder forbids applied to external tools. | none |
| Parallel dispatch of per-model bench runs | **vendor as-is** | `libs.subagents.run_agents(specs, repo=…, max_concurrency=len(specs))` — the public API (in `subagents/__init__.py:__all__`) that takes hand-built `AgentSpec` list. Owned-paths-disjoint agents run in parallel (4 Seed models × 2 datasets = 8 units × ~30 min serial → ~30 min wall clock parallel). ⚠️ Two pitfalls: (a) `run_agents` defaults `max_concurrency=4` (`agent.py:431`) — pass `len(specs)` explicitly or 8 units become 2 waves; (b) do NOT use `fanout()` — it picks models internally under the pool ≤$1.5/Mtok cap (`agent.py:657,665`) which would silently drop `seed-1.6`/`seed-2.0-lite` ($2.00/Mtok output) AND defaults `record=True` (`agent.py:621`), conflicting with §Chosen approach step 3's "do not record". Bwrap sandbox layer wraps EvalPlus's own sandbox for defense-in-depth. Cost caps + provenance ledger + wall-clock caps included. | none |
| Flywheel signal | **skip for bench** | Verified `pg_ledger.py:157-172` `record_agent_run(spec, result, quality_score, project)` schemas the row's `model` + `task_type` from `spec`, not `result`. For our design that would misattribute pass@1 to the orchestrator model rather than the target. Cleaner: write pass@1 directly to `agents.humaneval_score` etc., and let `derive_quality_v2.py`'s weight-of-evidence pick it up into `quality_tier` — which is what `pick_models("code")` consumes. Flywheel keeps its production-only semantic (test-authoring / implementer runs). | none |
| Sandboxing | **vendor as-is (composed)** | Two independent layers: (a) EvalPlus internal — multiprocessing.Process + rlimit + `subprocess.Popen=None` inside the child (same as `human-eval/execution.py`); (b) subagents outer — bwrap `--unshare-net --ro-bind / /` via `sandbox.py:wrap_command`. Two independent sandboxes = defense in depth, zero custom code. | none |
| Parse EvalPlus result JSON + write DB | **build** — project-local (~40 LOC glue) | Post-run: read `results/<mid>_temp_0.0.eval_results.json`, extract pass@1 for HumanEval / HumanEval+ / MBPP / MBPP+, `UPDATE agents SET humaneval_score = pass_humaneval * 100, coding_score = mean(4 pass@1) * 100, last_verified = date('now') WHERE id = ?`. Both writes are on the 0-100 scale to match `weighted_coding`'s BenchLM-composite scale. `weighted_coding` deliberately NOT touched — populated by `scrape_benchlm.py:70` from BenchLM's own composite, and crossing populators would break the tier threshold's cross-model comparability. Pure glue — no library covers this exact (evalplus JSON → agents table) shape. | none |
| CLI + `--models`/`--datasets`/`--cost-cap` flags | **build** — project-local (~30 LOC argparse) | Trivial argparse wiring calling `run_agents` with the composed spec list. Mirrors `microbench_or_models.py` pattern. | none |

**fabrik-lib consult performed:** grepped `/opt/fabrik-lib/README.md` for `bench|eval|sandbox|score|humaneval|pass@|code.*(exec|run)|parallel`. Hits: `claude-evaluator/` (Claude-CLI rater; wrong domain), `subagents/` (**adopted** for parallel dispatch + bwrap outer sandbox + cost caps — the composition's core; `record_agent_run` intentionally skipped, see §Chosen approach step 3), `concurrency-throttle/` (not needed — subagents handles concurrency internally). **No `code-sandbox-exec` candidate flag anymore** (Revision 1 flagged it; EvalPlus + subagents cover the space cleanly, so a new fabrik-lib module here would be redundant).

## Shape/infra implications

- **Scaffold type:** hub-side utility script (`scripts/kilo-benchmarks/**`). NOT a deployed service.
- **`shape:` flags:** N/A — no `specs/services/*.yaml` touched. Hub-only, no VPS deploy.
- **New deps** (spec-authorized): `evalplus>=0.3.0` added to `pyproject.toml` — pins EvalPlus at the reviewed v0.3.0 line (Oct 2025). Ordinarily new deps are a HARD STOP per CLAUDE.md, but this spec IS the authorization (the ticket). `libs.subagents` is already vendored — no change.
- **New env vars:** none — EvalPlus reads `OPENAI_API_KEY`; we set `OPENAI_API_KEY=$OPENROUTER_API_KEY` before invoking (documented in the CLI). No new secret material.
- **DB schema:** no ALTER TABLE — writes only to existing `humaneval_score` + `coding_score` + `last_verified` columns. `weighted_coding` is deliberately left untouched (BenchLM-owned via `scrape_benchlm.py:70` — crossing populators would collide the tier threshold semantic in `derive_quality_v2.py`).
- **Sandbox provisioning:** `bwrap` must be available on the host running the script (WSL dev + any future cron host). Already a soft-requirement for `libs.subagents` usage; documented in that module's README. If absent, `subagents.sandbox.sandbox_available()` returns False and the module refuses to run tool-enabled agents fail-closed. Plan step: preflight probe for `bwrap --version`; if missing, install via `sudo apt install bubblewrap`.
- **Governance-sync:** none. Hub-only script.

## Constraints

- **Idempotent by construction.** Freshness gate (`last_verified >= today - 60d` skips) matches sibling scrapers. Re-runs never double-write.
- **Fail-open per model.** A single problem's timeout or a bad JSON response never crashes the whole run — just counts that problem as failed and continues.
- **Fail-safe per run.** OR API failure (network, 401, 429) → log WARN, exit 0, don't corrupt DB. Kill switch via `--cost-cap` prevents runaway spend.
- **Sandbox correctness:** the sandbox test (§Success criteria "safety") is BLOCKING — must land as a regression test (`test_sandbox_prevents_fs_write`, `test_sandbox_prevents_shell_call`). Failing to prove sandbox safety = failing to ship.
- **No new packages.** `pyproject.toml`, `requirements.txt`, `uv.lock` untouched.

## Open/blocking unknowns

### Resolved

- **Reinvent HumanEval scoring vs use existing tooling?** — RESOLVED (Revision 2, user pushback): use EvalPlus (1774★, actively maintained). It handles HumanEval + HumanEval+ + MBPP + MBPP+ with OR-compatible backend in one tool.
- **How to get parallelism + downstream reach into `pick_models("code")`?** — RESOLVED (Revision 2 + Pass-1 correction): `libs.subagents.run_agents(specs, repo=…, max_concurrency=len(specs))` for parallel dispatch (owned-paths + bwrap sandbox + cost caps; the explicit `max_concurrency` overrides `run_agents`' default of 4 at `agent.py:431`). `fanout()` is NOT usable — it picks models internally via `pick_models` under the pool ≤$1.5/Mtok cap (so `seed-1.6`/`seed-2.0-lite` at $2.00/Mtok get dropped) AND defaults `record=True`, both wrong here. Downstream reach via direct DB writes to `humaneval_score` + `coding_score` (0-100 scale) + a new `humaneval_score` tier signal added to `derive_quality_v2.py` (Phase F, ~5 LOC), which folds into the `quality_tier` that `pick_models("code")` picks from. `record_agent_run` intentionally NOT called (would misattribute pass@1 to orchestrator, not target — verified `pg_ledger.py:157-172`). `weighted_coding` intentionally NOT written (BenchLM-reserved via `scrape_benchlm.py:70`).
- **Datasets?** — RESOLVED: HumanEval + MBPP (EvalPlus auto-generates HumanEval+ and MBPP+ scores from the same completions). 4 metrics per model, ~$0.665/model average, ~$2.66 total (see §Cost estimate for the per-model breakdown).
- **Sample count per problem (pass@k)?** — RESOLVED: N=1 with `--greedy` (temp=0, pass@1). EvalPlus default.
- **Sandbox mechanism?** — RESOLVED: two independent layers via composition — EvalPlus's own multiprocessing+rlimit inside its subagent runtime, wrapped by subagents' bwrap `--unshare-net --ro-bind`. Defense in depth, zero custom sandbox code.
- **Cost cap default?** — RESOLVED: `$5/model/run` (well above the $1.13 max on any of the 4 Seed target models; catches only runaway loops). Enforced via `AgentSpec.max_cost_usd`.
- **Populate `humaneval_score` OR `coding_score` OR both — and `weighted_coding`?** — RESOLVED via live-verified writer-side survey (2026-07-10): `humaneval_score` and `coding_score` have **zero populators** across the whole `scripts/` tree (both are declared columns waiting for a first writer — this bench is it). `weighted_coding` IS populated — by `scrape_benchlm.py:70` from BenchLM's `categoryScores.coding` composite (0-100 scale; Tier 3 threshold ≥88, Tier 2 ≥70 in `derive_quality_v2.py:87,101`). Decision: bench writes `humaneval_score = pass_humaneval * 100` (single-signal) + `coding_score = mean(HumanEval, HumanEval+, MBPP, MBPP+) * 100` (bench composite, 0-100), and deliberately does NOT touch `weighted_coding` — reserving it for BenchLM composites keeps the tier threshold cross-model-comparable.
- **`FAMILIES` update in same script?** — RESOLVED: separate step in the plan phase; script only writes DB columns. `FAMILIES` edit is a 1-liner in `rank_coding_subagents.py` (Plan Phase E) — adds `bytedance-seed/seed-` prefix only (NOT `bytedance/ui-tars`, which stays out of coding selection by design).
- **Adding new deps allowed?** — RESOLVED: yes for `evalplus>=0.3.0` — this spec IS the authorization per CLAUDE.md's "deps files editable only if the ticket authorises."

### Still-open (each has a named resolution step — all self-service)

1. **HumanEval canonical-solution leakage.** Models trained on GitHub almost certainly saw HumanEval + its reference solutions; newer Seed 2.0 pass@1 may reflect memorization more than reasoning. Partial mitigation IS in scope: EvalPlus's HumanEval+ runs 80× more tests per problem + MBPP+ is a reworked separate dataset — a memorizer of the canonical HumanEval solution can still fail the extended tests. This is the field's standard contamination-lite response. **Follow-up plan (out of scope here):** add `livecodebench_score` column + `microbench_lcb.py` runner that filters to post-model-training-cutoff LCB problems (contamination-proof by construction). **Not blocking** — spec accepts pass@1 as a coarse baseline supplemented by HumanEval+/MBPP+.

2. **`derive_quality_v2.py` threshold calibration** — the new `humaneval_score ≥ X` tier signal needs concrete thresholds. First-Seed-run pass@1 gives us the observed distribution; pick thresholds AT plan-time (Phase F) from that distribution (rough starting point: Tier 3 ≥ 60, Tier 2 ≥ 40, matching the shape of the `weighted_coding` calibration ≥88/≥70 rescaled to HumanEval-only variance). SELF-SERVICE: run the bench first, observe the Seed distribution, then set thresholds in one commit. **Not blocking** — worst case, thresholds are wrong on iteration 1 and adjusted in Phase F review.

Zero cross-AI dependencies, zero unanswered execution-blocking questions. (Residuals from Rev 2 that resolved during this pass: `weighted_coding` column semantics → answered by writer-side grep of `scrape_benchlm.py:70`; UI-TARS coding baseline → out-of-scope by redesign, deferred to a GUI-bench follow-up plan.)

## Handoff

- **Next step (this command, automatic):** `/fabrik-spec-review docs/superpowers/specs/2026-07-10-coding-microbench-runner-design.md`.
- **After CONVERGED + user approval:**
  - Not a persistence-schema change (columns exist) → skip `/fabrik-data-contract`.
  - Not a GUI → skip `/fabrik-ui-design`.
  - `/fabrik-plan-after-chat docs/superpowers/specs/2026-07-10-coding-microbench-runner-design.md`.
  - Then `/fabrik-execute-plan`.

**Expected wall clock (execution):** ~1.5-2h autonomous for plan + implementation (much less code to write than Revision 1 — most of it is EvalPlus wiring + subagents dispatch + DB glue + `derive_quality_v2.py` tier-lift). Then ~30 min real-clock for the actual bench run (4 Seed models × 2 datasets × ~30 min per model, parallelized via `libs.subagents.run_agents(specs, max_concurrency=len(specs))` → ~30 min wall clock total).

**Expected spend:** ~$2.66 for the live bench (4 Seed models × HumanEval + MBPP at real OR prices) + ~$0.30 for `/fabrik-review` pool passes ≈ **$2.96 total**. Delta vs Revision 1 (~$1.11): +$1.85 for 4× the benchmark coverage (HumanEval + HumanEval+ + MBPP + MBPP+) + parallel dispatch (2.5h → ~30 min wall clock).

**Follow-up work explicitly out of scope for this spec (each earns its own plan later):**
- **GUI-agent bench for UI-TARS** — bench `bytedance/ui-tars-1.5-7b` against a suitable GUI benchmark (ScreenSpot / VisualWebBench / WebArena), populate a new `screenspot_score` (or similar) column, and — if it earns it — surface it in a GUI-agent selection MD (a peer of `CODING_SUBAGENT_SELECTION.md`, not the same file). UI-TARS does NOT belong in the coding selection MD by design.
- **Contamination-proof coding bench** — add LiveCodeBench (LCB) via a separate `microbench_lcb.py` runner + `livecodebench_score` column; LCB releases new problems monthly with training-cutoff dates, so per-model filtering to post-cutoff problems is contamination-free by construction. Layer atop this spec's HumanEval+/MBPP+ coarse baseline.

**💡 No fabrik-lib candidate flagged** (Revision 2 change): Revision 1 flagged `code-sandbox-exec` as a candidate for extraction; EvalPlus + subagents composition covers the space cleanly, so a new fabrik-lib module in this domain would be redundant. The composition itself might inspire a small helper in the future (`benchmark-dispatcher` — dispatch EvalPlus-style benchmarks through the subagents runtime with automatic result→column-write reduction across the `agents` schema) but that's speculative and doesn't clear the "concrete second use" bar yet.
