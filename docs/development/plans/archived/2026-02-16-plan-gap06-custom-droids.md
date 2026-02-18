# 2026-02-16-plan-gap06-custom-droids

**Status:** NOT_STARTED
**Created:** 2026-02-16
**Priority:** P1 (High)
**Estimated Effort:** 3-4 hours
**Source:** Research document "Optimizing Workflows Across AI Coding Platforms"

---

## EXECUTION MODE HEADER (mandatory)

```text
STAGE: 3 — Execution
MODE: Mode 3 — Build (Cascade implements)
SPEC STATUS: FROZEN (this plan is read-only during execution)
SCOPE: GAP-06 Custom Droids only
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
Expand Factory custom droids with specialized roles

GOAL:
Create role-specific droids (planner, security-auditor, test-generator, documentation-writer) that carry system prompts, model preferences, and tooling policies.

DONE WHEN (all true):
- [ ] 4 new droids created in ~/.factory/droids/
- [ ] Each droid has: identity, capabilities, triggers, model, tools
- [ ] Droids documented in docs/reference/custom-droids.md
- [ ] Gate command passes: ls ~/.factory/droids/*.md | wc -l >= 7

OUT OF SCOPE:
- Modifying existing 3 droids
- Factory CLI modifications
- Droid testing framework
```

---

## GLOBAL CONSTRAINTS

