#!/usr/bin/env python3
"""Seed direct-vendor specialist rows into `agents` so they appear in
the AI Models Browser alongside gateway-routed LLMs.

Why a separate seeder from `seed_translation_and_stt.py`:
  - That script reads a v1 bake-off doc and only knows about models
    that produced chrF++ scores. It can't add image-gen / TTS / video
    / OCR rows whose "score" is a different shape (e.g. $/image).
  - This script encodes operator-known facts: pricing, capability
    flags, and a short description per direct-vendor specialist. Rows
    are inserted with `via_openrouter=0 via_kilo=0` and the appropriate
    direct-gateway flag (e.g. `via_dashscope=1` for DashScope).
  - Marked with `service_type` (llm | stt | tts | translation |
    image_gen | video_gen | music_gen | ocr | embedding) so the browser
    can filter / categorize.

Cost normalization: `input_cost_per_m` is ALWAYS dollars per million
billable units of the vendor's primary metric so rows are sortable on
a single numeric axis:
  - LLM      → $/M tokens
  - STT      → $/M audio-seconds (vendor-quoted $/minute × 1e6 / 60)
  - TTS      → $/M characters    (vendor-quoted $/1K chars × 1000)
  - Translation → $/M characters (DeepL/Google/Azure quote per-M-char)
  - Image    → $/M images        (vendor-quoted $/image × 1e6)
  - Video    → $/M video-seconds (vendor-quoted $/second × 1e6)
  - Music    → $/M audio-seconds
  - OCR      → $/M pages         (vendor-quoted $/page × 1e6)
The `pricing_unit` column carries the canonical unit label for display
(`M-tokens`, `audio-min`, `M-chars`, `image`, `video-sec`, `audio-min`,
`page`); the browser converts back to vendor-quoted price at render
time.

Idempotent: each vendor's row is upserted by id. Pre-existing rows are
updated (price, name, description, status, service_type, pricing_unit)
without clobbering operator edits to fields not in `_UPSERT_FIELDS`.
"""

from __future__ import annotations

import sqlite3
import sys
from datetime import UTC, datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
DB_PATH = SCRIPT_DIR / "kilo_agents.db"


def _log(msg: str) -> None:
    print(f"[seed_direct_vendors] {msg}")


def _today() -> str:
    return datetime.now(UTC).date().isoformat()


# Helper price converters (so the table reads in vendor-quoted units)
def per_min(usd_per_min: float) -> float:
    """Convert $/audio-minute → $/M audio-seconds (the normalized axis)."""
    return usd_per_min * 1_000_000 / 60


def per_1k_chars(usd_per_1k: float) -> float:
    return usd_per_1k * 1000


def per_image(usd_per_image: float) -> float:
    return usd_per_image * 1_000_000


def per_video_sec(usd_per_sec: float) -> float:
    return usd_per_sec * 1_000_000


def per_page(usd_per_page: float) -> float:
    return usd_per_page * 1_000_000


# ============================================================
# VENDORS — direct-vendor specialist catalogue.
#
# Data source HONESTY (2026-06-29): all entries here are operator-encoded
# from training-data knowledge (cutoff Jan 2026) + the one Recraft URL
# fetched live in the seeding session. There is NO automated vendor-pricing
# scraper. Prices are point-in-time; vendors do change them.
#
# When in doubt: read the row's `description` (it carries the canonical
# unit + caveats) and the vendor's pricing page before committing to a
# heavy-volume integration. Each description marks "approximate" or
# "credit-based proxy" where the vendor doesn't publish a flat $/unit
# (Suno, Udio, Pika, HeyGen, Recraft Nano Banana).
#
# Older / less-relevant SKUs are listed because they appear in existing
# codebases under /opt/ and operators may still need them.
# ============================================================
VENDORS: dict[str, dict] = {}


def _add(mid: str, **kw) -> None:
    VENDORS[mid] = kw


