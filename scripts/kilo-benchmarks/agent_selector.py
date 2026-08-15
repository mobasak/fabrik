#!/usr/bin/env python3
"""
Agent Selector - Runtime task-to-agent routing.

Selects agents based on task complexity, routing to appropriate priority levels.
Complexity is determined at runtime, NOT stored in assignments.

Usage:
    from agent_selector import select_agent, select_reviewer

    # For coding tasks
    agent = select_agent("coding", "complex")  # Returns best coder
    agent = select_agent("coding", "simple")   # Returns cheapest adequate coder

    # For reviewing with vision requirement
    agent = select_reviewer("complex", require_vision=True)
"""

import sqlite3
from pathlib import Path
from typing import Literal

SCRIPT_DIR = Path(__file__).parent
DB_PATH = SCRIPT_DIR / "kilo_agents.db"

# Complexity → Priority fallback chains
# Each complexity level tries priorities in order until one succeeds
COMPLEXITY_MAP: dict[str, list[int]] = {
    "simple": [5, 4, 3, 2, 1],  # cheapest first, full cascade if needed
    "medium": [3, 2, 4, 1, 5],  # balanced first
    "complex": [1, 2, 3],  # best only — fail if unavailable (no cheap fallback)
}

ComplexityLevel = Literal["simple", "medium", "complex"]
RoleType = Literal["coding", "reviewing", "fixing", "documentation", "testing"]


# User-facing → DB role mapping. The `agent_roles` table partitions
# `coding` into TWO separate routes (`coding_simple` with 5 priorities for
# the cheap-cascade chain, `coding_complex` with 3 frontier picks) but
# every other role is stored 1:1 with its user-facing name. Pre-fix the
# selector queried `r.role = "coding"` and got 0 rows for every complexity
# level — silently broken for any caller that wanted a coding agent.
# Verified 2026-06-30: live DB has roles {coding_complex(3), coding_simple(5),
# documentation(5), fixing(5), reviewing(5), testing(2)}.
def _resolve_db_role(role: str, complexity: str) -> str:
    """Map user-facing (role, complexity) → the actual `agent_roles.role` value.

    For coding tasks the DB splits the pool by complexity:
      - complex   → `coding_complex` (frontier-only, 3 priorities)
      - simple    → `coding_simple`  (cheap-cascade, 5 priorities)
      - medium    → `coding_simple`  (balanced order falls through the 5-row pool)
    Every other user-facing role maps 1:1 to its DB row.
    """
    if role == "coding":
        return "coding_complex" if complexity == "complex" else "coding_simple"
    return role


def _all_db_roles_for(role: str) -> list[str]:
    """Used by list_agents_for_role to enumerate every DB row that belongs
    to a user-facing role. Coding fans out across its two pools; everything
    else is a single row."""
    if role == "coding":
        return ["coding_complex", "coding_simple"]
    return [role]


class NoAgentAvailableError(Exception):
    """Raised when no suitable agent is found for the given criteria."""

    pass


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_agent(
    role: RoleType,
    priority: int,
    require_vision: bool = False,
    min_elo: int | None = None,
    *,
    complexity: ComplexityLevel | None = None,
) -> dict | None:
    """
    Get agent for a specific (role, priority) — resolving the user-facing
    role to its DB row first when there's a complexity-split (currently
    only `coding`).

    Args:
        role: User-facing role (coding, reviewing, etc.)
        priority: Priority level (1-5 — varies by role).
        require_vision: If True, only return agents with vision capability.
        min_elo: Optional minimum ELO score requirement.
        complexity: Required when `role == "coding"` to pick the
            coding_simple vs coding_complex pool. Ignored for other roles.

    Returns:
        Agent dict with api_id, name, provider, etc. or None if not found.
    """
    db_role = _resolve_db_role(role, complexity or "simple")
    conn = get_connection()

    query = """
        SELECT
            a.id,
            a.api_id,
            a.name,
            a.provider,
            a.arena_elo,
            a.tbench_accuracy,
            a.input_cost_per_m,
            a.output_cost_per_m,
            a.has_vision,
            a.has_tools,
            a.is_agentic,
            a.perf_per_dollar,
            r.priority,
            r.min_elo as role_min_elo
        FROM agent_roles r
        JOIN agents a ON a.id = r.agent_id
        WHERE r.role = ?
          AND r.priority = ?
          AND a.status = 'active'
          AND a.blocked = 0
    """
    params: list = [db_role, priority]

    if require_vision:
        query += " AND a.has_vision = 1"

    if min_elo is not None:
        query += " AND a.arena_elo >= ?"
        params.append(min_elo)

    query += " LIMIT 1"

    cursor = conn.execute(query, params)
    row = cursor.fetchone()
    conn.close()

    if row:
        return dict(row)
    return None


