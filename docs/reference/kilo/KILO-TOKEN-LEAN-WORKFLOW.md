# Kilo Token-Lean Workflow Guide

**Last Updated:** 2026-03-17
**Status:** Production Ready

## Overview

The Kilo code review workflow has been optimized for **efficient**, **fast**, **result-oriented**, and **token-economical** solo developer use. This guide documents the operational characteristics and recommended configuration.

---

## Assessment: Why It's Now Production-Ready

### Efficiency ✅

**Default review scope is `diff_only`**, not `full`:
- Reduces unnecessary context volume by sending only changed lines
- Oversized `full` prompts auto-degrade to `diff_only` before failing
- Prevents prompt size failures while maintaining review quality

**Expensive features are opt-in by env flag:**
- Multi-pass review: OFF by default (`KILO_ENABLE_MULTI_PASS=0`)
- PASS verification: OFF by default (`KILO_ENABLE_PASS_VERIFY=0`)
- Audit logging: OFF by default (`KILO_ENABLE_AUDIT=0`)
- Common path stays lean, advanced features available when needed

**Quality enforcement remains strict:**
- JSON schema validation: REQUIRED
- Structured evidence for BLOCKER/MAJOR issues: REQUIRED
- Plan coverage validation: REQUIRED
- Token savings come from scope reduction, not accepting low-quality outputs

### Speed ✅

**Monitored execution replaces blind timeout:**
- `run_kilo()` uses `Popen + _monitor_process()`
- Tracks stdout/stderr growth as progress signal
- Slow but active runs continue (no premature kills)
- Hung processes still terminated via idle timeout (120s default)

**Model escalation limited to one fallback:**
- Solo workflow optimized: 1 fallback maximum
- No long escalation ladder walks
- Faster failure path when models don't work

**Doc-only reviews are lighter:**
- Lower iteration caps for documentation reviews
- Appropriate effort allocation per content type

### Result-Oriented ✅

**Hard schema enforcement:**
- Verdict, summary, issues, plan_coverage all required
- Structured evidence objects for serious issues
- Optimized for actionable review/fix/re-review cycle
- No verbose commentary without structure

**Retry with JSON skeleton on malformed output:**
- Improves odds of getting usable review output
- One retry attempt with structured template
- Better than immediate failure on schema violations

**Reliable state management:**
- Verification usage accounting fixed (`usage.add_review(verify_result)`)
- Config.variant state leak fixed (try/finally restoration)
- Config.model state leak fixed (try/finally restoration)
- No cross-iteration state pollution

**Incomplete-JSONL retry resilience:**
- Retries on "no step_finish event received"
- Retries on "Too many parse errors"
- Does NOT retry on size/schema/quality failures (correct behavior)

### Token Economy ✅

**Single biggest saving: `review_mode="diff_only"`**
- Full file contents no longer sent by default
- Context limited to changed lines + surrounding context
- Estimated 60-75% token reduction vs. full mode

**No automatic multi-pass costs:**
- Multi-pass review requires explicit `KILO_ENABLE_MULTI_PASS=1`
- Default single-pass workflow for speed

**No automatic PASS re-verification:**
- PASS max-variant verification requires `KILO_ENABLE_PASS_VERIFY=1`
- Saves double-review tokens on successful reviews

**Batching remains in place:**
- Large file sets split into manageable batches
- Prevents single-prompt explosions
- Maintains review quality while controlling cost

---

## Operational Recommendations

### Default Configuration (Token-Lean)

```bash
# These are already the defaults - no action needed
review_mode = "diff_only"           # ✓ Set in code
verify_high_risk = False            # ✓ Set in code
KILO_ENABLE_MULTI_PASS = 0          # ✓ Default OFF
KILO_ENABLE_PASS_VERIFY = 0         # ✓ Default OFF
KILO_ENABLE_AUDIT = 0               # ✓ Default OFF
```

### When to Use Full Mode

