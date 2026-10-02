# Plan — /fabrik-task carries feature-sized work; the spec chain is for modules

Status: IN-PROGRESS
**Owner:** infra
Spec: docs/superpowers/specs/2026-10-02-fabrik-task-feature-lane-design.md
Date: 2026-10-02

Built from Revision 2 of the spec, CONVERGED (D-491), whose design the operator approved: *"approved"* (D-492). Plan CONVERGED by `/fabrik-plan-review` (D-495).
A spec-fed delta plan: each ticket cites the spec section it implements and restates nothing that section settles.

## What we already agreed

- The goal, the personas and the module test — spec § Goal; § Personas; § The delta D1.
- Heavy surfaces in the lane with the full review (D2); multi-commit closes, Behaviours ≤ 7, undeclared-path refusal with `--design-amend` (D3); appetite (D4); independent slices are several runs (D6).
- Revision 2: sync paths enter the hub lane (D7); the in-lane review stops at the first own-fix-only round (D8); `--why`, the refusal ledger and DOWNGRADE (D9); `Size: small` at spec time with plan-review holding the gate (D10, superseding D5); `Appetite:` per plan phase (D11); fixture-first, staged rollout behind `.fabrik/lane.json` (D12).
- Rejected: everything in spec § Rejected alternatives.
- Decided HERE, from the grounding (no new operator question):
  - The lane logic is ONE new PURE module, `scripts/task_lane.py`, built in four serialized tickets (T02 admission, T03a the close measurement, T03b the receipt, T04 the review stop). It never imports `scripts/command_run.py` — 276,817 bytes, above a ticket's READ budget — so every fact that file owns (the sync hits, the state dir, the exclusion set, the record stack) enters as an argument, and only the integration ticket T08 touches `command_run.py` and maps them in (§ Interfaces pins the API).
  - The rollout constant both plan graders need lives in a new `scripts/enforcement/plan_appetite.py` (`LANE_ROLLOUT_DATE = "2026-10-03"`), so neither grader imports the other.
  - The `--surface` refusal on spec-review and plan-review starts applies at lane v2 only, so a repo without `.fabrik/lane.json` behaves exactly as today (D12).
  - A v2 record is one stamped `gate: 2` at `start`; an unstamped record keeps today's close (spec § Lifecycle).
  - The plan graders (T05a) and the four command sources (T05b, T05c) are independent of the module and run in parallel with it.
  - The routed residuals land as acceptance lines: W-0a89f069 (the receipt's real command in T03b; `handoff --review` and the receipt commit outside `--commit` in T03a and T08); W-25318990 (the `lane.json` changer echo in T02 and T08, the pin count in T06, `--surface` on review starts in T08, the `phases` name in T06).
  - The template's lane rows and the `_LANE_DEFAULT` flip are NOT in this plan: they are the day-7 commit D12 gates on its criterion, filed by T08 as a work item.

## Ticket Board

| Ticket | Title | Depends | Parallel | State | Commit |
|---|---|---|---|---|---|
| T01 | The replay fixture, pinned before any gate code | — | ⚡ | ✅ | squash of worktree-agent-ad5af92a95a1b16fa |
| T02 | task_lane.py admission: the module test, the switch, the refusal ledger, the replay | T01 | ⛓️ | ✅ | squash of worktree-agent-a7202d6507f63bf60 |
| T03a | task_lane.py close: the per-commit measurement and its refusals | T02 | ⛓️ | ✅ | squash of worktree-agent-ac91db68cafca62c4 |
| T03b | The close's review receipt: the real command, the lane marker, checks (a)–(d) | T03a | ⛓️ | ✅ | squash of worktree-agent-a379f1f87ad60b5c6 |
| T04 | The in-lane review stops hunting at the first own-fix-only round | T03b | ⛓️ | ✅ | squash of worktree-agent-a2a01fcb66a468b21 |
| T05a | Plan graders: Appetite per phase and the Size-small spec rule | — | ⚡ | ✅ | squash of worktree-agent-a749e8b44ee6b8c13 |
| T05b | The spec and plan commands: size at spec time, DOWNGRADE, no false approval | — | ⚡ | ✅ | squash of worktree-agent-a5bd5c37407d40e54 |
| T05c | Plan review holds the small-spec gate; execute-plan passes phase appetite | — | ⚡ | ✅ | squash of worktree-agent-a90fb4ec43ca7029e |
| T06 | The feedback report reads the lane's new fields | T03b | ⛓️ | ✅ | squash of worktree-agent-a1b58998b8da3489e |
| T07 | /fabrik-task's own text and the run-record protocol | T03b | ⛓️ | ✅ | squash of worktree-agent-ab6f1cab1615f043e |
| T08 | Integration: wire task_lane into command_run.py, the hub lane table, distribution, hub opt-in | T04, T05a, T05b, T05c, T06, T07 | ⛓️ | ✅ | squash of lane-t08b |

## Merge Order

1. T01
2. T02
3. T03a
4. T03b
5. T04
6. T05a
7. T05b
8. T05c
9. T06
10. T07
11. T08

The fixture first (T01), then the module in four serialized tickets on one file (T02, T03a, T03b, T04); the plan graders and
command sources (T05a, T05b, T05c) are unconnected to the module and may merge at any point before T08; the report (T06) and the lane's own
text (T07) read the field names fixed below; the integration last (T08). No two Depends-unconnected tickets share a path.

## Interfaces

- **The `task_lane` API (introduced T02, T03a, T03b, T04; consumed by T08 and the replay test).** Pure functions — no import of `command_run.py`, no environment reads:
  - `lane_version(root: Path) -> tuple[int, str | None, str | None]` — (version, the commit that last set `.fabrik/lane.json` or `None`, a warning or `None`); `_LANE_DEFAULT = 1`.
  - `contract_hit(path: str) -> bool`, `is_new_source(status: str, path: str) -> bool`, `is_migration(path: str) -> bool` — the path helpers; `classify_commit`, `admit` and `measure_close` all call them, so admission, the replay and the close cannot disagree.
  - `admit(declared: dict[str, str], files: list[str], *, sync_hits: set[str], appetite: int | None, why: str | None, version: int) -> Verdict` — `Verdict(route: str, review: "scoped" | "full", reason: str)`; `route` is `lane`, `chain: contract|oneway|tradeoffs|appetite`, `refused` (naming the bad or missing input), or at version 1 today's routes verbatim — `chain: files` and the `right-now` routes.
  - `classify_commit(rows: list[tuple[str, str, str | None]], *, repo_kind: "hub" | "project", sync_regex: str) -> str` — rows are `(status, path, old_path)`; the verdict is one of `lane`, `lane: full-review`, `chain: contract`, `chain: new-source`.
  - `record_refusal(ledger: Path, row: dict) -> str` — appends one JSON line, returns the refusal id; T08 passes `_state_dir().parent / "lane-refusals.jsonl"`.
  - `LaneRecord` — `stamped: bool`, `files: list[str]`, `design_paths: list[str]`, `amendments: list[str]`, `behaviours: int`, `appetite: int`, `started_at: float` (required), `consumers: str`, `sync_hits: set[str]`, `in_worktree: bool` (a sync-path run in a linked worktree may commit several times, D7); T08 builds it from the run record.
  - `measure_close(rec: LaneRecord, commits: list[list[tuple[str, str, str | None]]], *, excluded: Callable[[str], bool], verb: "done" | "blocked" | "handoff", now: float, loc_added: int, receipt: str | None) -> CloseVerdict` — `CloseVerdict(refused: str | None, needs_full_review: bool, upgrade: list[str], design_amends: int, amended_paths: list[str], oversized_mini: list[str], loc_added: int, over_appetite: bool, findings: list[str])` — `upgrade` holds every token the close raised (`contract`, `new-source`, `behaviours`, `appetite`).
  - `check_review_receipt(path: Path, commits: list[str], *, root: Path) -> list[str]` — the refusal reasons, empty when (a)–(d) hold; T08 calls it when `done`/`handoff` carries `--review`, and `measure_close` receives the receipt path only to exempt it from the declaration check.
  - `scope_growth_rounds(stack: list[dict]) -> tuple[int, int]` — `(rounds, qualify)`.
- **Feedback field names (fixed here; T06 reads them, T07 documents them, T08 writes them):** `parent`, `size`, `from_downgrade`, `design_amends`, `loc_added`, `over_appetite`, `upgrade`, `upgrades`, `over_appetite_phases`, `phase_marks`. Every value is a string, as today's `fields: dict[str, str]` (`scripts/command_run.py:3604`): `upgrade` keeps today's SINGLE token — the evidence's `UPGRADE:` token when present (e.g. `sync`, which `command_feedback_report.py:1312` excludes by equality), else the first of `CloseVerdict.upgrade` in the order `contract`, `new-source`, `behaviours`, `appetite` — and `upgrades` carries every token the close raised, space-joined.
- **T01 → T02 — the replay fixture `tests/fixtures/lane_replay.json` with its expected verdicts.** Seam test: `tests/test_lane_replay.py`, in T02's (the consumer's) Touches and Gate.
- **T03b → T04 — the exact `**Lane:** fabrik-task` receipt line written by `review_receipt.py --lane`.** Seam test: `tests/test_task_lane_review_stop.py` (T04) writes its receipts with T03b's `review_receipt.py`.
- **T02–T04 → T08 — the API above.** Seam tests: `tests/test_command_run_fabrik_task.py` and `tests/test_command_run_lane_v2.py` (T08) drive the real `command_run.py start`/`step`/`line`/`round`/`done`/`handoff`/`blocked` against fixture repos, never a stubbed module.

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
  `python3 scripts/command_run.py dispatch --seats N` before each fan-out. Coders: Opus for T01, T02, T03a, T03b, T04, T05a, T06 (`native`) and
  T05b, T05c, T07 (`never-route` — command text); T08 is the orchestrator's, in the main checkout. Haiku never codes.
