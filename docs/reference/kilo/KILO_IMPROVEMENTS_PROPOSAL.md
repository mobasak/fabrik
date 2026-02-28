# Kilo System Improvement Proposals

**Last Updated:** 2026-02-28
**Status:** Proposed for Review

This document contains improvement proposals for Fabrik's Kilo integration, including agent scripts, code review system, and generation scripts.

---

## Overview

After comprehensive analysis of the Kilo CLI integration and Fabrik's 9-step workflow, here are strategic improvements to enhance reliability, observability, and cost optimization.

---

## 1. Agent Scripts (.sh) Improvements

### Current State

Scripts in `~/.traycer/cli-agents/` are minimal and functional but lack:
- Error handling and validation
- Debugging/observability capabilities
- Timeout protection
- Cost tracking

### Proposed Enhancements

#### 1.1 Add Debug Mode

**Benefit:** Troubleshoot Traycer integration issues without editing scripts.

```bash
#!/bin/sh
# Enable debug mode via env var
if [ "$KILO_DEBUG" = "1" ]; then
    set -x  # Print all commands
    echo "[DEBUG] Agent: B04-grok41fast-code-high" >&2
    echo "[DEBUG] TRAYCER_PROMPT length: ${#TRAYCER_PROMPT}" >&2
    echo "[DEBUG] TRAYCER_TASK_ID: $TRAYCER_TASK_ID" >&2
fi
```

**Usage:**
```bash
export KILO_DEBUG=1
# Run Traycer task - now with detailed output
```

#### 1.2 Add Timeout Protection

**Benefit:** Prevent hung Traycer jobs from blocking workflow.

```bash
# Add timeout wrapper (default 10 minutes)
TIMEOUT="${KILO_TIMEOUT:-600}"

# Run with timeout
timeout "$TIMEOUT" kilo run --format json --auto \
    --model kilo/x-ai/grok-4.1-fast \
    --variant high \
    --agent code \
    "$PROMPT"

EXIT_CODE=$?

if [ $EXIT_CODE -eq 124 ]; then
    echo '{"error": "timeout", "duration": '$TIMEOUT'}' >&2
    exit 124
fi

exit $EXIT_CODE
```

**Usage:**
```bash
export KILO_TIMEOUT=300  # 5 minutes for fast tasks
```

#### 1.3 Add Cost Tracking

**Benefit:** Track credit usage per Traycer phase for budget optimization.

```bash
# Log usage to tracking file
USAGE_LOG="${KILO_USAGE_LOG:-.droid/kilo_usage.jsonl}"

# Extract cost from Kilo JSON output if available
if [ -n "$KILO_TRACK_COST" ]; then
    # Append to JSONL log
    echo "{\"timestamp\":\"$(date -Iseconds)\",\"agent\":\"B04-grok41fast-code-high\",\"task_id\":\"$TRAYCER_TASK_ID\",\"exit_code\":$EXIT_CODE}" >> "$USAGE_LOG"
fi
```

**Analysis:**
```bash
# Show total cost by agent
jq -s 'group_by(.agent) | map({agent: .[0].agent, calls: length})' .droid/kilo_usage.jsonl
```

#### 1.4 Add Environment Validation

**Benefit:** Fail fast with clear error messages.

```bash
# Validate environment before running
if [ -z "$TRAYCER_PROMPT" ] && [ ! -f "$TRAYCER_PROMPT_TMP_FILE" ]; then
    echo '{"error": "no_prompt", "message": "TRAYCER_PROMPT and TRAYCER_PROMPT_TMP_FILE both empty"}' >&2
    exit 2
fi

# Validate kilo CLI exists
if ! command -v kilo >/dev/null 2>&1; then
    echo '{"error": "kilo_not_found", "message": "kilo CLI not in PATH"}' >&2
    exit 2
fi
```

#### 1.5 Add kilo/auto Support

**Benefit:** Leverage Auto Model routing for optimal cost/performance.

```bash
# Allow override via env var
MODEL="${KILO_AUTO_MODEL:-kilo/x-ai/grok-4.1-fast}"

# New agent: AUTO-code-high.sh using kilo/auto
kilo run --format json --auto \
    --model kilo/auto \
    --agent code \
    "$PROMPT"
```

### Implementation Plan

1. **Update `generate_kilo_agents.py`** to include enhanced features
2. **Add optional flags** (controlled via env vars, disabled by default)
3. **Regenerate all 18 agents** with new features
4. **Create `AUTO-code.sh` and `AUTO-review.sh`** agents using `kilo/auto`
5. **Document env vars** in `KILO_AGENT_NAMING.md`

