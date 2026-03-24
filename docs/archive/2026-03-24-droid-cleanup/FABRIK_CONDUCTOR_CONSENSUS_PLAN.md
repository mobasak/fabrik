# Project CONDUCTOR - Final Consensus Plan

**Version:** 1.0 Final
**Date:** 2026-01-07
**Status:** APPROVED BY 4-MODEL CONSENSUS

---

## Executive Summary

Transform Fabrik from a collection of primitives into a unified deployment automation platform by implementing the **DeploymentOrchestrator**.

**Reviewers & Sessions:**
| Model | Session ID | Review Status |
|-------|------------|---------------|
| Claude Sonnet 4.5 | `c169df0c` | ✅ Approved with amendments |
| Claude Opus 4.5 | `efa322ba` | ✅ Approved with amendments |
| Gemini 3 Pro | `5ad8a79a` | ✅ Approved with amendments |
| GPT 5.2 | `6e6ce66a` | ✅ Approved with amendments |

---

## Consensus Design Decisions

### Q1: State Persistence → **SQLite (4/4 consensus)**

| Model | Vote | Notes |
|-------|------|-------|
| Sonnet | SQLite | With JSON export for debugging |
| Opus | SQLite | With versioning and journal |
| Gemini | SQLite | Single-file, supports concurrency |
| GPT 5.2 | SQLite | Behind `StateStore` interface |

**Final Decision:** SQLite with `StateStore` abstraction
- Tables: `deployments`, `resources`, `events` (append-only)
- JSON export for debugging (with secret redaction)
- Migration system for schema evolution

### Q2: Rollback Scope → **Configurable (4/4 consensus)**

| Model | Vote | Notes |
|-------|------|-------|
| Sonnet | Configurable | Auto for Coolify, prompt for DNS |
| Opus | Configurable | Per-resource with defaults |
| Gemini | Configurable | User specifies in spec |
| GPT 5.2 | Configurable | "Rollback what we created in this run" |

**Final Decision:** Policy-based rollback with ownership tracking
```yaml
# In spec.yaml
rollback:
  coolify: auto      # auto | manual | never
  dns: manual        # Expensive resources default to manual
  monitors: auto
```

### Q3: Idempotency → **Hybrid (4/4 consensus)**

| Model | Vote | Notes |
|-------|------|-------|
| Sonnet | Spec hash | Skip if unchanged |
| Opus | Name check + update | Terraform pattern |
| Gemini | Name check | Standard pattern |
| GPT 5.2 | Hybrid | Name/UUID + spec hash |

**Final Decision:** Two-phase idempotency check
1. **Lookup:** Find existing deployment by name/UUID in local state
2. **Diff:** Compare spec hash; skip if unchanged, update if different

### Q4: Secrets Priority → **env vars → .env → generate (3/4 consensus)**

| Model | Vote | Notes |
|-------|------|-------|
| Sonnet | .env → env → generate | Local dev priority |
| Opus | .env → env → generate | Same |
| Gemini | env → .env → generate | CI/CD priority |
| GPT 5.2 | env → .env → generate | Standard injection |

**Final Decision:** Environment-first (CI/CD optimized)
```
1. Environment variables (CI/CD, production)
2. Project .env file (local dev)
3. Auto-generate (CSPRNG, 32 char alphanumeric)
```

**Mandatory:** Never persist secrets in state/logs. Use `SecretStr` from Pydantic.

### Q5: Error Recovery → **Auto-rollback with options (4/4 consensus)**

| Model | Vote | Notes |
|-------|------|-------|
| Sonnet | Hybrid | Auto for Coolify, prompt for DNS |
| Opus | Auto-rollback | Default to clean up |
| Gemini | Auto-rollback | Fail-safe default |
| GPT 5.2 | Retry + rollback | Retry transient, rollback on verify fail |

**Final Decision:** Smart error handling
1. **Transient errors:** Retry with exponential backoff (3 attempts)
2. **Verification failure:** Auto-rollback owned resources
3. **User option:** `--no-rollback` flag to disable

---

## Revised Architecture

### Module Structure (Consensus: +5 modules)

