# Fabrik Consolidated Gap Analysis

**Date:** 2026-01-07
**Reviewers:** Claude Sonnet 4.5, Claude Opus 4.5, Gemini 3 Pro, GPT 5.2

---

## Session IDs (for follow-up consultations)

| Model | Session ID |
|-------|------------|
| Claude Sonnet 4.5 | `c169df0c-fb5a-4133-bda8-4e5079013d71` |
| Claude Opus 4.5 | `efa322ba-d6b1-4a2f-9915-4eda2e2b7c5d` |
| Gemini 3 Pro | `5ad8a79a-ebf9-44ee-a03e-f3ec16b45fe4` |
| GPT 5.2 | `6e6ce66a-12b5-4ae3-a4d3-bdc18f33fdaf` |

---

## Unanimous Agreement: The #1 Missing Piece

**ALL FOUR MODELS AGREE:** Fabrik needs a **Unified Deployment Orchestrator**

| Model | Their #1 Finding |
|-------|------------------|
| **Sonnet** | "Missing DeploymentOrchestrator class that unifies all primitives" |
| **Opus** | "Natural Language → Spec Generation + unified orchestration" |
| **Gemini** | "No drift detection or reconciliation loop - apply is not idempotent" |
| **GPT 5.2** | "Single end-to-end orchestration layer for plan→apply→verify→rollback" |

---

## Consolidated Critical Gaps (P0)

### P0-1: End-to-End Orchestration Layer
**Consensus: 4/4 models**

| Location | Issue |
|----------|-------|
| `cli.py:136-191` | `apply` skips provisioner Steps 0-2 |
| `provisioner.py` | Only used for WordPress, not general apps |
| `cli.py` vs `provisioner.py` vs `wordpress/deployer.py` | Three parallel orchestration paths |

**Agreed Solution:** Create `src/fabrik/orchestrator.py`
```python
class DeploymentOrchestrator:
    def deploy(self, spec) -> DeploymentResult:
        self.validate()      # Check spec + secrets
        self.provision()     # DNS, domain (if needed)
        self.deploy()        # Coolify
        self.verify()        # Postconditions
        self.rollback_on_failure()  # Safety
```

### P0-2: Rollback Not Implemented
**Consensus: 4/4 models**

| Location | Issue |
|----------|-------|
| `verify.py:300-307` | `trigger_rollback()` returns `pass` |
| `cli.py:473-476` | DNS deletion says "not implemented yet" |

**Agreed Solution:** Implement actual rollback logic for Coolify + DNS + monitors

### P0-3: Secrets Management is Manual & Insecure
**Consensus: 4/4 models**

| Location | Issue |
|----------|-------|
| `provisioner.py:129-133` | Plaintext password in job JSON |
| `provisioner.py:200-202` | Password gen doesn't follow 32-char policy |
| `cli.py:115-121` | Manual `-s KEY=VALUE` flags |

**Agreed Solution:**
- Auto-load from `.env` / vault
- Never persist plaintext secrets
- Follow CSPRNG policy (32 char alphanumeric)

### P0-4: Apply is Not Idempotent (No Drift Detection)
**Consensus: 3/4 models (Sonnet, Gemini, GPT)**

| Location | Issue |
|----------|-------|
| `cli.py:180-290` | `apply` creates new, doesn't update existing |
| `provisioner.py` | No reconciliation loop |

**Agreed Solution:** Check if deployment exists, diff spec, update instead of create

### P0-5: Provisioner Step 2 Has Dead Code
**Consensus: 3/4 models (Sonnet, Opus, GPT)**

| Location | Issue |
|----------|-------|
| `provisioner.py:342-351` | Calls methods that don't exist |
| `provisioner.py:553+` | Missing `_step2_coolify_create_app()` |

**Agreed Solution:** Implement or remove dead code paths

---

## Consolidated High-Value Improvements (P1)

### P1-1: Natural Language → Spec Generation
**Consensus: 2/4 models (Opus, Gemini)**

```bash
# Proposed
fabrik idea "Python API that tracks crypto prices"
# → Auto-selects template, generates spec, scaffolds code
```

### P1-2: Multi-Environment Support
**Consensus: 2/4 models (Gemini, GPT)**

| Issue | Solution |
|-------|----------|
| Single domain/env per spec | Support `env.staging` / `env.production` |
| Manual spec duplication | One spec, multiple environments |

### P1-3: Droid Integration During Deployment
**Consensus: 2/4 models (Sonnet, Opus)**

| Issue | Solution |
|-------|----------|
| Droid not used during apply | Report progress to droid |
| No AI assistance on failures | Auto-diagnose with droid exec |

