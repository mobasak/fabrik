**Status:** COMPLETE (Implemented 2026-03-02, Verified 2026-03-07)

# Kilo Review Strictness Enforcement

## Goal

Implement always-on hard-gated Kilo code review workflow with strict JSON schema validation, evidence requirements, plan coverage validation, and risk-based multi-pass reviews.

## DONE WHEN

- [x] Plan created with all corrections applied
- [x] All dataclasses extended with new fields
- [x] JSON schema validator implemented
- [x] Plan requirement extraction working
- [x] Parse function is pure sync (no asyncio.run)
- [x] Evidence validation enforces structured evidence
- [x] Plan coverage validation checks completeness
- [x] Pre-review gates run deterministically
- [x] Prompt template includes gate results
- [x] Retry logic tracks token costs accurately
- [x] Multi-pass uses dataclasses.replace
- [x] Pytest test harness passes all tests
- [x] Implementation docs complete
- [x] DOC_REVIEW_PROMPT_TEMPLATE updated with evidence/plan_coverage
- [x] VERIFY_PROMPT_TEMPLATE updated with evidence/plan_coverage
- [x] Doc/verify modes bypass plan coverage validation
- [x] Full mode retrieves diff for risk assessment
- [x] Retry logic broadened to catch no-JSON failures
- [x] Plan coverage normalization handles REQ-/R/B prefixes

## Out of Scope

- VS Code extension development
- Kilo CLI itself (we only integrate with it)
- Changes to final_gate.py
- Pre-commit hook modifications

## Critical Requirements

### 1. parse_review_output Must NOT Auto-Fill
**CURRENT PROBLEM:** Existing code silently defaults missing fields (verdict, summary, issues) → defeats hard gating
**REQUIRED:** Return `<reviewer>` BLOCKER if schema validation fails. NO fallbacks, NO assumptions.

### 2. Schema vs Validator Policy (INTENTIONAL SPLIT)
- **Schema enforces:** evidence field present on ALL issues (BLOCKER, MAJOR, MINOR)
- **validate_evidence() enforces:** quality of evidence for BLOCKER/MAJOR only
- **Why:** Schema catches missing fields at JSON level, validator checks meaningful content
- **This split is intentional and must remain consistent**

### 3. Token Accounting Across Retries
- Track ALL attempts: `attempt_results = []`
- First attempt: `attempt_results.append(result)`
- On retry: `attempt_results.append(retry_result)`
- Sum `input_tokens`, `output_tokens`, `cost` across all attempts
- Attach summed totals to final `ReviewResult`

### 4. Plan Coverage Persistence
- MUST be in `iteration_data` dict: `"plan_coverage": result.plan_coverage,`
- MUST cover extracted requirements OR at least 1 generic entry if none extracted
- Persisted to `review_iter_*.json`

### 5. Async-Safe Retry
- `parse_review_output()` is pure sync (no asyncio.run)
- Retry logic in `_run_single_batch_review()` (already async)
- Second `await run_kilo(...)` with JSON skeleton if schema fails

### 6. Fault-Tolerant Gates (Renamed)
- Renamed: `run_final_gate()` → `run_pre_review_gates()` (avoid collision)
- Returns structured failure if script missing/errors
- Always injects into prompt via `{gate_results}` placeholder

### 7. Config Copy for Multi-Pass
- Use `dataclasses.replace(config, skip_categories={...})`
- NOT `security_config = config` (aliasing breaks isolation)

### 8. Safe Gate File Write
- Check `SESSION_DIR` exists and session_id is set before writing
- Handle empty raw_output safely (missing script, timeout, exception cases)
- MINOR issues can have empty/minimal evidence without validation failure

## Implementation Steps

See detailed implementation in:
- `2026-03-02-implementation-step-by-step.md`
- `2026-03-02-code-changes.md`

## Testing

```bash
# Install dependencies
pip install -r requirements.txt

# Run test harness
pytest tests/test_kilo_review_validation.py -v

# Test with real review
python scripts/kilo_code_review.py review src/file.py \
  --plan "Test task" \
  --output json
```

## Implementation Complete (2026-03-07)

**Actual Timeline:** 4 hours (as estimated)

**All requirements verified in codebase:**
- ✅ All 14 steps implemented in `scripts/kilo_code_review.py`
- ✅ Test harness complete: `tests/test_kilo_review_validation.py`, `tests/test_kilo_strictness_scenarios.py`
- ✅ No auto-fill in parse_review_output - strict schema enforcement
- ✅ Evidence + plan coverage validation working
- ✅ Multi-pass review for high-risk changes
- ✅ Token accounting across retries

**READY TO ARCHIVE**
