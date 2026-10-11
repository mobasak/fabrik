# Plan — session-history retention: archive, prove, then prune

Status: IN-PROGRESS
**Owner:** fleet
Revision: 2026-10-11 — **Phase C REOPENS under the operator's ruling D-736**; CONVERGED the same day by `/fabrik-plan-review` after 16 passes (§ Pass Ledger, revision 2026-10-11) (supersedes D-470's
3650-day local keep and D-565's Phase C deferral). Operator, 2026-10-11, verbatim: *"i want all my
chat histories but not in local, in local recent 3 days might be fine. now for fabrik agents infra,
kaizen, intel, fleet named histories needed, not the scratchpad, subagents etc. we need to implement
this asap. do not forget we have 3 claude.md file one is for fabrik, one for fabrik-lib and one for
governance for all opt projects. be extremely careful not lose my chat histories seen in the screen.
i read them to continue where i left. (all repos)"*. Phases 0, A and the archive timer are LIVE
(D-720; 9,405 sessions in the bucket); Phase B's download leg is still blocked by this network;
§ Phase C below is the revision — the earlier sections stand as executed and are not re-planned.
Revision: 2026-10-05 — **the destination moved to Backblaze B2 DIRECT from this machine** (D-565,
superseding D-142's and D-144's vps1 → Backrest destination). Operator, 2026-10-05: *"why not
directly to Backblaze B2 repo and reachable and searchable via session recall?"* · *"vps1, 2, 3 has
limited storage. this machine is mostly up."* · bucket `wsl-ozgur` created by the operator in the B2
console · *"update the plan to save b2 directly now proceed and finish the plan after reviewing it"*.
**Phase C (the pruner) is DEFERRED, not built** — see § Phase C.
Build state (re-grounded 2026-10-05): Phase 0's CODE shipped (899bfb1a6) but was never scheduled —
no `~/.claude/state/transcript-growth.tsv` exists. Phase A's CODE shipped (a1647928b) with an rsync
transport to vps1 and has NEVER RUN — no `~/.claude/archive/manifest.jsonl` exists. Nothing has
reached any archive.
Date: 2026-09-06 (revised 2026-10-05)
Owner: fleet
Spec: `docs/superpowers/specs/2026-09-05-session-history-retention-design.md` (CONVERGED 2026-09-06,
D-142; partially superseded by D-565 — it now carries a header note and markers at every passage
the revision changed; md5 `1334dc674424a17ea32303abde3bce28` with the D-736 marker of 2026-10-11)

## Why the phase order is a safety property, not a preference

This build deletes irreplaceable data at its last step. Four claims in this work's history were
refuted by reading code *after* they had been asserted confidently — a size comparison that called
15 `.bak` files "provably lossless" when 293 messages existed only in them; "text forever in
session-recall" when `_reclaim_orphans` deletes a session's turns as soon as its JSONL is gone;
"vps1 is a single host" when Backrest already ships to Backblaze B2; and, in this plan's own first
draft, "nothing else reads subagent transcripts" when `claude-stop-decider.py:421` reads exactly
that. The phase order exists so that a fifth mistake costs disk, not history.

**No phase may merge forward. Phase C does not begin until Phase B has produced a byte-identical
restore pulled back from B2** — and, after the 2026-10-05 revision, not until its own reopening
tripwire fires (§ Phase C).

## Phase 0 — MEASURE (no code deletes anything)

The spec fixes 90 days but leaves the size cap open, and honestly so: MAIN was **0.61 GB in August**
and **4.89 GB in the first five days of September**.

- **0.1** `scripts/sysadmin/sample_transcript_growth.sh` appends a daily row (date, MAIN bytes, file
  count, largest single file) using the same predicate as the spec's baseline:
  `find ~/.claude/projects -name '*.jsonl' ! -path '*/subagents/*'`.
- **0.2** Runs daily from the same systemd user timer as the archiver (A.7) — it never ran under
  the first revision because no schedule was ever installed. It is now the SENSOR for Phase C's
  reopening tripwire; no cap value enters code before 14 rows exist.
- **0.3** The cap is **TWO bounds, not one**, because one number cannot protect against two
  different failures:
  - **aggregate** — p95 of the observed daily rate × 90, bounding sustained growth;
  - **per-file** — a ceiling on any SINGLE transcript. The aggregate bound cannot see a runaway
    session: the largest transcript on disk was **696.5 MB** on 2026-09-05 (1,358.0 MB on 2026-10-05) and 50% of all bytes live in the top 14
    files, so a 10 GB session would sit comfortably under a 90 GB aggregate while filling the disk
    on its own. A file over the per-file ceiling is **reported, never silently archived or pruned**.

**Gate 0 (runnable, with Gate A):** `bash scripts/sysadmin/sample_transcript_growth.sh` run by hand
from this worktree, then `wc -l < ~/.claude/state/transcript-growth.tsv` ≥ 2 (header + the first
row); the timer adds a row a day after Gate S. The 14-row bound derivation belongs to Phase C's
reopening, not to this revision's close. **Deletes nothing.**
⚠️ **Phase 0 runs CONCURRENTLY WITH PHASE A**, not with Phase B — B needs an archive that only A
produces. (The first draft said "A and B proceed in parallel", which was false.)

## Phase A — TRANSPORT + ARCHIVE (non-destructive)

- **A.1 — the archiver.** `zstd -12` each MAIN transcript older than `ARCHIVE_AFTER_DAYS` to
  `<ARCHIVE_ROOT>/<project-slug>/<session-id>.jsonl.zst`, appending
  **`(project_slug, session_id, sha256, bytes, mtime_ns, also_slugs, archived_at)`** to a manifest.
  ⚠️ **`project_slug` is part of the KEY, not decoration.** A session id is unique within a project
  directory; the plan must not assume it is unique across all 266 of them. Keying on
  `(session_id, sha256)` alone — the first draft's key — cannot disambiguate a collision and could
  match a transcript against another project's archive.
  Compression is measured: **6.08x on a 70.7 MB transcript, 1.5 s compress, 0.08 s restore,
  byte-identical, sha256 match**.
- **A.1a — skip what is already archived, without re-reading it.** The revision-1 code re-ran
  `zstd -12` over every eligible transcript on every run. A transcript is now skipped outright when
  the LATEST manifest row for its `(project_slug, session_id)` records the file's current `bytes`
  and `mtime_ns` and its `.zst` exists — no hash, no compression. Otherwise it is hashed; if the
  hash equals that latest row's `sha256` and the `.zst` exists, nothing is recompressed and no row
  is written; else it is compressed and a NEW row is appended.
  ⚠️ **Only the LATEST row per `(project_slug, session_id)` describes the object at
  `<slug>/<session-id>.jsonl.zst`.** A re-archive overwrites that object; an older row's bytes live
  on as a PRIOR VERSION in the bucket (it keeps all versions, A.3). `archived_at` is the
  COMPRESSION time, earlier than the upload, so it does not select a version by itself: an older
  version is found with `lsf --b2-versions` (each version listed with its upload time) or fetched
  with `--version-at` set to an instant AFTER that row's run finished and BEFORE the next run that
  rewrote the object. Locally, an older row's bytes are gone once overwritten.
- **A.1b — one object per file, not per hard link.** D-467 hardlinks worktree transcripts into
  their repo's lane: **117** MAIN transcript paths share **59** inodes (`find … -type f -links +1`),
  so the glob meets the same bytes under two slugs. The archiver groups by `(st_dev, st_ino)`, archives
  once under the first slug in sorted order, and records the others in `also_slugs` — a restore
  re-links them. De-duplicated, MAIN is **5,895 files / 9.82 GB**, not 5,953 / 13.86 GB (one
  predicate for both: `find ~/.claude/projects/ -mindepth 2 -maxdepth 2 -name '*.jsonl' -type f`).
- **A.1c — the two binaries are probed, never assumed** (`core/30-ops.md` FLOOR: a shelled-out
  binary gets a `shutil.which()` probe that fails fast): `zstd` and `rclone` missing ⇒ exit 1
  naming the binary, before anything is read.
- **A.1d — one run at a time.** `fcntl.flock(<ARCHIVE_ROOT>/.archive.lock, LOCK_EX | LOCK_NB)`; a
  second run (a hand run overlapping the timer) prints that the lock is held and exits 0 without
  touching the archive — the holder ships.
