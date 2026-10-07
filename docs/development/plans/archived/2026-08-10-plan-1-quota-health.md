# Quota-health for the resume mesh — reset-clock revival, health-aware rotation, token re-capture, reboot sweep

Status: EXECUTED
Spec: docs/superpowers/specs/2026-08-10-quota-health-design.md (CONVERGED 2026-08-10, operator-approved)
Shape: MONOLITH — primary surface is `~/.claude/bin` + `~/.claude/.claude-manager` (out-of-repo, DR-versioned); the ticket-set gate bans out-of-repo Touches, and the reviewed resume-mesh plan (2026-08-09-plan-2) is the precedent for this shape. 5 phases.

## What we already agreed (spec + operator, verbatim decisions)

- Parse the wall (`rateLimitType`, `resetsAt`) at death; switch to a healthy sibling when one exists
  ("if the other account has quota, we can switch directly"); schedule revival at the reset clock
  otherwise ("send a resume/continue after the clock is reached") — operator, 2026-08-09.
- AUTOROTATE flips default ON with this build (was opt-in-off pending exactly this design).
- Pane revival = the armed self-watch's wake; never headless typing into a pane.
- Re-capture live tokens after manual logins (three triggers; monotone snapshot guard).
- Reboot sweep resumes ONLY `CLAUDE_MESH_AUTONOMOUS=1`-marked sessions, staggered; panes manual.
- Lowest-`usedPercent` healthy sibling preferred (operator cost-question delta).
- Dollar-cost accounting stays decoupled (recorded decision in the spec).

## Context Ledger

| Source | What binds | Grounded ref |
|---|---|---|
| Spec (CONVERGED) | goal, approach, bounds, taxonomy, allocation of every design decision | docs/superpowers/specs/2026-08-10-quota-health-design.md |
| Shipped CLI binary | StopFailure payload fields (`error_details`); `resetsAt`/`rateLimitType` (6 members incl. `overage`) | `~/.local/share/claude/versions/2.1.219` — two independent inspections 2026-08-10 (spec table) |
| claude-manager tap | `statusline.json rateLimits.{fiveHour,sevenDay}.resetsAt` structured source; `session-start-tap.js` = the SessionStart ride for the drift-check | `~/.claude/.claude-manager/statusline-tap.js` (`resetsAt:l(n.resets_at)`) |
| `claude_rotate.py` | the rotation CLI this plan seam-extends: `main()` dispatch `scripts/sysadmin/claude_rotate.py:658-685`; `_active_account()` :151; `_secure_write()` :203; install writes `ACTIVE_MARKER` :284, rolling `BACKUP_CREDS` :277 | fresh read 2026-08-10 |
| The reviewed mesh | insertion points: sound.sh rotation gate :145 + 2a spawn gate :164 (⚠️ file under active sibling churn — re-grep by PATTERN at execution); selfwatch backoff :36-38; autoresume backoff :41+:78; harness summary print :473 / 71 fixtures | fresh greps 2026-08-10, re-freshed mid-review after a sibling's headless-mute block shifted sound.sh ~+23 lines |
| `.windsurf/rules` (ACTIVE per select_rules) | 10-python (typing/env), 55-observability (stdout/bounded logs), 45-testing (behavior contract), 35-security-auth floor (no secrets in code/echo) | run at spec time, packs re-read |
| fabrik-lib | verdict table inherited from the spec: BUILD (box opsware; `api-quota`/`llm-dispatch` dismissed by name), VENDOR `claude_rotate.py` + tap + mesh | spec § fabrik-lib verdict |
| Memories (operator law) | Claude Code CLI/OAuth only; no $ caps on operational loops; single-operator threat model; DR backup after every `~/.claude` change; commit-AND-push per phase | recorded memory files |

## Global Constraints

