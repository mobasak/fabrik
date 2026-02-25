# Implementation Plan: [Feature Name]

> Created with `droid exec --use-spec`

## Overview

[Brief description of what we're building/migrating and why]

**Scope:** [Number of files affected, components involved]
**Timeline:** [Estimated total duration]
**Risk Level:** [Low/Medium/High]

---

## Phases

### Phase 1: [Name] (Days 1-2)

**Goal:** [What this phase accomplishes]

- [ ] Task 1
- [ ] Task 2
- [ ] Task 3

**Files affected:**
- `path/to/file1.ts`
- `path/to/file2.ts`

**Validation:**
```bash
# How to verify this phase works
npm run test:auth
curl http://localhost:3000/health
```

**Rollback:**
```bash
git revert HEAD~N  # or specific commit
```

---

### Phase 2: [Name] (Days 3-4)

**Goal:** [What this phase accomplishes]

**Dependencies:** Phase 1 complete

- [ ] Task 1
- [ ] Task 2

**Files affected:**
- `path/to/file3.ts`

**Validation:**
```bash
# Verification commands
```

**Rollback:**
```bash
# Rollback commands
```

---

### Phase 3: [Name] (Days 5-6)

**Goal:** [What this phase accomplishes]

**Dependencies:** Phase 2 complete

- [ ] Task 1
- [ ] Task 2

**Validation:**
```bash
# Verification commands
```

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| [Risk 1] | Low/Med/High | Low/Med/High | [How to prevent/handle] |
| [Risk 2] | Low/Med/High | Low/Med/High | [How to prevent/handle] |

---

## Rollback Plan

**Full rollback procedure:**
```bash
# 1. Disable feature flag (if applicable)
export FEATURE_FLAG=false

# 2. Revert to last stable
git checkout main
git revert --no-commit HEAD~N..HEAD
git commit -m "Rollback: [feature name]"

# 3. Deploy rollback
# [deployment commands]
```

**Point of no return:** [Describe when rollback becomes difficult/impossible]

---

## Feature Flags

```bash
# Environment variable for gradual rollout
export NEW_FEATURE_ENABLED=true
export NEW_FEATURE_ROLLOUT_PERCENT=10
```

---

## Progress Log

| Date | Phase | Status | Notes |
|------|-------|--------|-------|
| YYYY-MM-DD | Phase 1 | ⏳ In Progress | Started implementation |
| YYYY-MM-DD | Phase 1 | ✅ Complete | All tests passing |
| YYYY-MM-DD | Phase 2 | ⏳ In Progress | |

---

## Commands Reference

```bash
# Create this plan
droid exec --use-spec "Create implementation plan for [feature]"

# Implement a phase
droid exec --auto medium "Implement Phase N per IMPLEMENTATION_PLAN.md"

# Commit phase
droid exec --auto medium "Commit Phase N changes with detailed message"

# Create PR
droid exec --auto medium "Create PR for Phase N on branch feature-phase-N"

# Test phase
droid exec --auto medium "Run tests for Phase N"
```
