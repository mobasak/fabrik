# T03 — run-record events + sid plumbing + lifecycle audit

Depends: T01
Parallel: ⚡ (with T02, T04)
Complexity: native (command_run.py is fleet-synced CORE_SCRIPTS + the Stop hook's 5th cause reads
its records)
## Scope
Lifecycle events from every record mutation. Grounded root cause of the collision: sid resolution falls to `nosession` when `CLAUDE_SESSION_ID` is empty (scripts/command_run.py:60-61); record naming + lock at scripts/command_run.py:85-97.

## Touches
- scripts/command_run.py
- tests/test_command_run.py

## Context Files
- docs/superpowers/specs/2026-08-16-kaizen-closed-loop-v2-design.md
- scripts/command_run.py
- scripts/sysadmin/kaizen_events.py



## Interfaces

Consumes: T01 `emit()`.
Produces:
- Events at every record mutation: `run_open` (command, phases, terminal), `phase` (n, title),
  `round` (findings, classes), `run_close` (verdict: done/blocked + evidence summary hash) —
  emitted AFTER the record `save()` returns and OUTSIDE the record lock, each call wrapped
  (a raising emitter can never abort or corrupt a record mutation — tested by monkeypatching
  emit to raise mid-verb).
- **sid honesty fix for the `nosession` collision** (grounded root cause: Bash-tool shells carry
  empty `CLAUDE_SESSION_ID`, `scripts/command_run.py:60-61`): when the sid resolves to `nosession`,
  the record STILL works as today (no behavior break for the Stop hook) but every emitted event
  carries `sid_source: "none"` — and `command_run.py` gains `--session-from-events` OPTIONAL
  resolution: candidates = ALL session files with ANY event naming this cwd since the run's own start time
  (never a sliding N-minute window — a boundary can hide the second candidate and mis-adopt);
  adopt ONLY when exactly one distinct sid remains over that whole window, else refuse
  (deterministic-join-or-nothing; both branches tested). The collision itself is thereby measurable (events show N distinct cwds mutating
  `nosession.json`) even where it is not yet solvable.
- The record dict gains `closed_by` (`agent` today; `coroner`/`ttl` written by T05) — additive,
  default absent, so existing consumers are untouched — the Stop hook keys on `state == "running"` ONLY (.claude/hooks/final_gate_stop.py:385,801), and `closed_by` is additive.

## Steps

1. TDD: extend `tests/test_command_run.py` — each CLI verb emits its event (tmp events dir);
   `nosession` emission carries `sid_source: "none"`; `--session-from-events` adopts a
   single-candidate sid and REFUSES an ambiguous one; existing record behavior byte-stable
   (the Stop hook contract: the `state` field + `pinned_line` unchanged). RUN RED first.
2. Implement (emission wrapped fail-open; import via the same additive-path fallback as T02 —
   command_run.py is fleet-synced and must degrade to today's behavior where kaizen_events is
   absent).
3. Gate: `uv run pytest tests/test_command_run.py -q` green + a live `start`/`done` cycle in this
   session shows the paired events.

## Behavior Contract

- **Given** a `/fabrik-*` run opened, stepped, rounded, and closed, **When** the record mutates,
  **Then** matching `run_open`/`phase`/`round`/`run_close` events carry the record's command,
  phases, and verdict (scripts/command_run.py).

Docs: none (schema doc rows ride T01; runbook notes ride T09).
Gate: `uv run pytest tests/test_command_run.py -q` + the live cycle smoke.
