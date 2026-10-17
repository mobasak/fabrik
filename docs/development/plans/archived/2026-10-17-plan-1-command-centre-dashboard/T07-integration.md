# T07 — Integration: the shell goes live, the old page layer leaves, the tests follow it, the receipt
Appetite: 420

## Scope
The set's single Integration ticket. It owns the indivisible files: `scripts/sysadmin/quota_dashboard.py`
(215,566 B) and `tests/test_quota_dashboard.py` (227,670 B, 169 tests), which no view ticket may split. It flips
`GET /` to the app shell (spec § Contract deltas), turns `/repos.html` into the 14-day redirect to `/#work`
(§ Lifecycle, Adoption), re-points the target registries' rebuild-on-miss at the new builders (INV-1), removes
every old HTML builder from the module (INV-3, INV-4), rewrites the HTML-substring tests against the new
markup's landmarks in the same commit that removes the markup they pinned (spec § Validation), adds the
page-layer and browser tests, rewrites the subsystem doc, and writes the receipt.
DO-NOT: change a collector, a POST endpoint's contract beyond T02's token, or any view module's behaviour
(a defect found in a view goes back to its ticket's owner through the orchestrator).

Depends: T03, T04, T05, T06
Parallel: ⛓️
Integration: true
Complexity: native
Gate: .venv/bin/python -m pytest tests/test_quota_dashboard.py tests/test_quota_dashboard_render_failure.py tests/test_quota_dashboard_posture.py tests/test_quota_dashboard_banner.py tests/test_quota_dashboard_page_layer.py tests/test_quota_dashboard_browser.py tests/test_quota_dashboard_ui_kit.py tests/test_quota_dashboard_app_js.py tests/test_quota_dashboard_server.py tests/test_quota_dashboard_overview.py tests/test_quota_dashboard_work.py tests/test_quota_dashboard_accounts.py tests/test_quota_dashboard_views_misc.py -q
Gate: .venv/bin/python scripts/final_gate.py --check --json
Gate: .venv/bin/python scripts/enforcement/check_convergence.py
Docs: docs/workstation/quota-dashboard.md (the subsystem doc, rewritten); CHANGELOG, INDEX and FEATURES rows through the orchestrator's Deltas

## Touches
- scripts/sysadmin/quota_dashboard.py — the indivisible module (READ-budget hatch)
- tests/test_quota_dashboard.py — the indivisible suite (READ-budget hatch)
- tests/test_quota_dashboard_render_failure.py
- tests/test_quota_dashboard_posture.py
- tests/test_quota_dashboard_banner.py
- tests/test_quota_dashboard_page_layer.py — NEW
- tests/test_quota_dashboard_browser.py — NEW
- docs/workstation/quota-dashboard.md
- docs/development/reviews/2026-10-17-plan-1-command-centre-dashboard-review.md

## Consumes
- Every earlier ticket's Produces: T01's `components.shell` and the static files; T02's `VIEWS`, `_view_data`,
  `_LAST_STATUS`, `_LEGACY_TOKEN_UNTIL`, the guard and the routes; T03–T06's view modules and the targets T03
  and T04 return.

## Steps
1. Write `tests/test_quota_dashboard_page_layer.py` FIRST and watch it fail on today's module: the INV-4 scan —
   an AST walk over `scripts/sysadmin/quota_dashboard.py` and every `scripts/sysadmin/dashboard_ui/**/*.py`
   finds no `str` constant matching `<[a-zA-Z/!]` (plain literal, f-string part, `%` or `.format` template alike —
   so a `'<span>' + value` concatenation is caught too) outside `dashboard_ui/components.py`; the
   catalogue scan — every view rendered from fixture data under `strings.use(<stand-in>)` contains no
   catalogue-owned English string, and an AST scan finds no user-visible string literal in the view modules
   outside `strings.t` calls; the INV-2 inventory — a fixed list taken from today's five tabs asserts each renders
   in some view: Repos — the picker, the owner chips with counts, the tag filter, the skipped-store list, the item-row
   fields and the Accept / Reject / Comment controls; the agents block — the summary counts line, the repo error
   banner, the quiet-repos line, per agent state, NOW, Holds, NEXT with its queued counts, last merge, merge owner,
   named-from, windows, paused (by, at, why, partial), pause-not-honoured, the dormant count, and Pause / Resume;
   Quota — the four banners (probe failed, rotation paused, pause unreadable, no accounts), the account-row fields and
   the four controls, the returning and pending rows, the governor verdict, the Warnings list, the rotation note with
   its threshold and probe interval; Usage — the spend data with `built_at` and the window; Commands — the nine
   catalogue columns, the intro with its source count, the corpus-unreadable banner, the matrix with its intro,
   caveat and totals, the box-budget line; External — the pool credits, the search-API quotas, the external-services
   intro and page.
2. Flip `GET /` and `/index.html` (`scripts/sysadmin/quota_dashboard.py:3943`) to `components.shell`; make
   `/repos.html` a `303` to `/#work` while today is on or before `_LEGACY_TOKEN_UNTIL`, and `404` after it; set
   `_LEGACY_TOKEN_UNTIL` to this ticket's coding date plus 14 days — one date for the redirect and the token
   window, as spec § Lifecycle and § Which actions confirm tie them to the same merge.
3. Re-point the rebuild-on-miss in `pause_agent` and `item_verdict` (:2662-2665, :2733-2736) from
   `_repos_page(fresh=True)` to the view dispatcher (`overview` for pause targets, `work` for item targets), and add
   the restart cases to `tests/test_quota_dashboard.py`: with both registries emptied and no view rendered, a verdict
   POST and a pause POST for a target the real Overview and Work views show are found.
4. Delete the old page layer — the 30 top-level HTML-emitting functions an all-literal AST scan lists at 18d619f1e
   (31 counting `_row`'s nested `cell`): `_agent_row`, `_agents_block`, `_api_quotas_panel`, `_bar`, `_budget_banner`,
   the HTML half of `_budget_probe`, `_commands_table`, `_ext_matrix_intro`, `_ext_matrix_table`, `_ext_services_intro`,
   `_fmt_renewal`, `_governor_panel`, `_item_line`, `_natives_cell`, `_pause_cell`, `_pending_row`,
   `_pool_credits_panel`, `_repo_pane`, `_repos_body`, `_repos_page` (with its cache, :2255-2256), `_return_row`, `_row`,
   `_safe_pane`, the HTML half of `_spend_panel`, `_switch_cell`, `_tiers_cell`, `_unclassified_warning`,
   `_verdict_cell`, `_with_stale_banner`, `render` — plus the constants only they read (`_REPOS_STYLE`,
   `_REPOS_PICK_JS`, `_OWNER_FILTER_JS`, `REPOS_REFRESH_S`) and anything else step 1's scan still flags. Then:
   `generate()` keeps its probe, `quota.json` and `_LAST_STATUS` duty and stops writing `index.html`; `/quota.json`
   serves `_JSON` and, when the payload is older than MAX_AGE_S, starts `_regen_async()` as `_fresh_html` does today
   (:3947-3951) — `_fresh_html` itself goes; `main --once` (:4077-4093) becomes "probe once, write `quota.json`, print
   its path, exit" and its `--help` text says so.
5. Rewrite the HTML-substring tests in `tests/test_quota_dashboard.py` (about 116 of 169; builders `generate`
   36, `_repos_page` 32, `render` 22, `_api_quotas_panel` 13, `_fresh_html` 10) and the 10 / 9 / 1 tests in the
   three sibling files against the new views' landmarks (`aria-labelledby` ids, `data-*` hooks, the catalogue
   keys) — every behaviour each old test pinned keeps a test; a test whose behaviour the redesign retired (an
   iframe, a tab) is deleted with its reason in the commit body. The 20 POST and 25 collector tests stay as they
   are apart from the verdict tests sending a token.
6. Write `tests/test_quota_dashboard_browser.py` with `pytest.importorskip("playwright.sync_api")` and
   `sync_playwright` (pytest-playwright is not installed; playwright 1.61.0 and chromium-1228 are in the hub
   `.venv`), the server in-process on port 0 over fixture stores, at 1440 and 390 px: the summary strip and then
   *Needs you* inside the first screen; the strip's counts equal the fixtures'; from the skip link, Tab reaches
   the first action of the first card in the first expanded group; the primary loop — open, read, Accept,
   confirm — completes by keyboard alone in four steps; the dialog traps focus and returns it; no horizontal page
   scroll at 390 px and at 200 % zoom; the theme toggle survives a reload with no flash (the `data-theme`
   attribute set before first paint); a half-typed comment survives a refresh tick; a 409 announces the changed
   item. Gate the module `@pytest.mark.needs_browser` only if a launch fails on this box — it launches in 0.8 s.
7. Rewrite `docs/workstation/quota-dashboard.md` for the six views, the routes, the guard, the token, the
   redirect window and its date, the package layout and the render-time baseline from T01's commit body.
8. Run every Gate line to green.
9. `python scripts/enforcement/check_doc_sync.py --range <plan base>..HEAD` and
   `python scripts/enforcement/check_doc_stubs.py --range <plan base>..HEAD`; `/fabrik-docs-review` on the docs the
   plan changed; `/fabrik-features` for the console's FEATURES row.
10. `/fabrik-review` on the whole-plan diff to its coverage-adjudicated exit (the plan's heavy round), the
    receipt written to the Touches path with the verbatim `final_gate.py --check --json` `"status":"success"`.
11. Commit the Touches; the orchestrator applies CHANGELOG, INDEX (the new package, tests and receipt) and
    FEATURES through Deltas, and files the work item that removes the redirect and the token's legacy branch on
    the `_LEGACY_TOKEN_UNTIL` date.

## Behavior Contract
- **Given** the redesigned module, **When** the page-layer scan runs, **Then** no string holding an HTML tag is built outside the components and no user-visible literal sits outside the catalogue (spec § Invariants INV-4)
- **Given** today's five tabs' controls and data fields, **When** the inventory test renders every view, **Then** each one appears in some view (spec § Invariants INV-2)
- **Given** the operator opens the board's URL, **When** GET / is served, **Then** it is the app shell with the Overview as the default view (spec § Contract deltas)
- **Given** a bookmark to /repos.html, **When** it is opened within the 14-day window it redirects to /#work, **Then** after the window it returns 404 (spec § Lifecycle)
- **Given** a restarted server, **When** a pause or verdict POST arrives for a target the views show, **Then** the rebuild-on-miss finds it through the new builders (spec § Invariants INV-1; scripts/sysadmin/quota_dashboard.py:2733)
- **Given** a 1440 px and a 390 px browser, **When** the Overview loads, **Then** the summary strip and Needs you sit in the first screen, the page never scrolls sideways, and the primary loop completes by keyboard in four steps (spec § Validation; spec § Personas)
- **Given** a half-typed comment and an open dialog, **When** a refresh tick fires, **Then** the text survives, the dialog stays and focus returns to the invoker on close (spec § Invariants INV-5)
- **Given** a chosen theme, **When** the page reloads, **Then** the theme holds with no flash of the other theme (spec § Theme, motion, keyboard)

## Context Files
- .windsurf/rules/saas/60-saas-ui.md
- .windsurf/rules/core/design-system-template.md
- .windsurf/rules/core/45-testing-strategy.md
- .windsurf/rules/core/40-documentation.md
- docs/superpowers/specs/2026-10-16-command-centre-dashboard-design.md
- docs/development/reviews/2026-10-17-command-centre-dashboard-spec-review.md
