# T05 — the coroner: death/revival reconstruction + record closure + hole metric

Depends: T01, T03
Parallel: —
Complexity: complex (pool coder permitted; the record-closure seam and the READ-ONLY sound-system
boundary are reviewed native at acceptance per the D4 floor)
## Scope
Death reconstruction from the mesh's markers + transcript tails per the authority doc (docs/workstation/hooks-index.md:31 — the five mid-stream death texts + the structural api_error key; docs/workstation/hooks-index.md:36 — the .errparked record). Record closure via the load/save API at scripts/command_run.py:129-150. Sound-system files are READ-ONLY, always.

## Touches
- scripts/sysadmin/kaizen_coroner.py
- tests/test_kaizen_coroner.py

## Context Files
- docs/superpowers/specs/2026-08-16-kaizen-closed-loop-v2-design.md
- docs/workstation/hooks-index.md
- scripts/command_run.py
- scripts/sysadmin/kaizen_shrink_audit.py
- scripts/sysadmin/kaizen_events.py



## Interfaces

Consumes: T01 `emit()`; T03's record shape + `closed_by` field; the mesh markers + notify log
(READ-ONLY — the sound system is untouchable); transcript tails under `~/.claude/projects/`.
Produces:
- `kaizen_coroner.sweep(sources) -> CoronerReport` + CLI `--sweep`/`--selftest` — for each session
  with death evidence and no `session_end` event: a reconstructed `death` event (class from the
  marker/tail key; exposure joined from the session's last trusted events, unjoinable fields
  literal `unknown`) appended to THAT session's event file, marked `reconstructed: true`; a
  matching `revival` event where the mesh log shows one.
- Record closure: a record with `state: "running"` attributed to a death gets
  `state: "died"`, `closed_by: "coroner"` — the Stop hook blocks ONLY on
  `state == "running"` (.claude/hooks/final_gate_stop.py:385,801; `done`/`blocked` set
  `state` to the verb, scripts/command_run.py:416 — `died`/`expired` join that vocabulary); a `state: "running"` record past `KAIZEN_RUN_TTL_H` (default 12, matching the
  Stop hook's stale-fail-open horizon) with no death evidence gets `state: "expired"`,
  `closed_by: "ttl"`. Never any other mutation of records.
- The hole metric: `holes = transcripts-with-activity − sessions-with-session_end`, per day,
  reported to T06 as a first-class instrument-health input.

## Steps

1. TDD with BOTH-WAYS fixtures (duplex law): a fixture lock-dir + transcript tail for each death
   class (errparked record; the five mid-stream texts; the structural api_error key at
   retries-exhausted; a still-retrying api_error that must NOT count) + a live-session control
   (busy, no death → untouched). RUN RED first.
2. Implement sweep (stdlib; every marker/transcript read `errors="replace"`; sound-system paths
   opened read-only — no write, no delete, ever).
3. Closure tests: fixture running-state record + death → died/coroner; stale no-death →
   expired/ttl; closed record → no-op; the Stop hook's reading of a coroner-closed record
   verified (only `state == "running"` blocks — .claude/hooks/final_gate_stop.py:385).
4. `--selftest` duplex canary. Gate: `uv run pytest tests/test_kaizen_coroner.py -q` green.

## Behavior Contract

- **Given** a transcript tail carrying the mesh's death keys and no `session_end` event, **When**
  the coroner sweeps, **Then** a reconstructed `death` event exists with joined-or-`unknown`
  exposure fields, the session's run record (if `running`) is closed `verdict: died` stamped
  `closed_by: coroner`, and the session counts in the hole metric
  (scripts/sysadmin/kaizen_coroner.py).
- **Given** a run record still `running` past the TTL with no death evidence, **When** the coroner
  sweeps, **Then** the record closes `verdict: expired` — never left pinning its project.

Docs: coroner section rides T01's schema doc (T09 verifies).
Gate: `uv run pytest tests/test_kaizen_coroner.py -q` && `python3 scripts/sysadmin/kaizen_coroner.py --selftest`
