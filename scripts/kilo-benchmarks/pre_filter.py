#!/usr/bin/env python3
"""
Pre-filter for role mapper.

Creates per-role shortlists with hard filters and ranking.
Reduces input from 117 models to ~60 across 5 role-scoped lists.
"""

import json
import sqlite3
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).parent
DB_PATH = SCRIPT_DIR / "kilo_agents.db"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def pre_filter() -> dict[str, list[dict[str, Any]]]:
    """Generate per-role shortlists."""
    conn = get_connection()
    shortlists = {}

    # Helper to compute perf_per_dollar
    def compute_perf_per_dollar(
        arena_elo: float | None, input_cost: float | None, output_cost: float | None
    ) -> float:
        """Compute performance per dollar metric."""
        base_elo = arena_elo or 1400
        total_cost = (input_cost or 0) + (output_cost or 0) + 0.01
        return base_elo / total_cost

    def enrich_metrics(model: dict[str, Any]) -> None:
        """Compute derived metrics referenced by role_configs.yaml primary_metric."""
        input_cost = model.get("input_cost_per_m") or 0
        output_cost = model.get("output_cost_per_m") or 0
        total_cost = input_cost + output_cost + 0.01
        model["inverse_total_cost"] = 1.0 / total_cost

        tbench = model.get("tbench_accuracy")
        elo = model.get("arena_elo")
        if tbench is None and elo is None:
            model["mean_normalized_tbench_elo"] = None
        else:
            tbench_norm = (tbench or 0) / 100.0
            elo_norm = (elo or 1400) / 1600.0
            model["mean_normalized_tbench_elo"] = (tbench_norm + elo_norm) / 2.0

    # Standard fields for all queries
    standard_fields = """
        id, name, provider, arena_elo, tbench_accuracy, weighted_coding,
        input_cost_per_m, output_cost_per_m, context_window_k,
        has_tools, is_agentic, has_reasoning, has_vision,
        output_tokens_per_sec, ttft_ms
    """

    # coding_simple: lower quality bar AND hard cost ceiling at SQL level. The
    # cost filter is critical here — without it, the LIMIT 12 fills with
    # premium models (sorted by weighted_coding DESC) that all fail the $5
    # cost_cap downstream, leaving the cheap-tier candidates crowded out of
    # the shortlist entirely. Same $5 ceiling also lives in role_configs.yaml
    # as defense-in-depth.
    cursor = conn.execute(f"""
        SELECT {standard_fields}
        FROM agents
        WHERE status = 'active' AND blocked = 0
          AND has_tools = 1 AND is_agentic = 1
          AND weighted_coding >= 75.0
          AND (input_cost_per_m + output_cost_per_m) <= 5.0
        ORDER BY weighted_coding DESC
        LIMIT 12
    """)
    coding_simple_models = []
    for row in cursor.fetchall():
        model = dict(row)
        model["perf_per_dollar"] = compute_perf_per_dollar(
            model["arena_elo"], model["input_cost_per_m"], model["output_cost_per_m"]
        )
        enrich_metrics(model)
        coding_simple_models.append(model)
    shortlists["coding_simple"] = coding_simple_models

    # coding_complex: high bar so only top-tier coders qualify. Default route
    # for ambiguous tickets — quality regressions are more expensive than
    # cost regressions.
    cursor = conn.execute(f"""
        SELECT {standard_fields}
        FROM agents
        WHERE status = 'active' AND blocked = 0
          AND has_tools = 1 AND is_agentic = 1
          AND weighted_coding >= 85.0
        ORDER BY weighted_coding DESC
        LIMIT 12
    """)
    coding_complex_models = []
    for row in cursor.fetchall():
        model = dict(row)
        model["perf_per_dollar"] = compute_perf_per_dollar(
            model["arena_elo"], model["input_cost_per_m"], model["output_cost_per_m"]
        )
        enrich_metrics(model)
        coding_complex_models.append(model)
    shortlists["coding_complex"] = coding_complex_models

    # Reviewing: has_reasoning=1, status=active, rank by arena_elo
    cursor = conn.execute(f"""
        SELECT {standard_fields}
        FROM agents
        WHERE status = 'active' AND blocked = 0
          AND has_reasoning = 1
        ORDER BY arena_elo DESC
        LIMIT 12
    """)
    reviewing_models = []
    for row in cursor.fetchall():
        model = dict(row)
        model["perf_per_dollar"] = compute_perf_per_dollar(
            model["arena_elo"], model["input_cost_per_m"], model["output_cost_per_m"]
        )
        enrich_metrics(model)
        reviewing_models.append(model)
    shortlists["reviewing"] = reviewing_models

    # Fixing: has_tools=1, is_agentic=1, rank by mean(norm(tbench), norm(arena_elo))
    cursor = conn.execute(f"""
        SELECT {standard_fields}
        FROM agents
        WHERE status = 'active' AND blocked = 0
          AND has_tools = 1 AND is_agentic = 1
        ORDER BY
            (COALESCE(tbench_accuracy, 0) / 100.0 + COALESCE(arena_elo, 0) / 1600.0) DESC
        LIMIT 12
    """)
    fixing_models = []
    for row in cursor.fetchall():
        model = dict(row)
        model["perf_per_dollar"] = compute_perf_per_dollar(
            model["arena_elo"], model["input_cost_per_m"], model["output_cost_per_m"]
        )
        enrich_metrics(model)
        fixing_models.append(model)
    shortlists["fixing"] = fixing_models

    # Documentation: arena_elo>=1400, input_cost<=1.00, status=active, rank by arena_elo (quality)
    cursor = conn.execute(f"""
        SELECT {standard_fields}
        FROM agents
        WHERE status = 'active' AND blocked = 0
          AND arena_elo >= 1400
          AND input_cost_per_m <= 1.00
        ORDER BY arena_elo DESC
        LIMIT 10
    """)
    documentation_models = []
    for row in cursor.fetchall():
        model = dict(row)
        model["perf_per_dollar"] = compute_perf_per_dollar(
            model["arena_elo"], model["input_cost_per_m"], model["output_cost_per_m"]
        )
        enrich_metrics(model)
        documentation_models.append(model)
    shortlists["documentation"] = documentation_models

    # Testing: has_tools=1, is_agentic=1, status=active, rank by tbench (fallback weighted_coding)
    cursor = conn.execute(f"""
        SELECT {standard_fields}
        FROM agents
        WHERE status = 'active' AND blocked = 0
          AND has_tools = 1 AND is_agentic = 1
        ORDER BY
            CASE
                WHEN tbench_accuracy IS NOT NULL THEN tbench_accuracy
                WHEN weighted_coding IS NOT NULL THEN weighted_coding
                ELSE 0
            END DESC
        LIMIT 10
    """)
    testing_models = []
    for row in cursor.fetchall():
        model = dict(row)
        model["perf_per_dollar"] = compute_perf_per_dollar(
            model["arena_elo"], model["input_cost_per_m"], model["output_cost_per_m"]
        )
        enrich_metrics(model)
        testing_models.append(model)
    shortlists["testing"] = testing_models

    conn.close()

    # Warn on empty shortlists
    for role, models in shortlists.items():
        if len(models) < 3:
            print(f"WARNING: {role} shortlist has only {len(models)} models")

    # Write JSON output
    out_path = SCRIPT_DIR / "shortlists.json"
    out_path.write_text(json.dumps(shortlists, indent=2, default=str))
    print(f"Wrote shortlists to {out_path}")

    return shortlists


if __name__ == "__main__":
    shortlists = pre_filter()
    for role, models in shortlists.items():
        print(f"\n{role}: {len(models)} models")
