# Plan — standby-survivable resume sweep (persistent markers + death-class eligibility + vm-cut classification)

Status: DRAFT
Date: 2026-08-13
Owner: infra (operator-dispatched after the 2026-08-13 Modern Standby incident diagnosis)
Shape: monolith, single phase (small box-side hardening + one synced-hook edit)

## What we already agreed

- Operator dispatch (verbatim NEXT echo): "dispatch the mesh follow-ups as a small plan
  (/fabrik-plan-after-chat: persistent death records + standby-aware sweep)".
- Incident (2026-08-13, diagnosed this session; memory:
  `project_modern_standby_killed_overnight_agents.md`): Modern Standby (Kernel-Power 506 at
  02:31, exit 507 at 09:51) terminated/bounced the WSL VM ~13× (05:39–07:11 "no-lockdir" sweeps);
  `/tmp/claude-sound-locks-1000` was wiped every bounce, destroying the `.autonomous` markers AND
  `.errparked` death records → `claude-reboot-sweep.sh:51` exited `no-lockdir` and resumed NOTHING.
- **Grounded design pivot (supersedes the "mirror the death records" phrasing in the dispatch):**
  the sweep already reconstructs mid-work WITHOUT an errparked record — eligibility falls back to
  `decider --check` on the (persistent) transcript (`claude-reboot-sweep.sh:107-110`). So the
  minimal correct fix persists the **`.autonomous` markers** (the only /tmp state with no other
  source of truth), NOT a mirror of every death record. Two real gaps, both probe-confirmed:
  - **Gap 1 — markers are /tmp-only:** written at `session_orient.py:140` into
    `CLAUDE_SOUND_LOCKDIR` (default `/tmp/claude-sound-locks-<uid>`); VM termination erases them;
    sweep exits at `:51` when the dir is gone.
  - **Gap 2 — death-class verdicts are ineligible:** the REAL dead session (web-ecommerce-factory
    `86cf0e31`) prints `stalled-api-error: stalled mid-stream tail` under `--check`, and the
    sweep's `case "$verdict" in busy*)` (`claude-reboot-sweep.sh:110`) REJECTS it →
    `skip-not-midwork`, marker consumed, session stays dead. (Counter-probe: trade-intelligence
    `1991fa9b` prints `parked: assistant-done` → correctly stays ineligible.)
- Standby-aware classification: when the lock dir is missing but persistent markers exist, the
  sweep classifies and logs the cut (`vm-cut`) instead of the dead-end `no-lockdir` exit.
  **Non-goal:** naming "standby" vs "crash" precisely (needs Windows Kernel-Power access from a
  cron context — fragile; the WSL-side signal is mtime/boot-time evidence, logged as detail).
- Constraints (operator mandates, standing): `claude-sound.sh` / `claude-selfwatch.sh` /
  `claude-autoresume.sh` are READ-ONLY. Editable: `claude-reboot-sweep.sh`,
  `claude-mesh-test.sh` (the harness), `session_orient.py` (repo, SYNCED — see ledger), plus new
  files under `~/.claude/state/`. Box surfaces are DR-versioned, never git-committed. No rotation
  coupling. Fixtures red-first (mesh harness currently 114 ok; decider self-test 97 — untouched by
  this plan unless a probe disproves that).

## Context Ledger

