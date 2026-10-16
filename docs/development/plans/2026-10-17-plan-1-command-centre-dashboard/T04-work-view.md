# T04 — The Work view: per-repo queues with the verdict controls and the tag filter
Appetite: 200

## Scope
Implements the Work row of spec § Information architecture: today's Repos tab content — the repo picker with fabrik
first (D-738), the owner chips (D-745), the per-owner item tables with the verdict controls under today's rule
(D-917): Accept and Reject on every open item except an awaiting non-decision, Comment on every item (`_verdict_cell`
`scripts/sysadmin/quota_dashboard.py:2361`, `scripts/work.py:3813`), the tag filter and the skipped-store list. The
agents table on today's Repos tab moves to the Overview (T03), so this view has none. The confirm rules (spec § Which
actions confirm): Accept opens a dialog showing the full question with an optional note sent as the verdict's text;
Reject opens a dialog whose reason is required; Comment is an inline field with no dialog. Every region has its
loading, empty and error state, errors in words (spec § Components); the view carries a freshness stamp at its 20 s
cadence. DO-NOT: edit `scripts/sysadmin/quota_dashboard.py` (T07 removes `_repos_page`), write JavaScript (T01's
attributes — `data-pick-group`, `data-filter-group`, the action attributes — carry every behaviour), or render agents.

Depends: T02
Parallel: ⚡
Complexity: native
Gate: .venv/bin/python -m pytest tests/test_quota_dashboard_work.py -q
Docs: none (T07 owns `docs/workstation/quota-dashboard.md`)

## Touches
- scripts/sysadmin/dashboard_ui/views/work.py — PRIMARY PATH
- tests/test_quota_dashboard_work.py — NEW

## Consumes
- T01 `components.*` (`table`, `button`, `field`, `dialog`, `freshness`, `fragment`, `region_state`), `strings.t`, the
  attributes; T02 `ViewContext`, `ViewResult`, `snapshot.token`, `dashboard_ui.fmt` (`repo_order` — fabrik first, then
  by remaining count, then name, :2330), and `_view_data("work")` → `{"now", "refresh_s", "work": [{name, items[],
  error, skipped[], main, root}], "hub_agents", "owner_order", "repos_ttl_s"}` (`_collect_work`,
  `scripts/sysadmin/quota_dashboard.py:2285`), plus `"next_cap"` / `"next_tip_cap"` for the item rows' Next cell (its
  text capped with `fmt.cap(next, next_cap)`, the whole of it to `next_tip_cap` in the title, as :2445 does today).
- Today's page as the inventory of what must survive: `_repos_page` (`scripts/sysadmin/quota_dashboard.py:3014`) and the
  per-repo pane `_repo_pane` (`scripts/sysadmin/quota_dashboard.py:2369`) — the owner chips with every hub agent and the
  empty owner shown even at 0 (:2246, :2404-2414), the item rows with their `data-tags` (:2439) that the tag filter
  reads, the item line `_item_line` and the safe pane `_safe_pane` — the coder reads those functions (between :2246 and
  :3046) and carries every column, chip and filter over.

## Produces
- `work.render(data, ctx)` → the fragment and `item_targets` — every item shown, in the shape `_publish_item_targets`
  (`scripts/sysadmin/quota_dashboard.py:2714`) takes, so a verdict posted from this view finds its target.
- The picker: one pane per repo inside a `data-pick-group="repo"`, each `data-pick="<repo>"`, so `/#work/<repo>`
  selects the pane client-side and a reload keeps it (spec § Information architecture, Navigation).

## Steps
1. Write `tests/test_quota_dashboard_work.py` FIRST and watch it fail: fabrik is first in the picker and every pane
   carries its `data-pick`; each owner gets a chip with its count (`data-filter="owner:<name>"`), every hub agent and the
   empty owner included at 0, each owner's section carrying `data-f-owner`; every item row carries `data-f-tag` with its
   tags, and the tag box is a `field(kind="search", data={"filter": "tag", "filter-mode": "token"})` so a typed tag
   matches whole tokens as today's does (:2917) and its Next cell capped at `next_cap` with the longer text in its title; an open non-awaiting item has Accept, Reject and Comment, an awaiting decision the same,
   an awaiting non-decision Comment only (D-917); every verdict body carries the item's `snapshot.token`; Accept's
   dialog takes an optional note, Reject's requires one, Comment is an inline field with `data-text-from`; a repo whose
   collector returned `error` shows the error in words and the other repos render; skipped stores are listed; the view carries a freshness stamp at 20 s; the returned
   `item_targets` contain every item shown.
2. Write `work.py` to green.
3. Run the Gate to green, then `.venv/bin/ruff check` on the Touches.
4. `python scripts/enforcement/check_doc_sync.py`.
5. `/fabrik-review` on the ticket's changed surface to its coverage-adjudicated exit.
6. Commit the Touches.

## Behavior Contract
- **Given** several repos, **When** the Work view renders, **Then** fabrik is first in the picker and each repo's pane is addressable as /#work/<repo> so a reload keeps it (spec § Information architecture; D-738)
- **Given** an open item, an awaiting decision and an awaiting non-decision, **When** their rows render, **Then** the first two offer Accept, Reject and Comment and the third Comment only (spec § Information architecture; scripts/sysadmin/quota_dashboard.py:2361)
- **Given** a verdict button in the Work view, **When** it renders, **Then** its body carries the item's snapshot token, Accept's dialog takes an optional note and Reject's requires a reason (spec § Which actions confirm)
- **Given** owners, tags and skipped stores, **When** the Work view renders, **Then** every hub agent and the empty owner have a chip with a count, rows carry their tags for the filter and their capped Next text, and the skipped stores are listed (spec § Information architecture; scripts/sysadmin/quota_dashboard.py:2404)
- **Given** a repo whose collector failed, **When** the Work view renders, **Then** that repo shows its error in words, the other repos render, and the view shows its read time (spec § Lifecycle; scripts/sysadmin/quota_dashboard.py:2285)
- **Given** the rendered Work view, **When** a verdict POST arrives for any item it shows, **Then** the item is found on the board (spec § Invariants INV-1; scripts/sysadmin/quota_dashboard.py:2714)

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
