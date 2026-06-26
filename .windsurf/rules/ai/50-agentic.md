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

**Purpose:** Multi-step reasoning or tool use.

## Fabrik default
- **Claude** for reasoning + tool use. **Operational** agents (sysadmin, watchdog, bootstrap) run via **Claude Code CLI w/ subscription OAuth** — never `ANTHROPIC_API_KEY`.

## Examples
OpenAI o3/o4-mini, Claude (Projects / agent loops), LangChain Agents, AutoGPT.

## Kilo coverage
✅ 88 models with `reasoning`, 148 with `toolcall`. Free reasoning: `giga-potato-thinking`. Paid: `nvidia/nemotron-nano-9b` ($0.04/1M). For function-calling agents, filter on the `toolcall` flag.

**Use cases:** automation, code execution, planning, research.

**Anti-pattern:** putting per-call $ caps on the operational diagnose loop — it must run (Claude Code is subscription-billed). See `core/cost-budget.md`.
