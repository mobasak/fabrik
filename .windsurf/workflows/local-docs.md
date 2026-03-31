---
description: Local_Documentator_llama3.1-8b - Instant documentation with local LLM (llama8b, 8B, ~80-100 tok/s)
---

# Local_Documentator_llama3.1-8b — Fast Documentation with Local LLM

## When to Use

When you need to:
- Generate or update README files
- Create CHANGELOG entries
- Write documentation
- Generate code comments
- Update API documentation

**Hardware:** Uses GPU only (8B, fits in VRAM), ~80-100 tok/s (instant)

**Cost:** FREE (local model)

**Special Feature:** **Fast-Path** - Bypasses lock when 5.5GB VRAM free + GPU idle

## How to Use

// turbo
```bash
/opt/fabrik/scripts/Local_Documentator_llama3.1-8b.sh "update README with new API endpoints"
```

## Features

- **Blazing Fast:** Runs entirely in GPU VRAM (~80-100 tok/s)
- **Fast-Path Optimization:** Bypasses hardware lock when GPU is idle
- **Hardware Protection:** Falls back to Global Sequential Guard if needed
- **Zero Cost:** No API charges

## Examples

```bash
# Generate CHANGELOG
/opt/fabrik/scripts/Local_Documentator_llama3.1-8b.sh "generate CHANGELOG entry for today's commits"

# Update README
/opt/fabrik/scripts/Local_Documentator_llama3.1-8b.sh "add installation instructions to README"

# API documentation
/opt/fabrik/scripts/Local_Documentator_llama3.1-8b.sh "document the /api/users endpoints"

# With stdin (Cascade context)
echo "Write docstrings for the auth module" | /opt/fabrik/scripts/Local_Documentator_llama3.1-8b.sh
```

## When NOT to Use

- For code implementation → use `/local-coder` instead
- For bug fixes → use `/local-fixer` instead
- For code review → use `/local-review` or `/kilo-review` instead

## Performance Note

This is the **fastest** local workflow due to:
1. Small 8B model fits entirely in 8GB VRAM
2. Fast-path bypasses lock when GPU idle
3. Instant responses for documentation tasks
