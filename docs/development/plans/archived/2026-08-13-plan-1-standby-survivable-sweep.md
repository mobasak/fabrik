# Plan — standby-survivable resume sweep (persistent markers + death-class eligibility + vm-cut classification)

Status: EXECUTED 2026-08-13 (both legs live: persistent markers + seeded launcher + hardened
sweep + cut-session notify. Harness 114→152, repo tests 23, 7-round/5-wave review loop closed
CLEAN — docs/development/reviews/2026-08-13-plan-1-standby-survivable-sweep-review.md; gate
47/0; DR 20260813T122559Z; fleet-sync verified)
Date: 2026-08-13
Owner: infra (operator-dispatched after the 2026-08-13 Modern Standby incident diagnosis)
Shape: monolith, single phase (small box-side hardening + one synced-hook edit)

## What we already agreed

- Operator dispatch (verbatim NEXT echo): "dispatch the mesh follow-ups as a small plan
  (/fabrik-plan-after-chat: persistent death records + standby-aware sweep)".
- Incident (2026-08-13, diagnosed this session; memory:
  `project_modern_standby_killed_overnight_agents.md`): Modern Standby (Kernel-Power 506 at
  02:31, exit 507 at 09:51) terminated/bounced the WSL VM ~13× (05:39–07:11 "no-lockdir" sweeps);
  `/tmp/claude-sound-locks-1000` was wiped every bounce, destroying the `.errparked` death
  records (and any `.autonomous` markers — though none existed, see F1) →
  `claude-reboot-sweep.sh:51` exited `no-lockdir` and resumed NOTHING.
- **Grounded design pivot (supersedes the "mirror the death records" phrasing in the dispatch):**
  the sweep already reconstructs mid-work WITHOUT an errparked record — eligibility falls back to
  `decider --check` on the (persistent) transcript (`claude-reboot-sweep.sh:107-110`). So the
  minimal correct fix persists the **`.autonomous` markers** (the only /tmp state with no other
  source of truth), NOT a mirror of every death record. Two real gaps, both probe-confirmed:
  - **Gap 1 — markers are /tmp-only:** written at `session_orient.py:140` into
    `CLAUDE_SOUND_LOCKDIR` (default `/tmp/claude-sound-locks-<uid>`); VM termination erases them;
    sweep exits at `:51` when the dir is gone.
  - **Gap 2 — death-class verdicts are ineligible:** a dead-mid-work transcript prints
    `stalled-api-error: <detail>` under `--check` (deterministic probe below; at grounding time
    the REAL dead session `86cf0e31` printed it live before the operator's post-wake resume
    moved its tail), and the sweep's `case "$verdict" in busy*)` (`claude-reboot-sweep.sh:110`)
    REJECTS it → `skip-not-midwork`, marker consumed, session stays dead. (Counter-guard:
    cleanly-parked transcripts print `parked: …` — probed live on `1991fa9b` — and must STAY
    ineligible.)
- **F1 (native closer, CONFIRMED — reshapes the plan into TWO legs):** nothing on the box
  exports `CLAUDE_MESH_AUTONOMOUS=1` except the sweep's own respawn (`:124`) — grep across
  `~/.claude/bin`, settings, profiles, `/opt/fabrik/scripts`, `/opt/*/scripts`, systemd returns
  ONE file: the sweep itself. The marker population is EMPTY today, and the incident's dead
  sessions were interactive panes the sweep structurally excludes (`:9-11`). Marker persistence
  alone would ship green and change nothing for the incident class. Therefore:
  - **Leg A (autonomous, future-proof):** marker persistence + all sweep hardening below, PLUS a
    seed producer — `scripts/ci_fix_dispatcher.py` (repo-side, ours, genuinely autonomous)
    exports `CLAUDE_MESH_AUTONOMOUS=1` on its `claude -p` spawns. Other launcher owners
    (youtube headless crons, the watchdog) get a fabrik-mail handoff naming the one-line export —
    cross-repo, never edited from here.
  - **Leg B (interactive — the actual incident class):** the sweep detects the vm-cut and
    NOTIFIES the operator per cut-mid-work session via the EXISTING
    `claude-sound.sh mesh-notify <sid> <cwd> <err>` mode (invoking the READ-ONLY script is not
    editing it; contract grounded at `claude-sound.sh:249-262`: `/opt/*` cwd gate, 30-min
    per-session suppress, `MESH_NOTIFY_CMD` injection seam for fixtures, body carries the exact
    `claude --resume <sid>` command). Cut-mid-work detection needs NO markers: scan the newest
    ≤20 transcripts under `~/.claude/projects/*/` with mtime < boot epoch and mtime > boot−48h,
    `--check` each (20s timeout, headless); verdict `busy*`/`stalled-api-error*` = cut mid-work
    → one notify each. Auto-RESUMING interactive panes stays FORBIDDEN (second-writer; `:9-11`).
