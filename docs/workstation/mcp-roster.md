# MCP Roster — every server on this box: function, consumers, cost, config topology

**Date:** 2026-08-30 · **Status:** ✅ CURRENT (measured live, not recalled)
**Affects:** the local WSL2 dev box — every Claude Code window in every `/opt` repo. NOT the VPS fleet.

**⚠️ KEEP-CURRENT CONTRACT (operator directive 2026-08-30):** any change to the MCP roster — a server
added/removed/re-scoped, a config file moved, the per-project split implemented — updates THIS doc in
the SAME change. The roster lives in five config files (below); this doc is the one place a human can
see all of it. Adding a server without its row here is the defect this doc exists to end.

---

## Config topology — and the rotation law

The roster is defined in **five** `.claude.json` files, all currently identical (18 servers):

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

---

## The 18 servers

Weight = measured RSS on 2026-08-30 across live processes (per-window cost scales with window count).

| MCP | What it does | Who actually needs it (scaffold types / repos) | Weight | Recommended default |
|---|---|---|---|---|
| **session-recall** | past-session search (`search_chats`/`get_chat`) — governance-mandated by ORIENT + commands | ALL repos | 201 MB / 4p | **ON everywhere** |
| **context7** | live library/framework docs (`resolve-library-id`, `query-docs`) | all coding types, plan/build phases | 364 MB / 7p | **ON everywhere** |
| **exa** | web search + raw fetch — grounding order #1 in every spec/review command | all repos, design/review phases | 183 MB / 4p | **ON everywhere** |
| github | GitHub API (PRs, issues, code search) | PR/issue automation | 173 MB / 4p | OFF — the `gh` CLI in Bash covers it |
| brave-search | second search engine (cross-check fallback in the grounding order) | research-heavy: hub, wef, intel | 384 MB / 7p | OFF; ON research repos |
| firecrawl | scrape/crawl (raw HTML) | crawling repos (wef) — connection flaky in practice | light | OFF; ON wef |
| playwright | browser automation — fabrik-gui, /design-review, /fabrik-user-test | UI types: saas-skeleton, static-site, docusaurus, chrome-extension, desktop-app | 102 MB / 2p | ON UI types only |
| chrome-devtools | deep browser debug/perf traces | same UI types; overlaps playwright | 321 MB / 5p | OFF; enable per debug session |
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
(session-recall + context7 + exa); the full roster survives only where each server is consumed.

---

## Status of the split (decision pending)

Proposed 2026-08-30, operator decision pending: trim the user-level roster to the universal trio;
each repo gains a project-level `.mcp.json` with its extras — emitted per scaffold type by the
scaffolder (fleet's beat) and backfilled to existing repos; every roster edit applied via the
rotator's sync (the rotation law above). When implemented, update this doc's table with the
per-type `.mcp.json` contents and flip this section to EXECUTED.

**Related:** [MCP_HTTP_TRANSPORT.md](MCP_HTTP_TRANSPORT.md) (transport detail) ·
[wsl-shell-mcp-setup.md](wsl-shell-mcp-setup.md) (the Claude-Desktop bridge server) ·
[cleanup-automation.md](cleanup-automation.md) (the box's resource hygiene).
