"""Regression tests for scrape_openrouter_endpoints._extract_cheapest.

Guards against the provider-name-fallback bug: OR's endpoint schema has
`provider_name` (clean label like "DeepInfra") separate from `name` (full
endpoint identifier like "DeepInfra | meta-llama/llama-3.3-70b").
Falling back from provider_name to name produced garbage labels in the
UI's Cheapest column.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scrape_openrouter_endpoints import _extract_cheapest


def test_returns_none_when_provider_name_missing():
    """If OR omits provider_name, skip the endpoint. Never surface the
    endpoint's `name` field as if it were the provider."""
    payload = {
        "data": {
            "endpoints": [
                {
                    "name": "DeepInfra | meta-llama/llama-3.3-70b-instruct",
                    "pricing": {"prompt": "0.0000001"},
                    "status": 0,
                },
            ]
        }
    }
    provider, price, quant = _extract_cheapest(payload)
    assert provider is None, f"expected None, got {provider!r}"
    assert price is None
    assert quant is None


def test_picks_min_priced_in_service_endpoint():
    payload = {
        "data": {
            "endpoints": [
                {
                    "provider_name": "Together",
                    "pricing": {"prompt": "0.000001", "quantization": "fp8"},
                    "status": 0,
                },
                {
                    "provider_name": "DeepInfra",
                    "pricing": {"prompt": "0.0000001", "quantization": "fp8"},
                    "status": 0,
                },
            ]
        }
    }
    provider, price, quant = _extract_cheapest(payload)
    assert provider == "DeepInfra"
    assert abs(price - 0.1) < 1e-9
    assert quant == "fp8"


def test_skips_out_of_service_endpoints():
    """OR uses status < 0 for disabled/degraded routes — must not win."""
    payload = {
        "data": {
            "endpoints": [
                {
                    "provider_name": "CheapButDown",
                    "pricing": {"prompt": "0.00000001"},  # $0.01/M
                    "status": -2,
                },
                {
                    "provider_name": "PricierButUp",
                    "pricing": {"prompt": "0.0000005"},  # $0.50/M
                    "status": 0,
                },
            ]
        }
    }
    provider, price, _ = _extract_cheapest(payload)
    assert provider == "PricierButUp"
    assert abs(price - 0.5) < 1e-9


def test_skips_zero_and_negative_prices():
    """Broken free-tier entries with prompt=0 must not win at $0."""
    payload = {
        "data": {
            "endpoints": [
                {"provider_name": "GarbageFree", "pricing": {"prompt": "0"}, "status": 0},
                {"provider_name": "Valid", "pricing": {"prompt": "0.000001"}, "status": 0},
            ]
        }
    }
    provider, _, _ = _extract_cheapest(payload)
    assert provider == "Valid"


def test_empty_endpoints_returns_none():
    """No endpoints (404, empty list, missing data) must return (None, None, None)."""
    for payload in ({"data": {"endpoints": []}}, {"data": {}}, {}):
        assert _extract_cheapest(payload) == (None, None, None)


def test_fetch_endpoints_handles_non_utf8_body(monkeypatch):
    """A mangling proxy or edge case sending non-UTF-8 bytes must not
    crash the loop. Regression guard for the missing UnicodeDecodeError
    catch that was found in adversarial review."""

    from scrape_openrouter_endpoints import _fetch_endpoints

    class FakeResp:
        def __init__(self, body: bytes):
            self._body = body

        def read(self) -> bytes:
            return self._body

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

    def fake_urlopen(req, timeout=None):
        # non-UTF-8 sequence (0xFF is invalid start byte)
        return FakeResp(b"\xff\xfe garbage \xff")

    monkeypatch.setattr("scrape_openrouter_endpoints.urlopen", fake_urlopen)
    result = _fetch_endpoints("anything/slug")
    assert result is None, "must return None on non-UTF-8 body, not raise"


def test_non_numeric_status_is_skipped():
    """A string status like 'unknown' should NOT be treated as in-service."""
    payload = {
        "data": {
            "endpoints": [
                {
                    "provider_name": "MysteriousStatus",
                    "pricing": {"prompt": "0.0000001"},
                    "status": "unknown",
                },
            ]
        }
    }
    assert _extract_cheapest(payload) == (None, None, None)
