# MANDATORY: Run docs_sync.py After Code Changes

**Tags:** #documentation #tasks #phases #enforcement

After completing ANY code change, I MUST run:

```bash
python3 scripts/docs_sync.py
```

This checks and reminds about:
1. **CHANGELOG.md** - Entry for code changes
2. **tasks.md** - Phase status update if implementation work
3. **Phase docs** - Checkboxes if completing tracked tasks
4. **docs/INDEX.md** - Structure map if files added/moved

**Integrated into workflow:**
- `droid-review.sh` automatically runs docs_sync.py after reviews
- Pre-commit enforces CHANGELOG exists

**Sequence:**
```
Code change → droid-review.sh → docs_sync.py → Update all flagged docs → Commit
```

**Violation:** Committing without running docs_sync.py and addressing its output.
