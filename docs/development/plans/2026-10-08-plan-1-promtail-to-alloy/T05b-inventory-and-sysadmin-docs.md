# T05b — The VPS inventory and the sysadmin doc name Alloy

Depends: T02, T03, T04
Parallel: ⚡
Complexity: simple
Appetite: 45
Gate: python scripts/enforcement/check_doc_links.py
Docs: the rows above (current-state docs touched by the shipper change)

## Scope
Implements spec § Documentation landing sites for the docs below: every current-state claim that Promtail is the
running shipper (its name, port 9080, config path, metric names, container) is rewritten for Alloy (name `alloy`,
port 12345, `configs/alloy/config.alloy`, the `loki_write_*` metrics), and a sentence that is history (a dated
incident, a past migration) stays as written. Each doc keeps saying that Promtail stays defined under the
`rollback` profile until Gate S where it already describes the stack's services (spec § The delta › D6). DO-NOT: edit
any code or config, any governance file, `agents-fabrik.md`, `docs/reference/prebuilt-app-containers.md` or
`.windsurf/rules/` (infra's, mailed per T06).

## Touches
- docs/infrastructure/vps-complete-inventory.md — PRIMARY PATH
- docs/infrastructure/vps-ai-sysadmin.md

## Behavior Contract
- **Given** the docs this ticket owns, **When** each is searched for Promtail, **Then** every remaining mention is history, the rollback-profile service or the Gate S cleanup — none presents Promtail as the running shipper (spec § Documentation landing sites; docs/infrastructure/vps-complete-inventory.md:27)
- **Given** the docs this ticket owns, **When** `check_doc_links.py` runs, **Then** no link in them is broken, docs/infrastructure/vps-complete-inventory.md included (.windsurf/rules/core/40-documentation.md)

## Context Files
- docs/superpowers/specs/2026-10-05-promtail-to-alloy-design.md
- .windsurf/rules/core/40-documentation.md
- docs/infrastructure/vps-complete-inventory.md
- docs/infrastructure/vps-ai-sysadmin.md
