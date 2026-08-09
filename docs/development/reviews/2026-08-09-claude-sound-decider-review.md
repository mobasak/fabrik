# Review — claude-sound stop-decider (workstation notification system)

Surface: `~/.claude/bin/claude-stop-decider.py` md5 `a3093c28c4` · `~/.claude/bin/claude-sound.sh`
md5 `9d2ae9fa5b` (files live OUTSIDE git — md5s are the anchor). First review of this surface.
Built this session (Fable) replacing the timing-heuristic implementation: state-based park
detection — ring only at true final rest (no blocking hook, no in-flight subagent, no pending
background task), distinct immediate sound for errors.

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
| logic errors / boundary (tail windows, reversed-walk, ternary) | UNCHECKED | |
| wake-source completeness (hooks, shell tasks, subagents, Monitor, ScheduleWakeup, SendMessage) | UNCHECKED | |
| fail-open vs fail-closed (each guard's failure direction) | UNCHECKED | |
| cost/limit accounting edges (stale bounds, tail-bytes caps, unknown≠0) | UNCHECKED | |
| boundary/sentinel/prefix collisions (marker false-positives, quoted markers) | UNCHECKED | |
| concurrency & races (lock supersede, parallel Stops, log writes) | UNCHECKED | |
| shell safety (quoting, injection via payload, detach semantics, pipe buffering) | UNCHECKED | |
| resource cleanup (locks, log growth, zombie verifiers) | UNCHECKED | |
| performance (full-file scans ×2 per Stop on 200MB+ transcripts) | UNCHECKED | |
| test quality (does the self-test prove its claims; red-on-revert) | UNCHECKED | |
| behavior-without-a-test | UNCHECKED | |

## Pass Ledger

```
Pass 1a — MY authoritative pass (design-suspect grounding, all live-evidence) | found: 5 | fixed: 5
  F1 degenerate ternary in last_message_state (both arms identical — dead code hiding the
     stop_reason=None decision) → explicit branches + documented killed-mid-stream policy
  F2 "unknown" tail (attachment burst > 256KB) fell straight to parked → widen-once to 4MB
     before concluding
  F3 CONFIRMED gap: Monitor uses toolUseResult.taskId (+timeoutMs/persistent), NOT
     backgroundTaskId (live-grounded in -opt-web-ecommerce-factory) → pending Monitors were
     invisible = false RING; now matched with timeoutMs-derived deadline
  F4 CONFIRMED gap: ScheduleWakeup (/loop) parks BY DESIGN and the timer re-wakes it
     (live-grounded in -opt-brand-identiy-creator: real delaySeconds=900 dispatch) → new
     busy-wakeup check from last dispatch ts+delaySeconds (+120s slack; stop:true ends it)
  F5 CONFIRMED bug: completions delivered mid-turn land as attachment/queue-operation
     entries, not type=user (live-grounded: task b257ofyuw's completion existed ONLY in
     those rows) → user-only filter left it pending forever = false SILENCE; filter now
     excludes only `assistant`, matches the raw line (payloads live outside message.content)
  Self-test grown 11 → 19 fixtures, all green; real-session verdicts re-grounded (brand:
  busy-task ✓, seo/trade: busy-subagent ✓, me: busy-subagent = the review's own two finders ✓)
Pass 1b — finder A (decider logic/boundaries) + finder B (shell/integration/wake-completeness),
  native fabrik-reviewer ×2, partitioned classes, rubric-armed | IN FLIGHT
  (pool skipped: fanout returned empty on every dispatch this session — persistent
   deepseek empty-completion, documented in prior reviews; native finders substituted)
```

## Disposition Ledger

(one entry per raised candidate — FIXED or REFUTED with proof; no silent passes)
