# Plan 3 — own scrape tool, slice 1a (hub side)

Status: DRAFT
Profile: small
**Owner:** intel
Spec: `docs/superpowers/specs/2026-10-21-own-scrape-tools-design.md` (CONVERGED, approved D-1100) · Work item: W-10146d20

## Goal

Deliver the hub side of the spec's slice 1a (spec § Lifecycle, "Slice 1a"): every Firecrawl tool line in the command
and agent sources pins `proxy: "basic"`; the `fabrik-scrape` MCP server fabrik-lib builds is vendored, run and
registered on this box; and `fabrik-researcher` switches its raw-page fetch to it once its own ledger is all-pass.

## What we already agreed

- The own tool is an MCP server, `fabrik-scrape`, built by fabrik-lib as `web-scrape-mcp` and vendored into the hub —
  spec § Chosen approach, item 1.
- Slice 1a is the scrape tool only, static and markdown paths, rendering off, on asks G5, G6, G7, G10, G11, plus
  `proxy: "basic"` on every Firecrawl line and the web-tools call log — spec § Lifecycle, "Slice 1a".
- Firecrawl stays the fallback, closed to operator-cleared sources until the slice-1d test — spec § Fallback contract.
- `fabrik-scrape` is a raw-page fetch, never in the graded search chain; `_TIER1` is not widened — spec § Chosen
  approach, item 2.
- A command switches only when its own ledger is all-pass; fact strings are fixed before the run — spec § Test
  ledger (closing paragraph) and § Lifecycle.
- fabrik-lib builds the module and asks as its W-89c8b88f, and the web-tools call log as its W-eadc4d0a (coordinator
  relay, 2026-10-21); this plan does not write into `/opt/fabrik-lib` (cross-repo hard stop).
- The approval row exists: `docs/DECISIONS.md` D-1100 (verified by grep before planning).

## Intake Inventory

