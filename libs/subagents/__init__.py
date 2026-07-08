"""subagents — vendorable parallel-subagent runtime (OpenRouter-direct).

Recruit and run N subagents in parallel via the OpenRouter API for coding /
research / docs / review tasks. Layered containment: an OS sandbox (bubblewrap)
write-confines `run_command` to the worktree (fail-closed), under
worktree-per-agent + diff-not-applied + owned_paths scope-check + caps + a
durable provenance ledger.

    from subagents import run_agents, AgentSpec

    results = run_agents(
        [AgentSpec(task="add a test for X", model="anthropic/claude-sonnet-5",
                   owned_paths=["tests/*.py"])],
        repo="/path/to/repo",
    )
"""

from __future__ import annotations

from .agent import AgentResult, AgentSpec, arun_agents, run_agents
from .mcp_tools import SAFE_RESEARCH_SERVERS
from .methodology import METHODOLOGY_KINDS, methodology
from .pg_ledger import SUBAGENT_RUNS_DDL, record_run
from .select import (
    TASK_KINDS,
    TASK_MODEL_TABLE,
    load_task_ranking,
    model_price,
    pick_models,
)

__all__ = [
    "run_agents",
    "arun_agents",
    "AgentSpec",
    "AgentResult",
    "methodology",
    "METHODOLOGY_KINDS",
    "pick_models",
    "TASK_KINDS",
    "TASK_MODEL_TABLE",
    "model_price",
    "load_task_ranking",
    "record_run",
    "SUBAGENT_RUNS_DDL",
    "SAFE_RESEARCH_SERVERS",
]
