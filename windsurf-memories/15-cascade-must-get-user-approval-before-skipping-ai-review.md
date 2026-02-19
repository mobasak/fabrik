# Cascade Must Get User Approval Before Skipping AI Review

**Tags:** #enforcement #ai_review #workflow #mandatory

After implementing any code change, I MUST:

1. Run `./scripts/droid-review.sh` on changed files
2. Implement the ONE test recommended in Section E of the review output
3. Run `pytest tests/ -v` to verify the test passes

**Sequence:**
```
Code change → droid-review.sh → Implement one-test → pytest → Commit
```

**The one-test must cover:**
- The highest-risk code path identified in review
- Given / When / Then structure
- Clear assertion of expected behavior

**Violation:** Committing code changes without the recommended test.

**Note:** For Traycer-managed tasks, Traycer verifier is the primary review surface. This droid-based review is fallback for non-Traycer tasks.