| I# | Item (anchored) | Disposition | Where |
|---|---|---|---|
| I1 | "plan the hub side of slice 1a" (this run's argument) | IN | Phases A-C |
| I2 | spec § Lifecycle 1a: "every command or seat line naming a Firecrawl tool gains `proxy: "basic"`" | IN | Phase A |
| I3 | spec § Lifecycle 1a: "infra registers it" | IN | Phase B (infra executes the unit install under a gate) |
| I4 | spec § Lifecycle 1a: "Then `fabrik-researcher` switches (its own ledger first)" | IN | Phase C |
| I5 | spec § Chosen approach 2: the three contract copies gain `fabrik-scrape` in the fetch sentence | IN for the hub's two copies (Phase C); OUT-OF-SCOPE for `/opt/fabrik-lib/CLAUDE.md` — a cross-repo file, requested from fabrik-lib by mail in Phase C |
| I6 | spec § Lifecycle 1b, 1c, 1d (crawl, rendering, the proxyUsed test) | OUT-OF-SCOPE | later plans, one per slice; 1d is gated on the operator's approval (spec § Fallback contract) |
| I7 | the seven other commands' switches (spec § Lifecycle: "one command per slice") | OUT-OF-SCOPE | later plans after this one; `fabrik-researcher` goes first |
| I8 | the web-tools caller-and-URL log (spec § Lifecycle 1a) | IN as a re-vendor of the hub's `libs/web_tools.py` (Phase B step 2, checked for the call log AND the `proxy: "basic"` payload), built by fabrik-lib as W-eadc4d0a |
| I9 | spec § Lifecycle 1a: "the capability ledger re-runs THROUGH `scrape` … must grade PASS on U1, U2, U3, U4 and U7" | IN | Phase B step 11 |
| I10 | spec § Documentation landing sites: `.windsurf/rules/core/57-external-data-sourcing.md` (the agent-time roster) | IN | Phase C step 6 |
| I11 | spec § Documentation landing sites: the precedent's PORTS row lists 8032 while its endpoint is `:8033/mcp` | OUT-OF-SCOPE | infra's row, mailed to infra at this plan's close |

Intake: 11 items — 8 IN (one partly), 3 OUT-OF-SCOPE (each named), 0 ASK.

## Global Constraints

- Logs are unbuffered JSON or plain lines to stdout only; no `*.log` file write (`core/10-python.md:301-302`).
- `uv` for every package operation; the server's own venv is created and filled with `uv`, never `pip`
  (`core/10-python.md:22`); the hub's shared `.venv` and `pyproject.toml`/`uv.lock` are not touched.
- Python service ports are 8000-8099 (`core/10-python.md:282`); the server listens on `127.0.0.1:8034` only.
- No write outside this repo except the gated Phase B steps (the main checkout's server venv and the unit file) and
  the run's own scratch folders (`/opt/fabrik/.tmp/runs/<session>/<run>/` and the `RUN-SCRATCH:` folder its `start`
  prints), and the emitter's regenerated `/opt/*/.mcp.json` files (Phase B step 10, infra, `--check` first); no edit
  under `/opt/fabrik-lib` (cross-repo).
- Command and agent text is edited in `commands/_sources/` and `commands/_agents/` only; the rendered corpus is the
  coordinator's merge-time render (CLAUDE.md § Behavior, merge-time render only).
- No secret is printed; the browserless token stays in `/opt/fabrik/.env`.
- 12-Factor: config by env vars (III); no daemonizing or PID file — systemd supervises (VIII); stdout logs (XI); the
  vendored release is immutable, updated only by re-vendoring (V).

## Context Ledger

| Source | What binds | Grounded ref |
|---|---|---|
| `core/40-documentation.md` (MATCHED) | new reference doc allowed under `docs/reference/`; INDEX on any added file; PORTS curated tables only | `.windsurf/rules/core/40-documentation.md:192`, `:140`, `:170`; `PORTS.md:147` |
| `core/10-python.md` (FLOOR) | `uv`, type hints, stdout logs, port range | `.windsurf/rules/core/10-python.md:22`, `:168`, `:301`, `:282` |
| `core/57-external-data-sourcing.md` | agent-time tool = MCP server; bypass line | spec § Constraints Digest |
| fabrik-lib `web-scrape-mcp` (VENDOR, being built) | the `scrape` tool and its `blocked` contract | spec § fabrik-lib asks; fabrik-lib W-89c8b88f |
| fabrik-lib `web-tools` (VENDOR, re-vendored) | the Firecrawl call log | fabrik-lib W-eadc4d0a; hub copy `libs/web_tools.py` |
| precedent box MCP server | systemd unit + `mcp_defs.json` http entry | `/etc/systemd/system/fabrik-citation-verifier-mcp.service`; `scripts/sysadmin/mcp_defs.json:28-31` |
| `agents-fabrik.md` | none touched — no VPS, compose, DB or Traefik change in slice 1a | `/opt/fabrik/agents-fabrik.md:361` (Planning Constraints read; items 6 and 4 apply: ports checked, existing service reused) |
| `specs/services/*.yaml` `shape:` | none — not a scaffolded project | — |

No new capability is built fresh in the hub: every module is fabrik-lib's, vendored (spec § fabrik-lib verdict).

## Constraints Digest

Quotes are verbatim with markdown emphasis removed (backticks, and `*` used as emphasis — a `*` inside a glob is kept),
the checker's convention.

| Quote | Source |
|---|---|
| Reference: docs/reference/**/*.md | `.windsurf/rules/core/40-documentation.md:192` |
| Rule: Edit existing docs instead of creating new ones. | `.windsurf/rules/core/40-documentation.md:186` |
| Update when: Any file added, removed, or moved. | `.windsurf/rules/core/40-documentation.md:140` |
| PORTS.md — port allocations, managed by scaffold + registrar system | `.windsurf/rules/core/40-documentation.md:170` |
| uv is the mandated Python package manager. Never use raw pip, pip install, poetry, or pipenv. | `.windsurf/rules/core/10-python.md:22` |
| Use type hints for all function signatures | `.windsurf/rules/core/10-python.md:168` |
| Python services: 8000-8099 | `.windsurf/rules/core/10-python.md:282` |
| Factor XI — Logs. Structured JSON, unbuffered, to stdout — and nothing else (PYTHONUNBUFFERED=1). | `.windsurf/rules/core/10-python.md:301` |
| Watched-fail-first (for tests this change adds or modifies; trivia stays skipped per the Behavior Contract): a non-trivial behavior's test proves something only if it has been SEEN RED | `.windsurf/rules/core/45-testing-strategy.md:22` |
| THE BYPASS LINE IS THE LEGAL LINE, and it runs straight through our own toolbox. | `.windsurf/rules/core/57-external-data-sourcing.md:258` |

PORTS.md is edited only in its curated "Development Services (WSL Only)" table, which `PORTS.md:147` names the
authoritative registry; the generated block is left alone.

## Phase A — `proxy: "basic"` on every Firecrawl line (no dependency; runs now)

Appetite: 60

Implements spec § Lifecycle, slice 1a ("every command or seat line naming a Firecrawl tool gains `proxy: "basic"`")
and spec § Fallback contract (why Firecrawl's default `auto` mode is not allowed). DO-NOT: change any fetch order,
switch any command to `fabrik-scrape`, or touch the search-chain grader.

Complexity: inline
Gate: .venv/bin/python -m pytest tests/test_firecrawl_proxy_basic.py tests/test_research_tier_order.py -q

### Touches

- tests/test_firecrawl_proxy_basic.py — NEW, the grader
- commands/_sources/fabrik-spec.md
- commands/_sources/fabrik-spec-review.md
- commands/_sources/fabrik-plan-after-chat.md
- commands/_sources/fabrik-vision.md
- commands/_agents/fabrik-researcher.md

### Behavior Contract

- **Given** a Firecrawl scrape or crawl instruction in `commands/_sources/` or `commands/_agents/` (`firecrawl_scrape`, `firecrawl_batch_scrape`, `firecrawl_crawl`, `mcp__firecrawl__*`, "Firecrawl scrape" or "Firecrawl crawl" in prose, or firecrawl followed by `maxAge`), **When** the grader scans it, **Then** its own clause carries the literal `proxy: "basic"` in either quote style, holds no negation word on the grader's list and names no other proxy mode (spec § Lifecycle 1a); the phase review confirms each pinned clause instructs the basic proxy (step 7)
- **Given** a pin outside the mention's clause, any negation word in the clause (even an unrelated one — the remedy is rewording that clause), a clause naming `stealth`, `auto` or `enhanced`, or a search-only name, **When** the grader judges it, **Then** the first three fail and the last is not a mention (spec § Fallback contract)

### Steps

1. Write `tests/test_firecrawl_proxy_basic.py` from the prototype `proto_grader5.py` (Evidence A; pinned beside the
   plan in each review pin), a strict literal rule that fails closed: a MENTION is a scrape or crawl tool name
   (`firecrawl_scrape`, `firecrawl_batch_scrape`, `firecrawl_crawl`), `mcp__firecrawl__*`, "Firecrawl scrape" or
   "Firecrawl crawl" in prose, or the word firecrawl with `maxAge` within 40 characters, line wraps collapsed first
   (search- and map-only names are not mentions); its CLAUSE runs from the mention to the next `.`,
   `;`, `→` or ` — ` outside a code span (double-backtick spans masked first), and a `.` does not end it only inside
   `e.g.`, `i.e.`, `cf.` or between digits; the clause PASSES only when it holds the literal `proxy: "basic"` (either
   quote style), no negation word anywhere (never, not, no, nor, neither, without, instead, drop, omit, unless, avoid,
   skip…, except, cannot, or a word ending in n't with either apostrophe) and no `stealth`, `auto` or `enhanced` anywhere in the clause. A negation unrelated to the proxy also fails the clause — the failure message says
   to reword that clause; a false red costs a rewrite, a false green ships an unpinned call. The grader guards PRESENCE
   against regression; natural-language negation is unbounded, so the cheapest way to satisfy it without the outcome
   is a negation spelled outside its list — written in the test's docstring, and answered by a named check, never by
   a longer list: step 7 here, and for every later change, the test's failure message and docstring say that a review
   of a change to a pinned clause reads that clause and states that it instructs the basic proxy. The docstring names
   the `MENTION`, `NEG`, `OTHER` and `PIN` constants as the lists instead of repeating them, so it cannot drift. One parametrised test over
   the 36 fixtures in Evidence A (each judged as listed, covering all five mention spellings) and one over the real
   corpus that lists every `path:line` lacking the pin. Today the corpus test fires on 17 mentions on 16 lines in 5
   files (Evidence A).
2. Run it and confirm the corpus test FAILS red for the right reason, listing the 17 mentions, while the fixtures
   pass: `.venv/bin/python -m pytest tests/test_firecrawl_proxy_basic.py -q` → 1 failed, 36 passed.
3. Add `proxy: "basic"` inside the clause of each of the 17 mentions (Evidence A), wording each clause with no negation word, keeping each sentence's meaning:
   e.g. "`firecrawl_scrape` with `maxAge: 0`" becomes "`firecrawl_scrape` with `maxAge: 0` and `proxy: "basic"`";
   researcher `:22` names the family `mcp__firecrawl__*`, so its clause says scrape and crawl calls pass
   `proxy: "basic"`.
4. Re-run the gate → all passed. Prove red-on-revert in a throwaway worktree: `git worktree add <RUN-SCRATCH>/probe
   HEAD`; copy the six Touches files from the working tree into the probe; assert the probe holds the edit (`grep -c
   'proxy: "basic"' <probe>/commands/_sources/fabrik-spec.md` ≥ 4); revert ONE pinned clause there and assert it lacks
   the pin; run the grader from inside the probe → red naming exactly that line; remove the probe. Never in the shared
   tree.
5. `python3 scripts/enforcement/check_doc_sync.py` → no ERROR; CHANGELOG entry under `[Unreleased]`
   (`### Changed — Firecrawl calls in commands pin the basic proxy (2026-10-21)`); `INDEX.md` row for the new test.
6. Render to a temp directory, never the live corpus: `.venv/bin/python commands/assemble_commands.py --dest
   <RUN-SCRATCH>/render` (a non-live `--dest` writes agents under `<dest>/_agents`, never `~/.claude/agents`,
   `commands/assemble_commands.py:1171`); then `rg -c 'proxy: "basic"' <RUN-SCRATCH>/render` shows the pin in the four
   rendered commands and `_agents/fabrik-researcher.md`. `--check` is not the gate here: it diffs against the installed
   corpus and must report drift until the coordinator's merge-time render (`commands/assemble_commands.py:10`).
7. **`/fabrik-review` on this phase's changed surface — BLOCKING, run to its coverage-adjudicated exit** (the
   command sources are a governance-sync surface, CLAUDE.md § Orient lane row 1): partitioned file slices, a Sonnet
   and a Haiku finder per slice, every candidate executed by the lead, delta rounds to a closing round that confirms
   zero code or doc defects. Named check in that review: the lead reads each of the 17 pinned clauses and records,
   per `path:line`, that it instructs `proxy: "basic"` (the grader's cobra counter-measure, step 1).
8. Commit the phase with explicit pathspecs and trailers; push.

### Interfaces

Produces: the grader `tests/test_firecrawl_proxy_basic.py`, which Phase C's edits must keep green.

## Phase B — vendor, run and register `fabrik-scrape` (after fabrik-lib W-89c8b88f and W-eadc4d0a merge)

Appetite: 120

Implements spec § Chosen approach 1 (the server), § Lifecycle 1a ("infra registers it"; "the capability ledger
re-runs THROUGH `scrape` … must grade PASS on U1, U2, U3, U4 and U7, with U6 returning `blocked: bot-wall` and U5
returning `blocked: unsupported`"), and § Shape (one local MCP server process, one `mcp_defs.json` entry, one port).
DO-NOT: enable rendering, edit the vendored code, or touch `libs/web_scrape/` (the older kilo-db copy).

Complexity: inline
Gate: .venv/bin/python -m pytest tests/test_scrape_ledger.py tests/test_emit_mcp_project_config.py -q, then /opt/fabrik/libs/web_scrape_mcp/.venv/bin/python scripts/scrape_ledger.py --probe http://127.0.0.1:8034/mcp — Expected: tests pass; `initialize` answers with `serverInfo` and `tools/list` contains `scrape` (a bare GET on a streamable-HTTP MCP endpoint answers 406, as the precedent does on :8033, so it is never the gate)

Start condition, self-service: fabrik-lib's reply mail names the merge SHAs of W-89c8b88f and W-eadc4d0a
(`python3 scripts/mail.py list` shows it). Until then the phase does not start; this is an event wait, not a question.

Where things run: the unit and its venv target the MAIN checkout (`/opt/fabrik`), like the precedent unit targets its
own repo. So steps 1-8 are worktree work merged by the coordinator; steps 9-12 run only after that merge.

### Touches

- libs/web_scrape_mcp/ — NEW, the vendored module (copied whole from `/opt/fabrik-lib/web-scrape-mcp/` at the merged SHA)
- libs/web_tools.py — re-vendored from `/opt/fabrik-lib/web-tools/web_tools.py` at W-eadc4d0a's SHA
- scripts/scrape_ledger.py — NEW, the MCP probe, transcript harvest and ledger runner (used by this phase's gate and by Phase C)
- tests/test_scrape_ledger.py — NEW, its tests with a mocked MCP client
- scripts/sysadmin/emit_mcp_project_config.py — `fabrik-scrape` joins the universal set
- tests/test_emit_mcp_project_config.py — its pinned universal set (`:42`) gains `fabrik-scrape`
- scripts/sysadmin/mcp_defs.json — the `fabrik-scrape` http entry
- scripts/sysadmin/systemd/fabrik-scrape-mcp.service — NEW, the unit's source of truth in the repo
- docs/reference/fabrik-scrape-mcp.md — NEW, the subsystem doc
- docs/workstation/mcp-roster.md
- PORTS.md

### Behavior Contract

- **Given** the server is started by its unit, **When** `scripts/scrape_ledger.py --probe` posts an MCP `initialize` to `http://127.0.0.1:8034/mcp`, **Then** it gets `serverInfo` back and `tools/list` contains `scrape` (spec § Chosen approach 1)
- **Given** the spec's capability ledger U1-U7 with fact strings fixed before the run, **When** each URL goes through `scrape`, **Then** U1, U2, U3, U4 and U7 grade PASS, U6 returns `blocked: bot-wall` with `status` 403 and no render, and U5 returns `blocked: unsupported` (spec § Lifecycle 1a)
- **Given** `scrape` on `http://127.0.0.1:8033/`, **When** called, **Then** it returns `blocked: scope` (spec § fabrik-lib asks G7)
- **Given** `scripts/scrape_ledger.py` and a mocked MCP client, **When** it runs an input, **Then** every fact string round-trips byte-identical, each row carries facts found, clean ratio, path, `blocked` reason and `status`, and an input row without an `expected` field is refused (spec § Test ledger)
- **Given** the emitter, **When** it renders any repo's `.mcp.json`, **Then** `fabrik-scrape` is in the set and `scripts/enforcement/check_mcp_scope.py` exits 0 (spec § Chosen approach 2: every repo's seats)
- **Given** the re-vendored `libs/web_tools.py`, **When** its Firecrawl payloads are built, **Then** each carries `proxy: "basic"` and each call logs its caller and URL (spec § fabrik-lib asks, the web-tools row)

### Steps

Pre-merge, in the worktree:

1. Read fabrik-lib's merged `web-scrape-mcp/README.md` and follow its vendor instructions; copy the module into
   `libs/web_scrape_mcp/` at the merged SHA, recording the SHA in a `VENDORED_FROM` line of its README.
2. Re-vendor `libs/web_tools.py` from fabrik-lib at W-eadc4d0a's SHA. Check the spec's web-tools row landed:
   `rg -n '"proxy": "basic"' libs/web_tools.py` finds the scrape and crawl payloads (today `:424` builds
   `{"url", "formats"}` with none), and the per-call caller-and-URL log is present; a missing part is mailed to
   fabrik-lib and the re-vendor waits. Run its importers — `rg -l "libs\.web_tools|from libs import
   web_tools|from web_tools import|import web_tools" tests scripts` lists `tests/test_rivals_run.py` and
   `scripts/rivals_run.py` — with `/opt/fabrik/scripts/capped_run.sh -- .venv/bin/python -m pytest
   tests/test_rivals_run.py -q`.
3. Write `tests/test_scrape_ledger.py` first (mocked MCP client; the Behavior Contract row above) and watch it fail;
   then write `scripts/scrape_ledger.py` (typed, results to stdout and to `--out <json>`, `# AFTER-EDIT:` header naming
   `docs/reference/fabrik-scrape-mcp.md`) with three modes: `--probe <url>` runs `initialize` + `tools/list`;
   `--harvest --since 2026-10-01 --out <json>` reads subagent transcripts under `~/.claude/projects/*/*/subagents/` and
   `~/.claude-fleet/*/projects/*/*/subagents/`, keeps those whose `agent-*.meta.json` says `"agentType":
   "fabrik-researcher"`, and extracts `input.url` / `input.urls` from their `mcp__firecrawl__firecrawl_scrape`,
   `mcp__exa__web_fetch_exa` and `WebFetch` tool calls, de-duplicated; and `<input json>` runs each row through
   `scrape`, refusing a row without an `expected` field (`pass` or a named `blocked` reason with its spec cite), and
   grades PASS as every fact string found AND clean ratio ≥ 0.6 (spec § Test ledger). The script runs under the
   server's venv (it needs the MCP client); its test runs under the hub `.venv`, which already carries `mcp` 1.29.0.
4. Write `scripts/sysadmin/systemd/fabrik-scrape-mcp.service` modelled on the precedent unit (Evidence B):
   `User=ozgur`, `WorkingDirectory=/opt/fabrik`, NO `EnvironmentFile=` — the hub's secrets never enter a
   network-facing fetcher's environment (the same rule as `scripts/sysadmin/systemd/session-archive.service:3-4`), and
   slice 1a needs no browserless credential because rendering is off — then only non-secret `Environment=` lines for
   the host (`127.0.0.1`) and port (`8034`), using the module's own variable names from its README;
   `ExecStart=/opt/fabrik/libs/web_scrape_mcp/.venv/bin/python <the module's entry point>`; and the precedent's
   hardening — `Restart=always`, `RestartSec=3`, `StartLimitIntervalSec=60`, `StartLimitBurst=5`, `MemoryMax=512M`,
   `MemorySwapMax=0`, `OOMPolicy=stop`, `NoNewPrivileges=true`. Port 8034 is free (Evidence B).
5. Add `"fabrik-scrape": {"type": "http", "url": "http://127.0.0.1:8034/mcp"}` to `scripts/sysadmin/mcp_defs.json`
   beside the precedent entry (`:28-31`), and add `"fabrik-scrape"` to `UNIVERSAL6` in
   `scripts/sysadmin/emit_mcp_project_config.py:39-46` — the researcher renders to every repo, so every repo's
   `.mcp.json` must carry the server. That widens the D-013 universal set: mint its row (`python3 scripts/decisions.py
   --reserve-id .`, supersedes nothing, extends D-013) and edit `docs/workstation/mcp-roster.md` in the same commit
   (`scripts/enforcement/check_mcp_scope.py:20-22`); add `fabrik-scrape` to the test's server list and pinned set
   (`tests/test_emit_mcp_project_config.py:24`, `:42`, so its `defs_file` fixture `:47` serves it), watch the
   universal-set test fail before the emitter edit; run that test and
   `python3 scripts/enforcement/check_mcp_scope.py` → exit 0.
6. Docs: write `docs/reference/fabrik-scrape-mcp.md` (what it is, tools, `blocked` reasons, unit, port, venv rebuild,
   re-vendor steps) + its `INDEX.md` row; a `docs/workstation/mcp-roster.md` row beside the precedent (`:75`); a
   `PORTS.md` row in "Development Services (WSL Only)"; CHANGELOG entry; `check_doc_sync.py` → no ERROR.
7. **`/fabrik-review` on the pre-merge surface — BLOCKING, run to its coverage-adjudicated exit** (a new mechanism and
   a box service: full review); the vendored module is out of finding scope, its integration (unit, entry, script,
   docs) in it.
8. Commit with explicit pathspecs and trailers; push; raise the merge request; the coordinator merges.

Post-merge, on the main checkout, as a gate:

9. Gate (deploy): building the venv and installing the unit write outside this worktree (`/opt/fabrik/libs/
   web_scrape_mcp/.venv`, `/etc/systemd/system/`) — the operator approves through the coordinator; on approval infra
   runs, from `/opt/fabrik`: `uv venv libs/web_scrape_mcp/.venv`, `uv pip install --python
   libs/web_scrape_mcp/.venv/bin/python -r libs/web_scrape_mcp/requirements.txt`, then `sudo install -m 644
   scripts/sysadmin/systemd/fabrik-scrape-mcp.service /etc/systemd/system/`, `sudo systemctl daemon-reload`, `sudo
   systemctl enable --now fabrik-scrape-mcp`.
10. Infra runs `python3 scripts/sysadmin/emit_mcp_project_config.py` (first with `--check`, which reports and never writes, `:334`; the default `--root /opt` (`:331`) rewrites every
    repo's generated `.mcp.json`, so the real run stays inside step 9's operator gate) so every
    repo's generated `.mcp.json` gains `fabrik-scrape`; `python3 scripts/sysadmin/mcp_health.py` → `fabrik-scrape` live.
11. Run the phase gate; then the capability ledger U1-U7 through `scrape` (the spec's URLs and the pass table above,
    fact strings re-fixed before the run from an independent read) and the scope call; results in the run folder. A
    FAIL is mailed to fabrik-lib and stops Phase C.
12. Record the gate and ledger outputs in the review receipt; commit and push.

### Interfaces

Consumes: fabrik-lib `web-scrape-mcp` at its merged SHA (tool `scrape`, spec § Chosen approach 1's return shape);
fabrik-lib `web-tools` at W-eadc4d0a.
Produces: the live MCP endpoint `http://127.0.0.1:8034/mcp` named `fabrik-scrape`, present in the hub `.mcp.json`;
`scripts/scrape_ledger.py` (`--probe <url>`, `<input json>` → result JSON); both consumed by Phase C.

## Phase C — the researcher's ledger, then its switch

Appetite: 120

Implements spec § Lifecycle 1a ("Then `fabrik-researcher` switches (its own ledger first, as for every command)"),
spec § Test ledger (fact strings fixed before the run), spec § Chosen approach 2 (the researcher's order, long-page
rule, DEAD rule, credit-error rules; the contract copies' fetch sentence) and spec § Fallback contract (what a seat does
per `blocked` reason). DO-NOT: switch any other command; widen `_TIER1`; edit `/opt/fabrik-lib/CLAUDE.md` (mailed).

Complexity: inline
Gate: .venv/bin/python -m pytest tests/test_firecrawl_proxy_basic.py tests/test_research_tier_order.py tests/test_researcher_fallback_contract.py tests/test_scrape_ledger.py -q — Expected: all passed

Start condition: Phase B's post-merge steps done — `fabrik-scrape` is live and in the hub `.mcp.json` — and the
session is a NEW one started after that, so a `fabrik-researcher` seat it dispatches can reach the server.

### Touches

- commands/_agents/fabrik-researcher.md
- tests/test_researcher_fallback_contract.py — NEW, the grader for the switched agent text
- .windsurf/rules/core/57-external-data-sourcing.md — the agent-time roster line (`:64`)
- CLAUDE.md
- templates/governance/CLAUDE.md

### Behavior Contract

- **Given** the researcher's ledger input of URLs with fact strings fixed beforehand, **When** `scripts/scrape_ledger.py` runs them through `fabrik-scrape`, **Then** every URL grades PASS or returns the `blocked` reason the spec expects, and no fact string is edited after the run (spec § Test ledger)
- **Given** the ledger is all-pass, **When** the agent file switches, **Then** `mcpServers` lists `fabrik-scrape` and the raw-fetch order is `fabrik-scrape` → exa (per `blocked` reason) → Firecrawl (closed until slice 1d except an operator-cleared source) (spec § Chosen approach 2, § Fallback contract)
- **Given** the switched agent file, **When** the grader reads it, **Then** it states each Fallback-contract row: `robots` → no other fetcher this session, `WebFetch` and exa included; `scope` → never fetched; non-429 `http-4xx` → reported, no fallback; `http-429` → never exa or Firecrawl; `bot-wall` → no exa, `WebFetch` or Firecrawl (Firecrawl only for an operator-cleared source after slice 1d); `empty` → exa allowed, never Firecrawl; an exa read is cited as exa's cached copy; and every Firecrawl entry point is closed until the slice-1d test (spec § Fallback contract)
- **Given** the two hub contract copies, **When** the new fetch sentence lands, **Then** the grader finds it byte-identical in both and outside the tier ladder sentence, and `tests/test_research_tier_order.py` stays green (spec § Chosen approach 2)

### Steps

1. Build the researcher's URL list: `/opt/fabrik/libs/web_scrape_mcp/.venv/bin/python scripts/scrape_ledger.py
   --harvest --since 2026-10-01 --out <RUN-SCRATCH>/researcher-urls.json` (Phase B step 3), recording the command line;
   sample at least 10 and at most 20 distinct URLs with at least one per kind (docs page, API reference, GitHub raw
   file, PDF, a long page).
2. For each URL fix BEFORE any run: its fact strings, from one independent read (`WebFetch`) recorded beside them, and
   its `expected` outcome — `pass`, or a named `blocked` reason with the spec cite that predicts it (a PDF is
   `unsupported` until slice 1b) — in `<RUN-SCRATCH>/researcher-ledger-input.json` (spec § Test ledger).
3. Run `/opt/fabrik/libs/web_scrape_mcp/.venv/bin/python scripts/scrape_ledger.py
   <RUN-SCRATCH>/researcher-ledger-input.json --out <RUN-SCRATCH>/researcher-ledger.json`. All-pass means every row's
   result equals its pre-fixed `expected` (PASS = every fact string found AND clean ratio ≥ 0.6). A row that differs
   stops the phase: the researcher keeps Firecrawl, and the failing kind goes to fabrik-lib as a new ask.
4. Write `tests/test_researcher_fallback_contract.py` first and watch it fail on today's files: it asserts the
   researcher's `mcpServers` names `fabrik-scrape`, the raw-fetch order, and that its text carries each
   Fallback-contract row named in the Behavior Contract above, one assertion per row; and that the fetch sentence of step 6 appears
   byte-identical in `CLAUDE.md` and `templates/governance/CLAUDE.md`, in a sentence of its own after the
   METERED sentence, never inside the `tier 1 is …` chain.
5. On all-pass, edit `commands/_agents/fabrik-researcher.md`: `mcpServers` (line 4, Evidence C) gains `fabrik-scrape`;
   the raw-fetch order, the long-page rule (`:36-44`), the DEAD rule (`:86`, keyed on the `status` of a `blocked`
   result) and the credit-error rules follow spec § Chosen approach 2; the spec's § Fallback contract table is carried
   row by row, every Firecrawl leg marked closed until slice 1d except an operator-cleared source named in the plan or
   work item. Both graders go green.
6. Add this sentence, byte-identical, to `CLAUDE.md` § External Knowledge and `templates/governance/CLAUDE.md`, as its
   own sentence right after "`exa` and `firecrawl` are METERED: tier 2 is for a miss, never a habit."
   (`CLAUDE.md:306-307`, template `:280-281`) — never inside the `tier 1 is …` chain: "For a raw page read (an exact quote, a live re-fetch), call `fabrik-scrape` `scrape(url)`
   first — a fetch, not a search engine, outside this ladder; on a `blocked` result follow its reason
   (the `fabrik-researcher` agent)." The template syncs to projects that hold no `commands/` tree, so the sentence
   names the agent, never its source path. Mail fabrik-lib the same sentence for `/opt/fabrik-lib/CLAUDE.md`. Add `fabrik-scrape` to rule 57's agent-time roster line
   (`.windsurf/rules/core/57-external-data-sourcing.md:64`, beside `firecrawl`).
7. Run the phase gate → all passed; `check_doc_sync.py` → no ERROR; CHANGELOG entry; `INDEX.md` row for the test.
8. **`/fabrik-review` on this phase's changed surface — BLOCKING, run to its coverage-adjudicated exit** (synced
   contract and agent files: full review).
9. Run `/fabrik-docs-review` over the plan's doc changes; then the plan's final gate:
   `python scripts/final_gate.py --check --json` → `"status":"success"` and
   `python scripts/enforcement/check_convergence.py --project-root .` → exit 0. A green gate is necessary, not
   sufficient: the proof is the ledgers and the review receipts.
10. Commit with explicit pathspecs and trailers; push; raise the merge request.

### Interfaces

Consumes: `fabrik-scrape` at `http://127.0.0.1:8034/mcp` and `scripts/scrape_ledger.py` (Phase B); Phase A's grader.
Produces: the switched researcher; the ledger result JSON the merge request cites.

## Coverage Checklist

| Class | Source | State |
|---|---|---|
| security-auth: SSRF / non-public addresses, secret handling in the unit | FLOOR core/35-security-auth.md | FIXED r1 (unit has no `EnvironmentFile=`, binds 127.0.0.1; the `blocked: scope` call on :8033 is a Phase B behaviour) |
| data-postgres: no database touched | FLOOR core/25-data-postgres.md | CLEAN (no Touches path reaches a database; both seats, r1) |
| ops: the systemd unit (memory cap, restart, user, no host-wide port) | FLOOR core/30-ops.md | FIXED r1 (the precedent's hardening set; install is a gated post-merge step) |
| 12-Factor (III config, V immutable release, VIII no daemonizing, XI stdout logs) | FLOOR 12-FACTOR | FIXED r1 (non-secret `Environment=` lines; systemd supervises; results to stdout and `--out`) |
| Python script discipline (uv, type hints, stdout) | MATCHED core/10-python.md | CLEAN (uv venv; `scrape_ledger.py` typed, stdout; r1-r3) |
| doc-sync triggers (CHANGELOG, INDEX, new reference doc, curated PORTS row) | MATCHED core/40-documentation.md | FIXED r1 (reference doc, INDEX, roster, PORTS row; the precedent's PORTS mismatch mailed as I11) |
| tests: one per behaviour, watched-fail-first | MATCHED core/45-testing-strategy.md | FIXED r1-r3 (proxy grader v4 with 25 fixtures; `test_scrape_ledger.py`; emitter test red first; fallback grader) |
| agent-time MCP vs runtime module; the bypass line | MATCHED core/57-external-data-sourcing.md | FIXED r1-r2 (rule 57 roster line; bot-wall and robots rows forbid evasion) |
| resilience: fallback, retry and 429 handling (57 sends readers to 58) | core/58-resilience.md | FIXED r2 (Fallback rows match spec :219-225; 429 never to exa or Firecrawl) |
| recurrence: fail-open vs fail-closed on every gate/guard | standing class | FIXED r1-r3 (grader fails closed; ledger refuses a row without `expected`; gate is an MCP probe, never a bare GET) |
| recurrence: cost/quota/limit accounting edges | standing class | CLEAN (Firecrawl pinned to `basic` and closed until slice 1d; no metered call in this plan; r1-r3) |
| recurrence: boundary/sentinel/prefix collisions | standing class | FIXED r2-r3 (clause end on abbreviations and digits; `mcp__firecrawl__*` vs search-only names) |
| recurrence: behavior-without-a-test | standing class | FIXED r1-r4 (every Behavior Contract row names a test or a named executed check: the Phase B probe and capability ledger and the Phase C researcher ledger are live runs; the web-tools pin and call log are step 2's `rg` and its presence check of the call log; the proxy clauses' meaning is Phase A step 7's named check) |

```text
# REVIEW RUBRIC — inject into EVERY finder prompt (generated by review_rubric.py)
# Honesty (L1): this arms the review — it raises compliance probability, it does not guarantee it.

## FLOOR — always injected, regardless of glob (spec L3; SERVICE surface)

### core/35-security-auth.md
**The default for ALL new projects, including user-facing SaaS + mobile.** Vendor `fabrik-lib/fastapi-user-auth`: the app issues its own JWTs — **Argon2id** (the vendored argon2-cffi defaults meet OWASP minimums; never Argon2i) + timing-equalized login, atomic refresh-token rotation (`DELETE … RETURNING`), JWT `jti` denylist revocation, and dual-mode tenant-isolation RLS. Supabase is retired as a default (see `agents-fabrik.md § Supabase`); reach for Pattern B only for a project that *already* runs on Supabase Auth.
- Do not use NextAuth.js, Clerk, Auth0, or Firebase Auth.
- ADDITIONAL affordance a project justifies, never the default door.
- project files the fabrik-lib request FIRST, never hand-rolls WebAuthn.
| `chrome-extension` | ✅ **use this** | ⚠️ only via `chrome.identity.launchWebAuthFlow` + the `https://<ext-id>.chromiumapp.org/` redirect the pack already mandates; a bare mailed link lands in a TAB that cannot reach `chrome.storage.session` |
| `desktop-app` | ✅ **use this** | ⚠️ needs a registered custom protocol handler; the token then goes to `safeStorage` (`desktop-app/72-desktop.md`) |
- service MUST be able to say which:
| **Another Fabrik service** (Docker-to-Docker on the `fabrik` network) | `X-Internal-Token` + `internal_auth.py`, `hmac.compare_digest`, 403 on reject | § Internal Service Auth (M2M) below — **never** an inline `APIKeyHeader`, never a per-service key name |
- An approval link opened somewhere the user did not start must never mint a session silently.
- > **Fail-closed invariant (hard, every mode).** `auth.uid()` and `current_tenant_id()` MUST return `NULL` (→ the policy denies) on unset, empty, or malformed claims — wrap the body in `EXCEPTION WHEN OTHERS THEN RETURN NULL`. **Never** raise and never default to a value: a default turns one bad/empty JWT into a cross-tenant read, and a raise turns a deny into a 500. This is the single most security-critical line in the build — verify it explicitly with a no-context probe (`SELECT auth.uid()` → `NULL`).
- The JWT signing secret must be at least 256 bits, generated via `openssl rand -hex 32`, and injected via Pydantic Settings. Never hardcode it.
- **Pin the algorithm in the VERIFIER** — pass an explicit allow-list (`algorithms=["HS256"]`), never let the library dispatch on the token header's `alg`. Header-driven dispatch is the classic confusion attack (an RS256 public key replayed as an HS256 HMAC secret); `alg: none` is rejected unconditionally.
- "Sticky sessions are a violation of twelve-factor and should never be used or relied upon."
- => Mandate: processes are stateless/share-nothing. **STICKY SESSIONS ARE BANNED** (not just file-based sessions). Session state goes to `redis-main` (Redis) with a TTL. Never in-process memory, never on local disk. Any design that assumes "the same user hits the same process" is a violation.
- **Pattern B (legacy / migration-only):** The Supabase client SDK handles token storage. On mobile, wrap with `expo-secure-store` (never AsyncStorage or MMKV for tokens). See `80-mobile.md` § Backend Integration.
- **Both patterns:** Never store JWTs in `localStorage` or `sessionStorage` on web. Never store JWTs in AsyncStorage or MMKV on mobile.
- **Chrome Extension (MV3) specifics:** `chrome.storage.session` defaults to `TRUSTED_CONTEXTS`, so **content scripts cannot read the token** — keep it in the SW / extension-page context and have content scripts fetch it via SW-mediated messaging (`chrome.runtime.sendMessage`), not a direct read. For social login use `chrome.identity.launchWebAuthFlow` with **PKCE** (`code_verifier` via `crypto.subtle`, held in `storage.session`, redirect `https://<ext-id>.chromiumapp.org/`); the **backend** does the code-for-token exchange. **Never a heavy browser auth SDK** (Auth0-SPA-JS, `oidc-client-ts`) — they assume DOM/`localStorage`/iframes and break in the service worker. Pin a manifest `key` so the extension ID (and thus the `chrome-extension://<id>` CORS origin) is stable across machines. Full detail: `chrome-ext/70-chrome-ext.md`.
- **Never rely solely on the framework's request-shaping layer for access control.** CVE-2025-29927 (the `x-middleware-subrequest` bypass) proved COMPLETE middleware bypass via one crafted header; it is long patched upstream, but the rule outlives the patch — current Next.js even RENAMED the file to say so: `middleware.ts` became **`proxy.ts`**, explicitly repositioned as request-shaping, not a security boundary. ⚠️ **On current majors a leftover `middleware.ts` is SILENTLY IGNORED at build** — nonce injection and redirects stop executing with no error; rename it when upgrading.
- `CORSMiddleware` in FastAPI must populate `allow_origins` from environment variables (Pydantic Settings). Never hardcode origins.
- `X-Frame-Options: DENY` — kept as the legacy fallback only; formally obsoleted by `frame-ancestors`, never ship it ALONE
**Never** write inline `APIKeyHeader` / `require_api_key`. **Never** use per-service key names (`SERVICE_API_KEY`, `PROXY_API_KEY`). Scaffold `python-api` auto-emits `internal_auth.py`, `metrics.py` (REQUEST_COUNT / ERROR_COUNT / ACTIVE_JOBS / PROCESSING_COUNT), `/metrics` endpoint (Authelia-bypassed), and `SERVICE_INTERNAL_SECRET_KEY` in `.env.example`.
- => Mandate: config via env vars only (`os.getenv("KEY", "default")`); **ZERO secrets/constants in code**. Apply the open-source litmus test to every change. **BANNED**: grouped/named env config sets (e.g. a `config/production.yml` or a `settings.production` group) — env vars are granular and orthogonal, set per deploy. (The pack already covers secret handling — cross-reference existing secret patterns and extend with config orthogonality.)
- `POST /auth/passwordless/request` is ALREADY capped per email and per IP in Redis by the library (`AUTH_PASSWORDLESS_REQUEST_CAP`, `AUTH_PASSWORDLESS_IP_REQUEST_CAP`): tune those, add no second limiter, and never answer it with 429 — it returns 202 either way, so throttling never reveals an account. `POST /auth/passwordless/verify` has a per-code attempt cap (`AUTH_PASSWORDLESS_ATTEMPT_CAP`) but no per-IP bound; the project adds that bucket.
- [ ] Mobile tokens stored in `expo-secure-store` — never AsyncStorage or MMKV.
- A dedicated admin host on its own domain — never the customer-facing app's domain — behind 2FA: set `shape.is_admin_dashboard: true` there. The Authelia registrar adds a per-domain `two_factor` rule on `fabrik apply`, so every path on that domain sits behind 2FA except the standing `/health` and `/metrics` bypasses (D-366, `saas/60-saas-ui.md` § Admin). API services with bearer auth: set `shape.has_bearer_api: true` — the registrar inserts an Authelia **bypass** rule *before* the `two_factor` catch-all so machine/bearer callers aren't hit with interactive 2FA. Don't add Traefik `authelia-forward` middlewares manually — the scaffolder + registrars emit them.
- > **⚠️ Bearer bypass scope — security-critical.** The bypass defaults to `^/api/`, which makes the **entire** `/api/*` surface public (un-2FA'd). If the application authenticates only a **sub-prefix** (e.g. `/api/v1` carries the bearer/internal-token check) while OTHER `/api/*` routes are unauthenticated (legacy / admin / destructive), you **MUST** narrow the bypass with `shape.bearer_bypass_prefix: "^/api/v1"` — otherwise `fabrik apply` exposes those routes to the public internet. **Bypass ONLY the path the app itself authenticates.** Value must start with `^/`; the verifier (`orchestrator/verifier.check_api_bypass`) probes the configured prefix on deploy. When unsure whether a service has un-auth'd `/api/*` routes, ask the app owner before relying on the `^/api/` default.

### core/25-data-postgres.md
| Vector search | pgvector on `postgres-main` + `fabrik-lib/rag` — ⚠️ the extension is NOT currently installed there (probed 2026-09-01: the plain upstream PostgreSQL Alpine image, `plpgsql` only — `CLAIMS.yaml` row `fleet-postgres-main-no-pgvector`); a project needing vectors REQUESTS the fleet infra change first, never assumes it | same `postgres-main` DSN |
**"Own database" means a DATABASE on `postgres-main`, never a database SERVER.** Per-project isolation is a separate database (its own name, its own role) on the shared container — isolation, quota and backup are all satisfied at that grain. A dedicated Postgres instance is a decision, not a default: it needs its own `docs/DECISIONS.md` row naming what the shared server cannot serve (web-ecommerce-factory 01M1Q8X9, 2026-09-05: "one DB per store" read naively as one server per customer).
- Use Pydantic `BaseSettings` (per `10-python.md` § Config Loading) — never raw `os.getenv` **for an APPLICATION's settings surface**:
- ⚠️ **Scope, stated here because this LINE is what `review_rubric.py` injects — without its section.** The rubric FLOOR-injects this mandate *and* `35-security-auth`'s "config via env vars only (`os.getenv("KEY", "default")`)" into every finder prompt on every review, so a finder reading both literally has two rules it cannot both satisfy, and files a false positive on whichever it applies. The carve-out: `BaseSettings` governs a SERVICE's config surface (a `Settings` object, DB/Redis DSNs, secrets). A **vendored fabrik-lib module** has no settings object by design — it reads its own knobs with bare `os.getenv("KEY", "default")`, which is `35-security-auth`'s mandate being satisfied, not this … (wrapped further — read the pack)
- Never blindly trust `--autogenerate`. Always review `upgrade()` and `downgrade()` for unintended column drops, rename misinterpretations, and ENUM alterations before committing.
- > **Older pythons only** (services pinned below stdlib-uuid7 — which today includes SCAFFOLDED services: the scaffold still emits an older interpreter and ships `uuid-utils`; alignment tracked in the backlog): import `uuid7` from `uuid_utils.compat`, never `uuid_utils.uuid7()` directly — the latter returns `uuid_utils.UUID`, which asyncpg rejects (not a stdlib `uuid.UUID`). **DB-side:** newer PostgreSQL majors ship native `uuidv7()` (probe: `SELECT uuidv7()`); prefer `DEFAULT uuidv7()` at schema level where it exists. `postgres-main` currently runs major <!--v:postgres_major-->16<!--/v-->, which predates it — generate app-side on the fleet.
- Foreign keys must declare `ON DELETE` behaviour explicitly — `CASCADE` if children cannot exist without the parent, `RESTRICT` to protect audit trails. Never rely on the implicit default.
- This section owns the **canonical** engine, session, and `get_db`. `10-python.md` imports from here — never redefines its own.
- Database `AsyncSession` must be scoped to the route handler via `Depends()`. Never open sessions or transactions in global middleware — this holds connections during serialisation and I/O, exhausting the pool.
**BANNED as a server-side backing service** (dev, test, and prod alike):
**⚠️ SCOPE — this ban is about BACKING SERVICES, not client-local storage.** It does **NOT** apply to:
- **`desktop-app`** — SQLite is the **mandated** engine there (`desktop-app/72-desktop.md` § Local Persistence: `better-sqlite3` + SQLCipher; *"Production builds MUST encrypt the local SQLite file"*).
**12-Factor IV (Backing Services) — generalised:** swapping ANY attached backing service (DB, cache, object storage) is a **config change, never a code change**. The handle lives in `DATABASE_URL` / `REDIS_URL` / storage env — the code *reads* it, the code does not *decide* it. Never `if ENV == "prod":` branching to pick a host. (See § PostgreSQL Host Selection, which already mandates this for the DB.)
- [ ] All primary keys use UUIDv7 — stdlib `uuid.uuid7` on current Python (older pythons: `uuid_utils.compat.uuid7`, never direct `uuid_utils.uuid7()`); no `uuid4()`.

### core/30-ops.md
- the pinned release leaves full security support, never per-pack.
- All services deploy via `fabrik apply` (SSH + Docker Compose) on the `fabrik` network. Traefik routes external traffic — services do NOT bind host ports.
- **No `ports:` section.** All external traffic routes through Traefik. Never bind host ports. See Docker Port Security below. **12‑Factor VII (Port binding):** "the app is self‑contained and exports HTTP by binding to a port; it does not rely on runtime injection of a webserver" — which is exactly WHY no host `ports:`.
- **`container_name: <name>` is mandatory.** Same `_validate_compose()` gate refuses any service without it. Stable names are required so Gatus endpoints, inter-service URLs, and `docker exec`/`docker inspect` keys don't drift per redeploy. Use the bare service name (`browserless`, `gotenberg`, `meilisearch`, `glitchtip-web`, `site-provisioner`, etc.) — never UUID-suffixed names.
- gets one (ruling D-052) — see `core/60-watchdog.md`. Do not author a `watchdog: { enabled: false }` opt-out; if a project genuinely cannot host the sidecar, that is a ruling to obtain, not a default to flip.
- path before the flag goes in the spec, and assert target health (`/api/v1/targets` → `up`), never a bare `curl` of a path you assumed.
- remove it` on the hub) names a plan that protects nothing. Never add a service-named plan.
- health-enabled service can NEVER pass `up -d --wait` on a fresh database, and the deploy hangs to timeout.  An init the deploy cannot perform itself is a runbook step the plan MUST own.
- `fabrik redeploy <app>` SSHes to the VPS and runs `git pull` + `docker compose up -d --wait` against the **GitHub remote**, NOT the local `/opt/<app>` clone. Skipping `git push` redeploys the previous remote commit — the VPS never sees local changes.
**Mandate:** build → release → run are strictly separated. Releases are IMMUTABLE; the git SHA is the release ID. NEVER hot‑patch a running container (no `docker exec` to edit code/config in place, no in‑place code mutation on the VPS). Any change = a new build + a new release via `fabrik apply` / `fabrik redeploy`.
- Runtime database migrations that modify the app container (migrations MUST be run as separate deploy‑time steps)
**Place a service next to its data.** A spoke-hosted service reaches `postgres-main`/`redis-main` over the WireGuard mesh, and that hop is cross-Atlantic (Coventry ↔ LA) on EVERY query — a per-request chatty service pays it hundreds of times per page. So a DB-chatty service targets vps1; a spoke earns a service whose data traffic is light, batched or cached; a service PINNED to a spoke by hardware (GPU) batches or caches its data access — the data never moves off vps1. Measure before choosing (`ping 10.99.0.1` from the spoke, and the request's query count), never assume — the correctness rule ("container DNS, never localhost") says nothing about latency.
**Mandate:** WSL dev and the VPS run the SAME backing services (PostgreSQL + Redis), same major version. NEVER substitute a different backing service in dev (no SQLite standing in for Postgres, no in‑memory dict standing in for Redis). The same code must run unmodified in both environments.
- WSL runs PostgreSQL + Redis at the SAME MAJOR as the VPS containers — probe the live truth, never copy a tag from a doc: `ssh vps "sudo docker inspect postgres-main redis-main --format '{{.Config.Image}}'"` (probed 2026-09-01: the plain upstream PostgreSQL Alpine image at the fleet major recorded in `CLAIMS.yaml` row `pg-fleet-major` · `redis:7-alpine` — upstream official images, outside OUR-image Alpine ban per § Banned Patterns)
**Invariant:** Never use `ports:` in compose.yaml to expose internal services to the host. All external traffic must go through Traefik.
**Health endpoints (`/health`, `/healthz`, `/metrics`, `/api/health`) bypass Authelia on all services** — required for Gatus and Prometheus monitoring. The bypass is **resource-based, not domain-bound** — applies on every domain routed through Authelia (hub direct + spokes via `authelia-vps1@file` middleware). Never protect these paths.
**CRITICAL:** Use `web`/`websecure` in Traefik labels — never `http`/`https` (those entrypoints do not exist). The scaffolder emits the correct entrypoint names; if you hand-write labels, match these exactly.
**Mandate:** migrations and admin tasks run as a ONE‑OFF process against the DEPLOYED image + env — identical environment to regular processes. NEVER run admin tasks from a laptop against prod, NEVER via `docker exec` into a live container, and **ABSOLUTELY NEVER auto-run migrations from app startup/`lifespan`** (concurrent replicas race the Alembic version table → wedged deploy).
- `docker compose run --rm <svc> alembic upgrade head` (against deployed environment) — `<svc>` is a service that declares `.env.owner` (a `migrate` service), never the app service — the owner DSN is not in the app service's environment after the owner split (D-754), and `run` replaces the service's `command`, so a hand-off written there is bypassed
- > **`fabrik run` and `.fabrik/hooks/post-deploy/` do NOT exist** — the real CLI answers `Error: No such command 'run'`, the hook path appears nowhere in the platform, and `_post_deploy_sync()` (`cli.py:64`) only refreshes `data/projects.yaml`; an agent following either ships a deploy where migrations never run. Do not re-add either without a `path:line` in `src/fabrik/` that executes it.
**Processes are share-nothing:** any state shared across requests MUST go to Redis (`redis-main`) with a TTL. A project using Redis for sessions MUST declare `shape.needs_cache: true` in `specs/services/<id>.yaml`, or `fabrik apply` skips the Redis registrar and the deploy is silently broken.
- "A twelve-factor app never relies on implicit existence of system-wide packages"
**Mandate:** any binary the app shells out to (ffmpeg, yt-dlp, poppler, tesseract…) MUST be `apt-get install`-ed in the Dockerfile, with a `shutil.which()` startup probe that fails fast. **The pinned base image is the version boundary** — exact `=version` apt pins are banned: they break on every Debian point release as old debs leave the mirrors (the "works then mysteriously breaks" class this section exists to prevent); the codename pin + image digest give the reproducibility. Never assume `curl`/ImageMagick/ffmpeg exist in the image — they don't by default.

### 12-FACTOR (all twelve axes)
- I codebase: shared code → fabrik-lib, never two apps in one repo
- II deps: every shelled-out binary installed + pinned in the Dockerfile
- III config: granular env vars; no secrets in code; no grouped env sets
- IV backing services: swappable by DSN/config change only
- V build/release/run: releases immutable; never hot-patch a container
- VI processes: stateless; session state → redis-main; no sticky sessions
- VII port binding: bind in-container; Traefik routes; no host ports:
- VIII concurrency: scale out; never daemonize or write PID files
- IX disposability: SIGTERM returns in-flight jobs to the queue; jobs idempotent
- X dev/prod parity: same backing services everywhere; no SQLite-for-Postgres
- XI logs: unbuffered stdout only; the app never writes/rotates a logfile
- XII admin: migrations/one-offs run against the deployed release, never startup

## MATCHED — packs whose globs hit the changed paths

### core/10-python.md  (hit: libs/web_tools.py, scripts/scrape_ledger.py, scripts/sysadmin/emit_mcp_project_config.py)
**`uv`** is the mandated Python package manager. Never use raw `pip`, `pip install`, `poetry`, or `pipenv`.
- Dependencies live in `pyproject.toml` + `uv.lock`. Do not modify these files unless the ticket authorises it.
- its own reviewed commit, never as a side effect of unrelated work.
- The one RULE: use SQLAlchemy async consistently — never mix `async def` with sync `.query().all()` (the Banned table row; the full session pattern is `25-data-postgres.md`'s).
- The canonical `engine`, `async_session`, and `get_db` are defined in `src/database.py` — owned by `25-data-postgres.md`. Import from there, never redefine:
**Config convention:** apps read a complete `DATABASE_URL` (`postgresql+asyncpg://user:pass@host:port/db`) and `REDIS_URL` from env. Discrete `DB_HOST`/`DB_PORT`/`DB_NAME`/`DB_USER`/`DB_PASSWORD` for the app to assemble are **banned**. The env supplies the complete URL — `localhost` in WSL, `postgres-main` on VPS — so the host concern is an env-layer responsibility, never code logic. See `30-ops.md` compose template for how discrete vars are interpolated into `DATABASE_URL` at the compose level.
- volume** (`30-ops.md` § Volumes), never in `.tmp` and never in `/tmp`.
**GlitchTip discipline:** unhandled exceptions (FastAPI 500s) are auto-captured by GlitchTip with full stacktraces. In the `except Exception` branch, log a **short event name + correlation_id** — never `logger.exception()` (that duplicates the traceback in Loki AND GlitchTip). See `55-observability.md` § Error Reporting for the full rule.
**Note:** Use the scaffolded logger: `from {package}.logger import get_logger` (see `55-observability.md` § Pre-Scaffolded Logging). Do not use `structlog.get_logger()` directly or `logging.getLogger(__name__)`.
- **Never a bare `asyncio.create_task()`** — an unreferenced task is silently garbage-collected and its exceptions vanish. Hold the reference and await it, or use `asyncio.TaskGroup`.
- **`datetime.now(UTC)`, never `datetime.utcnow()`** — deprecated and naive; naive datetimes are a real cross-service defect class.
- Type the package, never `.`: the root walks the hub-synced `scripts/`, where mypy finds the same file under two module names and stops on every fresh project. file-worker types `mypy --explicit-package-bases worker`; a `server/` backend (saas-skeleton, static-site, office-extension, chrome-extension, mobile-app) runs `mypy src` from `server/` (D-605).
- Ruff's selected rule-sets MUST include `ASYNC` (blocking IO in async code — machine-enforces this pack's hardest-to-review rule), `B` (bugbear) and `S` (bandit) alongside the defaults; configured in `pyproject.toml`, emitted by the scaffolder.
- Production services run via `uvicorn` CLI in the Dockerfile, not `uvicorn.run()` in code. Base image is always the pinned Debian `-slim` variant on `linux/amd64` (the variant is pinned fleet-wide in `30-ops.md` § Container Base Images — change it THERE, never per-repo). Never use Alpine — musllinux wheels exist now (PEP 656) but coverage is still partial, source builds are dramatically slower, and musl's allocator/stack defaults degrade CPython; the trade never pays on this fleet.
- `uvicorn.run()` is for local development only. Never ship it in production code.
- a fleet scaling decision (more containers), never a per-app flag.
**BANNED: grouped/named env config sets.** 12F is explicit — *"env vars are granular controls, each fully orthogonal to other env vars"* — so a `config/production.yml`, a `settings.production` group, or a `config/{dev,staging,prod}.yaml` tree is a violation. Env vars are granular and set **per deploy**, never batched into a named "environment".
**BANNED:** `logging.FileHandler`, `logging.handlers.RotatingFileHandler`, `TimedRotatingFileHandler`, `loguru` file sinks, any `*.log` file write, any in-app log rotation/retention/cleanup. The app never decides where logs are stored or routed — Docker → Promtail → Loki does. Full rule: `55-observability.md` § Logs.
**Factor XII — Admin processes. NEVER migrate from app startup.**
**BANNED: `alembic upgrade head` in FastAPI's `lifespan`, in an `@app.on_event("startup")`, or as an import side-effect.** With more than one replica (or a restart storm) two containers run `upgrade head` **concurrently** → they race the Alembic version table → duplicate DDL → **wedged deploy**. Migrations are a **one-off admin process against the deployed release**: `docker compose run --rm <svc> alembic upgrade head` (`<svc>` is a service that declares `.env.owner` (a `migrate` service), never the app service — the owner DSN is not in the app service's environment after the owner split (D-754), and `run` replaces the service's `command`, so a hand-off written there is bypassed) (see `30-ops.md` § Release & Admin Processes).
| `alembic upgrade head` in `lifespan` / startup hook | One-off admin process against the deployed release: `docker compose run --rm <svc> alembic upgrade head`, `<svc>` a service that declares `.env.owner` (a `migrate` service), never the app service (D-754) (concurrent replicas race the version table) |

### core/40-documentation.md  (hit: .windsurf/rules/core/57-external-data-sourcing.md, CLAUDE.md, PORTS.md)
- > **⚠️ `docs/OPERATIONS.md` + `docs/DEPLOYMENT.md` are FLEET-AI INTERFACES, not just docs (D-065).**
- **Tier-1 (author → verify → converge; the author leg is NATIVE while the pool is OFF, D-181 — `scripts/doc_reconcile.py`'s pool author cannot dispatch):** for each **mechanically-detectable** doc whose Doc-Sync trigger fired (`docs/QUICKSTART.md` · `docs/CONFIGURATION.md` · `docs/data-contract.md` · `docs/SERVICES.md` · `docs/OPERATIONS.md` — the reliable-signal subset), `scripts/doc_reconcile.py` dispatches a cheap OpenRouter-pool author (`libs.subagents`, `pick_models("docs")`) to emit a **minimal structured patch**, **verifies it before applying** (a symbol cross-check catches invented endpoints; the orchestrator injects a higher-assurance native-Claude verify), and loops to a zero-edit round. Runs per phase in `/fabrik-execute-plan`; never blocks (fail-safe). The other docs (CHANGELOG, INDEX, FEATURES, RESILIENCE, PORTS, the READMEs, `db/schema.sql`, …) have no reliable mechanical content-signal → they rely on the touch-on-change backstop below + your own edit (force-update, not force-correct).
- The SSOT is the type-aware registry (`scripts/enforcement/_doc_registry.py::PROJECT_DOCS`) — this table is its project-facing rendering, kept in step, never a second truth. `/fabrik-plan-after-chat` (the plan set's spine + tickets — the ticket-format authority) injects these rows per ticket as its `Docs:` line.
- Standalone work (not plan execution) → `Agent-Role: primary`. Trailers go below a blank line, above `Co-Authored-By`. ⚠️ The trailer block must be its OWN paragraph with NO blank line inside it: git parses only the LAST paragraph, and only if it is all-trailers. A blank line before `Co-Authored-By:` demotes everything above it to prose; so does a prose line glued to the top of the block. Measured 2026-08-15: 200 of the last 200 hub commits carried `Agent-Role:` and only 10 parsed, because the old example here shipped the blank line.
- **⚠️ Link it or it is decoration.** *Measured:* requests for files that do NOT exist came ~zero from AI bots — agents never go looking. It follows (inference, not measurement) that a file only gets read when something points at it: reference it from the docs index or README.
- ⚠️ **In the hub (`/opt/fabrik`) `llms.txt` is GENERATED** (`scripts/generate_capability_index.py`, refreshed daily) — never hand-edit it there; change the generator. A project has no such generator; an `llms.txt` it ships, hand-written or built by its own code, is its own.
- either way. Cheap and reversible — never at the expense of `OPERATIONS.md`/`DEPLOYMENT.md`, which are the load-bearing agent interfaces (D-065).
- **No skipped heading levels** — `##` to `###`, never `##` to `####`
- **Fenced code blocks only** — never indented code (AI treats it inconsistently)

### core/45-testing-strategy.md  (hit: tests/test_emit_mcp_project_config.py, tests/test_firecrawl_proxy_basic.py, tests/test_researcher_fallback_contract.py)
- **Behavior Contract**: every ticket enumerates its distinct **user-observable behaviors / acceptance criteria** and tests **each one** — one high-value integration/E2E test per behavior, risk-ordered, TDD for the risky ones. Skip trivia (getters / framework glue / config): **lean-but-complete, NOT 100%-line-coverage dogma**. Do not chase line coverage — ensure every behavior has a test that would fail if that behavior regressed. (Cheap pool subagents can author the per-behavior tests — the suggest→curate→author→fix workflow in `62-using-subagents.md` § Dispatch policy + `~/.claude/commands/fabrik-review.md`.)
- **No cosmetic assertions**: never assert against CSS classes, Tailwind utility strings, pixel measurements, or snapshot hashes. Assert application state and user-visible outcomes only.
- **Watched-fail-first** (for tests this change adds or modifies; trivia stays skipped per the Behavior Contract): a non-trivial behavior's test proves something only if it has been SEEN RED — either write it first and watch it fail, or (after the fact) neuter the fix/feature, prove the test goes red, then RESTORE and re-run to green. The neutered state is never staged, committed, or left in the tree. A green test never seen red is unverified — a suite can pass with its guard deleted.
- **Run tests**: `uv run pytest tests/` (never bare `pytest` — Fabrik uses `uv`) — **when the project has a `pyproject.toml`/`uv.lock`**. A subagent seat runs no package-manager verb and runs `.venv/bin/python -m pytest` instead (`10-python.md` § Package Manager). A `requirements.txt`-only project (no manifest) runs `.venv/bin/python -m pytest tests/` — the manifest clause chooses the RUNNER, it never disarms the mandate to run the suite (web-ecommerce-factory 01M1QEY5, 2026-09-05: the clause read as "does not apply here"). ⚠️ **Gate this on the manifest, because this line is FLOOR-injected into finder prompts and a vendored fabrik-lib MODULE has neither by design**: the module recipe ships `requirements.txt` (`fabrik-lib/README.md` § Creating a Reference Implementation), so `uv run` cannot … (wrapped further — read the pack)
- **Zero-mock database policy**: never mock SQLAlchemy, SQLModel, or database sessions. All backend tests execute against a real PostgreSQL instance.
- **`ASGITransport` never runs lifespan** — anything the app initializes at startup (scaffolded apps are lifespan-based) silently does not exist in tests; wrap with `asgi-lifespan`'s `LifespanManager` when a test needs startup state.
- Use `structlog` in test helpers if logging is needed — never `print()`. See `55-observability.md`.
- **Never stub a server action from Playwright** — the server is the E2E boundary; stubbing belongs in the unit lane where the action is a plain function.
- Run Playwright against the PRODUCTION build (`next build && next start`), never the dev server.
- All locators must be **semantic**: `page.getByRole('button', { name: /submit/i })`. Never use CSS selectors or XPath.
- Launch Playwright's **bundled Chromium** (`channel: 'chromium'`) — stable Chrome/Edge removed the `--load-extension` / `--disable-extensions-except` side-load flags (Chrome 137/139), so those args only work under bundled Chromium, never installed stable Chrome.
- Run `@axe-core/playwright` with **`bypassCSP: true`** (the non-relaxable extension CSP otherwise makes axe throw on `chrome-extension://` pages); keep `@axe-core/playwright` a **dev-dependency only** (MPL-2.0 — never bundled into the shipped artifact). Gate bundle size with `size-limit` **per surface** (popup / side-panel / content-script). Full loop: `chrome-ext/70-chrome-ext.md` § Testing & UI Verification.
- Keep the generated types committed and re-generate on schema changes (`uv run python -c "import json; from <package>.main import app; print(json.dumps(app.openapi()))" > openapi.json` — the scaffold emits `src/<package>/main.py`, never a flat `src/main.py`, so `src.main` imports nothing).
**BANNED in tests:**
| A GUARD proven only by the ONE spelling of the defect you already fixed | Write the guard's subject five LEGITIMATE ways — five a DIFFERENT author would plausibly write, not five typos of yours — and count how many it still catches; one of five means it is keyed on your fix, not on the class — and one of five is the FLOOR of the failure, never its definition: four of five is a partial class and is reported as four of five. This is IN ADDITION to red-on-revert below, not a rival bar: that one proves the guard fires at all, this one proves it fires on the class. ⚠️ Cheapest ways to satisfy it WITHOUT the outcome (`CLAUDE.md` § UNIVERSAL governance markers, the entry whose anchor is **you get the behavior you measure** — search the ANCHOR, not the rule name: the project-facing contract lists that section by anchor alone and carries the name `cobra-effect` nowhere): (i) write five near-identical spellings and count 5/5; (ii) ship at 2/5 and REPORT it, needing no fabrication at all, in the hope that a reported count reads as a passed one — it does not: under 5/5 is a finding; (iii) claim the exercise and record nothing, since the five are never committed. So the bar is TWO things and needs both: **the five go IN the test file as executable CASES**, never a comment — a comment cannot go RED, so nothing can falsify it, and that is the objection, not that it records nothing — **and anything under 5/5 is a finding, not a pass**. ⚠️ Two paths this row does NOT close, stated rather than pretended away: you can shrink the SUBJECT until five legitimate spellings all land inside what the guard already catches (nothing is fabricated; the claim narrowed, not the guard), and an honest 4/5 — real information, 80% of the class — costs the author something to report, so the cheapest response to it is silence. Report the count you got either way — a 4/5 with the miss NAMED is a finding someone can act on, and a 5/5 nobody can execute is not a pass at all. Measured 4× in one day across 2 repos (01M1S4D78KRM0ZSYDNGTHS9HYQ), and once more the day this row landed: a contract-parity grader that read the LIVE file instead of the tree under test stayed green under the exact drift it existed to catch |
| A test THIS change adds/modifies that was never seen red (no fail-first, no red-on-revert proof) | Watch it fail first, or neuter the change → prove red → restore → re-run green |
- [ ] Destructive DB tests pass the throwaway guard before connecting — `require_throwaway(TEST_DATABASE_URL)` where the scaffold emitted `tests/conftest.py`; where it did not (an unscaffolded repo has no such helper), this anchored predicate, verbatim: `dbname = urlparse(url).path.lstrip('/'); assert dbname.lower().endswith(('_test', 'throwaway', 'scratch')), dbname` — never point them at a dev/shared DB.

### core/57-external-data-sourcing.md  (hit: docs/reference/fabrik-scrape-mcp.md, libs/web_scrape_mcp/, scripts/scrape_ledger.py)
- API clients, connectors, webhook handlers). ⚠️ `58-resilience` does NOT auto-load on `connectors/`, `ingest/`, `webhooks/` or `scrapers/` paths — when this pack fires, read 58 explicitly; every rule below that says "the 58 contract" assumes you have.
**Never scrape when an API exists** — an API is a contract you can PROFILE (limits, resume, deprecation channel) and be authorised under; a scraper has no contract, breaks on markup change, and may violate ToS. (APIs still deprecate and break — field 10 exists because they do.)
- ⚠️ **Two lanes, and conflating them is the mistake this ladder invites.** An MCP server is an
- ⚠️ **Check the roster before naming one — do not cite from memory**: the roster is SPLIT (user-level + per-repo `.mcp.json`), canonical at `/opt/fabrik/docs/workstation/mcp-roster.md`, probed by `python3 /opt/fabrik/scripts/sysadmin/mcp_health.py`.
- (pluggable, Anti-Captcha — ⚠️ a BYPASS capability, not a default; see § Hard constraints, "the bypass line") · `adaptive-dispatch` (learns which fetch strategy works per domain) · `web-tools` (env-keyed Exa/Brave/Firecrawl executors — the RUNTIME answer to rung 1) · `proxy-pool` (Postgres-backed proxy pool — ⚠️ same caveat as `captcha-solve`: a bypass capability, never a default) · `api-quota` (`QuotaTracker` parses rate-limit headers, persists quota state and gates calls at the cap; `KeyPool` rotates across many keys — the RUNTIME half of profile fields 1, 2, 7 and 9) · `webhooks` (**outgoing** delivery with HMAC signing — it does … (wrapped further — read the pack)
- (⚠️ OpenRouter-only, see § Hard constraints), `ai-image`, `ai-audio`, `ai-translate`, `search`, `scrape`, `captcha`, `proxy`, `domains`, `email`, `storage`, `backup`, `research-data`, `media-stock`, `infra-platform`, `comms`, `dev-tools`, `unidentified`.
**Derive the count and the category set from the FILE, never from this list** — the file has a non-dict `_README` key, so the guard is not optional: `python3 -c "import json,collections;d=json.load(open('scripts/service_catalog.json'));print(collections.Counter(v['category'] for v in d.values() if isinstance(v,dict)))"`. Grep it by `category` before adding any new vendor; detailed contracts live in `docs/reference/apis/**`. Key via env var, never in code.
**An UNKNOWN never waives the design decision — design to the conservative reading**: unknown cap behaviour ⇒ assume silent truncation and verify counts yourself; unknown idempotency ⇒ assume non-idempotent; unknown resume ⇒ checkpoint on your side; unknown health signal ⇒ treat every 5xx burst as *possibly them* and pause rather than hammer; unknown key expiry ⇒ rotate on a schedule anyway; unknown deprecation channel ⇒ watch the headers; unknown schema stability ⇒ validate strictly at the boundary.
| 4 | **Identity posture** — limits per-key, per-account or per-IP? does the ToS permit multiple accounts/orgs — **cite the clause + URL, or UNKNOWN** | decides whether horizontal scale is even available — see the ⚠️ below |
| 9 | **Credential lifecycle** — does the key/token EXPIRE, on what schedule; can it be rotated with an overlap (two keys valid at once) or only by a hard cut; what does an expired key LOOK like (401? 403? a silent empty 200?) | decides whether rotation can be automated at all, and whether the connector can even tell a dead credential from a dead vendor — an expired key is the failure a retry loop can never fix |
| 11 | **Data contract + EXPECTED YIELD** — the response schema pinned at profile time, and the yield the surface must return; what the vendor changes WITHOUT a version bump (nullable flips, new enum values, added fields, pagination shape); freshness/lag and eventual-consistency window; how deletion shows (tombstone vs vanish); a sample kept for diffing | decides the validation posture: a `200` with a different shape is the failure that corrupts silently — outages page you, drift does not ⚠️ **and the EXPECTED YIELD per page** — a number, or `0 is terminal` — and terminal is a POSITION, never a surface. Zero rows is the contract only where a predecessor proves you are past the data: page N+1 after page N returned rows, a delta past a non-empty cursor, a section index that listed N items. Zero on the FIRST page or a cold cursor is a failed fetch ONLY where the surface also states a `≥1` floor for that position — a listing whose first page always has rows. It is NOT a failure on a search or a filtered section, where an empty first page is the honest answer; those declare `0 is terminal` and nothing else. The incident this closes is the listing case: a challenge page on page 1 of a surface that promised rows, read as "crawl complete, 0 rows". A zero-row page is only a failure against a stated `≥1`; undeclared, it is not one (the scraper-failure-classes bullet under § The Capability Profile). |
- ⚠️ **Field 4 is where an operational question becomes a legal one.** Asking "are multiple accounts permitted, and are limits per-key or per-IP?" is ordinary capacity planning, and the answer is sometimes an explicit yes (separate billing orgs, per-project keys). Provisioning extra accounts or rotating IPs **in order to evade a cap the vendor set** is the circumvention shape from § Hard constraints, and it is an operator decision with the ToS quoted — never an engineering convenience. (That exit is legitimate here on the contractual-gate ground — an authorisation, not a menu.) Record what the ToS actually says; do not infer permission from the absence of a block.
- expiry never happens in production; the `58` last-resort rung that died of an expired credential is this row unfilled.
- model (pydantic `strict=True` / zod `.strict()`, unknown keys rejected deliberately), never silently drop an invalid record, and export the invalid-record RATE as a metric — a spike is the upstream change announcing itself, and a `missing` cluster on one field says which one.
- signature outside the timestamp tolerance. ⚠️ **And it runs a reconciliation poll** — a scheduled pull of "what did you send since <cursor>" against the vendor's list endpoint — because a delivery the provider gave up on during your deploy is otherwise unrecoverable by construction. No list endpoint in field 12 ⇒ say so, and treat every missed webhook as a known gap in §9.
- row 22 alarms on, never the fetch count. A **bot-block** (`403`, a challenge page) is a pause condition, not a retry and not a bypass: `58` says never retry a 403, and § Hard constraints says never solve the challenge — the legal move is `adaptive-dispatch`'s strategy switch (static → rendered), then a pause, then an operator decision.
- ONCE, never hot-looping, and named as human-gated in §2b so nobody expects the queue to wake itself.
- ⚠️ **One subject, one home.** The profile records the VENDOR's contract (measured, dated). YOUR handling of it — timeout/retry config, fallback, pause keys — stays in the per-dependency detail card in `docs/RESILIENCE.md`; that card LINKS the profile and never copies its numbers.
- ⚠️ **Not gate-enforced yet, deliberately — and measured 2026-09-02: 0 of the 6 hub vendor docs in `docs/reference/apis/` carry a profile.** This is a new obligation; per the FIX directive a detector ships after its fire rate is measured, not before. Until then the profile's teeth are the `Profile:` line on the dependency's card in `docs/RESILIENCE.md` — **§2b where the doc has one, otherwise the project's equivalent per-dependency row or section** (the scaffold template does carry the slot, verified at `templates/scaffold/docs/RESILIENCE_TEMPLATE.md:63` § 2b Detail Card Per Dependency, whose first field is `Profile`; but a project scaffolded before it, or one whose … (wrapped further — read the pack)
- **LLM data = OpenRouter ONLY** — never a direct vendor LLM SDK (`openai`, `@anthropic-ai/sdk`). Non-LLM vendor APIs are fine directly.
- **Vendor keys are env vars** (`os.getenv`), never constants; the repo must stay open-sourceable (12F-III).
- Honour a TDM reservation even when your own UA is not the one named. ⚠️ **The token set churns and vendors now run SEVERAL bots each** — Anthropic retired `anthropic-ai` and `Claude-Web` for `ClaudeBot` (training) / `Claude-User` (user-initiated fetch) / `Claude-SearchBot` (indexing), and OpenAI/Perplexity document their user-initiated fetchers (`ChatGPT-User`, `Perplexity-User`) as *not* governed by robots.txt. Read a site's file for the group matching YOUR token, not a 2024 block-list. The machine-readable successor is the IETF AIPREF `Content-Usage` rule (robots.txt directive + HTTP header, a draft that updates RFC 9309 if approved) — honour it … (wrapped further — read the pack)
- **⚠️ THE BYPASS LINE IS THE LEGAL LINE, and it runs straight through our own toolbox.** Reading a logged-out public page is a different act from defeating a control. The moment a pipeline solves a CAPTCHA, replays a session, rotates IPs to beat a block, or evades a hard rate limit, it leaves "public data" territory — and the live litigation wave targets the
- catalog's `proxy` and `captcha` categories are therefore **capabilities, never defaults**: reach for them only where a human operator has decided the specific source warrants it, and say so in the plan.
- on a page you never agreed to are weak against a logged-out fetcher; terms you click through, or accept by creating an account, are an ordinary contract and scraping in breach of them is a straightforward claim. So "we have an account there" changes the answer — check before assuming the public-page reasoning applies.
- ⚠️ **Where the profile lives differs between hub and project** — `EXTERNAL_SYSTEMS.md` is a hub-only index; do not send a project at it.
- `cost` · `capability` · `url` · `status` · `match` · `hosts` · `merged_match`), never the envelope — the twelve profile fields live in the vendor doc, dated and re-verifiable.
- the handler, never onto Authelia. It does not ride the health-path bypass either. **The mechanism is the spec, not a hope:** route the receiver under the service's `shape.bearer_bypass_prefix` (a path-regex, default `^/api/` for `has_bearer_api` services, narrowable) — that IS the explicit public route; there is no per-path bypass field to invent. An UNSIGNED provider that must write cross-tenant is the `needs_payments_ingest` shape.

# promote-to-check_*: 104 injected mandate(s) look deterministically greppable — their backtick literals, one line each (the full mandates are ABOVE, not repeated: re-emitting ~20 FLOOR lines verbatim doubled the rubric and got it skimmed — web-ecommerce-factory 01M1QEY5, 2026-09-05)
- `fabrik-lib/fastapi-user-auth` `DELETE … RETURNING` `jti` `agents-fabrik.md § Supabase`
- `chrome-extension` `chrome.identity.launchWebAuthFlow` `https://<ext-id>.chromiumapp.org/` `chrome.storage.session`
- `desktop-app` `safeStorage` `desktop-app/72-desktop.md`
- `fabrik` `X-Internal-Token` `internal_auth.py` `hmac.compare_digest` `APIKeyHeader`
- `auth.uid()` `current_tenant_id()` `NULL` `EXCEPTION WHEN OTHERS THEN RETURN NULL` `SELECT auth.uid()` `NULL`
- `openssl rand -hex 32`
- `algorithms=["HS256"]` `alg` `alg: none`
- `redis-main`
- `expo-secure-store` `80-mobile.md`
- `localStorage` `sessionStorage`
- `chrome.storage.session` `TRUSTED_CONTEXTS` `chrome.runtime.sendMessage` `chrome.identity.launchWebAuthFlow` `code_verifier` `crypto.subtle` `storage.session`
- `x-middleware-subrequest` `middleware.ts` `proxy.ts` `middleware.ts`
- `CORSMiddleware` `allow_origins`
- `X-Frame-Options: DENY` `frame-ancestors`
- `APIKeyHeader` `require_api_key` `SERVICE_API_KEY` `PROXY_API_KEY` `python-api` `internal_auth.py` `metrics.py` `/metrics` `SERVICE_INTERNAL_SECRET_KEY`
- `os.getenv("KEY", "default")` `config/production.yml` `settings.production`
- `POST /auth/passwordless/request` `AUTH_PASSWORDLESS_REQUEST_CAP` `AUTH_PASSWORDLESS_IP_REQUEST_CAP` `POST /auth/passwordless/verify`
- `expo-secure-store`
- `shape.is_admin_dashboard: true` `two_factor` `fabrik apply` `/health` `/metrics` `saas/60-saas-ui.md` `shape.has_bearer_api: true` `two_factor`
- `^/api/` `/api/*` `/api/v1` `/api/*` `shape.bearer_bypass_prefix: "^/api/v1"` `fabrik apply` `^/` `orchestrator/verifier.check_api_bypass` `/api/*` `^/api/`
```

## Evidence

### Phase A

`commands/_agents/fabrik-researcher.md:35`, `commands/_sources/fabrik-spec.md:145`. Every Firecrawl scrape or crawl
line, then per-file counts, then the `proxy: "basic"` count (none) — `rg -n` / `rg -c` over the two directories:

```text
commands/_agents/fabrik-researcher.md:35:     FOUND re-fetch the page with `mcp__firecrawl__firecrawl_scrape` and `maxAge: 0` (a live fetch).
commands/_agents/fabrik-researcher.md:37:     FIRST instead — `mcp__firecrawl__firecrawl_scrape` with `formats: ["query"]`,
commands/_agents/fabrik-researcher.md:86:     `mcp__firecrawl__firecrawl_scrape` with `maxAge: 0` (a live fetch) also answers 404 — then it is `DEAD`
commands/_agents/fabrik-researcher.md:121:- **Library/API docs:** `WebFetch` the library's OFFICIAL docs site to find and read the page — but on an HTML docs page a schema field or a parameter name is quoted from the raw arm (rule 1: exa's fetch, then `mcp__firecrawl__firecrawl_scrape` with `maxAge: 0`; the page's `.md` source when the site publishes one), never from a WebFetch answer alone, which has stated fields the page does not carry (a /fabrik-spec run, 2026-10-06: three invented facts); JSON/XML and version claims keep rule 3's routing (no docs-summariser MCP is wired; the roster history lives in `docs/workstation/mcp-roster.md`).
commands/_sources/fabrik-spec-review.md:77:`mcp__firecrawl__firecrawl_search`/`firecrawl_scrape` (on the official library docs; `WebFetch` only to locate a page) → the `gh` CLI to read
commands/_sources/fabrik-spec-review.md:89:(`raw.githubusercontent.com`, view-source, `firecrawl_scrape` with `maxAge: 0` — firecrawl reuses recently indexed
commands/_sources/fabrik-plan-after-chat.md:221:  `mcp__firecrawl__firecrawl_search` / `firecrawl_scrape`** (and official-docs `WebFetch` for library detail). Capture the
commands/_sources/fabrik-spec.md:140:  `mcp__firecrawl__firecrawl_search` / `firecrawl_scrape` on the library's OFFICIAL docs site for framework/API detail (`WebFetch` only to locate
commands/_sources/fabrik-spec.md:145:- Capture the **real** endpoint / signature / auth model / limits / pricing from a RAW fetch (`firecrawl_scrape`
commands/_sources/fabrik-spec.md:262:  **actually fetch it this session** (`WebFetch` / `firecrawl_scrape`) — a claim you didn't
commands/_sources/fabrik-spec.md:264:  `firecrawl_scrape` with `maxAge: 0`, a live fetch) and match the string — normalising whitespace first (raw HTML wraps lines
commands/_sources/fabrik-vision.md:572:  `mcp__firecrawl__firecrawl_search`/`firecrawl_scrape` → `mcp__context7` (library docs) → `mcp__github`
commands/_sources/fabrik-spec-review.md:2
commands/_sources/fabrik-plan-after-chat.md:1
commands/_sources/fabrik-vision.md:1
commands/_agents/fabrik-researcher.md:4
commands/_sources/fabrik-spec.md:4
proxy-basic count above (empty = 0 files)
```

Pre-pin prototype v5 of Phase A's grader (`proto_grader5.py`; the strict literal rule of Phase A step 1, its
negation and mode lists widened by plan-review passes 4-5), run read-only on today's sources — 17 mentions on 16
lines lack the pin (the 12 above plus researcher `:22`, `:149`, `:150`, `:154`; `fabrik-spec-review.md:89` holds
two), and all 36 fixtures are judged as listed:

```text
mentions 17, missing the pin 17
  commands/_sources/fabrik-plan-after-chat.md:221
  commands/_sources/fabrik-spec-review.md:77
  commands/_sources/fabrik-spec-review.md:89
  commands/_sources/fabrik-spec-review.md:89
  commands/_sources/fabrik-spec.md:140
  commands/_sources/fabrik-spec.md:145
  commands/_sources/fabrik-spec.md:262
  commands/_sources/fabrik-spec.md:264
  commands/_sources/fabrik-vision.md:572
  commands/_agents/fabrik-researcher.md:22
  commands/_agents/fabrik-researcher.md:35
  commands/_agents/fabrik-researcher.md:37
  commands/_agents/fabrik-researcher.md:86
  commands/_agents/fabrik-researcher.md:121
  commands/_agents/fabrik-researcher.md:149
  commands/_agents/fabrik-researcher.md:150
  commands/_agents/fabrik-researcher.md:154
OK  want 0 got 0: '`firecrawl_scrape` with `maxAge: 0` and `proxy: "basic"`.'
OK  want 0 got 0: '`firecrawl_crawl` with `"proxy": "basic"` in scrapeOptions.'
OK  want 0 got 0: "`firecrawl_scrape` with `proxy: 'basic'`."
OK  want 0 got 0: '`firecrawl_scrape` (e.g. a docs page) with `proxy: "basic"`.'
OK  want 0 got 0: '`firecrawl_scrape` on v2.1 pages with `proxy: "basic"`.'
OK  want 0 got 0: '`mcp__firecrawl__firecrawl_search` for a query.'
OK  want 1 got 1: '`firecrawl_scrape` with `maxAge: 0`. Later: `proxy: "basic"`.'
OK  want 1 got 1: '`firecrawl_scrape` but never `proxy: "basic"`.'
OK  want 1 got 1: '`firecrawl_scrape` with `maxAge: 0` and without `proxy: "basic"`.'
OK  want 1 got 1: '`firecrawl_scrape` with no `proxy: "basic"`.'
OK  want 1 got 1: '`firecrawl_scrape` with `proxy: "stealth"` instead of `proxy: "basic"`.'
OK  want 1 got 1: 'use ``a`b`` here. `firecrawl_scrape` with `maxAge: 0`. Later `proxy: "basic"`.'
OK  want 1 got 1: '`firecrawl_scrape` must never, under any circumstance at all, carry `proxy: "basic"`.'
OK  want 1 got 1: '`firecrawl_scrape` with `proxy: "basic"` is not needed.'
OK  want 1 got 1: '`firecrawl_scrape` with `proxy: "basic"` never set.'
OK  want 1 got 1: '`firecrawl_scrape` on plan A. Later `proxy: "basic"`.'
OK  want 1 got 1: '`firecrawl_scrape` on attempt 2. Later `proxy: "basic"`.'
OK  want 1 got 1: '`firecrawl_scrape` (not exa) with `proxy: "basic"`.'
OK  want 1 got 1: '`firecrawl_scrape` with no cache and `proxy: "basic"`.'
OK  want 1 got 1: '`firecrawl_scrape` with `proxy: "basic"` (never `proxy: "auto"`).'
OK  want 1 got 1: 'settled by firecrawl `maxAge: 0`, else the verdict'
OK  want 1 got 1: 'settled by firecrawl\n  `maxAge: 0`, else the verdict'
OK  want 1 got 1: 'firecrawl (with `maxAge: 0`) is that read'
OK  want 1 got 1: 'a Firecrawl scrape with `maxAge: 0`'
OK  want 1 got 1: '`firecrawl_batch_scrape` over the list'
OK  want 1 got 1: '`firecrawl_scrape` cannot take `proxy: "basic"`.'
OK  want 1 got 1: '`firecrawl_scrape` doesn\'t need `proxy: "basic"`.'
OK  want 1 got 1: '`firecrawl_scrape` with `maxAge: 0`, skipping `proxy: "basic"`.'
OK  want 1 got 1: '`firecrawl_scrape` must avoid `proxy: "basic"`.'
OK  want 1 got 1: '`firecrawl_scrape` with `proxy: "basic"` except on a retry.'
OK  want 1 got 1: '`firecrawl_scrape` with neither `maxAge: 0` nor `proxy: "basic"`.'
OK  want 1 got 1: '`firecrawl_scrape` with `proxy: "basic"`, or the stealth proxy on a retry.'
OK  want 1 got 1: '`firecrawl_scrape` with `proxy: "basic"` and then auto mode if it fails.'
OK  want 1 got 1: 're-fetch the page with Firecrawl scrape (a live fetch).'
OK  want 1 got 1: '`firecrawl_scrape` doesn’t need `proxy: "basic"`.'
OK  want 0 got 0: 're-fetch the page with Firecrawl scrape and `proxy: "basic"`.'
fixtures 36/36
```

### Phase B

`scripts/sysadmin/mcp_defs.json:28`, `/etc/systemd/system/fabrik-citation-verifier-mcp.service` (the precedent unit,
lines 6-13), then the `mcp_defs.json` entry, then the 80xx listeners (`ss -ltn`) — 8034 is free:

```text
[Service]
Type=simple
User=ozgur
WorkingDirectory=/opt/fabrik-citation-verifier
Environment=FABRIK_CITATION_VERIFIER_URL=http://127.0.0.1:8032
Environment=FABRIK_MCP_HTTP_HOST=127.0.0.1
Environment=FABRIK_MCP_HTTP_PORT=8033
ExecStart=/opt/fabrik-citation-verifier/mcp_server/.venv/bin/python -m mcp_server.server_http
    "fabrik-citation-verifier": {
      "type": "http",
      "url": "http://127.0.0.1:8033/mcp"
    },
0.0.0.0:8031
0.0.0.0:8032
127.0.0.1:8033
127.0.0.1:8040
```

### Phase C

`CLAUDE.md:302`, `tests/test_research_tier_order.py:22`. The two contract fetch sentences, the researcher's
`mcpServers` line and the closed tier-1 set (`grep -n`):

```text
CLAUDE.md:302:2026-09-22, D-337 as refined by D-338): tier 1 is `WebSearch` → `WebFetch` or `brave-search` — any of them; **when they fail or do
templates/governance/CLAUDE.md:276:2026-09-22, D-337 as refined by D-338): tier 1 is `WebSearch` → `WebFetch` or `brave-search` — any of them; **when they fail or do
4:mcpServers: [exa, brave-search, firecrawl]
22:_TIER1 = r"(?:`WebSearch`|`WebFetch`|`mcp__brave-search__brave_web_search`)"
```

## Pass Ledger

| Pass | seats · axes | counters | method | plan md5 (start → end) |
|-----:|---|---|---|---|
| 1 | opus-1 (Phases A and C, Global Constraints, Digest, Coverage, Evidence, File Scope) · sonnet-1 (the rest) | findings 25 · confirmed 23 (sonnet 9; opus 14 new, 2 duplicates of sonnet's capability-ledger and rule-57 rows) · refuted 0 | each claim executed by the lead: 406 on a bare GET to :8033, `emit_mcp_project_config.py:39-46` UNIVERSAL6, `assemble_commands.py:1171` non-live `--dest`, the v2 grader's six fixtures and 15-line corpus run, the researcher subagent `meta.json` `agentType` field | 68dad3bf → e9fcc3f7 (pins-2) |
| 2 | the same two seats, each re-verifying its own slice over the pass-1 fix diff plus one hop | findings 8 · confirmed 7 (opus: grader fail-open spellings, Fallback-row contradiction with spec :219-225, emitter test outside scope, Global Constraints vs the emitter's writes, and P-opus-4/P-opus-16 still true; sonnet: emitter test (duplicate) and the emitter's `--check` / `--root /opt`) · 5 of them inside text round 1 added · refuted 0 | lead executed: `proto_grader3.py` 16/16 fixtures and a 16-line corpus run, spec :217-227 and :245-249 read, `tests/test_emit_mcp_project_config.py:24/:42/:47`, emitter `:331`/`:334`, `CLAUDE.md:306` and template `:280` | e9fcc3f7 → 17da142e (pins-3) |
| 3 | the same two seats, each over the pass-2 fix diff plus one hop | findings 3 · confirmed 2 (opus: P-opus-4 wrapped `maxAge` spelling, P3-opus-1 the negation window misjudged both ways — both inside grader text this review wrote) · refuted 1 (opus note: emitter `--root`/`--check` at `:331`/`:334`, re-read, correct) · sonnet 0 | lead replaced the negation heuristic with a strict literal rule that fails closed (`proto_grader4.py`, 25/25 fixtures, 17 mentions on 16 lines); Coverage Checklist adjudicated, 13 of 13 | 17da142e → 5225c266 (pins-4) |
| 4 | opus-1 alone (the only slice the pass-3 fix touched), the pass-3 fixed set after the scope-growth stop | findings 2 · confirmed 2 (P4-opus-1: negations and modes in other words and a prose mention pass the v4 grader; P4-opus-2: the behavior-without-a-test verdict overstated) · both inside text this review wrote · refuted 0 | lead: v5 lists widened (35/35 fixtures, corpus unchanged at 17); presence is the grader's scope, meaning is Phase A step 7's named check; the Coverage verdict restated; the prototype now pinned beside the plan | 5225c266 → 60b32e6d (pins-5) |
| 5 | opus-1 alone, the pass-4 fixed set with the prototype pinned beside the plan | findings 2 · confirmed 2 (P5-opus-1: a typographic apostrophe in n't; P5-opus-2: the prototype docstring still described v4) · both minor, inside text this review wrote · refuted 0 | lead: `n['’]t`, docstring names the constants, the meaning check made standing in the test's message (the seat's design judgement, adopted); 36/36 fixtures, corpus 17 | 60b32e6d → (pins-6) |

## Self-audit

- Grounding run: every anchor above was read this session (Evidence blocks are the captured outputs); the two packs
  in the must-read set were read by a seat and each quoted line re-read with `sed -n` before the Digest was written.
- (a) Coverage: each "What we already agreed" item → Phase A (proxy pin), Phase B (server, registration, call-log
  re-vendor), Phase C (ledger, switch, contract sentence); slices 1b-1d and other commands are named OUT-OF-SCOPE.
- (b) Cross-phase consistency: Phase B produces `fabrik-scrape` at `127.0.0.1:8034/mcp`; Phase C consumes that exact
  name and URL; Phase A's grader is consumed by Phase C's gate.
- Fixed point: not claimed — `/fabrik-plan-review` converges this DRAFT.

## Residual unknowns

| Unknown | Resolution step |
|---|---|
| the exact layout and vendor steps of `web-scrape-mcp` | resolved at Phase B step 1 from fabrik-lib's merged README; the start condition waits for it |
| the server's env-var names for host and port | Phase B step 4 uses the module's own names from its README; `FABRIK_SCRAPE_HOST`/`_PORT` are the default if it names none |
| whether the researcher's ledger is all-pass | Phase C step 4 decides; a FAIL keeps Firecrawl and files a fabrik-lib ask |
| the operator's approval of the unit install | Phase B step 5, boarded through the coordinator as a gate |

## File Scope (owned paths)

- tests/test_firecrawl_proxy_basic.py
- commands/_sources/fabrik-spec.md
- commands/_sources/fabrik-spec-review.md
- commands/_sources/fabrik-plan-after-chat.md
- commands/_sources/fabrik-vision.md
- commands/_agents/fabrik-researcher.md
- libs/web_scrape_mcp/
- libs/web_tools.py
- scripts/sysadmin/mcp_defs.json
- scripts/sysadmin/systemd/fabrik-scrape-mcp.service
- docs/reference/fabrik-scrape-mcp.md
- docs/workstation/mcp-roster.md
- PORTS.md
- scripts/scrape_ledger.py
- tests/test_scrape_ledger.py
- scripts/sysadmin/emit_mcp_project_config.py
- tests/test_emit_mcp_project_config.py
- tests/test_researcher_fallback_contract.py
- .windsurf/rules/core/57-external-data-sourcing.md
- CLAUDE.md
- templates/governance/CLAUDE.md
