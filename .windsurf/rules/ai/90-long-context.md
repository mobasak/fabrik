---
activation: glob
globs: ["**/long-context/**", "**/codebase-analysis/**", "**/document-qa/**", "**/long-document/**"]
description: Long-Context AI (category 16) — documents, codebases and conversations too long for an ordinary prompt. Model choice is ai/00's (Claude by alias); the advertised window is not the usable window; curate before you stuff, put the documents first and the question last; retrieval beats a full context on cost; compact long runs early; analyse codebases by agentic search.
trigger: glob
currency_pass: 2026-10-03
---
<!-- CONSUMER: Coding agents building long-document, document-QA, codebase-analysis or long-conversation features
     GOAL: Send the model the smallest context that answers the question, and size every long input against what the
     model can actually use, not what its window advertises.
     AGENT USAGE: Model choice is ai/00-ai-model-selection.md (Claude by alias); retrieval is core/65-rag-search.md.
     Record a project's choice and the rejected alternative in project.yaml (`ai_category`, `ai_subcategory`,
     `ai_tools`), as ai/00's selection workflow says. -->

# 16. Long-Context AI

Last content verification: 2026-10-03

**Purpose:** Process documents, codebases and conversations that are too long for an ordinary prompt.

## Fabrik defaults

- **Model choice is ai/00's, and this pack names no model generation.** Select Claude by alias: `opus` for
  long-context work, `fable` only when `opus` measurably falls short, as `ai/00-ai-model-selection.md` sets. `opus`,
  `sonnet` and `fable` run a 1M-token window by default; `haiku`'s is smaller. A window size is never the reason to
  pick a model; the measured result on the project's own task at the length it will run is.
- **The advertised window is not the usable window.** Accuracy falls as input grows, well inside the advertised
  length: Chroma's study of 18 models found performance "increasingly unreliable as input length grows" in every
  experiment; on NoLiMa, 11 of 13 models that claim 128K tokens fell below half their short-input score at 32K; and
  length alone cost about 14% to 85% of accuracy even when the evidence was retrieved perfectly. Similar distracting
  passages make it worse. So every token is a cost to accuracy, not just to the bill: measure the task at the input
  length you will actually send, and send less when the score drops.
- **Curate before you stuff, and order what you send.** The working rule from Anthropic's own guidance is the smallest
  set of high-signal tokens that does the job. For an input over about 20,000 tokens: put the documents at the top and
  the question last, which Anthropic measured at up to 30% better on complex multi-document input and Google
  recommends for Gemini (OpenAI's guidance for its own models is to put the instructions both before and after the
  context); wrap each document in its own tags with its source; and ask the model to quote the relevant passages
  before it answers, which turns a long-context task back into a short one.
