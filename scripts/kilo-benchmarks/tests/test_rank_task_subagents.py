"""Tests for rank_task_subagents.py — the subagent-runs flywheel aggregator.

Tests the pure ranking function against seeded fixtures — no live DB required.
The DB query itself is exercised in the smoke test in the phase gate.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Import the module under test
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_empty_input_emits_stub_content() -> None:
    """No aggregated rows → stub markdown, exit 0."""
    from rank_task_subagents import render

    md = render([])
    assert "No aggregated runs yet" in md
    assert md.startswith("Last refresh:")


def test_ranks_by_value_success_x_quality_over_cost() -> None:
    """value = success × quality / cost — cheapest AT high quality wins."""
    from rank_task_subagents import render

    # Two models for task_type="spec": one cheap+decent, one expensive+top
    rows = [
        # (task_type, model, n, avg_cost, avg_quality, success_rate)
        ("spec", "cheap-good", 10, 0.10, 1.5, 0.90),  # value = 0.9 * 1.5 / 0.10 = 13.5
        ("spec", "expensive-top", 10, 0.50, 1.7, 0.95),  # value = 0.95 * 1.7 / 0.50 = 3.23
    ]
    md = render(rows)
    # Cheap-good ranks #1 by value
    cheap_pos = md.find("cheap-good")
    exp_pos = md.find("expensive-top")
    assert cheap_pos >= 0 and exp_pos >= 0, md
    assert cheap_pos < exp_pos, f"expected cheap-good above expensive-top in md, got:\n{md}"


def test_min_runs_threshold_filters_out_low_n() -> None:
    """Pairs with fewer than 3 runs must NOT appear in the ranking."""
    from rank_task_subagents import filter_min_runs

    rows = [
        ("spec", "flaky-once", 1, 0.05, 2.0, 1.0),  # 1 run — drop
        ("spec", "twice", 2, 0.05, 2.0, 1.0),  # 2 runs — drop
        ("spec", "thrice", 3, 0.05, 2.0, 1.0),  # 3 runs — keep
        ("spec", "many", 47, 0.32, 1.64, 0.94),  # keep
    ]
    kept = filter_min_runs(rows, min_n=3)
    kept_models = {r[1] for r in kept}
    assert kept_models == {"thrice", "many"}


def test_multiple_task_types_get_separate_sections() -> None:
    """Each task_type gets its own ### section in the emitted markdown."""
    from rank_task_subagents import render

    rows = [
        ("spec", "z-ai/glm-5", 47, 0.32, 1.64, 0.94),
        ("plan", "minimax/minimax-m2.5", 62, 0.28, 1.30, 0.91),
        ("code", "deepseek/deepseek-v3.2", 100, 0.15, 1.20, 0.88),
    ]
    md = render(rows)
    assert "### spec" in md
    assert "### plan" in md
    assert "### code" in md


def test_render_includes_metadata_header() -> None:
    """Emitted MD must carry Last refresh + Formula + Window + Min runs metadata."""
    from rank_task_subagents import render

    md = render([])
    assert "Last refresh:" in md
    assert "Formula:" in md
    assert "Window:" in md
    assert "Min runs:" in md


def test_zero_cost_row_survives_without_division_error() -> None:
    """A zero avg_cost row must not crash the ranker (max(cost, 1e-9) guard)."""
    from rank_task_subagents import render

    rows = [
        ("spec", "free-tier", 5, 0.0, 1.0, 0.80),
    ]
    md = render(rows)
    assert "free-tier" in md  # Row survives; extreme value doesn't crash
