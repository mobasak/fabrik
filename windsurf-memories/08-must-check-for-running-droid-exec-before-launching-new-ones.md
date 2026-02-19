# MUST check for running droid exec before launching new ones

**Tags:** #droid_exec #process_monitor #safety #workflow

Before running ANY droid exec command manually:

1. **Check if a wrapper script exists:**
   - `scripts/docs_updater.py --file <path>` - for doc updates
   - `scripts/droid-review.sh <files>` - for code review
   - `scripts/review_processor.py` - for background reviews
   - `scripts/droid_core.py` - for task execution (replaces droid_runner.py + droid_tasks.py)

2. **If wrapper exists, USE IT** - don't run `droid exec` directly

3. **Required flags for file writes:**
   - `--auto medium` minimum (not `--auto low`)
   - `-o json` for structured output
   - Specific prompt with "Write changes DIRECTLY to files"

4. **Never invent new droid exec calls** when working scripts exist

**Violation:** Running `droid exec` manually instead of using wrapper scripts.
