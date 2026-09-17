# `/fabrik-task` — the lane between a right-now fix and the spec chain

**Status:** DRAFT
**Profile:** full section set. `Profile: delta`'s trigger — *every Intake Inventory item maps to code that exists today* — fails: `/fabrik-task` is a NEW command with no source file behind it, and two of its three code changes add behaviour (`command_run.py start` gains a declaration, the router gains a stem). Verdict stated per the profile rule.
**Owner:** infra (this hub window). **Date:** 2026-09-17.
**Emitted by:** `/fabrik-spec`, seeded by a `superpowers:brainstorming` run (architectural path) in the same session.

## Personas

**Primary — the agent about to do a small-but-real change, in the operator's words:** *"be 100% sure about your design as you will be the consumer."* The consumer is the running agent — in the hub and in the ~46 project repos where the command renders — holding a change that carries one decision and needs "our way of working and structure" without the spec chain.

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
- **The kaizen collector** (automated) — reads the new `oversized_mini` field as a series; no change to its code is owed by this spec (the field rides the existing feedback row).
- **Sibling sessions** (automated) — subtract `/fabrik-task`'s dispatch stamps exactly as for any command; nothing new.
- **`/fabrik-review-scoped`'s seats** — receive the design fields in their brief and are asked whether the change fits the declared size; the command itself is invoked unchanged.
- **The project agent in ~46 repos** — receives the three-lane decision rule through `templates/governance/CLAUDE.md` § Orient step 0 (a sync trigger) and the rendered command box-wide.

Every feature below traces to one of these; a mechanism with no persona here is cut.

## Intake Inventory

| I# | Item (anchored to the operator's words) | Disposition | Where |
|---|---|---|---|
| I1 | *"some tasks does not require full spec/specreview/plan/planreview/execute/fabrikreview/scopedreview"* | IN | § Why this exists; § Chosen approach (KEPT/DROPPED table) |
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
| I13 | *"what will /fabrik-task do? compact of all spec/specreview/plan/planreview/execute/fabrikreview/scopedreview?"* | IN | § Chosen approach — the KEPT/DROPPED table |
| I14 | *"spec takes hours"* (the sizing question earlier in the session) | IN | § Why this exists — measured |
| I15 | *"i face this issue a lot in all repos, so we need a permanent and well working mechanism"* | IN | § Awareness — the rule lands in the template contract too; § Lifecycle |
| I16 | D-row versus a mini-spec file as the durable artifact — the fork I put to the operator; answered with *"yes task looks fine"* | IN | § Chosen approach — D-row; § Rejected alternatives R3 |
| I17 | The adjacent-damage checker (reading A of the brainstorm: an edit silently damages neighbouring text and every gate stays green) | OUT-OF-SCOPE | A separate mechanism, not a lane. Destination that exists: the `change:` verdict filed against `/fabrik-review-scoped` at its close in this session (feedback ledger, ts 1789671545, "a fix REPLACING a whole long line asserts the neighbouring lines' opening clauses survive it") — it will be read by that command's next `/fabrik-command-improve` run. |

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

**Both failure directions, executed in one session (2026-09-17):** the same one-paragraph edit to `commands/_sources/fabrik-review-scoped.md` was attempted three times as an elaborated mechanism — 3 review rounds, 35 findings, 22 confirmed, confirmed/own-fix 10/0 → 6/6 → 6/6 firing the D-278 stop, the third cut regressing the rendered corpus — and all three reverted; then once correctly sized: 130 B, 1 confirmed defect, converged on pass 2 (commit 02df9b74f, D-288). The difference was not care; it was WHEN the sizing test was applied. The contract's existing test (CLAUDE.md § Behavior, the mail SIZING step, D-097) is sound and was applied to the *draft* — which, once elaborated, genuinely was a mechanism.

**The asymmetry that decides the default:** over-sizing costs ~6 hours before any code; under-sizing costs one ~30-minute review, with the review as the backstop. Those are not symmetric risks. The lane exists to make the cheap direction the default without making it the *unreviewed* direction.

## What exists today (grounded)

