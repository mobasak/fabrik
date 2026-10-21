# Own scrape and crawl tools for agents and runtime, Firecrawl as fallback — design

Status: DRAFT
Owner: intel
Work item: W-10146d20 · governing decision D-1093

## Personas

| Persona | Who | What they need from this | Duty this spec gives them |
|---|---|---|---|
| **P1 — the operator** (primary) | Özgür, quoted in D-1093 | research that keeps working when a metered vendor runs dry, without paying for a top-up | none (approves the spec gate) |
| P2 — research seats | `fabrik-researcher` and the research/grounding seats `/fabrik-spec`, `/fabrik-spec-review`, `/fabrik-plan-review`, `/fabrik-plan-after-chat`, `/fabrik-vision`, `/fabrik-data-contract`, `/fabrik-workflow-review` dispatch | a live, raw page read (the `maxAge:0` "settle a dispute" fetch) and a small docs crawl, as markdown | call the own tool first; call Firecrawl only on a typed `blocked` result or a gap row |
| P3 — runtime code | `rivals_run.py` (51 project copies), fabrik-lib `web-tools`, the deep-research and competitor-intel packs | a scrape leg that does not spend credits | route `web_scrape` / `web_crawl` / the verify-stage scraper through web-scrape first |
| P4 — the coordinator | the hub merge owner | merges a synced surface once, with a test that proves the fallback order | merge; force the governance sync |
| P5 — fabrik-lib's agent | the module owner (a separate repo) | concrete, small enhancement requests with a test each | build the module enhancements in § fabrik-lib asks |
| P6 — infra | the beat for the MCP roster, `mcp_defs.json`, `emit_mcp_project_config.py`, the box services | one new local MCP server registered beside `fabrik-citation-verifier` | register and supervise the server |

The operator, verbatim (D-1093): *"we need to find where we use firecrawl, test it against our modules, if we can
replace properly, we should, if not we need to enhance our modules if it is not too much for, and restest, then use our
tools, firecrawl can become a fallback."* And earlier the same day: *"dont we have fabrik-lib modules to do exact same as
like firecrawl?"*

**P2's loop, step budget 3:** (1) call `scrape(url)` on the own tool; (2) read the markdown, or on `blocked` call
`firecrawl_scrape`; (3) cite the URL and the fetch date. Every feature below traces to P2 or P3; the MCP server exists
because P2's seats have no shell (`fabrik-researcher` carries Read, Grep, Glob, WebFetch, WebSearch, ToolSearch only).

## Intake Inventory

| I# | Item (anchored) | Disposition | Where |
|---|---|---|---|
| I1 | "find where we use firecrawl" | IN | § Inventory |
| I2 | "test it against our modules" | IN | § Test ledger |
| I3 | "if we can replace properly, we should" | IN | § Chosen approach |
| I4 | "if not we need to enhance our modules if it is not too much for" | IN | § fabrik-lib asks (small gaps) · § Gaps kept on Firecrawl (large) |
| I5 | "and restest" | IN | § Lifecycle — the ledger re-runs after each enhancement |
| I6 | "then use our tools, firecrawl can become a fallback" | IN | § Chosen approach · § Fallback contract |
| I7 | "dont we have fabrik-lib modules to do exact same as like firecrawl?" | IN | § fabrik-lib verdict (answer: scrape and crawl yes; search, LLM extraction, screenshots and anti-bot no) |
| I8 | coordinator's method: "the calls actually made this month by kind" | IN, measured as unavailable | § Inventory — no local call log exists; only the credit balance is readable |
| I9 | D-1093: "no Firecrawl top-up" | IN | § Constraints |
| I10 | browserless memory raise 2G→3G (gate W-cbd80821) | OUT-OF-SCOPE | its own operator gate W-cbd80821; § Lifecycle names it as the growth trigger for rendered fetches |
| I11 | the Brave key is revoked (gate W-12f21514) | OUT-OF-SCOPE | its own operator gate W-12f21514; search is not in this spec |
| I12 | 40 projects still vendor the retired `libs/subagents/web_tools.py` (D-132) | OUT-OF-SCOPE | a fleet finding mailed at close (named in § Open items) |
| I13 | the live Firecrawl key sits in `backups/*.env.backup*` | OUT-OF-SCOPE | by design — `backups/` is the gitignored pre-edit copy the contract requires; key rotation is an operator credentials gate, named in § Open items |

Intake: 13 items — 9 IN, 4 OUT-OF-SCOPE (each named), 0 ASK.

## Goal

Agents and runtime code read and crawl web pages through Fabrik's own infrastructure — fabrik-lib `web-scrape` (httpx
plus the vps1 browserless container), `doc-crawl` and `pdf-extract` — and reach Firecrawl only when the own tool reports
a page it cannot read (a bot wall) or a capability it does not have (LLM schema extraction, screenshots, page actions).

