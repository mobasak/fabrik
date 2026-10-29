# T04 — Integration: the live section in the Services view, hermetic board tests, the route's 303, the whole-plan close
Appetite: 360
Integration: true

## Scope
Implements spec § Chosen approach item 1 (`docs/superpowers/specs/2026-10-18-external-services-page-design.md:105`),
§ Failure's live half (:284), the board half of § Contract deltas (:308), D2, D8 and D9 (:485, :499, :503), and
§ Validation's browser and accessibility rows (:335). Indivisible: the collector in `scripts/sysadmin/quota_dashboard.py`
(144,534 B), the Services view, the removed link card and its four strings, the test isolation helper and the four
board test files that pin the link card or render Services (`tests/test_quota_dashboard.py` alone is 247,958 B)
change together, or a commit between them leaves a red suite. The route's `303` could land in a commit of its own;
it stays here by choice (spine § Ticket breadth). Then the whole-plan close.

The read runs in a CHILD PROCESS, so the spec's whole-read bound holds whatever the server does (spec
`docs/superpowers/specs/2026-10-18-external-services-page-design.md:294`, :413). A new
`scripts/sysadmin/inventory_read.py` is that child: run as `[sys.executable, <its path>, "--deadline", <epoch seconds>]`
like the board's rotation call (`quota_dashboard.py:592`), it puts `scripts/` and `scripts/sysadmin/` on its own `sys.path`,
connects with `registry_db.connect(connect_timeout=2, options="-c statement_timeout=2000")`, calls
`inventory.load(conn, before_query=…)` re-arming `SET LOCAL statement_timeout` to the deadline left (never below
1 ms), and reports EVERY outcome as one JSON object, written once to stdout: on success
`{"rows": [<row>, …], "synced_at": <float> | null}`, every row carrying T02's keys with strings, ints, floats,
`null` and lists of strings only (a balance or price is converted to `float` before `json.dumps`), exiting 0; on
any failure `{"error": "<ExceptionClass>: <first line of the message>"}`, exiting 1. Its module top imports only
`json` and `sys`; everything else — reading `--deadline` from `sys.argv` by hand (no argparse, which prints and
exits on its own), importing `registry_db`, `inventory` and psycopg2, the read and the success object's
`json.dumps` — runs inside one `try` whose `except BaseException` builds the error object, so a bad argv, an import
failure or an interrupt is reported the same way; the one write to stdout follows the `try`. The board process never imports `registry_db` or psycopg2 (D9 holds in the child: a missing psycopg2
is the child's failure, so the section's error state), and needs no `sys.path` change.

The collector, `_inventory(ctx)`, in `quota_dashboard.py`, keeps two fields behind ONE lock: the last good read
(rows, `synced_at`, the read's START time) and the read in flight (its `subprocess.Popen`, its start, its
deadline, a done event). Each request has ONE deadline, 5 s from its own arrival, and every wait it makes is
bounded by what is left of it. Under the lock — held only for these decisions, never across a read — a request
(1) serves the last good read if it started under 60 s ago; else (2) when no read is in flight, spawns the child;
else (3) joins the read in flight. It then releases the lock and waits on that
read's done event until its OWN deadline. A read's deadline is 4.5 s after its spawning request's arrival, so the
kill, the cleanup and the render fit inside that request's 5 s. The spawning request's waiter thread reads the
child with `communicate(timeout=<the read's deadline left>)` and on timeout kills it and calls `communicate()`
again, which reaps the child and drains and closes both pipes and cannot block on the server — the child is
gone (`kill()` then `communicate()` on a child blocked in `recv()` returned in 0.001 s with both pipes closed, in the
review's pass-6 probe); it writes the last good read under the lock on success, and clears
the in-flight field on every exit — so a read never outlives its 5 s and at most one is ever alive. ONE outcome
rule covers every request that ends without a fresh result (its wait ran out, the child failed or was killed):
the section's error state, as spec § Failure states; the last good read is served only inside its 60 s, and a
failed read never replaces it. The error state carries the failure's class and first line only:
`ReadTimeout: registry read killed at its deadline` for a killed child; else the child's stdout parsed as JSON —
an object with `rows` and exit 0 is the fresh read, an object whose `error` is a string gives that string — and
anything else (stdout not one JSON object, or a shape that does not match its exit status) gives
`ReadFailed: exit status <n>`. The child's stderr is drained by `communicate()` and never read. No connection is
ever cancelled: `psycopg2`'s `cancel()` against a server that accepts and never answers froze every thread of the
process in this review's pass-3 probe (TCP, executed); the child's kill is what ends a stalled read. The collector
also reads `classified_at` as the mtime of
`_FABRIK_ROOT / ".tmp/external-services/classify_last.json"`. `_view_data("services")` carries `inventory` in place of
`ext_page`; `views/services.py` renders the section after the pool and API cards and drops `_external` and its
`link` import; `/external-services.html` answers `303` to `/#services` with no removal date; `EXT_SERVICES_HTML` and
`QUOTA_DASH_EXT_SERVICES` go.
DO-NOT: change `inventory.py` or `gen_dashboard.py` (a defect there goes back to its owner ticket); touch the `commands`
branch's `ext_services` key (`quota_dashboard.py:2386-2390`, a different list read by
`tests/test_quota_dashboard_server.py:470`); let any board test read the real registry.

