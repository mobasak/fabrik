# claude -p (native Claude tiers) as first-class CODER + REVIEWER scoring candidates — Design Spec

Status: CONVERGED
Date: 2026-07-20
Author: primary (Claude Opus 4.8)
Scope decision (operator, 2026-07-20): **coder + reviewer FIRST** (this spec). The remaining roles
(research/docs/plan/spec) are added by **extending the existing judged-benchmark spec+plan**
([2026-07-19-task-subagent-scoring-benchmark-design.md](2026-07-19-task-subagent-scoring-benchmark-design.md)) — a
separate follow-on, so the native-Claude leg inherits the judged design (correlated-prior + flywheel for
plan/spec; generation for research/docs) instead of the unsound plan/spec-generation an earlier draft added.
Reviewed adversarially (2 independent Opus passes) — this rewrite fixes the confirmed defects (§ What the review killed).

---

## Goal

Score the operator's own Claude Max tiers — **`claude-code/{opus,sonnet,haiku,fable}`** — on the **coder and
reviewer** benchmarks, the SAME way and next to the 57 OpenRouter models, so the shared ranking shows best
**value across cheap models AND Claude** on one axis. These two roles are first because they are where Claude
does the expensive inline work today (coding + final review). The **ranking cost is the cache-aware
API-equivalent VALUE** of each subscription run's tokens (comparable to the pool); the **real amortized
subscription cost** and the **weekly-quota draw** are shown alongside — never OpenRouter per-token dispatch
pricing (§ 2).

**Why:** 3 rotated Claude Max accounts (~$600/mo) do the bulk of coding/reviewing inline. Measuring where a
cheap OpenRouter model is "good enough" vs where Claude clearly wins is the lever to reserve Claude for
orchestrator / final-review / hard tasks and consolidate **3 accounts → 1 (or 2)** while holding quality.

**Out of scope (here):** research/docs/plan/spec (→ the judged-spec extension); the runtime — the pool never
dispatches `claude -p`, the orchestrator is native Claude always, and Claude spawns its OWN native subagents
off the ranking (§ Boundaries); a PoLL judge.

**Illustrative target row (NOT a measured value — the real numbers come from the run):**
`claude-code/haiku · q<measured> · $<api-equiv>/1k · <p50>s · claude (subscription-run; amort≈$0.09/M, quota-tracked)`.
(The earlier `q4.21 · ~$0.02 · 3.5s` was the `anthropic/claude-haiku-4.5` artifact reused + a guessed
cost/latency — not a derivation; deleted.)

---

## What the adversarial review killed (and how this rewrite fixes it)

1. **Quota-% as a COST rate → CUT (unsound on this box).** `statusline.json.rateLimits.sevenDay.usedPercent`
   is last-writer-wins across ALL sessions/accounts (H1), has no history, is model-blind if applied as one
   rate (H2), non-identifiable by regression (H3), and breaks on the 5h/7d interaction + weekly reset +
   integer quantization (H4–H6). The ranking cost is now the **API-equivalent valuation** (§ 2①), immune to
   all of it. `usedPercent` returns only as ③'s per-run *capacity* proxy — a single isolated before/after read
   in a controlled off-peak window, NOT a $-rate regression across accounts — a different, weaker use H1 bounds.
2. **plan/spec-generation → REMOVED from this spec.** `structural_grade`'s citation check can't resolve for a
   one-shot model (every cheap model gated out of spec; plan collapses to keyword-regex noise; it's a deferred
   *floor*, not a score). Those roles move to the judged-spec extension untouched.
