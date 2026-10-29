# Plan — one door: the lane verb, three refusing starts, one rule (D-861)

Status: CONVERGED
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
ledger, one door lookup, two close fields), `scripts/command_feedback_report.py` ≈60 (the `verdicts` section), `.claude/hooks/final_gate_stop.py`
≈4 (one cause string), `.claude/hooks/skill_router.py` ≈6 (one directive string). Text: two contracts, three command sources,
`docs/reference/command-run-protocol.md`, `agents-fabrik-core.md`; graders in three test files.

## What this plan is

Three inline phases the executor codes in the main checkout (every code path here is a governance-sync path — `scripts/command_run.py`,
`scripts/task_lane.py`, `.claude/hooks/`, `templates/governance/` — so, as the venv plan did, phases A–C land as ONE commit after the
Finish review; D-369/D7):

- **A — the verb and the doors** (`spec § The delta` R2, R3, R4): `task_lane.py` gains the trip-list constant, a PURE `lane_verdict()`
  and the dated enforcement constant; `command_run.py` gains a `lane` verb that shares `_task_size_gate`'s fact-gathering and `admit`
  call without its refusal-row side effects, writes `~/.claude/state/lane-verdicts.jsonl`, and ONE lookup ahead of the three `start`
  branches checks the verdict in `dryrun`/`warn`/`deny`; the close records `lane_verdict`/`lane_outcome`. Red-first tests, replay pass.
- **B — the report, the hook, the router** (R3, R5): the `--lane` report's new `verdicts` section (verdict vs outcome per agent, fire
  rate per mode, the kill ratio); the Stop hook's `unreviewed-spontaneous` cause names the verb; the router's directive says "run the lane
  check first".
