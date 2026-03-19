# Development Tracking System Design

**Status:** IN_PROGRESS
**Created:** 2026-03-19
**Iteration:** 6 (production-ready, tonight's deployment)

## Goal

Track pre-kilo, kilo review, post-kilo workflow costs. Start using tonight.

## DONE WHEN

- [ ] Script created with CLI commands
- [ ] Import from existing JSONL works
- [ ] Reports show actionable data
- [ ] Ready to use in current session

---

## Final Design (Iteration 6)

### Schema

```sql
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT DEFAULT (datetime('now')),
    project TEXT,
    task_id TEXT,
    phase_id TEXT,
    event_type TEXT NOT NULL,
    data TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_ts ON events(ts);
CREATE INDEX IF NOT EXISTS idx_type ON events(event_type);
```

### Event Types

| Type | Source | Fields |
|------|--------|--------|
| `pre_kilo` | final_gate.py | passed, failed_checks, auto_fixed |
| `kilo_review` | kilo_code_review.py | model, verdict, issues, cost_usd, tokens |
| `post_kilo` | final_gate.py --post-kilo | passed, failed_checks |
| `agent_run` | Traycer agents | agent, model, duration_s, cost_usd |
| `commit` | git | hash, files, insertions, deletions |

### CLI Commands

```bash
# Log events (called by other scripts)
dev_tracker.py log pre_kilo '{"passed":true,"auto_fixed":3}'
dev_tracker.py log kilo_review '{"model":"sonnet-4.6","verdict":"PASS","cost_usd":0.12}'
dev_tracker.py log post_kilo '{"passed":true}'

# Import existing data
dev_tracker.py import

# Reports
dev_tracker.py report summary      # Today's summary
dev_tracker.py report costs        # Cost breakdown by model
dev_tracker.py report gates        # Pre/post kilo pass rates
dev_tracker.py report workflow     # Full workflow analysis

# Ad-hoc
dev_tracker.py query "SELECT * FROM events WHERE event_type='kilo_review'"
```

### Key Reports

**1. Summary (default)**
```
Today (2026-03-19):
  Events: 15
  Cost: $0.87
  Gate pass rate: 85%
  Review iterations: avg 1.3
```

**2. Cost Breakdown**
```
Model              Runs    Cost     Avg
sonnet-4.6           8    $0.64   $0.08
deepseek-v3.2        5    $0.05   $0.01
gemini-3.1-pro       2    $0.18   $0.09
```

**3. Workflow Analysis**
```
Phase          Pass%   Avg Time   Issues
pre_kilo        92%      2.1s     ruff:3, mypy:1
kilo_review     78%     12.4s     MAJOR:2, MINOR:5
post_kilo       95%      1.8s     -
```

---

## Integration Points

### 1. final_gate.py (existing)
Already logs to `.droid/gate_issues.jsonl`. Add:
```python
# At end of run_all_checks()
subprocess.run(['python', '/opt/fabrik/scripts/dev_tracker.py', 'log',
                'pre_kilo' if not post_kilo else 'post_kilo', json.dumps(result)])
```

### 2. kilo_code_review.py (existing)
Already logs to `.droid/kilo_usage.jsonl`. Add:
```python
# At end of run_review()
subprocess.run(['python', '/opt/fabrik/scripts/dev_tracker.py', 'log',
                'kilo_review', json.dumps(usage_data)])
```

### 3. Batch import (for historical data)
```bash
dev_tracker.py import  # Reads all .droid/*.jsonl files
```

---

## Files

- `scripts/dev_tracker.py` - ~150 lines, self-contained
- `.droid/dev_tracker.db` - Auto-created SQLite DB
