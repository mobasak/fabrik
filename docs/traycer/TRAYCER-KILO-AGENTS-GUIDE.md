# Kilo Agents for Traycer Epic Planning

**Last Updated:** 2026-03-16
**Purpose:** Configure Traycer to use maximum-thinking Kilo agents for plan discussions

---

## Highest-Capability Agents (Ranked by Thinking Power)

### Tier 1: Maximum Thinking (Force These)

| Agent | Thinking Level | Best Use Case | Recommended Strategy |
|-------|----------------|---------------|---------------------|
| **orchestrator** | ⭐⭐⭐⭐⭐ | Multi-step workflows, dependency analysis, architecture sequencing | **critical** |
| **plan** | ⭐⭐⭐⭐⭐ | Strategic planning, approach validation, phase design | **critical** |
| **ask** | ⭐⭐⭐⭐ | Deep reasoning, verification, complex Q&A | **premium** |

### Tier 2: Standard Capability

| Agent | Thinking Level | Best Use Case | Recommended Strategy |
|-------|----------------|---------------|---------------------|
| **code** | ⭐⭐⭐ | Implementation details, code-level review | **standard** |
| **debug** | ⭐⭐⭐ | Error analysis, troubleshooting | **standard** |
| **general** | ⭐⭐ | Quick checks, simple analysis | **economy** |

---

## Strategy to Model Mapping

### Critical Strategy (Prime Tier) - ~$5/call

Forces the most capable models with maximum thinking:

```
TIER: Prime
MODELS:
- kilo/anthropic/claude-opus-4.6      ← Best reasoning
- kilo/openai/gpt-5.2-pro             ← GPT Pro
```

**Cost:** ~$5.00 per call
**Use for:** Critical architecture decisions, complex dependency analysis

### Premium Strategy (Strong Tier) - ~$3/call

Forces high-capability models:

```
TIER: Strong
MODELS:
- kilo/anthropic/claude-sonnet-4.6    ← Strong reasoning
- kilo/openai/gpt-5.3-codex           ← Code-focused
- kilo/google/gemini-3.1-pro-preview  ← Google's best
```

**Cost:** ~$3.00 per call
**Use for:** Standard architecture review, verification

### Standard Strategy (Balanced Tier) - ~$0.50/call

```
TIER: Balanced
MODELS:
- kilo/openai/gpt-5.2-codex
- kilo/zhipu/glm-5
- kilo/xai/grok-4.1-fast
```

**Cost:** ~$0.50 per call
**Use for:** Verification passes, follow-up questions

---

## Recommended Traycer Epic Configuration

### For Maximum Quality (Cost: ~$13/Epic)

**Step 1: Architecture Review**
```python
kilo_review(
    prompt="[Epic architecture analysis]",
    files=[...],
    strategy="critical"  # Forces Prime tier (orchestrator agent)
)
```
**Agent:** orchestrator
**Model:** claude-opus-4.6
**Cost:** ~$5

**Step 2: Strategic Planning**
```python
kilo_plan(
    prompt="[Phase sequencing validation]",
    files=[...],
    strategy="critical"  # Forces Prime tier (plan agent)
)
```
**Agent:** plan
**Model:** claude-opus-4.6
**Cost:** ~$5

**Step 3: Verification**
```python
kilo_ask(
    prompt="[Verify fixes applied]",
    files=[...],
    strategy="premium"  # Forces Strong tier (ask agent)
)
```
**Agent:** ask
**Model:** claude-sonnet-4.6
**Cost:** ~$3

**Total:** ~$13 per Epic (maximum thinking capability)

**Monthly capacity (Traycer Pro+ $50):** ~3-4 Epics with max-quality Kilo

---

### For Balanced Quality (Cost: ~$8/Epic)

**Step 1: Architecture Review**
```python
kilo_review(
    prompt="[Epic architecture analysis]",
    files=[...],
    strategy="premium"  # Forces Strong tier
)
```
**Cost:** ~$3