- **Retrieval beats a full context on cost; measure which wins on accuracy.** When the budget allows, a full long
  context scored higher on the models tested, though the winner flips with the task and the retriever, and retrieval
  costs a fraction of it (one 2026 study of two small models in one domain: 26 times fewer tokens per query for a few
  points less correctness; another: costs near 100 times higher at 300 pages, where retrieval's own accuracy also
  fell). Default to retrieval (`core/65-rag-search.md`, fabrik-lib's `rag` module) when the corpus is more than one
  document or the same corpus answers many questions. Send the whole document when it is one document read once, or
  when the answer needs all of it (a summary, a cross-section comparison). Decide on the project's own questions,
  scored both ways.
- **Long conversations and agent runs: compact early, keep durable rules out of the conversation.** Response quality
  degrades as a conversation grows, so keep the active context small. Clear old tool results, compact before the
  window fills, keep rules that must survive compaction in files (`CLAUDE.md`, a memory file), and push research into
  subagents that return summaries. A fresh session with a better prompt beats a long one carrying corrections. In
  Claude Code, a model with a native 1M window compacts only at about 967K tokens by default; set `autoCompactWindow`
  in `settings.json` to compact far earlier, or `CLAUDE_CODE_AUTO_COMPACT_WINDOW` for headless `claude -p` runs, which
  overrides `/autocompact`, `--autocompact` and the setting (a `/autocompact` value is saved per model and overrides
  the setting). On the Messages API, server-side compaction and tool-result clearing do the same job. Clearing tool
  results invalidates the cached prompt prefix, so it trades against prompt caching, and cached tokens still fill the
  window.
- **Analyse a codebase by agentic search, not by loading it whole.** Claude Code finds code with glob and grep and
  reads files when it needs them, and its team dropped a local vector index because agentic search worked better with
  fewer security, privacy, staleness and reliability problems. A semantic index can still add accuracy on large
  codebases — semantic search beside grep raised Cursor's average accuracy (+12.5%) — so add one only when a test on
  the project shows the lift.
- **Pay once for a long prefix.** When the same long document or system prompt goes out more than once, cache it. On
  Claude a cache read costs a tenth of the input price (less on the newest top models), a five-minute write a quarter
  more than it and a one-hour write twice, so caching pays after one read on the five-minute cache and after two on
  the one-hour cache; a prompt below the model's minimum length is silently not cached, which shows as zero
  cache-write and zero cache-read tokens on the call. Claude bills its whole 1M window at the standard per-token rate.
  Gemini's Pro tier and OpenAI's flagship models charge a higher rate for every token once a prompt passes a size step
  (200K and 272K tokens respectively), so check the step before sending them a long prompt. Offline jobs go through
  the batch APIs at half price. Size input in tokens with the provider's own counter, never in words: the newest
  Claude tokenizer produces about 30% more tokens for the same text.

**Anti-pattern:** picking a model for its window size; pasting a whole repository or document set into one prompt
because it fits; the question at the top of a long prompt; a long agent run that never compacts; treating a perfect
needle-in-a-haystack score as proof the model reasons over the whole context.

## The fleet today

No fleet repository has a directory matching this pack's globs, and none pins a 1M-window model or sets up prompt
caching itself (43 repositories, 7,627 source files read on 2026-10-03). Long inputs go to Claude through fabrik-lib's
`llm-dispatch` and `claude -p` by alias, which surfaces the CLI's usage figures, carrying the cache read and write
  token counts today; retrieval goes
through fabrik-lib's `rag` module, under `core/65-rag-search.md`.

## Subcategories

- **Benchmarks beyond a single needle:** NoLiMa, RULER, LongBench, Fiction.LiveBench, Michelangelo's latent structure
  queries, multi-needle reference resolution. A single needle-in-a-haystack pass is not evidence of long-context
  reasoning.
- **Context management:** compaction, tool-result clearing, memory files, subagents, prompt caching.
- **Models:** Claude by alias (`ai/00-ai-model-selection.md`); Gemini and OpenAI's flagship models (1M-class windows,
  each with a long-prompt price step); open-weight long-context models — DeepSeek's (MIT licence, 1M window), Qwen's
  (Apache licence; 1M only by YaRN extension, which can cost accuracy on short text), Meta's Llama (community licence;
  up to 10M tokens), Kimi's (a modified MIT licence; 1M window), and MiniMax's (non-commercial without MiniMax's
  written authorisation). Read the exact licence before use.

**Use cases:** codebase analysis, long-document question answering, contract and report review, book-length
summarisation, long-running agent sessions.

<!-- OPENROUTER_ROUTES:START — last-refreshed: 2026-09-07 (auto-managed by category_export_markdown.py) -->
*Auto-generated 2026-09-07 (UTC) by `category_route_mapper.py` → injected here by `category_export_markdown.py`. Edits between the markers will be overwritten on the next daily run.*

*No eligible models today — floors too strict or catalog too thin. See `cache/update.log` for details. Reason: No model satisfies category='long-context' floors: min_quality_tier=1, min_context_window_k=200, require_vision=False, require_tools=False, require_reasoning=False, allow_free=True, stability_required=False, sort_key='context_window_k DESC'*
<!-- OPENROUTER_ROUTES:END -->
