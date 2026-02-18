# GAP-09 Pipeline Orchestrator — Spec-Level Implementation Plan

**Version:** 1.3.0
**Revision Date:** 2026-02-17
**Status:** SPEC (not implementation)
**Compliance:** GAP-09 v1.0
**Source:** `@/opt/fabrik/docs/development/plans/archived/2026-02-16-plan-gap09-pipeline-orchestrator.md`

---

## Implementation Readiness Checklist

> **Pre-implementation step:** Before starting, verify repo paths exist and run the canonical gate on a clean checkout. Check boxes as verified.

| Checkbox | Verification Method |
|----------|--------------------|
| [ ] **Spec-Level Implementation Plan attached** | This document exists |
| [ ] Repo grounding paths verified | `ls scripts/droid_core.py config/models.yaml` |
| [ ] Required Artifacts list complete | Review Section 2 artifacts table |
| [ ] Deterministic Gate passes | `python scripts/pipeline_runner.py --help && python scripts/pipeline_runner.py run "Test" --dry-run && echo PASS` |
| [ ] DONE WHEN measurable | Each criterion has a gate command |
| [ ] Failure modes defined | Section 5 Failure Matrix complete |

---

## Artifacts Table

| Path | Action | Purpose | Gate Coverage |
|------|--------|---------|---------------|
| `scripts/pipeline_runner.py` | CREATE | 5-stage pipeline orchestrator | Canonical gate |
| `tests/test_pipeline_runner.py` | CREATE | Unit tests for pipeline | `pytest tests/test_pipeline_runner.py` |
| `.factory/reports/<run_id>/report.json` | CREATE (runtime) | Execution report | Schema validation |
| `.factory/reports/latest` | CREATE (symlink) | Points to most recent run | `test -L .factory/reports/latest` |
| `CHANGELOG.md` | MODIFY | Document GAP-09 completion | `grep -q "GAP-09" CHANGELOG.md` |

---

## Report Contract

**Path convention:** `.factory/reports/<run_id>/report.json`

**Latest symlink:** `.factory/reports/latest` → `.factory/reports/<most_recent_run_id>/`

> **Windows fallback:** On Windows (or if symlink creation fails), write `.factory/reports/latest.txt` containing the run_id instead. Quick validation commands should check for symlink first, then fall back to `latest.txt`.

> **Rule:** Pipeline MUST create report at `<run_id>/report.json` AND update `latest` pointer (symlink or `latest.txt`) after successful completion.

**Schema (minimal required fields):**

```json
{
  "run_id": "uuid-v4-string",
  "task": "original task description",
  "status": "success | failed | escalated",
  "risk_level": "LOW | MEDIUM | HIGH",
  "stages": [
    {
      "name": "discovery | planning | execution | verification | ship",
      "session_id": "string",
      "model": "model-id",
      "started_at": "ISO8601",
      "ended_at": "ISO8601",
      "success": true,
      "tokens_used": 1234,
      "output_summary": "string (max 500 chars)"
    }
  ],
  "timestamps": {
    "started_at": "ISO8601",
    "ended_at": "ISO8601",
    "duration_seconds": 123.45
  },
  "metrics": {
    "total_tokens": 5000,
    "verification_iterations": 1,
    "stages_executed": 5
  },
  "errors": [
    {
      "stage": "string",
      "message": "string",
      "recoverable": false
    }
  ]
}
```

**Validation command (accepts run_id or defaults to latest):**

```bash
# Validate specific run:
python -c "
import json, sys
from pathlib import Path
run_id = sys.argv[1] if len(sys.argv) > 1 else 'latest'
report_path = Path(f'.factory/reports/{run_id}/report.json')
if not report_path.exists(): sys.exit(f'Report not found: {report_path}')
report = json.loads(report_path.read_text())
required = ['run_id', 'task', 'status', 'stages', 'timestamps']
missing = [f for f in required if f not in report]
if missing: sys.exit(f'Missing fields: {missing}')
print(f'✓ Report schema valid: {run_id}')
" [RUN_ID]
```

