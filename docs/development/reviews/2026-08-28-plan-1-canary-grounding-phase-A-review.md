# Review — canary-grounding Phase A (probe harness)

Surface: `scripts/sysadmin/canary_grounding.py` + `tests/test_canary_grounding.py` (both NEW) +
CHANGELOG/INDEX/.env.example/CONFIGURATION rows. Plan:
`docs/development/plans/2026-08-28-plan-1-canary-grounding.md` Phase A.

Finders: pool deepseek/deepseek-v3.2-exp + google/gemini-3-flash-preview (round 1) + orchestrator
adjudication (no native Opus finder owed — the diff touches no auth/schema/migrations/secrets/
concurrency surface; new standalone hub script).

## Coverage Checklist

| Class | Verdict |
|---|---|
| Judge correctness (prefix contract, boundaries) | REFUTED(4) — unicode/`+` continuation chars are unreachable for hex-only generated paths and a trailing junk char after the EXACT path is the trailing-prose class (scores 5 per the re-frozen spec); empty-rest crash self-refuted (`if rest` guards); case + space-separated-extension are spec-settled (exact sequence instructed; right-path-then-junk = trailing prose) |
| Roster derivation | REFUTED(1) — all-anthropic roster → empty → loud exit 1 is the designed batch-level failure, not a per-unit one; mock matches `pick_models`' verified `list[str]` return |
| Index alignment (specs/_LAST_PATHS/results) | FIXED(2) — CONFIRMED: a results list shorter than specs was silently truncated, and an EMPTY results list exited 0 with an empty report (zero forward progress reading as success). Guard added: `N/M results returned` loud line; empty → exit 1. Both tests watched RED first (`test_run_batch_empty_results_is_loud_and_nonzero`, `test_run_batch_short_results_is_loud`) |
| Fail-open vs fail-closed | CLEAN + FIXED(1 test) — per-unit fail-soft loud + continue; record-ok-score-fail leaves an unscored row NULL-invisible to the average (plan IX bullet, by design); fail-soft test strengthened to assert exactly the failed unit is unscored |
| Cost accounting edges | REFUTED(2) — `>` at exactly $0.10 matches "exceeds"; unknown (None) costs reported as `unknown`, never counted 0; negative-cost has no realistic path and the line is alarm-only |
| Mutable-global `_LAST_PATHS` | REFUTED(1) — reset at batch start; single-process weekly cron; deliberate test seam (documented in the module) |
| Stdout-only (XI) | CLEAN — no handlers, no file writes; cron log lives in the operator's redirect under the state dir |
| Behavior-without-a-test | CLEAN — 16 tests, every stepped behavior named; judge suite + the two new guards watched red first |

## Round ledger

| Round | finders | found | new | fixed |
|---:|---|---:|---:|---:|
| 1 | pool ×2 + orchestrator | 15 | 15 | 2 (+1 test strengthened) |
| 2 (post-fix re-run) | full suite 16/16 + lean gate success; fix diff re-read | 0 | 0 | 0 |

Flywheel: both pool rows scored via `set_quality` (project=canary-grounding-build).

## Proofs (this run)

```
$ uv run pytest tests/test_canary_grounding.py -q   → 16 passed
$ python scripts/final_gate.py --lean --json         → "status": "success"
```