- **A.2 — the transport: `rclone copy` straight to B2, through ONE helper.**
  `rclone copy <ARCHIVE_ROOT>/ sessionb2:<bucket>/<prefix>/ --fast-list --transfers 4 --exclude /manifest.jsonl --exclude /.archive.lock --exclude /.snapshot-*/**`,
  then, after the rows are appended, `rclone copyto --no-check-dest <ARCHIVE_ROOT>/manifest.jsonl sessionb2:<bucket>/<prefix>/manifest.jsonl`
  (amended 2026-10-08: the snapshot exclude keeps A.4's frozen copies off the bucket, and
  `--no-check-dest` stops the manifest upload from depending on B2's download host, which copyto
  otherwise HEADs first — that HEAD hung 42 min on Gate A's first run behind an SNI filter).
  `<prefix>` is `SESSION_ARCHIVE_B2_PREFIX` (default `archive`).
  - **Every rclone call goes through `_rclone(verb, *args)`, and the verb is an ALLOW-list:**
    `copy`, `copyto`, `lsf`. Any other verb, and any argument whose option NAME (the text
    before any `=`) is `--b2-hard-delete` or starts with `--delete`, raises `ValueError` before a
    process starts — rclone accepts `--b2-hard-delete=true`, so an equality test is not enough. A deny-list of argv
    literals only covers the spellings someone thought of; an allow-list at run time does not
    depend on how a future caller spells the call. (`sync`, `move`, `moveto`, `delete`,
    `deletefile`, `purge`, `cleanup` — which on B2 deletes old versions — `rmdir`, `rmdirs` and
    `backend` are all refused by construction.)
  - **The remote lives in the CHILD's environment, never in argv and never in `rclone.conf`:**
    `RCLONE_CONFIG_SESSIONB2_TYPE=b2`, `RCLONE_CONFIG_SESSIONB2_ACCOUNT`,
    `RCLONE_CONFIG_SESSIONB2_KEY`. The child env is the parent env with every inherited `RCLONE_*`
    variable REMOVED first (so no `RCLONE_B2_HARD_DELETE` or stray remote can ride in), then these
    three added. argv is readable by every process on the box (`ps`).
  - **`SESSION_ARCHIVE_B2_ENDPOINT` is recorded, never passed.** It is B2's S3-compatible endpoint;
    rclone's native `b2` backend says of its own endpoint option "Leave blank normally"
    (`rclone help backend b2`).
  - **`--fast-list`** — one listing call per tree instead of one per directory; B2 bills class-C
    transactions per call. **No compression flag** — the payload is already zstd.
  - **The manifest ships SECOND and ONLY by `copyto`** (excluded from the `copy`). A failed
    `copyto` exits 1 with the rows kept — the `.zst` bytes already landed, so the rows are true —
    and the next run re-ships the manifest.
- **A.2a — credentials.** From the process environment; else from `SESSION_ARCHIVE_ENV_FILE`
  (default `/opt/fabrik/.env`), of which ONLY lines matching
  `^(export\s+)?SESSION_ARCHIVE_[A-Z0-9_]+=` are read (CR stripped, one matching pair of quotes
  stripped); every other line is ignored, so the archiver never loads the hub's other secrets.
  A missing or unreadable file, or either key absent or empty, is a loud exit 1 BEFORE any rclone
  call, naming `SESSION_ARCHIVE_B2_KEY_ID`, `SESSION_ARCHIVE_B2_APPLICATION_KEY` and the file path —
  never a value. The systemd unit carries NO `EnvironmentFile=` (that would load every hub secret).
- **A.2b — the verification verbs the gates use** (they share `_rclone` and the child env, so a
  gate never needs the key in a shell): `--remote-count` prints the number of `*.jsonl.zst`
  objects under the prefix and the sha256 of the remote `manifest.jsonl` (fetched by `copyto` to a
  temp file); `--fetch <path-under-prefix> <local-path> [--version-at <RFC3339>]` downloads one
  object, optionally as it was at that instant (`--b2-version-at`). Both exit non-zero when rclone
  does. Amended 2026-10-08, because `rclone copyto` exits 0 having written NOTHING when it cannot
  resolve the source as one object (absent, or the download host unreachable): `--remote-count`
  prints `remote_manifest_sha256 absent` when no manifest arrived, and `--fetch` refuses a target
  that already exists and exits 1 unless exactly one regular file arrived (a prefix is refused).
- **A.3 — the bucket, recorded rather than configured.** Bucket `wsl-ozgur` (id
  `d46ef77ceab3068aa018061b`, Private, SSE enabled, lifecycle **Keep all versions**, Object Lock
  **disabled**), created by the operator 2026-10-04. Its settings live in `/opt/fabrik/.env` as
  `SESSION_ARCHIVE_B2_BUCKET` / `SESSION_ARCHIVE_B2_BUCKET_ID` / `SESSION_ARCHIVE_B2_ENDPOINT` (not
  secrets). The application key is the operator's to create — restricted to `wsl-ozgur`, read +
  write; no existing key can reach this bucket (the youtube key is restricted to
  `youtube-pipeline`, fabrik's to `vps1-ocoron-backups`, both verified by `b2_authorize_account`
  2026-10-05). Revision 1's Backrest plan is withdrawn: nothing lands on vps1.
- **A.4 — env, not literals.** `ARCHIVE_ROOT`, `ARCHIVE_AFTER_DAYS` (default **0** since the
  2026-10-08 amendment, D-row of that date: the hub's named windows — infra, fleet, intel, kaizen —
  each run ONE session for days and never go idle for a day, so the first default of 1 would never
  have backed them up while open; each changed transcript now ships one snapshot per daily run,
  hashed and compressed from a frozen copy so its row describes exactly the uploaded bytes),
  `ARCHIVE_MAX_FILE_MB`, `SESSION_ARCHIVE_B2_BUCKET`, `SESSION_ARCHIVE_B2_PREFIX`,
  `SESSION_ARCHIVE_ENV_FILE`. The vps1 `ARCHIVE_REMOTE` is removed.
- **A.5 — failure is loud and non-destructive.** rclone non-zero on the `copy` (no network, bad
  key, quota) ⇒ exit 1 and no rows; on the manifest `copyto` ⇒ exit 1, rows kept (A.2). Nothing in
  Phase A can delete a transcript, an archived object or a remote object; the only thing it
  removes is its own `.snapshot-*` frozen copy (A.4), and a run holding the lock reaps one a killed
  run left behind. A transcript that vanishes between the scan and its copy is skipped; any other
  `OSError` (a full disk) is a clean exit 1.
- **A.6 — the marker.** A `README` in `~/.claude/projects/` stating the tree is data, not cache —
  aimed at the failure that actually happened: a human freeing disk space.
- **A.7 — the schedule: a systemd USER timer, catch-up friendly.** `session-archive.timer`
  (`OnCalendar=daily`, `Persistent=true` — a run missed while the machine was off fires at the next
  start of the user manager) starts `session-archive.service`, whose
  `ExecStartPre=-/opt/fabrik/scripts/sysadmin/sample_transcript_growth.sh` runs the sampler — the
  leading `-` makes systemd ignore its exit status, because the sampler runs under `set -euo
  pipefail` and a sampler error must never skip the backup — and whose `ExecStart` runs
  `/opt/fabrik/.venv/bin/python /opt/fabrik/scripts/sysadmin/archive_transcripts.py` — the MAIN
  checkout. Unit files are tracked in `scripts/sysadmin/systemd/` and installed by
  `scripts/sysadmin/install_session_archive_timer.sh`, which (1) refuses unless
  `loginctl show-user "$USER" -p Linger` reads `Linger=yes` (without linger the user manager does
  not start until a login, so the catch-up would wait for one — it prints the `loginctl
  enable-linger` remedy), (2) runs `systemd-analyze --user verify` on both units, (3) copies them to
  `~/.config/systemd/user/`, `daemon-reload`, `enable --now` (which also writes
  `timers.target.wants/`). Not cron: crontab writes are refused on this box's agent sessions, and
  cron has no catch-up. **Installed only after infra merges this branch** — before that the main
  checkout still holds the rsync transport.

**Gate A (runnable, from this worktree, before the merge):**
the archiver's first live run exits 0 · `.venv/bin/python scripts/sysadmin/archive_transcripts.py --remote-count`
prints a count **≥ 1** that equals `find ~/.claude/archive -name '*.jsonl.zst' | wc -l`, and a
manifest sha256 equal to `sha256sum ~/.claude/archive/manifest.jsonl` (amended 2026-10-08: on a
network that blocks B2's download host the fetch reads `absent`, so the remote manifest's SIZE from
an API `lsf` stands in, equal to the local file's) · a SECOND run immediately after appends rows
only for transcripts written since the first (amended 2026-10-08: with the window at 0 the open
windows always change, so "0 rows" cannot hold; every unchanged transcript is skipped) · `systemd-analyze --user verify
scripts/sysadmin/systemd/session-archive.service scripts/sysadmin/systemd/session-archive.timer`
prints nothing · `test -s ~/.claude/projects/README` · the Phase-A test file green. **Zero
deletions.** `/fabrik-review-scoped` at the boundary.

**Gate S (runnable, after infra's merge — the plan's last step):** `bash
scripts/sysadmin/install_session_archive_timer.sh` exits 0 · `systemctl --user list-timers
session-archive.timer` shows a next run · `systemctl --user start session-archive.service` then
`systemctl --user show session-archive.service -p Result` reads `Result=success`.

## Phase B — PROVE THE RESTORE (still non-destructive)

The local round trip is measured. **The leg back from B2 is not, and it is the one that matters.**

- **B.1** Pick an archived transcript whose live file still hashes to its latest manifest row and
  download its object **from the bucket** — `archive_transcripts.py --fetch /<slug>/<sid>.jsonl.zst
  <scratch>/r.zst` — never the local `~/.claude/archive` copy, which would prove the wrong hop.
- **B.2** `zstd -d <scratch>/r.zst -o <scratch>/r.jsonl`, then `cmp <scratch>/r.jsonl <live original>`
  and `sha256sum <scratch>/r.jsonl` against the row's `sha256`.
- **B.3** Embed the verbatim command output in the Evidence section.
- **B.4** Prove the archive stands alone — a prior version, restored without its live file. In an
  ISOLATED prefix (`SESSION_ARCHIVE_B2_PREFIX=restore-proof`, a scratch `CLAUDE_PROJECTS_DIR` and
  `ARCHIVE_ROOT`, `ARCHIVE_AFTER_DAYS=0`): archive a synthetic transcript (run 1), append a line to
  it, archive again (run 2), delete the scratch source, then `--fetch /<slug>/<sid>.jsonl.zst out.zst
  --version-at <T>` — `T` captured from the SERVER's clock after run 1 returns — `date -u -d "$(curl -sI https://api.backblazeb2.com/ | sed -n 's/^[Dd]ate: //p')" +%Y-%m-%dT%H:%M:%SZ` converts the RFC 7231 `Date` header to the RFC 3339 instant `--version-at` takes, then add 2 s (the header is floored to the second; B2 stamps a version with its own upload time, and this box ran 2 min 49 s behind it on 2026-10-12, so a `date -u` instant read "absent") — with at
  least 4 s before run 2 starts (`archived_at` is the compression time, not the upload, § A.1a) —
  and match its decompressed sha256 to the RUN-1 row —
  the bytes no file on disk holds any more. (One live run cannot do this: a bucket version exists
  only after the same object is written twice.) The proof objects stay in `restore-proof/`; they
  are tiny and the transport cannot delete them.
- **B.5** `--remote-count` alone fetches the manifest object from the bucket and prints its sha256 (no parse) and a bucket-wide
  object count (never an object list or a key lookup): with only the bucket, the listing works and the manifest comes down — the
  two things a restore needs before B.1's fetch, which is what shows B.1's key is present.

**Gate B (runnable):** B.2's `cmp` exits 0 and its sha256 equals the row's; B.4's decompressed
sha256 equals the run-1 row's and differs from the run-2 row's; outputs embedded.
⚠️ A failed or skipped Gate B is a `BLOCKED:` escalation.

## Phase C — ROTATE, TAG, PRUNE (reopened 2026-10-11, D-736) — EXECUTED 2026-10-12 (Gate C passed)

> **C.0–C.4 EXECUTED 2026-10-11** (D-742): the archive current (310 rows), the agent tag and the ROTATE advisory
> (aa876c94b), the pruner and its subagent tier (09624683c) with the unit on `--dry-run`, the contract in the docs
> and the four requests (1416db236); three full `/fabrik-review` loops, each closing at confirmed 0 (receipts
> `…-phase-2-c1-review.md`, `…-phase-3-c2-c3-review.md`, `…-phase-5-c4-review.md`). **Gate C PASSED 2026-10-12**
> (§ Evidence — Phase C, "Gate C — execution log"): steps (0)–(6) executed — `W-c49a7adf`, `W-18d6d1ae`, `W-0fc6fe12`
> closed at 59a2a136a; the canary deleted 10 transcripts and restored 2 byte-exact; the unit runs `--apply --nightly`.
> Status stays IN-PROGRESS until the first nightly apply (Tue 2026-10-13 00:00 + the timer's up-to-15-min delay) is
> read; then EXECUTED and archived.

**What changed since the deferral.** The deferral's three tripwires were disk, a proven restore and
searchability. Disk never fired; what fired instead was the VS Code extension host: it OOM'd four
times on 2026-10-10/11 (`JavaScript heap out of memory` at its 4 GB heap, `SIGABRT`,
`remoteagent.log`), fed by 26.4 GB of local transcripts in 36,882 files, the four named hub windows
at 1.53 / 1.16 / 0.80 / 0.08 GB each — the extension loads every listed session's history
(anthropics/claude-code #89075) and crash-loops past 2 GiB (#97229). The operator's ruling (D-736)
sets the contract this phase implements. Everything here is grounded in § Evidence — Phase C.

**The contract, as the operator stated it, in the terms the code uses:**
- **Off-box: everything.** Every MAIN transcript of every repo keeps shipping to B2 nightly (Phase A,
  live). Subagent transcripts, tasks and shell snapshots are never archived (they never were).
- **Local: ~3 days.** A MAIN transcript whose `mtime` is older than **3 days** is deleted locally
  once — and only once — the archive provably holds its bytes (C.2). What the pruner NEVER touches:
  an OPEN session — a live `claude` process still carries its id (the registry's `pid`+`procStart`,
  C.2.1 r2) — however old; a file written in the last 3 days; the newest session of every project
  slug AND of every tagged agent (C.2.1 r3). What it DOES touch: a session older than 3 days whose
  window is gone (a reload or an extension-host crash ends every session in a window,
  `worktree_transcript_link.py:9-10`) and that is neither a project's nor an agent's newest — it
  leaves the `/resume` picker and is one `prune_transcripts.py --restore <session_id>` (C.2.5) or one
  `search_chats` away. That is the operator's "3 days might be fine" taken at its word; the restore
  verb is what makes "be extremely careful" hold for the rest.
- **Named histories for infra, kaizen, intel, fleet.** A session is tagged with its agent name in
  the manifest (C.1); a named window ROTATES to a fresh session before its file reaches the sizes
  that crash the extension (C.1.3), so "infra's history" becomes a chain of tagged sessions, each
  archived on its night and pruned after 3 days, instead of one file that grows for months.
- **Not scratchpad, not subagents.** Scratch is already swept (`scratch_sweep.py`); subagent
  transcripts get a 3-day local cliff with no archive (C.3).
- **The three governance files state the rule** (C.4): hub `CLAUDE.md`, `templates/governance/
  CLAUDE.md` (every /opt project; infra's sync path), fabrik-lib's `CLAUDE.md` (another repo).

**Why rotation, not slimming.** Measured on infra's 1.53 GB: 73% is tool results, attachments and
tool calls; 2% is the operator's own text; 222 compact boundaries, 5 MB after the last one;
duplicate rows from the `/compact` re-append bug (#92089) are 9.7%. Deduplication would recover a
tenth; the rest is exactly the tool output session-recall indexes. Rotation makes the live file
small by construction and leaves the content where search already is.

### C.0 — Verify the archive is current for the hub windows (read-only, 10 min) — ✅ EXECUTED 2026-10-11 (the C.1 commit; read-only, no diff of its own)
Appetite: 10

> **Executed 2026-10-11 13:34–13:44 UTC:** rather than wait for the 00:00 timer, `systemctl --user start
> session-archive.service` ran the installed unit by hand (9,769 MAIN transcripts eligible, **310 new
> manifest rows**, `Finished` rc 0). The probe then showed every hub window with a fresh row —
> infra `dd3c06d1` 1,530,478,917 B, intel `4e90716e` 1,158,228,129 B, fleet `1970a0ff` 803,835,706 B,
> kaizen `5fa5812d` 79,177,890 B, all `archived_at` 2026-10-11T13:34/35Z — intel and kaizen unchanged
> since (A.1a will skip them tonight), infra and fleet already grown (open windows, the daily snapshot
> catches them). Not BLOCKED: the archive is current. Probe script: `scratchpad/c0_probe.py`
> (identity rows → session ids → `stat` vs the latest manifest row; metadata only).

The 2026-10-11 00:17 run failed on DNS (`lookup api.backblazeb2.com … read udp`), systemd's 15-min
restart succeeded with 51 rows, and the hub windows had no new row that night. Not a defect: they
had **0 records** between the 2026-10-10 00:43 archive and the 00:34 run (their sessions died in the
2026-10-10 00:34 crash and were reopened 2026-10-11 10:36), so A.1a's unchanged test skipped them
correctly (§ Evidence — Phase C, probe 1). C.0 just re-runs the probe after tonight's timer and
records the four fresh rows; a hub window with NO row for two consecutive nights while its file
changed is a `BLOCKED: missing infra — the archive is not current` before anything else in Phase C.

### C.1 — Tag by agent, rotate the named windows (non-destructive) — ✅ EXECUTED 2026-10-11 (aa876c94b; review fixes 14701439e · 4ea95fa87 · 6898b3244; receipt d2ab1d7fe)
Appetite: 90

> **Executed 2026-10-11:** `scripts/sysadmin/transcript_size_check.py` (new, the user-level UserPromptSubmit hook),
> `archive_transcripts.py` (`agent` key via the identity row else the registry join on pid + procStart as integers;
> the `--agent <name>` verb), `install_user_hooks.py` wiring, 20 new tests seen red first in a throwaway worktree
> (94 pass over the three modules), docs rows (INDEX, hooks-index, session-history-retention, CONFIGURATION,
> `.env.example`). The full `/fabrik-review` ran 4 rounds — 18 → 6 → 1 → 0 confirmed, 25 FIXED / 0 REFUTED — and its
> receipt `docs/development/reviews/2026-09-06-plan-1-session-history-retention-phase-2-c1-review.md` is CONVERGED
> with the post-flip `final_gate.py --check` embedded. Nothing deleted, nothing under `~/.claude/projects` touched.

- **C.1.1 `agent` in the manifest row.** `archive_transcripts.py` reads
  `~/.claude/state/agent-identity.jsonl` (one JSON per line: `session_id`, `name`, `pid`,
  `pid_start`, `toplevel`, `at`; written by `scripts/whoami_agent.py`; 42 rows today) and writes
  `"agent": "<name>"` into each new manifest row (absent when no binding names the session). The
  latest `at` per `session_id` wins. Rows already shipped are not rewritten (append-only manifest).
  **The binding is keyed by SESSION ID, and `/clear` mints a new one** — `resolve_agent_name()`
  (`scripts/whoami_agent.py:259-274`) matches `row["session_id"] == CLAUDE_CODE_SESSION_ID`; `pid` +
  `pid_start` is only the collision/liveness test (`:134-152`, `:356-373`). So a rotated window's
  new session has no row. One function, `agent_for(session_id)`, resolves in two legs: (1) the latest
  identity row for that `session_id`; else (2) the REGISTRY JOIN — the `~/.claude/sessions/<pid>.json`
  entry whose `sessionId` is this session's, joined on `(pid, procStart)` to the identity row with
  the same `(pid, pid_start)` (the `claude` PROCESS survives `/clear`; both fields are
  `/proc/<pid>/stat` field 22, compared as INTEGERS — the registry stores `procStart` as a JSON
  string, `_pid_start` returns an int (`whoami_agent.py:118-131`); asserted at build on one live
  window); else no key. The join is read-only and never writes the identity file.
- **C.1.2 `--agent <name>`.** A read-only verb: the manifest's rows for that agent, newest first —
  `session_id`, `project_slug`, `bytes`, `archived_at`, and whether the local file still exists.
  "infra's history" is this list; each session is readable through session-recall's `get_chat`
  while indexed, and restorable with `--fetch` from any network that reaches the download host.
- **C.1.3 The rotation advisory — a USER-level `UserPromptSubmit` hook, every window, every repo.**
  New `scripts/sysadmin/transcript_size_check.py`, wired by `scripts/sysadmin/install_user_hooks.py`
  beside `selfwatch_check.py` (the user-level hook list, `~/.claude/settings.json`; hub-local, not a
  governance-sync path). It reads the hook JSON's `transcript_path` (the field
  `worktree_transcript_link.py:92` already reads from the same payload) and `session_id`, stats the
  file, and when the size is ≥ `ROTATE_ADVISE_MB` (default **200**) prints ONE line:
  `ROTATE: this session's transcript is <N> MB — run `/clear <agent>-<YYYY-MM-DD>` now, then
  `python3 /opt/fabrik/scripts/whoami_agent.py --as <agent> --force` (safe here: the name's holder
  is pid <P>, this window's own claude process); the previous session stays resumable and is
  archived tonight (D-736)`. `<P>` is this window's `claude` pid, found by the same `/proc` ancestry
  walk `whoami_agent._session_pid` uses (`:81-107`), and `<agent>` is `resolve_agent_name()` or, when
  that is empty, the identity row joined on `(pid, pid_start)` — the hook never guesses a name.
  Fail-open: any error, exit 0, no output. **Stamped,
  never per-prompt:** `~/.claude/state/rotate-advised/<session_id>` records the 100 MB step last
  advised; the line prints only when the size crosses a NEW step (200, 300, 400 …), so a window that
  does not rotate hears it once per 100 MB, not on every prompt — `install_user_hooks.py:37-42`
  records why: the bare per-prompt shape was measured and rejected for `scratch_sweep` ("9 of 9 live
  sessions fired on EVERY prompt … wallpaper is how enforcement dies", D-184/D-187); the stamp is
  this hook's counter-measure to that shape (its fire rate is bounded by steps, by construction),
  not a repeat of that measurement. The read-compare-write runs under an `flock`, so two windows of
  one session print a step once; an ambiguous registry join tags nothing (review 2026-10-11).
  Why 200: the extension crashed users at 467 MB (#23953) and loops past 2 GiB; a busy hub window
  grows ~25 MB/day (infra: 1,528 → 1,530 MB in a day of light use; the 2026-10-05 → 10-11 delta
  was ~170 MB), so 200 MB is roughly a week and keeps every window an order of magnitude under the
  first crash report. `/clear` starts a new session and keeps the previous one resumable
  (code.claude.com/docs/en/commands: *"`/clear [name]` — Start a new conversation with empty
  context. Pass a name to label the previous conversation in the `/resume` picker"*). The agent
  binding does NOT follow `/clear` (C.1.1: keyed by session id), and a plain re-bind in the new
  session is REFUSED — `_bind_locked` (`whoami_agent.py:356-373`) finds the pre-`/clear` row holding
  the same name with the same live `pid`+`pid_start` and answers "held by a LIVE session" (executed
  in round 1 with a scratch store). Hence `--force` in the ROTATE line — and `--force` skips the
  WHOLE collision block (`:356`), the liveness check included, so a genuinely different live session
  on the same name would be overwritten silently: that is why the line prints the holder's pid and
  says it is this window's, and why the operator types `--force` only after a plain
  `whoami_agent.py --as <agent>` (no `--force`) in the new session has been REFUSED naming that same
  pid — the refusal text carries it (`:367-370`); `--who` prints only the resolved name (`:424-427`)
  and cannot serve here. The two pids must agree. The row
  records `force: true`, and the manifest's registry join (C.1.1) tags the new session even when the
  operator skips the re-bind. The permanent fix — a holder row
  with the same `pid`+`pid_start` IS this session's predecessor, bind without `--force` — is a
  `scripts/whoami_agent.py` change, a governance-sync path (`.pre-commit-config.yaml:164`): sent to
  infra as a `request` (D-441) in C.4, not edited here.
- **C.1.4 Rotate the four windows NOW, before any deletion.** The operator runs `/clear infra-2026-10-11`
  then `python3 scripts/whoami_agent.py --as infra` (refused, naming the holder's pid), and `--force`
  only when that pid is the one the ROTATE line printed (and kaizen, intel, fleet alike) once this
  phase's advisory ships; the old sessions archive that night and fall under C.2 three days later.
  This alone ends the startup OOM: the sidebar then lists files of a few MB, not GB. It is a one-time
  act plus the advisory; nothing forces a later rotation (Residual risk 10 names the backstops).

**Gate C.1 (runnable):** `pytest tests/test_archive_transcripts.py -k agent` green after being seen
red (a row for a bound session carries `agent`; an unbound one carries none; the latest binding
wins); `pytest tests/test_transcript_size_check.py` green after red (≥ threshold prints the ROTATE
line with the size; below prints nothing; a missing/unreadable path prints nothing, exit 0; the
same step twice prints once; a new step prints again); `pytest tests/test_archive_transcripts.py -k
registry_join` green after red (a session with no identity row but a registry entry joined on
`pid`+`procStart` gets the name; neither ⇒ no key); `pytest tests/test_archive_transcripts.py -k
agent_verb` green after red (`--agent <name>` lists only that agent's rows, newest first, with the
local-file flag); `python3 scripts/sysadmin/install_user_hooks.py --check` exit 0 with the new hook
listed (`tests/test_install_user_hooks.py`).

### C.2 — The pruner (the ONLY deleter of MAIN transcripts under `~/.claude/projects`) — ✅ EXECUTED 2026-10-11 (09624683c; review fix 6f79449f1; receipt e094b5bdd)
Appetite: 150

> **Executed 2026-10-11:** `scripts/sysadmin/prune_transcripts.py` (new) — the eight fail-closed clauses in this
> section's order, the last look (stat + OPEN re-read before EACH unlink), the fsynced `pruned.jsonl` row before
> every unlink, the cap and the `--expect` echo, the `prune-log.jsonl` summary row written in a `finally`,
> `--restore` / `--verify-ledger` / `--status`, the archiver's lock; `_group_by_inode` skips (and names) a vanished
> path; the unit's second `ExecStart=-… --dry-run`; `psycopg2-binary` declared, `uv.lock` regenerated; the
> `.env.example` / CONFIGURATION rows. Graders: 49 in `tests/test_prune_transcripts.py` + 4 in
> `tests/test_archive_transcripts.py`, every clause seen red (30/30 then 9/9 mutations red in throwaway worktrees).
> **Gate C.2 dry-run over the live tree:** 9,742 inodes scanned · deletable 0 · not-indexed 7,082 ·
> newest-of-slug 1,618 · in-window 1,040 · newest-of-agent 2 · 22 files over 200 MB reported · exit 0 — nothing
> deleted (rule 8 refuses everything until session-recall's ingest and the DSN exist, as this section predicts).
> The full `/fabrik-review` over C.2 + C.3: 16 raised / 15 confirmed / 1 refuted in round 1, all fixed in
> 6f79449f1; round 2 confirmed 0 — receipt
> `docs/development/reviews/2026-09-06-plan-1-session-history-retention-phase-3-c2-c3-review.md` CONVERGED.

New `scripts/sysadmin/prune_transcripts.py` — `--dry-run` is the default and prints a table; `--apply`
deletes. It runs after the archiver from the same unit as a second `ExecStart=` line in
`session-archive.service`, prefixed `-`: `man systemd.service` (ExecStart=) — *"If more than one
command is specified, the commands are invoked sequentially in the order they appear in the unit
file. If one of the commands fails (and is not prefixed with "-"), other lines are not executed, and
the unit is considered failed."* So a night whose archive failed prunes nothing, and a pruner
refusal (exit 3, reason printed) never fails the unit — without the `-`, `Restart=on-failure` would
re-run the ARCHIVER up to `StartLimitBurst=4` times for a pruner outcome. The `-` also hides a
crash (exit 1) from systemd, so the pruner reports for itself: `main()` catches every exception and,
BEFORE exiting, appends one summary row to `~/.claude/archive/prune-log.jsonl` — `run_at`, `mode`,
`deleted`, `deferred` (deletable beyond this run's cap), the refusals by reason, `over_threshold`
(written by dry-run and apply runs only — `--restore`, `--verify-ledger` and `--status` write none;
an exception in those three exits 1 with the error on stderr and no row),
(every MAIN transcript larger than `ROTATE_ADVISE_MB`, Residual 10's backstop), and `error` with the
traceback text when there was one; `prune_transcripts.py --status` prints the last row AND the last
APPLY row (the nightly dry-run writes rows of its own), Gate C (5) reads the apply row, and the
retention doc names `--status` as the morning check. Exit codes: 0 = ran (0 or more
deletions); 3 = refused (`--expect` mismatch, lock held, no manifest, `--verify-ledger` MISSING,
`--restore` with a survivor of another sha256, or whose `--fetch` failed — the object absent from
the bucket, the download host unreachable, or rclone's own failure such as a revoked key; A.2's
`--fetch` exits non-zero for all three — 1 when no file arrived, non-zero when rclone fails (A.2 fixes
no code for that case) — and the pruner treats any non-zero `--fetch` as this refusal, naming the
three causes and passing `--fetch`'s stderr through: the archiver's own line for the first two, where
rclone exited 0 and wrote nothing, whatever `--fetch` prints for the third);
1 = error (a dry-run or apply run writes its row first; the other verbs write none); 2 = usage.
The pruner takes the archiver's own lock (`ARCHIVE_ROOT/<LOCK_NAME>`, the same `flock`) so a hand-run
`--apply` can never overlap the timer's archiver; and the archiver's `_group_by_inode`
(`archive_transcripts.py:200-206`) gains a `FileNotFoundError` skip for a path that vanished between
its scan and its `stat` (today that raises outside `archive_one`'s handler, `:428`, and would abort
the night's run). **Other deleters, inventoried:** the crontab's
`17 5 * * * find ~/.claude-youtube-headless/projects -type f -mtime +1 -delete` removes a headless
pipeline's own `claude -p` transcripts in a SEPARATE config dir after one day — never archived, not
the operator's chat, out of D-736's scope and left as is; `~/.claude/bin/claude-reboot-sweep.sh`
deletes only its lock and marker files (`:95-241`) and SCANS transcripts (`:259`) to list cut
sessions — it removes none. The unit edit reaches `~/.config/systemd/user/` only through
`install_session_archive_timer.sh` run from the MAIN checkout after the merge (its header: *"Run
from the MAIN checkout after the archiver change is merged"*) — Gate C step (0).

- **C.2.1 The invariant, in code — every clause fail-CLOSED.** A local MAIN transcript is deleted
  only when ALL hold:
  1. `mtime` older than `PRUNE_AFTER_DAYS` (default **3**);
  2. **not OPEN**: no `~/.claude/sessions/<pid>.json` entry carries its `sessionId` with a live
     process — `/proc/<pid>` exists AND the entry's `procStart` equals `/proc/<pid>/stat` field 22,
     both as integers (the registry stores it as a string; a missing or non-numeric `procStart`
     counts as alive: fail-closed; a recycled pid does not; `pidDomain` is recorded in the ledger
     row, not consulted — the test is the live `/proc`, and an entry from another boot has no live
     pid with its `procStart`) — and no
     `agent-identity.jsonl` row carries its `session_id` with `pid`+`pid_start` alive the same way
     (the identity file trims rows after 30 days, `whoami_agent.py:53`, so the registry is the
     primary test and the identity row the belt). Measured 2026-10-11: 1,401 entries, 9 live pids,
     6 of them with a matching `procStart`, 6 `pidDomain`s (= boots). The registry is ONE directory
     for every account slug (`~/.claude-fleet/<slug>/sessions` → `~/.claude/sessions`, Evidence
     probe 5), so a pinned session is seen;
  3. **not the newest session of its project slug, and not the newest of its agent** (the `agent`
     tag, C.1.1) — a long-idle project keeps its resume point, and each hub agent keeps its latest
     chain link even though the four hub windows share the `-opt-fabrik` slug;
  4. its CURRENT sha256 equals the latest manifest row's `sha256` for `(project_slug, session_id)`
     (re-hashed at delete time, never trusted from archive time);
  5. the `.zst` under the ROW's `project_slug` (objects exist only under the primary slug,
     `archive_transcripts.py:242-244`; an aliased `also_slugs` row points there too) exists,
     decompresses, and the sha256 of its CONTENT equals the row's and the file's — `zstd -t` alone
     proves the frame, not the bytes: with `also_slugs` aliasing, a worktree name whose hard link
     broke keeps resolving to a row whose object was later rewritten for the primary (executed in
     round 1: `zst exists True · decompresses to the worktree bytes False`);
  6. the bucket lists the object under the ROW's `project_slug` with the SAME size and SHA1 as the
     local `.zst` (`rclone lsf --files-only --format psh --hash SHA1 <prefix>/<slug>/`, one listing
     per slug — works from this network for small AND multi-part objects, § Evidence probe 3; the
     listing failing ⇒ nothing in that slug is deleted);
  7. every name of the inode — found at PRUNE time by `(st_dev, st_ino)` over the whole tree, never
     from the manifest's `also_slugs` (a twin `worktree_transcript_link.py` created after the
     archive run has no alias) — passes 1–3, and every name's `(slug, session_id)` has a row; one
     name without a row ⇒ the inode is skipped. The names are unlinked in one pass after ONE ledger
     row naming them all; two `unlink()` calls are not atomic, so a kill between them leaves one
     twin and the row — `--restore` re-creates the missing name as a hard link to the surviving
     twin when that twin's sha256 equals the row's, so the names end as one inode again; a
     survivor whose sha256 differs (resumed and appended after the kill) is a REFUSAL — the
     survivor is the newer history and tonight's archive takes it (C.2.5 never overwrites an
     existing path);
  8. **session-recall holds it**: an `index_state` row (`/opt/session-recall/db/schema.sql:55-62`:
     `file_path`, `inode`, `size`, `mtime`, `lines_ingested`) whose `inode` is the file's `st_ino`
     and whose `size` is the file's current size — looked up BY INODE, never by path, because
     session-recall keeps ONE row per inode and prefers the `--claude-worktrees-` name
     (`ingest/reindex.py:298-312`, `_one_name_per_inode`), so a hub window's `-opt-fabrik` name has
     no row of its own. Same inode and size is the ingest's own "indexed to the end" key
     (`reindex.py:239-248`). Not `sessions.last_at`: that is the newest TEXT turn
     (`ingest/parse.py:108-122` drops tool-result, tool-use-only and system lines), so it is
     legitimately older than the file's last line. The pruner reads it through `psycopg2` (2.9.12 in
     the hub venv; today only a transitive pin in `uv.lock` as `psycopg2-binary`, so C.2 DECLARES it in
     `pyproject.toml` — the one dependency edit this plan authorises — and regenerates the lock) with
     session-recall's EXISTING read-only role
     `recall_ro` (`schema.sql:85-100` — the role at `:85-94`, its `SELECT` on `sessions`, `turns`,
     `index_state`, `index_run` at `:100` —
     the MCP server's own role; nothing is created or narrowed), whose DSN the operator copies into
     `/opt/fabrik/.env` as `SESSION_RECALL_RO_DSN`. The pruner's own env reader — the archiver's
     `_ENV_LINE` shape (`archive_transcripts.py:70`) with the prefixes `SESSION_RECALL_RO_DSN`,
     `PRUNE_` and `ROTATE_ADVISE_MB`; the hook uses the same reader — is how `PRUNE_AFTER_DAYS`,
     `PRUNE_MAX_PER_RUN` and `ROTATE_ADVISE_MB` reach a unit with no `EnvironmentFile=` (rows in
     `.env.example` + `docs/CONFIGURATION.md`). No DSN, no connection, no row for the inode, or a size
     mismatch ⇒ not deleted, reason `not-indexed`. The index is fresh on
     USE, not by schedule — session-recall's tools run a bounded incremental reindex before answering
     (`README.md:34`), and nothing else on this box runs `python -m ingest.reindex` (no timer, no
     cron — round-1 probe) — so until C.4 (c)'s nightly ingest exists this clause refuses every
     deletion: the correct failure, since "searchable through session-recall" (C.2.4) is a promise
     the pruner must not make for it. The Digest's rows bind this one query — the DSN from the
     environment, never a literal (`core/10-python.md:129`), no secret in the script
     (`core/35-security-auth.md:267`); `core/25-data-postgres.md` binds nothing here (§ CONSTRAINTS
     DIGEST).
  **Order and the last look:** rules 1–3 and 8 (cheap) → 4 (the hash, seconds on a GB file) → 5–6
  → then, immediately before the unlink, a re-`stat` (size and `mtime` unchanged since the hash) and
  rule 2 again; a change ⇒ skipped with reason `changed-under-hash`. A deletion appends a row to
  `~/.claude/archive/pruned.jsonl` (`project_slug`, `session_id`, `sha256`, `bytes`, `paths`,
  `agent`, `pruned_at`) — the restore list `--restore` reads (C.2.5); the file sits in
  `ARCHIVE_ROOT`, so `ship()` uploads it nightly as one more small object, deliberately: the restore
  list is off-box too.
- **C.2.2 `--apply` is deliberate, and CAPPED on every path.** Every run — dry or apply, hand or
  nightly — orders the deletable files OLDEST `mtime` first and takes at most `PRUNE_MAX_PER_RUN`
  (default **200**) of them as THIS RUN's set; the rest are reported as `deferred`. The dry-run table
  prints both numbers: deletable in total, and this run's count. A hand run requires `--apply
  --expect <N>` equal to this run's count; a mismatch deletes nothing and prints both numbers;
  `--max <M>` changes this run's size (and so the count `--expect` must match) — `--max 10
  --expect 10` is the 10 oldest, the canary. The unit runs `--apply --nightly` (no wrapper script —
  the mode lives in `prune_transcripts.py`, in File Scope): it takes the oldest 200 and writes the
  summary row, so the ~7,200-file backlog (Evidence probe 2: 9,687 MAIN files, 2,470 inside the
  window) drains in about 36 nights, never in one step. COBRA, stated honestly: a nightly mode that
  computes its own set always agrees with itself, so "the operator saw the count" is NOT what the
  nightly path proves — its brake is the cap, the summary row and the ledger row per deletion. On
  the hand path `--expect` is an ECHO, not a proof: this run's count is `min(cap or --max,
  deletable)`, which is 200 on every night the backlog exceeds the cap and `M` under `--max M`, so
  `--expect` can be typed without reading anything; it guards a stale or mistyped command (the
  count moved since the table was read), nothing more. The proof Gate C demands is the pasted
  dry-run table, and the hand path's real brake is the cap. A
  "bytes within 1% of the dry-run" check was dropped: both figures come from one process over one
  tree, seconds apart, and could never disagree.
- **C.2.3 Graders, each SEEN RED first** (`core/45-testing-strategy.md:22`): a file inside the
  window → never offered · an OPEN session (live pid) → never offered, however old · the newest
  session of a slug → never offered · absent from the manifest → not deleted · archived at sha A
  then mutated to sha B → not deleted · `.zst` missing → not deleted · `.zst` corrupt → not deleted
  · remote listing absent / size differs / SHA1 differs → not deleted · listing call fails → nothing
  in that slug deleted · two names on one inode where one fails → neither deleted · a name whose
  `(slug, session_id)` has no row → the inode skipped · the `.zst` decompresses to other bytes →
  not deleted · an OPEN session by the identity row alone (registry entry dead) → not deleted · a
  registry entry with a live pid but another `procStart` → not OPEN · the newest of an agent, older
  than another agent's session in the same slug → kept · no `index_state` row for the file's inode,
  or its `size` differs from the file's, or no DSN → not deleted (`not-indexed`) · the file changed
  between the hash and the unlink →
  `changed-under-hash`, not deleted · `--apply` without `--expect` or with the wrong count → nothing
  deleted · more deletable than the cap → exactly the oldest cap-many deleted, the rest `deferred`,
  on the hand AND the nightly path; `--max` widens a hand run · the archiver lock held → exit 3 · an
  exception in a dry-run or apply run → the summary row carries `error`, exit 1, and every unlinked
  name is in a
  ledger row written before it · `--status` prints the last summary row · `--verify-ledger` lists
  every `pruned.jsonl` row's object with its size and SHA1, exit 3 on any MISSING · a deletion writes
  its `pruned.jsonl` row
  BEFORE the unlink (a crash between them leaves a row with the file still present, never the
  reverse) · `--restore` with a survivor carrying the row's sha256 → the missing names hard-linked to
  it, no fetch, and the inode's `mtime` is now · `--restore` with a survivor of another sha256 →
  exit 3, nothing written · `--restore` whose `--fetch` fails (absent object, unreachable host, or an
  rclone failure) → exit 3, nothing written, and stderr names the three causes and carries
  `--fetch`'s stderr (the archiver's line; whatever `--fetch` prints when rclone failed) · `--restore <session_id>` re-creates every path of the row byte-identical to the row's
  `sha256` (C.2.5) · `--agent <name>` lists only that agent's rows, newest first (C.1.2) · the unit
  file's second `ExecStart` carries the `-` prefix and follows the archiver's line.
- **C.2.4 What the operator sees afterwards.** The VS Code picker lists each project's sessions
  from the last 3 days plus its newest and each agent's newest; older sessions are reached through
  session-recall (`search_chats` / `get_chat`, their text is in Postgres — rule 8 guarantees the
  index holds them) or put back into the picker with `--restore` (C.2.5).
- **C.2.5 `--restore <session_id>` — the restore list's one consumer.** Reads the `pruned.jsonl`
  row (local first, else the bucket's copy), fetches the object with the archiver's `--fetch`
  (needs the download host — § Phase B; a `--fetch` that exits non-zero — absent object, unreachable
  host, or rclone's own failure, which the pruner does not tell apart — is a plain refusal, exit 3,
  naming the three causes with `--fetch`'s stderr passed through),
  decompresses to the first missing path the row names and hard-links every other missing path to it;
  when a path of the row still EXISTS with the row's sha256 (a half-unlinked twin), the missing
  names are hard-linked to that survivor and nothing is fetched; when a path still exists with
  ANOTHER sha256, `--restore` refuses (exit 3) naming it — that survivor is live history, not a
  restore target. It verifies the sha256 against the row, then sets the inode's `mtime` to now
  (a hard link inherits the survivor's old `mtime`; without the touch the names would be offered
  again at the next dry-run), and reports. Restored files are ordinary transcripts: `/resume`
  lists them; the archiver re-hashes them once a night (A.1a's outright skip needs the manifest's
  `mtime_ns`, which the touch changed; the hash matches, so no new row and no upload — one hash per
  night is the price of a restore), and after 3 more days the pruner may offer them again. `--restore` never deletes and never overwrites an existing path.
- **C.2.6 `--verify-ledger` — the restore list's integrity check.** Re-runs rule 6 over every
  `pruned.jsonl` row: the object under the row's `project_slug` is listed with the row's size and
  SHA1 (one `rclone lsf` per slug), each row printed `OK` or `MISSING`; any `MISSING` ⇒ exit 3. It
  deletes nothing and needs no download host. Gate C (4) runs it; the retention doc names it beside
  `--status` as the morning check.

**Gate C.2 (runnable):** `pytest tests/test_prune_transcripts.py` green after each grader was red;
`python3 scripts/sysadmin/prune_transcripts.py` (dry-run) over the live tree prints its table and
exits 0 with **0 deletions** and the counts of candidates per refusal reason (rule 8 refuses all
of them until session-recall's ingest timer exists — that count is the evidence the clause works);
`pytest tests/test_archive_transcripts.py -k vanished` green after red (the `_group_by_inode` skip);
the unit-file test asserts `Type=oneshot`, the archiver's `ExecStart` first and the pruner's
`ExecStart=-` second; `ruff check` + `ruff format --check` clean. **No `--apply` in this gate.**

### C.3 — Subagent transcripts, tasks, shell snapshots: a 3-day cliff, no archive — ✅ EXECUTED 2026-10-11 (09624683c, with C.2; receipt e094b5bdd)
Appetite: 60

> **Executed 2026-10-11:** `prune_transcripts.py --tier subagents` (included by `--nightly`): sidechains older than
> the window whose parent is not OPEN and not in flight (the stop-decider's rule, `subagent_running` copied), plus
> `~/.claude/tasks/` and `~/.claude/shell-snapshots/` entries by age — one `pruned.jsonl` row each, no cap, never
> archived. Graders red-first (a young sidechain stays, an in-flight one stays, a live parent keeps all, tasks and
> snapshots by age). Reviewed with C.2 (the one review this section's gate names); its one candidate (a parent-OPEN
> test for tasks/snapshots) was refuted against the Behavior Contract row — age alone, as written.

`prune_transcripts.py --tier subagents`: `~/.claude/projects/<slug>/<session>/subagents/agent-*.jsonl`
older than 3 days whose parent session is not OPEN (C.2.1 rule 2) and which
`~/.claude/bin/claude-stop-decider.py::pending_subagents` does not count as in flight (its
`subagent_running` reads the sidechain tail; a file older than `SUBAGENT_STALE_S` is never in
flight) are deleted, with a `pruned.jsonl` row each. `~/.claude/tasks/` and `~/.claude/shell-snapshots/`
entries older than 3 days likewise (both are per-session scratch Claude Code regenerates; measured
today both directories are empty). 27,195 files / 10.1 GB today. Graders red-first: a file inside the
window stays; an in-flight sidechain stays; a live parent keeps all its subagents.

**Gate C.3:** `pytest tests/test_prune_transcripts.py -k subagent` green after red; the dry-run table
shows the subagent tier's counts; `--apply` only at Gate C; the full `/fabrik-review` over C.2 + C.3
runs here, after both tiers exist (review floor).

### C.4 — Docs, the three governance files, session-recall — ✅ EXECUTED 2026-10-11 (1416db236; review fixes 9a42fca7e · a6730b30c; receipt 786645688)
Appetite: 60

> **Executed 2026-10-11:** hub `CLAUDE.md` § Pointers carries the session-history paragraph; the retention doc
> gained the restore path after a prune (`--restore`), the morning check (`--status`, `--verify-ledger`,
> `--agent`) and the named-windows section; the archiver's header and MARKER stopped saying nothing prunes
> (in the C.2 review fix 6f79449f1); `.env.example` / CONFIGURATION rows landed in C.1/C.2. **The four
> requests (D-441):** infra `01M4NVZGE9VTE3TK57ZVECD8FF` (the governance-template paragraph) and
> `01M4NVZJTMSSBDTVPSR7M4X7GF` (`whoami_agent.py`: a `/clear` predecessor binds without `--force`); fabrik-lib
> `01M4NVZMZ9THM7DFYMKSBCF82P` (its `CLAUDE.md` paragraph); session-recall `01M4NVZQ7NJR8F2GZMZKZPTB3E`
> (keep archived sessions on `--full`, an `agent` column, a nightly ingest + the `recall_ro` DSN — rule 8
> waits on it); replies `01M4NWR4HZD8K531SPP09JRQPT` / `01M4NWRF5VNEFB27AQT7A579A8` name the two deliberate
> deviations the quoted paragraph carries. Gate C.4: `check_doc_links.py` OK (0 broken of 3,734 refs);
> `docs_updater.py --check` reports only pre-existing items outside this surface (an old plan's broken links,
> the PLANS block). The full `/fabrik-review`: 7 raised / 6 confirmed / 1 refuted → 1 own-fix → 0 — receipt
> `docs/development/reviews/2026-09-06-plan-1-session-history-retention-phase-5-c4-review.md` CONVERGED.

- `docs/workstation/session-history-retention.md`: "nothing prunes" becomes the C.2 contract, the
  restore path after a prune, the `--agent` verb and the ROTATE line; `archive_transcripts.py`'s header
  and `MARKER` text stop saying the box never deletes (the archiver still never deletes — the pruner
  does, and the README names it).
- `docs/workstation/hooks-index.md` + `install_user_hooks.py`: the new user-level hook row.
- **Hub `CLAUDE.md` (this repo, fleet edits; NOT a governance-sync path — `.pre-commit-config.yaml:164`
  carries no `^CLAUDE\.md`, so nothing distributes on commit; operator-named (I6), so C.4's full
  `/fabrik-review` covers it):**
  one paragraph under § Pointers: *Session history: every MAIN transcript ships to B2 nightly; the
  local copy is pruned after 3 days by the guarded pruner (never an open session, never a project's
  or an agent's newest); history is read through session-recall or put back with
  `prune_transcripts.py --restore <session_id>`; a named hub window rotates with `/clear
  <agent>-<date>` + `whoami_agent.py --as <agent> --force` when the ROTATE line appears (D-736).*
- **`scripts/whoami_agent.py` (a governance-sync path, infra's beat):** a `request` (D-441): a holder
  row with the same `pid`+`pid_start` as the binding process is this session's `/clear` predecessor
  — bind without `--force`, and record the predecessor's `session_id` on the new row. Until it
  lands, the ROTATE line's `--force` is the sanctioned path (C.1.3).
- **`templates/governance/CLAUDE.md` (every /opt project — a governance-sync path, infra's beat):**
  the same paragraph, sent to infra as a `request` carrying the exact text (D-441 authority); infra
  commits it in the main checkout so the post-commit sync distributes it.
- **`/opt/fabrik-lib/CLAUDE.md` (sync-excluded repo):** the same paragraph, sent to fabrik-lib as a
  `request`.
- **session-recall (another repo):** a `request` with D-441 authority: (a) `ingest/reindex.py::
  _reclaim_orphans` must keep a session whose `(project_slug, session_id)` has a manifest row (path
  via `SESSION_ARCHIVE_MANIFEST`, default `~/.claude/archive/manifest.jsonl`) — today `--full` drops
  any session whose file is gone (`reindex.py:341,526-528`; the 2026-09 mail 01M1SPW1 is still unread
  in their inbox); (b) an `agent` column on `sessions`, filled from `agent-identity.jsonl`, and an
  `agent=` filter on `search_chats`; (c) a NIGHTLY incremental ingest (`cd /opt/session-recall &&
  .venv/bin/python -m ingest.reindex`, their documented command, `README.md:63`) that runs before
  00:00, plus the EXISTING `recall_ro` role's DSN (`schema.sql:85-100`; no new role, no changed
  grant) for the operator to copy into `/opt/fabrik/.env` as `SESSION_RECALL_RO_DSN` — because the
  pruner's rule 8 deletes nothing whose file session-recall's `index_state` has not indexed to its
  current inode and size —
  today nothing schedules the ingest (round-1 probe: `systemctl --user list-timers --all` shows only
  `session-archive` and `launchpadlib-cache-clean`; `crontab -l` has no reindex line), so without
  (c) the pruner stays a dry-run in effect. Interim, verified: no cron, timer or script runs
  `--full` on this box, so nothing deletes index rows before (a) lands; the pruner's `pruned.jsonl`
  is the list to re-ingest from the archive if it ever does.

**Gate C.4:** `docs_updater.py --check` green; `check_doc_links.py` green; the FOUR mails sent (ids
in Evidence: infra ×2 — the governance template and `whoami_agent.py` —, fabrik-lib, session-recall);
the full `/fabrik-review` over C.4's diff (docs, the hub `CLAUDE.md` paragraph, the four mails'
texts) green — review floor.

### Gate C — the FIRST real deletion (operator-visible, once)

All of C.1–C.4 green, then, in this order: (0) the branch MERGED by infra (`merge_request.py`) and
`install_session_archive_timer.sh` re-run from the MAIN checkout — the unit calls
`/opt/fabrik/scripts/sysadmin/prune_transcripts.py`, which does not exist there until the merge; the
re-installed unit carries `ExecStart=-… --dry-run` (the default) and `systemctl --user cat` shows it;
(1) **Gate B's download proof** (B.1–B.5) from a network that reaches `https://f004.backblazeb2.com`
— the only thing this network cannot do; a phone hotspot or the VPN off does it in minutes; (1b)
**session-recall's side of rule 8 is live**: their reply to C.4 (c) (mail id in Evidence) confirms
the nightly incremental ingest, and `SESSION_RECALL_RO_DSN` is set in `/opt/fabrik/.env` (presence
checked by name, never printed) — absent, Gate C is `BLOCKED: missing infra — session-recall's
nightly ingest / the read-only DSN`, for Gate C only: C.1–C.4 and the dry-run do not wait on it;
(2) `prune_transcripts.py` dry-run, its table pasted into Evidence — its deletable total must be
> 0 (the DSN and a matching row are live) and its `not-indexed` count must be 0: rule 8 is
evaluated right after rules 1–3 (the order in C.2.1), so the count is every old, closed,
non-newest transcript the ingest has not indexed to its end — the set session-recall must cover
for "searchable" to be true, whether or not rules 4–7 would later refuse the file; a non-zero count
names the sessions the ingest misses, and Gate C waits for session-recall; (3) the
**canary**: `--apply --max 10 --expect 10` by hand (this
run's set = the 10 oldest deletable files), then `--restore` of two of them from the bucket,
byte-identical (`sha256sum` against the `pruned.jsonl` rows); the two restored files are LEFT in
place — they carry a fresh `mtime`, so rule 1 keeps them 3 days and they re-enter the queue then;
(4) `prune_transcripts.py --verify-ledger` prints `OK` for every row (exit 0), and `--remote-count`
is UNCHANGED from before (3) — the pruner never touches the bucket; (5) the sidebar of one project
reopened and its last-3-days sessions still listed, one hub window's `/resume` list still showing
its newest, and `--status` showing the canary's summary row as the last APPLY row (`deleted: 10`,
no `error`; the unit's nightly dry-run may have written a later dry-run row, which is why `--status`
prints both); (6) the
unit's second `ExecStart` switched from `--dry-run` to `--apply --nightly` (the oldest 200 a night;
a hand run with `--max <M> --expect <M>` after (3) may take bigger bites — each one a pasted
table). **Any step red ⇒ the unit stays on dry-run.** Deletes nothing until (3).

**Review floor** (CLAUDE.md § Completion Contract 1a: heavy = *"a new mechanism outside the
`/fabrik-task` lane (D-315), gate/hook/enforcement, a governance-sync path, auth/schema/migrations/
concurrency, >5 files, or anything an operator asked for by name"*): every sub-phase here is
operator-named (I3, I4, I6), so none takes the scoped review — the full `/fabrik-review` after C.1
(a user-level HOOK), the full `/fabrik-review` ONCE over C.2 + C.3 together (one script,
`prune_transcripts.py`, its MAIN and subagent tiers, the concurrency with in-flight subagents), and
the full `/fabrik-review` after C.4 (its docs and the hub `CLAUDE.md` paragraph — outside the sync
regex, so no post-commit distribution rides on it, which is why it is a doc edit and not why it
could take a lighter review) — three full reviews, each before the next sub-phase, so Gate C's
"all of C.1–C.4 green" never waits on the plan's Finish review, which still runs last over the whole
Phase C diff; seats native (D-181), the Opus seat authoritative on C.2's invariant; read-only git in
seats.

## Phase C (2026-10-05 deferral) — superseded text, kept for the record

**Not built in this revision.** Panel (`/fabrik-*` autonomy rule, D-558): Opus and Fable seats,
same brief, neither shown the other's answer — both returned **DEFER in whole**, neither tier to
ship now. Grounds both cited: Gate B is unproven on the new hop; Phase 0 has no rows, so the cap is
an invented number (residual risk 1); the operator's two retention edits since the spec (D-233,
D-470 — `cleanupPeriodDays: 3650`) both point at KEEPING; the operator's 2026-10-05 ask is that
history stay *"searchable via session recall"*, and session-recall is a mirror — a pruned
transcript's index rows go on the next `--full` (`_reclaim_orphans`, spec § THE CORRECTION); and
disk is not binding (~18 GB of transcripts, 242 GB free of 1007 GB). The subagent 7-day tier was
weighed separately and also deferred: it is irreversible, returns ~2.7 GB nobody needs, and
splitting it off would mean waiving "no phase may merge forward", which no operator ruling does.

**Reopening tripwire — all three at once:**
1. **Disk:** Phase 0's log (≥ 14 rows) forecasts local free space under **100 GB within 90 days**,
   or free space is already under 100 GB.
2. **Gate B** is green on the B2-direct path (this revision's Phase B).
3. **Searchability survives a prune:** either `/opt/session-recall` has acked
   `01M1SPW1KKNXKKKM8MSVT6RHQ9` with a `--full` fix that keeps archived sessions indexed, or the
   index can ingest from the archive.

When it reopens, the design below is the starting point, re-reviewed — not executed as written.

- **C.1 — the invariant, in code.** Refuse to delete any transcript whose **CURRENT** sha256 is
  absent from the manifest under its **`(project_slug, session_id, sha256)`** key. Re-hash at delete
  time; never trust the sha recorded at archive time. Archive unreachable ⇒ **fail CLOSED**.
- **C.2 — the graders, each SEEN RED first** (`core/45-testing-strategy.md:21`): transcript absent
  from the manifest → not deleted; archived at sha A then mutated to sha B → not deleted; archive
  unreachable → nothing deleted; manifest row present but the `.zst` missing → not deleted;
  `.zst` corrupted → not deleted; two projects with the same session id → neither deletes on the
  other's row; a file inside the window → never offered.
- **C.3 — tiers.** MAIN by mtime, oldest first, union of the window and the aggregate bound;
  SUBAGENT 7 days, hard cliff (one live reader, `~/.claude/bin/claude-stop-decider.py:421,515`,
  inspects in-flight sessions only).
- **C.4 — pool receipts** need a per-day rotation summary so `kaizen_backfill.py:137` can tell
  "rotated" from "no dispatches".
- **C.5 — a local `--full` guard** (hub-side wrapper); `/opt/session-recall` is not patched here.

**Gate C (2026-10-05 text):** not applicable to that revision; the plan closed at Gate B. Superseded
by § Phase C above (D-736).

## Intake Inventory (2026-10-11 revision — the operator's words, every item dispositioned)

| I# | Item (anchored) | Disposition | Where |
|---|---|---|---|
| I1 | *"i want all my chat histories but not in local"* | IN | Phase A (live) + C.2 |
| I2 | *"in local recent 3 days might be fine"* | IN | C.2.1 rule 1 (`PRUNE_AFTER_DAYS=3`) |
| I3 | *"for fabrik agents infra, kaizen, intel, fleet named histories needed"* | IN | C.1.1–C.1.4 |
| I4 | *"not the scratchpad, subagents etc."* | IN | C.3 (subagents, tasks, snapshots); scratch already swept |
| I5 | *"we need to implement this asap"* | IN | C.1.4 rotation first (ends the crash today); C.2 behind Gate C |
| I6 | *"we have 3 claude.md file … fabrik … fabrik-lib … governance for all opt projects"* | IN | C.4 |
| I7 | *"be extremely careful not lose my chat histories seen in the screen"* | IN | C.2.1 rules 1–3 + the last look, C.2.2 (the cap), C.2.5 `--restore`, Gate C (0)–(5) |
| I8 | *"(all repos)"* | IN | the pruner walks every project slug; the hook is user-level |
| I9 | "why was the extension host running out of memory" (asked 2026-10-11) | IN | § Phase C preamble; root cause and the external issues cited |
| I10 | "how are others doing this? research" | IN | § Phase C "Why rotation, not slimming"; sources in Evidence probe 5 |
| I11 | the 26 GB of `.dmp` crash dumps in `%LOCALAPPDATA%\Temp\wsl-crashes\` | OUT-OF-SCOPE | the operator's Windows files; named in the 2026-10-11 session, not a repo action |
| I12 | report the OOM to Anthropic (drafted) | OUT-OF-SCOPE | W-49a8280d (gate: publish) stays with the operator |
| I13 | session-recall keeps archived sessions indexed (`--full` orphan sweep) | IN | C.4 mail (a) + the interim verification |

Intake: 13 items — 11 IN, 2 OUT-OF-SCOPE (each named above), 0 ASK.

## Behavior Contract — Phase C (each test SEEN RED first)

- **Given** a manifest run over a session bound in `agent-identity.jsonl`, **When** its row is written, **Then** the row carries `"agent": "<name>"` and an unbound session's row carries no `agent` key (C.1.1)
- **Given** two bindings for one session, **When** the row is written, **Then** the later `at` wins (C.1.1)
- **Given** a session with no identity row whose registry entry's `(pid, procStart)` equals an identity row's `(pid, pid_start)`, **When** the row is written, **Then** `agent` is that row's name; with neither, no key (C.1.1 registry join)
- **Given** `--agent <name>`, **When** it runs over a manifest, **Then** it lists only rows tagged `<name>`, newest first, each with whether the local file exists (C.1.2)
- **Given** a transcript of ≥ `ROTATE_ADVISE_MB`, **When** `transcript_size_check.py` runs on the hook JSON, **Then** it prints exactly one `ROTATE:` line naming the size, `/clear` and the `--force` re-bind; below the threshold, or on any error, it prints nothing and exits 0 (C.1.3)
- **Given** the same session at the same 100 MB step, **When** the hook runs again, **Then** it prints nothing; at a new step it prints once more (C.1.3 stamp)
- **Given** the new hook in `ENTRIES`, **When** `install_user_hooks.py --check` runs, **Then** it exits 0 and lists it; a settings file missing it exits non-zero (C.1.3 wiring)
- **Given** a MAIN transcript inside the 3-day window, **When** the pruner runs, **Then** it is never offered, in dry-run or apply (C.2.1 r1)
- **Given** a transcript older than 3 days whose session id is in a registry entry with a live pid and a matching `procStart`, **When** the pruner runs, **Then** it is refused as OPEN; the same entry with a live pid and ANOTHER `procStart` is not OPEN; an entry without `procStart` is OPEN (C.2.1 r2)
- **Given** a transcript whose only liveness evidence is an identity row with `pid`+`pid_start` alive, **When** the pruner runs, **Then** it is refused as OPEN (C.2.1 r2, identity leg)
- **Given** a project slug whose only sessions are older than 3 days, **When** the pruner runs, **Then** the newest is kept (C.2.1 r3)
- **Given** two agents' sessions in one slug, **When** the pruner runs, **Then** each agent's newest is kept even when another agent's session is newer (C.2.1 r3, agent leg)
- **Given** a transcript with no manifest row for its `(slug, session_id)`, **When** `--apply` runs, **Then** it is not deleted, reason `not-archived` (C.2.1 r4)
- **Given** a transcript whose current sha256 differs from its latest manifest row, **When** `--apply` runs, **Then** it is not deleted and the reason is `sha-mismatch` (C.2.1 r4)
- **Given** a manifest row whose `.zst` is missing, fails `zstd -t`, or decompresses to bytes whose sha256 differs from the row's, **When** `--apply` runs, **Then** nothing is deleted for that session (C.2.1 r5)
- **Given** a file with no session-recall `index_state` row for its inode, or a row whose `size` differs from the file's, or no `SESSION_RECALL_RO_DSN`, or no reachable database, **When** `--apply` runs, **Then** it is not deleted, reason `not-indexed`; a row for the inode under ANY path (the worktree name) with the file's size passes (C.2.1 r8)
- **Given** a file whose size or `mtime` changed between the hash and the unlink, **When** `--apply` runs, **Then** it is not deleted, reason `changed-under-hash` (C.2.1 last look)
- **Given** a remote listing that is absent, or whose size or SHA1 differs from the local `.zst`, **When** `--apply` runs, **Then** nothing is deleted for that session; a failed listing deletes nothing in that slug (C.2.1 r6)
- **Given** one inode with two names where one name fails a rule or has no manifest row, **When** `--apply` runs, **Then** neither name is unlinked (C.2.1 r7)
- **Given** `--apply` without `--expect`, or with a count that differs from this run's count (the dry-run's capped figure, or `--max`'s), **When** it runs, **Then** nothing is deleted and both counts are printed (C.2.2)
- **Given** more deletable files than `PRUNE_MAX_PER_RUN`, **When** `--apply --nightly` runs, **Then** exactly the oldest cap-many are deleted and the rest are reported `deferred`; **When** a hand run passes `--max M --expect M`, **Then** exactly the oldest `M` are deleted (C.2.2)
- **Given** any exception during a dry-run or apply run, **When** the pruner exits, **Then** a `prune-log.jsonl` summary row carrying `error` exists, the exit code is 1, and no file was unlinked without its `pruned.jsonl` row; `--status` prints the last row and the last apply row; an exception in `--restore`, `--verify-ledger` or `--status` exits 1 with no row (C.2 summary row)
- **Given** a MAIN transcript larger than `ROTATE_ADVISE_MB`, **When** the nightly run writes its summary row, **Then** the path is in `over_threshold` (C.2, Residual 10's backstop)
- **Given** `pruned.jsonl` rows whose objects are listed with matching size and SHA1, and one whose object is absent, **When** `--verify-ledger` runs, **Then** it prints `OK` per row and `MISSING` for that one and exits 3; all present ⇒ exit 0 (C.2.6)
- **Given** the archiver's lock held, **When** `--apply` runs, **Then** it exits 3 and deletes nothing (C.2 lock)
- **Given** a path that vanishes between the archiver's scan and `_group_by_inode`, **When** the archiver runs, **Then** it skips that path and archives the rest (C.2, `archive_transcripts.py:200-206`)
- **Given** a `pruned.jsonl` row and a reachable download host, **When** `--restore <session_id>` runs, **Then** every path in the row exists again with the row's sha256 and all of them are one inode — fetched when none survived, hard-linked to a surviving identical twin when one did (no fetch) — and the inode's `mtime` is now, so the next dry-run does not offer it; a surviving path with another sha256 ⇒ refused, exit 3, nothing written; an existing path is never overwritten (C.2.5)
- **Given** a deletable file, **When** `--apply --expect N` runs, **Then** its `pruned.jsonl` row exists before the unlink and names every path removed (C.2.3)
- **Given** a subagent sidechain older than 3 days whose parent is not OPEN and not in flight, **When** `--tier subagents --apply` runs, **Then** it is deleted with a row; an in-flight or live-parent sidechain stays (C.3)
- **Given** `~/.claude/tasks/` and `~/.claude/shell-snapshots/` entries older than 3 days, **When** `--tier subagents --apply` runs, **Then** they are deleted with a row each; younger entries stay (C.3)
- **Given** the unit file, **When** `tests/test_archive_transcripts.py -k unit_file` runs, **Then** it asserts `Type=oneshot`, the archiver's `ExecStart` first and the pruner's `ExecStart=-` second — the `man systemd.service` ordering rule quoted in C.2 (C.2 unit ordering)

## Evidence — Phase C (2026-10-11 revision; every block captured from a run this session)

Probe 1 — the hub windows were idle between the two archive runs (A.1a skipped them correctly):
```
infra   records in the idle window: 0 · after the 10-11 run: 559
fleet   records in the idle window: 0 · after the 10-11 run: 693
kaizen  records in the idle window: 0 · after the 10-11 run: 744
```
(`journalctl --user -u session-archive.service`: 00:18:11 `TRANSPORT FAILED … lookup api.backblazeb2.com … read udp`; 00:34:27 `51 new manifest row(s)`.)

Probe 2 — the local population (`find ~/.claude/projects -name '*.jsonl'`, the realpath of
`~/.claude-fleet/active/projects`):
```
36882
total 26.4 GB
modified <3d: 2470 files 8.6 GB
  1530 MB /home/ozgur/.claude/projects/-opt-fabrik/dd3c06d1-41b1-4610-bfd5-deb4f29fcc2e.jsonl
  1158 MB /home/ozgur/.claude/projects/-opt-fabrik--claude-worktrees-intel/4e90716e-696b-4ddf-90ab-70e30f51f294.jsonl
   797 MB /home/ozgur/.claude/projects/-opt-fabrik--claude-worktrees-fleet/1970a0ff-baa3-401b-ba52-fb0c5de43261.jsonl
subagent transcripts: 27195 files 10.1 GB
```

Probe 3 — remote size + SHA1 listing works from this network, small and multi-part objects alike
(`rclone lsf --files-only --format psh --hash SHA1 <prefix>/-opt-fabrik/`):
```
objects listed under -opt-fabrik/: 54
kaizen  remote size,sha1 = ('7807980', '861209464e519366bd6441f50172d2b25df0793a') · local = (7807980, 861209464e519366bd6441f50172d2b25df0793a)
infra   remote size,sha1 = ('236606395', '8afd49ceb6b80852e89ff30487d7f6d319c9bdb6') · local = (236606395, 8afd49ceb6b80852e89ff30487d7f6d319c9bdb6)
```
The download host is still unreachable here (`curl -sI https://f004.backblazeb2.com/` → no response),
so Gate B's download leg stays an operator step from another network.

Probe 4 — what a hub transcript is made of (infra, 1,530 MB):
```
  total 1530 MB · compact boundaries 222 · after last boundary 5 MB
       407 MB   26.6%    84932 recs  user/tool_result
       310 MB   20.2%    95648 recs  attachment
       305 MB   19.9%    97938 recs  assistant
       261 MB   17.0%    84850 recs  assistant/tool_use
       106 MB    7.0%     2963 recs  file-history-snapshot
        30 MB    1.9%     9407 recs  user
dd3c06d1    1530 MB  duplicate-uuid rows: 55333 of 589084 (9.7% of bytes, 149 MB)
```

Probe 5 — open-session detection and the binding store:
```
registry: live-pid entries 5, dead-pid entries 1393, live session ids 3     (~/.claude/sessions/<pid>.json: pid, sessionId, cwd, startedAt, …)
42 /home/ozgur/.claude/state/agent-identity.jsonl                             ({"session_id","name","pid","pid_start","toplevel","at"} per line)
```
Probe 5b — the liveness test and the binding, re-measured in the plan review (2026-10-11, later the
same day; the registry keeps growing):
```
entries 1401 pid-alive 9 pid-alive-and-same-procStart 6 domains 6
status values [None, 'busy', 'idle', 'waiting']
readlink -f ~/.claude-fleet/{sarp,can,mob,ob,ozgurbasak,active}/sessions → /home/ozgur/.claude/sessions   (one registry for every slug)
6 live claude processes, every one CLAUDE_CONFIG_DIR=/home/ozgur/.claude-fleet/active
whoami_agent.py:259-274 resolve_agent_name(): CLAUDE_AGENT env, else the LAST row with session_id == CLAUDE_CODE_SESSION_ID
whoami_agent.py:356-373 _bind_locked(): a holder row with the same name, another session_id and a live pid+pid_start → rc 1 "held by a LIVE session"
man systemd.service (ExecStart=): "If one of the commands fails (and is not prefixed with "-"), other lines are not executed, and the unit is considered failed."
systemctl --user list-timers --all: session-archive.timer, launchpadlib-cache-clean.timer — no session-recall ingest; crontab -l: no reindex/ingest line
crontab -l: 17 5 * * * find /home/ozgur/.claude-youtube-headless/projects -type f -mtime +1 -delete   (the one other transcript deleter; a separate config dir)
claude-reboot-sweep.sh: rm/-delete at :95,141,166,201,217,226,240,241 — lock and marker files only; :259 scans transcripts, deletes none
```
`code.claude.com/docs/en/commands`: *"`/clear [name]` — Start a new conversation with empty context. Pass
a name to label the previous conversation in the `/resume` picker … Resume the previous conversation
with …"*; `docs/en/interactive-mode`: *"Running `/clear` starts a new session … The previous session's
conversation is preserved and can be resumed."* External grounding of the crash class and of practice
elsewhere (all via WebSearch + WebFetch, 2026-10-11): anthropics/claude-code #89075, #97229, #23953,
#8722, #92089, #18905, #86991, #64999; openai/codex #24948; kuroko1t/claude-vault; Ruya-AI/cozempic;
allaboutcoding.ghinda.com/where-ai-coding-clis-store-session-logs. Code anchors read this session:
`scripts/sysadmin/archive_transcripts.py:188-222` (selection, inode grouping, latest rows),
`:225-278` (`archive_one`, the A.1a skip), `:316-345` (`remote_count`, `fetch`);
`/opt/session-recall/ingest/reindex.py:341,526-528` (`_reclaim_orphans` on `--full`);
`/opt/session-recall/db/schema.sql:38-50` (`turns.content`, the FTS mirror);
`~/.claude/bin/claude-stop-decider.py:528-560` (`subagent_running` at `:530`, `pending_subagents` at
`:552`, signature `(transcript: Path, session_id: str, now: float | None = None)`);
`scripts/sysadmin/worktree_transcript_link.py:1-30` (the hard-linked worktree twin) and `:92` (the
hook payload's `transcript_path`, the field the ROTATE hook reads too);
`.pre-commit-config.yaml:158-164` (the governance-sync filter — `scripts/sysadmin/` and the user-level
hook list are outside it; `templates/governance/` and `.claude/hooks/` are inside).

**Gate C (0) — GREEN (W-c49a7adf), captured by infra (session dd3c06d1), 2026-10-11.** Branch
`worktree-fleet` merged (c3ca37677, request 01M4NYEN9SEP1C3EQ147VE4XYT); the pruner reached the main
checkout with it (`git log -1 -- scripts/sysadmin/prune_transcripts.py` → 6f79449f1). Then
`bash scripts/sysadmin/install_session_archive_timer.sh` ran from `/opt/fabrik` at 20:00 +03; the timer
next fires Mon 2026-10-12 00:14 +03. The re-installed unit:
```
$ systemctl --user cat session-archive.service
# /home/ozgur/.config/systemd/user/session-archive.service
# Session-history archive -> Backblaze B2 (docs/workstation/session-history-retention.md, D-565).
# Installed by scripts/sysadmin/install_session_archive_timer.sh into ~/.config/systemd/user/.
# No EnvironmentFile=: the archiver reads ONLY the SESSION_ARCHIVE_* lines of /opt/fabrik/.env
# itself, so the hub's other secrets never enter this unit's environment.
#
# No After=network-online.target: the USER manager has no such target, so it would order
# nothing. A run that starts before the network is up (the boot-time catch-up) fails with a
# non-zero exit and is retried by Restart= below, at most 4 times in 2 hours.
[Unit]
Description=Archive Claude session transcripts to Backblaze B2
StartLimitIntervalSec=2h
StartLimitBurst=4

[Service]
Type=oneshot
# The leading "-" ignores the sampler's exit status: it runs under set -euo pipefail, and a
# sampler error must never skip the backup.
ExecStartPre=-/opt/fabrik/scripts/sysadmin/sample_transcript_growth.sh
ExecStart=/opt/fabrik/.venv/bin/python /opt/fabrik/scripts/sysadmin/archive_transcripts.py
# The pruner runs AFTER the archiver (man systemd.service, ExecStart=: commands run sequentially;
# a failing command without "-" stops the rest and fails the unit), so a night whose archive
# failed prunes nothing. Its own "-" keeps a pruner refusal (exit 3) from failing the unit, which
# would make Restart= re-run the ARCHIVER for a pruner outcome; the pruner reports for itself in
# ~/.claude/archive/prune-log.jsonl (`prune_transcripts.py --status`). It stays on --dry-run until
# Gate C step (6) of the retention plan switches it to --apply --nightly (D-736).
ExecStart=-/opt/fabrik/.venv/bin/python /opt/fabrik/scripts/sysadmin/prune_transcripts.py --dry-run
Restart=on-failure
RestartSec=15min
Nice=10
IOSchedulingClass=idle
```

The unit's second `ExecStart=` argv, run by hand from `/opt/fabrik` at 2026-10-11 20:11:03 +03 (an
interactive shell, not the unit's environment). This is NOT Gate C (2)'s table: it fails (2)'s bar
(deletable > 0, `not-indexed` 0), as it must while (1b) is open. Its counts move as transcripts are
written and indexed; the C.2 capture above is an earlier run of the pruner, from fleet's worktree before
the merge brought it to `/opt/fabrik`:
```
$ /opt/fabrik/.venv/bin/python /opt/fabrik/scripts/sysadmin/prune_transcripts.py --dry-run
prune_transcripts (dry-run): MAIN tier — 9813 transcript inode(s) scanned · deletable 0 · this run 0 (cap 200) · deferred 0
  refusals: in-window 1055 · newest-of-agent 2 · newest-of-slug 1618 · not-indexed 7138
  over-threshold (> 200 MB): 22 file(s)
```

### Gate C — execution log (2026-10-12, fleet; operator D-746 "proceed and do not stop again for the things you can handle yourself")

**(0) infra's merge + timer re-install — DONE** (`c3ca37677` merged 2026-10-11; `systemctl --user cat session-archive.service` line 27
`ExecStart=-/opt/fabrik/.venv/bin/python /opt/fabrik/scripts/sysadmin/prune_transcripts.py --dry-run`; timer next 2026-10-12 00:14).

**(1) Gate B's download proof — PASSED through a SOCKS tunnel to vps1** (`ssh -N -D 127.0.0.1:1080 ozgur@vps1.ocoron.com`,
`HTTPS_PROXY=socks5://127.0.0.1:1080`, which reaches rclone through the archiver's child environment — it strips only `RCLONE_*`).
This network's SNI filter still drops `f004.backblazeb2.com` directly (`curl --resolve f004.backblazeb2.com:443:149.137.128.16` times out);
through the tunnel it answers `HTTP 301`. The first attempt, COMPLETE and verbatim from scratch `gateb-run.out` from its `== B.1` line
to its `(end)` (B.1, B.2 and B.5 pass; B.4 as written in this plan — `T` from the local clock — FAILS):
```
== B.1 fetch /-opt-seo/8fe44dc5-a1ef-4f95-a79f-c5b19dfcee02.jsonl.zst from the bucket (through the tunnel)
fetched /-opt-seo/8fe44dc5-a1ef-4f95-a79f-c5b19dfcee02.jsonl.zst -> /tmp/claude-1000/-opt-fabrik--claude-worktrees-fleet/1970a0ff-baa3-401b-ba52-fb0c5de43261/scratchpad/gateb/r.zst
fetch rc=0
  object bytes 7918
== B.2 decompress, cmp against the live original, sha256 against the row
  cmp: IDENTICAL
  sha256 fetched : 43fcd3a37c25d51cde6896bfc19d5dd0c9184731220459a64eae809c1dc5f891
  sha256 row     : 43fcd3a37c25d51cde6896bfc19d5dd0c9184731220459a64eae809c1dc5f891
  sha256: MATCH
== B.4 the archive stands alone: two versions of a synthetic transcript in restore-proof/, the first restored by --version-at after the source is gone
archive_transcripts: 1 MAIN transcript(s) eligible (idle > 0.0d)
archive_transcripts: 1 new manifest row(s); archive at /tmp/claude-1000/-opt-fabrik--claude-worktrees-fleet/1970a0ff-baa3-401b-ba52-fb0c5de43261/scratchpad/gateb/proof/archive
run1 rc=0
archive_transcripts: 1 MAIN transcript(s) eligible (idle > 0.0d)
archive_transcripts: 1 new manifest row(s); archive at /tmp/claude-1000/-opt-fabrik--claude-worktrees-fleet/1970a0ff-baa3-401b-ba52-fb0c5de43261/scratchpad/gateb/proof/archive
run2 rc=0
  scratch source deleted; T=2026-10-11T21:15:12Z
archive_transcripts: /-gateb-proof/00000000-0000-4000-8000-00000000b4b4.jsonl.zst was not downloaded: absent from the bucket, or B2's download host is unreachable from this network
version-at fetch rc=1
zstd: can't stat /tmp/claude-1000/-opt-fabrik--claude-worktrees-fleet/1970a0ff-baa3-401b-ba52-fb0c5de43261/scratchpad/gateb/v1.zst : No such file or directory -- ignored 
  sha256 run-1 source : f7e662fdc67b33459e677f151b4b0b1c26dde6f73bb706192444a5e39d1886bc
  sha256 fetched v1   : <none>
  B.4: MISMATCH
== B.5 remote-count (the manifest fetched from the bucket) lists the B.1 object
remote_objects 9923
remote_manifest_sha256 2a9a7784834bf2b4b651460c1013f25884e6aa360889fe7abd5a61301b4faa74
```
B.4 then PASSED once `T` was taken from the SERVER's clock — COMPLETE and verbatim, the `== B.4 proof` section of scratch
`gatec-fixes-run.out` (both versions are addressable by instant; the run-1 bytes come back from the bucket alone):
```
== B.4 proof, preserved: --version-at 2026-10-11T21:18:00Z (between the two uploads on the SERVER clock) and 21:19:00Z (after run 2)
fetched /-gateb-proof/00000000-0000-4000-8000-00000000b4b4.jsonl.zst -> /tmp/claude-1000/-opt-fabrik--claude-worktrees-f
  2026-10-11T21:18:00Z -> 1 line(s), sha256 f7e662fdc67b33459e677f151b4b0b1c26dde6f73bb706192444a5e39d1886bc == run-1 source: B.4 MATCH
fetched /-gateb-proof/00000000-0000-4000-8000-00000000b4b4.jsonl.zst -> /tmp/claude-1000/-opt-fabrik--claude-worktrees-f
  2026-10-11T21:19:00Z -> 2 line(s), sha256 11fe4e48ad4cbb562f5e278882d552fe0a75aaa313e23db4845fb90bc372d32e (run-2 bytes)
  run-1 source sha256: f7e662fdc67b33459e677f151b4b0b1c26dde6f73bb706192444a5e39d1886bc
```
B.5's 9923 was counted while the 23:12 archive run's uploads were still landing; after that run and the canary the bucket holds
9923 objects = the manifest's 9,923 distinct `(slug, session)` keys over 9,969 rows (the same `gatec-fixes-run.out`), so B.5 and the
post-canary count agree and the canary changed nothing in the bucket. `--remote-count` fetches the manifest object from the bucket and prints
its sha256 (it never parses it) and a bucket-wide object count, never an object list or a key lookup: it proves the bucket is listable and the
manifest downloadable with only the bucket; B.1's own fetch is what shows B.1's key is present (the B.5 recipe now says so).
B.4's recipe as written (`T` from the local clock, 3 s after run 1) returned NOTHING at every instant from 21:15:16Z to 21:17:40Z:
this box's clock is 2 min 49 s BEHIND B2's (`date -u` 21:19:51Z while both B2 hosts answered `Date: … 21:22:40 GMT`), and
`--b2-version-at` is keyed on the server's upload time. The proof holds; the lesson is in `docs/LESSONS_LEARNT.md`.

**(1b) session-recall's side — LIVE.** The index is incremental within minutes (a turn of this session written 21:14 was returned by
`search_chats` at 21:33; `recent_chats` for the worktree slug reports nothing because the hard-linked transcript is indexed under
`-opt-fabrik`, D-467). `SESSION_RECALL_RO_DSN` is present in `/opt/fabrik/.env` (by name — copied by fleet under D-746 after the
operator's ruling; `grep -c '^SESSION_RECALL_RO_DSN=' /opt/fabrik/.env` → 1; hub `.env` backed up to `backups/.env.backup.20261012-000806`).
The plan's (1b) names session-recall's REPLY as the evidence; the reply has not come (mail 01M4NVZQ7NJR8F2GZMZKZPTB3E unread in their
inbox after 9 h). Its intent — the ingest live and incremental — was verified by execution above, and the DSN half was closed under
D-746, which covers the copy and nothing else. Recorded as a DEVIATION from the step as written: the mail stays open and their reply,
when it comes, is pasted here; it is not a precondition the operator waived.

**The archive is current:** a manual `archive_transcripts.py` run at 23:12–00:32 shipped 230 new rows (9,739 → 9,969; the 217 same-day
transcripts and the changed ones); 11 of the 230 carry an `agent` tag — `infra`, `fleet`, `intel`, `kaizen` among them (the first tagged
rows: C.1 landed after the day's earlier run).

**(2) dry-run with the index visible (through the tunnel; a direct `rclone lsf` took > 3 min per slug):**
```
prune_transcripts (dry-run): MAIN tier — 9959 transcript inode(s) scanned · deletable 7280 · this run 200 (cap 200) · deferred 7080
  refusals: in-window 1059 · newest-of-agent 2 · newest-of-slug 1618
  over-threshold (> 200 MB): 22 file(s)
```
`not-indexed` is 0 (the line is gone); this run's 200 come from 4 slugs (trade-intelligence 105 · youtube 48 · -tmp 36 · -home-ozgur 11).

**(3) the canary — `--apply --max 10 --expect 10`:**
```
prune_transcripts: deleted 10 (MAIN 10 inode(s), subagent-tier 0); deferred 7272; ledger /home/ozgur/.claude/archive/pruned.jsonl
```
(3 `-home-ozgur` + 7 `-opt-youtube` sessions, the oldest; one fsynced `pruned.jsonl` row before each unlink.)

**(4) two restored from the bucket alone, then the ledger verified:**
```
restore: 3b5d6a6e-77d3-4097-aeef-ac5aea8f905e — fetched; paths ['…/-opt-youtube/3b5d6a6e-….jsonl']; sha256 83c29f423de3… verified; mtime now   (69036 bytes back)
restore: 247cfafc-0ca5-46b0-834c-f8b7c1ff18d6 — fetched; paths ['…/-opt-youtube/247cfafc-….jsonl']; sha256 b290a3928663… verified; mtime now   (70140 bytes back)
verify-ledger: 10 row(s), 0 MISSING
```
`--remote-count` after the canary (`gatec-fixes-run.out`): `remote_objects 9923` — equal to B.5's figure and to the manifest's 9,923 distinct
keys; the deletion touched nothing in the bucket.

**(5) `--status`:** `last apply: {"deleted": 10, "deletable": 7282, "deferred": 7272, "mode": "apply", …}`. The step's
operator-visible half (a project's sidebar still listing its last-3-days sessions, a hub window's `/resume` still showing its newest)
is the operator's glance at the next window open; the rule that guarantees it held at file level (`gatec-fixes-run.out`): after the canary
`-opt-youtube` holds 6 sessions modified within 3 days — 2 of them the restored canary files (their mtime is now; `ls -t` lists them first)
and 4 in-window sessions the rule kept, its newest original session (`a16ff916…`, third in `ls -t`) among the 4; `-opt-fabrik` holds 108; the canary
took only sessions older than 3 days that were neither a project's nor an agent's newest.

**(6) the unit flipped and installed** (`scripts/sysadmin/systemd/session-archive.service` → `--apply --nightly`; installed from this
worktree's `install_session_archive_timer.sh`, which copies the unit from its own tree): `systemctl --user cat session-archive.service`
line 27 `ExecStart=-/opt/fabrik/.venv/bin/python /opt/fabrik/scripts/sysadmin/prune_transcripts.py --apply --nightly`; next run
Tue 2026-10-13 00:00 plus the timer's `RandomizedDelaySec` (up to 15 min). **Gate C PASSED 2026-10-12 00:50** — the first nightly
apply takes the oldest 200 of the MAIN set as it stands that night (the 2 restored canary files carry `mtime now` and re-enter after 3
days; newly aged files join) AND the subagent tier, which `--nightly` adds and which has no cap by design (C.3 — the 3-day cliff, never
archived). Measured by `--dry-run --tier subagents` on 2026-10-12 01:06 (`gatec-fixes-run.out`): `16208 entr(ies) scanned · this run 6723 ·
refusals: in-window 152 · parent-open 9333`. The morning check is `prune_transcripts.py --status` + `--verify-ledger`.

## Gate mechanics

Each phase proves itself with `ruff check` + `ruff format --check` + `pytest` on its OWN files, and
`final_gate.py --json` is read as the shared gate; any red it carries that names no file of this
plan is declared in the Evidence section in the exact `GATE-SCOPE:` form the regex at
`scripts/enforcement/check_convergence.py:386` accepts, never hidden. (The first revision's two sibling reds are not re-asserted here; the gate is
re-run at each phase boundary and its live output decides.)

## Context Ledger

- **Rule packs** (the rubric over the full File Scope, § Rubric run): `core/35-security-auth.md`,
  `core/25-data-postgres.md` (an application-code pack — BaseSettings, asyncpg; it binds nothing in a stdlib
  script's one `SELECT`), `core/30-ops.md`, `core/10-python.md`,
  `core/40-documentation.md`, `core/45-testing-strategy.md`; quoted in § CONSTRAINTS DIGEST.
- **fabrik-lib modules:** none vendored (§ fabrik-lib verdict: BUILD, hub-local).
- **`agents-fabrik.md` invariants:** none touched — this is box-local workstation infrastructure,
  not a fleet service; no `specs/services/*.yaml`, so no `shape.*` flag applies.
- **Phase C sources (2026-10-11):** `~/.claude/state/agent-identity.jsonl` (the agent↔session
  binding `scripts/whoami_agent.py` writes — C.1.1 reads it, never writes it);
  `~/.claude/sessions/<pid>.json` (Claude Code's own peer registry — the OPEN test, C.2.1 r2);
  `scripts/sysadmin/worktree_transcript_link.py` (D-467's hard links — C.2.1 r7);
  `~/.claude/bin/claude-stop-decider.py::pending_subagents` (the one live reader of subagent
  sidechains — C.3 respects its in-flight rule); `scripts/sysadmin/install_user_hooks.py` (the
  user-level hook list the ROTATE advisory joins); session-recall's `turns.content` + `_reclaim_orphans`
  (the mirror and its one hazard — C.4). None is a fleet service; no `shape:` flag applies.
  12-Factor: the pruner and the hook log to stdout and the summary row (XI), daemonize nothing (VIII),
  read the one backing service (session-recall's Postgres, rule 8) from the environment (IV), shell out only
  to `zstd` and `rclone`, both already probed by the archiver (II).
- **Live system facts this plan stands on** (Evidence): `rclone v1.72.0`, zstd 1.5.5,
  `systemctl --user` running with `Linger=yes`, bucket `wsl-ozgur` (operator-created), the
  `SESSION_ARCHIVE_B2_*` settings in `/opt/fabrik/.env`, D-467's hard links (117 paths on 59
  inodes); and, from `docs/DECISIONS.md` rather than Evidence, D-470's `cleanupPeriodDays: 3650`.

## Behavior Contract — Phase A (each test SEEN RED, `core/45-testing-strategy.md:21`)

All in `tests/test_archive_transcripts.py`. rclone never runs for real in a test: `_rclone` hands
its argv and env to one module-level runner, `_run_rclone(argv, env)`, and the tests replace THAT
runner with a recorder that captures each call and returns the configured result. `zstd` is NOT
faked — it runs for real (the file already skips when `zstd` is absent), so `.zst` files exist and
decompress.
The `tree` fixture sets `ARCHIVE_AFTER_DAYS=0` explicitly (its files are written now, so the new
default of 1 would make every revision-1 test vacuous), plus fake `SESSION_ARCHIVE_B2_*` keys.

| # | Behavior | Test proves |
|---|---|---|
| A-B1 | An unchanged, already-archived transcript is neither re-hashed nor recompressed (A.1a) | on a second run the recorder sees no `zstd` call and the hash function is never called; no row appended |
| A-B2 | A changed transcript is re-archived under a NEW row | after the source changes, the second run appends a row with the new sha and the `.zst` decompresses to the new bytes |
| A-B3 | Hard-linked twins are archived once (A.1b) | two slugs holding one inode yield one `.zst` and one row whose `also_slugs` names the other slug |
| A-B4 | Ship order: `copy` (manifest excluded) → rows appended → `copyto` manifest | recorder order, the `--exclude /manifest.jsonl` argument on `copy`, and the manifest row count at `copyto` time |
| A-B5 | Missing key ⇒ exit 1 before any rclone call, naming both variables and the env file, printing no value | three fixtures — keys absent from env and file, `SESSION_ARCHIVE_ENV_FILE` pointing at a missing path, and at an unreadable (`chmod 000`) file: each rc 1, stderr names `SESSION_ARCHIVE_B2_KEY_ID`, `SESSION_ARCHIVE_B2_APPLICATION_KEY` and the file, no recorded call, no rows |
| A-B6 | The key reaches rclone only through the child env; the env file contributes only `SESSION_ARCHIVE_*` lines; inherited `RCLONE_*` are stripped | no argv element contains the key; the child env holds `RCLONE_CONFIG_SESSIONB2_KEY`; a fixture file with `export SESSION_ARCHIVE_B2_KEY_ID="k"`, a CRLF line and an `OTHER_SECRET=x` line parses the first two and never exposes `OTHER_SECRET`; a parent `RCLONE_B2_HARD_DELETE=true` is absent from the child env |
| A-B7 | `_rclone` refuses every non-allowed verb and every deleting flag | `sync`, `move`, `moveto`, `delete`, `deletefile`, `purge`, `cleanup`, `rmdir`, `rmdirs`, `backend` each raise `ValueError` (ten spellings, executable cases); `--delete-after`, `--b2-hard-delete` and `--b2-hard-delete=true` as arguments raise; an AST walk finds the string `"rclone"` as a list head ONLY inside `_rclone` |
| A-B8 | A failed `copy` writes no rows | with fake keys set, `copy` returning non-zero → rc 1, zero rows, and the recorder shows `copy` WAS called (the failure is the transport's, not the key check's) |
| A-B9 | A failed manifest `copyto` exits 1 and keeps the rows; the next run re-ships the manifest | rc 1, rows present; a second run with `copyto` succeeding calls it again |
| A-B10 | A held lock makes a second run exit 0 without touching the archive | with the lock held by the test, rc 0, a "lock held" line, no recorded call, no new row |
| A-B11 | `ARCHIVE_AFTER_DAYS` defaults to 0 (amended 2026-10-08) | with the variable unset, a transcript modified now and one aged two days are both eligible; a transcript that grows mid-archive gets a row whose sha256 and bytes match its decompressed object |
| A-B12 | A missing `zstd` or `rclone` exits 1 naming it | with `shutil.which` returning None for each in turn, rc 1 and the binary named |
| A-B13 | The unit files carry no `EnvironmentFile=`, run the MAIN checkout's script, and the timer is `Persistent=true` | parse both files under `scripts/sysadmin/systemd/` |

The four revision-1 tests (sha matches source, slug disambiguation, subagents excluded, per-file
ceiling) stay green under the fixture's explicit `ARCHIVE_AFTER_DAYS=0`. Revision 1's AST test
over `rsync` argv is replaced by A-B7.

## Execution discipline

- **A `/fabrik-review-scoped` pass at EVERY phase boundary, blocking** — Phase A's changed surface
  (the archiver, its tests, the two unit files, the installer, the docs) is reviewed by independent
  finder seats (refute → prove-before-fix with a kept regression test → re-run the gate after each
  fix) to a quiet closing round BEFORE Phase B starts; Phase B's evidence edit gets the same pass
  before the plan flips EXECUTED. The archiver is a backup path, so a Phase-A review that finds a
  transport or credential defect re-opens Phase A, never ships it as a follow-up.
- **Dispatch policy: native seats only (the pool is OFF, D-181).** Review finders are
  `fabrik-reviewer` seats sized by `dispatch_headroom.py`, stamped with `command_run.py dispatch`
  before they go out; the orchestrator (Opus or Fable) executes every refutation and every
  confirmed reproduction.
- **Parallelism:** in Phase A the tests and the unit-file / installer / doc work are independent
  and may run concurrently; they MERGE at Gate A. Phase B is strictly after Phase A — it restores
  what A shipped.
- **Order of the live steps:** (1) Phase A code + tests + review; (2) Gate 0 and Gate A from THIS
  worktree — the sampler and the archiver run by hand (`bash scripts/sysadmin/sample_transcript_growth.sh`,
  `.venv/bin/python scripts/sysadmin/archive_transcripts.py`), the key read from `/opt/fabrik/.env`
  by A.2a; (3) Phase B + Gate B; (4) `/fabrik-docs-review`, a fresh `final_gate.py --check --json`,
  the merge request (`merge_request.py request`); (5) after infra merges, Gate S — the installer
  and the first timer run; only then Status EXECUTED and the plan archived. The unit points at the
  MAIN checkout's script, which is why (5) waits for the merge.

## Open / blocking unknowns

0. **(2026-10-11) Gate B's download leg** — BLOCKING for Gate C's first `--apply`, not for C.1–C.4's
   code or for the dry-run. This network blocks `f004.backblazeb2.com` (SNI); the per-object size +
   SHA1 listing (C.2.1 r6) works and is the per-run integrity check, but one real download (B.1–B.5)
   is owed before the first deletion. RESOLUTION, operator step: run B.1–B.5 from a network that
   reaches the host (`curl -sI https://f004.backblazeb2.com/` answers), paste the output into
   Evidence. Absent at Gate C ⇒ the unit stays on dry-run, nothing is deleted; not a `BLOCKED:` for
   the earlier gates.
1. **The B2 application key for `wsl-ozgur`** — RESOLVED 2026-10-08 (D-720). Kept for the record:
   BLOCKING for Gate A and Gate B, not for the code.
   Asked of the operator 2026-10-05 (no existing key can reach the bucket — § A.3). RESOLUTION,
   self-service once it exists: the operator writes `SESSION_ARCHIVE_B2_KEY_ID` and
   `SESSION_ARCHIVE_B2_APPLICATION_KEY` into `/opt/fabrik/.env`; the executor checks presence with
   `awk -F= '/^SESSION_ARCHIVE_B2_(KEY_ID|APPLICATION_KEY)=/ {print $1, (length($2)>0 ? "set" : "empty")}' /opt/fabrik/.env`
   (names and emptiness only, never a value) before Gate A. Absent at Gate A ⇒
   `BLOCKED: missing infra — the wsl-ozgur application key`.

## File Scope (owned paths)

- `scripts/sysadmin/archive_transcripts.py`
- `tests/test_archive_transcripts.py`
- `scripts/sysadmin/systemd/session-archive.service` (new)
- `scripts/sysadmin/systemd/session-archive.timer` (new)
- `scripts/sysadmin/install_session_archive_timer.sh` (new)
- `docs/workstation/session-history-retention.md` (new)
- `docs/development/plans/2026-09-06-plan-1-session-history-retention.md`
- `docs/superpowers/specs/2026-09-05-session-history-retention-design.md`
- `.env.example` (Phase C: `SESSION_RECALL_RO_DSN`, `PRUNE_AFTER_DAYS`, `PRUNE_MAX_PER_RUN`, `ROTATE_ADVISE_MB`)
- `pyproject.toml` + `uv.lock` (Phase C.2 — `psycopg2-binary` declared, the lock regenerated; no other dependency changes)
- `docs/CONFIGURATION.md` (the same four rows)
- `scripts/sysadmin/prune_transcripts.py` (new, Phase C)
- `tests/test_prune_transcripts.py` (new, Phase C)
- `scripts/sysadmin/transcript_size_check.py` (new, Phase C)
- `tests/test_transcript_size_check.py` (new, Phase C)
- `scripts/sysadmin/install_user_hooks.py` (Phase C — the hook list)
- `tests/test_install_user_hooks.py` (Phase C)
- `docs/workstation/hooks-index.md` (Phase C — the hook row)
- `CLAUDE.md` (Phase C.4 — one paragraph under § Pointers; outside the governance-sync regex;
  reviewed by C.4's full `/fabrik-review`)

Not in File Scope, sent as requests (D-441): `templates/governance/CLAUDE.md` and
`scripts/whoami_agent.py` (infra — both governance-sync paths), `/opt/fabrik-lib/CLAUDE.md` (fabrik-lib),
`/opt/session-recall/ingest/reindex.py` + `db/schema.sql` + a nightly ingest timer (session-recall).
No wrapper script: the nightly mode (`--apply --nightly`) and the restore verb (`--restore`) live in
`prune_transcripts.py`.

Read, invoked, not modified: `scripts/sysadmin/sample_transcript_growth.sh` (the unit's
`ExecStartPre`; writes `~/.claude/state/transcript-growth.tsv`). Outside the repo, written at run
time (not repo paths, so not lockable): `~/.config/systemd/user/session-archive.{service,timer}` and
`~/.config/systemd/user/timers.target.wants/` (the installer), `~/.claude/archive/` (the archiver and
`pruned.jsonl`, `prune-log.jsonl`), `~/.claude/state/rotate-advised/` (the ROTATE hook's stamps),
`~/.claude/state/transcript-growth.tsv` (the sampler), `~/.claude/projects/README` (A.6), and the
bucket prefixes `archive/` and `restore-proof/`. Governance ledgers (`CHANGELOG.md`, `INDEX.md`,
`docs/DECISIONS.md`, `docs/LESSONS_LEARNT.md`, `docs/STRATEGIC_BACKLOG.md`) stay out of File Scope by
grammar.

## Rubric run (verbatim; the `# promote-to-check_*` tail elided)

```
$ python3 scripts/review_rubric.py --changed scripts/sysadmin/archive_transcripts.py tests/test_archive_transcripts.py scripts/sysadmin/systemd/session-archive.service scripts/sysadmin/systemd/session-archive.timer scripts/sysadmin/install_session_archive_timer.sh docs/workstation/session-history-retention.md docs/development/plans/2026-09-06-plan-1-session-history-retention.md docs/superpowers/specs/2026-09-05-session-history-retention-design.md .env.example docs/CONFIGURATION.md
# REVIEW RUBRIC — inject into EVERY finder prompt (generated by review_rubric.py)
# Honesty (L1): this arms the review — it raises compliance probability, it does not guarantee it.

## FLOOR — always injected, regardless of glob (spec L3; SERVICE surface)

### core/35-security-auth.md
**The default for ALL new projects, including user-facing SaaS + mobile.** Vendor `fabrik-lib/fastapi-user-auth`: the app issues its own JWTs — **Argon2id** (the vendored argon2-cffi defaults meet OWASP minimums; never Argon2i) + timing-equalized login, atomic refresh-token rotation (`DELETE … RETURNING`), JWT `jti` denylist revocation, and dual-mode tenant-isolation RLS. Supabase is retired as a default (see `agents-fabrik.md § Supabase`); reach for Pattern B only for a project that *already* runs on Supabase Auth.
- Do not use NextAuth.js, Clerk, Auth0, or Firebase Auth.
- ADDITIONAL affordance a project justifies, never the default door.
- project files the fabrik-lib request FIRST, never hand-rolls WebAuthn.
| `chrome-extension` | ✅ **use this** | ⚠️ only via `chrome.identity.launchWebAuthFlow` + the `https://<ext-id>.chromiumapp.org/` redirect the pack already mandates; a bare mailed link lands in a TAB that cannot reach `chrome.storage.session` |
| `desktop-app` | ✅ **use this** | ⚠️ needs a registered custom protocol handler; the token then goes to `safeStorage` (`desktop-app/72-desktop.md`) |
- service MUST be able to say which:
| **Another Fabrik service** (Docker-to-Docker on the `fabrik` network) | `X-Internal-Token` + `internal_auth.py`, `hmac.compare_digest`, 403 on reject | § Internal Service Auth (M2M) below — **never** an inline `APIKeyHeader`, never a per-service key name |
- An approval link opened somewhere the user did not start must never mint a session silently.
- > **Fail-closed invariant (hard, every mode).** `auth.uid()` and `current_tenant_id()` MUST return `NULL` (→ the policy denies) on unset, empty, or malformed claims — wrap the body in `EXCEPTION WHEN OTHERS THEN RETURN NULL`. **Never** raise and never default to a value: a default turns one bad/empty JWT into a cross-tenant read, and a raise turns a deny into a 500. This is the single most security-critical line in the build — verify it explicitly with a no-context probe (`SELECT auth.uid()` → `NULL`).
- The JWT signing secret must be at least 256 bits, generated via `openssl rand -hex 32`, and injected via Pydantic Settings. Never hardcode it.
- **Pin the algorithm in the VERIFIER** — pass an explicit allow-list (`algorithms=["HS256"]`), never let the library dispatch on the token header's `alg`. Header-driven dispatch is the classic confusion attack (an RS256 public key replayed as an HS256 HMAC secret); `alg: none` is rejected unconditionally.
- "Sticky sessions are a violation of twelve-factor and should never be used or relied upon."
- => Mandate: processes are stateless/share-nothing. **STICKY SESSIONS ARE BANNED** (not just file-based sessions). Session state goes to `redis-main` (Redis) with a TTL. Never in-process memory, never on local disk. Any design that assumes "the same user hits the same process" is a violation.
- **Pattern B (legacy / migration-only):** The Supabase client SDK handles token storage. On mobile, wrap with `expo-secure-store` (never AsyncStorage or MMKV for tokens). See `80-mobile.md` § Backend Integration.
- **Both patterns:** Never store JWTs in `localStorage` or `sessionStorage` on web. Never store JWTs in AsyncStorage or MMKV on mobile.
- **Chrome Extension (MV3) specifics:** `chrome.storage.session` defaults to `TRUSTED_CONTEXTS`, so **content scripts cannot read the token** — keep it in the SW / extension-page context and have content scripts fetch it via SW-mediated messaging (`chrome.runtime.sendMessage`), not a direct read. For social login use `chrome.identity.launchWebAuthFlow` with **PKCE** (`code_verifier` via `crypto.subtle`, held in `storage.session`, redirect `https://<ext-id>.chromiumapp.org/`); the **backend** does the code-for-token exchange. **Never a heavy browser auth SDK** (Auth0-SPA-JS, `oidc-client-ts`) — they assume DOM/`localStorage`/iframes and break in the service worker. Pin a manifest `key` so the extension ID (and thus the `chrome-extension://<id>` CORS origin) is stable across machines. Full detail: `chrome-ext/70-chrome-ext.md`.
- **Never rely solely on the framework's request-shaping layer for access control.** CVE-2025-29927 (the `x-middleware-subrequest` bypass) proved COMPLETE middleware bypass via one crafted header; it is long patched upstream, but the rule outlives the patch — current Next.js even RENAMED the file to say so: `middleware.ts` became **`proxy.ts`**, explicitly repositioned as request-shaping, not a security boundary. ⚠️ **On current majors a leftover `middleware.ts` is SILENTLY IGNORED at build** — nonce injection and redirects stop executing with no error; rename it when upgrading.
- `CORSMiddleware` in FastAPI must populate `allow_origins` from environment variables (Pydantic Settings). Never hardcode origins.
- `X-Frame-Options: DENY` — kept as the legacy fallback only; formally obsoleted by `frame-ancestors`, never ship it ALONE
**Never** write inline `APIKeyHeader` / `require_api_key`. **Never** use per-service key names (`SERVICE_API_KEY`, `PROXY_API_KEY`). Scaffold `python-api` auto-emits `internal_auth.py`, `metrics.py` (REQUEST_COUNT / ERROR_COUNT / ACTIVE_JOBS / PROCESSING_COUNT), `/metrics` endpoint (Authelia-bypassed), and `SERVICE_INTERNAL_SECRET_KEY` in `.env.example`.
- => Mandate: config via env vars only (`os.getenv("KEY", "default")`); **ZERO secrets/constants in code**. Apply the open-source litmus test to every change. **BANNED**: grouped/named env config sets (e.g. a `config/production.yml` or a `settings.production` group) — env vars are granular and orthogonal, set per deploy. (The pack already covers secret handling — cross-reference existing secret patterns and extend with config orthogonality.)
- [ ] Mobile tokens stored in `expo-secure-store` — never AsyncStorage or MMKV.
- > **⚠️ Bearer bypass scope — security-critical.** The bypass defaults to `^/api/`, which makes the **entire** `/api/*` surface public (un-2FA'd). If the application authenticates only a **sub-prefix** (e.g. `/api/v1` carries the bearer/internal-token check) while OTHER `/api/*` routes are unauthenticated (legacy / admin / destructive), you **MUST** narrow the bypass with `shape.bearer_bypass_prefix: "^/api/v1"` — otherwise `fabrik apply` exposes those routes to the public internet. **Bypass ONLY the path the app itself authenticates.** Value must start with `^/`; the verifier (`orchestrator/verifier.check_api_bypass`) probes the configured prefix on deploy. When unsure whether a service has un-auth'd `/api/*` routes, ask the app owner before relying on the `^/api/` default.

### core/25-data-postgres.md
| Vector search | pgvector on `postgres-main` + `fabrik-lib/rag` — ⚠️ the extension is NOT currently installed there (probed 2026-09-01: `postgres:16-alpine`, `plpgsql` only); a project needing vectors REQUESTS the fleet infra change first, never assumes it | same `postgres-main` DSN |
**"Own database" means a DATABASE on `postgres-main`, never a database SERVER.** Per-project isolation is a separate database (its own name, its own role) on the shared container — isolation, quota and backup are all satisfied at that grain. A dedicated Postgres instance is a decision, not a default: it needs its own `docs/DECISIONS.md` row naming what the shared server cannot serve (web-ecommerce-factory 01M1Q8X9, 2026-09-05: "one DB per store" read naively as one server per customer).
- Use Pydantic `BaseSettings` (per `10-python.md` § Config Loading) — never raw `os.getenv` **for an APPLICATION's settings surface**:
- ⚠️ **Scope, stated here because this LINE is what `review_rubric.py` injects — without its section.** The rubric FLOOR-injects this mandate *and* `35-security-auth`'s "config via env vars only (`os.getenv("KEY", "default")`)" into every finder prompt on every review, so a finder reading both literally has two rules it cannot both satisfy, and files a false positive on whichever it applies. The carve-out: `BaseSettings` governs a SERVICE's config surface (a `Settings` object, DB/Redis DSNs, secrets). A **vendored fabrik-lib module** has no settings object by design — it reads its own knobs with bare `os.getenv("KEY", "default")`, which is `35-security-auth`'s mandate being satisfied, not this … (wrapped further — read the pack)
- Never blindly trust `--autogenerate`. Always review `upgrade()` and `downgrade()` for unintended column drops, rename misinterpretations, and ENUM alterations before committing.
- > **Older pythons only** (services pinned below stdlib-uuid7 — which today includes SCAFFOLDED services: the scaffold still emits an older interpreter and ships `uuid-utils`; alignment tracked in the backlog): import `uuid7` from `uuid_utils.compat`, never `uuid_utils.uuid7()` directly — the latter returns `uuid_utils.UUID`, which asyncpg rejects (not a stdlib `uuid.UUID`). **DB-side:** newer PostgreSQL majors ship native `uuidv7()` (probe: `SELECT uuidv7()`); prefer `DEFAULT uuidv7()` at schema level where it exists. `postgres-main` currently runs major <!--v:postgres_major-->16<!--/v-->, which predates it — generate app-side on the fleet.
- Foreign keys must declare `ON DELETE` behaviour explicitly — `CASCADE` if children cannot exist without the parent, `RESTRICT` to protect audit trails. Never rely on the implicit default.
- This section owns the **canonical** engine, session, and `get_db`. `10-python.md` imports from here — never redefines its own.
- Database `AsyncSession` must be scoped to the route handler via `Depends()`. Never open sessions or transactions in global middleware — this holds connections during serialisation and I/O, exhausting the pool.
**BANNED as a server-side backing service** (dev, test, and prod alike):
**⚠️ SCOPE — this ban is about BACKING SERVICES, not client-local storage.** It does **NOT** apply to:
- **`desktop-app`** — SQLite is the **mandated** engine there (`desktop-app/72-desktop.md` § Local Persistence: `better-sqlite3` + SQLCipher; *"Production builds MUST encrypt the local SQLite file"*).
**12-Factor IV (Backing Services) — generalised:** swapping ANY attached backing service (DB, cache, object storage) is a **config change, never a code change**. The handle lives in `DATABASE_URL` / `REDIS_URL` / storage env — the code *reads* it, the code does not *decide* it. Never `if ENV == "prod":` branching to pick a host. (See § PostgreSQL Host Selection, which already mandates this for the DB.)
- [ ] All primary keys use UUIDv7 — stdlib `uuid.uuid7` on current Python (older pythons: `uuid_utils.compat.uuid7`, never direct `uuid_utils.uuid7()`); no `uuid4()`.

### core/30-ops.md
- the pinned release leaves full security support, never per-pack.
- All services deploy via `fabrik apply` (SSH + Docker Compose) on the `fabrik` network. Traefik routes external traffic — services do NOT bind host ports.
- **No `ports:` section.** All external traffic routes through Traefik. Never bind host ports. See Docker Port Security below. **12‑Factor VII (Port binding):** "the app is self‑contained and exports HTTP by binding to a port; it does not rely on runtime injection of a webserver" — which is exactly WHY no host `ports:`.
- **`container_name: <name>` is mandatory.** Same `_validate_compose()` gate refuses any service without it. Stable names are required so Gatus endpoints, inter-service URLs, and `docker exec`/`docker inspect` keys don't drift per redeploy. Use the bare service name (`browserless`, `gotenberg`, `meilisearch`, `glitchtip-web`, `site-provisioner`, etc.) — never UUID-suffixed names.
- gets one (ruling D-052) — see `core/60-watchdog.md`. Do not author a `watchdog: { enabled: false }` opt-out; if a project genuinely cannot host the sidecar, that is a ruling to obtain, not a default to flip.
- path before the flag goes in the spec, and assert target health (`/api/v1/targets` → `up`), never a bare `curl` of a path you assumed.
- remove it` on the hub) names a plan that protects nothing. Never add a service-named plan.
- health-enabled service can NEVER pass `up -d --wait` on a fresh database, and the deploy hangs to timeout.  An init the deploy cannot perform itself is a runbook step the plan MUST own.
- `fabrik redeploy <app>` SSHes to the VPS and runs `git pull` + `docker compose up -d --wait` against the **GitHub remote**, NOT the local `/opt/<app>` clone. Skipping `git push` redeploys the previous remote commit — the VPS never sees local changes.
**Mandate:** build → release → run are strictly separated. Releases are IMMUTABLE; the git SHA is the release ID. NEVER hot‑patch a running container (no `docker exec` to edit code/config in place, no in‑place code mutation on the VPS). Any change = a new build + a new release via `fabrik apply` / `fabrik redeploy`.
- Runtime database migrations that modify the app container (migrations MUST be run as separate deploy‑time steps)
**Place a service next to its data.** A spoke-hosted service reaches `postgres-main`/`redis-main` over the WireGuard mesh, and that hop is cross-Atlantic (Coventry ↔ LA) on EVERY query — a per-request chatty service pays it hundreds of times per page. So a DB-chatty service targets vps1; a spoke earns a service whose data traffic is light, batched or cached; a service PINNED to a spoke by hardware (GPU) batches or caches its data access — the data never moves off vps1. Measure before choosing (`ping 10.99.0.1` from the spoke, and the request's query count), never assume — the correctness rule ("container DNS, never localhost") says nothing about latency.
**Mandate:** WSL dev and the VPS run the SAME backing services (PostgreSQL + Redis), same major version. NEVER substitute a different backing service in dev (no SQLite standing in for Postgres, no in‑memory dict standing in for Redis). The same code must run unmodified in both environments.
- WSL runs PostgreSQL + Redis at the SAME MAJOR as the VPS containers — probe the live truth, never copy a tag from a doc: `ssh vps "sudo docker inspect postgres-main redis-main --format '{{.Config.Image}}'"` (2026-09-01: `postgres:16-alpine` · `redis:7-alpine` — upstream official images, outside OUR-image Alpine ban per § Banned Patterns)
**Invariant:** Never use `ports:` in compose.yaml to expose internal services to the host. All external traffic must go through Traefik.
**Health endpoints (`/health`, `/healthz`, `/metrics`, `/api/health`) bypass Authelia on all services** — required for Gatus and Prometheus monitoring. The bypass is **resource-based, not domain-bound** — applies on every domain routed through Authelia (hub direct + spokes via `authelia-vps1@file` middleware). Never protect these paths.
**CRITICAL:** Use `web`/`websecure` in Traefik labels — never `http`/`https` (those entrypoints do not exist). The scaffolder emits the correct entrypoint names; if you hand-write labels, match these exactly.
**Mandate:** migrations and admin tasks run as a ONE‑OFF process against the DEPLOYED image + env — identical environment to regular processes. NEVER run admin tasks from a laptop against prod, NEVER via `docker exec` into a live container, and **ABSOLUTELY NEVER auto-run migrations from app startup/`lifespan`** (concurrent replicas race the Alembic version table → wedged deploy).
- > **`fabrik run` and `.fabrik/hooks/post-deploy/` do NOT exist** — the real CLI answers `Error: No such command 'run'`, the hook path appears nowhere in the platform, and `_post_deploy_sync()` (`cli.py:64`) only refreshes `data/projects.yaml`; an agent following either ships a deploy where migrations never run. Do not re-add either without a `path:line` in `src/fabrik/` that executes it.
**Processes are share-nothing:** any state shared across requests MUST go to Redis (`redis-main`) with a TTL. A project using Redis for sessions MUST declare `shape.needs_cache: true` in `specs/services/<id>.yaml`, or `fabrik apply` skips the Redis registrar and the deploy is silently broken.
- "A twelve-factor app never relies on implicit existence of system-wide packages"
**Mandate:** any binary the app shells out to (ffmpeg, yt-dlp, poppler, tesseract…) MUST be `apt-get install`-ed in the Dockerfile, with a `shutil.which()` startup probe that fails fast. **The pinned base image is the version boundary** — exact `=version` apt pins are banned: they break on every Debian point release as old debs leave the mirrors (the "works then mysteriously breaks" class this section exists to prevent); the codename pin + image digest give the reproducibility. Never assume `curl`/ImageMagick/ffmpeg exist in the image — they don't by default.

### 12-FACTOR (all twelve axes)
- I codebase: shared code → fabrik-lib, never two apps in one repo
- II deps: every shelled-out binary installed + pinned in the Dockerfile
- III config: granular env vars; no secrets in code; no grouped env sets
- IV backing services: swappable by DSN/config change only
- V build/release/run: releases immutable; never hot-patch a container
- VI processes: stateless; session state → redis-main; no sticky sessions
- VII port binding: bind in-container; Traefik routes; no host ports:
- VIII concurrency: scale out; never daemonize or write PID files
- IX disposability: SIGTERM returns in-flight jobs to the queue; jobs idempotent
- X dev/prod parity: same backing services everywhere; no SQLite-for-Postgres
- XI logs: unbuffered stdout only; the app never writes/rotates a logfile
- XII admin: migrations/one-offs run against the deployed release, never startup

## MATCHED — packs whose globs hit the changed paths

### core/10-python.md  (hit: scripts/sysadmin/archive_transcripts.py, tests/test_archive_transcripts.py)
**`uv`** is the mandated Python package manager. Never use raw `pip`, `pip install`, `poetry`, or `pipenv`.
- Dependencies live in `pyproject.toml` + `uv.lock`. Do not modify these files unless the ticket authorises it.
- its own reviewed commit, never as a side effect of unrelated work.
- The one RULE: use SQLAlchemy async consistently — never mix `async def` with sync `.query().all()` (the Banned table row; the full session pattern is `25-data-postgres.md`'s).
- The canonical `engine`, `async_session`, and `get_db` are defined in `src/database.py` — owned by `25-data-postgres.md`. Import from there, never redefine:
**Config convention:** apps read a complete `DATABASE_URL` (`postgresql+asyncpg://user:pass@host:port/db`) and `REDIS_URL` from env. Discrete `DB_HOST`/`DB_PORT`/`DB_NAME`/`DB_USER`/`DB_PASSWORD` for the app to assemble are **banned**. The env supplies the complete URL — `localhost` in WSL, `postgres-main` on VPS — so the host concern is an env-layer responsibility, never code logic. See `30-ops.md` compose template for how discrete vars are interpolated into `DATABASE_URL` at the compose level.
- volume** (`30-ops.md` § Volumes), never in `.tmp` and never in `/tmp`.
**GlitchTip discipline:** unhandled exceptions (FastAPI 500s) are auto-captured by GlitchTip with full stacktraces. In the `except Exception` branch, log a **short event name + correlation_id** — never `logger.exception()` (that duplicates the traceback in Loki AND GlitchTip). See `55-observability.md` § Error Reporting for the full rule.
**Note:** Use the scaffolded logger: `from {package}.logger import get_logger` (see `55-observability.md` § Pre-Scaffolded Logging). Do not use `structlog.get_logger()` directly or `logging.getLogger(__name__)`.
- **Never a bare `asyncio.create_task()`** — an unreferenced task is silently garbage-collected and its exceptions vanish. Hold the reference and await it, or use `asyncio.TaskGroup`.
- **`datetime.now(UTC)`, never `datetime.utcnow()`** — deprecated and naive; naive datetimes are a real cross-service defect class.
- Ruff's selected rule-sets MUST include `ASYNC` (blocking IO in async code — machine-enforces this pack's hardest-to-review rule), `B` (bugbear) and `S` (bandit) alongside the defaults; configured in `pyproject.toml`, emitted by the scaffolder.
- Production services run via `uvicorn` CLI in the Dockerfile, not `uvicorn.run()` in code. Base image is always the pinned Debian `-slim` variant on `linux/amd64` (the variant is pinned fleet-wide in `30-ops.md` § Container Base Images — change it THERE, never per-repo). Never use Alpine — musllinux wheels exist now (PEP 656) but coverage is still partial, source builds are dramatically slower, and musl's allocator/stack defaults degrade CPython; the trade never pays on this fleet.
- `uvicorn.run()` is for local development only. Never ship it in production code.
- a fleet scaling decision (more containers), never a per-app flag.
**BANNED: grouped/named env config sets.** 12F is explicit — *"env vars are granular controls, each fully orthogonal to other env vars"* — so a `config/production.yml`, a `settings.production` group, or a `config/{dev,staging,prod}.yaml` tree is a violation. Env vars are granular and set **per deploy**, never batched into a named "environment".
**BANNED:** `logging.FileHandler`, `logging.handlers.RotatingFileHandler`, `TimedRotatingFileHandler`, `loguru` file sinks, any `*.log` file write, any in-app log rotation/retention/cleanup. The app never decides where logs are stored or routed — Docker → Promtail → Loki does. Full rule: `55-observability.md` § Logs.
**Factor XII — Admin processes. NEVER migrate from app startup.**
**BANNED: `alembic upgrade head` in FastAPI's `lifespan`, in an `@app.on_event("startup")`, or as an import side-effect.** With more than one replica (or a restart storm) two containers run `upgrade head` **concurrently** → they race the Alembic version table → duplicate DDL → **wedged deploy**. Migrations are a **one-off admin process against the deployed release**: `docker compose run --rm <svc> alembic upgrade head` (see `30-ops.md` § Release & Admin Processes).

### core/40-documentation.md  (hit: docs/CONFIGURATION.md, docs/development/plans/2026-09-06-plan-1-session-history-retention.md, docs/superpowers/specs/2026-09-05-session-history-retention-design.md)
- > **⚠️ `docs/OPERATIONS.md` + `docs/DEPLOYMENT.md` are FLEET-AI INTERFACES, not just docs (D-065).**
- **Tier-1 (author → verify → converge; the author leg is NATIVE while the pool is OFF, D-181 — `scripts/doc_reconcile.py`'s pool author cannot dispatch):** for each **mechanically-detectable** doc whose Doc-Sync trigger fired (`docs/QUICKSTART.md` · `docs/CONFIGURATION.md` · `docs/data-contract.md` · `docs/SERVICES.md` · `docs/OPERATIONS.md` — the reliable-signal subset), `scripts/doc_reconcile.py` dispatches a cheap OpenRouter-pool author (`libs.subagents`, `pick_models("docs")`) to emit a **minimal structured patch**, **verifies it before applying** (a symbol cross-check catches invented endpoints; the orchestrator injects a higher-assurance native-Claude verify), and loops to a zero-edit round. Runs per phase in `/fabrik-execute-plan`; never blocks (fail-safe). The other docs (CHANGELOG, INDEX, FEATURES, RESILIENCE, PORTS, the READMEs, `db/schema.sql`, …) have no reliable mechanical content-signal → they rely on the touch-on-change backstop below + your own edit (force-update, not force-correct).
- The SSOT is the type-aware registry (`scripts/enforcement/_doc_registry.py::PROJECT_DOCS`) — this table is its project-facing rendering, kept in step, never a second truth. `/fabrik-plan-after-chat` (the plan set's spine + tickets — the ticket-format authority) injects these rows per ticket as its `Docs:` line.
- Standalone work (not plan execution) → `Agent-Role: primary`. Trailers go below a blank line, above `Co-Authored-By`. ⚠️ The trailer block must be its OWN paragraph with NO blank line inside it: git parses only the LAST paragraph, and only if it is all-trailers. A blank line before `Co-Authored-By:` demotes everything above it to prose; so does a prose line glued to the top of the block. Measured 2026-08-15: 200 of the last 200 hub commits carried `Agent-Role:` and only 10 parsed, because the old example here shipped the blank line.
- **⚠️ Link it or it is decoration.** *Measured:* requests for files that do NOT exist came ~zero from AI bots — agents never go looking. It follows (inference, not measurement) that a file only gets read when something points at it: reference it from the docs index or README.
- ⚠️ **In THIS repo `llms.txt` is GENERATED** (`scripts/generate_capability_index.py`, refreshed daily) — never hand-edit it; change the generator. A project writing one by hand owns it.
- either way. Cheap and reversible — never at the expense of `OPERATIONS.md`/`DEPLOYMENT.md`, which are the load-bearing agent interfaces (D-065).
- **No skipped heading levels** — `##` to `###`, never `##` to `####`
- **Fenced code blocks only** — never indented code (AI treats it inconsistently)

### core/45-testing-strategy.md  (hit: tests/test_archive_transcripts.py)
- **Behavior Contract**: every ticket enumerates its distinct **user-observable behaviors / acceptance criteria** and tests **each one** — one high-value integration/E2E test per behavior, risk-ordered, TDD for the risky ones. Skip trivia (getters / framework glue / config): **lean-but-complete, NOT 100%-line-coverage dogma**. Do not chase line coverage — ensure every behavior has a test that would fail if that behavior regressed. (Cheap pool subagents can author the per-behavior tests — the suggest→curate→author→fix workflow in `62-using-subagents.md` § Dispatch policy + `~/.claude/commands/fabrik-review.md`.)
- **No cosmetic assertions**: never assert against CSS classes, Tailwind utility strings, pixel measurements, or snapshot hashes. Assert application state and user-visible outcomes only.
- **Watched-fail-first** (for tests this change adds or modifies; trivia stays skipped per the Behavior Contract): a non-trivial behavior's test proves something only if it has been SEEN RED — either write it first and watch it fail, or (after the fact) neuter the fix/feature, prove the test goes red, then RESTORE and re-run to green. The neutered state is never staged, committed, or left in the tree. A green test never seen red is unverified — a suite can pass with its guard deleted.
- **Run tests**: `uv run pytest tests/` (never bare `pytest` — Fabrik uses `uv`) — **when the project has a `pyproject.toml`/`uv.lock`**. A `requirements.txt`-only project (no manifest) runs `.venv/bin/python -m pytest tests/` — the manifest clause chooses the RUNNER, it never disarms the mandate to run the suite (web-ecommerce-factory 01M1QEY5, 2026-09-05: the clause read as "does not apply here"). ⚠️ **Gate this on the manifest, because this line is FLOOR-injected into finder prompts and a vendored fabrik-lib MODULE has neither by design**: the module recipe ships `requirements.txt` (`fabrik-lib/README.md` § Creating a Reference Implementation), so `uv run` cannot resolve it and `python3 -m pytest` is the only thing that works. Telling a finder the sole working … (wrapped further — read the pack)
- **Zero-mock database policy**: never mock SQLAlchemy, SQLModel, or database sessions. All backend tests execute against a real PostgreSQL instance.
- **`ASGITransport` never runs lifespan** — anything the app initializes at startup (scaffolded apps are lifespan-based) silently does not exist in tests; wrap with `asgi-lifespan`'s `LifespanManager` when a test needs startup state.
- Use `structlog` in test helpers if logging is needed — never `print()`. See `55-observability.md`.
- **Never stub a server action from Playwright** — the server is the E2E boundary; stubbing belongs in the unit lane where the action is a plain function.
- Run Playwright against the PRODUCTION build (`next build && next start`), never the dev server.
- All locators must be **semantic**: `page.getByRole('button', { name: /submit/i })`. Never use CSS selectors or XPath.
- Launch Playwright's **bundled Chromium** (`channel: 'chromium'`) — stable Chrome/Edge removed the `--load-extension` / `--disable-extensions-except` side-load flags (Chrome 137/139), so those args only work under bundled Chromium, never installed stable Chrome.
- Run `@axe-core/playwright` with **`bypassCSP: true`** (the non-relaxable extension CSP otherwise makes axe throw on `chrome-extension://` pages); keep `@axe-core/playwright` a **dev-dependency only** (MPL-2.0 — never bundled into the shipped artifact). Gate bundle size with `size-limit` **per surface** (popup / side-panel / content-script). Full loop: `chrome-ext/70-chrome-ext.md` § Testing & UI Verification.
- Keep the generated types committed and re-generate on schema changes (`uv run python -c "import json; from <package>.main import app; print(json.dumps(app.openapi()))" > openapi.json` — the scaffold emits `src/<package>/main.py`, never a flat `src/main.py`, so `src.main` imports nothing).
**BANNED in tests:**
| A GUARD proven only by the ONE spelling of the defect you already fixed | Write the guard's subject five LEGITIMATE ways — five a DIFFERENT author would plausibly write, not five typos of yours — and count how many it still catches; one of five means it is keyed on your fix, not on the class — and one of five is the FLOOR of the failure, never its definition: four of five is a partial class and is reported as four of five. This is IN ADDITION to red-on-revert below, not a rival bar: that one proves the guard fires at all, this one proves it fires on the class. ⚠️ Cheapest ways to satisfy it WITHOUT the outcome (`CLAUDE.md` § UNIVERSAL governance markers, the entry whose anchor is **you get the behavior you measure** — search the ANCHOR, not the rule name: the project-facing contract lists that section by anchor alone and carries the name `cobra-effect` nowhere): (i) write five near-identical spellings and count 5/5; (ii) ship at 2/5 and REPORT it, needing no fabrication at all, in the hope that a reported count reads as a passed one — it does not: under 5/5 is a finding; (iii) claim the exercise and record nothing, since the five are never committed. So the bar is TWO things and needs both: **the five go IN the test file as executable CASES**, never a comment — a comment cannot go RED, so nothing can falsify it, and that is the objection, not that it records nothing — **and anything under 5/5 is a finding, not a pass**. ⚠️ Two paths this row does NOT close, stated rather than pretended away: you can shrink the SUBJECT until five legitimate spellings all land inside what the guard already catches (nothing is fabricated; the claim narrowed, not the guard), and an honest 4/5 — real information, 80% of the class — costs the author something to report, so the cheapest response to it is silence. Report the count you got either way — a 4/5 with the miss NAMED is a finding someone can act on, and a 5/5 nobody can execute is not a pass at all. Measured 4× in one day across 2 repos (01M1S4D78KRM0ZSYDNGTHS9HYQ), and once more the day this row landed: a contract-parity grader that read the LIVE file instead of the tree under test stayed green under the exact drift it existed to catch |
| A test THIS change adds/modifies that was never seen red (no fail-first, no red-on-revert proof) | Watch it fail first, or neuter the change → prove red → restore → re-run green |
- [ ] Destructive DB tests call `require_throwaway(TEST_DATABASE_URL)` before connecting — never point them at a dev/shared DB.
# promote-to-check_*: … (elided here — the greppable-literal tail; the FLOOR and MATCHED sections above are verbatim)
```

## Rubric run (2026-10-11 revision; verbatim over the Phase C File Scope; the `# promote-to-check_*` tail elided)

```
$ python3 scripts/review_rubric.py --changed scripts/sysadmin/archive_transcripts.py tests/test_archive_transcripts.py scripts/sysadmin/systemd/session-archive.service scripts/sysadmin/systemd/session-archive.timer scripts/sysadmin/install_session_archive_timer.sh docs/workstation/session-history-retention.md docs/development/plans/2026-09-06-plan-1-session-history-retention.md docs/superpowers/specs/2026-09-05-session-history-retention-design.md .env.example docs/CONFIGURATION.md scripts/sysadmin/prune_transcripts.py tests/test_prune_transcripts.py scripts/sysadmin/transcript_size_check.py tests/test_transcript_size_check.py scripts/sysadmin/install_user_hooks.py tests/test_install_user_hooks.py docs/workstation/hooks-index.md CLAUDE.md
# REVIEW RUBRIC — inject into EVERY finder prompt (generated by review_rubric.py)
# Honesty (L1): this arms the review — it raises compliance probability, it does not guarantee it.

## FLOOR — always injected, regardless of glob (spec L3; SERVICE surface)

### core/35-security-auth.md
**The default for ALL new projects, including user-facing SaaS + mobile.** Vendor `fabrik-lib/fastapi-user-auth`: the app issues its own JWTs — **Argon2id** (the vendored argon2-cffi defaults meet OWASP minimums; never Argon2i) + timing-equalized login, atomic refresh-token rotation (`DELETE … RETURNING`), JWT `jti` denylist revocation, and dual-mode tenant-isolation RLS. Supabase is retired as a default (see `agents-fabrik.md § Supabase`); reach for Pattern B only for a project that *already* runs on Supabase Auth.
- Do not use NextAuth.js, Clerk, Auth0, or Firebase Auth.
- ADDITIONAL affordance a project justifies, never the default door.
- project files the fabrik-lib request FIRST, never hand-rolls WebAuthn.
| `chrome-extension` | ✅ **use this** | ⚠️ only via `chrome.identity.launchWebAuthFlow` + the `https://<ext-id>.chromiumapp.org/` redirect the pack already mandates; a bare mailed link lands in a TAB that cannot reach `chrome.storage.session` |
| `desktop-app` | ✅ **use this** | ⚠️ needs a registered custom protocol handler; the token then goes to `safeStorage` (`desktop-app/72-desktop.md`) |
- service MUST be able to say which:
| **Another Fabrik service** (Docker-to-Docker on the `fabrik` network) | `X-Internal-Token` + `internal_auth.py`, `hmac.compare_digest`, 403 on reject | § Internal Service Auth (M2M) below — **never** an inline `APIKeyHeader`, never a per-service key name |
- An approval link opened somewhere the user did not start must never mint a session silently.
- > **Fail-closed invariant (hard, every mode).** `auth.uid()` and `current_tenant_id()` MUST return `NULL` (→ the policy denies) on unset, empty, or malformed claims — wrap the body in `EXCEPTION WHEN OTHERS THEN RETURN NULL`. **Never** raise and never default to a value: a default turns one bad/empty JWT into a cross-tenant read, and a raise turns a deny into a 500. This is the single most security-critical line in the build — verify it explicitly with a no-context probe (`SELECT auth.uid()` → `NULL`).
- The JWT signing secret must be at least 256 bits, generated via `openssl rand -hex 32`, and injected via Pydantic Settings. Never hardcode it.
- **Pin the algorithm in the VERIFIER** — pass an explicit allow-list (`algorithms=["HS256"]`), never let the library dispatch on the token header's `alg`. Header-driven dispatch is the classic confusion attack (an RS256 public key replayed as an HS256 HMAC secret); `alg: none` is rejected unconditionally.
- "Sticky sessions are a violation of twelve-factor and should never be used or relied upon."
- => Mandate: processes are stateless/share-nothing. **STICKY SESSIONS ARE BANNED** (not just file-based sessions). Session state goes to `redis-main` (Redis) with a TTL. Never in-process memory, never on local disk. Any design that assumes "the same user hits the same process" is a violation.
- **Pattern B (legacy / migration-only):** The Supabase client SDK handles token storage. On mobile, wrap with `expo-secure-store` (never AsyncStorage or MMKV for tokens). See `80-mobile.md` § Backend Integration.
- **Both patterns:** Never store JWTs in `localStorage` or `sessionStorage` on web. Never store JWTs in AsyncStorage or MMKV on mobile.
- **Chrome Extension (MV3) specifics:** `chrome.storage.session` defaults to `TRUSTED_CONTEXTS`, so **content scripts cannot read the token** — keep it in the SW / extension-page context and have content scripts fetch it via SW-mediated messaging (`chrome.runtime.sendMessage`), not a direct read. For social login use `chrome.identity.launchWebAuthFlow` with **PKCE** (`code_verifier` via `crypto.subtle`, held in `storage.session`, redirect `https://<ext-id>.chromiumapp.org/`); the **backend** does the code-for-token exchange. **Never a heavy browser auth SDK** (Auth0-SPA-JS, `oidc-client-ts`) — they assume DOM/`localStorage`/iframes and break in the service worker. Pin a manifest `key` so the extension ID (and thus the `chrome-extension://<id>` CORS origin) is stable across machines. Full detail: `chrome-ext/70-chrome-ext.md`.
- **Never rely solely on the framework's request-shaping layer for access control.** CVE-2025-29927 (the `x-middleware-subrequest` bypass) proved COMPLETE middleware bypass via one crafted header; it is long patched upstream, but the rule outlives the patch — current Next.js even RENAMED the file to say so: `middleware.ts` became **`proxy.ts`**, explicitly repositioned as request-shaping, not a security boundary. ⚠️ **On current majors a leftover `middleware.ts` is SILENTLY IGNORED at build** — nonce injection and redirects stop executing with no error; rename it when upgrading.
- `CORSMiddleware` in FastAPI must populate `allow_origins` from environment variables (Pydantic Settings). Never hardcode origins.
- `X-Frame-Options: DENY` — kept as the legacy fallback only; formally obsoleted by `frame-ancestors`, never ship it ALONE
**Never** write inline `APIKeyHeader` / `require_api_key`. **Never** use per-service key names (`SERVICE_API_KEY`, `PROXY_API_KEY`). Scaffold `python-api` auto-emits `internal_auth.py`, `metrics.py` (REQUEST_COUNT / ERROR_COUNT / ACTIVE_JOBS / PROCESSING_COUNT), `/metrics` endpoint (Authelia-bypassed), and `SERVICE_INTERNAL_SECRET_KEY` in `.env.example`.
- => Mandate: config via env vars only (`os.getenv("KEY", "default")`); **ZERO secrets/constants in code**. Apply the open-source litmus test to every change. **BANNED**: grouped/named env config sets (e.g. a `config/production.yml` or a `settings.production` group) — env vars are granular and orthogonal, set per deploy. (The pack already covers secret handling — cross-reference existing secret patterns and extend with config orthogonality.)
- [ ] Mobile tokens stored in `expo-secure-store` — never AsyncStorage or MMKV.
- A dedicated admin host on its own domain — never the customer-facing app's domain — behind 2FA: set `shape.is_admin_dashboard: true` there. The Authelia registrar adds a per-domain `two_factor` rule on `fabrik apply`, so every path on that domain sits behind 2FA except the standing `/health` and `/metrics` bypasses (D-366, `saas/60-saas-ui.md` § Admin). API services with bearer auth: set `shape.has_bearer_api: true` — the registrar inserts an Authelia **bypass** rule *before* the `two_factor` catch-all so machine/bearer callers aren't hit with interactive 2FA. Don't add Traefik `authelia-forward` middlewares manually — the scaffolder + registrars emit them.
- > **⚠️ Bearer bypass scope — security-critical.** The bypass defaults to `^/api/`, which makes the **entire** `/api/*` surface public (un-2FA'd). If the application authenticates only a **sub-prefix** (e.g. `/api/v1` carries the bearer/internal-token check) while OTHER `/api/*` routes are unauthenticated (legacy / admin / destructive), you **MUST** narrow the bypass with `shape.bearer_bypass_prefix: "^/api/v1"` — otherwise `fabrik apply` exposes those routes to the public internet. **Bypass ONLY the path the app itself authenticates.** Value must start with `^/`; the verifier (`orchestrator/verifier.check_api_bypass`) probes the configured prefix on deploy. When unsure whether a service has un-auth'd `/api/*` routes, ask the app owner before relying on the `^/api/` default.

### core/25-data-postgres.md
| Vector search | pgvector on `postgres-main` + `fabrik-lib/rag` — ⚠️ the extension is NOT currently installed there (probed 2026-09-01: the plain upstream PostgreSQL Alpine image, `plpgsql` only — `CLAIMS.yaml` row `fleet-postgres-main-no-pgvector`); a project needing vectors REQUESTS the fleet infra change first, never assumes it | same `postgres-main` DSN |
**"Own database" means a DATABASE on `postgres-main`, never a database SERVER.** Per-project isolation is a separate database (its own name, its own role) on the shared container — isolation, quota and backup are all satisfied at that grain. A dedicated Postgres instance is a decision, not a default: it needs its own `docs/DECISIONS.md` row naming what the shared server cannot serve (web-ecommerce-factory 01M1Q8X9, 2026-09-05: "one DB per store" read naively as one server per customer).
- Use Pydantic `BaseSettings` (per `10-python.md` § Config Loading) — never raw `os.getenv` **for an APPLICATION's settings surface**:
- ⚠️ **Scope, stated here because this LINE is what `review_rubric.py` injects — without its section.** The rubric FLOOR-injects this mandate *and* `35-security-auth`'s "config via env vars only (`os.getenv("KEY", "default")`)" into every finder prompt on every review, so a finder reading both literally has two rules it cannot both satisfy, and files a false positive on whichever it applies. The carve-out: `BaseSettings` governs a SERVICE's config surface (a `Settings` object, DB/Redis DSNs, secrets). A **vendored fabrik-lib module** has no settings object by design — it reads its own knobs with bare `os.getenv("KEY", "default")`, which is `35-security-auth`'s mandate being satisfied, not this … (wrapped further — read the pack)
- Never blindly trust `--autogenerate`. Always review `upgrade()` and `downgrade()` for unintended column drops, rename misinterpretations, and ENUM alterations before committing.
- > **Older pythons only** (services pinned below stdlib-uuid7 — which today includes SCAFFOLDED services: the scaffold still emits an older interpreter and ships `uuid-utils`; alignment tracked in the backlog): import `uuid7` from `uuid_utils.compat`, never `uuid_utils.uuid7()` directly — the latter returns `uuid_utils.UUID`, which asyncpg rejects (not a stdlib `uuid.UUID`). **DB-side:** newer PostgreSQL majors ship native `uuidv7()` (probe: `SELECT uuidv7()`); prefer `DEFAULT uuidv7()` at schema level where it exists. `postgres-main` currently runs major <!--v:postgres_major-->16<!--/v-->, which predates it — generate app-side on the fleet.
- Foreign keys must declare `ON DELETE` behaviour explicitly — `CASCADE` if children cannot exist without the parent, `RESTRICT` to protect audit trails. Never rely on the implicit default.
- This section owns the **canonical** engine, session, and `get_db`. `10-python.md` imports from here — never redefines its own.
- Database `AsyncSession` must be scoped to the route handler via `Depends()`. Never open sessions or transactions in global middleware — this holds connections during serialisation and I/O, exhausting the pool.
**BANNED as a server-side backing service** (dev, test, and prod alike):
**⚠️ SCOPE — this ban is about BACKING SERVICES, not client-local storage.** It does **NOT** apply to:
- **`desktop-app`** — SQLite is the **mandated** engine there (`desktop-app/72-desktop.md` § Local Persistence: `better-sqlite3` + SQLCipher; *"Production builds MUST encrypt the local SQLite file"*).
**12-Factor IV (Backing Services) — generalised:** swapping ANY attached backing service (DB, cache, object storage) is a **config change, never a code change**. The handle lives in `DATABASE_URL` / `REDIS_URL` / storage env — the code *reads* it, the code does not *decide* it. Never `if ENV == "prod":` branching to pick a host. (See § PostgreSQL Host Selection, which already mandates this for the DB.)
- [ ] All primary keys use UUIDv7 — stdlib `uuid.uuid7` on current Python (older pythons: `uuid_utils.compat.uuid7`, never direct `uuid_utils.uuid7()`); no `uuid4()`.

### core/30-ops.md
- the pinned release leaves full security support, never per-pack.
- All services deploy via `fabrik apply` (SSH + Docker Compose) on the `fabrik` network. Traefik routes external traffic — services do NOT bind host ports.
- **No `ports:` section.** All external traffic routes through Traefik. Never bind host ports. See Docker Port Security below. **12‑Factor VII (Port binding):** "the app is self‑contained and exports HTTP by binding to a port; it does not rely on runtime injection of a webserver" — which is exactly WHY no host `ports:`.
- **`container_name: <name>` is mandatory.** Same `_validate_compose()` gate refuses any service without it. Stable names are required so Gatus endpoints, inter-service URLs, and `docker exec`/`docker inspect` keys don't drift per redeploy. Use the bare service name (`browserless`, `gotenberg`, `meilisearch`, `glitchtip-web`, `site-provisioner`, etc.) — never UUID-suffixed names.
- gets one (ruling D-052) — see `core/60-watchdog.md`. Do not author a `watchdog: { enabled: false }` opt-out; if a project genuinely cannot host the sidecar, that is a ruling to obtain, not a default to flip.
- path before the flag goes in the spec, and assert target health (`/api/v1/targets` → `up`), never a bare `curl` of a path you assumed.
- remove it` on the hub) names a plan that protects nothing. Never add a service-named plan.
- health-enabled service can NEVER pass `up -d --wait` on a fresh database, and the deploy hangs to timeout.  An init the deploy cannot perform itself is a runbook step the plan MUST own.
- `fabrik redeploy <app>` SSHes to the VPS and runs `git pull` + `docker compose up -d --wait` against the **GitHub remote**, NOT the local `/opt/<app>` clone. Skipping `git push` redeploys the previous remote commit — the VPS never sees local changes.
**Mandate:** build → release → run are strictly separated. Releases are IMMUTABLE; the git SHA is the release ID. NEVER hot‑patch a running container (no `docker exec` to edit code/config in place, no in‑place code mutation on the VPS). Any change = a new build + a new release via `fabrik apply` / `fabrik redeploy`.
- Runtime database migrations that modify the app container (migrations MUST be run as separate deploy‑time steps)
**Place a service next to its data.** A spoke-hosted service reaches `postgres-main`/`redis-main` over the WireGuard mesh, and that hop is cross-Atlantic (Coventry ↔ LA) on EVERY query — a per-request chatty service pays it hundreds of times per page. So a DB-chatty service targets vps1; a spoke earns a service whose data traffic is light, batched or cached; a service PINNED to a spoke by hardware (GPU) batches or caches its data access — the data never moves off vps1. Measure before choosing (`ping 10.99.0.1` from the spoke, and the request's query count), never assume — the correctness rule ("container DNS, never localhost") says nothing about latency.
**Mandate:** WSL dev and the VPS run the SAME backing services (PostgreSQL + Redis), same major version. NEVER substitute a different backing service in dev (no SQLite standing in for Postgres, no in‑memory dict standing in for Redis). The same code must run unmodified in both environments.
- WSL runs PostgreSQL + Redis at the SAME MAJOR as the VPS containers — probe the live truth, never copy a tag from a doc: `ssh vps "sudo docker inspect postgres-main redis-main --format '{{.Config.Image}}'"` (probed 2026-09-01: the plain upstream PostgreSQL Alpine image at the fleet major recorded in `CLAIMS.yaml` row `pg-fleet-major` · `redis:7-alpine` — upstream official images, outside OUR-image Alpine ban per § Banned Patterns)
**Invariant:** Never use `ports:` in compose.yaml to expose internal services to the host. All external traffic must go through Traefik.
**Health endpoints (`/health`, `/healthz`, `/metrics`, `/api/health`) bypass Authelia on all services** — required for Gatus and Prometheus monitoring. The bypass is **resource-based, not domain-bound** — applies on every domain routed through Authelia (hub direct + spokes via `authelia-vps1@file` middleware). Never protect these paths.
**CRITICAL:** Use `web`/`websecure` in Traefik labels — never `http`/`https` (those entrypoints do not exist). The scaffolder emits the correct entrypoint names; if you hand-write labels, match these exactly.
**Mandate:** migrations and admin tasks run as a ONE‑OFF process against the DEPLOYED image + env — identical environment to regular processes. NEVER run admin tasks from a laptop against prod, NEVER via `docker exec` into a live container, and **ABSOLUTELY NEVER auto-run migrations from app startup/`lifespan`** (concurrent replicas race the Alembic version table → wedged deploy).
- > **`fabrik run` and `.fabrik/hooks/post-deploy/` do NOT exist** — the real CLI answers `Error: No such command 'run'`, the hook path appears nowhere in the platform, and `_post_deploy_sync()` (`cli.py:64`) only refreshes `data/projects.yaml`; an agent following either ships a deploy where migrations never run. Do not re-add either without a `path:line` in `src/fabrik/` that executes it.
**Processes are share-nothing:** any state shared across requests MUST go to Redis (`redis-main`) with a TTL. A project using Redis for sessions MUST declare `shape.needs_cache: true` in `specs/services/<id>.yaml`, or `fabrik apply` skips the Redis registrar and the deploy is silently broken.
- "A twelve-factor app never relies on implicit existence of system-wide packages"
**Mandate:** any binary the app shells out to (ffmpeg, yt-dlp, poppler, tesseract…) MUST be `apt-get install`-ed in the Dockerfile, with a `shutil.which()` startup probe that fails fast. **The pinned base image is the version boundary** — exact `=version` apt pins are banned: they break on every Debian point release as old debs leave the mirrors (the "works then mysteriously breaks" class this section exists to prevent); the codename pin + image digest give the reproducibility. Never assume `curl`/ImageMagick/ffmpeg exist in the image — they don't by default.

### 12-FACTOR (all twelve axes)
- I codebase: shared code → fabrik-lib, never two apps in one repo
- II deps: every shelled-out binary installed + pinned in the Dockerfile
- III config: granular env vars; no secrets in code; no grouped env sets
- IV backing services: swappable by DSN/config change only
- V build/release/run: releases immutable; never hot-patch a container
- VI processes: stateless; session state → redis-main; no sticky sessions
- VII port binding: bind in-container; Traefik routes; no host ports:
- VIII concurrency: scale out; never daemonize or write PID files
- IX disposability: SIGTERM returns in-flight jobs to the queue; jobs idempotent
- X dev/prod parity: same backing services everywhere; no SQLite-for-Postgres
- XI logs: unbuffered stdout only; the app never writes/rotates a logfile
- XII admin: migrations/one-offs run against the deployed release, never startup

## MATCHED — packs whose globs hit the changed paths

### core/10-python.md  (hit: scripts/sysadmin/archive_transcripts.py, scripts/sysadmin/install_user_hooks.py, scripts/sysadmin/prune_transcripts.py)
**`uv`** is the mandated Python package manager. Never use raw `pip`, `pip install`, `poetry`, or `pipenv`.
- Dependencies live in `pyproject.toml` + `uv.lock`. Do not modify these files unless the ticket authorises it.
- its own reviewed commit, never as a side effect of unrelated work.
- The one RULE: use SQLAlchemy async consistently — never mix `async def` with sync `.query().all()` (the Banned table row; the full session pattern is `25-data-postgres.md`'s).
- The canonical `engine`, `async_session`, and `get_db` are defined in `src/database.py` — owned by `25-data-postgres.md`. Import from there, never redefine:
**Config convention:** apps read a complete `DATABASE_URL` (`postgresql+asyncpg://user:pass@host:port/db`) and `REDIS_URL` from env. Discrete `DB_HOST`/`DB_PORT`/`DB_NAME`/`DB_USER`/`DB_PASSWORD` for the app to assemble are **banned**. The env supplies the complete URL — `localhost` in WSL, `postgres-main` on VPS — so the host concern is an env-layer responsibility, never code logic. See `30-ops.md` compose template for how discrete vars are interpolated into `DATABASE_URL` at the compose level.
- volume** (`30-ops.md` § Volumes), never in `.tmp` and never in `/tmp`.
**GlitchTip discipline:** unhandled exceptions (FastAPI 500s) are auto-captured by GlitchTip with full stacktraces. In the `except Exception` branch, log a **short event name + correlation_id** — never `logger.exception()` (that duplicates the traceback in Loki AND GlitchTip). See `55-observability.md` § Error Reporting for the full rule.
**Note:** Use the scaffolded logger: `from {package}.logger import get_logger` (see `55-observability.md` § Pre-Scaffolded Logging). Do not use `structlog.get_logger()` directly or `logging.getLogger(__name__)`.
- **Never a bare `asyncio.create_task()`** — an unreferenced task is silently garbage-collected and its exceptions vanish. Hold the reference and await it, or use `asyncio.TaskGroup`.
- **`datetime.now(UTC)`, never `datetime.utcnow()`** — deprecated and naive; naive datetimes are a real cross-service defect class.
- Type the package, never `.`: the root walks the hub-synced `scripts/`, where mypy finds the same file under two module names and stops on every fresh project. file-worker types `mypy --explicit-package-bases worker`; a `server/` backend (saas-skeleton, static-site, office-extension, chrome-extension, mobile-app) runs `mypy src` from `server/` (D-605).
- Ruff's selected rule-sets MUST include `ASYNC` (blocking IO in async code — machine-enforces this pack's hardest-to-review rule), `B` (bugbear) and `S` (bandit) alongside the defaults; configured in `pyproject.toml`, emitted by the scaffolder.
- Production services run via `uvicorn` CLI in the Dockerfile, not `uvicorn.run()` in code. Base image is always the pinned Debian `-slim` variant on `linux/amd64` (the variant is pinned fleet-wide in `30-ops.md` § Container Base Images — change it THERE, never per-repo). Never use Alpine — musllinux wheels exist now (PEP 656) but coverage is still partial, source builds are dramatically slower, and musl's allocator/stack defaults degrade CPython; the trade never pays on this fleet.
- `uvicorn.run()` is for local development only. Never ship it in production code.
- a fleet scaling decision (more containers), never a per-app flag.
**BANNED: grouped/named env config sets.** 12F is explicit — *"env vars are granular controls, each fully orthogonal to other env vars"* — so a `config/production.yml`, a `settings.production` group, or a `config/{dev,staging,prod}.yaml` tree is a violation. Env vars are granular and set **per deploy**, never batched into a named "environment".
**BANNED:** `logging.FileHandler`, `logging.handlers.RotatingFileHandler`, `TimedRotatingFileHandler`, `loguru` file sinks, any `*.log` file write, any in-app log rotation/retention/cleanup. The app never decides where logs are stored or routed — Docker → Promtail → Loki does. Full rule: `55-observability.md` § Logs.
**Factor XII — Admin processes. NEVER migrate from app startup.**
**BANNED: `alembic upgrade head` in FastAPI's `lifespan`, in an `@app.on_event("startup")`, or as an import side-effect.** With more than one replica (or a restart storm) two containers run `upgrade head` **concurrently** → they race the Alembic version table → duplicate DDL → **wedged deploy**. Migrations are a **one-off admin process against the deployed release**: `docker compose run --rm <svc> alembic upgrade head` (see `30-ops.md` § Release & Admin Processes).

### core/40-documentation.md  (hit: CLAUDE.md, docs/CONFIGURATION.md, docs/development/plans/2026-09-06-plan-1-session-history-retention.md)
- > **⚠️ `docs/OPERATIONS.md` + `docs/DEPLOYMENT.md` are FLEET-AI INTERFACES, not just docs (D-065).**
- **Tier-1 (author → verify → converge; the author leg is NATIVE while the pool is OFF, D-181 — `scripts/doc_reconcile.py`'s pool author cannot dispatch):** for each **mechanically-detectable** doc whose Doc-Sync trigger fired (`docs/QUICKSTART.md` · `docs/CONFIGURATION.md` · `docs/data-contract.md` · `docs/SERVICES.md` · `docs/OPERATIONS.md` — the reliable-signal subset), `scripts/doc_reconcile.py` dispatches a cheap OpenRouter-pool author (`libs.subagents`, `pick_models("docs")`) to emit a **minimal structured patch**, **verifies it before applying** (a symbol cross-check catches invented endpoints; the orchestrator injects a higher-assurance native-Claude verify), and loops to a zero-edit round. Runs per phase in `/fabrik-execute-plan`; never blocks (fail-safe). The other docs (CHANGELOG, INDEX, FEATURES, RESILIENCE, PORTS, the READMEs, `db/schema.sql`, …) have no reliable mechanical content-signal → they rely on the touch-on-change backstop below + your own edit (force-update, not force-correct).
- The SSOT is the type-aware registry (`scripts/enforcement/_doc_registry.py::PROJECT_DOCS`) — this table is its project-facing rendering, kept in step, never a second truth. `/fabrik-plan-after-chat` (the plan set's spine + tickets — the ticket-format authority) injects these rows per ticket as its `Docs:` line.
- Standalone work (not plan execution) → `Agent-Role: primary`. Trailers go below a blank line, above `Co-Authored-By`. ⚠️ The trailer block must be its OWN paragraph with NO blank line inside it: git parses only the LAST paragraph, and only if it is all-trailers. A blank line before `Co-Authored-By:` demotes everything above it to prose; so does a prose line glued to the top of the block. Measured 2026-08-15: 200 of the last 200 hub commits carried `Agent-Role:` and only 10 parsed, because the old example here shipped the blank line.
- **⚠️ Link it or it is decoration.** *Measured:* requests for files that do NOT exist came ~zero from AI bots — agents never go looking. It follows (inference, not measurement) that a file only gets read when something points at it: reference it from the docs index or README.
- ⚠️ **In the hub (`/opt/fabrik`) `llms.txt` is GENERATED** (`scripts/generate_capability_index.py`, refreshed daily) — never hand-edit it there; change the generator. A project has no such generator; an `llms.txt` it ships, hand-written or built by its own code, is its own.
- either way. Cheap and reversible — never at the expense of `OPERATIONS.md`/`DEPLOYMENT.md`, which are the load-bearing agent interfaces (D-065).
- **No skipped heading levels** — `##` to `###`, never `##` to `####`
- **Fenced code blocks only** — never indented code (AI treats it inconsistently)

### core/45-testing-strategy.md  (hit: tests/test_archive_transcripts.py, tests/test_install_user_hooks.py, tests/test_prune_transcripts.py)
- **Behavior Contract**: every ticket enumerates its distinct **user-observable behaviors / acceptance criteria** and tests **each one** — one high-value integration/E2E test per behavior, risk-ordered, TDD for the risky ones. Skip trivia (getters / framework glue / config): **lean-but-complete, NOT 100%-line-coverage dogma**. Do not chase line coverage — ensure every behavior has a test that would fail if that behavior regressed. (Cheap pool subagents can author the per-behavior tests — the suggest→curate→author→fix workflow in `62-using-subagents.md` § Dispatch policy + `~/.claude/commands/fabrik-review.md`.)
- **No cosmetic assertions**: never assert against CSS classes, Tailwind utility strings, pixel measurements, or snapshot hashes. Assert application state and user-visible outcomes only.
- **Watched-fail-first** (for tests this change adds or modifies; trivia stays skipped per the Behavior Contract): a non-trivial behavior's test proves something only if it has been SEEN RED — either write it first and watch it fail, or (after the fact) neuter the fix/feature, prove the test goes red, then RESTORE and re-run to green. The neutered state is never staged, committed, or left in the tree. A green test never seen red is unverified — a suite can pass with its guard deleted.
- **Run tests**: `uv run pytest tests/` (never bare `pytest` — Fabrik uses `uv`) — **when the project has a `pyproject.toml`/`uv.lock`**. A `requirements.txt`-only project (no manifest) runs `.venv/bin/python -m pytest tests/` — the manifest clause chooses the RUNNER, it never disarms the mandate to run the suite (web-ecommerce-factory 01M1QEY5, 2026-09-05: the clause read as "does not apply here"). ⚠️ **Gate this on the manifest, because this line is FLOOR-injected into finder prompts and a vendored fabrik-lib MODULE has neither by design**: the module recipe ships `requirements.txt` (`fabrik-lib/README.md` § Creating a Reference Implementation), so `uv run` cannot resolve it and `python3 -m pytest` is the only thing that works. Telling a finder the sole working … (wrapped further — read the pack)
- **Zero-mock database policy**: never mock SQLAlchemy, SQLModel, or database sessions. All backend tests execute against a real PostgreSQL instance.
- **`ASGITransport` never runs lifespan** — anything the app initializes at startup (scaffolded apps are lifespan-based) silently does not exist in tests; wrap with `asgi-lifespan`'s `LifespanManager` when a test needs startup state.
- Use `structlog` in test helpers if logging is needed — never `print()`. See `55-observability.md`.
- **Never stub a server action from Playwright** — the server is the E2E boundary; stubbing belongs in the unit lane where the action is a plain function.
- Run Playwright against the PRODUCTION build (`next build && next start`), never the dev server.
- All locators must be **semantic**: `page.getByRole('button', { name: /submit/i })`. Never use CSS selectors or XPath.
- Launch Playwright's **bundled Chromium** (`channel: 'chromium'`) — stable Chrome/Edge removed the `--load-extension` / `--disable-extensions-except` side-load flags (Chrome 137/139), so those args only work under bundled Chromium, never installed stable Chrome.
- Run `@axe-core/playwright` with **`bypassCSP: true`** (the non-relaxable extension CSP otherwise makes axe throw on `chrome-extension://` pages); keep `@axe-core/playwright` a **dev-dependency only** (MPL-2.0 — never bundled into the shipped artifact). Gate bundle size with `size-limit` **per surface** (popup / side-panel / content-script). Full loop: `chrome-ext/70-chrome-ext.md` § Testing & UI Verification.
- Keep the generated types committed and re-generate on schema changes (`uv run python -c "import json; from <package>.main import app; print(json.dumps(app.openapi()))" > openapi.json` — the scaffold emits `src/<package>/main.py`, never a flat `src/main.py`, so `src.main` imports nothing).
**BANNED in tests:**
| A GUARD proven only by the ONE spelling of the defect you already fixed | Write the guard's subject five LEGITIMATE ways — five a DIFFERENT author would plausibly write, not five typos of yours — and count how many it still catches; one of five means it is keyed on your fix, not on the class — and one of five is the FLOOR of the failure, never its definition: four of five is a partial class and is reported as four of five. This is IN ADDITION to red-on-revert below, not a rival bar: that one proves the guard fires at all, this one proves it fires on the class. ⚠️ Cheapest ways to satisfy it WITHOUT the outcome (`CLAUDE.md` § UNIVERSAL governance markers, the entry whose anchor is **you get the behavior you measure** — search the ANCHOR, not the rule name: the project-facing contract lists that section by anchor alone and carries the name `cobra-effect` nowhere): (i) write five near-identical spellings and count 5/5; (ii) ship at 2/5 and REPORT it, needing no fabrication at all, in the hope that a reported count reads as a passed one — it does not: under 5/5 is a finding; (iii) claim the exercise and record nothing, since the five are never committed. So the bar is TWO things and needs both: **the five go IN the test file as executable CASES**, never a comment — a comment cannot go RED, so nothing can falsify it, and that is the objection, not that it records nothing — **and anything under 5/5 is a finding, not a pass**. ⚠️ Two paths this row does NOT close, stated rather than pretended away: you can shrink the SUBJECT until five legitimate spellings all land inside what the guard already catches (nothing is fabricated; the claim narrowed, not the guard), and an honest 4/5 — real information, 80% of the class — costs the author something to report, so the cheapest response to it is silence. Report the count you got either way — a 4/5 with the miss NAMED is a finding someone can act on, and a 5/5 nobody can execute is not a pass at all. Measured 4× in one day across 2 repos (01M1S4D78KRM0ZSYDNGTHS9HYQ), and once more the day this row landed: a contract-parity grader that read the LIVE file instead of the tree under test stayed green under the exact drift it existed to catch |
| A test THIS change adds/modifies that was never seen red (no fail-first, no red-on-revert proof) | Watch it fail first, or neuter the change → prove red → restore → re-run green |
- [ ] Destructive DB tests call `require_throwaway(TEST_DATABASE_URL)` before connecting — never point them at a dev/shared DB.
# promote-to-check_*: (83 injected mandates — elided, see the file)
```

## Pass Ledger (/fabrik-plan-review, revision 2026-10-11)

| Pass | seats · axes re-checked | counters | method | plan md5 (start → end) |
|-----:|---|---|---|---|
| Pass 1 | 7 seats (8 stamped — the researcher slice raised nothing and needed no refuter), section-partitioned (D-212): opus×1 (rules-invariant: C.2, Gate C, review floor, BC, Evidence, File Scope, CC13–21, Digest) + sonnet×2 (rest-phases: preamble, C.0/C.1/C.3/C.4, Intake; rest-ledgers: Context Ledger, Open unknowns, Rubric/Pass Ledger, Residual, Self-audit, spec marker) + fabrik-researcher×1 (cited-facts: the external citations and the systemd rule), refuter per slice (sonnet×3) · Q1–Q11 | found: 30, new: 30, confirmed: 27, refuted: 3 (O17 — the pinned dirs are one tree; O20 — the stop-decider anchor holds; S4 — the crash fix is independent of the tag), fixed: 27, unexecuted: 0, edits: 34 + 2 cite corrections | method: full pass over the pinned 31dcd50e8 revision + the arming (b7073f822); the refuters executed every check and the orchestrator re-executed the load-bearing ones before fixing (`whoami_agent.py` resolution and the refused re-bind; the registry's 1,401/9/6 liveness count and its single directory; `man systemd.service`; the reboot sweep's deletions; the crontab's second deleter; every cited anchor). The researcher's slice: 0 candidates, every external citation fetched live and faithful | c36d6c5fe1897d958513434b0040baa0 (+ arming b7073f822) → 883972d7fe07d56f03f2225c4bcb0c8c (before this row) |
| Pass 2 | the same 3 slices, 6 seats (8 stamped): opus×1 (rules-invariant) + sonnet×2 (rest-phases, rest-ledgers) + refuter per slice (sonnet×3) · the DELTA pass (D-339): every round-1 id re-verified over the fix diff, then the new text hunted | round-1 ids (27 unique; the ledger carried 30 rows, rest-ledgers S1–S3 twice): 23 NOW_FALSE, 3 STILL_TRUE (O10 → O30, O22 → O24, rest-phases-S3 → O29), 1 recorded NEW by the seat (O8 — closed through O25/O26), 0 REGRESSED; found: 14, new: 14, confirmed: 14, own-fix: 14 (all inside the round-1 fix text), fixed: 14, unexecuted: 0, edits: 30 | method: delta — the cap that refused instead of draining (O25/O26/O32), `last_at` as a freshness key (O27), the unconfigured database (O31), the unspecified `--verify-ledger` (O28), the swallowed exits (O29), the operator-named surfaces on a scoped review (O30/S5), the string `procStart` (O24), the uninformed `--force` (S4), the `--agent` row without a gate step (S6), the ledger's seat count (O33), rule 8's dependency on another repo (S5-ledgers); the orchestrator read `index_state`'s columns, `parse.py:108-122`, `README.md:34,63` and `psycopg` 3.3.4 in the hub venv before fixing | 0a2506a5b176b4708383f7f4b4012a6c → bd218780127b42d6d17230ebd2b80bdf (before this row) |
| Pass 3 | the same 3 slices, 6 seats (8 stamped): opus×1 + sonnet×2 + refuter per slice (sonnet×3) · the DELTA pass over the round-2 fix diff | round-2 ids (14): 12 NOW_FALSE, 2 STILL_TRUE (O27 → O34, rest-ledgers-S4 → O37/S7), 0 REGRESSED; found: 21 (4 of them re-verification statuses), new: 17, confirmed: 17, own-fix: 16 (the spec md5 in the header predates the review), fixed: 17, unexecuted: 0, edits: 22 + 2 | method: delta — rule 8 by inode (session-recall's `_one_name_per_inode`, read), the existing `recall_ro` (schema read), `psycopg2` and its lock pin (venv + `uv.lock` read), the pruner's own env reader, the `--who` verb that prints no pid (code read), `--expect` vacuous under `--max`, Gate C (2) vacuous, the summary row's writers, C.4's circular wait on the Finish review, two unlinks not atomic, the Pass 2 counters, the header's spec md5. `command_run.py round` printed the scope-growth stop (D-355): pass 4 re-verifies the FIXED set alone, no new hunt | 2676f864b3881ed04da1c2fbf467019a → f7309c2cc1ba50beba6361f11fc7028d (before this row) |
| Pass 4 | the same 3 slices, 6 seats (8 stamped): opus×1 + sonnet×2 + refuter per slice (sonnet×3) · RE-VERIFICATION of the fixed set alone (D-355) | round-3 ids: the rules-invariant seat's `ledger_status` carries its 14 (10 NOW_FALSE, 4 STILL_TRUE — O38 `--expect` still vacuous without `--max`; O39 Gate C (2) still passable with ingest mostly broken; O43 r8's `core/25` sentence; O47 the BC `--restore` row's one-inode promise — and O48/O49 filed as NEW), and the two Sonnet seats' round-3 ids (rest-phases-S7, rest-ledgers-S6/S7) have no `ledger_status` rows in pass-4.json — their FIXED statuses are in the seats' returned text in the workflow journal (`wf_c804dd39-fa3/journal.jsonl`), which the ledger file does not carry; 0 REGRESSED outside the fixed hunks; found: 9, new: 5 (O48 error-row scope, O49/S8 the Pass 3 counter, O50 the nightly dry-run row, rest-phases-S8 the grant's line), confirmed: 9, own-fix: 9, fixed: 9, unexecuted: 0, edits: 14 | method: re-verification — the refuters executed the `--who`/`--as` code paths, `_one_name_per_inode`, the `recall_ro` grant (at `:100`, not `:85-97`), the venv's `psycopg2` and `uv.lock`, the `_ENV_LINE` shape, both Digest quotes, and recounted pass-2/pass-3 ledgers; the orchestrator fixed only the nine and nothing else | 37c1cc763e6021c24fc78064ed020d0f → d826c2b4d68392b825832954aea4c0e4 (before this row) |
| Pass 5 | the same 3 slices, 5 seats (8 stamped; the rest-phases slice raised nothing and needed no refuter): opus×1 + sonnet×2 + refuter ×2 · RE-VERIFICATION of the nine round-4 fixes | round-4 ids (9): re-verified in the seats' notes (no `ledger_status` rows in pass-5.json), all FIXED at their core; found: 5, new: 5 (O51 the hard-link branch inherits the survivor's old `mtime`; O52 a diverged survivor leaves two inodes; O53 the exit-code line and the C.2.3 grader still unscoped; O54 Gate C (2) names rules 1–7 where the order evaluates 8 after 1–3; rest-ledgers-S9 the Pass 4 row's counter vs the ledger file), confirmed: 5, own-fix: 5, fixed: 5, unexecuted: 0, edits: 8 | method: re-verification — the refuters executed `os.link` mtime inheritance and the diverged-survivor case in scratch, the Digest quotes, `schema.sql:85-100`, and recounted pass-3/pass-4; the orchestrator fixed only the five | d436ce84eb8b37978c88eb5def39f3be → 06af6e7a6a707e450212bd320b1881bf (before this row) |
| Pass 6 | 2 slices, 4 seats (8 stamped): opus×1 (rules-invariant) + sonnet×1 (rest-ledgers) + refuter ×2 · RE-VERIFICATION of the five round-5 fixes | round-5 ids (5): all FIXED (recorded in the seats' notes; the opus seat's `ledger_status` is empty by its own report); found: 5 (4 new + S9 re-confirmed: the Pass 4 row's 'in their notes' named a field pass-4.json lacks — reworded in pass 7 to name the journal), new: 4 (O55 the touched inode is re-hashed nightly under A.1a; O56 the exit-3 list lacked `--restore`'s refusals; O57 no grader for the two new `--restore` outcomes; O58 the Pass 5 row's statuses rest on notes, not rows), confirmed: 5, own-fix: 5, fixed: 4, unexecuted: 0, edits: 5 | method: re-verification — the refuter executed `os.utime` on a hard-linked pair (the survivor's `mtime` moves too) and recounted pass-5.json (0 `ledger_status` rows); the orchestrator fixed only the four | 580de832df6cb47014131d1a97e217a7 → a80c8dd4f4b60abe9f8a036cc6342d02 (before this row) |
| Pass 7 | 2 slices, 4 seats (8 stamped): opus×1 + sonnet×1 + refuter ×2 · RE-VERIFICATION of the four round-6 fixes | round-6 ids (4): all FIXED (`ledger_status` rows in pass-7.json, NOW_FALSE ×4); found: 2, new: 2 (O59 `--restore`'s no-object refusal named one of two causes `--fetch` cannot tell apart and had no grader; rest-ledgers-S1 the Pass 4 row's 'in their notes' named a field the ledger file lacks), confirmed: 2, own-fix: 2, fixed: 2, unexecuted: 0, edits: 6 | method: re-verification — the refuter grepped the pin for every `unreachable` and read A.2 :146-149 against the exit-code line, C.2.5 and C.2.3; the orchestrator fixed only the two | b9fab016c3384c1717282564b9cddc3f → 25b304a47f5e5926e8f8f4f9e6d3fdcf (before this row) |
| Pass 8 | 2 slices, 3 seats (8 stamped; the rest-ledgers slice raised nothing and needed no refuter): opus×1 + sonnet×1 + refuter ×1 · RE-VERIFICATION of the two round-7 fixes | round-7 ids (2): both FIXED (`ledger_status` O59 NOW_FALSE; the Pass 4/6 rows' sources verified against the wf_c804dd39-fa3 journal's result rows by agentId); found: 2, new: 2 (O60 the `--fetch` refusal named two of the three causes A.2 maps to exit 1 — rclone's own failure missing; O61 its grader asserted no message), both PLAUSIBLE from the finder, confirmed by the refuter, own-fix: 2, fixed: 2, unexecuted: 0, edits: 4 | method: re-verification — the finder grepped every `unreachable`/`tell apart` in the pin (11 hits, all placed) and read A.2 :140-153; the orchestrator widened the refusal to the three causes and made the grader assert the message | 4ce5c6fd88e93924d382d054ce5c67a1 → 4e6e3482132ae7c61a40135641d7ef59 (before this row) |
| Pass 9 | 2 slices, 4 seats (8 stamped): opus×1 + sonnet×1 + refuter ×2 · RE-VERIFICATION of the two round-8 fixes | round-8 ids (2): both FIXED (`ledger_status` O60/O61 NOW_FALSE; the rest-ledgers seat recorded the same two as FIXED rows S2/S3); found: 5 rows, of which 2 defects (O62 = rest-ledgers-S1: 'rclone's own message' does not exist for the two causes where rclone exits 0 and writes nothing — the message is `--fetch`'s own line; O63: 'exits 1 for all three' overstated A.2's 'non-zero when rclone does'), confirmed: 2, own-fix: 2, fixed: 2, unexecuted: 0, edits: 4 | method: re-verification — the finder grepped the pin for every `brings nothing`/`both causes`/`tell apart`/`unreachable` (14 hits, all placed) and read A.2 :138-155 and the worked `--fetch` transcript :1393-1395; the orchestrator aligned the three sentences with A.2's exact words | 034eac457f7c7adc0d78a3892dff0758 → a8fd5f399b5405b280d3d4f4f7a5c273 (before this row) |
| Pass 10 | 2 slices, 3 seats (8 stamped; the rest-ledgers slice raised nothing and needed no refuter): opus×1 + sonnet×1 + refuter ×1 · RE-VERIFICATION of the two round-9 fixes | round-9 ids (2): both FIXED (the opus seat's notes; the rest-ledgers seat raised nothing); found: 1, new: 1 (O64: the C.2 text asserted rclone's exit code and message are passed through, which A.2 :145-146 never promises — only 'non-zero when rclone does'), confirmed: 1, own-fix: 1, fixed: 1, unexecuted: 0, edits: 3 | method: re-verification — the refuter's recorded grep over the pin's exit/stderr/rclone claims returned 5 hits (:145, :385, :388, :523, :1641 — pass-10.json's verdict output) against A.2 :144-149; the orchestrator weakened the four phrases to A.2's words | 12ac1059b49991f92ac9c5dad7ab19fa → 440e9ef0b193d933ae4ecaba7f08f616 (before this row) |
| Pass 11 | 2 slices, 3 seats (8 stamped): opus×1 + sonnet×1 + refuter ×1 · RE-VERIFICATION of the one round-10 fix | round-10 id O64: FIXED (the refuter's verdict mechanism in pass-11.json; `ledger_status` rows there: 0); found: 1, new: 1 (O65: the Pass 10 row's grep count had no source in pass-10.json), confirmed: 1, own-fix: 1, fixed: 1, unexecuted: 0, edits: 2 | method: re-verification — the refuter re-ran the recorded grep on the p10 pin (5) and searched pass-10.json for the claimed count (none); the orchestrator sourced the row from the ledger file. Seats, found, confirmed and `ledger_status` in this row are read from pass-11.json; edits from the fix diff (pr-p12-fix.patch); own-fix and fixed are the orchestrator's disposition | 0b3ba5cf47d9ef9289e41fbbd99658a6 → 480330c9fa86c47a58b5df4afb5517ca (before this row) |
| Pass 12 | 1 slice, 2 seats (8 stamped): opus×1 + refuter ×1 · RE-VERIFICATION of the one round-11 ledger fix | round-11 id O65: its 5-hit count stands (pass-10.json's verdict output); its 13 attribution was confirmed unsourced as rest-ledgers-O2 and closed in this round (`ledger_status` rows in pass-12.json: 0); found: 2, new: 2 (rest-ledgers-O1: the Pass 11 row's provenance sentence named cells pass-11.json does not hold; rest-ledgers-O2: the '13' attribution had no pinned source), confirmed: 2, own-fix: 2, fixed: 2, unexecuted: 0, edits: 3 | method: re-verification — the refuter grepped pass-11.json for every cell name the row claimed to source and searched four scratch locations for a standalone 13 (none). Seats, found, confirmed and `ledger_status` in this row are read from pass-12.json; edits from the fix diff (pr-p13-fix.patch); own-fix and fixed are the orchestrator's disposition | c5f556539e4326fbe01fd7435da02a6c → 7f418837a37fcdae577db09d091098cb (before this row) |
| Pass 13 | 1 slice, 2 seats (8 stamped): opus×1 + refuter ×1 · RE-VERIFICATION of the two round-12 ledger-cell fixes | round-12 ids O1, O2: both NOW_FALSE (pass-13.json `ledger_status`, 3 rows: O1 NOW_FALSE, O2 NOW_FALSE, O3 NEW); found: 1 (rest-ledgers-O3: the Pass 12 row's O65 cell cited a FIXED no verdict in pass-12.json states), confirmed: 1; own-fix: 1 and fixed: 1 are the orchestrator's disposition; unexecuted: 0; edits: 2 (from the fix diff pr-p14-fix.patch) | method: re-verification — the finder grepped the pin's Pass 10–12 rows and the refuter ran a python probe and greps over pass-12.json's verdict mechanisms for FIXED/O65 (neither names O65 FIXED). Seats, found, confirmed and `ledger_status` in this row are read from pass-13.json | f7774ea4f5e3847456960145ad630044 → c3053b6dec4a44e3e82000e2a95a33dc (before this row) |
| Pass 14 | 1 slice, 2 seats (8 stamped; pass-14.json labels: find:rest-ledgers:opus, refute:rest-ledgers) · RE-VERIFICATION of the round-13 ledger-cell fix | pass-14.json top-level `ledger_status`: 0 rows (none); found: 2, confirmed: 2 (rest-ledgers-O1: the Pass 13 row said no rows where pass-13.json's top-level `ledger_status` has 3; rest-ledgers-O2: its method cell gave the finder's pin grep to the refuter); own-fix: 2 and fixed: 2 are the orchestrator's disposition; unexecuted: 0; edits: 3 (from the fix diff pr-p15-fix.patch) | method: re-verification — seats, found, confirmed, the seat labels and `ledger_status` in this row are read from pass-14.json by the script that appended the row; the orchestrator fixed the two cells and corrected its row-writer to read the top-level array | e995fb06d214e7719d339e1a7e262528 → 11fcd4a3ef83c2ead70c4df5aab33746 (before this row) |
| Pass 15 | 1 slice, 2 seats (8 stamped; pass-15.json labels: find:rest-ledgers:opus, refute:rest-ledgers) · RE-VERIFICATION of the two round-14 ledger-cell fixes | pass-15.json top-level `ledger_status`: 0 rows (none); found: 1 (rest-ledgers-O1 — its claim text is in pass-15.json), confirmed: 1; own-fix: 1 and fixed: 1 are the orchestrator's disposition; unexecuted: 0; edits: 3 (from the fix diff pr-p16-fix.patch) | method: re-verification — seats, labels, found, confirmed and `ledger_status` in this row are read from pass-15.json by the script that appended the row | c05b2902057bf605b18f57973a626a41 → 353910be0cb3fbb9517d7fe4ff9b478d (before this row) |
| Pass 16 | 1 slice, 1 seat (8 stamped; pass-16.json label: find:rest-ledgers:opus; the workflow dispatched no refuter — nothing to refute) · the QUIET round: RE-VERIFICATION of the round-15 ledger-clause fix | pass-16.json top-level `ledger_status`: 1 rows (O1 NOW_FALSE); found: 0, confirmed: 0, fixed: 0, unexecuted: 0 — `closable: true` from the workflow; edits after this round: the Status flip, this row and the D-row only | method: closing — the seat grepped the pin for the removed phrase (0 hits), probed pass-13/14/15.json's seat keys and top-level arrays, and recomputed both md5s in the Pass 15 row (match). Seats, label, found, confirmed and `ledger_status` in this row are read from pass-16.json by the script that appended the row | c465334c3054cccd5b03f15305610c15 (the quiet round's pin) → c465334c3054cccd5b03f15305610c15 (before this row) |

## Pass Ledger (/fabrik-plan-review, revision 2026-10-05)

| Pass | seats · axes re-checked | counters | method | plan md5 (start → end) |
|-----:|---|---|---|---|
| Pass 1 | opus×1 (rules: Phase A, BC, File Scope, Rubric, Checklist, Evidence, Digest, Gate mechanics) + sonnet×1 (rest), refuter per slice (sonnet×2) · all axes | found: 26, new: 26, confirmed: 25, fixed: 25, unexecuted: 0, edits: 1 | method: citation — full pass; 25 confirmed by the refuters' executed checks and re-executed by the orchestrator (find -mtime rounding, the `-mmin +1440` re-measure, hard-link count, GATE-SCOPE regex line, rubric over the full File Scope, digest quotes re-located), 1 orchestrator candidate (hard links), rest-S4 RECORDED — measured (a 2026-09-05 snapshot read as current; wording updated) | 7017f5f9… → 3e672238… |
| Pass 2 | opus×1 (rules, round-1 owner) + sonnet×1 (rest, round-1 owner), refuter sonnet×1 · delta over the round-1 fix hunks | found: 9, new: 9, confirmed: 9, fixed: 9, unexecuted: 0, edits: 1 | method: re-derivation — 24 of 25 round-1 claims NOW_FALSE, rules-O16 STILL_TRUE in part (no missing-file fixture → A-B5 widened); 8 NEW inside the fix hunks (flag `=value` spelling, the recorder faking zstd, the sampler failing `ExecStartPre`, `archived_at` ≠ upload time, two MAIN predicates mixed, Self-audit 24 vs 25, a missing zstd version line, `30-ops.md:224` → `:225`); own-fix 9 of 9; also the gate-driven digest reshape and Context Ledger, made after the pin | 39fb89c8… → 12f9dda0… |
| Pass 3 | opus×1 (rules, round-1 owner) + sonnet×1 (rest, round-1 owner), refuter sonnet×1 · delta over the pass-2 hunks + the post-pin digest/Context Ledger | found: 1, new: 1, confirmed: 1, fixed: 1, unexecuted: 0, edits: 1 | method: re-derivation — 10 of 10 rules claims and rest-S5 NOW_FALSE (8 digest quotes re-located verbatim at their lines; `ExecStartPre=-` proven by a transient `systemd-run --user` unit; `--b2_hard_delete` refused by rclone itself; 5953 − (117 − 59) = 5895); 1 NEW, rules-O33 (own-fix: pass 2's Context Ledger cited Linger and D-470 "from Evidence") → `loginctl` output added, D-470 cited to the ledger. Scope-growth stop: passes 2 and 3 both ≥ ⅔ own-fix — hunting suspended; the remaining pass re-verifies the fixed set only | 742d8ea3… → bdfc2206… |
| Pass 4 | opus×1 (rules, round-1 owner) · the remainder pass over the fixed set (rules-O33) | found: 0, new: 0, confirmed: 0, fixed: 0, unexecuted: 0, edits: 0 | method: re-derivation — rules-O33 NOW_FALSE, re-executed by the seat and by the orchestrator (`loginctl show-user ozgur -p Linger` → `Linger=yes`; `grep -c 'cleanupPeriodDays: 3650' docs/DECISIONS.md` → 2); a wording note on row 3 ("the ledger" = the decision ledger) RECORDED — measured (wording; changes no behaviour); standing clean since pass 3: every other class | d08eee8d… → d08eee8d… ✓ |

## Coverage Checklist

| # | Class | Source | Verdict | Evidence |
|---|---|---|---|---|
| CC1 | fail-open vs fail-closed on every gate/guard (missing key, failed transport, unreadable env file) | standing | FIXED | round 1 rules-O2/O7/O8/O16/O17: missing key or unreadable file → exit 1 before any call (A.2a, A-B5); a failed `copy` → exit 1, no rows (A-B8, now proven to reach the transport); a failed manifest `copyto` → exit 1, rows kept (A-B9); Gate A requires a count ≥ 1 through `--remote-count`, which exits non-zero with rclone |
| CC2 | cost / quota / limit accounting edges (B2 class-C calls, keep-all-versions storage, per-file ceiling) | standing | FIXED | rules-O20 (A.1a's size+mtime pre-check removes the daily re-read), rules-O10/O9 (sizes re-measured: 9.82 GB unique, 3.53 GB idle > 24 h, residual risk 5 re-priced), `--fast-list` kept; residual risk 7 names the over-1 GB files |
| CC3 | boundary / sentinel / prefix collisions (`SESSION_ARCHIVE_` prefix parse, slug/session key, remote path prefix) | standing | FIXED | the env-file regex is anchored `^(export\s+)?SESSION_ARCHIVE_[A-Z0-9_]+=` (A-B6 graded with an `OTHER_SECRET` line); hard-linked twins under two slugs (orchestrator, round 1: 117 paths, 59 inodes) → A.1b + A-B3; the proof objects live under their own prefix `restore-proof/` (B.4) |
| CC4 | behavior without a test (every A-B row has a test; Phase B is evidence, not code) | standing | FIXED | rules-O18: the units (A-B13), the verify step and the README marker are in Gate A; the manifest-ship failure (A-B9), the lock (A-B10) and the binary probe (A-B12) gained rows |
| CC5 | config via granular env vars, no secret in code or argv (12-Factor III) | `core/35-security-auth.md` / `core/10-python.md` FLOOR | FIXED | rules-O16: child-env-only key (A-B6), inherited `RCLONE_*` stripped, no `EnvironmentFile=` (A-B13); the endpoint is recorded, never passed (rules-O12) |
| CC6 | logs to stdout/stderr only, no log file written by the app (12-Factor XI) | `core/10-python.md` FLOOR | CLEAN | the archiver prints to stdout/stderr (the current script, `print(... file=sys.stderr)`); under systemd the journal captures it; no step writes a log file |
| CC7 | `uv`/no new dependency; rclone and zstd are system binaries probed, not installed | `core/10-python.md` / `core/30-ops.md:467` | FIXED | A.1c probes both with `shutil.which` (A-B12); stdlib only (`fcntl`, `subprocess`); `rclone v1.72.0` and zstd 1.5.5 present (Evidence) |
| CC8 | Behavior Contract + watched-fail-first for every new or modified test | `core/45-testing-strategy.md` MATCHED | FIXED | rules-O3 (fixture pins `ARCHIVE_AFTER_DAYS=0`), rules-O4 (A-B1's oracle is "no zstd call, no hash call", not inode/mtime, which a recompression keeps — executed), rules-O7 (A-B8 asserts the transport ran) |
| CC9 | a guard proven by more than the one spelling of its defect | `core/45-testing-strategy.md` MATCHED | FIXED | rules-O5/O6: an allow-list at run time inside `_rclone`, graded by ten refused verbs and three refused flag spellings as executable cases, plus the AST assertion that `"rclone"` heads a list only inside `_rclone` |
| CC10 | the new box-local doc is linked (INDEX row) and uses fenced code only | `core/40-documentation.md` MATCHED | CLEAN | § Docs owed names the `INDEX.md` row; the execution phase writes the doc; `/fabrik-docs-review` runs at Finish |
| CC11 | concurrency on the shared archive (hand run vs timer) | orchestrator, round 1 | FIXED | rules-O21: `flock` on `<ARCHIVE_ROOT>/.archive.lock` (A.1d, A-B10), excluded from the upload |
| CC12 | gates executable as written, in the order written | orchestrator, round 1 | FIXED | rules-O1/S1/O2/S2: Gate 0 and Gate A run by hand before the merge, Gate S after it; gates use `--remote-count`/`--fetch`, which carry the key; B.4 builds its own two versions in `restore-proof/` |
| CC13 | (2026-10-11) fail-open vs fail-closed on EVERY pruner clause — mtime window, OPEN test, newest-per-slug, sha equality, local `.zst` verify, remote size+SHA1, hard-link twins, `--expect`, the listing call failing | standing + `core/45-testing-strategy.md:22` | FIXED | round 1 rules-O2/O4/O5/O6/O7/O8/O9/O15/O16/O22 + round 2 O25–O27/O29/O31 + round 3 O35/O39/O47: every clause fail-closed — r2 by procStart, r5 by decompressed bytes under the row's slug, r7 by prune-time inode scan, r8 by index_state inode+size with no DSN ⇒ not deleted, the last look before unlink, the cap that takes the oldest N, the `-` ExecStart with the summary row; C.2.3 lists a RED-first grader per clause |
| CC14 | (2026-10-11) open-session detection soundness — pid reuse (`procStart` must match), dead registry entries (1,393 of 1,398), `pidDomain`, a pinned session (one registry dir for every slug), the identity file's `pid_start` and its 30-day trim, a window idle past the 3-day window after a reload (not OPEN — kept only as a project's or agent's newest, else restorable) | orchestrator, Phase C | FIXED | round 1 rules-O3/O22 + round 2 O24 + Evidence probe 5b (1,401 entries, 9 live pids, 6 matching procStart, 6 pidDomains, one registry dir for every slug): r2 matches pid + procStart as integers, the identity file is the belt (30-day trim named), a reload-closed idle window is kept only as a project's or agent's newest and is otherwise restorable (C.2.5) |
| CC15 | (2026-10-11) hard-link identity — `(st_dev, st_ino)` as the archiver groups it; twin names with differing mtimes; a twin the linker has not yet created | `scripts/sysadmin/worktree_transcript_link.py` | FIXED | round 1 rules-O2/O15 + rest-ledgers-S3 + rounds 4–6 O47/O51/O52: r7 scans `(st_dev, st_ino)` at prune time, a name without a row skips the inode, a twin created after the archive has no alias and is caught by r4; `--restore` re-links a surviving identical twin and touches the inode's mtime, refuses a diverged one |
| CC16 | (2026-10-11) remote integrity proof — `lsf --hash SHA1` on small AND multi-part objects, a stale version listed, a prefix with no objects, the download host still blocked (Gate C precondition) | `core/30-ops.md:225` (a backup that protects nothing reads green) | FIXED | round 1 rules-O9 + round 2 O28 + rounds 7–10 O59–O64: `--verify-ledger` re-runs rule 6 over every pruned row (size + SHA1, exit 3 on MISSING); Gate C (1) keeps the download proof as the precondition; the `--fetch` refusal names the three causes A.2 maps to a non-zero exit, in A.2's own words |
| CC17 | (2026-10-11) the ROTATE hook — reads `transcript_path` from the hook JSON (the field `worktree_transcript_link.py:92` reads; `selfwatch_check.py` reads only `session_id`/`cwd`), fail-open on every error, threshold env var, the 100 MB-step stamp (never per-prompt — `install_user_hooks.py:37-42`), the agent binding across `/clear` (keyed by session id; `--force` re-bind; the registry join) | `core/10-python.md` MATCHED | FIXED | round 1 rules-O1/O18/O21 + rest-phases-S1–S3 + round 2 S4 + round 3 O37/S7: the hook reads `transcript_path` (worktree_transcript_link.py:92), is stamped per 100 MB step (install_user_hooks.py:37-42), fails open; the binding is keyed by session id, the registry join tags a rotated window, the plain `--as` refusal's pid informs `--force`, the successor rule is infra's request |
| CC18 | (2026-10-11) unit ordering — a second `ExecStart=` in a `Type=oneshot` unit runs only after the first succeeds, and carries the `-` prefix so a pruner refusal never fails the unit nor re-runs the archiver under `Restart=on-failure` (`man systemd.service`, quoted in C.2; asserted by a unit-file test) | orchestrator, Phase C | FIXED | round 1 rules-O6 + `man systemd.service` read + round 2 O29 + rounds 4–5 O48/O50/O53: the second ExecStart is `-` prefixed, exit codes 0/3/1/2 named, the summary row scoped to dry-run/apply, `--status` prints the last row and the last apply row; the unit-file test asserts order and prefix |
| CC19 | (2026-10-11) data-integrity of the manifest as the delete authority — append-only, `also_slugs` aliasing, a row for the worktree slug while the canonical row is `-opt-fabrik`, `agent` key optional | `archive_transcripts.py:209-222` | FIXED | round 1 rules-O2/O14/O15 + round 2 O27/O31 + round 3 O35/O36/O42/O44: the manifest row's `agent` key is optional and derived (identity row, else the registry join); `also_slugs` aliasing is defused by r5's decompressed-bytes compare under the row's slug; `pruned.jsonl` has its consumer (`--restore`) and ships to B2 deliberately; r8 reads session-recall's `index_state` by inode through the existing `recall_ro` |
| CC20 | (2026-10-11) behaviour without a test — every Phase C G/W/T row names its grader; the governance-file paragraphs and the three mails have an executable gate (`docs_updater.py --check`, mail ids in Evidence) | `core/45-testing-strategy.md` MATCHED | FIXED | round 1 rules-O12/O14 + round 2 O28 + round 3 O46 + rounds 4–8 O57/O61: every Phase C behaviour has a G/W/T row naming its grader, the C.2.3 list carries a RED-first grader per clause including `--restore`'s three outcomes and `--verify-ledger`; the four mails have ids in Evidence at Gate C.4 |
| CC21 | (2026-10-11) Status/lifecycle grammar — `Status: DRAFT` on a plan whose Phases 0/A are EXECUTED (the 2026-10-05 precedent), `Appetite:` per sub-phase as the EXECUTION contract (`/fabrik-execute-plan`'s UPGRADE finding; `check_plan_quality.py` does not grade a plan dated before `LANE_ROLLOUT_DATE` 2026-10-03 — `plan_appetite.is_graded`), the Coverage Checklist + rubric block the flip reads | `check_convergence.py` (`_checklist_section`, `RUBRIC_RUN`) | FIXED | round 1 rules-O11/O23 + rest-ledgers-S7 + round 3 O43 + round 4 O45 + rounds 9–16 (the Pass Ledger rows themselves): `Status: DRAFT` on a plan with EXECUTED phases follows the 2026-10-05 precedent (D-569) and flips here; Appetite lines are the execution contract (check_plan_quality does not grade a plan dated before LANE_ROLLOUT_DATE); the Digest binds Gate C and names what core/25 does not bind; the spec md5 in the header matches the pin; check_plan_quality rc 0 after every fix pass |

## Execution notes

**2026-10-05 — Phase A code shipped and reviewed; Gate A BLOCKED on the B2 application key.**
- Code: 8677a962d (archiver, tests, units, installer, docs), review fixes 23e891dec and b5cb26110.
- `/fabrik-review` (routed up from review-scoped — the `flock` is a concurrency surface): confirmed
  12 → 2 → 0, receipt `docs/development/reviews/2026-10-05-plan-1-session-history-retention-phase-A-review.md`
  (c911db3a9). 46 tests; 14 Behavior-Contract mutants and 10 fix mutants each watched red in a
  throwaway worktree.
- Gate 0 — GREEN (run by hand from this worktree):

```
$ bash scripts/sysadmin/sample_transcript_growth.sh
sample_transcript_growth: 2026-10-05  main=13917832151 bytes / 5969 files  largest=1364840151 bytes
$ wc -l ~/.claude/state/transcript-growth.tsv
2 /home/ozgur/.claude/state/transcript-growth.tsv
```

- Gate A — BLOCKED: missing infra. `SESSION_ARCHIVE_B2_KEY_ID` / `SESSION_ARCHIVE_B2_APPLICATION_KEY`
  are not in `/opt/fabrik/.env` (presence check: the file holds 3 `SESSION_ARCHIVE_B2_*` lines — bucket,
  bucket id, endpoint — and no key). Resume: the operator adds the key; the run resumes at Gate A
  (first live run, `--remote-count`), then Phase B, Finish, Gate S. The plan lock stays `active`.

**2026-10-08/09 — Gate A GREEN; the archive covers the open named windows (resume, W-08eeaee1).**
- The operator created the key (keyName `wsl`, restricted to `wsl-ozgur`) and asked for it to be saved
  into `/opt/fabrik/.env` (backup `/opt/fabrik/backups/.env.backup.20261008-225609`).
- Run 1 (the merged Phase A code, window 1 day): 8,040 eligible, 7,981 rows; every object landed, then
  the manifest `copyto` hung 42 min on a HEAD to B2's download host. Diagnosis by execution: this
  machine's network cuts the TLS handshake to `f004.backblazeb2.com` by SNI (the name fails even at
  another host's IP, while `f000` passes at f004's IP), while the upload API host works. Stopped by
  hand; the run exited 1 with rows kept, as A.5 designs.
- The operator then asked whether the named windows (infra, fleet, intel, kaizen) are kept. They were
  not: each runs one session for days and never idles a day. Amended A.2/A.2b/A.4/A.5 (D-row of
  2026-10-09), with `/fabrik-review-scoped` confirmed 9 → 5 → 0 (3 seats + refuter per round,
  independent readers returned every round).
- Run 2 (amended code): 8,994 eligible, 947 rows, exit 0; manifest shipped with `--no-check-dest`.
- Run 3, immediately after: 8,998 eligible, **13 rows** (the sessions being written right now), exit 0.

```
$ .venv/bin/python scripts/sysadmin/archive_transcripts.py --remote-count
remote_objects 8928
remote_manifest_sha256 absent        # the blocked download host, not a missing manifest
$ find ~/.claude/archive -name '*.jsonl.zst' | wc -l
8928
$ rclone lsf --files-only --format sp sessionb2:wsl-ozgur/archive/   (via the archiver's _rclone)
2439117;manifest.jsonl               # local manifest.jsonl: 2439117 bytes
$ systemd-analyze --user verify scripts/sysadmin/systemd/session-archive.service scripts/sysadmin/systemd/session-archive.timer; echo rc=$?
rc=0
$ test -s ~/.claude/projects/README && echo present
present
$ .venv/bin/python -m pytest -q tests/test_archive_transcripts.py
61 passed
```

The four named windows' current sessions are in the manifest: fleet `1970a0ff` 785.3 MB, intel
`4e90716e` 1,148.7 MB, kaizen `5fa5812d` 62.3 MB, infra `dd3c06d1` 1,519.6 MB (run 2; run 3
re-archived each). **Phase B is blocked from this network:** `--fetch` needs the download host the
SNI filter cuts (`docs/workstation/session-history-retention.md` § Restore).

**2026-10-09 — Gate S GREEN, ahead of Phase B; Phase B BLOCKED (missing infra: a network path to
B2's download host).** Infra merged the branch (a224626af). Gate S ran before Gate B because the
timer only archives and uploads, which is non-destructive. "No phase may merge forward" guards Phase
C's deletions, and Phase C stays deferred. Every day without the timer was a day with no off-site
copy.

```
$ bash scripts/sysadmin/install_session_archive_timer.sh   (main checkout, archiver md5 0767f5bd = this branch)
Created symlink …/timers.target.wants/session-archive.timer → …/session-archive.timer.
$ systemctl --user list-timers session-archive.timer
Sat 2026-10-10 00:11:16 +03  22h -  -  session-archive.timer  session-archive.service
$ systemctl --user start session-archive.service; systemctl --user show session-archive.service -p Result -p ExecMainStatus
Result=success
ExecMainStatus=0
$ .venv/bin/python scripts/sysadmin/archive_transcripts.py --fetch /-opt-fabrik/fa631570-1f8f-4df9-a15e-467e872b897f.jsonl.zst <scratch>/b1-r.zst; echo rc=$?
archive_transcripts: /-opt-fabrik/fa631570-….jsonl.zst was not downloaded: absent from the bucket, or B2's download host is unreachable from this network
rc=1
$ curl -sS -o /dev/null -w "%{http_code}\n" -I https://f004.backblazeb2.com/
000          # SSL_ERROR_SYSCALL at SSL_connect; with --resolve, the f004 NAME fails at f000's IP and the f000 name passes at f004's IP
```

Resume: from a network that reaches `https://f004.backblazeb2.com` (the check above prints a 4xx
instead of `000`), run Phase B (B.1-B.5), then the Finish `/fabrik-review`, then flip EXECUTED.
The plan lock stays `active`.

## Evidence

**Revision 2026-10-05 — the measurements the B2-direct route is built on** (this machine):

```
$ find ~/.claude/projects/ -name '*.jsonl' ! -path '*/subagents/*' -printf '%s\n' | awk …
MAIN      5942 files  13.84 GB            (any depth, subagents excluded — the spec's predicate)
SUBAGENT  21305 files  8.04 GB
$ M="find ~/.claude/projects/ -mindepth 2 -maxdepth 2 -name '*.jsonl' -type f"   # the archiver's glob
$ $M -printf '%i %s\n' | awk …                   -> MAIN all links  5953 files  13.86 GB
$ $M -printf '%i %s\n' | sort -u | awk …         -> MAIN unique     5895 files  9.82 GB
$ $M -links +1 | wc -l ; $M -links +1 -printf '%i\n' | sort -u | wc -l
117
59
$ $M -mmin +1440 -printf '%i %s\n' | sort -u | awk …   (idle > 24 h: the first ARCHIVE_AFTER_DAYS=1 run)
MAIN unique idle>24h 5569 files 3.53 GB
$ zstd --version
*** Zstandard CLI (64-bit) v1.5.5, by Yann Collet ***
$ df -h --output=size,used,avail,pcent /
1007G  715G  242G  75%
$ zstd -12 -q -f zt.jsonl -o zt.jsonl.zst; stat -c '%y %n' zt.jsonl zt.jsonl.zst
2026-01-02 03:04:05.000000000 +0300 zt.jsonl
2026-01-02 03:04:05.000000000 +0300 zt.jsonl.zst
$ python3 b2caps.py /opt/fabrik/.env        # b2_authorize_account; secret never printed
restricted to bucket: vps1-ocoron-backups
can create a bucket: False
can create a restricted key: False
$ (same for /opt/youtube/.env) -> allowed.bucketName: youtube-pipeline; b2_create_bucket -> HTTP 401 unauthorized
$ rclone version | head -1
rclone v1.72.0
$ systemctl --user is-system-running
running
$ loginctl show-user ozgur -p Linger
Linger=yes
```

**First revision (2026-09-06, historical — the vps1 route this revision withdraws):**

**Phase 0 / A — the measurements this plan is built on** (`scripts/sync-vps-sysadmin.sh:28` is the
transport analogue; `~/.ssh/config` supplies the alias):

```
$ find ~/.claude/projects -name '*.jsonl' ! -path '*/subagents/*' -printf '%s\n' | awk '{t+=$1;n++} END{...}'
  MAIN      5915 files    5.53 GB
  SUBAGENT  8169 files    2.74 GB
  pool ledgers: 445M total
  index: 10177 sessions, 0 with agent- id, 2938 pre-August
```

**Phase A.3 — the live Backrest config that decided the path** (read-only, `ssh vps`):

```
paths   : ['/opt']
excludes: ['/opt/containerd/**', '/opt/fabrik/.git/**', '/opt/*restic-cache*',
           '/opt/manually_installed.txt', '/opt/backups/**']
retention: {"policyTimeBucketed": {"daily": 30}}
schedule: {"cron": "0 3 * * *", "clock": "CLOCK_LOCAL"}
REPO b2-vps1 -> s3://…
/dev/vda1       108G   49G   59G  46% /
```

**Phase C.3 — the subagent reader the first draft missed** (`claude-stop-decider.py`):

```
23:  background SUBAGENT        | its sidechain `<sid>/subagents/agent-*.jsonl` last    | busy-subagent
421:            f = transcript.parent / session_id / "subagents" / w[4:]
515: def pending_subagents(transcript: Path, session_id: str, now: float | None = None) -> list[str]:
```

**Whole-repo gate, declared rather than hidden:**

(Revision 1's out-of-surface gate declaration stood here; it named two sibling reds of
2026-09-06 and is not a declaration for this revision.)

```
status: failure | skipped: ['pytest']
 FAIL: Convergence Evidence (plans + reviews) — docs/development/reviews/2026-09-03-plan-1-multi-agent-per-repo-T11-review.md
 FAIL: Command Corpus (references resolve — BLOCKING) — 9 broken reference(s) under docs/orchestrator/
```

## CONSTRAINTS DIGEST

Computed via `review_rubric.py --changed` over this plan's full File Scope (§ Rubric run): FLOOR
`core/35-security-auth.md`, `core/25-data-postgres.md`, `core/30-ops.md` + the 12-Factor axes;
MATCHED `core/10-python.md`, `core/40-documentation.md`, `core/45-testing-strategy.md` — six packs.
`core/25-data-postgres.md` binds nothing here: through Phase B no database was touched, and Phase
C's rule 8 — ONE read-only `SELECT` on session-recall's `index_state` through `SESSION_RECALL_RO_DSN`
— is bound by the rows below, not by that pack (its rules address application code: settings
classes, the asyncpg scheme): the DSN comes from the environment and is never a literal
(`core/10-python.md:129`), and no secret enters the script (`core/35-security-auth.md:267`). Quotes
re-located verbatim 2026-10-05 and
re-checked 2026-10-11 (8 of 8 at their cited lines, round 1 of the Phase C review).

| Verbatim quote | Source | Rule |
|---|---|---|
| A green test never seen red is unverified — a suite can pass with its guard deleted. | `.windsurf/rules/core/45-testing-strategy.md:22` | Watched-fail-first |
| one high-value integration/E2E test per behavior, risk-ordered | `.windsurf/rules/core/45-testing-strategy.md:20` | Behavior Contract |
| ZERO secrets/constants in code | `.windsurf/rules/core/35-security-auth.md:267` | No secrets in code (A.2a) |
| any binary the app shells out to | `.windsurf/rules/core/30-ops.md:467` | Shelled-out binaries are probed (A.1c) |
| names a plan that protects nothing | `.windsurf/rules/core/30-ops.md:225` | A backup that protects nothing reads green (Gate A, Gate B) |
| A compose/worker/job change that isn't reflected there ships a silent misdeploy | `.windsurf/rules/core/30-ops.md:193` | Ops docs are the deploy channel |
| host = os.getenv('DB_HOST', 'postgres-main')  # banned — use DATABASE_URL directly | `.windsurf/rules/core/10-python.md:129` | No hardcoded hosts |
| rows immutable, supersede-by-new-row | `.windsurf/rules/core/40-documentation.md:24` | Decision ledger (D-565) |

`core/30-ops.md:225` is the sharpest row and it decides three steps: Gate A counts the `.zst`
objects that actually landed in the bucket (≥ 1, equal to the local count), Gate B restores
bytes from the bucket, and **Gate C's canary (3)** deletes ten files only after two of them come
back byte-identical through `--restore` — a transport that reads green while shipping nothing fails
all three, and a pruner whose rule 5 trusted `zstd -t` alone would have passed a frame holding the
wrong bytes (C.2.1 r5). `core/45-testing-strategy.md:22` binds the deleter's every clause: each
refusal in C.2.3 is a grader SEEN RED. `core/30-ops.md:467` decides A.1c.

## fabrik-lib verdict

**BUILD.** `/opt/fabrik-lib/README.md` has no archive/backup/compression/retention module — the only
`B2` hit is `rn-media-kit/`, an RN/Expo client upload kit, unrelated. New-module bar: the archiver is
project-specific (Claude transcript layout, session-recall's mirror semantics, this box's
bucket and timer), failing (a) *generic* and (b) *reused by ≥2 project types*. Hub-local, no candidate flag.

## Docs owed (Doc Sync Matrix)

(2026-10-11, Phase C) `docs/workstation/session-history-retention.md` (the prune contract, the restore
path after a prune, `--agent`, the ROTATE line) · `docs/workstation/hooks-index.md` (the user-level hook
row) · `CLAUDE.md` § Pointers (one paragraph) · `INDEX.md` rows for the new scripts and tests ·
`CHANGELOG.md` per phase · `docs/DECISIONS.md` D-736 (minted 2026-10-11) · the spec's § Phase C
passage gains a D-736 marker.
`docs/workstation/session-history-retention.md` (NEW — box-local subsystem: what runs, where the
archive lives, how to restore; grep first, extend never duplicate) · `INDEX.md` rows for every new
file · `CHANGELOG.md` per phase · `.env.example` + `docs/CONFIGURATION.md` for the
`SESSION_ARCHIVE_*` variables · the spec's § Where the cold archive lives gains a pointer to D-565 ·
`docs/DECISIONS.md` D-565.

## Residual risks, named

1. **The cap is unknown until Phase 0 reports.** A and B are safe without it; C is not, and must not
   start with an invented number.
2. **Subagent deletion is irreversible with no index fallback**, and has one live reader whose safety
   rests on it only inspecting in-flight sessions. Operator-accepted (Phase C, deferred).
3. **The off-site copy is only as current as this machine is on.** A missed run catches up when the
   user manager next starts (`Persistent=true`, linger asserted by the installer); a dead disk loses
   at most what was written since the last run (a day, at the default window of 0).
4. **`--full` remains live upstream** until session-recall acts; it matters only once something
   prunes, which this revision does not.
5. **B2 storage cost is small but not zero.** About 1.6 GB compressed today (9.82 GB of unique MAIN
   at the measured 6.08x); B2 bills $6.95/TB-month after the first 10 GB free
   (https://www.backblaze.com/cloud-storage/pricing, WebSearch, 2026-10-05). "Keep all versions"
   stores every re-upload of a changed transcript; the daily timer bounds that to one version per
   changed transcript per day (the open named windows: roughly 100-150 MB compressed each per day).
6. **Object Lock is disabled and the key may carry delete rights.** The transport refuses every
   deleting verb and flag (A.2, graded by A-B7) and the bucket keeps all versions, so a stray
   overwrite is recoverable; a key leaked WITH `deleteFiles` could still remove versions. Enabling
   Object Lock on `wsl-ozgur` is an operator console setting — recommended, not required to close.
8. **(2026-10-11) A pruned session leaves the VS Code picker.** By design and by the operator's
   ruling: after 3 days a closed session is reached through session-recall or put back with
   `--restore <session_id>` (C.2.5), not the sidebar. The newest session of every project AND of
   every tagged agent is kept, so a long-idle project and each hub agent still have their resume
   point; an OPEN window is never touched however idle. A window closed by a reload and idle 4+
   days is the case the operator must know: it is restorable, not visible. If the operator later
   wants a longer window, `PRUNE_AFTER_DAYS` is the one knob.
9. **(2026-10-11) session-recall's ingest and `--full` are manual commands in another repo.** Nothing
   schedules either (verified: no cron, timer or script; their tools self-heal with a bounded
   incremental reindex on each query, `README.md:34`); rule 8 therefore refuses every deletion until
   the nightly ingest and the read-only DSN (C.4 (c)) exist — fail-closed, Gate C (1b) names it a
   `BLOCKED: missing infra` for Gate C alone, and the dry-run table shows it as the `not-indexed`
   count. A hand-run `--full` after a prune would drop the pruned sessions' index
   rows until (a) lands — `pruned.jsonl` is the list to re-ingest from the archive.
10. **(2026-10-11) The ROTATE line is advice, not enforcement.** A window that never rotates keeps
   growing; its file still ships nightly and is never pruned while open. Backstops: the line
   re-prints at every new 100 MB step (never silent, never wallpaper), and the nightly summary row's
   `over_threshold` lists every MAIN transcript over `ROTATE_ADVISE_MB` (`--status` shows it; a BC
   row grades it). The extension's crash threshold is
   Anthropic's defect (#89075, #97229); the advisory keeps us an order of magnitude under it, and the
   sidebar load is bounded by the prune regardless.
7. **The largest transcripts are over a gigabyte** (1,358.0 MB and two linked copies of 1,030.5 MB
   on 2026-10-05); rclone uploads them as B2 large files in parts. `ARCHIVE_MAX_FILE_MB` stays unset
   so nothing is silently skipped; a file over a ceiling, when one is set, is reported.

## Self-audit

- **Revision 2026-10-11 (Phase C reopened, D-736).** (a) Coverage — each Intake item maps to a
  phase step (I1→A+C.2, I2→C.2.1 r1, I3→C.1, I4→C.3, I5→C.1.4 then Gate C, I6→C.4, I7→C.2.1 r1-3 +
  C.2.2 + Gate C, I8→the pruner walks every slug and the hook is user-level, I9/I10→the preamble and
  probe 5, I13→C.4(a)); the two OUT-OF-SCOPE items name their destination. (b) Cross-phase
  signatures — C.1.1 writes `agent` into the manifest row; C.1.2 and session-recall's requested
  `agent` column read the same key; C.2.1 r4 reads the row's `sha256`/`project_slug`/`session_id`
  exactly as `_latest_rows` keys them (`archive_transcripts.py:209-222`); C.2.1 r7 and the archiver's
  `_group_by_inode` agree on `(st_dev, st_ino)` as the identity of a file; C.3 calls the stop-decider's
  `pending_subagents` by its existing signature `(transcript, session_id, now)`; the unit's second
  `ExecStart=-` depends on the first succeeding (oneshot ordering, `man systemd.service` quoted in
  C.2) and never fails the unit itself, which C.2's unit-file test asserts; C.1.1's registry join
  and C.2.1 r2 read the same registry fields (`sessionId`, `pid`, `procStart`) and the same identity
  fields (`session_id`, `pid`, `pid_start`); `--restore` reads the `pruned.jsonl` row exactly as the
  deletion wrote it (`paths`, `sha256`).
  (c) The grounding passes: four probes executed this session (idle window, population, remote
  size+SHA1, transcript composition), the sessions registry and identity file read, the archiver's
  selection/skip/ship code read at `:188-345`, the external crash class and practice elsewhere
  fetched from primary sources. (d) Round 1 of `/fabrik-plan-review` (30 candidates, 27 confirmed,
  3 refuted) corrected the one claim that had been marked VERIFY-AT-BUILD: the binding is keyed by
  session id, not pid (`whoami_agent.py:259-274`), a re-bind after `/clear` is refused without
  `--force` (`:356-373`), and C.1.1 now derives the tag through the registry join — no VERIFY-AT-BUILD
  remains. The same round made rule 2 match `procStart`, rule 5 compare decompressed bytes, rule 7
  scan inodes at prune time, added rule 8 (session-recall holds it) and the last look, capped every
  `--apply`, replaced the wrapper with `--nightly`, added `--restore`, the `-` prefix, the lock, the
  stamp, the inventory of other deleters, Gate C (0) and the canary, and re-sized the review floor.
  (e) Round 2 (the delta pass, 14 candidates, all confirmed) tightened those fixes: integer compare
  on `procStart`; the cap TAKES the oldest N instead of refusing (so the backlog drains and the
  canary is runnable); rule 8 keys on `index_state`'s inode + size (not `last_at`) through a named
  read-only DSN the Digest now binds; `--verify-ledger` and the summary row / `--status` specified
  with rows; the restored canary files are left in place; the `--force` re-bind is informed by the
  holder pid the hook prints; the review floor is full everywhere the operator named the surface.
  (f) Round 3 (the delta pass, 17 new confirmed) corrected what round 2's text asserted without
  reading: rule 8 looks up `index_state` by INODE (session-recall keeps one row per inode under the
  worktree name), through the existing `recall_ro` role and the declared `psycopg2`; the pruner's own
  env reader carries the `PRUNE_*`/`ROTATE_*` knobs into a unit without `EnvironmentFile=`; the
  `--force` cross-check is the plain `--as` refusal's pid, not `--who`; `--expect` under `--max` is
  named vacuous; Gate C (2) can fail; the summary row's writers are named; C.4 gets its own full
  review (no wait on the Finish); two unlinks are not atomic; the spec md5 and the Pass 2 counters
  corrected. (g) Round 4 (re-verification of the fixed set, 9 confirmed) closed the four that were
  still true — `--expect` named an echo, Gate C (2) requires `not-indexed` = 0, r8 no longer
  attributes a rule to `core/25`, `--restore` re-links to a surviving identical twin — and the three
  the fixes introduced (the error row scoped to dry-run/apply, `--status` showing the last apply
  row, the Pass 3 counter), plus the `recall_ro` grant's real line (`:100`). (h) Round 5 (5 confirmed,
  all inside the round-4 hunks): `--restore` touches the inode's `mtime` after a hard link and
  refuses a diverged survivor; the exit-code line and the C.2.3 grader carry the error row's scope;
  Gate C (2) names the set it measures (files passing rules 1–3); the Pass 4 row counts what the
  ledger file holds. (i) Round 6 (4 confirmed, all follow-ons inside the round-5 hunks): the
  exit-3 list carries `--restore`'s two refusals; C.2.3 grades the two new `--restore` outcomes;
  C.2.5 states the nightly re-hash a touched inode costs under A.1a; the Pass 5 row says where its
  statuses live. (j) Round 7 (2 confirmed): `--restore`'s no-object refusal names both causes
  `--fetch` cannot tell apart (A.2) with its grader; the Pass 4 row names the journal, not notes, as
  where the Sonnet seats' statuses live. (k) Round 8 (2 confirmed): the `--fetch` refusal names
  rclone's own failure as the third cause A.2 maps to the same exit, and its grader asserts the
  message. (l) Round 9 (2 confirmed): the refusal's exit and message claims now match A.2 exactly —
  non-zero (1 when no file arrived, non-zero when rclone fails) and `--fetch`'s stderr, which is the
  archiver's own line for the two causes where rclone exited 0 and wrote nothing. (m) Round 10 (1
  confirmed): the C.2 text no longer asserts rclone's code or message are passed through — A.2
  promises only 'non-zero when rclone does' and `--fetch`'s own output. (n) Round 11 (1 confirmed):
  the Pass 10 row's grep count is now the refuter's recorded 5. (o) Round 12 (2 confirmed, both in
  the ledger rows): the unsourced 13 is dropped, and the Pass 11 row names which cells come from the
  ledger file, which from the fix diff, and which are the orchestrator's disposition. (p) Round 13 (1
  confirmed): the Pass 12 row's O65 cell says what pass-10.json and pass-12.json hold instead of a
  FIXED no verdict there states. (q) Round 14 (2 confirmed): the Pass 13 row's `ledger_status` cell
  reads the file's top-level array (3 rows), and its method cell names
  the finder for the pin grep and the refuter for the pass-12.json probe. (r) Round 15 (1 confirmed):
  the Pass 14 row and (q) no longer name a seat-level `ledger_status` array — the seat objects in
  the ledger files carry no such key.
- **Revision 2026-10-05:** every step that named vps1, Backrest, `ssh vps` or rsync was replaced or
  marked historical; Phase C's deferral is a recorded panel ruling with a three-part tripwire, not
  a silent drop. Round 1 of its review (25 confirmed) found the gates could not run in the order
  written and could not reach a remote that lived only in the archiver's child env; the gates now
  run through the archiver's own `--remote-count`/`--fetch`, Gate S carries the post-merge timer,
  the deletion ban became a run-time allow-list, and the sizes were re-measured (hard links counted
  twice, `-mtime +1` meant 48 h).

- **Every phase gate now names a runnable command.** The first draft's Self-audit claimed this while
  Gates 0 and A were prose — an internal contradiction the finders caught, and the same shape as
  captioning a numstat instead of reading it.
- Phase 0's relationship to A and B is corrected: concurrent with **A**, not with B, because B
  consumes A's output.
- The manifest key carries `project_slug`; keying on `(session_id, sha256)` could have matched a
  transcript against another project's archive.
- The grader list grew 4 → 7: a manifest row that vouches for missing or corrupted bytes is now
  tested, not assumed.
- `--delete` / `--remove-source-files` are banned **and graded**, because a safety model that depends
  on future humans not adding a flag is not a safety model.
- The Evidence section carries fenced, verbatim output; a `GATE-SCOPE` line, when the shared
  gate is red for an out-of-surface cause, uses the form the regex at
  `scripts/enforcement/check_convergence.py:386` accepts.
