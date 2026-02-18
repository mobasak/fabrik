# 2026-02-16-plan-gap02-windsurf-workflows

**Status:** NOT_STARTED
**Created:** 2026-02-16
**Priority:** P1 (High)
**Estimated Effort:** 2-3 hours
**Source:** Research document "Optimizing Workflows Across AI Coding Platforms"

---

## EXECUTION MODE HEADER (mandatory)

```text
STAGE: 3 — Execution
MODE: Mode 3 — Build (Cascade implements)
SPEC STATUS: FROZEN (this plan is read-only during execution)
SCOPE: GAP-02 Windsurf Workflows only
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
Create Windsurf Workflows for common Fabrik operations

GOAL:
Enable one-command execution of complex multi-step tasks via /slash-commands in Windsurf Cascade.

DONE WHEN (all true):
- [ ] .windsurf/workflows/ directory exists
- [ ] At least 5 core workflows created
- [ ] Workflows follow Windsurf format (YAML frontmatter + markdown)
- [ ] Workflows reference existing skills and scripts
- [ ] Gate command passes: ls -la .windsurf/workflows/*.md | wc -l >= 5

OUT OF SCOPE:
- Windsurf IDE configuration changes
- New skills creation (use existing)
- Modifying Factory CLI settings
```

---

## GLOBAL CONSTRAINTS

```text
CONSTRAINTS:
- Format: YAML frontmatter + markdown steps
- Location: .windsurf/workflows/*.md
- Naming: kebab-case (e.g., deploy-service.md)
- Reference existing: Factory skills, enforcement scripts, droid-review.sh
- No duplicate logic (call existing tools)

SESSION MANAGEMENT:
- Start: droid exec -m swe-1-5 "Start GAP-02" (captures session_id)
- Continue: droid exec --session-id <id> "Next step..."
- WARNING: Changing models mid-session loses context
- Verification uses SEPARATE session (Verifier independence)

MODEL ASSIGNMENTS (from config/models.yaml):
- Execution: swe-1-5 or gpt-5.1-codex (Stage 3 - Build)
- Verification: gpt-5.3-codex (Stage 4 - Verify)
- Documentation: claude-haiku-4-5 (Stage 5 - Ship)
```

---

## EXISTING INFRASTRUCTURE (avoid duplication)

| Component | Location | Reuse Strategy |
|-----------|----------|----------------|
| Factory Skills | `~/.factory/skills/` | Reference in workflows |
| Enforcement | `scripts/enforcement/` | Call validate_conventions |
| Code Review | `scripts/droid-review.sh` | Include review steps |
| Scaffold | `fabrik.scaffold` | Reference fabrik-scaffold skill |
| Docker | `templates/scaffold/` | Reference fabrik-docker skill |

---

## CANONICAL GATE

```text
CANONICAL GATE:
ls .windsurf/workflows/*.md && cat .windsurf/workflows/new-service.md | head -20
```

---

## EXECUTION STEPS

### Step 1 — Create Workflows Directory

```text
DO:
- Create .windsurf/workflows/ directory
- Create README.md explaining workflow format and usage

GATE:
- ls -la .windsurf/workflows/README.md

EVIDENCE REQUIRED:
- Directory listing
- README.md content

SELF-REVIEW (Builder):
- Check: README explains workflow format
- Check: Usage examples provided

PRE-FLIGHT GATES:
- Validate YAML frontmatter syntax

MODE 4 VERIFICATION (Verifier):
- droid exec -m gpt-5.3-codex --session-id <verify_session> "Audit workflows README: Clear? Complete? Follows Fabrik standards?"
- If issues → fix → re-verify (MAX 2 iterations)
```

---

### Step 2 — Create /new-service Workflow

```text
DO:
- Create new-service.md workflow
- Steps: scaffold → docker setup → compose → health endpoint → watchdog → deploy check
- Reference fabrik-scaffold, fabrik-docker, fabrik-health-endpoint skills
- Include dual code review after implementation

Content structure:
---
description: Create a new Fabrik service with full Docker deployment setup
---

# New Service Workflow

## Prerequisites
- Project name decided
- Port allocated in PORTS.md

## Steps
1. Scaffold project structure
2. Create Dockerfile (python:3.12-slim-bookworm)
3. Create compose.yaml with healthcheck
4. Implement /health endpoint
5. Create watchdog script
6. Run preflight check
7. Code review

GATE:
- cat .windsurf/workflows/new-service.md | grep -c "##" >= 5

EVIDENCE REQUIRED:
- new-service.md content
- Step count verification

SELF-REVIEW (Builder):
- Check: References existing skills
- Check: All 7 steps present

PRE-FLIGHT GATES:
- Validate YAML frontmatter: cat .windsurf/workflows/new-service.md | head -10

MODE 4 VERIFICATION (Verifier):
- droid exec -m gpt-5.3-codex --session-id <verify_session> "Audit new-service.md: Complete? References correct skills?"
- If issues → fix → re-verify (MAX 2 iterations)
```

---

### Step 3 — Create /pre-deploy-check Workflow

