# ✅ READY TO IMPLEMENT - Kilo Review Strictness

**Status:** COMPLETE (Implemented 2026-03-02, Verified 2026-03-07)
**Date:** 2026-03-02
**Implementation Time:** 4 hours (as estimated)

---

## Implementation Order (14 Steps)

| Step | Task | Time | File |
|------|------|------|------|
| 1 | Add jsonschema dependency | 5min | requirements.txt |
| 2 | Update dataclasses (evidence, plan_coverage) | 10min | kilo_code_review.py |
| 3 | Update iteration persistence | 5min | kilo_code_review.py |
| 4 | Add imports | 5min | kilo_code_review.py |
| 5 | Add schema validator | 30min | kilo_code_review.py |
| 6 | Add requirement extraction | 20min | kilo_code_review.py |
| 7 | Replace parse_review_output (NO AUTO-FILL) | 20min | kilo_code_review.py |
| 8 | Add validators (evidence + coverage) | 30min | kilo_code_review.py |
| 9 | Add gates (renamed run_pre_review_gates) | 15min | kilo_code_review.py |
| 10 | Replace REVIEW_PROMPT_TEMPLATE | 15min | kilo_code_review.py |
| 11 | Replace _run_single_batch_review | 45min | kilo_code_review.py |
| 12 | Add multi-pass (assess + run) | 20min | kilo_code_review.py |
| 13 | Update run_review() routing | 10min | kilo_code_review.py |
| 14 | Create pytest tests | 30min | test_kilo_review_validation.py |

**Total: ~4 hours**

---

## Critical Requirements

### 1. NO AUTO-FILL in parse_review_output
- Current code silently defaults missing fields → defeats gating
- Return `<reviewer>` BLOCKER if schema fails
- NO fallbacks, NO assumptions

### 2. Schema vs Validator Split (Intentional)
- **Schema enforces:** evidence on ALL issues
- **Validator checks quality:** BLOCKER/MAJOR only
- MINOR can have minimal evidence

### 3. Token Accounting
- Track: `attempt_results = []`
- Sum across ALL attempts (not just final call)

### 4. Plan Coverage Persistence
- Add: `"plan_coverage": result.plan_coverage,` to iteration_data
- Save to: `review_iter_*.json`

---

## Detailed Implementation

See complete code in:
- `2026-03-02-requirements-final.md` - All 14 steps with full code
- `2026-03-02-execution-order.md` - Steps 1-8 detailed
- `2026-03-02-implementation-step-by-step.md` - Original detailed guide
- `2026-03-02-code-changes-summary.md` - Quick reference

---

## Start Command

```bash
# Step 1
echo "jsonschema>=4.17.0" >> /opt/fabrik/requirements.txt
pip install -r /opt/fabrik/requirements.txt

# Verify
python -c "import jsonschema; print('✓ jsonschema installed:', jsonschema.__version__)"
```

**Then proceed with Steps 2-14.**

---

## Implementation Complete

All requirements implemented and verified in codebase.
All 14 steps completed successfully.

**READY TO ARCHIVE**
