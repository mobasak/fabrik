---
activation: glob
globs: ["**/embeddings/**", "**/retrieval/**", "**/rag/**", "**/vector/**", "**/search/**"]
description: Search & retrieval discipline — MeiliSearch full-text, pgvector embeddings, hybrid search, chunking, citations, retrieval evals
trigger: glob
---
<!-- CONSUMER: Coding agents building search/retrieval features
     GOAL: MeiliSearch vs pgvector decision, index lifecycle, hybrid search, chunking, citations
     TRAYCER USAGE: Injects as Context File for search-related tickets. Decision guide shapes tech-plan.
     AGENT USAGE: Follow the decision guide. Use MeiliSearch for keyword search, pgvector for semantic. -->

# Search & Retrieval Rules

Apply when working on embedding pipelines, vector search, retrieval-augmented generation, or text search. Skip for pure CRUD, UI, or infrastructure work.

## Choosing: MeiliSearch vs pgvector

| Need | Use |
|------|-----|
| Instant keyword search, typo tolerance, autocomplete, faceted filtering (products, docs) | **MeiliSearch** |
| Semantic similarity, "find similar", recommendations | **pgvector** (see Vector Storage below) |
| Knowledge-base / Q&A retrieval needing keyword + meaning fused | **pgvector hybrid** (dense + tsvector + RRF) |

Both MeiliSearch and pgvector-hybrid handle keywords. Pick **MeiliSearch** when typo-tolerance, faceting, or instant as-you-type UX matter (catalog/doc search). Pick **pgvector hybrid** when the keyword match feeds an LLM or semantic pipeline.

## Full-text Search (MeiliSearch)

Apply for instant keyword search: product catalogs, documentation, autocomplete, faceted filtering.

### Index Lifecycle (registrar-owned)

- Indexes are auto-created when `shape.has_search_feature: true` in `specs/services/<id>.yaml`. Index name = `<id_with_underscores>`.
- **Never** create or delete indexes via the Meilisearch API directly — the registrar owns lifecycle (`fabrik apply` creates, `fabrik destroy --drop-data` destroys). Manual index creation drifts from spec.

### Index Configuration

- Declare attributes explicitly per index — Meili indexes everything by default, which bloats the index and slows search:
  - `searchableAttributes`: ordered by importance (first = highest ranking weight). Only fields users actually search.
  - `filterableAttributes`: fields used in `filter=` (category, price, status, tags). Required before you can filter on them.
  - `sortableAttributes`: fields used in `sort=` (price, date). Required before you can sort on them.
- Set these at index setup, not per-query. Changing them triggers a full reindex.

### Ranking & Relevance

- Keep Meili's default ranking rules (`words, typo, proximity, attribute, sort, exactness`) unless a documented product need requires reordering. Never remove `typo` — typo-tolerance is the main reason to choose Meili over pgvector `tsvector`.
- Define `synonyms` for domain terms (SKU aliases, abbreviations, TR/EN pairs) at index config time.

### Ingestion & Reindex

- Push documents in batches via the background worker queue — never block the API thread on indexing.
- Reindex (settings or schema change) runs as an async background job, never inline in a request.

### Resilience

- MeiliSearch and pgvector are external dependencies — wrap all calls with timeout + retry per `58-resilience.md`. A search-backend outage must degrade gracefully, never hang the request.

## Vector Storage

- **pgvector** on PostgreSQL 16 is the sole vector store. Dedicated vector databases (Pinecone, Qdrant, Weaviate, Milvus) are **banned** — they add network latency, duplicate data synchronization, and complicate backups.
- pgvector with HNSW indexes handles 50M+ vectors with sub-millisecond search. This exceeds Fabrik's projected capacity needs.
- Ensure `pgvector` and `pg_trgm` extensions are enabled in the PostgreSQL instance.

## HNSW Index Parameters

- Always use **HNSW** indexes. Do not use IVFFlat — it requires manual rebuilds to maintain recall.
- Build parameters: `WITH (m = 16, ef_construction = 64)`. Omitting these yields sub-optimal recall.
- Query-time tuning: set `hnsw.ef_search = 40` for interactive UI latency, `200` for analytical background jobs.
- **Note**: With PG16 + pgvector 0.7+, HNSW is production-ready. IVFFlat is the old default and significantly slower.

## Hybrid Search

- Pure vector similarity search is **banned** for user-facing queries. Dense vectors fail on exact keyword matches (error codes, UUIDs, SKUs, acronyms).
- Every search must independently query:
  1. **Dense**: pgvector cosine distance (`<=>`) via HNSW index.
  2. **Sparse**: PostgreSQL native `tsvector` with `ts_rank_cd` (BM25).
- Results are fused via **Reciprocal Rank Fusion (RRF)**: `score = 1.0 / (60 + rank)`. The constant `k=60` is the default.
- **Never** add raw vector cosine scores to raw BM25 scores — their distributions are mathematically incompatible. RRF normalizes via rank position.
- Do not deploy external cross-encoder re-rankers unless explicitly required — they add massive latency to the critical path.

