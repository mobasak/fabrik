# T02 — Server wiring: the request guard, view and static routes, the view data, the snapshot token
Appetite: 300

## Scope
Implements spec § Contract deltas (every row except the `GET /` and `/repos.html` flips, which are T07's),
INV-6 of § Invariants with the configured host settled (review row P3-1), the 409 half of § Which actions
confirm, and the data half of INV-1: the view registry every view ticket plugs into, the pure formatters the
views share, and a data function per view so the view modules stay pure renderers that never touch this module.
Today's page (`render`, `_repos_page`, `generate`) keeps working unchanged: every existing test in
`tests/test_quota_dashboard.py` stays green in this ticket.
DO-NOT: build any view's markup (T03–T06), change `GET /` or `/repos.html` (T07), change any collector's cadence,
cache or output beyond the additive `root` key named below (INV-1), or put a probe or a subprocess on a request
thread that today's code keeps off it.

Depends: T01
Parallel: ⛓️
Complexity: native
Gate: .venv/bin/python -m pytest tests/test_quota_dashboard_server.py tests/test_quota_dashboard.py -q
Docs: none (T07 owns `docs/workstation/quota-dashboard.md`)

## Touches
- scripts/sysadmin/quota_dashboard.py — PRIMARY PATH
- scripts/sysadmin/dashboard_ui/views/__init__.py — the view registry, `ViewContext`, `ViewResult`
- scripts/sysadmin/dashboard_ui/snapshot.py — the snapshot token
- scripts/sysadmin/dashboard_ui/fmt.py — the pure formatters, moved out of the module
- tests/test_quota_dashboard_server.py — NEW

## Consumes
- T01's `dashboard_ui.components` (`Safe`, `region_state`, `stale_banner`).

## Produces (consumed by T03–T07)
- `dashboard_ui.views.VIEWS = ("overview", "work", "accounts", "usage", "commands", "services")` — the navigation order.
- `ViewContext(opt_root: Path, fabrik_root: Path, now: float)` and `ViewResult(html: Safe, pause_targets: list[dict]
  | None = None, item_targets: list[dict] | None = None)` (frozen dataclasses).
- The view-module protocol: `dashboard_ui/views/<name>.py` defines `render(data: dict, ctx: ViewContext) -> ViewResult`
  and MAY define `collect(ctx: ViewContext) -> dict`, whose keys are merged over the server's data. `views.load(name)`
  imports `dashboard_ui.views.<name>` with `importlib.import_module`; a missing module or one without `render` raises
  `LookupError`. Every fragment's root element carries `data-stamp` = a hash of its markup (T01's unchanged-swap skip).
- `dashboard_ui.fmt` — the nine pure helpers only the HTML builders use today (an AST scan at 18d619f1e, every one
  free of module-level names): `_ago`, `_cap`, `_fmt_age`, `_fmt_reset`, `_posture_sub`, `_repo_order`,
  `_stage_tone`, `_tone`, `_opt_root` move there as public names (`ago`, `cap`, … , `opt_root`), and the module
  imports them back under their old names so today's builders and tests are untouched.