```
src/fabrik/orchestrator/
├── __init__.py          # DeploymentOrchestrator main class
├── context.py           # DeploymentContext (shared state)
├── states.py            # DeploymentState enum + transitions
├── exceptions.py        # Typed exceptions (NEW)
├── validator.py         # SpecValidator
├── secrets.py           # SecretsManager (CSPRNG, masking)
├── provisioner.py       # ResourceProvisioner (DNS, CF)
├── deployer.py          # ServiceDeployer (Coolify, idempotent)
├── verifier.py          # PostconditionVerifier
├── rollback.py          # RollbackManager (policy-based)
├── journal.py           # Append-only event log (NEW)
├── locks.py             # File/DB locking (NEW - all models agreed)
├── state_store.py       # SQLite abstraction (NEW)
└── notifier.py          # Event hooks/notifications (NEW)
```

### State Machine

```
                    ┌─────────────────┐
                    │     PENDING     │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
            ┌───────│   VALIDATING    │───────┐
            │       └────────┬────────┘       │
            │                │                │
            │       ┌────────▼────────┐       │
            │   ┌───│  PROVISIONING   │───┐   │
            │   │   └────────┬────────┘   │   │
            │   │            │            │   │
            │   │   ┌────────▼────────┐   │   │
            │   │   │    DEPLOYING    │   │   │
            │   │   └────────┬────────┘   │   │
            │   │            │            │   │
            │   │   ┌────────▼────────┐   │   │
            │   └───│    VERIFYING    │───┘   │
            │       └────────┬────────┘       │
            │                │                │
     ┌──────▼──────┐  ┌──────▼──────┐  ┌──────▼──────┐
     │   FAILED    │  │  COMPLETE   │  │ROLLING_BACK │
     └─────────────┘  └─────────────┘  └──────┬──────┘
                                              │
                                       ┌──────▼──────┐
                                       │ ROLLED_BACK │
                                       └─────────────┘
```

---

## Revised Timeline (Consensus: 10-12 days)

| Phase | Original | Revised | Reason |
|-------|----------|---------|--------|
| 0: Integration Audit | - | 1 day | Sonnet: avoid conflicts |
| 1A: Foundation | 1.5 days | 2 days | +locks, +exceptions |
| 1B: Validation | 1 day | 1.5 days | +ComposeLinter |
| 1C: Deploy & Verify | 2 days | 3 days | +retry, +idempotency |
| 1D: Rollback & CLI | 1.5 days | 2 days | +policy, +journal |
| 1E: Tests | 0.5 days | 2 days | All models: critical |
| **Total** | **7 days** | **11.5 days** | +65% |

---

## Implementation Phases

### Phase 0: Integration Audit (Day 0)
**Goal:** Understand existing code before touching it

| Task | Hours | Deliverable |
|------|-------|-------------|
| 0.1 Audit `provisioner.py` (685 lines) | 3h | Dependency map |
| 0.2 Map WordPress deployer | 2h | Integration points |
| 0.3 Design adapter interfaces | 2h | Interface specs |
| 0.4 Create test fixtures | 1h | Mock specs |

### Phase 1A: Foundation (Days 1-2)
**Goal:** Core state management

| Task | File | Hours | Description |
|------|------|-------|-------------|
| 1A.1 | `states.py` | 3h | State enum + valid transitions |
| 1A.2 | `exceptions.py` | 2h | `DeploymentError`, `ValidationError`, etc. |
| 1A.3 | `context.py` | 4h | `DeploymentContext` with resource tracking |
| 1A.4 | `state_store.py` | 4h | SQLite backend + migrations |
| 1A.5 | `locks.py` | 3h | File-based locking for concurrent safety |

**Acceptance Criteria:**
- [ ] State transitions logged to SQLite
- [ ] Concurrent deploys detected and blocked
- [ ] Resources tracked for rollback

### Phase 1B: Validation & Secrets (Days 2-3)
**Goal:** Validate before deploying

| Task | File | Hours | Description |
|------|------|-------|-------------|
| 1B.1 | `validator.py` | 5h | Spec + template + compose validation |
| 1B.2 | `secrets.py` | 5h | Priority chain + CSPRNG + `SecretStr` |

**Secrets Policy (32 char alphanumeric):**
```python
def generate_secret() -> str:
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(32))
```

### Phase 1C: Deploy & Verify (Days 3-6)
**Goal:** Reliable deployment with verification

