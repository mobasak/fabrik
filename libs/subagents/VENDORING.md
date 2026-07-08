# Vendoring `subagents` into a project (e.g. `trade-intelligence`)

`subagents` is a **fabrik-lib module**: you **copy it into your project and own it** — no pip
package, no shared runtime dependency, no `/opt/` import at build time. It is **self-contained**
(the only runtime dep is `httpx`; the OpenRouter transport is vendored inside it as
`_client.py`/`_transport.py`), so a copy just works.

> **Who runs this:** the **consuming project** (e.g. `trade-intelligence`), not fabrik-lib.
> fabrik-lib authors the module; it never writes into your tree.

---

## 1. Copy the module — FLAT (copy the package, not the module dir)

**Copy the inner `subagents/` PACKAGE straight to `libs/subagents/`** so `libs/subagents/__init__.py`
lands directly under `libs/` — this is what makes the documented `from libs.subagents import …`
resolve. Do **NOT** copy the outer `subagents/` module dir (that nests it as
`libs/subagents/subagents/` and only `from libs.subagents.subagents import …` would work — the
import shape this module does **not** document, and the one that silently breaks every consumer +
the `/fabrik-*` flywheel snippets).

```bash
# from the consuming project root — libs/subagents/ must NOT already exist (cp would nest into it)
cp -r /opt/fabrik-lib/subagents/subagents your-project/libs/subagents        # the PACKAGE, flat
cp /opt/fabrik-lib/subagents/requirements.txt your-project/libs/subagents/   # httpx==0.28.1
pip install -r your-project/libs/subagents/requirements.txt
# (optional) the tests, if you want to run them in-project:
# cp -r /opt/fabrik-lib/subagents/tests your-project/libs/subagents/tests
```

Layout after copying (FLAT — the canonical shape):
`libs/subagents/__init__.py`, `libs/subagents/agent.py`, `libs/subagents/select.py`, … — the
package contents live **directly** under `libs/subagents/`.

## 2. No import rewrite needed — the package is relative-import throughout

The package imports its own internals **relatively** (`from .agent import …`, `from .select import
…`, `from . import sandbox`) — it never hard-codes its own top-level name. So once it sits at
`libs/subagents/` with the project root on `sys.path` (the default when you run from the project
root), **`from libs.subagents import …` just works — no rewriting, no `PYTHONPATH` hack.** (Inside
fabrik-lib the same package is imported as `subagents`; vendored flat it is `libs.subagents`. Same
code, different top-level name — that is exactly what relative imports buy you.)

**Verify the copy imports (all four — the flywheel write is `record_agent_run`, NOT `record_run`):**
```bash
python -c "from libs.subagents import run_agents, AgentSpec, pick_models, record_agent_run; print('ok')"
```

## 3. Prerequisites — only what your features need

| You want… | Install / set |
|---|---|
| **Single-shot research pool** (`tools_enabled=False`) | `OPENROUTER_API_KEY` + system `git` — nothing else |
| **Tool-enabled agents** (the model runs `run_command`) | **bubblewrap** (`apt install bubblewrap`) — `run_command` is sandboxed and **fails closed** without it |
| **Web research tools** (`web_tools=`) | the matching key(s): `EXA_API_KEY` / `BRAVE_API_KEY` / `FIRECRAWL_API_KEY` / `CONTEXT7_API_KEY` |
| **MCP research tools** (`mcp_servers=`) | Node/`npx` on the host + `pip install mcp` (optional, lazy-imported); point `mcp_config` at your `mcp.json` |
| **Centralized run-metrics flywheel** | Postgres access + `pip install psycopg`; set `SUBAGENT_RUNS_DSN` (+ `SUBAGENT_PROJECT`) |

**For a trade-intelligence / research use case** you almost certainly want the **top row only** —
research pools and web/MCP tools need **no** bubblewrap and no git worktree machinery.

## 4. Minimal usage — a research-tuned starter

```python
from libs.subagents import run_agents, AgentSpec, pick_models, methodology

# a 3-model fan-out that RESEARCHES (no code tools, no sandbox needed):
models = pick_models("research", n=3)                 # cheapest-that-ranks per our benchmark
specs = [
    AgentSpec(
        task="Summarize today's crude-oil market-moving headlines with sources.",
        model=m,
        system=methodology("research"),
        tools_enabled=False,                          # single-shot text, no worktree/sandbox
        web_tools=frozenset({"web_search", "docs_lookup"}),   # opt-in, needs the keys
        max_turns=6, max_cost_usd=0.20, wall_clock_s=300,
    )
    for m in models
]
results = run_agents(specs, repo="/path/to/your/project")
for r in results:
    print(r.agent_id, r.status, r.cost_usd)
    print(r.text)      # each model's answer — YOU judge/merge; nothing is auto-applied
```

`run_agents` is synchronous; `arun_agents(...)` is the async core. See `README.md` for the full
API (`AgentSpec` fields, caps, `web_tools`/`mcp_servers`, `pick_models`, the flywheel `record_agent_run`)
and `PROPOSED_RULE-using-subagents.md` for the safety guardrails (keep the sandbox on for
tool-enabled pools, never route auth/secrets/migrations to the pool, bound every agent).

## 5. Keeping the copy current

You **own** the copy — divergence is fine. To pull upstream improvements later, re-copy the package
(`/opt/fabrik-lib/subagents/subagents/` → `libs/subagents/`, the same **flat** shape as §1) and
re-apply your local changes. If you fix a real bug in the vendored copy, report it upstream in
`/opt/fabrik-lib/subagents/UPSTREAM_FEEDBACK.md` so every project benefits (that is the one write
allowed back into fabrik-lib).
