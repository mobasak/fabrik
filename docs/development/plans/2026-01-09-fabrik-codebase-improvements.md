# Fabrik Codebase Improvements Execution Plan

**Created:** 2026-01-09
**Status:** Ready for Review
**Owner:** User

---

## How to Use This Document

### Skipping Items
To skip any item, add `[skip]` after the checkbox:
```
- [ ] [skip] Item description...
```

When executing, I will ignore any item marked with `[skip]`.

### Execution
After you've reviewed and marked skips, say: **"Execute the plan"** and I will proceed with unchecked items only.

---

## Summary

| Priority | Category | Issues | Est. Time |
|----------|----------|--------|-----------|
| P0 | Security | 4 | 2-3 hours |
| P0 | Hardcoded Infrastructure | 5 | 1-2 hours |
| P0 | Platform Compatibility | 3 | 1-2 hours |
| P0 | Logic Bugs | 4 | 2-3 hours |
| P1 | Code Quality | 10 | 4-6 hours |

**Total Estimated Time:** 10-16 hours (can be done incrementally)

---

## Backward Compatibility Guarantee

All fixes will:
1. **Preserve existing function signatures** - No breaking API changes
2. **Use env vars with fallback defaults** - Current behavior preserved if env not set
3. **Add conditional imports** - Not remove platform-specific code
4. **Include regression tests** - Verify existing behavior before/after

---

# PHASE 1: Security Fixes (P0)

## 1.1 Command Injection in WordPress Driver

**Risk:** HIGH - User input executed as shell commands
**File:** `src/fabrik/drivers/wordpress.py`

### Checklist

- [ ] **1.1.1** Add `shlex.quote()` to all user inputs in `_exec()` method
- [ ] **1.1.2** Add `shlex.quote()` to `run()`, `wp_cli()`, and related methods
- [ ] **1.1.3** Add test: `tests/drivers/test_wordpress_injection.py`

**Gate:** `pytest tests/drivers/test_wordpress_injection.py -v`

**Safe Change Pattern:**
```python
# BEFORE (vulnerable)
cmd = f"wp {command} --path={path}"

# AFTER (safe)
import shlex
cmd = f"wp {shlex.quote(command)} --path={shlex.quote(path)}"
```

---

## 1.2 Path Traversal in Orchestrator Validator

**Risk:** HIGH - Attacker can reference files outside templates directory
**File:** `src/fabrik/orchestrator/validator.py`

### Checklist

- [ ] **1.2.1** Add path validation in `validate()` method to ensure resolved path stays within `templates_dir`
- [ ] **1.2.2** Add test: `tests/orchestrator/test_validator_path_traversal.py`

**Gate:** `pytest tests/orchestrator/test_validator_path_traversal.py -v`

**Safe Change Pattern:**
```python
# BEFORE
template_path = self.templates_dir / template

# AFTER
template_path = (self.templates_dir / template).resolve()
if not str(template_path).startswith(str(self.templates_dir.resolve())):
    raise ValueError(f"Invalid template path: {template}")
```

---

## 1.3 SSRF Protection in Orchestrator Validator

**Risk:** MEDIUM - Domains resolving to internal IPs not blocked
**File:** `src/fabrik/orchestrator/validator.py`

### Checklist

- [ ] **1.3.1** Add DNS resolution check in `validate_domain_security()` to block private IPs
- [ ] **1.3.2** Add test for internal IP detection

**Gate:** `pytest tests/orchestrator/test_validator_ssrf.py -v`

---

## 1.4 Shell Escaping in WordPress Analytics

**Risk:** MEDIUM - Fragile manual escaping
**File:** `src/fabrik/wordpress/analytics.py`

### Checklist

- [ ] **1.4.1** Replace `.replace("'", "'\\''")` with `shlex.quote()`
- [ ] **1.4.2** Verify WP-CLI commands still work after change

**Gate:** Manual test with special characters in input

---

# PHASE 2: Hardcoded Infrastructure (P0)

## 2.1 Replace Hardcoded VPS IP (172.93.160.197)

**Files affected:** 5 files
**Impact:** Non-breaking - adds env var with current value as default

### Checklist

