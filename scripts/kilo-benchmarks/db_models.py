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

# Priority → tier name mapping.
#
# Under cheapest-above-floors semantics:
#   P1 = cheapest qualified agent (every priority meets quality + speed floors)
#   P5 = most expensive qualified agent (= highest quality among survivors)
#
# Tier labels are intentionally kept ("Free"/"Prime") for compatibility with
# kilo_code_review.py, which hardcodes them. The MAPPING is inverted vs the
# old capability-first scheme so that:
#   - "Prime" tier callers (high-risk paths) get P5 = highest quality slot
#   - "Free" tier callers (low-risk paths) get P1 = cheapest qualified slot
#
# The name "Free" is now a misnomer (P1 isn't $0/M anymore, just cheapest above
# floors) but renaming would require coordinated edits in kilo_code_review.py
# and other consumers. Track that as a follow-up.
PRIORITY_TO_TIER = {
    1: "Free",  # cheapest qualified
    2: "Economy",
    3: "Balanced",
    4: "Strong",
    5: "Prime",  # most expensive qualified (= highest quality)
}

# Escalation paths: strategy → list of priorities to try, in order.
# Updated to reflect cheapest-above-floors: low-risk paths start at P1
# (cheap) and escalate UP; high-risk paths start at P5 (premium) and
# escalate DOWN to mid-range fallbacks.
ESCALATION_PATHS = {
    "free": [1, 2, 3],  # Start cheapest qualified, escalate to mid
    "economy": [2, 3, 4],  # Start economy, escalate to strong
    "standard": [3, 4, 5],  # Start balanced, escalate to premium
    "premium": [4, 5],  # Start strong, escalate to premium
    "critical": [5],  # Premium only (highest quality)
}

# Rough estimated cost per priority level for budget pre-checks.
# Real costs vary by role and model — this is only for order-of-magnitude
# budget gates in the router.
PRIORITY_ESTIMATED_COST = {
    1: 0.015,  # cheapest qualified (e.g., Gemini 3.1 Pro ~$14/M @ ~1K tokens)
    2: 0.016,
    3: 0.017,
    4: 0.020,
    5: 0.030,  # premium (e.g., Opus 4.6 ~$30/M @ ~1K tokens)
}


# Legacy alias: the `coding` role was split into coding_simple +
# coding_complex on 2026-05-13. Callers that haven't migrated yet get
# coding_complex (the safer default — quality over cost). Use
# classify_ticket() at the dispatch site to choose the right tier explicitly.
LEGACY_ROLE_ALIASES = {
    "coding": "coding_complex",
}


def _resolve_role(role: str) -> str:
    """Map legacy role names to current canonical names."""
    return LEGACY_ROLE_ALIASES.get(role, role)


def get_model_for_priority(role: str, priority: int) -> str | None:
    """
    Get model API ID for a specific role and priority.

    Args:
        role: One of 'coding_simple', 'coding_complex', 'reviewing', 'fixing',
              'documentation', 'testing'. Legacy 'coding' resolves to
              'coding_complex' for backwards compatibility — but new code
              should classify the ticket and pass the explicit tier.
        priority: 1-5. Under cheapest-above-floors: 1=cheapest qualified,
                  5=most expensive (= highest quality among survivors).

    Returns:
        Model API ID with kilo/ prefix (e.g., "kilo/anthropic/claude-opus-4.6")
        or None if not found.
    """
    role = _resolve_role(role)
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


def get_model_avoiding_provider(
    role: str,
    exclude_provider: str | None,
    max_priority: int = 5,
) -> tuple[str | None, int | None, str | None]:
    """
    Pick the cheapest qualified agent for `role` whose provider is NOT
    `exclude_provider`. Used by the dispatcher to enforce the same-family
    cross-role guard (coder and reviewer should not share a provider so a
    Google outage doesn't take down both halves of a ticket).

    Walks priorities 1 → max_priority and returns the first match. If every
    qualified agent belongs to the excluded provider, falls through to the
    cheapest qualified agent anyway (better to dispatch a same-family pair
    than to drop the ticket).

    Args:
        role: 'coding_simple', 'coding_complex', 'reviewing', 'fixing',
              'documentation', or 'testing'. Legacy 'coding' → 'coding_complex'.
        exclude_provider: provider string to avoid (e.g. 'google').
                          Pass None to skip the guard.
        max_priority: highest priority to consider (default 5).

    Returns:
        (kilo_id, priority, reason) where reason is 'avoided', 'fallback', or
        'no-guard'. kilo_id is None only when the role has zero assignments.
    """
    role = _resolve_role(role)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.execute(
            """
            SELECT a.api_id, a.provider, r.priority
              FROM agent_roles r
              JOIN agents a ON a.id = r.agent_id
             WHERE r.role = ?
               AND r.priority <= ?
               AND a.status = 'active'
               AND a.blocked = 0
          ORDER BY r.priority
            """,
            (role, max_priority),
        )
        rows = cur.fetchall()
    finally:
        conn.close()

    if not rows:
        return None, None, None

    if not exclude_provider:
        first = rows[0]
        return f"kilo/{first['api_id']}", first["priority"], "no-guard"

    # Prefer cross-family
    for row in rows:
        if row["provider"] != exclude_provider:
            return f"kilo/{row['api_id']}", row["priority"], "avoided"

    # Fallback: every qualified row is the excluded provider. Ship anyway.
    first = rows[0]
    return f"kilo/{first['api_id']}", first["priority"], "fallback"


def get_models_by_priority(role: str, priorities: list[int]) -> list[str]:
    """
    Get models for multiple priorities (for escalation paths).

    Args:
        role: 'coding_simple' | 'coding_complex' | 'reviewing' | 'fixing' |
              'documentation' | 'testing'. Legacy 'coding' → 'coding_complex'.
        priorities: List of priorities to include (e.g., [3, 2, 1])

    Returns:
        List of model API IDs with kilo/ prefix, ordered by input priorities
    """
    role = _resolve_role(role)
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
    Get ordered fallback chain for a role, priority 1 → 5.

    Under cheapest-above-floors semantics, priority 1 is the cheapest qualified
    model and 5 is the most expensive. The "fallback" name predates the
    inversion — callers iterating this list should still treat it as
    "try in this order", but the order is now cheapest-first.

    Args:
        role: 'coding_simple' | 'coding_complex' | 'reviewing' | 'fixing' |
              'documentation' | 'testing'. Legacy 'coding' → 'coding_complex'.

    Returns:
        List of model API IDs ordered by priority ASC.
    """
    role = _resolve_role(role)
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

    Tier semantics under cheapest-above-floors:
        Free    → P1 (cheapest qualified)
        Economy → P2
        Balanced → P3
        Strong  → P4
        Prime   → P5 (most expensive = highest quality among survivors)
    """
    role = _resolve_role(role)
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
