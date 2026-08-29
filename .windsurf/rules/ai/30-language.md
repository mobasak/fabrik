---
activation: glob
globs: ["**/llm/**", "**/nlp/**", "**/text/**", "**/translation/**", "**/summariz/**", "**/embeddings/**", "**/embedding/**"]
description: Language AI (category 3) — LLMs (Claude Opus 4.8 default; Sonnet 4.6 high-volume; Haiku 4.5 speed), embeddings/search (pgvector ONLY — dedicated vector DBs banned), translation (DeepL), summarization. Kilo: 235 language models.
trigger: glob
---
<!-- CONSUMER: Coding agents building text/LLM/embedding features + Traycer (tech-plan)
     GOAL: Claude as default LLM; pgvector is the ONLY vector store; DeepL for translation.
     TRAYCER USAGE: Context File for language/NLP/embedding tickets.
     AGENT USAGE: LLM → Claude (Opus 4.8 default). Embeddings → pgvector on Postgres/Supabase. See core/65-rag-search.md + core/66-rag-chunking.md for retrieval discipline. -->

# 3. Language AI

Last content verification: 2026-08-18

**Purpose:** Process and generate text.

## Fabrik defaults
- **LLM → Claude Opus 4.8** (current lineup: Opus 4.8 / Sonnet 4.6 / Haiku 4.5 / Fable 5). Sonnet for high-volume production, Haiku for speed-critical.
- **Embeddings & vector search → pgvector** on PostgreSQL or Supabase. **Dedicated vector DBs (Pinecone / Qdrant / Weaviate / Milvus) are BANNED** — they add network latency, duplicate data sync, complicate backups, and cost money when pgvector is free on your existing Postgres.
- **Translation → DeepL.**

## Subcategories
- **Large Language Models:** Claude (Opus 4.8 default), ChatGPT, Gemini, Grok, Mistral
- **Embeddings & Search:** pgvector (Fabrik default), Cohere, OpenAI Embeddings
- **Translation:** DeepL, Google Translate, NLLB (Meta)
- **Summarization/Extraction:** Claude, GPT-4, Cohere Summarize

## Gateway coverage

Pick the **cheaper gateway per model** — the bake-off browser shows the per-row markup. For translation specifically, prefer a dedicated MT model (DeepL, or `qwen-mt-turbo` via DashScope) over an LLM when the language is in scope.

<!-- GATEWAY_COUNTS:START — last-refreshed: 2026-08-18 (auto-managed by update_gateway_counts.py) -->
*Live gateway counts (active models, 2026-08-18 UTC; auto-refreshed from `kilo_agents.db`):*

language-tagged (any gateway): **0**
translation-scored (any gateway): **9**

Sweet-spot dedicated MT: `qwen-mt-turbo` via DashScope (top-3 on FR/PT/DE/ID/AR, weaker on HU/RO/UR/KO; see the Translation tab in the bake-off browser).
<!-- GATEWAY_COUNTS:END -->

**Use cases:** chatbots, content generation, search, translation.

**Anti-pattern:** standing up a dedicated vector DB when pgvector is already on the project's Postgres.

<!-- OPENROUTER_ROUTES:START — last-refreshed: 2026-08-18 (auto-managed by category_export_markdown.py) -->
*Auto-generated 2026-08-18 (UTC) by `category_route_mapper.py` → injected here by `category_export_markdown.py`. Edits between the markers will be overwritten on the next daily run.*

*No eligible models today — floors too strict or catalog too thin. See `cache/update.log` for details. Reason: No model satisfies category='language' floors: min_quality_tier=2, min_context_window_k=32, require_vision=False, require_tools=False, require_reasoning=False, allow_free=True, stability_required=False, sort_key='input_cost_per_m ASC'*
<!-- OPENROUTER_ROUTES:END -->