- [ ] **2.1.1** `src/fabrik/cli.py` - Replace with `os.getenv('VPS_IP', '172.93.160.197')`
- [ ] **2.1.2** `src/fabrik/provisioner.py` - Replace with env var
- [ ] **2.1.3** `src/fabrik/verify.py` - Replace with env var
- [ ] **2.1.4** `src/fabrik/wordpress/deployer.py` - Replace with env var
- [ ] **2.1.5** Add `VPS_IP` to `.env.example` with documentation

**Gate:** `grep -r "172.93.160.197" src/ --include="*.py" | wc -l` should return 0

---

## 2.2 Replace Hardcoded Namecheap URL

**File:** `src/fabrik/config.py`

### Checklist

- [ ] **2.2.1** Change default to use `NAMECHEAP_API_URL` env var with current URL as fallback
- [ ] **2.2.2** Add to `.env.example`

**Gate:** `grep "namecheap.vps1.ocoron.com" src/ --include="*.py" -r` shows only default fallback

---

## 2.3 Replace Hardcoded /opt/fabrik Paths

**Files affected:** 15+ files
**Impact:** Non-breaking - uses FABRIK_ROOT env var

### Checklist

- [ ] **2.3.1** Create `src/fabrik/paths.py` with:
  ```python
  FABRIK_ROOT = Path(os.getenv('FABRIK_ROOT', '/opt/fabrik'))
  ```
- [ ] **2.3.2** Update `scripts/docs_sync.py` to use FABRIK_ROOT
- [ ] **2.3.3** Update `scripts/docs_updater.py` to use FABRIK_ROOT
- [ ] **2.3.4** Update `scripts/droid_core.py` to use FABRIK_ROOT
- [ ] **2.3.5** Update `scripts/enforcement/check_changelog.py` to use FABRIK_ROOT
- [ ] **2.3.6** Update remaining scripts (batch update)

**Gate:** `grep -r '"/opt/fabrik"' scripts/ src/ --include="*.py" | grep -v FABRIK_ROOT | wc -l` should return 0

---

# PHASE 3: Platform Compatibility (P0)

## 3.1 Make fcntl Imports Conditional

**Risk:** Scripts crash on Windows
**Files:** `scripts/docs_updater.py`, `scripts/utils/subprocess_helper.py`

### Checklist

- [ ] **3.1.1** Wrap fcntl import in try/except with fallback
  ```python
  try:
      import fcntl
      HAS_FCNTL = True
  except ImportError:
      HAS_FCNTL = False
  ```
- [ ] **3.1.2** Add Windows-compatible fallback for file locking (use `msvcrt` or skip locking)
- [ ] **3.1.3** Update `scripts/utils/subprocess_helper.py` same pattern

**Gate:** `python -c "import scripts.docs_updater"` works (no ImportError)

---

## 3.2 Fix Sync httpx in Async Context

**Risk:** Blocks event loop
**File:** `src/fabrik/drivers/cloudflare.py`

### Checklist

- [ ] **3.2.1** Add `httpx.AsyncClient` alternative methods
- [ ] **3.2.2** Keep sync methods for CLI usage (backward compat)
- [ ] **3.2.3** Document which to use in async vs sync contexts

**Gate:** Existing tests pass

---

## 3.3 Fix subprocess_helper Shell Handling

**Risk:** Commands with arguments fail
**File:** `scripts/utils/subprocess_helper.py`

### Checklist

- [ ] **3.3.1** Detect string commands and set `shell=True` OR split into list
- [ ] **3.3.2** Add warning log for shell=True usage
- [ ] **3.3.3** Add test for command with arguments

**Gate:** `python -c "from scripts.utils.subprocess_helper import safe_run; safe_run('echo hello world')"`

---

# PHASE 4: Logic Bugs (P0)

## 4.1 Fix Compose Linter Variable Detection

**Risk:** Variables incorrectly reported as resolved
**File:** `src/fabrik/compose_linter.py`

### Checklist

- [ ] **4.1.1** Change set subtraction logic to track occurrences, not just names
- [ ] **4.1.2** Add support for `$VAR` syntax (without braces)
- [ ] **4.1.3** Fix regex to allow lowercase variables
- [ ] **4.1.4** Add test cases for each bug

