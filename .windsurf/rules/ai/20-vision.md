---
activation: glob
globs: ["**/vision/**", "**/image/**", "**/images/**", "**/imagegen/**", "**/img/**", "**/ocr/**", "**/video-gen/**"]
description: Vision AI (category 2) — image understanding on Claude through `claude -p` on the subscription first; image generation with Recraft (branded, vector, its Flash tier for bulk) and FLUX (photoreal), Replicate or fal as host; dedicated models for pixel boxes, pose, real time and bulk document OCR; licence traps named.
trigger: glob
currency_pass: 2026-10-02
---
<!-- CONSUMER: Coding agents building image understanding, image generation, OCR or detection features.
     GOAL: Understanding goes to Claude first; generation goes to Recraft or FLUX; a dedicated model only where Claude's own
     documented limits bite. No weights with a non-commercial licence as a default.
     AGENT USAGE: Can Claude do it? → `claude -p` through llm-dispatch. Generating? → Recraft (branded/vector, Flash tier for
     bulk) or FLUX (photoreal). Boxes, pose, real time, bulk OCR → § Subcategories. Model choice across categories is
     ai/00-ai-model-selection.md; record a project's choice and the rejected alternative in project.yaml (`ai_category`,
     `ai_subcategory`, `ai_tools`), as ai/00's selection workflow says. -->

# 2. Vision AI

Last content verification: 2026-10-02

**Purpose:** Interpret or generate images and video.

## Fabrik defaults

