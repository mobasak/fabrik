<!-- RAG Domain Module — loaded by 02-epic-decomposition-command
     when Vision Summary Technology Decisions includes a RAG pipeline.
     Not scaffold-specific — any project type can need RAG.
     Consumer: Traycer planning LLM (NOT coding agents).
     Coding agents use .windsurf/rules/core/65-rag-search.md + 66-rag-chunking.md instead. -->

# RAG Domain Module

## What RAG Is

Retrieval-Augmented Generation. Your product has a corpus of text (comments, documents, articles, support tickets). Users need to find, filter, and extract intelligence from it. RAG is the system that makes this possible.

Without RAG: users stare at a list or use ctrl+F.
With RAG: users ask questions in natural language, filter by structured attributes, and get AI-generated answers grounded in their actual data.

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
|---|---|---|
| Full-text search over a corpus (docs, comments, articles) | Embeddings + Retriever | 1 |
| Structured filtering (by intent, sentiment, entity, category) | + Classifier | 2 |
| Natural-language Q&A ("what do people say about X?") | + Answer Generator | 3 |
| Dashboard insights, PDF reports, executive summaries | + Summarizer | 3 |
| Mission-critical precision (legal, medical, compliance) | + Re-ranker | 3+ |

**Start at Phase 1. Add phases when the product demands them.** Each phase is an independent epic — no need to plan all at once.

## Phase Progression

| Phase | What ships | User sees | AI cost |
|---|---|---|---|
| **Phase 1: Search** | Embeddings + Retriever + Chunking | Semantic search bar. "Find comments about X." | One-time: ~$0.01/M tokens for embedding |
| **Phase 2: Intelligence** | + Classifier | Structured filters. "Show buying intent for retinol, negative sentiment." | One-time: ~$0.02-0.15/M tokens for classification |
| **Phase 3: Generation** | + Answer Generator + Summarizer | AI-written answers, dashboard insights, reports | Per-query: ~$0.02-0.15 per answer |
| **Phase 3+: Precision** | + Re-ranker | Better top-10 results for complex queries | Per-query: adds ~50ms latency |

## Epic Patterns for Decomposition

When `02-epic-decomposition-command` encounters a RAG pipeline in the Vision Summary:

### Phase 1 Epic: "Search Pipeline"
- Chunking pipeline (per `core/66-rag-chunking.md`)
- Embedding pipeline (per `core/65-rag-search.md` § Embedding Models)
- Hybrid retriever (pgvector + tsvector + RRF)
- Search API endpoint
- Search UI (if applicable)
- **Depends on:** backend/database epic (needs tables, schema)
- **Delivers:** working semantic search

### Phase 2 Epic: "Classification Pipeline" (if needed)
- Classifier model selection (benchmark per `core/65-rag-search.md` § Model Selection Rules)
- Classification pipeline (batch processor via `core/75-workers-jobs.md`)
- Structured filter API endpoints
- Filter UI (if applicable)
- **Depends on:** Phase 1 (needs chunks in database)
- **Delivers:** structured filtering on top of search

### Phase 3 Epic: "RAG Intelligence" (if needed)
- Answer generator (prompt + retrieval integration)
- Summarizer (batch or on-demand)
- Q&A UI or report generation
- **Depends on:** Phase 1 (needs retriever). Phase 2 optional (classification enriches answers)
- **Delivers:** AI-generated answers and insights

## Infrastructure Requirements

- **PostgreSQL** with `pgvector` + `pg_trgm` extensions (postgres-main or Supabase)
- **HNSW index** on embedding columns (`m=16, ef_construction=64`)
- **Background worker** for chunking, embedding, classification (never inline in API handlers)
- **OpenRouter API key** (`OPENROUTER_API_KEY`) for embeddings + any LLM components
- **No dedicated vector databases** (Pinecone, Qdrant, Weaviate banned — pgvector only)

## Rule Packs (for coding agents, not Traycer)

- `core/65-rag-search.md` — full RAG architecture: vector storage, hybrid search, embedding models, pipeline components, model selection
- `core/66-rag-chunking.md` — 12-rule chunking spec (heading-based splitting, envelopes, quality checks — applies to any text, not just Markdown)
- `core/75-workers-jobs.md` — background processing for chunking/embedding/classification pipelines
