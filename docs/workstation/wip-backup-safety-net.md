# WIP Backup Safety Net — no agent work is ever more than 15 minutes from safe

`scripts/wip_backup.sh`, cron `*/15` (flock-guarded, `/tmp/wip-backup.log`): every dirty `/opt` git repo
gets its ENTIRE working tree — staged + unstaged + untracked — snapshotted to `refs/wip/autobackup`
(+ a dated `refs/wip/bak-<ts>` kept 7 days) and the rolling ref force-pushed to origin (off-box).

**Configuration (env vars, all optional — production runs on the defaults):**

- `WIP_BACKUP_ROOT` (default `/opt`) — the directory whose immediate subdirs are scanned as repos.
- `WIP_BACKUP_PUSH_TIMEOUT` (default `120`) — seconds bounding every `git push` (both the main tree's
  and each worktree's), so a stalled network call can never cost a local snapshot or wedge a later
  repo in the same run under the cron's own `flock -n`. A non-numeric or `0` value is rejected and
  silently replaced with the real default (`0` is GNU `timeout`'s own "no limit" sentinel, so passing
  it through unvalidated would silently re-introduce an unbounded push).
- `WIP_BACKUP_TMP_DIR` (default `/tmp`) — where every scratch file (`wip-index-*`, `wip-wt-push/-live/
  -enum.*`) is created. Exists so tests can point the script at a private directory instead of sharing
  the real `/tmp` with this box's own live cron; never override it in production.

**Why it's safe around live agents:** the snapshot is built through an ISOLATED index
(`GIT_INDEX_FILE` temp) — it never touches the real index, HEAD, any branch, or the stash list, so a
sibling's half-staged work stays exactly as they left it. Clean repos and unchanged-dirty repos are
skipped (no ref churn). `archived/` is excluded.

**What it protects against:** VS Code reloads and machine restarts (the post-restart session can't
attribute the old session's uncommitted files — now it doesn't need to for safety), pre-commit
stash/restore accidents, resets, and any agent forgetting to commit.

**Recovery (main tree):**

```
git log refs/wip/autobackup                      # what/when
git checkout refs/wip/autobackup -- <path>       # restore one file
git cherry-pick -n refs/wip/autobackup           # restore the whole snapshot as WIP
git for-each-ref 'refs/wip/bak-*'                # point-in-time snapshots (7 days)
```

**Linked worktrees are netted too, and their refs are a separate namespace.** A `git worktree`
nested anywhere under a repo (e.g. an agent's own `.claude/worktrees/<name>`, or a top-level
sibling worktree of the same store) gets the SAME snapshot recipe, into its own refs, never
`refs/wip/autobackup`:

- `refs/wip/wt-<name>-<id8>` — a ROLLING ref (like `autobackup`), updated only when the worktree's
  tree actually changes, and force-pushed off-box the same way.
- `refs/wip/wt-<name>-<id8>-<ts>` — a dated, LOCAL-ONLY snapshot (like `bak-*`), written only on
  that same change and kept 7 days.

`<id8>` is the first 8 hex characters of `sha1(realpath of the worktree)` — needed because two
worktrees can sanitise to the same name (e.g. `"agent x"` and `"agent-x"` both become `agent-x`);
the hash keeps their refs distinct.

**Recovery (a linked worktree):**

```
git for-each-ref 'refs/wip/wt-*'                          # every worktree's refs, rolling + dated
git for-each-ref 'refs/wip/wt-<name>-*'                   # one worktree's refs by name
git checkout <rolling-ref> -- <path>                      # restore one file from a worktree's snapshot
git cherry-pick -n <rolling-ref>                          # restore the whole worktree snapshot as WIP
```

**Reaper — expiry for a worktree that no longer exists.** Once a worktree is fully removed AND
pruned (`git worktree remove` + `git worktree prune` — gone from `git worktree list` entirely, not
merely missing on disk) AND its newest dated ref has itself aged past the 7-day window, the script
deletes its now-orphaned ROLLING ref too, locally and pushes the deletion — otherwise a rolling ref
for a worktree nobody remembers would pin its commit's objects forever. A worktree still registered
(even if temporarily unenterable, or locked because an agent is actively running there) is never
touched by the reaper, however long its dated ref has been gone.

**FAILS CLOSED, never open:** the reaper runs for a repo only when it can prove its own inputs were
complete, and logs exactly one line naming the reason whenever it can't — never a silent skip, and
never a guess at what's still live. Logged reasons: `.git/worktrees unreadable` (the admin dir itself can't even be looked inside, so the
expected count can't be trusted), `worktree list exited non-zero` (git's own enumeration call
failed), `enumeration incomplete: N of M` (the printed list didn't match the admin-dir-derived
expected count), `live-ids file vanished` (the file the enumeration was recording into went
unreadable mid-loop, checked both when created and again immediately before the reap loop runs),
`live-ids incomplete: N of M recorded` (every worktree was seen, but fewer than that many lines were
actually WRITTEN — e.g. an ENOSPC on `/tmp` mid-run silently drops an `echo` append), and `mktemp
failed for live-ids file`. Any one of these means the run is treated as "can't prove what's live" and
the entire reap pass for that repo is skipped, never partially trusted.

Backup refs are NEVER work commits: nothing merges them, the Stop-hook ignores them, and force-pushing
the rolling ref is by design (it's a backup slot, not a branch).

**Snapshot-era caveat:** snapshots taken before 2026-08-09 ~18:00 were built from an EMPTY temp index
and record tracked-but-gitignored files as deletions — recovering from one of those via `cherry-pick`
would DELETE such files. Current snapshots seed the index from HEAD (fixed); old dated refs age out
in 7 days. If you must recover from a pre-fix ref, restore single files (`git checkout <ref> -- <path>`),
never the whole snapshot.

**After a SIGKILL (e.g. an OOM-kill):** the script's own temp files (`/tmp/wip-index-*`,
`/tmp/wip-wt-*`) are removed by a trap on every TRAPPABLE exit — normal, early, or a caught signal
like SIGTERM — but SIGKILL cannot be trapped and can leave one behind. Sweep exactly those two
prefixes by hand; never delete `/tmp/wip-backup.lock` (that just lets a concurrent `flock -n` run
early) or `/tmp/wip-backup.log` (the forensic record of what already ran).
