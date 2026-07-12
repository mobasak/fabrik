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

import os as _os

from ._dotenv import load_env
from .agent import (
    AgentResult,
    AgentSpec,
    arun_agents,
    fanout,
    results_table,
    run_agents,
)
from .ledger import audit_unrecorded
from .mcp_tools import SAFE_RESEARCH_SERVERS
from .methodology import METHODOLOGY_KINDS, methodology
from .pg_ledger import (
    SUBAGENT_RUNS_DDL,
    flush_outbox,
    record_agent_run,
    record_run,
    set_quality,
)
from .select import (
    TASK_KINDS,
    TASK_MODEL_TABLE,
    load_task_ranking,
    model_price,
    pick_models,
)

# Autoload the curated keys AT IMPORT so a bare `os.getenv("OPENROUTER_API_KEY")` works everywhere —
# not just inside `run_agents(repo=…)`. A pre-check on the raw process env used to false-negative
# ("no key → pool dead") because the key lives in `<repo>/.env` / the fleet file, not the shell env.
# `import subagents` now surfaces it. Non-overriding (a real env var wins), never raises; opt out with
# `SUBAGENTS_NO_AUTOLOAD=1`.
if _os.getenv("SUBAGENTS_NO_AUTOLOAD") != "1":
    try:
        # Only the KEY — it's the "can I dispatch?" signal a pre-check false-negatives on. The DSN
        # and web-tool keys stay loaded by run_agents(repo=…) at dispatch, so import has no effect on
        # recording/tooling behaviour (and doesn't perturb tests that assume the no-DSN outbox default).
        load_env(_os.getcwd(), keys=("OPENROUTER_API_KEY",))
    except Exception:  # noqa: BLE001 — import must never fail on a best-effort env autoload
        pass

__all__ = [
    "run_agents",
    "arun_agents",
    "fanout",
    "results_table",
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
    "record_agent_run",
    "set_quality",
    "flush_outbox",
    "audit_unrecorded",
    "load_env",
    "SUBAGENT_RUNS_DDL",
    "SAFE_RESEARCH_SERVERS",
]