# ---------- STT (transcription) ----------
_add(
    "soniox/stt-async-v4",
    name="Soniox: STT Async v4",
    provider="soniox",
    service_type="stt",
    is_stt_capable=1,
    input_cost_per_m=per_min(0.10),
    pricing_unit="audio-min",
    quality_tier=1,
    is_ga=1,
    description="Soniox async STT. ~60+ languages, hallucination-free, speaker diarization, mid-sentence language switching. Fabrik default for multilingual transcription. Used by /opt/youtube. $0.10/audio-minute.",
)
_add(
    "soniox/stt-realtime-v4",
    name="Soniox: STT Realtime v4",
    provider="soniox",
    service_type="stt",
    is_stt_capable=1,
    input_cost_per_m=per_min(0.13),
    pricing_unit="audio-min",
    quality_tier=1,
    is_ga=1,
    description="Soniox realtime STT (streaming). Sub-second latency, same multilingual profile as async. $0.13/audio-minute.",
)
_add(
    "openai/whisper-large-v3",
    name="OpenAI: Whisper Large v3",
    provider="openai",
    service_type="stt",
    is_stt_capable=1,
    input_cost_per_m=per_min(0.006),
    pricing_unit="audio-min",
    quality_tier=2,
    is_ga=1,
    description="OpenAI Whisper Large v3 (cloud API). 99 languages, robust on noisy audio. $0.006/minute via OpenAI API.",
)
_add(
    "openai/gpt-4o-transcribe",
    name="OpenAI: GPT-4o Transcribe",
    provider="openai",
    service_type="stt",
    is_stt_capable=1,
    input_cost_per_m=per_min(0.006),
    pricing_unit="audio-min",
    quality_tier=1,
    is_ga=1,
    description="OpenAI's 4o-based transcription. Beats Whisper Large v3 on WER. $0.006/audio-minute.",
)
_add(
    "openai/gpt-4o-mini-transcribe",
    name="OpenAI: GPT-4o Mini Transcribe",
    provider="openai",
    service_type="stt",
    is_stt_capable=1,
    input_cost_per_m=per_min(0.003),
    pricing_unit="audio-min",
    quality_tier=2,
    is_ga=1,
    description="Cheaper variant of gpt-4o-transcribe. Half the price, modest WER hit. $0.003/audio-minute.",
)
_add(
    "deepgram/nova-3",
    name="Deepgram: Nova-3",
    provider="deepgram",
    service_type="stt",
    is_stt_capable=1,
    input_cost_per_m=per_min(0.0043),
    pricing_unit="audio-min",
    quality_tier=1,
    is_ga=1,
    description="Deepgram's flagship. Multilingual, low-latency streaming, custom vocabularies. ~$0.0043/min batch, $0.0077/min streaming.",
)
_add(
    "deepgram/nova-2",
    name="Deepgram: Nova-2",
    provider="deepgram",
    service_type="stt",
    is_stt_capable=1,
    input_cost_per_m=per_min(0.0036),
    pricing_unit="audio-min",
    quality_tier=2,
    is_ga=1,
    description="Deepgram Nova-2 (older). Still strong on EN, cheaper than Nova-3.",
)
_add(
    "assemblyai/universal-2",
    name="AssemblyAI: Universal-2",
    provider="assemblyai",
    service_type="stt",
    is_stt_capable=1,
    input_cost_per_m=per_min(0.0062),
    pricing_unit="audio-min",
    quality_tier=1,
    is_ga=1,
    description="AssemblyAI Universal-2. Best speaker diarization in class, multilingual. $0.0062/minute.",
)
_add(
    "google/cloud-speech-v2",
    name="Google: Cloud Speech-to-Text v2 (Chirp 2)",
    provider="google",
    service_type="stt",
    is_stt_capable=1,
    input_cost_per_m=per_min(0.024),
    pricing_unit="audio-min",
    quality_tier=2,
    is_ga=1,
    description="Google Cloud Speech-to-Text v2 with Chirp 2 model. 100+ languages, batch + streaming. $0.024/minute standard.",
)
_add(
    "azure/speech-to-text",
    name="Azure: Speech-to-Text (standard)",
    provider="azure",
    service_type="stt",
    is_stt_capable=1,
    input_cost_per_m=per_min(0.006),
    pricing_unit="audio-min",
    quality_tier=3,
    is_ga=1,
    description="Azure Cognitive Services Speech-to-Text. Wide language coverage. ~$0.36/audio-hour = $0.006/minute.",
)
_add(
    "speechmatics/enhanced",
    name="Speechmatics: Enhanced",
    provider="speechmatics",
    service_type="stt",
    is_stt_capable=1,
    input_cost_per_m=per_min(0.0083),
    pricing_unit="audio-min",
    quality_tier=2,
    is_ga=1,
    description="Speechmatics Enhanced. Strong accent + dialect coverage. ~$0.50/audio-hour = $0.0083/min.",
)

