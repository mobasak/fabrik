# T06 receipt — shared fragments: design, deploy and certification (full form)

- **Start commit (baseline):** `61d1f4b99c6a8188a281f86799268fe54ee1b5d1` (origin/kaizen-lean-u01)
- **Branch:** `claude/lean-t06`
- **Rule:** D-1236 as narrowed by D-1240 (coverage test, ban clause verbatim to the end of its `;`/`—` clause), D-1238 points 1-2. The loader at the start commit has no `class`/`clauses` keys (`_ENTRY` = id,file,section,baseline,current,text,ordered,forbidden,enforced,pins,changed-by), so each entry records its class as a `# class:` YAML comment and each clause labelled narrative/duplicate-of as a `# clauses: {L<baseline line>.<clause n>: narrative | {duplicate-of: id}}` comment (clauses split at `;` and `—` outside backticks, numbered from 1); the hub converts them to keys when the canonical loader lands. `commands/command_rules.py`, `tests/test_command_rules.py` and every other tooling file are untouched.

## Own text, words before -> after

| file | words before (`wc -w`) | after | % of baseline | own-text units before -> after (words, frontmatter excluded) |
|---|---|---|---|---|
| `commands/_fragments/design-critique.md` | 817 | 799 | 97% | 808 -> 790 (97%) |
| `commands/_fragments/design-gate-panel.md` | 653 | 625 | 95% | 648 -> 620 (95%) |
| `commands/_fragments/deploy-chain.md` | 364 | 330 | 90% | 364 -> 330 (90%) |
| `commands/_fragments/cert-board-contract.md` | 1124 | 922 | 82% | 1126 -> 924 (82%) |
| `commands/_fragments/cert-execution.md` | 617 | 586 | 94% | 614 -> 583 (94%) |
| `commands/_fragments/cert-handoff-grammar.md` | 280 | 263 | 93% | 280 -> 263 (93%) |
| `commands/_fragments/cert-visual-deliverable.md` | 153 | 84 | 54% | 152 -> 83 (54%) |
| `commands/_fragments/autonomy-run.md` | 1173 | 1092 | 93% | 1166 -> 1085 (93%) |
| `commands/_agents/design-review.md` | 831 | 795 | 95% | 652 -> 616 (94%) |
| **total** | **6012** | **5496** | **91%** | **5810 -> 5294 (91%)** |

## Entries by ledger and class

| ledger | entries | reworded | ban | grammar | behavioural | prose | vanished (rule / narrative / duplicate-of) |
|---|---|---|---|---|---|---|---|
| `design-critique.yaml` | 22 | 2 | 7 | 0 | 0 | 15 | 2 / 1 / 0 |
| `design-gate-panel.yaml` | 19 | 3 | 6 | 0 | 0 | 13 | 3 / 0 / 0 |
| `deploy-chain.yaml` | 14 | 3 | 3 | 0 | 0 | 11 | 3 / 0 / 0 |
| `cert-board-contract.yaml` | 31 | 11 | 16 | 0 | 0 | 15 | 11 / 3 / 0 |
| `cert-execution.yaml` | 17 | 5 | 7 | 0 | 0 | 10 | 5 / 0 / 0 |
| `cert-handoff-grammar.yaml` | 5 | 4 | 4 | 0 | 0 | 1 | 4 / 0 / 0 |
| `cert-visual-deliverable.yaml` | 3 | 2 | 0 | 0 | 0 | 3 | 2 / 0 / 0 |
| `autonomy-run.yaml` | 38 | 8 | 19 | 0 | 0 | 19 | 7 / 0 / 0 |
| `design-review.yaml` | 44 | 4 | 2 | 0 | 0 | 42 | 3 / 1 / 0 |
| **total** | **193** | **42** | | | | | |

