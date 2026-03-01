Phase 3 Step 3: Add pre-review validation to kilo_code_review.py

Added pre_review_checks() function to validate files BEFORE calling Kilo API.

VALIDATION CHECKS:
1. File existence check
2. File size check (>500KB blocks review)
3. Python syntax validation (compile check)
4. Encoding validation (UTF-8)
5. Empty file detection

FAIL-FAST BEHAVIOR:
- Returns ERROR report immediately if validation fails
- Does NOT call Kilo API (saves credits)
- Issues marked as BLOCKER/VALIDATION category
- Clear fix hints provided

BENEFITS:
- Catch common issues without spending API credits
- Faster feedback loop (no network call)
- Clearer error messages for file-level problems
- Prevents wasting tokens on invalid input

EXAMPLE BLOCKED SCENARIOS:
- Large files (>500KB) blocked (must be manually split)
- Python files with syntax errors
- Missing/empty files
- Binary/encoding issues
