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
import math
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass

RETRYABLE_STATUS = frozenset({408, 429, 500, 502, 503, 504})  # core/58-resilience


def _retry_after(header: str | None, attempt: int) -> float:
    """Seconds to wait before a retry: the vendor's `Retry-After` when it is a small integer,
    else a short backoff — capped so a hostile header cannot stall the daily chain (BH4)."""
    try:
        v = float(header) if header else 1.0 * (attempt + 1)
        return 0.0 if v != v else max(0.0, min(v, 30.0))  # never negative, never NaN (BJ3/BK5)
    except ValueError:
        return min(1.0 * (attempt + 1), 30.0)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """A usage endpoint never legitimately redirects; urllib's default handler would re-send the
    vendor key in `Authorization` to whatever host a 3xx names — a parked domain, an open
    redirect, a DNS interception — and over plain http (BB8). A redirect is an HTTPError → None."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D102
        return None


_OPENER = urllib.request.build_opener(_NoRedirect)

TIMEOUT_S = 10
RETRIES = 2
MAX_BODY = (
    1 << 20
)  # Apify's monthly usage carries a daily per-service breakdown (tens of KB — EXTERNAL_SYSTEMS.md, Apify row 7), DeepL's usage a few fields; an unbounded read let a misbehaving endpoint hold the daily chain's memory and clock (FB9); crossing the cap is SAID so the chain log carries the cause (FC4)


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
                raw = resp.read(MAX_BODY + 1)
                if len(raw) > MAX_BODY:
                    print(
                        f"WARNING: {url}: response over {MAX_BODY} bytes — not a usage answer, no snapshot",
                        file=sys.stderr,
                    )
                    return None
                obj = json.loads(raw.decode("utf-8"))
                return obj if isinstance(obj, dict) else None
        except urllib.error.HTTPError as exc:
            # only a transient status is retried (core/58 RETRYABLE_STATUS); a 3xx (BB8), 401/403/404
            # is final on the first answer — a revoked key is not hammered three times (BH4)
            if exc.code not in RETRYABLE_STATUS or attempt == RETRIES:
                return None
            time.sleep(_retry_after(exc.headers.get("Retry-After"), attempt))
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
    return _finite(used, "usd_used_month")


def fetch_deepl(api_key: str) -> CreditSnapshot | None:
    # A DeepL API-Free key ends in ":fx" and uses the api-free host.
    host = "api-free.deepl.com" if api_key.endswith(":fx") else "api.deepl.com"
    d = _get_json(f"https://{host}/v2/usage", {"Authorization": f"DeepL-Auth-Key {api_key}"})
    if not d or d.get("character_count") is None or d.get("character_limit") is None:
        return None
    limit = d["character_limit"]
    if not isinstance(limit, (int, float)) or isinstance(limit, bool) or not math.isfinite(limit):
        return None
    if limit >= 1e12:
        # DeepL's documented "no limit" sentinel (EXTERNAL_SYSTEMS.md, DeepL row 7): an unlimited
        # plan is not a balance of 1e12 — the usage is the number worth tracking (FC4)
        return _finite(d["character_count"], "chars_used_unlimited_plan")
    return _finite(d["character_limit"] - d["character_count"], "chars_remaining")


def _finite(value: object, unit: str) -> CreditSnapshot | None:
    """A snapshot only for a FINITE number: `json.loads` accepts the non-standard `NaN`/`Infinity`
    literals and `float()` passed them through to a NUMERIC column and the dashboard (FC4)."""
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return CreditSnapshot(number, unit) if math.isfinite(number) else None


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
