# Plan review — merge-owner row grammar (W-5d3ed438)

**Status:** IN-PROGRESS
**Command:** /fabrik-plan-review · joint loop over a `Size: small` spec (spec § The delta D10)
**Artifacts:** `docs/development/plans/2026-10-17-plan-1-merge-owner-grammar.md` and
`docs/superpowers/specs/2026-10-17-merge-owner-grammar-design.md`, both DRAFT at 0bccb9f98.

## Round zero — the orchestrator's pre-pin probe

Executed before the first pin; each fix is in the round-1 pin.

| # | Finding | Evidence | Fix |
|---|---|---|---|
| Z1 | Step 1 said every new grader is red today; A2's `**Merge owner:**` spelling and A5 are green today | `rule_cases.py` (run folder `probes/`): both read `alpha` under today's grammar; the two mutants executed (bold token without `(?-i:)` reads `rotated`; `\**` reads `beta`) | Step 1 names both and the mutant that turns each red (0bccb9f98) |

## Ask ↔ spec

Built from the spec's own § Intake Inventory (4 items: 4 IN).

| I# | The ask (anchored) | Where the spec answers it | Where the plan builds it | Disposition |
|---|---|---|---|---|
| I1 | "a bold-wrapped label `**MERGE OWNER:** coordinator` never matches" (W-5d3ed438) | § The delta D1 | Phase A step 2; A1, A3, A5, A6 | IN |
| I2 | "a bare what-cell opening with prose `Merge owner: rotated weekly` reads `rotated` as the owner" (W-5d3ed438) | § The delta D2 | Phase A step 2; A2, A3b, A4, A6 | IN |
| I3 | "in all three copies, with a shared-fixture parity test" (W-5d3ed438) | § The delta D3 | Phase A step 1; A6, A7 | IN |
| I4 | "check `--merge-owner` still reads coordinator after your change" (coordinator) | § Validation V4 | Phase A step 6 | IN |

## Pass Ledger