**Step 2: Strategic Planning**
```python
kilo_plan(
    prompt="[Phase sequencing validation]",
    files=[...],
    strategy="premium"  # Forces Strong tier
)
```
**Cost:** ~$3

**Step 3: Verification**
```python
kilo_ask(
    prompt="[Verify fixes applied]",
    files=[...],
    strategy="standard"  # Balanced tier
)
```
**Cost:** ~$0.50

**Total:** ~$6.50 per Epic (high quality, better budget)

**Monthly capacity (Traycer Pro+ $50):** ~7-8 Epics

---

### For Budget-Conscious (Cost: ~$3.50/Epic)

**Step 1: Architecture Review**
```python
kilo_review(
    prompt="[Epic architecture analysis]",
    files=[...],
    strategy="premium"  # Strong tier
)
```
**Cost:** ~$3

**Step 2: Verification**
```python
kilo_ask(
    prompt="[Verify all aspects]",
    files=[...],
    strategy="standard"  # Balanced tier
)
```
**Cost:** ~$0.50

**Total:** ~$3.50 per Epic (original recommendation)

**Monthly capacity (Traycer Pro+ $50):** ~14 Epics

---

## Traycer Epic Prompt Template

### Maximum Thinking Configuration

When telling Traycer to use Kilo for planning, specify:

```
Use Kilo agents with maximum thinking capability:

1. Architecture Review:
   - Tool: kilo_review
   - Strategy: critical
   - Agent: orchestrator
   - Expected model: claude-opus-4.6

2. Strategic Planning:
   - Tool: kilo_plan
   - Strategy: critical
   - Agent: plan
   - Expected model: claude-opus-4.6

3. Verification:
   - Tool: kilo_ask
   - Strategy: premium
   - Agent: ask
   - Expected model: claude-sonnet-4.6

Budget: ~$13 per Epic for maximum quality
Accept this cost for critical architecture decisions.
```

---

## Agent Capabilities Detailed

### orchestrator (Tier 1)

**Thinking Capabilities:**
- Multi-step workflow analysis
- Dependency graph reasoning
- Architecture sequencing
- Risk assessment
- Integration point identification

**Best For:**
- WordPress Site Factory refactoring
- Multi-phase Epic planning
- Complex system architecture
- Deployment pipeline design

**Example Prompt:**
```
Review this WordPress Site Factory epic implementation plan for:
1. Dependency correctness (no missing prerequisites)
2. Architecture sequencing (planner before deployer)
3. Rollout safety (regression baseline first)
4. Idempotency boundaries (spec wrapper before stage tracking)
5. Infrastructure timing (provisioner after execution flow stable)

Identify any BLOCKER-level sequencing errors or missing critical prerequisites.
Use critical strategy for maximum thinking depth.
```

### plan (Tier 1)

**Thinking Capabilities:**
- Strategic approach design
- Phase breakdown optimization
- Alternative approach comparison
- Long-term maintainability reasoning
- Scope boundary definition

**Best For:**
- Epic phase design
- Refactoring strategy
- Feature rollout planning
- Migration approaches

**Example Prompt:**
```
Review this phase plan for the WordPress Site Factory restructuring:

Phase 0: Regression baseline + resolver
Phase 1: ResolvedSpec + manifest generators
Phase 2: Stage decomposition + idempotency
Phase 3: Infrastructure provisioner
Phase 4: Capability system

Evaluate:
1. Phase boundaries (correct abstraction levels?)
2. Deliverable clarity (each phase independently testable?)
3. Alternative sequencing (any safer approaches?)
4. Scope completeness (missing critical work?)

Use critical strategy for deep strategic thinking.
```

### ask (Tier 1)

**Thinking Capabilities:**
- Deep Q&A reasoning
- Verification logic
- Edge case identification
- Specification gap detection
- Assumption validation

**Best For:**
- Post-fix verification
- Spec clarification
- Edge case analysis
- Sanity checks

**Example Prompt:**
```
Verify that these fixes address the original issues:

Original Issues:
1. Missing WP_ENVIRONMENT_TYPE
2. No database restart policy
3. Backup volume not configured

Applied Fixes:
[show fixed spec]

Verify:
1. All original issues resolved
2. No new issues introduced
3. Edge cases covered (e.g., environment variable precedence)

Use premium strategy for thorough verification.
```

