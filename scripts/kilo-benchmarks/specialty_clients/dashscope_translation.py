# AFTER-EDIT: scripts/kilo-benchmarks/tests/test_specialty_clients/test_dashscope_translation.py
"""Alibaba DashScope Qwen-MT translation client.

DashScope translation API 2026-07-03 (live-verified):
  POST https://dashscope-intl.aliyuncs.com/api/v1/services/aigc/text-generation/generation
  Headers: {"Authorization": "Bearer <DASHSCOPE_API_KEY>", "Content-Type": "application/json"}
  Body:    {"model":"qwen-mt-turbo","input":{"messages":[...]},
            "parameters":{"translation_options":{"source_lang","target_lang"}}}
  Response 200: {"output":{"choices":[{"message":{"content":"<translated>"}}]},
                 "usage":{"total_tokens":<int>}}
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from specialty_pricing import PRICING  # noqa: E402

ENDPOINT = "https://dashscope-intl.aliyuncs.com/api/v1/services/aigc/text-generation/generation"
BENCH_TEXT = "Hello, how are you today? I hope you have a wonderful day ahead."


def bench_one(model_id: str, api_key: str) -> dict:
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    body = {
        "model": "qwen-mt-turbo",
        "input": {"messages": [{"role": "user", "content": BENCH_TEXT}]},
        "parameters": {"translation_options": {"source_lang": "English", "target_lang": "Spanish"}},
    }
    t0 = time.monotonic()
    try:
        r = requests.post(ENDPOINT, json=body, headers=headers, timeout=30)
        if r.status_code >= 400:
            return _err(_http_err(r))
        data = r.json()
        content = (data.get("output") or {}).get("choices") or []
        if not content or not (content[0].get("message") or {}).get("content"):
            return _err(f"no translation in response: {data}")
        perf_seconds = time.monotonic() - t0
        # PRICING is per_char; charge on the deterministic prompt length so cost
        # tracking is stable and matches the pricing table exactly.
        per_char = float((PRICING.get(model_id) or {}).get("per_char", 0.000018))
        return {
            "perf_seconds": round(perf_seconds, 2),
            "cost_usd": round(len(BENCH_TEXT) * per_char, 8),
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