# ---------- TTS (voice generation) ----------
_add(
    "soniox/tts",
    name="Soniox: TTS (multilingual)",
    provider="soniox",
    service_type="tts",
    input_cost_per_m=180.0,  # $0.18/M chars
    pricing_unit="M-chars",
    quality_tier=1,
    is_ga=1,
    description="Soniox text-to-speech (2026). Same multilingual + faithfulness profile as their STT. Fabrik default for multilingual TTS. $0.18/M characters.",
)
_add(
    "elevenlabs/multilingual-v2",
    name="ElevenLabs: Multilingual v2 (Creator)",
    provider="elevenlabs",
    service_type="tts",
    input_cost_per_m=per_1k_chars(0.30),
    pricing_unit="M-chars",
    quality_tier=1,
    is_ga=1,
    description="ElevenLabs Multilingual v2 at Creator tier. Best-in-class prosody + emotional range. $0.30/1K chars.",
)
_add(
    "elevenlabs/turbo-v2.5",
    name="ElevenLabs: Turbo v2.5",
    provider="elevenlabs",
    service_type="tts",
    input_cost_per_m=per_1k_chars(0.165),
    pricing_unit="M-chars",
    quality_tier=2,
    is_ga=1,
    description="ElevenLabs Turbo v2.5. Half the cost of Multilingual v2 with mild quality trade-off. $0.165/1K chars.",
)
_add(
    "elevenlabs/flash-v2.5",
    name="ElevenLabs: Flash v2.5 (lowest latency)",
    provider="elevenlabs",
    service_type="tts",
    input_cost_per_m=per_1k_chars(0.165),
    pricing_unit="M-chars",
    quality_tier=2,
    is_ga=1,
    description="ElevenLabs Flash v2.5. ~75 ms latency, optimized for realtime conversational agents. $0.165/1K chars.",
)
_add(
    "elevenlabs/eleven-v3-alpha",
    name="ElevenLabs: v3 (alpha preview)",
    provider="elevenlabs",
    service_type="tts",
    input_cost_per_m=per_1k_chars(0.30),
    pricing_unit="M-chars",
    quality_tier=1,
    is_ga=0,
    description="ElevenLabs v3 alpha. Next-gen prosody / emotional control. Preview pricing matches Multilingual v2.",
)
_add(
    "openai/tts-1",
    name="OpenAI: TTS-1",
    provider="openai",
    service_type="tts",
    input_cost_per_m=per_1k_chars(0.015),
    pricing_unit="M-chars",
    quality_tier=3,
    is_ga=1,
    description="OpenAI TTS-1 standard. 6 voices, English-leaning. $0.015/1K chars — cheapest tier-1 vendor.",
)
_add(
    "openai/tts-1-hd",
    name="OpenAI: TTS-1 HD",
    provider="openai",
    service_type="tts",
    input_cost_per_m=per_1k_chars(0.030),
    pricing_unit="M-chars",
    quality_tier=2,
    is_ga=1,
    description="OpenAI TTS-1 HD. Higher fidelity than TTS-1. $0.030/1K chars.",
)
_add(
    "openai/gpt-4o-mini-tts",
    name="OpenAI: GPT-4o Mini TTS",
    provider="openai",
    service_type="tts",
    input_cost_per_m=per_1k_chars(0.015),
    pricing_unit="M-chars",
    quality_tier=2,
    is_ga=1,
    description="OpenAI 4o-mini-tts. Controllable speaking style via prompt. $0.015/1K chars (approx, billed by audio output).",
)
_add(
    "cartesia/sonic-2",
    name="Cartesia: Sonic 2",
    provider="cartesia",
    service_type="tts",
    input_cost_per_m=per_1k_chars(0.04),
    pricing_unit="M-chars",
    quality_tier=2,
    is_ga=1,
    description="Cartesia Sonic 2. ~75 ms latency, voice cloning, multilingual. Competitive with ElevenLabs Flash. $0.04/1K chars.",
)
_add(
    "playht/play-3.0-mini",
    name="PlayHT: Play 3.0 Mini",
    provider="playht",
    service_type="tts",
    input_cost_per_m=per_1k_chars(0.034),
    pricing_unit="M-chars",
    quality_tier=2,
    is_ga=1,
    description="PlayHT Play 3.0 Mini. Realtime conversational TTS, voice cloning. ~$0.034/1K chars.",
)
_add(
    "google/cloud-tts-wavenet",
    name="Google: Cloud TTS (WaveNet)",
    provider="google",
    service_type="tts",
    input_cost_per_m=16.0,  # $16/M chars
    pricing_unit="M-chars",
    quality_tier=3,
    is_ga=1,
    description="Google Cloud TTS with WaveNet voices. 220+ voices across 40+ languages. $16/M characters.",
)
_add(
    "azure/speech-tts-neural",
    name="Azure: Speech TTS (Neural)",
    provider="azure",
    service_type="tts",
    input_cost_per_m=16.0,
    pricing_unit="M-chars",
    quality_tier=3,
    is_ga=1,
    description="Azure Cognitive Services Neural TTS. 140+ languages/locales, custom voice support. $16/M characters.",
)

