# Traycer→Kilo Coder Self-Review Workflow Analysis

**Date:** 2026-03-06
**Last Updated:** 2026-03-06
**Status:** PARTIALLY IMPLEMENTED - NEEDS FIXES

---

## User's Intended Workflow

1. **Traycer calls Kilo CLI coder agents** (via shell scripts)
2. **Coder agent codes** (implements the task)
3. **Coder agent reviews its own work FIRST** (Step 2.5 - self-review)
4. **Coder agent calls Kilo review script** (`kilo_code_review.py`)
5. **Coder agent fixes issues** (iterative loop until PASS)
6. **Traycer verifies** (Step 6 - NOT calling reviewers directly)

**Key Constraint:** Traycer does NOT call Kilo reviewers for code review. Only the coder agent calls the review script.

---

## Current Implementation Gaps

### Gap #1: No Self-Review in Traycer Prompts ❌

**File:** `~/.traycer/prompt-templates/Kilo Plan – Fabrik 9-Step.md`
**Line:** 138

**Current:**
```markdown
This is **Step 2 (Implementation)**. YOU must complete the full workflow:

**Step 3: Pre-Kilo Gate**  <-- Jumps directly here
```

**Missing:** Step 2.5 self-review instructions before Step 3.

**Impact:** Coder agents don't know they should self-review.

---

### Gap #2: Placeholder Self-Review (Not Real) ❌

**File:** `/opt/fabrik/scripts/traycer_agents_fixed/Free01-*.sh`
**Line:** 146

**Current:**
```bash
--self-review "Agent completed implementation"  # Generic placeholder
```

**Problem:**
- No actual review performed
- No spec compliance check
- No edge case verification
- No requirement coverage

**Impact:** Self-review is fake, provides no value.

---

### Gap #3: Auto-Review Hook is Optional ⚠️

**File:** `/opt/fabrik/scripts/traycer_agents_fixed/Free01-*.sh`
**Line:** 136

**Current:**
```bash
if [ "$TRAYCER_AUTO_REVIEW" = "1" ] && [ $EXIT_CODE -eq 0 ]; then
```

**Problem:** Only runs if environment variable is set.

**Impact:** Can be bypassed, not enforced.

---

### Gap #4: No Self-Review Logic in Agents ❌

**Current:** Agents have no code to perform actual self-review.

**Needed:**
- Prompt agent to analyze its own code
- Check against original task/spec
- Identify potential issues
- Generate structured report

**Impact:** Self-review step is completely missing.

---

## What Works ✅

1. **`traycer_agent_review.py`** - Review script works correctly
2. **Fixed agent scripts** - Correct file isolation (unique task files)
3. **Documentation** - Complete guide exists in `/opt/fabrik/templates/traycer/agent-post-execution-hook.md`
4. **Kilo review script** - Schema validation fixed, works reliably

---

## Required Fixes

### Fix #1: Update Traycer Prompt Template

**File:** `~/.traycer/prompt-templates/Kilo Plan – Fabrik 9-Step.md`

**Add after line 138:**
```markdown
**Step 2.5: Self-Review (MANDATORY)**

Before running gates, perform structured self-review:

1. Re-read the task/spec completely
2. Check each requirement against your code changes
3. Verify edge cases are handled
4. Confirm environment variables documented
5. Confirm database changes documented

Generate this report:

\```
SELF-REVIEW COMPLETE:
✓ All spec requirements implemented: [Yes/No + details]
✓ Edge cases handled: [list specific cases or "N/A"]
✓ Env vars documented: [list variables or "N/A"]
✓ DB changes documented: [list changes or "N/A"]
⚠ Potential issues: [list concerns or "None identified"]
\```

This self-review will be passed to the review script in Step 4.
```

### Fix #2: Implement Real Self-Review in Agent Scripts

**File:** `/opt/fabrik/scripts/traycer_agents_fixed/Free*.sh`

