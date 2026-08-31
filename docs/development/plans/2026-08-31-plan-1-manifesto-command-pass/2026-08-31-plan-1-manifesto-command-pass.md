# The commands/skills manifesto pass — evaluate + update all 32 commands against the Operating Manifesto

Status: IN-PROGRESS

Operator directive (2026-08-31, verbatim): "create a plan which will walk you through all commands/skills,
and you will evaluate and update each against docs/reference/operating-manifesto.md without stopping. one by
one. after evaluating each command you will run a /fabrik-review so at least 31 tickets." Authority:
D-043 (manifesto adopted) · D-044 (bound into governance; "The commands/skills corpus gets its own
manifesto pass next" recorded) · 52278be3 (the instrument: docs/reference/command-evaluation-checklist.md
§ Governance Chain item 63b — the six manifesto intersections, with "N/A because X" a valid verdict).
The corpus denominator is **32 command sources** (grounded live: `ls commands/_sources/*.md | wc -l` = 32),
so the operator's "at least 31 tickets" floor is met with 32 command tickets + T01 (fragments baseline)
+ T34 (Integration receipt) = **34 tickets**.

## Intake Inventory

| I# | Item (anchored) | Disposition | Where |
|---|---|---|---|
| I1 | "walk you through all commands/skills" | IN | T02–T33 — one ticket per source, all 32; T01 covers the 21 shared fragments the commands render from |
| I2 | "evaluate and update each against docs/reference/operating-manifesto.md" | IN | every ticket's Scope step 2–3 (the 63b six-intersection adjudication + minimal fixes) |
| I3 | "without stopping. one by one" | IN | serial Depends chain T01→T34 + § Execution Discipline (the three BLOCKED cases are the only halts) |
| I4 | "after evaluating each command you will run a /fabrik-review" | IN | every ticket's Scope step 4 + § Execution Discipline review floor + each ticket's second G/W/T row |
| I5 | "so at least 31 tickets" | IN | 34 tickets (32 ≥ 31 command tickets; the floor is exceeded because the real denominator is 32) |
| I6 | "i will do the same for our commands/skills too after claude.md" (prior turn) | IN | this plan IS that pass; the CLAUDE.md half shipped at D-044 |
| I7 | checklist 63b as the lens; "N/A because X" valid; no vocabulary injection (this turn's /fabrik-plan-after-chat args) | IN | § Global Constraints + every ticket's DO-NOT |

Intake: 7 items — 7 IN, 0 OUT-OF-SCOPE, 0 ASK.

## Global Constraints

- **The evaluation brief is FIXED — no re-scoping between tickets.** Every ticket adjudicates the SAME six
  63b intersections (docs/reference/command-evaluation-checklist.md § Governance Chain, item 63b): checkable
  gates · ledger routing + the one-way field block · rigor-scales-with-irreversibility · labeled
  verified/assumption evidence · captured disorder · most-reversible default. "N/A because X" is a valid
  verdict per intersection; forgetting to adjudicate one is not.
- **Do not inject manifesto vocabulary** into a command where an intersection is genuinely N/A — the verdict
  table is the deliverable; an edit needs a failing intersection.
- **Evaluate the RENDERED command** (`$HOME/.claude/commands/<cmd>.md`), fix the SOURCE
  (`commands/_sources/<cmd>.md`) — never the rendered wrapper (checklist § Evaluate the RENDERED command).
- **Do not re-litigate what `scripts/enforcement/check_command_corpus.py` gates** (checklist § Do not
  re-litigate): web_tools names · chain references · script paths · trailer match · run-record presence.
- **Fragment blast radius:** a fragment edit multiplies across every including command. T01 sweeps all 21
  fragments ONCE and is the ONLY ticket that owns `commands/_fragments/`; a later NEW fragment finding
  (expected rare) is an ORCHESTRATOR-APPLIED edit: the dispatching session applies it directly under the
  plan File Scope (the orchestrator is exempt from ticket-Touches collision by the gate's own carve-out),
  records it in the finding ticket's review artifact, and re-renders — never an in-ticket edit outside
  Touches, and NOT the D3 governance-Deltas block (whose fixed format covers only the five governance
  surfaces).
- **Render law:** `python commands/assemble_commands.py` (bare render) ONLY from the merged-master MAIN
  checkout — a worktree render PRUNES master-only artifacts box-wide (CLAUDE.md § Merge-time render);
  `--check` is safe anywhere. Execution runs in the MAIN checkout on master, serially, so the per-ticket
  post-commit render is sanctioned.
- **NO-POOL standing directive** (operator, this session): all work solo native + native finder subagents;
  every commit carries a `NO-POOL: standing operator directive` line (the form
  `scripts/enforcement/check_subagent_flywheel.py:7` reads).
- **Shared-tree git law:** explicit pathspecs + Agent Provenance Trailers per commit; `git reset -q HEAD --
  <paths>` after each scoped commit; push per ticket; NEVER --force, NEVER --amend.
- 12-Factor non-negotiables (inherited; this plan is docs/governance-only — no code, compose, deps, env or
  schema surface is in scope, so the axes bind by exclusion): logs stdout-only (XI) · no startup migrations
  (XII) · same backing services (X) · no sticky sessions (VI) · no daemonizing (VIII) · workers requeue on
  SIGTERM (IX) · releases immutable (V) · granular env config, no secrets in code (III) · shelled binaries
  pinned (II). A ticket that finds itself editing any such surface is out of scope — BLOCKED, not improvised.

## Constraints Digest

| Rule (verbatim) | Source |
|---|---|
| "No skipped heading levels — `##` to `###`, never `##` to `####`" | .windsurf/rules/core/40-documentation.md:197 |
| "Fenced code blocks only — never indented code (AI treats it inconsistently)" | .windsurf/rules/core/40-documentation.md:199 |
| "a `NO-POOL: <reason>` line in ANY in-cycle commit message (`base..HEAD`) or a `FABRIK_NO_POOL` env var" | scripts/enforcement/check_subagent_flywheel.py:7 |
| "Enforce every Part B agentic pattern the task touches — a multi-step / loop / tool-using prompt that omits the termination contract, evidence-before-assertion, or grounding is the usual failure." | docs/reference/MD/ai-prompt-templates.md:20 |
| "Distil, don't dump — a system prompt is the durable contract (~200–800 tokens)" | docs/reference/MD/ai-prompt-templates.md:296 |
| "Does it conform to the Operating Manifesto … Map the command onto the manifesto's shape and check the load-bearing intersections, not vocabulary" | docs/reference/command-evaluation-checklist.md § Governance Chain 63b |
| FLOOR packs (35-security-auth · 25-data-postgres · 30-ops) + 12-Factor: injected; this plan touches only `.md` governance surfaces — every code-shaped mandate binds by exclusion (see Global Constraints last bullet) | review_rubric.py run, Evidence block 2 |

## Ticket Board

| Ticket | Title | Depends | Parallel | State | Commit |
|---|---|---|---|---|---|
| T01 | Fragments manifesto baseline (all 21 shared fragments) | — | ⛓️ | ✅ | (this commit) |
| T02 | /design-review — 63b manifesto conformance + fixes + per-command review | T01 | ⛓️ | ✅ | (this commit) |
| T03 | /fabrik-catchup — 63b manifesto conformance + fixes + per-command review | T02 | ⛓️ | ✅ | (this commit) |
| T04 | /fabrik-conformance-review — 63b manifesto conformance + fixes + per-command review | T03 | ⛓️ | ✅ | (this commit) |
| T05 | /fabrik-data-contract — 63b manifesto conformance + fixes + per-command review | T04 | ⛓️ | ✅ | (this commit) |
| T06 | /fabrik-decommission — 63b manifesto conformance + fixes + per-command review | T05 | ⛓️ | ✅ | (this commit) |
| T07 | /fabrik-deploy — 63b manifesto conformance + fixes + per-command review | T06 | ⛓️ | ✅ | (this commit) |
| T08 | /fabrik-deploy-plan — 63b manifesto conformance + fixes + per-command review | T07 | ⛓️ | ✅ | (this commit) |
| T09 | /fabrik-deploy-plan-review — 63b manifesto conformance + fixes + per-command review | T08 | ⛓️ | ✅ | (this commit; incl. the sanctioned T07 back-flip fixup) |
| T10 | /fabrik-deploy-verify — 63b manifesto conformance + fixes + per-command review | T09 | ⛓️ | ✅ | (this commit) |
| T11 | /fabrik-doc-converge — 63b manifesto conformance + fixes + per-command review | T10 | ⛓️ | ✅ | (this commit) |
| T12 | /fabrik-docs-review — 63b manifesto conformance + fixes + per-command review | T11 | ⛓️ | ✅ | (this commit) |
| T13 | /fabrik-execute-plan — 63b manifesto conformance + fixes + per-command review | T12 | ⛓️ | ✅ | (this commit) |
| T14 | /fabrik-features — 63b manifesto conformance + fixes + per-command review | T13 | ⛓️ | ✅ | (this commit) |
| T15 | /fabrik-flows — 63b manifesto conformance + fixes + per-command review | T14 | ⛓️ | ✅ | (this commit) |
| T16 | /fabrik-flows-review — 63b manifesto conformance + fixes + per-command review | T15 | ⛓️ | ✅ | (this commit) |
| T17 | /fabrik-generate-tests — 63b manifesto conformance + fixes + per-command review | T16 | ⛓️ | ✅ | (this commit) |
| T18 | /fabrik-plan-after-chat — 63b manifesto conformance + fixes + per-command review | T17 | ⛓️ | ✅ | (this commit) |
| T19 | /fabrik-plan-review — 63b manifesto conformance + fixes + per-command review | T18 | ⛓️ | ✅ | (this commit) |
| T20 | /fabrik-release — 63b manifesto conformance + fixes + per-command review | T19 | ⛓️ | ✅ | (this commit) |
| T21 | /fabrik-repo-review — 63b manifesto conformance + fixes + per-command review | T20 | ⛓️ | ✅ | (this commit) |
| T22 | /fabrik-review — 63b manifesto conformance + fixes + per-command review | T21 | ⛓️ | ✅ | (this commit) |
| T23 | /fabrik-review-scoped — 63b manifesto conformance + fixes + per-command review | T22 | ⛓️ | ✅ | (this commit) |
| T24 | /fabrik-rivals — 63b manifesto conformance + fixes + per-command review | T23 | ⛓️ | ✅ | (this commit) |
| T25 | /fabrik-rules-review — 63b manifesto conformance + fixes + per-command review | T24 | ⛓️ | ✅ | (this commit) |
| T26 | /fabrik-service-test — 63b manifesto conformance + fixes + per-command review | T25 | ⛓️ | ⬜ | |
| T27 | /fabrik-spec — 63b manifesto conformance + fixes + per-command review | T26 | ⛓️ | ⬜ | |
| T28 | /fabrik-spec-review — 63b manifesto conformance + fixes + per-command review | T27 | ⛓️ | ⬜ | |
| T29 | /fabrik-ui-design — 63b manifesto conformance + fixes + per-command review | T28 | ⛓️ | ⬜ | |
| T30 | /fabrik-ui-design-review — 63b manifesto conformance + fixes + per-command review | T29 | ⛓️ | ⬜ | |
| T31 | /fabrik-upstream — 63b manifesto conformance + fixes + per-command review | T30 | ⛓️ | ⬜ | |
| T32 | /fabrik-user-test — 63b manifesto conformance + fixes + per-command review | T31 | ⛓️ | ⬜ | |
| T33 | /fabrik-workflow-review — 63b manifesto conformance + fixes + per-command review | T32 | ⛓️ | ⬜ | |
| T34 | Integration — whole-plan receipt, gates, docs convergence | T33 | ⛓️ | ⬜ | |

## Merge Order

1. T01
2. T02
3. T03
4. T04
5. T05
6. T06
7. T07
8. T08
9. T09
10. T10
11. T11
12. T12
13. T13
14. T14
15. T15
16. T16
17. T17
18. T18
19. T19
20. T20
21. T21
22. T22
23. T23
24. T24
25. T25
26. T26
27. T27
28. T28
29. T29
30. T30
31. T31
32. T32
33. T33
34. T34


## Interfaces

- **T01 produces** the fragment-level 63b verdict ledger (its review artifact) — **every command ticket
  consumes it** as the swept-classes reference deciding "verify-only vs new fragment finding". Seam test:
  the CONSUMER ticket's `python commands/assemble_commands.py --check` green run over the post-T01 corpus
  (each command ticket's Gate line — the render-sync check proves fragments and sources still compose).
- **T02–T33 produce** per-command 63b verdict tables + fixed sources — **T34 consumes** all of them (the
  receipt enumerates 32/32 + fragments). Seam test: T34's `python scripts/final_gate.py --check --json`
  over the merged corpus (in T34's Touches artifact).

## Execution Discipline (binding on /fabrik-execute-plan)

- **Review floor** — every ticket, on completion of its evaluation+fixes, runs `/fabrik-review` on its
  changed surface to a coverage-adjudicated exit (every class CLEAN/FIXED/REFUTED, a full fresh round
  returning new: 0) BEFORE its merge and its Board flip; no ticket merges on a first-pass green. The
  review artifact lives at the ticket's mandated stem-named path (in its Touches). A ticket whose
  evaluation changed NOTHING (all six intersections CONFORM or N/A) still writes the verdict table and
  runs a scoped verification review over the artifact — the honest no-change outcome is recorded, never
  skipped.
- **Dispatch policy** — NO-POOL standing operator directive: the dispatching session executes each ticket
  natively, one by one, in THIS repo's MAIN checkout on master (no worktrees — the corpus render law and
  the serial chain make isolation pointless); native fabrik-reviewer subagents serve as the review
  finders. The pool is not used; every commit declares `NO-POOL:` so check_subagent_flywheel reads the
  waiver. Zero flywheel rows is the declared, waived outcome.
- **Parallelism + merge** — NONE, by operator directive ("without stopping. one by one"): a strict serial
  chain T01→T34 (Depends edges; `commands/_fragments/` has a single Touches owner — T01 — so no
  Serialized row is needed or present). There is no fan-out and
  therefore no merge/dedupe point; each ticket commits+pushes its own surface before the next begins.
  "Without stopping" means: the ONLY sanctioned halts between tickets are the three BLOCKED cases
  (3 consecutive same-test failures · missing infra · unresolvable spec contradiction); context length is
  never a reason (the harness auto-compacts; durable state lives in the Board + review artifacts).
- **Self-reference law (the pass edits commands the pass itself runs).** The ORCHESTRATING contract
  (`/fabrik-execute-plan`, as rendered at run start) is FROZEN for the whole run: T13's fixes to its
  source take effect for FUTURE runs and never re-bind the in-flight orchestration. Likewise each
  ticket's `/fabrik-review` binds to the contract AS RENDERED at that ticket's invocation — earlier
  tickets' converged reviews are NOT re-run under later contracts (mid-pass contract drift is the
  point of the pass, each review was valid under the contract in force at its commit, which pins the
  corpus sha). T34's receipt records this law was applied, not retro-fitted.
- **Resume-render law.** On ANY resume after a halt (BLOCKED or session death), the FIRST act is
  `python commands/assemble_commands.py --check`; if out of sync, render from the master MAIN
  checkout before touching the next ticket — a halt between push and render leaves the live corpus
  stale, most acutely after T01.

## Context Ledger

| Source | What binds | Grounded ref |
|---|---|---|
| .windsurf/rules/core/40-documentation.md (MATCHED — rubric run in Evidence) | markdown discipline on every .md this plan edits | :197 no skipped headings · :199 fenced blocks only |
| .windsurf/rules/core/62-using-subagents.md (judgment read) | dispatch policy + the NO-POOL waiver form | § Dispatch policy; waiver form at scripts/enforcement/check_subagent_flywheel.py:7 |
| docs/reference/MD/ai-prompt-templates.md (Pointers-mandated for command authoring) | every fix to a command is prompt-authoring — Part B patterns bind; distil, don't dump | :20 Part B enforcement · :296 distil |
| docs/reference/operating-manifesto.md (canonical, D-043/D-044) | the evaluation TARGET — six intersections via 63b | :12 Phase-0 triage · :27 Phase-1 gate · :85-89 invariants · :93 § Binding |
| docs/reference/command-evaluation-checklist.md (the instrument, 52278be3) | 63b + the checklist's own laws (rendered-not-source, no re-litigation, N/A-valid) | § Governance Chain 63b · § Do not re-litigate · § Evaluate the RENDERED command |
| CLAUDE.md § Merge-time render + § shared-repo law | render only from master MAIN; pathspec/trailer/push discipline | CLAUDE.md § Behavior (Merge-time render only) |
| scripts/enforcement/check_command_corpus.py (gate, Tier-2) | the five mechanically-decided facts no ticket re-derives | checklist § Do not re-litigate |
| fabrik-lib consult | NO new capability is built — this plan edits governance prose only; nothing to vendor | fabrik-lib/README.md checked: no module owns command-corpus evaluation; not applicable — no build |

## File Scope (owned paths)

- commands/_sources/
- commands/_fragments/
- docs/development/plans/2026-08-31-plan-1-manifesto-command-pass/
- docs/development/reviews/2026-08-31-plan-1-manifesto-command-pass-T01-fragments-baseline-review.md
- docs/development/reviews/2026-08-31-plan-1-manifesto-command-pass-T02-design-review-review.md
- docs/development/reviews/2026-08-31-plan-1-manifesto-command-pass-T03-fabrik-catchup-review.md
- docs/development/reviews/2026-08-31-plan-1-manifesto-command-pass-T04-fabrik-conformance-review-review.md
- docs/development/reviews/2026-08-31-plan-1-manifesto-command-pass-T05-fabrik-data-contract-review.md
- docs/development/reviews/2026-08-31-plan-1-manifesto-command-pass-T06-fabrik-decommission-review.md
- docs/development/reviews/2026-08-31-plan-1-manifesto-command-pass-T07-fabrik-deploy-review.md
- docs/development/reviews/2026-08-31-plan-1-manifesto-command-pass-T08-fabrik-deploy-plan-review.md
- docs/development/reviews/2026-08-31-plan-1-manifesto-command-pass-T09-fabrik-deploy-plan-review-review.md
- docs/development/reviews/2026-08-31-plan-1-manifesto-command-pass-T10-fabrik-deploy-verify-review.md
- docs/development/reviews/2026-08-31-plan-1-manifesto-command-pass-T11-fabrik-doc-converge-review.md
- docs/development/reviews/2026-08-31-plan-1-manifesto-command-pass-T12-fabrik-docs-review-review.md
- docs/development/reviews/2026-08-31-plan-1-manifesto-command-pass-T13-fabrik-execute-plan-review.md
- docs/development/reviews/2026-08-31-plan-1-manifesto-command-pass-T14-fabrik-features-review.md
- docs/development/reviews/2026-08-31-plan-1-manifesto-command-pass-T15-fabrik-flows-review.md
- docs/development/reviews/2026-08-31-plan-1-manifesto-command-pass-T16-fabrik-flows-review-review.md
- docs/development/reviews/2026-08-31-plan-1-manifesto-command-pass-T17-fabrik-generate-tests-review.md
- docs/development/reviews/2026-08-31-plan-1-manifesto-command-pass-T18-fabrik-plan-after-chat-review.md
- docs/development/reviews/2026-08-31-plan-1-manifesto-command-pass-T19-fabrik-plan-review-review.md
- docs/development/reviews/2026-08-31-plan-1-manifesto-command-pass-T20-fabrik-release-review.md
- docs/development/reviews/2026-08-31-plan-1-manifesto-command-pass-T21-fabrik-repo-review-review.md
- docs/development/reviews/2026-08-31-plan-1-manifesto-command-pass-T22-fabrik-review-review.md
- docs/development/reviews/2026-08-31-plan-1-manifesto-command-pass-T23-fabrik-review-scoped-review.md
- docs/development/reviews/2026-08-31-plan-1-manifesto-command-pass-T24-fabrik-rivals-review.md
- docs/development/reviews/2026-08-31-plan-1-manifesto-command-pass-T25-fabrik-rules-review-review.md
- docs/development/reviews/2026-08-31-plan-1-manifesto-command-pass-T26-fabrik-service-test-review.md
- docs/development/reviews/2026-08-31-plan-1-manifesto-command-pass-T27-fabrik-spec-review.md
- docs/development/reviews/2026-08-31-plan-1-manifesto-command-pass-T28-fabrik-spec-review-review.md
- docs/development/reviews/2026-08-31-plan-1-manifesto-command-pass-T29-fabrik-ui-design-review.md
- docs/development/reviews/2026-08-31-plan-1-manifesto-command-pass-T30-fabrik-ui-design-review-review.md
- docs/development/reviews/2026-08-31-plan-1-manifesto-command-pass-T31-fabrik-upstream-review.md
- docs/development/reviews/2026-08-31-plan-1-manifesto-command-pass-T32-fabrik-user-test-review.md
- docs/development/reviews/2026-08-31-plan-1-manifesto-command-pass-T33-fabrik-workflow-review-review.md
- docs/development/reviews/2026-08-31-plan-1-manifesto-command-pass-review.md

## Behavior Contract

- **Given** all 21 fragment files under `commands/_fragments/`, **When** each is evaluated against checklist item 63b's six intersections, **Then** a per-fragment verdict table (CONFORMS/FIXED/N-A per intersection) lands in the ticket's review artifact with 21/21 fragments adjudicated (commands/_fragments/run-record.md:1)
- **Given** fragment fixes applied, **When** /fabrik-review runs on the changed fragments and `python commands/assemble_commands.py --check` runs, **Then** the review converges to new: 0 and the check is green — fragment-level manifesto classes are SWEPT so command tickets verify-only (docs/reference/operating-manifesto.md:93)
- **Given** the rendered command at the box path named in Scope and its source `commands/_sources/design-review.md`, **When** it is evaluated against checklist item 63b's six intersections (docs/reference/command-evaluation-checklist.md § Governance Chain), **Then** the ticket's review artifact records a written verdict per intersection — CONFORMS at path:line · FIXED at path:line · N/A because X — with zero unadjudicated intersections (commands/_sources/design-review.md:3)
- **Given** fixes applied to `commands/_sources/design-review.md` (any NEW fragment-level finding applied by the orchestrator under the plan File Scope and recorded in this ticket's review artifact) — OR the honest all-CONFORM/no-change outcome, which still writes the verdict table and runs a scoped verification review over it, **When** /fabrik-review runs on the ticket's changed surface, **Then** it converges to a new: 0 round with every finding FIXED or REFUTED, `python commands/assemble_commands.py --check` is green, and the ticket's commit is pushed (docs/reference/operating-manifesto.md:4)
- **Given** the rendered command at the box path named in Scope and its source `commands/_sources/fabrik-catchup.md`, **When** it is evaluated against checklist item 63b's six intersections (docs/reference/command-evaluation-checklist.md § Governance Chain), **Then** the ticket's review artifact records a written verdict per intersection — CONFORMS at path:line · FIXED at path:line · N/A because X — with zero unadjudicated intersections (commands/_sources/fabrik-catchup.md:2)
- **Given** fixes applied to `commands/_sources/fabrik-catchup.md` (any NEW fragment-level finding applied by the orchestrator under the plan File Scope and recorded in this ticket's review artifact) — OR the honest all-CONFORM/no-change outcome, which still writes the verdict table and runs a scoped verification review over it, **When** /fabrik-review runs on the ticket's changed surface, **Then** it converges to a new: 0 round with every finding FIXED or REFUTED, `python commands/assemble_commands.py --check` is green, and the ticket's commit is pushed (docs/reference/operating-manifesto.md:4)
- **Given** the rendered command at the box path named in Scope and its source `commands/_sources/fabrik-conformance-review.md`, **When** it is evaluated against checklist item 63b's six intersections (docs/reference/command-evaluation-checklist.md § Governance Chain), **Then** the ticket's review artifact records a written verdict per intersection — CONFORMS at path:line · FIXED at path:line · N/A because X — with zero unadjudicated intersections (commands/_sources/fabrik-conformance-review.md:2)
- **Given** fixes applied to `commands/_sources/fabrik-conformance-review.md` (any NEW fragment-level finding applied by the orchestrator under the plan File Scope and recorded in this ticket's review artifact) — OR the honest all-CONFORM/no-change outcome, which still writes the verdict table and runs a scoped verification review over it, **When** /fabrik-review runs on the ticket's changed surface, **Then** it converges to a new: 0 round with every finding FIXED or REFUTED, `python commands/assemble_commands.py --check` is green, and the ticket's commit is pushed (docs/reference/operating-manifesto.md:4)
- **Given** the rendered command at the box path named in Scope and its source `commands/_sources/fabrik-data-contract.md`, **When** it is evaluated against checklist item 63b's six intersections (docs/reference/command-evaluation-checklist.md § Governance Chain), **Then** the ticket's review artifact records a written verdict per intersection — CONFORMS at path:line · FIXED at path:line · N/A because X — with zero unadjudicated intersections (commands/_sources/fabrik-data-contract.md:2)
- **Given** fixes applied to `commands/_sources/fabrik-data-contract.md` (any NEW fragment-level finding applied by the orchestrator under the plan File Scope and recorded in this ticket's review artifact) — OR the honest all-CONFORM/no-change outcome, which still writes the verdict table and runs a scoped verification review over it, **When** /fabrik-review runs on the ticket's changed surface, **Then** it converges to a new: 0 round with every finding FIXED or REFUTED, `python commands/assemble_commands.py --check` is green, and the ticket's commit is pushed (docs/reference/operating-manifesto.md:4)
- **Given** the rendered command at the box path named in Scope and its source `commands/_sources/fabrik-decommission.md`, **When** it is evaluated against checklist item 63b's six intersections (docs/reference/command-evaluation-checklist.md § Governance Chain), **Then** the ticket's review artifact records a written verdict per intersection — CONFORMS at path:line · FIXED at path:line · N/A because X — with zero unadjudicated intersections (commands/_sources/fabrik-decommission.md:2)
- **Given** fixes applied to `commands/_sources/fabrik-decommission.md` (any NEW fragment-level finding applied by the orchestrator under the plan File Scope and recorded in this ticket's review artifact) — OR the honest all-CONFORM/no-change outcome, which still writes the verdict table and runs a scoped verification review over it, **When** /fabrik-review runs on the ticket's changed surface, **Then** it converges to a new: 0 round with every finding FIXED or REFUTED, `python commands/assemble_commands.py --check` is green, and the ticket's commit is pushed (docs/reference/operating-manifesto.md:4)
- **Given** the rendered command at the box path named in Scope and its source `commands/_sources/fabrik-deploy.md`, **When** it is evaluated against checklist item 63b's six intersections (docs/reference/command-evaluation-checklist.md § Governance Chain), **Then** the ticket's review artifact records a written verdict per intersection — CONFORMS at path:line · FIXED at path:line · N/A because X — with zero unadjudicated intersections (commands/_sources/fabrik-deploy.md:2)
- **Given** fixes applied to `commands/_sources/fabrik-deploy.md` (any NEW fragment-level finding applied by the orchestrator under the plan File Scope and recorded in this ticket's review artifact) — OR the honest all-CONFORM/no-change outcome, which still writes the verdict table and runs a scoped verification review over it, **When** /fabrik-review runs on the ticket's changed surface, **Then** it converges to a new: 0 round with every finding FIXED or REFUTED, `python commands/assemble_commands.py --check` is green, and the ticket's commit is pushed (docs/reference/operating-manifesto.md:4)
- **Given** the rendered command at the box path named in Scope and its source `commands/_sources/fabrik-deploy-plan.md`, **When** it is evaluated against checklist item 63b's six intersections (docs/reference/command-evaluation-checklist.md § Governance Chain), **Then** the ticket's review artifact records a written verdict per intersection — CONFORMS at path:line · FIXED at path:line · N/A because X — with zero unadjudicated intersections (commands/_sources/fabrik-deploy-plan.md:2)
- **Given** fixes applied to `commands/_sources/fabrik-deploy-plan.md` (any NEW fragment-level finding applied by the orchestrator under the plan File Scope and recorded in this ticket's review artifact) — OR the honest all-CONFORM/no-change outcome, which still writes the verdict table and runs a scoped verification review over it, **When** /fabrik-review runs on the ticket's changed surface, **Then** it converges to a new: 0 round with every finding FIXED or REFUTED, `python commands/assemble_commands.py --check` is green, and the ticket's commit is pushed (docs/reference/operating-manifesto.md:4)
- **Given** the rendered command at the box path named in Scope and its source `commands/_sources/fabrik-deploy-plan-review.md`, **When** it is evaluated against checklist item 63b's six intersections (docs/reference/command-evaluation-checklist.md § Governance Chain), **Then** the ticket's review artifact records a written verdict per intersection — CONFORMS at path:line · FIXED at path:line · N/A because X — with zero unadjudicated intersections (commands/_sources/fabrik-deploy-plan-review.md:2)
- **Given** fixes applied to `commands/_sources/fabrik-deploy-plan-review.md` (any NEW fragment-level finding applied by the orchestrator under the plan File Scope and recorded in this ticket's review artifact) — OR the honest all-CONFORM/no-change outcome, which still writes the verdict table and runs a scoped verification review over it, **When** /fabrik-review runs on the ticket's changed surface, **Then** it converges to a new: 0 round with every finding FIXED or REFUTED, `python commands/assemble_commands.py --check` is green, and the ticket's commit is pushed (docs/reference/operating-manifesto.md:4)
- **Given** the rendered command at the box path named in Scope and its source `commands/_sources/fabrik-deploy-verify.md`, **When** it is evaluated against checklist item 63b's six intersections (docs/reference/command-evaluation-checklist.md § Governance Chain), **Then** the ticket's review artifact records a written verdict per intersection — CONFORMS at path:line · FIXED at path:line · N/A because X — with zero unadjudicated intersections (commands/_sources/fabrik-deploy-verify.md:2)
- **Given** fixes applied to `commands/_sources/fabrik-deploy-verify.md` (any NEW fragment-level finding applied by the orchestrator under the plan File Scope and recorded in this ticket's review artifact) — OR the honest all-CONFORM/no-change outcome, which still writes the verdict table and runs a scoped verification review over it, **When** /fabrik-review runs on the ticket's changed surface, **Then** it converges to a new: 0 round with every finding FIXED or REFUTED, `python commands/assemble_commands.py --check` is green, and the ticket's commit is pushed (docs/reference/operating-manifesto.md:4)
- **Given** the rendered command at the box path named in Scope and its source `commands/_sources/fabrik-doc-converge.md`, **When** it is evaluated against checklist item 63b's six intersections (docs/reference/command-evaluation-checklist.md § Governance Chain), **Then** the ticket's review artifact records a written verdict per intersection — CONFORMS at path:line · FIXED at path:line · N/A because X — with zero unadjudicated intersections (commands/_sources/fabrik-doc-converge.md:2)
- **Given** fixes applied to `commands/_sources/fabrik-doc-converge.md` (any NEW fragment-level finding applied by the orchestrator under the plan File Scope and recorded in this ticket's review artifact) — OR the honest all-CONFORM/no-change outcome, which still writes the verdict table and runs a scoped verification review over it, **When** /fabrik-review runs on the ticket's changed surface, **Then** it converges to a new: 0 round with every finding FIXED or REFUTED, `python commands/assemble_commands.py --check` is green, and the ticket's commit is pushed (docs/reference/operating-manifesto.md:4)
- **Given** the rendered command at the box path named in Scope and its source `commands/_sources/fabrik-docs-review.md`, **When** it is evaluated against checklist item 63b's six intersections (docs/reference/command-evaluation-checklist.md § Governance Chain), **Then** the ticket's review artifact records a written verdict per intersection — CONFORMS at path:line · FIXED at path:line · N/A because X — with zero unadjudicated intersections (commands/_sources/fabrik-docs-review.md:2)
- **Given** fixes applied to `commands/_sources/fabrik-docs-review.md` (any NEW fragment-level finding applied by the orchestrator under the plan File Scope and recorded in this ticket's review artifact) — OR the honest all-CONFORM/no-change outcome, which still writes the verdict table and runs a scoped verification review over it, **When** /fabrik-review runs on the ticket's changed surface, **Then** it converges to a new: 0 round with every finding FIXED or REFUTED, `python commands/assemble_commands.py --check` is green, and the ticket's commit is pushed (docs/reference/operating-manifesto.md:4)
- **Given** the rendered command at the box path named in Scope and its source `commands/_sources/fabrik-execute-plan.md`, **When** it is evaluated against checklist item 63b's six intersections (docs/reference/command-evaluation-checklist.md § Governance Chain), **Then** the ticket's review artifact records a written verdict per intersection — CONFORMS at path:line · FIXED at path:line · N/A because X — with zero unadjudicated intersections (commands/_sources/fabrik-execute-plan.md:2)
- **Given** fixes applied to `commands/_sources/fabrik-execute-plan.md` (any NEW fragment-level finding applied by the orchestrator under the plan File Scope and recorded in this ticket's review artifact) — OR the honest all-CONFORM/no-change outcome, which still writes the verdict table and runs a scoped verification review over it, **When** /fabrik-review runs on the ticket's changed surface, **Then** it converges to a new: 0 round with every finding FIXED or REFUTED, `python commands/assemble_commands.py --check` is green, and the ticket's commit is pushed (docs/reference/operating-manifesto.md:4)
- **Given** the rendered command at the box path named in Scope and its source `commands/_sources/fabrik-features.md`, **When** it is evaluated against checklist item 63b's six intersections (docs/reference/command-evaluation-checklist.md § Governance Chain), **Then** the ticket's review artifact records a written verdict per intersection — CONFORMS at path:line · FIXED at path:line · N/A because X — with zero unadjudicated intersections (commands/_sources/fabrik-features.md:2)
- **Given** fixes applied to `commands/_sources/fabrik-features.md` (any NEW fragment-level finding applied by the orchestrator under the plan File Scope and recorded in this ticket's review artifact) — OR the honest all-CONFORM/no-change outcome, which still writes the verdict table and runs a scoped verification review over it, **When** /fabrik-review runs on the ticket's changed surface, **Then** it converges to a new: 0 round with every finding FIXED or REFUTED, `python commands/assemble_commands.py --check` is green, and the ticket's commit is pushed (docs/reference/operating-manifesto.md:4)
- **Given** the rendered command at the box path named in Scope and its source `commands/_sources/fabrik-flows.md`, **When** it is evaluated against checklist item 63b's six intersections (docs/reference/command-evaluation-checklist.md § Governance Chain), **Then** the ticket's review artifact records a written verdict per intersection — CONFORMS at path:line · FIXED at path:line · N/A because X — with zero unadjudicated intersections (commands/_sources/fabrik-flows.md:2)
- **Given** fixes applied to `commands/_sources/fabrik-flows.md` (any NEW fragment-level finding applied by the orchestrator under the plan File Scope and recorded in this ticket's review artifact) — OR the honest all-CONFORM/no-change outcome, which still writes the verdict table and runs a scoped verification review over it, **When** /fabrik-review runs on the ticket's changed surface, **Then** it converges to a new: 0 round with every finding FIXED or REFUTED, `python commands/assemble_commands.py --check` is green, and the ticket's commit is pushed (docs/reference/operating-manifesto.md:4)
- **Given** the rendered command at the box path named in Scope and its source `commands/_sources/fabrik-flows-review.md`, **When** it is evaluated against checklist item 63b's six intersections (docs/reference/command-evaluation-checklist.md § Governance Chain), **Then** the ticket's review artifact records a written verdict per intersection — CONFORMS at path:line · FIXED at path:line · N/A because X — with zero unadjudicated intersections (commands/_sources/fabrik-flows-review.md:2)
- **Given** fixes applied to `commands/_sources/fabrik-flows-review.md` (any NEW fragment-level finding applied by the orchestrator under the plan File Scope and recorded in this ticket's review artifact) — OR the honest all-CONFORM/no-change outcome, which still writes the verdict table and runs a scoped verification review over it, **When** /fabrik-review runs on the ticket's changed surface, **Then** it converges to a new: 0 round with every finding FIXED or REFUTED, `python commands/assemble_commands.py --check` is green, and the ticket's commit is pushed (docs/reference/operating-manifesto.md:4)
- **Given** the rendered command at the box path named in Scope and its source `commands/_sources/fabrik-generate-tests.md`, **When** it is evaluated against checklist item 63b's six intersections (docs/reference/command-evaluation-checklist.md § Governance Chain), **Then** the ticket's review artifact records a written verdict per intersection — CONFORMS at path:line · FIXED at path:line · N/A because X — with zero unadjudicated intersections (commands/_sources/fabrik-generate-tests.md:2)
- **Given** fixes applied to `commands/_sources/fabrik-generate-tests.md` (any NEW fragment-level finding applied by the orchestrator under the plan File Scope and recorded in this ticket's review artifact) — OR the honest all-CONFORM/no-change outcome, which still writes the verdict table and runs a scoped verification review over it, **When** /fabrik-review runs on the ticket's changed surface, **Then** it converges to a new: 0 round with every finding FIXED or REFUTED, `python commands/assemble_commands.py --check` is green, and the ticket's commit is pushed (docs/reference/operating-manifesto.md:4)
- **Given** the rendered command at the box path named in Scope and its source `commands/_sources/fabrik-plan-after-chat.md`, **When** it is evaluated against checklist item 63b's six intersections (docs/reference/command-evaluation-checklist.md § Governance Chain), **Then** the ticket's review artifact records a written verdict per intersection — CONFORMS at path:line · FIXED at path:line · N/A because X — with zero unadjudicated intersections (commands/_sources/fabrik-plan-after-chat.md:2)
- **Given** fixes applied to `commands/_sources/fabrik-plan-after-chat.md` (any NEW fragment-level finding applied by the orchestrator under the plan File Scope and recorded in this ticket's review artifact) — OR the honest all-CONFORM/no-change outcome, which still writes the verdict table and runs a scoped verification review over it, **When** /fabrik-review runs on the ticket's changed surface, **Then** it converges to a new: 0 round with every finding FIXED or REFUTED, `python commands/assemble_commands.py --check` is green, and the ticket's commit is pushed (docs/reference/operating-manifesto.md:4)
- **Given** the rendered command at the box path named in Scope and its source `commands/_sources/fabrik-plan-review.md`, **When** it is evaluated against checklist item 63b's six intersections (docs/reference/command-evaluation-checklist.md § Governance Chain), **Then** the ticket's review artifact records a written verdict per intersection — CONFORMS at path:line · FIXED at path:line · N/A because X — with zero unadjudicated intersections (commands/_sources/fabrik-plan-review.md:2)
- **Given** fixes applied to `commands/_sources/fabrik-plan-review.md` (any NEW fragment-level finding applied by the orchestrator under the plan File Scope and recorded in this ticket's review artifact) — OR the honest all-CONFORM/no-change outcome, which still writes the verdict table and runs a scoped verification review over it, **When** /fabrik-review runs on the ticket's changed surface, **Then** it converges to a new: 0 round with every finding FIXED or REFUTED, `python commands/assemble_commands.py --check` is green, and the ticket's commit is pushed (docs/reference/operating-manifesto.md:4)
- **Given** the rendered command at the box path named in Scope and its source `commands/_sources/fabrik-release.md`, **When** it is evaluated against checklist item 63b's six intersections (docs/reference/command-evaluation-checklist.md § Governance Chain), **Then** the ticket's review artifact records a written verdict per intersection — CONFORMS at path:line · FIXED at path:line · N/A because X — with zero unadjudicated intersections (commands/_sources/fabrik-release.md:2)
- **Given** fixes applied to `commands/_sources/fabrik-release.md` (any NEW fragment-level finding applied by the orchestrator under the plan File Scope and recorded in this ticket's review artifact) — OR the honest all-CONFORM/no-change outcome, which still writes the verdict table and runs a scoped verification review over it, **When** /fabrik-review runs on the ticket's changed surface, **Then** it converges to a new: 0 round with every finding FIXED or REFUTED, `python commands/assemble_commands.py --check` is green, and the ticket's commit is pushed (docs/reference/operating-manifesto.md:4)
- **Given** the rendered command at the box path named in Scope and its source `commands/_sources/fabrik-repo-review.md`, **When** it is evaluated against checklist item 63b's six intersections (docs/reference/command-evaluation-checklist.md § Governance Chain), **Then** the ticket's review artifact records a written verdict per intersection — CONFORMS at path:line · FIXED at path:line · N/A because X — with zero unadjudicated intersections (commands/_sources/fabrik-repo-review.md:2)
- **Given** fixes applied to `commands/_sources/fabrik-repo-review.md` (any NEW fragment-level finding applied by the orchestrator under the plan File Scope and recorded in this ticket's review artifact) — OR the honest all-CONFORM/no-change outcome, which still writes the verdict table and runs a scoped verification review over it, **When** /fabrik-review runs on the ticket's changed surface, **Then** it converges to a new: 0 round with every finding FIXED or REFUTED, `python commands/assemble_commands.py --check` is green, and the ticket's commit is pushed (docs/reference/operating-manifesto.md:4)
- **Given** the rendered command at the box path named in Scope and its source `commands/_sources/fabrik-review.md`, **When** it is evaluated against checklist item 63b's six intersections (docs/reference/command-evaluation-checklist.md § Governance Chain), **Then** the ticket's review artifact records a written verdict per intersection — CONFORMS at path:line · FIXED at path:line · N/A because X — with zero unadjudicated intersections (commands/_sources/fabrik-review.md:2)
- **Given** fixes applied to `commands/_sources/fabrik-review.md` (any NEW fragment-level finding applied by the orchestrator under the plan File Scope and recorded in this ticket's review artifact) — OR the honest all-CONFORM/no-change outcome, which still writes the verdict table and runs a scoped verification review over it, **When** /fabrik-review runs on the ticket's changed surface, **Then** it converges to a new: 0 round with every finding FIXED or REFUTED, `python commands/assemble_commands.py --check` is green, and the ticket's commit is pushed (docs/reference/operating-manifesto.md:4)
- **Given** the rendered command at the box path named in Scope and its source `commands/_sources/fabrik-review-scoped.md`, **When** it is evaluated against checklist item 63b's six intersections (docs/reference/command-evaluation-checklist.md § Governance Chain), **Then** the ticket's review artifact records a written verdict per intersection — CONFORMS at path:line · FIXED at path:line · N/A because X — with zero unadjudicated intersections (commands/_sources/fabrik-review-scoped.md:2)
- **Given** fixes applied to `commands/_sources/fabrik-review-scoped.md` (any NEW fragment-level finding applied by the orchestrator under the plan File Scope and recorded in this ticket's review artifact) — OR the honest all-CONFORM/no-change outcome, which still writes the verdict table and runs a scoped verification review over it, **When** /fabrik-review runs on the ticket's changed surface, **Then** it converges to a new: 0 round with every finding FIXED or REFUTED, `python commands/assemble_commands.py --check` is green, and the ticket's commit is pushed (docs/reference/operating-manifesto.md:4)
- **Given** the rendered command at the box path named in Scope and its source `commands/_sources/fabrik-rivals.md`, **When** it is evaluated against checklist item 63b's six intersections (docs/reference/command-evaluation-checklist.md § Governance Chain), **Then** the ticket's review artifact records a written verdict per intersection — CONFORMS at path:line · FIXED at path:line · N/A because X — with zero unadjudicated intersections (commands/_sources/fabrik-rivals.md:2)
- **Given** fixes applied to `commands/_sources/fabrik-rivals.md` (any NEW fragment-level finding applied by the orchestrator under the plan File Scope and recorded in this ticket's review artifact) — OR the honest all-CONFORM/no-change outcome, which still writes the verdict table and runs a scoped verification review over it, **When** /fabrik-review runs on the ticket's changed surface, **Then** it converges to a new: 0 round with every finding FIXED or REFUTED, `python commands/assemble_commands.py --check` is green, and the ticket's commit is pushed (docs/reference/operating-manifesto.md:4)
- **Given** the rendered command at the box path named in Scope and its source `commands/_sources/fabrik-rules-review.md`, **When** it is evaluated against checklist item 63b's six intersections (docs/reference/command-evaluation-checklist.md § Governance Chain), **Then** the ticket's review artifact records a written verdict per intersection — CONFORMS at path:line · FIXED at path:line · N/A because X — with zero unadjudicated intersections (commands/_sources/fabrik-rules-review.md:2)
- **Given** fixes applied to `commands/_sources/fabrik-rules-review.md` (any NEW fragment-level finding applied by the orchestrator under the plan File Scope and recorded in this ticket's review artifact) — OR the honest all-CONFORM/no-change outcome, which still writes the verdict table and runs a scoped verification review over it, **When** /fabrik-review runs on the ticket's changed surface, **Then** it converges to a new: 0 round with every finding FIXED or REFUTED, `python commands/assemble_commands.py --check` is green, and the ticket's commit is pushed (docs/reference/operating-manifesto.md:4)
- **Given** the rendered command at the box path named in Scope and its source `commands/_sources/fabrik-service-test.md`, **When** it is evaluated against checklist item 63b's six intersections (docs/reference/command-evaluation-checklist.md § Governance Chain), **Then** the ticket's review artifact records a written verdict per intersection — CONFORMS at path:line · FIXED at path:line · N/A because X — with zero unadjudicated intersections (commands/_sources/fabrik-service-test.md:2)
- **Given** fixes applied to `commands/_sources/fabrik-service-test.md` (any NEW fragment-level finding applied by the orchestrator under the plan File Scope and recorded in this ticket's review artifact) — OR the honest all-CONFORM/no-change outcome, which still writes the verdict table and runs a scoped verification review over it, **When** /fabrik-review runs on the ticket's changed surface, **Then** it converges to a new: 0 round with every finding FIXED or REFUTED, `python commands/assemble_commands.py --check` is green, and the ticket's commit is pushed (docs/reference/operating-manifesto.md:4)
- **Given** the rendered command at the box path named in Scope and its source `commands/_sources/fabrik-spec.md`, **When** it is evaluated against checklist item 63b's six intersections (docs/reference/command-evaluation-checklist.md § Governance Chain), **Then** the ticket's review artifact records a written verdict per intersection — CONFORMS at path:line · FIXED at path:line · N/A because X — with zero unadjudicated intersections (commands/_sources/fabrik-spec.md:2)
- **Given** fixes applied to `commands/_sources/fabrik-spec.md` (any NEW fragment-level finding applied by the orchestrator under the plan File Scope and recorded in this ticket's review artifact) — OR the honest all-CONFORM/no-change outcome, which still writes the verdict table and runs a scoped verification review over it, **When** /fabrik-review runs on the ticket's changed surface, **Then** it converges to a new: 0 round with every finding FIXED or REFUTED, `python commands/assemble_commands.py --check` is green, and the ticket's commit is pushed (docs/reference/operating-manifesto.md:4)
- **Given** the rendered command at the box path named in Scope and its source `commands/_sources/fabrik-spec-review.md`, **When** it is evaluated against checklist item 63b's six intersections (docs/reference/command-evaluation-checklist.md § Governance Chain), **Then** the ticket's review artifact records a written verdict per intersection — CONFORMS at path:line · FIXED at path:line · N/A because X — with zero unadjudicated intersections (commands/_sources/fabrik-spec-review.md:2)
- **Given** fixes applied to `commands/_sources/fabrik-spec-review.md` (any NEW fragment-level finding applied by the orchestrator under the plan File Scope and recorded in this ticket's review artifact) — OR the honest all-CONFORM/no-change outcome, which still writes the verdict table and runs a scoped verification review over it, **When** /fabrik-review runs on the ticket's changed surface, **Then** it converges to a new: 0 round with every finding FIXED or REFUTED, `python commands/assemble_commands.py --check` is green, and the ticket's commit is pushed (docs/reference/operating-manifesto.md:4)
- **Given** the rendered command at the box path named in Scope and its source `commands/_sources/fabrik-ui-design.md`, **When** it is evaluated against checklist item 63b's six intersections (docs/reference/command-evaluation-checklist.md § Governance Chain), **Then** the ticket's review artifact records a written verdict per intersection — CONFORMS at path:line · FIXED at path:line · N/A because X — with zero unadjudicated intersections (commands/_sources/fabrik-ui-design.md:2)
- **Given** fixes applied to `commands/_sources/fabrik-ui-design.md` (any NEW fragment-level finding applied by the orchestrator under the plan File Scope and recorded in this ticket's review artifact) — OR the honest all-CONFORM/no-change outcome, which still writes the verdict table and runs a scoped verification review over it, **When** /fabrik-review runs on the ticket's changed surface, **Then** it converges to a new: 0 round with every finding FIXED or REFUTED, `python commands/assemble_commands.py --check` is green, and the ticket's commit is pushed (docs/reference/operating-manifesto.md:4)
- **Given** the rendered command at the box path named in Scope and its source `commands/_sources/fabrik-ui-design-review.md`, **When** it is evaluated against checklist item 63b's six intersections (docs/reference/command-evaluation-checklist.md § Governance Chain), **Then** the ticket's review artifact records a written verdict per intersection — CONFORMS at path:line · FIXED at path:line · N/A because X — with zero unadjudicated intersections (commands/_sources/fabrik-ui-design-review.md:2)
- **Given** fixes applied to `commands/_sources/fabrik-ui-design-review.md` (any NEW fragment-level finding applied by the orchestrator under the plan File Scope and recorded in this ticket's review artifact) — OR the honest all-CONFORM/no-change outcome, which still writes the verdict table and runs a scoped verification review over it, **When** /fabrik-review runs on the ticket's changed surface, **Then** it converges to a new: 0 round with every finding FIXED or REFUTED, `python commands/assemble_commands.py --check` is green, and the ticket's commit is pushed (docs/reference/operating-manifesto.md:4)
- **Given** the rendered command at the box path named in Scope and its source `commands/_sources/fabrik-upstream.md`, **When** it is evaluated against checklist item 63b's six intersections (docs/reference/command-evaluation-checklist.md § Governance Chain), **Then** the ticket's review artifact records a written verdict per intersection — CONFORMS at path:line · FIXED at path:line · N/A because X — with zero unadjudicated intersections (commands/_sources/fabrik-upstream.md:2)
- **Given** fixes applied to `commands/_sources/fabrik-upstream.md` (any NEW fragment-level finding applied by the orchestrator under the plan File Scope and recorded in this ticket's review artifact) — OR the honest all-CONFORM/no-change outcome, which still writes the verdict table and runs a scoped verification review over it, **When** /fabrik-review runs on the ticket's changed surface, **Then** it converges to a new: 0 round with every finding FIXED or REFUTED, `python commands/assemble_commands.py --check` is green, and the ticket's commit is pushed (docs/reference/operating-manifesto.md:4)
- **Given** the rendered command at the box path named in Scope and its source `commands/_sources/fabrik-user-test.md`, **When** it is evaluated against checklist item 63b's six intersections (docs/reference/command-evaluation-checklist.md § Governance Chain), **Then** the ticket's review artifact records a written verdict per intersection — CONFORMS at path:line · FIXED at path:line · N/A because X — with zero unadjudicated intersections (commands/_sources/fabrik-user-test.md:2)
- **Given** fixes applied to `commands/_sources/fabrik-user-test.md` (any NEW fragment-level finding applied by the orchestrator under the plan File Scope and recorded in this ticket's review artifact) — OR the honest all-CONFORM/no-change outcome, which still writes the verdict table and runs a scoped verification review over it, **When** /fabrik-review runs on the ticket's changed surface, **Then** it converges to a new: 0 round with every finding FIXED or REFUTED, `python commands/assemble_commands.py --check` is green, and the ticket's commit is pushed (docs/reference/operating-manifesto.md:4)
- **Given** the rendered command at the box path named in Scope and its source `commands/_sources/fabrik-workflow-review.md`, **When** it is evaluated against checklist item 63b's six intersections (docs/reference/command-evaluation-checklist.md § Governance Chain), **Then** the ticket's review artifact records a written verdict per intersection — CONFORMS at path:line · FIXED at path:line · N/A because X — with zero unadjudicated intersections (commands/_sources/fabrik-workflow-review.md:2)
- **Given** fixes applied to `commands/_sources/fabrik-workflow-review.md` (any NEW fragment-level finding applied by the orchestrator under the plan File Scope and recorded in this ticket's review artifact) — OR the honest all-CONFORM/no-change outcome, which still writes the verdict table and runs a scoped verification review over it, **When** /fabrik-review runs on the ticket's changed surface, **Then** it converges to a new: 0 round with every finding FIXED or REFUTED, `python commands/assemble_commands.py --check` is green, and the ticket's commit is pushed (docs/reference/operating-manifesto.md:4)
- **Given** all 33 work tickets merged, **When** the whole-plan receipt runs `python scripts/final_gate.py --check --json` + `python scripts/enforcement/check_convergence.py` + `python scripts/enforcement/check_doc_sync.py` and /fabrik-docs-review over the corpus docs, **Then** every command's 63b verdict table exists (32/32 + fragments), the gate reports success, and the receipt records the per-ticket commit list (docs/reference/command-evaluation-checklist.md:161)
- **Given** the cumulative diff of T01..T33, **When** the whole-plan /fabrik-review runs over it to a coverage-adjudicated exit (its Coverage Checklist + Pass Ledger living in the receipt artifact), **Then** the receipt's Pass Ledger closes on a round carrying the literal `found: 0 · fixed: 0` — what check_convergence.py's QUIET_PASS regex (scripts/enforcement/check_convergence.py:150) actually demands before any EXECUTED flip; a standing adjudicated row that keeps found above zero is BLOCKED-escalated, never carried into the close (commands/_sources/fabrik-execute-plan.md:958)

## Evidence

Denominator + budgets (run 2026-08-31, this session):

```
$ ls commands/_sources/*.md | wc -l
32
$ ls commands/_fragments/ | wc -l
21
$ ls ~/.claude/commands/*.md | wc -l
32
$ wc -c docs/reference/operating-manifesto.md docs/reference/command-evaluation-checklist.md | tail -1
39291 total
$ wc -c commands/_sources/*.md | sort -rn | head -2
662403 total
 73670 commands/_sources/fabrik-execute-plan.md
$ wc -c commands/_fragments/*.md | tail -1
67514 total
```

Largest command ticket READ set (T13, the FULL 6-item Context Files after review round 4): spine
(~81 KB and growing with Board flips) + 73,670 (fabrik-execute-plan source) + 9,550 (manifesto)
+ 29,741 (checklist) + 12,741 (40-documentation pack) + T01's review artifact (does not exist at
plan time — the emit gate counts a missing path as 0; estimated 10–25 KB once written)
≈ 207 KB now, ≈ 232 KB worst-case at execution < READ_BUDGET_BYTES 262,144, headroom ≈ 30 KB.
Mitigation if spine growth erodes it: the 40-documentation pack is droppable from Context Files
(it auto-activates by glob on any .md edit — belt-and-braces only). T01's set = 67,514 (all 21
fragments via its Touches dir — deliberately NOT repeated in Context Files, which would double-count)
+ spine ~82 KB + 39,291 (manifesto+checklist) + pack ≈ 202 KB. Every ticket fits, with the caveat
measured, not assumed.

Rubric run for the plan's surfaces (verbatim head):

```
$ python scripts/review_rubric.py --changed commands/_sources/fabrik-review.md commands/_fragments/run-record.md docs/reference/command-evaluation-checklist.md | grep '^### |^## '
## FLOOR — always injected, regardless of glob (spec L3)
### core/35-security-auth.md
### core/25-data-postgres.md
### core/30-ops.md
### 12-FACTOR (all twelve axes)
## MATCHED — packs whose globs hit the changed paths
### core/40-documentation.md  (hit: commands/_fragments/run-record.md, commands/_sources/fabrik-review.md, docs/reference/command-evaluation-checklist.md)
```

Primary-path citations (authorial floor — spine Evidence cites every ticket's primary path): T01 →
commands/_fragments/ (21 files, run-record.md:1 read); T02–T33 → each `commands/_sources/<cmd>.md`
(all 32 opened this session for the description-line citation embedded in each ticket's first G/W/T
row — the line numbers were computed by reading each file, not assumed); T34 →
docs/development/reviews/2026-08-31-plan-1-manifesto-command-pass-review.md (receipt, created at execution).

## Self-audit

- (a) **Coverage** — every Intake row I1–I7 maps to a delivering ticket or binding section (table above);
  the operator's four verbs (walk all · evaluate+update · without stopping · review each) land in T02–T33
  Scope steps 1–5, the serial chain, and § Execution Discipline. Gap check: skills = the rendered
  ~/.claude/skills wrappers are GENERATED from the same 32 sources by the same renderer — evaluating the
  source + rendered command covers them; no separate skill ticket is owed (the wrapper carries no authored
  content — its header says DO NOT HAND-EDIT).
- (b) **Cross-ticket interfaces** — T01's produced verdict ledger is consumed by T02–T33 under the same
  name (the T01 review artifact path, fixed in T01's Touches); T34 consumes the per-ticket artifact paths
  exactly as each ticket's Touches spells them (same generator emitted both sides, so the names cannot
  drift). Seam tests named in § Interfaces.
- Grounding passes run: corpus denominator (ls ×3) · byte budgets (wc) · rubric (fenced above) ·
  NO-POOL waiver form read at check_subagent_flywheel.py:7 · description-line per source read
  programmatically. Not yet a fixed point — that is /fabrik-plan-review's job (auto-invoked next).

## Residual unknowns

- **Resolved:** ticket count (32 sources, not 31 — grounded); render safety (serial master MAIN execution
  sanctions per-ticket renders); fragment recurrence (T01-first design); read budgets (all fit).
- **Open — carries its resolution step:** how many commands genuinely FAIL an intersection is unknowable
  until evaluated (this is the work itself, not a planning gap); resolution = the per-ticket verdict
  tables. If a 63b intersection proves systematically ambiguous across the first 3 tickets (same
  adjudication argument recurring), the executor records it in the T-in-flight review artifact and
  continues — the checklist wording fix is an in-beat corpus edit the pass itself may apply at first
  encounter (it owns docs/reference/command-evaluation-checklist.md? NO — the checklist is NOT in File
  Scope; the fix routes as a normal spontaneous edit outside the plan, per CLAUDE.md — NOT via T34's Deltas
  block, whose D3 format covers only the five governance surfaces. Named here so the executor does not
  stall on it).
- **Open — seeded finding for T22 (pre-existing corpus tension, found by this review's closing pass):**
  `/fabrik-review`'s exit keys on `new: 0` and explicitly allows a standing adjudicated row to keep
  `found:` above zero forever (commands/_sources/fabrik-review.md § Reporting), while
  `check_convergence.py:150` (QUIET_PASS) and `check_review_coverage.py` demand a literal
  `found: 0 · fixed: 0` closing row. T22 owns `commands/_sources/fabrik-review.md` in this pass and
  adjudicates the tension under 63b intersection (a) — checkable gates must agree with their graders;
  resolution lands there, not here.


## Coverage Checklist

Derived from the recorded rubric run below (FLOOR + MATCHED) + the four standing recurrence classes.

| class | verdict | evidence |
|---|---|---|
| FLOOR: security-auth / data-postgres / ops + 12-Factor (code classes) | CLEAN | the set's File Scope is .md-only (commands/_sources/, _fragments/, plan+review docs) — no code/compose/deps/env/schema step exists in any ticket; Global Constraints binds the axes by exclusion and routes any code-surface discovery to BLOCKED (examined: all 34 tickets' Touches) |
| 40-documentation (MATCHED): markdown discipline on every emitted .md | CLEAN | generator emits flat `##`/`###` headings, fenced blocks only; emit gate + review of spine/ticket structure found no skipped levels (examined: spine + 34 tickets) |
| fail-open vs fail-closed on every gate/guard (standing) | CLEAN | the set's gates (`assemble_commands.py --check`, emit gate, final_gate --check) all fail-closed on error; the one advisory (breadth screen) is weighed in this review, not obeyed silently |
| cost/quota/limit accounting edges (standing) | CLEAN | READ budgets recomputed against `READ_BUDGET_BYTES` 262144 with real `wc -c` outputs (Evidence block); largest ticket ≈120 KB; no other quota surface in scope (NO-POOL — zero pool spend by design, waived via the declared commit line) |
| boundary/sentinel/prefix collisions (standing) | FIXED(1) | finder: the per-ticket review-artifact filenames must be stem-prefixed for the containment exemption AND unique — verified all 33 artifact paths distinct and stem-prefixed (re-derived by script); plus the D-041-style id race has no analogue here (ticket ids minted once by one generator) |
| behavior-without-a-test (standing) | CLEAN | every ticket's G/W/T rows terminate in an executable check (`assemble --check`, the review's new: 0 round, final_gate) — the "test" for governance prose is the named gate, per 63b intersection (a) |

Recorded rubric run (verbatim):

```
# REVIEW RUBRIC — inject into EVERY finder prompt (generated by review_rubric.py)
# Honesty (L1): this arms the review — it raises compliance probability, it does not guarantee it.

## FLOOR — always injected, regardless of glob (spec L3)

### core/35-security-auth.md
- Do not use NextAuth.js, Clerk, Auth0, or Firebase Auth.
- ADDITIONAL affordance a project justifies, never the default door.
| `chrome-extension` | ✅ **use this** | ⚠️ only via `chrome.identity.launchWebAuthFlow` + the `https://<ext-id>.chromiumapp.org/` redirect the pack already mandates; a bare mailed link lands in a TAB that cannot reach `chrome.storage.session` |
| `desktop-app` | ✅ **use this** | ⚠️ needs a registered custom protocol handler; the token then goes to `safeStorage` (`desktop-app/72-desktop.md`) |
- service MUST be able to say which:
| **Another Fabrik service** (Docker-to-Docker on the `fabrik` network) | `X-Internal-Token` + `internal_auth.py`, `hmac.compare_digest`, 403 on reject | § Internal Service Auth (M2M) below — **never** an inline `APIKeyHeader`, never a per-service key name |
- An approval link opened somewhere the user did not start must never mint a session silently.
- > **Fail-closed invariant (hard, every mode).** `auth.uid()` and `current_tenant_id()` MUST return `NULL` (→ the policy denies) on unset, empty, or malformed claims — wrap the body in `EXCEPTION WHEN OTHERS THEN RETURN NULL`. **Never** raise and never default to a value: an error-open helper turns one bad/empty JWT into a full cross-tenant read. This is the single most security-critical line in the build — verify it explicitly with a no-context probe (`SELECT auth.uid()` → `NULL`).
- The JWT signing secret must be at least 256 bits, generated via `openssl rand -hex 32`, and injected via Pydantic Settings. Never hardcode it.
- "Sticky sessions are a violation of twelve-factor and should never be used or relied upon."
- => Mandate: processes are stateless/share-nothing. **STICKY SESSIONS ARE BANNED** (not just file-based sessions). Session state goes to `redis-main` (Redis) with a TTL. Never in-process memory, never on local disk. Any design that assumes "the same user hits the same process" is a violation.
- **Pattern B (legacy / migration-only):** The Supabase client SDK handles token storage. On mobile, wrap with `expo-secure-store` (never AsyncStorage or MMKV for tokens). See `80-mobile.md` § Backend Integration.
- **Both patterns:** Never store JWTs in `localStorage` or `sessionStorage` on web. Never store JWTs in AsyncStorage or MMKV on mobile.
- **Chrome Extension (MV3) specifics:** `chrome.storage.session` defaults to `TRUSTED_CONTEXTS`, so **content scripts cannot read the token** — keep it in the SW / extension-page context and have content scripts fetch it via SW-mediated messaging (`chrome.runtime.sendMessage`), not a direct read. For social login use `chrome.identity.launchWebAuthFlow` with **PKCE** (`code_verifier` via `crypto.subtle`, held in `storage.session`, redirect `https://<ext-id>.chromiumapp.org/`); the **backend** does the code-for-token exchange. **Never a heavy browser auth SDK** (Auth0-SPA-JS, `oidc-client-ts`) — they assume DOM/`localStorage`/iframes and break in the service worker. Pin a manifest `key` so the extension ID (and thus the `chrome-extension://<id>` CORS origin) is stable across machines. Full detail: `chrome-ext/70-chrome-ext.md`.
- **Never rely solely on `middleware.ts` for access control.** CVE-2025-29927 allows complete middleware bypass via header manipulation.
- `CORSMiddleware` in FastAPI must populate `allow_origins` from environment variables (Pydantic Settings). Never hardcode origins.
**Never** write inline `APIKeyHeader` / `require_api_key`. **Never** use per-service key names (`SERVICE_API_KEY`, `PROXY_API_KEY`). Scaffold `python-api` auto-emits `internal_auth.py`, `metrics.py` (REQUEST_COUNT / ERROR_COUNT / ACTIVE_JOBS / PROCESSING_COUNT), `/metrics` endpoint (Authelia-bypassed), and `SERVICE_INTERNAL_SECRET_KEY` in `.env.example`.
- => Mandate: config via env vars only (`os.getenv("KEY", "default")`); **ZERO secrets/constants in code**. Apply the open-source litmus test to every change. **BANNED**: grouped/named env config sets (e.g. a `config/production.yml` or a `settings.production` group) — env vars are granular and orthogonal, set per deploy. (The pack already covers secret handling — cross-reference existing secret patterns and extend with config orthogonality.)
- [ ] Mobile tokens stored in `expo-secure-store` — never AsyncStorage or MMKV.

### core/25-data-postgres.md
- Use Pydantic `BaseSettings` (per `10-python.md` § Config Loading) — never raw `os.getenv` **for an
- ⚠️ **Scope, stated here because this LINE is what `review_rubric.py` injects — without its section.**
- Never blindly trust `--autogenerate`. Always review `upgrade()` and `downgrade()` for unintended column drops, rename misinterpretations, and ENUM alterations before committing.
- > **Critical:** import `uuid7` from `uuid_utils.compat`, never `uuid_utils.uuid7()` directly — the latter returns `uuid_utils.UUID`, which asyncpg rejects (not a stdlib `uuid.UUID` subclass). **PostgreSQL 18** (released Sep 2025) added native `uuidv7()` — if your instance is PG18+, you can use `DEFAULT uuidv7()` at the schema level instead of app-side generation. On PG16/17, generate app-side as above.
- Foreign keys must declare `ON DELETE` behaviour explicitly — `CASCADE` if children cannot exist without the parent, `RESTRICT` to protect audit trails. Never rely on the implicit default.
- This section owns the **canonical** engine, session, and `get_db`. `10-python.md` imports from here — never redefines its own.
- Database `AsyncSession` must be scoped to the route handler via `Depends()`. Never open sessions or transactions in global middleware — this holds connections during serialisation and I/O, exhausting the pool.
**BANNED as a server-side backing service** (dev, test, and prod alike):
**⚠️ SCOPE — this ban is about BACKING SERVICES, not client-local storage.** It does **NOT** apply to:
- **`desktop-app`** — SQLite is the **mandated** engine there (`desktop-app/72-desktop.md` § Local Persistence: `better-sqlite3` + SQLCipher; *"Production builds MUST encrypt the local SQLite file"*).
**12-Factor IV (Backing Services) — generalised:** swapping ANY attached backing service (DB, cache, object storage) is a **config change, never a code change**. The handle lives in `DATABASE_URL` / `REDIS_URL` / storage env — the code *reads* it, the code does not *decide* it. Never `if ENV == "prod":` branching to pick a host. (See § PostgreSQL Host Selection, which already mandates this for the DB.)

### core/30-ops.md
- All services deploy via `fabrik apply` (SSH + Docker Compose) on the `fabrik` network. Traefik routes external traffic — services do NOT bind host ports.
- **No `ports:` section.** All external traffic routes through Traefik. Never bind host ports. See Docker Port Security below. **12‑Factor VII (Port binding):** "the app is self‑contained and exports HTTP by binding to a port; it does not rely on runtime injection of a webserver" — which is exactly WHY no host `ports:`.
- **`container_name: <name>` is mandatory.** Same `_validate_compose()` gate refuses any service without it. Stable names are required so Gatus endpoints, inter-service URLs, and `docker exec`/`docker inspect` keys don't drift per redeploy. Use the bare service name (`browserless`, `gotenberg`, `meilisearch`, `glitchtip-web`, `site-provisioner`, etc.) — never UUID-suffixed names.
- `fabrik redeploy <app>` SSHes to the VPS and runs `git pull` + `docker compose up -d --wait` against the **GitHub remote**, NOT the local `/opt/<app>` clone. Skipping `git push` redeploys the previous remote commit — the VPS never sees local changes.
**Mandate:** build → release → run are strictly separated. Releases are IMMUTABLE; the git SHA is the release ID. NEVER hot‑patch a running container (no `docker exec` to edit code/config in place, no in‑place code mutation on the VPS). Any change = a new build + a new release via `fabrik apply` / `fabrik redeploy`.
- Runtime database migrations that modify the app container (migrations MUST be run as separate deploy‑time steps)
**Mandate:** WSL dev and the VPS run the SAME backing services (PostgreSQL + Redis), same major version. NEVER substitute a different backing service in dev (no SQLite standing in for Postgres, no in‑memory dict standing in for Redis). The same code must run unmodified in both environments.
**Invariant:** Never use `ports:` in compose.yaml to expose internal services to the host. All external traffic must go through Traefik.
**Health endpoints (`/health`, `/healthz`, `/metrics`, `/api/health`) bypass Authelia on all services** — required for Gatus and Prometheus monitoring. The bypass is **resource-based, not domain-bound** — applies on every domain routed through Authelia (hub direct + spokes via `authelia-vps1@file` middleware). Never protect these paths.
**CRITICAL:** Use `web`/`websecure` in Traefik labels — never `http`/`https` (those entrypoints do not exist). The scaffolder emits the correct entrypoint names; if you hand-write labels, match these exactly.
**Mandate:** migrations and admin tasks run as a ONE‑OFF process against the DEPLOYED image + env — identical environment to regular processes. NEVER run admin tasks from a laptop against prod, NEVER via `docker exec` into a live container, and **ABSOLUTELY NEVER auto-run migrations from app startup/`lifespan`** (concurrent replicas race the Alembic version table → wedged deploy).
- > sees a file that looks exactly like a migration step, and ships a deploy where migrations never run —
- > the rule producing the very defect it exists to prevent. Do not re-add either without a `path:line` in
**Processes are share-nothing:** any state shared across requests MUST go to Redis (`redis-main`) with a TTL. A project using Redis for sessions MUST declare `shape.needs_cache: true` in `specs/services/<id>.yaml`, or `fabrik apply` skips the Redis registrar and the deploy is silently broken.
- "A twelve-factor app never relies on implicit existence of system-wide packages"
**Mandate:** any binary the app shells out to (ffmpeg, yt-dlp, poppler, tesseract…) MUST be `apt-get install`-ed AND version-pinned in the Dockerfile, with a `shutil.which()` startup probe that fails fast. Never assume `curl`/ImageMagick/ffmpeg exist in the image — they don't by default.

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

### core/40-documentation.md  (hit: docs/development/plans/2026-08-31-plan-1-manifesto-command-pass/, docs/development/reviews/)
- **Tier-1 (cheap-pool author → verify → converge):** for each **mechanically-detectable** doc whose Doc-Sync trigger fired (`docs/QUICKSTART.md` · `docs/CONFIGURATION.md` · `docs/data-contract.md` · `docs/SERVICES.md` · `docs/OPERATIONS.md` — the reliable-signal subset), `scripts/doc_reconcile.py` dispatches a cheap OpenRouter-pool author (`libs.subagents`, `pick_models("docs")`) to emit a **minimal structured patch**, **verifies it before applying** (a symbol cross-check catches invented endpoints; the orchestrator injects a higher-assurance native-Claude verify), and loops to a zero-edit round. Runs per phase in `/fabrik-execute-plan`; never blocks (fail-safe). The other docs (CHANGELOG, INDEX, FEATURES, RESILIENCE, PORTS, the READMEs, `db/schema.sql`, …) have no reliable mechanical content-signal → they rely on the touch-on-change backstop below + your own edit (force-update, not force-correct).
- Standalone work (not plan execution) → `Agent-Role: primary`. Trailers go below a blank line, above `Co-Authored-By`. ⚠️ The trailer block must be its OWN paragraph with NO blank line inside it: git parses only the LAST paragraph, and only if it is all-trailers. A blank line before `Co-Authored-By:` demotes everything above it to prose; so does a prose line glued to the top of the block. Measured 2026-08-15: 200 of the last 200 hub commits carried `Agent-Role:` and only 10 parsed, because the old example here shipped the blank line.
- **No skipped heading levels** — `##` to `###`, never `##` to `####`
- **Fenced code blocks only** — never indented code (AI treats it inconsistently)

# promote-to-check_*: 38 injected mandate(s) look deterministically greppable
| `chrome-extension` | ✅ **use this** | ⚠️ only via `chrome.identity.launchWebAuthFlow` + the `https://<ext-id>.chromiumapp.org/` redirect the pack already mandates; a bare mailed link lands in a TAB that cannot reach `chrome.storage.session` |
| `desktop-app` | ✅ **use this** | ⚠️ needs a registered custom protocol handler; the token then goes to `safeStorage` (`desktop-app/72-desktop.md`) |
| **Another Fabrik service** (Docker-to-Docker on the `fabrik` network) | `X-Internal-Token` + `internal_auth.py`, `hmac.compare_digest`, 403 on reject | § Internal Service Auth (M2M) below — **never** an inline `APIKeyHeader`, never a per-service key name |
- > **Fail-closed invariant (hard, every mode).** `auth.uid()` and `current_tenant_id()` MUST return `NULL` (→ the policy denies) on unset, empty, or malformed claims — wrap the body in `EXCEPTION WHEN OTHERS THEN RETURN NULL`. **Never** raise and never default to a value: an error-open helper turns one bad/empty JWT into a full cross-tenant read. This is the single most security-critical line in the build — verify it explicitly with a no-context probe (`SELECT auth.uid()` → `NULL`).
- The JWT signing secret must be at least 256 bits, generated via `openssl rand -hex 32`, and injected via Pydantic Settings. Never hardcode it.
- => Mandate: processes are stateless/share-nothing. **STICKY SESSIONS ARE BANNED** (not just file-based sessions). Session state goes to `redis-main` (Redis) with a TTL. Never in-process memory, never on local disk. Any design that assumes "the same user hits the same process" is a violation.
- **Pattern B (legacy / migration-only):** The Supabase client SDK handles token storage. On mobile, wrap with `expo-secure-store` (never AsyncStorage or MMKV for tokens). See `80-mobile.md` § Backend Integration.
- **Both patterns:** Never store JWTs in `localStorage` or `sessionStorage` on web. Never store JWTs in AsyncStorage or MMKV on mobile.
- **Chrome Extension (MV3) specifics:** `chrome.storage.session` defaults to `TRUSTED_CONTEXTS`, so **content scripts cannot read the token** — keep it in the SW / extension-page context and have content scripts fetch it via SW-mediated messaging (`chrome.runtime.sendMessage`), not a direct read. For social login use `chrome.identity.launchWebAuthFlow` with **PKCE** (`code_verifier` via `crypto.subtle`, held in `storage.session`, redirect `https://<ext-id>.chromiumapp.org/`); the **backend** does the code-for-token exchange. **Never a heavy browser auth SDK** (Auth0-SPA-JS, `oidc-client-ts`) — they assume DOM/`localStorage`/iframes and break in the service worker. Pin a manifest `key` so the extension ID (and thus the `chrome-extension://<id>` CORS origin) is stable across machines. Full detail: `chrome-ext/70-chrome-ext.md`.
- **Never rely solely on `middleware.ts` for access control.** CVE-2025-29927 allows complete middleware bypass via header manipulation.
- `CORSMiddleware` in FastAPI must populate `allow_origins` from environment variables (Pydantic Settings). Never hardcode origins.
**Never** write inline `APIKeyHeader` / `require_api_key`. **Never** use per-service key names (`SERVICE_API_KEY`, `PROXY_API_KEY`). Scaffold `python-api` auto-emits `internal_auth.py`, `metrics.py` (REQUEST_COUNT / ERROR_COUNT / ACTIVE_JOBS / PROCESSING_COUNT), `/metrics` endpoint (Authelia-bypassed), and `SERVICE_INTERNAL_SECRET_KEY` in `.env.example`.
- => Mandate: config via env vars only (`os.getenv("KEY", "default")`); **ZERO secrets/constants in code**. Apply the open-source litmus test to every change. **BANNED**: grouped/named env config sets (e.g. a `config/production.yml` or a `settings.production` group) — env vars are granular and orthogonal, set per deploy. (The pack already covers secret handling — cross-reference existing secret patterns and extend with config orthogonality.)
- [ ] Mobile tokens stored in `expo-secure-store` — never AsyncStorage or MMKV.
- Use Pydantic `BaseSettings` (per `10-python.md` § Config Loading) — never raw `os.getenv` **for an
- ⚠️ **Scope, stated here because this LINE is what `review_rubric.py` injects — without its section.**
- Never blindly trust `--autogenerate`. Always review `upgrade()` and `downgrade()` for unintended column drops, rename misinterpretations, and ENUM alterations before committing.
- > **Critical:** import `uuid7` from `uuid_utils.compat`, never `uuid_utils.uuid7()` directly — the latter returns `uuid_utils.UUID`, which asyncpg rejects (not a stdlib `uuid.UUID` subclass). **PostgreSQL 18** (released Sep 2025) added native `uuidv7()` — if your instance is PG18+, you can use `DEFAULT uuidv7()` at the schema level instead of app-side generation. On PG16/17, generate app-side as above.
- Foreign keys must declare `ON DELETE` behaviour explicitly — `CASCADE` if children cannot exist without the parent, `RESTRICT` to protect audit trails. Never rely on the implicit default.
- This section owns the **canonical** engine, session, and `get_db`. `10-python.md` imports from here — never redefines its own.
```


## Pass Ledger (/fabrik-plan-review, 2026-08-31)

| Pass | axes re-checked | method | raised | new: | edits | set md5 (start → end) |
|-----:|---|---|---:|---:|---:|---|
| 1 | all (wide: author-blind finder on judgment surfaces + orchestrator mechanical sweep; arming: rubric+checklist into spine) | citation | 9 | 9 | 8 fixes (spine + 34 tickets) | 52092885… → b7115c60… |
| 2 | scoped: pass-1 edits (roll-up equality, Context Files, budgets) | citation | 1 (own measurement artifact, REFUTED) | 1 | 0 | b7115c60… |
| 3 | all (wide closing: fresh non-author finder, 10 re-derivation items, 36-citation sweep) | **re-derivation** | 1 (stale :158 citation) | 1 | 1 (→ :161, both sites) | b7115c60… → a6238453… |
| 4 | all (wide: fresh non-author finder) | citation | 2 (spine-in-Context-Files + convergence-citation wording) | 2 | 2 + budget redesign (T01 sole fragment owner) | a6238453… → 6c44d7c5… |
| 5 | all (wide: fresh non-author finder) | citation | 3 (orphaned Serialized clause · Deltas-term misuse · stale Evidence arithmetic) | 3 | 0 (breaker) | 6c44d7c5… |
| — | **## BLOCKED: NON-CONVERGENCE breaker fired (new: 1→2→3 non-decreasing)** — foundation error named: fix rounds introducing unverified claims; re-ground rule adopted: every fix carries in-round re-derivation | — | — | — | — | — |
| 6 | fix round under the re-ground rule (G1–G3 + fragment-ownership redesign; every introduced claim re-derived in-round against primary source) | **re-derivation** | 1 (own grep scare, REFUTED as legitimate D3 usage) | 1 | G1–G3 | 6c44d7c5… → df991307… |
| 7 | all (wide closing: fresh non-author finder) | citation | 1 (T34's phantom write-channel for out-of-scope docs) | 1 | 3 (REPORT-mode + T01 symmetry + dedup + arithmetic) | df991307… → 8e885030… |
| 8 | all (wide closing: fresh non-author finder; budgets, chain, slugs, citations, gates ALL re-derived with denominators — 32/32, 34/34, 33/33, 32/32) | **re-derivation** | 0 | 0 | **0** | 8e885030… → 8e885030… ✓ → **CONVERGED** |

Trajectory of fresh candidates across wide rounds: 9 → 1 → 2 → 3 (breaker) → 1 → 0. Gates at the
flip: `check_plan_tickets --plan-dir` exit 0 (zero WARN) · `check_ticket_breadth` silent (all 34
score 3–4, threshold 5) · probes re-run verbatim-identical at pass 1 and pass 8.
