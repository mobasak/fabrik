---
activation: glob
globs: ["**/embeddings/**", "**/retrieval/**", "**/rag/**", "**/vector/**", "**/chunking/**", "**/ingest/**"]
description: Markdown chunking discipline — heading-based splits, chunk envelopes, overlap strategy, quality checks for RAG pipelines
trigger: glob
currency_pass: 2026-09-22
---
<!-- CONSUMER: Coding agents building search/RAG ingestion pipelines
     GOAL: Deterministic Markdown chunking for vector embedding and retrieval
     TRAYCER USAGE: Injects as Context File for any ticket involving document ingestion, search indexing, or RAG.
     AGENT USAGE: Follow the 12 rules when splitting documents for embedding. Co-activates with 65-rag-search.md. -->

# RAG-Optimized Markdown Chunking Rules

How to split documents into chunks for vector embedding and retrieval. Chunks must: (1) retrieve precisely, (2) fit the embedding model's input, (3) keep enough local context to answer, (4) preserve citations.

**Applies when:** building document ingestion, RAG pipelines, or knowledge base indexing. Projects with `shape.has_search_feature: true` also reference `65-rag-search.md` (that pack owns the shape flag gate and the search architecture; this pack owns the chunking spec).

**Before you chunk at all:** a corpus under roughly 200k tokens goes into the prompt whole — no RAG, no chunking (Anthropic's Contextual Retrieval note, 2024). Chunk when the corpus does not fit, not because a pipeline exists.

**Two stages, and the module is only the second.** The vendored fabrik-lib `rag` module's `chunk_text()` is the PLAINTEXT path — recursive paragraph → sentence splitting, token-bounded, sentence-boundary overlap, envelope metadata — and it parses no Markdown; `heading_path` is a breadcrumb the CALLER passes. For Markdown, **your heading-aware pre-pass** (§1, §5, §6; algorithm steps 1–4a) splits by headings and hands each section to `chunk_text(section, heading_path=[...])` for the size work (steps 4b–8). LangChain's `MarkdownHeaderTextSplitter` + a size splitter is the same shape off the shelf (claim `langchain-markdown-header-splitter`).

---

## 1. Chunk Boundaries

### Rule 1 — Chunk by headings first

Use Markdown headings as primary boundaries:
- `#` = document boundary
- `##` = section boundary (primary split point)
- `###` = subsection boundary (secondary split if section too large)

**Never split mid-section unless it exceeds max size.**

### Rule 2 — Preserve heading path in every chunk

Each chunk must carry its full breadcrumb: `Doc title > H2 > H3` — the module's `heading_path` list, passed per section.

Essential for relevance scoring and model grounding.

### Rule 3 — Keep atomic units intact

Never split inside:
- Tables
- Code blocks
- Checklists
- Numbered procedures
- YAML/JSON snippets
- Policy/rule lists where items cross-reference

If an atomic unit is too large, treat it as its own chunk with a context header (up to the embedding ceiling, § 2).

---

## 2. Chunk Size Targets

Count TOKENS, never characters — the module's `count_tokens()` (`cl100k_base`, an approximation for the default Qwen embedder) is the one ruler; "around four characters per token" is an OpenAI-tokenizer rule of thumb (claim `azure-chunking-overlap-guidance`), not a bound.

| Bound | Tokens | Module constant |
|---|---|---|
| **Target** (vector-embedding pipeline) | 512–800 | `TOKEN_TARGET_MAX` bounds the grouping (`chunk_text(target_max=…)` moves a project off it); `TOKEN_TARGET_MIN` is declared but never enforced — the only lower bound the module applies is the hard min |
| **Hard max** — your pre-pass splits above it; the module warns and caps merge/overlap growth at it | 1,200 | `TOKEN_HARD_MAX` |
| **Hard min** — merge with neighbour | 120 | `TOKEN_HARD_MIN` |
| **Embedding ceiling** | `RAG_EMBED_TOKEN_CEILING` (default 6800) | the module's only forced cut, on the token grid, unlogged (the pieces surface as hard-max warnings — except on a one-chunk doc, where the module returns before the warning loop). Holds only while `target_max` stays below it: the backstop runs only when the ceiling is under the hard max (`chunker.py`'s "Ceiling backstop" block after its step 4 — unnumbered), so a `target_max` raised above the ceiling emits un-embeddable chunks — raise the ceiling first, in the process ENV before `rag.chunker` is imported (module-scope read), then `target_max` |

**This file is the authoritative source for chunk sizes**; `65-rag-search.md` defers here. The bounds are the module's, not a vendor figure: the hard min exists because a fragment below it carries no answerable context, the hard max because an embedding of that much text over-compresses. The measured evidence points SMALLER for precision (claims `chroma-chunking-eval-sizes`, `chunk-size-multidataset-2025`); the 512–800 target buys answerable context at the cost of pinpoint precision. Move it only with a `rag.eval` before/after on a golden set (`65-rag-search.md` § Retrieval Quality Evaluation), never by thumb.

