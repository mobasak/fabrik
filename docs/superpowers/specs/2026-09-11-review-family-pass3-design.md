# Review-family adoption, pass 3 — the last five loops, the bounded hop, and the six cost fixes

Status: DRAFT
Profile: delta
Owner: — (infra; the unnamed hub window fabrik-06, session dd3c06d1)
Date: 2026-09-11
Predecessors: `docs/superpowers/specs/2026-09-08-review-convergence-redesign-design.md` (D-203 → D-206/D-207/D-208) · `docs/superpowers/specs/2026-09-10-review-family-adoption-design.md` (D-212/D-215/D-217/D-218/D-219; its plan EXECUTED and archived at f31990d1) · `docs/STRATEGIC_BACKLOG.md` row 61 (this spec's origin) · `docs/LESSONS_LEARNT.md` 2026-09-11 "A delta-review loop converges only when the kill and the hop are both pinned"

## In one line

Finish the review family's move under D-203 — the five loops that include neither termination fragment, the five `term-coverage` consumers, and 66 restatements of the retired exit in 11 commands — and cut the measured cost of every loop with six text-only fixes: a bounded delta hop, delta rounds sized by the fix, a route-up that replaces the scoped loop, a mandatory round zero, the git-verb prohibition in every seat brief, and no second docs loop over docs the heavy review already graded.

## Intake Inventory

The conversation is the denominator (operator words quoted; the 2026-09-10 rows carried from the archived plan's backlog row; the 2026-09-11 rows from this session's turns after the plan closed).

| I# | Item (anchored) | Disposition | Where |
|---|---|---|---|
| I1 | 2026-09-10: "ok note them, do not forget, strategic_backlog.md assign yourself" — the pass-3 row: the five fragment-less review loops | IN | § The delta D1 |
| I2 | same row: verify the `term-coverage` inheritors (`/fabrik-conformance-review`, `/fabrik-service-test`, `/fabrik-user-test`) | IN — CHANGED: the population is FIVE consumers, not three (re-derived § What exists today, row 3) | § The delta D2 |
| I3 | the row's third class (added at the archive): the other 11 `term-edit` consumers' 66 prose restatements of the retired zero-edits exit; `fabrik-review.md:11`; `fabrik-ui-design-review.md:140,143` | IN | § The delta D3 |
| I4 | 2026-09-11: "all agents are waiting for your work here. our review commands was taking too much time." | IN — the motivating failure | § Why this exists |
| I5 | "does it need any modification so that it can be more accurate, fast, lean, effective, also takes shorter time?" → the six fixes named in reply; "so can you include all these fixes into fabrik-spec pass-3 now?" | IN | § The delta D4–D9 |
| I6 | "how many subagents did you use while executing this plan?" — 116 review seats, 0 coder seats, 95 % of 882 min in review loops | IN — the measurement that sizes the fixes | § Why this exists |
| I7 | "answer my question before invoking a fabrik-spec command" — the operator wants the state stated before machinery runs | IN — the close-out of this spec states the ask ↔ spec table FIRST (this command's Phase 6) | § Machinery report |
| I8 | 2026-09-10: "/opt/fabrik-lib-account and /opt/fabrik-lib-review are not repos which agents run in" | OUT-OF-SCOPE — a census convention, already encoded in `check_convergence.py`'s comment and the workflow doc (worktrees excluded via `git worktree list`) | archived plan f31990d1 |
| I9 | the trade-intelligence held sync of the previous plan (mail 01M23G21EBSS4BC187HQ7PS02X) | OUT-OF-SCOPE — a separate thread, never folded in (operator ruling carried from the previous spec) | memory `project_review_convergence_plan_finish_state` |
| I10 | the seat that ran `git stash --keep-index` in the shared tree during the docs review (this session, 2026-09-11) | IN — the failure D8 encodes | § The delta D8 |
| I11 | rounds 8–11 of the Finish review were residue of the previous round's fixtures (a filesystem-order mutant kill, an ungraded helper, a cleanup that raised on the red path) | IN — the failure D7 encodes | § The delta D7 |
| I12 | the Finish docs review took 12 passes over one 1,118-line reference — one neighbouring section per pass | IN — the failure D4 and D9 encode | § The delta D4, D9 |

Intake: 12 items — 10 IN, 2 OUT-OF-SCOPE (each named above), 0 ASK.

## Personas

One line each (delta profile; no new persona): **the review orchestrator** (a Fable/Opus session running any review-family command — the primary; the operator's words: *"our review commands was taking too much time"*) · **the operator** who waits on the loop and reads its close-out · **the finder/reconciler seats** (`fabrik-reviewer`, `fabrik-researcher`, `design-review`, `general-purpose` reconcilers — automated consumers of every brief this spec changes; the duty holder for D8 is the seat, the duty holder for D7 is the orchestrator) · **the assembler and the graders** (`assemble_commands.py`, `check_convergence.py`, `check_review_coverage.py`, `check_review_hygiene.py`, `command_run.py` — the automated consumers of the fragment grammar) · **the ~46 project repos** that receive the rendered commands box-wide. The primary's minimal loop is unchanged from the predecessor spec (pin → dispatch → execute → fix → record → close); this spec removes rounds from it, it adds no step.

## Goal

Every review-family command closes on the CONFIRMED exit with a delta hop that is bounded in the fragment text, sizes its delta rounds by the fix, never runs two loops over one diff, and briefs its seats with the git-verb prohibition — so a `Profile: small` plan's review cost falls from the measured 838 of 882 minutes to a budgeted fraction, without lowering recall (round 1 keeps its partition and floor).

## Why this exists

Measured on plan `2026-09-10-plan-1-review-family-adoption` (the fleet feedback ledger, `~/.claude/state/command-feedback.jsonl`, session dd3c06d1, re-read 2026-09-11):

| Record | Wall-clock | Rounds | Seats | What the rounds did |
|---|---|---|---|---|
| Phase A `/fabrik-review-scoped` | 67 min | 3 | 9 | three rounds, then routed up — the heavy loop redid the same diff |
| Phase A `/fabrik-review` (routed up) | 266 min | 15 | 31 | rounds 11–14 confirmed graders for behaviour the change never touched (the breaker fired 3·3·3·4) |
| Phase B `/fabrik-review-scoped` | 48 min | 3 | 5 | — |
| Finish `/fabrik-review` | 298 min | 12 | 34 | series 10 7 4 6 4 3 3 5 2 3 1 0; rounds 8–11 were residue of the previous round's own fixtures |
| Finish `/fabrik-docs-review` | 159 min | 12 | 37 | series 12 9 8 13 6 4 5 8 3 2 2 0; one neighbouring section of a 1,118-line reference per pass |
| `/fabrik-execute-plan` (the whole run) | 882 min | — | 0 coder seats | 838 min (95 %) inside review loops; the code and docs the plan asked for took under an hour |

Three properties of the loops caused it, none of them a defect of `/fabrik-execute-plan` itself: (a) the delta hop is unbounded — every command says "the fix diff plus one hop of callers and callees" and nothing says where the hop stops, so each round's fix creates the next round's hop; (b) every round costs the floor — three seats on a four-line delta; (c) the scoped loop runs its three rounds and THEN routes up. The predecessor plan landed the exit, the partition and the delta rounds; it did not bound the hop, and the two Finish loops are the proof. The operator's words: *"all agents are waiting for your work here. our review commands was taking too much time."*

## What exists today (grounded — `path:line`, re-read 2026-09-11 at f31990d1..391d1852)

1. **The fragment population.** `commands/_fragments/term-edit.md` (27 lines) is included by 13 sources (`grep -l '{{include:term-edit}}' commands/_sources/*.md`: data-contract, deploy-checklist, deploy-plan-review, doc-converge, features, flows, flows-review, plan-review, rivals, spec-review, ui-design, ui-design-review, workflow-review). `commands/_fragments/term-coverage.md` (35 lines) is included by 5 (conformance-review, repo-review, review, service-test, user-test). `commands/_fragments/subagents-core.md` (15 lines) is included by 20.
2. **The five fragment-less loops** (`grep -c -i confirmed` per source): `fabrik-review-scoped.md` 2 mentions, includes only `run-record`, 103 lines; `fabrik-docs-review.md` 0, includes `grounding-artifact` + `subagents-core`, 211 lines — its exit is "zero new discrepancies AND makes zero doc edits — a no-op pass" (`:141`) with "Never solo, never two" (`:128`); `fabrik-rules-review.md` 0, 163 lines — "a pass whose gap list is identical to the prior pass (a no-op …)" (`:10`); `fabrik-epics-review.md` 1, 541 lines — "A doer produces, a separate review forces the no-op" (`:19`); `design-review.md` 0, 48 lines — "done ONLY when a fresh, demonstrably-thorough design-review pass finds ZERO issues" (`:39`).
3. **The `term-coverage` consumers**: `fabrik-conformance-review.md` 0 `confirmed` mentions, `fabrik-service-test.md` 3, `fabrik-user-test.md` 4, plus `/fabrik-review` and `/fabrik-repo-review` (the code loops D-203 re-cut first). The fragment's exit row (`term-coverage.md:20-24`) still reads `found: 0 · new: 0 · fixed: 0` with the D-048 history clause — it carries no `confirmed:` counter, so its five consumers inherit the OLD exit grammar; the graders accept it ("a ledger without `confirmed:` keeps the `found: 0` rule", D-206).
4. **The 66 restatements** (the five-phrase grep `ZERO edits|no-op|edit-free|changes nothing|needs no edits`, re-derived 2026-09-11 on the sources): ui-design 14, ui-design-review 11, flows-review 10, data-contract 7, workflow-review 5, doc-converge 5, deploy-plan-review 4, flows 3, features 3, deploy-checklist 3, rivals 1 = 66. `fabrik-review.md:11` "close it only at the quiet delta round"; `fabrik-ui-design-review.md:140` "(parallel grounders per axis)", `:143` "one INDEPENDENT grounder each".
5. **The hop is defined by example only**: `term-edit.md:27` "delta over § 3, § 7 + one hop"; `fabrik-review.md:508` "delta over pass 1's fix diff + one hop"; `fabrik-repo-review.md:156` "the DELTA rounds, over the fix diff plus one hop of callers and callees"; `fabrik-review.md:422-434` defines round 1 as the only full pass and every later round as a delta but bounds nothing. The word "hop" appears in no rule sentence of `core/62`.
6. **Seat sizing today**: `fabrik-review.md:438` "The closing delta round ALWAYS carries a fresh, non-authoring finder seat"; `fabrik-review-scoped.md:60-75` "The floor is 3 readers … three readers of the same one-unit diff on different angles, `dispatch_headroom.py --units 1`"; D-208 keeps the floor for `/fabrik-review-scoped` and grounding surfaces; D-218 sizes a `term-edit` delta round "by the fix (one seat for one paragraph plus the hygiene script)" — the code loops and the coverage loops have no such sentence.
7. **The route-up**: `fabrik-review-scoped.md:27-33` — ">5 files → STOP and run the full `/fabrik-review` instead … Invoked per phase/ticket by a `Profile: small` plan: step 1's trigger is SATISFIED by the plan's Finish `/fabrik-review` … record `ROUTED-TO-FINISH: <trigger>` and continue the light pass here"; `:32-33` "Step 5's three-rounds trigger still escalates". Under `Profile: small` the scoped loop therefore runs to its own close and the heavy loop repeats the diff (Phase A: 67 + 266 min).
8. **Round zero**: the orchestrator's pre-pin probe exists as prose in `term-edit.md:16-18` (RESIDUE before every pin: re-read edited paragraphs, grep old wording, hygiene script) for DOCUMENT loops; no sentence in `term-coverage.md`, `fabrik-review.md` or `subagents-core.md` names the CODE-side probe (mutants asserted dead by test name on a fresh copy, environment-bound tests deselected, `__pycache__` purged).
9. **The git-verb prohibition**: `commands/_agents/fabrik-reviewer.md:33` already says "Read-only — and that includes git. Never edit, write, or commit, and never `git checkout --`, `git restore`, `git stash`, `git reset`"; `fabrik-researcher.md`, `design-review.md`, `fabrik-gui.md` carry no git sentence; no seat BRIEF template (`subagents-core.md`, the `/fabrik-review` and `/fabrik-docs-review` brief paragraphs) carries it — and the pass-9 docs-review seat that ran `git stash --keep-index` was a `fabrik-reviewer` briefed by a prose brief that said only "never write into /opt/fabrik". `CLAUDE.md` § Shared repo names the stash hazard for the ORCHESTRATOR and carries no recovery recipe for a seat's stash.
10. **The Finish docs loop**: `fabrik-execute-plan.md:272` runs `/fabrik-docs-review` at Finish over docs the plan changed; `:400-406` "whole-plan doc-coverage RECEIPT … run /fabrik-docs-review → converge docs to a truthful fixed point"; nothing excludes docs the whole-plan `/fabrik-review` already graded as review surface (the archived plan's `FINAL_GATE_WORKFLOW.md` rows were graded by both loops).
11. **The graders**: `check_convergence.py::_closing_row_fail` refuses a CONVERGED/EXECUTED flip whose last Pass row does not read `confirmed: 0`; `check_review_coverage.py` demands a quiet final ledger row and reads `confirmed:` where present; `check_review_hygiene.py --surface` grades the rendered corpus for retired phrases (`--phrase`), residue and table shape; `tests/enforcement/test_flip_gate_matrix.py` pins the flip-gate invocation matrix; `tests/test_assemble_dispatch_step.py` pins the assembler's FLOOR strings and kinds.
12. **The decision rows**: D-206 (the counter), D-207 (partition by file), D-208 (the floor retired for the two partitioned code loops, KEPT for grounding surfaces and `/fabrik-review-scoped`), D-212 (the family moves under D-203 now), D-218 (the floor stands down for a `term-edit` loop that partitions by section; a delta round sized by the fix).

Profile trigger check: every intake item maps to text that exists today (rows 1–12); the delta is a change to existing fragments, sources, agent definitions and one pack sentence — no new component, no new script. `Profile: delta` holds.

## The delta

Every item CITES the rulings and the landed mechanics; nothing re-narrates them.

- **D1 — the five fragment-less loops move under D-203 by INCLUSION, not by a third fragment.** `/fabrik-docs-review`, `/fabrik-rules-review`, `/fabrik-epics-review` and `/design-review` include `term-edit` (their artifact is a document set, a rule set, an epic set, a screen set — the edit-shaped contract) with each command's own ARTIFACT / DONE_WORD / AXES fragment parameters (the assembler's substitution slots) and its exit vocabulary rewritten to the fragment's (the "no-op pass" of `fabrik-docs-review.md:87,141-165`, the "identical gap list" of `fabrik-rules-review.md:10`, the "forces the no-op" of `fabrik-epics-review.md:19`, the "ZERO issues" of `design-review.md:39` — each becomes a citation of the fragment's closing round); `/fabrik-review-scoped` includes `term-coverage` (its artifact is a diff with a class ledger) and keeps D-208's three-reader floor at ROUND 1 only (see D5). A third fragment is rejected (§ Rejected alternatives 1).
- **D2 — `term-coverage.md` gains the `confirmed:` counter and the same closing-row grammar as `term-edit`**: its exit row reads `confirmed: 0 · fixed: 0 · unexecuted: 0` (D-206), `found:`/`new:` stay as recall and the stall-breaker keys on `confirmed:` (three consecutive non-decreasing nonzero delta rounds), the D-048 history clause is deleted (present-tense rule, `core/40`), and its five consumers are verified by execution to render the counter (`check_review_hygiene.py --surface ~/.claude/commands/<each>.md --phrase 'found: 0 · new: 0 · fixed: 0'` → 0 hits; `/fabrik-conformance-review`'s 0 `confirmed` mentions become ≥1 by inclusion alone).
- **D3 — the 66 restatements are deleted or rewritten as citations** in the 11 `term-edit` consumers, plus `fabrik-review.md:11` and `fabrik-ui-design-review.md:140,143`; the acceptance grep is the five-phrase grep on the SOURCE surfaces → 0 hits outside a fenced quotation, and `check_review_hygiene.py --surface <rendered corpus> --phrase` for each of the five phrases → 0 hits.
- **D4 — THE BOUNDED HOP, in the fragment text (F1).** `term-edit.md` and `term-coverage.md` each gain ONE sentence defining the delta round's surface: *a CONFIRMED defect of a delta round is a defect of a line INSIDE the previous round's fix hunks, or a live contradiction those hunks created with a sentence of the same section; a defect one hop out — a caller, a callee, a neighbouring section, a pre-existing claim — is RECORDED with a named destination (a backlog row, a mail, a sibling ticket) and never counted, even when real and executed.* The ledger's `confirmed:` and the record's `--confirmed` count the SAME thing under this rule (the two-number convention of the archived plan's receipt is retired). `subagents-core.md` and the `/fabrik-review` / `/fabrik-repo-review` / `/fabrik-docs-review` brief paragraphs cite the sentence instead of "plus one hop of callers and callees". Grader: `check_review_hygiene.py --phrase 'plus one hop'` → 0 hits over the rendered corpus outside the fragment's own sentence; the flip-gate matrix unchanged.
- **D5 — DELTA ROUNDS SIZED BY THE FIX (F2).** Round 1 is the only full pass and keeps its partition (D-207) or its floor (D-208 for `/fabrik-review-scoped` and grounding surfaces). Every later round dispatches by the size of the previous round's fix diff: under a stated budget — **20 changed lines** (the value is a parameter of the fragment, one place) — ONE fresh non-authoring seat plus the hygiene script; above it, the round-1 partition over the touched slices. `dispatch_headroom.py` prints the size: `--slices` or `--units` as today, plus `--delta <changed lines>` which prints `SEATS: 1` under the budget (a stamp is still owed). Needs a D-row narrowing D-208's "KEPT for … `/fabrik-review-scoped`" to round 1 (§ Decisions taken). Grader: `tests/test_assemble_dispatch_step.py` pins the two FLOOR strings' new clause; `dispatch_headroom.py`'s test pins `--delta 4 → SEATS: 1`, `--delta 21 → the partition`.
- **D6 — THE ROUTE-UP REPLACES THE SCOPED LOOP (F3).** `fabrik-review-scoped.md:27-33`: when step 1's trigger fires (>5 files, a gate/hook/enforcement path, auth/schema/migration/concurrency, the corpus renderer) the command hands the diff to `/fabrik-review` IMMEDIATELY — it records `ROUTED-UP: <trigger>` with 0 rounds and closes its record by name; under `Profile: small` it does the same, deferring to the plan's Finish `/fabrik-review` and running NO light rounds of its own (the current "continue the light pass here" sentence is deleted). Step 5's three-rounds trigger stays for the surfaces that did not trip step 1. Grader: a `command_run.py` probe under scratch env — a scoped record closed with `ROUTED-UP` and `rounds: 0` is TERMINAL by the route, not by a quiet round (a `command_run.py` change: `done --routed-up <trigger>` accepts a 0-round record; red-first test in `tests/test_command_run*.py`).
- **D7 — ROUND ZERO IS THE ORCHESTRATOR'S PRE-PIN PROBE (F4), stated in both fragments.** Before any seat sees a delta: every mutant a fix names is asserted dead by the NAME of the failing test on a fresh copy of the pin, with environment-bound tests deselected and `__pycache__` purged; every added line is re-read whole (length, citations, claims); the class of the fix is swept (the siblings of the shape). A round whose seats confirm only residue of the previous round's fix is the signal to sweep the class, not to run another round. This extends `term-edit.md:16-18`'s RESIDUE obligation to code loops (`term-coverage.md`) and names the code-side method; the Pass Ledger's `method:` cell may read `method: round-zero probe — <what>` on the row that records it. Grader: none mechanical — the receipt's Pass row names it (the coverage gate already reads the method cell); the lesson entry cites the measurement.
- **D8 — THE GIT-VERB PROHIBITION in every seat brief and every agent definition (F5).** `subagents-core.md` gains the sentence *a seat runs NO git command that mutates state in the shared tree — no stash, checkout, reset, restore, apply, commit, clean; read-only git only (`show`, `diff`, `log`, `status`, `ls-files`); every probe on a copy*; the four agent definitions (`fabrik-reviewer` already carries it at `:33`; `fabrik-researcher`, `design-review`, `fabrik-gui` gain it) carry the same sentence; `CLAUDE.md` § Shared repo gains the recovery recipe for a seat's stash (`git stash show --name-only 'stash@{0}'`, then `git show 'stash@{0}':<path> > <path>` per file, md5-verified against the pre-incident values, the entry left for a human — never a pop, which the classifier blocks). Grader: `check_review_hygiene.py --surface commands/_agents/ --phrase 'git stash'` → 4 of 4 definitions carry the prohibition sentence (a positive-presence check: the hygiene script's `--symbol` mode, or a new `tests/test_agent_definitions.py` case, whichever exists — extend, never duplicate).
- **D9 — NO SECOND DOCS LOOP OVER DOCS THE HEAVY REVIEW GRADED (F6).** `fabrik-execute-plan.md:272` and `:400-406`: the Finish `/fabrik-docs-review` runs over the plan's docs MINUS the docs the whole-plan `/fabrik-review` already graded (its receipt's Coverage Checklist names them); the Finish brief lists the excluded docs with the receipt row that graded each. When the set is empty the step records `SKIPPED — every changed doc was review surface` and the plan's Execution note says so. Grader: the plan-quality check already reads Execution notes; a red-first test in `tests/enforcement/test_check_plan_quality*.py` accepts the `SKIPPED —` shape (extend the existing one).

## Chosen approach (and why it is the lean one)

Inclusion over a third fragment; one sentence for the hop and one number for the delta budget, each in exactly one place (the two fragments), cited everywhere else; every other change deletes text (66 restatements, the D-048 clause, the "continue the light pass" sentence) or moves a duty to where its holder reads it (the agent definitions, the seat brief). Two scripts change by one flag each (`dispatch_headroom.py --delta`, `command_run.py done --routed-up`), both with red-first tests on their existing suites. No new script, no new dependency.

## Rejected alternatives

1. **A third fragment (`term-loop`) for the five loops** — rejected: it would restate `term-edit`'s exit in different words, the defect `core/40`'s single-source rule and the predecessor's rounds 8–11 (a fragment that restated the pack re-opened four times) exist to prevent; the five loops are edit-shaped or coverage-shaped, both fragments already exist.
2. **A round cap** — rejected by D-203 R6 and the carried rulings; the bounded hop ends loops by construction, not by count.
3. **Counting one-hop findings as confirmed but not requiring a fix** — rejected: a counted-but-unfixed row is exactly the non-quiet ledger `check_review_coverage.py` refuses; RECORDED with a destination is the family's existing disposition (D-206).
4. **Sizing delta rounds by the floor with cheaper models (Haiku)** — rejected by D-208's evidence (Haiku seats confirmed nothing in the D-191 rounds 15–18) and D-190's pricing; the saving is in seats per round, not price per seat.
5. **Keeping the scoped loop's three rounds before a route-up "for the light pass's own value"** — rejected by the Phase A measurement: 67 minutes bought nothing the heavy loop did not redo.
6. **A hard gate that refuses a `git stash` from a seat** — rejected: the classifier already blocks the recovery and not the act; a tool-level guard on stash is outside this repo's reach (the harness), so the control is the brief text plus the recovery recipe; measured fire rate before any check: 1 incident in ~120 seats.
7. **Running the Finish docs review over everything and de-duplicating findings afterwards** — rejected: the duplicate cost is the seats and the passes, not the findings.

## Contract deltas

None to `docs/data-contract.md` or `docs/ui-design.md` (no data, no screens). Command-corpus contract: `term-edit.md` and `term-coverage.md` gain one hop sentence, one delta-budget number and the round-zero paragraph; `term-coverage.md` gains the `confirmed:` counter; `subagents-core.md` gains the git-verb sentence; `dispatch_headroom.py --delta` and `command_run.py done --routed-up` are additive flags (a caller passing neither behaves as today — the MIRROR: no existing invocation breaks; the two FLOOR strings the assembler renders change wording, pinned by their test).

## Cost

- Corpus: `term-edit.md` +~6 lines; `term-coverage.md` +~8 / −~6 (the counter, the hop, the D-048 history clause deleted); `subagents-core.md` +2; `fabrik-review-scoped.md` −~8 / +~4; `fabrik-docs-review.md` −~20 / +~6 (the include replaces its loop paragraphs); `fabrik-rules-review.md`, `fabrik-epics-review.md`, `design-review.md` −~6 / +~3 each; the 11 consumers −66 restatements (+ ~11 citation lines); `fabrik-review.md` and `fabrik-repo-review.md` −2 / +2 (the hop citation); `fabrik-execute-plan.md` +~6; four agent definitions +1 each; `CLAUDE.md` § Shared repo +~4 (the recipe) and `templates/governance/CLAUDE.md` the same bullet; `core/62` § Role separation +1 sentence (the hop, cited by the fragments).
- Code: `scripts/sysadmin/dispatch_headroom.py` +~25 (`--delta`); `scripts/command_run.py` +~15 (`done --routed-up`); tests +~60 across their existing suites. Fleet-synced text: `core/62`, both `CLAUDE.md`, `command_run.py` (RUN_SCRIPT) — the plan's ONE forced sync at Finish.
- Plan shape: `Profile: small` (D-169) — code diff 2 files / ~40 lines, tests excluded; the corpus edits are text. Three phases: A the two fragments + `subagents-core` + the two flags with their tests; B the five loops' inclusion + the 66 restatements + the route-up + the Finish docs-loop rule; C the agent definitions, `CLAUDE.md` × 2, `core/62`, the docs, the sync, the heavy round.
- Expected saving, to be MEASURED (§ Lifecycle): a Finish `/fabrik-review` of a small plan from 12 rounds / 34 seats / 298 min to ≤5 rounds / ≤10 seats / ≤90 min; a Finish docs review from 12 passes / 37 seats to ≤3 passes / ≤5 seats or SKIPPED; a `Profile: small` Phase A from 67 + 266 min to the heavy loop alone.

## Validation

- **V1** — red-first: the flip-gate matrix and `test_assemble_dispatch_step.py` pin the new FLOOR/hop strings (a mutant restoring "plus one hop of callers and callees" turns a test red); `dispatch_headroom.py --delta 4 → SEATS: 1`, `--delta 21 → partition`; `command_run.py done --routed-up` on a 0-round scratch record → TERMINAL by route, and refused without the flag.
- **V2** — the five-phrase grep on the 11 sources → 0 hits outside fences; `check_review_hygiene.py --surface ~/.claude/commands/ --phrase` × 5 → 0; `--phrase 'plus one hop'` → 0 outside the fragment sentence; `--phrase 'found: 0 · new: 0 · fixed: 0'` over the five `term-coverage` consumers → 0.
- **V3** — `python3 commands/assemble_commands.py --check` clean; `check_command_corpus.py` green; every render from the main checkout.
- **V4** — this spec's own `/fabrik-spec-review` under D-212 with D4/D5 applied to itself: the delta after pass 1 is one seat per small delta; the Pass Ledger states where the hop stopped.
- **V5** — the four agent definitions each carry the git-verb sentence (positive-presence check); `CLAUDE.md` and its template bullet byte-identical (`diff`).
- **V6** — the first three reviews under the landed text (one `/fabrik-review` Finish, one `/fabrik-docs-review`, one `/fabrik-review-scoped` that routes up) measured from the feedback ledger: rounds, seats, wall-clock, and the count of RECORDED-one-hop rows per receipt.

## Decisions taken

- **At approval (minted by the approving turn):** the spec's approval row; a row narrowing D-208 — the three-reader floor of `/fabrik-review-scoped` and the grounding surfaces applies to ROUND 1; every later round is sized by the fix under the fragment's delta budget (one fresh seat under 20 changed lines); a row stating the bounded hop as the family's delta rule (the fragment sentence is the text; the row is the ruling).
- **Not decided here:** the delta budget's exact value beyond 20 (V6 measures it); a harness-level guard on `git stash` (outside this repo).

## Lifecycle

Lands via one small plan; V6 measures the saving on the first three reviews and re-pins the budget if the RECORDED-one-hop rows show real defects escaping (a RECORDED row with a destination is never lost — it is a backlog row, so the fix is a ticket, not a re-opened loop); degradation: a loop that trips the breaker under the bounded hop names its foundation error as today; retired when the family is folded into one termination fragment, if ever.

## Grounding (external facts — the approach floor; fetched 2026-09-11 by one native `fabrik-researcher` seat, quotes verbatim after whitespace normalisation; the orchestrator probes each URL's status at the flip)

| G# | Claim the approach rests on | Source | Verdict |
|---|---|---|---|
| G1 | review effectiveness falls with the size of the reviewed change and the time spent (why a delta round bounds its surface) | SmartBear, "Best practices for peer code review" (the Cisco study): "developers should review no more than 200 to 400 lines of code (LOC) at a time… a review of 200-400 LOC over 60 to 90 minutes should yield 70-90% defect discovery" — https://smartbear.com/learn/code-review/best-practices-for-peer-code-review/ (fetched 2026-09-11 on two arms; HTTP 200 at the flip probe) | VERIFIED |
| G2 | a mutant's kill can be nondeterministic — timeouts and external load (why round zero asserts a kill by test name on a fresh copy, and why the filesystem-order kill of the archived plan's round 8 was a real class) | PIT FAQ: "a mutant may be detected as timed out on one run, but killed or surviving on another" — https://pitest.org/faq/ (fetched 2026-09-11; HTTP 200 at the flip probe) | VERIFIED |
| G3 | `git stash` saves the working directory and index state and reverts the working directory to HEAD (why a seat's stash sweeps every session's files) | git-scm.com, `git stash` DESCRIPTION: "The command saves your local modifications away and reverts the working directory to match the HEAD commit." — https://git-scm.com/docs/git-stash (fetched 2026-09-11; HTTP 200 at the flip probe) | VERIFIED |

Internal measurements (the primary evidence): the feedback ledger rows in § Why this exists; the archived plan's receipt (`docs/development/reviews/2026-09-10-plan-1-review-family-adoption-review.md`, rows M1–S2 and Pass 8's non-convergence note); the docs-review summary in this session's scratch (12 passes, the BAR imposed at pass 9); `docs/LESSONS_LEARNT.md` 2026-09-11.

