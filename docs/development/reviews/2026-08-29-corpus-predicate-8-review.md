# Review — corpus predicate 8 + the single-sourced test-generation pipeline

**Status:** CONVERGED
**Surface:** `728b584765994b41c4cdb4bb6b2d2be2f9ed2f11` + `git diff HEAD` md5 `2b402cf7f583fa5be305adad70ca0bfc`
**Scope:** commit `728b5847` — 10 files, +252/−21.
**Anchor:** no prior review exists for this scope (newest reviews in `docs/development/reviews/` are all
other subjects: zitadel deploy, canary-grounding, db-before-boot, provider-death). **The anchor did not
match and there was nothing to inherit — so this is a full WIDE pass 1, not a verification-and-delta run.**

**Finder mechanism — declared honestly.** The operator's standing `NO-POOL:` directive (carried in the
commit body under review) forbids pool and subagent dispatch for hub work, so the command's mandated
pool-breadth + native-Opus layers were NOT dispatched. Per the command's own fallback clause — *"If
neither mechanism is available, run genuinely independent passes and do not let a later pass narrow an
earlier one"* — the passes below are single-context and class-partitioned. **This is a weaker recall
mechanism than the command specifies, and the report says so rather than implying finder breadth it did
not have.** Nothing is owed to the flywheel: zero pool dispatches.

---

## Rubric (verbatim, `python scripts/review_rubric.py --changed <the 10 paths>`)

The full output is long; the classes it produced are reproduced as Coverage Checklist rows below.
FLOOR: `core/35-security-auth` · `core/25-data-postgres` · `core/30-ops` · all twelve 12-Factor axes.
MATCHED: `core/10-python` (hit: `check_command_corpus.py`, `test_check_command_corpus.py`) ·
`core/40-documentation` (hit: `CHANGELOG.md`, `INDEX.md`, `commands/_fragments/test-generation-loop.md`) ·
`core/45-testing-strategy` (hit: `tests/test_check_command_corpus.py`).

```
## MATCHED — packs whose globs hit the changed paths

### core/10-python.md  (hit: scripts/enforcement/check_command_corpus.py, tests/test_check_command_corpus.py)
### core/40-documentation.md  (hit: CHANGELOG.md, INDEX.md, commands/_fragments/test-generation-loop.md)
### core/45-testing-strategy.md  (hit: tests/test_check_command_corpus.py)
```

---

## Coverage Checklist

