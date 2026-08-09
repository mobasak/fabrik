# WIP Backup Safety Net — no agent work is ever more than 15 minutes from safe

`scripts/wip_backup.sh`, cron `*/15` (flock-guarded, `/tmp/wip-backup.log`): every dirty `/opt` git repo
gets its ENTIRE working tree — staged + unstaged + untracked — snapshotted to `refs/wip/autobackup`
(+ a dated `refs/wip/bak-<ts>` kept 7 days) and the rolling ref force-pushed to origin (off-box).

**Why it's safe around live agents:** the snapshot is built through an ISOLATED index
(`GIT_INDEX_FILE` temp) — it never touches the real index, HEAD, any branch, or the stash list, so a
sibling's half-staged work stays exactly as they left it. Clean repos and unchanged-dirty repos are
skipped (no ref churn). `archived/` is excluded.

**What it protects against:** VS Code reloads and machine restarts (the post-restart session can't
attribute the old session's uncommitted files — now it doesn't need to for safety), pre-commit
stash/restore accidents, resets, and any agent forgetting to commit.

**Recovery:**

```
git log refs/wip/autobackup                      # what/when
git checkout refs/wip/autobackup -- <path>       # restore one file
git cherry-pick -n refs/wip/autobackup           # restore the whole snapshot as WIP
git for-each-ref 'refs/wip/bak-*'                # point-in-time snapshots (7 days)
```

Backup refs are NEVER work commits: nothing merges them, the Stop-hook ignores them, and force-pushing
the rolling ref is by design (it's a backup slot, not a branch).

**Snapshot-era caveat:** snapshots taken before 2026-08-09 ~18:00 were built from an EMPTY temp index
and record tracked-but-gitignored files as deletions — recovering from one of those via `cherry-pick`
would DELETE such files. Current snapshots seed the index from HEAD (fixed); old dated refs age out
in 7 days. If you must recover from a pre-fix ref, restore single files (`git checkout <ref> -- <path>`),
never the whole snapshot.