- **Seat probes** — any seat that builds a scratch git repo sets `GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1` and
  runs `git init -b master`; seats never read `$HOME/.claude*` or `~/.claude-fleet` and never write under `/opt`.
  T01's capture of the 20 task rows is the orchestrator's (the feedback ledger lives under `$HOME`); the coder receives them as a file.
- **Red first (D12)** — every ticket's tests are committed and seen RED before its code; T02's replay test is written against T01's fixture before `classify_commit` exists.
- **Commands** — `commands/` is rendered only from the main master checkout: render → `--check` → commit, in T08.
- **Parallelism + merge** — T01 → T02 → T03a → T03b → T04 serialized (one module); T05a, T05b, T05c in parallel with them; T06 and T07 after T03b;
  T08 last. Every merge happens in the main checkout in § Merge Order through `merge_request.py merge`.
- **Shared-file gates** — a ticket's own Gate names only its own test files; at each module ticket's MERGE the orchestrator additionally runs every lane test file that exists at that point — `python -m pytest tests/test_lane_replay.py tests/test_task_lane_admission.py tests/test_task_lane_close.py tests/test_task_lane_receipt.py tests/test_task_lane_review_stop.py -q`, trimmed to the files present — so a later ticket that breaks an earlier one's rule is red at its merge; T08's merge runs that full list plus T08's own Gate.
- **Commands render once** — T05b, T05c and T07 grade their sources with source-level tests and `tests/test_check_command_corpus.py`; `assemble_commands.py --check` compares against the installed corpus and is run only in T08, after the render.
- **Breadth advisory (`check_ticket_breadth.py`)** — T04 was split on it (the scope-growth fragment moved to T07, leaving T04 one fleet-synced checker plus the pure function it pins). KEPT, each with its reason: T02 (score 8) — its rows are the arms of ONE `admit` function, and a split puts half the routing table in each ticket; T03a (score 9) — its rules share the one per-commit walk of `measure_close`; T06 (score 6) — one `--lane` view over one ledger; T04 (score 5) — the checker's lane constant and the pure function are one invariant held by one lockstep test; T07 (score 5) — the command text, the fragment and the protocol doc describe the same contract and are graded by the same source tests; T08 (score 12) — the `Integration: true` ticket, the only one that may read `command_run.py`.
- **Appetite (D11, dogfooded)** — each ticket's `Appetite:` is minutes; a ticket past 2× is re-planned, not pushed through.
- **Ids** — every D-row this plan mints uses `python3 scripts/decisions.py --reserve-id .`.

