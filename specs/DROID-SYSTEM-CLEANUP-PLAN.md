# DROID-SYSTEM-CLEANUP-PLAN

**Created:** 2026-01-06
**Status:** ✅ EXECUTED by Gemini-3-pro-preview
**Scope:** Complete cleanup of /opt/fabrik and ~/.factory droid systems
**Reviewed By:** GPT-5.1-codex-max, Claude Sonnet 4.5
**Executed By:** Gemini-3-pro-preview (commit 803c4cb)
**Actual Effort:** ~15 minutes (automated execution)

---

## Executive Summary

This plan addresses all critical, high, and medium severity issues identified by the tri-model review of the Fabrik droid ecosystem.

### AI Review Feedback Incorporated

| Reviewer | Key Additions |
|----------|---------------|
| **GPT-5.1-codex-max** | Phase ordering, model name verification, shared helper pattern |
| **Claude Sonnet 4.5** | Race conditions, file locking, backward compatibility shims |
| **Gemini-3-pro-preview** | Edge cases, testing coverage, migration safety |

### Critical Additions from Review

1. **File locking** for concurrent hook execution
2. **Deduplication** before .droid migration
3. **Backward compatibility shims** for breaking changes
4. **--git-diff flag implementation** before hook update
5. **Shared subprocess helper** to avoid duplication

---

## Phase 0: Prerequisites (NEW - Per AI Review)

### Task 0.1: Create Shared Subprocess Helper
**Files:** `scripts/utils/subprocess_helper.py` (new)
**Risk:** None

| Subtask | Action | Verification |
|---------|--------|--------------|
| 0.1.1 | Create `scripts/utils/` directory | Dir exists |
| 0.1.2 | Create subprocess_helper.py with safe_run() | File created |
| 0.1.3 | Include check=True, timeout, stderr logging | Function works |
| 0.1.4 | Add --dry-run support for destructive ops | Flag works |

### Task 0.2: Backup Current State
**Files:** All affected files
**Risk:** None

| Subtask | Action | Verification |
|---------|--------|--------------|
| 0.2.1 | Create timestamped backup of ~/.factory/ | Backup exists |
| 0.2.2 | Create backup of .droid/ | Backup exists |
| 0.2.3 | Git commit current state | Clean commit |

### Task 0.3: Stop Background Processors
**Risk:** Low

| Subtask | Action | Verification |
|---------|--------|--------------|
| 0.3.1 | Check for running review_processor.py | `pgrep` |
| 0.3.2 | Gracefully stop any processors | No processes |
| 0.3.3 | Add file lock mechanism | Lock file works |

---

## Phase 1: Critical - Review System Consolidation

### Task 1.1: Archive Redundant Review Worker
**Files:** `scripts/review_worker.py`
**Risk:** Low (worker is secondary system)

| Subtask | Action | Verification |
|---------|--------|--------------|
| 1.1.1 | Create `scripts/archive/` directory | `ls scripts/archive/` |
| 1.1.2 | Move `review_worker.py` to archive with `.deprecated` suffix | File moved |
| 1.1.3 | Update any imports/references to review_worker | `grep -r "review_worker"` |
| 1.1.4 | Update documentation referencing review_worker | Doc audit |

### Task 1.2: Consolidate .droid Directories
**Files:** `.droid/` structure
**Risk:** Medium (data migration)

| Subtask | Action | Verification |
|---------|--------|--------------|
| 1.2.1 | Inventory current .droid structure | List all dirs |
| 1.2.2 | Merge `reviews/queue` → `review_queue` | Data preserved |
| 1.2.3 | Merge `reviews/pending` → `review_results` | Data preserved |
| 1.2.4 | Remove empty/obsolete directories | Clean structure |
| 1.2.5 | Update review_processor.py paths if needed | Script works |

### Task 1.3: Unify Hook Configurations
**Files:** `~/.factory/settings.json`, `~/.factory/hooks.json`
**Risk:** High (affects all droid exec sessions)

| Subtask | Action | Verification |
|---------|--------|--------------|
| 1.3.1 | Backup both config files | Backups created |
| 1.3.2 | Compare hook definitions side-by-side | Diff analysis |
| 1.3.3 | Merge all hooks into settings.json | Combined config |
| 1.3.4 | Archive hooks.json with timestamp | `hooks.json.bak.YYYYMMDD` |
| 1.3.5 | Test droid exec session | Hooks fire correctly |

---

## Phase 2: High - Model Registry Fix

### Task 2.1: Dynamic Model Loading
**Files:** `scripts/droid_models.py`, `config/models.yaml`
**Risk:** Medium (affects model selection)

| Subtask | Action | Verification |
|---------|--------|--------------|
| 2.1.1 | Add `load_models_from_yaml()` function | Function exists |
| 2.1.2 | Replace hardcoded `DEFAULT_MODEL` with YAML lookup | Dynamic loading |
| 2.1.3 | Replace hardcoded `MODELS` dict with YAML source | Single source of truth |
| 2.1.4 | Update `FABRIK_TASK_MODELS` to read from YAML | Config-driven |
| 2.1.5 | Add fallback for missing YAML | Graceful degradation |
| 2.1.6 | Run model recommendation tests | Correct models returned |

### Task 2.2: Fix Hardcoded Model in Hooks
**Files:** `~/.factory/hooks/fabrik-code-review.py`
**Risk:** Low

| Subtask | Action | Verification |
|---------|--------|--------------|
| 2.2.1 | Import model lookup function | Import works |
| 2.2.2 | Replace hardcoded model with `get_review_models()` | Dynamic model |
| 2.2.3 | Test code review hook | Correct model used |

---

## Phase 3: High - Error Handling & Subprocess Safety

### Task 3.1: Fix Bare Exceptions
**Files:** `scripts/container_images.py`
**Risk:** Low

