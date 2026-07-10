#!/usr/bin/env python3
# AFTER-EDIT: scripts/kilo-benchmarks/scrape_modelscope_catalog.py scripts/kilo-benchmarks/tests/test_ms_enrich.py
"""ModelScope-specific metadata enrichment for --ingest-new mode.

Two tiers, in order:
  1. HuggingFace Hub — two-endpoint fetch (partial config + full config.json)
  2. modelscope.cn — Next.js SPA scrape via vendored web-scrape module

Both tiers fail-open (return None on any error). The caller
(scrape_modelscope_catalog.py:ingest_new) falls to placeholder defaults
if both return None.

Phase-2 plan reference: docs/development/plans/2026-07-10-plan-2-modelscope-new-row-ingest.md
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from typing import Any

import httpx

__all__: list[str] = ["HFMetadata", "fetch_hf_metadata"]

_HF_API = "https://huggingface.co/api/models/{}"
_HF_CONFIG = "https://huggingface.co/{}/resolve/main/config.json"
_HTTP_TIMEOUT = 10.0

_REASONING_TAGS = frozenset({"thinking", "reasoning"})
_TOOLS_TAGS = frozenset({"function-calling", "tool-use", "tools"})
_VISION_TAGS = frozenset(
    {"vision", "image-text-to-text", "image-to-text", "visual-question-answering"}
)

# Broad fail-open catches around unpredictable network/data. Includes
# httpx.InvalidURL (not a subclass of httpx.HTTPError in httpx 0.28) +
# AttributeError (non-dict JSON payloads).
_HF_FETCH_ERRORS: tuple[type[BaseException], ...] = (
    httpx.HTTPError,
    httpx.InvalidURL,
    json.JSONDecodeError,
    ValueError,
    AttributeError,
    TypeError,
)


@dataclass(frozen=True)
class HFMetadata:
    context_window_k: int | None
    has_reasoning: bool
    has_tools: bool
    has_vision: bool
    is_gated: bool
    model_type: str | None
    pipeline_tag: str | None
    source_url: str


def _tags_intersect(tags: list[str] | None, needles: frozenset[str]) -> bool:
    if not tags:
        return False
    lowered = {str(t).lower() for t in tags if isinstance(t, str)}
    return bool(lowered & needles)


def _extract_context_k(cfg: dict[str, Any]) -> int | None:
    """Pull max context length from HF config.json. Handles nested VLM shapes.

    Common keys in order: max_position_embeddings (LLM), n_positions (GPT-style),
    max_seq_len / seq_length (some architectures). Also walks text_config for
    LLaVA-style VLMs where the LM lives in a nested block.
    """
    for key in ("max_position_embeddings", "n_positions", "max_seq_len", "seq_length"):
        v = cfg.get(key)
        if isinstance(v, int) and v > 0:
            return v // 1024
    # VLM fallback: text-tower config
    text_cfg = cfg.get("text_config")
    if isinstance(text_cfg, dict):
        return _extract_context_k(text_cfg)
    return None


def fetch_hf_metadata(hf_id: str, *, client: httpx.Client | None = None) -> HFMetadata | None:
    """Fetch HF Hub metadata via /api/models + /resolve/main/config.json.

    Fail-open: returns None on any error (404, 5xx, network, JSON parse,
    non-dict payloads, malformed IDs). Partial data OK: if /resolve missed,
    context_window_k stays None.
    """
    owned_client = client is None
    if client is None:
        client = httpx.Client(timeout=_HTTP_TIMEOUT, follow_redirects=True)
    try:
        api_url = _HF_API.format(hf_id)
        try:
            r = client.get(api_url)
            r.raise_for_status()
            api_data_raw: Any = r.json()
            if not isinstance(api_data_raw, dict):
                raise TypeError(f"HF /api returned non-dict: {type(api_data_raw).__name__}")
            api_data: dict[str, Any] = api_data_raw
        except _HF_FETCH_ERRORS as exc:
            print(f"[ms_enrich] WARN: HF /api miss for {hf_id}: {exc}", file=sys.stderr)
            return None

        tags = api_data.get("tags") or []
        pipeline_tag = api_data.get("pipeline_tag")
        # /resolve/main/config.json is best-effort
        context_window_k: int | None = None
        model_type: str | None = None
        try:
            r2 = client.get(_HF_CONFIG.format(hf_id))
            r2.raise_for_status()
            cfg_raw: Any = r2.json()
            if isinstance(cfg_raw, dict):
                context_window_k = _extract_context_k(cfg_raw)
                mt = cfg_raw.get("model_type")
                if isinstance(mt, str):
                    model_type = mt
        except _HF_FETCH_ERRORS:
            pass  # partial data acceptable

        # Vision signal: also inspect pipeline_tag (some HF entries expose the
        # tag only in pipeline_tag, not the tags array).
        pipe_lower = (pipeline_tag or "").lower()
        has_vision = _tags_intersect(tags, _VISION_TAGS) or pipe_lower in _VISION_TAGS

        return HFMetadata(
            context_window_k=context_window_k,
            has_reasoning=_tags_intersect(tags, _REASONING_TAGS),
            has_tools=_tags_intersect(tags, _TOOLS_TAGS),
            has_vision=has_vision,
            is_gated=bool(api_data.get("gated")),
            model_type=model_type,
            pipeline_tag=pipeline_tag,
            source_url=api_url,
        )
    finally:
        if owned_client:
            client.close()
