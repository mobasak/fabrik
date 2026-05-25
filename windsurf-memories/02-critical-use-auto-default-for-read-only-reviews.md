# CRITICAL: Use --auto default (no flag) for read-only reviews

**Tags:** #droid_exec #safety #review #autonomy

When asking droid exec to REVIEW (not execute):

WRONG (allows edits):
```bash
droid exec --auto low "Review this plan..."
```

CORRECT (read-only):
```bash
droid exec "Review this plan. DO NOT make any changes, only provide feedback."
```

Key rules:
- No --auto flag = read-only by default
- Always add explicit "DO NOT make changes" in prompt for reviews
- Use --auto low/medium/high ONLY when you WANT edits

Reference: AGENTS.md Auto-Run Levels table
