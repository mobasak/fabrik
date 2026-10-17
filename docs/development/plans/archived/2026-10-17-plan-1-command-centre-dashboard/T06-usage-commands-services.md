# T06 — The Usage, Commands and Services views
Appetite: 260

## Scope
Implements the Usage, Commands and Services rows of spec § Information architecture and their Freshness stamps
(§ Components). Usage is today's spend panel unchanged in content (`_spend_panel`
`scripts/sysadmin/quota_dashboard.py:1021`). Commands is today's command catalogue (`_commands_table` :2140) as a
searchable list with per-command detail in a disclosure, keeping today's intro line (the number of sources read live
under `commands/_sources/`) and today's "Command corpus unreadable" banner (:3257-3258); and the service matrix
(`_ext_matrix_table` :2205, D-172) as its own sub-view behind T01's APG `tabs`, with today's matrix intro and its
caveat (`_ext_matrix_intro` :2173 — the denominator and how many rows did NOT come from the rendered corpus, computed
from each row's `rendered`) and its `of N` totals row. Services is the pool credits shown ONCE (`_pool_credits_panel`
:564), the search-API quotas moved from Commands (`_api_quotas_panel` :487, D-176), the external-services intro
(`_ext_services_intro`, defined at :1443) and a link that opens `/external-services.html` in its own tab
(`target="_blank" rel="noopener"`), no iframe. The box-budget banner (`_budget_banner` :2116) is NOT here: it is the
Overview's Health strip (T03). Every region has its loading, empty and error state, errors in words, never a blank
area (spec § Components): an unconfigured or uncached pool (`pool` is `None`) says so in words. DO-NOT: edit
`scripts/sysadmin/quota_dashboard.py` (T02 split the data halves, T07 removes the old builders), fetch from the
network at render (`fetch=False`, INV-1), or write JavaScript (T01's `data-filter-group`, `tabs` and `disclosure`
carry every behaviour).

Depends: T02
Parallel: ⚡
Complexity: native
Gate: .venv/bin/python -m pytest tests/test_quota_dashboard_views_misc.py -q
Docs: none (T07 owns `docs/workstation/quota-dashboard.md`)

## Touches
- scripts/sysadmin/dashboard_ui/views/usage.py
- scripts/sysadmin/dashboard_ui/views/commands.py — PRIMARY PATH
- scripts/sysadmin/dashboard_ui/views/services.py
- tests/test_quota_dashboard_views_misc.py — NEW

## Consumes
- T01 `components.*` (`table`, `tabs`, `disclosure`, `field`, `freshness`, `fragment`, `region_state`), `strings.t`, the
  filter attributes; T02 `ViewContext`, `ViewResult`, `dashboard_ui.fmt` (`stage_tone`, `fmt_age`, `ago`) and `_view_data`:
  - usage → `{"spend": <the sidecar dict: top-level built_at, and per_model_spend.{tiers, daily, spend_usd,
    base_rate_per_mtok, monthly_spend, window_start, window_end, unweighted}> or {"error": …}}`;
  - commands → `{"commands": <_load_commands() rows: name, next, services, natives, rule, tiers, rendered, purpose,
    when, skip, stage> or {"error": …}, "ext_services": <_EXT_SERVICES: the matrix's column keys, labels and titles>}`
    (`_load_commands` :1574);
  - services → `{"pool": <_pool_credits(fetch=False): a dict, or None when unconfigured or uncached>, "apis":
    <_api_quotas(fetch=False)>, "ext_page": {"path", "mtime"}}` (:176 TTL 300 s, :414 TTL 1,800 s).
- Today's builders as the inventory of what must survive: the coder reads `_spend_panel`, `_commands_table`,
  `_natives_cell`, `_tiers_cell`, `_ext_matrix_intro`, `_ext_matrix_table`, `_pool_credits_panel`, `_fmt_renewal`,
  `_api_quotas_panel`, `_unclassified_warning` and `_ext_services_intro` in `scripts/sysadmin/quota_dashboard.py` and
  carries every column, line and datum over.

