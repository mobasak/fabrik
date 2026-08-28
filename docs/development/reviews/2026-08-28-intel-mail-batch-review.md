# Review — intel mail-handling batch: driver probe · re-vendor · pack warning · lint enrollment

Scope: my four commits in `56beaa0e..0144988f` — `eba2c077` (pg-driver third-cause probe + test),
`81e3abb7` (competitor_intel re-vendor at cb6c59e — reviewed as PROCESS integrity, the vendored
lines are fabrik-lib's 12-round loop's), `443b325f` (62-pack inline warning + backlog row),
`0144988f` (vendored-lint exclusion). Sibling commits in range out of scope.
Surface: authored-delta diff = 320 lines.

## Rubric

`review_rubric.py --changed` over the five authored files: 8 sections (mandatory core + 12-Factor
+ 10-python + 40-documentation + 45-testing + 62-using-subagents).

## Coverage Checklist

| Class | Verdict |
|---|---|
| Driver-probe correctness | REFUTED(2) — find_spec's degraded-specificity on a broken install falls through to the GENERIC message (never a false claim; the deliberate fail direction, actual-import could hang the gate); interpreter-identity approximation documented in the helper's docstring |
| Advisory ordering | FIXED(1) — the both-absent state suppressed the driver cause behind the DSN message ("provision the DSN" would not have sufficed); the DSN message now appends the missing-driver note. Driver-vs-generic precedence verified correct |
| Re-vendor process integrity | CLEAN — source = fabrik-lib committed HEAD cb6c59e (their WIP tree deliberately not used), orchestrator byte-identity diffed, 103/103 hub tests, zero local edits to vendored lines |
| Lint-exclusion blast radius | REFUTED(1) — the dir is an rsync --delete mirror of canonical; hub-authored files cannot live there by construction; upstream B007s noted back to the module's own gate |
| Doc/backlog truth | REFUTED(1) — the measured-differential evidence is the archived mail, ULID-cited in both docs (the standing convention for cross-repo evidence) |
| Behavior-without-a-test | FIXED(1) — the probe's fail-open exception path was untested; `test_driver_probe_error_fails_open_to_the_generic_message` added (asserts no false driver claim) |
| Fleet lens | REFUTED(1) + CLEAN — empty-env-var precedence falls through to file layers, which matches the recorder's behavior; synced check/pack semantics verified for the spread |

## Pass Ledger

| Pass | finders | found | new | fixed |
|---:|---|---:|---:|---:|
| 1 (wide) | pool ×2: deepseek-v3.2-exp, gemini-3-flash + native adjudication | 7 | 7 | 2 |
| 2 (scoped confirm) | native: 33/33 suite over the fix diff | 0 | 0 | 0 |
| 3 (closing sweep) | pool ×2 (one NONE + verified checklist; one self-retracted, no standing candidate) + native | 0 | 0 | 0 |

Flywheel: all completed pool rows scored via set_quality (project=intel-review).

## Proofs (this run)

```
$ uv run pytest tests/test_check_subagent_flywheel.py -q   → 33 passed
$ python scripts/final_gate.py --check --json               → "status": "success"
```
