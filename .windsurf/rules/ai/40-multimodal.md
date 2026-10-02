---
activation: glob
globs: ["**/multimodal/**", "**/vqa/**", "**/vision-language/**", "**/image-captioning/**", "**/doc-understanding/**"]
description: Vision-Language & Multimodal AI (category 4) — understand images, documents, audio and video together. Images and PDFs go to Claude through claude -p on the subscription; Claude takes no audio or video, so video and non-speech audio go to Gemini through OpenRouter and speech is transcribed first (ai/10). Visual QA, captioning, document and video understanding.
trigger: glob
currency_pass: 2026-10-02
---
<!-- CONSUMER: Coding agents building multimodal features (visual QA, captioning, document or video understanding)
     GOAL: Route each input to an engine that actually reads that modality — Claude for images and PDFs, Gemini for
     video and non-speech audio, a transcript for speech.
     AGENT USAGE: Name the modalities present first; Claude silently drops an audio part, so never send it one. Model
     choice across categories is ai/00-ai-model-selection.md; record a project's choice and the rejected alternative in
     project.yaml (`ai_category`, `ai_subcategory`, `ai_tools`), as ai/00's selection workflow says. -->

# 4. Vision-Language & Multimodal AI

Last content verification: 2026-10-02

**Purpose:** Combine text, image, audio, and video understanding.

## Fabrik defaults

Start by naming the modalities in the input. Claude reads text, images and PDFs and nothing else: Anthropic's model
API lists only image and PDF input among its capabilities, Claude Code's Read tool has no audio or video type, and the
OpenAI-compatible endpoint drops an audio part silently instead of refusing it — audio sent that way is lost without an
error.

- **Images and documents → Claude through `claude -p`** on the Max subscription (ai/00-ai-model-selection.md § Claude
  subscription first), on the same `run_agentic` ladder ai/20-vision.md sets for image understanding: the Read tool
  reads the file, start at `haiku`, escalate on measured failure. That covers visual question answering, captioning,
  charts, screenshots and document understanding. Pass what the caller already knows about the subject — a product
  name, a document type: the fleet's own image describer confused products when blind, and every model it tested
  scored 8 to 10 out of 10 once given the product name. Image cost grows with pixels, so crop to the region that
  matters.
- **PDFs → read the text before the pixels.** The Read tool reads a short PDF whole and a longer one in page ranges of
  up to 20 pages, and refuses a PDF over 100 pages or 20 MB; an encrypted PDF fails outright. Page-range reads render
  each page as an image with `pdftoppm` (poppler-utils must be on the host) and draw visual tokens from the subscription
  quota, so a native-text PDF whose layout does not matter goes through fabrik-lib's `pdf-extract` first, and a scan
  through fabrik-lib's `ocr`, whose `make_claude_vision_fn` falls back to Claude for the pages Tesseract cannot read —
  only with `min_conf` above 0, since the default never escalates. A deployed service that calls `claude -p` declares
  `shape.uses_claude_cli` (ai/00). Bulk document parsing goes to a dedicated parser (§ Subcategories).
- **Speech → transcribe, then Claude.** Spoken content goes through ai/10-speech-audio.md's transcription route, and
  Claude works on the transcript — unless the question is how it was said (tone, emotion): that audio goes to Gemini
  like non-speech audio, and who spoke when is ai/10's diarization.
- **Video, and audio that is not speech → Gemini through OpenRouter.** Every Gemini tier reads video and audio, and the
  vendor-access catalog reaches Gemini through OpenRouter, not a direct Google key. Start on the Flash-Lite tier, the
  cheapest, and move up a tier on measured failure. Send a local clip as a base64 `video_url` and audio as base64
  `input_audio`; a public YouTube video goes as its link, with no download — OpenRouter sends a video URL only to a
  provider that takes one (Google AI Studio).
  Cost a clip before sending it: video runs about 100 tokens a second at the default low media resolution, audio 32
  tokens a second, priced at the tier's input rate — check Google's price page, since the Flash tier's rate doubles on
  2027-01-01. OpenRouter exposes one control, `processing` on the video part: `"agentic"` for long recordings (a Gemini
  feature; other providers ignore it) or `"static"`, which samples one frame a second. It has no frame-rate or
  resolution setting, so for fast action trim the clip or send the frames that matter to Claude. A 1M-context tier takes
  up to three hours of video at the default resolution.
