---
activation: glob
globs: ["**/embeddings/**", "**/retrieval/**", "**/rag/**", "**/vector/**", "**/search/**"]
description: Search & retrieval discipline — MeiliSearch full-text, pgvector three-leg hybrid search via the vendored fabrik-lib `rag` module, embeddings through OpenRouter, chunking, citations, retrieval evals; the fleet's pgvector state stated as probed
trigger: glob
currency_pass: 2026-09-22
---
<!-- CONSUMER: Coding agents building search/retrieval features
     GOAL: MeiliSearch vs pgvector decision, index lifecycle, hybrid search, chunking, citations
     TRAYCER USAGE: Injects as Context File for search-related tickets. Decision guide shapes tech-plan.
     AGENT USAGE: Follow the decision guide. Use MeiliSearch for keyword search, pgvector (the vendored `rag` module) for semantic + hybrid. -->

# Search & Retrieval Rules

Apply when working on embedding pipelines, vector search, retrieval-augmented generation, or text search. Skip for pure CRUD, UI, or infrastructure work. **The reference implementation is fabrik-lib `rag/`** (vendor it: `cp -r /opt/fabrik-lib/rag/ src/rag/`) — ingest → chunk → embed → three-leg hybrid search → optional rerank → eval harness; this pack states the rules that module implements and the fleet facts it depends on.

## Choosing: MeiliSearch vs pgvector

