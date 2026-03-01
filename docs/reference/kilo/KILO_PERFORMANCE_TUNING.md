# Kilo Performance Tuning Guide

**Last Updated:** 2026-03-01

Optimize Kilo CLI usage for speed, cost, and quality.

---

## Model Selection by Task

### Quick Reference

| Task | Recommended Model | Tier | Cost |
|------|-------------------|------|------|
| Quick code snippet | Ultra (Codestral) | Ultra | ~$0.25/M |
| Documentation | Free (GLM 4.5 Air) | Free | $0 |
| Simple review | Economy (Flash 3) | Economy | ~$0.02/M |
| Complex review | Strong (Sonnet 4.5) | Strong | ~$3/M |
| Security audit | Prime (Opus 4.6) | Prime | ~$5/M |
| Unknown/mixed | Auto (kilo/auto) | Auto | Variable |

### Environment Variables

```bash
# Force specific model
export KILO_REVIEW_MODEL=kilo/anthropic/claude-sonnet-4.6

# Use auto routing (recommended)
export KILO_REVIEW_MODEL=kilo/auto
```

---

## Cost Optimization

### 1. Use Free Tier First

For development and iteration:
```bash
# Free models (9 available)
Free01-minimax21    # General purpose
Free06-qwen3coder   # Coding tasks
Free08-deepseekr1   # Review tasks
```

### 2. Pre-Review Validation (Coming Soon)

Future updates will include `pre_review_checks()` to catch common issues:
- Syntax errors
- File size limits
- Encoding issues

### 3. Session Continuity

Reuse session context to reduce tokens:
```bash
# First review
python scripts/kilo_code_review.py review src/ --output json

# Subsequent reviews (cheaper - context preserved)
python scripts/kilo_code_review.py review src/ --session continue
```

### 4. Diff-Scoped Routing

The script automatically routes based on file paths:
- High-risk paths → Opus (expensive, thorough)
- Normal paths → Flash (cheap, fast)

Override only when needed:
```bash
--model kilo/anthropic/claude-opus-4.6
```

---

## Speed Optimization

### 1. Timeout Configuration

```bash
# For agent scripts (default 600s)
export KILO_TIMEOUT=300

# For kilo_code_review.py (default 300s)
export KILO_REVIEW_TIMEOUT=300  # 5 minutes for faster tasks

# Per-agent timeout in generated scripts
# Configured via generate_kilo_agents.py
```

### 2. Parallel Review

For large codebases, batch files:
```bash
# Review in batches of 5 (hardcoded default)
python scripts/kilo_code_review.py review src/

# Note: MAX_FILES_PER_BATCH is hardcoded in kilo_code_review.py
# Edit the constant directly if needed
```

### 3. Skip Pre-commit

When pre-commit is slow or not needed:
```bash
python scripts/kilo_code_review.py review src/ --skip-precommit
```

### 4. Mypy Recovery

Mypy cache corruption can cause hangs:
```bash
# Safe mypy with auto-recovery
make mypy-safe

# Or clear cache manually
rm -rf .mypy_cache/
```

---

## Quality Optimization

### 1. Variant Selection

| Variant | Use Case | Token Budget |
|---------|----------|--------------|
| minimal | Quick checks | Low |
| low | Simple tasks | Low-Medium |
| high | Complex logic | High |
| max | Critical/security | Maximum |

**Note:** `medium` variant is used in agent scripts but not in kilo_code_review.py CLI.

### 2. Review Categories

Skip irrelevant categories:
```bash
--skip-categories DOCS  # Skip documentation checks
--skip-categories EDGE  # Skip edge case analysis
```

### 3. Doc Mode

For markdown-only changes:
```bash
--doc-mode  # Lighter review, fewer iterations
```

---

## Monitoring

### Usage Statistics

```bash
# Summary
python scripts/kilo_code_review.py stats

# By model (identify expensive patterns)
python scripts/kilo_code_review.py stats --by-model

# By file type (optimize per language)
python scripts/kilo_code_review.py stats --by-filetype
```

### Cost Tracking

Enable per-agent tracking:
```bash
export KILO_TRACK_COST=1
```

Logs to: `.droid/kilo_usage.jsonl`

### Health Checks

```bash
# Verify all agents
bash scripts/kilo_agent_health.sh

# Check specific agent
sh -n ~/.traycer/cli-agents/Auto01-auto-code-auto-i000-o000.sh
```

---

## Best Practices

### 1. Start Cheap, Escalate When Needed

```
Free tier → Economy → Balanced → Strong → Prime
```

### 2. Use Auto Model for Unknown Tasks

```bash
export KILO_REVIEW_MODEL=kilo/auto
```

Auto routing:
- Review mode → Opus 4.6
- Code mode   → Sonnet 4.5

### 3. Batch Similar Files

Group by file type for consistent review:
```bash
python scripts/kilo_code_review.py review src/**/*.py
python scripts/kilo_code_review.py review tests/**/*.py
```

### 4. Cache Management

Clear caches periodically:
```bash
# Mypy cache
rm -rf .mypy_cache/

# Model cache (refreshes daily automatically)
rm .droid/kilo_models_cache.json
```

---

## Tier Cost Comparison

| Tier | Input $/1M | Output $/1M | Best For |
|------|------------|-------------|----------|
| Free | $0 | $0 | Development, iteration |
| Ultra | $0.25 | $0.75 | Quick specialized tasks |
| Economy | $0.02-0.36 | $0.02-1.2 | Budget production |
| Balanced | $0.02-1.75 | $0.05-14 | Most tasks |
| Strong | $0.02-3.00 | $0.05-15 | Production code |
| Prime | $5.00-21 | $25-168 | Critical/security |

---

## See Also

- [KILO_TROUBLESHOOTING.md](KILO_TROUBLESHOOTING.md) - Problem solutions
- [KILO_MODEL_SELECTION.md](KILO_MODEL_SELECTION.md) - Model details
- [KILO_CLI_REFERENCE.md](KILO_CLI_REFERENCE.md) - Complete CLI reference
