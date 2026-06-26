---
activation: glob
globs: ["**/ai/**", "**/llm/**", "**/models/**", "**/inference/**", "**/agents/**", "**/prompts/**", "project.yaml"]
description: AI model & tool selection INDEX — match the task to one of 16 categories, prefer specialized tools over general LLMs, check Kilo CLI before paid external APIs, honor Fabrik AI defaults (pgvector-only, Recraft images, Soniox TTS). Routes to per-category packs 10–90 in this folder.
trigger: glob
---
<!-- CONSUMER: Coding agents choosing an AI provider/model/tool + Traycer (tech-plan step)
     GOAL: Right tool for the task type; specialized over general; free Kilo over paid external; Fabrik defaults enforced.
     TRAYCER USAGE: Injects as Context File for any AI-feature ticket. The selection workflow shapes the tech-plan.
     AGENT USAGE: Identify category → open the matching pack (10–90) → check Kilo → shortlist → document the choice + rejected alternative in project.yaml. -->

# AI Model & Tool Selection — Index

This folder is the **canonical AI ruleset** (it replaced the former `docs/reference/AI_TAXONOMY.md`, now a redirect stub). This file is the index + the global selection discipline; the per-category packs carry the catalogue and the binding default for each category.

> Last content verification: 2026-06-25 (Claude lineup, Soniox TTS, Recraft/FLUX re-checked). Other vendor/version names are indicative — verify version + price before committing in a project.
>
> Freshness is checked daily (warn-only) by `scripts/check_ai_pack_freshness.py` in the WSL pipeline — it flags this `Last content verification:` stamp when it is >90 days old (see `docs/workflows/KILO_BENCHMARK_WORKFLOW.md`). On review, **re-stamp the date above**: that is what records a human re-verified the model lineup / vendor picks. (Per-pack packs may carry their own stamp; this index's stamp is the headline one.)

## Selection workflow (do this before writing code)

1. **Identify the category** from the 16 below.
2. **Open the matching pack** (`10`–`90`) for its subcategories, tools, and the Fabrik default.
3. **Check Kilo CLI alternatives** (`kilo run kilo/<provider>/<model>`) — categories 1–6 are well covered; don't reach for a paid external API when a free/cheap Kilo model fits.
4. **Shortlist**, then **document the choice + the top alternative you rejected** in `project.yaml` (`ai_category`, `ai_subcategory`, `ai_tools`).

## The 4 selection rules

- Match task to category first (prevents wrong tool type).
- Prefer specialized tools in a category over general ones.
- Check Kilo CLI alternatives before external APIs.
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

## Kilo CLI alternatives by category

Models via `kilo run kilo/<provider>/<model>`:

| Category | Kilo Coverage | Free Options | Paid Options |
|----------|---------------|--------------|--------------|
| 1. Speech/Audio | ⚠️ 9 models | — | `google/gemini-2.0-flash-lite` $0.07/1M |
| 2. Vision | ✅ 70 models | `giga-potato` | `google/gemma-3-27b-it` $0.03/1M |
| 3. Language | ✅ 235 models | Many | Full range |
| 4. Multimodal | ✅ 70 models | `qwen/qwen3-vl-235b-thinking` | `bytedance-seed/seed-1.6-flash` $0.07/1M |
| 5. Agentic | ✅ 88 models | `giga-potato-thinking` | `nvidia/nemotron-nano-9b` $0.04/1M |
| 6. Code | ✅ 148 models | `minimax/minimax-m2.5:free` | Full range |
| 7–15 | ❌ Specialized | Use domain tools | DataRobot, AlphaFold, etc. |

**Kilo capability flags:** `reasoning` (88) · `toolcall` (148) · `input.image` (70) · `input.audio` (9) · `input.video` (19) · `attachment` (70). **Sync:** `python /opt/fabrik/scripts/kilo_model_sync.py --sync`. (Counts/prices drift between syncs — re-verify from the sync, not this table.)

## Anti-patterns

- General LLM for a specialized task (e.g. an LLM for transcription instead of Soniox; an LLM for translation instead of DeepL/Soniox).
- Choosing a tool before identifying the category.
- Reaching for a paid external API when a free Kilo alternative exists.
- Shipping code whose AI behavior contradicts `specs/services/<id>.yaml::shape` (embeddings without `needs_database`, search without `has_search_feature`, `/metrics` without `exposes_metrics`).

## Operational AI paths — auth boundary

Operational stack (sysadmin, watchdog, bootstrap) uses **Claude Code CLI w/ subscription OAuth** — never `ANTHROPIC_API_KEY`. That key exists ONLY for `fabrik ai generate` content utilities. Per-LLM-call cost caps apply to paid APIs via `core/cost-budget.md`; they must not be placed on the operational diagnose loop.