```text
DO:
- Create pre-deploy-check.md workflow
- Steps: validate conventions → secrets scan → health test → Docker build → compose validate
- Reference existing enforcement scripts
- Include rollback instructions if checks fail

GATE:
- cat .windsurf/workflows/pre-deploy-check.md | grep -c "##" >= 4

EVIDENCE REQUIRED:
- pre-deploy-check.md content
- Validation step references

SELF-REVIEW (Builder):
- Check: References enforcement scripts
- Check: Rollback instructions present

MODE 4 VERIFICATION (Verifier):
- droid exec -m gpt-5.3-codex --session-id <verify_session> "Audit pre-deploy-check.md: All checks covered? Safe?"
- If issues → fix → re-verify (MAX 2 iterations)
```

---

### Step 4 — Create /hotfix Workflow

```text
DO:
- Create hotfix.md workflow
- Steps: branch from main → fix → test → review → merge → deploy
- Include dual code review requirement
- Add rollback procedure

GATE:
- cat .windsurf/workflows/hotfix.md | grep -c "##" >= 4

EVIDENCE REQUIRED:
- hotfix.md content
- Branch strategy documented

SELF-REVIEW (Builder):
- Check: Branch strategy clear
- Check: Rollback procedure documented

MODE 4 VERIFICATION (Verifier):
- droid exec -m gpt-5.3-codex --session-id <verify_session> "Audit hotfix.md: Safe? Rollback complete?"
- If issues → fix → re-verify (MAX 2 iterations)
```

---

### Step 5 — Create /code-review Workflow

```text
DO:
- Create code-review.md workflow
- Wraps droid-review.sh with additional context
- Steps: gather changed files → run dual review → address P0 → address P1 → final check
- Reference existing droid-review.sh script

GATE:
- cat .windsurf/workflows/code-review.md | grep "droid-review"

EVIDENCE REQUIRED:
- code-review.md content
- droid-review.sh reference

SELF-REVIEW (Builder):
- Check: References droid-review.sh
- Check: P0/P1 priority handling

MODE 4 VERIFICATION (Verifier):
- droid exec -m gpt-5.3-codex --session-id <verify_session> "Audit code-review.md: Correct droid-review.sh usage?"
- If issues → fix → re-verify (MAX 2 iterations)
```

---

### Step 6 — Create /add-feature Workflow

```text
DO:
- Create add-feature.md workflow
- Steps: spec → plan → implement → test → review → document → commit
- Reference spec-pipeline templates
- Include checkpoint after each major step

GATE:
- cat .windsurf/workflows/add-feature.md | grep -c "##" >= 5

EVIDENCE REQUIRED:
- add-feature.md content
- Spec-pipeline reference

SELF-REVIEW (Builder):
- Check: References spec-pipeline
- Check: Checkpoints after major steps

MODE 4 VERIFICATION (Verifier):
- droid exec -m gpt-5.3-codex --session-id <verify_session> "Audit add-feature.md: Spec-first pattern? Complete?"
- If issues → fix → re-verify (MAX 2 iterations)
```

---

### Step 7 — Update Documentation and AGENTS.md

```text
DO:
- Add workflows section to AGENTS.md
- Update docs/INDEX.md with workflows reference
- Update CHANGELOG.md

GATE:
- grep -c "workflows" AGENTS.md >= 1
- grep -c "workflows" docs/INDEX.md >= 1

EVIDENCE REQUIRED:
- AGENTS.md diff
- docs/INDEX.md diff
- CHANGELOG.md entry

SELF-REVIEW (Builder):
- Check: All docs updated
- Check: CHANGELOG entry present

MODE 4 VERIFICATION (Verifier - FINAL):
- droid exec -m gpt-5.3-codex --session-id <verify_session> "Final audit GAP-02: All gates pass? Docs updated? Ready to merge?"
- Must return: {"ready": true, "issues": []}
```

---

## STOP CONDITIONS

```text
STOP IF:
- Windsurf doesn't recognize .windsurf/workflows/ format
- Existing workflows discovered (check first!)
- Conflicts with Factory skills

ON STOP:
- Report exact blocker
- Propose at most 2 resolution options
```

---

## EXPECTED BENEFITS

| Benefit | Metric |
|---------|--------|
| Reduced task time | -50% time on multi-step operations |
| Consistency | Same process every time |
| Onboarding | New devs productive in hours |
| Reduced errors | No forgotten steps |

---

## WORKFLOWS TO CREATE

| Workflow | Slash Command | Purpose |
|----------|---------------|---------|
| new-service.md | /new-service | Full service scaffold |
| pre-deploy-check.md | /pre-deploy-check | Deployment validation |
| hotfix.md | /hotfix | Emergency fix flow |
| code-review.md | /code-review | Dual-model review |
| add-feature.md | /add-feature | Spec-first feature |

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

Mode 4 Verification (Verifier):
- Result: PASS / FAIL
- Issues: <none or list>
- Re-verify count: <N>

Next:
- Proceed to Step <N+1> OR STOP (if verify failed)
```

---

## SESSION MANAGEMENT

```text
SESSION RULES:
1. Start execution session: droid exec -m swe-1-5 "Begin GAP-02 Step 1"
2. Capture session_id from response
3. Continue with: droid exec --session-id <id> "Step 2..."
4. Verification uses SEPARATE session (Verifier independence)
5. If model change needed: Start new session, summarize context first
6. Document session_id in each step report
```
