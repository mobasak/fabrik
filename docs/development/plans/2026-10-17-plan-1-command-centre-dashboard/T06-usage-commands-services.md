# T06 — The Usage, Commands and Services views
Appetite: 240

## Scope
Implements the Usage, Commands and Services rows of spec § Information architecture and their Freshness
stamps (§ Components): Usage is today's spend panel unchanged in content (`_spend_panel`
`scripts/sysadmin/quota_dashboard.py:1021`); Commands is today's command catalogue (`_commands_table` :2140) as
a searchable list with per-command detail in a disclosure, and the service matrix (`_ext_matrix_table` :2205,
D-172) as its own sub-view behind the APG Tabs pattern; Services is the pool credits shown ONCE
(`_pool_credits_panel` :564), the search-API quotas moved from Commands (`_api_quotas_panel` :487, D-176), the
external-services intro (`_ext_services_intro`, :3264) and a link that opens `/external-services.html` in its
own tab (`target="_blank" rel="noopener"`), no iframe. The box-budget banner (`_budget_banner` :2116) is NOT
here: it is the Overview's Health strip (T03). DO-NOT: edit `scripts/sysadmin/quota_dashboard.py` (T02 split
the data halves, T07 removes the old builders), fetch from the network at render (`fetch=False`, INV-1), or
write JavaScript beyond declaring T01's attributes.

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
- T01 `components.*`, `strings.t`; T02 `ViewContext`, `ViewResult` and `_view_data`: usage → `{"spend":
  _spend_data()}` (the sidecar's `per_model_spend.{tiers, daily, spend_usd, base_rate_per_mtok}`); commands →
  `{"commands": _load_commands(), "matrix": …}` (`_load_commands` :1574 — keys `name, next, services, natives,
  rule, tiers, rendered, purpose, when, skip, stage`); services → `{"pool": _pool_credits(fetch=False), "apis":
  _api_quotas(fetch=False)}` (:176 TTL 300 s, :414 TTL 1,800 s).
- Today's builders as the inventory of what must survive: the coder reads `_spend_panel`, `_commands_table`,
  `_ext_matrix_table`, `_pool_credits_panel`, `_api_quotas_panel` and `_ext_services_intro` in
  `scripts/sysadmin/quota_dashboard.py` and carries every column and datum over.

## Produces
- `usage.render`, `commands.render`, `services.render` (T02's protocol), each with a `freshness` stamp at its
  data's own cadence — pool 300 s, search APIs 1,800 s, the spend sidecar daily — and Commands with none
  (`cadence_s=None`: it reads its sources live and never goes stale).

## Steps
1. Write `tests/test_quota_dashboard_views_misc.py` FIRST from fixture data and watch it fail: every column of
   today's command catalogue appears in Commands (`name, next, services, natives, rule, tiers, purpose, when,
   skip, stage`), the search box has a label and filters the list by name and purpose, each command's detail is
   a disclosure; the matrix is a separate tab panel with `role="tablist"`/`tab`/`tabpanel` and
   `aria-selected`; pool credits appear once and only in Services; the search-API quotas appear in Services and
   not in Commands; the external-services link opens in its own tab and no `<iframe>` exists in any of the three;
   every datum `_spend_panel` shows appears in Usage; each view's freshness stamp carries its cadence and
   Commands carries none; a data key holding `{"error": …}` renders that region's error state in words.
2. Write the three modules to green.
3. Run the Gate to green, then `ruff check` on the Touches.
4. `python scripts/enforcement/check_doc_sync.py`.
5. `/fabrik-review` on the ticket's changed surface to its coverage-adjudicated exit.
6. Commit the Touches.

## Behavior Contract
- **Given** the command catalogue, **When** the Commands view renders, **Then** every column of today's table appears, the labelled search filters by name and purpose, and each command's detail opens in a disclosure (spec § Information architecture; scripts/sysadmin/quota_dashboard.py:2140)
- **Given** the service matrix, **When** the operator picks its tab, **Then** it shows as its own tab panel following the APG Tabs pattern (spec § Information architecture; scripts/sysadmin/quota_dashboard.py:2205)
- **Given** pool credits and search-API quotas, **When** the views render, **Then** both appear in Services, the pool credits exactly once, and neither appears in Commands (spec § Information architecture; D-176)
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
with `scripts/sysadmin/quota_dashboard.py` it is 263,449 B, over the 262,144 B read budget. Every spec rule
this ticket needs is stated in its Scope, Steps and Behavior Contract; T01's components already carry the
§ Components and § Theme rules.
