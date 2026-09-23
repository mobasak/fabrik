---
activation: glob
globs: ["**/ai/**", "**/llm/**", "**/models/**", "**/inference/**", "**/agents/**", "**/prompts/**", "project.yaml"]
description: AI model & tool selection INDEX — Claude on the Max subscription (`claude -p`, selected by alias so it is always the latest model) first; specialized vendors for non-LLM categories; metered gateways only for what Claude cannot serve. Honors Fabrik AI defaults (pgvector-only, Recraft images, Soniox TTS). Routes to per-category packs 10–90 in this folder.
trigger: glob
currency_pass: 2026-09-23
---
<!-- CONSUMER: Coding agents choosing an AI provider/model/tool + Traycer (tech-plan step)
     GOAL: Claude subscription first; right specialized tool for non-LLM work; latest Claude models by alias; Fabrik defaults enforced.
     TRAYCER USAGE: Injects as Context File for any AI-feature ticket. The selection workflow shapes the tech-plan.
     AGENT USAGE: Can Claude do it? → `claude -p` by alias. Otherwise identify category → open the matching pack (10–90) → shortlist → document the choice + rejected alternative in project.yaml. -->

# AI Model & Tool Selection — Index

This folder is the **canonical AI ruleset** (it replaced the former `docs/reference/AI_TAXONOMY.md`, which has been removed). This file is the index + the global selection discipline; the per-category packs carry the catalogue and the binding default for each category.

