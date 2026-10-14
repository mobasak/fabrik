# Plan — the coordinator role: sort, prioritise, merge, keep the records; never build

Status: DRAFT
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
  builder's `next`/`ready` in a multi-window repo (spec § The delta D3 jobs 2–3, D4; § Contract deltas,
  "Work item" and "Assignment").
- **B — the role:** `coordinator` joins every hub beat list; the charter; the fleet carrier in the
  governance template (spec § Contract deltas, "hub beat lists", "identity", "fleet carrier"; D3's **Never** and
  escalation table).
- **C — the hub handover, then Finish:** the mirrors, the config and map flips, the `MERGE OWNER` row,
  infra's move into its worktree (spec D1, § Contract deltas "merge owner", "mirrors"); then the whole-plan
  `/fabrik-review` and one receipt.

Per phase: `/fabrik-review-scoped` on that phase's surface. At Finish: one heavy `/fabrik-review` (the
`/fabrik-execute-plan` D7 floor). `scripts/mail.py`, `.claude/hooks/mail_notify.py`, `scripts/command_run.py`
and `templates/governance/CLAUDE.md` are governance-sync paths: each phase commits once, after its review.

## Intake Inventory

| I# | Item (anchored) | Disposition | Where |
|---|---|---|---|
| I1 | spec § Intake Inventory rows 1–8 (with 5b) | IN | Phases A–C, per the spec rows |
| I2 | *"please do not drift"* (operator, D-863) — the spec's § Recorded, not applied stays out | IN | § Global Constraints, first bullet |
| I3 | P5-1 the four-name list census | IN | Phase B step 1 (the lists that change) and § Decisions taken here (the ones that do not) |
| I4 | P5-2 the hold mechanism | IN | Phase A step 2 (`assign --blocked-by` / `--unblock`) |
| I5 | P5-3 closing the in-flight major releases every held major | IN | Phase A step 3 (the triage guard) |
| I6 | P5-4 a builder claims what the coordinator queued it | IN | Phase A step 4 |
| I7 | P5-5 the unscored listing in the existing `triage`; `--apply` skips unscored items | IN | Phase A step 3 |
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
  high/high item while another high/high item is in flight (an owner, status `open` or `blocked`). Closing the
  in-flight major can therefore never hand two majors out at once, whatever the holds say.
- **Builders in a multi-window repo see only their own items** in `next` and `ready` (P5-4): an unowned
  item is offered only to the distributor. A single-window repo is unchanged.
- **`triage --apply` skips unscored items in a multi-window store** (P5-5); the unscored list prints in every
  `triage` run.
- **A finished plan is marked `Status: EXECUTED` and moved to `docs/development/plans/archived/`** (P5-6):
  `EXECUTED` is in both `docs_updater.py::PLAN_DONE` and `work.py::_PLAN_DONE` and is the value the hub's plans use.
- **The four-name lists that gain `coordinator`** (P5-1): `mail.py::HUB_BEATS` (and its docstring and the
  `send`/`route --to-agent` help), `mail_notify.py::_HUB_BEATS`, `command_run.py::_BEATS` (a finding mailed to
  the coordinator is a filing), `quota_dashboard.py::_HUB_OWNERS` and `_HUB_AGENTS`, and `CLAUDE.md`'s
  `route --to-agent` line and trailer row. **Unchanged:** the feedback-grammar strings (`close-feedback.md`,
  the `command_run.py` FEEDBACK text) — they name where a finding is routed by beat, and the coordinator owns
  no beat.
- **The feedback-owner fallback stays as it is** (P5-7): `work.py::_feedback_owner` falls back to the
  distributor only when `feedback_owner` is unset. The hub sets it (`kaizen`); in another multi-window repo the
  coordinator turns a feedback-queue nudge into a work item for a builder (job 3) — the charter says so. A code
  change would decide another repo's feedback owner for it.
- **D5's drop-list batch check** (spec § Open unknowns): the coordinator scores the first 50 items, and the
  drops among them go to the Opus + Fable panel as ONE batch. If both seats agree with every drop, later drops
  carry only their reasons; if either rejects one, every later batch of 50 goes to the panel too.
- **The launch:** the operator starts the coordinator window; a hub agent cannot open one. Merge requests that
  arrive between the `MERGE OWNER` row and the launch wait in the mailbox, addressed to `coordinator` — none is lost.

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
  with `work.py init` under `tmp_path`, registered worktree names for the multi-window case, and the
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