# ---------- Music / audio gen ----------
_add(
    "suno/v4",
    name="Suno: v4 (music gen)",
    provider="suno",
    service_type="music_gen",
    input_cost_per_m=per_min(0.10),
    pricing_unit="audio-min",
    quality_tier=1,
    is_ga=1,
    description="Suno v4 song generation. Full vocals + instrumentation from prompt or lyrics. ~$0.10/song-minute (credit-based; price approximate).",
)
_add(
    "udio/v1",
    name="Udio: v1 (music gen)",
    provider="udio",
    service_type="music_gen",
    input_cost_per_m=per_min(0.10),
    pricing_unit="audio-min",
    quality_tier=2,
    is_ga=1,
    description="Udio v1 music generation. Competitor to Suno; strong on instrumental + remix workflows.",
)
_add(
    "stability/stable-audio-2",
    name="Stability: Stable Audio 2",
    provider="stability",
    service_type="music_gen",
    input_cost_per_m=per_min(0.30),
    pricing_unit="audio-min",
    quality_tier=2,
    is_ga=1,
    description="Stability AI Stable Audio 2. Sound effects + music up to 3 min. Via Replicate / Stability API.",
)
_add(
    "elevenlabs/sound-effects",
    name="ElevenLabs: Sound Effects",
    provider="elevenlabs",
    service_type="music_gen",
    input_cost_per_m=per_1k_chars(0.30),
    pricing_unit="M-chars",
    quality_tier=2,
    is_ga=1,
    description="ElevenLabs Sound Effects. Text-to-SFX up to 22 sec per generation. Billed per character of prompt.",
)

# ---------- Self-hosted TTS (operator-run GPU pod, not an API vendor) ----------
_add(
    "coqui/xtts-v2",
    name="Coqui: XTTS-v2 (self-hosted)",
    provider="coqui",
    service_type="tts",
    input_cost_per_m=0,  # No per-char API cost — pod electricity + GPU rent only
    pricing_unit="M-chars",
    quality_tier=3,
    is_ga=1,
    description=(
        "Coqui XTTS-v2 — open-weight multilingual TTS (16+ langs, voice cloning, "
        "Apache 2.0). Runs on operator's own GPU pod (T4 or L40S tier; warm pod "
        "for sub-second TTFA). $0 per-character cost but pod overhead (electricity "
        "+ GPU rent) only pays off above ~100K chars/day. Fabrik default TTS "
        "fallback per .windsurf/rules/ai/10-speech-audio.md."
    ),
)

# ---------- Translation ----------
_add(
    "deepl/deepl-pro",
    name="DeepL: Pro Machine Translation",
    provider="deepl",
    service_type="translation",
    is_translation_capable=1,
    input_cost_per_m=25.0,
    pricing_unit="M-chars",
    quality_tier=2,
    is_ga=1,
    description="DeepL Pro MT. Best-in-class for EU language pairs + 30+ languages, formality control, glossary support. $25/M characters. Used by AutoPoly + Fabrik language pipelines.",
)
_add(
    "deepl/deepl-free",
    name="DeepL: Free Tier",
    provider="deepl",
    service_type="translation",
    is_translation_capable=1,
    input_cost_per_m=0,
    pricing_unit="M-chars",
    quality_tier=2,
    is_ga=1,
    description="DeepL Free. 500K chars/month limit, same quality as Pro. Useful for low-volume background translation.",
)
_add(
    "google/cloud-translate-v3",
    name="Google: Cloud Translation v3 (NMT)",
    provider="google",
    service_type="translation",
    is_translation_capable=1,
    input_cost_per_m=20.0,
    pricing_unit="M-chars",
    quality_tier=3,
    is_ga=1,
    description="Google Cloud Translation v3. 130+ languages, glossary + custom-model support. $20/M characters (basic NMT model).",
)
_add(
    "azure/translator-text",
    name="Azure: Translator Text",
    provider="azure",
    service_type="translation",
    is_translation_capable=1,
    input_cost_per_m=10.0,
    pricing_unit="M-chars",
    quality_tier=3,
    is_ga=1,
    description="Azure Translator Text S1 tier. 100+ languages, document translation + custom translator. $10/M characters.",
)
_add(
    "amazon/translate",
    name="Amazon: Translate",
    provider="amazon",
    service_type="translation",
    is_translation_capable=1,
    input_cost_per_m=15.0,
    pricing_unit="M-chars",
    quality_tier=3,
    is_ga=1,
    description="Amazon Translate. 75+ languages, active custom-terminology API. $15/M characters.",
)
# qwen-mt-turbo is seeded by seed_translation_and_stt.py path; left as-is.

