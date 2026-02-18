# 2026-02-16-plan-gap09-pipeline-orchestrator

**Status:** IN_PROGRESS
**Created:** 2026-02-16
**Priority:** P0 (Critical)
**Estimated Effort:** 8-12 hours
**Source:** Model consultation feedback (GPT-5.3-Codex, Gemini Pro, Opus)

---

## EXECUTION MODE HEADER (mandatory)

```text
STAGE: 3 — Execution
MODE: Mode 3 — Build (Cascade implements)
SPEC STATUS: FROZEN (this plan is read-only during execution)
SCOPE: GAP-09 Pipeline Orchestrator only
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
Create pipeline_runner.py to orchestrate the 5-stage AI coding pipeline

GOAL:
Connect the 5 stages (Discovery → Planning → Execution → Verification → Ship) with
automated transitions, session management, pre-flight gates, and re-verify caps.

DONE WHEN (all true):
- [ ] scripts/pipeline_runner.py exists with full 5-stage orchestration
- [ ] Dual-model discovery (Stage 1) uses run_discovery_dual_model()
- [ ] Planning with review (Stage 2) uses run_planning_with_review()
- [ ] Pre-flight gates run before each verification
- [ ] Re-verify loop capped at 2 iterations
- [ ] Session IDs preserved within stages, separate for verification
- [ ] Risk-based routing: small changes skip Stage 1/2
- [ ] Gate command passes: python scripts/pipeline_runner.py --help
- [ ] Integration test passes with a sample task

OUT OF SCOPE:
- Web UI for pipeline monitoring
- Real-time streaming dashboard
- CI/CD integration (separate GAP)
- Traycer integration (GAP-07)
```

---

## GLOBAL CONSTRAINTS

```text
CONSTRAINTS:
- Language: Python 3.12 with type annotations
- Location: scripts/pipeline_runner.py
- Dependencies: Use existing droid_core.py functions only
- No new external deps
- Follow existing scripts/droid_*.py patterns

SESSION MANAGEMENT:
- Start: droid exec -m swe-1-5 "Start GAP-09" (captures session_id)
- Continue: droid exec --session-id <id> "Next step..."
- WARNING: Changing models mid-session loses context
- Verification uses SEPARATE session (Verifier independence)

MODEL ASSIGNMENTS (from config/models.yaml):
- Execution: swe-1-5 or gpt-5.1-codex (Stage 3 - Build)
- Verification: gpt-5.3-codex (Stage 4 - Verify)
- Documentation: claude-haiku-4-5 (Stage 5 - Ship)
```

---

## EXISTING INFRASTRUCTURE (extend, don't duplicate)

| Component | Location | Reuse Strategy |
|-----------|----------|----------------|
| Multi-model execution | `scripts/droid_core.py` | Use run_discovery_dual_model(), run_planning_with_review(), run_parallel_models() |
| Pre-flight gates | `scripts/droid_core.py` | Use run_with_preflight_gates() |
| Task execution | `scripts/droid_core.py` | Use run_droid_exec() |
| Model config | `config/models.yaml` | Dynamic model resolution |
| Session management | `scripts/droid_core.py` | DroidSession class |

## IMPLEMENTED INFRASTRUCTURE (2026-02-16)

The following functions are now implemented and wired into CLI dispatch:

### Multi-Model Functions (droid_core.py)

```python
# Stage 1: Dual-model discovery
run_discovery_dual_model(prompt, task_type, cwd) -> MultiModelResult
# Uses TOOL_CONFIGS[task_type]['model'] + ['dual_model']
# Results keyed by model ID (order-independent, fixes as_completed() bug)

# Stage 2: Tri-model planning with review
run_planning_with_review(prompt, task_type, cwd, max_review_iterations=2) -> MultiModelResult
# Uses 'model' (Sonnet) + 'parallel_model' (Flash) + 'review_model' (Codex)
# Enforces MAX 2 review iterations, then escalates

# Parallel execution across models
run_parallel_models(prompt, task_type, models, autonomy, cwd) -> dict[str, TaskResult]
# Returns {model_id: result} preserving identity regardless of completion order

# Multi-module parallel (distribute modules across models)
run_multi_module_parallel(module_prompts, task_type, models, autonomy, cwd) -> dict[str, TaskResult]
# Round-robin distribution of modules across models
```

### Pre-Flight Gates (droid_core.py)

