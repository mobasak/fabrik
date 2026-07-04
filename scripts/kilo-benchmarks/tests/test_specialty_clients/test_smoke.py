# AFTER-EDIT: scripts/kilo-benchmarks/specialty_clients/*.py
"""Integration smoke suite for the specialty bench clients.

Opt-in: run with `pytest -m integration`. Skipped by default.
Real provider APIs. Total real cost: ~$0.03 across all 7 tests.

Plan 2026-07-03-plan-1-full-speed-coverage-close.md Phase B.7.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from dotenv import load_dotenv

SCRIPT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(SCRIPT_DIR))

from specialty_clients import (  # noqa: E402
    bfl_via_fal,
    dashscope_translation,
    elevenlabs_sfx,
    elevenlabs_tts,
    openai_whisper,
    recraft,
    replicate,
)


def _key(name: str) -> str:
    load_dotenv("/opt/fabrik/.env")
    v = os.getenv(name)
    if not v:
        pytest.skip(f"{name} not set in /opt/fabrik/.env")
    return v


@pytest.mark.integration
def test_smoke_bfl_via_fal_flux_schnell():
    r = bfl_via_fal.bench_one("bfl/flux-schnell", _key("FAL_KEY"))
    assert r["error"] is None, r
    assert 0.5 < r["perf_seconds"] < 60


@pytest.mark.integration
def test_smoke_recraft_direct_v3():
    r = recraft.bench_one("recraft/v3", _key("RECRAFT_API_KEY"))
    assert r["error"] is None, r
    assert 0.5 < r["perf_seconds"] < 60
    assert 0.005 < r["cost_usd"] < 0.20


@pytest.mark.integration
def test_smoke_replicate_sdxl():
    r = replicate.bench_one("stability/sdxl", _key("REPLICATE_API_TOKEN"))
    assert r["error"] is None, r
    assert 0.5 < r["perf_seconds"] < 120


@pytest.mark.integration
def test_smoke_elevenlabs_tts_multilingual_v2():
    r = elevenlabs_tts.bench_one("elevenlabs/multilingual-v2", _key("ELEVENLABS_API_KEY"))
    assert r["error"] is None, r
    assert 0.3 < r["perf_seconds"] < 30


@pytest.mark.integration
def test_smoke_elevenlabs_sfx_2s():
    r = elevenlabs_sfx.bench_one("elevenlabs/sound-effects", _key("ELEVENLABS_API_KEY"))
    assert r["error"] is None, r
    assert 0.3 < r["perf_seconds"] < 60


@pytest.mark.integration
def test_smoke_openai_whisper_10s_silence():
    r = openai_whisper.bench_one("openai/whisper-large-v3", _key("OPENAI_API_KEY"))
    assert r["error"] is None, r
    assert 0.3 < r["perf_seconds"] < 30


@pytest.mark.integration
def test_smoke_dashscope_qwen_mt_turbo_en_es():
    r = dashscope_translation.bench_one("qwen/qwen-mt-turbo", _key("DASHSCOPE_API_KEY"))
    assert r["error"] is None, r
    assert 0.1 < r["perf_seconds"] < 30
