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

Last content verification: 2026-07-31

**Purpose:** Process extremely long documents, codebases, or conversations.

## Fabrik default
- **Claude Opus 4.8 (1M)** for long-context work; **Claude Fable 5 (1M)** for the most demanding long-horizon reasoning/agentic runs.

## Examples
Claude Opus 4.8 (1M), Claude Fable 5 (1M), Gemini 2.5 Pro (1M), GPT-4o (128K).

**Use cases:** codebase analysis, book summarization, long-document QA, multi-file reasoning.

<!-- OPENROUTER_ROUTES:START — last-refreshed: 2026-07-31 (auto-managed by category_export_markdown.py) -->
*Auto-generated 2026-07-31 (UTC) by `category_route_mapper.py` → injected here by `category_export_markdown.py`. Edits between the markers will be overwritten on the next daily run.*

| Priority | OpenRouter ID | Cost ($/M in) | Context | Status |
|---|---|---|---|---|
| P1 | `x-ai/grok-4.20` | $1.25 | 2000k | GA |
| P2 | `openrouter/auto` | free | 2000k | free |

To consume via a Fabrik spec: `llm_provider: openrouter` + `llm_model: <P1 id>`. Fallback chain via the OpenRouter `models: [P1, P2, P3]` request parameter.
<!-- OPENROUTER_ROUTES:END -->
