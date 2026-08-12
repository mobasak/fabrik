# Plan — Connection-failure auto-resume (the sibling class the mid-stream plan missed)

Status: EXECUTED 2026-08-12 (decider DR-versioned; suite 82→94 red-first, mesh 114/114, DR
20260812T211418Z, gate 46/0 fresh. Whole-plan review:
docs/development/reviews/2026-08-12-plan-3-connection-failure-resume-review.md — pool+native closer
CLEAN, verified against 5094 live records)
Date: 2026-08-12
Owner: infra session (operator-approved this turn: "havent you implemented this?" + both
recommended scope answers — whole connection-failure family + fold in the arming check)

## What we already agreed

- **The gap (grounded from the LIVE incident this session):** `/opt/iterative_image_editor`
  session 35204643, 2026-08-12 15:41:05Z. Record shape (real, read from the transcript):
  `{type:"system", subtype:"api_error", level:"error", error:{formatted:"Unable to connect to
  API (ENOTIMP)", connection:{code:"ENOTIMP", message:"getaddrinfo ENOTIMP api.anthropic.com"}},
  retryAttempt:10, maxRetries:10, source:"request_retry"}`. The CLI exhausted its own 10 retries
  and gave up — a resumable death (network heals → "proceed" works), same revival pattern as the
  mid-stream family.
- **Why neither net caught it:** the mid-stream detector (`_tail_is_stalled`) walks for
  `type=assistant` + top-level `isApiErrorMessage=true`; this is `type=system` +
  `subtype=api_error` with NO `message.role`, so the walk falls straight through its user/assistant
  branches to the "keep walking back" line and skips it. The StopFailure loud-layer classes
  (auth/rate_limit/server_error/overloaded) do not include a retries-exhausted connection failure
  either. Both nets miss it by construction.
- **Operator decision 1 — SCOPE = the whole connection-failure family**, keyed STRUCTURALLY not by
  a string allowlist that rots: a `type=system`/`subtype=api_error` record whose
  `error.connection.code` is present AND `retryAttempt == maxRetries` (retries exhausted) is a
  resumable death. Covers ENOTIMP/ECONNRESET/ECONNREFUSED/ETIMEDOUT/ENOTFOUND and any sibling —
  the exhausted-retries signal is the invariant, the specific code is not.
- **Operator decision 2 — fold in the ARMING gap:** auto-continue cannot fire the pane unless the
  session armed its `claude-selfwatch.sh` Monitor. This session shows NO recent self-watch arm in
  `~/.claude/sweep.log` and no `.errparked` was written. Investigate WHY iterative_image_editor's
  session didn't arm (the mandate is in the synced `session_orient.py` SessionStart hook, but only
  fires if the session actually calls `Monitor`), record the finding + a lesson. This is a
  read-only diagnosis in THIS plan — no fix to the arming mechanism unless the probe reveals a
  one-line decider-adjacent cause (else it becomes its own recorded follow-up).
- **Recovery discrimination stays intact:** if REAL operator input or a recovered assistant record
  follows the api_error (the session was attended / it continued), the walk must still return False
  FIRST — a connection failure that the operator already resumed is NOT a death. Only when the
  api_error is the effective newest meaningful record (sidecar machine-appends —
  last-prompt/ai-title/mode/file-history-snapshot, which have no role and are already walked past —
  are the only things after it) is it a death.
