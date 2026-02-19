# Check Existing Code Before Creating New Scripts

**Tags:** #scripts #duplicate #check_first #droid_core

## Before Creating New Scripts (MANDATORY)

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
