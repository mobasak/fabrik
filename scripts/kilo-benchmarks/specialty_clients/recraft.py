# AFTER-EDIT: scripts/kilo-benchmarks/tests/test_specialty_clients/test_recraft.py
"""Recraft direct REST client.

Recraft API 2026-07-03 (live-verified):
  POST https://external.api.recraft.ai/v1/images/generations
  Headers: {"Authorization": "Bearer <RECRAFT_API_KEY>", "Content-Type": "application/json"}
  Body:    {"prompt": "<text>", "model": "recraftv3", "style": "digital_illustration"}
  Response 200: {"created", "credits", "data":[{"image_id","url"}]}
  1 credit ~ $0.001. Recraftv3 costs ~40 credits/image = $0.04.
"""

from __future__ import annotations

import time

import requests

ENDPOINT = "https://external.api.recraft.ai/v1/images/generations"
MODEL_MAP = {
    "recraft/v3": "recraftv3",
    "recraft/nano-banana": "recraftv3",  # nano-banana fallback to v3
    "recraft/recraft-v4.1": "recraftv3",  # v4.1 fallback to v3 (mapping may need update)
}


def bench_one(model_id: str, api_key: str) -> dict:
    recraft_model = MODEL_MAP.get(model_id)
    if recraft_model is None:
        return _err(f"no Recraft model map for {model_id}")
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    body = {"prompt": "a cat on a sofa", "model": recraft_model, "style": "digital_illustration"}
    t0 = time.monotonic()
    try:
        r = requests.post(ENDPOINT, json=body, headers=headers, timeout=60)
        if r.status_code >= 400:
            return _err(f"http {r.status_code}: {r.text[:200]}")
        data = r.json()
        credits = data.get("credits", 0)
        perf_seconds = time.monotonic() - t0
        return {
            "perf_seconds": round(perf_seconds, 2),
            "cost_usd": credits * 0.001,
            "error": None,
        }
    except requests.exceptions.RequestException as e:
        return _err(f"http error: {e}")


def _err(msg: str) -> dict:
    return {"perf_seconds": None, "cost_usd": 0.0, "error": msg}
