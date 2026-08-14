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

- **pgvector** on PostgreSQL is the sole vector store, on **`postgres-main`** (shared Fabrik Postgres on the `fabrik` Docker network; `pgvector/pgvector:pg16` — pgvector + pg_trgm enabled) — the default. Pair with `fabrik-lib/rag` for the ingest→search pipeline. (A legacy Supabase project ships pgvector too; the same HNSW indexes + hybrid-search patterns apply until it migrates to `postgres-main`.)
- Dedicated vector databases (Pinecone, Qdrant, Weaviate, Milvus) are **banned** — they add network latency, duplicate data synchronization, and complicate backups. pgvector on `postgres-main` eliminates these problems.
- pgvector with HNSW indexes comfortably handles hundreds of thousands to low single-digit millions of vectors in-RAM. This exceeds Fabrik's projected capacity needs.
- Ensure `pgvector` and `pg_trgm` extensions are enabled in whichever PostgreSQL instance you use.

## HNSW Index Parameters

- Always use **HNSW** indexes. Do not use IVFFlat — it requires manual rebuilds to maintain recall.
- Build parameters: `WITH (m = 16, ef_construction = 64)`. Omitting these yields sub-optimal recall.
- Query-time tuning: set `hnsw.ef_search = 40` for interactive UI latency, `200` for analytical background jobs.
- **Note**: pgvector 0.7+ HNSW is production-ready. IVFFlat is the old default and significantly slower.

## Hybrid Search

- Pure vector similarity search is **banned** for user-facing queries. Dense vectors fail on exact keyword matches (error codes, UUIDs, SKUs, acronyms).
- Every search must independently query:
  1. **Dense**: pgvector cosine distance (`<=>`) via HNSW index.
  2. **Sparse**: PostgreSQL native `tsvector` with `ts_rank_cd` (coverage-density ranking — NOT BM25; native Postgres full-text has no BM25. For true BM25, use ParadeDB `pg_search` or VectorChord-bm25 extension).
- Results are fused via **Reciprocal Rank Fusion (RRF)**: `score = 1.0 / (60 + rank)`. The constant `k=60` is the default.
- **Never** add raw vector cosine scores to raw keyword ranking scores — their distributions are mathematically incompatible. RRF normalizes via rank position.
- Do not deploy external cross-encoder re-rankers unless explicitly required — they add massive latency to the critical path.

## Chunking Strategy

- Use **Recursive Character Splitting**. Semantic chunking (embedding-similarity-based splitting) is banned — it is expensive, slow, and yields only 3–5% marginal retrieval gain.
- Default chunk size: **300–800 tokens** (target), **1,200 hard max**, **120 minimum**, **10–20% overlap**. See `66-rag-chunking.md` for the authoritative size targets.
- Pre-process and chunk text asynchronously via the background worker queue. Never block the main API thread with ingestion.
- **For Markdown documents:** chunk by `##` headings first, preserve heading breadcrumbs in every chunk, never split inside tables/code blocks/numbered lists. See `66-rag-chunking.md` for the full 12-rule chunking spec including chunk envelopes, overlap strategy, and quality checks.

## RAG Pipeline Components

A RAG system uses multiple stages. Some need AI models, some don't.

| Component | What it does | Gateway | Notes |
|---|---|---|---|
| **Embeddings** | Text → vector | **OpenRouter API only** | Kilo CLI has no embedding support |
| **Classifier** (optional) | Chunk → structured labels (intent, sentiment, entities) | **OpenRouter API** (high volume) or **Kilo CLI** (low volume) | Project-specific ontology — define in project docs, not here |
| **Answer generator** | Retrieved chunks → human answer | OpenRouter API or Kilo CLI | For RAG Q&A UIs |
| **Summarizer** (optional) | Multiple chunks → condensed insight | OpenRouter API or Kilo CLI | For reports/dashboards |
| **Re-ranker** (optional) | Re-score top-K for precision | OpenRouter API | Only if retrieval quality insufficient |
| **Retriever** | Query → ranked chunks | **No AI model** — pgvector + tsvector + RRF in PostgreSQL | Pure SQL, zero API calls |

### Two Gateways

| Gateway | When to use | Overhead | Cost advantage |
|---|---|---|---|
| **OpenRouter API** (`httpx` → `openrouter.ai/api/v1/`) | Application code, automated pipelines, high volume. **Required for embeddings.** | <100ms/call | Pay-per-token |
| **Kilo CLI** (`kilo run --model kilo/<provider>/<model>`) | Scripts, tooling, low-volume tasks (i18n validation, code review, one-off analysis) | 3-5s/call (subprocess) | Free tiers + 50% bonus credits on Kilo Pass ($19/mo) |

**Banned:** calling vendor APIs directly (Alibaba Cloud, Google Vertex, OpenAI direct). Never import vendor-specific SDKs (`dashscope`, `google-cloud-aiplatform`). Both gateways abstract provider details.

### Model Selection Rules

