# Plan — one door: the lane verb, three refusing starts, one rule (D-861)

Status: DRAFT
Profile: small
**Owner:** kaizen

Spec: `docs/superpowers/specs/2026-10-14-one-door-lane-design.md` (DRAFT at e9dcb0f18, `Size: small`, `Profile: delta` on the
2026-10-02 lane spec — `/fabrik-plan-review` grades its sections together with this plan and flips both). Operator ruling
2026-10-14: *"i dont want to be get involved in now, task, spec selection process. agents should decide it by selecting most
suitable and best approach. lean, fast, error free"*. Since the spec was written, infra shipped D-862 (f0a6d1326): `/fabrik-spec
start --file/--declare` runs `task_lane.admit` through `_task_size_gate(command="fabrik-spec")`, opt-in. This plan builds on
that code and never duplicates it (infra's rule, memory `project_lane_gate_two_sided_d862`: a third caller of the gate path).
Estimated diff: ≈360 lines across 5 code files, tests excluded — `scripts/task_lane.py` ≈90 (`LANE_TRIPS`, `lane_verdict()`,
`enforce_mode()`, `_LANE_ENFORCE`), `scripts/command_run.py` ≈190 (`_lane_facts` extraction, the `lane` verb, the verdict
ledger, three door lookups, two close fields), `scripts/command_feedback_report.py` ≈60 (`--lanes`), `.claude/hooks/final_gate_stop.py`
≈4 (one cause string), `.claude/hooks/skill_router.py` ≈6 (one directive string). Text: two contracts, three command sources,
`docs/reference/command-run-protocol.md`, `agents-fabrik-core.md`; graders in three test files.

## What this plan is

Three inline phases the executor codes in the main checkout (every code path here is a governance-sync path — `scripts/command_run.py`,
`scripts/task_lane.py`, `.claude/hooks/`, `templates/governance/` — so, as the venv plan did, phases A–C land as ONE commit after the
Finish review; D-369/D7):

- **A — the verb and the doors** (`spec § The delta` R2, R3, R4): `task_lane.py` gains the trip-list constant, a PURE `lane_verdict()`
  and the dated enforcement constant; `command_run.py` gains a `lane` verb that shares `_task_size_gate`'s fact-gathering and `admit`
  call without its refusal-row side effects, writes `~/.claude/state/lane-verdicts.jsonl`, and the three `start` branches look the
  verdict up in `dryrun`/`warn`/`deny`; the close records `lane_verdict`/`lane_outcome`. Red-first tests, replay row.
- **B — the report, the hook, the router** (R3, R5): `command_feedback_report.py --lanes` (verdict vs outcome per agent, fire rate per
  mode, the kill ratio); the Stop hook's `unreviewed-spontaneous` cause names the verb; the router's directive says "run the lane
  check first".
- **C — the rule text and its graders** (R1, R6): the three-question rule rendered from `LANE_TRIPS` replaces the six-row table and its
  four paragraphs in `CLAUDE.md` and `templates/governance/CLAUDE.md`; `/fabrik-spec` Phase 0, `/fabrik-task` § SIZE and
  `/fabrik-review-scoped`'s start point at the verb (and carry infra's three D-862 follow-ups); the eight table graders are rewritten to
  bind the rule to the same constants; protocol doc, Front door line, fabrik-lib mail, Doc Sync; Finish: the full `/fabrik-review`
  (a hook path is in scope) and ONE commit.

Per phase: `/fabrik-review-scoped` on that phase's surface. At Finish: one heavy `/fabrik-review` (the `/fabrik-execute-plan` D7 floor) and
one receipt, `docs/development/reviews/2026-10-14-plan-2-one-door-lane-review.md`.

## Intake Inventory

| I# | Item (anchored) | Disposition | Where |
|---|---|---|---|
| I1 | spec § Intake Inventory I1–I13 (13 items, all IN) | IN | Phases A–C per the spec's R1–R6 |
| I2 | *"NEXT: /fabrik-plan-after-chat docs/superpowers/specs/2026-10-14-one-door-lane-design.md"* (the operator's go) | IN | this file |
| I3 | infra, mail 01M4Y05AYDT40DKBNE2Q0DVHRR: *"kaizen's one-door spec … must be a third caller of `_task_size_gate(command=…)`, not a parallel implementation"* | IN | Phase A step 2 (`_lane_facts` shared with `_task_size_gate`; `admit` is the one decider) |
| I4 | infra, same mail — follow-ups on kaizen's Phase 0 wording: (a) pass `--file`/`--declare` at start; (b) read a `spec-start` row's `verdict`/`restart`; (c) skip a `spec-start` row whose spec closed `done` | IN | Phase C step 3 |
| I5 | judge panel (spec § Decisions taken): rollout hub `warn` / fleet `dryrun` / `deny` after a measured week; the phase touching the hook owes the full `/fabrik-review` | IN | Phase A step 6 (`_LANE_ENFORCE`), Finish |
| I6 | spec § Open unknowns: the exact `consumers=external` test the verb can execute | IN | Phase A step 1 (the trip is `admit`'s own: a declared `consumers=external` or a `contract_hit` path — the verb adds no second definition) |

## What we already agreed (citations, not restatement)

- The rule, its three questions, the review line and the tie-break: `spec § The delta` R1.
- The verb's flags, verdict forms, file-list binding and operator prefix: `spec § The delta` R2.
- The three doors refuse without a verdict; the Stop hook and the router name it: `spec § The delta` R3.
- One dated enforcement constant, `dryrun → warn → deny`, kill rule 1 in 5: `spec § The delta` R4; rollout order `spec § Decisions taken`.
- `lane_verdict`/`lane_outcome` on the close row and `--lanes` in the report: `spec § The delta` R5.
- The command sources point at the verb; `/fabrik-spec` Phase 0 shrinks: `spec § The delta` R6.
- Approach C (a model judge) rejected; A (text only) rejected: `spec § Rejected alternatives`.
- Code owner infra, text owner kaizen: `spec § Ownership`; D-862's code is the base: `docs/DECISIONS.md` D-862.

## Global Constraints (every phase inherits these)

- Fleet-synced scripts and hooks (`.pre-commit-config.yaml` governance-sync filter: `^scripts/(…|command_run|task_lane|…)\.py$`,
  `^\.claude/hooks/`, `^templates/governance/`): one behaviour for ~46 repos; a flagless start keeps today's behaviour in every mode
  but `deny`; `task_lane.py` stays PURE (`scripts/task_lane.py:5-8`: *"no import of command_run.py, no environment reads that change an
  answer"*) and replay-graded (`tests/test_lane_replay.py`).
- No model call on the request path (`skill_router.py:25-32`'s latency ruling); no new daemon; the only new store is
  `~/.claude/state/lane-verdicts.jsonl` beside the existing ledgers, redirected in tests through `COMMAND_RUN_DIR`
  (`tests/conftest.py:249-279`, autouse).
- A hook never imports `command_run.py` or `task_lane.py` (`.claude/hooks/final_gate_stop.py:566-570`): the hook change is text only.
- Every gate command runs from WSL dev: `.venv/bin/python -m pytest …`, `python3 scripts/…`; never `fabrik …`.
- 12-Factor non-negotiables: logs to stdout only (XI); no PID files or daemons (VIII); config by env var, no grouped env set (III);
  no new backing service (X); immutable releases (V) — none of these surfaces is a service, the rules bind the scripts' own I/O.
- Shared-append files (`CHANGELOG.md`, `docs/DECISIONS.md`, `INDEX.md`) go through CLAUDE.md § EXIT's private-index recipe, never a
  pathspec commit; the Doc Sync rows this plan keys: CHANGELOG (always), `docs/reference/command-run-protocol.md` (the verb), the
  D-row for the `deny` flip when it happens (not in this plan).
- Red-first for every new behaviour (`core/45-testing-strategy.md:22`); type hints on every new signature (`core/10-python.md:160`).

## Context Ledger

| Source | What binds | Grounded ref |
|---|---|---|
| `.windsurf/rules/core/10-python.md` (FLOOR) | type hints on all signatures; no import-time env reads for config | `:160` "Use type hints for all function signatures"; `:309` import-time `os.getenv` banned |
| `.windsurf/rules/core/45-testing-strategy.md` (MATCHED: tests/) | one test per behaviour, watched-fail-first | `:20-22` |
| `.windsurf/rules/core/40-documentation.md` (MATCHED: CLAUDE.md, templates, commands) | edit existing docs, allowlisted new `.md` only; one H1 | `:186`, `:184-196`, `:241` |
| fabrik-lib | no module routes work or gates a start; `decision-gate` is a typed-decision MODEL lane (D-527/D-550) — BUILD, hub-local, not a lib candidate (reads hub-only state) | `/opt/fabrik-lib/README.md` module table (53 rows read; none matches) |
| `agents-fabrik.md` § Workflow (three tiers) | the front door text this plan rewrites in `agents-fabrik-core.md:17` | `agents-fabrik.md:43-53` |
| `specs/services/*.yaml` `shape:` | none — no service, no flag | — |
| `docs/data-contract.md` / `docs/ui-design.md` | none frozen for the hub | — |
| D-862 (`docs/DECISIONS.md`) | `_task_size_gate(command=)` and `_spec_admit_v2` are the gate path; `spec-start` rows; `downgrade: no-refusal` | `scripts/command_run.py:4143-4145`, `:4065-4077`, `:4122-4139`, `:3988` |

## Constraints Digest (verbatim rows from the MUST-READ packs)

| Quote | Source |
|---|---|
| Edit existing docs instead of creating new ones. | `.windsurf/rules/core/40-documentation.md:186` |
| Reference: `docs/reference/**/*.md` | `.windsurf/rules/core/40-documentation.md:192` |
| One H1 per document | `.windsurf/rules/core/40-documentation.md:241` |
| a non-trivial behavior's test proves something only if it has been SEEN RED | `.windsurf/rules/core/45-testing-strategy.md:22` |
| Use type hints for all function signatures | `.windsurf/rules/core/10-python.md:160` |

## Phase A — the verb and the doors

Appetite: 150

**Interfaces — Produces** (`spec § The delta` R2, R3, R4):
- `scripts/task_lane.py` — `LANE_TRIPS: tuple[tuple[str, str], ...]`: the Q1 trip list as (key, text) pairs — `("contract", "another repo
  or person must change BY HAND …")`, `("data", "data others stored changes shape or is destroyed")`, `("published", "a published name,
  URL or contract that a shipped client reads moves or breaks")`, `("tradeoff", "two approaches the build itself cannot rank …")`,
  `("session", "it will not finish in one session")` — the ONE source the contract text is rendered from (Phase C) and the verb's
  reasons are keyed on; `lane_verdict(declared, files, *, sync_hits, appetite, why, version, fix, docs_only, prefix) -> LaneVerdict`
  (frozen dataclass `lane: "now"|"task"|"spec"`, `reason: str`, `review: "scoped"|"full"`, `trip: str | None`, `restart: str`) — PURE:
  `prefix in ("now","task","spec")` wins and sets `reason = "operator prefix"`; else `docs_only` or `fix` ⇒ `now`, review from
  `admit(...).review`; else `v = admit(declared, files, sync_hits=…, appetite=…, why=…, version=…)`: a `chain:` route ⇒ `spec` with
  `trip` the route's suffix (`contract`/`appetite`/`oneway`/`tradeoffs`) and `reason = v.reason`; `right-now + …` ⇒ `now`; `lane` ⇒
  `task`; `refused` ⇒ `LaneVerdict("refused", v.reason, …)` so the verb prints the gate's own refusal; `restart` is the ready start line
  (`python3 scripts/command_run.py start --command fabrik-task --phases 5 --terminal "<…>" --surface "<…>" --file … --declare …` for
  task, the spec's start line with the same flags for spec, nothing for now). `enforce_mode(is_hub: bool) -> str` reads
  `_LANE_ENFORCE = {"hub": "warn", "fleet": "dryrun", "since": "2026-10-15", "deny_after_days": 7}` — a constant, no env read; `deny`
  is a later commit that edits the constant (its own D-row).
- `scripts/command_run.py` — `_lane_facts(args, sid) -> LaneFacts` (dataclass: `root, rels, answers, sync_hits, appetite, why, version,
  switch, dirty, docs_only`): the fact-gathering that `_task_size_gate` does today at `:4160-4313` (paths → rels, the `--declare`
  parse against `_TASK_DECLARE_KEYS` + `consumers`, the sync-filter hits, `lane_version`), extracted so `_task_size_gate` and the verb
  compute the same facts; `_task_size_gate` keeps its signature, its refusal rows and its prints (every `spec_gate` and lane-v2 test
  stays green). The `lane` subparser (`parents=[common]`; `--ask` required, `--file` append, `--declare`, `--appetite`, `--why`,
  `--oneway`, `--tradeoff`, `--fix`; `--oneway`/`--tradeoff` set `declared["oneway"|"tradeoffs"]="yes"` and `why`), a pre-lock
  reader like `line` (`:3582`) inside its own refusing `try` (`main`'s outer handler fails soft to rc 0, `:3618-3620`); it prints ONE
  line `LANE: <lane> — <reason>` plus the `restart` line, and appends `{id: "LV-<8 hex>", ts, session, repo, agent, ask, files, declared,
  flags, lane, reason, trip, review, mode}` to `_lane_verdicts()` = `_state_dir().parent / "lane-verdicts.jsonl"` (`:88-92`, `:3998`
  precedent). `_lane_verdict_for(sid, lane, rels) -> dict | None`: the newest row of this session with that lane whose `files` ⊇ `rels`
  (or the row named by `--lane-verdict <id>`). Door lookups: the spec branch `:5368-5376` (before `:5374`, also covering a flagless
  start), the task branch before `:5408`, a new `_cmd == "fabrik-review-scoped"` check inside `:5379-5401` mirroring `:5382-5389`;
  each: `mode = tl.enforce_mode(is_hub)`; no verdict → `dryrun`: a ledger `door` row only; `warn`: the row plus the refusal text printed
  as `NOTE — <cmd>: no lane verdict for this start — run python3 scripts/command_run.py lane --ask "…" --file … first` and the start
  proceeds; `deny`: `_refuse(...)` with the same text. `--resume-from` (`:5366-5367`) skips the lookup, as it skips the gate. `start`
  gains `--lane-verdict ID`. The record keeps `lane_verdict: <id>` next to the `lane_gate` stamp (`:5510-5518`), only on the three
  commands (the `:5506-5509` rule). `_close` (`:6854-6880`): `lane_verdict` and `lane_outcome` on the three commands' rows —
  `ok`; `grew` (a `now` whose record's covered files exceed `_FULL_REVIEW_FILES` or add a source file, by `tl.counted`/`tl.is_new_source`
  over the record's surface); `handed-off` (a task closed by `handoff`); `small-no-trip` (a spec whose close carries `size: small` and a
  `lane_gate` of `lane` or `none`); `prefix` (the verdict row's reason was the operator prefix).
- `is_hub` = `_repo_root()` resolves to `/opt/fabrik` or a worktree whose common dir is the hub's (`git rev-parse --git-common-dir`),
  computed once in the verb and the doors.

**Consumes:** `task_lane.admit`, `record_refusal`'s row shape (`:400-423`), `_lane_module()`, `_lane_version_at`, `_refuse`, the
`start`/`handoff`/`_close` seams named above.

**Mirror (named):** `tests/test_command_run_lane_v2.py` `spec_gate` tests (:1164-1348) and every `_started_v2` test — unchanged
behaviour, re-run; `tests/test_lane_replay.py` — a `lane_verdict` row joins the tasks fixture (`tests/fixtures/lane_replay_tasks.json`,
21 rows, loaded only through `scripts/lane_replay_capture.py::load`) with `expected_lane`; `docs/reference/command-run-protocol.md:52-59`
(the `start`/`handoff` rows gain `--lane-verdict`, a `lane` row, the two feedback fields — Phase C).

0. Probe: `.venv/bin/python -m pytest -q tests/test_command_run_lane_v2.py -k spec_gate` → 9 passed (the D-862 baseline this
   phase must keep); `.venv/bin/python -m pytest -q tests/test_lane_replay.py` → passed; record both in Evidence.
1. **Write the failing tests first** in `tests/test_command_run_lane_v2.py` (rows A1–A8), copying `run_dir`/`_repo`/`_cr`/`_rec`/
   `_ledger`/`_V2` (`:19-69`, `:277-281`; `_cr` pins `COMMAND_RUN_DIR`, `KAIZEN_EVENTS_DIR`, `HOME`, `CLAUDE_SESSION_ID`); add
   `_verdicts(run_dir)` reading `run_dir.parent / "lane-verdicts.jsonl"`; a unit test file `tests/test_task_lane_verdict.py` for
   `lane_verdict()` and `enforce_mode()` driving `scripts/task_lane.py` by path, every trip and the prefix. Run → red (the verb and
   the functions do not exist); paste the red summary into Evidence.
2. `scripts/task_lane.py`: `LANE_TRIPS`, `LaneVerdict`, `lane_verdict()`, `_LANE_ENFORCE`, `enforce_mode()` — after `record_refusal`,
   before `classify_commit`; the module docstring's bullet list gains two lines (`lane_verdict`, `enforce_mode`); the `AFTER-EDIT`
   header gains `tests/test_task_lane_verdict.py`. Gate: `.venv/bin/python -m pytest -q tests/test_task_lane_verdict.py` → green.
3. `scripts/command_run.py`: extract `_lane_facts` from `_task_size_gate` (`:4160-4313`) and call it there (behaviour identical:
   `-k spec_gate` and the lane-v2 suite stay green — run them, paste the count); add `_lane_verdicts()`, `_lane_verdict_for()`, the
   `lane` subparser (`:3414-3420` is the shape) and its pre-lock dispatch (`:3582` is the position); the verb computes
   `LaneFacts`, calls `tl.lane_verdict(...)`, prints, appends. Gate: A1–A4 green.
4. The three door lookups at `:5368`/`:5379`/`:5408` with `enforce_mode(is_hub)`; `--lane-verdict` on `start`; the record stamp; the
   `_close` fields (`:6854-6880`). Gate: A5–A8 green; the whole file `.venv/bin/python -m pytest -q tests/test_command_run_lane_v2.py
   tests/test_command_run_fabrik_task.py` green.
5. Replay: add `expected_lane` to the 21 task rows of `tests/fixtures/lane_replay_tasks.json` via `scripts/lane_replay_capture.py`
   (extend `load`/capture to carry it); `tests/test_lane_replay.py` gains `test_every_task_row_gets_the_pinned_lane_verdict`.
   Gate: `.venv/bin/python -m pytest -q tests/test_lane_replay.py` → green.
6. The constant: `_LANE_ENFORCE["hub"] = "warn"`, `["fleet"] = "dryrun"`, `["since"]` = the merge date, `["deny_after_days"] = 7`; its
   docstring states the cobra (`--fix` on everything; a one-word `--oneway`) and the counter (`lane_outcome` per agent, `--lanes`).
7. Closing sequence: (1) the phase gate above green; (2) `python3 scripts/enforcement/check_doc_sync.py` + the protocol doc rows deferred
   to Phase C are noted; (3) `/fabrik-review-scoped` on this phase's surface, run to its coverage-adjudicated exit, every finding
   FIXED/REFUTED; (4) no commit yet — D7: one commit after Finish.

### Behavior Contract — Phase A

- **Given** `--ask "fix the flaky login test" --file tests/test_login.py --fix`, **When** `lane` runs, **Then** it prints `LANE: now —` and
  appends one row with `lane: now` (`spec § The delta` R2; `scripts/task_lane.py:313` `admit`).
- **Given** `--file src/a.py --declare <_V2>` with no trip, **When** `lane` runs, **Then** it prints `LANE: task` and the ready
  `start --command fabrik-task` line, and the row's `restart` equals that line (`spec § The delta` R2).
- **Given** `--file specs/services/x.yaml --declare <_V2>`, **When** `lane` runs, **Then** it prints `LANE: spec — tripped: contract:` and
  the row carries `trip: contract` (`scripts/task_lane.py:167` `contract_hit`, `:365-368`).
- **Given** `--declare …oneway=yes…` with no `--why`/`--oneway` text, **When** `lane` runs, **Then** it prints the gate's own
  `--why is required` refusal and writes NO row (`scripts/task_lane.py:371-381`).
- **Given** `--ask "spec: …"`, **When** `lane` runs, **Then** the row reads `lane: spec, reason: operator prefix` whatever the files
  (`spec § The delta` R2).
- **Given** `start --command fabrik-spec` with no verdict row in the hub (`warn`), **When** it runs, **Then** the start proceeds, prints
  `NOTE — fabrik-spec: no lane verdict`, and a `door` row lands; **Given** the fleet (`dryrun`) only the row lands; **Given**
  `_LANE_ENFORCE["hub"] == "deny"` (monkeypatched), the start is REFUSED naming the verb (`spec § The delta` R3, R4;
  `scripts/command_run.py:5368-5376`).
- **Given** a `task` verdict for `src/a.py` and a `start --command fabrik-task --file src/a.py --file src/b.py`, **When** it runs in
  `deny`, **Then** it is refused (file set not covered) and succeeds with `--lane-verdict <id>` (`spec § The delta` R2 binding).
- **Given** a task started on a `task` verdict and closed by `handoff`, **When** the feedback row is written, **Then** it carries
  `lane_verdict: <id>` and `lane_outcome: handed-off` (`spec § The delta` R5; `scripts/command_run.py:6854-6880`).

## Phase B — the report, the hook, the router

Appetite: 60

**Interfaces — Produces:**
- `scripts/command_feedback_report.py` — `_verdict_rows(path)` (the `_refusal_rows` shape, `:2001-2018`, over `lane-verdicts.jsonl`);
  `lanes(rows, verdicts, *, window_days) -> dict`: per agent and per repo `{verdicts: {now, task, spec}, outcomes: {ok, grew,
  handed-off, small-no-trip, prefix}, doors: {dryrun, warn, deny} fire counts, kill_ratio: handed-off task verdicts / task verdicts}`,
  joining verdict rows to feedback rows on `lane_verdict`; `_lanes_text(doc)`; a `--lanes` flag after `--lane` (`:2561-2566`) and
  its `--json` form. The kill rule prints as `KILL: task→spec hand-offs 3/12 (25%) > 20% — revert the doors to warn` when tripped.
- `.claude/hooks/final_gate_stop.py:1394` — the cause text becomes `a review of {N} file(s) — /fabrik-review-scoped; run python3
  scripts/command_run.py lane --ask "<the request>" --file … first and take the lane it names` (text only; no import).
- `.claude/hooks/skill_router.py:788-790` — `build_injection` reads `This request matches /{skill} (Stage: …) — run the lane check first
  (python3 scripts/command_run.py lane --ask "…" --file …), then invoke the skill its verdict names, or state in one line why it does
  not apply.`; the docstring at `:5-6` paraphrases the same.

**Consumes:** Phase A's ledger row shape and the two feedback fields.

**Mirror (named):** `tests/test_command_feedback_report_lane.py` fixtures (`_row`, `_refusal`, `_write`, `_lane`, `_doc`, `:1-90`) —
extended with `_verdict(...)`; `tests/test_skill_router.py` (whichever test pins `build_injection`'s text — grep `invoke the skill`);
the Stop hook's cause tests (grep `unreviewed-spontaneous` in tests/).

1. **Failing tests first**: `tests/test_command_feedback_report_lane.py` rows B1–B3 (a synthetic verdict ledger + feedback rows →
   `--lanes --json` doc; the kill line); `tests/test_skill_router.py` row B4 (the directive text); the hook cause test row B5. Run →
   red; paste the summary.
2. `command_feedback_report.py`: `_verdict_rows`, `lanes`, `_lanes_text`, the flag. Gate: `.venv/bin/python -m pytest -q
   tests/test_command_feedback_report_lane.py` → green.
3. `final_gate_stop.py:1394` and `skill_router.py:788-790`. Gate: `.venv/bin/python -m pytest -q tests/test_skill_router.py
   tests/test_final_gate_stop*.py -k "lane or unreviewed or injection"` → green.
4. Closing sequence: (1) gates green; (2) `check_doc_sync.py`; (3) `/fabrik-review-scoped` on this phase's surface to its exit;
   (4) no commit yet.

### Behavior Contract — Phase B

- **Given** three verdict rows (now, task, spec) joined to three feedback rows, **When** `--lanes --json` runs, **Then**
  `doc["agents"][a]["verdicts"] == {"now":1,"task":1,"spec":1}` and `outcomes` counts the three classes (`spec § The delta` R5).
- **Given** 3 of 12 task verdicts closed `handed-off`, **When** `--lanes` runs, **Then** the text carries the `KILL:` line (`spec §
  The delta` R4).
- **Given** `door` rows in two modes, **When** `--lanes` runs, **Then** `doors` counts them per mode (the fire rate the `deny` flip reads).
- **Given** a prompt the router matches to `/fabrik-spec`, **When** `build_injection` runs, **Then** its text contains `run the lane
  check first` and `command_run.py lane` (`spec § The delta` R3; `.claude/hooks/skill_router.py:788-790`).
- **Given** a record-less editing turn, **When** the Stop hook assembles causes, **Then** the `unreviewed-spontaneous` text names
  `command_run.py lane` (`.claude/hooks/final_gate_stop.py:1394`).

## Phase C — the rule text and its graders, then Finish

Appetite: 120

**Interfaces — Produces:**
- `CLAUDE.md` § Orient step 0 and `templates/governance/CLAUDE.md`: the six-row table, the precedence paragraph, the D-859 paragraph, the
  no-code clause and the tripwire (`CLAUDE.md:71-88`, `templates/governance/CLAUDE.md:64-81`) replaced by the rule block of `spec § The
  delta` R1, byte-identical in both, its Q1 list rendered from `LANE_TRIPS` (the test renders the constant and compares); the project
  parentheticals rows 1/1b carried today move into the review line as one clause each.
- `commands/_sources/fabrik-spec.md:23-55` Phase 0: the DOWNGRADE check becomes "this run's `spec` verdict (or `--lane-verdict`) is
  present — the start refused otherwise under `deny`, printed the verb under `warn`; its `--oneway`/`--tradeoff` reason is § Why's first
  line; pass `--file`/`--declare` at start (infra follow-up a); a `spec-start` row is read for its `verdict` and `restart`, never assumed
  a task restart (b); a `spec-start` row whose spec closed `done` is skipped — join on the close row's `spec_refusal` (c); an `LR-` row
  still drives the D9 handoff." `commands/_sources/fabrik-task.md:30-40` § SIZE opens with "paste the start line the lane verb printed".
  `commands/_sources/fabrik-review-scoped.md:15-30`: the record opens from a `now` verdict; the classification step keeps its order.
- `docs/reference/command-run-protocol.md:52-59`: the `lane` verb row, `--lane-verdict`, the ledger, `lane_verdict`/`lane_outcome`.
  `agents-fabrik-core.md:17` Front door: three tiers restated as the three questions, one line.
- `tests/test_governance_template_split.py`: the eight table graders (`:456-805`, grounded by name in Evidence) retired and replaced by:
  the rule block present and identical in both contracts; its Q1 list equals the rendering of `scripts/task_lane.py::LANE_TRIPS` (import
  by path); the review line names exactly `admit`'s `full` reasons (`sync`, `heavy`, `migration`, `files > 5`) plus the contract's
  auth/schema/operator-named words; the tie-break sentence present; the block renders as a fenced code block in GFM (markdown-it);
  the handle-now pointer `_LANE_POINTER` (`:497-514`) retargeted to "§ Orient step 0's lane rule". `tests/test_spec_plan_lane_text.py`
  Phase 0 pins (`:87-125`, `:275-305`) rewritten to the verdict wording (the D9 `--from-downgrade` restart and `## RESUME` pins stay).
- Mail to fabrik-lib: the rule block verbatim for its hand-kept CLAUDE.md (replacing its table at ~:379-394).

**Consumes:** `LANE_TRIPS` (Phase A); the `--lanes` name (Phase B).

**Mirror (named):** `scripts/enforcement/check_governance_tables.py` — generic overflow checker, no lane knowledge (grep `lane` = 0): the
rule block is fenced, not a table, so it reads nothing; `check_governance_drift` anchors — none in the replaced text (verified by grep
of the § UNIVERSAL list); `docs/superpowers/specs/2026-10-02-fabrik-task-feature-lane-design.md` (frozen; superseded in part by
D-861's row, not edited); `tests/test_fabrik_task_source.py` SIZE_CAP (D-296: raise by a D-row if § SIZE grows — the two-line change
is within the cap or the row says so).

1. **Failing graders first**: the new `test_governance_template_split.py` tests and the rewritten `test_spec_plan_lane_text.py` pins
   → red on the current text; paste.
2. The two contracts (rule block; `python3 -c` renders `LANE_TRIPS` to compare); `agents-fabrik-core.md:17`. Gate: `.venv/bin/python
   -m pytest -q tests/test_governance_template_split.py` → green; `python3 scripts/enforcement/check_governance_tables.py --strict` → OK.
3. The three command sources and the protocol doc; `python3 commands/assemble_commands.py --check` (DIFFERS rows for this branch's own
   edits are expected in a worktree; in the main checkout render → `--check` → commit). Gate: `.venv/bin/python -m pytest -q
   tests/test_spec_plan_lane_text.py tests/test_fabrik_task_source.py tests/test_review_scoped_queue_pass.py` → green.
4. Mail fabrik-lib (`python scripts/mail.py send --to fabrik-lib --kind request`) with the rule block; record the id in Evidence.
5. Doc Sync: `CHANGELOG.md` entry (private index); `INDEX.md` — no new docs; `docs/DECISIONS.md` — the build row is D-861's; the
   `deny` flip is a later row. `python3 scripts/enforcement/check_doc_sync.py`.
6. **Finish**: `python3 scripts/review_receipt.py --init --changed <every path in File Scope> --scope plan-2-one-door-lane` →
   `docs/development/reviews/2026-10-14-plan-2-one-door-lane-review.md`; the full `/fabrik-review` over the whole-plan diff (the hook
   path and `command_run.py` are heavy surfaces; D7 floor: `dispatch_headroom.py --slices sonnet=3,haiku=3` for three file slices —
   `task_lane.py`+tests, `command_run.py`+tests, hooks+report+text — plus one Haiku whole-surface seat, per the D-862 review's lesson
   that three Haiku-only seats found 0 of 14) to `confirmed: 0 · fixed: 0`; `review_receipt.py --restamp`; then
   `.venv/bin/python scripts/final_gate.py --check --json` → `"status":"success"` and `python3 scripts/enforcement/check_convergence.py`.
7. ONE commit, explicit pathspecs + trailers, after the Finish review (D7); in the main checkout render → `--check` → commit; the
   post-commit sync carries `command_run.py`, `task_lane.py`, the hooks and the template; `/fabrik-docs-review` on the protocol doc.

### Behavior Contract — Phase C

- **Given** both contracts, **When** the grader runs, **Then** the rule block is byte-identical in both and its Q1 items equal the
  rendering of `scripts/task_lane.py::LANE_TRIPS` (`spec § The delta` R1).
- **Given** the rule block, **When** rendered with markdown-it, **Then** it is a fenced code block inside item 0 and no lane table remains
  (`tests/test_governance_template_split.py:725` precedent).
- **Given** `commands/_sources/fabrik-spec.md` Phase 0, **When** the pins run, **Then** it says the `spec` verdict is present or the start
  refused, names `--file`/`--declare` at start, reads a `spec-start` row's `verdict`/`restart`, skips a row whose spec closed `done`,
  and keeps the `--from-downgrade <refusal id>` restart (`spec § The delta` R6; infra follow-ups a–c).
- **Given** `agents-fabrik-core.md:17`, **When** read, **Then** the Front door names the three questions and `/fabrik-task` under doubt.
- **Given** the whole-plan diff, **When** `final_gate.py --check --json` and `check_convergence.py` run after the Finish review, **Then**
  both are green and the receipt is CONVERGED with `confirmed: 0 · fixed: 0`.

## File Scope (owned paths)

- scripts/task_lane.py
- scripts/command_run.py
- scripts/command_feedback_report.py
- scripts/lane_replay_capture.py
- .claude/hooks/final_gate_stop.py
- .claude/hooks/skill_router.py
- CLAUDE.md
- templates/governance/CLAUDE.md
- agents-fabrik-core.md
- commands/_sources/fabrik-spec.md
- commands/_sources/fabrik-task.md
- commands/_sources/fabrik-review-scoped.md
- docs/reference/command-run-protocol.md
- tests/test_task_lane_verdict.py
- tests/test_command_run_lane_v2.py
- tests/test_lane_replay.py
- tests/fixtures/lane_replay_tasks.json
- tests/test_command_feedback_report_lane.py
- tests/test_skill_router.py
- tests/test_governance_template_split.py
- tests/test_spec_plan_lane_text.py
- docs/development/reviews/2026-10-14-plan-2-one-door-lane-review.md

## Evidence

**Phase A.** The gate path and ledger helpers this phase extends (grounder A, every anchor opened 2026-10-14):
```text
scripts/task_lane.py:67:_FULL_REVIEW_FILES = 5
scripts/task_lane.py:72:_APPETITE_MAX = 240
scripts/task_lane.py:167:def contract_hit(path: str) -> bool:
scripts/task_lane.py:313:def admit(
scripts/task_lane.py:400:def record_refusal(ledger: Path, row: dict[str, Any]) -> str:
scripts/command_run.py:3998:def _lane_ledger() -> Path:
scripts/command_run.py:4065:def _spec_admit_v2(
scripts/command_run.py:4143:def _task_size_gate(
scripts/command_run.py:5250:                    return _refuse("REFUSED — --file/--declare belong to --command fabrik-task")
scripts/command_run.py:5264:                        "REFUSED — --appetite/--why/--from-downgrade belong to --command fabrik-task"
```
`_task_size_gate`'s side effects a verdict-only caller must not inherit (grounder A): `_task_admit_v2` writes a refusal row on every
`chain:` verdict (`:4031-4047`) and `_spec_admit_v2` on every `--why` override (`:4122-4139`) — hence `_lane_facts` is extracted and
`admit` is the shared decider. D-862's landing, read at master:
```text
f0a6d1326 feat(lane): the gate is two-sided — /fabrik-spec start through task_lane.admit, spec-start override rows, no
 scripts/command_feedback_report.py                 | 104 ++++++++-
 scripts/command_run.py                             | 233 +++++++++++++++++---
 scripts/task_lane.py                               |   4 +
 tests/test_command_run_lane_v2.py                  | 237 +++++++++++++++++++++
 10 files changed, 916 insertions(+), 32 deletions(-)
```
The PURE rule (`scripts/task_lane.py:5-8`): "PURE: no import of ``command_run.py``, no environment reads that change an answer."

**Phase B.** The hook builds its cause text with no import (`.claude/hooks/final_gate_stop.py:1390-1395`: `owed.append(f"a review of
{len(unreviewed)} file(s) — /fabrik-review-scoped")`; `:566-570` the no-import rule); the router has no task trigger and builds its
directive at `build_injection` (`.claude/hooks/skill_router.py:788-790`):
```text
$ command grep -c "fabrik-task" .claude/hooks/skill_router.py
0
$ command grep -n '"spec": "fabrik-spec"' .claude/hooks/skill_router.py
110:    "spec": "fabrik-spec",
```
The report's lane helpers (`scripts/command_feedback_report.py`):
```text
2001:def _refusal_rows(path: Path | None) -> list[dict]:
2069:def _downgraded_specs(rows: list[dict]) -> set[int]:
2083:def _norefusal_downgrades(rows: list[dict]) -> int:
2096:def _unjoined_downgrades(rows: list[dict]) -> int:
2129:def lane(
2309:def _lane_text(doc: dict) -> str:
```

**Phase C.** The table and paragraphs to replace, and the graders that pin them:
```text
CLAUDE.md:71:   **The LANE table — apply it to the SMALLES
CLAUDE.md:84:   **Under doubt the lane is `/fabrik-task`.** 
CLAUDE.md:86:   **No code surface at all** (docs, ledgers or
CLAUDE.md:88:   **Tripwire:** if the first draft cites a scr
templates/governance/CLAUDE.md:64:   **The LANE table — ap
templates/governance/CLAUDE.md:77:   **Under doubt the lane 
templates/governance/CLAUDE.md:79:   **No code surface at al
templates/governance/CLAUDE.md:81:   **Tripwire:** if the fi
```
Graders keyed on the table's literal shape (grounder C, all in `tests/test_governance_template_split.py`): `_lane_table` :444-453;
`test_the_lane_table_carries_the_six_tests_and_its_verdict_row` :456; `test_the_lane_tables_verdict_row_names_a_command_that_exists`
:469; `test_the_heavy_surface_list_names_a_governance_sync_path` :482 (kept — § 1a, not the table);
`test_the_handle_now_clause_points_at_the_lane_table_instead_of_restating_a_test` :497 (retargeted);
`test_the_lane_tables_verdicts_match_the_size_gates_own_routing` :518; `test_the_lane_table_states_the_precedence_the_gate_actually_evaluates`
:600; `test_the_hubs_lane_table_matches_lane_v2` :667; `test_the_lane_table_renders_as_a_table_for_every_gfm_reader` :725;
`test_the_lane_table_is_mirrored_into_the_fleet_template_row_for_row` :766; `test_the_templates_mirrored_prose_matches_the_hubs` :785.
`scripts/enforcement/check_governance_tables.py`: grep `lane` → 0 (generic). The spec's own measurement that motivates all of it:
315 task closes, 77 spec closes, 9 refusals, 0 downgrade seeds since 2026-10-02 (`spec § Why this exists`).

## Self-audit

- Grounding passes: three `fabrik-researcher` seats (command_run.py gate path and dispatch; task_lane.py and the two test harnesses;
  hooks, report and the text graders), every anchor opened; the lead re-read `_task_size_gate`'s callers, the spec branch and the
  `_close` lane block. Found: the gate's refusal-row side effects (→ `_lane_facts`); the hook's no-import rule (→ text only); the
  eight table graders (→ Phase C rewrites them); `test_spec_plan_lane_text.py` carries no D-862 pins (D-862's row lists it, the
  content is prose in `fabrik-spec.md:19-55`) — the plan keeps that prose, not a phantom pin.
- (a) Coverage of "What we already agreed": R1 → Phase C steps 2–3; R2 → A steps 2–3; R3 → A step 4, B step 3; R4 → A step 6, Finish;
  R5 → A step 4 (fields), B step 2 (report); R6 → C step 3; approach C rejected → no model call anywhere (Global Constraints); infra
  follow-ups a–c → C step 3; `_task_size_gate` as the one gate path → A step 3 (`_lane_facts` shared, `admit` shared). No gap.
- (b) Cross-phase names: `LANE_TRIPS` (A) is read by C's grader; `lane_verdict`/`lane_outcome` (A) are read by B's `lanes()`; the
  `door` row kind (A) is counted by B; `enforce_mode(is_hub)` (A) is the only mode reader. Consistent.
- Fixed point: not yet — `/fabrik-plan-review` grades this plan with the spec and flips both.

## Residual unknowns

- **Resolved:** the gate seam (shared facts + `admit`, no shared side effects); the hook stays import-free; the replaced graders are
  enumerated; the `consumers=external` test is `admit`'s own (declared or `contract_hit`), no second definition.
- **Open, with its step:** the exact `now` outcome `grew` predicate (counted files > 5 or a new source file) is measured against the
  review-scoped record's covered files at close — Phase A step 4 reads `_close`'s surface list and pins the predicate in A8; if the
  record carries no file list for a scoped review, `grew` is `unknown` and the report says so. The `deny` flip after a week is its own
  D-row and commit, not this plan's.

## Coverage Checklist

| Class | Status |
|---|---|
| Hunt: `scripts/task_lane.py` — `lane_verdict`, `enforce_mode`, `LANE_TRIPS`; PURE kept | UNCHECKED |
| Hunt: `scripts/command_run.py` — `_lane_facts`, the `lane` verb, three door lookups, `_close` fields | UNCHECKED |
| Hunt: `scripts/command_feedback_report.py` — `_verdict_rows`, `lanes`, `--lanes` | UNCHECKED |
| Hunt: `.claude/hooks/final_gate_stop.py`, `.claude/hooks/skill_router.py` — the two strings | UNCHECKED |
| Hunt: the two contracts, three command sources, protocol doc, Front door — every changed claim against the code | UNCHECKED |
| Recurrence: fail-open/fail-closed — a swallowed error or an absent check that reads as success | UNCHECKED |
| Recurrence: boundary/sentinel/prefix — the file-set superset test, the `LV-` id, the prefix words | UNCHECKED |
| Recurrence: behavior-without-a-test — a contract row no test kills (mutation asserted) | UNCHECKED |
| Recurrence: denominator on every count — the `--lanes` ratios and the kill rule | UNCHECKED |

Rubric invocation (verbatim output — the gate reads the generated header):

```text
$ python3 scripts/review_rubric.py --changed scripts/command_run.py scripts/task_lane.py .claude/hooks/final_gate_stop.py .claude/hooks/skill_router.py scripts/command_feedback_report.py CLAUDE.md templates/governance/CLAUDE.md commands/_sources/fabrik-spec.md tests/test_command_run_lane_v2.py
# REVIEW RUBRIC — inject into EVERY finder prompt (generated by review_rubric.py)
# Honesty (L1): this arms the review — it raises compliance probability, it does not guarantee it.

## FLOOR — always injected, regardless of glob (spec L3; TOOLING surface)

### core/10-python.md
### 12-FACTOR (all twelve axes)

## MATCHED — packs whose globs hit the changed paths

### core/40-documentation.md  (hit: CLAUDE.md, commands/_sources/fabrik-spec.md, templates/governance/CLAUDE.md)
### core/45-testing-strategy.md  (hit: tests/test_command_run_lane_v2.py)
```
