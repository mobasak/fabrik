---
activation: glob
globs: ["**/embeddings/**", "**/retrieval/**", "**/rag/**", "**/vector/**"]
description: RAG & search discipline — embeddings, chunking, vector storage, citations, context windows, retrieval evals
trigger: glob
---

# RAG & Search Rules

Apply when working on embedding pipelines, vector search, retrieval-augmented generation, or text search. Skip for pure CRUD, UI, or infrastructure work.

## Vector Storage

- **pgvector** on PostgreSQL 16 is the sole vector store. Dedicated vector databases (Pinecone, Qdrant, Weaviate, Milvus) are **banned** — they add network latency, duplicate data synchronization, and complicate backups.
- pgvector with HNSW indexes handles 50M+ vectors with sub-millisecond search. This exceeds Fabrik's projected capacity needs.
- Ensure `pgvector` and `pg_trgm` extensions are enabled in the PostgreSQL instance.

## HNSW Index Parameters

- Always use **HNSW** indexes. Do not use IVFFlat — it requires manual rebuilds to maintain recall.
- Build parameters: `WITH (m = 16, ef_construction = 64)`. Omitting these yields sub-optimal recall.
- Query-time tuning: set `hnsw.ef_search = 40` for interactive UI latency, `200` for analytical background jobs.
- **Note**: With PG16 + pgvector 0.7+, HNSW is production-ready. IVFFlat is the old default and significantly slower.

## Vector DB Selection Rationale

- **pgvector**: Use when vectors are a feature of your app alongside relational data
- **Qdrant/Weaviate**: Use when vectors are the app — millions of embeddings, complex filtering at scale, and you need a dedicated search engine with its own clustering/sharding.

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

## Embedding Models

- Defaults (pick based on context):
  - **API (high accuracy)**: `voyage-3-large` (1024 dimensions) or `text-embedding-3-large`.
  - **Self-hosted (Ollama)**: `Qwen3-Embedding`.
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
