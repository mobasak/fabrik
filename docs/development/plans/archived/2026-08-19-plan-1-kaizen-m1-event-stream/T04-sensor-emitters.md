# T04 — sensor emitters: gate_run per-check + rule_activation

Depends: T01
Parallel: ⚡ (with T02, T03)
Complexity: never-route (Touches scripts/final_gate.py — the never-route named path; native coder)
## Scope
The gate becomes a sensor: per-check results assemble as (name, ok, msg) tuples at scripts/final_gate.py:416-445 — the single emission choke point; activation computes in scripts/select_rules.py:144-156.

## Touches
- scripts/final_gate.py
- scripts/select_rules.py
- scripts/review_rubric.py
- tests/test_kaizen_sensor_emitters.py

## Context Files
- docs/superpowers/specs/2026-08-16-kaizen-closed-loop-v2-design.md
- scripts/final_gate.py
- scripts/select_rules.py
- scripts/sysadmin/kaizen_events.py



## Interfaces

Consumes: T01 `emit()`.
Produces:
- `gate_run` — ONE event per gate invocation: tier, mode flags (`--check`/`--lean`), overall
  status, and `checks: [{name, outcome}]` for every EXECUTED check (advisory rows labeled as
  such) — emitted at the single report-assembly point, after the JSON is composed, fail-open.
- `rule_activation` — from `select_rules.py` main(): `packs: [{pack, globs_fired}]` for ACTIVE
  packs; from `review_rubric.py`: `rubric_injection` with the pack list injected. **Honest label
  (residual #1, baked in):** these are *invocation-time* activations; the metric definition (T06)
  carries the label `invocation-time — per-edit activation lands with a PostToolUse surface (M2)`.

## Steps

1. TDD: `tests/test_kaizen_sensor_emitters.py` — run each script as a subprocess with
   `KAIZEN_EVENTS_DIR=tmp` on a fixture tree; assert one `gate_run` with per-check rows matching
   the JSON report 1:1 (no check silently absent), one `rule_activation` listing the fixture pack.
   Fail-open: module absent → outputs byte-identical to today. RUN RED first.
2. Implement — emission code is ≤10 lines per script at the assembly seams; NOTHING about check
   logic changes (never-route discipline: the sensors observe the gate, they never alter it).
3. Gate: `uv run pytest tests/test_kaizen_sensor_emitters.py -q` + a live
   `final_gate.py --lean --json --check` run shows the event with its full check roster.

## Behavior Contract

- **Given** a `final_gate.py --json` run, **When** it completes, **Then** ONE `gate_run` event
  carries per-check name+outcome for every executed check and the overall status
  (scripts/final_gate.py).
- **Given** a `select_rules.py` invocation, **When** packs resolve, **Then** a `rule_activation`
  event lists each ACTIVE pack with the glob that fired it (scripts/select_rules.py).

Docs: schema rows ride T01's doc; the invocation-time label is stated in T06's definition registry.
Gate: `uv run pytest tests/test_kaizen_sensor_emitters.py -q` + the live gate smoke.
