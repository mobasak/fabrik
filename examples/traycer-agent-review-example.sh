#!/bin/bash
# Example: Traycer CLI Agent Auto-Review Workflow
# This demonstrates how a Traycer CLI agent would invoke the auto-review workflow

# Simulated scenario: Agent just implemented JWT authentication

# 1. Agent identifies what it changed
TASK="Implement JWT authentication with token expiration"
CHANGED_FILES=(
    "src/fabrik/auth.py"
    "tests/test_auth.py"
)
SESSION_ID="ses_traycer_agent_12345"

# 2. Agent performs self-review
SELF_REVIEW="SELF-REVIEW COMPLETE:
✓ All spec requirements implemented: Yes
✓ Edge cases handled: Token expiration, invalid tokens, missing tokens, malformed tokens
✓ Env vars documented: JWT_SECRET, JWT_EXPIRY added to .env.example
✓ DB changes documented: N/A (stateless JWT)
⚠ Potential issues: None identified

Implementation details:
- Used PyJWT library for token generation/validation
- Added middleware for authentication
- Created helper functions for token creation and validation
- Added comprehensive test coverage (95%)"

# 3. Run auto-review workflow
echo "================================================"
echo "TRAYCER AGENT AUTO-REVIEW WORKFLOW"
echo "================================================"
echo ""
echo "Task: $TASK"
echo "Session: $SESSION_ID"
echo "Files: ${CHANGED_FILES[*]}"
echo ""
echo "Running workflow..."
echo ""

python /opt/fabrik/scripts/traycer_agent_review.py \
    --task "$TASK" \
    --files "${CHANGED_FILES[@]}" \
    --self-review "$SELF_REVIEW" \
    --session-id "$SESSION_ID" \
    --output text

EXIT_CODE=$?

echo ""
echo "================================================"
echo "Workflow completed with exit code: $EXIT_CODE"
echo ""

if [ $EXIT_CODE -eq 0 ]; then
    echo "✅ SUCCESS: Ready for Traycer verification"
    echo "Next: Traycer AI will verify and commit"
elif [ $EXIT_CODE -eq 1 ]; then
    echo "❌ FAILED: Issues found during review"
    echo "Next: Fix issues and re-run workflow"
elif [ $EXIT_CODE -eq 2 ]; then
    echo "⚠️  ERROR: Script error or invalid input"
    echo "Next: Check error message and fix configuration"
fi

exit $EXIT_CODE
