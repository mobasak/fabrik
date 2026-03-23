#!/usr/bin/env python3
"""
Database-driven model selection for Kilo CLI wrappers.

Purpose: Provides functions to query reviewer/coder/fixer models from kilo_agents.db.
         Replaces hardcoded TIER_MODELS and MODEL_FALLBACK_CHAIN in kilo scripts.

Usage:
    from db_models import get_models_by_priority, get_fallback_chain, get_model_for_priority

When updating: Also update README.md in this folder.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

# DB path - same folder as this module
DB_PATH = Path(__file__).parent / "kilo_agents.db"

# Priority to tier name mapping (for logging/display only)
PRIORITY_TO_TIER = {
    1: "Prime",
    2: "Strong",
    3: "Balanced",
    4: "Economy",
    5: "Free",
}

# Escalation paths: strategy → list of priorities to try
# These define escalation policy, not model data
ESCALATION_PATHS = {
    "free": [5, 4, 3],  # Start cheapest, escalate up
    "economy": [4, 3, 2],  # Start economy, escalate up
    "standard": [3, 2, 1],  # Start balanced, escalate to best
    "premium": [2, 1],  # Start strong, escalate to prime
    "critical": [1],  # Only priority 1 (best)
}

# Estimated cost per priority level (for budget checks)
PRIORITY_ESTIMATED_COST = {
    5: 0.0,  # Free tier
    4: 0.02,  # Economy
    3: 0.01,  # Balanced (often best value)
    2: 0.05,  # Strong
    1: 0.50,  # Prime
}


def get_model_for_priority(role: str, priority: int) -> str | None:
    """
    Get model API ID for a specific role and priority.

    Args:
        role: One of 'coding', 'reviewing', 'fixing', 'documentation', 'testing'
        priority: 1-5 (1=best, 5=cheapest)

    Returns:
        Model API ID with kilo/ prefix (e.g., "kilo/anthropic/claude-opus-4.6")
        or None if not found
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.execute(
        """
        SELECT a.api_id
        FROM agent_roles r
        JOIN agents a ON a.id = r.agent_id
        WHERE r.role = ? AND r.priority = ?
          AND a.status = 'active' AND a.blocked = 0
    """,
        (role, priority),
    )
    row = cursor.fetchone()
    conn.close()

    if row:
        return f"kilo/{row[0]}"
    return None


def get_models_by_priority(role: str, priorities: list[int]) -> list[str]:
    """
    Get models for multiple priorities (for escalation paths).

    Args:
        role: One of 'coding', 'reviewing', 'fixing', 'documentation', 'testing'
        priorities: List of priorities to include (e.g., [3, 2, 1])

    Returns:
        List of model API IDs with kilo/ prefix, ordered by input priorities
    """
    conn = sqlite3.connect(DB_PATH)
    models = []
    for priority in priorities:
        cursor = conn.execute(
            """
            SELECT a.api_id
            FROM agent_roles r
            JOIN agents a ON a.id = r.agent_id
            WHERE r.role = ? AND r.priority = ?
              AND a.status = 'active' AND a.blocked = 0
        """,
            (role, priority),
        )
        row = cursor.fetchone()
        if row:
            models.append(f"kilo/{row[0]}")
    conn.close()
    return models