## fabrik-lib verdict

One line: no capability is vendored, enhanced or built — the delta is command text, two additive flags on hub RUN_SCRIPTS, and one pack sentence; `fabrik-lib/README.md` offers no review-loop module.

## Constraints digest

| # | Rule (verbatim) | Pack `file:line` | How this spec obeys it |
|---|---|---|---|
| C1 | "Role separation (review loops) — who hunts LAST is never the author" | `.windsurf/rules/core/62-using-subagents.md:184` | the closing round keeps a fresh non-authoring seat under D5; round zero is the author's probe, never the closing read |
| C2 | "loop is a delta round with a fresh seat (D-212). **One sanctioned exception — the solo" | `core/62-using-subagents.md:190` | D1 cites the exception's home; the five loops include the fragment that cites it |
| C3 | "**⚠️ THE OPENROUTER POOL IS OFF — operator ruling D-181 (2026-09-07), OFF BY POLICY" | `core/62-using-subagents.md:65` | every seat native; D5's one-seat delta is a native seat |
| C4 | "Source, config, or Docker file changed \| `CHANGELOG.md` entry under `## [Unreleased]`; `INDEX.md` reflects change" | `core/40-documentation.md:66` | the plan's per-phase CHANGELOG entries; INDEX rows for this spec and the plan |
| C5 | "Internal plans, changelogs, and developer notes are exempt from brand voice — clarity and speed matter more than tone." | `core/40-documentation.md:205` | the fragment sentences are rules, present tense, one place each |
| C6 (FLOOR) | "Scaffolded doc templates, Documentation Sync Matrix, changelog, INDEX.md, writing style" | `core/40-documentation.md:7` | § Documentation landing sites |

