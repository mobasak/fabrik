# /fabrik-review — this session's infra work (12 commits, 76c0a53b..dce99d33)

Status: CLOSED — coverage-adjudicated exit, final round `new: 0`, every found candidate adjudicated

**Surface:** `HEAD dce99d335d67004c0864b3575a9917e8d025e9ba` · diff md5 `342e2492d21aefaf047e1e047f577327`

**Scope.** Twelve commits: the `/fabrik-rivals` re-audit and its expired justification, the
command-evaluation checklist and its calibration, the `spec-review` router stem, three new advisory
enforcement checks (`check_spec_convergence`, `check_feedback_duty`, plus corpus predicate 6), the
close-out feedback duty end to end (fragment → `--feedback` → record → event → kaizen `Filed` cell),
transdoc's five certification findings, and the agent-definition governance.

**Finders.** Native orchestrator only. `NO-POOL: operator standing directive — no subagent or pool
dispatch for hub work.` Every finding reproduced by executing the real artifact.

**Exit contract used.** This review is the first to exit under the contract it fixed: `new: 0` with
every found candidate adjudicated, not `found: 0`. That is deliberate — the alternative was to hold
this review to a rule I had just proven unreachable.

## Rubric

`python scripts/review_rubric.py --changed <8 code paths>` — FLOOR (`core/35-security-auth`,
`core/25-data-postgres`, `core/30-ops`, all twelve 12-Factor axes) + MATCHED (`core/10-python`).

## Coverage Checklist

| # | Class | Verdict | Evidence |
|---|---|---|---|
| 1 | **fail-open vs fail-closed** (standing) | CLEAN | All five `warn_only` checks probed across 8 argv/root shapes (bad flag, missing value, unknown positional, `--help`, missing dir, a FILE as root): every path rc=0. A non-zero exit from a `warn_only` check is a blocking red in ~46 repos. |
| 2 | **contract vs its grader** | FIXED (1) | **F1, the session's worst finding.** The `term-coverage` fix for transdoc keyed the exit on `new: 0`, but `check_review_coverage.py:1388` still hard-required `int(rows[-1]) != 0` on `found:`. The grader REJECTED the exact state the contract calls converged — transdoc's own defect (two clauses judging one state oppositely), recreated by my fix for it, one layer out. |
| 3 | **doc/code parity** | FIXED (1) | **F3.** After F1, `/fabrik-review`'s own body still promised `found: 0` in six places incl. its description and the `done --evidence` template, and `/fabrik-conformance-review` once. An agent read two different exit conditions in one rendered file. |
| 4 | **classifier accuracy** | FIXED (1) | **F2.** `_feedback_verdict` read any beat name as a filing — but `close-feedback.md` INSTRUCTS `none — <surfaces exercised>`, and those surfaces are routinely the beat names ("infra rules", "the fleet specs"). An honest `none` counted as `filed`, inflating compliance in the metric built to measure it. Then a second layer: `filed?` matched the bare infinitive, so "nothing to **file**" also read as filed. |
| 5 | **advisory output budget** (standing) | CLEAN | `check_spec_convergence` worst case 463/500 with the remedy intact; the marker is charged up front in all three new checks. |
| 6 | **fleet blast radius** | CLEAN | `scripts/enforcement/` syncs as a directory; all three new checks verified silent when their subject is absent (the state of most of the fleet) and registered `warn_only`. `check_feedback_duty` confirmed running inside transdoc's own gate. |
| 7 | **Stop-hook release** | CLEAN | The new `handoff` close sets `state="handoff"`; `final_gate_stop.py:482` blocks only on `state == "running"`, so the disposition genuinely releases. A fourth close that still trapped the agent would be worse than none. |
| 8 | **parser safety** | CLEAN | `_ledger_shapes` deliberately NOT extended (its docstring records three parallel readers drifting until the triple implementation was named the foundation error); `new:` is read off the raw line it already returns. `_NEW_TOKEN` is token-anchored, so a `renewed:` decoy cannot forge the exit. |
| 9 | **behavior-without-a-test** (standing) | CLEAN | F1/F2/F3 each landed with tests watched RED first; both new-check finding paths proven by red-on-revert with the mutation asserted APPLIED (Lesson 134). |
| 10 | **backward compatibility** | CLEAN | The `new:` exit FALLS BACK to `found:` when a row carries no `new:` counter — every pre-existing report grades exactly as before. Verified against the real corpus: 1 non-quiet flag before AND after, the same pre-existing 2026-08-10 report. Silently re-grading history is not a fix. |
| 11 | **cost / quota / limit** (standing) | REFUTED | No metered spend on this surface; the `claude -p` posture is unchanged. |
| 12 | **boundary / sentinel / prefix** (standing) | CLEAN | Beat matching is whole-word (`infrastructure` ≠ `infra`, `intelligence` ≠ `intel`), verified by execution. |
| 13 | **Python discipline** (`core/10-python`) | CLEAN | `ruff check .` clean; three lint-ratchet catches during the session were fixed at source, never suppressed. |
| 14 | Secrets / config (FLOOR 35) | CLEAN | No key, host or token added; the feedback prose is HASHED into the store, never persisted (verified: a filing naming "Kilo" leaves no "Kilo" in the line). |
| 15 | Postgres / Docker / 12-Factor (FLOOR 25/30) | REFUTED | No DB, service, container or port on this surface. |
| 16 | corpus / render / agents | CLEAN | `assemble_commands.py --check` clean; corpus check green across 47 files (43 before predicate 6); drift detection proven by hand-editing a live agent and watching it flag. |

