# Droid Exec Integration Guide

**Last Updated:** 2026-02-14

Complete guide for Cascade and other AI agents working with droid exec in Fabrik.

## Quick Reference

```python
# Essential imports
from scripts.droid_model_updater import (
    is_model_safe_for_auto,  # Check if model can be used automatically
    get_model_price,          # Get price multiplier for cost estimation
    get_models_without_prices, # Models requiring explicit approval
    is_model_available,       # Check if model exists
    ensure_models_fresh,      # Refresh model cache (daily)
)

from scripts.droid_session import (
    get_or_create_session,    # Persist session IDs
    log_token_usage,          # Track per-run token usage
    get_quota_status,         # Get remaining tokens
    estimate_run_cost,        # Estimate cost before running
    check_quota_warning,      # Get quota warning message
)
```

## Critical Rules

### 1. Model Safety (ENFORCED)

Models **without price multipliers cannot be used automatically**:

```python
safe, reason = is_model_safe_for_auto("gpt-5.3-codex")
if not safe:
    print(f"⚠️ {reason}")  # Requires explicit user approval
```

**Currently unpriced models:** `claude-opus-4-6-fast`, `glm-5`, `gpt-5.3-codex`

### 2. Session Management (CRITICAL)

| Rule | Consequence |
|------|-------------|
| Same session ID | Same context maintained |
| Different model | Context LOST (new session auto-created) |
| Session expired (24h) | Context LOST |

```python
# Get/create session for a context (e.g., branch, PR)
session_id = get_or_create_session("feature-auth", model="gpt-5.1-codex-max")

# Use in droid exec
# droid exec --session-id {session_id} -m gpt-5.1-codex-max -o json "..."

# Invalidate when done (PR merged)
invalidate_session("feature-auth")
```

### 3. JSON Output (REQUIRED)

Always use `-o json` for machine parsing:

```bash
output=$(droid exec -m gpt-5.1-codex-max -o json "task")
```

Response includes:
```json
{
  "session_id": "uuid",
  "result": "...",
  "usage": {
    "input_tokens": 40375,
    "output_tokens": 1511,
    "cache_read_input_tokens": 31148
  }
}
```

### 4. Token Tracking (MANDATORY)

After every run, log usage:

```python
import json
from scripts.droid_session import log_token_usage

response = json.loads(output)
log_token_usage(
    session_id=response["session_id"],
    usage=response["usage"],
    model="gpt-5.1-codex-max",
    context_key="code-review"
)
```

### 5. Cost Estimation (RECOMMENDED)

Before expensive runs, estimate cost:

```python
from scripts.droid_session import estimate_run_cost

estimate = estimate_run_cost("claude-opus-4-6", estimated_tokens=50000)
# estimate["multiplier"] = 2.0
# estimate["standard_tokens"] = 100000
# estimate["budget_percent"] = 1.13  # % of remaining budget
# estimate["warning"] = False
```

## System Limits

| Limit | Value |
|-------|-------|
| Output per command | 64KB |
| Hook timeout | 60s |
| CLI default timeout | 1800s |
| Recommended task timeout | 300-600s |

## Billing

| Plan | Tokens/Month | Price | Cycle |
|------|--------------|-------|-------|
| Pro | 20,000,000 | $20 | 27th-26th |
| Max | 200,000,000 | $200 | 27th-26th |

Overage: $2.70/million standard tokens

```bash
# Check quota status
python scripts/droid_session.py quota --usage 11184379
```

## Price Multipliers (Token Cost)

Models have different costs per token:

| Model | Multiplier | Cost |
|-------|------------|------|
| gemini-3-flash-preview | 0.2x | Cheapest |
| gpt-5.1-codex-max | 0.5x | Low |
| gpt-5.1 | 1.0x | Standard |
| claude-opus-4-6 | 2.0x | Premium |

**Standard tokens = raw_tokens × multiplier**

## File Locations

| File | Purpose |
|------|---------|
| `scripts/droid_model_updater.py` | Model validation, price fetching |
| `scripts/droid_session.py` | Session management, billing, token tracking |
| `scripts/droid-review.sh` | Code review wrapper with token logging |
| `scripts/.model_update_cache.json` | Cached models + prices (24h TTL) |
| `scripts/.droid_sessions.json` | Active session IDs |
| `scripts/.droid_token_usage.jsonl` | Token usage log |
| `config/models.yaml` | Model configurations |
| `~/.factory/hooks/session-end-token-log.py` | Auto-log hook |

## Wrapper Scripts (USE THESE)

| Script | When to Use |
|--------|-------------|
| `scripts/droid-review.sh` | Code review |
| `scripts/docs_updater.py` | Documentation updates |
| `scripts/droid_core.py` | Task execution |

**DO NOT** run `droid exec` directly when wrappers exist.

## Changes Made Today (2026-02-14)

1. **Model price fetching** - Daily fetch from Factory docs
2. **Model safety validation** - Blocks unpriced models
3. **Session management** - Persists sessions per context
4. **Token tracking** - Per-run logging with JSON output
5. **Billing integration** - Quota status, daily budget
6. **Cost estimation** - Pre-run cost calculation using multipliers

## For Other Cascade Agents

When working in this codebase:

1. **Always check model safety** before auto-selecting models
2. **Use JSON output** (`-o json`) for all droid exec calls
3. **Log token usage** after every run
4. **Persist session IDs** for multi-step tasks
5. **Check quota** before large operations
6. **Use wrapper scripts** when they exist
