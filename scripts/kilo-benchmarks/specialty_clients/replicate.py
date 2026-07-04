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

import sys
import time
from pathlib import Path
from urllib.parse import urlparse

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from specialty_pricing import PRICING  # noqa: E402

CREATE_URL = "https://api.replicate.com/v1/predictions"
ALLOWED_HOSTS = {"api.replicate.com", "replicate.com", "replicate.delivery"}
# Model versions must be updated periodically. These snapshots are 2026-07-03.
# Only pinned, live versions live here — placeholder rows would enqueue
# malformed predictions weekly, so they're intentionally omitted; those model
# IDs fall through to `no Replicate version pinned` until a real hash lands.
VERSION_MAP = {
    "stability/sdxl": "39ed52f2a78e934b3ba6e2a89f5b1c712de7dfea535525255b1aa35c5565e08b",
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
            return _err(_http_err("create", r))
        data = r.json()
        poll_url = data.get("urls", {}).get("get")
        if not poll_url:
            return _err("no poll url in create response")
        if not _host_allowed(poll_url):
            return _err(
                f"refuses to send REPLICATE_API_TOKEN to non-Replicate host: "
                f"{urlparse(poll_url).hostname}"
            )
        deadline = t0 + MAX_POLL_SECONDS
        while time.monotonic() < deadline:
            pr = requests.get(poll_url, headers=headers, timeout=15)
            if pr.status_code >= 400:
                return _err(_http_err("poll", pr))
            pd = pr.json()
            status = pd.get("status", "")
            if status == "succeeded":
                perf_seconds = time.monotonic() - t0
                metrics_cost = pd.get("metrics", {}).get("total_cost") or 0.0
                # Replicate omits total_cost on some routes; back-fill from PRICING
                # so cost-cap arithmetic still tracks real spend.
                if not metrics_cost:
                    p = PRICING.get(model_id) or {}
                    metrics_cost = p.get("per_image") or p.get("per_generation") or 0.0
                return {
                    "perf_seconds": round(perf_seconds, 2),
                    "cost_usd": float(metrics_cost),
                    "error": None,
                }
            if status in ("failed", "canceled"):
                return _err(f"replicate {status}: {pd.get('error')}")
            time.sleep(1.5)
        return _err(f"timeout after {MAX_POLL_SECONDS}s")
    except requests.exceptions.RequestException as e:
        return _err(f"http error: {e}")


def _host_allowed(url: str) -> bool:
    host = urlparse(url).hostname or ""
    return host in ALLOWED_HOSTS or any(host.endswith("." + h) for h in ALLOWED_HOSTS)


def _http_err(prefix: str, r) -> str:
    retry = r.headers.get("Retry-After") if getattr(r, "headers", None) else None
    suffix = f" Retry-After: {retry}" if retry else ""
    return f"{prefix} {r.status_code}: {r.text[:200]}{suffix}"


def _err(msg: str) -> dict:
    return {"perf_seconds": None, "cost_usd": 0.0, "error": msg}
