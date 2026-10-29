# T03 — The Overview view: summary strip, decisions waiting, blocked merges, agents, quota, health
Appetite: 360

## Scope
Implements spec § Overview — the "Needs you" section first (items 0–5), the Overview row of § Information
architecture, the Accept / Reject / Comment / Pause / Resume rows of § Which actions confirm, the Growth trigger of
§ Lifecycle (more than 100 decisions → each group shows its five oldest and a link to that repo's Work view), and the
review's routed rows P3-3 (a blocked-merge card whose repo has no resolvable merge owner) and P5-r1 (the reorder
rule when only Health is faulted). Settled here for P5-r1: the spec's sentence is applied as written — when the band
is RED or WALL, OR any probe has failed, BOTH the Quota and the Health strips move above the decisions; with neither,
they stay below Agents. DO-NOT: edit `scripts/sysadmin/quota_dashboard.py` (T02 gave this view its data; T07 removes
the old agents block), write JavaScript (T01's attributes carry every behaviour), merge or retry anything (blocked
merges are read-only), or write to any store except through the existing POST endpoints.

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
- T01: `components.*` (`card`, `badge`, `clamp`, `dialog`, `field`, `freshness`, `fragment`, `region_state`),
  `strings.t`, the action attributes; T02: `ViewContext`, `ViewResult`, `snapshot.token`, `dashboard_ui.fmt`, and
  `_view_data("overview")`'s keys `now`, `refresh_s`, `probe_interval_s`, `work`, `box`, `status`, `budget`, `health`,
  `ag_states`, `hub_agents` (T02 § Produces).
- The data shapes, read from the collectors (never re-derived):
  - `work`: `[{name, items[], error, skipped[], main, root}]` (`_collect_work`, `scripts/sysadmin/quota_dashboard.py:2285`);
    an awaiting item carries `status: "awaiting-operator"`, `kind`, `ground` (gate · owned · underivable, or absent),
    `question`, `created` (ISO), `creator` (the asking agent), optional `comments[]` and `alt_ids[]` (43 items, all
    `kind: decision`, on 2026-10-17).
  - `box`: `collect_box` (`scripts/agent_status.py:417`) — `{repos: [...]}`, per repo `{name, main, store, agents[],
    dormant (a count, :373), error?}`; per agent `{name, window, windows, named_from, state ∈ working|idle|stale|away
    (:340-347), now{command, phase, phases, title, surface, updated_ts, stale}|null, claim, next{queued, top[{id,
    priority, title}]}, merges[{sha, ts, item, subject}], merge_owner, paused{name, names, partial, by, at, why}|null,
    can_pause, pause_honoured}`. Today's agents block shows, and this view keeps (`scripts/sysadmin/quota_dashboard.py:2561-2640`,
    :2745-2800): the summary counts line (N working / idle / stale / away), the repo-level `error` banner, "N repos with
    no recent agent" (`quiet`, :2756), per agent the state badge, NOW (command · phase/phases · title, or the stale
    note), Holds (`claim`), NEXT (the top items and "+N more queued" or "nothing queued"), last merge, "merge owner
    (merges others)" when `merge_owner`, "named from its last run" when `named_from == "record"`, "N windows" when
    `windows > 1`, the paused marker with `by`, `at` and `why` (and "partial" when `paused.partial`), and "not
    honoured here until this repo's work.py syncs" when `pause_honoured` is false.
  - `status`: the `claude_rotate.py --status --json` payload (`scripts/sysadmin/claude_rotate.py:5818-5834`, top-level
    keys `accounts, active, pending, pause, fleet_warnings, picture, posture`) — the band at `posture.active.band` (and
    `band_fable`), the fleet windows at `posture.fleet.windows.<five_hour|seven_day|fable>.{utilization, slug}`, the
    successor at `posture.fleet.successor`, `posture.fleet.next_relief` and the hold at `posture.fleet.hold`
    (:5649-5660); each window's reset time from the active account's row in `accounts` (`five_hour.resets_at_epoch`,
    `seven_day.resets_at_epoch`, `model_windows.Fable.resets_at_epoch`, as `_row` reads them,
    `scripts/sysadmin/quota_dashboard.py:774-861`), formatted with `fmt.fmt_reset`; `probe_failed` when T02's fallback set it.
  - `budget`: the box-budget data with its `caveats` as plain strings (`{"disabled": True}` renders nothing); `health`: `{stale: [...], failed: [...]}`.

