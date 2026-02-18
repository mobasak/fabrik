# 2026-02-16-plan-gap04-kpi-dashboard

**Status:** NOT_STARTED
**Created:** 2026-02-16
**Priority:** P1 (High)
**Estimated Effort:** 6-8 hours
**Source:** Research document "Optimizing Workflows Across AI Coding Platforms"

---

## EXECUTION MODE HEADER (mandatory)

```text
STAGE: 3 — Execution
MODE: Mode 3 — Build (Cascade implements)
SPEC STATUS: FROZEN (this plan is read-only during execution)
SCOPE: GAP-04 KPI Dashboard only
NEXT REQUIRED: Mode 4 — Verify with Factory Droid after each step

RULES:
- Follow steps exactly in order
- Do NOT redesign or change scope (spec freeze)
- One step at a time
- After each step: show Evidence + Gate result
- After each step: Mode 4 verification
- If a Gate fails → STOP and report
- Maintain same session ID throughout execution

ROLE SEPARATION:
- Builder (Cascade/You): Implements code, runs self-review
- Verifier (Factory Droid): Independent audit, approves changes
- Rule: "Verifier never fixes. Builder never self-verifies."
```

---

## TASK METADATA

```text
TASK:
Implement KPI tracking for AI coding workflow metrics

GOAL:
Enable data-driven optimization of AI coding workflows by tracking cycle time, token cost, iteration count, and gate pass rate.

DONE WHEN (all true):
- [ ] KPI data stored in .droid/kpis.jsonl
- [ ] CLI command to view KPIs: python scripts/kpi_tracker.py report
- [ ] Token usage integrated from droid_session.py
- [ ] Cycle time tracking implemented
- [ ] Gate pass rate calculated
- [ ] Gate command passes: python scripts/kpi_tracker.py report --summary

OUT OF SCOPE:
- Web dashboard UI (CLI only for now)
- Historical data migration
- Real-time streaming metrics
- External monitoring integration (Prometheus, etc.)
```

---

## GLOBAL CONSTRAINTS

```text
CONSTRAINTS:
- Storage: JSONL format in .droid/kpis.jsonl
- Language: Python 3.12 with type annotations
- Dependencies: No new deps (use stdlib + existing)
- Integration: Use Factory hooks (NOT direct droid_session.py modification)
- Data source: Ingest existing .droid_token_usage.jsonl (no duplication)
- Format: Follow existing scripts/droid_*.py patterns
- Zero regression risk: No changes to core droid_session.py

SESSION MANAGEMENT:
- Start: droid exec -m swe-1-5 "Start GAP-04" (captures session_id)
- Continue: droid exec --session-id <id> "Next step..."
- WARNING: Changing models mid-session loses context
- Verification uses SEPARATE session (Verifier independence)

MODEL ASSIGNMENTS (from config/models.yaml):
- Execution: swe-1-5 or gpt-5.1-codex (Stage 3 - Build)
- Verification: gpt-5.3-codex (Stage 4 - Verify)
- Documentation: claude-haiku-4-5 (Stage 5 - Ship)
```

---

## EXISTING INFRASTRUCTURE (reuse, don't duplicate)

| Component | Location | Reuse Strategy |
|-----------|----------|----------------|
| Token tracking | `scripts/droid_session.py` | **READ ONLY** - parse existing output |
| Session management | `scripts/droid_session.py` | Use session IDs from logs |
| Token log | `.droid_token_usage.jsonl` | **PRIMARY DATA SOURCE** - ingest directly |
| Model pricing | `config/models.yaml` | Get cost per token |
| Process monitor | `scripts/process_monitor.py` | Track execution time |
| Factory hooks | `~/.factory/hooks/` | Add PostToolUse hook for KPI capture |

**Key insight:** droid_session.py already writes to `.droid_token_usage.jsonl`. KPI tracker **ingests this file** rather than modifying droid_session.py. Zero regression risk.

---

## CANONICAL GATE

```text
CANONICAL GATE:
python scripts/kpi_tracker.py report --summary && echo "PASS"
```

---

## EXECUTION STEPS

### Step 1 — Design KPI Data Schema