---

## 2. Code Review Script (kilo_code_review.py) Improvements

### Current State

`scripts/kilo_code_review.py` is functional but could benefit from:
- `kilo/auto` support
- Better cost tracking
- Retry logic for transient failures
- Model performance metrics

### Proposed Enhancements

#### 2.1 Add kilo/auto Support

**Benefit:** Automatic mode-based routing for review vs fix tasks.

```python
# Add to REASONING_MODELS set
REASONING_MODELS.add("kilo/auto")

# Auto model routing logic
def get_review_model(files: list[Path]) -> str:
    """Select model based on file types"""
    if os.getenv("KILO_REVIEW_MODEL"):
        return os.getenv("KILO_REVIEW_MODEL")

    # Use kilo/auto for mixed tasks
    if os.getenv("KILO_USE_AUTO", "false").lower() == "true":
        return "kilo/auto"

    # Default to Opus 4.6 for deep review
    return "kilo/anthropic/claude-opus-4.6"
```

**Usage:**
```bash
export KILO_USE_AUTO=true
python scripts/kilo_code_review.py review src/ --output json
```

#### 2.2 Add Cost Tracking Per Review

**Benefit:** Budget optimization insights.

```python
@dataclass
class ReviewSession:
    session_id: str
    files: list[str]
    model: str
    iterations: int
    total_cost: float = 0.0
    verdict: str = "PENDING"

    def save(self):
        """Save session metrics to .droid/review_sessions.jsonl"""
        with open(".droid/review_sessions.jsonl", "a") as f:
            json.dump(asdict(self), f)
            f.write("\n")
```

**Analysis:**
```bash
# Show review costs by model
jq -s 'group_by(.model) | map({model: .[0].model, avg_cost: (map(.total_cost) | add / length), sessions: length})' .droid/review_sessions.jsonl
```

#### 2.3 Add Retry Logic for Transient Failures

**Benefit:** Resilience to network/API hiccups.

```python
def run_kilo_review(prompt: str, model: str, max_retries: int = 3) -> dict:
    """Run Kilo review with exponential backoff retry"""
    for attempt in range(max_retries):
        try:
            result = subprocess.run(
                ["kilo", "run", "--format", "json", "--auto",
                 "--model", model, "--agent", "ask", prompt],
                capture_output=True, text=True, timeout=300
            )
            if result.returncode == 0:
                return json.loads(result.stdout)

            # Retry on specific error codes
            if result.returncode in [124, 503]:  # Timeout or service unavailable
                wait_time = 2 ** attempt  # Exponential backoff
                print(f"⏳ Retrying in {wait_time}s (attempt {attempt+1}/{max_retries})", file=sys.stderr)
                time.sleep(wait_time)
                continue

            # Don't retry other errors
            break

        except subprocess.TimeoutExpired:
            if attempt < max_retries - 1:
                continue
            raise

    return {"verdict": "ERROR", "issues": []}
```

#### 2.4 Add Model Performance Metrics

**Benefit:** Track which models perform best for different file types.

```python
@dataclass
class ModelMetrics:
    """Track model performance for review tasks"""
    model: str
    file_type: str
    avg_iterations: float
    avg_cost: float
    pass_rate: float

    @classmethod
    def load(cls) -> list[ModelMetrics]:
        """Load from .droid/model_metrics.json"""
        ...

    def update(self, session: ReviewSession):
        """Update metrics with new session data"""
        ...
```

**Usage:**
```bash
# Show best models by file type
python scripts/kilo_code_review.py stats --by-filetype
```

#### 2.5 Add Pre-Review Validation

**Benefit:** Catch issues before spending credits.

```python
def pre_review_checks(files: list[Path]) -> list[str]:
    """Run fast validation before Kilo review"""
    issues = []

    # Check file sizes
    for f in files:
        if f.stat().st_size > MAX_FILE_SIZE:
            issues.append(f"File too large: {f} ({f.stat().st_size} bytes)")

    # Check for syntax errors (Python only)
    for f in [f for f in files if f.suffix == ".py"]:
        try:
            compile(f.read_text(), f, "exec")
        except SyntaxError as e:
            issues.append(f"Syntax error in {f}:{e.lineno}: {e.msg}")

    return issues
```

### Implementation Plan

1. **Add `kilo/auto` support** to model selection logic
2. **Implement cost tracking** with session persistence
3. **Add retry logic** with exponential backoff
4. **Create metrics module** for model performance tracking
5. **Add pre-review validation** to fail fast
6. **Update docs** with new env vars and flags