```text
CONSTRAINTS:
- Location: /home/ozgur/.factory/droids/*.md (use ABSOLUTE paths, not ~)
- Format: YAML frontmatter + markdown body
- Models: DYNAMIC resolution from config/models.yaml scenarios section
  - Use: python3 scripts/droid_models.py recommend <scenario>
  - Do NOT hardcode model names (they change frequently)
- Tools: Reference existing Factory tools
- No duplicate functionality with existing droids

SESSION MANAGEMENT:
- Start: droid exec -m swe-1-5 "Start GAP-06" (captures session_id)
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

| Component | Location | Purpose |
|-----------|----------|---------|
| code-reviewer.md | ~/.factory/droids/ | Code quality reviews |
| worker.md | ~/.factory/droids/ | Generic task worker |
| service-migrator.md | ~/.factory/droids/ | Migration helper |
| Factory skills | ~/.factory/skills/ | 12 skills available |
| Model config | config/models.yaml | Model selection |

**Key insight:** New droids should have distinct purposes from existing 3.

---

## CANONICAL GATE

```text
CANONICAL GATE:
ls ~/.factory/droids/*.md | wc -l && cat ~/.factory/droids/planner.md | head -20
```

---

## EXECUTION STEPS

### Step 1 — Create Planner Droid

```text
DO:
- Create ~/.factory/droids/planner.md
- Identity: Spec-first planning specialist
- Capabilities:
  - Break features into phases
  - Create execution plans
  - Define gates and checkpoints
  - Estimate effort
- Model: $(python3 scripts/droid_models.py recommend spec) -- dynamic, deep reasoning
- Reasoning: high
- Triggers: "plan", "spec", "design", "architecture"
- Tools: read-only (no file edits)

NOTE: In droid .md file, use model_preference: "spec" to let Factory resolve dynamically

GATE:
- test $(cat /home/ozgur/.factory/droids/planner.md | grep -c "identity\|capabilities\|triggers") -ge 3

EVIDENCE REQUIRED:
- planner.md content
- Trigger patterns

PRE-FLIGHT GATES:
- Validate YAML frontmatter: head -20 ~/.factory/droids/planner.md

MODE 4 VERIFICATION (Verifier):
- droid exec -m gpt-5.3-codex --session-id <verify_session> "Audit planner droid: Complete? Triggers correct? List issues as JSON."
- If issues → fix → re-verify (MAX 2 iterations)
```

---

### Step 2 — Create Security Auditor Droid

```text
DO:
- Create ~/.factory/droids/security-auditor.md
- Identity: Security-focused code reviewer
- Capabilities:
  - OWASP vulnerability detection
  - Secret scanning
  - Dependency audit
  - Input validation review
  - Authentication/authorization review
- Model: $(python3 scripts/droid_models.py recommend code_review) -- dynamic, thorough
- Triggers: "security", "audit", "vulnerability", "pentest"
- Tools: read-only, can run bandit/semgrep

NOTE: In droid .md file, use model_preference: "code_review" for dynamic resolution

GATE:
- test $(cat /home/ozgur/.factory/droids/security-auditor.md | grep -c "OWASP\|secret\|vulnerability") -ge 2

EVIDENCE REQUIRED:
- security-auditor.md content
- Security focus areas

PRE-FLIGHT GATES:
- Validate YAML frontmatter: head -20 ~/.factory/droids/security-auditor.md

MODE 4 VERIFICATION (Verifier):
- droid exec -m gpt-5.3-codex --session-id <verify_session> "Audit security-auditor droid: OWASP coverage? Safe read-only? List issues."
- If issues → fix → re-verify (MAX 2 iterations)
```

---

### Step 3 — Create Test Generator Droid

```text
DO:
- Create ~/.factory/droids/test-generator.md
- Identity: Test creation specialist
- Capabilities:
  - Unit test generation
  - Integration test design
  - Edge case identification
  - Test coverage analysis
  - Property-based test suggestions
- Model: $(python3 scripts/droid_models.py recommend code) -- dynamic, balanced
- Triggers: "test", "coverage", "unittest", "pytest"
- Tools: can edit test files only (tests/*)

NOTE: In droid .md file, use model_preference: "code" for dynamic resolution

GATE:
- test $(cat /home/ozgur/.factory/droids/test-generator.md | grep -c "test\|coverage\|edge") -ge 3

EVIDENCE REQUIRED:
- test-generator.md content
- Tool restrictions

CODE REVIEW:
- droid exec -m gpt-5.3-codex "Review test-generator droid"
- droid exec -m gemini-3-pro-preview "Review test-generator capabilities"
```

---

### Step 4 — Create Documentation Writer Droid

```text
DO:
- Create ~/.factory/droids/documentation-writer.md
- Identity: Documentation specialist
- Capabilities:
  - API documentation
  - README generation
  - Code comments
  - Changelog updates
  - Diagram creation (mermaid)
- Model: $(python3 scripts/droid_models.py recommend quick) -- dynamic, fast/cheap
- Triggers: "document", "readme", "changelog", "api docs"
- Tools: can edit docs/* and *.md files only

NOTE: In droid .md file, use model_preference: "quick" for dynamic resolution

GATE:
- test $(cat /home/ozgur/.factory/droids/documentation-writer.md | grep -c "README\|changelog\|API") -ge 2

EVIDENCE REQUIRED:
- documentation-writer.md content
- File restrictions

CODE REVIEW:
- droid exec -m gpt-5.3-codex "Review documentation-writer droid"
- droid exec -m gemini-3-pro-preview "Review documentation-writer scope"
```

---

### Step 5 — Create Reference Documentation

```text
DO:
- Create docs/reference/custom-droids.md
- Document all 7 droids (3 existing + 4 new)
- Include:
  - Droid purpose
  - When to use
  - Model and reasoning settings
  - Tool permissions
  - Example invocations
- Add cross-references to Factory docs

GATE:
- test $(grep -c "##" docs/reference/custom-droids.md) -ge 7

EVIDENCE REQUIRED:
- custom-droids.md content
- All droids documented

CODE REVIEW:
- droid exec -m gpt-5.3-codex "Review custom-droids.md documentation"
- droid exec -m gemini-3-pro-preview "Review documentation clarity"
```

---

### Step 6 — Update AGENTS.md and Factory Integration

```text
DO:
- Add custom droids section to AGENTS.md
- Update ~/.factory/settings.json if needed
- Verify droids are recognized by Factory CLI
- Update CHANGELOG.md

GATE:
- test $(grep -c "droid" AGENTS.md) -ge 3
- test $(ls /home/ozgur/.factory/droids/*.md | wc -l) -ge 7

EVIDENCE REQUIRED:
- AGENTS.md diff
- Droid count verification
- CHANGELOG entry

CODE REVIEW:
- droid exec -m gpt-5.3-codex "Review AGENTS.md droid integration"
- droid exec -m gemini-3-pro-preview "Review overall droid ecosystem"
```

---

### Step 7 — Final Verification

```text
DO:
- Test each new droid with simple prompt
- Verify model selection works
- Verify tool restrictions work
- Document any issues

GATE:
- All 4 new droids respond appropriately to triggers

EVIDENCE REQUIRED:
- Test invocation outputs
- Any issues documented

CODE REVIEW:
- droid exec -m gpt-5.3-codex "Final review of droid ecosystem"
- droid exec -m gemini-3-pro-preview "Final review of droid ecosystem"
```

---

## STOP CONDITIONS

```text
STOP IF:
- Factory CLI doesn't recognize new droids
- Model names in config/models.yaml don't match
- Droid format incompatible with Factory

ON STOP:
- Report exact blocker
- Check Factory documentation
- Propose at most 2 resolution options
```

---

## EXPECTED BENEFITS

| Benefit | Metric |
|---------|--------|
| Role specialization | Right droid for right task |
| Cost optimization | Cheaper models for simpler tasks |
| Quality improvement | Specialized prompts = better output |
| Tool safety | Restricted permissions per role |

---

## DROID ECOSYSTEM (Dynamic Model Resolution)

| Droid | Role | Model Preference | Tools |
|-------|------|------------------|-------|
| code-reviewer | Review quality | code_review | read-only |
| worker | Generic tasks | default | full |
| service-migrator | Migrations | code | limited |
| **planner** | Spec-first planning | spec (high reasoning) | read-only |
| **security-auditor** | Security review | code_review | read + security tools |
| **test-generator** | Test creation | code | tests/* only |
| **documentation-writer** | Docs | quick (fast/cheap) | docs/* + *.md |

**Model resolution:** `python3 scripts/droid_models.py recommend <preference>`

This ensures droids always use the current best model as config/models.yaml is updated.

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
