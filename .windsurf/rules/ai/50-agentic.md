---
activation: glob
globs: ["**/agentic/**", "**/reasoning/**", "**/orchestrator/**", "**/orchestration/**", "**/multi-agent/**", "**/agent-loop/**"]
description: Agentic / Reasoning AI (category 5) — multi-step reasoning & tool use (OpenAI o3/o4-mini, Claude, LangChain Agents, AutoGPT). Automation, planning, research. Kilo: 88 reasoning + 148 toolcall models.
trigger: glob
---
<!-- CONSUMER: Coding agents building agentic/reasoning systems + Traycer (tech-plan)
     GOAL: Pick a reasoning/tool-use model; Claude is the Fabrik default; honor the operational auth boundary.
     TRAYCER USAGE: Context File for agent/automation/reasoning tickets.
     AGENT USAGE: Default Claude. For tool-calling agents, require the `toolcall` capability. Operational agents use Claude Code OAuth, NOT ANTHROPIC_API_KEY (see core/cost-budget.md + 00-ai-model-selection.md). -->

# 5. Agentic / Reasoning AI

Last content verification: 2026-08-11

**Purpose:** Multi-step reasoning or tool use.

## Fabrik default
- **Claude** for reasoning + tool use. **Operational** agents (sysadmin, watchdog, bootstrap) run via **Claude Code CLI w/ subscription OAuth** — never `ANTHROPIC_API_KEY`.

## Examples
OpenAI o3/o4-mini, Claude (Projects / agent loops), LangChain Agents, AutoGPT.

## Gateway coverage

The major frontier (o3, Claude reasoning, Gemini 3.x Pro thinking, GLM-5.2) is on both Kilo and OpenRouter at frequently different per-token costs. For function-calling agents, filter on the `toolcall` flag (Kilo) or the `tools` chip (bake-off browser). Pick the cheaper gateway per model.

<!-- GATEWAY_COUNTS:START — last-refreshed: 2026-08-11 (auto-managed by update_gateway_counts.py) -->
*Live gateway counts (active models, 2026-08-11 UTC; auto-refreshed from `kilo_agents.db`):*

reasoning-capable across all gateways: **243**
tool/function-calling across all gateways: **311**

All major frontier reasoning models (o3, Claude reasoning, Gemini 3.x thinking, GLM-5.2) are on both Kilo and OpenRouter — pick the cheaper rate per model.
<!-- GATEWAY_COUNTS:END -->

**Use cases:** automation, code execution, planning, research.

**Anti-pattern:** putting per-call $ caps on the operational diagnose loop — it must run (Claude Code is subscription-billed). See `core/cost-budget.md`.

<!-- OPENROUTER_ROUTES:START — last-refreshed: 2026-08-11 (auto-managed by category_export_markdown.py) -->
*Auto-generated 2026-08-11 (UTC) by `category_route_mapper.py` → injected here by `category_export_markdown.py`. Edits between the markers will be overwritten on the next daily run.*

| Priority | OpenRouter ID | Cost ($/M in) | Context | Status |
|---|---|---|---|---|
| P1 | `openai/gpt-5.5` | $5.00 | 1050k | GA |
| P2 | `openai/gpt-5.4` | $2.50 | 1050k | GA |
| P3 | `anthropic/claude-opus-4.7` | $5.00 | 1000k | GA |

To consume via a Fabrik spec: `llm_provider: openrouter` + `llm_model: <P1 id>`. Fallback chain via the OpenRouter `models: [P1, P2, P3]` request parameter.
<!-- OPENROUTER_ROUTES:END -->