- **The sizing test** — CLAUDE.md § Behavior, mail HANDLE-NOW clause: *"a validated request is either SPEC/PLAN work (a new mechanism, a vendored/synced surface, schema, auth, >5 files) … or a RIGHT-NOW fix"* (D-097, 2026-09-03; extended fleet-wide by D-098 with a third outcome for project agents: file upstream). It names no moment and no object to apply itself to.
- **`Profile: small`** (D-169, 2026-09-06) — an EXECUTION profile: plans ≤ ~400 lines / ≤ 5 files run inline with `/fabrik-review-scoped` per phase and one heavy round. It still costs spec + spec-review upstream. It is unchanged by this spec and stays the execution profile inside the chain.
- **The run record** — `scripts/command_run.py`: `start` already takes `--surface` and persists it (`:2643`, `"surface": (args.surface or "").strip()`); the Stop hook reads that field for review-family records (`.claude/hooks/final_gate_stop.py:996-1010`). `_close` (`:3121`) owns `done`/`blocked` and writes the feedback row with `wall_s` and `rounds` (`:3662`, `:3678`). `handoff` exists as a sanctioned close. **No new verb is required**: phase 0 is an extension of `start`, the re-measure lives in `_close`, UPGRADE is `handoff`.
- **The router** — `.claude/hooks/skill_router.py`: Tier 1 is `STEM_SKILLS` (stem → skill, `:105-`) plus `KEYWORD_STEMS` (bilingual regex → stem, `:175-`); *"a stem here with no KEYWORD_STEMS row never matches; a row there with no entry here resolves to None"*. Tier 2 (Haiku) is off unless `FABRIK_ROUTER_HAIKU=1`. So awareness at the router **requires both rows**, and the file is a governance-sync trigger.
- **The sync trigger set** — `.pre-commit-config.yaml:155`, the `governance-sync` hook's `files:` regex; `scripts/governance_sync_postcommit.sh` re-reads it. `commands/_sources/` is NOT in it (tested); `scripts/command_run.py`, `.claude/hooks/`, `templates/governance/` ARE.
- **The review the lane invokes** — `/fabrik-review-scoped` (`commands/_sources/fabrik-review-scoped.md`, 18,654 B): units-sized, floor 3 readers at round 1, closes on a delta pass confirming zero. Invoked unchanged.
- **The manifesto's triage** — `docs/reference/operating-manifesto.md:10-14`: *Reversible (cheap to undo, contained blast radius) → skip to Phase 4 … One-way (structural, public, expensive or impossible to unwind) → run the full loop. Rigor scales with irreversibility.* A ONE-WAY decision grows its D-row with the Binding block (`:102-106`).
- **The cobra rule** — D-253 / CLAUDE.md FIX DIRECTIVE 5: every gate or counter introduced writes down its cheapest bypass in the same change.
- **A rejected mechanism that binds this design** — D-097 REJECTED a new enforcement check for mail triage: *"fire rate unmeasured and the Stop hook already blocks record-less code edits (FIX DIRECTIVE 5)"*. The SIZE gate must therefore be a refusal inside the agent's own tool on the agent's own declaration — the shape `done --feedback` already has — never a gate over others' work.
- **The feedback ledger and the kaizen loop** — every close writes `wall_s`, `rounds`, the four verdict fields (D-175); `command_feedback_report.py --queue` and `/fabrik-command-improve` consume them (D-234). A new field on the row is read by the collector with no code change.
- **Where commands are documented** — `docs/CAPABILITIES.md:387` (one bullet per command), `docs/reference/command-run-protocol.md` (the record contract; names `--surface` at `:208`, `:221`, `:224`), `INDEX.md`.
- **What a "small change" is, measured** — over the last 300 hub commits, excluding the five shared-append ledgers: 69% touch ≤3 non-ledger files, 81% ≤4, 87% ≤5. "≤3" is the two-thirds line, not a round number.

## Chosen approach

**One command, one run record, the D-row as the durable artifact. It SEQUENCES existing mechanisms and RESTATES none.** The command's source is glue between four things that already exist as fragments or contract text — the run record, the FIX DIRECTIVE, `/fabrik-review-scoped`, the close-out feedback — and it adds exactly two new things: the SIZE gate and the DESIGN-in-the-record step.

