# Own scrape and crawl tools for agents and runtime, Firecrawl as fallback — design

Status: DRAFT
Owner: intel
Work item: W-10146d20 · governing decision D-1093

## Personas

| Persona | Who | What they need from this | Duty this spec gives them |
|---|---|---|---|
| **P1 — the operator** (primary) | Özgür, quoted in D-1093 | research that keeps working when a metered vendor runs dry, without paying for a top-up, and no breakage in commands that use it today | approves the spec gate, including the one departure from the work item (§ Fallback contract); clears a named bot-walled source for the Firecrawl fallback when one matters; approves the one `proxyUsed` test call and its page (slice 1d) |
| P2 — research seats | `fabrik-researcher` and the research seats that `/fabrik-spec`, `/fabrik-spec-review`, `/fabrik-plan-review`, `/fabrik-plan-after-chat`, `/fabrik-vision`, `/fabrik-data-contract` and `/fabrik-workflow-review` dispatch | a live, raw page read (the `maxAge:0` "settle a dispute" fetch) and a small docs crawl, as markdown | call `fabrik-scrape` first for a raw page; follow § Fallback contract on a `blocked` result |
| P3 — runtime code | `scripts/rivals_run.py` (the `/fabrik-rivals` engine: the hub plus 49 project copies on one hash, fabrik-lib's own copy on another), fabrik-lib `web-tools`, the deep-research and competitor-intel packs | a scrape leg that does not spend credits | call web-scrape first behind the `FABRIK_SCRAPE_LEG` switch (§ Chosen approach 3) |
| P4 — intel (this spec's builder) | the hub agent that owns W-10146d20 | a staged, revertible switch | write the per-command ledgers; edit the eight command sources, `fabrik-researcher.md`, the three contract copies' fetch sentence and the hub `rivals_run.py` (`tests/test_research_tier_order.py` is left unchanged); mail fabrik-lib the asks; run the slice-1d `proxyUsed` test once P1 approves it |
| P5 — fabrik-lib's agent | the module owner (a separate repo) | concrete requests, each with a test | build `web-scrape-mcp` and the asks G1-G12 in § fabrik-lib asks; change `web-tools` routing |
| P6 — infra | the beat for the MCP roster, `mcp_defs.json`, `emit_mcp_project_config.py` and box services | one new local MCP server registered beside `fabrik-citation-verifier` | register, supervise and health-probe the server |
| P7 — the coordinator | the hub merge owner | one slice per merge, each with its own full review | merge each slice; force the governance sync for synced paths |
| P8 — fleet | the beat for vps1 and its services | browserless on vps1 that cannot be steered into private ranges | in slice 1c, make vps1 browserless refuse requests to private and cloud-metadata ranges, proven by the redirect test (§ Shape) |

The operator, verbatim (D-1093): *"we need to find where we use firecrawl, test it against our modules, if we can
replace properly, we should, if not we need to enhance our modules if it is not too much for, and restest, then use our
tools, firecrawl can become a fallback."* Earlier the same day: *"dont we have fabrik-lib modules to do exact same as like
firecrawl?"* And, recorded in the work item: *"our commands actively uses it, so we must be very careful."*

**P2's loop, step budget 3:** (1) call `scrape(url)` on `fabrik-scrape`; (2) read the markdown, or act on the `blocked`
reason per § Fallback contract; (3) cite the URL and the fetch date. A page longer than one chunk adds one `scrape`
call per further chunk read (the long-page rule, § Chosen approach 2), capped by the plan; the three steps are the
budget for a page that fits in one. Every feature below traces to P2 or P3; the MCP
server exists because P2's seats have no shell (`fabrik-researcher` carries Read, Grep, Glob, WebFetch, WebSearch and
ToolSearch only, `commands/_agents/fabrik-researcher.md`:8-9).

## Intake Inventory

| I# | Item (anchored) | Disposition | Where |
|---|---|---|---|
| I1 | "find where we use firecrawl" | IN | § Inventory |
| I2 | "test it against our modules" | IN | § Test ledger |
| I3 | "if we can replace properly, we should" | IN | § Chosen approach |
| I4 | "if not we need to enhance our modules if it is not too much for" | IN | § fabrik-lib asks (small gaps) · § Kept on Firecrawl (large gaps) |
| I5 | "and restest" | IN | § Lifecycle — each command's ledger re-runs after the asks land |
| I6 | "then use our tools, firecrawl can become a fallback" | IN | § Chosen approach · § Fallback contract |
| I7 | "dont we have fabrik-lib modules to do exact same as like firecrawl?" | IN | § fabrik-lib verdict (scrape, render, PDF and crawl yes; search, LLM extraction, screenshots, page actions and bot walls no) |
| I8 | "the calls actually made this month by kind" | IN | § Inventory — counted from session transcripts |
| I9 | D-1093: no Firecrawl top-up | IN | § Constraints Digest |
| I10 | browserless memory raise 2G→3G (gate W-cbd80821) | OUT-OF-SCOPE | its own operator gate W-cbd80821; § Lifecycle names it as the growth trigger |
| I11 | the Brave key is revoked (gate W-12f21514) | OUT-OF-SCOPE | its own operator gate W-12f21514; search is not changed here |
| I12 | the vendored `libs/subagents/web_tools.py` calls Firecrawl scrape and crawl | IN (inventoried, not re-routed) | § Inventory; retired by fabrik-lib D-132 — its unfinished removal is reported in § Open items |
| I13 | the live Firecrawl key sits in `backups/*.env.backup*` | OUT-OF-SCOPE | by design (the gitignored pre-edit copies); key rotation is an operator credentials gate, § Open items |
| I14 | "we must be very careful": the switch is STAGED, one command at a time, never a cut-over | IN | § Lifecycle — rollout |
| I15 | a pass/fail ledger per capability AND per command, on the URLs that command hits; a command switches only when its ledger is all-pass, else it keeps Firecrawl | IN | § Test ledger · § Lifecycle |
| I16 | full `/fabrik-review` on every slice (the command sources are a governance-sync surface) | IN | § Lifecycle — rollout |

Intake: 16 items — 13 IN, 3 OUT-OF-SCOPE (each named), 0 ASK.

## Goal

Agents and runtime code read and crawl web pages through Fabrik's own infrastructure — fabrik-lib `web-scrape` (httpx
plus the vps1 browserless container), `doc-crawl` and `pdf-extract` — and reach Firecrawl only for what those modules
cannot do (LLM schema extraction, screenshots, page actions, an unavailable renderer) or for a bot-walled source the
operator has cleared by name.

