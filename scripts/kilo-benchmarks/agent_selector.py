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
) -> dict | None:
    """
    Get agent for a specific role and priority level.

    Args:
        role: The role to select for (coding, reviewing, etc.)
        priority: Priority level (1-5)
        require_vision: If True, only return agents with vision capability
        min_elo: Optional minimum ELO score requirement

    Returns:
        Agent dict with api_id, name, provider, etc. or None if not found.
    """
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
    params: list = [role, priority]

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
        agent = get_agent(role, priority, require_vision, min_elo)
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
    List all assigned agents for a role, ordered by priority.

    Returns:
        List of agent dicts with priority info.
    """
    conn = get_connection()
    cursor = conn.execute(
        """
        SELECT
            a.id,
            a.api_id,
            a.name,
            a.provider,
            a.arena_elo,
            a.tbench_accuracy,
            a.has_vision,
            a.perf_per_dollar,
            r.priority,
            r.min_elo
        FROM agent_roles r
        JOIN agents a ON a.id = r.agent_id
        WHERE r.role = ?
          AND a.status = 'active'
          AND a.blocked = 0
        ORDER BY r.priority
        """,
        (role,),
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