- All new box files: stdlib-only python or POSIX bash, peers of the decider; `set -u` in bash; fail-open toward the existing mesh behavior (an error in quota logic must degrade to today's 90s path, never block a hook).
- No secrets in code or logs; token BYTES never echoed/printed; credential snapshots 600-mode via `_secure_write` (rotate side); `wall-state.json` 600-mode via `os.open(..., 0o600)` inside `--record` (quota side — it cannot reach `_secure_write`).
- 12-Factor rows binding here: **III** config via env (`CLAUDE_SOUND_*`/`MESH_*` knobs; no grouped sets) · **XI** no new log files — all logging through `log_line`/`log_verdict` into the existing bounded log · **VIII** owned deviation per spec (sleepers/watches ARE the substrate; no PID files; kill-safe via markers) · **V** no hot-patching a running watch (changes land on disk; running monitors pick them up at next arm).
- Every waiter bounded: waits return from `--wait-seconds` already clamped (`max(0, resetsAt−now)+jitter`, `jitter_max<slack` per type: five_hour 120/300s, seven_day* + exhausted-overage 600/1800s); unknown reset → legacy 90s; past deadline → the mesh ring path owns.
- The wait loop contract (spec): slices ≤60s, each slice touches `.reviving` (35-min staleness stays honest) and re-runs the survival re-check; `start.lock` wraps only the start instant.
- `<synthetic>`/anonymous sids: no per-session mesh state (existing guards; new code honors them).
- Shared-tree law: stage explicit paths only; provenance trailers; push per phase; DR backup after every `~/.claude/bin` or `.claude-manager` change (`bash /opt/fabrik/scripts/dr_claude_backup.sh`).

## Phase A — `claude-quota.py`: parse, wall-state, wait computation (the core) ✅ EXECUTED

> Closed 2026-08-10: 39 self-test fixtures + harness Section Q. `/fabrik-review` ran 4 rounds,
> 14 fixes — heaviest: the manager tap reports AMBIENT usage, not exhaustion (a transient 429
> would have slept hours), then the priority inversion that fix introduced. Final round NONE.
> Gate `mesh-test: 80 ok, 0 fail` · DR `20260810T082835Z`.

**Files:** `~/.claude/bin/claude-quota.py` (new, ~200 LOC, stdlib-only) · harness Section Q in `~/.claude/bin/claude-mesh-test.sh` (new fixtures appended BEFORE the summary PRINT at :473 — :474 is the trailing exit-check; inserting between them would print a stale count).

**Interfaces — Produces (later phases consume verbatim):**
- CLI `claude-quota.py --record` — stdin = the StopFailure payload JSON; resolves `(rateLimitType, resetsAt)` via the spec ladder (statusline-structured first; `error_details` regex second, plausibility-gated to `[now, now+max_window_for_type]`; else UNKNOWN) and upserts `~/.claude/.claude-manager/wall-state.json` `{account: {rateLimitType, resetsAt, recordedAt}}` for the ACTIVE account — resolved by replicating ALL THREE of `_active_account()`'s signals in order (token-match → unique-org-match → marker; `claude_rotate.py:168-200` — the org step exists precisely for the marker-less bootstrap account and MUST NOT be dropped; read-only reimplementation, bash-callable). Exit 0 always (fail-open); `--record` never blocks the hook path.
- CLI `claude-quota.py --wait-seconds <error-class>` — prints ONE integer: `max(0, resetsAt−now)+jitter` for the active account's live wall (self-expired entries ignored), `90` when unknown/transient/flowing-overage, per-type jitter/slack from the Global Constraints row. THE one wait computation both revival layers consult.
- CLI `claude-quota.py --healthy-sibling` — prints the snapshot-dir NAME of the healthiest sibling (no live wall; among several, lowest `statusline` `usedPercent`… falls back to any-no-wall when percents are absent) or exits 1 when none.
- CLI `claude-quota.py --status` — human-readable wall-state dump (the operator inspector).
- CLI `claude-quota.py --self-test` — fixture suite like the decider's; exit 0 = green.
- `rateLimitType=overage`: flowing → transient (90); exhausted-with-parseable-reset in `error_details` → wall on seven_day* bounds (spec's conservative pin; the channel is the named unknown).

**Steps:**
1. Highest-risk test FIRST (TDD): write `--self-test` fixtures for the parse ladder — structured-beats-regex, plausibility gate rejects an implausible regex epoch, unknown→90, per-type jitter bounds, self-expiry, `<synthetic>`-safe account resolution, the MARKER-LESS-account org-match case, malformed-payload→exit-0 (fail-open), wall-state written with MODE 0600 (via `os.open(..., O_WRONLY|O_CREAT|O_TRUNC, 0o600)` — `--record` has no access to `_secure_write`, so the security floor is pinned here as its own fixture), `--status` row-per-live-wall, monotone `recordedAt` — run `python3 ~/.claude/bin/claude-quota.py --self-test` and watch the missing implementation FAIL RED, then implement to green.
2. Implement ALL FIVE subcommands per the Interfaces block (`--record`, `--wait-seconds`, `--healthy-sibling`, `--status`, `--self-test` — the last is the fixture runner); `--status` is manual-only for operators but still gets a self-test case (prints one row per live wall, none when empty); `bash -n`-clean callers not needed here (python); `ruff` the file with the repo venv (advisory — the file is out-of-repo, style parity with the decider).
3. Harness Section Q (sandboxed like A-D: `CLAUDE_SOUND_LOCKDIR` + tmp `.claude-manager`; FIRST extend the harness's SBHOME copy block — the `cp`/conditional-copy lines near the top — to install `claude-quota.py` into the sandbox, or every Q fixture and the Phase-B default-path fixtures hit file-not-found): Q1 record-from-payload writes wall-state; Q2 wait-seconds bounded (assert integer within `[resetsAt−now, resetsAt−now+jitter_max]`); Q3 healthy-sibling picks lowest usedPercent; Q4 no-sibling exit 1; Q5 unknown→90. Watch each RED first (missing script → red), then green.
4. Gate: `bash ~/.claude/bin/claude-mesh-test.sh` → `mesh-test: <71+5> ok, 0 fail` AND `python3 ~/.claude/bin/claude-quota.py --self-test` → all green.
5. `python scripts/enforcement/check_doc_sync.py` (no repo docs owed yet — Phase E owns them) → note-only.
6. **/fabrik-review on Phase A's changed surface — BLOCKING, run to its coverage-adjudicated exit** (every class CLEAN/FIXED/REFUTED; the fixing pass is never the last look).
7. DR backup (`bash /opt/fabrik/scripts/dr_claude_backup.sh`) + commit any repo-side deltas with trailers + push.

**Behavior Contract (risk-ordered):** structured-source-beats-regex (the ladder inversion) · plausibility gate rejects out-of-window epochs · wait always bounded per type · healthy-sibling prefers lowest usedPercent · fail-open: malformed payload/state → exit 0 + legacy semantics.

## Phase B — Mesh integration: record at death, switch-or-wait, announce ✅ EXECUTED

> Closed 2026-08-10: harness Section BQ (+ BQ7/8/9 gap fixtures) → `mesh-test: 95 ok, 0 fail`.
> `/fabrik-review` ran 3 rounds, 10 fixes — heaviest (native, reproduced): the gate verified the
> healthy sibling then called blind `--next`, which on a 3-account box can rotate INTO another
> walled account; rotation now targets `--switch <verified>`. Also: the offline ceiling was
> measured from the original death (any hiccup after a multi-hour wait rang instantly), an absent
> helper failed CLOSED, and the announce hid behind the rotation opt-in. Confirming round: both
> raised candidates REFUTED with proof (the `*[!0-9]*` guard does catch negatives — verified
> empirically; the ceiling re-baseline is the intended semantic). DR `20260810T1157Z`.

**Files:** `~/.claude/bin/claude-sound.sh` (failure branch) · `~/.claude/bin/claude-selfwatch.sh` · `~/.claude/bin/claude-autoresume.sh` · harness fixtures.

**Interfaces — Consumes:** Phase A's four CLIs verbatim. **Produces:** the end-to-end behavior the spec's Goals 1-3 name.

**Steps:**
1. Red-first harness fixtures (append; watch each red against unmodified scripts): B13 death-with-known-reset → wall-state written (sound.sh calls `--record`); B14 healthy-sibling present + AUTOROTATE=1 → `claude_rotate --next` spawned (shim) + immediate revival; B15 no sibling → NO rotation churn + the announce line carries "walled until" (MESH_NOTIFY_CMD shim); W6 selfwatch consults `--wait-seconds` via the `MESH_QUOTA_CMD` shim; W6b DEFAULT path — no shim, the sandbox-installed real `claude-quota.py` + a seeded wall-state answers (the production path, both layers); B16 autoresume same pair; B16c helper-FAILURE path (MESH_QUOTA_CMD → missing binary) degrades to 90; B17 the autoresume wait-loop touches `.reviving` each slice (mtime advances during a shimmed 3-slice wait — `.reviving` is the REVIVER's flag alone; the pane watch has no relationship to it, per the spec's interlock paragraph).
2. sound.sh failure branch, `rate_limit` arm (insertion at the rotation gate — `:145` as of this review's LAST fresh grep, but ⚠️ sound.sh is under ACTIVE SIBLING CHURN today (a headless-mute block landed mid-review, shifting every line ~+23): the executor RE-GREPS the anchor patterns (`rate_limit|authentication_failed|invalid_grant)` and the 2a spawn-gate class list) at execution start, never trusts these absolutes): call `--record` (detached-safe, `|| true`); with AUTOROTATE on: `--healthy-sibling` → hit: existing `claude_rotate.py --next` path through the rotation limiter (the `rotation.last` 600s window — read/write at `:150`/`:153` this grep; A-section fixtures pin it) · miss: skip rotation, `mesh-notify`-announce "walled until <reset>, revival scheduled" (suppress rules reused).
3. selfwatch `:36-38` + autoresume `:41,:78`: replace the fixed `bo=90` for `rate_limit` with `$(claude-quota.py --wait-seconds rate_limit)` (env override `MESH_QUOTA_CMD` for fixtures; absent/failed helper → 90 fail-open). The SLICED WAIT IS NET-NEW CODE in both scripts (nothing slice-shaped exists in either backoff today — the current waits are single un-sliced sleeps): a `while remaining>0; do sleep min(60,remaining); …; done` loop; per slice, autoresume touches `.reviving` (it owns the flag) AND calls the pre-existing `survived()` primitive (`claude-autoresume.sh:33` — the primitive exists, its per-slice WIRING is new); selfwatch per slice re-checks its marker exists (its own existing heal semantics, now inside the loop).
4. Gate: full harness green (`mesh-test: 84 ok, 0 fail` — 71 + Q1-Q5 + B13/B14/B15/W6/W6b/B16/B16c/B17) + `bash -n` all three scripts + decider `--self-test` unchanged-green.
5. `check_doc_sync.py` → note-only (Phase E owns docs).
6. **/fabrik-review on Phase B's changed surface — BLOCKING, coverage-adjudicated exit.**
7. DR backup + commit repo deltas + push.

**Behavior Contract:** death-with-reset records the wall · sibling-healthy switches (rotation limiter honored) · alone-and-walled announces + schedules, zero churn · both layers' rate_limit waits come from the ONE helper · `.reviving` stays fresh through arbitrary waits · helper failure degrades to today's 90s.

## Phase C — Token re-capture: `--capture-current` + drift triggers ✅ EXECUTED

> Closed 2026-08-10: 19 red-first tests, lean gate 25/0. `/fabrik-review` (native + pool) found
> FOUR real defects — (1) drift-check compared only the ACCESS token while the incident was a
> stale REFRESH token (byte-compare now), (2) the hourly cron logged to an unwritable `/var/log`
> path so the trigger NEVER RAN (empirically reproduced; now `~/.claude/drift-check.log`, live
> end-to-end verified), (3) "monotone" was renamed rather than implemented (now a real
> regression-refusal on the credential's `expiresAt` generation), (4) the byte-identical vendored
> `scripts/aro-wake/` copy was never synced. Plus `.prev` rolling backup, ROTATE_LOCK during
> capture, collision-proof tmp, failed-capture logging. **Live effect: mob@'s 1.5-day-stale
> snapshot — the cause of today's 12:05 login failure — is now byte-identical to the live
> credentials.**

**Files:** `scripts/sysadmin/claude_rotate.py` (repo, fleet-synced surface — the seam is additive) · `tests/test_claude_rotate_capture.py` (new, repo) · `~/.claude/settings.json` (one SessionStart hook entry) · crontab (+1 hourly line).

**Interfaces — Produces:** `claude_rotate.py --capture-current` (snapshot live `ACTIVE_CREDS` into the active account's dir via `_secure_write` `:203`, identified via `_active_account()` `:151`; MONOTONE guard: refuse when the live creds' mtime/content is not newer than the stored snapshot — never regress a snapshot) · `claude_rotate.py --drift-check` (read-only compare live-vs-snapshot; on divergence → capture; exit 0 quiet) — wired at `main()` dispatch `:676-685`.

**Steps:**
1. Red-first pytest: `tests/test_claude_rotate_capture.py` — tmp CLAUDE_DIR fixtures: capture writes the 600-mode snapshot CRASH-SAFELY via tmp+`os.replace` (mirroring `_activate_snapshot`'s own pattern at `claude_rotate.py:278-279` — `_secure_write` alone direct-writes dst with an unlink→recreate window, NOT atomic; the monotone promise needs the rename); monotone guard refuses older content; drift-check captures on divergence and no-ops on parity; token bytes never in stdout/stderr (capture output asserted empty of the token string). Run RED (args unrecognized) → implement → green.
2. Implement both subcommands (reuse `_read_access_token`/`_active_account`/`_secure_write`; ~60 LOC).
3. The THREE triggers (per the agreement): (a) settings.json SessionStart hook entry `claude_rotate.py --drift-check` (async, 10s timeout — rides every session start incl. the first after a manual login); (b) crontab hourly floor at MINUTE :35 — deliberately offset from the existing `:05 sync-claude-accounts-to-fleet.sh` fleet-push so a capture lands before the NEXT push, never mid-push (order-dependence noted: the two hourly credential jobs stay independent); (c) the operator command `--capture-current` itself. Backup settings.json first (credentials-adjacent config → `backups/` per CLAUDE.md).
4. Gate: `python -m pytest tests/test_claude_rotate_capture.py -q` green + `.venv/bin/ruff check scripts/sysadmin/claude_rotate.py` clean + a live `--drift-check` run exits 0.
5. `check_doc_sync.py` → CHANGELOG owed (Phase E consolidates).
6. **/fabrik-review on Phase C's changed surface — BLOCKING, coverage-adjudicated exit.**
7. DR backup (settings.json changed) + commit `scripts/sysadmin/claude_rotate.py` + tests with trailers + push.

**Behavior Contract:** capture is monotone (never regresses) · drift-check auto-captures within one trigger of any manual login · restore reads only the single per-account snapshot (existing `--switch` path unchanged — verified by an assertion test, not modified) · token bytes never emitted.

## Phase D — Reboot sweep + autonomous marking ✅ EXECUTED

> Closed 2026-08-10: harness Section R (11 assertions) -> `mesh-test: 113 ok, 0 fail`; 2 review
> rounds, 8 fixes — heaviest: `@reboot` fires on any cron-daemon restart, so without a liveness
> gate the sweep could resume a session whose writer is still alive; plus cron-environment
> realities (unset HOME crashes under `set -u`; a bare PATH made it log "resumed" while
> `claude` never ran). DR `20260810T095823Z`.

**Files:** `~/.claude/bin/claude-reboot-sweep.sh` (new) · `.claude/hooks/session_orient.py` (repo, fleet-synced: the env-gated marker drop) · `tests/test_session_orient_hook.py` (repo) · crontab (+1 `@reboot` line) · harness Section R.

**Interfaces — Consumes:** the decider's EXISTING `--check` CLI (prints `verdict: detail` from state — `claude-stop-decider.py` main() `--check` branch, fresh-grepped this review) + `errparked` records; `start.lock` serialization; `CLAUDE_MESH_AUTONOMOUS=1` launcher convention. **Produces:** `<sid>.autonomous` markers `{sid, cwd, transcript_path}` (JSON, lock dir); the sweep resumes marked+mid-work sessions staggered.

**Steps:**
1. Red-first orient tests: `test_autonomous_env_drops_marker` (env set + sid → marker JSON in `CLAUDE_SOUND_LOCKDIR`), `test_autonomous_marker_even_when_headless` (CLAUDE_MESH_HEADLESS=1 + CLAUDE_MESH_AUTONOMOUS=1 → marker STILL dropped — the block is INDEPENDENT of the arm gate: placed after the arm_line computation, gated ONLY on its own env+sid; a placement inside the arm gate would silently unmark every headless autonomous session, the exact population the sweep serves), `test_no_env_no_marker` — run RED, then add the ~10-line block to `session_orient.py:105` region (fail-open), green (17 orient tests).
2. `claude-reboot-sweep.sh` (`set -u`, per Global Constraints — asserted by `bash -n` + a harness grep fixture on the shebang block): walk `*.autonomous` markers; per marker: clear the sid's pre-reboot `.reviving` FIRST (spec pin), keep only `decide()`-busy or errparked-standing sessions (probe via `claude-stop-decider.py --check`), resume via `serialize_start`-style spacing with `CLAUDE_SOUND_NO_REVIVE=1 CLAUDE_MESH_HEADLESS=1 claude -p --resume <sid> "continue"`; consume the marker after a successful start; log every outcome through the sound log.
3. Harness Section R (sandboxed, `claude` shim; extend the SBHOME copy block for `claude-reboot-sweep.sh` — same reason as Section Q's note): R1 marked+mid-work → resumed (shim log) + marker consumed; R2 marked+parked-clean → skipped + marker consumed; R3 unmarked → untouched; R4 two marked → starts spaced (starts.log seconds distinct); R5 pre-reboot `.reviving` cleared; R6 a SECOND sweep run is a no-op (markers already consumed — consumption idempotent). Red-first (missing script), then green.
4. Crontab: `@reboot sleep 120 && bash ~/.claude/bin/claude-reboot-sweep.sh` (after the DR entry's slot; 120s lets systemd/net settle).
5. Gate: `mesh-test: 90 ok, 0 fail` (84 + R1-R6) + orient pytest 17/17 + `bash -n` sweep.
6. **/fabrik-review on Phase D's changed surface — BLOCKING, coverage-adjudicated exit.**
7. DR backup + fleet-sync rides the `.claude/hooks/` commit + push.

**Behavior Contract:** only marked sessions swept (R1/R3) · mid-work filter via the decider's real verdicts (R2) · staggered starts (R4) · pre-reboot `.reviving` cleared before any resume (R5) · marker consumed exactly once, idempotent (R1+R6) · panes structurally excluded = R3 (no marker → untouched; panes never mark).

## Phase E — Flip, docs, receipt (the closing phase) ✅ EXECUTED

> Closed 2026-08-10: AUTOROTATE default 0->1 (A0 fixtures rewritten red-first), hooks-index +
> config-inventory + CHANGELOG + memory updated, FULL gate `success 35 / 0`,
> `check_convergence` rc=0, `mesh-test: 114 ok, 0 fail`. Receipt:
> `docs/development/reviews/2026-08-10-plan-1-quota-health-review.md`.

**Files:** `~/.claude/bin/claude-sound.sh` (AUTOROTATE default flip) · `docs/workstation/hooks-index.md` · `docs/workstation/claude-configuration-inventory.md` · `CHANGELOG.md` · `docs/LESSONS_LEARNT.md` (entry or `none`) · `docs/development/reviews/2026-08-10-plan-1-quota-health-review.md` (receipt) · memory files.

**Steps:**
1. Flip `CLAUDE_SOUND_AUTOROTATE` default `0→1` in sound.sh (the operator's condition is now met: rotation is health-aware); keep `=0` as the documented escape hatch; harness A0 fixture updated red-first (asserts the NEW default rotates only-with-healthy-sibling; explicit `=0` still suppresses) — A0 is MODIFIED, not added: the total stays `mesh-test: 90 ok, 0 fail`.
2. Docs: hooks-index StopFailure row (health-aware rotation ON, reset-clock waits, sweep row for the new @reboot entry + SessionStart drift-check row); config-inventory (new files, crontab lines, wall-state.json, fixture count); CHANGELOG one entry; memory: append one line each via python (the established pattern): `~/.claude/projects/-opt-fabrik/memory/feedback_commit_push_backup_discipline.md` gains `- SHIPPED 2026-08-10: quota-health live (reset-clock revival + health-aware rotation default-ON + re-capture + reboot sweep; plan 2026-08-10-plan-1)`; `project_claude_max_quota_burn.md` gains the same one-liner referencing the new automatic behavior.
3. `python scripts/enforcement/check_doc_sync.py` + `python scripts/enforcement/check_hooks_index.py` green.
4. `/fabrik-docs-review` for the touched docs — run to its truthful fixed point.
5. FULL gate: `python scripts/final_gate.py --check --json` → `"status":"success"` + `python scripts/enforcement/check_convergence.py` green. (Green is necessary, not sufficient — the Evidence below is the proof.)
6. **/fabrik-review on the whole-plan surface — BLOCKING, coverage-adjudicated exit** — the receipt file embeds the verbatim gate JSON + per-phase verdicts.
7. DR backup + commit + push; plan `Status:` flip to EXECUTED is the executor's.

**Behavior Contract:** default-on rotation switches ONLY with a healthy sibling (A0-new) · explicit `=0` preserves wait-only · docs rows match shipped behavior (checked by hooks-index gate).

## File Scope (owned paths)

- docs/development/plans/2026-08-10-plan-1-quota-health.md
- docs/development/reviews/2026-08-10-plan-1-quota-health-review.md
- scripts/sysadmin/claude_rotate.py
- tests/test_claude_rotate_capture.py
- .claude/hooks/session_orient.py
- tests/test_session_orient_hook.py
- docs/workstation/hooks-index.md
- docs/workstation/claude-configuration-inventory.md

Box surfaces (out-of-repo, DR-versioned — outside the repo lock, listed for the executor's awareness):
`~/.claude/bin/claude-quota.py` (new) · `claude-sound.sh` · `claude-selfwatch.sh` · `claude-autoresume.sh` ·
`claude-mesh-test.sh` · `claude-reboot-sweep.sh` (new) · `~/.claude/settings.json` (one hook entry) ·
`~/.claude/.claude-manager/wall-state.json` (new state) · crontab (2 lines).
(Governance files CHANGELOG/INDEX/docs-README/FEATURES + LESSONS_LEARNT stay outside File Scope per the shared-append rule.)

## Evidence

**Phase A/B (mesh insertion points — fresh greps 2026-08-10 ~07:4x):**
- `~/.claude/bin/claude-sound.sh:145` (`rate_limit|authentication_failed|invalid_grant)` — the rotation gate arm) and `:164` (the 2a spawn-gate class list) — re-greped after the sibling shift; anchors are the PATTERNS, not the numbers.
- `~/.claude/bin/claude-selfwatch.sh:36-38` (`rate_limit) bo=90 … sleep "${MESH_BACKOFF_OVERRIDE:-$bo}"`); `~/.claude/bin/claude-autoresume.sh:41,:78` (same pair).
- Harness summary print at `claude-mesh-test.sh:473` (exit-check at :474 — fixtures insert before :473); 71 fixtures green this session (independently re-run by the plan-review grounder, same output):
```
mesh-test: 71 ok, 0 fail
```
**Phase C (rotate seam):**
- `scripts/sysadmin/claude_rotate.py:658-685` (`main()` dispatch: `--list`/`--switch`/`--next` — the exact place `--capture-current`/`--drift-check` slot in); `:151` `_active_account()` (token-match → marker → org, PURE read); `:203` `_secure_write` (0600, direct-write — NOT atomic alone; capture wraps it in tmp+`os.replace` per `_activate_snapshot:278-279`); `:277` BACKUP_CREDS; `:284` ACTIVE_MARKER write.
**Phase A parse sources (spec-inherited, independently re-verified twice):**
- CLI binary: `hook_event_name:"StopFailure",error:s,error_details:e.errorDetails,…` + `resetsAt=Math.round(Number(o));if(t)n.rateLimitType=t` + the 6-member `rateLimitType` enum (spec External-deps table, two inspections).
- Tap: `statusline-tap.js` `resetsAt:l(n.resets_at)` → `rateLimits.{fiveHour,sevenDay}`; live keys present:
```
/rateLimits/fiveHour = None
/rateLimits/sevenDay = None
```
**Phase D:**
- `.claude/hooks/session_orient.py:105-106` (`arm_line = ""` + the `CLAUDE_MESH_HEADLESS` gate — the marker block lands adjacent, same env vocabulary); orient tests currently 14 green.
- `~/.claude/settings.json:11` (`"SessionStart": [` — the drift-check hook entry's insertion list).

## Self-audit

- (a) Coverage: agreed items → phases: parse/wall-state→A; switch-or-schedule+announce→B; re-capture→C; sweep→D; AUTOROTATE flip+docs→E; lowest-usedPercent→A (`--healthy-sibling`); cost-decoupling→no phase (recorded non-goal). No gaps found.
- (b) Cross-phase interfaces: B consumes exactly A's four CLI names/outputs (single-integer stdout for `--wait-seconds`; dir-name stdout for `--healthy-sibling`); D consumes the decider's existing `--check` verdicts and the NO_REVIVE/HEADLESS env names already shipped in autoresume; C touches only additive `main()` arms (existing `--switch`/`--next` asserted-unchanged by a test). Names verified against the fresh greps above.
- Grounding passes: spec inherited (4-pass converged); this plan added fresh line-number greps for every insertion point + the rotate-seam read; environment preflight: python3/bash/crontab/pytest/ruff all present in WSL (used this session); no new system toolchain.
- Not yet a fixed point: `/fabrik-plan-review` owes the independent convergence round.

## Residual unknowns

- RESOLVED (spec): parse-ladder precedence; bounds per type; `.reviving` touch contract; sweep eligibility.
- ACCEPTED RESIDUAL (Phase C, review 2026-08-10): when a refreshed live token matches no
  snapshot, identity falls back to the `.active-account` marker — and a legitimate refresh is
  indistinguishable from an out-of-band `claude auth login` as a DIFFERENT account. Refusing
  marker-resolved captures would block the primary use case, so capture proceeds and the `.prev`
  rolling backup is the one-generation recovery path. Revisit if the CLI ever exposes an account
  identifier inside the credential blob.
- OPEN (named, self-service): exact `error_details` text per wall type — Phase A ships the payload-capture line (class+details only) and the regex is tuned from the first live wall; until then the structured source + 90s fallback carry. — statusline staleness: Phase A probes at build (Q-fixtures include a stale-entry case); wall-state self-expiry bounds it. — the overage delivery channel: conservative pin per spec; payload capture resolves it.
- No open item blocks execution start; none requires the operator.