# ---------- Image generation ----------
_add(
    "recraft/v4.1",
    name="Recraft: v4.1 (illustration / SVG)",
    provider="recraft",
    service_type="image_gen",
    input_cost_per_m=per_image(0.04),
    pricing_unit="image",
    quality_tier=1,
    is_ga=1,
    description="Recraft v4.1 — Fabrik default for branded / vector / illustration. Native SVG output, style consistency. Used by /opt/brand-identiy-creator. $0.04/image.",
)
_add(
    "recraft/v4-icon",
    name="Recraft: v4 Icon",
    provider="recraft",
    service_type="image_gen",
    input_cost_per_m=per_image(0.04),
    pricing_unit="image",
    quality_tier=2,
    is_ga=1,
    description="Recraft v4 Icon mode. Optimized for pictogram / icon generation with custom styles. $0.04/image.",
)
_add(
    "recraft/v3",
    name="Recraft: v3",
    provider="recraft",
    service_type="image_gen",
    input_cost_per_m=per_image(0.04),
    pricing_unit="image",
    quality_tier=2,
    is_ga=1,
    description="Recraft v3 (older). Still supported for projects that pinned this generation. $0.04/image.",
)
_add(
    "bfl/flux-pro-1.1",
    name="BFL: FLUX Pro 1.1 (photoreal)",
    provider="bfl",
    service_type="image_gen",
    input_cost_per_m=per_image(0.04),
    pricing_unit="image",
    quality_tier=1,
    is_ga=1,
    description="FLUX Pro 1.1 via Black Forest Labs. Fabrik default photoreal generator; owned BFL_API_KEY. $0.04/image (1024×1024).",
)
_add(
    "bfl/flux-pro-1.1-ultra",
    name="BFL: FLUX Pro 1.1 Ultra",
    provider="bfl",
    service_type="image_gen",
    input_cost_per_m=per_image(0.06),
    pricing_unit="image",
    quality_tier=1,
    is_ga=1,
    description="FLUX Pro 1.1 Ultra — 4MP output, raw-mode option for natural photography. $0.06/image.",
)
_add(
    "bfl/flux-pro",
    name="BFL: FLUX Pro 1.0",
    provider="bfl",
    service_type="image_gen",
    input_cost_per_m=per_image(0.05),
    pricing_unit="image",
    quality_tier=2,
    is_ga=1,
    description="FLUX Pro 1.0 — earlier flagship. Use only for projects pinned to this version. $0.05/image.",
)
_add(
    "bfl/flux-dev",
    name="BFL: FLUX Dev (12B open-weight)",
    provider="bfl",
    service_type="image_gen",
    input_cost_per_m=per_image(0.025),
    pricing_unit="image",
    quality_tier=2,
    is_ga=1,
    description="FLUX Dev open-weight via BFL hosted API. Non-commercial license; good for iteration. $0.025/image.",
)
_add(
    "bfl/flux-schnell",
    name="BFL: FLUX Schnell (1-4 step)",
    provider="bfl",
    service_type="image_gen",
    input_cost_per_m=per_image(0.003),
    pricing_unit="image",
    quality_tier=2,
    is_ga=1,
    description="FLUX Schnell — distilled checkpoint, ~13× cheaper than Pro. $0.003/image. Good for thumbnails / ideation.",
)
_add(
    "bfl/flux-fill",
    name="BFL: FLUX Fill (inpaint)",
    provider="bfl",
    service_type="image_gen",
    input_cost_per_m=per_image(0.05),
    pricing_unit="image",
    quality_tier=2,
    is_ga=1,
    description="FLUX Fill — inpainting / outpainting variant. $0.05/image.",
)
_add(
    "bfl/flux-redux",
    name="BFL: FLUX Redux (img2img)",
    provider="bfl",
    service_type="image_gen",
    input_cost_per_m=per_image(0.025),
    pricing_unit="image",
    quality_tier=2,
    is_ga=1,
    description="FLUX Redux — image variation / img2img. $0.025/image.",
)
_add(
    "stability/sd3.5-large",
    name="Stability AI: SD 3.5 Large",
    provider="stability",
    service_type="image_gen",
    input_cost_per_m=per_image(0.065),
    pricing_unit="image",
    quality_tier=2,
    is_ga=1,
    description="Stable Diffusion 3.5 Large via Stability API. 8B params, strong text rendering. $0.065/image.",
)
_add(
    "stability/sd3.5-large-turbo",
    name="Stability AI: SD 3.5 Large Turbo",
    provider="stability",
    service_type="image_gen",
    input_cost_per_m=per_image(0.04),
    pricing_unit="image",
    quality_tier=2,
    is_ga=1,
    description="SD 3.5 Large Turbo — fewer steps, ~38 %% cheaper. $0.04/image.",
)
_add(
    "stability/stable-image-ultra",
    name="Stability AI: Stable Image Ultra",
    provider="stability",
    service_type="image_gen",
    input_cost_per_m=per_image(0.08),
    pricing_unit="image",
    quality_tier=1,
    is_ga=1,
    description="Stability's flagship — best SD3 output, photoreal + typography. $0.08/image.",
)
_add(
    "stability/stable-image-core",
    name="Stability AI: Stable Image Core",
    provider="stability",
    service_type="image_gen",
    input_cost_per_m=per_image(0.03),
    pricing_unit="image",
    quality_tier=2,
    is_ga=1,
    description="Stability Core — fast SD-based generation. $0.03/image.",
)
_add(
    "stability/sdxl",
    name="Stability AI: SDXL (via Replicate)",
    provider="stability",
    service_type="image_gen",
    input_cost_per_m=per_image(0.0023),
    pricing_unit="image",
    quality_tier=3,
    is_ga=1,
    description="SDXL via Replicate (`stability-ai/sdxl`). Open-weights flexibility (LoRAs, ControlNet). ~$0.0023/image via pay-per-second.",
)
_add(
    "openai/dall-e-3",
    name="OpenAI: DALL-E 3 (standard)",
    provider="openai",
    service_type="image_gen",
    input_cost_per_m=per_image(0.04),
    pricing_unit="image",
    quality_tier=2,
    is_ga=1,
    description="DALL-E 3 standard quality. 1024×1024 default; HD variant available. $0.04/image standard.",
)
_add(
    "openai/dall-e-3-hd",
    name="OpenAI: DALL-E 3 (HD)",
    provider="openai",
    service_type="image_gen",
    input_cost_per_m=per_image(0.08),
    pricing_unit="image",
    quality_tier=1,
    is_ga=1,
    description="DALL-E 3 HD. Higher detail. $0.08/image (1024×1024) or $0.12 wide formats.",
)
_add(
    "openai/gpt-image-1",
    name="OpenAI: GPT-Image-1",
    provider="openai",
    service_type="image_gen",
    input_cost_per_m=per_image(0.04),
    pricing_unit="image",
    quality_tier=1,
    is_ga=1,
    description="OpenAI GPT-Image-1 (the model behind ChatGPT's native image gen). Strong text rendering. ~$0.04/image equivalent (billed by input/output tokens; this is a rough per-image proxy).",
)
_add(
    "google/imagen-3",
    name="Google: Imagen 3",
    provider="google",
    service_type="image_gen",
    input_cost_per_m=per_image(0.04),
    pricing_unit="image",
    quality_tier=2,
    is_ga=1,
    description="Google Imagen 3 via Vertex AI. Photoreal + typography. $0.04/image.",
)
_add(
    "google/imagen-4",
    name="Google: Imagen 4",
    provider="google",
    service_type="image_gen",
    input_cost_per_m=per_image(0.04),
    pricing_unit="image",
    quality_tier=1,
    is_ga=1,
    description="Google Imagen 4. Successor to Imagen 3 with better text rendering + prompt adherence. $0.04/image standard.",
)
_add(
    "ideogram/v3",
    name="Ideogram: v3",
    provider="ideogram",
    service_type="image_gen",
    input_cost_per_m=per_image(0.10),
    pricing_unit="image",
    quality_tier=1,
    is_ga=1,
    description="Ideogram v3. Best-in-class typography in generated images, magic prompts. $0.10/image.",
)
_add(
    "ideogram/v2",
    name="Ideogram: v2",
    provider="ideogram",
    service_type="image_gen",
    input_cost_per_m=per_image(0.08),
    pricing_unit="image",
    quality_tier=2,
    is_ga=1,
    description="Ideogram v2. Strong typography baseline; cheaper than v3. $0.08/image.",
)
_add(
    "recraft/v4-svg",
    name="Recraft: v4 (SVG vector)",
    provider="recraft",
    service_type="image_gen",
    input_cost_per_m=per_image(0.08),
    pricing_unit="image",
    quality_tier=1,
    is_ga=1,
    description="Recraft v4 SVG mode. True vector output; brand-identiy-creator's logo path uses this. $0.08/image.",
)
_add(
    "recraft/v2",
    name="Recraft: v2",
    provider="recraft",
    service_type="image_gen",
    input_cost_per_m=per_image(0.04),
    pricing_unit="image",
    quality_tier=3,
    is_ga=1,
    description="Recraft v2 (legacy). Kept for projects pinned to this generation. $0.04/image.",
)
_add(
    "recraft/nano-banana",
    name="Recraft: Nano Banana (image editing)",
    provider="recraft",
    service_type="image_gen",
    input_cost_per_m=per_image(0.04),
    pricing_unit="image",
    quality_tier=1,
    is_ga=1,
    description="Recraft Nano Banana — state-of-the-art image editing via natural language (color swaps, object changes, add/remove elements). Pricing approx $0.04/edit; verify on recraft.ai/ai-models.",
)

