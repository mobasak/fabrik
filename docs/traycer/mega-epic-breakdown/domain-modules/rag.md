<!-- RAG Domain Module — loaded by mega-epic-breakdown commands
     when Vision Summary Technology Decisions includes a RAG pipeline:
       • 02-epic-decomposition-command — drives RAG-pipeline epic patterns
         (search phase → classification phase → generation phase).
       • 00-trigger-workflow-command Step E4 (EXISTING mode) — drives delta
         decisions when adding search/RAG to an existing project.
     Not scaffold-specific — any project type can need RAG; loaded by the
     `RAG pipeline` field of Technology Decisions rather than a scaffold type.
     Traycer reads this file from disk based on the Vision Summary's
     Technology Decisions — no manual paste needed.
     Consumer: Traycer planning LLM (NOT coding agents).
     Coding agents use .windsurf/rules/core/65-rag-search.md + 66-rag-chunking.md instead. -->

# RAG Domain Module

## What RAG Is

Retrieval-Augmented Generation. Your product has a corpus of text (comments, documents, articles, support tickets). Users need to find, filter, and extract intelligence from it. RAG is the system that makes this possible.

Without RAG: users stare at a list or use ctrl+F.
With RAG: users ask questions in natural language, filter by structured attributes, and get AI-generated answers grounded in their actual data.

## Is RAG Even the Right Tool? (decide before Phase 1)

Not every "search over text" use case is RAG. Per `core/65-rag-search.md` § Choosing:

| User need | Route | Why |
| --- | --- | --- |
| Instant keyword search, typo tolerance, autocomplete, faceted filtering (product catalog, doc site, support tickets) | **MeiliSearch** (registrar via `shape.has_search_feature: true`) | Ships in days. No embedding pipeline, no LLM costs. Typo-tolerance is the deciding factor. |
| Semantic similarity, "find similar", recommendations | **pgvector** | Dense vectors. No keyword side. |
| Knowledge-base / Q&A retrieval needing **keyword + meaning fused** | **pgvector hybrid** (this module) | What this domain module decomposes. |

**Planning consequence:** if the Vision Summary's search use case is pure catalog / doc-site / faceted filtering, do NOT decompose into RAG epics — emit a single MeiliSearch-integration epic instead and `shape.has_search_feature: true` in the spec. Only continue into Phase 1 below when the keyword match feeds an LLM or semantic pipeline.

## The 6 Components (library analogy)

Think of building a library:

### 1. Embeddings — Index cards

Each chunk of text becomes a list of 1024 numbers (a vector). Texts with similar meaning get similar vectors. "I love this retinol cream" and "vitamin A derivative works great" end up near each other, even though they share no words.

**Without this:** search is keyword-only. "retinol cream" won't find "vitamin A derivative."

**Cost:** ~$0.01 per million tokens. Cheapest component. Run once per chunk, store forever.

### 2. Retriever — The librarian finding books

User asks a question → question becomes a vector → PostgreSQL finds the closest chunks via cosine similarity + keyword matching + rank fusion.

**This is NOT an AI model.** It's pure SQL running in PostgreSQL (pgvector + tsvector + RRF). Zero API calls. Sub-100ms latency.

**Without this:** vectors sit in a database doing nothing. This is what makes them useful.

### 3. Classifier (optional) — Stickers on each book

An LLM reads each chunk and tags it: intent (buying, complaint, question), sentiment (positive, negative), entities (brands, ingredients, people). Now users can filter: "show me BUYING INTENT comments about RETINOL with NEGATIVE sentiment."

**Without this:** you can search by meaning but can't filter by intent, sentiment, or entity. You have a search engine, not an intelligence platform.

**Cost:** ~$0.02-0.15 per million tokens depending on model (benchmark before selecting). Run once per chunk. This is what separates a $5/mo search tool from a $500/mo vertical SaaS.

### 4. Answer Generator (optional) — The librarian writing a summary

Retriever finds 10 relevant chunks. An LLM reads them and writes a human answer: "Based on 10 comments across 4 videos, users report retinol is effective for acne scarring but causes irritation in the first 2 weeks."

**Without this:** users see 10 raw text chunks and read them themselves. Still useful, but not a differentiator.

**Cost:** per-query (not per-chunk). ~$0.02-0.15 per answer depending on model.

### 5. Summarizer (optional) — The librarian writing a report

Takes 100+ chunks about a topic and condenses into a paragraph for a dashboard card or PDF report. "Retinol sentiment: 72% positive, 18% negative (irritation), 10% neutral."

**Without this:** dashboards show counts and lists, not narrative insights.

### 6. Re-ranker (optional, rarely needed) — Double-checking the librarian

After retrieval, a cross-encoder re-reads each result and re-orders by actual relevance. Gets retrieval from 90-95% accuracy to 97%.

**Without this:** retriever results are already good. Most projects never need this.

## Decision Matrix — Which Components Does Your Product Need?