```text
DO:
- Define KPI event types:
  - task_start: {task_id, timestamp, model, task_type}
  - task_end: {task_id, timestamp, status, tokens_used, iterations}
  - gate_result: {task_id, gate_name, passed, timestamp}
  - review_cycle: {task_id, reviewer, issues_p0, issues_p1, timestamp}
- Create docs/reference/kpi-schema.md documenting format
- Define aggregation periods: daily, weekly, billing_cycle

GATE:
- docs/reference/kpi-schema.md exists
- Schema covers all 4 metrics (cycle_time, cost, iterations, gate_rate)

EVIDENCE REQUIRED:
- kpi-schema.md content
- Event type definitions

CODE REVIEW:
- droid exec -m gpt-5.3-codex "Review KPI schema for completeness"
- droid exec -m gemini-3-pro-preview "Review KPI schema for analytics best practices"
```

---

### Step 2 — Create KPI Tracker Core Module

```text
DO:
- Create scripts/kpi_tracker.py
- Implement KPIEvent dataclass
- Implement KPIStore class:
  - log_event(event: KPIEvent) -> None
  - get_events(start: datetime, end: datetime) -> list[KPIEvent]
  - get_summary(period: str) -> dict
- Use .droid/kpis.jsonl for storage
- Add type annotations throughout

GATE:
- python -c "from scripts.kpi_tracker import KPIStore; print('OK')"

EVIDENCE REQUIRED:
- kpi_tracker.py content (core classes)
- Import test output

PRE-FLIGHT GATES:
- ruff check scripts/kpi_tracker.py && mypy scripts/kpi_tracker.py

MODE 4 VERIFICATION (Verifier):
- droid exec -m gpt-5.3-codex --session-id <verify_session> "Audit kpi_tracker.py: Fabrik patterns? Type hints? List issues as JSON."
- If issues → fix → re-verify (MAX 2 iterations)
```

---

### Step 3 — Implement Metric Calculators

```text
DO:
- Add to kpi_tracker.py:
  - calculate_cycle_time(task_id) -> timedelta
  - calculate_cost(task_id) -> float (USD)
  - calculate_iterations(task_id) -> int
  - calculate_gate_pass_rate(period) -> float (0-1)
- Integrate with droid_session.py token data
- Use config/models.yaml for pricing

GATE:
- python scripts/kpi_tracker.py --test-calculations

EVIDENCE REQUIRED:
- Calculator functions
- Test output

PRE-FLIGHT GATES:
- ruff check scripts/kpi_tracker.py && mypy scripts/kpi_tracker.py
- pytest tests/test_kpi_tracker.py -x (if exists)

MODE 4 VERIFICATION (Verifier):
- droid exec -m gpt-5.3-codex --session-id <verify_session> "Audit metric calculators: Accurate? Edge cases handled? List issues."
- If issues → fix → re-verify (MAX 2 iterations)
```

---

### Step 4 — Create Factory Hook for KPI Capture

```text
DO:
- Create ~/.factory/hooks/kpi-capture.py (PostToolUse hook)
- Hook triggers after droid exec completes
- Hook reads .droid_token_usage.jsonl for latest entry
- Hook calls kpi_tracker.py to log aggregated event
- NO modification to droid_session.py (zero regression risk)

Hook logic:
1. Check if tool was 'droid exec' completion
2. Parse latest entry from .droid_token_usage.jsonl
3. Call: python scripts/kpi_tracker.py log --from-token-log
4. Exit 0 (non-blocking)

GATE:
- ls ~/.factory/hooks/kpi-capture.py
- python ~/.factory/hooks/kpi-capture.py --test (dry run)

EVIDENCE REQUIRED:
- kpi-capture.py content
- Test output showing log ingestion

PRE-FLIGHT GATES:
- python -m py_compile ~/.factory/hooks/kpi-capture.py

MODE 4 VERIFICATION (Verifier):
- droid exec -m gpt-5.3-codex --session-id <verify_session> "Audit kpi-capture.py: Safe? Non-blocking? List issues."
- If issues → fix → re-verify (MAX 2 iterations)
```

---

### Step 5 — Integrate with droid-review.sh

