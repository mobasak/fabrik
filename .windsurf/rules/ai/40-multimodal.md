---
activation: glob
globs: ["**/multimodal/**", "**/vqa/**", "**/vision-language/**", "**/image-captioning/**", "**/doc-understanding/**"]
description: Vision-Language & Multimodal AI (category 4) — combine text/image/audio/video understanding (Claude Opus 4.8, GPT-4o, Gemini 2.5 Pro, LLaVA). Visual QA, image captioning, document & video understanding. Kilo: 70 multimodal models.
trigger: glob
---
<!-- CONSUMER: Coding agents building multimodal features + Traycer (tech-plan)
     GOAL: Pick a model that natively handles the modalities present; Claude Opus 4.8 is the default.
     TRAYCER USAGE: Context File for multimodal / visual-QA / document-understanding tickets.
     AGENT USAGE: Default Claude Opus 4.8 (vision+language). Verify the model supports the exact modalities (image/video/audio) before committing. -->

# 4. Vision-Language & Multimodal AI

Last content verification: 2026-09-05

**Purpose:** Combine text, image, audio, and video understanding.

## Fabrik default
- **Claude Opus 4.8** for vision+language understanding (high-resolution vision, document understanding). GPT-4o / Gemini 2.5 Pro are alternatives — verify version + price first.

## Examples
Claude Opus 4.8, GPT-4o, Gemini 2.5 Pro, LLaVA, Kosmos-2.

## Gateway coverage

Both gateways carry the major multimodal frontier (Claude / GPT-4o / Gemini) at comparable prices — pick the cheaper rate per model from the bake-off browser. For `input.video`, check the `input.video` flag in either browser before picking.

<!-- GATEWAY_COUNTS:START — last-refreshed: 2026-09-05 (auto-managed by update_gateway_counts.py) -->
*Live gateway counts (active models, 2026-09-05 UTC; auto-refreshed from `kilo_agents.db`):*

vision-input across all gateways: **233**

Multimodal overlaps with Vision (category 2) — see the Audio/Vision tab in the bake-off browser for the audio-in subset.
<!-- GATEWAY_COUNTS:END -->

**Use cases:** image captioning, visual QA, document understanding, video analysis.

<!-- OPENROUTER_ROUTES:START — last-refreshed: 2026-09-05 (auto-managed by category_export_markdown.py) -->
*Auto-generated 2026-09-05 (UTC) by `category_route_mapper.py` → injected here by `category_export_markdown.py`. Edits between the markers will be overwritten on the next daily run.*

*No eligible models today — floors too strict or catalog too thin. See `cache/update.log` for details. Reason: No model satisfies category='multimodal' floors: min_quality_tier=1, min_context_window_k=1, require_vision=True, require_tools=True, require_reasoning=True, allow_free=False, stability_required=True, sort_key='input_cost_per_m ASC'*
<!-- OPENROUTER_ROUTES:END -->