def select_agent(
    role: RoleType,
    complexity: ComplexityLevel,
    require_vision: bool = False,
    min_elo: int | None = None,
) -> dict:
    """
    Select best available agent for a role based on task complexity.

    Complexity determines which priority levels to try:
    - simple: 5→4→3→2→1 (cheapest first, full cascade)
    - medium: 3→2→4→1→5 (balanced first)
    - complex: 1→2→3 (best only, fails if unavailable)

    Args:
        role: The role to select for
        complexity: Task complexity level
        require_vision: If True, only consider agents with vision
        min_elo: Optional minimum ELO requirement

    Returns:
        Agent dict with api_id, name, etc.

    Raises:
        NoAgentAvailableError: If no suitable agent found
    """
    priorities = COMPLEXITY_MAP.get(complexity)
    if not priorities:
        raise ValueError(f"Unknown complexity level: {complexity}")

    for priority in priorities:
        agent = get_agent(role, priority, require_vision, min_elo, complexity=complexity)
        if agent:
            return agent

    # Build helpful error message
    tried = ", ".join(str(p) for p in priorities)
    vision_note = " with vision" if require_vision else ""
    elo_note = f" (min_elo={min_elo})" if min_elo else ""
    raise NoAgentAvailableError(
        f"No agent found for role={role} complexity={complexity}{vision_note}{elo_note}. "
        f"Tried priorities: {tried}"
    )


def select_reviewer(
    complexity: ComplexityLevel,
    require_vision: bool = False,
    min_elo: int | None = None,
) -> dict:
    """
    Convenience function for selecting a reviewer agent.

    For reviewing tasks, vision is often useful but not always required.
    Call with require_vision=True when reviewing screenshots or diagrams.

    Args:
        complexity: Task complexity level
        require_vision: If True, require vision capability (for image reviews)
        min_elo: Optional minimum ELO requirement

    Returns:
        Agent dict with api_id, name, etc.

    Raises:
        NoAgentAvailableError: If no suitable agent found
    """
    return select_agent("reviewing", complexity, require_vision, min_elo)


def select_coder(complexity: ComplexityLevel, min_elo: int | None = None) -> dict:
    """Convenience function for selecting a coding agent."""
    return select_agent("coding", complexity, min_elo=min_elo)


def select_fixer(complexity: ComplexityLevel, min_elo: int | None = None) -> dict:
    """Convenience function for selecting a fixing agent."""
    return select_agent("fixing", complexity, min_elo=min_elo)


def select_tester(complexity: ComplexityLevel, min_elo: int | None = None) -> dict:
    """Convenience function for selecting a testing agent."""
    return select_agent("testing", complexity, min_elo=min_elo)


def select_documenter(complexity: ComplexityLevel = "simple") -> dict:
    """
    Convenience function for selecting a documentation agent.

    Documentation is cost-optimized by default, so simple complexity
    is usually the right choice.
    """
    return select_agent("documentation", complexity)


def list_agents_for_role(role: RoleType) -> list[dict]:
    """
    List all assigned agents for a user-facing role, ordered by priority.

    For `coding` this returns the union of `coding_simple` + `coding_complex`
    pools — each agent row carries an `_db_role` field so callers can tell
    which pool a given agent belongs to. Other roles are 1:1 with their
    DB row.
    """
    db_roles = _all_db_roles_for(role)
    placeholders = ",".join("?" * len(db_roles))
    conn = get_connection()
    cursor = conn.execute(
        f"""
        SELECT
            a.id,
            a.api_id,
            a.name,
            a.provider,
            a.arena_elo,
            a.tbench_accuracy,
            a.has_vision,
            a.perf_per_dollar,
            r.role AS _db_role,
            r.priority,
            r.min_elo
        FROM agent_roles r
        JOIN agents a ON a.id = r.agent_id
        WHERE r.role IN ({placeholders})
          AND a.status = 'active'
          AND a.blocked = 0
        ORDER BY r.role, r.priority
        """,
        db_roles,
    )
    agents = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return agents


if __name__ == "__main__":
    # Demo usage
    print("Agent Selector Demo\n")

    for role in ["coding", "reviewing", "fixing", "documentation", "testing"]:
        print(f"\n[{role.upper()}]")
        agents = list_agents_for_role(role)  # type: ignore
        for a in agents:
            vision = " [vision]" if a["has_vision"] else ""
            print(f"  #{a['priority']} {a['name']}{vision} (elo={a['arena_elo']})")

    print("\n\nComplexity routing examples:")
    for complexity in ["simple", "medium", "complex"]:
        try:
            agent = select_coder(complexity)  # type: ignore
            print(f"  coding/{complexity}: {agent['name']} (priority {agent['priority']})")
        except NoAgentAvailableError as e:
            print(f"  coding/{complexity}: {e}")
