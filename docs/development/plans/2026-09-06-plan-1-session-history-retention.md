# Plan — session-history retention: archive, prove, then prune

Status: DRAFT
Date: 2026-09-06
Owner: fleet
Spec: `docs/superpowers/specs/2026-09-05-session-history-retention-design.md` (CONVERGED, md5
`9bf26fd7f744155ab541c23650fd8205`, D-142, commit `2814df66`)

## Why the phase order is a safety property, not a preference

This build deletes irreplaceable data at its last step. Two claims in the spec's own history were
refuted by reading code *after* they had been asserted confidently — a size comparison that called
15 `.bak` files "provably lossless" when 293 messages existed only in them, and "text forever in
session-recall" when `_reclaim_orphans` deletes a session's turns as soon as its JSONL is gone. The
phase order exists so that being wrong a third time costs disk, not history.

**No phase may merge forward. Phase C does not begin until Phase B has produced a byte-identical
restore pulled back through Backrest and B2.**

## Phase 0 — MEASURE (no code ships)

The spec fixes 90 days but leaves the size cap open, and honestly so: MAIN was **0.61 GB in August**
and **4.89 GB in the first five days of September**, the difference between a ~2 GB and a ~90 GB
window. A number invented now would be the fourth confident guess in this file's history.

- **0.1** Add a daily sampler recording MAIN bytes/day and file count to a flat log —
  `find ~/.claude/projects -name '*.jsonl' ! -path '*/subagents/*'`, the same predicate the spec's
  baseline used, so the series is comparable.
- **0.2** Let it run **14 days**. No cap value is written into code before then.
- **0.3** Derive the cap from the observed p95 daily rate × 90, and record it with its measurement
  window in the spec's Open unknown 1.

**Gate:** 14 daily samples exist and the derived cap is written down with the command that produced
it. **Deletes nothing. Blocks nothing** — phases A and B proceed in parallel.

## Phase A — TRANSPORT + ARCHIVE (non-destructive)

Nothing today copies transcripts off the WSL box. This is the real work.

- **A.1 — the archiver.** `zstd -12` each MAIN transcript older than N days into
  `<archive>/<project-slug>/<session-id>.jsonl.zst`, and append `(session_id, sha256, bytes,
  archived_at)` to a manifest. Compression is measured, not assumed: **6.08x on a 70.7 MB
  transcript, 1.5 s to compress, 0.08 s to restore, byte-identical with matching sha256**.
  ⚠️ The sha recorded is of the **source file at archive time**; Phase C re-hashes at delete time
  rather than trusting it.
- **A.2 — the transport.** `rsync -az <archive>/ vps:<remote>/` behind an `ssh vps 'mkdir -p …'`,
  exactly the shape `scripts/sync-vps-sysadmin.sh:21,28` already uses fleet-side. rsync gives
  incrementality and idempotency for free: a dropped link costs a re-run, never a partial or
  doubled copy. ⚠️ **The alias is `vps`, not `vps1`** — `vps1` does not resolve
  (`~/.ssh/config`: `Host vps` → 172.93.160.197).
- **A.3 — Backrest coverage. THE PLAN PICKS: its own plan, not `opt-configs`.**
  Backrest has one repo, `b2-vps1` (`s3://`, Backblaze B2), and nine scheduled plans; `opt-configs`
  backs up **all of `/opt`** on a schedule. Riding it would be one line of nothing, and it is the
  wrong call: `opt-configs` protects a mostly-static config tree, and folding a monotonically
  growing archive into it couples an archive's retention to a config backup's retention, changes
  that plan's snapshot churn, and makes a config restore drag the archive with it. A dedicated plan
  keeps the two independent — its own retention, its own restore, its own failure.
  The archive therefore lives **outside** the `/opt` subtree `opt-configs` sweeps, or that plan's
  paths are narrowed; the step must verify which, because a double-backed-up archive is
  silent B2 spend.
- **A.4 — env, not literals.** Archive root, remote path, retention days and the cap come from env
  with defaults (`core/10-python.md:128` bans hardcoded hosts; 12-Factor III). No `localhost`, no
  baked paths.
- **A.5 — the marker.** A `README` in `~/.claude/projects/` stating the tree is data, not cache,
  aimed squarely at the failure that actually happened: a human freeing disk space.

**Gate A:** the archive exists on vps1, `restic snapshots` (via Backrest) lists it, and the manifest
row count equals the archived file count. **Zero deletions.** `/fabrik-review-scoped` at the
boundary.

## Phase B — PROVE THE RESTORE (still non-destructive)

The local round trip is measured. **The leg through Backrest and B2 is not, and it is the one that
matters.**

- **B.1** Pick an archived transcript. Restore it **from the B2 repo** (not from the vps1 copy —
  that would prove the wrong hop).
- **B.2** `zstd -d`, then `cmp` against the live original **and** compare sha256.
- **B.3** Record the verbatim command output in the plan's Evidence block.
- **B.4** Restore one transcript whose live original has since been **deleted or rewritten**, to
  prove the archive stands alone rather than only agreeing with a file that still exists.

**Gate B:** a byte-identical restore, pulled from B2, with its output embedded. ⚠️ **Phase C is
BLOCKED until this gate is green.** A failed or skipped Gate B is a `BLOCKED:` escalation, never a
reason to proceed with a smaller prune.

## Phase C — THE PRUNER, behind its grader

