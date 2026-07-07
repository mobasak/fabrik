# AFTER-EDIT: scripts/kilo-benchmarks/microbench_specialty.py
"""Locks in the fix for the specialty-clients gap surfaced by A.5.5 in the
best-model-suggester Phase A.

Before this fix, `_dispatch` had no branch for `via='openrouter'` and no way
to reach stability's newer sd3.5 slugs on Replicate — 11 rows in the
`microbench_specialty --limit 20` cohort hit "no client for X" or fell to
"no Replicate version pinned". These tests assert that dispatch now routes
each of those model IDs to a real client.

No network calls: bench_one itself is not exercised here — dispatch alone.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPT_DIR))

from microbench_specialty import _dispatch  # noqa: E402
from specialty_clients import openrouter_image_gen, replicate  # noqa: E402


@pytest.mark.parametrize(
    "model_id",
    [
        "google/gemini-2.5-flash-image",
        "google/gemini-3-pro-image",
        "google/gemini-3-pro-image-preview",
        "google/gemini-3.1-flash-image",
        "google/gemini-3.1-flash-image-preview",
        "openai/gpt-5-image",
        "openai/gpt-5-image-mini",
        "openai/gpt-5.4-image-2",
    ],
)
def test_openrouter_image_gen_dispatch(model_id):
    """The 8 openai/google image_gen rows now route to openrouter_image_gen."""
    fn, _key, tag = _dispatch(model_id, "image_gen", {"OPENROUTER_API_KEY": "x"})
    assert fn is openrouter_image_gen.bench_one, f"{model_id} → wrong client"
    assert tag == "openrouter"


@pytest.mark.parametrize(
    "model_id",
    [
        "stability/sd3.5-large",
        "stability/sd3.5-large-turbo",
        "stability/stable-audio-2",
    ],
)
def test_stability_dispatch_now_reaches_replicate(model_id):
    """Stability sd3.5/audio-2 route to replicate — and the SLUG_TRANSLATION
    lets bench_one hit `/v1/models/<official>/predictions` instead of falling
    through to the no-version-pinned error path.
    """
    fn, _key, tag = _dispatch(
        model_id,
        "image_gen" if "audio" not in model_id else "music_gen",
        {"REPLICATE_API_TOKEN": "x"},
    )
    assert fn is replicate.bench_one, f"{model_id} → wrong client"
    assert tag == "replicate_direct"
    # The translation dict must map each internal id to an OFFICIAL_MODELS entry.
    slug = replicate._SLUG_TRANSLATION.get(model_id)
    assert slug is not None, f"missing SLUG_TRANSLATION for {model_id}"
    assert slug in replicate.OFFICIAL_MODELS, f"{slug} not in OFFICIAL_MODELS"


def test_openrouter_client_error_shape():
    """bench_one's transport error path returns the standard error dict shape."""
    # Force a transport error by pointing at an unreachable host.
    from unittest.mock import patch

    import requests

    with patch.object(
        requests,
        "post",
        side_effect=requests.ConnectionError("dial tcp: connection refused"),
    ):
        result = openrouter_image_gen.bench_one("openai/gpt-5-image", "fake-key")
    assert result["perf_seconds"] is None
    assert result["cost_usd"] == 0.0
    assert "openrouter transport" in (result["error"] or "")


def test_openrouter_client_http_error_shape():
    """A 4xx from OpenRouter surfaces as a non-None error string, perf_seconds=None."""
    from unittest.mock import MagicMock, patch

    import requests

    fake = MagicMock()
    fake.status_code = 402
    fake.text = "insufficient credits"
    with patch.object(requests, "post", return_value=fake):
        result = openrouter_image_gen.bench_one("openai/gpt-5-image", "fake-key")
    assert result["perf_seconds"] is None
    assert "402" in (result["error"] or "")
    assert "insufficient credits" in (result["error"] or "")
