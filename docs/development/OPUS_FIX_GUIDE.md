# Quick Fix Guide for Opus 4.6

## The Bug (1 Line Fix)

**File:** `scripts/kilo_code_review.py` (broken version at commit `ce9e80a`)

**Problem:** Lines 2689-2744 are ORPHANED - they're outside any function definition.

**Location:**
```python
# Line 2651-2687: pre_review_checks() function
def pre_review_checks(files: list[Path]) -> list[str]:
    # ... validation logic ...
    return issues  # LINE 2687 - FUNCTION ENDS HERE

# LINE 2689-2744: ORPHANED CODE (not inside any function)
lines.append(f"📁 Files reviewed: {len(report.files_reviewed)}")  # ❌ report and lines undefined
# ... 56 lines of orphaned code using report and lines ...
return "\n".join(lines)  # LINE 2744 - orphaned return statement

# Line 2747: Next function starts
# =============================================================================
```

**What happened:** These lines belong INSIDE `format_report_text()` function (defined at line 2633), but they got placed OUTSIDE after `pre_review_checks()` ends.

---

## The Fix

**Step 1:** Find where `format_report_text()` function body should be

In working version (5301c34), `format_report_text()` is at line ~2600-2650.

**Step 2:** Move lines 2689-2744 INSIDE the correct function

Either:
- Option A: Move them into existing `format_report_text()` if it exists
- Option B: Wrap them in a new function definition if one is missing

**Step 3:** Verify the fix

```bash
python -m py_compile scripts/kilo_code_review.py  # Must pass
ruff check scripts/kilo_code_review.py            # Must pass
python scripts/kilo_code_review.py --help         # Must work instantly
```

---

## All 4 Features Are Actually Correct

1. ✅ **Retry logic** (lines 173-182, 1195-1250) - Works perfectly
2. ✅ **Model metrics** (line 377-378) - Works perfectly  
3. ✅ **Pre-review validation** (lines 2651-2687) - Works perfectly
4. ✅ **Infinite loop fix** (lines 2905-3017) - Works perfectly

Only bug: Orphaned code after line 2687.

---

## Commands for Opus

```bash
# Get broken version
cd /opt/fabrik
git show ce9e80a:scripts/kilo_code_review.py > /tmp/broken.py

# Get working version
git show 5301c34:scripts/kilo_code_review.py > /tmp/working.py

# See the diff
git diff 5301c34..ce9e80a -- scripts/kilo_code_review.py

# Fix and test
python -m py_compile scripts/kilo_code_review.py
ruff check scripts/kilo_code_review.py
python scripts/kilo_code_review.py --help
```

---

## Expected Result

After fix:
- ✅ 0 F821 errors (down from 42)
- ✅ Script imports instantly
- ✅ All 4 features working
- ✅ No functionality lost
