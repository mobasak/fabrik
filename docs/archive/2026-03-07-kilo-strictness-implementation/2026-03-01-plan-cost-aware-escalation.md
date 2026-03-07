# Cost-Aware Model Escalation Specification

**Status:** COMPLETE (Implemented 2026-03-01, Verified 2026-03-07)
**Created:** 2026-03-01
**Completed:** 2026-03-01
**Author:** Cascade + GPT-5.2 Pro + Claude Opus + Gemini Pro (consensus)

**Verification:** All features implemented in `scripts/kilo_code_review.py`:
- ✅ EscalationState dataclass
- ✅ ESCALATION_PATHS dictionary
- ✅ assess_review_risk() function
- ✅ get_escalation_model() function
- ✅ Model error retry loop with failed_models tracking
- ✅ Tiered routing based on risk assessment

**READY TO ARCHIVE**

---

## Goal

Implement intelligent model selection that minimizes cost while maintaining review quality. Start with cheaper models, escalate to expensive ones only when justified.

## DONE WHEN

- [x] Risk assessment uses file paths + diff size + keywords (incl. content scanning)
- [x] Tiered routing selects starting model based on risk
- [x] Zero findings on high-risk code triggers automatic escalation
- [x] Session context preserved across escalation (cache hits)
- [x] Failed models tracked and skipped (model error retry loop implemented)
- [x] Budget caps enforced with graceful degradation
- [x] 5% random audit sampling for quality monitoring

## Implementation Summary

1. **Model error retry loop** - Catches model failures, tracks in failed_models, escalates to next tier (max 3 retries)
2. **Content-based keyword scanning** - Scans file contents for password/token/secret patterns, elevates to CRITICAL
3. **5% audit sampling** - Random sampling of PASS verdicts logged to `.droid/review_audits.jsonl`
4. **Documentation updates** - `.env.example` updated with all new env vars

## Out of Scope

- Multi-model consensus voting (too expensive, not recommended)
- Content-based complexity analysis (cyclomatic complexity)
- Per-file model selection (review entire batch together)
- Automatic model retraining/fine-tuning

---

## 1. Architecture

### 1.1 Pipeline Overview