Depends: T01, T02, T03
Parallel: ⛓️
Complexity: native
Gate: /opt/fabrik/scripts/capped_run.sh -- .venv/bin/python -m pytest tests/test_quota_dashboard.py tests/test_quota_dashboard_server.py tests/test_quota_dashboard_views_misc.py tests/test_quota_dashboard_page_layer.py tests/test_quota_dashboard_browser.py -q -rs
Gate: .venv/bin/python scripts/final_gate.py --check --json && .venv/bin/python scripts/enforcement/check_convergence.py
Docs: `CHANGELOG.md` (this ticket's `### Added|Changed|Fixed` entry atop `[Unreleased]`); `INDEX.md` (a row for `scripts/sysadmin/inventory_read.py`, and the quota-dashboard test rows whose counts change); `docs/workstation/quota-dashboard.md` (the Services section, the route row, the setting row, the hermetic-tests sentence, the related-scripts block); `docs/workflows/DATA_SYNC_WORKFLOW.md:46-47` wording check; `capabilities.json` + `docs/CAPABILITIES.md` regenerated by `scripts/generate_capability_index.py` after T03's retirement, never by hand

## Touches
- scripts/sysadmin/quota_dashboard.py
- scripts/sysadmin/inventory_read.py — NEW: the child process that reads the registry
- scripts/sysadmin/dashboard_ui/views/services.py
- scripts/sysadmin/dashboard_ui/strings.py
- tests/quota_dashboard_isolation.py
- tests/test_quota_dashboard.py
- tests/test_quota_dashboard_server.py
- tests/test_quota_dashboard_views_misc.py
- tests/test_quota_dashboard_page_layer.py
- tests/test_quota_dashboard_browser.py
- docs/workstation/quota-dashboard.md
- docs/workflows/DATA_SYNC_WORKFLOW.md
- capabilities.json
- llms.txt
- docs/CAPABILITIES.md
- docs/development/reviews/2026-10-18-plan-1-external-services-inventory-review.md

## Behavior Contract
- **Given** the board test isolation, **When** any board test renders the Services view, **Then** the collector's spawn is replaced by a stub returning the census fixture or a stated failure, `SERVICES_REGISTRY_DSN` names an unusable DSN so a real child cannot reach the registry, the board process imports neither registry_db nor psycopg2, and the 60 s slot is empty at each test's start (spec § Validation; tests/quota_dashboard_isolation.py:35)
- **Given** the real child against a fake server that accepts and never answers, **When** the Services view is requested, **Then** the inventory section shows its error state within 5 s with the failure's class and first line only, the child is killed and gone, and the pool and API cards render (spec § Failure; scripts/sysadmin/quota_dashboard.py:2218)
- **Given** an empty slot, two concurrent requests, a failed child, and a last good read 59 s and 61 s past its start, **When** requests reach the collector, **Then** the concurrent requests share one child, every request answers within 5 s of its own arrival, every request without a fresh result serves the section's error state, a failed read leaves the last good read in place, the in-flight field clears on every exit so the next request starts afresh, a request held on the lock answers within its own deadline, no connection is cancelled, and the read at 59 s is served while 61 s spawns a new child (spec § Failure; scripts/sysadmin/quota_dashboard.py:531)
- **Given** psycopg2 cannot be imported in the child, **When** the Services view renders, **Then** the board serves every view and only the inventory section shows its error state, naming the import's exception class from the child's error object whatever its stderr holds, and the board process never imported psycopg2 (spec § Contract deltas D9)
- **Given** a bookmark to /external-services.html, **When** it is requested, **Then** the board answers 303 to /#services with an empty body, and no link card, ext_page key or services.ext string remains (spec § Contract deltas; scripts/sysadmin/quota_dashboard.py:2833)
- **Given** the Services view at census scale (tests/external_services_fixture.py) in a 1280 px and a 375 px browser, **When** the operator types a provider name, picks each select, force-swaps and clears, **Then** the group holding the match opens, groups with no match are hidden, the count updates, Cost free shows no freemium row, the Needs-attention list is unchanged by any filter, the filter values, the qd-filter-open:<group> record and the visible filtering survive the swap, clearing closes what the filter opened and keeps a hand-opened group open, and the page never scrolls sideways (spec § Validation)
- **Given** the inventory section at census scale with groups collapsed, and the static file gen_dashboard writes from the same fixture, **When** the browser measures each at 1280 px and 375 px, **Then** the section is at most 4,000 px tall, the static file lays out without sideways scroll inside its wrapper, and axe reports no violation of 1.3.1, 1.4.1, 1.4.3, 1.4.11, 2.1.1, 3.3.2 or 4.1.3 in both themes, with an open row detail included (spec § Validation; spec § Risks the plan carries)
- **Given** two renders of the Services view a minute apart with the same registry, **When** their fragments are compared, **Then** the data-stamp is unchanged (spec § Data flow; scripts/sysadmin/dashboard_ui/views/__init__.py:66)

## Context Files
- .windsurf/rules/core/10-python.md
- .windsurf/rules/core/45-testing-strategy.md
- .windsurf/rules/saas/60-saas-ui.md
- docs/superpowers/specs/2026-10-18-external-services-page-design.md
- scripts/sysadmin/dashboard_ui/inventory.py
- scripts/sysadmin/dashboard_ui/components.py
- scripts/registry_db.py
- tests/external_services_fixture.py
> "The route itself answers `303` to `/#services`, with no removal date (the board test asserts the `303`)" — `docs/superpowers/specs/2026-10-18-external-services-page-design.md:313-314`

Grounding (read at c4e827715): the services branch is `scripts/sysadmin/quota_dashboard.py:2392-2402`; the `/repos.html`
303 template is :2833-2843 (Location, empty body, `Cache-Control: no-store`); `_guarded` (:2218) catches but never
times out; libpq connects in C and never calls Python's `socket.socket.connect` (executed: a spy on it saw no call
while `psycopg2.connect('host=127.0.0.1 port=1 …')` failed), so the board suites' `no_network` guard
(`tests/quota_dashboard_isolation.py:51-58`) cannot see a registry connection, TCP or the default peer-auth socket
(`scripts/registry_db.py:19`); the guard is therefore two-sided — `isolate()` (:35) sets `SERVICES_REGISTRY_DSN`
(`scripts/registry_db.py:27`) to `postgresql:///none?host=<tmp_path>/no-socket`, a unix-socket directory that does
not exist, so any child fails at once with no name lookup or network attempt; it is inherited by any child, and `after_load` (:46) replaces the
collector's spawn with the stub — and without it every Services render in these suites would read the live
registry —
`tests/test_quota_dashboard.py` renders Services at :1284, :1349, :1527, :1855, :1864, :1873, :1961, :1966, :2476,
:2493 and over every view at :1886; `tests/test_quota_dashboard_page_layer.py` builds its board at :646-666; the browser
fixture serves the real board (`tests/test_quota_dashboard_browser.py:89-121`). The tests to rewrite with the link
card: `tests/test_quota_dashboard.py:1844-1867` and :2240-2278 (`urlopen` follows a 303, so the route test uses a
no-redirect opener), `tests/test_quota_dashboard_server.py:454`, `tests/test_quota_dashboard_views_misc.py:175`,
:327-345, :432-435 (the cadence set gains 86400), :450, :497-500, `tests/test_quota_dashboard_page_layer.py:469`,
:662, :783-784.