## Why this exists

Firecrawl is the scrape leg of the research seats and of the runtime code, and it is metered. On 2026-10-21 the account
read `remaining_credits: -6`, `plan_credits: 5000`, period 2026-10-12 → 2026-11-12 (executed: `GET
https://api.firecrawl.dev/v1/team/credit-usage`; response kept as `fc_credits.out` in the run folder). The 5 000 credits
went in nine days. Every seat that names `firecrawl_scrape` — including the researcher's "settle a dispute" live fetch —
is dead for three weeks (a live call this session returned "Insufficient credits to perform this request."), and the
runtime scrape legs fail. The operator ruled no top-up (D-1093). fabrik-lib already fetches, renders, extracts PDFs and
crawls; nothing exposes it to the seats.

## Inventory (I1, I8, I12)

Measured by an Explore seat over the hub, fabrik-lib and every `/opt` project, 2026-10-21 (`inventory-seat.jsonl` in the
run folder), and corrected by review.

| Surface | Firecrawl capability used | Kind |
|---|---|---|
| `mcp.json`:16-20, `scripts/sysadmin/mcp_defs.json`:32-38, `scripts/sysadmin/emit_mcp_project_config.py`:43 | the MCP server itself | config |
| `commands/_agents/fabrik-researcher.md` (`mcpServers` line 4; scrape with `maxAge:0`; the long-page rule at :36-44 uses `formats: ["query"]` with `directQuote`, an LLM extraction; rules naming a Firecrawl credit error; the DEAD rule at :86 rests on a live Firecrawl 404) | scrape, LLM extraction | instruction |
| eight command sources: fabrik-spec, fabrik-spec-review, fabrik-plan-review, fabrik-plan-after-chat, fabrik-data-contract, fabrik-vision, fabrik-workflow-review, fabrik-rivals | search and scrape | instruction |
| the three contract copies' § External Knowledge (`CLAUDE.md`, `templates/governance/CLAUDE.md`, `/opt/fabrik-lib/CLAUDE.md`), `.windsurf/rules/core/57-external-data-sourcing.md`, `/opt/fabrik-lib/.windsurfrules`:54, the search chain held by `tests/test_research_tier_order.py` | tier-2 engine (D-337/D-338/D-845) | instruction |
| fabrik-lib `web-tools/web_tools.py`:421 (scrape), :439 (crawl), :772 (async search), :815 (async scrape); hub copy `libs/web_tools.py` | search, scrape, crawl | code |
| `scripts/rivals_run.py` (hub + 49 projects on one hash; fabrik-lib's copy on another): legs at :1169, verify-stage `scrape=a_firecrawl_scrape` at :1253 | search, scrape | code |
| `libs/subagents/web_tools.py`:227-247 in 39 projects and the hub (the hub copy frozen on purpose, D-547) | scrape, crawl | code, retired (fabrik-lib D-132) |
| `commands/assemble_commands.py`:467 (`mcp_servers=[…"firecrawl"…]` inside a POOL OFF block) | MCP grant for a pool seat | dormant config |
| deep-research and competitor-intel packs | search leg | config |
| `scripts/sysadmin/quota_dashboard.py`:377, `scripts/sysadmin/mcp_health.py`:159 | credit balance read (v1 endpoint) | code |

**Calls this month, by kind** (I8): session transcripts, `tool_use` blocks named `mcp__firecrawl__*` with an October
timestamp, de-duplicated by tool-use id (`fc_calls.py` over `fc_files.txt`, the 20 489 transcripts an `rg -l
mcp__firecrawl__` lists, of which 2 132 were modified since 2026-10-01 and read; output kept as `fc_calls.out`):
**192 calls — `firecrawl_scrape` 187, `firecrawl_search` 3, `firecrawl_map` 2**; 128 of them fall inside the billing
period (from 2026-10-12). Agent tool calls are therefore scrape almost entirely — but this count is not split by
`formats`, and the researcher's long-page rule asks for `formats: ["query"]`, an LLM extraction this spec keeps on
Firecrawl; only the markdown share is claimed as replaced, and the per-command ledgers count scrape calls by `formats`.
`firecrawl_crawl` was called 0 times. The calls are far too few to spend 5 000 credits, so most of the spend came from somewhere the transcripts do not
show — see § Residual unknowns.

## Test ledger (I2, I15) — fabrik-lib against each use, 2026-10-21

Firecrawl could not run side by side (out of credits), so each case is graded on what its use needs: page-specific
facts (exact phrases) in the extracted text, plus a clean-text ratio (letters, digits and spaces over all characters,
floor 0.6). Pass 2 replaced pass 1, whose facts were common words that markup noise could satisfy. Harness
`ledger2_run.py`, results `ledger2.json`, failing pages kept under `html/`, follow-up probes `inspect2.py` to
`inspect5.py` with their printed results in `probes.out` — all in the run folder
`/opt/fabrik/.tmp/runs/5ce9d888-9344-466f-b905-652ac93cdf89/fabrik-spec-2026-10-21T16-07-23-0300/`. Escalation in pass 2
is a plain browserless `/content` render, never stealth.

| # | Use | URL | Path | Facts · clean | Graded | Judgement after inspection |
|---|---|---|---|---|---|---|
| U1 | re-fetch of static vendor docs | docs.python.org/3/library/bisect.html | static | 2/3 · 0.83 | PARTIAL | PASS — the missed fact is present as `key = None` (the converter spaces the signature); the fact string was wrong |
| U2 | re-fetch of an API reference | platform.claude.com/docs/en/api/messages (301 from docs.anthropic.com) | static | 1/3 · 0.89 | PARTIAL | FAIL as built, fixed by design — the site sends a reduced HTML page (7.46 MB, 107 KB of text, no "Body parameters") and a plain render gives the same text; asked with `Accept: text/markdown` or at the `.md` URL it returns the full 1.2 MB reference (`anthropic-version` ×16, `stop_sequences` ×9). The converter lost nothing; the request did. Ask G10 |
| U3 | rivals verify-stage pricing page | linear.app/pricing | static | 4/4 · 0.92 | PASS | PASS |
| U4 | GitHub README fact check | github.com/browserless/browserless | static | 1/2 · 0.88 | PARTIAL | PASS — the README text is all there (`docker run`, `ghcr.io/browserless` ×3); "TOKEN" is not in that README |
| U5 | PDF paper | arxiv.org/pdf/1706.03762 | PDF bytes → pdf-extract | 2/3 · 0.92 | PARTIAL | PARTIAL — 35 525 chars extracted, but some lines lose their word spaces ("AshishVaswani"); gap G8 |
| U6 | review site behind a DataDome interstitial (`captcha-delivery.com/interstitial`) | g2.com/products/linear/reviews | static (403, 1.7 KB) → plain render (2.6 KB); the server would stop at the 403 page as `bot-wall` | 0/2 · 0.0 | FAIL | FAIL, as it should — the page is a `captcha-delivery.com` (DataDome) interstitial with 0 chars of text; `is_bot_wall` has no DataDome marker, so it did not say so (ask G11) |
| U7 | blog article | simonwillison.net/2024/Dec/31/llms-in-2024/ | static | 2/2 · 0.95 | PASS | PASS |
| U8 | docs crawl, depth 2, cap 8 pages | docs.pydantic.dev/latest/concepts/models/ | doc-crawl over static | 1 of 8 pages in the subtree | PARTIAL | PARTIAL — the crawl seeds the whole origin's sitemap and follows nav links first, so 7 of 8 pages left `/latest/concepts/`; gap G2 |

**Served today: U1, U3, U4, U7** (static scrape). PDF and crawl work but need G8 and G2; U2 needs G10 (ask for
markdown first); U6 is a page our tools must report, not read. The rendered path executed (U2's render returned a 7.45 MB
DOM, `probes.out`; U6 2.6 KB) but has no passing case yet. These cases stand for capabilities; the switch itself is gated
per command (§ Lifecycle). U2's "not on the page" reading was wrong until a second request method (the markdown
request) was tried; U1 and U4 were checked only against the same fetch's raw HTML, and their fact strings were reworded
after the run. Every ledger from here on fixes its fact strings BEFORE the run, from an independent read of the page (a
browser or `WebFetch`) recorded beside them; no fact string is edited after the run — a missed fact the independent read
shows on the page is a FAIL of the tool, one it shows absent is struck with that read cited.