---

## 3. Generate Script (generate_kilo_agents.py) Improvements

### Current State

`scripts/generate_kilo_agents.py` generates agents but lacks:
- Validation of generated scripts
- Backup mechanism
- Dry-run mode
- `kilo/auto` agent variants

### Proposed Enhancements

#### 3.1 Add Dry-Run Mode

**Benefit:** Preview changes before applying.

```python
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true",
                       help="Show what would be generated without writing")
    parser.add_argument("--backup", action="store_true", default=True,
                       help="Backup existing scripts before regenerating")
    args = parser.parse_args()

    if args.dry_run:
        print("DRY RUN - No files will be modified")
        # Show what would be generated
        ...
```

#### 3.2 Add Script Validation

**Benefit:** Catch generation errors before deployment.

```python
def validate_script(script_path: Path) -> list[str]:
    """Validate generated shell script"""
    issues = []
    content = script_path.read_text()

    # Check shebang
    if not content.startswith("#!/bin/sh"):
        issues.append("Missing or incorrect shebang")

    # Check for exit statement
    if "exit $?" not in content:
        issues.append("Missing explicit exit statement")

    # Check for required env var handling
    if "TRAYCER_PROMPT" not in content:
        issues.append("Missing TRAYCER_PROMPT handling")

    # Shell syntax check
    result = subprocess.run(["sh", "-n", str(script_path)],
                           capture_output=True, text=True)
    if result.returncode != 0:
        issues.append(f"Shell syntax error: {result.stderr}")

    return issues
```

#### 3.3 Add Backup Mechanism

**Benefit:** Safe rollback if generation fails.

```python
def backup_existing_agents(output_dir: Path) -> Path:
    """Backup existing agents before regeneration"""
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_dir = output_dir.parent / f"cli-agents-backup-{timestamp}"

    if output_dir.exists():
        shutil.copytree(output_dir, backup_dir)
        print(f"✓ Backed up existing agents to {backup_dir}")
        return backup_dir

    return None
```

#### 3.4 Generate kilo/auto Agents

**Benefit:** Leverage Auto Model routing.

```python
# Add to agent generation
AUTO_AGENTS = [
    {
        "model_name": "auto",
        "full_name": "kilo/auto",
        "use_case": "code",
        "variant": "auto",
        "specialty": "Auto model routing for code tasks",
        "input_per_1m": 0.0,  # Variable
        "output_per_1m": 0.0,  # Variable
    },
    {
        "model_name": "auto",
        "full_name": "kilo/auto",
        "use_case": "review",
        "variant": "auto",
        "specialty": "Auto model routing for review tasks",
        "input_per_1m": 0.0,  # Variable
        "output_per_1m": 0.0,  # Variable
    },
]

# Generate AUTO-code.sh and AUTO-review.sh
```

#### 3.5 Add Model Availability Check

**Benefit:** Fail fast if models don't exist in Kilo.

```python
def check_model_availability(model_name: str) -> bool:
    """Check if model exists in Kilo CLI"""
    result = subprocess.run(
        ["kilo", "models", "--format", "json"],
        capture_output=True, text=True, timeout=10
    )

    if result.returncode != 0:
        print(f"⚠ Warning: Could not verify model availability", file=sys.stderr)
        return True  # Assume available

    models = json.loads(result.stdout)
    model_ids = [m["id"] for m in models]

    return model_name in model_ids or f"kilo/{model_name}" in model_ids
```

### Implementation Plan

1. **Add argparse** for flags (--dry-run, --no-backup, --validate)
2. **Implement backup mechanism** with timestamp
3. **Add validation function** for generated scripts
4. **Generate AUTO agents** (AUTO-code.sh, AUTO-review.sh)
5. **Add model availability check** before generation
6. **Update docs** with new script features

---

## 4. New Utility Scripts

### 4.1 kilo_agent_health.sh

**Purpose:** Health check for all Traycer CLI agents.

```bash
#!/bin/bash
# Check health of all Kilo agents

AGENTS_DIR="$HOME/.traycer/cli-agents"
FAILURES=0

for agent in "$AGENTS_DIR"/*.sh; do
    name=$(basename "$agent")

    # Check executable
    if [ ! -x "$agent" ]; then
        echo "❌ $name - not executable"
        ((FAILURES++))
        continue
    fi

    # Check syntax
    if ! sh -n "$agent" 2>/dev/null; then
        echo "❌ $name - syntax error"
        ((FAILURES++))
        continue
    fi

    echo "✓ $name"
done

if [ $FAILURES -gt 0 ]; then
    echo ""
    echo "❌ $FAILURES agent(s) failed health check"
    exit 1
fi

echo ""
echo "✓ All agents healthy"
exit 0
```

