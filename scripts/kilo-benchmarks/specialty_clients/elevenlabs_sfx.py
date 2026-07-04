# AFTER-EDIT: scripts/kilo-benchmarks/tests/test_specialty_clients/test_elevenlabs_sfx.py
"""ElevenLabs Sound Effects client.

ElevenLabs SFX API 2026-07-03 (live-verified):
  POST https://api.elevenlabs.io/v1/sound-generation
  Headers: {"xi-api-key": "<ELEVENLABS_API_KEY>", "Content-Type": "application/json"}
  Body:    {"text":"<prompt>","duration_seconds":<int>}
  Response 200: binary audio/mpeg (~33KB for 2s at 128kbps in probe)
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from specialty_pricing import PRICING  # noqa: E402

ENDPOINT = "https://api.elevenlabs.io/v1/sound-generation"
BENCH_PROMPT = "gentle wind blowing through trees"
DURATION_SECONDS = 2


def bench_one(model_id: str, api_key: str) -> dict:
    headers = {"xi-api-key": api_key, "Content-Type": "application/json"}
    body = {"text": BENCH_PROMPT, "duration_seconds": DURATION_SECONDS}
    t0 = time.monotonic()
    try:
        r = requests.post(ENDPOINT, json=body, headers=headers, timeout=60, allow_redirects=False)
        if r.status_code >= 400:
            return _err(_http_err(r))
        if len(r.content) < 100:
            return _err(f"suspiciously small audio: {len(r.content)} bytes")
        perf_seconds = time.monotonic() - t0
        per_gen = float((PRICING.get(model_id) or {}).get("per_generation", 0.02))
        return {
            "perf_seconds": round(perf_seconds, 2),
            "cost_usd": per_gen,
            "error": None,
        }
    except requests.exceptions.RequestException as e:
        return _err(f"http error: {e}")


def _http_err(r) -> str:
    retry = r.headers.get("Retry-After") if getattr(r, "headers", None) else None
    suffix = f" Retry-After: {retry}" if retry else ""
    return f"http {r.status_code}: {r.text[:200]}{suffix}"


def _err(msg: str) -> dict:
    return {"perf_seconds": None, "cost_usd": 0.0, "error": msg}