- Standby-aware classification: when the lock dir is missing/freshly-recreated, the sweep logs
  `vm-cut` (detail: boot epoch vs newest marker/transcript mtime) instead of the dead-end
  `no-lockdir` exit. Boot epoch one-liner (probed in the cron env, F9):
  `boot=$(( $(date +%s) - $(awk '{print int($1)}' /proc/uptime) ))`.
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
| `~/.claude/bin/claude-mesh-test.sh` | the R-fixture family (R1/R2/R6 …) already sandboxes the sweep via `$RLOCKS` + env overrides; new fixtures extend this family | `claude-mesh-test.sh:667-687` (`RLOCKS` def `:668`, `SWEEP()` `:683-687` — closer F8 span fix) |
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
      persistent wins; both copies consumed) — covers markers written before the orient change
      lands (transition safety). Existing R-fixtures stay green ONLY via the mandated
      restructure below (the naive union breaks them — pool F2 / closer F4).
      **Loop restructure is MANDATORY, not stylistic (pool finding F2):** the current
      `for marker in "$locks"/*.autonomous; do [ -e "$marker" ] || break` (`:55-56`) aborts the
      WHOLE loop on the first unmatched glob — a single `for` over two globs would silently skip
      the legacy dir whenever the state dir is empty. Implement as: collect both dirs' matches
      into a dedup'd list first (two nullglob-safe gather passes), then iterate the list; the
      `break` guard dies with the restructure. RS4 red-first pins exactly the
      empty-state-dir + legacy-marker case.
   a2. **Sweep self-lock (pool finding F3):** the sweep has NO flock today, and persistent
      markers widen the concurrent-invocation window (`@reboot` + a cron-daemon restart + a
      manual run can overlap → both pass eligibility before either consumes → double
      `--resume` = the second-writer failure). Add a non-blocking self-lock at entry — with the
      state dir defaulted-and-created FIRST, sweep-side (a box where no writer ever ran has no
      state dir yet; a failed `exec 9>` would abort the whole sweep, worse than today):
      `state="${MESH_STATE_DIR:-$HOME/.claude/state/autonomous}"; mkdir -p -m 700 "$state";
      exec 9>"$state/.sweep.lock"; flock -n 9 || { note "skip-concurrent"; exit 0; }`.
      Fixture RS8: a sweep started while another holds the lock exits `skip-concurrent`,
      consuming nothing.
   a3. **Atomic claim-before-spawn (pool F4 + closer F5/F6):** `rm -f` can never be a claim —
      it SUCCEEDS on an already-deleted file, so two racing sweeps both "consume" and
      double-spawn; and every rm failure is swallowed today (`:76`, `:114`, `:121`), so an
      unremovable persistent marker (root-owned dir, ro mount, full disk) re-spawns the same
      session on EVERY boot — defeating the `:121-122` invariant verbatim. Replace the pre-spawn
      consume with an atomic claim: `mv "$marker" "$marker.claimed" || { note "consume-failed";
      continue; }`; spawn only on mv success; delete the `.claimed` file after spawn (best-
      effort). The mv is atomic per marker even across racing sweeps (only one wins), layered
      UNDER the flock (a2) as defense in depth. Fixture RS9: unremovable marker → `consume-
      failed`, zero spawns, marker still present for the next (fixed-permissions) boot.
   b. Missing lock dir is **no longer an exit** when markers exist: `mkdir -p` it, log
      `vm-cut` with detail (boot epoch vs newest marker mtime + newest transcript mtime — the
      wall-clock evidence), and continue the sweep. No markers anywhere → keep today's
      `no-lockdir` exit verbatim (RS6 becomes its FIRST pin — nothing pins it today, closer F7).
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

## Plan-time probes (re-runnable, deterministic — the grounding for the two gap claims)

