# Review — cmd 27/31 corpus audit of /fabrik-conformance-review + the flush-race root cause (2026-08-29)

**Status:** CONVERGED
**Surface:** commits pending this run (thread_anchor.py, final_gate_stop.py, command_run.py, tests, docs) — the audited command source itself needed ZERO edits
**Scope:** the 23-surface checklist audit of `commands/_sources/fabrik-conformance-review.md`, plus
the register blackout's true root cause, measured by the `anchor_harvest` telemetry shipped at
cmd 25. Rubric context armed via `review_rubric.py --changed` at cmd 25 over the same hook/router
surfaces; this run's code changes are the same subsystem's second seam.

**Finder mechanism:** single-context under the operator's standing `NO-POOL:` directive — no pool
breadth, no independent native finder. Class-partitioned rounds over a fixed ledger; stated, not
implied.

---

## Coverage Checklist

| # | Class | Verdict | Evidence |
|---|---|---|---|
| C1 | FLUSH-RACE — the register blackout's measured root cause | FIXED(1) | `anchor_harvest` events: chars=3749 at a mid-turn Stop, chars=0 at the turn-final Stop ten minutes later with `tp=True` — the harness fires Stop before the final text entry is flushed, so the extractor read the closing tool_use entry as empty. Fixed as a class in `scripts/thread_anchor.py` + `.claude/hooks/final_gate_stop.py`: extractors skip textless assistant entries; `line --hook` harvests from the payload's transcript at prompt time (race-free by construction); `harvest --hook` implements what its help text had promised since day one. 3 red-first tests in `tests/test_thread_anchor_flush_race.py`; register suite 16 green. |
| C2 | CLOSER-ARTIFACT-GATE — the command's ledger contract vs the closer | FIXED(1) | The command's OUTPUT section says "that FILE is the deliverable, not this chat", yet `fabrik-conformance-review` was absent from `command_run.py`'s artifact-gated done list (the round-135 hole, a fourth command over). Added to the tuple + the pinning test's loop, watched RED then green (`tests/test_command_run.py::test_cert_and_mega_done_also_require_their_reports`). |
| C3 | STALE-TEST-CONTRACT — tests pinning a superseded behavior | FIXED(3) | Three zero-rounds-notice tests still declared terminal "t" and expected the pre-loop-shaped-only NOTICE from earlier today; updated to loop-shaped terminals plus a new silence guard for non-loop terminals (`test_the_zero_rounds_notice_is_silent_for_a_non_loop_terminal`); command_run suites 117 green. |
| C4 | GATE-GRAMMAR CLAIMS — every checker behavior the command asserts | CLEAN | Verified against `scripts/enforcement/check_review_coverage.py` live: fence-stripping before the rubric search (`:359` + `RUBRIC_RUN :235`), the four standing recurrence classes by name (`:54-57`), `Pass 1/Pass 2` labelling + minimum-two (`PASS2 :234, :368`), `ROUTED(n)` first-class in `VERDICT :50`, bare-CLEAN-without-paths rejected (`_PATHISH :236, :399`). |
| C5 | CITATIONS + WIRING | CLEAN | trade-intelligence `e3b779cc` is a real commit and its ledger file exists (cross-repo READ); `fab-ettw-08-implementation-validation-fabrik.md` exists; NEXT map gate-style entry at `assemble_commands.py:71`; router routes all five probe phrasings (EN×2, TR×1, +2 generics) to the `conformance` stem; both constitutions' gate rows name it. |
| C6 | FRAGMENT FIT (item 25) | CLEAN | The `term-coverage` include looked like a diff-shape contradiction; the fragment itself carves out `/fabrik-conformance-review` BY NAME and mandates the discovery-until-dry loop with the inventory-hash Surface — fragment and body share the wording. Refuted as a finding. |
| C7 | fail-open/fail-closed | FIXED(1) | C1 is this class again: an empty extraction was indistinguishable from a missing message (fail-silent); the textless-skip + second pass close the class while both hooks stay fail-open by design. |
| C8 | cost/quota accounting | CLEAN | No cost/limit edge touched; the 5s harvest cap and 2MB tail bound unchanged in both copies (`thread_anchor.py::_TAIL_BYTES`, `final_gate_stop.py::_TAIL_READ_BYTES`). |
| C9 | boundary/sentinel/prefix | CLEAN | The race-shaped test transcript pins the exact boundary (text entry → tool_use entry → metadata lines); `_final_message_text` boundary behavior identical across both copies. |
| C10 | behavior-without-a-test | CLEAN | Every behavior change shipped its grader in-run: 3 flush-race tests, 1 closer-gate case, 4 zero-rounds tests (3 updated + 1 new); suites 16 + 117 + 161 green this turn. |

---

## Pass Ledger

- Pass 1 (WIDE) — all 23 surfaces vs the checklist + the telemetry-measured race — classes closer-artifact-gate, stale-test-contract (flush-race fixed pre-audit in phase 1): found: 2, fixed: 2
- Pass 2 (WIDE) — full ledger re-sweep, fresh, incl. re-read of every fixed hunk: found: 0, fixed: 0 — the no-op round (TERMINAL verdict printed by `command_run.py`)

## Gate

Verbatim `python3 scripts/final_gate.py --json` top-level, run this turn after the final commit:

```json
{"status": "success", "tier": 2, "passed": 55, "failed": 0, "failures": []}
```

The audited command source required zero edits — the cleanest audit of the corpus so far; its
gate-grammar claims were all TRUE because the command and the checker were co-designed against
each other, which is the live-use-stays-true gradient operating at authoring time.