Appetite: 120

Surface: `scripts/work.py`, `tests/test_work_coordinator.py` (new), `docs/reference/work-tracking.md`.

1. **Scores (spec D4).** `assign` gains `--impact high|low`, `--effort high|low` and `--why "<one line>"`.
   - Writing either field requires `--why`; the item stores `impact`, `effort` and `score_reason`.
   - When the item then carries both fields, `priority` is derived: high/low → 1, high/high → 2, low/low → 3.
   - low/high is refused with the time-sink pointer: drop it with `work.py drop --why`.
   - `--priority 0` alongside the fields keeps 0 (the incident override); any other `--priority` with the
     fields is refused (the priority is derived).
   - `add --priority` and `assign --priority` without the fields behave exactly as today.
2. **Holds (P5-2).** `assign --blocked-by <id>` (repeatable) adds to `blocked_by`, refusing an unknown id and
   the item itself; `--unblock <id>` removes one. `ready` already skips an item with an open blocker
   (`scripts/work.py::_is_ready`).
3. **Triage (P5-3, P5-5).** `cmd_triage` additionally:
   - prints `unscored <n>: <ids>` — every open item without both fields;
   - in a multi-window store (`_workers` non-empty) leaves unscored items out of the plan;
   - leaves every high/high item out of the plan while one high/high item is in flight (an owner, status
     `open` or `blocked`), and prints which item holds the slot.
4. **Builders see their own (P5-4).** `cmd_next` and `cmd_ready` pass `mine=True` with an owned-only filter
   when the repo is multi-window and the caller is not the distributor; unowned items stay visible to the
   distributor and in single-window repos.