## fabrik-lib verdict (I7)

| Capability | Verdict | Module · why |
|---|---|---|
| fetch a page (static) | VENDOR + ENHANCE | `web-scrape` `WebScraper.fetch_static` — U1, U3, U4, U7; G5 (status, title), G10 (ask for markdown first), G11 (DataDome marker) |
| render a JS page | VENDOR — no passing case yet | `web-scrape` `fetch_rendered` over vps1 browserless `/content`; the stealth `/function` path is never used |
| page → markdown | VENDOR | `doc-crawl` `html_to_markdown` |
| PDF → text | VENDOR + ENHANCE | `pdf-extract`; G1 (bytes reach it) is composition, G8 (word spacing) is an ask; image-only pages go to `ocr` or return `blocked: unsupported` |
| crawl a docs site | VENDOR + ENHANCE | `doc-crawl` `Crawler`; G2 (scoping), G3 (errors), G9 (title) |
| agent-facing tool | BUILD — 🆕 fabrik-lib module | none exists; `web-scrape-mcp` · an MCP server composing the three modules · every repo's seats · tools `scrape`, `crawl` |
| bot-walled pages | NOT SERVED | defeating a control crosses the bypass line; reported, or Firecrawl for a source the operator clears by name |
| LLM schema extraction, screenshots, page actions | KEEP ON FIRECRAWL | web-scrape's scope excludes LLM extraction (`/opt/fabrik-lib/web-scrape/SPEC.md`:16); the calling agent extracts from markdown |
| search | UNCHANGED | fabrik-lib has no search; the D-337 ladder's search engines stand |

## Chosen approach (A + runtime routing)

