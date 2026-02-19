---
auto_execution_mode: 0
description: Fix a reported bug with test-first approach
---

# Bug Fix Workflow

Fix a reported bug using a test-first approach to prevent regressions.

## Steps

1. **Reproduce the bug** — Document exact reproduction steps:
   - What input/action triggers it?
   - What is the expected behavior?
   - What is the actual behavior?

2. **Add failing test** — Write a test that captures the bug:
```bash
# Create test that fails with current code
pytest tests/test_<module>.py::<test_name> -v
# Should FAIL (proves bug exists)
```

3. **Implement fix** — Make the minimal change to fix the bug:
   - Prefer upstream fixes over downstream workarounds
   - Address root cause, not symptoms

// turbo
4. **Verify test passes**:
```bash
pytest tests/test_<module>.py::<test_name> -v
# Should PASS
```

// turbo
5. **Run regression suite** — Ensure no other tests broke:
```bash
pytest tests/ -v --tb=short
```

6. **Update CHANGELOG.md** under `[Unreleased]`:
```markdown
### Fixed - <Brief description> (YYYY-MM-DD)
- Fixed: <what was broken>
- Root cause: <why it was broken>
```

## Verification

- [ ] Failing test added that captures the bug
- [ ] Test now passes with the fix
- [ ] No regressions (full test suite passes)
- [ ] `CHANGELOG.md` updated with fix description
