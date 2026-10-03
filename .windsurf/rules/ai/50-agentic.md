---
activation: glob
globs: ["**/agentic/**", "**/reasoning/**", "**/orchestrator/**", "**/orchestration/**", "**/multi-agent/**", "**/agent-loop/**"]
description: Agentic / Reasoning AI (category 5) — multi-step reasoning and tool use. Agent loops run on Claude through claude -p and fabrik-lib's llm-dispatch (run_agentic, sessions, max_turns, a fixed tool set) on the subscription, never ANTHROPIC_API_KEY; a framework only on a recorded need. Automation, planning, research.
trigger: glob
currency_pass: 2026-10-02
---
<!-- CONSUMER: Coding agents building agentic or reasoning systems (tool-using loops, planners, research agents)
     GOAL: Run agent loops on Claude through llm-dispatch with a bounded turn count and a fixed tool set; honor the
     subscription auth boundary.
     AGENT USAGE: Prefer a workflow on a fixed code path; an agent loop only where the steps cannot be predicted. Model
     choice across categories is ai/00-ai-model-selection.md; record a project's choice and the rejected alternative in
     project.yaml (`ai_category`, `ai_subcategory`, `ai_tools`), as ai/00's selection workflow says. -->

# 5. Agentic / Reasoning AI

Last content verification: 2026-10-02

**Purpose:** Multi-step reasoning or tool use.

## Fabrik defaults

- **Workflow before agent.** Anthropic's "Building effective agents" draws the line this pack follows: a workflow runs
  model calls on a fixed code path (prompt chaining, routing, parallel calls, orchestrator-workers,
  evaluator-optimizer); an agent directs its own steps and tool use. Write the workflow whenever the steps can be
  named in advance, and give a model the loop only where they cannot.
- **Agent loops → Claude through `claude -p`**, by alias, on the Max subscription (ai/00-ai-model-selection.md
  § Claude subscription first), through fabrik-lib's `llm-dispatch`: `run_agentic` for one tool-using run,
  `start_session` and `continue_session` for a multi-turn agent, `json_schema` for the final answer. Agent loops run
  on `opus`, and on `fable` when `opus` measurably falls short (ai/00); ai/00's haiku-first ladder is for single calls,
  such as one tool-free step inside a loop. No agent framework by default: nothing in the fleet imports one, and
  `llm-dispatch` is the loop.
- **Bound every loop.** Set `max_turns` on every agentic call: unset, the CLI runs without a limit, and when the limit is
  hit the call exits with an error. Size `timeout_s` to the turn count: the lane default is 300 s, and a timed-out run
  is killed mid-turn with its cost unknown. Give the run a fixed tool set with `tools`, which leaves MCP tools
  untouched, so deny those with `disallowed_tools` (`mcp__*` removes them all), and keep `permission_mode` at
  `dontAsk`, the module's default; `bypassPermissions` needs the module's explicit opt-in. `dontAsk` denies any call
  that would prompt, so grant the tools that edit or run commands with `allowed_tools` (`Edit`, a `Bash` rule scoped to
  a command prefix): `tools` only restricts what exists. Keep the module's default
  `setting_sources=""`, which keeps the project's settings, hooks and `.mcp.json` out of the run (the bare CLI loads
  them even in an untrusted folder), and load MCP servers through `mcp_configs` with `strict_mcp_config`. The agentic
  and session helpers raise `DispatchError` with no metered fallback, so catch it; a `max_turns` exit is one, and it is
  billed. A multi-turn agent resumes only a persisted session; a resumed result carries the session total, so read the
  last result rather than summing results — `budget_record` already receives each turn's delta.
- **Typed gates inside a loop.** A decision the harness makes between model calls with a fixed answer — is this tool
  call risky, is the run still on task, which skill or tool does this request need — is a closed-answer decision, and
  ai/00's decision-model lane may take it when its six conditions hold. Such a gate only tightens what the loop allows:
  `allowed_tools`, `disallowed_tools` and `dontAsk` stay the permission boundary, and a model's verdict on a tool call
  is never the only thing between the agent and an irreversible act.