# ---------- Video generation ----------
_add(
    "runway/gen-3-alpha",
    name="Runway: Gen-3 Alpha",
    provider="runway",
    service_type="video_gen",
    input_cost_per_m=per_video_sec(0.10),
    pricing_unit="video-sec",
    quality_tier=1,
    is_ga=1,
    description="Runway Gen-3 Alpha. Text-to-video + image-to-video up to 10s. $0.10/video-second.",
)
_add(
    "runway/gen-3-alpha-turbo",
    name="Runway: Gen-3 Alpha Turbo",
    provider="runway",
    service_type="video_gen",
    input_cost_per_m=per_video_sec(0.05),
    pricing_unit="video-sec",
    quality_tier=2,
    is_ga=1,
    description="Runway Gen-3 Alpha Turbo. Half the cost, fast iteration. $0.05/video-second.",
)
_add(
    "runway/gen-4",
    name="Runway: Gen-4",
    provider="runway",
    service_type="video_gen",
    input_cost_per_m=per_video_sec(0.12),
    pricing_unit="video-sec",
    quality_tier=1,
    is_ga=1,
    description="Runway Gen-4. Latest flagship. $0.12/video-second.",
)
_add(
    "luma/dream-machine-1.6",
    name="Luma: Dream Machine 1.6",
    provider="luma",
    service_type="video_gen",
    input_cost_per_m=per_video_sec(0.08),
    pricing_unit="video-sec",
    quality_tier=2,
    is_ga=1,
    description="Luma Dream Machine. ~5s clips at 1080p. $0.08/sec ($0.40/5s clip).",
)
_add(
    "luma/ray-2",
    name="Luma: Ray 2",
    provider="luma",
    service_type="video_gen",
    input_cost_per_m=per_video_sec(0.08),
    pricing_unit="video-sec",
    quality_tier=1,
    is_ga=1,
    description="Luma Ray 2. Better motion + physics than Dream Machine. $0.08/sec.",
)
_add(
    "kling/v2",
    name="Kling AI: v2",
    provider="kling",
    service_type="video_gen",
    input_cost_per_m=per_video_sec(0.06),
    pricing_unit="video-sec",
    quality_tier=1,
    is_ga=1,
    description="Kling AI v2. Up to 2-minute videos, image-to-video + extend. $0.06/sec ($0.30/5s clip).",
)
_add(
    "kling/v1.5",
    name="Kling AI: v1.5",
    provider="kling",
    service_type="video_gen",
    input_cost_per_m=per_video_sec(0.04),
    pricing_unit="video-sec",
    quality_tier=2,
    is_ga=1,
    description="Kling v1.5. Cheaper baseline. $0.04/sec.",
)
_add(
    "pika/v2",
    name="Pika Labs: Pika 2.0",
    provider="pika",
    service_type="video_gen",
    input_cost_per_m=per_video_sec(0.09),
    pricing_unit="video-sec",
    quality_tier=2,
    is_ga=1,
    description="Pika 2.0. Strong on stylized + animated content. ~$0.09/sec (credit-based).",
)
_add(
    "google/veo-3",
    name="Google: Veo 3",
    provider="google",
    service_type="video_gen",
    input_cost_per_m=per_video_sec(0.75),
    pricing_unit="video-sec",
    quality_tier=1,
    is_ga=1,
    description="Google Veo 3. State-of-the-art generation incl. native audio. $0.75/video-second (premium tier).",
)
_add(
    "google/veo-2",
    name="Google: Veo 2",
    provider="google",
    service_type="video_gen",
    input_cost_per_m=per_video_sec(0.50),
    pricing_unit="video-sec",
    quality_tier=2,
    is_ga=1,
    description="Google Veo 2. Predecessor to Veo 3. $0.50/video-second.",
)
_add(
    "openai/sora-turbo",
    name="OpenAI: Sora Turbo",
    provider="openai",
    service_type="video_gen",
    input_cost_per_m=per_video_sec(0.10),
    pricing_unit="video-sec",
    quality_tier=1,
    is_ga=1,
    description="OpenAI Sora Turbo. Up to 20s clips at 1080p. Pricing varies by resolution + duration; ~$0.10/sec proxy.",
)
_add(
    "heygen/video",
    name="HeyGen: Video (avatar)",
    provider="heygen",
    service_type="video_gen",
    input_cost_per_m=per_video_sec(0.30),
    pricing_unit="video-sec",
    quality_tier=2,
    is_ga=1,
    description="HeyGen avatar-driven video. Talking-head + voice clone synthesis. ~$0.30/sec (subscription-based; this is per-credit proxy).",
)

