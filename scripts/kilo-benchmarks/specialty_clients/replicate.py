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
# "Official model" IDs — reached via `/v1/models/{owner}/{name}/predictions`
# (no version hash needed; Replicate resolves the current default version).
# Matches the pattern used by /opt/brand-identiy-creator's replicate.py client.
OFFICIAL_MODELS = frozenset(
    {
        "recraft-ai/recraft-v3",
        "recraft-ai/recraft-v4",
        "recraft-ai/recraft-v4-svg",
        "recraft-ai/recraft-v4.1",
        "recraft-ai/recraft-v4.1-svg",
    }
)
MAX_POLL_SECONDS = 180


def bench_one(model_id: str, api_key: str) -> dict:
    if model_id in OFFICIAL_MODELS:
        create_url = f"https://api.replicate.com/v1/models/{model_id}/predictions"
        body: dict = {"input": {"prompt": "a cat on a sofa"}}
    else:
        version = VERSION_MAP.get(model_id)
        if version is None:
            return _err(f"no Replicate version pinned for {model_id}")
        create_url = CREATE_URL
        body = {"version": version, "input": {"prompt": "a cat on a sofa"}}
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    t0 = time.monotonic()
    try:
        r = requests.post(create_url, json=body, headers=headers, timeout=30, allow_redirects=False)
        if r.status_code >= 400:
            return _err(_http_err("create", r))
        data = r.json()
        if not isinstance(data, dict):
            return _err(f"create non-dict body: {str(data)[:200]}")
        # `.get("urls") or {}` guards against an explicit JSON null on that key —
        # `.get("urls", {})` returns None when the key IS present but null, which
        # would then AttributeError on the next `.get("get")` and crash the whole
        # cohort run (not caught by `except RequestException`).
        poll_url = (data.get("urls") or {}).get("get")
        if not poll_url:
            return _err("no poll url in create response")
        if not _host_allowed(poll_url):
            return _err(
                f"refuses to send REPLICATE_API_TOKEN to non-Replicate host: "
                f"{urlparse(poll_url).hostname}"
            )
        deadline = t0 + MAX_POLL_SECONDS
        while time.monotonic() < deadline:
            pr = requests.get(poll_url, headers=headers, timeout=15, allow_redirects=False)
            if pr.status_code >= 400:
                return _err(_http_err("poll", pr))
            pd = pr.json()
            if not isinstance(pd, dict):
                return _err(f"poll non-dict body: {str(pd)[:200]}")
            status = pd.get("status", "")
            if status == "succeeded":
                perf_seconds = time.monotonic() - t0
                metrics_cost = (pd.get("metrics") or {}).get("total_cost") or 0.0
                # Replicate omits total_cost on some routes; back-fill from PRICING
                # so cost-cap arithmetic still tracks real spend.
                if not metrics_cost:
                    p = PRICING.get(model_id) or {}
                    metrics_cost = p.get("per_image") or p.get("per_generation") or 0.0
                try:
                    cost = float(metrics_cost)
                except (TypeError, ValueError):
                    cost = float((PRICING.get(model_id) or {}).get("per_image", 0.0))
                # Reject negatives — a compromised upstream returning -X would
                # otherwise DECREMENT running_cost and defeat the cap.
                cost = max(cost, 0.0)
                return {
                    "perf_seconds": round(perf_seconds, 2),
                    "cost_usd": cost,
                    "error": None,
                }
            if status in ("failed", "canceled"):
                return _err(f"replicate {status}: {str(pd.get('error'))[:200]}")
            time.sleep(1.5)
        return _err(f"timeout after {MAX_POLL_SECONDS}s")
    except requests.exceptions.RequestException as e:
        return _err(f"http error: {e}")


def _host_allowed(url: str) -> bool:
    p = urlparse(url)
    if p.scheme != "https":
        return False
    host = p.hostname or ""
    return host in ALLOWED_HOSTS or any(host.endswith("." + h) for h in ALLOWED_HOSTS)


def _http_err(prefix: str, r) -> str:
    retry = r.headers.get("Retry-After") if getattr(r, "headers", None) else None
    suffix = f" Retry-After: {retry}" if retry else ""
    return f"{prefix} {r.status_code}: {r.text[:200]}{suffix}"


def _err(msg: str) -> dict:
    return {"perf_seconds": None, "cost_usd": 0.0, "error": msg}
