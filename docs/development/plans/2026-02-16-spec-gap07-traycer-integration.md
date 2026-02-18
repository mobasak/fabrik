# GAP-07 Traycer Integration — Spec-Level Implementation Plan

**Version:** 1.1.0  
**Revision Date:** 2026-02-17  
**Status:** SPEC (not implementation)  
**Compliance:** GAP-07 v1.0  
**Source:** `@/opt/fabrik/docs/development/plans/archived/2026-02-16-plan-gap07-traycer-integration.md`

---

## Implementation Readiness Checklist

> **Pre-implementation step:** Before starting, verify repo paths exist and run the canonical gate on a clean checkout. Check boxes as verified.

- [ ] **Spec-Level Implementation Plan (implementable specs) attached**
- [ ] Repo grounding paths verified (all referenced files/dirs either exist or are explicitly CREATE)
- [ ] Required Artifacts list complete (CREATE/MODIFY + exact paths)
- [ ] Deterministic Gate is **one exact command** (copy/paste) and passes on a clean checkout
- [ ] DONE WHEN criteria are measurable and mapped to artifacts + gate output
- [ ] Failure modes/rollback defined (even if minimal)

---

## Artifacts Table

| Path | Action | Purpose | Gate Coverage |
|------|--------|---------|---------------|
| `docs/reference/traycer-evaluation.md` | CREATE | Evaluation results | Canonical gate |
| `.tmp/traycer-baseline.json` | CREATE (runtime) | Baseline metrics | Comparison data |
| `.tmp/traycer-test.json` | CREATE (runtime) | Traycer metrics | Comparison data |
| `CHANGELOG.md` | MODIFY | Document GAP-07 | Manual verify |

---

## BLOCKER: Traycer CLI Command

> **BLOCKER:** Traycer CLI command not yet confirmed. Before implementation starts, must:
> 1. Confirm Traycer installation method (npm, pip, binary)
> 2. Get exact CLI invocation for version check
> 3. Document required environment variables (API key, etc.)
> 4. Update this spec with exact commands

**Fallback:** If Traycer CLI unavailable, use web interface and document manual verification steps.

---

## 1. Repo Grounding (Mandatory First Section)

### A. Structure Map (Top 3 Levels)

```
/opt/fabrik/
├── templates/
│   └── traycer/                # Traycer templates (EXISTS)
│       └── (template files)
├── docs/
│   └── reference/              # For evaluation doc
└── config/
    └── models.yaml             # Model configuration
```

### B. GAP-07 Integration Points

| Component | Status | Path | Action |
|-----------|--------|------|--------|
| `templates/traycer/` | **FOUND** | `templates/traycer/` | **VERIFY** — templates exist |
| `docs/reference/traycer-evaluation.md` | **NOT FOUND** | `docs/reference/` | **CREATE** required |
| Traycer CLI | **EXTERNAL** | N/A | **VERIFY** — available |

### C. Blockers

| Blocker | Fix Option 1 | Fix Option 2 |
|---------|--------------|--------------|
| Traycer not installed | Install via npm/pip | Evaluate without install |
| No Traycer account | Create free account | Defer to later GAP |

---

## 2. Required Artifacts (CREATE vs MODIFY)

| Path | Action | Justification | NOT Changed | Diff Size |
|------|--------|---------------|-------------|-----------|
| `docs/reference/traycer-evaluation.md` | **CREATE** | GAP-07 DONE WHEN: evaluation complete | — | **M** (~100 lines) |
| `templates/traycer/*.md` | **VERIFY/MODIFY** | Traycer compatibility | Core templates | **S** |
| `CHANGELOG.md` | **MODIFY** | Standard practice | Existing entries | **S** |

**Explicitly NOT created/modified:**
- `scripts/*` — No script changes for evaluation
- `src/*` — No source changes
- Pipeline integration — Future GAP if adopted

**SCOPE:** This is an **EVALUATION ONLY** GAP. Decision to adopt is the deliverable.

---

## 3. Interface & Contract Specification

### A. Evaluation Criteria

| Criterion | Weight | Pass Threshold |
|-----------|--------|----------------|
| **Spec anchoring** | 30% | Reduces rule-skipping by >50% |
| **Duplicate prevention** | 25% | Catches >80% of duplicate code |
| **Context preservation** | 20% | Multi-phase context maintained |
| **Integration effort** | 15% | <4 hours to integrate |
| **Cost** | 10% | <$50/month for current usage |

