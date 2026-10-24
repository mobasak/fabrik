# Spec review — lean command corpus design

**Command:** /fabrik-spec-review
**Surface:** `docs/superpowers/specs/2026-10-25-lean-command-corpus-design.md`
**Work item:** W-96f36043 (P0) · nested in `/fabrik-spec` · design approval: the Opus + Fable panel, D-1217
**Shape:** agent-tool (hub, D-961: no `Workflow`)

## Slices (round 1, disjoint)

| Slice | Seat | Scope |
|---|---|---|
| A-rules | opus×1 (`fabrik-reviewer`) | § Target, § The measure, § The rule test, § How a command is cut, § Loop changes, § Order, § Binding |
| B-rest | sonnet×1 (`fabrik-reviewer`) | § Personas, § Problem, § Intake Inventory, § Constraints Digest, § Panel, § fabrik-lib verdict, § Lifecycle, § Review and landing, § Rejected alternatives, § Residual unknowns |
| C-facts | sonnet×1 (`fabrik-researcher`) | the three cited external pages |

## Pass Ledger

| Pass | seats · axes re-checked (intake · personas · facts · vendor · approach · completeness · constraints) | counters | method | spec md5 (start → end) |
|-----:|---|---|---|---|
| Pass 1 | opus×1 + sonnet×1 + sonnet×1 researcher · all axes | found: 30, new: 30, confirmed: 25, fixed: 25, unexecuted: 0, edits: 25 | method: citation — full pass; orchestrator executed: `check_spec_convergence.py` on a flipped scratch copy (1 examined, 0 findings after the residual section), `curl` status 200 on both docs pages, a raw-page search of the prompting page (history: 5 hits, none advising a rule's history), `grep -nE "TemporaryDirectory\|sys.exit\("` on `commands/assemble_commands.py` (:1323, :1382, :1265, :1438), the `{{include:` count over 39 sources (24 fragments shared), the change-axis and distinct-id re-counts (2,449/220; 42 ids, 12 dates); 1 REFUTED (B-C11, "~46 repos" is `CLAUDE.md`'s own figure), 1 RECORDED — measured (B-C6, `llm-dispatch` sizes a call's input, not a rendered file), 3 minor A-findings fixed with the 12 | dd172afbe67c63fb8c244403bf06f38a → 7f9b1e312c3444950fdb075a5df8ad0b |

## Round 1 dispositions

| id | finding | disposition |
|---|---|---|
| C-1 | the prompting page is now titled "Prompting best practices" | CONFIRMED (raw fetch) — fixed |
| B-C1 | change-axis counts were over all states, not `done` | CONFIRMED (re-count 2,449/220) — fixed |
| B-C2 | 129/23 are mentions, not distinct ids/dates | CONFIRMED (42, 12) — fixed |
| B-C3 | D-1216's "all other builder work pauses" has no row | CONFIRMED (pin grep 0 hits) — fixed: I14 + § Program holds |
| B-C4 | D-1216's command-improve pause has no row, holder or lift | CONFIRMED — fixed: I15 + § Program holds |
| B-C5 | the "not doing its work" complaint has no row | CONFIRMED — fixed: I16 |
| B-C6 | `llm-dispatch` prompt sizing unmentioned | RECORDED — measured (per-call input size, not a rendered-file measure; no reuse) |
| B-C7 | ceiling-raise trigger names no usable source | CONFIRMED (the file holds only the current value) — fixed: git log source |
| B-C8 | `remove: none` ratio has no denominator or holder | CONFIRMED — fixed |
| B-C9 | 300-entry trigger unmeasured | CONFIRMED — fixed: the test prints counts |
| B-C10 | no holder files trigger items | CONFIRMED — fixed: kaizen, daily digest read |
| B-C11 | "~46 repos" unverifiable | REFUTED (`CLAUDE.md` line 7 states ~46 repos) |
| A-C1 | the test cannot read `--check`'s temp dir | CONFIRMED (`assemble_commands.py:1323`, `:1382`) — fixed: the test renders itself |
| A-C2 | the pilot does not share `/fabrik-review`'s fragments | CONFIRMED (include grep) — fixed |
| A-C3 | the step-3 fragment list is wrong | CONFIRMED (24 shared + `close-feedback`; `review-probe-catalogue` is not rendered) — fixed |
| A-C4 | L1's ledger-less refusal contradicts the program's own additions | CONFIRMED — fixed: three exemptions |
| A-C5 | own text excluded new kaizen docs | CONFIRMED — fixed: own text widened |
| A-C6 | rules moved into seat definitions had no ledger | CONFIRMED — fixed: the `file:` field |
| A-C7 | pins on non-render files were deleted with no carrier | CONFIRMED (`tests/test_review_scoped_queue_pass.py` reads `_agents`, the catalogue and the workflow js) — fixed |
| A-C8 | the light form excluded steps it depends on | CONFIRMED — fixed: steps 2-8 apply, ledger holds only changed rules |
| A-C9 | `reads` growth both needed a D-row and was not blocked | CONFIRMED — fixed: a D-row only for an added path |
| A-C10 | agent definitions belonged to both ceilings | CONFIRMED — fixed: own text / `render` |
| A-C11 | a ceiling breach had no exit code distinct from drift | CONFIRMED (codes 1, 2, 3 in use) — fixed: LOSS 4, ceiling 5 |
| A-C12 | the floor's median is undefined before any command reaches 50% | CONFIRMED — fixed: U1 |
| A-m1 | TRIPWIRE "AND" ambiguous | CONFIRMED — fixed: EITHER |
| A-m2 | "about 30 commands" vs 39 rendered | CONFIRMED — fixed |
| A-m3 | "closed one level deep" undefined | CONFIRMED — fixed |
