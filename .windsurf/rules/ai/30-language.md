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

## Kilo coverage
✅ 235 models — the broadest category. Many free options; full paid range. Check Kilo before any paid external LLM API for non-operational generation tasks.

**Use cases:** chatbots, content generation, search, translation.

**Anti-pattern:** standing up a dedicated vector DB when pgvector is already on the project's Postgres.
