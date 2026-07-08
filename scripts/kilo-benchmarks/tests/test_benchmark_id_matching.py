"""Behavior Contract for the SWE/Aider manual override map in
scrape_coding_benchmarks.py.

Phase E of plan-4 (pipeline-health coverage closure). The map is consulted
BEFORE the fuzzy canon_variants path, mirroring GROQ_TO_OR_ID at
scrape_groq_speeds.py:187.
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def test_manual_override_precedence():
    """B1: manual-override lookup wins even against an empty canon_idx.

    Even if the fuzzy matcher would fail (no canon_variants match), an entry
    listed in BENCHMARK_NAME_TO_AGENT_ID resolves.
    """
    from scrape_coding_benchmarks import BENCHMARK_NAME_TO_AGENT_ID, _match_id

    empty_idx: dict[str, str] = {}
    name = "mini-SWE-agent + Claude 4.5 Opus medium (20251101)"
    assert name in BENCHMARK_NAME_TO_AGENT_ID
    assert _match_id(empty_idx, name) == "anthropic/claude-opus-4.5"


def test_fuzzy_fallback_preserved():
    """B2: an entry NOT in the manual map still routes to canon_variants."""
    from scrape_coding_benchmarks import _match_id

    canon_idx = {"anthropic-claude-opus-4-5": "anthropic/claude-opus-4.5"}
    # This name is NOT in BENCHMARK_NAME_TO_AGENT_ID, so it must go through
    # canon_variants (which will canonicalize "Claude 4.5 Opus" → "claude-4-5-opus"
    # then also try "claude-opus-4-5") and hit the canon_idx entry above.
    assert _match_id(canon_idx, "Anthropic Claude 4.5 Opus") == "anthropic/claude-opus-4.5"


def test_unknown_returns_none():
    """B3: name not in override AND not resolvable via fuzzy → None."""
    from scrape_coding_benchmarks import _match_id

    canon_idx = {"anthropic-claude-opus-4-5": "anthropic/claude-opus-4.5"}
    assert _match_id(canon_idx, "Warp") is None
    assert _match_id(canon_idx, "Some Proprietary Agent v99") is None


def test_override_covers_top_20_unmatched_patterns():
    """B4: coverage — the map covers the highest-value unmatched patterns.

    The daily_refresh --dry-run 2026-07-08 dumped these names as SWE
    unmatched samples; the map targets the ones behind a resolvable base
    model (proprietary-agent-only entries like Warp / ACoder / Harness AI
    have no meaningful mapping and stay unmatched).
    """
    from scrape_coding_benchmarks import BENCHMARK_NAME_TO_AGENT_ID

    # At least the mini-SWE-agent + Claude 4.5 Opus pair (highest frequency).
    assert (
        "mini-SWE-agent + Claude 4.5 Opus medium (20251101)"
        in BENCHMARK_NAME_TO_AGENT_ID
    )
    assert (
        "live-SWE-agent + Claude 4.5 Opus medium (20251101)"
        in BENCHMARK_NAME_TO_AGENT_ID
    )
    # And the top-3 base models operators care about.
    values = set(BENCHMARK_NAME_TO_AGENT_ID.values())
    assert "anthropic/claude-opus-4.5" in values
    assert "anthropic/claude-sonnet-4.5" in values
    assert "openai/gpt-5" in values