- **Reasoning depth is effort, not a thinking budget.** On the `sonnet`, `opus` and `fable` rungs thinking is adaptive,
  a thinking token budget is rejected, and effort steers how much the model reasons and acts. The `haiku` rung is the
  reverse: extended thinking with a budget is its only mode and effort does not apply, so a haiku step has no reasoning
  knob on the CLI lane. Set effort with `effort=` on the call, or `CLAUDE_CLI_EFFORT` for the process (empty means each
  model's designed effort, ai/00), deliberately and before judging that a rung fell short, and keep one level across a
  session's turns: changing it between requests drops the prompt cache.
- **Auth boundary.** Agents run on the subscription's OAuth through the unmodified CLI, never `ANTHROPIC_API_KEY`
  (ai/00). Never pass `bare=True` on that lane: bare mode never reads OAuth credentials and fails with "Not logged in".
  A deployed service declares `shape.uses_claude_cli` and mounts the rotated `~/.claude`, never a static token.
  Anthropic's terms say subscription OAuth is for ordinary, individual use of Claude Code and its own apps; developers
  building products or services, including with the Agent SDK, should use an API key, and Anthropic does not permit
  routing requests through Free, Pro or Max credentials on behalf of their users, reserving the right to enforce that
  without notice. The operator's own development and automation through the unmodified CLI is the closest fit to that
  ordinary use; how far it stretches is part of W-ee2156db. Until the operator
  rules on W-ee2156db, a new `claude -p` call that answers another user's request is the operator's decision before it
  is built, never a default. `claude -p` draws from the plan's usage limits today; a planned move to a separate monthly
  credit was paused on 2026-06-15.
- **Parallel fan-out** (graders, finders, reconcilers) runs as native subagents per core/62-using-subagents.md.

**Anti-pattern:** putting per-call dollar caps on the operational diagnose loop. It must run, and Claude Code is
subscription-billed: the daily caps are its ceiling and `max_turns` bounds a call (core/cost-budget.md). A product's
agent loop may carry `max_budget_usd` as a second ceiling beside cost-budget's caps.

**Licence trap — AutoGPT is a platform now, not a library.** Its `autogpt_platform` folder is under the Polyform Shield
License, which is source-available, not open source; only the rest of the repo is MIT. Read the licence of the part you
would vendor.

## Subcategories

- **Agent frameworks** (only on a recorded need: graph state, durable runs, a non-Claude model in the loop): LangGraph
  (MIT; LangChain's agents run on it), Pydantic AI (MIT), CrewAI (MIT), Microsoft's Agent Framework (MIT, stable; the
  successor to AutoGen, which is in maintenance mode, and to Semantic Kernel), OpenAI's Agents SDK (MIT, still before
  its first major release). The Claude Agent SDK is Claude Code's loop as a Python or TypeScript library; its docs
  authenticate by API key, so the fleet uses its CLI form through `llm-dispatch`.
- **Research:** fabrik-lib's `deep-research`, a fixed five-stage workflow (plan, search, shortlist, verify, deliver,
  driven by a pack) — the workflow-first case, not an agent loop.
  `ai-consult`, the metered frontier fan-out, is off while the subagent pool is paused.
- **Tools for agents:** the Model Context Protocol, now governed by the Agentic AI Foundation under the Linux
  Foundation.
- **Design reading:** Anthropic's engineering posts on building effective agents, context engineering, writing tools
  for agents, its multi-agent research system, and evals for agents.
- **Compare on:** Terminal-Bench for agentic coding, τ-bench for tool-using conversational agents, GAIA for general
  assistants. The Berkeley Function Calling Leaderboard has not been updated since 2026-04-12, so it misses the current
  frontier.

## Gateway coverage

A non-Claude reasoning model goes through OpenRouter: filter for tool calling with `supported_parameters=tools`, and set
reasoning depth with its `reasoning` parameter (an effort level or a token cap, not both). Reasoning tokens bill as
output, and some models never return them. Pick the rate per model from the bake-off browser (hub-only), using its
tools chip.

<!-- GATEWAY_COUNTS:START — last-refreshed: 2026-09-07 (auto-managed by update_gateway_counts.py) -->
*Live gateway counts (active models, 2026-09-07 UTC; auto-refreshed from `kilo_agents.db`):*

reasoning-capable across all gateways: **254**
tool/function-calling across all gateways: **348**

All major frontier reasoning models (o3, Claude reasoning, Gemini 3.x thinking, GLM-5.2) are on both Kilo and OpenRouter — pick the cheaper rate per model.
<!-- GATEWAY_COUNTS:END -->

**Use cases:** automation, code execution, planning, research.

<!-- OPENROUTER_ROUTES:START — last-refreshed: 2026-09-07 (auto-managed by category_export_markdown.py) -->
*Auto-generated 2026-09-07 (UTC) by `category_route_mapper.py` → injected here by `category_export_markdown.py`. Edits between the markers will be overwritten on the next daily run.*

*No eligible models today — floors too strict or catalog too thin. See `cache/update.log` for details. Reason: No model satisfies category='agentic' floors: min_quality_tier=1, min_context_window_k=1, require_vision=False, require_tools=True, require_reasoning=True, allow_free=False, stability_required=True, sort_key='tbench_accuracy DESC'*
<!-- OPENROUTER_ROUTES:END -->
