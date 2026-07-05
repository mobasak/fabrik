# AFTER-EDIT: scripts/kilo-benchmarks/tests/test_microbench_specialty.py
"""Provider pricing snapshot 2026-07-03 — re-verify quarterly.

Update this table AND run test_pricing_table_covers_all_active_specialty_rows
whenever a new non-LLM model is seeded into the DB. Missing entries would
silently break the cost cap on the specialty bench.

Plan 2026-07-03-plan-1-full-speed-coverage-close.md Phase B.2.
"""

from __future__ import annotations

PRICING: dict[str, dict] = {
    # ---------- BFL routed via Fal.ai (U-B.0.1' pivot) ----------
    # BFL v1 endpoints return 404/403 with our key; Fal.ai mirrors flux-1.
    # Prices are Fal.ai's (near-parity with BFL direct on schnell/dev/pro).
    "bfl/flux-schnell": {"per_image": 0.003, "via": "fal_ai"},
    "bfl/flux-dev": {"per_image": 0.025, "via": "fal_ai"},
    "bfl/flux-pro": {"per_image": 0.05, "via": "fal_ai"},
    "bfl/flux-pro-1.1": {"per_image": 0.04, "via": "fal_ai"},
    "bfl/flux-pro-1.1-ultra": {"per_image": 0.06, "via": "fal_ai"},
    "bfl/flux-fill": {"per_image": 0.05, "via": "fal_ai"},
    "bfl/flux-redux": {"per_image": 0.025, "via": "fal_ai"},
    # ---------- Recraft direct ----------
    # Live probe 2026-07-03: 40 credits per recraftv3 image = ~$0.04
    "recraft/v3": {"per_image": 0.04, "via": "recraft_direct"},
    "recraft/nano-banana": {"per_image": 0.02, "via": "recraft_direct"},
    # ---------- Stability via Replicate ----------
    "stability/sd3.5-large": {"per_image": 0.065, "via": "replicate"},
    "stability/sd3.5-large-turbo": {"per_image": 0.04, "via": "replicate"},
    "stability/sdxl": {"per_image": 0.003, "via": "replicate"},
    # ---------- Recraft via Replicate (official-model endpoint) ----------
    # Uses `/v1/models/{owner}/{name}/predictions` — no version hash needed.
    # Same model as `recraft/v3` direct route but reached through the
    # existing REPLICATE_API_TOKEN (no separate RECRAFT_API_KEY required in
    # projects that already talk to Replicate — e.g. /opt/brand-identiy-creator).
    "recraft-ai/recraft-v3": {"per_image": 0.04, "via": "replicate_official"},
    "recraft-ai/recraft-v4": {"per_image": 0.04, "via": "replicate_official", "estimate": True},
    "recraft-ai/recraft-v4-svg": {"per_image": 0.06, "via": "replicate_official", "estimate": True},
    "recraft-ai/recraft-v4.1": {"per_image": 0.04, "via": "replicate_official", "estimate": True},
    "recraft-ai/recraft-v4.1-svg": {"per_image": 0.06, "via": "replicate_official", "estimate": True},
    # ---------- ElevenLabs direct ----------
    # Creator tier $22/mo = $0.00003/char, ~30 chars/word.
    "elevenlabs/multilingual-v2": {"per_char": 0.00003, "via": "elevenlabs_direct"},
    "elevenlabs/turbo-v2.5": {"per_char": 0.00003, "via": "elevenlabs_direct"},
    "elevenlabs/eleven-v3-alpha": {"per_char": 0.00003, "via": "elevenlabs_direct"},
    "elevenlabs/sound-effects": {"per_generation": 0.02, "via": "elevenlabs_direct"},
    # ---------- Stability music via Replicate ----------
    "stability/stable-audio-2": {"per_generation": 0.10, "via": "replicate"},
    # ---------- OpenAI direct (Whisper STT) ----------
    "openai/whisper-large-v3": {"per_minute": 0.006, "via": "openai_direct"},
    # ---------- Alibaba DashScope (Qwen-MT translation) ----------
    "qwen/qwen-mt-turbo": {"per_char": 0.000018, "via": "dashscope_direct"},
    # ---------- Post-A.7 expansion (B.3.0, review pass 10) ----------
    # Conservative defaults + best-known routing. Client overrides with real
    # cost from provider response. `estimate: True` flag lets B.2's drift
    # test flag entries that should be tightened once verified live.
    # -- BFL Flux 2 family via Fal.ai --
    "black-forest-labs/flux.2-flex": {"per_image": 0.04, "via": "fal_ai", "estimate": True},
    "black-forest-labs/flux.2-klein-4b": {"per_image": 0.02, "via": "fal_ai", "estimate": True},
    "black-forest-labs/flux.2-max": {"per_image": 0.08, "via": "fal_ai", "estimate": True},
    "black-forest-labs/flux.2-pro": {"per_image": 0.06, "via": "fal_ai", "estimate": True},
    # -- ByteDance / Google / Microsoft / xAI image via OpenRouter --
    "bytedance-seed/seedream-4.5": {"per_image": 0.05, "via": "openrouter", "estimate": True},
    "google/gemini-2.5-flash-image": {"per_image": 0.04, "via": "openrouter", "estimate": True},
    "google/gemini-3-pro-image": {"per_image": 0.08, "via": "openrouter", "estimate": True},
    "google/gemini-3-pro-image-preview": {"per_image": 0.08, "via": "openrouter", "estimate": True},
    "google/gemini-3.1-flash-image": {"per_image": 0.04, "via": "openrouter", "estimate": True},
    "google/gemini-3.1-flash-image-preview": {
        "per_image": 0.04,
        "via": "openrouter",
        "estimate": True,
    },
    "microsoft/mai-image-2.5": {"per_image": 0.05, "via": "openrouter", "estimate": True},
    "openai/gpt-5-image": {"per_image": 0.05, "via": "openrouter", "estimate": True},
    "openai/gpt-5-image-mini": {"per_image": 0.03, "via": "openrouter", "estimate": True},
    "openai/gpt-5.4-image-2": {"per_image": 0.06, "via": "openrouter", "estimate": True},
    "openai/gpt-image-1-mini": {"per_image": 0.03, "via": "openrouter", "estimate": True},
    "openai/gpt-image-2": {"per_image": 0.05, "via": "openrouter", "estimate": True},
    "sourceful/riverflow-v2-fast": {"per_image": 0.03, "via": "openrouter", "estimate": True},
    "sourceful/riverflow-v2.5-fast": {"per_image": 0.03, "via": "openrouter", "estimate": True},
    "x-ai/grok-imagine-image-quality": {"per_image": 0.05, "via": "openrouter", "estimate": True},
    "recraft/recraft-v4.1": {"per_image": 0.04, "via": "recraft_direct", "estimate": True},
    # -- STT expansions --
    "google/chirp-3": {"per_minute": 0.024, "via": "openrouter", "estimate": True},
    "microsoft/mai-transcribe-1.5": {"per_minute": 0.020, "via": "openrouter", "estimate": True},
    "mistralai/voxtral-mini-transcribe": {
        "per_minute": 0.010,
        "via": "openrouter",
        "estimate": True,
    },
    "nvidia/parakeet-tdt-0.6b-v3": {"per_minute": 0.010, "via": "openrouter", "estimate": True},
    "openai/whisper-1": {"per_minute": 0.006, "via": "openai_direct"},
    "openai/whisper-large-v3-turbo": {"per_minute": 0.006, "via": "openai_direct"},
    "qwen/qwen3-asr-flash-2026-02-10": {"per_minute": 0.010, "via": "openrouter", "estimate": True},
    # -- TTS expansions --
    "canopylabs/orpheus-3b-0.1-ft": {"per_char": 0.00003, "via": "openrouter", "estimate": True},
    "google/gemini-3.1-flash-tts-preview": {
        "per_char": 0.00003,
        "via": "openrouter",
        "estimate": True,
    },
    "hexgrad/kokoro-82m": {"per_char": 0.00002, "via": "openrouter", "estimate": True},
    "microsoft/mai-voice-2": {"per_char": 0.00003, "via": "openrouter", "estimate": True},
    "mistralai/voxtral-mini-tts-2603": {"per_char": 0.00003, "via": "openrouter", "estimate": True},
    "sesame/csm-1b": {"per_char": 0.00002, "via": "openrouter", "estimate": True},
    "x-ai/grok-voice-tts-1.0": {"per_char": 0.00003, "via": "openrouter", "estimate": True},
    "zyphra/zonos-v0.1-hybrid": {"per_char": 0.00003, "via": "openrouter", "estimate": True},
    "zyphra/zonos-v0.1-transformer": {"per_char": 0.00003, "via": "openrouter", "estimate": True},
}