## Behavior Contract

- **Given** the capture script run against `/opt/fabrik` ending at `c84f0b0b7` and the four project repos, **When** the fixture is written, **Then** it holds exactly 300 hub commits and each project repo's last 200 commits (tojlo-mail's 137, its whole history) with `-M -C` status letters, and `--check` re-derives the same rows (spec § What exists today item 7; § The delta D12 (1))
- **Given** the fixture, **When** each commit's expected verdict is read, **Then** it is one of the closed verdict set in the spine § Interfaces, the wef1 commit is `lane`, and the two historical handoffs not caused by the file count keep the verdicts they routed to (spec § Validation V0)
- **Given** version 2 and a feature declaring 6 existing files and 2 new source files, no contract path, `oneway=no`, `tradeoffs=no`, appetite 120, **When** `admit` runs, **Then** the route is `lane` with review `full` (more than 5 files selects the full review); with 4 files, review `scoped` (spec § Validation V1; § The delta D2)
- **Given** a declared `--file` `specs/services/x.yaml` (repo root — the Fabrik spec location), `api/openapi.yaml`, `api/openapi-v2.json` or `web/x.schema.json`, or `consumers=external`, **When** `admit` runs, **Then** the route is `chain: contract`; the same names under `node_modules/`, `.venv/` or `vendor/` path SEGMENTS are not hits, while `myvendor/` and `node_modules_old/` are NOT exclusions (`myvendor/openapi.yaml` is a hit), and `api/openapi.yml` (the spec lists `.json`/`.yaml` only), `apps/x/specs/services/y.yaml` and `x.schema.json.bak` are not hits; the basename patterns match case-INSENSITIVELY, so `api/OpenAPI.yaml` and `web/X.Schema.JSON` are hits; and `consumers=internal` never removes a hit (spec § The delta D1)
- **Given** `tradeoffs=yes` or `oneway=yes` without `--why`, **When** `admit` runs, **Then** it refuses naming the missing reason; with `--why`, the route is `chain` and `record_refusal` appends one row with an id, the git common dir, the declared keys, `--why` and the `--file` list to the ledger path it was given (spec § The delta D9; § Validation V9)
- **Given** appetite 240 or no appetite, **When** `admit` runs, **Then** it is admitted (default 240); 241 routes `chain: appetite`; 0, a negative or a non-integer value is refused naming the flag (spec § The delta D1, D4)
- **Given** version 2 and a declared path in the `sync_hits` set, or `heavy=yes`, or a migration path segment (`migrations/`, `alembic/versions/` at any depth), **When** `admit` runs, **Then** the route is `lane` with review `full`; at version 1 a sync hit or `heavy=yes` keeps today's `right-now + /fabrik-review` disposition and `decision=no` keeps today's `right-now + /fabrik-review-scoped` at both versions (spec § The delta D2, D7)
- **Given** no `.fabrik/lane.json`, **When** `lane_version` runs, **Then** it returns `(1, None, None)` from `_LANE_DEFAULT = 1`; with `{"version": 2}` committed it returns 2 and the commit that last set it; invalid JSON, an unknown version or a string version return 1 with a warning naming the file, and an uncommitted file returns its version with commit `None` (spec § The delta D12; W-25318990)
- **Given** T01's fixture, **When** `tests/test_lane_replay.py` runs `classify_commit` over every commit and `admit` over the 20 task rows, **Then** every pinned verdict matches — written and seen RED before `classify_commit` exists (spec § Validation V0; § The delta D12 (1))
- **Given** a stamped record whose commits add 3 new non-test, non-`.md` source files, one of them a copy (`C`), **When** `measure_close` runs, **Then** `upgrade` includes `new-source` and `needs_full_review` is true, and `classify_commit` on the same rows returns `chain: new-source` (spec § Validation V2)
- **Given** a stamped record declared `consumers=internal` whose commit touches `specs/services/x.yaml` that the `excluded` predicate would hide, **When** `measure_close` runs, **Then** `upgrade` includes `contract` and `needs_full_review` is true, and `classify_commit` on the same rows returns `chain: contract` (spec § Validation V3)
- **Given** a stamped record and a committed path named in neither the design nor an amendment, **When** `measure_close` runs for `done`, **Then** it refuses naming the path; after `--design-amend` names it, it passes with `design_amends: 1` and that path in `amended_paths`; for `blocked` or `handoff` the same path is recorded, never refused; the run's own receipt path is exempt (spec § Validation V4; § The delta D3.3)
- **Given** a design with 8 Behaviours, **When** `measure_close` runs, **Then** `upgrade` includes `behaviours`; with 7 it does not (spec § Validation V5)
- **Given** two commits where the first renames a declared file and the second edits the new name, **When** `measure_close` runs, **Then** the edit counts as declared; **Given** a record whose `sync_hits` is non-empty, **Then** more than one commit is refused, since a sync-path run commits once (spec § The delta D3.2, D7)
- **Given** a stamped record with appetite 60, **When** `measure_close` runs at 121 minutes, **Then** it records `over_appetite: true` and returns the UPGRADE line; at exactly 120 minutes it does not (spec § Validation V6)
- **Given** commits adding 801 lines, **When** `measure_close` runs, **Then** it records `loc_added: 801` and returns a `change:` finding, never a refusal; 800 returns no finding (spec § The delta D3.4)
- **Given** an UNSTAMPED record, **When** `measure_close` runs with two commits and an undeclared path, **Then** it measures the last commit only and lists the path in `oversized_mini`, never refused (spec § Lifecycle)
- **Given** a receipt outside `docs/development/reviews/`, one failing `check_review_coverage.py`, one whose command token is `/fabrik-review-scoped` (which starts with `/fabrik-review`), and one whose range tip is not the last commit, **When** `check_review_receipt` runs, **Then** each is refused with its own reason; a valid one passes (spec § The delta D1 checks (a)–(d))
- **Given** a range tip written as a short SHA of the last commit, **When** check (d) runs, **Then** it passes; a short SHA of an earlier commit is refused (spec § The delta D1 (d))
- **Given** `review_receipt.py --command /fabrik-review-scoped --lane`, **When** the receipt is written, **Then** its `**Command:**` line carries `/fabrik-review-scoped` and the exact line `**Lane:** fabrik-task` is present; `--command /fabrik-other` is refused; without `--command` the line stays `/fabrik-review` (W-0a89f069)
- **Given** a stack whose last entry is `{"command": "fabrik-task"}`, **When** `scope_growth_rounds` runs, **Then** it returns `(1, 1)`; for an empty stack, or one whose last entry is another command with `fabrik-task` deeper, it returns `(3, 2)` (spec § The delta D8)
- **Given** a receipt with the exact line `**Lane:** fabrik-task` whose round 2 confirms only own-fix defects followed by a quiet closing row, **When** `check_review_coverage.py` runs, **Then** it passes; the same receipt without that line, or with `**Lane:** fabrik-task-x`, keeps the two-round rule (spec § Validation V8)
- **Given** both constants, **When** the lockstep test runs, **Then** `_LANE_OWN_FIX_ROUNDS_FOR_STOP` equals `scope_growth_rounds([{"command": "fabrik-task"}])[1]` and `_OWN_FIX_ROUNDS_FOR_STOP` still equals `SCOPE_GROWTH_QUALIFY` (spec § The delta D8)
- **Given** a plan dated `2026-10-03` with one ticket lacking `Appetite:`, or carrying `Appetite: 0` or `Appetite: soon`, **When** the graders run, **Then** they refuse it naming the ticket; a plan dated `2026-10-02` is not refused (spec § Validation V10; § The delta D11)
- **Given** a `Profile: small` plan whose spec is `Status: DRAFT` without `Size: small`, **When** the graders run, **Then** they refuse it; with `Size: small` they pass; a `CONVERGED` spec passes either way (spec § The delta D10)
- **Given** the `/fabrik-spec` source, **When** Phase 0 is read, **Then** it orders the DOWNGRADE handoff with `--resume`, the refusal id in the reason and the `/fabrik-task --from-downgrade <id>` restart in the seed (spec § The delta D9)
- **Given** the `/fabrik-spec` source, **When** Phase 5 is read, **Then** it writes `Size: small` for a spec whose deltas estimate ≤ ~400 code lines and ≤ 5 code files and hands it straight to `/fabrik-plan-after-chat` (spec § The delta D10)
- **Given** the `/fabrik-plan-after-chat` source, **When** the approval-row step and the emit rule are read, **Then** a `Size: small` spec mints no approval row and every phase or ticket carries `Appetite: <minutes>` (spec § The delta D10, D11)
- **Given** the `/fabrik-plan-review` source, **When** its small-spec exception is read, **Then** it names `--surface` with the spec path, the joint loop, both flips, the approval row and the design-approval gate instead of the auto-handoff (spec § The delta D10)
- **Given** the `/fabrik-execute-plan` source, **When** § Execution Loop is read, **Then** each phase start passes `step --appetite <minutes>` and the phase marker reads `elapsed <m>/<appetite>` (spec § The delta D11)
- **Given** fixture rows and a refusal ledger, **When** `command_feedback_report.py --lane` runs, **Then** it prints per agent the refused and downgraded shares, and the task-to-spec ratio excludes downgraded spec runs (spec § The delta D9)
- **Given** task rows with durations, `upgrade` values and `from_downgrade` ids, **When** the report runs, **Then** it prints the task median, the UPGRADE share and the share of downgraded tasks that later upgraded (spec § Validation 30-day; kill rules)
- **Given** review rows with and without `parent: fabrik-task`, **When** the report runs, **Then** the in-lane full-review median uses only the former (spec § Validation 30-day)
- **Given** a spec row with `size: small`, a later `fabrik-spec-review` row whose `surface` contains that spec path, and a `fabrik-plan-review` row that does too, **When** the report runs, **Then** only the first counts as sent back to spec-review (spec § Validation kill rules; W-25318990)
- **Given** execute-plan rows carrying `over_appetite_phases` and `phase_marks`, **When** the report runs, **Then** it prints the over-appetite share without reading `phases`, and counts `lane.json` pins per repo (W-25318990)
- **Given** the `/fabrik-task` source, **When** it is read, **Then** it names the Behaviours list with its cap of 7, multi-commit closes and the single commit for a sync-path run, `--design-amend`, the refusal of undeclared paths, the full review for heavy and sync surfaces, and the four new UPGRADE tokens (spec § The delta D3, D7)
- **Given** `docs/reference/command-run-protocol.md`, **When** it is read, **Then** every flag and field named in this ticket's Scope is documented (spec § Contract deltas)
- **Given** the scope-growth fragment, **When** it is read, **Then** it names the lane variant and that the review still closes only on a confirmed-zero pass (spec § The delta D8; D-355)
- **Given** the 2026-09-17 lane spec, **When** its header is read, **Then** it carries a SUPERSEDED-IN-PART banner pointing to this spec (spec § Documentation landing sites)
- **Given** a repo with no `.fabrik/lane.json`, **When** `start`, `done`, `round` and a `fabrik-plan-review` `start` without `--surface` run, **Then** each behaves as before this plan, no `gate: 2` is stamped and `start` prints `lane: v1` (spec § The delta D12 OFF state)
- **Given** the hub with `.fabrik/lane.json` `{"version": 2}`, **When** a 6-file feature starts, **Then** it is admitted, stamped `gate: 2`, and `start` prints `lane: v2` and the commit that set the switch; `--why` with `tradeoffs=yes` writes a ledger row under the state dir's parent (spec § Validation V1, V9; W-25318990)
- **Given** a v2 record, **When** `done --commit A B` runs with an undeclared path, **Then** it is refused; after `step --phase 2 --design-amend <path>` it closes; a contract hit at close refuses `done` and `handoff` until `--review <receipt>` names a valid full-review receipt, and `blocked` closes without one (spec § Validation V2–V4; § The delta D1; W-0a89f069)
- **Given** a `/fabrik-review` record nested under a running `/fabrik-task`, **When** `round` records an own-fix-only round 2, **Then** the advisory prints the stop; the same rounds without the `fabrik-task` parent print nothing (spec § Validation V8)
- **Given** a `fabrik-task` started `--appetite 60` and an execute-plan phase started `step --appetite 30`, **When** `line` runs at 121 and 61 minutes, **Then** each prints elapsed/appetite and the re-plan order; the closes record `over_appetite` and `over_appetite_phases: 1` with `phase_marks` (spec § Validation V6, V10)
- **Given** a v2 repo, **When** `fabrik-spec-review` or `fabrik-plan-review` starts without `--surface`, **Then** it is refused naming the flag; a `fabrik-task` started `--from-downgrade <id>` closes with `from_downgrade: <id>`, its feedback row also carries `design_amends`, `loc_added`, the single-token `upgrade` and the space-joined `upgrades` from the close, and an evidence `UPGRADE: sync` still writes `upgrade: sync`, a `/fabrik-spec` close on a spec carrying `Size: small` writes `size: small`, and a nested review's row carries `parent: fabrik-task` (W-25318990; spec § Validation kill rules)
- **Given** the manifest, the governance-sync regex and the hub enable commit, **When** they are read, **Then** `scripts/task_lane.py` is in both, `.fabrik/lane.json` is in neither, and the enable commit's only path is `.fabrik/lane.json`, so it distributes nothing (spec § The delta D12)
- **Given** the hub `CLAUDE.md`, **When** the lane table is read, **Then** row 5 is the module tests, rows 1 and 1b send sync and heavy work into the lane with the full review, and every UNIVERSAL anchor is still present; **Given** every ticket merged, **Then** the lane test files pass and the next real hub `/fabrik-task` closes under `lane: v2` (spec § Contract deltas; § Validation V0)

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
- scripts/enforcement/plan_appetite.py
- scripts/fabrik_synced_manifest.py
- scripts/lane_replay_capture.py
- scripts/review_receipt.py
- scripts/task_lane.py
- tests/fixtures/lane_replay.json
- tests/fixtures/lane_replay_tasks.json
- tests/test_command_feedback_report_lane.py
- tests/test_command_run_fabrik_task.py
- tests/test_command_run_lane_v2.py
- tests/test_fabrik_task_source.py
- tests/test_lane_replay.py
- tests/test_lane_replay_capture.py
- tests/test_lane_switch_not_synced.py
- tests/test_plan_appetite_size.py
- tests/test_plan_review_small_gate.py
- tests/test_review_receipt.py
- tests/test_spec_plan_lane_text.py
- tests/test_task_lane_admission.py
- tests/test_task_lane_close.py
- tests/test_task_lane_receipt.py
- tests/test_task_lane_review_stop.py