**Replace lines 135-160 with:**
```bash
# MANDATORY: Self-Review (Step 2.5)
if [ $EXIT_CODE -eq 0 ] && [ -n "$CHANGED_FILES" ]; then
    echo "[INFO] Performing Step 2.5: Self-Review..." >&2

    # Call agent again for self-review (separate invocation)
    SELF_REVIEW_PROMPT="You just implemented this task:

$PROMPT

Changed files:
$CHANGED_FILES

Perform structured self-review:
1. Check each requirement against code changes
2. Verify edge cases handled
3. Confirm env vars/DB changes documented
4. Identify potential issues

Output ONLY this format:
SELF-REVIEW COMPLETE:
✓ All spec requirements implemented: [details]
✓ Edge cases handled: [list or N/A]
✓ Env vars documented: [list or N/A]
✓ DB changes documented: [list or N/A]
⚠ Potential issues: [list or None]"

    SELF_REVIEW_OUTPUT=$(timeout 60 kilo run --format text --model kilo/minimax/minimax-m2.1 --variant minimal "$SELF_REVIEW_PROMPT" 2>&1)

    [ "$KILO_DEBUG" = "1" ] && echo "[DEBUG] Self-review output: $SELF_REVIEW_OUTPUT" >&2

    # Run auto-review workflow with real self-review
    python /opt/fabrik/scripts/traycer_agent_review.py \
        --task "$PROMPT" \
        --files $CHANGED_FILES \
        --self-review "$SELF_REVIEW_OUTPUT" \
        --session-id "$SESSION_ID" \
        --output json

    REVIEW_EXIT=$?

    if [ $REVIEW_EXIT -ne 0 ]; then
        EXIT_CODE=$REVIEW_EXIT
    fi
fi
```

### Fix #3: Make Auto-Review Mandatory (Not Optional)

Remove the `if [ "$TRAYCER_AUTO_REVIEW" = "1" ]` condition. Self-review should always run on success.

### Fix #4: Validate Self-Review Content

**File:** `/opt/fabrik/scripts/traycer_agent_review.py`

**Add validation in `main()` function:**
```python
# Validate self-review is not placeholder
if args.self_review == "Agent completed implementation":
    print(json.dumps({
        "error": "Self-review is placeholder. Agent must perform actual self-review.",
        "exit_code": 2
    }), file=sys.stderr)
    return 2

# Check self-review has required sections
required_sections = ["spec requirements", "edge cases", "env vars", "db changes", "potential issues"]
missing = [s for s in required_sections if s.lower() not in args.self_review.lower()]

if missing:
    print(json.dumps({
        "warning": f"Self-review missing sections: {', '.join(missing)}",
        "proceeding": True
    }), file=sys.stderr)
```

---

## Testing Plan

1. **Test Traycer prompt update**
   - Verify agent receives self-review instructions
   - Check agent generates structured report

2. **Test real self-review**
   - Agent codes task
   - Agent performs self-review (separate Kilo call)
   - Verify output contains required sections

3. **Test auto-review workflow**
   - Self-review passed to `traycer_agent_review.py`
   - Steps 3-5 run automatically
   - Verify no placeholder rejection

4. **Test fix loop**
   - Inject issues
   - Verify agent fixes and re-reviews
   - Confirm iterative workflow works

5. **Test Traycer integration**
   - Verify Traycer doesn't call reviewers directly
   - Only coder agent triggers reviews
   - Traycer handles Step 6 verification only

---

## Summary

**Current State:** Workflow is 60% implemented
- ✅ Review script works
- ✅ Agent file isolation works
- ❌ Self-review is placeholder (not real)
- ❌ Traycer prompts missing Step 2.5
- ⚠️ Auto-review is optional (should be mandatory)

**After Fixes:** Workflow will be 100% functional
- ✅ Agent performs real self-review
- ✅ Traycer prompts include Step 2.5
- ✅ Auto-review always runs
- ✅ No Traycer→reviewer calls (only coder→review script)
