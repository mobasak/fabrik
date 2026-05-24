---
activation: glob
globs: ["**/embeddings/**", "**/retrieval/**", "**/rag/**", "**/vector/**", "**/chunking/**", "**/ingest/**"]
description: Markdown chunking discipline — heading-based splits, chunk envelopes, overlap strategy, quality checks for RAG pipelines
trigger: glob
---
<!-- CONSUMER: Coding agents building search/RAG ingestion pipelines
     GOAL: Deterministic Markdown chunking for vector embedding and retrieval
     TRAYCER USAGE: Injects as Context File for any ticket involving document ingestion, search indexing, or RAG.
     AGENT USAGE: Follow the 12 rules when splitting documents for embedding. Co-activates with 65-rag-search.md. -->

# RAG-Optimized Markdown Chunking Rules

How to split Markdown documents into chunks for vector embedding and retrieval. Chunks must: (1) retrieve precisely, (2) fit context windows, (3) keep enough local context to answer, (4) preserve citations.

**Applies when:** building document ingestion, RAG pipelines, or knowledge base indexing. Projects with `shape.has_search_feature: true` should also reference `65-rag-search.md` for the full search architecture (that pack owns the shape flag gate; this pack owns the chunking spec).

---

## 1. Chunk Boundaries

### Rule 1 — Chunk by headings first

Use Markdown headings as primary boundaries:
- `#` = document boundary
- `##` = section boundary (primary split point)
- `###` = subsection boundary (secondary split if section too large)

**Never split mid-section unless it exceeds max size.**

### Rule 2 — Preserve heading path in every chunk

Each chunk must carry its full breadcrumb: `Doc title > H2 > H3`

Essential for relevance scoring and model grounding.

### Rule 3 — Keep atomic units intact

Never split inside:
- Tables
- Code blocks
- Checklists
- Numbered procedures
- YAML/JSON snippets
- Policy/rule lists where items cross-reference

If an atomic unit is too large, treat it as its own chunk with a context header.

---

## 2. Chunk Size Targets

| Metric | Target | Hard max | Minimum |
|---|---|---|---|
| **Tokens** | 300–800 | 1,200 | 120 |
| **Characters** | 2,000–5,000 | 8,000 | 800 |

Beyond 1,200 tokens retrieval precision drops. Below 120 tokens context is lost.

**Alignment with `65-rag-search.md`:** that pack specifies 512–1024 tokens for pgvector chunks. The ranges overlap — use the higher end (512–800) for vector embedding, the lower end (300–500) for pure keyword retrieval.

---

## 3. Overlap Strategy

### Rule 4 — Overlap on semantic boundaries only

- 10–20% of chunk size, OR
- Last 1–2 paragraphs, OR
- Last 3–7 bullet items (if list-heavy)

Never overlap partial code blocks or partial table rows.

### Rule 5 — Carry-forward for procedures

For step-by-step sections: include last 1–2 steps of previous chunk at top of next chunk. Keeps procedural continuity.

---

## 4. Chunk Envelope (metadata per chunk)

### Required metadata

```json
{
  "doc_id": "stable-identifier",
  "source_uri": "docs/reference/architecture.md",
  "title": "System Architecture",
  "heading_path": ["Architecture", "VPS", "Docker Setup"],
  "chunk_index": 3,
  "chunk_total": 12,
  "content_hash": "sha256:abc123...",
  "updated_at": "2026-05-21"
}
```

### Recommended chunk header (prepend to chunk text)

```md
<!-- doc: System Architecture | path: docs/reference/architecture.md | heading: Architecture > VPS > Docker Setup | chunk: 3/12 -->
```

Gives the model instant grounding without external metadata wiring.

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

---

## 7. Retrieval Robustness

### Rule 10 — No orphan chunks

Every chunk must be interpretable without the previous chunk. If not, prepend a 2–4 line context summary.

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

```
1. Parse Markdown → heading tree + paragraphs + lists + tables + code blocks
2. Collect any content between # title and first ## as a "preamble chunk" under the doc breadcrumb
3. Build initial chunks per ## section
4. If chunk > max:
   a. Split by ###
   b. If still too large, split by paragraph groups
   c. If still too large, split by list item groups (keep items intact)
   d. If a single atomic unit (table, code block) still exceeds max:
      emit it as its own chunk, prepend a context header, and log a warning
      (do NOT split inside the atomic unit — accept the oversize)
5. Merge undersized chunks:
      For any chunk < 120 tokens, merge it into the adjacent sibling chunk under
      the same or parent heading. If the merge would breach max, leave the chunk
      as-is and log a warning. A merged chunk takes the shared parent breadcrumb
      as its heading_path (Rule 2).
6. Apply overlap (semantic boundary only)
7. Prepend chunk header
8. Compute content hash
9. Output: chunk text + metadata
```

---

## 9. Quality Checks (automatable)

A chunk passes if:
- No broken code fences (open/close state parse — every opening ``` has a matching close)
- No partial tables (header + separator + rows intact)
- Contains heading path
- Within size bounds (120–1200 tokens)
- Does not start mid-sentence or mid-list-item
- Has at least one anchor term (topic keyword) in first 200 chars of body text (excluding the prepended chunk header comment)

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

---

## Related Rule Packs

- `65-rag-search.md` — parent pack: MeiliSearch vs pgvector decision, hybrid search, embedding models, token budgeting, citations
- `25-data-postgres.md` — pgvector lives on `postgres-main`
- `75-workers-jobs.md` — async ingestion/chunking via job queue

---

## Done When

- [ ] Chunks split by `##` headings first, `###` as secondary split.
- [ ] Every chunk carries its heading breadcrumb path.
- [ ] No chunk splits inside tables, code blocks, checklists, or numbered procedures.
- [ ] Chunk sizes within 120–1,200 tokens (target 300–800).
- [ ] Overlap is 10–20%, on semantic boundaries only.
- [ ] Chunk envelope metadata includes `doc_id`, `source_uri`, `heading_path`, `chunk_index`, `content_hash`.
- [ ] Quality checks pass: no broken fences, no partial tables, heading path present, size within bounds.
- [ ] Ingestion runs via background worker queue — never on the API thread.