| Need | Use |
|------|-----|
| Instant keyword search, typo tolerance, autocomplete, faceted filtering (products, docs) | **MeiliSearch** |
| Query-free item-to-item similarity from a stored vector ("more like this", recommendations) | **pgvector** cosine alone — the one pure-vector case (§ Hybrid Search) |
| Knowledge-base / Q&A retrieval needing keyword + meaning fused | **pgvector hybrid** (dense + tsvector + trigram + RRF — the `rag` module's `search()`) |

Both MeiliSearch and pgvector-hybrid handle keywords. Pick **MeiliSearch** when typo-tolerance, faceting, or instant as-you-type UX matter (catalog/doc search). Pick **pgvector hybrid** when the keyword match feeds an LLM or semantic pipeline. MeiliSearch also ships its own vector/hybrid search (per-index `embedders`, `semanticRatio`) — **not used here: one vector store per project.** Two embedding pipelines drift apart (different models, different chunking) and the Meili copy has no eval harness; semantic retrieval lives in pgvector, Meili stays keyword.

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

- Keep Meili's DEFAULT ranking rules unless a documented product need requires reordering — and do not write the list yourself, because it depends on the version: from Meilisearch v1.36 the default is seven (`words, typo, proximity, attributeRank, sort, wordPosition, exactness`); the fleet's `meilisearch` container runs v<!--v:meilisearch_major-->1.13<!--/v--> (probed 2026-09-22), whose default is six with the combined `attribute` rule — a settings PUT naming `attributeRank`/`wordPosition` against it is rejected, and the two forms cannot be mixed on any version. Never remove `typo` — typo-tolerance is the main reason to choose Meili over pgvector `tsvector`.
- Define `synonyms` for domain terms (SKU aliases, abbreviations, TR/EN pairs) at index config time.

### Ingestion & Reindex

- Push documents in batches via the background worker queue — never block the API thread on indexing.
- Reindex (settings or schema change) runs as an async background job, never inline in a request.

### Resilience

- MeiliSearch and pgvector are external dependencies — wrap Meili and ingest DB calls with timeout + retry per `58-resilience.md`. **Neither `search()` nor `embed_texts()`/`embed_single()` takes an outer retry:** `search()` is deadline-bounded and deliberately retry-free (`max_retries=0` — a retry multiplies `RAG_SEARCH_DEADLINE_S` and re-enters the in-flight bound), and the embed client already retries internally (`MAX_RETRIES` with exponential backoff, one breaker failure per exhausted request) — an outer retry multiplies both and trips the breaker early. A search-backend outage must degrade gracefully, never hang the request (the `rag` module's `search()` fails OPEN to `[]` on ANY embed or SQL failure — a deadline, in-flight saturation, an open breaker, a statement timeout, a missing `rag_search()` — and returns NO degradation signal: a failed search and an empty corpus are the same `[]`. Wrap `search()` and read your own timer/breaker to surface "degraded" instead of "no results"; the missing signal is filed upstream, the same class as `hnsw.iterative_scan`).

## Vector Storage

- **pgvector on PostgreSQL is the sole vector store, on `postgres-main`** (the shared Fabrik Postgres on the `fabrik` Docker network). Dedicated vector databases (Pinecone, Qdrant, Weaviate, Milvus) are **banned** — network latency, a second copy of the data to keep in sync, a second backup.
- ⚠️ **The rule is ahead of the fleet — verify before you plan.** Probed 2026-09-22 on the hub: `postgres-main` runs the plain `postgres:<!--v:postgres_major-->16<!--/v-->-alpine` image; `pg_trgm` is available (installed in one database), and the `vector` extension is **not available at all** — `pg_available_extensions` has no row for it, so `CREATE EXTENSION vector` cannot succeed on any database there. A project that needs vectors **REQUESTS the fleet infra change first** — `python scripts/mail.py send --to fabrik --to-agent fleet --kind request`, asking for (a) the official pgvector image family for the fleet major (`pgvector/pgvector:pg<!--v:postgres_major-->16<!--/v-->` — the same image the CI scaffold already uses), at a pgvector 0.8+ line so `hnsw.iterative_scan` exists, and (b) a superuser `CREATE EXTENSION vector; CREATE EXTENSION pg_trgm;` on the project's database (pgvector's control file is not `trusted`, so a database owner cannot). Never a project-side workaround, never a vector DB, never an in-process index. The probe is HUB-side (a project has no fleet creds): `ssh vps 'sudo -n docker exec -i postgres-main psql -U postgres -tA' <<< "select name, default_version from pg_available_extensions where name in ('vector','pg_trgm')"`.
- One legacy Supabase project (`25-data-postgres.md` still routes it; `agents-fabrik.md` § Supabase names it — if you are not sure it is yours, it is not) ships pgvector today: the same HNSW index and three-leg hybrid apply there until it migrates to `postgres-main`, and it is the one place pgvector runs without the fleet change.
- The `rag` module's `migration.sql` creates both extensions (`CREATE EXTENSION IF NOT EXISTS vector; … pg_trgm;`) and the `vector(1024)` column — it needs a superuser AND the package present on the server; the registrar creates neither (see § Epic Decomposition).
- Rule of thumb, not a vendor figure: budget an HNSW index at 1024 dimensions as roughly `rows × dims × 4 bytes × 2` (vectors plus graph) against the `memory:` limit in `infra/vps1/postgres/compose.yaml`, the one compose for `postgres-main` — and that limit is shared with `shared_buffers`, `work_mem` and every other project on `postgres-main`, so the practical bound once the fleet change lands is low hundreds of thousands of 1024-dim vectors, not millions; switch the column to `halfvec` (2-byte floats) when that budget binds, and past that a dedicated instance is a fleet request; measure with `pg_relation_size` on the index, never with the thumb.

## HNSW Index Parameters

- Always use **HNSW** indexes. Do not use IVFFlat — it requires manual rebuilds to maintain recall.
- Build parameters: `WITH (m = 16, ef_construction = 64)` — pgvector's own defaults, and what `migration.sql` writes; state them anyway so a hand-written index cannot silently take different ones.
- Query-time tuning: `hnsw.ef_search = 40` (pgvector's default) for interactive latency, `200` for analytical background jobs — the module's `rag_search(…, ef_search_val)` sets it per call with `SET LOCAL`.
- **Filtered queries need iterative scans.** With approximate indexes the `WHERE` filter is applied AFTER the index scan, so a selective filter starves the result set (10% selectivity at `ef_search = 40` averages 4 rows); set `hnsw.iterative_scan = relaxed_order` (pgvector's 0.8 line; `strict_order` keeps exact distance order at lower throughput — `relaxed_order` is the default here because RRF re-ranks by position anyway) for any tenant- or metadata-filtered search. ⚠️ The module does NOT set it today, and its `FORCE ROW LEVEL SECURITY` on `tenant_id` makes EVERY `rag_search()` a filtered query — add `SET LOCAL hnsw.iterative_scan = relaxed_order` beside the `SET LOCAL hnsw.ef_search` in `migration.sql`'s function (or next to `statement_timeout` in `search.py`) and file it in the module's `UPSTREAM_FEEDBACK.md` (mailed to fabrik-lib 2026-09-22).

## Hybrid Search

- Pure vector similarity search is **banned** wherever the query text derives from a user's words — typed, spoken, or LLM-rewritten — because dense vectors fail on exact keyword matches (error codes, UUIDs, SKUs, acronyms). The one sanctioned pure-vector path is query-free item-to-item similarity: a bare `<=>` from a STORED item's own vector (the module ships no helper for it); embedding a user's query and walking from its nearest chunk is a query in disguise.
- Every search runs THREE legs and fuses them — the module's `rag_search()` SQL function, one round trip:
  1. **Dense**: pgvector cosine distance (`<=>`) via the HNSW index.
  2. **Sparse**: PostgreSQL `tsvector` ranked with `ts_rank_cd` over `websearch_to_tsquery('simple', …)` — coverage-density, NOT BM25 (native Postgres full-text has no BM25; when a measured need for true BM25 exists, the maintained Postgres extensions are ParadeDB `pg_search`, VectorChord-bm25 and Tiger Data's `pg_textsearch`). The `simple` configuration has no stemming — language-agnostic by design, which is why the third leg exists.
  3. **Trigram**: `pg_trgm` `similarity()` — catches misspellings, inflected TR/EN forms and codes the other two legs miss.
- Results are fused via **Reciprocal Rank Fusion (RRF)**: `score = Σ 1.0 / (k + rank)` with `k = 60` (Cormack, Clarke & Büttcher, SIGIR 2009 — still pgvector's own hybrid example default; the module's `rrf_k`).
- **Never** add raw vector cosine scores to raw keyword ranking scores — their distributions are mathematically incompatible. RRF normalizes via rank position.
- **Reranking is OPT-IN and measured, never default** — a cross-encoder is a second model call on the critical path, hundreds of milliseconds at the paid tier. It re-scores a widened candidate pool (`search(conn, q, rerank=openrouter_rerank(), candidate_k=50)`) through OpenRouter `/rerank` — the module's tier tries a free model, then `cohere/rerank-v3.5`; it fails FAST and fails OPEN to the RRF order inside the request deadline. Turn it on only when `rag.eval` shows the precision lift on your golden set — the golden set, the `rag.eval` command and its verbatim before/after output committed under `docs/` with the `k` named (a lift nobody can re-RUN was never measured) — and know that it **egresses the candidates' chunk TEXT to the reranker vendor** — never on a corpus whose text may not leave the tenant boundary. The DEFAULT tier's first hop is a FREE model on shared terms: for any tenant-bound corpus pin the tier you reviewed — `openrouter_rerank(tier=["cohere/rerank-v3.5"], api_key=…)` — the review is of the tier you pinned, not of the vendor you had in mind.

## Chunking Strategy

- Use **Recursive Character Splitting** — the module's `chunk_text()` (plaintext: paragraph/sentence boundaries with 10–20% overlap on sentence boundaries; `heading_path` is a breadcrumb it carries, not a split it makes — Markdown heading splits are `66-rag-chunking.md`'s algorithm). Semantic chunking (embedding-similarity splits) is **not used by default**: the one primary evaluation (Chroma's chunking report) shows single-digit-point gains for an embedding call per split; adopt it only with a measured lift on your golden set.
- Chunk size: `66-rag-chunking.md` is the authoritative source — **512–800 tokens** for a vector-embedding pipeline (the module's `chunk_text()` default; one chunk row feeds all three legs, so there is no separate keyword band), **1,200 hard max**, **120 minimum**, **10–20% overlap**; `chunk_text(target_max=…)` is where a project moves off the default, with a measurement (`target_min` is declared but never enforced — 66 § 2).
- Token counts in the chunker are `cl100k_base` approximations (the default embedding model has its own tokenizer); the hard per-chunk ceiling `RAG_EMBED_TOKEN_CEILING` (default 6800, far under the model's limit) guarantees nothing is un-embeddable — raise it toward the model's real limit to reduce splits, never above it.
- Pre-process and chunk text asynchronously via the background worker queue. Never block the main API thread with ingestion.
- **For Markdown documents:** chunk by `##` headings first, preserve heading breadcrumbs in every chunk, never split inside tables/code blocks/numbered lists. See `66-rag-chunking.md` for the full 12-rule chunking spec including chunk envelopes, overlap strategy, and quality checks.

## RAG Pipeline Components

A RAG system uses multiple stages. Some need AI models, some don't.

| Component | What it does | Route | Notes |
|---|---|---|---|
| **Embeddings** | Text → vector | **OpenRouter `/embeddings`** (module `embed.py`) | One key, all providers; batching, retries, circuit breaker, dimension reduction are the module's |
| **Classifier** (optional) | Chunk → structured labels (intent, sentiment, entities) | OpenRouter chat (module `classifier.py`, `RAG_CLASSIFIER_MODEL`) | Project-specific ontology — define in project docs, not here |
| **Answer generator** | Retrieved chunks → human answer | OpenRouter chat (`rag.adapters.openrouter_chat`), the subscription path `claude_p_chat` (`claude -p`, low volume), or a model you run yourself (§ The gateway) | For RAG Q&A UIs |
| **Summarizer** (optional) | Multiple chunks → condensed insight | same routes as the answer generator | For reports/dashboards |
| **Re-ranker** (optional) | Re-score top-K for precision | OpenRouter `/rerank` (module `rerank.py`) | Only with a measured lift — § Hybrid Search |
| **Retriever** | Query → ranked chunks | **No AI model** — pgvector + tsvector + pg_trgm + RRF in PostgreSQL | Pure SQL, zero API calls beyond embedding the query |

### The gateway

**OpenRouter is the one metered gateway** (`https://openrouter.ai/api/v1/` — `/embeddings`, `/chat/completions`, `/rerank`; OpenAI-compatible; `OPENROUTER_API_KEY`). The subscription path for LOW-volume LLM steps — an operator-facing or batch step (a judge run, a one-off classification), never a per-request path — is `claude -p` through the module's `claude_p_chat` adapter; the other exception is a model YOU run where the text never leaves your boundary (a local Ollama, or a GPU worker you operate — § Done When). **The OpenRouter subagent pool, Kilo subagents and the module's `free_lanes_chat` adapter are PAUSED** (operator, D-181/D-182, re-confirmed 2026-09-22 — D-343; `62-using-subagents.md`) — do not wire them into a pipeline; the module's README still recommends `free_lanes_chat` because it predates the pause. The module's `openrouter_chat` adapter rides fabrik-lib `ai-consult`'s `run()` HTTP transport: that is a plain OpenRouter chat call inside a product pipeline, and it is allowed — as are the module's own direct `httpx` posts to `/embeddings`, `/rerank` and `/chat/completions`: what D-343 pauses is `ai-consult`'s coding-workflow fan-out (`consult()`, `panel()`) and `62-using-subagents.md`'s ban on a direct OpenRouter call is scoped to the orchestrator and its seats, never a product runtime.

**Banned:** calling vendor APIs directly (Alibaba Cloud, Google Vertex, OpenAI direct). Never import vendor-specific SDKs (`dashscope`, `google-cloud-aiplatform`). The gateway abstracts provider details.

### Model Selection Rules

- **Benchmark 2-3 candidates with real project data before selecting.** Price ≠ quality. Test with multilingual samples (TR+EN minimum) — cheaper models often beat expensive ones on non-English text.
- **Start cheap, upgrade on measured failure.** Cheapest model that passes a 50-100 sample golden set at >90% accuracy wins. Swap = one env value (`RAG_CLASSIFIER_MODEL`, `RAG_EMBEDDING_MODEL`).
- **Multilingual is the deciding factor.** A model that returns empty entities for Turkish text is disqualified regardless of English quality.
- Model ids and prices are ENV VALUES read from the roster — a default behind an env override (the module's `DEFAULT_MODEL = os.getenv(...)`) is fine, a bare constant is not: a provider retires an id or reprices it without notice (the module's own docstrings carry prices from the day they were benchmarked — the roster and OpenRouter's model page are the current numbers).

## Embedding Models

**Use ONLY the roster models.** The winners block below is auto-managed by the hub's catalog engine (`/opt/ai-model-catalog/engine/embedding_export_markdown.py`, daily) — edit nothing between the markers; a project reads the block, not the hub path. Called via OpenRouter `/v1/embeddings` — one API key (`OPENROUTER_API_KEY`), all providers unified.

```python
# Production pattern — OpenRouter embeddings (what rag/embed.py does, minus its batching/breaker)
async def embed(texts: list[str], model: str, dimensions: int = 1024) -> list[list[float]]:
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://openrouter.ai/api/v1/embeddings",
            headers={"Authorization": f"Bearer {get_settings().openrouter_api_key}"},
            json={"model": model, "input": texts, "dimensions": dimensions},
            timeout=30.0,
        )
        resp.raise_for_status()
        vectors = [item["embedding"] for item in resp.json()["data"]]
        for v in vectors:  # every response, never `assert` (stripped under -O): a provider that ignores `dimensions` returns 4096 — the column is vector(1024)
            if len(v) != dimensions:
                raise ValueError(f"{model} returned {len(v)} dims, expected {dimensions}")
        return vectors
```

<!-- EMBEDDING_WINNERS:START (auto-managed by embedding_export_markdown.py) -->
| Role | Use when | Model | Cost | Context |
|---|---|---|---|---|
| **Default (TR+EN)** | Most projects — use ONE model for BOTH ingest and query | `qwen/qwen3-embedding-8b` | $0.01/M | 32k |
<!-- EMBEDDING_WINNERS:END -->

Full roster with its floors (multilingual, ≥32k context, GA only): `docs/reference/kilo/KILO_AGENT_SELECTION_GUIDE.md` § Embedding Roster (fleet-synced).

### Embedding Rules

- **ONE model per search pipeline.** Documents and queries MUST use the same model — cosine similarity only works within a single embedding space.
- **1024 dimensions** via the `dimensions` API parameter — the module's schema is `vector(1024)` and `RAG_EMBEDDING_DIMENSIONS` defaults to it. The default model outputs 4096 natively and supports Matryoshka truncation to any size 32–4096; the accuracy cost of 1024 on TR+EN is UNMEASURED in any primary source — keep 1024, and measure on your golden set before shrinking further. Upgrade later by adding a parallel column and re-embedding. Check the returned length on EVERY response and raise (the module's `embed.py` already does; a hand-rolled client copies the sample above): whether a given provider honours `dimensions` through OpenRouter is not documented per model, and the fallback model is a different width.
- **Default:** `qwen/qwen3-embedding-8b` for both ingest and query — $0.01/M, 32k context, multilingual (100+ languages by its model card; TR quality is your golden set's to prove). The module's `RAG_EMBEDDING_FALLBACK` is `qwen/qwen3-embedding-4b` — a different model with its own native width; confirm it is listed before relying on it.
- **The roster's `frontier_reference` and `code_embedding` slots are EMPTY today** (no model clears their floors) — the following are benchmark CANDIDATES for those roles, not roster picks: `openai/text-embedding-3-large` when max recall is needed AND a full corpus re-embed is budgeted ($0.13/M, 13× the default, 8k context); `mistralai/codestral-embed-2505` for a code-specific pipeline ($0.15/M, 8k — a separate index from natural-language search). A project that uses one records the benchmark that justified it.
- **`openai/text-embedding-3-small` is on OpenRouter ($0.02/M, 8k) but outside the roster's floors** (not multilingual-first, 8k context) — the roster's default is cheaper AND multilingual; don't pick it from habit. Worth a benchmark against the default when the roster next moves: `voyageai/voyage-4` ($0.06/M, 32k), `google/gemini-embedding-001` ($0.15/M).
- Switching models = full re-embed (unless same dimensionality).

## Token Budgeting

- **85% rule**: never fill the LLM context window past 85% of its stated maximum. The remaining 15% is the safety buffer for system prompts, generation tokens, and BPE estimation variance.
- Token counting is **model-dependent**. Use the model's own tokenizer or counting endpoint:
  - **OpenAI models:** `tiktoken` (`o200k_base` for current models, `cl100k_base` for older ones)
  - **Anthropic (Claude):** `client.messages.count_tokens(...)` (`POST /v1/messages/count_tokens`)
  - **Open models via OpenRouter, a local Ollama, or a GPU worker you operate:** the model's own tokenizer where available, else `tiktoken` as an approximation — the 15% buffer absorbs the drift
- Heuristic character-division (`len(text) / 4`) is **banned** — it fails unpredictably with code blocks and non-English text.
- **Context limits are read from the provider, never hardcoded.** A static per-model table in code rots the week a model moves (the current Claude line is 1M by default, not 200k; the GPT-4o figure is a legacy model's). The source is per ROUTE: `context_length` from OpenRouter's `GET /api/v1/models` for gateway models; the vendor's published window for the `claude -p` path (Anthropic's context-windows page — a claims row, not a constant); `POST /api/show` (`model_info` → `<arch>.context_length`) for a local Ollama model; and for a GPU worker you operate, the inference server's own model-metadata endpoint — `76-gpu-workers.md` § Inference Server Selection owns the server choice — never a constant. Fetch at startup, refresh on a schedule, fail loud.

```python
# Per-model context limits — fetched, never a hand-typed dict
resp = httpx.get("https://openrouter.ai/api/v1/models", timeout=10.0)  # at startup; refresh on a schedule, fail LOUD
resp.raise_for_status()                                                  # an empty dict would budget every model at the fallback — a constant with extra steps
limits = {m["id"]: m["context_length"] for m in resp.json()["data"]}
budget = int(limits[model] * 0.85)                                       # KeyError on an unknown id is the right failure
token_count = count_tokens(prompt, model)       # the model-specific counter above
if token_count > budget:
    ...  # drop the lowest-ranked context chunks until within budget
```

## Citations & Source Attribution

- During chunking, inject the document's global ID and chunk sequence number into the chunk's metadata — in the module these are identity COLUMNS (`source_type`/`source_id`/`chunk_seq`, part of the uniqueness key), not the `metadata` JSONB, which is for filters.
- Explicitly instruct the LLM in the system prompt: *"Cite the `chunk_id` for every claim you make from the provided context."*
- The presentation layer maps cited `chunk_id` values back to human-readable source documents or URLs before rendering.

## Retrieval Quality Evaluation

- **Retrieval is measured offline with the module's harness** — `rag.eval.evaluate(searches, qrels, ks=(1,3,5,10))` → `recall@k`, `precision@k`, `hit@k`, `mrr`, `map`, `ndcg@k`, stdlib-only, no LLM; `@k` is SOURCE-granularity (several chunks of one source count once). The golden set is 50–100 queries with relevant `source_id`s; `rag.eval.synth.generate_qrels` drafts it, a human curates it before it is trusted.
- **Generation is measured only where an answer exists:** the opt-in LLM judge `rag.eval.judge.faithfulness(...)` / `answer_relevance(...)` (any `Chat` adapter), or Ragas' `Faithfulness` + `Context Precision` (DeepEval names the second `Contextual Precision`). A non-generative retrieval surface cannot tick a faithfulness metric honestly.
- Run the harness in unit tests against the golden set; do not deploy a prompt or model change if faithfulness or `recall@10` drops below the established baseline; measure a reranker's lift the same way before enabling it.

---

## Banned Patterns

| Pattern | Use Instead |
|---------|-------------|
| Dedicated vector DBs (Pinecone, Qdrant, Weaviate, Milvus), in-process indexes (FAISS, hnswlib, sqlite-vec, local Chroma) or a vector index on `redis-main` | pgvector on `postgres-main` — after the fleet has it (§ Vector Storage); the interim is the fleet request, not a second store |
| Meilisearch `embedders` / `semanticRatio` in any project | One vector store: pgvector (after the fleet change); Meili stays keyword — the interim is the fleet request, not Meili's embedders |
| IVFFlat indexes | HNSW with `m=16, ef_construction=64`; `hnsw.iterative_scan` for filtered queries |
| Pure vector search on any query derived from a user's words (typed, spoken, LLM-rewritten) | Three-leg hybrid (pgvector + tsvector + pg_trgm + RRF); pure cosine only for query-free item-to-item similarity from a stored vector |
| Adding raw cosine scores to raw keyword ranking scores | Reciprocal Rank Fusion: `1.0 / (60 + rank)` |
| A reranker on by default, or on text that may not leave the tenant | Opt-in `search(rerank=…)` after a measured lift; fail-open; egress reviewed |
| Semantic chunking without a measured lift | Recursive Character Splitting with 10–20% overlap (`chunk_text()`) |
| Heuristic token counting (`len / 4`) | Model-specific tokenizer or `tiktoken` (with the 15% buffer) |
| Any static per-model context limit — a dict, a config file, an env value, a constant, whatever it is named | The per-route provider source at startup (§ Token Budgeting) |
| Filling 100% of LLM context window | 85% token budget cap |
| Synchronous ingestion on API thread | Async ingestion via background worker queue |
| Manual Meili index creation via API | `shape.has_search_feature: true` — registrar owns lifecycle |
| Indexing all attributes (Meili default) | Explicit `searchableAttributes` + `filterableAttributes` + `sortableAttributes` |
| Synchronous/inline reindex on the API thread | Async reindex via background worker |
| pgvector for exact keyword/typo search | MeiliSearch full-text |
| MeiliSearch for semantic similarity | pgvector cosine + hybrid |
| The pool, Kilo, or `free_lanes_chat` in a pipeline | OpenRouter chat, `claude_p_chat` for low volume, or a model you run yourself with no vendor egress — the others are paused |
| A model id or price as a code constant | The roster + env values; the provider's page for today's price |

---

## Related Rule Packs

- `25-data-postgres.md` — pgvector lives on `postgres-main`, indexing discipline. ⚠️ OPEN CONFLICT: 25 bans `psycopg2-binary` by name (its stated exception — `75-workers-jobs.md`'s parent monitor — is itself stale: `psycopg2` appears exactly once in all of 75, as "legacy-only" in a LISTEN sample (§ Worker Wake-Up), and § Parent Process DB Connections — the loops 25 names — uses `asyncpg`; so 25's ban may have no live exception at all) and the vendored `rag` module requires it (`rag/requirements.txt`, a psycopg2 connection in `search()`). Until 25's turn settles it, a RAG project's 25 Done When is knowingly waived for that one dependency — this sentence is NOT the waiver, and mixing drivers elsewhere stays banned. Its 2026-09-01 probe line ("`plpgsql` only") listed INSTALLED extensions in the default database; this pack's probe lists AVAILABLE ones — both are true.
- `58-resilience.md` — timeout/retry for MeiliSearch and pgvector calls
- `75-workers-jobs.md` — async ingestion/reindex via job queue
- `66-rag-chunking.md` — 12-rule Markdown chunking spec
- `62-using-subagents.md` — the paused runtimes the pipeline must not wire in
- fabrik-lib `rag/README.md` + `CUSTOMIZATION.md` — the module contract, env vars, gotchas, `UPSTREAM_FEEDBACK.md` for fixes

---

## Done When

- [ ] The fleet has `vector` available on `postgres-main` (probed, not assumed) — or, for the one legacy Supabase project, on its own instance — and `pgvector` + `pg_trgm` are created in the project's database; no external vector DB dependencies.
- [ ] HNSW indexes created with `m=16, ef_construction=64` on all embedding columns; `hnsw.iterative_scan` set on filtered searches.
- [ ] Embedding model from the auto-generated roster — not selected from agent training data; a candidate outside the roster (an EMPTY slot's role) carries its committed benchmark.
- [ ] ONE embedding model per pipeline — same model for ingest and query.
- [ ] Dimensions set to 1024 via API parameter and the returned length checked on every response (a raise, not an assert).
- [ ] EVERY AI call — metered or free — goes through OpenRouter, except the `claude_p_chat` subscription path for operator-facing or batch steps and a model YOU run where the text never leaves your boundary — a local Ollama, or a GPU worker you operate on rented hardware (`76-gpu-workers.md` splits the two and only one is excluded: its MANAGED-API category — Together, Groq, Fireworks, where the VENDOR runs the model (76 § Managed API Providers) — is NOT this carve-out and stays under the OpenRouter rule; its GPU-CLOUD category — RunPod, Modal, Vast.ai, where YOU run the server on their hardware (76 § GPU Cloud Providers) — IS. The test is WHO RUNS THE MODEL, never the client and never the URL's domain: 76 prescribes the same `AsyncOpenAI` + `base_url` swap for both (76 § Client-Side Pattern). Rented hardware still carries your text across a TRUST BOUNDARY — for a tenant-bound corpus § Hybrid Search's rule applies; 76's "Egress" columns are data-transfer BILLING, a different thing, and a `$0` there says nothing about confidentiality); no vendor SDKs, no direct free-tier keys; nothing wired to the paused pool/Kilo/free lanes.
- [ ] Every query derived from a user's words runs the three-leg hybrid with RRF fusion — pure vector only for query-free item-to-item similarity; reranking only after a measured lift.
- [ ] Chunks are 512–800 tokens (vector pipeline default) with 10–20% overlap per `66-rag-chunking.md`.
- [ ] Token counting uses a model-specific tokenizer (or `tiktoken` with the 15% buffer) — no heuristic `len/4`.
- [ ] Context budget capped at 85% of the per-model limit read from the provider — no hardcoded table.
- [ ] Chunk metadata includes document ID and sequence number for citation tracking, and the system prompt instructs the model to cite `chunk_id`.
- [ ] Reranking, if on: the golden set, the `rag.eval` command and its verbatim before/after output are committed under `docs/`, and the chunk-text egress is reviewed against the TIER actually pinned.
- [ ] Retrieval eval tests exist against a curated golden set (`rag.eval`, ≥ `recall@10` baseline pinned). Where a GENERATION step is under test, they include a faithfulness judge (both faithfulness metrics judge an ANSWER; a non-generative retrieval surface cannot tick them honestly, and `precision_at_k` divides by k, so 4-of-4 at k=10 scores 0.4 by design).
- [ ] Search feature declared via `shape.has_search_feature: true` — no manual index creation.
- [ ] `searchableAttributes`, `filterableAttributes`, `sortableAttributes` explicitly declared per index.
- [ ] Synonyms defined for domain terms; the instance's default ranking rules retained (never a hand-written list), `typo` never removed.
- [ ] Meili indexing and reindex run via background worker — API thread never blocked.
- [ ] Meili, ingest and embedding calls wrapped with timeout/retry per `58-resilience.md`; `search()` is NOT wrapped in an outer retry; a failed-open empty search is surfaced as degraded by the caller's own wrapper.

---

## Epic Decomposition (PLANNING layer — read before any RAG epic exists)

**Planning consequence of § Choosing:** if the Vision Summary's search use case is **pure catalog / doc-site /
faceted filtering / typo-tolerant keyword**, do **NOT** decompose into RAG epics at all — emit a **single
MeiliSearch-integration epic** instead. RAG is for *keyword + meaning fused* retrieval. Decomposing a catalog
search into embeddings / retriever / generator epics is the most expensive way to build a feature MeiliSearch
gives you in one ticket.

**Phase progression** — start at Phase 1; add a phase only when the product demands it:
Phase 0 fleet precondition (pgvector available on `postgres-main` — a fleet request, § Vector Storage) →
Phase 1 retrieval (embeddings + retriever) → Phase 2 + classifier/labels → Phase 3 + answer generator /
summarizer. Each phase is its own epic; each later phase depends on the one before.

> ### ⚠️ WHO CREATES THE pgvector EXTENSION AND THE HNSW INDEX — READ THIS
>
> **The registrar does NOT.** `shape.has_search_feature: true` provisions **MeiliSearch only**
> (`src/fabrik/drivers/meilisearch.py` — `SHAPE_FLAG = "has_search_feature"`; its mutation surface is two in-container `curl` calls over ssh — a POST to `/indexes`
> (`create_index`) and a DELETE (`delete_index`, the `--drop-data` path) — neither issuing SQL). Executed against the codebase: **`hnsw` appears in 0 of the hub's 80 tracked
> `src/*.py` files**, and no registrar issues `CREATE EXTENSION`. There is no shape flag for pgvector; do not look
> for one.
>
> So **every RAG epic MUST carry its own migration** creating the extension and the index — the vendored
> `rag/migration.sql` does both (`CREATE EXTENSION IF NOT EXISTS vector; … pg_trgm;` and the HNSW index at
> `m=16, ef_construction=64`) — run as a superuser, once per database (`specs/services/youtube.yaml` carries the run-once comment shape), **and only after the fleet has the
> package** (§ Vector Storage: today it does not). A planner that assumed the registrar owned this emitted a RAG
> pipeline with no index at all.
