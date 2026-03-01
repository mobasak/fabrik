# Kilo Usage Guide

**Last Updated:** 2026-03-01

How to use Kilo CLI agents and the review script - both automatically and manually.

---

## Quick Start

### Automatic Usage (Traycer Integration)

When using Traycer, agents are invoked automatically:
1. Select an agent from the Traycer UI (sorted A-Z by tier)
2. Traycer passes your prompt to the agent script
3. Agent runs Kilo CLI with configured model/variant
4. Results return to Traycer

### Manual Usage (CLI)

```bash
# Basic review (auto-selects model based on risk)
python scripts/kilo_code_review.py review src/myfile.py

# Use free tier (development, iteration)
python scripts/kilo_code_review.py review src/ --strategy free

# Budget-constrained review
python scripts/kilo_code_review.py review src/ --max-cost 0.50

# Stats on usage
python scripts/kilo_code_review.py stats --by-model --by-filetype
```

---

## Cost-Aware Strategies

### Available Strategies

| Strategy | Starting Tier | Escalation Path | Max Cost |
|----------|---------------|-----------------|----------|
| `free` | Free ($0) | Free → Economy → Balanced → Strong | ~$3/review |
| `economy` | Economy (~$0.02/M) | Economy → Balanced → Strong → Prime | ~$5/review |
| `standard` | Balanced (~$0.5/M) | Balanced → Strong → Prime | ~$25/review |
| `premium` | Strong (~$3/M) | Strong → Prime | ~$50/review |
| `critical` | Prime (~$5/M) | Prime only | ~$50/review |

### Automatic Strategy Selection

Without `--strategy`, the script selects based on file risk:

| Risk Level | Files | Auto Strategy |
|------------|-------|---------------|
| **LOW** | `.md`, `.rst`, config | `free` |
| **MEDIUM** | Normal code | `economy` |
| **HIGH** | `src/`, `scripts/`, `.sh` | `standard` |
| **CRITICAL** | `auth/`, `security/`, payments | `premium` |

### Examples

```bash
# Development: start free, escalate if needed
python scripts/kilo_code_review.py review docs/ --strategy free

# Production: standard review
python scripts/kilo_code_review.py review src/api/ --strategy standard

# Security audit: premium tier
python scripts/kilo_code_review.py review src/auth/ --strategy premium

# Budget cap: stop escalation at $1
python scripts/kilo_code_review.py review src/ --max-cost 1.00

# No escalation: stay at initial tier
python scripts/kilo_code_review.py review src/ --strategy economy --no-escalate
```

---

## Agent Tiers

### 40 Agents by Tier (A-Z sorted in Traycer UI)

| Tier | Count | Cost | Best For |
|------|-------|------|----------|
| **Auto** | 2 | Variable | Unknown tasks (kilo/auto routing) |
| **Balanced** | 6 | $0.02-14/M | Most production work |
| **Economy** | 8 | $0.02-0.36/M | Simple tasks, docs |
| **Free** | 9 | $0 | Development, iteration |
| **Prime** | 3 | $5-168/M | Critical, final reviews |
| **Strong** | 6 | $0.02-15/M | Complex logic, security |
| **Ultra** | 6 | ~$0.25/M | Codestral specialized |

### Direct Agent Usage

```bash
# Debug mode for any agent
KILO_DEBUG=1 ~/.traycer/cli-agents/Free01-minimax21-code-medium-i000-o000.sh

# Track costs
KILO_TRACK_COST=1 ~/.traycer/cli-agents/Economy01-flash3-code-minimal-i000-o002.sh

# Custom timeout
KILO_TIMEOUT=120 ~/.traycer/cli-agents/Strong04-sonnet46-review-max-i300-o1500.sh
```

---

## Review Script Commands

### `review` - Read-only review

```bash
python scripts/kilo_code_review.py review <files> [options]

# Examples
python scripts/kilo_code_review.py review src/main.py
python scripts/kilo_code_review.py review src/ tests/ --strategy free
python scripts/kilo_code_review.py review . --plan "Add user authentication"
```

### `auto-fix` - Review and fix loop

```bash
python scripts/kilo_code_review.py auto-fix <files> --max-iterations 3

# With severity filter
python scripts/kilo_code_review.py auto-fix src/ --min-severity MAJOR
```

### `staged` - Review git staged files

```bash
python scripts/kilo_code_review.py staged
python scripts/kilo_code_review.py staged --no-fix  # Just report
```

### `changed` - Review git changed files

```bash
python scripts/kilo_code_review.py changed
```

### `stats` - Usage statistics

```bash
# Summary
python scripts/kilo_code_review.py stats

# By model (identify expensive patterns)
python scripts/kilo_code_review.py stats --by-model

# By file type
python scripts/kilo_code_review.py stats --by-filetype

# Last 7 days
python scripts/kilo_code_review.py stats --days 7
```

