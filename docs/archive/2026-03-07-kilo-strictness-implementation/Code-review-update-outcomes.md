**Status:** COMPLETE (Implemented 2026-03-02, Verified 2026-03-07)

# Kilo Code Review Implementation Outcomes

What changed after implementation
1) Reviewer output becomes hard-contract JSON (no “best effort” parsing)

parse_review_output() will stop auto-filling missing fields and will hard-fail if JSON is missing or schema-invalid, returning a single <reviewer> BLOCKER issue.

Result: you no longer get “silently accepted” malformed reviewer output; bad output is detected immediately and forces a retry/FAIL path.

2) Every review now includes plan_coverage

ReviewResult gains plan_coverage, and schema requires it.

Result: each review explicitly states which plan requirements were satisfied/missing/partial, with evidence text.

3) BLOCKER/MAJOR findings must carry structured evidence

ReviewIssue gains evidence, and the schema requires evidence in the JSON object for issues.

Caller enforces evidence quality for BLOCKER/MAJOR (missing evidence → forced FAIL with <reviewer> BLOCKER inserted).

4) The review prompt will include deterministic gate results

You will run scripts/final_gate.py via the renamed run_pre_review_gates() and inject its compact summary into the review prompt via {gate_results}.

Result: the reviewer sees deterministic failures (tests/lint/etc.) and can cite them as evidence rather than inventing.

5) Schema failure triggers exactly one retry with a JSON skeleton

If the first reviewer output fails schema, _run_single_batch_review() retries once using an explicit skeleton and “JSON-only” instruction.

6) Token/cost accounting becomes accurate across retries

Instead of only using the last call, you track attempt_results and sum tokens/cost across attempts; stats["attempts"] is added.

Result: you get correct cost reporting when retries happen.

7) Optional risk-triggered multi-pass review

Risk assessment can trigger a second security-only pass using dataclasses.replace() to avoid config mutation.

Result: security-sensitive/large diffs get deeper coverage without changing the main config object.

What you will get explicitly (deliverables / outputs)
A) New/updated data fields in outputs

ReviewIssue.evidence (structured dict)

ReviewResult.plan_coverage (list of requirement coverage objects)

B) Stronger, machine-checkable review artifacts on disk

Iteration JSON (review_iter_*.json) will now include plan_coverage (so you can audit coverage per iteration).

A gate_output.txt artifact is written (safely) for debugging gate runs.

C) Deterministic enforcement behavior

You will reliably see one of these outcomes per review call:

Valid PASS/FAIL with schema-valid JSON, issues (with evidence), and plan_coverage.

Hard FAIL with <reviewer> BLOCKER if:

no JSON returned

schema invalid (after optional single retry)

evidence validation fails for BLOCKER/MAJOR

plan coverage incomplete

D) A test harness to prove validators work

New test file tests/test_kilo_review_validation.py covering schema/evidence/coverage/requirement extraction.

## Implementation Complete (2026-03-07)

**All changes verified in codebase:**

✅ `/opt/fabrik/requirements.txt` - jsonschema>=4.17.0 added

✅ `/opt/fabrik/scripts/kilo_code_review.py` - All features implemented:
- Dataclass additions (evidence, plan_coverage)
- Schema + validator (REVIEW_RESULT_SCHEMA)
- Plan extraction (extract_plan_requirements)
- Strict parser (no auto-fill)
- Gates injection (run_pre_review_gates)
- Retry + token accounting
- Multi-pass logic (assess_review_risk, run_multi_pass_review)

✅ `/opt/fabrik/tests/test_kilo_review_validation.py` - Test harness created
✅ `/opt/fabrik/tests/test_kilo_strictness_scenarios.py` - Scenario tests created

**READY TO ARCHIVE**
