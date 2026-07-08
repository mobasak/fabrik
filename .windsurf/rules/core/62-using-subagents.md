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

The pool is a **rule, not a roster: OpenRouter output price ≤ $1.5/Mtok** (turn-count beats token-price — the cheapest model often takes 2–3× the turns and costs more overall). **Name no model rosters or per-stage rankings in this pack** — they are the flywheel's *output* and live in ONE place: the module's `_TABLE` + the synced **`CODING_SUBAGENT_SELECTION.md`** (which overrides `_TABLE` via `SUBAGENT_SELECTION_DOC` once it has enough runs). Copying them here is the 3-way drift this pack exists to avoid.

**Select with `pick_models(task_type, max_cost_per_mtok=1.2, …)` — never hand-pick.** It returns the flywheel-ranked pool best-first; take the cheapest that clears your bar. What enforces the cap today: the **ranking** `pick_models` draws from (`_TABLE` / the synced doc) lists only the ≤$1.5 pool, so a bare `pick_models` returns only those; AND `max_cost_per_mtok` is a **fail-closed ceiling** (`select.py:312-318`) that drops any over-ceiling *or* unpriced model a synced-doc override could surface. Note the module's *price* table (`_OUT_PRICE`) deliberately prices the On-request models too (for benchmarking + offline determinism) — so it is the **ranking + the ceiling**, not the price table, that gate them out. That's why you **always pass the ceiling** (`=1.2`, or `=1.5` for the fleet cap): it holds regardless of module version or what the synced doc contains. **The one named default is `minimax/minimax-m3`** (best overall / best reviewer — review/plan/docs/research); for code, take the cheapest of what `pick_models("code")` returns (`prefer="value"`). **No `anthropic/*` via the pool** — Claude is subscription-native; use the `fabrik-reviewer` Claude Code subagent, not the pool. Don't invent OR IDs — verify the ID exists.

**Two tiers (a rule, not a member list) — the benchmark keeps ALL models; it only *separates* which are auto-selectable:**