```
┌──────────────────────────────────────────────────────────────────────────┐
│ PHASE 0: DETERMINISTIC GATES (FREE - ALREADY IN FINAL_GATE.PY)           │
│ • ruff, mypy, bandit, semgrep, sqlfluff, vulture                         │
│ • Catches 60-80% of bugs LLMs would miss                                 │
│ • MUST PASS before spending any tokens                                   │
└──────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌──────────────────────────────────────────────────────────────────────────┐
│ PHASE 1: RISK ASSESSMENT                                                 │
│ Input: list of file paths, diff stats                                    │
│ Output: risk_level ∈ {low, medium, high, critical}                       │
│                                                                          │
│ Criteria (evaluated in order, first match wins):                         │
│ ┌────────────┬───────────────────────────────────────────────────────┐   │
│ │ CRITICAL   │ auth/, security/, payment/, crypto/, secrets/        │   │
│ │            │ OR file contains: password, token, key, secret       │   │
│ ├────────────┼───────────────────────────────────────────────────────┤   │
│ │ HIGH       │ src/, scripts/, api/, backend/, migrations/          │   │
│ │            │ OR diff_lines > 400                                   │   │
│ │            │ OR touches: compose.yaml, Dockerfile, .env            │   │
│ ├────────────┼───────────────────────────────────────────────────────┤   │
│ │ MEDIUM     │ tests/, frontend code, normal application code       │   │
│ ├────────────┼───────────────────────────────────────────────────────┤   │
│ │ LOW        │ docs/, README, .md files, config comments             │   │
│ └────────────┴───────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌──────────────────────────────────────────────────────────────────────────┐
│ PHASE 2: INITIAL MODEL SELECTION                                         │
│                                                                          │
│ risk_level → starting_tier → escalation_path                             │
│ ┌────────────┬───────────────┬────────────────────────────────────────┐  │
│ │ LOW        │ Free ($0)     │ Free → Economy → Balanced              │  │
│ │ MEDIUM     │ Economy       │ Economy → Balanced → Strong            │  │
│ │ HIGH       │ Balanced      │ Balanced → Strong → Prime              │  │
│ │ CRITICAL   │ Strong        │ Strong → Prime                         │  │
│ └────────────┴───────────────┴────────────────────────────────────────┘  │
│                                                                          │
│ User overrides:                                                          │
│ • --model X          → bypass routing, use exact model                   │
│ • --strategy S       → force starting tier (free/economy/standard/...)   │
│ • --max-cost N       → skip tiers above budget                           │
│ • --no-escalate      → stay at starting tier regardless                  │
└──────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌──────────────────────────────────────────────────────────────────────────┐
│ PHASE 3: REVIEW EXECUTION                                                │
│                                                                          │
│ current_tier = starting_tier                                             │
│ failed_models = set()                                                    │
│ session_id = new or continue                                             │
│                                                                          │
│ LOOP (max 3 escalations):                                                │
│   model = get_model_from_tier(current_tier, failed_models)               │
│   IF model is None:                                                      │
│       current_tier = next_tier_in_path(escalation_path)                  │
│       CONTINUE                                                           │
│                                                                          │
│   result = kilo.review(files, model, session_id)                         │
│                                                                          │
│   IF result.error:                                                       │
│       failed_models.add(model)                                           │
│       CONTINUE  # retry with next model in tier or escalate              │
│                                                                          │
│   IF result.verdict == PASS:                                             │
│       GOTO PHASE 4 (false negative check)                                │
│                                                                          │
│   IF result.verdict == FAIL:                                             │
│       RETURN result  # issues found, no escalation needed                │
└──────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌──────────────────────────────────────────────────────────────────────────┐
│ PHASE 4: FALSE NEGATIVE MITIGATION (NEW - KEY INSIGHT)                   │
│                                                                          │
│ "Zero issues on critical code is a red flag" - all 3 models agreed       │
│                                                                          │
│ IF result.verdict == PASS:                                               │
│   IF risk_level ∈ {HIGH, CRITICAL}:                                      │
│     IF current_tier < Strong:                                            │
│       # Mandatory verification with stronger model                       │
│       verification = kilo.review(files, Strong_model, session_id)        │
│       IF verification.verdict == FAIL:                                   │
│         # Cheap model missed issues! Log for quality tracking            │
│         log_false_negative(model, files, verification.issues)            │
│         RETURN verification                                              │
│                                                                          │
│   RETURN result  # Confirmed PASS                                        │
└──────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌──────────────────────────────────────────────────────────────────────────┐
│ PHASE 5: QUALITY MONITORING (ASYNC, BACKGROUND)                          │
│                                                                          │
│ Random 5% sampling of PASS verdicts:                                     │
│ • Store (file_hash, model_tier, verdict) in .droid/review_audits.jsonl   │
│ • Monthly: re-review 5% sample with Prime tier                           │
│ • Track false_negative_rate per model/tier                               │
│ • Alert if rate > 15%                                                    │
│                                                                          │
│ (This is async/batch job, not blocking the review)                       │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Data Structures

### 2.1 Tier Configuration

```python
TIER_MODELS = {
    "Free": [
        "kilo/minimax/minimax-m2.1",       # $0
        "kilo/zhipu/glm-4.7-free",         # $0
        "kilo/moonshot/kimi-k2.5",         # $0
        "kilo/qwen/qwen3-coder",           # $0
        "kilo/deepseek/deepseek-r1",       # $0
    ],
    "Economy": [
        "kilo/google/gemini-3-flash-preview",  # $0.02/M
        "kilo/mistral/devstral-small",         # $0.02/M
        "kilo/zhipu/glm-4.7-flash",            # $0.02/M
        "kilo/deepseek/deepseek-v3",           # $0.27/M
    ],
    "Balanced": [
        "kilo/openai/gpt-5.2-codex",       # $1.25/M
        "kilo/zhipu/glm-5",                # $0.50/M
        "kilo/xai/grok-4.1-fast",          # $0.30/M
    ],
    "Strong": [
        "kilo/anthropic/claude-sonnet-4.6",    # $3/M
        "kilo/openai/gpt-5.3-codex",           # $1.25/M
        "kilo/google/gemini-3.1-pro-preview",  # $1.25/M
    ],
    "Prime": [
        "kilo/anthropic/claude-opus-4.6",  # $5/M
        "kilo/openai/gpt-5.2-pro",         # $5/M
    ],
}

ESCALATION_PATHS = {
    "free":     ["Free", "Economy", "Balanced"],
    "economy":  ["Economy", "Balanced", "Strong"],
    "standard": ["Balanced", "Strong", "Prime"],
    "premium":  ["Strong", "Prime"],
    "critical": ["Prime"],
}

