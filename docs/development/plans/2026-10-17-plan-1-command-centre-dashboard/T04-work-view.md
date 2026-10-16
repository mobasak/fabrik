# T04 — The Work view: per-repo queues with the verdict controls and the tag filter
Appetite: 180

## Scope
Implements the Work row of spec § Information architecture: today's Repos tab content — the repo picker with
fabrik first (D-738), the owner chips (D-745), the per-owner item tables with the verdict controls under
today's rule (D-917): Accept and Reject on every open item except an awaiting non-decision, Comment on every
item (`_verdict_cell` `scripts/sysadmin/quota_dashboard.py:2361`, `scripts/work.py:3813`), and the tag filter.
The agents table that sits on today's Repos tab moves to the Overview (T03), so this view has none.
DO-NOT: edit `scripts/sysadmin/quota_dashboard.py` (T07 removes `_repos_page`), write JavaScript (T01's
action attributes carry every POST), or render agents.

Depends: T02
Parallel: ⚡
Complexity: native
Gate: .venv/bin/python -m pytest tests/test_quota_dashboard_work.py -q
Docs: none (T07 owns `docs/workstation/quota-dashboard.md`)

## Touches
- scripts/sysadmin/dashboard_ui/views/work.py — PRIMARY PATH
- tests/test_quota_dashboard_work.py — NEW

## Consumes
- T01 `components.*`, `strings.t`, the action attributes; T02 `ViewContext`, `ViewResult`, `snapshot.token`,
  `_view_data("work")` → `{"work": [{name, items[], error, skipped[], main}]}` from `_collect_work`
  (`scripts/sysadmin/quota_dashboard.py:2285`).
- Today's page as the inventory of what must survive: `_repos_page` (`scripts/sysadmin/quota_dashboard.py:3014`)
  and the per-repo pane `_repo_pane` (`scripts/sysadmin/quota_dashboard.py:2369`) — the owner chips with every
  hub agent and the empty owner shown even at 0 (:2246, :2404-2414), the item rows with their `data-tags` (:2439)
  that the tag filter reads — the coder reads those functions (between :2246 and :3046) and carries every column,
  chip and filter over.

## Produces
- `work.render(data, ctx)` → the fragment and `item_targets` — the repos list exactly as `_publish_item_targets`
  (`scripts/sysadmin/quota_dashboard.py:2714`) takes it, so a verdict posted from this view finds its target.
- The picker selects a repo through the URL (`/#work/<repo>`), so a reload keeps the repo (spec § Information
  architecture, Navigation).

## Steps
1. Write `tests/test_quota_dashboard_work.py` FIRST and watch it fail: fabrik is first in the picker; each
   owner gets a chip with its count, every hub agent and the empty owner included at 0; an open non-awaiting item has Accept, Reject and Comment, an awaiting
   decision the same, an awaiting non-decision Comment only (D-917); every verdict button's body carries the
   item's `snapshot.token`; Accept's dialog takes an optional note and Reject's requires one; a repo whose
   collector returned `error` shows the error state in words; skipped stores are listed; the tag filter
   narrows the rows by tag; the returned `item_targets` contain every item shown.
2. Write `work.py` to green.
3. Run the Gate to green, then `ruff check` on the Touches.
4. `python scripts/enforcement/check_doc_sync.py`.
5. `/fabrik-review` on the ticket's changed surface to its coverage-adjudicated exit.
6. Commit the Touches.

## Behavior Contract
- **Given** several repos, **When** the Work view renders, **Then** fabrik is first in the picker and the picked repo is kept in the URL across a reload (spec § Information architecture; D-738)
- **Given** an open item, an awaiting decision and an awaiting non-decision, **When** their rows render, **Then** the first two offer Accept, Reject and Comment and the third Comment only (spec § Information architecture; scripts/sysadmin/quota_dashboard.py:2361)
- **Given** a verdict button in the Work view, **When** it renders, **Then** its body carries the item's snapshot token and Reject's dialog requires a reason (spec § Which actions confirm)
- **Given** a repo whose collector failed, **When** the Work view renders, **Then** that repo shows its error in words and the other repos render normally (spec § Lifecycle; scripts/sysadmin/quota_dashboard.py:2285)
- **Given** the rendered Work view, **When** a verdict POST arrives for any item it shows, **Then** the item is found on the board (spec § Invariants INV-1; scripts/sysadmin/quota_dashboard.py:2714)

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
