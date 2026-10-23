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
| `session-archive.service` | same | `ExecStartPre=-` the growth sampler (its failure never skips the backup), then the archiver, the pruner, and `rotate_session.py due --mb-only --mail` (W-f975fee0 slice 3: each repo's mailbox gets one `ack: no` mail — the hub's addressed to its coordinator — listing the agents whose transcript is past `ROTATE_ADVISE_MB`, with the rotate command for each; its `-` keeps a mail failure from failing the unit); a failed run (e.g. no network at boot) is retried every 15 min, at most 4 times in 2 h |
| `scripts/sysadmin/sample_transcript_growth.sh` | main checkout | one row a day into `~/.claude/state/transcript-growth.tsv` (date, MAIN bytes, files, largest) |
| `scripts/sysadmin/transcript_size_check.py` | user-level hook (every window) | the ROTATE advisory (D-736 C.1.3): one `ROTATE:` line when a session's transcript crosses a new 100 MB step at or past `ROTATE_ADVISE_MB` (200) — at the next item boundary `rotate <agent>` to the coordinator, who types `/clear <agent>-<date>` and the informed `--force` re-bind; and the context sensor (W-f975fee0): `ROTATE-DUE` from 40% of the window, `COMPACT-DUE` from 85%, once per step; stamped per session, fail-open |
| `scripts/sysadmin/archive_transcripts.py` | main checkout | zstd each MAIN transcript (`ARCHIVE_AFTER_DAYS`, default 0 — an open window ships a daily snapshot, compressed from a frozen copy) into `~/.claude/archive/<slug>/<session>.jsonl.zst`, append `manifest.jsonl`, `rclone copy` to the bucket, then upload the manifest |
| `scripts/sysadmin/prune_transcripts.py` | main checkout — the unit's second `ExecStart=-` line, after the archiver | the ONLY deleter of MAIN transcripts (D-736 C.2): on `--dry-run` (a hand run; the unit ran this mode until Gate C passed on 2026-10-12) it prints the table and writes a summary row to `~/.claude/archive/prune-log.jsonl`; on `--apply --nightly` it deletes the oldest `PRUNE_MAX_PER_RUN` (200) transcripts that pass EVERY guard — older than `PRUNE_AFTER_DAYS` (3), not an OPEN session, not a project's or an agent's newest, indexed by session-recall to the current inode and size, current sha256 = the manifest row's, the `.zst` decompressing to those bytes, the bucket listing it with the same size and SHA1, every hard-linked name passing — one fsynced `pruned.jsonl` row BEFORE each unlink; `--restore <session_id>` puts one back, `--verify-ledger` re-lists every pruned object, `--status` shows the last row and the last apply row; the subagent tier (sidechains, `~/.claude/tasks`, `~/.claude/shell-snapshots`) is a 3-day cliff, never archived |

Install (from the main checkout, once the archiver change is merged):

```bash
bash scripts/sysadmin/install_session_archive_timer.sh
```

It refuses unless `loginctl show-user "$USER" -p Linger` reads `Linger=yes`, verifies both units,
copies them and enables the timer.

## Where the copy lives

- **Bucket** `wsl-ozgur` (Backblaze B2, Private, SSE, lifecycle *Keep all versions*), prefix
  `archive/`. Settings in `/opt/fabrik/.env` (a non-empty process-environment value wins; an empty one counts as unset): `SESSION_ARCHIVE_B2_BUCKET`, `SESSION_ARCHIVE_B2_PREFIX`,
  `SESSION_ARCHIVE_B2_BUCKET_ID`, `SESSION_ARCHIVE_B2_ENDPOINT` (informational — never passed to
  rclone). The application key — `SESSION_ARCHIVE_B2_KEY_ID`, `SESSION_ARCHIVE_B2_APPLICATION_KEY` —
  is restricted to that bucket and lives in the same file; the archiver reads ONLY the
  `SESSION_ARCHIVE_*` lines.
- **Local** `~/.claude/archive/` holds the same `.zst` files and the manifest.
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
`task` or a `shell-snapshot`, which belong to no project — and nothing to restore from, since that tier
is never archived — and that file ships to the bucket with the archive, so the list is off-box too.

```bash
cd /opt/fabrik
.venv/bin/python scripts/sysadmin/prune_transcripts.py --restore <session_id> [--slug <slug>]
```

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
re-runs every check, types `/clear <agent>-<date>` (or `/compact <focus>`), waits for the registry's new session id,
then types one resume prompt — re-arm the self-watch (a /clear may kill or orphan background shells), re-bind with
`python3 /opt/fabrik/scripts/whoami_agent.py --as <agent> --force`, read only the memory notes, `work.py next` and
the run's seed — and records every outcome (`ok`, `refused:<check>` — `request`, `claim`, `error`, `orphan` among them —, `stale`,
`partial:<step>`, and the verb's `aborted:<check>`) in `~/.claude/state/rotations.jsonl`. Nothing is queued or retried: keys typed mid-turn would
queue. Install the units once from the main checkout with `scripts/sysadmin/install_rotate_unit.sh` (`--check`
reports). The previous session stays resumable and is archived that night.

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
```

<!-- BEGIN related-scripts: generated by scripts/render_doc_script_links.py — do not hand-edit -->
## Related scripts

Scripts that declare this document in their `# AFTER-EDIT:` header — editing one of them
means updating this page in the same change. This list is generated from those headers
(`python3 scripts/render_doc_script_links.py`); add the doc to a script's header, not here.

- `scripts/sysadmin/archive_transcripts.py`
- `scripts/sysadmin/prune_transcripts.py`
- `scripts/sysadmin/rotate_session.py`
- `scripts/sysadmin/transcript_size_check.py`
<!-- END related-scripts -->
