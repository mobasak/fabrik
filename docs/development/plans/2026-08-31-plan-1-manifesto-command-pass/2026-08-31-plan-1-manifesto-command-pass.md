# The commands/skills manifesto pass — evaluate + update all 32 commands against the Operating Manifesto

Status: DRAFT

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
  fragments ONCE; a later ticket edits a fragment only for a NEW finding T01's ledger does not carry, and
  says so in its review artifact.
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
| T01 | Fragments manifesto baseline (all 21 shared fragments) | — | ⛓️ | ⬜ | |
| T02 | /design-review — 63b manifesto conformance + fixes + per-command review | T01 | ⛓️ | ⬜ | |
| T03 | /fabrik-catchup — 63b manifesto conformance + fixes + per-command review | T02 | ⛓️ | ⬜ | |
| T04 | /fabrik-conformance-review — 63b manifesto conformance + fixes + per-command review | T03 | ⛓️ | ⬜ | |
| T05 | /fabrik-data-contract — 63b manifesto conformance + fixes + per-command review | T04 | ⛓️ | ⬜ | |
| T06 | /fabrik-decommission — 63b manifesto conformance + fixes + per-command review | T05 | ⛓️ | ⬜ | |
| T07 | /fabrik-deploy — 63b manifesto conformance + fixes + per-command review | T06 | ⛓️ | ⬜ | |
| T08 | /fabrik-deploy-plan — 63b manifesto conformance + fixes + per-command review | T07 | ⛓️ | ⬜ | |
| T09 | /fabrik-deploy-plan-review — 63b manifesto conformance + fixes + per-command review | T08 | ⛓️ | ⬜ | |
| T10 | /fabrik-deploy-verify — 63b manifesto conformance + fixes + per-command review | T09 | ⛓️ | ⬜ | |
| T11 | /fabrik-doc-converge — 63b manifesto conformance + fixes + per-command review | T10 | ⛓️ | ⬜ | |
| T12 | /fabrik-docs-review — 63b manifesto conformance + fixes + per-command review | T11 | ⛓️ | ⬜ | |
| T13 | /fabrik-execute-plan — 63b manifesto conformance + fixes + per-command review | T12 | ⛓️ | ⬜ | |
| T14 | /fabrik-features — 63b manifesto conformance + fixes + per-command review | T13 | ⛓️ | ⬜ | |
| T15 | /fabrik-flows — 63b manifesto conformance + fixes + per-command review | T14 | ⛓️ | ⬜ | |
| T16 | /fabrik-flows-review — 63b manifesto conformance + fixes + per-command review | T15 | ⛓️ | ⬜ | |
| T17 | /fabrik-generate-tests — 63b manifesto conformance + fixes + per-command review | T16 | ⛓️ | ⬜ | |
| T18 | /fabrik-plan-after-chat — 63b manifesto conformance + fixes + per-command review | T17 | ⛓️ | ⬜ | |
| T19 | /fabrik-plan-review — 63b manifesto conformance + fixes + per-command review | T18 | ⛓️ | ⬜ | |
| T20 | /fabrik-release — 63b manifesto conformance + fixes + per-command review | T19 | ⛓️ | ⬜ | |
| T21 | /fabrik-repo-review — 63b manifesto conformance + fixes + per-command review | T20 | ⛓️ | ⬜ | |
| T22 | /fabrik-review — 63b manifesto conformance + fixes + per-command review | T21 | ⛓️ | ⬜ | |
| T23 | /fabrik-review-scoped — 63b manifesto conformance + fixes + per-command review | T22 | ⛓️ | ⬜ | |
| T24 | /fabrik-rivals — 63b manifesto conformance + fixes + per-command review | T23 | ⛓️ | ⬜ | |
| T25 | /fabrik-rules-review — 63b manifesto conformance + fixes + per-command review | T24 | ⛓️ | ⬜ | |
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