| Task | File | Hours | Description |
|------|------|-------|-------------|
| 1C.1 | `provisioner.py` | 6h | DNS/Cloudflare via existing drivers |
| 1C.2 | `deployer.py` | 12h | Coolify idempotent (Opus: underestimated) |
| 1C.3 | `verifier.py` | 5h | HTTP/Health/SSL with retry |
| 1C.4 | `notifier.py` | 3h | Event hooks for droid/slack |

**Idempotency Logic (deployer.py):**
```python
def deploy(self, ctx: DeploymentContext) -> None:
    # 1. Check local state for existing UUID
    existing = self.state_store.get_deployment(ctx.spec.id)

    # 2. If exists, compare spec hash
    if existing and existing.spec_hash == ctx.spec_hash:
        logger.info("No changes detected, skipping deploy")
        return

    # 3. If exists but changed, update
    if existing:
        self._update_deployment(existing.coolify_uuid, ctx)
    else:
        self._create_deployment(ctx)
```

### Phase 1D: Rollback & CLI (Days 6-8)
**Goal:** Safe failure handling

| Task | File | Hours | Description |
|------|------|-------|-------------|
| 1D.1 | `rollback.py` | 8h | Policy-based, ownership-aware |
| 1D.2 | `journal.py` | 4h | Append-only event log |
| 1D.3 | `__init__.py` | 4h | Main orchestrator class |
| 1D.4 | CLI refactor | 4h | `fabrik apply` uses orchestrator |

**Rollback Safety Rule:**
> Only rollback resources created in THIS deployment run, with recorded ownership.

### Phase 1E: Tests (Days 8-10)
**Goal:** Production-ready confidence

| Test Type | Count | Hours | Coverage Target |
|-----------|-------|-------|-----------------|
| Unit tests | 40-50 | 8h | 80% |
| Integration | 10-15 | 6h | Key flows |
| E2E | 2-3 | 2h | Full lifecycle |

**Test Infrastructure:**
```yaml
# tests/docker-compose.test.yaml
services:
  coolify-mock:
    image: mockserver/mockserver
    ports: ["8000:1080"]
  postgres-test:
    image: postgres:16-alpine
    ports: ["5433:5432"]
```

---

## Risk Mitigation (All Models Agreed)

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Coolify API instability | High | High | Retry with exponential backoff |
| Secrets in logs | Medium | Critical | `SecretStr`, grep tests |
| Orphaned resources | Medium | Medium | Resource tagging + GC script |
| Concurrent deploys | Medium | High | File locking in `locks.py` |
| DNS propagation delays | High | Medium | Configurable timeouts, resume |
| Existing provisioner conflict | High | High | Adapter pattern, Phase 0 audit |

---

## Success Criteria

1. ✅ `fabrik apply spec.yaml` works end-to-end without manual steps
2. ✅ Failed deployments automatically roll back owned resources
3. ✅ Re-running apply updates existing deployment (idempotent)
4. ✅ Secrets auto-loaded from env/file or auto-generated (32 char)
5. ✅ All resources tracked in SQLite for cleanup
6. ✅ Concurrent deploys detected and blocked
7. ✅ 80% test coverage on orchestrator module

---

## Out of Scope (Phase 2+)

| Feature | Deferred To | Reason |
|---------|-------------|--------|
| Vault integration | Phase 2 | .env sufficient for MVP |
| Natural Language → Spec | Phase 3 | Major feature, separate project |
| Multi-environment (staging/prod) | Phase 2 | Single env covers 90% |
| WordPress content automation | Phase 2 | Orchestrator handles infra only |
| Web UI | Phase 3 | CLI-first approach |

---

## Next Steps

1. **User approval** of this consensus plan
2. Start **Phase 0: Integration Audit**
3. Create orchestrator module skeleton
4. Implement in order: states → context → store → locks → ...

---

## Appendix: Model-Specific Insights

### From Sonnet
- Add Phase 0 integration audit before coding
- Progress streaming for droid integration
- Template validation catches errors before Coolify

### From Opus
- Deployment journal is critical for debugging
- Uptime Kuma integration should be included
- Test coverage must be ≥80%

### From Gemini
- SQLite is non-negotiable for state
- Resource tagging for orphan detection
- `SecretStr` everywhere to prevent leaks

### From GPT 5.2
- `StateStore` abstraction allows future migration
- Retry transient errors before rollback
- WordPress stays separate (infra vs content)
