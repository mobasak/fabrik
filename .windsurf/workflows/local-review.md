---
description: Local_Review_llama70b - Deep code review with local LLM (llama70b, 70B, ~8-12 tok/s)
---

# Local_Review_llama70b — Interactive Code Review with Local LLM

## When to Use

When you need:
- Deep architectural review
- Security analysis
- Bug identification in existing code
- Code quality assessment
- Identify potential issues before commit

**Hardware:** Uses CPU-only (70B model, low-context to avoid RAM pressure), ~8-12 tok/s

**Cost:** FREE (local model)

## How to Use

// turbo
```bash
/opt/fabrik/scripts/Local_Review_llama70b.sh "review the authentication implementation in src/api/auth.py"
```

## Features

- **Deep Analysis:** 70B model provides thorough architectural review
- **Hardware Protection:** Global Sequential Guard prevents concurrent loading
- **Temperature 0:** Absolute logic, deterministic reviews
- **Zero Cost:** No API charges

## Examples

```bash
# Review specific implementation
/opt/fabrik/scripts/Local_Review_llama70b.sh "review this API endpoint for security issues"

# With stdin (Cascade context)
echo "Check for SQL injection vulnerabilities in the database layer" | /opt/fabrik/scripts/Local_Review_llama70b.sh

# Architectural review
/opt/fabrik/scripts/Local_Review_llama70b.sh "review the microservice architecture in this project"
```

## When NOT to Use

- For automated review loop → use `/kilo-review` instead
- For quick bug fixes → use `/local-fixer` instead
- For documentation → use `/local-docs` instead

## Note

This is **interactive review only**. For automated review → fix → re-review workflow, use `/kilo-review`.