## Chunking Strategy

- Use **Recursive Character Splitting**. Semantic chunking (embedding-similarity-based splitting) is banned — it is expensive, slow, and yields only 3–5% marginal retrieval gain.
- Default chunk size: **512–1024 tokens** with **10–20% overlap** to preserve context across boundaries.
- Pre-process and chunk text asynchronously via the background worker queue. Never block the main API thread with ingestion.
- **For Markdown documents:** chunk by `##` headings first, preserve heading breadcrumbs in every chunk, never split inside tables/code blocks/numbered lists. See `docs/reference/MD/rag-chunking-rules.md` for the full 12-rule chunking spec including chunk envelopes, overlap strategy, and quality checks.

## Embedding Models

- Defaults (pick based on context):
  - **API (high accuracy)**: `voyage-3-large` (1024 dimensions) or `text-embedding-3-large`.
  - **Self-hosted (Ollama)**: `Qwen3-Embedding`. <!-- verify current model at use time; embedding model names change fast -->
- Target 1024–1536 dimensions — lower dimensionality reduces PostgreSQL memory overhead.

## Token Budgeting

- **85% rule**: never fill the LLM context window past 85% of its stated maximum. The remaining 15% is the safety buffer for system prompts, generation tokens, and BPE estimation variance.
- Use `tiktoken` (specifically `o200k_base` or `cl100k_base` for OpenAI models) to count tokens before dispatching to the LLM API. Heuristic character-division (`len(text) / 4`) is **banned** — it fails unpredictably with code blocks and non-English text.

```python
import tiktoken

encoding = tiktoken.encoding_for_model(model)
MODEL_LIMIT = 128_000
BUDGET = int(MODEL_LIMIT * 0.85)

if len(encoding.encode(prompt)) > BUDGET:
    # Truncate context chunks until within budget
    ...
```

## Citations & Source Attribution

- During chunking, inject the document's global ID and chunk sequence number into the chunk's metadata (stored alongside the embedding in PostgreSQL).
- Explicitly instruct the LLM in the system prompt: *"Cite the `chunk_id` for every claim you make from the provided context."*
- The presentation layer maps cited `chunk_id` values back to human-readable source documents or URLs before rendering.

## Retrieval Quality Evaluation

- Measure only two core metrics: **Faithfulness** (does the answer match the retrieved chunks?) and **Context Precision** (is the relevant chunk in the top-K results?).
- Automate evaluation via Ragas or DeepEval in unit tests against a static golden dataset of 50–100 test queries.
- Do not deploy prompt changes if Faithfulness drops below the established baseline.

---

## Banned Patterns

| Pattern | Use Instead |
|---------|-------------|
| Dedicated vector DBs (Pinecone, Qdrant, Weaviate) | pgvector on PostgreSQL 16 |
| IVFFlat indexes | HNSW with `m=16, ef_construction=64` |
| Pure vector search for user-facing queries | Hybrid search (pgvector + tsvector + RRF) |
| Adding raw cosine scores to raw BM25 scores | Reciprocal Rank Fusion: `1.0 / (60 + rank)` |
| Semantic chunking (embedding-similarity splits) | Recursive Character Splitting with 10–20% overlap |
| Heuristic token counting (`len / 4`) | `tiktoken.encoding_for_model()` BPE counting |
| Filling 100% of LLM context window | 85% token budget cap |
| Synchronous ingestion on API thread | Async ingestion via background worker queue |
| Manual Meili index creation via API | `shape.has_search_feature: true` — registrar owns lifecycle |
| Indexing all attributes (Meili default) | Explicit `searchableAttributes` + `filterableAttributes` + `sortableAttributes` |
| Synchronous/inline reindex on the API thread | Async reindex via background worker |
| pgvector for exact keyword/typo search | MeiliSearch full-text |
| MeiliSearch for semantic similarity | pgvector cosine + hybrid |

---

## Done When

- [ ] `pgvector` and `pg_trgm` extensions enabled — no external vector DB dependencies.
- [ ] HNSW indexes created with `m=16, ef_construction=64` on all embedding columns.
- [ ] User-facing search uses hybrid (dense + sparse) with RRF fusion — no pure vector search.
- [ ] Chunks are 512–1024 tokens with 10–20% overlap using recursive splitting.
- [ ] Token counting uses `tiktoken` — no heuristic division in any LLM API call path.
- [ ] Context budget capped at 85% of model limit before LLM dispatch.
- [ ] Chunk metadata includes document ID and sequence number for citation tracking.
- [ ] Retrieval eval tests (Faithfulness + Context Precision) exist against a golden dataset.
- [ ] Search feature declared via `shape.has_search_feature: true` — no manual index creation.
- [ ] `searchableAttributes`, `filterableAttributes`, `sortableAttributes` explicitly declared per index.
- [ ] Synonyms defined for domain terms; `typo` ranking rule retained.
- [ ] Meili indexing and reindex run via background worker — API thread never blocked.
- [ ] Meili + pgvector calls wrapped with timeout/retry per `58-resilience.md`.