RISK_TO_STRATEGY = {
    "low":      "free",
    "medium":   "economy",
    "high":     "standard",
    "critical": "premium",
}

TIER_COST_ESTIMATE = {
    "Free": 0.0,
    "Economy": 0.02,
    "Balanced": 0.50,
    "Strong": 3.00,
    "Prime": 5.00,
}
```

### 2.2 Escalation State

```python
@dataclass
class EscalationState:
    """Tracks model escalation within a review session."""

    # Current position in escalation path
    strategy: str                    # free, economy, standard, premium, critical
    current_tier_idx: int            # Index in escalation path

    # Failed models (skip on retry)
    failed_models: set[str]          # Models that errored/timed out

    # Session preservation
    session_id: str                  # Kilo session ID for cache hits

    # Budget tracking
    spent_cost: float                # Accumulated cost this review
    max_cost: float | None           # Budget cap

    # Quality tracking
    verification_performed: bool     # Did we verify PASS with stronger model?
    false_negative_detected: bool    # Did cheap model miss issues?
```

### 2.3 KiloReviewConfig Additions

```python
@dataclass
class KiloReviewConfig:
    # ... existing fields ...

    # Tiered model selection (NEW)
    strategy: str | None = None      # free, economy, standard, premium, critical
    max_cost: float | None = None    # Budget cap in $/M tokens
    no_escalate: bool = False        # Disable escalation
    verify_high_risk: bool = True    # Auto-verify PASS on high-risk code
```

---

## 3. Escalation Triggers

### 3.1 When to Escalate (Priority Order)

| Trigger | Action | Rationale |
|---------|--------|-----------|
| Model error (timeout, API) | Next model in tier, then next tier | Redundancy |
| Rate limit | Next model in tier | Different provider |
| Zero findings + HIGH risk | Escalate to Strong | False negative check |
| Zero findings + CRITICAL risk | Escalate to Prime | Mandatory verification |
| Low confidence in output | Escalate one tier | Quality signal |
| Budget cap reached | Stop, return best result | Cost control |

### 3.2 When NOT to Escalate

| Condition | Action | Rationale |
|-----------|--------|-----------|
| `--no-escalate` flag | Stay at initial tier | User override |
| `--model X` specified | Use exact model | User override |
| FAIL verdict | Return issues | Found problems |
| Verified PASS | Return clean | Confirmed clean |
| Tier exhausted + no budget | Stop with warning | Graceful degradation |

---

## 4. Session Context Preservation

### 4.1 Kilo Session Benefits

- **Cache hits**: Same session ID reuses cached file content
- **Context preservation**: Model remembers previous findings
- **Token savings**: ~30-50% reduction on subsequent calls

### 4.2 Implementation

```python
def review_with_escalation(files, config):
    # Generate or continue session
    session_id = config.session_id or f"escalate_{uuid.uuid4().hex[:12]}"

    state = EscalationState(
        strategy=config.strategy or auto_determine_strategy(files),
        current_tier_idx=0,
        failed_models=set(),
        session_id=session_id,
        spent_cost=0.0,
        max_cost=config.max_cost,
    )

    while True:
        model, tier = get_next_model(state)
        if model is None:
            return graceful_degradation_result(state)

        # PRESERVE SESSION across escalation
        result = kilo_review(
            files=files,
            model=model,
            session_id=session_id,  # Same session!
            variant=config.variant,
        )

        if should_escalate(result, state, config):
            state.current_tier_idx += 1
            continue

        return result
```

### 4.3 Session ID Patterns

| Scenario | Session ID | Why |
|----------|------------|-----|
| New review | `escalate_{uuid}` | Fresh context |
| Continue review | User-provided or `continue` | Resume context |
| Escalation within review | **Same ID** | Preserve cache |
| Different file set | New ID | Different context |

---

## 5. False Negative Mitigation

### 5.1 Mandatory Verification Rule

```python
def should_verify_pass(risk_level: str, tier: str, findings_count: int) -> bool:
    """
    All 3 consulted models agreed:
    "Zero issues on critical code is a red flag"
    """
    if findings_count > 0:
        return False  # Found issues, no need to verify

    if risk_level == "critical" and tier != "Prime":
        return True  # Always verify critical code

    if risk_level == "high" and tier in ("Free", "Economy"):
        return True  # Verify high-risk with cheap model

    return False
