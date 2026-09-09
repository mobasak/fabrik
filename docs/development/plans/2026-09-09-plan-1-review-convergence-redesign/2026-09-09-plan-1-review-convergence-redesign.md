# Review convergence redesign — partitioned single pass, delta rounds, zero-CONFIRMED quiet round

Status: DRAFT
**Owner:** —
Spec: docs/superpowers/specs/2026-09-08-review-convergence-redesign-design.md (CONVERGED 509c1b10, approved by the operator's `/fabrik-plan-after-chat` invocation 2026-09-09 — D-205; rulings D-203; supersede rows D-206, D-207, D-208)

## Goal

Ship the spec's ten deltas so a `/fabrik-review`, `/fabrik-repo-review` or `/fabrik-review-scoped` closes on a round whose partitioned pass CONFIRMED zero code or doc defects by execution: the receipt grammar and both gates learn `confirmed:`/`unexecuted:` with the old rows still parsing, the run record learns `--confirmed`, the seat budget is sized by slices, the grep-shaped classes move into a hygiene script, the command corpus and rule pack carry the partition and delta-round rules, and the BLOCKED D-191 receipt is the first application (one delta round, then the flip at round 19).

## What we already agreed (from the spec + this conversation)

- The operator's five rules (D-203, R1–R5) and the six agreed restatements (R6–R11) — every one has a D-section in the spec; this plan maps each to a ticket (§ Self-audit (a)).
- Quiet = zero CONFIRMED (executed) code/doc defects; RECORDED and REFUTED never count; `confirmed: 0` implies `fixed: 0` (D1, DD12) → T01, T02, T03, T09.
- One partitioned pass by FILE, one model per slice; Haiku at most one judgement-shaped inventory seat; the scriptable classes are a script from round 1 (D2, D4) → T04, T07, T08.
- Round 1 is the only full pass; every later round is a delta over the fix diff plus one hop of callers/callees; the closing delta round carries a fresh non-authoring seat (D5, DD10) → T07, T09.
- The seat budget is sized by `--slices`; `--units` stays for grounding/adjudication surfaces where the D-186/D-188 floor still applies (D3, DD2, DD5) → T04.
- Backward compatibility for in-flight receipts in the ~46 synced projects: a ledger without `confirmed:` keeps the `found: 0` rule; 535 of 535 corpus Pass rows parse unchanged; the token rule's fire rate over the 275 hub receipts is ONE row, repaired in-commit (D7, DD4) → T01, T02.
- The hygiene script starts advisory and graduates on a measured false-positive rate below 5 % over 20 receipts (DD6) → T08 + a backlog row.
- The D-191 receipt flips at round 19 after one honest delta round, adjudicated on Opus by name (D9, V12) → T09.
- Pool OFF (D-181/D-182); D-190 pricing; no new dependency; every behaviour change ships a red-first grader (I19).
- Rejected and never re-proposed: a round cap, majority vote across seats or passes, restoring the overlapping seats, a severity-weighted exit, a new review-orchestrator service (spec § Rejected alternatives).
- This plan's own reviews run under the corpus as it is TODAY — the spec's rules bind the hub only once T01–T03 merge; the Execution Discipline says how each ticket's receipt closes (§ Execution Discipline).

## Intake Inventory

The conversation between the spec's CONVERGED close and this invocation (2026-09-09, this session) stated the items below; the spec's own I1–I20 are inherited by ticket (§ Self-audit (a)) and not repeated.

| I# | Item (anchored) | Disposition | Where |
|---|---|---|---|
| I1 | `/fabrik-plan-after-chat docs/superpowers/specs/2026-09-08-review-convergence-redesign-design.md` — the invocation on a CONVERGED spec, taken as approval of the spec AS IS | IN | D-205 minted in this change; the whole set |
| I2 | "have you implemented new way of review commands?" | IN — the answer was NO; this plan IS the implementation | T01–T09 |
| I3 | "our spec review also took too much time … why is it taking too much time? how can we decrease this duration meaningfully?" | OUT-OF-SCOPE — the diagnosis was delivered in chat (451 min, 44 rounds, one paragraph re-reviewed by three seats per pass); the fixes that belong to `/fabrik-spec-review` and `/fabrik-plan-review` are NOT in the approved spec's landing sites | `docs/STRATEGIC_BACKLOG.md` § Later, the `[infra]` row "Review-family adoption of D-203's rules" written in this change |
| I4 | "beyond your above reply, is there anything can be done to spec review as like we will do for code review?" — five review-family rules (D1 bar for spec/plan review; delta rounds by SECTION via the cross-reference tokens; the grep-shaped spec axes as a script; executed evidence pinned once; correct-never-extend edits) | OUT-OF-SCOPE — the operator invoked the plan on the spec as is without widening it; the rules are recorded, not built | the same backlog row |
| I5 | The spec's Machinery report RECORDED residues: the first `QUIET_PASS` alternative requires a bare `found: 0` while the second tolerates `0+` (fail-closed, 0 corpus exemplars); colon homoglyphs outside the normaliser (forgery exclusion) | OUT-OF-SCOPE — V13 freezes the spec's regex verbatim; both are fail-closed with 0 exemplars | § Residual unknowns (named, with the one-character fix a later spec may adopt) |
| I6 | The spec's RECORDED residue: `RECORDED — hygiene false positive` is written with a `: <why>` suffix at D4 and bare at D7/DD13 — "the plan pins one shape" | IN — pinned to the parenthesised form `RECORDED — hygiene false positive (<why>)`, the same shape as the other three verdicts (D6's colon rule) | T02 (the `VERDICT` widening), T08 |
| I7 | The grounding seats' finding this run: `_ledger_shapes`'s tuple has FOUR positional unpacks (`:581`, `:1263`, `:1284`, `:1562`) and TWO construction sites (`:1121`, `:1134`) where the spec enumerated two unpacks and one construction | IN — every site named in T01's Scope | T01 |
| I8 | The grounding seats' finding: `scripts/command_run.py` (137 KB) plus `tests/test_command_run.py` (145 KB) exceed the per-ticket READ budget together, and the one test that breaks (`:3073-3087`) lives in that file | IN — the pair is owned by the Integration ticket by the READ-budget hatch (`check_plan_tickets.py`'s `if t.integration: continue`) | T09 |

Intake: 8 items — 5 IN, 3 OUT-OF-SCOPE (I3, I4 → the backlog row; I5 → § Residual unknowns), 0 ASK.

## Ticket Board

| Ticket | Title | Depends | Parallel | State | Commit |
|---|---|---|---|---|---|
| T01 | Coverage gate: both grammars learn `confirmed:`/`unexecuted:`, the 5-tuple and its readers, the exit rule, the line normalisation | — | ⚡ | ⬜ | |
| T02 | Coverage gate: the token, counter and header rules, the RECORDED verdicts, the residual and finders-cell checks, the receipt template | T01 | ⛓️ | ⬜ | |
| T03 | `check_convergence.py` QUIET_PASS follows the new grammar | — | ⚡ | ⬜ | |
| T04 | `dispatch_headroom.py --slices`: the floor stands down under a partition; the docstrings, printed sentences and the CLI reference doc | — | ⚡ | ⬜ | |
| T05 | The board banner sentence and its doc | — | ⚡ | ⬜ | |
| T06 | core/62, both CLAUDE.md files, the convergence prompts and the prompt template carry the partition rule and the new exit | — | ⚡ | ⬜ | |
| T07 | The three review commands, the rules-review D-048 cite, the subagents fragment; the V7/V8 corpus tests | T04, T05, T06 | ⛓️ | ⬜ | |
| T08 | `check_review_hygiene.py`: the grep-shaped classes as an advisory script | T02 | ⛓️ | ⬜ | |
| T09 | Integration: `command_run.py --confirmed` (the READ-budget hatch), the protocol and event docs, the first application on the D-191 receipt, the whole-plan gate | T01, T02, T03, T04, T05, T06, T07, T08 | ⛓️ | ⬜ | |

