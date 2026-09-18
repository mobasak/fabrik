# Plan 1 (2026-09-18) — the `/fabrik-task` lane: SIZE at `start`, DESIGN in the record, one own-commit re-measure

Status: CONVERGED
Profile: standard
**Owner:** —
**Spec:** `docs/superpowers/specs/2026-09-17-fabrik-task-lane-design.md` — CONVERGED at a40d75870 by the operator's ruling (D-293; the three rulings D-289/D-290/D-291, the MIRROR confirmed by D-292).

## Goal

Build the lane the spec designs (spec § Goal): a `/fabrik-task` command whose SIZE gate is the `start` verb of the fleet-synced `scripts/command_run.py`, whose design lives in the run record, whose review is the unchanged `/fabrik-review-scoped`, and whose close re-measures the run's OWN commit against its declaration and writes two feedback-ledger fields — plus the two CLAUDE.md copies carrying the six-test decision rule, § 1a's new trigger and the two sizing pointers, and one mail to `fabrik-lib`.

## What we already agreed (from the spec + this conversation)

- The decision rule, its six tests and verdict row, and the moment it applies — spec § The decision rule (rule 1, 1b, 2–6; the MIRROR paragraph).
- SIZE is the `start` itself with a stated inventory (two flag guards, three path/state checks, two lane tests, five declared answers; fourteen refusal outcomes over eight templates (the fourteenth is the internal-exception arm this review added, with its own template)) — spec § Chosen approach, Phase 0.
- Phase 2's six design fields in the record via `step --design <path>`, refused over 2,000 characters — spec § Chosen approach, Phase 2.
- `/fabrik-review-scoped` invoked unchanged at phase 4; the heavy review only on a mid-run sync/heavy crossing — spec § Chosen approach, Phase 4 and UPGRADE.
- Phase 5's re-measure as SIX INVARIANTS with graders — the operator's ruling makes them this plan's Phase A acceptance criteria (D-293): spec § Chosen approach, Phase 5, (i)–(vi).
- Two row fields only, `oversized_mini` and `upgrade`, read by `command_feedback_report.py --queue`'s existing header — spec § Validation V4, D-290 (U10).
- § 1a gains "a governance-sync path" in all three contract copies; fabrik-lib by mail — spec § Documentation landing sites, D-289 (U8).
- The two inline sizing clauses become pointers to the step-0 table; the three MIRROR consequences are confirmed — spec § The decision rule (the pointer paragraph), D-291, D-292.
- The router row is RESOLVED-NEGATIVE; no `skill_router.py` change — spec § Awareness, its D-k (a letter internal to the spec's § Decisions taken, folded into ledger row D-293 — there is no `D-k` in `docs/DECISIONS.md`).
- Cost and profile: five code/contract files plus two tests, `Profile: standard` because `command_run.py` is a fleet-synced heavy surface owing the full `/fabrik-review` — spec § Cost.
- Validation the build owns: V0's project-repo measurement (U28), V1's backtest (U29), V2's dogfood, V3's cobra probe — spec § Validation, § Open unknowns.
- Operator this turn: *"yes as usual until it converges then run necessary commands till you finish the entire execution"* — the chain runs to the end without an operator gate between review and execution (the ruling of 2026-09-18; the design approval is D-293).

## Intake Inventory

| I# | Item (anchored) | Disposition | Where |
|---|---|---|---|
| I1 | *"run necessary commands till you finish the entire execution"* | IN | this plan → `/fabrik-plan-review` → `/fabrik-execute-plan` in one chain |
| I2 | *"yes as usual until it converges"* — the spec approval | IN | D-293; spec CONVERGED at a40d75870 |
| I3 | U19's three MIRROR consequences, confirmed | IN | T04a/T04b (the pointers), D-292 |
| I4 | U8 — § 1a gains "a governance-sync path" in three copies | IN | T04a (hub), T04b (template), T04b (the mail to fabrik-lib) |
| I5 | U10 — two row fields, existing reader | IN | T01b (writer), T02 (reader) |
| I6 | the six phase-5 invariants as Phase A acceptance criteria | IN | T01b Behavior Contract |
| I7 | V0's project-repo measurement before the sync (U28) | IN | T05 |
| I8 | V1's backtest over the 24 lane-choice commits (U29) | IN | T05 |
| I9 | V2's dogfood run on a real candidate | IN | T05 |
| I10 | V3's cobra probe | IN | T05 |
| I11 | the router row | OUT-OF-SCOPE | RESOLVED-NEGATIVE by the spec (§ Awareness, its internal D-k — folded into ledger row D-293) with its return bar; no ticket |
| I12 | the 23 unanswered `/fabrik-spec-review` feedback verdicts this chain produced | OUT-OF-SCOPE | `python3 scripts/command_feedback_report.py --queue fabrik-spec-review` is the destination; `/fabrik-command-improve fabrik-spec-review` after this chain |
| I13 | 14 sibling WIP files dirty in the shared tree | IN | § Global Constraints (never staged, never `noqa`'d) |
| I14 | the spec's own residual: phase-5 edge cases that graders settle | IN | T01b's graders are the settlement; spec § Review line |

Intake: 14 items — 12 IN, 2 OUT-OF-SCOPE (each named above), 0 ASK.

## Ticket Board

| Ticket | Title | Depends | Parallel | State | Commit |
|---|---|---|---|---|---|
| T01a | `command_run.py` — SIZE at `start` (`--file`/`--declare`, the inventory) + `step --design` | — | ⚡ | ⬜ | |
| T01b | `command_run.py` — `--commit` on the close verbs, the own-commit re-measure, the two row fields | T01a | ⛓️ | ⬜ | |
| T02 | `command_feedback_report.py --queue` header: the two series + the adoption share | T01b | ⛓️ | ⬜ | |
| T03 | the command source `commands/_sources/fabrik-task.md`, its render, the docs rows | T01b | ⚡ | ⬜ | |
| T04a | hub `CLAUDE.md`: the lane table, § 1a's trigger, the HANDLE-NOW pointer | T03 | ⛓️ | ⬜ | |
| T04b | `templates/governance/CLAUDE.md`: the same table + trigger, outcome (ii)'s pointer; the fabrik-lib mail | T04a | ⛓️ | ⬜ | |
| T05 | Integration: receipt, whole-plan gate + review, docs-review, the sync, V0/V1/V2/V3 | T02, T04b | ⛓️ | ⬜ | |

**Breadth advisory, adjudicated (`check_ticket_breadth.py --plan-dir` 2026-09-18 flagged T01a score 9 · T01b score 9 (7 before round 1 added two graded behaviours)):** both are KEPT, not split — their behaviours are one coupled invariant apiece. T01a's eight rows are the single guard CHAIN the spec fixes in ORDER (flag guards → path/state checks → lane tests + declared answers); splitting it would put two halves of one ordering contract in two tickets and add a third serialized merge on the same fleet-synced file. T01b's rows ARE the operator's Phase A acceptance-criteria SET (D-293) and are read together; the split the advisory suggests would split a ruling. The advisory's own calibration (recall 2/3, precision 0.50, ρ=0.45) is a prompt to look, and looking is what this line records.

## Merge Order

1. T01a
2. T01b
3. T02
4. T03
5. T04a
6. T04b
7. T05

Serialized: scripts/command_run.py — T01a T01b
Serialized: CLAUDE.md — T04a T04b
Serialized: tests/test_governance_template_split.py — T04a T04b

## Interfaces

- **T01a → T01b:** `rec["declared"]` — a dict `{files: [<repo-relative path>…], decision, heavy, mechanism, oneway, tradeoffs: "yes"|"no", sha: <hex or "unavailable">, sync_test: "ok"|"unavailable"}` persisted by `start` (T01a Produces; T01b Consumes `files` and `sync_test` at close — `sha` is the START-time HEAD, recorded for the coroner and for a human reading the record, and is deliberately NOT what invariant (ii) compares against, which is `rec["started_epoch"]`). Seam test: T01b's grader starts a `fabrik-task` record through the real `start` and reads `declared` back from the record json.
- **T01a → T01b:** `rec["design"]` — the text `step --design <path>` stored (≤ 2,000 chars). Its concrete reader is `command_run.py status`, which prints the WHOLE record (`:2527-2528`, `json.dumps(load(sid))`) and so needs no change; the spec's reason for the field is durability — OUT and TERMINAL have no other home once the scratchpad is swept, and the coroner/resume read the record, not the file. No seam test beyond T01a's own.
- **T01b → T02:** the feedback-ledger row keys `oversized_mini` (a string: `0` · `<n> · commit=<sha> · paths=<p1,p2,p3>` — this order DIVERGES from the CONVERGED spec's Phase 5 (vi), deliberately and under D-294; see T01b step 3 (vi) · `unmeasurable=<no-commit|no-git|sync_test-unavailable>`) and `upgrade` (a string token, e.g. `sync`, `heavy`, `mechanism`, or absent). Seam test, owned by T02: a row written by the real `command_run.py done --commit …` in a throwaway `COMMAND_RUN_DIR` + ledger is read by `queue()` and counted.
- **T01a/T01b → T03:** the CLI lines the source prints (`start --file … --declare …`, `step --design`, `done --commit …`). Seam test, owned by T03: every `command_run.py <verb> …` line the source carries parses under the real parser (`--help` accepts the flags; a refused flag fails the test).
- **T03 → T04a/T04b:** the rendered `/fabrik-task` command exists (`~/.claude/commands/fabrik-task.md`) before the contract tables name it. Seam test, owned by T04a: the lane table's `/fabrik-task` cell is a name `commands/_sources/` carries.

## Behavior Contract

- **Given** `start --command fabrik-task` with no `--file`, **When** it runs, **Then** it exits 1 with `REFUSED — fabrik-task: missing --file` and no record opens — and an exception raised anywhere inside the lane block exits 1 with `REFUSED — fabrik-task: start could not complete (<exception class>)` too, never rc 0 with no record (`scripts/command_run.py:2557-2559`) (scripts/command_run.py:2360-2368; spec § Chosen approach, Phase 0)
- **Given** `start --command fabrik-review --file a.py`, **When** it runs, **Then** it exits 1 with `REFUSED — --file/--declare belong to --command fabrik-task` and every other command's start output is byte-identical to today's (scripts/command_run.py:2360-2368; spec § Chosen approach, Phase 0)
- **Given** a declared path that matches the governance-sync regex read from the hub's `.pre-commit-config.yaml` `- id: governance-sync` block, **When** `start` runs with `mechanism=no`, **Then** it exits 1 with `REFUSED — fabrik-task: sync → right-now + /fabrik-review`; with `mechanism=yes` also declared the lane named is `/fabrik-spec` (scripts/governance_sync_postcommit.sh:28-30; .pre-commit-config.yaml:149-155; spec § The decision rule)
- **Given** a declared path that is tracked, present and modified, or present and untracked, **When** `start` runs, **Then** it exits 1 with the dirty-at-start message; an absent declared path starts (scripts/command_run.py:2583, :2623-2663; spec § Chosen approach, Phase 0)
- **Given** a valid declaration, **When** `start` succeeds, **Then** the record carries `declared` with the seven keys and `sha`, and stdout carries `RECORD: <started_at>` after the pinned line (scripts/command_run.py:2636, :2682; spec § Chosen approach, Phase 0)
- **Given** the stdlib extraction of the `files:` scalar, **When** compared to PyYAML's read of the same file, **Then** they are equal on the live file, and an absent or empty scalar yields `sync_test: unavailable` plus the stderr line `⚠ fabrik-task: sync lane test SKIPPED (cannot read the governance-sync filter)`, never an empty regex and never a silent skip (scripts/governance_sync_postcommit.sh:44; spec § Chosen approach, Phase 0)
- **Given** `step --phase 2 --design <path>` on a `fabrik-task` record, **When** the file is ≤ 2,000 characters, **Then** `rec["design"]` holds its text and no later `step` overwrites it (a second `--design` is kept out with a stderr NOTE); over 2,000, or on a path that cannot be read, it is REFUSED with the phase NOT advanced (scripts/command_run.py:2370-2377, :1602; spec § Chosen approach, Phase 2)
- **Given** a `fabrik-task` record in a repo with no commits, **When** `start` runs, **Then** the record carries `sha: unavailable` and the dirty check is skipped (scripts/command_run.py:2636; spec § Chosen approach, Phase 0)
- **Given** a `fabrik-task` record with `declared.files = [a]` and a commit that changed `a` and added `b`, **When** `done --commit <that sha>` runs, **Then** the ledger row carries `oversized_mini: 1 · commit=<sha> · paths=b` (scripts/command_run.py:3121, :3655-3676; spec § Chosen approach, Phase 5 (iii)–(vi))
- **Given** the same record and a commit that changed only `a`, `CHANGELOG.md` and `docs/FEATURES.md`, **When** `done --commit` runs, **Then** the row carries `oversized_mini: 0` (the Doc Sync Matrix destinations parsed from `CLAUDE.md` § Doc Sync Matrix at close time plus `docs/CAPABILITIES.md` are excluded) (CLAUDE.md § Doc Sync Matrix; spec § Chosen approach, Phase 5 (iv))
- **Given** a commit that renames a declared file into `scripts/enforcement/` and also touches `docs/reference/technology-stack-decision-guide.md` — a Doc Sync Matrix EXCL prefix member that is ALSO a sync-regex hit, **When** `done --commit` runs, **Then** the row counts BOTH, because set B of invariant (v) takes every sync-regex hit excluded or not (scripts/command_run.py:3121; spec § Chosen approach, Phase 5 (v))
- **Given** `--commit` that is empty, ABSENT on a `done`, resolves to a merge, or is dated before `started_at`, **When** `done` runs, **Then** it is REFUSED — the four close-time CONDITIONS (empty · resolves to a merge · dated before `started_at` · ABSENT on a `done`) carry THREE distinct messages, the merge and the stale date sharing one — and the record stays `running` (scripts/command_run.py:3360-3371; spec § Chosen approach, Phase 5 (ii))
- **Given** `handoff --reason "UPGRADE: mechanism"` or `done --evidence "UPGRADE: sync — …"` on a `fabrik-task` record, **When** the close runs, **Then** the row carries `upgrade: mechanism` / `upgrade: sync`; a `/fabrik-review` close writes neither field (scripts/command_run.py:3074, :3655-3676; spec § Chosen approach, UPGRADE)
- **Given** a ROOT commit (no parent) whose only path is an undeclared file, **When** `done --commit <it>` runs, **Then** the diff is taken against the empty tree `4b825dc642cb6eb9a060e54bf8d69288fbee4904` and the row counts that path (spec § Chosen approach, Phase 5 (iii))
- **Given** `handoff --command fabrik-task --resume <seed> --reason "UPGRADE: mechanism"` with no `--commit`, **When** the close runs, **Then** the row carries `oversized_mini: unmeasurable=no-commit` and `upgrade: mechanism`, and the close is NOT refused; `no-commit` WINS unconditionally when `--commit` is absent — there is no diff to take, so the membership arm cannot run and `sync_test-unavailable` cannot apply; that reason is reachable only on a close that DID carry a commit (spec § Chosen approach, Phase 5 (ii), (vi))
- **Given** the parser of `CLAUDE.md` § Doc Sync Matrix, **When** run on the live file, **Then** it reads every table row (22 today) and yields 25 tokens — 23 concrete paths plus the two `<name>` prefixes (`docs/reference/`, `docs/workstation/`) (CLAUDE.md § Doc Sync Matrix; spec § Chosen approach, Phase 5 (iv))
- **Given** a ledger with `fabrik-task` rows carrying `oversized_mini`/`upgrade` and review-scoped rows some of which are nested (same `sid`, the same repository — both `repo` values non-empty and either equal or one a path under the other on a `/` boundary — and `o.ts − o.wall_s ≤ r.ts ≤ o.ts`), **When** `--queue fabrik-task` renders, **Then** the header carries the `oversized_mini` rate over numeric rows excluding `upgrade: sync` rows, the `unmeasurable` share, the `upgrade` rate and the adoption share with nested rows excluded (scripts/command_feedback_report.py:1106, :1139-1142; spec § Validation V4)
- **Given** `--queue <any other command>`, **When** it renders, **Then** the header is byte-identical to today's (scripts/command_feedback_report.py:1139-1142)
- **Given** `commands/_sources/fabrik-task.md`, **When** the size/include grader runs, **Then** it is ≤ 8,847 bytes and its only `{{include:}}` is `run-record` (commands/assemble_commands.py:1170, :1184; spec § Constraints C2)
- **Given** the rendered corpus, **When** `assemble_commands.py --check` and `check_command_corpus.py` run, **Then** both are green and `~/.claude/commands/fabrik-task.md` exists (commands/assemble_commands.py:1170)
- **Given** every `command_run.py …` line the source carries, **When** parsed by the real parser, **Then** none is refused (scripts/command_run.py:2360-2496; spec § Chosen approach)
- **Given** hub `CLAUDE.md`, **When** T04a lands, **Then** § Orient step 0 carries the six-test + verdict-row table between the stage table and `Fork rules:`, § 1a's list contains "a governance-sync path", and the HANDLE-NOW clause's enumeration is replaced by the pointer sentence (CLAUDE.md:63-74, :198, :238; spec § The decision rule)
- **Given** `templates/governance/CLAUDE.md`, **When** T04b lands, **Then** its step-0 table, § 1a list and outcome (ii) mirror the hub's edits, `tests/test_governance_template_split.py` is green, and the mail to `fabrik-lib` carrying § 1a's trigger is sent (templates/governance/CLAUDE.md:56-67, :210, :355; /opt/fabrik-lib/CLAUDE.md:524; spec § Documentation landing sites)
- **Given** the whole-plan diff, **When** T05 runs, **Then** `final_gate.py --check --json` is `success`, `check_convergence.py` passes, the receipt embeds both, the sync dry-run lists only the template's project copies and one `--force` distributes it, V0 is measured in one project repo, V1's agreement is reported, and the dogfood `/fabrik-task` run closes with a `0` row (spec § Validation V0–V3)

## Global Constraints

- The tree is SHARED: three sessions; 14 sibling WIP files are dirty today (`PORTS.md`, `docs/reference/agents/kaizen-log-*.md`, 8 under `libs/subagents/`, `tests/test_assemble_dispatch_step.py`, `tests/test_check_review_coverage_precommit.py`, `tests/test_final_gate_stop_hook.py`) — never staged, reverted, stashed or `noqa`'d; explicit pathspecs; provenance trailers; never `--amend`; shared-append files (`CHANGELOG.md`, `docs/DECISIONS.md`, `docs/STRATEGIC_BACKLOG.md`, `INDEX.md`) by the private-index recipe in ONE shell.
- `scripts/command_run.py` is fleet-synced (governance-sync trigger; `.pre-commit-config.yaml:155`): every change is correct for ~46 repos, stdlib-only (`scripts/command_run.py:46-60`), and its new behaviour is scoped to `--command fabrik-task` — every other command's `start`/`close` output byte-identical.
- `templates/governance/CLAUDE.md` is a governance-sync trigger; the hub copy is not; the shared blocks stay byte-identical (`tests/test_governance_template_split.py`).
- Render from the main checkout only, in the order render → `--check` → `check_command_corpus.py` → commit; never bare-render from a worktree.
- Never bare-run the gate: `.venv/bin/python scripts/final_gate.py --check --json`.
- The pool is OFF (D-181/D-182): native seats only; `dispatch_headroom.py` then `command_run.py dispatch --seats N` before every fan-out.
- Tests: `uv run pytest tests/<file> -q`; watched-fail-first on a throwaway worktree (`git worktree add <scratch>/probe HEAD`), never a copied file; a `command_run.py` probe sets `COMMAND_RUN_DIR=<scratch>` and `--session probe-<id>`; never write `~/.claude/state/`.
- No new dependency (`pyproject.toml`/`uv.lock` untouched); PyYAML appears only in a GRADER (the equality assertion), never in `command_run.py`.
- 12-Factor non-negotiables inherited by every phase: logs to stdout only, never a logfile (XI) · no migration from startup (XII) · same backing services in every env (X) · no sticky sessions (VI) · no daemonizing/PID files (VIII) · workers requeue on SIGTERM, idempotent jobs (IX) · immutable releases (V) · granular env vars, no grouped sets, no secrets in code (III) · shelled-out binaries pinned in the Dockerfile (II). None of this plan's tickets touches a service, a worker or a compose file; the rows bind by inheritance.
- Naming kebab-case; `Never-Route:` scripts/enforcement/ (built-in) — untouched by this plan.

## Context Ledger

| Source | What binds | Grounded ref |
|---|---|---|
| `.windsurf/rules/core/10-python.md` (FLOOR) | `uv` runs the tests; stdlib-only script stays stdlib-only; `datetime.now(UTC)`; no bare `asyncio.create_task` (n/a) | `.windsurf/rules/core/10-python.md:21` |
| `.windsurf/rules/core/45-testing-strategy.md` (MATCHED: tests/) | one test per behaviour, watched-fail-first, `uv run pytest tests/` | `:19-21`, `:47-49` |
| `.windsurf/rules/core/40-documentation.md` (MATCHED: CLAUDE.md, commands/_sources/, templates/) | Doc Sync Matrix rows are gate-checked; markdown rules (no skipped heading levels, fenced code with a language) | `:133`, `:240-243` |
| `.windsurf/rules/core/62-using-subagents.md` (judgement read) | native seats for every fan-out; role separation in review loops | `:63`, `:184` |
| `fabrik-lib` (consulted: `/opt/fabrik-lib/README.md` module table) | no module supplies a run-record extension, a YAML-scalar extraction or a git-diff re-measure — BUILD fresh; not a fabrik-lib candidate (hub-only machinery, one consumer) | `/opt/fabrik-lib/README.md:13-86` — the `## Modules` table, all **71** rows enumerated (re-derived 2026-09-18; the earlier "40" understated the population) |
| `agents-fabrik.md` § Planning Constraints | solo developer; no port, compose or deploy surface touched by this plan | `agents-fabrik.md:362-380` |
| `specs/services/*.yaml` `shape.*` | none — no service, DB, cache or metrics change | — |
| `docs/data-contract.md` / `docs/ui-design.md` | absent in the hub — not a GUI project | — |
| `CLAUDE.md` § Sync-consciousness + § Behavior (shared tree) | the trigger regex is read from the YAML; the private-index recipe; render order | `CLAUDE.md:198`, `.pre-commit-config.yaml:155` |

## Constraints Digest

| Rule (verbatim) | file:line | Pack |
|---|---|---|
| **`uv`** is the mandated Python package manager. Never use raw `pip`, `pip install`, `poetry`, or `pipenv`. | `.windsurf/rules/core/10-python.md:21` | core/10-python |
| **Behavior Contract**: every ticket enumerates its distinct **user-observable behaviors / acceptance criteria** and tests **each one** — one high-value integration/E2E test per behavior, risk-ordered, TDD for the risky ones. | `.windsurf/rules/core/45-testing-strategy.md:19` | core/45-testing-strategy |
| **Watched-fail-first** (for tests this change adds or modifies; trivia stays skipped per the Behavior Contract): a non-trivial behavior's test proves something only if it has been SEEN RED | `.windsurf/rules/core/45-testing-strategy.md:21` | core/45-testing-strategy |
| **Run tests**: `uv run pytest tests/` (never bare `pytest` — Fabrik uses `uv`) | `.windsurf/rules/core/45-testing-strategy.md:47` | core/45-testing-strategy |
| **Enforced:** Gate-checked, no exceptions. Every code-shipping ticket must produce exactly one entry. | `.windsurf/rules/core/40-documentation.md:133` | core/40-documentation |
| **No skipped heading levels** — `##` to `###`, never `##` to `####` | `.windsurf/rules/core/40-documentation.md:240` | core/40-documentation |
| **Fenced code blocks only** — never indented code (AI treats it inconsistently) | `.windsurf/rules/core/40-documentation.md:242` | core/40-documentation |
| XI logs: unbuffered stdout only; the app never writes/rotates a logfile | `scripts/review_rubric.py:140` | 12-Factor (FLOOR) |

Every selection below cites a digest row or states `unconstrained`: the graders' runner (row 4), the test-per-behaviour shape (row 2), red-first (row 3), the CHANGELOG entry per ticket via the orchestrator's Deltas (row 5), the markdown of the new source and the CLAUDE.md edits (rows 6–7); the re-measure's git calls are `unconstrained` by any pack (subprocess in a stdlib script, the file's existing pattern).

## Execution Discipline (binding on /fabrik-execute-plan)

- **Review floor** — every ticket, on the coder's return, runs `/fabrik-review` on its changed surface to a coverage-adjudicated exit BEFORE its merge; no ticket merges on a first-pass green. T01a and T01b are the heavy surface (fleet-synced `command_run.py`): their reviews are partitioned by file with the Opus seat on `scripts/command_run.py` (`dispatch_headroom.py --slices opus=1,sonnet=1`, stamped first). T05's whole-plan `/fabrik-review` writes the receipt.
- **Dispatch policy** — native Claude seats for every fan-out (the pool is OFF, D-181/D-182); the coders are native worktree coders (`Complexity: native` on T01a/T01b/T03/T04a/T04b — Opus for the two `command_run.py` tickets, the design-heavy surface; Sonnet default for T02); the Opus seat for the authoritative review pass and for the decide/merge the orchestrator owns.
- **Parallelism + merge** — T01a runs first alone (it carries the parser changes every later ticket cites); on its merge T01b runs alone (same file, Serialized); on T01b's merge T02 and T03 fan out concurrently (disjoint Touches) and merge in Merge-Order position; T04a then T04b follow serially on the two contract copies; T05 last. Results merge in the main checkout by the orchestrator, per ticket, each after its own review.

## File Scope (owned paths)

- scripts/command_run.py
- tests/test_command_run_fabrik_task.py
- scripts/command_feedback_report.py
- tests/test_command_feedback_report.py
- commands/_sources/fabrik-task.md
- tests/test_fabrik_task_source.py
- docs/CAPABILITIES.md
- docs/reference/command-run-protocol.md
- CLAUDE.md
- templates/governance/CLAUDE.md
- tests/test_governance_template_split.py
- docs/development/reviews/2026-09-18-plan-1-fabrik-task-lane-review.md

## Evidence

- `scripts/command_run.py:2360-2368` — the `start` subparser: `--command` (required), `--phases` (required, int), `--terminal`, `--surface`; T01a adds `--file` (append) and `--declare` beside them.
- `scripts/command_run.py:2370-2377` — the `step` subparser: `--review-waived` (`:2371-2375`), `--phase` (required), `--title`; handled inline at `:2708`; `:2709` clamps `--phase` to ≥ 1 (why SIZE is the `start`, not a step); `rec["phase_title"] = args.title` at `:2789`, `save` at `:2792` — `design` is set between `:2789` and `:2790`; the review-artifact refusal `:2726-2760` keys on `PHASE_REVIEW_COMMANDS = frozenset({"fabrik-execute-plan"})` (`:699`), which `fabrik-task` never joins.
- `scripts/command_run.py:2583` — `start` is handled INLINE in `_mutate` (`if args.cmd == "start":`; there is no `_start` function): the nested-record park (`:2615-2622`), the record literal `new = {` at `:2623-2663` with `"command"` at `:2625`, `started_at: _now()` at `:2631` (`:912-913`, `%Y-%m-%dT%H:%M:%S%z`), `started_epoch: time.time()` at `:2636`, `repo_root: _repo_root()` at `:2639` (`_repo_root` `:844-855`, `git rev-parse --show-toplevel`); `save(sid, new)` at `:2681`, the ONLY stdout print `print(pinned_line(new))` at `:2682`, the stderr NESTED START warning `:2690-2697`, `return 0` at `:2699`. A `--file`/`--declare` guard sits between `:2583` and `:2623`; `RECORD: <started_at>` prints after `:2682`.
- `scripts/command_run.py:2440-2456`, `:2458-2483`, `:2485-2503` — the `done`/`handoff`/`blocked` subparsers (`--evidence` required at `:2447`; `--resume` required at `:2469-2477`; `--reason` required on `blocked` at `:2494`); T01b adds `--commit` to all three.
- `scripts/command_run.py:3074-3075` → `_close` (`:3121`) serves `done`, `blocked` and `handoff`; the verb branch `:3500-3511` (`evidence` at `:3501`, `handoff`'s `blocked_reason`/`resume` at `:3508-3509`, `blocked`'s at `:3511`); `rec["state"] = args.cmd` at `:3493`; `:3360-3371` the `--feedback` refusal keyed on `started_at` (`_feedback_is_required`, `:1193-1202`) — the canonical close-time REFUSED shape: rc 1, the message on BOTH streams (`sys.stderr.write(f"[command_run] {msg}\n")` then `print(msg)`, `:3369-3371`), which the three new refusals copy.
- `scripts/command_run.py:3655-3676` — `_row`, the ledger row literal (`ts sid repo command state wall_s rounds findings confirmed phases phase_reached agent surface account …`; the two new keys go in at `:3674-3675`, after `cost_usd` and before `**_tok`); `:3677` `_pending_row = _row`; `:3682` strips `stack` from the nested copy; the ledger append `:3705-3712` (`_feedback_ledger_path` `:1621-1622` = `$COMMAND_RUN_DIR`'s parent `/command-feedback.jsonl`; `_append_ledger_row` `:1609-1618`); the `run_close` kaizen event dict `:3600-3624` (a new row key is NOT echoed unless added there); `:1602-1606` `_LEDGER_FIELD_CAP = 2000` / `_cap_field`, applied at `:3671` and `:3673`; the git-subprocess shape to copy is `:3215-3229` (`capture_output=True, text=True, timeout=10, cwd=root`) — ⚠️ but `check=True` is WRONG for the lane's FOUR rc-SIGNALLING calls — the fourth is the present-and-untracked probe, because `git diff --quiet HEAD -- <p>` returns 0 for an untracked path (executed) and `git ls-files --error-unmatch <p>` rc 1 is what sees it and must be `check=False` with `.returncode` read: executed 2026-09-18, `git diff --quiet HEAD -- <p>` on a dirty path raises rc 1, `git rev-parse -q --verify HEAD` in a commit-less repo raises rc 1, `git cat-file -t <bad>` raises rc 128 — and `_mutate`'s caller converts ANY exception to `return 0` with no record written (`:2557-2559`), so under `check=True` a dirty declared path is a SILENT SUCCESS: no refusal, no record, no Stop-hook block — the file runs no `git diff` today.
- `scripts/command_feedback_report.py:1106` — `queue(rows, command, ledger)`; `:1119-1129` the `for_it`/`mine`/`excluded` filters; `:1138-1144` the header f-string T02 extends — by APPENDING one `series:` line after it under a `command == "fabrik-task"` guard, never by adding a `+ (f"; …")` clause inside the shared string (T02 step 2; that is what keeps every other command's header byte-identical); `_default_ledger()` `:33-41` (`$COMMAND_RUN_DIR`'s parent, else `~/.claude/state`), `_rows()` `:44-63`; the `--queue` dispatch `:1319-1325`; `:941-950` the `surface` aggregation; `tests/test_command_feedback_report.py:22-43` the `_row`/`_write` fixture and `:46-52` `_run(... --ledger <path>)`, `:1493-1515` the header-assertion test the new graders copy.
- `.pre-commit-config.yaml:149-155` — the `- id: governance-sync` block; its `files:` scalar is the SIXTH of six in the file (lengths 84/20/30/74/33/678, re-derived at this plan's basis; `decisions-ledger-check` at `:103` carries one too) and must be located by the id, never by position; `scripts/governance_sync_postcommit.sh:28-30` parses it with PyYAML, `:44` refuses an EMPTY filter.
- `CLAUDE.md:63-74` — § Orient step 0's stage table (`| Stage | Covers |` at `:63`, last row `| \`utility\` |` at `:72`, blank `:73`, `Fork rules:` at `:74`; rows indented three spaces — the lane table lands between `:72` and `:74`); `:198` the HANDLE-NOW clause carrying "SPEC/PLAN work (a new mechanism, a vendored/synced surface, schema, auth, >5 files) … or a RIGHT-NOW fix"; `:238` § 1a's "heavy surfaces (new mechanism, gate/hook/enforcement, auth/schema/migrations/concurrency, >5 files, or anything an operator asked for by name)". Template twins at `:56-67` (`| \`utility\` |` at `:65`, `Fork rules:` at `:67`), `:353-359` (outcomes (i)–(iii); (ii) at `:355-356`) and `:210` (the 1a substring byte-identical to the hub's). The `review-after-change` anchor (`EVERY code-changing chunk of work gets a review-family pass`) lives in the SAME 1a paragraph — the edit touches only the `heavy surfaces (…)` clause. `tests/test_governance_template_split.py` pins the T6 commit-recipe claims (`:112-184`), the QUOTA claims (`:230-256`) and two shared spans (`:293-296`) — none in step 0 or 1a. `/opt/fabrik-lib/CLAUDE.md:524` carries the same § 1a list and no SIZE clause (read-only; the mail). `.pre-commit-config.yaml:149-156` the governance-sync block (`files:` at `:155`; `^templates/governance/` matches, root `CLAUDE.md` does not); the template → `<repo>/CLAUDE.md` mapping is `scripts/fabrik_synced_manifest.py:110` (`GOVERNANCE_TEMPLATES`), iterated at `scripts/sync_enforcement_to_projects.py:2028`; `--dry-run` `:2325-2329`, `--force` `:2335-2339`; `command_run.py` is in `CORE_SCRIPTS` (`fabrik_synced_manifest.py:61`), `command_feedback_report.py` and `commands/` are not synced. `scripts/mail.py:1625-1649` — `send --to <repo> --kind <k>` with the body on stdin (`--to-agent` is required only for hub-bound sends); the D-035 contract at `docs/reference/fabrik-mail.md:175`.
- `scripts/enforcement/check_corpus_weight.py:62-69` (`SURFACES`, four directories + two files), `:97-134` (`measure()`), `:162`/`:198-233` (base comparison), `:362-365` (the growth WARN's prose asks for a D-row cite; nothing enforces it) — no per-file cap; `commands/assemble_commands.py:1170` (the single-pass `{{include:NAME}}` substitution), `:1184-1195` (close-feedback auto-appended), `:50-88` (the `NEXT` dict, injected into the SKILL wrapper only, `:103` the fallback), `:912-914` (only `description:` is parsed; `Stage:` is read by `skill_router.py:739` from the installed SKILL text), `:97-136` (the wrapper written to `~/.claude/skills/<name>/SKILL.md`, `:37-38` the two destinations); `scripts/enforcement/check_command_corpus.py:22-53` (its eight predicates — a source must open a run record, `:96-98`, and print `--feedback` on every close line, `:121-123`); `commands/_fragments/run-record.md` 3,245 B (no nested include); `commands/_sources/fabrik-features.md` 8,847 B (the smallest of 37); `docs/CAPABILITIES.md:391-393` (the alphabetical bullet block; `fabrik-task` lands between `:392` and `:393`); `docs/reference/command-run-protocol.md:52-56` (the `start`/`step`/`done` CLI rows); `.claude/hooks/skill_router.py:105-114` (a not-yet-built command auto-enrolls at fire time — no edit needed, and the router row is out by D-k).
- `tests/test_command_run.py:43-82` — the `_cr` harness (`COMMAND_RUN_DIR`, `KAIZEN_EVENTS_DIR`, `CLAUDE_SESSION_ID`, the auto-injected `--feedback`); `:495-510` the throwaway-git-repo fixture (`:497` is mid-`dict(`); the new graders live in `tests/test_command_run_fabrik_task.py` because that file is 262,935 bytes — larger than the READ budget on its own.
- `scripts/enforcement/check_phase_tests.py:36`, `:46`, `:53`, `:131`, `:153-154`, `:223`, `:245-246` — the plan-lock read the command source mirrors (with `--name-status -M` and both paths of a rename).
- `scripts/enforcement/check_decisions_unique.py:145` — the ledger splits on bare `|`; the D-row mapping writes `&#124;`.

```text
$ git -C /opt/fabrik log -300 --format=%H a929b33f8 | wc -l ; python3 - <<'EOF'   # V0 at the pinned basis (executed 2026-09-18)
300
base a929b33f8: 300 commits; sync 97 (32%); <=3 208 (69%); pass both 162 (54%); refused 138 (46%)
lane-choice: 101; refused 34 (34%); sync-refused 27; >3-only 7
sync-refused touching templates/governance/CLAUDE.md: 9 ; false refusals (comment/docstring-only in a synced script): 3 of 27 (11%)
EOF
```

```text
$ python3 scripts/sysadmin/dispatch_headroom.py --units 4 --mechanical 0     # this plan's grounding fan-out
SEATS: 5  (units=4, read-only; caps {'wanted': 5, 'concurrency_cap': 20, 'box_cap': 22})
```

## Self-audit

- Grounding passes: the spec review's three runs executed every `path:line` above against `a929b33f8`/`ccb26ed14`/`a40d75870`; this run re-read the parser blocks, `_start`, `_row`, `queue()`, the corpus and CLAUDE.md anchors, and dispatched five native researcher seats (Opus authoritative on `command_run.py`, Sonnet on the four units) whose corrections are folded into § Evidence and the tickets — the Pass Ledger records the round.
- (a) Coverage — the rule + inventory → T01a; the six invariants + two fields → T01b; the reader → T02; the source + docs → T03; the two contract copies + the mail → T04a/T04b; V0–V3 + the sync + the receipt → T05. No agreed item lacks a ticket.
- (b) Cross-ticket signatures — `declared` keys named identically in T01a (Produces), T01b (Consumes) and T03 (the printed `--declare` grammar); the row grammar in T01b (Produces) and T02 (Consumes); the CLI lines in T03 are graded against the real parser; the table's `/fabrik-task` cell in T04a/T04b is graded against the rendered corpus.
- Sizing: `python -m scripts.enforcement.check_plan_tickets --plan-dir docs/development/plans/2026-09-18-plan-1-fabrik-task-lane` — its SUMMARY line is recorded in § Residual unknowns once run; the READ budget is the reason `tests/test_command_run.py` is not a Touches/Context entry and the two CLAUDE.md copies are two tickets.
- Fixed point: not yet — `/fabrik-plan-review` runs next in this turn.

## Coverage Checklist

Rubric over the touched surfaces (`python scripts/review_rubric.py --changed scripts/command_run.py scripts/command_feedback_report.py commands/_sources/fabrik-task.md CLAUDE.md templates/governance/CLAUDE.md tests/test_command_run_fabrik_task.py`):

```text
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
- Ruff's selected rule-sets MUST include `ASYNC` (blocking IO in async code — machine-enforces this pack's hardest-to-review rule), `B` (bugbear) and `S` (bandit) alongside the defaults; configured in `pyproject.toml`, emitted by the scaffolder.
- Production services run via `uvicorn` CLI in the Dockerfile, not `uvicorn.run()` in code. Base image is always the pinned Debian `-slim` variant on `linux/amd64` (the variant is pinned fleet-wide in `30-ops.md` § Container Base Images — change it THERE, never per-repo). Never use Alpine — musllinux wheels exist now (PEP 656) but coverage is still partial, source builds are dramatically slower, and musl's allocator/stack defaults degrade CPython; the trade never pays on this fleet.
- `uvicorn.run()` is for local development only. Never ship it in production code.
- a fleet scaling decision (more containers), never a per-app flag.
**BANNED: grouped/named env config sets.** 12F is explicit — *"env vars are granular controls, each fully orthogonal to other env vars"* — so a `config/production.yml`, a `settings.production` group, or a `config/{dev,staging,prod}.yaml` tree is a violation. Env vars are granular and set **per deploy**, never batched into a named "environment".
**BANNED:** `logging.FileHandler`, `logging.handlers.RotatingFileHandler`, `TimedRotatingFileHandler`, `loguru` file sinks, any `*.log` file write, any in-app log rotation/retention/cleanup. The app never decides where logs are stored or routed — Docker → Promtail → Loki does. Full rule: `55-observability.md` § Logs.
**Factor XII — Admin processes. NEVER migrate from app startup.**
**BANNED: `alembic upgrade head` in FastAPI's `lifespan`, in an `@app.on_event("startup")`, or as an import side-effect.** With more than one replica (or a restart storm) two containers run `upgrade head` **concurrently** → they race the Alembic version table → duplicate DDL → **wedged deploy**. Migrations are a **one-off admin process against the deployed release**: `docker compose run --rm <svc> alembic upgrade head` (see `30-ops.md` § Release & Admin Processes).

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

### core/40-documentation.md  (hit: CLAUDE.md, commands/_sources/fabrik-task.md, templates/governance/CLAUDE.md)
- > **⚠️ `docs/OPERATIONS.md` + `docs/DEPLOYMENT.md` are FLEET-AI INTERFACES, not just docs (D-065).**
- **Tier-1 (author → verify → converge; the author leg is NATIVE while the pool is OFF, D-181 — `scripts/doc_reconcile.py`'s pool author cannot dispatch):** for each **mechanically-detectable** doc whose Doc-Sync trigger fired (`docs/QUICKSTART.md` · `docs/CONFIGURATION.md` · `docs/data-contract.md` · `docs/SERVICES.md` · `docs/OPERATIONS.md` — the reliable-signal subset), `scripts/doc_reconcile.py` dispatches a cheap OpenRouter-pool author (`libs.subagents`, `pick_models("docs")`) to emit a **minimal structured patch**, **verifies it before applying** (a symbol cross-check catches invented endpoints; the orchestrator injects a higher-assurance native-Claude verify), and loops to a zero-edit round. Runs per phase in `/fabrik-execute-plan`; never blocks (fail-safe). The other docs (CHANGELOG, INDEX, FEATURES, RESILIENCE, PORTS, the READMEs, `db/schema.sql`, …) have no reliable mechanical content-signal → they rely on the touch-on-change backstop below + your own edit (force-update, not force-correct).
- The SSOT is the type-aware registry (`scripts/enforcement/_doc_registry.py::PROJECT_DOCS`) — this table is its project-facing rendering, kept in step, never a second truth. `/fabrik-plan-after-chat` (the plan set's spine + tickets — the ticket-format authority) injects these rows per ticket as its `Docs:` line.
- Standalone work (not plan execution) → `Agent-Role: primary`. Trailers go below a blank line, above `Co-Authored-By`. ⚠️ The trailer block must be its OWN paragraph with NO blank line inside it: git parses only the LAST paragraph, and only if it is all-trailers. A blank line before `Co-Authored-By:` demotes everything above it to prose; so does a prose line glued to the top of the block. Measured 2026-08-15: 200 of the last 200 hub commits carried `Agent-Role:` and only 10 parsed, because the old example here shipped the blank line.
- **⚠️ Link it or it is decoration.** *Measured:* requests for files that do NOT exist came ~zero from AI bots — agents never go looking. It follows (inference, not measurement) that a file only gets read when something points at it: reference it from the docs index or README.
- ⚠️ **In THIS repo `llms.txt` is GENERATED** (`scripts/generate_capability_index.py`, refreshed daily) — never hand-edit it; change the generator. A project writing one by hand owns it.
- either way. Cheap and reversible — never at the expense of `OPERATIONS.md`/`DEPLOYMENT.md`, which are the load-bearing agent interfaces (D-065).
- **No skipped heading levels** — `##` to `###`, never `##` to `####`
- **Fenced code blocks only** — never indented code (AI treats it inconsistently)

### core/45-testing-strategy.md  (hit: tests/test_command_run_fabrik_task.py)
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

# promote-to-check_*: ELIDED (the sanctioned elision — the tail is 21 greppable-literal lines; header, FLOOR and MATCHED above are verbatim)
```


Every row is adjudicated at the flip with ONE of the verdicts `check_review_coverage.py` accepts — `CLEAN` · `FIXED(n)` · `REFUTED` · `ROUTED(n)` · `RECORDED — (unexecuted|by design|measured|hygiene false positive)` — never `PASS`, `OK` or `✓`, which fail `check_convergence.py` with an opaque message.

| # | Class | Verdict | Where |
|---|---|---|---|
| 1 | core/10-python — stdlib-only script, `uv` runner, no new dependency | CLEAN | executed: `pyproject.toml`/`uv.lock` are in no ticket's Touches; PyYAML appears only in T01a's equality GRADER, never in `command_run.py`; every ticket's Gate runs `uv run pytest`; `check_plan_tickets` 0 findings over 7 tickets |
| 2 | 12-Factor — no service/worker/compose surface touched; rows inherited | CLEAN | the set's 15 Touches paths are scripts, tests, a command source, two contract copies and a receipt — no compose, no service, no worker; the § Global Constraints roll-up states the inheritance |
| 3 | core/40-documentation — Doc Sync Matrix rows per ticket; markdown rules on the two CLAUDE.md copies and the new source | FIXED(3) | the Constraints Digest column order (it was grading NOTHING — 8 QUOTE-NOT-FOUND, now 0 with both positive controls made to fire); the digest table's missing blank line (the next paragraph rendered INSIDE the table — proven with `markdown_it`, now `table_close → paragraph_open`); the embedded `review_rubric.py` block replaced by the verbatim run |
| 4 | core/45-testing-strategy — one test per behaviour, red-first, `uv run pytest` | FIXED(4) | both Gates' `-k` filters dropped (executed: `-k` deselected a failing grader and the run exited 0); the PyYAML equality grader moved into step 2's red-first batch; the grader count corrected six → eight; the refusal tests re-sized per CONDITION (four) rather than per message (three) |
| 5 | fail-open / fail-closed — `sync_test: unavailable` fails OPEN by design; the close-time refusals fail CLOSED; the empty-regex arm | FIXED(6) | the mandated `check=True` shape (all three rc-signalling git calls raise, and `:2557-2559` turns that into rc 0 with NO record — a dirty declared path was a silent success); the `--command /fabrik-task` bypass; `except Exception` named with its four live escapes; the `--design` unreadable/second-value arms; the `UPGRADE:`-only IndexError path; the sync-skip made visible on stderr at start |
| 6 | cost / limit edges — `_LEDGER_FIELD_CAP` on `design` and the row strings; the ≤ 8,847 B source cap | FIXED(2) | the `oversized_mini` field reordered so `_cap_field`'s TAIL truncation cannot eat `commit=<sha>` (executed: 2,441 chars destroyed it under the spec's order — the divergence is declared and routed); T02's zero-denominator arm now prints `oversized_mini —/0` instead of dividing |
| 7 | boundary / sentinel — root commit (empty tree), merge (refused), `HEAD`-less repo (`sha: unavailable`), absent vs present-untracked path | FIXED(5) | a Behavior-Contract row added for the root commit against the empty tree; `-z` + `core.quotePath=false` (a non-ASCII declared path never matched its own diff line); `-C` added (executed: `-M` alone MIS-ATTRIBUTES a rename+copy commit); the present-and-untracked probe named as the FOURTH rc-signalling call (`git diff --quiet` returns 0 for an untracked path); the adoption-nesting repo guard's empty-string collapse |
| 8 | behaviour without a test — every Behavior Contract row above names its grader | FIXED(3) | two of the spec's six invariants had NO row (the empty-tree arm and the `unmeasurable` arm) and now do; five behaviours round 1 added to the STEPS were folded into existing rows rather than left ungraded, both tickets at exactly 8 of `MAX_BEHAVIORS = 8`; the cobra note moved to the source docstring where FIX DIRECTIVE 5 wants it |

## Pass Ledger

| Pass | seats · axes re-checked (claims · gates · interfaces · completeness) | counters | method | set md5 (start → end) |
|---:|---|---|---|---|
| Pass 1 | opus×1 (rule/grammar sections + T01a/T01b) + sonnet×1 (T02–T05 + the narrative sections) · all axes | found: 53, new: 53, confirmed: 47, fixed: 47, unexecuted: 0, edits: 51 | method: citation — the full partitioned pass, every candidate EXECUTED before it was counted; round zero ran the DRAFT's own introduced claims first (6 fixed pre-pin); the four flip-gate MATRIX rows run on a flipped scratch copy; 6 candidates RECORDED rather than confirmed (2 duplicates of the orchestrator's own, 1 folded, 2 `{{include:}}` hygiene false positives, 1 scratch-root gate artifact) and 1 sub-claim REFUTED by execution (a seat read the old UPGRADE-token rule as yielding an empty token; executed, its `.split()` reading yields `sync` — the missing ANCHOR was the real defect, and that is what was fixed) · mirrors: 7 claim terms swept across all 8 files | c3b364cb… → b4a6458f… |
| Pass 2 | opus×1 (fresh) + sonnet×1 (fresh) · delta over round 1's 162-line fix diff plus one hop | found: 17, new: 17, confirmed: 16, fixed: 16, unexecuted: 0, edits: 61 | method: re-derivation — every round-1 fix re-derived from its primary source, not re-cited; ALL 16 confirmed are own-fix (own-fix: round 1) — the plan's own surface was quiet, and the defects were in round 1's fix text: a field reorder propagated to 1 of 4 sites, `six graders`/`six rows`/`three refusals` counts stale against the rows the round itself added, an `unmeasurable` row prescribing two values for one input, a `--design` refusal contradicting its own Behavior-Contract row, a `try/except` naming no class once `check=True` was dropped, and a deleted blank line that made the next paragraph render inside the digest table (executed with `markdown_it`). The Sonnet seat also caught that FOUR round-1 fixes never landed — the patch script exited on its first miss — which is why every fix is now marker-verified with one `grep -c` each. 3 RECORDED (1 wording, 2 one-hop-out) · mirrors: 4 claim terms swept | 1f77338d… → 8f2bfc18… |
| Pass 3 | opus×1 (fresh) + sonnet×1 (fresh) · delta over round 2's 61-line fix diff, mandate NARROWED to re-verifying the fixed set | found: 12, new: 12, confirmed: 12, fixed: 12, unexecuted: 0, edits: 32 | method: re-derivation — the seats verified 22 of 30 round-2 fixes CORRECT by execution (the `-z` field structure, the `quotePath` demotion, the `UPGRADE:` grammar on six inputs, the four rc-signalling calls, the harness spans, the digest blank line via a parser) and the orchestrator's own PROPAGATION SWEEPS found 4 more (counts, shared anchors, quoted refusal messages, `spec §` cites — 64 cites resolve, 33 shared anchors agree, every repeated message byte-identical). ALL 12 confirmed are own-fix (own-fix: rounds 1-2). ⚠️ **`command_run.py` printed the D-278 SCOPE-GROWTH stop here** (47/0 → 16/16 → 12/12): the plan's own surface has been quiet since round 1 and the loop was correcting its own prose. Exit taken — the named set fixed, the residue routed, the closing round re-verifies THAT SET only · mirrors: 4 sweeps across all 8 files | 8f2bfc18… → 651c0685… |
| Pass 4 | opus×1 (fresh) · re-derivation over round 3's 32-line fix set only, per the D-278 exit | found: 2, new: 2, confirmed: 2, fixed: 2, unexecuted: 0, edits: 4 | method: re-derivation — 10 of the 12 round-3 fixes verified CORRECT by execution (the refusal-template collision set, the 14/8 inventory against the spec's own 13/7, the byte-identical roll-up rows, the five close-time strings, the D-294 id free at `decisions.py --next-id`, the mail's cite at spec `:137`); the seat also EXECUTED the flip on a throwaway repo and proved `check_convergence` green with BOTH negative controls firing. 2 confirmed, both own-fix (own-fix: round 3): `os.environ.get("FABRIK_HUB_ROOT", "/opt/fabrik")` makes an EMPTY override a RELATIVE path — the running repo's copy, whose governance-sync scalar differs from the hub's in 38 of 38 repos (executed) — and a MULTI-commit `git revert` HALTS at the first conflict, so T05's restore left the hub copy carrying the refuted rule at rc 0 with `.git/sequencer` behind (executed both arms). 1 RECORDED — measured (the `SIXTH of six` vs the spec's `five` scalar census: both true on different populations, 6 keys of which 5 are single-quoted, and the plan anchors on the id never a position) · mirrors: 3 sites | b048ff5c… → 56012a24… |
| Pass 5 | opus×1 (fresh) · CLOSING — re-derivation over round 4's 4-line fix set only, per the D-278 exit taken at round 3 | found: 0, new: 0, confirmed: 0, fixed: 0, unexecuted: 0, edits: 0 | method: re-derivation — both round-4 fixes re-derived from their primary source and CONFIRMED CORRECT by execution: an empty `FABRIK_HUB_ROOT` yields a relative path under the two-arg form and an absolute one under `or` (and 0 of the 38 non-hub `/opt/*/.pre-commit-config.yaml` scalars equal the hub's, re-measured independently); the multi-commit `git revert` halts at rc 1 with `.git/sequencer` present having attempted only T04b, while the one-at-a-time sequence restores BOTH copies, preserves the sibling hunk and leaves no sequencer. `command_run.py` printed TERMINAL: every known class swept clean. 1 RECORDED — measured (wording: "its ten `os.environ.get` sites" counts distinct env names, 10; by call site 12 lines — the load-bearing clause is unaffected, and a closing round does not edit) · mirrors: 3 sites clean | 479a6815… → 479a6815… ✓ → **CONVERGED** |

## Residual unknowns

- **Resolved by the spec:** the lane rule, the inventory, the invariants, the row fields, the exclusion set, the numbers (all at basis `a929b33f8`).
- **Open (self-service, T05):** V0's project-repo fire rate — measured in `/opt/youtube` before the sync with the plan's own script (`git log -300` there, the hub's regex read by absolute path); expected far below the hub's 46%.
- **Open (self-service, T05):** V1's per-test agreement over the 24 lane-choice commits (author-blind seats answer tests 2–4 only from a cited D-row, else UNANSWERABLE); >30% disagreement on answerable rows re-cuts the rule before T04a lands — which is why T05 depends on T04b but the backtest step runs FIRST inside T05, before the sync.
- **Open (self-service, T05):** the dogfood candidate — the first `/fabrik-task` run is on a real ≤3-file reversible decision the backtest names; the plan's own Integration ticket is NOT that candidate.
- **Sizing evidence (executed at the emit gate, 2026-09-18):** `✓ [plan_tickets] /opt/fabrik/docs/development/plans/2026-09-18-plan-1-fabrik-task-lane: graded 7 ticket(s), 14 Touches path(s), 23 Context-Files entry(ies); READ budget measured against /opt/fabrik; 0 finding(s)`.
