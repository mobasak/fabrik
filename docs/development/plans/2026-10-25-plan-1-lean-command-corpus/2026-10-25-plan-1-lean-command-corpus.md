# Lean command corpus — the rewrite plan set

Status: IN-PROGRESS
**Owner:** kaizen
Spec: `docs/superpowers/specs/2026-10-25-lean-command-corpus-design.md` (Status: CONVERGED, D-1217, D-1219) · Work item: W-96f36043 (the P0 lean program, D-1216) · Plan decisions: D-1222

## What we already agreed

- The goal and the measure: every `/fabrik-*` command's own text at or under 50% of its baseline, or a recorded floor, with no rule lost (spec § Target, § The rule test, § Binding).
- The order: tooling first, then the `/fabrik-review-scoped` pilot, then the remaining shared files, `/fabrik-review`, `/fabrik-task`, `/fabrik-execute-plan`, `/fabrik-command-improve`, then the rest by hours in the light form (spec § Order).
- The levers and their limits (spec § How a command is cut, § Time budget); the loop changes L1 and L2 (spec § Loop changes); the holds (spec § Program holds).
- Coordinator ruling (a), 2026-10-25: the rewrites run in hub windows as a normal plan set for `/fabrik-execute-plan`, sequential in the agreed order; no batch emitter, D-1213 stays in force (cloud drain unused).
- The coordinator, starting this plan: "one self-contained ticket per command in the agreed order … panel floor, lean seat briefs, finders via intel's API lane when it lands", and three filed findings fold into the fragment tickets (W-6effedda, W-9ad5860f, W-f723cb66).
- infra-2, owner of the tooling (W-a9b5e763), 2026-10-25: slice A merges on its own as soon as its full review closes, and B and C follow as separate merge requests; command tickets keep off `commands/command_rules.py`, `commands/assemble_commands.py`, `commands/_size_ceiling.json`, `scripts/command_run.py` and `scripts/command_feedback_report.py`; C drafts the `remove:` sentence in `close-feedback.md` (kaizen's answer).

## Intake Inventory

| I# | Item (anchored) | Disposition | Where |
|---|---|---|---|
| I1 | the converged spec is the plan's source (spec Status: CONVERGED) | IN | every ticket cites it |
| I2 | ruling (a): "hub windows … sequential in the agreed order" | IN | § Execution Discipline, § Merge Order |
| I3 | "one self-contained ticket per command in the agreed order" | IN | § Ticket Board; a unit over the READ budget splits into pin-migration tickets plus its rewrite (D-1222) |
| I4 | "panel floor" seats | IN | § Execution Discipline |
| I5 | "lean seat briefs" (the question and the pin) | IN | § Execution Discipline, and lever T4 in T01d |
| I6 | "finders via intel's API lane when it lands" (W-230abfd5) | IN | § Execution Discipline |
| I7 | the three filed findings W-6effedda, W-9ad5860f, W-f723cb66 | IN | the pilot shared-file unit (T01a-T01d) |
| I8 | no `/fabrik-command-improve` run until L1 and L2 land | IN | § Global Constraints; it lifts at the L2 merge (spec § Program holds) |
| I9 | the tooling (W-a9b5e763) is infra-2's, as three merge requests | IN | § Interfaces (precondition merges), not a dispatched ticket (D-1222) |
| I10 | the § Lifecycle notes for the tooling: the frozen sample's source is the after-window report, a window with fewer than 5 fast-closed surfaces samples them all, and "confirmed defects per run" joins the measure list | IN | § Interfaces, the time measure's delivery list |
| I11 | intel's W-0a91bf86 measuring scripts are untracked (`docs/development/reviews/2026-10-25-w-0a91bf86-lean-program-phase-wall-clock.md:96`) | IN | § Residual unknowns R4; intel commits it (W-487e966a) and infra-2 pins it |
| I12 | the W-9ad5860f half in `.claude/workflows/fabrik-review-loop.js` | OUT-OF-SCOPE | intel's beat; the item W-9ad5860f stays open with intel |
| I13 | lever T1's spread to `/fabrik-repo-review` | OUT-OF-SCOPE | after `/fabrik-review`'s after-window report (spec § Time budget); kaizen opens that item at the report (§ Execution Discipline) |
| I14 | the after-window reports, frozen samples and cobra counters | OUT-OF-SCOPE | kaizen's § Lifecycle duties after each merge; one kaizen work item per landed top-four unit (§ Execution Discipline) |

Intake: 14 items — 11 IN, 3 OUT-OF-SCOPE (each named above), 0 ASK.

## Global Constraints

- Every ticket waits for its preconditions (§ Interfaces), each probed on master by what landed, never by a merge's name:
  - T01a: `git show origin/master:.fabrik/work/W-487e966a.json | python3 -c "import json,sys; print(json.load(sys.stdin)['status'])"` prints `done` (after `git fetch`; `dropped` means the coordinator names the replacement), `scripts/command_time_measure.py` exists, `commands/command_rules.py` holds `def generate_unchanged`, and `commands/_size_ceiling.json` exists;
  - T01a: neither `.fabrik/plan-locks/2026-10-21-plan-3-own-scrape-slice-1a.json` nor `.fabrik/plan-locks/2026-10-22-plan-1-least-operator-approval.json` lists a path this plan's § File Scope lists, while it is `active` (R9);
  - T10: `scripts/command_run.py` holds L2's `remove:` field.
- The `/fabrik-command-improve` hold (spec § Program holds) stands until the L2 merge, the last tooling piece, lands; kaizen tells the coordinator in that turn. Until then kaizen runs no `/fabrik-command-improve`, and the rows keep accumulating.
- The coordinator freezes non-program edits to a unit's files from its first ticket's start to its merge (spec § Target).
- A unit's baseline is taken at its first ticket's start commit, never earlier (spec § Target).
- Ledger grammar is slice A's, exactly:
  - The ledger file is `commands/_rules/<cmd>.yaml` with `command:`, or `commands/_rules/_shared/<name>.yaml` with `shared: <repo path>`.
  - Every ledger needs `baseline_sentences:` (a `<name>.baseline.txt` beside it) and `baseline_sha256:`.
  - Each entry is `{id, file, section, baseline, current}` plus at least one carrier: `text`, `ordered`, `forbidden` or `enforced`. Unknown keys are refused.
  - `vanished:` is keyed `L<n>`, each value `narrative`, `{rule: [ids]}` or `{duplicate-of: id}`.
  - `file:` paths are repo-relative.
- A single-command fragment (`scope-growth-exit`, `judge-panel`, `agent-feedback`) takes the `shared:` form, because a command ledger's baseline covers the source alone (D-1222).
- A corpus-text pin test has its presence pins migrated into the ledger in its unit. A behavioural test (it drives code) keeps its pins, and the ledger carries each pinned phrase verbatim, so the rewrite never edits it (D-1222).
- A test outside a ticket's Touches that the rewrite turns red is a Touches miss. The orchestrator adds it to that ticket's Touches and to § File Scope in an amendment commit before the ticket merges. It is never skipped, xfailed or left red.
- No ticket edits a tooling file: `commands/command_rules.py`, `commands/assemble_commands.py`, `commands/_size_ceiling.json`, `scripts/command_run.py`, `scripts/command_feedback_report.py`, `tests/test_command_rules.py`. `commands/_size_ceiling.json` is in a rewrite ticket's Touches only because the text-measure merge's ratchet writes it in that ticket's commit; no hand edit, as infra-2 agreed (§ What we already agreed).
- **The reader-test run.** Every ticket that cuts a file runs every test that reads it, whatever its role. At the ticket's start, from the repo root, list (1) per cut file's stem, the tests naming it: `command grep -rlE --include='*.py' "<stem>(\.md|['\"/}])" tests/`; and (2) the tests that glob a corpus directory by path and name no stem: `python3 -c "import pathlib,re; print(' '.join(str(p) for p in sorted(pathlib.Path('tests').rglob('test_*.py')) if re.search(r'\.r?glob\(', t := p.read_text(errors='replace')) and re.search(r'commands/_(sources|fragments|agents)|[\"\'/]_(sources|fragments|agents)[\"\'/]', t)))"`. Run their union through `/opt/fabrik/scripts/capped_run.sh -- .venv/bin/python -m pytest -q <the files>` once at the start commit, recording its reds, and again before the merge. That run is the net for every pin the step-2 literal scan misses: a pin under 25 characters, a regex or structure assert, or a phrase the test normalises differently. A test red at the end and green at the start is a Touches miss (the rule above); one already red at the start is reported, not owned.
- A test assert that relates two files, or loops over several commands (the same sentence in two files, a minimum count of copies, a list of commands), is never migrated into one unit's ledger, because a ledger grades one file. It stays, the reader-test run keeps it green, and each unit it names keeps the asserted text verbatim.
- A kept test that asserts raw text (a line break, emphasis) holds the rewrite to those bytes, though the ledger normalises them; the reader-test run is the check.
- In a rewrite ticket, the presence pins to delete are listed by running step 2's snippet over the Touches tests against the start-commit file.
- A ledger entry's `current` is one whole unit as `command_rules.units()` returns it: a sentence as its splitter cuts it, a whole table row, or a fence joined with ` ⏎ `.
- `units()` drops a leading frontmatter block. So a rule in an agent definition's frontmatter (`tools`, `disallowedTools`, `model`, `omitClaudeMd`, a ban in `description`) is carried by an entry with `section: ""`, `current: ""` and the phrase as a `text` carrier, which `_check` grades against the whole live file.
- L2's `close-feedback.md` sentence lands before T01a starts, so the baseline holds it, or after unit 01 merges, carrying its own entry in `commands/_rules/_shared/close-feedback.yaml`; never inside unit 01's freeze.
- A ticket's 50% row grades each file it cuts: a source by `command_rules.own_text`, a shared file whole, both in words. A command's own text in spec § Target (its render plus its kaizen-owned reads) is the sum of those files, so it is halved when every one of them is. Floors break that sum, so T46 tabulates the per-command figure.
- The worktree never renders. `python3 commands/assemble_commands.py --check` is safe because it renders to a temp dir. The coordinator renders at merge (`CLAUDE.md` § Behavior, merge-time render only).
- Tests run through `/opt/fabrik/scripts/capped_run.sh -- .venv/bin/python -m pytest …` and never bare. No seat runs a package-manager verb.
- 12-Factor non-negotiables, inherited though this plan writes only Markdown, YAML and tests:
  - logs are unbuffered JSON to stdout only, never a logfile (XI);
  - migrations never run from startup (XII);
  - the same backing services in dev, test and prod (X);
  - no sticky sessions (VI), no daemonizing or PID files (VIII);
  - workers requeue on SIGTERM (IX);
  - releases are immutable (V);
  - config is granular env vars with no secrets in code (III);
  - shelled-out binaries are pinned (II).

## Constraints Digest

| Quote | Source |
|---|---|
| this table is its project-facing rendering, kept in step, never a second truth | `.windsurf/rules/core/40-documentation.md:94` |
| No skipped heading levels — ## to ###, never ## to #### | `.windsurf/rules/core/40-documentation.md:242` |
| Fenced code blocks only — never indented code | `.windsurf/rules/core/40-documentation.md:244` |
| Watch it fail first, or neuter the change → prove red → restore → re-run green | `.windsurf/rules/core/45-testing-strategy.md:201` |
| No cosmetic assertions: never assert against CSS classes | `.windsurf/rules/core/45-testing-strategy.md:21` |
| is the mandated Python package manager. Never use raw pip, pip install, poetry, or pipenv. | `.windsurf/rules/core/10-python.md:22` |
| with the unit split, the author-blind rule (§ Role separation) and the decide/refute/merge you own | `.windsurf/rules/core/62-using-subagents.md:38` |

Selections against it: a ticket's ledger is the single source of a rule's wording, with no second copy left in a pin test (row 1). Rewritten Markdown keeps heading levels and fenced code (rows 2-3). A changed pin test is proven red-on-revert in the unit's full review (row 4). Pins assert text the agent acts on, never layout (row 5). Seats run `.venv/bin/python` and no package-manager verb (row 6). Every classification pair and panel pair is author-blind, and the orchestrator decides, refutes and merges (row 7).

## Context Ledger

| Source | What binds | Grounded ref |
|---|---|---|
| `.windsurf/rules/core/40-documentation.md` (MATCHED) | one source of truth; heading and fence form of the rewritten Markdown | `.windsurf/rules/core/40-documentation.md:94`, `:242`, `:244` |
| `.windsurf/rules/core/45-testing-strategy.md` (MATCHED) | pin-test edits proven red-on-revert; no cosmetic asserts | `.windsurf/rules/core/45-testing-strategy.md:201` |
| `.windsurf/rules/core/10-python.md` (FLOOR) | no package-manager verb from a seat | `.windsurf/rules/core/10-python.md:22` |
| `.windsurf/rules/core/62-using-subagents.md` (MATCHED) | native seats, author-blind, orchestrator decides | `.windsurf/rules/core/62-using-subagents.md:38` |
| `fabrik-lib` | none: spec § fabrik-lib verdict builds every capability, hub-internal | `docs/superpowers/specs/2026-10-25-lean-command-corpus-design.md:410` |
| `agents-fabrik.md` | no infra invariant touched (no compose, port, DB or deploy surface) | `agents-fabrik.md` § Planning Constraints, read by its heading |
| `specs/services/*.yaml` `shape:` | none: no service changes | n/a |
| `docs/data-contract.md`, `docs/ui-design.md` | none: the hub has neither, and this plan builds no UI | n/a |
| The tooling (W-a9b5e763 slice A) | the ledger grammar and the functions every ticket calls | `commands/command_rules.py::vanished`, `::own_text`, `::write_baseline`, `::losses` on master since merge bc2a9c30b (D-1221; by symbol, since later slices move its lines) |

## Execution Discipline (binding on /fabrik-execute-plan)

- **Review floor.** Every ticket, on the coder's return, runs `/fabrik-review` on its changed surface to a coverage-adjudicated exit BEFORE its merge; no ticket merges on a first-pass green. It is the full review, because every command source is a governance-sync path (spec § Review and landing). Its seats include the rule test's audit pair, which reports any `current` weaker than its `baseline`, and a ban dropped by a positive rewrite.
- **Dispatch policy.**
  - Native Claude seats through the `Agent` tool only; the hub never calls the `Workflow` tool (D-961).
  - The coder is a native worktree coder: Sonnet by default, Opus for the full-form rewrite tickets (T02, T07c, T08, T09, T10).
  - Each rewrite's vanished-unit classification is two author-blind seats in one message, one Sonnet and one Haiku. The orchestrator adjudicates their union.
  - Rule changes go to an Opus + Fable panel in one message, each seat blind to the other: T1, T4, every floor and the KILL test (spec § Time budget, § Binding).
  - Every brief carries only its question and its pin (lever T4), at the panel floor.
  - Review finders run through intel's API-credit lane (`scripts/api_credit.py run`, W-230abfd5) once that item is done, because it spares the weekly quota. Until then they are native `fabrik-reviewer` seats.
- **Parallelism + merge.** Nothing fans out between tickets: ruling (a) runs the units one after another, and the Depends chain is linear.
  - Fan-out happens only inside a ticket: the classification pair, the panel pair and the review's finders. Each merges in the orchestrator, who dedupes and adjudicates every union before acting.
  - A unit is one merge: its migration tickets and its rewrite land as one merge request to the coordinator, sent at its last ticket's close. The next unit's baseline is then master's.
  - After each of the top-four units (T02, T07c, T08, T09) merges, kaizen opens one work item for that command's after-window report (spec § Lifecycle, § Time budget).

## Ticket Board

| Ticket | Title | Depends | Parallel | State | Commit |
|---|---|---|---|---|---|
| T01a | Pilot shared files: the fragments and seat definitions /fabrik-review-scoped shares — ledger and pin migration, part a | — | ⛓️ | 🔵 | |
| T01b | Pilot shared files: the fragments and seat definitions /fabrik-review-scoped shares — ledger and pin migration, part b | T01a | ⛓️ | ⬜ | |
| T01c | Pilot shared files: the fragments and seat definitions /fabrik-review-scoped shares — ledger and pin migration, part c | T01b | ⛓️ | ⬜ | |
| T01d | Pilot shared files: the fragments and seat definitions /fabrik-review-scoped shares — the rewrite | T01c | ⛓️ | ⬜ | |
| T02 | Lean rewrite of /fabrik-review-scoped (full form) | T01d | ⛓️ | ⬜ | |
| T03a | Shared fragment term-coverage — ledger and pin migration, part a | T02 | ⛓️ | ⬜ | |
| T03b | Shared fragment term-coverage — ledger and pin migration, part b | T03a | ⛓️ | ⬜ | |
| T03c | Shared fragment term-coverage — the rewrite | T03b | ⛓️ | ⬜ | |
| T04a | Shared fragment term-edit — ledger and pin migration, part a | T03c | ⛓️ | ⬜ | |
| T04b | Shared fragment term-edit — ledger and pin migration, part b | T04a | ⛓️ | ⬜ | |
| T04c | Shared fragment term-edit — the rewrite | T04b | ⛓️ | ⬜ | |
| T05a | Shared fragments: subagents-core and the grounding, intake and test-loop fragments — ledger and pin migration, part a | T04c | ⛓️ | ⬜ | |
| T05b | Shared fragments: subagents-core and the grounding, intake and test-loop fragments — ledger and pin migration, part b | T05a | ⛓️ | ⬜ | |
| T05c | Shared fragments: subagents-core and the grounding, intake and test-loop fragments — the rewrite | T05b | ⛓️ | ⬜ | |
| T06 | Shared fragments: design, deploy and certification fragments plus the design-review seat | T05c | ⛓️ | ⬜ | |
| T07a | Lean rewrite of /fabrik-review (full form) — ledger and pin migration, part a | T06 | ⛓️ | ⬜ | |
| T07b | Lean rewrite of /fabrik-review (full form) — ledger and pin migration, part b | T07a | ⛓️ | ⬜ | |
| T07c | Lean rewrite of /fabrik-review (full form) — the rewrite | T07b | ⛓️ | ⬜ | |
| T08 | Lean rewrite of /fabrik-task (full form) | T07c | ⛓️ | ⬜ | |
| T09 | Lean rewrite of /fabrik-execute-plan (full form) | T08 | ⛓️ | ⬜ | |
| T10 | Lean rewrite of /fabrik-command-improve (full form) | T09 | ⛓️ | ⬜ | |
| T11 | Lean rewrite of /fabrik-spec (light form) | T10 | ⛓️ | ⬜ | |
| T12 | Lean rewrite of /fabrik-plan-review (light form) | T11 | ⛓️ | ⬜ | |
| T13 | Lean rewrite of /fabrik-plan-after-chat (light form) | T12 | ⛓️ | ⬜ | |
| T14 | Lean rewrite of /fabrik-spec-review (light form) | T13 | ⛓️ | ⬜ | |
| T15 | Lean rewrite of /fabrik-data-contract (light form) | T14 | ⛓️ | ⬜ | |
| T16 | Lean rewrite of /fabrik-docs-review (light form) | T15 | ⛓️ | ⬜ | |
| T17 | Lean rewrite of /fabrik-conformance-review (light form) | T16 | ⛓️ | ⬜ | |
| T18 | Lean rewrite of /fabrik-catchup (light form) | T17 | ⛓️ | ⬜ | |
| T19 | Lean rewrite of /fabrik-features (light form) | T18 | ⛓️ | ⬜ | |
| T20 | Lean rewrite of /fabrik-doc-converge (light form) | T19 | ⛓️ | ⬜ | |
| T21 | Lean rewrite of /fabrik-user-test (light form) | T20 | ⛓️ | ⬜ | |
| T22 | Lean rewrite of /fabrik-deploy-checklist (light form) | T21 | ⛓️ | ⬜ | |
| T23 | Lean rewrite of /fabrik-ui-design-review (light form) | T22 | ⛓️ | ⬜ | |
| T24 | Lean rewrite of /fabrik-ui-design (light form) | T23 | ⛓️ | ⬜ | |
| T25 | Lean rewrite of /fabrik-flows (light form) | T24 | ⛓️ | ⬜ | |
| T26 | Lean rewrite of /fabrik-service-test (light form) | T25 | ⛓️ | ⬜ | |
| T27 | Lean rewrite of /hibernate (light form) | T26 | ⛓️ | ⬜ | |
| T28 | Lean rewrite of /fabrik-flows-review (light form) | T27 | ⛓️ | ⬜ | |
| T29 | Lean rewrite of /design-review (light form) | T28 | ⛓️ | ⬜ | |
| T30 | Lean rewrite of /fabrik-upstream (light form) | T29 | ⛓️ | ⬜ | |
| T31 | Lean rewrite of /fabrik-release (light form) | T30 | ⛓️ | ⬜ | |
| T32 | Lean rewrite of /fabrik-vision (light form) | T31 | ⛓️ | ⬜ | |
| T33 | Lean rewrite of /fabrik-epics (light form) | T32 | ⛓️ | ⬜ | |
| T34 | Lean rewrite of /fabrik-epics-review (light form) | T33 | ⛓️ | ⬜ | |
| T35 | Lean rewrite of /fabrik-deploy (light form) | T34 | ⛓️ | ⬜ | |
| T36 | Lean rewrite of /fabrik-deploy-plan (light form) | T35 | ⛓️ | ⬜ | |
| T37 | Lean rewrite of /fabrik-deploy-verify (light form) | T36 | ⛓️ | ⬜ | |
| T38 | Lean rewrite of /fabrik-deploy-plan-review (light form) | T37 | ⛓️ | ⬜ | |
| T39 | Lean rewrite of /fabrik-repo-review (light form) | T38 | ⛓️ | ⬜ | |
| T40 | Lean rewrite of /fabrik-rivals (light form) | T39 | ⛓️ | ⬜ | |
| T41 | Lean rewrite of /fabrik-decommission (light form) | T40 | ⛓️ | ⬜ | |
| T42 | Lean rewrite of /fabrik-generate-tests (light form) | T41 | ⛓️ | ⬜ | |
| T43 | Lean rewrite of /fabrik-rules-review (light form) | T42 | ⛓️ | ⬜ | |
| T44 | Lean rewrite of /fabrik-reverse-engineer (light form) | T43 | ⛓️ | ⬜ | |
| T45 | Lean rewrite of /fabrik-workflow-review (light form) | T44 | ⛓️ | ⬜ | |
| T46 | Integration: close-out evidence, whole-plan gates and the review receipt | T45 | ⛓️ | ⬜ | |

## Merge Order

1. T01a
2. T01b
3. T01c
4. T01d
5. T02
6. T03a
7. T03b
8. T03c
9. T04a
10. T04b
11. T04c
12. T05a
13. T05b
14. T05c
15. T06
16. T07a
17. T07b
18. T07c
19. T08
20. T09
21. T10
22. T11
23. T12
24. T13
25. T14
26. T15
27. T16
28. T17
29. T18
30. T19
31. T20
32. T21
33. T22
34. T23
35. T24
36. T25
37. T26
38. T27
39. T28
40. T29
41. T30
42. T31
43. T32
44. T33
45. T34
46. T35
47. T36
48. T37
49. T38
50. T39
51. T40
52. T41
53. T42
54. T43
55. T44
56. T45
57. T46

## Units

A unit is one command or one shared-file group. A unit whose files and corpus-text pin tests exceed the READ budget (262144 bytes) splits into migration tickets, which move its pins into its ledger, and a final rewrite ticket. All of a unit's tickets land as one merge (D-1222).

Breadth advisory (`check_ticket_breadth.py`, plan-review pass 1): 46 of 57 tickets score ≥ 5, every flag `areas=1 (commands)` (T46: docs-only), scored on its Behavior-Contract rows alone. Kept, not split: a rewrite ticket's rows (the start-commit ledger with no LOSS, the 50% target or a floor, every vanished unit labelled, bans and pinned phrases carried verbatim, presence pins migrated, `--check` never 4 or 5) are facets of ONE invariant, no rule lost in this file's cut, and a split would put the ledger and the cut it grades in different tickets.

| Unit | Tickets | Files cut | Kept behavioural pin tests |
|---|---|---|---|
| 01 | T01a, T01b, T01c, T01d | `no-workflow-hub.md`, `run-record.md`, `orient.md`, `close-chain.md`, `close-feedback.md`, `review-probe-catalogue.md`, `fabrik-reviewer.md`, `fabrik-researcher.md`, `fabrik-gui.md` | `test_command_feedback_report.py`, `test_command_run.py`, `test_review_loop_workflow.py` |
| 02 | T02 | `fabrik-review-scoped.md`, `scope-growth-exit.md` | `test_assemble_dispatch_step.py`, `test_governance_template_split.py`, `test_review_loop_workflow.py` |
| 03 | T03a, T03b, T03c | `term-coverage.md` | `test_review_exit_contract.py`, `test_review_loop_workflow.py`, `test_review_receipt.py` |
| 04 | T04a, T04b, T04c | `term-edit.md` | `test_review_exit_contract.py`, `test_review_refusals.py`, `test_assemble_dispatch_step.py`, `test_review_loop_workflow.py`, `test_review_receipt.py` |
| 05 | T05a, T05b, T05c | `subagents-core.md`, `delegated-reads.md`, `grounding-artifact.md`, `grounding-code.md`, `grounding-rules.md`, `questionbar.md`, `injection.md`, `test-generation-loop.md`, `chat-intake.md`, `repo-identity.md` | `test_review_exit_contract.py`, `test_rule_grounding.py`, `test_dispatch_headroom.py`, `test_assemble_dispatch_step.py`, `test_review_loop_workflow.py` |
| 06 | T06 | `design-critique.md`, `design-gate-panel.md`, `deploy-chain.md`, `cert-board-contract.md`, `cert-execution.md`, `cert-handoff-grammar.md`, `cert-visual-deliverable.md`, `autonomy-run.md`, `design-review.md` | `test_certification_coverage.py`, `test_check_command_corpus.py`, `test_review_loop_workflow.py` |
| 07 | T07a, T07b, T07c | `fabrik-review.md` | `test_review_refusals.py`, `test_assemble_dispatch_step.py`, `test_review_loop_workflow.py` |
| 08 | T08 | `fabrik-task.md` | `test_command_run_lane_v2.py` |
| 09 | T09 | `fabrik-execute-plan.md` | `test_assemble_dispatch_step.py`, `test_command_run.py`, `test_governance_template_split.py`, `test_mail_structure.py`, `test_review_loop_workflow.py` |
| 10 | T10 | `fabrik-command-improve.md`, `agent-feedback.md` | `test_command_feedback_report.py`, `test_command_improve_drive.py` |
| 11 | T11 | `fabrik-spec.md`, `judge-panel.md` | none |
| 12 | T12 | `fabrik-plan-review.md` | `test_rule_grounding.py`, `test_assemble_dispatch_step.py`, `test_review_loop_workflow.py` |
| 13 | T13 | `fabrik-plan-after-chat.md` | none |
| 14 | T14 | `fabrik-spec-review.md` | `test_check_convergence.py`, `test_final_gate_stop_deferral.py`, `test_gate_decision_blocks.py`, `test_review_loop_workflow.py` |
| 15 | T15 | `fabrik-data-contract.md` | `test_check_stage_artifacts.py` |
| 16 | T16 | `fabrik-docs-review.md` | `test_assemble_dispatch_step.py` |
| 17 | T17 | `fabrik-conformance-review.md` | `test_assemble_dispatch_step.py` |
| 18 | T18 | `fabrik-catchup.md` | none |
| 19 | T19 | `fabrik-features.md` | none |
| 20 | T20 | `fabrik-doc-converge.md` | `test_assemble_dispatch_step.py` |
| 21 | T21 | `fabrik-user-test.md` | none |
| 22 | T22 | `fabrik-deploy-checklist.md` | `test_check_command_corpus.py` |
| 23 | T23 | `fabrik-ui-design-review.md` | `test_assemble_dispatch_step.py`, `test_final_gate_stop_deferral.py`, `test_gate_decision_blocks.py` |
| 24 | T24 | `fabrik-ui-design.md` | `test_assemble_dispatch_step.py` |
| 25 | T25 | `fabrik-flows.md` | none |
| 26 | T26 | `fabrik-service-test.md` | none |
| 27 | T27 | `hibernate.md` | none |
| 28 | T28 | `fabrik-flows-review.md` | `test_final_gate_stop_deferral.py`, `test_gate_decision_blocks.py` |
| 29 | T29 | `design-review.md` | none |
| 30 | T30 | `fabrik-upstream.md` | none |
| 31 | T31 | `fabrik-release.md` | `test_chrome_launch_pack.py`, `test_final_gate_stop_deferral.py`, `test_gate_decision_blocks.py` |
| 32 | T32 | `fabrik-vision.md` | `test_vision_reads_work_stores.py` |
| 33 | T33 | `fabrik-epics.md` | `test_check_command_corpus.py` |
| 34 | T34 | `fabrik-epics-review.md` | `test_check_command_corpus.py`, `test_governance_template_split.py`, `test_vision_reads_work_stores.py` |
| 35 | T35 | `fabrik-deploy.md` | `test_check_command_corpus.py`, `test_final_gate_stop_deferral.py`, `test_gate_decision_blocks.py` |
| 36 | T36 | `fabrik-deploy-plan.md` | `test_check_command_corpus.py` |
| 37 | T37 | `fabrik-deploy-verify.md` | `test_check_command_corpus.py` |
| 38 | T38 | `fabrik-deploy-plan-review.md` | `test_check_command_corpus.py`, `test_final_gate_stop_deferral.py`, `test_gate_decision_blocks.py`, `test_review_loop_workflow.py` |
| 39 | T39 | `fabrik-repo-review.md` | `test_assemble_dispatch_step.py`, `test_review_loop_workflow.py` |
| 40 | T40 | `fabrik-rivals.md` | none |
| 41 | T41 | `fabrik-decommission.md` | `test_assemble_dispatch_step.py` |
| 42 | T42 | `fabrik-generate-tests.md` | none |
| 43 | T43 | `fabrik-rules-review.md` | none |
| 44 | T44 | `fabrik-reverse-engineer.md` | none |
| 45 | T45 | `fabrik-workflow-review.md` | none |

The tail, in its order (spec § Order step 6: descending hours, ties by own words; done closes since 2026-09-21 from `~/.claude/state/command-feedback.jsonl`):

| Command | Done runs since 09-21 | Hours | Own words today |
|---|---|---|---|
| `/fabrik-spec` | 149 | 161.9 | 9174 |
| `/fabrik-plan-review` | 156 | 146.1 | 7338 |
| `/fabrik-plan-after-chat` | 131 | 116.9 | 12052 |
| `/fabrik-spec-review` | 78 | 86.1 | 4830 |
| `/fabrik-data-contract` | 41 | 15.1 | 3491 |
| `/fabrik-docs-review` | 28 | 13.2 | 2781 |
| `/fabrik-conformance-review` | 8 | 8.7 | 2501 |
| `/fabrik-catchup` | 10 | 7.3 | 2323 |
| `/fabrik-features` | 12 | 5.9 | 1866 |
| `/fabrik-doc-converge` | 16 | 5.6 | 1654 |
| `/fabrik-user-test` | 1 | 4.5 | 5107 |
| `/fabrik-deploy-checklist` | 4 | 4.5 | 3816 |
| `/fabrik-ui-design-review` | 12 | 4.2 | 2867 |
| `/fabrik-ui-design` | 18 | 2.8 | 4362 |
| `/fabrik-flows` | 2 | 2.7 | 2831 |
| `/fabrik-service-test` | 1 | 1.9 | 3730 |
| `/hibernate` | 5 | 1.6 | 877 |
| `/fabrik-flows-review` | 2 | 1.4 | 2438 |
| `/design-review` | 1 | 1.0 | 1343 |
| `/fabrik-upstream` | 2 | 0.3 | 3653 |
| `/fabrik-release` | 1 | 0.1 | 2578 |
| `/fabrik-vision` | 0 | 0.0 | 13435 |
| `/fabrik-epics` | 0 | 0.0 | 7708 |
| `/fabrik-epics-review` | 0 | 0.0 | 7491 |
| `/fabrik-deploy` | 0 | 0.0 | 4893 |
| `/fabrik-deploy-plan` | 0 | 0.0 | 4780 |
| `/fabrik-deploy-verify` | 0 | 0.0 | 4577 |
| `/fabrik-deploy-plan-review` | 0 | 0.0 | 4324 |
| `/fabrik-repo-review` | 0 | 0.0 | 2893 |
| `/fabrik-rivals` | 0 | 0.0 | 2852 |
| `/fabrik-decommission` | 0 | 0.0 | 2565 |
| `/fabrik-generate-tests` | 0 | 0.0 | 2309 |
| `/fabrik-rules-review` | 0 | 0.0 | 2050 |
| `/fabrik-reverse-engineer` | 0 | 0.0 | 1627 |
| `/fabrik-workflow-review` | 0 | 0.0 | 1336 |

## Interfaces

- **Precondition merges (producer: infra-2, W-a9b5e763; consumer: every ticket).**
  - Slice A: `commands/command_rules.py` with `own_text`, `write_baseline`, `vanished`, `load_ledger` and `losses`, and the `--check` LOSS exit 4. On master since merge bc2a9c30b (D-1221; review receipt 4ce9a1a48, CONVERGED).
  - The text-measure merge (infra-2, W-a9b5e763), needed before T01a:
    - `command_rules.generate_unchanged(baseline_path, new_own_text) -> [entry]`, the measure, and `commands/_size_ceiling.json` with its ratchet and `--check` exit 5;
    - every command's full-measure baseline, published;
    - `changed-by` in the ledger grammar's entry keys, which T07c's T1 rule change needs (spec § The rule test step 8; requested of infra-2).
  - The time measure (intel, W-487e966a), needed before T01a: the D-1219 measuring script committed as `scripts/command_time_measure.py` with a fixture test; infra-2 then pins it by commit and runs it nightly with the kaizen digest. It must carry the frozen-sample source (the after-window report), the all-of-them rule for fewer than 5 fast-closed surfaces, and the confirmed-defects-per-run column.
  - The L2 merge (infra-2, W-a9b5e763), needed before T10: L2's `remove:` field in `scripts/command_run.py` and its grouping in `scripts/command_feedback_report.py`, plus the `remove:` sentence in `commands/_fragments/close-feedback.md`.
  - infra-2 names its own merges; the plan's earlier slice letters B and C are retired.
  - **Seam test:** `tests/test_command_rules.py`, owned by the producer and run read-only by every ticket's first Gate line. It auto-discovers the ledgers.
- **Shared ledgers (producers: T01a-T01d, T03a-T03c, T04a-T04c, T05a-T05c, T06; consumers: every later command unit).** `commands/_rules/_shared/<name>.yaml` asserts each shared file against itself. A command unit never re-ledgers or re-cuts a shared file. Its seam is the same `tests/test_command_rules.py` run.
- **Unit ledger across its tickets (producer: a unit's migration part a; consumer: its later parts and its rewrite).** Part a writes `<name>.baseline.txt` and the entries. A later ticket extends the ledger and never rewrites its baseline.
- **The pilot's words-per-rule figure (producer: T02; consumer: every floor D-row).** It is recorded in the pilot D-row (spec § Residual unknowns U1). T01d lands before it, so T01d proposes no floor of its own: a unit-01 file still over 50% is named in unit 01's merge as an open floor (T01d step 6), and T02's step 9 mints its floor D-row with the pilot figure.

## Behavior Contract

- **Given** the shared files `no-workflow-hub.md`, `run-record.md`, `orient.md`, `close-chain.md`, `close-feedback.md`, `review-probe-catalogue.md`, `fabrik-reviewer.md`, `fabrik-researcher.md`, `fabrik-gui.md` at the unit's start commit, **When** its baseline and ledger are written before any cut, **Then** `tests/test_command_rules.py` prints its LEDGER line with zero LOSS lines and the files are byte-identical to the start commit (spec § The rule test)
- **Given** the presence pins on the shared files `no-workflow-hub.md`, `run-record.md`, `orient.md`, `close-chain.md`, `close-feedback.md`, `review-probe-catalogue.md`, `fabrik-reviewer.md`, `fabrik-researcher.md`, `fabrik-gui.md` in the tests of migration part a, **When** this ticket commits, **Then** each is deleted and its phrase is a carrier in the ledger, and an absence pin is a `forbidden:` carrier or stays (spec § The rule test)
- **Given** the presence pins on the shared files `no-workflow-hub.md`, `run-record.md`, `orient.md`, `close-chain.md`, `close-feedback.md`, `review-probe-catalogue.md`, `fabrik-reviewer.md`, `fabrik-researcher.md`, `fabrik-gui.md` in the tests of migration part b, **When** this ticket commits, **Then** each is deleted and its phrase is a carrier in the ledger, and an absence pin is a `forbidden:` carrier or stays (spec § The rule test)
- **Given** the presence pins on the shared files `no-workflow-hub.md`, `run-record.md`, `orient.md`, `close-chain.md`, `close-feedback.md`, `review-probe-catalogue.md`, `fabrik-reviewer.md`, `fabrik-researcher.md`, `fabrik-gui.md` in the tests of migration part c, **When** this ticket commits, **Then** each is deleted and its phrase is a carrier in the ledger, and an absence pin is a `forbidden:` carrier or stays (spec § The rule test)
- **Given** the ledger for the shared files `no-workflow-hub.md`, `run-record.md`, `orient.md`, `close-chain.md`, `close-feedback.md`, `review-probe-catalogue.md`, `fabrik-reviewer.md`, `fabrik-researcher.md`, `fabrik-gui.md` written from its baseline own text at the unit's start commit, **When** `tests/test_command_rules.py` renders the corpus, **Then** it prints a LEDGER line for it with zero LOSS lines (spec § The rule test)
- **Given** the shared files `no-workflow-hub.md`, `run-record.md`, `orient.md`, `close-chain.md`, `close-feedback.md`, `review-probe-catalogue.md`, `fabrik-reviewer.md`, `fabrik-researcher.md`, `fabrik-gui.md` rewritten, **When** its own text is counted with `command_rules.own_text`, **Then** it is at most 50% of the baseline count or unit 01's merge names it as an open floor that T02 settles (spec § Target)
- **Given** every baseline unit of the shared files `no-workflow-hub.md`, `run-record.md`, `orient.md`, `close-chain.md`, `close-feedback.md`, `review-probe-catalogue.md`, `fabrik-reviewer.md`, `fabrik-researcher.md`, `fabrik-gui.md` with no surviving match, **When** the ledger is loaded, **Then** each has a `vanished:` label adjudicated from a Sonnet and a Haiku seat's union (spec § The rule test)
- **Given** a NEVER or refusal clause, or a phrase a kept behavioural test pins, in the baseline of the shared files `no-workflow-hub.md`, `run-record.md`, `orient.md`, `close-chain.md`, `close-feedback.md`, `review-probe-catalogue.md`, `fabrik-reviewer.md`, `fabrik-researcher.md`, `fabrik-gui.md`, **When** it is rewritten, **Then** the phrase survives verbatim as a `text` carrier (spec § How a command is cut)
- **Given** the corpus after the shared files `no-workflow-hub.md`, `run-record.md`, `orient.md`, `close-chain.md`, `close-feedback.md`, `review-probe-catalogue.md`, `fabrik-reviewer.md`, `fabrik-researcher.md`, `fabrik-gui.md` rewrite, **When** `assemble_commands.py --check` runs, **Then** it exits 0 or 1 and never 4 or 5 (spec § The rule test)
- **Given** the `review-probe-catalogue.md` seat-isolation recipe, **When** the code under test imports a gitignored generated file or runs from a git archive, **Then** the recipe says to copy that file into the archive tree and to run Python with `-P` and `env -C` (W-6effedda, W-9ad5860f)
- **Given** `commands/_agents/fabrik-reviewer.md` rewritten, **When** a seat reads its house rules, **Then** they forbid executing the surface under review, and the T4 panel verdict on brief contents is a D-row (W-f723cb66, spec § Time budget)
- **Given** the ledger for `/fabrik-review-scoped` written from its baseline own text at the unit's start commit, **When** `tests/test_command_rules.py` renders the corpus, **Then** it prints a LEDGER line for it with zero LOSS lines (spec § The rule test)
- **Given** `/fabrik-review-scoped` rewritten, **When** its own text is counted with `command_rules.own_text`, **Then** it is at most 50% of the baseline count or a floor D-row names the shortfall (spec § Target)
- **Given** every baseline unit of `/fabrik-review-scoped` with no surviving match, **When** the ledger is loaded, **Then** each has a `vanished:` label adjudicated from a Sonnet and a Haiku seat's union (spec § The rule test)
- **Given** a NEVER or refusal clause, or a phrase a kept behavioural test pins, in the baseline of `/fabrik-review-scoped`, **When** it is rewritten, **Then** the phrase survives verbatim as a `text` carrier (spec § How a command is cut)
- **Given** a presence pin in a corpus-text test on `/fabrik-review-scoped`, **When** this ticket commits, **Then** the pin is deleted and its phrase is a ledger carrier, and an absence pin is a `forbidden:` carrier or stays (spec § The rule test)
- **Given** the corpus after the `/fabrik-review-scoped` rewrite, **When** `assemble_commands.py --check` runs, **Then** it exits 0 or 1 and never 4 or 5 (spec § The rule test)
- **Given** the pilot's whole own text (`/fabrik-review-scoped`'s source plus the pilot shared files), **When** it is measured against its baseline with a green rule test, **Then** it is at or under 60%, or the orchestrator stops the program by the KILL clause; and words per rule (live words ÷ live entries) goes to the U1 D-row (spec § Binding)
- **Given** the shared file `term-coverage.md` at the unit's start commit, **When** its baseline and ledger are written before any cut, **Then** `tests/test_command_rules.py` prints its LEDGER line with zero LOSS lines and the files are byte-identical to the start commit (spec § The rule test)
- **Given** the presence pins on the shared file `term-coverage.md` in the tests of migration part a, **When** this ticket commits, **Then** each is deleted and its phrase is a carrier in the ledger, and an absence pin is a `forbidden:` carrier or stays (spec § The rule test)
- **Given** the presence pins on the shared file `term-coverage.md` in the tests of migration part b, **When** this ticket commits, **Then** each is deleted and its phrase is a carrier in the ledger, and an absence pin is a `forbidden:` carrier or stays (spec § The rule test)
- **Given** the ledger for the shared file `term-coverage.md` written from its baseline own text at the unit's start commit, **When** `tests/test_command_rules.py` renders the corpus, **Then** it prints a LEDGER line for it with zero LOSS lines (spec § The rule test)
- **Given** the shared file `term-coverage.md` rewritten, **When** its own text is counted with `command_rules.own_text`, **Then** it is at most 50% of the baseline count or a floor D-row names the shortfall (spec § Target)
- **Given** every baseline unit of the shared file `term-coverage.md` with no surviving match, **When** the ledger is loaded, **Then** each has a `vanished:` label adjudicated from a Sonnet and a Haiku seat's union (spec § The rule test)
- **Given** a NEVER or refusal clause, or a phrase a kept behavioural test pins, in the baseline of the shared file `term-coverage.md`, **When** it is rewritten, **Then** the phrase survives verbatim as a `text` carrier (spec § How a command is cut)
- **Given** the corpus after the shared file `term-coverage.md` rewrite, **When** `assemble_commands.py --check` runs, **Then** it exits 0 or 1 and never 4 or 5 (spec § The rule test)
- **Given** the shared file `term-edit.md` at the unit's start commit, **When** its baseline and ledger are written before any cut, **Then** `tests/test_command_rules.py` prints its LEDGER line with zero LOSS lines and the files are byte-identical to the start commit (spec § The rule test)
- **Given** the presence pins on the shared file `term-edit.md` in the tests of migration part a, **When** this ticket commits, **Then** each is deleted and its phrase is a carrier in the ledger, and an absence pin is a `forbidden:` carrier or stays (spec § The rule test)
- **Given** the presence pins on the shared file `term-edit.md` in the tests of migration part b, **When** this ticket commits, **Then** each is deleted and its phrase is a carrier in the ledger, and an absence pin is a `forbidden:` carrier or stays (spec § The rule test)
- **Given** the ledger for the shared file `term-edit.md` written from its baseline own text at the unit's start commit, **When** `tests/test_command_rules.py` renders the corpus, **Then** it prints a LEDGER line for it with zero LOSS lines (spec § The rule test)
- **Given** the shared file `term-edit.md` rewritten, **When** its own text is counted with `command_rules.own_text`, **Then** it is at most 50% of the baseline count or a floor D-row names the shortfall (spec § Target)
- **Given** every baseline unit of the shared file `term-edit.md` with no surviving match, **When** the ledger is loaded, **Then** each has a `vanished:` label adjudicated from a Sonnet and a Haiku seat's union (spec § The rule test)
- **Given** a NEVER or refusal clause, or a phrase a kept behavioural test pins, in the baseline of the shared file `term-edit.md`, **When** it is rewritten, **Then** the phrase survives verbatim as a `text` carrier (spec § How a command is cut)
- **Given** the corpus after the shared file `term-edit.md` rewrite, **When** `assemble_commands.py --check` runs, **Then** it exits 0 or 1 and never 4 or 5 (spec § The rule test)
- **Given** the shared files `subagents-core.md`, `delegated-reads.md`, `grounding-artifact.md`, `grounding-code.md`, `grounding-rules.md`, `questionbar.md`, `injection.md`, `test-generation-loop.md`, `chat-intake.md`, `repo-identity.md` at the unit's start commit, **When** its baseline and ledger are written before any cut, **Then** `tests/test_command_rules.py` prints its LEDGER line with zero LOSS lines and the files are byte-identical to the start commit (spec § The rule test)
- **Given** the presence pins on the shared files `subagents-core.md`, `delegated-reads.md`, `grounding-artifact.md`, `grounding-code.md`, `grounding-rules.md`, `questionbar.md`, `injection.md`, `test-generation-loop.md`, `chat-intake.md`, `repo-identity.md` in the tests of migration part a, **When** this ticket commits, **Then** each is deleted and its phrase is a carrier in the ledger, and an absence pin is a `forbidden:` carrier or stays (spec § The rule test)
- **Given** the presence pins on the shared files `subagents-core.md`, `delegated-reads.md`, `grounding-artifact.md`, `grounding-code.md`, `grounding-rules.md`, `questionbar.md`, `injection.md`, `test-generation-loop.md`, `chat-intake.md`, `repo-identity.md` in the tests of migration part b, **When** this ticket commits, **Then** each is deleted and its phrase is a carrier in the ledger, and an absence pin is a `forbidden:` carrier or stays (spec § The rule test)
- **Given** the ledger for the shared files `subagents-core.md`, `delegated-reads.md`, `grounding-artifact.md`, `grounding-code.md`, `grounding-rules.md`, `questionbar.md`, `injection.md`, `test-generation-loop.md`, `chat-intake.md`, `repo-identity.md` written from its baseline own text at the unit's start commit, **When** `tests/test_command_rules.py` renders the corpus, **Then** it prints a LEDGER line for it with zero LOSS lines (spec § The rule test)
- **Given** the shared files `subagents-core.md`, `delegated-reads.md`, `grounding-artifact.md`, `grounding-code.md`, `grounding-rules.md`, `questionbar.md`, `injection.md`, `test-generation-loop.md`, `chat-intake.md`, `repo-identity.md` rewritten, **When** its own text is counted with `command_rules.own_text`, **Then** it is at most 50% of the baseline count or a floor D-row names the shortfall (spec § Target)
- **Given** every baseline unit of the shared files `subagents-core.md`, `delegated-reads.md`, `grounding-artifact.md`, `grounding-code.md`, `grounding-rules.md`, `questionbar.md`, `injection.md`, `test-generation-loop.md`, `chat-intake.md`, `repo-identity.md` with no surviving match, **When** the ledger is loaded, **Then** each has a `vanished:` label adjudicated from a Sonnet and a Haiku seat's union (spec § The rule test)
- **Given** a NEVER or refusal clause, or a phrase a kept behavioural test pins, in the baseline of the shared files `subagents-core.md`, `delegated-reads.md`, `grounding-artifact.md`, `grounding-code.md`, `grounding-rules.md`, `questionbar.md`, `injection.md`, `test-generation-loop.md`, `chat-intake.md`, `repo-identity.md`, **When** it is rewritten, **Then** the phrase survives verbatim as a `text` carrier (spec § How a command is cut)
- **Given** the corpus after the shared files `subagents-core.md`, `delegated-reads.md`, `grounding-artifact.md`, `grounding-code.md`, `grounding-rules.md`, `questionbar.md`, `injection.md`, `test-generation-loop.md`, `chat-intake.md`, `repo-identity.md` rewrite, **When** `assemble_commands.py --check` runs, **Then** it exits 0 or 1 and never 4 or 5 (spec § The rule test)
- **Given** the ledger for the shared files `design-critique.md`, `design-gate-panel.md`, `deploy-chain.md`, `cert-board-contract.md`, `cert-execution.md`, `cert-handoff-grammar.md`, `cert-visual-deliverable.md`, `autonomy-run.md`, `design-review.md` written from its baseline own text at the unit's start commit, **When** `tests/test_command_rules.py` renders the corpus, **Then** it prints a LEDGER line for it with zero LOSS lines (spec § The rule test)
- **Given** the shared files `design-critique.md`, `design-gate-panel.md`, `deploy-chain.md`, `cert-board-contract.md`, `cert-execution.md`, `cert-handoff-grammar.md`, `cert-visual-deliverable.md`, `autonomy-run.md`, `design-review.md` rewritten, **When** its own text is counted with `command_rules.own_text`, **Then** it is at most 50% of the baseline count or a floor D-row names the shortfall (spec § Target)
- **Given** every baseline unit of the shared files `design-critique.md`, `design-gate-panel.md`, `deploy-chain.md`, `cert-board-contract.md`, `cert-execution.md`, `cert-handoff-grammar.md`, `cert-visual-deliverable.md`, `autonomy-run.md`, `design-review.md` with no surviving match, **When** the ledger is loaded, **Then** each has a `vanished:` label adjudicated from a Sonnet and a Haiku seat's union (spec § The rule test)
- **Given** a NEVER or refusal clause, or a phrase a kept behavioural test pins, in the baseline of the shared files `design-critique.md`, `design-gate-panel.md`, `deploy-chain.md`, `cert-board-contract.md`, `cert-execution.md`, `cert-handoff-grammar.md`, `cert-visual-deliverable.md`, `autonomy-run.md`, `design-review.md`, **When** it is rewritten, **Then** the phrase survives verbatim as a `text` carrier (spec § How a command is cut)
- **Given** a presence pin in a corpus-text test on the shared files `design-critique.md`, `design-gate-panel.md`, `deploy-chain.md`, `cert-board-contract.md`, `cert-execution.md`, `cert-handoff-grammar.md`, `cert-visual-deliverable.md`, `autonomy-run.md`, `design-review.md`, **When** this ticket commits, **Then** the pin is deleted and its phrase is a ledger carrier, and an absence pin is a `forbidden:` carrier or stays (spec § The rule test)
- **Given** the corpus after the shared files `design-critique.md`, `design-gate-panel.md`, `deploy-chain.md`, `cert-board-contract.md`, `cert-execution.md`, `cert-handoff-grammar.md`, `cert-visual-deliverable.md`, `autonomy-run.md`, `design-review.md` rewrite, **When** `assemble_commands.py --check` runs, **Then** it exits 0 or 1 and never 4 or 5 (spec § The rule test)
- **Given** `/fabrik-review` at the unit's start commit, **When** its baseline and ledger are written before any cut, **Then** `tests/test_command_rules.py` prints its LEDGER line with zero LOSS lines and the files are byte-identical to the start commit (spec § The rule test)
- **Given** the presence pins on `/fabrik-review` in the tests of migration part a, **When** this ticket commits, **Then** each is deleted and its phrase is a carrier in the ledger, and an absence pin is a `forbidden:` carrier or stays (spec § The rule test)
- **Given** the presence pins on `/fabrik-review` in the tests of migration part b, **When** this ticket commits, **Then** each is deleted and its phrase is a carrier in the ledger, and an absence pin is a `forbidden:` carrier or stays (spec § The rule test)
- **Given** the ledger for `/fabrik-review` written from its baseline own text at the unit's start commit, **When** `tests/test_command_rules.py` renders the corpus, **Then** it prints a LEDGER line for it with zero LOSS lines (spec § The rule test)
- **Given** `/fabrik-review` rewritten, **When** its own text is counted with `command_rules.own_text`, **Then** it is at most 50% of the baseline count or a floor D-row names the shortfall (spec § Target)
- **Given** every baseline unit of `/fabrik-review` with no surviving match, **When** the ledger is loaded, **Then** each has a `vanished:` label adjudicated from a Sonnet and a Haiku seat's union (spec § The rule test)
- **Given** a NEVER or refusal clause, or a phrase a kept behavioural test pins, in the baseline of `/fabrik-review`, **When** it is rewritten, **Then** the phrase survives verbatim as a `text` carrier (spec § How a command is cut)
- **Given** the corpus after the `/fabrik-review` rewrite, **When** `assemble_commands.py --check` runs, **Then** it exits 0 or 1 and never 4 or 5 (spec § The rule test)
- **Given** intel's D-344 measure exists at this unit's start, **When** the panel rules on T1, **Then** each `/fabrik-review` ledger entry the ruling rewrites lists that D-row under `changed-by:`, and with no measure T1 is recorded as not proposed (spec § Time budget)
- **Given** the ledger for `/fabrik-task` written from its baseline own text at the unit's start commit, **When** `tests/test_command_rules.py` renders the corpus, **Then** it prints a LEDGER line for it with zero LOSS lines (spec § The rule test)
- **Given** `/fabrik-task` rewritten, **When** its own text is counted with `command_rules.own_text`, **Then** it is at most 50% of the baseline count or a floor D-row names the shortfall (spec § Target)
- **Given** every baseline unit of `/fabrik-task` with no surviving match, **When** the ledger is loaded, **Then** each has a `vanished:` label adjudicated from a Sonnet and a Haiku seat's union (spec § The rule test)
- **Given** a NEVER or refusal clause, or a phrase a kept behavioural test pins, in the baseline of `/fabrik-task`, **When** it is rewritten, **Then** the phrase survives verbatim as a `text` carrier (spec § How a command is cut)
- **Given** a presence pin in a corpus-text test on `/fabrik-task`, **When** this ticket commits, **Then** the pin is deleted and its phrase is a ledger carrier, and an absence pin is a `forbidden:` carrier or stays (spec § The rule test)
- **Given** the corpus after the `/fabrik-task` rewrite, **When** `assemble_commands.py --check` runs, **Then** it exits 0 or 1 and never 4 or 5 (spec § The rule test)
- **Given** `/fabrik-task`'s rewrite, **When** its ledger is read, **Then** the full `/fabrik-review` after phase 5 step 5 and the v2 nested-review routing are live entries, not retired ones (spec § Time budget)
- **Given** the ledger for `/fabrik-execute-plan` written from its baseline own text at the unit's start commit, **When** `tests/test_command_rules.py` renders the corpus, **Then** it prints a LEDGER line for it with zero LOSS lines (spec § The rule test)
- **Given** `/fabrik-execute-plan` rewritten, **When** its own text is counted with `command_rules.own_text`, **Then** it is at most 50% of the baseline count or a floor D-row names the shortfall (spec § Target)
- **Given** every baseline unit of `/fabrik-execute-plan` with no surviving match, **When** the ledger is loaded, **Then** each has a `vanished:` label adjudicated from a Sonnet and a Haiku seat's union (spec § The rule test)
- **Given** a NEVER or refusal clause, or a phrase a kept behavioural test pins, in the baseline of `/fabrik-execute-plan`, **When** it is rewritten, **Then** the phrase survives verbatim as a `text` carrier (spec § How a command is cut)
- **Given** a presence pin in a corpus-text test on `/fabrik-execute-plan`, **When** this ticket commits, **Then** the pin is deleted and its phrase is a ledger carrier, and an absence pin is a `forbidden:` carrier or stays (spec § The rule test)
- **Given** the corpus after the `/fabrik-execute-plan` rewrite, **When** `assemble_commands.py --check` runs, **Then** it exits 0 or 1 and never 4 or 5 (spec § The rule test)
- **Given** the ledger for `/fabrik-command-improve` written from its baseline own text at the unit's start commit, **When** `tests/test_command_rules.py` renders the corpus, **Then** it prints a LEDGER line for it with zero LOSS lines (spec § The rule test)
- **Given** `/fabrik-command-improve` rewritten, **When** its own text is counted with `command_rules.own_text`, **Then** it is at most 50% of the baseline count or a floor D-row names the shortfall (spec § Target)
- **Given** every baseline unit of `/fabrik-command-improve` with no surviving match, **When** the ledger is loaded, **Then** each has a `vanished:` label adjudicated from a Sonnet and a Haiku seat's union (spec § The rule test)
- **Given** a NEVER or refusal clause, or a phrase a kept behavioural test pins, in the baseline of `/fabrik-command-improve`, **When** it is rewritten, **Then** the phrase survives verbatim as a `text` carrier (spec § How a command is cut)
- **Given** a presence pin in a corpus-text test on `/fabrik-command-improve`, **When** this ticket commits, **Then** the pin is deleted and its phrase is a ledger carrier, and an absence pin is a `forbidden:` carrier or stays (spec § The rule test)
- **Given** the corpus after the `/fabrik-command-improve` rewrite, **When** `assemble_commands.py --check` runs, **Then** it exits 0 or 1 and never 4 or 5 (spec § The rule test)
- **Given** `/fabrik-command-improve`'s rewritten source, **When** an agent reads its edit contract, **Then** it states that an edit must fit its ceiling and pass the ledger, and that a `remove:` candidate is a ledger check, never permission to delete (spec § Loop changes)
- **Given** the ledger for `/fabrik-spec` written from its baseline own text at the unit's start commit, **When** `tests/test_command_rules.py` renders the corpus, **Then** it prints a LEDGER line for it with zero LOSS lines (spec § The rule test)
- **Given** `/fabrik-spec` rewritten, **When** its own text is counted with `command_rules.own_text`, **Then** it is at most 50% of the baseline count or a floor D-row names the shortfall (spec § Target)
- **Given** every baseline unit of `/fabrik-spec` with no surviving match, **When** the ledger is loaded, **Then** each has a `vanished:` label adjudicated from a Sonnet and a Haiku seat's union (spec § The rule test)
- **Given** a NEVER or refusal clause, or a phrase a kept behavioural test pins, in the baseline of `/fabrik-spec`, **When** it is rewritten, **Then** the phrase survives verbatim as a `text` carrier (spec § How a command is cut)
- **Given** a presence pin in a corpus-text test on `/fabrik-spec`, **When** this ticket commits, **Then** the pin is deleted and its phrase is a ledger carrier, and an absence pin is a `forbidden:` carrier or stays (spec § The rule test)
- **Given** the corpus after the `/fabrik-spec` rewrite, **When** `assemble_commands.py --check` runs, **Then** it exits 0 or 1 and never 4 or 5 (spec § The rule test)
- **Given** the ledger for `/fabrik-plan-review` written from its baseline own text at the unit's start commit, **When** `tests/test_command_rules.py` renders the corpus, **Then** it prints a LEDGER line for it with zero LOSS lines (spec § The rule test)
- **Given** `/fabrik-plan-review` rewritten, **When** its own text is counted with `command_rules.own_text`, **Then** it is at most 50% of the baseline count or a floor D-row names the shortfall (spec § Target)
- **Given** every baseline unit of `/fabrik-plan-review` with no surviving match, **When** the ledger is loaded, **Then** each has a `vanished:` label adjudicated from a Sonnet and a Haiku seat's union (spec § The rule test)
- **Given** a NEVER or refusal clause, or a phrase a kept behavioural test pins, in the baseline of `/fabrik-plan-review`, **When** it is rewritten, **Then** the phrase survives verbatim as a `text` carrier (spec § How a command is cut)
- **Given** a presence pin in a corpus-text test on `/fabrik-plan-review`, **When** this ticket commits, **Then** the pin is deleted and its phrase is a ledger carrier, and an absence pin is a `forbidden:` carrier or stays (spec § The rule test)
- **Given** the corpus after the `/fabrik-plan-review` rewrite, **When** `assemble_commands.py --check` runs, **Then** it exits 0 or 1 and never 4 or 5 (spec § The rule test)
- **Given** the ledger for `/fabrik-plan-after-chat` written from its baseline own text at the unit's start commit, **When** `tests/test_command_rules.py` renders the corpus, **Then** it prints a LEDGER line for it with zero LOSS lines (spec § The rule test)
- **Given** `/fabrik-plan-after-chat` rewritten, **When** its own text is counted with `command_rules.own_text`, **Then** it is at most 50% of the baseline count or a floor D-row names the shortfall (spec § Target)
- **Given** every baseline unit of `/fabrik-plan-after-chat` with no surviving match, **When** the ledger is loaded, **Then** each has a `vanished:` label adjudicated from a Sonnet and a Haiku seat's union (spec § The rule test)
- **Given** a NEVER or refusal clause, or a phrase a kept behavioural test pins, in the baseline of `/fabrik-plan-after-chat`, **When** it is rewritten, **Then** the phrase survives verbatim as a `text` carrier (spec § How a command is cut)
- **Given** a presence pin in a corpus-text test on `/fabrik-plan-after-chat`, **When** this ticket commits, **Then** the pin is deleted and its phrase is a ledger carrier, and an absence pin is a `forbidden:` carrier or stays (spec § The rule test)
- **Given** the corpus after the `/fabrik-plan-after-chat` rewrite, **When** `assemble_commands.py --check` runs, **Then** it exits 0 or 1 and never 4 or 5 (spec § The rule test)
- **Given** the ledger for `/fabrik-spec-review` written from its baseline own text at the unit's start commit, **When** `tests/test_command_rules.py` renders the corpus, **Then** it prints a LEDGER line for it with zero LOSS lines (spec § The rule test)
- **Given** `/fabrik-spec-review` rewritten, **When** its own text is counted with `command_rules.own_text`, **Then** it is at most 50% of the baseline count or a floor D-row names the shortfall (spec § Target)
- **Given** every baseline unit of `/fabrik-spec-review` with no surviving match, **When** the ledger is loaded, **Then** each has a `vanished:` label adjudicated from a Sonnet and a Haiku seat's union (spec § The rule test)
- **Given** a NEVER or refusal clause, or a phrase a kept behavioural test pins, in the baseline of `/fabrik-spec-review`, **When** it is rewritten, **Then** the phrase survives verbatim as a `text` carrier (spec § How a command is cut)
- **Given** a presence pin in a corpus-text test on `/fabrik-spec-review`, **When** this ticket commits, **Then** the pin is deleted and its phrase is a ledger carrier, and an absence pin is a `forbidden:` carrier or stays (spec § The rule test)
- **Given** the corpus after the `/fabrik-spec-review` rewrite, **When** `assemble_commands.py --check` runs, **Then** it exits 0 or 1 and never 4 or 5 (spec § The rule test)
- **Given** the ledger for `/fabrik-data-contract` written from its baseline own text at the unit's start commit, **When** `tests/test_command_rules.py` renders the corpus, **Then** it prints a LEDGER line for it with zero LOSS lines (spec § The rule test)
- **Given** `/fabrik-data-contract` rewritten, **When** its own text is counted with `command_rules.own_text`, **Then** it is at most 50% of the baseline count or a floor D-row names the shortfall (spec § Target)
- **Given** every baseline unit of `/fabrik-data-contract` with no surviving match, **When** the ledger is loaded, **Then** each has a `vanished:` label adjudicated from a Sonnet and a Haiku seat's union (spec § The rule test)
- **Given** a NEVER or refusal clause, or a phrase a kept behavioural test pins, in the baseline of `/fabrik-data-contract`, **When** it is rewritten, **Then** the phrase survives verbatim as a `text` carrier (spec § How a command is cut)
- **Given** a presence pin in a corpus-text test on `/fabrik-data-contract`, **When** this ticket commits, **Then** the pin is deleted and its phrase is a ledger carrier, and an absence pin is a `forbidden:` carrier or stays (spec § The rule test)
- **Given** the corpus after the `/fabrik-data-contract` rewrite, **When** `assemble_commands.py --check` runs, **Then** it exits 0 or 1 and never 4 or 5 (spec § The rule test)
- **Given** the ledger for `/fabrik-docs-review` written from its baseline own text at the unit's start commit, **When** `tests/test_command_rules.py` renders the corpus, **Then** it prints a LEDGER line for it with zero LOSS lines (spec § The rule test)
- **Given** `/fabrik-docs-review` rewritten, **When** its own text is counted with `command_rules.own_text`, **Then** it is at most 50% of the baseline count or a floor D-row names the shortfall (spec § Target)
- **Given** every baseline unit of `/fabrik-docs-review` with no surviving match, **When** the ledger is loaded, **Then** each has a `vanished:` label adjudicated from a Sonnet and a Haiku seat's union (spec § The rule test)
- **Given** a NEVER or refusal clause, or a phrase a kept behavioural test pins, in the baseline of `/fabrik-docs-review`, **When** it is rewritten, **Then** the phrase survives verbatim as a `text` carrier (spec § How a command is cut)
- **Given** a presence pin in a corpus-text test on `/fabrik-docs-review`, **When** this ticket commits, **Then** the pin is deleted and its phrase is a ledger carrier, and an absence pin is a `forbidden:` carrier or stays (spec § The rule test)
- **Given** the corpus after the `/fabrik-docs-review` rewrite, **When** `assemble_commands.py --check` runs, **Then** it exits 0 or 1 and never 4 or 5 (spec § The rule test)
- **Given** the ledger for `/fabrik-conformance-review` written from its baseline own text at the unit's start commit, **When** `tests/test_command_rules.py` renders the corpus, **Then** it prints a LEDGER line for it with zero LOSS lines (spec § The rule test)
- **Given** `/fabrik-conformance-review` rewritten, **When** its own text is counted with `command_rules.own_text`, **Then** it is at most 50% of the baseline count or a floor D-row names the shortfall (spec § Target)
- **Given** every baseline unit of `/fabrik-conformance-review` with no surviving match, **When** the ledger is loaded, **Then** each has a `vanished:` label adjudicated from a Sonnet and a Haiku seat's union (spec § The rule test)
- **Given** a NEVER or refusal clause, or a phrase a kept behavioural test pins, in the baseline of `/fabrik-conformance-review`, **When** it is rewritten, **Then** the phrase survives verbatim as a `text` carrier (spec § How a command is cut)
- **Given** a presence pin in a corpus-text test on `/fabrik-conformance-review`, **When** this ticket commits, **Then** the pin is deleted and its phrase is a ledger carrier, and an absence pin is a `forbidden:` carrier or stays (spec § The rule test)
- **Given** the corpus after the `/fabrik-conformance-review` rewrite, **When** `assemble_commands.py --check` runs, **Then** it exits 0 or 1 and never 4 or 5 (spec § The rule test)
- **Given** the ledger for `/fabrik-catchup` written from its baseline own text at the unit's start commit, **When** `tests/test_command_rules.py` renders the corpus, **Then** it prints a LEDGER line for it with zero LOSS lines (spec § The rule test)
- **Given** `/fabrik-catchup` rewritten, **When** its own text is counted with `command_rules.own_text`, **Then** it is at most 50% of the baseline count or a floor D-row names the shortfall (spec § Target)
- **Given** every baseline unit of `/fabrik-catchup` with no surviving match, **When** the ledger is loaded, **Then** each has a `vanished:` label adjudicated from a Sonnet and a Haiku seat's union (spec § The rule test)
- **Given** a NEVER or refusal clause, or a phrase a kept behavioural test pins, in the baseline of `/fabrik-catchup`, **When** it is rewritten, **Then** the phrase survives verbatim as a `text` carrier (spec § How a command is cut)
- **Given** a presence pin in a corpus-text test on `/fabrik-catchup`, **When** this ticket commits, **Then** the pin is deleted and its phrase is a ledger carrier, and an absence pin is a `forbidden:` carrier or stays (spec § The rule test)
- **Given** the corpus after the `/fabrik-catchup` rewrite, **When** `assemble_commands.py --check` runs, **Then** it exits 0 or 1 and never 4 or 5 (spec § The rule test)
- **Given** the ledger for `/fabrik-features` written from its baseline own text at the unit's start commit, **When** `tests/test_command_rules.py` renders the corpus, **Then** it prints a LEDGER line for it with zero LOSS lines (spec § The rule test)
- **Given** `/fabrik-features` rewritten, **When** its own text is counted with `command_rules.own_text`, **Then** it is at most 50% of the baseline count or a floor D-row names the shortfall (spec § Target)
- **Given** every baseline unit of `/fabrik-features` with no surviving match, **When** the ledger is loaded, **Then** each has a `vanished:` label adjudicated from a Sonnet and a Haiku seat's union (spec § The rule test)
- **Given** a NEVER or refusal clause, or a phrase a kept behavioural test pins, in the baseline of `/fabrik-features`, **When** it is rewritten, **Then** the phrase survives verbatim as a `text` carrier (spec § How a command is cut)
- **Given** a presence pin in a corpus-text test on `/fabrik-features`, **When** this ticket commits, **Then** the pin is deleted and its phrase is a ledger carrier, and an absence pin is a `forbidden:` carrier or stays (spec § The rule test)
- **Given** the corpus after the `/fabrik-features` rewrite, **When** `assemble_commands.py --check` runs, **Then** it exits 0 or 1 and never 4 or 5 (spec § The rule test)
- **Given** the ledger for `/fabrik-doc-converge` written from its baseline own text at the unit's start commit, **When** `tests/test_command_rules.py` renders the corpus, **Then** it prints a LEDGER line for it with zero LOSS lines (spec § The rule test)
- **Given** `/fabrik-doc-converge` rewritten, **When** its own text is counted with `command_rules.own_text`, **Then** it is at most 50% of the baseline count or a floor D-row names the shortfall (spec § Target)
- **Given** every baseline unit of `/fabrik-doc-converge` with no surviving match, **When** the ledger is loaded, **Then** each has a `vanished:` label adjudicated from a Sonnet and a Haiku seat's union (spec § The rule test)
- **Given** a NEVER or refusal clause, or a phrase a kept behavioural test pins, in the baseline of `/fabrik-doc-converge`, **When** it is rewritten, **Then** the phrase survives verbatim as a `text` carrier (spec § How a command is cut)
- **Given** a presence pin in a corpus-text test on `/fabrik-doc-converge`, **When** this ticket commits, **Then** the pin is deleted and its phrase is a ledger carrier, and an absence pin is a `forbidden:` carrier or stays (spec § The rule test)
- **Given** the corpus after the `/fabrik-doc-converge` rewrite, **When** `assemble_commands.py --check` runs, **Then** it exits 0 or 1 and never 4 or 5 (spec § The rule test)
- **Given** the ledger for `/fabrik-user-test` written from its baseline own text at the unit's start commit, **When** `tests/test_command_rules.py` renders the corpus, **Then** it prints a LEDGER line for it with zero LOSS lines (spec § The rule test)
- **Given** `/fabrik-user-test` rewritten, **When** its own text is counted with `command_rules.own_text`, **Then** it is at most 50% of the baseline count or a floor D-row names the shortfall (spec § Target)
- **Given** every baseline unit of `/fabrik-user-test` with no surviving match, **When** the ledger is loaded, **Then** each has a `vanished:` label adjudicated from a Sonnet and a Haiku seat's union (spec § The rule test)
- **Given** a NEVER or refusal clause, or a phrase a kept behavioural test pins, in the baseline of `/fabrik-user-test`, **When** it is rewritten, **Then** the phrase survives verbatim as a `text` carrier (spec § How a command is cut)
- **Given** the corpus after the `/fabrik-user-test` rewrite, **When** `assemble_commands.py --check` runs, **Then** it exits 0 or 1 and never 4 or 5 (spec § The rule test)
- **Given** the ledger for `/fabrik-deploy-checklist` written from its baseline own text at the unit's start commit, **When** `tests/test_command_rules.py` renders the corpus, **Then** it prints a LEDGER line for it with zero LOSS lines (spec § The rule test)
- **Given** `/fabrik-deploy-checklist` rewritten, **When** its own text is counted with `command_rules.own_text`, **Then** it is at most 50% of the baseline count or a floor D-row names the shortfall (spec § Target)
- **Given** every baseline unit of `/fabrik-deploy-checklist` with no surviving match, **When** the ledger is loaded, **Then** each has a `vanished:` label adjudicated from a Sonnet and a Haiku seat's union (spec § The rule test)
- **Given** a NEVER or refusal clause, or a phrase a kept behavioural test pins, in the baseline of `/fabrik-deploy-checklist`, **When** it is rewritten, **Then** the phrase survives verbatim as a `text` carrier (spec § How a command is cut)
- **Given** a presence pin in a corpus-text test on `/fabrik-deploy-checklist`, **When** this ticket commits, **Then** the pin is deleted and its phrase is a ledger carrier, and an absence pin is a `forbidden:` carrier or stays (spec § The rule test)
- **Given** the corpus after the `/fabrik-deploy-checklist` rewrite, **When** `assemble_commands.py --check` runs, **Then** it exits 0 or 1 and never 4 or 5 (spec § The rule test)
- **Given** the ledger for `/fabrik-ui-design-review` written from its baseline own text at the unit's start commit, **When** `tests/test_command_rules.py` renders the corpus, **Then** it prints a LEDGER line for it with zero LOSS lines (spec § The rule test)
- **Given** `/fabrik-ui-design-review` rewritten, **When** its own text is counted with `command_rules.own_text`, **Then** it is at most 50% of the baseline count or a floor D-row names the shortfall (spec § Target)
- **Given** every baseline unit of `/fabrik-ui-design-review` with no surviving match, **When** the ledger is loaded, **Then** each has a `vanished:` label adjudicated from a Sonnet and a Haiku seat's union (spec § The rule test)
- **Given** a NEVER or refusal clause, or a phrase a kept behavioural test pins, in the baseline of `/fabrik-ui-design-review`, **When** it is rewritten, **Then** the phrase survives verbatim as a `text` carrier (spec § How a command is cut)
- **Given** a presence pin in a corpus-text test on `/fabrik-ui-design-review`, **When** this ticket commits, **Then** the pin is deleted and its phrase is a ledger carrier, and an absence pin is a `forbidden:` carrier or stays (spec § The rule test)
- **Given** the corpus after the `/fabrik-ui-design-review` rewrite, **When** `assemble_commands.py --check` runs, **Then** it exits 0 or 1 and never 4 or 5 (spec § The rule test)
- **Given** the ledger for `/fabrik-ui-design` written from its baseline own text at the unit's start commit, **When** `tests/test_command_rules.py` renders the corpus, **Then** it prints a LEDGER line for it with zero LOSS lines (spec § The rule test)
- **Given** `/fabrik-ui-design` rewritten, **When** its own text is counted with `command_rules.own_text`, **Then** it is at most 50% of the baseline count or a floor D-row names the shortfall (spec § Target)
- **Given** every baseline unit of `/fabrik-ui-design` with no surviving match, **When** the ledger is loaded, **Then** each has a `vanished:` label adjudicated from a Sonnet and a Haiku seat's union (spec § The rule test)
- **Given** a NEVER or refusal clause, or a phrase a kept behavioural test pins, in the baseline of `/fabrik-ui-design`, **When** it is rewritten, **Then** the phrase survives verbatim as a `text` carrier (spec § How a command is cut)
- **Given** a presence pin in a corpus-text test on `/fabrik-ui-design`, **When** this ticket commits, **Then** the pin is deleted and its phrase is a ledger carrier, and an absence pin is a `forbidden:` carrier or stays (spec § The rule test)
- **Given** the corpus after the `/fabrik-ui-design` rewrite, **When** `assemble_commands.py --check` runs, **Then** it exits 0 or 1 and never 4 or 5 (spec § The rule test)
- **Given** the ledger for `/fabrik-flows` written from its baseline own text at the unit's start commit, **When** `tests/test_command_rules.py` renders the corpus, **Then** it prints a LEDGER line for it with zero LOSS lines (spec § The rule test)
- **Given** `/fabrik-flows` rewritten, **When** its own text is counted with `command_rules.own_text`, **Then** it is at most 50% of the baseline count or a floor D-row names the shortfall (spec § Target)
- **Given** every baseline unit of `/fabrik-flows` with no surviving match, **When** the ledger is loaded, **Then** each has a `vanished:` label adjudicated from a Sonnet and a Haiku seat's union (spec § The rule test)
- **Given** a NEVER or refusal clause, or a phrase a kept behavioural test pins, in the baseline of `/fabrik-flows`, **When** it is rewritten, **Then** the phrase survives verbatim as a `text` carrier (spec § How a command is cut)
- **Given** a presence pin in a corpus-text test on `/fabrik-flows`, **When** this ticket commits, **Then** the pin is deleted and its phrase is a ledger carrier, and an absence pin is a `forbidden:` carrier or stays (spec § The rule test)
- **Given** the corpus after the `/fabrik-flows` rewrite, **When** `assemble_commands.py --check` runs, **Then** it exits 0 or 1 and never 4 or 5 (spec § The rule test)
- **Given** the ledger for `/fabrik-service-test` written from its baseline own text at the unit's start commit, **When** `tests/test_command_rules.py` renders the corpus, **Then** it prints a LEDGER line for it with zero LOSS lines (spec § The rule test)
- **Given** `/fabrik-service-test` rewritten, **When** its own text is counted with `command_rules.own_text`, **Then** it is at most 50% of the baseline count or a floor D-row names the shortfall (spec § Target)
- **Given** every baseline unit of `/fabrik-service-test` with no surviving match, **When** the ledger is loaded, **Then** each has a `vanished:` label adjudicated from a Sonnet and a Haiku seat's union (spec § The rule test)
- **Given** a NEVER or refusal clause, or a phrase a kept behavioural test pins, in the baseline of `/fabrik-service-test`, **When** it is rewritten, **Then** the phrase survives verbatim as a `text` carrier (spec § How a command is cut)
- **Given** the corpus after the `/fabrik-service-test` rewrite, **When** `assemble_commands.py --check` runs, **Then** it exits 0 or 1 and never 4 or 5 (spec § The rule test)
- **Given** the ledger for `/hibernate` written from its baseline own text at the unit's start commit, **When** `tests/test_command_rules.py` renders the corpus, **Then** it prints a LEDGER line for it with zero LOSS lines (spec § The rule test)
- **Given** `/hibernate` rewritten, **When** its own text is counted with `command_rules.own_text`, **Then** it is at most 50% of the baseline count or a floor D-row names the shortfall (spec § Target)
- **Given** every baseline unit of `/hibernate` with no surviving match, **When** the ledger is loaded, **Then** each has a `vanished:` label adjudicated from a Sonnet and a Haiku seat's union (spec § The rule test)
- **Given** a NEVER or refusal clause, or a phrase a kept behavioural test pins, in the baseline of `/hibernate`, **When** it is rewritten, **Then** the phrase survives verbatim as a `text` carrier (spec § How a command is cut)
- **Given** the corpus after the `/hibernate` rewrite, **When** `assemble_commands.py --check` runs, **Then** it exits 0 or 1 and never 4 or 5 (spec § The rule test)
- **Given** the ledger for `/fabrik-flows-review` written from its baseline own text at the unit's start commit, **When** `tests/test_command_rules.py` renders the corpus, **Then** it prints a LEDGER line for it with zero LOSS lines (spec § The rule test)
- **Given** `/fabrik-flows-review` rewritten, **When** its own text is counted with `command_rules.own_text`, **Then** it is at most 50% of the baseline count or a floor D-row names the shortfall (spec § Target)
- **Given** every baseline unit of `/fabrik-flows-review` with no surviving match, **When** the ledger is loaded, **Then** each has a `vanished:` label adjudicated from a Sonnet and a Haiku seat's union (spec § The rule test)
- **Given** a NEVER or refusal clause, or a phrase a kept behavioural test pins, in the baseline of `/fabrik-flows-review`, **When** it is rewritten, **Then** the phrase survives verbatim as a `text` carrier (spec § How a command is cut)
- **Given** a presence pin in a corpus-text test on `/fabrik-flows-review`, **When** this ticket commits, **Then** the pin is deleted and its phrase is a ledger carrier, and an absence pin is a `forbidden:` carrier or stays (spec § The rule test)
- **Given** the corpus after the `/fabrik-flows-review` rewrite, **When** `assemble_commands.py --check` runs, **Then** it exits 0 or 1 and never 4 or 5 (spec § The rule test)
- **Given** the ledger for `/design-review` written from its baseline own text at the unit's start commit, **When** `tests/test_command_rules.py` renders the corpus, **Then** it prints a LEDGER line for it with zero LOSS lines (spec § The rule test)
- **Given** `/design-review` rewritten, **When** its own text is counted with `command_rules.own_text`, **Then** it is at most 50% of the baseline count or a floor D-row names the shortfall (spec § Target)
- **Given** every baseline unit of `/design-review` with no surviving match, **When** the ledger is loaded, **Then** each has a `vanished:` label adjudicated from a Sonnet and a Haiku seat's union (spec § The rule test)
- **Given** a NEVER or refusal clause, or a phrase a kept behavioural test pins, in the baseline of `/design-review`, **When** it is rewritten, **Then** the phrase survives verbatim as a `text` carrier (spec § How a command is cut)
- **Given** a presence pin in a corpus-text test on `/design-review`, **When** this ticket commits, **Then** the pin is deleted and its phrase is a ledger carrier, and an absence pin is a `forbidden:` carrier or stays (spec § The rule test)
- **Given** the corpus after the `/design-review` rewrite, **When** `assemble_commands.py --check` runs, **Then** it exits 0 or 1 and never 4 or 5 (spec § The rule test)
- **Given** the ledger for `/fabrik-upstream` written from its baseline own text at the unit's start commit, **When** `tests/test_command_rules.py` renders the corpus, **Then** it prints a LEDGER line for it with zero LOSS lines (spec § The rule test)
- **Given** `/fabrik-upstream` rewritten, **When** its own text is counted with `command_rules.own_text`, **Then** it is at most 50% of the baseline count or a floor D-row names the shortfall (spec § Target)
- **Given** every baseline unit of `/fabrik-upstream` with no surviving match, **When** the ledger is loaded, **Then** each has a `vanished:` label adjudicated from a Sonnet and a Haiku seat's union (spec § The rule test)
- **Given** a NEVER or refusal clause, or a phrase a kept behavioural test pins, in the baseline of `/fabrik-upstream`, **When** it is rewritten, **Then** the phrase survives verbatim as a `text` carrier (spec § How a command is cut)
- **Given** a presence pin in a corpus-text test on `/fabrik-upstream`, **When** this ticket commits, **Then** the pin is deleted and its phrase is a ledger carrier, and an absence pin is a `forbidden:` carrier or stays (spec § The rule test)
- **Given** the corpus after the `/fabrik-upstream` rewrite, **When** `assemble_commands.py --check` runs, **Then** it exits 0 or 1 and never 4 or 5 (spec § The rule test)
- **Given** the ledger for `/fabrik-release` written from its baseline own text at the unit's start commit, **When** `tests/test_command_rules.py` renders the corpus, **Then** it prints a LEDGER line for it with zero LOSS lines (spec § The rule test)
- **Given** `/fabrik-release` rewritten, **When** its own text is counted with `command_rules.own_text`, **Then** it is at most 50% of the baseline count or a floor D-row names the shortfall (spec § Target)
- **Given** every baseline unit of `/fabrik-release` with no surviving match, **When** the ledger is loaded, **Then** each has a `vanished:` label adjudicated from a Sonnet and a Haiku seat's union (spec § The rule test)
- **Given** a NEVER or refusal clause, or a phrase a kept behavioural test pins, in the baseline of `/fabrik-release`, **When** it is rewritten, **Then** the phrase survives verbatim as a `text` carrier (spec § How a command is cut)
- **Given** a presence pin in a corpus-text test on `/fabrik-release`, **When** this ticket commits, **Then** the pin is deleted and its phrase is a ledger carrier, and an absence pin is a `forbidden:` carrier or stays (spec § The rule test)
- **Given** the corpus after the `/fabrik-release` rewrite, **When** `assemble_commands.py --check` runs, **Then** it exits 0 or 1 and never 4 or 5 (spec § The rule test)
- **Given** the ledger for `/fabrik-vision` written from its baseline own text at the unit's start commit, **When** `tests/test_command_rules.py` renders the corpus, **Then** it prints a LEDGER line for it with zero LOSS lines (spec § The rule test)
- **Given** `/fabrik-vision` rewritten, **When** its own text is counted with `command_rules.own_text`, **Then** it is at most 50% of the baseline count or a floor D-row names the shortfall (spec § Target)
- **Given** every baseline unit of `/fabrik-vision` with no surviving match, **When** the ledger is loaded, **Then** each has a `vanished:` label adjudicated from a Sonnet and a Haiku seat's union (spec § The rule test)
- **Given** a NEVER or refusal clause, or a phrase a kept behavioural test pins, in the baseline of `/fabrik-vision`, **When** it is rewritten, **Then** the phrase survives verbatim as a `text` carrier (spec § How a command is cut)
- **Given** the corpus after the `/fabrik-vision` rewrite, **When** `assemble_commands.py --check` runs, **Then** it exits 0 or 1 and never 4 or 5 (spec § The rule test)
- **Given** the ledger for `/fabrik-epics` written from its baseline own text at the unit's start commit, **When** `tests/test_command_rules.py` renders the corpus, **Then** it prints a LEDGER line for it with zero LOSS lines (spec § The rule test)
- **Given** `/fabrik-epics` rewritten, **When** its own text is counted with `command_rules.own_text`, **Then** it is at most 50% of the baseline count or a floor D-row names the shortfall (spec § Target)
- **Given** every baseline unit of `/fabrik-epics` with no surviving match, **When** the ledger is loaded, **Then** each has a `vanished:` label adjudicated from a Sonnet and a Haiku seat's union (spec § The rule test)
- **Given** a NEVER or refusal clause, or a phrase a kept behavioural test pins, in the baseline of `/fabrik-epics`, **When** it is rewritten, **Then** the phrase survives verbatim as a `text` carrier (spec § How a command is cut)
- **Given** the corpus after the `/fabrik-epics` rewrite, **When** `assemble_commands.py --check` runs, **Then** it exits 0 or 1 and never 4 or 5 (spec § The rule test)
- **Given** the ledger for `/fabrik-epics-review` written from its baseline own text at the unit's start commit, **When** `tests/test_command_rules.py` renders the corpus, **Then** it prints a LEDGER line for it with zero LOSS lines (spec § The rule test)
- **Given** `/fabrik-epics-review` rewritten, **When** its own text is counted with `command_rules.own_text`, **Then** it is at most 50% of the baseline count or a floor D-row names the shortfall (spec § Target)
- **Given** every baseline unit of `/fabrik-epics-review` with no surviving match, **When** the ledger is loaded, **Then** each has a `vanished:` label adjudicated from a Sonnet and a Haiku seat's union (spec § The rule test)
- **Given** a NEVER or refusal clause, or a phrase a kept behavioural test pins, in the baseline of `/fabrik-epics-review`, **When** it is rewritten, **Then** the phrase survives verbatim as a `text` carrier (spec § How a command is cut)
- **Given** the corpus after the `/fabrik-epics-review` rewrite, **When** `assemble_commands.py --check` runs, **Then** it exits 0 or 1 and never 4 or 5 (spec § The rule test)
- **Given** the ledger for `/fabrik-deploy` written from its baseline own text at the unit's start commit, **When** `tests/test_command_rules.py` renders the corpus, **Then** it prints a LEDGER line for it with zero LOSS lines (spec § The rule test)
- **Given** `/fabrik-deploy` rewritten, **When** its own text is counted with `command_rules.own_text`, **Then** it is at most 50% of the baseline count or a floor D-row names the shortfall (spec § Target)
- **Given** every baseline unit of `/fabrik-deploy` with no surviving match, **When** the ledger is loaded, **Then** each has a `vanished:` label adjudicated from a Sonnet and a Haiku seat's union (spec § The rule test)
- **Given** a NEVER or refusal clause, or a phrase a kept behavioural test pins, in the baseline of `/fabrik-deploy`, **When** it is rewritten, **Then** the phrase survives verbatim as a `text` carrier (spec § How a command is cut)
- **Given** the corpus after the `/fabrik-deploy` rewrite, **When** `assemble_commands.py --check` runs, **Then** it exits 0 or 1 and never 4 or 5 (spec § The rule test)
- **Given** the ledger for `/fabrik-deploy-plan` written from its baseline own text at the unit's start commit, **When** `tests/test_command_rules.py` renders the corpus, **Then** it prints a LEDGER line for it with zero LOSS lines (spec § The rule test)
- **Given** `/fabrik-deploy-plan` rewritten, **When** its own text is counted with `command_rules.own_text`, **Then** it is at most 50% of the baseline count or a floor D-row names the shortfall (spec § Target)
- **Given** every baseline unit of `/fabrik-deploy-plan` with no surviving match, **When** the ledger is loaded, **Then** each has a `vanished:` label adjudicated from a Sonnet and a Haiku seat's union (spec § The rule test)
- **Given** a NEVER or refusal clause, or a phrase a kept behavioural test pins, in the baseline of `/fabrik-deploy-plan`, **When** it is rewritten, **Then** the phrase survives verbatim as a `text` carrier (spec § How a command is cut)
- **Given** the corpus after the `/fabrik-deploy-plan` rewrite, **When** `assemble_commands.py --check` runs, **Then** it exits 0 or 1 and never 4 or 5 (spec § The rule test)
- **Given** the ledger for `/fabrik-deploy-verify` written from its baseline own text at the unit's start commit, **When** `tests/test_command_rules.py` renders the corpus, **Then** it prints a LEDGER line for it with zero LOSS lines (spec § The rule test)
- **Given** `/fabrik-deploy-verify` rewritten, **When** its own text is counted with `command_rules.own_text`, **Then** it is at most 50% of the baseline count or a floor D-row names the shortfall (spec § Target)
- **Given** every baseline unit of `/fabrik-deploy-verify` with no surviving match, **When** the ledger is loaded, **Then** each has a `vanished:` label adjudicated from a Sonnet and a Haiku seat's union (spec § The rule test)
- **Given** a NEVER or refusal clause, or a phrase a kept behavioural test pins, in the baseline of `/fabrik-deploy-verify`, **When** it is rewritten, **Then** the phrase survives verbatim as a `text` carrier (spec § How a command is cut)
- **Given** a presence pin in a corpus-text test on `/fabrik-deploy-verify`, **When** this ticket commits, **Then** the pin is deleted and its phrase is a ledger carrier, and an absence pin is a `forbidden:` carrier or stays (spec § The rule test)
- **Given** the corpus after the `/fabrik-deploy-verify` rewrite, **When** `assemble_commands.py --check` runs, **Then** it exits 0 or 1 and never 4 or 5 (spec § The rule test)
- **Given** the ledger for `/fabrik-deploy-plan-review` written from its baseline own text at the unit's start commit, **When** `tests/test_command_rules.py` renders the corpus, **Then** it prints a LEDGER line for it with zero LOSS lines (spec § The rule test)
- **Given** `/fabrik-deploy-plan-review` rewritten, **When** its own text is counted with `command_rules.own_text`, **Then** it is at most 50% of the baseline count or a floor D-row names the shortfall (spec § Target)
- **Given** every baseline unit of `/fabrik-deploy-plan-review` with no surviving match, **When** the ledger is loaded, **Then** each has a `vanished:` label adjudicated from a Sonnet and a Haiku seat's union (spec § The rule test)
- **Given** a NEVER or refusal clause, or a phrase a kept behavioural test pins, in the baseline of `/fabrik-deploy-plan-review`, **When** it is rewritten, **Then** the phrase survives verbatim as a `text` carrier (spec § How a command is cut)
- **Given** a presence pin in a corpus-text test on `/fabrik-deploy-plan-review`, **When** this ticket commits, **Then** the pin is deleted and its phrase is a ledger carrier, and an absence pin is a `forbidden:` carrier or stays (spec § The rule test)
- **Given** the corpus after the `/fabrik-deploy-plan-review` rewrite, **When** `assemble_commands.py --check` runs, **Then** it exits 0 or 1 and never 4 or 5 (spec § The rule test)
- **Given** the ledger for `/fabrik-repo-review` written from its baseline own text at the unit's start commit, **When** `tests/test_command_rules.py` renders the corpus, **Then** it prints a LEDGER line for it with zero LOSS lines (spec § The rule test)
- **Given** `/fabrik-repo-review` rewritten, **When** its own text is counted with `command_rules.own_text`, **Then** it is at most 50% of the baseline count or a floor D-row names the shortfall (spec § Target)
- **Given** every baseline unit of `/fabrik-repo-review` with no surviving match, **When** the ledger is loaded, **Then** each has a `vanished:` label adjudicated from a Sonnet and a Haiku seat's union (spec § The rule test)
- **Given** a NEVER or refusal clause, or a phrase a kept behavioural test pins, in the baseline of `/fabrik-repo-review`, **When** it is rewritten, **Then** the phrase survives verbatim as a `text` carrier (spec § How a command is cut)
- **Given** a presence pin in a corpus-text test on `/fabrik-repo-review`, **When** this ticket commits, **Then** the pin is deleted and its phrase is a ledger carrier, and an absence pin is a `forbidden:` carrier or stays (spec § The rule test)
- **Given** the corpus after the `/fabrik-repo-review` rewrite, **When** `assemble_commands.py --check` runs, **Then** it exits 0 or 1 and never 4 or 5 (spec § The rule test)
- **Given** the ledger for `/fabrik-rivals` written from its baseline own text at the unit's start commit, **When** `tests/test_command_rules.py` renders the corpus, **Then** it prints a LEDGER line for it with zero LOSS lines (spec § The rule test)
- **Given** `/fabrik-rivals` rewritten, **When** its own text is counted with `command_rules.own_text`, **Then** it is at most 50% of the baseline count or a floor D-row names the shortfall (spec § Target)
- **Given** every baseline unit of `/fabrik-rivals` with no surviving match, **When** the ledger is loaded, **Then** each has a `vanished:` label adjudicated from a Sonnet and a Haiku seat's union (spec § The rule test)
- **Given** a NEVER or refusal clause, or a phrase a kept behavioural test pins, in the baseline of `/fabrik-rivals`, **When** it is rewritten, **Then** the phrase survives verbatim as a `text` carrier (spec § How a command is cut)
- **Given** the corpus after the `/fabrik-rivals` rewrite, **When** `assemble_commands.py --check` runs, **Then** it exits 0 or 1 and never 4 or 5 (spec § The rule test)
- **Given** the ledger for `/fabrik-decommission` written from its baseline own text at the unit's start commit, **When** `tests/test_command_rules.py` renders the corpus, **Then** it prints a LEDGER line for it with zero LOSS lines (spec § The rule test)
- **Given** `/fabrik-decommission` rewritten, **When** its own text is counted with `command_rules.own_text`, **Then** it is at most 50% of the baseline count or a floor D-row names the shortfall (spec § Target)
- **Given** every baseline unit of `/fabrik-decommission` with no surviving match, **When** the ledger is loaded, **Then** each has a `vanished:` label adjudicated from a Sonnet and a Haiku seat's union (spec § The rule test)
- **Given** a NEVER or refusal clause, or a phrase a kept behavioural test pins, in the baseline of `/fabrik-decommission`, **When** it is rewritten, **Then** the phrase survives verbatim as a `text` carrier (spec § How a command is cut)
- **Given** the corpus after the `/fabrik-decommission` rewrite, **When** `assemble_commands.py --check` runs, **Then** it exits 0 or 1 and never 4 or 5 (spec § The rule test)
- **Given** the ledger for `/fabrik-generate-tests` written from its baseline own text at the unit's start commit, **When** `tests/test_command_rules.py` renders the corpus, **Then** it prints a LEDGER line for it with zero LOSS lines (spec § The rule test)
- **Given** `/fabrik-generate-tests` rewritten, **When** its own text is counted with `command_rules.own_text`, **Then** it is at most 50% of the baseline count or a floor D-row names the shortfall (spec § Target)
- **Given** every baseline unit of `/fabrik-generate-tests` with no surviving match, **When** the ledger is loaded, **Then** each has a `vanished:` label adjudicated from a Sonnet and a Haiku seat's union (spec § The rule test)
- **Given** a NEVER or refusal clause, or a phrase a kept behavioural test pins, in the baseline of `/fabrik-generate-tests`, **When** it is rewritten, **Then** the phrase survives verbatim as a `text` carrier (spec § How a command is cut)
- **Given** the corpus after the `/fabrik-generate-tests` rewrite, **When** `assemble_commands.py --check` runs, **Then** it exits 0 or 1 and never 4 or 5 (spec § The rule test)
- **Given** the ledger for `/fabrik-rules-review` written from its baseline own text at the unit's start commit, **When** `tests/test_command_rules.py` renders the corpus, **Then** it prints a LEDGER line for it with zero LOSS lines (spec § The rule test)
- **Given** `/fabrik-rules-review` rewritten, **When** its own text is counted with `command_rules.own_text`, **Then** it is at most 50% of the baseline count or a floor D-row names the shortfall (spec § Target)
- **Given** every baseline unit of `/fabrik-rules-review` with no surviving match, **When** the ledger is loaded, **Then** each has a `vanished:` label adjudicated from a Sonnet and a Haiku seat's union (spec § The rule test)
- **Given** a NEVER or refusal clause, or a phrase a kept behavioural test pins, in the baseline of `/fabrik-rules-review`, **When** it is rewritten, **Then** the phrase survives verbatim as a `text` carrier (spec § How a command is cut)
- **Given** the corpus after the `/fabrik-rules-review` rewrite, **When** `assemble_commands.py --check` runs, **Then** it exits 0 or 1 and never 4 or 5 (spec § The rule test)
- **Given** the ledger for `/fabrik-reverse-engineer` written from its baseline own text at the unit's start commit, **When** `tests/test_command_rules.py` renders the corpus, **Then** it prints a LEDGER line for it with zero LOSS lines (spec § The rule test)
- **Given** `/fabrik-reverse-engineer` rewritten, **When** its own text is counted with `command_rules.own_text`, **Then** it is at most 50% of the baseline count or a floor D-row names the shortfall (spec § Target)
- **Given** every baseline unit of `/fabrik-reverse-engineer` with no surviving match, **When** the ledger is loaded, **Then** each has a `vanished:` label adjudicated from a Sonnet and a Haiku seat's union (spec § The rule test)
- **Given** a NEVER or refusal clause, or a phrase a kept behavioural test pins, in the baseline of `/fabrik-reverse-engineer`, **When** it is rewritten, **Then** the phrase survives verbatim as a `text` carrier (spec § How a command is cut)
- **Given** the corpus after the `/fabrik-reverse-engineer` rewrite, **When** `assemble_commands.py --check` runs, **Then** it exits 0 or 1 and never 4 or 5 (spec § The rule test)
- **Given** the ledger for `/fabrik-workflow-review` written from its baseline own text at the unit's start commit, **When** `tests/test_command_rules.py` renders the corpus, **Then** it prints a LEDGER line for it with zero LOSS lines (spec § The rule test)
- **Given** `/fabrik-workflow-review` rewritten, **When** its own text is counted with `command_rules.own_text`, **Then** it is at most 50% of the baseline count or a floor D-row names the shortfall (spec § Target)
- **Given** every baseline unit of `/fabrik-workflow-review` with no surviving match, **When** the ledger is loaded, **Then** each has a `vanished:` label adjudicated from a Sonnet and a Haiku seat's union (spec § The rule test)
- **Given** a NEVER or refusal clause, or a phrase a kept behavioural test pins, in the baseline of `/fabrik-workflow-review`, **When** it is rewritten, **Then** the phrase survives verbatim as a `text` carrier (spec § How a command is cut)
- **Given** the corpus after the `/fabrik-workflow-review` rewrite, **When** `assemble_commands.py --check` runs, **Then** it exits 0 or 1 and never 4 or 5 (spec § The rule test)
- **Given** every command and shared-file ledger merged, **When** the receipt tabulates baseline and final own-text words, **Then** each is at or under 50% or names its floor D-row (spec § Binding)
- **Given** the tooling phase's published full-measure baselines, **When** the full measure is re-run at the close, **Then** no command's full measure has grown (spec § Target)
- **Given** the merged plan, **When** `final_gate.py --check --json` and `check_convergence.py` run, **Then** both report success and the receipt embeds their output (spec § Review and landing)
- **Given** the feedback ledger after the L2 merge, **When** the receipt counts close rows, **Then** it reports the `remove:` rows flowing with their `none` share (spec § Lifecycle)

## File Scope (owned paths)

- commands/_rules/_shared/no-workflow-hub.yaml
- commands/_rules/_shared/no-workflow-hub.baseline.txt
- commands/_rules/_shared/run-record.yaml
- commands/_rules/_shared/run-record.baseline.txt
- commands/_rules/_shared/orient.yaml
- commands/_rules/_shared/orient.baseline.txt
- commands/_rules/_shared/close-chain.yaml
- commands/_rules/_shared/close-chain.baseline.txt
- commands/_rules/_shared/close-feedback.yaml
- commands/_rules/_shared/close-feedback.baseline.txt
- commands/_rules/_shared/review-probe-catalogue.yaml
- commands/_rules/_shared/review-probe-catalogue.baseline.txt
- commands/_rules/_shared/fabrik-reviewer.yaml
- commands/_rules/_shared/fabrik-reviewer.baseline.txt
- commands/_rules/_shared/fabrik-researcher.yaml
- commands/_rules/_shared/fabrik-researcher.baseline.txt
- commands/_rules/_shared/fabrik-gui.yaml
- commands/_rules/_shared/fabrik-gui.baseline.txt
- tests/test_review_queue_pass.py
- tests/test_review_scoped_queue_pass.py
- tests/test_command_improve_queue_pass.py
- tests/test_fabrik_task_queue_pass.py
- tests/test_plan_review_queue_pass.py
- tests/test_spec_plan_lane_text.py
- tests/test_agent_definitions.py
- tests/test_bounded_hop_new_output.py
- tests/test_close_feedback_autoappend.py
- tests/test_frontend_design_routing.py
- tests/test_orient_fragment.py
- tests/test_plan_after_chat_queue_pass.py
- tests/test_producing_command_fragments.py
- tests/test_run_scratch_brief_wording.py
- tests/test_seat_home_read_rule.py
- tests/test_seat_recipe_readable.py
- tests/test_spec_queue_pass.py
- commands/_fragments/no-workflow-hub.md
- commands/_fragments/run-record.md
- commands/_fragments/orient.md
- commands/_fragments/close-chain.md
- commands/_fragments/close-feedback.md
- commands/_fragments/review-probe-catalogue.md
- commands/_agents/fabrik-reviewer.md
- commands/_agents/fabrik-researcher.md
- commands/_agents/fabrik-gui.md
- commands/_size_ceiling.json
- commands/_sources/fabrik-review-scoped.md
- commands/_fragments/scope-growth-exit.md
- commands/_rules/fabrik-review-scoped.yaml
- commands/_rules/fabrik-review-scoped.baseline.txt
- commands/_rules/_shared/scope-growth-exit.yaml
- commands/_rules/_shared/scope-growth-exit.baseline.txt
- tests/test_review_command_text_defects.py
- tests/test_spec_review_queue_pass.py
- commands/_rules/_shared/term-coverage.yaml
- commands/_rules/_shared/term-coverage.baseline.txt
- tests/test_plan_review_recurring_rules.py
- tests/test_term_coverage_round_zero.py
- commands/_fragments/term-coverage.md
- commands/_rules/_shared/term-edit.yaml
- commands/_rules/_shared/term-edit.baseline.txt
- commands/_fragments/term-edit.md
- commands/_rules/_shared/subagents-core.yaml
- commands/_rules/_shared/subagents-core.baseline.txt
- commands/_rules/_shared/delegated-reads.yaml
- commands/_rules/_shared/delegated-reads.baseline.txt
- commands/_rules/_shared/grounding-artifact.yaml
- commands/_rules/_shared/grounding-artifact.baseline.txt
- commands/_rules/_shared/grounding-code.yaml
- commands/_rules/_shared/grounding-code.baseline.txt
- commands/_rules/_shared/grounding-rules.yaml
- commands/_rules/_shared/grounding-rules.baseline.txt
- commands/_rules/_shared/questionbar.yaml
- commands/_rules/_shared/questionbar.baseline.txt
- commands/_rules/_shared/injection.yaml
- commands/_rules/_shared/injection.baseline.txt
- commands/_rules/_shared/test-generation-loop.yaml
- commands/_rules/_shared/test-generation-loop.baseline.txt
- commands/_rules/_shared/chat-intake.yaml
- commands/_rules/_shared/chat-intake.baseline.txt
- commands/_rules/_shared/repo-identity.yaml
- commands/_rules/_shared/repo-identity.baseline.txt
- commands/_fragments/subagents-core.md
- commands/_fragments/delegated-reads.md
- commands/_fragments/grounding-artifact.md
- commands/_fragments/grounding-code.md
- commands/_fragments/grounding-rules.md
- commands/_fragments/questionbar.md
- commands/_fragments/injection.md
- commands/_fragments/test-generation-loop.md
- commands/_fragments/chat-intake.md
- commands/_fragments/repo-identity.md
- commands/_fragments/design-critique.md
- commands/_fragments/design-gate-panel.md
- commands/_fragments/deploy-chain.md
- commands/_fragments/cert-board-contract.md
- commands/_fragments/cert-execution.md
- commands/_fragments/cert-handoff-grammar.md
- commands/_fragments/cert-visual-deliverable.md
- commands/_fragments/autonomy-run.md
- commands/_agents/design-review.md
- commands/_rules/_shared/design-critique.yaml
- commands/_rules/_shared/design-critique.baseline.txt
- commands/_rules/_shared/design-gate-panel.yaml
- commands/_rules/_shared/design-gate-panel.baseline.txt
- commands/_rules/_shared/deploy-chain.yaml
- commands/_rules/_shared/deploy-chain.baseline.txt
- commands/_rules/_shared/cert-board-contract.yaml
- commands/_rules/_shared/cert-board-contract.baseline.txt
- commands/_rules/_shared/cert-execution.yaml
- commands/_rules/_shared/cert-execution.baseline.txt
- commands/_rules/_shared/cert-handoff-grammar.yaml
- commands/_rules/_shared/cert-handoff-grammar.baseline.txt
- commands/_rules/_shared/cert-visual-deliverable.yaml
- commands/_rules/_shared/cert-visual-deliverable.baseline.txt
- commands/_rules/_shared/autonomy-run.yaml
- commands/_rules/_shared/autonomy-run.baseline.txt
- commands/_rules/_shared/design-review.yaml
- commands/_rules/_shared/design-review.baseline.txt
- tests/test_design_critique_fragment.py
- commands/_rules/fabrik-review.yaml
- commands/_rules/fabrik-review.baseline.txt
- tests/test_execute_plan_d7.py
- commands/_sources/fabrik-review.md
- commands/_sources/fabrik-task.md
- commands/_rules/fabrik-task.yaml
- commands/_rules/fabrik-task.baseline.txt
- tests/test_fabrik_task_source.py
- commands/_sources/fabrik-execute-plan.md
- commands/_rules/fabrik-execute-plan.yaml
- commands/_rules/fabrik-execute-plan.baseline.txt
- tests/test_execute_plan_queue_pass.py
- tests/test_execute_plan_validation_first.py
- tests/test_features_queue_pass.py
- tests/test_plan_review_small_gate.py
- commands/_sources/fabrik-command-improve.md
- commands/_fragments/agent-feedback.md
- commands/_rules/fabrik-command-improve.yaml
- commands/_rules/fabrik-command-improve.baseline.txt
- commands/_rules/_shared/agent-feedback.yaml
- commands/_rules/_shared/agent-feedback.baseline.txt
- commands/_sources/fabrik-spec.md
- commands/_fragments/judge-panel.md
- commands/_rules/fabrik-spec.yaml
- commands/_rules/fabrik-spec.baseline.txt
- commands/_rules/_shared/judge-panel.yaml
- commands/_rules/_shared/judge-panel.baseline.txt
- commands/_sources/fabrik-plan-review.md
- commands/_rules/fabrik-plan-review.yaml
- commands/_rules/fabrik-plan-review.baseline.txt
- commands/_sources/fabrik-plan-after-chat.md
- commands/_rules/fabrik-plan-after-chat.yaml
- commands/_rules/fabrik-plan-after-chat.baseline.txt
- commands/_sources/fabrik-spec-review.md
- commands/_rules/fabrik-spec-review.yaml
- commands/_rules/fabrik-spec-review.baseline.txt
- commands/_sources/fabrik-data-contract.md
- commands/_rules/fabrik-data-contract.yaml
- commands/_rules/fabrik-data-contract.baseline.txt
- tests/test_data_contract_recurring_rules.py
- commands/_sources/fabrik-docs-review.md
- commands/_rules/fabrik-docs-review.yaml
- commands/_rules/fabrik-docs-review.baseline.txt
- tests/test_docs_review_queue_pass.py
- commands/_sources/fabrik-conformance-review.md
- commands/_rules/fabrik-conformance-review.yaml
- commands/_rules/fabrik-conformance-review.baseline.txt
- tests/test_conformance_review_queue_pass.py
- commands/_sources/fabrik-catchup.md
- commands/_rules/fabrik-catchup.yaml
- commands/_rules/fabrik-catchup.baseline.txt
- tests/test_catchup_queue_pass.py
- commands/_sources/fabrik-features.md
- commands/_rules/fabrik-features.yaml
- commands/_rules/fabrik-features.baseline.txt
- commands/_sources/fabrik-doc-converge.md
- commands/_rules/fabrik-doc-converge.yaml
- commands/_rules/fabrik-doc-converge.baseline.txt
- tests/test_doc_converge_queue_pass.py
- commands/_sources/fabrik-user-test.md
- commands/_rules/fabrik-user-test.yaml
- commands/_rules/fabrik-user-test.baseline.txt
- commands/_sources/fabrik-deploy-checklist.md
- commands/_rules/fabrik-deploy-checklist.yaml
- commands/_rules/fabrik-deploy-checklist.baseline.txt
- tests/test_deploy_checklist_queue_pass.py
- commands/_sources/fabrik-ui-design-review.md
- commands/_rules/fabrik-ui-design-review.yaml
- commands/_rules/fabrik-ui-design-review.baseline.txt
- tests/test_flows_review_queue_pass.py
- tests/test_ui_design_review_queue_pass.py
- commands/_sources/fabrik-ui-design.md
- commands/_rules/fabrik-ui-design.yaml
- commands/_rules/fabrik-ui-design.baseline.txt
- tests/test_ui_design_queue_pass.py
- commands/_sources/fabrik-flows.md
- commands/_rules/fabrik-flows.yaml
- commands/_rules/fabrik-flows.baseline.txt
- tests/test_flows_queue_pass.py
- commands/_sources/fabrik-service-test.md
- commands/_rules/fabrik-service-test.yaml
- commands/_rules/fabrik-service-test.baseline.txt
- commands/_sources/hibernate.md
- commands/_rules/hibernate.yaml
- commands/_rules/hibernate.baseline.txt
- commands/_sources/fabrik-flows-review.md
- commands/_rules/fabrik-flows-review.yaml
- commands/_rules/fabrik-flows-review.baseline.txt
- tests/enforcement/test_trigger_routing.py
- commands/_sources/design-review.md
- commands/_rules/design-review.yaml
- commands/_rules/design-review.baseline.txt
- tests/test_design_review_queue_pass.py
- commands/_sources/fabrik-upstream.md
- commands/_rules/fabrik-upstream.yaml
- commands/_rules/fabrik-upstream.baseline.txt
- tests/test_upstream_queue_pass.py
- commands/_sources/fabrik-release.md
- commands/_rules/fabrik-release.yaml
- commands/_rules/fabrik-release.baseline.txt
- tests/test_release_queue_pass.py
- commands/_sources/fabrik-vision.md
- commands/_rules/fabrik-vision.yaml
- commands/_rules/fabrik-vision.baseline.txt
- commands/_sources/fabrik-epics.md
- commands/_rules/fabrik-epics.yaml
- commands/_rules/fabrik-epics.baseline.txt
- commands/_sources/fabrik-epics-review.md
- commands/_rules/fabrik-epics-review.yaml
- commands/_rules/fabrik-epics-review.baseline.txt
- commands/_sources/fabrik-deploy.md
- commands/_rules/fabrik-deploy.yaml
- commands/_rules/fabrik-deploy.baseline.txt
- commands/_sources/fabrik-deploy-plan.md
- commands/_rules/fabrik-deploy-plan.yaml
- commands/_rules/fabrik-deploy-plan.baseline.txt
- commands/_sources/fabrik-deploy-verify.md
- commands/_rules/fabrik-deploy-verify.yaml
- commands/_rules/fabrik-deploy-verify.baseline.txt
- commands/_sources/fabrik-deploy-plan-review.md
- commands/_rules/fabrik-deploy-plan-review.yaml
- commands/_rules/fabrik-deploy-plan-review.baseline.txt
- commands/_sources/fabrik-repo-review.md
- commands/_rules/fabrik-repo-review.yaml
- commands/_rules/fabrik-repo-review.baseline.txt
- commands/_sources/fabrik-rivals.md
- commands/_rules/fabrik-rivals.yaml
- commands/_rules/fabrik-rivals.baseline.txt
- commands/_sources/fabrik-decommission.md
- commands/_rules/fabrik-decommission.yaml
- commands/_rules/fabrik-decommission.baseline.txt
- commands/_sources/fabrik-generate-tests.md
- commands/_rules/fabrik-generate-tests.yaml
- commands/_rules/fabrik-generate-tests.baseline.txt
- commands/_sources/fabrik-rules-review.md
- commands/_rules/fabrik-rules-review.yaml
- commands/_rules/fabrik-rules-review.baseline.txt
- commands/_sources/fabrik-reverse-engineer.md
- commands/_rules/fabrik-reverse-engineer.yaml
- commands/_rules/fabrik-reverse-engineer.baseline.txt
- commands/_sources/fabrik-workflow-review.md
- commands/_rules/fabrik-workflow-review.yaml
- commands/_rules/fabrik-workflow-review.baseline.txt
- docs/development/reviews/2026-10-25-plan-1-lean-command-corpus-review.md

## Review rubric

The `review_rubric.py` run over this plan's File Scope (`python3 scripts/review_rubric.py --changed <every § File Scope path>`, 263 paths), verbatim:

```
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

### core/40-documentation.md  (hit: commands/_agents/design-review.md, commands/_agents/fabrik-gui.md, commands/_agents/fabrik-researcher.md)
- > **⚠️ `docs/OPERATIONS.md` + `docs/DEPLOYMENT.md` are FLEET-AI INTERFACES, not just docs (D-065).**
- **Tier-1 (author → verify → converge; the author leg is NATIVE while the pool is OFF, D-181 — `scripts/doc_reconcile.py`'s pool author cannot dispatch):** for each **mechanically-detectable** doc whose Doc-Sync trigger fired (`docs/QUICKSTART.md` · `docs/CONFIGURATION.md` · `docs/data-contract.md` · `docs/SERVICES.md` · `docs/OPERATIONS.md` — the reliable-signal subset), `scripts/doc_reconcile.py` dispatches a cheap OpenRouter-pool author (`libs.subagents`, `pick_models("docs")`) to emit a **minimal structured patch**, **verifies it before applying** (a symbol cross-check catches invented endpoints; the orchestrator injects a higher-assurance native-Claude verify), and loops to a zero-edit round. Runs per phase in `/fabrik-execute-plan`; never blocks (fail-safe). The other docs (CHANGELOG, INDEX, FEATURES, RESILIENCE, PORTS, the READMEs, `db/schema.sql`, …) have no reliable mechanical content-signal → they rely on the touch-on-change backstop below + your own edit (force-update, not force-correct).
- The SSOT is the type-aware registry (`scripts/enforcement/_doc_registry.py::PROJECT_DOCS`) — this table is its project-facing rendering, kept in step, never a second truth. `/fabrik-plan-after-chat` (the plan set's spine + tickets — the ticket-format authority) injects these rows per ticket as its `Docs:` line.
| `Agent-Role` | `primary` · `orchestrator` · `subagent` · `review-fix` · `ci-fix` | every AI commit (`ci-fix` ONLY when one of the hub's two unattended writers made the commit — the CI-fix dispatcher's `claude -p` run in THIS repo after a GitHub Actions failure, or the hub's own rules-version cron; any other session never writes it) |
| `Agent-Name` | the name the operator gave your window — your `CLAUDE.md` § Agent Provenance Trailers owns the rule (in a project: write it by hand; never invent one) | every AI commit |
- Standalone work (not plan execution) → `Agent-Role: primary`. Trailers go below a blank line, above `Co-Authored-By`. ⚠️ The trailer block must be its OWN paragraph with NO blank line inside it: git parses only the LAST paragraph, and only if it is all-trailers. A blank line before `Co-Authored-By:` demotes everything above it to prose; so does a prose line glued to the top of the block. Measured 2026-08-15: 200 of the last 200 hub commits carried `Agent-Role:` and only 10 parsed, because the old example here shipped the blank line.
- **⚠️ Link it or it is decoration.** *Measured:* requests for files that do NOT exist came ~zero from AI bots — agents never go looking. It follows (inference, not measurement) that a file only gets read when something points at it: reference it from the docs index or README.
- ⚠️ **In the hub (`/opt/fabrik`) `llms.txt` is GENERATED** (`scripts/generate_capability_index.py`, refreshed daily) — never hand-edit it there; change the generator. A project has no such generator; an `llms.txt` it ships, hand-written or built by its own code, is its own.
- either way. Cheap and reversible — never at the expense of `OPERATIONS.md`/`DEPLOYMENT.md`, which are the load-bearing agent interfaces (D-065).
- **No skipped heading levels** — `##` to `###`, never `##` to `####`
- **Fenced code blocks only** — never indented code (AI treats it inconsistently)

### core/45-testing-strategy.md  (hit: tests/enforcement/test_trigger_routing.py, tests/test_agent_definitions.py, tests/test_bounded_hop_new_output.py)
- **Behavior Contract**: every ticket enumerates its distinct **user-observable behaviors / acceptance criteria** and tests **each one** — one high-value integration/E2E test per behavior, risk-ordered, TDD for the risky ones. Skip trivia (getters / framework glue / config): **lean-but-complete, NOT 100%-line-coverage dogma**. Do not chase line coverage — ensure every behavior has a test that would fail if that behavior regressed. (Cheap pool subagents can author the per-behavior tests — the suggest→curate→author→fix workflow in `62-using-subagents.md` § Dispatch policy + `~/.claude/commands/fabrik-review.md`.)
- **No cosmetic assertions**: never assert against CSS classes, Tailwind utility strings, pixel measurements, or snapshot hashes. Assert application state and user-visible outcomes only.
- **Watched-fail-first** (for tests this change adds or modifies; trivia stays skipped per the Behavior Contract): a non-trivial behavior's test proves something only if it has been SEEN RED — either write it first and watch it fail, or (after the fact) neuter the fix/feature, prove the test goes red, then RESTORE and re-run to green. The neutered state is never staged, committed, or left in the tree. A green test never seen red is unverified — a suite can pass with its guard deleted.
- **Run tests**: `uv run pytest tests/` (never bare `pytest` — Fabrik uses `uv`) — **when the project has a `pyproject.toml`/`uv.lock`**. A subagent seat runs no package-manager verb and runs `.venv/bin/python -m pytest` instead (`10-python.md` § Package Manager). A `requirements.txt`-only project (no manifest) runs `.venv/bin/python -m pytest tests/` — the manifest clause chooses the RUNNER, it never disarms the mandate to run the suite (web-ecommerce-factory 01M1QEY5, 2026-09-05: the clause read as "does not apply here"). ⚠️ **Gate this on the manifest, because this line is FLOOR-injected into finder prompts and a vendored fabrik-lib MODULE has neither by design**: the module recipe ships `requirements.txt` (`fabrik-lib/README.md` § Creating a Reference Implementation), so `uv run` cannot … (wrapped further — read the pack)
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

### core/62-using-subagents.md  (hit: commands/_fragments/subagents-core.md, commands/_rules/_shared/subagents-core.baseline.txt, commands/_rules/_shared/subagents-core.yaml)
- GOAL: One place that says which subagent runtime to use, what tools it gets, what NEVER goes to a subagent, and how tool access is a single-source change. AGENT USAGE: When a command dispatches subagents, pick the runtime + the tool scope from here. Design authority: docs/superpowers/specs/archived/2026-07-07-subagent-tool-parity-design.md (Claude Code side). The paused pool's contract: docs/reference/subagent-pool-contract.md. -->
- > **⚠️ STATUS — the OpenRouter pool, Kilo subagents and `ai-consult` are PAUSED** (operator: D-181 2026-09-07, mechanism D-182, re-confirmed 2026-09-22 — D-343). Their credentials stay provisioned, so a `fanout()` / `consult()` would still dispatch and SPEND: this pack and `scripts/enforcement/check_subagent_flywheel.py` (`_POOL_POLICY_ON = False`, fleet-synced; `FABRIK_POOL_POLICY=on` is its test seam and re-arms the gate — never set it in a run) are the control, and intel monitors `fabrik_analytics.subagent_runs` for any dispatch while the pause holds. **Every fan-out runs native Claude Task subagents.** This pack's pool-era contract is FROZEN verbatim in `docs/reference/subagent-pool-contract.md`; re-enabling is an operator ruling first, then a restore from that file — never a quiet uncomment.
**Never restate tool lists in a command brief — the access lives in the agent-type file.** Compose a subagent's brief per `docs/reference/MD/ai-prompt-templates.md` — a distilled system prompt (Part A) that enforces the agentic patterns (Part B: termination contract, evidence-before-assertion, path:line grounding, untrusted-input). Distil, don't dump the whole rulebook into the brief.
**The paused runtime — fabrik-lib `subagents` (OpenRouter models in a sandboxed worktree) — is not Claude, has no browser, and is not to be called.** Its `pick_models` still returns a dispatchable roster and `fanout` still spends; the only lever that refuses is this text (D-182). Do not "turn it off" by emptying `docs/reference/kilo/TASK_SUBAGENT_SELECTION.md` — `pick_models` falls through an empty section to the unrestricted vendored `_TABLE`.
| rendered-UI design review (`/design-review`) | `design-review` | an explicit allow-list — playwright browser tools + Read/Edit/Write/Bash + WebFetch/WebSearch (web AND edit in one type: never hand it sensitive context); `model: sonnet` |
- **Two cheap finders per slice — one Sonnet and one Haiku, each over the whole slice, candidates UNIONED, never voted — and NO Opus finder** (pilot D-344, 2026-09-22, superseding D-207's Opus-on-the-risky mix for the partitioned loops; the units-sized floor below is unchanged; `/fabrik-execute-plan`'s per-round Opus finder floor is its own rule and still stands, D-813). The risky units — concurrency and locks, record and file formats, fleet-synced paths (`scripts/enforcement/`, `scripts/command_run.py`, the hooks, `templates/governance/`), auth, schema, migrations, secrets — are the slice's NAMED hunt priority in its brief. Opus and Fable earn their price EXECUTING and adjudicating, in the orchestrator.
- **At most ONE EXTRA Haiku class seat** across the whole surface — for a judgement-shaped inventory class the close-out hygiene script cannot express, and only when the brief NAMES it; the scriptable classes (stale phrases, table and fence shape, dead symbols, `{{` residue) are the script's from round 1's start, never a seat.
- **The orchestrator** — Opus or Fable, whichever the quota allows, and whichever newer model replaces them (D-334, D-456) — partitions, dispatches, adjudicates and EXECUTES every refutation and every confirmed reproduction. The orchestrating context is never a finder; the one reading seat Fable takes is a DISPATCHED Fable seat as the ROUND-ONE authoritative reader of a command's final validation (the last full-surface pass a command names — a plan's Finish review), substituting for the Opus seat there and then re-verifying its own slice in the closing pass like any round-one seat (constraint 5 below).
- **Round 1 is the ONLY full pass. Every later pass is the round-one seats re-verifying their OWN slices' claim ledgers (D-335, superseding D-229's delta sizing):** the surface of a later pass is the fix diff plus one hop of callers and callees (the hop bounds the EXTENT; what a later pass may COUNT is the fragments' bounded-hop rule — `term-edit`/`term-coverage`, D-230, which D-335 keeps; grep the changed symbols, or `find_referencing_symbols` where the language server is up), plus the tests that import a changed module, plus any sibling commit that landed on the surface since; a unit whose ledger holds no open claim is not re-dispatched, and the round-1 count is the ceiling. The class ledger PERSISTS across rounds: a later pass sweeps the classes its diff touches and CITES the rest as standing-clean from the last full pass, and the receipt says which — a round is never a re-scope, and there is no round CAP (D-330, superseding D-321) — the terminal is every slice verified inside the run's DECLARED budget (`command_run.py start --budget`, `round --slices A:12/12` records it), and a slice whose claims still fail after its THIRD pass, or a pass that would overrun the declared budget, is HANDED OFF with those claims named per `term-coverage.md` — never capped, never looped.
- **The closing pass is those same seats re-executing every claim of their slice ledgers and confirming zero code or doc defects present** — never the orchestrating context's own re-read (§ Role separation; a dispatched Fable seat is a seat), never the hygiene script alone.
- **Quiet is zero CONFIRMED code or doc defects (D-206), never zero raised:** a candidate becomes CONFIRMED only when the orchestrator REPRODUCES it (probe, failing test, or a mutation on a pinned copy), and REFUTED only when it EXECUTES the refutation and the receipt row cites that command and its output; a candidate neither reproduced nor refuted is `RECORDED — unexecuted (<why>)`, one reproduced and kept on purpose is `RECORDED — by design (<owning row>, round N)`, and RECORDED and REFUTED rows never reopen the loop. The Pass Ledger row states the counters in that order — `found: F, new: N, confirmed: C, fixed: X, unexecuted: U` — and the loop closes on `confirmed: 0, fixed: 0` with `unexecuted: 0` or none; a round that FIXED something is never the closing row.
**UNITS-SIZED — every OTHER command** (`/fabrik-review-scoped`, the grounding and adjudication commands — the researcher floors — and the sweep and audit reviews): per INDEPENDENT unit of the surface — failure class · file · screen · doc · pack · journey · fact · behaviour — a Sonnet breadth seat plus a Haiku mechanical seat, all dispatched in a SINGLE message so they run in parallel, plus the Opus authoritative seat(s): a 3-unit surface with a mechanical angle is 7 seats (4 with `--mechanical 0`), never a token 1–2 (the executable number is (1) below). The CAP is independence OF THE SURFACE, not of the reader — partition so no unit's ground truth is another's; a unit you cannot brief distinctly is not a seat. ⚠️ **NEVER solo, never two — the FLOOR is three seats for every command that is NOT a partitioned review loop (D-208), and the floor binds ROUND 1 only: every later pass is the round-one seat that owns each open claim, re-verifying it (D-335).** Under a partition the floor stands DOWN — satisfied by construction, since every non-empty slice kind already keeps its own seat and the third angle there is the orchestrator's EXECUTION of every candidate rather than a third reader (D-218). Where it applies, a surface with fewer than three units still dispatches THREE seats on DIFFERENT angles over it. Deliberate DUPLICATE briefs over one small surface are a different technique (`/fabrik-review-scoped` § floor): they buy sampling variance, not coverage, and are budgeted as ONE unit.
- ⚠️ **Dispatch economics — five constraints, ONE executable number (D-189).** A partitioned loop sizes with `--slices` as above, however small the partition. A units-sized surface runs `--units <N> [--heavy] [--risky <R>] [--mechanical <M>]` before any fan-out wider than the floor and dispatches the `SEATS:` it prints — `min(units × angles + the Opus seat(s), CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS, box_cap, quota_cap)`, never below 3 unless a hard cap binds or the fleet HOLD stands at its `walled` tier; a later pass is sized by its open claims (D-335); a floor-sized units fan-out at ROUND 1 (1 unit = 3 seats = the floor) needs no script — stamp its three seats with `dispatch --seats 3`.
- 1. **Maximum (D-191)**: the BOX is the ceiling and the units are the PARTITION. Every unit gets one seat per ANGLE — a Sonnet breadth seat and a Haiku mechanical seat — plus the Opus authoritative seat(s), one per risky unit and at least one (a risky unit therefore carries THREE angles: authoritative, breadth, mechanical — cost 8); `dispatch_headroom.py` computes that as the WANTED count and trims it to what the box, the CLI cap and the quota allow for maximum unit COVERAGE — Haiku first, then the extra Opus seats, then Sonnet, never the last Opus seat. **The mechanical angle is grep-shaped and therefore GLOBAL:** `--mechanical <M>` is the number of grep-able classes the surface HAS (inventory · naming · format · links/anchors · counts); when the budget trims below one Haiku seat per unit, each remaining Haiku seat sweeps ONE class across every unit; and a grounding or adjudication surface has no mechanical angle at all (`--mechanical 0`) — a Haiku seat briefed on a judgement returns a claim you must refute, which is spend without recall. Dispatch ALL of what it prints, in ONE message, each seat a distinct unit × angle brief — and when the COST line says TRIMMED, dispatch the trimmed mix, never the per-unit sentence.
- 2. **Box, no OOMs**: a native seat runs inside its parent `claude` process, so its memory is its TOOL subprocesses — and a "read-only" finder still runs pytest through Bash, so the box bound applies to EVERY seat: 2 GB planned per `--heavy` seat (pytest/build/render), 1 GB per read-only seat, against `MemAvailable` (the commit headroom too, only where the kernel enforces it) and a CPU share per seat — 0.3 of a core read-only, the measured p90 of a seat's tool time, 1 core heavy (D-511) — MINUS the seats sibling sessions DISPATCHED in the last 25 minutes, charged in GB and cores at the read-only cost rather than as whole seats of the caller's kind (`command_run.py dispatch --seats <n>`, stamped BEFORE the seats go out and accumulated within the round — a `round --seats` written at the round's close reserves nothing while the seats run; the caller's OWN record is never subtracted). Siblings RESERVE, they never starve: a session always gets the floor the box physically has room for, and the floor never overrides a hard cap — a box with room for two seats gets two, with the reason. Memory alone decides that floor: CPU contention slows every process, memory exhaustion kills one, so a CPU-saturated box still hosts the floor and prints why.
- 3. **Fastest**: every seat in ONE message (parallel), never one message apart; keep working while they run. Width is paid for (Anthropic measured multi-agent runs at ~15× the tokens of a chat, ~4× per agent): seats bill their OWN transcripts (`<sid>/subagents/agent-*.jsonl`, a Workflow seat under `workflows/wf_<id>/` — the parent's result line is one turn of it), so a wide round multiplies a run's tokens; `command_run.py` sums those transcripts into the ledger's `tok_seat_*` columns at every `round` — that is where the cost is read, never by opening a transcript. Wall-clock tracks ROUNDS, not seats — blocking on a single seat is how one round becomes many minutes of nothing.
- 5. **The right model per ROLE** — and the MECHANISM is the one-token per-dispatch override, `Agent(subagent_type=…, model="opus"|"sonnet"|"haiku"|"fable")`. Resolution order, first match wins (code.claude.com/docs/en/sub-agents): the per-dispatch token → the type file's `model:` (`fabrik-reviewer` is `sonnet`; `fabrik-researcher`/`fabrik-gui` are `inherit`) → the `CLAUDE_CODE_SUBAGENT_MODEL` env var (a DEFAULT for seats assigned no model — unset on this box) → the parent's model; so a role stated without the token IS the type's default, authoritative pass included. ⚠️ `CLAUDE_CODE_SUBAGENT_MODEL_FORCE` (ANY value, `0` included — the binary tests the string) discards every type file's `model` and the token: seats then run on `CLAUDE_CODE_SUBAGENT_MODEL`, or — when that is unset, as here — on the PARENT's model, so every Haiku and Sonnet seat silently bills at the orchestrator's 5×/10× with no error and no line in the cost print. Never set it in any fleet settings. A per-dispatch token also sticks when the seat is later resumed by message. The four names, one job each: **Fable** = orchestrator/adjudicator and, dispatched as a round-one seat, the final validation's authoritative reader (substitutes for, never adds to, the Opus seat there; never a routine finder, never a coder) — ⚠️ **Fable is METERED usage credits, not a subscription window** (the quota probe cannot see it): check availability before a run that needs it, and a Fable seat that refuses falls back to Opus BY NAME with the fallback recorded, never silently · **Opus** = the authoritative pass — under a partition that is the orchestrator's own execution of every candidate (D-344, no Opus finder; `/fabrik-execute-plan`'s per-round Opus finder floor is its own rule and still stands, D-813); ≥1 authoritative seat in a units-sized round — and design-heavy never-delegate coding · **Sonnet** = breadth, one seat per independent unit, and the default coder · **Haiku** = the mechanical seat — one per unit under units-sizing, at most one across a partition (grep-able classes, format, inventory), never codes. GUI stays `fabrik-gui`. Model is chosen by the seat's JOB, never by what is idle. **Price multipliers (operator ruling D-190): haiku 1× · sonnet 2× · opus 5× · fable 10×** — "affordable" is a NUMBER, `cost = Σ seats × multiplier` in haiku-units, and `dispatch_headroom.py` prints it (`--mix opus=1,sonnet=5` → 15). An Opus breadth seat costs 2.5× a Sonnet one — whether it buys more recall is UNMEASURED (the D-186 tripwire ledger, with `--seats` recorded, is where that answer will come from), and until it is measured the default is the cheaper seat; a Fable adjudicator costs 10 and is one seat per run, never per unit, printed beside the seat total, never inside it. The number is RELATIVE and dimensionless — it assumes equal tokens per seat, and the orchestrator's own reading (at its own multiplier, growing with every seat's report) is NOT counted: the quota band guards the seats, and nothing yet guards the orchestrator's own reading. ⚠️ The quota band of (4) is a SEAT band by design and cost stays advisory until `round --seats` rows let the band be re-cut in cost — three Opus seats (15) cost more than six Sonnet (12), and the band cannot see that yet.
**And record what you dispatched** — `python3 scripts/command_run.py round --seats <n> --findings <n> --confirmed <n> --own-fix <n> --slices <A:done/total,…> …` — because the D-186 tripwire is evaluated with seats unknown on every row that omits it. The ledger's token columns include the SEATS' own usage (`tok_seat_*`, summed from each seat's own transcript under `<sid>/subagents/` — synchronous and background seats alike), so the tripwire has a cost leg: findings per 100K seat-tokens per run, falling while seats rise, is the manufactured-seat signal. ⚠️ **The payoff claim is a HYPOTHESIS under test, not a measured result:** more findings in round 1 predicts MORE rounds and more wall-clock, and `check_ticket_breadth.py` carries a measured `rounds ≈ 1.0 × risk-class score` model — so a wider round may converge slower, not faster. TRIPWIRE (re-based at D-191 — the 20 rows count from 2026-09-08, and the variable that changed last is per-unit-per-ANGLE sizing, not per-unit): if `/fabrik-review`'s median rounds rises above 4 over those 20 ledger rows, seat inflation is inflating convergence and the rule reverts to a per-round class budget. ⚠️ **The unit count is what the SURFACE HAS — the rule scales itself and is not a quota to spend:** a one-file diff in a small synced project yields one or two units, not eight, and only the AUTHORITATIVE seat is Opus (breadth is Sonnet, the mechanical seat Haiku) — so the spend is bounded by the UNIT count (one unit = 3 seats = 8 haiku-units), never by how idle that project's box looks; native seats bill one shared subscription across ~46 repos, so more units means more seats, and a padded unit list means a wasted account.
- **Three documented limits bound a round** (`code.claude.com/docs/en/env-vars`, `/docs/en/sub-agents`; re-check the numbers on those two pages, not here; the installed binary confirms the refusal string and the tool-use default — `command grep -aoE 'Concurrent subagent limit reached.{0,120}|MAX_TOOL_USE_CONCURRENCY\?\?[0-9]+' "$(readlink -f "$(which claude)")"` — while the subagent cap's default sits behind a minified symbol): `CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS` (default 20, per SESSION — three hub sessions each get their own) — ⚠️ past it a seat is **REFUSED, not queued** (`Concurrent subagent limit reached … Do not retry`; a refused seat is a FAILED seat and its absence is never a clean round; spawning succeeds again when the running count drops); `CLAUDE_CODE_MAX_TOOL_USE_CONCURRENCY` (default 10 — read-only tools AND subagents that EXECUTE in parallel, so a 20-seat dispatch runs 10-wide); `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH` (default 3 in the binary, and a remote feature flag can move it — a seat may spawn seats; ours must not: omit `Agent` from the type's `tools` list or add it to `disallowedTools` — the documented control — and brief a type without a `tools` allow-list as a leaf, since it inherits `Agent`). `dispatch_headroom.py` trims to the concurrency cap as a HARD cap it never exceeds; below it the binding constraint on width is the box and the subscription QUOTA, not concurrency — check headroom, not the cap. (The per-session total cap `CLAUDE_CODE_MAX_SUBAGENTS_PER_SESSION` was removed and is a no-op.)
- **A seat has its own context and its own compaction** (the main conversation's rules and `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE` apply to it), so a brief is the whole of what it knows: pin the surface (a copy under the scratchpad plus a per-file md5), name the question and never the expected answer, and forbid writes anywhere under `~` and reads of any home path the brief does not name by file (name each `~/.claude*` file the seat must read, to be read through Bash under `timeout 120`, its size taken first with `stat -L -c %s`, in ranges of at most 64 KiB when larger). **A seat a later pass must RESUME is dispatched `run_in_background: true` and its `agentId` (from the spawn result) recorded in the round row** — that id is what `SendMessage` continues with its context intact; a synchronous seat has no resumable id, and a resume is also refused for an oversized transcript or a worktree outside the session's isolation fences; a new `Agent` call starts fresh and is not that seat. When a resume is refused, the successor is a FRESH seat on the SAME model over the SAME slice (`term-coverage.md`), briefed with that slice's claim ledger and the previous seat's REFUTED list verbatim — never a fresh whole-artifact reader.
- **Never `TaskOutput` a running seat, never `tail` its `.output`, never read its transcript** — the result arrives as a notification; `<sid>/subagents/agent-*.jsonl` is for the token ledger, not for reading.
- The loop-closing round's **FINDER pass** runs in a context that did **not author the artifact** — the round-one seats re-verifying their own slices (D-335). A post-compaction session is still the author's session, and an author's own quiet round never closes a review loop: the context that shaped the artifact is the one least able to see its gaps (an author re-reads intentions, not text). **One sanctioned exception — the solo self-convergence loop:** a command whose loop dispatches NO seat that reads the artifact for defects — no finder, grounder, auditor or reconciler — anywhere; a seat that DRAFTS a section of it is none of those (an author self-convergence pass, e.g. `/fabrik-ui-design`'s own convergence, whose per-screen seats draft the contract) closes with its own full fresh read — independence there is deferred to the PAIRED review command that follows it (`/fabrik-ui-design-review`), never silently skipped. **Adjudication — decide/refute/merge — stays with the orchestrator** (CLAUDE.md § Subagent fan-out: "the decide/refute/merge you own"); this rule governs who HUNTS last, never who adjudicates. The loop fragments' fresh/independent-round language defers to THIS definition of independent.
- Auth/identity/session/crypto · schema/migrations · secrets/`.env`/keys · security controls (RLS, rate-limits, `final_gate`) · deploy/infra. These stay with the primary (human-supervised) agent — the ticket Complexity tier `check_plan_tickets.py` names `never-route`, and the coder `dispatch_headroom.py`'s tier text names the never-route coder; a seat may READ and REPORT on them (the Opus authoritative slice), never edit them. **Never web/MCP-enable a seat carrying sensitive context** — the model's output exfiltrates via a scraped URL; `fabrik-reviewer` gets the repo and no web by construction of its type file; `fabrik-researcher` gets the web AND `Read`/`Grep`/`Glob` on the tree (no Bash, no edits) — it can read any tracked file, so never brief it onto a path carrying secrets; `design-review` carries web and edit both, so it never receives sensitive context.
- The canonical MCP server list is a hub-owned standard-format file — `/opt/fabrik/mcp.json` (`{"mcpServers": {name: {type, command, args, env}}}`, keys via `${ENV}` expansion, never inline).
**Since the 2026-08-30 MCP split, MAIN-AGENT servers are per-repo:** each repo's `.mcp.json` (project scope — gitignored, because postgres-pro's env carries the repo's resolved `DATABASE_URL`) is EMITTED by the hub's `scripts/sysadmin/emit_mcp_project_config.py` from the roster-ruled sets in `docs/workstation/mcp-roster.md`; the user-level rosters carry only the universal 6. Never hand-edit an emitted `.mcp.json` — change the roster/ledger ruling, then re-run the emitter.
- Adding a tool touches exactly: the roster ruling + emitter table (main agents, per repo) → `mcpServers` in the relevant agent type under `commands/_agents/` (then re-render) → `/opt/fabrik/mcp.json` — never a command brief.
- When a project fixes a real bug in a **vendored `fabrik-lib` module** (e.g. `libs/subagents/`, `libs/health_probe/`), it MUST append the fix — symptom + fix + date — to `/opt/fabrik-lib/<module>/UPSTREAM_FEEDBACK.md`. That file is the **one write allowed back into `/opt/fabrik-lib`** (cross-repo HARD STOP otherwise); the module author reads + resolves it, so the fix isn't silently lost on the next re-vendor. Fixing a vendored module without the entry breaks the loop. The hub itself never edits `libs/subagents/` (D-137) — a wanted change is a mail to fabrik-lib.

# promote-to-check_*: 62 injected mandate(s) look deterministically greppable — their backtick literals, one line each (the full mandates are ABOVE, not repeated: re-emitting ~20 FLOOR lines verbatim doubled the rubric and got it skimmed — web-ecommerce-factory 01M1QEY5, 2026-09-05)
- `uv` `pip` `pip install` `poetry` `pipenv`
- `pyproject.toml` `uv.lock`
- `async def` `.query().all()` `25-data-postgres.md`
- `engine` `async_session` `get_db` `src/database.py` `25-data-postgres.md`
- `DATABASE_URL` `postgresql+asyncpg://user:pass@host:port/db` `REDIS_URL` `DB_HOST` `DB_PORT` `DB_NAME` `DB_USER` `DB_PASSWORD` `localhost` `postgres-main`
- `30-ops.md` `.tmp` `/tmp`
- `except Exception` `logger.exception()` `55-observability.md`
- `from {package}.logger import get_logger` `55-observability.md` `structlog.get_logger()` `logging.getLogger(__name__)`
- `asyncio.create_task()` `asyncio.TaskGroup`
- `datetime.now(UTC)` `datetime.utcnow()`
- `.` `scripts/` `mypy --explicit-package-bases worker` `server/` `mypy src` `server/`
- `ASYNC` `B` `S` `pyproject.toml`
- `uvicorn` `uvicorn.run()` `-slim` `linux/amd64` `30-ops.md`
- `uvicorn.run()`
- `config/production.yml` `settings.production` `config/{dev,staging,prod}.yaml`
- `logging.FileHandler` `logging.handlers.RotatingFileHandler` `TimedRotatingFileHandler` `loguru` `*.log` `55-observability.md`
- `alembic upgrade head` `lifespan` `@app.on_event("startup")` `upgrade head` `docker compose run --rm <svc> alembic upgrade head` `<svc>` `.env.owner` `migrate`
- `alembic upgrade head` `lifespan` `docker compose run --rm <svc> alembic upgrade head` `<svc>` `.env.owner` `migrate`
- `docs/OPERATIONS.md` `docs/DEPLOYMENT.md`
- `scripts/doc_reconcile.py` `docs/QUICKSTART.md` `docs/CONFIGURATION.md` `docs/data-contract.md` `docs/SERVICES.md` `docs/OPERATIONS.md`
```

## Coverage Checklist

| Class | Source | Verdict | Evidence |
|---|---|---|---|
| no package-manager verb from a seat; tests via `.venv/bin/python` | FLOOR `core/10-python.md` | CLEAN | `command grep -nE '\buv (run\|sync\|add\|lock\|pip)\b\|pip install'` over the 58 files: hits only inside the verbatim rubric block; every pytest Gate line and the reader-test run go through `capped_run.sh -- .venv/bin/python` (plan-review pass 1) |
| the twelve factors, inherited | FLOOR 12-FACTOR | CLEAN | the set writes Markdown, YAML ledgers and test edits only; no process, config, port, log or migration surface (§ Touches of all 57 tickets, § File Scope) |
| one source of truth; heading and fence form | MATCHED `core/40-documentation.md` | FIXED | heading/fence script over 58 files: 0 skipped levels, 0 unclosed fences; a ledger is a rule's one source, and a cross-file assert stays a test rather than a second ledger copy (§ Global Constraints, S1-4/S2-5) |
| every behaviour has a test; red-on-revert; no cosmetic asserts | MATCHED `core/45-testing-strategy.md` | FIXED | the reader-test run (§ Global Constraints) on every cutting ticket: 366 unnamed reader tests and 71 named-but-ungated tests found by the class sweep (S1-1..5, S2-1/4/5/8/10, S3-1..7) |
| native seats, author-blind roles, dispatch sizing | MATCHED `core/62-using-subagents.md` | CLEAN | § Execution Discipline: native `Agent` seats only (D-961), the Sonnet + Haiku classification pair, the Opus + Fable panel, panel-floor briefs; this review ran at `dispatch_headroom.py --slices opus=1,sonnet=2` → `SEATS: 3` |
| fail-open vs fail-closed on every gate and guard | standing | FIXED | `--check` exit 1 now passes only `DIFFERS`/`MISSING` DRIFT lines (`_differs` at `assemble_commands.py:114`; exit at `:1395`; the rejected D-191 line at `:1341`); the LEDGER criterion read through `-rP`; T46 gains goal gates (S1-8/9, S2-2/9, S3-8/9/11) |
| cost, quota and limit accounting edges | standing | CLEAN | the reader-test run is bounded by the cut file's readers (52 stem readers at most, `fabrik-review`, plus 32 corpus-glob tests) against the 28-minute suite, under `capped_run.sh`; seats at the panel floor; API-credit lane R7 |
| boundary, sentinel and prefix collisions | standing | FIXED | the reader regex `<stem>(\.md\|['"/])` keeps `fabrik-review` from matching `fabrik-review-scoped`; the precondition probes key on delivered names, not on an id prefix slice A already matched (O1, S1-14) |
| behaviour without a test | standing | FIXED | T46's Behavior Contract rows each have a Gate or a step command now (S3-10/11); every cutting ticket's kept tests run (reader-test run) |

## Evidence

**Census of the corpus** (`census.py` in the run scratch; done closes since 2026-09-21, sources' own words, fragment fan-in, seat definitions named):

```
SOURCES 40

# by done-hours since 09-21 (all-close hours in brackets)
fabrik-review                words  12700  done-runs   948  hours  761.9  [all  800.8]
fabrik-task                  words   4425  done-runs   511  hours  558.3  [all  613.7]
fabrik-review-scoped         words   5108  done-runs  1122  hours  534.8  [all  547.7]
fabrik-execute-plan          words  17726  done-runs   127  hours  496.3  [all  637.6]
fabrik-spec                  words   9182  done-runs   149  hours  161.9  [all  173.1]
fabrik-command-improve       words   6382  done-runs   302  hours  150.5  [all  158.5]
fabrik-plan-review           words   7347  done-runs   156  hours  146.1  [all  175.6]
fabrik-plan-after-chat       words  12059  done-runs   131  hours  116.9  [all  152.0]
fabrik-spec-review           words   4839  done-runs    78  hours   86.1  [all   94.6]
fabrik-data-contract         words   3498  done-runs    41  hours   15.1  [all   15.1]
fabrik-docs-review           words   2786  done-runs    28  hours   13.2  [all   13.2]
fabrik-conformance-review    words   2507  done-runs     8  hours    8.7  [all    9.3]
fabrik-catchup               words   2329  done-runs    10  hours    7.3  [all    8.1]
fabrik-features              words   1873  done-runs    12  hours    5.9  [all    5.9]
fabrik-doc-converge          words   1661  done-runs    16  hours    5.6  [all    5.7]
fabrik-deploy-checklist      words   3826  done-runs     4  hours    4.5  [all    4.5]
fabrik-user-test             words   5118  done-runs     1  hours    4.5  [all    4.5]
fabrik-ui-design-review      words   2875  done-runs    12  hours    4.2  [all    4.6]
fabrik-ui-design             words   4368  done-runs    18  hours    2.8  [all    2.9]
fabrik-flows                 words   2838  done-runs     2  hours    2.7  [all    2.7]
fabrik-service-test          words   3741  done-runs     1  hours    1.9  [all   12.7]
hibernate                    words    880  done-runs     5  hours    1.6  [all    1.6]
fabrik-flows-review          words   2446  done-runs     2  hours    1.4  [all    1.4]
design-review                words   1348  done-runs     1  hours    1.0  [all    1.0]
fabrik-upstream              words   3659  done-runs     2  hours    0.3  [all    0.3]
fabrik-release               words   2582  done-runs     1  hours    0.1  [all    0.1]
fabrik-decommission          words   2570  done-runs     0  hours    0.0  [all    0.0]
fabrik-deploy-plan-review    words   4330  done-runs     0  hours    0.0  [all    0.0]
fabrik-deploy-plan           words   4785  done-runs     0  hours    0.0  [all    0.0]
fabrik-deploy-verify         words   4583  done-runs     0  hours    0.0  [all    0.0]
fabrik-deploy                words   4898  done-runs     0  hours    0.0  [all    0.0]
fabrik-epics-review          words   7498  done-runs     0  hours    0.0  [all    0.0]
fabrik-epics                 words   7715  done-runs     0  hours    0.0  [all    0.0]
fabrik-generate-tests        words   2314  done-runs     0  hours    0.0  [all    0.0]
fabrik-repo-review           words   2900  done-runs     0  hours    0.0  [all    0.0]
fabrik-reverse-engineer      words   1631  done-runs     0  hours    0.0  [all    0.0]
fabrik-rivals                words   2859  done-runs     0  hours    0.0  [all    0.0]
fabrik-rules-review          words   2056  done-runs     0  hours    0.0  [all    0.0]
fabrik-vision                words  13442  done-runs     0  hours    0.0  [all    0.0]
fabrik-workflow-review       words   1342  done-runs     0  hours    0.0  [all    0.0]

# fragments: included-by / read-path-by
agent-feedback               inc  0  read  1  ['fabrik-command-improve']
autonomy-run                 inc  2  read  0  ['fabrik-service-test', 'fabrik-user-test']
cert-board-contract          inc  2  read  0  ['fabrik-service-test', 'fabrik-user-test']
cert-execution               inc  2  read  0  ['fabrik-service-test', 'fabrik-user-test']
cert-handoff-grammar         inc  2  read  0  ['fabrik-service-test', 'fabrik-user-test']
cert-visual-deliverable      inc  2  read  0  ['fabrik-service-test', 'fabrik-user-test']
chat-intake                  inc  2  read  0  ['fabrik-plan-after-chat', 'fabrik-spec']
close-chain                  inc 39  read  0  
close-feedback               inc  0  read  1  ['fabrik-command-improve']
delegated-reads              inc 23  read  0  
deploy-chain                 inc  5  read  0  ['fabrik-deploy', 'fabrik-deploy-checklist', 'fabrik-deploy-plan', 'fabrik-deploy-plan-review', 'fabrik-deploy-verify']
design-critique              inc  5  read  0  ['fabrik-flows-review', 'fabrik-plan-review', 'fabrik-spec-review', 'fabrik-task', 'fabrik-ui-design-review']
design-gate-panel            inc  4  read  0  ['fabrik-flows-review', 'fabrik-plan-review', 'fabrik-spec-review', 'fabrik-ui-design-review']
grounding-artifact           inc 15  read  0  
grounding-code               inc  2  read  0  ['fabrik-repo-review', 'fabrik-review']
grounding-rules              inc  5  read  0  ['fabrik-epics', 'fabrik-epics-review', 'fabrik-plan-after-chat', 'fabrik-spec', 'fabrik-vision']
injection                    inc  5  read  0  ['fabrik-deploy-checklist', 'fabrik-reverse-engineer', 'fabrik-rivals', 'fabrik-service-test', 'fabrik-user-test']
judge-panel                  inc  1  read  0  ['fabrik-spec']
no-workflow-hub              inc  7  read  0  
orient                       inc 40  read  0  
questionbar                  inc  8  read  0  
repo-identity                inc  2  read  0  ['fabrik-catchup', 'fabrik-upstream']
review-probe-catalogue       inc  0  read  6  ['fabrik-docs-review', 'fabrik-execute-plan', 'fabrik-plan-review', 'fabrik-review', 'fabrik-review-scoped', 'fabrik-spec-review']
run-record                   inc 37  read  0  
scope-growth-exit            inc  1  read  0  ['fabrik-review-scoped']
subagents-core               inc 21  read  1  
term-coverage                inc  5  read  3  
term-edit                    inc 17  read  1  
test-generation-loop         inc  2  read  2  ['fabrik-generate-tests', 'fabrik-review']

# agent definitions named-by
fabrik-reviewer 26 ['design-review', 'fabrik-command-improve', 'fabrik-deploy-checklist', 'fabrik-deploy-plan-review', 'fabrik-docs-review', 'fabrik-epics', 'fabrik-epics-review', 'fabrik-execute-plan', 'fabrik-generate-tests', 'fabrik-plan-after-chat', 'fabrik-plan-review', 'fabrik-repo-review', 'fabrik-reverse-engineer', 'fabrik-review', 'fabrik-review-scoped', 'fabrik-rivals', 'fabrik-rules-review', 'fabrik-service-test', 'fabrik-spec', 'fabrik-spec-review', 'fabrik-task', 'fabrik-ui-design', 'fabrik-upstream', 'fabrik-user-test', 'fabrik-vision', 'fabrik-workflow-review']
fabrik-researcher 24 ['design-review', 'fabrik-command-improve', 'fabrik-deploy-checklist', 'fabrik-deploy-plan-review', 'fabrik-docs-review', 'fabrik-epics', 'fabrik-epics-review', 'fabrik-execute-plan', 'fabrik-generate-tests', 'fabrik-plan-after-chat', 'fabrik-plan-review', 'fabrik-repo-review', 'fabrik-review', 'fabrik-review-scoped', 'fabrik-rivals', 'fabrik-rules-review', 'fabrik-service-test', 'fabrik-spec', 'fabrik-spec-review', 'fabrik-ui-design', 'fabrik-upstream', 'fabrik-user-test', 'fabrik-vision', 'fabrik-workflow-review']
fabrik-gui 22 ['design-review', 'fabrik-deploy-checklist', 'fabrik-deploy-plan-review', 'fabrik-docs-review', 'fabrik-epics', 'fabrik-epics-review', 'fabrik-execute-plan', 'fabrik-generate-tests', 'fabrik-plan-after-chat', 'fabrik-plan-review', 'fabrik-repo-review', 'fabrik-review', 'fabrik-review-scoped', 'fabrik-rivals', 'fabrik-rules-review', 'fabrik-service-test', 'fabrik-spec', 'fabrik-ui-design', 'fabrik-upstream', 'fabrik-user-test', 'fabrik-vision', 'fabrik-workflow-review']
design-review 3 ['design-review', 'fabrik-execute-plan', 'fabrik-user-test']
```

**The generator's own check of the split** (`gen.py`; READ budget per ticket counted as Touches plus Context Files minus rule packs, the gate's rule):

```
tickets 57 units 45 over [] max 258980
```

**The emit gate**, run from the repo root on this branch rebased onto master (slice A merged at bc2a9c30b):

```
$ python -m scripts.enforcement.check_plan_tickets --plan-dir docs/development/plans/2026-10-25-plan-1-lean-command-corpus
✓ [plan_tickets] /opt/fabrik/.claude/worktrees/kaizen/docs/development/plans/2026-10-25-plan-1-lean-command-corpus: graded 57 ticket(s), 483 Touches path(s), 110 Context-Files entry(ies); READ budget measured against /opt/fabrik/.claude/worktrees/kaizen; 0 finding(s)
```

**The corpus-reading test suite at the base commit** (`run_corpus_suite.py`: every `tests/**/test_*.py` naming `_sources`, `_fragments`, `_agents` or `assemble_commands`, under `capped_run.sh`):

```
1 failed, 5941 passed, 2 skipped, 1 warning in 1693.34s (0:28:13)
```

Over 142 test files at base 4c0827c22. The one failure, `tests/test_prune_transcripts.py::test_c3_a_live_parent_keeps_every_sidechain_and_an_in_flight_one_stays`, is outside the corpus surface. The 28 minutes are why no ticket gate runs the whole set.

Grounded anchors, each read in this run:
- `docs/superpowers/specs/2026-10-25-lean-command-corpus-design.md:125` (target), `:177` (completeness), `:232` (retiring pins), `:239` (the tail), `:291` (T1), `:362` (L1 text), `:495` (KILL).
- `commands/assemble_commands.py:34` (`_CLOSE_FEEDBACK`) and `:1326` (`def check()`, whose exit is at `:1395`).
- `commands/_sources/fabrik-task.md:216-219` (the nested review and the full review after phase 5 step 5).
- `commands/_agents/fabrik-reviewer.md:6` (`omitClaudeMd: true`).
- `commands/_sources/fabrik-command-improve.md:288-300` (today's size paragraph).
- `docs/development/reviews/2026-10-25-w-0a91bf86-lean-program-phase-wall-clock.md:96-106` (the untracked measuring scripts).
- `scripts/api_credit.py:657-673` (the `run`/`status`/`settle` verbs).
- `scripts/command_run.py:2608` (`_USAGE_FIELDS`) and `:2896` (`_parse_usage_feedback`).

Each ticket cites its primary path in its Touches and its spec rules verbatim at `docs/superpowers/specs/2026-10-25-lean-command-corpus-design.md:<line>`.

## Pass Ledger

`/fabrik-plan-review`, receipt `docs/development/reviews/2026-10-25-plan-1-lean-command-corpus-plan-review.md`. Slices: A (spine, T01a-T02, opus), B (T03a-T20, sonnet), C (T21-T46, sonnet); shape `agent-tool` (D-961). Hash: the combined set md5, run from inside the set dir; a row's end hash is taken before the row is written.

| Pass | seats · axes re-checked (claims · gates · interfaces · completeness) | counters | method | plan md5 (start → end) |
|-----:|---|---|---|---|
| Pass 1 | opus×1 + sonnet×2 (slices A, B, C) · all axes | found: 49, new: 49, confirmed: 48, fixed: 48, unexecuted: 0, edits: 23 | method: citation — full pass over all 58 files (A 205 claims, B ~700, C ~150); orchestrator executed the reader-test class sweep (366 unnamed, 71 named-but-ungated over 626 test files), the lock-overlap probe (2 active locks, 10 paths), `-rP` on a printing test, `assemble_commands.py` drift and exit lines (:1340-1343, :1395), `_ENTRY` (:183, no `changed-by`), `units()` frontmatter drop (:82-84), the anchors (:34, :1326, :1395); flip gates on a flipped scratch copy: rule grounding 6 examined 0 findings, plan quality 58 examined 0 findings (planted mutant → 1), convergence graded the spine; 1 RECORDED — by design (S2-14b, `fabrik-task.md:216-217` matches the spec's own cite) | 4516608359d074abaf6f0dcf7c0f580a → 13e4df8a85eb5afa96c94e86a6fef3e0 |
| Pass 2 | opus×1 + sonnet×2 (round-1 owners of A, B, C) · delta over the round-1 hunks + one hop | found: 18, new: 18, confirmed: 10, fixed: 10, unexecuted: 0, edits: 12 | method: re-derivation — each seat re-executed its slice's load-bearing claims over pins-2b (A: BC multiset 277 = 277, File Scope 263 = 263, 153 spec quotes, anchors :34/:1326/:1395, the frontmatter carrier on a scratch ledger red/green; B: the step-5 snippet, T07c step 0 (`False`), `decisions.py D-344`, four stem listings; C: 27/27 md5, `-rP`, the doc-gate flags, the folded gate lists); orchestrator ran the stem listing (8 of 15 paths `.pyc`), the corpus-glob census (30 tests glob the corpus and name no stem, `test_review_queue_pass.py` among them), `work.py show` (invalid verb), the item files on `origin/master`; confirmed: the `.pyc` leak (S1-201/S2-201/S3-201), corpus-glob tests unlisted (S3-202, closing S2-202/S2-205), `work.py show` (S1-202/S2-204), rewrite step 2 vs step 5 (S1-204/S2-203), T46 start commit (S3-204) and its master-only gate (S3-205), the `MISSING` token (S2-206/S3-206), T01d's self-justifying floor (S1-203), the Self-audit holds line (S1-205), S1-11 left in the part-a tickets; own-fix: round 1 for all 10; 1 REFUTED (S3-203: `command grep` runs the real binary, CLAUDE.md § HARD STOPS); out-of-hop fixed with destination this plan: the part-a cross-file carve-out (S2-5) and the Coverage row's cite; the corpus-glob listing rewritten from an `xargs` pipe the worktree guard refuses to a Python one-liner; `own_text` described by what it returns (infra-2's text-measure branch keeps include lines as markers) | dfd21005f4e30c84a9cca0faec8578c0 → 0dcbc27ea96e17a9645f461c1e17b73e |
| Pass 3 | opus×1 + sonnet×2 (round-1 owners of A, B, C) · delta over the round-2 hunks + one hop | found: 3, new: 3, confirmed: 3, fixed: 3, unexecuted: 0, edits: 4 | method: re-derivation — B quiet (the stem and corpus-glob listings run verbatim, the T03c and T10 unions hold `test_assemble_dispatch_step.py` and `test_agent_definitions.py`, steps 2/3/5 consistent); C quiet (27/27 md5, both listings run, T46 gate 2 matches); A re-derived BC 277 = 277, File Scope 263 = 263, 153 spec quotes, the origin/master probe (`open`, twice); orchestrator ran T46 step 1's start-commit shape on `commands/command_rules.py` (first add 0329c943c, its parent lacks the file and holds the source); confirmed: the corpus-glob listing over-matched identifiers and pulled in `test_prune_transcripts.py`, red at base (S1-301), the T01d no-floor rule never reached T01d step 6, its BC row or T02 (S1-302), the probe's `dropped` case (S1-303); own-fix: round 2 for all 3. SCOPE GROWTH: rounds 2 and 3 both at own-fix ≥ 2/3 (10/10, 3/3), so the hunt stopped; this fixed set alone is re-verified next. Class rewrite — the reader-test bullet (rounds 2, 3): rewritten whole, path-anchored corpus-glob listing (32 tests, `test_prune_transcripts.py` out) and reds measured against the start commit; both listings executed verbatim from the plan text (11 and 32 files, 0 `.pyc`) | 0dcbc27ea96e17a9645f461c1e17b73e → e8135556e3522862a0cbb914ec72b1a1 |
| Pass 4 | opus×1 (round-1 owner of A; B and C restated at their last verified counts, no open claim) · the scope-growth stop's fixed set: S1-301, S1-302, S1-303 | found: 1, new: 1, **confirmed: 0**, fixed: 0, unexecuted: 0, edits: 0 | method: re-derivation — both reader-test listings run verbatim from the plan (fabrik-researcher 7 files, corpus-glob 32, `test_prune_transcripts.py` absent); the S1-1..S1-4 tests found in their unions; the cost row's 52 and 32 re-counted; T01d step 6, its BC row (byte-identical to the spine copy) and T02 step 9 read; BC multiset 277 = 277; S1-301..S1-303 CLOSED; standing clean since their last full pass: claims, touches, interfaces, definedness, behavior-contract, deferred-questions; 1 RECORDED — measured (S1-401, post-stop residue: T01d's and T02's gate lines say a red test is a Touches miss while the spine rule they cite reports a start-red test; the gate defers to that rule; destination: T01d's own `/fabrik-review`, the gate's first run) | a6fed8e4bba05ee0a24f949902703ae3 → a6fed8e4bba05ee0a24f949902703ae3 ✓ → **CONVERGED** (D-1227) |

## Self-audit

Grounding passes run:
- **The census** (above): sources, fragment fan-in, seat definitions and hours.
- **Three grounding seats.**
  - An Opus `fabrik-researcher` checked the spec's repo anchors. It found three drifts:
    - the `check()` exit was at `assemble_commands.py:1383`, not `:1382`, on slice A's branch (`:1395` on master since slice A merged);
    - `tests/test_assemble_agents_dest.py` calls `ac.render(Path(td))`, not the `render(tmp_path, None, …)` the spec quotes;
    - intel's measuring scripts are untracked.
  - A Sonnet seat censused the pin tests on the pilot files.
  - A Sonnet seat located the measure script, the API-credit lane and the close-feedback parser.
- **An AST literal scan** of every candidate test for ≥25-character literals found verbatim in the file being cut. It replaced a name-only match that had listed 22 over-budget tickets, most of them false hits.

None of the three drifts changes a ticket: the tooling is infra-2's, and the untracked script is the time measure's delivery (§ Interfaces).

(a) **Coverage of What we already agreed:**
- The goal and the measure: every unit's Behavior Contract rows 1-2, and T46.
- The order: § Merge Order.
- The levers: each rewrite's step 4 and the T07c and T08 rows.
- L1 and L2: the text-measure and L2 merges (§ Interfaces), and T10.
- The holds: § Global Constraints (the hold lifts at the L2 merge).
- Ruling (a): § Execution Discipline.
- The coordinator's brief: § Execution Discipline and T01a-T01d.
- infra-2's split: § Interfaces.

Gaps: none.

(b) **Cross-ticket signature consistency.** Every ticket calls the same four slice-A functions by the same symbols (`command_rules.py::vanished`, `::own_text`, `::write_baseline`, `::losses`), writes the same ledger shape, and names `generate_unchanged` exactly as the text-measure merge's interface does. The ledger and baseline file names follow the tooling's test fixture (`commands/_rules/<cmd>.baseline.txt`).

Fixed point: reached by `/fabrik-plan-review` in four passes (§ Pass Ledger; D-1227).

## Residual unknowns

Resolved:
- **Where the tooling lives:** infra-2's three merge requests, not a ticket (D-1222).
- **Where the pins go:** pin migration plus kept behavioural tests (D-1222).
- **How single-command fragments are ledgered:** the `shared:` form (D-1222).
- **The READ budget:** every ticket is under 262144 bytes (§ Evidence).

Still open, each with its resolution step:
- **R1 — when the text-measure, time-measure and L2 merges land.** Resolution: the executor runs § Global Constraints' precondition probes before T01a and before T10, and waits rather than starting. Waiting is not a mid-run question, because the plan names it. Slice A is on master (bc2a9c30b), so the emit gate grades the set clean (§ Evidence).
- **R2 — the name of the text-measure merge's ceiling ratchet.** Resolution: that merge documents it in `docs/reference/command-corpus-check.md` § Rule ledger, and each ticket's step 7 reads it there. No ticket starts before it merges (R1).
- **R3 — the step-2 scan misses a pin under 25 characters, a regex or structure assert, and a phrase its test normalises differently.** Resolution: § Global Constraints' reader-test run turns each such miss red inside the ticket, and the Touches-miss rule amends it before merge.
- **R4 — intel's measuring script.** Resolution: intel commits it as `scripts/command_time_measure.py` (W-487e966a), and infra-2 pins it by commit. Until it lands, no time baseline is cut and no unit starts (R1).
- **R5 — intel's D-344 measure for T1.** Resolution: at its start T07c runs `python3 scripts/decisions.py D-344`. It proposes T1 only if a row after D-1219 records the D-344 pair's measured recall in `/fabrik-review`, and otherwise records T1 as not proposed.
- **R6 — infra-2's lane clause W-a0a32de2.** Resolution: at its start T08 runs the same probe on `W-a0a32de2` (`git show origin/master:.fabrik/work/W-a0a32de2.json`, its `status`). If it is `done`, T08 carries the clause; otherwise the clause lands later under its own D-row.
- **R7 — whether the API-credit lane is live.** Resolution: native `fabrik-reviewer` seats until W-230abfd5 is done.
- **R8 — the spec's U1, U2 and U3** are carried as the spec states them: U1 at T02 (T01d's own figure before it, § Interfaces), U2 with the text-measure merge, U3 at each unit's close.
- **R9 — two active plan locks overlap this plan's scope**, and `/fabrik-execute-plan` stops on any overlap. `2026-10-21-plan-3-own-scrape-slice-1a` (intel) lists `commands/_agents/fabrik-researcher.md` and the `fabrik-spec`, `fabrik-plan-after-chat`, `fabrik-spec-review` and `fabrik-vision` sources. `2026-10-22-plan-1-least-operator-approval` (kaizen, parked) listed `deploy-chain.md`, `design-gate-panel.md` and the `fabrik-release`, `fabrik-deploy` and `fabrik-deploy-plan-review` sources. Neither branch has unmerged edits to those ten files. Resolution, from each lock's owner (`docs/reference/plan-lock-lifecycle.md` § Remediation): kaizen narrowed its lock in 108f46748 on this branch; intel narrows its lock in its W-487e966a branch. T01a waits on § Global Constraints' lock probe.