```bash
# Whole-file context needed (rare cases)
python scripts/kilo_code_review.py review <files> \
  --review-mode full \
  --plan "Task description" \
  --review-agent ask \
  --output json
```

**Use full mode only when:**
- Reviewing architectural changes spanning entire files
- Context from unmodified code is essential
- Diff-only mode produces incomplete reviews

### Recommended Workflow (Staged Review)

**Use `staged` for the main reviewer surface instead of `diff_only`:**

```bash
# 1. Coder implements
# 2. Run final_gate.py (deterministic checks)
python /opt/fabrik/scripts/final_gate.py

# 3. Stage intended files only
git add <files>

# 4. Initial staged review
export REVIEW_ID="feat-auth-$(date +%Y%m%d)"
python scripts/kilo_code_review.py staged \
  --session continue \
  --tracked-review-id "$REVIEW_ID" \
  --plan "Brief micro-spec" \
  --review-agent ask \
  --output json

# 5. Coder fixes issues

# 6. Verify fixes (lighter than full review)
python scripts/kilo_code_review.py review \
  --session continue \
  --tracked-review-id "$REVIEW_ID" \
  --verify-mode \
  --fixes-description "Fixed auth validation edge case" \
  --review-agent ask \
  --output json

# 7. Repeat verify if needed

# 8. Run final_gate.py again
python /opt/fabrik/scripts/final_gate.py

# 9. Commit
git commit -m "feat: implement auth validation"
```

### Scoped Session Continuation

**Sessions are now scoped by:**
- **Project root** (git repository)
- **Git branch** (prevents cross-branch pollution)
- **Tracked review ID** (stable cycle identifier)

**Required for continuation:**
```bash
--session continue --tracked-review-id "$REVIEW_ID"
```

**Without `--tracked-review-id`, continuation will fail:**
```
ValueError: --tracked-review-id is required with --session continue
```

### Daily Usage Pattern

```bash
# Standard review (token-efficient)
python scripts/kilo_code_review.py review <files> \
  --plan "Brief task description" \
  --review-agent ask \
  --output json

# Continue session if issues found (REQUIRES tracked-review-id)
python scripts/kilo_code_review.py review <files> \
  --session continue \
  --tracked-review-id "$REVIEW_ID" \
  --output json

# Repeat until verdict=PASS (max 5 iterations recommended)
```

### Optional Features (Opt-In Only)

```bash
# High-stakes review: enable multi-pass
export KILO_ENABLE_MULTI_PASS=1
python scripts/kilo_code_review.py review <files> --plan "..." --output json

# Paranoid mode: enable PASS verification
export KILO_ENABLE_PASS_VERIFY=1
python scripts/kilo_code_review.py review <files> --plan "..." --output json

# Metrics tracking: enable audit logging
export KILO_ENABLE_AUDIT=1
python scripts/kilo_code_review.py review <files> --plan "..." --output json
```

---

## Implementation Verification

### 1. Retry Logic for Incomplete JSONL

**Helper function location:** Line 2010
```bash
$ grep -n "_is_retryable_parse_failure" scripts/kilo_code_review.py
2010:def _is_retryable_parse_failure(exc: Exception) -> bool:
2127:                if _is_retryable_parse_failure(e) and attempt < MAX_RETRIES - 1:
```

**Retry markers:**
```bash
$ grep -n "no step_finish event received" scripts/kilo_code_review.py
1889:            raise RuntimeError("Kilo run incomplete - no step_finish event received")
2014:        "no step_finish event received",
```

**Retry message:**
```bash
$ grep -n "Kilo incomplete/garbled response" scripts/kilo_code_review.py
2130:                        f"⏳ Kilo incomplete/garbled response ({e}). Retrying in {wait_time}s...",
```

### 2. Parser Stays Strict

`parse_kilo_jsonl()` still raises on incomplete output:
- Line 1889: `raise RuntimeError("Kilo run incomplete - no step_finish event received")`
- Strictness preserved, retry handled in `run_kilo()`

### 3. Retry Only Transport Failures

