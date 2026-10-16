# T03 — The Overview view: summary strip, decisions waiting, blocked merges, agents, quota, health
Appetite: 300

## Scope
Implements spec § Overview — the "Needs you" section first (items 0–5), the Overview row of § Information
architecture, the Accept / Reject / Comment / Pause / Resume rows of § Which actions confirm, and the
review's routed rows P3-3 (a blocked-merge card whose repo has no resolvable merge owner) and P5-r1 (the
reorder rule when only Health is faulted). Settled here for P5-r1: the spec's sentence is applied as written —
when the band is RED or WALL, OR any probe has failed, BOTH the Quota and the Health strips move above the
decisions; with neither, they stay below Agents. DO-NOT: edit `scripts/sysadmin/quota_dashboard.py` (T02 gave
this view its data; T07 removes the old agents block), merge or retry anything (blocked merges are read-only),
or write to any store except through the existing POST endpoints.

Depends: T02
Parallel: ⚡
Complexity: native
Gate: .venv/bin/python -m pytest tests/test_quota_dashboard_overview.py -q
Docs: none (T07 owns `docs/workstation/quota-dashboard.md`)

## Touches
- scripts/sysadmin/dashboard_ui/views/overview.py — PRIMARY PATH
- scripts/sysadmin/dashboard_ui/merges.py — the fleet-wide blocked-merge reader
- tests/test_quota_dashboard_overview.py — NEW

## Consumes
- T01: `components.*`, `strings.t`; T02: `ViewContext`, `ViewResult`, `snapshot.token`, and `_view_data("overview")`'s
  keys `work`, `box`, `status`, `budget`, `health` (T02 § Produces).
- The data shapes, read from the collectors (never re-derived):
  - `work`: `[{name, items[], error, skipped[], main}]` from `_collect_work` (`scripts/sysadmin/quota_dashboard.py:2285`);
    an awaiting item carries `status: "awaiting-operator"`, `kind`, `ground` (gate · owned · underivable, or
    absent), `question`, `created` (ISO), `creator` (the asking agent), optional `comments[]` and `alt_ids[]` (43 items, all `kind:
    decision`, on 2026-10-17).
  - `box`: `collect_box` (`scripts/agent_status.py:417`) — per repo `{name, main, agents[], dormant, error?}`; per
    agent `{name, state ∈ working|idle|stale|away (scripts/agent_status.py:340-347), now{command, phase, phases,
    title, stale}|null, claim, next{queued, top[]}, merges[{sha, ts, item, subject}], paused{names, by, at,
    why}|null, can_pause}`; `dormant` is a count (`scripts/agent_status.py:373`).
  - `status`: the `claude_rotate.py --status --json` payload — band at `posture.active.band` (and `band_fable`),
    fleet windows at `posture.fleet.windows.<window>.{utilization, slug, wall}`, `hold`, `successor`,
    `picture.next_relief` (`scripts/sysadmin/claude_rotate.py:5818-5834`).

## Produces
- `merges.blocked(opt_root: Path, fabrik_root: Path) -> list[dict]` — for every `/opt/<repo>/.git/fabrik-merge/*.json`
  (the git common dir, so a worktree's records are its main checkout's), groups records by `branch`, takes the
  record with the greatest `id` (ULID), and returns it when its `outcome` is `refused` or its `phase` is
  `catchup-refused`: `{repo, branch, item, requester, id, age_s (from the ULID's 48-bit time), reason, owner,
  owner_error}`. `owner` comes from `python3 <fabrik_root>/scripts/decisions.py --merge-owner <repo>` (one call
  per repo that has a blocked branch, timeout 10 s): exit 0 → its stdout; exit 3 (`UNDECLARED`) or any other exit
  → `owner: None` with the resolver's message in `owner_error` (P3-3). An unreadable or non-JSON record is
  skipped and counted in the Health strip, never raised.
- `overview.collect(ctx)` returns `{"blocked": merges.blocked(…)}`; `overview.render(data, ctx)` returns the
  fragment plus `pause_targets` (the repos list exactly as `_publish_pause_targets` takes it, :2647) — T02's
  dispatcher publishes them.

