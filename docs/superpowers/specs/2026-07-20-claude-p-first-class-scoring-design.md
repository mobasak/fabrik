# claude -p (native Claude tiers) as first-class CODER + REVIEWER scoring candidates — Design Spec

Status: DRAFT
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
does the expensive inline work today (coding + final review). Cost is **derived from the fixed Claude Max
subscription**, never OpenRouter per-token pricing.

**Why:** 3 rotated Claude Max accounts (~$600/mo) do the bulk of coding/reviewing inline. Measuring where a
cheap OpenRouter model is "good enough" vs where Claude clearly wins is the lever to reserve Claude for
orchestrator / final-review / hard tasks and consolidate **3 accounts → 1 (or 2)** while holding quality.

**Out of scope (here):** research/docs/plan/spec (→ the judged-spec extension); the runtime — the pool never
dispatches `claude -p`, the orchestrator is native Claude always, and Claude spawns its OWN native subagents
off the ranking (§ Boundaries); a PoLL judge.

**Illustrative target row (NOT a measured value — the real numbers come from the run):**
`claude-code/haiku · q<measured> · $<amortized>/1k · <p50>s · claude (subscription-derived)`. (The earlier
`q4.21 · ~$0.02 · 3.5s` was the `anthropic/claude-haiku-4.5` artifact reused + a guessed cost/latency — not a
derivation; deleted.)

---

## What the adversarial review killed (and how this rewrite fixes it)

1. **Quota-% cost derivation → CUT (unsound on this box).** `statusline.json.rateLimits.sevenDay.usedPercent`
   is last-writer-wins across ALL sessions/accounts (H1), has no history, is model-blind if applied as one
   rate (H2), non-identifiable by regression (H3), and breaks on the 5h/7d interaction + weekly reset +
   integer quantization (H4–H6). Replaced by the **amortized model** below, which needs none of it.
2. **plan/spec-generation → REMOVED from this spec.** `structural_grade`'s citation check can't resolve for a
   one-shot model (every cheap model gated out of spec; plan collapses to keyword-regex noise; it's a deferred
   *floor*, not a score). Those roles move to the judged-spec extension untouched.