**Retried:**
- `"no step_finish event received"` - incomplete stream
- `"Too many parse errors"` - garbled JSONL

**NOT retried:**
- Oversized output
- Invalid output type
- Review-schema failures
- Evidence/coverage validation failures

### 4. Uses Existing Retry Budget

- Uses `MAX_RETRIES` from `run_kilo()`
- No separate retry counter
- Exponential backoff: `2**attempt` seconds

---

## Token Savings Estimate

| Feature | Before | After | Savings |
|---------|--------|-------|---------|
| Review mode | `full` | `diff_only` | ~60-75% |
| Multi-pass | Always ON | OFF by default | ~50% on PASS |
| PASS verification | Auto for high-risk | OFF by default | ~25% on PASS |
| **Total for PASS case** | ~4x tokens | ~1x tokens | **~75%** |

---

## Timeout Configuration

### Default Values (Suitable for Most Cases)

```bash
KILO_IDLE_TIMEOUT=120      # Kills if no output for 120s
KILO_HARD_TIMEOUT=1200     # Absolute max runtime: 20 minutes
KILO_POLL_INTERVAL=1.0     # Check every 1 second
```

### Adjust Only If Needed

```bash
# For very slow models or large diffs
export KILO_IDLE_TIMEOUT=300
export KILO_HARD_TIMEOUT=2400
```

---

## Troubleshooting

### "Kilo incomplete/garbled response" Retry

**What it means:** Upstream Kilo returned incomplete JSONL (no `step_finish` event)

**What happens:**
1. Script detects incomplete response
2. Waits `2**attempt` seconds (exponential backoff)
3. Retries with same prompt
4. Max 3 attempts before final failure

**If persistent:**
- Check network stability
- Try different model
- Reduce file count in batch

### "Kilo timeout" vs "Idle timeout"

**Idle timeout (⏳):** No output for 120s → process hung
**Hard timeout:** Absolute max runtime exceeded (1200s)

Both are retried automatically (up to MAX_RETRIES).

---

## Best Practices

### 1. Keep Flags OFF by Default
- Enable multi-pass/verification/audit only for critical reviews
- Default token-lean workflow suitable for 95% of cases

### 2. Use diff_only Mode
- Full mode only when whole-file context essential
- Prompt degradation handles oversized full prompts automatically

### 3. Fix ALL Issues (Not Just Blockers)
- Fix BLOCKER, MAJOR, and MINOR issues
- Re-review until verdict=PASS
- Max 5 iterations before escalating

### 4. Monitor Usage
- Enable audit logging (`KILO_ENABLE_AUDIT=1`) periodically
- Check cumulative stats at end of review
- Adjust workflow if costs too high

---

## Production Status

**Version:** Commit 5a1fcab
**Status:** ✅ PRODUCTION READY
**Token Efficiency:** ~75% reduction vs. previous defaults
**Reliability:** Monitors process health, no premature kills
**State Safety:** No config leaks across iterations

---

---

## Issue-State Persistence

**Automatic issue tracking across iterations:**

### Storage Location
```
.droid/reviews/<tracked_review_id>_issues.json
```

### Issue Lifecycle

| Status | Meaning |
|--------|---------|
| `open` | Issue still present in latest review |
| `fixed` | Previously open, now absent from review |
| `rejected` | Manually marked as false positive |

### Issue Key Generation

Issues are fingerprinted by:
- `tracked_review_id`
- `file`
- `lines`
- `category`
- `why` (first 120 chars)

### Workflow Integration

```bash
# Get only open issues for coder feedback
python -c "
from scripts.kilo_code_review import get_open_issues
issues = get_open_issues('$REVIEW_ID')
for issue in issues:
    print(f'{issue[\"file\"]}:{issue[\"lines\"]} - {issue[\"why\"]}')
"
```

**Benefits:**
- No duplicate issue reporting across iterations
- Tracks when issues are fixed
- Provides historical context
- Enables focused coder prompts (open issues only)