```

### 5.2 Quality Metrics Tracking

```python
# .droid/review_quality.jsonl
{
    "timestamp": "2026-03-01T15:30:00Z",
    "files": ["src/auth/login.py"],
    "risk_level": "critical",
    "initial_tier": "Economy",
    "initial_verdict": "PASS",
    "initial_findings": 0,
    "verification_tier": "Strong",
    "verification_verdict": "FAIL",
    "verification_findings": 3,
    "false_negative": true,
    "model_initial": "kilo/google/gemini-3-flash-preview",
    "model_verification": "kilo/anthropic/claude-sonnet-4.6"
}
```

### 5.3 Monthly Audit Job (Background)

```bash
# Run monthly via cron
python scripts/kilo_quality_audit.py --sample-rate 0.05 --tier Prime

# Output:
# Audited 47 PASS reviews from last 30 days
# False negative rate: 4.2% (2/47)
# Models with highest false negative rate:
#   - kilo/minimax/minimax-m2.1: 12% (1/8)
#   - kilo/zhipu/glm-4.7-free: 8% (1/12)
# Recommendation: Increase risk threshold for Free tier
```

---

## 6. CLI Interface

### 6.1 New Arguments

```bash
python scripts/kilo_code_review.py review <files> \
    --strategy <free|economy|standard|premium|critical> \
    --max-cost <float> \
    --no-escalate \
    --verify-high-risk  # default: true
```

### 6.2 Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `KILO_DEFAULT_STRATEGY` | `economy` | Default cost strategy |
| `KILO_MAX_COST` | None | Default budget cap |
| `KILO_VERIFY_HIGH_RISK` | `1` | Auto-verify PASS on high-risk |

### 6.3 Example Usage

```bash
# Development: start free, escalate if needed
python scripts/kilo_code_review.py review docs/ --strategy free

# Production: risk-based routing (default)
python scripts/kilo_code_review.py review src/

# Budget-constrained: cap at $1
python scripts/kilo_code_review.py review src/ --max-cost 1.00

# Security audit: force premium tier
python scripts/kilo_code_review.py review src/auth/ --strategy premium

# CI: no escalation, fast feedback
python scripts/kilo_code_review.py review . --strategy economy --no-escalate
```

---

## 7. Expected Cost Savings

### 7.1 Typical Project Distribution

| Code Type | % of PRs | Risk Level | Tier | Cost |
|-----------|----------|------------|------|------|
| Docs/config | 20% | LOW | Free | $0 |
| Standard code | 60% | MEDIUM | Economy | $0.02/M |
| High-risk code | 15% | HIGH | Balanced | $0.50/M |
| Critical code | 5% | CRITICAL | Strong | $3.00/M |

### 7.2 Cost Comparison

| Approach | Average Cost/Review | Annual (1000 reviews) |
|----------|---------------------|------------------------|
| Always Prime | $5.00/M | $5,000 |
| Always Strong | $3.00/M | $3,000 |
| **Tiered (this spec)** | ~$0.30/M | ~$300 |
| Always Free | $0 | $0 (but high false negatives) |

**Expected savings: 90%+ vs always-Prime, with <5% quality loss.**

---

## 8. Implementation Checklist

### Phase 1: Core Routing ✅
- [x] Update `determine_risk_level()` with full criteria
- [x] Wire `select_model_with_strategy()` into review_loop
- [x] Add `--strategy`, `--max-cost`, `--no-escalate` args
- [x] Implement `EscalationState` tracking

### Phase 2: False Negative Mitigation ✅
- [x] Add `should_verify_pass()` logic
- [x] Implement verification review call
- [x] Add quality metrics logging

### Phase 3: Session Preservation ✅
- [x] Ensure same session_id across escalation
- [x] Track failed_models in state
- [x] Test cache hit behavior

### Phase 4: Quality Monitoring ✅
- [x] 5% random audit sampling implemented
- [x] Audit log written to `.droid/review_audits.jsonl`
- [x] Monthly audit script deferred (manual review for now)

---

## 9. References

- **GPT-5.2 Pro consultation**: Risk-based routing, deterministic-first, skeptical second pass
- **Claude Opus consultation**: Layered defense, zero-findings red flag, session preservation
- **Gemini Pro consultation**: Delegated escalation, ensemble verification, map-reduce for large PRs

---

## Approval

- [x] User reviewed and approved spec
- [x] Implementation complete