**Quick validation (latest):**

```bash
python -c "import json; from pathlib import Path; r=json.loads(Path('.factory/reports/latest/report.json').read_text()); assert all(k in r for k in ['run_id','task','status']); print('✓ Valid')"
```

---

## Risk Routing Reasoning

> **Rule:** Unknown risk = HIGH to be fail-safe; must be visible in report.

| Risk | Start Stage | Reasoning |
|------|-------------|----------|
| HIGH | Discovery (Stage 1) | Auth, security, database, API, migration need full analysis |
| MEDIUM | Planning (Stage 2) | Features, endpoints, components skip discovery |
| LOW | Execution (Stage 3) | Typos, docs, comments skip planning |
| UNKNOWN | Discovery (Stage 1) | Fail-safe: treat unknown as HIGH |

**UNKNOWN handling (deterministic):**

```python
def assess_risk(task: str) -> RiskLevel:
    """Returns RiskLevel. UNKNOWN is not a valid return value."""
    task_lower = task.lower()
    # HIGH keywords
    if any(kw in task_lower for kw in ['auth', 'security', 'database', 'api', 'migration']):
        return RiskLevel.HIGH
    # MEDIUM keywords
    if any(kw in task_lower for kw in ['feature', 'endpoint', 'component']):
        return RiskLevel.MEDIUM
    # LOW keywords
    if any(kw in task_lower for kw in ['typo', 'fix', 'docs', 'comment', 'readme']):
        return RiskLevel.LOW
    # Default: HIGH (fail-safe, no UNKNOWN state)
    return RiskLevel.HIGH
```

> **Exit code 5** is for risk assessment *function failure* (exception), not for unknown classification. The function MUST always return a valid RiskLevel (defaulting to HIGH).

---

## 1. Repo Grounding (Mandatory First Section)

### A. Structure Map (Top 3 Levels)

```
/opt/fabrik/
├── scripts/
│   ├── droid_core.py          # Core execution functions
│   ├── droid_models.py        # Model resolution
│   ├── droid_session.py       # Session management
│   ├── process_monitor.py     # Process tracking
│   └── enforcement/           # Validation scripts
├── config/
│   └── models.yaml            # Model configuration
├── tests/
│   ├── test_droid_core.py     # Existing droid tests
│   └── orchestrator/          # Orchestrator tests exist
└── docs/development/plans/
    └── 2026-02-16-plan-gap09-pipeline-orchestrator.md
```

### B. GAP-09 Integration Points

| Component | Status | Path |
|-----------|--------|------|
| `run_discovery_dual_model()` | **FOUND** | `scripts/droid_core.py:1224` |
| `run_planning_with_review()` | **FOUND** | `scripts/droid_core.py:1298` |
| `run_with_preflight_gates()` | **FOUND** | `scripts/droid_core.py:1488` |
| `run_parallel_models()` | **FOUND** | `scripts/droid_core.py:1163` |
| `run_droid_exec()` | **FOUND** | `scripts/droid_core.py` |
| `scripts/pipeline_runner.py` | **NOT FOUND** | **CREATE required** |
| `tests/test_pipeline_runner.py` | **NOT FOUND** | **CREATE required** |

### C. Blockers

| Blocker | Fix |
|---------|-----|
| `scripts/pipeline_runner.py` does not exist | **CREATE** (GAP-09 scope) |
| `tests/test_pipeline_runner.py` does not exist | **CREATE** (GAP-09 scope) |

---

## 2. Required Artifacts (CREATE vs MODIFY)

| Path | Action | Justification | NOT Changed | Diff Size |
|------|--------|---------------|-------------|-----------|
| `scripts/pipeline_runner.py` | **CREATE** | GAP-09 DONE WHEN | — | **L** |
| `tests/test_pipeline_runner.py` | **CREATE** | GAP-09 DONE WHEN | — | **M** |
| `scripts/droid_core.py` | **VERIFY** | Confirm functions exist | All code | **0** |
| `config/models.yaml` | **VERIFY** | Confirm stage configs | All config | **0** |