## Pass Ledger

| Pass | finders | found | new | fixed |
|---|---|---|---|---|
| Pass 1 (WIDE) | native orchestrator, all 16 classes | 2 | 2 | 2 |
| Pass 2 (SCOPED) | native, the fix diff + its callers | 0 | 0 | 0 |
| Pass 3 (SCOPED) | native, doc/code parity over the F1 fix | 1 | 1 | 1 |
| Pass 4 (SCOPED) | native, mechanical: fail-open · corpus · render · lint | 1 | 1 | 0 |
| **Pass 5 (closing FULL sweep)** | native, all 16 classes against the final code | **0** | **0** | **0** |

Pass 4's single candidate was REFUTED as out of scope — see below.

## Findings

- **F1 — the grader rejected the contract's own exit.** CONFIRMED at `check_review_coverage.py:1388`.
  Fixed by reading `new:` off the ledger row's raw line, with a deliberate fallback to `found:` for
  rows that carry no `new:` counter. 6 tests.
- **F2 — an honest `none` counted as a filing.** CONFIRMED by executing the classifier. Two layers:
  a bare beat name, then the bare infinitive "file". Fixed; 2 tests over 8 phrasings.
- **F3 — six stale `found: 0` promises** in `/fabrik-review`'s own body plus one in
  `/fabrik-conformance-review`. Fixed, and the example ledger now MODELS the new exit (a pass with
  `found: 1, new: 0` that correctly EXITS), because an example is what agents copy.

## Refuted

- **`design-review.md` promises `found: 0` as its exit.** REFUTED as out of scope: it does not
  include `term-coverage`, carries its own independent convergence contract, and is untouched by this
  diff. ⚠️ Recorded because the same termination trap plausibly exists there — "Refuting/deferring
  findings does not count as empty" means a permanently-deferred finding blocks convergence forever,
  which is exactly transdoc's shape. It deserves its own evidence and its own change, not a
  drive-by edit from a review whose surface it is not on.

## Phase verdicts

- **Phase 0 (scope + surface hash + rubric + persist)** — PASS. 12-commit surface hashed, rubric run
  over the 8 changed code paths, report created before Pass 1.
- **Phase 1 (finders, recall)** — PASS. All 16 classes swept in one wide round; 2 raised.
- **Phase 2 (refute)** — PASS. The `design-review` candidate refuted as out-of-scope with its reason
  recorded rather than silently dropped; F1/F2/F3 confirmed by executing the real artifacts.
- **Phase 3 (prove & fix + regression guards)** — PASS. Three fixes, each with tests watched RED
  first; backward compatibility proven against the real 49-report corpus (same single flag before and
  after).
- **Phase 4 (loop to no-op)** — PASS. Five passes; the closing full sweep raised nothing.

## Closing evidence

```
$ python -m pytest tests/test_command_run.py tests/enforcement/ tests/test_agent_definitions.py \
    tests/test_close_feedback_autoappend.py tests/test_check_convergence.py -q
865 passed

$ for c in spec_convergence feedback_duty rivals_dossier: python scripts/enforcement/check_$c.py
rc=0 (all three, against the real repo)

$ python commands/assemble_commands.py --check
check OK — installed commands + skills match rendered sources

$ python scripts/enforcement/check_command_corpus.py
✓ command corpus: ... all sound across 47 corpus file(s)

$ ruff check .
All checks passed!

$ python scripts/final_gate.py --json
"status": "success"  (41 blocking / 0 failures)
```

Contract, grader and docs now agree on one exit condition — verified mechanically: fragment
`new: 0` present, grader `_NEW_TOKEN` present, zero `found: 0`-as-exit claims left in the review
command's body.
