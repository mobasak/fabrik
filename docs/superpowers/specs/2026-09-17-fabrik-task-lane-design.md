# `/fabrik-task` — the lane between a right-now fix and the spec chain

**Status:** DRAFT
**Review:** `/fabrik-spec-review` 2026-09-17 — pass 1 (6 seats: 52 findings, 31 confirmed, own-fix 0) applied as 41 edits; pass 2 (3 fresh seats) confirmed 22 defects, ALL inside those edits (own-fix 22 of 22), several restating pass-1 findings with a wrong grounding attached. The D-278 scope-growth exit was taken: no third rewrite. The residue is **U6–U27** under § Open unknowns, each with its named resolution; three are the operator's forks (U8, U10, U19). **NOT CONVERGED** — the build must not start on this text.
**Profile:** full section set. `Profile: delta`'s trigger — *every Intake Inventory item maps to code that exists today* — fails: `/fabrik-task` is a NEW command with no source file behind it, and two of its three code changes add behaviour (`command_run.py start` gains a declaration, the router gains a stem). Verdict stated per the profile rule.
**Owner:** infra (this hub window). **Date:** 2026-09-17.
**Emitted by:** `/fabrik-spec`, seeded by a `superpowers:brainstorming` run (architectural path) in the same session.

## Personas

**Primary — the agent about to do a small-but-real change, in the operator's words** (and the holder of the UPGRADE duty: it materialises the seed and calls `handoff`; phase 4's seats may *recommend* an upgrade, the primary *takes* it): *"be 100% sure about your design as you will be the consumer."* The consumer is the running agent — in the hub and in the ~46 project repos where the command renders — holding a change that carries one decision and needs "our way of working and structure" without the spec chain.

**The primary's minimal loop, counted — this is the frozen STEP BUDGET (6):**
0. **SIZE** — declare the surface; two tests execute, three are answered; proceed or be refused with the lane named.
1. **MEASURE** — reproduce and attribute; `select_rules.py` over the surface; the terminal condition stated at `start`.
2. **DESIGN** — the six fields into the run record (≤ ~1,200 chars): PROBLEM · APPROACH · DECISION (reversible?) · MIRROR · OUT · TERMINAL.
3. **BUILD** — the change plus its grader, red-first; plan-lock check on the declared paths first.
4. **REVIEW** — `/fabrik-review-scoped`, unchanged, its seats handed the design fields as part of the surface.
5. **CLOSE** — the commit is re-measured against step 0's declaration; D-row if DECISION was one; CHANGELOG; commit + push; FEEDBACK.

A downstream contract that adds a seventh step forces a budget bump and says why.

