# Session-history retention — the off-site archive

Box-local. What keeps this machine's Claude Code session transcripts safe, where the copy lives,
and how to get a transcript back. Decisions: D-142 (archive, not session-recall, is the durable
tier), D-470 (local retention 3650 days on every account), D-565 (ship direct to Backblaze B2),
D-569 (the plan's converged revision), D-736 (the operator's ruling: every history in B2, ~3 days
local, the four named hub windows, never a session visible on screen), D-737 (Phase C). Plan:
`docs/development/plans/2026-09-06-plan-1-session-history-retention.md`.

## What runs

| Piece | Where | What it does |
|---|---|---|
| `session-archive.timer` | `~/.config/systemd/user/` (source: `scripts/sysadmin/systemd/`) | daily, `Persistent=true` — a run missed while the machine was off fires when the user manager next starts; linger keeps that manager up without a login |
| `session-archive.service` | same | `ExecStartPre=-` the growth sampler (its failure never skips the backup), then the archiver, the pruner, and `rotate_session.py due --mb-only --mail` (W-f975fee0 slice 3: each repo's mailbox gets one `ack: no` mail — the hub's addressed to its coordinator — listing the agents whose transcript is past `ROTATE_ADVISE_MB`, with the rotate command for each; its `-` keeps a mail failure from failing the unit); a failed run (e.g. no network at boot) is retried every 15 min, at most 4 starts in 19 h (the interval holds four attempts of up to 4 h 40 min — systemd re-arms the start timeout for each of the four start commands, measured on systemd 255, then five stop stages and the restart pause — so even a slow failure reaches the limit, and under 24 h so a window the nightly timer opened closes before the next night's start; one a boot catch-up or by-hand start opened can still refuse it until `reset-failed`, which the FAILED mail names), and a start command still going after `TimeoutStartSec=1h` is ended as a failure; then `session_archive_alert.py check` as `ExecStopPost=-` (W-36687f76, below), which mails a pruner refusal (exit 3) or a failed rotation mail — the two `-` failures systemd logs nothing for |
| `session-archive-alert.service` | same | the archive unit's `OnFailure=`: with `RestartMode=direct` it starts ONCE, after the retries are spent, and runs `session_archive_alert.py failed` |
| `scripts/sysadmin/session_archive_alert.py` | main checkout | the backup's alert (W-36687f76) — each mail goes to infra (`ack: required`) and the coordinator (`ack: no`). `failed`: the final failure, with the unit's journal tail. `check`: on a SUCCESSFUL run only, every step that did not exit 0 (read from `systemctl --user show -p ExecStartPre -p ExecStart`, which holds each step's status only while the unit runs; systemd logs nothing for a `-` step that fails) and the archiver's partial nights from its own summary line — subagent failures, `0 MAIN transcript(s) eligible`, the archive lock held, or no summary at all; a run stopped mid-archive (it still ends `success`) is mailed as STOPPED; what it cannot read, and its own crash, are mailed too. Its worst case (`CHECK_BUDGET_S`) stays under the unit's `TimeoutStopSec=5min`, so a slow check never re-runs the archiver |
| `scripts/sysadmin/sample_transcript_growth.sh` | main checkout | one row a day into `~/.claude/state/transcript-growth.tsv` (date, MAIN bytes, files, largest) |
| `scripts/sysadmin/transcript_size_check.py` | user-level hook (every window) | the ROTATE advisory (D-736 C.1.3): one `ROTATE:` line when a session's transcript crosses a new 100 MB step at or past `ROTATE_ADVISE_MB` (200) — at the next item boundary `rotate <agent>` to the coordinator, who types `/clear <agent>-<date>` and the informed `--force` re-bind; and the context sensor (W-f975fee0): `ROTATE-DUE` from 40% of the window, `COMPACT-DUE` from 85%, once per step; stamped per session, fail-open |
| `scripts/sysadmin/archive_transcripts.py` | main checkout | zstd each MAIN transcript (`ARCHIVE_AFTER_DAYS`, default 0 — an open window ships a daily snapshot, compressed from a frozen copy) into `~/.claude/archive/<slug>/<session>.jsonl.zst`, append `manifest.jsonl`, `rclone copy` to the bucket, then upload the manifest; since D-1182 also every subagent transcript (`<slug>/<session-dir>/subagents/**/*.jsonl` — sidechains, workflow sidechains, workflow journals; not `.meta.json`) into `~/.claude/archive/<slug>/<rel>.zst` with its row in its OWN `manifest-subagents.jsonl` (keyed slug + `rel`, the path under the slug dir), uploaded beside the MAIN one; a sidechain that fails to archive prints `FAILED … the pruner keeps it` and the night goes on |
| `scripts/sysadmin/prune_transcripts.py` | main checkout — the unit's second `ExecStart=-` line, after the archiver | the ONLY deleter of MAIN transcripts (D-736 C.2): on `--dry-run` (a hand run; the unit ran this mode until Gate C passed on 2026-10-12) it prints the table and writes a summary row to `~/.claude/archive/prune-log.jsonl`; on `--apply --nightly` it deletes the oldest `PRUNE_MAX_PER_RUN` (200) transcripts that pass EVERY guard — older than `PRUNE_AFTER_DAYS` (3), not an OPEN session, not a project's or an agent's newest, indexed by session-recall to the current inode and size, current sha256 = the manifest row's, the `.zst` decompressing to those bytes, the bucket listing it with the same size and SHA1, every hard-linked live name passing, its set-aside links (`<session>.jsonl.superseded-<ms>`) unlinked with them and a set-aside-only inode never deleted (D-1188) — one fsynced `pruned.jsonl` row BEFORE each unlink; `--restore <session_id>` puts one back, `--verify-ledger` re-lists every pruned object, `--status` shows the last row and the last apply row; the subagent tier: a sidechain (`<slug>/<sid>/subagents/agent-*.jsonl`) older than 3 days is deleted only when the archive vouches for it (D-1182: its `manifest-subagents.jsonl` row, then the same sha256 / `.zst` / bucket checks, then the last look) and `--restore agent-<id>` puts it back; `~/.claude/tasks` and `~/.claude/shell-snapshots` stay a 3-day cliff, never archived; the workflow sidechains (`subagents/workflows/…`) are archived and never pruned |

Install (from the main checkout, once the archiver change is merged):

```bash
bash scripts/sysadmin/install_session_archive_timer.sh
```

It refuses unless `loginctl show-user "$USER" -p Linger` reads `Linger=yes` and `systemd-analyze --user verify`
prints nothing for the three units (a key in the wrong section is only a warning at rc 0), copies them — the alert
unit first, since verify never resolves an `OnFailure=` target — and enables the timer. Claude Code's safety check
refuses an agent this run, so the operator's one-time setup script runs it as its `archive` step, after a diff and a
backup of the installed units (`operator-setup.md`).

## Where the copy lives

- **Bucket** `wsl-ozgur` (Backblaze B2, Private, SSE, lifecycle *Keep all versions*), prefix
  `archive/`. Settings in `/opt/fabrik/.env` (a non-empty process-environment value wins; an empty one counts as unset): `SESSION_ARCHIVE_B2_BUCKET`, `SESSION_ARCHIVE_B2_PREFIX`,
  `SESSION_ARCHIVE_B2_BUCKET_ID`, `SESSION_ARCHIVE_B2_ENDPOINT` (informational — never passed to
  rclone). The application key — `SESSION_ARCHIVE_B2_KEY_ID`, `SESSION_ARCHIVE_B2_APPLICATION_KEY` —
  is restricted to that bucket and lives in the same file; the archiver reads ONLY the
  `SESSION_ARCHIVE_*` lines.
- **Local** `~/.claude/archive/` holds the same `.zst` files and both manifests (`manifest.jsonl` for
  MAIN, `manifest-subagents.jsonl` for the subagent tier).
- The transcripts themselves stay in `~/.claude/projects/` for at least 3 days (Claude's own
  `cleanupPeriodDays` stays 3650, D-470 — its sweep is never the deleter). The ONE thing that
  prunes them is `prune_transcripts.py` (the row above; D-736 superseding the Phase C deferral):
  on `--apply --nightly` since Gate C passed on 2026-10-12 (the merge, the download proof through the
  vps1 tunnel, session-recall's incremental ingest + `SESSION_RECALL_RO_DSN`, a 10-file canary). A pruned session is still read through session-recall and put back with
  `prune_transcripts.py --restore <session_id>`; `prune_transcripts.py --status` and
  `--verify-ledger` are the morning check.

## Safety properties

- **The transport cannot delete.** Every rclone call goes through one helper whose verbs are an
  allow-list (`copy`, `copyto`, `lsf`) and which refuses any `--delete*` or `--b2-hard-delete`
  option. Because the bucket keeps all versions, an overwritten `.zst` leaves its prior version
  recoverable.
- **The key never appears in a command line** — it reaches rclone through the child process's
  environment (`RCLONE_CONFIG_SESSIONB2_*`) only.
- **A manifest row is written only after its bytes landed**; the manifest itself ships after.
- **One run at a time** (`~/.claude/archive/.archive.lock`); a second run exits 0 and does
  nothing.
- **An open window is archived from a frozen copy** (`~/.claude/archive/.snapshot-*/`, never
  uploaded): the copy is hashed and compressed, so a row always describes the uploaded bytes even
  while the session appends. A run killed mid-copy leaves that folder behind; the next run removes it.
- **Hard links** (D-467 links worktree transcripts into their repo's lane) are archived once; the
  row's `also_slugs` names the other folders.
- **Set-asides** (W-a2cae11b, D-1188): when Claude Code relocates a transcript onto a destination
  already holding one, it renames the occupant `<slug>/<session>.jsonl.superseded-<ms>`. Both scripts
  treat that name as a MAIN name. A set-aside that is a hard link of a live `<session>.jsonl` (the
  usual case) is archived with it, never written into `also_slugs`, and pruned in the same pass that
  prunes its live names. Before this fix, such a link kept the inode's blocks on disk. A set-aside
  that is the only name of its inode is archived under its own key — object
  `<slug>/<session>.superseded-<ms>.jsonl.zst` — and the pruner never deletes it (`set-aside-only`):
  session-recall indexes `*/*.jsonl` only, so it cannot vouch for one.
  - Claude Code's own cleanup deletes set-asides. One that it creates and deletes between two
    nightly runs is never archived.
  - One that it deletes after an archive has no `pruned.jsonl` row. Fetch it as in § Restore below —
    `--fetch '/<slug>/<session>.superseded-<ms>.jsonl.zst' /tmp/r.zst`, then
    `zstd -d /tmp/r.zst -o ~/.claude/projects/<slug>/<session>.jsonl.superseded-<ms>`.
  - Two pruned inodes can share one session id: the set-aside one and the transcript moved in over
    it. `prune_transcripts.py --restore <session>` then refuses, listing each slug. Pick one with
    `--slug=<slug>`, written with `=` because every slug starts with `-`.

## Restore

The archiver carries the two verbs a restore needs, using the same key handling:

```bash
cd /opt/fabrik
.venv/bin/python scripts/sysadmin/archive_transcripts.py --remote-count          # objects + manifest hash
.venv/bin/python scripts/sysadmin/archive_transcripts.py --fetch '/<slug>/<session>.jsonl.zst' /tmp/r.zst
zstd -d /tmp/r.zst -o /tmp/r.jsonl                                                # then compare / put back
```

- **The leading `/` is required:** every slug starts with `-` (`-opt-fabrik`), which argparse would
  read as an option. `--fetch` writes to a path that must NOT exist yet, and exits 1 unless exactly
  one regular file arrived — a prefix (a folder of objects) is refused.
- `--remote-count` prints `remote_manifest_sha256 absent` when no manifest could be fetched.
- ⚠️ **Downloads need B2's download host (`f004.backblazeb2.com` for this bucket); uploads do not.**
  On 2026-10-08 this machine's network cut the TLS handshake to that hostname (an SNI filter: the
  name is refused even at another host's IP, while the upload API host works). From such a network
  the archive still uploads daily, but `--fetch` exits 1 ("was not downloaded … unreachable") and
  `--remote-count` reads the manifest as `absent`: rclone resolves a single object through the
  download host and, failing that, sees an empty folder. Run a restore from a network that reaches
  `https://f004.backblazeb2.com` (check with `curl -sI https://f004.backblazeb2.com/`).

- An OLDER version of a transcript (the object is overwritten each time the transcript changes):
  add `--version-at <RFC3339 instant>` — an instant after the run that uploaded the version you
  want and before the next run that rewrote it. A manifest row's `archived_at` is the compression
  time, a little before the upload.
- A transcript whose row has `also_slugs`: restore it once, then hard-link it into each listed
  folder.
- Put a restored file back under `~/.claude/projects/<slug>/<session>.jsonl`; session-recall picks
  it up on its next incremental index.

### After a prune — `prune_transcripts.py --restore`

A session the pruner removed (Phase C, D-736) is listed in `~/.claude/archive/pruned.jsonl` — one row
per deletion. A `main` row carries the tier, the slug, the session id, the sha256, the byte count, every
path removed, the agent tag, the object key with its size and SHA1, and `pruned_at`; a `subagents` row
carries the tier, its `kind` (`subagent`, `task` or `shell-snapshot`), the byte count, the paths and
`pruned_at`, plus the slug and the parent session id — filled for a `subagent` kind, empty strings for a
`task` or a `shell-snapshot`, which belong to no project. Since D-1182 a `subagent` row also carries the
sha256 and the object key with its size and SHA1, so it restores like a MAIN one; a task, a shell
snapshot and a sidechain pruned before D-1182 have nothing to restore from. That file ships to the bucket
with the archive, so the list is off-box too.

```bash
cd /opt/fabrik
.venv/bin/python scripts/sysadmin/prune_transcripts.py --restore <session_id> [--slug=<slug>]
.venv/bin/python scripts/sysadmin/prune_transcripts.py --restore agent-<id> [--slug=<slug>]   # a sidechain
```

- A session id selects MAIN rows only; `agent-<id>` selects only sidechain rows whose path ends in
  `agent-<id>.jsonl`. When one agent id was pruned under two session dirs the restore refuses and lists
  both paths with their `pruned_at` — fetch the one you want with `archive_transcripts.py --fetch` instead.

- It re-creates EVERY path the row names as one inode: when a hard-linked twin survived with the row's
  sha256, the missing names are linked to it and nothing is fetched; otherwise the object is fetched
  (the download host above applies), verified against the row's sha256, written to the first missing
  path (never over an existing file) and hard-linked to the rest. The inode's `mtime` is set to now, so
  the next dry-run keeps it for 3 more days; `/resume` lists it again.
- A surviving path with ANOTHER sha256 is live history: the restore refuses (exit 3) and names it.
- A failed fetch is a refusal naming the three causes (object absent · download host unreachable ·
  rclone itself failed) with `--fetch`'s own line; nothing is written.
- Exit codes: 0 restored · 3 refused · 1 error · 2 usage.

### The morning check

```bash
.venv/bin/python scripts/sysadmin/prune_transcripts.py --status          # the last run's row and the last APPLY row
.venv/bin/python scripts/sysadmin/prune_transcripts.py --verify-ledger   # every pruned object still listed with its size + SHA1
.venv/bin/python scripts/sysadmin/archive_transcripts.py --agent infra   # one named window's history, newest first
```

## Named hub windows — `agent`, `--agent`, and the ROTATE line

Each manifest row carries `"agent": "<name>"` when the session is bound to a hub agent (D-736 C.1): the
latest `~/.claude/state/agent-identity.jsonl` row for its session id, else the registry join
(`~/.claude/sessions/<pid>.json` → `pid`+`procStart` ↔ the identity row's `pid`+`pid_start`, as integers),
which is what tags a window after `/clear`. `archive_transcripts.py --agent <name>` lists that agent's
rows newest first with whether the local file still exists — "infra's history" is that list plus
session-recall. The pruner keeps each agent's NEWEST session as well as each project's. When a window's
transcript passes `ROTATE_ADVISE_MB` (200 MB) the user-level hook prints one `ROTATE:` line per 100 MB
step, and from 40% of the context window a `ROTATE-DUE` line at 40, 50, 60, 70 and 80% (`COMPACT-DUE` at
85, 90 and 100%, W-f975fee0). Rotation waits for the next item boundary (D-1119): the builder messages its coordinator
`rotate <agent>` (or `compact <agent> <focus>`), and the coordinator runs `agents_up.sh rotate-session <agent>
[--compact <focus>] [--trigger ctx|mb|unrelated|compact|manual|lift]` from its repo (D-1135). That verb
(`scripts/sysadmin/rotate_session.py request`) resolves the pane tagged `@agent <agent>`, its one `claude` process and
that process's registry session, and aborts at the first failing check: the transcript unwritten for 30 s, the transcript
ended at a turn end, no run record running, no seat in flight, the worktree clean and pushed, the pane's input line
empty. It then writes ONE data-only request (`~/.claude/state/rotate-requests/<repo>--<agent>.json`; one at a
time). The user unit `fabrik-rotate.path` starts `fabrik-rotate.service` (`rotate_session.py execute`), which
re-runs every check, types `/clear <agent>-<date>` (or `/compact <focus>`) — each text pasted, then `C-m` as its own
call once the input line shows that text unchanged over two captures, then the input line must hold something other
than that text (empty, a placeholder, a dialog) (an Enter sent right behind the paste was swallowed, W-b92aa5cf) —
waits for the registry's new session id, re-points the repo's `.fabrik/session-agents.json` entry from the old
session id to the new one itself under the repo's agents lock (`refused:agents lock busy` after 30 s; `refused:agents
lock unavailable` when the lock cannot be resolved) (W-b72231b8, D-1175: only for the checkout the old session's binding names; a file
agents_up.sh would refuse, a missing entry or a hand edit since its read is left alone, and the state is rowed as
`registry`), then types one resume prompt — re-arm the self-watch (a /clear may kill or orphan background shells), re-bind with
`python3 /opt/fabrik/scripts/whoami_agent.py --as <agent> --force`, read only the memory notes, `work.py next` and
the run's seed, the notes and any output the harness saved to a file through the Read tool and each command as a
separate Bash call, never sed, awk or head on a shell variable (Claude Code's worktree isolation stops on that for a
person — W-1783a9fe, D-1173) — and records every outcome (`ok`, `refused:<check>` — `request`, `claim`, `error`, `orphan` among them —, `stale`,
`partial:<step>`, `typed-unsent:<step>` — a text that never showed, never settled, or stayed in the input line after `C-m` —, and the verb's `aborted:<check>`) in
`~/.claude/state/rotations.jsonl`, with `resume_sent_at` and, for a bound row, `rebind_s` (the bind's own time minus
the send). The re-bind wait is `REBIND_GRACE_S` (180 s, W-b72231b8 slice 2; the one late bind measured took 98 s); a
bind later than that rows `partial:rebind`. While it waits the executor holds its lock, so another rotation asked in that
window is refused `aborted:pending` — the coordinator asks again; nothing retries it. The verb's exit says whether asking again can pass (W-05021a03): **75** when the abort clears by itself — the session still in its turn, a run record or seat still going, the rotation in flight, tmux slow, a pane restarting or drawn without its input box — and **1** only on positive evidence that an act comes first: a bad argument or trigger, the request directory's ownership, a dialog's numbered option on the prompt row (answer it), text in the input box (clear it or ask with `--stale-input discard`, which refuses a box over 1000 characters), two transcripts for the session, no identity binding yet (the reason names the `whoami_agent.py --as <agent> --force` to send) or one held by another window, uncommitted or unpushed work, a slash-command ending (send one prompt), or a request the path unit never claimed (`install_rotate_unit.sh --check`). Its stderr line says `(transient …)` or `(permanent …)`. A crash also exits 1, and argparse's usage error, or a run outside any repository, exits 2, so anything but 75 is read, never retried blindly. Every wait the script itself runs
is a named constant and `REQUEST_WORST_S` (517 s, the agents-lock wait included) is derived from them, and `execute`
claims no new request after `CLAIM_CUTOFF_S` (20 s), so the last rotation it starts ends inside the unit's 600 s
timeout — except that the git calls `run_checks` makes (60 s timeout each) and the one that resolves the agents lock's
path are not counted yet (W-b728822f). A request left unclaimed waits for the path
unit's next start, which almost always rows it `stale` (it is then older than 60 s). Nothing is queued or retried: keys typed mid-turn would
queue. Install the units once from the main checkout with `scripts/sysadmin/install_rotate_unit.sh` (`--check`
reports). The previous session stays resumable and is archived that night.

The pane's input box must be empty for a rotation: check 5 reads every row of the box down to its closing rule, and the
dim placeholder of a fresh box counts as empty. Text someone left unsent in the box blocks it; the coordinator clears it
with `agents_up.sh rotate-session <agent> --stale-input discard --operator-ok "<the operator's words>"` (W-ee19169d):
the request records the box's text (its rows joined, whitespace collapsed), and the unit acts only when the box still
reads exactly that text on two captures 2 s apart and every check passes again right before the key (the session idle
— an Escape in a running turn would interrupt it). It then sends one fast double Escape, which Claude Code uses to
clear a non-empty box (C-u deletes only the current row). On an empty box a double Escape opens the Rewind menu, which
the unit closes and refuses. The box must read empty before the normal rotation runs, and the discarded text and the
operator's words are written to the row.

A /clear keeps the claude process, and with it the folder the pane STARTED in, which is where its hooks, settings and
permissions load from (`CLAUDE_PROJECT_DIR`) and where its session is filed, so the grid resumes it there too. A
builder that moved into another linked worktree therefore runs stale hooks until it is MOVED (`selfwatch_check.py`
prints `HOOKS LOAD FROM ANOTHER TREE`): the coordinator runs `agents_up.sh rotate-session <agent> --move [--trigger …]`
(W-e38f8ee7), a rotation into the worktree the builder works in. The folder is derived, never typed: the linked
worktree in place under the repo's `.claude/worktrees/` that holds the session record's `cwd`. The request is refused
(exit 1) when the cwd is in none, when that tree is named `coordinator` or `*-coordinator`, when the session is already
filed under it (nothing to move), and with `--compact` or `--stale-input` (the declared merge owner's tree is refused at
execute, by the pane command below, as `refused:launch`); otherwise it runs the same checks and writes a `mode:
move` request. The unit gets the pane command first — `agents_up.sh --pane-cmd <repo> <agent> <new id> --into <folder>
--from <old id> --replacing <old pid>`, run with the pane's own PATH and AGENT_IDENTITY_FILE, which refuses when the
resolver no longer gives the agent that session, when the new id is known or has a transcript, when the folder is a
coordinator's or another builder's tree, or when another `claude -n <agent>` already runs there. It then runs every
check, reads the input box and the transcript twice 2 s apart (a `respawn-pane -k` kills a running turn, where a
/clear typed into one only queues), and runs `tmux respawn-pane -k -c <folder>` with that command: the pane keeps its
id and `@agent` tag, and a FRESH `claude -n <agent> --session-id <new id>` starts there with the move prompt as its
first turn — the resume prompt above, prefixed with where it now starts — so no key is typed. The old claude (that pid
and start time, a zombie counting as exited) gets 10 s to exit, then SIGTERM and 5 s, then SIGKILL and 2 s (`old_exit:
gone|term|kill|survived`; its detached children are not reaped). A respawn whose tmux call fails or times out rows
`partial:respawn` and reaps nothing, since it cannot tell whether the old claude was replaced. The unit waits for the
new session's record (`partial:launch` without one), re-points the registry and waits for the re-bind as above; the row
carries `mode: move` and `into`, and `predecessor_row` reads false because `whoami_agent.py` records a predecessor only
for a re-bind inside the same process, and a move starts a new one. The move's waits are `MOVE_WORST_S`, under
`REQUEST_WORST_S`. The next grid start finds the new session filed under the folder and starts the pane there.

Nothing types a rotation unasked, but two listings offer them (W-f975fee0 slice 3): `rotate_session.py due
[--mb-only] [--mail]` lists every live agent at or past 40% of its context window or `ROTATE_ADVISE_MB`, the caller
and the coordinators included, pool seats never, with its action — the exact `agents_up.sh rotate-session <agent>
--repo <repo> --trigger ctx|mb` for a tmux (`cli`) agent, the operator's `/clear <agent>-<date>` for a window with no
pane — and an agent it cannot read (no name bound, no single transcript) as an `unread` row, never dropped.
`hibernate.py lift` prints the same rows as offers with `--trigger lift`, and the nightly unit mails them MB-only.
The request directory is created 0700 by `request`, `execute` and the installer; a symlinked one refuses in all three,
and one another uid owns refuses in `request` and `execute`.

## Checking it

```bash
systemctl --user list-timers session-archive.timer
systemctl --user show session-archive.service -p Result
journalctl --user -u session-archive.service -n 50
journalctl --user -u session-archive-alert.service -n 20   # the alert's own sends
systemctl --user reset-failed session-archive.service      # after a FAILED mail: clears the start limit, then `start`
```

A failed or partial night arrives as two `finding` mails in the `fabrik` mailbox: one to infra (`ack: required`),
one to the coordinator (`ack: no`); a quiet night sends nothing. A night the timer never fired sends nothing either —
neither `OnFailure=` nor `ExecStopPost=` runs.

<!-- BEGIN related-scripts: generated by scripts/render_doc_script_links.py — do not hand-edit -->
## Related scripts

Scripts that declare this document in their `# AFTER-EDIT:` header — editing one of them
means updating this page in the same change. This list is generated from those headers
(`python3 scripts/render_doc_script_links.py`); add the doc to a script's header, not here.

- `scripts/sysadmin/archive_transcripts.py`
- `scripts/sysadmin/prune_transcripts.py`
- `scripts/sysadmin/rotate_session.py`
- `scripts/sysadmin/session_archive_alert.py`
- `scripts/sysadmin/transcript_size_check.py`
<!-- END related-scripts -->
