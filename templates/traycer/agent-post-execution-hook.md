# Traycer Agent Post-Execution Hook Template

**Purpose:** This template is appended to Traycer CLI agent prompts to enforce auto-review workflow after coding.

---

## Instructions for Agent

After you complete your implementation task, you MUST run the auto-review workflow before stopping.

### Step 1: Self-Review (Step 2.5)

Before running any gates, perform a self-review:

1. Re-read the task/spec completely
2. Check each requirement against your code changes
3. Verify edge cases are handled
4. Confirm environment variables documented
5. Confirm database changes documented

Generate a structured self-review report:

```
SELF-REVIEW COMPLETE:
✓ All spec requirements implemented: [Yes/No]
✓ Edge cases handled: [list or "N/A"]
✓ Env vars documented: [list or "N/A"]
✓ DB changes documented: [list or "N/A"]
⚠ Potential issues: [list or "None identified"]
```

### Step 2: Run Auto-Review Workflow

The review script internally follows the **staged-first / verify-mode workflow**:

**Internal Flow:**
1. **Deterministic gate** - runs `final_gate.py` (pre-Kilo)
2. **Staged initial review** - full SPEC verification on commit candidate
3. **Scoped continuation** - maintains session across iterations
4. **Verify-mode follow-up loops** - lighter checks focused on fixes
5. **Persisted open issues** - reused across iterations
6. **Post-Kilo gate** - runs `final_gate.py` again

Execute the following command:

```bash
# Set review ID (use Traycer-provided or generate stable recognizable ID)
REVIEW_ID="${TRAYCER_REVIEW_ID:-feat-$(date +%Y%m%d)-<slug>}"

python /opt/fabrik/scripts/traycer_agent_review.py \
    --task "Your task description here" \
    --files <file1> <file2> ... \
    --self-review "Your self-review report above" \
    --tracked-review-id "$REVIEW_ID" \
    --session-id "${SESSION_ID}" \
    --output json
```

**Where:**
- `--task`: One-line description of what you implemented
- `--files`: Space-separated list of files you modified
- `--self-review`: The self-review report you generated
- `--tracked-review-id`: Stable review cycle ID (required for scoped sessions)
- `--session-id`: Your session ID (environment variable or generated)
- `--output`: Use `json` for programmatic parsing or `text` for human-readable

**Session Scoping (NEW - 2026-03-17):**
- Sessions scoped by: `project_root + git_branch + tracked_review_id`
- `--tracked-review-id` **REQUIRED** with `--session continue`
- Prevents cross-repo/branch session pollution
- Issue state persisted to `.droid/reviews/<tracked_review_id>_issues.json`
- Open issues reused across iterations
- Auto-close is conservative: only for staged, single-batch, non-verify, auto-fix runs

### Step 3: Interpret Results

The script returns JSON with structure:

```json
{
  "workflow": "traycer_agent_auto_review",
  "coder_session_id": "ses_xyz",
  "task": "Implement feature X",
  "files": ["src/file1.py", "src/file2.py"],
  "steps": {
    "self_review": {
      "step": "2.5",
      "findings": "...",
      "status": "COMPLETE"
    },
    "pre_kilo": {
      "step": "3",
      "passed": true,
      "total_checks": 24,
      "status": "PASS"
    },
    "kilo_review": {
      "step": "4",
      "reviewer_session_id": "ses_abc",
      "verdict": "PASS",
      "summary": "No issues found",
      "issues_count": 0,
      "cost": 0.15,
      "status": "PASS"
    },
    "post_kilo": {
      "step": "5",
      "passed": true,
      "total_checks": 24,
      "status": "PASS"
    }
  },
  "final_status": "PASSED",
  "exit_code": 0,
  "next_action": "STOP - Ready for Traycer verification"
}
```

### Step 4: Handle Results

**If final_status = "PASSED":**
- ✅ All gates passed
- ✅ Kilo review passed
- STOP and report: "Implementation complete. Ready for Traycer verification."
- **DO NOT COMMIT** - Traycer AI will verify and commit

**If final_status = "FAILED_PRE_KILO":**
- ❌ Deterministic checks failed
- Fix the issues reported in `steps.pre_kilo.output`
- Re-run the workflow
- Repeat until PASSED

