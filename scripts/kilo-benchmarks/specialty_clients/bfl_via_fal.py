# AFTER-EDIT: scripts/kilo-benchmarks/tests/test_specialty_clients/test_bfl_via_fal.py
"""BFL routed through Fal.ai queue.

Fal.ai queue API 2026-07-03 (live-verified):
  POST https://queue.fal.run/fal-ai/flux/{model-suffix}
  Headers: {"Authorization": "Key <FAL_KEY>", "Content-Type": "application/json"}
  Body:    {"prompt": "<text>", "image_size": "square"}
  Response 200: {"status":"IN_QUEUE", "request_id", "status_url", "queue_position"}
  Poll:    GET status_url until status in {"COMPLETED","FAILED"}
  On 403 with body containing "Exhausted balance" → log [FAL-BALANCE-EXHAUSTED].
"""

from __future__ import annotations

import time

import requests

FAL_ENDPOINTS = {
    "bfl/flux-schnell": "https://queue.fal.run/fal-ai/flux/schnell",
    "bfl/flux-dev": "https://queue.fal.run/fal-ai/flux/dev",
    "bfl/flux-pro": "https://queue.fal.run/fal-ai/flux-pro",
    "bfl/flux-pro-1.1": "https://queue.fal.run/fal-ai/flux-pro/v1.1",
    "bfl/flux-pro-1.1-ultra": "https://queue.fal.run/fal-ai/flux-pro/v1.1-ultra",
    "bfl/flux-fill": "https://queue.fal.run/fal-ai/flux-pro/v1/fill",
    "bfl/flux-redux": "https://queue.fal.run/fal-ai/flux-pro/v1/redux",
    "black-forest-labs/flux.2-flex": "https://queue.fal.run/fal-ai/flux-2/flex",
    "black-forest-labs/flux.2-klein-4b": "https://queue.fal.run/fal-ai/flux-2/klein",
    "black-forest-labs/flux.2-max": "https://queue.fal.run/fal-ai/flux-2/max",
    "black-forest-labs/flux.2-pro": "https://queue.fal.run/fal-ai/flux-2/pro",
}

MAX_POLL_SECONDS = 120


def bench_one(model_id: str, api_key: str) -> dict:
    endpoint = FAL_ENDPOINTS.get(model_id)
    if endpoint is None:
        return _err(f"no Fal.ai endpoint mapped for {model_id}")
    headers = {"Authorization": f"Key {api_key}", "Content-Type": "application/json"}
    body = {"prompt": "a cat on a sofa", "image_size": "square"}
    t0 = time.monotonic()
    try:
        r = requests.post(endpoint, json=body, headers=headers, timeout=30)
        if r.status_code == 403 and "Exhausted balance" in r.text:
            return _err("[FAL-BALANCE-EXHAUSTED] top up at fal.ai/dashboard/billing")
        if r.status_code >= 400:
            return _err(f"enqueue {r.status_code}: {r.text[:200]}")
        data = r.json()
        status_url = data.get("status_url")
        if not status_url:
            return _err("no status_url in enqueue response")
        # Poll queue
        deadline = t0 + MAX_POLL_SECONDS
        while time.monotonic() < deadline:
            pr = requests.get(status_url, headers=headers, timeout=15)
            if pr.status_code >= 400:
                return _err(f"poll {pr.status_code}: {pr.text[:200]}")
            pd = pr.json()
            status = pd.get("status", "").upper()
            if status == "COMPLETED":
                perf_seconds = time.monotonic() - t0
                return {"perf_seconds": round(perf_seconds, 2), "cost_usd": 0.0, "error": None}
            if status in ("FAILED", "ERROR"):
                return _err(f"fal status {status}: {pd}")
            time.sleep(1.0)
        return _err(f"timeout after {MAX_POLL_SECONDS}s")
    except requests.exceptions.RequestException as e:
        return _err(f"http error: {e}")


def _err(msg: str) -> dict:
    return {"perf_seconds": None, "cost_usd": 0.0, "error": msg}
