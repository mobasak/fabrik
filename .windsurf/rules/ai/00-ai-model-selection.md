---
activation: glob
globs: ["**/ai/**", "**/llm/**", "**/models/**", "**/inference/**", "**/agents/**", "**/prompts/**", "project.yaml"]
description: AI model & tool selection INDEX — match the task to one of 16 categories, prefer specialized vendors over general LLMs, pick the cheapest gateway (Kilo CLI and OpenRouter are peers), honor Fabrik AI defaults (pgvector-only, Recraft images, Soniox TTS). Routes to per-category packs 10–90 in this folder.
trigger: glob
---
<!-- CONSUMER: Coding agents choosing an AI provider/model/tool + Traycer (tech-plan step)
     GOAL: Right tool for the task type; specialized over general; cheapest gateway for the model; Fabrik defaults enforced.
     TRAYCER USAGE: Injects as Context File for any AI-feature ticket. The selection workflow shapes the tech-plan.
     AGENT USAGE: Identify category → open the matching pack (10–90) → consult the bake-off browser for cost+quality + cheapest gateway → shortlist → document the choice + rejected alternative in project.yaml. -->

# AI Model & Tool Selection — Index

This folder is the **canonical AI ruleset** (it replaced the former `docs/reference/AI_TAXONOMY.md`, now a redirect stub). This file is the index + the global selection discipline; the per-category packs carry the catalogue and the binding default for each category.

