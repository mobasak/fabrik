# Review — intel sitting: dead-Kilo-module removal + flywheel nested-trap diagnosis

Scope: `caabff14~1..8f19a088` + this run's fixes (partial-split warn + docstring invariant + 1 test).
Surface: HEAD `97516add` · pre-review `git diff HEAD | md5sum` = `23d369a22d4e55bbf182ec1afd2f5bac`
(working-tree delta beyond the fixes = sibling WIP only).

## Rubric (verbatim `review_rubric.py --changed` header)

```
### core/35-security-auth.md
### core/25-data-postgres.md
### core/30-ops.md
### 12-FACTOR (all twelve axes)
### core/10-python.md  (hit: scripts/enforcement/check_subagent_flywheel.py, tests/test_check_subagent_flywheel.py)
### core/40-documentation.md  (hit: CHANGELOG.md, INDEX.md)
### core/45-testing-strategy.md  (hit: tests/test_check_subagent_flywheel.py)
### core/62-using-subagents.md  (hit: scripts/enforcement/check_subagent_flywheel.py, tests/test_check_subagent_flywheel.py)
```

## Coverage Checklist

| Class | Verdict |
|---|---|
| Deletion completeness | REFUTED(1) — proven by execution: 4777 tests collect clean on this surface; pre-delete grep found only the tombstone assert (`test_synced_manifest.py:125`) + fixture filename (`test_check_undeclared_imports.py:296`), both kept |
| Docs truth (CHANGELOG/INDEX vs reality) | REFUTED(1) — the fleet-state claims were executed live this session (sweep output; recovery backup exists at `backups/nested-ledger-recovered-20260828.jsonl`); INDEX row removal matches the deletion |
| Nested-trap branch correctness (ordering, exit semantics) | FIXED(1) + CLEAN — partial-split edge fixed (⚠ advisory on pass-with-stray, `test_pass_with_nested_ledger_present_still_warns`, red-first); ordering verified: real-rows pass wins, nested-only blocks with the diagnosis |
| Fail-open vs fail-closed | REFUTED(2) — corrupt/unreadable nested file changes only the MESSAGE while exit stays 1 on both paths (the sentinel's no-block purpose applies to the real-ledger check); lenient corrupt-line counting is the function's documented design |
| Fleet lens (synced check false-positives) | REFUTED(1) — the probe keys on the LEDGER FILE at `<root>/<name>/.tmp/subagents/ledger.jsonl`; the `<name>/<name>` ledger shape has no legitimate instance (fleet-swept live: only trap instances found) |
| Boundary/sentinel (PROJECT_ROOT.name edges) | REFUTED(1) — PROJECT_ROOT is `parents[2]` of a file at `scripts/enforcement/` depth; the root-path edge is structurally unreachable |
| Behavior-without-a-test | CLEAN — 3 behaviors, 3 tests, all watched RED first (trap diagnosis, partial-split warn, plus the pre-existing suite at 23/23) |
| Docstring invariant truth | FIXED(1) — the fail-safe invariant now admits the deliberate nested-trap blocking state (round-2 finding: the docstring judged the new block a violation of its own contract) |
| Declaration semantics (`FABRIK_NO_POOL=""`, fresh-repo history) | REFUTED(2) — pre-existing surface outside this diff; empty value correctly ≠ a declaration (the contract mandates a reason string); fresh-repo edge self-refuted by its own finder |
| Cost/limit accounting edges | CLEAN — `_merge_base_epoch` reuse verified pure-per-call; in-cycle window identical across real/nested probes |
| python/testing/62 pack conformance | CLEAN — verified by round-5 finders against the current source + tests |

## Pass Ledger

| Pass | finders | found | new | fixed |
|---:|---|---:|---:|---:|
| 1 (wide) | pool ×3: deepseek-v3.2-exp, gemini-3-flash, qwen3-max(error) + native orchestrator adjudication | 6 | 6 | 1 |
| 2 (closing sweep 1) | pool ×2: deepseek-v3.2-exp, gemini-3-flash + native | 4 | 4 | 1 |
| 3 (post-fix sweep) | pool ×2 + native | 2 | 2 | 0 |
| 4 (fresh sweep) | pool ×2 + native | 1 | 1 | 0 |
| 5 (terminal) | pool ×2: both NONE + native re-read | 0 | 0 | 0 |

Flywheel: all completed pool finder rows scored via `set_quality` (project=`intel-review`).
qwen3-max round-1 error = non-result, unscored per Lesson-97 discipline.

## Proofs (this run)

```
$ uv run pytest tests/test_check_subagent_flywheel.py -q      → 23 passed
$ uv run pytest tests/ -q --co                                 → 4777 tests collected (0 errors)
$ python scripts/final_gate.py --check --json                  → "status": "success"
```

Fixes applied this run: the ⚠ partial-split advisory (+ red-first test) and the docstring
invariant addition — both to `scripts/enforcement/check_subagent_flywheel.py`.
