# Traycer Epic + Kilo Direct CLI Integration

**Last Updated:** 2026-03-07
**Status:** ✅ Working Method (MCP Not Supported)

---

## Why Direct CLI Instead of MCP

**Finding:** Traycer documentation (`/opt/fabrik/docs/traycer/README.md`) states:

> **Remote only:** Local MCP servers NOT supported

**What this means:**
- Traycer only accepts **remote HTTPS MCP servers** registered on traycer.ai platform
- Local stdio MCP servers (what we built) are **not supported**
- Config files (`~/.traycer/mcp.json` or `~/.factory/mcp.json`) are **not read**

**Solution:** Use direct CLI execution instead of MCP protocol.

---

## How Traycer Can Access Kilo

Traycer runs in your WSL environment and has:
- ✅ Filesystem access to `/opt/fabrik/`
- ✅ CLI agent execution capability (`~/.traycer/cli-agents/`)
- ✅ Python interpreter access

**Therefore:** Traycer can execute Kilo CLI directly via shell commands.

---

## Kilo CLI Commands for Maximum Thinking

### 1. Architecture Review (orchestrator @ critical)

```bash
python /opt/fabrik/scripts/kilo_code_review.py review \
  --review-agent orchestrator \
  --strategy critical \
  --output json \
  --plan "Review WordPress Site Factory epic implementation plan for:
1. Dependency correctness (no missing prerequisites)
2. Architecture sequencing (planner before deployer)
3. Rollout safety (regression baseline first)
4. Idempotency boundaries (spec wrapper before stage tracking)
5. Infrastructure timing (provisioner after execution flow stable)

Epic context: Phase-based restructuring of fabrik deploy-wordpress to use
ResolvedSpec wrapper, manifest generators, stage decomposition, and
infrastructure provisioner. Currently all logic is in single monolithic
SiteDeployer class.

Identify BLOCKER-level sequencing errors or missing critical prerequisites." \
  --file /opt/fabrik/docs/development/plans/wordpress-site-factory-epic.md
```

**Expected cost:** ~$5 (Prime tier - claude-opus-4.6)

### 2. Strategic Planning (plan @ critical)

```bash
python /opt/fabrik/scripts/kilo_code_review.py review \
  --review-agent plan \
  --strategy critical \
  --output json \
  --plan "Review phase sequencing for WordPress Site Factory refactoring:

Phase 0: Regression baseline + ContainerResolver
Phase 1: ResolvedSpec wrapper + manifest generators
Phase 2: Stage decomposition + idempotency tracking
Phase 3: Infrastructure provisioner
Phase 4: Capability system integration

Evaluate:
1. Phase boundaries (correct abstraction levels?)
2. Deliverable clarity (each phase independently testable?)
3. Alternative sequencing (any safer approaches?)
4. Scope completeness (missing critical work?)

Provide strategic recommendations for phase design." \
  --file /opt/fabrik/docs/development/plans/wordpress-site-factory-epic.md
```

**Expected cost:** ~$5 (Prime tier - claude-opus-4.6)

### 3. Verification (ask @ premium)

```bash
python /opt/fabrik/scripts/kilo_code_review.py review \
  --review-agent ask \
  --strategy premium \
  --output json \
  --plan "Verify Epic plan completeness:

Phase 0 (baseline):
- Regression tests cover existing deploy-wordpress flows? ✓
- ContainerResolver fix addresses name drift? ✓
- Test suite runs against real Coolify instance? ✓

Phase 1 (spec wrapper):
- ResolvedSpec captures all config variations? ✓
- Manifest generators handle Jinja2 templates? ✓
- Validation runs before deployment? ✓

Confirm all prerequisites satisfied and no edge cases missed."
```

**Expected cost:** ~$3 (Strong tier - claude-sonnet-4.6)

---

## Traycer Epic Prompt (Copy-Paste Ready)

Use this prompt in Traycer Epic chat to enable Kilo consultation:

```
KILO CONSULTATION MODE ENABLED

For this Epic planning session, consult Kilo CLI agents for architecture validation.

Kilo Location: /opt/fabrik/scripts/kilo_code_review.py
Execution Method: Direct CLI (not MCP - local MCP not supported by Traycer)

CONSULTATION WORKFLOW:

Step 1 - Architecture Review (Cost: ~$5)
Execute:
python /opt/fabrik/scripts/kilo_code_review.py review \
  --review-agent orchestrator \
  --strategy critical \
  --output json \
  --plan "[Insert epic architecture review prompt here]" \
  --file [relevant epic plan files]

Agent: orchestrator (max thinking capability)
Model: claude-opus-4.6 (Prime tier)
Focus: Dependency correctness, sequencing validation, BLOCKER identification

Step 2 - Strategic Planning (Cost: ~$5)
Execute:
python /opt/fabrik/scripts/kilo_code_review.py review \
  --review-agent plan \
  --strategy critical \
  --output json \
  --plan "[Insert phase sequencing review prompt here]" \
  --file [epic plan]

Agent: plan (max thinking capability)
Model: claude-opus-4.6 (Prime tier)
Focus: Phase boundaries, alternative approaches, scope gaps

Step 3 - Verification (Cost: ~$3)
Execute:
python /opt/fabrik/scripts/kilo_code_review.py review \
  --review-agent ask \
  --strategy premium \
  --output json \
  --plan "[Insert verification prompt checking all fixes applied]"

Agent: ask (high thinking capability)
Model: claude-sonnet-4.6 (Strong tier)
Focus: Completeness check, edge case coverage, fix validation

TOTAL BUDGET: ~$13 per Epic (worth it for critical architecture)

OUTPUT HANDLING:
- Parse JSON response from each command
- Extract "verdict", "issues", "summary" fields
- Apply BLOCKER/MAJOR fixes to Epic specs automatically
- Show cost tracking in final plan presentation
- Report quality score based on Kilo findings

EXECUTION RULES:
1. Run Step 1 first - do not proceed if BLOCKER found
2. Fix BLOCKER issues before Step 2
3. Run Step 2 for strategic validation
4. Apply recommendations and run Step 3 for verification
5. Present final plan with Kilo quality seal

Begin consultation now for WordPress Site Factory Epic.
```

---

## Expected Kilo JSON Response Format

### Success Response

```json
{
  "verdict": "PASS",
  "summary": "Architecture review complete. Phase sequencing is dependency-correct.",
  "issues": [
    {
      "severity": "MAJOR",
      "category": "ARCHITECTURE",
      "file": "phase-plan.md",
      "lines": "Phase 1",
      "why": "ResolvedSpec should validate config before manifest generation",
      "fix_hint": "Add validation step between spec resolution and manifest generation"
    }
  ],
  "plan_coverage": [
    {
      "requirement": "Dependency correctness",
      "status": "satisfied",
      "evidence": "All phases have clear prerequisites"
    }
  ],
  "cost": 5.24,
  "model": "kilo/anthropic/claude-opus-4.6"
}
```

### How Traycer Should Handle Response

```python
# Parse Kilo output
kilo_result = json.loads(kilo_stdout)

# Check verdict
if kilo_result["verdict"] == "BLOCKER":
    # STOP - critical issues found
    print(f"❌ BLOCKER issues found: {len(kilo_result['issues'])}")
    print("Cannot proceed until resolved.")
    # Show issues to user
    return

# Apply fixes
for issue in kilo_result["issues"]:
    if issue["severity"] in ["BLOCKER", "MAJOR"]:
        # Update Epic specs with fix_hint
        apply_fix(issue)

# Track cost
total_cost += kilo_result["cost"]

# Continue to next step
```

---

## Cost Budget (Direct CLI Same as MCP Would Be)

| Configuration | Cost/Epic | Quality | Epics/Month |
|--------------|-----------|---------|-------------|
| **Maximum** | ~$13 | ⭐⭐⭐⭐⭐ | 3-4 |
| **Balanced** | ~$7 | ⭐⭐⭐⭐ | 7-8 |
| **Budget** | ~$3.50 | ⭐⭐⭐ | 14 |

**Recommended for WordPress Site Factory:** Maximum ($13) - critical refactoring

---

## Agent Capabilities Reference

| Agent | Thinking Level | Strategy | Model | Cost | Best For |
|-------|----------------|----------|-------|------|----------|
| orchestrator | ⭐⭐⭐⭐⭐ | critical | opus-4.6 | ~$5 | Architecture/dependencies |
| plan | ⭐⭐⭐⭐⭐ | critical | opus-4.6 | ~$5 | Strategic planning |
| ask | ⭐⭐⭐⭐ | premium | sonnet-4.6 | ~$3 | Verification/Q&A |
| code | ⭐⭐⭐ | standard | codex | ~$0.50 | Implementation review |
| general | ⭐⭐ | economy | fast | ~$0.02 | Quick checks |

---

## Example: WordPress Epic Consultation

### Step 1: Architecture Review Command