```python
run_with_preflight_gates(prompt, task_type, cwd, run_lint=True, run_typecheck=True, run_tests=False) -> tuple[bool, str]
# FAIL-CLOSED: Missing tools (ruff/mypy/pytest) = FAIL, not SKIP
# Must pass before AI verification proceeds
```

### CLI Integration

```bash
# New flags available for all task types:
python -m scripts.droid_core analyze "Prompt" --dual      # Use dual-model discovery
python -m scripts.droid_core code "Prompt" --preflight   # Run pre-flight gates first
python -m scripts.droid_core spec "Prompt"               # Auto-uses tri-model planning
```

### Fixes Applied

1. **as_completed() ordering bug** - Fixed by using dict keyed by model ID instead of list
2. **Pre-flight gates fail-open** - Now fail-closed (FileNotFoundError = FAIL)
3. **Dead code call sites** - CLI dispatch now routes to multi-model functions based on task type and flags

---

## CANONICAL GATE

```text
CANONICAL GATE:
python scripts/pipeline_runner.py --help && \
python scripts/pipeline_runner.py --dry-run "Test task" && \
echo "PASS"
```

---

## PIPELINE ARCHITECTURE

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                        FABRIK AI CODING PIPELINE                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐                     │
│  │   Stage 1   │    │   Stage 2   │    │   Stage 3   │                     │
│  │  DISCOVERY  │───▶│  PLANNING   │───▶│  EXECUTION  │                     │
│  │             │    │             │    │             │                     │
│  │ GPT-5.3 +   │    │ Sonnet +    │    │   SWE-1.5   │                     │
│  │ Gemini Pro  │    │ Flash +     │    │   (Build)   │                     │
│  │ (Dual)      │    │ Codex Review│    │             │                     │
│  └─────────────┘    └─────────────┘    └──────┬──────┘                     │
│                                               │                             │
│                                               ▼                             │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐                     │
│  │   Stage 5   │    │   Stage 4   │    │ PRE-FLIGHT  │                     │
│  │    SHIP     │◀───│ VERIFICATION│◀───│   GATES     │                     │
│  │             │    │             │    │             │                     │
│  │  Haiku 4.5  │    │ GPT-5.3-    │    │ ruff, mypy  │                     │
│  │  (Docs)     │    │ Codex       │    │ pytest      │                     │
│  └─────────────┘    │ (MAX 2 iter)│    │             │                     │
│                     └─────────────┘    └─────────────┘                     │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │ RISK ROUTER: Small changes → Skip Stage 1/2 → Direct to Stage 3        ││
│  └─────────────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## EXECUTION STEPS

### Step 1 — Create pipeline_runner.py Skeleton

```text
DO:
- Create scripts/pipeline_runner.py with:
  - PipelineConfig dataclass (stages, models, session_ids, caps)
  - PipelineResult dataclass (stage_results, total_time, tokens_used)
  - RiskLevel enum (LOW, MEDIUM, HIGH)
  - Main orchestration function: run_pipeline()
  - CLI interface with argparse

GATE:
- python scripts/pipeline_runner.py --help

EVIDENCE REQUIRED:
- pipeline_runner.py skeleton content
- --help output

SELF-REVIEW (Builder):
- Check: Type annotations on all functions
- Check: Imports from droid_core.py

PRE-FLIGHT GATES:
- ruff check scripts/pipeline_runner.py && mypy scripts/pipeline_runner.py

MODE 4 VERIFICATION (Verifier):
- droid exec -m gpt-5.3-codex --session-id <verify_session> "Audit pipeline_runner.py skeleton: Types? Imports? Structure?"
- If issues → fix → re-verify (MAX 2 iterations)
```

---

### Step 2 — Implement Risk Router

```text
DO:
- Add assess_risk() function that returns RiskLevel based on:
  - Number of files changed
  - Presence of keywords (security, auth, database, API)
  - Complexity indicators
- Add route_by_risk() that determines starting stage:
  - LOW: Skip to Stage 3 (Execution)
  - MEDIUM: Start at Stage 2 (Planning)
  - HIGH: Start at Stage 1 (Discovery)

GATE:
- python -c "from scripts.pipeline_runner import assess_risk, RiskLevel; print(assess_risk('Fix typo in README'))"

EVIDENCE REQUIRED:
- assess_risk() implementation
- Test output showing risk levels

SELF-REVIEW (Builder):
- Check: Risk criteria comprehensive
- Check: Default to HIGH for unknown

PRE-FLIGHT GATES:
- ruff check scripts/pipeline_runner.py && mypy scripts/pipeline_runner.py

MODE 4 VERIFICATION (Verifier):
- droid exec -m gpt-5.3-codex --session-id <verify_session> "Audit risk router: Complete criteria? Safe defaults?"
- If issues → fix → re-verify (MAX 2 iterations)
```

