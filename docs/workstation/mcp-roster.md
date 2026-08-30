# MCP Roster — every server on this box: function, consumers, cost, config topology

**Date:** 2026-08-30 · **Status:** ✅ CURRENT (measured live, not recalled)
**Affects:** the local WSL2 dev box — every Claude Code window in every `/opt` repo. NOT the VPS fleet.

**⚠️ KEEP-CURRENT CONTRACT (operator directive 2026-08-30):** any change to the MCP roster — a server
added/removed/re-scoped, a config file moved, the per-project split implemented — updates THIS doc in
the SAME change. The roster lives in five config files (below); this doc is the one place a human can
see all of it. Adding a server without its row here is the defect this doc exists to end.

---

## Config topology — and the rotation law

The roster is defined in **five** `.claude.json` files, all currently identical (**16 servers** since 2026-08-30 — context7 + github retired):

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

## The servers (16 active + 2 retired)

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
| chrome-devtools | deep browser debug/perf traces (Core-Web-Vitals in the Build-Verification Loop) | DECLARED in fabrik-gui's own mcpServers allow-list | 321 MB / 5p | ON web-GUI types (with playwright) — **RULED 2026-08-30 (D-015 + D-019: rides with playwright everywhere playwright is granted, overlays included — § ruling in full)** |
| shadcn | SaaS UI component registry (MIT-B pair, operator-wired) | saas-skeleton | light | ON saas-skeleton only |
| magicui | motion component registry (the pair's other half) | saas-skeleton | 99 MB / 2p | ON saas-skeleton only |
| mobile-mcp | device/emulator automation | mobile-app | light | ON mobile-app only |
| maestro | mobile/web UI test flows — **heaviest server on the box** | mobile-app | **724 MB / 4p** | ON mobile-app only |
| postgres-pro | restricted Postgres inspection (`--access-mode=restricted`) | ALL repos — data-contract/debug DB lens | light | ON all types — **RULED 2026-08-30 (D-020: universal, operator word)**; crash FIXED same day (`uvx --with 'mcp<2'` pin, synced to all 5 fleet rosters). ⚠️ per-repo `DATABASE_URI` still owed by the split implementation — the single user-level URI pointed at a dead :15432, and local PG creds are per-repo |
| grafana | fleet observability (Prometheus/Loki/dashboards) — runs as a docker container per window | hub (deploy/monitoring, fleet beat) | docker | ON hub only |
| media-engine | image/video generation (`/opt/iterative_image_editor`) — product/catalog/packshot, avatar + faceless video, edit suite, stock, compliance | media producers: wef, brand-identiy-creator, youtube | 295 MB / 4p | ON those three only — **RULED 2026-08-30 (D-018): CONTENT-driven, never type-driven.** Standing rule: any future repo whose product/pipeline output IS media gets the overlay at adoption (one rotator edit); one-off design assets (hero/og/empty-state) route through a producer or hub window, or the engine's own API — never a fleet-wide MCP grant |
| pubchem | chemistry database lookups | chemical-commerce content (wef/bhdtrade) | light | ON wef only |
| fabrik-citation-verifier | academic citation verification (PubMed/Crossref/…, `/opt` service) | dossier/research: transdoc | service | ON transdoc only |
| serena | LSP semantic code navigation | ALL repos — symbol-level grounding (find_symbol, find_referencing_symbols) | light idle | ON all types — **RULED 2026-08-30 (D-021: adopt-and-wire)**. Root cause of prior zero usage was zero corpus wiring, not quality; now named in plan-after-chat's grounding phase + review's adjudication. Measured trial: still unused after wiring = a retirement case with evidence |

**Net effect of the split as RULED:** a typical headless API repo drops 16 → **6** servers (the
universal set: session-recall + exa + brave-search + firecrawl + postgres-pro + serena); the full
roster survives only hub-class (hub + fabrik-lib, D-015).

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
| `firecrawl` | RULED universal 2026-08-30 (D-013, "no exception"); its crash was a corrupted npx-cache entry, fixed same day |
| `postgres-pro` | RULED universal 2026-08-30 (D-020) — operator: "fix postgres-pro and wire it all type of projects"; overrides the shape-driven proposal |
| `serena` | RULED universal 2026-08-30 (D-021: adopt-and-wire) — corpus now names it for symbol-level grounding (plan-after-chat + review); unused-after-wiring = measured retirement case |

(The old "swap github/firecrawl out via corpus edits" recommendation is resolved: `github` RETIRED
end-to-end per D-014 — corpus now teaches the `gh` CLI; `firecrawl` went the other way, universal
per D-013.)

| Scaffold type | Beyond the universal 6 | Evidence |
|---|---|---|
| `python-api` | — (universal 6 only) | no command names anything type-specific for headless |
| `python-api-gpu` | — (universal 6 only) | as python-api |
| `node-api` | — (universal 6 only) | as python-api |
| `file-api` | — (universal 6 only) | as python-api |
| `file-worker` | — (universal 6 only) | as python-api |
| `saas-skeleton` | playwright · chrome-devtools · shadcn · magicui | fabrik-gui declares `mcpServers: [playwright, shadcn, chrome-devtools]`; /fabrik-ui-design drives the shadcn MCP by name; magicui = the operator's SaaS pair |
| `chrome-extension` | playwright · chrome-devtools | fabrik-gui dispatches here (MV3 loop via bundled Chromium) |
| `mobile-app` | maestro · mobile-mcp | the Build-Verification Loop's mobile branch: "mobile (RN): Maestro MCP + Mobile Next MCP" (plan-after-chat/execute-plan/user-test) + 80-mobile pack |
| `desktop-app` | playwright · chrome-devtools · shadcn² | Electron web UI → fabrik-gui's set; ²shadcn when the design system is shadcn-based (ui-design: "when the system is shadcn-based") |
| `static-site` | playwright · chrome-devtools · shadcn² | rendered-site design-review/user-test via fabrik-gui |
| `docusaurus` | playwright · chrome-devtools | reader-journey certification via fabrik-gui |
| `wordpress` | — (universal 6 only) | legacy, out of fabrik |

¹ (retired footnote) postgres-pro rode `shape.needs_database` until D-020 made it universal.
² only when the repo's frozen design system is shadcn-based; magicui stays saas-only EXCEPT the wef
overlay (D-017 supersedes the boundary for that one repo) (original operator boundary:
"use on the SaaS UI, never on produced sites").

**Per-REPO overlays (content-driven, never type-driven):** wef → +playwright (D-016: it drives/verifies
the ecommerce sites it produces) +chrome-devtools (D-019: rides with playwright wherever granted) +shadcn +magicui (D-017: React/Tailwind storefronts; motion = conversion
tooling — supersedes the magicui saas-only boundary for wef ONLY, it stands elsewhere) +pubchem
+media-engine (firecrawl now universal per D-013) · brand-identiy-creator, youtube → +media-engine ·
transdoc → +fabrik-citation-verifier (data-contract's only mention is a NEGATIVE — "does not apply
here") · hub → +grafana (deploy-verify/decommission run hub-side only; user-test's "Grafana" is
vendored-client example prose, verified).

**Headcount effect (post-D-021):** headless types run **6 servers instead of 16**; web-GUI types
8-10; mobile-app 8.

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

## Chrome-devtools — the ruling in full (D-015 + D-019, saved 2026-08-30)

Chrome-devtools is playwright's MEASURING companion, never its duplicate: playwright DRIVES the
screen (navigate, click, type, screenshot, a11y snapshot — does it work?); chrome-devtools MEASURES
it (Core-Web-Vitals via `lighthouse_audit` LCP/CLS/INP, `performance_analyze_insight` traces,
CPU/network THROTTLING for the loading/slow states, console + network inspection — is it fast?).
Neither replaces the other, and the corpus binds both by name in the same loops:

- `fabrik-ui-design.md:187` — `lighthouse_audit` (LCP/CLS/INP) + `performance_analyze_insight` in the design gate
- `fabrik-user-test.md:166,227` — throttling produces the loading/slow screen states; "a slow screen fails 'easy to use'"
- `fabrik-plan-review.md:283` + `fabrik-execute-plan.md:209` — the CWV budget in the Build-Verification Loop
- `fabrik-execute-plan.md:199` — `fabrik-gui` declares it in its own mcpServers allow-list

**Who needs it — exactly playwright's set, by rule:** chrome-devtools RIDES WITH playwright
everywhere playwright is granted — the 6 UI-bearing types (D-015) AND every per-repo playwright
overlay (D-019: wef gets +chrome-devtools with its D-016 playwright — CWV on a produced storefront
is conversion tooling, a slow shop loses sales). `mobile-app` stays out (maestro/mobile-mcp loop);
headless types have nothing to measure. Like playwright, it is NEVER a crawling/research tool.

## Chronic non-connectors — root-caused 2026-08-30 (distinct from the herd outage)

Three servers were NOT herd victims; they are broken independently, each probed to its exact error:

| Server | Root cause (verbatim evidence) | Fix direction |
|---|---|---|
| firecrawl | ~~CRASHED at startup~~ **FIXED 2026-08-30**: the `FSLegacyMainResolve` error was a corrupted `~/.npm/_npx/12b05d58…` cache entry (the 2026-08-30 wipe incident's residue — `mcp-proxy` present, its `@modelcontextprotocol/server` dep missing). Cleared the one entry; clean respawn verified. If it recurs after a cache event: clear the entry, never the whole `_npx` | the curl-swap candidate is DEAD (D-013: firecrawl universal) |
| postgres-pro | ~~`uvx postgres-mcp` crashes: `No module named 'mcp.server.fastmcp'`~~ **FIXED 2026-08-30 (D-020)**: the mcp 2.x SDK renamed FastMCP; postgres-mcp is v1 code. Pinned `uvx --with 'mcp<2' postgres-mcp` via the rotator — MCP initialize handshake verified (`postgres-mcp 1.29.1` responds), all 5 fleet rosters carry the pin. Residue: `DATABASE_URI` layer is per-repo (split-plan item) — the old URI targeted dead :15432 | done — URI repoint rides the split |
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
