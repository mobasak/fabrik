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

__all__: list[str] = []  # populated by Phase B (fetch_hf_metadata) + Phase C (fetch_ms_metadata)