**Explicitly NOT created/modified (OUT OF SCOPE per GAP-09):**
- `.github/workflows/*`
- Any CI/CD integration
- Web UI for pipeline monitoring
- Real-time streaming dashboard
- Traycer integration (GAP-07)

---

## 3. Interface & Contract Specification

### A. CLI Contract

**Command syntax:**

```bash
python scripts/pipeline_runner.py <command> [options]
```

**Subcommands:**

| Subcommand | Description |
|------------|-------------|
| `run` | Execute full pipeline |
| `stage` | Execute single stage |
| `--help` | Show help |

**Flags for `run`:**

| Flag | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `TASK` | positional | yes | — | Task description |
| `--dry-run` | flag | no | false | Simulate without execution |
| `--stage` | choice | no | auto | Start stage: `discovery`, `planning`, `execution`, `verification`, `ship` |
| `--risk` | choice | no | auto | Override: `low`, `medium`, `high` |
| `--cwd` | path | no | `.` | Working directory |
| `--json` | flag | no | false | JSON output |

**Exit codes:**

| Code | Meaning |
|------|---------|
| `0` | Success |
| `1` | Stage failure |
| `2` | Retry exhausted (MAX 2 verification iterations) |
| `3` | Configuration error |
| `4` | Pre-flight gate failure |
| `5` | Risk assessment failure |

### B. State Machine Definition

**Session ID Allocation (per GAP-09 DATA FLOW):**

| Session | Stages | Purpose |
|---------|--------|---------|
| `session_id_1` | Stage 1 + Stage 2 | Discovery → Planning continuity |
| `session_id_2` | Stage 3 | Execution (new session for build) |
| `session_id_3` | Stage 4 | Verification (SEPARATE for Verifier independence) |
| `session_id_4` | Stage 5 | Documentation (docs only) |

**Stage transition table:**

```
┌────────────────┬─────────────────┬─────────────┬────────────────┬─────────────┐
│ Current State  │ Event           │ Next State  │ Action         │ Session     │
├────────────────┼─────────────────┼─────────────┼────────────────┼─────────────┤
│ INIT           │ risk=HIGH       │ DISCOVERY   │ run_stage_1    │ session_1   │
│ INIT           │ risk=MEDIUM     │ PLANNING    │ run_stage_2    │ session_1   │
│ INIT           │ risk=LOW        │ EXECUTION   │ run_stage_3    │ session_2   │
│ DISCOVERY      │ success         │ PLANNING    │ run_stage_2    │ session_1   │
│ DISCOVERY      │ failure         │ FAILED      │ report_error   │ —           │
│ PLANNING       │ success         │ EXECUTION   │ run_stage_3    │ session_2   │
│ PLANNING       │ failure         │ FAILED      │ report_error   │ —           │
│ EXECUTION      │ success         │ PRE_VERIFY  │ run_preflight  │ session_2   │
│ EXECUTION      │ failure         │ FAILED      │ report_error   │ —           │
│ PRE_VERIFY     │ gates_pass      │ VERIFICATION│ run_stage_4    │ session_3   │
│ PRE_VERIFY     │ gates_fail      │ FAILED      │ exit(4)        │ —           │
│ VERIFICATION   │ approved        │ SHIP        │ run_stage_5    │ session_4   │
│ VERIFICATION   │ rejected, n<2   │ EXECUTION   │ run_stage_3    │ session_2   │
│ VERIFICATION   │ rejected, n=2   │ FAILED      │ exit(2)        │ —           │
│ SHIP           │ success/skip    │ DONE        │ report_success │ session_4   │
│ SHIP           │ failure         │ FAILED      │ report_error   │ —           │
└────────────────┴─────────────────┴─────────────┴────────────────┴─────────────┘
```

**Pre-flight gates position (per GAP-09):**

