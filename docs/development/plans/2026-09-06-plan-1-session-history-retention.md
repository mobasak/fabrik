# Plan — session-history retention: archive, prove, then prune

Status: DRAFT
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
    session: the largest transcript on disk is **696.5 MB** and 50% of all bytes live in the top 14
    files, so a 10 GB session would sit comfortably under a 90 GB aggregate while filling the disk
    on its own. A file over the per-file ceiling is **reported, never silently archived or pruned**.

**Gate 0 (runnable):** at this plan's close, `wc -l < ~/.claude/state/transcript-growth.tsv` ≥ 2
(header + the first sampled row, written by the timer's first run). The 14-row bound derivation
belongs to Phase C's reopening, not to this revision's close. **Deletes nothing.**
⚠️ **Phase 0 runs CONCURRENTLY WITH PHASE A**, not with Phase B — B needs an archive that only A
produces. (The first draft said "A and B proceed in parallel", which was false.)

## Phase A — TRANSPORT + ARCHIVE (non-destructive)

- **A.1 — the archiver.** `zstd -12` each MAIN transcript older than N days to
  `<ARCHIVE_ROOT>/<project-slug>/<session-id>.jsonl.zst`, appending
  **`(project_slug, session_id, sha256, bytes, archived_at)`** to a manifest.
  ⚠️ **`project_slug` is part of the KEY, not decoration.** A session id is unique within a project
  directory; the plan must not assume it is unique across all 266 of them. Keying on
  `(session_id, sha256)` alone — the first draft's key — cannot disambiguate a collision and could
  match a transcript against another project's archive.
  Compression is measured: **6.08x on a 70.7 MB transcript, 1.5 s compress, 0.08 s restore,
  byte-identical, sha256 match**.
- **A.1a — skip what is already archived (added 2026-10-05).** The first revision re-ran
  `zstd -12` over EVERY eligible transcript on every run. The output is deterministic and zstd
  keeps the source mtime (verified: a `2026-01-02 03:04:05` source yields a `.zst` with the same
  mtime), so rclone would not re-upload — but re-compressing every eligible MAIN transcript
  (13.84 GB today) at `-12` on every run is wasted CPU.
  A transcript whose `(project_slug, session_id, sha256)` is already in the manifest AND whose
  `.zst` exists is hashed, not recompressed.
- **A.2 — the transport: `rclone copy` straight to B2, with its flags argued.**
  `rclone copy <ARCHIVE_ROOT>/ sessionb2:<bucket>/archive/ --fast-list --transfers 4`
  then, after the manifest rows are appended, `rclone copyto <manifest> sessionb2:<bucket>/archive/manifest.jsonl`.
  - **The remote is defined in the ENVIRONMENT of the rclone child, never in argv and never in
    `rclone.conf`:** `RCLONE_CONFIG_SESSIONB2_TYPE=b2`, `_ACCOUNT`, `_KEY`, built from
    `SESSION_ARCHIVE_B2_KEY_ID` / `SESSION_ARCHIVE_B2_APPLICATION_KEY`. argv is readable by every
    process on the box (`ps`); a second credential store is a second thing to rotate.
  - **Credentials come from the process environment, else from the `SESSION_ARCHIVE_*` lines of
    `SESSION_ARCHIVE_ENV_FILE` (default `/opt/fabrik/.env`)** — only that prefix is read, so the
    archiver never loads the rest of the hub's secrets into its environment. A missing key is a
    loud non-zero exit naming the two variables, never a silent skip.
  - **`--fast-list`** — one listing call per directory tree instead of one per directory; B2 bills
    class-C transactions per call.
  - **no compression flag** — the payload is already zstd.
  - **The manifest ships SECOND and separately.** The first revision appended rows after the
    transport and never shipped the manifest that run, so the remote copy always lagged one run —
    a restore from B2 alone would have had no record of the newest archives.
  ⚠️ **`sync`, `move`, `delete`, `purge`, `--delete-*` and `--b2-hard-delete` are BANNED and the
  ban is GRADED, not trusted** (an AST test over every rclone argv in the script). `sync` makes the
  bucket mirror the local tree — the exact inversion D-144 banned `--delete` for. The bucket keeps
  all versions (the operator's console setting), so an overwritten `.zst` leaves its prior
  version recoverable; a hard delete would not.
- **A.3 — the bucket, recorded rather than configured.** Bucket `wsl-ozgur` (id
  `d46ef77ceab3068aa018061b`, Private, SSE enabled, lifecycle **Keep all versions**, Object Lock
  **disabled**, endpoint `s3.us-west-004.backblazeb2.com`), created by the operator 2026-10-04.
  Its settings live in `/opt/fabrik/.env` as `SESSION_ARCHIVE_B2_BUCKET` /
  `SESSION_ARCHIVE_B2_BUCKET_ID` / `SESSION_ARCHIVE_B2_ENDPOINT` (not secrets). The application
  key is the operator's to create — restricted to `wsl-ozgur`, read + write; no existing key can
  reach this bucket (the youtube key is restricted to `youtube-pipeline`, fabrik's to
  `vps1-ocoron-backups`, both verified by `b2_authorize_account` 2026-10-05). The Backrest plan of
  the first revision (old A.3) is withdrawn: nothing lands on vps1.
- **A.4 — env, not literals.** `ARCHIVE_ROOT`, `ARCHIVE_AFTER_DAYS` (default **1** — a session
  idle less than a day is still being written, and every upload of a growing file is one more
  kept version), `ARCHIVE_MAX_FILE_MB`, `SESSION_ARCHIVE_B2_*`, `SESSION_ARCHIVE_ENV_FILE`. The
  vps1 default `ARCHIVE_REMOTE` is removed.
- **A.5 — failure is loud and non-destructive.** rclone non-zero (no network, bad key, quota)
  ⇒ the run exits non-zero and appends no manifest rows; the manifest is only appended AFTER the
  `.zst` files landed. Nothing in Phase A can delete a local file or a remote object.
- **A.6 — the marker.** A `README` in `~/.claude/projects/` stating the tree is data, not cache —
  aimed at the failure that actually happened: a human freeing disk space.
- **A.7 — the schedule: a systemd USER timer, catch-up friendly.** `systemctl --user` is running
  on this box. `session-archive.timer` fires daily with `Persistent=true` (a run missed while the
  machine was off fires at next boot) and starts `session-archive.service`, which runs Phase 0's
  sampler then the archiver. Unit files are tracked in the repo
  (`scripts/sysadmin/systemd/session-archive.{service,timer}`) and installed by
  `scripts/sysadmin/install_session_archive_timer.sh` (copy to `~/.config/systemd/user/`,
  `daemon-reload`, `enable --now`). Not cron: crontab writes are refused on this box's agent
  sessions, and cron has no catch-up.

**Gate A (runnable):**
`rclone lsf -R --files-only sessionb2:wsl-ozgur/archive/ | grep -c '\.jsonl\.zst$'` equals
`find ~/.claude/archive -name '*.jsonl.zst' | wc -l` · the remote `manifest.jsonl` equals the local
one (`rclone cat … | sha256sum` vs `sha256sum`) · `systemctl --user list-timers session-archive.timer`
shows a next run · the AST ban test green. **Zero deletions.** `/fabrik-review-scoped` at the
boundary.

## Phase B — PROVE THE RESTORE (still non-destructive)

The local round trip is measured. **The leg back from B2 is not, and it is the one that matters.**

- **B.1** Download an archived `.zst` **from the bucket** (`rclone copyto sessionb2:wsl-ozgur/archive/<slug>/<sid>.jsonl.zst <scratch>/`),
  never the local `~/.claude/archive` copy — that would prove the wrong hop.
- **B.2** `zstd -d`, then `cmp` against the live original and `sha256sum` against the manifest
  row's `sha256`.
- **B.3** Embed the verbatim command output in `## Evidence`.
- **B.4** Prove the archive stands alone: restore a **prior version** of an object whose live
  original has since changed (`rclone … --b2-versions`, or the `--b2-version-at` of the first
  upload), and match it against the manifest row written for THAT version's sha — not against
  the file on disk, which no longer agrees with it.
- **B.5** Restore the remote `manifest.jsonl` alone and confirm it lists the object B.1 restored —
  a restore with only the bucket must be able to find what is in it.

**Gate B (runnable):** `cmp <restored> <original> && sha256sum -c`, output embedded, plus B.4's
version-match line.
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
plan is declared in `## Evidence` in the exact `GATE-SCOPE:` form `check_convergence.py:224`
accepts, never hidden. (The first revision's two sibling reds are not re-asserted here; the gate is
re-run at each phase boundary and its live output decides.)

## Evidence`.
- **B.4** Prove the archive stands alone: restore a **prior version** of an object whose live
  original has since changed (`rclone … --b2-versions`, or the `--b2-version-at` of the first
  upload), and match it against the manifest row written for THAT version's sha — not against
  the file on disk, which no longer agrees with it.
- **B.5** Restore the remote `manifest.jsonl` alone and confirm it lists the object B.1 restored —
  a restore with only the bucket must be able to find what is in it.

**Gate B (runnable):** `cmp <restored> <original> && sha256sum -c`, output embedded, plus B.4's
version-match line.
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

## ⚠️ Gate mechanics under a red shared gate

`final_gate.py --json` is currently RED for two sibling-owned causes — `Command Corpus` (infra's
in-flight orchestrator retirement) and `Convergence Evidence` on
`docs/development/reviews/2026-09-03-plan-1-multi-agent-per-repo-T11-review.md` (`693751ad`,
`Agent-Name: infra`). A green whole-repo gate is not currently obtainable, so each phase proves
itself with `ruff check` + `ruff format --check` + `pytest` on its OWN files, plus the failing gate
embedded and declared in the exact form `check_convergence.py:224` accepts — not a paraphrase.

## Evidence

**Revision 2026-10-05 — the measurements the B2-direct route is built on** (this machine):

```
$ find ~/.claude/projects/ -name '*.jsonl' ! -path '*/subagents/*' -printf '%s\n' | awk …
MAIN      5942 files  13.84 GB
SUBAGENT  21305 files  8.04 GB
MAIN idle >1d  5395 files  2.68 GB        (-mtime +1: what the first ARCHIVE_AFTER_DAYS=1 run takes)
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

GATE-SCOPE: out-of-surface — Command Corpus (references resolve) and Convergence Evidence; findings naming this surface: 0 of 10; measured by: `.venv/bin/python scripts/final_gate.py --check --json`

```
status: failure | skipped: ['pytest']
 FAIL: Convergence Evidence (plans + reviews) — docs/development/reviews/2026-09-03-plan-1-multi-agent-per-repo-T11-review.md
 FAIL: Command Corpus (references resolve — BLOCKING) — 9 broken reference(s) under docs/orchestrator/
```

## CONSTRAINTS DIGEST

Computed via `review_rubric.py --changed` over this plan's surfaces — 7 packs (FLOOR + MATCHED), not
the full 26 ACTIVE, per the command's own anti-skimming rule.

| Rule | Verbatim | Source |
|---|---|---|
| Watched-fail-first | *"A green test never seen red is unverified — a suite can pass with its guard deleted."* | `core/45-testing-strategy.md:21` |
| Behavior Contract | *"one high-value integration/E2E test per behavior, risk-ordered … lean-but-complete, NOT 100%-line-coverage dogma"* | `core/45-testing-strategy.md:19` |
| No hardcoded hosts | *"host = os.getenv('DB_HOST', 'postgres-main')  # banned — use DATABASE_URL directly"* | `core/10-python.md:128` |
| Ops docs are the deploy channel | *"A compose/worker/job change that isn't reflected there ships a silent misdeploy"* | `core/30-ops.md:192` |
| Paper backups | *"VOLUME gets a plan pointed at a directory that never exists — a paper backup that reads green and"* | `core/30-ops.md:222` |
| Decision ledger | *"a decision made or received gets its row in the SAME change; rows immutable, supersede-by-new-row"* | `core/40-documentation.md:23` |

`core/30-ops.md:222` is the sharpest row here and it still decides a step: Gate A counts the
`.zst` objects that actually landed in the bucket against the local archive, and Gate B restores
bytes from the bucket — a transport that reads green while shipping nothing fails both.

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
   rests on it only inspecting in-flight sessions. Operator-accepted.
3. **The off-site copy is only as current as this machine is on.** A missed run catches up at
   next boot (`Persistent=true`); a dead disk loses at most the sessions newer than the last run
   plus `ARCHIVE_AFTER_DAYS`.
6. **Object Lock is disabled and the key may carry delete rights.** The transport never deletes
   (graded), and the bucket keeps all versions, so a stray overwrite is recoverable; a key leaked
   WITH `deleteFiles` could still remove versions. Enabling Object Lock on `wsl-ozgur` is an
   operator console setting, recommended, not required for this plan to close.
4. **`--full` remains live upstream** until session-recall acts; C.5 reduces the local blast radius
   and does not fix their repo.
5. **B2 storage cost is small but not zero.** About 2.3 GB compressed today at the measured 6.08x
   (13.84 GB MAIN); B2 bills $6.95/TB-month after the first 10 GB free
   (https://www.backblaze.com/cloud-storage/pricing, WebSearch, 2026-10-05). "Keep all versions"
   stores every re-upload of a growing transcript; `ARCHIVE_AFTER_DAYS=1` bounds that churn.

## Self-audit

- **Revision 2026-10-05:** every step that named vps1, Backrest, `ssh vps` or rsync was replaced or
  marked historical; Gate A and Gate B now name commands against the bucket; Phase C's deferral is
  a recorded panel ruling with a three-part tripwire, not a silent drop; the manifest now ships to
  the bucket every run.

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
- `## Evidence` carries fenced, verbatim output and the `GATE-SCOPE` line in the exact form
  `check_convergence.py:224` accepts — this plan could not legally have flipped without it.
