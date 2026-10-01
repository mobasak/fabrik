# Plan — /fabrik-task carries feature-sized work; the spec chain is for modules

Status: DRAFT
**Owner:** infra
Spec: docs/superpowers/specs/2026-10-02-fabrik-task-feature-lane-design.md
Date: 2026-10-02

Built from Revision 2 of the spec, CONVERGED (D-491), whose design the operator approved: *"approved"* (D-492).
A spec-fed delta plan: each ticket cites the spec section it implements and restates nothing that section settles.

## What we already agreed

- The goal, the personas and the module test — spec § Goal; § Personas; § The delta D1.
- Heavy surfaces in the lane with the full review (D2); multi-commit closes, Behaviours ≤ 7, undeclared-path refusal with `--design-amend` (D3); appetite (D4); independent slices are several runs (D6).
- Revision 2: sync paths enter the hub lane (D7); the in-lane review stops at the first own-fix-only round (D8); `--why`, the refusal ledger and DOWNGRADE (D9); `Size: small` at spec time with plan-review holding the gate (D10, superseding D5); `Appetite:` per plan phase (D11); fixture-first, staged rollout behind `.fabrik/lane.json` (D12).
- Rejected: everything in spec § Rejected alternatives.
- Decided HERE, from the grounding (no new operator question):
  - The lane logic is ONE new module, `scripts/task_lane.py`, built in three serialized tickets (T02 admission, T03 close, T04 the review stop). `scripts/command_run.py` is 276,817 bytes, above a ticket's READ budget, so only the integration ticket T08 touches it and wires the module in.
  - The plan graders (T05a) and the four command sources (T05b, T05c) are independent of the module and run in parallel with it.
  - The routed residuals land as acceptance lines: W-0a89f069 (the receipt's real command, `handoff --review`, the receipt commit outside `--commit`) in T03; W-25318990 (the `lane.json` changer echo in T02 and T08, the pin count in T06, `--surface` on review starts in T08, the `phases` name in T06).
  - The template's lane rows and the `_LANE_DEFAULT` flip are NOT in this plan: they are the day-7 commit D12 gates on its criterion, filed by T08 as a work item.

## Ticket Board

| Ticket | Title | Depends | Parallel | State | Commit |
|---|---|---|---|---|---|
| T01 | The replay fixture, pinned before any gate code | — | ⚡ | ⬜ | |
| T02 | task_lane.py admission: the module test, the switch, the refusal ledger | T01 | ⛓️ | ⬜ | |
| T03 | task_lane.py close: re-checks, the refusal, multi-commit, the review receipt | T02 | ⛓️ | ⬜ | |
| T04 | The in-lane review stops hunting at the first own-fix-only round | T03 | ⛓️ | ⬜ | |
| T05a | Plan graders: Appetite per phase and the Size-small spec rule | — | ⚡ | ⬜ | |
| T05b | The spec and plan commands: size at spec time, DOWNGRADE, no false approval | — | ⚡ | ⬜ | |
| T05c | Plan review holds the small-spec gate; execute-plan shows phase appetite | — | ⚡ | ⬜ | |
| T06 | The feedback report reads the lane's new fields | T03 | ⛓️ | ⬜ | |
| T07 | /fabrik-task's own text and the run-record protocol | T03 | ⛓️ | ⬜ | |
| T08 | Integration: wire task_lane into command_run.py, the hub lane table, distribution, hub opt-in | T04, T05a, T05b, T05c, T06, T07 | ⛓️ | ⬜ | |

## Merge Order

1. T01
2. T02
3. T03
4. T04
5. T05a
6. T05b
7. T05c
8. T06
9. T07
10. T08

The fixture first (T01, red by construction), then the module in three serialized tickets on one file (T02, T03, T04); the plan graders and
command sources (T05a, T05b, T05c) are unconnected to the module and may merge at any point before T08; the report (T06) and the lane's own
text (T07) read T03's field names; the integration last (T08). No two Depends-unconnected tickets share a path.

## Interfaces

- **T01 → T02 — the replay fixture `tests/fixtures/lane_replay.json` and its verdict names.** Seam test: `tests/test_lane_replay.py` (T01) calls T02's classifier; T02's gate runs it.
- **T02/T03 → T08 — `task_lane.admit`, `lane_version`, `record_refusal`, `measure_close`, `check_review_receipt`.** Seam test: `tests/test_command_run_fabrik_task.py` (T08) drives the real `command_run.py start`/`done` against fixture repos, never a stubbed module.
- **T03 → T04 — the `**Lane:** fabrik-task` receipt line written by `review_receipt.py --lane`.** Seam test: `tests/test_task_lane_review_stop.py` (T04) reads receipts written by T03's code.
- **T03 → T06, T07 — the feedback field names (`design_amends`, `loc_added`, `over_appetite`, `upgrade`).** Seam: T06's fixture rows use those names verbatim; T07's protocol doc lists them.

## Constraints Digest

| Rule (verbatim) | file:line | Pack |
|---|---|---|
| **`uv`** is the mandated Python package manager. Never use raw `pip`, `pip install`, `poetry`, or `pipenv`. | `.windsurf/rules/core/10-python.md:22` | core/10-python — every ticket's test runs under the repo `.venv` |
| Anything that must SURVIVE a restart is not temp: it goes on a **named | `.windsurf/rules/core/10-python.md:153` | core/10-python — the refusal ledger lives beside the state dir, never `/tmp` |
| **Behavior Contract**: every ticket enumerates its distinct **user-observable behaviors / acceptance criteria** and tests **each one** | `.windsurf/rules/core/45-testing-strategy.md:20` | core/45-testing-strategy — one test per G/W/T row |
| **Watched-fail-first** (for tests this change adds or modifies; trivia stays skipped per the Behavior Contract): a non-trivial behavior's test proves something only if it has been SEEN RED | `.windsurf/rules/core/45-testing-strategy.md:22` | core/45-testing-strategy — D12's red-first rule |
| **Fenced code blocks only** — never indented code (AI treats it inconsistently) | `.windsurf/rules/core/40-documentation.md:243` | core/40-documentation — T07's docs |

## Execution Discipline (binding on /fabrik-execute-plan)

- **Review floor** — every ticket, on the coder's return, runs the full `/fabrik-review` on its changed surface to a
  coverage-adjudicated exit BEFORE its merge: `scripts/command_run.py`, `scripts/task_lane.py` (synced CORE_SCRIPTS from T08),
  `scripts/enforcement/check_*`, `.pre-commit-config.yaml` and `CLAUDE.md` are governance-sync or never-route paths and the operator named this work.
  A plumbing commit is followed by a hand-run `bash scripts/governance_sync_postcommit.sh`.
- **Dispatch policy** — native Claude seats (the pool is OFF, D-181/D-182): `dispatch_headroom.py` then
  `python3 scripts/command_run.py dispatch --seats N` before each fan-out. Coders: Opus for T01–T04, T05a, T06 (`native`) and
  T05b, T05c, T07 (`never-route` — command text); T08 is the orchestrator's, in the main checkout. Haiku never codes.
- **Seat probes** — any seat that builds a scratch git repo sets `GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1` and
  runs `git init -b master`; seats never read `$HOME/.claude*` or `~/.claude-fleet` and never write under `/opt`.
  T01's capture of the 20 task rows is the orchestrator's (the feedback ledger lives under `$HOME`); the coder receives them as a file.
- **Red first (D12)** — every ticket's tests are committed and seen RED before its code; T01's red run is its own evidence.
- **Commands** — `commands/` is rendered only from the main master checkout: render → `--check` → commit, in T08.
- **Parallelism + merge** — T01 → T02 → T03 → T04 serialized (one module); T05a, T05b, T05c in parallel with them; T06 and T07 after T03;
  T08 last. Every merge happens in the main checkout in § Merge Order through `merge_request.py merge`.
- **Shared-file gates** — T02's merge re-runs T01's `tests/test_lane_replay.py` (now green), T03's merge re-runs T02's gate and T04's re-runs T03's (one module); T08's gate is the full lane test set plus `final_gate.py --check --json`.
- **Appetite (D11, dogfooded)** — each ticket's `Appetite:` is minutes; a ticket past 2× is re-planned, not pushed through.
- **Ids** — every D-row this plan mints uses `python3 scripts/decisions.py --reserve-id .`.

## Behavior Contract

- **Given** the capture script run against `/opt/fabrik` at `c84f0b0b7` and the four project repos, **When** the fixture is written, **Then** it holds exactly 300 hub commits and 62/62/86/97 non-docs-only project commits with their status letters from `-M -C` (spec § What exists today item 7)
- **Given** the fixture, **When** `tests/test_lane_replay.py` runs before T02, **Then** it fails on the missing classifier, never on the data (spec § The delta D12 (1))
- **Given** the wef1 commit in the fixture, **When** its pinned verdict is read, **Then** it is `lane` (admitted), and the two non-file historical handoffs are pinned `chain` and `seat` as before (spec § Validation V0)
- **Given** a v2 repo and a feature declaring 6 existing files and 2 new source files, no contract path, `oneway=no`, `tradeoffs=no`, appetite 120, **When** `admit` runs, **Then** the verdict is `lane` (spec § Validation V1)
- **Given** a declared file `specs/services/x.yaml`, or `api/openapi.yaml`, or `web/x.schema.json`, **When** `admit` runs, **Then** the verdict is `chain: contract`; the same names under `node_modules/` are ignored (spec § The delta D1)
- **Given** `tradeoffs=yes` or `oneway=yes` without `--why`, **When** `admit` runs, **Then** it refuses naming the missing reason; with `--why`, the verdict is `chain` and a refusal row with an id, the git common dir, the declared keys, `--why` and the `--file` list is appended to the ledger (spec § The delta D9; § Validation V9)
- **Given** appetite 300, **When** `admit` runs, **Then** the verdict is `chain: appetite` (spec § The delta D1)
- **Given** a hub-v2 repo and a declared governance-sync path, **When** `admit` runs, **Then** the verdict is `lane: full-review`; in a v1 repo the verdict is today's `right-now + /fabrik-review` (spec § The delta D7)
- **Given** no `.fabrik/lane.json`, **When** `lane_version` runs, **Then** it returns 1 (`_LANE_DEFAULT`); with `{"version": 2}` it returns 2 and the commit that set it (spec § The delta D12; W-25318990)
- **Given** the T01 fixture, **When** `tests/test_lane_replay.py` runs, **Then** every pinned verdict matches (spec § Validation V0)
- **Given** a v2 record whose commits add 3 new non-test source files, one of them a copy (`C`), **When** `measure_close` runs, **Then** it records `upgrade: new-source` and requires a full-review receipt (spec § Validation V2)
- **Given** a v2 record declared `consumers=internal` whose commit touches `specs/services/x.yaml` that a Doc Sync exclusion would hide, **When** `measure_close` runs, **Then** the hit is found and `done` needs a full-review receipt (spec § Validation V3)
- **Given** a committed path named in neither the design nor an amendment, **When** `measure_close` runs for a v2 record, **Then** it refuses; after `--design-amend` naming it, it passes and records `design_amends: 1` with the path; for a v1 record the same path is recorded as `oversized_mini`, never refused (spec § Validation V4; § The delta D3.3; § Lifecycle)
- **Given** a design with 8 Behaviours, **When** `measure_close` runs, **Then** it records `upgrade: behaviours` (spec § Validation V5)
- **Given** two commits where the first renames a declared file and the second edits the new name, **When** `measure_close` runs, **Then** the edit counts as declared and no other session's commit is read (spec § The delta D3.2)
- **Given** a receipt outside `docs/development/reviews/`, failing coverage, carrying `/fabrik-review-scoped`, or without the last commit as its range tip, **When** `check_review_receipt` runs, **Then** each is refused; a valid one passes, and the receipt's own commit is not in the `--commit` list (spec § The delta D1 checks (a)–(d); W-0a89f069)
- **Given** `review_receipt.py --command /fabrik-review-scoped --lane`, **When** the receipt is written, **Then** its `**Command:**` line carries the real command and a `**Lane:** fabrik-task` line is present (W-0a89f069)
- **Given** a v2 record with appetite 60 closing after 130 minutes, **When** `measure_close` runs, **Then** it records `over_appetite: true` and returns the UPGRADE line to print (spec § Validation V6)
- **Given** a review record whose parent is `fabrik-task` and whose round 2 confirms only own-fix defects, **When** the advisory runs, **Then** it prints the stop; with no `fabrik-task` parent it stays silent until round 3 (spec § Validation V8)
- **Given** a receipt with `**Lane:** fabrik-task` whose last own-fix-only round is followed by a quiet closing row, **When** `check_review_coverage.py` runs, **Then** it passes; the same receipt without the `**Lane:**` line keeps today's two-round rule (spec § The delta D8)
- **Given** the rendered scope-growth fragment, **When** it is read, **Then** it names the lane variant and that the review still closes only on a confirmed-zero pass (spec § The delta D8; D-355)
- **Given** a plan dated on or after the rollout date with one phase lacking `Appetite:`, **When** the graders run, **Then** they refuse it naming the phase; a plan dated before is not refused (spec § Validation V10; § The delta D11)
- **Given** a `Profile: small` plan whose spec is `Status: DRAFT` without `Size: small`, **When** the graders run, **Then** they refuse it; with `Size: small` they pass (spec § The delta D10)
- **Given** a lane refusal whose `--file` list overlaps a new brief with one reversible decision, **When** `/fabrik-spec` Phase 0 is read, **Then** it orders the DOWNGRADE handoff naming the refusal id and the `/fabrik-task --from-downgrade` restart (spec § The delta D9)
- **Given** a spec whose deltas estimate ≤ ~400 code lines and ≤ 5 code files, **When** `/fabrik-spec` Phase 5 is read, **Then** it writes `Size: small` and hands the spec straight to `/fabrik-plan-after-chat` (spec § The delta D10)
- **Given** a `Size: small` spec, **When** `/fabrik-plan-after-chat` reaches its approval-row step, **Then** it does not mint an approval row (spec § The delta D10)
- **Given** any plan, **When** `/fabrik-plan-after-chat`'s emit rule is read, **Then** every phase or ticket carries `Appetite: <minutes>` (spec § The delta D11)
- **Given** a `Size: small` spec, **When** `/fabrik-plan-review` converges, **Then** it flips the spec and the plan to CONVERGED, mints the approval row, and ends at the design-approval gate instead of auto-handing off (spec § The delta D10)
- **Given** a plan phase with `Appetite: 60`, **When** `/fabrik-execute-plan` enters and finishes it, **Then** the phase marker reads `elapsed <m>/60`, and past 120 minutes the re-plan order is printed (spec § The delta D11)
- **Given** fixture rows and a refusal ledger, **When** `command_feedback_report.py --lane` runs, **Then** it prints per agent the refused and downgraded shares, and the task-to-spec ratio excludes downgraded spec runs (spec § The delta D9)
- **Given** review rows with and without `parent: fabrik-task`, **When** the report runs, **Then** the in-lane full-review median uses only the former (spec § Validation)
- **Given** a spec row with `size: small` and later review rows whose `surface` starts with that spec path, **When** the report runs, **Then** it counts the spec as sent back to spec-review only when a spec-review row follows (spec § Validation kill rules; W-25318990)
- **Given** execute-plan rows carrying `over_appetite_phases` and `phase_marks`, **When** the report runs, **Then** it prints the over-appetite share without reading the declared `phases` field (W-25318990)
- **Given** the rendered `/fabrik-task`, **When** it is read, **Then** it names the Behaviours list with its cap of 7, multi-commit closes, `--design-amend`, the refusal of undeclared paths, the full review for heavy and sync surfaces, and the four new UPGRADE tokens (spec § The delta D3, D7)
- **Given** `docs/reference/command-run-protocol.md`, **When** it is read, **Then** every new flag and field (`consumers`, `--appetite`, `--why`, `--from-downgrade`, `--design-amend`, `--review`, `gate`/`lane`, `design_amends`, `loc_added`, `over_appetite`, `parent`, `size`, `over_appetite_phases`, `phase_marks`) is documented (spec § Contract deltas)
- **Given** the 2026-09-17 lane spec, **When** its header is read, **Then** it carries a SUPERSEDED-IN-PART banner pointing to this spec (spec § Documentation landing sites)
- **Given** a repo with no `.fabrik/lane.json`, **When** `command_run.py start --command fabrik-task` and `done` run, **Then** they behave exactly as before this plan and `start` prints `lane: v1` (spec § The delta D12 OFF-state grader)
- **Given** the hub with `.fabrik/lane.json` `{"version": 2}`, **When** a 6-file feature starts, **Then** it is admitted and `start` prints `lane: v2` and the commit that set the switch (spec § Validation V1; W-25318990)
- **Given** the manifest and the governance-sync regex, **When** they are read, **Then** `scripts/task_lane.py` is in both and `.fabrik/lane.json` is in neither (spec § The delta D12)
- **Given** the hub `CLAUDE.md`, **When** the lane table is read, **Then** row 5 is the module tests, rows 1 and 1b send sync and heavy work into the lane with the full review, and every UNIVERSAL anchor is still present (spec § Contract deltas)
- **Given** an execute-plan record whose phase 2 declared `--appetite 30` and ran 70 minutes, **When** the run closes, **Then** the feedback row carries `over_appetite_phases: 1` and `phase_marks`, and `line` printed the re-plan order past 60 minutes (spec § Validation V10)
- **Given** a `/fabrik-spec-review` or `/fabrik-plan-review` `start` without `--surface`, **When** it runs, **Then** it is refused naming the flag, so every review row carries the spec path the D10 kill rule joins on (W-25318990)
- **Given** a `/fabrik-task` started with `--from-downgrade <id>`, **When** it closes, **Then** its feedback row carries that refusal id, and a nested review's row carries `parent: fabrik-task` (spec § Validation kill rules; § The delta D8)
- **Given** every ticket merged, **When** the T01 replay test and the full lane test files run, **Then** all pass, and the next real hub `/fabrik-task` run closes under `lane: v2` (spec § Validation V0)

## Global Constraints

- Never-Route: CLAUDE.md
- Never-Route: commands/_sources/
- Never-Route: .pre-commit-config.yaml
- The template's lane rows (`templates/governance/CLAUDE.md`) and `_LANE_DEFAULT` stay unchanged in this plan (spec § The delta D12).
- `.fabrik/lane.json` is repo-owned: never in the synced manifest, never in the sync filter.
- Shared tree: sibling WIP is never staged, reverted or stashed; ledger rows go through the private-index recipe in ONE shell.
- fabrik-lib and Volkan's port are sync-excluded: their adoption is a mail at the day-7 flip, never an edit.

## Context Ledger

- Spec: `docs/superpowers/specs/2026-10-02-fabrik-task-feature-lane-design.md` (Revision 2 CONVERGED D-491; approved D-492).
- Superseded in part: `docs/superpowers/specs/2026-09-17-fabrik-task-lane-design.md`.
- Proposal: web-ecommerce-factory 01M3WJMF.
- Routed residuals: W-0a89f069, W-25318990.

## File Scope (owned paths)

- .fabrik/lane.json
- .pre-commit-config.yaml
- CLAUDE.md
- commands/_fragments/scope-growth-exit.md
- commands/_sources/fabrik-execute-plan.md
- commands/_sources/fabrik-plan-after-chat.md
- commands/_sources/fabrik-plan-review.md
- commands/_sources/fabrik-spec.md
- commands/_sources/fabrik-task.md
- docs/development/reviews/2026-10-02-plan-1-fabrik-task-feature-lane-review.md
- docs/reference/command-run-protocol.md
- docs/superpowers/specs/2026-09-17-fabrik-task-lane-design.md
- scripts/command_feedback_report.py
- scripts/command_run.py
- scripts/enforcement/check_plan_quality.py
- scripts/enforcement/check_plan_tickets.py
- scripts/enforcement/check_review_coverage.py
- scripts/fabrik_synced_manifest.py
- scripts/lane_replay_capture.py
- scripts/review_receipt.py
- scripts/task_lane.py
- tests/fixtures/lane_replay.json
- tests/test_command_feedback_report_lane.py
- tests/test_command_run_fabrik_task.py
- tests/test_fabrik_task_source.py
- tests/test_lane_replay.py
- tests/test_lane_switch_not_synced.py
- tests/test_plan_appetite_size.py
- tests/test_plan_review_small_gate.py
- tests/test_task_lane_admission.py
- tests/test_task_lane_close.py
- tests/test_task_lane_review_stop.py

## Evidence

Grounding run 2026-10-02 in `/opt/fabrik` at aa7f1ac20 (every cite below resolved there by `sed -n`).

- Cite points: `scripts/command_run.py:84` (`_state_dir`), `:429`/`:435` (`SCOPE_GROWTH_ROUNDS`/`_QUALIFY`), `:473` (`scope_growth_warning`), `:2706-2713` (handoff `--resume`), `:2809` (`_TASK_MAX_FILES = 3`), `:3019` (`_task_size_gate`), `:3178-3192` (the file-count refusal), `:3216-3297` (the exclusion set), `:3363` (`--name-status -M -C`), `:3519-3541` (rename carry), `:3571-3572` (`oversized_mini`), `:3752-3759` (the record stack), `:4932` (`phases`); `scripts/enforcement/check_review_coverage.py:400` (`_OWN_FIX_ROUNDS_FOR_STOP = 2`), `:491-493`; `scripts/enforcement/check_plan_tickets.py:241` (`PROFILE_RE`); `scripts/review_receipt.py:138` (hard-coded `/fabrik-review`); `scripts/command_feedback_report.py:82`, `:1374`; `scripts/fabrik_synced_manifest.py:37`; `.pre-commit-config.yaml:164`; `commands/_sources/fabrik-spec.md:324-325`, `:326-339`; `fabrik-plan-after-chat.md:52-55`, `:210-222`; `fabrik-plan-review.md:17`; `fabrik-spec-review.md:280-294`; `fabrik-execute-plan.md:389-438`, `:527-529`; `fabrik-task.md:56`, `:78`, `:110-111`, `:113`.
- READ-budget sizing of the largest touched files (bytes):

```text
276817 scripts/command_run.py            (T08 only — the orchestrator's)
185145 scripts/enforcement/check_review_coverage.py
145850 scripts/enforcement/check_plan_tickets.py
103422 CLAUDE.md
102718 commands/_sources/fabrik-execute-plan.md
101654 scripts/command_feedback_report.py
 69381 commands/_sources/fabrik-plan-after-chat.md
```

## Self-audit

- Every ticket cites the spec section it implements; no ticket restates a settled design.
- Every Validation row lands in a ticket: V0 T01, T02, T08 · V1 T02, T08 · V2 T03 · V3 T03 · V4 T03 · V5 T03 · V6 T03 · V7 T02 · V8 T04 · V9 T02, T05b · V10 T05a, T05c, T08 · D10 T05a, T05b, T05c · the kill-rule joins T06, T08.
- Every routed residual is an acceptance line: W-0a89f069 T03 · W-25318990 T02, T06, T08.
- `CLAUDE.md` is T08's; `INDEX.md`, CHANGELOG and DECISIONS are in no Touches — their rows are the orchestrator's (T08 lists `INDEX.md` in Context Files).

## Coverage Checklist

Armed at execution by `python scripts/review_rubric.py --changed <the File Scope paths>`; each ticket's finder brief carries its slice of it.

## Pass Ledger

| Pass | seats · axes re-checked | counters | method | plan md5 (start → end) |
|---|---|---|---|---|

## Residual unknowns

- U1 — whether the day-7 hub week shows a refusal the fixture did not predict: answered by the D12 criterion at the flip, not by this plan.