- **Only the frames matter → Claude.** When the question is about what is visible, not about sound or motion, sample
  the frames that matter and send them to Claude as images instead of sending the video.
- **Open weights** (data residency, an offline device, or a volume past core/76-gpu-workers.md's break-even) → Qwen's
  open models: hosted first on OpenRouter, since core/76 starts with managed APIs; on a GPU pod per core/76 only past
  its break-even or for residency; locally on an offline device. Its current open models read images and video
  natively, and its open omni model adds audio. Both families ship Apache-licensed weights.

**Licence trap — check each checkpoint, not the family.** LLaVA's code is Apache-licensed but each checkpoint carries its
base model's licence, such as Llama's community licence. Qwen's newer omni models are hosted only; the open one is the
earlier generation. Read the licence file shipped with the exact weights before adopting them.

## Subcategories

⚠️ **A vendor NAMED here is not a vendor we can CALL.** `/opt/fabrik/docs/reference/kilo/AI_VENDOR_ACCESS.md` (ai/00's
source of truth for callable vendors) says which ones have keys today; OpenAI and Google are reached through OpenRouter.

- **Visual question answering, captioning, charts:** Claude (default); Gemini's Flash-Lite tier through OpenRouter as
  the measured cheap fallback; Qwen's open models.
- **Document understanding:** Claude for a few documents. For bulk parsing: Mistral OCR through OpenRouter's
  file-parser plugin (its default engine, billed per page to the OpenRouter account — Mistral direct has no key; about
  $4 per 1,000 pages there, $2 through its batch API), LlamaParse (a new vendor that needs a signup; from 1 to 45 credits
  a page, 1,000 credits for $1.25), or Docling (MIT, self-hosted, with IBM's small Granite document model). Gemini reads PDFs up to 1,000 pages and does not charge
  for their native text.
- **Video understanding:** Gemini (default); Qwen's open models or its open omni model. OpenAI's models take
  no video.
- **Audio understanding (sound events, music, and how speech was said):** Gemini (default); OpenAI's audio model and Qwen's
  open omni model as alternatives.
- **Compare on:** arena.ai's vision leaderboard for hosted models, MMMU for multimodal reasoning, OpenCompass's own
  multimodal board for open weights (its Hugging Face mirror is stale). Video-MME's board has no current frontier
  entries, so test video work on your own clips.

## Gateway coverage

OpenRouter carries the hosted multimodal frontier, including video input (`video_url`) and audio input (`input_audio`,
base64 only); a provider may price audio tokens above text. Each provider has its own video rules: Google AI Studio
takes only YouTube links and Vertex only base64. For a non-Claude model, pick the rate per model from the bake-off
browser (hub-only). The browser carries no video-input flag, so before relying on video check that the model lists it
in `architecture.input_modalities` on OpenRouter's models endpoint (its `/models` listing).

<!-- GATEWAY_COUNTS:START — last-refreshed: 2026-09-07 (auto-managed by update_gateway_counts.py) -->
*Live gateway counts (active models, 2026-09-07 UTC; auto-refreshed from `kilo_agents.db`):*

vision-input across all gateways: **235**

Multimodal overlaps with Vision (category 2) — see the Audio/Vision tab in the bake-off browser for the audio-in subset.
<!-- GATEWAY_COUNTS:END -->

**Use cases:** image captioning, visual QA, document understanding, video analysis.

<!-- OPENROUTER_ROUTES:START — last-refreshed: 2026-09-07 (auto-managed by category_export_markdown.py) -->
*Auto-generated 2026-09-07 (UTC) by `category_route_mapper.py` → injected here by `category_export_markdown.py`. Edits between the markers will be overwritten on the next daily run.*

*No eligible models today — floors too strict or catalog too thin. See `cache/update.log` for details. Reason: No model satisfies category='multimodal' floors: min_quality_tier=1, min_context_window_k=1, require_vision=True, require_tools=True, require_reasoning=True, allow_free=False, stability_required=True, sort_key='input_cost_per_m ASC'*
<!-- OPENROUTER_ROUTES:END -->
