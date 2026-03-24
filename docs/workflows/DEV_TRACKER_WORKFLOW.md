# Development Tracker Workflow

**Last Updated:** 2026-03-24
**Status:** PRODUCTION
**Script:** `scripts/dev_tracker.py`
**Database:** `.droid/dev_tracker.db`

## Overview

The Development Tracker collects and reports on all agent workflow events across the Fabrik ecosystem. It provides cost tracking, gate pass rates, and workflow analytics for the solo developer.

---

## Data Collection Points

### Event Types

| Event Type | Source Script | Trigger | Fields |
|------------|---------------|---------|--------|
| `pre_kilo` | `final_gate.py` | Before Kilo review | `passed`, `failed_checks`, `auto_fixed` |
| `kilo_review` | `kilo_code_review.py` | After Kilo review | `model`, `verdict`, `issues`, `cost_usd`, `tokens` |
| `post_kilo` | `final_gate.py --post-kilo` | After fixes | `passed`, `failed_checks` |
| `agent_run` | Traycer agents | Agent completion | `agent`, `model`, `duration_s`, `cost_usd` |
| `agent_issue` | Any agent | On error | `issue_type`, `message`, `agent`, `model` |
| `commit` | git hooks (planned) | On commit | `hash`, `files`, `insertions`, `deletions` |

### Data Sources (Import)

The tracker imports from existing JSONL files across all `/opt/*` projects:

| File | Location | Maps To |
|------|----------|---------|
| `kilo_usage.jsonl` | `.droid/` | `kilo_review` events |
| `gate_issues.jsonl` | `.droid/` | `pre_kilo`/`post_kilo` events |
| `review_sessions.jsonl` | `.droid/` | `kilo_review` events |
| `transcripts/*.txt` | `.droid/transcripts/` | `agent_run` events |

---

## Database Schema

```sql
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT DEFAULT (datetime('now', 'localtime')),
    project TEXT,
    task_id TEXT,
    phase_id TEXT,
    event_type TEXT NOT NULL,
    data TEXT NOT NULL  -- JSON blob
);
CREATE INDEX IF NOT EXISTS idx_ts ON events(ts);
CREATE INDEX IF NOT EXISTS idx_type ON events(event_type);
```

---

## CLI Commands

### Logging Events

```bash
# Log a pre-kilo gate result
dev_tracker.py log pre_kilo '{"passed":true,"auto_fixed":3}'

# Log a kilo review result
dev_tracker.py log kilo_review '{"model":"sonnet-4.6","verdict":"PASS","cost_usd":0.12,"tokens":5000}'

# Log an agent issue
dev_tracker.py issue timeout "Model kilo/google/gemini-3-flash timed out"
dev_tracker.py issue rate_limit "Plan generation rate limited"
```

### Importing Historical Data

```bash
# Import all JSONL files from all /opt/* projects
dev_tracker.py import
```

### Reports

```bash
# Today's summary (default)
dev_tracker.py report summary

# Cost breakdown by model
dev_tracker.py report costs

# Gate pass rates
dev_tracker.py report gates

# Agent issues
dev_tracker.py report issues

# Full workflow analysis (all reports)
dev_tracker.py report workflow

# Token savings from deterministic fixes
dev_tracker.py report savings
```

### Ad-Hoc Queries

```bash
# Run custom SQL
dev_tracker.py query "SELECT * FROM events WHERE event_type='kilo_review' ORDER BY ts DESC LIMIT 10"

# Check for cross-project pollution
dev_tracker.py pollution
```

---

## Report Examples

### Summary Report

```
📊 Today (2026-03-24):
   Events: 15
   Cost: $0.87
   Gate pass rate: 85% (11/13)
```

### Cost Breakdown

```
💰 Cost Breakdown:
Model                      Runs      Cost      Avg
---------------------------------------------------
sonnet-4.6                    8    $   0.64   $0.080
deepseek-v3.2                 5    $   0.05   $0.010
gemini-3.1-pro                2    $   0.18   $0.090
```

### Savings Report

```
💾 Token Savings (Deterministic Fixes):
   Auto-fixes applied: 47
   Estimated tokens saved: ~23,500
   Estimated cost avoided: $0.24

   Why: Each deterministic fix (whitespace, EOF, formatting)
   prevents ~500 tokens of LLM retry logic.
```

---

## Integration Points

### 1. final_gate.py

After `run_all_checks()`:
```python
import subprocess, json
result = {"passed": all_passed, "auto_fixed": files_fixed_count}
subprocess.run(['python', 'scripts/dev_tracker.py', 'log',
                'pre_kilo' if not post_kilo else 'post_kilo',
                json.dumps(result)])
```

### 2. kilo_code_review.py

After review completion:
```python
usage_data = {"model": model, "verdict": verdict, "cost_usd": cost, "tokens": tokens}
subprocess.run(['python', 'scripts/dev_tracker.py', 'log',
                'kilo_review', json.dumps(usage_data)])
```

### 3. Traycer Agents

On agent completion, log:
```bash
dev_tracker.py log agent_run '{"agent":"coder","model":"sonnet-4.6","duration_s":45,"cost_usd":0.08}'
```

---

## Environment Variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `FABRIK_ROOT` | Root directory for Fabrik | `/opt/fabrik` |
| `FABRIK_PROJECT` | Current project path | `$FABRIK_ROOT` |
| `TRAYCER_TASK_ID` | Current Traycer task | `null` |
| `TRAYCER_PHASE_ID` | Current Traycer phase | `null` |
| `TRAYCER_AGENT_NAME` | Agent name for issues | `unknown` |
| `KILO_MODEL` | Current Kilo model | `unknown` |

---

## Cross-Project Pollution Detection

The tracker can detect when files from other projects accidentally appear in git status:

```bash
dev_tracker.py pollution
```

This checks for:
- Files resolved outside current project directory
- Symlinks pointing to external projects

---

## Files

| File | Purpose |
|------|---------|
| `scripts/dev_tracker.py` | Main CLI script (~450 lines) |
| `.droid/dev_tracker.db` | SQLite database |
| `.droid/kilo_usage.jsonl` | Raw Kilo usage logs (source) |
| `.droid/gate_issues.jsonl` | Raw gate issue logs (source) |

---

## Related Workflows

- [Final Gate Workflow](FINAL_GATE_WORKFLOW.md) — Pre/post Kilo gate checks
- [Kilo Review Workflow](KILO_REVIEW_WORKFLOW.md) — Code review process
- [Kilo Agent Management](KILO_AGENT_MANAGEMENT.md) — Agent selection and benchmarking