## Steps
1. Write `tests/test_quota_dashboard_overview.py` FIRST with fixture records in two temporary repos and watch
   it fail: a branch refused then merged is not blocked; a branch whose newest record is refused is; one whose
   newest is `catchup-refused` is; one still in flight (neither outcome nor that phase) is not; a repo whose
   `decisions.py --merge-owner` exits 3 shows "owner unresolved" with the message (P3-3). Decision ordering:
   the hub's group first, then repos by their oldest item; inside a group `gate` first, then oldest `created`,
   an item with no ground after the grounded ones; the first non-empty group expanded (the hub's when it has
   any) and every other collapsed to its count; a non-decision awaiting item shows Comment only, a decision
   shows Accept, Reject and Comment, and every card carries the `snapshot.token` of its item as `data-token`.
   The empty state reads the catalogue's "Nothing waiting on you" line with the last read time. The summary
   strip's counts equal the fixture's (decisions per repo with the oldest age, blocked merges, agents not
   working, band and active account, health faults), each a link to its section. The reorder: band RED, band
   WALL and a failed probe each put Quota and Health above Decisions; GREEN with no fault keeps them below.
   Agents: one row per agent whatever its state, the dormant count line per repo, Pause on a working agent
   with `can_pause`, Resume on a paused one naming every marker and the first marker's setter.
2. Write `merges.py`, then `overview.py`, to green — every string through `strings.t`, every value through the
   components.
3. Declare each action on its button with T01's action attributes (no JavaScript in this ticket — `app.js`
   is T01's): Accept → dialog with the full
   question and an optional note sent as `text`; Reject → dialog that requires a reason; Comment → no dialog;
   Pause → dialog stating the agent stops starting new work at its next turn boundary
   (`scripts/sysadmin/quota_dashboard.py:2958`); Resume → dialog naming the markers it lifts. Each verdict POST
   sends `token`; a 409 re-fetches the view and announces "this item changed — read it again" in the live region.
4. Run the Gate to green, then `ruff check` on the Touches.
5. `python scripts/enforcement/check_doc_sync.py`.
6. `/fabrik-review` on the ticket's changed surface to its coverage-adjudicated exit.
7. Commit the Touches.

## Behavior Contract
- **Given** merge records in two repos, **When** the blocked-merge reader runs, **Then** a branch is blocked only when its newest record by ULID is refused or catchup-refused, never when a later record merged or is still in flight (spec § Overview item 2; scripts/merge_request.py:1927)
- **Given** a blocked branch in a repo whose merge owner cannot be resolved, **When** its card renders, **Then** it says the owner is unresolved and shows the resolver's message (receipt row P3-3; scripts/decisions.py:651)
- **Given** awaiting items across several repos, **When** the Overview renders, **Then** the hub's group comes first, repos follow by their oldest item, gate items lead each group, an ungrounded item sorts after the grounded ones, and only the first non-empty group is expanded (spec § Overview item 1)
- **Given** an awaiting decision and an awaiting non-decision, **When** their cards render, **Then** the decision offers Accept, Reject and Comment and the non-decision offers Comment only, each card carrying its snapshot token (spec § Overview item 1; scripts/work.py:3813)
- **Given** no awaiting item anywhere, **When** the Overview renders, **Then** it shows the nothing-waiting line with the time of the last read, never an empty area (spec § Overview item 1; .windsurf/rules/core/design-system-template.md:605)
- **Given** the stores and the status payload, **When** the summary strip renders, **Then** its counts match the stores and each links to its section (spec § Overview item 0)
- **Given** the band is RED or WALL or a probe has failed, **When** the Overview renders, **Then** the Quota and Health strips appear above the decisions, and otherwise below the agents (spec § Overview item 0; receipt row P5-r1)
- **Given** agents in every state and a paused agent, **When** the Agents section renders, **Then** every agent the collector lists has a row with its state badge, the dormant count shows per repo, and Resume names every marker it lifts (spec § Overview item 3; scripts/agent_status.py:385)

## Context Files
- .windsurf/rules/saas/60-saas-ui.md
- .windsurf/rules/core/design-system-template.md
- .windsurf/rules/core/10-python.md
- .windsurf/rules/core/45-testing-strategy.md
- scripts/agent_status.py
- scripts/decisions.py
- docs/superpowers/specs/2026-10-16-command-centre-dashboard-design.md