## Produces
- `usage.render`, `commands.render`, `services.render` (T02's protocol), each with a `freshness` stamp at its data's own
  cadence — pool 300 s, search APIs 1,800 s, the spend sidecar daily (from `built_at`) — and Commands with none
  (`cadence_s=None`: it reads its sources live and never goes stale).

## Steps
1. Write `tests/test_quota_dashboard_views_misc.py` FIRST from fixture data and watch it fail:
   - Commands: every column of today's table appears — the pipeline-order `#`, Command, Stage, Purpose, When to use, Skip when,
     Next, Native subagents, Model tiers (:2140-2170) — and the intro line with the source count; the labelled search
     (`field(kind="search", data={"filter": "find"})` inside a `group(data={"filter-group": "commands"})`) filters rows
     that carry `data-f-find="<name> <purpose>"` by substring; each command's detail is a
     disclosure; an empty `commands` renders the corpus-unreadable banner in words.
   - Matrix: a separate tab panel (`role="tablist"`, `tab`, `tabpanel`, `aria-selected`), its columns from
     `ext_services`, the intro with the not-from-the-rendered-corpus caveat counted from `rendered`, and the `of N` totals.
   - Services: pool credits appear once and only here; `pool=None` renders the catalogue's not-configured line, never an
     empty area; the search-API quotas appear here and not in Commands; the external-services link opens in its own tab
     and no `<iframe>` exists in any of the three views.
   - Usage: every datum `_spend_panel` shows appears, `built_at` and the window included.
   - Freshness: each view's stamp carries its cadence and Commands carries none; a key holding `{"error": …}` renders
     that region's error in words while the rest of the view renders.
2. Write the three modules to green.
3. Run the Gate to green, then `.venv/bin/ruff check` on the Touches.
4. `python scripts/enforcement/check_doc_sync.py`.
5. `/fabrik-review` on the ticket's changed surface to its coverage-adjudicated exit.
6. Commit the Touches.

## Behavior Contract
- **Given** the command catalogue, **When** the Commands view renders, **Then** every column of today's table and its intro appear, the labelled search filters by name and purpose, each command's detail opens in a disclosure, and an unreadable corpus says so in words (spec § Information architecture; scripts/sysadmin/quota_dashboard.py:2140)
- **Given** the service matrix, **When** the operator picks its tab, **Then** it shows as its own tab panel following the APG Tabs pattern, with its intro, caveat and totals (spec § Information architecture; scripts/sysadmin/quota_dashboard.py:2205)
- **Given** pool credits and search-API quotas, **When** the views render, **Then** both appear in Services, the pool credits exactly once, neither in Commands, and an unconfigured pool says so in words (spec § Information architecture; D-176)
- **Given** the Services view, **When** it renders, **Then** the external-services page is a link opening in its own tab and no view holds an iframe (spec § Contract deltas; spec § Invariants INV-3)
- **Given** the spend sidecar, **When** the Usage view renders, **Then** every datum today's spend panel shows appears (spec § Information architecture; scripts/sysadmin/quota_dashboard.py:1021)
- **Given** each of the three views, **When** it renders, **Then** its freshness stamp uses its data's own cadence and Commands never goes stale (spec § Components)
- **Given** a collector that failed, **When** its view renders, **Then** that region shows the error in words and the rest of the view renders (spec § Lifecycle)

## Context Files
- .windsurf/rules/saas/60-saas-ui.md
- .windsurf/rules/core/design-system-template.md
- .windsurf/rules/core/10-python.md
- .windsurf/rules/core/45-testing-strategy.md
- scripts/sysadmin/quota_dashboard.py

The spec (`docs/superpowers/specs/2026-10-16-command-centre-dashboard-design.md`) is NOT a Context File here:
with `scripts/sysadmin/quota_dashboard.py` it is 263,449 B, over the 262,144 B read budget (the rule packs are
budget-exempt; the spec is not). Every spec rule this ticket needs is stated in its Scope, Steps and Behavior
Contract; T01's components already carry the § Components and § Theme rules.
