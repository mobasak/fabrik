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
}


def estimate_cost(model_id: str, *, chars: int = 200, minutes: float = 0.17) -> float:
    """Estimate cost per single bench call for a specialty model.

    `chars=200` matches the fixed TTS prompt. `minutes=0.17` = 10 seconds
    of audio for Whisper. Image gen is per_image (no arg needed).
    """
    p = PRICING.get(model_id)
    if p is None:
        return 0.0
    if "per_image" in p:
        return p["per_image"]
    if "per_generation" in p:
        return p["per_generation"]
    if "per_char" in p:
        return p["per_char"] * chars
    if "per_minute" in p:
        return p["per_minute"] * minutes
    return 0.0