**Other personas, each holding a named duty:**
- **The operator** — reads the D-row (the lane's only durable design artifact), the FEEDBACK line, and the three success metrics; is offered the lane choice in the NEXT line of any run that could take either lane.
- **The Stop hook** (`.claude/hooks/final_gate_stop.py`, automated) — already reads the record's `state` and `surface` (`:996-1010`); a `/fabrik-task` record is a review-family-adjacent record it blocks on while `running`. It gains no new duty.
- **`skill_router.py`** (automated, fleet-synced) — routes bare prose to `/fabrik-task` at Tier 1; owes a `STEM_SKILLS` entry and a `KEYWORD_STEMS` row, both bilingual, intent-anchored so a bare "task" never fires on ordinary prose.
- **`command_run.py`** (automated, fleet-synced) — persists the phase-0 declaration at `start`, refuses a start that fails a mechanical test, and re-measures at `done`, writing the result into the feedback row.
- **The kaizen collector** (automated) — reads the new row fields as series: `oversized_mini`, `salami_suspect`, `upgrade`, and the three `*_missed` flags; no change to its code is owed by this spec (the fields ride the existing feedback row).
- **Sibling sessions** (automated) — subtract `/fabrik-task`'s dispatch stamps exactly as for any command; nothing new.
- **`/fabrik-review-scoped`'s seats** — receive the design fields in their brief and are asked whether the change fits the declared size; the command itself is invoked unchanged.
- **The project agent in ~46 repos** — receives the three-lane decision rule through `templates/governance/CLAUDE.md` § Orient step 0 (a sync trigger) and the rendered command box-wide.

Every feature below traces to one of these; a mechanism with no persona here is cut.

## Intake Inventory

| I# | Item (anchored to the operator's words) | Disposition | Where |
|---|---|---|---|
| I1 | *"some tasks does not require full spec/specreview/plan/planreview/execute/fabrikreview/scopedreview"* | IN | § Why this exists; § Chosen approach ("What the chain's stages become") |
| I2 | *"but they still need our way of working and structure"* | IN | § Chosen approach — sequence-not-restate; every gate kept |
| I3 | *"a type of mini all combined command or?"* | IN | § Chosen approach — one command, one record |
| I4 | *"and how to decide what to do"* | IN | § The decision rule |
| I5 | *"it must retain all constraints, functions of our worklow"* | IN | § Constraints C1; § Chosen approach |
| I6 | *"agents can be easily decide what workflow to be selected"* | IN | § The decision rule; § Awareness |
| I7 | *"it should be lean"* | IN | § Constraints C2 (byte budget) |
| I8 | *"effective"* | IN | § Validation — the three metrics and thresholds |
| I9 | *"manifesto, infra, rules aware"* | IN | § Constraints C3–C5 |
| I10 | *"be sure agents will aware of it can easily decide in between offering a fabrik-spec workflow or fabrik-task workflow"* | IN | § Awareness (two surfaces); § The decision rule |
| I11 | *"be 100% sure about your design as you will be the consumer"* | IN | § Validation — dogfood |
| I12 | *"you can use several subagents to test it if you want"* | IN | § Validation — backtest and cobra probe |
| I13 | *"what will /fabrik-task do? compact of all spec/specreview/plan/planreview/execute/fabrikreview/scopedreview?"* | IN | § Chosen approach — "What the chain's stages become" |
| I14 | *"spec takes hours"* (the sizing question earlier in the session) | IN | § Why this exists — measured |
| I15 | *"i face this issue a lot in all repos, so we need a permanent and well working mechanism"* | IN | § Awareness — the rule lands in the template contract too; § Lifecycle |
| I16 | D-row versus a mini-spec file as the durable artifact — the fork I put to the operator; answered with *"yes task looks fine"* | IN | § Chosen approach — D-row; § Rejected alternatives R3 |
| I17 | The adjacent-damage checker (reading A of the brainstorm: an edit silently damages neighbouring text and every gate stays green) | OUT-OF-SCOPE | A separate mechanism, not a lane. Destination that exists: the `change:` verdict filed against `/fabrik-review-scoped` at its close in this session (feedback ledger, ts 1789669428 — `round(ts)` — "a fix REPLACING a whole long line asserts the neighbouring lines' opening clauses survive it") — it will be read by that command's next `/fabrik-command-improve` run. |

## Goal

Add one command, `/fabrik-task`, that carries a small change with one reversible decision from "I have a change" to "committed, pushed, reviewed, recorded" in one run record, keeping every gate and decision the spec chain makes and dropping only its intermediate artifacts and their separate reviews — and give every agent a decision rule it can apply **before drafting** to choose between three lanes.

## Why this exists

**The cost, measured from `~/.claude/state/command-feedback.jsonl` on 2026-09-17** (re-derive before citing; the ledger is live):

| lane | runs | median per run | total |
|---|---|---|---|
| `fabrik-spec` · `fabrik-spec-review` · `fabrik-plan-after-chat` · `fabrik-plan-review` | 65 | 85 min | 158 h |
| `fabrik-execute-plan` | 30 | 259 min | 210 h |
| `fabrik-review-scoped` + `fabrik-command-improve` (the light lane) | 78 | 32 min | 50 h |

A full chain is ~6 hours before a line is written, ~10 with execution. The light lane is 32 minutes. **There is nothing between them.** So an agent holding a change with one real decision either pays the chain or skips design.

**Both failure directions, executed in one session (2026-09-17):** the same one-paragraph edit to `commands/_sources/fabrik-review-scoped.md` was attempted three times as an elaborated mechanism — 3 review rounds, 35 findings, 22 confirmed, confirmed/own-fix 10/0 → 6/6 → 6/6 firing the D-278 stop, the third cut regressing the rendered corpus — and all three reverted; then once correctly sized: 130 B, converged on pass 2 with 1 confirmed defect (commit 02df9b74f, D-288; the round series is the review's own close row, feedback ledger ts 1789671545, `rounds 2 (0→0)`). The difference was not care; it was WHEN the sizing test was applied. The contract's existing test (CLAUDE.md § Behavior, the mail SIZING step, D-097) is sound and was applied to the *draft* — which, once elaborated, genuinely was a mechanism.

**The asymmetry that decides the default:** over-sizing costs ~6 hours before any code; under-sizing costs one ~30-minute review, with the review as the backstop. Those are not symmetric risks. The lane exists to make the cheap direction the default without making it the *unreviewed* direction.

## What exists today (grounded)

- **The sizing test** — CLAUDE.md § Behavior, mail HANDLE-NOW clause: *"a validated request is either SPEC/PLAN work (a new mechanism, a vendored/synced surface, schema, auth, >5 files) … or a RIGHT-NOW fix"* (D-097, 2026-09-03; extended fleet-wide by D-098 with a third outcome for project agents: file upstream). It names no moment and no object to apply itself to.
- **`Profile: small`** (D-169, 2026-09-06) — an EXECUTION profile: plans ≤ ~400 lines / ≤ 5 files run inline with `/fabrik-review-scoped` per phase and one heavy round. It still costs spec + spec-review upstream. It is unchanged by this spec and stays the execution profile inside the chain.
- **The run record** — `scripts/command_run.py`: `start` already takes `--surface` and persists it (`:2643`, `"surface": (args.surface or "").strip()`); the Stop hook reads that field for review-family records (`.claude/hooks/final_gate_stop.py:996-1010`). `_close` (`:3121`) owns `done`/`blocked` and writes the feedback row with `wall_s` and `rounds` (`:3662`, `:3663`). `handoff` exists as a sanctioned close. **No new verb is required**: phase 0 is an extension of `start`, the re-measure lives in `_close`, UPGRADE is `handoff`.
- **The router** — `.claude/hooks/skill_router.py`: Tier 1 is `STEM_SKILLS` (stem → skill, `:105-`) plus `KEYWORD_STEMS` (bilingual regex → stem, `:264-`; the comment block describing it starts at `:175`); *"a stem here with no KEYWORD_STEMS row never matches; a row there with no entry here resolves to None"*. Tier 2 (Haiku) is off unless `FABRIK_ROUTER_HAIKU=1`. So awareness at the router **requires both rows**, and the file is a governance-sync trigger.
- **The sync trigger set** — `.pre-commit-config.yaml:155`, the `governance-sync` hook's `files:` regex; `scripts/governance_sync_postcommit.sh` re-reads it. `commands/_sources/` is NOT in it (tested); `scripts/command_run.py`, `.claude/hooks/`, `templates/governance/` ARE.
- **The review the lane invokes** — `/fabrik-review-scoped` (`commands/_sources/fabrik-review-scoped.md`, 18,654 B): units-sized, floor 3 readers at round 1, closes on a delta pass confirming zero. Invoked unchanged.
- **The manifesto's triage** — `docs/reference/operating-manifesto.md:10-14`: *Reversible (cheap to undo, contained blast radius) → skip to Phase 4 … One-way (structural, public, expensive or impossible to unwind) → run the full loop. Rigor scales with irreversibility.* A ONE-WAY decision grows its D-row with the Binding block (`:102-106`).
- **The cobra rule** — D-253 / CLAUDE.md FIX DIRECTIVE 5: every gate or counter introduced writes down its cheapest bypass in the same change.
- **A rejected mechanism that binds this design** — D-097 REJECTED a new enforcement check for mail triage: *"fire rate unmeasured and the Stop hook already blocks record-less code edits (FIX DIRECTIVE 5)"*. The SIZE gate must therefore be a refusal inside the agent's own tool on the agent's own declaration — the shape `done --feedback` already has — never a gate over others' work.
- **The feedback ledger and the kaizen loop** — every close writes `wall_s`, `rounds`, the four verdict fields (D-175); `command_feedback_report.py --queue` and `/fabrik-command-improve` consume them (D-234). A new field on the row is read by the collector with no code change.
- **Where commands are documented** — `docs/CAPABILITIES.md:387` (one bullet per command), `docs/reference/command-run-protocol.md` (the record contract; names `--surface` at `:208`, `:221`, `:224`), `INDEX.md`.
- **What a "small change" is, measured** — over the last 300 hub commits, excluding the four shared-append files CLAUDE.md § Behavior names (`CHANGELOG.md`, `docs/DECISIONS.md`, `docs/STRATEGIC_BACKLOG.md`, `INDEX.md`) plus `docs/LESSONS_LEARNT.md`, which this session appends the same way: 69% touch ≤3 non-ledger files, 81% ≤4, 87% ≤5 (68/80/86 with only the canonical four). "≤3" is the two-thirds line, not a round number.

## Chosen approach

**One command, one run record, the D-row as the durable artifact. It SEQUENCES existing mechanisms and RESTATES none.** The command's source is glue between four things that already exist as fragments or contract text — the run record, the FIX DIRECTIVE, `/fabrik-review-scoped`, the close-out feedback — and it adds exactly two new things: the SIZE gate and the DESIGN-in-the-record step.

**Phase 0 — SIZE.** `command_run.py start --command fabrik-task --surface "<the subject, one phrase>" --declare files=<a:b:c>,mechanism=<yes|no>,oneway=<yes|no>,tradeoffs=<yes|no>` then:
- **executes** two tests: `files` count ≤ 3, and every declared path against the governance-sync regex read from `.pre-commit-config.yaml` (the same regex `governance_sync_postcommit.sh` reads; never a copy);
- **records** the three declared answers — they are exactly the decision rule's three non-executable tests (mechanism, ONE-WAY, trade-offs) — and a `yes` to any of them is a refusal;
- on any failure **REFUSES the start and NAMES the lane** (`REFUSED — fabrik-task: <test> → <lane>`; a sync hit names the heavy-surface rule, the others name `/fabrik-spec`), and on success persists `declared: {files, mechanism, oneway, tradeoffs, sha}` in the record, where `sha` is `git rev-parse HEAD` at start. `--surface` keeps its ledger meaning (what the run is OVER — one phrase); the path list lives in `--declare`, because `_close` must parse it (U1) and because a unique path list in `--surface` would corrupt the column `command_feedback_report.py:941-950` groups by.
**The moment.** Command text cannot observe what an agent thought before typing. What the record CAN observe is order within a turn: the event stream is order-faithful (`command_run.py:1148`, `_queue`), so the command requires `start` to be the turn's first write-verb event and `_close` records whether it was. Across turns the moment is a discipline, stated as one; the § decision rule's tripwire is its named fallback, not its enforcement.
This is not a new enforcement check over the tree (D-097's rejected shape); it is the command's own tool refusing an under-specified start, exactly as `done` refuses without `--feedback`. It has a fire rate all the same, and § Validation V0 measures it before the build.

**Phase 1 — MEASURE.** FIX DIRECTIVE 1 verbatim: reproduce, attribute, name the root cause. `python scripts/select_rules.py` over the declared surface; the ACTIVE packs are read. The terminal condition is already in the record from `start --terminal`.

**Phase 2 — DESIGN, drafted where it will be minted.** The six fields — PROBLEM · APPROACH · DECISION (reversible?) · MIRROR · OUT · TERMINAL — are written as the D-row's draft text into `<scratchpad>/fabrik-task/<sid>/design.md`, and the record carries only the pointer: `command_run.py step --phase 2 --title "design: <that path>"`. Two facts of `command_run.py` decide this home: `phase_title` is a single scalar overwritten by the next `step` (`:2789`), so fields put there are gone by phase 3; and `pinned_line` interpolates the title verbatim into every response's `RUN:` line (`:254-256`), so fields put there flood every turn. The draft is read by phase 4's seats from that path and minted verbatim as the D-row at phase 5. R4 stands: no new verb. MIRROR is mandatory: the contract's *"every contract change has a MIRROR — name the shape you just broke"*.

**Phase 3 — BUILD.** Plan-lock check by `owned_paths` against the declared paths first; the change and its grader, red-first; shared-append files by the private-index recipe.

**Phase 4 — REVIEW.** `/fabrik-review-scoped` invoked as the skill, unchanged. Its seat briefs carry the phase-2 draft's path and the phase-0 declaration and ask three extra questions, one per declared test: *does the change fit the declared size? did it add a mechanism the declaration said no to? can you name a second approach the declaration said did not exist?* A `yes` lands on the row as `size_missed` / `mechanism_missed` / `tradeoff_missed`, and the seat holds an UPGRADE verdict (*this change requires the heavier lane*). Spec-review is thereby folded in: the design is reviewed once, together with what it produced.

**Phase 5 — CLOSE, in this order.** D-row minted from the phase-2 draft (if DECISION was one), CHANGELOG, commit + push — **then** `done --command fabrik-task`, which re-measures the run's OWN change, never the tree: the working-tree paths this run touched (mtime ≥ `started_epoch`, the pattern `command_run.py:3243` already uses) plus the commits since `started_epoch` whose `Agent-Context` trailer names this run, against `declared.files` and the sync regex. It writes `oversized_mini: {files_over: n, sync_hit: bool}`, `salami_suspect: <prior row | none>` and `declared_files` into the feedback row. On a shared tree this is best-effort: a window a sibling's commit contaminates records `oversized_mini: unmeasurable` (fail-open, the `:3212` precedent), never a violation attributed to the wrong agent. Two shapes it must not take, written down per D-253: a diff "since `declared.sha`" is authorship-blind and would record a sibling's files as this run's; and intersecting the measured set with `declared.files` is vacuous — a test filtered to its own declaration cannot fail.

**UPGRADE — the one-way ratchet.** From phase 2 on, a size input crossing — a fourth file, a sync path, a verb that must exist, a decision that turns one-way — first materialises the seed (a `## RESUME` block naming the test crossed, appended to the phase-2 `design.md`) and then closes `command_run.py handoff --command fabrik-task --resume <that design.md> --reason "UPGRADE: <test crossed>"`; `handoff`'s `--resume` is `required=True` (`command_run.py:2469-2477`), so the artifact must exist and does. `/fabrik-spec` opens seeded with that file. At phase 0 or 1 nothing exists to hand off, so a crossing there is `start`'s own refusal. The close writes `upgrade: <test>` onto the feedback row — the row carries `state` but not `reason` (`:3508`, `:3511` write `blocked_reason` only to the record), so without the field the UPGRADE rate is unreadable. Nothing downgrades mid-run.

**What the chain's stages become:**

| chain stage | what it is for | in `/fabrik-task` |
|---|---|---|
| `/fabrik-spec` | decide problem, approach, out-of-scope, the mirror | phase 2 — the same decisions as six fields in the record |
| `/fabrik-spec-review` | author-blind check of the design | folded into phase 4 — reviewed once, with its implementation |
| `/fabrik-plan-after-chat` | steps, file scope, evidence | phase 0+1 — the declared surface and terminal ARE the plan; one phase by definition |
| `/fabrik-plan-review` | review the plan | dropped — a one-phase ≤3-file plan is reviewed by reviewing its result |
| `/fabrik-execute-plan` | build, commit, review per phase | phase 3 — one build, one commit |
| `/fabrik-review` (heavy) | partitioned finders, delta rounds | not in the lane — needing it is an UPGRADE trigger |
| `/fabrik-review-scoped` | light review to convergence | phase 4, unchanged |
| `/fabrik-docs-review` | docs truthful | folded into phase 5 via the Doc Sync Matrix |

Every DECISION and GATE is kept; the intermediate ARTIFACTS and their separate reviews are dropped.

## The decision rule

Applied to the **smallest change that discharges the ask, before drafting** — never to a draft already elaborated:

The blast-radius tests the field publishes come first; the count comes last and is admitted as a house heuristic.

1. touches a governance-sync path — a PUBLIC CONTRACT for ~46 repos? *(executable — the regex)* → **not this lane; the heavy-surface rule the contract already has applies** (CLAUDE.md § Completion Contract 1a: gate/hook/enforcement → right-now + the full `/fabrik-review`; the spec chain only if a later test also trips). Measured: 33% of the last 300 hub commits touch a sync path, so on the hub this test refuses a third of the work — into the lane that already exists for it; in the 46 project repos, where synced files are never hand-edited, it refuses almost nothing.
2. needs a new mechanism — a verb, flag, schema, hook, table, cron — a NEW ARCHITECTURAL COMPONENT? → **spec chain**
3. is the one decision ONE-WAY — structural, public, expensive to unwind? → **spec chain** (the Binding block lives there)
4. are there genuine TRADE-OFFS to adjudicate — more than one defensible approach? *(Google's test)* → **spec chain**; *no trade-offs and no decision at all — a pure fix* → **right-now + `/fabrik-review-scoped`** (exists today)
5. house heuristic, stated as one: more than 3 files? → **spec chain** (`Profile: small` then lightens execution). Grounding: 69% of the last 300 hub commits touch ≤3 non-ledger files; Google treats file count as a size multiplier and names no number; RFC 2904 says size is not the test. It is here because it is the one test the router and the operator can see before any work, never because the literature ranks it.
6. one reversible decision, statable in the six fields, ≤3 files, no sync path, no mechanism? → **`/fabrik-task`**

**Tripwire (the fallback, not the enforcement):** if the first draft cites a script's internals, re-run the tests — either real mechanism work was found or the draft over-scoped, and the verdict says which. The enforcement is phase 0's first-event rule; this catches the elaboration that happened in an earlier turn.

This table lands in CLAUDE.md § Orient step 0 and its twin `templates/governance/CLAUDE.md` — the project copy carries D-098's third outcome (a synced-surface defect files upstream) ahead of these six.

## Awareness (I6, I10)

Two surfaces, both required:
1. **The step-0 routing table** in both CLAUDE.md copies — the six tests above, in the table agents already consult.
2. **`skill_router.py`** — a `STEM_SKILLS` entry `"task": "fabrik-task"` and a bilingual `KEYWORD_STEMS` row. The row must be intent-anchored: the file's own round-2 finding retired bare high-frequency words because *"the task is …"* and *"görev"* fire on ordinary prose. Candidate anchors: EN `(small|quick|one)[- ](change|fix|task) with (a|one) decision`, `decide and (fix|change)`, `fabrik[- ]task`; TR `küçük (değişiklik|görev)\w*`, `karar\w* (ver|al)\w* ve (düzelt|değiştir)\w*`. The exact regexes are tested in `tests/test_skill_router_hook.py` against its existing collision corpus before they ship — and, since precision without recall is a dead row, against a POSITIVE corpus of ≥15 realistic small-change prompts (EN + TR) the lane exists for: the candidates above scored 0 collisions on the 35-prompt negative corpus and **0 of 8** on realistic prompts, because each requires the operator to already use the lane's vocabulary. An anchor set below 50% recall on the positive corpus is not shipped; surface 1 then stands alone and § Awareness says so. The command's own description carries a `TRIGGER` and a `SKIP` clause naming `/fabrik-spec`'s triggers, so the rendered corpus explains the choice at the point of invocation.

## Rejected alternatives

- **R1 — `Profile: mini` on `/fabrik-spec`.** Reuses the most, but still three invocations, and the profile mechanism already carries two variants. The lane's value is ONE record.
- **R2 — grow `/fabrik-review-scoped` with a design step.** Cheapest, but turns the light REVIEW pass into a build command and muddles the identity the Stop hook depends on.
- **R3 — a mini-spec FILE as the artifact.** Findable, but costs an allowlist entry, INDEX rows and gate checks; the D-row already carries what/why/where, is greppable, and is what the contract mandates for any decision. Operator chose the D-row (I16).
- **R4 — a new `size` verb in `command_run.py`.** `start --surface` already persists a surface; extending `start` with `--declare` and re-measuring in `_close` touches the same file with less new surface.
- **R5 — a new blocking enforcement check for sizing, in `scripts/enforcement/` or in the Stop hook.** D-097 rejected exactly this shape on fire rate; a Stop-hook gate is the same shape one turn later. The SIZE gate is a refusal in the agent's own tool on the agent's own declaration instead — and it still owes its fire rate (V0).
- **R6 — a per-round `--delta` threshold instead of a file count.** `--delta` exists for review sizing (D-229) and measures a fix, not a task; file count is what the router and the operator can see before any work.
- **R7 — no lane; sharpen the existing test's wording.** The test was right and was applied at the wrong moment; wording cannot fix WHEN.
- **R9 — `~/.claude/state/command-runs/` as the salami lookup store.** The run-records dir is per-session and pruned; the feedback ledger is fleet-wide, append-only, and already read on the close path (`_queue_depth`, `command_run.py:1660-1710`), so the overlap check folds into a read that exists.
- **R8 — Oxide's shape: one artifact, variable depth, judgement decides.** Grounded (RFD 1). Rejected here because our artifacts are graded by checkers that grep for fixed headings (`check_spec_convergence.py`, `check_convergence.py`), so "one artifact at variable depth" fights the gate instead of using it; and because the failure this spec answers was a JUDGEMENT failure — the depth was chosen wrong three times in one day — which is the case for an executable test, not for more judgement.

## Lifecycle

- **Adoption / first run:** the build ends with the DOGFOOD — the first `/fabrik-task` is run on a real candidate from the backtest, and the command is not declared done until that run closes.
- **Growth triggers, read from V4's series (each a trigger to re-examine, none a pass/fail):** a rising `oversized_mini` share → the file or mechanism test is re-examined by a `/fabrik-command-improve` run on this command's queue; a rising `upgrade` share → the rule is too permissive at the top and the table tightens; a median wall-clock drifting toward the chain's → phase 2 or 4 is the suspect; a FALLING adoption share beside a green `oversized_mini` → the lane is being skipped, not gamed (C3's third cobra).
- **The ratchet must not accrete process (DORA's vicious cycle):** an UPGRADE is a hand-off to the lane that already exists, never a new step added to this one; if UPGRADE rates rise, the response is to tighten the six tests at the top, not to add checks inside `/fabrik-task`.
- **Degradation:** if `command_run.py`'s re-measure cannot run (no git, no `declared.sha`), the close records `oversized_mini: unknown` — counted as an instrument gap, never bucketed as clean (the kaizen collector's own rule).
- **Retirement:** remove the source, the two router rows, the table row in both CLAUDE.md copies, the two doc rows and the tests; in `command_run.py` the phase-0 refusal tests and the re-measure go with them, while `--declare` and the row fields stay accepted, because closed records and ledger rows reference them.

## External dependencies

**1a — none.** This design is purely internal: no vendor, API, SDK, library, protocol or pricing is touched. Every fact above is grounded in this repo at `path:line` or measured from its ledgers this session.

**1c — approach grounding (live research, this session).** The design's core is a tiered change process with a reversibility-first sizing test and a one-way upgrade ratchet. Grounded live by a `fabrik-researcher` seat, 2026-09-17, each source fetched raw unless marked:

- **A published three-lane system for the identical gap — SUPPORTS the lane.** Rust's compiler team runs PR (light) / MCP (medium) / RFC (heavy): *"RFCs are… a heavy-weight proposal mechanism, reserved for significant changes… MCPs are… a medium-weight proposal mechanism, suitable for most proposals… PRs are… a light-weight proposal mechanism."* — https://forge.rust-lang.org/compiler/proposals-and-stabilization.html. Its founding RFC states the gap in our words: *"a channel for signaling intentions that lies somewhere between opening a PR… and creating a… design meeting proposal or RFC"*, to *"avoid the phenomenon of PRs living in limbo because it's not clear what level of approval is required."* — https://rust-lang.github.io/rfcs/2904-compiler-major-change-process.html. (The forge page says PRs are *also* "suitable for most proposals"; the phrase does not distinguish the MCP tier.)
- **The size test is NOT lines or files — CONTRADICTS a file count as the primary test.** RFC 2904: *"whether something is a major change proposal is not necessarily related to the number of lines of code that are affected. Renaming a method can affect a large number of lines… but it may not be a major change."* Google's design-doc guidance centres the decision on ambiguity and trade-offs: *"At the center of that decision lies whether the solution to the design problem is ambiguous"* and *"If a doc basically says 'This is how we are going to implement it' without going into trade-offs… it would probably have been a better idea to write the actual program right away."* — https://www.industrialempathy.com/posts/design-docs-at-google/. The tests the field publishes are cross-team reach, public contract, new architectural component, reversibility, and ambiguity (designdoc.tech, 2026-04-03, a vendor blog: *"1. Does this affect more than one team?… 2. Is this hard to reverse?… 3. Does this introduce a new architectural component?… 5. Does this change a public contract?"* — its item 4, elided here, is a documentation-value test, *"Will people need to understand this decision six months from now?"*, so the list is not purely blast-radius — https://designdoc.tech/blog/when-not-to-write-an-rfc). **Consequence for this spec:** the decision rule leads with those; the file count is a house heuristic, stated as one.
- **Reversibility is a member of every published test set, never ranked first — SUPPORTS it as mandatory, CONTRADICTS "reversibility first".** The concept itself is not grounded externally: `docs/reference/operating-manifesto.md:10-14` (Phase 0 triage) is this repo's authority on reversible-vs-one-way and the SIZE gate cites it directly. What the field adds is only the ranking: designdoc.tech lists cross-team first and reversibility second; RFC 2904 uses reversibility as one of two shortcut conditions inside the process (*"The FCP can be skipped if the change is easily reversed and/or further objections are considered unlikely"*), not as the classifier.
- **The ≤12-line design is Google's own mini doc — SUPPORTS phase 2.** *"it is absolutely possible to write a 1-3 page 'mini design doc'… you still do all the same steps as for a longer doc, just keep things more terse."* — industrialempathy.com, above.
- **Size guidance that exists names lines and treats files as a multiplier, with no file number — SILENT on "3".** Google eng-practices, which disclaims any threshold first (*"There are no hard and fast rules about how large is 'too large'"*): *"100 lines is usually a reasonable size for a CL, and 1000 lines is usually too large… it's up to the judgment of your reviewer… A 200-line change in one file might be okay, but spread across 50 files it would usually be too large."* — https://google.github.io/eng-practices/review/developer/small-cls.html. SmartBear's own study of a Cisco team (a vendor study) on review effectiveness: *"beyond 400 LOC, the ability to find defects diminishes."* — https://smartbear.com/learn/code-review/best-practices-for-peer-code-review/. DORA: *"working in small batches predicts software delivery performance"* with a TIME threshold (*"longer than a week… is too big"*) — https://dora.dev/capabilities/working-in-small-batches/.
- **The measured gaming shape is salami-slicing, and the counters are published — SUPPORTS the cobra section as amended.** *"There is an incentive to make RFCs as small as possible since the smaller the RFC is, the easier it is to get accepted […] unfinished features where the initial work is done but follow-up work is not tracked."* (the elision spans the author's own concession that this "could be good") — https://www.ncameron.org/blog/the-problem-with-rfcs/. Counters: reviewer-side upward bounce — *"If the approval required… requires an MCP or an RFC, then the contribution should be closed or marked as blocked, with a request to create an MCP or RFC first"*; and *"An earlier accepted MCP is not a substitute for any later necessary approvals."* — forge.rust-lang.org, above. DORA names the mirror cost of the lighter lane being skipped rather than gamed: *"Treating all changes equally… change review is inefficient, and people are unable to devote time and attention to those that require true concentration."* — dora.dev, below.
- **Uniform heavy process is the named pitfall; tiering is the recommendation; but an escalation path must not accrete process — SUPPORTS the lane, WARNS the ratchet.** DORA: *"Treating all changes equally. When all changes are subject to the same approval process, change review is inefficient"* and *"Responding to problems by adding more process […] drives up lead times and batch sizes, creating a vicious cycle."* — https://dora.dev/capabilities/streamlining-change-approval/. designdoc.tech on the mirror risk: *"Once engineers view the RFC process as red tape, they stop engaging meaningfully with the RFCs that actually matter."*
- **The one-way ratchet has direct precedent — SUPPORTS.** The brainstorming skill this design was born in: *"The ratchet is one-way: hidden complexity discovered mid-task upgrades the path — stop, say so, and step up. Nothing downgrades mid-task."* — https://raw.githubusercontent.com/obra/superpowers/refs/heads/main/skills/brainstorming/SKILL.md; RFC 2904: *"if the change proves more controversial or complex, we may escalate towards design meetings, longer write-ups, or full RFCs before reaching a final decision."* A DOWNGRADE path was found in none of the 4 process documents fetched — *not found in 4*, not "does not exist".
- **An alternative shape the field uses — RECORDED as R8.** Oxide scales depth inside ONE artifact rather than adding lanes: *"use your best judgement when it comes to the level of depth to devote to an RFD."* — https://rfd.shared.oxide.computer/rfd/0001.
- **Verified in full text — SUPPORTS "small = few files" as a distribution, names no threshold.** Sadowski et al. 2018, *Modern Code Review: A Case Study at Google*, § "Review size": *"over 35% of the changes under consideration modify only a single file and about 90% modify fewer than 10 files."* — https://doi.org/10.1145/3183519.3183525, read through the DOI's full-text mirror (dl.acm.org answers 403 to fetchers; the abstract does not carry the figures). Not quoted, not load-bearing: the DORA 2024 PDF and pandev-metrics' matrix.

## fabrik-lib verdict table

| capability | verdict | why |
|---|---|---|
| sizing test + declaration persistence | BUILD (extend `command_run.py`) | the record already exists; nothing in fabrik-lib models a run |
| routing | BUILD (two rows in `skill_router.py`) | box-local hook |
| review | REUSE `/fabrik-review-scoped` | unchanged |

## Shape / infra implications

Hub-side only; no scaffold type, no `shape:` flag. Fleet-synced files touched: `scripts/command_run.py`, `.claude/hooks/skill_router.py`, `templates/governance/CLAUDE.md` — all governance-sync triggers, so the build's commit distributes to ~46 repos on the post-commit hook and the command renders box-wide. `commands/_sources/fabrik-task.md` reaches agents by render, not sync.

## Constraints

- **C1 — sequence, never restate.** The source points at run-record, close-feedback, the FIX DIRECTIVE, `/fabrik-review-scoped`, the D-row rule; it restates none. Adds exactly SIZE and DESIGN.
- **C2 — lean.** Source ≤ 8,847 B (`fabrik-features.md`, the smallest today), measured by `check_corpus_weight.py --check`; renders `run-record` (3,245 B) and `close-feedback` (14,612 B) like every command; never `term-coverage` (25 KB) or `term-edit`.
- **C3 — manifesto.** ONE-WAY excluded (test 3); the cobra written in the command's docstring: the cheapest bypass is UNDER-DECLARING at phase 0 — the counter is the executable re-measure at close writing `oversized_mini` as a series, plus the review seats asked whether the change fits the declaration. The residual bypass the re-measure cannot see — declaring `mechanism=no` and adding a flag anyway — is countered only by phase 4's second question (`mechanism_missed`), and is named as such. **The THIRD cobra, and the cheapest of all: never open a `/fabrik-task` record** — do the spec-sized change as a right-now fix + `/fabrik-review-scoped`, the lane one step below, which has no gate, no declaration and no re-measure. Every counter above is blind to it by construction, and so is a success metric whose denominator is "`/fabrik-task` closes". Its counter costs no machinery: § Validation reports the lane's ADOPTION SHARE — `/fabrik-task` closes over (`/fabrik-task` + `/fabrik-review-scoped`) closes in the same window (baseline: 26–36 review-scoped closes per ISO week, weeks 37–38 of 2026) — and a falling share beside a green `oversized_mini` reads as evasion, not success. **The FOURTH: commit the bulk before `start`**, so a diff from `declared.sha` sees nothing; the re-measure's author-trailer half is its counter, and it is best-effort. **The SECOND cobra, and the one the literature measured (ncameron): SALAMI-SLICING — a spec-sized change cut into several mini tasks that each pass the gate.** Three counters, all published shapes: (a) phase 4's seats hold an UPGRADE verdict — *"this change requires the spec lane"* bounces the run to `handoff`, exactly as Rust closes a PR with *"a request to create an MCP or RFC first"*; (b) an accepted mini buys nothing later — its D-row is a record of one reversible decision and confers no approval on a follow-up (Rust: *"An earlier accepted MCP is not a substitute for any later necessary approvals"*); (c) `_close` writes `declared_files` onto the feedback row, and a `/fabrik-task` whose paths overlap any prior `/fabrik-task` row **in the same repo** is flagged `salami_suspect: <prior row>` — a series, read like `oversized_mini`, never a block. Implementation facts the build inherits: the check runs BEFORE `_pending_row` is built (`:3661`), not at `_queue_depth`'s call site (`:3729`, after the row is appended); the ledger is box-global, so the `repo` field filters; `declared_files` passes `_cap_field` (2,000 chars, `:1602-1606`) and a truncated list degrades detection; the read inherits `_queue_depth`'s fail-soft and FIFO-guard contract (`:1660-1676`). No time window — the flag is advisory, and a window is a number with no reason. What none of the three can see is a slice that touches disjoint paths for one design; that residual is named here and left to the operator's read of the D-rows.
- **C4 — infra.** Plan-locks by `owned_paths`; pool OFF (D-181/D-182); the sync regex read from the YAML; shared-append files by the private-index recipe.
- **C5 — rules.** `select_rules.py` + ACTIVE packs at phase 1; `review_rubric.py --changed` at phase 4.
- **C6 — no new enforcement check** (D-097); the refusal lives in the command's own tool, and FIX DIRECTIVE 5 still binds it: its fire rate is measured in V0 before the build, on the hub and stated as the hub's.

## Cost

| file | change | synced? |
|---|---|---|
| `commands/_sources/fabrik-task.md` | NEW, ≤ 8,847 B | render only |
| `scripts/command_run.py` | `start --declare` + the phase-0 tests + `_close` re-measure + `oversized_mini` on the row | YES — heavy; full `/fabrik-review` on this phase |
| `.claude/hooks/skill_router.py` | `STEM_SKILLS` + `KEYWORD_STEMS` rows | YES |
| `CLAUDE.md` / `templates/governance/CLAUDE.md` | the six-test table in § Orient step 0 | template YES |
| `tests/test_command_run.py`, `tests/test_skill_router_hook.py` | graders, red-first | — |
| `docs/CAPABILITIES.md`, `docs/reference/command-run-protocol.md`, `INDEX.md`, `CHANGELOG.md`, `docs/DECISIONS.md` | rows | — |

Estimated: `command_run.py` ~215–305 lines (`--declare` parse and five refusals ~60–90; the regex read from the YAML ~40–60; declaration persistence ~15; the authorship-scoped re-measure ~60–80; `salami_suspect` under `_queue_depth`'s contract ~40–60 — for scale, `_queue_depth` alone is 63 lines for one ledger read); the command source ~200 lines; the router rows ~20; graders at D-169's 1.5× ratio ~300+. Five non-test files (the source, `command_run.py`, the router, both CLAUDE.md copies) plus two tests. That exceeds D-169's ≤400 lines / ≤5 files on both axes: **the build runs `Profile: standard`**, and its `command_run.py` phase is the one heavy `/fabrik-review`. By this spec's own rule the change is spec-lane work (tests 1, 2, 3 all trip) — the rule applied to its own first customer.

## Validation

**V0 — Fire rate, measured before the build (FIX DIRECTIVE 5).** Over the last 300 hub commits, the four shared-append files CLAUDE.md names plus `docs/LESSONS_LEARNT.md` excluded by name (including it moves the figures by ~1.3 points, not the conclusion): 33% touch a governance-sync path; 69% touch ≤3 non-ledger files; 54% pass both mechanical tests; **46% would be refused at `start` by at least one.** That is the hub's rate — its beat is the synced surfaces — and the refusals route to the lane the contract already names for them. The 46 project repos are expected to read far lower; the build measures one of them before the sync.

**V1 — Backtest (I12), over COMMITS, not ledger prose.** The ledger's `surface` field is free text (30% of done rows name no file at all), never records reversibility or trade-offs, and passes `_cap_field`, whose truncation shrinks a file list and so biases toward "≤3 files" — a backtest over it would test the seats' guessing, with a bias toward agreeing with the lane. So the backtest runs over the last 300 hub commits: tests 1 and 5 EXECUTED from `git show --name-only` (exact), tests 2, 3 and 4 answered by author-blind seats from the commit body and any D-row it cites. Sample 24 by seed 17 from the 217 commits with a non-ledger file: `d58bc4081 c9f8b0de5 17472c0aa 352347eec 3f6b80547 3f136995b e305994d1 5489ef2f5 11b75eac3 48742920a 51bbdeffd c8155724d 69cff4f7d 3b1f8f231 b206f0655 b5c018552 b65d6557d 76e3a738c db62cdf9e 13c1271d3 a9e0213b1 d6e844292 5ea5029d4 7cef85768` — in it the sync test trips 9 of 24, the file count 12 of 24, and 9 of 24 pass both. Report agreement between the six-test verdict and the lane each commit actually took, adjudicate every disagreement; a rule that disagrees with >30% of them is re-cut before the build.

**V2 — Dogfood (I11).** The first `/fabrik-task` run is on a real candidate V1 names as mini; the build is not done until that run closes with a converged review and a D-row.

**V3 — Cobra probe.** A seat attempts to route a known spec-sized task (one the backtest classed as spec) through `/fabrik-task` by under-declaring, and reports whether phase 0 refuses, phase 4's seats catch it, or phase 5's re-measure records it — and whether any path lets it through silently.

**V4 — Success series, read from the feedback ledger with no new machinery, UNTHRESHOLDED for the first 20 closes:** median wall-clock (predicted: the light lane's 32 min plus phase 0 and phase 2, not a midpoint of two lanes it does not combine); rounds-to-converge; the `oversized_mini` rate; the UPGRADE rate (`upgrade` field); and the ADOPTION SHARE against `/fabrik-review-scoped`. Twenty closes cannot decide a 10% ceiling — P(≤2 of 20 | true rate 20%) = 0.21 — so nothing is pass/fail on the build; each is a trigger to re-examine, and § Lifecycle names the re-examination. The ledger is fleet-wide: the cost table in § Why this exists and these series both span every repo, which is right for a lane that renders box-wide and is stated here.

## Documentation landing sites

- `docs/reference/command-run-protocol.md` — the `--declare` extension and the `oversized_mini` field, beside the existing `--surface` text.
- `docs/CAPABILITIES.md` — the command's bullet.
- `INDEX.md` — the new source file's row.
- `CHANGELOG.md` — the build's entry.
- `docs/DECISIONS.md` — the rows in § Decisions taken.
- The command's own source is self-documenting for its phases; no dedicated reference doc is opened (it is a command, not a subsystem).

## Decisions taken (minted at CONVERGED)

- D-a — the three-lane rule and the moment it applies (before drafting, to the minimal discharge) — **supersedes D-097 clause (b)** (the binary mail-sizing test) and **extends D-098** (the project agents' three outcomes gain the lane).
- D-f — the step budget is SIX; a seventh forces a bump and says why.
- D-g — `handoff` is the UPGRADE verb; no new verb is minted (R4). The V4 numbers are command text, not decisions.
- D-b — `/fabrik-task` exists; the D-row is its durable artifact; ONE-WAY decisions are excluded.
- D-c — the ≤3-file threshold, grounded on the 69% measurement.
- D-d — the SIZE gate is a refusal in the agent's own tool, not an enforcement check (consistent with D-097).
- D-e — the cobra counter: re-measure at close, `oversized_mini` as a kaizen series.

## Open / blocking unknowns

- **U1 — RESOLVED by ruling here:** structured `--declare` versus free-text `--surface` — structured, because `_close` must parse it to re-measure.
- **U2 — OPEN, named resolution:** the exact `KEYWORD_STEMS` regexes. Resolved in the build against BOTH corpora — the collision corpus (any anchor that fires is cut) and a positive corpus of ≥15 realistic prompts (a set below 50% recall is not shipped; surface 1 stands alone).
- **U3 — OPEN, named resolution:** whether the backtest agreement clears 70%. Resolved by V1 before the build; below it, the rule is re-cut and this spec's § The decision rule is amended on its next non-delta pass.
- **U4 — RESOLVED:** the 1c approach grounding landed (§ External dependencies), and it re-cut the decision rule and the cobra section before self-review.
- **U5 — RESOLVED for Sadowski 2018:** the quote is verbatim in the paper's body (§ "Review size"), reached through the DOI's full-text mirror (dl.acm.org returns 403 to fetchers) — the source of record is that mirror, stated as such. The DORA 2024 PDF and pandev's matrix stay unquoted; neither decides anything here.
- **U6 — OPEN (design, the review's own residue): "the moment" is not observable by the record.** Pass 2 established that the event stream carries 17 event types and no tree-write event, and no turn boundary (`scripts/sysadmin/kaizen_events.py:114-132`, `:476-490`), so "`start` is the turn's first write-verb event" cannot be checked. The one observable is `mtime(declared files) < started_epoch` at `start` — a file already edited before the record opened. Resolution: § Chosen approach phase 0 drops the first-event claim, states the moment as a discipline, and adds the mtime pre-check; the tripwire is restored as the enforcement.
- **U7 — OPEN (design): the declare set cannot express "no decision at all".** A pure fix declares `mechanism=no,oneway=no,tradeoffs=no` and is ADMITTED, so the lane swallows the right-now lane test 4 routes to. Resolution: `decision=<yes|no>` joins `--declare`; `no` refuses, naming right-now + `/fabrik-review-scoped`.
- **U8 — OPEN (contract fork, the operator's): test 1's destination does not exist for 13% of hub commits.** CLAUDE.md § Completion Contract 1a's heavy-surface triggers (new mechanism, gate/hook/enforcement, auth/schema/migrations/concurrency, >5 files, operator-named) name no sync-path trigger; of the 99 of 300 hub commits that touch a sync path, 39 touch only non-1a sync paths (`templates/governance/`, `.windsurf/rules/`, the root governance files, `.claude/settings.json`) and would be refused into a LIGHTER lane than `/fabrik-task`. Resolution: § 1a gains "a governance-sync path" as a heavy trigger in the same change — a contract edit, so the operator rules on it — or test 1's refusal names `/fabrik-review` explicitly and 1a is left alone.
- **U9 — OPEN (design): the re-measure's commit half matches nothing and its mtime half mis-attributes.** No `Agent-Context` string is defined for a run and the record holds no run id (0 occurrences in `command_run.py`); the `:3243` mtime pattern's own comment records a sibling's UNCOMMITTED write being attributed to the wrong run, and the spec's fail-open was keyed on commits, so it never fires. Resolution: the re-measure is mtime-only and best-effort; ANY mtime movement outside `declared.files` since `started_epoch` records `oversized_mini: unmeasurable`; the commit half is dropped.
- **U10 — OPEN (scope fork, the operator's): the six new row fields have no reader.** 0 of 9 `scripts/sysadmin/kaizen_*.py` read the feedback ledger; `scripts/command_feedback_report.py` consumes a fixed 18-key set that names none of `oversized_mini`, `salami_suspect`, `upgrade`, `size_missed`, `mechanism_missed`, `tradeoff_missed`. The spec's "no change to its code is owed" is false. Resolution: either `command_feedback_report.py` gains a `--lane fabrik-task` reader (a sixth non-test file in the build) or the fields are cut to `oversized_mini` + `upgrade` and surfaced by the existing `--queue` header. The operator rules on the scope.
- **U11 — OPEN (design): no writer carries the seats' three answers onto the parent's row.** `/fabrik-review-scoped` opens its own nested record; nothing writes onto the parent's pending row from it. Resolution: `done --review-verdict size=<y|n>,mechanism=<y|n>,tradeoff=<y|n>` on the parent, transcribed by the primary from the review's close.
- **U12 — OPEN (design): the UPGRADE ratchet has no exit at phase 1** and its artifact guarantee is false. `handoff --resume` is `required=True` for a STRING; nothing validates the path (`:3509`); and at phase 1 the record is already running, so "start's own refusal" cannot apply. Resolution: the ratchet is available from phase 1; the phase-1 seed is a `design.md` holding only the `## RESUME` block; the text says the seed must be materialised FIRST because nothing checks it.
- **U13 — OPEN (residual): scratch death before phase 5 loses the only design copy.** The D-row is minted at phase 5; a session that dies at phase 3 leaves `design.md` to the janitor and the record to the coroner. Resolution: phase 2 also appends the six fields to the run record as `design` (a string field, written once, never overwritten — `phase_title`'s overwrite is why it cannot live there), so the record outlives scratch.
- **U14 — OPEN (nit): `--declare files=a:b:c` uses two legal filename characters as separators** with no escaping and no refusal. Resolution: refuse a declared path containing `,` or `:`, or take a repeated `--file` flag.
- **U15 — OPEN (nit): two citations off by a hair** — the mtime pattern is `>= started_epoch - 2` (a 2-second slack sitting on the boundary this test lives on), and `command_feedback_report.py:941-950` aggregates `surface` per `(command, item)` rather than "groups by" it; the I17 ledger row is cited by a mis-rounded key (`round(1789669428.86)` is 1789669429 — cite the float).
- **U16 — OPEN (nit): `declared_files` has no named reader in § Personas** — its reader is `_close` itself at the next `/fabrik-task` close in the same repo.
- **U17 — OPEN (design): the adoption share's denominator contains its numerator.** Phase 4 invokes `/fabrik-review-scoped`, whose `done` appends a review-scoped row, so every task close adds one to both sides: `T/(2T+S)`, structural ceiling 50%, and the stated 26–36/week baseline is pre-adoption, done-only, with week 38 a partial week (~4 of 7 days, pace ~45). Resolution: the share is `T / (T + S_standalone)` where a review-scoped row nested under a `/fabrik-task` parent is excluded — the row's `stack` or a `parent` field tells them apart; the baseline is restated as done-only and re-read over a complete week.
- **U18 — OPEN (design): the fourth cobra's counter is blind to it.** A commit made BEFORE `start` is not "since `started_epoch`" and its files' mtimes precede it — neither half of the re-measure can see it, so "the author-trailer half is its counter" is false; a trailer the same agent writes after the fact is a self-report. Resolution: name the bypass as UNCOUNTERED by the re-measure, and counter it with the one observable U6 names — `mtime(declared files) < started_epoch` at `start` refuses a record opened after the work.
- **U19 — OPEN (contract fork, the operator's): D-a supersedes D-097(b) but no file edits the text that clause lives in.** D-097(b)'s own home is CLAUDE.md § Behavior's HANDLE-NOW clause (`>5 files`), and § Cost touches only § Orient step 0, so after the build a 4-file mail-driven change is right-now under § Behavior and spec-lane under D-a. Resolution: the same change edits the HANDLE-NOW clause to point at the step-0 table (one pointer, no restatement), or D-a's file-count test is aligned to `>5` — the operator rules.
- **U20 — OPEN (design): `salami_suspect` with no window saturates on hot files** — `scripts/command_run.py` appears in 48% and `CLAUDE.md` in 72% of the last 300 hub commits, both in scope, so from the second `/fabrik-task` in this repo the flag fires on nearly every run: wallpaper. Resolution: exclude the measured hot set (any path touched by >25% of the last 300 commits, recomputed at close) or scope overlap to the same DESIGN (the D-row's subject), and restore a window with the measured reason.
- **U21 — OPEN (nit): the `salami_suspect` insertion point is `≤ :3655`, not `:3661`** (`:3661` is inside the `_row` dict literal; `_pending_row = _row` is `:3677`).
- **U22 — OPEN (design): the backtest population is 54% commits that had no lane choice** — 13 of the 24 carry `Agent-Role: review-fix` or an `Agent-Phase`, i.e. were made inside a running plan or review loop, so "the lane it actually took" is not theirs. And a commit body records what was DONE, not what was CONSIDERED, so an unstated trade-off reads as "no trade-offs" → mini: the bias survives the move from ledger to commits. Resolution: the population is commits with NO `Agent-Phase` and `Agent-Role: primary` (denominator restated), and tests 2/3/4 are answered from the D-row a commit cites or marked UNANSWERABLE, never inferred from silence.
- **U23 — OPEN (design): V4 names no n at which the series decides.** Computed: a ≤10% `oversized_mini` ceiling is decidable against a 20% alternative at n = 82 closes (α 0.05, power 0.80; accept if ≤10 of 82). Resolution: V4 states "re-read at 82 closes; descriptive below that", and § Lifecycle's "rising" gets that definition.
- **U24 — OPEN (nit): § Cost's ~200-line source estimate contradicts C2's ≤ 8,847 B cap** — the corpus runs 73–188 B/line (median 88; `fabrik-features.md` is 115 lines at 77 B/line), so ~200 lines is ~2× the cap. Resolution: the source is ~110 lines; the `Profile: standard` argument rests on the `command_run.py` lines, which stand.
- **U25 — OPEN (nit): "exceeds D-169 on both axes" is false on the file axis** — five non-test files is ≤5, not >5; the line axis alone carries `Profile: standard`.
- **U26 — OPEN (design): V0 is a base rate, not FIX DIRECTIVE 5's fire rate** — it counts correct refusals, never false ones, and states no verdict or rejection threshold. Resolution: V0 adds an adjudicated sample (20 refused commits, each judged "should this have been mini?"), a false-refusal ceiling above which the gate is REJECTED (a recordable outcome), and a post-build re-measure.
- **U27 — OPEN (nit): `_queue_depth` is 54 lines (`:1660-1713`), not 63; the retired lane keeps emitting series unless the reader stops reading them; R5's D-097 grounding is mail-scoped; U2's router row already failed its own bar at n=8 (0% recall) and is RESOLVED-NEGATIVE pending a wider corpus.**

## Residual assumptions

- That mtime-since-`started_epoch` plus the `Agent-Context` trailer identify a run's own change well enough on a shared tree; where they cannot, the close says `unmeasurable` rather than guessing.
- That a scratch `design.md` survives the run: scratch is disposable by contract, so the D-row (minted at phase 5) is the only copy that outlives the session — an UPGRADE before phase 5 hands the file to `/fabrik-spec` in the same turn.