- **Image understanding → Claude through `claude -p`** on the Max subscription (ai/00-ai-model-selection.md § Claude
  subscription first): describe, classify, tag, read a screenshot or a chart, pull the text out of one hard image. Call it
  through fabrik-lib's `llm-dispatch` — `run_agentic(prompt, tools=("Read",), max_turns=4, add_dirs=(<image dir>,),
  model="haiku")`. The CLI has no image flag; Claude reads the file with its Read tool, headless included. Give the file
  the extension of its real format (the Read tool takes the type from the extension), and ask for something only the
  image contains, so that a blind answer shows up as a failure. Start at `haiku` and escalate on measured failure per
  ai/00's dispatch ladder — except dense screenshots and small text, which need a high-resolution model (`sonnet` or
  above; `haiku` reads at the standard resolution): crop to the region that matters rather than downscaling. It reads
  JPEG, PNG, WebP and GIF (first frame only). Every image draws visual tokens from the subscription quota, and past 20
  images in one run — earlier Read results count — every image must be 2000 px or less a side or the request is
  rejected. Visual question answering, captioning and document understanding are ai/40-multimodal.md, which starts
  that work on this same ladder and routes the video and audio Claude cannot read.
- **When a dedicated model beats Claude.** Anthropic's vision docs say Claude's coordinates and counts are approximate,
  that it errs on very small, rotated or low-quality images, will not name people, cannot tell an AI-generated image,
  and is not for medical scans. So pixel-exact boxes, counting many small objects, real-time video frames, on-device
  inference and face or pose landmarks go to a dedicated model, and bulk document OCR to a dedicated parser
  (§ Subcategories).
- **Image generation.** Claude does not generate images.
  - **Branded / recurring-style / vector → Recraft** (its current model): native SVG output and brand styles held by a
    style id, for logos, mascots and sets that must look like a family. About $0.035 a raster image, $0.08 a vector.
  - **Bulk / low-personality illustration → Recraft's Flash tier** (about $0.007 an image) — vocabulary cards, icons,
    one-off concrete nouns; weigh the count and the need for a shared style before reaching for Recraft's full model.
    FLUX's small klein model (from about $0.014) when you need open weights you can self-host: they are Apache-licensed.
  - **Photoreal → FLUX (Black Forest Labs)**, its pro tier (from about $0.03 a megapixel), through Replicate or fal.
  - **Host / fallback → Replicate**, or fal when it is cheaper for that model or the only host. The hub's vendor-access
    catalog (`/opt/fabrik/docs/reference/kilo/AI_VENDOR_ACCESS.md`) does not recommend a direct BFL route, and Recraft's
    direct key has had little or no credit, so call Recraft through fal or Replicate until the key is funded.

**Licence trap — open weights are not commercial weights.** FLUX's larger klein model, its dev weights and its Kontext
dev weights carry the FLUX Non-Commercial License. Ultralytics YOLO is AGPL-3.0 for its code and every model trained with
it: closed-source commercial use, internal R&D included, needs its paid Enterprise License. OpenPose is licensed for
noncommercial research only. Surya's weights need a paid licence above $5M funding or revenue. None of them is a Fabrik
default. Adopting one takes its owner's commercial licence — open-sourcing the whole product cures only the AGPL case.

## Subcategories

⚠️ **A vendor NAMED here is not a vendor we can CALL.** These lists say what exists in each lane;
`/opt/fabrik/docs/reference/kilo/AI_VENDOR_ACCESS.md` (ai/00's source of truth for callable vendors) and the reach map
`/opt/fabrik/docs/reference/ai-media-generation-provider-map.md` say what the fleet can call. Check them before designing
around any vendor below.
- **Image generation:** Recraft; FLUX (Black Forest Labs); Replicate and fal as hosts; OpenAI GPT Image; Ideogram for
  text rendered inside the image (through fal or Replicate); Stable Diffusion (Stability's Community License: free
  commercial use below USD 1M annual revenue). Midjourney has no public API and its terms forbid automated access, so
  it is not callable.
- **Video generation:** the reach map's § VIDEO is the only list of live routes; this pack does not copy it, because a
  copy drifts — read the map, and carry no vendor list or count from it into a design.
- **3D / mesh generation:** see `25-3d-generation.md`.
- **Image understanding** (describe, classify, tag, read screenshots and charts): Claude through `claude -p`, as above.
- **Object detection** (boxes, counts, real time): on-device or real-time detection of everyday objects → MediaPipe's
  Object Detector (Apache-2.0; still images, video and live streams; its default models know the 80 COCO classes).
  Custom classes with pixel-exact boxes have no commercially clean default here: Ultralytics YOLO needs its paid licence
  for closed use, and Google Cloud Vision needs a Google Cloud project the vendor-access catalog lists as not set up —
  choose one deliberately and record why.
- **OCR (text from images):**
  - **A few hard pages or a short PDF → Claude** reads them directly; the Read tool takes PDFs too, in ranges of up to
    20 pages.
  - **A scanned batch → Tesseract** (Apache-2.0) behind fabrik-lib's `ocr/`, which preprocesses bad scans and retries
    before paying. Its paid fallback is an injectable `vision_fn` that receives PNG bytes: write them to a `.png` in a
    temp directory and call Claude through `llm-dispatch` on it, rather than the module's metered OpenRouter default.
  - **Layout-heavy documents at volume (tables, columns) → PaddleOCR** (Apache-2.0, ships a document vision-language
    parser). Small dedicated parsers lead the OmniDocBench document-OCR leaderboard over general vision models, and no
    Claude model is listed there — so bulk document OCR goes to a parser, and Claude takes the hard pages and the meaning.
  - **Managed → Google Cloud Vision or AWS Textract**, about $1.50 per 1,000 pages for plain text; Textract's tables and
    forms cost more per page. Neither is set up today: the vendor-access catalog lists the Google Cloud project as not
    set up and has no AWS row, so a managed OCR route starts with an account and is recorded as a choice.
- **Face / pose estimation:** MediaPipe (Apache-2.0, on-device, maintained under Google AI Edge). OpenPose is
  noncommercial only.

## Gateway coverage

Image understanding runs on Claude through `claude -p`, not a metered gateway (ai/00). A metered vision model through
OpenRouter is the fallback only when Claude measurably falls short or a call cannot use the subscription; the counts
below inventory that fallback. Image generation is not gateway-routed: call Recraft and FLUX directly or through
Replicate or fal.

<!-- GATEWAY_COUNTS:START — last-refreshed: 2026-09-07 (auto-managed by update_gateway_counts.py) -->
*Live gateway counts (active models, 2026-09-07 UTC; auto-refreshed from `kilo_agents.db`):*

vision-input across all gateways: **235**

These are vision *understanding* models. Image *generation* (Recraft / FLUX) is not gateway-routed.
<!-- GATEWAY_COUNTS:END -->

**Use cases:** content creation, surveillance, document processing.

<!-- OPENROUTER_ROUTES:START — last-refreshed: 2026-09-07 (auto-managed by category_export_markdown.py) -->
*Auto-generated 2026-09-07 (UTC) by `category_route_mapper.py` → injected here by `category_export_markdown.py`. Edits between the markers will be overwritten on the next daily run.*

*No eligible models today — floors too strict or catalog too thin. See `cache/update.log` for details. Reason: No model satisfies category='vision' floors: min_quality_tier=1, min_context_window_k=1, require_vision=True, require_tools=False, require_reasoning=False, allow_free=False, stability_required=True, sort_key='input_cost_per_m ASC'*
<!-- OPENROUTER_ROUTES:END -->