## Why this exists

Firecrawl is the only scrape leg the research seats and the runtime code use, and it is metered. On 2026-10-21 the
account read `remaining_credits: -6` of `plan_credits: 5000`, with the period ending 2026-11-12 (executed:
`GET https://api.firecrawl.dev/v1/team/credit-usage`, `fc_credits.py` in the run folder). The 5 000 credits went in nine
days, so every seat that names `firecrawl_scrape` — including the researcher's "settle a dispute" live fetch — is dead
for three weeks, and the runtime scrape legs return errors. The operator ruled no top-up (D-1093). fabrik-lib already
fetches, renders and crawls; nothing exposes it to the seats.

## Inventory (I1, I8)

Measured by an Explore seat over the hub, fabrik-lib and every `/opt` project, 2026-10-21 (report in the run folder,
`inventory-seat.jsonl`).

| Surface | Firecrawl capability used | Kind |
|---|---|---|
| `mcp.json`:16-20, `scripts/sysadmin/mcp_defs.json`:32-36, `scripts/sysadmin/emit_mcp_project_config.py`:43 | the MCP server itself | config |
| `commands/_agents/fabrik-researcher.md` (mcpServers line 4; scrape with `maxAge:0`, `formats:["query"]`) | scrape, "structured extraction" | instruction |
| eight command sources: fabrik-spec, fabrik-spec-review, fabrik-plan-review, fabrik-plan-after-chat, fabrik-data-contract, fabrik-vision, fabrik-workflow-review, fabrik-rivals | search and scrape | instruction |
| `CLAUDE.md` § External Knowledge, `.windsurf/rules/core/57-external-data-sourcing.md`, `.windsurfrules`:54 | tier-2 engine (D-337/D-338/D-845) | instruction |
| fabrik-lib `web-tools/web_tools.py`:421 (scrape), :439 (crawl), :772 (async search), :815 (async scrape); hub copy `libs/web_tools.py` | search, scrape, crawl | code |
| `scripts/rivals_run.py` (hub + 50 project copies, one hash): legs at :1169, verify-stage `scrape=a_firecrawl_scrape` at :1253 | search, scrape | code |
| deep-research and competitor-intel packs | search leg | config |
| `scripts/sysadmin/quota_dashboard.py`:372, `scripts/sysadmin/mcp_health.py`:157 | credit balance read | code |

No capability beyond search, scrape and crawl is called anywhere (map, agent, parse, research_* are unused). **No local
log of Firecrawl calls exists**, so I8 is answered by the balance alone.

## Test ledger (I2) — fabrik-lib against each use, 2026-10-21

Firecrawl could not be run side by side (out of credits), so each case is graded on what its use NEEDS: the page's own
known facts in the extracted markdown. Harness `ledger_run.py` and `ledger_crawl.py`, results `ledger.json` and
`ledger_crawl.json` in the run folder `/opt/fabrik/.tmp/runs/5ce9d888-9344-466f-b905-652ac93cdf89/fabrik-spec-2026-10-21T16-07-23-0300/`.

| # | Use | URL | Path | Facts | Verdict |
|---|---|---|---|---|---|
| U1 | researcher re-fetch of static vendor docs | docs.python.org/3/library/bisect.html | static | 3/3 | PASS (0.4 s) |
| U2 | re-fetch of an API reference | docs.anthropic.com/en/api/messages | static | 3/3 | PASS (4.5 s) |
| U3 | rivals verify-stage pricing page | linear.app/pricing | static | 3/3 | PASS (0.7 s) |
| U4 | GitHub README fact check | github.com/browserless/browserless | static | 3/3 | PASS (0.9 s) |
| U5 | PDF paper | arxiv.org/pdf/1706.03762 | static | binary noise | FAIL — no PDF path (gap G1) |
| U6 | review site behind Turnstile | g2.com/products/linear/reviews | rendered, stealth | 0/2 | FAIL — bot wall (gap G4) |
| U7 | blog article | simonwillison.net/2024/Dec/31/llms-in-2024/ | static | 2/2 | PASS (1.4 s) |
| U8 | docs crawl, depth 2, 8 pages | docs.pydantic.dev/latest/concepts/models/ | static via doc-crawl | 8 pages, 103 KB | PASS, but drifted out of the subtree (gap G2) |

**6 of 8 uses are served today** (5 scrapes and the crawl); the PDF is a composition gap, the Turnstile wall is the one
case that genuinely needs a hosted service.

## fabrik-lib verdict (I7)

