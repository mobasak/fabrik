---
activation: glob
globs: ["**/subagents/**", "**/libs/subagents/**", "**/*subagent*", "**/mcp.json", "**/.mcp.json", "**/agents/*.md"]
description: How to dispatch subagents — the two runtimes, per-task tool access (Claude Code agent-types vs pool web_tools/mcp_servers), the never-route safety list, the mcp.json source-of-truth, pool-vs-native, and the record_agent_run flywheel
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

These are the **native** types — used for GUI, the authoritative/high-risk pass, and the decide/refute/merge. Under § Dispatch policy the **gradeable fan-out** of these same commands (review finders, research grounders, doc reconcilers, rules auditors, implementers) **defaults to the POOL** (Runtime B); native here is the authoritative complement, not the default worker.

| Work | subagent_type | Access |
|---|---|---|
| web-research grounders (`/fabrik-spec`, `/fabrik-spec-review`, `/fabrik-plan-after-chat`, `/fabrik-plan-review`, `/fabrik-data-contract`) | **`fabrik-researcher`** | search + docs MCPs; read-only |
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

**Select with `pick_models(task_type, …)` — never hand-pick.** It returns the flywheel-ranked pool best-first; take the cheapest that clears your bar. **`pick_models` is the SOLE ≤$1.5 gatekeeper: an always-on `_MAX_POOL_PRICE_PER_MTOK = 1.5` cap enforced in-code** (`libs/subagents/select.py`), so a >$1.5 model can never reach the default (Auto) pool no matter what the synced doc contains. Three enforcement points agree, ascending trust: the aggregation filter that writes the doc → a caller's optional `max_cost_per_mtok` (pass it only to *tighten below* 1.5) → the module cap (authoritative). So `max_cost_per_mtok` is defense-in-depth, not necessity. **The one named default is `minimax/minimax-m3`** (best overall / best reviewer — review/plan/docs/research); for code, take the cheapest of what `pick_models("code")` returns (`prefer="value"`). **No `anthropic/*` via the pool** — Claude is subscription-native; use the `fabrik-reviewer` Claude Code subagent, not the pool. Don't invent OR IDs — verify the ID exists.

**Two tiers (a rule, not a member list) — the benchmark keeps ALL models; it only *separates* which are auto-selectable:**

| Tier | Rule | Selection |
|---|---|---|
| **Auto** | output ≤ $1.5/Mtok | `pick_models` returns it freely — **no approval** |
| **On-request** | output > $1.5 (glm / kimi / grok / qwen etc. — still benchmarked + priced, never auto) | **only when the operator names/approves it THIS turn**; opt in explicitly with `allow_above_cap=True` (it drops the always-on ≤$1.5 cap for that one call) and justify at the call site like `sandbox=False`; say why the cheap pool didn't suffice |

A model over $1.5, or any off-Auto model without the operator's explicit per-turn OK → **STOP, ask.**

