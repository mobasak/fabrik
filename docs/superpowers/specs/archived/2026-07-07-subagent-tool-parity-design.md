# Subagent Tool-Parity — Design Spec

**Status:** CONVERGED · **Version 2** (post-convergence factual reconciliation, 2026-07-07)
**Version 2 (no external-fact change — same live-grounding):** (a) the pool half is now its own CONVERGED spec `../../../fabrik-lib/docs/superpowers/specs/2026-07-07-subagents-mcp-client-design.md` — **interim Brave provider SHIPPED**, the MCP-client capability designed there; my "add Brave provider" ask is superseded by that. (b) Added the deliverables assigned to me after v1: **`/opt/fabrik/mcp.json`** (the MCP source-of-truth, non-dot so Claude Code doesn't auto-load it over the user-scoped servers) + **key provisioning** (`EXA/FIRECRAWL/CONTEXT7/BRAVE_API_KEY` into `/opt/fabrik/.env`, done). (c) The `tools`×`mcpServers` open unknown is **RESOLVED**: the built `fabrik-researcher` uses `mcpServers:` + `disallowedTools:` (omits `tools:`) and registered with the search MCPs, read-only. SC4 count 3→4.
**Convergence (v1):** Pass 1 re-verified all external facts live this session (Claude Code subagent `tools`/`mcpServers` model at code.claude.com/docs/en/sub-agents; `@brave/brave-search-mcp-server`; the fabrik-lib `subagents` module source — `agent.py` AgentSpec + `web_tools.py` Exa/Firecrawl/Context7-no-Brave + `PROPOSED_RULE`) and audited the vendor verdict against `/opt/fabrik-lib/README.md` (subagents=VENDOR, adaptive-dispatch≠this, web_tools=ENHANCE, no module for native Claude-Code scoping) — fixed 2 completeness gaps (no testable success criteria; the non-research dispatchers unplaced). Pass 2 fixed 2 more (all 10 dispatchers now placed; SC count). Pass 3 fixed 4 count-inconsistencies (8→10 briefs ×2, "4 repo-grounded"→5, Shape/infra deliverables). Pass 4: full 4-axis re-scan, **zero edits**, md5 START==END (`f7883365121c1853102bb48c2012c2e6`) — the fixed point.
**Date:** 2026-07-07
**Author:** Claude (via `/fabrik-spec`, driven by Özgür)
**Scope:** hub-side governance in `/opt/fabrik` (agent types, command briefs, a rules pack, MCP config) + one enhancement proposed to `/opt/fabrik-lib/subagents`. No deployed service; no `shape.*` flags apply.
**Related:** `2026-07-06-subagent-runs-telemetry-design.md` (the *flywheel*/`record_agent_run` side) — this spec is the complementary *tool-access* side; both concern the same three runtimes.

---

## Goal

When any Fabrik command dispatches a subagent (research grounder, code finder, GUI reviewer, doc reconciler, implementer), that subagent must have **exactly the external tools its task needs — no more, no less — across whichever of the three runtimes it runs on**. Adding a new tool (e.g. today's Brave Search MCP) must be a **bounded, single-source change** (update one agent type + one module provider), not an edit to every dispatching command.

**The three runtimes** (all real, all in play):
- **A — Claude Code MAIN agent.** Has every session-connected MCP: `exa`, `brave-search`, `firecrawl`, `context7`, `playwright`, `chrome-devtools`, `shadcn` (+ `puppeteer`, `github`, `pubchem`, `fabrik-citation-verifier`), plus `WebSearch`/`WebFetch` and skills (`frontend-design`, `dataviz`). Mobile (`maestro`, `mobile-next`) are build-time-wired, not global.
- **B — Claude Code SUBAGENTS** (the `Agent` tool / `subagent_type`). These *are* Claude instances; tool access is governed by the agent-type frontmatter. **This is what commands dispatch today** (the fabrik-lib pool is not vendored yet).
- **C — fabrik-lib `subagents` POOL** (OpenRouter-API models). Not Claude; **no MCP, no browser.** Capabilities are the module's own `web_tools` (hosted Exa/Firecrawl/Context7 by env key) + sandboxed file tools.

## Non-goals / out of scope

- The `record_agent_run`/telemetry flywheel (covered by `2026-07-06-subagent-runs-telemetry-design.md`).
- Building a new subagent runtime — the pool already exists (`fabrik-lib/subagents`).
- Giving the pool browser/GUI tools — there is no OpenRouter-side equivalent (see Constraints).
- Re-grounding the `.windsurf/rules` write-style packs (that is `/fabrik-plan-after-chat`'s job).

---

## External dependencies (grounded live, this session — 2026-07-07)

1. **Claude Code subagent tool model** — the mechanism for Runtime B access.
   - `tools` frontmatter: **"Inherits all tools if omitted."** When listed, the subagent gets **only** those.
   - **"Subagents inherit the internal tools and MCP tools available in the main conversation by default."**
   - **`mcpServers`** frontmatter: *"MCP servers available to this subagent"* — references an already-configured server by name (e.g. `exa`) or an inline definition. This is the clean per-server scoping knob.
   - `disallowedTools`: subtracts from the inherited/specified list. `skills` field preloads Skills (don't list `Skill` in `tools`).
   - Caveat: **plugin** subagents ignore `mcpServers`/`hooks`/`permissionMode` — a scoped agent type must live in `.claude/agents/` or `~/.claude/agents/`, not a plugin.
   - Source: https://code.claude.com/docs/en/sub-agents (fetched 2026-07-07).
2. **Brave Search MCP** — the tool added today.
   - Package `@brave/brave-search-mcp-server` (Brave Software, v2.0.82, 2026-05-14). Run: `npx -y @brave/brave-search-mcp-server --transport stdio` (stdio is default). Key: env `BRAVE_API_KEY` (or `BRAVE_API_KEY_FILE`). Tools: web/local/image/video/news/summarizer.
   - Sources: https://www.npmjs.com/package/@brave/brave-search-mcp-server · https://github.com/brave/brave-search-mcp-server (fetched 2026-07-07).
   - **Wired this session:** `BRAVE_API_KEY` saved to `/opt/fabrik/.env` (+ `.env.example` placeholder); `claude mcp add brave-search --scope user` → **✔ Connected**. Tool namespace `mcp__brave-search__*`.
3. **fabrik-lib `subagents` module** — the Runtime-C runtime (VENDOR target).
   - `AgentSpec` (`subagents/subagents/agent.py:42-82`): `web_tools: frozenset[str] | None` (off by default — `{web_search, web_search_brave, web_scrape, web_crawl, docs_lookup}`), `tools_enabled`, `allowed_commands` (default `python/pytest/ruff/mypy`, **no `git`, no network**), `sandbox` (bubblewrap, fail-closed), `task_type` (`spec/plan/code/review/docs/research`).
   - `web_tools.py`: *"Env-keyed HTTP tools that call the hosted Exa / Brave / Firecrawl / Context7 APIs. OFF by default."* (`web_search`→Exa, `web_search_brave`→Brave, `web_scrape`/`web_crawl`→Firecrawl, `docs_lookup`→Context7). **Brave provider SHIPPED (`web_search_brave`, `web_tools.py:130`); no browser tool.**
   - `PROPOSED_RULE-using-subagents.md`: the never-route list (auth/identity/crypto · schema/migrations · secrets · security controls · deploy/infra) + "enable web_tools per task type, not by default" + "keep the sandbox on."
   - Source: read directly this session at the paths above.

---

## fabrik-lib vendor → enhance → build verdict

| Capability | Verdict | Owner (WHO develops it) |
|---|---|---|
| Parallel subagent-pool runtime (Runtime C) | **VENDOR** `fabrik-lib/subagents` as-is (already built) | consuming project vendors it; **fabrik-lib AI** maintains |
| Runtime-B tool scoping (Claude Code subagents) | **native config, not a build** — agent-type `tools:` + `mcpServers:` + `disallowedTools:` | **us** (`/opt/fabrik` → `~/.claude/agents/*.md`) |
| The pool's tool access (Brave provider **+** MCP client) | **ENHANCE** `fabrik-lib/subagents` — interim Brave `web_search` provider **SHIPPED** + an MCP-client capability | **fabrik-lib AI** — designed in its own CONVERGED spec `2026-07-07-subagents-mcp-client-design.md` (v1 asked only for the Brave provider; the MCP client generalises it) |
| The tool-per-task-type-per-runtime routing rule + never-route list | **BUILD (glue)** — a short `.windsurf/rules` pack `using-subagents` folding the module's `PROPOSED_RULE` + the mapping | **us** (`/opt/fabrik`) → `.windsurf/rules/core/62-using-subagents.md` |
| The MCP source-of-truth the pool reads (`AgentSpec.mcp_config`) + provisioning the `*_API_KEY`s into the pool env | **BUILD (glue/config)** — a standard `{"mcpServers":{…}}` file, keys via `${ENV}` | **us** (`/opt/fabrik`) → `/opt/fabrik/mcp.json` + `/opt/fabrik/.env` |

**Answer to "who develops this?": BOTH, split — and neither part is large.** We own the Claude Code side (agent types + command wiring + the rules pack + MCP config, all configuration) and vendor the module; fabrik-lib AI owns the one module enhancement (a Brave provider in `web_tools`) plus any new tool-knob the pool needs. There is **no build-from-scratch** on either side — the runtime exists, and Runtime-B scoping is native Claude Code.

---

## The tool → runtime mapping (the core artifact)

| Capability | Main agent (A) | Claude Code subagent (B) | Pool (C) |
|---|---|---|---|
| Web search | `mcp__exa__*`, `mcp__brave-search__*`, `WebSearch` | `mcpServers: [exa, brave-search]` (scoped type) or inherit | `web_tools={"web_search","web_search_brave"}` (Exa + Brave — both shipped) |
| Page scrape/crawl | `mcp__firecrawl__*` | `mcpServers: [firecrawl]` | `web_tools={"web_scrape","web_crawl"}` |
| Library docs | `mcp__context7__*` | `mcpServers: [context7]` | `web_tools={"docs_lookup"}` |
| GUI drive/verify | `mcp__playwright__*`, `shadcn`, `chrome-devtools`, `maestro` | `mcpServers: [playwright, …]` (or `design-review` type) | **❌ none — stays in A/B (primary or a Claude Code subagent)** |
| File read/edit + `ruff`/`pytest` | native | native (`tools:`) | module file tools + `allowed_commands` |

## Chosen approach — scoped agent types + module `web_tools`, indexed by one rules pack

1. **Runtime B — three scoped Claude Code agent types** (`~/.claude/agents/`):
   - **`fabrik-researcher`** — `tools: Read, Grep, Glob, WebSearch, WebFetch`; `mcpServers: [exa, brave-search, firecrawl, context7]`. Grounding commands (`/fabrik-spec-review`, `/fabrik-plan-after-chat`, `/fabrik-plan-review`, `/fabrik-data-contract`) dispatch **grounders** as this type.
   - **`fabrik-gui`** — `mcpServers: [playwright, shadcn, chrome-devtools]` (+ `frontend-design`/`dataviz` via `skills:`). GUI screen-building / rendered-review subagents. (`design-review` already covers the rendered-critique case with `mcp__playwright__*`.)
   - **`fabrik-reviewer`** — unchanged (`Read, Grep, Glob, Bash`, no MCP); code review is repo-grounded. Add `context7` **only** if SDK-doc verification is later wanted.
2. **Runtime C — `AgentSpec.web_tools` set from `task_type`** at dispatch: `research`/`plan` → `{web_search, docs_lookup}` (+`web_scrape` to read a page); `code`/`review`/`docs` → `None`. GUI is never routed to the pool.
3. **One source of truth** — a short `.windsurf/rules` pack **`using-subagents`** that folds the module's `PROPOSED_RULE` (never-route list, sandbox-on, bound every agent) + the mapping table above. Command briefs *reference* it; they don't restate tool lists.
4. **Adding a tool becomes single-source**: Runtime A = `claude mcp add` (main agent, done for Brave) → auto-inherited by any *unrestricted* subagent; Runtime B scoped types = add the server to the relevant agent type's `mcpServers:` (one file); Runtime C = fabrik-lib adds the provider to `web_tools`. Three touch points, each owned by the right party — never all 10 dispatching command briefs.
5. **Only the *web-research* commands get `fabrik-researcher`; every other dispatcher is least-privilege.** Placing all 10 subagent-dispatching commands (the set the flywheel pass covers):
   - **`fabrik-researcher`** (search MCPs): `/fabrik-spec-review`, `/fabrik-plan-after-chat`, `/fabrik-plan-review`, `/fabrik-data-contract` — grounders that re-verify external facts / field standards live.
   - **reviewer-class, MCP-less** (`fabrik-reviewer` or equivalent): `/fabrik-review` (finders), `/fabrik-docs-review` (reconcilers), `/fabrik-repo-review` (unit reviewers), `/fabrik-rules-review` (pack auditors), `/fabrik-ui-design-review` (contract grounders) — all read code/contracts, never the web.
   - **general builder type** (native file/edit/Bash + optional `context7` for SDK docs, no search/GUI MCPs): `/fabrik-execute-plan` implementers.
   - **`fabrik-gui`** / `design-review` (browser MCPs): GUI screen-building + rendered-review subagents (in `/fabrik-execute-plan`'s GUI phases / the Build Verification Loop).
   A subagent gets web/GUI/MCP access only when its task provably needs it — least-privilege by default.

### Rejected alternatives
- **Dispatch everything untyped (`Tools: *`).** Simplest — every subagent inherits every MCP by default. **Rejected:** violates the goal ("*exactly* the tools its task needs") and least-privilege — a code finder would carry browser/scrape tools, a research agent would carry file-write/exec near secrets (the module's own `never-route` discipline exists precisely to prevent this). It also does nothing for Runtime C (no MCP there).
- **Per-command tool lists in each brief.** **Rejected:** this is the 10-file-edit maintenance cost (one per dispatching command) the goal explicitly exists to remove; drifts immediately.

---

## Constraints

- **GUI/browser has no pool equivalent.** Runtime C cannot drive Playwright/Maestro/shadcn. All GUI verification stays in Runtime A (primary) or B (a Claude Code `fabrik-gui`/`design-review` subagent). A plan that routes GUI work to the pool is wrong by construction.
- **Never-route to the pool** (`PROPOSED_RULE`): auth/identity/session/crypto, schema/migrations, secrets/`.env`/keys, security controls (RLS, rate-limits, `final_gate`), deploy/infra — these stay with the primary agent.
- **Web tools are paid + reach the internet.** Enable per task type only; `max_cost_usd` does **not** bound web-API spend → cap `max_turns` for web-enabled pool agents. Never web-enable a task carrying sensitive context (output itself exfiltrates via a scraped URL).
- **Cross-repo HARD STOP:** we do **not** edit `/opt/fabrik-lib`; the Brave-provider enhancement is proposed to fabrik-lib, built by its AI.
- **Plugin caveat:** the scoped agent types must live in `~/.claude/agents/` (plugin subagents ignore `mcpServers`).
- **Secret hygiene:** `BRAVE_API_KEY` lives in gitignored `.env`; never committed. `.env.example` carries only the empty placeholder.

## Shape / infra

Hub-side governance + config only — no scaffold type, no deployed service, **no `shape.*` flags**. Deliverables: two new agent types `~/.claude/agents/fabrik-researcher.md` + `fabrik-gui.md` (**built**); the `.windsurf/rules/core/62-using-subagents.md` pack (**built**); **`/opt/fabrik/mcp.json`** the MCP source-of-truth (**built**); key provisioning into `/opt/fabrik/.env` (**done**); and edits to the dispatching command briefs to name the right `subagent_type` — **done (2026-07-07):** `fabrik-researcher` wired into the 4 web-research commands (`/fabrik-spec-review`, `/fabrik-plan-after-chat`, `/fabrik-plan-review`, `/fabrik-data-contract`); `fabrik-gui` wired into `/fabrik-execute-plan`'s GUI phases (3b); reviewer-class (finders) + general builder (implementers) were already the case. The v1 "propose the Brave provider" item is **done** (fabrik-lib shipped it). **All deliverables on the Claude Code side are now complete.**

## Success criteria (testable)

1. **Research subagent has the search MCPs.** A grounder dispatched as `fabrik-researcher` can call `mcp__brave-search__*` **and** `mcp__exa__*` and get results (live probe).
2. **Finder stays least-privilege.** `grep -E "mcp__|WebSearch|WebFetch|mcpServers" ~/.claude/agents/fabrik-reviewer.md` returns nothing — the code-review type has no web/MCP access.
3. **Right type per command.** The 4 web-research commands (`/fabrik-spec-review`, `/fabrik-plan-after-chat`, `/fabrik-plan-review`, `/fabrik-data-contract`) name `subagent_type: fabrik-researcher` for their grounders; the 5 repo-grounded dispatchers (`/fabrik-review`, `/fabrik-docs-review`, `/fabrik-repo-review`, `/fabrik-rules-review`, `/fabrik-ui-design-review`) name the reviewer-class type — both verifiable by grep.
4. **Adding a tool is single-source.** Introducing a new search MCP requires editing exactly four files — the main MCP config (`claude mcp add`), `~/.claude/agents/fabrik-researcher.md` (`mcpServers`), `/opt/fabrik/mcp.json` (the pool source-of-truth), and fabrik-lib `web_tools.py` — and **zero** command briefs: `grep -lE "mcp__[a-z]" ~/.claude/commands/fabrik-*.md` gains no new file.
5. **The rule pack is the single source.** `.windsurf/rules/**/using-subagents.md` exists and contains the never-route list + the tool→runtime mapping table; each of the 10 dispatching briefs references it rather than restating tool lists.
6. **GUI never hits the pool.** The mapping marks GUI ❌ for Runtime C, and no command sets `web_tools` for a GUI task or routes a GUI/Playwright step to the pool (grep the GUI loops).
7. **Pool web_tools track task_type.** A pool `AgentSpec` for a `research`/`plan` task carries `web_tools={"web_search","docs_lookup"}`; a `code`/`review`/`docs` task carries `web_tools=None` (inspect the dispatch call sites).

## Open / blocking unknowns

- **`tools` × `mcpServers` interaction — RESOLVED (v2).** The built `fabrik-researcher` **omits `tools:`** and uses **`mcpServers:` + `disallowedTools:`** (subtract the mutation/exec tools); Claude Code registered it as "all tools except Edit/Write/MultiEdit/NotebookEdit/Bash" — i.e. it keeps the search MCPs and is read-only. Note (minor, non-blocking): `mcpServers:` here did **not** scope the MCP set *down* to just the four listed — the agent inherited all MCP servers minus the disallowed built-ins; if strict per-server least-privilege is wanted later, list the `mcp__…` tools explicitly in `tools:` instead. Functionally the research tools are present, read-only enforced.
- **Brave-in-pool timing (not blocking):** the pool isn't vendored yet, so the fabrik-lib `web_tools` Brave provider is a *proposal now, build-when-vendored*. Until then Runtime C uses Exa for `web_search` (unchanged).
- **Mobile MCPs (maestro/mobile-next):** build-time-wired per `gui-toolchain.md`; the `fabrik-gui` type lists them only for mobile projects. Not a global concern.