5. **Docs.** `docs/reference/work-tracking.md` documents the three `assign` flags, the two holds flags and the
   triage lines (`CLAUDE.md` § Doc Sync Matrix, "API/SDK/CLI changed" — the hub's CLI reference is this page).
6. Gate, `/fabrik-review-scoped`, commit with the D-rows for § Decisions taken here.

### Behavior Contract — Phase A

| # | Given | When | Then | Test |
|---|---|---|---|---|
| A1 | an item | the distributor runs `assign <id> --impact high --effort low --why x` | `impact`, `effort`, `score_reason` stored; `priority` 1 | `tests/test_work_coordinator.py::test_score_derives_priority` |
| A2 | an item | `--impact high --effort high` / `--impact low --effort low` | priority 2 / 3 | same test, parametrised |
| A3 | an item | `--impact low --effort high` | refused, naming `work.py drop --why`; item unchanged | `::test_time_sink_refused` |
| A4 | an item | `--impact high` without `--why` | refused; item unchanged | `::test_score_needs_reason` |
| A5 | an item | `--impact high --effort low --why x --priority 0` / `--priority 3` | 0 kept / refused | `::test_priority_override` |
| A6 | items X, Y | `assign Y --blocked-by X`, then `--unblock X` | Y absent from `ready` while X is open; present after the unblock | `::test_hold_and_release` |
| A7 | an item | `--blocked-by` an unknown id, or itself | refused | `::test_hold_refuses_bad_ids` |
| A8 | a store with scored and unscored items | `triage` | prints `unscored <n>: <ids>` naming exactly the unscored ones | `::test_triage_lists_unscored` |
| A9 | a multi-window store, a worker below the floor, only unscored items | `triage --apply` | nothing assigned | `::test_triage_skips_unscored` |
| A10 | a high/high item owned and open, another high/high unowned | `triage --apply` | the second is not assigned; the slot holder is named | `::test_one_major_in_flight` |
| A11 | a multi-window store, an unowned ready item | a builder runs `next` / `ready` | the item is not offered; the distributor's `next` offers it | `::test_builder_sees_own_items` |
| A12 | a single-window store | any agent runs `next` | unchanged behaviour (unowned items offered) | `::test_single_window_unchanged` |

## Phase B — the role

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
4. **D-rows:** D-471 narrowed; D-442 narrowed (in a multi-window repo a builder claims what the coordinator
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

## Phase C — the hub handover, then Finish

Appetite: 75

Surface: `CLAUDE.md`, `docs/reference/agents/infra.md`, `docs/reference/multi-agent-operating-model.md`,
`.fabrik/work/config.json`, `.fabrik/beat-owners.json`, `docs/DECISIONS.md`, `CHANGELOG.md`.

1. **Mirrors (spec § Contract deltas):** `CLAUDE.md` § Shared repo and § EXIT ("infra (the merge owner)" →
   the coordinator; infra joins the worktree agents), § Autonomy (the coordinator cause);
   `docs/reference/agents/infra.md` (merge owner and distributor removed, builder in
   `.claude/worktrees/infra`); `docs/reference/multi-agent-operating-model.md` § Ownership surfaces, § Hub vs
   project and § Claim or assign.
2. **Flips:** `.fabrik/work/config.json` `distributor: coordinator`, `queue_floor: 1`; `.fabrik/beat-owners.json`
   topics `merge request` and `work item` → `coordinator` (`check_beat_owners.py` validates against
   `HUB_BEATS`, which Phase B extended).
3. **The row:** `supersedes D-453: MERGE OWNER: coordinator` (`decisions.py --merge-owner` resolves it).
4. **Commit and push** steps 1–3 together, CHANGELOG entry included; then infra moves itself into
   `.claude/worktrees/infra` (`EnterWorktree`). The operator starts the coordinator window with the charter's
   launch line; its first assignment is D5.
5. **Finish:** the whole-plan `/fabrik-review` (D7 floor) over Phases A–C, one receipt; fixes it finds land
   from infra's worktree as a merge request to the coordinator.

### Behavior Contract — Phase C

| # | Given | When | Then | Test |
|---|---|---|---|---|
| C1 | the committed row | `decisions.py --merge-owner .` | prints `coordinator` | executed in § Evidence |
| C2 | the committed config | `work.py triage` as `coordinator` | runs as the distributor; as `infra`, `triage --apply` is refused | executed in § Evidence |
| C3 | the map | `check_beat_owners.py` | passes with `coordinator` owners | executed in § Evidence |

## File Scope (owned paths)

- `scripts/work.py`, `tests/test_work_coordinator.py`
- `scripts/mail.py`, `.claude/hooks/mail_notify.py`, `scripts/command_run.py`, `scripts/sysadmin/quota_dashboard.py`
- `tests/test_quota_dashboard.py`, `tests/test_mail_addressing.py`
- `docs/reference/agents/coordinator.md`, `docs/reference/agents/infra.md`, `docs/reference/multi-agent-operating-model.md`, `docs/reference/work-tracking.md`
- `templates/governance/CLAUDE.md`, `CLAUDE.md`
- `.fabrik/work/config.json`, `.fabrik/beat-owners.json`
- `docs/DECISIONS.md`, `CHANGELOG.md`, `INDEX.md`, `docs/development/plans/2026-10-15-plan-1-coordinator-role.md`

## Coverage Checklist

| Spec item | Plan (phase · step, or Behavior Contract row) |
|---|---|
| D1 where the role runs | B · step 3 (fleet carrier); C · steps 1–4 (hub) |
| D2 model | B · step 2 (launch line, by alias) |
| D3 jobs 1, 4, 5, 6, 7, **Never**, escalation | B · steps 2–3 — the agent's behaviour, carried by the charter and the template |
| D3 job 2, D4 | A · step 1; rows A1–A5 |
| D3 job 3 | A · steps 2–4; rows A6–A12; C · step 2 (`queue_floor: 1`) |
| D5 | § Decisions taken here (batch check); C · step 4 (first assignment) |
| Contract deltas: work item | A · step 1; row A8 |
| Contract deltas: assignment (D-442) | A · step 4; B · step 4 |
| Contract deltas: beat lists before the row | B · step 1 (rows B1–B3), then C · step 3 |
| Contract deltas: merge owner, distributor | C · steps 2–3 (rows C1, C2) |
| Contract deltas: identity | B · step 2 (row B4); C · step 4 |
| Contract deltas: mirrors | C · step 1 |
| Contract deltas: fleet carrier | B · step 3 |

## Evidence

Filled at execution (the `/fabrik-execute-plan` contract): per phase, the gate's JSON status line and the
commands named in the Behavior Contract tables, with their output.

## Self-audit

- Every spec delta and P5-1..P5-7 maps to a step (Coverage Checklist, Intake Inventory).
- Nothing from § Recorded, not applied is planned.
- The order constraint (lists before the row) is Phase B before Phase C.

## Residual unknowns

None that block execution: the launch is the operator's act and the gap is safe (§ Decisions taken here).

## Pass Ledger

| Pass | seats · axes re-checked | counters | method | plan md5 (start → end) |
|-----:|---|---|---|---|