| Gate Point | Requirement | Source |
|------------|-------------|--------|
| Before Stage 4 Verification | **MUST** run (fail-closed) | GAP-09 DONE WHEN: "Pre-flight gates run before each verification" |
| Before Stage 3 Execution | **MAY** run (optional) | GAP-09 Step-5: "FIRST runs run_with_preflight_gates()" |

**Rule:** The pre-verify gate (before Stage 4) is mandatory and cannot be skipped. The pre-execution gate (before Stage 3) is optional but recommended. Running pre-execution does NOT satisfy the pre-verify requirement.

```
                    ┌─────────────────┐
                    │ PRE-FLIGHT      │  ◀── MAY run (optional, per Step-5)
                    │ (optional)      │
                    └────────┬────────┘
                             │
                             ▼
                    Stage 3 EXECUTION
                             │
                             ▼
                    ┌─────────────────┐
                    │ PRE-FLIGHT      │  ◀── MUST run (mandatory, per DONE WHEN)
                    │ GATES           │
                    │ ruff, mypy      │
                    │ FAIL-CLOSED     │
                    └────────┬────────┘
                             │ gates_pass
                             ▼
                    Stage 4 VERIFICATION
```

**Risk routing:**

| Risk Level | Starting Stage | Stages Executed |
|------------|----------------|-----------------|
| `LOW` | 3 (Execution) | 3 → preflight → 4 → 5 |
| `MEDIUM` | 2 (Planning) | 2 → 3 → preflight → 4 → 5 |
| `HIGH` | 1 (Discovery) | 1 → 2 → 3 → preflight → 4 → 5 |

### C. Data Contract

> **Clarification:** `StageResult` is an internal dataclass used during execution. `report.json` is the persisted external report format written to disk.

**StageResult schema (internal dataclass):**

```json
{
  "stage": "verification",
  "status": "pass",
  "started_at": "2026-02-16T18:02:31Z",
  "ended_at": "2026-02-16T18:03:45Z",
  "session_id": "session_id_3",
  "model": "gpt-5.3-codex",
  "output": "{\"approved\": true}",
  "iteration": 1,
  "tokens_used": 800
}
```

**StageResult → report.json mapping:**

| StageResult field | report.json field | Notes |
|-------------------|-------------------|-------|
| `stage` | `stages[].name` | Stage name |
| `session_id` | `stages[].session_id` | Direct copy |
| `model` | `stages[].model` | Direct copy |
| `started_at` | `stages[].started_at` | Direct copy |
| `ended_at` | `stages[].ended_at` | Direct copy |
| `status` | `stages[].success` | `"pass"` → `true` |
| `tokens_used` | `stages[].tokens_used` | **Canonical name** |
| `output` | `stages[].output_summary` | Truncated to 500 chars |

**PipelineResult schema:**

```json
{
  "version": "1.0.0",
  "task": "Add health endpoint",
  "risk": "low",
  "status": "success",
  "stages": [ ... ],
  "metrics": {
    "total_time_seconds": 226,
    "total_tokens_used": 2000,
    "verification_iterations": 1,
    "stages_executed": 2,
    "stages_skipped": 3
  }
}
```

---

## 4. Golden Paths (2 Required)

### Golden Path 1: LOW Risk Task

**Command:**
```bash
python scripts/pipeline_runner.py run "Fix typo in README.md" --json
```

**Expected flow:**
```
INIT → risk=LOW → EXECUTION(session_2) → PRE_VERIFY → VERIFICATION(session_3) → SHIP(session_4) → DONE
```

**Expected exit code:** `0`

**Expected file side effects:**
- `README.md` modified
- `.droid/pipeline_state_<uuid>.json` created

---

### Golden Path 2: HIGH Risk Task

**Command:**
```bash
python scripts/pipeline_runner.py run "Add JWT authentication endpoint"
```

**Expected flow:**
```
INIT → risk=HIGH → DISCOVERY(session_1) → PLANNING(session_1) → EXECUTION(session_2) → PRE_VERIFY → VERIFICATION(session_3) → SHIP(session_4) → DONE
```