3. **Transport asymmetry → FIXED.** `claude -p` is dispatched **SINGLE-SHOT, NO tools, NO repo access,
   `--max-turns 1`** — identical protocol to the OpenRouter `_direct_call`/`generate` single completion — so
   the graders measure the same thing. (An earlier draft gave Claude `--allowedTools`/`--add-dir`/multi-turn,
   which rigged coding pass@1 and plan/spec citations in Claude's favor by transport, not quality.)

---

## Chosen approach — one single-shot `claude_p_call` shim + a three-number cost model + a carve-out

### 1. Dispatch shim — VENDOR + ENHANCE claude-evaluator, SINGLE-SHOT

`claude-evaluator._call_cli` ([/opt/fabrik-lib/claude-evaluator/claude_evaluator/core.py:188](/opt/fabrik-lib/claude-evaluator/claude_evaluator/core.py#L188)) already shells `npx @anthropic-ai/claude-code --print --output-format text --model
<m> --system-prompt <s>` (stdin prompt, fail-closed) and is **already vendored in-tree**
(`/opt/ai-model-catalog/engine/vendor/claude_evaluator/core.py` (ai-model-catalog)). So VENDOR + ENHANCE, not build.

`/opt/ai-model-catalog/engine/claude_p.py` → `claude_p_call(tier, prompt, *, system, timeout) -> (text, usage)`
wraps it with ONE core enhancement (→ upstream): **`--output-format text` → `json`** to capture the `usage`
token block `_call_cli` discards — the CLI json uses the Anthropic API key names `input_tokens` /
`output_tokens` / `cache_read_input_tokens` / `cache_creation_input_tokens` (snake_case, grounded 2026-07-20;
NOT the `usage-history.json` camelCase `input/output/cacheRead/cacheCreation` — do not conflate the two). **It adds NO
`--allowedTools`, NO `--add-dir`, and keeps a single turn** — deliberately, to match the OpenRouter single
completion (transport parity). Aliases (grounded on-disk + `claude --help`): `claude-opus-4-8` ·
`claude-sonnet-5` · `claude-haiku-4-5-20251001` · `claude-fable-5`. Ignore the JSON's `total_cost_usd`.

Wired as a **model-namespace branch** (`model.startswith("claude-code/")`) — NOT a `run_fn` — in the two
harnesses, each building its OWN result object from `(text, usage)` (a small adapter; review returns a
`_DirectResult`, coding a `_Gen`):
- **review** — beside `_direct_call` [microbench_review.py:458](../../engine/microbench_review.py#L458) / `run_direct` [:514](../../engine/microbench_review.py#L514); grader unchanged (`f1(recall,precision)×5`).
- **code** — beside the `_or_run(...)` call in `generate` [microbench_coding_direct.py:243](../../engine/microbench_coding_direct.py#L243); grader unchanged (LiveCodeBench `pass@1×5`, single-shot for everyone).

### 2. Subscription-run cost — THREE numbers for THREE questions (measure tokens once, calibrate three rates)

One cost number can't do this job, and the earlier amortized-only basis had a fatal flaw (below). The run
executes on the **subscription** (OAuth, no per-token bill), yet the ranker needs a number **comparable to the
OpenRouter pool** (which IS priced at API rates), the operator needs the real spend, AND the 3→1 decision needs
the capacity draw. The operator's deep-research
([../../reference/research/2026-07-20-claude-max-20x-effective-cost-per-token.md](../../reference/research/2026-07-20-claude-max-20x-effective-cost-per-token.md))
establishes these as **three distinct numbers**, and that Claude Max is **10–30× cheaper per token than the
API** — so **cost is NOT the binding constraint; the weekly quota is.** The single input to all three is the
run's raw per-type token counts (the CLI `usage` block's snake_case `input_tokens`/`output_tokens`/
`cache_read_input_tokens`/`cache_creation_input_tokens`) from `--output-format json` — the same `usage` object
`ccusage` reads from `~/.claude/projects/*.jsonl` (research § Measurement: "the raw token count is the only
valid metric"). *Measure the tokens; calibrate three rates.*

**① API-equivalent, cache-aware $ — the RANKING axis** (the benchmark's `$/run` / `$/1k` column, beside the pool):
```
api_equiv = in·P_in + out·P_out + cacheRead·P_in·0.1 + cacheCreation·P_in·(1.25 | 2.0)
```
list prices per tier (Opus $5/$25 · Sonnet $3/$15 · Haiku $1/$5 · Fable $10/$50 per M) + cache multipliers
(read ×0.1, write-5m ×1.25, write-1h ×2.0), grounded 2026-07-20 (§ External dependencies). The CLI's single
`cache_creation_input_tokens` gives no 5m-vs-1h split → default the write multiplier to **1.25×** (Claude
Code's 5-min default; a ttl breakdown, if present, selects ×2.0). Computing ① ourselves from raw tokens (not
`ccusage`'s dollar) also sidesteps ccusage issue #899, which mis-prices 1h writes at 1.25×. This makes `claude-code/*` **comparable to
the pool on one axis**, and it **reserves Claude correctly**: Opus's list price is high, so a value-sort places
it in the premium tier used sparingly — exactly the orchestrator/final-review/hard-tasks intent. It is **not
"OpenRouter pricing"**: the dispatch is the subscription CLI; ① is a *valuation* of the run's own tokens at
list rate (computed by us from raw tokens, NOT the CLI's `total_cost_usd`) — the only metric that yields an
apples-to-apples ranking.

**② Amortized subscription $ — the real out-of-pocket** (shown beside ①, NOT ranked on):
`total_subscription_$ ÷ measured monthly throughput` ≈ **$0.093/M** typical (research § Effective
Cost-Per-Token) → a run costs a few tenths of a cent. This is the number that honours "cost DERIVED from the
subscription" — your actual share of the fixed fee (`$200 × live account count from ~/.claude/manager-accounts/`
÷ global monthly tokens from `usage-history.json`). Kept OFF the ranking because it's throughput-dependent and
sinks every Claude run to ~zero (the exact defect below).

**③ Weekly-quota consumption — the 3→1 DECISION axis** (the binding constraint): the quota meters opaque
server-side "active-compute-hours," **not raw tokens** (research § metering — `/usage` weights differently and
resets weekly). Per-run proxy = the **`statusline.json` `rateLimits.sevenDay.usedPercent` delta** read in an
ISOLATED window (the run is already operator-triggered / off-peak / low-concurrency, § Constraints), OR active
wall-clock seconds — summed over the workload we'd route to `claude -p` subagents vs ONE account's weekly cap.
This — not cost — answers "1 or 2 accounts": move every task where a cheap model's value ≥ Claude's off Claude,
then test whether the remainder fits one account's weekly quota. ③ is a capacity ESTIMATE, not a precise meter.

**Why ① and not amortized-only (the defect this fixes):** the previous §2 ranked on amortized cost, which at
90%-cache-read + heavy usage prices a run at ~$0.001 → Claude wrongly TOPS the cheap-and-good sort, the
opposite of reserving it. ① (list-price valuation) keeps Opus expensive → correctly premium; ② carries the
"you get a lot for the fee" truth as context; ③ carries the real capacity constraint.

**Measure-vs-calibrate (the discipline the "are you sure" caught):** ①/② price the *tokens* (raw, from the
run's `usage`/jsonl — never a guessed allotment); the RATES calibrate separately (list prices for ①,
subscription÷throughput for ②). Rotation- AND concurrency-proof for ①/②: which of the 3 accounts ran it, or
how many ran in parallel, never enters the math. Only ③'s isolated-window read is concurrency-sensitive —
hence the controlled window. An **optional scarcity multiplier** (operator dial) can bias the ranker harder
toward cheap models on top of ①; off by default.

### 3. Gate carve-out — keep `claude-code/*` shortlist-visible (verified clean to add)

Add `or m.startswith("claude-code/")` to `review_eligible`/`code_eligible`
([build_task_baselines.py:150,234](../../scripts/kilo-benchmarks/build_task_baselines.py#L150)) — a single set-comprehension each, consumed by every render site with no other edit (verified). So `claude-code/*`
stays in the `### review`/`### code` sections + the `✅ Selected subagents` shortlist regardless of its
API-equivalent cost (avoiding the haiku-4.5 gated-out artifact); the value *sort* still ranks it by ① cost, so
a premium tier sits low-but-visible. The carve-out (added to the set-comprehension, so it bypasses ALL gates)
matters more under ① than it did under amortized: an Opus tier's high API-equivalent cost trips the review
`$/1k ≤ 0.70` + `$/run < 0.007` gates (and code `$/1k ≤ 3.5`), and npx cold-start latency trips `p50 ≤ 10s` —
all bypassed for `claude-code/*` so a premium-but-slow native tier stays visible.

### 4. Doc emit

`rank_task_subagents.py` emits `claude-code/*` into the full review/code tables + the carved-in sections +
shortlists as `claude-code/<tier> · q<score5> · $<api-equiv>/1k · <p50>s · claude (subscription-run)` — the
`$/1k` cell is **① (ranking parity with the pool)**; the section preamble carries **② amort ≈$/M** and **③
quota-draw** for the operator. Parser-compatible (`load_task_ranking` reads col2=model + last=n, so middle
cells are safe), zero module change (auto-discovery shipped fleet-wide, fabrik-lib ee91f8b).

---

## Rejected alternatives

| Rejected | Why |
|---|---|
| Score Claude via OpenRouter `anthropic/*` (per-token) | Banned; prices the wrong resource (fixed subscription, not per-token) — the mis-price that gated haiku-4.5 out. |
| Quota-% (`sevenDay.usedPercent`) derivation | Unsound on this box: cross-account last-writer-wins, model-blind, non-identifiable, 5h/7d + reset + integer-% noise (adversarial review H1–H6). |
| Give `claude-code/*` tools + multi-turn | Breaks "identical graders" — inflates coding pass@1 + lets only Claude resolve plan/spec citations. Single-shot for everyone. |
| plan/spec generation-scoring (here) | `structural_grade` is a deferred floor; citations unresolvable one-shot → cheap models gated out of spec, plan = noise. → the judged-spec extension. |
| Amortized subscription $ as THE ranking axis | Prices 90%-cache-read runs at ~$0 → Claude wrongly TOPS the cheap-and-good sort, the opposite of reserving it. Amortized is kept as ② (real out-of-pocket, shown); the ranking axis is ① API-equivalent. |
| The CLI `total_cost_usd` field as the ranking $ | It's Claude's own API-rate calc; the valid metric is raw per-type tokens → we compute ① ourselves (ccusage method). `total_cost_usd` ignored. NOT "OpenRouter pricing" — dispatch stays on the subscription CLI; ① is a *valuation* of subscription tokens. |

---

## External dependencies (grounded 2026-07-20)

| Dep | Use | Grounded |
|---|---|---|
| Claude Code CLI | `--print --model <alias> --output-format json` single-shot dispatch (via `claude-evaluator` → `npx @anthropic-ai/claude-code`; on-box `claude` 2.1.215 same CLI) | `claude --help`: `--print`, `--model` ("alias `fable/opus/sonnet` or full name `claude-fable-5`"), `--output-format` present. Aliases confirmed as live `byModel` keys in `usage-history.json`. `json` `usage` keys GROUNDED 2026-07-20 (Anthropic API/JSONL): snake_case `input_tokens`/`output_tokens`/`cache_read_input_tokens`/`cache_creation_input_tokens` (`_call_cli` uses `text` in-tree → one build probe is a sanity check, not an unknown). |
| claude-manager `usage-history.json` | **②'s denominator** (global monthly throughput for the amortized rate) | GROUNDED: `~/.claude/.claude-manager/usage-history.json` `days[date].byModel[tier]` = `input/output/cacheRead/cacheCreation`, months deep, **global (no account dimension)** — sufficient for the amortized rate. |
| `~/.claude/projects/*.jsonl` (ccusage source) | authoritative per-run raw per-type tokens for **①/②** | The `--output-format json` `usage` block is the live per-run source; the jsonl is what `ccusage` parses (research § Measurement) and the cross-check. Key names grounded 2026-07-20 (see CLI row above). |
| claude-manager `statusline.json` `rateLimits.sevenDay.usedPercent` | **③'s** per-run capacity proxy (isolated-window delta) | GROUNDED live snapshot (no history); last-writer-wins across accounts (H1) → read in the controlled off-peak single-session window; active wall-clock seconds is the fallback proxy. |
| Anthropic list prices | **①'s** `P_in`/`P_out` per tier + cache multipliers | GROUNDED 2026-07-20, `platform.claude.com/docs/en/about-claude/pricing`: Opus $5/$25 · Sonnet 4.6 $3/$15 · Haiku 4.5 $1/$5 · **Fable 5 $10/$50 (a real published API price, NOT promo-only)**; cache read ×0.1 / write-5m ×1.25 / write-1h ×2.0 (prompt-caching doc). ⚠️ Sonnet 5 carries an intro **$2/$10 through 2026-08-31** (standard $3/$15 after) — re-confirm at build if scoring `claude-sonnet-5`. |
| Max 20x price | `total_subscription_$` (②) | GROUNDED 2026-07-20, `support.claude.com/en/articles/11049741`: **$200/account/mo**. Account count from `~/.claude/manager-accounts/` (3 today: can/mob/ob, verified on disk). |

---

## Internal reuse verdict (vendor-first)

| Capability | Verdict | Module / ref |
|---|---|---|
| Claude Code CLI dispatch (subprocess + `--model` + fail-closed) | **VENDOR + ENHANCE** | `claude-evaluator._call_cli` [core.py:188](/opt/fabrik-lib/claude-evaluator/claude_evaluator/core.py#L188) (already vendored). Enhance (core): `--output-format json` → capture `usage`. **Upstream** to `claude-evaluator/UPSTREAM_FEEDBACK.md` (generic: a json/usage mode for cost tracking). |
| review / code graders + persist + doc-emit + carve-out | **VENDOR as-is** | the 2 harnesses + `build_task_baselines` gates + `rank_task_subagents` — unchanged except the namespace-branch dispatch + `claude-code/*` carve-out |
| three-number cost model | **BUILD** (~60 lines) | `derive_cost.py`: from a run's raw per-type tokens → **①** `api_equiv` (a `claude_price_ratios.json` of list prices + cache multipliers), **②** `amortized` (`usage-history.json` global throughput ÷ total subscription $), **③** `quota_draw` (`statusline.json` usedPercent delta or active-seconds). Ladder checked: `cost-budget/` (caps+ledger, not a rate), `api-quota/` (X-RateLimit, not a subscription valuation) — neither fits. Project-specific → no fabrik-lib candidate. |

**🆕 fabrik-lib candidate:** none. **Shape/infra:** none — hub-internal `scripts/kilo-benchmarks/` tooling.

---

## Constraints

- **LLM gateway (audited — not a violation):** `claude-code/*` uses the **Claude Code CLI on the subscription**
  (OAuth, no per-token bill) — an already-approved operational path (`watchdog/` runs "llm_client Claude Code
  primary", `claude-evaluator/` dispatches via it). Namespace `claude-code/<tier>`, **never `anthropic/*`**.
- **Identical measurement** — same graders AND same single-shot dispatch protocol as OpenRouter; only the
  backend (CLI vs OpenRouter) and cost basis (subscription-run valuation vs OpenRouter metered) differ.
- **Cost = three subscription-derived numbers** (§ 2): ① API-equivalent valuation (the ranking axis), ②
  amortized subscription (real out-of-pocket, shown), ③ weekly-quota draw (the 3→1 axis) — never OpenRouter
  per-token dispatch pricing; per-type tokens always recorded; the CLI `total_cost_usd` ignored.
- **Quota-bound run** — the ~review 30 + code 50 = 80 problems × 4 tiers ≈ 320 `claude -p` calls consume the
  **shared rotation quota** (subscription-quota-bound, not $-bound). Operator-triggered, off-peak, low
  concurrency, resumable (`_measured_models`); it competes with the watchdog/orchestrator for quota.
- **12-Factor / ops** — stdout only; config via JSON; no secrets in code; no logfiles.

---

## Boundaries

`claude -p` lives ONLY in this benchmark (to produce scores). The pool is OpenRouter-only; the orchestrator is
native Claude always. At runtime the `claude-code/*` scores are **surfaced** in `TASK_SUBAGENT_SELECTION.md`,
and the **native Claude orchestrator reads them and spawns its OWN native Task subagents** on the recommended
tier — `claude-code/*` = spawn native, `openrouter/*` = pool. **This spec owns** the benchmark dispatch shim,
the three-number cost model, the carve-out, and the emitted rows; nothing depends on a subagents-module change.

---

## Open / blocking unknowns

**Resolved:** aliases (grounded); `claude-evaluator` VENDOR+ENHANCE (accurate); the three-number cost model
(§ 2, from the operator's Gemini research) ranks on ① API-equivalent — not amortized — which fixes the "Claude
looks free" inversion, and quarantines `usedPercent` to ③'s isolated capacity proxy; carve-out + seams
verified; transport parity (single-shot) fixes the asymmetry. **External facts live-grounded 2026-07-20**:
Anthropic list prices + cache multipliers (`platform.claude.com/docs/en/about-claude/pricing`), Max-20x $200
(`support.claude.com/.../11049741`), **Fable 5 is a real published API price** (not promo-only), and the CLI
`--output-format json` `usage` keys are snake_case `*_input_tokens` (not the `usage-history.json` camelCase).

**Still open — self-service at build, none blocks the plan:**
- **Sonnet 5 intro pricing** — if the run scores `claude-sonnet-5`, its live rate is the intro **$2/$10 through
  2026-08-31** (standard $3/$15 after); pick the rate live at build. (All other prices grounded 2026-07-20, §
  External dependencies; an error here scales ① linearly but doesn't break the mechanism.)
- **Gate/carve-out policy sign-off** — recommend carve-out + ①-ranked with ②/③ shown (+ optional scarcity
  dial); operator's final call.

---

## Success criteria

1. `claude_p_call` dispatches all four tiers via `claude -p --output-format json`, **single-shot, no tools**
   (transport parity with OpenRouter), records per-type tokens, in the shape the review/coding graders consume.
2. `claude-code/{opus,sonnet,haiku,fable}` are scored on **review (F1×5) and code (pass@1×5)** with the SAME
   graders + same single-shot protocol as the OpenRouter models.
3. Cost is **three subscription-derived numbers** (§ 2): ① API-equivalent cache-aware valuation from the run's
   raw tokens (the ranking axis), ② amortized subscription $ (real out-of-pocket, shown), ③ weekly-quota draw
   (the 3→1 axis) — never OpenRouter per-token dispatch pricing; the CLI `total_cost_usd` ignored.
4. `TASK_SUBAGENT_SELECTION.md` surfaces `claude-code/*` rows (`… · $<api-equiv>/1k · … · claude
   (subscription-run)`, with ② amort + ③ quota in the section preamble) in the full tables + carved-in
   `### review`/`### code` sections + shortlists; parser-compatible, zero module change.
5. The carve-out keeps `claude-code/*` shortlist-visible past the eligibility gates (`$/1k`, `$/run`, `p50`) so a
   premium-but-slow native tier stays a routing option; the value sort still ranks it by ① API-equivalent cost.
6. Resumable (`_measured_models`) + operator-triggered (quota-bound). One test per new behavior (the shim's
   token capture, the three-number cost math (①/②/③), the namespace-branch adapters, the carve-out render)
   against temp fixtures — no real Claude call in the unit suite.
7. research/docs/plan/spec are NOT scored here — they are added by extending the 2026-07-19 judged spec+plan.
