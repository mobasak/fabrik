# Droid Scripts Consolidation Plan

**Status:** ✅ COMPLETE (2026-01-08)

**Goal:** Consolidate task execution scripts while preserving CI-critical validation.

## Summary

| Task | Status |
|------|--------|
| Create `droid_core.py` (merge droid_tasks + droid_runner) | ✅ Done |
| Delete `droid_tasks.py` and `droid_runner.py` | ✅ Done |
| Verify no broken imports | ✅ Done |
| Update CHANGELOG | ✅ Done |
| Queue merge (review_processor + docs_updater) | ❌ Cancelled (by design) |

**Result:**
- `droid_core.py`: 1316 lines (vs 1507 combined = **13% reduction**)
- All 11 task types working
- run/status/list commands working

**Cancelled (by design):**
- `droid_queue.py` merge — `docs_updater.py` has CI-critical `--check`/`--sync` validation; merging would increase blast radius

---

## Final Architecture

```
scripts/
├── droid_core.py       (1316 lines) ← NEW (replaces droid_tasks + droid_runner)
├── review_processor.py (770 lines)  ← KEPT (async reviews)
├── docs_updater.py     (878 lines)  ← KEPT (CI-critical validation)
├── docs_sync.py        (191 lines)  ← KEPT (check-only)
├── droid_models.py     (1129 lines) ← KEPT (model registry)
├── droid-review.sh     (102 lines)  ← KEPT (shell wrapper)
└── .archive/2026-01-08-pre-consolidation/  ← BACKUP
```

---

## Backup Location

```
scripts/.archive/2026-01-08-pre-consolidation/
├── docs_sync.py          (6,240 bytes)
├── docs_updater.py       (28,806 bytes)
├── droid_models.py       (37,295 bytes)
├── droid_model_updater.py (13,604 bytes)
├── droid-review.sh       (2,689 bytes)
├── droid_runner.py       (18,487 bytes)  ← DELETED from scripts/
├── droid_tasks.py        (32,550 bytes)  ← DELETED from scripts/
└── review_processor.py   (25,703 bytes)
```

---

## Before/After

```
BEFORE (6 scripts, 4475 lines):          AFTER (5 scripts, 4386 lines):
├── droid_tasks.py    (964)  ─┐          ├── droid_core.py    (1316) ← MERGED
├── droid_runner.py   (543)  ─┘          ├── review_processor.py (770) ← KEPT
├── review_processor.py (770)            ├── docs_updater.py    (878) ← KEPT
├── docs_updater.py    (878)             ├── docs_sync.py       (191) ← KEPT
├── docs_sync.py       (191)             ├── droid_models.py   (1129) ← KEPT
└── droid_models.py   (1129)             └── droid-review.sh    (102) ← KEPT
```

---

## Execution Steps (Final Status)

### Step 1: Create droid_core.py ✅ DONE

- Merged `droid_tasks.py` + `droid_runner.py`
- All 11 task types working
- run/status/list commands working
- ProcessMonitor integration preserved

### Step 2: Create droid_queue.py ❌ CANCELLED

- **Reason:** `docs_updater.py` has CI-critical `--check`/`--sync` validation
- Merging would increase blast radius of bugs
- Queue scripts kept separate (different concerns)

### Step 3: Update droid-review.sh ⏭️ SKIPPED

- Not needed since queue scripts unchanged

### Step 4: Update imports ✅ DONE

- Verified no broken imports exist

### Step 5: Delete old scripts ✅ DONE

- `droid_tasks.py` deleted
- `droid_runner.py` deleted
- Backup preserved at `scripts/.archive/2026-01-08-pre-consolidation/`

### Step 6: Update documentation ✅ DONE

- CHANGELOG updated
- This plan file updated

### Step 7: Backward-compatible aliases ⏭️ SKIPPED

- Not needed since queue scripts unchanged

---

## Rollback Plan

```bash
# If anything breaks:
cp scripts/.archive/2026-01-08-pre-consolidation/droid_tasks.py scripts/
cp scripts/.archive/2026-01-08-pre-consolidation/droid_runner.py scripts/
```

---

## Success Criteria (Final)

- [x] `droid_core.py` created and working
- [x] All 11 task types work: `python scripts/droid_core.py <type> "prompt"`
- [x] run/status/list commands work
- [x] Old scripts deleted (droid_tasks.py, droid_runner.py)
- [x] Backup preserved
- [x] CHANGELOG updated
- [x] No broken imports

**Owner:** Cascade
**Completed:** 2026-01-08