| Subtask | Action | Verification |
|---------|--------|--------------|
| 3.1.1 | Line 332: Replace `except:` with `except (ValueError, TypeError, KeyError):` | Specific exception |
| 3.1.2 | Line 489: Replace `except:` with specific exceptions | Specific exception |
| 3.1.3 | Add logging for caught exceptions | Errors visible |

### Task 3.2: Add Subprocess Error Handling
**Files:** `scripts/container_images.py`, `scripts/setup_duplicati_backup.py`
**Risk:** Medium

| Subtask | Action | Verification |
|---------|--------|--------------|
| 3.2.1 | Add `check=True` to subprocess.run() calls | Errors raised |
| 3.2.2 | Add timeout parameters where missing | No hangs |
| 3.2.3 | Add try/except around subprocess calls | Graceful handling |
| 3.2.4 | Add returncode checks for SSH commands | Failures detected |

---

## Phase 4: Medium - Windsurf Hook Fix

### Task 4.1: Fix Silent No-Op in Enforcement
**Files:** `.windsurf/hooks.json`, `scripts/enforcement/validate_conventions.py`
**Risk:** Medium

| Subtask | Action | Verification |
|---------|--------|--------------|
| 4.1.1 | Add `--git-diff` flag to validate_conventions.py | New flag works |
| 4.1.2 | Update hooks.json to use `--git-diff` instead of `${WINDSURF_FILES:-}` | No empty runs |
| 4.1.3 | Add fallback to scan staged files if no git diff | Always has files |
| 4.1.4 | Test enforcement in Windsurf session | Hook runs on edits |

---

## Phase 5: Medium - Code Cleanup

### Task 5.1: Move Example Code
**Files:** `scripts/droid_runner_integration_example.py`
**Risk:** None

| Subtask | Action | Verification |
|---------|--------|--------------|
| 5.1.1 | Create `docs/examples/` if not exists | Dir exists |
| 5.1.2 | Move example file to docs/examples/ | File moved |
| 5.1.3 | Update any references | No broken imports |

### Task 5.2: Clean Empty Directories
**Files:** `~/.factory/` subdirectories
**Risk:** None

| Subtask | Action | Verification |
|---------|--------|--------------|
| 5.2.1 | Identify empty directories in .factory | List found |
| 5.2.2 | Remove or document purpose | Clean structure |

---

## Phase 6: Documentation & Verification

### Task 6.1: Update Documentation
**Files:** `docs/reference/enforcement-system.md`, `AGENTS.md`
**Risk:** None

| Subtask | Action | Verification |
|---------|--------|--------------|
| 6.1.1 | Document review_processor.py as canonical | Docs updated |
| 6.1.2 | Document hook configuration in settings.json | Docs accurate |
| 6.1.3 | Document model loading from YAML | Docs complete |
| 6.1.4 | Update AGENTS.md workflow section | Workflow clear |

### Task 6.2: Final Verification
**Risk:** None

| Subtask | Action | Verification |
|---------|--------|--------------|
| 6.2.1 | Run full enforcement check | All pass |
| 6.2.2 | Test droid exec session | Hooks work |
| 6.2.3 | Test code review trigger | Reviews run |
| 6.2.4 | Run dual-model review on changes | Both models pass |
| 6.2.5 | Commit with proper message | Clean commit |

---

## Risk Assessment

| Phase | Risk Level | Rollback Strategy |
|-------|------------|-------------------|
| 1 | Medium | Restore from archive/backups |
| 2 | Medium | Revert droid_models.py changes |
| 3 | Low | No rollback needed |
| 4 | Medium | Revert hooks.json |
| 5 | None | Move files back |
| 6 | None | N/A |

---

## Success Criteria

1. **Single review system:** Only review_processor.py active
2. **Single hook config:** Only settings.json contains hooks
3. **Dynamic models:** All model lookups use models.yaml
4. **No bare exceptions:** All except blocks are specific
5. **No silent failures:** All subprocess calls checked
6. **Enforcement always runs:** Hook never no-ops
7. **Clean codebase:** No dead code in production paths

---

## Estimated Effort (Revised per AI Review)

| Phase | Tasks | Original | Revised |
|-------|-------|----------|---------|
| 0 | 3 | - | 30 min |
| 1 | 3 | 30 min | 60 min |
| 2 | 2 | 45 min | 75 min |
| 3 | 2 | 30 min | 45 min |
| 4 | 1 | 20 min | 45 min |
| 5 | 2 | 10 min | 20 min |
| 6 | 2 | 30 min | 45 min |
| **Total** | **15** | **~2.5h** | **~5 hours** |

## Execution Order (Per GPT Review)

```
Phase 0 (Prerequisites) → Phase 4 (--git-diff flag) → Phase 2 (Model registry)
→ Phase 1 (Review consolidation) → Phase 3 (Error handling) → Phase 5 (Cleanup)
→ Phase 6 (Docs & verification)
```

---

## Appendix: Files Affected

### Scripts
- `scripts/review_worker.py` → archive
- `scripts/review_processor.py` → verify paths
- `scripts/droid_models.py` → major changes
- `scripts/container_images.py` → exception fixes
- `scripts/setup_duplicati_backup.py` → subprocess fixes
- `scripts/droid_runner_integration_example.py` → move
- `scripts/enforcement/validate_conventions.py` → add flag

### Configuration
- `~/.factory/settings.json` → merge hooks
- `~/.factory/hooks.json` → archive
- `~/.factory/hooks/fabrik-code-review.py` → fix model
- `.windsurf/hooks.json` → fix command
- `config/models.yaml` → source of truth

### Documentation
- `docs/reference/enforcement-system.md`
- `AGENTS.md`
- `docs/README.md`
