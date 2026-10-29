# Plan — the external-services inventory, rendered by one page-layer function into the board and the chain's file (W-3e9e2f4c)

Status: EXECUTED 2026-10-18
Whole-plan review: docs/development/reviews/2026-10-18-plan-1-external-services-inventory-review.md
**Owner:** infra

Spec: `docs/superpowers/specs/2026-10-18-external-services-page-design.md` — CONVERGED, approved by the Opus + Fable panel
(D-966, md5 0c163da4764296f37aa3fd9c62cd633f at c4e827715). Spec review receipt:
`docs/development/reviews/2026-10-18-external-services-page-spec-review.md`. Research ledger:
`docs/reference/research/2026-10-18-external-services-page-ledger.md`. Work item W-3e9e2f4c (P2, the one major project in
flight). Parent: `docs/superpowers/specs/2026-10-16-command-centre-dashboard-design.md` (D-925), whose DT2 (:471) makes a
spec's § The design the board's UI contract — the hub has no `docs/ui-design.md` and none is written here. Out of scope:
W-7e467f2d (the stalled classifier, spec I8).

## What we already agreed

- The operator, 2026-10-16, relayed by the coordinator: "also dashboard, repos have a mess ui. i want it to be done in
  best user friendly way. best ui practises. it will be our command and control centre" — spec § Personas, I1.
- Approach C, one body-only renderer with two callers — spec § Chosen approach, D1.
- The layout, attention rules, ordering and filter bar with its inverse — spec § The design, D3, D4, D10.
- The reader, renderer, secrets and stable-id invariants — spec § Data flow.
- The bounded live read and both failure paths — spec § Failure.
- The board, chain and component deltas; `dashboard_server.py` retired; the route a `303` — spec § Contract deltas, D5-D9.
- The checks the build owes — spec § Validation; the growth and retirement rules — spec § Lifecycle.
- The plan-time risks — spec § Risks the plan carries.
- The coordinator (fabrik-21), 2026-10-18: "Carry on with /fabrik-ui-design, then /fabrik-plan-after-chat … One request
  together with the plan is fine" — one merge request carries the spec and the built plan.