**Expected exit code:** `0`

**Expected file side effects:**
- `src/api/auth.py` created
- `CHANGELOG.md` updated
- `.droid/pipeline_state_<uuid>.json` created

---

## 5. Failure Matrix (5 Cases)

| # | Failure Condition | Detection | Response | Exit Code |
|---|-------------------|-----------|----------|-----------|
| 1 | Pre-flight gate fails | `run_with_preflight_gates()` returns `(False, _)` | Abort before Stage 4 | `4` |
| 2 | Verification rejected twice | `iteration == 2` AND rejected | Escalate to human | `2` |
| 3 | Model not available | `droid exec` error | Print available models | `3` |
| 4 | Risk assessment fails | Empty task | Print error | `5` |
| 5 | Stage 3 execution fails | `TaskResult.success == False` | Abort pipeline | `1` |

---

## 6. Deterministic Gate Definition

**CANONICAL GATE (exactly as written in GAP-09):**

```bash
python scripts/pipeline_runner.py --help && \
python scripts/pipeline_runner.py run "Test task" --dry-run && \
echo "PASS"
```

**Expected PASS output:**
```
usage: pipeline_runner.py ...
...
PASS
```

**Expected FAIL output:**
```
Error: No module named 'scripts.pipeline_runner'
```

---

## 7. Step-Reporting Format (COMPLIANCE REQUIREMENT)

**Per GAP-09 REPORTING FORMAT, after every step the builder/verifier MUST output:**

```text
STEP <N> STATUS: PASS / FAIL
SESSION ID: <current_session_id>
MODE: Build → Verify

Changed files:
- <path>

Gate output:
<pasted output>

Self-Review (Builder):
- [x] Check 1 passed
- [x] Check 2 passed

Pre-Flight Gates:
- ruff: PASS/FAIL
- mypy: PASS/FAIL

Mode 4 Verification (Verifier):
- Result: PASS / FAIL
- Issues: <none or list>
- Re-verify count: <N>/2

Next:
- Proceed to Step <N+1> OR STOP (if verify failed)
```

**Compliance rules:**

1. Builders MUST include this report after each step
2. Verifiers MUST include this report after each audit
3. Session ID MUST be documented in each report
4. Pre-Flight Gates section MUST appear before Mode 4 Verification
5. Re-verify count MUST show current iteration out of MAX 2

---

## 8. Cross-System Impact

### Components Touched Indirectly

| Component | Impact |
|-----------|--------|
| `scripts/droid_core.py` | **READ-ONLY** — imports functions |
| `config/models.yaml` | **READ-ONLY** — reads stage configs |
| `.droid/` directory | **WRITE** — state persistence |

### Explicitly NOT Changed (OUT OF SCOPE per GAP-09)

| Component | Reason |
|-----------|--------|
| `.github/workflows/*` | OUT OF SCOPE |
| CI/CD integration | OUT OF SCOPE |
| Web UI for pipeline monitoring | OUT OF SCOPE |
| Real-time streaming dashboard | OUT OF SCOPE |
| Traycer integration | GAP-07 scope |
| `scripts/droid_core.py` | All functions exist |
| `src/` | No source changes |

### Duplication Avoidance

All stage execution uses existing `droid_core.py` functions:

| Stage | Function |
|-------|----------|
| Stage 1 | `run_discovery_dual_model()` |
| Stage 2 | `run_planning_with_review()` |
| Stage 3 | `run_droid_exec()` |
| Pre-verify | `run_with_preflight_gates()` |
| Stage 4 | `run_droid_exec()` with verification model |
| Stage 5 | `run_droid_exec()` with docs model |

---

## 9. Execution Steps (DO/GATE/EVIDENCE Format)

### Step 1 — Create pipeline_runner.py Skeleton

