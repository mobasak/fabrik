# T02 — `/fabrik-decommission` command

Depends: —
Parallel: ⚡
Complexity: native
Docs: CHANGELOG entry via Deltas
Gate: python commands/assemble_commands.py --check

## Scope

Author `commands/_sources/fabrik-decommission.md` — the retirement runbook encoding the wpf +
captcha lessons of 2026-08-07 — and wire it into the assembler. DO-NOT: perform any teardown
inside the command text's own examples; DO-NOT touch other command sources; governance via Deltas.

The command's contract: **Phase 0 GROUND TRUTH** — liveness probe (DNS vs resolving sibling
domains, container check where reachable — NEVER catalog/env rows as evidence: archived-source ≠
dead-service is the motivating trap); consumer sweep (`grep` fleet `.env`/specs/code for the
service's URL/API refs). **Phase 1 DECIDE** — three distinct outcomes stated to the operator:
archive-source-only (service lives on), full decommission (runtime teardown — ALWAYS a separately
operator-gated step with a named checklist: containers, Traefik route, registrar entries, DNS,
Gatus probe), or migrate-consumers-first (blockers listed per consumer). **Phase 2 EXECUTE** —
source move to `/opt/archived/<name>` (uncommitted files preserved — verify count before/after);
hub bookkeeping: catalog + PORTS + fleet-audit regen, spec disposition (delete or annotate),
memory record distinguishing archived-source vs dead-service, CHANGELOG via Deltas. **Termination**
— a receipts table: every bookkeeping surface reconciled with evidence. TRIGGER + `Stage: utility`.

## Touches

- commands/_sources/fabrik-decommission.md
- commands/assemble_commands.py

## Behavior Contract

- **Given** a retirement request, **When** `/fabrik-decommission` runs, **Then** the consumer sweep and runtime-liveness probe (DNS vs siblings, never registry rows) run BEFORE any move, and runtime teardown is a separately operator-gated step (commands/_sources/fabrik-decommission.md:1).
- **Given** a completed decommission, **When** its receipts are checked, **Then** source sits under /opt/archived, spec/PORTS/catalog/audit rows are reconciled, and a memory record distinguishes archived-source from dead-service (commands/_sources/fabrik-decommission.md:1).

## Context Files

- commands/_sources/fabrik-doc-converge.md (authoring exemplar)
- commands/assemble_commands.py (wiring shape)
- scripts/fleet_doc_audit.py (retirement = /opt/archived location, no name-lists — the mechanism to reference)
- docs/reference/MD/ai-prompt-templates.md (Parts A–C)