## Evidence

Closing re-derivation (Pass 4), verbatim, at base 579096eb1:

```text
plan_quality files 12 findings []
full-path cites 33 unresolved 0
rollup True 47
filescope True
dead gates []
touched tests not in own gate []
✓ [plan_tickets] /opt/fabrik/docs/development/plans/2026-10-02-plan-1-fabrik-task-feature-lane: graded 11 ticket(s), 42 Touches path(s), 40 Context-Files entry(ies); READ budget measured against /opt/fabrik; 0 finding(s)
```

Grounding: every cite below re-resolved at 579096eb1 by `sed -n`.

- Cite points: `scripts/command_run.py:84` (`_state_dir`), `:429`/`:435` (`SCOPE_GROWTH_ROUNDS`/`_QUALIFY`), `:473` (`scope_growth_warning`), `:2706-2713` (handoff `--resume`), `:2809` (`_TASK_MAX_FILES = 3`), `:2898` (`_sync_filter_source`), `:3019` (`_task_size_gate`), `:3178-3192` (the file-count refusal), `:3216-3297` (the exclusion set), `:3363` (`--name-status -M -C`), `:3519-3541` (rename carry), `:3571-3572` (`oversized_mini`), `:3604` (`fields: dict[str, str]`), `:3752-3759` (the record stack), `:4932` (`phases`); `scripts/enforcement/check_review_coverage.py:400`, `:491-493`, `:3009-3040` (its CLI); `tests/test_check_review_coverage_scope_growth.py:202` (the twin lockstep); `scripts/enforcement/check_plan_tickets.py:241` (`PROFILE_RE`); `scripts/review_receipt.py:138`; `scripts/command_feedback_report.py:82`, `:1312` (the `sync` equality), `:1374`; `scripts/fabrik_synced_manifest.py:37`; `.pre-commit-config.yaml:164`; `commands/_sources/fabrik-spec.md:324-339`; `fabrik-plan-after-chat.md:52-55`, `:210-222`; `fabrik-plan-review.md:17`; `fabrik-spec-review.md:280-294`; `fabrik-execute-plan.md:389-438`, `:527-529`; `fabrik-task.md:56`, `:78`, `:110-111`, `:113`.
- READ-budget sizing of the largest touched files (bytes):

