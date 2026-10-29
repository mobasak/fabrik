# Operator one-time setup

The operator's requirement 1.1 (`docs/reference/operator-agent-requirements.md`): the operator does the one-time
steps only the operator can do, once, and the coordinators do the rest. Claude Code's safety check refuses agents the
settings-file, home-dir and user-systemd writes below, so they are collected in ONE script the operator runs
(W-d6726a65, D-1311).

## The run

From the hub main checkout, on master:

```bash
python3 /opt/fabrik/scripts/sysadmin/operator_setup.py           # dry run: a diff of every change, writes nothing
python3 /opt/fabrik/scripts/sysadmin/operator_setup.py --apply   # back up, write, verify, print the undo lines
```

The five steps:

| step | what it changes |
|---|---|
| `hooks` | the user-level hook entries in every account dir `install_user_hooks.py` targets (its `_targets()`) — the bytes are that installer's own output, computed on a scratch copy of HOME |
| `wrapper` | `~/.claude/bin/claude-agent-wrapper.sh` — a copy of `scripts/sysadmin/claude-agent-wrapper.sh` (the tab router's wrapper, `claude-tab-router.md`), mode 0755 |
| `vscode` | `claudeCode.claudeProcessWrapper` in `~/.local/share/code-server/User/settings.json` and `~/.vscode-server/data/Machine/settings.json`, every other key kept; an editor that is not installed (no parent dir) is skipped |
| `archive` | the nightly chat backup's three systemd user units (`session-archive.service`, its timer and its failure alert, W-36687f76) — the script diffs and backs them up, then runs `scripts/sysadmin/install_session_archive_timer.sh` once, which verifies, installs and enables them (`session-history-retention.md`) |
| `ssh` | a keepalive for git pushes (W-030ac2fe): `~/.ssh/config` gains a comment-marked `Host github.com` block with `ServerAliveInterval 15` and `ServerAliveCountMax 4`, put before the file's first `Host`/`Match` section because ssh takes the first value it reads (a file without one gets it appended; a missing `~/.ssh` is created 0700, a new config 0600, an existing one keeps its mode). Without it a push on a dead connection never times out. Whether the step is needed, and whether its result works, is decided by what `ssh -G -F <copy> git@github.com` itself resolves; only the insert point is found by matching the `Host`/`Match` keyword. A keepalive already as tight (an interval of 15 s or less, interval × count at most 60 s) is in place and kept, so an operator's own tighter value is never overridden. `-G` never connects, but it runs the config's `Match exec` commands and may do DNS, as every push does (30 s limit) |

Exit codes: 0 done or nothing to do · 1 a refusal, a failed archive installer or a failed verification · 2 `--apply`
outside the hub main checkout or with it off master. A second `--apply` changes nothing and exits 0.

## What it refuses

The whole plan is built before anything is written, and a planning refusal writes nothing: a target that is a symlink
or sits outside HOME, an account `settings.json` the installer cannot parse or that repeats a key, an editor settings
file that is not plain JSON (comments, a trailing comma, a BOM, a duplicate key, the nested `claudeCode` form — the key
to add by hand is printed), an unreachable user systemd manager, and linger off for the archive step (it prints
`loginctl enable-linger <user>`). The ssh step also refuses a `~/.ssh/config` writable by group or others or owned by
another user than you or root (ssh itself refuses such a file, but `-G -F` skips that check), a config it cannot read or
ssh will not parse, a write into a `~/.ssh` that cannot take it (a file, a dangling symlink, mode 0500, or a missing `~/.ssh` in a HOME you
cannot write — a config already in place needs no write and is no refusal), a HOME that
is not your passwd home (ssh reads `~` from passwd, never `$HOME`; `OPERATOR_SETUP_SSH_HOME=1` lifts this check and says
so on stderr — it exists for the tests' scratch HOME, and an operator who sets it gets a config ssh never reads), and a looser setting the block cannot override: a global `ServerAliveInterval` or an `Include`
above the first section wins over anything after it, so the step prints the value ssh resolves; move that line below the
first section, or tighten it there. A host alias that reaches github.com under another `Host` name is not covered. A
file edited after planning is not overwritten: it is re-read before the backups
and again right before its own write, and the run stops there. Two exceptions are accepted (W-88173de4), since no
portable compare-and-swap on a path exists: a save landing between that last re-read and the replace (the new
file's write and fsync included), and a save to one of the three archive units before the installer's own `install`
lands — a unit that differed at planning is re-checked as a guard only before the backups (the done list reads it
again after the installer), and one that did not is never re-checked or backed up. Once `--apply` has made its backup dir, a later stop —
the archive installer failing, a backup that does not read back, or that re-read — leaves the backups and whatever was already written, and prints the
undo lines for exactly that.

`--apply`'s guard proves the script's location (`/opt/fabrik/scripts/sysadmin/`) and that the main checkout is on
master — not that the tree is clean; the wrapper it installs runs in every chat tab, so run it after a merge, never
mid-edit.

## Rollback

`--apply` copies every file it changes into `~/.local/state/fabrik/operator-setup-<timestamp>/` (mode 0700) first and
prints one undo line per file — `cp -p <backup> "$HOME"/<path>` for a file that existed, `rm -f "$HOME"/<path>` for one
it created. When the archive installer ran, the lines open with `systemctl --user stop session-archive.timer` when the timer was
not active before, then put the timer's persistent link (`timers.target.wants/session-archive.timer` in the unit dir —
`~/.config/systemd/user` unless `XDG_CONFIG_HOME` is set) back as it was: `rm -f` when the installer's `enable` added
it, `ln -sfn -- <old target>` when `enable` rewrote a link that pointed elsewhere, nothing when it already pointed at
the unit (never `systemctl --user disable`, which would also delete an alias you made to the unit; W-88173de4); a
non-symlink at that path is refused at planning, and so is a link whose old target is not UTF-8 or holds a control
or line-break character (a tab included), which cannot be printed as one undo line (W-b3192e98). They end with `systemctl --user daemon-reload`. The archive installer runs FIRST, so
when it fails the other steps are unwritten and the undo lines name the units it changed. Any parent directory a step
has to create (`~/.ssh`, `~/.claude/bin`) is made 0700 and left in place, empty, by the undo. The tab router's fast rollback stays
`"CLAUDE_TAB_ROUTER": "off"` in `claudeCode.environmentVariables`.

## Not in it

No permission allow rule: W-835894a6 needs only the wrapper, and infra-3's two candidates for W-b9ad80ae
(`agents_up.sh add/remove`, `wt.exe`) wait on that item's live proof. The rotation unit restart is W-8f957e4b.

<!-- BEGIN related-scripts: generated by scripts/render_doc_script_links.py — do not hand-edit -->
## Related scripts

Scripts that declare this document in their `# AFTER-EDIT:` header — editing one of them
means updating this page in the same change. This list is generated from those headers
(`python3 scripts/render_doc_script_links.py`); add the doc to a script's header, not here.

- `scripts/sysadmin/operator_setup.py`
<!-- END related-scripts -->
