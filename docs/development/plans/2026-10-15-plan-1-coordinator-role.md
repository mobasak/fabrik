# Plan — the coordinator role: sort, prioritise, merge, keep the records; never build

Status: EXECUTED — approved D-871; Phases A-C merged (0e19427e4), merge ownership handed to the coordinator (D-874)
Profile: small
**Owner:** infra

Spec: `docs/superpowers/specs/2026-10-14-coordinator-role-design.md` (CONVERGED, approved D-868 at ca5223bda;
planned features pinned in `docs/FEATURES.md` at 5104fb0b3). Review receipt with the plan-time inputs this
plan settles: `docs/development/reviews/2026-10-14-coordinator-role-spec-review.md` § Residual (P5-1..P5-7).

Estimated diff ≈170 lines across 5 code files, tests excluded:
- `scripts/work.py` ≈155 (scores, holds, triage, builder `next`/`ready`);
- `scripts/mail.py` ≈6 (beat tuple, docstring, two help strings);
- `.claude/hooks/mail_notify.py` ≈1;
- `scripts/command_run.py` ≈1;
- `scripts/sysadmin/quota_dashboard.py` ≈2.

Data and docs, not code: `.fabrik/work/config.json`, `.fabrik/beat-owners.json`, the charter
`docs/reference/agents/coordinator.md` (new), `templates/governance/CLAUDE.md`, `CLAUDE.md`,
`docs/reference/agents/infra.md`, `docs/reference/multi-agent-operating-model.md`, `docs/reference/work-tracking.md`.

## What this plan is

Three inline phases the orchestrator codes itself in the main checkout; no coder is dispatched:

- **A — the store:** scores and derived priority, holds, the unscored listing and the triage guards, and a
  builder's `next`/`ready` in a coordinator-mode repo (spec § The delta D3 jobs 2–3, D4; § Contract deltas,
  "Work item" and "Assignment").
- **B — the role:** `coordinator` joins every hub beat list; the charter; the fleet carrier in the
  governance template (spec § Contract deltas, "hub beat lists", "identity", "fleet carrier"; D3's **Never** and
  escalation table).
- **C — Finish, then the hub handover:** the mirrors, the config and map flips and the `MERGE OWNER` row are
  prepared; the mail goes out; the whole-plan `/fabrik-review` runs while infra is still merge owner; then, once the
  operator has launched the coordinator, the flip is committed and infra moves into its worktree (spec D1,
  § Contract deltas "merge owner", "mirrors").

Per phase: `/fabrik-review-scoped` on that phase's surface. At Finish (before the handover): one heavy
`/fabrik-review` (the `/fabrik-execute-plan` D7 floor). `scripts/work.py`, `scripts/mail.py`,
`.claude/hooks/mail_notify.py`, `scripts/command_run.py` and `templates/governance/CLAUDE.md` are governance-sync
paths: each phase commits once, after its review, and the commit distributes fleet-wide.

## Intake Inventory

| I# | Item (anchored) | Disposition | Where |
|---|---|---|---|
| I1 | spec § Intake Inventory rows 1–8 (with 5b) | IN | Phases A–C, per the spec rows |
| I2 | *"please do not drift"* (operator, D-863) — the spec's § Recorded, not applied stays out | IN | § Global Constraints, first bullet |
| I3 | P5-1 the four-name list census | IN | Phase B step 1 (the lists that change) and § Decisions taken here (the ones that do not) |
| I4 | P5-2 the hold mechanism | IN | Phase A step 2 (`assign --blocked-by` / `--unblock`) |
| I5 | P5-3 closing the in-flight major releases every held major | IN | Phase A step 3 (the triage guard) |
| I6 | P5-4 a builder claims what the coordinator queued it | IN | Phase A step 4 |
| I7 | P5-5 the unscored listing in the existing `triage`; scored items planned first (the panel changed "skip" to "order" so nothing starves) | IN | Phase A step 3 |
| I8 | P5-6 the finished-plan status value | IN | Phase B step 2 (the charter names `EXECUTED`) |
| I9 | P5-7 `.fabrik/beat-owners.json` and the feedback-owner fallback | IN | Phase C step 2 (the map); § Decisions taken here (the fallback) |
| I10 | spec § Open unknowns — D5's drop-list batch check, "decided at planning" | IN | § Decisions taken here; Phase B step 2 (the charter) |
| I11 | spec § Recorded, not applied (mail noise, `work.py reopen`, the item-to-cost join) | OUT-OF-SCOPE | spec § Recorded, not applied — each its own decision later |

## What we already agreed (citations, not restatement)

- Goal and personas: `spec § Goal`, `spec § Personas`; why: `spec § Why this exists`.
- What exists: `spec § What exists today (grounded)`.
- Where the role runs, model, the seven jobs, **Never**, escalation: `spec § The delta` D1–D3.
- Priority: `spec § The delta` D4; the first re-score: D5.
- Contract deltas and their mirrors: `spec § Contract deltas`.
- Decisions: `spec § Decisions taken`; approval: D-868 (design approved for writing: D-863).
- Rejected: `spec § Rejected alternatives`.

## Decisions taken here (plan-time, reversible — D-869)

- **Hold = `blocked_by`, written by `assign --blocked-by <id>` / `--unblock <id>`** (P5-2). The spec names
  `blocked_by`, and `_is_ready` (`scripts/work.py::_is_ready`) already keeps a blocked item out of `ready`; a
  `hold` tag would be a second mechanism for the same state.
- **One major in flight is enforced in `triage`, not only by holds** (P5-3): `triage` never plans a
  high/high item while another high/high item is in flight (owned or claimed, status `open` or `blocked`), and plans at most one high/high item per run. Closing the in-flight major can therefore never make
  `triage` hand two majors out at once, whatever the holds say. A manual `assign --owner` is the distributor's own
  act and is not guarded.
- **Every new store behaviour is opt-in per repo (plan approval, both panel seats).** `work.py` is fleet-synced
  (`scripts/fabrik_synced_manifest.py`, the `governance-sync` filter), so Phase A's commit reaches every repo. The
  builder filter, the doorbell change and the triage ordering below act only in a store whose
  `.fabrik/work/config.json` carries `"coordinator_mode": true`; the scoring and hold flags and the unscored listing
  are additive and act everywhere. The hub sets the key at its handover (Phase C); each other multi-window repo's
  coordinator sets it, with `queue_floor: 1`, when it takes the role (the template tells it how).
- **Builders in a coordinator-mode repo see only their own items** in `next`, `ready` and the prompt count (P5-4):
  an unowned item is offered only to the distributor. When the coordinator has no live window, the Stop doorbell
  still lets a builder with an empty queue take an unowned item, pointing at `work.py ready --all --mine`
  (own items, then unassigned ones) instead of `work.py next` — no builder idles because a window is closed (D-512). A single-window
  repo and a repo without the key are unchanged.
- **`triage` plans scored items before unscored ones in a coordinator-mode store** (P5-5): nothing starves while
  the backlog is being scored, and scored work wins; the unscored list prints in every `triage` run.
- **A finished plan is marked `Status: EXECUTED` and moved to `docs/development/plans/archived/`** (P5-6):
  `EXECUTED` is in both `docs_updater.py::PLAN_DONE` and `work.py::_PLAN_DONE` and is the value the hub's plans use.
- **The four-name lists that gain `coordinator`** (P5-1): `mail.py::HUB_BEATS` (and its docstring and the
  `send`/`route --to-agent` help), `mail_notify.py::_HUB_BEATS`, `quota_dashboard.py::_HUB_OWNERS` and `_HUB_AGENTS`, and `CLAUDE.md`'s
  `route --to-agent` line and trailer row. **Unchanged:** `command_run.py::_BEATS`, whose only reader is the FEEDBACK
  verdict (amended at the Finish review, D-875), and the feedback-grammar strings (`close-feedback.md`,
  the `command_run.py` FEEDBACK text) — they name where a finding is routed by beat, and the coordinator owns
  no beat.
- **The feedback-owner fallback stays as it is** (P5-7): `work.py::_feedback_owner` falls back to the
  distributor when `feedback_owner` is unset or not a valid name. The hub sets it (`kaizen`); in another multi-window repo the
  coordinator turns a feedback-queue nudge into a work item for a builder (job 3) — the charter says so. A code
  change would decide another repo's feedback owner for it.
- **D5's drop-list batch check** (spec § Open unknowns, "the panel, or the operator" — plan approval chose the
  operator): the coordinator scores the first 50 items and boards their proposed drops, with reasons, as ONE
  awaiting-operator item (job 5); nothing is dropped until the operator answers. The operator's answer decides
  whether later batches are boarded too. The panel stays the escalation for a coin-flip score (spec D3).
- **The launch gates the row:** the operator starts the coordinator window (a hub agent cannot open one). infra
  stays merge owner in the main checkout until `mail.py who coordinator` shows the live session; only then are the
  row and the config flip committed and infra moves to its worktree — so no hub merge waits on an empty seat.

## Global Constraints (every phase inherits these)

- **No drift (D-863).** Only the spec's delta; nothing from § Recorded, not applied. A finding that asks for new
  scope is recorded in the receipt, never applied.
- **Order (spec § Contract deltas):** `coordinator` joins every hub beat list (Phase B) BEFORE the
  `MERGE OWNER: coordinator` row (Phase C) — `merge_request.py` sends `--to-agent <owner>` and `mail.py` refuses a
  name outside `HUB_BEATS`.
- **Status, never content (spec D3 job 7).** The coordinator's write surface is the charter's list; nothing in this
  plan gives it a code path that edits another session's spec, plan, board or lock.
- **Distributor-only verbs stay distributor-only:** the new `assign` flags sit behind `cmd_assign`'s existing
  distributor check; `triage --apply` keeps its own.
- **Model by alias:** the coordinator launches with `--model sonnet`, never a pinned ID (Constraints Digest row 1).
- **No new dependency; no deps-file edit** (Constraints Digest row 2).
- **Tests:** one per behaviour, each watched fail first (Constraints Digest row 3); fixtures build a scratch store
  with `work.py init` under `tmp_path`, registered worktree names for the multi-window case, `"coordinator_mode":
  true` written into the scratch store's `config.json` for every coordinator-mode row (A9, A12, A14), and the
  `CLAUDE_AGENT` env var for the caller; red-on-revert runs in a throwaway worktree (`git worktree add --detach
  <scratch>/probe HEAD`), never in the shared checkout.
- **Seats** never mutate git state, never read `~/.claude*`, never write under `/opt`.
- **Execution discipline (native seats only, D-181):** every phase ends with `/fabrik-review-scoped` on its
  surface and does not hand on until its closing pass confirms zero defects. The Finish `/fabrik-review`
  partitions the whole-plan diff by file into a Sonnet and a Haiku finder per slice (D-344), plus the D7 Opus
  floor once; the orchestrator executes every refutation (Constraints Digest row 4).

## Context Ledger

| Source | What binds | Grounded ref |
|---|---|---|
| `.windsurf/rules/ai/00-ai-model-selection.md` (MATCHED) | select Claude by alias | `ai/00-ai-model-selection.md:34` |
| `.windsurf/rules/core/10-python.md` (MATCHED) | no deps-file edit; UTC-aware datetimes | `core/10-python.md:30`, `:220` |
| `.windsurf/rules/core/45-testing-strategy.md` (MATCHED) | watched-fail-first | `core/45-testing-strategy.md:22` |
| `.windsurf/rules/core/62-using-subagents.md` (MATCHED) | who hunts last is never the author | `core/62-using-subagents.md:77` |
| `.windsurf/rules/core/40-documentation.md` (MATCHED) | docs the change makes stale are updated in it | `CLAUDE.md` § Doc Sync Matrix |
| `.windsurf/rules/core/75-workers-jobs.md` (MATCHED by `.fabrik/beat-owners.json`) | not engaged: no job, queue or handler changes | — |
| `.windsurf/rules/core/35-security-auth.md`, `core/25-data-postgres.md`, `core/30-ops.md` (FLOOR) | not engaged: no secret, no database, no service | `spec § What exists today` |
| D-442, D-453, D-471, D-613, D-860, D-863, D-868 | self-service, merge owner, coordinator, panel, cloud credit, approvals | `docs/DECISIONS.md` |

## Constraints Digest (verbatim rows from the MUST-READ packs)

| Quote | Source |
|---|---|
| select Claude by alias; those packs are corrected on their own turns | `.windsurf/rules/ai/00-ai-model-selection.md:34` |
| Dependencies live in `pyproject.toml` + `uv.lock`. Do not modify these files unless the ticket authorises it. | `.windsurf/rules/core/10-python.md:30` |
| Watched-fail-first (for tests this change adds or modifies; trivia stays skipped per the Behavior Contract) | `.windsurf/rules/core/45-testing-strategy.md:22` |
| Role separation (review loops) — who hunts LAST is never the author | `.windsurf/rules/core/62-using-subagents.md:77` |

## Phase A — the store

✅ EXECUTED 2026-10-15 — the Phase A commit on branch `plan-coordinator-role` (isolation worktree; reaches master at Finish). `/fabrik-review-scoped` (ROUTED-TO-FINISH: governance-sync) closed quiet: confirmed 9 → 2 → 0; 23 coordinator tests, every one seen red first; 582 work-store tests green.

