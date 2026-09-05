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

Last content verification: 2026-09-05

**Purpose:** Multi-step reasoning or tool use.

## Fabrik default
- **Claude** for reasoning + tool use. **Operational** agents (sysadmin, watchdog, bootstrap) run via **Claude Code CLI w/ subscription OAuth** — never `ANTHROPIC_API_KEY`.

## Examples
OpenAI o3/o4-mini, Claude (Projects / agent loops), LangChain Agents, AutoGPT.

## Gateway coverage

The major frontier (o3, Claude reasoning, Gemini 3.x Pro thinking, GLM-5.2) is on both Kilo and OpenRouter at frequently different per-token costs. For function-calling agents, filter on the `toolcall` flag (Kilo) or the `tools` chip (bake-off browser). Pick the cheaper gateway per model.

<!-- GATEWAY_COUNTS:START — last-refreshed: 2026-09-05 (auto-managed by update_gateway_counts.py) -->
*Live gateway counts (active models, 2026-09-05 UTC; auto-refreshed from `kilo_agents.db`):*

reasoning-capable across all gateways: **254**
tool/function-calling across all gateways: **346**

All major frontier reasoning models (o3, Claude reasoning, Gemini 3.x thinking, GLM-5.2) are on both Kilo and OpenRouter — pick the cheaper rate per model.
<!-- GATEWAY_COUNTS:END -->

**Use cases:** automation, code execution, planning, research.

**Anti-pattern:** putting per-call $ caps on the operational diagnose loop — it must run (Claude Code is subscription-billed). See `core/cost-budget.md`.

<!-- OPENROUTER_ROUTES:START — last-refreshed: 2026-09-05 (auto-managed by category_export_markdown.py) -->
*Auto-generated 2026-09-05 (UTC) by `category_route_mapper.py` → injected here by `category_export_markdown.py`. Edits between the markers will be overwritten on the next daily run.*

*No eligible models today — floors too strict or catalog too thin. See `cache/update.log` for details. Reason: No model satisfies category='agentic' floors: min_quality_tier=1, min_context_window_k=1, require_vision=False, require_tools=True, require_reasoning=True, allow_free=False, stability_required=True, sort_key='tbench_accuracy DESC'*
<!-- OPENROUTER_ROUTES:END -->
