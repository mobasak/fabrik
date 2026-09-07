# Relief wake — when the fleet-quota hold lifts, every armed session is woken and told where it left off

Status: DRAFT
Profile: small
**Owner:** fleet
**Date:** 2026-09-07
**Operator dispatch:** "when the quota comes back, agent which stops due to it, should know and restart working where they have left, so if you need to do below do so."

## What we already agreed

- **Goal (operator, verbatim):** "fleet quota restored but i dont see any agents woken up and working" → "when the quota comes back, agent which stops due to it, should know and restart working where they have left".
- **Measured cause (2026-09-07 09:45):** the hold's LIFT has no waker. The tick's relief path only unlinks the stamp (`scripts/sysadmin/claude_rotate.py:4595` and `:4605`); the only pane waker is the self-watch, which fires on DEATH markers (`~/.claude/bin/claude-selfwatch.sh:38-41`); a session that obeyed the hold ended its turn and is idle, not dead. Census: 1 of 9 live Claude panes held a `selfwatch.lock`; five `authentication_failed` markers from ~05:45 sat unconsumed.
- **Chosen mechanism (D-177):** at the stamp unlink the tick writes a `hold_lifted <epoch>` marker for every sid whose self-watch is ARMED (a held `selfwatch.lock`), the self-watch gains a `hold_lifted` class that prints a RESUME line naming where the session left off, and the hold's own instruction text tells a held session to ARM the self-watch (Monitor is allowed under the hold — `.claude/hooks/quota_stop.py:52`). `TaskStop` joins the hold's allow-list so a held session can stop its own native subagent.
- **Rejected (D-177):** a Stop-hook cause that BLOCKS a held turn until the lock is held — the hold already yields the Stop hook (D-158) because blocking a held turn only burns quota; a session that cannot arm would be trapped. Rejected too: waking unarmed panes by any other channel — none exists (VS Code panes take input only from harness-native wakers).
- **Out of this plan (filed):** the hold's other allow-list gaps (quoted git args, `-G`, `%(trailers)`, `$'…'`) — infra's hook contract, mail `01M1WD26H60V7S5XBCKVKH2TB7`; the self-watch's arming coverage beyond the nudge (8 of 9 panes ignored the per-prompt check) is a discipline gap measured, not a mechanism this plan can force.
- **Source of truth for the self-watch:** `~/.claude/bin/claude-selfwatch.sh` exists ONLY there (`scripts/dr_claude_backup.sh:13`, mirrored to the DR store by its line 91, cron `45 3 * * *` + `@reboot`). Edits land in place, are proven by `~/.claude/bin/claude-mesh-test.sh` (158 fixtures, sandboxed HOME + lock dir), and are mirrored the same day by running `scripts/dr_claude_backup.sh`.
- **Twins:** `scripts/sysadmin/claude_rotate.py` and `scripts/aro-wake/claude_rotate.py` stay byte-identical (`cp` + `cmp`).

Branch: **RICH** — goal and approach are pinned by the operator's words and this morning's measurement; no brainstorm.

## Intake Inventory

