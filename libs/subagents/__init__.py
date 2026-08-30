# ══════════════════════════════════════════════════════════════════════════════════
# ⚠️  DEV-TIME ONLY — importing this from a project's src/ or tests/ breaks CI and the
# deployed container. It is gitignored fleet-wide (Fabrik-synced VENDORED_DIRS). Vendor
# what you need into tracked source; never import it from shipped code.
#
# Runtime web research is the one piece products legitimately want — vendor the
# standalone `fabrik-lib/web-tools/` module instead; it drags none of this pool behind it.
# ══════════════════════════════════════════════════════════════════════════════════
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

from ._dotenv import env_status, load_env
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
    agent_ids_present,
    flush_outbox,
    record_agent_run,
    record_run,
    set_quality,
    unscored_agent_ids,
)
from .providers import (
    ProviderConfig,
    UnknownProviderError,
    known_providers,
    resolve_provider,
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
        # The FULL curated set (key + SUBAGENT_RUNS_DSN + web-tool keys). Key-only wasn't enough: a
        # standalone record_agent_run/set_quality (no run_agents call) then had no DSN and silently
        # buffered to the outbox instead of recording live. Tests are unaffected — conftest sets
        # SUBAGENTS_NO_AUTOLOAD=1 before any test imports this module.
        load_env(_os.getcwd())
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
    # ⚠️ THE FIX THAT STOPPED ONE LAYER SHORT. These two were added to `pg_ledger.__all__` with a
    # comment saying "a public-looking name that is not exported is a trap for the consumer who needs
    # it most" — and then not exported HERE, which is the import path the README actually prints. The
    # README snippet raised ImportError against the shipped package. Same defect, one module up.
    "agent_ids_present",
    "unscored_agent_ids",
    "audit_unrecorded",
    "load_env",
    "env_status",
    "SUBAGENT_RUNS_DDL",
    "SAFE_RESEARCH_SERVERS",
    "resolve_provider",
    "known_providers",
    "ProviderConfig",
    "UnknownProviderError",
]