```text
276817 scripts/command_run.py            (T08 only — the Integration ticket)
185145 scripts/enforcement/check_review_coverage.py
145850 scripts/enforcement/check_plan_tickets.py
103422 CLAUDE.md
102718 commands/_sources/fabrik-execute-plan.md
101654 scripts/command_feedback_report.py
 69381 commands/_sources/fabrik-plan-after-chat.md
```

- Execution note (T02 review round 1, O3): T02's coder was authorised to edit `scripts/lane_replay_capture.py` and re-capture `tests/fixtures/lane_replay.json` (T01's files, already merged) so the test-path rule lives in one helper in `task_lane.py`; recorded here because those paths are outside T02's Touches.

## Self-audit

- Every ticket cites the spec section it implements; no ticket restates a settled design.
- Every Validation row lands in a ticket: V0 T01, T02, T08 · V1 T02, T08 · V2 T03a, T08 · V3 T03a, T08 · V4 T03a, T08 · V5 T03a · V6 T03a, T08 · V7 T02 · V8 T04, T08 · V9 T02, T05b, T08 · V10 T05a, T05c, T08 · D10 T05a, T05b, T05c · the 30-day measures and kill-rule joins T06 (read), T08 (written) · D12's OFF state T08 · unstamped records T03a.
- Every routed residual is an acceptance line: W-0a89f069 T03b (the real command), T03a and T08 (`handoff --review`, the receipt outside `--commit`) · W-25318990 T02 (`lane.json` commit), T06 (pins, `phases` not reused, the `surface` join), T08 (`--surface` at v2, the echo).
- `CLAUDE.md` is T08's; `INDEX.md`, CHANGELOG and DECISIONS are in no Touches — their rows are the orchestrator's (T08 lists `INDEX.md` in Context Files).