| I# | Item (anchored) | Disposition | Where |
|---|---|---|---|
| I1 | "fleet quota restored but i dont see any agents woken up" | IN | Phase A (the wake signal) |
| I2 | "agent which stops due to it, should know … where they have left" | IN | Phase B (the RESUME line names the run record's blocked reason + the thread anchors) |
| I3 | "we dont want to waste tokens there if they hit a cap" (subagents under the hold; TaskStop denied, measured) | IN | Phase C (`TaskStop` allowed under the hold) |
| I4 | 8 of 9 panes unarmed — a wake reaches only armed sessions | IN (the nudge) / OUT-OF-SCOPE (forcing it) | Phase C (hold text orders the arm); rejected option recorded in D-177 |
| I5 | the hold denies quoted git args, `-G`, `%(trailers)` (measured under the hold) | OUT-OF-SCOPE | infra's hook contract — mail `01M1WD26H60V7S5XBCKVKH2TB7` |
| I6 | "why did nobody wake" needs a denominator next time | IN | Phase A (the `hold-lifted` ledger row with counts) |

Intake: 6 items — 5 IN, 1 OUT-OF-SCOPE (named above), 0 ASK.

## Context Ledger

| Source | What binds | Grounded ref |
|---|---|---|
| `.windsurf/rules/core/10-python.md` (MATCHED) | env via `os.getenv`, no grouped env sets; ruff `B`/`S` rule-sets | `10-python.md:288` |
| `.windsurf/rules/core/45-testing-strategy.md` (MATCHED) | one test per behaviour, watched-fail-first, no in-memory substitute for a backing service | `45-testing-strategy.md:19,21,171` |
| `.windsurf/rules/core/35-security-auth.md` (FLOOR) | zero secrets in code; the marker carries a class + epoch, never a token | `35-security-auth.md:266` |
| `.windsurf/rules/core/30-ops.md` (FLOOR) | share-nothing processes; fail fast on a missing tool | `30-ops.md:469,502` |
| `.windsurf/rules/core/self-healing.md` (AVAILABLE, matches) | every self-healing step emits a visible signal (a counter/log row) | `self-healing.md:75` |
| `agents-fabrik.md` § MANDATORY | fabrik-lib checked; no ports, no compose, no VPS — box-local | `agents-fabrik.md:350-360` |
| fabrik-lib (`/opt/fabrik-lib/README.md`) | `alerting/` = fire-and-forget Telegram alerts (already used by the tick's advisory); no module wakes a pane — the self-watch IS the box's waker, so this plan EXTENDS it rather than building a new one. fabrik-lib checked — no vendorable waker exists. | `README.md` rows `alerting/`, `watchdog/` |
| `docs/workstation/hooks-index.md` rows 17/102/106/108/112 | the mesh's contracts: the arm order, the mechanical armed check, the marker classes, the hold, the death family | `hooks-index.md:17,102,106,108,112` |
| `scripts/sysadmin/selfwatch_check.py` | the ONE armed decider (`_armed`: `/proc/locks` positive-only, then a `LOCK_SH\|LOCK_NB` probe) — the tick mirrors it, never a pgrep | `selfwatch_check.py:42-83` |
| `.claude/hooks/quota_stop.py` (fleet-synced) | the hold's allow-list (`_READ_TOOLS`, `Monitor` in, `TaskStop` out) and instruction text (`_reason`) | `quota_stop.py:44-64,541-550` |

## CONSTRAINTS DIGEST

| Pack | Rule (verbatim) | file:line | Applies to |
|---|---|---|---|
| core/35-security-auth | "config via env vars only (`os.getenv("KEY", "default")`); **ZERO secrets/constants in code**" | `.windsurf/rules/core/35-security-auth.md:266` | the lock dir + marker paths come from `CLAUDE_SOUND_LOCKDIR` / uid, never a literal box path |
| core/10-python | "**BANNED: grouped/named env config sets.** 12F is explicit — *"env vars are granular controls…"*" | `.windsurf/rules/core/10-python.md:288` | knobs stay granular (`MESH_POLL`, `MESH_JITTER_MAX`, `ROTATE_STATE_DIR`) |
| core/45-testing-strategy | "every ticket enumerates its distinct **user-observable behaviors / acceptance criteria** and tests **each one**" | `.windsurf/rules/core/45-testing-strategy.md:19` | the Behavior Contract below, one grader per row |
| core/45-testing-strategy | "a non-trivial behavior's test proves something only if it has been SEEN RED" | `.windsurf/rules/core/45-testing-strategy.md:21` | every grader red-on-revert before its phase commits |
| core/45-testing-strategy | "**BANNED in tests:** … Any in-memory substitute for a real backing service" | `.windsurf/rules/core/45-testing-strategy.md:171-175` | the mesh fixture runs the REAL script under a sandbox HOME + lock dir (the harness's shape), no stub of `flock` |
| core/30-ops | "**Processes are share-nothing:** any state shared across requests MUST go to Redis" | `.windsurf/rules/core/30-ops.md:469` | unconstrained here (no request state) — the marker is the mesh's existing file protocol, the ledger its existing JSONL |
| core/30-ops | "Startup validation — fail fast if a required tool is missing" | `.windsurf/rules/core/30-ops.md:502` | the tick's wake helper fails OPEN (a missing lock dir wakes nobody and says so in the ledger row) — the tick must never crash on the mesh |
| core/self-healing | "Every ladder step MUST emit a counter AND a `structlog.info()` … row carrying the resource name + reason" | `.windsurf/rules/core/self-healing.md:75` | the `hold-lifted` ledger row (`woken`, `armed`, `reason`) + one tick log line |

## Global Constraints

- Box-local, one user: the lock dir is `${CLAUDE_SOUND_LOCKDIR:-/tmp/claude-sound-locks-$(id -u)}` (`claude-selfwatch.sh:18`, `selfwatch_check.py:42-43`); the tick runs as the same user (cron) so it sees the same dir.
- The marker file protocol is FIXED by the mesh: `<lockdir>/<safe-sid>.errparked` holding `<class> <epoch>` (`claude-selfwatch.sh:20,39-41`); `safe` = `tr -c 'A-Za-z0-9_-' '_' | head -c 64` (`:19`), mirrored by `selfwatch_check._safe` (`:32`). A new class rides the same file — never a second file the watch does not read.
- Never overwrite an existing `.errparked`: a real death record outranks a wake; the tick skips a sid that already carries one.
- Armed = the lock is HELD (`selfwatch_check.py:12-13`); a lock file without a holder is a dead watch and gets no marker.
- The tick fails OPEN on the mesh: any exception in the wake helper is caught, counted in the ledger row, and never aborts the tick.
- Twins byte-identical; the self-watch edited in place + mirrored by `scripts/dr_claude_backup.sh` the same day; every hook edit is fleet-synced by the post-commit governance-sync (verify md5 in three project copies).
- 12-Factor non-negotiables inherited verbatim: logs to stdout only (XI — the tick already prints; no logfile); no daemonizing/PID files (VIII — the self-watch is a Monitor child, not a daemon); config = granular env vars (III); no backing-service substitutes in tests (X); releases immutable (V); migrations never from startup (XII — n/a); no sticky sessions (VI — n/a); workers requeue on SIGTERM (IX — n/a); pinned binaries (II — `flock`, `curl` are util-linux/curl already on the box, probed by the harness).

## Phases

### Phase A — the wake signal in the tick (`scripts/sysadmin/claude_rotate.py` + twin)

**Files:** `scripts/sysadmin/claude_rotate.py` (`_fleet_active_wall_advisory` at `:4566`, both unlink sites `:4595` + `:4605`; new helpers `_selfwatch_lock_dir()`, `_armed_sids()`, `_wake_held_sessions(now, reason)`), `scripts/aro-wake/claude_rotate.py` (cp + cmp), `tests/test_claude_rotate_v2.py` (unit graders), `tests/test_claude_fleet.py` (the tick-level grader beside `test_fleet_exhaustion_advisory_fires_once_then_rearms_on_relief` at `:1321`).

**Interfaces — Produces:** `_wake_held_sessions(now: float, reason: str) -> dict` returning `{"armed": int, "woken": int, "skipped_death": int, "errors": int}`; a ledger row `{"event": "hold-lifted", "ts": now, "reason": "relief"|"dwell", **counts}` via `_ledger_append` (`:2151`); a marker `<lockdir>/<safe>.errparked` = `hold_lifted <int(now)>\n` per armed sid. **Consumes:** nothing new.

Steps:
1. **Highest-risk test FIRST (red):** in `tests/test_claude_rotate_v2.py` add `test_the_lift_wakes_only_armed_sids_and_never_overwrites_a_death` — a tmp lock dir (`monkeypatch.setenv("CLAUDE_SOUND_LOCKDIR", …)`) with three lock files: `a.selfwatch.lock` HELD (the test holds `fcntl.flock(fd, LOCK_EX|LOCK_NB)` on it for the test's life — the exact shape the watch uses at `claude-selfwatch.sh:25-29`), `b.selfwatch.lock` unheld, `c.selfwatch.lock` held but `c.errparked` already present (`server_error 1`). Assert: `a.errparked` is written as `hold_lifted <epoch>`, `b` gets none, `c.errparked` still reads `server_error 1`, the return is `{"armed": 2, "woken": 1, "skipped_death": 1, "errors": 0}`, and the ledger holds one `hold-lifted` row. Run: `.venv/bin/python -m pytest tests/test_claude_rotate_v2.py -q -k lift_wakes` → expected `1 failed` (AttributeError: no `_wake_held_sessions`).
2. Implement the three helpers next to `_fleet_exhaustion_stamp` (`:3935`): `_selfwatch_lock_dir()` = `Path(os.environ.get("CLAUDE_SOUND_LOCKDIR") or f"/tmp/claude-sound-locks-{os.getuid()}")`; `_armed_sids()` iterates `*.selfwatch.lock`, probes each with `fcntl.flock(fd, LOCK_SH|LOCK_NB)` on an `O_RDONLY` fd (held → `BlockingIOError` → armed; mirror of `selfwatch_check._armed` `:65-83`, including the `/proc/locks` positive-only fast path — vendor the two functions verbatim, cite the source in a comment; never `pgrep`); `_wake_held_sessions(now, reason)` writes the marker for each armed sid whose `.errparked` does not exist, appends the ledger row, prints one line `tick: hold lifted (<reason>) — woke N of M armed self-watches`, and wraps everything in `try/except OSError` counting `errors`.
3. Wire both unlink sites: `if stamp.exists(): stamp.unlink(...); _wake_held_sessions(now, "relief")` at `:4595` and `"dwell"` at `:4605` — the wake fires ONLY on a real transition (stamp present → absent), which is the dedup: the tick runs every 5 min and an absent stamp wakes nobody.
4. Tick-level grader in `tests/test_claude_fleet.py`: extend the fixture pattern of `:1321` — set the stamp, hold one lock in the tmp lock dir, run `cr._cmd_tick()` through relief (a sibling regains headroom, as `:1345-1349` does) and assert the marker + the ledger row; then a second tick with no stamp asserts NO second marker (dedup). Expected red before step 3, green after.
5. `cp scripts/sysadmin/claude_rotate.py scripts/aro-wake/claude_rotate.py && cmp` both → identical; `ruff check` + `ruff format` both.
6. Gate: `.venv/bin/python -m pytest tests/test_claude_rotate_v2.py tests/test_claude_fleet.py -q` → expected `N passed, 0 failed` (today's baseline: 122 + 195).
7. `python scripts/enforcement/check_doc_sync.py`; doc rows: `docs/workstation/claude-account-rotation.md` (the hold section: "on relief the tick wakes every armed self-watch") + CHANGELOG entry.
8. `/fabrik-review-scoped` on Phase A's surface (Profile: small) — fix in-run to a raised-zero no-op.
9. Commit `-- scripts/sysadmin/claude_rotate.py scripts/aro-wake/claude_rotate.py tests/test_claude_rotate_v2.py tests/test_claude_fleet.py docs/workstation/claude-account-rotation.md` (+ CHANGELOG via the hot-file guard) with provenance trailers; push.

### Phase B — the `hold_lifted` class in the self-watch (`~/.claude/bin/claude-selfwatch.sh`, outside the repo)

**Files:** `~/.claude/bin/claude-selfwatch.sh` (class dispatch `:43-53`, wake line `:110`), `~/.claude/bin/claude-mesh-test.sh` (new fixture W10 beside W6 at `:298-308`), `docs/workstation/hooks-index.md` (rows 106/112: the marker class table gains `hold_lifted`), `scripts/dr_claude_backup.sh` run (mirror), `CHANGELOG.md`.

**Interfaces — Consumes:** the marker `hold_lifted <epoch>` from Phase A. **Produces:** one stdout line per lift: `RESUME: the fleet-quota hold LIFTED at <HH:MM> (the rotation tick saw relief). If you stopped for it, resume the run you closed BLOCKED — its record's reason and \`python3 scripts/thread_anchor.py line\` carry where you left off; if you are mid-task, ignore this line — this self-watch STAYS ARMED (do NOT re-arm).`

Steps:
1. **Red first — fixture W10** in `claude-mesh-test.sh` after W7 (`:316`): arm `SW timeout 30 bash "$SBHOME/.claude/bin/claude-selfwatch.sh" sW10 > "$T/w10.out" &`, sleep 2, write `printf 'hold_lifted %s\n' "$(date +%s)" > "$LOCKS/sW10.errparked"`, wait ≤10 s for consumption, assert `grep -c '^RESUME: the fleet-quota hold LIFTED' "$T/w10.out"` = 1 AND the marker is consumed AND a second `server_error` marker still wakes (`grep -c '^RESUME:'` = 2 — the watch stays armed, W6's shape). Run `bash ~/.claude/bin/claude-mesh-test.sh` → expected `FAIL: W10 …` (the old script prints the generic "died on hold_lifted" line, the grep for the LIFTED text is 0).
2. Implement: in the class dispatch (`:52-53`) add `hold_lifted) bo=0 ;;`; keep the connectivity gate (`:93-98`) and the post-wait re-check (`:107`); branch the wake text on `$err` = `hold_lifted` to the Produces line above (formatting the epoch with `date -d @"$death" +%H:%M`); every other class keeps the existing line verbatim.
3. Re-run the harness → expected `all green` (the harness's own exit 0 and its PASS count = previous + 1); run the existing W1–W9 unchanged.
4. Mirror: `scripts/dr_claude_backup.sh` → expected a DR-store commit carrying `claude/bin/claude-selfwatch.sh` + `claude-mesh-test.sh` (read its log line).
5. Docs: `docs/workstation/hooks-index.md` rows 106 (class table: `hold_lifted` = a lift, not a death — no error voice, no Telegram) and 112 (the self-watch consumes it like a death record); CHANGELOG.
6. Gate: `bash ~/.claude/bin/claude-mesh-test.sh` exit 0; `python scripts/enforcement/check_doc_sync.py`.
7. `/fabrik-review-scoped` on Phase B's surface (the shell diff + the doc rows; the script is outside the repo — paste its `diff` into the review's record) — fix in-run.
8. Commit the repo side `-- docs/workstation/hooks-index.md` (+ CHANGELOG guarded); push. The self-watch itself is mirrored by step 4 (the DR store is its git).

### Phase C — the hold nudges the arm and allows `TaskStop` (`.claude/hooks/quota_stop.py`, fleet-synced)

**Files:** `.claude/hooks/quota_stop.py` (`_READ_TOOLS` `:44-57`, `_reason` `:541-550`), `tests/test_quota_stop_hook.py` (31 tests; the `_reason` grader at `:511`), `docs/workstation/hooks-index.md` row 108, `templates/governance/CLAUDE.md` + `CLAUDE.md` (the ORIENT (a) line already orders the arm — add one clause: "the hold's lift wakes ONLY an armed watch"), CHANGELOG, DECISIONS (D-177 minted with this plan).

**Interfaces — Consumes:** nothing. **Produces:** the hold's denial text ends with: `ARM the self-watch NOW if it is not armed — Monitor(persistent: true, command: "bash ~/.claude/bin/claude-selfwatch.sh <sid>", description: "resume-mesh self-watch") is allowed under the hold — the lift wakes ONLY an armed watch.`; `TaskStop` in `_READ_TOOLS`.

Steps:
1. **Red first:** `tests/test_quota_stop_hook.py` — `test_taskstop_is_allowed_under_the_hold` (`hook.decide("TaskStop", {}, stamp_exists=True, …)` → `("allow", "")`, mirroring the existing Monitor case) and `test_the_hold_text_orders_the_self_watch_arm` (`"ARM the self-watch" in hook._reason("Bash")` and the literal `claude-selfwatch.sh` in it). Run `-k "taskstop or self_watch_arm"` → expected `2 failed`.
2. Implement both (one set entry, one sentence). Mirror named: `TaskStop` can end a background Monitor — including the self-watch itself — under the hold; acceptable: a session that stops its own watch loses only its own wake, and `TaskStop` cannot change the tree or spend quota.
3. Green: `.venv/bin/python -m pytest tests/test_quota_stop_hook.py tests/test_stop_hook_quota_hold_exemption.py -q` → expected all passed (31 + existing).
4. Docs: hooks-index row 108 (the allow-list + the arm nudge), the two governance files' ORIENT (a) clause, CHANGELOG; D-177 row present in `docs/DECISIONS.md` (minted at plan time, staged with the plan).
5. Post-commit: verify the fleet sync (`md5sum .claude/hooks/quota_stop.py` equals `/opt/tryton-crm`, `/opt/transdoc`, `/opt/youtube` copies); mail infra (`mail.py send --to fabrik --to-agent infra --kind finding`) naming the hook change and the commit — their beat, the hub's committed code.
6. Gate: `python scripts/final_gate.py --check --json` → `"status": "success"` (pytest is the hub's deliberate skip; the touched suites ran in steps 3 and Phase A.6) AND `python scripts/enforcement/check_convergence.py` exit 0. A green gate is necessary, not sufficient — the Evidence below is the proof.
7. `/fabrik-docs-review` over the docs this plan touched (hooks-index rows 106/108/112, claude-account-rotation.md, the two governance ORIENT lines).
8. **The ONE heavy round (Profile: small):** `/fabrik-review` over the whole-plan diff (Phases A–C) — pool trio + native finder, one receipt at `docs/development/reviews/2026-09-07-plan-1-relief-wake-review.md`; fix in-run to a no-op.
9. Commit `-- .claude/hooks/quota_stop.py tests/test_quota_stop_hook.py docs/workstation/hooks-index.md templates/governance/CLAUDE.md CLAUDE.md` (+ CHANGELOG/DECISIONS guarded); push.

## Execution Discipline (binding on /fabrik-execute-plan)

- **Review floor:** every phase, on its own diff, runs `/fabrik-review-scoped` to a raised-zero no-op BEFORE its commit; the whole-plan diff gets ONE full `/fabrik-review` at Finish (Phase C.8). No phase commits on a first-pass green.
- **Dispatch policy:** Profile: small — the orchestrator codes each phase INLINE in the main checkout (D-169/D-170: pool coders OFF for code). Pool-default stays for the gradeable READ-ONLY fan-out: the closing readers (`fanout("review", …, mode="read_only")`, ×3, `set_quality` back-filled per unit) plus one native finder for the authority pass. `NO-POOL` is NOT in force.
- **Parallelism + merge:** Phases A and B are independent (A writes markers, B reads them; the fixture in B writes its own marker) and MAY be built in either order but are committed in order A → B → C; the closing readers fan out in parallel and are merged/deduped by the orchestrator in the Finish review's Disposition Ledger.

## Behavior Contract

- **Given** the fleet-exhausted stamp exists and this tick sees relief, **When** the tick unlinks it, **Then** every sid with a HELD `selfwatch.lock` and no existing `.errparked` gets `hold_lifted <epoch>` and a `hold-lifted` ledger row records `armed`/`woken`/`skipped_death`/`errors` (`scripts/sysadmin/claude_rotate.py:4595`).
- **Given** a lock file whose holder is gone, **When** the lift fires, **Then** that sid gets NO marker (a dead watch cannot wake a pane) (`scripts/sysadmin/selfwatch_check.py:65-83`).
- **Given** a sid already carrying a death record, **When** the lift fires, **Then** the record is untouched (a death outranks a wake) (`scripts/sysadmin/claude_rotate.py:4595`).
- **Given** no stamp exists at tick time, **When** the tick runs, **Then** no marker is written (dedup by transition; the transient-dwell unlink obeys the same rule) (`scripts/sysadmin/claude_rotate.py:4605`).
- **Given** an armed self-watch, **When** `hold_lifted <epoch>` lands in its marker, **Then** it prints exactly one `RESUME: the fleet-quota hold LIFTED …` line naming the run record + thread anchors, consumes the marker, and keeps watching (a later death still wakes) (`~/.claude/bin/claude-selfwatch.sh:52,110`).
- **Given** the hold stands, **When** a session calls `TaskStop`, **Then** it is allowed (`.claude/hooks/quota_stop.py:44-57`).
- **Given** the hold denies a tool, **When** its reason is rendered, **Then** the text orders the self-watch arm with the Monitor call and says the lift wakes only an armed watch (`.claude/hooks/quota_stop.py:541-550`).

## File Scope (owned paths)

- scripts/sysadmin/claude_rotate.py
- scripts/aro-wake/claude_rotate.py
- tests/test_claude_rotate_v2.py
- tests/test_claude_fleet.py
- .claude/hooks/quota_stop.py
- tests/test_quota_stop_hook.py
- docs/workstation/hooks-index.md
- docs/workstation/claude-account-rotation.md
- templates/governance/CLAUDE.md
- CLAUDE.md
- docs/development/reviews/2026-09-07-plan-1-relief-wake-review.md

(Outside the repo, owned by this plan's execution: `~/.claude/bin/claude-selfwatch.sh`, `~/.claude/bin/claude-mesh-test.sh` — mirrored by `scripts/dr_claude_backup.sh`. Governance files CHANGELOG/DECISIONS are orchestrator-applied shared-append surfaces, outside the lock by rule.)

## Coverage Checklist

```text
$ python scripts/review_rubric.py --changed scripts/sysadmin/claude_rotate.py .claude/hooks/quota_stop.py scripts/sysadmin/selfwatch_check.py tests/test_claude_rotate_v2.py
## FLOOR — always injected, regardless of glob (spec L3)
### core/35-security-auth.md
### core/25-data-postgres.md
### core/30-ops.md
### 12-FACTOR (all twelve axes)
## MATCHED — packs whose globs hit the changed paths
### core/10-python.md  (hit: .claude/hooks/quota_stop.py, scripts/sysadmin/claude_rotate.py, scripts/sysadmin/selfwatch_check.py)
### core/45-testing-strategy.md  (hit: tests/test_claude_rotate_v2.py)
```

| Class | Verdict | Evidence (what/where hunted) |
|---|---|---|
| `core/35-security-auth.md` | UNCHECKED | — |
| `core/25-data-postgres.md` | UNCHECKED | — |
| `core/30-ops.md` | UNCHECKED | — |
| `core/10-python.md` | UNCHECKED | — |
| `core/45-testing-strategy.md` | UNCHECKED | — |
| fail-open vs fail-closed on every gate/guard | UNCHECKED | — |
| cost/quota/limit accounting edges (unknown≠0, per-call vs batch) | UNCHECKED | — |
| boundary/sentinel/prefix collisions | UNCHECKED | — |
| behavior-without-a-test | UNCHECKED | — |

(Filled by `/fabrik-plan-review`'s convergence round; every row CLEAN/FIXED/REFUTED before the CONVERGED flip.)

## Evidence

### Phase A
- `scripts/sysadmin/claude_rotate.py:4595` and `:4605` — the two unlink sites; `:2151` `_ledger_append`; `:3935` `_fleet_exhaustion_stamp`; `:4711` the tick's call.
```text
$ sed -n 4595p scripts/sysadmin/claude_rotate.py
        stamp.unlink(missing_ok=True)  # relief arrived (flip/reset) → re-arm for the next wall
$ sed -n 4605p scripts/sysadmin/claude_rotate.py
        stamp.unlink(missing_ok=True)  # transient dwell hold, not exhaustion → re-arm
$ grep -rnE 'selfwatch|wake|resume' scripts/sysadmin/claude_rotate.py | wc -l
0
```
- The armed census this morning (the denominator): `ls /tmp/claude-sound-locks-1000/*.selfwatch.lock | wc -l` → 1; `flock -n` held for exactly that one (this session); nine live Claude panes (`pgrep -af claude` minus helpers).

### Phase B
- `~/.claude/bin/claude-selfwatch.sh:18-30` (lock dir, marker path, the duplicate-arm flock), `:38-53` (marker poll, class dispatch), `:93-110` (connectivity gate, post-wait re-check, consume, RESUME line).
```text
$ sed -n 52,53p ~/.claude/bin/claude-selfwatch.sh
  case "$err" in  # per-class remedy wait (rotation for account classes, cool-off for load)
    rate_limit) bo=90 ;; overloaded) bo=60 ;; server_error) bo=30 ;; *) bo=0 ;;
$ sed -n 110p ~/.claude/bin/claude-selfwatch.sh
  printf 'RESUME: this session died on %s; the cause has been healed; resume the interrupted task — this self-watch STAYS ARMED (standing watch: do NOT re-arm; a duplicate arm exits at once)\n' "$err"
$ grep -n 'SRC=' ~/.claude/bin/claude-mesh-test.sh
10:SRC="$HOME/.claude/bin"
$ sed -n 13p scripts/dr_claude_backup.sh; sed -n 91p scripts/dr_claude_backup.sh
#   ~/.claude/bin/**                        hand-built hook helpers (claude-sound.sh, claude-stop-decider.py) — exist ONLY here
  mirror "$CLAUDE_DIR/bin"                         "claude/bin"
```

### Phase C
- `.claude/hooks/quota_stop.py:44-57` `_READ_TOOLS` (Monitor allowed, TaskStop absent), `:541-550` `_reason`; `tests/test_quota_stop_hook.py:511` the existing `_reason` grader.
```text
$ sed -n 44,57p .claude/hooks/quota_stop.py | tr -d ' \n'
_READ_TOOLS={"Read","Grep","Glob","LS","ToolSearch","AskUserQuestion","TaskOutput","Monitor","ListMcpResourcesTool","ReadMcpResourceTool","ReadMcpResourceDirTool","ListAgents",}
```
- Measured under the hold on 2026-09-07 01:24–01:40: `TaskStop` returned the hold's denial (the native pass `a493302ecc82f2e19` could not be stopped); `Monitor` was NOT tried under the hold — the allow-list says it passes; Phase C.1 asserts it stays allowed (`hook.decide("Monitor", …)` is already covered by the suite's Monitor case — re-verify, do not assume).

## Self-audit

- **Grounding passes run:** the tick's relief path (read at `:4556-4612`), the self-watch script (whole, 111 lines), `selfwatch_check.py` (the decider), `quota_stop.py` (allow-list + reason), the decider's marker clear paths (`claude-stop-decider.py:904-924, 1052`), the mesh harness (`:14-44, :244-316`), the DR mirror (`dr_claude_backup.sh:13,91` + crontab lines 110-111), fabrik-lib README (no waker module), `hooks-index.md` rows 17/102/106/108/112, the ledger of this morning's episode.
- **(a) Coverage of "What we already agreed":** the wake signal → Phase A; "know where they left off" → Phase B's RESUME text; TaskStop → Phase C; the arm nudge → Phase C; the rejected Stop-hook cause → D-177 (no phase); the self-watch source of truth + mirror → Phase B.4; twins → Phase A.5; the denominator → Phase A's ledger row. No gap.
- **(b) Cross-phase signatures:** Phase A writes `hold_lifted <epoch>` (space-separated, class first — the exact shape `:39-40` parses with `awk '{print $1}'`/`$2`); Phase B dispatches on the literal `hold_lifted`; Phase C's text names the exact Monitor call the ORIENT line uses. Consistent.
- **Mirror check per fix:** a marker to a mid-turn (not held) session → one ignorable line (the text says so); a lock whose holder died between enumeration and write → the probe is taken immediately before the write, a microsecond race at worst, and the marker then waits for the next arm (the arm consumes pre-arm history at `:34` — so a stale `hold_lifted` never fires into a fresh arm); `TaskStop` under the hold can stop the watch itself → the session's own loss only.
- **Fixed point:** not yet claimed — `/fabrik-plan-review` converges this DRAFT.

## Residual unknowns

- **Resolved:** whether `Monitor` is allowed under the hold — yes (`quota_stop.py:52`); where the self-watch's source lives — `~/.claude/bin` only, DR-mirrored; whether the marker path is the same for every repo — yes (per-uid tmp dir, cwd-agnostic); whether headless sessions are affected — no (they never arm; `claude-autoresume.sh` revives them).
- **Open, self-service:** the exact PASS count of the mesh harness today (Phase B.3 records it from the run — the harness prints it); the tmp lock dir's behaviour across a reboot (tmpfs — locks and markers vanish together, so a lift straddling a reboot wakes nobody: the reboot sweep is the waker there; recorded, not solved here).
- **Open, filed:** the hold's remaining allow-list gaps (quoted args, `-G`, `%(trailers)`) — `01M1WD26H60V7S5XBCKVKH2TB7`, infra.
