# StopFailure Resume Mesh — design spec

Status: CONVERGED (spec-review 2026-08-09; operator-approved 2026-08-09) · Spec author: Fable · Scope: workstation (`~/.claude/bin` + docs); no fleet-synced surface changes

## Goal

When a Claude Code session's turn dies on a `StopFailure` API error, the session should resume
**without the operator** whenever the cause permits, and ring **only** when a human is genuinely
required. Operator requirement (verbatim intent, 2026-08-09): *"if I send a continue/proceed command
the agent can start working from where it left"* — automate exactly that continue, safely.

This extends the shipped sound-decider system (state-based park detection, `~/.claude/bin/
claude-stop-decider.py` + `claude-sound.sh`, reviewed CLEAN-CONVERGED 2026-08-09) — it does not
replace any of it.

## Grounded facts the design rests on (all verified 2026-08-09)

| Fact | Evidence |
|---|---|
| `StopFailure` `error` is a closed 10-value enum | shipped binary v2.1.219 zod schema + official hooks doc matcher table (dual-grounded) |
| A StopFailure hook **cannot** continue the agent — its output is discarded | binary: `zpt` executor calls `SM({...})` fire-and-forget; contrast `Stop`'s `VEe` generator that consumes decisions |
| An error-dead transcript resumes with context intact via `claude -p --resume` | live test: session died on `model_not_found`, revived with valid model, recalled codeword ZEBRA-42 |
| The failure pipeline (hook → decider turn_dead mode → ring) works headless unmodified | same live test: `arg=failure err=model_not_found` logged, rang at 16:20:57 |
| Session crons fire "while the REPL is idle" but each fire costs an API turn | CronCreate schema; rejected as standing heartbeat — quota is the binding constraint (③) |
| A `persistent: true` Monitor costs zero while silent; each stdout line wakes the session | Monitor schema; /loop ScheduleWakeup revival observed live (brand) |
| Turn-death ≠ agent-death: pending wakers (task/subagent/wakeup) revive and retry | built + E2E-proven in the decider's turn_dead work |
| Display-layer connection drops are NOT deaths (turn persisted, normal Stop) | live specimen 16:22: "Connection closed mid-response" banner, transcript complete `end_turn`, no StopFailure fired |
| `https://api.anthropic.com` answers any unauthenticated request with an HTTP status (connectivity probe: any response incl. 4xx = up; zero tokens/auth) | live probe 2026-08-09: bare GET → 404 in ~0.11s; `/v1/messages` → 405 |

## Rejected alternatives

- **Cron heartbeat in every session** — native and simple, but ~144 API turns/day/session at 10-min
  cadence; wrong on a quota-bound box.
- **Headless-twin revival for interactive panes** (`claude --resume -p` against a pane session) —
  forks the work into an invisible second writer; the pane stays dead. Disqualified.
- **StopFailure hook returning a continue decision** — impossible; output discarded (binary-proven).

## Architecture — three layers

```
death (StopFailure) ──► Layer 1: heal the cause (all sessions, automatic)
                            │
              ┌─────────────┴──────────────┐
              ▼                            ▼
   Layer 2a: headless reviver     Layer 2b: pane self-watch (Monitor)
   (opt-in env, claude --resume)  (opt-in per long run, wakes in place)
              │                            │
              └─────────────┬──────────────┘
                            ▼
        Layer 3: ring + escalate (only when truly dead with no reviver)
```

### Layer 1 — heal the cause at the moment of death (every session)

**Component:** extension of the existing failure branch in `claude-sound.sh` (or the decider's
turn_dead path — implementation plan decides the seam).

**Behavior by error class:**