| Pass | seats · axes re-checked (claims · gates · interfaces · completeness) | counters | method | plan md5 (start → end) |
|-----:|---|---|---|---|
| Pass 1 | opus×1 (O: spec What exists/Chosen/Delta/Validation/Decisions + plan Global Constraints/Phase A/File Scope/Digest/Checklist/Evidence) + sonnet×1 (S: every other section of both) · all axes; shape: agent-tool | found: 16, new: 16, confirmed: 11, fixed: 11, unexecuted: 0, edits: 20 | method: citation + re-derivation — full pass; the orchestrator executed every candidate (`pass1_verify.py`, `rule_cases.py`, the real-reader owner loop) | a72b988a… → 5c6a9983… (plan); spec fc30bdb7… → 8a4602fa… |
| Pass 2 | opus×1 + sonnet×1 (the round-1 slice owners) · delta over the pass-1 fix hunks + one hop; shape: agent-tool | found: 7, new: 7, confirmed: 3, fixed: 3, unexecuted: 0, edits: 4 | method: re-derivation — the 13 pass-1 ledger rows re-executed (all CLOSED; the step-6 loop run as a python driver and against a broken-prefix mutant, `rule_cases.py` re-run, the pins probed on edited copies); 3 confirmed, all own-fix of pass 1 (the step-6 loop broke when pasted, its live-ledger window, A3b missing from step 1's red list) | 0a097a56… → 9c91b6e4… (plan); spec 8a4602fa… → 8a4602fa… |
| Pass 3 | opus×1 + sonnet×1 (the round-1 slice owners) · delta over the pass-2 fix hunks; shape: agent-tool | found: 5, new: 5, confirmed: 2, fixed: 2, unexecuted: 0, edits: 3 | method: re-derivation — the 6 pass-2 rows re-executed (step 6's two loops run against a base copy and an edited copy: 52 lines, 9 `rc=0`, 43 `rc=3`, diff empty); 2 confirmed, both own-fix of pass 2 (the fix script corrupted the text around step 6; `<base SHA>` undefined); scope-growth stop fired (own-fix 3/3 → 2/2) | 90129f68… → 04726964… (plan); spec 8a4602fa… → 8a4602fa… |
| Pass 4 | opus×1 + sonnet×1 (round-1 owners) · the pass-3 fixed set (the scope-growth stop's remainder round); standing clean since Pass 1: every other class; shape: agent-tool | found: 0, new: 0, confirmed: 0, fixed: 0, unexecuted: 0, edits: 0 | method: re-derivation — the fixed set re-derived from the pin (steps 1–7 consecutive, one step 6, the Phase A heading, eight `- **Given**` rows A1–A7 with A3b; the pin diffed against d908e2058: exactly the four intended hunks; `<base SHA>` defined); load-bearing claims re-derived (the six touchpoint lines, `rule_cases.py` 11/0, 52 ledgers, intake 6/6 and 4/4, V1–V5 mapping) | 5470f1f7… → 5470f1f7… ✓ (plan); spec 8a4602fa… → 8a4602fa… ✓ |

### Pass 1 candidates

| Id | Finding | Disposition |
|---|---|---|
| O-1, S-1 | Step 6 and Global Constraint 1 rest on `owner_diff.py`, a run-folder script; re-pointed at the edited file it compares the new grammar with a near copy of itself and passes a broken prefix | CONFIRMED (the seat's broken copy printed `changed 0` while `--merge-owner /opt/fabrik` read `infra`), FIXED — the real reader, `decisions.py --merge-owner`, run over every ledger before and after, diffed; baseline taken (52 ledgers: 9 rc 0, 43 rc 3; hub `coordinator`) |
| O-2 | A mixed-case un-adoption row (`Merge owner: UNDECLARED`) un-adopts today and becomes prose, bringing back an older owner; untested and unstated | CONFIRMED (`pass1_verify.py`: old undeclared True, new False), FIXED — spec D2 and § Lifecycle Failure state it; A3b added; `rule_cases.py` case added (red today) |
| O-3 | The hook's `:211` ("Case-insensitive because the phrase match is") would state the opposite of the code | CONFIRMED (read), FIXED — Interfaces and step 3 name it |
| O-4 | The `uses` pin (`:903`) is its own literal; the plan never said it changes | CONFIRMED (read `:896`, `:897`, `:903`, `:912`, `:917`), FIXED — spec D3 and A6 name each literal that changes and `:896` that does not |
| O-5, S-2 | Pin and fixture ranges disagreed (`:880-920`, `:896-918`, `:879-924`, `:896-924`; `_OWNER_CASES` `:1270-1305`) | CONFIRMED (the test runs `:879-920`; `_OWNER_CASES` `:1271-1306`), FIXED in both docs |
| O-6 | The guard-order warning is true of the owner regex alone, not of the reader, which tests `_UNDECLARED_RE` first | CONFIRMED (`pass1_verify.py`: regex alone `UNDECLARED`, reader the un-adoption), FIXED — spec D1 says so; A6 adds a guard-order mutant |
| O-7 | Evidence pasted 7 of `bold_probe.py`'s 11 rows unannounced; `rule_cases.py` was not in a run folder a seat could find; I3 and the checklist said "A5 and A6 red on a mutant" | CONFIRMED, FIXED — "7 of its 11 case rows shown"; the probe's absolute durable path cited; both rows corrected |
| O-8 | `ruff format --check` in step 4 fails: the edited one-line compiles pass 100 characters | CONFIRMED (seat's `ruff format --diff`: 1 file would be reformatted), FIXED — step 2 runs `ruff format` |
| O-9 | Other bold spellings (`***…***`, `__…__`, tab before `**`, bold name) stay prose, unstated | CONFIRMED (seat's probe, `new= None` for each), FIXED — one sentence in spec § Decisions taken |
| S-3 | Size: spec ≈25 code lines, plan ≈30 | CONFIRMED, FIXED — ≈30 in both |
| S-4 | Phase B had no INDEX step for the receipts and no `/fabrik-docs-review` | CONFIRMED, FIXED — Phase B step 2 |
| S-5 | "~46 repos" beside a 52-ledger census | RECORDED — measured (wording; ~46 is the synced fleet the hook reaches, 52 the ledgers on the box; changes no behaviour) |
| S-6 | § Lifecycle names three hub-absolute readers; the plan's Evidence lists four | REFUTED — the fourth, `scripts/check_commit_trailers.py`, is not fleet-synced (`fabrik_synced_manifest.py --list`), so "three fleet-synced readers" is exact |
| S-7 | Anchors cited at 83bc96588 / 0cbf8d780; HEAD is 826d6eb4a | RECORDED — measured (every anchor the seat opened holds at 826d6eb4a) |

Also found by the orchestrator while fixing: the spec's § Growth trigger named `owner_census.py` without a path —
FIXED, its absolute durable path cited.

### Pass 2 candidates

| Id | Finding | Disposition |
|---|---|---|
| O-N1 | Step 6's loop wrapped across a line inside `$(…)`: pasted as written, `decisions.py` runs with no arguments and every line reads `rc=127`, so the diff is empty whatever the edit does (own-fix: round 1) | CONFIRMED (seat's `subprocess` probe: `x first rc=127`; `decisions.py` with no argument exits 2), FIXED — step 6 is a fenced block, one command per line, and the before-file's line count and `rc=` tallies are pasted (an `rc=2`/`rc=127` line means it did not run); executed: diff empty, 52 lines, 9 `rc=0`, 43 `rc=3` |
| S-N3, O-N4 | The before and after loops read the live ledgers at different times, so another session's append between them makes the diff non-empty for a reason unrelated to the grammar (own-fix: round 1) | CONFIRMED (by construction: the hub ledger is appended by every session), FIXED — step 6 runs the base reader (a throwaway worktree at the base SHA) and the edited reader back to back; Global Constraint 1 aligned |
| O-N2 | Step 1's red-today list omitted A3b, which is red today (own-fix: round 1) | CONFIRMED (`rule_cases.py`: `A3b … old='' red today`), FIXED |
| S-N1 | File Scope omits `INDEX.md`, `CHANGELOG.md`, `docs/STRATEGIC_BACKLOG.md`, which Phase B edits | REFUTED — they are governance files, kept out of File Scope by the plan grammar (`scripts/enforcement/check_plan_tickets.py::GOVERNANCE_FILES`) |
| S-N2 | ONE-HOP: spec § Lifecycle Adoption names only declaring rows as the old/new difference; a mixed-case un-adoption row differs too | RECORDED — measured (wording; the census holds no such row, 0 of 52; changes no behaviour) |
| O-N3 | ONE-HOP: `probes/rule_cases.py` loads the live `decisions.py` as its old grammar, so after step 2 its "red today" column is meaningless | RECORDED — measured (the probe is run-folder evidence, run before the edit in step 1; the in-repo graders are the tests, whose red is watched in step 1) |

### Pass 3 candidates

| Id | Finding | Disposition |
|---|---|---|
| S-N3A, O-P3-1 | The pass-2 fix corrupted the text around step 6: a truncated old step 6 fused with the new one, step 7 and the `**Behavior Contract (Phase A):**` heading deleted, A1's `- **Gi` prefix cut (own-fix: round 2) | CONFIRMED (the pin's lines 132 and 147; the fix script took its slice indices before a preceding replacement shortened the text), FIXED — the plan rebuilt from d908e2058 with every pass-2 edit as an exact once-only replacement, the script asserting step 7, the heading and one step 6 present and the fragments absent (d83577563) |
| S-N3B, O-P3-2 | `<base SHA>` undefined; an executor could pick a SHA that already holds the edit and get an empty diff that proves nothing (own-fix: round 2) | CONFIRMED, FIXED — step 6 defines it as the commit Phase A starts from (`git rev-parse HEAD` before step 1) |
| O-P3-3 | The fenced block cannot run in a worktree-isolated session (the guard refused the `$(python3 …)` loop for a seat) | REFUTED — this session ran the block's commands in this worktree in pass 2 (`git worktree add`, both loops, `diff` → rc 0, `git worktree remove`); the refusal applies to a seat's compound shell, not to the executing session |
| S-N1 (re-check) | The refutation's path | CLOSED — the receipt now names `scripts/enforcement/check_plan_tickets.py::GOVERNANCE_FILES` |

**Scope-growth stop (pass 3).** Passes 2 and 3 confirmed only defects inside this review's own fix hunks (own-fix
3/3, then 2/2; `command_run.py round` printed `SCOPE GROWTH`). Every defect open in the window is fixed above. The
remainder round re-verifies that fixed set alone; any further own-fix defect it raises is `RECORDED — measured` onto
work item W-5d3ed438's notes (the build reads this plan there) and does not reopen the hunt.
