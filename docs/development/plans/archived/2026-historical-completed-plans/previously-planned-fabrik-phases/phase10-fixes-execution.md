# Phase 10 Fixes — Code Review Remediation

**Status:** ✅ COMPLETE (historical implementation)
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
Orchestrator Code Review Fixes

GOAL:
Fix all critical and medium issues identified by GPT 5.1 and Gemini 3 reviews

DONE WHEN (all true):
- Rollback only deletes resources created in current run (not pre-existing)
- Invalid state transitions raise exceptions
- Domain validation blocks localhost/private IPs
- find_existing fails fast on Coolify errors
- deployed_url only set after successful verification
- All new tests pass
- Gate command passes: pytest tests/orchestrator/ -q

OUT OF SCOPE:
- DNS provisioning implementation
- SSL certificate check integration
- Secrets persistence to .env
- check_ssl() test coverage (deferred)
```

---

## GLOBAL CONSTRAINTS

```text
CONSTRAINTS:
- Language: Python 3.12
- No new deps
- Backward compatibility: existing --dry-run behavior unchanged
- Follow patterns in: src/fabrik/orchestrator/
```

---

## CANONICAL GATE

```text
CANONICAL GATE:
cd /opt/fabrik && source .venv/bin/activate && pytest tests/orchestrator/ -q
```

---

## EXECUTION STEPS

### Step 1 — Fix rollback safety (CRITICAL)

```text
DO:
- In deployer.py: Only add to created_resources on CREATE, not UPDATE
- Modify deploy() to check if existing before adding resource
- Add test: update path should NOT mark for rollback

GATE:
- pytest tests/orchestrator/test_deployer.py -q

EVIDENCE REQUIRED:
- Files changed: deployer.py, test_deployer.py
- Test output showing update doesn't add to created_resources
```

---

### Step 2 — Fix state machine enforcement (CRITICAL)

```text
DO:
- In __init__.py: _transition() raises exception on invalid transition
- Add InvalidStateTransition exception to exceptions.py
- Add test for invalid transition rejection

GATE:
- pytest tests/orchestrator/test_states.py tests/orchestrator/test_integration.py -q

EVIDENCE REQUIRED:
- Files changed: __init__.py, exceptions.py, test_states.py
- Test output
```

---

### Step 3 — Fix domain validation (CRITICAL - SSRF)

```text
DO:
- In validator.py: Add strict domain validation regex
- Block: localhost, 127.*, 10.*, 192.168.*, 172.16-31.*, ::1
- Require valid TLD (not just contains ".")
- Add tests for blocked domains

GATE:
- pytest tests/orchestrator/test_validator.py -q

EVIDENCE REQUIRED:
- Files changed: validator.py, test_validator.py
- Test output showing blocked domains rejected
```

---

### Step 4 — Fix find_existing error handling (MEDIUM)

```text
DO:
- In deployer.py: find_existing raises on Coolify API errors
- Only return None for "not found" case
- Add test for API error propagation

GATE:
- pytest tests/orchestrator/test_deployer.py -q

EVIDENCE REQUIRED:
- Files changed: deployer.py, test_deployer.py
- Test output
```

---

### Step 5 — Fix deployed_url timing (MEDIUM)

```text
DO:
- In verifier.py: Don't set ctx.deployed_url until after success
- Move deployed_url assignment after health check passes
- Add test: failed verification should not set deployed_url

GATE:
- pytest tests/orchestrator/test_verifier.py -q

EVIDENCE REQUIRED:
- Files changed: verifier.py, test_verifier.py
- Test output
```

---

### Step 6 — Final verification + docs

```text
DO:
- Run full test suite
- Update docs/INDEX.md with orchestrator entry
- Mark phase10.md as complete

GATE:
- CANONICAL GATE passes
- docs/INDEX.md contains orchestrator section

EVIDENCE REQUIRED:
- Full pytest output (66+ tests)
- Git diff showing doc updates
```

---

## STOP CONDITIONS

```text
STOP IF:
- Any test fails after fix attempt
- Backward compatibility broken (--dry-run stops working)
- Gate cannot be satisfied after 2 attempts

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
- <path>

Gate output:
<pasted output>

Next:
- Proceed to Step <N+1> OR STOP
```