```text
DO:
- Create scripts/pipeline_runner.py with:
  - PipelineConfig dataclass (stages, models, session_ids, caps)
  - PipelineResult dataclass (stage_results, total_time, tokens_used)
  - RiskLevel enum (LOW, MEDIUM, HIGH)
  - StageResult dataclass matching schema in Section 3.C
  - CLI interface with argparse (flags from Section 3.A)

GATE:
python scripts/pipeline_runner.py --help

EVIDENCE REQUIRED:
- pipeline_runner.py exists with all dataclasses
- --help output showing all flags

SELF-REVIEW (Builder):
- [ ] Type annotations on all functions
- [ ] Imports from droid_core.py correct
- [ ] Dataclasses match schemas in Section 3.C

PRE-FLIGHT GATES:
ruff check scripts/pipeline_runner.py && mypy scripts/pipeline_runner.py

MODE 4 VERIFICATION:
- Verifier audits: Types? Imports? Structure?
- If issues → fix → re-verify (MAX 2 iterations)
```

---

### Step 2 — Implement Risk Router

```text
DO:
- Add assess_risk(task: str) -> RiskLevel function:
  - Returns HIGH for: "auth", "security", "database", "API", "migration"
  - Returns MEDIUM for: "feature", "endpoint", "component"
  - Returns LOW for: "typo", "fix", "docs", "comment", "readme"
  - Default to HIGH for unknown (fail-safe)
- Add route_by_risk(risk: RiskLevel) -> int (starting stage number)

GATE:
python -c "from scripts.pipeline_runner import assess_risk, RiskLevel; print(assess_risk('Fix typo in README'))"
# Expected: RiskLevel.LOW

EVIDENCE REQUIRED:
- assess_risk() returns correct RiskLevel for test inputs
- route_by_risk() maps to correct starting stage

SELF-REVIEW (Builder):
- [ ] Risk criteria comprehensive
- [ ] Default to HIGH for unknown (fail-safe)
- [ ] Keywords case-insensitive

PRE-FLIGHT GATES:
ruff check scripts/pipeline_runner.py && mypy scripts/pipeline_runner.py

MODE 4 VERIFICATION:
- Verifier audits: Complete criteria? Safe defaults?
- If issues → fix → re-verify (MAX 2 iterations)
```

---

### Step 3 — Implement Stage 1 (Discovery) Integration

```text
DO:
- Add run_stage_1_discovery(task: str, cwd: str) -> StageResult:
  - Calls run_discovery_dual_model() from droid_core.py
  - Captures session_id for continuity (session_id_1)
  - Outputs merged spec from both models
  - Returns StageResult with success/failure

GATE:
python -c "from scripts.pipeline_runner import run_stage_1_discovery; help(run_stage_1_discovery)"

EVIDENCE REQUIRED:
- run_stage_1_discovery() implementation
- Integration with droid_core.run_discovery_dual_model()

SELF-REVIEW (Builder):
- [ ] Uses dual_model from TOOL_CONFIGS
- [ ] Session ID captured and returned
- [ ] StageResult populated correctly

PRE-FLIGHT GATES:
ruff check scripts/pipeline_runner.py && mypy scripts/pipeline_runner.py

MODE 4 VERIFICATION:
- Verifier audits: Dual-model? Session management?
- If issues → fix → re-verify (MAX 2 iterations)
```

---

### Step 4 — Implement Stage 2 (Planning) Integration

```text
DO:
- Add run_stage_2_planning(task: str, session_id: str, cwd: str) -> StageResult:
  - Calls run_planning_with_review() from droid_core.py
  - Uses max_review_iterations=2 (cap)
  - Continues session_id_1 from Stage 1
  - Returns StageResult with plan output

GATE:
python -c "from scripts.pipeline_runner import run_stage_2_planning; help(run_stage_2_planning)"

EVIDENCE REQUIRED:
- run_stage_2_planning() implementation
- max_review_iterations=2 enforced

SELF-REVIEW (Builder):
- [ ] Review cap enforced (max_review_iterations=2)
- [ ] Uses parallel_model and review_model from config
- [ ] Session continuity maintained

PRE-FLIGHT GATES:
ruff check scripts/pipeline_runner.py && mypy scripts/pipeline_runner.py

MODE 4 VERIFICATION:
- Verifier audits: Review cap? Model assignments?
- If issues → fix → re-verify (MAX 2 iterations)
```