Appetite: 150

Surface: `scripts/work.py`, `tests/test_work_coordinator.py` (EXISTS — 28 tests; extend it, never recreate),
`docs/reference/work-tracking.md`.

1. **Scores (spec D4).** `assign` gains `--impact high|low`, `--effort high|low` and `--why "<one line>"`.
   - `cmd_assign`'s "assign needs --owner, --priority, --tag and/or --untag" guard and message gain the five new
     flags (this step's and step 2's), behind the existing distributor check.
   - Writing either field requires `--why`; the item stores `impact`, `effort` and `score_reason` (a later scoring
     call overwrites the reason with its own).
   - Every check runs on the item as it will be written, so a score split across two calls is judged as one:
     with both fields present, `priority` is derived (high/low → 1, high/high → 2, low/low → 3); low/high is
     refused with the time-sink pointer (`work.py drop --why`) and nothing is written.
   - `--priority 0` on a scored item sets 0 (the incident override); the override ends when the coordinator
     re-scores the item without `--priority 0` in the same call — the priority is derived again, and the call
     prints `P0 override cleared (now P<n>)` so the clearing is never silent; any other `--priority` on an item that
     carries both fields (or gains them in this call) is refused, because its priority is derived. On an unscored
     item `add --priority` and `assign --priority` behave exactly as today.
2. **Holds (P5-2).** `assign --blocked-by <id>` (repeatable) adds to `blocked_by`, refusing an unknown id and the
   item itself; `--unblock <id>` removes one. `ready` already skips an item with an open blocker
   (`scripts/work.py::_is_ready`).
3. **Triage (P5-3, P5-5).** `cmd_triage` additionally:
   - prints `unscored <n>: <ids>` — every open item without both fields, excluding `kind: next` items and items
     closed in another tree (`_closed_ids`);
   - in a coordinator-mode store (`config.json` `coordinator_mode: true`), plans scored routable items before
     unscored ones (each group in today's order);
   - computes the in-flight major by a fresh scan of `_iter_items(main)` minus `_closed_ids(main)`: an item with
     both fields high, owned or claimed, and status `open` or `blocked` (`_pool` and `_worker_queues`
     cannot answer this: both read only ready, unclaimed items). While one exists, no high/high item is planned and
     the slot holder is printed; while none exists, at most ONE high/high item is planned per run.
4. **Builders see their own (P5-4).** One helper decides "a builder in a coordinator-mode repo": `main =
   _worktrees(repo)[0].resolve()` (never `_workers(repo)`, which is empty from a linked tree), `_workers(main)`
   non-empty, `coordinator_mode: true` in main's config, and the caller is not the distributor. The caller's name is resolved exactly as the Stop hook resolves it today —
   `scripts/work.py::_stop_action`'s name block, every fallback it carries (the session-aware `_agent_name`, the
   worker tree's name, the feedback owner's tree, the distributor in the main checkout) — factored out unchanged
   into one helper that both call. For such a builder:
   - `next` and the default `ready` offer only items the builder owns — the filter is applied in `cmd_next` and in
     `cmd_ready`'s default branch, never inside `_ready_items`/`_ready_from`, so `ready --all` and
     `ready --all --mine` keep today's output (the doorbell's self-service list below);
   - the prompt block's `work: N ready` line counts only those;
   - the Stop doorbell's no-live-coordinator branch keeps today's "take the next unowned item" and names
     `python3 scripts/work.py ready --all --mine` (the caller's own items, then unassigned ones, never another
     agent's — `_ready_from`'s `mine` filter) instead of `work.py next`, so the builder can still serve itself
     while the coordinator is away.
   The distributor, every single-window repo and every repo without the key keep today's behaviour.
5. **Docs.** `docs/reference/work-tracking.md`: the three score flags, the two hold flags and the triage lines;
   the `ready`/`next` rows ("this agent's own first, then unassigned") and the "`ready` stays the fallback" line,
   rewritten for builders in a coordinator-mode repo — a repo without the key is unchanged (`CLAUDE.md` § Doc
   Sync Matrix, "API/SDK/CLI changed").
6. Gate, `/fabrik-review-scoped`, commit. `scripts/work.py` is a governance-sync path: the commit distributes it
   fleet-wide, which is why every behaviour that changes what a builder sees is behind `coordinator_mode`.

### Behavior Contract — Phase A

Fixtures extend `tests/test_work_coordinator.py`'s existing fake-`/proc` fixture (`FABRIK_WORK_PROC`), so workers
are PRESENT — without it `triage` plans nothing at HEAD and A9–A10 could never be seen red.

| # | Given | When | Then | Test |
|---|---|---|---|---|
| A1 | an item | the distributor runs `assign <id> --impact high --effort low --why x` | `impact`, `effort`, `score_reason` stored; `priority` 1 | `tests/test_work_coordinator.py::test_score_derives_priority` |
| A2 | an item | `--impact high --effort high` / `--impact low --effort low` | priority 2 / 3 | same test, parametrised |
| A3 | an item | `--impact low --effort high` in one call, or `--impact low` then `--effort high` in two | refused, naming `work.py drop --why`; item unchanged | `::test_time_sink_refused` (both shapes) |
| A4 | an item | `--impact high` without `--why`; or `--blocked-by X` alone | refused / accepted (the "assign needs" guard knows the new flags) | `::test_score_needs_reason`, `::test_assign_guard_knows_new_flags` |
| A5 | a scored item | `--priority 0`; then `--priority 3`; then a re-score without `--priority` | 0 set; 3 refused; the re-score restores the derived priority | `::test_priority_override` |
| A6 | items X, Y | `assign Y --blocked-by X`, then `--unblock X` | Y absent from `ready` while X is open; present after | `::test_hold_and_release` |
| A7 | an item | `--blocked-by` an unknown id, or itself | refused | `::test_hold_refuses_bad_ids` |
| A8 | scored, unscored, a `kind: next` item | `triage` | `unscored <n>: <ids>` names exactly the unscored non-next ones | `::test_triage_lists_unscored` |
| A9 | coordinator mode, a present worker below the floor, a scored low/low item (P3) and an OLDER unscored P2 item | `triage` | the scored P3 item is planned first (at HEAD, and without the key, the unscored P2 item is first — the red step) | `::test_triage_scored_first` |
| A10 | a high/high item owned and open — then claimed — then `blocked`; another high/high unowned | `triage --apply` | the second is never assigned; the slot holder is named | `::test_one_major_in_flight` (three states) |
| A11 | no major in flight, two unowned high/high items, two present workers below the floor | `triage --apply` | exactly one is assigned | `::test_one_major_per_run` |
| A12 | coordinator mode, an unowned ready item committed on main and merged into the builder's branch (so the builder's own tree holds it) | a builder runs `next` / `ready` FROM ITS LINKED WORKTREE | not offered by `next` or the default `ready` — at HEAD it IS offered, the red step; still listed by `ready --all` and by `ready --all --mine` (the guard against a filter placed in the shared helper); the distributor's `next` from the main checkout offers it; the builder's prompt count excludes it | `::test_builder_sees_own_items` |
| A13 | a single-window store; a multi-window store without the key | any agent runs `next` | unchanged (unowned items offered) | `::test_unchanged_without_coordinator_mode` |
| A14 | coordinator mode, no live coordinator window, a routable unowned item | the Stop decision for a builder with an empty queue | a `doorbell` that says "unowned" and names `work.py ready --all --mine`, not `work.py next` (at HEAD it names `next`); the existing `::test_stop_doorbell_for_an_empty_worker_when_only_backlog_waits` (no key) keeps passing unchanged | `::test_doorbell_points_at_ready_all_mine` |

## Phase B — the role

✅ EXECUTED 2026-10-15 — the Phase B commit on branch `plan-coordinator-role` (reaches master at Finish). `/fabrik-review-scoped` (ROUTED-TO-FINISH: governance-sync) closed quiet: confirmed 20 → 7 → 0 (round 2's seven were six own-fix and one census miss); the census also brought `docs/reference/fabrik-mail.md`, `docs/workstation/quota-dashboard.md` and `scripts/sysadmin/mail_escalate.py` into the surface. The new guide test (`test_cli_refusal_exits_2_with_the_beat_guide_on_stderr`, now over every `HUB_BEATS` name) is red on the pre-fix `mail.py`.

Appetite: 90

Surface: `scripts/mail.py`, `.claude/hooks/mail_notify.py`, `scripts/command_run.py`,
`scripts/sysadmin/quota_dashboard.py`, `tests/test_quota_dashboard.py`, `tests/test_mail_addressing.py`,
`docs/reference/agents/coordinator.md` (new), `templates/governance/CLAUDE.md`, `CLAUDE.md`, `INDEX.md`.

1. **Beat lists (P5-1).** Add `coordinator` to the lists § Decisions taken here names; update the two tests that
   pin the dashboard's owner order (`tests/test_quota_dashboard.py`, the `owners ==` and `every =` lists);
   `tests/test_mail_notify.py` already pins `_HUB_BEATS == HUB_BEATS`.
2. **The charter** `docs/reference/agents/coordinator.md`, first line `# Agent charter — coordinator` (so
   `agent_role.py` injects it): mandate, a pointer to the template section for the seven jobs and priority
   table (never restated), the hub's write surface (job 7 and **Never**), the finished-plan mark (`EXECUTED` +
   archive), the D5 batch check, the feedback-nudge rule, and the launch line
   `CLAUDE_AGENT=coordinator claude -n coordinator-fabrik --model sonnet`.
3. **The fleet carrier.** `templates/governance/CLAUDE.md`, beside the D-471 sentence: one section carrying the
   seven jobs, **Never**, the escalation table and D4's table, and the D-471 narrowing ("in a multi-window repo
   the main-checkout agent coordinates and does nothing else"). Single-window repos: the one agent applies the
   same priority rules and the one-major limit.
4. **D-rows:** D-471 narrowed; D-442 narrowed (in a coordinator-mode repo a builder claims what the coordinator
   queued it).
5. `INDEX.md` row for the charter. Gate, `/fabrik-review-scoped`, commit (governance-sync paths: the
   post-commit sync distributes the template and the synced scripts).

### Behavior Contract — Phase B

| # | Given | When | Then | Test |
|---|---|---|---|---|
| B1 | the hub mailbox | `mail.py send --to fabrik --to-agent coordinator` | accepted (today: refused as an unknown hub beat) | `tests/test_mail_addressing.py::test_coordinator_is_a_hub_beat` |
| B2 | a mail addressed to `coordinator` | the notify hook renders it | the owner shows (tuples pinned equal) | `tests/test_mail_notify.py` (existing equality pin) |
| B3 | a repo pane | the dashboard renders owners | `coordinator` appears in the hub order | `tests/test_quota_dashboard.py` (updated pins) |
| B4 | the new `docs/reference/agents/coordinator.md` | the agents-directory contract runs | its first line carries the `# Agent charter` marker `agent_role.py` keys on | `tests/test_agent_role_hook.py` (parametrised over every file in `docs/reference/agents/`) |

## Phase C — Finish, then the hub handover

⏸ 2026-10-15 — steps 1-5 done, step 6 waiting on the launch. Step 5: the Finish `/fabrik-review` closed 10 → 3 → 0
(`docs/development/reviews/2026-10-15-plan-1-coordinator-role-review.md`) and Phases A-B merged to master at
300d803ed (fleet sync ran). Step 4 (after that merge): fabrik-lib 01M4YN9HNE and the seven multi-window repos mailed
(`_workers` measured: 8 of 42 stores, the hub and those seven); fleet, intel and kaizen told by `SendMessage`.
Steps 1-3 are committed on this branch only, with the CHANGELOG entry — merging the branch into master IS the flip,
done by infra once `mail.py who coordinator` shows the live session; then infra tells the coordinator and moves to
`.claude/worktrees/infra`.

Appetite: 75

Surface: `CLAUDE.md`, `docs/reference/agents/infra.md`, `docs/reference/multi-agent-operating-model.md`,
`.fabrik/work/config.json`, `.fabrik/beat-owners.json`, `docs/DECISIONS.md`, `CHANGELOG.md`.

1. **Mirrors (spec § Contract deltas):** `CLAUDE.md` § Shared repo and § EXIT ("infra (the merge owner)" →
   the coordinator; infra joins the worktree agents), § Autonomy (the coordinator cause);
   `docs/reference/agents/infra.md` (merge owner and distributor removed, builder in
   `.claude/worktrees/infra`); `docs/reference/multi-agent-operating-model.md` § Ownership surfaces, § Hub vs
   project and § Claim or assign. Prepared in the working tree, not yet committed.
2. **Flips, prepared:** `.fabrik/work/config.json` `distributor: coordinator`, `queue_floor: 1`,
   `coordinator_mode: true`; in `.fabrik/beat-owners.json` the topics `merge request` and `work item` move OUT of
   the infra rule that holds them (with eight other topics) into a NEW rule
   `{"topics": ["merge request", "work item"], "owner": "coordinator"}` — a topic is matched across all rules and
   two owners on one subject read as ambiguous (`scripts/mail.py::owner_of`), so the strings move, the infra rule
   keeps the rest. `check_beat_owners.py` validates owners against `HUB_BEATS`, which Phase B extended.
