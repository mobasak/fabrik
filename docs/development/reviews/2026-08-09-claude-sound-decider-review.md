# Review — claude-sound stop-decider (workstation notification system)

Surface: `~/.claude/bin/claude-stop-decider.py` md5 `0892da40cb` · `~/.claude/bin/claude-sound.sh`
md5 `58177657d0` (files live OUTSIDE git — md5s are the anchor). First review of this surface.
Built this session (Fable) replacing the timing-heuristic implementation: state-based park
detection — ring only at true final rest (no blocking hook, no in-flight subagent, no pending
background task, no scheduled wakeup), distinct immediate sound for errors.

**Exit state: CLEAN-CONVERGED** — final round found 0 / fixed 0; every checklist class adjudicated;
27 self-test fixtures green; live E2E ring + silent verdicts verified on the final build (13:17:10).

## Rubric (from `review_rubric.py --changed <2 paths>`)

```
FLOOR: core/35-security-auth · core/25-data-postgres · core/30-ops · 12-FACTOR — injected;
       mostly N/A to a workstation hook script (no web auth, no DB, no deploy). Applicable
       floor slices: fail-open-vs-fail-closed, config-via-env, no-secrets-in-code.
MATCHED: (no .windsurf glob matches — files outside the repo) → reviewed under core/10-python
       discipline + the command's standing recurrence classes.
```

## Coverage Checklist