1. **A new MCP server, `fabrik-scrape`**, built by fabrik-lib as the module `web-scrape-mcp`, vendored into the hub and
   registered on this box like `fabrik-citation-verifier` (streamable HTTP on 127.0.0.1, a `"type": "http"` entry in
   `scripts/sysadmin/mcp_defs.json`, a port from `PORTS.md`). It runs on the current SDK line, `mcp>=2.3,<3`, whose
   server class is `MCPServer` (v2 renamed `FastMCP`), in its own venv. Two tools:
   - `scrape(url, render="auto"|"always"|"never", max_length=20000, start_index=0, max_age_s=0)` →
     `{status, final_url, content_type, title, markdown, truncated, short, path, fetched_at}` with `path` one of
     markdown, static, rendered, pdf, and `fetched_at` the UTC time of the fetch (ISO 8601) that P2 cites.
     The first request asks for markdown (`Accept: text/markdown, text/html;q=0.9`); a site that answers with
     `text/markdown` is used as-is, because some docs sites serve their full reference that way and a reduced page as
     HTML (measured: platform.claude.com, U2). Otherwise static HTML, converted. `auto` renders through plain browserless `/content` when an
     HTML page's text is under 800 characters; `always` forces a render; `never` returns the static result as it is.
     The 800-character test applies to HTML only — plain text, JSON, XML and markdown responses are returned whatever
     their length. The stealth path is never called. A PDF content type goes to pdf-extract. `start_index` reads a long
     page in chunks. `max_age_s=0` is the live re-fetch the researcher's dispute rule needs. A short result is returned
     with `short: true`, not refused.
   - **Rendering is off until it is proven safe.** Until a redirect from a public URL to a private or cloud-metadata
     address, sent through vps1 browserless, is shown refused, and one rendered case grades PASS, `render="always"`
     returns `blocked: render-unavailable` and `auto` does not render: a short HTML page is returned as fetched with
     `short: true` (§ Lifecycle, slice 1c). Once on, the number of renders in
     flight at once is bounded (one 2G container also serves other callers); a render that cannot start within a short
     wait returns `blocked: render-unavailable`, and the server counts renders per day and per minute. A rendered body
     whose final navigation host resolves to a non-public address is discarded as `blocked: scope`; an ordinary public
     redirect (apex to www, or `docs.anthropic.com` to `platform.claude.com`, U2) is not.
   - `crawl(url, max_depth=2, max_pages=20, include_paths=[], exclude_paths=[], use_sitemap=False)` → pages
     `{url, depth, title, markdown}` plus `errors`; by default only pages under the start URL's path.
   - **Never empty markdown.** A page the server cannot read returns `{blocked: true, reason, status}` — `status` the
     HTTP status it came from, null for a reason with none (`robots`, `scope`, `render-unavailable`) — with `reason` one of:
     `robots` (refused by robots.txt), `scope` (a non-public address — below), `http-<status>` (any 4xx or 5xx after
     retries; a 429 is retried after its `Retry-After` when that is at most 30 s, else reported at once as `http-429` — G12), `bot-wall` (`is_bot_wall` true — with G11 that covers DataDome, U6's case),
     `empty` (under 50 characters of text after every attempt), `render-unavailable` (browserless unreachable),
     `unsupported` (an image-only PDF, a content type it cannot read).
   - **The wall check runs on every body the server sees** — the static page before any render, and any 4xx or 5xx
     body (`FetchError.body` for a 5xx) before its status is reported — so a wall is `bot-wall` whatever status it
     answers with (U6 answers the static request with 403, a DataDome page and an `x-datadome` header,
     `inspect6.py`), and one met when browserless is down is not mistaken for a transient error. A 4xx (except 429)
     or 5xx whose body is not a known wall but holds under 50 characters of text, or no HTML, is returned as
     `blocked: empty`, not `http-<status>` — the seat cannot see the body, so the server classifies it. A 404 or 410
     is always `http-404` / `http-410` whatever its body — unless the body is a known wall, which stays `bot-wall` (a
     raw-file 404 is the 14-byte "404: Not Found", measured on raw.githubusercontent.com, `raw404.py` → `probes.out`), and
     every `blocked` result carries the HTTP `status` it came from, so the researcher's DEAD rule keys on the status.
   - **Address guard on every hop.** Before each request and each redirect hop the server refuses loopback, private,
     link-local and cloud-metadata addresses (`blocked: scope`), as the MCP fetch server does by default. It passes
     fabrik-lib's `_SsrfSafeTransport` pattern as `WebScraper(transport=…)` (`/opt/fabrik-lib/web-scrape/README.md`,
     section on the address guard); a render is sent only for a URL that passed that check. A model-driven fetch on
     this box would otherwise reach the box's own local services, which a hosted Firecrawl never could.
