#!/usr/bin/env python3
"""
Per-role shortlist generator for the embedding pipeline.

Mirrors chat's `pre_filter.py`: writes `embedding_shortlists.json` containing
per-role candidate lists (top-N by cost-axis after applying floors). Diagnostic
output for humans + downstream eval scripts; the canonical winner table is
populated by `embedding_role_mapper.py`.

Usage:
    python scripts/kilo-benchmarks/embedding_pre_filter.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))

from embedding_selector import (  # noqa: E402  (sibling-import after sys.path tweak)
    NoEligibleEmbeddingError,
    select_for_role,
)

CONFIG_PATH = SCRIPT_DIR / "embedding_role_configs.yaml"
SHORTLISTS_PATH = SCRIPT_DIR / "embedding_shortlists.json"

# Shortlists are diagnostic — keep more candidates than slots so a human
# reviewing the JSON can see the next-best alternative.
SHORTLIST_LIMIT_MULTIPLIER = 3
MIN_SHORTLIST = 5


def build_shortlists() -> dict[str, list[dict]]:
    cfg = yaml.safe_load(CONFIG_PATH.read_text())
    roles = cfg.get("roles", {})

    shortlists: dict[str, list[dict]] = {}
    for role_name, role_cfg in roles.items():
        slots = int(role_cfg.get("slots", 1))
        limit = max(MIN_SHORTLIST, slots * SHORTLIST_LIMIT_MULTIPLIER)
        try:
            rows = select_for_role(role_cfg, limit=limit)
        except NoEligibleEmbeddingError as e:
            shortlists[role_name] = []
            print(f"[embedding_pre_filter] {role_name}: 0 candidates ({e})")
            continue
        shortlists[role_name] = [
            {
                "id": r["id"],
                "provider": r["provider"],
                "input_cost_per_m": r["input_cost_per_m"],
                "context_window_k": r["context_window_k"],
                "quality_tier": r["quality_tier"],
                "is_multilingual": r["is_multilingual"],
                "is_code_tuned": r["is_code_tuned"],
                "dimensions": r["dimensions"],
                "score_used": r["score_used"],
                "score_type": r["score_type"],
            }
            for r in rows
        ]
        print(f"[embedding_pre_filter] {role_name}: {len(rows)} candidates")
    return shortlists


def main() -> int:
    shortlists = build_shortlists()
    SHORTLISTS_PATH.write_text(json.dumps(shortlists, indent=2, default=str))
    print(f"[embedding_pre_filter] wrote → {SHORTLISTS_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