- **C — the rule text and its graders** (R1, R6): the three-question rule rendered from `LANE_TRIPS` replaces the six-row table and its
  four paragraphs in `CLAUDE.md` and `templates/governance/CLAUDE.md`; `/fabrik-spec` Phase 0, `/fabrik-task` § SIZE and
  `/fabrik-review-scoped`'s start point at the verb (and carry infra's three D-862 follow-ups); the nine table graders are rewritten to
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
- `lane_verdict`/`lane_outcome` on the close row and the `verdicts` section of the `--lane` report: `spec § The delta` R5.
- The command sources point at the verb; `/fabrik-spec` Phase 0 shrinks: `spec § The delta` R6.
- Approach C (a model judge) rejected; A (text only) rejected: `spec § Rejected alternatives`.
- Code owner infra, text owner kaizen: `docs/DECISIONS.md` D-861 (its where-cell); D-862's code is the base: `docs/DECISIONS.md` D-862.

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
- `scripts/task_lane.py` — `LANE_TRIPS: tuple[tuple[str, str, str], ...]`: the Q1 trip list as (key, text, how) triples, one per
  `chain:` route suffix `admit` returns (`:365-381`, no more and no fewer — the grader counts both) — `("contract", "a published name,
  URL or contract a shipped client reads moves or breaks — another repo or person must change BY HAND (a synced path reverts through
  the sync and does not count)", "executed: a contract path (`contract_hit`) or a declared consumers=external")`, `("appetite", "it
  will not finish in one session", "executed: --appetite over 240 min")`, `("oneway", "data others stored changes shape or is
  destroyed, or anything else a revert would not undo", "named: --oneway")`, `("tradeoffs", "two approaches the build itself cannot
  rank (a trade-off the build settles is ordinary task work)", "named: --tradeoff")` — the TEXT field is the Q1 clause verbatim,
  parentheticals included; `render_q1(trips=LANE_TRIPS) -> str` (PURE, same module) joins the texts as `That is: <t1>; <t2>; <t3>;
  <t4>.` and the Phase C grader compares that string to the contract's Q1 "That is:" sentence after whitespace normalisation
  (`" ".join(text.split())`), because the contract hard-wraps the sentence at the block's width — equality is token for token, not
  byte for byte, and the wrap is the contract's; the ONE source the contract text is rendered from (Phase C) and the verb's reasons
  are keyed on; `lane_verdict(declared, files, *, sync_hits, appetite, why, version,
  fix, docs_only, prefix) -> LaneVerdict` (frozen dataclass `lane: "now"|"task"|"spec"|"refused"`, `reason: str`, `review:
  "scoped"|"full"`, `trip: str | None`, `restart: str`) — PURE: `prefix in ("now","task","spec")` wins and sets `reason = "operator
  prefix"`; else ONE `admit` call decides — `v = admit({**declared, "decision": "no" if (fix or docs_only) else declared["decision"]},
  files, sync_hits=…, appetite=…, why=…, version=…)` — so Q1 runs BEFORE `--fix`/docs-only can say `now` (a fix on a contract path or
  over the appetite is spec work, as the table's precedence rule says today): a `chain:` route ⇒ `spec` with `trip` the route's
  suffix and `reason = v.reason` (a v1-pinned repo's `chain: files`, `:299`, reads `spec` with `trip: "files"`, a key outside
  `LANE_TRIPS` — the grader compares the v2 suffixes only, `:365-381`); `right-now + …` ⇒ `now` with `review = v.review` (`:389-394`);
  `lane` ⇒ `task` with `reason = "no measurable trip and no --oneway/--tradeoff named"`; `refused` (only a malformed `--appetite` can
  reach it — the verb's declaration is always complete) ⇒ `LaneVerdict("refused", v.reason, …)` so the verb prints the gate's own
  refusal and writes no row; `docs_only` is ONE predicate, the file suffixes — every rel ends in `.md`, `.txt` or `.rst` (`counted`
  is NOT it: `counted("README.md")` is True); `restart` is the ready start line
  (`python3 scripts/command_run.py start --command fabrik-task --phases 5 --terminal "<…>" --surface "<…>" --file … --declare <the
  full declaration>` for task; for spec the same with `--command fabrik-spec` plus `--why "<the --oneway/--tradeoff text, or
  'operator prefix: spec'>"`, because `_spec_admit_v2` refuses a `lane` route without `--why` (`scripts/command_run.py:4102-4107`) and
  that start writes D-862's `spec-start` override row as today; nothing for now). `enforce_mode(is_hub: bool, override: str | None =
  None) -> str` reads `_LANE_ENFORCE = {"hub": "warn", "fleet": "dryrun", "since": "2026-10-15"}` — a constant, no env read in this
  module, no `deny_after_days` (nothing would read it: the flip is a reviewed commit against the bar in `spec § The delta` R4); `override in ("dryrun","warn","deny")` wins (the caller passes it; PURE stays intact); `deny` is a later
  commit that edits the constant (its own D-row).
- `scripts/command_run.py` — `_lane_facts(paths, declare, sid) -> LaneFacts` (dataclass: `root, rels, answers, malformed, sync_hits,
  version, switch, dirty, docs_only`): the FACT-gathering that `_task_size_gate` does today at `:4160-4313` (paths → rels, the
  `--declare` parse against `_TASK_DECLARE_KEYS` + `consumers`, the dirty check, the sync-filter hits, `lane_version`), extracted so
  `_task_size_gate` and the verb compute the same facts — the flag GUARD (`:4177-4197`: `missing --file`, `missing --declare keys`,
  `must be yes|no`) and the dirty-path REFUSAL (`:4269-4274`) stay in `_task_size_gate`, which reads the facts and refuses as today;
  `_task_size_gate` keeps its signature, its refusal rows and its prints (every `spec_gate` and lane-v2 test stays green). The `lane`
  subparser (`parents=[common]`; `--ask` required, `--file` append (required), `--declare` OPTIONAL, `--appetite`, `--oneway TEXT`,
  `--tradeoff TEXT` (a non-empty string each — argparse refuses an empty value), `--fix`): the verb COMPLETES the declaration before
  `admit` sees it — defaults `decision=yes` (`no` under `--fix`), `consumers=internal`, `heavy=no`, `mechanism=no`, `oneway=yes` +
  `why` from `--oneway`, `tradeoffs=yes` + `why` from `--tradeoff`, and any `--declare k=v` given overrides a default (so
  `consumers=external` is declared here, as `admit` requires, never measured twice); `docs_only` by the suffix rule above; a pre-lock
  reader like `line` (`:3582`) inside its own refusing `try` (`main`'s outer handler fails
  soft to rc 0, `:3618-3620`); it prints ONE line `LANE: <lane> — <reason>` plus the `restart` line, and appends `{kind: "verdict", id:
  "LV-<8 hex>", ts, session, repo, agent, ask, files, declared, flags, lane, reason, trip, review, mode, mode_source, head}` (`head`
  = `git rev-parse HEAD` at verb time, the base `grew` reads from) to
  `_lane_verdicts()` = `_state_dir().parent / "lane-verdicts.jsonl"` (`:88-92`, `:3998` precedent). `_lane_verdict_for(sid, lane,
  rels, chosen=None) -> dict | None`: the newest `verdict` row of this session with that lane whose `files` ⊇ `rels` — with `chosen`
  (`--lane-verdict <id>`) that one row, and ONLY if its lane matches and its `files` ⊇ `rels`, else a `mismatch` (the same door
  outcome as no verdict, its text naming the uncovered paths); any read error (absent, unreadable or malformed ledger) returns `None`
  after a one-line `NOTE — lane-verdicts.jsonl unreadable (<ExcName>)`, so a broken ledger is a missing verdict, never an exception
  the start `try` (`:5411-5419`) turns into a refusal in `dryrun`/`warn`. ONE door lookup for the three commands, the FIRST statement
  INSIDE the `try:` at `:5365` (never before it — an exception outside the `try` escapes to `main` as rc 0 with no record, the case
  `:5411-5418` warns about), ahead of the `if _seed is not None` chain (so a flagless spec start, which falls to the `elif _cmd !=
  _TASK_COMMAND` arm at `:5379`, is covered too): `if _cmd in _LANE_DOORS and _seed is None and not _nested_under(rec)`
  (`_LANE_DOORS = ("fabrik-spec", "fabrik-task", "fabrik-review-scoped")`; `_nested_under(rec)` is true only when `rec` — the
  record `:5452` reads to park a parent — is `running` AND its `command` is `fabrik-task` or `fabrik-execute-plan`, the two callers
  whose phase reviews open `/fabrik-review-scoped` inside them (`commands/_sources/fabrik-task.md:165-166`,
  `fabrik-execute-plan.md:59`); any other running parent, `/fabrik-review` included, leaves the start top-level, so a stray record
  cannot exempt a door — a NESTED start has no verdict of its own and is never refused: it writes a `door` row with `outcome:
  "nested"` and `parent: <the parent command>` and proceeds in every mode; under `deny` an unguarded check would have refused every
  one of the ~315 task reviews a week and buried the fire rate); a `/fabrik-task --from-downgrade <LR-id>` start is satisfied by
  that refusal row ONLY when the door finds it in `_lane_ledger()` (`:3998`; a row of this repo with `route` `chain: …` or
  `spec-start`) — a well-formed id with no row is `missing`, since the gate's own check at `:4023-4027` (`_REFUSAL_ID.fullmatch`)
  tests the SHAPE alone and runs after the door — giving `outcome: "downgrade"`, the spec run's own verdict, because the session
  holds only a `spec` verdict then; the rels are `start`'s `--file` list (empty for `/fabrik-review-scoped`, which
  refuses `--file` at `:5381` — its verdict is matched on lane alone); `mode = tl.enforce_mode(is_hub, os.environ.get("FABRIK_LANE_ENFORCE"))`
  (the env read lives HERE, not in `task_lane.py`; `mode_source` records `constant` or `override`); no verdict/mismatch → `dryrun`: a
  ledger `door` row only (`{kind: "door", ts, session, repo, agent, command, files, mode, mode_source, outcome: "missing"|"mismatch"}`,
  same file — the append is BEST-EFFORT in every mode: its own `try`, a failed write prints `NOTE — lane-verdicts.jsonl not written
  (<ExcName>)` and never refuses the start; only a missing verdict refuses, and only in `deny`); `warn`: the row plus the refusal text
  printed as `NOTE — <cmd>: no lane verdict for this start — run python3 scripts/command_run.py lane --ask "…" --file … first, or
  pass --lane-verdict <LV-id> for a verdict another window recorded` and the start proceeds; `deny`: `_refuse(...)` with the same
  text. A verdict
  found writes a `door` row with `outcome: "ok"` and the verdict id. `--resume-from` (`:5366-5367`) skips the lookup, as it skips the
  gate. `start` gains `--lane-verdict ID`. The record keeps `lane_verdict: <id>` next to the `lane_gate` stamp (`:5510-5518`), only on
  the three commands (the `:5506-5509` rule). `_close` (`:6854-6880`): `lane_verdict` and `lane_outcome` on the three commands' rows —
  in this precedence, the first that holds: `handed-off` (a task closed by `handoff` whose close text carries the `UPGRADE:` prefix —
  the `upgrade:` field the parse at `:4596-4599` writes, the one the 16 measured upgrades carry; a handoff without it falls through);
  `grew` (a `now` verdict whose record is `/fabrik-review-scoped`: the paths of the commits between the verdict's `head` and the
  close's HEAD that carry this record's `Agent-Name` trailer, ANCHORED — `git log <head>..HEAD --format=%H --grep='^Agent-Name:
  <agent>$'` (unanchored, `kaizen` would match `kaizen-2`); skipped, falling through to the next outcome, when `_agent_name()`
  (`:2689-2708`) returns `""` (an empty pattern would match every commit) — then the existing `--name-status` reader at `:4622-4642`
  over each, a READ that needs no `--commit` flag, which `_task_close_fields` refuses on every command but the task's (`:5161-5168`)
  — exceed `_FULL_REVIEW_FILES` by `tl.counted` or add a source file by `tl.is_new_source`; two windows bound to the same role name
  are counted together (the mirror, stated in the docstring: the role name is the finest attribution a commit carries); an
  uncommitted close reads nothing and falls through — the cobra, written in the field's docstring: commit after the close and `grew`
  never fires; the counter is the Stop hook's own commit-at-task-end cause, which forbids that order); `small-no-trip` (a spec whose
  close row carries `size: small` (`:6853`) and whose JOINED verdict row has `trip: null` — the verdict named no trip; `lane_gate`
  is not the key: a flagless spec start is covered by any spec verdict and stamps `lane_gate: none` whatever the verdict tripped);
  `small-named` (the same close on a verdict whose `trip` is `oneway` or `tradeoffs` — the one-word `--oneway` the spec's R5 names
  as the cheapest way through, now counted under the agent's name); `prefix` (the verdict row's reason was the operator prefix);
  else `ok`. The close row also copies the verdict's `flags` (so the report reads a `--fix` share per agent) and, for a spec
  started from a prefix verdict, the restart line passes `--lane-verdict <LV-id>` and `--why "operator prefix: spec"` so the
  `spec-start` override row D-862 writes (`:4122-4139`) carries that literal `why` and the report splits it from agent overrides.
- `is_hub` = `_repo_root()` equals `FABRIK_HUB_ROOT` (default `/opt/fabrik`) or `_main_checkout(root)` does — the two hub TESTS
  `_sync_verdict` runs first (`:3675-3678`, `:3693`), lifted into a small `_is_hub(root)` helper; NEVER `_sync_verdict` itself,
  which also answers True for any repo carrying `.fabrik/synced.lock` (`:3681-3688`) and would put the whole fleet in `warn`;
  computed once in the verb and the doors. Tests set `FABRIK_HUB_ROOT=<fixture
  repo>` to read `hub`, and `FABRIK_LANE_ENFORCE=deny` to read `deny` (both through `_cr`'s env; `command_run.py` runs as a
  subprocess there, so a monkeypatch cannot reach `_LANE_ENFORCE`). COBRA of the override: `FABRIK_LANE_ENFORCE=dryrun` in a live
  shell silences `deny`; the `door` row records `mode_source: override`, the `--lane` report counts overrides per agent, and the
  constant's docstring says so.

**Consumes:** `task_lane.admit`, `record_refusal`'s row shape (`:400-423`), `_lane_module()`, `_lane_version_at`, `_refuse`, the
`start`/`handoff`/`_close` seams named above.

**Mirror (named):** `tests/test_command_run_lane_v2.py` `spec_gate` tests (:1164-1348) and every `_started_v2` test — unchanged
behaviour, re-run; `tests/test_lane_replay.py` — the 300-commit replay (`classify_commit` rows, files per commit) gains a
`lane_verdict()` pass; the 21-row tasks fixture (`tests/fixtures/lane_replay_tasks.json`, read by `json.loads` at
`tests/test_lane_replay.py:94,111`, never by `lane_replay_capture.py`) is NOT touched — its rows carry no files or declared answers, so
an `expected_lane` there would be synthesised from the row it grades; `docs/reference/command-run-protocol.md:52-59` (the
`start`/`handoff` rows gain `--lane-verdict`, a `lane` row, the two feedback fields — Phase C).

0. Probe: `.venv/bin/python -m pytest -q tests/test_command_run_lane_v2.py -k spec_gate` → 9 passed (the D-862 baseline this
   phase must keep); `.venv/bin/python -m pytest -q tests/test_lane_replay.py` → passed; record both in Evidence.
1. **Write the failing tests first** in `tests/test_command_run_lane_v2.py` (rows A1–A12), reusing `_cr`/`_rec`/`_start` (imported
   from `tests/test_command_run_fabrik_task.py` at `:17`; `_cr` pins `COMMAND_RUN_DIR`, `KAIZEN_EVENTS_DIR`, `HOME`, `CLAUDE_SESSION_ID`
   and takes `extra_env=` — `test_command_run_fabrik_task.py:96,111`) and the file's own `_ledger`/`_V2` (`:19-69`, `:277-281`); add
   `_verdicts(run_dir)` reading `run_dir.parent / "lane-verdicts.jsonl"`; a unit test file `tests/test_task_lane_verdict.py` for
   `lane_verdict()` and `enforce_mode()` driving `scripts/task_lane.py` by path, every trip and the prefix. Run → red (the verb and
   the functions do not exist); paste the red summary into Evidence.
2. `scripts/task_lane.py`: `LANE_TRIPS`, `render_q1()`, `LaneVerdict`, `lane_verdict()`, `_LANE_ENFORCE`, `enforce_mode()` — after `record_refusal`,
   before `classify_commit`; the module docstring's bullet list gains two lines (`lane_verdict`, `enforce_mode`); the `AFTER-EDIT`
   header gains `tests/test_task_lane_verdict.py`. Gate: `.venv/bin/python -m pytest -q tests/test_task_lane_verdict.py` → green.
3. `scripts/command_run.py`: extract `_lane_facts` from `_task_size_gate` (`:4160-4313`, facts only — the guard and the dirty
   refusal stay) and call it there (behaviour identical: `-k spec_gate` and the lane-v2 suite stay green — run them, paste the count);
   add `_lane_verdicts()`, `_lane_verdict_for()`, the `lane` subparser (`:3414-3420` is the shape) and its pre-lock dispatch (`:3582`
   is the position); the verb completes the declaration, computes `LaneFacts`, calls `tl.lane_verdict(...)`, prints, appends. Gate:
   A1–A5 green.
4. The ONE door lookup before the branch chain (`:5365`) with `enforce_mode(is_hub, override)`; `--lane-verdict` on `start`; the
   record stamp; the `_close` fields (`:6854-6880`). Gate: A6–A12 green; the whole file `.venv/bin/python -m pytest -q
   tests/test_command_run_lane_v2.py tests/test_command_run_fabrik_task.py` green.
5. Replay: `tests/test_lane_replay.py` gains `test_the_replayed_commits_get_a_lane_verdict` — the same 300-commit rows
   `classify_commit` is graded on, each commit's file list through `lane_verdict()` with the verb's default declaration, pinning: no
   `refused`, every `chain:` admit route reads `spec` with its `trip` equal to the route suffix, every docs-only commit reads `now`,
   and the lane distribution as a fixture constant (re-pinned by a D-row when the trip list changes). The tasks fixture is untouched.
   Gate: `.venv/bin/python -m pytest -q tests/test_lane_replay.py` → green.
6. The constant: `_LANE_ENFORCE["hub"] = "warn"`, `["fleet"] = "dryrun"`, `["since"]` = the merge date; its
   docstring states the cobra (`--fix` on everything; a one-word `--oneway`; `FABRIK_LANE_ENFORCE=dryrun` in a live shell) and the
   counter (`lane_outcome` and `mode_source` per agent in the `--lane` report).
7. Closing sequence: (1) the phase gate above green; (2) `python3 scripts/enforcement/check_doc_sync.py` + the protocol doc rows deferred
   to Phase C are noted; (3) `/fabrik-review-scoped` on this phase's surface, run to its coverage-adjudicated exit, every finding
   FIXED/REFUTED; (4) no commit yet — D7: one commit after Finish.

### Behavior Contract — Phase A

- A1 **Given** `--ask "fix the flaky login test" --file tests/test_login.py --fix` and NO `--declare`, **When** `lane` runs, **Then**
  it prints `LANE: now —` with `review: scoped`, and appends one `verdict` row with `lane: now` and the completed declaration
  (`decision=no`) (`spec § The delta` R2; `scripts/task_lane.py:313` `admit`, `:389-394`).
- A2 **Given** `--file src/a.py` with no flags and no trip, **When** `lane` runs, **Then** it prints `LANE: task — no measurable trip
  and no --oneway/--tradeoff named` and the ready `start --command fabrik-task … --declare decision=yes,…` line, and the row's
  `restart` equals that line (`spec § The delta` R2).
- A3 **Given** `--file specs/services/x.yaml`, **When** `lane` runs, **Then** it prints `LANE: spec — tripped: contract:`, the row
  carries `trip: contract`, and its `restart` is a `start --command fabrik-spec` line carrying `--why` (`scripts/task_lane.py:167`
  `contract_hit`, `:365-368`; `scripts/command_run.py:4102-4107`).
- A4 **Given** `--oneway "the row ids are public"` on `src/a.py`, **When** `lane` runs, **Then** it prints `LANE: spec — tripped:
  oneway` and the row's `declared` carries `oneway=yes` with that text as `why`; **Given** `--appetite 0`, **Then** it prints the
  gate's own `--appetite must be a positive integer` refusal and writes NO row (`scripts/task_lane.py:356-362`, `:371-381`).
- A5 **Given** `--ask "spec: …"`, **When** `lane` runs, **Then** the row reads `lane: spec, reason: operator prefix` whatever the files
  (`spec § The delta` R2).
- A6 **Given** `start --command fabrik-spec` with no flags and no verdict row, **When** it runs with `FABRIK_HUB_ROOT=<the fixture repo>`
  (`warn`), **Then** the start proceeds, prints `NOTE — fabrik-spec: no lane verdict`, and a `door` row with `outcome: missing`
  lands; **Given** no `FABRIK_HUB_ROOT` match (the fleet, `dryrun`) only the row lands; **Given** `FABRIK_LANE_ENFORCE=deny`, the
  start is REFUSED naming the verb and `--lane-verdict`, and the row reads `mode_source: override` (`spec § The delta` R3, R4;
  `scripts/command_run.py:5365`, `:3675-3678`).
- A7 **Given** a `task` verdict for `src/a.py` and a `start --command fabrik-task --file src/a.py --file src/b.py`, **When** it runs in
  `deny`, **Then** it is refused naming `src/b.py` (file set not covered), is refused the same with `--lane-verdict <that id>`, and
  succeeds with `--lane-verdict <an id whose files cover both>` (`spec § The delta` R2 binding).
- A12 **Given** `FABRIK_LANE_ENFORCE=deny`, a running `/fabrik-task` record and no `now` verdict, **When** `start --command
  fabrik-review-scoped` runs (nested), **Then** it proceeds and the `door` row reads `outcome: nested, parent: fabrik-task`; **Given**
  the running record is `/fabrik-review` instead, **Then** the start is REFUSED (not a nesting parent); **Given** a `spec`-only
  session and `start --command fabrik-task --from-downgrade <the LR- id a prior spec start's refusal row minted in the fixture
  ledger>`, **Then** it proceeds with `outcome: downgrade`; **Given** a well-formed `LR-` id no ledger row carries, **Then** it is
  REFUSED as `missing` (`scripts/command_run.py:5452-5459`, `:3998`, `:4023-4027`).
- A8 **Given** a task started on a `task` verdict and closed by `handoff --reason "UPGRADE: tradeoffs …"`, **When** the feedback row is
  written, **Then** it carries `lane_verdict: <id>` and `lane_outcome: handed-off`; a `handoff` without the prefix reads `ok` (`spec §
  The delta` R5; `scripts/command_run.py:4596-4599`, `:6854-6880`).
- A9 **Given** a `now` verdict for one `.md` (row `head` = HEAD then) and a `/fabrik-review-scoped` record under `CLAUDE_AGENT=kaizen`,
  and one commit after it carrying `Agent-Name: kaizen` that adds `src/new.py`, **When** it closes, **Then** `lane_outcome: grew`;
  **Given** the same commit under `Agent-Name: kaizen-2`, or no bound agent name, **Then** `ok` (`scripts/command_run.py:2689-2708`,
  `:4622-4642`; `scripts/task_lane.py` `is_new_source`).
- A10 **Given** a `spec` verdict by prefix (`trip: null`) and a `/fabrik-spec` close whose row carries `size: small`, **When** it
  closes, **Then** `lane_outcome: small-no-trip` (it outranks `prefix`); **Given** an `oneway`-tripped verdict closing `size: small`,
  **Then** `small-named`; **Given** a `contract`-tripped verdict and a FLAGLESS spec start (`lane_gate: none`) closing `size: small`,
  **Then** `ok` — the key is the verdict's `trip`, never `lane_gate` (`scripts/command_run.py:6853`).
- A11 **Given** a verdict whose reason is the operator prefix and an ordinary `done`, **When** it closes, **Then** `lane_outcome: prefix`
  (`spec § The delta` R5).

## Phase B — the report, the hook, the router

Appetite: 60

**Interfaces — Produces:**
- `scripts/command_feedback_report.py` — `_verdict_rows(path)` (the `_refusal_rows` shape, `:2001-2018`, over `lane-verdicts.jsonl`
  beside the refusals ledger); the EXISTING `--lane` report (`lane()` `:2129`, `_lane_text` `:2309`, flag `:2561-2566` — the task
  lane's refusal/downgrade measures) gains one section, `doc["verdicts"]`: per agent and per repo `{verdicts: {now, task, spec},
  fix_share: <verdict rows whose flags carry --fix> / verdicts, outcomes: {ok, grew, handed-off, small-no-trip, small-named, prefix},
  doors: {missing, mismatch, nested, downgrade, ok} × {dryrun, warn, deny} fire counts (top-level = all but nested), overrides: <door
  rows with mode_source: override>, prefix_overrides: <spec-start rows whose why starts "operator prefix:"> split from the D-862
  override count, kill: {handed_off, joined, verdicts} — the ratio over task verdicts JOINED to a closed task row, both printed as
  `3/12 joined (of 15 verdicts)`, over_route: (small-no-trip + small-named) / spec verdicts}`, joining verdict rows to feedback
  rows on `lane_verdict`; `_lane_text` prints it after the downgrade block, with `KILL:` and `OVER-ROUTE:` lines when tripped
  (`spec § The delta` R4's bars); `--json` carries it. NO new flag — a `--lanes`
  beside `--lane` is a confusion the spec's R5 is amended to avoid (this review). The kill rule prints as `KILL: task→spec hand-offs
  3/12 (25%) > 20% — revert the doors to warn` when tripped.
- `.claude/hooks/final_gate_stop.py:1394` — the cause text becomes `a review of {N} file(s) — /fabrik-review-scoped; run python3
  scripts/command_run.py lane --ask "<the request>" --file … first and take the lane it names` (text only; no import).
- `.claude/hooks/skill_router.py:788-790` — `build_injection` reads `This request matches /{skill} (Stage: …) — run the lane check first
  (python3 scripts/command_run.py lane --ask "…" --file …), then invoke the skill its verdict names, or state in one line why it does
  not apply.`; the docstring at `:5-6` paraphrases the same.

**Consumes:** Phase A's ledger row shape and the two feedback fields.

**Mirror (named):** `tests/test_command_feedback_report_lane.py` fixtures (`_row`, `_refusal`, `_write`, `_lane`, `_doc`, `:1-90`) —
extended with `_verdict(...)`; every existing `--lane` test there keeps its asserts (the new section is additive);
`tests/test_skill_router_hook.py:290` `test_build_injection_nested_shape_and_directive_wording` (the one pin on `build_injection`'s
text); the Stop hook's cause tests (grep `unreviewed-spontaneous` in tests/).

1. **Failing tests first**: `tests/test_command_feedback_report_lane.py` rows B1–B3 (a synthetic verdict ledger + feedback rows →
   `--lane --json` doc's `verdicts` section; the kill line); `tests/test_skill_router_hook.py` row B4 (the directive text, next to
   `:290`); the hook cause test row B5. Run → red; paste the summary.
2. `command_feedback_report.py`: `_verdict_rows`, the `verdicts` section in `lane()`, its block in `_lane_text`. Gate: `.venv/bin/python
   -m pytest -q tests/test_command_feedback_report_lane.py` → green.
3. `final_gate_stop.py:1394` and `skill_router.py:788-790`. Gate: `.venv/bin/python -m pytest -q tests/test_skill_router_hook.py
   tests/test_final_gate_stop*.py -k "lane or unreviewed or injection"` → green.
4. Closing sequence: (1) gates green; (2) `check_doc_sync.py`; (3) `/fabrik-review-scoped` on this phase's surface to its exit;
   (4) no commit yet.

### Behavior Contract — Phase B

- B1 **Given** three verdict rows (now, task, spec) joined to three feedback rows, **When** `--lane --json` runs, **Then**
  `doc["verdicts"]["agents"][a]["verdicts"] == {"now":1,"task":1,"spec":1}` and `outcomes` counts the three classes, while every
  key the existing `--lane` tests read is unchanged (`spec § The delta` R5).
- B2 **Given** 15 task verdicts of which 12 joined a closed task and 3 of those `handed-off`, **When** `--lane` runs, **Then** the
  text carries `KILL:` with `3/12 joined (of 15 verdicts)`; **Given** 2 of 5 spec verdicts closed `small-no-trip` or `small-named`,
  **Then** it carries `OVER-ROUTE:` (`spec § The delta` R4).
- B3 **Given** `door` rows in two modes, one `nested`, one with `mode_source: override`, and one `spec-start` row whose `why` is
  `operator prefix: spec`, **When** `--lane` runs, **Then** `doors` counts them per mode and outcome with `nested` outside the
  top-level total, `overrides` reads 1, `prefix_overrides` reads 1 and `fix_share` is printed (the fire rate the `deny` flip reads).
- B4 **Given** a prompt the router matches to `/fabrik-spec`, **When** `build_injection` runs, **Then** its text contains `run the lane
  check first` and `command_run.py lane` (`spec § The delta` R3; `.claude/hooks/skill_router.py:788-790`).
- B5 **Given** a record-less editing turn, **When** the Stop hook assembles causes, **Then** the `unreviewed-spontaneous` text names
  `command_run.py lane` (`.claude/hooks/final_gate_stop.py:1394`).

## Phase C — the rule text and its graders, then Finish

Appetite: 120

**Interfaces — Produces:**
- `CLAUDE.md` § Orient step 0 and `templates/governance/CLAUDE.md`: the six-row table, the precedence paragraph, the D-859 paragraph, the
  no-code clause and the tripwire (`CLAUDE.md:75-92`, `templates/governance/CLAUDE.md:66-83`) replaced by the rule block of `spec § The
  delta` R1, byte-identical in both, its Q1 list rendered from `LANE_TRIPS` (the test renders the constant and compares); the project
  parentheticals rows 1/1b carry today collapse into the review line's words — the template's vendored-`libs/` trigger
  as "vendored"; the hub's D-137 note is no review trigger and stays in § Behavior — and row 1b's D-892 scope (an
  explicit full-review ask or a named code or config change; naming alone never routes up a docs- or ledger-only diff)
  is carried as the spec's review line words it. Every pointer at the retired text is retargeted in step 2:
  "lane row 1b" (§ Completion Contract 1a in both contracts, `commands/_sources/fabrik-review-scoped.md:2` and `:15`,
  `commands/_sources/fabrik-task.md:44`, `.windsurf/rules/core/50-code-review.md:79`) → "the lane rule's review
  line"; "no-code-surface diff" in the same sites → "docs- or ledger-only diff"; "row 5 of § Orient step 0's lane
  table" (§ 1a in both) and "the lane table" (`commands/_sources/fabrik-task.md:32`) → "§ Orient step 0's lane rule"
  (Q1 where the pointer meant row 5); `commands/_sources/fabrik-spec.md:53-55`'s `decision=no` sentence ("row 4b", "the
  lane table's precedence rule for 4b with 1 or 1b") → "a `now` verdict (Q3): right-now and the review the lane rule's
  review line selects"; "row 5's module tests" (`commands/_sources/fabrik-review-scoped.md:15`) and "the lane table's row-5 module tests"
  (`.windsurf/rules/core/50-code-review.md:77`) → "Q1 of the lane rule"; "a row-6 verdict" (`CLAUDE.md:227`,
  `templates/governance/CLAUDE.md:423`) → "a `task` verdict"; `docs/reference/fabrik-task-lane.md:4`, `:18`, `:37`
  ("the lane table", "lane rows") → "the lane rule", and `:55`'s "the old lane table" → "the old lane text".
- `commands/_sources/fabrik-spec.md:23-55` Phase 0: the DOWNGRADE check becomes "this run's `spec` verdict (or `--lane-verdict`) is
  present — the start refused otherwise under `deny`, printed the verb under `warn`; its `--oneway`/`--tradeoff` reason is § Why's first
  line; pass `--file`/`--declare` at start (infra follow-up a); a `spec-start` row is read for its `verdict` and `restart`, never assumed
  a task restart (b); a `spec-start` row whose spec closed `done` is skipped — join on the close row's `spec_refusal` (c); an `LR-` row
  still drives the D9 handoff." `commands/_sources/fabrik-task.md:30-40` § SIZE opens with "paste the start line the lane verb printed"; its UPGRADE block
  (`:224-233`) adds, before the `/fabrik-spec` restart, "re-run the lane verb with the trip you crossed (`--oneway`/`--tradeoff`, or
  the contract path / appetite) — the spec start needs that `spec` verdict".
  `commands/_sources/fabrik-review-scoped.md:15-30`: the record opens from a `now` verdict; the classification step keeps its order.
- `docs/reference/command-run-protocol.md:52-59`: the `lane` verb row, `--lane-verdict`, the ledger, `lane_verdict`/`lane_outcome`.
  `agents-fabrik-core.md:17` Front door: three tiers restated as the three questions, one line.
- `tests/test_governance_template_split.py`: the nine table graders (`:461-848`, grounded by name in Evidence — eight hub/mirror
  tests plus the template's own GFM render at `:837`) retired and replaced by: the rule block present and identical in both contracts;
  its Q1 "That is:" sentence equals `render_q1()` of `scripts/task_lane.py::LANE_TRIPS` after whitespace normalisation (import by
  path) and `LANE_TRIPS`' keys equal the set of
  `chain:` suffixes `admit` can return (a trip added to one side reds the test); the review line names exactly `admit`'s `full`
  reasons (`sync`, `heavy`, `migration`, `files > 5`) plus the contract's vendored/auth/schema/operator-named words; the tie-break sentence
  present; the block renders as a fenced code block in GFM (markdown-it) in BOTH files (replacing `:730` and `:837`); the handle-now
  pointer constant `_LANE_POINTER` (`:392`, read by `:502` for the hub and `:865` for the template — ONE edit retargets both) becomes
  "§ Orient step 0's lane rule". D-892's grader (`test_operator_named_work_is_scoped_at_row_1b_and_pointed_at_elsewhere`,
  outside `:461-848`) is retargeted, not retired: its clause assert reads the review line in both contracts and its
  pointer asserts read "the lane rule's review line"; a sweep assert finds no match of `(?i)lane[ -]table|lane rows?|\brows? ?[0-9]|
  \brow-[0-9]|no-code-surface` in the two contracts, the three command sources, `50-code-review.md` or
  `docs/reference/fabrik-task-lane.md` (panel, both seats). It proves only the spellings it matches: the cheapest pass
  without the outcome is a respelled pointer ("tier 1b", "the 1b test"), which the positive pointer asserts and the
  review catch; a bare `1b`/`4b` token is not swept — measured, it fires on 7 legitimate "Phase 1b" lines in
  `fabrik-spec.md`.
  `tests/test_fabrik_task_queue_pass.py:124` (`heavy=yes` includes operator-named work) reads "(the lane rule's
  review line)". `tests/test_spec_plan_lane_text.py`
  Phase 0 pins (`:87-125`, `:275-305`) rewritten to the verdict wording (the D9 `--from-downgrade` restart and `## RESUME` pins stay).
- Mail to fabrik-lib: the rule block verbatim for its hand-kept CLAUDE.md (replacing its table at ~:379-394).

**Consumes:** `LANE_TRIPS` (Phase A); the `--lane` report's `verdicts` section (Phase B).

**Mirror (named):** `scripts/enforcement/check_governance_tables.py` — generic overflow checker, no lane knowledge (grep `lane` = 0): the
rule block is fenced, not a table, so it reads nothing; `check_governance_drift` anchors — none in the replaced text (verified by grep
of the § UNIVERSAL list); `docs/superpowers/specs/2026-10-02-fabrik-task-feature-lane-design.md` (frozen; superseded in part by
D-861's row, not edited); `tests/test_fabrik_task_source.py` SIZE_CAP (D-296: raise by a D-row if § SIZE grows — the two-line change
is within the cap or the row says so).

1. **Failing graders first**: the new `test_governance_template_split.py` tests and the rewritten `test_spec_plan_lane_text.py` pins
   → red on the current text; paste.
2. The two contracts (rule block; `python3 -c` renders `LANE_TRIPS` to compare); `agents-fabrik-core.md:17`; every retargeted
   pointer (Produces, first bullet). Gate: `.venv/bin/python -m pytest -q tests/test_governance_template_split.py
   tests/test_fabrik_task_queue_pass.py` → green; `python3 scripts/enforcement/check_governance_tables.py --strict` → OK.
3. The three command sources and the protocol doc; `python3 commands/assemble_commands.py --check` (DIFFERS rows for this branch's own
   edits are expected in a worktree; in the main checkout render → `--check` → commit). Gate: `.venv/bin/python -m pytest -q
   tests/test_spec_plan_lane_text.py tests/test_fabrik_task_source.py tests/test_review_scoped_queue_pass.py
   tests/test_governance_template_split.py tests/test_fabrik_task_queue_pass.py` → green (step 3 rewrites lines the pointer asserts read).
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

- **Given** both contracts, **When** the grader runs, **Then** the rule block is byte-identical in both and its Q1 "That is:" sentence
  equals `render_q1()` of `scripts/task_lane.py::LANE_TRIPS` after whitespace normalisation (`spec § The delta` R1).
- **Given** the rule block, **When** rendered with markdown-it, **Then** it is a fenced code block inside item 0 and no lane table remains
  (`tests/test_governance_template_split.py:730` precedent).
- **Given** `commands/_sources/fabrik-spec.md` Phase 0, **When** the pins run, **Then** it says the `spec` verdict is present or the start
  refused, names `--file`/`--declare` at start, reads a `spec-start` row's `verdict`/`restart`, skips a row whose spec closed `done`,
  and keeps the `--from-downgrade <refusal id>` restart; `commands/_sources/fabrik-task.md`'s UPGRADE block names the verb re-run
  (`spec § The delta` R3, R6; infra follow-ups a–c).
- **Given** `agents-fabrik-core.md:17`, **When** read, **Then** the Front door names the three questions and `/fabrik-task` under doubt.
- **Given** the whole-plan diff, **When** `final_gate.py --check --json` and `check_convergence.py` run after the Finish review, **Then**
  both are green and the receipt is CONVERGED with `confirmed: 0 · fixed: 0`.

## File Scope (owned paths)

- scripts/task_lane.py
- scripts/command_run.py
- scripts/command_feedback_report.py
- .claude/hooks/final_gate_stop.py
- .claude/hooks/skill_router.py
- CLAUDE.md
- templates/governance/CLAUDE.md
- agents-fabrik-core.md
- commands/_sources/fabrik-spec.md
- commands/_sources/fabrik-task.md
- commands/_sources/fabrik-review-scoped.md
- .windsurf/rules/core/50-code-review.md
- docs/reference/fabrik-task-lane.md
- docs/reference/command-run-protocol.md
- tests/test_task_lane_verdict.py
- tests/test_command_run_lane_v2.py
- tests/test_lane_replay.py
- tests/test_command_feedback_report_lane.py
- tests/test_skill_router_hook.py
- tests/test_governance_template_split.py
- tests/test_spec_plan_lane_text.py
- tests/test_fabrik_task_queue_pass.py
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
scripts/command_run.py:5365:        try:
scripts/command_run.py:5381:                    return _refuse("REFUSED — --file/--declare belong to --command fabrik-task")
scripts/command_run.py:5395:                        "REFUSED — --appetite/--why/--from-downgrade belong to --command fabrik-task"
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
CLAUDE.md:75:   **The LANE table — apply it to the SMALLES
CLAUDE.md:88:   **Under doubt the lane is `/fabrik-task`.** 
CLAUDE.md:90:   **No code surface at all** (docs, ledgers or
CLAUDE.md:92:   **Tripwire:** if the first draft cites a scr
templates/governance/CLAUDE.md:66:   **The LANE table — ap
templates/governance/CLAUDE.md:79:   **Under doubt the lane 
templates/governance/CLAUDE.md:81:   **No code surface at al
templates/governance/CLAUDE.md:83:   **Tripwire:** if the fi
```
Graders keyed on the table's literal shape (grounder C, all in `tests/test_governance_template_split.py`): `_lane_table` :449-458;
`test_the_lane_table_carries_the_six_tests_and_its_verdict_row` :461; `test_the_lane_tables_verdict_row_names_a_command_that_exists`
:474; `test_the_heavy_surface_list_names_a_governance_sync_path` :487 (kept — § 1a, not the table);
`test_the_handle_now_clause_points_at_the_lane_table_instead_of_restating_a_test` :502 (retargeted);
`test_the_lane_tables_verdicts_match_the_size_gates_own_routing` :523; `test_the_lane_table_states_the_precedence_the_gate_actually_evaluates`
:605; `test_the_hubs_lane_table_matches_lane_v2` :672; `test_the_lane_table_renders_as_a_table_for_every_gfm_reader` :730;
`test_the_lane_table_is_mirrored_into_the_fleet_template_row_for_row` :771; `test_the_templates_mirrored_prose_matches_the_hubs` :790;
`test_the_template_renders_its_lane_table_for_every_gfm_reader` :837 (the template's GFM render — found by this plan's review, outside
the first grounding's range). Kept, like :487: `test_the_templates_heavy_surface_list_names_a_governance_sync_path` :851 (§ 1a);
`test_the_templates_outcome_ii_points_at_the_lane_table_and_keeps_all_three` :865 reads `_LANE_POINTER` (:392) with :502 — retargeted
once. Nine retired, three touched. D-892's grader `test_operator_named_work_is_scoped_at_row_1b_and_pointed_at_elsewhere` :1965
is retargeted, and `tests/test_fabrik_task_queue_pass.py:124` pins `fabrik-task.md:44`'s "(lane row 1b)" — both read the pointers.
`scripts/enforcement/check_governance_tables.py`: grep `lane` → 0 (generic). The spec's own measurement that motivates all of it:
315 task closes, 77 spec closes, 9 refusals, 0 downgrade seeds since 2026-10-02 (`spec § Why this exists`).

## Self-audit

- Grounding passes: three `fabrik-researcher` seats (command_run.py gate path and dispatch; task_lane.py and the two test harnesses;
  hooks, report and the text graders), every anchor opened; the lead re-read `_task_size_gate`'s callers, the spec branch and the
  `_close` lane block. Found: the gate's refusal-row side effects (→ `_lane_facts`); the hook's no-import rule (→ text only); the
  nine table graders (→ Phase C rewrites them); `test_spec_plan_lane_text.py` carries no D-862 pins (D-862's row lists it, the
  content is prose in `fabrik-spec.md:19-55`) — the plan keeps that prose, not a phantom pin. `/fabrik-plan-review` round 1 (two
  finder seats, 17 candidates, 15 confirmed by execution) moved the door lookup ahead of the branch chain, split the flag guard out
  of `_lane_facts`, keyed `LANE_TRIPS` on `admit`'s four route suffixes, made `enforce_mode` testable through two env seams read in
  `command_run.py`, dropped the tasks-fixture replay, folded `--lanes` into `--lane`, and corrected `tests/test_skill_router_hook.py`.
  The Opus + Fable design panel (both `sound-with-changes`, every concern ACCEPTED) added: top-level-only door checks with `nested`
  and `downgrade` outcomes (A12), the UPGRADE block's verb re-run, `small-named`, the joined kill denominator and the over-route
  ratio, the `--fix` share, the prefix-override split, the `deny` bar in R4, `>5 files` in the review line, Q3 rewritten, the
  LANE_TRIPS texts made byte-exact, `_is_hub` kept off `_sync_verdict`, `deny_after_days` dropped, and four stale cites.
- (a) Coverage of "What we already agreed": R1 → Phase C steps 2–3; R2 → A steps 2–3; R3 → A step 4, B step 3; R4 → A step 6, Finish;
  R5 → A step 4 (fields), B step 2 (report); R6 → C step 3; approach C rejected → no model call anywhere (Global Constraints); infra
  follow-ups a–c → C step 3; `_task_size_gate` as the one gate path → A step 3 (`_lane_facts` shared, `admit` shared). `spec §
  Validation`: red-first graders → A1–A12, B1–B5, C rows; the 300-commit replay → A step 5; the parent spec's V7–V10 (`admit`'s own
  tests) → A step 0's `-k spec_gate` baseline and step 3's lane-v2 re-run. No gap.
- (b) Cross-phase names: `LANE_TRIPS` (A) is read by C's grader; `lane_verdict`/`lane_outcome` (A) are read by B's `verdicts` section;
  the `door` row kind and `mode_source` (A) are counted by B; `enforce_mode(is_hub, override)` (A) is the only mode reader, its env
  seams `FABRIK_HUB_ROOT`/`FABRIK_LANE_ENFORCE` read in `command_run.py` only. Consistent.
- Fixed point: not yet — `/fabrik-plan-review` grades this plan with the spec and flips both.

## Residual unknowns

- **Resolved:** the gate seam (shared facts + `admit`, no shared side effects); the hook stays import-free; the replaced graders are
  enumerated; the `consumers=external` test is `admit`'s own (declared or `contract_hit`), no second definition.
- **Resolved by the review:** the `now` outcome `grew` is measured over the agent's own commits between the verdict's recorded `head`
  and the close's HEAD (anchored `Agent-Name` trailer match, the existing `--name-status` reader) and pinned in A9; `small-no-trip`
  keys on the joined verdict's `trip`, pinned in A10. No `unknown` outcome exists.
- **Not this plan's:** the `deny` flip after a measured week is its own D-row and commit.

## Pass Ledger

The joint `Size: small` loop's ledger (`/fabrik-plan-review`; the panel table, the ask ↔ spec table and the
rubric paste live in `docs/development/reviews/2026-10-14-one-door-lane-plan-review.md`). Each row's end hash is the pin the next round read; the start hash is the pin
the round read — both taken with that round's own ledger rows absent (the anti-cheat rule), which is why the
hashes here differ from the committed file's.

| Pass | seats · slices | counters | method | md5 (start → end) |
|---|---|---|---|---|
| Pass 1 | opus×1 (Global Constraints, Context Ledger, Digest, Phase A, File Scope, Evidence, Coverage Checklist; spec R2–R4, § Validation) + sonnet×1 (every other section of both) · full pass | found: 17, new: 17, confirmed: 15, fixed: 15, unexecuted: 0 | method: citation — every candidate executed by the lead against master f0a6d1326 (the spec branch at :5368, `_task_size_gate`'s guard at :4177-4197, `admit`'s routes at :365-381, the fixture reader at `tests/test_lane_replay.py:94`, `ls tests` for the router test, the template GFM grader at :824); 2 PLAUSIBLE folded into the same fix | plan 93009503 · spec 0f184f53 → plan d0275fb7 · spec 8f1fe0eb |
| Pass 2 | opus×1 + sonnet×1 (round-1 slice owners) · delta over the round-1 fix hunks | found: 7, new: 5, confirmed: 6, fixed: 6, unexecuted: 0 | method: re-derivation — each seat re-executed its own ledger (A 12/12, B 5/5): 15 CLOSED, 2 residues, 4 defects in the fix (`--fix` skipped Q1 — `admit` with decision=no on a contract path executed to `chain: contract`; two `docs_only` predicates — `counted("README.md")` executed True; the lookup placed outside the `try`; no outcome precedence) | plan d0275fb7 · spec 8f1fe0eb → plan 51887d0c · spec e09d6cdd |
| Pass 3 | opus×1 + sonnet×1 (round-1 slice owners) · delta over the round-2 fix hunks | found: 4, new: 1, confirmed: 4, fixed: 4, unexecuted: 0 | method: re-derivation — A 11/11 and B 5/5 re-executed; the four confirmed were all in round-2 text (`small-no-trip` keyed on `lane_gate`, the `Agent-Name` grep unanchored and empty on an unbound name — `_agent_name()` at :2689-2708 executed, the import cite `:3` where the file reads `:17`, a stale Residual paragraph); the scope-growth stop fired (D-355) | plan 51887d0c · spec e09d6cdd → plan 81f60c22 · spec e09d6cdd |
| Pass 4 | opus×1 + sonnet×1 (round-1 slice owners) · remainder round — the round-3 fixed set only | found: 0, new: 0, confirmed: 0, fixed: 0, unexecuted: 0 | method: re-derivation — A re-derived every anchor its slice cites (task_lane :5-8, :67, :72, :167, :299, :313, :356-362, :365-381, :389-394, :400-423; command_run :88-92, :2638, :3414-3420, :3582, :3618-3620, :3675-3678, :3693, :3988, :3998, :4065-4077, :4102-4107, :4122-4145, :4160-4313, :4596-4599, :4614-4642, :5161-5168, :5365-5419, :5506-5518, :6853-6880), B 3/3 (the Residual paragraph, A9/A10, the outcome names across Phases A and B) | plan 81f60c22 · spec e09d6cdd → plan 81f60c22 · spec e09d6cdd ✓ |
| Pass 5 | opus×1 + sonnet×1 (round-1 slice owners) · delta re-opened by the design panel (Opus, Fable: both `sound-with-changes`; 16 concerns ACCEPTED, 0 rejected — `docs/development/reviews/2026-10-14-one-door-lane-plan-review.md` § Panel) | found: 3, new: 3, confirmed: 3, fixed: 3, unexecuted: 0 | method: re-derivation — A 11 changes CLOSED and 3 confirmed in the fold (any `running` record exempted a door, :5452 executed; the downgrade id accepted on shape alone, `_REFUSAL_ID` at :4023-4027; the renderer unnamed so "byte for byte" was unbuildable), B 6/6 (fabrik-task.md:224-233, D-861's where-cell, :4122-4139); the stop fired again | plan 1e36e1c2 · spec b47ee234 → plan 717f472c · spec d0e492f2 |
| Pass 6 | opus×1 + sonnet×1 (round-1 slice owners) · remainder round — the round-5 fixed set only | found: 1, new: 0, confirmed: 0, fixed: 0, unexecuted: 0 | method: re-derivation — A 3/3 (`_nested_under` against fabrik-task.md:165-166 and fabrik-execute-plan.md:59, the ledger lookup at :3998 with :4023-4027 named shape-only, `render_q1` token-for-token against R1's hard wrap), B 3/3 (Phase A/C/spec R1 agree on `render_q1`); the one candidate is RECORDED below, never edited in a closing round; standing clean since Pass 4: every class of the ledger | plan 717f472c · spec d0e492f2 → plan 717f472c · spec d0e492f2 ✓ |
| Pass 7 | opus×1 (spec rule block, Row map, Phase C Produces + grader bullet) + sonnet×1 (every other section of both) · delta re-opened by D-892 (W-cc43f23e: operator-named work folded into R1's review line) | found: 8, new: 6, confirmed: 6, fixed: 6, unexecuted: 0 | method: citation — every candidate executed by the lead against the live tree: `tests/test_fabrik_task_queue_pass.py:124` pins `fabrik-task.md:44` (unlisted); the step-2 gate ran a grader whose sources step 3 edited; "row 5 of … lane table" / "the lane table" pointers unretargeted; the no-code set pointed at a paragraph R1 retires; anchors drifted +4/+5/+13 since Pass 6 (`grep -n` executed); the template's vendored-`libs/` trigger dropped by a byte-identical block | plan 28f0cdf4 · spec 408ec22f → plan c0da172c · spec ecdbdbc3 |
| Pass 8 | opus×1 + sonnet×1 (round-1 slice owners) · delta over the round-7 fix hunks | found: 4, new: 3, confirmed: 3, fixed: 3, unexecuted: 0 | method: re-derivation — A 5/5 and B 3/3 CLOSED; 3 confirmed: File Scope listed `test_fabrik_task_queue_pass.py` three times (own fix), `fabrik-review-scoped.md:15` "row 5's" outside the sweep, the step-3 gate did not re-run the pointer graders (own fix); 1 PLAUSIBLE refuted (vendored cannot fire in the hub, D-137) | plan c0da172c · spec ecdbdbc3 → plan 8b745a2d · spec ecdbdbc3 |
| Pass 9 | opus×1 + sonnet×1 (round-1 slice owners) · delta over the round-8 fix hunks | found: 2, new: 2, confirmed: 2, fixed: 2, unexecuted: 0 | method: re-derivation — 3/3 CLOSED; 2 confirmed outside the phrase sweep ("the lane table's row-5" at `50-code-review.md:77`, "a row-6 verdict" at `CLAUDE.md:227` / template `:423`); the sweep became a regex and the lead executed it over the 6 files: 24 hits, each named | plan 8b745a2d · spec ecdbdbc3 → plan 1e4b93b1 · spec ecdbdbc3 |
| Pass 10 | opus×1 + sonnet×1 (round-1 slice owners) · delta over the round-9 fix hunk | found: 1, new: 1, confirmed: 1, fixed: 1, unexecuted: 0 | method: re-derivation — 2/2 CLOSED; 1 confirmed: `fabrik-spec.md:53-55`'s `decision=no` sentence ("row 4b") was covered only implicitly by the Phase 0 rewrite — named | plan 1e4b93b1 · spec ecdbdbc3 → plan 0b2a409e · spec ecdbdbc3 |
| Pass 11 | opus×1 + sonnet×1 (round-1 slice owners) · remainder round — the round-10 fixed set only | found: 0, new: 0, confirmed: 0, fixed: 0, unexecuted: 0 | method: re-derivation — A diffed od-pins4 → od-pins5 (only :368-371 changed, no retarget lost or doubled), B re-ran the regex: 17 hit lines outside the replaced block, 0 unmapped | plan 0b2a409e · spec ecdbdbc3 → plan 0b2a409e · spec ecdbdbc3 ✓ |
| Pass 12 | opus×1 + sonnet×1 (round-1 slice owners) · delta re-opened by the design panel (Opus, Fable: both APPROVE with changes — `docs/development/reviews/2026-10-14-one-door-lane-plan-review.md` § Panel, D-892 fold) | found: 1, new: 1, confirmed: 0, fixed: 0, unexecuted: 0 | method: re-derivation — A re-ran the case-insensitive regex over the 7 files: 40 hits, 14 in the excluded ranges, 26 each named; `docs/reference/fabrik-task-lane.md:4/18/37/55` cited right; B: the doc once in File Scope, 0 tests read it before this plan; 1 PLAUSIBLE refuted ("the old lane text" at :55 stays true for a pre-sync window); standing clean: every class of the ledger | plan 14843280 · spec ecdbdbc3 → plan 14843280 · spec ecdbdbc3 ✓ |

## Residual

| Id | Verdict |
|---|---|
| A1-F11 | FIXED r1 (PLAUSIBLE in round 1 — the door lookups sat inside the start `try`, so a malformed ledger would refuse in dryrun; the plan reads the ledger in its own guard and appends best-effort) |
| A1-F12 | FIXED r1 (PLAUSIBLE in round 1 — the outcome rules had no file list; round 2 confirmed the remainder, `_task_close_fields` refuses `--commit` off the task command at :5161-5168, and round 3 closed it on the agent's own commits between the verdict's head and HEAD) |
| B6-R1 | RECORDED — hygiene false positive (Pass 6 residue after the scope-growth stop: Phase C step 2 says "`python3 -c` renders `LANE_TRIPS` to compare", the shell form of the `render_q1()` the Produces bullet and the contract row name two paragraphs above; not contradictory, not edited in a closing round) |
| O4-bar | RECORDED — by design (D-865 — a per-agent numeric `small-named` bar was not set: no data yet; the over-route ratio is reported and the week's D-row sets any bar) |

## Coverage Checklist

| Class | Status |
|---|---|
| Hunt: `scripts/task_lane.py` — `lane_verdict`, `enforce_mode`, `LANE_TRIPS`; PURE kept | FIXED r1 (`LANE_TRIPS` keyed on `admit`'s four route suffixes, `:365-381`; `enforce_mode(is_hub, override)` with the env read moved to `command_run.py` so `:5-8` PURE holds) · FIXED r2 (one `admit` call decides before `--fix`; `docs_only` by suffix) · FIXED r5 (`render_q1()`, the clause texts verbatim) — executed against scripts/task_lane.py:299-423 |
| Hunt: `scripts/command_run.py` — `_lane_facts`, the `lane` verb, the one door lookup, `_close` fields | FIXED r1 (the guard and dirty refusal stay in `_task_size_gate` `:4177-4197`/`:4269-4274`; one lookup ahead of the chain at `:5365`; `--lane-verdict` must cover the files; the verb completes the declaration) · FIXED r2-r3 (lookup inside the `try`; `grew` over the agent's own commits with an anchored trailer; `small-no-trip` on the verdict's trip) · FIXED r5 (`_nested_under` = a running `fabrik-task`/`fabrik-execute-plan` parent, `:5452-5459`; the downgrade row looked up in `_lane_ledger()` `:3998`) |
| Hunt: `scripts/command_feedback_report.py` — `_verdict_rows`, the `--lane` report's `verdicts` section | FIXED r1 (`--lanes` folded into the existing `--lane` report, `lane()` `:2129`, `_lane_text` `:2309`) · FIXED r5 (joined kill denominator, `fix_share`, `prefix_overrides`, `over_route`, `nested`/`downgrade` door outcomes; B1–B3 rewritten) |
| Hunt: `.claude/hooks/final_gate_stop.py`, `.claude/hooks/skill_router.py` — the two strings | CLEAN (.claude/hooks/final_gate_stop.py:1390-1395 and :566-570, .claude/hooks/skill_router.py:788-790 and :25-32 re-read in Passes 1 and 4; the hook change is text only, no import, no mode read — spec R4 corrected to say so in Pass 1) · FIXED r1 (the test file is `tests/test_skill_router_hook.py:290`, not a non-existent `test_skill_router.py`) |
| Hunt: the two contracts, three command sources, protocol doc, Front door — every changed claim against the code | FIXED r1 (nine table graders of tests/test_governance_template_split.py:456-837 enumerated, the template GFM render at :824 included; `_LANE_POINTER` :387 retargeted once for :497 and :852) · FIXED r5 (`fabrik-task.md:224-233` UPGRADE block names the verb re-run; R1's review line adds `files > 5`, Q3 rewritten; `render_q1` compared after whitespace normalisation) |
| Recurrence: fail-open/fail-closed — a swallowed error or an absent check that reads as success | FIXED r2 (an unreadable verdict ledger reads as a missing verdict with a NOTE, never an exception the start `try` at scripts/command_run.py:5411-5419 turns into a refusal; the door-row append is best-effort) · FIXED r5 (any `running` record no longer exempts a door; a well-formed `LR-` id without a ledger row is `missing`, not `downgrade`) |
| Recurrence: boundary/sentinel/prefix — the file-set superset test, the `LV-` id, the prefix words | FIXED r1 (`--lane-verdict <id>` must also cover the file set, A7) · FIXED r3 (the `Agent-Name` grep anchored `^…$` — `kaizen` matched `kaizen-2`, an empty name matched every commit; `small-no-trip` keyed on `trip: null`, not the `lane_gate` sentinel `none`) · FIXED r5 (`_REFUSAL_ID` at :4023-4027 named shape-only) |
| Recurrence: behavior-without-a-test — a contract row no test kills (mutation asserted) | FIXED r1-r2 (A4 rewritten to a reachable refusal; A6 to seams a subprocess test can set — `FABRIK_HUB_ROOT`, `FABRIK_LANE_ENFORCE`; A9–A11 added; the `LANE_TRIPS`↔`admit` route-count grader) · FIXED r5 (A12 — nested, non-nesting parent, minted downgrade id, well-formed id without a row; the `small-named` case in A10) |
| Recurrence: cost/quota accounting — pool units scored, native seats counted, a limit at its edges | CLEAN (docs/development/plans/2026-10-14-plan-2-one-door-lane.md File Scope touches no seat, dispatch, quota or budget path; the review itself dispatched 2 finder + 2 panel seats, each stamped with `command_run.py dispatch --seats 2`; no pool) |
| Recurrence: proxy-as-evidence — the real check EXECUTED, not read | CLEAN (docs/development/plans/2026-10-14-plan-2-one-door-lane.md and the spec: every candidate in Passes 1–6 executed by a seat probe or the lead — `admit` with decision=no, `counted("README.md")`, `md5sum -c`; check_plan_quality.py, check_plans.py and plan_appetite.py rc 0 after every round; review_rubric.py re-run after the File Scope change, header byte-identical) |
| Recurrence: denominator on every count — the `verdicts` section's ratios, the joined kill denominator, the over-route ratio | FIXED r5 (the kill ratio over task verdicts JOINED to a closed task, both numbers printed `3/12 joined (of 15 verdicts)`; `nested` outside the top-level door total; the over-route ratio over spec verdicts) · CLEAN (docs/development/plans/2026-10-14-plan-2-one-door-lane.md Evidence: `grep -c fabrik-task` = 0 of 1 file, 21 fixture rows by load, nine graders of a 444-852 span by name) |

Rubric invocation (verbatim output — the gate reads the generated header):

```text
$ python3 scripts/review_rubric.py --changed scripts/task_lane.py scripts/command_run.py scripts/command_feedback_report.py .claude/hooks/final_gate_stop.py .claude/hooks/skill_router.py CLAUDE.md templates/governance/CLAUDE.md agents-fabrik-core.md commands/_sources/fabrik-spec.md commands/_sources/fabrik-task.md commands/_sources/fabrik-review-scoped.md docs/reference/command-run-protocol.md tests/test_task_lane_verdict.py tests/test_command_run_lane_v2.py tests/test_lane_replay.py tests/test_command_feedback_report_lane.py tests/test_skill_router_hook.py tests/test_governance_template_split.py tests/test_spec_plan_lane_text.py
# REVIEW RUBRIC — inject into EVERY finder prompt (generated by review_rubric.py)
# Honesty (L1): this arms the review — it raises compliance probability, it does not guarantee it.

## FLOOR — always injected, regardless of glob (spec L3; TOOLING surface)

### core/10-python.md
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

### core/40-documentation.md  (hit: CLAUDE.md, agents-fabrik-core.md, commands/_sources/fabrik-review-scoped.md)
- > **⚠️ `docs/OPERATIONS.md` + `docs/DEPLOYMENT.md` are FLEET-AI INTERFACES, not just docs (D-065).**
- **Tier-1 (author → verify → converge; the author leg is NATIVE while the pool is OFF, D-181 — `scripts/doc_reconcile.py`'s pool author cannot dispatch):** for each **mechanically-detectable** doc whose Doc-Sync trigger fired (`docs/QUICKSTART.md` · `docs/CONFIGURATION.md` · `docs/data-contract.md` · `docs/SERVICES.md` · `docs/OPERATIONS.md` — the reliable-signal subset), `scripts/doc_reconcile.py` dispatches a cheap OpenRouter-pool author (`libs.subagents`, `pick_models("docs")`) to emit a **minimal structured patch**, **verifies it before applying** (a symbol cross-check catches invented endpoints; the orchestrator injects a higher-assurance native-Claude verify), and loops to a zero-edit round. Runs per phase in `/fabrik-execute-plan`; never blocks (fail-safe). The other docs (CHANGELOG, INDEX, FEATURES, RESILIENCE, PORTS, the READMEs, `db/schema.sql`, …) have no reliable mechanical content-signal → they rely on the touch-on-change backstop below + your own edit (force-update, not force-correct).
- The SSOT is the type-aware registry (`scripts/enforcement/_doc_registry.py::PROJECT_DOCS`) — this table is its project-facing rendering, kept in step, never a second truth. `/fabrik-plan-after-chat` (the plan set's spine + tickets — the ticket-format authority) injects these rows per ticket as its `Docs:` line.
- Standalone work (not plan execution) → `Agent-Role: primary`. Trailers go below a blank line, above `Co-Authored-By`. ⚠️ The trailer block must be its OWN paragraph with NO blank line inside it: git parses only the LAST paragraph, and only if it is all-trailers. A blank line before `Co-Authored-By:` demotes everything above it to prose; so does a prose line glued to the top of the block. Measured 2026-08-15: 200 of the last 200 hub commits carried `Agent-Role:` and only 10 parsed, because the old example here shipped the blank line.
- **⚠️ Link it or it is decoration.** *Measured:* requests for files that do NOT exist came ~zero from AI bots — agents never go looking. It follows (inference, not measurement) that a file only gets read when something points at it: reference it from the docs index or README.
- ⚠️ **In the hub (`/opt/fabrik`) `llms.txt` is GENERATED** (`scripts/generate_capability_index.py`, refreshed daily) — never hand-edit it there; change the generator. A project has no such generator; an `llms.txt` it ships, hand-written or built by its own code, is its own.
- either way. Cheap and reversible — never at the expense of `OPERATIONS.md`/`DEPLOYMENT.md`, which are the load-bearing agent interfaces (D-065).
- **No skipped heading levels** — `##` to `###`, never `##` to `####`
- **Fenced code blocks only** — never indented code (AI treats it inconsistently)

### core/45-testing-strategy.md  (hit: tests/test_command_feedback_report_lane.py, tests/test_command_run_lane_v2.py, tests/test_governance_template_split.py)
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
# promote-to-check_* tail (36 greppable mandates) elided here — the header, FLOOR and MATCHED sections above are verbatim
```
