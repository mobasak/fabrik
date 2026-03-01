BUGFIX: Fix infinite loop in kilo_code_review.py run_precommit

ROOT CAUSE:
The run_precommit() function would hang indefinitely when ruff had unfixable errors because:
1. Lines 2958-2973: When ruff fails, runs ruff --fix and continues
2. If ruff can't actually fix the issues, it returns the same errors
3. Loop continues with same error, triggering ruff --fix again
4. No progress detection = infinite loop

SYMPTOMS:
- kilo_code_review.py hangs when reviewing files
- User has to Ctrl+C to cancel
- final_gate.py also hangs (calls kilo review internally)

FIX:
Added progress tracking:
1. Store previous_output before each iteration
2. Before running ruff --fix, check if output == previous_output
3. If same error twice in a row, ruff can't fix it -> return False
4. This breaks the infinite loop and provides clear error message

CHANGES:
- Added previous_output variable to track iteration state
- Added comparison check before ruff --fix
- Returns False with clear message when stuck

EXPECTED BEHAVIOR:
- If ruff can fix: loops until clean (max 5 iterations)
- If ruff can't fix: detects after 1 retry, returns False with message
- No more infinite loops