```bash
python /opt/fabrik/scripts/kilo_code_review.py review \
  --review-agent orchestrator \
  --strategy critical \
  --output json \
  --plan "WordPress Site Factory Epic - Architecture Review

Context:
- Current: Monolithic SiteDeployer (812 lines)
- Goal: Phase-based restructuring with 5 phases
- Risk: Complex dependencies, must maintain backward compatibility

Review Requirements:
1. Phase 0 (regression baseline) - sufficient coverage?
2. Phase 1 (ResolvedSpec) - correct abstraction boundary?
3. Phase 2 (stage decomposition) - idempotency design sound?
4. Phase 3 (infrastructure provisioner) - timing correct?
5. Phase 4 (capability system) - integration points clear?

Identify BLOCKER issues only - this is critical production infrastructure." \
  --file /opt/fabrik/docs/development/plans/wordpress-site-factory-epic.md \
  --file /opt/fabrik/src/fabrik/wordpress/site_deployer.py
```

### Expected Kilo Response

```json
{
  "verdict": "PASS",
  "summary": "Phase sequencing is dependency-correct. Found 2 MAJOR improvements.",
  "issues": [
    {
      "severity": "MAJOR",
      "category": "ARCHITECTURE",
      "why": "Phase 1 should include manifest validation before Phase 2 uses them",
      "fix_hint": "Add ManifestValidator class in Phase 1, use in Phase 2"
    },
    {
      "severity": "MAJOR",
      "category": "TESTING",
      "why": "Phase 0 regression tests don't cover Coolify API edge cases",
      "fix_hint": "Add test for: container name conflicts, network isolation, volume mounts"
    }
  ],
  "cost": 5.12,
  "model": "kilo/anthropic/claude-opus-4.6"
}
```

### Traycer Action

```
Kilo Review Complete ($5.12)
- Verdict: PASS with improvements
- Issues: 2 MAJOR (no BLOCKERS)

Applying fixes:
1. Added ManifestValidator to Phase 1 deliverables
2. Enhanced Phase 0 test suite with edge cases

Updated Epic Brief reflects changes.
```

---

## Advantages Over MCP (Even If It Worked)

| Aspect | Direct CLI | MCP (If Supported) |
|--------|------------|-------------------|
| Setup complexity | Low (already works) | High (hosting required) |
| Latency | Local execution | Network round-trip |
| Auth management | None needed | API keys/OAuth |
| Cost | Kilo only | Kilo + hosting |
| Debugging | Direct stdout/stderr | Network layer issues |
| Security | Local only | HTTPS exposure |

**Direct CLI is simpler and faster.**

---

## Troubleshooting

### Issue: Command not found

**Cause:** Traycer can't find Python or Kilo script

**Fix:**
```bash
# Use absolute paths
/opt/fabrik/.venv/bin/python /opt/fabrik/scripts/kilo_code_review.py review ...
```

### Issue: JSON parsing error

**Cause:** Kilo returned non-JSON output (usually error message)

**Fix:**
```bash
# Check stderr for errors
python /opt/fabrik/scripts/kilo_code_review.py review ... 2>&1 | tee /tmp/kilo-debug.log
```

### Issue: High cost

**Cause:** Using critical strategy on large files

**Fix:**
- Use `--plan` for prompts instead of large `--file` attachments
- Reduce file count (only attach essential files)
- Use `premium` instead of `critical` for non-critical reviews

---

## Summary

**MCP Integration:** ❌ Not supported (Traycer only supports remote HTTPS servers)

**Direct CLI Integration:** ✅ Works today

**How to use:**
1. Copy Traycer Epic prompt from this guide
2. Paste into Traycer Epic chat
3. Traycer executes Kilo CLI commands directly
4. Parses JSON, applies fixes, presents final plan

**Cost:** Same as MCP would have been (~$13 for max quality)

**Benefit:** Simpler, faster, no hosting needed

---

## Files Reference

| File | Purpose |
|------|---------|
| `/opt/fabrik/scripts/kilo_code_review.py` | Kilo CLI (execute this) |
| `/opt/fabrik/docs/traycer/TRAYCER-KILO-AGENTS-GUIDE.md` | Agent capabilities |
| `/opt/fabrik/docs/traycer/TRAYCER-KILO-DIRECT-CLI.md` | This guide |
| `/opt/fabrik/docs/traycer/README.md` | Traycer overview (confirms no local MCP) |

---

## Next Step

**Copy the "Traycer Epic Prompt" section** and paste it into your Traycer Epic chat.

Traycer will then execute Kilo consultations for the WordPress Site Factory Epic and present a quality-validated plan.