---

### Step 3 — Implement Stage 1 (Discovery) Integration

```text
DO:
- Add run_stage_1_discovery() that:
  - Calls run_discovery_dual_model() from droid_core.py
  - Captures session_id for continuity
  - Outputs merged spec from both models
  - Returns StageResult with success/failure

GATE:
- python -c "from scripts.pipeline_runner import run_stage_1_discovery; help(run_stage_1_discovery)"

EVIDENCE REQUIRED:
- run_stage_1_discovery() implementation
- Integration with droid_core.run_discovery_dual_model()

SELF-REVIEW (Builder):
- Check: Uses dual_model from TOOL_CONFIGS
- Check: Session ID captured

PRE-FLIGHT GATES:
- ruff check scripts/pipeline_runner.py && mypy scripts/pipeline_runner.py

MODE 4 VERIFICATION (Verifier):
- droid exec -m gpt-5.3-codex --session-id <verify_session> "Audit Stage 1 implementation: Dual-model? Session management?"
- If issues → fix → re-verify (MAX 2 iterations)
```

---

### Step 4 — Implement Stage 2 (Planning) Integration

```text
DO:
- Add run_stage_2_planning() that:
  - Calls run_planning_with_review() from droid_core.py
  - Uses max_review_iterations=2 (cap)
  - Captures session_id
  - Returns StageResult with plan output

GATE:
- python -c "from scripts.pipeline_runner import run_stage_2_planning; help(run_stage_2_planning)"

EVIDENCE REQUIRED:
- run_stage_2_planning() implementation
- max_review_iterations=2 enforced

SELF-REVIEW (Builder):
- Check: Review cap enforced
- Check: Uses parallel_model and review_model

PRE-FLIGHT GATES:
- ruff check scripts/pipeline_runner.py && mypy scripts/pipeline_runner.py

MODE 4 VERIFICATION (Verifier):
- droid exec -m gpt-5.3-codex --session-id <verify_session> "Audit Stage 2 implementation: Review cap? Model assignments?"
- If issues → fix → re-verify (MAX 2 iterations)
```

---

### Step 5 — Implement Stage 3 (Execution) with Pre-Flight Gates

```text
DO:
- Add run_stage_3_execution() that:
  - FIRST runs run_with_preflight_gates() from droid_core.py
  - ONLY IF gates pass: calls run_droid_exec() with SWE-1.5
  - Uses session_id from Stage 2
  - Supports multi-module parallel execution via run_multi_module_parallel()

GATE:
- python -c "from scripts.pipeline_runner import run_stage_3_execution; help(run_stage_3_execution)"

EVIDENCE REQUIRED:
- run_stage_3_execution() implementation
- Pre-flight gates integration

SELF-REVIEW (Builder):
- Check: Pre-flight gates before execution
- Check: SWE-1.5 model used

PRE-FLIGHT GATES:
- ruff check scripts/pipeline_runner.py && mypy scripts/pipeline_runner.py

MODE 4 VERIFICATION (Verifier):
- droid exec -m gpt-5.3-codex --session-id <verify_session> "Audit Stage 3 implementation: Pre-flight gates? Correct model?"
- If issues → fix → re-verify (MAX 2 iterations)
```

---

### Step 6 — Implement Stage 4 (Verification) with Re-Verify Cap

```text
DO:
- Add run_stage_4_verification() that:
  - Uses SEPARATE session_id (Verifier independence)
  - Uses GPT-5.3-Codex for audit
  - Enforces MAX 2 re-verify iterations
  - After 2 failures: escalates to human or second verifier
  - Returns structured JSON issues list

GATE:
- python -c "from scripts.pipeline_runner import run_stage_4_verification; help(run_stage_4_verification)"

EVIDENCE REQUIRED:
- run_stage_4_verification() implementation
- Re-verify cap enforced

SELF-REVIEW (Builder):
- Check: Separate session for verifier
- Check: MAX 2 iterations enforced
- Check: Escalation path defined

PRE-FLIGHT GATES:
- ruff check scripts/pipeline_runner.py && mypy scripts/pipeline_runner.py

MODE 4 VERIFICATION (Verifier):
- droid exec -m gpt-5.3-codex --session-id <verify_session> "Audit Stage 4 implementation: Separate session? Re-verify cap? Escalation?"
- If issues → fix → re-verify (MAX 2 iterations)
```