- **Rejected:** a string allowlist of error codes (rots — structural retries-exhausted key instead);
  coupling to rotation (the mid-stream plan's constraint holds); editing any box surface other than
  the decider.

## CONSTRAINTS DIGEST (rule-grounding gate)

| rule | pack:line | implication here |
|---|---|---|
| watched-fail-first for the risky behavior | core/45-testing-strategy.md § Behavior Contract | every new detection row + the recovery-discrimination guard is a red-first `--self-test` fixture |
| production sound surface — diagnose read-only, edit only as the deliberate feature | memory `feedback_dont_touch_the_sound_system` + mid-stream plan | ONLY `~/.claude/bin/claude-stop-decider.py` is edited; sound/selfwatch/autoresume READ-ONLY |
| no rotation coupling | memory `project_manual_rotation_decision` | zero switch/rotate code in the delta |
| box surfaces are DR-versioned, not git | mid-stream plan File-Scope precedent | the decider edit is DR-backed (step 6), not committed; only the repo-side docs are git |

## Context Ledger

| Source | What binds | Grounded ref |
|---|---|---|
| `2026-08-11-plan-2-stalled-midstream-resume.md` (archived) | the exact machinery this extends: `_tail_is_stalled` walk, `stalled-api-error` verdict, `api_error_stalled` `.errparked` write, the 256KB→8MB widen | archived plan + `claude-stop-decider.py` |
| `~/.claude/bin/claude-stop-decider.py:187-266` | `_tail_is_stalled` — the walk with user(:216)/assistant(:242) branches; a no-role `type=system` record falls to :254 "keep walking back" (THE gap) | read this session |
| `~/.claude/bin/claude-stop-decider.py:243,253` | assistant branch keys on `isApiErrorMessage` + `_API_ERROR_STALL_PATTERNS` — the sibling shape the new branch mirrors | read this session |
| `~/.claude/bin/claude-stop-decider.py:966,1039` | `stalled_death = verdict == "stalled-api-error"` → the `api_error_stalled <epoch>` `.errparked` write in `_run_hook_inner` — the revival path the new class reuses UNCHANGED | read this session |
| the live incident transcript | the real record shape (fixtures copy it verbatim) | `~/.claude/projects/-opt-iterative-image-editor/35204643-*.jsonl:36370` |
| `~/.claude/sweep.log` + `session_orient.py:102-117` | the self-watch arming mandate + this session's missing arm — the arming-gap probe target | read this session |

## Global Constraints

- ONLY `~/.claude/bin/claude-stop-decider.py` is edited (box surface, DR-versioned). Sound/selfwatch/
  autoresume scripts are READ-ONLY. No rotation/switch code. Subagent probes keep
  `CLAUDE_SOUND_HEADLESS=1`; never fire the sound system to test. `/usr/bin/grep` for sound-debug.log
  (the interactive grep is a shadowed ugrep wrapper). Token bytes never printed. DR backup after the
  decider change. The repo-side commit carries only the hooks-index/CHANGELOG doc rows + this plan +
  the review artifact (the decider itself is DR-versioned, per the mid-stream precedent).

## Phase A — detect the connection-failure death, route it into the existing revival, prove it — ✅ EXECUTED 2026-08-12

Interfaces — Produces: a new no-role branch in `_tail_is_stalled` (`type=system`/`subtype=api_error`
+ `error.connection.code` present + `retryAttempt == maxRetries` → death, returning True) that
mirrors the assistant `isApiErrorMessage` branch; the SAME `stalled-api-error` verdict + the SAME
`api_error_stalled` `.errparked` write consume it (no new verdict, no new revival layer). Consumes:
the existing `_tail_is_stalled` walk + recovery-discrimination + widen logic.

1. **Precedence probe (self-service, read-only) — truncate at the DEATH MOMENT.** The live
   transcript has since grown past the incident (the operator manually resumed: line 36371 is real
   `user` input immediately after the api_error at 36370, then real turns to line 36507), so the
   FULL transcript correctly reads non-death — a recovered session. That is the wrong baseline. The
   red baseline is the transcript AS IT WAS when the Stop hook fired: `head -36370 <incident.jsonl>`
   (the api_error as the literal tail, nothing after). Run the decider on THAT truncated copy in a
   sandbox (`CLAUDE_SOUND_HEADLESS=1`, sandboxed LOCK_DIR) → the connection-failure record is walked
   past (no-role `type=system` → falls to `last_message_state`) → a non-death verdict = the RED the
   fix flips. Separately, run it on the FULL current transcript → non-death (recovered), which is
   the LIVE proof that recovery-discrimination (connfail4) is load-bearing, not theoretical: the
   real operator "proceed" at 36371 must, and does, suppress the death.
2. **Arming-gap probe (self-service, read-only):** `/usr/bin/grep` `~/.claude/sweep.log` +
   sound-debug.log for session 35204643's self-watch arm; read `session_orient.py:102-117`'s arming
   mandate. Record the finding (armed-but-consumed vs never-armed vs headless-skip) in the plan's
   Evidence + a LESSONS_LEARNT entry. If the cause is a one-line decider-adjacent bug, fix it in
   scope; else record it as a named follow-up (the decision the operator folded in).
3. **TDD — the risky behavior first, watched RED (fixtures in the decider `--self-test` suite):**
   add fixtures BEFORE the code, each watched fail:
   - `connfail1` — a `type=system`/`subtype=api_error`/`code=ENOTIMP`/`retryAttempt==maxRetries`
     tail, no waiters → `stalled-api-error` (death). RED now (walked past).
   - `connfail2` — same record but `retryAttempt < maxRetries` (retries NOT exhausted, still
     retrying) → NOT a death (busy/parked, the CLI may still recover on its own).
   - `connfail3` — the family: ECONNRESET / ETIMEDOUT / ECONNREFUSED / ENOTFOUND each exhausted →
     all `stalled-api-error` (structural key, not a string allowlist).
   - `connfail4` — recovery discrimination: an api_error record with REAL operator input AFTER it →
     False (attended — not a death); with only sidecar machine-appends (no-role
     last-prompt/ai-title/mode/file-history-snapshot) after it → death.
   - `connfail5` — malformed guards: `error` non-dict, `connection` non-dict, `retryAttempt`/
     `maxRetries` non-int/absent → never raise, never a false death (the `X or default`
     truthy-wrong-type class the mid-stream plan closed — reuse `isinstance` guards).
   Watch every fixture RED for the right reason (wrong verdict or, for the guards, a crash).
4. **Implement the no-role branch in `_tail_is_stalled`** (the ONLY edited surface), placed BEFORE
   the `# queue-operations / attachments / system rows — keep walking back` line so the record is
   classified instead of skipped: `if e.get("type") == "system" and e.get("subtype") ==
   "api_error":` → read `err = e.get("error"); err = err if isinstance(err, dict) else {}`;
   `conn = err.get("connection"); conn = conn if isinstance(conn, dict) else {}`; a death iff
   `conn.get("code")` is a non-empty str AND `_ints_equal_exhausted(e.get("retryAttempt"),
   e.get("maxRetries"))` (a helper: both int-coercible AND equal AND ≥1). Return True on a death;
   `continue` (keep walking) otherwise — a non-exhausted api_error is not yet dead. The existing
   `stalled-api-error` verdict + `.errparked` write need NO change (verify by reading :966/:1039,
   not editing).
5. **End-to-end wake proof (read-only on the consumers):** with a throwaway session id, drive the
   decider on a `connfail1`-shaped transcript through `_run_hook_inner` (sandboxed LOCK_DIR,
   `CLAUDE_SOUND_HEADLESS=1`) → assert the `api_error_stalled <epoch>` `.errparked` record is
   written (the armed self-watch's contract), the `(stalled api error)`-class log line appears, and
   the selfwatch awk contract still matches — same E2E shape as the mid-stream plan's row-4 proof.
6. **Fixture-harness sweep + DR:** `env -u CLAUDE_SOUND_AUTOROTATE bash ~/.claude/bin/claude-mesh-test.sh`
   (env-clean) → 0 fail; then `bash /opt/fabrik/scripts/dr_claude_backup.sh` → commit+push line
   observed (the decider is DR-versioned, not git).
7. **Docs (Doc Sync Matrix):** `docs/workstation/hooks-index.md` Stop row extended to name the
   connection-failure class alongside the mid-stream family (one clause); `CHANGELOG.md` entry.
8. `python scripts/enforcement/check_doc_sync.py` clean for the phase's triggers.
9. **`/fabrik-review` on the changed surface — BLOCKING, to a coverage-adjudicated exit** (pool
   finders + a native non-author closer; the decider diff + fixtures + doc rows).
10. FULL gate `python scripts/final_gate.py --check --json` → success + `check_convergence.py` green.
11. Commit the repo-side files (explicit paths + `Agent-Name: infra` trailers); the box-side decider
    edit is DR-versioned by step 6, not git-committed (mid-stream precedent).

**Behavior Contract (Phase A):** the five fixture rows in step 3 — risk-ordered, the
recovery-discrimination row (connfail4) and the retries-not-exhausted row (connfail2) load-bearing
(the class this mesh bites us with is false-death/false-ring, so the no-false-positive rows are the
guard, not decoration).

## Execution notes (subagents + parallelism)

Single-phase: the decider edit + fixtures are ONE serial unit (same file). Pool-default applies to
the REVIEW layer (step 9's finder fan-out — pool finders that record + a native non-author closer).
The grounding fan-out was done at plan time (the incident transcript + decider seams above).

## File Scope (owned paths)

- docs/development/plans/2026-08-12-plan-3-connection-failure-resume.md
- docs/development/reviews/2026-08-12-plan-3-connection-failure-resume-review.md
- docs/workstation/hooks-index.md

Box surfaces (out-of-repo, DR-versioned — outside the plan lock, listed for the executor's
awareness, mid-stream precedent): `~/.claude/bin/claude-stop-decider.py` (the ONLY edited box
surface) · `claude-mesh-test.sh` (run) · `claude-sound.sh` / `claude-selfwatch.sh` /
`claude-autoresume.sh` (READ-ONLY).

## Evidence

- The real record shape (fixtures copy it verbatim):
```
$ sed -n '36370p' ~/.claude/projects/-opt-iterative-image-editor/35204643-*.jsonl
{"type":"system","subtype":"api_error","level":"error","error":{"message":"Connection error.",
 "formatted":"Unable to connect to API (ENOTIMP)","connection":{"code":"ENOTIMP",
 "message":"getaddrinfo ENOTIMP api.anthropic.com","isSSLError":false},...},
 "retryInMs":37424,"retryAttempt":10,"maxRetries":10,"source":"request_retry",...}
```
- The gap in the walk (a no-role `type=system` record falls to the keep-walking line, unclassified):
```
$ grep -n "keep walking back" ~/.claude/bin/claude-stop-decider.py
254:                # queue-operations / attachments / system rows — keep walking back
```
- The revival path reused UNCHANGED:
```
$ grep -n "stalled_death = verdict\|api_error_stalled " ~/.claude/bin/claude-stop-decider.py
966:    stalled_death = verdict == "stalled-api-error"
1039:                f"api_error_stalled {int(time.time())}\n"
```
- The arming-gap signal (drives step 2 + the lesson):
```
$ grep -c "35204643" ~/.claude/sweep.log   → 0   (no self-watch arm recorded for the session)
```
- The death moment vs. the recovered present (why step 1 truncates at 36370):
```
$ wc -l < ~/.claude/projects/-opt-iterative-image-editor/35204643-*.jsonl   → 36507
$ sed -n '36370,36371p' … | jq -r '.type + " role=" + (.message.role // "none")'
system role=none     ← the api_error (the tail at Stop time)
user role=user       ← the operator's MANUAL proceed (proof recovery-discrimination must fire)
```
The Stop hook fired with 36370 as the tail; the operator then typed 36371, resuming manually — the
exact auto-continue this plan replaces. Red baseline = `head -36370`; recovery proof = the full file.

## Self-audit

- (a) Coverage vs "What we already agreed": family detection → step 3-4 (structural exhausted-retries
  key); recovery discrimination → connfail4; arming-gap diagnosis → step 2 + lesson; existing-revival
  reuse (no new layer) → step 4 verifies :966/:1039 unchanged; fixtures red-first → step 3;
  no-rotation → Global Constraints. No gap.
- (b) Single phase; the one produced name (the new branch's structural predicate) is consumed only
  inside `_tail_is_stalled` + its fixtures — no cross-phase drift.
- Grounding: incident record read (jsonl:36370), decider walk read (:187-266), revival path read
  (:966/:1039), sweep.log probed. Not yet a fixed point — `/fabrik-plan-review` owns convergence.

## Residual unknowns

- OPEN (self-service, resolved at step 1): whether real turns follow the api_error in the incident
  transcript (recovery-discrimination must win there) — the precedence probe settles it before
  coding; either answer is handled by connfail4.
- OPEN (self-service, step 2): the arming-gap root cause (never-armed vs consumed vs headless-skip)
  — the probe classifies it; a decider-adjacent one-liner lands in scope, anything larger is a named
  follow-up (operator-folded decision).
- RESOLVED: the record shape (jsonl:36370), the reused revival path (:966/:1039 unchanged), the
  structural key (retries-exhausted, not a string allowlist).