> Last content verification: 2026-09-23 (Claude-subscription-first policy; the Kilo gateway is retired; the metered subagent pool is paused).
>
> Freshness is checked daily (warn-only) by `scripts/check_ai_pack_freshness.py` in the WSL pipeline — it flags this `Last content verification:` stamp when it is >90 days old (see `docs/workflows/KILO_BENCHMARK_WORKFLOW.md`). On review, **re-stamp the date above**: that is what records a human re-verified the model lineup / vendor picks. (Per-pack packs may carry their own stamp; this index's stamp is the headline one.)

## Claude subscription first (BINDING)

**If Claude can do the task — text, code, reasoning, classification, extraction, structured output, image understanding — run it through `claude -p` on the Claude Max subscription.** Per token it costs less than nearly every metered model: the hub's cost sidecar (`/opt/fabrik/scripts/kilo-benchmarks/claude_p_cost.json`, `amortized_per_mtok` over a rolling 30-day window, rebuilt by `/opt/fabrik/scripts/claude_p_cost.py --refresh` — both hub-only) puts the subscription's amortized rate below every priced route but free tiers and a micro-model or two, and far below Anthropic's own API list prices. Metered APIs are for what Claude cannot serve (rung 4 of § In-code AI agent calls — the dispatch ladder) and for the specialized non-LLM categories below.

**Always the latest Claude models — select by ALIAS, never by an old ID.** Claude Code's aliases resolve to the newest model of each family and move with every release, so code that says `--model opus` never goes stale:

| Alias | Use it for | Resolves to today (pin this ID only when reproducibility beats currency) |
|---|---|---|
| `haiku` | speed-critical, high-volume, simple extraction — rung 1 of in-code dispatch | `<!--v:claude_haiku_id-->claude-haiku-4-5-20251001<!--/v-->` |
| `sonnet` | daily coding; the next rung when `haiku` measurably falls short | `<!--v:claude_sonnet_id-->claude-sonnet-5<!--/v-->` |
| `opus` | complex reasoning and long agentic work; the CLI's account default when no model is set | `<!--v:claude_opus_id-->claude-opus-5-5<!--/v-->` |
| `fable` | the hardest and longest-running tasks, when `opus` measurably falls short | `<!--v:claude_fable_id-->claude-fable-5-1<!--/v-->` |

A pinned ID in code or config is a stale model waiting to happen: when reproducibility genuinely matters, take the ID from the table above (its values are machine-owned in `.windsurf/rules/versions.yaml`) and record why the pin beats the alias. Fable is never an account default — it is always selected explicitly. `best` resolves to Fable where it is available, else Opus. **Where a category pack (`10`–`90`) or a sibling pack still names a Claude model by version, or routes an LLM step to a metered gateway only, THIS section wins** — select Claude by alias; those packs are corrected on their own turns.

## Selection workflow (do this before writing code)

> **Before recommending any NON-Claude model for the operator to actually run:** read the applicable `docs/reference/kilo/*_SELECTION.md` and consult `docs/reference/kilo/AI_VENDOR_ACCESS.md`. If the model you want to recommend is not in the accessible set, either flag it clearly ("**new vendor — needs signup + payment method**") or pick a peer from the accessible set. When in doubt, run `python /opt/ai-model-catalog/engine/suggest_model.py --task <task> --volume-<unit> <N>` — it hard-fails with exit=1 if no data exists for that task class, so you can't extrapolate from thin air.

## Selection MDs — read before recommending a non-Claude model

Every recommendation the operator will actually run should be grounded in the corresponding auto-generated selection doc + the vendor-access catalog. All of them live in `docs/reference/kilo/` and are governance-synced to every project. The two subagent-selection docs rank models for the metered subagent pool, which is PAUSED (D-181/D-343) — read them only when choosing a metered fallback.

| Task class | Selection MD | Regenerated by |
|---|---|---|
| Coding LLMs (agents/subagents — pool paused) | `docs/reference/kilo/CODING_SUBAGENT_SELECTION.md` | `rank_coding_subagents.py` (ai-model-catalog engine) |
| Empirical per-task_type ranking (spec / plan / code / review / docs / research — pool paused) | `docs/reference/kilo/TASK_SUBAGENT_SELECTION.md` | `rank_task_subagents.py` — FROZEN while the pool is paused (`daily_refresh.sh` skips it; the doc's own `Evidence age:` line says how old) |
| TTS | `docs/reference/kilo/TTS_SELECTION.md` | `rank_tts.py` (daily) |
| STT | `docs/reference/kilo/STT_SELECTION.md` | `rank_stt.py` (daily) |
| Translation | `docs/reference/kilo/TRANSLATION_SELECTION.md` | `rank_translation.py` (daily) |
| Image generation | `docs/reference/kilo/IMAGE_GEN_SELECTION.md` | `rank_image_gen.py` (daily) |

**Vendor access:** `docs/reference/kilo/AI_VENDOR_ACCESS.md` is the single source of truth for which vendors the operator can call today. Rows with Status ✅ or ⚠️ are accessible (⚠️ = accessible but low balance — pick a ✅ peer if one is on the Pareto frontier).

**Reachability filter — SUSPENDED with the pool (D-181/D-182, 2026-09-07): the pool is OFF by ruling, do not call `pick_models`; the recipe is kept for re-enable.**
<!-- POOL OFF (D-181):
**Reachability filter (2026-07-09 canonical alignment):** to avoid dispatching to a vendor the operator can't reach with existing keys, call `pick_models` with the canonical `exclude=` seam:

```python
import sqlite3
from libs.subagents import pick_models

# Build the unreachable set from the seed catalog (agents.reachable_with_existing_keys=0):
con = sqlite3.connect("scripts/kilo-benchmarks/kilo_agents.db")
unreachable = tuple(
    r[0] for r in con.execute(
        "SELECT id FROM agents WHERE status='active' AND blocked=0 "
        "AND reachable_with_existing_keys=0"
    )
)
picks = pick_models("review", n=3, exclude=unreachable)
```

`exclude=` is the documented "reliability lever" in canonical `subagents`; the pre-filter is a plan-1 project-local mechanism (was a module fork — reverted). No env var, no kwarg toggle, no HTML-comment doc parsing — just pass the set at the call site.

> **Freshness caveat:** `agents.reachable_with_existing_keys` is populated by `/opt/ai-model-catalog/engine/seed_specialty_catalog.py` (which parses `AI_VENDOR_ACCESS.md`). The seeder is NOT wired into `daily_refresh.sh`'s cron — it runs on-demand when the operator edits `AI_VENDOR_ACCESS.md`. If a vendor was recently added/removed, run `python /opt/ai-model-catalog/engine/seed_specialty_catalog.py` before relying on the `unreachable` set. The DB filter at `rank_coding_subagents.py:269` reads the same column, so a stale seed also stales the ranked doc.
-->

1. **Can Claude do it?** Then it is `claude -p` by alias (§ Claude subscription first) — in-code single calls through the dispatch ladder below (starting at `haiku`), interactive and agentic work on `opus` (`fable` when `opus` measurably falls short) — stop here.
2. **Otherwise identify the category** from the 16 below, and **open the matching pack** (`10`–`90`) for its subcategories, tools, and the Fabrik default.
3. **Pick the cheapest route for a non-Claude model.** OpenRouter (`https://openrouter.ai/api/v1`) is the metered gateway; DashScope (`DS` badge — `qwen-mt-turbo` etc.) and SiliconFlow (`SF`) are valid direct-API gateways when the model isn't on OpenRouter. The bake-off browser (`/opt/fabrik/scripts/kilo-benchmarks/models_browser.html`, hub-only, "Source" column) shows the rate per route.
4. **Shortlist**, then **document the choice + the top alternative you rejected** in `project.yaml` (`ai_category`, `ai_subcategory`, `ai_tools`).

## The 4 selection rules

- Match task to category first (prevents wrong tool type).
- Claude on the subscription before any metered LLM; select it by alias so it is the latest model.
- Prefer specialized vendors in a non-LLM category over general LLMs (Soniox for TTS over an LLM, Recraft/FLUX for image gen). Translation is text, so it is `claude -p` first; Qwen-MT-Turbo or DeepL only when a bake-off shows Claude misses the quality or cost bar for that language pair.
- Document the alternative considered + why not chosen.

## The 16 categories → packs

| # | Category | Pack |
|---|----------|------|
| 1 | Speech & Audio | `10-speech-audio.md` |
| 2 | Vision | `20-vision.md` |
| 2b | 3D asset generation (zero-edit pipeline) | `25-3d-generation.md` |
| 3 | Language | `30-language.md` |
| 4 | Vision-Language & Multimodal | `40-multimodal.md` |
| 5 | Agentic / Reasoning | `50-agentic.md` |
| 6 | Code & Developer | `60-code.md` |
| 7 | Data & Predictive | `70-data-predictive.md` |
| 8–15 | Robotics, Synthetic Data, Recommendation, Cybersecurity, Bio/Healthcare, Edge, Governance, Generative Design | `80-specialized-domains.md` |
| 16 | Long-Context | `90-long-context.md` |

## Fabrik defaults — do not deviate without a documented reason

| Need | Default | Notes |
|------|---------|-------|
| Embeddings / vector search | **pgvector** on `postgres-main` (Supabase is retired as a runtime target) | Dedicated vector DBs (Pinecone/Qdrant/Weaviate/Milvus) are **banned** — latency, data-sync, backup, and cost when pgvector is free on existing Postgres. See `core/65-rag-search.md` + `30-language.md`. |
| Image gen (branded / vector / illustration) | **Recraft** (its current model) | Style consistency for branded work. |
| Image gen (photoreal) | **FLUX (BFL)** | Owned `BFL_API_KEY`; Replicate as host/fallback. |
| TTS (multilingual / faithful) | **Soniox TTS** | 60+ langs, hallucination-free, native EN/TR + mid-sentence switching, GDPR. |
| TTS (expressive voices) | **ElevenLabs** | When prosody matters more than faithfulness. |
| LLM (default) | **Claude via `claude -p` on the subscription, by alias** | In-code dispatch starts at `haiku` and escalates `sonnet` → `opus` → `fable` on measured failure (§ dispatch ladder); interactive and agentic work defaults to `opus` — see § Claude subscription first. |

## Candidate signup vendors (watch-list — not currently active)

Vendors that would beat the accessible set on cost or speed for NON-Claude work, but need signup + payment method before we can call them. Two docs for two questions:

- **Per-model watch-list** (generated by the ai-model-catalog engine's `rank_candidate_signups.py`) — `docs/reference/kilo/CANDIDATE_SIGNUPS.md`. Union-selects `reachable_with_existing_keys=0` rows from `agents` + `gpu_providers`, ranked by seeded price + `signup_trigger`. That column is seeded on demand by `/opt/ai-model-catalog/engine/seed_specialty_catalog.py` (not by the daily cron) — run it after editing `AI_VENDOR_ACCESS.md`, or the watch-list is stale.
- **Aggregator-tier roadmap** (hand-authored, ranked by capability × ease × effort) — `docs/reference/kilo/AGGREGATOR_ROADMAP.md`. 5-tier list of gateways / meta-gateways / direct vendors worth signing up for (Groq, Cerebras, DeepInfra direct, Cloudflare Workers AI, xAI, Mistral, Cohere, etc.). Also contains the wiring pattern reference (SiliconFlow 2026-07-09 as the canonical 5-step recipe).

| Vendor | Category | Why signup | Blocker |
|---|---|---|---|
| Hyperbolic | LLM inference (open Llama-class models) + GPU (H100) | ~30% cheaper open-model inference vs OpenRouter; cheaper H100 than vast/runpod on-demand | new account + payment method |
| Together | LLM inference (open Llama-class models) | Direct-vendor throughput often beats OpenRouter routing | new account + payment method |
| Cerebras | LLM inference (open Llama-class models) | LPU is the fastest tier for open models | new account + payment method |
| Novita | LLM inference + GPU (H100) | Cheapest observed for open models (est.); mid-market H100 | new account + payment method |
| DeepL | Translation | Free tier up to 500K chars/mo | new account (Free tier is enough for dev) |

When the ranker (`suggest_model.py`) sees a locked-out row Pareto-beating the accessible frontier by ≥30% for equivalent quality, it emits a `💡 Consider signup: <vendor>` hint on stderr — that's when the watch-list is worth acting on.

## Gateway coverage by category

For a non-Claude model, OpenRouter (`https://openrouter.ai/api/v1/chat/completions`) is the metered gateway, and DashScope, SiliconFlow, and ModelScope are direct-API gateways for specialist routes (e.g. `qwen-mt-turbo`, Hunyuan, Zhipu GLM direct). **The Kilo gateway is retired** (operator, 2026-07-19): its key is still provisioned — the pool is off by POLICY, not by credential (D-182 restored the keys) — but a Kilo route is not an option for new work, even though the counts below still inventory it.

<!-- GATEWAY_COUNTS:START — last-refreshed: 2026-09-07 (auto-managed by update_gateway_counts.py) -->
*Live gateway counts (active models, 2026-09-07 UTC; auto-refreshed from `kilo_agents.db`):*

| Gateway | Active routable models | Notes |
|---|---|---|
| **OpenRouter** | 386 | of which **350** dual-routed with Kilo, **36** OR-only |
| **Kilo CLI** | 350 | of which **350** dual-routed with OR, **0** Kilo-only |
| **DashScope** (direct) | 1 | specialist routes (e.g. `qwen-mt-turbo`) |
| **SiliconFlow** (direct) | 41 | specialist routes (e.g. Hunyuan) |
| **ModelScope** (direct) | 32 | Zhipu GLM direct (4) + Tencent Hunyuan Hy3 (1) + 27 Qwen/DeepSeek/MiniMax/Kimi/stepfun/moonshotai/nex-agi active overlap |

Capability counts (any-gateway): reasoning **254** · tools/function-calling **348** · vision-input **235** · translation-scored **9** · STT-capable **36**.
<!-- GATEWAY_COUNTS:END -->

For specialized categories 7–15 (Robotics / Synthetic data / Recommendation / Cybersecurity / Bio-Healthcare / Edge / Governance / Generative design) use domain tools, not gateway LLMs.

**Direct-API gateways (use when the model isn't on OpenRouter):**

- **DashScope** (`dashscope-intl.aliyuncs.com`) — Qwen-MT-Turbo (dedicated MT), Qwen-VL, etc.
- **SiliconFlow** (`api.siliconflow.com`) — Hunyuan, Qwen3-Embedding, etc.
- **ModelScope** (`api-inference.modelscope.cn`) — Zhipu GLM direct, Tencent Hunyuan, plus a Qwen/DeepSeek/MiniMax/Kimi/stepfun/moonshotai/nex-agi active overlap (the counts block above carries the live numbers).
- **Soniox / Recraft / FLUX (BFL)** — specialized vendors, see per-category packs.

**Bake-off browser** (`/opt/fabrik/scripts/kilo-benchmarks/models_browser.html`, hub-only) is the source of truth for per-model gateway + price + quality for non-Claude models. Tabbed by signal: Overview / Reasoning / Coding / Translation / Audio. The "Source" column badges (OR / K / DS / SF / MS) tell you the route at a glance; a `K`-only route is retired.

## Anti-patterns

- Paying a metered API for a task the Claude subscription can do.
- Pinning an old Claude model ID (or copying one from an old doc) instead of selecting by alias.
- General LLM for a specialized non-LLM task (e.g. an LLM for transcription instead of Soniox).
- Choosing a tool before identifying the category.
- Routing new work through the retired Kilo gateway.
- Shipping code whose AI behavior contradicts `specs/services/<id>.yaml::shape` (embeddings without `needs_database`, search without `has_search_feature`, `/metrics` without `exposes_metrics`).

## Operational AI paths — auth boundary

Operational stack (sysadmin, watchdog, bootstrap) uses **Claude Code CLI w/ subscription OAuth** — never `ANTHROPIC_API_KEY`. No fabrik code path reads that key (the `fabrik ai generate` utilities were removed 2026-06-16); a project that needs a metered LLM goes through OpenRouter. Per-LLM-call cost caps apply to paid APIs via `core/cost-budget.md`; they must not be placed on the operational diagnose loop.

## In-code AI agent calls — the dispatch ladder (BINDING)

When project/pipeline code needs an **AI step wired into the code** (mechanical code can't do the job —
transcript classification, fix dispatch, content triage), select the model by this ladder.

**First choice — vendor the `fabrik-lib/llm-dispatch` module, don't hand-roll.** Implement this ladder by
vendoring **`llm-dispatch`** (vendor-don't-build, CLAUDE.md § Pointers) rather than a bespoke `claude -p`
subprocess per project — it IS this ladder as a generic client (`complete()`/`complete_json()`/
`get_last_usage()`): **claude -p subscription primary** (`--output-format json`, whose envelope carries
`total_cost_usd`, `usage` (main loop only) and a per-model `modelUsage` — client-side estimates, not a bill;
`llm-dispatch` hands `usage` and `cost_usd` to `budget_record`, while `get_last_usage()` returns `usage` plus the
model label only; for per-model `modelUsage`, call `dispatch()` and read `result.raw["modelUsage"]`) with an **OpenRouter HTTP fallback**; env-driven `LLMConfig`; **INJECT** your vendored
`cost-budget` via the `budget_check`/`budget_record` hooks; `complete()`/`complete_json()` return empty instead of raising when a CALL fails (building the config from the environment can still raise `ValueError` on a malformed numeric var). The module's own default model
(`CLAUDE_CLI_MODEL`) is `opus` — set `haiku` for rung 1 below. ⚠️ `complete(model=…)` sets the OpenRouter model
only; the `claude -p` leg always runs `CLAUDE_CLI_MODEL`, so choose the rung with a per-rung config —
`complete(prompt, config=dataclasses.replace(LLMConfig.from_env(), claude_model="sonnet"))` (a bare
`LLMConfig(...)` skips the environment: no OpenRouter key, default effort) — or `dispatch(ClaudeCall(prompt,
model="sonnet"))`, which RAISES (`DispatchError`, or `ValueError` for an invalid `ClaudeCall`) and has no OpenRouter leg, so catch both yourself. The CLI leg runs at
`CLAUDE_CLI_EFFORT=low` by default — raise it before judging that a rung measurably fell short.
**Infra prerequisite:** a *deployed* service that shells to
`claude -p` MUST declare **`shape.uses_claude_cli: true`** (+ `claude_cli_home`) so the deployer mounts the
host's **rotated** `~/.claude` read-only into the container — auth follows the fleet account rotation;
**never** bake a static `CLAUDE_CODE_OAUTH_TOKEN` (it pins one account and dies at its weekly quota). Then
select the rung — always by alias, so each rung is the latest model of its family:

1. **`claude -p --model haiku`** — the default first rung (subscription; the 1× quota tier in
   `claude_p_cost.json::per_model_spend.tiers`).
2. **`claude -p --model sonnet`, then `--model opus`** — each only when the previous rung is measurably not
   enough (task fails its quality gate / errors — a measured escalation, never a vibes one).
3. **`claude -p --model fable`** — only when opus is measurably not enough.
4. **Fallback: OpenRouter** — for a call Claude can't serve (capability/latency mismatch, or the call must
   be metered-isolated from the subscription). ⚠️ `complete()`/`complete_json()` take this leg whenever the
   `claude -p` leg yields no text — binary missing, auth failure, timeout, error, quota, an empty result, and
   also when YOUR `budget_check` refuses `claude-cli` (and `budget_check` fails OPEN if it raises);
   `dispatch()` and the session/agentic calls never fall back, and `complete_structured()` only through a `fallback=` you inject. The key is
   `KILO_API_KEY` before `OPENROUTER_API_KEY`, and `KILO_API_URL` overrides the endpoint — wherever the
   fleet's keys sit in the environment (the hub's, per D-182) they win. So unset both `KILO_*` vars and set
   the project's OWN `OPENROUTER_API_KEY`, guard the leg with `budget_check`, and alert on the dispatcher's
   no-content fallback — or run with no key at all when the call must never go metered. Set `LLM_DEFAULT_MODEL` to the bake-off
   winner (the module's built-in default is a placeholder id, not evidence). The model is chosen by
   **tested evidence, never assumption**: consult the selection MDs / `suggest_model.py`, or run a
   scored bake-off — lowest cost that meets the required capability; record the result in the
   project's decision ledger.

Boundaries: `claude -p` is the subscription CLI — the sanctioned Claude path (see auth boundary
above; never `ANTHROPIC_API_KEY`, never a vendor SDK — `core/57-external-data-sourcing.md` hard constraint). Every rung wraps
in the `58-resilience` contract, and any unattended paid-LLM loop still carries watchdog +
cost-budget. This ladder governs **in-code single-call/worker dispatch**; gradeable parallel fan-out
(review finders, graders, doc reconcilers) runs NATIVE while the pool is OFF (D-181) per `core/62-using-subagents.md`.