| Error | Action at death |
|---|---|
| `rate_limit`, `authentication_failed` | spawn detached `python3 /opt/fabrik/scripts/sysadmin/claude_rotate.py --next` + credential re-sync (the keepalive's existing auth-401 remedy, reused — never reimplemented) |
| `overloaded`, `server_error` | nothing — time heals |
| `max_output_tokens`, `invalid_request`, `unknown` | nothing to heal — resumable as-is |
| `oauth_org_not_allowed`, `billing_error`, `model_not_found` | nothing — human-only by design |

**Marker:** the failure branch writes `/tmp/claude-sound-locks-<uid>/<safe-sess>.errparked`
(error class + timestamp) at **delegation time — on every StopFailure**, before the decider runs.
This is deliberate: the armed self-watch is itself a pending Monitor that keeps the decider silent,
so a ring-gated marker would never appear (deadlock — caught in spec self-review). The marker is a
*death record*, not a *truly-dead verdict*; the ring remains the truly-dead signal. Cleared by the
next Stop-path decider run for the session (successful revival) and by the existing >1h lock prune.
If another waker revives the session before the self-watch fires, the watch's later RESUME line is
redundant but harmless — its instruction is idempotent ("if interrupted, resume; if already
resumed, continue").

**Guarantee delivered:** any subsequent "continue" — human or automated — succeeds first try for
every healable class.

**Rotation-storm guard:** rotation trigger is rate-limited (marker: at most one triggered rotation
per N minutes box-wide, N≈10) so a burst of dying sessions can't thrash accounts.

**Amendment (operator adjudication, first live firing):** the rotation trigger is **OPT-IN
(`CLAUDE_SOUND_AUTOROTATE=1`), default OFF**. The blind version rotated while two of three accounts
were weekly-walled and the active one only needed its known 5-hour window reset waited out — every
open interactive window got invalidated for nothing. It stays off until the health-aware design
ships: consult per-account wall state AND limit TYPE before switching; a knowable reset time means
WAIT, never rotate.

### Layer 2a — headless auto-reviver (opt-in)

**Component:** small detached helper spawned by the failure branch **only when**
`CLAUDE_SOUND_AUTORESUME=1` is set in the dying session's environment (supervisors export it;
default OFF so pipelines with their own retry logic are never double-retried).

**Behavior:** per-class backoff (`server_error` 30s · `overloaded` 60s · `rate_limit` after the
Layer-1 rotation completes · `max_output_tokens`/`invalid_request`/`unknown` immediate) →
**connectivity gate** → `claude -p --resume <session_id> "continue"` → attempt counter in the lock
dir, **cap 2 counted attempts** → on final failure fall through to Layer 3. Human-only classes
never enter the reviver.

**Connectivity gate (network-change hiccups — sustained outages wait, they don't burn):** before
each resume attempt, probe `curl -s -o /dev/null --max-time 5 https://api.anthropic.com` — ANY
HTTP response (4xx included) = network up (live-verified 2026-08-09: 404 in ~0.11s; zero tokens,
zero auth; a DNS failure/timeout = down). While DOWN: poll every 30s WITHOUT consuming an attempt
(TLS handshake only), up to a **30-min offline ceiling from death**; past the ceiling → Layer 3
ring (a half-hour outage is human-worthy). This makes brief blips (Wi-Fi switch, VPN toggle, WSL
DNS flip) self-healing and long outages patient-then-loud, instead of burning both attempts while
offline. Note: Layer-1 rotation also needs network — if it failed offline, the gated resume simply
fails once online, consumes an attempt, and the cap/ring path holds.

**Revival-storm guard (the operator's real pattern: MANY full-throttle sessions dying together on a
VPN/Wi-Fi/tether switch, then the network returning for all of them at once):** after the gate
passes, each reviver sleeps a random **0–45s jitter**, then passes a box-wide **serialized-start
mutex: resume starts are ≥15s apart** (mkdir mutex with 60s stale steal). *(Implementation
amendment, review-adjudicated: the originally-specified K=2 held-slot design was disproven — a slot
held across a full resumed run collides with any stale-steal timeout and dismantles the guard under
the very storm it exists for; serialized starts deliver the same staggered-trickle guarantee without
held state.)* N simultaneous deaths revive as a staggered trickle, never as an N-wide burst that
itself triggers a `rate_limit` cascade. The 2b self-watch applies the same jitter before printing
its RESUME line.
Sibling guard: the rotation-storm limiter (Layer 1) already serializes the account side; this
serializes the turn side.

**WSL note (deliberate):** the probe runs inside WSL with the agents' own resolver — it measures
the network the agents actually experience. If a VPN leaves WSL DNS persistently broken (the
documented `WSL2-DNS-FIX` class), the probe correctly stays down and the ceiling rings — that is a
box fault to fix at the OS layer, not something revival should paper over.

**Proven path:** the ZEBRA-42 test is this flow end-to-end.

### Layer 2b — interactive pane self-watch (opt-in per long run)

**Component:** a watch template (`~/.claude/bin/claude-selfwatch.sh <session_id>`) + one standing
sentence in the workstation run-discipline docs: *long autonomous runs arm the self-watch.*

**Behavior:** the agent arms `Monitor(persistent: true, command: claude-selfwatch.sh <sid>)` at the
start of a long run. The script loops silently watching this session's `errparked` marker; when it
appears: wait the per-class remedy time (read from the marker), then for the network-shaped classes
(`server_error`/`unknown`) ALSO wait for the same connectivity probe to pass (poll 30s, same
30-min offline ceiling — waking an agent into a dead network just kills the next turn too) → print
exactly one line —
`RESUME: this session died on <error>; the cause has been healed; resume the interrupted task` —
→ exit. The printed line wakes the pane through the native notification queue; the agent resumes
**in place, in the visible pane**. The consumed monitor means a second death has no waker → rings.
Past the offline ceiling the watch exits WITHOUT printing — the decider's existing 60-min
task-stale bound then rings exactly once (interlock, no new code).

**Cost:** zero API tokens while silent; one sleep-loop shell process per armed run.

**Interlock with the decider (no changes needed):** error death with the watch pending → decider
sees a pending Monitor → silent (revival coming). Watch older than the decider's 60-min task-stale
bound → decider rings once AND the watch still revives — one informative ring, then self-heal.

### Layer 3 — ring + escalate (mostly exists)

Second-death rings are already built (waker-consumed logic). Addition: when a StopFailure park
actually **rings** (truly dead — keyed on the ring, NOT on the `errparked` marker, which records
every death including self-revived ones) for a session whose cwd is under `/opt/`, also fire the
existing `APPRISE_SEND` Telegram path (lives in the sysadmin scripts — e.g.
`/opt/fabrik/scripts/sysadmin/proactive-check.sh` — not in `claude-sound.sh`; vendor the call
pattern from there) — dead long-runs reach the operator away from the desk.
Rate-limited (one message per session per 30 min).

## What stays human-only (deliberate)

`model_not_found` (model choice is not the machine's call), `billing_error`,
`oauth_org_not_allowed` (account/billing decisions), and `authentication_failed` **after** rotation
has been tried (all accounts exhausted = nothing left to rotate to). These ring with their
error-family sound, exactly as today.

## Testing strategy (Behavior Contract for the implementation plan)

1. **Layer 1:** fixture-fire each error class through `claude-sound.sh failure` → assert the
   rotation trigger fires for `rate_limit`/`authentication_failed` only (mock `claude_rotate` via
   PATH shim); assert `errparked` is written on EVERY StopFailure delegation (busy or parked) and
   cleared by the next Stop-path decider run; assert the Telegram escalation keys on ringing parks
   only.
2. **Layer 2a:** repeat the ZEBRA-42 flow with the reviver instead of a manual resume: kill a
   headless session (`model_not_found` is NOT revivable — use a synthetic `server_error` via a
   crafted payload through the real script), assert `claude -p --resume` is invoked with backoff
   and capped at 2. **Connectivity gate:** with the probe shimmed DOWN (PATH curl shim), assert no
   attempt is consumed and the 30-min ceiling falls through to ring; shim UP mid-wait → assert the
   resume fires and exactly one attempt is counted. **Storm guard:** launch 5 revivers against a
   shimmed-up probe → assert all 5 resumes complete with serialized starts (no two attempt starts
   share a second — the mutex-critical-section starts log is the deterministic witness). Watched-fail-first where practical.
3. **Layer 2b:** arm the self-watch on a scratch session, write its `errparked` marker by hand,
   assert exactly one RESUME line is printed and the process exits; live-arm in a real long run at
   the next opportunity (the delivery-after-error residual's confirmation).
4. **Regression:** full decider `--self-test` (34 fixtures) stays green; the review's E2E battery
   (busy-silent / parked-ring / dup-park / hook-wait / compact) re-run.

## Residual risks (accepted, named)

- **Monitor-wake delivery into an error-dead pane** is extrapolated (three proven facts, §Grounded)
  but not yet observed end-to-end in a pane; first real quota-hit with a watch armed confirms.
  Failure mode if wrong: today's behavior (ring) — no regression.
- **`claude -p --resume` against a session later reopened interactively** — the reviver only ever
  targets sessions flagged headless by their supervisor (env opt-in), so the two-writers hazard is
  excluded by construction, not by detection.
- **Rotation side-effects:** `--next` switches the box-wide active account; the existing
  single-refresh-owner + sync machinery already governs this (same path the keepalive uses).

## Build inventory (for the plan)

- `claude-sound.sh` failure branch: +Layer-1 dispatch (~15 lines) + 2a spawn gate (~10 lines)
- `claude-stop-decider.py`: clear `errparked` on successful Stop-path runs (~4 lines) — plus fixtures
  (the WRITE lives in the failure branch, per the marker semantics above)
- `~/.claude/bin/claude-autoresume.sh` (new, ~55 lines): backoff + connectivity gate (probe loop,
  30-min ceiling) + jitter + serialized-start mutex (≥15s spacing) + resume + cap — Layer 2a
- `~/.claude/bin/claude-selfwatch.sh` (new, ~30 lines): marker watch template + the same
  connectivity gate for network-shaped classes + wake jitter — Layer 2b
- Rotation rate-limit marker (~5 lines, in the Layer-1 dispatch)
- Telegram escalation hook-in (~10 lines, reuses APPRISE_SEND)
- Docs: workstation run-discipline sentence (arm the self-watch) + inventory rows; DR-backup list
  already covers `~/.claude/bin/**`