# Per-model prompt lengths actually used by the specialty clients — keep in
# sync with each client's BENCH_TEXT so dry-run cost previews match real spend.
# Values verified via `len(client.BENCH_TEXT)` at import time (see the drift
# test in test_microbench_specialty).
_BENCH_CHARS_BY_MODEL = {
    "qwen/qwen-mt-turbo": 64,  # dashscope_translation.BENCH_TEXT
}
_DEFAULT_TTS_CHARS = 213  # elevenlabs_tts.BENCH_TEXT length
_DEFAULT_STT_MINUTES = 10 / 60.0  # openai_whisper.SILENCE_SECONDS


def estimate_cost(
    model_id: str, *, chars: int | None = None, minutes: float | None = None
) -> float:
    """Estimate cost per single bench call for a specialty model.

    Char counts come from a per-model table so translation (64 chars) isn't
    over-estimated as TTS (213 chars). Callers may still override via `chars=`
    for a custom sizing.
    """
    p = PRICING.get(model_id)
    if p is None:
        return 0.0
    if "per_image" in p:
        return p["per_image"]
    if "per_generation" in p:
        return p["per_generation"]
    if "per_char" in p:
        c = chars if chars is not None else _BENCH_CHARS_BY_MODEL.get(model_id, _DEFAULT_TTS_CHARS)
        return p["per_char"] * c
    if "per_minute" in p:
        m = minutes if minutes is not None else _DEFAULT_STT_MINUTES
        return p["per_minute"] * m
    return 0.0
