---
activation: glob
globs: ["**/vision/**", "**/image/**", "**/images/**", "**/imagegen/**", "**/img/**", "**/ocr/**", "**/video-gen/**"]
description: Vision AI (category 2) — image gen (Recraft v4.1 = Fabrik default for branded/vector/illustration, FLUX/BFL for photoreal, Replicate as host/fallback), video gen, object/scene recognition, OCR, face/pose. Kilo: 70 vision models.
trigger: glob
---
<!-- CONSUMER: Coding agents building image/vision features + Traycer (tech-plan)
     GOAL: Recraft for branded/illustration, FLUX for photoreal; don't reach for Midjourney/DALL·E by default.
     TRAYCER USAGE: Context File for image/vision tickets.
     AGENT USAGE: Branded/vector → Recraft v4.1. Photoreal → FLUX (BFL_API_KEY). Replicate = model host/fallback. Document choice in project.yaml. -->

# 2. Vision AI

Last content verification: 2026-06-27

**Purpose:** Interpret or generate images/video.

## Fabrik defaults
- **Branded / vector / illustration → Recraft v4.1** (flat/vector/illustration, style consistency; Fabrik default via BFL-style API).
- **Photoreal → FLUX (BFL)** — FLUX.1 / FLUX.2, owned `BFL_API_KEY`.
- **Model host / fallback → Replicate.**

## Subcategories
- **Image Generation:** Recraft (v4.1), FLUX (BFL), Replicate (host/fallback), Midjourney, DALL·E, Stable Diffusion
- **Video Generation:** Runway, Pika, Synthesia
- **3D / mesh generation:** see `25-3d-generation.md` — zero-edit asset pipeline (Meshy / Tripo / Rodin / TRELLIS 2)
- **Object/Scene Recognition:** YOLOv8, Detectron2, Google Vision API
- **OCR (text from images):** Tesseract, AWS Textract
- **Face/Pose Estimation:** MediaPipe, OpenPose

## Kilo coverage
✅ 70 models with `input.image`. Free: `giga-potato`. Paid: `google/gemma-3-27b-it` ($0.03/1M). Note: Kilo models do vision *understanding* — for image *generation*, use Recraft/FLUX.

**Use cases:** content creation, surveillance, document processing.

<!-- OPENROUTER_ROUTES:START — last-refreshed: 2026-06-27 (auto-managed by category_export_markdown.py) -->
*Auto-generated 2026-06-27 (UTC) by `category_route_mapper.py` → injected here by `category_export_markdown.py`. Edits between the markers will be overwritten on the next daily run.*

| Priority | OpenRouter ID | Cost ($/M in) | Context | Status |
|---|---|---|---|---|
| P1 | `openai/gpt-5-nano` | $0.05 | 400k | GA |
| P2 | `google/gemma-3-12b-it` | $0.05 | 131k | GA |

To consume via a Fabrik spec: `llm_provider: openrouter` + `llm_model: <P1 id>`. Fallback chain via the OpenRouter `models: [P1, P2, P3]` request parameter.
<!-- OPENROUTER_ROUTES:END -->