- This plan's own seam decisions, D-967 (rowed with this plan): the read/load split in `gen_dashboard.py`, epoch-float
  times, the cache slot written on completion, the test-isolation stub, the four tickets; its worker-thread read is
  superseded by D-968 (minted with this plan's convergence), which amends the spec: the live read runs in a child
  process the collector kills at its deadline (spec § Amendments).

## Intake Inventory

| # | Intake item (spec § Intake Inventory) | Delivered by |
|---|---|---|
| I1 | The operator's "best user friendly way … command and control centre" | T01, T02, T04 |
| I2 | The parent spec's follow-up for this page | T04 (the section replaces the link card) |
| I3 | The one major project in flight (D-954) | the whole set |
| I4 | Zero secrets — a credential COUNT only | T02 (the zero-secrets test), T03 |
| I5 | The daily chain and its D-106 heartbeat keep working | T03 |
| I6 | The command centre's tokens, components and strings | T01, T02 |
| I7 | The 2026-10-18 census | T02 (fixture classes), T04 (measured height) |
| I8 | The untriaged classification itself | OUT OF SCOPE — W-7e467f2d |
| I9 | `dashboard_server.py` retired | T03 |
| I10 | D-961: never the Workflow tool | Execution Discipline |
| I11 | Responsive, dark + light, catalogue | T01, T02, T04 (browser and axe) |

## Ticket Board

| Ticket | Title | Depends | Parallel | State | Commit |
|---|---|---|---|---|---|
| T01 | Page-layer additions | — | ⚡ | ✅ | |
| T02 | The inventory module | T01 | ⛓️ | ✅ | |
| T03 | The static file; dashboard_server retired | T02 | ⛓️ | ✅ | |
| T04 | Integration | T01, T02, T03 | ⛓️ | ✅ | |

## Merge Order

1. T01
2. T02
3. T03
4. T04

## Interfaces

- **T01 → T02, T04: the page-layer additions.** `components.select`, `components.table(..., align=)`,
  `components.status_text`, and `app.js`'s markers `data-filter-item`, `data-filter-section`, `data-filter-count`,
  `data-filter-status` with the `qd-filter-open:<group>` record (T01 § Produces). Seam tests: T01's own
  `tests/test_quota_dashboard_app_js.py` over a fixture page; T04's browser test drives the wired section.
- **T02 → T03, T04: the reader and renderer.** `inventory.load(conn, *, before_query=None) -> (rows, synced_at)`,
  `inventory.render(rows, *, now, synced_at, classified_at, interactive) -> Safe`, `inventory.credit_cell`,
  `inventory.STALE_AFTER_H`, `registry_db.connect(**kwargs)` — every time an epoch float (T02 § Produces). Seam tests:
  T03's chain cases call `inventory.render(..., interactive=False)` through `gen_dashboard.main`; T04's server cases call
  it through `_view_data("services")`.
- **T03 → T04: `gen_dashboard`'s names.** `gen_dashboard._read()`, `load()` (rows alone), `render(rows, *, …)` keyword-only
  (T03 § Produces); `dashboard_server.py` gone before T04 removes the route that served its output. Seam test: T04's
  whole-plan gate runs the chain suite again over the merged tree.

## Execution Discipline (binding on /fabrik-execute-plan)

- **Review floor** — every ticket, on the coder's return, runs `/fabrik-review` on its changed surface to a
  coverage-adjudicated exit BEFORE its merge; no ticket merges on a first-pass green. T04 (a request path, a thread and a
  lock in the board, plus the whole-plan diff) takes the full partitioned review; each review closes only on a closing
  pass that confirms zero code or doc defects (D-206, D-335).
- **Dispatch policy** — native Claude seats for every fan-out (the pool is OFF, D-181/D-182), through the Agent tool and
  never the Workflow tool (D-961, `shape: agent-tool`): `dispatch_headroom.py` sizes each review and `command_run.py
  dispatch --seats N` stamps it before the seats go out. Coders are native worktree coders (`Complexity: native` on every
  ticket); Haiku never codes. The orchestrator — Opus or Fable as the quota allows — executes every refutation and the
  decide-merge; an Opus seat takes the authoritative pass on T04's collector and on the whole-plan review.
- **Parallelism + merge** — the four tickets run in Merge Order, one at a time: each consumes the one before
  (T02 renders with T01's components, T03 and T04 call T02's functions, T04 removes the route T03's retirement leaves
  orphaned). Inside a ticket the coder may fan its test writing out to parallel native seats; their results merge into
  the ticket's own branch before its review, deduped by file and line by the orchestrator.

## Ticket breadth (check_ticket_breadth.py verdicts)

The screen flagged 4 of 4 tickets (scores 7–10, each one area plus its test file; the score tracks the Behavior-Contract
row count). Every ticket is KEPT, for one reason each: its rows are one invariant seen from several inputs, and a split
would spread that invariant across tickets that must merge together anyway.

- T01 kept — eight rows, one invariant: the filter's state machine (select, open, record, hide, inverse, swap) lives in
  one `app.js` function family and its components; split, the inverse would be reviewed apart from what it inverts.
- T02 kept — eight rows, one module: one reader and one renderer whose fixtures share every census class.
- T03 kept — seven rows, one CLI: the generator's output and its exit paths, with the retirement that its `CSS`/`HELPERS`
  removal forces in the same commit (`scripts/dashboard_server.py:26` imports them).
- T04 kept — the Integration ticket. Its live wiring is indivisible: the collector, the section and the board suites'
  stub land together, or every Services render in those suites reads the live registry in between. Its route half
  (the `303`, `EXT_SERVICES_HTML`, `QUOTA_DASH_EXT_SERVICES` and their tests) could peel into its own commit without a
  red suite; it stays here because it shares the four board test files and the request path the same review reads,
  and a peeled ticket would re-read both.

## Behavior Contract

### T01 — from `T01-page-layer-additions.md`

- **Given** a `select()` with a value holding `<script>` and quotes, **When** it renders, **Then** labels and values are escaped, the matching option is selected, and a bad id or data key raises ValueError (spec § The design, Filter bar; scripts/sysadmin/dashboard_ui/components.py:72)
- **Given** a `table()` with `align=[None, "right"]`, **When** it renders, **Then** the second column's header and cells carry data-align="right" and a positional call without align renders exactly as before (spec § Contract deltas; scripts/sysadmin/dashboard_ui/components.py:191)
- **Given** a filter group with a cost select in token mode, **When** the operator picks free, **Then** only rows whose cost token is free stay visible and no freemium row does (spec § The design, Filter bar; scripts/sysadmin/dashboard_ui/static/app.js:460)
- **Given** a stored filter state holding a select value, **When** the view re-initialises, **Then** the select shows the stored value, and a stored value no option offers resets the select to all and drops that key (spec § The design, Filter bar; scripts/sysadmin/dashboard_ui/static/app.js:514)
- **Given** closed filter sections, **When** a typed term matches a row inside one, **Then** that section opens, its id is recorded under qd-filter-open:<group>, sections with no match are hidden, the status element reads filter.shown and each group's count element reads filter.group_count with its shown and total counts (spec § The design, Filter bar)
- **Given** one section opened by the filter and one opened by hand that also matches, **When** the filter is cleared, **Then** the filter-opened section closes, hidden sections return, the hand-opened one stays open, and qd-filter-open:<group> is emptied (spec § The design, Filter bar)
- **Given** a filter set, **When** the view is force-swapped and, separately, the page is reloaded, **Then** the filter values, the qd-filter-open:<group> record and the visible filtering are the same after each, and a corrupt record (not a list of ids) is reset without touching qd-filter:<group> (spec § Validation; scripts/sysadmin/dashboard_ui/static/app.js:504)
- **Given** the new components, **When** the page-layer scans run, **Then** every new text parameter is a scanned text slot and align and options are non-text keywords (tests/test_quota_dashboard_page_layer.py:302)

### T02 — from `T02-inventory-module.md`

- **Given** a fake connection answering the five queries and max(last_seen), with a fetchone that returns None for an empty answer as the chain suite's fake does and, separately, (None,) as Postgres does, **When** load runs with and without a before_query hook, **Then** it returns rows with balance, unit and credit_at in place of the credit string, synced_at as an epoch float or None in both empty shapes, the hook ran once before each query, with no hook no other SQL ran, and api_keys rows of kind credential, credential-unattributed and code-host give keys 1, unattributed 1 and keys 0 respectively while every one keeps its project in projects (spec § Data flow; scripts/gen_dashboard.py:94)
- **Given** provider URLs https://ok.example, HTTPS://UP.example, /admin, #x and http://a b, **When** render runs, **Then** only the first carries an href and every other renders as plain text (spec § Validation; scripts/sysadmin/dashboard_ui/components.py:47)
- **Given** fixture rows covering every census class at census counts, **When** render runs, **Then** the section holds Needs attention, eighteen category tables with the Unidentified table last, the Untriaged queue as one section of 331 list entries and no table row, an unidentified row in both Needs attention and the Unidentified table, and the More counts each equal to its formula (spec § The design items 2-5; spec § Validation)
- **Given** one row per attention rule (a 49 h credit, unattributed credentials, unidentified, retiring), a 47 h credit, a healthy row, a paid row with no credential, synced_at and classified_at each 49 h old, 47 h old and None, and five and six rows sharing a reason, **When** render runs, **Then** each rule row, both 49 h and both None source cases are entries, the 47 h, healthy and paid-without-credential rows and a stalled classifier over an empty Untriaged queue are not, five rows are listed by name and six collapse into one counted details listing all six (spec § The design item 3; spec § Validation)
- **Given** providers named www.googleapis and captcha and a category named captcha, **When** render runs interactive, **Then** every details carries a slug id with its kind's prefix, every id is valid and unique, and every filter target carries a data-f-<name> attribute for each filter control's name (spec § Data flow; scripts/sysadmin/dashboard_ui/static/app.js:473)
- **Given** interactive False, **When** render runs, **Then** the output holds no filter control, no clamp, no button and no data-filter-status, and project lists past three names show the rest in a native details (spec § Chosen approach)
- **Given** a credential value string in the fixture and a provider named </script><img src=x onerror=1>, **When** render runs in both modes, **Then** the value appears nowhere and the name renders as text (spec § Validation)
- **Given** a 5,000-row fixture, **When** render runs, **Then** it completes in under 200 ms (spec § Lifecycle)

### T03 — from `T03-static-file.md`

- **Given** a fixture registry and the test's timezone pinned (TZ set and time.tzset), **When** gen_dashboard writes the static file, **Then** it holds no script element, no src attribute, only `https?` provider hrefs, the inlined app.css, a Registry synced line with date, time and zone, and Registry never synced when synced_at is None (spec § Validation; spec § The design item 1)
- **Given** a fake connection that records close, **When** _read runs and when inventory.load raises, **Then** the connection is closed on both paths (scripts/gen_dashboard.py:121)
- **Given** a fixture registry, **When** the static file is written, **Then** each of today's ten stat values, ten columns and the footer legend appears at the home the spec maps it to (spec § The design item 2; spec § Validation)
- **Given** a dead registry or a render that raises, **When** main runs, **Then** it prints the one typed line, exits 1 and leaves the previous file unchanged (spec § Failure; scripts/gen_dashboard.py:308)
- **Given** a row missing a required key, **When** main runs, **Then** it exits 1 rather than writing a file (tests/test_external_services_chain.py:1043)
- **Given** gen_dashboard and its imports, **When** the module loads twice, and separately in a fresh subprocess, **Then** scripts and scripts/sysadmin each appear on sys.path once, and the subprocess's sys.modules never holds quota_dashboard (spec § Chosen approach; tests/test_external_services_chain.py:2059)
- **Given** the retirement, **When** the scripts and tests are searched, **Then** dashboard_server.py and its tests are gone, while the chain's step and heartbeat are unchanged (spec § Contract deltas; scripts/external_services_chain.sh:117)

### T04 — from `T04-integration.md`

- **Given** the board test isolation, **When** any board test renders the Services view, **Then** the collector's spawn is replaced by a stub returning the census fixture or a stated failure, `SERVICES_REGISTRY_DSN` names an unusable DSN so a real child cannot reach the registry, the board process imports neither registry_db nor psycopg2, and the 60 s slot is empty at each test's start (spec § Validation; tests/quota_dashboard_isolation.py:35)
- **Given** the real child against a fake server that accepts and never answers, **When** the Services view is requested, **Then** the inventory section shows its error state within 5 s with the failure's class and first line only, the child is killed and gone, and the pool and API cards render (spec § Failure; scripts/sysadmin/quota_dashboard.py:2218)
- **Given** an empty slot, two concurrent requests, a failed child, and a last good read 59 s and 61 s past its start, **When** requests reach the collector, **Then** the concurrent requests share one child, every request answers within 5 s of its own arrival, every request without a fresh result serves the section's error state, a failed read leaves the last good read in place, the in-flight field clears on every exit so the next request starts afresh, a request held on the lock answers within its own deadline, no connection is cancelled, and the read at 59 s is served while 61 s spawns a new child (spec § Failure; scripts/sysadmin/quota_dashboard.py:531)
- **Given** psycopg2 cannot be imported in the child, **When** the Services view renders, **Then** the board serves every view and only the inventory section shows its error state, naming the import's exception class from the child's error object whatever its stderr holds, and the board process never imported psycopg2 (spec § Contract deltas D9)
- **Given** a bookmark to /external-services.html, **When** it is requested, **Then** the board answers 303 to /#services with an empty body, and no link card, ext_page key or services.ext string remains (spec § Contract deltas; scripts/sysadmin/quota_dashboard.py:2833)
- **Given** the Services view at census scale (tests/external_services_fixture.py) in a 1280 px and a 375 px browser, **When** the operator types a provider name, picks each select, force-swaps and clears, **Then** the group holding the match opens, groups with no match are hidden, the count updates, Cost free shows no freemium row, the Needs-attention list is unchanged by any filter, the filter values, the qd-filter-open:<group> record and the visible filtering survive the swap, clearing closes what the filter opened and keeps a hand-opened group open, and the page never scrolls sideways (spec § Validation)
- **Given** the inventory section at census scale with groups collapsed, and the static file gen_dashboard writes from the same fixture, **When** the browser measures each at 1280 px and 375 px, **Then** the section is at most 4,000 px tall, the static file lays out without sideways scroll inside its wrapper, and axe reports no violation of 1.3.1, 1.4.1, 1.4.3, 1.4.11, 2.1.1, 3.3.2 or 4.1.3 in both themes, with an open row detail included (spec § Validation; spec § Risks the plan carries)
- **Given** two renders of the Services view a minute apart with the same registry, **When** their fragments are compared, **Then** the data-stamp is unchanged (spec § Data flow; scripts/sysadmin/dashboard_ui/views/__init__.py:66)

## Global Constraints

- Box-local hub tool. The board process stays stdlib Python on `/usr/bin/python3`; D9's psycopg2 is imported only in
  the child `scripts/sysadmin/inventory_read.py` the board spawns; the
  generator runs under the hub `.venv` (`scripts/external_services_chain.sh:117`); no CDN, no build step; playwright is in
  the `.venv` for tests only.
- The bind stays `127.0.0.1:5051` (`PORTS.md`); no port is added.
- `dashboard_ui` never imports `quota_dashboard`; `inventory.py` never imports `registry_db` or psycopg2.
- Every value interpolated into HTML passes through a component; every user-visible string comes from the catalogue; no
  colour literal outside `app.css`'s token blocks; no inline `style=`; no iframe.
- Zero secrets: the rows carry metadata and a credential COUNT only.
- The chain's CLI, exit codes, atomic write and D-106 heartbeat are unchanged.
- Every test run goes through `/opt/fabrik/scripts/capped_run.sh` (D-935); no board test opens a registry connection.
- 12-Factor, as they apply to a box-local tool with no container: III config = granular env vars, no grouped env sets,
  no secrets in code · XI logs stay unbuffered lines on stderr, no logfile · VIII no daemonizing or PID files beyond
  today's launcher and the generator's PID-named tmp file · VI no per-viewer session state · II no shelled-out binary is
  added · IX/XII/X/V no worker, migration, backing service or container exists here.
- Shared tree: commit by explicit pathspec with Agent Provenance Trailers; never stage a sibling's WIP; never edit the main
  checkout. The Doc Sync ledgers a ticket's Docs line names (`CHANGELOG.md`, `INDEX.md`) are staged in that ticket's
  commit although they sit outside File Scope: they are shared-append files no plan lock holds
  (`scripts/enforcement/check_plan_tickets.py:532-533`), and `check_doc_sync.py` refuses a code commit without its
  CHANGELOG entry.

## Constraints Digest

The spec's § Constraints Digest binds every ticket; its six rows are copied here unchanged, followed by rows this plan
adds for the packs the rubric matches (10-python, 12-node, 40-documentation, 45-testing) and the FLOOR packs it injects.

| Quote | Source | Binds |
|---|---|---|
| Zero secrets in either output (I4); a credential COUNT only. | `docs/superpowers/specs/2026-10-18-external-services-page-design.md:409` | T02, T03 |
| The chain's CLI, exit codes, atomic write and D-106 heartbeat unchanged (I5). | `docs/superpowers/specs/2026-10-18-external-services-page-design.md:410` | T03 |
| The shared renderer is body-only; from the page layer `gen_dashboard.py` imports `dashboard_ui.inventory`, `components` and `strings` only, never `quota_dashboard` (the panel's caveat). | `docs/superpowers/specs/2026-10-18-external-services-page-design.md:411` | T02, T03 |
| The live registry read is bounded in time (2 s connect, 5 s for the whole read); the static file carries no script. | `docs/superpowers/specs/2026-10-18-external-services-page-design.md:413` | T03, T04 |
| The board keeps running under `/usr/bin/python3`; the registry read adds psycopg2 (present for that interpreter: 2.9.11 from the user site `~/.local` when `HOME` is set, as under the board's cron and `--serve`; 2.9.9 from the system `dist-packages` otherwise) as a named exception to the parent spec's "no new dependency" rule (D9), imported only in the child process the board spawns, so the board process itself stays stdlib. | `docs/superpowers/specs/2026-10-18-external-services-page-design.md:414` | T04 |
| Responsive 375→2560 px, dark and light, English-only with a catalogue (D-926). | `docs/superpowers/specs/2026-10-18-external-services-page-design.md:418` | T01, T02, T04 |
| BANNED: logging.FileHandler, logging.handlers.RotatingFileHandler, TimedRotatingFileHandler, loguru file sinks, any *.log file write, any in-app log rotation/retention/cleanup. | `.windsurf/rules/core/10-python.md:294` | Global Constraints XI |
| No cosmetic assertions: never assert against CSS classes, Tailwind utility strings, pixel measurements, or snapshot hashes. | `.windsurf/rules/core/45-testing-strategy.md:21` | Every ticket's tests assert landmarks, roles, text and state; T04's height check is the spec's measured budget, read from the browser, not a snapshot |
| Fenced code blocks only — never indented code (AI treats it inconsistently) | `.windsurf/rules/core/40-documentation.md:244` | T03's and T04's doc edits |
| Node.js production backend patterns (current LTS) | `.windsurf/rules/core/12-node.md:4` | Matched by glob on `app.js` only: `app.js` is a browser script served to the board's page, with no Node runtime, package or server, so no rule of this backend pack binds T01's edit; the browser behaviour is bound by T01's own tests |

## Context Ledger

- `docs/superpowers/specs/2026-10-18-external-services-page-design.md` — the design; § The design is the UI contract (DT2).
- `docs/development/reviews/2026-10-18-external-services-page-spec-review.md` — the converged review and the panel's changes.
- `docs/reference/research/2026-10-18-external-services-page-ledger.md` — the 38 research facts the spec cites.
- `.windsurf/rules/core/10-python.md`, `.windsurf/rules/core/12-node.md` (app.js), `.windsurf/rules/core/40-documentation.md`,
  `.windsurf/rules/core/45-testing-strategy.md`, `.windsurf/rules/saas/60-saas-ui.md` and
  `.windsurf/rules/core/design-system-template.md` (applied by analogy — no scaffold type here); the FLOOR packs
  `.windsurf/rules/core/35-security-auth.md`, `25-data-postgres.md`, `30-ops.md`.
- fabrik-lib: no module renders an operator console (spec § fabrik-lib verdict, BUILD); `scripts/registry_db.py` is reused
  in-repo. No vendored module is touched, so no `UPSTREAM_FEEDBACK.md` step.
- `docs/workstation/quota-dashboard.md` (T04) and `docs/reference/external-services-registry.md` (T03) — the subsystem docs.

## File Scope (owned paths)

- scripts/sysadmin/dashboard_ui/components.py
- scripts/sysadmin/dashboard_ui/static/app.js
- scripts/sysadmin/dashboard_ui/static/app.css
- scripts/sysadmin/dashboard_ui/inventory.py
- scripts/sysadmin/dashboard_ui/strings.py
- scripts/sysadmin/dashboard_ui/views/services.py
- scripts/sysadmin/quota_dashboard.py
- scripts/sysadmin/inventory_read.py
- scripts/registry_db.py
- scripts/gen_dashboard.py
- scripts/dashboard_server.py
- tests/test_quota_dashboard_ui_kit.py
- tests/test_quota_dashboard_app_js.py
- tests/test_quota_dashboard_page_layer.py
- tests/test_external_services_inventory.py
- tests/external_services_fixture.py
- tests/test_external_services_chain.py
- tests/quota_dashboard_isolation.py
- tests/test_quota_dashboard.py
- tests/test_quota_dashboard_server.py
- tests/test_quota_dashboard_views_misc.py
- tests/test_quota_dashboard_browser.py
- docs/reference/external-services-registry.md
- docs/workstation/quota-dashboard.md
- docs/workflows/DATA_SYNC_WORKFLOW.md
- docs/CAPABILITIES.md
- capabilities.json
- llms.txt
- docs/development/reviews/2026-10-18-plan-1-external-services-inventory-review.md

## Evidence

Primary paths, each read at c4e827715 by the seven Phase-1 grounding seats and re-printed by the orchestrator: T01
`scripts/sysadmin/dashboard_ui/components.py:191` and `scripts/sysadmin/dashboard_ui/static/app.js:662`; T02
`scripts/gen_dashboard.py:56` and `scripts/registry_db.py:33`; T03 `scripts/gen_dashboard.py:297` and
`scripts/external_services_chain.sh:117`; T04 `scripts/sysadmin/quota_dashboard.py:2392`, :2844, :2218, :531,
`scripts/sysadmin/dashboard_ui/views/services.py:196` and `tests/quota_dashboard_isolation.py:51`.

Cited lines, printed at c4e827715 (a small Python reader over the worktree, 14 of 14 as cited):

```
scripts/gen_dashboard.py:56: def load() -> list[dict]:
scripts/gen_dashboard.py:297: def main(argv: list[str] | None = None) -> int:
scripts/registry_db.py:33: def connect():
scripts/sysadmin/quota_dashboard.py:2392: elif name == "services":
scripts/sysadmin/quota_dashboard.py:2844: elif path == "/external-services.html":
scripts/sysadmin/quota_dashboard.py:2218: def _guarded(fn, *args, **kwargs) -> object:
scripts/sysadmin/quota_dashboard.py:531: _credits_lock = threading.Lock()
scripts/sysadmin/dashboard_ui/components.py:191: def table(
scripts/sysadmin/dashboard_ui/components.py:227: def field(
scripts/sysadmin/dashboard_ui/static/app.js:662: if (el && el.matches && el.matches("input[data-filter], textarea[data-filter]")) { filterInput(el); }
scripts/sysadmin/dashboard_ui/static/app.js:492: function validFilterState(state) {
scripts/sysadmin/dashboard_ui/views/services.py:196: def render(data: dict, ctx: ViewContext) -> ViewResult:
tests/quota_dashboard_isolation.py:51: def loopback(address: object) -> bool:
scripts/external_services_chain.sh:117: if _step gen_dashboard "$VENV_PY" "$FABRIK_ROOT/scripts/gen_dashboard.py" "$DASHBOARD"; then
```

The suites the set changes, collected at c4e827715 (`capped_run.sh -- .venv/bin/python -m pytest --collect-only -q
-p no:cacheprovider <the nine files>`, then counted per file; the run ended `797 tests collected in 0.75s`):

```
     50 scripts/tests/test_registry_sync.py
     59 tests/test_external_services_chain.py
     88 tests/test_quota_dashboard_app_js.py
     19 tests/test_quota_dashboard_browser.py
     58 tests/test_quota_dashboard_page_layer.py
    179 tests/test_quota_dashboard.py
     45 tests/test_quota_dashboard_server.py
    221 tests/test_quota_dashboard_ui_kit.py
     78 tests/test_quota_dashboard_views_misc.py
```

The grounding seats' findings this plan settles (each read from source, the seat that found it named):

- The board's isolation treats a unix-socket connection as never the network (`tests/quota_dashboard_isolation.py:51-55`)
  and the registry's default DSN is the peer-auth socket (`scripts/registry_db.py:19`), so without a stub every Services
  render in the board suites reads the live registry — unit-C seats; settled in T04's isolation stub.
- `statement_timeout` is server-side and cannot bound a client blocked on a backend that never replies — the Opus seat;
  settled by T04's child process killed at the read's deadline, the server-side timeouts kept as the backend's own
  bound (spec amended, D-968; pass 3 executed that `cancel()` freezes the process against a silent server).
- `gen_dashboard.main()` needs `synced_at` while `load()` keeps returning rows alone, and six chain tests patch `gd.load`
  and a one-argument `gd.render` by name (`tests/test_external_services_chain.py:232`, :241, :254, :887, :942, :1049) —
  units A and C; settled by T03's `_read()` and the keyword-only `render`.
- `link()` refuses an href today's gate accepts (`scripts/sysadmin/dashboard_ui/components.py:47` against
  `scripts/gen_dashboard.py:192`) — units B and Opus; settled in T02 (plain text on refusal).
- `page_layer.py:784` builds its INVENTORY at import through `K("services.ext.age")`, so the key removal and that row's
  rewrite share T04's commit — the Opus seat.
- The `components.py:205` anchor in the spec's § Risks is `:206` — the unit-B mechanical seat; the plan cites `:206`.

### Execution (2026-10-18)

Merged on `worktree-infra`: T01 `5d7f1057c`, T02 `a4647e46e`, T03 `4bddb47d2`, T04 `e660340bf` (the T04 coder's
`4a11504c1` plus the whole-plan validation's four fix commits). Whole-plan validation:
`docs/development/reviews/2026-10-18-plan-1-external-services-inventory-review.md` — CONVERGED, five passes, confirmed
12 → 3 → 1 → 0 → 0, sixteen findings fixed (F1–F16). Every ticket's suite plus the seam suites on the integrated tree
`89fdcf104` (`capped_run.sh -- .venv/bin/python -m pytest` over the chain, inventory, registry-sync and the thirteen
board files): `1243 passed, 20 skipped in 241.72s` — the 20 are `scripts/tests/test_registry_sync.py`'s live-registry
write cases, opt-in by `REGISTRY_WRITE_TESTS=1`.

The live request (D7): the merged board served from this worktree on port 5097 with an empty HOME (no accounts to
probe); the inventory child read the real registry over the peer-auth socket. Verbatim:

```
$ curl -s -i http://127.0.0.1:5097/external-services.html | head -8
HTTP/1.0 303 See Other
Server: quota-dashboard Python/3.12.3
Date: Sun, 18 Oct 2026 14:07:33 GMT
Location: /#services
Content-Length: 0
Cache-Control: no-store
$ curl -s -i http://127.0.0.1:5097/v/services -o live-services.html -w '%{http_code} %{size_download} bytes %{time_total}s\n'
200 217042 bytes 0.309624s
$ grep -o '[0-9,]* providers' live-services.html | head -2
466 providers
331 providers
$ grep -c 'could not be read' live-services.html
0
```

## Self-audit

Grounding: seven native seats in one message (3 Sonnet breadth, 3 Haiku mechanical, 1 Opus authoritative; units A server
side, B page layer, C consumers and tests), every finding re-read by the orchestrator against the code before it entered a
ticket; 14 plan-shaping findings, 0 refuted; the cited lines re-printed above.

(a) Coverage — every item of "What we already agreed" has a ticket: the layout, rules, filter and inverse → T01 + T02;
the reader and renderer invariants → T02; the bounded read and the failure paths → T04 (live), T03 (chain); the
contract deltas → T01 (components, app.js), T03 (the generator, the retirement), T04 (the board, the route); § Validation
→ T02 (unit), T03 (chain), T04 (browser, axe, height); § Lifecycle's 5,000-row render test → T02; § Risks the plan
carries → T04 (axe 1.3.1 with an open detail, the static file opened in the browser and measured, the height, the
test sequencing, the retirement owner named at T04's close). No gap.

(b) Cross-ticket signature consistency — T02 produces `load(conn, *, before_query=None)`, which T03 calls with no hook
and T04 with its deadline hook; `render(rows, *, now, synced_at, classified_at, interactive)`, which T03 calls with
`interactive=False` and T04 with `True`; every time an epoch float on both sides (`ctx.now` is `time.time()`; T03
converts the mtime and `synced_at` as floats). T01 produces the markers T02 emits and T04's browser test reads; the
`qd-filter-open:<group>` key is the same string in T01 and T04. Consistent.

Fixed point: not claimed — `/fabrik-plan-review` converges this set.

## Coverage Checklist

| Class | Verdict |
|---|---|
| core/35-security-auth.md | CLEAN — no auth, secret or CORS surface changes; zero secrets held (T02 row 7, T03); the board's loopback bind and POST guards untouched (Global Constraints); hunted T01-T04 Touches |
| core/25-data-postgres.md | FIXED — no schema or migration; the read is SELECT-only in one implicit transaction, bounded server-side by statement_timeout and client-side by killing T04's child at the read's deadline (rules-3/4, R4-1); `fetchone` shapes for an empty max() settled in T02 (rules-1) |
| core/30-ops.md | CLEAN — no container, compose, port or deploy surface; the chain's step and heartbeat unchanged (T03, `scripts/external_services_chain.sh:117`) |
| 12-FACTOR | CLEAN — Global Constraints list each axis as it applies; no logfile (XI), no new binary (II), granular env vars only (III, `QUOTA_DASH_EXT_SERVICES` removed in T04) |
| core/10-python.md | FIXED — every new Python function typed in its ticket's Produces; logs stay stderr lines; Decimal-to-float at the credit_cell seam (T03) |
| core/12-node.md | REFUTED — matched by glob on app.js only, a browser script with no Node runtime (Constraints Digest row) |
| core/40-documentation.md | FIXED — each doc site owned by a ticket's Docs line (T03 registry doc, T04 quota-dashboard doc, DATA_SYNC wording, catalogue regenerated with llms.txt in File Scope, rules-11) |
| core/45-testing-strategy.md | FIXED — one Behavior row per behaviour, spec § Validation rows mapped (rules-6, rules-7, context-3), census-scale fixture shared (rules-8), red-first possible for every row |
| Recurrence: fail-open vs fail-closed on every gate/guard | FIXED — the registry guard in the board suites now fails loudly on any connect (rules-3); link() gated to ^https?:// before it is called (rules-2); a missing psycopg2 is the section's error state, never a silent empty (T04 row 4) |
| Recurrence: cost/quota/limit accounting edges (unknown ≠ 0, per-call vs batch) | FIXED — a None synced_at or classified_at is an attention entry, never a fresh read (T02 row 4); one read alive at a time, each request's own 5 s budget (rules-4/10); the slot's 60 s counted from the read's start (rules-12) |
| Recurrence: boundary/sentinel/prefix collisions | FIXED — slug ids with a prefix per kind against `captcha` as provider and category (T02 row 5); the five/six collapse boundary and 47/49 h boundaries pinned (T02 row 4); token mode so free never matches freemium (T01 row 3) |
| Recurrence: behavior-without-a-test | FIXED — the static wrapper's layout (context-3), the reload of the filter record (context-7), the connection close (context-5) and every spec § Validation browser step (rules-7) now each carry a row |

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

### core/10-python.md  (hit: scripts/dashboard_server.py, scripts/gen_dashboard.py, scripts/registry_db.py)
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

### core/12-node.md  (hit: scripts/sysadmin/dashboard_ui/static/app.js)
- Never mix `require()` and `import` in the same package — dual-package hazard.
- **New services target the current Active LTS line** (`node:<!--v:node_lts-->24<!--/v-->`). The previous LTS line is maintenance-only — existing services may ride it to its EOL, new services never target it. `node-api` + `file-api` scaffolds declare the floor `engines.node: ">=<!--v:node_engines_floor-->22<!--/v-->.0.0"`.
- **Never** `process.env.X || 'default'` for secrets/tokens/DSNs — silent defaults are the #1 source of "works locally, fails in prod".
- For complex config: Zod schema validation at boot, typed `config` object exported, never reach `process.env` from business code.
- > **12-Factor XI (Logs), verbatim:** *"each running process writes its event stream, unbuffered, to `stdout`"* — and *"A twelve-factor app never concerns itself with routing or storage of its output stream. It should not attempt to write to or manage logfiles."*
- > **BANNED: any file transport.** `pino.destination('/path/app.log')`, `winston.transports.File`, `winston-daily-rotate-file`, `fs.createWriteStream` for logs, any `*.log` write, any in-app log rotation/retention. The app logs JSON to `stdout` and nothing else; **Docker → Promtail → Loki owns routing and retention.** Full rule: `55-observability.md` § Logs.
- Use `pino` for application logs; `pino-http` for request logs. NEVER `console.log` outside bootstrap (breaks Loki/Promtail parsing + wastes GlitchTip).
- Auth tokens, HMAC signatures, webhook secrets — **always** `crypto.timingSafeEqual(Buffer.from(a), Buffer.from(b))`. Never `==` or `===`. (The bug class Node itself shipped as CVE-2026-21713 — HMAC verification through a non-constant-time compare, a timing side channel leaking MAC values; the runtime fix is the patch floor above, this rule keeps the class out of OUR code.)
- A crafted `__proto__` header name crashes an unpatched Node via `req.headersDistinct` (CVE-2026-21710 — uncaught TypeError, process-down DoS). Mitigation is the patched-runtime floor above. **Coding agents:** never read raw header maps without an explicit allowlist.
- Always terminate TLS at Traefik, never in Node. CVE-2026-21637 (unhandled exception in the TLS SNI-callback path → remote DoS) is avoided entirely by Traefik handling TLS.
- CORS: explicit `origin:` array per environment. Never `cors({ origin: '*' })` on a service with auth.
| `cluster` | **BANNED** | Replaced by deploying multiple Docker container replicas behind Traefik. Cluster in a containerized environment doubles process count without observable scaling. |
- **Local development: run `.ts` files directly — `node index.ts`.** Type stripping is stable and enabled by default in current Node; ts-node and tsx are obsolete for dev (opt-out flag `--no-experimental-strip-types` exists, never use it).
- **Production Docker build:** `esbuild` or `swc` for transpile (millisecond-fast). `tsc --noEmit` runs in CI for type-checking only — never as a build step.
- LLM gateway: **OpenRouter only.** Never import vendor SDKs (`openai`, `@anthropic-ai/sdk`) directly. See `core/65-rag-search.md`.
- Payment processing: **iyzico** for TR domestic SaaS subscriptions; **Paddle Billing** (international MoR) for cross-border. PayTR applies only to WooCommerce / physical D2C (see `85-payments-billing.md:16`), not to Node SaaS backends. **Stripe is unavailable to a TR-resident LLC** — never wire the `stripe` npm SDK. Per-flow detail: `core/85-payments-billing.md`.
- Never inline `APIKeyHeader` middleware patterns or per-service key names (`SERVICE_API_KEY`, `PROXY_API_KEY`) — single shared secret per-fleet.
| `pino.destination('*.log')` / `winston.transports.File` / any log file write or rotation | JSON → `stdout` only; Docker → Promtail → Loki routes | 12-Factor XI: the app must never write or manage a logfile |
- [ ] `npm ci --ignore-scripts` in Dockerfile + CI (never `npm install`).

### core/40-documentation.md  (hit: docs/CAPABILITIES.md, docs/development/reviews/2026-10-18-plan-1-external-services-inventory-review.md, docs/reference/external-services-registry.md)
- > **⚠️ `docs/OPERATIONS.md` + `docs/DEPLOYMENT.md` are FLEET-AI INTERFACES, not just docs (D-065).**
- **Tier-1 (author → verify → converge; the author leg is NATIVE while the pool is OFF, D-181 — `scripts/doc_reconcile.py`'s pool author cannot dispatch):** for each **mechanically-detectable** doc whose Doc-Sync trigger fired (`docs/QUICKSTART.md` · `docs/CONFIGURATION.md` · `docs/data-contract.md` · `docs/SERVICES.md` · `docs/OPERATIONS.md` — the reliable-signal subset), `scripts/doc_reconcile.py` dispatches a cheap OpenRouter-pool author (`libs.subagents`, `pick_models("docs")`) to emit a **minimal structured patch**, **verifies it before applying** (a symbol cross-check catches invented endpoints; the orchestrator injects a higher-assurance native-Claude verify), and loops to a zero-edit round. Runs per phase in `/fabrik-execute-plan`; never blocks (fail-safe). The other docs (CHANGELOG, INDEX, FEATURES, RESILIENCE, PORTS, the READMEs, `db/schema.sql`, …) have no reliable mechanical content-signal → they rely on the touch-on-change backstop below + your own edit (force-update, not force-correct).
- The SSOT is the type-aware registry (`scripts/enforcement/_doc_registry.py::PROJECT_DOCS`) — this table is its project-facing rendering, kept in step, never a second truth. `/fabrik-plan-after-chat` (the plan set's spine + tickets — the ticket-format authority) injects these rows per ticket as its `Docs:` line.
- Standalone work (not plan execution) → `Agent-Role: primary`. Trailers go below a blank line, above `Co-Authored-By`. ⚠️ The trailer block must be its OWN paragraph with NO blank line inside it: git parses only the LAST paragraph, and only if it is all-trailers. A blank line before `Co-Authored-By:` demotes everything above it to prose; so does a prose line glued to the top of the block. Measured 2026-08-15: 200 of the last 200 hub commits carried `Agent-Role:` and only 10 parsed, because the old example here shipped the blank line.
- **⚠️ Link it or it is decoration.** *Measured:* requests for files that do NOT exist came ~zero from AI bots — agents never go looking. It follows (inference, not measurement) that a file only gets read when something points at it: reference it from the docs index or README.
- ⚠️ **In the hub (`/opt/fabrik`) `llms.txt` is GENERATED** (`scripts/generate_capability_index.py`, refreshed daily) — never hand-edit it there; change the generator. A project has no such generator; an `llms.txt` it ships, hand-written or built by its own code, is its own.
- either way. Cheap and reversible — never at the expense of `OPERATIONS.md`/`DEPLOYMENT.md`, which are the load-bearing agent interfaces (D-065).
- **No skipped heading levels** — `##` to `###`, never `##` to `####`
- **Fenced code blocks only** — never indented code (AI treats it inconsistently)

### core/45-testing-strategy.md  (hit: tests/quota_dashboard_isolation.py, tests/test_external_services_chain.py, tests/test_external_services_inventory.py)
- **Behavior Contract**: every ticket enumerates its distinct **user-observable behaviors / acceptance criteria** and tests **each one** — one high-value integration/E2E test per behavior, risk-ordered, TDD for the risky ones. Skip trivia (getters / framework glue / config): **lean-but-complete, NOT 100%-line-coverage dogma**. Do not chase line coverage — ensure every behavior has a test that would fail if that behavior regressed. (Cheap pool subagents can author the per-behavior tests — the suggest→curate→author→fix workflow in `62-using-subagents.md` § Dispatch policy + `~/.claude/commands/fabrik-review.md`.)
- **No cosmetic assertions**: never assert against CSS classes, Tailwind utility strings, pixel measurements, or snapshot hashes. Assert application state and user-visible outcomes only.
- **Watched-fail-first** (for tests this change adds or modifies; trivia stays skipped per the Behavior Contract): a non-trivial behavior's test proves something only if it has been SEEN RED — either write it first and watch it fail, or (after the fact) neuter the fix/feature, prove the test goes red, then RESTORE and re-run to green. The neutered state is never staged, committed, or left in the tree. A green test never seen red is unverified — a suite can pass with its guard deleted.
- **Run tests**: `uv run pytest tests/` (never bare `pytest` — Fabrik uses `uv`) — **when the project has a `pyproject.toml`/`uv.lock`**. A `requirements.txt`-only project (no manifest) runs `.venv/bin/python -m pytest tests/` — the manifest clause chooses the RUNNER, it never disarms the mandate to run the suite (web-ecommerce-factory 01M1QEY5, 2026-09-05: the clause read as "does not apply here"). ⚠️ **Gate this on the manifest, because this line is FLOOR-injected into finder prompts and a vendored fabrik-lib MODULE has neither by design**: the module recipe ships `requirements.txt` (`fabrik-lib/README.md` § Creating a Reference Implementation), so `uv run` cannot resolve it and `python3 -m pytest` is the only thing that works. Telling a finder the sole working … (wrapped further — read the pack)
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
# promote-to-check_*: (elided — the full mandates are above)
```

## Pass Ledger

| Pass | seats · axes re-checked | counters | method | set md5 (start → end) |
|-----:|---|---|---|---|
| Pass 1 | opus×1 (slice rules: spine Interfaces, Execution Discipline, Global Constraints, roll-up, File Scope; T02, T04) + sonnet×1 (slice context: T01, T03; spine agreed, intake, breadth, digest, ledger, Evidence, Self-audit, residuals) · shape: agent-tool (D-961) | found: 20, new: 20, confirmed: 19, fixed: 19, unexecuted: 0, edits: 31 | method: re-derivation — every candidate re-executed by the lead: the one-argument `render` lambda against the keyword call (`TypeError`), `link()` over `/admin` and `#top` (both linked), a spy on `socket.socket.connect` around `psycopg2.connect` (no call seen), the chain fakes' answer keys and `fetchone` (`tests/test_external_services_chain.py:1078-1106`), `after_load` at `tests/quota_dashboard_isolation.py:46`, the filter emitter `scripts/sysadmin/dashboard_ui/views/commands.py:144`, :164; context-7b (option labels unscanned) recorded, not a defect: labels come from the catalogue | 57927e7d695b0abf43104f848437f88f → 346d93a7a99b0a7dc669734bb21d5eeb |
| Pass 2 | opus×1 + sonnet×1 (round-1 owners) · delta over every pass-1 hunk + one hop (fix1.diff, 436 lines) · shape: agent-tool | found: 8, new: 8, confirmed: 8, fixed: 8, unexecuted: 0, edits: 9 | method: re-derivation — 20 pass-1 ids re-executed (19 FIXED, context-7b recorded and accepted); new candidates re-executed by the lead: `link()` against a prefix gate (`http://a b` passes the prefix, `link()` refuses), the chain fake at `tests/test_external_services_chain.py:1643` (Decimal) and :2459 (the connect patch), `scripts/tests/test_registry_sync.py:41-44` (the opt-in writes the LIVE registry), `psycopg2.extensions.connection.cancel` (present); the collector's concurrency paragraph, which drew defects in two consecutive passes, was REWRITTEN whole around one lock and one outcome rule (the spec's error state) | baf2aa3d3422cc15ad18b1a17e467196 → d4eb141c00914aa1ad93ac7850fb4b18 |
| Pass 3 | opus×1 + sonnet×1 (round-1 owners) · the pass-2 fixed set only (scope-growth remainder round) · shape: agent-tool | found: 5, new: 5, confirmed: 5, fixed: 5, unexecuted: 0, edits: 6 | method: re-derivation — NEW-1…NEW-4 and context-9/-10 re-executed FIXED; new: `psycopg2`'s `cancel()` against a fake server that accepts and never answers froze every thread for 28 s (the rules seat's `probe_cancel.py`, re-read by the lead), keepalives left the query blocked over 12 s, the in-flight record held no connection handle, three concurrency rules had no assertion; context-11's claimed coverage absent (no fake answers `api_keys` rows) — the cancel and keepalives removed, the frozen-server wedge stated as an accepted residual, T02's first row guards `keys`/`projects` | f656f6cf8978a5b740dd1011aafb1f03 → 63680a366e9cbdc87333e57ce30139c1 |
| Pass 4 | opus×1 + sonnet×1 (round-1 owners) · the pass-3 fixed set only (scope-growth remainder round) · shape: agent-tool | found: 3, new: 3, confirmed: 2, fixed: 2, unexecuted: 0, edits: 12 | method: re-derivation — P3-1…P3-4 and context-11 re-executed FIXED; new: the accepted wedge departed from the CONVERGED spec's whole-read bound (`docs/superpowers/specs/2026-10-18-external-services-page-design.md:294`, :413 — read by the lead) and credited an unexecuted unix-socket probe; resolved by amending the spec (D-968, line-count neutral, § Amendments): the read runs in a child process killed at its deadline; the context seat's fake-routing note recorded, not a defect (the chain fakes answer `[]` for `api_keys`) | 2b88aae312931ea72add46212ab304a5 → c5e60b86f62025100bf039df4fa3ae11 |
| Pass 5 | opus×1 + sonnet×1 (round-1 owners) · the pass-4 fixed set and the spec amendment (D-968) + one hop · shape: agent-tool | found: 6, new: 6, confirmed: 6, fixed: 6, unexecuted: 0, edits: 8 | method: re-derivation — R4-1 and R4-2 re-executed FIXED; the child design probed (`kill()`+`wait()` on a child blocked in `recv()`: 0.001 s; spawn 0.046 s); new: the board-to-child contract incomplete, a stale § Data flow hook sentence, the `quota_dashboard.py:493` precedent wrong (only :592 runs `sys.executable`), unclosed pipes after a kill, the 5 s overrun after a kill, an isolation DSN that could look up a name — the last executed by the lead (`postgresql:///none?host=<missing dir>` fails in 0.0 s); the context seat confirmed 0 (13 spec cites re-read) | fc170c6d984ff3f6121d02d9a4ee4791 → c6f56ab63dca950194c675fa8bfc7c55 |
| Pass 6 | opus×1 + sonnet×1 (round-1 owners) · the pass-5 fixed set (the board-to-child contract, the spec edits) + one hop · shape: agent-tool | found: 1, new: 1, confirmed: 1, fixed: 1, unexecuted: 0, edits: 4 | method: re-derivation — F5-1..F5-6 re-executed FIXED (`kill()`+`communicate()` 0.001 s, both pipes closed; the isolation DSN fails in 0.000 s); new: the board had no test telling the child's line from a raw traceback (an import failure before the handler printed `Traceback (most recent call last):`, probed) — fixed by imports inside the child's one `try` and a one-line `^[A-Za-z_][\w.]*: ` test, executed by the lead (handled → the class line, crash and silent exit → `ReadFailed`); the context seat confirmed 0 (13 spec cites re-read, 565 lines) | f8bab6847243d5d31bb1b8198ac03e55 → 10f78772dba1ff6ceb7bd6bad00dd213 |
| Pass 7 | opus×1 (the rules slice's round-1 owner; the context slice untouched since its pass-6 zero) · the pass-6 fix (T04's child error line) + one hop · shape: agent-tool | found: 1, new: 1, confirmed: 1, fixed: 1, unexecuted: 0, edits: 3 | method: re-derivation — F6-1 re-executed FIXED (6 classification cases); new: a warning printed before the child's line defeated the one-line test (`ReadFailed: <string>:2: UserWarning: w`, probed) — the site's second defect, so the rule was REWRITTEN, not patched: the board classifies the LAST non-empty stderr line against `^[A-Za-z_][\w.]*:`, which also reads a traceback's closing class line; row 4 pins it; executed by the lead over 7 cases (handled, crash, silent exit, warning + handled, warning + crash, empty message, stray last line) | 10f78772dba1ff6ceb7bd6bad00dd213 → 616f1005d6de380e101bc05d3dae3b89 |
| Pass 8 | opus×1 (the rules slice's round-1 owner; the context slice untouched since its pass-6 zero) · the pass-7 rewrite (T04's stderr classification) + one hop · shape: agent-tool | found: 1, new: 1, confirmed: 1, fixed: 1, unexecuted: 0, edits: 3 | method: re-derivation — F7-1 re-executed FIXED (7 of 7 cases); new: argparse's `SystemExit` escapes `except Exception` and its `inventory_read.py: error: …` line matched the class regex (probed, exit 2) — the stderr site's THIRD defect, so the site is DELETED: every outcome is one JSON object on stdout (`rows` on exit 0, a string `error` on exit 1, built under `except BaseException` with `--deadline` read by hand), stderr is never read, anything else is `ReadFailed: exit status <n>` — which also closes the held exit-0 bad-JSON gap; executed by the lead over 10 cases (success, import, multi-line message, interrupt, empty message, argv missing, argv bad, raw crash, exit-0 junk, exit-0 error) | 616f1005d6de380e101bc05d3dae3b89 → 961001d9bec01ddd3c30fd7c2000d17a |
| Pass 9 | opus×1 (the rules slice's round-1 owner; the context slice untouched since its pass-6 zero) · the pass-8 rewrite (T04's one-JSON-object outcome contract) + one hop · shape: agent-tool | found: 0, new: 0, confirmed: 0, fixed: 0, unexecuted: 0, edits: 0 | method: re-derivation — F8-1 re-executed FIXED (the JSON outcome contract re-run independently); no contradiction with spec § Failure (`docs/superpowers/specs/2026-10-18-external-services-page-design.md:294`) or T04 rows 1-4; every Coverage Checklist row adjudicated; `check_plan_tickets` 0 findings | 9ea0929b4e22f4897f0888a32b4d401c → 9ea0929b4e22f4897f0888a32b4d401c |

## Residual unknowns

- Resolved: the import seams (no cycle; `inventory.py` imports only the package and the stdlib) — the Opus seat.
- Resolved: the per-ticket READ budget — the live wiring is indivisible and is T04, the Integration ticket.
- Resolved: whether libpq's `connect_timeout` bounds a unix-socket connect is no longer load-bearing — T04 kills the
  child at the read's deadline whatever the socket does.
- Resolved: a registry server that accepts a connection and never answers — the read runs in a child process the
  collector kills at the read's deadline, so the whole read ends within 5 s as spec :294 and :413 require; no
  connection is cancelled (`psycopg2`'s `cancel()` froze every thread in this review's pass-3 TCP probe).
- Open: the 4,000 px height is still the spec's estimate — resolution: T04's browser test measures the section and the
  receipt records the number; past the bar, collapse further before any bar change (spec § Risks).
- Resolved: `scripts/tests/test_registry_sync.py:394` runs only with `REGISTRY_WRITE_TESTS=1`, which writes
  `test_zzz_regsync` rows to the LIVE registry (its skip reason, `:41-44`), so no gate runs it; the shape it reads —
  `gd.load()` returning the rows list with `provider`, `keys` and `projects` — is guarded by T02's first Behavior
  row, which feeds a fake cursor `api_keys` rows of each kind and asserts `keys`, `unattributed` and `projects`
  per provider; T03's chain cases (`tests/test_external_services_chain.py:1117`, :2459-2462) keep `gd.load()`
  returning the list.
- Open: the static file's retirement has no owner yet — resolution: T04's close files a work item naming it (spec § Risks).
