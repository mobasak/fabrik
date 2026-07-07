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

**Composing the subagent's brief/system prompt:** follow `docs/reference/MD/ai-prompt-templates.md` — a distilled system prompt (Part A) that enforces the agentic patterns (Part B: termination contract, evidence-before-assertion, path:line grounding, untrusted-input). Distil, don't dump the whole rulebook into the brief.

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

## Approved pool models — the ≤ $1.5/Mtok output rule (BINDING)

The pool is defined by a **rule, not a frozen list: OpenRouter output price ≤ $1.5/Mtok.** Current members (every model that clears it) are the 5 benchmarked below — a future cheaper model **joins automatically** once it clears a benchmark, and anything over $1.5 is **never auto-selected** (glm-5/5.x ~$3+, kimi $2–3.5, grok $2.5, qwen $3.75 — priced only for explicit opt-in benchmarks). **No `anthropic/*` via the pool** — Claude is subscription-native, so use the `fabrik-reviewer` Claude Code subagent, not the pool. A model over $1.5 or off-list without the operator's explicit per-turn OK → **STOP, ask.**

| Model | OpenRouter ID | $/Mtok in→out | avg quality (fleet test) |
|---|---|---|---|
| deepseek-v4-flash | `deepseek/deepseek-v4-flash` | 0.09 → 0.18 | 3.25 (**best at code, 4.80**) |
| minimax-m2.5 | `minimax/minimax-m2.5` | 0.12 → 0.48 | 3.80 |
| deepseek-v3.2 | `deepseek/deepseek-v3.2` | 0.23 → 0.34 | 4.00 |
| deepseek-v4-pro | `deepseek/deepseek-v4-pro` | 0.44 → 0.87 | 4.15 |
| minimax-m3 | `minimax/minimax-m3` | 0.30 → 1.20 | **4.65 (best overall / best reviewer)** |

**Two tiers — the benchmark keeps ALL models; it only *separates* which are auto-selectable:**

| Tier | Members | Selection |
|---|---|---|
| **Auto** (output ≤ $1.5/Mtok) | the 5 above | `pick_models` picks freely — **no approval** |
| **On-request** (output > $1.5) | `glm-5/5.x` · `kimi` · `grok` · `qwen` (+ any future pricier) — still benchmarked + priced, just **never auto** | **only when the operator names/approves it this turn**; say why the cheap pool didn't suffice for this specific hard task |

**Per-stage ranking (module benchmark, best-first — `pick_models("<task_type>")` returns exactly this order; take the cheapest that clears your bar):**

| Stage | Ranking (best → cheapest-viable) |
|---|---|
| plan | `minimax-m3` → `v4-pro` → `v3.2` → `v4-flash` → `m2.5` |
| review | `minimax-m3` → `v3.2` → `v4-pro` → `m2.5` → `v4-flash` |
| code | `v4-flash` → `minimax-m3` → `v4-pro` → `v3.2` → `m2.5` |
| spec | `m2.5` → `v3.2` → (`m3` / `v4-pro` / `v4-flash` by overall) |
| docs / research | `minimax-m3` → `v4-pro` → `v3.2` → `m2.5` → `v4-flash` (no A/B yet — by overall) |

- Pick with `pick_models("<task_type>", max_cost_per_mtok=1.2, …)` — the module's **vendored default pool is now exactly these 5**; a model outside it → **STOP, ask the operator** (don't invent versions — verify the OR ID exists).
- Defaults (top of each ranking): **review/plan/docs/research** → `minimax/minimax-m3`; **code** → `deepseek/deepseek-v4-flash`; **spec** → `minimax/minimax-m2.5`.
- **Close the flywheel loop (every pool dispatch):** select via **`pick_models(task_type, …)`** (enforces the pool + the flywheel ranking) → judge the run → **`record_run(result, quality_score, project=<name>)`**. Fleet runs → `subagent_runs` → aggregation → `CODING_SUBAGENT_SELECTION.md` → sharper `pick_models` next time.
- **⚠️ Three sources must agree or the cost policy silently drifts:** the module's vendored `_TABLE` (set to the ≤$1.5 pool), the flywheel-refreshed **`CODING_SUBAGENT_SELECTION.md`** (which **overrides** the vendored default via `SUBAGENT_SELECTION_DOC`), and **this pack**. The **flywheel→doc aggregation MUST filter to output ≤ $1.5/Mtok** — else a refreshed doc re-admits glm/kimi/grok/qwen and undoes the policy. This pack states the rule; keep the doc aligned to it.

## Dispatch policy — parallel by default + a mixed cheap worker set (BINDING)

**Every command task that decomposes is fanned out to subagents in parallel wherever suitable** (independent work, disjoint `owned_paths` — the finder / grounder / reconciler / implementer classes are the common case). Encourage parallelism in **every** command; do decomposable work via subagents, not inline. Serialize only on a true data dependency or a shared file.

**Standard worker mix per fan-out — diversity for cents:**
- **1–2+ Claude Code subagents** — the native `fabrik-*` type for the task (subscription-billed), scaled to size/risk: more (or **Opus**) for auth / schema / migrations / concurrency; **Sonnet/Haiku** for routine breadth.
- **+ `minimax/minimax-m3`** via the pool (`run_agents`, the right `task_type`) — the proven cheap OpenRouter worker; adds an **independent, differently-biased** pass **and** feeds the flywheel, for cents. *(Gated on `libs/subagents/` being vendored; until then, Claude subagents only.)*
- **+ optionally one more allowlisted cheap model** (`deepseek/deepseek-v4-flash` = best value, or another from § Approved pool models) **when the task warrants more breadth**.

**Always cost-conservative:** stay within § Approved pool models; never add an expensive/unlisted model without the operator's explicit per-turn approval. The **orchestrator (you) always adjudicates** — cheap pool workers *surface* candidates; you refute / merge / decide and own the verdict. `record_run` every pool worker so `pick_models` keeps improving.

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
