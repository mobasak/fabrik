---
activation: glob
globs: ["**/vision/**", "**/image/**", "**/images/**", "**/imagegen/**", "**/img/**", "**/ocr/**", "**/video-gen/**"]
description: Vision AI (category 2) — image gen (Recraft v4.1 for branded/recurring-style/vector, FLUX-schnell for bulk illustration, FLUX/BFL for photoreal, Replicate as host/fallback), video gen, object/scene recognition, OCR, face/pose. Kilo: 70 vision models.
trigger: glob
---
<!-- CONSUMER: Coding agents building image/vision features + Traycer (tech-plan)
     GOAL: Recraft for branded/recurring-style; FLUX-schnell for bulk/one-off illustration; FLUX for photoreal. Don't reach for Midjourney/DALL·E by default.
     TRAYCER USAGE: Context File for image/vision tickets.
     AGENT USAGE: Branded/recurring-style/vector → Recraft v4.1. Bulk/one-off illustration → FLUX-schnell. Photoreal → FLUX (BFL_API_KEY). Replicate = model host/fallback. Document choice in project.yaml. -->

# 2. Vision AI

Last content verification: 2026-08-18

**Purpose:** Interpret or generate images/video.

## Fabrik defaults
- **Branded / recurring-style / vector → Recraft v4.1** — logos, brand identity, mascots,
  themed sets where style consistency across images matters, or SVG scalability is needed
  (~$0.04/img; the style-id premium only pays off when images must look like a family).
- **Bulk / low-personality illustration → FLUX-schnell (BFL/Replicate)** — vocabulary cards,
  icons, one-off concrete-noun art (apple, tree, canteen) where per-image style variation is
  irrelevant or even helpful. ~$0.003/img, ~10× cheaper. DO NOT default bulk illustration to
  Recraft just because it's "illustration" — weigh count + style-consistency need first.
- **Photoreal → FLUX (BFL)** — FLUX.1 / FLUX.2, owned `BFL_API_KEY`.
- **Model host / fallback → Replicate.**

## Subcategories

⚠️ **A vendor NAMED here is not a vendor we can CALL.** These lists say what exists in each lane; `docs/reference/ai-media-generation-provider-map.md` says what is reachable with keys the fleet holds, and the two drift apart silently — a name here with no key is a dead end that reads like a recommendation. Check the reach map before designing around any vendor below.
- **Image Generation:** Recraft (v4.1), FLUX (BFL), Replicate (host/fallback), Midjourney, DALL·E, Stable Diffusion
- **Video Generation:** see `docs/reference/ai-media-generation-provider-map.md` § VIDEO — generation for what is actually REACHABLE with keys we hold — the reach map is the ONLY list of live routes, and this pack deliberately does not copy it (a copy is exactly the drift the warning above describes). As of 2026-09-05 the map named eleven reachable routes via WaveSpeed + fal + Gemini/OpenAI keys; **Runway and Synthesia were add-key — not callable**, and Pika reachable only through an aggregator. This line previously named exactly those three and nothing else, so the pack's entire video guidance pointed at three dead ends while omitting eleven live routes (iterative_image_editor, `01M1KN5NAXBJW7PD7A01F2NPB4`).
- **3D / mesh generation:** see `25-3d-generation.md` — zero-edit asset pipeline (Meshy / Tripo / Rodin / TRELLIS 2)
- **Object/Scene Recognition:** YOLOv8, Detectron2, Google Vision API
- **OCR (text from images):** Tesseract, AWS Textract
- **Face/Pose Estimation:** MediaPipe, OpenPose

## Gateway coverage

Either gateway is fine — pick the cheaper rate per model from the bake-off browser. **Note:** these are vision *understanding* models. For image *generation*, use Recraft (branded/vector) or FLUX/BFL (photoreal) directly — not a gateway LLM.

<!-- GATEWAY_COUNTS:START — last-refreshed: 2026-08-18 (auto-managed by update_gateway_counts.py) -->
*Live gateway counts (active models, 2026-08-18 UTC; auto-refreshed from `kilo_agents.db`):*

vision-input across all gateways: **217**

These are vision *understanding* models. Image *generation* (Recraft / FLUX) is not gateway-routed.
<!-- GATEWAY_COUNTS:END -->

**Use cases:** content creation, surveillance, document processing.

<!-- OPENROUTER_ROUTES:START — last-refreshed: 2026-08-18 (auto-managed by category_export_markdown.py) -->
*Auto-generated 2026-08-18 (UTC) by `category_route_mapper.py` → injected here by `category_export_markdown.py`. Edits between the markers will be overwritten on the next daily run.*

*No eligible models today — floors too strict or catalog too thin. See `cache/update.log` for details. Reason: No model satisfies category='vision' floors: min_quality_tier=1, min_context_window_k=1, require_vision=True, require_tools=False, require_reasoning=False, allow_free=False, stability_required=True, sort_key='input_cost_per_m ASC'*
<!-- OPENROUTER_ROUTES:END -->
