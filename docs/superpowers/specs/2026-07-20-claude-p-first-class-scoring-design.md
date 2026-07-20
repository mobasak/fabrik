# claude -p (native Claude tiers) as first-class scoring candidates — Design Spec

Status: CONVERGED
Date: 2026-07-20
Author: primary (Claude Opus 4.8)
Extends: [2026-07-19-task-subagent-scoring-benchmark-design.md](2026-07-19-task-subagent-scoring-benchmark-design.md) (CONVERGED, executed) — this adds the native-Claude leg + makes plan/spec generation-benchmarked.
Handover: fabrik-lib subagents-module AI, 2026-07-20 (see § Boundaries).

---

## Goal

Score the operator's own Claude Max tiers — **`claude-code/{opus,sonnet,haiku,fable}`** — on the **same
benchmarks** as the 57 OpenRouter models, across **all six task types** (review · code · research · docs ·
plan · spec), so the shared ranking (`pick_models` + `TASK_SUBAGENT_SELECTION.md`) shows best **value across
cheap models AND Claude** on one axis. The benchmark only *produces the scores*; the **native Claude
orchestrator reads the ranking and routes each task** — cheap OpenRouter model via the pool, or its own native
Claude subagent — accordingly (see § Boundaries: the pool never dispatches `claude -p`). Cost is **derived from
the fixed Claude Max subscription quota**, never OpenRouter per-token pricing.

**Why (operator):** 3 rotated Claude Max accounts (~$600/mo effective; $200/account) do the bulk of
coding/reviewing inline — the expensive fixed subscription is the workhorse. The weekly quota is burned in
~2 days per account, forcing rotation. The lever: **find, per task type, the sweet spot where a cheap
OpenRouter model is "good enough" and Claude is reserved for orchestrator / final-review / hard tasks** →
consolidate 3 accounts → **1 (or 2)** while holding quality.

**Load-bearing invariant:** quality is MEASURED (score5 / pass@1, identical graders); Claude's cost is
DERIVED from the $200 subscription — never OpenRouter pricing. Mis-price it and you reproduce the live
artifact where `anthropic/claude-haiku-4.5` scored grade A / 4.21 but showed `$1.867/1k` and was gated
INELIGIBLE — the exact exclusion this spec prevents.

**Target row (operator, verbatim) — for ALL four tiers, every task type they're scored on:**
```
claude-code/haiku    q4.21   ~$0.02/run   3.5s   claude (subscription-derived)
```
i.e. `claude-code/<tier> | q<score5> | ~$<derived>/run | <p50>s | claude (subscription-derived)`.

**Out of scope:** the **native orchestrator's runtime routing** (Claude's own Task-tool decision to spawn a
native subagent on a recommended tier — informed by these scores, but Claude's logic, not a pool transport; see
§ Boundaries — there is NO runtime `claude -p` transport to build); any change to how the 57 OpenRouter models
are scored; a PoLL LLM-judge (still deferred).

---

## Chosen approach — one shared `claude_p_call` shim, three harnesses, config-derived cost

Reuse the three existing, proven benchmark harnesses unchanged except for **one added dispatch path**, and
add a **config-driven subscription-derived cost model**. This is the lean, low-maintenance choice: the
graders, persistence, gates, and doc-emit already exist and are reviewed; we add a thin CLI shim + a rate
config, not a fourth benchmark.

### 1. One dispatch shim — VENDOR + ENHANCE claude-evaluator's Claude Code CLI primitive

