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

Last content verification: 2026-06-27

**Purpose:** Multi-step reasoning or tool use.

## Fabrik default
- **Claude** for reasoning + tool use. **Operational** agents (sysadmin, watchdog, bootstrap) run via **Claude Code CLI w/ subscription OAuth** — never `ANTHROPIC_API_KEY`.

## Examples
OpenAI o3/o4-mini, Claude (Projects / agent loops), LangChain Agents, AutoGPT.

## Kilo coverage
✅ 88 models with `reasoning`, 148 with `toolcall`. Free reasoning: `giga-potato-thinking`. Paid: `nvidia/nemotron-nano-9b` ($0.04/1M). For function-calling agents, filter on the `toolcall` flag.

**Use cases:** automation, code execution, planning, research.

**Anti-pattern:** putting per-call $ caps on the operational diagnose loop — it must run (Claude Code is subscription-billed). See `core/cost-budget.md`.

<!-- OPENROUTER_ROUTES:START — last-refreshed: 2026-06-27 (auto-managed by category_export_markdown.py) -->
*Auto-generated 2026-06-27 (UTC) by `category_route_mapper.py` → injected here by `category_export_markdown.py`. Edits between the markers will be overwritten on the next daily run.*

| Priority | OpenRouter ID | Cost ($/M in) | Context | Status |
|---|---|---|---|---|
| P1 | `openai/gpt-5.4` | $2.50 | 1050k | GA |
| P2 | `openai/gpt-5.3-codex` | $1.75 | 400k | GA |
| P3 | `anthropic/claude-opus-4.6` | $5.00 | 1000k | GA |

To consume via a Fabrik spec: `llm_provider: openrouter` + `llm_model: <P1 id>`. Fallback chain via the OpenRouter `models: [P1, P2, P3]` request parameter.
<!-- OPENROUTER_ROUTES:END -->