### B. Evaluation Document Schema

```markdown
# Traycer Integration Evaluation

**Date:** YYYY-MM-DD  
**Evaluator:** [name]  
**Version:** Traycer vX.Y.Z

## Executive Summary
[1-2 sentence recommendation]

## Decision
- [ ] **ADOPT** — Integrate into GAP-09 pipeline
- [ ] **DEFER** — Re-evaluate in 3 months
- [ ] **REJECT** — Does not meet requirements

## Evaluation Results

### 1. Spec Anchoring (30%)
**Score:** X/10
**Evidence:** [test results]

### 2. Duplicate Prevention (25%)
**Score:** X/10
**Evidence:** [test results]

### 3. Context Preservation (20%)
**Score:** X/10
**Evidence:** [test results]

### 4. Integration Effort (15%)
**Score:** X/10
**Evidence:** [hours estimate]

### 5. Cost (10%)
**Score:** X/10
**Evidence:** [pricing analysis]

## Test Cases Run

| Test | Expected | Actual | Pass/Fail |
|------|----------|--------|-----------|
| ... | ... | ... | ... |

## Recommendation
[Detailed recommendation with reasoning]

## Next Steps
[If ADOPT: integration steps]
[If DEFER: conditions for re-evaluation]
[If REJECT: alternatives considered]
```

### C. Test Cases (Minimum 5)

| # | Test Case | Purpose | Pass Criteria |
|---|-----------|---------|---------------|
| 1 | **Spec-to-code fidelity** | Does code match spec? | <5% deviation |
| 2 | **Duplicate detection** | Catches copy-paste code | Flags duplicates |
| 3 | **UI consistency** | Reuses existing components | No new modules |
| 4 | **Rule compliance** | Follows AGENTS.md | No violations |
| 5 | **Multi-phase context** | Remembers previous phases | Context preserved |

---

## 4. Golden Paths (2 Required)

### Golden Path 1: Run Traycer Evaluation

**Command:**
```bash
# Install Traycer (if needed)
npm install -g traycer

# Create test artifact
traycer artifact create "Add health endpoint to user-service" --spec

# Execute with verification
traycer execute --verify
```

**Expected output:**
```
Artifact created: artifact_abc123
Executing plan...
Verification: PASS
  - Spec compliance: 95%
  - No duplicates detected
  - Rules followed: 12/12
```

---

### Golden Path 2: Compare With/Without Traycer

**Test design:**
```
Task: "Add settings panel using existing components"

Run A (without Traycer):
- Use current GAP-09 pipeline
- Measure: duplicates, violations, review cycles

Run B (with Traycer):
- Use Traycer Plan + Verify
- Measure: same metrics

Compare: Which has fewer issues?
```

---

## 5. Failure Matrix (5 Cases)

| # | Failure Condition | Detection | Response | Rollback |
|---|-------------------|-----------|----------|----------|
| 1 | **Traycer unavailable** | CLI not found | Defer evaluation | None |
| 2 | **Account limits reached** | API error | Use local-only mode | None |
| 3 | **Spec format incompatible** | Parse error | Adapt template format | None |
| 4 | **No measurable improvement** | Metrics same | Document, REJECT | None |
| 5 | **Cost exceeds budget** | Pricing check | DEFER, re-evaluate | None |

---

## 6. Deterministic Gate Definition

**CANONICAL GATE:**

```bash
# Verify: decision checkbox + test cases section + score totals
grep -E "^\- \[(x|X)\] \*\*(ADOPT|DEFER|REJECT)\*\*" docs/reference/traycer-evaluation.md && \
grep -q "## Test Cases Run" docs/reference/traycer-evaluation.md && \
grep -q "Score:" docs/reference/traycer-evaluation.md && \
grep -c "| PASS |" docs/reference/traycer-evaluation.md | grep -q "[5-9]" && \
echo "PASS"
```

**Gate requirements:**
1. Decision checkbox checked (ADOPT, DEFER, or REJECT)
2. "Test Cases Run" section exists
3. "Score:" totals present
4. At least 5 test cases with PASS/FAIL documented

**Expected PASS output:**
```
- [x] **ADOPT** — Integrate into GAP-09 pipeline
PASS
```

OR