| Class | Verdict | Evidence |
|---|---|---|
| logic errors / boundary (tail windows, reversed-walk, ternary) | FIXED | F1 ternary, A1 widen-8MB, A4 `or 0.0`; edge fixtures 16b(c/e/g) green |
| wake-source completeness (hooks, shell tasks, subagents, Monitor, ScheduleWakeup, SendMessage) | FIXED | F3 Monitor `taskId`, F4 ScheduleWakeup, F5+A3 delivery types; residuals R1/R2 below (zero observed usage) |
| fail-open vs fail-closed (each guard's failure direction) | FIXED | every failure lands on RING-not-silence: no-transcript→ring, decider-ERROR→ring (A2), decider-MISSING→ring (B2), stale artifacts expire→ring; busy states are the only silences and each is structurally proven |
| cost/limit accounting edges (stale bounds, tail-bytes caps, unknown≠0) | FIXED | ±5s staleness-edge fixtures (16b-g); Monitor deadline `min(timeoutMs/1000+120, TASK_STALE)`; timestampless dispatch EXPIRES (A4 fixture) |
| boundary/sentinel/prefix collisions (marker false-positives, quoted markers) | FIXED | type filters both sides: assistant-quoting fixtures (5, 11c), assistant-toolUseResult fixture (16b-a), tool_result-echo fixture (16b-b) |
| concurrency & races (lock supersede, parallel Stops, log writes) | FIXED | A5: prune + owner-only release + `still_owner` re-check inside grace; residual R4 (no flock — accepted, documented in code) |
| shell safety (quoting, injection via payload, detach semantics, pipe buffering) | CLEAN | payload passed via stdin pipe only (never interpolated into a command); `setsid nohup … &` detach; `jq -r` reads, no `eval`; `printf '%s'` not `echo` |
| resource cleanup (locks, log growth, zombie verifiers) | FIXED | B4 log rotation 5MB→1MB, A5 lock prune >1h, subprocess timeouts 15s, monitor-task bound TASK_STALE_S |
| performance (full-file scans per Stop on 200MB+ transcripts) | FIXED | A6 removed the second full scan (byte-equality suffices — every invalidating transition APPENDS); sweep: largest real transcript decides in ≤0.8s |
| test quality (does the self-test prove its claims; red-on-revert) | FIXED | A7 mutation-survivability pack (27 fixtures): each fix has a fixture that fails if the fix is reverted (type-filter, echo, timestampless, non-dict, oversized, max_tokens, ±edge) |
| behavior-without-a-test | FIXED | C1 closed the last untested behavior (play_done fallback); both paths proven via subprocess mock (dead socket→powershell, healthy→ffplay) + live ring 13:17:10 |

## Pass Ledger

```
Pass 1a — MY authoritative pass (design-suspect grounding, all live-evidence) | found: 5 | fixed: 5
  F1 degenerate ternary in last_message_state (both arms identical — dead code hiding the
     stop_reason=None decision) → explicit branches + documented killed-mid-stream policy
  F2 "unknown" tail (attachment burst > 256KB) fell straight to parked → widen-once before concluding
  F3 CONFIRMED gap: Monitor uses toolUseResult.taskId (+timeoutMs/persistent), NOT
     backgroundTaskId (live-grounded in -opt-web-ecommerce-factory) → pending Monitors were
     invisible = false RING; now matched with timeoutMs-derived deadline
  F4 CONFIRMED gap: ScheduleWakeup (/loop) parks BY DESIGN and the timer re-wakes it
     (live-grounded in -opt-brand-identiy-creator: real delaySeconds=900 dispatch) → new
     busy-wakeup check from last dispatch ts+clamp(delay) (+120s slack; stop:true ends it)
  F5 CONFIRMED bug: completions delivered mid-turn land as attachment/queue-operation
     entries, not type=user (live-grounded: task b257ofyuw's completion existed ONLY in
     those rows) → user-only filter left it pending forever = false SILENCE
Pass 1b — finder B (shell/integration/wake-completeness), native | raised: 11 | fixed: 5 refuted: 2 residual: 4
Pass 1c — finder A (decider logic/boundaries), native | raised: 11 | fixed: 9 accepted: 2
  (pool skipped: fanout returned empty on every dispatch this session — persistent
   deepseek empty-completion, documented in prior reviews; native finders substituted)
Pass 2  — confirming round: fresh full read of BOTH final files | found: 2 | fixed: 2
  C1 CONFIRMED: decider play_done() had the same B1 defect fixed in the shell — ffplay
     exits 0 having played NOTHING on a dead Pulse socket, and `returncode == 0 → return`
     never reached the powershell fallback = lost park signal; also ignored the
     CLAUDE_SOUND_MEDIA/PULSE env overrides the shell honors → precondition-gated
     (is_socket + wav exists) with env overrides, fallback beep otherwise; both paths
     proven via subprocess mock, live ring re-verified
  C2 cosmetic: whitespace-run in pending_wakeup condition → normalized continuation
Pass 3  — quiet pass on the final build | found: 0 | fixed: 0 → EXIT
  self-test 27/27 green · real-session sweep all correct (brand busy-subagent, seo parked,
  trade busy-subagent ×2, me busy-task — the decider caught THIS session's own pending
  monitor, a live true-positive) · E2E: parked→ring 13:17:10, busy→silent, malformed→
  labeled ring · md5 anchors 0892da40cb / 58177657d0 (= this header)
```

## Disposition Ledger

Finder B (shell/integration):
- B1 ffplay exit-0-no-audio masks fallback — **FIXED** (precondition gating in play(); live-reproduced first)
- B2 done-branch had zero observability + no decider-missing fallback — **FIXED** (decider-MISSING ring + "delegated" log line)
- B3 CronCreate interval loops park like /loop but are not detected — **RESIDUAL R1, accepted**: zero CronCreate usage observed across every transcript on this box; failure direction is a false RING (annoyance) not false silence; revisit if crons appear
- B4 unbounded debug log — **FIXED** (5MB→keep-1MB rotation)
- B5 hardcoded MEDIA/PULSE paths — **FIXED** (CLAUDE_SOUND_MEDIA/PULSE env overrides; C1 extended this to the decider)
- B6 "async:true means the 10s timeout kills the decider mid-grace" — **REFUTED**: `async: true` detaches the hook from the timeout budget; live rings arrive at Stop+10–15s (log 13:11:16, 13:17:10), impossible if killed at 10s
- B7 lock files never deleted — **FIXED** (A5 prune + release)
- B8 payload not quoted into decider safely — **REFUTED as raised, hardened anyway**: payload always travels via stdin pipe (`printf '%s' "$PAYLOAD" |`), never a shell argument; no interpolation exists
- B9 "ScheduleWakeup is not a real tool / invented" — **REFUTED**: verbatim dispatch held from -opt-brand-identiy-creator transcript (`delaySeconds: 900`, `prompt: <<autonomous-loop-dynamic>>`)
- B10 SendMessage-to-agent wakes could false-ring — **RESIDUAL R2, accepted**: agent-team continuations deliver as user entries (→ busy-input already) or subagent sidechains (covered); no bare-SendMessage park observed; failure direction = extra ring
- B11 powershell.exe absent on non-WSL — **RESIDUAL R3, accepted**: WSL-only deployment by design (WSLg Pulse socket is the primary path)

Finder A (decider logic):
- A1 oversized final line (543 real >256KB lines, max 3.5MB) reads "flushing" forever = permanent false silence — **FIXED** (unknown/flushing → widen-once to 8MB; fixture 16b-e)
- A2 non-dict JSON / malformed payload → AttributeError → silent death — **FIXED** (isinstance guards + top-level try/except → decider-ERROR ring+log; fixture 16b-d)
- A3 F5's fix over-reached: tool_result echoes (agent Read-ing a log) could false-complete — **FIXED** (completion accepted only from attachment / queue-operation / user-STRING-with-`<task-notification>`; fixture 16b-b)
- A4 `_ts_epoch(e) or now` self-reset staleness on every scan = muted forever — **FIXED** (`or 0.0` → ages out; fixture 16b-c)
- A5 lock hygiene (never released, never pruned) — **FIXED** (owner-only release, >1h prune); no-flock race **accepted, documented in code**: worst outcome is one extra or one stale chime (R4)
- A6 second full decide() scan after grace is redundant — **FIXED** (byte-equality proves the verdict holds: every invalidating transition appends; halves per-Stop cost)
- A7 fixtures don't kill mutations (type filter, echo, edges) — **FIXED** (7-fixture survivability pack)
- A8 malformed payload logged as "no transcript" (dishonest label) — **FIXED** ("(malformed payload)" label; E2E-verified 13:11:06)
- A9 dead `_texts_of` helper — **FIXED** (removed)
- A10 wakeup clamp magic numbers unsourced — **FIXED** (comment cites the tool's published [60,3600] contract; `max(0,…)` display guard)
- A11 empty-string session_id degrades lock naming — **ACCEPTED as-is**: sanitized to `_`, worst case shared lock for malformed payloads which ring immediately anyway

Confirming round:
- C1 play_done ffplay-exit-0 fallback gap + no env overrides — **FIXED** (see Pass 2)
- C2 whitespace cosmetic — **FIXED**
- R5 queue-operation raw-line scan: an OPERATOR-QUEUED paste quoting a live pending `<task-id>` of THIS session would false-complete it — **RESIDUAL, accepted**: ids are session-local + short-lived; requires quoting this session's own live id inside a queued message; failure bounded by TASK_STALE_S (returns to ringing ≤60min)

## Self-audit

- Every fix has a pinning fixture or a live E2E proof; self-test 27/27 green on the final md5.
- Every silence is structurally justified (busy-*), every failure path lands on ring-not-silence.
- Residuals R1–R5 are enumerated with failure DIRECTION stated (all bounded: extra ring or ≤60min-late ring — never permanent silence).
- Surfaces live outside git; the md5 anchors in the header are the verified final state.
