# Plan — session-history retention: archive, prove, then prune

Status: CONVERGED
Date: 2026-09-06
Owner: fleet
Spec: `docs/superpowers/specs/2026-09-05-session-history-retention-design.md` (CONVERGED, md5
`9bf26fd7f744155ab541c23650fd8205`, D-142, commit `2814df66`)

## Why the phase order is a safety property, not a preference

This build deletes irreplaceable data at its last step. Four claims in this work's history were
refuted by reading code *after* they had been asserted confidently — a size comparison that called
15 `.bak` files "provably lossless" when 293 messages existed only in them; "text forever in
session-recall" when `_reclaim_orphans` deletes a session's turns as soon as its JSONL is gone;
"vps1 is a single host" when Backrest already ships to Backblaze B2; and, in this plan's own first
draft, "nothing else reads subagent transcripts" when `claude-stop-decider.py:421` reads exactly
that. The phase order exists so that a fifth mistake costs disk, not history.

**No phase may merge forward. Phase C does not begin until Phase B has produced a byte-identical
restore pulled back through Backrest and B2.**

## Phase 0 — MEASURE (no code deletes anything)

The spec fixes 90 days but leaves the size cap open, and honestly so: MAIN was **0.61 GB in August**
and **4.89 GB in the first five days of September**.

- **0.1** `scripts/sysadmin/sample_transcript_growth.sh` appends a daily row (date, MAIN bytes, file
  count, largest single file) using the same predicate as the spec's baseline:
  `find ~/.claude/projects -name '*.jsonl' ! -path '*/subagents/*'`.
- **0.2** Runs **14 days** by cron. No cap value enters code before then.
- **0.3** The cap is **TWO bounds, not one**, because one number cannot protect against two
  different failures:
  - **aggregate** — p95 of the observed daily rate × 90, bounding sustained growth;
  - **per-file** — a ceiling on any SINGLE transcript. The aggregate bound cannot see a runaway
    session: the largest transcript on disk is **696.5 MB** and 50% of all bytes live in the top 14
    files, so a 10 GB session would sit comfortably under a 90 GB aggregate while filling the disk
    on its own. A file over the per-file ceiling is **reported, never silently archived or pruned**.

**Gate 0 (runnable):** `wc -l < <growth-log>` ≥ 14, and the derived bounds are committed to the
spec's Open unknown 1 with the command that produced them. **Deletes nothing.**
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
- **A.2 — the transport, with its flags argued rather than copied.**
  `rsync -a --no-o --no-g --partial <ARCHIVE_ROOT>/ vps:/opt/session-archive/`
  behind `ssh vps 'mkdir -p /opt/session-archive'` — the shape of
  `scripts/sync-vps-sysadmin.sh:21,28`, with three deliberate departures:
  - **`--no-o --no-g`** — `-a` implies `-o -g`, and preserving owner/group across two machines with
    different uid maps is meaningless here and can fail as non-root.
  - **no `-z`** — the payload is already zstd. Compressing incompressible bytes is wasted CPU on
    every run.
  - **`--partial`** — a dropped link resumes rather than restarting a large `.zst`.
  ⚠️ **`--delete` and `--remove-source-files` are BANNED and the ban is GRADED, not trusted.**
  Either flag turns the transport into a mirror that deletes the archive when the local side prunes,
  silently inverting this plan's entire safety model. A test greps the shipped script for both and
  fails if either appears.
  ⚠️ **The alias is `vps`, not `vps1`** — `vps1` does not resolve (`~/.ssh/config`: `Host vps` →
  172.93.160.197).
- **A.3 — Backrest: its own plan, and the path is chosen to avoid a paper backup.**
  Read live from `/opt/backrest/config/config.json`: one repo `b2-vps1` (`s3://`, Backblaze B2);
  `opt-configs` backs up **`/opt`** on `0 3 * * *`, retention **`{"daily": 30}`**, excluding
  `/opt/containerd/**`, `/opt/fabrik/.git/**`, `/opt/*restic-cache*`, `/opt/manually_installed.txt`
  and **`/opt/backups/**`**.
  Consequences that decide the step:
  - **The archive must NOT live under `/opt/backups/`** — that prefix is excluded, so an archive
    there would be backed up by nothing while looking correct. This is precisely
    `core/30-ops.md:222`'s *"paper backup that reads green"*.
  - `/opt/session-archive/` IS swept by `opt-configs` by default, so the step **adds it to that
    plan's excludes** and gives the archive **its own plan** — otherwise every archive byte is
    stored twice in B2 and inherits a config backup's 30-daily retention rather than its own.
  - The archive's own plan gets a retention suited to an append-only store, not `daily: 30`.