**If final_status = "FAILED_KILO_REVIEW":**
- ❌ Kilo reviewer found issues
- Review `steps.kilo_review.issues` array
- Fix ALL issues (BLOCKER, MAJOR, MINOR)
- Re-run the workflow
- Repeat until PASSED

**If final_status = "FAILED_POST_KILO":**
- ❌ Your fixes broke deterministic checks
- Review `steps.post_kilo.output`
- Fix the regressions
- Re-run the workflow
- Repeat until PASSED

### Step 5: Report to User

Always provide a summary to the user:

```
Implementation Status: [COMPLETE | NEEDS_FIXES]

Self-Review:
  <Your self-review findings>

Review Workflow:
  Step 3 - Pre-Kilo Gate: [PASS | FAIL] (X/Y checks)
  Step 4 - Kilo Review: [PASS | FAIL] (Y issues found)
  Step 5 - Post-Kilo Gate: [PASS | FAIL] (X/Y checks)

Final Status: [PASSED | FAILED]
Next Action: [Ready for Traycer verification | Fix issues and re-run]

[If failed, list the issues to fix]
```

---

## Example Usage in Traycer CLI Agent

```python
# After implementing the feature
changed_files = ["src/auth.py", "tests/test_auth.py"]
task_description = "Implement JWT authentication"

# Generate self-review
self_review = """
SELF-REVIEW COMPLETE:
✓ All spec requirements implemented: Yes
✓ Edge cases handled: Token expiration, invalid tokens, missing tokens
✓ Env vars documented: JWT_SECRET, JWT_EXPIRY in .env.example
✓ DB changes documented: N/A
⚠ Potential issues: None identified
"""

# Run auto-review workflow
import subprocess
import json

result = subprocess.run([
    "python",
    "/opt/fabrik/scripts/traycer_agent_review.py",
    "--task", task_description,
    "--files", *changed_files,
    "--self-review", self_review,
    "--session-id", session_id,
    "--output", "json"
], capture_output=True, text=True)

review_data = json.loads(result.stdout)

if review_data["final_status"] == "PASSED":
    print("✅ Implementation complete. Ready for Traycer verification.")
    # Stop here - DO NOT COMMIT
elif review_data["final_status"].startswith("FAILED"):
    print(f"❌ Review failed: {review_data['final_status']}")
    # Extract issues and fix them
    if "kilo_review" in review_data["steps"]:
        for issue in review_data["steps"]["kilo_review"].get("issues", []):
            print(f"  - {issue['severity']}: {issue['file']} - {issue['why']}")
    # Re-run workflow after fixes
```

---

## Integration Points

**Where to add this template:**

1. **Traycer CLI Agent System Prompt:**
   Add as final instruction block:
   ```
   After completing implementation, you MUST run the auto-review workflow
   following the template in /opt/fabrik/templates/traycer/agent-post-execution-hook.md
   ```

2. **Traycer Prompt Templates:**
   Copy this file to `~/.traycer/prompt-templates/fabrik-auto-review.md`
   Reference in agent prompts via:
   ```
   {% include 'fabrik-auto-review.md' %}
   ```

3. **Post-Execution Hook:**
   Configure Traycer to automatically run this script after agent execution:
   ```yaml
   # In Traycer config
   post_execution_hook:
     script: /opt/fabrik/scripts/traycer_agent_review.py
     args:
       - --task
       - "{{ task }}"
       - --files
       - "{{ changed_files }}"
       - --self-review
       - "{{ self_review }}"
       - --session-id
       - "{{ session_id }}"
   ```

---

## Benefits

1. **Automated Quality:** Every Traycer agent output is reviewed automatically
2. **Separate Reviewer:** Kilo reviewer runs as separate agent (unbiased)
3. **Session Isolation:** Coder and reviewer maintain separate session IDs
4. **No False Commits:** Agent stops before commit, Traycer AI verifies
5. **Consistent Workflow:** Same 9-step workflow for all agents
6. **Cost Tracking:** Review costs tracked separately from coding

---

## Cost Estimate

Typical auto-review workflow cost:
- Pre-Kilo Gate: FREE (deterministic)
- Kilo Review: ~$0.10-0.50 (depending on file size)
- Post-Kilo Gate: FREE (deterministic)

**Total:** ~$0.10-0.50 per agent execution