The Claude Code CLI subprocess dispatch already exists: **`fabrik-lib/claude-evaluator._call_cli`**
([/opt/fabrik-lib/claude-evaluator/claude_evaluator/core.py:188](/opt/fabrik-lib/claude-evaluator/claude_evaluator/core.py#L188)) shells `npx @anthropic-ai/claude-code --print --output-format text
--model <config.model> --system-prompt <…>` (stdin prompt, fail-closed on non-zero exit), and it is
**already vendored in-tree** ([scripts/kilo-benchmarks/vendor/claude_evaluator/](../../scripts/kilo-benchmarks/vendor/claude_evaluator/core.py), Phase B, for the research tiebreak). So this is **VENDOR + ENHANCE, not a fresh build.**

`scripts/kilo-benchmarks/claude_p.py` → `claude_p_call(tier, prompt, *, system, max_turns, tools, add_dir,
timeout) -> (text, usage)` **wraps the vendored `_call_cli`** with two ENHANCEMENTS (core changes →
upstream, see the verdict table):
- **`--output-format text` → `json`** so the outer JSON carries the **`usage` token block** the cost model
  needs — `_call_cli` today discards it (it only needs the result text). Parse `result` (the answer, in the
  shape the graders expect) + `usage{input_tokens, output_tokens, cache_creation_input_tokens,
  cache_read_input_tokens}`. **Record RAW tokens always; ignore `total_cost_usd`** (per-token estimate ≠
  subscription cost — handover §4).
- **benchmark flags** `--max-turns N`, `--allowedTools Read Grep Glob`, `--add-dir <dir>` (the coding task
  needs repo access) — `_call_cli` passes none today.
- inherits `_call_cli`'s guards: validated `--model` alias, argv (never `shell=True`), timeout, non-zero
  exit → RuntimeError → errored slot (excluded from grading, never scored 0). Aliases (grounded,
  system-confirmed): `claude-opus-4-8` · `claude-sonnet-5` · `claude-haiku-4-5-20251001` · `claude-fable-5`
  (via `npx @anthropic-ai/claude-code`, i.e. the same Claude Code CLI as the on-box `claude` 2.1.215).

Wired as the **THIRD dispatch path** in each harness, selected when the model id starts `claude-code/`:
- **review** — beside `_direct_call` [microbench_review.py:458](../../scripts/kilo-benchmarks/microbench_review.py#L458) / `run_direct` [:514](../../scripts/kilo-benchmarks/microbench_review.py#L514); grader unchanged (`f1(recall,precision)×5`).
- **code** — beside the `_or_run`/`_transport.run` call in `generate` [microbench_coding_direct.py:205](../../scripts/kilo-benchmarks/microbench_coding_direct.py#L205); grader unchanged (LiveCodeBench `pass@1×5`).
- **research/docs** — as an injectable `run_fn` in `microbench_judged.generate()` (the seam already exists — `run_fn` is a param, used by `--smoke`'s echo).

### 2. plan/spec become generation-benchmarked (the one design change)

Today plan/spec are correlated-prior only (no generation) — so no model, cheap or Claude, is actually
*measured* on them. To score **all** models uniformly, make plan/spec generation-benchmarked like
research/docs:
- add small **fabrik-private plan/spec PROMPT corpora** (`corpora/plan_qa.json`, `spec_qa.json`): ~6–8 items
  each, `{prompt, [reference/rubric hints]}` — "write a plan/spec for <fabrik-private task X>".
- every model generates a plan/spec; **`structural_grader.structural_grade`** (already built, unit-tested)
  scores it (phases · runnable gates · resolving `path:line` citations · sections · shape).
- wire plan/spec into `microbench_judged.main()`'s `--all` generation path (today it refuses them) + add
  `plan`/`spec` to `_CORPUS_FILES`.
- `correlated_prior` stays as the cold-start seed; the **measured** structural score supersedes it via the
  existing `microbench_judged:*` source-precedence guard (already built, A6).

### 3. Subscription-derived cost model — auto-derived from the claude-manager extension's on-disk data

`claude -p` has **no per-token bill** — Claude Max 20x is fixed $200/account with an **undisclosed,
model-weighted weekly quota**. But the absolute allotment is never needed: the **claude-manager extension
(`vishalguptax.claude-manager`) already records the two signals on disk** (grounded 2026-07-20):
- **`~/.claude/.claude-manager/statusline.json` → `rateLimits.sevenDay.usedPercent`** — Anthropic's OWN
  **model-weighted %** of the weekly quota consumed (e.g. `{"usedPercent": 36, "resetsAt": 1784721600}`). It
  already encodes opus-counts-heavier-than-haiku, so the weighting is observed, not guessed.
- **`~/.claude/.claude-manager/usage-history.json` → `days[<date>].byModel[<tier>]`** — exact per-tier tokens
  per day (`input`/`output`/`cacheRead`/`cacheCreation`), for `claude-opus-4-8`/`claude-sonnet-5`/
  `claude-haiku-4-5-20251001`/`claude-fable-5`, with months of history.

**Derivation (the undisclosed quota cancels — only the FRACTION consumed is used). ⚠️ weight the token
TYPES — `byModel` shows `cacheRead` dwarfs `input+output` ~300× and Anthropic prices it near-zero, so a
flat token count mis-prices badly:**
```
weekly $/account   = $200 / 4.33 ≈ $46.15
eff_units(x)       = w_in·input + w_out·output + w_cc·cacheCreation + w_cr·cacheRead   # per-type weights
$ burned in window = Δ(sevenDay.usedPercent) × $46.15
rate ($/eff-unit)  = ($46.15 × Δ%used) ÷ Δ eff_units(window)          # from the LOGGED usedPercent + byModel
cost_usd(run)      = eff_units(run) × rate                            # run's OWN per-type tokens, cache-light
```
`--output-format json` reports the four token types per call, so `eff_units` is computable exactly. The
weights `w_*` are either Anthropic's published input:output:cache-write:cache-read **price ratios** (grounded
at build) OR **regressed** empirically: `Δ%used ~ (input, output, cacheCreation, cacheRead)` across logged
windows → the four weights, no assumption. (The benchmark's fresh calls are cache-light, so its cost is
dominated by input+output regardless — the weighting mostly affects reading the orchestrator's usage during
calibration.)
- **Measure tokens per run (confounder-proof), then cost = tokens × a CACHED rate — never read Δ%used live
  during a run.** Each `claude -p --output-format json` call yields its OWN `usage` tokens, summed per model:
  exact, per-call, and immune to **rotation mid-run** (same tokens whichever account serves it) and
  **concurrent usage** (the orchestrator + other sessions hit the same accounts — counting only the benchmark's
  own calls excludes them). `total_$[model] = tokens[model] × rate[model]`; `$/run`, `$/1k` derive exactly as
  the coding/review benches do from `usage.cost`.
- **`rate` (per eff-unit) is calibrated SEPARATELY (a stable constant), not from the noisy run.** ⚠️
  `sevenDay.usedPercent` is a **live snapshot only** (grounded: `statusline.json` is atomically overwritten by
  `statusline-tap.js` each update — NO history in `usage-history.json`). So calibration needs one of: **(a) a
  tiny `usedPercent` logger** — a periodic appender snapshotting `statusline.json.rateLimits` to a history file
  (the honest fix; also feeds the regression), or **(b) controlled before/after bursts** — read `usedPercent`,
  run a burst big enough to move the integer % measurably, read again. Then `rate = ($46.15 × Δ%used) ÷ Δ
  eff_units`, cached in `claude_code_rates.json`. Every run thereafter multiplies its own eff_units by the
  cached rate. (Reading Δ%used *during* a rotating, concurrently-shared benchmark would over-attribute — hence
  the measure/calibrate split.)
- **cost_usd** drops straight into the existing gates + value ranker (`$/1k`) with **zero grader change**.
  `total_cost_usd`/`statusline.cost.totalUsd` are kept only as a "what OpenRouter would charge" cross-check,
  never as the subscription cost.
- **The 3→1 lever is NOT a rate peg** (the amortized $/token is intrinsic — identical for 1 or 3 accounts):
  it is the **value ranking** — move every task where a cheap model's value ≥ Claude's off Claude, then check
  whether the Claude-only remainder fits one account's weekly quota. An **optional scarcity multiplier**
  (`current-weekly-burn ÷ one-account capacity`, ≈3.5× while oversubscribed) is a tunable operator dial that
  pushes the ranker harder toward cheap models — an explicit knob, not a hidden peg.

### 4. Gate treatment — carve-out + derived cost shown (recommend; operator's final call)

A `claude-code/*` **carve-out**: always shortlist-visible for routing (never hard-gated out like the
haiku-4.5 artifact), **with the derived cost shown** so the ranker prefers cheap models when quality is
comparable and reaches for Claude only where it wins. (Alternative — the same derived-cost gate — is
recorded as the rejected option; a pure carve-out that *ignores* cost would over-route to Claude and hold
spend at $600.) `judged_eligible`/`review_eligible`/`code_eligible` gain a `claude-code/*` bypass that keeps
them in the `### <task>` section + the `✅ Selected subagents` shortlist regardless of the amortized rate.

### 5. Doc emit — the operator's row shape

`rank_task_subagents.py` emits `claude-code/*` into the full tables AND (carved-in) the `### review`/`###
code`/`### research`/`### docs`/`### plan`/`### spec` routing sections + the `✅ Selected subagents`
shortlists, in the shape `claude-code/<tier> · q<score5> · ~$<derived>/run · <p50>s · claude
(subscription-derived)`. Format matches the module's parser (`load_task_ranking`: decimal rank + `/`-cell) so
it ingests with **zero code change** — fleet-wide auto-discovery already shipped (fabrik-lib ee91f8b).

**Leanness grounding (1c) — internal precedent, not an external cite.** The lean pattern is proven *in this
repo*, which is the strongest grounding: (a) the three benchmarks already normalize a heterogeneous backend's
cost to a common `$/token → $/1k → value` axis for ranking (`microbench_coding_direct` / `microbench_review`
`usage.cost`); (b) `claude-evaluator` already proves the Claude Code CLI subscription-dispatch path works +
is vendored + tested. So the design is *reuse the measured graders + reuse the existing CLI dispatch (enhanced
for tokens) + one small cost adapter* — the smallest change that adds Claude to the same ranking. No external
"best-practice" claim is load-bearing here (the approach is dictated by the existing harness architecture), so
none is cited — the internal precedent at the cited `path:line` is the grounding.

---

## Rejected alternatives

| Rejected | Why |
|---|---|
| Score Claude via **OpenRouter `anthropic/*`** (per-token) | Banned (per-token OR Claude); and it prices the WRONG resource — the operator pays the fixed subscription, not per-token. This is the exact mis-price that gated haiku-4.5 out. |
| A **fourth benchmark harness** for Claude | Reinvents the graders/persist/emit; the three harnesses already measure quality identically — only the transport differs. One shim, not a harness. |
| **Pure carve-out** (Claude always shortlisted, cost ignored) | Over-routes to Claude → holds spend at $600, defeats the 3→1 goal. Carve-out **with derived cost shown** is the fix. |
| Leave plan/spec **correlated-prior only** | Then no model is *measured* on plan/spec — "all models, all task types" is impossible. Generation-benchmark them. |
| Peg the rate to the **$600 actual** spend | Prices Claude as cheap (amortized over 3 accounts) → ranker keeps picking it → no consolidation pressure. Peg to the $200 target. |

---

## External dependencies (grounded this session, 2026-07-20)

| Dep | Use | Grounded |
|---|---|---|
| Claude Code CLI | the `--print --model <alias> --output-format json` dispatch (via `claude-evaluator._call_cli` → `npx @anthropic-ai/claude-code`; the on-box `claude` 2.1.215 is the same CLI) | flags grounded: `--print/-p`, `--output-format`, `--model`, `--add-dir`, `--allowedTools`, `--max-turns` (`claude --help`, 2026-07-20) + `_call_cli` [core.py:197-208](/opt/fabrik-lib/claude-evaluator/claude_evaluator/core.py#L197). ⚠️ **`_call_cli` uses `--output-format text`, so the `json` `usage`-block shape is UNexercised in-tree** — its exact keys (`input_tokens`/`output_tokens`/`cache_*`) are a named open item, confirmed by ONE real `--output-format json` probe before parsing (bounded, single call). |
| claude-manager extension (`vishalguptax.claude-manager`) | the on-disk quota + per-tier token data the cost model reads | **GROUNDED 2026-07-20**: `statusline.json` → `rateLimits.sevenDay.usedPercent` (Anthropic's model-weighted weekly-quota %, e.g. 36, + `resetsAt`) — ⚠️ **LIVE snapshot only, atomically overwritten, no history** → a `usedPercent` logger is needed. `usage-history.json` → `days[date].byModel[tier]` = exact **per-type** tokens (`input`/`output`/`cacheCreation`/`cacheRead`, months deep) — ⚠️ `cacheRead` ~300× `input+output` + priced near-zero → weight the types. (`~/.claude/manager-accounts/` = rotation creds only, the earlier miss.) |
| Model aliases | `--model` values | grounded (system-confirmed): `claude-opus-4-8` · `claude-sonnet-5` · `claude-haiku-4-5-20251001` · `claude-fable-5`. |

---

## Internal reuse verdict (vendor-first)

| Capability | Verdict | Module / ref |
|---|---|---|
| review / code / research / docs graders + persist + doc-emit | **VENDOR as-is** | the 3 existing harnesses + `build_task_baselines` gates + `rank_task_subagents` — unchanged except the added dispatch path + the `claude-code/*` carve-out |
| plan/spec structural grading | **VENDOR as-is** | `structural_grader.structural_grade` (built, unit-tested) — now fed real generations |
| correlated cold-start prior + measured-source precedence | **VENDOR as-is** | `correlated_prior` + the A6 precedence guard (built) |
| `claude -p` CLI dispatch (subprocess + `--model` + fail-closed) | **VENDOR + ENHANCE** | `claude-evaluator._call_cli` [core.py:188](/opt/fabrik-lib/claude-evaluator/claude_evaluator/core.py#L188) — already vendored in-tree. **Enhance (core):** `--output-format json` to capture the `usage` token block (`_call_cli` uses `text` + discards it) + `--max-turns`/`--allowedTools`/`--add-dir`. **Upstream:** append to `/opt/fabrik-lib/claude-evaluator/UPSTREAM_FEEDBACK.md` — "json-output mode returning the usage token block for cost/benchmark tracking" (generic; any cost-tracking use wants it). The thin `claude_p.py` wrapper (tier→alias, benchmark flags, `(text,usage)` return) stays hub-internal. |
| subscription-derived cost model | **BUILD** (~60 lines) | a tiny `usedPercent` logger (appends `statusline.json.rateLimits` snapshots → JSONL, since it has no history) + `derive_rates.py` (logger history + `usage-history.json` type-weighted → `rate` → `claude_code_rates.json`) + `derive_cost(eff_units, tier, rates)`. Ladder checked: `cost-budget/` (per-project caps + a cost_ledger — RECORDS/CAPS spend, doesn't DERIVE a rate), `api-quota/` (X-RateLimit headers + KeyPool rotation — tracks API-key rate limits, not the subscription's weekly quota) — neither amortizes a fixed subscription over observed quota, so BUILD is justified. Project-specific → no fabrik-lib candidate. *(Future: feed `derive_cost` output into `cost-budget`'s `cost_ledger` — out of scope.)* |

**🆕 fabrik-lib candidate:** none (hub-internal; the reusable runtime transport is the subagents module's, not ours).

**Shape/infra:** none — hub-internal `scripts/kilo-benchmarks/` tooling, run by the operator / `daily_refresh.sh`. No deployed service, no `shape:` flags, no compose.

---

## Constraints

- **LLM gateway (constraint-audited — NOT a violation)** — the "OpenRouter-only, no direct vendor SDK" ban
  targets the per-token `@anthropic-ai/sdk` / `anthropic/*` API. `claude-code/*` uses the **Claude Code CLI on
  the subscription** (OAuth, no API key, no per-token bill) — an **already-approved operational path**, grounded
  in two live fabrik-lib modules: `watchdog/` runs "**llm_client Claude Code primary** + OpenRouter fallback"
  and `claude-evaluator/` dispatches via the Claude Code CLI. So this reuses an established pattern, not a new
  gateway. Namespace `claude-code/<tier>`, **never `anthropic/*`** (that per-token OR route stays banned).
- **Quality graders unchanged** — identical score5/pass@1; only the transport + cost differ.
- **Cost derived, never OpenRouter pricing** — `tokens × rate[tier]`, rate from config.
- **Quota-bound, not $-bound** — the ~440 `claude -p` invocations (review 30 + code 50 + research 8 + docs 6
  + plan/spec ~6–8 each ≈ 110 problems × 4 tiers) consume the **shared rotation quota**. Run off-peak, low
  concurrency, resumable (`_measured_models`); it competes with the watchdog/sysadmin for quota. Operator-triggered, never cron.
- **12-Factor / ops** — stdout only; config via env/JSON; temp-safe; no logfiles.

---

## Boundaries — `claude -p` lives ONLY in the benchmark (no runtime pool transport)

**Corrected (operator, 2026-07-20):** the subagents module will **NOT** dispatch `claude -p`. The pool is
**OpenRouter-only**, and the **orchestrator is native Claude (opus/fable) always** — it is not a pool-dispatched
worker. So `claude -p` exists **only in this benchmark**, purely to *produce the scores*. There is no runtime
`claude -p` transport to coordinate — the handover's "runtime transport + let claude-code/* through pick_models"
is superseded by this.

**Runtime routing (informational — not built here):** the benchmark's `claude-code/*` scores are **surfaced**
(mentioned) in `TASK_SUBAGENT_SELECTION.md` + whatever ranking the subagents module reads. The **native Claude
orchestrator consults that ranking and spawns its OWN native subagents** (Task tool, opus/sonnet/haiku) for the
recommended tier — dispatch differs by **namespace**: a `claude-code/*` pick = "spawn a native subagent," an
`openrouter/*` pick = "dispatch via the pool." Same ranking, two dispatch mechanisms; the pool never calls
`claude -p`.

**THIS spec owns (all of it):** the `claude -p` **benchmark** dispatch (VENDOR+ENHANCE claude-evaluator); the
derived-cost model + `claude_code_rates.json`; the gate carve-out; the emitted `claude-code/*` scoring rows.
Nothing depends on a subagents-module change — the emitted rows (same doc format, zero parser change) are the
whole interface; how the orchestrator acts on them is Claude's native decision.

---

## Open / blocking unknowns

**Resolved this session:** the CLI + flags + aliases (grounded on-box); the three harness seams (read at
path:line); plan/spec-generation via the built structural grader; the cost-model math.

**Grounded this session (the DATA source is confirmed on-disk):** the claude-manager extension records the
live `sevenDay.usedPercent` (`statusline.json`) + exact per-tier per-type tokens (`usage-history.json byModel`)
— so no disclosed allotment is needed. But two calibration items are genuinely open (verified, not
hand-waved):

**Still open — self-service at build, none blocks writing the plan:**
- **A `usedPercent` logger** — `sevenDay.usedPercent` is a LIVE snapshot only (no history; verified). *Resolution:*
  add a tiny periodic appender (snapshot `statusline.json.rateLimits` → a JSONL history) so `Δ%used` is
  measurable across windows; until it has run a while, fall back to controlled before/after calibration bursts.
- **Per-token-type weights** — `cacheRead` dwarfs `input+output` ~300× and is priced near-zero, so cost must
  weight the four types. *Resolution:* seed `w_*` from Anthropic's published input:output:cache-write:cache-read
  price ratios (ground live at build), then refine by regressing `Δ%used` on the four token types once the logger
  has data. (Benchmark calls are cache-light, so its own cost is input+output-dominated regardless.)
- **Gate policy (carve-out vs derived-cost gate)** — *Resolution:* recommend carve-out + derived-cost-shown
  (operator intent: reserve Claude for hard tasks). Surfaced for the operator's final sign-off; the
  implementation makes it a one-flag choice.
- **Exact `usage` JSON keys** — *Resolution:* one real `--output-format json` probe at convergence confirms
  the token key names before parsing (bounded, $0-adjacent single call).

---

## Success criteria

1. `claude_p_call` dispatches all four tiers via `claude -p --output-format json`, records raw tokens, in the
   shape the review/coding/judged graders consume — one shim, three harnesses.
2. `claude-code/{opus,sonnet,haiku,fable}` are **scored on all six task types** with the SAME graders as the
   OpenRouter models (review F1×5, code pass@1×5, research EM/F1, docs recall/precision, plan/spec
   structural) — plan/spec now generation-benchmarked.
3. Cost is **subscription-derived** (`eff_units × rate`, `eff_units` = type-weighted tokens so near-free
   `cacheRead` doesn't swamp it), never OpenRouter pricing; `rate` derived from the claude-manager
   `sevenDay.usedPercent` (via a logger, since it's snapshot-only) × $46.15/wk ÷ `eff_units`; per-type tokens
   always recorded; `total_cost_usd` ignored.
4. `TASK_SUBAGENT_SELECTION.md` surfaces `claude-code/*` rows as `claude-code/<tier> · q<score5> ·
   ~$<derived>/run · <p50>s · claude (subscription-derived)` in the full tables AND the carved-in routing
   sections + `✅ Selected subagents` shortlists — parser-compatible, zero module change.
5. The gate carve-out keeps `claude-code/*` shortlist-visible regardless of the amortized rate; the rate pegs
   to the $200 target so the ranker reserves Claude for hard tasks (the 3→1 lever).
6. The `claude -p` benchmark is resumable (`_measured_models`) + operator-triggered (quota-bound); one test
   per new behavior (the shim's token capture, the derived-cost math, plan/spec generation, the carve-out
   render) against temp fixtures — no real Claude call in the unit suite.
