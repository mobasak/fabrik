# Review — intel sitting 2: absent-DSN advisory + repo= doc line

Scope: my two commits in `6386c9c5..cc724c42` — `0cee8499` (one sentence in
`62-using-subagents.md`: `repo=` is the project ROOT, absolute) and `cc724c42`
(`check_subagent_flywheel._warn_unrecorded` absent-DSN diagnosis + red-first test + CHANGELOG) —
plus this run's own fixes. Sibling commits in the range are OUT of scope (their own loops).
Surface: HEAD `cc724c42` at review start; diff-of-scope = 164 lines.

## Rubric (verbatim header)

```
### core/35-security-auth.md
### core/25-data-postgres.md
### core/30-ops.md
### 12-FACTOR (all twelve axes)
### core/10-python.md  (hit: scripts/enforcement/check_subagent_flywheel.py, tests/test_check_subagent_flywheel.py)
### core/40-documentation.md  (hit: .windsurf/rules/core/62-using-subagents.md, CHANGELOG.md)
### core/45-testing-strategy.md  (hit: tests/test_check_subagent_flywheel.py)
### core/62-using-subagents.md  (hit: all three)
```

## Coverage Checklist

| Class | Verdict |
|---|---|
| DSN-detection correctness | FIXED(2) — a BOM-prefixed DSN line read a provisioned repo as unrecordable (now `lstrip("﻿")`), and a process-env/CI-injected DSN with a clean `.env` was mis-flagged (now `os.environ` honored first); both red-first in `test_dsn_detection_survives_bom_and_honors_process_env` |
| Fail direction (advisory stays advisory) | REFUTED(1) — the OSError fallback keeping the GENERIC message is Lesson-123's broken-instrument rule by design: an unreadable `.env` proves no absence; the branch never blocks in any state |
| Message truth | CLEAN — every claim in both new messages traced to a verified fact (survey, fail-open contract, store identity); round-3 closers confirmed |
| Fleet lens | FIXED(1 — the env-var honor IS the fleet fix) + CLEAN — a repo recording via CI env no longer gets the false "unrecordable" advisory; synced-check semantics verified for the 46-repo spread |
| Secret hygiene | REFUTED(1) — presence-only check, no value ever reaches stdout; the raised item was a future-hypothetical, not a defect in this code |
| Behavior-without-a-test | CLEAN — every behavior (absent-DSN message, BOM, env-var, hermetic delenv) test-pinned; 25/25 |
| Doc-line accuracy (62 pack) | REFUTED(1) — "absolute path" is deliberate pedagogy; the shipped seam honors an existing relative path as the safety net, and nothing mechanically punishes `repo="."` — no false-red exists |
| Boundary/sentinel edges | REFUTED(1) — alternate `.env` locations violate the fleet convention (root `.env` is where the scaffold + registrar write); a design bound, not a bug |

## Pass Ledger

| Pass | finders | found | new | fixed |
|---:|---|---:|---:|---:|
| 1 (wide) | pool ×2: deepseek-v3.2-exp, gemini-3-flash + native orchestrator adjudication | 8 | 8 | 2 |
| 2 (scoped confirm) | native: full suite + lean gate over the fix diff | 0 | 0 | 0 |
| 3 (closing full sweep) | pool ×2 (both NONE with checked lists) + native re-read | 0 | 0 | 0 |

Flywheel: all completed pool finder rows scored via `set_quality` (project=`intel-review`).

## Proofs (this run)

```
$ uv run pytest tests/test_check_subagent_flywheel.py -q   → 25 passed
$ python scripts/final_gate.py --check --json               → "status": "success"
```

One fix-round side-catch: the env-var honor broke the earlier absent-DSN test (the hub test
process itself carries a real DSN) — made hermetic with `monkeypatch.delenv`, which is itself
the proof the new honor path works.
