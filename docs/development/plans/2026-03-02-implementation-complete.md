# Kilo Strictness - Complete Implementation Guide

**All corrections applied. Ready to implement.**

---

## ⚠️ CRITICAL FAILURE POINTS (Must Avoid)

### 1. parse_review_output Must NOT Auto-Fill
**Current Problem:** Existing code silently defaults missing fields (verdict, summary, issues)
**Required:** Return `<reviewer>` BLOCKER if schema validation fails. NO fallbacks, NO assumptions.
**Why it matters:** Auto-filling defeats hard gating - invalid output must be rejected, not silently fixed.

### 2. Schema vs Validator Policy (Intentional Split)
**Schema enforces:** evidence field present on ALL issues (BLOCKER, MAJOR, MINOR)
**validate_evidence() enforces:** quality of evidence for BLOCKER/MAJOR only
**Why:** Schema catches missing fields at JSON level, validator checks meaningful content for critical issues
**This split is intentional and must remain consistent**

### 3. Token Accounting Must Sum ALL Attempts
**Track:** `attempt_results = []`
**First call:** `attempt_results.append(result)`
**Retry:** `attempt_results.append(retry_result)`
**Final:** Sum input_tokens, output_tokens, cost across ALL attempts
**Why it matters:** Accurate cost tracking, especially when retry happens

### 4. Plan Coverage Must Be Persisted
**Required:** Add `"plan_coverage": result.plan_coverage,` to iteration_data dict
**Saved to:** `review_iter_*.json`
**Must cover:** Extracted requirements OR at least 1 generic entry if none extracted

---

## Quick Reference

### Files to Modify
1. `/opt/fabrik/requirements.txt` - Add `jsonschema>=4.17.0`
2. `/opt/fabrik/scripts/kilo_code_review.py` - 14 explicit changes (see below)
3. `/opt/fabrik/tests/test_kilo_review_validation.py` - NEW file

### All Corrections Applied
1. ✅ Async-safe retry (no asyncio.run in parse)
2. ✅ Token accounting (sum all attempts, not just final call)
3. ✅ Safe gate write (check SESSION_DIR exists)
4. ✅ Config copy (dataclasses.replace, not aliasing)
5. ✅ Pytest format (standard discovery)
6. ✅ Renamed function (run_pre_review_gates, avoid collision)
7. ✅ Gate injection to prompt ({gate_results} placeholder)
8. ✅ JSON skeleton in retry prompt
9. ✅ NO auto-fill in parse_review_output
10. ✅ Evidence policy split (schema all, validator BLOCKER/MAJOR)
11. ✅ Plan coverage persistence

## Implementation Checklist

- [x] Add jsonschema to requirements.txt
- [x] Add imports (line 44): `from dataclasses import replace`, `import jsonschema`
- [x] Update ReviewIssue: add `evidence: dict[str, Any] | None = None`
- [x] Update ReviewResult: add `plan_coverage: list[dict[str, Any]] = field(default_factory=list)`
- [x] Add schema validator after line 110 (REVIEW_RESULT_SCHEMA + validate_review_schema)
- [x] Add plan extraction (extract_plan_requirements + format_requirements_for_prompt)
- [x] Replace parse_review_output (pure sync, no asyncio.run)
- [x] Add validate_evidence + validate_plan_coverage
- [x] Add run_pre_review_gates + format_gate_results_compact (renamed)
- [x] Replace REVIEW_PROMPT_TEMPLATE (add {gate_results} placeholder)
- [x] Replace _run_single_batch_review (retry + token accounting + safe gate write)
- [x] Add risk assessment (assess_review_risk + run_multi_pass_review with dataclasses.replace)
- [x] Update run_review (use multi-pass on risk)
- [x] Update iteration save: add `"plan_coverage": result.plan_coverage`
- [x] Create pytest tests
- [x] Update DOC_REVIEW_PROMPT_TEMPLATE with evidence/plan_coverage fields
- [x] Update VERIFY_PROMPT_TEMPLATE with evidence/plan_coverage and fix categories
- [x] Add doc/verify mode bypass for plan coverage validation
- [x] Fix full mode to retrieve diff for risk assessment
- [x] Broaden retry logic to catch no-JSON failures (not just schema)
- [x] Add plan coverage normalization for REQ-/R/B prefix handling

## Testing

```bash
pip install -r requirements.txt
pytest tests/test_kilo_review_validation.py -v
python scripts/kilo_code_review.py review src/file.py --plan "Test" --output json
```

## Full implementation details in companion files:
- `2026-03-02-implementation-step-by-step.md` (Steps 1-5)
- `2026-03-02-code-changes-summary.md` (Code snippets)
