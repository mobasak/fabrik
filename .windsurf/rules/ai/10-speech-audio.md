---
activation: glob
globs: ["**/speech/**", "**/audio/**", "**/tts/**", "**/stt/**", "**/transcription/**", "**/voice/**", "**/music/**"]
description: Speech & Audio AI (category 1) — transcription (Soniox, ElevenLabs Scribe, OpenAI, Deepgram, AssemblyAI), TTS (Soniox default, ElevenLabs for expressive voices, Chatterbox self-hosted), voice cloning, speech gating, diarization, audio classification, music generation — with the commercial-use limits that decide them.
trigger: glob
currency_pass: 2026-10-02
---
<!-- CONSUMER: coding agents building speech or audio features (the globs fire on speech/audio/voice paths).
     GOAL: pick the right speech tool, respect each model's licence, never use a general LLM for plain transcription.
     Model choice across categories is ai/00-ai-model-selection.md; record a project's vendor choice in docs/DECISIONS.md. -->

# 1. Speech & Audio AI

Last content verification: 2026-10-02

**Purpose:** Convert or interpret sound. Before recommending a vendor the operator will run, read `ai/00-ai-model-selection.md`
§ Selection MDs — the TTS and STT selection docs and the vendor-access catalog.

## Fabrik defaults

- **TTS → Soniox TTS** — 60+ languages from every voice, mid-sentence language switching (native EN/TR), output that does not
  invent, drop or substitute words, voice cloning from a clip of up to 20 seconds, and an EU region (in-region processing and storage, enabled on
  request). Use **ElevenLabs** when expressive prosody matters more than faithfulness.
- **Transcription → Soniox** (real-time and async, 60+ languages, US/EU/Japan/India regions) or a peer from § Subcategories.
- **Gate audio before a paid transcription call** with fabrik-lib's `speech-detect/` (Silero VAD, fail-open) — silent or empty
  audio never reaches the paid engine.
- **TTS fallback (self-hosted) → Chatterbox Multilingual** (Resemble AI; MIT licence on code and weights; 23 languages including
  Turkish; zero-shot voice cloning) on the operator's own GPU pod. Use it when (a) per-character API cost needs a floor at high
  volume, (b) data residency forbids hosted TTS, or (c) the primary vendor is rate-limited or down. Every Chatterbox output
  carries Resemble's imperceptible Perth watermark — say so wherever provenance matters. The pod must be provisioned and warm,
  so it does not beat the API defaults at low volume.

**Licence trap — check the WEIGHTS, not the code.** Coqui XTTS (the company shut down in January 2024) ships its weights
under the Coqui Public Model License: non-commercial only. F5-TTS and Meta MusicGen weights are CC-BY-NC. None of them may back
a paid product, whatever the code licence says.

## Subcategories

- **Transcription (Speech-to-Text):** Soniox, ElevenLabs Scribe, OpenAI (its speech-to-text guide names the current default
  model; `whisper-1` stays for word or segment timestamps), Deepgram, AssemblyAI — Deepgram and AssemblyAI both cover Turkish.
  Whisper's open weights (MIT) are the self-hosted option.
- **Speaker diarization:** pyannote.audio (MIT code; its pretrained pipeline is gated on Hugging Face — accept the conditions and
  use a token) or a vendor's built-in diarization.
- **Speech Synthesis (Text-to-Speech):** Soniox TTS, ElevenLabs, Amazon Polly, Chatterbox (self-hosted); Kokoro (Apache 2.0)
  for English-first self-hosted speech without cloning.
- **Voice Cloning:** ElevenLabs (Instant and Professional Voice Cloning, managed under My Voices), Soniox (clone from a clip of up to 20 seconds),
  Chatterbox (self-hosted).
- **Audio Classification:** YAMNet (needs the legacy `tf-keras` package, not current Keras), PANNs (MIT), the Audio Spectrogram Transformer — all trained on Google
  AudioSet, which is the labelled dataset, not a tool.
- **Music Generation:** Suno (models trained on licensed catalogues; free-tier output is non-commercial), Mubert (API with
  commercial sync licences; no distribution to streaming services), Udio (downloads disabled since its 2025 label settlement —
  not a source of deliverable audio), Meta MusicGen (CC-BY-NC weights — non-commercial).

## Gateway coverage

For STT and TTS, **prefer the direct vendor** (Soniox, ElevenLabs, OpenAI, Deepgram) over a gateway LLM — a dedicated model is
cheaper and many times faster. If a gateway is unavoidable, OpenRouter is the one in use (the Kilo gateway is retired).

<!-- GATEWAY_COUNTS:START — last-refreshed: 2026-09-07 (auto-managed by update_gateway_counts.py) -->
*Live gateway counts (active models, 2026-09-07 UTC; auto-refreshed from `kilo_agents.db`):*

STT-capable across all gateways: **36**

Direct-vendor specialists (Soniox, Whisper API, gpt-4o-transcribe, Deepgram) are NOT in this DB — they live in their own `stt_quality` JSON and the bake-off browser's Audio/Vision tab. Gateway LLMs are last-resort.
<!-- GATEWAY_COUNTS:END -->

**Use cases:** transcription services, voice assistants, audio processing.

**Anti-pattern:** sending audio to a general LLM for plain transcription. On public speech-to-text benchmarks the best dedicated
models match or beat general LLMs on word error rate at a fraction of the cost and many times the speed; use an LLM only when
the task is understanding the audio, not transcribing it.

<!-- OPENROUTER_ROUTES:START — last-refreshed: 2026-09-07 (auto-managed by category_export_markdown.py) -->
*Auto-generated 2026-09-07 (UTC) by `category_route_mapper.py` → injected here by `category_export_markdown.py`. Edits between the markers will be overwritten on the next daily run.*

*No eligible models today — floors too strict or catalog too thin. See `cache/update.log` for details. Reason: No model satisfies category='speech-audio' floors: min_quality_tier=1, min_context_window_k=1, require_vision=False, require_tools=False, require_reasoning=False, allow_free=False, stability_required=True, sort_key='input_cost_per_m ASC'*
<!-- OPENROUTER_ROUTES:END -->
