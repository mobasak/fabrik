#!/usr/bin/env python3
# AFTER-EDIT: scripts/registry_sync.py scripts/kilo-benchmarks/daily_refresh.sh
"""Hybrid credit fetchers — per-provider account balance/usage via each vendor's API.

Resilience (core/58): every HTTP call is timeout + retry wrapped and returns None on ANY
failure (never raises) — a fetch failure degrades to "no snapshot", never crashes the run.
Endpoints live-verified in the CONVERGED spec (2026-07-18). The real API key is read host-side
from all-envs.env by the caller; it is never sent anywhere but the vendor's own API.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """A usage endpoint never legitimately redirects; urllib's default handler would re-send the
    vendor key in `Authorization` to whatever host a 3xx names — a parked domain, an open
    redirect, a DNS interception — and over plain http (BB8). A redirect is an HTTPError → None."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D102
        return None


_OPENER = urllib.request.build_opener(_NoRedirect)

TIMEOUT_S = 10
RETRIES = 2


@dataclass
class CreditSnapshot:
    balance: float
    unit: str


def _get_json(url: str, headers: dict[str, str]) -> dict | None:
    """GET url → parsed JSON dict, or None on any failure (timeout/HTTP/parse)."""
    req = urllib.request.Request(url, headers=headers)  # noqa: S310 (https vendor endpoints only)
    for attempt in range(RETRIES + 1):
        try:
            with _OPENER.open(req, timeout=TIMEOUT_S) as resp:  # noqa: S310 — never follows a redirect (BB8)
                obj = json.loads(resp.read().decode("utf-8"))
                return obj if isinstance(obj, dict) else None
        except (urllib.error.URLError, TimeoutError, ValueError, OSError):
            if attempt == RETRIES:
                return None
    return None


def fetch_apify(api_key: str) -> CreditSnapshot | None:
    d = _get_json(
        "https://api.apify.com/v2/users/me/usage/monthly",
        {"Authorization": f"Bearer {api_key}"},
    )
    used = (d.get("data") or {}).get("totalUsageCreditsUsd") if d else None
    return CreditSnapshot(float(used), "usd_used_month") if used is not None else None


def fetch_deepl(api_key: str) -> CreditSnapshot | None:
    # A DeepL API-Free key ends in ":fx" and uses the api-free host.
    host = "api-free.deepl.com" if api_key.endswith(":fx") else "api.deepl.com"
    d = _get_json(f"https://{host}/v2/usage", {"Authorization": f"DeepL-Auth-Key {api_key}"})
    if not d or d.get("character_count") is None or d.get("character_limit") is None:
        return None
    remaining = float(d["character_limit"] - d["character_count"])
    return CreditSnapshot(remaining, "chars_remaining")


def fetch_exa(_api_key: str) -> CreditSnapshot | None:
    # Exa per-key usage is GET admin-api.exa.ai/team-management/api-keys/{id}/usage — it needs the
    # key's ID (a separate lookup we don't have from all-envs.env). Residual: add the key-id lookup.
    return None


def fetch_replicate(_api_key: str) -> CreditSnapshot | None:
    # Replicate's GET /v1/account returns account identity (username/type), not a numeric balance.
    return None


FETCHERS: dict[str, Callable[[str], CreditSnapshot | None]] = {
    "apify": fetch_apify,
    "deepl": fetch_deepl,
    "exa": fetch_exa,
    "replicate": fetch_replicate,
}


def fetch_balance(provider: str, api_key: str) -> CreditSnapshot | None:
    """Fetch the account balance/usage for a provider, or None (no fetcher / fetch failed).

    Final guard: catches ANY exception (e.g. a malformed vendor field crashing `float()`) → None,
    so a bad response can never propagate out and abort the caller's DB transaction."""
    fn = FETCHERS.get(provider)
    if not fn:
        return None
    try:
        return fn(api_key)
    except Exception:  # noqa: BLE001 - the "never raises" contract; a bad vendor field => no snapshot
        return None
