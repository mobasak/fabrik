# T01 — `/fabrik-catchup` command

Depends: —
Parallel: ⚡
Complexity: native
Docs: CHANGELOG entry via Deltas
Gate: python commands/assemble_commands.py --check && python -m pytest tests/test_fleet_doc_audit.py -q

## Scope

Author `commands/_sources/fabrik-catchup.md` — the project-resume command that replaces the
hand-written catch-up paste-prompts of 2026-08-07 — and wire it into the assembler (NEXT map +
PARAMS). DO-NOT: implement any converge loop inside catchup (it ROUTES to `/fabrik-doc-converge`,
`/fabrik-features`, `/fabrik-data-contract`, `/fabrik-ui-design`); DO-NOT touch any other command
source; DO-NOT edit governance files (Deltas only).

The command's contract (from the operator conversation + the two hand-written exemplars):
**Phase 0 MEASURE** — plan states vs `.fabrik/plan-locks/*` (contradictions like
IN-PROGRESS-plan/released-lock), key-doc freshness vs code (`git log` per doc vs
`src/ app/ web/ lib/ scripts/` — the fleet-audit probe set), stub sentinels, untracked key docs,
`specs/services/<id>.yaml` `shape:` vs code truth, stale consumer references (env pointing at dead
services — probe liveness by DNS-vs-siblings, never registry rows). **Phase 1 QUEUE** — worst-first
fix list, each item routed to its owning command or a named reconcile action. **Phase 2 EXECUTE** —
run the queue one item at a time, committing per item (pathspecs + trailers). **Termination** — the
re-measure is a no-op and the lean gate is green. TRIGGER clause + `Stage: utility` from birth;
description names fleet_doc_audit's report as hub-side input when present.

## Touches

- commands/_sources/fabrik-catchup.md
- commands/assemble_commands.py

## Behavior Contract

- **Given** a neglected project, **When** `/fabrik-catchup` runs, **Then** it MEASURES first (plan-state vs locks, key-doc freshness vs code, stub sentinels, spec↔shape truth) and emits a worst-first fix queue routed to existing converge commands (commands/_sources/fabrik-catchup.md:1).
- **Given** a catchup fix queue, **When** executed, **Then** each fix lands via its owning command (`/fabrik-doc-converge`, `/fabrik-features`, `/fabrik-data-contract`) — catchup never re-implements a converge loop (commands/_sources/fabrik-catchup.md:1).

## Context Files

- commands/_sources/fabrik-doc-converge.md (the authoring exemplar + the routing target's real contract)
- commands/assemble_commands.py (NEXT map ~:40-48, PARAMS ~:177-190 — one entry each)
- scripts/fleet_doc_audit.py (the measurement probes to mirror project-side)
- docs/reference/MD/ai-prompt-templates.md (Parts A–C)
- docs/workstation/spine-ticket-plans-usage.md (the catch-up context it serves)