3. **Transport asymmetry → FIXED.** `claude -p` is dispatched **SINGLE-SHOT, NO tools, NO repo access,
   `--max-turns 1`** — identical protocol to the OpenRouter `_direct_call`/`generate` single completion — so
   the graders measure the same thing. (An earlier draft gave Claude `--allowedTools`/`--add-dir`/multi-turn,
   which rigged coding pass@1 and plan/spec citations in Claude's favor by transport, not quality.)

---

## Chosen approach — one single-shot `claude_p_call` shim + an amortized cost model + a carve-out

### 1. Dispatch shim — VENDOR + ENHANCE claude-evaluator, SINGLE-SHOT

`claude-evaluator._call_cli` ([/opt/fabrik-lib/claude-evaluator/claude_evaluator/core.py:188](/opt/fabrik-lib/claude-evaluator/claude_evaluator/core.py#L188)) already shells `npx @anthropic-ai/claude-code --print --output-format text --model
<m> --system-prompt <s>` (stdin prompt, fail-closed) and is **already vendored in-tree**
([scripts/kilo-benchmarks/vendor/claude_evaluator/](../../scripts/kilo-benchmarks/vendor/claude_evaluator/core.py)). So VENDOR + ENHANCE, not build.

`scripts/kilo-benchmarks/claude_p.py` → `claude_p_call(tier, prompt, *, system, timeout) -> (text, usage)`
wraps it with ONE core enhancement (→ upstream): **`--output-format text` → `json`** to capture the `usage`
token block `_call_cli` discards (`input`/`output`/`cacheCreation`/`cacheRead`). **It adds NO
`--allowedTools`, NO `--add-dir`, and keeps a single turn** — deliberately, to match the OpenRouter single
completion (transport parity). Aliases (grounded on-disk + `claude --help`): `claude-opus-4-8` ·
`claude-sonnet-5` · `claude-haiku-4-5-20251001` · `claude-fable-5`. Ignore the JSON's `total_cost_usd`.

Wired as a **model-namespace branch** (`model.startswith("claude-code/")`) — NOT a `run_fn` — in the two
harnesses, each building its OWN result object from `(text, usage)` (a small adapter; review returns a
`_DirectResult`, coding a `_Gen`):
- **review** — beside `_direct_call` [microbench_review.py:458](../../scripts/kilo-benchmarks/microbench_review.py#L458) / `run_direct` [:514](../../scripts/kilo-benchmarks/microbench_review.py#L514); grader unchanged (`f1(recall,precision)×5`).
- **code** — beside the `_or_run(...)` call in `generate` [microbench_coding_direct.py:243](../../scripts/kilo-benchmarks/microbench_coding_direct.py#L243); grader unchanged (LiveCodeBench `pass@1×5`, single-shot for everyone).

### 2. Subscription-derived cost — AMORTIZE the subscription over global usage, weighted by list-price ratios

No `usedPercent`, no bursts, no per-account attribution — only the global `usage-history.json` (grounded:
per-model per-type tokens, months deep, all accounts aggregated) + Anthropic's published price ratios:
```
w[model][type]     = Anthropic list-price ratio (per model × input/output/cacheWrite/cacheRead)   # ground at build
weighted(x)        = Σ_type w[model][type] · tokens[type]                                          # "list-price value"
monthly_weighted   = Σ over usage-history (all models × types) of weighted(·)                      # global, real
rate ($/w-unit)    = subscription_$per_month ÷ monthly_weighted
cost_usd(run)      = weighted(run) × rate            # same $/1k units as OpenRouter usage.cost → drops into the ranker
```
- **Per-model-weighted** (opus's ratio ≫ haiku's → opus costs more) — fixes the discarded-weighting defect.
- **Robust**: uses only the global token history (which exists + is deep) + the published ratios (stable,
  groundable). Immune to the quota-% file's cross-account/reset/quantization problems.
- **`subscription_$per_month`** = the ACTUAL total ($200 × live account count from `~/.claude/manager-accounts/`;
  ~$600 today). The per-w-unit rate is stable as you consolidate (numerator and the fleet denominator drop
  together), so it needs no "peg."
- **Honest caveat:** this is an *amortized* cost (your share of the fixed fee), so at today's heavy usage the
  per-token rate is LOW — Claude looks cheap. That is truthful ("you get a lot for $600"). The **3→1 decision
  is therefore a QUALITY + CAPACITY call** (move every task where a cheap model's value ≥ Claude's off Claude,
  then see if the remainder fits one account), **not** a manipulated cost. An **optional scarcity multiplier**
  (operator dial) can bias the ranker harder toward cheap models if desired; off by default.

### 3. Gate carve-out — keep `claude-code/*` shortlist-visible (verified clean to add)

Add `or m.startswith("claude-code/")` to `review_eligible`/`code_eligible`
([build_task_baselines.py:150,234](../../scripts/kilo-benchmarks/build_task_baselines.py#L150)) — a single set-comprehension each, consumed by every render site with no other edit (verified). So `claude-code/*`
stays in the `### review`/`### code` sections + the `✅ Selected subagents` shortlist regardless of its
amortized cost (avoiding the haiku-4.5 gated-out artifact); the value *sort* still ranks it by cost, so a
premium tier sits low-but-visible. The carve-out also covers the review `$/run < 0.007` and `p50 ≤ 10s` gates
that a real `claude -p` call (npx cold-start latency) would otherwise trip.

### 4. Doc emit

`rank_task_subagents.py` emits `claude-code/*` into the full review/code tables + the carved-in sections +
shortlists as `claude-code/<tier> · q<score5> · $<amortized>/1k · <p50>s · claude (subscription-derived)` —
parser-compatible (`load_task_ranking`), zero module change (auto-discovery shipped fleet-wide, fabrik-lib ee91f8b).

---

## Rejected alternatives

| Rejected | Why |
|---|---|
| Score Claude via OpenRouter `anthropic/*` (per-token) | Banned; prices the wrong resource (fixed subscription, not per-token) — the mis-price that gated haiku-4.5 out. |
| Quota-% (`sevenDay.usedPercent`) derivation | Unsound on this box: cross-account last-writer-wins, model-blind, non-identifiable, 5h/7d + reset + integer-% noise (adversarial review H1–H6). |
| Give `claude-code/*` tools + multi-turn | Breaks "identical graders" — inflates coding pass@1 + lets only Claude resolve plan/spec citations. Single-shot for everyone. |
| plan/spec generation-scoring (here) | `structural_grade` is a deferred floor; citations unresolvable one-shot → cheap models gated out of spec, plan = noise. → the judged-spec extension. |
| API-equivalent (`total_cost_usd`) as THE cost | Contradicts the operator's "never OpenRouter pricing"; over-prices the sunk subscription. |

---

## External dependencies (grounded 2026-07-20)

| Dep | Use | Grounded |
|---|---|---|
| Claude Code CLI | `--print --model <alias> --output-format json` single-shot dispatch (via `claude-evaluator` → `npx @anthropic-ai/claude-code`; on-box `claude` 2.1.215 same CLI) | `claude --help`: `--print`, `--model` ("alias `fable/opus/sonnet` or full name `claude-fable-5`"), `--output-format` present. Aliases confirmed as live `byModel` keys in `usage-history.json`. ⚠️ `_call_cli` uses `text`, so the `json` `usage` key names are UNexercised in-tree → confirm with ONE real probe at build. |
| claude-manager `usage-history.json` | the amortized denominator (global per-model per-type monthly tokens) | GROUNDED: `~/.claude/.claude-manager/usage-history.json` `days[date].byModel[tier]` = `input/output/cacheRead/cacheCreation`, months deep, **global (no account dimension)** — sufficient for the amortized rate. |
| Anthropic published price ratios | the per-model per-type weights `w[model][type]` | ⚠️ **NOT live-verified this session** (web tools were down in review). Ground the current opus/sonnet/haiku/fable input:output:cache-write:cache-read list prices live at build; cite URL + date. |
| Max 20x price | `subscription_$per_month` | `$200/account/mo` — widely documented but **not live-verified here**; ground at build. Account count from `~/.claude/manager-accounts/` (3 today). |

---

## Internal reuse verdict (vendor-first)

| Capability | Verdict | Module / ref |
|---|---|---|
| Claude Code CLI dispatch (subprocess + `--model` + fail-closed) | **VENDOR + ENHANCE** | `claude-evaluator._call_cli` [core.py:188](/opt/fabrik-lib/claude-evaluator/claude_evaluator/core.py#L188) (already vendored). Enhance (core): `--output-format json` → capture `usage`. **Upstream** to `claude-evaluator/UPSTREAM_FEEDBACK.md` (generic: a json/usage mode for cost tracking). |
| review / code graders + persist + doc-emit + carve-out | **VENDOR as-is** | the 2 harnesses + `build_task_baselines` gates + `rank_task_subagents` — unchanged except the namespace-branch dispatch + `claude-code/*` carve-out |
| amortized cost model | **BUILD** (~40 lines) | `derive_cost.py`: reads `usage-history.json` + a `claude_price_ratios.json` (published ratios) → `rate` → `cost_usd`. Ladder checked: `cost-budget/` (caps+ledger, not a rate), `api-quota/` (X-RateLimit, not a subscription amortization) — neither fits. Project-specific → no fabrik-lib candidate. |

**🆕 fabrik-lib candidate:** none. **Shape/infra:** none — hub-internal `scripts/kilo-benchmarks/` tooling.

---

## Constraints

- **LLM gateway (audited — not a violation):** `claude-code/*` uses the **Claude Code CLI on the subscription**
  (OAuth, no per-token bill) — an already-approved operational path (`watchdog/` runs "llm_client Claude Code
  primary", `claude-evaluator/` dispatches via it). Namespace `claude-code/<tier>`, **never `anthropic/*`**.
- **Identical measurement** — same graders AND same single-shot dispatch protocol as OpenRouter; only the
  backend (CLI vs OpenRouter) and cost basis (amortized subscription vs metered) differ.
- **Cost = amortized subscription** (`weighted(run) × rate`), never OpenRouter pricing; per-type tokens always
  recorded; `total_cost_usd` ignored.
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
the amortized cost model, the carve-out, and the emitted rows; nothing depends on a subagents-module change.

---

## Open / blocking unknowns

**Resolved:** aliases (grounded); `claude-evaluator` VENDOR+ENHANCE (accurate); the amortized cost model
avoids the quota-% defects (uses only global `usage-history` + published ratios); carve-out + seams verified;
transport parity (single-shot) fixes the asymmetry.

**Still open — self-service at build, none blocks the plan:**
- **Anthropic price ratios + Max-20x $ — live-ground at build** (web tools were down this session): the
  per-model input:output:cache list prices + the $200/account price. Cite URL + date. (An error here scales
  the cost linearly but doesn't break the mechanism.)
- **The `json` `usage` key names** — one real `--output-format json` probe at build (`_call_cli` uses `text`).
- **Gate/carve-out policy sign-off** — recommend carve-out + amortized-cost-shown (+ optional scarcity dial);
  operator's final call.

---

## Success criteria

1. `claude_p_call` dispatches all four tiers via `claude -p --output-format json`, **single-shot, no tools**
   (transport parity with OpenRouter), records per-type tokens, in the shape the review/coding graders consume.
2. `claude-code/{opus,sonnet,haiku,fable}` are scored on **review (F1×5) and code (pass@1×5)** with the SAME
   graders + same single-shot protocol as the OpenRouter models.
3. Cost is **amortized-subscription-derived** (`weighted(run) × rate`, `rate = subscription_$ ÷ global monthly
   weighted tokens from usage-history`, per-model list-price weights), never OpenRouter pricing;
   `total_cost_usd` ignored.
4. `TASK_SUBAGENT_SELECTION.md` surfaces `claude-code/*` rows (`… · $<amortized>/1k · … · claude
   (subscription-derived)`) in the full tables + carved-in `### review`/`### code` sections + shortlists;
   parser-compatible, zero module change.
5. The carve-out keeps `claude-code/*` shortlist-visible past the eligibility gates (cost, `$/run`, `p50`) so a
   premium-but-slow native tier stays a routing option; the value sort still ranks it by amortized cost.
6. Resumable (`_measured_models`) + operator-triggered (quota-bound). One test per new behavior (the shim's
   token capture, the amortized-cost math, the namespace-branch adapters, the carve-out render) against temp
   fixtures — no real Claude call in the unit suite.
7. research/docs/plan/spec are NOT scored here — they are added by extending the 2026-07-19 judged spec+plan.