# ---------- OCR ----------
_add(
    "mistral/ocr",
    name="Mistral: OCR",
    provider="mistral",
    service_type="ocr",
    input_cost_per_m=per_page(0.001),
    pricing_unit="page",
    quality_tier=1,
    is_ga=1,
    description="Mistral OCR. Strong on PDF + handwritten + multilingual + math. $0.001/page (= $1/1K pages).",
)
_add(
    "amazon/textract",
    name="Amazon: Textract",
    provider="amazon",
    service_type="ocr",
    input_cost_per_m=per_page(0.0015),
    pricing_unit="page",
    quality_tier=2,
    is_ga=1,
    description="AWS Textract. Forms + tables + queries. $0.0015/page basic; $0.05/page for forms+tables.",
)
_add(
    "google/document-ai",
    name="Google: Document AI",
    provider="google",
    service_type="ocr",
    input_cost_per_m=per_page(0.0015),
    pricing_unit="page",
    quality_tier=2,
    is_ga=1,
    description="Google Document AI (Enterprise Document OCR processor). $0.0015/page; higher for specialist processors.",
)
_add(
    "azure/document-intelligence",
    name="Azure: Document Intelligence (Read)",
    provider="azure",
    service_type="ocr",
    input_cost_per_m=per_page(0.0015),
    pricing_unit="page",
    quality_tier=2,
    is_ga=1,
    description="Azure Document Intelligence Read model. Layout-aware OCR with table/key-value extraction. $0.0015/page.",
)
_add(
    "llamaindex/llamaparse",
    name="LlamaIndex: LlamaParse",
    provider="llamaindex",
    service_type="ocr",
    input_cost_per_m=per_page(0.003),
    pricing_unit="page",
    quality_tier=2,
    is_ga=1,
    description="LlamaParse. PDF + table-heavy doc parsing tuned for RAG ingestion. $0.003/page (premium tier).",
)