There is no separate "keyword" chunk size: the module's three retrieval legs (dense, `tsvector`, trigram) read the SAME `rag_chunks` row, and Meili stays keyword — its own `embedders`/`semanticRatio` path is banned, so it runs no second chunking pipeline (`65-rag-search.md` § Choosing).

---

## 3. Overlap Strategy

### Rule 4 — Overlap on semantic boundaries only

- 10–20% of chunk size (the module: 15%, whole sentences from the previous chunk's tail, skipped when it would breach the hard max — not a parameter; a different ratio is a mail to fabrik-lib with the eval attached), OR
- Last 1–2 paragraphs, OR
- Last 3–7 bullet items (if list-heavy)

Never overlap partial code blocks or partial table rows. Overlap is a continuity aid, not a retrieval gain — measured as neither helping nor harming retrieval, and it lowers token-level IoU (claims `late-chunking-jina-2024`, `chroma-chunking-eval-sizes`). Do not raise it to chase recall.

### Rule 5 — Carry-forward for procedures

For step-by-step sections: include last 1–2 steps of previous chunk at top of next chunk. Keeps procedural continuity.

---

## 4. Chunk Envelope (metadata per chunk)

### Required metadata — what the module writes

`Chunk.to_metadata()` → `rag_chunks.metadata` (JSONB):

```json
{
  "doc_id": "stable-identifier",
  "source_uri": "docs/reference/architecture.md",
  "heading_path": ["Architecture", "VPS", "Docker Setup"],
  "chunk_index": 3,
  "chunk_total": 12,
  "content_hash": "sha256-hex",
  "token_count": 640
}
```

`title`, `updated_at`, tags — anything else — go in the `metadata=` argument of `ingest_text()`, merged into every chunk's JSONB. Identity is NOT in the JSONB: the row's uniqueness key is the columns `(tenant_id, source_type, source_id, chunk_seq, content_hash)`; citations cite the row's `chunk_id` and map it back (`65-rag-search.md` § Citations & Source Attribution).

### Recommended chunk header (prepend to chunk text)

```md
<!-- doc: {doc_id} | path: Architecture > VPS > Docker Setup | uri: docs/reference/architecture.md | chunk: 4/12 -->
```

That is the module's shape (`Chunk.chunk_header`: `path:` is the breadcrumb, `uri:` the file, `doc:` the `doc_id`; `chunk:` is 1-BASED while the JSONB `chunk_index` is 0-based — the chunk above is `chunk_index: 3` of 12). Gives the model instant grounding without external metadata wiring. ⚠️ The module COMPUTES it but `ingest_text()` embeds the bare `c.content` and has no hook for it — to prepend, call `chunk_text()` yourself and write via `ingest_records()` with the envelope spread in — `{"text": c.chunk_header + "\n\n" + c.content, **c.to_metadata()}` — because `ingest_records()` stores a record's non-`text` keys as its JSONB and never calls `to_metadata()` for you; on that route the row's `content_hash` COLUMN hashes header+content while the JSONB's `content_hash` and `token_count` describe the bare content. `ingest_text()` is the no-header path. Add nothing beyond the header: it is embedded AND indexed into `tsv`. The measured form is Anthropic's Contextual Retrieval — a chunk-specific context sentence prepended before embedding (claim `anthropic-contextual-retrieval`); the breadcrumb is the zero-cost version, the LLM-written sentence the upgrade, measured like any other.

---

## 5. Markdown-Specific Splitting Rules

| Rule | Description |
|---|---|
| **Rule 6** | Split on paragraphs (blank lines), not line wraps |
| **Rule 7** | Keep list + intro sentence together in same chunk |
| **Rule 8** | Keep table + interpretation paragraph together |
| **Rule 9** | For code blocks: include heading path + 1–2 sentences of purpose + the code block |

---

## 6. Special Handling by Doc Type

| Doc type | Split by | Notes |
|---|---|---|
| **Specs/policies** | `##` sections | Keep "Definitions" near "Rules" if terms are referenced |
| **How-to/runbooks** | Procedure phases | Keep rollback steps separate and retrievable |
| **FAQs** | Per question (Q+A together) | Add tags: `tags: ["billing","refunds"]` |
| **API docs** | Per endpoint | Include request + response + error codes together |
| **Transcripts, OCR, scraped text** (no structure) | The module's plaintext path as-is | A punctuation-free run-on is hard-split at the embedding ceiling — expected; the pieces surface as hard-max warnings (none on a one-chunk doc) |

---

## 7. Retrieval Robustness

### Rule 10 — No orphan chunks

Every chunk must be interpretable without the previous chunk. If not, prepend a 2–4 line context summary (§ 4's contextual header is the measured form).

### Rule 11 — Normalize synonyms

In chunk header or first paragraph, include canonical names AND aliases:
- "Single Sign-On (SSO) / SAML"
- "Payment Intent (PI)"

### Rule 12 — Explicit key fields for structured data

If chunk contains configs or API fields:
```md
Fields: token, expires_in, scope
```
Improves keyword retrieval.

---

## 8. Chunking Algorithm (deterministic)

Steps 1–3, 4a, 4d's header and warning, and 7 are the caller's; 4b, 4c, 5, 6 and 8 are `chunk_text()` per section (its merge leaves an undersized chunk silently — no warning).

```
1. Parse Markdown → heading tree + paragraphs + lists + tables + code blocks
2. Collect any content between # title and first ## as a "preamble chunk" under the doc breadcrumb
3. Build initial chunks per ## section
4. If chunk > max:
   a. Split by ###
   b. If still too large, split by paragraph groups
   c. If still too large, split by list item groups (keep items intact) — sentences, in the module
   d. If a single atomic unit (table, code block) still exceeds max:
      emit it as its own chunk, prepend a context header, and log a warning
      (do NOT split inside the atomic unit — accept the oversize up to the embedding
      ceiling; past it the module cuts on the token grid, header-less and unlogged,
      because an un-embeddable chunk is worse than a cut one — and only while
      target_max stays below the ceiling, § 2)
5. Merge undersized chunks:
      For any chunk < 120 tokens, merge it into the adjacent sibling chunk under
      the same or parent heading. If the merge would breach max, leave the chunk
      as-is — the module does this SILENTLY; your pre-pass logs it. A merged chunk
      takes the shared parent breadcrumb as its heading_path (Rule 2) — re-parenting
      is the pre-pass's: chunk_text() stamps one heading_path on every chunk of a call.
6. Apply overlap (semantic boundary only)
7. Prepend chunk header
8. Compute content hash
9. Output: chunk text + metadata
```

**Two measured upgrades, both opt-in:** the contextual header (§ 4), and *late chunking* — embed the whole document with a long-context mean-pooling model, pool per chunk afterwards (claim `late-chunking-jina-2024`). Late chunking needs token-level embeddings a gateway `/embeddings` call never returns; it is reachable only with a model you run yourself (`65-rag-search.md` § Done When's carve-out) — an option, not a default. Semantic chunking is not one of the two: its compute is not repaid by consistent gains (claim `semantic-chunking-cost-2024`).

---

## 9. Quality Checks (automatable)

A chunk passes if:
- No broken code fences (open/close state parse — every opening ``` has a matching close)
- No partial tables (header + separator + rows intact)
- Contains heading path
- Within size bounds (120–1200 tokens)
- Does not start mid-sentence or mid-list-item
- Has at least one anchor term (topic keyword) in first 200 chars of body text (excluding the prepended chunk header comment)

The module runs only two size warnings (a one-chunk doc below the hard min; a chunk above the hard max) and a debug log for a mid-sentence start; the fence, table and anchor checks belong to your Markdown pre-pass — write them or say in the plan that you did not.

---

## Banned Patterns

| Pattern | Use Instead |
|---------|-------------|
| Splitting mid-code-block or mid-table | Keep atomic units intact (Rule 3) |
| Chunks without heading breadcrumbs | Prepend heading path to every chunk (Rule 2) |
| Overlapping partial code/tables | Overlap on semantic boundaries only (Rule 4) |
| Orphan chunks requiring prior context | Prepend 2–4 line context summary (Rule 10) |
| Chunks above 1,200 tokens | Split by ### then by paragraph groups |
| Chunks below 120 tokens | Merge with adjacent sibling (Algorithm step 5) |
| Sizing chunks in characters, or by a second tokenizer | Tokens, via the module's `count_tokens()` — one ruler |
| A chunk size changed by thumb | `rag.eval` before/after on a golden set, committed under `docs/` (overlap is not a parameter — see Rule 4) |
| A hand-rolled splitter beside the module's | The Markdown pre-pass + `chunk_text()`; a change wanted inside the module is a mail to fabrik-lib |

---

## Related Rule Packs

- `65-rag-search.md` — parent pack: MeiliSearch vs pgvector decision, hybrid search, embedding models, token budgeting, citations
- `25-data-postgres.md` — pgvector lives on `postgres-main`
- `75-workers-jobs.md` — the job-queue discipline ingestion/chunking runs under (75 states the queue rules, not RAG)

---

## Done When

- [ ] Markdown is split by `##` headings first, `###` as secondary split, in a pre-pass that hands each section to `chunk_text()` with its `heading_path`.
- [ ] Every chunk carries its heading breadcrumb path.
- [ ] No chunk splits inside tables, code blocks, checklists, or numbered procedures.
- [ ] Chunk sizes within 120–1,200 tokens (target 512–800 for the vector pipeline), counted in tokens by the module — a structure-free corpus on the plaintext path (§ 6) is the named exception; record its warning count instead.
- [ ] Overlap is 10–20%, on semantic boundaries only (the module's 15%), and was not raised to chase recall.
- [ ] Chunk envelope metadata includes `doc_id`, `source_uri`, `heading_path`, `chunk_index`, `content_hash`; citations resolve through the row's identity columns.
- [ ] The chunk header is actually prepended before embedding (the module does not do it), or the plan says why not.
- [ ] Quality checks pass: no broken fences, no partial tables, heading path present, size within bounds.
- [ ] Ingestion runs via background worker queue — never on the API thread.
