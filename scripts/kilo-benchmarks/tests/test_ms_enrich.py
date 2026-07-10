"""Behavior Contract for scripts/kilo-benchmarks/ms_enrich.py.

Plan-2 (ModelScope new-row ingest) — Phases A/B/C populate this file.
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def test_a1_web_scrape_public_api_importable():
    """Vendored web-scrape module exposes the API Phase C consumes."""
    from libs.web_scrape import (  # noqa: F401
        FetchError,
        ParseError,
        WebScraper,
        extract_nextjs_data,
    )


def test_a2_web_scrape_scraper_constructs(tmp_path):
    """WebScraper(cache_dir, browserless_url, browserless_token) constructs."""
    from libs.web_scrape import WebScraper

    scraper = WebScraper(
        cache_dir=tmp_path / "cache",
        browserless_url="https://browser.example.com",
        browserless_token="fake-token",
    )
    assert scraper is not None


def test_a3_module_imports():
    """Scaffold sanity — module exists and imports cleanly."""
    import ms_enrich  # noqa: F401


# ── Phase B: fetch_hf_metadata ────────────────────────────────────────────────

import httpx  # noqa: E402

_HF_API_INTERNLM = {
    "id": "internlm/internlm3-8b-instruct",
    "tags": ["text-generation", "internlm3", "custom_code"],
    "pipeline_tag": "text-generation",
    "gated": False,
}

_HF_CONFIG_INTERNLM = {
    "max_position_embeddings": 32768,
    "model_type": "internlm3",
    "hidden_size": 4096,
}


def _mock_transport(routes: dict) -> httpx.MockTransport:
    """Route URL → response. Any unrouted URL returns 404."""

    def handler(request: httpx.Request) -> httpx.Response:
        return routes.get(str(request.url), httpx.Response(404))

    return httpx.MockTransport(handler)


def test_b1_hf_happy_path():
    from ms_enrich import fetch_hf_metadata

    routes = {
        "https://huggingface.co/api/models/internlm/internlm3-8b-instruct": httpx.Response(
            200, json=_HF_API_INTERNLM
        ),
        "https://huggingface.co/internlm/internlm3-8b-instruct/resolve/main/config.json": httpx.Response(
            200, json=_HF_CONFIG_INTERNLM
        ),
    }
    client = httpx.Client(transport=_mock_transport(routes))
    md = fetch_hf_metadata("internlm/internlm3-8b-instruct", client=client)
    assert md is not None
    assert md.context_window_k == 32
    assert md.model_type == "internlm3"
    assert md.pipeline_tag == "text-generation"
    assert md.is_gated is False
    assert md.has_reasoning is False


def test_b2_hf_api_404_returns_none():
    from ms_enrich import fetch_hf_metadata

    client = httpx.Client(transport=_mock_transport({}))  # all URLs 404
    assert fetch_hf_metadata("nonexistent/model", client=client) is None


def test_b3_hf_resolve_404_returns_partial():
    from ms_enrich import fetch_hf_metadata

    routes = {
        "https://huggingface.co/api/models/x/y": httpx.Response(
            200, json={"id": "x/y", "tags": [], "gated": False}
        ),
        # /resolve NOT routed → 404
    }
    client = httpx.Client(transport=_mock_transport(routes))
    md = fetch_hf_metadata("x/y", client=client)
    assert md is not None
    assert md.context_window_k is None  # config.json missed
    assert md.is_gated is False


def test_b4_hf_timeout_returns_none():
    from ms_enrich import fetch_hf_metadata

    def handler(request):
        raise httpx.ConnectTimeout("simulated")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    assert fetch_hf_metadata("any/model", client=client) is None


def test_b5_hf_bogus_json_returns_none():
    from ms_enrich import fetch_hf_metadata

    routes = {
        "https://huggingface.co/api/models/x/y": httpx.Response(200, content=b"not-json-lol"),
    }
    client = httpx.Client(transport=_mock_transport(routes))
    assert fetch_hf_metadata("x/y", client=client) is None


def test_b6_hf_gated_sets_flag():
    from ms_enrich import fetch_hf_metadata

    routes = {
        "https://huggingface.co/api/models/x/y": httpx.Response(
            200, json={"id": "x/y", "tags": [], "gated": True}
        ),
    }
    client = httpx.Client(transport=_mock_transport(routes))
    md = fetch_hf_metadata("x/y", client=client)
    assert md.is_gated is True


def test_b7_hf_reasoning_tag_detected():
    from ms_enrich import fetch_hf_metadata

    routes = {
        "https://huggingface.co/api/models/x/y": httpx.Response(
            200,
            json={"id": "x/y", "tags": ["thinking", "text-generation"], "gated": False},
        ),
    }
    client = httpx.Client(transport=_mock_transport(routes))
    md = fetch_hf_metadata("x/y", client=client)
    assert md.has_reasoning is True


def test_b8_hf_tools_and_vision_tags_detected():
    """Phase-B review F4 regression — has_tools/has_vision detection."""
    from ms_enrich import fetch_hf_metadata

    routes = {
        "https://huggingface.co/api/models/x/y": httpx.Response(
            200,
            json={
                "id": "x/y",
                "tags": ["function-calling", "image-text-to-text", "text-generation"],
                "gated": False,
            },
        ),
    }
    client = httpx.Client(transport=_mock_transport(routes))
    md = fetch_hf_metadata("x/y", client=client)
    assert md.has_tools is True
    assert md.has_vision is True


def test_b9_hf_non_dict_api_payload_returns_none():
    """Phase-B review F1 regression — non-dict JSON payload → fail-open None."""
    from ms_enrich import fetch_hf_metadata

    routes = {
        "https://huggingface.co/api/models/x/y": httpx.Response(200, json=["a", "list", "not", "a", "dict"]),
    }
    client = httpx.Client(transport=_mock_transport(routes))
    assert fetch_hf_metadata("x/y", client=client) is None


def test_b10_hf_invalid_url_returns_none():
    """Phase-B review F2 regression — malformed hf_id (control char) → fail-open."""
    from ms_enrich import fetch_hf_metadata

    # httpx raises InvalidURL (not HTTPError subclass) — must be caught.
    md = fetch_hf_metadata("bad\x00id/model")
    assert md is None


def test_b11_hf_null_config_returns_partial():
    """Phase-B review F1 regression — /resolve returns JSON literal null →
    partial return (context stays None), not crash."""
    from ms_enrich import fetch_hf_metadata

    routes = {
        "https://huggingface.co/api/models/x/y": httpx.Response(
            200, json={"id": "x/y", "tags": [], "gated": False}
        ),
        "https://huggingface.co/x/y/resolve/main/config.json": httpx.Response(200, json=None),
    }
    client = httpx.Client(transport=_mock_transport(routes))
    md = fetch_hf_metadata("x/y", client=client)
    assert md is not None
    assert md.context_window_k is None


def test_b12_hf_owned_client_default_path():
    """Phase-B review F3 regression — client=None branch exercised (bad id
    guarantees fail-open, so no real network call needed to prove the code
    path constructs + closes the owned client)."""
    from ms_enrich import fetch_hf_metadata

    md = fetch_hf_metadata("\x00\x00\x00/bad")
    assert md is None


def test_b13_hf_pipeline_tag_vision_detected():
    """Phase-B review F6 regression — pipeline_tag='image-text-to-text' alone
    (no vision tag in tags array) still sets has_vision=True."""
    from ms_enrich import fetch_hf_metadata

    routes = {
        "https://huggingface.co/api/models/x/y": httpx.Response(
            200,
            json={
                "id": "x/y",
                "tags": ["text-generation"],  # no vision tag
                "pipeline_tag": "image-text-to-text",
                "gated": False,
            },
        ),
    }
    client = httpx.Client(transport=_mock_transport(routes))
    md = fetch_hf_metadata("x/y", client=client)
    assert md.has_vision is True


# ── Phase C: fetch_ms_metadata ────────────────────────────────────────────────


def _make_next_html(payload: dict) -> str:
    """Build a minimal HTML fragment with __NEXT_DATA__ embedded."""
    import json as _json
    return (
        '<html><body><script id="__NEXT_DATA__" type="application/json">'
        + _json.dumps(payload)
        + "</script></body></html>"
    )


class _FakeScraper:
    def __init__(self, response_map):
        self._map = response_map

    def fetch_rendered(self, url, **kw):
        if isinstance(self._map, Exception):
            raise self._map
        return self._map[url]


def test_c1_ms_happy_path():
    from ms_enrich import fetch_ms_metadata

    html = _make_next_html(
        {"props": {"pageProps": {"model": {"max_tokens": 32768, "description": "S1 model"}}}}
    )
    scraper = _FakeScraper(
        {"https://modelscope.cn/models/Shanghai_AI_Laboratory/Intern-S1": html}
    )
    md = fetch_ms_metadata("Shanghai_AI_Laboratory/Intern-S1", scraper=scraper)
    assert md is not None
    assert md.context_window_k == 32
    assert md.description == "S1 model"


def test_c2_ms_no_nextdata_returns_none():
    from ms_enrich import fetch_ms_metadata

    scraper = _FakeScraper({"https://modelscope.cn/models/x/y": "<html>no next data</html>"})
    assert fetch_ms_metadata("x/y", scraper=scraper) is None


def test_c3_ms_fetch_error_returns_none():
    from libs.web_scrape import FetchError
    from ms_enrich import fetch_ms_metadata

    scraper = _FakeScraper(FetchError("simulated"))
    assert fetch_ms_metadata("x/y", scraper=scraper) is None


def test_c4_ms_context_missing_partial_ok():
    from ms_enrich import fetch_ms_metadata

    html = _make_next_html({"props": {"pageProps": {"model": {"description": "no context"}}}})
    scraper = _FakeScraper({"https://modelscope.cn/models/x/y": html})
    md = fetch_ms_metadata("x/y", scraper=scraper)
    assert md is not None
    assert md.context_window_k is None
    assert md.description == "no context"


def test_c5_ms_walker_finds_nested():
    from ms_enrich import fetch_ms_metadata

    html = _make_next_html(
        {"props": {"pageProps": {"model": {"details": {"deeply": {"max_length": 16384}}}}}}
    )
    scraper = _FakeScraper({"https://modelscope.cn/models/x/y": html})
    md = fetch_ms_metadata("x/y", scraper=scraper)
    assert md.context_window_k == 16


def test_c6_ms_walker_ignores_related_model_gated():
    """Phase-C review F1 regression — walker MUST be anchored to primary
    model block, not the whole page. A relatedModels/carousel entry with
    gated=True must NOT leak into the primary model's is_gated flag.
    """
    from ms_enrich import fetch_ms_metadata

    html = _make_next_html(
        {
            "props": {
                "pageProps": {
                    "model": {"gated": False, "max_tokens": 32768, "description": "primary"},
                    "relatedModels": [{"id": "other/model", "gated": True, "description": "other"}],
                }
            }
        }
    )
    scraper = _FakeScraper({"https://modelscope.cn/models/x/y": html})
    md = fetch_ms_metadata("x/y", scraper=scraper)
    assert md is not None
    assert md.is_gated is False, "primary model is not gated; relatedModels leaked in"
    assert md.description == "primary"
    assert md.context_window_k == 32


def test_c7_ms_context_string_value_coerced():
    """Phase-C review F3 regression — string numeric max_tokens (JS-authored
    JSON often stringifies numbers) must be coerced, not silently dropped."""
    from ms_enrich import fetch_ms_metadata

    html = _make_next_html(
        {"props": {"pageProps": {"model": {"max_tokens": "32768"}}}}
    )
    scraper = _FakeScraper({"https://modelscope.cn/models/x/y": html})
    md = fetch_ms_metadata("x/y", scraper=scraper)
    assert md is not None
    assert md.context_window_k == 32


def test_c8_ms_description_dict_rejected():
    """Phase-C review F4 regression — a dict description (i18n {en, zh})
    must NOT be stringified into a Python repr; return None instead."""
    from ms_enrich import fetch_ms_metadata

    html = _make_next_html(
        {"props": {"pageProps": {"model": {"description": {"en": "hi", "zh": "你好"}}}}}
    )
    scraper = _FakeScraper({"https://modelscope.cn/models/x/y": html})
    md = fetch_ms_metadata("x/y", scraper=scraper)
    assert md is not None
    assert md.description is None, "dict description must not stringify to repr"


def test_c9_ms_subkilo_context_returns_none():
    """Phase-C review F5 regression — value < 1024 must return None, not 0."""
    from ms_enrich import fetch_ms_metadata

    html = _make_next_html(
        {"props": {"pageProps": {"model": {"max_tokens": 512}}}}
    )
    scraper = _FakeScraper({"https://modelscope.cn/models/x/y": html})
    md = fetch_ms_metadata("x/y", scraper=scraper)
    assert md is not None
    assert md.context_window_k is None, "sub-1024 value must not misreport 0K"


def test_b14_hf_vlm_nested_text_config_context():
    """Phase-B review F5 regression — LLaVA-style VLM has max_position_embeddings
    under text_config.*, not top-level. Fallback walker must find it."""
    from ms_enrich import fetch_hf_metadata

    routes = {
        "https://huggingface.co/api/models/x/y": httpx.Response(
            200, json={"id": "x/y", "tags": [], "gated": False}
        ),
        "https://huggingface.co/x/y/resolve/main/config.json": httpx.Response(
            200,
            json={
                "model_type": "llava",
                "text_config": {"max_position_embeddings": 8192},
            },
        ),
    }
    client = httpx.Client(transport=_mock_transport(routes))
    md = fetch_hf_metadata("x/y", client=client)
    assert md.context_window_k == 8
