# Cascade Backup Guide

**Last Updated:** 2026-01-13

This guide documents how Windsurf Cascade configuration is backed up for migration to new machines.

---

## Backup Architecture

| Item | Location | Backup Method | Automation |
|------|----------|---------------|------------|
| **Extensions** | Windows: `~/.windsurf/extensions/` | `sync_extensions.sh` → `EXTENSIONS.md` | ✅ Fully automated (pre-commit) |
| **Workspace Rules** | `.windsurf/rules/*.md` | Git | ✅ Fully automated |
| **Memories** | Codeium cloud | Cascade export → `CASCADE_MEMORIES_GLOBAL_RULES_BACKUP.md` | ⚠️ Manual trigger |
| **Global Rules** | Codeium cloud | Cascade export → `CASCADE_MEMORIES_GLOBAL_RULES_BACKUP.md` | ⚠️ Manual trigger |

---

## Why Manual for Memories & Global Rules?

Memories and global rules are stored in **Codeium's cloud**, not in local files. They're only accessible within a live Cascade conversation.

- `droid exec` from shell: ❌ Cannot access memories/rules
- Cascade in conversation: ✅ Has full access

The pre-commit hook checks backup freshness and reminds you when it's stale (>7 days).

---

## Backup Files

### 1. Extensions (`docs/reference/EXTENSIONS.md`)
- **Updated:** Automatically on every commit
- **Contains:** List of installed extensions with install commands
- **Restore:** Run the install commands on new machine

### 2. Workspace Rules (`.windsurf/rules/`)
- **Updated:** Automatically via git
- **Contains:** Project-specific Cascade rules
- **Restore:** Automatic on `git clone`

### 3. Memories & Global Rules (`docs/reference/CASCADE_MEMORIES_GLOBAL_RULES_BACKUP.md`)
- **Updated:** When you ask Cascade to update it
- **Contains:** All memories and global rules with full content
- **Restore:** Ask Cascade to create memories from the file

---

## How to Update Backups

### Extensions (Automatic)
```bash
# Happens automatically on commit, or manually:
./scripts/sync_extensions.sh
```

### Memories & Global Rules (Manual)
When the pre-commit hook warns about stale backup, ask Cascade:
```
Update the cascade backup file with current memories and global rules
```

Or periodically (weekly recommended):
```
Export all memories and global rules to CASCADE_MEMORIES_GLOBAL_RULES_BACKUP.md
```

---

## Restoring on New Machine

### 1. Clone the Repository
```bash
git clone <repo-url>
cd <project>
```
This restores:
- ✅ Workspace rules (`.windsurf/rules/`)
- ✅ Backup files for reference

### 2. Install Extensions
```bash
# Run all install commands from EXTENSIONS.md:
cat docs/reference/EXTENSIONS.md | grep "windsurf --install-extension" | bash
```

### 3. Restore Memories
Open Cascade and say:
```
Please create memories from each section in docs/reference/CASCADE_MEMORIES_GLOBAL_RULES_BACKUP.md under "PART 1: MEMORIES"
```

### 4. Restore Global Rules
1. Open Windsurf Settings > Cascade > Rules
2. Add each rule from PART 2 of `CASCADE_MEMORIES_GLOBAL_RULES_BACKUP.md`

---

## Pre-commit Hooks

Two hooks manage backups:

### sync-extensions
- **Runs:** Every commit
- **Does:** Exports extensions to `EXTENSIONS.md`
- **Updates:** Only when extensions change

### sync-cascade-backup
- **Runs:** Every commit
- **Does:** Checks if backup is >7 days old
- **Output:** Warning message if stale, reminder to ask Cascade

---

## Troubleshooting

### Hook says "CASCADE BACKUP MISSING"
Ask Cascade to create the initial backup:
```
Export all memories and global rules to CASCADE_MEMORIES_GLOBAL_RULES_BACKUP.md
```

### Hook says "CASCADE BACKUP STALE"
Ask Cascade to update the backup:
```
Update the cascade backup file with current memories and global rules
```

### Extensions not syncing
Check if `windsurf` CLI is available:
```bash
windsurf --list-extensions
```
If not available, you may need to run from Windows side or add to PATH.

---

## File Locations Summary

```
/opt/fabrik/
├── .windsurf/rules/           # Workspace rules (git-tracked)
│   ├── 00-critical.md
│   ├── 10-python.md
│   ├── 20-typescript.md
│   ├── 30-ops.md
│   ├── 40-documentation.md
│   ├── 50-code-review.md
│   └── 90-automation.md
├── docs/reference/
│   ├── EXTENSIONS.md                              # Auto-generated
│   ├── CASCADE_MEMORIES_GLOBAL_RULES_BACKUP.md   # Manual export
│   └── CASCADE_BACKUP_GUIDE.md                   # This file
└── scripts/
    ├── sync_extensions.sh      # Extensions hook
    └── sync_cascade_backup.sh  # Freshness check hook
```