- **Benchmark 2-3 candidates with real project data before selecting.** Price ≠ quality. Test with multilingual samples (TR+EN minimum) — cheaper models often beat expensive ones on non-English text.
- **Start cheap, upgrade on measured failure.** Cheapest model that passes a 50-100 sample golden set at >90% accuracy wins. Swap = one line change (model ID string).
- **Multilingual is the deciding factor.** A model that returns empty entities for Turkish text is disqualified regardless of English quality.

## Embedding Models

**Use ONLY these models.** Auto-updated daily by `scripts/kilo-benchmarks/embedding_export_markdown.py`. Called via OpenRouter `/v1/embeddings` endpoint — one API key (`OPENROUTER_API_KEY`), all providers unified.

```python
# Production pattern — OpenRouter embeddings
async def embed(texts: list[str], model: str = "qwen/qwen3-embedding-8b") -> list[list[float]]:
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://openrouter.ai/api/v1/embeddings",
            headers={"Authorization": f"Bearer {get_settings().openrouter_api_key}"},
            json={"model": model, "input": texts},
            timeout=30.0,
        )
        resp.raise_for_status()
        return [item["embedding"] for item in resp.json()["data"]]
```

<!-- EMBEDDING_WINNERS:START (auto-generated — do not edit between markers) -->
| Role | Use when | Model | Cost | Context |
|---|---|---|---|---|
| **Code-specific** | Separate pipeline — IDE semantic search, codebase retrieval | `voyageai/voyage-code-4` | $0.12/M | 32k |
| **Premium quality** | Separate pipeline — only when max recall needed AND budget allows full re-embed | `voyageai/voyage-4-large` | $0.12/M | 32k |
| **Premium quality fallback** | Fallback if P1 unavailable | `voyageai/voyage-code-4` | $0.12/M | 32k |
| **Default (TR+EN)** | Most projects — use ONE model for BOTH ingest and query | `qwen/qwen3-embedding-8b` | $0.01/M | 32k |
| **Default (TR+EN) fallback** | Fallback if P1 unavailable | `qwen/qwen3-embedding-4b` | $0.02/M | 32k |
<!-- EMBEDDING_WINNERS:END -->

Full roster: `docs/reference/kilo/KILO_AGENT_SELECTION_GUIDE.md` § Embedding Roster.

### Embedding Rules

- **ONE model per search pipeline.** Documents and queries MUST use the same model — cosine similarity only works within a single embedding space.
- **Target 1024 dimensions** (via `dimensions` API parameter). Matryoshka Representation Learning (MRL) means the first N dimensions carry the most information — 4096→1024 loses only ~1-3% accuracy (MTEB benchmarks) while cutting memory/search/index size 4x. At 975K chunks: 1024d = 3.9 GB vs 4096d = 15.6 GB (VPS has 12 GB total). Upgrade to 1536/2048 later by adding a parallel column and re-embedding.
- **Default:** `qwen/qwen3-embedding-8b` for both ingest and query. $0.01/M, multilingual (TR+EN), 32k context.
- **Frontier:** `text-embedding-3-large` only when max recall needed AND full corpus re-embed is budgeted. 13x more expensive.
- **Code:** `codestral-embed-2505` for code-specific pipelines. Separate index from natural-language search.
- Switching models = full re-embed (unless same dimensionality).
- **`text-embedding-3-small` is NOT in the roster.** Use `qwen3-embedding-8b` instead (cheaper, multilingual, longer context).

## Token Budgeting

- **85% rule**: never fill the LLM context window past 85% of its stated maximum. The remaining 15% is the safety buffer for system prompts, generation tokens, and BPE estimation variance.
- Token counting is **model-dependent**. Use the model's own tokenizer or counting endpoint:
  - **OpenAI models:** `tiktoken` (`o200k_base` or `cl100k_base`)
  - **Anthropic (Claude):** `client.count_tokens()` endpoint
  - **Local Ollama models:** model's tokenizer or approximate with tiktoken (the 15% buffer absorbs drift)
- Heuristic character-division (`len(text) / 4`) is **banned** — it fails unpredictably with code blocks and non-English text.
- **Context limits vary wildly by model.** Never hardcode a single `MODEL_LIMIT` — look it up per model:

```python
# Model-specific context limits — DO NOT hardcode a single value
MODEL_LIMITS = {
    "claude-sonnet-4-6": 200_000,
    "gpt-4o": 128_000,
    "gemini-2.5-pro": 1_000_000,
    "llama-3.3-70b": 128_000,
    "qwen3-32b": 32_768,       # local Ollama
}

model_limit = MODEL_LIMITS.get(model, 32_000)  # conservative default
budget = int(model_limit * 0.85)

# Count tokens with the appropriate tokenizer
token_count = count_tokens(prompt, model)  # model-specific implementation
if token_count > budget:
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
| Dedicated vector DBs (Pinecone, Qdrant, Weaviate, Milvus) | pgvector on `postgres-main` — no network latency, no sync, single backup, $0 cost |
| IVFFlat indexes | HNSW with `m=16, ef_construction=64` |
| Pure vector search for user-facing queries | Hybrid search (pgvector + tsvector + RRF) |
| Adding raw cosine scores to raw keyword ranking scores | Reciprocal Rank Fusion: `1.0 / (60 + rank)` |
| Semantic chunking (embedding-similarity splits) | Recursive Character Splitting with 10–20% overlap |
| Heuristic token counting (`len / 4`) | Model-specific tokenizer or `tiktoken` (with 15% buffer for non-OpenAI) |
| Hardcoded `MODEL_LIMIT = 128_000` | Per-model context limits from a config dict |
| Filling 100% of LLM context window | 85% token budget cap |
| Synchronous ingestion on API thread | Async ingestion via background worker queue |
| Manual Meili index creation via API | `shape.has_search_feature: true` — registrar owns lifecycle |
| Indexing all attributes (Meili default) | Explicit `searchableAttributes` + `filterableAttributes` + `sortableAttributes` |
| Synchronous/inline reindex on the API thread | Async reindex via background worker |
| pgvector for exact keyword/typo search | MeiliSearch full-text |
| MeiliSearch for semantic similarity | pgvector cosine + hybrid |

---

## Related Rule Packs

- `25-data-postgres.md` — pgvector lives on `postgres-main`, indexing discipline
- `58-resilience.md` — timeout/retry for MeiliSearch and pgvector calls
- `75-workers-jobs.md` — async ingestion/reindex via job queue
- `66-rag-chunking.md` — 12-rule Markdown chunking spec

---

## Done When

- [ ] `pgvector` and `pg_trgm` extensions enabled — no external vector DB dependencies.
- [ ] HNSW indexes created with `m=16, ef_construction=64` on all embedding columns.
- [ ] Embedding model from the auto-generated roster — not selected from agent training data.
- [ ] ONE embedding model per pipeline — same model for ingest and query.
- [ ] Dimensions set to 1024 via API parameter.
- [ ] All AI calls go through OpenRouter API (embeddings) or OpenRouter/Kilo CLI (LLM tasks) — no vendor SDKs.
- [ ] User-facing search uses hybrid (dense + sparse) with RRF fusion — no pure vector search.
- [ ] Chunks are 300–800 tokens (target) with 10–20% overlap per `66-rag-chunking.md`.
- [ ] Token counting uses model-specific tokenizer (or `tiktoken` with 15% buffer) — no heuristic `len/4`.
- [ ] Context budget capped at 85% of per-model limit before LLM dispatch — no hardcoded `128_000`.
- [ ] Chunk metadata includes document ID and sequence number for citation tracking.
- [ ] Retrieval eval tests (Faithfulness + Context Precision) exist against a golden dataset.
- [ ] Search feature declared via `shape.has_search_feature: true` — no manual index creation.
- [ ] `searchableAttributes`, `filterableAttributes`, `sortableAttributes` explicitly declared per index.
- [ ] Synonyms defined for domain terms; `typo` ranking rule retained.
- [ ] Meili indexing and reindex run via background worker — API thread never blocked.
- [ ] Meili + pgvector calls wrapped with timeout/retry per `58-resilience.md`.

---

## Epic Decomposition (PLANNING layer — read before any RAG epic exists)

> Promoted from `docs/traycer/mega-epic-breakdown/domain-modules/rag.md` (2026-07-13), which has been deleted.
> That module's two *unique* infrastructure claims were both **FALSE and dangerous** — see the warning below.

**Planning consequence of § Choosing:** if the Vision Summary's search use case is **pure catalog / doc-site /
faceted filtering / typo-tolerant keyword**, do **NOT** decompose into RAG epics at all — emit a **single
MeiliSearch-integration epic** instead. RAG is for *keyword + meaning fused* retrieval. Decomposing a catalog
search into embeddings / retriever / generator epics is the most expensive way to build a feature MeiliSearch
gives you in one ticket.

**Phase progression** — start at Phase 1; add a phase only when the product demands it:
Phase 1 retrieval (embeddings + retriever) → Phase 2 + classifier/labels → Phase 3 + answer generator /
summarizer. Each phase is its own epic; each later phase depends on the one before.

> ### ⚠️ WHO CREATES THE pgvector EXTENSION AND THE HNSW INDEX — READ THIS
>
> **The registrar does NOT.** `shape.has_search_feature: true` provisions **MeiliSearch only**
> (`src/fabrik/drivers/meilisearch.py` — `SHAPE_FLAG = "has_search_feature"`; its entire mutation surface is an
> HTTP POST to the Meili container). Executed against the codebase: **`hnsw` appears ZERO times in `src/`**, and
> no registrar issues `CREATE EXTENSION`.
>
> So **every RAG epic MUST carry its own migration** creating the extension and the index:
> `CREATE EXTENSION IF NOT EXISTS vector;` (a **superuser, run-once** step — see `specs/services/youtube.yaml`)
> and the HNSW index per § Vector Storage (`m=16, ef_construction=64`).
>
> The deleted `rag.md` told planners *"the registrar owns index/extension lifecycle — never create indexes
> manually."* A planner that believed it emitted a RAG pipeline **with no index at all**. There is no shape flag
> for pgvector; do not look for one.

