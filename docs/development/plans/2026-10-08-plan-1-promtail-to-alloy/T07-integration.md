# T07 — Integration: rehearsals, the last doc, gates and the receipt

Depends: T01, T02, T03, T04, T05a, T05b, T05c, T05d, T05e, T06
Parallel: ⛓️
Complexity: native
Integration: true
Appetite: 120
Gate: python scripts/final_gate.py --check --json
Docs: INDEX.md, docs/README.md, CHANGELOG.md (orchestrator-applied)

## Scope
The orchestrator, after T01–T06 merge into the `fleet-alloy` branch: (a) runs the local rehearsals the spec leaves
to the build — V3 (positions import on a real container log at a known offset, read-only mount, no re-ship after a
restart), V4a (label parity into a throwaway Loki 3.4.2: exactly `container_name, filename, host, job, service_name,
stream`) and V5a (rollback rehearsal on local copies of the real compose files under a throwaway project name: forward
switch, the D6 rollback, then a plain `up -d` — Promtail runs, no alloy container) — each with its output fenced in
the receipt (spec § Validation); (b) rewrites the Promtail claims in `docs/reference/apis/EXTERNAL_SYSTEMS.md` (the one
doc too large for a doc ticket's READ budget); (c) boards the operator window as a gate (one DECISION block, ground
`gate`, naming the runbook) and the Gate S follow-up as a backlog item for the fleet agent; (d) applies the INDEX.md and
docs/README.md rows for the runbook, the renamed noise-filter doc and the new tests, and the CHANGELOG entry; (e) runs
the whole-plan gates and writes the receipt `docs/development/reviews/2026-10-08-plan-1-promtail-to-alloy-review.md`.
The branch is NOT sent for merge here: spec D8 merges it after the window's battery, which the runbook's close names. DO-NOT: run any window step, touch a host or a docker volume outside the throwaway
rehearsal projects, or send the branch for merge.

## Touches
- docs/development/reviews/2026-10-08-plan-1-promtail-to-alloy-review.md
- docs/reference/apis/EXTERNAL_SYSTEMS.md

## Behavior Contract
- **Given** a Promtail positions file naming a local container log at a known offset, mounted read-only, **When** Alloy starts with the committed hub config, **Then** it ships only the lines after the offset, logs the conversion, and ships nothing again after a restart (spec § Validation V3)
- **Given** Alloy tailing local containers into a throwaway Loki 3.4.2, **When** the label names are listed, **Then** they are exactly `container_name, filename, host, job, service_name, stream` (spec § Validation V4a)
- **Given** local copies of the new compose files under a throwaway project, **When** the forward switch, the D6 rollback and a plain `up -d` run in turn, **Then** Promtail runs and no alloy container exists (spec § Validation V5a)
- **Given** the plan's branch, **When** T07 closes, **Then** the operator window is an open awaiting-operator gate, the Gate S follow-up is a backlog item, and the branch has not been sent for merge (spec § The delta › D8; § Lifecycle)

## Context Files
- docs/superpowers/specs/2026-10-05-promtail-to-alloy-design.md
- docs/operations/promtail-to-alloy-runbook.md
- infra/vps1/monitoring/compose.yaml
- configs/alloy/config.alloy
