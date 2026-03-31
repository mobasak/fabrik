---
description: Local_Fixer_ds16b - Fast bug fixes with local LLM (deepseek16b, 16B, ~40-60 tok/s)
---

# Local_Fixer_ds16b — Fast Bug Fixing with Local LLM

## When to Use

When you need to:
- Fix specific bugs or errors
- Debug issues quickly
- Apply surgical code fixes
- Resolve test failures
- Fix linting or type errors

**Hardware:** Uses GPU + RAM spillover (hybrid-gpu), ~40-60 tok/s

**Cost:** FREE (local model)

## How to Use

// turbo
```bash
/opt/fabrik/scripts/Local_Fixer_ds16b.sh "fix the null pointer exception in src/api/auth.py:45"
```

## Features

- **Fast Execution:** 16B model on GPU provides quick fixes (~40-60 tok/s)
- **Surgical Precision:** DeepSeek specialized in logical reasoning
- **Hardware Protection:** Global Sequential Guard prevents concurrent loading
- **Minimal Edits:** Follows existing code style, no refactoring
- **Zero Cost:** No API charges

## Examples

```bash
# Fix specific error
/opt/fabrik/scripts/Local_Fixer_ds16b.sh "fix the TypeScript error in app/api/route.ts:23"

# Debug API issue
/opt/fabrik/scripts/Local_Fixer_ds16b.sh "debug why API returns 500 on POST /users"

# Fix test failure
/opt/fabrik/scripts/Local_Fixer_ds16b.sh "fix the failing test in tests/test_auth.py"

# With stdin (Cascade context)
echo "Resolve the import error in src/utils/helpers.py" | /opt/fabrik/scripts/Local_Fixer_ds16b.sh
```

## When NOT to Use

- For automated fix loop → use `/kilo-review auto-fix` instead
- For new features → use `/local-coder` instead
- For documentation → use `/local-docs` instead
- For architectural review → use `/local-review` instead