## Merge Order

1. T01
2. T03
3. T04
4. T05
5. T06
6. T02
7. T07
8. T08
9. T09

Serialized: scripts/enforcement/check_review_coverage.py — T01, T02

## Interfaces

- **T01 → T02 (one extraction contract):** `_ledger_shapes(text) -> tuple[tables, prose_runs, ordered]` where every row is `(found: int, confirmed: int | None, fixed: int, unexecuted: int | None, line: str)`; `_pass_counters(line) -> tuple[int, int | None, int, int | None] | None`; `_MEGA_ROW` groups 1 `found`, 2 `confirmed` (optional), 3 `fixed`, 4 `unexecuted` (optional). T02 adds `_refuse_row(line, path_kind, reason) -> str` (the named refusal) on top of T01's parse and never re-parses. Seam test: `tests/enforcement/test_review_refusals.py::test_the_refusal_rules_read_t01s_tuple` (T02's Touches) parses the V1 row through `_ledger_shapes` and asserts the 5-tuple before any refusal runs.
- **T01 → T03 (same rows, two gates):** the V1 round-19 row and D9's round-18 row are the shared fixtures — T03's `QUIET_PASS` test and T01's exit test carry them verbatim (V13 ↔ V1). No import; `check_convergence.py` imports `RUBRIC_RUN, UNCHECKED, VERDICT, _blocked_ok, _checklist_section, _table_rows` from the coverage gate (`check_convergence.py:429-446`) and never `_ledger_shapes`, so T01's tuple change cannot reach it.
- **T02 → T08:** `VERDICT` accepts `RECORDED — (unexecuted|by design|measured|hygiene false positive) (…)`; T08's dual-verdict class counts `VERDICT` matches per disposition cell and imports `_table_rows` from `check_review_coverage` (same package, `scripts/enforcement/`). Seam test: `tests/enforcement/test_check_review_hygiene.py::test_the_dual_verdict_class_uses_the_gates_own_vocabulary`.
- **T04 → T05:** `dispatch_headroom.py --json` keeps every key `_budget_probe` reads (`caps`, `quota`, `box_caps`, `siblings`, `box_caps_floored` — `quota_dashboard.py:1850-1919`) and adds `slices` and `mix_by_slice`; T05 changes only the banner sentence. Seam test: T05's positive-control assertion on the rendered banner.
- **T04, T05, T06 → T07:** T07's V7 test asserts the two D-191 literals are absent from `scripts/**/*.py`, `docs/workstation/`, core/62 and both CLAUDE.md files — the sentences T04/T05/T06 rewrite — and that `dispatch_headroom.py`'s printed sentences carry "units-sized grounding surface". Consumer: `tests/test_assemble_dispatch_step.py` (T07's Touches).
- **T01, T02 → T09:** the hub's gate accepts `confirmed:` before the first application writes round 19 (Merge Order); T09's `round --confirmed` is what the delta round records. T08 → T09: the hygiene script runs at the delta round's start and close.

## Behavior Contract

- **Given** a receipt whose last Pass Ledger row is `| Pass 19 | opus×1 | found: 4, new: 2, confirmed: 0, fixed: 0, unexecuted: 0 | delta |`, **When** `check_review_coverage.py` grades it, **Then** the exit rule passes (quiet by `confirmed: 0` although `found:` is 4) and the same receipt with `confirmed: 1, fixed: 1` fails naming `confirmed` (scripts/enforcement/check_review_coverage.py:581-584)
- **Given** a receipt whose last row is old-grammar `found: 3, fixed: 0` with no `confirmed:` token anywhere, **When** the gate runs, **Then** it fails on `found: 3` (the old rule stands) and the same receipt ending `found: 0, fixed: 0` passes (scripts/enforcement/check_review_coverage.py:582)
- **Given** the cell-anchored row `| 19 | found: 0 | confirmed: 0 | fixed: 0 | unexecuted: 0 |` and the same row without its closing pipe, **When** `_ledger_shapes` parses them, **Then** both resolve MEGA-first to `(0, 0, 0, 0, line)` and the widened `_MEGA_ROW` matches exactly the 2 rows today's regex matches over the 275 committed receipts (scripts/enforcement/check_review_coverage.py:996, :1117-1121)
- **Given** the prose line `Pass 19: found: 0, confirmed: 3, fixed: 0`, **When** `_pass_counters` reads it, **Then** it returns `(0, 3, 0, None)`, and the mis-ordered `Pass 19: found: 0, fixed: 0, confirmed: 0` is refused by name, never `None` (scripts/enforcement/check_review_coverage.py:1054-1061)
- **Given** the 275 committed receipts at 2dec30c8, **When** every `|`-leading line and prose Pass line is parsed by the widened grammars, **Then** 535 of 535 Pass rows parse with `confirmed=None` and every receipt's quiet/non-quiet verdict is unchanged — 0 flips (scripts/enforcement/check_review_coverage.py:1064)
- **Given** a receipt carrying `confirmed<U+200B>: 3` (a literal zero-width space after the word) and one carrying a `U+2028` inside a Pass row, **When** `_strip_fences` runs, **Then** the zero-width character is deleted and the `U+2028` becomes a space BEFORE `_kept_lines` splits the text, reusing `_LINE_BREAKS`, and the header window at `:366` sees the normalised text (scripts/enforcement/check_review_coverage.py:299, :754, :766)
- **Given** a mega-validation receipt whose last row carries `confirmed: 0`, **When** `check_mega_validation` reads it, **Then** the last row unpacks as the 5-tuple, the hash-chain pairs still read the raw line, the mega exit reads `confirmed` when present and the pair otherwise, and the 3 existing tuple-reading mega tests stay green unchanged (scripts/enforcement/check_review_coverage.py:1263, :1275, :1284)
- **Given** the widened tuple, **When** `tests/enforcement/test_review_exit_contract.py` and `tests/enforcement/test_mega_validation_reports.py` run unchanged, **Then** all pass, and the exit error text no longer says "a FRESH candidate counts even when refuted" but names D-203 (scripts/enforcement/check_review_coverage.py:584)
- **Given** the row `| 19 | found: 0 | fixed: 0 | confirmed: 3 |` under a real vocabulary header with one prior parsing data row, **When** the gate runs, **Then** the row is REFUSED by name with the cell-anchored repair message, and every REFUSED fixture in the spec's V2 list is refused (scripts/enforcement/check_review_coverage.py:996)
- **Given** `| Pass 19 | opus×1 | found: 0, fixed: 0 | delta (confirmed: 3) |`, **When** parsed, **Then** it is refused (a token outside the counter cell) while `| Pass 19 | opus×1 | **found: 0, confirmed: 0** | **fixed: 0** |` parses and reads quiet (scripts/enforcement/check_review_coverage.py:1054)
- **Given** `| u | x | found: 0 | fixed: 0 | unexecuted: 2 |` or `| Pass 19 | opus×1 | found: 0, fixed: 0, unexecuted: 2 | m |`, **When** the gate runs, **Then** each is refused by the counter rule (`unexecuted:` without `confirmed:`), never read as old-grammar quiet (scripts/enforcement/check_review_coverage.py:1117-1121)
- **Given** a method cell `HIGH/CONFIRMED: two MORE anti-cheat errors` on a resolved old-grammar row, **When** the case-insensitive token scan runs, **Then** it is exempt under the five-conjunct carve-out (the 28 corpus cells, 30 occurrences, 0 lost) and `| 19 | found: 0 | fixed: 0 | Confirmed: 3 defects stand |` is refused; the rule's fire rate over the 275 receipts is exactly 1 row, `docs/development/reviews/2026-08-31-plan-1-manifesto-command-pass-T20-fabrik-release-review.md:15`, repaired by the orchestrator's Delta at this ticket's merge (scripts/enforcement/check_review_coverage.py:1019-1020)
- **Given** a header row `| Pass | Finders | found: F, confirmed: C, fixed: X | Method |` with its separator and one parsing data row, **When** the block parses, **Then** the header is exempt from the token rule and not counted when testing whether the block parses; a second header-shaped row inside the same block is a refused data row; the `--init` header with no data row is not yet a ledger (scripts/enforcement/check_review_coverage.py:176-213)
- **Given** a closing Pass row carrying `unexecuted: 1`, **When** the gate runs, **Then** the receipt is not quiet; a residual row `RECORDED — by design (F342, round 15; F358, round 17)` under a closing `Pass 18` passes, `(F999, round 18)` is refused by name, `(D-203)` passes, and `RECORDED — measured (<why>)` never enters `confirmed:` or `unexecuted:` (scripts/enforcement/check_review_coverage.py:520-539)
- **Given** a closing Pass row whose finders cell names no model token (`opus×N`, `sonnet×N`, `haiku×N`), **When** the gate runs, **Then** it is refused; a cell reading `native sonnet×2` passes (scripts/enforcement/check_review_coverage.py:1064)
- **Given** `review_receipt.py --init`, **When** it writes a skeleton, **Then** its Pass Ledger prose and fenced examples carry the five-counter row shape and the four RECORDED verdicts, the skeleton carries a `## Residual` section, `VERDICT` accepts `RECORDED — unexecuted (…)`, `RECORDED — by design (…)`, `RECORDED — measured (…)` and `RECORDED — hygiene false positive (…)`, and the mechanically-completed skeleton test passes with a new-grammar closing row (scripts/review_receipt.py:161-172, scripts/enforcement/check_review_coverage.py:51)
- **Given** D9's round-18 row, V1's round-19 row, `| u | x | found: 0 | fixed: 0 | unexecuted: 2 |` and `| 19 | found: 0 | confirmed: 00 | fixed: 0 |`, **When** `QUIET_PASS` is searched, **Then** the results are no match, match, no match, match (scripts/enforcement/check_convergence.py:203)
- **Given** the 275 committed receipts, **When** the old and the new `QUIET_PASS` run whole-text over each, **Then** the quiet set is identical — 166 of 275 under both, 0 flips — asserted by the test over `git ls-files docs/development/reviews/*.md` (scripts/enforcement/check_convergence.py:771-775)
- **Given** `--slices opus=1,sonnet=5,haiku=1` on an idle box, **When** `dispatch_headroom.py` runs, **Then** it prints `SEATS: 7` and the mix `{opus 1, sonnet 5, haiku 1}`; under a cap of 5 it trims Haiku first, then the extra Opus seats, then Sonnet, never below one Opus (scripts/sysadmin/dispatch_headroom.py:373-388)
- **Given** `--slices opus=1,sonnet=1`, **When** it runs, **Then** it prints `SEATS: 2` with no "raised to the floor" reason, no below-the-floor advisory, `floor_granted` 0 and `box_caps_floored` false for both halves (scripts/sysadmin/dispatch_headroom.py:550-557, :565, :448-449, :694)
- **Given** `--slices opus=1,sonnet=2` without `--units`, **When** it runs, **Then** it runs (units defaults to the slice count 3); `--units 0 --slices opus=1` prints `SEATS: 1`, never `SEATS: 0` through the nothing-to-partition branch (scripts/sysadmin/dispatch_headroom.py:543-548, :648)
- **Given** every positional `budget(units, heavy, b, q, s, risky, mechanical)` call today (3 script sites, `tests/test_quota_dashboard.py:3275`, 50 sites in `tests/sysadmin/test_dispatch_headroom.py`), **When** `slices` is not given, **Then** the result is byte-identical to today and the 31 existing tests pass unchanged (scripts/sysadmin/dispatch_headroom.py:404-412)
- **Given** the module docstring, `full_mix()`'s, `_mix_story()`'s and the printed sentences at `:602`/`:606`, **When** grepped case-insensitively over line-joined text, **Then** "one Sonnet breadth seat AND one Haiku mechanical seat" and "one Sonnet + one Haiku" are absent and "units-sized grounding surface" is present in the printed sentences (scripts/sysadmin/dispatch_headroom.py:15, :353, :579, :602, :606)
- **Given** `docs/workstation/claude-account-rotation.md` § 223-239, **When** read line-joined, **Then** it documents `--slices`, the optional `--units` and the floor rule, and the wrapped D-191 sentence at `:227-228` is gone (docs/workstation/claude-account-rotation.md:223-239)
- **Given** `--json`, **When** it prints, **Then** the payload carries `slices` and `mix_by_slice` beside every key it carries today (scripts/sysadmin/dispatch_headroom.py:698-717)
- **Given** the rendered board, **When** `_budget_probe` renders the banner, **Then** the HTML carries "Box budget (D-189" (the positive control) and not "one Sonnet + one Haiku", and the sentence names the partition (scripts/sysadmin/quota_dashboard.py:1908-1912)
- **Given** `docs/workstation/quota-dashboard.md` § The box-budget banner, **When** read, **Then** it describes the slice mix the script prints and carries neither D-191 literal (docs/workstation/quota-dashboard.md:99)
- **Given** `.windsurf/rules/core/62-using-subagents.md` after this ticket, **When** read line-joined, **Then** § Dispatch policy carries the partition rule, the delta-round rule and the executed-critic rule, the `:65` floor sentence reads "NEVER solo, never two — the FLOOR is three seats for `/fabrik-review-scoped` and the grounding commands", and neither D-191 literal remains (.windsurf/rules/core/62-using-subagents.md:63-65)
- **Given** `CLAUDE.md` and `templates/governance/CLAUDE.md`, **When** read line-joined, **Then** the fan-out bullet carries the partition rule with neither D-191 literal, the § COMMAND RUN-RECORD paragraph says quiet = zero CONFIRMED with `round --confirmed`, and every anchor phrase in § UNIVERSAL governance markers is byte-identical to today (CLAUDE.md:38-39, :355; templates/governance/CLAUDE.md:30-31, :356)
- **Given** `docs/reference/convergence-prompts.md` § CODE REVIEW CONVERGENCE and `docs/reference/MD/ai-prompt-templates.md:270`, **When** read, **Then** the first carries the delta-round brief and the executed-refutation row shape and the second's "done" row reads the five-counter row with `confirmed: 0` as the exit (docs/reference/convergence-prompts.md:64, docs/reference/MD/ai-prompt-templates.md:270)
- **Given** `commands/_sources/fabrik-review.md` after this ticket, **When** read, **Then** Phase 1 partitions by slice (Opus risky, Sonnet ordinary, at most one Haiku class seat), Phase 2 says the orchestrator executes every candidate and every refutation, Phase 4 says a delta round over the fix diff plus one hop closes on `confirmed: 0`, the completion claim at `:437` reads the new row and drops `new: 0`, and the example rows carry the five counters (commands/_sources/fabrik-review.md:166-172, :260-307, :364, :422-424, :435-437)
- **Given** `fabrik-repo-review.md`, `fabrik-review-scoped.md` and `fabrik-rules-review.md`, **When** read, **Then** waves are slices and the certification pass is the class-ledger close with `--confirmed`, the scoped command's `:47` round line carries `--confirmed` and `:68-70` keeps the 3-reader floor without the D-191 sentence, and the rules-review's `:138` cites D-203 instead of D-048 (commands/_sources/fabrik-repo-review.md:64, :154, :162; commands/_sources/fabrik-review-scoped.md:47, :68-70; commands/_sources/fabrik-rules-review.md:138)
- **Given** `commands/_fragments/subagents-core.md:3`, **When** rendered into the 20 commands that include it, **Then** the partition rule replaces the D-191 sentence, the delta-round sentence and the D8 brief lessons survive a render, and no rendered command carries a D-191 literal (commands/_fragments/subagents-core.md:3)
- **Given** the rendered corpus (36 commands), the sources, the fragment, core/62, both CLAUDE.md files, `scripts/**/*.py` and `docs/workstation/`, **When** the V7 test joins each file's text with `" ".join(text.split())` and searches case-insensitively, **Then** 0 files carry either D-191 literal, the banner positive control holds, and the test was seen red on `templates/governance/CLAUDE.md:356`, `dispatch_headroom.py:602`, the rendered banner and `claude-account-rotation.md:227-228` before the fixes (tests/test_assemble_dispatch_step.py:1)
- **Given** the main checkout after T07's edits, **When** `python3 commands/assemble_commands.py` renders and `--check` runs, **Then** `--check` exits 0 and `check_command_corpus.py` is green (commands/assemble_commands.py:1095)
- **Given** the D-191 receipt at 741eebbf (`git show`), **When** `check_review_hygiene.py --receipt` runs on it, **Then** it reports F280's unescaped `|` inside a table cell and F314's disposition cell carrying two verdict tokens; at 69f01b92 it is silent (docs/development/reviews/2026-09-08-box-bound-seats-d191-review.md:636, :670)
- **Given** a rendered command carrying `{{X}}` residue, a markdown file with an unclosed fence run, a symbol named with `--symbol` that `grep -c` finds 0 times, and a phrase named with `--phrase`, **When** the script runs with `--surface`, **Then** each is reported as its class with `path:line`, and the fence class follows the CommonMark same-char-run rule copied from `check_command_corpus.py:943-960` (scripts/enforcement/check_command_corpus.py:943)
- **Given** any input, **When** the script runs, **Then** it exits 0, prints `[ADVISORY]`-prefixed lines, emits `--json` for the orchestrator, and is registered `warn_only=True` in `final_gate.py` beside the other advisory checks (scripts/final_gate.py:347-374, :1186)
- **Given** a receipt whose ledger row was fixed at a round's start by a hygiene hit, **When** the row is written, **Then** the hit counts as a confirmed doc defect of that round and a hit adjudicated false is `RECORDED — hygiene false positive (<why>)`, never counted — the verdict shape T02's `VERDICT` accepts (scripts/enforcement/check_review_coverage.py:51)
- **Given** `round --confirmed 0 --classes-swept <every class>`, **When** it runs, **Then** it prints the TERMINAL verdict; `round --confirmed 0` with no classes does not; `round --findings 0` on a record whose rounds never stated `confirmed` keeps the old test (scripts/command_run.py:322-327)
- **Given** a round recorded with `--confirmed 3`, **When** the record and the event are read, **Then** both carry `confirmed: 3`, the round line prints `confirmed:` beside `findings:`, and the TERMINAL banner names `confirmed 0` and the delta-round rule instead of "a scoped round never closes the loop"; the test at `tests/test_command_run.py:3073-3087` is rewritten and a grader on the new banner text is added (scripts/command_run.py:316, :329-337, :2006-2022, :2050-2062)
- **Given** a record whose every round states `confirmed`, **When** the oscillation advisory, the `FEEDBACK:` trend and the feedback-ledger row are built, **Then** they read the `confirmed` series; a record with one unstated round reads `findings`; a terminal condition naming `confirmed:` is loop-shaped for the zero-rounds nudge (scripts/command_run.py:342-344, :1455-1466, :1872, :2557)
- **Given** `docs/reference/command-run-protocol.md` and `docs/workstation/kaizen-event-stream.md`, **When** read, **Then** the `round` row carries `--confirmed`, the TERMINAL sentence at `:113` states the confirmed rule, the example record at `:28` and the lines `:110-115`, `:152`, `:316`, `:405` agree, and the round event's field list at `kaizen-event-stream.md:115` carries `confirmed` (docs/reference/command-run-protocol.md:55, :113; docs/workstation/kaizen-event-stream.md:115)
- **Given** the D-191 receipt BLOCKED at round 18, **When** the orchestrator runs one delta round over 69f01b92's fix diff (`tests/test_command_feedback.py`, `tests/test_conftest_isolation.py`, `docs/reference/command-run-protocol.md` plus one hop of callers) with a fresh non-authoring Opus seat and adjudicates on Opus by name, **Then** round 18's row is re-adjudicated to `found: 11, new: 9, confirmed: 3, fixed: 3, unexecuted: 0` with the rewritten method cell, round 19's row is written by the delta round, the `## BLOCKED: spec contradiction` section closes with a one-line pointer to D-203 and the spec, the receipt reads `Status: CONVERGED`, and `check_review_coverage.py` is OK on it (docs/development/reviews/2026-09-08-box-bound-seats-d191-review.md:318, :327)
- **Given** the whole plan merged, **When** the Integration receipt is written, **Then** it embeds the cross-ticket seam run, `check_doc_sync.py --range` and `check_doc_stubs.py --range`, the verbatim `final_gate.py --check --json` success, `check_convergence.py`, `/fabrik-docs-review`, the corpus render from the main checkout, the pre-sync dry run of the token rule over every `/opt/*/docs/development/reviews/*.md` (count and denominator), and the forced sync (docs/development/reviews/2026-09-09-plan-1-review-convergence-redesign-review.md:1)

## Global Constraints

- Shared tree, three hub sessions: every merge is a private-index commit of explicitly named paths (`GIT_INDEX_FILE=<scratch>/private.index; git read-tree HEAD; git add -- <paths>; assert the staged set; git commit-tree; git update-ref refs/heads/master NEW OLD; git reset -q HEAD -- <paths>`); never `git add -A`, `--amend`, stash; fetch + fast-forward before every push; never `--force`.
- Fleet-synced surfaces in scope: `scripts/enforcement/` (recursive, `fabrik_synced_manifest.py:125-126`), `scripts/command_run.py` (RUN_SCRIPT, `:56`), `templates/governance/CLAUDE.md`, `.windsurf/rules/core/62-using-subagents.md`. A commit-tree commit skips the post-commit governance sync: run `python3 scripts/sync_enforcement_to_projects.py --force` after each merge that touches one, and once more at Finish.
- Backward compatibility is a CONTRACT (DD4): a receipt row with no `confirmed:` token grades under today's rule; 535 of 535 corpus Pass rows keep parsing; the only committed hub row the token rule refuses is the T20 checklist cell, repaired in T02's commit; project receipts are dry-run at T09 before the forced sync.
- Commands render from the MAIN checkout only, order render → `--check` → commit (`commands/assemble_commands.py`; the renderer prunes when run from a worktree; the `command-corpus-check` pre-commit hook refuses a commit whose sources are ahead of the installed corpus).
- Never-Route: scripts/enforcement/
- Never-Route: scripts/final_gate.py
- The pool is OFF (D-181/D-182): every seat native; D-190 pricing (haiku 1× · sonnet 2× · opus 5× · fable 10×) stays the cost unit.
- No new dependency; `uv` only; every test SEEN RED first (fail-first or neuter → red → restore → green, the neutered state never staged); every mutation restored inside ONE Bash call with an asserted restore.
- Every `command_run.py` probe in a test sets `COMMAND_RUN_DIR`, `COMMAND_RUN_TRANSCRIPT` and `KAIZEN_EVENTS_DIR` — `tests/conftest.py:114-123` pins only `KAIZEN_EVENTS_DIR`; use `tests/test_command_run.py`'s `_cr` helper (`:42-52`) or set the other two yourself.
- 12-Factor non-negotiables (binding on every ticket): logs = unbuffered to **stdout only, never a logfile** (XI) · migrations = a one-off process against the deployed release, never from `lifespan`/startup (XII) · same backing services in dev/test/prod, no SQLite-for-Postgres, no `fakeredis` (X) · no sticky sessions (VI) · no daemonizing / PID files (VIII) · workers requeue in-flight jobs on SIGTERM (IX) · releases immutable (V) · granular env vars, no grouped env sets, no secrets in code (III) · shelled-out binaries installed + pinned in the Dockerfile (II). None of the tickets touches a deployed surface; the constraints bind by inheritance.
- `datetime.now(UTC)`, never `utcnow()` (core/10-python.md:219); `list[str]` / `str | None` (core/10-python.md:160).
- Never propose or emit a docker volume deletion; never `pkill -f` from a Bash-tool command; never a foreground shell sleep in a fixture.

## Context Ledger

| Source | What binds | Grounded ref |
|---|---|---|
| `.windsurf/rules/core/10-python.md` (MATCHED: scripts/command_run.py, check_convergence.py, check_review_coverage.py) | `uv` only, no new dependency (:21); modern typing forms (:160); `datetime.now(UTC)` (:219); ruff rule-sets ASYNC/B/S (:245) | § Constraints digest |
| `.windsurf/rules/core/45-testing-strategy.md` (glob: tests/**) | one test per behaviour, watched-fail-first (:21); a bugfix ships a regression test that fails first (:31) | every ticket's Behavior Contract; T01 rows 7–8 |
| `.windsurf/rules/core/40-documentation.md` (glob: **/*.md) | tables simple and atomic (:245); no commented-out content (:246); CHANGELOG entry format (:131); INDEX on file add (:139); trailer block its own paragraph (:111) | T06, T07, T08 (INDEX row), every commit |
| `.windsurf/rules/core/62-using-subagents.md` (MATCHED: itself) | the loop-closing FINDER pass is never the author (:186); adjudication stays with the orchestrator (:193-195); the three-seat floor sentence (:65); banned: gating trust on a model name (:262) | T06 (the pack's own text), T07, T09 (the delta round's fresh seat) |
| `.windsurf/rules/core/58-resilience.md` | "every external call has timeout + retry with backoff" (:87) | the 15-minute seat box and the 25-minute reservation clock stay (T04, T07) |
| FLOOR `core/35-security-auth.md` · `core/25-data-postgres.md` · `core/30-ops.md` | activation globs (`:3` in each) hit no path this plan touches; the secrets/env litmus binds by inheritance | read; no row applies — no auth, schema or compose surface |
| `agents-fabrik.md` § Planning Constraints (:362-380) | solo developer; no scaffold reorganisation; state conflicts surfaced in the ticket | the set adds one script under an existing directory, no new top-level path |
| `fabrik-lib/README.md` | vendor, don't build — checked: 71 modules, two mention review, neither is a review engine (spec § fabrik-lib verdict) | all BUILD; not a fabrik-lib candidate (hub-specific machinery) |
| `scripts/enforcement/check_review_coverage.py` | the ONE extraction contract `_ledger_shapes` (:1064) and its 4 positional unpacks (:581, :1263, :1284, :1562), 2 construction sites (:1121, :1134), 7 annotation slots (:1066-1067, :1085, :1093-1096, :1224); the line split at `:754` precedes `_strip_fences` (:766) | T01 |
| `scripts/enforcement/check_convergence.py` | `QUIET_PASS` at `:203`, its single call site `:775` over the whole review text (`:771`); imports from the coverage gate at `:429-446` never include `_ledger_shapes` | T03 |
| `scripts/command_run.py` | the terminal expression `:322-327`, the banner `:329-337`, the series `:342-344`, the trend `:1455-1466`, the ledger row series `:2557`, `_loop_shaped` `:1872`, the round dict `:2006-2022`, the event `:2050-2062` | T09 |
| `scripts/sysadmin/dispatch_headroom.py` | 17 `FLOOR` lines inside `budget()` `:404-575` (code :442 :446 :447 :471 :507 :537 :551 :557 :565 · f-strings :454 :464 :554 · plain string :520 · comments :426 :439 :444 :450); `full_mix` padding `:368-369`; `trim` `:373-388`; callers `:668/:688/:689` | T04 |
| `scripts/final_gate.py` | `run_optional_check(..., warn_only=True)` (:347-374; registrations at :1186, :1203) — the advisory tier a new check joins | T08 |
| `docs/DECISIONS.md` | D-203 (the rulings), D-205 (this approval), D-206/D-207/D-208 (the supersede rows), D-181/D-182 (pool OFF), D-190 (pricing), D-169 (Profile: small — NOT taken: ~690 code lines across 7 code files) | § Global Constraints |
| No `docs/data-contract.md`, no `docs/ui-design.md`, no `specs/services/*.yaml` `shape:` change | internal machinery: no DB, cache, metrics, search or admin surface | — |

## Constraints digest

| Pack | Row (verbatim) | Applies to |
|---|---|---|
| .windsurf/rules/core/10-python.md:21 | "**`uv`** is the mandated Python package manager. Never use raw `pip`, `pip install`, `poetry`, or `pipenv`." | no dependency added by any ticket |
| .windsurf/rules/core/10-python.md:160 | "Use `list[str]` not `List[str]`; use `str \| None` not `Optional[str]`" | the widened tuple annotations (T01), the new script (T08) |
| .windsurf/rules/core/10-python.md:219 | "**`datetime.now(UTC)`, never `datetime.utcnow()`**" | the round event stamp (T09) |
| .windsurf/rules/core/10-python.md:245 | "Ruff's selected rule-sets MUST include `ASYNC` (blocking IO in async code — machine-enforces" | every Python ticket runs `ruff check` in its gate path |
| .windsurf/rules/core/45-testing-strategy.md:21 | "**Watched-fail-first** (for tests this change adds or modifies; trivia stays skipped per the Behavior Contract): a non-trivial behavior's test proves something only if it has been SEEN RED" | every test in the set; V7 names its red-first sites |
| .windsurf/rules/core/45-testing-strategy.md:31 | "**Bugfix** \| One regression test. Write a test that **fails first** reproducing the bug, then implement the fix." | the two unnamed unpack sites (T01 row 7), the 900-character window test (T01) |
| .windsurf/rules/core/40-documentation.md:245 | "**Keep tables simple and atomic** — no multiline cells" | the ledger row grammar stays one line (T01, T02) |
| .windsurf/rules/core/40-documentation.md:246 | "**No commented-out content blocks** — dead text confuses AI and pollutes diffs" | the D-191 sentence is replaced, never commented out (T06, T07); the POOL-OFF comments stay as the sanctioned exception |
| .windsurf/rules/core/40-documentation.md:131 | "**Format:** Entry under `## [Unreleased]` with `### Added\|Changed\|Fixed — Title (YYYY-MM-DD)`" | one CHANGELOG entry per ticket (Deltas) |
| .windsurf/rules/core/40-documentation.md:139 | "**Update when:** Any file added, removed, or moved." | INDEX rows for the new script and the new tests (Deltas) |
| .windsurf/rules/core/40-documentation.md:111 | "The trailer block must be its OWN paragraph with NO blank line inside it: git parses only the LAST paragraph, and only if it is all-trailers." | every commit |
| .windsurf/rules/core/62-using-subagents.md:186 | "The loop-closing round's **FINDER pass** runs in a context that did **not author the artifact**" | T09's delta round carries a fresh non-authoring Opus seat (DD10) |
| .windsurf/rules/core/62-using-subagents.md:193-195 | "**Adjudication — decide/refute/merge — stays with the orchestrator** … this rule governs who HUNTS last, never who adjudicates." | executing a refutation is adjudication (D6) — the text T06/T07 write says so |
| .windsurf/rules/core/62-using-subagents.md:65 | "**NEVER solo, never two — the FLOOR is three seats.** A surface with fewer than three units still dispatches THREE seats on DIFFERENT angles over it" | the MUST this plan narrows to `/fabrik-review-scoped` and the grounding commands (DD2, D-208) — T06 |
| .windsurf/rules/core/62-using-subagents.md:262 | "Gating a review's trust on a specific pool model name instead of the methodology (native-Opus authority + refutation)." (Banned) | D2 names roles by kind; trust rests on executed refutation |
| .windsurf/rules/core/58-resilience.md:87 | "every external call has timeout + retry with backoff. Circuit-breaker for repeated failures." | the seat time box and reservation clock bound a hung seat |
| FLOOR .windsurf/rules/core/35-security-auth.md:3 · 25-data-postgres.md:3 · 30-ops.md:3 | the activation `globs:` lines — `**/auth/**`, `**/secrets/**`, …; `**/db/**`, `**/migrations/**`, …; `**/Dockerfile`, `**/compose.yaml`, … | no path in File Scope matches: no auth, schema or compose surface — read, none applicable; the secrets litmus ("ZERO secrets/constants in code") binds by inheritance and no ticket reads env |

## Execution Discipline (binding on /fabrik-execute-plan)

- **Review floor** — every ticket, on the coder's return, runs `/fabrik-review` on its changed surface to a coverage-adjudicated exit BEFORE its merge; no ticket merges on a first-pass green. The plan is its own first customer, so the closing bar is stated per phase: until T01+T02 are merged to master the hub's gate reads the OLD rule and every receipt closes on `found: 0 · new: 0 · fixed: 0` (T01, T03, T04, T05, T06 — small surfaces; T01's own receipt is graded by the gate T01 rewrites, so its closing row is checked BOTH by the committed gate at HEAD~ and by the new one); from T02's merge on, every receipt closes on a row carrying `confirmed: 0` (the working tree's gate is the hub's gate), and RECORDED/REFUTED rows never reopen the loop (D-203 binds by ruling). No round cap; the NON-CONVERGENCE escalation stays the only other exit.
- **Dispatch policy** — native Claude seats for every fan-out (the pool is OFF, D-181): the coder for T01, T02, T03, T08 is a native Opus worktree coder (`never-route`: `scripts/enforcement/`, `scripts/final_gate.py`); T06, T07, T09 are `native` (fleet-synced governance text, the command corpus, the run record and the delta round — Opus); T04 (`complex`) and T05 (`simple`) dispatch a native Sonnet coder. Per-ticket review seats: the D-191 mix under the old corpus until T07 renders (Opus authoritative + one Sonnet + one Haiku per unit, `dispatch_headroom.py --units`); from T07's merge, the partition (`--slices`) — stamped BEFORE they go out with `python3 scripts/command_run.py dispatch --seats <n>`. The Opus seat is the authoritative reader of every `scripts/enforcement/` and `scripts/command_run.py` slice (DD7's risky list). Every receipt is written with `scripts/review_receipt.py --init` and graded by the hub's gate before its commit (`git add -N` then `python3 scripts/enforcement/check_review_coverage.py <receipt>`).
- **Parallelism + merge** — T01, T03, T04, T05, T06 fan out concurrently at dispatch 1 (disjoint Touches); T02 follows T01 on `scripts/enforcement/check_review_coverage.py` (the Serialized row); T07 waits for T04, T05 and T06 (its V7 test reads their sentences); T08 waits for T02 (`VERDICT`); T09 runs last and alone. Results merge in the MAIN checkout in Merge Order by private-index commit; the D-191 receipt's flip and the governance-file rows are the orchestrator's Deltas at T09, never a coder's edit.

## File Scope (owned paths)

- scripts/enforcement/check_review_coverage.py
- tests/enforcement/test_review_confirmed_grammar.py
- tests/enforcement/test_review_refusals.py
- tests/enforcement/test_review_exit_contract.py
- tests/test_check_review_coverage_blocked.py
- scripts/review_receipt.py
- tests/test_review_receipt.py
- scripts/enforcement/check_convergence.py
- tests/test_check_convergence.py
- scripts/sysadmin/dispatch_headroom.py
- tests/sysadmin/test_dispatch_headroom.py
- docs/workstation/claude-account-rotation.md
- scripts/sysadmin/quota_dashboard.py
- docs/workstation/quota-dashboard.md
- .windsurf/rules/core/62-using-subagents.md
- CLAUDE.md
- templates/governance/CLAUDE.md
- docs/reference/convergence-prompts.md
- docs/reference/MD/ai-prompt-templates.md
- commands/_sources/fabrik-review.md
- commands/_sources/fabrik-repo-review.md
- commands/_sources/fabrik-review-scoped.md
- commands/_sources/fabrik-rules-review.md
- commands/_fragments/subagents-core.md
- tests/test_assemble_dispatch_step.py
- scripts/enforcement/check_review_hygiene.py
- tests/enforcement/test_check_review_hygiene.py
- scripts/final_gate.py
- docs/workflows/FINAL_GATE_WORKFLOW.md
- scripts/command_run.py
- tests/test_command_run.py
- docs/reference/command-run-protocol.md
- docs/workstation/kaizen-event-stream.md
- docs/development/reviews/2026-09-09-plan-1-review-convergence-redesign-review.md

## Evidence

- Every code surface the spec anchored at 2dec30c8 is byte-identical at HEAD (81d9571a), so the spec-review's 16-of-16 anchor verification holds for this plan's citations:

```text
$ git diff --stat 2dec30c8 HEAD -- scripts/enforcement/check_review_coverage.py scripts/enforcement/check_convergence.py scripts/command_run.py scripts/sysadmin/dispatch_headroom.py scripts/sysadmin/quota_dashboard.py scripts/review_receipt.py commands/_sources/fabrik-review.md commands/_sources/fabrik-repo-review.md commands/_sources/fabrik-review-scoped.md commands/_sources/fabrik-rules-review.md commands/_fragments/subagents-core.md .windsurf/rules/core/62-using-subagents.md CLAUDE.md templates/governance/CLAUDE.md | wc -l
0
```

- T01 — the extraction contract's every reader (the spec named `:581` and `:1562`; the grounding pass found four unpacks and two constructions):

```text
$ grep -n 'for f, _x, _ln in\|f_found, f_fixed, f_line\|for _, _, line in rows\|row = (pair\[0\]\|row = (pc\[0\]\|_ledger_shapes(text)' scripts/enforcement/check_review_coverage.py
572:    ev_tables, ev_prose, ordered_rows = _ledger_shapes(text)
581:    founds = [str(f) for f, _x, _ln in ordered_rows]
1121:                row = (pair[0], pair[1], line)
1134:                row = (pc[0], pc[1], line)
1223:    tables, prose_rows, _ = _ledger_shapes(text)
1263:        f_found, f_fixed, f_line = rows[-1]
1284:        pairs = [_MEGA_HASH_PAIR.search(line) for _, _, line in rows]
1542:        c_tables, c_prose, ordered_rows = _ledger_shapes(text)
1562:        rows = [str(f) for f, _x, _ln in ordered_rows]
```

- T01 — the line split precedes the fence strip, so the normalisation must run on `text` before `_kept_lines` (scripts/enforcement/check_review_coverage.py:754, :766-768) and reuse the canonical break set (:299):

```text
$ sed -n '299p;754p;766,768p' scripts/enforcement/check_review_coverage.py
_LINE_BREAKS = "\r\n\v\f\x1c\x1d\x1e\x85\u2028\u2029"  # == what str.splitlines() splits on
    lines = text.splitlines(keepends=True)
def _strip_fences(text: str) -> str:
    live, _quoted = _split_indented(_kept_lines(text))
    return "".join(live)
```

- T02 — `VERDICT` carries no `RECORDED` alternative today (scripts/enforcement/check_review_coverage.py:51); the D-191 receipt is the only one of 275 that writes the verdict (52 occurrences):

```text
$ sed -n '51p' scripts/enforcement/check_review_coverage.py; grep -c 'RECORDED' scripts/enforcement/check_review_coverage.py
VERDICT = re.compile(r"\b(CLEAN|FIXED\s*\(?\d*\)?|REFUTED|ROUTED\s*\(?\d*\)?)\b")
0
```

- T03 — `QUIET_PASS` is at `:203` (the spec says `:200`, the comment block's start), one call site at `:775` over the whole review text:

```text
$ grep -n '^QUIET_PASS' scripts/enforcement/check_convergence.py
203:QUIET_PASS = re.compile(r"found:\s*0\b[^\n]*?fixed:\s*0\b", re.I)
```

- T04 — the 17 `FLOOR` lines inside `budget()` (scripts/sysadmin/dispatch_headroom.py:404-575):

```text
$ awk 'NR>=404 && NR<=575 && /FLOOR/ {print NR}' scripts/sysadmin/dispatch_headroom.py | tr '\n' ' '
426 439 442 444 446 447 450 454 464 471 507 520 537 551 554 557 565
```

- T05, T06, T07 — the D-191 sentence's sites by a LINE grep, which misses `quota_dashboard.py` (two adjacent literals, `:1911-1912`) and the rotation doc (wrapped at `:227-228`) — the reason V7 joins lines:

```text
$ grep -rlc 'one Sonnet breadth seat AND one Haiku\|one Sonnet + one Haiku' commands/_sources commands/_fragments .windsurf/rules/core/62-using-subagents.md CLAUDE.md templates/governance/CLAUDE.md scripts/sysadmin docs/workstation | grep -v ':0$'
commands/_sources/fabrik-review-scoped.md
commands/_fragments/subagents-core.md
.windsurf/rules/core/62-using-subagents.md
CLAUDE.md
templates/governance/CLAUDE.md
$ printf '%s of %s sources include subagents-core\n' "$(grep -l '{{include:subagents-core}}' commands/_sources/*.md | wc -l)" "$(ls commands/_sources/*.md | wc -l)"
20 of 36 sources include subagents-core
```

- T09 — the terminal expression (scripts/command_run.py:322-327) and the `round` row of the protocol doc (docs/reference/command-run-protocol.md:55), the kaizen field list (docs/workstation/kaizen-event-stream.md:115):

```text
$ sed -n '322,327p' scripts/command_run.py
    terminal = (
        bool(classes)
        and not open_c
        and int(last.get("findings", 0)) == 0
        and bool(last.get("swept"))  # the record's key; the event stream says classes_swept
    )
$ sed -n '115p' docs/workstation/kaizen-event-stream.md
| `round` | `n`, `findings`, `classes_swept`, `classes_new`, `classes_open` | `scripts/command_run.py round` |
```

- T09 — the round-18 fix diff the first application's delta round covers (the commit that BLOCKED the receipt):

```text
$ git show --stat --format= 69f01b92 | tail -6
 CHANGELOG.md                                       |   6 +-
 .../2026-09-08-box-bound-seats-d191-review.md      | 307 ++++++++++++++++++---
 docs/reference/command-run-protocol.md             |   2 +-
 tests/test_command_feedback.py                     |  14 +-
 tests/test_conftest_isolation.py                   |   6 +-
 5 files changed, 291 insertions(+), 44 deletions(-)
```

- Sizing — the grounding dispatch this plan ran (7 seats on 5 units, `--mechanical 0`, 2 risky) and the corpus population:

```text
$ python3 scripts/sysadmin/dispatch_headroom.py --units 5 --risky 2 --mechanical 0 | grep -E '^SEATS'
SEATS: 7  (units=5, read-only; caps {'wanted': 7, 'concurrency_cap': 20, 'box_cap': 19})
$ ls docs/development/reviews/*.md | wc -l
275
```

## Self-audit

- Grounding passes: 7 native `fabrik-researcher` seats (2 Opus authoritative on the coverage gate and the run record, 5 Sonnet breadth on the receipt template, the convergence gate, the seat budget, the corpus text and the hygiene classes), all pinned to the working tree = HEAD = 2dec30c8 for every surface (§ Evidence, block 1), plus my own reads of every `path:line` this spine and its tickets cite. Findings folded in: the four unpacks and two constructions (T01), `_strip_fences` normalising BEFORE the split (T01), the mega exit rule as a second definition of quiet (T01 row 7 — same branch rule), the `:1048` and `:1042-1044` retyped literals (T01), the 900-character `inspect.getsource` window test (T01), `VERDICT` without `RECORDED` (T02), no residual section and no finders-cell reader today (T02), `QUIET_PASS` at `:203` not `:200` (T03), no `--units`-required test today (T04), the two adjacent literals and the wrapped doc line (T05, T07), `CLAUDE.md:38-39` / template `:30-31` for the no-op paragraph (T06), `fabrik-rules-review.md:138` citing D-048 (T07), the private fence tracker in `check_command_corpus.py:943-960` and `check_retired_terms.py`'s always-exit-0 contract (T08), the one breaking test at `tests/test_command_run.py:3073-3087`, the `_loop_shaped` tuple, the ledger row series and the AFTER-EDIT header missing three callers (T09).
- (a) Coverage — spec I1–I20 and R1–R11: R1/R2/R6 (D1) → T01, T02, T03, T09; R3 (D2) → T04, T06, T07; R4 (D4) → T08, T07; R5 (D5) → T07, T09; R7 (D3) → T04, T05; R8 (D6) → T02, T07; R9 (D7) → T01, T02, T03, T09; R10 (D8) → T07 (the fragment's brief template); R11 (D9) → T09; D10 → T07 (`fabrik-review-scoped.md`); § Documentation landing sites → T04 (rotation doc), T05 (board doc), T06 (prompts, template), T09 (protocol, kaizen) + Deltas (CHANGELOG, INDEX, backlog, D-rows); V1–V13 → T01 (V1, V2 grammar half), T02 (V2 refusal half, V5, V11), T03 (V13), T04 (V4), T07 (V7, V8), T08 (V6, V10 backlog), T09 (V3, V9, V12). This run's I1–I8 → § Intake Inventory. No agreement without a ticket.
- (b) Cross-ticket signatures — the 5-tuple `(found, confirmed | None, fixed, unexecuted | None, line)` is produced by T01 and consumed by T02, T08 (via `_table_rows`, unchanged shape) and never by T03 (§ Interfaces); `VERDICT`'s four RECORDED forms are written by T02 and read by T08 and the T09 receipt; `--slices` JSON keys are produced by T04 and left unread by T05 (the banner reads five existing keys); the V7 literals are written by T04/T05/T06 and asserted by T07; `round --confirmed` is produced by T09 and used by T09's own delta round.
- Sizing: `Profile: small` NOT taken — ~690 code lines across 7 code files (coverage gate ~250, hygiene script ~250, `dispatch_headroom.py` ~90, `command_run.py` ~70, `review_receipt.py` ~20, `check_convergence.py` ~5, `quota_dashboard.py` ~3) plus ~10 text files; the set shape by the >3-phase and READ-budget triggers. Per-ticket READ sets (Touches + Context Files, bytes, `wc -c` this run): T01 ≈ 244 KB, T02 ≈ 242 KB, T03 ≈ 227 KB, T04 ≈ 244 KB, T05 ≈ 195 KB, T06 ≈ 243 KB, T07 ≈ 228 KB, T08 ≈ 203 KB — every one under `READ_BUDGET_BYTES` 262,144; T09 carries `scripts/command_run.py` (137,490) + `tests/test_command_run.py` (144,794) by the Integration hatch. The emit gate's summary line is recorded in § Residual unknowns once run.
- Fixed point: not yet — this is the DRAFT; `/fabrik-plan-review` converges it in this turn.

## Coverage Checklist

Rubric over the touched surfaces (`python scripts/review_rubric.py --changed scripts/enforcement/check_review_coverage.py scripts/enforcement/check_convergence.py scripts/command_run.py scripts/sysadmin/dispatch_headroom.py commands/_sources/fabrik-review.md commands/_sources/fabrik-repo-review.md commands/_sources/fabrik-review-scoped.md commands/_fragments/subagents-core.md .windsurf/rules/core/62-using-subagents.md CLAUDE.md templates/governance/CLAUDE.md`):

```text
# REVIEW RUBRIC — inject into EVERY finder prompt (generated by review_rubric.py)
## FLOOR — always injected, regardless of glob (spec L3)
### core/35-security-auth.md
### core/25-data-postgres.md
### core/30-ops.md
## MATCHED — packs whose globs hit the changed paths
### core/10-python.md  (hit: scripts/command_run.py, scripts/enforcement/check_convergence.py, scripts/enforcement/check_review_coverage.py)
```

| Class | Status |
|---|---|
| core/10-python.md rows (uv, typing, datetime, ruff sets) | CLEAN — no dependency; the tuple annotations use `int \| None` (T01); `datetime.now(UTC)` for the event stamp (T09); ruff in every Python gate path |
| core/40-documentation.md rows (atomic tables, no commented-out text, CHANGELOG, INDEX, trailers) | CLEAN — one-line ledger rows (T01/T02); replacement not comment-out (T06/T07); one CHANGELOG entry per ticket and INDEX rows for the new script and tests (Deltas) |
| core/62 rows (non-author closing seat, adjudication with the orchestrator, the floor's new scope, no model-name gating) | CLEAN — T09's delta round dispatches a fresh Opus seat; T06/T07 write the executed-critic rule; D-208 narrows the floor by ruling |
| FLOOR 35/25/30 | CLEAN — no auth, schema or compose surface; no ticket reads env or secrets |
| Recurrence: bounded-count claims without denominators | CLEAN — "535 of 535", "2 of 275", "166 of 275", "28 cells / 30 occurrences / 0 lost", "1 row of 275", "20 of 36", "17 FLOOR lines", "3 call sites / 4 unpacks / 2 constructions / 7 annotation slots", "0 of 5 tests", "31 tests unchanged" all carry their denominators |
| Recurrence: proxy-as-evidence | CLEAN — every gate line is a runnable command; V7 joins lines because the line grep in § Evidence demonstrably misses two sites; the emit gate's summary line (not its exit code) is the sizing evidence |
| Recurrence: fleet blast radius of a synced surface | CLEAN — `scripts/enforcement/`, `command_run.py`, core/62 and the governance template are named synced in § Global Constraints; backward compatibility is a contract row (DD4); T09 dry-runs the token rule over project receipts before the forced sync |
| Recurrence: idempotency / fail direction asserted on disk | CLEAN — every refusal is fail-CLOSED and named; the two known fail-open shapes (an inert tail after a quiet row; a non-Pass-headed comma-cell row) are booked to the backlog with their measured fire rates (spec D7), not silently accepted |

## Pass Ledger

| Pass | Layer | Method | Findings → fixed | What was re-derived |
|---|---|---|---|---|
| Pass 0 | 7 native `fabrik-researcher` grounders (2 Opus, 5 Sonnet) + own reads | method: re-derivation | 23 grounding deltas → all folded into the tickets before emit | every anchor in § Evidence and every `path:line` in T01–T09 |

## Residual unknowns

- **Resolved:** the reader enumeration of `_ledger_shapes` (4 unpacks, 2 constructions, 7 annotation slots — T01); where the normalisation runs (before `_kept_lines`, T01); which test breaks in `tests/test_command_run.py` (one, `:3073-3087` — T09); the Integration hatch for the run record's file pair (I8); the verdict shape for hygiene false positives (I6 → parentheses).
- **Resolved by ruling, not to be re-litigated:** no round cap, no majority vote, no severity-weighted exit, the overlapping seats retired (D-203, D-207, D-208).
- **Open (self-service, T09):** the token rule's fire rate over the ~46 projects' receipts is measured by T09's dry run (`for r in /opt/*/docs/development/reviews/*.md`, count and denominator in the receipt) BEFORE the forced sync; a hit in a project receipt is repaired by mail to that repo's agent, never by a hub edit of a project file.
- **Open (measured after ship, backlog):** the hygiene script's false-positive rate over its first 20 receipts fleet-wide (DD6, V10) — a `[infra]` backlog row written at T09; it errors only after graduation.
- **Open (named, not built):** the first `QUIET_PASS` alternative requires a bare `found: 0` while the second tolerates `0+`; colon homoglyphs are outside `_strip_fences`'s normalisation — both fail-CLOSED with 0 corpus exemplars (spec § Machinery report); V13 freezes the spec's regex verbatim, so the one-character `0+` symmetry waits for a later spec.
- **Resolved (sizing evidence, the emit gate's own summary line, 2026-09-09):** `✓ [plan_tickets] /opt/fabrik/docs/development/plans/2026-09-09-plan-1-review-convergence-redesign: graded 9 ticket(s), 35 Touches path(s), 47 Context-Files entry(ies); READ budget measured against /opt/fabrik; 0 finding(s)` — exit 0, zero WARN lines; `check_plan_quality.py --plan-dir` exit 0 with no output (its silent rc 0 is re-read by `/fabrik-plan-review`). The first emit refused T02's Touches entry for the T20 receipt (`outside this plan's stem — a ticket owns only its OWN plan's review/lock artifacts`); the repair moved to the orchestrator's Deltas.
