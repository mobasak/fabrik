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
plan · spec), so `pick_models(task_type)` routes each task to best **value across cheap models AND Claude**.
Cost is **derived from the fixed Claude Max subscription quota**, never OpenRouter per-token pricing.

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

**Out of scope:** the runtime `claude -p` transport + flywheel recording + letting `claude-code/*` through
`pick_models` (the subagents-module AI owns these — § Boundaries); any change to how the 57 OpenRouter models
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

### 3. Subscription-derived cost model (config, quota-based)

`claude -p` has **no per-token bill** — Claude Max is fixed $200/account with an **undisclosed weekly token
quota** (`Q_week`) burned in ~2 days. So:
- **rate[tier]** = `$200 / (Q_week[tier] × 4.33)` → $/Mtok. Per-account and **identical whether you run 1 or
  3 accounts** (rotation buys more tokens at the same price) → the honest marginal $/token.
- **cost_usd(run)** = `tokens × rate[tier]` → same units as OpenRouter `usage.cost`, so it drops straight
  into the existing gates + value ranker with **zero grader change**.
- **`Q_week[tier]`** is an **ops-refreshed config** (`claude_code_rates.json`), authoritative source = the
  operator's **claude-manager extension** (per-tier tokens observed at each weekly-quota trip). A placeholder
  rate ships so the pipeline runs day one; ops refreshes it. (`~/.claude/manager-accounts/` holds only
  rotation credentials — grounded — not token counters; auto-instrumenting `Q_week` from the rotation logs
  is a future follow-on in the sysadmin AI's domain, not this spec.)
- **Policy peg (the 3→1 lever):** compute `rate` against the **$200 single-account TARGET**, not the ~$600
  actual — so the value-ranker prices Claude as if already downsized, reserving it (esp. `opus`) for
  hard/orchestrator/final-review work and moving "good-enough" tasks to the cheap pool.

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
| claude-manager extension | authoritative `Q_week[tier]` per-tier weekly-quota token totals → the rate config | ops-provided (browser extension). `~/.claude/manager-accounts/` = rotation creds only (grounded, not counters). **Named input, not blocking** (placeholder rate ships). |
| Model aliases | `--model` values | grounded (system-confirmed): `claude-opus-4-8` · `claude-sonnet-5` · `claude-haiku-4-5-20251001` · `claude-fable-5`. |

---

## Internal reuse verdict (vendor-first)

| Capability | Verdict | Module / ref |
|---|---|---|
| review / code / research / docs graders + persist + doc-emit | **VENDOR as-is** | the 3 existing harnesses + `build_task_baselines` gates + `rank_task_subagents` — unchanged except the added dispatch path + the `claude-code/*` carve-out |
| plan/spec structural grading | **VENDOR as-is** | `structural_grader.structural_grade` (built, unit-tested) — now fed real generations |
| correlated cold-start prior + measured-source precedence | **VENDOR as-is** | `correlated_prior` + the A6 precedence guard (built) |
| `claude -p` CLI dispatch (subprocess + `--model` + fail-closed) | **VENDOR + ENHANCE** | `claude-evaluator._call_cli` [core.py:188](/opt/fabrik-lib/claude-evaluator/claude_evaluator/core.py#L188) — already vendored in-tree. **Enhance (core):** `--output-format json` to capture the `usage` token block (`_call_cli` uses `text` + discards it) + `--max-turns`/`--allowedTools`/`--add-dir`. **Upstream:** append to `/opt/fabrik-lib/claude-evaluator/UPSTREAM_FEEDBACK.md` — "json-output mode returning the usage token block for cost/benchmark tracking" (generic; any cost-tracking use wants it). The thin `claude_p.py` wrapper (tier→alias, benchmark flags, `(text,usage)` return) stays hub-internal. |
| subscription-derived cost model | **BUILD** (config + ~20 lines) | `claude_code_rates.json` + `derive_cost(tokens, tier, rates)`. Ladder checked: `cost-budget/` (per-project caps + a cost_ledger — RECORDS/CAPS spend, doesn't DERIVE a rate), `api-quota/` (X-RateLimit headers + KeyPool rotation — tracks API-key rate limits, not the subscription's undisclosed weekly-token quota) — neither amortizes a fixed subscription over observed quota, so BUILD is justified. Project-specific pricing policy, not reusable → no fabrik-lib candidate. *(A future integration could feed `derive_cost`'s output into `cost-budget`'s `cost_ledger` for cross-project visibility — out of scope here.)* |

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

## Boundaries (coordinate — do NOT build the other side)

**THIS spec owns:** the `claude -p` **benchmark** dispatch shim in the 3 harnesses; the derived-cost model +
`claude_code_rates.json`; the gate carve-out decision; the emitted `claude-code/*` rows in
`TASK_SUBAGENT_SELECTION.md`; the plan/spec-generation extension.

**The subagents-module AI owns (do NOT build):** the **runtime** `claude -p` transport + flywheel recording +
letting `claude-code/*` through `pick_models` (auto-discovery shipped fleet-wide, fabrik-lib ee91f8b). The
emitted rows are the coordination surface — same doc format, zero parser change.

---

## Open / blocking unknowns

**Resolved this session:** the CLI + flags + aliases (grounded on-box); the three harness seams (read at
path:line); plan/spec-generation via the built structural grader; the cost-model math.

**Still open — each self-service or a named input, none blocks writing the plan:**
- **`Q_week[tier]` values** — *Resolution:* ops-provided config from the claude-manager extension; a
  placeholder rate ships so quality-scoring runs day one, cost re-prices on config refresh. A future
  rotation-log auto-instrumentation is the sysadmin AI's follow-on (flagged, not built here).
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
3. Cost is **subscription-derived** (`tokens × rate[tier]`, rate from `claude_code_rates.json`), never
   OpenRouter pricing; raw tokens always recorded; `total_cost_usd` ignored.
4. `TASK_SUBAGENT_SELECTION.md` surfaces `claude-code/*` rows as `claude-code/<tier> · q<score5> ·
   ~$<derived>/run · <p50>s · claude (subscription-derived)` in the full tables AND the carved-in routing
   sections + `✅ Selected subagents` shortlists — parser-compatible, zero module change.
5. The gate carve-out keeps `claude-code/*` shortlist-visible regardless of the amortized rate; the rate pegs
   to the $200 target so the ranker reserves Claude for hard tasks (the 3→1 lever).
6. The `claude -p` benchmark is resumable (`_measured_models`) + operator-triggered (quota-bound); one test
   per new behavior (the shim's token capture, the derived-cost math, plan/spec generation, the carve-out
   render) against temp fixtures — no real Claude call in the unit suite.