> Last content verification: 2026-06-29 (gateway-agnostic policy: Kilo CLI and OpenRouter are peer gateways; pick by cost+availability per model. Prior text mandated "Kilo CLI before paid external APIs" — superseded because OpenRouter often prices the same model cheaper and many sweet-spot models (e.g. `qwen/qwen-mt-turbo` via DashScope) aren't on Kilo at all.) Last full lineup check: 2026-06-25 (Claude lineup, Soniox TTS, Recraft/FLUX).
>
> Freshness is checked daily (warn-only) by `scripts/check_ai_pack_freshness.py` in the WSL pipeline — it flags this `Last content verification:` stamp when it is >90 days old (see `docs/workflows/KILO_BENCHMARK_WORKFLOW.md`). On review, **re-stamp the date above**: that is what records a human re-verified the model lineup / vendor picks. (Per-pack packs may carry their own stamp; this index's stamp is the headline one.)

## Selection workflow (do this before writing code)

1. **Identify the category** from the 16 below.
2. **Open the matching pack** (`10`–`90`) for its subcategories, tools, and the Fabrik default.
3. **Pick the cheapest gateway for the model.** Kilo CLI (`kilo run kilo/<provider>/<model>`) and OpenRouter (`https://openrouter.ai/api/v1`) are **peer gateways** — the same model is frequently dual-routed. Use the bake-off browser (`scripts/kilo-benchmarks/models_browser.html`, "Source" column shows OR/K/DS badges and a Kilo-vs-OR markup %) to pick the cheaper rate per model. DashScope (`DS` badge — `qwen-mt-turbo` etc.) and SiliconFlow (`SF`) are valid direct-API gateways when the model isn't on Kilo or OR.
4. **Shortlist**, then **document the choice + the top alternative you rejected** in `project.yaml` (`ai_category`, `ai_subcategory`, `ai_tools`).

## The 4 selection rules

- Match task to category first (prevents wrong tool type).
- Prefer specialized vendors in a category over general LLMs (Soniox for TTS over an LLM, DeepL/Qwen-MT-Turbo for translation, Recraft/FLUX for image gen).
- For LLM models that are dual-routed (Kilo + OpenRouter), pick the cheaper gateway — they're peers; neither is privileged.
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
| Embeddings / vector search | **pgvector** on Postgres/Supabase | Dedicated vector DBs (Pinecone/Qdrant/Weaviate/Milvus) are **banned** — latency, data-sync, backup, and cost when pgvector is free on existing Postgres. See `core/65-rag-search.md` + `30-language.md`. |
| Image gen (branded / vector / illustration) | **Recraft v4.1** | Style consistency for branded work. |
| Image gen (photoreal) | **FLUX (BFL)** | Owned `BFL_API_KEY`; Replicate as host/fallback. |
| TTS (multilingual / faithful) | **Soniox TTS** | 60+ langs, hallucination-free, native EN/TR + mid-sentence switching, GDPR. |
| TTS (expressive voices) | **ElevenLabs** | When prosody matters more than faithfulness. |
| LLM (default) | **Claude Opus 4.8** | Current lineup: Opus 4.8 / Sonnet 4.6 / Haiku 4.5 / Fable 5. Sonnet for high-volume, Haiku for speed-critical. |

## Gateway coverage by category

Kilo CLI (`kilo run kilo/<provider>/<model>`) and OpenRouter (`https://openrouter.ai/api/v1/chat/completions`) are **peer gateways**. Either is valid — pick by per-model price (the bake-off browser shows the cheaper rate per row). DashScope and SiliconFlow are direct-API gateways for specialist routes (e.g. `qwen-mt-turbo`).

<!-- GATEWAY_COUNTS:START — last-refreshed: 2026-07-02 (auto-managed by update_gateway_counts.py) -->
*Live gateway counts (active models, 2026-07-02 UTC; auto-refreshed from `kilo_agents.db`):*

| Gateway | Active routable models | Notes |
|---|---|---|
| **OpenRouter** | 340 | of which **338** dual-routed with Kilo, **2** OR-only |
| **Kilo CLI** | 338 | of which **338** dual-routed with OR, **0** Kilo-only |
| **DashScope** (direct) | 1 | specialist routes (e.g. `qwen-mt-turbo`) |
| **SiliconFlow** (direct) | 1 | specialist routes (e.g. Hunyuan) |

Capability counts (any-gateway): reasoning **197** · tools/function-calling **256** · vision-input **168** · translation-scored **9** · STT-capable **21**.
<!-- GATEWAY_COUNTS:END -->

For specialized categories 7–15 (Robotics / Synthetic data / Recommendation / Cybersecurity / Bio-Healthcare / Edge / Governance / Generative design) use domain tools, not gateway LLMs.

**Direct-API gateways (use when the model isn't on Kilo/OR):**

- **DashScope** (`dashscope-intl.aliyuncs.com`) — Qwen-MT-Turbo (dedicated MT), Qwen-VL, etc.
- **SiliconFlow** (`api.siliconflow.com`) — Hunyuan, Qwen3-Embedding, etc.
- **Soniox / Recraft / FLUX (BFL)** — specialized vendors, see per-category packs.

**Kilo capability flags:** `reasoning` (88) · `toolcall` (148) · `input.image` (70) · `input.audio` (9) · `input.video` (19) · `attachment` (70). **Sync:** `python /opt/fabrik/scripts/kilo_model_sync.py --sync`. (Counts/prices drift between syncs — re-verify from the sync, not this table.)

**Bake-off browser** (`scripts/kilo-benchmarks/models_browser.html`) is the source of truth for per-model gateway + price + quality. Tabbed by signal: Overview / Reasoning / Coding / Translation / Audio. The "Source" column badges (OR / K / DS / SF) and the Kilo-vs-OR markup % tell you the cheaper gateway at a glance.

## Anti-patterns

- General LLM for a specialized task (e.g. an LLM for transcription instead of Soniox; an LLM for translation instead of DeepL/Qwen-MT-Turbo when the language is in scope).
- Choosing a tool before identifying the category.
- Picking the more expensive gateway when a model is dual-routed (Kilo and OpenRouter often differ 10–40 % on the same model — read the markup column).
- Treating Kilo and OpenRouter as anything other than peer gateways. Neither is mandated by Fabrik for product code; the historical "Kilo before paid external" rule is superseded as of 2026-06-29.
- Shipping code whose AI behavior contradicts `specs/services/<id>.yaml::shape` (embeddings without `needs_database`, search without `has_search_feature`, `/metrics` without `exposes_metrics`).

## Operational AI paths — auth boundary

Operational stack (sysadmin, watchdog, bootstrap) uses **Claude Code CLI w/ subscription OAuth** — never `ANTHROPIC_API_KEY`. That key exists ONLY for `fabrik ai generate` content utilities. Per-LLM-call cost caps apply to paid APIs via `core/cost-budget.md`; they must not be placed on the operational diagnose loop.