### `verify` - Verify manual fixes

```bash
python scripts/kilo_code_review.py verify src/fixed.py --fixes "Added null check"
```

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `KILO_REVIEW_MODEL` | `kilo/auto` | Force specific model |
| `KILO_REVIEW_TIMEOUT` | `300` | Timeout for review script (seconds) |
| `KILO_TIMEOUT` | `600` | Timeout for agent scripts (seconds) |
| `KILO_DEBUG` | `0` | Enable debug output (`1` to enable) |
| `KILO_TRACK_COST` | `0` | Enable cost tracking (`1` to enable) |
| `KILO_USAGE_LOG` | `.droid/kilo_usage.jsonl` | Usage log file |
| `KILO_DEFAULT_STRATEGY` | (auto) | Default cost strategy (free/economy/standard/premium/critical) |
| `KILO_MAX_COST` | None | Default max cost per review ($/M tokens) |
| `KILO_VERIFY_HIGH_RISK` | `true` | Verify PASS on high-risk code with stronger model |
| `KILO_AUDIT_SAMPLE_RATE` | `0.05` | PASS verdict sampling rate for quality monitoring |
| `KILO_AUDIT_LOG` | `.droid/review_audits.jsonl` | Audit sample log file |

---

## Recommended Workflows

### Development (Fast, Free)

```bash
# Use free models during development
python scripts/kilo_code_review.py review src/ --strategy free

# Quick iteration
python scripts/kilo_code_review.py review src/myfile.py --strategy free --no-escalate
```

### Pre-Commit (Balanced)

```bash
# Standard review with escalation
python scripts/kilo_code_review.py staged --strategy economy

# Or use the auto strategy (default)
python scripts/kilo_code_review.py staged
```

### Security Review (Premium)

```bash
# Force premium tier
python scripts/kilo_code_review.py review src/auth/ --strategy premium

# Or critical for final audit
python scripts/kilo_code_review.py review src/ --strategy critical
```

### Budget-Conscious

```bash
# Cap at $1 per review
python scripts/kilo_code_review.py review src/ --max-cost 1.00

# Check costs regularly
python scripts/kilo_code_review.py stats --by-model --days 7
```

---

## Escalation Behavior

### When Does Escalation Happen?

1. **Model error** - Timeout, API failure, rate limit → retry with next model in tier, then escalate
2. **Zero findings on high-risk code** - False negative mitigation triggers verification with stronger model
3. **Budget allows** - Escalation respects `--max-cost` and `--no-escalate` flags

### Model Error Retry (NEW)

When a model fails, Kilo automatically:
1. Tracks the failed model in `failed_models` set
2. Tries next model in same tier
3. If tier exhausted, escalates to next tier (respecting budget)
4. Max 3 retry attempts per review

### False Negative Mitigation (NEW)

"Zero issues on critical code is a red flag" - all consulted AIs agreed.

| Risk Level | Trigger | Verification Model |
|------------|---------|-------------------|
| HIGH | PASS with zero findings, tier < Strong | Strong (claude-sonnet-4.6) |
| CRITICAL | PASS with zero findings, tier < Prime | Prime (claude-opus-4.6) |

```bash
# Disable verification (saves tokens but less safe)
python scripts/kilo_code_review.py review src/ --verify-high-risk=false
```

### Content-Based Risk Detection (NEW)

Files are scanned for secret patterns (password=, token=, api_key=) and elevated to CRITICAL risk:

```
# These files get CRITICAL risk even if in docs/
password = "hunter2"
TOKEN=sk-abc123
```

### Preventing Escalation

```bash
# Stay at initial tier
python scripts/kilo_code_review.py review src/ --no-escalate

# Cap by cost
python scripts/kilo_code_review.py review src/ --max-cost 0.50
```

---

## Quality Monitoring

### 5% Audit Sampling

Random PASS verdicts are sampled and logged for quality monitoring:
- Log file: `.droid/review_audits.jsonl`
- Sample rate: 5% (configurable via `KILO_AUDIT_SAMPLE_RATE`)

### False Negative Tracking

When verification catches issues cheap models missed:
- Log file: `.droid/kilo_metrics.jsonl`
- Tracks: initial model, verification model, findings missed

### Session Preservation

Same session ID is preserved across escalation for cache hits:
- ~30-50% token savings on subsequent calls
- Model remembers previous file context

---

## See Also

- [KILO_TROUBLESHOOTING.md](KILO_TROUBLESHOOTING.md) - Problem solutions
- [KILO_PERFORMANCE_TUNING.md](KILO_PERFORMANCE_TUNING.md) - Optimization guide
- [KILO_MODEL_SELECTION.md](KILO_MODEL_SELECTION.md) - Model details
- [KILO_CLI_REFERENCE.md](KILO_CLI_REFERENCE.md) - Complete CLI reference
