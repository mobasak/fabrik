# Review convergence redesign — partitioned single pass, delta rounds, zero-CONFIRMED quiet round

Status: DRAFT
Profile: delta
Owner: infra
Date: 2026-09-08
Ruling: D-203 (the operator's five rules, minted by the sibling hub session mid-review; this spec is the delta that ships them) — the supersede rows for D-048, D-191 and the D-186/D-188 floor are minted at approval.

## In one line

A `/fabrik-review` or `/fabrik-repo-review` closes on a QUIET round, and quiet now means: the partitioned pass confirmed zero code or doc defects by execution. Refuted candidates never count. Every file is read once per round by exactly one model, chosen by what it is good at, and every round after the first reviews only the previous round's fix diff plus its callers.

## Intake Inventory

The conversation that invoked this spec (2026-09-08, this session) stated the items below in the operator's own words. IN = covered at the named section.

| I# | Item (anchored) | Disposition | Where |
|---|---|---|---|
| I1 | "currently our reviews are taking too much time, even days, and we cant work proper work efficiently. we need to fix this." | IN | § Why this exists · § Goal |
| I2 | "what does this say? https://agentpatterns.ai/code-review/review-then-implement-loop/" | IN | § Grounding (G1) — the page's one-pass-then-escalate rule, and why this delta adopts its verification gate but not its single-pass cap |
| I3 | "what are the current best practises to use?" | IN | § Grounding (G1–G9) · § Chosen approach |
| I4 | "exit only quite round should stay." (R1) | IN | § The delta D1 · § Decisions taken R1 |
| I5 | "A refuted candidate counts as a fresh finding: this is wrong, it is definetly not." (R2) | IN | § The delta D1, D6 · § Decisions taken R2 |
| I6 | "i keep saying you use more agents, i was thinking you are dividing tasks amongst the agents according to their type, and in a single pass, they make a combined full pass. the way we do currently is wasteful." (R3) | IN | § The delta D2, D3 · § Decisions taken R3 |
| I7 | "we have fable, opus, sonnet, haiku, all agents must be used efficiently and wisely not wastefully." (R4) | IN | § The delta D2, D4 · § Decisions taken R4 |
| I8 | "while fixing, if you create new errors, they must be definetely fixed, in this case, we can review only the fix without making ful pass" (R5) | IN | § The delta D5 · § Decisions taken R5 |
| I9 | "i want to switch to 'A review closes on a round with zero confirmed code or doc defects'" | IN | § The delta D1 · § Decisions taken R1/R2 |
| I10 | "i want to see all these decisions in the created spec, do not skip a single thing/ good decisions." | IN | § Decisions taken — every ruling R1–R11 and every design decision DD1–DD9 has its own row |
| I11 | "i am planning to accept it and update /fabrik-review and /fabrik-repo-review" | IN | § The delta — both commands are the primary surfaces; § Documentation landing sites |
| I12 | "but first what will we lose/drop tell me" | IN | § Rejected alternatives (the redundancy trade, stated) · § Lifecycle (degradation) |
| I13 | The BLOCKED D-191 receipt "flips to CONVERGED under the new rule once this ships" (R11) | IN | § The delta D9 (first application) |
| I14 | The seat-brief lessons of the D-191 review (R10: pin once, `git init` the pin, `KAIZEN_EVENTS_DIR` on every probe, restore inside one Bash call, never bare-grep, Python `time.sleep`, 15-min box) | IN | § The delta D8 |
| I15 | The NON-CONVERGENCE escalation stays as the only other exit (R6) | IN | § The delta D1 · § Decisions taken R6 |
| I16 | The seat budget still runs through `dispatch_headroom.py`, sized by slices (R7) | IN | § The delta D3 · § Decisions taken R7 |
| I17 | The consensus/critic rule: a one-seat, unreproduced candidate is dropped (R8) | IN | § The delta D6 · § Decisions taken R8 |
| I18 | `confirmed:` on the ledger row, `--confirmed` on `round`, backward compatibility for in-flight receipts (R9) | IN | § The delta D6, D7 · § Contract deltas |
| I19 | The pool stays OFF (D-181/D-182); D-190 pricing stays; no new dependency; red-first graders | IN | § Constraints |

Intake: 19 items — 19 IN, 0 OUT-OF-SCOPE, 0 ASK. Every item derives from the operator's rulings this turn or from the frozen ledger; no question cleared the bar.

## Personas

**Primary persona, in the operator's own words:** *"currently our reviews are taking too much time, even days, and we cant work proper work efficiently."* — the OPERATOR who waits on a review to close before the next piece of work can start.

The primary's minimal loop, counted (the frozen STEP BUDGET downstream contracts meet or bump):

1. Invoke `/fabrik-review <surface>` (or `/fabrik-repo-review`).
2. Round 1 runs: one partitioned full pass, all seats in one message, 15-minute box.
3. The orchestrator adjudicates by execution and fixes what is CONFIRMED.
4. Round 2 runs on the fix diff plus callers only.
5. The round confirms zero → the receipt flips to CONVERGED, the run closes.

Five steps; step 4 repeats only while a delta round confirms something. Today the same loop is steps 1–3 repeated as full passes without a bound (18 times on the D-191 review).

Every duty the delta creates names its holder:

| Persona | Role in this delta | Duty |
|---|---|---|
| Operator | rules on the closing bar; reads the receipt | approves this spec; owns the D-rows |
| Orchestrator session (Fable, or Opus by name when Fable refuses) | partitions the surface, dispatches, adjudicates | EXECUTES every refutation and every confirmed reproduction (D6); never a finder |
| Opus seat | reviews the risky slices only | returns candidates with a concrete failure scenario |
| Sonnet seats | review the ordinary code and doc slices | same |
| Haiku seats | sweep the grep-shaped classes surface-wide, one seat per class | return `file:line` hits; most classes become the close-out script (D4) |
| `check_review_coverage.py` (gate, fleet-synced) | grades the receipt | reads `confirmed:` as the exit counter; keeps the old rule for ledgers without it (D7) |
| `check_convergence.py` QUIET_PASS (gate) | grades plans/receipts for convergence claims | its quiet test follows D7's grammar |
| `command_run.py` (fleet-synced) | the run record | `round --confirmed <n>`; TERMINAL fires on confirmed == 0 with a class-ledger close (D7) |
| `dispatch_headroom.py` | the seat budget | sizes by SLICES, prints the partition mix (D3) |
| Sibling sessions | subtract the stamp | unchanged: budget → stamp → dispatch in one breath |
| The ~46 synced projects | run the same commands and gates | receive the change by the post-commit governance sync; in-flight receipts keep parsing (D7) |
| `/fabrik-execute-plan` | invokes `/fabrik-review` at phase boundaries | inherits the new exit; nothing else changes for it |

## Goal

Cut a review's wall-clock from days to about one full pass plus a few short delta rounds, without lowering what "reviewed" means: every confirmed defect is still fixed with a red-first guard, every class is still swept, and the exit is still a quiet round.

## Why this exists

Measured on this box, 2026-09-08, the `/fabrik-review` over D-191..D-194 (`docs/development/reviews/2026-09-08-box-bound-seats-d191-review.md`):

| Measure | Value |
|---|---|
| Rounds | 18 (closed BLOCKED on the bar contradiction, not on a defect) |
| Wall-clock | ~8.3 h of run-record time |
| Seats per round | 6–11; ~1.3M seat tokens per round |
| Raw-candidate series | 24→16→27→15→17→18→23→38→28→16→14→15→13→16→8→14→12→11 — never quiet |
| Confirmed defects, rounds 16–18 | from the Opus seat and one Sonnet seat; the Haiku seats produced zero confirmed defects in rounds 15–18 |
| Fix residue | the confirmed defects of rounds 14–17 were each in the previous round's fix |
| Round 18 | 0 confirmed defects, 11 raw candidates (grader hardening, doc wording, refuted mechanical claims) — not quiet under D-048 |

Three causes, each a rule rather than a defect in the code under review: (a) D-048 counts a refuted candidate as fresh, so a surface this size never produces a quiet round; (b) D-191 gives every unit a Sonnet seat AND a Haiku seat with an Opus seat over everything, so each file is read two or three times per round; (c) every round is a full pass, so a fix that touched four files costs a forty-minute sweep of ninety. The same shape elsewhere: brand-identity-creator's primary-text review ran 35 passes (their D-021/D-022, 2026-09-06); web-ecommerce-factory's T01 review ran 42 rounds without a quiet round (their D-105, 2026-09-04).

How the delta resolves exactly that: (a) becomes "quiet = zero CONFIRMED, executed"; (b) becomes a partition, one model per slice; (c) becomes delta rounds. Under the new rules the D-191 review would have closed around round 9 at roughly a third of the seat spend (the receipt's own round series: the last confirmed code defect that was not fix residue landed in round 12; rounds 13–18 were fix residue and refuted candidates).

## What exists today (grounded)

| Surface | Today | Anchor |
|---|---|---|
| `/fabrik-review` exit | "This pass found or fixed anything → you are structurally not done. Go back to Phase 1 and run a fresh, fully-independent finder round" | `commands/_sources/fabrik-review.md:364` |
| `/fabrik-review` completion claim | "only when the last row is `found: 0 · new: 0 · fixed: 0`" | `commands/_sources/fabrik-review.md:437` |
| `/fabrik-repo-review` exit | "You EXIT when, after that pass, every checklist row is adjudicated" — and its waves (round 14–16 of the D-191 review) | `commands/_sources/fabrik-repo-review.md:154`, `:64` |
| The seat rule (D-191) | "every unit gets one Sonnet breadth seat AND one Haiku mechanical seat … plus the Opus authoritative seat(s)" | `commands/_fragments/subagents-core.md:3` · `CLAUDE.md:355` · `.windsurf/rules/core/62-using-subagents.md:65` |
| The three-seat floor (D-186/D-188) | "NEVER solo, never two — the FLOOR is three seats" | `commands/_fragments/subagents-core.md:3` |
| The seat budget | `full_mix()` = one Sonnet per unit + Haiku per unit (or `--mechanical`) + Opus per risky unit; `FLOOR = 3`; `trim()` | `scripts/sysadmin/dispatch_headroom.py:352`, `:42`, `:373`, `:404` |
| The gate's exit rule | "final ledger round raised N (a FRESH candidate counts even when refuted … D-048) — the exit round must be quiet" | `scripts/enforcement/check_review_coverage.py:584` |
| The ledger row grammar | `\| found: N \| fixed: M \|` cell-anchored; Pass-labelled lines parsed by `_unparsed_pass_lines` / `_ledger_shapes` | `scripts/enforcement/check_review_coverage.py:996`, `:1023`, `:1064` |
| The run record's round | `round --seats --findings --classes-swept --classes-new`; TERMINAL requires `bool(classes) and not open_c and findings == 0 and bool(last.get("swept"))` | `scripts/command_run.py:1546`, `:320` (the `terminal =` block) |
| The oscillation advisory | `PER_UNIT_ROUND_COMMANDS = {fabrik-execute-plan, fabrik-repo-review}` | `scripts/command_run.py:274` |
| The unstamped-seat nudge | counts seat transcripts newer than the round | `scripts/command_run.py:1976` |
| The run-record paragraph | "A round that sweeps every known class with 0 findings IS the no-op round" | `CLAUDE.md` § COMMAND RUN-RECORD |
| The prior exit ruling | D-048: `found: 0 · fixed: 0` canonical; a re-raise of a standing row is cited, never counted; a fresh candidate counts even when refuted | `docs/DECISIONS.md` D-048 |
| The receipt of the first application | BLOCKED at round 18 with a `## BLOCKED: spec contradiction` section | `docs/development/reviews/2026-09-08-box-bound-seats-d191-review.md` § BLOCKED |

Every item of the Intake Inventory maps to code or contract text that exists today; the profile trigger holds — this is a delta on existing engines.

## The delta

### D1 — Quiet is redefined; the exit stays a quiet round (R1, R2, R6)

- A round is QUIET when its pass (full or delta) CONFIRMED zero code or doc defects. `found:` keeps counting raw candidates (the seats' recall); `confirmed:` is the exit counter.
- CONFIRMED means EXECUTED: a probe on a pinned copy, a failing test, or a mutation on a copy that the grader turns red. A candidate the orchestrator cannot execute is RECORDED with the reason and does not count; a candidate executed and shown false is REFUTED and does not count. Neither reopens the loop. This supersedes D-048's "a fresh candidate counts even when refuted".
- The only other exit stays: `## BLOCKED: NON-CONVERGENCE` after three non-decreasing nonzero delta rounds, naming the suspected foundation error; and the three sanctioned BLOCKED cases. No round cap.
- "Quiet cannot be reached by relabelling": a candidate with a concrete failure scenario that the orchestrator did not execute may not be REFUTED — it is RECORDED as `unexecuted`, listed in the receipt's residual section, and the receipt says how many such rows the closing round carries. A closing round with unexecuted PLAUSIBLE code candidates is not quiet.

### D2 — One combined pass, partitioned by model (R3, R4)

- The surface is cut into DISJOINT slices. Each slice goes to exactly one seat, by kind:
  - **Opus** — the risky units only: concurrency and locks, record and file formats, fleet-synced surfaces (`scripts/enforcement/`, `scripts/command_run.py`, the hooks, `templates/governance/`), auth, schema, migrations, secrets handling.
  - **Sonnet** — every other code and doc unit.
  - **Haiku** — the grep-shaped classes, ONE seat per class across the whole surface (stale phrases, table and fence shape, dead symbols, inventory counts, `{{` residue).
  - **Fable** (the orchestrator; Opus by name when Fable refuses) — partitions, dispatches, adjudicates, executes every refutation and every confirmed reproduction. Never a finder.
- The union of the slices IS the full pass. No file is read by two seats in one round. The authoritative second read that D-191 put over everything is replaced by the orchestrator's execution of every candidate (D6).
- Sizing on the D-191 review's surface: 3 risky units (Opus ×1 with all three, or ×3 when independent), 5 ordinary units (Sonnet ×5), 3 grep classes (Haiku ×3 in round 1, the script thereafter) → ~5–9 seats in round 1, 2–4 in a delta round, against 10–11 every round today.

### D3 — The seat budget is sized by slices (R7)

- `dispatch_headroom.py` gains `--slices opus=<n>,sonnet=<n>,haiku=<n>` (the partition the orchestrator computed) and prints `SEATS:` = min(Σ slices, the CLI cap, the box cap minus sibling seats, quota headroom), trimming Haiku first (its classes fold into the script), then extra Opus, then Sonnet, never below one Opus when a risky slice exists. `--units/--risky/--mechanical` stay for the commands that size by units (spec/plan grounding); `full_mix()` keeps serving them.
- The 15-minute seat time box stays. Budget → `dispatch --seats <n>` → the seats, in one breath, stays. The 25-minute sibling reservation stays.
- The floor under partition (re-deciding D-186/D-188 for tiny surfaces): every non-empty slice kind present in the surface gets its seat; a surface with no risky unit still dispatches one Opus seat over its most consequential slice; a one-file surface may be one Opus seat plus the close-out script. The measured "three seats on different angles" rule is retired for review loops — the third angle is the orchestrator's execution, not a third reader. (D-186/D-188 stay in force for grounding and adjudication surfaces: spec and plan grounding still run the researcher floor.)

### D4 — Most of Haiku's work becomes a script at close (R4)

- The grep-shaped classes that every review re-sweeps (stale phrases named in the brief, `{{` residue in rendered commands, receipt row shape and verdict words, fence parity, CHANGELOG entry shape, dead symbols by `grep -c`) move into `scripts/enforcement/check_review_hygiene.py`, run by the orchestrator at each round's close and by `check_review_coverage.py` at the flip. A Haiku seat is dispatched in round 1 only for a class the script cannot express (a judgement-shaped inventory), and only if that class is in the brief.
- Fire rate before it blocks: the script runs advisory for its first 20 receipts fleet-wide (the D-033 tier), measured from the feedback ledger; it graduates to a gate error only when its false-positive rate on those receipts is below 5 % (the codeant.ai baseline, G7).

### D5 — Delta rounds (R5)

- Round 1 is the ONLY full partitioned pass. Every round ≥ 2 is a DELTA round: its surface is the previous round's fix diff plus its callers and callees (one hop, by symbol), plus any sibling commit that landed on the original surface since the last round.
- The same partition rule applies to the delta: risky hunks → Opus, the rest → Sonnet, grep classes → the script (or one Haiku seat if a brief-named class is not scriptable).
- A fix that creates a new defect is CONFIRMED in the next delta round and fixed; the loop continues until a delta round confirms zero. The class ledger persists across rounds; a delta round sweeps the classes its diff touches and CITES the classes it did not touch as standing-clean from the last full pass (the receipt says which).
- A round is never a re-scope: the brief for a delta round is the fixed class ledger applied to the delta surface.

### D6 — The critic step and the consensus rule (R2, R8)

- The orchestrator holds the critic role: for every candidate a seat raises with a concrete failure scenario, the orchestrator EXECUTES it (probe, failing test, or mutation on a pinned copy) before it becomes CONFIRMED, and executes the refutation before it becomes REFUTED. Disagreement is evidence-grounded (G3, G4): a refutation cites the executed command and its output in the receipt row.
- A candidate raised by one seat and not reproduced by the orchestrator is RECORDED, never counted (R8). It is not silently dropped: the receipt row carries `RECORDED — unexecuted: <why>`; the "suspected-but-not-reproduced" channel the reproduce-before-report literature names (G2) is this row.
- The Opus authoritative re-read of every file is retired; the Opus seat reviews only its risky slices. The safety net for a Sonnet slice's blind spot is the executed adjudication, not a second reader.

### D7 — Contract and gate changes (R9)

- Receipt Pass Ledger row: `| Pass N | <finders> | found: F, confirmed: C, fixed: X | <method> |` — `confirmed:` sits between `found:` and `fixed:`; the row parser accepts both the new triple and the old pair.
- `check_review_coverage.py` exit rule: if the final ledger row carries `confirmed:`, quiet = `confirmed: 0` (and `fixed: 0` in that round); if it carries no `confirmed:` (an in-flight receipt written under the old grammar), the old rule stands — `found: 0`. The D-048 clause in the error text is replaced by the D-203 clause. `check_convergence.py`'s QUIET_PASS test reads the same grammar.
- `command_run.py round` gains `--confirmed <n>` (default: None = not stated). The TERMINAL verdict fires when the round swept classes (`swept` non-empty), no class is open, and `confirmed == 0`; a record whose rounds never state `confirmed` keeps the old `findings == 0` test. The oscillation advisory reads the `confirmed` series when present, the `findings` series otherwise.
- The seats-declared grader and the unstamped-seat nudge are unchanged.
- Both commands' text, the subagents fragment, core/62 § dispatch policy and the CLAUDE.md fan-out bullet carry the partition rule and the new exit; the D-191 sentence ("one Sonnet breadth seat AND one Haiku mechanical seat per unit, plus the Opus authoritative seat over everything") is replaced everywhere it renders — grep the corpus, never a count.

### D8 — The seat-brief template carries the D-191 review's lessons (R10)

Every finder brief the two commands emit states: pin dirs are created ONCE before the first dispatch and never touched while seats run; `git init` inside a `git archive` pin (a bare pin fails one dispatch_headroom test through `_repo_root()`); every `command_run.py` probe sets `COMMAND_RUN_DIR`, `COMMAND_RUN_TRANSCRIPT` and `KAIZEN_EVENTS_DIR` (F349: tests wrote fabricated rounds under the live sid until the conftest pin); every mutation is applied, tested and restored inside ONE Bash call with an asserted restore (a `trap` across calls is unreliable); never bare-grep a tracked path (`git show <sha>:<path>`); Python `time.sleep` in fixture scripts, never a foreground shell sleep; HARD TIME BOX 15 minutes; report `MACHINERY:` last.

### D9 — First application (R11)

The D-191 receipt (`docs/development/reviews/2026-09-08-box-bound-seats-d191-review.md`, BLOCKED at round 18 with 0 confirmed defects and 11 raw candidates) flips to CONVERGED at round 18 in the commit that ships D7, with its Pass Ledger row rewritten to the new grammar (`found: 11, confirmed: 0, fixed: 3`) and its `## BLOCKED: spec contradiction` section closed by a one-line pointer to D-203 and this spec.

## Chosen approach (and why it is the lean one)

One model per slice, execution as the critic, delta rounds — the "reviewer + critic, three agents beat five" shape (G3) with the reproduce-before-report gate (G2) held by the orchestrator, diff-based re-review after a fix (G6), and hard resource ceilings per seat (G8). It is the leanest of the three approaches below because it changes text in two commands, one fragment, one rule pack, one contract paragraph, two gate constants and two script arguments, adds one script, and retires two overlapping seat kinds; it adds no dependency and no new mechanism beyond a counter.

Scored against the owner's five criteria: quality first — the executed-critic rule is stricter than today's argued refutations; total cost of ownership — seat spend per round drops to roughly a third and rounds after the first to minutes; speed to ship — corpus render plus the post-commit sync; easy to maintain — one grammar, one counter; set and forget — the hygiene script replaces recurring Haiku seats.

The six reality-challenges: nothing paid where free exists (native seats only); nothing complex where simple exists (a counter and a partition, no new orchestration layer); consume before build (the existing `dispatch_headroom.py`, `command_run.py` and gate grammars are extended, not replaced); low maintenance (fewer seats, one script); compatible with Fabrik infra (fleet-synced surfaces change together, render → `--check` → commit); no duplicate — no existing project or service is a review engine.

## Rejected alternatives

| Alternative | Why rejected |
|---|---|
| Keep D-048's rule and add a round cap (3 interactive, per G5) | The operator ruled the quiet-round exit stays and refuted candidates do not count (R1, R2, R6); a cap alone leaves the counting defect and ends reviews by fiat |
| Keep the overlapping seats (Sonnet + Haiku per unit + Opus over all) and only change the counter | The operator called the overlap wasteful (R3); the measured marginal gain of an extra reader falls monotonically (G4) and the D-191 Haiku seats confirmed nothing in rounds 15–18 |
| A one-pass automated fix then escalate to a human (the agentpatterns loop, G1) | That pattern's fixer is a coding agent editing a human's PR; ours is the orchestrator fixing confirmed defects with red-first graders, and the operator ruled a fix's residue must be fixed (R5). Adopted from it: the verification gate and "escalate rather than loop" as the NON-CONVERGENCE exit |
| Majority vote across seats (a finding must be raised by two passes, G5) | Under partition no two seats read the same file, so a vote is impossible by construction; execution by the orchestrator (R8) is the stronger filter and needs no redundancy |
| Full re-sweep after every fix (today) | Fix residue is real but local; the delta round covers the fix plus callers (G6) at a tenth of the cost; the class ledger persists so nothing is re-scoped |
| A new "review orchestrator" service or a second script driving the loop | Over-engineering: the loop already lives in the command text and the run record; the delta is text, a counter and a partition |
| Drop the Haiku tier entirely | The operator ruled all four models are used where they pay (R4); grep-shaped classes are Haiku's lane in round 1 and a script's thereafter |
| Keep argued refutations (a seat's reasoning suffices) | Ten reviewers unanimously endorsed a non-existent bug until one empirical test killed it (G2b); refutation must be executed |

What is DROPPED, stated (I12): the automatic second look at a file by a second reader. In 18 rounds the second reader added no confirmed defect the executed adjudication would have missed; the delta accepts that loss in exchange for executed refutations and delta rounds. The operator was told this before ruling.

## Contract deltas

- **Receipt grammar** (`docs/development/reviews/*.md`, fleet-wide): Pass Ledger rows carry `found: F, confirmed: C, fixed: X`; the Coverage Checklist and disposition rows gain the verdict `RECORDED — unexecuted: <why>` for unreproduced candidates. Old rows keep parsing.
- **Run record** (`~/.claude/state/command-runs/*.json`): a round dict gains `confirmed` (int or absent); the round event gains `confirmed`.
- **`dispatch_headroom.py` CLI**: `--slices opus=N,sonnet=N,haiku=N`; `--json` gains `slices` and `mix_by_slice`.
- **Command text**: `/fabrik-review` Phase 1 (partition), Phase 2 (execute every candidate), Phase 4 (delta round; quiet = confirmed 0); `/fabrik-repo-review` Phase 1 (waves become slices; a wave's reservation close stays), Phase 4 (delta rounds; the certification pass is the class-ledger close); the subagents fragment; core/62 § Dispatch policy; the CLAUDE.md fan-out bullet and § COMMAND RUN-RECORD paragraph; `templates/governance/CLAUDE.md` mirror of both.
- No data contract, UI contract or `shape:` change — internal machinery.

## Cost

- Build: ~8 files of text, two scripts (`command_run.py`, `dispatch_headroom.py`) with small argument additions, two gates (`check_review_coverage.py`, `check_convergence.py`) with a grammar extension, one new script (`check_review_hygiene.py`), ~12 red-first tests. Roughly one plan of five tickets; `Profile: small` per D-169 is plausible for the plan and the plan decides.
- Run: per review, seats per round fall from 10–11 to ~5–9 in round 1 and 2–4 in delta rounds; on the D-191 surface the modelled total is ~9 rounds × ~4 average seats against 18 × 10 — roughly a third of the seat spend and under half the wall-clock. Measured after the first three reviews under the new rules (Lifecycle).

## Validation

| V# | Behaviour | Proof |
|---|---|---|
| V1 | A closing round with `confirmed: 0` and a swept class ledger reads quiet; `found: 11` on that row does not fail the gate | `check_review_coverage.py` test: red-first on the D-191 receipt's round-18 row |
| V2 | A ledger without `confirmed:` keeps the old `found: 0` rule | test: an old-grammar receipt with a non-quiet last row still fails; a quiet one passes |
| V3 | `round --confirmed 0 --classes-swept <all>` prints TERMINAL; `round --confirmed 0` with no classes does not; `round --findings 0` with no `confirmed` on any round keeps the old test | `tests/test_command_run.py`, red on revert of each clause |
| V4 | `dispatch_headroom.py --slices opus=1,sonnet=4,haiku=2` prints SEATS 7 on an idle box, trims Haiku first under a cap, never below one Opus | `tests/sysadmin/test_dispatch_headroom.py` |
| V5 | A RECORDED — unexecuted code candidate in the closing round makes the receipt not quiet | gate test: red-first |
| V6 | The hygiene script reproduces the D-191 review's Haiku findings on the receipt at 741eebbf (F280's raw pipe, F314's dual verdict) and is silent on the receipt at 69f01b92 | `tests/enforcement/test_check_review_hygiene.py` |
| V7 | The rendered corpus carries no "one Sonnet breadth seat AND one Haiku mechanical seat" sentence and every fan-out command carries the partition step | `tests/test_assemble_dispatch_step.py` extension; `grep -c` over 36 rendered commands = 0 |
| V8 | A delta round's brief names the fix diff + callers and cites the standing-clean classes | command text test (the fragment's delta-round sentence survives a render) |
| V9 | First application: the D-191 receipt flips to CONVERGED and `check_review_coverage.py` is OK on it | the commit that ships D7 |
| V10 | Fire rate: the hygiene script advisory on the first 20 receipts, false-positive rate measured before it errors | the feedback ledger + a backlog row until measured |

## Decisions taken

Operator rulings received 2026-09-08 (recorded as D-203 by the sibling session; each restated here so the spec carries them all — I10):

| R# | Ruling (operator's words or the agreed restatement) | Applied at |
|---|---|---|
| R1 | "exit only quite round should stay" — a quiet round is REDEFINED as a round whose partitioned pass confirms zero code or doc defects | D1 |
| R2 | "A refuted candidate counts as a fresh finding: this is wrong, it is definetly not" — RECORDED and REFUTED never reopen the loop; CONFIRMED means executed; D-048 superseded | D1, D6 |
| R3 | "dividing tasks amongst the agents according to their type, and in a single pass, they make a combined full pass. the way we do currently is wasteful" — one partitioned pass, disjoint slices, one model per slice; D-191's seat mix superseded | D2, D3 |
| R4 | "we have fable, opus, sonnet, haiku, all agents must be used efficiently and wisely not wastefully" — each model where it pays; after round 1 a model sweeps only its changed slice; Haiku's classes become a script | D2, D4 |
| R5 | "if you create new errors, they must be definetely fixed … we can review only the fix without making ful pass" — delta rounds over the fix diff plus callers | D5 |
| R6 | No round cap; the NON-CONVERGENCE escalation stays as the only other exit | D1 |
| R7 | The seat budget still runs through `dispatch_headroom.py`, sized by slices; the 15-minute box and budget → stamp → dispatch stay | D3 |
| R8 | A candidate raised by one seat and not reproduced by the orchestrator is RECORDED, never counted | D6 |
| R9 | `confirmed:` on the ledger row, `--confirmed` on `round`, TERMINAL on confirmed == 0 with a class-ledger close, backward compatibility for in-flight receipts | D7 |
| R10 | The seat-brief template carries the D-191 review's lessons | D8 |
| R11 | The BLOCKED D-191 receipt flips to CONVERGED under the new rule once this ships | D9 |

Design decisions this spec makes under those rulings (each reversible; override by re-freeze):

| DD# | Decision | Why |
|---|---|---|
| DD1 | "Executed" = a probe on a pinned copy, a failing test, or a mutation on a copy; an unexecutable candidate is `RECORDED — unexecuted` and a closing round carrying one for a code claim is not quiet | closes the relabelling loophole the operator was warned of |
| DD2 | The floor under partition: one seat per non-empty slice kind; a surface without a risky unit still gets one Opus seat over its most consequential slice; D-186/D-188's three-different-angles rule stays only for grounding and adjudication surfaces | the third angle in a review is the orchestrator's execution |
| DD3 | The delta surface = fix diff + one hop of callers/callees by symbol + sibling commits on the original surface since the last round | one hop is where fix residue lived in rounds 14–17; deeper hops re-create the full pass |
| DD4 | `found:` stays (recall), `confirmed:` is added (the exit), `fixed:` stays; old rows parse; the gate branches on the presence of `confirmed:` | in-flight receipts in ~46 projects must not break on sync day |
| DD5 | `dispatch_headroom.py` gains `--slices` and keeps `--units` for the commands that size by units | spec and plan grounding are judgement surfaces; their D-186/D-188 floor stays |
| DD6 | The hygiene script starts advisory and graduates on a measured false-positive rate below 5 % over 20 receipts | a detector that fires on legitimate patterns is wallpaper (CLAUDE.md § FIX DIRECTIVE 5) |
| DD7 | The Opus seat's scope is a fixed list (concurrency, locks, record/file formats, fleet-synced paths, auth, schema, migrations, secrets); the orchestrator may add a unit to it with the reason in the brief | a list beats a judgement call under time pressure |
| DD8 | The oscillation advisory reads the `confirmed` series when present; `PER_UNIT_ROUND_COMMANDS` is unchanged | per-slice counts of a delta round are what convergence looks like |
| DD9 | `check_convergence.py` QUIET_PASS follows the same grammar (D-203 names it) | one definition of quiet across the gates |

## Lifecycle

- **Adoption:** ships as one plan; the corpus renders from the main checkout; the post-commit governance sync distributes the gates and `command_run.py`; the D-191 receipt is the first flip (D9). Reviews in flight in project repos keep their old grammar until their next round writes a `confirmed:` row.
- **Growth:** the hygiene script's class list grows by brief-named classes that repeat in two reviews (the feedback ledger's `change:` field is the source); the partition's risky list (DD7) grows by D-row. Trigger to revisit: three reviews in a row where a delta round confirms a defect outside the one-hop surface — then DD3 widens to two hops.
- **Degradation:** if Fable refuses, Opus adjudicates by name (recorded); if the box cap trims below one seat per slice kind, the orchestrator serialises slices across messages under one round (the stamp accumulates, the reservation clock is per message); if execution of a candidate is impossible on a pinned copy (a race, a live-only path), it is `RECORDED — unexecuted` and named in the residual section.
- **Retirement:** superseded by a new D-row; the old grammar keeps parsing for the receipts written under it.

## Grounding (external facts and the approach floor — fetched 2026-09-08 by four native `fabrik-researcher` seats, one Opus; raw-arm fetches, verbatim quotes)

| G# | Source | Fetched | What it grounds |
|---|---|---|---|
| G1 | https://agentpatterns.ai/code-review/review-then-implement-loop/ | 2026-09-08 | "Cap automated fix attempts at one pass. If the coding agent's fix does not resolve the finding cleanly (tests fail, or new issues appear), escalate to human review rather than looping." — adopted as the NON-CONVERGENCE exit, not as a cap (R5/R6); acceptance floor "adopted at 16.6% versus 56.5% for humans" |
| G2 | https://agentpatterns.ai/code-review/reproduce-before-report-verification-gate/ | 2026-09-08 | "A reproduce-before-report verification gate drops any reviewer finding the verifier cannot reproduce against actual code behavior." · "A pipeline that fans out reviewers but reports every candidate is fan-out: it amplifies false positives instead of filtering them." · the suspected-but-not-reproduced channel → `RECORDED — unexecuted` |
| G2b | https://arxiv.org/abs/2604.19049 (Refute-or-Promote) | 2026-09-08 | "the pipeline killed ∼79% of ∼171 candidates before advancing to disclosure"; "ten dedicated reviewers unanimously endorsed a non-existent Bleichenbacher padding oracle in OpenSSL's CMS module; it was killed only by a single empirical test, motivating the mandatory empirical gate." → DD1 |
| G3 | https://arxiv.org/abs/2608.18167 (Adversarial Review) | 2026-09-08 | "outperforming a five-agent baseline while using only three agents"; "it requires that disagreement be minimal, structured, and evidence-grounded" → D6 |
| G3b | https://agentpatterns.ai/code-review/evidence-grounded-disagreement/ | 2026-09-08 | naive reviewer pair F1 0.457 below a single reviewer 0.495; grounded pair 0.533 — "only requiring every objection to cite code makes the second reviewer worth it" → refutations cite the executed command |
| G4 | https://arxiv.org/abs/2511.16708 (+ html body) | 2026-09-08 | "diminishing returns of +14.9pp, +13.5pp, and +11.2pp for agents 2, 3, and 4"; "Security detects 87.5% of security bugs but only 4.2% overall" (overall TPR) → retire the overlapping reader |
| G5 | https://zylos.ai/research/2026-03-01-multi-model-ai-code-review-convergence/ | 2026-09-08 | "hard caps of 1-2 loops for automated CI/CD, with 3-5 rounds for interactive review sessions" (not adopted — R6); "issues flagged in only one pass are discarded as noise"; "A good tool achieves >60% signal ratio; a great tool >80%."; "Dual-threshold circuit breakers" |
| G6 | https://mastra.ai/articles/ai-code-review-tools | 2026-09-08 | "then reviews each later commit with an incremental pass focused on the update." → D5; agentpatterns "Diff-Based Review": "Review what changed, not the full output — mistakes live in the delta" |
| G7 | https://www.codeant.ai/blogs/ai-code-review-false-positives | 2026-09-08 | "For most teams, <10% should be your baseline 'acceptable' threshold. For high-throughput organizations, <5% is the optimal target." → DD6's 5 % bar. (An earlier draft of this session cited 10–30 % bands and a SonarSource 3.2 % figure from this page; the live page carries neither — corrected by the seat.) |
| G8 | https://blog.cloudflare.com/ai-code-review/ | 2026-09-08 | "Instead of asking one model to review everything, we split the review into domain-specific agents." · top tier "Reserved exclusively for the Review Coordinator", standard tier "the workhorse for our heavy-lifting sub-reviewers", a light model "for lightweight, text-heavy tasks" · "If the coordinator isn't sure, it uses its tools to read the source code and verify." → D2's model-by-slice partition and D6 |
| G9 | https://javascript.plainenglish.io/dont-let-your-ai-agents-loop-forever-an-engineering-guide-to-termination-criteria-c09d8d68f871 | 2026-09-08 | "Enforce hard ceilings across three independent dimensions: turns, tokens, and wall-clock time" → the 15-minute seat box and the reservation clock stay per seat, not per review |

Search leg (real search, `WebSearch`, 2026-09-08): the Opus seat's query surfaced https://arxiv.org/html/2607.06065 (SWE-Review), https://arxiv.org/html/2607.24604v1 ("Looping Is Not Reliability"), and the Cloudflare/mastra/projectdiscovery pages the fourth seat opened; ≥2 distinct URLs from ≥2 tools with at least one via search — the 1c floor is met. Behaviours R1–R11 are ruled (D-203) and grounded by their row, per D-153; the literature above grounds HOW they are built.

## fabrik-lib verdict

One line: nothing to vendor — the surfaces are hub scripts and the command corpus; no fabrik-lib module covers review orchestration, and this delta is not a fabrik-lib candidate (hub-specific machinery, not generic).

## Constraints digest

| Pack | Rule (verbatim) | Anchor | Applies to |
|---|---|---|---|
| core/62 | "The loop-closing round's **FINDER pass** runs in a context that did **not author the artifact**" | `.windsurf/rules/core/62-using-subagents.md:184-186` | D2/D5: delta-round seats are fresh dispatches; the orchestrator adjudicates, never hunts last |
| core/62 | "**Adjudication — decide/refute/merge — stays with the orchestrator**" | `:192-193` | D6 |
| core/62 | "Gating a review's trust on a specific pool model name instead of the methodology (native-Opus authority + refutation)." (Banned) | `:262` | D2 names roles by kind; trust rests on executed refutation |
| core/62 | "every fan-out a command names runs NATIVE (Runtime A)" | `:65` | all seats native; the pool stays OFF (D-181/D-182) |
| core/40 | "**No commented-out content blocks** — dead text confuses AI and pollutes diffs" | `.windsurf/rules/core/40-documentation.md:245` | the retired D-191 sentence is replaced, not commented out (the POOL-OFF comments are the sanctioned exception) |
| core/40 | "**Keep tables simple and atomic** — no multiline cells" | `:244` | the new ledger row grammar stays one line |
| core/10 | "**`uv`** is the mandated Python package manager." | `.windsurf/rules/core/10-python.md:21` | no new dependency; nothing to install |
| core/58 | "every external call has timeout + retry with backoff" | `.windsurf/rules/core/58-resilience.md:87` | seats keep the 15-minute box; the reservation clock bounds a hung seat |
| FLOOR 35 / 25 / 30 | glob-scoped to auth, DB and Docker paths | headers | no row applies: the delta touches no auth, schema or compose surface — read, none applicable |

## Shape / infra implications

One line: none — hub machinery, no `specs/services/*.yaml`, no `shape:` flag, no deploy.

## Documentation landing sites

- `docs/reference/command-run-protocol.md` — the `round --confirmed` row and the TERMINAL rule.
- `docs/workstation/quota-dashboard.md` § The box-budget banner — the slice mix `dispatch_headroom.py` prints.
- `docs/reference/convergence-prompts.md` — the delta-round brief and the executed-refutation row shape.
- `docs/DECISIONS.md` — D-203 (ruling), the supersede rows for D-048, D-191 and the D-186/D-188 review floor at approval.
- `CHANGELOG.md` — one entry per ticket; `INDEX.md` — the new script and its test; `docs/STRATEGIC_BACKLOG.md` — the hygiene script's fire-rate row until measured.
- The two commands, the fragment, core/62 and both CLAUDE.md files self-document the rule.

## Open / blocking unknowns

- Resolved: whether a refuted candidate counts (R2, D-203); whether the exit stays a quiet round (R1); the partition and the delta rule (R3–R5).
- Open, with a resolution step: the hygiene script's false-positive rate on real receipts — measured advisory over the first 20 receipts (DD6, V10) before it may error. The modelled "closes around round 9 at a third of the spend" is a projection from the D-191 series; the first three reviews under the new rules measure it (Lifecycle).

## Machinery report

Wall-clock at DRAFT hand-over: recorded in the run record; four grounding seats (1 Opus, 3 Sonnet), three quoted facts corrected against the live pages by the seats. Friction with the D-153 text: none; the delta profile's collapsed sections held.
