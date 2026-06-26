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

**Purpose:** Combine text, image, audio, and video understanding.

## Fabrik default
- **Claude Opus 4.8** for vision+language understanding (high-resolution vision, document understanding). GPT-4o / Gemini 2.5 Pro are alternatives — verify version + price first.

## Examples
Claude Opus 4.8, GPT-4o, Gemini 2.5 Pro, LLaVA, Kosmos-2.

## Kilo coverage
✅ 70 models with image input. Free: `qwen/qwen3-vl-235b-thinking`. Paid: `bytedance-seed/seed-1.6-flash` ($0.07/1M). For `input.video`, only 19 models qualify — check the `input.video` flag.

**Use cases:** image captioning, visual QA, document understanding, video analysis.
