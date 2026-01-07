# Project CONDUCTOR - Implementation Plan

**Version:** Draft 1.0 | **Date:** 2026-01-07 | **Status:** Awaiting consensus

---

## Goal

Create `src/fabrik/orchestrator/` module that unifies deployment lifecycle.

---

## Architecture

```
DeploymentOrchestrator
├── context.py      # DeploymentContext (shared state)
├── states.py       # DeploymentState enum
├── validator.py    # SpecValidator
├── secrets.py      # SecretsManager (auto-load, CSPRNG)
├── provisioner.py  # ResourceProvisioner (DNS, CF)
├── deployer.py     # ServiceDeployer (Coolify, idempotent)
├── verifier.py     # PostconditionVerifier
├── rollback.py     # RollbackManager
└── __init__.py     # Main orchestrator class
```

---

## Implementation Tasks

### Phase 1A: Foundation (Days 1-2)

| Task | File | Hours | Deliverable |
|------|------|-------|-------------|
| 1.1 | `context.py` | 4h | DeploymentContext dataclass |
| 1.2 | `states.py` | 2h | DeploymentState enum |
| 1.3 | `__init__.py` | 6h | Base DeploymentOrchestrator |

### Phase 1B: Validation (Days 2-3)

| Task | File | Hours | Deliverable |
|------|------|-------|-------------|
| 2.1 | `validator.py` | 4h | SpecValidator |
| 2.2 | `secrets.py` | 4h | SecretsManager with CSPRNG |

### Phase 1C: Deploy & Verify (Days 3-5)

| Task | File | Hours | Deliverable |
|------|------|-------|-------------|
| 3.1 | `provisioner.py` | 6h | DNS/CF provisioning |
| 3.2 | `deployer.py` | 8h | Coolify deploy (idempotent) |
| 3.3 | `verifier.py` | 4h | HTTP/Health/SSL checks |

### Phase 1D: Rollback & CLI (Days 5-7)

| Task | File | Hours | Deliverable |
|------|------|-------|-------------|
| 4.1 | `rollback.py` | 6h | RollbackManager |
| 4.2 | `cli.py` refactor | 4h | Use orchestrator |
| 4.3 | Tests | 4h | Core test coverage |

---

## Key Design Decisions (Need Consensus)

### Q1: State Persistence
- **Option A:** JSON files (current approach)
- **Option B:** SQLite database
- **Option C:** In-memory only (stateless)

### Q2: Rollback Scope
- **Option A:** Full rollback (Coolify + DNS + monitors)
- **Option B:** Coolify only (DNS persists)
- **Option C:** Configurable per-resource

### Q3: Idempotency Strategy
- **Option A:** Check by name, update if exists
- **Option B:** Check by spec hash, skip if unchanged
- **Option C:** Always recreate (destroy + create)

### Q4: Secrets Source Priority
- **Option A:** .env → env vars → generate
- **Option B:** env vars → .env → generate
- **Option C:** Vault integration required

### Q5: Error Recovery
- **Option A:** Auto-rollback on any failure
- **Option B:** Prompt user for rollback decision
- **Option C:** Rollback only on verification failure

---

## Success Criteria

1. `fabrik apply spec.yaml` works end-to-end without manual steps
2. Failed deployments automatically roll back
3. Re-running apply updates existing deployment (idempotent)
4. Secrets auto-loaded or auto-generated
5. All resources tracked for cleanup

---

## Questions for Model Review

1. Is this architecture correct?
2. Which options for Q1-Q5?
3. Missing components?
4. Risk areas?
5. Suggested test strategy?
