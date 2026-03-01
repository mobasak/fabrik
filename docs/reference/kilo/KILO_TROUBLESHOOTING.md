# Kilo Troubleshooting Guide

**Last Updated:** 2026-03-01

Quick solutions for common Kilo CLI and Traycer agent issues.

---

## Common Issues

### 1. Agent Script Not Executable

**Symptom:** `Permission denied` when running agent script

**Fix:**
```bash
chmod +x ~/.traycer/cli-agents/*.sh
```

### 2. Kilo CLI Not Found

**Symptom:** `kilo: command not found`

**Fix:**
```bash
# Check if kilo is installed
which kilo

# If not found, install via npm
npm install -g @kilocode/cli
```

### 3. Model Not Available

**Symptom:** `Model not found` or `Model unavailable` error

**Fix:**
```bash
# Refresh model cache
kilo models --refresh

# Check model availability
python scripts/kilo_code_review.py stats --by-model
```

### 4. Timeout During Review

**Symptom:** Review hangs or times out

**Cause:** Large file, slow API, or cache corruption

**Fix:**
```bash
# For agent scripts (default 600s)
export KILO_TIMEOUT=300

# For kilo_code_review.py (default 300s)
export KILO_REVIEW_TIMEOUT=300

# For mypy specifically
make mypy-safe
```

### 5. Infinite Loop in Pre-commit

**Symptom:** `ruff --fix` keeps modifying same files

**Fix:** The `kilo_code_review.py` has built-in infinite loop detection. If stuck:
```bash
# Skip pre-commit
python scripts/kilo_code_review.py review <files> --skip-precommit
```

### 6. Session Continuity Lost

**Symptom:** `--session continue` not finding previous session

**Fix:**
```bash
# List existing sessions
ls .droid/reviews/

# Start new session explicitly
# Omit --session flag to start fresh
python scripts/kilo_code_review.py review <files>
```

---

## Debug Mode

Enable debug output for all agents:

```bash
export KILO_DEBUG=1
export KILO_TRACK_COST=1

# Run your task - will show detailed output
```

Debug shows:
- Agent name and model
- Prompt length
- Task ID
- Timeout settings
- Exit codes
- Duration

---

## Cost Tracking

### View Usage Statistics

```bash
# Last 30 days summary
python scripts/kilo_code_review.py stats

# By model
python scripts/kilo_code_review.py stats --by-model

# By file type
python scripts/kilo_code_review.py stats --by-filetype

# Custom time range
python scripts/kilo_code_review.py stats --days 7
```

### Usage Log Location

- Session logs: `.droid/kilo_usage.jsonl`
- Review sessions: `.droid/review_sessions.jsonl`
- Metrics: `.droid/kilo_metrics.jsonl`

---

## Agent Health Check

```bash
# Check all agents for issues
bash scripts/kilo_agent_health.sh

# Regenerate if needed
python scripts/generate_kilo_agents.py

# Dry-run first
python scripts/generate_kilo_agents.py --dry-run
```

---

## Model Selection Issues

### Routing Decisions

Review model selection is based on diff file paths:
- **High-risk paths** (src/, scripts/, auth/) → Opus 4.6
- **Normal paths** → Gemini 3 Flash (cheaper)

Override with:
```bash
export KILO_REVIEW_MODEL=kilo/anthropic/claude-sonnet-4.6
```

### Available Tiers

| Tier | Models | Cost |
|------|--------|------|
| Auto | kilo/auto | Variable |
| Prime | Opus 4.6, GPT-5.2 Pro | $5-25/M |
| Strong | Sonnet 4.6, GPT-5.3 | $1-15/M |
| Balanced | GPT-5.2, Grok | $0.02-14/M |
| Economy | Gemini Flash, Devstral | ~$0.02/M |
| Free | MiniMax M2.1, GLM 4.7-free, Kimi K2.5 | $0 |
| Ultra | Codestral | ~$0.25/M |

---

## Error Codes

| Exit Code | Meaning | Action |
|-----------|---------|--------|
| 0 | Success | - |
| 1 | Review failed (issues remain) | Fix issues |
| 2 | Error (invalid input, Kilo unavailable) | Check config |
| 124 | Timeout | Increase KILO_TIMEOUT |
| 503 | Service unavailable | Retry later |

---

## Getting Help

1. Check agent logs: `~/.traycer/cli-agents/`
2. Review session: `.droid/reviews/<session_id>/`
3. Enable debug: `KILO_DEBUG=1`
4. Run health check: `scripts/kilo_agent_health.sh`

---

## See Also

- [KILO_CLI_REFERENCE.md](KILO_CLI_REFERENCE.md) - Complete CLI reference
- [KILO_PERFORMANCE_TUNING.md](KILO_PERFORMANCE_TUNING.md) - Optimization guide
- [KILO_MODEL_SELECTION.md](KILO_MODEL_SELECTION.md) - Model selection details
