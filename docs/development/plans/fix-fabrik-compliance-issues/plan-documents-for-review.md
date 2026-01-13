## Plan Documents for Review

### Master Index
`@/opt/fabrik/docs/development/plans/2026-01-09-fixes-00-index.md`

### Module Plans (in execution order)

| # | Plan |
|---|------|
| 1 | `@/opt/fabrik/docs/development/plans/2026-01-09-fixes-01-core.md` |
| 2 | `@/opt/fabrik/docs/development/plans/2026-01-09-fixes-02-drivers.md` |
| 3 | `@/opt/fabrik/docs/development/plans/2026-01-09-fixes-03-orchestrator.md` |
| 4 | `@/opt/fabrik/docs/development/plans/2026-01-09-fixes-04-scripts.md` |
| 5 | `@/opt/fabrik/docs/development/plans/2026-01-09-fixes-05-enforcement.md` |
| 6 | `@/opt/fabrik/docs/development/plans/2026-01-09-fixes-06-wordpress.md` |

---

After reviewing, mark items with `[skip]` and say **"Execute"** when ready.

Let me create a comprehensive update for the remaining sections and then regenerate all plan files with proper HOW TO FIX sections.



## ✅ All 6 Plan Documents Updated with HOW TO FIX Sections

Each plan now includes:

### 1. Safety Rules Header
- Before/after each fix checklist
- Fix patterns table by issue type
- Verification commands

### 2. HOW TO FIX for Every Item
Each issue now has a specific fix strategy with:
- Code example (where applicable)
- **SAFE:** explanation of why it won't break existing code

### Sample from Drivers Plan

```markdown
- [ ] **1.** Synchronous httpx.Client blocks event loop...

  **HOW TO FIX:**
  ```python
  # Add async alternative, keep sync for backward compat
  async def _async_request(...):
      async with httpx.AsyncClient() as client:
          ...
  ```
  **SAFE:** New async method, existing sync code unchanged.

- [ ] **8.** `https://api.cloudflare.com/client/v4 (API Base URL)`

  **HOW TO FIX:** Move to env var with current URL as default
```

---

### Updated Plan Files

| File | Items | With HOW TO FIX |
|------|-------|-----------------|
| `@/opt/fabrik/docs/development/plans/2026-01-09-fixes-01-core.md` | 121 | ✅ |
| `@/opt/fabrik/docs/development/plans/2026-01-09-fixes-02-drivers.md` | 62 | ✅ |
| `@/opt/fabrik/docs/development/plans/2026-01-09-fixes-03-orchestrator.md` | 59 | ✅ |
| `@/opt/fabrik/docs/development/plans/2026-01-09-fixes-04-scripts.md` | 154 | ✅ |
| `@/opt/fabrik/docs/development/plans/2026-01-09-fixes-05-enforcement.md` | 148 | ✅ |
| `@/opt/fabrik/docs/development/plans/2026-01-09-fixes-06-wordpress.md` | 215 | ✅ |

**Index:** `@/opt/fabrik/docs/development/plans/2026-01-09-fixes-00-index.md`

---

### My Execution Protocol

When you say **"Execute"**, for each item I will:

1. **Read** the current file to understand context
2. **Apply** the fix pattern shown
3. **Verify** with `python3 -m py_compile <file>`
4. **Test** with `pytest tests/ -v` (if tests exist)
5. **Report** status before moving to next item
6. **Stop** if any verification fails
