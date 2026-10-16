# T02 — Server wiring: the request guard, view and static routes, the view data, the snapshot token
Appetite: 240

## Scope
Implements spec § Contract deltas (every row except the `GET /` and `/repos.html` flips, which are T07's),
INV-6 of § Invariants with the configured host settled (review row P3-1), the 409 half of § Which actions
confirm, and the data half of INV-1: the view registry every view ticket plugs into, and a data function per
view so the view modules stay pure renderers. Today's page (`render`, `_repos_page`, `generate`) keeps
working unchanged: every existing test in `tests/test_quota_dashboard.py` stays green in this ticket.
DO-NOT: build any view's markup (T03–T06), change `GET /` or `/repos.html` (T07), or change any collector's
cadence, cache or output (INV-1).

Depends: T01
Parallel: ⛓️
Complexity: native
Gate: .venv/bin/python -m pytest tests/test_quota_dashboard_server.py tests/test_quota_dashboard.py -q
Docs: none (T07 owns `docs/workstation/quota-dashboard.md`)

## Touches
- scripts/sysadmin/quota_dashboard.py — PRIMARY PATH
- scripts/sysadmin/dashboard_ui/views/__init__.py — the view registry, `ViewContext`, `ViewResult`
- scripts/sysadmin/dashboard_ui/snapshot.py — the snapshot token
- tests/test_quota_dashboard_server.py — NEW

## Consumes
- T01's `dashboard_ui.components.Safe` and `region_state` (the error fragment a failed view returns).

## Produces (consumed by T03–T07)
- `dashboard_ui.views.VIEWS = ("overview", "work", "accounts", "usage", "commands", "services")` — the order is
  the navigation order.
- `ViewContext(opt_root: Path, fabrik_root: Path, now: float)` and
  `ViewResult(html: Safe, pause_targets: list[dict] | None = None, item_targets: list[dict] | None = None)`
  (frozen dataclasses).
- The view-module protocol: `dashboard_ui/views/<name>.py` defines `render(data: dict, ctx: ViewContext) ->
  ViewResult` and MAY define `collect(ctx: ViewContext) -> dict`, whose keys are merged over the server's data.
  `dashboard_ui.views.load(name)` imports the module with `importlib.import_module`; a missing module or one
  without `render` raises `LookupError`.
- `quota_dashboard._view_data(name: str, ctx) -> dict` — the server-side data each view receives:
  overview → `{"work": _collect_work(opt), "box": collect_box(opt) or {"error": …}, "status": <the cached
  `_probe()` payload or {"error": …}>, "budget": _budget_data(), "health": {"stale": […], "failed": […]}}` ·
  work → `{"work": …}` · accounts → `{"status": …}` · usage → `{"spend": _spend_data()}` · commands →
  `{"commands": _load_commands(), "matrix": <the rows `_ext_matrix_table` reads>}` · services →
  `{"pool": _pool_credits(fetch=False), "apis": _api_quotas(fetch=False)}`. Each value is the collector's own
  output, unchanged; a collector that raises becomes `{"error": "<Type>: <message>"}` for that key only.
- `quota_dashboard._budget_data()` and `_spend_data()` — the data halves split out of `_budget_probe`
  (`scripts/sysadmin/quota_dashboard.py:1965`, cache `_budget_cache` TTL 60 s at :1960) and `_spend_panel`
  (`scripts/sysadmin/quota_dashboard.py:1021`, reading `_COST_SIDECAR` :1432); the HTML halves keep their
  names and output and call the data halves, so today's page is byte-identical.
- `quota_dashboard._LAST_STATUS: list[tuple[float, dict] | None]` — the newest successful `_probe()` payload
  and when it was read, swapped in whole by `generate()` (:3406) on every probe-loop pass (the
  `_LAST_RENDER_FAILURE` pattern, :3427); `_view_data` reads it, and when it is still `None` (a fresh process)
  probes once synchronously. Views whose data holds `status` (overview, accounts) get today's two stale triggers
  (`_with_stale_banner`, :3430 — a failure newer than the payload, or a payload older than
  `PROBE_INTERVAL_S + PROBE_TIMEOUT_S + 60`) as T01's `components.stale_banner` prepended by the dispatcher; the
  same triggers fill `health.stale`.
- `snapshot.token(item: dict) -> str` — the first 16 hex characters of sha256 over the JSON of
  `[question, status, ground, len(comments), sorted(alt_ids)]` (missing fields as `None`, `0`, `[]`).
- `item_verdict(repo, item, action, text="", token=None)` — after the existing target lookup
  (`scripts/sysadmin/quota_dashboard.py:2733-2738`) reads `<main>/.fabrik/work/<item>.json`; a `token` that
  differs from `snapshot.token` of the item as it stands returns `409 {"ok": false, "error": "changed"}`; an
  absent token is accepted while `_LEGACY_TOKEN_UNTIL` (a module constant, `None` here; T07 sets the date) is
  `None` or today is on or before it, and refused with the same 409 after it. `do_POST` passes `body.get("token")`.

## Steps
1. Write `tests/test_quota_dashboard_server.py` FIRST (the server in-process on port 0, as the existing tests
   load the module — `_load(tmp_path, monkeypatch, **env)` in `tests/test_quota_dashboard.py`) and watch every
   case fail: a GET with `Host: evil.example:<port>` → 421, and with `127.0.0.1:<port>`, `localhost:<port>`,
   `[::1]:<port>` → served; with `QUOTA_DASH_HOST=10.0.0.5`, `10.0.0.5:<port>` is served too (P3-1); a POST
   carrying `Sec-Fetch-Site: cross-site` → 403 before the body is read, while `same-origin`, `same-site`, `none`
   and no header reach the existing header guard; `GET /v/<each view>` with a fake view module monkeypatched
   into `dashboard_ui.views` → 200 `text/html` fragment, `GET /v/nope` → 404, a view whose `render` raises →
   200 with the `region_state("error", …)` fragment and the exception's type in words, never a traceback;
   `GET /static/app.css` and `/static/app.js` → 200, `Cache-Control: no-cache`, an `ETag`, and 304 on a matching
   `If-None-Match`; `/static/../quota_dashboard.py` and any other name → 404; the 409 cases — a token from
   before a comment was appended, before the ground changed, before a duplicate merge added an `alt_ids` entry —
   and the 200 case with the current token; an absent token accepted with `_LEGACY_TOKEN_UNTIL = None` and
   refused (409) with a date in the past; a view's `pause_targets` / `item_targets` published through
   `_publish_pause_targets` (:2647) / `_publish_item_targets` (:2714) so a following POST finds its target;
   `/v/accounts` carries the stale banner when `_LAST_RENDER_FAILURE` is newer than `_LAST_STATUS` and when the
   payload is older than the bound, and carries none for a fresh payload.
2. Add `_guard(self, method) -> bool` to `_Handler` (`scripts/sysadmin/quota_dashboard.py:3855`) and call it
   first in `do_GET` (:3943) and `do_POST` (:3871). The allowed `Host` values are `127.0.0.1`, `localhost`,
   `[::1]` and the configured `QUOTA_DASH_HOST` (:49-52) when it is none of those, each joined to the port the
   server is actually bound to (`self.server.server_address[1]`, so a test's port 0 works); 421 is sent with a
   one-line text body. `ensure()`'s `_health_ok` (:4023-4026) already sends `Host: 127.0.0.1:<port>` — leave it.
3. Load the package the way the module already loads its siblings (by path, `importlib.util`,
   :2541-2544) or by putting `Path(__file__).resolve().parent` on `sys.path` once; `dashboard_ui` must never
   import `quota_dashboard` (running as `__main__`, a second import would split its target registries).
4. Add `/v/<view>` and `/static/<name>` to `do_GET`, both through the existing shared tail (:3975-3980) for
   `no-store` on views; the static ETag is the file's sha256 prefix, read per request (no cache to go stale).
5. Split `_budget_probe` and `_spend_panel` into data and HTML halves (Produces); add `_view_data` and the
   view dispatcher that calls `collect` (when the module has one), `render`, then publishes any returned targets.
6. Add the token to `item_verdict` and pass it from `do_POST` (Produces).
7. Run the Gate to green (the 169 tests in `tests/test_quota_dashboard.py` unchanged and green), then
   `ruff check` on the Touches.
8. `python scripts/enforcement/check_doc_sync.py`.
9. `/fabrik-review` on the ticket's changed surface to its coverage-adjudicated exit — this is a request guard
   on a page that runs account switches, so the review covers the guard's every branch.
10. Commit the Touches.

## Behavior Contract
- **Given** a request whose Host is not 127.0.0.1, localhost, [::1] or the configured QUOTA_DASH_HOST at the bound port, **When** the server receives it, **Then** it answers 421 and runs nothing (spec § Invariants INV-6; scripts/sysadmin/quota_dashboard.py:3943)
- **Given** a POST carrying Sec-Fetch-Site cross-site, **When** the server receives it, **Then** it answers 403 before reading the body, while same-origin, same-site, none and an absent header pass on to the header guard (spec § Invariants INV-6; scripts/sysadmin/quota_dashboard.py:3876)
- **Given** a view name in VIEWS, **When** GET /v/<view> is requested, **Then** the server returns that view's HTML fragment, a view that raises returns its error state in words, and any other name returns 404, while /static/app.css and /static/app.js come back with Cache-Control no-cache and an ETag, 304 on a matching If-None-Match, and no other /static/ path is served (spec § Contract deltas)
- **Given** a verdict POST whose snapshot token was taken before the item's question, status, ground, comment count or merged duplicates changed, **When** it arrives, **Then** the server answers 409 changed and work.py is not run (spec § Which actions confirm; scripts/sysadmin/quota_dashboard.py:2724)
- **Given** a verdict POST with no token, **When** the legacy window is open it is accepted as today, **Then** once the window's date has passed it is refused with the same 409 (spec § Which actions confirm; spec § Lifecycle)
- **Given** a view that returns pause or item targets, **When** a guarded POST for one of them arrives next, **Then** the target is found on the board without a rebuild (spec § Invariants INV-1; scripts/sysadmin/quota_dashboard.py:2733)
- **Given** the last probe failed after the cached payload was read, or the payload is older than a probe cycle, **When** a view that shows quota data is fetched, **Then** it carries the stale banner, built on tokens, and a fresh payload carries none (spec § Lifecycle; scripts/sysadmin/quota_dashboard.py:3430)
- **Given** the budget probe and the spend panel split into data and HTML halves, **When** today's page renders, **Then** its output is unchanged and every existing dashboard test passes (spec § Invariants INV-1; scripts/sysadmin/quota_dashboard.py:1965)

## Context Files
- .windsurf/rules/core/35-security-auth.md
- .windsurf/rules/core/10-python.md
- .windsurf/rules/core/45-testing-strategy.md

The spec (`docs/superpowers/specs/2026-10-16-command-centre-dashboard-design.md`) is NOT a Context File here:
with `scripts/sysadmin/quota_dashboard.py` it is 263,449 B, over the 262,144 B read budget. Every spec rule
this ticket needs is stated in its Scope, Steps and Behavior Contract; T01's components already carry the
§ Components and § Theme rules.