```
- [x] **DEFER** — Re-evaluate in 3 months
PASS
```

OR

```
- [x] **REJECT** — Does not meet requirements
PASS
```

---

## 7. Step-Reporting Format (COMPLIANCE REQUIREMENT)

After **every step**, builder/verifier MUST output:

```text
STEP <N> STATUS: PASS / FAIL
SESSION ID: <current_session_id>
MODE: Build → Verify

Changed files:
- <path>

Gate output:
<pasted output>

Self-Review (Builder):
- [ ] Test cases defined
- [ ] Metrics measured
- [ ] Evidence documented

Pre-Flight Gates:
- Traycer available: PASS/FAIL
- Account active: PASS/FAIL

Mode 4 Verification (Verifier):
- Result: PASS / FAIL
- Issues: <none or list>
- Re-verify count: <N>/2

Next:
- Proceed to Step <N+1> OR STOP (if verify failed)
```

---

## 8. Cross-System Impact

### Components Touched Indirectly

| Component | Impact |
|-----------|--------|
| GAP-09 Pipeline | May integrate Traycer if ADOPT |
| `templates/traycer/` | May need format updates |
| Workflow | May change planning phase |

### Invariants (Hard Rules)

- **MUST produce:** Decision document with evidence
- **MUST NOT:** Integrate before evaluation complete
- **MUST run:** Minimum 5 test cases
- **MUST compare:** With and without Traycer

### Decision Criteria

```
┌─────────────────────────────────────────┐
│ Decision Matrix                         │
├─────────────────────────────────────────┤
│ ADOPT if:                               │
│   - Total score >= 7/10                 │
│   - No criterion below 5/10             │
│   - Cost within budget                  │
│                                         │
│ DEFER if:                               │
│   - Score 5-7/10                        │
│   - OR missing test data                │
│   - OR pricing unclear                  │
│                                         │
│ REJECT if:                              │
│   - Score < 5/10                        │
│   - OR any criterion < 3/10             │
│   - OR cost prohibitive                 │
└─────────────────────────────────────────┘
```

---

## 9. Execution Steps (DO/GATE/EVIDENCE Format)

### Step 1 — Verify Traycer Availability

```text
DO:
- Check if Traycer CLI is available: traycer --version (or web interface)
- Check account/pricing tier
- Review Traycer documentation for integration requirements
- Document any prerequisites needed

GATE:
traycer --version || echo "CLI not available, use web interface"

EVIDENCE REQUIRED:
- Traycer version or web access confirmed
- Pricing tier documented
- Prerequisites identified

SELF-REVIEW (Builder):
- [ ] Can access Traycer (CLI or web)
- [ ] Understand pricing model
- [ ] Know integration requirements

IF BLOCKED:
- Document blockers in evaluation document
- Set decision to DEFER
- Skip to Step 5 (Create Evaluation Document)

MODE 4 VERIFICATION:
- Verifier confirms prerequisites assessment
- If issues → document and proceed to evaluation
```

---

### Step 2 — Define Test Cases

```text
DO:
- Create 5+ test cases from Section 3.C:
  1. Spec-to-code fidelity (does code match spec?)
  2. Duplicate detection (catches copy-paste code?)
  3. UI consistency (reuses existing components?)
  4. Rule compliance (follows AGENTS.md?)
  5. Multi-phase context (remembers previous phases?)
- Define quantitative pass criteria for each

GATE:
# Test cases documented in evaluation template
test -f /tmp/traycer-test-cases.md && wc -l /tmp/traycer-test-cases.md | grep -q "[5-9]"

EVIDENCE REQUIRED:
- 5+ test cases documented
- Pass criteria are quantitative (%, count, etc.)

SELF-REVIEW (Builder):
- [ ] Test cases are measurable
- [ ] Criteria are objective (not subjective)
- [ ] Same metrics can be used for with/without comparison

MODE 4 VERIFICATION:
- Verifier audits: Tests measurable? Criteria fair?
- If issues → fix → re-verify (MAX 2 iterations)
```

---

### Step 3 — Run Baseline (Without Traycer)