```text
DO:
- Modify droid-review.sh to log review_cycle events
- Capture P0/P1 issue counts from review output
- Call kpi_tracker.py to log event
- Add --no-kpi flag to skip logging if needed

GATE:
- ./scripts/droid-review.sh --help shows --no-kpi option

EVIDENCE REQUIRED:
- droid-review.sh diff
- Help output

CODE REVIEW:
- droid exec -m gpt-5.3-codex "Review droid-review.sh KPI integration"
- droid exec -m gemini-3-pro-preview "Review shell script quality"
```

---

### Step 6 — Implement CLI Report Commands

```text
DO:
- Add CLI to kpi_tracker.py using argparse:
  - report: Show KPIs for current billing cycle
  - report --daily: Daily breakdown
  - report --weekly: Weekly breakdown
  - report --summary: One-line summary
  - report --json: JSON output for tooling
- Format output as readable table

GATE:
- python scripts/kpi_tracker.py report --summary

EVIDENCE REQUIRED:
- CLI implementation
- Sample report output

CODE REVIEW:
- droid exec -m gpt-5.3-codex "Review KPI CLI for usability"
- droid exec -m gemini-3-pro-preview "Review CLI output format"
```

---

### Step 7 — Documentation and Final Verification

```text
DO:
- Update docs/reference/kpi-schema.md with final format
- Add KPI section to AGENTS.md
- Update docs/CONFIGURATION.md with KPI settings
- Update CHANGELOG.md
- Run full integration test

GATE:
- python scripts/kpi_tracker.py report --summary
- CHANGELOG.md updated

EVIDENCE REQUIRED:
- Documentation diffs
- Final report output
- CHANGELOG entry

CODE REVIEW:
- droid exec -m gpt-5.3-codex "Final review of KPI system"
- droid exec -m gemini-3-pro-preview "Final review of KPI system"
```

---

## STOP CONDITIONS

```text
STOP IF:
- Token log format (.droid_token_usage.jsonl) incompatible with parser
- Factory hook system doesn't support PostToolUse events
- Storage file corruption detected

ON STOP:
- Report exact blocker
- No rollback needed (droid_session.py unchanged)
- Propose at most 2 resolution options
```

---

## EXPECTED BENEFITS

| Benefit | Metric |
|---------|--------|
| Prove ROI | Actual $/feature visible |
| Model selection | Data on which model costs less |
| Identify bottlenecks | "Reviews take 40% of cycle time" |
| Budget forecasting | Predict monthly AI spend |

---

## KPI METRICS TO TRACK

| Metric | Formula | Target |
|--------|---------|--------|
| Cycle Time | task_end.timestamp - task_start.timestamp | Track, optimize |
| Token Cost | tokens_used * price_per_token | < $X/PR |
| Iteration Count | count(review_cycles) per task | ≤ 2 |
| Gate Pass Rate | passed_gates / total_gates | > 80% |

---

## DATA FLOW (Hook-Based, Zero Regression)

```
droid exec start
    └─→ droid_session.py: get_or_create_session() [UNCHANGED]

droid exec complete
    └─→ droid_session.py: log_token_usage() [UNCHANGED]
        └─→ writes to .droid_token_usage.jsonl
    └─→ Factory PostToolUse hook: kpi-capture.py
        └─→ reads .droid_token_usage.jsonl (latest entry)
        └─→ calls kpi_tracker.py log --from-token-log
        └─→ writes to .droid/kpis.jsonl

droid-review.sh complete
    └─→ kpi_tracker.py: log_event(review_cycle)

User runs report
    └─→ python scripts/kpi_tracker.py report
        └─→ Read .droid/kpis.jsonl
        └─→ Calculate aggregates
        └─→ Display table
```

**Key benefit:** droid_session.py is NEVER modified. KPI system is purely additive.

---

## REPORTING FORMAT (strict)

After **every step**, the agent must output:

```text
STEP <N> STATUS: PASS / FAIL

Changed files:
- <path>

Gate output:
<pasted output>

Code Review (GPT-5.3):
<summary of findings>

Code Review (Gemini Pro):
<summary of findings>

Next:
- Proceed to Step <N+1> OR STOP
```