- **A.4 — env, not literals.** `ARCHIVE_ROOT`, `ARCHIVE_REMOTE`, `ARCHIVE_AFTER_DAYS` and both cap
  bounds come from env with defaults (`core/10-python.md:128` bans hardcoded hosts; 12-Factor III).
- **A.5 — failure is loud and non-destructive.** rsync non-zero (disk full, bad path, SSH down) ⇒
  the run **exits non-zero and archives nothing further**; the manifest is only appended AFTER a
  verified remote landing. Nothing in Phase A can delete a local file, so a transport failure costs
  a re-run and never data. vps1 has **59 GB free** — ample now, not infinite, which is why Gate A
  asserts free space and the per-file bound exists.
- **A.6 — the marker.** A `README` in `~/.claude/projects/` stating the tree is data, not cache —
  aimed at the failure that actually happened: a human freeing disk space.

**Gate A (runnable):**
`ssh vps 'ls /opt/session-archive | wc -l'` equals the local manifest row count ·
`ssh vps 'sudo restic -r <repo> snapshots --path /opt/session-archive'` lists a snapshot **and**
`restic ls <snap> | head` shows files in it (a plan pointed at an empty path reads green forever) ·
`ssh vps 'df --output=avail /opt | tail -1'` above a floor · `grep -c -- '--delete\|--remove-source-files' <script>` = 0.
**Zero deletions.** `/fabrik-review-scoped` at the boundary.

## Phase B — PROVE THE RESTORE (still non-destructive)

The local round trip is measured. **The leg through Backrest and B2 is not, and it is the one that
matters.**

- **B.1** Restore an archived transcript **from the B2 repo** (`restic restore`), not from the vps1
  copy — that would prove the wrong hop.
- **B.2** `zstd -d`, then `cmp` and sha256 against the live original.
- **B.3** Embed the verbatim command output in `## Evidence`.
- **B.4** Restore one transcript whose live original has since been **deleted or rewritten**, proving
  the archive stands alone rather than only agreeing with a file that still exists.

**Gate B (runnable):** `cmp <restored> <original> && sha256sum -c`, output embedded.
⚠️ **Phase C is BLOCKED until this gate is green.** A failed or skipped Gate B is a `BLOCKED:`
escalation, never a reason to prune more cautiously.

## Phase C — THE PRUNER, behind its graders

- **C.1 — the invariant, in code.** Refuse to delete any transcript whose **CURRENT** sha256 is
  absent from the manifest under its **`(project_slug, session_id, sha256)`** key. Re-hash at delete
  time; never trust the sha recorded at archive time. Archive unreachable ⇒ **fail CLOSED**.