FLOOR packs core/25, core/30, core/35 and the 12-factor axes: read; unconstrained here (no data, no ops, no auth surface) — stated, not skipped.

## Shape / infra implications

None: the hub has no `project.yaml`; nothing deploys. Box-wide render of the corpus; fleet sync of `core/62`, both `CLAUDE.md` and `command_run.py`.

## Documentation landing sites

`docs/workflows/FINAL_GATE_WORKFLOW.md` (the `term-coverage` counter and the hop sentence as the graders read them); `docs/reference/command-run-protocol.md` (`done --routed-up`); `docs/workstation/` nothing; `CHANGELOG.md` per phase; `INDEX.md` rows for this spec and its plan; `docs/DECISIONS.md` the rows above; `docs/STRATEGIC_BACKLOG.md` row 61 → SHIPPED at the plan's archive.

## Open / blocking unknowns

- Resolved: the `term-coverage` population (five, not three); the reviewer definition already carries the git sentence (D8 is the briefs and the other three definitions).
- Open, with a resolution step: whether `command_run.py`'s TERMINAL logic accepts a 0-round record cleanly (`terminal = quiet and len(rounds) >= 2` at `:391` per the backlog row) — the plan's Phase A red-first test decides the shape (`--routed-up` sets a terminal-by-route flag the `done` path reads).

## Machinery report

DRAFT written 2026-09-11 from the run record's open; the intake enumerated from the conversation (12 items); the counts re-derived on the sources this turn; one researcher seat dispatched for G1–G3 (the approach floor); no external vendor fact asserted. The operator asked for the answer before the machinery ("answer my question before invoking a fabrik-spec command") — the close-out presents the ask ↔ spec table first.