Class assignment: `ban` = the unit holds a never/must/only/refuse word (D-1238 point 2; the entry's carrier holds the same token and the clause verbatim from the ban word to the end of its `;`/`—` clause); `grammar` = none (every grammar-bearing fence/row is either unchanged or carried inside a `ban` unit); `behavioural` = none: no phrase of these nine files is asserted by a test on EMITTED output (the kept readers `test_certification_coverage.py`, `test_check_command_corpus.py`, `test_review_loop_workflow.py` are plain string-in-file asserts, and every phrase they pin is kept verbatim, so those tests stay green unedited); `prose` = the rest.

## Reworded entries: clause count and how each clause is covered

A reworded entry's single `text` carrier is its whole current unit (so one phrase holds every anchor of every clause and the clause stems are held by the same phrase). Clause coverage was checked by an executable script (anchor presence, >=70% of the first 8 content stems, ban clause verbatim) over each baseline clause against its carrier; "label" means the clause is recorded narrative in the entry's `# clauses:` comment.

| entry | baseline L | clauses | coverage |
|---|---|---|---|
| `design-critique`: dcr-u4 | L5 | 2 | 1: phrase; 2: phrase |
| `design-critique`: dcr-u15 | L17 | 7 | 1: phrase; 2: phrase; 3: phrase; 4: phrase; 5: phrase; 6: phrase; 7: phrase |
| `design-gate-panel`: dgp-u1 | L2 | 1 | 1: phrase |
| `design-gate-panel`: dgp-u7 | L8 | 6 | 1: phrase; 2: phrase; 3: phrase; 4: phrase; 5: phrase; 6: phrase |
| `design-gate-panel`: dgp-u12 | L13 | 1 | 1: phrase |
| `deploy-chain`: dc-u2 | L3 | 2 | 1: phrase; 2: phrase |
| `deploy-chain`: dc-u8 | L9 | 2 | 1: phrase; 2: phrase |
| `deploy-chain`: dc-u14 | L15 | 2 | 1: phrase; 2: label narrative |
| `cert-board-contract`: cbc-u1 | L2 | 1 | 1: phrase |
| `cert-board-contract`: cbc-u3 | L4 | 2 | 1: phrase; 2: label narrative |
| `cert-board-contract`: cbc-u4 | L6 | 2 | 1: phrase; 2: phrase |
| `cert-board-contract`: cbc-u9 | L12 | 1 | 1: phrase |
| `cert-board-contract`: cbc-u15 | L18 | 2 | 1: phrase; 2: label narrative |
| `cert-board-contract`: cbc-u18 | L21 | 3 | 1: phrase; 2: label narrative; 3: phrase |
| `cert-board-contract`: cbc-u20 | L23 | 6 | 1: phrase; 2: label narrative; 3: phrase; 4: phrase; 5: phrase; 6: phrase |
| `cert-board-contract`: cbc-u21 | L24 | 3 | 1: phrase; 2: phrase; 3: label narrative |
| `cert-board-contract`: cbc-u22 | L25 | 3 | 1: phrase; 2: phrase; 3: phrase |
| `cert-board-contract`: cbc-u23 | L26 | 2 | 1: phrase; 2: label narrative |
| `cert-board-contract`: cbc-u24 | L27 | 2 | 1: phrase; 2: label narrative |
| `cert-execution`: ce-u0 | L1 | 2 | 1: phrase; 2: phrase |
| `cert-execution`: ce-u3 | L4 | 2 | 1: phrase; 2: phrase |
| `cert-execution`: ce-u6 | L7 | 1 | 1: phrase |
| `cert-execution`: ce-u9 | L10 | 2 | 1: phrase; 2: phrase |
| `cert-execution`: ce-u17 | L18 | 2 | 1: phrase; 2: label narrative |
| `cert-handoff-grammar`: chg-u1 | L2 | 5 | 1: phrase; 2: phrase; 3: label narrative; 4: phrase; 5: phrase |
| `cert-handoff-grammar`: chg-u2 | L3 | 1 | 1: phrase |
| `cert-handoff-grammar`: chg-u3 | L4 | 3 | 1: phrase; 2: phrase; 3: phrase |
| `cert-handoff-grammar`: chg-u4 | L5 | 5 | 1: phrase; 2: phrase; 3: phrase; 4: phrase; 5: phrase |
| `cert-visual-deliverable`: cvd-u0 | L1 | 4 | 1: phrase; 2: phrase; 3: phrase; 4: label narrative |
| `cert-visual-deliverable`: cvd-u1 | L2 | 2 | 1: phrase; 2: phrase |
| `autonomy-run`: ar-u1, ar-u2 | L2 | 3 | 1: phrase; 2: phrase; 3: phrase |
| `autonomy-run`: ar-u7 | L7 | 2 | 1: phrase; 2: label narrative |
| `autonomy-run`: ar-u17 | L17 | 1 | 1: phrase |
| `autonomy-run`: ar-u18 | L18 | 2 | 1: phrase; 2: label narrative |
| `autonomy-run`: ar-u20 | L20 | 2 | 1: phrase; 2: phrase |
| `autonomy-run`: ar-u21 | L21 | 4 | 1: phrase; 2: phrase; 3: phrase; 4: label narrative |
| `autonomy-run`: ar-u27 | L27 | 3 | 1: phrase; 2: label narrative; 3: phrase |
| `design-review`: dr-u1 | L2 | 1 | 1: phrase |
| `design-review`: dr-u2 | L3 | 5 | 1: phrase; 2: phrase; 3: phrase; 4: phrase; 5: phrase |
| `design-review`: dr-u8 | L9 | 1 | 1: phrase |

## Pins deleted

None. Every phrase a test pins in these nine files survives verbatim in the rewritten text, so no test file was edited (spec step 7 deletes a presence pin only when its phrase no longer survives; the Touches test files are untouched, which keeps the merge with the other workers' edits to them mechanical). Kept-verbatim phrases the readers pin: `deploy-chain.md` needles of `tests/test_check_command_corpus.py::test_every_deploy_chain_command_carries_the_shared_order_and_repo_block` (`**PROJECT**`, `**HUB**`, `Gate 2`, the five command names); `design-critique.md` phrases of `tests/test_review_loop_workflow.py` ("copy the project's own file to the scratchpad and name it by that", "the md5 standing in for a commit wherever line", "one plain command per Bash call"); `cert-board-contract.md` phrases of `tests/enforcement/test_certification_coverage.py` ("zero mapped IDs cannot be reported as working", "The dispatcher's default unit is a CODER, so an unrouted test ticket puts a coding agent on a browser job."); and the literals of the Touches tests (`test_design_critique_fragment`, `test_plan_review_queue_pass`, `test_plan_review_recurring_rules`, `test_seat_home_read_rule`, `test_spec_review_queue_pass`, `test_fabrik_task_queue_pass`, `test_frontend_design_routing`), all found by the step-2 scan and re-run green.

## Vanished labels (author labels — audit owed)

### `design-critique.yaml` — 3 vanished lines
- L5: **rule dcr-u4** — `the design artifact pinned by md5 (the spec, plan, flows or UI contract, or the phase-2 `design.md`) and the c…`
- L13: **narrative** — `Fable runs on metered usage credits…`
- L17: **rule dcr-u15** — ``ACCEPTED` — the change is applied, and reviewed before anyone approves it: in spec-review and plan-review it …`

### `design-gate-panel.yaml` — 3 vanished lines
- L2: **rule dgp-u1** — `Their brief adds what the operator would weigh: the artifacts this one builds on or feeds (spec, plan, flows, …`
- L8: **rule dgp-u7** — `Before the round that reviews the revision is pinned, each change is written beside the ACCEPTED concern it an…`
- L13: **rule dgp-u12** — `Brief the operator in at most ten lines under the heading `PANEL APPROVED (<artifact path>)`: what the file is…`

### `deploy-chain.yaml` — 3 vanished lines
- L3: **rule dc-u2** — `Run each step where its row says — a step run in the wrong repo either cannot see its inputs (a project has no…`
- L9: **rule dc-u8** — `| 3 | `/fabrik-deploy-plan` | the HUB (`/opt/fabrik`) for VPS surfaces · the PROJECT for store surfaces (mobil…`
- L15: **rule dc-u14** — `The contract freezes on the CERTIFIED build — certification produces fixes, and fixes move exactly what the co…`

### `cert-board-contract.yaml` — 14 vanished lines
- L2: **rule cbc-u1** — `⚠️ The denominator comes from a live REGISTRY, not from this list and not from a doc. The four discovery modes…`
- L4: **rule cbc-u3** — `A registry that cannot be reached fails LOUD naming what could not be enumerated — a silently short list rebui…`
- L5: **narrative** — `Why: the inventory used to be PROSE WITH COUNTS, authored by the agent later graded against it, and nothing re…`
- L6: **rule cbc-u4** — `On a surface the project authored, the agent's enumeration and reality converge and this never bites; on an IN…`
- L7: **narrative** — `Measured on a `saas-skeleton` wrapping a vendored ERP, immediately after a genuine md5-verified `/fabrik-featu…`
- L12: **rule cbc-u9** — `The heading is load-bearing: `/fabrik-execute-plan`'s dispatcher triggers on that bare string, so a mis-headed…`
- L18: **rule cbc-u15** — ``DEFERRED` is REJECTED, with its synonyms — a "later" state is the loophole that lets the whole contract be ig…`
- L21: **rule cbc-u18** — `Evidence discipline: the board's `evidence/` dir is NEVER a runner's `--output` dir (runners WIPE their output…`
- L23: **rule cbc-u20** — `And recording stays OUT of the grader by design — a checker that can also mark things done will eventually mar…`
- L24: **rule cbc-u21** — `The fifth oracle — reference-data reconciliation (trade-intelligence `01M1580AH`, 2026-08-29). The UI-truth-vs…`
- L25: **rule cbc-u22** — `So for every journey whose output is ADJUDICATED CONTENT (levies, prices, entitlements, computed rows), at lea…`
- L26: **rule cbc-u23** — `No independent reference reachable → say so in the ledger (`reference-reconciliation: unavailable — <why>`); a…`
- L27: **rule cbc-u24** — `The demoted doc inventory keeps its teeth. Demoting `docs/FEATURES.md` to a cross-check does NOT mean discardi…`
- L34: **narrative** — `That is the retest loop, structurally…`

### `cert-execution.yaml` — 5 vanished lines
- L1: **rule ce-u0** — `Done ONLY when a full round reports `new inventory: 0 · new findings: 0 · fixes applied: 0` — TWO consecutive …`
- L4: **rule ce-u3** — `A matrix cell deliberately skipped is listed SKIPPED with a reason — silent shrinkage of the inventory or matr…`
- L7: **rule ce-u6** — `Work the HANDED-OFF list on a hard schedule (no budget-feel exits): T3 doc re-freezes first (cheap, bounded) →…`
- L10: **rule ce-u9** — `T2 batch cap: more than 3 distinct owning modules on the list is a SYSTEMIC signal (the phase-boundary reviews…`
- L18: **rule ce-u17** — `After the last code-changing row closes, run one full Phase-5 round (fresh discovery sweep + full reconcile — …`

### `cert-handoff-grammar.yaml` — 4 vanished lines
- L2: **rule chg-u1** — `A CLOSED row without an existing repro path + proof fails the gate; an OPEN row routed to `/fabrik-review` (th…`
- L3: **rule chg-u2** — `Severity is ASSIGNED by blast radius, not vibes (`/fabrik-release` BLOCKS on P0/P1 and operator-WARNs P2/P3, s…`
- L4: **rule chg-u3** — `When torn between two tiers, take the HIGHER — the operator can waive down (their waiver mints its ledger row)…`
- L5: **rule chg-u4** — `Only the two `HANDOFF` forms carry the digit — `DESIGN-GAP` rows have NO severity slot in the parsed grammar; …`

### `cert-visual-deliverable.yaml` — 2 vanished lines
- L1: **rule cvd-u0** — `⚠️ VISUAL-DELIVERABLE QA — if a journey's deliverable IS a visual artifact, the proof is EYES ON THE RENDERED …`
- L2: **rule cvd-u1** — `For EVERY image/PDF/SVG/favicon/video-frame deliverable: RENDER it (rasterize PDFs + SVGs first), then INSPECT…`

### `autonomy-run.yaml` — 7 vanished lines
- L2: **rule ar-u1, ar-u2** — `This certification runs start→finish in ONE invocation, fully autonomously. You do NOT pause to ask, to narrat…`
- L7: **rule ar-u7** — ``grep` / `Read` the codebase — the router / handler / schema / the actual symbol…`
- L17: **rule ar-u17** — `"I judged this worth asking," "running low on context, I'll finish later," "the core is covered, the rest can …`
- L18: **rule ar-u18** — `(Context is not a reason: the harness AUTO-COMPACTS long conversations and the run continues — your durable-as…`
- L20: **rule ar-u20** — `Post-compact, the SessionStart hook auto-injects a recent-context recap, and the `session-recall` MCP (`search…`
- L21: **rule ar-u21** — `A HARD STOP always overrides — this contract AND the Termination contract below; it is never a "routable findi…`
- L27: **rule ar-u27** — `Any other finding — a contract↔code contradiction on one field/flow, a degradable gap — is routed, not halted:…`

### `design-review.yaml` — 4 vanished lines
- L2: **rule dr-u1** — `You conduct world-class design reviews following the rigorous standards of top Silicon Valley companies like S…`
- L3: **rule dr-u2** — `The git-verb prohibition (spec D8): NO git command that mutates state in the shared tree — no stash, checkout,…`
- L9: **rule dr-u8** — `Analyze the PR description to understand motivation, changes, and testing notes (or just the description of th…`
- L51: **narrative** — `Example: Instead of "Change margin to 16px", say "The spacing feels inconsistent with adjacent elements, creat…`


## Floor — own text is 91% of baseline, not 50%

Zero LOSS is held; the 50% target is not met, and this ticket names the floor instead. Per file (table above): 82-97% for eight files and 54% for `cert-visual-deliverable.md`. Live rule count: 193 ledger entries over the nine files, 64 of them `ban` units; 42 entries are reworded and the rest survive byte-for-byte.

Why the files do not halve under D-1240 without dropping a rule:

1. **A ban clause is verbatim from its ban word to the end of its `;`/`—` clause** (D-1240), and these files are dense with never/must/only/refuse. The baseline's own punctuation decides how much a ban clause drags along: where a ban clause runs to the end of a sentence it keeps the whole sentence, anecdote and parenthetical included (`cert-board-contract` baseline L6, L31, L40; `autonomy-run` L33, L35; `design-gate-panel` L8). A clause holding a ban word cannot be labelled narrative or duplicate-of.
2. **Every other kept clause is a distinct rule, a required-items list or a procedure step.** What this ticket cut: every clause that was history, an incident story, an example or a reason carrying no rule, and restated sentences — 15 clauses and 5 whole lines, each labelled in its ledger (see "Vanished labels"). Cutting a list item or a step's object to reach 8 stems would drop a rule the author-blind audit reads as LOST, so the remaining clauses are kept whole.
3. **Reader-test pins.** Phrases pinned by `test_certification_coverage`, `test_check_command_corpus` and `test_review_loop_workflow` are kept verbatim by the ticket; phrases pinned by the Touches tests are kept too, so no test file was edited (a pin deleted only to cut text would make the merge with the other workers' edits to the same test files non-mechanical).

The 41 clauses still more than 8 words over their anchors-plus-8-stems minimum (clause split at `;`/`—`; minimum = first 8 content stems + anchors, ban tail whole), each with why it cannot shrink:

| file | baseline clause (first words) | words | minimum (anchors + 8 stems; ban tail whole) | why it cannot shrink |
|---|---|---|---|---|
| `design-critique` | L1.3 dispatch two author-blind critique seats in ONE message: `fa… | 23 | 13 | phrase pinned by a reader test that this ticket keeps green (kept verbatim) |
| `design-critique` | L5.1 the design artifact pinned by md5 (the spec, plan, flows or … | 24 | 11 | list of required items; each item is a distinct rule (dropping any one loses it) |
| `design-critique` | L5.2 a cited fleet-synced file (`scripts/enforcement/`, `.windsur… | 55 | 12 | phrase pinned by a reader test that this ticket keeps green (kept verbatim) |
| `design-critique` | L7.3 the absolute scratchpad when the line reads `none` or is abs… | 42 | 20 | phrase pinned by a reader test that this ticket keeps green (kept verbatim) |
| `design-critique` | L11.2 each with an anchor (section or line), the claim, its eviden… | 41 | 10 | phrase pinned by a reader test that this ticket keeps green (kept verbatim) |
| `design-critique` | L16.1 Once both critiques are in hand (the stand-in Opus seat's wh… | 34 | 9 | list of required items; each item is a distinct rule (dropping any one loses it) |
| `design-critique` | L17.3 that round is a delta round of the same loop, so its own-fix… | 32 | 9 | phrase pinned by a reader test that this ticket keeps green (kept verbatim) |
| `design-critique` | L17.4 residue a delta round raises AFTER the stop fired is `RECORD… | 40 | 10 | phrase pinned by a reader test that this ticket keeps green (kept verbatim) |
| `design-critique` | L17.5 an artifact already CONVERGED at HEAD, re-reviewed, goes bac… | 24 | 11 | phrase pinned by a reader test that this ticket keeps green (kept verbatim) |
| `design-critique` | L20.1 Run the step once per artifact version: an md5 already criti… | 31 | 19 | phrase pinned by a reader test that this ticket keeps green (kept verbatim) |
| `design-critique` | L24.1 The counter: a critique that names no concern AND no attack … | 23 | 9 | procedure step; the tail carries a condition or an object of the step |
| `design-gate-panel` | L2.1 Their brief adds what the operator would weigh: the artifact… | 44 | 12 | phrase pinned by a reader test that this ticket keeps green (kept verbatim) |
| `design-gate-panel` | L6.1 When Fable is unavailable, the second Opus seat stands in an… | 18 | 10 | procedure step; the tail carries a condition or an object of the step |
| `design-gate-panel` | L8.1 Before the round that reviews the revision is pinned, each c… | 49 | 29 | ban clause whose comma list (objects of the ban) must stay verbatim to the end of the clause (D-1240) |
| `design-gate-panel` | L8.3 the code line it describes, a decision row, an artifact sect… | 28 | 9 | list of required items; each item is a distinct rule (dropping any one loses it) |
| `design-gate-panel` | L14.1 In autonomy mode the Stop hook checks that line against the … | 22 | 9 | procedure step; the tail carries a condition or an object of the step |
| `deploy-chain` | L10.1 | 4 | `/fabrik-deploy-plan-review` | the same repo as the pl… | 24 | 12 | phrase pinned by a reader test that this ticket keeps green (kept verbatim) |
| `cert-board-contract` | L9.1 Two generated artifacts and one hand-written recipe, all ins… | 20 | 9 | procedure step; the tail carries a condition or an object of the step |
| `cert-board-contract` | L12.1 The heading is load-bearing: `/fabrik-execute-plan`'s dispat… | 28 | 10 | phrase pinned by a reader test that this ticket keeps green (kept verbatim) |
| `cert-board-contract` | L19.1 `inherited` / `vendored` / `generated` / `legacy` / `low pri… | 40 | 14 | phrase pinned by a reader test that this ticket keeps green (kept verbatim) |
| `cert-board-contract` | L20.6 beside the spine, `ledger.md` and the `runtime.md` recipe ar… | 20 | 12 | anchor-dense: every backticked token is an anchor |
| `cert-board-contract` | L24.2 reference-data reconciliation (trade-intelligence `01M1580AH… | 51 | 43 | ban clause: head holds the condition the ban applies to |
| `cert-board-contract` | L25.1 So for every journey whose output is ADJUDICATED CONTENT (le… | 29 | 9 | list of required items; each item is a distinct rule (dropping any one loses it) |
| `cert-board-contract` | L25.3 asserting not just that rendered rows are right but that eve… | 22 | 9 | procedure step; the tail carries a condition or an object of the step |
| `cert-board-contract` | L28.1 A large divergence between the doc inventory and the registr… | 17 | 9 | procedure step; the tail carries a condition or an object of the step |
| `cert-board-contract` | L32.1 The dispatcher's default unit is a CODER, so an unrouted tes… | 20 | 9 | phrase pinned by a reader test that this ticket keeps green (kept verbatim) |
| `cert-execution` | L8.3 seeded with exactly: the committed red repro path, the ownin… | 21 | 11 | procedure step; the tail carries a condition or an object of the step |
| `cert-handoff-grammar` | L2.2 an OPEN row routed to `/fabrik-review` (the code-wrong route… | 23 | 11 | procedure step; the tail carries a condition or an object of the step |
| `cert-visual-deliverable` | L1.2 if a journey's deliverable IS a visual artifact, the proof i… | 46 | 10 | list of required items; each item is a distinct rule (dropping any one loses it) |
| `cert-visual-deliverable` | L2.1 For EVERY image/PDF/SVG/favicon/video-frame deliverable: REN… | 21 | 10 | procedure step; the tail carries a condition or an object of the step |
| `cert-visual-deliverable` | L2.2 fan them across artifact classes, adjudicate yourself) again… | 30 | 9 | list of required items; each item is a distinct rule (dropping any one loses it) |
| `autonomy-run` | L9.2 and if it truly stops you establishing the oracle to run at … | 23 | 15 | ban clause: head holds the condition the ban applies to |
| `autonomy-run` | L13.1 a defect you do not own ({{HANDOFF}}) → write the failing re… | 37 | 13 | ban clause whose comma list (objects of the ban) must stay verbatim to the end of the clause (D-1240) |
| `autonomy-run` | L13.2 the run does not wait for the other owner mid-sweep, and the… | 17 | 9 | procedure step; the tail carries a condition or an object of the step |
| `autonomy-run` | L14.1 Where a Phase 6 exists (the certification gauntlets), the ro… | 21 | 10 | procedure step; the tail carries a condition or an object of the step |
| `autonomy-run` | L17.1 "I judged this worth asking," "running low on context, I'll … | 32 | 9 | list of required items; each item is a distinct rule (dropping any one loses it) |
| `autonomy-run` | L34.1 On re-invocation after a crash / quota-hit / disconnect / ki… | 44 | 9 | procedure step; the tail carries a condition or an object of the step |
| `autonomy-run` | L38.1 Every gauntlet subagent runs its suite as a plain synchronou… | 21 | 9 | procedure step; the tail carries a condition or an object of the step |
| `design-review` | L1.1 You are an elite design review specialist with deep expertis… | 19 | 9 | list of required items; each item is a distinct rule (dropping any one loses it) |
| `design-review` | L2.1 You conduct world-class design reviews following the rigorou… | 19 | 9 | procedure step; the tail carries a condition or an object of the step |
| `design-review` | L68.1 Your goal is to ensure the highest quality user experience w… | 17 | 9 | procedure step; the tail carries a condition or an object of the step |

The hub mints the floor D-row (live rule count x the U1 words-per-rule figure); this ticket mints none (Steps 6 and 9).

## Gates

- `python3 -m pytest -q tests/test_command_rules.py -rP`: 32 passed, 3 skipped. Its PASSES section prints one `LEDGER` line per ledger, nine of them this ticket's: `autonomy-run`, `cert-board-contract`, `cert-execution`, `cert-handoff-grammar`, `cert-visual-deliverable`, `deploy-chain`, `design-critique`, `design-gate-panel`, `design-review`; zero LOSS lines.
- `python3 commands/assemble_commands.py --check`: exit 1 at the start commit and at the end; every DRIFT line reads `DIFFERS from what this tree renders` or `MISSING in /root/.claude/agents` (the clone has no installed corpus); 0 other DRIFT lines, no LOSS, no ORPHAN, no ceiling line other than `REPORT … shrank … lowered by assemble_commands.py --ratchet at merge`.
- Reader-test run (spine § Global Constraints, the stem listing of the nine files + the corpus-glob listing + the seven tests the ticket names; 46 files), through `python3 -m pytest -q` (the clone has no `capped_run.sh`):
  - start commit: 53 failed, 2319 passed, 10 skipped, 1 warning in 359.44s (0:05:59)
  - end: 53 failed, 2319 passed, 10 skipped, 1 warning in 360.05s (0:06:00)
  - failures that are new at the end: 0 
  - failures at the start that pass at the end: 0
  - the failure set at the start commit (all box-service or environment reds of the clone: `test_fabrik_deck`, `test_generate_capability_index`, `test_quota_dashboard`, `test_review_queue_pass::test_a_cwd_rooted_tool_runs_after_an_os_chdir` and the like): 53; none is in a Touches file this ticket edited (no test file was edited).

## LEFT FOR THE HUB

- The author-blind Sonnet + Haiku audit of every reworded entry (old against new) and of the vanished labels ("author labels — audit owed"): the Step-5 classification pair cannot run in this clone.
- The review wave over the nine ledgers and the nine rewritten files.
- The floor D-row for the nine files (above).
- The ceiling ratchet of `commands/_size_ceiling.json` at merge (Step 7); the file is untouched.
- Converting the `# class:` and `# clauses:` comments to keys once the canonical loader (`class`, `clauses` in `_ENTRY`) lands.
- `CHANGELOG.md`, the `INDEX.md` rows for the eighteen new files under `commands/_rules/_shared/` (nine ledgers, nine baselines) and any D-row: written by the hub at merge.

## SELF-AUDIT (before the push)

Inputs: the `baseline_sentences:` file of each ledger at the start commit, the rewritten file, its ledger. Method: an executable clause audit (every baseline clause, split at `;`/`—` outside backticks, checked against its carrier entry for anchor presence — backticked tokens, numbers, ban words —, at least 70% of its first 8 content stems, and the ban clause verbatim from the ban word to the clause end; a clause labelled narrative/duplicate-of is refused if it holds a ban word), plus a by-eye read of the diff for the four checks. Earlier passes fixed: ban tails and anchors restored in `design-gate-panel` L8 (`must still pass …`, `must reach …`), `autonomy-run` L5 (`must behave`), L32 (`test-only dependency …`), L2/L13, `cert-board-contract` L27 (`That clause survived …`), `cert-execution` L3/L13, `design-critique` L11 (SQL-predicate clause), `deploy-chain` row 3 and L2, and the wrong labels `deploy-chain` L2 (duplicate-of a table header), `design-review` L2/L5/L68 (persona/goal sentences that carry a rule) — all restored or relabelled.

COUNTS: entries read 193 / reworded 42 / weaker 0 / lost 0 / invented 0 / wrong vanished labels 0