- **C.2 — the graders, each SEEN RED first** (`core/45-testing-strategy.md:21` — *"A green test never
  seen red is unverified"*):
  1. transcript absent from the manifest → **not deleted**;
  2. archived at sha A then **mutated in place** to sha B → **not deleted** (the `.bak` shape: 13 of
     15 diverged mid-file);
  3. archive destination **unreachable** → nothing deleted;
  4. manifest row present but the **`.zst` missing from the archive** → not deleted;
  5. manifest row present but the **`.zst` corrupted** (fails `zstd -t`) → not deleted;
  6. two projects holding the **same session id** → each matches its own archive, neither deletes on
     the other's row;
  7. a file inside the window → never offered.
  Graders 4–6 were added by the author-blind finders; the first draft's four would have let a
  manifest row vouch for bytes that no longer exist.
- **C.3 — the tiers, with the algorithm stated.** MAIN: delete candidates are files with
  `mtime` older than 90 days, **oldest first**, and additionally — if the aggregate bound is
  exceeded — oldest-archived-first until the store is back under it. "Whichever binds first" means
  the union of both candidate sets, never their intersection. SUBAGENT transcripts 7 days, **no
  archive, hard cliff**. `tool-results/` with its parent.
  ⚠️ **The subagent cliff has ONE live reader and the first draft missed it.**
  `~/.claude/bin/claude-stop-decider.py:421,515` reads `<sid>/subagents/agent-*.jsonl` to detect a
  session busy-waiting on a background subagent. It only ever inspects **in-flight** sessions, which
  a 7-day window never reaches — so the cliff is safe, but it is safe *for a reason*, not because
  nothing reads them. (`.claude/hooks/final_gate_stop.py:679` is a prose regex, not a consumer.)
- **C.4 — pool receipts, 14 days + rotation, WITH the kaizen coupling closed.**
  `libs/subagents/ledger.py:372` calls `read_all()` over the whole history;
  `scripts/sysadmin/kaizen_collect.py:57` reads that ledger and filters by a single day's stamp
  (`:226`), so the daily run survives rotation — but `scripts/sysadmin/kaizen_backfill.py:137`
  backfills a RANGE from file mtimes and would report **zero runs** for rotated days rather than
  "unavailable". **Rotation must write a per-day summary line, or `measure_subagents` must
  distinguish "rotated" from "no dispatches".**
- **C.5 — a local `--full` guard (hub-side only).** A wrapper refusing `ingest.reindex --full`
  unless the archive covers every orphan it would reclaim.
  ⚠️ **CROSS-REPO HARD STOP: `/opt/session-recall` is NOT patched by this plan.** Mailed upstream as
  `01M1SPW1KKNXKKKM8MSVT6RHQ9` (ack required); the fix is theirs.

**Gate C (runnable):** all seven graders red-then-green; `--dry-run` over the real tree printing
what WOULD be deleted, reviewed before any live run.

## ⚠️ Gate mechanics under a red shared gate

`final_gate.py --json` is currently RED for two sibling-owned causes — `Command Corpus` (infra's
in-flight orchestrator retirement) and `Convergence Evidence` on
`docs/development/reviews/2026-09-03-plan-1-multi-agent-per-repo-T11-review.md` (`693751ad`,
`Agent-Name: infra`). A green whole-repo gate is not currently obtainable, so each phase proves
itself with `ruff check` + `ruff format --check` + `pytest` on its OWN files, plus the failing gate
embedded and declared in the exact form `check_convergence.py:224` accepts — not a paraphrase.

## Evidence

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

`core/30-ops.md:222` is the sharpest row here and it changed a step: Gate A asserts the snapshot
**contains files**, and A.3 keeps the archive out of `/opt/backups/**` precisely because that prefix
is excluded from the plan that would otherwise cover it.

## fabrik-lib verdict

**BUILD.** `/opt/fabrik-lib/README.md` has no archive/backup/compression/retention module — the only
`B2` hit is `rn-media-kit/`, an RN/Expo client upload kit, unrelated. New-module bar: the archiver is
project-specific (Claude transcript layout, session-recall's mirror semantics, this box's Backrest
topology), failing (a) *generic* and (b) *reused by ≥2 project types*. Hub-local, no candidate flag.

## Docs owed (Doc Sync Matrix)

`docs/workstation/session-history-retention.md` (NEW — box-local subsystem; grep first, extend never
duplicate) · `INDEX.md` row · `CHANGELOG.md` per phase · the spec's Open unknown 1 updated with the
Phase-0 bounds · `docs/OPERATIONS.md` if the Backrest plan set changes (`core/30-ops.md:192`).

## Residual risks, named

1. **The cap is unknown until Phase 0 reports.** A and B are safe without it; C is not, and must not
   start with an invented number.
2. **Subagent deletion is irreversible with no index fallback**, and has one live reader whose safety
   rests on it only inspecting in-flight sessions. Operator-accepted.
3. **Phase A writes to a live production VPS.** It adds files under a new path only, never touches an
   existing one, and fails loudly rather than silently.
4. **`--full` remains live upstream** until session-recall acts; C.5 reduces the local blast radius
   and does not fix their repo.
5. **B2 storage cost is small but not zero** at the 90 GB worst case — Phase 0's bounds are what keep
   it in the noise, which is another reason C cannot precede 0.

## Self-audit

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