---

### Step 5 — Implement Stage 3 (Execution) with Pre-Flight Gates

```text
DO:
- Add run_stage_3_execution(task: str, plan: str, cwd: str) -> StageResult:
  - Uses NEW session (session_id_2)
  - Calls run_droid_exec() with execution model (swe-1-5)
  - Supports multi-module parallel execution via run_multi_module_parallel()
  - Returns StageResult with code output

GATE:
python -c "from scripts.pipeline_runner import run_stage_3_execution; help(run_stage_3_execution)"

EVIDENCE REQUIRED:
- run_stage_3_execution() implementation
- New session_id_2 created

SELF-REVIEW (Builder):
- [ ] NEW session for execution (session_id_2)
- [ ] SWE-1.5 model used (or equivalent from config)
- [ ] Code output captured

PRE-FLIGHT GATES:
ruff check scripts/pipeline_runner.py && mypy scripts/pipeline_runner.py

MODE 4 VERIFICATION:
- Verifier audits: New session? Correct model?
- If issues → fix → re-verify (MAX 2 iterations)
```

---

### Step 6 — Implement Pre-Verify Gates (MANDATORY)

```text
DO:
- Add run_pre_verify_gates(cwd: str) -> tuple[bool, str]:
  - Calls run_with_preflight_gates() from droid_core.py
  - FAIL-CLOSED: Missing tools = FAIL, not SKIP
  - Returns (passed, output)
- Integrate into pipeline: MUST run before Stage 4

GATE:
python -c "from scripts.pipeline_runner import run_pre_verify_gates; print(run_pre_verify_gates('.'))"

EVIDENCE REQUIRED:
- run_pre_verify_gates() implementation
- Integration point in pipeline flow

SELF-REVIEW (Builder):
- [ ] Fail-closed behavior (FileNotFoundError = FAIL)
- [ ] Runs ruff, mypy at minimum
- [ ] Pipeline blocks on failure (exit code 4)

PRE-FLIGHT GATES:
ruff check scripts/pipeline_runner.py && mypy scripts/pipeline_runner.py

MODE 4 VERIFICATION:
- Verifier audits: Fail-closed? Correct integration?
- If issues → fix → re-verify (MAX 2 iterations)
```

---

### Step 7 — Implement Stage 4 (Verification) with Re-Verify Cap

```text
DO:
- Add run_stage_4_verification(code_output: str, cwd: str, iteration: int) -> StageResult:
  - Uses SEPARATE session (session_id_3) for Verifier independence
  - Uses GPT-5.3-Codex (or verification model from config)
  - Tracks iteration count
  - Returns structured JSON with approved/rejected + issues

GATE:
python -c "from scripts.pipeline_runner import run_stage_4_verification; help(run_stage_4_verification)"

EVIDENCE REQUIRED:
- run_stage_4_verification() implementation
- Iteration tracking
- Separate session_id_3

SELF-REVIEW (Builder):
- [ ] SEPARATE session for verifier (session_id_3)
- [ ] Iteration count tracked
- [ ] JSON output with approved/rejected

PRE-FLIGHT GATES:
ruff check scripts/pipeline_runner.py && mypy scripts/pipeline_runner.py

MODE 4 VERIFICATION:
- Verifier audits: Separate session? Iteration tracking?
- If issues → fix → re-verify (MAX 2 iterations)
```

---

### Step 8 — Implement Re-Verify Loop with MAX 2 Cap

