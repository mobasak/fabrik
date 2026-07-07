# Handoff — Coding-subagent doc must split Auto vs On-request tiers

**From:** best-model-suggester AI (fabrik hub, plan `docs/development/plans/archived/2026-07-05-plan-1-best-model-suggester.md` — EXECUTED 2026-07-07).
**To:** kilo-benchmarks AI (owner of `scripts/kilo-benchmarks/rank_coding_subagents.py` + `docs/reference/kilo/CODING_SUBAGENT_SELECTION.md`).
**Date:** 2026-07-08.
**Priority:** high — the current shipped state is silently violating the operator's cost policy on every daily refresh.

---

## The core ask (verbatim from operator)

> Don't remove any models — keep adding and benchmarking everything (glm, kimi, grok, qwen, and every future model). The goal is **separation**, not deletion.
>
> Split `CODING_SUBAGENT_SELECTION.md` into two tiers by the output-price rule:
>
> - **Auto** — OpenRouter output ≤ **$1.5/Mtok** — currently `deepseek/deepseek-v4-flash`, `deepseek/deepseek-v3.2`, `deepseek/deepseek-v4-pro`, `minimax/minimax-m2.5`, `minimax/minimax-m3`. **This is the only tier the module auto-selects from** (`pick_models` / the vendored `_TABLE`).
> - **On-request** — output > $1.5 — `glm-5/5.x`, `kimi`, `grok`, `qwen`, etc. Keep them fully benchmarked and priced, but tagged so `pick_models` never auto-promotes them — they're selectable only when the operator names one.
>
> Concretely: expose the Auto (≤$1.5) subset distinctly — a separate section, or a `tier: auto|on-request` / `auto_selectable: true` column — because the module reads this doc via `SUBAGENT_SELECTION_DOC` and it overrides the vendored default. If the doc doesn't separate them, a fresh sync silently re-admits the pricier models into auto-selection and undoes the cost policy.
>
> The tier boundary is a filter/flag, **not a cut**: a pricier model that benchmarks brilliantly stays in On-request (available when the operator asks), it just never enters Auto until its price drops ≤ $1.5. A new cheaper model that clears $1.5 auto-joins Auto. This matches the operator's `62-using-subagents.md` (Auto vs On-request tiers) and the fabrik-lib module's vendored `_TABLE`.

---

## Ground truth — why this is urgent (evidence, not opinion)

### 1. The binding rule already exists in the rules pack

**`.windsurf/rules/core/62-using-subagents.md:39-71`** already states the policy explicitly:

> **Approved pool models — the ≤ $1.5/Mtok output rule (BINDING)**
> The pool is defined by a **rule, not a frozen list: OpenRouter output price ≤ $1.5/Mtok.** …anything over $1.5 is **never auto-selected** (glm-5/5.x ~$3+, kimi $2–3.5, grok $2.5, qwen $3.75 — priced only for explicit opt-in benchmarks).
>
> **Two tiers — the benchmark keeps ALL models; it only *separates* which are auto-selectable:**
>
> | Tier | Members | Auto-selection |
> |---|---|---|
> | **Auto** (output ≤ $1.5/Mtok) | the 5 above | `pick_models` picks freely — **no approval** |
> | **On-request** (output > $1.5) | `glm-5/5.x` · `kimi` · `grok` · `qwen` (+ any future pricier) — still benchmarked + priced, just **never auto** | **only when the operator names/approves it this turn** |
>
> ⚠️ **Three sources must agree or the cost policy silently drifts:** the module's vendored `_TABLE` (set to the ≤$1.5 pool), the flywheel-refreshed **`CODING_SUBAGENT_SELECTION.md`** (which **overrides** the vendored default via `SUBAGENT_SELECTION_DOC`), and **this pack**. The **flywheel→doc aggregation MUST filter to output ≤ $1.5/Mtok** — else a refreshed doc re-admits glm/kimi/grok/qwen and undoes the policy.

### 2. Current `CODING_SUBAGENT_SELECTION.md` state VIOLATES the rule

The doc dated 2026-07-07 has **34+ models in one flat `### code` table** with no tier separation. Verbatim excerpt (columns: `In $/M`, `Out $/M`):

| # | Model | In $/M | **Out $/M** | Notes |
|---:|---|---:|---:|---|
| 1 | `minimax/minimax-m2.5` | 0.120 | **0.480** | ✓ Auto |
| 2 | `z-ai/glm-5` | 0.600 | **1.920** | ✗ Over $1.5 — SHOULD BE On-request |
| 3 | `deepseek/deepseek-v3.2` | 0.229 | **0.343** | ✓ Auto |
| 4 | `z-ai/glm-4.6` | 0.430 | **1.740** | ✗ Over $1.5 |
| 5 | `z-ai/glm-4.5` | 0.600 | **2.200** | ✗ Over $1.5 |
| 6 | `deepseek/deepseek-r1` | 0.700 | **2.500** | ✗ Over $1.5 |
| 7 | `moonshotai/kimi-k2.5` | 0.375 | **2.025** | ✗ Over $1.5 |
| 11 | `deepseek/deepseek-v4-flash` | 0.090 | **0.180** | ✓ Auto |
| 12 | `z-ai/glm-5.1` | 0.966 | **3.036** | ✗ Over $1.5 |
| 14 | `z-ai/glm-5.2` | 0.909 | **2.856** | ✗ Over $1.5 |
| 15 | `deepseek/deepseek-v4-pro` | 0.435 | **0.870** | ✓ Auto |
| 16 | `moonshotai/kimi-k2.6` | 0.660 | **3.410** | ✗ Over $1.5 |
| 17 | `moonshotai/kimi-k2.7-code` | 0.740 | **3.500** | ✗ Over $1.5 |