- `quota_dashboard._view_data(name: str, ctx) -> dict` — what each view receives. Every collector value is the
  collector's own output, unchanged; a collector that raises becomes `{"error": "<Type>: <message>"}` for that key
  only. The values today's builders read from module configuration are passed as data, because no view may import
  this module:
  - every view: `"now"`, `"refresh_s"` (REFRESH_S), `"probe_interval_s"` (PROBE_INTERVAL_S);
  - overview → `"work"` (the cached work data below), `"box"` (`collect_box`, `scripts/agent_status.py:417`, or
    `{"error": …}`), `"status"` (`_LAST_STATUS` below), `"budget"` (`_budget_data()`), `"health"` (`{"stale": […],
    "failed": […]}` — a view whose data is older than twice its cadence, and every collector key holding `error`
    plus a probe failure newer than the payload), `"ag_states"` (_AG_STATES), `"hub_agents"` (_HUB_AGENTS);
  - work → `"work"`, `"hub_agents"`, `"owner_order"` (the order `_owner_order` gives, per repo), `"repos_ttl_s"`,
    `"next_cap"` (NEXT_CAP) and `"next_tip_cap"` (NEXT_TIP_CAP) — the Next cell's text and tooltip caps (:2250-2251, read
    at :2445);
  - accounts → `"status"`, `"queue"` (the rotation order `_display_order`/`_queue_for_render` give today,
    `scripts/sysadmin/quota_dashboard.py:1262`, :879), `"trigger_threshold"` (TRIGGER_THRESHOLD), `"reserve_pct"`
    (_RESERVE_PCT), `"drain_band"` (`_drain_band()`, :3548), `"five_hour_s"`, `"seven_day_s"`, `"switch_header"`,
    `"pool_policy_on"` (`_pool_policy_on()`, read by `_governor_panel` at :1246), `"slug_re"` and `"email_re"` (the
    `_SLUG_RE` / `_EMAIL_RE` patterns as strings, :96-97, which decide which rows get controls);
  - usage → `"spend"` (`_spend_data()`, the whole sidecar dict `_spend_panel` reads: top-level `built_at` (:1137) and
    `per_model_spend.{tiers, daily, spend_usd, base_rate_per_mtok, monthly_spend, window_start, window_end,
    unweighted}` (:1006, :1115, :1136, :1147-1149));
  - commands → `"commands"` (`_load_commands()`, :1574, or `{"error": …}`), `"ext_services"` (_EXT_SERVICES — the
    matrix's column keys, labels and titles, :2205-2229);
  - services → `"pool"` (`_pool_credits(fetch=False)` — `None` when unconfigured or uncached), `"apis"`
    (`_api_quotas(fetch=False)`), `"ext_page"` (`{"path": "/external-services.html", "mtime": <EXT_SERVICES_HTML's
    mtime or None>}`).
- The work data cache: `_work_data()` returns `_collect_work(_opt_root())` cached for REPOS_TTL_S under `_repos_lock`
  and dropped by `_repos_gen` / `_drop_repos_cache` exactly as `_repos_page` caches its page (:3014-3046), so the
  collector's cadence and its warnings sink (:2299) see no concurrent callers. `_collect_work`'s entries gain one
  additive key, `root` — the tree it read the items from (`store.parent.parent.resolve()`, :2295) — beside `main`.
- `quota_dashboard._LAST_STATUS: list[tuple[float, dict] | None]` — the payload `_generate_locked` actually used on
  its last pass, INCLUDING the fallback it builds when the probe fails (the last good reading plus `probe_failed`
  and the live `active` pointer, :3478-3500), swapped in whole; and `_LAST_PROBE_FAILURE: list[tuple[float, str] |
  None]` — when the probe last failed and its error class, cleared by a successful probe. The time stamped on
  `_LAST_STATUS` is ALWAYS the time of the last SUCCESSFUL probe, carried unchanged through every fallback pass, so a
  continuing outage ages the payload and trips the bound below. That time is SEEDED once, before the first probe,
  in `_start_probe_loop` (:3653, which `serve()` calls before it serves any request, :3991-3993): the mtime of
  `quota.json` when the file lacks `probe_failed`, else `None` (unknown — stale at once). A first pass whose probe
  fails then carries the seeded value, and the fallback's rewrite of `quota.json` (:3497) can no longer launder it. When `_LAST_STATUS` is
  still `None` (a fresh process), `_view_data` seeds it from `quota.json` on disk (`_JSON`, :106) with the file's
  mtime as its time — unless the file holds `probe_failed` (the fallback rewrites it, :3497), when its time is
  unknown and the payload is treated as stale at once; with neither, `"status"` is `{"error": "no reading yet"}`. A request NEVER runs `_probe()`
  itself except through the one bounded path today's `_fresh_html` already has (:3674-3700): when `_pointer_moved()`
  and `_LAST_SYNC_REGEN` is older than PROBE_TIMEOUT_S, one synchronous `generate()`; and when the payload is older
  than MAX_AGE_S, `_regen_async()` — the same two triggers, now on `/v/overview` and `/v/accounts`.
- The stale banner on the views that show quota data (overview, accounts), replacing `_with_stale_banner`'s
  page-level injection (:3430): prepended by the dispatcher as T01's `components.stale_banner` when
  `_LAST_PROBE_FAILURE` is newer than the payload's time, or the payload is older than
  `PROBE_INTERVAL_S + PROBE_TIMEOUT_S + 60` (today's bound and its reasoning, :3440-3450).
- `quota_dashboard._budget_data()` — served from `_budget_cache`, which now holds the parsed data dict beside the HTML
  (`_budget_cache["data"]`), refreshed only by the background thread `_budget_banner` already starts (:2116-2137);
  `QUOTA_DASH_BUDGET=0` returns `{"disabled": True}` as `_budget_banner` returns "" today (:2122). The data carries
  `"caveats"` as a list of PLAIN strings — the text `_budget_caveats` (:2078) builds today, unescaped, so the Overview's
  components escape it once. `_spend_data()` —
  the data half of `_spend_panel` (:1021). The HTML halves keep their names and output and call the data halves.
- Targets: the dispatcher keeps the last `pause_targets` and `item_targets` of EACH view as a named slice and publishes
  the UNION through `_publish_pause_targets` (:2647) / `_publish_item_targets` (:2714), so one view's refresh never
  evicts another view's targets. Fail-closed as today (:2750, :2810 — "no board, no buttons"): a view whose `collect` or
  `render` raised, or that returned no targets, replaces its own slice with `[]`. Until T07 removes it, `/repos.html`'s
  build publishes as its own slice, `repos`, through the same union. `_ITEM_TARGETS` maps `(repo, id)` to `(main, root)`.
- `snapshot.token(item: dict) -> str` — the first 16 hex characters of sha256 over the JSON of `[question, status,
  ground, len(comments), sorted(alt_ids)]` (missing fields as `None`, `0`, `[]`).
- `item_verdict(repo, item, action, text="", token=None)` — after the target lookup (:2733-2738) reads
  `<root>/.fabrik/work/<item>.json` (the same tree the card was rendered from, `scripts/work.py:273-312` `_item_path`);
  a `token` that differs from `snapshot.token` of the item as it stands returns `409 {"ok": false, "error":
  "changed"}` and runs nothing; an absent token is accepted while `_LEGACY_TOKEN_UNTIL` (a module constant, `None` here;
  T07 sets the date) is `None` or today (local date) is on or before it, and refused with the same 409 after it.
  `do_POST` passes `body.get("token")`. Comment changes the token too (work.py appends every verdict to `comments`,
  `scripts/work.py:3822`); T01's forced refresh after a successful write re-renders the card with its new token.
  The check runs before `work.py verdict` takes its store lock — the window between the two is accepted (one
  operator, one board).

## Steps
1. Write `tests/test_quota_dashboard_server.py` FIRST (the server in-process on port 0, loading the module as
   `tests/test_quota_dashboard.py`'s `_load(tmp_path, monkeypatch, **env)` does) and watch every case fail:
   - Host: `evil.example:<port>` → 421; `127.0.0.1:<port>`, `localhost:<port>`, `[::1]:<port>` → served; with
     `QUOTA_DASH_HOST=10.0.0.5`, `10.0.0.5:<port>` is served too (P3-1).
   - A POST carrying `Sec-Fetch-Site: cross-site` → 403 before the body is read; `same-origin`, `same-site`, `none` and
     no header reach the existing `X-Quota-Dash` guard.
   - `GET /v/<each view>` with a fake view module monkeypatched into `dashboard_ui.views` → 200 `text/html` fragment
     with `data-stamp`; `GET /v/nope` and `/v/work/fabrik` → 404; a view whose `render` raises → 200 with the
     `region_state("error", …)` fragment naming the exception's type in words, never a traceback.
   - `GET /static/app.css` and `/static/app.js` → 200, `Cache-Control: no-cache`, an `ETag`, 304 on a matching
     `If-None-Match`; `/static/../quota_dashboard.py`, `/static/%2e%2e/x` and any other name → 404.
   - The 409 cases — a token from before a comment was appended, before the ground changed, before a duplicate merge
     added an `alt_ids` entry — and the 200 case with the current token; an absent token accepted with
     `_LEGACY_TOKEN_UNTIL = None` and refused (409) with a date in the past.
   - Targets: the Work view's targets survive an Overview render, and a following verdict POST for a Work-only item is
     found without a rebuild; a view that raises empties only its own slice, and a POST for a target only it held is
     refused "not on the board"; a `/repos.html` build does not evict a view's slice; after a simulated restart
     (`_ITEM_TARGETS` and `_PAUSE_TARGETS` emptied, no view rendered yet) a verdict POST and a pause POST for a target the
     fixture stores hold are found through the rebuild-on-miss as it stands in this ticket, `_repos_page(fresh=True)`
     (`scripts/sysadmin/quota_dashboard.py:2664`, :2735) — re-pointing it at the view dispatcher, and its restart test,
     are T07 step 3's.
   - Probe state: a probe that raises makes `/v/accounts` carry the stale banner and `health.failed` name it, and the
     payload's time stays the last good probe's across three failing passes, including when the process started with a
     good `quota.json` and its very first probe failed, and when it started with a `probe_failed` one (stale at once); a payload
     older than the bound carries the banner; a fresh one none; a fresh process with `quota.json` on disk serves it
     without probing (assert `_probe` was not called); `_pointer_moved()` true triggers exactly one bounded
     `generate()`.
   - Budget: `_view_data("overview")` with `QUOTA_DASH_BUDGET=0` returns `{"disabled": True}` and never starts a
     subprocess; with the cache empty it starts the background thread and returns at once.
   - Work data: two concurrent `/v/work` requests run `_collect_work` once.
2. Add `_guard(self, method) -> bool` to `_Handler` (`scripts/sysadmin/quota_dashboard.py:3855`), called first in
   `do_GET` (:3943) and `do_POST` (:3871). The allowed `Host` values are `127.0.0.1`, `localhost`, `[::1]` and the
   configured `QUOTA_DASH_HOST` (:49-52) when it is none of those, each joined to the port the server is bound to
   (`self.server.server_address[1]`, so a test's port 0 works); 421 carries a one-line text body. `ensure()`'s
   `_health_ok` (:4023-4026) sends `Host: <QUOTA_DASH_HOST>:<port>`, which the allowlist admits — leave it. (`[::1]`
   is allowlisted for a client that names it; the AF_INET server itself never answers on ::1.)
3. Put `Path(__file__).resolve().parent` on `sys.path` once at import (the only form under which
   `importlib.import_module("dashboard_ui.views.<name>")` and the views' `from dashboard_ui import components`
   resolve), then `import dashboard_ui`. `dashboard_ui` never imports `quota_dashboard` (running as `__main__`, a
   second import would split its target registries).
4. Add `/v/<view>` to `do_GET` through the existing shared tail (:3975-3980, `no-store`); add `/static/<name>` as its
   OWN branch (the shared tail always sends 200 and `no-store`): an allowlist of the two names, the ETag the file's
   sha256 prefix read per request.
5. Move the nine formatters into `dashboard_ui/fmt.py` and import them back; add `_work_data`, `_LAST_STATUS`,
   `_LAST_PROBE_FAILURE` (set in `_generate_locked`'s probe `except`, :3478, cleared after a good probe), the data
   halves of `_budget_probe` and `_spend_panel`, `_view_data`, and the view dispatcher that calls `collect` (when the
   module has one), `render`, then publishes the union of targets.
6. Add the token to `item_verdict` and pass it from `do_POST`.
7. Run the Gate to green (the 169 tests in `tests/test_quota_dashboard.py` unchanged and green), then
   `.venv/bin/ruff check` on the Touches.
8. `python scripts/enforcement/check_doc_sync.py`.
9. `/fabrik-review` on the ticket's changed surface to its coverage-adjudicated exit — this is a request guard on a
   page that runs account switches, so the review covers the guard's every branch.
10. Commit the Touches.

## Behavior Contract
- **Given** a request whose Host is not 127.0.0.1, localhost, [::1] or the configured QUOTA_DASH_HOST at the bound port, **When** the server receives it, **Then** it answers 421 and runs nothing (spec § Invariants INV-6; scripts/sysadmin/quota_dashboard.py:3943)
- **Given** a POST carrying Sec-Fetch-Site cross-site, **When** the server receives it, **Then** it answers 403 before reading the body, while same-origin, same-site, none and an absent header pass on to the header guard (spec § Invariants INV-6; scripts/sysadmin/quota_dashboard.py:3876)
- **Given** a view name in VIEWS, **When** GET /v/<view> is requested, **Then** the server returns that view's HTML fragment, a view that raises returns its error state in words, and any other name returns 404, while /static/app.css and /static/app.js come back with Cache-Control no-cache and an ETag, 304 on a matching If-None-Match, and no other /static/ path is served (spec § Contract deltas)
- **Given** a verdict POST whose snapshot token was taken before the item's question, status, ground, comment count or merged duplicates changed, **When** it arrives, **Then** the server answers 409 changed and work.py is not run (spec § Which actions confirm; scripts/sysadmin/quota_dashboard.py:2724)
- **Given** a verdict POST with no token, **When** the legacy window is open it is accepted as today, **Then** once the window's date has passed it is refused with the same 409 (spec § Which actions confirm; spec § Lifecycle)
- **Given** two views that each returned targets, **When** a guarded POST for a target of either arrives, **Then** it is found on the board without a rebuild, whichever view rendered last (spec § Invariants INV-1; scripts/sysadmin/quota_dashboard.py:2733)
- **Given** the probe failed after the payload was read, or the payload is older than a probe cycle, **When** a view that shows quota data is fetched, **Then** it carries the stale banner on tokens and the Health data names the failure, while a fresh payload carries none and a request never probes beyond today's one bounded pointer-moved regeneration (spec § Lifecycle; scripts/sysadmin/quota_dashboard.py:3478)
- **Given** the budget probe and the spend panel split into data and HTML halves, **When** today's page renders and the views fetch their data, **Then** today's output is unchanged, every existing dashboard test passes, and no subprocess or collector runs on a request thread more often than today (spec § Invariants INV-1; scripts/sysadmin/quota_dashboard.py:1965)

## Context Files
- .windsurf/rules/core/35-security-auth.md
- .windsurf/rules/core/10-python.md
- .windsurf/rules/core/45-testing-strategy.md

The spec (`docs/superpowers/specs/2026-10-16-command-centre-dashboard-design.md`) is NOT a Context File here:
with `scripts/sysadmin/quota_dashboard.py` it is 263,449 B, over the 262,144 B read budget. Every spec rule
this ticket needs is stated in its Scope, Produces, Steps and Behavior Contract.