```text
DO:
- Add verification loop in run_pipeline():
  - If rejected AND iteration < 2: return to Stage 3 with feedback
  - If rejected AND iteration == 2: escalate (exit code 2)
  - If approved: proceed to Stage 5

GATE:
# Simulate rejection loop
python -c "
from scripts.pipeline_runner import PipelineRunner
p = PipelineRunner()
# Mock test showing MAX 2 iterations
print('MAX iterations:', p.MAX_VERIFY_ITERATIONS)
"

EVIDENCE REQUIRED:
- Loop logic in run_pipeline()
- MAX 2 constant defined
- Escalation path on exhaustion

SELF-REVIEW (Builder):
- [ ] MAX 2 iterations enforced
- [ ] Feedback passed back to Stage 3
- [ ] Exit code 2 on exhaustion

PRE-FLIGHT GATES:
ruff check scripts/pipeline_runner.py && mypy scripts/pipeline_runner.py

MODE 4 VERIFICATION:
- Verifier audits: Loop logic? Cap enforced? Escalation?
- If issues → fix → re-verify (MAX 2 iterations)
```

---

### Step 9 — Implement Stage 5 (Ship) and Main Orchestrator

```text
DO:
- Add run_stage_5_ship(code_output: str, cwd: str) -> StageResult:
  - Uses session_id_4
  - Uses Haiku 4.5 (or docs model from config)
  - Only runs if code changes affect docs/API/config
  - Updates CHANGELOG.md, README.md as needed
- Add run_pipeline(task: str, dry_run: bool, cwd: str) -> PipelineResult:
  - Assesses risk and routes to appropriate starting stage
  - Executes stages in sequence per state machine
  - Manages session IDs across stages
  - Collects metrics (time, tokens, iterations)

GATE:
python scripts/pipeline_runner.py run "Add health endpoint" --dry-run

EVIDENCE REQUIRED:
- run_stage_5_ship() implementation
- run_pipeline() main orchestrator
- --dry-run output showing full flow

SELF-REVIEW (Builder):
- [ ] Conditional docs stage (skip if no doc changes)
- [ ] Full pipeline flow matches state machine
- [ ] Metrics collected (time, tokens, iterations)

PRE-FLIGHT GATES:
ruff check scripts/pipeline_runner.py && mypy scripts/pipeline_runner.py

MODE 4 VERIFICATION:
- Verifier audits: Full flow? Metrics? Docs conditional?
- If issues → fix → re-verify (MAX 2 iterations)
```

---

### Step 10 — Create Unit Tests

```text
DO:
- Create tests/test_pipeline_runner.py with:
  - test_assess_risk_low()
  - test_assess_risk_medium()
  - test_assess_risk_high()
  - test_route_by_risk()
  - test_dry_run_flow()
  - test_max_verify_iterations()

GATE:
pytest tests/test_pipeline_runner.py -v

EVIDENCE REQUIRED:
- All tests pass
- Coverage > 70%

SELF-REVIEW (Builder):
- [ ] Risk routing tested
- [ ] Dry-run tested
- [ ] MAX iterations tested

PRE-FLIGHT GATES:
ruff check tests/test_pipeline_runner.py && mypy tests/test_pipeline_runner.py

MODE 4 VERIFICATION (FINAL):
- Verifier audits: All steps complete? Gates pass? Ready to use?
- Must return: {"ready": true, "issues": []}
```

---

### STOP CONDITIONS

```text
STOP IF:
- droid_core.py multi-model functions not available
- Model names in config/models.yaml changed significantly
- Pre-flight gate tools (ruff, mypy) not installed

ON STOP:
- Report exact blocker
- Propose at most 2 resolution options
```

---

## 10. Summary of GAP-09 Compliance

| Requirement | Status |
|-------------|--------|
| Canonical gate matches GAP-09 exactly | ✅ |
| CI/workflow changes removed | ✅ |
| Pre-flight gates before Stage 4 (fail-closed) | ✅ |
| Session IDs match GAP-09 dataflow | ✅ |
| Step-reporting format included | ✅ |

**All sections are GAP-09 compliant.** Ready for Mode 3 (Build) execution.