2. **Seats and commands.** `fabrik-scrape` is the raw-page fetch, named only in a command's or the researcher's
   raw-fetch sentence, beside `WebFetch` (which summarises). It is a fetch, not a search engine: it never enters the
   search chain `tests/test_research_tier_order.py` grades, whose closed tier-1 set (`_TIER1`, :22) is not widened; the
   ladder's ORDER and its search engines are unchanged, and `firecrawl` stays in tier 2 for structured extraction and
   the fallback rows below. The three contract copies gain `fabrik-scrape` in the fetch sentence of § External
   Knowledge. `fabrik-researcher.md` gets `fabrik-scrape` in `mcpServers`, and:
   - its raw-fetch order becomes `fabrik-scrape` → `exa` `web_fetch_exa` → `firecrawl_scrape`;
   - its long-page rule (:36-44) reads the page through `scrape(url, start_index=…)` chunk by chunk until the
     locator's heading or symbol is found and compares the span there, naming the chunk offset in its verdict; a
     Firecrawl `formats: ["query"]` call is kept only for a page too long to page through, and only while the Firecrawl
     rows are open (§ Fallback contract);
   - its DEAD rule (:86) takes `blocked: http-404` from `fabrik-scrape` as the live 404 it needs;
   - its rules that turn a Firecrawl credit error into NEEDS-RAW-FETCH are re-pointed at the new order.
   Every command or seat line that names `firecrawl_scrape` or `firecrawl_crawl` passes `proxy: "basic"` (the
   installed `firecrawl-mcp` v3.24.0 schema accepts it for scrape and for crawl's `scrapeOptions`) — in slice 1a, for
   every such line, whether or not its command has switched yet.
3. **Runtime code.** fabrik-lib `web-tools` (`web_scrape`, `web_crawl`, `a_firecrawl_scrape`'s role) and the hub
   `rivals_run.py` verify-stage `scrape=` call web-scrape first and Firecrawl only per § Fallback contract, behind an
   environment switch `FABRIK_SCRAPE_LEG=own|firecrawl` whose default stays `firecrawl` until that caller's ledger is
   all-pass. The change lands in `web-tools`, not in `web-scrape`, whose scope forbids a managed scraping service
   (`/opt/fabrik-lib/web-scrape/SPEC.md`:17).

## Fallback contract

| Own-tool result | Seat / runtime does |
|---|---|
| markdown with content | use it; cite URL and fetch date |
| `blocked: robots` | report the page unreadable — never any other fetcher this session, `WebFetch` and exa included (another user agent would evade the site's robots group) |
| `blocked: scope` | report it — never fetched by anyone |
| `blocked: http-4xx` (except 429; a near-empty one arrives as `empty`) | report the page unreadable; an error page is never cited as content |
| `blocked: http-429` (after the server honoured a `Retry-After` of at most 30 s, or at once when it asks for longer) | report the page rate-limited — never exa or Firecrawl (rule 57's bypass line names evading a hard rate limit) |
| `blocked: http-5xx` (a near-empty one arrives as `empty`), `blocked: render-unavailable` | `exa` `web_fetch_exa`; else Firecrawl if it has credits and its rows are open (below); else report it |
| `blocked: empty` | `exa` `web_fetch_exa`; else report it — never Firecrawl, because the one empty page measured was an unrecognised bot wall (U6), a wall vendor `is_bot_wall` does not know reads as `empty`, and the only thing keeping Firecrawl off its escalating default is a parameter its docs mark deprecated (below) — a probable wall is not trusted to it |
| `blocked: bot-wall` | report the page unreadable and cite another source. Firecrawl is called on such a page only for a source the operator has cleared by name, recorded in the plan or work item (rule 57's bypass line: a pipeline that defeats a control leaves public-data territory, and handing the page to a vendor that does so is the same act) |
| `blocked: unsupported` (image-only PDF, unreadable content type) | Firecrawl if it has credits and its rows are open (below), or report it |
| a need the tool has no parameter for (LLM schema extraction, screenshot, page actions) | extract from the markdown, or call Firecrawl directly while its rows are open (below) |

**Why Firecrawl and not exa is the line.** Rule 57 names the tooling layer — anti-bot bypass and proxy services — not
every other fetcher. Firecrawl's default proxy mode is `auto`, which "will automatically retry scraping with enhanced
proxies if the basic proxy fails" (https://docs.firecrawl.dev/features/proxies, 2026-10-21): sending it a blocked page
asks it to rotate past the block. So **every Firecrawl call this design makes passes `proxy: "basic"`** — still a
documented mode, though the page marks the `proxy` parameter deprecated; if the API stops accepting it, every Firecrawl
row above shrinks to operator-cleared sources only. A deprecated parameter is more often accepted and ignored than
refused, so the silent case is guarded too: every Firecrawl fallback response is checked for the proxy mode the vendor
reports having used, and a response reporting another mode, or none, is discarded and the page reported unreadable. The
field is `data.metadata.proxyUsed` (`"basic" | "stealth"`), present in Firecrawl's source
(`apps/api/src/scraper/scrapeURL/index.ts`, added by PR #1551) but absent from its API reference. It defaults to
`"basic"` when the engine reports nothing and is backfilled on cached hits, so `"basic"` is necessary, not sufficient.
The Firecrawl rows therefore stay closed to operator-cleared sources until a test shows the field reaching a seat
through `firecrawl-mcp` and reporting `stealth` when `proxy: "stealth"` is set explicitly on a public page that is not
walled — never by sending a walled page in `auto` mode, which is the act this paragraph forbids. A stealth call is the
tooling layer rule 57 reserves for an operator's decision, so P1 approves that one call and its page by name first. The
test needs credits, so it runs after 2026-11-12 (§ Lifecycle, slice 1d). **"The Firecrawl rows are open"** means exactly that: credits exist and this test has
passed. It gates every Firecrawl entry point in this design — the fallback rows, the researcher's long-page `query`
call and a direct Firecrawl call for a need the tool lacks. exa's `web_fetch_exa` and `WebFetch` are ordinary fetches with no
documented escalation, so they may read an `empty` page or stand in while the server is down; a page known to be a wall
goes to neither. exa answers from its cache by default ("instant results from our cache, with automatic live crawling as
fallback", https://exa.ai/docs/reference/get-contents, 2026-10-21) and the `web_fetch_exa` tool cannot ask for a live
read, so a page read through exa is cited as exa's cached copy — never as the live re-fetch the dispute rule needs.

**A departure from the work item, surfaced for the spec gate.** The work item says "a failed own-tool call falls
through to it, never to a miss"; this contract does not fall through to Firecrawl on `bot-wall`, `robots`, `scope`,
`http-429`, a non-429 `http-4xx` or `empty`. The rule that
governs it, CLAUDE.md § Behavior: "**Conflict resolution:** rule pack > ticket (for HOW to write). … Surface any conflict
before proceeding." The bypass line is a rule pack, so this spec follows it and surfaces the conflict: P1 approves or
overrules it at the spec gate, and the closing D-row records which.

**A second departure, surfaced the same way.** The work item asks to switch each command "behind a flag that defaults to
the old path until that command's ledger is all-pass". Command text has no runtime flag, so this spec meets the intent
by changing a command's text only after its ledger is all-pass, with reverting that slice's commit as the off switch;
runtime code keeps a real flag (`FABRIK_SCRAPE_LEG`).

## Rejected alternatives

| Alternative | Why not |
|---|---|
| **The official MCP fetch server** (`mcp-server-fetch`) as the own tool | one `fetch` tool (url, `max_length`, `start_index`, `raw`): no crawl, no PDF, no browserless render. Its chunking, robots and private-address defaults are copied into `scrape`. Source: https://github.com/modelcontextprotocol/servers/blob/main/src/fetch/README.md, 2026-10-21 |
| **Crawl4AI** self-hosted | a heavy new dependency (Playwright and Chromium) that web-scrape's scope rules out (`/opt/fabrik-lib/web-scrape/SPEC.md`:193: "NOT `crawl4ai`, NOT `playwright`"); v0.9.5, Apache-2.0, `gh release list -R unclecode/crawl4ai`, 2026-10-21 |
| a Bash CLI script instead of an MCP server | `fabrik-researcher` has no Bash; the seats that need it most could not call it |
| Claude's built-in `WebFetch` as the raw fetch | it returns a small model's answer about the page, not the page; the dispute rule needs raw text |
| `exa` `web_fetch_exa` as the only raw fetch | metered like Firecrawl, so the same outage recurs; kept as the second leg |
| fabrik-lib `adaptive-dispatch` to choose static or render per domain | it learns from history the server does not have yet; the 800-character floor plus `render="always"` is enough to start, and adaptive-dispatch can replace the floor later without changing the tool contract |
| one cut-over of every command | refused by the operator's caution (I14); each command switches alone |
| top up Firecrawl | ruled out by the operator (D-1093) |
| stealth rendering, `captcha-solve` or `proxy-pool` to read U6 | the bypass line — a control is reported, never defeated |
| the server inside the hub instead of fabrik-lib | every repo's seats need it, and shared modules live in fabrik-lib (vendor, don't import) |

## Constraints Digest

Quotes are verbatim with markdown emphasis removed.

| Quote | Source |
|---|---|
| A worker, Beat job or webhook receiver cannot call one. | `.windsurf/rules/core/57-external-data-sourcing.md:56-57` |
| A fabrik-lib module — vendor, don't hand-roll: | `.windsurf/rules/core/57-external-data-sourcing.md:69` |
| Check the roster before naming one — do not cite from memory | `.windsurf/rules/core/57-external-data-sourcing.md:66` |
| THE BYPASS LINE IS THE LEGAL LINE, and it runs straight through our own toolbox. | `.windsurf/rules/core/57-external-data-sourcing.md:258` |
| exa and firecrawl are METERED: | `CLAUDE.md:306` |

Further: D-013 keeps `firecrawl` in every repo's MCP roster (kept, as the fallback). D-337/D-338/D-845 fix the research
ladder's order and engines; this spec keeps both and adds `fabrik-scrape` only as a raw-page fetch in the three
contract copies' fetch sentence — outside the search chain `tests/test_research_tier_order.py` grades. D-1093 forbids a
top-up.

## External dependencies

| Dependency | Grounded fact | Source, date |
|---|---|---|
| Firecrawl credit API | v1 fields `remaining_credits`, `plan_credits`, `billing_period_start`, `billing_period_end`; read: -6, 5000, 2026-10-12 → 2026-11-12. v2 renames them camelCase (`remainingCredits`, …) at `/v2/team/credit-usage`; `fc_credits.py`, `quota_dashboard.py` and `mcp_health.py` call v1 | https://docs.firecrawl.dev/api-reference/v1-endpoint/credit-usage and https://docs.firecrawl.dev/api-reference/endpoint/credit-usage; call executed 2026-10-21 |
| MCP Python SDK | latest v2.3.0 (2026-10-02); v2 renames `FastMCP` to `MCPServer` and moves transport options off the constructor; the precedent `fabrik-citation-verifier` runs v1.27.0 with `FastMCP` | `gh release list -R modelcontextprotocol/python-sdk`; https://github.com/modelcontextprotocol/python-sdk/blob/main/docs/migration.md; 2026-10-21 |
| MCP fetch server | markdown output, `max_length` default 5 000, `start_index`, robots obeyed for model requests, non-public addresses refused by default | https://github.com/modelcontextprotocol/servers/blob/main/src/fetch/README.md, 2026-10-21 |
| Firecrawl proxy modes | default `auto` "will automatically retry scraping with enhanced proxies if the basic proxy fails"; `proxy` parameter deprecated in favour of `auto` | https://docs.firecrawl.dev/features/proxies (fetched as `text/markdown`), 2026-10-21 |
| browserless v2 on vps1 | `POST /content` (token query parameter) renders a page; `/function` runs a script (the stealth path, not used) | https://docs.browserless.io/rest-apis/content; executed renders U2 and U6, 2026-10-21 |

## fabrik-lib asks (I4 — small gaps, by mail to fabrik-lib)

| Gap | Ask | Test that proves it |
|---|---|---|
| — | build `web-scrape-mcp` to § Chosen approach 1's tool contract, `blocked` reasons and address guard | a contract test per tool and per `blocked` reason |
| G1 | web-scrape returns the content type and bytes, so a PDF reaches pdf-extract | U5's URL yields pdf-extract text through `scrape` |
| G2 | doc-crawl include/exclude path patterns applied to sitemap seeds AND links, and `use_sitemap=False` | U8 stays under `/latest/concepts/` |
| G3 | doc-crawl reports fetch errors instead of `except Exception: continue` | a failing fetcher yields an error row |
| G5 | web-scrape returns status, final URL, title and the response headers beside the HTML (G11's `x-datadome` signal needs the headers) | a 404 URL reports 404; U1 reports 200 and its title; U6's static fetch exposes `x-datadome` |
| G6 | `ScopeError` exported from the package `__init__` as the README says | an import test |
| G7 | web-scrape ships the non-public-address transport (today a pattern in watchdog) for `transport=` | a 127.0.0.1 URL and a redirect to 169.254.169.254 both raise |
| G8 | pdf-extract keeps word spaces (pdfplumber tolerance) | U5 contains "Ashish Vaswani" |
| G9 | doc-crawl `DocPage` carries the page title | U8 pages have titles |
| G10 | web-scrape gains an OPT-IN `accept_markdown=False` parameter: when True it sends `Accept: text/markdown, text/html;q=0.9`, returns a `text/markdown` answer as-is, and puts the Accept value in the cache key (`_cache_key` hashes only url, method and body today, `webscrape.py`:495). `_do_request` takes no headers today (`self._client.get(url)`, `webscrape.py`:474), so per-request headers are threaded through `fetch_static`, the retry loop and `_do_request`. Only `web-scrape-mcp` passes True, so callers that parse HTML (`__NEXT_DATA__`, the module's purpose) are unchanged | U2 yields `anthropic-version` and `stop_sequences` with the flag; a mock transport asserts the Accept header sent; the same URL without the flag still returns HTML from a separate cache entry |
| G11 | `is_bot_wall` recognises DataDome (`captcha-delivery.com` in the body) beside its Cloudflare markers, and the server also treats an `x-datadome` response header as a wall signal | U6's static 403 (`html/U6-static.html`) returns `blocked: bot-wall` without a render |
| G12 | web-scrape honours a 429's `Retry-After` (delay-seconds or HTTP-date, RFC 9110 §10.2.3; a 429 may carry it, RFC 6585 §4) instead of its fixed 1/2/4 s backoff (`webscrape.py`:454-465 never reads headers): one wait of at most 30 s, at most 60 s of waiting per call in total; a longer ask raises `FetchError(status=429)` at once | `Retry-After: 2` waits at least 2 s before the retry; an HTTP-date 2 s ahead does the same; `Retry-After: 3600` raises immediately with status 429; three 429s in a row stop at the 60 s total |
| — | web-tools routes scrape and crawl to web-scrape first behind `FABRIK_SCRAPE_LEG` (§ Chosen approach 3), and every Firecrawl `scrape`/`crawl` payload it builds — sync and async (`web_tools.py`:424 builds `{"url", "formats"}` with no `proxy` today) — carries `proxy: "basic"`; the hub's `rivals_run.py` calls the same functions (P4 re-vendors) | a test per fallback row; a mock transport asserts `proxy: "basic"` in every Firecrawl payload; each Firecrawl call web-tools makes logs its caller and URL |

### Kept on Firecrawl (large gaps)

Bot-walled pages (and only for operator-cleared sources); LLM schema extraction; screenshots; page actions.

## Lifecycle

- **Rollout (I14-I16), sized to the operator's "address only urgent items".** The urgent loss is the seats' raw-page
  read (187 of 192 October calls were `firecrawl_scrape`, 0 were `firecrawl_crawl`), so slice 1 carries only that:
  - **Slice 1a** — fabrik-lib ships `web-scrape-mcp` with the `scrape` tool only, static and markdown paths, rendering
    off, on G5, G6, G7, G10 and G11; infra registers it; every command or seat line naming a Firecrawl tool gains
    `proxy: "basic"`; web-tools gains its per-call caller-and-URL log (the rest of the web-tools ask follows each
    caller's switch); the capability ledger re-runs THROUGH `scrape` with fact strings fixed before the run (§ Test
    ledger) and must grade PASS on U1, U2, U3, U4 and U7, with U6 returning `blocked: bot-wall` and U5 returning
    `blocked: unsupported` until 1b. Then `fabrik-researcher` switches (its own ledger first, as for every command).
  - **Slice 1b** — the `crawl` tool and G1, G2, G3, G8, G9 and G12, gated on U5 containing "Ashish Vaswani" and U8 keeping
    every page under its start path. Nothing in 1b blocks a seat switch.
  - **Slice 1c** — rendering turns on only after a redirect from a public URL to a private or cloud-metadata address,
    sent through vps1 browserless, is shown refused, and one rendered case grades PASS (§ Shape names the vps1 change).
  - **Slice 1d** — after the 2026-11-12 reset, P4 runs the one `proxyUsed` test P1 approved (§ Fallback contract);
    only its pass opens the Firecrawl rows. Until then every Firecrawl entry point stays closed to operator-cleared
    sources.
  Then one command per slice: intel builds that command's ledger from the URLs its runs actually fetched (from transcripts), switches the
  command's text only when that ledger is all-pass, and runs the full `/fabrik-review` on the slice. Command text has no
  runtime flag, so a slice is one commit and reverting it is the off switch; runtime code uses `FABRIK_SCRAPE_LEG`. A
  command whose ledger is not all-pass keeps Firecrawl. `/fabrik-rivals` and `fabrik-researcher` go first (they make the
  scrape calls).
- **Growth:** rendered fetches load the single vps1 browserless container. Trigger: more than 20 rendered fetches a day,
  or any browserless 5xx, raises the memory limit (gate W-cbd80821) before anything else.
- **Degradation:** browserless down → static fetches still work and renders return `blocked: render-unavailable`.
  Server down → `mcp_health.py` reports it (FIX-FIRST) and seats use `exa` (cited as exa's cached copy, never a live
  re-fetch); Firecrawl only for a source the operator has cleared, because without the server nothing classifies a
  page, so a wall cannot be told from an outage.
- **Retirement:** if the Firecrawl fallback goes unused for a full billing period, the plan is downgraded or dropped (an
  operator spend decision). The server is retired only if a hosted tool replaces fabrik-lib's modules.

## Shape / infra implications

Not a scaffold project. One local MCP server process on the WSL box (supervised like `fabrik-citation-verifier`), one
`mcp_defs.json` entry, one port from `PORTS.md`. One VPS change, in slice 1c only: vps1 browserless refuses requests
to private and cloud-metadata ranges in its own request handling (browserless follows redirects server-side, beyond
the box-side guard, `/opt/fabrik-lib/web-scrape/README.md` "Not covered" section). Until that change is verified,
rendering stays off.

## Documentation landing sites

`docs/reference/fabrik-scrape-mcp.md` (new, with its `INDEX.md` row) · `docs/workstation/mcp-roster.md` (the server) ·
`PORTS.md` (its MCP endpoint's port; the precedent's row lists 8032 while its endpoint is `:8033/mcp`, an infra note) · the three contract copies' § External Knowledge · `.windsurf/rules/core/57-external-data-sourcing.md`
(the agent-time roster) · the module's README in fabrik-lib · `CHANGELOG.md` · `docs/DECISIONS.md`.

## Residual unknowns

| Unknown | Why it is open | Resolution step |
|---|---|---|
| what spent the 5 000 credits | transcripts show 128 agent calls in the period, far too few; runtime callers (rivals_run, web-tools users, other repos sharing the key) leave no log | before 2026-11-12, when the period resets and the same spend can repeat: the operator reads Firecrawl's activity log — the only record of calls already made. The web-tools caller-and-URL log (§ fabrik-lib asks) ships in slice 1a so the next period is attributable. If the spend is not agent or runtime calls, the key-rotation gate (§ Open items) is raised as urgent. The answer decides which caller switches first |
| Firecrawl's output on the same URLs | out of credits, so no side-by-side run | re-run the capability ledger with a Firecrawl column after 2026-11-12 |
| the bot-wall detector's precision | `is_bot_wall` knew only Cloudflare and missed U6 (DataDome); other vendors may follow | the server logs `blocked` reasons and short results; review them after two weeks |
| how exa's crawler behaves on a bot wall | exa documents no proxy escalation, but its live crawl is opaque (an error names `CRAWL_LIVECRAWL_TIMEOUT`) | the seat records each `empty` → exa outcome in its research ledger (URL, text length); if exa returns content for a page later classified `bot-wall` (after G11 or a new marker), exa is dropped from the `empty` row. P4 (intel) reviews the records after two weeks |
| how many sites serve markdown on request | measured on one site (U2) | the server logs which path answered; the per-command ledgers show it |
| browserless capacity under seat load | one 2G container; rendered volume unmeasured | the server counts renders; the Lifecycle trigger applies |
| the address guard's reach inside browserless | browserless follows redirects on vps1, beyond the box-side check | rendering stays off until the vps1 change in § Shape is verified by a redirect test (slice 1c) |
| robots on the rendered path | robots is checked for web-scrape's user agent, but browserless renders with its own Chrome UA (`webscrape.py`:309-310) | slice 1c checks robots for both user agents, or sends browserless an object `userAgent` |
| whether `proxyUsed` reaches the seat through the MCP, and how far a `"basic"` report can be trusted | the field is undocumented, defaults to `"basic"` and is backfilled on cached hits; `firecrawl-mcp` v3.24.0 does not name it | after 2026-11-12 (it needs credits): the field reaches a seat, and an explicit `proxy: "stealth"` call on a public, unwalled page reports `stealth`; until then the Firecrawl rows are closed to operator-cleared sources (§ Fallback contract) |
| image-only PDFs | pdf-extract yields no text for scanned pages | `blocked: unsupported` until an `ocr` route is asked for |

## Open items

- Report to fabrik-lib that its D-132 removal is unfinished: 39 projects still carry `libs/subagents/web_tools.py`
  past the 2026-09-14 acknowledgement date (the hub copy stays, frozen by D-547).
- Operator gate, outside this spec: rotate the Firecrawl key (it sits in several backups, by design).
- Operator gate, not tested or used: Firecrawl's docs say "No API key needed to get started", which suggests a keyless,
  rate-limited tier. Switching to it while the keyed team is at −6 credits would be using another identity to get past
  a cap the vendor set — rule 57's field 4 makes that "an operator decision with the ToS quoted — never an engineering
  convenience" (`.windsurf/rules/core/57-external-data-sourcing.md`:129-133), and D-1093 rules "no Firecrawl top-up".
  Nothing in this design calls it.
- Size: not small (a new MCP server, fabrik-lib changes, ten command and contract surfaces) — the full chain.