- **C.1 — the invariant, in code.** Refuse to delete any transcript whose **CURRENT** sha256 is
  absent from a manifest keyed on **(session_id, sha256)**. Re-hash at delete time. Archive
  unreachable ⇒ **fail CLOSED**: nothing is deleted, the store grows, a warning fires.
- **C.2 — the graders, each SEEN RED before the pruner is trusted** (`core/45-testing-strategy.md:21`
  — *"A green test never seen red is unverified"*):
  - a transcript absent from the manifest, offered to the pruner → **not deleted**;
  - a transcript archived at sha A then **mutated in place** to sha B → **not deleted** (this is the
    `.bak` shape: 13 of 15 diverged mid-file, and a session-id-keyed manifest would have deleted
    them);
  - archive destination unreachable → **nothing deleted**;
  - a file inside the window → not offered at all.
- **C.3 — the tiers.** MAIN 90 days OR the Phase-0 cap, whichever binds first, counted on **mtime**
  (a resumed session then outlives its window — the KEEP direction, deliberate). SUBAGENT
  transcripts 7 days, **no archive, hard cliff** — they are unindexed (0 of 10,177 index rows carry
  an `agent-` id; `reindex.py:479` globs `*/*.jsonl` and never descends into `<session>/subagents/`),
  operator-accepted. `tool-results/` with its parent.
- **C.4 — pool receipts, 14 days + rotation, WITH the kaizen coupling closed.**
  `libs/subagents/ledger.py:372` calls `read_all()` over the whole history, and
  `scripts/sysadmin/kaizen_collect.py:57` reads that ledger — its `measure_subagents` filters by a
  single day's stamp (`:226`) so the daily run survives rotation, but
  `scripts/sysadmin/kaizen_backfill.py:137` backfills a RANGE from file mtimes and would report
  **zero runs** for rotated days rather than "unavailable". **Rotation must write a per-day summary
  line, or `measure_subagents` must distinguish "rotated" from "no dispatches".** A silent
  under-report is exactly what `Metric.unavailable` exists to prevent.
- **C.5 — a local `--full` guard (hub-side only).** A wrapper that refuses
  `ingest.reindex --full` unless the archive covers every orphan it would reclaim.
  ⚠️ **CROSS-REPO HARD STOP: `/opt/session-recall` is NOT patched by this plan.** The upstream fix
  was mailed as `01M1SPW1KKNXKKKM8MSVT6RHQ9` (ack required) and is theirs.

**Gate C:** every grader red-then-green, `--check` scoped to the changed files, and a dry-run over
the real tree showing what WOULD be deleted, reviewed before any live run.

## ⚠️ Gate mechanics under a red shared gate

`final_gate.py --json` is currently **RED for two sibling-owned reasons** — `Command Corpus`
(infra's in-flight orchestrator retirement) and `Convergence Evidence` on
`docs/development/reviews/2026-09-03-plan-1-multi-agent-per-repo-T11-review.md` (`693751ad`,
`Agent-Name: infra`). A green whole-repo gate is **not currently obtainable**, so every phase gate
above proves itself by: (a) `ruff check` + `ruff format --check` on **its own changed files**;
(b) `pytest` on its own test file; (c) `final_gate.py --check --json` with the failing checks named
and shown to be out-of-surface — the `GATE-SCOPE:` declaration, not a silent pass. A phase never
claims green by pointing at a red gate and asserting it is someone else's.

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

`core/30-ops.md:222` is the sharpest one for this plan: a Backrest plan pointed at a path that does
not exist reads green forever. Gate A must assert the snapshot **contains files**, not merely that
the plan ran.

## fabrik-lib verdict

**BUILD.** `/opt/fabrik-lib/README.md` has no archive/backup/compression/retention module — the only
`B2` hit is `rn-media-kit/`, an RN/Expo client upload kit, unrelated. New-module-candidate bar: the
archiver is **project-specific** (Claude transcript layout, session-recall's mirror semantics, this
box's Backrest topology), so it fails criterion (a) *generic* and (b) *reused by ≥2 project types*.
Hub-local, no `🆕 fabrik-lib candidate` flag.

## Docs owed (Doc Sync Matrix)

`docs/workstation/session-history-retention.md` (NEW — box-local subsystem; grep first, extend never
duplicate) · `INDEX.md` row · `CHANGELOG.md` per phase · `docs/DECISIONS.md` if any phase changes a
decision D-142 already recorded · the spec's Open unknown 1 updated with the Phase-0 cap.

## Residual risks, named

1. **The cap is unknown until Phase 0 reports.** Phases A and B are safe without it; Phase C is not,
   and must not start with an invented number.
2. **Subagent deletion is irreversible with no index fallback.** Operator-accepted, recorded here so
   it stays a choice rather than a discovery.
3. **The transport writes to a live production VPS.** Phase A adds files only; it must not touch any
   existing path, and its rsync target is a new directory.
4. **`--full` remains live upstream** until session-recall acts. The local guard (C.5) reduces the
   blast radius on this box; it does not fix their repo.

## Self-audit

- Every phase gate names a runnable command, and Gate B blocks Gate C explicitly rather than by
  convention.
- The Backrest sub-question the spec left open is **decided** here (own plan, not `opt-configs`)
  with its reasons, rather than deferred again.
- The kaizen coupling is a **step** (C.4), not a note.
- The size cap is a **measurement** (Phase 0), not a guess.
- Cross-repo boundary is stated twice — C.5 and Residual 4 — because it is the one place this plan
  could quietly become someone else's change.