**Phase 0 — SIZE.** The agent names the files. `command_run.py start --command fabrik-task --surface "<files>" --declare mechanism=<yes|no>,oneway=<yes|no>,paragraph=<yes|no>` then:
- **executes** two tests: file count ≤ 3, and every declared path against the governance-sync regex read from `.pre-commit-config.yaml` (the same regex `governance_sync_postcommit.sh` reads; never a copy);
- **records** the three declared answers; a `yes` to `mechanism` or `oneway`, or a `no` to `paragraph`, is a refusal;
- on any failure **REFUSES the start and NAMES the lane** (`REFUSED — fabrik-task: <test> → /fabrik-spec`), and on success persists `declared: {files, mechanism, oneway, paragraph, sha}` in the record, where `sha` is `git rev-parse HEAD` at start.
This is not a new enforcement check over the tree (D-097's rejected shape); it is the command's own tool refusing an under-specified start, exactly as `done` refuses without `--feedback`.

**Phase 1 — MEASURE.** FIX DIRECTIVE 1 verbatim: reproduce, attribute, name the root cause. `python scripts/select_rules.py` over the declared surface; the ACTIVE packs are read. The terminal condition is already in the record from `start --terminal`.

**Phase 2 — DESIGN IN THE RECORD.** `command_run.py step --phase 2 --title "PROBLEM: … · APPROACH: … · DECISION: … (reversible) · MIRROR: … · OUT: … · TERMINAL: …"`. Six fields, one step title, ≤ ~1,200 characters. This is the spec collapsed to what a spec decides, and it is the D-row's source. MIRROR is mandatory: the contract's *"every contract change has a MIRROR — name the shape you just broke"*.

**Phase 3 — BUILD.** Plan-lock check by `owned_paths` against the declared paths first; the change and its grader, red-first; shared-append files by the private-index recipe.

**Phase 4 — REVIEW.** `/fabrik-review-scoped` invoked as the skill, unchanged. Its seat briefs carry the phase-2 fields and the phase-0 declaration and ask one extra question: *does the change fit the declared size?* Spec-review is thereby folded in: the design is reviewed once, together with what it produced.

**Phase 5 — CLOSE.** `done --command fabrik-task` re-measures: the set of files changed since `declared.sha` (committed and working-tree) against `declared.files`, and every actual path against the sync regex. It writes `oversized_mini: {files_over: n, sync_hit: bool}` and `salami_suspect: <prior ts | none>` into the feedback row. D-row minted in the same commit if DECISION was one (its text is the six fields). CHANGELOG. Commit + push. FEEDBACK.

**UPGRADE — the one-way ratchet.** At any phase, a size input crossing — a fourth file, a sync path, a verb that must exist, a decision that turns one-way — is `command_run.py handoff --command fabrik-task --reason "UPGRADE: <test crossed>"`, and `/fabrik-spec` opens seeded with the phase-2 fields as its brief. Nothing downgrades mid-run.

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

1. touches a governance-sync path — a PUBLIC CONTRACT for ~46 repos? *(executable — the regex)* → **spec chain**
2. needs a new mechanism — a verb, flag, schema, hook, table, cron — a NEW ARCHITECTURAL COMPONENT? → **spec chain**
3. is the one decision ONE-WAY — structural, public, expensive to unwind? → **spec chain** (the Binding block lives there)
4. are there genuine TRADE-OFFS to adjudicate — more than one defensible approach? *(Google's test)* → **spec chain**; *no trade-offs and no decision at all — a pure fix* → **right-now + `/fabrik-review-scoped`** (exists today)
5. house heuristic, stated as one: more than 3 files? → **spec chain** (`Profile: small` then lightens execution). Grounding: 69% of the last 300 hub commits touch ≤3 non-ledger files; Google treats file count as a size multiplier and names no number; RFC 2904 says size is not the test. It is here because it is the one test the router and the operator can see before any work, never because the literature ranks it.
6. one reversible decision, statable in the six fields, ≤3 files, no sync path, no mechanism? → **`/fabrik-task`**

**Tripwire:** if the first draft cites a script's internals, re-run the test — either real mechanism work was found or the draft over-scoped, and the verdict says which.

This table lands in CLAUDE.md § Orient step 0 and its twin `templates/governance/CLAUDE.md` — the project copy carries D-098's third outcome (a synced-surface defect files upstream) ahead of these six.

## Awareness (I6, I10)

Two surfaces, both required:
1. **The step-0 routing table** in both CLAUDE.md copies — the six tests above, in the table agents already consult.
2. **`skill_router.py`** — a `STEM_SKILLS` entry `"task": "fabrik-task"` and a bilingual `KEYWORD_STEMS` row. The row must be intent-anchored: the file's own round-2 finding retired bare high-frequency words because *"the task is …"* and *"görev"* fire on ordinary prose. Candidate anchors: EN `(small|quick|one)[- ](change|fix|task) with (a|one) decision`, `decide and (fix|change)`, `fabrik[- ]task`; TR `küçük (değişiklik|görev)\w*`, `karar\w* (ver|al)\w* ve (düzelt|değiştir)\w*`. The exact regexes are tested in `tests/test_skill_router_hook.py` against its existing collision corpus before they ship. The command's own description carries a `TRIGGER` and a `SKIP` clause naming `/fabrik-spec`'s triggers, so the rendered corpus explains the choice at the point of invocation.

## Rejected alternatives

- **R1 — `Profile: mini` on `/fabrik-spec`.** Reuses the most, but still three invocations, and the profile mechanism already carries two variants. The lane's value is ONE record.
- **R2 — grow `/fabrik-review-scoped` with a design step.** Cheapest, but turns the light REVIEW pass into a build command and muddles the identity the Stop hook depends on.
- **R3 — a mini-spec FILE as the artifact.** Findable, but costs an allowlist entry, INDEX rows and gate checks; the D-row already carries what/why/where, is greppable, and is what the contract mandates for any decision. Operator chose the D-row (I16).
- **R4 — a new `size` verb in `command_run.py`.** `start --surface` already persists a surface; extending `start` with `--declare` and re-measuring in `_close` touches the same file with less new surface.
- **R5 — a new blocking enforcement check for sizing.** D-097 rejected exactly this shape on fire rate; the SIZE gate is a refusal in the agent's own tool on the agent's own declaration instead.
- **R6 — a per-round `--delta` threshold instead of a file count.** `--delta` exists for review sizing (D-229) and measures a fix, not a task; file count is what the router and the operator can see before any work.
- **R7 — no lane; sharpen the existing test's wording.** The test was right and was applied at the wrong moment; wording cannot fix WHEN.
- **R8 — Oxide's shape: one artifact, variable depth, judgement decides.** Grounded (RFD 1). Rejected here because our artifacts are graded by checkers that grep for fixed headings (`check_spec_convergence.py`, `check_convergence.py`), so "one artifact at variable depth" fights the gate instead of using it; and because the failure this spec answers was a JUDGEMENT failure — the depth was chosen wrong three times in one day — which is the case for an executable test, not for more judgement.

## Lifecycle

- **Adoption / first run:** the build ends with the DOGFOOD — the first `/fabrik-task` is run on a real candidate from the backtest, and the command is not declared done until that run closes.
- **Growth triggers, measured from the feedback ledger:** if over any 20 consecutive closes `oversized_mini` fires on >10%, the ≤3-file or the mechanism test is re-examined (a `/fabrik-command-improve` run on the queue this command accumulates); if the UPGRADE rate exceeds 30%, the decision rule is too permissive at the top and the table is tightened; if the median wall-clock exceeds 90 min, the lane has drifted heavy and phase 2 or 4 is the suspect.
- **The ratchet must not accrete process (DORA's vicious cycle):** an UPGRADE is a hand-off to the lane that already exists, never a new step added to this one; if UPGRADE rates rise, the response is to tighten the six tests at the top, not to add checks inside `/fabrik-task`.
- **Degradation:** if `command_run.py`'s re-measure cannot run (no git, no `declared.sha`), the close records `oversized_mini: unknown` — counted as an instrument gap, never bucketed as clean (the kaizen collector's own rule).
- **Retirement:** the lane is retired by removing the three router/table rows and the source; records already closed keep their fields.

## External dependencies

**1a — none.** This design is purely internal: no vendor, API, SDK, library, protocol or pricing is touched. Every fact above is grounded in this repo at `path:line` or measured from its ledgers this session.

**1c — approach grounding (live research, this session).** The design's core is a tiered change process with a reversibility-first sizing test and a one-way upgrade ratchet. Grounded live by a `fabrik-researcher` seat, 2026-09-17, each source fetched raw unless marked:

- **A published three-lane system for the identical gap — SUPPORTS the lane.** Rust's compiler team runs PR (light) / MCP (medium) / RFC (heavy): *"RFCs are… a heavy-weight proposal mechanism, reserved for significant changes… MCPs are… a medium-weight proposal mechanism, suitable for most proposals… PRs are… a light-weight proposal mechanism."* — https://forge.rust-lang.org/compiler/proposals-and-stabilization.html. Its founding RFC states the gap in our words: *"a channel for signaling intentions that lies somewhere between opening a PR… and creating a… design meeting proposal or RFC"*, to *"avoid the phenomenon of PRs living in limbo because it's not clear what level of approval is required."* — https://rust-lang.github.io/rfcs/2904-compiler-major-change-process.html.
- **The size test is NOT lines or files — CONTRADICTS a file count as the primary test.** RFC 2904: *"whether something is a major change proposal is not necessarily related to the number of lines of code that are affected. Renaming a method can affect a large number of lines… but it may not be a major change."* Google's design-doc guidance centres the decision on ambiguity and trade-offs: *"At the center of that decision lies whether the solution to the design problem is ambiguous"* and *"If a doc basically says 'This is how we are going to implement it' without going into trade-offs… it would probably have been a better idea to write the actual program right away."* — https://www.industrialempathy.com/posts/design-docs-at-google/. The tests the field publishes are cross-team reach, public contract, new architectural component, reversibility, and ambiguity (designdoc.tech, 2026-04-03: *"1. Does this affect more than one team?… 2. Is this hard to reverse?… 3. Does this introduce a new architectural component?… 5. Does this change a public contract?"* — https://designdoc.tech/blog/when-not-to-write-an-rfc). **Consequence for this spec:** the decision rule leads with those; the file count is a house heuristic, stated as one.
- **Reversibility is a member of every published test set, never ranked first — SUPPORTS it as mandatory, CONTRADICTS "reversibility first".** The concept itself is not grounded externally: `docs/reference/operating-manifesto.md:10-14` (Phase 0 triage) is this repo's authority on reversible-vs-one-way and the SIZE gate cites it directly. What the field adds is only the ranking: designdoc.tech lists cross-team first and reversibility second; RFC 2904 uses reversibility as a shortcut inside the process (*"The FCP can be skipped if the change is easily reversed"*), not as the classifier.
- **The ≤12-line design is Google's own mini doc — SUPPORTS phase 2.** *"it is absolutely possible to write a 1-3 page 'mini design doc'… you still do all the same steps as for a longer doc, just keep things more terse."* — industrialempathy.com, above.
- **Size guidance that exists names lines and treats files as a multiplier, with no file number — SILENT on "3".** Google eng-practices: *"100 lines is usually a reasonable size for a CL, and 1000 lines is usually too large… A 200-line change in one file might be okay, but spread across 50 files it would usually be too large."* — https://google.github.io/eng-practices/review/developer/small-cls.html. SmartBear/Cisco on review effectiveness: *"beyond 400 LOC, the ability to find defects diminishes."* — https://smartbear.com/learn/code-review/best-practices-for-peer-code-review/. DORA: *"working in small batches predicts software delivery performance"* with a TIME threshold (*"longer than a week… is too big"*) — https://dora.dev/capabilities/working-in-small-batches/.
- **The measured gaming shape is salami-slicing, and the counters are published — SUPPORTS the cobra section as amended.** *"There is an incentive to make RFCs as small as possible since the smaller the RFC is, the easier it is to get accepted… unfinished features where the initial work is done but follow-up work is not tracked."* — https://www.ncameron.org/blog/the-problem-with-rfcs/. Counters: reviewer-side upward bounce — *"If the approval required… requires an MCP or an RFC, then the contribution should be closed or marked as blocked, with a request to create an MCP or RFC first"*; and *"An earlier accepted MCP is not a substitute for any later necessary approvals."* — forge.rust-lang.org, above. DORA names the mirror cost of the lighter lane being skipped rather than gamed: *"Treating all changes equally… change review is inefficient, and people are unable to devote time and attention to those that require true concentration."* — dora.dev, below.
- **Uniform heavy process is the named pitfall; tiering is the recommendation; but an escalation path must not accrete process — SUPPORTS the lane, WARNS the ratchet.** DORA: *"Treating all changes equally. When all changes are subject to the same approval process, change review is inefficient"* and *"Responding to problems by adding more process… drives up lead times and batch sizes, creating a vicious cycle."* — https://dora.dev/capabilities/streamlining-change-approval/. designdoc.tech on the mirror risk: *"Once engineers view the RFC process as red tape, they stop engaging meaningfully with the RFCs that actually matter."*
- **The one-way ratchet has direct precedent — SUPPORTS.** The brainstorming skill this design was born in: *"The ratchet is one-way: hidden complexity discovered mid-task upgrades the path — stop, say so, and step up. Nothing downgrades mid-task."* — https://raw.githubusercontent.com/obra/superpowers/refs/heads/main/skills/brainstorming/SKILL.md; Rust: *"if the change proves more controversial or complex, we may escalate towards design meetings, longer write-ups, or full RFCs."* A DOWNGRADE path was found in none of the 4 process documents fetched — *not found in 4*, not "does not exist".
- **An alternative shape the field uses — RECORDED as R8.** Oxide scales depth inside ONE artifact rather than adding lanes: *"use your best judgement when it comes to the level of depth to devote to an RFD."* — https://rfd.shared.oxide.computer/rfd/0001.
- **Not verified this run, named as U5:** Sadowski et al. 2018's file-count distribution (*"over 35% of the changes… modify only a single file and about 90% modify fewer than 10 files"*, search-index text of https://doi.org/10.1145/3183519.3183525, PDF not opened); the DORA 2024 report's *"larger changes are slower and more prone to creating instability"* (PDF unreadable by both fetch arms); pandev-metrics' three-question matrix. None is load-bearing for a decision here.

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
- **C3 — manifesto.** ONE-WAY excluded (test 4); the cobra written in the command's docstring: the cheapest bypass is UNDER-DECLARING at phase 0 — the counter is the executable re-measure at close writing `oversized_mini` as a series, plus the review seats asked whether the change fits the declaration. The residual bypass the re-measure cannot see — declaring `mechanism=no` and adding a flag anyway — is named, not hidden; the seats' question is its only counter. **The SECOND cobra, and the one the literature measured (ncameron): SALAMI-SLICING — a spec-sized change cut into several mini tasks that each pass the gate.** Three counters, all published shapes: (a) phase 4's seats hold an UPGRADE verdict — *"this change requires the spec lane"* bounces the run to `handoff`, exactly as Rust closes a PR with *"a request to create an MCP or RFC first"*; (b) an accepted mini buys nothing later — its D-row is a record of one reversible decision and confers no approval on a follow-up (Rust: *"An earlier accepted MCP is not a substitute for any later necessary approvals"*); (c) `_close` writes the declared paths into the feedback row, so a `/fabrik-task` whose paths overlap a `/fabrik-task` closed within the previous 7 days is flagged `salami_suspect: <prior ts>` — a series, read like `oversized_mini`, never a block. What none of the three can see is a slice that touches disjoint paths for one design; that residual is named here and left to the operator's read of the D-rows.
- **C4 — infra.** Plan-locks by `owned_paths`; pool OFF (D-181/D-182); the sync regex read from the YAML; shared-append files by the private-index recipe.
- **C5 — rules.** `select_rules.py` + ACTIVE packs at phase 1; `review_rubric.py --changed` at phase 4.
- **C6 — no new enforcement check** (D-097); the refusal lives in the command's own tool.

## Cost

| file | change | synced? |
|---|---|---|
| `commands/_sources/fabrik-task.md` | NEW, ≤ 8,847 B | render only |
| `scripts/command_run.py` | `start --declare` + the phase-0 tests + `_close` re-measure + `oversized_mini` on the row | YES — heavy; full `/fabrik-review` on this phase |
| `.claude/hooks/skill_router.py` | `STEM_SKILLS` + `KEYWORD_STEMS` rows | YES |
| `CLAUDE.md` / `templates/governance/CLAUDE.md` | the six-test table in § Orient step 0 | template YES |
| `tests/test_command_run.py`, `tests/test_skill_router_hook.py` | graders, red-first | — |
| `docs/CAPABILITIES.md`, `docs/reference/command-run-protocol.md`, `INDEX.md`, `CHANGELOG.md`, `docs/DECISIONS.md` | rows | — |

Code files: 3 + 2 tests → the build runs `Profile: small` (D-169). By this spec's own rule the change is spec-lane work (tests 1, 2, 3 all trip) — the rule applied to its own first customer.

## Validation

**V1 — Backtest (I12).** Author-blind seats classify each of these 24 real closed runs (drawn 2026-09-17 from 185 done-with-surface rows across 18 commands, seed 17) with the six-test rule from the run's recorded surface, blind to the lane it took: `fabrik-spec` ×4 (ts 1788968234, 1789037133, 1788918241, 1789399457) · `fabrik-execute-plan` ×5 (1789504615, 1788799311, 1789097279, 1788870495, 1789659564) · `fabrik-review-scoped` ×7 (1789559500, 1789037347, 1789408498, 1789397165, 1788782386, 1789421498, 1789671545) · `fabrik-command-improve` ×4 (1789490961, 1789498211, 1789586054, 1789631997) · `fabrik-review` ×4 (1788816516, 1789213871, 1788820293, 1788825254). Report agreement with the lane actually taken and adjudicate every disagreement; a rule that disagrees with >30% of history is re-cut before the build.

**V2 — Dogfood (I11).** The first `/fabrik-task` run is on a real candidate V1 names as mini; the build is not done until that run closes with a converged review and a D-row.

**V3 — Cobra probe.** A seat attempts to route a known spec-sized task (one the backtest classed as spec) through `/fabrik-task` by under-declaring, and reports whether phase 0 refuses, phase 4's seats catch it, or phase 5's re-measure records it — and whether any path lets it through silently.

**V4 — Success metrics, read from the feedback ledger with no new machinery, over the first 20 closes:** median wall-clock ≤ 60 min (between the light lane's 32 and the chain's 85+); rounds-to-converge median ≤ 2; `oversized_mini` rate ≤ 10%. The UPGRADE rate is reported, not thresholded, for the first 20.

## Documentation landing sites

- `docs/reference/command-run-protocol.md` — the `--declare` extension and the `oversized_mini` field, beside the existing `--surface` text.
- `docs/CAPABILITIES.md` — the command's bullet.
- `INDEX.md` — the new source file's row.
- `CHANGELOG.md` — the build's entry.
- `docs/DECISIONS.md` — the rows in § Decisions taken.
- The command's own source is self-documenting for its phases; no dedicated reference doc is opened (it is a command, not a subsystem).

## Decisions taken (minted at CONVERGED)

- D-a — the three-lane rule and the moment it applies (before drafting, to the minimal discharge).
- D-b — `/fabrik-task` exists; the D-row is its durable artifact; ONE-WAY decisions are excluded.
- D-c — the ≤3-file threshold, grounded on the 69% measurement.
- D-d — the SIZE gate is a refusal in the agent's own tool, not an enforcement check (consistent with D-097).
- D-e — the cobra counter: re-measure at close, `oversized_mini` as a kaizen series.

## Open / blocking unknowns

- **U1 — RESOLVED by ruling here:** structured `--declare` versus free-text `--surface` — structured, because `_close` must parse it to re-measure.
- **U2 — OPEN, named resolution:** the exact `KEYWORD_STEMS` regexes. Resolved in the build by running the candidates against `tests/test_skill_router_hook.py`'s collision corpus; any anchor that fires on the corpus is cut.
- **U3 — OPEN, named resolution:** whether the backtest agreement clears 70%. Resolved by V1 before the build; below it, the rule is re-cut and this spec's § The decision rule is amended on its next non-delta pass.
- **U4 — RESOLVED:** the 1c approach grounding landed (§ External dependencies), and it re-cut the decision rule and the cobra section before self-review.
- **U5 — OPEN, named resolution:** three sources the seat could read only as search-index text (Sadowski 2018's file distribution, the DORA 2024 PDF, pandev's matrix). None decides anything here; `/fabrik-spec-review`'s researcher seats raw-fetch them (curl the PDFs) and either quote or delete them.

## Residual assumptions

- That `git rev-parse HEAD` at `start` is a usable baseline for the re-measure on a shared tree where siblings commit mid-run — the re-measure must diff by the agent's OWN paths (the declared set and the commit's own file list), never by "everything since the SHA".
- That a ≤ ~1,200-char step title is a tolerable home for the six fields; if it proves not to be, a `design` verb is the follow-up, not a reason to skip phase 2.