```text
DO:
- Select a representative test task: "Add settings panel using existing components"
- Execute using current GAP-09 pipeline (or manual droid exec)
- Measure:
  - Duplicate code introduced (lines, %)
  - Rule violations (AGENTS.md, pre-commit)
  - Review cycles needed
  - Time to completion
  - Token cost

GATE:
test -f /tmp/traycer-baseline.json && python -c "import json; json.load(open('/tmp/traycer-baseline.json'))"

EVIDENCE REQUIRED:
- Baseline metrics for all 5 test criteria
- Execution log or recording

SELF-REVIEW (Builder):
- [ ] Same task will be used for Traycer test
- [ ] Metrics are objective and reproducible
- [ ] No bias in measurement

MODE 4 VERIFICATION:
- Verifier audits: Metrics objective? Baseline fair?
- If issues → fix → re-verify (MAX 2 iterations)
```

---

### Step 4 — Run Traycer Test

```text
DO:
- Execute SAME task with Traycer Plan + Verify workflow
- Measure SAME metrics:
  - Duplicate code introduced
  - Rule violations
  - Review cycles needed
  - Time to completion
  - Token cost
- Document any qualitative observations

GATE:
test -f /tmp/traycer-test.json && python -c "import json; json.load(open('/tmp/traycer-test.json'))"

EVIDENCE REQUIRED:
- Traycer metrics for all 5 test criteria
- Execution log or recording
- Comparison table (baseline vs Traycer)

SELF-REVIEW (Builder):
- [ ] Same task used as baseline
- [ ] Same metrics measured
- [ ] Fair comparison (no handicaps)

MODE 4 VERIFICATION:
- Verifier audits: Comparison fair? Metrics accurate?
- If issues → fix → re-verify (MAX 2 iterations)
```

---

### Step 5 — Create Evaluation Document

```text
DO:
- Create docs/reference/traycer-evaluation.md
- Follow schema from Section 3.B:
  - Executive Summary (1-2 sentence recommendation)
  - Decision checkbox (ADOPT/DEFER/REJECT)
  - Evaluation Results (5 criteria with scores)
  - Test Cases Run (table with expected/actual/pass-fail)
  - Recommendation with reasoning
  - Next Steps
- Apply Decision Matrix from Section 8

GATE:
cat docs/reference/traycer-evaluation.md | grep -E "^\- \[(x|X| )\] \*\*(ADOPT|DEFER|REJECT)\*\*"

EVIDENCE REQUIRED:
- traycer-evaluation.md exists
- Decision checkbox marked
- All test results included

SELF-REVIEW (Builder):
- [ ] All 5 criteria scored
- [ ] Decision follows Decision Matrix rules
- [ ] Evidence supports decision

MODE 4 VERIFICATION:
- Verifier audits: Decision justified? Evidence complete?
- If issues → fix → re-verify (MAX 2 iterations)
```

---

### Step 6 — Final Verification

```text
DO:
- Run canonical gate to verify decision documented
- Update CHANGELOG.md with GAP-07 entry
- If ADOPT: outline integration plan
- If DEFER: document conditions for re-evaluation
- If REJECT: document alternatives considered

GATE (CANONICAL):
cat docs/reference/traycer-evaluation.md | grep -E "^\- \[(x|X)\] (ADOPT|DEFER|REJECT)" && \
echo "PASS"

EVIDENCE REQUIRED:
- Decision checkbox marked
- CHANGELOG updated
- Next steps documented

SELF-REVIEW (Builder):
- [ ] Decision is clear
- [ ] Evidence supports decision
- [ ] Next steps defined

MODE 4 VERIFICATION (FINAL):
- Verifier audits: Decision valid? Evidence complete?
- Must return: {"ready": true, "decision": "ADOPT|DEFER|REJECT"}
```

---

### STOP CONDITIONS

```text
STOP IF:
- Traycer completely unavailable (no CLI, no web)
- Pricing prohibitive (>$100/month for evaluation)
- No test task can be defined

ON STOP:
- Document blocker
- Set decision to DEFER with conditions
- Complete evaluation document with available information
```

---

## 10. Summary

| Requirement | Deliverable |
|-------------|-------------|
| Files to CREATE | `traycer-evaluation.md` |
| Files to MODIFY | `CHANGELOG.md`, possibly `templates/traycer/*` |
| Canonical Gate | Decision (ADOPT/DEFER/REJECT) documented |
| Minimum tests | 5 test cases with evidence |
| Scope | **EVALUATION ONLY** — no integration |

**All sections complete.** Ready for Mode 3 (Build) execution.
