---
description: Local_Coder_qwen32b - Implement features with local LLM (qwen32b, 32B, ~15-25 tok/s)
---

# Local_Coder_qwen32b — Coding with Local LLM

## When to Use

When you need to:
- Implement new features
- Write new code or create files
- Generate boilerplate or scaffolding
- Add functionality to existing code

**Hardware:** Uses Ryzen AI 9 + RAM (hybrid-cpu), ~15-25 tok/s

**Cost:** FREE (local model)

## How to Use

// turbo
```bash
/opt/fabrik/scripts/Local_Coder_qwen32b.sh "implement user authentication with JWT"
```

## Features

- **Hardware Protection:** Global Sequential Guard prevents GPU/RAM overload
- **Reuses Traycer Agent:** Calls `coding-1-fabrik-coder-qwen32b-local` CLI agent
- **Stdin Support:** Can pipe context from Cascade
- **Zero Cost:** No API charges

## Examples

```bash
# Direct invocation
/opt/fabrik/scripts/Local_Coder_qwen32b.sh "add Stripe subscription integration"

# With stdin (Cascade context)
echo "Create a health check endpoint for FastAPI" | /opt/fabrik/scripts/Local_Coder_qwen32b.sh

# Complex task
/opt/fabrik/scripts/Local_Coder_qwen32b.sh "implement real-time WebSocket notifications with Redis pub/sub"
```

## When NOT to Use

- For simple documentation updates → use `/local-docs` instead
- For bug fixes → use `/local-fixer` instead
- For code review → use `/local-review` or `/kilo-review` instead