| Capability | Verdict | Module · why |
|---|---|---|
| fetch a page (static) | VENDOR | `web-scrape` `WebScraper.fetch_static` — U1-U4, U7 pass |
| render a JS page | VENDOR | `web-scrape` `fetch_rendered` over vps1 browserless |
| page → markdown | VENDOR | `doc-crawl` `html_to_markdown` (`strip_chrome` + render) |
| PDF → text | VENDOR | `pdf-extract` (pdfplumber native text) — G1 is composition, not a build |
| crawl a docs site | VENDOR + ENHANCE | `doc-crawl` `Crawler`; needs include/exclude path patterns (G2) and fetch-error reporting (G3) |
| agent-facing tool | BUILD — 🆕 fabrik-lib candidate | none exists (capability seat, part 4); `web-scrape-mcp` · an MCP server composing the three modules · every repo's seats and the hub's · tools `scrape`, `crawl` |
| bot-wall pages (Turnstile) | KEEP ON FIRECRAWL | defeating a control is the bypass line (Constraints); fallback only |
| LLM schema extraction, screenshots, page actions | KEEP ON FIRECRAWL | web-scrape's own scope excludes LLM extraction; the calling agent extracts from markdown |
| search | OUT of this spec | fabrik-lib has no search; the D-337 ladder stands |

## Chosen approach (A + runtime routing)

1. **A new MCP server, `fabrik-scrape`**, built as a fabrik-lib module (`web-scrape-mcp`, the candidate above) and
   registered on this box like `fabrik-citation-verifier` (FastMCP over streamable HTTP on 127.0.0.1, an `"type": "http"`
   entry in `scripts/sysadmin/mcp_defs.json`). Two tools:
   - `scrape(url, render="auto", max_length=20000, start_index=0, max_age_s=0)` → `{status, final_url, content_type,
     title, markdown, truncated, path: "static"|"rendered"|"pdf"}` — static first; rendered when the static page is a
     bot wall or its markdown is under a floor; PDF bytes go to pdf-extract. Chunked reading (`start_index`) as the MCP
     fetch server does. `max_age_s=0` is the live re-fetch the researcher's dispute rule needs.
   - `crawl(url, max_depth=2, max_pages=20, include_paths=[], exclude_paths=[])` → pages `{url, depth, title,
     markdown}` plus `errors`.
   - A page the server cannot read returns a typed result `{blocked: true, reason}`, never empty markdown — the signal
     the seat's fallback reads.
2. **Seats and commands** name `fabrik-scrape` first for scrape and crawl, with `firecrawl_scrape` / `firecrawl_crawl`
   as the fallback leg; search instructions are unchanged.
3. **Runtime code** (`web-tools` `web_scrape`/`web_crawl` and `a_firecrawl_scrape`'s callers, `rivals_run.py`'s
   verify-stage `scrape=`) calls web-scrape first and Firecrawl only on `blocked` — a fabrik-lib change, requested by
   mail, re-vendored into the hub and the projects by the usual sync.

## Fallback contract

| Own-tool result | Seat / runtime does |
|---|---|
| markdown with content | use it; cite URL + fetch date |
| `blocked: bot-wall` | call Firecrawl once if it has credits; else report the page unreadable — never a bypass tool |
| `blocked: unsupported` (schema extraction, screenshot, actions) | Firecrawl, or extract from the markdown itself |
| network or 5xx after retries | report it; Firecrawl only if the page is load-bearing for the claim |

## Rejected alternatives

| Alternative | Why not |
|---|---|
| **The official MCP fetch server** (`mcp-server-fetch`) as the own tool | static only: no browserless render, no crawl, no PDF; U2-style JS pages and U8 need the modules we already run. Its chunking and robots behaviour are copied into `scrape`. Source: `modelcontextprotocol/servers` `src/fetch/README.md`, fetched 2026-10-21 via `gh api` |
| **Crawl4AI** self-hosted | a new heavy dependency (Playwright/Chromium) that web-scrape's own scope rules out ("NOT `crawl4ai`, NOT `playwright`", `/opt/fabrik-lib/web-scrape/SPEC.md`:193); v0.9.5, Apache-2.0, `gh release list -R unclecode/crawl4ai`, 2026-10-21 |
| a Bash CLI script instead of an MCP server | `fabrik-researcher` has no Bash tool; the seats that need it most could not call it |
| Claude's built-in `WebFetch` | it returns a model summary, not the raw page the dispute rule needs (`/fabrik-spec` § 1a: "a `WebFetch` reply summarises") |
| top up Firecrawl | ruled out by the operator (D-1093) |
| `captcha-solve` / `proxy-pool` to beat U6 | the bypass line (Constraints) — a control is reported, never defeated |
| put the server in the hub, not fabrik-lib | every repo's seats need it; fabrik-lib is where shared modules live (vendor-don't-import) |

## Constraints Digest

