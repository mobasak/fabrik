# Droid Exec Limits & Communication Reference

**Last Updated:** 2026-02-14

This document defines the technical limits and communication patterns for `droid exec` integration in Fabrik.

## Communication Mechanism

| Method | Flag | Use Case |
|--------|------|----------|
| Direct prompt | `droid exec "prompt"` | Short prompts (<4KB) |
| File input | `--file <path>` | Large prompts, avoids ARG_MAX |
| JSON output | `-o json` | Machine parsing, token tracking |
| Stream JSON | `-o stream-json` | Real-time tool monitoring |

## System Limits

| Limit | Value | Source |
|-------|-------|--------|
| **Command output** | 64KB | Factory docs |
| **Hook timeout** | 60s (configurable) | Factory docs |
| **CLI default timeout** | 1800s | Factory docs |
| **Recommended task timeout** | 300-600s | Best practice |

## Token Context Windows (Per Model)

| Model Family | Typical Context | Notes |
|--------------|-----------------|-------|
| GPT-5.x | 128K-256K tokens | Varies by variant |
| Claude 4.x | 200K tokens | Extended thinking available |
| Gemini 3.x | 1M+ tokens | Largest context |

## Session Management

### Critical Rules

1. **Same session ID = same context** - Reusing session ID maintains conversation history
2. **Model change = context loss** - Changing models mid-session loses/translates context
3. **Session TTL** - Sessions should be scoped to tasks (PR, branch, feature)

### When to Persist Sessions

| Scenario | Persist Session? | Reason |
|----------|------------------|--------|
| Multi-step task (analyze→code→review) | ✅ Yes | Shared context reduces tokens |
| Independent jobs in queue | ❌ No | Strict isolation needed |
| Same artifact, same model | ✅ Yes | Prefix caching benefits |
| Different models | ❌ No | Context will be lost anyway |

### Session API

```python
from scripts.droid_session import get_or_create_session, invalidate_session

# Get/create session for a context
session_id = get_or_create_session("feature-auth", model="gpt-5.1-codex-max")

# Use in droid exec
# droid exec --session-id {session_id} -m gpt-5.1-codex-max "..."

# Invalidate when done (e.g., PR merged)
invalidate_session("feature-auth")
```

## Model Validation Rules

### Price Multiplier Requirement

Models without known price multipliers **cannot be used automatically**. They require explicit user approval.

```python
from scripts.droid_model_updater import is_model_safe_for_auto, get_models_without_prices

# Check if model is safe for automatic use
is_safe, reason = is_model_safe_for_auto("gpt-5.3-codex")
if not is_safe:
    print(f"⚠️  {reason}")
    # Require explicit user approval before proceeding

# Get list of models requiring approval
no_price_models = get_models_without_prices()
# Currently: claude-opus-4-6-fast, glm-5, gpt-5.3-codex
```

### Deprecation Handling

When a model is deprecated:
- Session ID may still work but context quality is uncertain
- Always check `is_model_available()` before use
- Update `config/models.yaml` to use alternatives

## Token Tracking

### Per-Run Tracking (JSON Output)

```bash
# Run with JSON output to get token counts
output=$(droid exec -o json -m gpt-5.1-codex-max "task")

# Parse usage
echo "$output" | jq '.usage'
# {
#   "input_tokens": 40375,
#   "output_tokens": 1511,
#   "cache_read_input_tokens": 31148
# }
```

### Python API

```python
from scripts.droid_session import log_token_usage, get_token_usage_summary

# After parsing JSON output
log_token_usage(
    session_id="abc-123",
    usage={"input_tokens": 40375, "output_tokens": 1511},
    model="gpt-5.1-codex-max",
    context_key="feature-auth"
)

# Get usage summary
summary = get_token_usage_summary()
print(f"Last 24h: {summary['total_tokens']} tokens across {summary['run_count']} runs")
```

### Monthly Quota

| Plan | Tokens/Month | Bonus | Total |
|------|--------------|-------|-------|
| Pro | 10M | +10M | 20M |
| Max | 100M | +100M | 200M |

Overage: $2.70/million Standard Tokens

## Rate Limiting

- Factory enforces tier-based rate limits
- On rate limit: non-zero exit code with "Rate limit exceeded" message
- **Recommendation:** Implement exponential backoff

```python
import time

def run_with_backoff(cmd, max_retries=3):
    for attempt in range(max_retries):
        result = subprocess.run(cmd, capture_output=True)
        if result.returncode == 0:
            return result
        if "Rate limit exceeded" in result.stderr.decode():
            wait = 2 ** attempt * 5  # 5s, 10s, 20s
            time.sleep(wait)
        else:
            break
    return result
```

## Best Practices

1. **Always use `-o json`** for programmatic access
2. **Parse and log token usage** after every run
3. **Scope sessions to tasks** (branch/PR), not globally
4. **Check model safety** before automatic use
5. **Implement backoff** for rate limit handling
6. **Use file input** for prompts >4KB

## Files

| File | Purpose |
|------|---------|
| `scripts/droid_session.py` | Session management API |
| `scripts/droid_model_updater.py` | Model validation & price checking |
| `scripts/.droid_sessions.json` | Active session cache |
| `scripts/.droid_token_usage.jsonl` | Token usage log |
| `~/.factory/hooks/session-end-token-log.py` | SessionEnd hook |