---

### Step 7 — Implement Stage 5 (Ship) and Main Orchestrator

```text
DO:
- Add run_stage_5_ship() that:
  - Uses Haiku 4.5 for documentation
  - Only runs if code changes affect docs/API/config
  - Updates CHANGELOG.md, README.md as needed
- Add run_pipeline() main orchestrator that:
  - Assesses risk and routes to appropriate starting stage
  - Executes stages in sequence
  - Manages session IDs across stages
  - Collects metrics (time, tokens, iterations)
  - Returns PipelineResult

GATE:
- python scripts/pipeline_runner.py --dry-run "Add health endpoint"

EVIDENCE REQUIRED:
- run_stage_5_ship() implementation
- run_pipeline() main orchestrator
- --dry-run output

SELF-REVIEW (Builder):
- Check: Conditional docs stage
- Check: Full pipeline flow

PRE-FLIGHT GATES:
- ruff check scripts/pipeline_runner.py && mypy scripts/pipeline_runner.py && pytest tests/test_pipeline_runner.py -x

MODE 4 VERIFICATION (Verifier - FINAL):
- droid exec -m gpt-5.3-codex --session-id <verify_session> "Final audit GAP-09: All stages implemented? Gates? Caps? Ready to use?"
- Must return: {"ready": true, "issues": []}
```

---

## STOP CONDITIONS

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

## EXPECTED BENEFITS

| Benefit | Metric |
|---------|--------|
| Reduced token cost | -40% via risk routing (skip Stage 1/2 for small changes) |
| Faster execution | -30% via pre-flight gates (catch errors before LLM) |
| Near-flawless code | +50% first-pass success via dual-model + review |
| Reduced review burden | -60% human reviews via automated verification |

---

## DATA FLOW

```text
Input Task
    │
    ▼
┌───────────────┐
│ Risk Router   │ → LOW: Skip to Stage 3
│               │ → MEDIUM: Start Stage 2
│               │ → HIGH: Start Stage 1
└───────┬───────┘
        │
        ▼
┌───────────────┐     session_id_1
│ Stage 1       │ ───────────────────▶ Spec Output
│ Discovery     │     (dual-model)
└───────┬───────┘
        │
        ▼
┌───────────────┐     session_id_1 (continued)
│ Stage 2       │ ───────────────────▶ Plan Output
│ Planning      │     (tri-model)
└───────┬───────┘
        │
        ▼
┌───────────────┐     session_id_2 (new for build)
│ Stage 3       │ ───────────────────▶ Code Output
│ Execution     │     (pre-flight → SWE-1.5)
└───────┬───────┘
        │
        ▼
┌───────────────┐     session_id_3 (SEPARATE for verify)
│ Stage 4       │ ───────────────────▶ Audit Output
│ Verification  │     (GPT-5.3-Codex, max 2 iter)
└───────┬───────┘
        │
        ▼
┌───────────────┐     session_id_4 (docs only)
│ Stage 5       │ ───────────────────▶ Docs Output
│ Ship          │     (Haiku 4.5, conditional)
└───────┬───────┘
        │
        ▼
    Pipeline Result
    {stages: [], metrics: {time, tokens, iterations}}
```

---

## REPORTING FORMAT (strict)

After **every step**, the agent must output:

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

---

## SESSION MANAGEMENT

```text
SESSION RULES:
1. Start execution session: droid exec -m swe-1-5 "Begin GAP-09 Step 1"
2. Capture session_id from response
3. Continue with: droid exec --session-id <id> "Step 2..."
4. Verification uses SEPARATE session (Verifier independence)
5. If model change needed: Start new session, summarize context first
6. Document session_id in each step report

WHY THIS MATTERS:
- Same session = AI remembers previous steps
- Different model = context lost (new session auto-created)
- Provider switch (OpenAI↔Anthropic) = full context reset
```