| Quote | Source |
|---|---|
| A worker, Beat job or webhook receiver cannot call one. | `.windsurf/rules/core/57-external-data-sourcing.md:56` |
| A fabrik-lib module — vendor, don't hand-roll: | `.windsurf/rules/core/57-external-data-sourcing.md:69` |
| Check the roster before naming one — do not cite from memory | `.windsurf/rules/core/57-external-data-sourcing.md:66` |
| THE BYPASS LINE IS THE LEGAL LINE, and it runs straight through our own toolbox. | `.windsurf/rules/core/57-external-data-sourcing.md:258` |
| exa and firecrawl are METERED: | `CLAUDE.md:306` |

Further: D-013 keeps `firecrawl` in every repo's MCP roster (this spec keeps it, as the fallback); D-337/D-338/D-845 keep
the search ladder unchanged; D-1093 forbids a top-up.

## External dependencies

| Dependency | Grounded fact | Source, date |
|---|---|---|
| Firecrawl credit API | `remaining_credits: -6`, `plan_credits: 5000`, period end 2026-11-12 | `GET https://api.firecrawl.dev/v1/team/credit-usage`, executed 2026-10-21 |
| MCP Python SDK | latest release v2.3.0 (2026-10-02); FastMCP is the precedent server's base (`/opt/fabrik-citation-verifier/mcp_server/server.py`) | `gh release list -R modelcontextprotocol/python-sdk`, 2026-10-21 |
| MCP fetch server | markdown, `max_length` default 5 000, `start_index`, robots obeyed for model requests, private addresses refused | https://github.com/modelcontextprotocol/servers/blob/main/src/fetch/README.md, via `gh api`, 2026-10-21 |
| browserless v2 on vps1 | `/content` and `/function` used by web-scrape; credentials present (32-char token) | `/opt/fabrik-lib/web-scrape/README.md` and the executed U6 render, 2026-10-21 |

## fabrik-lib asks (I4 — small gaps, by mail to fabrik-lib)

| Gap | Ask | Test that proves it |
|---|---|---|
| G1 | web-scrape returns the content type (and bytes) so a PDF reaches pdf-extract | a PDF URL yields pdf-extract text |
| G2 | doc-crawl `include_paths` / `exclude_paths` patterns | U8 stays under `/latest/concepts/` |
| G3 | doc-crawl reports fetch errors instead of `except Exception: continue` | a failing fetcher yields an error row |
| G5 | web-scrape returns status, final URL and title beside the HTML | U1 reports 200 and the title |
| G6 | `ScopeError` exported as the README says; README test counts updated | an import test |

**Gaps kept on Firecrawl (large):** G4 Turnstile and similar bot walls; LLM schema extraction; screenshots; page actions.

## Lifecycle

- **Adoption:** the server ships with the five asks it needs most (G1-G3; G5-G6 can follow); the ledger re-runs (I5)
  and must hold 6/8 or better before any command text switches.
- **Growth:** rendered fetches load the single vps1 browserless container. Trigger: more than 20 rendered fetches a day,
  or a 5xx from browserless, raises the memory limit (gate W-cbd80821) before anything else.
- **Degradation:** browserless down → static fetches still work; the tool returns `blocked: render-unavailable` and the
  seat falls back. Server down → `mcp_health.py` reports it (FIX-FIRST) and seats use Firecrawl when it has credits.
- **Retirement:** if Firecrawl's fallback goes unused for a full billing period, the plan is downgraded or dropped (an
  operator spend decision); the server itself is retired only if a hosted tool replaces fabrik-lib's modules.

## Shape / infra implications

Not a scaffold project. One local MCP server process on the WSL box (supervised like `fabrik-citation-verifier`), one
`mcp_defs.json` entry, one port from `PORTS.md`. No VPS change; browserless on vps1 is reused.

## Documentation landing sites

`docs/reference/fabrik-scrape-mcp.md` (new, with its `INDEX.md` row) · `docs/workstation/mcp-roster.md` (the new
server) · `PORTS.md` (its port) · the module's own README in fabrik-lib · `CHANGELOG.md` · `docs/DECISIONS.md`.

## Residual unknowns

| Unknown | Why it is open | Resolution step |
|---|---|---|
| Firecrawl's output on U1-U8 | out of credits, so no side-by-side run; the ledger grades known facts instead | re-run the ledger with a Firecrawl column once credits return (2026-11-12) or on one paid call per case if the operator allows |
| browserless capacity under seat load | one 2G container on vps1; today's rendered volume is unmeasured | count rendered calls in the server for two weeks; the Lifecycle growth trigger applies |
| how often seats hit a bot wall | no call log exists for Firecrawl or the own tool | the server logs `blocked` results by reason; review after two weeks |

## Open items

- Placement — a fabrik-lib module (recommended) versus its own repo like citation-verifier: a review question.
- Mail at close: fleet — 40 projects vendor the retired `libs/subagents/web_tools.py` (D-132); operator gate — rotate
  the Firecrawl key (it is in several backups, by design).
- Size: not small (a new MCP server, fabrik-lib changes, ten command and contract surfaces) — the full chain.