### 4.2 kilo_cost_report.py

**Purpose:** Analyze Kilo usage costs across Traycer phases.

```python
#!/usr/bin/env python3
"""Generate cost report from Kilo usage logs"""

import json
from pathlib import Path
from datetime import datetime, timedelta

def generate_report(days: int = 7):
    """Generate cost report for last N days"""
    usage_file = Path(".droid/kilo_usage.jsonl")

    if not usage_file.exists():
        print("No usage data found")
        return

    cutoff = datetime.now() - timedelta(days=days)
    sessions = []

    with open(usage_file) as f:
        for line in f:
            session = json.loads(line)
            ts = datetime.fromisoformat(session["timestamp"])
            if ts >= cutoff:
                sessions.append(session)

    # Analyze by agent
    by_agent = {}
    for s in sessions:
        agent = s["agent"]
        if agent not in by_agent:
            by_agent[agent] = {"calls": 0, "cost": 0.0}
        by_agent[agent]["calls"] += 1

    # Print report
    print(f"📊 Kilo Usage Report (Last {days} Days)")
    print(f"Total sessions: {len(sessions)}")
    print("\nBy Agent:")
    for agent, stats in sorted(by_agent.items()):
        print(f"  {agent}: {stats['calls']} calls")
```

**Usage:**
```bash
python scripts/kilo_cost_report.py --days 30
```

---

## 5. Documentation Improvements

### 5.1 Add Troubleshooting Guide

**Location:** `docs/reference/kilo/KILO_TROUBLESHOOTING.md`

**Content:**
- Common Traycer integration issues
- Agent script debugging
- Model selection problems
- Cost optimization tips

### 5.2 Add Performance Tuning Guide

**Location:** `docs/reference/kilo/KILO_PERFORMANCE_TUNING.md`

**Content:**
- Model selection by task complexity
- Parallel review strategies
- Cost/speed tradeoffs
- Session continuity best practices

---

## Implementation Priority

### Phase 1 (Immediate - 1 week)
- ✅ Document Auto Model (kilo/auto)
- ⏳ Add `kilo/auto` support to `kilo_code_review.py`
- ⏳ Generate AUTO-code.sh and AUTO-review.sh agents
- ⏳ Add dry-run mode to `generate_kilo_agents.py`

### Phase 2 (Short-term - 2 weeks)
- ⏳ Add debug mode to agent scripts
- ⏳ Add cost tracking to agent scripts
- ⏳ Add retry logic to `kilo_code_review.py`
- ⏳ Create `kilo_agent_health.sh` utility

### Phase 3 (Medium-term - 1 month)
- ⏳ Add model performance metrics
- ⏳ Create `kilo_cost_report.py` utility
- ⏳ Add pre-review validation
- ⏳ Create troubleshooting guide

---

## Expected Benefits

### Cost Optimization
- **Free tier agents:** Zero-cost development for 50-70% of tasks
- **Auto Model routing:** 30-50% cost reduction for mixed tasks
- **Cost tier routing:** Automatic free → budget → premium escalation
- **50% rule enforcement:** Maintain cost discipline
- **Context optimization:** Reduce token usage 20-30%
- **Cost tracking:** Visibility for budget optimization
- **Pre-review validation:** Avoid wasted credits on syntax errors

**Total expected savings:** 60-80% reduction in monthly AI costs

### Reliability
- **Retry logic:** Handle transient API failures
- **Timeout protection:** Prevent hung Traycer jobs
- **Environment validation:** Fail fast with clear errors
- **Free tier fallback:** Continue working when budget exhausted

### Observability
- **Debug mode:** Troubleshoot integration issues
- **Usage logging:** Track credit consumption by tier
- **Performance metrics:** Identify best models per task and tier
- **Cost tier reporting:** Monitor 50% rule compliance

### Developer Experience
- **Dry-run mode:** Preview changes safely
- **Backup mechanism:** Rollback if needed
- **Health checks:** Verify agent integrity
- **Zero-cost onboarding:** Start with free tier, scale up as needed

---

## See Also

- **[KILO_MODEL_SELECTION.md](KILO_MODEL_SELECTION.md)** - Auto Model documentation
- **[KILO_AGENT_NAMING.md](KILO_AGENT_NAMING.md)** - Agent naming convention
- **[KILO_CLI_REFERENCE.md](KILO_CLI_REFERENCE.md)** - Complete CLI reference