Because `pick_models` reads `CODING_SUBAGENT_SELECTION.md` via the `SUBAGENT_SELECTION_DOC` env var and it **overrides the vendored `_TABLE`**, the current doc silently re-admits **at least 8 models over $1.5/Mtok** into auto-selection — every one of them a policy violation.

### 3. `rank_coding_subagents.py` has zero tier-split logic

Grepped the ranker: no `1.5`, no `tier`, no `auto`, no `on-request` filter/flag anywhere. The `SELECT` at `:215-222` includes `quality_tier` but that's the DB row's quality band, not a price-tier separator. So the doc is guaranteed to keep drifting until the ranker itself splits.

### 4. Operator ran the equivalent split on 2026-07-08

Same day the operator sent this message, they explicitly said (paraphrased for the record): *keep adding and benchmarking everything (glm, kimi, grok, qwen, and every future model). The goal is separation, not deletion.* No models get removed — pricier ones stay tracked, they just don't enter Auto.

---

## Recommended shape (proposal, not mandate)

Pick whichever fits the ranker's existing rendering pattern:

### Option A — two sections in the doc

```markdown
## Ranked table

### code — Auto tier (output ≤ $1.5/Mtok — `pick_models` picks freely)

| # | Model | ... | Out $/M | ... |
|---:|---|---|---:|---|
| 1 | `deepseek/deepseek-v4-flash` | ... | 0.180 | ... |
| 2 | `deepseek/deepseek-v3.2` | ... | 0.343 | ... |
| ... (only rows where Out $/M ≤ 1.5) ...

### code — On-request tier (output > $1.5/Mtok — operator opt-in only)

| # | Model | ... | Out $/M | ... |
|---:|---|---|---:|---|
| 1 | `z-ai/glm-5.2` | ... | 2.856 | ... |
| 2 | `moonshotai/kimi-k2.7-code` | ... | 3.500 | ... |
| ... (only rows where Out $/M > 1.5) ...
```

**Pros:** section headers are trivial for `pick_models` to scope by (grep between the two headers). Cheapest structural change.

### Option B — one section, new `Tier` column

Add a `Tier` column with values `auto` / `on-request` computed from `Out $/M ≤ 1.5`:

| # | Model | ... | Out $/M | **Tier** |
|---:|---|---|---:|---|
| 1 | `deepseek/deepseek-v4-flash` | ... | 0.180 | **auto** |
| 2 | `z-ai/glm-5.2` | ... | 2.856 | **on-request** |

**Pros:** single sort, single table, cleaner ordering. `pick_models` filters by column.
**Cons:** requires `pick_models` to know the column. If the module's current parser doesn't parse column values as filters, Option A is easier.

### Coordination with `pick_models`

The fabrik-lib subagents module's `pick_models` (in `/opt/fabrik-lib/subagents/subagents/select.py`) currently reads all rows under `### code`. Whichever option you pick, please coordinate with the fabrik-lib AI so `pick_models` learns the new shape — otherwise the split is invisible to the consumer that most needs it.

---

## What the best-model-suggester side already provides

- `docs/reference/kilo/AI_VENDOR_ACCESS.md` — vendor-reachability catalog (not model-price-tier — that's your ranker's job).
- `docs/reference/kilo/{TTS,STT,TRANSLATION,IMAGE_GEN}_SELECTION.md` — 4 sibling specialty selection docs pattern-cloned from your `rank_coding_subagents.py` layout (they already respect their own `reachable_with_existing_keys=1` filter). Take the pattern; it's yours.
- `docs/reference/kilo/CANDIDATE_SIGNUPS.md` — a related "watch-list" doc for vendors not currently reachable. Similar spirit: kept + priced but flagged as non-default.

If any of the tier-split lift is easier by cloning our template for `CODING_SUBAGENT_SELECTION.md`'s new sections, feel free.

---

## Non-negotiable acceptance criteria

1. `CODING_SUBAGENT_SELECTION.md` after a fresh `rank_coding_subagents.py` run must place every row with `Out $/M > 1.5` in a section (or column value) that `pick_models` will NOT read as auto-selectable.
2. No model is deleted from the doc — On-request rows must still be present, benchmarked, and priced.
3. A new model that clears the $1.5 output threshold auto-joins Auto on next daily refresh.
4. A model whose price crosses the threshold (either direction) moves between tiers automatically, no manual edit.

## Non-goals (for clarity)

- Don't change the underlying score formula.
- Don't change what data is collected — same benchmarks, same columns.
- Don't touch the fabrik-lib module's vendored `_TABLE` — that's their side; they'll follow you.

---

**When done:** please add a dated note at the bottom of this file OR update `CHANGELOG.md` with `### Changed — CODING_SUBAGENT_SELECTION.md now splits Auto vs On-request tiers`, and this handoff can be archived.