---

## Cost vs Quality Trade-offs

| Configuration | Cost/Epic | Quality | Monthly Epics | Use Case |
|--------------|-----------|---------|---------------|----------|
| **Maximum** | ~$13 | ⭐⭐⭐⭐⭐ | 3-4 | Critical production systems |
| **Balanced** | ~$7 | ⭐⭐⭐⭐ | 7-8 | Standard architecture work |
| **Budget** | ~$3.50 | ⭐⭐⭐ | 14 | Routine planning |

**Recommendation for WordPress Site Factory Epic:**
- Use **Maximum** configuration (~$13)
- This is a critical refactoring with complex dependencies
- Worth the cost for correct sequencing

---

## Forcing Specific Models

### Override Strategy with Direct Model Selection

```python
kilo_review(
    prompt="[Architecture analysis]",
    files=[...],
    # Don't specify strategy - override with model directly
    model="kilo/anthropic/claude-opus-4.6"  # Force Opus 4.6
)
```

**Note:** Direct model specification bypasses strategy-based routing.

---

## Troubleshooting: Exit Codes

When a Kilo CLI agent terminates, Traycer reports the exit code. Here are the common exit codes and their fixes:

### Exit Code 124: Timeout

| Aspect | Details |
|--------|---------|
| **Cause** | Task exceeded the agent's timeout limit |
| **Default** | 60 minutes (3600 seconds) |
| **Symptom** | `The terminal process "/bin/bash" terminated with exit code: 124` |

**Fixes:**
1. **Environment variable** (temporary): `export KILO_TIMEOUT=7200` (2 hours)
2. **Regenerate agents** with higher default: Edit `generate_kilo_agents.py` → change `KILO_TIMEOUT:-3600` → run script

**Root cause:** Complex tasks (large codebases, many files, multi-step operations) can exceed the timeout.

### Exit Code 1: Agent Failed

| Aspect | Details |
|--------|---------|
| **Cause** | Agent encountered an error but Kilo API call succeeded |
| **Symptom** | `The terminal process "/bin/bash" terminated with exit code: 1` |

**Common causes:**
1. **Missing Traycer report block** — Agent didn't output `BEGIN_TRAYCER_REPORT_MD...END_TRAYCER_REPORT_MD`
2. **Kilo API error** — Model not found, rate limit, auth failure
3. **Script error** — Missing dependencies, path issues

**Fixes:**
1. Check agent logs for actual error message
2. Verify `KILO_API_KEY` is set and valid
3. Verify model name is correct in agent script
4. For missing report block: Agent scripts now handle this gracefully (exit 0 if Kilo succeeded)

### Exit Code 0: Success

Agent completed successfully. Traycer will parse the output and proceed.

### Timeout Configuration

| Mode | Timeout Control | How to Set |
|------|-----------------|------------|
| **Direct Handoff** | `KILO_TIMEOUT` env var | `export KILO_TIMEOUT=3600` |
| **Smart YOLO** | Per-phase via Traycer UI | YOLO tab → timeout field |
| **Agent default** | Built into agent script | Regenerate agents |

---

## Summary

**For Traycer Epic to get maximum thinking capability:**

1. **Use these agents:**
   - `kilo_review` (orchestrator) for architecture
   - `kilo_plan` (plan) for strategy
   - `kilo_ask` (ask) for verification

2. **Force highest tiers:**
   - `strategy="critical"` → Prime tier (Opus 4.6, ~$5)
   - `strategy="premium"` → Strong tier (Sonnet 4.6, ~$3)

3. **Budget:**
   - Maximum quality: ~$13/Epic (3-4 Epics/month)
   - Balanced: ~$7/Epic (7-8 Epics/month)
   - Budget: ~$3.50/Epic (14 Epics/month)

**For WordPress Site Factory Epic:** Recommend **maximum** configuration ($13) for critical architecture correctness.
