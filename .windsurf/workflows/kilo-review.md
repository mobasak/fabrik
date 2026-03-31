---
description: Kilo_Review - Automated code review workflow (review → fix → re-review loop)
---

# Kilo_Review — Automated Code Review with Fix Loop

## When to Use

When you need:
- Automated code review before commit
- Review → fix → re-review workflow
- Quality gate with exit codes
- Review staged or changed files
- Multi-iteration fix loop until clean

**Uses:**
- `Local_Review_llama70b` (70B) for reviews
- `Local_Fixer_ds16b` (16B) for fixes

**Cost:** FREE (local models)

## How to Use

### Review staged files
// turbo
```bash
/opt/fabrik/scripts/Kilo_Review.sh staged
```

### Review working tree changes
// turbo
```bash
/opt/fabrik/scripts/Kilo_Review.sh changed
```

### Auto-fix loop (review → fix → re-review)
```bash
/opt/fabrik/scripts/Kilo_Review.sh auto-fix src/ --max-iterations 3
```

### Review specific files
```bash
/opt/fabrik/scripts/Kilo_Review.sh review src/api/auth.py tests/test_auth.py
```

## Features

- **Automated Loop:** Review → Fix → Re-Review until clean or max iterations
- **Exit Codes:**
  - `0` - Review passed (PASS verdict)
  - `1` - Review failed (issues remaining)
  - `2` - Error (script failure)
- **Hardware Protection:** Both agents use Global Sequential Guard
- **Session Continuity:** Can continue existing review sessions
- **Zero Cost:** No API charges

## Important: Stage All Files First

**RULE:** Before running `Kilo_Review.sh staged`, always stage ALL uncommitted files:

```bash
git add -A
/opt/fabrik/scripts/Kilo_Review.sh staged
```

The script warns if unstaged files exist, but it's better to stage everything first.

## Examples

```bash
# Quick review before commit
git add -A
/opt/fabrik/scripts/Kilo_Review.sh staged

# Auto-fix with max 3 iterations
git add -A
/opt/fabrik/scripts/Kilo_Review.sh auto-fix src/ --max-iterations 3

# Continue existing session
/opt/fabrik/scripts/Kilo_Review.sh auto-fix src/ --session continue

# Review specific files only
/opt/fabrik/scripts/Kilo_Review.sh review src/api/auth.py
```

## When NOT to Use

- For interactive review only → use `/local-review` instead
- For quick bug fix → use `/local-fixer` instead
- For documentation → use `/local-docs` instead
- For new features → use `/local-coder` instead

## Workflow Details

1. **Review Phase:** `Local_Review_llama70b` analyzes code
2. **Fix Phase:** If issues found, `Local_Fixer_ds16b` applies fixes
3. **Re-Review Phase:** `Local_Review_llama70b` validates fixes
4. **Loop:** Repeats until clean or max iterations reached
5. **Exit:** Returns appropriate exit code for CI/CD integration
