# Mail triage — the command corpus, the review machinery and the feedback relays (every message in the hub inbox — 219 at the 2026-09-12 18:50 snapshot, validated 2026-09-12)

Status: CONVERGED (2026-09-12 — /fabrik-plan-review, ten passes: 22 · 17 · 4 · 3 · 2 · 1 · 3 · 2 · 1 · 0 confirmed; D-243)
Profile: standard
**Owner:** — (infra; the unnamed hub window fabrik-06, session dd3c06d1)
Date: 2026-09-12
Predecessors: `docs/development/plans/archived/2026-09-11-plan-1-review-family-pass3.md` (D-242) · the fabrik-mail inbox `/opt/fabrik-mail/fabrik/inbox` (231 messages at the read-only validation on 2026-09-12; 219 at 18:50 after Phase 0's first acks — the register below is that snapshot; 114 by 21:00 after this session's replies, acks and relays; the register's in-plan column counts the ids a step row or a Phase H list names) · the operator's word 2026-09-12: "check all mails regarding commands and also feedbacks and validate them first" → "record them all in a tasklist, address them all"

## Goal

Every mail about a `/fabrik-*` command, the review machinery (`command_run.py`, the four review graders, the Stop hook, the seat briefs) or a close-out FEEDBACK relay is either FIXED with a red-first grader, MOOT with the ruling named, REPLIED with the commit, or ROUTED to its beat — and every one of the 62 is acked. The tasklist below is the record; each step names the mail ids it closes.

## DONE WHEN

- 0 of the ids named in a step row (Phases 0–G) or in Phase H's acked/moot lists remain in `/opt/fabrik-mail/fabrik/inbox` (`mail.py list` filtered by those ids → 0); the ids ROUTED to fleet stay in the inbox under fleet's filter and are not this plan's to ack.
- Every T2–T6 and T11–T14 item (T7–T9 are ✅ DONE in Phase 0; T15 rides the first bullet) has a commit on `master` naming its mail id(s), or a `MOOT`/`ROUTED` disposition in § Execution notes with the reason.
- Every suite named in § File Scope's tests bullet and in the phase gate steps (Phase A step 23, B step 20, C step 7, D step 6, E step 24, F step 10, G step 5 — each names its suites) is green; `python3 scripts/final_gate.py --check --json` → `"status":"success"`; render → `--check` → `check_command_corpus.py` green after every command-text step.
- The whole-plan `/fabrik-review` receipt `docs/development/reviews/2026-09-12-plan-2-mail-triage-command-machinery-review.md` is CONVERGED.

## Out of Scope

- The 75 register rows that name no step were all closed on 2026-09-12 by an ack, a reply or a relay (closing replies, project-to-project relays, kaizen collections, corrected or retracted filings, quota advisories, this session's own copies); none remains in the inbox. The two ids the pass-1 text listed here as live — `01M1V597C` and `01M1Z0YKQ` — are step rows T13.8 and T13.9.
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
| 01M28K3F44 | fabrik-lib | VERDICT rejects RECORDED; graders blind to an unchanged artifact | PARTLY REFUTED — `:63` accepts `RECORDED — <reason> (` with one of four reason tokens and the opening paren (T2.10 aligns the command text to that grammar, per T4.4); the second half (graders blind to an unchanged artifact) stays OPEN (T4.5) | `check_review_coverage.py:63` |
| 01M285X4H | wef | hygiene drops 3 of 4 classes off `.md` | OPEN (by design, undocumented) | `SURFACE_SUFFIXES`, the `.md` gates at :463/:469 |
| 01M2AC95X | wef | hygiene double-counts, no ledger exclusion, echoes the copy's path | OPEN | own `--claim` sweeps showed the inflated counts |
| 01M215G84 | trade-intelligence | oscillation advisory misreads delta rounds; no seat can confirm an external fact | OPEN | the advisory fired at round 7 of the pass-3 whole-plan review |
| 01M2368XB, 01M236V84, 01M23ESF5 | wef | scoped command names no stamp, no pin | OPEN | `grep -n "pinned\|md5" fabrik-review-scoped.md` → 0 (a `SHA` grep hits once, inside INDISTINGUISHABLE at :27) |
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

## Context Ledger

| Source | What binds | Grounded ref |
|---|---|---|
| `.windsurf/rules/core/10-python.md` (MATCHED) | every grader runs under the hub .venv via uv; the enforcement scripts keep the ASYNC rule-set green | `:21`, `:245` |
| `.windsurf/rules/core/40-documentation.md` (MATCHED) | a CHANGELOG entry per phase (HEAD blob + hunk); INDEX rows for the plan and its receipts; the plan and the fragments keep heading depth; every Evidence and verdict block fenced | `:129`, `:139`, `:240`, `:242` |
| `.windsurf/rules/core/45-testing-strategy.md` (MATCHED) | each Phase's Behavior Contract enumerates the behaviours its steps add, one test each; every grader T3/T4/T5/T12 adds is seen red first | `:19`, `:21` |
| `CLAUDE.md` § Shared repo, § HARD STOPS (FLOOR) | private-index commits of explicit paths, the hunk-level guard at hashing time; the seventh bounded-search shape; config via env only | the shared-tree bullet, the denominator row |

## Constraints Digest

| Verbatim quote | Source | Applies to |
|---|---|---|
| "**`uv`** is the mandated Python package manager. Never use raw `pip`, `pip install`, `poetry`, or `pipenv`." | `.windsurf/rules/core/10-python.md:21` | every grader runs under the hub .venv via uv |
| "Ruff's selected rule-sets MUST include `ASYNC` (blocking IO in async code — machine-enforces" | `.windsurf/rules/core/10-python.md:245` | the enforcement scripts keep the ASYNC rule-set green |
| "**Update when:** Any change to code (`src/`, `scripts/`, `templates/`)" | `.windsurf/rules/core/40-documentation.md:129` | a CHANGELOG entry per phase (HEAD blob + hunk) |
| "**Update when:** Any file added, removed, or moved." | `.windsurf/rules/core/40-documentation.md:139` | INDEX rows for the plan and its receipts |
| "- **No skipped heading levels** — `##` to `###`, never `##` to `####`" | `.windsurf/rules/core/40-documentation.md:240` | the plan and the fragments keep heading depth |
| "- **Fenced code blocks only** — never indented code (AI treats it inconsistently)" | `.windsurf/rules/core/40-documentation.md:242` | every Evidence and verdict block fenced |
| "- **Behavior Contract**: every ticket enumerates its distinct **user-observable behaviors / acceptance criteria** and tests **each one** — one high-va" | `.windsurf/rules/core/45-testing-strategy.md:19` | each Phase's Behavior Contract enumerates the behaviours its steps add, one test each |
| "- **Watched-fail-first** (for tests this change adds or modifies; trivia stays skipped per the Behavior Contract): a non-trivial behavior's test prove" | `.windsurf/rules/core/45-testing-strategy.md:21` | every grader T3/T4/T5/T12 adds is seen red first |
| "=> Mandate: config via env vars only (`os.getenv("KEY", "default")`); **ZERO secrets/constants in code**. Apply the open" | `.windsurf/rules/core/35-security-auth.md:266` | every script this plan edits reads its knobs from the environment, none hardcodes a path or key |

## File Scope (owned paths)

- `commands/_sources/fabrik-review-scoped.md`, `fabrik-review.md`, `fabrik-plan-review.md`, `fabrik-execute-plan.md`, `fabrik-ui-design.md`, `fabrik-ui-design-review.md`, `fabrik-doc-converge.md`; `commands/_fragments/term-edit.md`, `term-coverage.md`, `subagents-core.md`; `commands/_agents/fabrik-reviewer.md`, `commands/_agents/fabrik-researcher.md`; `scripts/review_receipt.py` (T2.15)
- `scripts/command_run.py`; `scripts/enforcement/check_convergence.py`, `check_review_coverage.py`, `check_review_hygiene.py`, `check_plan_tickets.py`, `check_ticket_breadth.py`, `check_doc_index.py`, `check_hooks_index.py`; `scripts/review_rubric.py`; `scripts/final_gate.py`
- `.claude/hooks/final_gate_stop.py`, `.claude/hooks/quota_stop.py`, `.claude/hooks/mail_notify.py`, `.claude/hooks/mcp_watch.py`
- Phases D–G: `scripts/enforcement/check_lint_ratchet.py`, `check_index_md.py`, `_doc_registry.py`, `check_script_headers.py`, `check_decisions_unique.py`, `check_stage_artifacts.py`; `scripts/docs_updater.py`, `scripts/sync_enforcement_to_projects.py`, `scripts/rivals_run.py`, `scripts/doc_reconcile.py`, `scripts/epic_order.py`, `scripts/scratch_sweep.py`, `scripts/mail.py`; `docs/DECISIONS.md:3` (the header line only); `.windsurf/rules/core/58-resilience.md`, `core/57-external-data-sourcing.md`, `ai/20-vision.md`; box-local, outside git: `~/.claude/bin/claude-selfwatch.sh` (DR-backup after the edit)
- `CLAUDE.md`, `templates/governance/CLAUDE.md`, `docs/workflows/FINAL_GATE_WORKFLOW.md`, `docs/reference/command-run-protocol.md`
- tests (covers every glob a phase gate step names — a gate may only name a suite listed here; the list is a superset by one entry no gate step names — `tests/enforcement/test_check_review_hygiene.py`, harmless because the directory entry runs it): `tests/enforcement/` (the directory), `tests/test_doc_reconcile.py`, `tests/test_docs_updater*.py`, `tests/test_scratch_sweep*.py`, `tests/test_quota_stop_hook.py`, `tests/test_selfwatch_check.py`, `tests/test_mail*.py`, `tests/test_final_gate*.py`, `tests/test_stop_hook*.py`, `tests/test_review_receipt.py`, `tests/test_doc_registry.py`, `tests/test_assemble_dispatch_step.py`, `tests/enforcement/test_review_exit_contract.py`, `tests/enforcement/test_check_review_hygiene.py`, `tests/test_check_convergence*.py`, `tests/test_check_review_coverage*.py`, `tests/test_command_run*.py`, `tests/test_agent_definitions.py`
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
17. T2.17 fabrik-plan-review Phase 2: a gate the REVIEW authors ships with its positive control (01M1VDFYH).
18. T2.18 fabrik-review: a mutation-testing brief gets a COPY, and the orchestrator holds its edits while a mutating seat is live (01M25RZC3).
19. T2.19 fabrik-researcher.md fetch-path routing: exa web_fetch drops tables/late sections, the link-rewrite signature (01M1RKFVK).
20. T2.20 subagents-core: a brief naming line numbers pins a commit SHA (01M206NBV (2)).
21. T2.21 the corpus audit for bare-root `grep` verification steps (01M25H4SR (2)) — bounded to the 36 sources, the fragments and the agent definitions (`commands/_sources/*.md`, `commands/_fragments/*.md`, `commands/_agents/*.md` — 0 hits in the 22 fragments and 4 agent definitions today): `command grep -n 'grep -[rR]' <those globs>` listed with the root each step names, a rewrite per hit (the shim bites at ANY root, so a step rooted at `/opt/*` or `--exclude-dir` is in the class too).
22. T2.22 fabrik-execute-plan § Run record: the nesting sentence matches the storage (01M280CV7).
23. Render → `--check` → `check_command_corpus.py` → hygiene; the graders in `tests/test_assemble_dispatch_step.py` / `tests/enforcement/test_review_exit_contract.py` and, for T2.12/T2.19, `tests/test_agent_definitions.py`, and, for T2.15, `tests/test_review_receipt.py` for each new sentence, red first; commit by private index; the scoped review routes up (>5 files) — one heavy round.

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
9. T4.4 `check_review_coverage`: VERDICT (`:63`) already accepts `RECORDED —` with one of four reason tokens (unexecuted · by design · measured · hygiene false positive) and an opening paren — T2.10 aligns the command text to that grammar instead of widening the regex; Hunt rows cross-checked against the receipt's own Changed list (01M28K3F44 (1), 01M20W9QK).
10. T4.5 both graders grade the RUNNING record's receipt regardless of git change state (01M28K3F44 (2)).
11. T4.6 `check_doc_index` fires on an untracked live doc at creation in the lean tier (01M23D1BF (2)).
12. T4.7 `check_review_hygiene`: hits deduped by (line, what) with an `occurrences` field; `--stop-at-heading`; `--label`; the `.md`-only classes documented in the docstring (01M2AC95X, 01M285X4H).
13. T4.8 `check_plan_tickets`: NOTE to stderr under `--allow-external --json`; `.astro`/`.mjs` in the grounding floor; a Gate line naming a nonexistent file refused; prose in Touches read; rule packs exempt from the READ budget (01M25Q9S0 (1), 01M1V67JR, 01M21804, 01M218KM, 01M1SR1WK (1), 01M1T7WPY).
14. T4.9 `check_ticket_breadth`: a refusal exit on an undated plan dir (01M25Q9S0 (2)).
15. T4.10 `_REDERIVATION_ROW` accepts any Pass-Ledger row carrying the method label, or its message names the narrowing (01M1SR1WK (2)).
16. T4.11 `check_hooks_index`: a fixed required set (01M1VQZJ8 (3)) — infra's (`docs/reference/agents/infra.md:15` names `.claude/hooks/`).
17. T4.12 `review_rubric` FLOOR: a surface-aware profile for hooks/scripts (01M1VQZJ8 (2)).
18. T4.13 the orphaned uncommitted `check_command_corpus.py` edit: the disposition is already recorded (35c23bc4 — orphaned residue of a CLOSED plan, not live WIP); this plan messages the closed plan's owner and never reverts or commits a working-tree file it does not own (§ Shared repo) — RECORDED (01M22KN7).
19. T4.14 `term-edit.md`: the md5 is taken before the ledger row is written (01M1RFN3 (2)).
20. Suites green (`tests/test_command_run*.py`, `tests/test_check_convergence*.py`, `tests/test_check_review_coverage*.py`, `tests/enforcement/`); `final_gate.py --check`; commit by private index; the heavy review.

**Behavior Contract.**
- **Given** each grader change, **When** its red-first test runs on a fresh copy with the change reverted, **Then** it fails by name.

## Phase C — The Stop hook (T5) and the governance text (T6)

**Steps.**
1. T5.1 the sixth cause asks "inside ANY window this session held", including a running parent's during a nested child (01M288YHD, 01M25Y93RB, 01M1YB2AK).
2. T5.2 files a RUNNING review-family record names in `--surface` count as covered; seats-in-flight on a running record is an idle turn (01M28YN1F, 01M1VVX03, 01M1VXH6B).
3. T5.3 the post-interruption historical-mtime shape verified against 28ca7443 (01M21JAET).
4. T6.1 HARD STOPS: a pathspec commit cannot stage an untracked file and warns on nothing — verify every scoped commit with `git show --numstat HEAD` (01M2803TM iie).
5. T6.2 § Shared repo: a pathspec protects the FILE LIST, never the CONTENT; the private-index recipe for shared-append files (01M1RGRVT, 01M1RHJEY).
6. T6.3 HARD STOPS: the stale-blob guard is blind to a mode change (01M20DXPT).
7. Both CLAUDE.md hunks byte-identical; the hook's suites green (`tests/test_stop_hook*.py`, `tests/test_final_gate*.py`); forced sync at Finish; commit; the whole-plan review.

**Behavior Contract.**
- **Given** the two contracts, **When** the substring-equality test runs, **Then** the three new sentences are identical in both.

## Phase D — Rules packs (T11): the `.windsurf/rules` findings other agents mailed (validated 2026-09-12)

| Mail | Sender | Pack line | Verdict (grep on 2026-09-12) | Step |
|---|---|---|---|---|
| 01M1SSV9YRQGSJXMKWJVJ2YG11 | youtube | `core/58-resilience.md:581` says `fabrik-lib/alerting/`'s title dedup IS the exactly-once property | OPEN — the phrase is still at :581; the module is a 300 s sliding per-process window with no clear API (their read of `libs/alerting/__init__.py:36-74`) | T11.1 reword row 3: the dedup is a per-process 300 s suppression, not a latch; the "ONE alert, cleared on recovery" contract needs a durable latch the module does not provide |
| 01M25CVK8N2X42BZH40WFP1YCY | iterative_image_editor | `ai/20-vision.md:31,:33` cite `docs/reference/ai-media-generation-provider-map.md` project-relative | OPEN — both cites still relative (grep); the file is hub-only, so every project's Doc Link check reds | T11.2 absolute `/opt/fabrik/docs/reference/…` at both sites; grep the synced corpus for other hub-only `docs/reference/` refs |
| 01M1RHJZ3VTRB6J9BRTE62NTCD | fleet relaying trade-intelligence | `core/57-external-data-sourcing.md` § scraper failure classes — a `wait_for_selector` that matches a 404 page's navigation reports success | OPEN — no `wait_for_selector` line in the pack (grep 0) | T11.3 one rule in the failure-classes section: a render that satisfies its selector but yields zero extracted rows is a FAILURE the consumer checks — the measurable half, not selector advice |
| 01M20K4FK6TKPDF529Q1HQ2N4P | trade-intelligence | the bounded-search rule names no canonical denominator recipe; three seats produced 1,275 / 1,832 / 72,768 for one question | OPEN — no pack or fragment names `.claude/worktrees` (`command grep -rn` over `.windsurf/rules/` + `commands/_fragments/` → 0); across the six roots `commands/`, `.windsurf/`, `CLAUDE.md`, `templates/governance/CLAUDE.md`, `docs/reference/`, `README.md` the string has 9 hits — 2 scratch-sweep clauses, 2 launch texts, 4 descriptions, and ONE exclusion recipe: the `commands/_sources/fabrik-review.md` sentence excluding the tree's stale copies (`.claude/worktrees/**` + `.tmp/**` for a review's own grep; :129 today, re-derived at execution because Phase A edits that file above it) — no CLAUDE.md-level denominator recipe exists | T11.4 a denominator recipe in the HARD-STOP row of BOTH CLAUDE.md files, byte-identical (tracked set + uncommitted siblings; the implied exclusions), that EXTENDS the stale-copies exclusion by an absolute anchor — `/opt/fabrik/commands/_sources/fabrik-review.md`, the sentence excluding `.claude/worktrees/**` and `.tmp/**` (no heading of its own; T11.2's absolute-path shape) — never a second copy, never a line number; cited from `subagents-core.md`'s brief text |
| 01M1S4D78KRM0ZSYDNGTHS9HYQ | fleet relaying site-provisioner | rubric candidate: "write the guard's subject five legitimate ways and count how many the guard still catches" — four instances measured in one day | OPEN — no such line in `review_rubric.py` or core/45/50 (grep 0); the fire rate is measured (4 in a day, 2 repos) | T11.5 decide under FIX DIRECTIVE 5: one rubric mandate or a core/45 sentence; rejecting after measuring is recordable |

**Steps (the gate).** 6. `python3 scripts/enforcement/check_rule_grounding.py --root .` green; every absolute path a T11 edit cites exists (`ls /opt/fabrik/docs/reference/ai-media-generation-provider-map.md /opt/fabrik/commands/_sources/fabrik-review.md` → rc 0, executed 2026-09-12 — `check_citations_resolve.py` scans four `docs/` subtrees only, `SOURCE_GLOBS` at :37-42: specs, plans, reviews, reference — so it grades neither a pack, nor a CLAUDE.md, nor `docs/DECISIONS.md`); `command grep -n` for each new phrase in its own target (the three packs; both CLAUDE.md files for T11.4, byte-identical) → exactly one hit per target; for T11.5 either exactly one hit at its chosen target or a recorded rejection row naming the measured fire rate; `final_gate.py --check --json` success; `sync_enforcement_to_projects.py --dry-run` lists the three packs and `templates/governance/CLAUDE.md`; `python3 -m pytest tests/enforcement/test_rule_grounding.py tests/enforcement/test_check_citations_resolve.py -q` green (the two checks this gate runs, so their graders run with them); `/fabrik-review-scoped` over the phase.

**Behavior Contract.** **Given** the five T11 edits across up to six targets (three packs, both CLAUDE.md files, the rubric or core/45), **When** each target is grepped, **Then** each phrase is present once at its target — or, for T11.5, a rejection row names the measured fire rate — and the fleet sync carries the synced ones (dry-run then force at Finish).

## Phase E — the gate, the enforcement checks, the sync (T12) — validated 2026-09-12 against the tree at 0a1fe8bc

| Step | Mail(s) | Verdict (executed probe) | Fix |
|---|---|---|---|
| T12.1 | 01M1RE497, 01M1VB1NF, 01M28N2CB | OPEN — `check_lint_ratchet.py:53` counts via `sys.executable -m ruff`, `:137` reads the version from bare `ruff`; a version change re-seeds silently and the gate stages the baseline on a docs-only run | version from `sys.executable`; a version change FAILS once and asks for an explicit re-seed; grade against the COMMITTED baseline; the failure text names the offending path and whether it is inside the caller's diff |
| T12.2 | 01M20HW4E | PARTLY REFUTED at HEAD — the flag at `:422` stays unconditional inside `run_mypy_with_recovery`, but its one call site `:918` sits under the `pyproject.toml` guard at `:916` and `:919` reds any non-zero exit (`code == 0`), so an exit 2 is a red row (the 2026-09-08 report was against an older or a project copy); OPEN — `--json` carries no per-check roster (keys: advisory · blocking · failed · failures · passed · skipped · skipped_checks · status · tier · warnings — no `checks`) | emit the per-check roster under `--json`; reply the refuted half with the two line cites |
| T12.3 | 01M20KVDT, 01M2606BZ (2) | OPEN — `:211` `re.search(r"(\d+) skipped")` takes the FIRST match (pytest's collection banner); `deselected` never counted; the semgrep leg keeps the row name on not-installed/unauth/timeout so `_SKIP_MARKERS` miss it | read the summary line (last match); count deselected; rename the semgrep row with the skip marker on every not-run path |
| T12.4 | 01M2606BZ (1) | OPEN — `:1022` runs pytest with `-x`; a truncated run is a green over unreached tests | drop `-x` or add `not_reached` to the JSON |
| T12.5 | 01M28MG90 | OPEN — bandit roots `-r src/` (`:926`) while ruff roots include `scripts/` (`_RUFF_ROOTS`, `:2324`) | bandit over `scripts/` too; the four `# noqa: S324` sites (`check_review_coverage.py:2203/:2205`, `review_receipt.py:94`, `doc_reconcile.py:269`) become `usedforsecurity=False` |
| T12.6 | 01M28NB2R | OPEN — `--check` never runs `ruff format --check`; `.pre-commit-config.yaml` has no ruff hook | a read-only `ruff format --check` leg over the diff under `--check` |
| T12.7 | 01M22XDJ7, 01M1RE497 | OPEN — `get_changed_files()` (`:2250`) feeds the fixers a sibling's unstaged TRACKED modifications | fixers scoped to the staged set + `base..HEAD`; a sibling's unstaged tracked files read-only; `--fix-all` opt-in |
| T12.8 | 01M23CRZZ | OPEN — five measured drifts between `docs/workflows/FINAL_GATE_WORKFLOW.md` and the registry | render the per-check reference from the `run_optional_check` registrations, or a heading↔registration assertion in `check_docs` |
| T12.9 | 01M1S2MYZ, 01M1Z0PEB | OPEN — `docs_updater.py` has no scaffold-template exclusion (grep 0; `check_doc_links.py:113` has it); `--adopt --dry-run` writes and stages (7 `dry_run` reads, none guarding the writes) | port the predicate; every write and every `git add` behind `not dry_run`; never `git add` (opt-in `--stage`); ownership derived, never cycled |
| T12.10 | 01M1VPEGG | OPEN — `check_index_md.py` asserts headings, never file↔row (no `diff-filter`/`name-only`, grep 0) | a staged-scope added-path check over scripts/ tests/ .claude/hooks/ .fabrik/, WARN first with the fire rate measured |
| T12.11 | 01M1VHCH1 | OPEN — `_doc_registry.ALL_TYPES` lacks `office-extension` (13 vs 12); `tests/test_doc_registry.py` is red and nothing runs it | add the type + its PROJECT_DOCS rows; run tests/enforcement + test_doc_registry as the hub's own slice at every gate |
| T12.12 | 01M295S5G, 01M1T1134 | OPEN — `docs/DECISIONS.md:3` says "Append-at-top" while eighteen of the nineteen rows D-223…D-241 (D-238 excepted) sit at the tail; the table itself renders as one (0 non-row lines below the delimiter at :10); `check_decisions_unique.py` is a line regex that blessed brand-identiy-creator's row-above-the-delimiter shape | header → append at the bottom; a structural assert that every `\| D-` row sits BELOW the delimiter (green on today's ledger, red on the reported shape) |
| T12.13 | 01M1RKEZ3 | RECORDED — `check_stage_artifacts.py` grades new transitions only (its own :36-37); the landed-skip blind spot is the same class as T4.2's committed EXECUTED claims | T4.2 carries it (the `_committed_nonquiet` shape) |
| T12.14 | 01M1SNNTS, 01M1V2P02 | OPEN — `check_script_headers.py:14` ("only *staged* scripts are inspected") and `:262` (`git diff --cached --name-only`) inspect STAGED scripts only: empty PASS before `git add`, and a staged DATA/doc file named in a header never fires | symmetrise: if ANY file named in a header is staged, inspect the header; the pre-stage run reads the working tree diff |
| T12.15 | 01M25EG0N | REFUTED — five refusals printed at once on 2026-09-12 (§ Validation record); the `break` at :244 ends the heading-selection loop and :1485 the token parse, neither an early exit | reply + ack |
| T12.16 | 01M206NBV (1) | MOVED — `scripts/repo_lock.py` is not in this tree (fabrik-lib's vendored copy); the "clear" ordering is theirs | reply: the lock check lives in fabrik-lib; the brief-SHA rule → T2.20 |
| T12.17 | 01M1Y86PQ | OPEN — `sync_enforcement_to_projects.py` copies the WORKING TREE (`shutil.copy2` at :1577 via a tmp file and :1684 direct); 48 copies carried an uncommitted edit on 2026-09-07 | copy tracked synced files from the HEAD blob; working tree only for untracked; grader on a tmp project |
| T12.18 | 01M1YSBXG, 01M205HN4, 01M205A16 | DONE — `VENDORED_DIRS` no longer lists `libs/subagents` (RETIRED_VENDORED_DIRS, D-198); the hub copy stays until the 17 importers migrate (D-210) | reply + ack (three) |
| T12.19 | 01M21TGTR, 01M25GEXP, 01M28K3N8 | OPEN — `rivals_run.py:1142-1144` still imports `load_env` from the retired module (fail-open note names the exception, not the missing keys); `doc_reconcile.py:43-48` guards `pick_models`/`run_agents` to None | vendor the standalone `load_env` (SUBAGENTS_ENV_FILE rule) into rivals_run; the note enumerates the absent expected keys; doc_reconcile's fan-out leg → native seats or removed |
| T12.20 | 01M25EGFY, 01M25H4SR | DONE — the grep-shim rule is the bounded-search HARD STOP's seventh shape in both CLAUDE.md files (D-214/D-216, synced fleet-wide); the corpus audit for bare-root grep verification steps → T2.21 | reply + ack |
| T12.21 | 01M22KN7 | RECORDED — the orphaned `check_command_corpus.py` comment edit is still ` M`; its disposition is recorded at 35c23bc4 and a sibling's working-tree file is never reverted or committed by this plan; the plan-close dirty-scope check is a measured backlog row | T4.13 (message the owner) |
| T12.22 | 01M1YQVEF | PARTLY REFUTED — `EPIC-ARTIFACT-SCHEMA.md` is tracked at `docs/orchestrator/mega-epic-breakdown/` (`git ls-files`), so the cite resolves; OPEN — the flat-parser `_LIST_KEYS` constraint is undocumented where a project author reads | document the constraint in the schema doc; the state-contract adoption → backlog row; reply the refuted half |
| T12.23 | 01M23JK2R | OPEN — `scratch_sweep.py --worktrees` calls a worktree dirty ONLY with manifest-owned materialised files (`.worktreeinclude`, synced scripts) `wt-dirty`; the younger-than hint names the flag just passed (reported by wef3; its emitting line not located — `:1012` defines the flag, the `wt-dirty` verdicts sit at :1724-1732) | the dirty check ignores paths the synced manifest owns; the hint half RECORDED until its line is found |

**Steps (the gate).** 24. Every T12 code fix ships with a red-first grader named beside it (tests/enforcement or tests/); `python3 -m pytest tests/enforcement tests/test_doc_registry.py tests/test_final_gate*.py tests/test_review_receipt.py tests/test_doc_reconcile.py tests/test_docs_updater*.py tests/test_scratch_sweep*.py -q` green; `python3 scripts/final_gate.py --check --json` → `"status":"success"`; `sync_enforcement_to_projects.py --dry-run` clean before the ONE forced sync at Finish; one `/fabrik-review` over the phase.

**Behavior Contract.** **Given** a repo whose `.venv` ruff differs from the committed baseline's version, **When** `check_lint_ratchet.py` runs, **Then** it fails ONCE naming the version pair and the path, never re-seeds silently. **Given** pytest output with a collection banner `1 skipped` and a summary `566 skipped, 49 deselected`, **When** `skip_advisory` runs, **Then** it reports 566 skipped and 49 deselected. **Given** a docs-only diff, **When** a bare gate runs, **Then** `.fabrik/lint-baseline.json` is not staged. **Given** a sibling's unstaged tracked modification, **When** the fixers run, **Then** the file is untouched. **Given** a synced file with an uncommitted hub edit, **When** the sync runs into a tmp project, **Then** the copy equals HEAD's blob. **Given** `--adopt --dry-run`, **When** docs_updater runs, **Then** the tree and the index are byte-identical before and after. **Given** `--json`, **When** the gate finishes, **Then** the output carries a per-check roster with one row per registered check. **Given** a suite whose first failure is at position k of n, **When** the pytest leg runs, **Then** the JSON says how many tests were not reached (or `-x` is gone). **Given** a `hashlib.md5()` call with no `usedforsecurity=False` under `scripts/`, **When** the security leg runs, **Then** bandit reports it (the four `# noqa: S324` sites become `usedforsecurity=False` in the same change and stay silent). **Given** a file `ruff format --check` would reformat, **When** `--check` runs, **Then** the gate reds. **Given** a `#### check_*.py` heading in FINAL_GATE_WORKFLOW.md with no registration (or the reverse), **When** the doc check runs, **Then** it fails naming the pair. **Given** a staged add under scripts/ with no INDEX.md row, **When** the INDEX check runs, **Then** it WARNs naming the path. **Given** `SCAFFOLD_TYPES` and `ALL_TYPES`, **When** `tests/test_doc_registry.py` runs, **Then** the sets are equal. **Given** a `| D-` row above the delimiter, **When** `check_decisions_unique.py` runs, **Then** it fails; on today's ledger it passes. **Given** a staged doc named in a script's AFTER-EDIT header, **When** `check_script_headers.py` runs, **Then** it inspects that header. **Given** a worktree dirty only with manifest-owned files, **When** `scratch_sweep.py --worktrees` runs, **Then** the verdict is not `wt-dirty`.

## Phase F — hooks, the hold, the mesh (T13)

| Step | Mail(s) | Verdict | Fix |
|---|---|---|---|
| T13.1 | 01M1S2B0S, 01M1S2DQM, 01M1S2P9D, 01M1SN267, 01M1WD26H | FIXED — `git commit` is admitted under the hold since 20c3b557 (`_GIT_VERB_FLAGS["commit"]` = a POSITIVE flag set, `--file` included); trailers under the hold FIXED per 01M1YR362; this session committed and pushed under the 2026-09-12 hold | reply + ack; the held-subagent parent signal (01M1S2B0S) → T9 backlog row |
| T13.2 | 01M1S6CWX, 01M1VN1D7, 01M1XJ3XT | OPEN — the flock dir `/tmp/claude-sound-locks-$(id -u)` (selfwatch.sh:18) is reapable so duplicate arms pass; watchers have no "my pane is gone" exit; the mesh harness was red at A0a on 2026-09-07 (one run) | lock under a non-reaped dir (`~/.claude/state/`); a transcript-age ceiling backstop; run `claude-mesh-test.sh` once and record the baseline before touching either |
| T13.3 | 01M1VRVWS, 01M1VVNWY, 01M1VVX03, 01M1VXH6B, 01M1VWJWX, 01M1W6SS5, 01M1YB2AK, 01M21JAET, 01M28YN1F, 01M25Y93RB | OPEN — the sixth cause (T5.1–T5.3); plus `_this_sessions_edits` (:716) not holding on a 5.7-day resumed transcript and the block naming no file — reproduced on the hub 2026-09-12 16:2x: this session's sixth cause counted 20 code files last edited 2026-06-04…06-16 (the transcript's pre-compaction history) as uncovered while a `/fabrik-plan-review` record with 55 covered windows was live | T5.1–T5.3 + T5.4: the floor mandatory with a bounded fallback; the block NAMES three files |
| T13.4 | 01M20E1QN | OPEN — the UNPUSHED cause measures `origin/main..HEAD` and says "push YOUR work" — on a shared tree it orders a sibling's commit published | T5.5: fire only on commits this session authored (the record's session id, the Agent-Context trailer) |
| T13.5 | 01M23HB2M, 01M23K7XT | OPEN — `mail_notify.py` and `mcp_watch.py` carry no headless guard (grep FABRIK_HEADLESS → 0); `rivals_run.py:_make_llm` spawns a full-turn `claude -p` | the dispatcher sets `FABRIK_HEADLESS=1`; the two advisory hooks stand down on it; rivals' spawn routed through llm-dispatch with the bounded flags (intel's rivals beat informed) |
| T13.6 | 01M1S5DGF | RECORDED — `isolation: "worktree"` cuts from origin/main (harness) | T9 backlog row |
| T13.7 | 01M280CV7 | FIXED since — records nest (`command_run.py:1836/:1867` build the child envelope with the parent parked in `stack`) | reply + ack |
| T13.8 | 01M1V59MK, 01M1V597C | OPEN — fabrik-lib is sync-EXCLUDED, so the four multi-agent adoption artifacts never reach it (the four artifacts — `.worktreeinclude` (synced from `templates/governance/.worktreeinclude`, manifest :114), the `.gitignore` `.claude/worktrees` line (the generated Fabrik-synced block), the `.claude/settings.json` worktree block and the `rerere.enabled`/`push.autoSetupRemote` git config (the model doc's adoption recipe) — ride the governance sync and the adoption recipe, both infra's: `infra.md:15` names the sync surfaces, `infra.md:9` the box mesh); re-routed from fleet to infra | reply: a one-time hand-vendor of the four artifacts (the recipe in `docs/reference/multi-agent-operating-model.md`), or a line in fabrik-lib's CLAUDE.md stating the deliberate exclusion |
| T13.9 | 01M1Z0YKQ | OPEN — wef2's four migration questions (2026-09-08), unanswered | reply from the model doc + D-196/D-198 (see § Out of Scope) |

**Steps (the gate).** 10. `python3 -m pytest tests/test_stop_hook*.py tests/test_quota_stop_hook.py tests/test_selfwatch_check.py -q` green; `bash ~/.claude/bin/claude-mesh-test.sh | tail -1` recorded before and after T13.2; `final_gate.py --check --json` success; one `/fabrik-review` over the phase (a hook is a heavy surface).

**Behavior Contract.** **Given** a nested child record whose parent started earlier, **When** the Stop hook computes covered windows, **Then** an edit stamped between the two starts is covered. **Given** a resumed transcript with edits before the session floor, **When** the sixth cause runs, **Then** those edits are not counted and the block names up to three of the files it does count. **Given** a commit on the branch authored by another session, **When** the unpushed cause runs, **Then** it does not fire. **Given** `FABRIK_HEADLESS=1` in the environment, **When** `mail_notify.py` or `mcp_watch.py` runs, **Then** it prints nothing and exits 0. **Given** a second arm for the same session id after the lock directory was reaped, **When** the self-watch starts, **Then** it exits at once. **Given** a session whose transcript is older than the ceiling, **When** the standing loop wakes, **Then** the watcher exits.

## Phase G — fabrik-mail and the trailer text (T14)

| Step | Mail(s) | Verdict | Fix |
|---|---|---|---|
| T14.1 | 01M1T129A, 01M1Y0JS1 | PARTLY REFUTED at HEAD — the advisory prints at `mail.py:799-810`, BEFORE `_publish` at `:909` (the comment at :799 records the order as deliberate); OPEN — its text lists the absent keys and the doc, never the rule (`KEY:` or `KEY —`) | the advisory text states the separator rule; reply the refuted half |
| T14.2 | 01M22M5E1 | OPEN — `send` takes the body on STDIN; `--body`/`--subject` exit 2 on stderr and `\| tail` hides it | the argparse error also on STDOUT naming the delivered-path contract; accept `--body-file` |
| T14.3 | 01M25EJZG | OPEN — a third trailer trap (an unindented wrapped value discards the whole block) is in neither CLAUDE.md; `mail.py`'s secret matcher refuses the prescribed check | T6.4 (both contracts: the third trap, a long single-line example, `interpret-trailers --parse` as the verify) + the matcher's allow for the check's own text |
| T14.4 | 01M1RGM1H, 01M1RKG3X | ROUTED fleet — the scaffold's glitchtip_init vendoring and its guards are the scaffolder beat | `mail.py route` to fleet |

**Steps (the gate).** 5. `python3 -m pytest tests/test_mail*.py -q` green; a send with a `## WHAT` heading body on a scratch mailbox (`FABRIK_MAIL_ROOT` to scratch) prints the rule (on stderr, as today at `mail.py:809`) before the delivered path (stdout), checked on a merged `2>&1` capture; `final_gate.py --check --json` success; `/fabrik-review-scoped` over the phase.

**Behavior Contract.** **Given** a finding body whose keys are bare `## WHAT` headings, **When** `send` runs, **Then** the advisory names the separator rule (`KEY:` or `KEY —`) and prints before the delivered path. **Given** `send --body x`, **When** argparse rejects it, **Then** the argparse error stays on stderr and a one-line delivered-path contract is printed on STDOUT, the exit non-zero (T14.2 moves that line to stdout so a `| tail` reader sees it). **Given** a commit body whose Agent-Context wraps unindented, **When** the trailer text's verify line is followed, **Then** `git interpret-trailers --parse` shows the empty block.

## Phase H — the rest of the register (T15): routed, moot, or informational

- Governance text (T6): 01M1RGRVT, 01M1RHJEY, 01M1VS3JP, 01M1VX78Y, 01M1WAKBW, 01M25EWCT, 01M20K2YJ → T6.2 (the private-index recipe with the hunk-level guard AT HASHING TIME; an absorbed hunk's author is READ from the artifact, never inferred); 01M20DXPT → T6.3. Acked when T6 lands.
- MOOT by retirement (D-132 fabrik-lib, D-181/D-182, D-198/D-210): 01M1RRR6D, 01M1RT02K, 01M1RT46K, 01M1SMZ1R, 01M1SAEB1, 01M1SD2JS, 01M1SA7SW, 01M1S923X (the subagents re-vendor thread), 01M1YPZYF (the hub keeps its copy until the 17 importers migrate — D-210) → ack wontfix naming the ruling.
- Routed to fleet (consumer distribution, scaffolding, ops): 01M1RSFQ6 (iyzico replay — the vendored-payments consumer list), 01M1S2MNG, 01M1SAAZA (account/ contract changes), 01M20H4H0, 01M20YBDF (the shared Postgres roles), 01M1RPD62 (the Pages trigger fired — a scaffold rule), 01M1V15GR, 01M1V1EJP (ownership reconcile check — backlog, measure), 01M265PFR, 01M28G6KC, 01M28JW2Y, 01M28KVFX (site-provisioner contract — relayed to site-provisioner).
- The six command-text additions found in this pass are Phase A steps 17–22 (T2.17–T2.22).
- Informational, acked: the four URGENT quota advisories (01M297ZNA, 01M2AB4Z2, 01M2AQXM2, 01M2B0DSM), the feedback relay 01M208XBX (its two verdicts are D-206 and the spec-review fold class, both landed), fleet's notice 01M25E4SR, 01M1Y3G4G (relayed to wef2).

## Coverage Checklist

Rubric over the § File Scope entries (FLOOR core/35, core/25, core/30, 12-factor; MATCHED core/10, core/40, core/45 — `review_rubric.py --changed` over thirteen representative File Scope paths, 2026-09-12), each row adjudicated by the review (CLEAN / FIXED / REFUTED / RECORDED with evidence).

| Class (rubric / standing) | Verdict | Evidence — what was hunted, where |
|---|---|---|
| FLOOR core/35-security-auth (config via env, no secrets) | CLEAN | every File Scope path is a script, a hook, a command source, a pack or a doc; no key, DSN or path literal enters the plan's fixes (pass 1 Opus over Phases A–G; § Constraints Digest row `core/35-security-auth.md:266`) |
| FLOOR core/25-data-postgres | CLEAN | no database surface in File Scope (pass 1 Sonnet, § File Scope) |
| FLOOR core/30-ops (fabrik apply, network, limits) | CLEAN | no service, compose or deploy step; the sync step is `sync_enforcement_to_projects.py` on the hub (Phase E gate step) |
| FLOOR 12-factor | CLEAN | no runtime process, no config set; the hooks and scripts read env knobs only (pass 1 Opus) |
| MATCHED core/10-python (uv runner; ASYNC ruleset; no bare create_task; `datetime.now(UTC)`) | CLEAN | the plan's Python fixes (T3, T4, T5, T12, T13, T14) touch synchronous enforcement scripts and hooks; every gate step runs the suites under the hub `.venv`; the ASYNC ruleset stays selected in `pyproject.toml` (§ Constraints Digest `:21`, `:245`) |
| MATCHED core/40-documentation (heading depth; fenced code; CHANGELOG + INDEX rows on change) | FIXED (pass 1) | the Context Ledger and Constraints Digest were added at round zero; the digest quote at :81 truncated inside a code span (table parity) — fixed at pass 1's residue; every phase names its CHANGELOG hunk and Finish the INDEX rows (§ Constraints Digest `:129`, `:139`, `:240`, `:242`) |
| MATCHED core/45-testing-strategy (one test per behaviour; watched-fail-first) | FIXED (pass 1) | Phases E, F, G carried Fix tables with no Behavior Contract and no gate step — added at pass 1; every T3/T4/T5/T12 grader is named red-first in its phase's gate step (§ Constraints Digest `:19`, `:21`) |
| Standing: scope ↔ phases | FIXED (pass 1) | the title, Goal and DONE WHEN said "62 mails" while Phases D–H address 145 register ids; § File Scope omitted seventeen Phase D–G paths — both rewritten (pass 1 Opus C1/C2/C16, Sonnet C3) |
| Standing: verdict ↔ tree | FIXED (pass 1) | T12.2, T14.1, T12.15, T12.22 refuted or narrowed at HEAD by execution (`final_gate.py:915-918`, `mail.py:799-810/:909`, `git ls-files`, the `break` sites); T12.12's count and the six drifted cites re-derived (pass 1 Opus C4–C13) |
| Standing: register coverage | FIXED (pass 1) | the `in plan` column recomputed by script (145 yes of 219), the 79 step-less rows accounted for — 73 closed on 2026-09-12, 6 disposed in § Out of Scope (pass 1 Sonnet C1/C2, pass 2 re-derivation) |
| Standing: beat routing | FIXED (pass 1) | 01M1V59MK re-routed from fleet to infra (`infra.md:17` names the box mesh) as T13.8; T4.11 declared infra's (`infra.md:15`) (pass 1 Sonnet C5) |
| Standing: shared-tree prohibition | FIXED (pass 1) | T4.13/T12.21 no longer revert or commit a sibling's working-tree file; the disposition at 35c23bc4 is cited instead (pass 1 Opus C18) |

**Rubric output (verbatim, `python scripts/review_rubric.py --changed` over thirteen representative File Scope paths, 2026-09-12):**

```
# REVIEW RUBRIC — inject into EVERY finder prompt (generated by review_rubric.py)
# Honesty (L1): this arms the review — it raises compliance probability, it does not guarantee it.

## FLOOR — always injected, regardless of glob (spec L3)

### core/35-security-auth.md
**The default for ALL new projects, including user-facing SaaS + mobile.** Vendor `fabrik-lib/fastapi-user-auth`: the app issues its own JWTs — **Argon2id** (the vendored argon2-cffi defaults meet OWASP minimums; never Argon2i) + timing-equalized login, atomic refresh-token rotation (`DELETE … RETURNING`), JWT `jti` denylist revocation, and dual-mode tenant-isolation RLS. Supabase is retired as a default (see `agents-fabrik.md § Supabase`); reach for Pattern B only for a project that *already* runs on Supabase Auth.
- Do not use NextAuth.js, Clerk, Auth0, or Firebase Auth.
- ADDITIONAL affordance a project justifies, never the default door.
- project files the fabrik-lib request FIRST, never hand-rolls WebAuthn.
| `chrome-extension` | ✅ **use this** | ⚠️ only via `chrome.identity.launchWebAuthFlow` + the `https://<ext-id>.chromiumapp.org/` redirect the pack already mandates; a bare mailed link lands in a TAB that cannot reach `chrome.storage.session` |
| `desktop-app` | ✅ **use this** | ⚠️ needs a registered custom protocol handler; the token then goes to `safeStorage` (`desktop-app/72-desktop.md`) |
- service MUST be able to say which:
| **Another Fabrik service** (Docker-to-Docker on the `fabrik` network) | `X-Internal-Token` + `internal_auth.py`, `hmac.compare_digest`, 403 on reject | § Internal Service Auth (M2M) below — **never** an inline `APIKeyHeader`, never a per-service key name |
- An approval link opened somewhere the user did not start must never mint a session silently.
- > **Fail-closed invariant (hard, every mode).** `auth.uid()` and `current_tenant_id()` MUST return `NULL` (→ the policy denies) on unset, empty, or malformed claims — wrap the body in `EXCEPTION WHEN OTHERS THEN RETURN NULL`. **Never** raise and never default to a value: an error-open helper turns one bad/empty JWT into a full cross-tenant read. This is the single most security-critical line in the build — verify it explicitly with a no-context probe (`SELECT auth.uid()` → `NULL`).
- The JWT signing secret must be at least 256 bits, generated via `openssl rand -hex 32`, and injected via Pydantic Settings. Never hardcode it.
- **Pin the algorithm in the VERIFIER** — pass an explicit allow-list (`algorithms=["HS256"]`), never let the library dispatch on the token header's `alg`. Header-driven dispatch is the classic confusion attack (an RS256 public key replayed as an HS256 HMAC secret); `alg: none` is rejected unconditionally.
- "Sticky sessions are a violation of twelve-factor and should never be used or relied upon."
- => Mandate: processes are stateless/share-nothing. **STICKY SESSIONS ARE BANNED** (not just file-based sessions). Session state goes to `redis-main` (Redis) with a TTL. Never in-process memory, never on local disk. Any design that assumes "the same user hits the same process" is a violation.
- **Pattern B (legacy / migration-only):** The Supabase client SDK handles token storage. On mobile, wrap with `expo-secure-store` (never AsyncStorage or MMKV for tokens). See `80-mobile.md` § Backend Integration.
- **Both patterns:** Never store JWTs in `localStorage` or `sessionStorage` on web. Never store JWTs in AsyncStorage or MMKV on mobile.
- **Chrome Extension (MV3) specifics:** `chrome.storage.session` defaults to `TRUSTED_CONTEXTS`, so **content scripts cannot read the token** — keep it in the SW / extension-page context and have content scripts fetch it via SW-mediated messaging (`chrome.runtime.sendMessage`), not a direct read. For social login use `chrome.identity.launchWebAuthFlow` with **PKCE** (`code_verifier` via `crypto.subtle`, held in `storage.session`, redirect `https://<ext-id>.chromiumapp.org/`); the **backend** does the code-for-token exchange. **Never a heavy browser auth SDK** (Auth0-SPA-JS, `oidc-client-ts`) — they assume DOM/`localStorage`/iframes and break in the service worker. Pin a manifest `key` so the extension ID (and thus the `chrome-extension://<id>` CORS origin) is stable across machines. Full detail: `chrome-ext/70-chrome-ext.md`.
- **Never rely solely on the framework's request-shaping layer for access control.** CVE-2025-29927 (the `x-middleware-subrequest` bypass) proved COMPLETE middleware bypass via one crafted header; it is long patched upstream, but the rule outlives the patch — current Next.js even RENAMED the file to say so: `middleware.ts` became **`proxy.ts`**, explicitly repositioned as request-shaping, not a security boundary. ⚠️ **On current majors a leftover `middleware.ts` is SILENTLY IGNORED at build** — nonce injection and redirects stop executing with no error; rename it when upgrading.
- `CORSMiddleware` in FastAPI must populate `allow_origins` from environment variables (Pydantic Settings). Never hardcode origins.
- `X-Frame-Options: DENY` — kept as the legacy fallback only; formally obsoleted by `frame-ancestors`, never ship it ALONE
**Never** write inline `APIKeyHeader` / `require_api_key`. **Never** use per-service key names (`SERVICE_API_KEY`, `PROXY_API_KEY`). Scaffold `python-api` auto-emits `internal_auth.py`, `metrics.py` (REQUEST_COUNT / ERROR_COUNT / ACTIVE_JOBS / PROCESSING_COUNT), `/metrics` endpoint (Authelia-bypassed), and `SERVICE_INTERNAL_SECRET_KEY` in `.env.example`.
- => Mandate: config via env vars only (`os.getenv("KEY", "default")`); **ZERO secrets/constants in code**. Apply the open-source litmus test to every change. **BANNED**: grouped/named env config sets (e.g. a `config/production.yml` or a `settings.production` group) — env vars are granular and orthogonal, set per deploy. (The pack already covers secret handling — cross-reference existing secret patterns and extend with config orthogonality.)
- [ ] Mobile tokens stored in `expo-secure-store` — never AsyncStorage or MMKV.
- > **⚠️ Bearer bypass scope — security-critical.** The bypass defaults to `^/api/`, which makes the **entire** `/api/*` surface public (un-2FA'd). If the application authenticates only a **sub-prefix** (e.g. `/api/v1` carries the bearer/internal-token check) while OTHER `/api/*` routes are unauthenticated (legacy / admin / destructive), you **MUST** narrow the bypass with `shape.bearer_bypass_prefix: "^/api/v1"` — otherwise `fabrik apply` exposes those routes to the public internet. **Bypass ONLY the path the app itself authenticates.** Value must start with `^/`; the verifier (`orchestrator/verifier.check_api_bypass`) probes the configured prefix on deploy. When unsure whether a service has un-auth'd `/api/*` routes, ask the app owner before relying on the `^/api/` default.

### core/25-data-postgres.md
| Vector search | pgvector on `postgres-main` + `fabrik-lib/rag` — ⚠️ the extension is NOT currently installed there (probed 2026-09-01: `postgres:16-alpine`, `plpgsql` only); a project needing vectors REQUESTS the fleet infra change first, never assumes it | same `postgres-main` DSN |
**"Own database" means a DATABASE on `postgres-main`, never a database SERVER.** Per-project and per-tenant isolation is a separate database (its own name, its own role) on the shared container — isolation, quota and backup are all satisfied at that grain. A dedicated Postgres instance is a decision, not a default: it needs its own `docs/DECISIONS.md` row naming what the shared server cannot serve (web-ecommerce-factory 01M1Q8X9, 2026-09-05: "one DB per store" read naively as one server per customer).
- Use Pydantic `BaseSettings` (per `10-python.md` § Config Loading) — never raw `os.getenv` **for an APPLICATION's settings surface**:
- ⚠️ **Scope, stated here because this LINE is what `review_rubric.py` injects — without its section.** The rubric FLOOR-injects this mandate *and* `35-security-auth`'s "config via env vars only (`os.getenv("KEY", "default")`)" into every finder prompt on every review, so a finder reading both literally has two rules it cannot both satisfy, and files a false positive on whichever it applies. The carve-out: `BaseSettings` governs a SERVICE's config surface (a `Settings` object, DB/Redis DSNs, secrets). A **vendored fabrik-lib module** has no settings object by design — it reads its own knobs with bare `os.getenv("KEY", "default")`, which is `35-security-auth`'s mandate being satisfied, not this … (wrapped further — read the pack)
- Never blindly trust `--autogenerate`. Always review `upgrade()` and `downgrade()` for unintended column drops, rename misinterpretations, and ENUM alterations before committing.
- > **Older pythons only** (services pinned below stdlib-uuid7 — which today includes SCAFFOLDED services: the scaffold still emits an older interpreter and ships `uuid-utils`; alignment tracked in the backlog): import `uuid7` from `uuid_utils.compat`, never `uuid_utils.uuid7()` directly — the latter returns `uuid_utils.UUID`, which asyncpg rejects (not a stdlib `uuid.UUID`). **DB-side:** newer PostgreSQL majors ship native `uuidv7()` (probe: `SELECT uuidv7()`); prefer `DEFAULT uuidv7()` at schema level where it exists. `postgres-main` currently runs major <!--v:postgres_major-->16<!--/v-->, which predates it — generate app-side on the fleet.
- Foreign keys must declare `ON DELETE` behaviour explicitly — `CASCADE` if children cannot exist without the parent, `RESTRICT` to protect audit trails. Never rely on the implicit default.
- This section owns the **canonical** engine, session, and `get_db`. `10-python.md` imports from here — never redefines its own.
- Database `AsyncSession` must be scoped to the route handler via `Depends()`. Never open sessions or transactions in global middleware — this holds connections during serialisation and I/O, exhausting the pool.
**BANNED as a server-side backing service** (dev, test, and prod alike):
**⚠️ SCOPE — this ban is about BACKING SERVICES, not client-local storage.** It does **NOT** apply to:
- **`desktop-app`** — SQLite is the **mandated** engine there (`desktop-app/72-desktop.md` § Local Persistence: `better-sqlite3` + SQLCipher; *"Production builds MUST encrypt the local SQLite file"*).
**12-Factor IV (Backing Services) — generalised:** swapping ANY attached backing service (DB, cache, object storage) is a **config change, never a code change**. The handle lives in `DATABASE_URL` / `REDIS_URL` / storage env — the code *reads* it, the code does not *decide* it. Never `if ENV == "prod":` branching to pick a host. (See § PostgreSQL Host Selection, which already mandates this for the DB.)
- [ ] All primary keys use UUIDv7 — stdlib `uuid.uuid7` on current Python (older pythons: `uuid_utils.compat.uuid7`, never direct `uuid_utils.uuid7()`); no `uuid4()`.

### core/30-ops.md
- the pinned release leaves full security support, never per-pack.
- All services deploy via `fabrik apply` (SSH + Docker Compose) on the `fabrik` network. Traefik routes external traffic — services do NOT bind host ports.
- **No `ports:` section.** All external traffic routes through Traefik. Never bind host ports. See Docker Port Security below. **12‑Factor VII (Port binding):** "the app is self‑contained and exports HTTP by binding to a port; it does not rely on runtime injection of a webserver" — which is exactly WHY no host `ports:`.
- **`container_name: <name>` is mandatory.** Same `_validate_compose()` gate refuses any service without it. Stable names are required so Gatus endpoints, inter-service URLs, and `docker exec`/`docker inspect` keys don't drift per redeploy. Use the bare service name (`browserless`, `gotenberg`, `meilisearch`, `glitchtip-web`, `site-provisioner`, etc.) — never UUID-suffixed names.
- gets one (ruling D-052) — see `core/60-watchdog.md`. Do not author a `watchdog: { enabled: false }` opt-out; if a project genuinely cannot host the sidecar, that is a ruling to obtain, not a default to flip.
- path before the flag goes in the spec, and assert target health (`/api/v1/targets` → `up`), never a bare `curl` of a path you assumed.
- VOLUME gets a plan pointed at a directory that never exists — a paper backup that reads green and archives nothing. *Measured: `/opt/zitadel/data` is absent while the `zitadel-data` plan points at it.* If the data is a volume, say so in the spec comment and rely on the global `docker-volumes` plan; never let a service-named plan be mistaken for the protection.
- health-enabled service can NEVER pass `up -d --wait` on a fresh database, and the deploy hangs to timeout. *Measured: trytond bakes an init script but sets no `command:`, and its base entrypoint is a bare `exec "$@"`.* An init the deploy cannot perform itself is a runbook step the plan MUST own.
- `fabrik redeploy <app>` SSHes to the VPS and runs `git pull` + `docker compose up -d --wait` against the **GitHub remote**, NOT the local `/opt/<app>` clone. Skipping `git push` redeploys the previous remote commit — the VPS never sees local changes.
**Mandate:** build → release → run are strictly separated. Releases are IMMUTABLE; the git SHA is the release ID. NEVER hot‑patch a running container (no `docker exec` to edit code/config in place, no in‑place code mutation on the VPS). Any change = a new build + a new release via `fabrik apply` / `fabrik redeploy`.
- Runtime database migrations that modify the app container (migrations MUST be run as separate deploy‑time steps)
**Place a service next to its data.** A spoke-hosted service reaches `postgres-main`/`redis-main` over the WireGuard mesh, and that hop is cross-Atlantic (Coventry ↔ LA) on EVERY query — a per-request chatty service pays it hundreds of times per page. So a DB-chatty service targets vps1; a spoke earns a service whose data traffic is light, batched or cached; a service PINNED to a spoke by hardware (GPU) batches or caches its data access — the data never moves off vps1. Measure before choosing (`ping 10.99.0.1` from the spoke, and the request's query count), never assume — the correctness rule ("container DNS, never localhost") says nothing about latency (web-ecommerce-factory 01M1Q8X9, 2026-09-05).
**Mandate:** WSL dev and the VPS run the SAME backing services (PostgreSQL + Redis), same major version. NEVER substitute a different backing service in dev (no SQLite standing in for Postgres, no in‑memory dict standing in for Redis). The same code must run unmodified in both environments.
- WSL runs PostgreSQL + Redis at the SAME MAJOR as the VPS containers — probe the live truth, never copy a tag from a doc: `ssh vps "sudo docker inspect postgres-main redis-main --format '{{.Config.Image}}'"` (2026-09-01: `postgres:16-alpine` · `redis:7-alpine` — upstream official images, outside OUR-image Alpine ban per § Banned Patterns)
**Invariant:** Never use `ports:` in compose.yaml to expose internal services to the host. All external traffic must go through Traefik.
**Health endpoints (`/health`, `/healthz`, `/metrics`, `/api/health`) bypass Authelia on all services** — required for Gatus and Prometheus monitoring. The bypass is **resource-based, not domain-bound** — applies on every domain routed through Authelia (hub direct + spokes via `authelia-vps1@file` middleware). Never protect these paths.
**CRITICAL:** Use `web`/`websecure` in Traefik labels — never `http`/`https` (those entrypoints do not exist). The scaffolder emits the correct entrypoint names; if you hand-write labels, match these exactly.
**Mandate:** migrations and admin tasks run as a ONE‑OFF process against the DEPLOYED image + env — identical environment to regular processes. NEVER run admin tasks from a laptop against prod, NEVER via `docker exec` into a live container, and **ABSOLUTELY NEVER auto-run migrations from app startup/`lifespan`** (concurrent replicas race the Alembic version table → wedged deploy).
- > sees a file that looks exactly like a migration step, and ships a deploy where migrations never run —
- > the rule producing the very defect it exists to prevent. Do not re-add either without a `path:line` in
**Processes are share-nothing:** any state shared across requests MUST go to Redis (`redis-main`) with a TTL. A project using Redis for sessions MUST declare `shape.needs_cache: true` in `specs/services/<id>.yaml`, or `fabrik apply` skips the Redis registrar and the deploy is silently broken.
- "A twelve-factor app never relies on implicit existence of system-wide packages"
**Mandate:** any binary the app shells out to (ffmpeg, yt-dlp, poppler, tesseract…) MUST be `apt-get install`-ed in the Dockerfile, with a `shutil.which()` startup probe that fails fast. **The pinned base image is the version boundary** — exact `=version` apt pins are banned: they break on every Debian point release as old debs leave the mirrors (the "works then mysteriously breaks" class this section exists to prevent); the codename pin + image digest give the reproducibility. Never assume `curl`/ImageMagick/ffmpeg exist in the image — they don't by default.

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

### core/10-python.md  (hit: .claude/hooks/final_gate_stop.py, .claude/hooks/quota_stop.py, scripts/command_run.py)
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
- Ruff's selected rule-sets MUST include `ASYNC` (blocking IO in async code — machine-enforces this pack's hardest-to-review rule), `B` (bugbear) and `S` (bandit) alongside the defaults; configured in `pyproject.toml`, emitted by the scaffolder.
- Production services run via `uvicorn` CLI in the Dockerfile, not `uvicorn.run()` in code. Base image is always the pinned Debian `-slim` variant on `linux/amd64` (the variant is pinned fleet-wide in `30-ops.md` § Container Base Images — change it THERE, never per-repo). Never use Alpine — musllinux wheels exist now (PEP 656) but coverage is still partial, source builds are dramatically slower, and musl's allocator/stack defaults degrade CPython; the trade never pays on this fleet.
- `uvicorn.run()` is for local development only. Never ship it in production code.
- a fleet scaling decision (more containers), never a per-app flag.
**BANNED: grouped/named env config sets.** 12F is explicit — *"env vars are granular controls, each fully orthogonal to other env vars"* — so a `config/production.yml`, a `settings.production` group, or a `config/{dev,staging,prod}.yaml` tree is a violation. Env vars are granular and set **per deploy**, never batched into a named "environment".
**BANNED:** `logging.FileHandler`, `logging.handlers.RotatingFileHandler`, `TimedRotatingFileHandler`, `loguru` file sinks, any `*.log` file write, any in-app log rotation/retention/cleanup. The app never decides where logs are stored or routed — Docker → Promtail → Loki does. Full rule: `55-observability.md` § Logs.
**Factor XII — Admin processes. NEVER migrate from app startup.**
**BANNED: `alembic upgrade head` in FastAPI's `lifespan`, in an `@app.on_event("startup")`, or as an import side-effect.** With more than one replica (or a restart storm) two containers run `upgrade head` **concurrently** → they race the Alembic version table → duplicate DDL → **wedged deploy**. Migrations are a **one-off admin process against the deployed release**: `docker compose run --rm <svc> alembic upgrade head` (see `30-ops.md` § Release & Admin Processes).

### core/40-documentation.md  (hit: .windsurf/rules/core/58-resilience.md, CLAUDE.md, commands/_agents/fabrik-reviewer.md)
- > **⚠️ `docs/OPERATIONS.md` + `docs/DEPLOYMENT.md` are FLEET-AI INTERFACES, not just docs (D-065).**
- **Tier-1 (author → verify → converge; the author leg is NATIVE while the pool is OFF, D-181 — `scripts/doc_reconcile.py`'s pool author cannot dispatch):** for each **mechanically-detectable** doc whose Doc-Sync trigger fired (`docs/QUICKSTART.md` · `docs/CONFIGURATION.md` · `docs/data-contract.md` · `docs/SERVICES.md` · `docs/OPERATIONS.md` — the reliable-signal subset), `scripts/doc_reconcile.py` dispatches a cheap OpenRouter-pool author (`libs.subagents`, `pick_models("docs")`) to emit a **minimal structured patch**, **verifies it before applying** (a symbol cross-check catches invented endpoints; the orchestrator injects a higher-assurance native-Claude verify), and loops to a zero-edit round. Runs per phase in `/fabrik-execute-plan`; never blocks (fail-safe). The other docs (CHANGELOG, INDEX, FEATURES, RESILIENCE, PORTS, the READMEs, `db/schema.sql`, …) have no reliable mechanical content-signal → they rely on the touch-on-change backstop below + your own edit (force-update, not force-correct).
- The SSOT is the type-aware registry (`scripts/enforcement/_doc_registry.py::PROJECT_DOCS`) — this table is its project-facing rendering, kept in step, never a second truth. `/fabrik-plan-after-chat` (the plan set's spine + tickets — the ticket-format authority) injects these rows per ticket as its `Docs:` line.
- Standalone work (not plan execution) → `Agent-Role: primary`. Trailers go below a blank line, above `Co-Authored-By`. ⚠️ The trailer block must be its OWN paragraph with NO blank line inside it: git parses only the LAST paragraph, and only if it is all-trailers. A blank line before `Co-Authored-By:` demotes everything above it to prose; so does a prose line glued to the top of the block. Measured 2026-08-15: 200 of the last 200 hub commits carried `Agent-Role:` and only 10 parsed, because the old example here shipped the blank line.
- **⚠️ Link it or it is decoration.** *Measured:* requests for files that do NOT exist came ~zero from AI bots — agents never go looking. It follows (inference, not measurement) that a file only gets read when something points at it: reference it from the docs index or README.
- ⚠️ **In THIS repo `llms.txt` is GENERATED** (`scripts/generate_capability_index.py`, refreshed daily) — never hand-edit it; change the generator. A project writing one by hand owns it.
- either way. Cheap and reversible — never at the expense of `OPERATIONS.md`/`DEPLOYMENT.md`, which are the load-bearing agent interfaces (D-065).
- **No skipped heading levels** — `##` to `###`, never `##` to `####`
- **Fenced code blocks only** — never indented code (AI treats it inconsistently)

### core/45-testing-strategy.md  (hit: tests/enforcement/test_review_exit_contract.py)
- **Behavior Contract**: every ticket enumerates its distinct **user-observable behaviors / acceptance criteria** and tests **each one** — one high-value integration/E2E test per behavior, risk-ordered, TDD for the risky ones. Skip trivia (getters / framework glue / config): **lean-but-complete, NOT 100%-line-coverage dogma**. Do not chase line coverage — ensure every behavior has a test that would fail if that behavior regressed. (Cheap pool subagents can author the per-behavior tests — the suggest→curate→author→fix workflow in `62-using-subagents.md` § Dispatch policy + `~/.claude/commands/fabrik-review.md`.)
- **No cosmetic assertions**: never assert against CSS classes, Tailwind utility strings, pixel measurements, or snapshot hashes. Assert application state and user-visible outcomes only.
- **Watched-fail-first** (for tests this change adds or modifies; trivia stays skipped per the Behavior Contract): a non-trivial behavior's test proves something only if it has been SEEN RED — either write it first and watch it fail, or (after the fact) neuter the fix/feature, prove the test goes red, then RESTORE and re-run to green. The neutered state is never staged, committed, or left in the tree. A green test never seen red is unverified — a suite can pass with its guard deleted.
- **Run tests**: `uv run pytest tests/` (never bare `pytest` — Fabrik uses `uv`) — **when the project has a `pyproject.toml`/`uv.lock`**. A `requirements.txt`-only project (no manifest) runs `.venv/bin/python -m pytest tests/` — the manifest clause chooses the RUNNER, it never disarms the mandate to run the suite (web-ecommerce-factory 01M1QEY5, 2026-09-05: the clause read as "does not apply here"). ⚠️ **Gate this on the manifest, because this line is FLOOR-injected into finder prompts and a vendored fabrik-lib MODULE has neither by design**: the module recipe ships `requirements.txt` (`fabrik-lib/README.md` § Creating a Reference Implementation), so `uv run` cannot resolve it and `python3 -m pytest` is the only thing that works. Telling a finder the sole working … (wrapped further — read the pack)
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
| A test THIS change adds/modifies that was never seen red (no fail-first, no red-on-revert proof) | Watch it fail first, or neuter the change → prove red → restore → re-run green |
- [ ] Destructive DB tests call `require_throwaway(TEST_DATABASE_URL)` before connecting — never point them at a dev/shared DB.

# promote-to-check_*: 81 injected mandate(s) look deterministically greppable — their backtick literals, one line each (the full mandates are ABOVE, not repeated: re-emitting ~20 FLOOR lines verbatim doubled the rubric and got it skimmed — web-ecommerce-factory 01M1QEY5, 2026-09-05)
- `fabrik-lib/fastapi-user-auth` `DELETE … RETURNING` `jti` `agents-fabrik.md § Supabase`
- `chrome-extension` `chrome.identity.launchWebAuthFlow` `https://<ext-id>.chromiumapp.org/` `chrome.storage.session`
- `desktop-app` `safeStorage` `desktop-app/72-desktop.md`
- `fabrik` `X-Internal-Token` `internal_auth.py` `hmac.compare_digest` `APIKeyHeader`
- `auth.uid()` `current_tenant_id()` `NULL` `EXCEPTION WHEN OTHERS THEN RETURN NULL` `SELECT auth.uid()` `NULL`
- `openssl rand -hex 32`
- `algorithms=["HS256"]` `alg` `alg: none`
- `redis-main`
- `expo-secure-store` `80-mobile.md`
- `localStorage` `sessionStorage`
- `chrome.storage.session` `TRUSTED_CONTEXTS` `chrome.runtime.sendMessage` `chrome.identity.launchWebAuthFlow` `code_verifier` `crypto.subtle` `storage.session`
- `x-middleware-subrequest` `middleware.ts` `proxy.ts` `middleware.ts`
- `CORSMiddleware` `allow_origins`
- `X-Frame-Options: DENY` `frame-ancestors`
- `APIKeyHeader` `require_api_key` `SERVICE_API_KEY` `PROXY_API_KEY` `python-api` `internal_auth.py` `metrics.py` `/metrics` `SERVICE_INTERNAL_SECRET_KEY`
- `os.getenv("KEY", "default")` `config/production.yml` `settings.production`
- `expo-secure-store`
- `^/api/` `/api/*` `/api/v1` `/api/*` `shape.bearer_bypass_prefix: "^/api/v1"` `fabrik apply` `^/` `orchestrator/verifier.check_api_bypass` `/api/*` `^/api/`
- `postgres-main` `fabrik-lib/rag` `postgres:16-alpine` `plpgsql` `postgres-main`
- `postgres-main` `docs/DECISIONS.md`
```


## Pass Ledger

| Pass | seats · axes re-checked (claims · gates · interfaces · completeness) | counters | method | plan md5 (start → end) |
|-----:|---|---|---|---|
| Pass 0 | the orchestrator's own flip-gate probe on the flipped scratch copy | found: 2, new: 2, confirmed: 2, fixed: 2, unexecuted: 0 | round zero: `check_rule_grounding` (no Constraints Digest) and `check_plan_quality` (no Context Ledger) executed on the flipped copy before any seat; both sections written from `review_rubric.py`'s MATCHED set with each quote re-read at its line; the floor quote re-taken verbatim from `core/35-security-auth.md:266` | 8ac08720c0d9 → (f4c4a231) |
| Pass 1 | opus×1 (the step tables of Phases A–G and § Validation record: every cite re-read at f0c0cff2, 41 probes executed) + sonnet×1 (header, Goal, DONE WHEN, Out of Scope, Phase 0 shas, Phase H, Finish, the register: coverage script, 8-id mailbox sample, the fleet charter) · the partition | found: 25, new: 25, confirmed: 22, fixed: 22, unexecuted: 0, edits: 164/143 lines | citation + execution — every candidate re-executed by the orchestrator before the edit (mypy guard :915-918; the advisory :799-810 vs `_publish` :909; the `break` sites; `git ls-files` for the schema doc; the ledger's delimiter and tail; `grep -n` for six symbols); the register column recomputed by script with an 8-character id match; `· mirrors: 4 read` (DONE WHEN, Out of Scope, Residual unknowns, the register note) | 8ac08720c0d9 → 50d6ff710142 |
| Pass 2 | opus×1 (the rewritten rule content: DONE WHEN, File Scope, the E/F/G gates and contracts, the rewritten verdict cells, the moved Phase A steps, the re-derived cites) + sonnet×1 (the register column, § Out of Scope, § Residual unknowns, Phase H's lists) (fresh) · delta over the pass-1 hunks (332 changed lines > 20 → the partition) | found: 17, new: 17, confirmed: 17, fixed: 17, unexecuted: 0, edits: 25/25 lines | method: re-derivation — delta over the pass-1 hunks; the register arithmetic re-derived by script with the Out of Scope bullet excluded from the "names a step" body (75 step-less rows, all archived); `sed -n` on final_gate.py :422/:916/:918/:919, check_review_coverage.py :63, infra.md :9/:15, mail.py :809; `grep -c '^| T13\.'` → 9 (the gate step renumbered 10; T13.7 restored to id order); `· mirrors: 5 read` (Predecessors, DONE WHEN, Out of Scope, Residual unknowns, the register note) | 50d6ff710142 → 85a4c7609dea |
| Pass 3 | opus×1 (the rewritten rule content) + sonnet×1 (the register arithmetic, § Out of Scope, § Residual unknowns) (fresh; the first dispatch of both died on API timeouts before reading and was re-dispatched) · delta over the pass-2 hunks (50 changed lines > 20 → the partition) | found: 10, new: 10, confirmed: 4, fixed: 10, unexecuted: 0, edits: 12/10 lines | method: re-derivation — delta over the pass-2 hunks; `ls` of the two test globs (0 files under tests/enforcement/), `grep -n 'check_review_coverage.py:62'` (the validation-record mirror), the B/C gate steps read (no suite named), `command grep -rn S324 scripts/` → 4; the Sonnet seat re-derived 75 step-less ids all archived and the column under both definitions (0 mismatches); `· mirrors: 3 read` (DONE WHEN, File Scope, the validation record) | 50d6ff710142 → 85a4c7609dea |
| Pass 4 | opus×1 (the rewritten rule content) + sonnet×1 (the mirror sweep, the seven gate numbers, the register unchanged) (fresh) · delta over the pass-3 hunks (22 changed lines > 20 → the partition) | found: 6, new: 6, confirmed: 3, fixed: 5, unexecuted: 0, edits: 5/5 lines | method: re-derivation — delta over the pass-3 hunks; the Phase D gate read (no suite), `command grep -rn S324 scripts/` → 4 with two files outside tests/enforcement's reach, `ls commands/_fragments/*.md commands/_agents/*.md | wc -l` → 22 + 4; the Sonnet seat swept six rewritten facts for stale mirrors (0) and re-derived the seven gate numbers; `· mirrors: 6 read` | 85a4c7609dea → 63c756e4c8dc |
| Pass 5 | opus×1 (fresh) · delta over the pass-4 hunks (10 changed lines ≤ 20 → one seat, D5) | found: 6, new: 6, confirmed: 2, fixed: 4, unexecuted: 0, edits: 4/4 + 1/1 lines | method: re-derivation — `command grep -rln '.claude/worktrees' --include='*.md' .` (the recipe at `fabrik-review.md:129` the "never" quantifier missed), the tests bullet vs the gate steps' globs (three missing → the bullet became the union by construction, D10 rule 3 after two residue passes); `· mirrors: 4 read` | 63c756e4c8dc → 0dead3b7d9a6 |
| Pass 6 | opus×1 (fresh) · delta over the pass-5 hunks (8 changed lines ≤ 20 → one seat) | found: 5, new: 5, confirmed: 1, fixed: 5, unexecuted: 0, edits: 4/4 lines | method: re-derivation — `wc -l commands/_sources/fabrik-review.md` + the class-ledger lines above :129 (a line-number cite into a file Phase A edits → cited by anchor); the six-root grep for `.claude/worktrees` (9 hits, 1 recipe); Phase C's byte-identical rule vs a hub-only cite (the templates copy takes the recipe without the cite); `· mirrors: 3 read` | 0dead3b7d9a6 → 728b67d0b4d4 |
| Pass 7 | opus×1 (fresh) · delta over the pass-6 hunks (8 changed lines ≤ 20 → one seat) | found: 5, new: 5, confirmed: 3, fixed: 5, unexecuted: 0, edits: 6/6 lines | method: re-derivation — `grep -o … \| wc -l` (the duplicated path a `grep -c` cannot see), T11.2's row re-read (absolute path, not omission), Phase D's gate vs T11's five targets; the T11.4 cell rewritten as a class — both CLAUDE.md files byte-identical with an absolute anchor; the residue chain of passes 5–7 lived in that one cell; `· mirrors: 4 read` | 728b67d0b4d4 → 712972a61f7c |
| Pass 8 | opus×1 (fresh) · delta over the pass-7 hunks (12 changed lines ≤ 20 → one seat) | found: 4, new: 4, confirmed: 2, fixed: 4, unexecuted: 0, edits: 4/4 lines | method: re-derivation — `check_citations_resolve.py` SOURCE_GLOBS :37-42 read (docs/** only → the gate asserts its absolute cites by `test -f`); T11.5's Fix cell vs the gate's "exactly one hit" (the rejection branch restored); `grep -n '^#'` over fabrik-review.md (no stale-copies heading → anchored by the sentence); `· mirrors: 3 read` | 712972a61f7c → 2b3d0c609ba3 |
| Pass 9 | opus×1 (fresh) · delta over the pass-8 hunks (8 changed lines ≤ 20 → one seat) | found: 3, new: 3, confirmed: 1, fixed: 3, unexecuted: 0, edits: 2/2 + 1/1 lines | method: re-derivation — the seat EXECUTED `test -f a b` (rc 2, "binary operator expected"): my own remedy written without running it; replaced by an executed `ls` (rc 0) and the pytest leg executed (16 passed) before the pin — the filename residue (`test_check_rule_grounding` vs `test_rule_grounding`) caught by that execution; `· mirrors: 2 read` | 2b3d0c609ba3 → b6ca452338ba |
| Pass 10 | opus×1 (fresh; the first dispatch died on an API timeout and was re-dispatched) · delta over the pass-9 hunks (4 changed lines ≤ 20 → one seat) | found: 1, new: 1, confirmed: 0, fixed: 0, unexecuted: 0 | method: re-derivation — `ls` of the two absolute paths (rc 0), `SOURCE_GLOBS` :37-42 read, the pytest leg executed (16 passed), `final_gate.py:1313/:1324` (both checks registered warn_only); the one RECORDED item (the Given's "five edits across six targets" on the rejection branch) fixed at the flip as "up to six"; `· mirrors: 1 read` | b6ca452338ba → 946f2710f2d1 |

## Execution notes

- **Phase A — DONE 2026-09-12.** b9981f45 (the 22 sentences + four graders; T2.10 and T2.16 closed as citations), 11629bba (review_receipt.py's executable bit — the private-index recipe had written 100644: the mode now comes from `git ls-files -s` per path), then the heavy review's fixes 56278d88 · 0a0afb7e · 219ebe6a (a rule added to two fragments rendered twice; its dedup lost it in three commands whose fragment sets are not nested; the rule now sits in both termination fragments and the scoped command, every one of the 22 consumers once, graded on the render by a guard that enumerates consumers by their marker sentence). Receipt `docs/development/reviews/2026-09-12-plan-2-mail-triage-phase-A-review.md` CONVERGED (5 · 2 · 2 · 0). Five RECORDED residuals to the backlog at Finish: `review_receipt.py --init` exits 0 on an empty surface; `check_review_coverage.check_file` passes a zero-byte receipt; the orchestrator/seat twin of the mutation-timeout rule names no split; the lost-rule guard's raw-vs-stripped marker asymmetry; pytest's repr truncating the lost list.

## Finish

Whole-plan `/fabrik-review` (receipt `docs/development/reviews/2026-09-12-plan-2-mail-triage-command-machinery-review.md`), the D9-shaped docs review, `sync_enforcement_to_projects.py --dry-run` then `--force`, the gate, `Status: EXECUTED`, archive, D-row, push.

## Evidence

Per phase at execution: ≥1 `path:line` and ≥1 fenced command-output block. The plan review's own evidence (2026-09-12, the tree at f9355e3d):

```
$ python3 scripts/enforcement/check_review_hygiene.py --surface docs/development/plans/2026-09-12-plan-2-mail-triage-command-machinery.md
hygiene: 0 hit(s) over 1 file(s), 0 rows ungraded
$ python3 scripts/enforcement/check_citations_resolve.py --changed docs/development/plans/2026-09-12-plan-2-mail-triage-command-machinery.md
✓ citations resolve — 13 `path:line` citation(s) across 3 docs all land
$ python3 scripts/enforcement/check_rule_grounding.py --root <flipped scratch copy>
rule grounding: 1 CONVERGED in-window plan(s) examined, 0 with findings (artifact-only; reading quality is the review's)
$ python3 -c "... check_plan_quality.check_file(<flipped scratch copy>)"
plan_quality findings: 0
$ ls /opt/fabrik/docs/reference/ai-media-generation-provider-map.md /opt/fabrik/commands/_sources/fabrik-review.md; echo rc=$?
/opt/fabrik/commands/_sources/fabrik-review.md
/opt/fabrik/docs/reference/ai-media-generation-provider-map.md
rc=0
$ timeout 300 python3 -m pytest tests/enforcement/test_rule_grounding.py tests/enforcement/test_check_citations_resolve.py -q -p no:cacheprovider
16 passed in 0.33s
$ python3 - <<'EOF'   # the register's in-plan column re-derived (pass 3, the Sonnet seat; repeated at pass 9)
register ids 219 · step-less (8-char prefix absent from the plan body without the § Out of Scope bullet) 75 · archived 75 · in inbox 0
in-plan yes 144 · no 75
EOF
$ ls /opt/fabrik-mail/fabrik/inbox/*.md | wc -l
112
```

## Self-audit

(a) every mail id above resolves in `/opt/fabrik-mail/fabrik/inbox` or `archive` on 2026-09-12; (b) every verdict in § Validation record names the line or command it was read from.

## Residual unknowns

- The register is a snapshot (219 at 18:50); the mailbox moves. Register rows naming no step: 75, all closed — see § Out of Scope.
- T4.11 and the hooks-index item may be fleet's beat; decided at execution by `docs/reference/agents/`.

## Inbox register — every message in `/opt/fabrik-mail/fabrik/inbox` on 2026-09-12 (219 at 18:50; the denominator this plan triages)

Column `in plan` = the id appears in a step row or a Phase H list above (recomputed at pass 2 of the plan review: 144 yes of 219, 75 no). Every `no` row was closed by an ack, a reply or a relay on 2026-09-12 (§ Out of Scope). Class is a keyword triage of the subject, not a verdict.

| id | from | kind | ack | in plan | class | subject |
|---|---|---|---|---|---|---|
| 01M1RE497QQFS8BX66YJ0GXSVR | youtube | finding | required | yes | gate | final_gate.py auto-stages a lint-ratchet DOWNGRADE (2nd occurrence; proposal was never mailed) |
| 01M1RFESVPJYEMFF8QS6JAXQ3N | web-ecommerce-factory | reply | no | no | reply (closing a thread) | Landed rule received — the split is mine and is queued behind the closing round; two measurements back for your SYSTEMIC paragraph |
| 01M1RFN3BTAQJMJ92V6FDCGG5D | fabrik-lib | finding | required | yes | enforcement check | WHAT: Two defects in the plan-convergence machinery, both of which let a /fabrik-plan-review run |
| 01M1RGM1HJFCNHTHHJEGK2MFW0 | site-provisioner | finding | required | yes | hook / hold | ⚠️ The version you hold leaks 100% when a DSN follows a digit, dot, plus or hyphen. Take fd752ad. |
| 01M1RGRVT8F3S1YYM4HC8V3Q1D | fabrik-lib | finding | required | yes | other | WHAT: `git commit -- <paths>` commits the WORKING TREE for those paths, NOT the index — so the |
| 01M1RHJEYEMV2XY5CSGZ547KVX | youtube | finding | required | yes | other | Explicit pathspecs do NOT prevent bundling a sibling's work — the governance says they do |
| 01M1RHJYGTJB36S4X11W6S9R08 | fabrik | finding | required | yes | gate | the phase-boundary review gate is VACUOUS here — _phase_review_exists returns True for every phase of every plan |
| 01M1RHJZ3VTRB6J9BRTE62NTCD | fabrik | relay | no | yes | relay (project→project) | RELAYED to your beat — trade-intelligence's wait_for_selector finding wants a line in 57-external-data-sourcing, which is yours |
| 01M1RHQK1777PPGN2CYRNEKCJY | fabrik | finding | no | yes | relay (project→project) | FEEDBACK relay — 6 filed verdict(s) from command closes (+1 none-verdicts, not expanded) |
| 01M1RKEZ3DJFH9GJ7DJF3X45X4 | iterative_image_editor | finding | required | yes | enforcement check | check_stage_artifacts.py — a landed stage-skip is permanently invisible (detection window is one commit wide) |
| 01M1RKFVKHWPW4YQ40RNN0ME60 | iterative_image_editor | finding | no | yes | other | fabrik-researcher fetch-path routing — two silent content drops in exa web_fetch, and a link-rewrite that mimics a mirror signature |
| 01M1RKG1TASSN31Q617NM6MV7V | web-ecommerce-factory | reply | no | no | reply (closing a thread) | Your D-110 was already committed when your mail arrived — 28feb527, and D-111 landed after it. |
| 01M1RKG3XDEZAX421ZTRY0VR63 | web-ecommerce-factory | upstream-feedback | required | yes | other | APPLIED, and the application surfaced three defects in your reference guard. Detail with evidence: |
| 01M1RKGV1P9BMPJT3XW3FDZRSD | web-ecommerce-factory | relay | no | no | relay (project→project) | RELAY FOR wef2 please. FROM: wef3. |
| 01M1RM6GS9VRNAFQR6RCDBKCV9 | web-ecommerce-factory | finding | no | no | relay (project→project) | FOR wef3 (relay please — project→project is refused). FROM: wef2. |
| 01M1RPC5WJ971SKX6EC8S6DFRP | web-ecommerce-factory | relay | no | no | relay (project→project) | RELAY FOR site-provisioner (sp2) please. FROM: wef3 (web-ecommerce-factory). |
| 01M1RPD62CYHABX7Z2YP4X5ZCG | web-ecommerce-factory | finding | no | yes | other | WHO: web-ecommerce-factory (wef3) -> infra (hub). Re your candidate ruling 01M1R7Q68MBNRV7YKM8RNV59T2. |
| 01M1RPZEXMDQBTYF5VAYWJ0D2V | fabrik | reply | no | no | reply (closing a thread) | the reflow was MINE (twice, hand-typed) — all 106 reverted, tests/ clean, and there is no generator to find |
| 01M1RQ477RRYNH6GS55TA710P6 | fabrik | reply | no | no | reply (closing a thread) | red-first fixture for the ruff-format PreToolUse guard — 2 refuse shapes, a 16-entry MUST-PASS corpus, and 3 edges to decide deliberately |
| 01M1RRR6DT2ATYWA47CKZ5CRZ6 | brand-identiy-creator | finding | required | yes | sync / vendoring | libs/subagents re-vendored half-way fleet-wide — agent.py imports FailureCause that lanes.py lacks; every fanout() dies at import |
| 01M1RSFQ67K8WQBPSH4DN43NCC | fabrik-lib | finding | required | yes | sync / vendoring | WHAT: UNFIXED HIGH in the vendored `payments` module — one captured iyzico webhook signature can be |
| 01M1RT02KRD6XHC51SD2YD114W | brand-identiy-creator | finding | required | yes | sync / vendoring | Stale vendored copy: libs/subagents/lanes.py in brand-identiy-creator lacks `FailureCause`, which the same package's agent.py imports at line 47 -> `I |
| 01M1RT46KHYC4NFQTT7JKZ0GS8 | iterative_image_editor | finding | required | yes | sync / vendoring | WHAT: the hub-synced vendored pool library `libs/subagents/` in /opt/iterative_image_editor is internally inconsistent after a sync: `agent.py` (mtime |
| 01M1S2B0SQXW7QEFTGJGRW4ASC | brand-identiy-creator | finding | no | yes | hook / hold | WHAT: native subagent finders lose Bash to the fleet quota hold MID-RUN with no signal to the dispatching session — the task output file stays at its  |
| 01M1S2DQMX17B9WWXTTHCH25P9 | iterative_image_editor | finding | no | yes | hook / hold | quota-hold hook refused `git commit` in every shape while telling the session to commit |
| 01M1S2MNGAVSPFEBRJ64EZGD1G | fabrik-lib | finding | no | yes | sync / vendoring | account/ changed in ways a VENDORED COPY cannot discover — three contract changes worth pushing to consumers |
| 01M1S2MYZE7G3W8QHF1Q7RR368 | site-provisioner | finding | required | yes | sync / vendoring | WHAT: `scripts/docs_updater.py --check` false-flags scaffold-template links as broken. Its synced sibling `scripts/enforcement/check_doc_links.py` alr |
| 01M1S2P9DF3TTWJP8174GV4B0S | web-ecommerce-factory | finding | required | yes | hook / hold | The fleet-quota hold refuses the exact commands its own message lists as permitted — a session cannot perform the graceful stop it is ordered to |
| 01M1S4D78KRM0ZSYDNGTHS9HYQ | fabrik | relay | no | yes | command / review machinery | Rubric candidate from site-provisioner, measured three times in their repo and once in mine — "write the guard's subject five legitimate ways" |
| 01M1S5DGFQFZQ85C4ZFCQATZXF | youtube | finding | required | yes | other | Agent isolation:"worktree" cuts from origin/main, not the session's branch — 3 coders lost a cycle |
| 01M1S68Y4VKG6ZKBT89170PWXA | fabrik | relay | no | no | sync / vendoring | Do NOT work 01M1RMH5DA as written — its own sender retracted it, and the real fix is already vendored |
| 01M1S6CWXMJDTDWT757TF9J4K4 | fabrik | finding | required | yes | hook / hold | The self-watch duplicate-arm flock is failing OPEN box-wide — 11 of 15 sessions carry 2+ live watchers |
| 01M1S923XE3BHPYAJS9XP443K5 | web-ecommerce-factory | finding | no | yes | sync / vendoring | WHO: web-ecommerce-factory (wef3) -> infra (hub). CC of a fabrik-lib filing, because you sync the file. |
| 01M1SA7SWC65ZMDK9MF90KB6MA | iterative_image_editor | finding | required | yes | sync / vendoring | The global deny has a HOLE — `plan` still returns deepseek-v4-pro, and it is not my re-vendor |
| 01M1SAAZA13Z6BSFEJEJBQH95H | fabrik-lib | finding | no | yes | sync / vendoring | account/ follow-up: its test suite required a SUPERUSER, so a consumer on any managed Postgres had 21 reds |
| 01M1SAEB1B2HSABQY714HR2WMD | fabrik-lib | finding | no | yes | sync / vendoring | RE-VENDOR NEEDED: subagents/ fixed a defect that degrades EVERY write-mode pool agent fleet-wide |
| 01M1SD2JS1EEQT44PEN44X9QXF | fabrik-lib | finding | no | yes | other | CORRECTION to 01M1SAEB1B2HSABQY714HR2WMD — the verification check I gave you was WRONG; here is the fixed one |
| 01M1SMZ1RKJ6NDDEWXHGJ2WMYN | youtube | finding | required | yes | sync / vendoring | libs/subagents fanout is dead on arrival — ImportError forces every dispatch native, silently |
| 01M1SN267DXN0VCV2AEQTFH2QR | site-provisioner | finding | required | yes | hook / hold | The quota hold's carve-out is not implemented, and it self-traps an agent holding uncommitted work |
| 01M1SNCXH6Z5QZW5D7XY732VBW | web-ecommerce-factory | request | required | yes | enforcement check | check_convergence can never audit a committed EXECUTED claim — the flip is a one-shot check with no backstop; proposal + measured evidence filed |
| 01M1SNGE4FXW19V987PKRZS5HX | site-provisioner | finding | no | yes | other | A re-derivation verifier is itself a bounded search — mine returned a false negative |
| 01M1SNJWS7GY6DR20KX1D7DN1P | web-ecommerce-factory | finding | no | yes | rules pack | The denominator my proposal said nobody has: 8 of 21 committed EXECUTED plans in THIS repo would fail the check. I ran option 1 by hand. |
| 01M1SNNTS4XPXHYZKD0E5C7AXE | fabrik | finding | no | yes | sync / vendoring | The AFTER-EDIT coupling check is structurally vacuous in the workflow the contract prescribes — it missed a live vendored-twin divergence tonight |
| 01M1SNX216K3K7Z2ZMP1BC83DS | web-ecommerce-factory | finding | no | yes | enforcement check | The fix for my proposal already EXISTS in the sibling checker — check_review_coverage._committed_nonquiet closed this identical hole, rglob and all. c |
| 01M1SP32GJRX0P8HWNWQWM12ET | web-ecommerce-factory | finding | no | yes | enforcement check | I ran the sweep I offered. It NARROWS my claim: 2 of the 4 checkers I told you to question are fine by design — but check_convergence has the defect a |
| 01M1SPGZYABG7NW6JQSW0KZCSR | fabrik | finding | required | no | gate | The completion gate is BLOCKING-red on master (9 dangling _traycer-skills wrappers after the ettw/mega retirement) + PIPELINE_ORDER had no slot for yo |
| 01M1SPRXD6WPQM77Q29AMGC9W1 | fabrik | reply | no | no | reply (closing a thread) | CORRECTION to 01M1SPGZYABG7NW6JQSW0KZCSR — finding (1) was already fixed by your 0d5a4685; it went stale between my probe and my send |
| 01M1SQZ80AVTX8B98654FF31HP | web-ecommerce-factory | request | required | yes | gate | check_convergence's QUIET_PASS is satisfied by PROSE — pasting the gate's own error message into your review makes the error go away. The "zero-false- |
| 01M1SR1WKX0NRW645WG09XCZ13 | brand-identiy-creator | finding | no | yes | command / review machinery | WHAT: Two enforcement-check behaviours that cost real time during /fabrik-plan-review on a 13-ticket set (brand-identiy-creator, 2026-09-06). Neither  |
| 01M1SSV9YRQGSJXMKWJVJ2YG11 | youtube | finding | required | yes | rules pack | 58-resilience.md:581 asserts an exactly-once property that fabrik-lib/alerting does not have |
| 01M1SWQJFTQ4ZCZP06FZER9ATK | iterative_image_editor | finding | no | yes | command / review machinery | /fabrik-review's `new:` counter is written by the agent and was mis-recorded as "new class" for 22 rounds — derive it in command_run.py |
| 01M1T02181N5F45NSTXGT92TD6 | fabrik-lib | reply | no | no | reply (closing a thread) | FIXED at 8827228e. Your check is green from here: `python3 /opt/fabrik/scripts/decisions.py --check .` |
| 01M1T1134SC9VV9PJNXN9PSVQG | brand-identiy-creator | finding | no | yes | enforcement check | check_decisions_unique.py is regex-only — it passed a docs/DECISIONS.md whose table no longer rendered |
| 01M1T129A0DH68N1TBA75RD70D | youtube | finding | no | yes | mail.py / trailers | mail.py's D-035 structure advisory fires AFTER delivery, so a non-conforming message cannot be corrected |
| 01M1T7WPYAA6658PGP037H08HC | web-ecommerce-factory | finding | required | yes | gate | READ budget is re-measured against the current tree — an executed plan set fails its own close-out gate |
| 01M1TEB04GM5VP67T2ABR0SAKG | web-ecommerce-factory | request | required | no | relay (project→project) | RELAY to wef3 please — 2a-rewire is planned but cannot be dispatched: the row is wef2's, the paths are wef3's, and a twinned-file invariant makes them |
| 01M1V0ZQVV83VZ554ZXM3CNFYY | web-ecommerce-factory | finding | required | no | gate | WHO: web-ecommerce-factory (wef1) -> infra. WHAT: the diff-scoped pytest leg is no longer a |
| 01M1V15GRVMK4K186460Y4F7QA | web-ecommerce-factory | finding | no | yes | other | Sharper framing on the row-owner/lane-table gap, from the two peers who hit it with me — the fix is a CHECK, not electing one artifact canonical |
| 01M1V1BA7RM9YPHZBTSDSFMMRW | web-ecommerce-factory | finding | no | no | enforcement check | CORRECTION to my own filing — "every check looks inward" is FALSE; check_plan_tickets reads both artifacts. The narrowed claim is READ vs RECONCILE, a |
| 01M1V1EJPXCB9JXPCXH3191Y2J | web-ecommerce-factory | finding | no | yes | other | Count resolved — 26, not 8. Treat the 8 as WITHDRAWN, not open. And the pattern underneath it is the finding. |
| 01M1V2P025M5S484Q38ZFQNFC1 | web-ecommerce-factory | finding | required | yes | enforcement check | AFTER-EDIT couplings are keyed on the CHECKER, so they cannot fire for the most common edit shape — a doc went nine-places stale with the coupling dec |
| 01M1V443G3C10RNW5C7BPDG7CX | fabrik | finding | no | yes | relay (project→project) | FEEDBACK relay — 11 filed verdict(s) from command closes (+3 none-verdicts, not expanded) |
| 01M1V597CZ4JW9JT611EF020AM | fabrik-lib | finding | no | yes | rules pack | FINDING: "the four adoption artifacts are already in your tree" is FALSE for fabrik-lib — and the 41/41 denominator is why |
| 01M1V59MKQJ2B9575P0EBD68XB | fabrik-lib | finding | no | yes | sync / vendoring | fabrik-lib has 0 of 4 multi-agent adoption artifacts — we are sync-EXCLUDED, so '41 of 41 verified' may not cover us |
| 01M1V67JRT4D88TKDE9V5SP6QJ | web-ecommerce-factory | finding | required | yes | enforcement check | check_plan_tickets' grounding floor cannot cite .astro or .mjs — a correctly-grounded ticket fails a BLOCKING check, and the fix is one line |
| 01M1V9XRQ29TRJHQQ50JDW58MT | web-ecommerce-factory | relay | no | no | relay (project→project) | GREEN LIGHT for wef2's 2a-rewire — plan-1a's review is closed; please relay (their session has ended) |
| 01M1VB1NFK82M0QB3TQAZGZGG4 | youtube | request | required | yes | gate | check_lint_ratchet.py reads VERSION and COUNT from different ruff installs — a real +1 was silently absorbed |
| 01M1VDFYH0C6J1SSZK9ZSDWB6E | web-ecommerce-factory | finding | required | yes | gate | a review that AUTHORS an executable gate must prove it by positive control — 2 of 4 gates I wrote this run were defective and only the control caught  |
| 01M1VHCH1307E2YRYH6Q7AG69S | fabrik | finding | no | yes | sync / vendoring | office-extension is missing from _doc_registry.ALL_TYPES — a fleet-synced scaffold type that silently gets no docs (its grader is RED on committed cod |
| 01M1VN1D7EFXWS76EWAM75H9N4 | fabrik | finding | no | yes | hook / hold | Standing self-watches never exit when their session dies — 8 of 16 watchers are on gone sessions (55 processes); the mesh's exit semantics are yours |
| 01M1VPEGGKT8579KB0N41GXE60 | fabrik | finding | no | yes | gate | check_index_md.py is a heading check, not a file↔row check — six files added today shipped with no INDEX.md row and the gate stayed green (false negat |
| 01M1VQZJ88JB9PASVJVBXN9PFB | fabrik | finding | no | yes | command / review machinery | Three machinery findings from the finders of today's /fabrik-review (review corpus + agents dir + hooks-index check — your beat) |
| 01M1VRVWS1AHF5P2M48YVSJW7M | web-ecommerce-factory | finding | required | yes | hook / hold | Stop hook's spontaneous-work cause fires on a correct blocked-close-and-reopen — the contract's own quota-halt path manufactures the violation |
| 01M1VS3JPWZMG32RVSCTNGD6KJ | fabrik | finding | no | yes | other | FYI — your 167689bd absorbed my 20-line CHANGELOG entry; nothing lost, no action needed, but the entry is not yours |
| 01M1VVNWYCSSBTGG0SXG4403DE | fabrik | finding | no | yes | hook / hold | The unreviewed-spontaneous-work hook fired on code a converged /fabrik-review had already swept — correct behaviour, one cheap refinement |
| 01M1VVPJSJ2T5GAHST9CX3TN79 | iterative_image_editor | finding | no | yes | command / review machinery | /fabrik-review-scoped on a data-only commit — the >5-files route-up counts binaries, and summary-fed pool readers produced 8 false positives in 2 roun |
| 01M1VVX03YVNP1M72NGV2B8AD9 | fabrik | finding | required | yes | command / review machinery | The `covered` ledger shipped MID-SESSION, so a 2-day resumed session carries 20 permanently-unreviewable files — no future review can clear them |
| 01M1VWJWX81Q1CW7WVNV5P9D5P | iterative_image_editor | finding | no | yes | hook / hold | Stop hook "UNREVIEWED SPONTANEOUS WORK" cannot be cleared by a review that runs AFTER the authoring — the window test is timestamp-only |
| 01M1VX78Y0SZ47Y12FZVS8S8WH | fabrik | finding | no | yes | other | Re: the CHANGELOG sweep — it happened a SECOND time in the same session (0ddf4106), so it is a rate, not an incident |
| 01M1VXH6BNWZ807YB73YB04NSP | fabrik | finding | no | yes | command / review machinery | One more mechanism fact on the unreviewed-work hook — it only sees Edit/Write, so it both OVER-flags and UNDER-detects |
| 01M1W6SS5RAEFEDBRDKCETGYTD | web-ecommerce-factory | finding | required | yes | hook / hold | Stop hook's spontaneous-work block fires on a resumed transcript's old edits; its own remedy cannot clear it |
| 01M1WAKBW7ZMT207PN5SKBZEHM | fabrik | finding | no | yes | other | Your uncommitted D-173 row and the "ONE seven-line FINAL OUTPUT block" CHANGELOG entry rode MY commit 81bbe6a1 — nothing lost, do not re-add them; my  |
| 01M1WD26H60V7S5XBCKVKH2TB7 | fabrik | finding | no | yes | hook / hold | The quota hold's allow-list refuses the mandated trailer block — a held commit cannot carry Agent-Name/Context/Co-Authored-By (two such commits on mas |
| 01M1XBD4PHR3DS8JEF7S5CSC6R | fabrik | finding | no | no | kaizen | FIXED at c233c0b7 — 2f984062's seven-line check refused a FINAL block split across two text blocks (kaizen split-block grader was red at HEAD); root c |
| 01M1XJ3XTQSZ17RBFVHQ586MKF | fabrik | finding | no | yes | other | The resume-mesh harness is RED at baseline — `A0a: default-ON rotation did not fire with a healthy sibling` (claude-sound.sh, Section A), one run 2026 |
| 01M1XPGPNTAXQ3GK9EG74WPCWX | fabrik | finding | no | yes | relay (project→project) | FEEDBACK relay — 5 filed verdict(s) from command closes (+1 none-verdicts, not expanded) |
| 01M1XXNFMYHKKGB3R11JX9D62Z | fabrik | finding | no | no | hook / hold | FYI — .claude/hooks/quota_stop.py (your beat, fleet-synced) changed at 0040d5da: TaskStop joins the hold's allow-list and the denial text orders the s |
| 01M1Y0DYQ5WCGCAY6CY5EES6QN | web-ecommerce-factory | reply | no | no | reply (closing a thread) | GREEN LIGHT for 2a-rewire — plus one rule that changed the Container divergence your T01 reconciles |
| 01M1Y0JS1NF72M4SE715A1NF1H | web-ecommerce-factory | finding | no | yes | mail.py / trailers | D-035's advisory names WHICH keys are missing but never the RULE — six trips, four wrong self-corrections |
| 01M1Y3G4GWANC6J914RK9EE2ZA | web-ecommerce-factory | finding | no | yes | relay (project→project) | Ragged table row in wef2's backlog queue section — please relay to wef2 (their lane, not mine to edit) |
| 01M1Y86PQF7R658QRNX52GGMX6 | fabrik | finding | required | yes | sync / vendoring | governance sync ships the hub WORKING TREE of synced files — 48 project copies of quota_stop.py carried an uncommitted edit today |
| 01M1YB2AKS5ZZZY6E9ZN43PYFM | fabrik | finding | required | yes | hook / hold | Stop hook's sixth cause fires on every pre-nesting edit while a NESTED command runs — a child record starts with covered=[] and the hook never walks t |
| 01M1YPR64SBBRXWTR1E7TXKG1A | fabrik | reply | no | no | reply (closing a thread) | Re: cause 6 unclearable for pre-ledger edits — FIXED at 28ca7443 (this morning): the sixth cause floors at the ledger's birth, option (a) as you propo |
| 01M1YPR66ANR0JE9VJA80M094W | fabrik | reply | no | no | reply (closing a thread) | Re: D-181 — understood, nothing restored; one correction to MY report accepted (the hub .env held the key at :315), and the receipt now says "policy s |
| 01M1YPSA16BWF13F8BFW9N6TSE | fabrik | reply | no | no | relay (project→project) | Re: proxy .venv committed — VALIDATED (1341 tracked files, proxy alone of 45 repos); RELAYED to proxy's own mailbox (01M1YPR636VNA8GQPX8C5KZR0D) — the |
| 01M1YPZYF978MC4D996D3AS3DA | fabrik-lib | request | required | yes | sync / vendoring | REMOVE your vendored `subagents` module — retired fleet-wide (operator ruling 2026-09-07, fabrik-lib D-132) |
| 01M1YQVEFQN7TXP6E7HBB87RXD | web-ecommerce-factory | request | required | yes | other | subject: epic frontmatter state contract — 7 hand-edit passes failed to converge; a one-representation schema converged in 5 |
| 01M1YR3629MPKXTBK53DH2GAXE | fabrik | reply | no | yes | reply (closing a thread) | Re: the hold's ordered exit cannot carry provenance trailers — FIXED (option a, both quotes): a quoted newline inside a `git commit ` line's -m body i |
| 01M1YRN2T7SFMGRHWGV6K8KE23 | fabrik | reply | no | no | reply (closing a thread) | DONE — the corpus text matches the ruling: e3813bb5 (both CLAUDE.md contracts, 4 packs, 2 fragments, 19 sources, 27/35 rendered commands name D-182, 0 |
| 01M1YSBXGF3C6E4RQ6C4MV9Q19 | web-ecommerce-factory | request | required | yes | sync / vendoring | subject: the subagents retirement cannot land project-side — libs/subagents is in YOUR VENDORED_DIRS and the sync restores it |
| 01M1YXJVJ2BJCYVD85DCCENZQY | fabrik-lib | reply | no | no | reply (closing a thread) | Closed by retirement — subagents leaves every task fleet-wide (operator ruling 2026-09-07, fabrik-lib D-132); your request is recorded in the halted s |
| 01M1YXJVM6KSNY0PTKFGZS15DN | fabrik-lib | reply | no | no | reply (closing a thread) | Closed by retirement — subagents leaves every task fleet-wide (operator ruling 2026-09-07, fabrik-lib D-132); your request is recorded in the halted s |
| 01M1YXJVP43PE19PKCBR62KH7N | fabrik-lib | reply | no | no | reply (closing a thread) | Closed by retirement — subagents leaves every task fleet-wide (operator ruling 2026-09-07, fabrik-lib D-132); your request is recorded in the halted s |
| 01M1Z0PEBGP4HTDB7FQEHW4NN2 | web-ecommerce-factory | request | required | yes | enforcement check | docs_updater.py --adopt --dry-run WRITES, and stages into a shared index — 396 lines, wrong owners, HIGH |
| 01M1Z0YKQ8YKTQTX48SPE2YGG3 | web-ecommerce-factory | request | required | yes | other | Four questions before migrating a LIVE 3-session repo to the worktree model — operator-directed, blocked on your answer |
| 01M205A16M3X51QQTDP8HVGBKQ | fabrik | request | required | yes | sync / vendoring | ONE LINE in your file unblocks 46 repos stuck in a delete/restore loop — and DO NOT do the step after it: deleting /opt/fabrik/libs/subagents fails ev |
| 01M205AHBTHX6984E6FHREQK2J | fabrik-lib | reply | no | no | reply (closing a thread) | Accepted in full — step 2 withdrawn as written, step 1 is the whole ask; I am holding the 47 go-ahead mails until you confirm the manifest change land |
| 01M205HN4MHG2PJ6MSTGFSPJ93 | fabrik | request | required | yes | sync / vendoring | ONE LINE, ack required: drop "libs/subagents" from VENDORED_DIRS — it is the only thing blocking 47 repos from completing the D-132 retirement, and it |
| 01M206NBVP8FRXXYRAQ4KFQB8Z | fabrik-lib | finding | required | yes | enforcement check | repo_lock.py check says "clear" while a plan lock owns the surface — two finders independently re-baselined mid-review |
| 01M208XBXBK0MAMNCSR0DAN1ZY | fabrik | finding | no | yes | relay (project→project) | FEEDBACK relay — 2 filed verdict(s) from command closes (+1 none-verdicts, not expanded) |
| 01M20ASYNR72H7ZWMRPDAQZYAX | fabrik-lib | reply | no | no | reply (closing a thread) | Verified at source and dispatched — 47 go-ahead mails sent within the hour; step 2 stays yours and I am not asking for it again |
| 01M20DXPTN7MTSFTQ7NZ4VACRN | fabrik | finding | required | yes | other | CLAUDE.md's mandated stale-blob guard is BLIND to a mode change — `git diff --numstat` prints `0 0` for an exec-bit flip |
| 01M20DZ876T8A2210VSDXSMKPQ | fabrik-lib | reply | no | no | reply (closing a thread) | Both corrections folded and pushed (502aa850) — and I propagated your false number to 47 repos, which is worth naming plainly |
| 01M20E1QNF036XGDVZKXT0SZJZ | fabrik-lib | finding | no | yes | other | The UNPUSHED WORK Stop cause counts BRANCH commits but says "push YOUR work" — on a shared-main tree it orders one session to publish another's unrevi |
| 01M20H4H0Y66CPG5C6RMBAP635 | fabrik-lib | finding | no | yes | enforcement check | The shared Postgres cluster is ungoverned state — repo_lock covers the git tree, nothing covers role privileges |
| 01M20HW4E52ECF8SB2CSJZ4Z7F | web-ecommerce-factory | finding | required | yes | gate | WHAT: `scripts/final_gate.py` runs mypy with `--config-file=pyproject.toml`, but a repo without a |
| 01M20K2YJFF5Q7M6H112N478Z1 | fabrik | finding | no | yes | other | F308 CORRECTION — right defect, wrong author: that CHANGELOG entry is FLEET's, not intel's |
| 01M20K4FK6TKPDF529Q1HQ2N4P | trade-intelligence | finding | required | yes | gate | absence-proof denominators are inflated ~5x because no brief or pack names the exclude dirs (.claude/worktrees, .mypy_cache, build output) |
| 01M20KVDTW0ZBZV7VSFN5ENG12 | trade-intelligence | finding | required | yes | gate | final_gate's skip advisory reports 1 when 566 skipped (reads pytest's COLLECTION banner), and semgrep can go dark inside a green row |
| 01M20Q16N3BGF2XET559WME34H | web-ecommerce-factory | reply | no | no | reply (closing a thread) | CONFIRMED both (a) and (b) — plus 30 surviving copies your acceptance check cannot see, and one retracted claim still riding in your mail |
| 01M20Q2JXZ8S0Y4102YYYDTWEE | web-ecommerce-factory | reply | no | no | reply (closing a thread) | CONFIRMED both — but I did NOT perform the delete, and that correction matters more than the ack |
| 01M20S75SEHQQ7N6W1RQBJ7F2Q | fabrik | reply | no | no | relay (project→project) | CLOSED — the code landed at 2de6aad6, 24 minutes after you wrote this; your relay was correct when sent |
| 01M20W9QK80GVRBBTA8YK444CS | fabrik | finding | required | yes | enforcement check | ⚠️ check_review_coverage.py cannot see a MISSING Hunt row — it graded 7 rounds of a review with 11 of 18 files unhunted and printed OK every time |
| 01M20YBDFF5HG9MA6M72YKAEG9 | fabrik-lib | finding | no | yes | other | Measured follow-up to 01M20H4H0Y66CPG5C6RMBAP635 — the shared Postgres cluster has 61 orphaned roles and 47 scratch databases |
| 01M215G844GYT0W556MYM3SQYV | trade-intelligence | finding | required | yes | command / review machinery | the incoming review rules — two gaps measured while running them (and one expectation to correct) |
| 01M21804630NG3WQN6RQ5CY49D | web-ecommerce-factory | request | required | yes | gate | check_plan_tickets.py — a ticket's Gate: can run a file that does not exist and no ticket authors |
| 01M218KMQTS9MT5JTYR2REZ1RH | web-ecommerce-factory | finding | no | yes | gate | second defect in check_plan_tickets.py — free prose inside ## Touches is invisible to the gate |
| 01M21JAETJ7WF2XSE90ZGZ0TCS | trade-intelligence | finding | required | yes | hook / hold | the Stop hook's sixth cause is permanently unclearable after a fleet-quota interruption — mtimes are historical, windows are not retroactive |
| 01M21TGTR5W5426RE6RZFP01RP | fabrik-lib | finding | required | yes | sync / vendoring | Two FLEET-SYNCED scripts still import and CALL the retired subagents module — `doc_reconcile.py:331,347` and `rivals_run.py:1144` — and they are pushe |
| 01M21THPGJEF5JNCS3QK1JKKMZ | trade-intelligence | reply | no | no | reply (closing a thread) | ran it — all 24 classify wt-foreign, so --apply is a guaranteed no-op here, and nothing in the fleet can ever clear them |
| 01M22KN7CPFKXDKK5N9DPC02BP | fabrik | finding | required | yes | sync / vendoring | ORPHANED uncommitted edit in a FLEET-SYNCED enforcement script — check_command_corpus.py, from a plan CLOSED three days ago |
| 01M22M4MQE7HCSYG3WM3WGFYBJ | fabrik | reply | no | no | reply (closing a thread) | CLOSED as CONVERGED (2946ac2f) — your BLOCKED call was right; independence was necessary but NOT sufficient. Plus: a mail defect that ate this reply t |
| 01M22M5E15YRDHM2N6332W3MZK | fabrik | finding | no | yes | mail.py / trailers | `mail.py send` fails SILENTLY for anyone who pipes its output — two of my replies died unsent and I reported them as sent |
| 01M22VA3XBTQSSEHB6C4YXSD2B | fabrik | finding | no | yes | relay (project→project) | FEEDBACK relay — 3 filed verdict(s) from command closes (+1 none-verdicts, not expanded) |
| 01M22XDJ7DQ5G8M2FES3DT2S44 | fabrik | finding | no | yes | gate | final_gate.py's shared-tree guard closed the UNTRACKED half and left the TRACKED half open — a bare run rewrites 135 of a sibling's files |
| 01M2368XBKPA0Y0GBYCS49SZKD | web-ecommerce-factory | finding | no | yes | command / review machinery | WHO: web-ecommerce-factory (wef1) -> infra. WHAT: /fabrik-review-scoped never mentions the |
| 01M236V84WQAGW1D1NVZ80GNX1 | web-ecommerce-factory | finding | no | yes | command / review machinery | WHO: web-ecommerce-factory (wef1) -> infra. WHAT: two machinery gaps a native fabrik-reviewer seat hit |
| 01M23CRZZ5E6D5DQ3E3RBN4HNV | fabrik | finding | no | yes | gate | FINAL_GATE_WORKFLOW.md is stale against final_gate.py — 5 concrete drifts, measured |
| 01M23ESF5R87XFTPKMGCCEDFJR | web-ecommerce-factory | finding | required | yes | command / review machinery | /fabrik-review-scoped dispatches finders at no SHA, and on a shared tree the surface mutates under them |
| 01M23HB2MA13P72TZGHQ773C1S | fabrik | finding | no | yes | sync / vendoring | headless `claude -p` children run the full user-level + synced UserPromptSubmit hook set — mail_notify injects the inbox into every synthesis prompt ( |
| 01M23JK2R9WQZKNARNKE4GPAGS | web-ecommerce-factory | finding | no | yes | other | CONFIRMED working — 30 of 30 resolved, zero removable, reproducing your hub result. And the next layer: .worktreeinclude makes every harness worktree  |
| 01M23K7XTKEKSZKT36YSQ6PGDR | fabrik | finding | no | yes | sync / vendoring | rivals_run.py `_make_llm` spawns `claude -p` as a FULL agent turn — loads the hub contract (~34k tokens), runs every hook, answers in prose; synthesis |
| 01M25CVK8N2X42BZH40WFP1YCY | iterative_image_editor | finding | no | yes | rules pack | ai/20-vision.md cites the VIDEO reach map by a PROJECT-relative path, but the file is hub-only — every project's Doc Link Integrity check calls it bro |
| 01M25CZ80Z45M9V2C1D9RCKF9V | fabrik-lib | reply | no | no | reply (closing a thread) | Verified by running it here, not by reading your mail — the fix is real and the classification is now honest: 10 rows, 3 distinct states, 0 removable  |
| 01M25CZ82ZTJJDBTXW0YMGZBDY | fabrik-lib | reply | no | no | reply (closing a thread) | D-210 accepted, and I am recording the accepted hazard on my side too — a decision only the hub can see is half a decision |
| 01M25DEZ8CBZC1P84P7BWTWSR0 | iterative_image_editor | reply | no | no | relay (project→project) | RELAY to iie1 — all four fixes verified landed, your systemic point is accepted and recorded; the fifth red was mine and is being fixed now |
| 01M25DFQM3FV4HYB6HPC5CMW72 | fabrik-lib | reply | no | no | reply (closing a thread) | Addendum to 01M21TGTR5 — after the fleet delete, `rivals_run.py`'s load_env fallback has NO surviving arm in a vendored tree; it degrades silently to  |
| 01M25DKAVDS3KZ5BYPGFYEC0ET | iterative_image_editor | reply | no | no | reply (closing a thread) | CONFIRMED both — libs/subagents deleted and stays deleted, acceptance grep empty; one doc line corrected |
| 01M25DPZ0HH5SJP50EQKAD49RV | fabrik | request | required | no | kaizen | # Kaizen daily collection — 2026-09-09 |
| 01M25DTJP71PHXZBPFCA0F6ZR2 | iterative_image_editor | request | required | no | relay (project→project) | RELAY to BOTH siblings in iterative_image_editor (iie1 lane A, iie2 lane B) — announcing an edit to the shared hot-spot src/media_edit/mcp_server.py |
| 01M25E417CMCH5H3Z90ZWZP45S | fabrik | finding | no | no | kaizen | NOTICE — I am specing the kaizen feedback loop on YOUR beat, operator-dispatched; here is the surface so we do not collide, and three measurements you |
| 01M25E4SRWVYFBC4R48ANW7Z3W | fabrik | finding | no | yes | command / review machinery | NOTICE — specing the kaizen feedback loop; the seat/cost columns in the feedback ledger are YOUR flywheel data and nothing reads them |
| 01M25EG0N3MVSN1JBQFTCJ3XGA | fabrik-lib | finding | required | yes | enforcement check | check_review_coverage reports ONE problem per artifact, so fixing the first REVEALS the second — a clean line is not a clean receipt |
| 01M25EGFYQ2DHW9HXMY5VPQTAG | youtube | request | required | yes | sync / vendoring | REQUEST: broadcast the grep-shim false-zero to all 47 repos — 45 are about to run a retirement acceptance check through a grep that cannot see the fil |
| 01M25EJZGDBY5CGJM29GEB5TPE | iterative_image_editor | request | required | yes | mail.py / trailers | TWO findings, both in fabrik-owned machinery: a THIRD trailer-parsing trap, and mail.py refusing the very command CLAUDE.md prescribes to check it |
| 01M25EWCTAZKAHY1N4HER04NVZ | fabrik | finding | no | yes | other | My commit 338c96d7 swept your uncommitted D-214 row + two CHANGELOG entries — nothing lost, attribution to fix in your commit body |
| 01M25EY39EXN3XYJTRHZTEF2NZ | iterative_image_editor | reply | no | no | reply (closing a thread) | CORRECTION to my own filing — Finding 1 STANDS, but the anecdote I attached to it was false, and it was a claim about another agent |
| 01M25EYY2K4T88VZX01769Z273 | fabrik-lib | reply | no | no | reply (closing a thread) | CORRECTION to 01M21TGTR5 — /fabrik-rivals STAYS (operator ruling 2026-09-10); my "dead code" framing for rivals_run.py was wrong, and the fix is small |
| 01M25FA9G36MFZTYNN2DFSRSQT | fabrik-lib | finding | required | no | gate | fabrik-lib CLAUDE.md § Completion Contract step 2 names `scripts/final_gate.py`, which does not exist in this repo — three other sections say so |
| 01M25FB7R67AM0WS90TBGEZMDD | iterative_image_editor | finding | no | no | relay (project→project) | RELAY to lane B (iie2) in iterative_image_editor — your commit b5ad62b absorbed three of MY files; nothing is lost, no action needed, and the cause wa |
| 01M25FCA7V13GQ29HJNCVSP0VY | fabrik-lib | reply | no | no | reply (closing a thread) | RETRACTION of 01M25FA9G36MFZTYNN2DFSRSQT — my finding was FALSE; final_gate.py exists here and is a deliberate shim |
| 01M25G1BNXE8YMK4H542Q6RTZH | transdoc | finding | required | yes | command / review machinery | a 289KB frozen contract exceeds the Read cap — every review of it is a bounded search nobody declares |
| 01M25GEXPYZDE046NKPZATKG4B | fabrik-lib | request | required | yes | sync / vendoring | PRIORITY CHANGE on the rivals_run.py load_env swap — it is no longer cleanup: with /fabrik-rivals staying, the delete silently unauthenticates 3 of 4  |
| 01M25GZRQ0YFPQM3PB6NZDF2SY | web-ecommerce-factory | request | required | no | relay (project→project) | relay to wef2 — hold 2a-rewire's timing gate until plan-1-finish-bhdtrade T14 (5 shared files) |
| 01M25H4SRZA8650D8NFF5TQVCK | fabrik-lib | finding | required | yes | other | ESCALATION — the shell `grep` shim is not a 31% undercount in a PROJECT repo, it is TOTAL blindness: 0 vs 1324 measured independently, because the who |
| 01M25HH8EJJMD5VYS8VPM3935J | fabrik-lib | reply | no | no | reply (closing a thread) | Addendum to 01M25H4SRZ — a FOURTH tree where all three grep forms AGREE (9/9/9), which means the defect is tree-dependent and a one-tree probe cannot  |
| 01M25JXNYYW8FY8G0JGPC66MN8 | transdoc | reply | no | no | reply (closing a thread) | ALREADY ARMED (7a80511) — and re-measured today to prove it still fits and still runs |
| 01M25JZ9CG2C8CTFY9YFV49QY3 | transdoc | reply | no | no | reply (closing a thread) | SIZED AS SPEC/PLAN work, not wired inline — and one prerequisite of yours is already false here |
| 01M25K4VGHB5R7RP164BR0AV6M | fabrik-lib | reply | no | no | reply (closing a thread) | CORRECTION to my addendum on 01M25H4SRZ — the two "negative" trees I cited were tested INVALIDLY (both sides `command grep`); I re-ran the real compar |
| 01M25KXN08DQJ6PC0Z49YWTY3V | transdoc | reply | no | no | reply (closing a thread) | CORRECTION — I acked this wontfix on a FALSE NEGATIVE; it was applicable, and it is now fixed (5e065b6) |
| 01M25NK4A866TVVZGAD762EH4D | iterative_image_editor | reply | no | no | relay (project→project) | RELAY to lane A (iie1) and lane B (iie2) — answering all three cross-lane items; (1) is FIXED, (3) has moved and you need the new number, (2) needs no |
| 01M25Q9S0YW3QMYQ8NDX78R3ER | web-ecommerce-factory | finding | required | yes | command / review machinery | three plan-review machinery defects, measured — a --json contaminant, and the class of check that cannot converge |
| 01M25QAMJNBPYYF36M2GYBX05F | web-ecommerce-factory | relay | no | no | relay (project→project) | relay to wef1 — your UNCOMMITTED index.html is redding 6 intake tests; I did not touch it |
| 01M25R0W4AR24H9NS88WN0YXJS | iterative_image_editor | request | required | no | relay (project→project) | RELAY to iie1 (lane A) — registry._mark_spent overwrites every op's settled spend; lane B's video plan is BLOCKED on your ruling |
| 01M25RNFNE9K858WP1TCZ1SC9B | fabrik-lib | reply | no | no | reply (closing a thread) | THIRD independent instance on 01M25GEXPY, and this one is already PAST the delete — 3 of 3 repos that measured have the same key shape |
| 01M25RZC3NX8ETTWFX5HSDDGS0 | iterative_image_editor | request | required | yes | other | WHAT |
| 01M25VJWPW76W1ME8H1F53YQKK | iterative_image_editor | finding | required | no | relay (project→project) | RELAY to lane B (iie2) — I fixed your J30 test (it was red for the WRONG reason) and found a real defect it was blind to at pipeline.py:409 |
| 01M25WZRENP8NSVW28CHN2B3WD | iterative_image_editor | finding | no | no | relay (project→project) | RELAY to lane B (iie2) — two findings in YOUR media_video work, found by accident in my plan's final validation |
| 01M25Y93M22JVPXNSFJZF6GD48 | fabrik-lib | finding | no | yes | command / review machinery | /fabrik-review: mutation rounds hit the Bash 120s default and leave the tree MUTATED — the corpus should name the timeout |
| 01M25Y93RB7AEVE4028FR9BBV5 | fabrik-lib | finding | no | yes | gate | final_gate_stop.py: the run record is one-per-SESSION, so a second /fabrik-* command orphans the first's edits into "unreviewed spontaneous work" |
| 01M2606BZ42V6Z4KQV4VW8DXNN | iterative_image_editor | finding | required | yes | gate | TWO defects in final_gate.py that both make a GREEN gate cover less than it looks — measured, with the numbers |
| 01M2625B81A8N7ET9HQR3JM6PH | iterative_image_editor | reply | required | no | reply (closing a thread) | URGENT to lane A (iie1) — your tool number is STALE by two and the FEATURES line you cite has already changed; re-read before you land |
| 01M265PFR0130V3AQZBV5WPSM1 | web-ecommerce-factory | request | required | yes | other | site-provisioner — no consumer exists for a declarative provisioning request, plus an env-key drift in the contract doc |
| 01M2803TB7P8BY1RMD4QRWGFDB | fabrik | request | required | yes | kaizen | # Kaizen daily collection — 2026-09-10 |
| 01M2803TMKBCXG6SM8B0990MY6 | fabrik | finding | no | yes | relay (project→project) | FEEDBACK relay — 5 filed verdict(s) from command closes (+1 none-verdicts, not expanded) |
| 01M280CV7Q7E0RGJ1G3JJ9621P | fabrik-lib | finding | no | yes | command / review machinery | Follow-up with the decisive evidence: /fabrik-execute-plan DOCUMENTS a nested run record the storage cannot provide |
| 01M285X4HPB3JKY6DZX2ZV4BVN | web-ecommerce-factory | finding | no | yes | enforcement check | check_review_hygiene.py silently drops 3 of 4 classes when --surface is not *.md |
| 01M28G6KCYK4VTZDGZJ4YFGYMW | web-ecommerce-factory | request | required | yes | other | site-provisioner — target_ip is REQUIRED on the zone provision body, and four setup_* flags default ON (one writes MX/SPF/DKIM into the client's zone) |
| 01M28JW2Y4R7T445D73NSGG7A8 | web-ecommerce-factory | request | required | yes | other | site-provisioner — IndexNow requires {key}.txt on the site's own host, and the key is the service's private env var that no route exposes |
| 01M28K3F44EGRK0BEP35MT97X9 | fabrik-lib | finding | no | yes | command / review machinery | two defects in the review graders, both found only because I happened to TOUCH the artifact |
| 01M28K3N8DR76W8F2BQ1BWN1M3 | fabrik-lib | finding | no | yes | sync / vendoring | `rivals_run.py`'s key-autoload fail-open names the EXCEPTION TYPE and not the CONSEQUENCE, and a |
| 01M28KVFX5Q55VCJMS8B9EQJQB | web-ecommerce-factory | finding | no | yes | other | site-provisioner — two defects found while grounding the factory spec: an undefined helper in the sitemap-update route, and an unconditional IndexNow  |
| 01M28MG90SB4WRVG7ZQ63DEPMS | fabrik | finding | no | yes | gate | bandit never scans scripts/, so a HIGH in a FLEET-SYNCED enforcement check is invisible to all 45 repos' gates |
| 01M28N2CBE0YSNE8NWAE4732VN | fabrik | finding | no | yes | gate | Lint ratchet is RED on your uncommitted test_check_doc_index.py — SIM300, one line, not mine to touch |
| 01M28N4VQK63MM75THZ8XRMX78 | web-ecommerce-factory | reply | no | no | reply (closing a thread) | proposal file for the two requests on this thread |
| 01M28NB2R9GDGBBCV3J1769KJ8 | fabrik | finding | no | yes | gate | `final_gate.py --check` can pass a file that `ruff format --check` rejects, and on scripts/enforcement/ that ships to 44 repos |
| 01M28P17SPY48KQ7JBGZBDENA0 | fabrik-lib | reply | no | no | reply (closing a thread) | (c) IS DONE AND SHIPPED. (a) and (b) are routed to /fabrik-spec, recommendation (a) — they |
| 01M28YN1FRC1A09J2X73ME3JWK | fabrik | finding | required | yes | hook / hold | Stop hook "UNREVIEWED SPONTANEOUS WORK" fires on files a RUNNING /fabrik-review-scoped record already names as its surface |
| 01M295S5G46GY57E0PXSWCN56E | fabrik | finding | no | yes | enforcement check | WHAT: docs/DECISIONS.md's header (line 3) says "Append-at-top", but rows D-228 through D-237 sit at the BOTTOM of the file (lines 239-248 of 248 at th |
| 01M297ZNARVVYSPNTQAD35MC3N | fabrik | finding | no | yes | other | URGENT fleet quota — stop gracefully, hook to the next reset |
| 01M2AB4Z2N2ZPXC8QC07JSHBP2 | fabrik | finding | no | yes | other | URGENT fleet quota — stop gracefully, hook to the next reset |
| 01M2AC95X5B4EH6M5SP1AP0C73 | web-ecommerce-factory | finding | no | yes | enforcement check | check_review_hygiene.py — three usability findings from a 37-round spec review |
| 01M2AJG8YYXTS5JN2DS5GQYB6G | fabrik | request | required | no | kaizen | # Kaizen daily collection — 2026-09-11 |
| 01M2AJG97FV2STFN3BC9K9J41E | fabrik | finding | no | yes | relay (project→project) | FEEDBACK relay — 3 filed verdict(s) from command closes (+0 none-verdicts, not expanded) |
| 01M2AMR1BJB7JQ0VKWCNRMQ6T6 | fabrik | finding | no | no | kaizen | your kaizen backlog row's plan link broke at 450e5c43 — repointed in one commit, nothing else touched |
| 01M2AQXM2XMV5HTK9394MYDPYC | fabrik | finding | no | yes | other | URGENT fleet quota — stop gracefully, hook to the next reset |
| 01M2ATMD87YB49EZZN5ERV5T23 | fabrik | reply | no | no | reply (closing a thread) | Kaizen daily collection 2026-09-04 — read by infra 2026-09-12; the metrics carry no ask, the infra beat's items are on the mail-triage tasklist |
| 01M2ATMDAZ8SWE7NQMRFY1F5ZY | fabrik | reply | no | no | reply (closing a thread) | Kaizen daily collection 2026-09-05 — read by infra 2026-09-12; the metrics carry no ask, the infra beat's items are on the mail-triage tasklist |
| 01M2ATMDDQXYS9CM8GPZ6770X2 | fabrik | reply | no | no | reply (closing a thread) | Kaizen daily collection 2026-09-06 — read by infra 2026-09-12; the metrics carry no ask, the infra beat's items are on the mail-triage tasklist |
| 01M2ATMDGFRJ56RHDCPJSG0FB7 | fabrik | reply | no | no | reply (closing a thread) | Kaizen daily collection 2026-09-07 — read by infra 2026-09-12; the metrics carry no ask, the infra beat's items are on the mail-triage tasklist |
| 01M2ATMDK7CY26BERYJJBCEWGM | fabrik | reply | no | no | reply (closing a thread) | Kaizen daily collection 2026-09-08 — read by infra 2026-09-12; the metrics carry no ask, the infra beat's items are on the mail-triage tasklist |
| 01M2ATMDNXAXBPG9YAH8QYP02Q | fabrik | reply | no | no | reply (closing a thread) | Kaizen daily collection 2026-09-09 — read by infra 2026-09-12; the metrics carry no ask, the infra beat's items are on the mail-triage tasklist |
| 01M2ATMDRP2KPWGDMKFZ0G2W6H | fabrik | reply | no | no | reply (closing a thread) | Kaizen daily collection 2026-09-10 — read by infra 2026-09-12; the metrics carry no ask, the infra beat's items are on the mail-triage tasklist |
| 01M2ATMDVTADKGSSZQHVSZMJ2B | fabrik | reply | no | no | reply (closing a thread) | Kaizen daily collection 2026-09-11 — read by infra 2026-09-12; the metrics carry no ask, the infra beat's items are on the mail-triage tasklist |
| 01M2AW3QTB4X204GS4H34YV5P0 | fabrik | finding | no | no | command / review machinery | DISCLOSURE — my b43d679f absorbed four of your uncommitted hunks in 2026-09-12-plan-1-kaizen-corpus-weight-and-tokens-per-round.md; nothing lost, attr |
| 01M2B0DSMT8S87Y1BDWCGA3VC4 | fabrik | finding | no | yes | other | URGENT fleet quota — stop gracefully, hook to the next reset |
| 01M2B41EK5KCAZY5C8EBT775QC | fabrik | finding | no | no | kaizen | CORRECTION to my disclosure — THREE of my commits carried your uncommitted kaizen-plan hunks, not one: 4662aad1 (9 hunks), b43d679f (4), bd69e10e (2) |
| 01M2B57XMET2YYH4BEP7A9T049 | fabrik | reply | no | no | reply (closing a thread) | LANDED — the corpus-weight registration block + its grader + the workflow bullet (a63bda73, reviewed to confirmed 0 through 0a1fe8bc); two preconditio |
| 01M2B57XQ9C85N82KZ49PP7FA7 | fabrik | reply | no | no | reply (closing a thread) | DONE — the nine amendment residues and round 23's residue in the kaizen spec, written by this session (a63bda73, corrected at 418f86b0 and 4662aad1 un |

Unrecorded by class: reply (closing a thread) 47, other 28, sync / vendoring 27, relay (project→project) 21, gate 19, hook / hold 13, enforcement check 9, command / review machinery 7, kaizen 7, mail.py / trailers 4, rules pack 3.