Serialized: commands/_fragments/ — T01, T02, T03, T04, T05, T06, T07, T08, T09, T10, T11, T12, T13, T14, T15, T16, T17, T18, T19, T20, T21, T22, T23, T24, T25, T26, T27, T28, T29, T30, T31, T32, T33

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
  chain T01→T34 (Depends edges + the Serialized row on `commands/_fragments/`). There is no fan-out and
  therefore no merge/dedupe point; each ticket commits+pushes its own surface before the next begins.
  "Without stopping" means: the ONLY sanctioned halts between tickets are the three BLOCKED cases
  (3 consecutive same-test failures · missing infra · unresolvable spec contradiction); context length is
  never a reason (the harness auto-compacts; durable state lives in the Board + review artifacts).

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
- **Given** fixes applied to `commands/_sources/design-review.md` (and a fragment only on a NEW fragment-level finding T01 did not sweep), **When** /fabrik-review runs on the ticket's changed surface, **Then** it converges to a new: 0 round with every finding FIXED or REFUTED, `python commands/assemble_commands.py --check` is green, and the ticket's commit is pushed (docs/reference/operating-manifesto.md:4)
- **Given** the rendered command at the box path named in Scope and its source `commands/_sources/fabrik-catchup.md`, **When** it is evaluated against checklist item 63b's six intersections (docs/reference/command-evaluation-checklist.md § Governance Chain), **Then** the ticket's review artifact records a written verdict per intersection — CONFORMS at path:line · FIXED at path:line · N/A because X — with zero unadjudicated intersections (commands/_sources/fabrik-catchup.md:2)
- **Given** fixes applied to `commands/_sources/fabrik-catchup.md` (and a fragment only on a NEW fragment-level finding T01 did not sweep), **When** /fabrik-review runs on the ticket's changed surface, **Then** it converges to a new: 0 round with every finding FIXED or REFUTED, `python commands/assemble_commands.py --check` is green, and the ticket's commit is pushed (docs/reference/operating-manifesto.md:4)
- **Given** the rendered command at the box path named in Scope and its source `commands/_sources/fabrik-conformance-review.md`, **When** it is evaluated against checklist item 63b's six intersections (docs/reference/command-evaluation-checklist.md § Governance Chain), **Then** the ticket's review artifact records a written verdict per intersection — CONFORMS at path:line · FIXED at path:line · N/A because X — with zero unadjudicated intersections (commands/_sources/fabrik-conformance-review.md:2)
- **Given** fixes applied to `commands/_sources/fabrik-conformance-review.md` (and a fragment only on a NEW fragment-level finding T01 did not sweep), **When** /fabrik-review runs on the ticket's changed surface, **Then** it converges to a new: 0 round with every finding FIXED or REFUTED, `python commands/assemble_commands.py --check` is green, and the ticket's commit is pushed (docs/reference/operating-manifesto.md:4)
- **Given** the rendered command at the box path named in Scope and its source `commands/_sources/fabrik-data-contract.md`, **When** it is evaluated against checklist item 63b's six intersections (docs/reference/command-evaluation-checklist.md § Governance Chain), **Then** the ticket's review artifact records a written verdict per intersection — CONFORMS at path:line · FIXED at path:line · N/A because X — with zero unadjudicated intersections (commands/_sources/fabrik-data-contract.md:2)
- **Given** fixes applied to `commands/_sources/fabrik-data-contract.md` (and a fragment only on a NEW fragment-level finding T01 did not sweep), **When** /fabrik-review runs on the ticket's changed surface, **Then** it converges to a new: 0 round with every finding FIXED or REFUTED, `python commands/assemble_commands.py --check` is green, and the ticket's commit is pushed (docs/reference/operating-manifesto.md:4)
- **Given** the rendered command at the box path named in Scope and its source `commands/_sources/fabrik-decommission.md`, **When** it is evaluated against checklist item 63b's six intersections (docs/reference/command-evaluation-checklist.md § Governance Chain), **Then** the ticket's review artifact records a written verdict per intersection — CONFORMS at path:line · FIXED at path:line · N/A because X — with zero unadjudicated intersections (commands/_sources/fabrik-decommission.md:2)
- **Given** fixes applied to `commands/_sources/fabrik-decommission.md` (and a fragment only on a NEW fragment-level finding T01 did not sweep), **When** /fabrik-review runs on the ticket's changed surface, **Then** it converges to a new: 0 round with every finding FIXED or REFUTED, `python commands/assemble_commands.py --check` is green, and the ticket's commit is pushed (docs/reference/operating-manifesto.md:4)
- **Given** the rendered command at the box path named in Scope and its source `commands/_sources/fabrik-deploy.md`, **When** it is evaluated against checklist item 63b's six intersections (docs/reference/command-evaluation-checklist.md § Governance Chain), **Then** the ticket's review artifact records a written verdict per intersection — CONFORMS at path:line · FIXED at path:line · N/A because X — with zero unadjudicated intersections (commands/_sources/fabrik-deploy.md:2)
- **Given** fixes applied to `commands/_sources/fabrik-deploy.md` (and a fragment only on a NEW fragment-level finding T01 did not sweep), **When** /fabrik-review runs on the ticket's changed surface, **Then** it converges to a new: 0 round with every finding FIXED or REFUTED, `python commands/assemble_commands.py --check` is green, and the ticket's commit is pushed (docs/reference/operating-manifesto.md:4)
- **Given** the rendered command at the box path named in Scope and its source `commands/_sources/fabrik-deploy-plan.md`, **When** it is evaluated against checklist item 63b's six intersections (docs/reference/command-evaluation-checklist.md § Governance Chain), **Then** the ticket's review artifact records a written verdict per intersection — CONFORMS at path:line · FIXED at path:line · N/A because X — with zero unadjudicated intersections (commands/_sources/fabrik-deploy-plan.md:2)
- **Given** fixes applied to `commands/_sources/fabrik-deploy-plan.md` (and a fragment only on a NEW fragment-level finding T01 did not sweep), **When** /fabrik-review runs on the ticket's changed surface, **Then** it converges to a new: 0 round with every finding FIXED or REFUTED, `python commands/assemble_commands.py --check` is green, and the ticket's commit is pushed (docs/reference/operating-manifesto.md:4)
- **Given** the rendered command at the box path named in Scope and its source `commands/_sources/fabrik-deploy-plan-review.md`, **When** it is evaluated against checklist item 63b's six intersections (docs/reference/command-evaluation-checklist.md § Governance Chain), **Then** the ticket's review artifact records a written verdict per intersection — CONFORMS at path:line · FIXED at path:line · N/A because X — with zero unadjudicated intersections (commands/_sources/fabrik-deploy-plan-review.md:2)
- **Given** fixes applied to `commands/_sources/fabrik-deploy-plan-review.md` (and a fragment only on a NEW fragment-level finding T01 did not sweep), **When** /fabrik-review runs on the ticket's changed surface, **Then** it converges to a new: 0 round with every finding FIXED or REFUTED, `python commands/assemble_commands.py --check` is green, and the ticket's commit is pushed (docs/reference/operating-manifesto.md:4)
- **Given** the rendered command at the box path named in Scope and its source `commands/_sources/fabrik-deploy-verify.md`, **When** it is evaluated against checklist item 63b's six intersections (docs/reference/command-evaluation-checklist.md § Governance Chain), **Then** the ticket's review artifact records a written verdict per intersection — CONFORMS at path:line · FIXED at path:line · N/A because X — with zero unadjudicated intersections (commands/_sources/fabrik-deploy-verify.md:2)
- **Given** fixes applied to `commands/_sources/fabrik-deploy-verify.md` (and a fragment only on a NEW fragment-level finding T01 did not sweep), **When** /fabrik-review runs on the ticket's changed surface, **Then** it converges to a new: 0 round with every finding FIXED or REFUTED, `python commands/assemble_commands.py --check` is green, and the ticket's commit is pushed (docs/reference/operating-manifesto.md:4)
- **Given** the rendered command at the box path named in Scope and its source `commands/_sources/fabrik-doc-converge.md`, **When** it is evaluated against checklist item 63b's six intersections (docs/reference/command-evaluation-checklist.md § Governance Chain), **Then** the ticket's review artifact records a written verdict per intersection — CONFORMS at path:line · FIXED at path:line · N/A because X — with zero unadjudicated intersections (commands/_sources/fabrik-doc-converge.md:2)
- **Given** fixes applied to `commands/_sources/fabrik-doc-converge.md` (and a fragment only on a NEW fragment-level finding T01 did not sweep), **When** /fabrik-review runs on the ticket's changed surface, **Then** it converges to a new: 0 round with every finding FIXED or REFUTED, `python commands/assemble_commands.py --check` is green, and the ticket's commit is pushed (docs/reference/operating-manifesto.md:4)
- **Given** the rendered command at the box path named in Scope and its source `commands/_sources/fabrik-docs-review.md`, **When** it is evaluated against checklist item 63b's six intersections (docs/reference/command-evaluation-checklist.md § Governance Chain), **Then** the ticket's review artifact records a written verdict per intersection — CONFORMS at path:line · FIXED at path:line · N/A because X — with zero unadjudicated intersections (commands/_sources/fabrik-docs-review.md:2)
- **Given** fixes applied to `commands/_sources/fabrik-docs-review.md` (and a fragment only on a NEW fragment-level finding T01 did not sweep), **When** /fabrik-review runs on the ticket's changed surface, **Then** it converges to a new: 0 round with every finding FIXED or REFUTED, `python commands/assemble_commands.py --check` is green, and the ticket's commit is pushed (docs/reference/operating-manifesto.md:4)
- **Given** the rendered command at the box path named in Scope and its source `commands/_sources/fabrik-execute-plan.md`, **When** it is evaluated against checklist item 63b's six intersections (docs/reference/command-evaluation-checklist.md § Governance Chain), **Then** the ticket's review artifact records a written verdict per intersection — CONFORMS at path:line · FIXED at path:line · N/A because X — with zero unadjudicated intersections (commands/_sources/fabrik-execute-plan.md:2)
- **Given** fixes applied to `commands/_sources/fabrik-execute-plan.md` (and a fragment only on a NEW fragment-level finding T01 did not sweep), **When** /fabrik-review runs on the ticket's changed surface, **Then** it converges to a new: 0 round with every finding FIXED or REFUTED, `python commands/assemble_commands.py --check` is green, and the ticket's commit is pushed (docs/reference/operating-manifesto.md:4)
- **Given** the rendered command at the box path named in Scope and its source `commands/_sources/fabrik-features.md`, **When** it is evaluated against checklist item 63b's six intersections (docs/reference/command-evaluation-checklist.md § Governance Chain), **Then** the ticket's review artifact records a written verdict per intersection — CONFORMS at path:line · FIXED at path:line · N/A because X — with zero unadjudicated intersections (commands/_sources/fabrik-features.md:2)
- **Given** fixes applied to `commands/_sources/fabrik-features.md` (and a fragment only on a NEW fragment-level finding T01 did not sweep), **When** /fabrik-review runs on the ticket's changed surface, **Then** it converges to a new: 0 round with every finding FIXED or REFUTED, `python commands/assemble_commands.py --check` is green, and the ticket's commit is pushed (docs/reference/operating-manifesto.md:4)
- **Given** the rendered command at the box path named in Scope and its source `commands/_sources/fabrik-flows.md`, **When** it is evaluated against checklist item 63b's six intersections (docs/reference/command-evaluation-checklist.md § Governance Chain), **Then** the ticket's review artifact records a written verdict per intersection — CONFORMS at path:line · FIXED at path:line · N/A because X — with zero unadjudicated intersections (commands/_sources/fabrik-flows.md:2)
- **Given** fixes applied to `commands/_sources/fabrik-flows.md` (and a fragment only on a NEW fragment-level finding T01 did not sweep), **When** /fabrik-review runs on the ticket's changed surface, **Then** it converges to a new: 0 round with every finding FIXED or REFUTED, `python commands/assemble_commands.py --check` is green, and the ticket's commit is pushed (docs/reference/operating-manifesto.md:4)
- **Given** the rendered command at the box path named in Scope and its source `commands/_sources/fabrik-flows-review.md`, **When** it is evaluated against checklist item 63b's six intersections (docs/reference/command-evaluation-checklist.md § Governance Chain), **Then** the ticket's review artifact records a written verdict per intersection — CONFORMS at path:line · FIXED at path:line · N/A because X — with zero unadjudicated intersections (commands/_sources/fabrik-flows-review.md:2)
- **Given** fixes applied to `commands/_sources/fabrik-flows-review.md` (and a fragment only on a NEW fragment-level finding T01 did not sweep), **When** /fabrik-review runs on the ticket's changed surface, **Then** it converges to a new: 0 round with every finding FIXED or REFUTED, `python commands/assemble_commands.py --check` is green, and the ticket's commit is pushed (docs/reference/operating-manifesto.md:4)
- **Given** the rendered command at the box path named in Scope and its source `commands/_sources/fabrik-generate-tests.md`, **When** it is evaluated against checklist item 63b's six intersections (docs/reference/command-evaluation-checklist.md § Governance Chain), **Then** the ticket's review artifact records a written verdict per intersection — CONFORMS at path:line · FIXED at path:line · N/A because X — with zero unadjudicated intersections (commands/_sources/fabrik-generate-tests.md:2)
- **Given** fixes applied to `commands/_sources/fabrik-generate-tests.md` (and a fragment only on a NEW fragment-level finding T01 did not sweep), **When** /fabrik-review runs on the ticket's changed surface, **Then** it converges to a new: 0 round with every finding FIXED or REFUTED, `python commands/assemble_commands.py --check` is green, and the ticket's commit is pushed (docs/reference/operating-manifesto.md:4)
- **Given** the rendered command at the box path named in Scope and its source `commands/_sources/fabrik-plan-after-chat.md`, **When** it is evaluated against checklist item 63b's six intersections (docs/reference/command-evaluation-checklist.md § Governance Chain), **Then** the ticket's review artifact records a written verdict per intersection — CONFORMS at path:line · FIXED at path:line · N/A because X — with zero unadjudicated intersections (commands/_sources/fabrik-plan-after-chat.md:2)
- **Given** fixes applied to `commands/_sources/fabrik-plan-after-chat.md` (and a fragment only on a NEW fragment-level finding T01 did not sweep), **When** /fabrik-review runs on the ticket's changed surface, **Then** it converges to a new: 0 round with every finding FIXED or REFUTED, `python commands/assemble_commands.py --check` is green, and the ticket's commit is pushed (docs/reference/operating-manifesto.md:4)
- **Given** the rendered command at the box path named in Scope and its source `commands/_sources/fabrik-plan-review.md`, **When** it is evaluated against checklist item 63b's six intersections (docs/reference/command-evaluation-checklist.md § Governance Chain), **Then** the ticket's review artifact records a written verdict per intersection — CONFORMS at path:line · FIXED at path:line · N/A because X — with zero unadjudicated intersections (commands/_sources/fabrik-plan-review.md:2)
- **Given** fixes applied to `commands/_sources/fabrik-plan-review.md` (and a fragment only on a NEW fragment-level finding T01 did not sweep), **When** /fabrik-review runs on the ticket's changed surface, **Then** it converges to a new: 0 round with every finding FIXED or REFUTED, `python commands/assemble_commands.py --check` is green, and the ticket's commit is pushed (docs/reference/operating-manifesto.md:4)
- **Given** the rendered command at the box path named in Scope and its source `commands/_sources/fabrik-release.md`, **When** it is evaluated against checklist item 63b's six intersections (docs/reference/command-evaluation-checklist.md § Governance Chain), **Then** the ticket's review artifact records a written verdict per intersection — CONFORMS at path:line · FIXED at path:line · N/A because X — with zero unadjudicated intersections (commands/_sources/fabrik-release.md:2)
- **Given** fixes applied to `commands/_sources/fabrik-release.md` (and a fragment only on a NEW fragment-level finding T01 did not sweep), **When** /fabrik-review runs on the ticket's changed surface, **Then** it converges to a new: 0 round with every finding FIXED or REFUTED, `python commands/assemble_commands.py --check` is green, and the ticket's commit is pushed (docs/reference/operating-manifesto.md:4)
- **Given** the rendered command at the box path named in Scope and its source `commands/_sources/fabrik-repo-review.md`, **When** it is evaluated against checklist item 63b's six intersections (docs/reference/command-evaluation-checklist.md § Governance Chain), **Then** the ticket's review artifact records a written verdict per intersection — CONFORMS at path:line · FIXED at path:line · N/A because X — with zero unadjudicated intersections (commands/_sources/fabrik-repo-review.md:2)
- **Given** fixes applied to `commands/_sources/fabrik-repo-review.md` (and a fragment only on a NEW fragment-level finding T01 did not sweep), **When** /fabrik-review runs on the ticket's changed surface, **Then** it converges to a new: 0 round with every finding FIXED or REFUTED, `python commands/assemble_commands.py --check` is green, and the ticket's commit is pushed (docs/reference/operating-manifesto.md:4)
- **Given** the rendered command at the box path named in Scope and its source `commands/_sources/fabrik-review.md`, **When** it is evaluated against checklist item 63b's six intersections (docs/reference/command-evaluation-checklist.md § Governance Chain), **Then** the ticket's review artifact records a written verdict per intersection — CONFORMS at path:line · FIXED at path:line · N/A because X — with zero unadjudicated intersections (commands/_sources/fabrik-review.md:2)
- **Given** fixes applied to `commands/_sources/fabrik-review.md` (and a fragment only on a NEW fragment-level finding T01 did not sweep), **When** /fabrik-review runs on the ticket's changed surface, **Then** it converges to a new: 0 round with every finding FIXED or REFUTED, `python commands/assemble_commands.py --check` is green, and the ticket's commit is pushed (docs/reference/operating-manifesto.md:4)
- **Given** the rendered command at the box path named in Scope and its source `commands/_sources/fabrik-review-scoped.md`, **When** it is evaluated against checklist item 63b's six intersections (docs/reference/command-evaluation-checklist.md § Governance Chain), **Then** the ticket's review artifact records a written verdict per intersection — CONFORMS at path:line · FIXED at path:line · N/A because X — with zero unadjudicated intersections (commands/_sources/fabrik-review-scoped.md:2)
- **Given** fixes applied to `commands/_sources/fabrik-review-scoped.md` (and a fragment only on a NEW fragment-level finding T01 did not sweep), **When** /fabrik-review runs on the ticket's changed surface, **Then** it converges to a new: 0 round with every finding FIXED or REFUTED, `python commands/assemble_commands.py --check` is green, and the ticket's commit is pushed (docs/reference/operating-manifesto.md:4)
- **Given** the rendered command at the box path named in Scope and its source `commands/_sources/fabrik-rivals.md`, **When** it is evaluated against checklist item 63b's six intersections (docs/reference/command-evaluation-checklist.md § Governance Chain), **Then** the ticket's review artifact records a written verdict per intersection — CONFORMS at path:line · FIXED at path:line · N/A because X — with zero unadjudicated intersections (commands/_sources/fabrik-rivals.md:2)
- **Given** fixes applied to `commands/_sources/fabrik-rivals.md` (and a fragment only on a NEW fragment-level finding T01 did not sweep), **When** /fabrik-review runs on the ticket's changed surface, **Then** it converges to a new: 0 round with every finding FIXED or REFUTED, `python commands/assemble_commands.py --check` is green, and the ticket's commit is pushed (docs/reference/operating-manifesto.md:4)
- **Given** the rendered command at the box path named in Scope and its source `commands/_sources/fabrik-rules-review.md`, **When** it is evaluated against checklist item 63b's six intersections (docs/reference/command-evaluation-checklist.md § Governance Chain), **Then** the ticket's review artifact records a written verdict per intersection — CONFORMS at path:line · FIXED at path:line · N/A because X — with zero unadjudicated intersections (commands/_sources/fabrik-rules-review.md:2)
- **Given** fixes applied to `commands/_sources/fabrik-rules-review.md` (and a fragment only on a NEW fragment-level finding T01 did not sweep), **When** /fabrik-review runs on the ticket's changed surface, **Then** it converges to a new: 0 round with every finding FIXED or REFUTED, `python commands/assemble_commands.py --check` is green, and the ticket's commit is pushed (docs/reference/operating-manifesto.md:4)
- **Given** the rendered command at the box path named in Scope and its source `commands/_sources/fabrik-service-test.md`, **When** it is evaluated against checklist item 63b's six intersections (docs/reference/command-evaluation-checklist.md § Governance Chain), **Then** the ticket's review artifact records a written verdict per intersection — CONFORMS at path:line · FIXED at path:line · N/A because X — with zero unadjudicated intersections (commands/_sources/fabrik-service-test.md:2)
- **Given** fixes applied to `commands/_sources/fabrik-service-test.md` (and a fragment only on a NEW fragment-level finding T01 did not sweep), **When** /fabrik-review runs on the ticket's changed surface, **Then** it converges to a new: 0 round with every finding FIXED or REFUTED, `python commands/assemble_commands.py --check` is green, and the ticket's commit is pushed (docs/reference/operating-manifesto.md:4)
- **Given** the rendered command at the box path named in Scope and its source `commands/_sources/fabrik-spec.md`, **When** it is evaluated against checklist item 63b's six intersections (docs/reference/command-evaluation-checklist.md § Governance Chain), **Then** the ticket's review artifact records a written verdict per intersection — CONFORMS at path:line · FIXED at path:line · N/A because X — with zero unadjudicated intersections (commands/_sources/fabrik-spec.md:2)
- **Given** fixes applied to `commands/_sources/fabrik-spec.md` (and a fragment only on a NEW fragment-level finding T01 did not sweep), **When** /fabrik-review runs on the ticket's changed surface, **Then** it converges to a new: 0 round with every finding FIXED or REFUTED, `python commands/assemble_commands.py --check` is green, and the ticket's commit is pushed (docs/reference/operating-manifesto.md:4)
- **Given** the rendered command at the box path named in Scope and its source `commands/_sources/fabrik-spec-review.md`, **When** it is evaluated against checklist item 63b's six intersections (docs/reference/command-evaluation-checklist.md § Governance Chain), **Then** the ticket's review artifact records a written verdict per intersection — CONFORMS at path:line · FIXED at path:line · N/A because X — with zero unadjudicated intersections (commands/_sources/fabrik-spec-review.md:2)
- **Given** fixes applied to `commands/_sources/fabrik-spec-review.md` (and a fragment only on a NEW fragment-level finding T01 did not sweep), **When** /fabrik-review runs on the ticket's changed surface, **Then** it converges to a new: 0 round with every finding FIXED or REFUTED, `python commands/assemble_commands.py --check` is green, and the ticket's commit is pushed (docs/reference/operating-manifesto.md:4)
- **Given** the rendered command at the box path named in Scope and its source `commands/_sources/fabrik-ui-design.md`, **When** it is evaluated against checklist item 63b's six intersections (docs/reference/command-evaluation-checklist.md § Governance Chain), **Then** the ticket's review artifact records a written verdict per intersection — CONFORMS at path:line · FIXED at path:line · N/A because X — with zero unadjudicated intersections (commands/_sources/fabrik-ui-design.md:2)
- **Given** fixes applied to `commands/_sources/fabrik-ui-design.md` (and a fragment only on a NEW fragment-level finding T01 did not sweep), **When** /fabrik-review runs on the ticket's changed surface, **Then** it converges to a new: 0 round with every finding FIXED or REFUTED, `python commands/assemble_commands.py --check` is green, and the ticket's commit is pushed (docs/reference/operating-manifesto.md:4)
- **Given** the rendered command at the box path named in Scope and its source `commands/_sources/fabrik-ui-design-review.md`, **When** it is evaluated against checklist item 63b's six intersections (docs/reference/command-evaluation-checklist.md § Governance Chain), **Then** the ticket's review artifact records a written verdict per intersection — CONFORMS at path:line · FIXED at path:line · N/A because X — with zero unadjudicated intersections (commands/_sources/fabrik-ui-design-review.md:2)
- **Given** fixes applied to `commands/_sources/fabrik-ui-design-review.md` (and a fragment only on a NEW fragment-level finding T01 did not sweep), **When** /fabrik-review runs on the ticket's changed surface, **Then** it converges to a new: 0 round with every finding FIXED or REFUTED, `python commands/assemble_commands.py --check` is green, and the ticket's commit is pushed (docs/reference/operating-manifesto.md:4)
- **Given** the rendered command at the box path named in Scope and its source `commands/_sources/fabrik-upstream.md`, **When** it is evaluated against checklist item 63b's six intersections (docs/reference/command-evaluation-checklist.md § Governance Chain), **Then** the ticket's review artifact records a written verdict per intersection — CONFORMS at path:line · FIXED at path:line · N/A because X — with zero unadjudicated intersections (commands/_sources/fabrik-upstream.md:2)
- **Given** fixes applied to `commands/_sources/fabrik-upstream.md` (and a fragment only on a NEW fragment-level finding T01 did not sweep), **When** /fabrik-review runs on the ticket's changed surface, **Then** it converges to a new: 0 round with every finding FIXED or REFUTED, `python commands/assemble_commands.py --check` is green, and the ticket's commit is pushed (docs/reference/operating-manifesto.md:4)
- **Given** the rendered command at the box path named in Scope and its source `commands/_sources/fabrik-user-test.md`, **When** it is evaluated against checklist item 63b's six intersections (docs/reference/command-evaluation-checklist.md § Governance Chain), **Then** the ticket's review artifact records a written verdict per intersection — CONFORMS at path:line · FIXED at path:line · N/A because X — with zero unadjudicated intersections (commands/_sources/fabrik-user-test.md:2)
- **Given** fixes applied to `commands/_sources/fabrik-user-test.md` (and a fragment only on a NEW fragment-level finding T01 did not sweep), **When** /fabrik-review runs on the ticket's changed surface, **Then** it converges to a new: 0 round with every finding FIXED or REFUTED, `python commands/assemble_commands.py --check` is green, and the ticket's commit is pushed (docs/reference/operating-manifesto.md:4)
- **Given** the rendered command at the box path named in Scope and its source `commands/_sources/fabrik-workflow-review.md`, **When** it is evaluated against checklist item 63b's six intersections (docs/reference/command-evaluation-checklist.md § Governance Chain), **Then** the ticket's review artifact records a written verdict per intersection — CONFORMS at path:line · FIXED at path:line · N/A because X — with zero unadjudicated intersections (commands/_sources/fabrik-workflow-review.md:2)
- **Given** fixes applied to `commands/_sources/fabrik-workflow-review.md` (and a fragment only on a NEW fragment-level finding T01 did not sweep), **When** /fabrik-review runs on the ticket's changed surface, **Then** it converges to a new: 0 round with every finding FIXED or REFUTED, `python commands/assemble_commands.py --check` is green, and the ticket's commit is pushed (docs/reference/operating-manifesto.md:4)
- **Given** all 33 work tickets merged, **When** the whole-plan receipt runs `python scripts/final_gate.py --check --json` + `python scripts/enforcement/check_convergence.py` + `python scripts/enforcement/check_doc_sync.py` and /fabrik-docs-review over the corpus docs, **Then** every command's 63b verdict table exists (32/32 + fragments), the gate reports success, and the receipt records the per-ticket commit list (docs/reference/command-evaluation-checklist.md:158)

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

Largest command ticket READ set = 73,670 (fabrik-execute-plan source) + 9,550 (manifesto) + 29,741
(checklist) + 40-documentation pack ≈ 120 KB < READ_BUDGET_BYTES 262,144. T01's set = 67,514 (all
fragments) + 39,291 + pack ≈ 112 KB. Every ticket fits.

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
  Scope; the fix routes as a normal spontaneous edit outside the plan, per CLAUDE.md, or waits for T34's
  Deltas. Named here so the executor does not stall on it).