| # | Class | Verdict | Evidence |
|---|---|---|---|
| C1 | FLOOR `35-security-auth` | CLEAN | No auth/secret/tenant surface. `git diff \| grep -iE 'password\|secret\|token\|api_key'` over both Python files: 0 hits. |
| C2 | FLOOR `25-data-postgres` | CLEAN | No DB, schema, migration or query in the diff — markdown + a regex markdown linter + tests. |
| C3 | FLOOR `30-ops` | CLEAN | No compose, ports, deploy or container surface. |
| C4 | FLOOR 12-Factor (twelve axes) | CLEAN | XI: 0 file/log writes (`open(`/`write_text`/`FileHandler` = 0 added). II: 0 `subprocess`. III: no config constants — the regexes are the check's subject matter. |
| C5 | MATCHED `10-python` | CLEAN | `ruff check` both files: All checks passed. `mypy`: 2 errors on this file, byte-identical to the parent commit (`valid_tools` frozenset\|None at what are now :364/:367) — pre-existing, not introduced. The "5 errors" first seen was 3 files, not 3 new. |
| C6 | MATCHED `40-documentation` | CLEAN | No heading-level skips in any edited doc (checked fence-aware). Doc Sync: INDEX row added, CHANGELOG entries, subsystem doc `command-corpus-check.md` updated per the script's own AFTER-EDIT header. Trailers parsed: `role=primary name=infra`. |
| C7 | MATCHED `45-testing-strategy` | FIXED(1) | H2: the three negative tests from `728b5847` had never been seen red. Retro-proven by targeted mutation — over-broad predicate reds two, always-fire reds the third. 0 mock objects; `monkeypatch` on a real filesystem fixture, no DB mocking. |
| C8 | RECURRENCE — fail-open vs fail-closed | FIXED(2) | F1 + G1. `_read` returns `None` on OSError and the caller skips (fail-open, correct: unprovable ≠ violated) — but the skip is now NAMED in `SKIPPED` and subtracted from the reported denominator, so it can never read as a clean audit. |
| C9 | RECURRENCE — cost/quota/limit edges | CLEAN | No cost, quota or budget accounting in scope. Zero pool dispatches this review, so nothing owed to the flywheel. |
| C10 | RECURRENCE — boundary/sentinel/prefix | FIXED(2) | F2 (fenced `#` mis-read as a heading) and H1 (`SKIPPED` triple-counted one file; `audited - len(SKIPPED)` could underflow negative). Both fixed with tests; the clamp proven red by mutation. |
| C11 | RECURRENCE — behavior without a test | FIXED(1) | Round 4 found the `max(0, …)` clamp shipped untested. Every other new behavior maps to a named test; 38 pass. |
| C12 | HUB FLEET LENS — project safety | CLEAN | `audit()` against a project-shaped tree (no `_sources`, no assembler) returns `[]`. Predicate 8 iterates `sources.glob("*.md")`, empty in all ~46 projects. |
| C13 | HUB FLEET LENS — contradiction | CLEAN | The rewritten `/fabrik-review` section states the rule present-tense with no change-history — an improvement on `728b5847`, which had embedded a dated audit finding in a command file (against `commands-are-rules-not-changelogs`). No pack conflict. |
| C14 | HUB FLEET LENS — false positives | FIXED(1) | F6. Enumerated EVERY heading in all 31 sources matching the loose pattern: the narrowed regex now matches exactly one (`fabrik-generate-tests.md:129`) and loses nothing real — the others are "Re-freeze close-out (runs ONLY…)", "Phase 5 — ITERATE until discovery runs dry" and the two "Where this runs". |
| C15 | CLAIM INTEGRITY | FIXED(2) | F3 (numbers from a prototype regex, corrected in 5 sites) and H3 (the summary line silently failed to gain "caller claims" because a `str.replace` matched nothing across a split string). Every published number re-derived from the shipped module this round: 460 / 82 / 17.8% / 3 claims / 31 sources / 23 surfaces — all match. |
| C16 | REGRESSION — content lost from `fabrik-review.md` | CLEAN | Whitespace-normalised diff of the pre-fix 5 steps vs the fragment: the fragment is a strict SUPERSET (adds the step-2 suggester scoring and the step-5 environment question). The lead-in sentence survives in `fabrik-review.md` above the include. |
| C17 | RENDER SAFETY | CLEAN | Rendered from the MAIN checkout (`git worktree list` first line = `/opt/fabrik`); `--check` reports "installed commands + skills match rendered sources"; 31 commands before and after, no prune. |

---

## Pass Ledger

```
Round 1 (WIDE)   — finders: native single-context, all 17 classes | found: 4 | new: 4 | fixed: 4 | → not done
                   F1 unguarded read · F2 fence closes section · F3 prototype numbers · F6 "Where this runs"
Round 2 (SCOPED) — finders: the fix diff + its callers | found: 1 | new: 1 | fixed: 1 | → not done
                   G1 skip claims coverage it did not have
Round 3 (SCOPED) — finders: the fix diff + its callers | found: 1 | new: 1 | fixed: 1 | → not done
                   H1 SKIPPED triple-counts; denominator can underflow
Round 4 (WIDE)   — finders: all 17 classes re-swept | found: 1 | new: 1 | fixed: 1 | → not done
                   C11 the clamp shipped untested
Round 5 (WIDE)   — finders: all 17 classes re-swept | found: 1 | new: 1 | fixed: 1 | → not done
                   H3 summary line never gained "caller claims" (silent str.replace miss)
Round 6 (WIDE)   — finders: all 17 classes re-swept, closing full sweep | found: 0 | new: 0 | → EXIT
```

**Finder mechanism, restated so the ledger is not read as stronger than it is:** every round above ran
single-context under the operator's `NO-POOL:` directive. No pool breadth layer, no independent native
Opus finder. The rounds are class-partitioned and each re-swept the fixed ledger rather than re-scoping,
but they are not the independent finders the command specifies.

---

## Per-finding disposition ledger

7 findings → 7 FIXED + 0 REFUTED.