def get_fallback_chain(role: str) -> list[str]:
    """
    Get ordered fallback chain for a role (priority 1 → 5).

    Args:
        role: One of 'coding', 'reviewing', 'fixing', 'documentation', 'testing'

    Returns:
        List of model API IDs, best first (priority 1, 2, 3, 4, 5)
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.execute(
        """
        SELECT a.api_id
        FROM agent_roles r
        JOIN agents a ON a.id = r.agent_id
        WHERE r.role = ?
          AND a.status = 'active' AND a.blocked = 0
        ORDER BY r.priority
    """,
        (role,),
    )
    rows = cursor.fetchall()
    conn.close()
    return [f"kilo/{r[0]}" for r in rows]


def get_escalation_models(role: str, strategy: str) -> list[str]:
    """
    Get models for an escalation strategy.

    Args:
        role: One of 'coding', 'reviewing', 'fixing', 'documentation', 'testing'
        strategy: One of 'free', 'economy', 'standard', 'premium', 'critical'

    Returns:
        List of model API IDs to try in order
    """
    priorities = ESCALATION_PATHS.get(strategy, ESCALATION_PATHS["economy"])
    return get_models_by_priority(role, priorities)


def get_tier_models(role: str) -> dict[str, list[str]]:
    """
    Get all models organized by tier (for compatibility with existing code).

    Returns dict mapping tier name to list of models:
    {
        "Prime": ["kilo/anthropic/claude-opus-4.6"],
        "Strong": ["kilo/google/gemini-3.1-pro-preview"],
        ...
    }
    """
    tiers: dict[str, list[str]] = {
        "Prime": [],
        "Strong": [],
        "Balanced": [],
        "Economy": [],
        "Free": [],
    }

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.execute(
        """
        SELECT a.api_id, r.priority
        FROM agent_roles r
        JOIN agents a ON a.id = r.agent_id
        WHERE r.role = ?
          AND a.status = 'active' AND a.blocked = 0
        ORDER BY r.priority
    """,
        (role,),
    )

    for api_id, priority in cursor.fetchall():
        tier = PRIORITY_TO_TIER.get(priority, "Balanced")
        tiers[tier].append(f"kilo/{api_id}")

    conn.close()
    return tiers


def get_model_cost(model_id: str) -> tuple[float, float]:
    """
    Get input/output cost per 1M tokens for a model.

    Args:
        model_id: Full model ID (with or without kilo/ prefix)

    Returns:
        (input_cost_per_m, output_cost_per_m) or (0.0, 0.0) if not found
    """
    # Strip kilo/ prefix if present
    api_id = model_id.replace("kilo/", "")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.execute(
        """
        SELECT input_cost_per_m, output_cost_per_m
        FROM agents WHERE api_id = ?
    """,
        (api_id,),
    )
    row = cursor.fetchone()
    conn.close()

    if row:
        return (row[0] or 0.0, row[1] or 0.0)
    return (0.0, 0.0)


def is_model_blocked(model_id: str) -> bool:
    """
    Check if a model is blocked.

    Args:
        model_id: Full model ID (with or without kilo/ prefix)

    Returns:
        True if blocked, False otherwise
    """
    api_id = model_id.replace("kilo/", "")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.execute(
        """
        SELECT blocked FROM agents WHERE api_id = ?
    """,
        (api_id,),
    )
    row = cursor.fetchone()
    conn.close()

    return bool(row and row[0])


def has_reasoning(model_id: str) -> bool:
    """
    Check if a model has reasoning capability.

    Args:
        model_id: Full model ID (with or without kilo/ prefix)

    Returns:
        True if model has reasoning capability, False otherwise
    """
    api_id = model_id.replace("kilo/", "")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.execute(
        """
        SELECT has_reasoning FROM agents WHERE api_id = ?
    """,
        (api_id,),
    )
    row = cursor.fetchone()
    conn.close()

    return bool(row and row[0])


def get_reasoning_models() -> set[str]:
    """
    Get all models with reasoning capability.

    Returns:
        Set of model API IDs with kilo/ prefix that have reasoning capability
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.execute(
        """
        SELECT api_id FROM agents
        WHERE has_reasoning = 1 AND status = 'active' AND blocked = 0
    """
    )
    rows = cursor.fetchall()
    conn.close()

    return {f"kilo/{r[0]}" for r in rows}


if __name__ == "__main__":
    # Quick test
    print("=== Reviewer Models ===")
    for priority in range(1, 6):
        model = get_model_for_priority("reviewing", priority)
        tier = PRIORITY_TO_TIER[priority]
        print(f"  Priority {priority} ({tier}): {model}")

    print("\n=== Fallback Chain (reviewing) ===")
    chain = get_fallback_chain("reviewing")
    for i, model in enumerate(chain, 1):
        print(f"  {i}. {model}")

    print("\n=== Escalation: standard strategy ===")
    models = get_escalation_models("reviewing", "standard")
    for model in models:
        print(f"  → {model}")

    print("\n=== Tier Models (reviewing) ===")
    tiers = get_tier_models("reviewing")
    for tier, models in tiers.items():
        if models:
            print(f"  {tier}: {models}")
