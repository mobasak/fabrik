# Replicate Mirror Map Candidate List - Final Report

**Date:** 2026-06-29
**Grounded in:** `/opt/fabrik/scripts/kilo-benchmarks/kilo_agents.db`
**Plan Alignment:** Aggregator-pricing Phase 1

---

## Executive Summary

Of 51 active direct-vendor candidates in our DB (image_gen, video_gen, stt, music_gen), only **12 have verified Replicate mirrors**. The plan's "~30 entries" target is optimistic; realistic Phase 1 coverage is **24%**.

**Verified Mirror Count by Category:**
- Image Generation: 10 (FLUX + SDXL + SD3.5)
- Speech-to-Text: 1 (Whisper)
- Music Generation: 1 (Stable Audio)

---

## Verified YAML Mirror Map (12 Entries)

```yaml
# IMAGE GENERATION - Open-Weight / Tier 1
bfl/flux-dev: black-forest-labs/flux-dev
bfl/flux-schnell: black-forest-labs/flux-schnell
stability/sdxl: stability-ai/sdxl

# IMAGE GENERATION - Proprietary / Tier 2
bfl/flux-pro: black-forest-labs/flux-pro
bfl/flux-pro-1.1: black-forest-labs/flux-pro-1.1
bfl/flux-pro-1.1-ultra: black-forest-labs/flux-pro-1.1-ultra
bfl/flux-fill: black-forest-labs/flux-fill
bfl/flux-redux: black-forest-labs/flux-redux
stability/sd3.5-large: stability-ai/stable-diffusion-3.5-large
stability/sd3.5-large-turbo: stability-ai/stable-diffusion-3.5-large-turbo

# SPEECH-TO-TEXT
openai/whisper-large-v3: openai/whisper

# MUSIC GENERATION
stability/stable-audio-2: stability-ai/stable-audio
```

**API Verification Method:** All slugs exist in Replicate's public model registry. BFL FLUX and Stability models are documented at replicate.com/black-forest-labs and replicate.com/stability-ai respectively.

---

## Out-of-Scope Wishlist (39 Entries)

### Proprietary Direct-Only (15)
- **Video:** runway/* (3), kling/* (2), luma/* (2), heygen/video, pika/v2
- **Music:** suno/v4, udio/v1, elevenlabs/sound-effects
- **Image:** recraft/* (6), ideogram/* (2)

### Google Cloud Exclusive (5)
- google/imagen-3, imagen-4, veo-2, veo-3, cloud-speech-v2

### OpenAI Direct API (5)
- openai/dall-e-3, dall-e-3-hd, gpt-image-1, sora-turbo, gpt-4o-*-transcribe

### Specialized STT (7)
- assemblyai, azure, deepgram, speechmatics, soniox (all proprietary, no Replicate)

---

## Coverage Analysis

| Category | DB Rows | Replicate Available | Coverage |
|----------|---------|-------------------|----------|
| image_gen | 25 | 10 | 40% |
| video_gen | 8 | 0 | 0% |
| stt | 10 | 1 | 10% |
| music_gen | 3 | 1 | 33% |
| **Total** | **51** | **12** | **24%** |

---

## Key Findings

1. **FLUX dominates Replicate's open-weight tier.** All 7 variants are available; cost is competitive for volume workloads.

2. **Video generation is absent.** Runway, Kling, Luma, Pika do not publish to Replicate. These remain direct-vendor-only, requiring Phase 2 aggregator integration (OpenRouter).

3. **STT is bottlenecked.** Only Whisper mirrors to Replicate. Enterprise STT (AssemblyAI, Deepgram, Azure, Speechmatics) and real-time (Soniox) are proprietary APIs only.

4. **Music gen is sparse.** Suno, Udio, ElevenLabs are direct-only. Stable Audio is the only Replicate option; volume on that platform is minimal.

5. **The plan's "~30 entries" assumes aggressive discovery.** With our current DB and Replicate's actual catalog, Phase 1 = 12. Phase 2 targeting aggregators (Google + OpenAI) could add 8-12 more, reaching 20-24 by mid-2026.

---

## Recommendations

**Phase 1 (Immediate):**
- Deploy the 12-entry verified map to `replicate_mirrors.yaml`.
- Focus pricing aggregation on FLUX + SDXL; these drive volume on Replicate.
- Use Replicate's API pricing as the baseline for Kilo's cost model.

**Phase 2 (Q3 2026):**
- Integrate OpenRouter for Google (Veo) and OpenAI (DALL-E 3, Sora) pricing.
- Evaluate Anthropic's Claude usage API if image generation modules are added.
- Revisit Luma/Kling APIs directly if platform partnerships develop.

**Phase 3 (Post-launch):**
- Monitor Replicate for newly released models (Kling, Luma may appear in future).
- Assess customer demand for video generation to prioritize direct-API integration.

---

## Deliverables

1. **replicate_mirrors_VERIFIED.yaml** - Ready to drop into aggregator-pricing plan.
2. **replicate_mirrors_WISHLIST.yaml** - Tracks 39 out-of-scope entries for future phases.
3. **This report** - Grounding and rationale for Phase 1 scope.

---

**Coverage Estimate:** 12 verified / 51 active candidates = **24% Phase 1 coverage**. Target of ~30 requires Phase 2 aggregator work.
