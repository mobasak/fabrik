# Mail triage — the command corpus, the review machinery and the feedback relays (62 mails, validated 2026-09-12)

Status: DRAFT
Profile: standard
**Owner:** — (infra; the unnamed hub window fabrik-06, session dd3c06d1)
Date: 2026-09-12
Predecessors: `docs/development/plans/archived/2026-09-11-plan-1-review-family-pass3.md` (D-242) · the fabrik-mail inbox `/opt/fabrik-mail/fabrik/inbox` (231 messages on 2026-09-12; 62 concern this plan) · the operator's word 2026-09-12: "check all mails regarding commands and also feedbacks and validate them first" → "record them all in a tasklist, address them all"

## Goal

Every mail about a `/fabrik-*` command, the review machinery (`command_run.py`, the four review graders, the Stop hook, the seat briefs) or a close-out FEEDBACK relay is either FIXED with a red-first grader, MOOT with the ruling named, REPLIED with the commit, or ROUTED to its beat — and every one of the 62 is acked. The tasklist below is the record; each step names the mail ids it closes.

## DONE WHEN

- 0 of the 62 mails listed here remain in `/opt/fabrik-mail/fabrik/inbox` (`mail.py list` filtered by the ids in this file → 0).
- Every T2–T6 item has a commit on `master` naming its mail id(s), or a `MOOT`/`ROUTED` disposition in § Execution notes with the reason.
- The five suites named in § File Scope are green; `python3 scripts/final_gate.py --check --json` → `"status":"success"`; render → `--check` → `check_command_corpus.py` green after every command-text step.
- The whole-plan `/fabrik-review` receipt `docs/development/reviews/2026-09-12-plan-2-mail-triage-command-machinery-review.md` is CONVERGED.

## Out of Scope