| Source | What binds | Grounded ref |
|---|---|---|
| `~/.claude/bin/claude-reboot-sweep.sh` | the sweep's whole contract: `no-lockdir` exit `:51`, marker glob `:55`, one-read parse `:59-68`, stale gate `:74-79`, pre-reboot `.reviving` clear `:83`, liveness gate `:91-98`, eligibility `:100-111` (errparked short-circuit `:105`, `--check` fallback `:107-110`, `case busy*` `:110`), consume-before-start `:121`, spacing `:120` | read in full this session |
| `/opt/fabrik/.claude/hooks/session_orient.py` | `.autonomous` marker writer: gated on `CLAUDE_MESH_AUTONOMOUS=1` `:127`, dir from `CLAUDE_SOUND_LOCKDIR` `:129-131`, 0600-at-create fd write `:140-143`, fail-open `:144-145` | `session_orient.py:125-145` |
| **SYNC-CONSCIOUSNESS** | `.claude/hooks/` is a governance-sync **trigger surface** — editing `session_orient.py` distributes to ~46 projects on commit. The change (marker target dir) is box-global and identical for every project, so fleet-correct by construction; still: verify post-sync on 2 sample projects | `.pre-commit-config.yaml` governance-sync files-filter |
| `~/.claude/bin/claude-stop-decider.py` | `--check` output shape `<verdict>: <detail>`; LOCK_DIR env `:65-66`; death verdict string `stalled-api-error` (mid-stream + connection-failure classes both route to it) — **not edited by this plan** | probed live: `stalled-api-error: stalled mid-stream tail` / `parked: assistant-done` |
| `~/.claude/bin/claude-mesh-test.sh` | the R-fixture family (R1/R2/R6 …) already sandboxes the sweep via `$RLOCKS` + env overrides; new fixtures extend this family | `claude-mesh-test.sh:680-721` |
| `claude-sound.sh` / `claude-selfwatch.sh` | READ-ONLY consumers; both honor `CLAUDE_SOUND_LOCKDIR` (`sound.sh:141,258,313`, `selfwatch.sh:14`) — the ephemeral lock dir STAYS where it is; nothing here changes for them | grep probe this session |
| fabrik-lib consult | no module covers WSL/mesh lock persistence (checked README table for state/persistence utilities — this is box-glue, not a reusable capability; no 🆕 candidate: single-box, zero reuse across project types) | `/opt/fabrik-lib/README.md` |
| `.windsurf/rules` (24 ACTIVE via `select_rules.py`) | binding on the hook edit: fail-open hook discipline (a broken hook must never block a session), stdout-only, bounded reads; shell: `set -u` cron-reality pattern already in the sweep | `core/10-python.md` + the sweep's own header conventions |
| DR | `dr_claude_backup.sh` after every `~/.claude` bin edit; `~/.claude/state/` is runtime data, NOT config — excluded from DR by design (a marker is reconstructible; backing it up would resurrect stale resumes on restore) | memory: `project_claude_config_dr_backup` |

## Design (settled)

New persistent dir: **`~/.claude/state/autonomous/`** (override: `MESH_STATE_DIR`), 0700, markers
0600 — same payload/format as today (`{sid, cwd, transcript_path, marked_at}`).

1. **Writer** (`session_orient.py`): write the marker to the persistent dir INSTEAD of the lock
   dir (sole consumer is the sweep; nothing else globs `*.autonomous` — grounded: only
   mesh-test fixtures do, via the sweep). Same 0600-at-create + fail-open discipline.
2. **Sweep** (`claude-reboot-sweep.sh`):
   a. Marker source = **union** of `MESH_STATE_DIR` and the legacy lock dir (dedupe by sid,
      persistent wins; both copies consumed) — keeps every existing R-fixture green and covers
      markers written before the orient change lands (transition safety, permanent cost ~3 lines).
   b. Missing lock dir is **no longer an exit** when markers exist: `mkdir -p` it, log
      `vm-cut` with detail (boot epoch vs newest marker mtime + newest transcript mtime — the
      wall-clock evidence), and continue the sweep. No markers anywhere → keep today's
      `no-lockdir` exit verbatim (fixture-pinned behavior).
   c. Eligibility `case` extends to the death classes: `busy*` (unchanged) **plus
      `stalled-api-error*`** — exactly the string the decider prints for both the mid-stream and
      connection-failure death families. `parked*` stays ineligible (probe-pinned).
3. **No decider edit, no errparked mirroring** — the death record's job (wake a live pane's armed
   self-watch) is inherently same-boot; post-VM-death revival is the sweep's job via `--check`.
4. **Bounce-loop self-heal (by construction, no code):** consume-before-start (`:121`) burns the
   marker on a possibly-doomed bounce boot, BUT the sweep's resume spawns with
   `CLAUDE_MESH_AUTONOMOUS=1` (`:124`) → the resumed session's own SessionStart re-runs
   `session_orient.py:127` and RE-WRITES the marker into the persistent dir. A resume killed by
   the next bounce is therefore re-marked and retried on the next boot; and a boot arriving while
   the resumed session still lives hits the liveness gate, which skips WITHOUT consuming
   (`:95-97`). Document, don't code — but fixture RS7 pins the re-mark half via the orient test.

## Phase A — implement + prove (single phase)

