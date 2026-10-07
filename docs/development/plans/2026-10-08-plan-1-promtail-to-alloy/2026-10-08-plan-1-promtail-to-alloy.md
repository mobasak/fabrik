# Plan — Promtail → Grafana Alloy across the fleet: branch, rehearsals and runbook ready for the operator's window

Status: DRAFT
**Owner:** fleet
Spec: docs/superpowers/specs/2026-10-05-promtail-to-alloy-design.md
Date: 2026-10-08

Built from the CONVERGED spec, approved for planning by D-651 (the Opus 5.5 + Fable 5.1 panel, unanimous, under the
operator's D-650 ruling and D-613). Work item W-aec7365b (claimed by fleet). Each ticket cites the spec section it
implements and restates nothing that section settles.

## What we already agreed

- The goal and personas — spec § Goal; spec § Personas.
- Approach B, Alloy running the converter's output on file tailing; A, C and D rejected — spec § The delta › D1;
  spec § Rejected alternatives.
- The ordered stop → start switch per host, vps3 then vps2 then vps1 — spec § The delta › D2.
- Port 12345, the watchers renamed to `alloy` after the last host under an Alertmanager silence — spec § The delta › D3.
- Positions hand over from Promtail's volume to `alloy-data` — spec § The delta › D4.
- Ceilings: hub 256M, spokes 128M with cpus 0.25 — spec § The delta › D5.
- Rollback restores the previous compose file; Promtail stays under `profiles: [rollback]` until Gate S — spec § The delta › D6.
- Image `grafana/alloy:v1.20.1`, `platform: linux/amd64`, the new volume classified recomputable — spec § The delta › D7.
- The branch merges after the window's battery — spec § The delta › D8; spec § Lifecycle.
- Decided HERE, under D-651's conditions:
  - **Condition 1.** The spec's sentence at
    `docs/superpowers/specs/2026-10-05-promtail-to-alloy-design.md:55-57` is stale. It says two more copies of the
    hub compose (`configs/monitoring-compose.yaml`, `specs/infrastructure/monitoring-stack.yaml`) sit in the repo,
    but D-595 retired both and neither path exists today. This plan reads that sentence as history: no ticket
    touches either path, and the receipt records the correction. The approved spec is not edited.
  - **Condition 2.** The hub volume classification row is `scripts/bootstrap/bootstrap-config.sh:218`
    (`monitoring_promtail-positions`); the spec's `:217` predates D-647's added line. T02 adds
    `monitoring_alloy-data` beside it.
  - **Condition 3.** The two Pass-5 wording notes (W-332b562c) are carried by T06. Every V4/V5 window is anchored on
    step (b) by name, and each D3 file-set check is a pass condition whose stray DRIFT or ORPHAN line means STOP.
  - **Condition 4.** The spokes have no bootstrap volume list. Their classification lives in
    `docs/operations/spoke-restore-inventory.md` § D (`:68`), which T03 extends with `monitoring-agent_alloy-data`
    beside `monitoring-agent_promtail-positions`.
  - **The build runs on its own branch, `fleet-alloy`, cut from master** — never on `worktree-fleet`. D8 holds the
    merge until after the window, and an unrelated merge request from a shared branch ships every commit on it
    (the D-647 incident, docs/LESSONS_LEARNT.md 2026-10-07).
  - The plan ends at WINDOW READINESS. The window (D2) is the operator's, behind a boarded gate; no ticket touches a
    host, a live service or a docker volume. Gate S and its cleanup change are a later window, boarded as a
    follow-up item.
  - Infra-owned text (4 rule packs, `CLAIMS.yaml`, `agents-fabrik.md`, six `commands/_sources/` files) and the
    governance-synced `docs/reference/prebuilt-app-containers.md` (measured against the `governance-sync`
    files-filter) go to infra in one mail, drafted in the runbook's appendix and sent after the battery.

## Ticket Board

| Ticket | Title | Depends | Parallel | State | Commit |
|---|---|---|---|---|---|
| T01 | The Alloy configs are the converter's output, committed | — | ⚡ | ⬜ | |
| T02 | The hub monitoring compose runs Alloy, Promtail kept under the rollback profile | T01 | ⚡ | ⬜ | |
| T03 | The spoke stack and bootstrap step 11 ship Alloy | T01 | ⚡ | ⬜ | |
| T04 | The watchers and every repo consumer move to Alloy's name, port and metrics | — | ⚡ | ⬜ | |
| T05a | The audit prompts and the setup docs name Alloy | T02, T03, T04 | ⚡ | ⬜ | |
| T05b | The VPS inventory and the sysadmin doc name Alloy | T02, T03, T04 | ⚡ | ⬜ | |
| T05c | The VPS status and the deployment architecture name Alloy | T02, T03, T04 | ⚡ | ⬜ | |
| T05d | The operations docs and the scaffold resilience template name Alloy | T02, T03, T04 | ⚡ | ⬜ | |
| T05e | The rebuild guides and the reference docs name Alloy | T02, T03, T04 | ⚡ | ⬜ | |
| T06 | The operator's window runbook: switch, battery, rollback, Gate S, the infra mail | T02, T03, T04 | ⚡ | ⬜ | |
| T07 | Integration: rehearsals, the last doc, gates and the receipt | T01, T02, T03, T04, T05a, T05b, T05c, T05d, T05e, T06 | ⛓️ | ⬜ | |

## Merge Order

1. T01
2. T02
3. T03
4. T04
5. T05a
6. T05b
7. T05c
8. T05d
9. T05e
10. T06
11. T07

T01 and T04 are independent. T02 and T03 consume T01's configs. The five doc tickets and the runbook cite the code
tickets' final lines. T07 is last.

## Interfaces

- **T01 → T02, T03:** `configs/alloy/config.alloy` and `scripts/bootstrap/templates/alloy.alloy.template` are the files
  the compose services mount and step 11 renders. Seam tests: `tests/test_vps_apply_limits.py` (T02) and
  `tests/test_monitoring_agent_template.py` (T03) each assert the mount path names T01's file.
- **T02, T03, T04 → T06:** the runbook quotes the service name `alloy`, port 12345, the volume names and the watcher
  job and endpoint names. Seam test: `tests/test_alloy_runbook.py` (T06) asserts each name the runbook uses exists
  in the compose files and configs.

## Constraints Digest

The spec's § Constraints digest holds verbatim (core/55-observability.md:54,55,59,60,61; core/30-ops.md:149,187;
core/90-bootstrap-scripts.md:135,142); this plan adds none. Every compose service keeps
`deploy.resources.limits.memory` (V10). Every bootstrap edit passes `bash -n` (T03's Gate).

## Execution Discipline (binding on /fabrik-execute-plan)

- **Review floor** — every ticket runs `/fabrik-review` on its changed surface to a coverage-adjudicated exit BEFORE its merge; no ticket merges on a first-pass green.
  The five doc tickets may take `/fabrik-review-scoped` instead; T01–T04 and T06 take the full `/fabrik-review` (bootstrap,
  deploy-adjacent and runbook surfaces).
- **Dispatch policy** — native Claude seats for every fan-out (the pool is OFF, D-181/D-182): `dispatch_headroom.py` then
  `python3 scripts/command_run.py dispatch --seats N` before each fan-out. Coders: Sonnet for every `simple` ticket; the
  orchestrator writes T06 and T07 (`native`). Haiku never codes. Seats never read `$HOME/.claude*` or any `.env`, never
  ssh, never touch a live host; a scratch docker rehearsal uses named containers removed after.
- **Branch** — before the first dispatch: `git worktree add <scratch>/fleet-alloy -b fleet-alloy master`; every merge
  lands on `fleet-alloy`, never on `worktree-fleet` (D8 holds the merge until after the window).
- **Operator gate** — no ticket runs the window; T07 boards it. The branch goes to `scripts/merge_request.py request`
  only after the window's battery is green.
- **Parallelism + merge** — T01 and T04 fan out first and concurrently (disjoint Touches); T02 and T03 follow T01 and run concurrently; T05a–T05e and T06 run concurrently once T02, T03 and T04 are merged;
  every merge happens on the `fleet-alloy` branch in § Merge Order, and the results merge/dedupe at T07, which re-runs every ticket's gate on the merged branch.
- **Ids** — every D-row this plan mints uses `python3 scripts/decisions.py --reserve-id .`.

## Behavior Contract

- **Given** the hub Promtail config, **When** `alloy convert --source-format=promtail` runs on it, **Then** its output equals `configs/alloy/config.alloy` byte for byte (spec § The delta › D1; configs/promtail/promtail-config.yaml:12)
- **Given** `promtail.yaml.template` rendered with fixed spoke values, **When** it is converted, **Then** the output equals `alloy.alloy.template` rendered with the same values (spec § Validation V1; scripts/bootstrap/templates/promtail.yaml.template)
- **Given** each committed config (the spoke one rendered), **When** `alloy run` loads it in a container with no network, **Then** it starts without a config error (spec § Validation V2)
- **Given** no docker on the machine, **When** the test runs, **Then** it skips with a stated reason instead of passing silently (core/45-testing-strategy.md)
- **Given** the hub compose, **When** it is parsed, **Then** the `alloy` service pins `grafana/alloy:v1.20.1`, declares `platform: linux/amd64` and a 256M memory limit, and carries the listen-address and storage-path flags (spec § The delta › D3, D5, D7)
- **Given** the hub compose, **When** `docker compose config` and `docker compose config --profiles` are read, **Then** `promtail` appears only under the `rollback` profile and both `promtail-positions` and `alloy-data` are declared volumes (spec § The delta › D6)
- **Given** the memory-limits table, **When** `tests/test_vps_apply_limits.py` reads it, **Then** `alloy 256` sits beside `promtail 256` and the hub compose's alloy limit matches it (scripts/vps_apply_limits.sh:56; spec § The delta › D5)
- **Given** the bootstrap volume classification, **When** it is read, **Then** `monitoring_alloy-data` is listed as recomputable beside `monitoring_promtail-positions` (scripts/bootstrap/bootstrap-config.sh:218; spec § The delta › D7)
- **Given** the spoke compose template rendered for vps2, **When** it is parsed, **Then** the `alloy` service carries a 128M memory limit, `cpus: 0.25`, `network_mode: host` and a listen address on the spoke's mesh IP port 12345 (spec § The delta › D3, D5; Validation V10)
- **Given** the rendered spoke template, **When** it is parsed, **Then** `promtail` appears only under the `rollback` profile and both positions volumes are declared (spec § The delta › D6)
- **Given** bootstrap step 11, **When** its script text is read, **Then** it renders and ships `alloy.alloy` beside `compose.yaml` and `promtail.yaml` and its verify filter names `alloy`, not `promtail` (scripts/bootstrap/bootstrap-vps.sh:738; spec § The delta › D8)
- **Given** the edited bootstrap script, **When** `bash -n` runs on it, **Then** it parses clean (.windsurf/rules/core/90-bootstrap-scripts.md:135)
- **Given** the infra mirrors for vps2 and vps3, **When** each is compared with the template rendered for that host, **Then** they are equal (infra/README.md; spec § The delta › D8)
- **Given** the spoke restore inventory, **When** § D is read, **Then** it classifies `monitoring-agent_alloy-data` beside `monitoring-agent_promtail-positions` (docs/operations/spoke-restore-inventory.md:68; D-651)
- **Given** `configs/prometheus/prometheus.yml`, **When** it is parsed, **Then** job `alloy` scrapes exactly `alloy:12345`, `10.99.0.2:12345` and `10.99.0.3:12345` and no job is named `promtail-spokes` (configs/prometheus/prometheus.yml:70; spec § The delta › D3)
- **Given** the Gatus observability-agents config, **When** it is parsed, **Then** endpoint `alloy` checks `http://alloy:12345/-/ready` with the old interval and failure threshold and no `promtail` endpoint remains (configs/gatus/apps/observability-agents.yaml:5; spec § The delta › D3)
- **Given** the observability audit, **When** its Alloy block runs against a local `alloy run`, **Then** every metric name it greps for is present in Alloy's `/metrics` (scripts/audit/05-observability.sh:78; spec ledger cv-04)
- **Given** `vps_sync.py`'s classification sets, **When** they are read, **Then** both contain `alloy` and still contain `promtail` (scripts/vps_sync.py:154; spec § The delta › D6)
- **Given** the repo consumers named in spec § What exists today, **When** each is searched, **Then** none presents Promtail as the running shipper outside the rollback-profile references (spec § The delta › D3)
- **Given** the docs this ticket owns, **When** each is searched for Promtail, **Then** every remaining mention is history, the rollback-profile service or the Gate S cleanup — none presents Promtail as the running shipper (spec § Documentation landing sites; docs/infrastructure/audit-prompts/01-full-system-audit.md:18)
- **Given** the docs this ticket owns, **When** `check_doc_links.py` runs, **Then** no link in them is broken, docs/infrastructure/audit-prompts/01-full-system-audit.md included (.windsurf/rules/core/40-documentation.md)
- **Given** the docs this ticket owns, **When** each is searched for Promtail, **Then** every remaining mention is history, the rollback-profile service or the Gate S cleanup — none presents Promtail as the running shipper (spec § Documentation landing sites; docs/infrastructure/vps-complete-inventory.md:27)
- **Given** the docs this ticket owns, **When** `check_doc_links.py` runs, **Then** no link in them is broken, docs/infrastructure/vps-complete-inventory.md included (.windsurf/rules/core/40-documentation.md)
- **Given** the docs this ticket owns, **When** each is searched for Promtail, **Then** every remaining mention is history, the rollback-profile service or the Gate S cleanup — none presents Promtail as the running shipper (spec § Documentation landing sites; docs/infrastructure/vps-status.md:46)
- **Given** the docs this ticket owns, **When** `check_doc_links.py` runs, **Then** no link in them is broken, docs/infrastructure/vps-status.md included (.windsurf/rules/core/40-documentation.md)
- **Given** the docs this ticket owns, **When** each is searched for Promtail, **Then** every remaining mention is history, the rollback-profile service or the Gate S cleanup — none presents Promtail as the running shipper (spec § Documentation landing sites; templates/scaffold/docs/RESILIENCE_TEMPLATE.md:568; docs/operations/hub-restore-inventory.md:104)
- **Given** the docs this ticket owns, **When** `check_doc_links.py` runs, **Then** no link in them is broken, templates/scaffold/docs/RESILIENCE_TEMPLATE.md included (.windsurf/rules/core/40-documentation.md)
- **Given** the docs this ticket owns, **When** each is searched for Promtail, **Then** every remaining mention is history, the rollback-profile service or the Gate S cleanup — none presents Promtail as the running shipper (spec § Documentation landing sites; docs/reference/health-monitoring.md:19)
- **Given** the docs this ticket owns, **When** `check_doc_links.py` runs, **Then** no link in them is broken, docs/infrastructure/vps-spoke-rebuild.md included (.windsurf/rules/core/40-documentation.md)
- **Given** the runbook, **When** its per-host sections are parsed, **Then** they run vps3, vps2, vps1 in that order and each carries steps (a) to (d) with stop before start and no plain `up -d` between them (spec § The delta › D2)
- **Given** the runbook's hub section, **When** it is parsed, **Then** the two D3 read-only checks precede vps1's step (b), each stated as a pass condition with a STOP action on a stray DRIFT or ORPHAN line, and the two `--push` runs follow step (c) with `FABRIK_ROOT` set to the branch worktree (spec § The delta › D3; W-332b562c)
- **Given** the battery, **When** V4 and V5 are read, **Then** each 15-minute window is anchored on step (b) by name (spec § Validation V4, V5; W-332b562c)
- **Given** the rollback section, **When** it is read, **Then** it restores `compose.yaml.pre-alloy` and runs `up -d --remove-orphans`, never a stop-and-start that leaves the new file in place (spec § The delta › D6)
- **Given** the preflight, **When** it is read, **Then** it opens the Alertmanager silence, starts the canary before step (a) and checks port 12345 with `ss -ltn` on each spoke (spec § The delta › D3; § Open / blocking unknowns U2)
- **Given** the appendix, **When** its mail body is checked with `mail.py`'s `_structure_gaps`, **Then** it carries every D-035 section and names every infra-owned file of spec § Lifecycle (spec § Lifecycle; scripts/mail.py)
- **Given** a Promtail positions file naming a local container log at a known offset, mounted read-only, **When** Alloy starts with the committed hub config, **Then** it ships only the lines after the offset, logs the conversion, and ships nothing again after a restart (spec § Validation V3)
- **Given** Alloy tailing local containers into a throwaway Loki 3.4.2, **When** the label names are listed, **Then** they are exactly `container_name, filename, host, job, service_name, stream` (spec § Validation V4a)
- **Given** local copies of the new compose files under a throwaway project, **When** the forward switch, the D6 rollback and a plain `up -d` run in turn, **Then** Promtail runs and no alloy container exists (spec § Validation V5a)
- **Given** the plan's branch, **When** T07 closes, **Then** the operator window is an open awaiting-operator gate, the Gate S follow-up is a backlog item, and the branch has not been sent for merge (spec § The delta › D8; § Lifecycle)

## Global Constraints

- No ticket touches vps1, vps2 or vps3, a running container, the live `/opt/monitoring` or `/opt/monitoring-agent`
  files, or a docker volume. Volumes are data: `promtail-positions` is kept until Gate S's own window.
- No edit to `.windsurf/rules/`, `CLAIMS.yaml`, `agents-fabrik.md`, `commands/_sources/` or
  `docs/reference/prebuilt-app-containers.md` — infra's, mailed (T06 appendix).
- The Promtail configs and the `promtail` services stay until Gate S.

## Context Ledger

| File | Why | Cite |
|---|---|---|
| `.windsurf/rules/core/55-observability.md` (ACTIVE) | the shipper rules the spec digest quotes | `.windsurf/rules/core/55-observability.md:54` |
| `.windsurf/rules/core/30-ops.md` (ACTIVE) | memory limit mandatory | `.windsurf/rules/core/30-ops.md:149` |
| `.windsurf/rules/core/90-bootstrap-scripts.md` (ACTIVE) | `bash -n`, idempotency | `.windsurf/rules/core/90-bootstrap-scripts.md:135` |
| `.windsurf/rules/core/40-documentation.md` (ACTIVE) | the doc sweep | `.windsurf/rules/core/40-documentation.md` |
| `.windsurf/rules/core/45-testing-strategy.md` (ACTIVE) | one test per behaviour | `.windsurf/rules/core/45-testing-strategy.md` |

## File Scope (owned paths)

- configs/alloy/config.alloy
- configs/gatus/README.md
- configs/gatus/apps/observability-agents.yaml
- configs/prometheus/prometheus.yml
- docs/DEPLOYMENT_ARCHITECTURE.md
- docs/SERVICES.md
- docs/development/reviews/2026-10-08-plan-1-promtail-to-alloy-review.md
- docs/infrastructure/alloy-noise-filter-setup.md
- docs/infrastructure/audit-prompts/01-full-system-audit.md
- docs/infrastructure/audit-prompts/02-container-health.md
- docs/infrastructure/audit-prompts/03-security-hardening.md
- docs/infrastructure/audit-prompts/04-performance-bottleneck.md
- docs/infrastructure/audit-prompts/05-observability-pipeline.md
- docs/infrastructure/audit-prompts/06-backup-disaster-recovery.md
- docs/infrastructure/audit-prompts/07-pre-production-checklist.md
- docs/infrastructure/audit-prompts/08-hardening-remediation.md
- docs/infrastructure/audit-prompts/README.md
- docs/infrastructure/glitchtip-sdk-integration-setup.md
- docs/infrastructure/grafana-dashboards-setup.md
- docs/infrastructure/grafana-provisioning-setup.md
- docs/infrastructure/prometheus-app-metrics-setup.md
- docs/infrastructure/promtail-noise-filter-setup.md
- docs/infrastructure/vps-ai-sysadmin.md
- docs/infrastructure/vps-bootstrap-plan.md
- docs/infrastructure/vps-complete-inventory.md
- docs/infrastructure/vps-fleet-architecture.md
- docs/infrastructure/vps-hub-rebuild.md
- docs/infrastructure/vps-spoke-rebuild.md
- docs/infrastructure/vps-status.md
- docs/infrastructure/vps-urls.md
- docs/operations/deployment.md
- docs/operations/disaster-recovery.md
- docs/operations/hub-restore-inventory.md
- docs/operations/promtail-to-alloy-runbook.md
- docs/operations/spoke-restore-inventory.md
- docs/reference/apis/EXTERNAL_SYSTEMS.md
- docs/reference/architecture.md
- docs/reference/health-monitoring.md
- docs/superpowers/specs/2026-09-04-vps1-container-memory-limits-design.md
- docs/workflows/development-and-deployment-workflow.md
- infra/README.md
- infra/vps1/monitoring/compose.yaml
- infra/vps2/monitoring-agent/compose.yaml
- infra/vps3/monitoring-agent/compose.yaml
- scripts/audit/05-observability.sh
- scripts/audit/06-backup.sh
- scripts/bootstrap/README.md
- scripts/bootstrap/bootstrap-config.sh
- scripts/bootstrap/bootstrap-hub.sh
- scripts/bootstrap/bootstrap-spoke-restore.sh
- scripts/bootstrap/bootstrap-vps.sh
- scripts/bootstrap/templates/alloy.alloy.template
- scripts/bootstrap/templates/monitoring-agent.compose.yaml.template
- scripts/generate_vps_inventory.py
- scripts/sysadmin/proactive-check.sh
- scripts/sysadmin/system-prompt.txt
- scripts/vps_apply_limits.sh
- scripts/vps_sync.py
- templates/file-worker/compose.yaml.j2
- templates/scaffold/docs/RESILIENCE_TEMPLATE.md
- tests/test_alloy_configs.py
- tests/test_alloy_runbook.py
- tests/test_alloy_watchers.py
- tests/test_monitoring_agent_template.py
- tests/test_vps_apply_limits.py
- docs/development/reviews/2026-10-08-plan-1-promtail-to-alloy-review.md

## Intake Inventory

| I# | Item | Disposition | Where |
|---|---|---|---|
| I1 | D-651 condition 1 — the spec's stale :55-57 sentence | IN | What we already agreed; receipt |
| I2 | D-651 condition 2 — cite `bootstrap-config.sh:218` | IN | T02 |
| I3 | D-651 condition 3 — the two Pass-5 wording notes (W-332b562c) | IN | T06 |
| I4 | D-651 condition 4 — the spoke positions-volume classification | IN | T03 |
| I5 | "every VPS write behind an operator gate" | IN | Global Constraints; T07 |
| I6 | "route infra-beat surfaces to infra by mail" | IN | T06 appendix |
| I7 | spec Intake I1–I16 | as dispositioned in the spec | spec § Intake Inventory |

## Evidence

Grounding run 2026-10-08 against `worktree-fleet` at 030b9a269. The spec's 21 load-bearing cites were re-derived;
20 held at their lines, and the UFW mesh rule moved from `:404-408` to `:402-408`:

```text
OK  infra/vps1/monitoring/compose.yaml:26-45 needle='promtail'
OK  scripts/bootstrap/bootstrap-vps.sh:704-738 needle='promtail'
OK  configs/prometheus/prometheus.yml:70-80 needle='promtail'
OK  configs/gatus/apps/observability-agents.yaml:5-14 needle='promtail'
OK  scripts/vps_apply_limits.sh:56-56 needle='promtail'
OK  scripts/vps_sync.py:154-154 needle='promtail'
OK  scripts/sync_prometheus_to_vps.sh:31-31 needle='FABRIK_ROOT'
MISS scripts/bootstrap/bootstrap-vps.sh:404-408 needle='10.99' -> the rule is at :408 with ${FABRIK_WG_SUBNET}; the comment at :404 names promtail:9080
```

The Promtail sweep (`command grep -rln -i promtail docs/ scripts/ templates/ configs/ infra/ src/ tests/`, history
excluded) returned 80 files. Dispositions: 34 current-state docs (T05a–T05e, plus `EXTERNAL_SYSTEMS.md` in T07);
23 owned by the code tickets; 13 history files left as written; 4 governance files applied by the orchestrator; 1
governance-synced doc to infra; and 2 others. Those two are `src/fabrik/drivers/watchdog.py` (I13, W-1feb4dfa) and
a test docstring that cites the spec. Doc-ticket READ sizes:

```text
T05a 157,014 B · T05b 192,877 B · T05c 168,221 B · T05d 168,137 B · T05e 165,213 B  (+ 54,758 B context each, budget 262,144 B)
docs/reference/apis/EXTERNAL_SYSTEMS.md 537,674 B → T07 (Integration, budget-exempt)
```

## Self-audit

- (a) Coverage — D1 → T01; D2 → T06; D3 → T02 (hub), T03 (spokes), T04 (watchers, consumers), T06 (window half);
  D4 → T02, T03; D5 → T02, T03; D6 → T02, T03, T06; D7 → T02; D8 → T03 (step 11), Execution Discipline (branch),
  T07 (no merge before the battery); V1, V2 → T01; V3, V4a, V5a → T07; V10 → T02, T03; V4–V9, V11 → T06; the doc
  landing sites → T05a–T05e, T07; the four D-651 conditions → I1–I4 above.
- (b) Cross-ticket names — `alloy`, `alloy-data`, `promtail-positions`, port 12345, job `alloy`, endpoint `alloy`,
  `configs/alloy/config.alloy` and `alloy.alloy.template` are spelled identically in every ticket.
- Not yet a fixed point: `/fabrik-plan-review` converges it.

## Residual unknowns

- Resolved: which file deploys the hub compose (none; spec U1); the spoke volume classification home (condition 4).
- Open: U2, whether port 12345 is free on each spoke host network. Resolution: the runbook's preflight `ss -ltn`.
  On a clash, the spoke flag and the Prometheus targets take another free port.
- Open: Alloy's exact metric names for the observability audit. Resolution: T04 reads them from a local
  `alloy run`'s `/metrics` (spec ledger cv-04).
