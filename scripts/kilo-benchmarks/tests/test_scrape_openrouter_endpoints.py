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


def test_namespace_preference_breaks_tie_for_first_party():
    """When multiple providers tie at the min price, prefer the one
    matching the model's namespace prefix. Regression guard for the
    Claude Opus 4.8 case where 6 endpoints all list $5/M and Google
    (arbitrary first-in-list) was mislabeled as the cheapest —
    misleading operators into thinking Vertex is a discount route."""
    # 6 providers, all identical price — mirrors the real OR response
    # for anthropic/claude-opus-4.8.
    payload = {
        "data": {
            "endpoints": [
                {"provider_name": "Google", "pricing": {"prompt": "0.000005"}, "status": 0},
                {"provider_name": "Anthropic", "pricing": {"prompt": "0.000005"}, "status": 0},
                {"provider_name": "Amazon Bedrock", "pricing": {"prompt": "0.000005"}, "status": 0},
            ]
        }
    }
    p, _, _ = _extract_cheapest(payload, model_id="anthropic/claude-opus-4.8")
    assert p == "Anthropic", f"expected Anthropic (namespace match), got {p!r}"

    # Without model_id, no preference applies — sort-first wins
    p2, _, _ = _extract_cheapest(payload)
    assert p2 == "Google", f"without model_id expected Google (first), got {p2!r}"

    # Namespace normalization: `x-ai/grok-4` → provider "xAI" wins
    payload_grok = {
        "data": {
            "endpoints": [
                {"provider_name": "Google Vertex", "pricing": {"prompt": "0.000002"}, "status": 0},
                {"provider_name": "xAI", "pricing": {"prompt": "0.000002"}, "status": 0},
            ]
        }
    }
    p3, _, _ = _extract_cheapest(payload_grok, model_id="x-ai/grok-4")
    assert p3 == "xAI"


def test_strictly_cheaper_provider_beats_namespace_preference():
    """Namespace preference ONLY applies on price ties. If a non-namespace
    provider is materially cheaper, they win — DeepInfra @ $0.10 must
    beat Meta-preference on llama-3.3-70b (Meta doesn't run its own
    endpoint anyway, but the invariant matters generally)."""
    payload = {
        "data": {
            "endpoints": [
                {"provider_name": "Meta", "pricing": {"prompt": "0.000005"}, "status": 0},
                {"provider_name": "DeepInfra", "pricing": {"prompt": "0.0000001"}, "status": 0},
            ]
        }
    }
    p, price, _ = _extract_cheapest(payload, model_id="meta-llama/llama-3.3-70b")
    assert p == "DeepInfra"
    assert abs(price - 0.1) < 1e-9


def test_prefers_namespace_normalization():
    """`_prefers_namespace` normalizes hyphens, underscores, spaces + casing."""
    from scrape_openrouter_endpoints import _prefers_namespace

    assert _prefers_namespace("Anthropic", "anthropic/claude-opus-4.8")
    assert _prefers_namespace("xAI", "x-ai/grok-4")
    assert _prefers_namespace("Alibaba", "alibaba/qwen-plus")
    assert _prefers_namespace("Google", "google/gemini-2.5-pro")
    assert not _prefers_namespace("Google", "anthropic/claude-opus-4.8")
    assert not _prefers_namespace("DeepInfra", "meta-llama/llama-3.3-70b")
    # None/empty guards
    assert not _prefers_namespace("", "anthropic/foo")
    assert not _prefers_namespace("Anthropic", None)
    assert not _prefers_namespace(None, "anthropic/foo")


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
