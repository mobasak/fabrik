---
activation: glob
globs: ["**/llm/**", "**/nlp/**", "**/text/**", "**/translation/**", "**/summariz*/**", "**/embeddings/**", "**/embedding/**"]
description: Language AI (category 3) — LLM work, translation and summarization on Claude through `claude -p` on the subscription first; embeddings through OpenRouter into pgvector on postgres-main (dedicated vector DBs banned); a dedicated MT engine only when a bake-off says so, DeepL last; licence traps named.
trigger: glob
currency_pass: 2026-10-02
---
<!-- CONSUMER: Coding agents building text, LLM, translation, summarization or embedding features.
     GOAL: Claude first for anything it can do; pgvector the only vector store; a dedicated engine only on measured need.
     AGENT USAGE: LLM, translation, summarization → `claude -p` by alias (ai/00). Embeddings and retrieval →
     core/65-rag-search.md and core/66-rag-chunking.md. Model choice across categories is ai/00-ai-model-selection.md;
     record a project's choice and the rejected alternative in project.yaml (`ai_category`, `ai_subcategory`, `ai_tools`),
     as ai/00's selection workflow says. -->

# 3. Language AI

Last content verification: 2026-10-02

**Purpose:** Process and generate text.

## Fabrik defaults

- **LLM → Claude through `claude -p`** on the Max subscription, selected by alias (ai/00-ai-model-selection.md
  § Claude subscription first). In-code calls go through fabrik-lib's `llm-dispatch` and start at `haiku`, escalating
  to `sonnet`, `opus` and `fable` only on measured failure; interactive and agentic work defaults to `opus`. A non-Claude
  LLM goes through ai/00's metered route only when Claude cannot serve the task.
- **Summarization and extraction → Claude**, with `llm-dispatch`'s schema-enforced JSON (`json_schema`) rather than
  prompt-and-parse.
- **Translation → Claude first**, as ai/00 says, through fabrik-lib's `mt-router`. Its Claude tier (Opus, the module's
  own measured choice) runs only on the context path: always pass product context, or set `MT_CLAUDE_PLAIN=1`, or a plain
  call goes straight to the metered engines. Behind Claude sit DeepL or Azure (when their keys are set), then a
  per-language chain across OpenRouter, DashScope and SiliconFlow. Claude first rests on ai/00's subscription cost rule;
  the WMT shared task of 2025 showed frontier LLMs competitive with dedicated MT in human evaluation, with the winner
  varying by language pair. So move a pair to another engine only when a bake-off shows Claude misses that pair's
  quality or cost bar, and record the result in the project's decision ledger and project.yaml. DeepL comes last in that
  choice: the operator rejected its translations as not context-aware enough (D-505).
- **Embeddings and vector search → pgvector on `postgres-main`**, embeddings through OpenRouter's `/embeddings` via
  fabrik-lib's `rag` module, the model an env value (`RAG_EMBEDDING_MODEL`). core/65-rag-search.md owns the binding
  model roster, the dimensions, the index — and the fact that `postgres-main` does not carry the `vector` extension yet,
  so read it before planning. Claude has no embedding model (Anthropic's docs point to Voyage AI). Supabase is retired as
  a runtime target.
- **Dedicated vector databases (Pinecone, Qdrant, Weaviate, Milvus) are BANNED** — they add network latency, a second
  copy to keep in sync, another backup and a bill, where pgvector runs inside the Postgres the fleet already operates
  once its image carries the extension. The ban rests on that operating cost; no neutral benchmark of stock pgvector
  against them at this fleet's scale exists.

**Licence trap — open weights are not commercial weights.** Meta's NLLB (No Language Left Behind) and SeamlessM4T
translation weights are CC-BY-NC-4.0 (NLLB's card calls it a research model, not for production); neither is a Fabrik
default.

## Subcategories

- **Large language models:** Claude (the default, above); OpenAI's GPT family, Google Gemini, xAI Grok and Mistral
  through OpenRouter — compare them with ai/00's selection docs and vendor-access catalog (§ Selection MDs) before
  choosing one; the bake-off browser is hub-only.
- **Embeddings:** core/65's roster is binding. Candidates for a benchmark against it: Qwen's open embedding models
  (Apache-2.0; the cheapest route on OpenRouter, about $0.01 per million tokens), OpenAI's text-embedding models and
  Google's Gemini embeddings (both on OpenRouter), Voyage AI (the partner Anthropic's docs recommend; now part of
  MongoDB, its API unchanged) and Cohere Embed (direct). The store is always pgvector.
- **Translation:** Claude through `mt-router` (above). For a pair a bake-off moves off Claude, try an engine that takes
  context first — another LLM through OpenRouter, or Qwen-MT on DashScope (its flash tier; the turbo tier is no longer
  updated) — then the managed engines: Azure AI Translator (about $10 per million characters, 2 million a month free on
  its free resource) and Google Cloud Translation (about $20 per million characters after 500,000 free a month; needs a
  Google Cloud signup, which the vendor-access catalog lists as not set up). DeepL last, on the operator's ruling above;
  its API Free and Pro plans are closed to new customers (a new account gets a one-time 1 million characters, then the
  Growth plan), and its next-gen model is opt-in (`model_type=quality_optimized`, listed for the paid plans) — which
  `mt-router` does not send today.
- **Summarization and extraction:** Claude, above. Cohere's summarize endpoint is legacy and unmaintained.

## Gateway coverage

LLM work, translation and summarization run on Claude through `claude -p`, not a metered gateway (ai/00). A metered
model through OpenRouter, or a dedicated MT engine, is the fallback only when Claude measurably falls short or a call
cannot use the subscription; the counts below inventory that fallback (their sweet-spot line still names Qwen-MT's
frozen turbo tier — the generator's text, not this pack's).

<!-- GATEWAY_COUNTS:START — last-refreshed: 2026-09-07 (auto-managed by update_gateway_counts.py) -->
*Live gateway counts (active models, 2026-09-07 UTC; auto-refreshed from `kilo_agents.db`):*

language-tagged (any gateway): **0**
translation-scored (any gateway): **9**

Sweet-spot dedicated MT: `qwen-mt-turbo` via DashScope (top-3 on FR/PT/DE/ID/AR, weaker on HU/RO/UR/KO; see the Translation tab in the bake-off browser).
<!-- GATEWAY_COUNTS:END -->

**Use cases:** chatbots, content generation, search, translation.

**Anti-pattern:** standing up a dedicated vector DB when pgvector is already on the project's Postgres.

<!-- OPENROUTER_ROUTES:START — last-refreshed: 2026-09-07 (auto-managed by category_export_markdown.py) -->
*Auto-generated 2026-09-07 (UTC) by `category_route_mapper.py` → injected here by `category_export_markdown.py`. Edits between the markers will be overwritten on the next daily run.*

*No eligible models today — floors too strict or catalog too thin. See `cache/update.log` for details. Reason: No model satisfies category='language' floors: min_quality_tier=2, min_context_window_k=32, require_vision=False, require_tools=False, require_reasoning=False, allow_free=True, stability_required=False, sort_key='input_cost_per_m ASC'*
<!-- OPENROUTER_ROUTES:END -->