| Tier | Rule | Selection |
|---|---|---|
| **Auto** | output ≤ $1.5/Mtok | `pick_models` returns it freely — **no approval** |
| **On-request** | output > $1.5 (glm / kimi / grok / qwen etc. — still benchmarked + priced, never auto) | **only when the operator names/approves it THIS turn**; opt in explicitly (the module's `allow_above_cap=True` once re-vendored — until then name the model directly) and justify at the call site like `sandbox=False`; say why the cheap pool didn't suffice |

A model over $1.5, or any off-Auto model without the operator's explicit per-turn OK → **STOP, ask.**

- **Close the flywheel loop (every pool dispatch):** `pick_models(task_type, max_cost_per_mtok=1.2)` → judge the run → `record_run(result, quality_score, project=<name>)`. Fleet runs → `subagent_runs` → aggregation (**filtered to ≤ $1.5/Mtok**, so a refresh never re-admits a pricier model) → `CODING_SUBAGENT_SELECTION.md` → sharper `pick_models` next time.
- **⚠️ Keep the TWO sources aligned:** the module's vendored `_TABLE` and the flywheel-refreshed `CODING_SUBAGENT_SELECTION.md` (which overrides it via `SUBAGENT_SELECTION_DOC`). **This pack lists NO models — only the rule — so it can never be the third source that drifts.**

## Dispatch policy — parallel by default + a mixed cheap worker set (BINDING)

**Every command task that decomposes is fanned out to subagents in parallel wherever suitable** (independent work, disjoint `owned_paths` — the finder / grounder / reconciler / implementer classes are the common case). Encourage parallelism in **every** command; do decomposable work via subagents, not inline. Serialize only on a true data dependency or a shared file.

**Standard worker mix per fan-out — diversity for cents:**
- **1–2+ Claude Code subagents** — the native `fabrik-*` type for the task (subscription-billed), scaled to size/risk: more (or **Opus**) for auth / schema / migrations / concurrency; **Sonnet/Haiku** for routine breadth.
- **+ `minimax/minimax-m3`** via the pool (`run_agents`, the right `task_type`) — the proven cheap OpenRouter worker; adds an **independent, differently-biased** pass **and** feeds the flywheel, for cents. *(Gated on `libs/subagents/` being vendored; until then, Claude subagents only.)*
- **+ optionally one more Auto-tier cheap model** (the next model `pick_models` returns for the task) **when the task warrants more breadth**.

**Always cost-conservative:** stay within § Approved pool models; never add an expensive/unlisted model without the operator's explicit per-turn approval. The **orchestrator (you) always adjudicates** — cheap pool workers *surface* candidates; you refute / merge / decide and own the verdict. `record_run` every pool worker so `pick_models` keeps improving.

## NEVER route to the pool (fabrik-lib PROPOSED_RULE)

Auth/identity/session/crypto · schema/migrations · secrets/`.env`/keys · security controls (RLS, rate-limits, `final_gate`) · deploy/infra. These stay with the primary (human-supervised) agent. **Never web/MCP-enable a task carrying sensitive context** — the model's output exfiltrates via a scraped URL. Keep the bwrap sandbox on (`sandbox=True`, fail-closed).

## The mcp.json source-of-truth

The canonical MCP server list is a hub-owned standard-format file — `/opt/fabrik/mcp.json` (`{"mcpServers": {name: {type, command, args, env}}}`, keys via `${ENV}` expansion, never inline). The pool's MCP client reads it via `AgentSpec.mcp_config` (path → unwrap the `mcpServers` key; dict → the bare server map). Adding a tool touches exactly: `claude mcp add` (main agent) → `mcpServers` in the relevant Runtime-A agent type → this `mcp.json` (pool) — never a command brief.

## Report every pool run — the results table AND the flywheel (both, always)

After any **pool** dispatch (`run_agents`) you EVALUATE, emit **BOTH** — sharing **one** quality verdict (judge once, put the same 0–5 in both). A run that showed a table but no `record_run` (or recorded but showed no table) is **half-done**:

1. **A results table** (one row per unit) so a human can compare models at a glance — use the helper `results_table([{ "unit":…, "model":…, "result":<AgentResult>, "quality":0-5, "fixes":… }, …])`. Provider / Cost / Latency / **Out** (`out_tokens`) come straight from the `AgentResult`; **quality + confirmed-fixes are YOUR verdict** after materializing the diff and running the gate/tests/review.
2. **A flywheel row per unit** — `record_run(result, quality_score=<the same 0-5>, project=<name>)`. This is the fleet-wide `subagent_runs` the ranking `pick_models` uses is refined from; skipping it means the ranking never improves. On the VPS `SUBAGENT_RUNS_DSN` connects directly; on WSL dev pass a peer-auth `connect=` factory.

Claude-Code-subagent (Runtime A) dispatches you evaluate: still `record_run` per evaluated run; `results_table` applies to the pool (Runtime B), which supplies the `AgentResult`. Inline / no-dispatch → nothing to record. See each command's "Flywheel" section + `docs/superpowers/specs/2026-07-06-subagent-runs-telemetry-design.md`.

## Vendored-module bug → UPSTREAM_FEEDBACK (binding)

When a project fixes a real bug in a **vendored `fabrik-lib` module** (e.g. `libs/subagents/`), it MUST append the fix — symptom + fix + date — to `/opt/fabrik-lib/<module>/UPSTREAM_FEEDBACK.md`. That file is the **one write allowed back into `/opt/fabrik-lib`** (cross-repo HARD STOP otherwise); the module author reads + resolves it, so the fix isn't silently lost on the next re-vendor. Fixing a vendored module without the entry breaks the loop.

## Banned

- A command brief that restates tool lists instead of naming a `subagent_type` / pointing here.
- A GUI/browser task routed to the pool (no equivalent — Runtime A/primary only).
- A pool task with `sandbox=False`, an inline API key, or web/MCP enabled while it carries sensitive context.
- Hard-coding the `mcp` SDK v2 API or the Tool schema attribute name.
- Naming a model roster or per-stage ranking in this pack (they live in the module `_TABLE` + `CODING_SUBAGENT_SELECTION.md`) — only `minimax/minimax-m3` (the default) may appear by name.
- A pool run that emitted a `record_run` but no `results_table` (or vice-versa) — both, one verdict.
- Fixing a bug in a vendored `fabrik-lib` module without an `UPSTREAM_FEEDBACK.md` entry.