---

## Micro-Spec Format (Plan Input)

**Pass concise specs, not full plans:**

### Recommended Format

```text
Objective:
<one sentence>

Non-goals:
- ...
- ...

Requirements:
REQ-1: ...
REQ-2: ...
REQ-3: ...

Acceptance checks:
- ...
- ...

Touched modules:
- path/a
- path/b
```

### DO NOT Pass

- Brainstorm text
- Roadmap sections
- Rationale/history
- Alternatives considered
- Long architectural discussions

**Why:** The script extracts numbered requirements (`REQ-*`, bullets) for plan coverage validation. Long plans inflate prompt size without adding review value.

---

## Semantic Batching (Caller Responsibility)

**Group files by subsystem before calling the script:**

### Recommended Buckets

```bash
# Auth/Security files
python scripts/kilo_code_review.py staged \
  --session continue \
  --tracked-review-id "$REVIEW_ID" \
  --plan "Auth module spec" \
  $(git diff --cached --name-only | grep -E 'auth|security')

# Backend/API files
python scripts/kilo_code_review.py staged \
  --session continue \
  --tracked-review-id "$REVIEW_ID" \
  --plan "API spec" \
  $(git diff --cached --name-only | grep -E 'api|routes')

# Frontend/UI files
python scripts/kilo_code_review.py staged \
  --session continue \
  --tracked-review-id "$REVIEW_ID" \
  --plan "UI spec" \
  $(git diff --cached --name-only | grep -E 'frontend|components')
```

**Rule:** If >5 staged files span unrelated areas, do NOT send them as one mixed batch.

**Why:** The script batches numerically. Better semantic grouping happens in the caller.

---

## Reviewer Setting Freeze (Per Cycle)

**Keep settings constant within one `tracked_review_id`:**

### Frozen Settings

- `review_agent`
- `strategy`
- `variant`
- Optional: `model`

### Enforcement Pattern

```bash
# First review in cycle
export REVIEW_ID="feat-xyz"
export REVIEW_AGENT="ask"
export STRATEGY="economy"
export VARIANT="high"

python scripts/kilo_code_review.py staged \
  --session continue \
  --tracked-review-id "$REVIEW_ID" \
  --review-agent "$REVIEW_AGENT" \
  --strategy "$STRATEGY" \
  --variant "$VARIANT" \
  --plan "..."

# Subsequent reviews MUST use same settings
python scripts/kilo_code_review.py review \
  --session continue \
  --tracked-review-id "$REVIEW_ID" \
  --review-agent "$REVIEW_AGENT" \
  --strategy "$STRATEGY" \
  --variant "$VARIANT" \
  --verify-mode
```

**Why:** Prevents reviewer drift between cycles, ensures consistent review quality.

---

## Verify Mode (Intermediate Loops)

**Do NOT rerun full review after every small fix:**

### When to Use Verify

- After minor fixes (1-3 issues)
- When fix is localized to one module
- When previous review was recent (<1 hour)

### When to Use Full Review

- Auth/security/migrations/infra changed
- Fix touched multiple modules
- Previous findings were architectural
- >24 hours since last review

### Usage Pattern

```bash
# First pass: full staged review
python scripts/kilo_code_review.py staged \
  --tracked-review-id "$REVIEW_ID" \
  --plan "..." \
  --output json

# Middle passes: verify only
python scripts/kilo_code_review.py review \
  --session continue \
  --tracked-review-id "$REVIEW_ID" \
  --verify-mode \
  --fixes-description "Fixed validation edge case in auth.py:45" \
  --output json

# Final risky pass: staged again if needed
python scripts/kilo_code_review.py staged \
  --session continue \
  --tracked-review-id "$REVIEW_ID" \
  --output json
```

---

## References

- Implementation: `scripts/kilo_code_review.py`
- CHANGELOG: Entry dated 2026-03-17
- Commit history: efb2763 → 36f361d → 6640382 → 5a1fcab → 9324b32
