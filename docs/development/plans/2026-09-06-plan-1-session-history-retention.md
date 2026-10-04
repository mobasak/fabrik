# Plan — session-history retention: archive, prove, then prune

Status: CONVERGED
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
Spec: `docs/superpowers/specs/2026-09-05-session-history-retention-design.md` (CONVERGED, md5
`9bf26fd7f744155ab541c23650fd8205`, D-142, commit `2814df66`; § Where the cold archive lives is
superseded by D-565 and carries a pointer to it)

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
  `rclone copy <ARCHIVE_ROOT>/ sessionb2:<bucket>/<prefix>/ --fast-list --transfers 4 --exclude /manifest.jsonl --exclude /.archive.lock`,
  then, after the rows are appended, `rclone copyto <ARCHIVE_ROOT>/manifest.jsonl sessionb2:<bucket>/<prefix>/manifest.jsonl`.
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
  does.
- **A.3 — the bucket, recorded rather than configured.** Bucket `wsl-ozgur` (id
  `d46ef77ceab3068aa018061b`, Private, SSE enabled, lifecycle **Keep all versions**, Object Lock
  **disabled**), created by the operator 2026-10-04. Its settings live in `/opt/fabrik/.env` as
  `SESSION_ARCHIVE_B2_BUCKET` / `SESSION_ARCHIVE_B2_BUCKET_ID` / `SESSION_ARCHIVE_B2_ENDPOINT` (not
  secrets). The application key is the operator's to create — restricted to `wsl-ozgur`, read +
  write; no existing key can reach this bucket (the youtube key is restricted to
  `youtube-pipeline`, fabrik's to `vps1-ocoron-backups`, both verified by `b2_authorize_account`
  2026-10-05). Revision 1's Backrest plan is withdrawn: nothing lands on vps1.
- **A.4 — env, not literals.** `ARCHIVE_ROOT`, `ARCHIVE_AFTER_DAYS` (default **1** — a session
  idle less than a day is still being written, and every upload of a growing file is one more kept
  version), `ARCHIVE_MAX_FILE_MB`, `SESSION_ARCHIVE_B2_BUCKET`, `SESSION_ARCHIVE_B2_PREFIX`,
  `SESSION_ARCHIVE_ENV_FILE`. The vps1 `ARCHIVE_REMOTE` is removed.