_UPSERT_FIELDS = (
    "name",
    "provider",
    "service_type",
    "pricing_unit",
    "input_cost_per_m",
    "output_cost_per_m",
    "context_window_k",
    "quality_tier",
    "is_ga",
    "description",
    "via_openrouter",
    "via_kilo",
    "is_stt_capable",
    "is_translation_capable",
    "stt_quality",
)


def upsert(conn: sqlite3.Connection, today: str) -> dict[str, int]:
    counts = {"inserted": 0, "updated": 0}
    for mid, spec in VENDORS.items():
        # Default gateway flags (direct-vendor specialists are NOT on OR/Kilo)
        spec.setdefault("via_openrouter", 0)
        spec.setdefault("via_kilo", 0)
        spec.setdefault("output_cost_per_m", 0)
        spec.setdefault("context_window_k", 0)
        cur = conn.execute(
            "SELECT id, status, discard_reason FROM agents WHERE id = ?", (mid,)
        ).fetchone()
        if cur:
            sets = []
            vals: list = []
            for field in _UPSERT_FIELDS:
                if field in spec:
                    sets.append(f"{field} = ?")
                    vals.append(spec[field])
            sets.append("last_verified = ?")
            vals.append(today)
            # Reactivate ONLY when the row was deprecated by an automated
            # verifier (e.g. the OpenRouter catalog verifier sweeping
            # DashScope-only rows before the exemption). An operator-set
            # discard_reason — anything that doesn't mention "verifier" —
            # MUST be respected so the operator can suppress a vendor by
            # editing the row directly.
            cur_status, cur_reason = cur[1], cur[2] or ""
            verifier_set = "verifier" in cur_reason.lower()
            if cur_status != "deprecated" or verifier_set:
                sets.append("status = 'active'")
                sets.append("discard_reason = NULL")
            vals.append(mid)
            conn.execute(f"UPDATE agents SET {', '.join(sets)} WHERE id = ?", vals)
            counts["updated"] += 1
        else:
            cols = ["id", "api_id", "status", "last_verified", "created_at", "updated_at"]
            placeholders = ["?", "?", "'active'", "?", "?", "?"]
            vals = [mid, mid.split("/")[-1], today, f"{today} 00:00:00", f"{today} 00:00:00"]
            for field in _UPSERT_FIELDS:
                if field in spec:
                    cols.append(field)
                    placeholders.append("?")
                    vals.append(spec[field])
            conn.execute(
                f"INSERT INTO agents ({', '.join(cols)}) VALUES ({', '.join(placeholders)})",
                vals,
            )
            counts["inserted"] += 1
    return counts


def main() -> int:
    today = _today()
    conn = sqlite3.connect(DB_PATH)
    try:
        counts = upsert(conn, today)
        conn.commit()
    finally:
        conn.close()
    _log(
        f"direct vendors: {len(VENDORS)} specs; inserted={counts['inserted']} updated={counts['updated']}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