3. **The row, prepared:** `supersedes D-453: MERGE OWNER: coordinator` (`decisions.py --merge-owner` resolves it).
4. **Mail — sent AFTER step 5's merge and before step 6's flip, out of list order** (the template reaches the
   fleet only when step 5's merge syncs it, so a mail sent earlier would point at text the repo does not yet hold —
   Finish review):
   - fabrik-lib's hand-kept CLAUDE.md (spec § Contract deltas, "by mail"): a `mail.py send --to fabrik-lib`
     request naming the D-471 narrowing and the hub's new merge owner, with the template section's text;
   - each other multi-window repo with a store (web-ecommerce-factory, tryton-crm, trade-intelligence,
     site-provisioner, whatsapp-agent, iterative_image_editor, brand-identiy-creator — `work.py::_workers`
     non-empty, measured at execution): one request naming the synced template section and how its coordinator
     takes the role (`coordinator_mode: true`, `queue_floor: 1`, its own D5);
   - the hub builders (fleet, intel, kaizen), by `SendMessage`: merge master before your next merge request — a
     branch older than Phase B carries a `mail.py` that refuses `--to-agent coordinator`.
5. **Finish, before the flip:** the whole-plan `/fabrik-review` (D7 floor) over Phases A–B's commits and this
   phase's prepared tree, one receipt; its fixes land while infra is still merge owner. infra also merges every open
   merge request addressed to it.
6. **The launch gate:** infra boards one awaiting-operator item — "launch the coordinator now:
   `CLAUDE_AGENT=coordinator claude -n coordinator-fabrik --model sonnet` in /opt/fabrik" — and waits. When
   `mail.py who coordinator` shows the live session, infra commits steps 1–3 with the CHANGELOG entry, pushes, tells
   the coordinator by `SendMessage` that it now owns merges and that its first assignment is D5, and moves itself
   into `.claude/worktrees/infra` (`EnterWorktree`).

### Behavior Contract — Phase C

| # | Given | When | Then | Test |
|---|---|---|---|---|
| C1 | the committed row | `decisions.py --merge-owner .` | prints `coordinator` | executed in § Evidence |
| C2 | the committed config | `work.py triage` as `coordinator` | runs as the distributor in coordinator mode; as `infra`, `triage --apply` is refused | executed in § Evidence |
| C3 | the map | `check_beat_owners.py`; `mail.py`'s `owner_of` on a subject "merge request …" | passes; the owner is `coordinator`, not ambiguous | executed in § Evidence |

## File Scope (owned paths)

- `scripts/work.py`, `tests/test_work_coordinator.py`
- `scripts/mail.py`, `.claude/hooks/mail_notify.py`, `scripts/command_run.py`, `scripts/sysadmin/quota_dashboard.py`, `scripts/sysadmin/mail_escalate.py`
- `tests/test_quota_dashboard.py`, `tests/test_mail_addressing.py`, `tests/test_governance_template_split.py`, `tests/test_command_run.py`
- `docs/reference/fabrik-mail.md`, `docs/workstation/quota-dashboard.md` (census mirrors, Phase B review)
- `docs/reference/agents/coordinator.md`, `docs/reference/agents/infra.md`, `docs/reference/multi-agent-operating-model.md`, `docs/reference/work-tracking.md`
- `templates/governance/CLAUDE.md`, `CLAUDE.md`
- `.fabrik/work/config.json`, `.fabrik/beat-owners.json`
- `docs/DECISIONS.md`, `CHANGELOG.md`, `INDEX.md`, `docs/development/plans/2026-10-15-plan-1-coordinator-role.md`

## Spec Coverage

