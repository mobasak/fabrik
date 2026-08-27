# Phase review — certification grader (plan phases A + B)

Status: CLOSED — coverage-adjudicated exit, final round `found: 0`

**Plan:** `docs/development/plans/2026-08-27-plan-1-certification-denominator.md` · **Phases:** A + B
**Surface:** `scripts/enforcement/check_certification_coverage.py` (new) ·
`tests/enforcement/test_certification_coverage.py` (new, 47 tests) · `scripts/final_gate.py` (one
`warn_only` registration). Commit `b94e9ce8` + the Phase-B additions.

**No agents** — the operator has rejected subagent/pool dispatch for this work, so finders ran
natively. Compensating control: every finding below was reproduced by execution.

## What these phases had to get right

The grader is built BEFORE either command changes, deliberately: a contract with no grader is the
exact defect the plan removes, and building the checker first means the prose has something to be
true against.

## Coverage Checklist

| # | Class | Verdict | Evidence |
|---|---|---|---|
| 1 | **fail-open vs fail-closed** | CLEAN | Exit 0 on every path incl. the guard's own; 4 tests. The BLOCKING verdict rides the finding's flag, never the exit code — `final_gate.py:198-208` turns a non-zero `warn_only` exit into a fleet-wide red. |
| 2 | **boundary / sentinel / prefix** | FIXED (1) | The cert-lock discriminator used `"cert" in plan` and flagged THIS plan's own lock (`...-certification-denominator.json`). Narrowed to require the plan point INTO the certifications tree; pinned by `test_an_implementation_plan_about_certification_is_not_a_cert_lock`. |
| 3 | **cost / quota / limit** | CLEAN | Advisory output bounded to the 500-char / 10-line budget, truncation NAMED never silent; asserted by `test_output_is_ascii_and_bounded`. |
| 4 | **behavior-without-a-test** | CLEAN | 47 tests; 11 guards proven red-on-revert with the source restored byte-identical; contract/test parity asserted mechanically rather than as a literal count. |
| 5 | Namespace separation | CLEAN | `TC##` verified to escape the `T##` pattern by executing the gate's own regex; heading, directory and lock-dir guards each tested. |
| 6 | Denominator integrity (Phase B) | CLEAN | Doc-denominator rejected, `registry_total` vs `ids_enumerated` catches a consistently-short generator, absent ledger reported. |
| 7 | Retired-type crash guard | CLEAN | `wordpress` absent from `REGISTRY_BY_TYPE`, present in `RETIRED_TYPES`; `test_the_registry_table_covers_every_live_scaffold_type` asserts the live set is total and that the retired string gets no row. |

## Findings

**Fixed (1) — a false positive in the guard's first smoke run.** `"cert" in str(data.get("plan"))`
flagged the executing plan's own lock, because the path contains *certification-denominator*. An
implementation plan ABOUT certification is not a cert board, and a false BLOCKING verdict on real
work is worse than a missed one. Now keyed on the plan pointing into `docs/development/certifications/`.

**Withdrawn (1) — a probe artifact, not a defect.** A tier-presence check reported the new row
missing from `--lean`, default and `--systemic`. It was reading a `checks` key the gate's JSON does
not emit; advisory rows live under `advisory`. Re-run correctly: present in all three. Recorded
because "fixing" a non-problem is its own defect.

**Not mine.** `--systemic` is red on `Documentation Drift` — two sibling plan files from June
(`2026-06-29-plan-watchdog-deploy-side.md`, `2026-06-30-plan-fabrik-deploy-readiness-gaps.md`).
Pre-existing, outside this plan's File Scope, and Tier 3 is never a completion gate.

## Pass Ledger

| Pass | finders | found | new | fixed |
|---:|---|---:|---:|---:|
| Pass 1 (WIDE) | native, all 7 classes | 2 | 2 | 1 + 1 withdrawn |
| **Pass 2 (terminal)** | native, same 7 re-swept | **0** | **0** | **0** |

`found: 0, fixed: 0` on the final look.

## Verification

```
$ python -m pytest tests/enforcement/test_certification_coverage.py -q
47 passed

$ python scripts/final_gate.py --check --json          # Tier 2
"status": "success"  (50 passed / 0 failed)

$ row present in --lean / default / --systemic         # advisory rows
True / True / True
```

11 mutants proven red-on-revert; two initially reported "pattern absent" because `ruff format` had
moved the target, and were re-run against the real text before any verdict was recorded — a mutation
that does not apply is not evidence.