- **A.5 — failure is loud and non-destructive.** rclone non-zero on the `copy` (no network, bad
  key, quota) ⇒ exit 1 and no rows; on the manifest `copyto` ⇒ exit 1, rows kept (A.2). Nothing in
  Phase A can delete a local file or a remote object.
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
manifest sha256 equal to `sha256sum ~/.claude/archive/manifest.jsonl` · a SECOND run immediately
after appends 0 rows and uploads nothing new · `systemd-analyze --user verify
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
  download its object **from the bucket** — `archive_transcripts.py --fetch <slug>/<sid>.jsonl.zst
  <scratch>/r.zst` — never the local `~/.claude/archive` copy, which would prove the wrong hop.
- **B.2** `zstd -d <scratch>/r.zst -o <scratch>/r.jsonl`, then `cmp <scratch>/r.jsonl <live original>`
  and `sha256sum <scratch>/r.jsonl` against the row's `sha256`.
- **B.3** Embed the verbatim command output in the Evidence section.
- **B.4** Prove the archive stands alone — a prior version, restored without its live file. In an
  ISOLATED prefix (`SESSION_ARCHIVE_B2_PREFIX=restore-proof`, a scratch `CLAUDE_PROJECTS_DIR` and
  `ARCHIVE_ROOT`, `ARCHIVE_AFTER_DAYS=0`): archive a synthetic transcript (run 1), append a line to
  it, archive again (run 2), delete the scratch source, then `--fetch <slug>/<sid>.jsonl.zst out.zst
  --version-at <T>` — `T` captured with `date -u +%Y-%m-%dT%H:%M:%SZ` after run 1 returns, with at
  least 2 s before run 2 starts (`archived_at` is the compression time, not the upload, § A.1a) —
  and match its decompressed sha256 to the RUN-1 row —
  the bytes no file on disk holds any more. (One live run cannot do this: a bucket version exists
  only after the same object is written twice.) The proof objects stay in `restore-proof/`; they
  are tiny and the transport cannot delete them.
- **B.5** `--remote-count` alone (the manifest fetched from the bucket) lists the object B.1
  restored — a restore with only the bucket can find what is in it.

**Gate B (runnable):** B.2's `cmp` exits 0 and its sha256 equals the row's; B.4's decompressed
sha256 equals the run-1 row's and differs from the run-2 row's; outputs embedded.
⚠️ A failed or skipped Gate B is a `BLOCKED:` escalation.

## Phase C — THE PRUNER: DEFERRED (panel ruling 2026-10-05, D-565)

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

**Gate C:** not applicable to this revision; the plan closes at Gate B.

## Gate mechanics

Each phase proves itself with `ruff check` + `ruff format --check` + `pytest` on its OWN files, and
`final_gate.py --json` is read as the shared gate; any red it carries that names no file of this
plan is declared in the Evidence section in the exact `GATE-SCOPE:` form the regex at
`scripts/enforcement/check_convergence.py:386` accepts, never hidden. (The first revision's two sibling reds are not re-asserted here; the gate is
re-run at each phase boundary and its live output decides.)

## Context Ledger

- **Rule packs** (the rubric over the full File Scope, § Rubric run): `core/35-security-auth.md`,
  `core/25-data-postgres.md` (binds nothing — no database), `core/30-ops.md`, `core/10-python.md`,
  `core/40-documentation.md`, `core/45-testing-strategy.md`; quoted in § CONSTRAINTS DIGEST.
- **fabrik-lib modules:** none vendored (§ fabrik-lib verdict: BUILD, hub-local).
- **`agents-fabrik.md` invariants:** none touched — this is box-local workstation infrastructure,
  not a fleet service; no `specs/services/*.yaml`, so no `shape.*` flag applies.
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
| A-B11 | `ARCHIVE_AFTER_DAYS` defaults to 1 | with the variable unset, a transcript modified now is not eligible and one aged two days is |
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

1. **The B2 application key for `wsl-ozgur`** — BLOCKING for Gate A and Gate B, not for the code.
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
- `.env.example`
- `docs/CONFIGURATION.md`

Read, invoked, not modified: `scripts/sysadmin/sample_transcript_growth.sh` (the unit's
`ExecStartPre`; writes `~/.claude/state/transcript-growth.tsv`). Outside the repo, written at run
time (not repo paths, so not lockable): `~/.config/systemd/user/session-archive.{service,timer}` and
`~/.config/systemd/user/timers.target.wants/` (the installer), `~/.claude/archive/` (the archiver),
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
`core/25-data-postgres.md` binds nothing here (no database is touched) and is named so its absence
from the rows below is a reading, not an omission. Quotes re-located verbatim 2026-10-05.

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

`core/30-ops.md:225` is the sharpest row and it decides two steps: Gate A counts the `.zst`
objects that actually landed in the bucket (≥ 1, equal to the local count), and Gate B restores
bytes from the bucket — a transport that reads green while shipping nothing fails both.
`core/30-ops.md:467` decides A.1c.

## fabrik-lib verdict

**BUILD.** `/opt/fabrik-lib/README.md` has no archive/backup/compression/retention module — the only
`B2` hit is `rn-media-kit/`, an RN/Expo client upload kit, unrelated. New-module bar: the archiver is
project-specific (Claude transcript layout, session-recall's mirror semantics, this box's
bucket and timer), failing (a) *generic* and (b) *reused by ≥2 project types*. Hub-local, no candidate flag.

## Docs owed (Doc Sync Matrix)

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
   at most the sessions newer than the last run plus `ARCHIVE_AFTER_DAYS`.
4. **`--full` remains live upstream** until session-recall acts; it matters only once something
   prunes, which this revision does not.
5. **B2 storage cost is small but not zero.** About 1.6 GB compressed today (9.82 GB of unique MAIN
   at the measured 6.08x); B2 bills $6.95/TB-month after the first 10 GB free
   (https://www.backblaze.com/cloud-storage/pricing, WebSearch, 2026-10-05). "Keep all versions"
   stores every re-upload of a changed transcript; `ARCHIVE_AFTER_DAYS=1` bounds that churn.
6. **Object Lock is disabled and the key may carry delete rights.** The transport refuses every
   deleting verb and flag (A.2, graded by A-B7) and the bucket keeps all versions, so a stray
   overwrite is recoverable; a key leaked WITH `deleteFiles` could still remove versions. Enabling
   Object Lock on `wsl-ozgur` is an operator console setting — recommended, not required to close.
7. **The largest transcripts are over a gigabyte** (1,358.0 MB and two linked copies of 1,030.5 MB
   on 2026-10-05); rclone uploads them as B2 large files in parts. `ARCHIVE_MAX_FILE_MB` stays unset
   so nothing is silently skipped; a file over a ceiling, when one is set, is reported.

## Self-audit

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
