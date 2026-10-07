# T05d — The operations docs and the scaffold resilience template name Alloy

Depends: T02, T03, T04a, T04b
Parallel: ⚡
Complexity: simple
Appetite: 45
Gate: python scripts/enforcement/check_doc_links.py
Docs: the rows above (current-state docs touched by the shipper change)

## Scope
Implements spec § Documentation landing sites for the docs below: every current-state claim that Promtail is the
running shipper (its name, port 9080, config path, metric names, container) is rewritten for Alloy (name `alloy`,
port 12345, `configs/alloy/config.alloy`, the `loki_write_*` metrics), and a sentence that is history (a dated
incident, a past migration) stays as written. `templates/scaffold/docs/RESILIENCE_TEMPLATE.md` changes one table cell (the shipper's name; the file is not a governance-sync trigger, measured against the `governance-sync` files-filter); `docs/operations/hub-restore-inventory.md` classifies `monitoring_alloy-data` beside `monitoring_promtail-positions`. Each doc keeps saying that Promtail stays defined under the
`rollback` profile until Gate S where it already describes the stack's services (spec § The delta › D6). DO-NOT: edit
any code or config, any governance file, `agents-fabrik.md`, `docs/reference/prebuilt-app-containers.md` or
`.windsurf/rules/` (infra's, mailed per T06).

## Touches
- templates/scaffold/docs/RESILIENCE_TEMPLATE.md — PRIMARY PATH
- docs/infrastructure/vps-fleet-architecture.md
- docs/operations/deployment.md
- docs/operations/disaster-recovery.md
- docs/SERVICES.md
- docs/operations/hub-restore-inventory.md

## Behavior Contract
- **Given** the docs this ticket owns, **When** each is searched for Promtail, **Then** every remaining mention is history, the rollback-profile service or the Gate S cleanup — none presents Promtail as the running shipper (spec § Documentation landing sites; templates/scaffold/docs/RESILIENCE_TEMPLATE.md:568; docs/operations/hub-restore-inventory.md:104)
- **Given** the docs this ticket owns, **When** `check_doc_links.py` runs, **Then** no link in them is broken, templates/scaffold/docs/RESILIENCE_TEMPLATE.md included (.windsurf/rules/core/40-documentation.md)

## Context Files
- docs/superpowers/specs/2026-10-05-promtail-to-alloy-design.md
- .windsurf/rules/core/40-documentation.md
- templates/scaffold/docs/RESILIENCE_TEMPLATE.md
- docs/infrastructure/vps-fleet-architecture.md
- docs/operations/deployment.md
- docs/operations/disaster-recovery.md
- docs/SERVICES.md
- docs/operations/hub-restore-inventory.md