| # | Finding | Disposition |
|---|---|---|
| F1 | Predicate 8 read a sibling source with no OSError guard, three lines below predicate 7's guard. `known_commands` proves existence at SET-BUILD time, not at READ time; a sibling's rename raises out of a BLOCKING fleet-synced gate. | **FIXED** — `_read()` helper, all four read sites converted. Test: `test_an_unreadable_caller_source_does_not_crash_the_gate` (monkeypatched read; deleting the file up front would NOT reproduce it, since `known_commands` would then skip the caller). |
| F2 | A `#` line inside a fenced code block was treated as a heading, closing the call-sites section; every claim below the first shell comment went unexamined. | **FIXED** — fence tracking in `_claimed_callers`. Test: `test_a_fenced_comment_does_not_close_the_call_sites_section`. |
| F3 | 439 mentions / 17.5% / 77 / 5 claims were computed with the PROTOTYPE's regex, not the shipped `_CHAIN_RE`; published in the CHANGELOG, the checklist, the reference doc, the module comment and the commit message. | **FIXED** — re-derived from the shipped module: 460 / 82 / 17.8% / 3. All five sites corrected, each now carrying the instruction to re-derive rather than re-quote. |
| F6 | `_CALLSITE_HEAD_RE` accepted "where this runs", matching `## Where this runs` in `/fabrik-deploy-plan` and its review — sections about which REPO to run from. Silent only by coincidence. | **FIXED** — narrowed to `call site(s)` / `auto-fires`, verified against every heading in all 31 sources. Test: `test_where_this_runs_is_not_a_call_sites_section`. |
| G1 | The OSError fix introduced a fail-silent-green: `main` printed "all sound across N corpus file(s)" with N counting files COLLECTED, so skipped files still read as audited. | **FIXED** — `SKIPPED` list, subtracted from the reported count and named in an advisory line. Test: `test_an_unreadable_file_is_reported_not_counted_as_audited`. |
| H1 | `_read` is called from four sites, so ONE unreadable file appended three `SKIPPED` entries — the denominator-honesty fix miscounting the denominator. `SKIPPED` can also name files outside `_corpus_files`, so the subtraction could go negative. | **FIXED** — dedupe by path + `max(0, …)`. Tests: `test_one_unreadable_file_is_counted_once`, `test_the_audited_count_never_goes_negative` (proven red by removing the clamp). |
| H3 | The `str.replace` adding "caller claims" to the summary line matched nothing — the string is split across two source lines — so the check ran a predicate its own output never named, and the miss was silent. | **FIXED** — anchor asserted before replacing; every later patch in this review does the same. Live output now names it. |

---

## Residual risks

- **⚠️ Cross-session incident, found while committing this review.** `ec05a490` (intel, "feat(flywheel):
  Phase B") committed my *uncommitted* `CHANGELOG.md` entry for this review — the only new `###` heading
  in that commit's CHANGELOG hunk is mine. The content is correct and in master; the provenance is not
  (`Agent-Role: orchestrator`, no `Agent-Name`). **Deliberately NOT rewritten** — no `--amend`, no
  `--force`; a second unreviewed history edit on top of the first is worse than the misattribution.
  Filed to intel as `01M157WD97HVCNXFS9HKWWGCRV` with the reproducing commands. This is the shared-tree
  hazard CLAUDE.md names, observed from the receiving end.

- **`_orch_corpus`'s wrapper read (`:199`) and the agent-definition read (`:422`) still use bare
  `read_text`.** Pre-existing, outside this change's blast radius, and neither is reached by predicate 8.
  Named here rather than fixed so the boundary is explicit; the same race applies to them.
- **The duplication sweep in `docs/STRATEGIC_BACKLOG.md` stands unfixed** — 4 source pairs, 95 shared
  six-line windows, `fabrik-service-test` + `fabrik-user-test` at 65. Deliberately deferred with its
  measure's blind spot documented, not parked silently.

---

## Verdict

**EXIT.** Round 6 returned `new: 0` with every candidate adjudicated; all 17 Coverage Checklist rows
are CLEAN or FIXED; the last code-changing pass (round 5) was followed by round 6's full fresh sweep.

The honest headline: **reviewing a 252-line change that added a fail-silent-green detector found seven
defects in it, and three were fail-silent-green.** Twice the fix for one introduced the next — the
OSError guard created a false denominator, and the denominator fix miscounted it. The pattern that
produced all three is the same one the predicate exists to catch: an assertion made without running
the real thing (a prototype's numbers, an unasserted `str.replace`, a survey of spellings rather than
of the sections those spellings would capture).