- The ~25 gate, hold and sync mails not about commands or review machinery (T10 lists them for a later triage; they are not addressed here).
- Any edit to `libs/subagents/` (D-137/D-210) or to a project's copy of a synced file.
- The kaizen loop pieces 1–4 (the sibling window's plan `2026-09-12-plan-1-kaizen-corpus-weight-and-tokens-per-round.md`); T7.1 hands that plan the one registration block it asked for and nothing more.
- Re-litigating the settled rulings: D-203, D-206, D-207/D-208 (narrowed by D-229), D-212, D-218, D-219, D-229, D-230, D-231, D-238, D-242, D-181/D-182.

## Validation record (read-only, 2026-09-12)

Every disposition below was checked against the tree at 091439d4 with `grep`, `head` and `mail.py read`; the code line cited is the one read. FIXED = landed before this plan; OPEN = still present; MOOT = superseded by a ruling; PARTIAL = half landed.

| Mail | Sender | Claim | Verdict | Evidence |
|---|---|---|---|---|
| 01M21FB59 | trade-intelligence | coverage still enforces D-048 | FIXED | `check_review_coverage.py::_confirmed_quiet` (D-206) |
| 01M25HTDF | hub | two closing-round shapes rendered | FIXED | `grep -c "FULL fresh sweep" commands/_fragments/term-coverage.md` → 0 mandates (pass 3 D2) |
| 01M1VRMZ6 | hub | scoped step-1 trigger list narrower than § 1a | FIXED | `fabrik-review-scoped.md:15` carries all five triggers (pass 3 D6) |
| 01M1Z91JBG | hub | researcher seat has no Bash yet commands mandate probes | FIXED | `fabrik-spec-review.md:100`; the D8 sentence self-qualifies |
| 01M1XJTT | fabrik-lib | `command_run.py` has no `--surface` | CLOSED | their re-vendor 01M1YXTTCX |
| 01M23D1BF | transdoc | `--confirmed` unrecognised; check_doc_index bills the wrong run | stale copy (synced 09-12) / OPEN | T4.6 |
| 01M1XKEVX | hub | read_only pool briefs ask for execution | MOOT | D-181; text inside POOL OFF comments |
| 01M1XKVN8P | wef | plan-review exit satisfiable by repetition | ADDRESSED | D-206/D-212; the closing row's re-derivation method rule |
| 01M288YHD | fabrik-lib | nesting does restore; the sixth cause fires on the parent's edits | OPEN (narrow) | T5.1 |
| 01M1RHJY | hub | `_phase_review_exists` vacuous | OPEN | `command_run.py:474` still carries the unscoped `-T\d{2}-review.md` alternative |
| 01M1RFN3 | fabrik-lib | untracked plans never graded; md5 anti-cheat self-referential | OPEN / doc | `check_convergence.py:827` skips `??` |
| 01M1SNCXH6 (+3) | wef | a committed EXECUTED plan is never re-audited | OPEN | `_converged_targets` grades only claims new this commit; no `_committed_nonquiet` twin |
| 01M1SQZ80 | wef | QUIET_PASS satisfied by prose | PARTIAL | `check_convergence.py:329` still a line regex; spines use `_PASS_ROW` |
| 01M20W9QK | hub | a missing Hunt row is invisible | OPEN | `grep -n "Hunt:" check_review_coverage.py` → 0 |
| 01M28K3F44 | fabrik-lib | VERDICT rejects RECORDED; graders blind to an unchanged artifact | OPEN | `check_review_coverage.py:62` |
| 01M285X4H | wef | hygiene drops 3 of 4 classes off `.md` | OPEN (by design, undocumented) | `SURFACE_SUFFIXES`, the `.md` gates at :463/:469 |
| 01M2AC95X | wef | hygiene double-counts, no ledger exclusion, echoes the copy's path | OPEN | own `--claim` sweeps showed the inflated counts |
| 01M215G84 | trade-intelligence | oscillation advisory misreads delta rounds; no seat can confirm an external fact | OPEN | the advisory fired at round 7 of the pass-3 whole-plan review |
| 01M2368XB, 01M236V84, 01M23ESF5 | wef | scoped command names no stamp, no pin | OPEN | `grep -n "pinned\|md5\|SHA" fabrik-review-scoped.md` → 0 |
| 01M1VVPJS, 01M1RHQK (youtube) | iie, youtube | the >5-file route-up counts binaries and doc companions | OPEN | the trigger is a raw file count |
| 01M25Y93M | fabrik-lib | mutation rounds hit the 120 s default; tree left mutated | PARTIAL | the copy rule (D8) lands; `grep -i timeout fabrik-review.md` → 0 |
| 01M25Q9S0 | wef | `--allow-external --json` NOTE on stdout; breadth fails open; prose-grep checks | OPEN | unverified beyond the mail's own reproduction |
| 01M1SR1WK | bic | packs counted in the READ budget; re-derivation regex | OPEN | `READ_BUDGET_BYTES = 262144`, no pack exemption seen |
| 01M1V67JR, 01M21804, 01M218KM, 01M1T7WPY | wef | check_plan_tickets gaps | OPEN | `grep "\.astro"` → 0 |
| 01M1VQZJ8 | fleet | reviewer Method step 1; surface-blind FLOOR; hooks-index derives its requirement | OPEN | — |
| 01M22KN7 | hub | orphaned uncommitted check_command_corpus.py edit | OPEN | `git status` → ` M` |
| 01M20B0CH, 01M1VPA9C | fabrik-lib, hub | seat deaths; agent roster | harness | T9 |
| 01M25EG0N | fabrik-lib | coverage reports one problem per artifact | REFUTED in part | five refusals printed at once on 2026-09-12 |
| 01M21JAET | trade-intelligence | sixth cause unclearable after an interruption | PARTIAL | 28ca7443 floors at the ledger's birth |
| 01M2AJKKV, 01M28VKD8 | hub | two requests to infra | OPEN | T7 |
| 7 kaizen collections | hub | daily requests 09-04 … 09-11 | OPEN | T8 |
| 7 FEEDBACK relays | hub | 35 close verdicts | see T2 | the recurring asks mapped in § Phase A |

## File Scope (owned paths)

- `commands/_sources/fabrik-review-scoped.md`, `fabrik-review.md`, `fabrik-plan-review.md`, `fabrik-execute-plan.md`, `fabrik-ui-design.md`, `fabrik-ui-design-review.md`, `fabrik-doc-converge.md`; `commands/_fragments/term-edit.md`, `term-coverage.md`, `subagents-core.md`; `commands/_agents/fabrik-reviewer.md`; `scripts/review_receipt.py`
- `scripts/command_run.py`; `scripts/enforcement/check_convergence.py`, `check_review_coverage.py`, `check_review_hygiene.py`, `check_plan_tickets.py`, `check_ticket_breadth.py`, `check_doc_index.py`, `check_hooks_index.py`; `scripts/review_rubric.py`; `scripts/final_gate.py`
- `.claude/hooks/final_gate_stop.py`
- `CLAUDE.md`, `templates/governance/CLAUDE.md`, `docs/workflows/FINAL_GATE_WORKFLOW.md`, `docs/reference/command-run-protocol.md`
- tests: `tests/test_assemble_dispatch_step.py`, `tests/enforcement/test_review_exit_contract.py`, `tests/enforcement/test_check_review_hygiene.py`, `tests/enforcement/test_check_convergence*.py`, `tests/enforcement/test_check_review_coverage*.py`, `tests/test_command_run*.py`, `tests/test_agent_definitions.py`, the hook's suite
- shared files by HEAD blob + hunk: `CHANGELOG.md`, `docs/DECISIONS.md`, `docs/STRATEGIC_BACKLOG.md`, `INDEX.md`

## Phase 0 — Mail: the replies, acks and routings that need no code

**Steps.**
1. T1 — ✅ DONE 2026-09-12 (replies 01M2AT9NNCWZB9TJDXFJN1KBHT, 01M2AT9YGP3ZC24V0S6B276SH4, 01M2ATA99CQDFW1E652KX50G95; all seven acked) — reply + ack the seven fixed/addressed items: 01M21FB59 (D-206), 01M25HTDF (2ec89bb5), 01M1VRMZ6 (acb50492), 01M1Z91JBG (2d5419a8 + spec-review :100), 01M1XJTT (their re-vendor), 01M23D1BF (finding 1 synced 09-12; finding 2 → T4.6), 01M1XKVN8P (D-206/D-212). Six ack-free items already acked on 2026-09-12: 01M1XKEVX, 01M288YHD, 01M1YXTTCX, 01M1YXTTEY, 01M1YXNK4, 01M1RJXN6.
2. T7.1 — ✅ DONE 2026-09-12 (a63bda73, reviewed to confirmed 0 through 418f86b0 · 4662aad1 · b43d679f · bd69e10e · 205bdd29 · 6049a968 · 052c32d8 · 0a1fe8bc — nine passes, receipt `docs/development/reviews/2026-09-12-mail-triage-t7-review.md`; the six-surface bullet per D-241) — 01M2AJKKV: the `final_gate.py` registration block + the `FINAL_GATE_WORKFLOW.md` bullet for `check_corpus_weight.py` (`warn_only=True`, `--check` threaded); reply with the sha.
3. T7.2 — ✅ DONE 2026-09-12 (a63bda73 + 418f86b0 + 4662aad1; the same heavy review) — 01M28VKD8: the nine kaizen-spec amendment candidates C1–C9, fixed by THIS session (the pen change the breaker demands), reviewed scoped, reply with the sha.
4. T8 — ✅ DONE 2026-09-12 (eight replies, eight acks — the metrics carry no ask) — the kaizen daily collections (09-04 … 09-11): reply each with this beat's entries (or `none`), ack.
5. T9 — ✅ DONE 2026-09-12 (one backlog row; 01M20B0CH and 01M1VPA9C acked; 01M1VQZJ8 stays open for T2.12/T4.11/T4.12) — 01M20B0CH, 01M1VPA9C, 01M1VQZJ8 (3): backlog rows (harness-side), acks; 01M1VQZJ8 (3) routed to fleet (hooks).

**Behavior Contract.**
- **Given** the 62 ids, **When** `mail.py list` runs at Finish, **Then** none of them is in the inbox.

## Phase A — Command text (T2) — one render chain, one `/fabrik-review-scoped` routed up by its own rule

**Steps.**
1. T2.1 `fabrik-review-scoped.md` step 5: "stamp first — `python3 scripts/command_run.py dispatch --seats <n>` before the message that dispatches them" beside the reader floor (01M2368XB, 01M1XPGPNT).
2. T2.2 the same command: every seat brief names a PIN — a copy under the scratchpad plus the md5 of `git diff HEAD -- <surface>` — and the finder re-diffs before reporting (01M236V84, 01M23ESF5).
3. T2.3 the same command, the classification: the >5-files trigger counts the DIFF surface — code and tests; binaries and the mandated CHANGELOG/LESSONS/BACKLOG companions never count (01M1VVPJS, 01M1RHQK).
4. T2.4 `fabrik-review.md` + `term-coverage.md` round-zero: a mutation battery runs with an explicit `timeout` at or above its own runtime and only on a copy (01M25Y93M).
5. T2.5 `fabrik-review.md` class ledger + `fabrik-plan-review.md` termination: "a class check must LOAD the artefact it grades; a grep for the wording that describes a defect matches the artifact's own correction and is refuted by any rewording — narrowing such a check is not converging" (01M25Q9S0 (3)).
6. T2.6 `term-coverage.md` + `term-edit.md`: the scope-growth stop — when N consecutive rounds' findings fall inside code the change ADDED, route that surface to `/fabrik-spec` and converge on the original diff (01M2AJG97 fabrik-lib).
7. T2.7 `fabrik-execute-plan.md`: resuming a plan MEASURES its Status against the receipts on disk before reading it; D2's precondition probes the surface it dispatches to (01M2AJG97, 01M2803TM iie).
8. T2.8 `subagents-core.md` / `term-edit.md`: a delta seat's brief carries the previous seat's REFUTED list verbatim.
9. T2.9 `fabrik-review.md`: a `fabrik-researcher` seat is dispatched for any PLAUSIBLE whose ground truth is outside the repo (01M215G84 (2)).
10. T2.10 the verdict vocabulary: the command's description line and the grader agree (RECORDED accepted, ROUTED kept) — with T4.4 (01M28K3F44 (1)).
11. T2.11 `fabrik-ui-design.md` + review twin: a size ceiling per contract with a history-split instruction; the Read-cap bound named (01M2803TM transdoc, 01M25G1BN).
12. T2.12 `commands/_agents/fabrik-reviewer.md` Method step 1: the materialised-tree case and `git -C <repo> show <sha>:<path>` (01M1VQZJ8 (1)).
13. T2.13 `fabrik-doc-converge.md`: a generic project-local reference-doc row in the Convergence Contract table (01M1V443 site-provisioner).
14. T2.14 `term-edit.md` round-zero: "when a check reports CLEAN, verify the check can fail"; a re-derivation script is itself a bounded search whose matcher needs its own denominator (01M1RHQK site-provisioner, 01M1SNGE4).
15. T2.15 `scripts/review_receipt.py`: the quoted row-shape block sits OUTSIDE the ledger section under a heading that says it is an example (01M22VA3X).
16. T2.16 verify the scoped step-5 escalation counts CONFIRMED (pass 3) — a citation, no edit if true.
17. Render → `--check` → `check_command_corpus.py` → hygiene; the graders in `tests/test_assemble_dispatch_step.py` / `test_review_exit_contract.py` for each new sentence, red first; commit by private index; the scoped review routes up (>5 files) — one heavy round.

**Behavior Contract.**
- **Given** the rendered corpus, **When** the hygiene script and the exit-contract tests run, **Then** every new sentence is present once at its source and 0 retired phrases return.

## Phase B — `command_run.py` (T3) and the graders (T4) — red-first, one `/fabrik-review`

**Steps.**
1. T3.1 `_phase_review_exists`: the ticket alternative binds to the plan stem the record carries AND the artifact's mtime must be at or after the record's start (01M1RHJY, 01M1RJXN6).
2. T3.2 `round`: `new:` derived from the classes ledger (or a `--new` counter refused when it exceeds `--findings`) (01M1SWQJ).
3. T3.3 the oscillation advisory reads the dispatch's `--delta`/surface size and suppresses itself when the surface shrank (01M215G84 (1)).
4. T3.4 `_parse_usage_feedback` refuses a verbatim unfilled `<…>` value; `_USAGE_GRAMMAR` round-trips through its own parser (backlog F25/F26).
5. T3.5 the seats advisory under a scratch env; `_trend_label` used or deleted.
6. T4.1 `check_convergence._converged_targets`: a CONVERGED/EXECUTED claim in the commit's own diff is a target (01M1RFN3 (1)).
7. T4.2 a committed EXECUTED plan is re-auditable — the `_committed_nonquiet` shape at the three sites wef named (01M1SNCXH6 + 01M1SNJWS + 01M1SNX21 + 01M1SP32G).
8. T4.3 the review branch's QUIET_PASS reads a table row through `_PASS_ROW`, never a prose line (01M1SQZ80).
9. T4.4 `check_review_coverage`: VERDICT accepts `RECORDED — …` rows; Hunt rows cross-checked against the receipt's own Changed list (01M28K3F44 (1), 01M20W9QK).
10. T4.5 both graders grade the RUNNING record's receipt regardless of git change state (01M28K3F44 (2)).
11. T4.6 `check_doc_index` fires on an untracked live doc at creation in the lean tier (01M23D1BF (2)).
12. T4.7 `check_review_hygiene`: hits deduped by (line, what) with an `occurrences` field; `--stop-at-heading`; `--label`; the `.md`-only classes documented in the docstring (01M2AC95X, 01M285X4H).
13. T4.8 `check_plan_tickets`: NOTE to stderr under `--allow-external --json`; `.astro`/`.mjs` in the grounding floor; a Gate line naming a nonexistent file refused; prose in Touches read; rule packs exempt from the READ budget (01M25Q9S0 (1), 01M1V67JR, 01M21804, 01M218KM, 01M1SR1WK (1), 01M1T7WPY).
14. T4.9 `check_ticket_breadth`: a refusal exit on an undated plan dir (01M25Q9S0 (2)).
15. T4.10 `_REDERIVATION_ROW` accepts any Pass-Ledger row carrying the method label, or its message names the narrowing (01M1SR1WK (2)).
16. T4.11 `check_hooks_index`: a fixed required set (01M1VQZJ8 (3)) — routed to fleet if the hooks beat is theirs.
17. T4.12 `review_rubric` FLOOR: a surface-aware profile for hooks/scripts (01M1VQZJ8 (2)).
18. T4.13 the orphaned uncommitted `check_command_corpus.py` edit: message its author, then revert-or-commit (01M22KN7).
19. T4.14 `term-edit.md`: the md5 is taken before the ledger row is written (01M1RFN3 (2)).
20. Suites green; `final_gate.py --check`; commit by private index; the heavy review.

**Behavior Contract.**
- **Given** each grader change, **When** its red-first test runs on a fresh copy with the change reverted, **Then** it fails by name.

## Phase C — The Stop hook (T5) and the governance text (T6)

**Steps.**
1. T5.1 the sixth cause asks "inside ANY window this session held", including a running parent's during a nested child (01M288YHD, 01M25Y93RB, 01M1YB2AK).
2. T5.2 files a RUNNING review-family record names in `--surface` count as covered; seats-in-flight on a running record is an idle turn (01M28YN1F).
3. T5.3 the post-interruption historical-mtime shape verified against 28ca7443 (01M21JAET).
4. T6.1 HARD STOPS: a pathspec commit cannot stage an untracked file and warns on nothing — verify every scoped commit with `git show --numstat HEAD` (01M2803TM iie).
5. T6.2 § Shared repo: a pathspec protects the FILE LIST, never the CONTENT; the private-index recipe for shared-append files (01M1RGRVT, 01M1RHJEY).
6. T6.3 HARD STOPS: the stale-blob guard is blind to a mode change (01M20DXPT).
7. Both CLAUDE.md hunks byte-identical; the hook's suite green; forced sync at Finish; commit; the whole-plan review.

**Behavior Contract.**
- **Given** the two contracts, **When** the substring-equality test runs, **Then** the three new sentences are identical in both.

## Finish

Whole-plan `/fabrik-review` (receipt `docs/development/reviews/2026-09-12-plan-2-mail-triage-command-machinery-review.md`), the D9-shaped docs review, `sync_enforcement_to_projects.py --dry-run` then `--force`, the gate, `Status: EXECUTED`, archive, D-row, push.

## Evidence

Per phase at execution: ≥1 `path:line` and ≥1 fenced command-output block.

## Self-audit

(a) every mail id above resolves in `/opt/fabrik-mail/fabrik/inbox` or `archive` on 2026-09-12; (b) every verdict in § Validation record names the line or command it was read from.

## Residual unknowns

- T10: the ~25 gate, hold and sync mails are listed by id in the tasklist's scratch copy and not addressed here.
- T4.11 and the hooks-index item may be fleet's beat; decided at execution by `docs/reference/agents/`.
