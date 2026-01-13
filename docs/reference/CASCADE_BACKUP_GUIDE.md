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

## Migration Scenario: Copying Entire WSL

When migrating to a new computer by copying the entire WSL filesystem:

### What's Preserved (Already in WSL)
- ✅ All project files and git repos
- ✅ Workspace rules (`.windsurf/rules/`)
- ✅ Backup files (`CASCADE_MEMORIES_GLOBAL_RULES_BACKUP.md`, `EXTENSIONS.md`)
- ✅ All scripts and configurations

### What's Lost
- ❌ **Windsurf chat history** - Stored in Codeium cloud, tied to account
- ❌ **Cascade memories** - Stored in Codeium cloud, need to recreate
- ❌ **Global rules** - Stored in Codeium cloud, need to recreate
- ❌ **Windsurf extensions** - Installed on Windows side, not in WSL

---

## Restore Steps After WSL Migration

### 1. Install Windsurf on New Windows
Download and install Windsurf on the new Windows machine.

### 2. Install Extensions (Windows Side)
From WSL, run the install commands:
```bash
cat /opt/fabrik/docs/reference/EXTENSIONS.md | grep "windsurf --install-extension" | bash
```
Or copy commands and run in Windows terminal.

### 3. Restore Memories
Open a new Cascade conversation and say:
```
Please create memories from each section in /opt/fabrik/docs/reference/CASCADE_MEMORIES_GLOBAL_RULES_BACKUP.md under "PART 1: MEMORIES". Create one memory per section.
```

### 4. Restore Global Rules
1. Open Windsurf Settings > Cascade > Rules
2. Add each rule from PART 2 of `CASCADE_MEMORIES_GLOBAL_RULES_BACKUP.md`

### 5. Chat History
**Chat history cannot be restored.** It's tied to your Codeium account/cloud.
- If logged into same Codeium account, some history may sync
- Otherwise, history is lost - this is why we backup memories/rules to files

---

## Alternative: Fresh Clone (Without WSL Copy)

If starting fresh without copying WSL:

### 1. Clone the Repository
```bash
git clone <repo-url>
cd <project>
```

### 2-5. Same as Above
Follow steps 2-5 from the WSL migration section.

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
