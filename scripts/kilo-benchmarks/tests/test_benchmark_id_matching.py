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


def test_override_map_shape_and_all_targets_exist_in_db():
    """B4: guardrail — every override value MUST point to a real active
    agents.id in kilo_agents.db, and the map must be non-trivially sized.

    F15 defense: prior version of this test only asserted 2 hardcoded keys
    exist + 3 values are present — trivially satisfied by almost any map,
    overclaimed "top 20 coverage." Now assert:
      (a) the map has ≥ 10 entries (real seed, not a stub);
      (b) EVERY value resolves to a real (status='active') agents.id — a
          typo'd or renamed agent_id in the map would silently no-op every
          UPDATE downstream while still incrementing `swe_matched` counts.
    """
    import sqlite3

    from scrape_coding_benchmarks import BENCHMARK_NAME_TO_AGENT_ID

    assert len(BENCHMARK_NAME_TO_AGENT_ID) >= 10, (
        f"map size {len(BENCHMARK_NAME_TO_AGENT_ID)} — too small; "
        "either seed more entries or drop this test"
    )
    db_path = Path(__file__).resolve().parent.parent / "kilo_agents.db"
    if not db_path.exists():
        # Local dev without the DB — best-effort skip. CI has the DB.
        import pytest as _pytest

        _pytest.skip(f"kilo_agents.db not present at {db_path}")
    con = sqlite3.connect(str(db_path))
    try:
        active_ids = {
            row[0]
            for row in con.execute("SELECT id FROM agents WHERE status='active'")
        }
    finally:
        con.close()
    missing = [
        (name, target)
        for name, target in BENCHMARK_NAME_TO_AGENT_ID.items()
        if target not in active_ids
    ]
    assert not missing, (
        "override map points to agents.id values that don't exist "
        f"(or aren't active): {missing[:5]}"
    )