1. **Red-baseline fixtures FIRST** (extend the R-family in `claude-mesh-test.sh`, sandboxed
   `$RLOCKS` + `MESH_STATE_DIR` + `MESH_DECIDER_CMD` stub, `MESH_SWEEP_LOG` to a temp file,
   `claude` stubbed on PATH; watch each RED before implementing):
   - RS1 (Gap 1): marker in `MESH_STATE_DIR`, lock dir DELETED, busy transcript → want
     `vm-cut` logged + `resume-spawned`; today: `no-lockdir` exit, nothing spawned.
   - RS2 (Gap 2): marker present, no errparked, decider stub prints
     `stalled-api-error: stalled mid-stream tail` → want `resume-spawned why=stalled-api-error`;
     today: `skip-not-midwork`.
   - RS3 (guard): decider stub prints `parked: assistant-done` → `skip-not-midwork` (must stay).
   - RS4 (compat): marker in LEGACY lock dir only → still consumed + swept (union path).
   - RS5 (dedupe): same sid marker in BOTH dirs → exactly one spawn, both copies consumed.
   - RS6 (true empty): no markers anywhere, no lock dir → `no-lockdir` exit unchanged.
   - Repo side: extend the EXISTING `tests/test_session_orient_hook.py` (grounded present)
     asserting the marker lands in `MESH_STATE_DIR` (env-overridden tmp), 0600, fail-open on an
     unwritable dir, and (RS7's repo half) that a re-run with `CLAUDE_MESH_AUTONOMOUS=1` re-writes
     a consumed marker.
2. **Implement** the three edits (design above): `session_orient.py` target dir;
   sweep union-read + vm-cut + eligibility case. Keep the sweep's one-line `note` discipline for
   every new decision path.
3. **Prove**: mesh harness green (`env -u CLAUDE_SOUND_AUTOROTATE bash
   ~/.claude/bin/claude-mesh-test.sh` — 114 + new all ok); repo tests green; **live replay**: run
   the sweep read-only-style against a sandbox seeded with the REAL 86cf0e31 transcript (copy) +
   a synthetic marker → `resume-spawned` path reached with the `claude` stub recording the exact
   `--resume` argv (never spawn a real resume in tests).
4. **Sync + DR**: commit repo side (`session_orient.py` + tests + docs) — governance-sync
   distributes the hook; post-sync probe 2 projects' `.claude/hooks/session_orient.py` md5 ==
   hub's. Run `bash /opt/fabrik/scripts/dr_claude_backup.sh` (sweep + harness edits).
5. **Docs** (Doc Sync Matrix): `docs/workstation/hooks-index.md` — §1 SessionStart
   `session_orient.py` row (marker → persistent `~/.claude/state/autonomous/`) + §2 StopFailure
   row's sweep clause (vm-cut + death-class eligibility); `CHANGELOG.md` entry; update memory
   `project_modern_standby_killed_overnight_agents.md` (follow-ups → executed).
6. **/fabrik-review** on the full delta (both box files + hook + tests) to a
   coverage-adjudicated quiet close; then FULL gate; commit repo side with
   `Agent-Name: infra` trailers, push.

Gates (runnable): mesh harness exit 0 with new count stated · `pytest tests/ -k orient` green ·
`python scripts/final_gate.py --json` success · post-sync md5 probe equal on 2 projects.

## Risks / edge cases baked in

- **Second-writer safety unchanged:** liveness gate (`:91-98`) still consults the persistent
  transcript; consume-before-start (`:121`) now removes BOTH marker copies before spawning.
- **Clean-shutdown replay:** a marker surviving a NORMAL shutdown is consumed harmlessly — the
  `--check` fallback reads the cleanly-ended transcript as `parked*` → skip (RS3 pins it).
- **Stale persistent markers:** the existing week `max_age` gate applies unchanged (mtime-based,
  dir-agnostic).
- **Orient hook failure:** fail-open preserved — an unwritable state dir logs nothing and never
  blocks a session (repo test pins it).
- **Fleet blast radius:** the orient edit ships to ~46 projects; the mechanism is identical
  everywhere (box-global dirs), and headless/interactive gating (`CLAUDE_MESH_AUTONOMOUS`) is
  untouched.

## File Scope

Repo: this plan file ·
`docs/development/reviews/2026-08-13-plan-1-standby-survivable-sweep-review.md` ·
`.claude/hooks/session_orient.py` (SYNCED) · `tests/test_session_orient_hook.py` ·
`docs/workstation/hooks-index.md`. (CHANGELOG/LESSONS stay OUT of File Scope by the plan-lock
grammar — shared-append surfaces; their update steps remain in Phase A.)
Box (DR-versioned, not git): `~/.claude/bin/claude-reboot-sweep.sh` ·
`~/.claude/bin/claude-mesh-test.sh` · new dir `~/.claude/state/autonomous/`.

## Evidence

(Per-phase `## Evidence` blocks — `path:line` + fenced command output — are appended at
execution; the probes in "What we already agreed" carry the plan-time grounding.)

## Self-audit

- Both gaps are probe-confirmed on the REAL incident artifacts (the `86cf0e31` `--check` output
  and the sweep's `:51`/`:110` lines), not inferred.
- The dispatch's "mirror the death records" was measured against the code and NARROWED to
  marker persistence + eligibility (the sweep's own `--check` fallback makes a death-record
  mirror redundant) — recorded as the design pivot, operator can override.
- No READ-ONLY surface is edited; the decider is untouched; no rotation coupling anywhere.
- Open residuals: none — every decision either grounded here or pinned by a fixture the executor
  watches RED first.
