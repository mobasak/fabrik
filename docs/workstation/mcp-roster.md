# MCP Roster — every server on this box: function, consumers, cost, config topology

**Date:** 2026-08-30 · **Status:** ✅ CURRENT (measured live, not recalled)
**Affects:** the local WSL2 dev box — every Claude Code window in every `/opt` repo. NOT the VPS fleet.

**⚠️ KEEP-CURRENT CONTRACT (operator directive 2026-08-30):** any change to the MCP roster — a server
added/removed/re-scoped, a config file moved, the per-project split implemented — updates THIS doc in
the SAME change. The roster lives in five config files (below); this doc is the one place a human can
see all of it. Adding a server without its row here is the defect this doc exists to end.

---

## Config topology — and the rotation law

The roster is defined in **five** `.claude.json` files, all currently identical (**17 servers** since 2026-08-30 — context7 retired):

| File | Role |
|---|---|
| `~/.claude.json` | the ad-hoc leftover from pre-fleet days — `claude_rotate.py::_roster_source` explicitly calls syncing FROM it "a REAL hazard" once the fleet exists |
| `~/.claude-fleet/{ob,can,sarp,mob}/.claude.json` | one per account; the **active** account's file (via the `~/.claude-fleet/active` symlink) is what live sessions read |

**⚠️ ROTATION LAW:** never hand-edit one file. A roster change goes through `claude_rotate.py`'s
roster-sync (`_roster_source` accepts a slug/dir/file to seed from) so all four account dirs stay
identical — otherwise the next quota rotation flips sessions onto a different roster mid-day.

**Process model:** every VS Code Claude window spawns its OWN copy of every enabled server
(most run 2 processes: npx wrapper + server). Tool *schemas* are deferred (ToolSearch loads them
on demand — zero context cost), but the *processes* spawn regardless. That is the CPU/RAM problem:
18 servers × 1–3 windows × 46+ repos.

**Measured 2026-08-30** (a few windows open, post-restart): 34 processes, **2.2 GB RSS** already.
At ~13 sessions the same roster measured ~23 GB (intel finding 01KZX92Q).

**⚠️ Fetch-at-spawn fragility (observed live 2026-08-30):** 13 of 18 servers are `npx -y`/`uvx`
fetch-at-spawn. After cache-prune's weekly `rm -rf ~/.npm/_npx` (00:06) + a WSL restart (13:40),
every window cold-fetched 13 servers simultaneously — connect timeouts, and the harness marks them
disconnected for the whole session (only the 5 locally-installed servers survived: session-recall,
grafana, media-engine, maestro, citation-verifier). A cold `npx` spawn succeeds in <25 s once the
herd is gone — the registry was fine; the simultaneity wasn't. Fixes that compose with the split:
pin/install servers locally instead of `npx @latest` per spawn, and/or drop the `_npx` wipe from
cache-prune (it re-downloads weekly for no gain). A window reload reconnects on the warm cache.

---

## The servers (17 active + 1 retired)

Weight = measured RSS on 2026-08-30 across live processes (per-window cost scales with window count).

