# T01 — The pause marker and the hibernate.py verbs
Appetite: 150

## Scope
Implements spec § Chosen approach L2 (the `mark --deadline` timeline, `paused`, the `status` checks 1-6, `brief --deadline`) and L3 (`woke`'s rule and seed list, `lift`'s caller check), in `scripts/sysadmin/hibernate.py`, plus the marker interface M of the spine. Folds the routed items I2-I5, I9, I11 (the reader half) and I14: `_armed_sids` compares names after `_selfwatch_safe` and treats `NotADirectoryError` as BLOCKS; an outside-`/opt` agent is judged by the same armed test; `brief`'s "Exit 0 means the box slept" is reworded and `tests/test_hibernate.py`'s resume-wake-alone cases at :515, :553, :565 are rewritten for the lift-only rule; `lift` takes `--self`, passes only for the ledger's merge owner (`FABRIK_DECISIONS_PY` seam) and names the plain-shell `lift` as the operator's last resort in its refusal; close times compare `updated_ts`+1 against `floor(paused_at)` (`scripts/command_run.py:2273-2275` writes whole seconds) and seeds are found by globbing `<state>/command-runs/seeds/<safe_sid>*` newer than the mark. DO-NOT: touch the rotation tick, the hooks or any launcher; DO-NOT import `claude_rotate.py` (read the lock dir directly, the same rule `_armed_sids` uses).

Depends: —
Parallel: ⛓️
Complexity: native
Gate: /opt/fabrik/scripts/capped_run.sh -- .venv/bin/python -m pytest tests/test_hibernate.py -q
Docs: docs/reference/hibernate.md (the timeline, the checks, `paused`, `woke`); commands/_sources/hibernate.md (render at merge from master only)

Grounded at: `scripts/sysadmin/hibernate.py:430` (status), `scripts/command_run.py:7740` (resume_seed only inside `_wall`), `scripts/sysadmin/claude_rotate.py:7417` (`_armed_sids`)

## Touches
- scripts/sysadmin/hibernate.py — PRIMARY PATH
- tests/test_hibernate.py
- docs/reference/hibernate.md
- commands/_sources/hibernate.md

## Behavior Contract
- **Given** a pause marked with `--deadline 10m`, **When** `hibernate.py paused` runs, **Then** it exits 0, and 1 after a lift (scripts/sysadmin/hibernate.py:507; spec § Chosen approach L2)
- **Given** two writers updating the marker at once, **When** both finish, **Then** neither key set is lost (scripts/sysadmin/hibernate.py:291; spec § Chosen approach L3)
- **Given** a live headless `sdk-*` session that is no agent's seat, **When** `status` runs before T-3, **Then** it is a BLOCKS row, and after T-3 a `held (headless)` row (scripts/sysadmin/hibernate.py:433; spec § Chosen approach L2)
- **Given** an agent with live seats, **When** `status` runs after T-3, **Then** it blocks until the agent's closed record names as many abandoned seats (scripts/sysadmin/hibernate.py:186; spec § Chosen approach L2)
- **Given** an agent whose self-watch is not armed, **When** `status` runs, **Then** it BLOCKS, an outside-`/opt` agent included (scripts/sysadmin/hibernate.py:430; spec § Chosen approach L2)
- **Given** a lifted pause and a session that started a run after the lift, **When** `woke` runs, **Then** it exits 1 `no pending resume` (scripts/sysadmin/hibernate.py:336; spec § Chosen approach L3)
- **Given** a non-hub session under the hold, **When** it runs `hibernate.py lift`, **Then** the lift is refused and a ledger row records it (scripts/sysadmin/hibernate.py:511; spec § Chosen approach L2)
- **Given** no minute-cron heartbeat for 3 minutes, **When** `status` runs, **Then** it BLOCKS with `no minute cron` (scripts/sysadmin/hibernate.py:430; spec § Chosen approach L2)

## Context Files
- .windsurf/rules/core/10-python.md
- .windsurf/rules/core/45-testing-strategy.md
- scripts/sysadmin/hibernate.py
- tests/test_hibernate.py
- docs/reference/hibernate.md
- commands/_sources/hibernate.md
