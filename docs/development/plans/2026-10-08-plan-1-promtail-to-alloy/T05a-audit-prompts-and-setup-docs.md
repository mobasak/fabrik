# T05a — The audit prompts and the setup docs name Alloy

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
incident, a past migration) stays as written. The noise-filter doc's rename and its two inbound referrers are T05c's (one ticket owns a rename and every file that
links to it, so each ticket's whole-tree `check_doc_links.py` Gate stays green). Each doc keeps saying that Promtail stays defined under the
`rollback` profile until Gate S where it already describes the stack's services (spec § The delta › D6). DO-NOT: edit
any code or config, any governance file, `agents-fabrik.md`, `docs/reference/prebuilt-app-containers.md` or
`.windsurf/rules/` (infra's, mailed per T06).

## Touches
- docs/infrastructure/audit-prompts/01-full-system-audit.md — PRIMARY PATH
- docs/infrastructure/audit-prompts/02-container-health.md
- docs/infrastructure/audit-prompts/03-security-hardening.md
- docs/infrastructure/audit-prompts/04-performance-bottleneck.md
- docs/infrastructure/audit-prompts/05-observability-pipeline.md
- docs/infrastructure/audit-prompts/06-backup-disaster-recovery.md
- docs/infrastructure/audit-prompts/07-pre-production-checklist.md
- docs/infrastructure/audit-prompts/08-hardening-remediation.md
- docs/infrastructure/audit-prompts/README.md
- docs/infrastructure/grafana-provisioning-setup.md
- docs/infrastructure/grafana-dashboards-setup.md
- docs/infrastructure/prometheus-app-metrics-setup.md
- infra/README.md
- scripts/bootstrap/README.md

## Behavior Contract
- **Given** the docs this ticket owns, **When** each is searched for Promtail, **Then** every remaining mention is history, the rollback-profile service or the Gate S cleanup — none presents Promtail as the running shipper (spec § Documentation landing sites; docs/infrastructure/audit-prompts/01-full-system-audit.md:18)
- **Given** the docs this ticket owns, **When** `check_doc_links.py` runs, **Then** no link in them is broken, docs/infrastructure/audit-prompts/01-full-system-audit.md included (.windsurf/rules/core/40-documentation.md)

## Context Files
- docs/superpowers/specs/2026-10-05-promtail-to-alloy-design.md
- .windsurf/rules/core/40-documentation.md
- docs/infrastructure/audit-prompts/01-full-system-audit.md
- docs/infrastructure/audit-prompts/02-container-health.md
- docs/infrastructure/audit-prompts/03-security-hardening.md
- docs/infrastructure/audit-prompts/04-performance-bottleneck.md
- docs/infrastructure/audit-prompts/05-observability-pipeline.md
- docs/infrastructure/audit-prompts/06-backup-disaster-recovery.md
- docs/infrastructure/audit-prompts/07-pre-production-checklist.md
- docs/infrastructure/audit-prompts/08-hardening-remediation.md
- docs/infrastructure/audit-prompts/README.md
- docs/infrastructure/grafana-provisioning-setup.md
- docs/infrastructure/grafana-dashboards-setup.md
- docs/infrastructure/prometheus-app-metrics-setup.md
- infra/README.md
- scripts/bootstrap/README.md
