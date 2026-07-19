---
activation: glob
globs: ["**/speech/**", "**/audio/**", "**/tts/**", "**/stt/**", "**/transcription/**", "**/voice/**", "**/music/**"]
description: Speech & Audio AI (category 1) — transcription (Soniox/Whisper), TTS (Soniox default for multilingual/faithful, ElevenLabs for expressive), voice cloning, audio classification, music gen. Kilo audio coverage is thin (9 models).
trigger: glob
---
<!-- CONSUMER: Coding agents building speech/audio features + Traycer (tech-plan)
     GOAL: Pick the right speech tool; Soniox is the Fabrik TTS default; don't use a general LLM for transcription.
     TRAYCER USAGE: Context File for audio/voice tickets.
     AGENT USAGE: Transcription → Soniox/Whisper. TTS → Soniox (multilingual/faithful) or ElevenLabs (expressive). Document choice in project.yaml. -->

# 1. Speech & Audio AI

Last content verification: 2026-07-19

**Purpose:** Convert or interpret sound.

## Fabrik defaults
- **TTS → Soniox TTS** (60+ langs, hallucination-free, native EN/TR + mid-sentence language switching, EU residency/GDPR) — preferred for faithful pronunciation & multilingual cards. Use **ElevenLabs** only when expressive prosody matters more than faithfulness.
- **Transcription → Soniox** or Whisper.
- **TTS fallback (self-hosted) → XTTS-v2 (Coqui)** — model weights run on operator's own GPU pod (Apache 2.0 license, voice cloning, 16+ languages). Use when (a) API costs need a $0-per-char floor at high volume, (b) data residency forbids hosted TTS, OR (c) the primary TTS vendor is rate-limited / down. Trade-off: GPU pod must be provisioned and warm; sub-second TTFA only on T4/L40S-tier. NOT a replacement for the API defaults at low volume — pod overhead defeats the cost win below ~100K chars/day.

## Subcategories
- **Transcription (Speech-to-Text):** Soniox, Whisper, Deepgram, AssemblyAI
- **Speech Synthesis (Text-to-Speech):** Soniox TTS, ElevenLabs (more expressive voices), Play.ht, Amazon Polly, XTTS-v2 (Coqui, self-hosted fallback)
- **Voice Cloning:** Resemble AI, ElevenLabs VoiceLab
- **Audio Classification:** Google AudioSet, YAMNet
- **Music Generation:** Suno, Udio, Mubert, Meta MusicGen

## Gateway coverage

For STT/TTS, **prefer the direct vendor** (Soniox, Whisper API, gpt-4o-transcribe, Deepgram) over a gateway LLM — quality and price both favor the dedicated path. If you must route via a gateway, pick the cheaper of Kilo / OpenRouter per model.

<!-- GATEWAY_COUNTS:START — last-refreshed: 2026-07-19 (auto-managed by update_gateway_counts.py) -->
*Live gateway counts (active models, 2026-07-19 UTC; auto-refreshed from `kilo_agents.db`):*

STT-capable across all gateways: **29**

Direct-vendor specialists (Soniox, Whisper API, gpt-4o-transcribe, Deepgram) are NOT in this DB — they live in their own `stt_quality` JSON and the bake-off browser's Audio/Vision tab. Gateway LLMs are last-resort.
<!-- GATEWAY_COUNTS:END -->

**Use cases:** transcription services, voice assistants, audio processing.

**Anti-pattern:** using a general LLM for transcription instead of Soniox/Whisper.

<!-- OPENROUTER_ROUTES:START — last-refreshed: 2026-07-19 (auto-managed by category_export_markdown.py) -->
*Auto-generated 2026-07-19 (UTC) by `category_route_mapper.py` → injected here by `category_export_markdown.py`. Edits between the markers will be overwritten on the next daily run.*

| Priority | OpenRouter ID | Cost ($/M in) | Context | Status |
|---|---|---|---|---|
| P1 | `openai/gpt-audio-mini` | $0.60 | 128k | GA |

To consume via a Fabrik spec: `llm_provider: openrouter` + `llm_model: <P1 id>`. Fallback chain via the OpenRouter `models: [P1, P2, P3]` request parameter.
<!-- OPENROUTER_ROUTES:END -->
