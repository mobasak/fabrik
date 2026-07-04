# AFTER-EDIT: scripts/kilo-benchmarks/tests/test_specialty_clients/test_replicate.py
"""Replicate prediction API.

Replicate API 2026-07-03 (docs-verified):
  POST https://api.replicate.com/v1/predictions
  Headers: {"Authorization": "Bearer <REPLICATE_API_TOKEN>", "Content-Type": "application/json"}
  Body:    {"version": "<hash>", "input": {...}}
  Response 201: {"id", "status":"starting", "urls":{"get","cancel"}, ...}
  Poll GET urls.get until status in {"succeeded","failed","canceled"}.
  Cost from metrics.total_cost when populated (or PRICING fallback).
"""

from __future__ import annotations

import time

import requests

CREATE_URL = "https://api.replicate.com/v1/predictions"
# Model versions must be updated periodically. These snapshots are 2026-07-03.
VERSION_MAP = {
    "stability/sdxl": "39ed52f2a78e934b3ba6e2a89f5b1c712de7dfea535525255b1aa35c5565e08b",
    "stability/sd3.5-large": "abc0e2d5-placeholder-update-live",
    "stability/sd3.5-large-turbo": "def1e3d5-placeholder-update-live",
    "stability/stable-audio-2": "aaa1e3d5-placeholder-update-live",
}
MAX_POLL_SECONDS = 180


def bench_one(model_id: str, api_key: str) -> dict:
    version = VERSION_MAP.get(model_id)
    if version is None:
        return _err(f"no Replicate version pinned for {model_id}")
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    body = {"version": version, "input": {"prompt": "a cat on a sofa"}}
    t0 = time.monotonic()
    try:
        r = requests.post(CREATE_URL, json=body, headers=headers, timeout=30)
        if r.status_code >= 400:
            return _err(f"create {r.status_code}: {r.text[:200]}")
        data = r.json()
        poll_url = data.get("urls", {}).get("get")
        if not poll_url:
            return _err("no poll url in create response")
        deadline = t0 + MAX_POLL_SECONDS
        while time.monotonic() < deadline:
            pr = requests.get(poll_url, headers=headers, timeout=15)
            if pr.status_code >= 400:
                return _err(f"poll {pr.status_code}: {pr.text[:200]}")
            pd = pr.json()
            status = pd.get("status", "")
            if status == "succeeded":
                perf_seconds = time.monotonic() - t0
                cost = pd.get("metrics", {}).get("total_cost", 0.0) or 0.0
                return {
                    "perf_seconds": round(perf_seconds, 2),
                    "cost_usd": float(cost),
                    "error": None,
                }
            if status in ("failed", "canceled"):
                return _err(f"replicate {status}: {pd.get('error')}")
            time.sleep(1.5)
        return _err(f"timeout after {MAX_POLL_SECONDS}s")
    except requests.exceptions.RequestException as e:
        return _err(f"http error: {e}")


def _err(msg: str) -> dict:
    return {"perf_seconds": None, "cost_usd": 0.0, "error": msg}