| Your product does... | You need... | Phase |
| --- | --- | --- |
| Full-text search over a corpus (docs, comments, articles) | Embeddings + Retriever | 1 |
| Structured filtering (by intent, sentiment, entity, category) | + Classifier | 2 |
| Natural-language Q&A ("what do people say about X?") | + Answer Generator | 3 |
| Dashboard insights, PDF reports, executive summaries | + Summarizer | 3 |
| Mission-critical precision (legal, medical, compliance) | + Re-ranker | 3+ |

**Start at Phase 1. Add phases when the product demands them.** Each phase is an independent epic — no need to plan all at once.

## Phase Progression

| Phase | What ships | User sees | AI cost |
| --- | --- | --- | --- |
| **Phase 1: Search** | Embeddings + Retriever + Chunking | Semantic search bar. "Find comments about X." | One-time: ~$0.01/M tokens for embedding |
| **Phase 2: Intelligence** | + Classifier | Structured filters. "Show buying intent for retinol, negative sentiment." | One-time: ~$0.02-0.15/M tokens for classification |
| **Phase 3: Generation** | + Answer Generator + Summarizer | AI-written answers, dashboard insights, reports | Per-query: ~$0.02-0.15 per answer |
| **Phase 3+: Precision** | + Re-ranker | Better top-10 results for complex queries | Per-query: adds ~50ms latency |

## Epic Patterns for Decomposition

When `02-epic-decomposition-command` encounters a RAG pipeline in the Vision Summary:

### Phase 1 Epic: "Search Pipeline"

- Chunking pipeline (per `core/66-rag-chunking.md` — 300-800 token target, 10-20% overlap, heading-aware)
- Embedding pipeline (per `core/65-rag-search.md` § Embedding Models) — default `qwen/qwen3-embedding-8b`, 1024 dimensions, ONE model used for both ingest and query
- **Hybrid retriever** (pgvector + tsvector + RRF). Pure vector search is **banned for user-facing queries** — dense alone fails on error codes, UUIDs, SKUs, acronyms.
- Search API endpoint
- Search UI (if applicable)
- **Spec contract:** `shape.has_search_feature: true` in `specs/services/<id>.yaml` so the registrar provisions HNSW + extensions on `fabrik apply`
- **Depends on:** backend/database epic (needs tables, schema)
- **Delivers:** working semantic search

### Phase 2 Epic: "Classification Pipeline" (if needed)

- Classifier model selection (benchmark 2-3 candidates against a 50-100 sample golden set per `core/65-rag-search.md` § Model Selection Rules — multilingual TR+EN samples mandatory)
- Classification pipeline (batch processor via `core/75-workers-jobs.md`)
- Structured filter API endpoints
- Filter UI (if applicable)
- **Depends on:** Phase 1 (needs chunks in database)
- **Delivers:** structured filtering on top of search

### Phase 3 Epic: "RAG Intelligence" (if needed)

- Answer generator (prompt + retrieval integration). Token budget capped at **85% of the per-model context window** (`core/65-rag-search.md` § Token Budgeting) — never hardcode `128_000`; look up per-model.
- **Citations are mandatory.** Every chunk's `chunk_id` + heading breadcrumb is in its metadata at chunking time; the generator's system prompt MUST instruct: *"Cite the `chunk_id` for every claim you make from the provided context."* Presentation layer maps `chunk_id` → human-readable source URL.
- **Retrieval eval is a launch gate.** Ragas or DeepEval against a static golden dataset of 50-100 queries, measuring **Faithfulness** (answer matches retrieved chunks) + **Context Precision** (relevant chunk in top-K). No prompt change ships if Faithfulness drops below baseline.
- Summarizer (batch or on-demand)
- Q&A UI or report generation
- **Depends on:** Phase 1 (needs retriever). Phase 2 optional (classification enriches answers)
- **Delivers:** AI-generated answers and insights with grounded citations

## Infrastructure Requirements

- **PostgreSQL** with `pgvector` + `pg_trgm` extensions on **postgres-main** (`pgvector/pgvector:pg16` image); vendor `fabrik-lib/rag` for the pipeline. HNSW index, `m=16, ef_construction=64`.
- **Spec flag:** `shape.has_search_feature: true` — registrar owns index/extension lifecycle. Never create indexes manually.
- **Background worker** for chunking, embedding, classification (never inline in API handlers).
- **OpenRouter** (`OPENROUTER_API_KEY`) — **the only gateway for embeddings** (Kilo CLI has no embedding endpoint). LLM components (classifier / generator / summarizer / re-ranker) may use OpenRouter API (high-volume, app code) OR Kilo CLI (low-volume scripts/tooling). Vendor SDKs (`dashscope`, `google-cloud-aiplatform`, OpenAI direct) are **banned**.
- **No dedicated vector databases** (Pinecone, Qdrant, Weaviate banned — pgvector only).

## Rule Packs (for coding agents, not Traycer)

- `core/65-rag-search.md` — full RAG architecture: vector storage, hybrid search, embedding models, pipeline components, model selection
- `core/66-rag-chunking.md` — 12-rule chunking spec (heading-based splitting, envelopes, quality checks — applies to any text, not just Markdown)
- `core/75-workers-jobs.md` — background processing for chunking/embedding/classification pipelines