| Spec item | Plan (phase · step, or Behavior Contract row) |
|---|---|
| D1 where the role runs | B · step 3 (fleet carrier); C · step 4 (other repos, by mail); C · steps 1–6 (hub) |
| D2 model | B · step 2 (launch line, by alias) |
| D3 jobs 1, 4, 5, 6, 7, **Never**, escalation | B · steps 2–3 — the agent's behaviour, carried by the charter and the template |
| D3 job 2, D4 | A · step 1; rows A1–A5 |
| D3 job 3 | A · steps 2–4; rows A6–A14; C · step 2 (hub `queue_floor: 1`); C · step 4 (other repos) |
| D5 | § Decisions taken here (operator check of the first drops); C · step 6 (first assignment); C · step 4 (other repos' own D5) |
| Contract deltas: work item | A · step 1; row A8 |
| Contract deltas: assignment (D-442) | A · step 4; B · step 4 |
| Contract deltas: beat lists before the row | B · step 1 (rows B1–B3), then C · step 3 |
| Contract deltas: merge owner, distributor | C · steps 2–3 (rows C1, C2) |
| Contract deltas: identity | B · step 2 (row B4); C · step 6 |
| Contract deltas: mirrors | C · step 1 (hub docs); B · step 3 (template); C · step 4 (fabrik-lib by mail) |
| Contract deltas: fleet carrier | B · step 3 |

## Coverage Checklist

Derived from `review_rubric.py` over the paths Phases A–C write (output pasted below), plus the review's class ledger.

| Class | Source | Where it bites in this plan | Status |
|---|---|---|---|
| secrets, config via env, no hardcoded fallback | core/35-security-auth.md (FLOOR) | no secret or credential is read; config is the store's `config.json` | CLEAN |
| data / migrations | core/25-data-postgres.md (FLOOR) | no database; the work store is JSON files | CLEAN |
| ops, cron, deploy invariants | core/30-ops.md (FLOOR) | no cron, no service, no VPS write | CLEAN |
| 12-Factor (all twelve) | the FLOOR block | stateless CLI verbs; config in one repo file | CLEAN |
| model by alias | ai/00-ai-model-selection.md | the coordinator's launch line | CLEAN |
| Python discipline (deps untouched, UTC) | core/10-python.md | `work.py`, `mail.py`, `mail_notify.py`, `command_run.py` edits | CLEAN |
| documentation landing sites | core/40-documentation.md | charter, template, CLAUDE.md mirrors, work-tracking, INDEX | FIXED (round 1: work-tracking `ready`/`next` rows added, F10) |
| one test per behaviour, watched-fail-first | core/45-testing-strategy.md | rows A1–A14, B1–B4 | FIXED (rounds 1–4: fake-proc fixture, A10–A14 red steps, A5 P0 exit) |
| author-blind review, native seats | core/62-using-subagents.md | per-phase scoped reviews, the Finish review | CLEAN |
| workers / jobs | core/75-workers-jobs.md | not engaged: no job or queue handler | CLEAN |
| cited symbols resolve | review class ledger | every `file::symbol` in the plan | FIXED (round 1: the test file exists — extend it, F5) |
| choices buildable as written | review class ledger | D-869's eight choices vs the code paths they touch | FIXED (rounds 1–3: per-run cap, linked-tree main, in-flight scan, callers, guard, P0 exit) |
| ordering (lists before the row) | review class ledger | Phase B → Phase C | CLEAN |
| File Scope = written paths | review class ledger | § File Scope vs every step | FIXED (round 2: step references renumbered) |

<!-- rubric output (review_rubric.py --changed <Phase A–C paths>) -->
# REVIEW RUBRIC — inject into EVERY finder prompt (generated by review_rubric.py)
# Honesty (L1): this arms the review — it raises compliance probability, it does not guarantee it.

## FLOOR — always injected, regardless of glob (spec L3; SERVICE surface)

### core/35-security-auth.md
**The default for ALL new projects, including user-facing SaaS + mobile.** Vendor `fabrik-lib/fastapi-user-auth`: the app issues its own JWTs — **Argon2id** (the vendored argon2-cffi defaults meet OWASP minimums; never Argon2i) + timing-equalized login, atomic refresh-token rotation (`DELETE … RETURNING`), JWT `jti` denylist revocation, and dual-mode tenant-isolation RLS. Supabase is retired as a default (see `agents-fabrik.md § Supabase`); reach for Pattern B only for a project that *already* runs on Supabase Auth.
- Do not use NextAuth.js, Clerk, Auth0, or Firebase Auth.
- ADDITIONAL affordance a project justifies, never the default door.
- project files the fabrik-lib request FIRST, never hand-rolls WebAuthn.
| `chrome-extension` | ✅ **use this** | ⚠️ only via `chrome.identity.launchWebAuthFlow` + the `https://<ext-id>.chromiumapp.org/` redirect the pack already mandates; a bare mailed link lands in a TAB that cannot reach `chrome.storage.session` |
| `desktop-app` | ✅ **use this** | ⚠️ needs a registered custom protocol handler; the token then goes to `safeStorage` (`desktop-app/72-desktop.md`) |
- service MUST be able to say which:
| **Another Fabrik service** (Docker-to-Docker on the `fabrik` network) | `X-Internal-Token` + `internal_auth.py`, `hmac.compare_digest`, 403 on reject | § Internal Service Auth (M2M) below — **never** an inline `APIKeyHeader`, never a per-service key name |
- An approval link opened somewhere the user did not start must never mint a session silently.
- > **Fail-closed invariant (hard, every mode).** `auth.uid()` and `current_tenant_id()` MUST return `NULL` (→ the policy denies) on unset, empty, or malformed claims — wrap the body in `EXCEPTION WHEN OTHERS THEN RETURN NULL`. **Never** raise and never default to a value: a default turns one bad/empty JWT into a cross-tenant read, and a raise turns a deny into a 500. This is the single most security-critical line in the build — verify it explicitly with a no-context probe (`SELECT auth.uid()` → `NULL`).
- The JWT signing secret must be at least 256 bits, generated via `openssl rand -hex 32`, and injected via Pydantic Settings. Never hardcode it.
- **Pin the algorithm in the VERIFIER** — pass an explicit allow-list (`algorithms=["HS256"]`), never let the library dispatch on the token header's `alg`. Header-driven dispatch is the classic confusion attack (an RS256 public key replayed as an HS256 HMAC secret); `alg: none` is rejected unconditionally.
- "Sticky sessions are a violation of twelve-factor and should never be used or relied upon."
- => Mandate: processes are stateless/share-nothing. **STICKY SESSIONS ARE BANNED** (not just file-based sessions). Session state goes to `redis-main` (Redis) with a TTL. Never in-process memory, never on local disk. Any design that assumes "the same user hits the same process" is a violation.
- **Pattern B (legacy / migration-only):** The Supabase client SDK handles token storage. On mobile, wrap with `expo-secure-store` (never AsyncStorage or MMKV for tokens). See `80-mobile.md` § Backend Integration.
- **Both patterns:** Never store JWTs in `localStorage` or `sessionStorage` on web. Never store JWTs in AsyncStorage or MMKV on mobile.
- **Chrome Extension (MV3) specifics:** `chrome.storage.session` defaults to `TRUSTED_CONTEXTS`, so **content scripts cannot read the token** — keep it in the SW / extension-page context and have content scripts fetch it via SW-mediated messaging (`chrome.runtime.sendMessage`), not a direct read. For social login use `chrome.identity.launchWebAuthFlow` with **PKCE** (`code_verifier` via `crypto.subtle`, held in `storage.session`, redirect `https://<ext-id>.chromiumapp.org/`); the **backend** does the code-for-token exchange. **Never a heavy browser auth SDK** (Auth0-SPA-JS, `oidc-client-ts`) — they assume DOM/`localStorage`/iframes and break in the service worker. Pin a manifest `key` so the extension ID (and thus the `chrome-extension://<id>` CORS origin) is stable across machines. Full detail: `chrome-ext/70-chrome-ext.md`.
- **Never rely solely on the framework's request-shaping layer for access control.** CVE-2025-29927 (the `x-middleware-subrequest` bypass) proved COMPLETE middleware bypass via one crafted header; it is long patched upstream, but the rule outlives the patch — current Next.js even RENAMED the file to say so: `middleware.ts` became **`proxy.ts`**, explicitly repositioned as request-shaping, not a security boundary. ⚠️ **On current majors a leftover `middleware.ts` is SILENTLY IGNORED at build** — nonce injection and redirects stop executing with no error; rename it when upgrading.
- `CORSMiddleware` in FastAPI must populate `allow_origins` from environment variables (Pydantic Settings). Never hardcode origins.
- `X-Frame-Options: DENY` — kept as the legacy fallback only; formally obsoleted by `frame-ancestors`, never ship it ALONE
**Never** write inline `APIKeyHeader` / `require_api_key`. **Never** use per-service key names (`SERVICE_API_KEY`, `PROXY_API_KEY`). Scaffold `python-api` auto-emits `internal_auth.py`, `metrics.py` (REQUEST_COUNT / ERROR_COUNT / ACTIVE_JOBS / PROCESSING_COUNT), `/metrics` endpoint (Authelia-bypassed), and `SERVICE_INTERNAL_SECRET_KEY` in `.env.example`.
- => Mandate: config via env vars only (`os.getenv("KEY", "default")`); **ZERO secrets/constants in code**. Apply the open-source litmus test to every change. **BANNED**: grouped/named env config sets (e.g. a `config/production.yml` or a `settings.production` group) — env vars are granular and orthogonal, set per deploy. (The pack already covers secret handling — cross-reference existing secret patterns and extend with config orthogonality.)
- [ ] Mobile tokens stored in `expo-secure-store` — never AsyncStorage or MMKV.
- A dedicated admin host on its own domain — never the customer-facing app's domain — behind 2FA: set `shape.is_admin_dashboard: true` there. The Authelia registrar adds a per-domain `two_factor` rule on `fabrik apply`, so every path on that domain sits behind 2FA except the standing `/health` and `/metrics` bypasses (D-366, `saas/60-saas-ui.md` § Admin). API services with bearer auth: set `shape.has_bearer_api: true` — the registrar inserts an Authelia **bypass** rule *before* the `two_factor` catch-all so machine/bearer callers aren't hit with interactive 2FA. Don't add Traefik `authelia-forward` middlewares manually — the scaffolder + registrars emit them.
- > **⚠️ Bearer bypass scope — security-critical.** The bypass defaults to `^/api/`, which makes the **entire** `/api/*` surface public (un-2FA'd). If the application authenticates only a **sub-prefix** (e.g. `/api/v1` carries the bearer/internal-token check) while OTHER `/api/*` routes are unauthenticated (legacy / admin / destructive), you **MUST** narrow the bypass with `shape.bearer_bypass_prefix: "^/api/v1"` — otherwise `fabrik apply` exposes those routes to the public internet. **Bypass ONLY the path the app itself authenticates.** Value must start with `^/`; the verifier (`orchestrator/verifier.check_api_bypass`) probes the configured prefix on deploy. When unsure whether a service has un-auth'd `/api/*` routes, ask the app owner before relying on the `^/api/` default.

### core/25-data-postgres.md
| Vector search | pgvector on `postgres-main` + `fabrik-lib/rag` — ⚠️ the extension is NOT currently installed there (probed 2026-09-01: the plain upstream PostgreSQL Alpine image, `plpgsql` only — `CLAIMS.yaml` row `fleet-postgres-main-no-pgvector`); a project needing vectors REQUESTS the fleet infra change first, never assumes it | same `postgres-main` DSN |
**"Own database" means a DATABASE on `postgres-main`, never a database SERVER.** Per-project isolation is a separate database (its own name, its own role) on the shared container — isolation, quota and backup are all satisfied at that grain. A dedicated Postgres instance is a decision, not a default: it needs its own `docs/DECISIONS.md` row naming what the shared server cannot serve (web-ecommerce-factory 01M1Q8X9, 2026-09-05: "one DB per store" read naively as one server per customer).
- Use Pydantic `BaseSettings` (per `10-python.md` § Config Loading) — never raw `os.getenv` **for an APPLICATION's settings surface**:
- ⚠️ **Scope, stated here because this LINE is what `review_rubric.py` injects — without its section.** The rubric FLOOR-injects this mandate *and* `35-security-auth`'s "config via env vars only (`os.getenv("KEY", "default")`)" into every finder prompt on every review, so a finder reading both literally has two rules it cannot both satisfy, and files a false positive on whichever it applies. The carve-out: `BaseSettings` governs a SERVICE's config surface (a `Settings` object, DB/Redis DSNs, secrets). A **vendored fabrik-lib module** has no settings object by design — it reads its own knobs with bare `os.getenv("KEY", "default")`, which is `35-security-auth`'s mandate being satisfied, not this … (wrapped further — read the pack)
- Never blindly trust `--autogenerate`. Always review `upgrade()` and `downgrade()` for unintended column drops, rename misinterpretations, and ENUM alterations before committing.
- > **Older pythons only** (services pinned below stdlib-uuid7 — which today includes SCAFFOLDED services: the scaffold still emits an older interpreter and ships `uuid-utils`; alignment tracked in the backlog): import `uuid7` from `uuid_utils.compat`, never `uuid_utils.uuid7()` directly — the latter returns `uuid_utils.UUID`, which asyncpg rejects (not a stdlib `uuid.UUID`). **DB-side:** newer PostgreSQL majors ship native `uuidv7()` (probe: `SELECT uuidv7()`); prefer `DEFAULT uuidv7()` at schema level where it exists. `postgres-main` currently runs major <!--v:postgres_major-->16<!--/v-->, which predates it — generate app-side on the fleet.
- Foreign keys must declare `ON DELETE` behaviour explicitly — `CASCADE` if children cannot exist without the parent, `RESTRICT` to protect audit trails. Never rely on the implicit default.
- This section owns the **canonical** engine, session, and `get_db`. `10-python.md` imports from here — never redefines its own.
- Database `AsyncSession` must be scoped to the route handler via `Depends()`. Never open sessions or transactions in global middleware — this holds connections during serialisation and I/O, exhausting the pool.
**BANNED as a server-side backing service** (dev, test, and prod alike):
**⚠️ SCOPE — this ban is about BACKING SERVICES, not client-local storage.** It does **NOT** apply to:
- **`desktop-app`** — SQLite is the **mandated** engine there (`desktop-app/72-desktop.md` § Local Persistence: `better-sqlite3` + SQLCipher; *"Production builds MUST encrypt the local SQLite file"*).
**12-Factor IV (Backing Services) — generalised:** swapping ANY attached backing service (DB, cache, object storage) is a **config change, never a code change**. The handle lives in `DATABASE_URL` / `REDIS_URL` / storage env — the code *reads* it, the code does not *decide* it. Never `if ENV == "prod":` branching to pick a host. (See § PostgreSQL Host Selection, which already mandates this for the DB.)
- [ ] All primary keys use UUIDv7 — stdlib `uuid.uuid7` on current Python (older pythons: `uuid_utils.compat.uuid7`, never direct `uuid_utils.uuid7()`); no `uuid4()`.

### core/30-ops.md
- the pinned release leaves full security support, never per-pack.
- All services deploy via `fabrik apply` (SSH + Docker Compose) on the `fabrik` network. Traefik routes external traffic — services do NOT bind host ports.
- **No `ports:` section.** All external traffic routes through Traefik. Never bind host ports. See Docker Port Security below. **12‑Factor VII (Port binding):** "the app is self‑contained and exports HTTP by binding to a port; it does not rely on runtime injection of a webserver" — which is exactly WHY no host `ports:`.
- **`container_name: <name>` is mandatory.** Same `_validate_compose()` gate refuses any service without it. Stable names are required so Gatus endpoints, inter-service URLs, and `docker exec`/`docker inspect` keys don't drift per redeploy. Use the bare service name (`browserless`, `gotenberg`, `meilisearch`, `glitchtip-web`, `site-provisioner`, etc.) — never UUID-suffixed names.
- gets one (ruling D-052) — see `core/60-watchdog.md`. Do not author a `watchdog: { enabled: false }` opt-out; if a project genuinely cannot host the sidecar, that is a ruling to obtain, not a default to flip.
- path before the flag goes in the spec, and assert target health (`/api/v1/targets` → `up`), never a bare `curl` of a path you assumed.
- remove it` on the hub) names a plan that protects nothing. Never add a service-named plan.
- health-enabled service can NEVER pass `up -d --wait` on a fresh database, and the deploy hangs to timeout.  An init the deploy cannot perform itself is a runbook step the plan MUST own.
- `fabrik redeploy <app>` SSHes to the VPS and runs `git pull` + `docker compose up -d --wait` against the **GitHub remote**, NOT the local `/opt/<app>` clone. Skipping `git push` redeploys the previous remote commit — the VPS never sees local changes.
**Mandate:** build → release → run are strictly separated. Releases are IMMUTABLE; the git SHA is the release ID. NEVER hot‑patch a running container (no `docker exec` to edit code/config in place, no in‑place code mutation on the VPS). Any change = a new build + a new release via `fabrik apply` / `fabrik redeploy`.
- Runtime database migrations that modify the app container (migrations MUST be run as separate deploy‑time steps)
**Place a service next to its data.** A spoke-hosted service reaches `postgres-main`/`redis-main` over the WireGuard mesh, and that hop is cross-Atlantic (Coventry ↔ LA) on EVERY query — a per-request chatty service pays it hundreds of times per page. So a DB-chatty service targets vps1; a spoke earns a service whose data traffic is light, batched or cached; a service PINNED to a spoke by hardware (GPU) batches or caches its data access — the data never moves off vps1. Measure before choosing (`ping 10.99.0.1` from the spoke, and the request's query count), never assume — the correctness rule ("container DNS, never localhost") says nothing about latency.
**Mandate:** WSL dev and the VPS run the SAME backing services (PostgreSQL + Redis), same major version. NEVER substitute a different backing service in dev (no SQLite standing in for Postgres, no in‑memory dict standing in for Redis). The same code must run unmodified in both environments.
- WSL runs PostgreSQL + Redis at the SAME MAJOR as the VPS containers — probe the live truth, never copy a tag from a doc: `ssh vps "sudo docker inspect postgres-main redis-main --format '{{.Config.Image}}'"` (probed 2026-09-01: the plain upstream PostgreSQL Alpine image at the fleet major recorded in `CLAIMS.yaml` row `pg-fleet-major` · `redis:7-alpine` — upstream official images, outside OUR-image Alpine ban per § Banned Patterns)
**Invariant:** Never use `ports:` in compose.yaml to expose internal services to the host. All external traffic must go through Traefik.
**Health endpoints (`/health`, `/healthz`, `/metrics`, `/api/health`) bypass Authelia on all services** — required for Gatus and Prometheus monitoring. The bypass is **resource-based, not domain-bound** — applies on every domain routed through Authelia (hub direct + spokes via `authelia-vps1@file` middleware). Never protect these paths.
**CRITICAL:** Use `web`/`websecure` in Traefik labels — never `http`/`https` (those entrypoints do not exist). The scaffolder emits the correct entrypoint names; if you hand-write labels, match these exactly.
**Mandate:** migrations and admin tasks run as a ONE‑OFF process against the DEPLOYED image + env — identical environment to regular processes. NEVER run admin tasks from a laptop against prod, NEVER via `docker exec` into a live container, and **ABSOLUTELY NEVER auto-run migrations from app startup/`lifespan`** (concurrent replicas race the Alembic version table → wedged deploy).
- `docker compose run --rm <svc> alembic upgrade head` (against deployed environment) — `<svc>` is a service that declares `.env.owner` (a `migrate` service), never the app service — the owner DSN is not in the app service's environment after the owner split (D-754), and `run` replaces the service's `command`, so a hand-off written there is bypassed
- > **`fabrik run` and `.fabrik/hooks/post-deploy/` do NOT exist** — the real CLI answers `Error: No such command 'run'`, the hook path appears nowhere in the platform, and `_post_deploy_sync()` (`cli.py:64`) only refreshes `data/projects.yaml`; an agent following either ships a deploy where migrations never run. Do not re-add either without a `path:line` in `src/fabrik/` that executes it.
**Processes are share-nothing:** any state shared across requests MUST go to Redis (`redis-main`) with a TTL. A project using Redis for sessions MUST declare `shape.needs_cache: true` in `specs/services/<id>.yaml`, or `fabrik apply` skips the Redis registrar and the deploy is silently broken.
- "A twelve-factor app never relies on implicit existence of system-wide packages"
**Mandate:** any binary the app shells out to (ffmpeg, yt-dlp, poppler, tesseract…) MUST be `apt-get install`-ed in the Dockerfile, with a `shutil.which()` startup probe that fails fast. **The pinned base image is the version boundary** — exact `=version` apt pins are banned: they break on every Debian point release as old debs leave the mirrors (the "works then mysteriously breaks" class this section exists to prevent); the codename pin + image digest give the reproducibility. Never assume `curl`/ImageMagick/ffmpeg exist in the image — they don't by default.

### 12-FACTOR (all twelve axes)
- I codebase: shared code → fabrik-lib, never two apps in one repo
- II deps: every shelled-out binary installed + pinned in the Dockerfile
- III config: granular env vars; no secrets in code; no grouped env sets
- IV backing services: swappable by DSN/config change only
- V build/release/run: releases immutable; never hot-patch a container
- VI processes: stateless; session state → redis-main; no sticky sessions
- VII port binding: bind in-container; Traefik routes; no host ports:
- VIII concurrency: scale out; never daemonize or write PID files
- IX disposability: SIGTERM returns in-flight jobs to the queue; jobs idempotent
- X dev/prod parity: same backing services everywhere; no SQLite-for-Postgres
- XI logs: unbuffered stdout only; the app never writes/rotates a logfile
- XII admin: migrations/one-offs run against the deployed release, never startup

## MATCHED — packs whose globs hit the changed paths

### ai/00-ai-model-selection.md  (hit: docs/reference/agents/coordinator.md, docs/reference/agents/infra.md)
**Always the latest Claude models — select by ALIAS, never by an old ID.** Claude Code's aliases resolve to the newest model of each family and move with every release, so code that says `--model opus` never goes stale:
- A pinned ID in code or config is a stale model waiting to happen: when reproducibility genuinely matters, take the ID from the table above (its values are machine-owned in `.windsurf/rules/versions.yaml`) and record why the pin beats the alias. Fable is never an account default — it is always selected explicitly. `best` resolves to Fable where it is available, else Opus. **Where a category pack (`10`–`90`) or a sibling pack still names a Claude model by version, or routes an LLM step to a metered gateway only, THIS section wins** — select Claude by alias; those packs are corrected on their own turns.
**Vendor access:** `docs/reference/kilo/AI_VENDOR_ACCESS.md` is the single source of truth for which vendors the operator can call today. Rows with Status ✅ or ⚠️ are accessible (⚠️ = accessible but low balance — pick a ✅ peer if one is on the Pareto frontier).
- Operational stack (sysadmin, watchdog, bootstrap) uses **Claude Code CLI w/ subscription OAuth** — never `ANTHROPIC_API_KEY`. No fabrik code path reads that key (the `fabrik ai generate` utilities were removed 2026-06-16); a project that needs a metered LLM goes through OpenRouter. Per-LLM-call cost caps apply to paid APIs via `core/cost-budget.md`; they must not be placed on the operational diagnose loop.
- model label only; for per-model `modelUsage`, read `DispatchResult.model_usage` from `dispatch()`) with an **opt-in OpenRouter HTTP fallback** (`LLM_ALLOW_METERED_FALLBACK`, off by default; never after a CLI call that already billed); env-driven `LLMConfig`; **INJECT** your vendored `cost-budget` via the `budget_check`/`budget_record` hooks; `complete()`/`complete_json()` return empty instead of raising when a CALL fails (building the config from the environment can still raise `ValueError` on a malformed numeric var). The module bakes in NO model: an unset `CLAUDE_CLI_MODEL` (or `LLM_DEFAULT_MODEL` when the HTTP leg runs) raises `ModelNotConfigured` at the point of use unless the call names one (a missing binary or a refusing `budget_check` raises first). ⚠️ `complete(model=…)` sets the OpenRouter model only; choose the `claude -p` rung per call with `complete(prompt, claude_model="sonnet")` — or `dispatch(ClaudeCall(prompt, model="sonnet"))`, which RAISES (`DispatchError`, or `ValueError` for an invalid `ClaudeCall`) and has no OpenRouter leg, so catch both yourself. `CLAUDE_CLI_EFFORT` defaults to empty (each model's designed effort) — set it deliberately before judging that a rung measurably fell short.
- `claude -p` MUST declare **`shape.uses_claude_cli: true`** (+ `claude_cli_home`) so the deployer mounts the host's **rotated** `~/.claude` read-only into the container — auth follows the fleet account rotation;
**never** bake a static `CLAUDE_CODE_OAUTH_TOKEN` (it pins one account and dies at its weekly quota). Then select the rung — always by alias, so each rung is the latest model of its family:
- enough (task fails its quality gate / errors — a measured escalation, never a vibes one).
- be metered-isolated from the subscription). ⚠️ `complete()`/`complete_json()` take this leg ONLY with `LLM_ALLOW_METERED_FALLBACK=1`, and then when the `claude -p` leg failed to produce text — binary missing, auth failure, timeout, error, quota, or YOUR `budget_check` refusing `claude-cli` — never after a CLI call that succeeded empty (already billed); `budget_check` fails OPEN if it raises, so deny by returning `False`; `dispatch()` and the session/agentic calls never fall back, and `complete_structured()` only through a `fallback=` you inject. The key is `KILO_API_KEY` before `OPENROUTER_API_KEY`, and `KILO_API_URL` overrides the endpoint — wherever the fleet's keys sit in the environment (the hub's, per D-182) they win. So when you opt in, unset both `KILO_*` vars, set the project's OWN `OPENROUTER_API_KEY`, guard the leg with `budget_check`, and alert on the dispatcher's no-content fallback; leave the opt-in off when the call must never go metered. Set `LLM_DEFAULT_MODEL` to the bake-off … (wrapped further — read the pack)
**tested evidence, never assumption**: consult the selection MDs / `suggest_model.py`, or run a scored bake-off — lowest cost that meets the required capability; record the result in the project's decision ledger.
- above; never `ANTHROPIC_API_KEY`, never a vendor SDK — `core/57-external-data-sourcing.md` hard constraint). Every rung wraps in the `58-resilience` contract, and any unattended paid-LLM loop still carries watchdog + cost-budget. This ladder governs **in-code single-call/worker dispatch**; gradeable parallel fan-out (review finders, graders, doc reconcilers) runs NATIVE while the pool is OFF (D-181) per `core/62-using-subagents.md`.
- 5. **No rationale needed:** the model returns probabilities, never a reason.
- Wire the lane only through fabrik-lib's `decision-gate` module, never a hand-rolled client. The module is vendorable (`/opt/fabrik-lib/decision-gate/`, its README is the contract); a project copies it in with the change that wires its first consumer, never ahead of one, and that consumer stays off until criterion 6 is met. Inside the lane, deterministic rules decide first and the model decides only what they leave open; every question carries an explicit `insufficient` option, because the model never abstains on its own; the threshold is calibrated per decision on the project's own labelled data, scored on a held-out split; everything under the threshold falls back to the ladder above; and a pilot runs in shadow mode first and is armed only when its wrong-allow rate is no worse than the mechanism it … (wrapped further — read the pack)

### core/10-python.md  (hit: .claude/hooks/mail_notify.py, scripts/command_run.py, scripts/mail.py)
**`uv`** is the mandated Python package manager. Never use raw `pip`, `pip install`, `poetry`, or `pipenv`.
- Dependencies live in `pyproject.toml` + `uv.lock`. Do not modify these files unless the ticket authorises it.
- its own reviewed commit, never as a side effect of unrelated work.
- The one RULE: use SQLAlchemy async consistently — never mix `async def` with sync `.query().all()` (the Banned table row; the full session pattern is `25-data-postgres.md`'s).
- The canonical `engine`, `async_session`, and `get_db` are defined in `src/database.py` — owned by `25-data-postgres.md`. Import from there, never redefine:
**Config convention:** apps read a complete `DATABASE_URL` (`postgresql+asyncpg://user:pass@host:port/db`) and `REDIS_URL` from env. Discrete `DB_HOST`/`DB_PORT`/`DB_NAME`/`DB_USER`/`DB_PASSWORD` for the app to assemble are **banned**. The env supplies the complete URL — `localhost` in WSL, `postgres-main` on VPS — so the host concern is an env-layer responsibility, never code logic. See `30-ops.md` compose template for how discrete vars are interpolated into `DATABASE_URL` at the compose level.
- volume** (`30-ops.md` § Volumes), never in `.tmp` and never in `/tmp`.
**GlitchTip discipline:** unhandled exceptions (FastAPI 500s) are auto-captured by GlitchTip with full stacktraces. In the `except Exception` branch, log a **short event name + correlation_id** — never `logger.exception()` (that duplicates the traceback in Loki AND GlitchTip). See `55-observability.md` § Error Reporting for the full rule.
**Note:** Use the scaffolded logger: `from {package}.logger import get_logger` (see `55-observability.md` § Pre-Scaffolded Logging). Do not use `structlog.get_logger()` directly or `logging.getLogger(__name__)`.
- **Never a bare `asyncio.create_task()`** — an unreferenced task is silently garbage-collected and its exceptions vanish. Hold the reference and await it, or use `asyncio.TaskGroup`.
- **`datetime.now(UTC)`, never `datetime.utcnow()`** — deprecated and naive; naive datetimes are a real cross-service defect class.
- Type the package, never `.`: the root walks the hub-synced `scripts/`, where mypy finds the same file under two module names and stops on every fresh project. file-worker types `mypy --explicit-package-bases worker`; a `server/` backend (saas-skeleton, static-site, office-extension, chrome-extension, mobile-app) runs `mypy src` from `server/` (D-605).
- Ruff's selected rule-sets MUST include `ASYNC` (blocking IO in async code — machine-enforces this pack's hardest-to-review rule), `B` (bugbear) and `S` (bandit) alongside the defaults; configured in `pyproject.toml`, emitted by the scaffolder.
- Production services run via `uvicorn` CLI in the Dockerfile, not `uvicorn.run()` in code. Base image is always the pinned Debian `-slim` variant on `linux/amd64` (the variant is pinned fleet-wide in `30-ops.md` § Container Base Images — change it THERE, never per-repo). Never use Alpine — musllinux wheels exist now (PEP 656) but coverage is still partial, source builds are dramatically slower, and musl's allocator/stack defaults degrade CPython; the trade never pays on this fleet.
- `uvicorn.run()` is for local development only. Never ship it in production code.
- a fleet scaling decision (more containers), never a per-app flag.
**BANNED: grouped/named env config sets.** 12F is explicit — *"env vars are granular controls, each fully orthogonal to other env vars"* — so a `config/production.yml`, a `settings.production` group, or a `config/{dev,staging,prod}.yaml` tree is a violation. Env vars are granular and set **per deploy**, never batched into a named "environment".
**BANNED:** `logging.FileHandler`, `logging.handlers.RotatingFileHandler`, `TimedRotatingFileHandler`, `loguru` file sinks, any `*.log` file write, any in-app log rotation/retention/cleanup. The app never decides where logs are stored or routed — Docker → Promtail → Loki does. Full rule: `55-observability.md` § Logs.
**Factor XII — Admin processes. NEVER migrate from app startup.**
**BANNED: `alembic upgrade head` in FastAPI's `lifespan`, in an `@app.on_event("startup")`, or as an import side-effect.** With more than one replica (or a restart storm) two containers run `upgrade head` **concurrently** → they race the Alembic version table → duplicate DDL → **wedged deploy**. Migrations are a **one-off admin process against the deployed release**: `docker compose run --rm <svc> alembic upgrade head` (`<svc>` is a service that declares `.env.owner` (a `migrate` service), never the app service — the owner DSN is not in the app service's environment after the owner split (D-754), and `run` replaces the service's `command`, so a hand-off written there is bypassed) (see `30-ops.md` § Release & Admin Processes).
| `alembic upgrade head` in `lifespan` / startup hook | One-off admin process against the deployed release: `docker compose run --rm <svc> alembic upgrade head`, `<svc>` a service that declares `.env.owner` (a `migrate` service), never the app service (D-754) (concurrent replicas race the version table) |

### core/40-documentation.md  (hit: CLAUDE.md, docs/reference/agents/coordinator.md, docs/reference/agents/infra.md)
- > **⚠️ `docs/OPERATIONS.md` + `docs/DEPLOYMENT.md` are FLEET-AI INTERFACES, not just docs (D-065).**
- **Tier-1 (author → verify → converge; the author leg is NATIVE while the pool is OFF, D-181 — `scripts/doc_reconcile.py`'s pool author cannot dispatch):** for each **mechanically-detectable** doc whose Doc-Sync trigger fired (`docs/QUICKSTART.md` · `docs/CONFIGURATION.md` · `docs/data-contract.md` · `docs/SERVICES.md` · `docs/OPERATIONS.md` — the reliable-signal subset), `scripts/doc_reconcile.py` dispatches a cheap OpenRouter-pool author (`libs.subagents`, `pick_models("docs")`) to emit a **minimal structured patch**, **verifies it before applying** (a symbol cross-check catches invented endpoints; the orchestrator injects a higher-assurance native-Claude verify), and loops to a zero-edit round. Runs per phase in `/fabrik-execute-plan`; never blocks (fail-safe). The other docs (CHANGELOG, INDEX, FEATURES, RESILIENCE, PORTS, the READMEs, `db/schema.sql`, …) have no reliable mechanical content-signal → they rely on the touch-on-change backstop below + your own edit (force-update, not force-correct).
- The SSOT is the type-aware registry (`scripts/enforcement/_doc_registry.py::PROJECT_DOCS`) — this table is its project-facing rendering, kept in step, never a second truth. `/fabrik-plan-after-chat` (the plan set's spine + tickets — the ticket-format authority) injects these rows per ticket as its `Docs:` line.
- Standalone work (not plan execution) → `Agent-Role: primary`. Trailers go below a blank line, above `Co-Authored-By`. ⚠️ The trailer block must be its OWN paragraph with NO blank line inside it: git parses only the LAST paragraph, and only if it is all-trailers. A blank line before `Co-Authored-By:` demotes everything above it to prose; so does a prose line glued to the top of the block. Measured 2026-08-15: 200 of the last 200 hub commits carried `Agent-Role:` and only 10 parsed, because the old example here shipped the blank line.
- **⚠️ Link it or it is decoration.** *Measured:* requests for files that do NOT exist came ~zero from AI bots — agents never go looking. It follows (inference, not measurement) that a file only gets read when something points at it: reference it from the docs index or README.
- ⚠️ **In the hub (`/opt/fabrik`) `llms.txt` is GENERATED** (`scripts/generate_capability_index.py`, refreshed daily) — never hand-edit it there; change the generator. A project has no such generator; an `llms.txt` it ships, hand-written or built by its own code, is its own.
- either way. Cheap and reversible — never at the expense of `OPERATIONS.md`/`DEPLOYMENT.md`, which are the load-bearing agent interfaces (D-065).
- **No skipped heading levels** — `##` to `###`, never `##` to `####`
- **Fenced code blocks only** — never indented code (AI treats it inconsistently)

### core/45-testing-strategy.md  (hit: tests/test_mail_addressing.py, tests/test_quota_dashboard.py, tests/test_work_coordinator.py)
- **Behavior Contract**: every ticket enumerates its distinct **user-observable behaviors / acceptance criteria** and tests **each one** — one high-value integration/E2E test per behavior, risk-ordered, TDD for the risky ones. Skip trivia (getters / framework glue / config): **lean-but-complete, NOT 100%-line-coverage dogma**. Do not chase line coverage — ensure every behavior has a test that would fail if that behavior regressed. (Cheap pool subagents can author the per-behavior tests — the suggest→curate→author→fix workflow in `62-using-subagents.md` § Dispatch policy + `~/.claude/commands/fabrik-review.md`.)
- **No cosmetic assertions**: never assert against CSS classes, Tailwind utility strings, pixel measurements, or snapshot hashes. Assert application state and user-visible outcomes only.
- **Watched-fail-first** (for tests this change adds or modifies; trivia stays skipped per the Behavior Contract): a non-trivial behavior's test proves something only if it has been SEEN RED — either write it first and watch it fail, or (after the fact) neuter the fix/feature, prove the test goes red, then RESTORE and re-run to green. The neutered state is never staged, committed, or left in the tree. A green test never seen red is unverified — a suite can pass with its guard deleted.
- **Run tests**: `uv run pytest tests/` (never bare `pytest` — Fabrik uses `uv`) — **when the project has a `pyproject.toml`/`uv.lock`**. A `requirements.txt`-only project (no manifest) runs `.venv/bin/python -m pytest tests/` — the manifest clause chooses the RUNNER, it never disarms the mandate to run the suite (web-ecommerce-factory 01M1QEY5, 2026-09-05: the clause read as "does not apply here"). ⚠️ **Gate this on the manifest, because this line is FLOOR-injected into finder prompts and a vendored fabrik-lib MODULE has neither by design**: the module recipe ships `requirements.txt` (`fabrik-lib/README.md` § Creating a Reference Implementation), so `uv run` cannot resolve it and `python3 -m pytest` is the only thing that works. Telling a finder the sole working … (wrapped further — read the pack)
- **Zero-mock database policy**: never mock SQLAlchemy, SQLModel, or database sessions. All backend tests execute against a real PostgreSQL instance.
- **`ASGITransport` never runs lifespan** — anything the app initializes at startup (scaffolded apps are lifespan-based) silently does not exist in tests; wrap with `asgi-lifespan`'s `LifespanManager` when a test needs startup state.
- Use `structlog` in test helpers if logging is needed — never `print()`. See `55-observability.md`.
- **Never stub a server action from Playwright** — the server is the E2E boundary; stubbing belongs in the unit lane where the action is a plain function.
- Run Playwright against the PRODUCTION build (`next build && next start`), never the dev server.
- All locators must be **semantic**: `page.getByRole('button', { name: /submit/i })`. Never use CSS selectors or XPath.
- Launch Playwright's **bundled Chromium** (`channel: 'chromium'`) — stable Chrome/Edge removed the `--load-extension` / `--disable-extensions-except` side-load flags (Chrome 137/139), so those args only work under bundled Chromium, never installed stable Chrome.
- Run `@axe-core/playwright` with **`bypassCSP: true`** (the non-relaxable extension CSP otherwise makes axe throw on `chrome-extension://` pages); keep `@axe-core/playwright` a **dev-dependency only** (MPL-2.0 — never bundled into the shipped artifact). Gate bundle size with `size-limit` **per surface** (popup / side-panel / content-script). Full loop: `chrome-ext/70-chrome-ext.md` § Testing & UI Verification.
- Keep the generated types committed and re-generate on schema changes (`uv run python -c "import json; from <package>.main import app; print(json.dumps(app.openapi()))" > openapi.json` — the scaffold emits `src/<package>/main.py`, never a flat `src/main.py`, so `src.main` imports nothing).
**BANNED in tests:**
| A GUARD proven only by the ONE spelling of the defect you already fixed | Write the guard's subject five LEGITIMATE ways — five a DIFFERENT author would plausibly write, not five typos of yours — and count how many it still catches; one of five means it is keyed on your fix, not on the class — and one of five is the FLOOR of the failure, never its definition: four of five is a partial class and is reported as four of five. This is IN ADDITION to red-on-revert below, not a rival bar: that one proves the guard fires at all, this one proves it fires on the class. ⚠️ Cheapest ways to satisfy it WITHOUT the outcome (`CLAUDE.md` § UNIVERSAL governance markers, the entry whose anchor is **you get the behavior you measure** — search the ANCHOR, not the rule name: the project-facing contract lists that section by anchor alone and carries the name `cobra-effect` nowhere): (i) write five near-identical spellings and count 5/5; (ii) ship at 2/5 and REPORT it, needing no fabrication at all, in the hope that a reported count reads as a passed one — it does not: under 5/5 is a finding; (iii) claim the exercise and record nothing, since the five are never committed. So the bar is TWO things and needs both: **the five go IN the test file as executable CASES**, never a comment — a comment cannot go RED, so nothing can falsify it, and that is the objection, not that it records nothing — **and anything under 5/5 is a finding, not a pass**. ⚠️ Two paths this row does NOT close, stated rather than pretended away: you can shrink the SUBJECT until five legitimate spellings all land inside what the guard already catches (nothing is fabricated; the claim narrowed, not the guard), and an honest 4/5 — real information, 80% of the class — costs the author something to report, so the cheapest response to it is silence. Report the count you got either way — a 4/5 with the miss NAMED is a finding someone can act on, and a 5/5 nobody can execute is not a pass at all. Measured 4× in one day across 2 repos (01M1S4D78KRM0ZSYDNGTHS9HYQ), and once more the day this row landed: a contract-parity grader that read the LIVE file instead of the tree under test stayed green under the exact drift it existed to catch |
| A test THIS change adds/modifies that was never seen red (no fail-first, no red-on-revert proof) | Watch it fail first, or neuter the change → prove red → restore → re-run green |
- [ ] Destructive DB tests pass the throwaway guard before connecting — `require_throwaway(TEST_DATABASE_URL)` where the scaffold emitted `tests/conftest.py`; where it did not (an unscaffolded repo has no such helper), this anchored predicate, verbatim: `dbname = urlparse(url).path.lstrip('/'); assert dbname.lower().endswith(('_test', 'throwaway', 'scratch')), dbname` — never point them at a dev/shared DB.

### core/62-using-subagents.md  (hit: docs/reference/agents/coordinator.md, docs/reference/agents/infra.md)
- GOAL: One place that says which subagent runtime to use, what tools it gets, what NEVER goes to a subagent, and how tool access is a single-source change. AGENT USAGE: When a command dispatches subagents, pick the runtime + the tool scope from here. Design authority: docs/superpowers/specs/archived/2026-07-07-subagent-tool-parity-design.md (Claude Code side). The paused pool's contract: docs/reference/subagent-pool-contract.md. -->
- > **⚠️ STATUS — the OpenRouter pool, Kilo subagents and `ai-consult` are PAUSED** (operator: D-181 2026-09-07, mechanism D-182, re-confirmed 2026-09-22 — D-343). Their credentials stay provisioned, so a `fanout()` / `consult()` would still dispatch and SPEND: this pack and `scripts/enforcement/check_subagent_flywheel.py` (`_POOL_POLICY_ON = False`, fleet-synced; `FABRIK_POOL_POLICY=on` is its test seam and re-arms the gate — never set it in a run) are the control, and intel monitors `fabrik_analytics.subagent_runs` for any dispatch while the pause holds. **Every fan-out runs native Claude Task subagents.** This pack's pool-era contract is FROZEN verbatim in `docs/reference/subagent-pool-contract.md`; re-enabling is an operator ruling first, then a restore from that file — never a quiet uncomment.
**Never restate tool lists in a command brief — the access lives in the agent-type file.** Compose a subagent's brief per `docs/reference/MD/ai-prompt-templates.md` — a distilled system prompt (Part A) that enforces the agentic patterns (Part B: termination contract, evidence-before-assertion, path:line grounding, untrusted-input). Distil, don't dump the whole rulebook into the brief.
**The paused runtime — fabrik-lib `subagents` (OpenRouter models in a sandboxed worktree) — is not Claude, has no browser, and is not to be called.** Its `pick_models` still returns a dispatchable roster and `fanout` still spends; the only lever that refuses is this text (D-182). Do not "turn it off" by emptying `docs/reference/kilo/TASK_SUBAGENT_SELECTION.md` — `pick_models` falls through an empty section to the unrestricted vendored `_TABLE`.
| rendered-UI design review (`/design-review`) | `design-review` | an explicit allow-list — playwright browser tools + Read/Edit/Write/Bash + WebFetch/WebSearch (web AND edit in one type: never hand it sensitive context); `model: sonnet` |
- **Two cheap finders per slice — one Sonnet and one Haiku, each over the whole slice, candidates UNIONED, never voted — and NO Opus finder** (pilot D-344, 2026-09-22, superseding D-207's Opus-on-the-risky mix for the partitioned loops; the units-sized floor below is unchanged; `/fabrik-execute-plan`'s per-round Opus finder floor is its own rule and still stands, D-813). The risky units — concurrency and locks, record and file formats, fleet-synced paths (`scripts/enforcement/`, `scripts/command_run.py`, the hooks, `templates/governance/`), auth, schema, migrations, secrets — are the slice's NAMED hunt priority in its brief. Opus and Fable earn their price EXECUTING and adjudicating, in the orchestrator.
- **At most ONE EXTRA Haiku class seat** across the whole surface — for a judgement-shaped inventory class the close-out hygiene script cannot express, and only when the brief NAMES it; the scriptable classes (stale phrases, table and fence shape, dead symbols, `{{` residue) are the script's from round 1's start, never a seat.
- **The orchestrator** — Opus or Fable, whichever the quota allows, and whichever newer model replaces them (D-334, D-456) — partitions, dispatches, adjudicates and EXECUTES every refutation and every confirmed reproduction. The orchestrating context is never a finder; the one reading seat Fable takes is a DISPATCHED Fable seat as the ROUND-ONE authoritative reader of a command's final validation (the last full-surface pass a command names — a plan's Finish review), substituting for the Opus seat there and then re-verifying its own slice in the closing pass like any round-one seat (constraint 5 below).
- **Round 1 is the ONLY full pass. Every later pass is the round-one seats re-verifying their OWN slices' claim ledgers (D-335, superseding D-229's delta sizing):** the surface of a later pass is the fix diff plus one hop of callers and callees (the hop bounds the EXTENT; what a later pass may COUNT is the fragments' bounded-hop rule — `term-edit`/`term-coverage`, D-230, which D-335 keeps; grep the changed symbols, or `find_referencing_symbols` where the language server is up), plus the tests that import a changed module, plus any sibling commit that landed on the surface since; a unit whose ledger holds no open claim is not re-dispatched, and the round-1 count is the ceiling. The class ledger PERSISTS across rounds: a later pass sweeps the classes its diff touches and CITES the rest as standing-clean from the last full pass, and the receipt says which — a round is never a re-scope, and there is no round CAP (D-330, superseding D-321) — the terminal is every slice verified inside the run's DECLARED budget (`command_run.py start --budget`, `round --slices A:12/12` records it), and a slice whose claims still fail after its THIRD pass, or a pass that would overrun the declared budget, is HANDED OFF with those claims named per `term-coverage.md` — never capped, never looped.
- **The closing pass is those same seats re-executing every claim of their slice ledgers and confirming zero code or doc defects present** — never the orchestrating context's own re-read (§ Role separation; a dispatched Fable seat is a seat), never the hygiene script alone.
- **Quiet is zero CONFIRMED code or doc defects (D-206), never zero raised:** a candidate becomes CONFIRMED only when the orchestrator REPRODUCES it (probe, failing test, or a mutation on a pinned copy), and REFUTED only when it EXECUTES the refutation and the receipt row cites that command and its output; a candidate neither reproduced nor refuted is `RECORDED — unexecuted (<why>)`, one reproduced and kept on purpose is `RECORDED — by design (<owning row>, round N)`, and RECORDED and REFUTED rows never reopen the loop. The Pass Ledger row states the counters in that order — `found: F, new: N, confirmed: C, fixed: X, unexecuted: U` — and the loop closes on `confirmed: 0, fixed: 0` with `unexecuted: 0` or none; a round that FIXED something is never the closing row.
**UNITS-SIZED — every OTHER command** (`/fabrik-review-scoped`, the grounding and adjudication commands — the researcher floors — and the sweep and audit reviews): per INDEPENDENT unit of the surface — failure class · file · screen · doc · pack · journey · fact · behaviour — a Sonnet breadth seat plus a Haiku mechanical seat, all dispatched in a SINGLE message so they run in parallel, plus the Opus authoritative seat(s): a 3-unit surface with a mechanical angle is 7 seats (4 with `--mechanical 0`), never a token 1–2 (the executable number is (1) below). The CAP is independence OF THE SURFACE, not of the reader — partition so no unit's ground truth is another's; a unit you cannot brief distinctly is not a seat. ⚠️ **NEVER solo, never two — the FLOOR is three seats for every command that is NOT a partitioned review loop (D-208), and the floor binds ROUND 1 only: every later pass is the round-one seat that owns each open claim, re-verifying it (D-335).** Under a partition the floor stands DOWN — satisfied by construction, since every non-empty slice kind already keeps its own seat and the third angle there is the orchestrator's EXECUTION of every candidate rather than a third reader (D-218). Where it applies, a surface with fewer than three units still dispatches THREE seats on DIFFERENT angles over it. Deliberate DUPLICATE briefs over one small surface are a different technique (`/fabrik-review-scoped` § floor): they buy sampling variance, not coverage, and are budgeted as ONE unit.
- ⚠️ **Dispatch economics — five constraints, ONE executable number (D-189).** A partitioned loop sizes with `--slices` as above, however small the partition. A units-sized surface runs `--units <N> [--heavy] [--risky <R>] [--mechanical <M>]` before any fan-out wider than the floor and dispatches the `SEATS:` it prints — `min(units × angles + the Opus seat(s), CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS, box_cap, quota_cap)`, never below 3 unless a hard cap binds or the fleet HOLD stands at its `walled` tier; a later pass is sized by its open claims (D-335); a floor-sized units fan-out at ROUND 1 (1 unit = 3 seats = the floor) needs no script — stamp its three seats with `dispatch --seats 3`.
- 1. **Maximum (D-191)**: the BOX is the ceiling and the units are the PARTITION. Every unit gets one seat per ANGLE — a Sonnet breadth seat and a Haiku mechanical seat — plus the Opus authoritative seat(s), one per risky unit and at least one (a risky unit therefore carries THREE angles: authoritative, breadth, mechanical — cost 8); `dispatch_headroom.py` computes that as the WANTED count and trims it to what the box, the CLI cap and the quota allow for maximum unit COVERAGE — Haiku first, then the extra Opus seats, then Sonnet, never the last Opus seat. **The mechanical angle is grep-shaped and therefore GLOBAL:** `--mechanical <M>` is the number of grep-able classes the surface HAS (inventory · naming · format · links/anchors · counts); when the budget trims below one Haiku seat per unit, each remaining Haiku seat sweeps ONE class across every unit; and a grounding or adjudication surface has no mechanical angle at all (`--mechanical 0`) — a Haiku seat briefed on a judgement returns a claim you must refute, which is spend without recall. Dispatch ALL of what it prints, in ONE message, each seat a distinct unit × angle brief — and when the COST line says TRIMMED, dispatch the trimmed mix, never the per-unit sentence.
- 2. **Box, no OOMs**: a native seat runs inside its parent `claude` process, so its memory is its TOOL subprocesses — and a "read-only" finder still runs pytest through Bash, so the box bound applies to EVERY seat: 2 GB planned per `--heavy` seat (pytest/build/render), 1 GB per read-only seat, against `MemAvailable` (the commit headroom too, only where the kernel enforces it) and a CPU share per seat — 0.3 of a core read-only, the measured p90 of a seat's tool time, 1 core heavy (D-511) — MINUS the seats sibling sessions DISPATCHED in the last 25 minutes, charged in GB and cores at the read-only cost rather than as whole seats of the caller's kind (`command_run.py dispatch --seats <n>`, stamped BEFORE the seats go out and accumulated within the round — a `round --seats` written at the round's close reserves nothing while the seats run; the caller's OWN record is never subtracted). Siblings RESERVE, they never starve: a session always gets the floor the box physically has room for, and the floor never overrides a hard cap — a box with room for two seats gets two, with the reason. Memory alone decides that floor: CPU contention slows every process, memory exhaustion kills one, so a CPU-saturated box still hosts the floor and prints why.
- 3. **Fastest**: every seat in ONE message (parallel), never one message apart; keep working while they run. Width is paid for (Anthropic measured multi-agent runs at ~15× the tokens of a chat, ~4× per agent): seats bill their OWN transcripts (`<sid>/subagents/agent-*.jsonl`, a Workflow seat under `workflows/wf_<id>/` — the parent's result line is one turn of it), so a wide round multiplies a run's tokens; `command_run.py` sums those transcripts into the ledger's `tok_seat_*` columns at every `round` — that is where the cost is read, never by opening a transcript. Wall-clock tracks ROUNDS, not seats — blocking on a single seat is how one round becomes many minutes of nothing.
- 5. **The right model per ROLE** — and the MECHANISM is the one-token per-dispatch override, `Agent(subagent_type=…, model="opus"|"sonnet"|"haiku"|"fable")`. Resolution order, first match wins (code.claude.com/docs/en/sub-agents): the per-dispatch token → the type file's `model:` (`fabrik-reviewer` is `sonnet`; `fabrik-researcher`/`fabrik-gui` are `inherit`) → the `CLAUDE_CODE_SUBAGENT_MODEL` env var (a DEFAULT for seats assigned no model — unset on this box) → the parent's model; so a role stated without the token IS the type's default, authoritative pass included. ⚠️ `CLAUDE_CODE_SUBAGENT_MODEL_FORCE` (ANY value, `0` included — the binary tests the string) discards every type file's `model` and the token: seats then run on `CLAUDE_CODE_SUBAGENT_MODEL`, or — when that is unset, as here — on the PARENT's model, so every Haiku and Sonnet seat silently bills at the orchestrator's 5×/10× with no error and no line in the cost print. Never set it in any fleet settings. A per-dispatch token also sticks when the seat is later resumed by message. The four names, one job each: **Fable** = orchestrator/adjudicator and, dispatched as a round-one seat, the final validation's authoritative reader (substitutes for, never adds to, the Opus seat there; never a routine finder, never a coder) — ⚠️ **Fable is METERED usage credits, not a subscription window** (the quota probe cannot see it): check availability before a run that needs it, and a Fable seat that refuses falls back to Opus BY NAME with the fallback recorded, never silently · **Opus** = the authoritative pass — under a partition that is the orchestrator's own execution of every candidate (D-344, no Opus finder; `/fabrik-execute-plan`'s per-round Opus finder floor is its own rule and still stands, D-813); ≥1 authoritative seat in a units-sized round — and design-heavy never-delegate coding · **Sonnet** = breadth, one seat per independent unit, and the default coder · **Haiku** = the mechanical seat — one per unit under units-sizing, at most one across a partition (grep-able classes, format, inventory), never codes. GUI stays `fabrik-gui`. Model is chosen by the seat's JOB, never by what is idle. **Price multipliers (operator ruling D-190): haiku 1× · sonnet 2× · opus 5× · fable 10×** — "affordable" is a NUMBER, `cost = Σ seats × multiplier` in haiku-units, and `dispatch_headroom.py` prints it (`--mix opus=1,sonnet=5` → 15). An Opus breadth seat costs 2.5× a Sonnet one — whether it buys more recall is UNMEASURED (the D-186 tripwire ledger, with `--seats` recorded, is where that answer will come from), and until it is measured the default is the cheaper seat; a Fable adjudicator costs 10 and is one seat per run, never per unit, printed beside the seat total, never inside it. The number is RELATIVE and dimensionless — it assumes equal tokens per seat, and the orchestrator's own reading (at its own multiplier, growing with every seat's report) is NOT counted: the quota band guards the seats, and nothing yet guards the orchestrator's own reading. ⚠️ The quota band of (4) is a SEAT band by design and cost stays advisory until `round --seats` rows let the band be re-cut in cost — three Opus seats (15) cost more than six Sonnet (12), and the band cannot see that yet.
**And record what you dispatched** — `python3 scripts/command_run.py round --seats <n> --findings <n> --confirmed <n> --own-fix <n> --slices <A:done/total,…> …` — because the D-186 tripwire is evaluated with seats unknown on every row that omits it. The ledger's token columns include the SEATS' own usage (`tok_seat_*`, summed from each seat's own transcript under `<sid>/subagents/` — synchronous and background seats alike), so the tripwire has a cost leg: findings per 100K seat-tokens per run, falling while seats rise, is the manufactured-seat signal. ⚠️ **The payoff claim is a HYPOTHESIS under test, not a measured result:** more findings in round 1 predicts MORE rounds and more wall-clock, and `check_ticket_breadth.py` carries a measured `rounds ≈ 1.0 × risk-class score` model — so a wider round may converge slower, not faster. TRIPWIRE (re-based at D-191 — the 20 rows count from 2026-09-08, and the variable that changed last is per-unit-per-ANGLE sizing, not per-unit): if `/fabrik-review`'s median rounds rises above 4 over those 20 ledger rows, seat inflation is inflating convergence and the rule reverts to a per-round class budget. ⚠️ **The unit count is what the SURFACE HAS — the rule scales itself and is not a quota to spend:** a one-file diff in a small synced project yields one or two units, not eight, and only the AUTHORITATIVE seat is Opus (breadth is Sonnet, the mechanical seat Haiku) — so the spend is bounded by the UNIT count (one unit = 3 seats = 8 haiku-units), never by how idle that project's box looks; native seats bill one shared subscription across ~46 repos, so more units means more seats, and a padded unit list means a wasted account.
- **Three documented limits bound a round** (`code.claude.com/docs/en/env-vars`, `/docs/en/sub-agents`; re-check the numbers on those two pages, not here; the installed binary confirms the refusal string and the tool-use default — `command grep -aoE 'Concurrent subagent limit reached.{0,120}|MAX_TOOL_USE_CONCURRENCY\?\?[0-9]+' "$(readlink -f "$(which claude)")"` — while the subagent cap's default sits behind a minified symbol): `CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS` (default 20, per SESSION — three hub sessions each get their own) — ⚠️ past it a seat is **REFUSED, not queued** (`Concurrent subagent limit reached … Do not retry`; a refused seat is a FAILED seat and its absence is never a clean round; spawning succeeds again when the running count drops); `CLAUDE_CODE_MAX_TOOL_USE_CONCURRENCY` (default 10 — read-only tools AND subagents that EXECUTE in parallel, so a 20-seat dispatch runs 10-wide); `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH` (default 3 in the binary, and a remote feature flag can move it — a seat may spawn seats; ours must not: omit `Agent` from the type's `tools` list or add it to `disallowedTools` — the documented control — and brief a type without a `tools` allow-list as a leaf, since it inherits `Agent`). `dispatch_headroom.py` trims to the concurrency cap as a HARD cap it never exceeds; below it the binding constraint on width is the box and the subscription QUOTA, not concurrency — check headroom, not the cap. (The per-session total cap `CLAUDE_CODE_MAX_SUBAGENTS_PER_SESSION` was removed and is a no-op.)
- **A seat has its own context and its own compaction** (the main conversation's rules and `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE` apply to it), so a brief is the whole of what it knows: pin the surface (a copy under the scratchpad plus a per-file md5), name the question and never the expected answer, and forbid home-directory reads (a seat that opens `~/.claude*` stalls). **A seat a later pass must RESUME is dispatched `run_in_background: true` and its `agentId` (from the spawn result) recorded in the round row** — that id is what `SendMessage` continues with its context intact; a synchronous seat has no resumable id, and a resume is also refused for an oversized transcript or a worktree outside the session's isolation fences; a new `Agent` call starts fresh and is not that seat. When a resume is refused, the successor is a FRESH seat on the SAME model over the SAME slice (`term-coverage.md`), briefed with that slice's claim ledger and the previous seat's REFUTED list verbatim — never a fresh whole-artifact reader.
- **Never `TaskOutput` a running seat, never `tail` its `.output`, never read its transcript** — the result arrives as a notification; `<sid>/subagents/agent-*.jsonl` is for the token ledger, not for reading.
- The loop-closing round's **FINDER pass** runs in a context that did **not author the artifact** — the round-one seats re-verifying their own slices (D-335). A post-compaction session is still the author's session, and an author's own quiet round never closes a review loop: the context that shaped the artifact is the one least able to see its gaps (an author re-reads intentions, not text). **One sanctioned exception — the solo self-convergence loop:** a command whose loop dispatches NO seat that reads the artifact for defects — no finder, grounder, auditor or reconciler — anywhere; a seat that DRAFTS a section of it is none of those (an author self-convergence pass, e.g. `/fabrik-ui-design`'s own convergence, whose per-screen seats draft the contract) closes with its own full fresh read — independence there is deferred to the PAIRED review command that follows it (`/fabrik-ui-design-review`), never silently skipped. **Adjudication — decide/refute/merge — stays with the orchestrator** (CLAUDE.md § Subagent fan-out: "the decide/refute/merge you own"); this rule governs who HUNTS last, never who adjudicates. The loop fragments' fresh/independent-round language defers to THIS definition of independent.
- Auth/identity/session/crypto · schema/migrations · secrets/`.env`/keys · security controls (RLS, rate-limits, `final_gate`) · deploy/infra. These stay with the primary (human-supervised) agent — the ticket Complexity tier `check_plan_tickets.py` names `never-route`, and the coder `dispatch_headroom.py`'s tier text names the never-route coder; a seat may READ and REPORT on them (the Opus authoritative slice), never edit them. **Never web/MCP-enable a seat carrying sensitive context** — the model's output exfiltrates via a scraped URL; `fabrik-reviewer` gets the repo and no web by construction of its type file; `fabrik-researcher` gets the web AND `Read`/`Grep`/`Glob` on the tree (no Bash, no edits) — it can read any tracked file, so never brief it onto a path carrying secrets; `design-review` carries web and edit both, so it never receives sensitive context.
- The canonical MCP server list is a hub-owned standard-format file — `/opt/fabrik/mcp.json` (`{"mcpServers": {name: {type, command, args, env}}}`, keys via `${ENV}` expansion, never inline).
**Since the 2026-08-30 MCP split, MAIN-AGENT servers are per-repo:** each repo's `.mcp.json` (project scope — gitignored, because postgres-pro's env carries the repo's resolved `DATABASE_URL`) is EMITTED by the hub's `scripts/sysadmin/emit_mcp_project_config.py` from the roster-ruled sets in `docs/workstation/mcp-roster.md`; the user-level rosters carry only the universal 6. Never hand-edit an emitted `.mcp.json` — change the roster/ledger ruling, then re-run the emitter.
- Adding a tool touches exactly: the roster ruling + emitter table (main agents, per repo) → `mcpServers` in the relevant agent type under `commands/_agents/` (then re-render) → `/opt/fabrik/mcp.json` — never a command brief.
- When a project fixes a real bug in a **vendored `fabrik-lib` module** (e.g. `libs/subagents/`, `libs/health_probe/`), it MUST append the fix — symptom + fix + date — to `/opt/fabrik-lib/<module>/UPSTREAM_FEEDBACK.md`. That file is the **one write allowed back into `/opt/fabrik-lib`** (cross-repo HARD STOP otherwise); the module author reads + resolves it, so the fix isn't silently lost on the next re-vendor. Fixing a vendored module without the entry breaks the loop. The hub itself never edits `libs/subagents/` (D-137) — a wanted change is a mail to fabrik-lib.

### core/75-workers-jobs.md  (hit: .fabrik/beat-owners.json)
- Connection string: `postgres-main:5432`, never `localhost`. See `30-ops.md` § Docker DNS.
- If the primary transaction rolls back, the job must never exist. This eliminates dual-write inconsistencies between application state and the queue.
- **Never** use a runtime-generated random UUID as an idempotency key — it changes on every retry, defeating the check entirely.
- The count and the base are env vars (`58-resilience.md` §7a tuning knobs), never literals in SQL or code.
- Poison-pill messages must never loop infinitely. The DLQ is for human inspection — automated agents do not resolve DLQ entries.
- **A dead-lettered job carries WHY, and the why must be honest about transport vs content.** A job that died from an operational cause (hard-timeout/poison, network, proxy, lock contention, worker restart) is an **operational** terminal — record it as `processing_timeout`/transient and present it as "timed out, will retry / re-runnable", and keep it resettable. **Never** stamp it with a *content* verdict (`deleted`, `unavailable`, `no_captions`) — that tells the user the content is gone when only the transport failed, and it's silent unrecoverable loss. A content terminal requires positive content evidence. See `58-resilience.md` § Operational failures are transient.
- I/O-bound handlers run in-process on the asyncio pool (the scaffold's default). Isolate a handler that can take the worker down with it — CPU-bound or memory-heavy — in a **child process** (shelling out is handled in-process by § External Subprocess Lifecycle); the parent monitors and marks a crashed child's job failed. ⚠️ Fork is opt-in under the pinned Python: since 3.14 `multiprocessing`'s POSIX default is `forkserver`, so `fork` must be requested explicitly (`multiprocessing.get_context("fork")`) and never from a process with threads alive (`os.fork()` warns on that since 3.12).
- **This complements the existing drain path, never replaces it.** If the job can finish in time, drain normally.
- **This complements the visibility timeout + orphan sweep, never replaces them.** The sweep is the crash-path backstop — SIGKILL, OOM, segfault, power loss. The fast path only fires on cooperative SIGTERM where the worker is still alive and can execute an `UPDATE`.
- Twelve-factor app processes **must never daemonize or write PID files.** Scale out via the process model (add container replicas), not up via in-process daemons. Docker supervises; Docker Compose restarts.
- 2. **The Adaptive Worker Pool parent** (§ Adaptive Worker Pool) supervises N independent claim loops — asyncio tasks by default, forked children for CPU-bound work — synchronised through the PG queue (`SKIP LOCKED`), not through each other. This is **not** a 12F violation: (a) the parent runs as the foreground CMD — it never daemonizes; (b) children are stateless workers, not daemons; (c) scaling *out* is still done by adding container replicas (`compose.yaml` `deploy.replicas`). The pool scales *within* one container; replicas scale *across* containers.
- 2. **Kill the group, never just the child.** On timeout/early-exit, `os.killpg(os.getpgid(proc.pid), SIGTERM)` then escalate to `SIGKILL` after a grace period. `proc.terminate()` signals only the direct child — grandchildren keep running, keep burning bandwidth/proxy, and keep per-resource locks held.
- 3. **Enforce a per-subprocess hard-timeout wall AND a kill-count poison cap.** The parent watchdog kills a subprocess that exceeds its hard limit, increments a DB `timeout_kill_count`, and after `TIMEOUT_KILL_MAX` (default 3) marks the job terminal. **That terminal is operational** — classify it transient/`processing_timeout` and surface it as "timed out, will retry", **never** as a content verdict like "unavailable" (see Dead-Letter Handling below and `58-resilience.md` § Operational failures are transient).
- 4. **Run an OS-process orphan reaper — distinct from the DB orphan-*job* sweep.** A Beat/cron sweep that SIGKILLs known subprocess names whose **parent is not a live worker** (build a live-worker-PID set; do NOT test `PPID == 1` — orphans reparent to the init system, and on WSL to `/init`, not PID 1) or that exceed the hard-limit age. The DB sweep reconciles queue rows; this reconciles OS processes — you need both.
- Every worker runs an adaptive pool: N independent claim loops scaled between `WORKER_MIN` and `WORKER_MAX` on queue depth. Fixed-concurrency workers waste resources when idle and bottleneck when loaded. The rules below are the pool's PROPERTIES; asyncio tasks are the default implementation, forked children the CPU-bound one — the same properties, not a second pattern. ⚠️ Do not assume the scaffold satisfies this section — verify the emitted worker against the Done When list before building on it.
- The parent is the **orchestrator only** — it never processes jobs. Each claim loop is independent against the PG queue.
- Fall back to process resources (`os.process_cpu_count()` — the affinity-aware count the pinned Python ships since 3.13; never `multiprocessing.cpu_count()`, which reports the HOST — and `os.sysconf`) only when cgroup files are absent or contain `max` (unbounded).
- 3. **Cap:** never exceed `max_workers`.
- 4. **Safety:** only kill workers with `job_id == 0` (idle, not processing). Never kill a worker mid-job.
- 5. **Floor:** never go below `min_workers`.
| Parent process using the shared connection pool | A dedicated short-lived connection per parent loop iteration, never the pool |
- [ ] Per-subprocess hard-timeout wall + kill-count poison cap; poison classified as operational/transient, never a content verdict.
- [ ] Scale-down: requires 3 consecutive idle checks (hysteresis); kills highest slot_id first; only idle workers; never below `min_workers`.

# promote-to-check_*: 135 injected mandate(s) look deterministically greppable — their backtick literals, one line each (the full mandates are ABOVE, not repeated: re-emitting ~20 FLOOR lines verbatim doubled the rubric and got it skimmed — web-ecommerce-factory 01M1QEY5, 2026-09-05)
- `fabrik-lib/fastapi-user-auth` `DELETE … RETURNING` `jti` `agents-fabrik.md § Supabase`
- `chrome-extension` `chrome.identity.launchWebAuthFlow` `https://<ext-id>.chromiumapp.org/` `chrome.storage.session`
- `desktop-app` `safeStorage` `desktop-app/72-desktop.md`
- `fabrik` `X-Internal-Token` `internal_auth.py` `hmac.compare_digest` `APIKeyHeader`
- `auth.uid()` `current_tenant_id()` `NULL` `EXCEPTION WHEN OTHERS THEN RETURN NULL` `SELECT auth.uid()` `NULL`
- `openssl rand -hex 32`
- `algorithms=["HS256"]` `alg` `alg: none`
- `redis-main`
- `expo-secure-store` `80-mobile.md`
- `localStorage` `sessionStorage`
- `chrome.storage.session` `TRUSTED_CONTEXTS` `chrome.runtime.sendMessage` `chrome.identity.launchWebAuthFlow` `code_verifier` `crypto.subtle` `storage.session`
- `x-middleware-subrequest` `middleware.ts` `proxy.ts` `middleware.ts`
- `CORSMiddleware` `allow_origins`
- `X-Frame-Options: DENY` `frame-ancestors`
- `APIKeyHeader` `require_api_key` `SERVICE_API_KEY` `PROXY_API_KEY` `python-api` `internal_auth.py` `metrics.py` `/metrics` `SERVICE_INTERNAL_SECRET_KEY`
- `os.getenv("KEY", "default")` `config/production.yml` `settings.production`
- `expo-secure-store`
- `shape.is_admin_dashboard: true` `two_factor` `fabrik apply` `/health` `/metrics` `saas/60-saas-ui.md` `shape.has_bearer_api: true` `two_factor`
- `^/api/` `/api/*` `/api/v1` `/api/*` `shape.bearer_bypass_prefix: "^/api/v1"` `fabrik apply` `^/` `orchestrator/verifier.check_api_bypass` `/api/*` `^/api/`
- `postgres-main` `fabrik-lib/rag` `plpgsql` `CLAIMS.yaml` `fleet-postgres-main-no-pgvector` `postgres-main`

## Evidence

Filled at execution (the `/fabrik-execute-plan` contract): per phase, the gate's JSON status line and the
commands named in the Behavior Contract tables, with their output.

## Self-audit

- Every spec delta and P5-1..P5-7 maps to a step (Coverage Checklist, Intake Inventory).
- Nothing from § Recorded, not applied is planned.
- The order constraint (lists before the row) is Phase B before Phase C.

## Residual unknowns

None that block execution. The one operator act — launching the coordinator window — is boarded at Phase C step 6
and gates the flip, so the hub keeps a merge owner throughout (§ Decisions taken here).

Recorded, not applied (review round 1, D-863): a guard on `claim` against an unowned major (a builder can still
claim one by id) and on a manual `assign --owner` of a second major — each is new scope, its own decision later.

## Pass Ledger

| Pass | seats · axes re-checked | counters | method | plan md5 (start → end) |
|-----:|---|---|---|---|
| Pass 1 | opus×1 + sonnet×1 (the round-1 slices) · all axes | found: 12, new: 12, confirmed: 7, fixed: 12, unexecuted: 0, edits: 14 | method: citation — partitioned pass; every claim executed against HEAD (scratch repos with linked worktrees, a fake proc table, `owner_of` probes) | 5169052f → 70a8ee2f |
| Pass 2 | opus×1 + sonnet×1 (the round-1 slice owners) · delta over the round-1 fix diff + one hop | found: 7, new: 7, confirmed: 5, fixed: 7, unexecuted: 0, edits: 8 | method: re-derivation — each seat re-derived its slice ledger (opus 7/9, sonnet 5/5) | 70a8ee2f → c90a339a |
| Pass 3 | opus×1 + sonnet×1 (the round-1 slice owners) · delta over the round-2 fix diff | found: 1, new: 1, confirmed: 1, fixed: 1, unexecuted: 0, edits: 2 | method: re-derivation — opus 4/5, sonnet 3/3 | c90a339a → 12951db7 |
| Pass 4 | opus×1 + sonnet×1 (the round-1 slice owners) · delta over the round-3 fix | found: 0, new: 0, confirmed: 0, fixed: 0, unexecuted: 0, edits: 0 | method: re-derivation — closing pass, opus 2/2, sonnet 1/1 verified; every other class standing clean since pass 1 | 12951db7 → 12951db7 ✓ |
| Pass 5 | opus×1 + sonnet×1 (the round-1 slice owners) · delta over the plan-approval panel's accepted changes (both seats sound-with-changes) + one hop | found: 5, new: 5, confirmed: 5, fixed: 5, unexecuted: 0, edits: 9 | method: re-derivation — opus 3/5, sonnet 6/6; all residue of the panel fixes | 907e0338 → 74abd740 |
| Pass 6 | opus×1 + sonnet×1 (the round-1 slice owners) · delta over the pass-5 fixes | found: 1, new: 1, confirmed: 1, fixed: 1, unexecuted: 0, edits: 2 | method: re-derivation — opus 5/5, sonnet 3/3; the 1 is a plausible filter-placement ambiguity, adjudicated and fixed | 74abd740 → ae0ec24d |
| Pass 7 | opus×1 + sonnet×1 (the round-1 slice owners) · delta over the pass-6 fix | found: 0, new: 0, confirmed: 0, fixed: 0, unexecuted: 0, edits: 0 | method: re-derivation — closing pass, opus 3/3, sonnet 2/2 verified; every other class standing clean | ae0ec24d → ae0ec24d ✓ |