- **Close the flywheel loop (every *pool* dispatch):** `pick_models(task_type)` (the in-code cap self-enforces ≤ $1.5, **inclusive** — don't pass `max_cost_per_mtok` unless you want a *tighter* project budget; the old `=1.2` was wrong, it excluded the legit $1.20–$1.50 band) → judge the run → **`record_agent_run(spec, result, quality_score, project=<name>)`**. ⚠️ `record_run(result, …)` on a raw `AgentResult` **silently no-ops** (it wants a dict; `model`/`task_type` live on the *spec*) — always `record_agent_run(spec, result, …)`. Fleet runs → `subagent_runs` → aggregation (**filtered to ≤ $1.5/Mtok inclusive**) → `CODING_SUBAGENT_SELECTION.md` → sharper `pick_models` next time.
- **⚠️ Keep the TWO sources aligned:** the module's vendored `_TABLE` and the flywheel-refreshed `CODING_SUBAGENT_SELECTION.md` (which overrides it via `SUBAGENT_SELECTION_DOC`). **This pack lists NO models — only the rule — so it can never be the third source that drifts.**

## Dispatch policy — pool-default for gradeable fan-out, native for GUI/authoritative/decide (BINDING)

**Everything decomposable → a subagent; the only question is the runtime.** Every command task that decomposes is fanned out in parallel wherever suitable (independent work, disjoint `owned_paths` — finder / grounder / reconciler / auditor / implementer classes). Do decomposable work via subagents, not inline; serialize only on a true data dependency or a shared file.

**The OpenRouter pool (`run_agents`, ≤ $1.5/Mtok) is the DEFAULT worker for gradeable text/code fan-out** — review finders, repo-review unit reviewers, doc reconcilers, rules-pack auditors, spec/plan research grounders, code implementers. Select with `pick_models(task_type)` (the in-code cap self-enforces ≤$1.5); every pool worker owes `record_agent_run(spec, result)` + `results_table` (§ Report every pool run) — this feeds the flywheel (`pick_models` learns). A single-shot (`tools_enabled=False`) **repo-grounded** worker (`task_type` `review`/`docs`/`plan` — they assert about code they can't see) must set `allow_ungrounded=True` to attest it inlined the content into `task`, or use `tools_enabled=True` for real file reads — the module **refuses** ungrounded single-shot verification (it hallucinates). Enforced (not prose) by `scripts/enforcement/check_subagent_flywheel.py`.

**Native Claude Task subagents (`fabrik-*`, subscription-billed) are for GUI + the authoritative/high-risk pass + the decide/refute/merge.** GUI (`fabrik-gui`, browser MCPs — no pool equivalent); the authoritative line-precise verification (`fabrik-reviewer`/Opus on auth / schema / migrations / secrets / concurrency); and the decide/refute/merge you always own. A native fan-out produces no `AgentResult`, so it **records nothing** to the flywheel (nothing to rank — that is by nature, not a gap).

**Always cost-conservative + you adjudicate:** stay within § Approved pool models; never add an expensive/unlisted model without the operator's explicit per-turn approval. Cheap pool workers *surface* candidates; you refute / merge / decide and own the verdict.

## Pool vs native — which runtime for a fan-out

| | Native Claude Task subagent (`fabrik-reviewer`/`-researcher`/`-gui`) | OpenRouter pool (`run_agents`) |
|---|---|---|
| **Model** | Claude (subscription) | cheap non-Claude, ~$0.18–$1.20/Mtok (≤$1.5 cap) |
| **Tools** | Read/Grep/Glob/Bash on the real tree; browser/UI | sandboxed worktree + `run_command`; real file R/W (`tools_enabled=True`) — **not** text-only |
| **Best for** | line-precise grounding, review recall, GUI, the decide/refute/merge | parallel code implementation, cheap review-recall breadth, research/prose |
| **Flywheel** | **no `AgentResult` → CANNOT record** (don't tell it to) | **must `record_agent_run(spec, result)` + `results_table`** per unit |

**Pool-default (above):** gradeable fan-out (finders / grounders / reconcilers / auditors / implementers) goes to the pool by default and records; GUI / authoritative / decide-merge stay native. Per-command map: `/fabrik-execute-plan` implementers · `/fabrik-review` + `/fabrik-repo-review` finders · `/fabrik-rules-review` per-pack auditors · `/fabrik-spec-review` + `/fabrik-plan-review` grounders · `/fabrik-docs-review` reconcilers · `/fabrik-plan-after-chat` + `/fabrik-data-contract` `path:line` grounders (+ a native ~20% citation verify-sample) · `/fabrik-spec` fact + best-practice grounders (research phases 1a/1c) → **all pool**; `/fabrik-ui-design` (screen build) → **native** (`fabrik-gui`); decide/refute/merge → **always you/native**. Keep the `try: from libs.subagents import record_agent_run / except ImportError: record_agent_run = None` guard **only** on genuine pool-dispatch commands — not as a device to pre-write native footers.

## NEVER route to the pool (fabrik-lib PROPOSED_RULE)

Auth/identity/session/crypto · schema/migrations · secrets/`.env`/keys · security controls (RLS, rate-limits, `final_gate`) · deploy/infra. These stay with the primary (human-supervised) agent. **Never web/MCP-enable a task carrying sensitive context** — the model's output exfiltrates via a scraped URL. Keep the bwrap sandbox on (`sandbox=True`, fail-closed).

## The mcp.json source-of-truth

The canonical MCP server list is a hub-owned standard-format file — `/opt/fabrik/mcp.json` (`{"mcpServers": {name: {type, command, args, env}}}`, keys via `${ENV}` expansion, never inline). The pool's MCP client reads it via `AgentSpec.mcp_config` (path → unwrap the `mcpServers` key; dict → the bare server map). Adding a tool touches exactly: `claude mcp add` (main agent) → `mcpServers` in the relevant Runtime-A agent type → this `mcp.json` (pool) — never a command brief.

## Report every pool run — the results table AND the flywheel (both, always)

After any **pool** (`run_agents`, Runtime B) dispatch you EVALUATE, emit **BOTH** — sharing **one** quality verdict (judge once, put the same 0–5 in both). A run that showed a table but no flywheel row (or vice-versa) is **half-done**:

1. **A results table** (one row per unit) so a human can compare models at a glance — use the helper `results_table([{ "unit":…, "model":…, "result":<AgentResult>, "quality":0-5, "fixes":… }, …])`. Provider / Cost / Latency / **Out** (`out_tokens`) come straight from the `AgentResult`; **quality + confirmed-fixes are YOUR verdict** after materializing the diff and running the gate/tests/review.
2. **A flywheel row per unit** — **`record_agent_run(spec, result, quality_score=<the same 0-5>, project=<name>)`**. ⚠️ the older `record_run(result, …)` **silently no-ops** on a raw `AgentResult` (it wants a dict; `model`/`task_type` live on the *spec*) — always `record_agent_run(spec, result, …)`. On the VPS `SUBAGENT_RUNS_DSN` connects directly; on WSL dev pass a peer-auth `connect=` factory. It is fail-open (returns `False` silently on a DB problem) — to prove the plumbing, SELECT the row back, don't trust the return.

**A native Claude-Code-subagent (Runtime A) dispatch produces NO `AgentResult` — it CANNOT record; the flywheel is pool-only (Runtime B).** So a native-fan-out command carries no flywheel footer (see § Pool vs native). Inline / no-dispatch → nothing to record. Telemetry design: `docs/superpowers/specs/2026-07-06-subagent-runs-telemetry-design.md`.

## Vendored-module bug → UPSTREAM_FEEDBACK (binding)

When a project fixes a real bug in a **vendored `fabrik-lib` module** (e.g. `libs/subagents/`), it MUST append the fix — symptom + fix + date — to `/opt/fabrik-lib/<module>/UPSTREAM_FEEDBACK.md`. That file is the **one write allowed back into `/opt/fabrik-lib`** (cross-repo HARD STOP otherwise); the module author reads + resolves it, so the fix isn't silently lost on the next re-vendor. Fixing a vendored module without the entry breaks the loop.

## Banned

- A command brief that restates tool lists instead of naming a `subagent_type` / pointing here.
- A GUI/browser task routed to the pool (no equivalent — Runtime A/primary only).
- A pool task with `sandbox=False`, an inline API key, or web/MCP enabled while it carries sensitive context.
- Hard-coding the `mcp` SDK v2 API or the Tool schema attribute name.
- Naming a model roster or per-stage ranking in this pack (they live in the module `_TABLE` + `CODING_SUBAGENT_SELECTION.md`) — only `minimax/minimax-m3` (the default) may appear by name.
- A pool run that emitted a `record_agent_run` but no `results_table` (or vice-versa) — both, one verdict. (And never `record_run(result, …)` — it no-ops; use `record_agent_run(spec, result, …)`.)
- Telling a **native** (Runtime A) fan-out to record a flywheel row — it has no `AgentResult`; recording is pool-only.
- Fixing a bug in a vendored `fabrik-lib` module without an `UPSTREAM_FEEDBACK.md` entry.