```
$ P=$(mktemp); printf '%s\n%s\n' '{"type":"user","timestamp":"2026-08-13T00:00:00.000Z","message":{"role":"user","content":"hi"}}' '{"type":"assistant","timestamp":"2026-08-13T00:00:01.000Z","isApiErrorMessage":true,"message":{"role":"assistant","stop_reason":"stop_sequence","content":[{"type":"text","text":"API Error: Response stalled mid-stream. The response above may be incomplete."}]}}' > "$P"; printf '{"session_id":"probe1","transcript_path":"%s","cwd":"/tmp"}' "$P" | CLAUDE_SOUND_HEADLESS=1 timeout 20 python3 ~/.claude/bin/claude-stop-decider.py --check; rm -f "$P"
stalled-api-error: stalled mid-stream tail
```

The verdict string `stalled-api-error: …` is Gap 2's red baseline: the current sweep
`case "$verdict" in busy*)` (`:110`) rejects it, so a genuinely-dead mid-work session is
`skip-not-midwork`'d. (History note: at plan-grounding time the REAL incident transcript
`86cf0e31` printed exactly this string live; the operator's post-wake resume then moved that
file's tail to `parked: assistant-done` — caught by this review's probe re-run, which is WHY the
probe is synthetic-deterministic rather than pointed at a living transcript. The counter-guard —
cleanly-parked sessions print `parked: …` and must stay ineligible — is pinned by fixture RS3
with a decider stub, same contract.)

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
   - RS8 (F3): a sweep started while another holds `.sweep.lock` exits `skip-concurrent`,
     consuming nothing.
   - RS9 (F4/F5/F6): an unremovable marker (chmod 555 parent) logs `consume-failed`, spawns
     nothing, and the next sweep (permissions restored) still processes it.
   - RS10 (Leg B): a projects tree seeded with one cut-mid-work transcript (stalled tail, mtime
     < boot) + one cleanly-parked one → exactly one `MESH_NOTIFY_CMD` stub capture, body contains
     `claude --resume`; second run within the suppress window sends nothing.
   - Leg A seed (repo side): `ci_fix_dispatcher.py` test asserting its claude spawn env carries
     `CLAUDE_MESH_AUTONOMOUS=1`.
   - Repo side (`tests/test_session_orient_hook.py`, grounded present): **RETARGET, don't just
     extend (closer F3)** — the existing marker assertions at `:218` and `:237` pin the marker to
     `CLAUDE_SOUND_LOCKDIR` and go RED the moment the orient edit lands; the plan treats that RED
     as the EXPECTED watched-fail of the retarget (flip them to `MESH_STATE_DIR`), then adds:
     0600 mode assert, fail-open on an unwritable state dir, and (RS7's repo half) a re-run with
     `CLAUDE_MESH_AUTONOMOUS=1` re-writes a consumed marker.
2. **Implement** the design above, in full: `session_orient.py` target dir · sweep gather-list
   union read (a) · self-flock (a2) · atomic mv-claim (a3) · vm-cut classification + Leg B
   transcript-scan notify via `claude-sound.sh mesh-notify` (b) · eligibility widening (c) ·
   `ci_fix_dispatcher.py` one-line `CLAUDE_MESH_AUTONOMOUS=1` export (Leg A seed). Keep the
   sweep's one-line `note` discipline for every new decision path.
3. **Prove**: mesh harness green (`env -u CLAUDE_SOUND_AUTOROTATE bash
   ~/.claude/bin/claude-mesh-test.sh` — 114 + new all ok); repo tests green; **sandbox replay**:
   run the sweep against a sandbox seeded with the SYNTHETIC stalled-tail transcript (the
   plan-time probe's construction — the real incident transcripts are living files whose tails
   have already moved, closer F2) + a marker → `resume-spawned` reached with the `claude` stub
   recording the exact `--resume` argv (never spawn a real resume in tests).
4. **Sync + DR**: commit repo side (`session_orient.py` + tests + docs) — governance-sync
   distributes the hook; post-sync probe 2 projects' `.claude/hooks/session_orient.py` md5 ==
   hub's. Run `bash /opt/fabrik/scripts/dr_claude_backup.sh` (sweep + harness edits).
5. **Docs** (Doc Sync Matrix): `docs/workstation/hooks-index.md` — §1 SessionStart
   `session_orient.py` row (marker → persistent `~/.claude/state/autonomous/`) + §2 StopFailure
   row's sweep clause (vm-cut + Leg B notify + death-class eligibility); `CHANGELOG.md` entry;
   update memory `project_modern_standby_killed_overnight_agents.md` (follow-ups → executed);
   **fabrik-mail handoffs** to the other launcher owners (youtube: the export one-liner + the
   `CLAUDE_CONFIG_DIR` nuance; watchdog repo likewise) — cross-repo, mail not edit.
6. **/fabrik-review** on the full delta (both box files + hook + tests) to a
   coverage-adjudicated quiet close; then FULL gate; commit repo side with
   `Agent-Name: infra` trailers, push.

Gates (runnable): mesh harness exit 0 with new count stated · `pytest tests/ -k orient` green ·
`python scripts/final_gate.py --json` success · post-sync md5 probe equal on 2 projects.

## Risks / edge cases baked in

- **Second-writer safety strengthened:** liveness gate (`:91-98`) still consults the persistent
  transcript; the pre-spawn consume becomes an atomic per-marker mv-claim (a3) under the sweep
  self-flock (a2) — both copies claimed before any spawn; interactive panes remain structurally
  excluded (Leg B notifies, never resumes).
- **Clean-shutdown replay:** a marker surviving a NORMAL shutdown is consumed harmlessly — the
  `--check` fallback reads the cleanly-ended transcript as `parked*` → skip (RS3 pins it).
- **Stale persistent markers:** the existing week `max_age` gate applies unchanged (mtime-based,
  dir-agnostic).
- **Orient hook failure:** fail-open preserved — an unwritable state dir logs nothing and never
  blocks a session (repo test pins it).
- **Fleet blast radius:** the orient edit ships to ~46 projects; the mechanism is identical
  everywhere (box-global dirs), and headless/interactive gating (`CLAUDE_MESH_AUTONOMOUS`) is
  untouched. Closer nuance, recorded: `/opt/youtube`'s headless cron runs with
  `CLAUDE_CONFIG_DIR=$HOME/.claude-youtube-headless` — a `HOME`-derived state dir keeps its
  markers in the default tree (same as today's /tmp behavior, but now persistent); harmless
  until youtube adopts the export, noted in its mail handoff.
- **Leg B scan bound (as executed):** gated on a FRESH boot (lock dir absent — cron-restart
  re-fires skip it, closing the re-notify window); ≤20 transcripts, subagent sidecars excluded,
  each behind `timeout 20`; sids Leg A just resumed are excluded (two-writer guard); notify
  suppression is a PERSISTENT 24h per-sid stamp in the state dir (the lock-dir `.notified`
  stamps die with the VM — 13 bounce boots must not storm).

## File Scope

Repo: this plan file ·
`docs/development/reviews/2026-08-13-plan-1-standby-survivable-sweep-review.md` ·
`.claude/hooks/session_orient.py` (SYNCED) · `tests/test_session_orient_hook.py` ·
`scripts/ci_fix_dispatcher.py` (+ its test file) ·
`docs/workstation/hooks-index.md`. (CHANGELOG/LESSONS stay OUT of File Scope by the plan-lock
grammar — shared-append surfaces; their update steps remain in Phase A.)
Box (DR-versioned, not git): `~/.claude/bin/claude-reboot-sweep.sh` ·
`~/.claude/bin/claude-mesh-test.sh` · new dir `~/.claude/state/autonomous/`.

## Evidence

(Per-phase `## Evidence` blocks — `path:line` + fenced command output — are appended at
execution; the probes in "What we already agreed" carry the plan-time grounding.)

## Self-audit

- Both gaps are probe-confirmed (Gap 2 by the deterministic synthetic probe — the live
  `86cf0e31` evidence expired mid-review when the operator's resume moved its tail, itself a
  recorded review catch; Gap 1 by the sweep's `:51` + the incident's `no-lockdir` log), not
  inferred. F1 (empty marker population) reshaped the plan into two legs rather than being
  papered over.
- The dispatch's "mirror the death records" was measured against the code and NARROWED to
  marker persistence + eligibility (the sweep's own `--check` fallback makes a death-record
  mirror redundant) — recorded as the design pivot, operator can override.
- No READ-ONLY surface is edited; the decider is untouched; no rotation coupling anywhere.
- Open residuals: none — every decision either grounded here or pinned by a fixture the executor
  watches RED first.
