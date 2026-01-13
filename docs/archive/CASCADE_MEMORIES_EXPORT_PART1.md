# Cascade Memories Export - Part 1 of 3

**Exported:** 2026-01-13

---

# MEMORY: Before Creating New Scripts (MANDATORY)

Before writing ANY new script, I MUST:
1. `grep_search` for similar functionality in scripts/
2. Check if droid_core.py, droid-review.sh, or existing wrappers handle it
3. If existing code can be extended → extend it, don't create new

**Violation:** Creating duplicate functionality.

**Key existing infrastructure:**
- `scripts/droid_core.py` - All droid exec task types with ProcessMonitor
- `scripts/droid-review.sh` - Code review wrapper
- `scripts/docs_updater.py` - Documentation updates
- `scripts/review_processor.py` - Background reviews

**Rule location:** `.windsurf/rules/00-critical.md`

---

# MEMORY: Factory CLI Settings

Factory CLI settings file: `/home/ozgur/.factory/settings.json`

Key settings for full automation:
- Model: claude-sonnet-4-5-20250929
- Reasoning: high (specModeReasoningEffort: high)
- Autonomy: auto-high
- Hooks: enabled
- Skills: enabled
- Cloud sync: enabled
- Custom droids: enabled
- Co-authored commits: enabled
- Background processes: allowed

Command allowlist includes: git ops, package managers, python/node, docker, pytest, safe rm paths (/opt/*, ~/.cache/*, etc.)
Command denylist blocks: system destruction (rm -rf /, /etc, /usr, /home), mkfs, dd, shutdown, fork bombs, chmod hazards.

---

# MEMORY: Before Launching droid exec

Before launching ANY droid exec command:

1. Check for running instances:
```bash
pgrep -f "droid exec" || echo "No running instances"
```

2. If instances are running, either:
   - Wait for them to complete
   - Ask user if they want to proceed
   - Use ProcessMonitor to check if stuck

3. For parallel droid calls, limit to 2-3 max to avoid resource contention

Reference: /opt/fabrik/scripts/process_monitor.py

---

# MEMORY: After Code Changes

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

---

# MEMORY: Code Review Wrapper

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