| MCP | What it does | Who actually needs it (scaffold types / repos) | Weight | Recommended default |
|---|---|---|---|---|
| **session-recall** | past-session search (`search_chats`/`get_chat`) — governance-mandated by ORIENT + commands | ALL repos | 201 MB / 4p | **ON everywhere** |
| ~~context7~~ | live library/framework docs | **RETIRED 2026-08-30 (operator decision):** measured usage was 45 tool calls in the box's ENTIRE transcript history (vs exa 563 · brave 417 · firecrawl 689) for 364 MB / 7 procs per-window; official-docs `WebFetch` covers the need. Removed from all 5 rosters via `claude_rotate.py --sync-mcp` + every corpus reference swapped to official-docs WebFetch same-change (phantom-arm law). Pool agents keep on-demand context7 via their own mcp.json (zero idle cost) | — | OFF everywhere |
| **exa** | web search + raw fetch — grounding order #1 in every spec/review command | all repos, design/review phases | 183 MB / 4p | **ON everywhere** |
| ~~github~~ | GitHub API (PRs, issues, code search) | **RETIRED 2026-08-30 (D-014):** every corpus ref swapped to the `gh` CLI (`gh search code`/`gh api` — authenticated, zero idle processes) in the same change; removed from all 5 rosters via the rotator (16 servers remain) | — | OFF everywhere |
| brave-search | second search engine — NAMED in the grounding order of 6 pipeline commands that run in EVERY repo (spec, spec-review, plan-after-chat, plan-review, data-contract, docs-review) | all repos | 384 MB / 7p | **ON everywhere** (corpus-driven; scoping it off would plant a phantom arm fleet-wide) |
| **firecrawl** | scrape/crawl (raw HTML) — fallback arm in 5 pipeline commands | ALL repos (operator ruling 2026-08-30, D-013: universal, no exception) | light | **ON everywhere** — the startup crash was a CORRUPTED npx cache entry (wipe-incident residue), cleared + respawn verified 2026-08-30; the curl-swap candidate is DEAD per the ruling |
| playwright | browser automation — fabrik-gui, /design-review, /fabrik-user-test; NEVER crawling (no grounding order names it — the research chain is exa/brave/firecrawl) | the 6 UI-bearing types | 102 MB / 2p | ON UI types only — **RULED 2026-08-30 (D-015)** |
| chrome-devtools | deep browser debug/perf traces (Core-Web-Vitals in the Build-Verification Loop) | DECLARED in fabrik-gui's own mcpServers allow-list | 321 MB / 5p | ON web-GUI types (with playwright) — **RULED 2026-08-30 (D-015)** |
| shadcn | SaaS UI component registry (MIT-B pair, operator-wired) | saas-skeleton | light | ON saas-skeleton only |
| magicui | motion component registry (the pair's other half) | saas-skeleton | 99 MB / 2p | ON saas-skeleton only |
| mobile-mcp | device/emulator automation | mobile-app | light | ON mobile-app only |
| maestro | mobile/web UI test flows — **heaviest server on the box** | mobile-app | **724 MB / 4p** | ON mobile-app only |
| postgres-pro | restricted Postgres inspection (`--access-mode=restricted`) | `needs_database` repos during data-contract/debug | light | OFF; ON DB-backed repos |
| grafana | fleet observability (Prometheus/Loki/dashboards) — runs as a docker container per window | hub (deploy/monitoring, fleet beat) | docker | ON hub only |
| media-engine | image/video generation (`/opt/iterative_image_editor`) | media producers: wef, brand-identiy-creator, youtube | 295 MB / 4p | ON those three only |
| pubchem | chemistry database lookups | chemical-commerce content (wef/bhdtrade) | light | ON wef only |
| fabrik-citation-verifier | academic citation verification (PubMed/Crossref/…, `/opt` service) | dossier/research: transdoc | service | ON transdoc only |
| serena | LSP semantic code navigation | large codebases (hub, trade-intelligence, youtube) | light idle | operator call — useful, but a per-window process everywhere |

**Net effect of the recommended split:** a typical headless API repo drops 18 → **3** servers
(session-recall + exa + brave-search); the full roster survives only where each server is consumed.

---

## Per-scaffold-type default sets (rebuilt 2026-08-30 from a corpus scan, not pipeline intuition)

**Method:** grep every `mcp__server__` reference + name mention across the rendered corpus (32
commands, agent defs, fragments, rule packs), read each ambiguous hit in context, and let COMMANDS
decide — a server a universal command names must exist everywhere it runs, or the reference is a
phantom arm (the wef 01M17XXF defect class).

**Universal base — every type, every repo (command-evidence; context7 left this set 2026-08-30):**

| Server | Evidence |
|---|---|
| `session-recall` | named by 22 commands + ORIENT mandate |
| `exa` | grounding order #1 in 7 pipeline commands (spec, spec-review, plan-after-chat, plan-review, data-contract, docs-review, execute-plan) |
| `brave-search` | named in the same grounding orders (6 commands) — every repo runs these |

Two more are named by universal commands but recommended for CORPUS EDITS instead of universal cost
(operator decision): `github` (2 refs in /fabrik-spec — swap to the `gh` CLI, zero processes) and
`firecrawl` (5 fallback refs — flaky/absent in live sessions already; swap to the orchestrator-`curl`
NEEDS-RAW-FETCH path the researcher def now teaches). Until those edits land, both are phantom arms
whether enabled or not.

| Scaffold type | Beyond the universal 3 | Evidence |
|---|---|---|
| `python-api` | postgres-pro¹ | no command names it — ad-hoc DB inspection utility, flag-driven |
| `python-api-gpu` | postgres-pro¹ | as python-api |
| `node-api` | postgres-pro¹ | as python-api |
| `file-api` | postgres-pro¹ | as python-api |
| `file-worker` | postgres-pro¹ | as python-api |
| `saas-skeleton` | playwright · chrome-devtools · shadcn · magicui · postgres-pro | fabrik-gui declares `mcpServers: [playwright, shadcn, chrome-devtools]`; /fabrik-ui-design drives the shadcn MCP by name; magicui = the operator's SaaS pair |
| `chrome-extension` | playwright · chrome-devtools | fabrik-gui dispatches here (MV3 loop via bundled Chromium) |
| `mobile-app` | maestro · mobile-mcp | the Build-Verification Loop's mobile branch: "mobile (RN): Maestro MCP + Mobile Next MCP" (plan-after-chat/execute-plan/user-test) + 80-mobile pack |
| `desktop-app` | playwright · chrome-devtools · shadcn² | Electron web UI → fabrik-gui's set; ²shadcn when the design system is shadcn-based (ui-design: "when the system is shadcn-based") |
| `static-site` | playwright · chrome-devtools · shadcn² | rendered-site design-review/user-test via fabrik-gui |
| `docusaurus` | playwright · chrome-devtools | reader-journey certification via fabrik-gui |
| `wordpress` | — (universal 4 only) | legacy, out of fabrik |

¹ rides `shape.needs_database: true`, never the type name.
² only when the repo's frozen design system is shadcn-based; magicui stays saas-only EXCEPT the wef
overlay (D-017 supersedes the boundary for that one repo) (original operator boundary:
"use on the SaaS UI, never on produced sites").

**Per-REPO overlays (content-driven, never type-driven):** wef → +playwright (D-016: it drives/verifies
the ecommerce sites it produces) +shadcn +magicui (D-017: React/Tailwind storefronts; motion = conversion
tooling — supersedes the magicui saas-only boundary for wef ONLY, it stands elsewhere) +pubchem
+media-engine (firecrawl now universal per D-013) · brand-identiy-creator, youtube → +media-engine ·
transdoc → +fabrik-citation-verifier (data-contract's only mention is a NEGATIVE — "does not apply
here") · hub → +grafana (deploy-verify/decommission run hub-side only; user-test's "Grafana" is
vendored-client example prose, verified) (+serena, operator call).

**Headcount effect:** headless types run **3-4 servers instead of 17**; web-GUI types 7-9;
mobile-app 6.

## Playwright — the ruling in full (D-015 + D-016, operator-saved verbatim rationale)

Playwright is NEVER a crawling tool: no grounding order in the corpus names it — the research chain
is exa → brave → firecrawl (+ raw `curl`). Its job is the opposite direction: it drives **our own
running screens** — navigate, click, type, screenshot at 375/768/1440, accessibility snapshots — for
the Build-Verification Loop, `/design-review`, and `/fabrik-user-test`'s web branch. Firecrawl reads
*other people's* sites; playwright verifies *ours*.

**Who needs it — every UI-bearing type:** `saas-skeleton` · `chrome-extension` (the only sanctioned
MV3 test harness — `launchPersistentContext`) · `desktop-app` (Electron UI) · `static-site` ·
`docusaurus` (rendered-site certification) · `mobile-app` is NOT in this set (its loop is
maestro/mobile-mcp). The `fabrik-gui` agent declares playwright by name. **Headless types
(python-api, python-api-gpu, node-api, file-api, file-worker) have zero use for it — nothing to
render.** Disposition: ON for the 6 UI-bearing types, OFF for headless; the hub keeps it only via
its hub-class full roster. Its companion `chrome-devtools` (performance/Core-Web-Vitals audits in
the same loop) takes the same disposition. **Plus the per-repo overlay: `web-ecommerce-factory`
(D-016)** — wef drives and verifies the ecommerce sites it produces, rendered-surface work its own
repo type would not otherwise grant.

## Chronic non-connectors — root-caused 2026-08-30 (distinct from the herd outage)

Three servers were NOT herd victims; they are broken independently, each probed to its exact error:

| Server | Root cause (verbatim evidence) | Fix direction |
|---|---|---|
| firecrawl | ~~CRASHED at startup~~ **FIXED 2026-08-30**: the `FSLegacyMainResolve` error was a corrupted `~/.npm/_npx/12b05d58…` cache entry (the 2026-08-30 wipe incident's residue — `mcp-proxy` present, its `@modelcontextprotocol/server` dep missing). Cleared the one entry; clean respawn verified. If it recurs after a cache event: clear the entry, never the whole `_npx` | the curl-swap candidate is DEAD (D-013: firecrawl universal) |
| postgres-pro | `uvx postgres-mcp` crashes: `No module named 'mcp.server.fastmcp'` — the mcp 2.x SDK renamed FastMCP; postgres-mcp is v1 code | pin `uvx --with 'mcp<2' postgres-mcp` in the roster (via the rotator sync) |
| fabrik-citation-verifier | config points at `http://127.0.0.1:8033/mcp` (type: http) but only the REST API on :8032 is up — :8033 answers nothing (curl 000) | the owning repo restarts its MCP endpoint or the roster repoints; connected this morning, so the endpoint died today |

`maestro` is a fourth, milder case: slow cold start (JVM), flappy across reloads — works once warm.

## Our OWN crawling MCP — built and never wired (found 2026-08-30)

`/opt/apidoccreator` (docs-registry, port 8302) is the box's own crawling/docs service: registers any
docs URL, auto-detects OpenAPI/llms.txt/sitemap/HTML, scrapes, LLM-generates + chunks, serves via
REST — and ships its own MCP server (`docs-mcp` console script → `/opt/apidoccreator/src/docs_registry/mcp_server.py`,
4 tools: list_docs · get_doc · search…). It is NOT in the 18-server roster — never connected to any
Claude window. Candidate: wire it (self-hosted, $0) as a partial context7 replacement for
already-registered sources; decision rides the same split.

## Status of the split (decision pending — PARTIALLY RULED)

**fabrik-lib is HUB-CLASS (operator ruling 2026-08-30, D-015): full roster, exactly like /opt/fabrik —
it builds modules for every scaffold type and its agent needs the whole toolbox. (Today this is
automatic: the roster is USER-level, every window on the box loads it; the split implementation must
preserve fabrik-lib + hub at full set while trimming project windows.)**

**Operator ruling 2026-08-30 (D-013): session-recall · exa · brave-search · firecrawl are UNIVERSAL —
every project, no exception. Any trim below excludes these four; the firecrawl→curl corpus swap is DEAD.**

Proposed 2026-08-30, remainder of the decision pending: trim the user-level roster to the universal set above;
each repo gains a project-level `.mcp.json` with its extras — emitted per scaffold type by the
scaffolder (fleet's beat) and backfilled to existing repos; every roster edit applied via the
rotator's sync (the rotation law above). When implemented, update this doc's table with the
per-type `.mcp.json` contents and flip this section to EXECUTED.

**Related:** [MCP_HTTP_TRANSPORT.md](MCP_HTTP_TRANSPORT.md) (transport detail) ·
[wsl-shell-mcp-setup.md](wsl-shell-mcp-setup.md) (the Claude-Desktop bridge server) ·
[cleanup-automation.md](cleanup-automation.md) (the box's resource hygiene).