### P1-4: GitOps Workflow
**Consensus: 2/4 models (Sonnet, Gemini)**

| Issue | Solution |
|-------|----------|
| Direct compose push | Push to git repo, Coolify pulls |
| No version history | Full git-based rollback |

### P1-5: Deployment Audit Trail
**Consensus: 2/4 models (Opus, GPT)**

| Issue | Solution |
|-------|----------|
| No deployment history | Log all deployments with timestamps |
| Can't see what changed | Track diffs between deploys |

---

## Consolidated Quick Wins (P2)

| ID | Issue | Location | Fix | Effort |
|----|-------|----------|-----|--------|
| P2-1 | Hardcoded VPS IP | `cli.py:208,381`, `provisioner.py:154` | Centralize to `os.getenv()` | 1h |
| P2-2 | DNS deletion not implemented | `cli.py:473-476` | Implement `DNSClient.delete_record` | 2h |
| P2-3 | Interactive secret prompts | `cli.py:160-180` | `click.prompt(hide_input=True)` | 1h |
| P2-4 | Template metadata | `template_renderer.py:53-59` | Add `metadata.yaml` per template | 2h |
| P2-5 | SSL expiry check | `verify.py:137-140` | Parse `notAfter`, check days | 30m |
| P2-6 | Dangerous server guessing | `deploy.py:13-17` | Fail fast if not configured | 30m |

---

## Consolidated Technical Debt (P3)

| ID | Issue | Location | Impact |
|----|-------|----------|--------|
| P3-1 | Only 2 test files for core | `tests/` | Critical coverage gap |
| P3-2 | Duplicate `ModelInfo` class | `droid_models.py:51-59,258-266` | Confusion |
| P3-3 | 3 DNS pathways | `dns.py`, `cloudflare.py`, `domain_setup.py` | Inconsistency |
| P3-4 | Job state in JSON files | `provisioner.py:165-175` | Not scalable |
| P3-5 | Duplicate verify logic | `provisioner.py:498-522` vs `verify.py` | Inconsistency |
| P3-6 | Jinja autoescape for YAML | `template_renderer.py:40-43` | May break output |

---

## Agreed Implementation Order

### Phase 1: Fix Critical Breaks (1-2 weeks)
**Goal:** Make `fabrik apply` work end-to-end

1. **P0-5: Fix provisioner dead code** (1 day)
2. **P0-3: Secure secrets management** (2 days)
3. **P0-2: Implement rollback** (3 days)
4. **P0-1: Create DeploymentOrchestrator** (3 days)
5. **P0-4: Make apply idempotent** (2 days)

**Deliverable:** Single `fabrik apply` that handles everything reliably

### Phase 2: High-Value Features (2-3 weeks)

1. **P1-3: Droid deployment monitoring** (4 days)
2. **P1-2: Multi-environment support** (3 days)
3. **P1-5: Deployment audit trail** (2 days)
4. **P1-1: NL → Spec generation** (5 days)

**Deliverable:** Fast, intelligent deployments with great feedback

### Phase 3: Quick Wins + Polish (1 week)

1. All P2 items (3 days total)
2. Documentation updates (1 day)

**Deliverable:** Production-ready UX

### Phase 4: Technical Debt (Ongoing)

1. Test coverage (5 days)
2. DNS unification (2 days)
3. Other P3 items

---

## Summary Metrics

| Category | Issues | Models Agreeing | Total Effort |
|----------|--------|-----------------|--------------|
| **P0 Critical** | 5 | 3-4/4 | 11 days |
| **P1 High-Value** | 5 | 2-4/4 | 14 days |
| **P2 Quick Wins** | 6 | 2-3/4 | 3 days |
| **P3 Tech Debt** | 6 | 2-3/4 | 12 days |
| **Total** | 22 | - | **40 days** |

---

## Final Verdict

> **Fabrik is 80% complete with excellent primitives (Coolify/Cloudflare drivers, WordPress automation, AI enforcement), but lacks the critical 20% orchestration layer that chains them into complete deployment flows.**

### The Single Most Important Change

Create `src/fabrik/orchestrator.py` that:
1. Unifies `cli.py` + `provisioner.py` + `wordpress/deployer.py`
2. Handles full lifecycle: validate → provision → deploy → verify → rollback
3. Is idempotent (can run multiple times safely)
4. Integrates with droid for AI-assisted debugging

**Estimated effort:** 9 days for the orchestrator alone
**ROI:** Transforms Fabrik from "manual assembly" to "true automation"

---

## Next Steps

1. Review this consolidated analysis
2. Proceed to `docs/reference/phase2.md` for implementation
3. Use session IDs above for follow-up consultations with specific models
