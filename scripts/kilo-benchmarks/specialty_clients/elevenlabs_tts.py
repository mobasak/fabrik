# AFTER-EDIT: scripts/kilo-benchmarks/tests/test_specialty_clients/test_elevenlabs_tts.py
"""ElevenLabs REST TTS client.

ElevenLabs TTS API 2026-07-03 (live-verified):
  POST https://api.elevenlabs.io/v1/text-to-speech/{voice_id}
  Headers: {"xi-api-key": "<ELEVENLABS_API_KEY>", "Content-Type": "application/json"}
  Body:    {"text": "<200-char sample>"}
  Response 200: binary audio/mpeg
  Default voice_id (verified): CwhRBWXzGAHq8TQ4Fs17 (Roger, premade voice)
"""

from __future__ import annotations

import time

import requests

DEFAULT_VOICE_ID = "CwhRBWXzGAHq8TQ4Fs17"
BENCH_TEXT = (
    "Kilo benchmark. This is a fixed two hundred character "
    "sample to measure the wall clock time from POST send to "
    "complete audio bytes received back from the ElevenLabs "
    "text to speech endpoint. Cheese pizza pineapple."
)  # ~200 chars


def bench_one(model_id: str, api_key: str) -> dict:
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{DEFAULT_VOICE_ID}"
    headers = {"xi-api-key": api_key, "Content-Type": "application/json"}
    body = {"text": BENCH_TEXT}
    t0 = time.monotonic()
    try:
        r = requests.post(url, json=body, headers=headers, timeout=60)
        if r.status_code >= 400:
            return _err(f"http {r.status_code}: {r.text[:200]}")
        if len(r.content) < 100:
            return _err(f"suspiciously small audio: {len(r.content)} bytes")
        perf_seconds = time.monotonic() - t0
        # Cost from PRICING (per-char) — actual char count in prompt
        cost = len(BENCH_TEXT) * 0.00003
        return {
            "perf_seconds": round(perf_seconds, 2),
            "cost_usd": round(cost, 8),
            "error": None,
        }
    except requests.exceptions.RequestException as e:
        return _err(f"http error: {e}")


def _err(msg: str) -> dict:
    return {"perf_seconds": None, "cost_usd": 0.0, "error": msg}
