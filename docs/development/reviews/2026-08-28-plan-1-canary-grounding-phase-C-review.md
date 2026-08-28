# Review — canary-grounding Phase C (integration: filing, liveness, docs)

Surface: `docs/reference/canary-grounding.md` (new) + FEATURES/STRATEGIC_BACKLOG/INDEX rows +
`.fabrik/liveness-registry.json` row + the fabrik-lib enhancement mail (`01M157W2GK`) + the infra
machinery mail (`01M157WKCC`). Plan: `docs/development/plans/2026-08-28-plan-1-canary-grounding.md`
Phase C. The doc-truth half converged separately under `/fabrik-docs-review` (2 passes, md5-stable
no-op, both gates green, one pool-reconciler fabricated-citation refuted by grep).

## Rubric (verbatim — `review_rubric.py --changed docs/reference/canary-grounding.md docs/FEATURES.md docs/STRATEGIC_BACKLOG.md INDEX.md .fabrik/liveness-registry.json` — FLOOR-only surface: docs + a JSON registry match no code packs; the FLOOR classes below were swept)

```
(identical FLOOR block to the phase-B artifact's rubric — same generator, same date; the MATCHED
section is empty for this all-docs surface. See 2026-08-28-plan-1-canary-grounding-phase-B-review.md
for the verbatim FLOOR text; re-run: python scripts/review_rubric.py --changed <the five paths>.)
```

## Coverage Checklist

| Class | Verdict |
|---|---|
| Cross-doc contradiction within the diff | CLEAN — finder found "no verifiable contradictions"; my own docs-review pass verified every claim against code with executable checks (cron-line diff, constant greps) |
| Liveness-registry row schema | CLEAN — keys match sibling cron rows (`cron_match`/`doc`/`evidence.log`/`max_age_hours`/`why`); 192h = weekly + 1-day slack |
| Mail precision (cold-implementer bar) | CLEAN — first finder: column position, threshold, task types, backward-compat rule, and the seed test all explicit; sample row included |
| Backlog verifiability | CLEAN — counts + file names quoted from this session's suite output; the parity-drift row names its evidence |
| Secret handling | FIXED(1) — the first infra-mail attempt tripped the secret guard on a code-ish literal (high-confidence FALSE POSITIVE, noted in the resent mail per the guard-false-positive duty); no credential was ever in the body |
| Fail-open vs fail-closed | CLEAN — registry row's STALE detection is the axis's zero-forward-progress alarm; degraded direction stays "no signal" |
| Boundary/sentinel/prefix collisions | CLEAN — n/a for a docs/registry surface; the registry `id` is unique (grep 1) |
| Behavior-without-a-test | CLEAN — no code shipped this phase; the docs' claims are covered by the Phase A/B suites they describe |
| Finder unverifiables | REFUTED(4) — all four "UNVERIFIABLE from the diff" candidates resolve against held evidence: conftest committed (ec05a490), failure counts = this session's suite output, the multiplier filing = mail 01M157W2GK, the reference doc exists (untracked at diff time because a sibling cleared the index — second occurrence this run, already mailed to infra) |

## Round ledger

| Pass | finders | found | new | fixed |
|---:|---|---:|---:|---:|
| Pass 1 | pool ×1 (mail half; flagged the empty index-cleared diff honestly) + pool ×1 (docs half, HEAD diff) + orchestrator | 5 | 5 | 1 (secret-guard resend) |
| Pass 2 | full gate + convergence + suites re-run post-restage; all four unverifiables refuted with held evidence | 0 | 0 | 0 |

Flywheel: 3 pool rows scored (2 finders + the docs-review reconciler) via `set_quality`.

## Proofs (this run)

```
$ python scripts/final_gate.py --check --json → "status": "success"
$ python -m scripts.enforcement.check_convergence → exit 0
$ TEST_DATABASE_URL=… uv run pytest scripts/kilo-benchmarks/tests/test_canary_grounding_column.py tests/test_canary_grounding.py -q → 27 passed
```