## Coverage Checklist

Armed 2026-10-02 by running `python scripts/review_rubric.py --changed <the 32 File Scope paths>`: 4 FLOOR packs + 3 MATCHED packs, plus the four standing recurrence classes. Pasted output, verbatim (only the promote-to-check tail elided, declared in place):

```text
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
- > **⚠️ Bearer bypass scope — security-critical.** The bypass defaults to `^/api/`, which makes the **entire** `/api/*` surface public (un-2FA'd). If the application authenticates only a **sub-prefix** (e.g. `/api/v1` carries the bearer/internal-token check) while OTHER `/api/*` routes are unauthenticated (legacy / admin / destructive), you **MUST** narrow the bypass with `shape.bearer_bypass_prefix: "^/api/v1"` — otherwise `fabrik apply` exposes those routes to the public internet. **Bypass ONLY the path the app itself authenticates.** Value must start with `^/`; the verifier (`orchestrator/verifier.check_api_bypass`) probes the configured prefix on deploy. When unsure whether a service has un-auth'd `/api/*` routes, ask the app owner before relying on the `^/api/` default.

### core/25-data-postgres.md
| Vector search | pgvector on `postgres-main` + `fabrik-lib/rag` — ⚠️ the extension is NOT currently installed there (probed 2026-09-01: `postgres:16-alpine`, `plpgsql` only); a project needing vectors REQUESTS the fleet infra change first, never assumes it | same `postgres-main` DSN |
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
- VOLUME gets a plan pointed at a directory that never exists — a paper backup that reads green and archives nothing.  If the data is a volume, say so in the spec comment and rely on the global `docker-volumes` plan; never let a service-named plan be mistaken for the protection.
- health-enabled service can NEVER pass `up -d --wait` on a fresh database, and the deploy hangs to timeout.  An init the deploy cannot perform itself is a runbook step the plan MUST own.
- `fabrik redeploy <app>` SSHes to the VPS and runs `git pull` + `docker compose up -d --wait` against the **GitHub remote**, NOT the local `/opt/<app>` clone. Skipping `git push` redeploys the previous remote commit — the VPS never sees local changes.
**Mandate:** build → release → run are strictly separated. Releases are IMMUTABLE; the git SHA is the release ID. NEVER hot‑patch a running container (no `docker exec` to edit code/config in place, no in‑place code mutation on the VPS). Any change = a new build + a new release via `fabrik apply` / `fabrik redeploy`.
- Runtime database migrations that modify the app container (migrations MUST be run as separate deploy‑time steps)
**Place a service next to its data.** A spoke-hosted service reaches `postgres-main`/`redis-main` over the WireGuard mesh, and that hop is cross-Atlantic (Coventry ↔ LA) on EVERY query — a per-request chatty service pays it hundreds of times per page. So a DB-chatty service targets vps1; a spoke earns a service whose data traffic is light, batched or cached; a service PINNED to a spoke by hardware (GPU) batches or caches its data access — the data never moves off vps1. Measure before choosing (`ping 10.99.0.1` from the spoke, and the request's query count), never assume — the correctness rule ("container DNS, never localhost") says nothing about latency.
**Mandate:** WSL dev and the VPS run the SAME backing services (PostgreSQL + Redis), same major version. NEVER substitute a different backing service in dev (no SQLite standing in for Postgres, no in‑memory dict standing in for Redis). The same code must run unmodified in both environments.
- WSL runs PostgreSQL + Redis at the SAME MAJOR as the VPS containers — probe the live truth, never copy a tag from a doc: `ssh vps "sudo docker inspect postgres-main redis-main --format '{{.Config.Image}}'"` (2026-09-01: `postgres:16-alpine` · `redis:7-alpine` — upstream official images, outside OUR-image Alpine ban per § Banned Patterns)
**Invariant:** Never use `ports:` in compose.yaml to expose internal services to the host. All external traffic must go through Traefik.
**Health endpoints (`/health`, `/healthz`, `/metrics`, `/api/health`) bypass Authelia on all services** — required for Gatus and Prometheus monitoring. The bypass is **resource-based, not domain-bound** — applies on every domain routed through Authelia (hub direct + spokes via `authelia-vps1@file` middleware). Never protect these paths.
**CRITICAL:** Use `web`/`websecure` in Traefik labels — never `http`/`https` (those entrypoints do not exist). The scaffolder emits the correct entrypoint names; if you hand-write labels, match these exactly.
**Mandate:** migrations and admin tasks run as a ONE‑OFF process against the DEPLOYED image + env — identical environment to regular processes. NEVER run admin tasks from a laptop against prod, NEVER via `docker exec` into a live container, and **ABSOLUTELY NEVER auto-run migrations from app startup/`lifespan`** (concurrent replicas race the Alembic version table → wedged deploy).
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

### core/10-python.md  (hit: scripts/command_feedback_report.py, scripts/command_run.py, scripts/enforcement/check_plan_quality.py)
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
- Ruff's selected rule-sets MUST include `ASYNC` (blocking IO in async code — machine-enforces this pack's hardest-to-review rule), `B` (bugbear) and `S` (bandit) alongside the defaults; configured in `pyproject.toml`, emitted by the scaffolder.
- Production services run via `uvicorn` CLI in the Dockerfile, not `uvicorn.run()` in code. Base image is always the pinned Debian `-slim` variant on `linux/amd64` (the variant is pinned fleet-wide in `30-ops.md` § Container Base Images — change it THERE, never per-repo). Never use Alpine — musllinux wheels exist now (PEP 656) but coverage is still partial, source builds are dramatically slower, and musl's allocator/stack defaults degrade CPython; the trade never pays on this fleet.
- `uvicorn.run()` is for local development only. Never ship it in production code.
- a fleet scaling decision (more containers), never a per-app flag.
**BANNED: grouped/named env config sets.** 12F is explicit — *"env vars are granular controls, each fully orthogonal to other env vars"* — so a `config/production.yml`, a `settings.production` group, or a `config/{dev,staging,prod}.yaml` tree is a violation. Env vars are granular and set **per deploy**, never batched into a named "environment".
**BANNED:** `logging.FileHandler`, `logging.handlers.RotatingFileHandler`, `TimedRotatingFileHandler`, `loguru` file sinks, any `*.log` file write, any in-app log rotation/retention/cleanup. The app never decides where logs are stored or routed — Docker → Promtail → Loki does. Full rule: `55-observability.md` § Logs.
**Factor XII — Admin processes. NEVER migrate from app startup.**
**BANNED: `alembic upgrade head` in FastAPI's `lifespan`, in an `@app.on_event("startup")`, or as an import side-effect.** With more than one replica (or a restart storm) two containers run `upgrade head` **concurrently** → they race the Alembic version table → duplicate DDL → **wedged deploy**. Migrations are a **one-off admin process against the deployed release**: `docker compose run --rm <svc> alembic upgrade head` (see `30-ops.md` § Release & Admin Processes).

### core/40-documentation.md  (hit: CLAUDE.md, commands/_fragments/scope-growth-exit.md, commands/_sources/fabrik-execute-plan.md)
- > **⚠️ `docs/OPERATIONS.md` + `docs/DEPLOYMENT.md` are FLEET-AI INTERFACES, not just docs (D-065).**
- **Tier-1 (author → verify → converge; the author leg is NATIVE while the pool is OFF, D-181 — `scripts/doc_reconcile.py`'s pool author cannot dispatch):** for each **mechanically-detectable** doc whose Doc-Sync trigger fired (`docs/QUICKSTART.md` · `docs/CONFIGURATION.md` · `docs/data-contract.md` · `docs/SERVICES.md` · `docs/OPERATIONS.md` — the reliable-signal subset), `scripts/doc_reconcile.py` dispatches a cheap OpenRouter-pool author (`libs.subagents`, `pick_models("docs")`) to emit a **minimal structured patch**, **verifies it before applying** (a symbol cross-check catches invented endpoints; the orchestrator injects a higher-assurance native-Claude verify), and loops to a zero-edit round. Runs per phase in `/fabrik-execute-plan`; never blocks (fail-safe). The other docs (CHANGELOG, INDEX, FEATURES, RESILIENCE, PORTS, the READMEs, `db/schema.sql`, …) have no reliable mechanical content-signal → they rely on the touch-on-change backstop below + your own edit (force-update, not force-correct).
- The SSOT is the type-aware registry (`scripts/enforcement/_doc_registry.py::PROJECT_DOCS`) — this table is its project-facing rendering, kept in step, never a second truth. `/fabrik-plan-after-chat` (the plan set's spine + tickets — the ticket-format authority) injects these rows per ticket as its `Docs:` line.
- Standalone work (not plan execution) → `Agent-Role: primary`. Trailers go below a blank line, above `Co-Authored-By`. ⚠️ The trailer block must be its OWN paragraph with NO blank line inside it: git parses only the LAST paragraph, and only if it is all-trailers. A blank line before `Co-Authored-By:` demotes everything above it to prose; so does a prose line glued to the top of the block. Measured 2026-08-15: 200 of the last 200 hub commits carried `Agent-Role:` and only 10 parsed, because the old example here shipped the blank line.
- **⚠️ Link it or it is decoration.** *Measured:* requests for files that do NOT exist came ~zero from AI bots — agents never go looking. It follows (inference, not measurement) that a file only gets read when something points at it: reference it from the docs index or README.
- ⚠️ **In THIS repo `llms.txt` is GENERATED** (`scripts/generate_capability_index.py`, refreshed daily) — never hand-edit it; change the generator. A project writing one by hand owns it.
- either way. Cheap and reversible — never at the expense of `OPERATIONS.md`/`DEPLOYMENT.md`, which are the load-bearing agent interfaces (D-065).
- **No skipped heading levels** — `##` to `###`, never `##` to `####`
- **Fenced code blocks only** — never indented code (AI treats it inconsistently)

### core/45-testing-strategy.md  (hit: tests/fixtures/lane_replay.json, tests/test_command_feedback_report_lane.py, tests/test_command_run_fabrik_task.py)
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
- [ ] Destructive DB tests call `require_throwaway(TEST_DATABASE_URL)` before connecting — never point them at a dev/shared DB.

# promote-to-check_*: 82 injected mandate(s) look deterministically greppable — their backtick literals, one line each (the full mandates are ABOVE, not repeated: re-emitting ~20 FLOOR lines verbatim doubled the rubric and got it skimmed — web-ecommerce-factory 01M1QEY5, 2026-09-05)
# (the backtick-literal list that follows this header is elided — 82 lines; the full mandates are above)
```

| Row | Verdict | Evidence |
|---|---|---|
| FLOOR core/35-security-auth | CLEAN | no auth surface; the only trust decisions are the receipt checks (a)–(d), which shell out to the existing coverage checker and resolve SHAs with `git rev-parse` (T03b), and the exact-line `**Lane:**` match (T04) |
| FLOOR core/25-data-postgres | CLEAN | no database; state is JSON lines beside the run-record state dir and `.fabrik/lane.json` |
| FLOOR core/30-ops | CLEAN | no compose, port or service; box scripts and a fleet-synced CLI |
| FLOOR 12-FACTOR | CLEAN | no new environment variable; `task_lane.py` is pure and reads no environment, the ledger path is passed in by T08 from the existing `_state_dir()` (`scripts/command_run.py:84`) |
| MATCHED core/10-python | FIXED | the refusal ledger beside the state dir, never `/tmp` (`10-python.md:153`); the module is pure so its tests never touch real state (pass 1, A-rules-O4) |
| MATCHED core/40-documentation | FIXED | T07 documents every flag and field by name, the scope-growth fragment moved to T07 (pass 1, B-tickets-S1–S3 gate repoint, T04 split) |
| MATCHED core/45-testing-strategy | FIXED | every ticket gate names existing or own-Touches test files (pass 1, S1–S5, O13); the replay test is red-first in T02 against T01's fixture; T04 adds a lockstep test (O2) |
| standing: fail-open/fail-closed | FIXED | malformed `lane.json` falls back to v1 with a warning, never to v2 (O16); the `--surface` refusal applies at v2 only, so a v1 repo is untouched (O15); `blocked` is never trapped by the receipt (O9) |
| standing: cost/quota accounting | CLEAN | no metered call; native seats only (pool OFF); appetite is minutes, validated positive integer, default 240 (O23) |
| standing: boundary/sentinel/prefix | FIXED | dependency directories match by path SEGMENT (`myvendor/`, `node_modules_old/` are not exclusions), `.yml` and `.bak` are not contract hits, the 240/241, 120/121 and 800/801 edges and the `LANE_ROLLOUT_DATE` boundary each have a row, the `**Lane:**` line is matched exactly (O17, O19, O22, O23) |
| standing: behavior-without-a-test | FIXED | 47 Behavior Contract rows; T08 gained CLI rows for every wiring point (O1, O7, O8, O20, O21) |

## Pass Ledger

| Pass | seats · axes re-checked | counters | method | plan md5 (start → end) |
|---|---|---|---|---|
| Pass 1 | native opus×1 + sonnet×1 finders, opus×1 + sonnet×1 refuters · slices A-rules (spine rules, T02, T03, T04, T08), B-tickets (T01, T05a, T05b, T05c, T06, T07, Evidence) | found: 30 · confirmed: 30 · own-fix: 0 | method: full section partition, every candidate executed by a refuter; the gate globs, the missing T08 rows and the absent rollout constant re-executed by the orchestrator | ae7ad38a → 3254082a |
| Pass 2 | native opus×1 + sonnet×1 finders, opus×1 refuter · same slices, claim ledger 30 | found: 7 · confirmed: 6 · own-fix: 4 | method: ledger re-verification over the fix diff plus one hop; O9 refuted (an empty design list already triggers the refusal) | 3254082a → ec398574 |
| Pass 3 | native opus×1 + sonnet×1 finders, opus×1 + sonnet×1 refuters · same slices, claim ledger 6 | found: 3 · confirmed: 2 · own-fix: 2 | method: ledger re-verification; B-tickets-S2 refuted by the orchestrator (a Gate may run an existing suite it does not change); scope-growth stop fired (D-278) — no further finder round | ec398574 → 93837598 |
| Pass 4 | orchestrator · every cite, the roll-up, File Scope, every Gate file, both pass-3 fixes | found: 0 · confirmed: 0 · own-fix: 0 | method: re-derivation — 33 of 33 full-path cites resolve at 579096eb1, 47 = 47 roll-up rows in order, File Scope 39 = union of Touches, 0 dead gates, every touched test in its own Gate, `check_plan_tickets` 0 findings (output in § Evidence) | 93837598 → final |

The confirmed series 30 → 6 → 2 → 0 fell every pass; passes 2 and 3 were mostly residue of the pass-1 restructuring (own-fix 4 of 6, 2 of 2), the seats re-sweeping the same persisted ledger each round.

## Residual unknowns

- U1 — whether the day-7 hub week shows a refusal the fixture did not predict: answered by the D12 criterion at the flip, not by this plan.
