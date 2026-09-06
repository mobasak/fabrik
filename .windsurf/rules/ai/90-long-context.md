---
activation: glob
globs: ["**/long-context/**", "**/codebase-analysis/**", "**/document-qa/**", "**/long-document/**"]
description: Long-Context AI (category 16) — process extremely long documents, codebases, or conversations. Claude Opus 4.8 (1M), Claude Fable 5 (1M), Gemini 2.5 Pro (1M), GPT-4o (128K).
trigger: glob
---
<!-- CONSUMER: Coding agents building long-document / codebase-analysis features + Traycer (tech-plan)
     GOAL: Pick a genuine long-context model (1M class) for whole-codebase or book-length input.
     TRAYCER USAGE: Context File for long-document QA / codebase-analysis / multi-file-reasoning tickets.
     AGENT USAGE: Default Claude Opus 4.8 (1M) or Fable 5 (1M) for the most demanding long-horizon work. Don't chunk-and-lose context when a 1M model fits. -->

# 16. Long-Context AI

Last content verification: 2026-09-06

**Purpose:** Process extremely long documents, codebases, or conversations.

## Fabrik default
- **Claude Opus 4.8 (1M)** for long-context work; **Claude Fable 5 (1M)** for the most demanding long-horizon reasoning/agentic runs.

## Examples
Claude Opus 4.8 (1M), Claude Fable 5 (1M), Gemini 2.5 Pro (1M), GPT-4o (128K).

**Use cases:** codebase analysis, book summarization, long-document QA, multi-file reasoning.

<!-- OPENROUTER_ROUTES:START — last-refreshed: 2026-09-06 (auto-managed by category_export_markdown.py) -->
*Auto-generated 2026-09-06 (UTC) by `category_route_mapper.py` → injected here by `category_export_markdown.py`. Edits between the markers will be overwritten on the next daily run.*

*No eligible models today — floors too strict or catalog too thin. See `cache/update.log` for details. Reason: No model satisfies category='long-context' floors: min_quality_tier=1, min_context_window_k=200, require_vision=False, require_tools=False, require_reasoning=False, allow_free=True, stability_required=False, sort_key='context_window_k DESC'*
<!-- OPENROUTER_ROUTES:END -->