## Produces
- `merges.blocked(opt_root: Path, fabrik_root: Path) -> list[dict]` — for every `<opt_root>/<repo>/.git/fabrik-merge/*.json`
  (the git common dir, so a worktree's records are its main checkout's), groups records by `branch`, takes the record
  with the greatest `id` (ULID), and returns it when its `outcome` is `refused` or its `phase` is `catchup-refused`:
  `{repo, branch, item, requester, id, age_s (from the ULID's 48-bit millisecond time), reason, owner, owner_error}`.
  `owner` comes from `python3 <fabrik_root>/scripts/decisions.py --merge-owner <opt_root>/<repo>` (a REPO_DIR path; one
  call per repo with a blocked branch, timeout 10 s, the answer cached per repo for the view's 20 s cadence): exit 0 →
  stdout is the owner; exit 3 → `owner: None`, `owner_error` = its stdout (`UNDECLARED`, `scripts/decisions.py:676-678`); any other exit or a
  timeout → `owner: None`, `owner_error` = its stderr or "timed out" (P3-3). An unreadable or non-JSON record is skipped
  and counted in the Health strip, never raised. Run on 2026-10-17 over the live records: 763 records, 30 branches, 1
  blocked (this worktree's own, parked behind W-5a1b8961) — the spine's Evidence.
- `overview.collect(ctx)` returns `{"blocked": merges.blocked(…)}`; `overview.render(data, ctx)` returns the fragment,
  `pause_targets` (the repos list exactly as `_publish_pause_targets` takes it, :2647) AND `item_targets` for every
  awaiting item it shows (the work entries as `_publish_item_targets` takes them, :2714) — so an Accept on an Overview
  card after a server restart finds its target.

## Steps
1. Write `tests/test_quota_dashboard_overview.py` FIRST with fixture records in two temporary repos and watch it fail:
   - Blocked merges: refused-then-merged is not blocked; newest refused is; newest `catchup-refused` is; in flight
     (neither) is not; exit 3 shows "owner unresolved" with `UNDECLARED`, exit 1 with the stderr line (P3-3).
   - Decisions: the hub's group first, then repos by their oldest item; inside a group `gate` first, then oldest
     `created`, an ungrounded item after the grounded ones; the first non-empty group expanded (the hub's when it has
     any), every other collapsed to its count; with more than 100 decisions each group shows its five oldest and a link
     to `/#work/<repo>`.
   - Cards: ground label, the question in `clamp` (three lines, "show all"), `creator`, the wait time from `created`; a
     decision shows Accept (dialog with the full question and an optional note), Reject (dialog, note required) and
     Comment (an inline `field` with `data-text-from`, no dialog); an awaiting non-decision shows Comment only; every
     verdict body carries the item's `snapshot.token` as `token`.
   - Empty and summary: no awaiting item → the catalogue's "Nothing waiting on you" line with the time of the last
     read; the summary strip's counts equal the fixture's (decisions per repo with the oldest age, blocked merges,
     agents not working, band and active account, health faults), each a link to its section; every section carries a
     `freshness` stamp at the 20 s cadence.
   - Reorder: band RED, band WALL and a failed probe each put Quota and Health above Decisions; GREEN with no fault
     keeps them below.
   - Agents: one row per agent whatever its state with every field of § Consumes; the dormant count line per repo;
     Pause (dialog stating the agent stops starting new work at its next turn boundary,
     `scripts/sysadmin/quota_dashboard.py:2958`, reason optional) on an agent with `can_pause`; Resume (dialog naming
     every marker in `paused.names` and the setter `paused.by`).
   - Quota and Health: the band with its window, the active account and successor, the three windows with their reset
     times, the hold tier when set, "probe failed" when `probe_failed` is set; Health lists each stale view, each failed
     probe or collector, unreadable merge records, and the box-budget line.
   - Targets: `render` returns `item_targets` for every awaiting item shown and `pause_targets` for every agent repo.
2. Write `merges.py`, then `overview.py`, to green — every string through `strings.t`, every value through the
   components.
3. Run the Gate to green, then `.venv/bin/ruff check` on the Touches.
4. `python scripts/enforcement/check_doc_sync.py`.
5. `/fabrik-review` on the ticket's changed surface to its coverage-adjudicated exit.
6. Commit the Touches.

## Behavior Contract
- **Given** merge records in two repos, **When** the blocked-merge reader runs, **Then** a branch is blocked only when its newest record by ULID is refused or catchup-refused, never when a later record merged or is still in flight (spec § Overview item 2; scripts/merge_request.py:1927)
- **Given** a blocked branch in a repo whose merge owner cannot be resolved, **When** its card renders, **Then** it says the owner is unresolved and shows the resolver's own message for that exit (receipt row P3-3; scripts/decisions.py:651)
- **Given** awaiting items across several repos, **When** the Overview renders, **Then** the hub's group comes first, repos follow by their oldest item, gate items lead each group, an ungrounded item sorts after the grounded ones, only the first non-empty group is expanded, and past 100 decisions each group shows its five oldest and a link to its Work view (spec § Overview item 1; spec § Lifecycle)
- **Given** an awaiting decision and an awaiting non-decision, **When** their cards render, **Then** each shows its ground, asker, wait and clamped question, the decision offers Accept, Reject and Comment and the non-decision Comment only, and every verdict carries the item's snapshot token (spec § Overview item 1; scripts/work.py:3813)
- **Given** the stores and the status payload, **When** the summary strip renders, **Then** its counts match the stores and link to their sections, every section shows its read time, and with nothing waiting the nothing-waiting line shows instead of an empty area (spec § Overview item 0; .windsurf/rules/core/design-system-template.md:605)
- **Given** the band is RED or WALL or a probe has failed, **When** the Overview renders, **Then** the Quota and Health strips appear above the decisions, and otherwise below the agents (spec § Overview item 0; receipt row P5-r1)
- **Given** agents in every state, a paused agent and the status payload, **When** the Agents, Quota and Health sections render, **Then** every agent the collector lists has its row and fields, Resume names every marker it lifts, and the quota strip shows the band, account, successor, windows with resets and the hold (spec § Overview items 3-5; scripts/agent_status.py:385)
- **Given** awaiting items and pausable agents, **When** the Overview renders, **Then** it returns item targets for every awaiting item and pause targets for every agent repo it shows, the inputs T02's restart test proves a POST finds (spec § Invariants INV-1; scripts/sysadmin/quota_dashboard.py:2733)

## Context Files
- .windsurf/rules/saas/60-saas-ui.md
- .windsurf/rules/core/design-system-template.md
- .windsurf/rules/core/10-python.md
- .windsurf/rules/core/45-testing-strategy.md
- scripts/agent_status.py
- scripts/decisions.py
- docs/superpowers/specs/2026-10-16-command-centre-dashboard-design.md
