# MANDATORY: Use droid-review.sh for ALL Code Reviews

**Tags:** #droid #review #prompt #templates #code_review

When reviewing code via droid exec, ALWAYS use the wrapper script:

```bash
# Code review (uses adaptive meta-prompt automatically)
./scripts/droid-review.sh src/path/to/file.py

# Plan review
./scripts/droid-review.sh --plan docs/development/plans/my-plan.md

# Multiple files
./scripts/droid-review.sh src/file1.py src/file2.py

# Specific model
./scripts/droid-review.sh --model gpt-5.1-codex-max src/file.py
```

**DO NOT** use raw `droid exec "Review..."` without the meta-prompt.

The wrapper:
- Loads `/opt/fabrik/templates/droid/review-meta-prompt.md` automatically
- Selects recommended model from config/models.yaml
- Runs read-only (no --auto flag)
- Produces structured P0/P1 output

**Violation:** Running `droid exec "Review..."` without the adaptive meta-prompt.
