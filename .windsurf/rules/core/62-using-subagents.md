---
activation: glob
globs: ["**/subagents/**", "**/libs/subagents/**", "**/*subagent*", "**/mcp.json", "**/.mcp.json", "**/agents/*.md"]
description: How to dispatch subagents — the two runtimes, per-task tool access (Claude Code agent-types vs pool web_tools/mcp_servers), the never-route safety list, the mcp.json source-of-truth, and the record_run flywheel
trigger: glob
---
<!-- CONSUMER: Coding agents (all) + Traycer (planning)
     GOAL: One place that says which subagent runtime to use, what tools it gets, what NEVER goes to a subagent, and how tool access is a single-source change.
     AGENT USAGE: When a command dispatches subagents, pick the runtime + the tool scope from here. Design authority: docs/superpowers/specs/2026-07-07-subagent-tool-parity-design.md (Claude Code side) + fabrik-lib subagents/PROPOSED_RULE-using-subagents.md + its 2026-07-07-subagents-mcp-client-design.md (pool side). -->

# Using Subagents

Two runtimes dispatch subagents; each scopes tools differently. **Never restate tool lists in a command brief — the access lives in the agent-type file (Runtime A) or the `AgentSpec` (Runtime B).**

## The two runtimes

- **A — Claude Code subagents** (`Agent` tool / `subagent_type`). *Are* Claude; tool access = the agent-type frontmatter (`tools` / `mcpServers` / `disallowedTools`). Used today. Can drive browsers.
- **B — fabrik-lib `subagents` pool** (OpenRouter-API models, sandboxed worktree). Not Claude; tools = the module's `web_tools` (Exa/Firecrawl/Context7/Brave HTTP) + `mcp_servers` (MCP client) + `allowed_commands`. **No browser** — GUI work never routes here.

## Which subagent_type per command (Runtime A)

| Work | subagent_type | Access |
|---|---|---|
| web-research grounders (`/fabrik-spec-review`, `/fabrik-plan-after-chat`, `/fabrik-plan-review`, `/fabrik-data-contract`) | **`fabrik-researcher`** | search + docs MCPs; read-only |
| code/doc/contract review (`/fabrik-review`, `/fabrik-docs-review`, `/fabrik-repo-review`, `/fabrik-rules-review`, `/fabrik-ui-design-review`) | **`fabrik-reviewer`** (or equivalent) | repo-only, no MCP |
| GUI screen build + verify (`/fabrik-execute-plan` GUI phases, Build Verification Loop) | **`fabrik-gui`** / `design-review` | browser MCPs + shell |
| code implementers (`/fabrik-execute-plan`) | general builder | file/edit/Bash + optional `context7`; no search/GUI MCP |

## Pool tool access (Runtime B)

- Enable **`web_tools`** and **`mcp_servers`** *per `task_type`*, off by default (they cost money + reach the internet): `research`/`plan` → `web_search`+`docs_lookup` (+ `web_scrape` to read a page); `code`/`review`/`docs` → none.
- **Safe-server allowlist (fail-safe):** research servers `exa`/`brave-search`/`firecrawl`/`context7` are default-on; **FS/shell/exec MCPs are refused** unless `allow_unlisted=True`; **browser MCPs are opt-in** on a capable host only — never default-on the pool.
- **Keys via the process env** (`EXA/FIRECRAWL/CONTEXT7/BRAVE_API_KEY`) — same model as `web_tools`; the hub provisions them into the pool env (`/opt/fabrik/.env` on WSL, deploy env on VPS). Never inline a key.
- **Pin the `mcp` Python SDK v1** (`ClientSession`/`stdio_client`) — the v2 `mcp.client.Client` line is a pre-release the repo marks "do not use in production." Don't hard-code the Tool schema attribute (`inputSchema` vs `input_schema`) — resolve it at build time against the pinned version.
- `max_turns` (not `max_cost_usd`) bounds MCP/web spend — cap it for tool-enabled pool agents and audit the ledger.

## NEVER route to the pool (fabrik-lib PROPOSED_RULE)

Auth/identity/session/crypto · schema/migrations · secrets/`.env`/keys · security controls (RLS, rate-limits, `final_gate`) · deploy/infra. These stay with the primary (human-supervised) agent. **Never web/MCP-enable a task carrying sensitive context** — the model's output exfiltrates via a scraped URL. Keep the bwrap sandbox on (`sandbox=True`, fail-closed).

## The mcp.json source-of-truth

The canonical MCP server list is a hub-owned standard-format file — `/opt/fabrik/mcp.json` (`{"mcpServers": {name: {type, command, args, env}}}`, keys via `${ENV}` expansion, never inline). The pool's MCP client reads it via `AgentSpec.mcp_config` (path → unwrap the `mcpServers` key; dict → the bare server map). Adding a tool touches exactly: `claude mcp add` (main agent) → `mcpServers` in the relevant Runtime-A agent type → this `mcp.json` (pool) — never a command brief.

## Flywheel

After you EVALUATE any subagent you dispatched (implementer: gate/tests; grounder/reviewer: your merge/refute verdict), call `record_run(result, quality_score=<0–5>, project=<project>)` — one per evaluated run. See each command's "Flywheel" section + `docs/superpowers/specs/2026-07-06-subagent-runs-telemetry-design.md`. Inline/no-dispatch → nothing to record.

## Banned

- A command brief that restates tool lists instead of naming a `subagent_type` / pointing here.
- A GUI/browser task routed to the pool (no equivalent — Runtime A/primary only).
- A pool task with `sandbox=False`, an inline API key, or web/MCP enabled while it carries sensitive context.
- Hard-coding the `mcp` SDK v2 API or the Tool schema attribute name.
