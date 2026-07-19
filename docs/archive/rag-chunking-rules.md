# RAG-Optimized Markdown Chunking Rules

How to split Markdown documents into chunks for vector embedding and retrieval. Chunks must: (1) retrieve precisely, (2) fit context windows, (3) keep enough local context to answer, (4) preserve citations.

> **Use when:** building search features with Meilisearch, implementing RAG pipelines, creating knowledge bases, or any project with `shape.has_search_feature: true`.

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
| **Tokens** | 300–800 | 1,200 | 120–200 |
| **Characters** | 2,000–5,000 | 8,000 | 800 |

Beyond 1,200 tokens retrieval precision drops. Below 120 tokens context is lost.

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
2. Build initial chunks per ## section
3. If chunk > max:
   a. Split by ###
   b. If still too large, split by paragraph groups
   c. If still too large, split by list item groups (keep items intact)
4. Apply overlap (semantic boundary only)
5. Prepend chunk header
6. Compute content hash
7. Output: chunk text + metadata
```

---

## 9. Quality Checks (automatable)

A chunk passes if:
- No broken code fences (``` count is even)
- No partial tables (header + separator + rows intact)
- Contains heading path
- Within size bounds (120–1200 tokens)
- Does not start mid-sentence or mid-list-item
- Has at least one anchor term (topic keyword) in first 200 chars

---

## When to Apply These Rules

- `shape.has_search_feature: true` → Meilisearch index receives chunked docs
- Any RAG pipeline (retrieval-augmented generation)
- Knowledge base ingestion (Obsidian, Notion exports)
- Documentation search features