**Gate:** `pytest tests/test_compose_linter.py -v`

---

## 4.2 Fix Orchestrator Deployer UUID Handling

**Risk:** State corruption from 'unknown' UUID
**File:** `src/fabrik/orchestrator/deployer.py`

### Checklist

- [ ] **4.2.1** Raise exception instead of returning 'unknown' when UUID missing
- [ ] **4.2.2** Add proper error message for debugging
- [ ] **4.2.3** Update callers to handle exception

**Gate:** Existing orchestrator tests pass

---

## 4.3 Fix Deploy.py Server Selection

**Risk:** Deploys to wrong server
**File:** `src/fabrik/deploy.py`

### Checklist

- [ ] **4.3.1** Raise error if `COOLIFY_SERVER_UUID` not set instead of using servers[0]
- [ ] **4.3.2** Add clear error message listing available servers

**Gate:** Manual test with unset COOLIFY_SERVER_UUID shows error

---

## 4.4 Fix droid_models.py Duplicate Definition

**Risk:** Maintenance confusion
**File:** `scripts/droid_models.py`

### Checklist

- [ ] **4.4.1** Remove duplicate `ModelInfo` dataclass (keep first occurrence)
- [ ] **4.4.2** Fix reference to archived `droid_tasks.py`

**Gate:** `python -c "import scripts.droid_models"` works without warnings

---

# PHASE 5: Code Quality (P1)

## 5.1 Add Retry Logic to Drivers

### Checklist

- [ ] **5.1.1** Add retry decorator to `src/fabrik/drivers/cloudflare.py`
- [ ] **5.1.2** Add retry decorator to `src/fabrik/drivers/coolify.py`
- [ ] **5.1.3** Handle rate limits (HTTP 429)

---

## 5.2 Add Missing Error Handling

### Checklist

- [ ] **5.2.1** `src/fabrik/wordpress/content.py` - Add try/except for Anthropic API
- [ ] **5.2.2** `src/fabrik/deploy.py` - Add try/except for network requests
- [ ] **5.2.3** `src/fabrik/orchestrator/rollback.py` - Add timeout to API calls

---

## 5.3 Consolidate Subprocess Logic

### Checklist

- [ ] **5.3.1** Identify duplicate streaming logic in droid_core.py, docs_updater.py, review_processor.py
- [ ] **5.3.2** Extract to `scripts/utils/subprocess_helper.py`
- [ ] **5.3.3** Update all callers

---

## 5.4 Fix WordPress Module Issues

### Checklist

- [ ] **5.4.1** `wordpress_api.py` - Fix URL construction (add trailing slash handling)
- [ ] **5.4.2** `wordpress_api.py` - Add streaming for large file uploads
- [ ] **5.4.3** `deployer.py` - Don't suppress exceptions in theme installation

---

## 5.5 Add Missing Tests

### Checklist

- [ ] **5.5.1** `tests/wordpress/` - Create test suite for deployer
- [ ] **5.5.2** `tests/test_provisioner.py` - Add provisioner tests
- [ ] **5.5.3** `tests/test_config.py` - Add config validation tests

---

# Execution Instructions

## Quick Start

1. **Review this document** - Mark items with `[skip]` as needed
2. **Say "Execute the plan"** - I will process only unmarked items
3. **After each phase** - I'll run the gate and show results
4. **Commit per phase** - Keep changes atomic and reviewable

## Rollback Plan

If any change breaks functionality:
1. `git stash` current changes
2. Identify the breaking change
3. Revert that specific edit
4. Continue with remaining items

## Gate Commands Summary

```bash
# Phase 1: Security
pytest tests/drivers/test_wordpress_injection.py tests/orchestrator/ -v

# Phase 2: Hardcoded values
grep -r "172.93.160.197" src/ --include="*.py" | wc -l  # Should be 0

# Phase 3: Platform
python -c "import scripts.docs_updater; import scripts.utils.subprocess_helper"

# Phase 4: Logic bugs
pytest tests/test_compose_linter.py -v

# Full regression
pytest tests/ -v
```

---

**Document Location:** `docs/development/plans/2026-01-09-fabrik-codebase-improvements.md`
