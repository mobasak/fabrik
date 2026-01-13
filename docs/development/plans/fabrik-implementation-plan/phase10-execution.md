# Phase 10 — Deployment Orchestrator

## EXECUTION MODE HEADER

```text
MODE: EXECUTION (PLAN LOCKED)

RULES:
- Follow steps exactly in order
- Do NOT redesign or change scope
- One step at a time
- After each step: show Evidence + Gate result
- If a Gate fails or is unclear → STOP and report
```

---

## TASK METADATA

```text
TASK:
Deployment Orchestrator

GOAL:
fabrik apply spec.yaml deploys end-to-end without manual intervention

DONE WHEN (all true):
- fabrik apply creates DNS + deploys to Coolify + verifies health
- Failed deploy auto-rolls back created resources
- Re-running apply updates existing (no duplicates)
- Gate command passes: fabrik apply --dry-run tests/fixtures/test-api.yaml

OUT OF SCOPE:
- Web UI
- Multi-environment (staging/prod)
- WordPress content automation
- Vault integration
```

---

## GLOBAL CONSTRAINTS

```text
CONSTRAINTS:
- Language: Python 3.12
- No new deps unless stated
- Follow patterns in: src/fabrik/
- Backward compatibility: yes (existing CLI commands work)
```

---

## CANONICAL GATE

```text
CANONICAL GATE:
cd /opt/fabrik && pytest tests/orchestrator/ -q
```

---

## EXECUTION STEPS

### Step 1 — Skeleton

```text
DO:
- Create folder: src/fabrik/orchestrator/
- Create files (stubs only):
  - __init__.py
  - states.py (DeploymentState enum)
  - context.py (DeploymentContext dataclass)
  - exceptions.py (typed errors)
  - secrets.py (stub)
- Create folder: tests/orchestrator/
- Create folder: tests/fixtures/
- Create fixture: tests/fixtures/test-api.yaml
- Add to pyproject.toml if needed

GATE:
- python -c "from fabrik.orchestrator import DeploymentState, DeploymentContext"
- test -f tests/fixtures/test-api.yaml

EVIDENCE REQUIRED:
- File list
- Import succeeds
```

---

### Step 2 — State + Secrets

```text
DO:
- Implement states.py (state machine with transitions)
- Implement secrets.py (env → .env → generate)
- Unit tests for both

GATE:
- pytest tests/orchestrator/test_states.py tests/orchestrator/test_secrets.py -q

EVIDENCE REQUIRED:
- Files changed
- Test output
```

---

### Step 3 — Validator + Deployer

```text
DO:
- Implement validator.py (spec validation)
- Implement deployer.py (Coolify deploy, idempotent)
- Wire to existing CoolifyClient

GATE:
- pytest tests/orchestrator/test_validator.py tests/orchestrator/test_deployer.py -q

EVIDENCE REQUIRED:
- Files changed
- Test output
```

---

### Step 4 — Verifier + Rollback

```text
DO:
- Implement verifier.py (HTTP health check)
- Implement rollback.py (undo created resources)
- Track ownership in context

GATE:
- pytest tests/orchestrator/test_verifier.py tests/orchestrator/test_rollback.py -q

EVIDENCE REQUIRED:
- Files changed
- Test output
```

---

### Step 5 — Orchestrator + CLI

```text
DO:
- Implement __init__.py (DeploymentOrchestrator class)
- Refactor cli.py apply() to use DeploymentOrchestrator
- Preserve all existing flags and backward compatibility
- Add --dry-run flag

GATE:
- fabrik apply --dry-run tests/fixtures/test-api.yaml

EVIDENCE REQUIRED:
- Files changed
- Dry-run output
```

---

### Step 6 — Integration test

```text
DO:
- Create test fixture: tests/fixtures/test-api.yaml
- Run full deploy against test spec (mocked Coolify)
- Verify rollback on simulated failure

GATE:
- CANONICAL GATE passes
- fabrik apply --dry-run tests/fixtures/test-api.yaml exits 0

EVIDENCE REQUIRED:
- Full test output
- Dry-run output
```

---

## STOP CONDITIONS

```text
STOP IF:
- Coolify API behavior differs from expected
- Existing cli.py breaks on changes
- Missing credentials for live test

ON STOP:
- Report exact blocker
- Propose at most 2 resolution options
```

---

## REPORTING FORMAT

After **every step**, output:

```text
STEP <N> STATUS: PASS / FAIL

Changed files:
- <path>

Gate output:
<pasted>

Next:
- Proceed to Step <N+1> OR STOP
```
