# AFTER-EDIT: scripts/kilo-benchmarks/microbench_specialty.py
"""OpenRouter image-generation microbench client.

Handles rows in `specialty_pricing.PRICING` with `via='openrouter'` — currently
`openai/gpt-*-image*` and `google/gemini-*-image*`. Calls OpenRouter's OpenAI-
compatible chat completions endpoint with `modalities=["image","text"]`, which
returns image URLs in the response's `images` field. We don't download the
image — we only need the round-trip wall-clock for the perf metric.

Cost: OpenRouter passes vendor cost through; per-image varies by model. Falls
back to `specialty_pricing.PRICING[model_id]['per_image']` when the response
omits `usage.total_cost`.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent.parent))
from specialty_pricing import PRICING  # noqa: E402

BENCH_TEXT = "a small round tabby cat sitting on a windowsill in soft afternoon light"

_ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"
_TIMEOUT_S = 90


def _err(msg: str) -> dict:
    return {"perf_seconds": None, "cost_usd": 0.0, "error": msg}


def _pricing_cost(model_id: str) -> float:
    p = PRICING.get(model_id) or {}
    return float(p.get("per_image") or p.get("per_generation") or 0.0)


def bench_one(model_id: str, api_key: str) -> dict:
    """One round-trip against OpenRouter for a single image_gen call.

    Returns {perf_seconds, cost_usd, error}. Errors are non-fatal to the wider
    cohort — the caller aggregates across BENCH_N_RUNS and reports a per-model
    verdict.
    """
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://fabrik.local/kilo-benchmarks",
        "X-Title": "fabrik-kilo-benchmarks",
    }
    body = {
        "model": model_id,
        "modalities": ["image", "text"],
        "messages": [{"role": "user", "content": BENCH_TEXT}],
        "max_tokens": 128,
    }
    t0 = time.monotonic()
    try:
        r = requests.post(_ENDPOINT, json=body, headers=headers, timeout=_TIMEOUT_S)
    except requests.RequestException as e:
        return _err(f"openrouter transport: {type(e).__name__}: {str(e)[:120]}")
    perf = time.monotonic() - t0
    if r.status_code >= 400:
        return _err(f"openrouter http {r.status_code}: {r.text[:200]}")
    try:
        data = r.json()
    except ValueError as e:
        return _err(f"openrouter non-json: {e}")
    if not isinstance(data, dict):
        return _err(f"openrouter non-dict body: {str(data)[:200]}")
    # OpenRouter surfaces vendor errors in `error` even on 200.
    if "error" in data:
        err = data["error"]
        msg = err.get("message") or str(err) if isinstance(err, dict) else str(err)
        return _err(f"openrouter vendor: {msg[:200]}")
    # Confirm at least one image came back so we're not counting a no-op response.
    choice = ((data.get("choices") or [{}])[0]) or {}
    msg = choice.get("message") or {}
    images = msg.get("images") or []
    if not images and not msg.get("content"):
        return _err("openrouter returned no images and no content")
    cost = float((data.get("usage") or {}).get("total_cost") or 0.0)
    if cost <= 0:
        cost = _pricing_cost(model_id)
    return {"perf_seconds": perf, "cost_usd": cost, "error": None}
