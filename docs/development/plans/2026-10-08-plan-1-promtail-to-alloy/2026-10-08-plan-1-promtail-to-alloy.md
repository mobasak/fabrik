# Plan — Promtail → Grafana Alloy across the fleet: branch, rehearsals and runbook ready for the operator's window

Status: IN-PROGRESS
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
  - **The build runs on its own branch, `fleet-alloy`, cut from master once this plan set is on master** — never on `worktree-fleet`. D8 holds the
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
| T01 | The Alloy configs are the converter's output, committed | — | ⚡ | ✅ | merged (wave 1) |
| T02 | The hub monitoring compose runs Alloy, Promtail kept under the rollback profile | T01 | ⚡ | ✅ | merged (wave 2) |
| T03 | The spoke stack and bootstrap step 11 ship Alloy | T01 | ⚡ | ✅ | merged (wave 2) |
| T04a | The Prometheus job and the Gatus endpoint move to Alloy | — | ⚡ | ✅ | merged (wave 1) |
| T04b | Every repo consumer names Alloy's container, port and metrics | — | ⚡ | ✅ | merged (wave 1) |
| T05a | The audit prompts and the setup docs name Alloy | T02, T03, T04a, T04b | ⚡ | ✅ | merged (wave 3) |
| T05b | The VPS inventory and the sysadmin doc name Alloy | T02, T03, T04a, T04b | ⚡ | ✅ | merged (wave 3) |
| T05c | The VPS status and the deployment architecture name Alloy | T02, T03, T04a, T04b | ⚡ | ✅ | merged (wave 3) |
| T05d | The operations docs and the scaffold resilience template name Alloy | T02, T03, T04a, T04b | ⚡ | ✅ | merged (wave 3) |
| T05e | The rebuild guides and the reference docs name Alloy | T02, T03, T04a, T04b | ⚡ | ✅ | merged (wave 3) |
| T06 | The operator's window runbook: switch, battery, rollback, Gate S, the infra mail | T02, T03, T04a, T04b | ⚡ | ✅ | merged (wave 3) |
| T07 | Integration: rehearsals, the last doc, gates and the receipt | T01, T02, T03, T04a, T04b, T05a, T05b, T05c, T05d, T05e, T06 | ⛓️ | ⬜ | |

## Merge Order

1. T01
2. T02
3. T03
4. T04a
5. T04b
6. T05a
7. T05b
8. T05c
9. T05d
10. T05e
11. T06
12. T07

T01, T04a and T04b are independent. T02 and T03 consume T01's configs. The five doc tickets and the runbook cite the
code tickets' final lines. T07 is last.

Breadth advisory (`check_ticket_breadth.py`, 6 of 11 flagged at plan-review pass 1): T04 (score 8) was SPLIT into
T04a (the watcher configs the window pushes) and T04b (the repo consumers) — two risk classes. KEPT, each one coupled
unit: T03 (8 — the spoke template, the step 11 that renders it and the mirrors it renders are one artifact), T06 (7 —
one runbook, one ordered sequence), T01 and T02 (6 — a config with its template; a compose with its ceiling row),
T07 (5 — the Integration ticket).

## Interfaces

- **T01 → T02, T03:** `configs/alloy/config.alloy` and `scripts/bootstrap/templates/alloy.alloy.template` are the files
  the compose services mount and step 11 renders. Seam tests: `tests/test_vps_apply_limits.py` (T02) and
  `tests/test_monitoring_agent_template.py` (T03) each assert the mount path names T01's file.
- **T02, T03, T04a → T06:** the runbook quotes the service name `alloy`, port 12345, the volume names and the watcher
  job and endpoint names. Seam test: `tests/test_alloy_runbook.py` (T06) asserts each name the runbook uses exists
  in the compose files and configs.

## Constraints Digest

The spec's § Constraints digest holds verbatim; the rubric run of plan-review pass 1 (below, § Coverage Checklist)
MATCHED eight packs and injects four FLOOR rows, each named here with the line that decides its effect.

| Pack | Verbatim | Where | Effect here |
|---|---|---|---|
| core/55-observability.md (MATCHED) | "Grafana Alloy is the successor (`alloy convert` migrates the config)." | `.windsurf/rules/core/55-observability.md:54` | T01 commits the converter's output |
| core/30-ops.md (FLOOR) | "`deploy.resources.limits.memory` is mandatory." | `.windsurf/rules/core/30-ops.md:149` | T02, T03: every alloy service carries a limit (V10) |
| core/90-bootstrap-scripts.md (MATCHED) | "run `bash -n scripts/bootstrap/bootstrap-vps.sh` (catches LOCAL parser" | `.windsurf/rules/core/90-bootstrap-scripts.md:135` | T03's Gate runs `bash -n` |
| core/45-testing-strategy.md (MATCHED) | "one test per user-observable behavior; regression test for bugfix" | `.windsurf/rules/core/45-testing-strategy.md:10` | every ticket's Behavior Contract row has its test |
| core/40-documentation.md (MATCHED) | "GOAL: Scaffolded doc templates, Documentation Sync Matrix, changelog, INDEX.md, writing style" | `.windsurf/rules/core/40-documentation.md:8` | T05a–T05e and T07; INDEX/README/CHANGELOG rows are orchestrator-applied |
| core/10-python.md (MATCHED) | "Logging handled errors (short event + context, not full traceback)" | `.windsurf/rules/core/10-python.md:178` | T04b's Python edits add set members and strings only — no logging path changes |
| core/57-external-data-sourcing.md (MATCHED) | "**Hub:** `docs/reference/apis/<vendor>.md`, plus its row in that dir's `EXTERNAL_SYSTEMS.md`." | `.windsurf/rules/core/57-external-data-sourcing.md:293` | T07 edits the existing rows of `EXTERNAL_SYSTEMS.md`; no new vendor profile |
| core/58-resilience.md (MATCHED) | "**Activation:** Glob — resilience files (RESILIENCE.md, health endpoints, HTTP clients, pause state, error classifier, dispatchers, beat tasks)." | `.windsurf/rules/core/58-resilience.md:17` | matched by `docs/reference/health-monitoring.md`'s name only; no resilience mechanism changes |
| core/self-healing.md (MATCHED) | "Self-healing in Fabrik = an autonomous-by-default escalation LADDER, NOT a new primitive." | `.windsurf/rules/core/self-healing.md:16` | matched by the same doc; no ladder step changes |
| core/35-security-auth.md, core/25-data-postgres.md (FLOOR) | — | — | unconstrained: no auth, secret or database surface changes |
| 12-FACTOR (FLOOR) | — | — | unconstrained: no application config, process model or backing-service binding changes — the shipper is fleet infrastructure |

## Execution Discipline (binding on /fabrik-execute-plan)

- **Review floor** — every ticket runs `/fabrik-review` on its changed surface to a coverage-adjudicated exit BEFORE its merge; no ticket merges on a first-pass green.
  The five doc tickets may take `/fabrik-review-scoped` instead; T01–T03, T04a, T04b and T06 take the full `/fabrik-review` (bootstrap,
  deploy-adjacent and runbook surfaces).
- **Dispatch policy** — native Claude seats for every fan-out (the pool is OFF, D-181/D-182): `dispatch_headroom.py` then
  `python3 scripts/command_run.py dispatch --seats N` before each fan-out. Coders: Sonnet for every `simple` ticket; the
  orchestrator writes T06 and T07 (`native`). Haiku never codes. Seats never read `$HOME/.claude*` or any `.env`, never
  ssh, never touch a live host; a scratch docker rehearsal uses named containers removed after.
- **Branch** — this plan set (docs only) reaches master first through the fleet branch's merge request; then, before
  the first dispatch: `git worktree add /opt/fabrik/.claude/worktrees/fleet-alloy -b fleet-alloy master` (a durable path:
  the operator runs the window from it). Every ticket merge and every Board update is committed on `fleet-alloy`, never
  on `worktree-fleet` (D8 holds the merge until after the window).
- **Operator gate** — no ticket runs the window; T07 boards it. The branch goes to `scripts/merge_request.py request`
  only after the window's battery is green.
- **Parallelism + merge** — T01, T04a and T04b fan out first and concurrently (disjoint Touches); T02 and T03 follow T01 and run concurrently; T05a–T05e and T06 run concurrently once T02, T03, T04a and T04b are merged;
  every merge happens on the `fleet-alloy` branch in § Merge Order, and the results merge/dedupe at T07, which re-runs every ticket's gate on the merged branch.
- **Ids** — every D-row this plan mints uses `python3 scripts/decisions.py --reserve-id .`.

## RESUME

Paused 2026-10-08 on the quota drain band (execute-plan D2: quota pressure pauses the plan, never thins the review).
Board: T01–T06 ✅ (waves 1–3 merged on `fleet-alloy`; receipts `-T01-review.md`, `-T02-review.md`, `-T05a-review.md`).
T07 part 1 landed at 1418e38cb: `docs/reference/apis/EXTERNAL_SYSTEMS.md` rewritten, Gate S boarded as W-a7ee59fd, and the
three rehearsals run locally on throwaway `t07r-` containers and projects, all PASS:

- **V5a** — after the forward switch `['alloy running', 'promtail exited']`; after the D6 rollback `['promtail running']`;
  after a plain `up -d` `['promtail running']` (no alloy container).
- **V4a** — Loki 3.4.2 label names `container_name, filename, host, job, service_name, stream`, plus Loki's own internal
  `__stream_shard__`.
- **V3** — positions file at offset 1089 (after line 10 of 20): Alloy shipped exactly `t07r-line-11` … `t07r-line-20`
  (10 lines), logged `successfully converted legacy positions file to the new format`, and shipped nothing again after a
  restart.

Resume, in the `fleet-alloy` worktree after the quota reset: `/fabrik-execute-plan docs/development/plans/2026-10-08-plan-1-promtail-to-alloy/`
→ D7 whole-plan validation (`/fabrik-review` over `ad790046b..HEAD`, at least 3 Sonnet finders plus the authoritative seat)
writing `docs/development/reviews/2026-10-08-plan-1-promtail-to-alloy-review.md` with the rehearsal results above and the
D-651 condition-1 correction → board the operator window as a `gate` DECISION → flip T07 ✅ and the spine to EXECUTED. The
branch is NOT sent for merge (spec D8). Leftover from the first V5a run: docker volume `t07r-v5a_alloy-data` (throwaway,
created 2026-10-08 by the rehearsal; deleting it is the operator's word).

## Behavior Contract

- **Given** the hub Promtail config, **When** `alloy convert --source-format=promtail` runs on it, **Then** its output equals `configs/alloy/config.alloy` byte for byte (spec § The delta › D1; configs/promtail/promtail-config.yaml:12)
- **Given** `promtail.yaml.template` rendered with fixed spoke values, **When** it is converted, **Then** the output equals `alloy.alloy.template` rendered with the same values (spec § Validation V1; scripts/bootstrap/templates/promtail.yaml.template)
- **Given** each committed config (the spoke one rendered), **When** `alloy run` loads it in a container with no network, **Then** it starts without a config error (spec § Validation V2)
- **Given** no docker on the machine, or the `grafana/alloy:v1.20.1` image neither cached nor pullable, **When** the test runs, **Then** it skips with the stated reason instead of passing silently (core/45-testing-strategy.md)
- **Given** the hub compose, **When** it is parsed, **Then** the `alloy` service pins `grafana/alloy:v1.20.1`, declares `platform: linux/amd64` and a 256M memory limit, and carries the listen-address and storage-path flags (spec § The delta › D3, D5, D7)
- **Given** the hub compose, **When** `docker compose config` and `docker compose config --profiles` are read, **Then** `promtail` appears only under the `rollback` profile and both `promtail-positions` and `alloy-data` are declared volumes (spec § The delta › D6)
- **Given** the memory-limits table, **When** `tests/test_vps_apply_limits.py` reads it, **Then** `alloy 256` sits beside `promtail 256` and the hub compose's alloy limit matches it (scripts/vps_apply_limits.sh:56; spec § The delta › D5; Validation V10)
- **Given** the bootstrap volume classification, **When** it is read, **Then** `monitoring_alloy-data` is listed as recomputable beside `monitoring_promtail-positions` (scripts/bootstrap/bootstrap-config.sh:220, beside :219; spec § The delta › D7)
- **Given** the spoke compose template rendered for vps2, **When** it is parsed, **Then** the `alloy` service pins `grafana/alloy:v1.20.1` with `platform: linux/amd64` and `restart: unless-stopped`, and carries a 128M memory limit, `cpus: 0.25`, `network_mode: host` and a listen address on the spoke's mesh IP port 12345 (spec § The delta › D3, D5, D7; Validation V10)
- **Given** the rendered spoke template, **When** it is parsed, **Then** `promtail` appears only under the `rollback` profile and both positions volumes are declared (spec § The delta › D6)
- **Given** bootstrap step 11, **When** its script text is read, **Then** it renders and ships `alloy.alloy` beside `compose.yaml` and `promtail.yaml` and its verify filter names `alloy`, not `promtail` (scripts/bootstrap/bootstrap-vps.sh:738; spec § The delta › D8)
- **Given** the two edited bootstrap scripts, **When** `bash -n` runs on each, **Then** both parse clean (.windsurf/rules/core/90-bootstrap-scripts.md:135)
- **Given** the infra mirrors for vps2 and vps3, **When** each is compared with the template rendered for that host, **Then** they are equal (infra/README.md; spec § The delta › D8)
- **Given** the spoke restore inventory, **When** § D is read, **Then** it classifies `monitoring-agent_alloy-data` beside `monitoring-agent_promtail-positions` (docs/operations/spoke-restore-inventory.md:68; D-651)
- **Given** `configs/prometheus/prometheus.yml`, **When** it is parsed, **Then** job `alloy` scrapes exactly `alloy:12345`, `10.99.0.2:12345` and `10.99.0.3:12345` and no job is named `promtail-spokes` (configs/prometheus/prometheus.yml:70; spec § The delta › D3)
- **Given** the Gatus observability-agents config, **When** it is parsed, **Then** endpoint `alloy` checks `http://alloy:12345/-/ready` with the old interval and failure threshold and no `promtail` endpoint remains (configs/gatus/apps/observability-agents.yaml:5; spec § The delta › D3)
- **Given** the observability audit, **When** its Alloy block runs against a local `alloy run`, **Then** every metric name it greps for is present in Alloy's `/metrics` once Alloy has pushed to a throwaway Loki (scripts/audit/05-observability.sh:78; spec ledger cv-04)
- **Given** the port registry, **When** `PORTS.md` is read, **Then** it lists 12345 for `alloy` and marks 9080 `promtail` as rollback-only (PORTS.md:40; spec § The delta › D3)
- **Given** `vps_sync.py`'s classification sets, **When** they are read, **Then** both contain `alloy` and still contain `promtail` (scripts/vps_sync.py:154; spec § The delta › D6)
- **Given** the repo consumers named in spec § What exists today, **When** each is searched, **Then** none presents Promtail as the running shipper outside the rollback-profile references (spec § The delta › D3)
- **Given** the docs this ticket owns, **When** each is searched for Promtail, **Then** every remaining mention is history, the rollback-profile service or the Gate S cleanup — none presents Promtail as the running shipper (spec § Documentation landing sites; docs/infrastructure/audit-prompts/01-full-system-audit.md:18)
- **Given** the docs this ticket owns, **When** `check_doc_links.py` runs, **Then** no link in them is broken, docs/infrastructure/audit-prompts/01-full-system-audit.md included (.windsurf/rules/core/40-documentation.md)
- **Given** the docs this ticket owns, **When** each is searched for Promtail, **Then** every remaining mention is history, the rollback-profile service or the Gate S cleanup — none presents Promtail as the running shipper (spec § Documentation landing sites; docs/infrastructure/vps-complete-inventory.md:27)
- **Given** the docs this ticket owns, **When** `check_doc_links.py` runs, **Then** no link in them is broken, docs/infrastructure/vps-complete-inventory.md included (.windsurf/rules/core/40-documentation.md)
- **Given** the docs this ticket owns, **When** each is searched for Promtail, **Then** every remaining mention is history, the rollback-profile service or the Gate S cleanup — none presents Promtail as the running shipper (spec § Documentation landing sites; docs/infrastructure/vps-status.md:46)
- **Given** the renamed noise-filter doc, **When** the tree is searched for `promtail-noise-filter-setup.md` outside history, **Then** nothing links it: `docs/DEPLOYMENT_ARCHITECTURE.md:855` and the glitchtip setup doc link `alloy-noise-filter-setup.md`, which describes Alloy's `stage.drop` (docs/DEPLOYMENT_ARCHITECTURE.md:855)
- **Given** the docs this ticket owns, **When** `check_doc_links.py` runs, **Then** no link in them is broken, docs/infrastructure/vps-status.md included (.windsurf/rules/core/40-documentation.md)
- **Given** the docs this ticket owns, **When** each is searched for Promtail, **Then** every remaining mention is history, the rollback-profile service or the Gate S cleanup — none presents Promtail as the running shipper (spec § Documentation landing sites; templates/scaffold/docs/RESILIENCE_TEMPLATE.md:568; docs/operations/hub-restore-inventory.md:104)
- **Given** the docs this ticket owns, **When** `check_doc_links.py` runs, **Then** no link in them is broken, templates/scaffold/docs/RESILIENCE_TEMPLATE.md included (.windsurf/rules/core/40-documentation.md)
- **Given** the docs this ticket owns, **When** each is searched for Promtail, **Then** every remaining mention is history, the rollback-profile service or the Gate S cleanup — none presents Promtail as the running shipper (spec § Documentation landing sites; docs/reference/health-monitoring.md:19)
- **Given** the docs this ticket owns, **When** `check_doc_links.py` runs, **Then** no link in them is broken, docs/infrastructure/vps-spoke-rebuild.md included (.windsurf/rules/core/40-documentation.md)
- **Given** the runbook, **When** its per-host sections are parsed, **Then** they run vps3, vps2, vps1 in that order and each carries steps (a) to (d) with stop before start and no plain `up -d` between them (spec § The delta › D2)
- **Given** the runbook's hub section, **When** it is parsed, **Then** the two D3 read-only checks precede vps1's step (b), each stated as a pass condition with a STOP action on a stray DRIFT or ORPHAN line, and the two `--push` runs follow step (c) with `FABRIK_ROOT` set to the branch worktree (spec § The delta › D3; W-332b562c)
- **Given** the battery, **When** V4, V5 and V6 are read, **Then** each 15-minute window is anchored on step (b) by name, and V6 writes numbered pre-markers 5 to 10 minutes before step (b) and one switch marker between (b) and (c) to the canary (no `--rm`), requiring each marker exactly once in Loki for that host within 2 minutes of (c) (spec § Validation V4, V5, V6; W-332b562c)
- **Given** the rollback section, **When** it is read, **Then** it restores `compose.yaml.pre-alloy` and runs `up -d --remove-orphans`, never a stop-and-start that leaves the new file in place (spec § The delta › D6)
- **Given** the preflight, **When** it is read, **Then** it opens the Alertmanager silence, starts the canary before step (a) and checks port 12345 with `ss -ltn` on each spoke (spec § The delta › D3; § Open / blocking unknowns U2)
- **Given** the Gate S section, **When** it is read, **Then** it names V8 and V9 green on all three hosts for 14 days as the trigger and lists the cleanup: the promtail service, the `promtail-positions` volume (classified before any change), the `.pre-alloy` files, the two Promtail configs and the `promtail 256` ceiling retired spec-row first (spec § The delta › D6)
- **Given** the close, **When** it is read, **Then** the operator signals the fleet agent that all three hosts passed their battery, and only then does the fleet agent send `fleet-alloy` for merge with `merge_request.py request` and send the infra mail (spec § Personas; § The delta › D8; § Lifecycle)
- **Given** the appendix, **When** its mail body is checked with `mail.py`'s `_structure_gaps`, **Then** it carries every D-035 section and names every infra-owned file of spec § Lifecycle (spec § Lifecycle; scripts/mail.py)
- **Given** a Promtail positions file naming a local container log at a known offset, mounted read-only, **When** Alloy starts with the committed hub config, **Then** it ships only the lines after the offset, logs the conversion, and ships nothing again after a restart (spec § Validation V3)
- **Given** Alloy tailing local containers into a throwaway Loki 3.4.2, **When** the label names are listed, **Then** they are exactly `container_name, filename, host, job, service_name, stream` (spec § Validation V4a)
- **Given** local copies of the new compose files under a throwaway project, **When** the forward switch, the D6 rollback and a plain `up -d` run in turn, **Then** Promtail runs and no alloy container exists (spec § Validation V5a)
- **Given** `docs/reference/apis/EXTERNAL_SYSTEMS.md`, **When** it is searched for Promtail, **Then** the shipper section names Alloy as running and every remaining Promtail mention is history or the rollback-profile service (docs/reference/apis/EXTERNAL_SYSTEMS.md:3019)
- **Given** the plan's branch, **When** T07 closes, **Then** the operator window is an open awaiting-operator gate, the Gate S follow-up is a backlog item, and the branch has not been sent for merge (spec § The delta › D8; § Lifecycle)

## Global Constraints

- No ticket touches vps1, vps2 or vps3, a running container, the live `/opt/monitoring` or `/opt/monitoring-agent`
  files, or a docker volume — outside the throwaway local rehearsal projects T07 creates and removes. Volumes are data: `promtail-positions` is kept until Gate S's own window.
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

- PORTS.md
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
- tests/test_alloy_consumers.py
- tests/test_alloy_runbook.py
- tests/test_alloy_watchers.py
- tests/test_monitoring_agent_template.py
- tests/test_vps_apply_limits.py

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

The Promtail sweep (`command grep -rln -i promtail docs/ scripts/ templates/ configs/ infra/ src/ tests/`, minus the
`docs/archive`, `plans/archived`, `/reviews/`, `research/` and `superpowers/` paths) returned 80 lines: 3 are `__pycache__`
binaries, and the 77 files are dispositioned as follows: 34 current-state docs (T05a–T05e, plus `EXTERNAL_SYSTEMS.md` in T07);
23 owned by the code tickets; 13 history files left as written; 4 governance files applied by the orchestrator; 1
governance-synced doc to infra; and 2 others. Those two are `src/fabrik/drivers/watchdog.py` (I13, W-1feb4dfa) and
a test docstring that cites the spec. Doc-ticket READ sizes:

```text
T05a 131,195 B · T05b 192,877 B · T05c 194,040 B · T05d 168,137 B · T05e 165,213 B  (+ 54,758 B context each, budget 262,144 B)
docs/reference/apis/EXTERNAL_SYSTEMS.md 537,674 B → T07 (Integration, budget-exempt)
```

## Self-audit

- (a) Coverage — D1 → T01; D2 → T06; D3 → T02 (hub), T03 (spokes), T04a (watchers), T04b (consumers), T06 (window half);
  D4 → T02, T03; D5 → T02, T03; D6 → T02, T03, T06; D7 → T02, T03; D8 → T03 (step 11), Execution Discipline (branch),
  T07 (no merge before the battery); V1, V2 → T01 (configs), T02, T03, T04b (`bash -n` on every edited script); V3, V4a, V5a → T07; V10 → T02, T03; V4–V9, V11 → T06; the doc
  landing sites → T05a–T05e, T07; the four D-651 conditions → I1–I4 above.
- (b) Cross-ticket names — `alloy`, `alloy-data`, `promtail-positions`, port 12345, job `alloy`, endpoint `alloy`,
  `configs/alloy/config.alloy` and `alloy.alloy.template` are spelled identically in every ticket.
- Not yet a fixed point: `/fabrik-plan-review` converges it.

## Coverage Checklist

Rubric invocation (verbatim; plan-review pass 1):

```text
$ python scripts/review_rubric.py --changed configs/alloy/config.alloy configs/gatus/README.md configs/gatus/apps/observability-agents.yaml configs/prometheus/prometheus.yml docs/DEPLOYMENT_ARCHITECTURE.md docs/SERVICES.md docs/development/reviews/2026-10-08-plan-1-promtail-to-alloy-review.md docs/infrastructure/alloy-noise-filter-setup.md docs/infrastructure/audit-prompts/01-full-system-audit.md docs/infrastructure/audit-prompts/02-container-health.md docs/infrastructure/audit-prompts/03-security-hardening.md docs/infrastructure/audit-prompts/04-performance-bottleneck.md docs/infrastructure/audit-prompts/05-observability-pipeline.md docs/infrastructure/audit-prompts/06-backup-disaster-recovery.md docs/infrastructure/audit-prompts/07-pre-production-checklist.md docs/infrastructure/audit-prompts/08-hardening-remediation.md docs/infrastructure/audit-prompts/README.md docs/infrastructure/glitchtip-sdk-integration-setup.md docs/infrastructure/grafana-dashboards-setup.md docs/infrastructure/grafana-provisioning-setup.md docs/infrastructure/prometheus-app-metrics-setup.md docs/infrastructure/promtail-noise-filter-setup.md docs/infrastructure/vps-ai-sysadmin.md docs/infrastructure/vps-bootstrap-plan.md docs/infrastructure/vps-complete-inventory.md docs/infrastructure/vps-fleet-architecture.md docs/infrastructure/vps-hub-rebuild.md docs/infrastructure/vps-spoke-rebuild.md docs/infrastructure/vps-status.md docs/infrastructure/vps-urls.md docs/operations/deployment.md docs/operations/disaster-recovery.md docs/operations/hub-restore-inventory.md docs/operations/promtail-to-alloy-runbook.md docs/operations/spoke-restore-inventory.md docs/reference/apis/EXTERNAL_SYSTEMS.md docs/reference/architecture.md docs/reference/health-monitoring.md docs/superpowers/specs/2026-09-04-vps1-container-memory-limits-design.md docs/workflows/development-and-deployment-workflow.md infra/README.md infra/vps1/monitoring/compose.yaml infra/vps2/monitoring-agent/compose.yaml infra/vps3/monitoring-agent/compose.yaml scripts/audit/05-observability.sh scripts/audit/06-backup.sh scripts/bootstrap/README.md scripts/bootstrap/bootstrap-config.sh scripts/bootstrap/bootstrap-hub.sh scripts/bootstrap/bootstrap-spoke-restore.sh scripts/bootstrap/bootstrap-vps.sh scripts/bootstrap/templates/alloy.alloy.template scripts/bootstrap/templates/monitoring-agent.compose.yaml.template scripts/generate_vps_inventory.py scripts/sysadmin/proactive-check.sh scripts/sysadmin/system-prompt.txt scripts/vps_apply_limits.sh scripts/vps_sync.py templates/file-worker/compose.yaml.j2 templates/scaffold/docs/RESILIENCE_TEMPLATE.md tests/test_alloy_configs.py tests/test_alloy_consumers.py tests/test_alloy_runbook.py tests/test_alloy_watchers.py tests/test_monitoring_agent_template.py tests/test_vps_apply_limits.py docs/development/reviews/2026-10-08-plan-1-promtail-to-alloy-review.md
# REVIEW RUBRIC — inject into EVERY finder prompt (generated by review_rubric.py)
# Honesty (L1): this arms the review — it raises compliance probability, it does not guarantee it.

## FLOOR — always injected, regardless of glob (spec L3; SERVICE surface)

### core/35-security-auth.md
**The default for ALL new projects, including user-facing SaaS + mobile.** Vendor `fabrik-lib/fastapi-user-auth`: the app issues its own JWTs — **Argon2id** (the vendored argon2-cffi defaults meet OWASP minimums; never Argon2i) + timing-equalized login, atomic refresh-token rotation (`DELETE … RETURNING`), JWT `jti` denylist revocation, and dual-mode tenant-isolation RLS. Supabase is retired as a default (see `agents-fabrik.md § Supabase`); reach for Pattern B only for a project that *already* runs on Supabase Auth.
- Do not use NextAuth.js, Clerk, Auth0, or Firebase Auth.
- ADDITIONAL affordance a project justifies, never the default door.
- project files the fabrik-lib request FIRST, never hand-rolls WebAuthn.
| `chrome-extension` | ✅ **use this** | ⚠️ only via `chrome.identity.launchWebAuthFlow` + the `https://<ext-id>.chromiumapp.org/` redirect the pack already mandates; a bare mailed link lands in a TAB that cannot reach `chrome.storage.session` |
| `desktop-app` | ✅ **use this** | ⚠️ needs a registered custom protocol handler; the token then goes to `safeStorage` (`desktop-app/72-desktop.md`) |
- service MUST be able to say which:
| **Another Fabrik service** (Docker-to-Docker on the `fabrik` network) | `X-Internal-Token` + `internal_auth.py`, `hmac.compare_digest`, 403 on reject | § Internal Service Auth (M2M) below — **never** an inline `APIKeyHeader`, never a per-service key name |
- An approval link opened somewhere the user did not start must never mint a session silently.
- > **Fail-closed invariant (hard, every mode).** `auth.uid()` and `current_tenant_id()` MUST return `NULL` (→ the policy denies) on unset, empty, or malformed claims — wrap the body in `EXCEPTION WHEN OTHERS THEN RETURN NULL`. **Never** raise and never default to a value: a default turns one bad/empty JWT into a cross-tenant read, and a raise turns a deny into a 500. This is the single most security-critical line in the build — verify it explicitly with a no-context probe (`SELECT auth.uid()` → `NULL`).
- The JWT signing secret must be at least 256 bits, generated via `openssl rand -hex 32`, and injected via Pydantic Settings. Never hardcode it.
- **Pin the algorithm in the VERIFIER** — pass an explicit allow-list (`algorithms=["HS256"]`), never let the library dispatch on the token header's `alg`. Header-driven dispatch is the classic confusion attack (an RS256 public key replayed as an HS256 HMAC secret); `alg: none` is rejected unconditionally.
- "Sticky sessions are a violation of twelve-factor and should never be used or relied upon."
- => Mandate: processes are stateless/share-nothing. **STICKY SESSIONS ARE BANNED** (not just file-based sessions). Session state goes to `redis-main` (Redis) with a TTL. Never in-process memory, never on local disk. Any design that assumes "the same user hits the same process" is a violation.
- **Pattern B (legacy / migration-only):** The Supabase client SDK handles token storage. On mobile, wrap with `expo-secure-store` (never AsyncStorage or MMKV for tokens). See `80-mobile.md` § Backend Integration.
- **Both patterns:** Never store JWTs in `localStorage` or `sessionStorage` on web. Never store JWTs in AsyncStorage or MMKV on mobile.
- **Chrome Extension (MV3) specifics:** `chrome.storage.session` defaults to `TRUSTED_CONTEXTS`, so **content scripts cannot read the token** — keep it in the SW / extension-page context and have content scripts fetch it via SW-mediated messaging (`chrome.runtime.sendMessage`), not a direct read. For social login use `chrome.identity.launchWebAuthFlow` with **PKCE** (`code_verifier` via `crypto.subtle`, held in `storage.session`, redirect `https://<ext-id>.chromiumapp.org/`); the **backend** does the code-for-token exchange. **Never a heavy browser auth SDK** (Auth0-SPA-JS, `oidc-client-ts`) — they assume DOM/`localStorage`/iframes and break in the service worker. Pin a manifest `key` so the extension ID (and thus the `chrome-extension://<id>` CORS origin) is stable across machines. Full detail: `chrome-ext/70-chrome-ext.md`.
- **Never rely solely on the framework's request-shaping layer for access control.** CVE-2025-29927 (the `x-middleware-subrequest` bypass) proved COMPLETE middleware bypass via one crafted header; it is long patched upstream, but the rule outlives the patch — current Next.js even RENAMED the file to say so: `middleware.ts` became **`proxy.ts`**, explicitly repositioned as request-shaping, not a security boundary. ⚠️ **On current majors a leftover `middleware.ts` is SILENTLY IGNORED at build** — nonce injection and redirects stop executing with no error; rename it when upgrading.
- `CORSMiddleware` in FastAPI must populate `allow_origins` from environment variables (Pydantic Settings). Never hardcode origins.
- `X-Frame-Options: DENY` — kept as the legacy fallback only; formally obsoleted by `frame-ancestors`, never ship it ALONE
**Never** write inline `APIKeyHeader` / `require_api_key`. **Never** use per-service key names (`SERVICE_API_KEY`, `PROXY_API_KEY`). Scaffold `python-api` auto-emits `internal_auth.py`, `metrics.py` (REQUEST_COUNT / ERROR_COUNT / ACTIVE_JOBS / PROCESSING_COUNT), `/metrics` endpoint (Authelia-bypassed), and `SERVICE_INTERNAL_SECRET_KEY` in `.env.example`.
- => Mandate: config via env vars only (`os.getenv("KEY", "default")`); **ZERO secrets/constants in code**. Apply the open-source litmus test to every change. **BANNED**: grouped/named env config sets (e.g. a `config/production.yml` or a `settings.production` group) — env vars are granular and orthogonal, set per deploy. (The pack already covers secret handling — cross-reference existing secret patterns and extend with config orthogonality.)
- [ ] Mobile tokens stored in `expo-secure-store` — never AsyncStorage or MMKV.
- > **⚠️ Bearer bypass scope — security-critical.** The bypass defaults to `^/api/`, which makes the **entire** `/api/*` surface public (un-2FA'd). If the application authenticates only a **sub-prefix** (e.g. `/api/v1` carries the bearer/internal-token check) while OTHER `/api/*` routes are unauthenticated (legacy / admin / destructive), you **MUST** narrow the bypass with `shape.bearer_bypass_prefix: "^/api/v1"` — otherwise `fabrik apply` exposes those routes to the public internet. **Bypass ONLY the path the app itself authenticates.** Value must start with `^/`; the verifier (`orchestrator/verifier.check_api_bypass`) probes the configured prefix on deploy. When unsure whether a service has un-auth'd `/api/*` routes, ask the app owner before relying on the `^/api/` default.

### core/25-data-postgres.md
| Vector search | pgvector on `postgres-main` + `fabrik-lib/rag` — ⚠️ the extension is NOT currently installed there (probed 2026-09-01: the plain upstream PostgreSQL Alpine image, `plpgsql` only — `CLAIMS.yaml` row `fleet-postgres-main-no-pgvector`); a project needing vectors REQUESTS the fleet infra change first, never assumes it | same `postgres-main` DSN |
**"Own database" means a DATABASE on `postgres-main`, never a database SERVER.** Per-project isolation is a separate database (its own name, its own role) on the shared container — isolation, quota and backup are all satisfied at that grain. A dedicated Postgres instance is a decision, not a default: it needs its own `docs/DECISIONS.md` row naming what the shared server cannot serve (web-ecommerce-factory 01M1Q8X9, 2026-09-05: "one DB per store" read naively as one server per customer).
- Use Pydantic `BaseSettings` (per `10-python.md` § Config Loading) — never raw `os.getenv` **for an APPLICATION's settings surface**:
- ⚠️ **Scope, stated here because this LINE is what `review_rubric.py` injects — without its section.** The rubric FLOOR-injects this mandate *and* `35-security-auth`'s "config via env vars only (`os.getenv("KEY", "default")`)" into every finder prompt on every review, so a finder reading both literally has two rules it cannot both satisfy, and files a false positive on whichever it applies. The carve-out: `BaseSettings` governs a SERVICE's config surface (a `Settings` object, DB/Redis DSNs, secrets). A **vendored fabrik-lib module** has no settings object by design — it reads its own knobs with bare `os.getenv("KEY", "default")`, which is `35-security-auth`'s mandate being satisfied, not this … (wrapped further — read the pack)
- Never blindly trust `--autogenerate`. Always review `upgrade()` and `downgrade()` for unintended column drops, rename misinterpretations, and ENUM alterations before committing.
- > **Older pythons only** (services pinned below stdlib-uuid7 — which today includes SCAFFOLDED services: the scaffold still emits an older interpreter and ships `uuid-utils`; alignment tracked in the backlog): import `uuid7` from `uuid_utils.compat`, never `uuid_utils.uuid7()` directly — the latter returns `uuid_utils.UUID`, which asyncpg rejects (not a stdlib `uuid.UUID`). **DB-side:** newer PostgreSQL majors ship native `uuidv7()` (probe: `SELECT uuidv7()`); prefer `DEFAULT uuidv7()` at schema level where it exists. `postgres-main` currently runs major <!--v:postgres_major-->16<!--/v-->, which predates it — generate app-side on the fleet.
- Foreign keys must declare `ON DELETE` behaviour explicitly — `CASCADE` if children cannot exist without the parent, `RESTRICT` to protect audit trails. Never rely on the implicit default.
- This section owns the **canonical** engine, session, and `get_db`. `10-python.md` imports from here — never redefines its own.
- Database `AsyncSession` must be scoped to the route handler via `Depends()`. Never open sessions or transactions in global middleware — this holds connections during serialisation and I/O, exhausting the pool.
**BANNED as a server-side backing service** (dev, test, and prod alike):
**⚠️ SCOPE — this ban is about BACKING SERVICES, not client-local storage.** It does **NOT** apply to:
- **`desktop-app`** — SQLite is the **mandated** engine there (`desktop-app/72-desktop.md` § Local Persistence: `better-sqlite3` + SQLCipher; *"Production builds MUST encrypt the local SQLite file"*).
**12-Factor IV (Backing Services) — generalised:** swapping ANY attached backing service (DB, cache, object storage) is a **config change, never a code change**. The handle lives in `DATABASE_URL` / `REDIS_URL` / storage env — the code *reads* it, the code does not *decide* it. Never `if ENV == "prod":` branching to pick a host. (See § PostgreSQL Host Selection, which already mandates this for the DB.)
- [ ] All primary keys use UUIDv7 — stdlib `uuid.uuid7` on current Python (older pythons: `uuid_utils.compat.uuid7`, never direct `uuid_utils.uuid7()`); no `uuid4()`.

### core/30-ops.md
- the pinned release leaves full security support, never per-pack.
- All services deploy via `fabrik apply` (SSH + Docker Compose) on the `fabrik` network. Traefik routes external traffic — services do NOT bind host ports.
- **No `ports:` section.** All external traffic routes through Traefik. Never bind host ports. See Docker Port Security below. **12‑Factor VII (Port binding):** "the app is self‑contained and exports HTTP by binding to a port; it does not rely on runtime injection of a webserver" — which is exactly WHY no host `ports:`.
- **`container_name: <name>` is mandatory.** Same `_validate_compose()` gate refuses any service without it. Stable names are required so Gatus endpoints, inter-service URLs, and `docker exec`/`docker inspect` keys don't drift per redeploy. Use the bare service name (`browserless`, `gotenberg`, `meilisearch`, `glitchtip-web`, `site-provisioner`, etc.) — never UUID-suffixed names.
- gets one (ruling D-052) — see `core/60-watchdog.md`. Do not author a `watchdog: { enabled: false }` opt-out; if a project genuinely cannot host the sidecar, that is a ruling to obtain, not a default to flip.
- path before the flag goes in the spec, and assert target health (`/api/v1/targets` → `up`), never a bare `curl` of a path you assumed.
- remove it` on the hub) names a plan that protects nothing. Never add a service-named plan.
- health-enabled service can NEVER pass `up -d --wait` on a fresh database, and the deploy hangs to timeout.  An init the deploy cannot perform itself is a runbook step the plan MUST own.
- `fabrik redeploy <app>` SSHes to the VPS and runs `git pull` + `docker compose up -d --wait` against the **GitHub remote**, NOT the local `/opt/<app>` clone. Skipping `git push` redeploys the previous remote commit — the VPS never sees local changes.
**Mandate:** build → release → run are strictly separated. Releases are IMMUTABLE; the git SHA is the release ID. NEVER hot‑patch a running container (no `docker exec` to edit code/config in place, no in‑place code mutation on the VPS). Any change = a new build + a new release via `fabrik apply` / `fabrik redeploy`.
- Runtime database migrations that modify the app container (migrations MUST be run as separate deploy‑time steps)
**Place a service next to its data.** A spoke-hosted service reaches `postgres-main`/`redis-main` over the WireGuard mesh, and that hop is cross-Atlantic (Coventry ↔ LA) on EVERY query — a per-request chatty service pays it hundreds of times per page. So a DB-chatty service targets vps1; a spoke earns a service whose data traffic is light, batched or cached; a service PINNED to a spoke by hardware (GPU) batches or caches its data access — the data never moves off vps1. Measure before choosing (`ping 10.99.0.1` from the spoke, and the request's query count), never assume — the correctness rule ("container DNS, never localhost") says nothing about latency.
**Mandate:** WSL dev and the VPS run the SAME backing services (PostgreSQL + Redis), same major version. NEVER substitute a different backing service in dev (no SQLite standing in for Postgres, no in‑memory dict standing in for Redis). The same code must run unmodified in both environments.
- WSL runs PostgreSQL + Redis at the SAME MAJOR as the VPS containers — probe the live truth, never copy a tag from a doc: `ssh vps "sudo docker inspect postgres-main redis-main --format '{{.Config.Image}}'"` (probed 2026-09-01: the plain upstream PostgreSQL Alpine image at the fleet major recorded in `CLAIMS.yaml` row `pg-fleet-major` · `redis:7-alpine` — upstream official images, outside OUR-image Alpine ban per § Banned Patterns)
**Invariant:** Never use `ports:` in compose.yaml to expose internal services to the host. All external traffic must go through Traefik.
**Health endpoints (`/health`, `/healthz`, `/metrics`, `/api/health`) bypass Authelia on all services** — required for Gatus and Prometheus monitoring. The bypass is **resource-based, not domain-bound** — applies on every domain routed through Authelia (hub direct + spokes via `authelia-vps1@file` middleware). Never protect these paths.
**CRITICAL:** Use `web`/`websecure` in Traefik labels — never `http`/`https` (those entrypoints do not exist). The scaffolder emits the correct entrypoint names; if you hand-write labels, match these exactly.
**Mandate:** migrations and admin tasks run as a ONE‑OFF process against the DEPLOYED image + env — identical environment to regular processes. NEVER run admin tasks from a laptop against prod, NEVER via `docker exec` into a live container, and **ABSOLUTELY NEVER auto-run migrations from app startup/`lifespan`** (concurrent replicas race the Alembic version table → wedged deploy).
- > **`fabrik run` and `.fabrik/hooks/post-deploy/` do NOT exist** — the real CLI answers `Error: No such command 'run'`, the hook path appears nowhere in the platform, and `_post_deploy_sync()` (`cli.py:64`) only refreshes `data/projects.yaml`; an agent following either ships a deploy where migrations never run. Do not re-add either without a `path:line` in `src/fabrik/` that executes it.
**Processes are share-nothing:** any state shared across requests MUST go to Redis (`redis-main`) with a TTL. A project using Redis for sessions MUST declare `shape.needs_cache: true` in `specs/services/<id>.yaml`, or `fabrik apply` skips the Redis registrar and the deploy is silently broken.
- "A twelve-factor app never relies on implicit existence of system-wide packages"
**Mandate:** any binary the app shells out to (ffmpeg, yt-dlp, poppler, tesseract…) MUST be `apt-get install`-ed in the Dockerfile, with a `shutil.which()` startup probe that fails fast. **The pinned base image is the version boundary** — exact `=version` apt pins are banned: they break on every Debian point release as old debs leave the mirrors (the "works then mysteriously breaks" class this section exists to prevent); the codename pin + image digest give the reproducibility. Never assume `curl`/ImageMagick/ffmpeg exist in the image — they don't by default.

### 12-FACTOR (all twelve axes)
- I codebase: shared code → fabrik-lib, never two apps in one repo
- II deps: every shelled-out binary installed + pinned in the Dockerfile
- III config: granular env vars; no secrets in code; no grouped env sets
- IV backing services: swappable by DSN/config change only
- V build/release/run: releases immutable; never hot-patch a container
- VI processes: stateless; session state → redis-main; no sticky sessions
- VII port binding: bind in-container; Traefik routes; no host ports:
- VIII concurrency: scale out; never daemonize or write PID files
- IX disposability: SIGTERM returns in-flight jobs to the queue; jobs idempotent
- X dev/prod parity: same backing services everywhere; no SQLite-for-Postgres
- XI logs: unbuffered stdout only; the app never writes/rotates a logfile
- XII admin: migrations/one-offs run against the deployed release, never startup

## MATCHED — packs whose globs hit the changed paths

### core/10-python.md  (hit: scripts/generate_vps_inventory.py, scripts/vps_sync.py, tests/test_alloy_configs.py)
**`uv`** is the mandated Python package manager. Never use raw `pip`, `pip install`, `poetry`, or `pipenv`.
- Dependencies live in `pyproject.toml` + `uv.lock`. Do not modify these files unless the ticket authorises it.
- its own reviewed commit, never as a side effect of unrelated work.
- The one RULE: use SQLAlchemy async consistently — never mix `async def` with sync `.query().all()` (the Banned table row; the full session pattern is `25-data-postgres.md`'s).
- The canonical `engine`, `async_session`, and `get_db` are defined in `src/database.py` — owned by `25-data-postgres.md`. Import from there, never redefine:
**Config convention:** apps read a complete `DATABASE_URL` (`postgresql+asyncpg://user:pass@host:port/db`) and `REDIS_URL` from env. Discrete `DB_HOST`/`DB_PORT`/`DB_NAME`/`DB_USER`/`DB_PASSWORD` for the app to assemble are **banned**. The env supplies the complete URL — `localhost` in WSL, `postgres-main` on VPS — so the host concern is an env-layer responsibility, never code logic. See `30-ops.md` compose template for how discrete vars are interpolated into `DATABASE_URL` at the compose level.
- volume** (`30-ops.md` § Volumes), never in `.tmp` and never in `/tmp`.
**GlitchTip discipline:** unhandled exceptions (FastAPI 500s) are auto-captured by GlitchTip with full stacktraces. In the `except Exception` branch, log a **short event name + correlation_id** — never `logger.exception()` (that duplicates the traceback in Loki AND GlitchTip). See `55-observability.md` § Error Reporting for the full rule.
**Note:** Use the scaffolded logger: `from {package}.logger import get_logger` (see `55-observability.md` § Pre-Scaffolded Logging). Do not use `structlog.get_logger()` directly or `logging.getLogger(__name__)`.
- **Never a bare `asyncio.create_task()`** — an unreferenced task is silently garbage-collected and its exceptions vanish. Hold the reference and await it, or use `asyncio.TaskGroup`.
- **`datetime.now(UTC)`, never `datetime.utcnow()`** — deprecated and naive; naive datetimes are a real cross-service defect class.
- Type the package, never `.`: the root walks the hub-synced `scripts/`, where mypy finds the same file under two module names and stops on every fresh project. file-worker types `mypy --explicit-package-bases worker`; a `server/` backend (saas-skeleton, static-site, office-extension, chrome-extension, mobile-app) runs `mypy src` from `server/` (D-605).
- Ruff's selected rule-sets MUST include `ASYNC` (blocking IO in async code — machine-enforces this pack's hardest-to-review rule), `B` (bugbear) and `S` (bandit) alongside the defaults; configured in `pyproject.toml`, emitted by the scaffolder.
- Production services run via `uvicorn` CLI in the Dockerfile, not `uvicorn.run()` in code. Base image is always the pinned Debian `-slim` variant on `linux/amd64` (the variant is pinned fleet-wide in `30-ops.md` § Container Base Images — change it THERE, never per-repo). Never use Alpine — musllinux wheels exist now (PEP 656) but coverage is still partial, source builds are dramatically slower, and musl's allocator/stack defaults degrade CPython; the trade never pays on this fleet.
- `uvicorn.run()` is for local development only. Never ship it in production code.
- a fleet scaling decision (more containers), never a per-app flag.
**BANNED: grouped/named env config sets.** 12F is explicit — *"env vars are granular controls, each fully orthogonal to other env vars"* — so a `config/production.yml`, a `settings.production` group, or a `config/{dev,staging,prod}.yaml` tree is a violation. Env vars are granular and set **per deploy**, never batched into a named "environment".
**BANNED:** `logging.FileHandler`, `logging.handlers.RotatingFileHandler`, `TimedRotatingFileHandler`, `loguru` file sinks, any `*.log` file write, any in-app log rotation/retention/cleanup. The app never decides where logs are stored or routed — Docker → Promtail → Loki does. Full rule: `55-observability.md` § Logs.
**Factor XII — Admin processes. NEVER migrate from app startup.**
**BANNED: `alembic upgrade head` in FastAPI's `lifespan`, in an `@app.on_event("startup")`, or as an import side-effect.** With more than one replica (or a restart storm) two containers run `upgrade head` **concurrently** → they race the Alembic version table → duplicate DDL → **wedged deploy**. Migrations are a **one-off admin process against the deployed release**: `docker compose run --rm <svc> alembic upgrade head` (see `30-ops.md` § Release & Admin Processes).

### core/40-documentation.md  (hit: configs/gatus/README.md, docs/DEPLOYMENT_ARCHITECTURE.md, docs/SERVICES.md)
- > **⚠️ `docs/OPERATIONS.md` + `docs/DEPLOYMENT.md` are FLEET-AI INTERFACES, not just docs (D-065).**
- **Tier-1 (author → verify → converge; the author leg is NATIVE while the pool is OFF, D-181 — `scripts/doc_reconcile.py`'s pool author cannot dispatch):** for each **mechanically-detectable** doc whose Doc-Sync trigger fired (`docs/QUICKSTART.md` · `docs/CONFIGURATION.md` · `docs/data-contract.md` · `docs/SERVICES.md` · `docs/OPERATIONS.md` — the reliable-signal subset), `scripts/doc_reconcile.py` dispatches a cheap OpenRouter-pool author (`libs.subagents`, `pick_models("docs")`) to emit a **minimal structured patch**, **verifies it before applying** (a symbol cross-check catches invented endpoints; the orchestrator injects a higher-assurance native-Claude verify), and loops to a zero-edit round. Runs per phase in `/fabrik-execute-plan`; never blocks (fail-safe). The other docs (CHANGELOG, INDEX, FEATURES, RESILIENCE, PORTS, the READMEs, `db/schema.sql`, …) have no reliable mechanical content-signal → they rely on the touch-on-change backstop below + your own edit (force-update, not force-correct).
- The SSOT is the type-aware registry (`scripts/enforcement/_doc_registry.py::PROJECT_DOCS`) — this table is its project-facing rendering, kept in step, never a second truth. `/fabrik-plan-after-chat` (the plan set's spine + tickets — the ticket-format authority) injects these rows per ticket as its `Docs:` line.
- Standalone work (not plan execution) → `Agent-Role: primary`. Trailers go below a blank line, above `Co-Authored-By`. ⚠️ The trailer block must be its OWN paragraph with NO blank line inside it: git parses only the LAST paragraph, and only if it is all-trailers. A blank line before `Co-Authored-By:` demotes everything above it to prose; so does a prose line glued to the top of the block. Measured 2026-08-15: 200 of the last 200 hub commits carried `Agent-Role:` and only 10 parsed, because the old example here shipped the blank line.
- **⚠️ Link it or it is decoration.** *Measured:* requests for files that do NOT exist came ~zero from AI bots — agents never go looking. It follows (inference, not measurement) that a file only gets read when something points at it: reference it from the docs index or README.
- ⚠️ **In THIS repo `llms.txt` is GENERATED** (`scripts/generate_capability_index.py`, refreshed daily) — never hand-edit it; change the generator. A project writing one by hand owns it.
- either way. Cheap and reversible — never at the expense of `OPERATIONS.md`/`DEPLOYMENT.md`, which are the load-bearing agent interfaces (D-065).
- **No skipped heading levels** — `##` to `###`, never `##` to `####`
- **Fenced code blocks only** — never indented code (AI treats it inconsistently)

### core/45-testing-strategy.md  (hit: tests/test_alloy_configs.py, tests/test_alloy_consumers.py, tests/test_alloy_runbook.py)
- **Behavior Contract**: every ticket enumerates its distinct **user-observable behaviors / acceptance criteria** and tests **each one** — one high-value integration/E2E test per behavior, risk-ordered, TDD for the risky ones. Skip trivia (getters / framework glue / config): **lean-but-complete, NOT 100%-line-coverage dogma**. Do not chase line coverage — ensure every behavior has a test that would fail if that behavior regressed. (Cheap pool subagents can author the per-behavior tests — the suggest→curate→author→fix workflow in `62-using-subagents.md` § Dispatch policy + `~/.claude/commands/fabrik-review.md`.)
- **No cosmetic assertions**: never assert against CSS classes, Tailwind utility strings, pixel measurements, or snapshot hashes. Assert application state and user-visible outcomes only.
- **Watched-fail-first** (for tests this change adds or modifies; trivia stays skipped per the Behavior Contract): a non-trivial behavior's test proves something only if it has been SEEN RED — either write it first and watch it fail, or (after the fact) neuter the fix/feature, prove the test goes red, then RESTORE and re-run to green. The neutered state is never staged, committed, or left in the tree. A green test never seen red is unverified — a suite can pass with its guard deleted.
- **Run tests**: `uv run pytest tests/` (never bare `pytest` — Fabrik uses `uv`) — **when the project has a `pyproject.toml`/`uv.lock`**. A `requirements.txt`-only project (no manifest) runs `.venv/bin/python -m pytest tests/` — the manifest clause chooses the RUNNER, it never disarms the mandate to run the suite (web-ecommerce-factory 01M1QEY5, 2026-09-05: the clause read as "does not apply here"). ⚠️ **Gate this on the manifest, because this line is FLOOR-injected into finder prompts and a vendored fabrik-lib MODULE has neither by design**: the module recipe ships `requirements.txt` (`fabrik-lib/README.md` § Creating a Reference Implementation), so `uv run` cannot resolve it and `python3 -m pytest` is the only thing that works. Telling a finder the sole working … (wrapped further — read the pack)
- **Zero-mock database policy**: never mock SQLAlchemy, SQLModel, or database sessions. All backend tests execute against a real PostgreSQL instance.
- **`ASGITransport` never runs lifespan** — anything the app initializes at startup (scaffolded apps are lifespan-based) silently does not exist in tests; wrap with `asgi-lifespan`'s `LifespanManager` when a test needs startup state.
- Use `structlog` in test helpers if logging is needed — never `print()`. See `55-observability.md`.
- **Never stub a server action from Playwright** — the server is the E2E boundary; stubbing belongs in the unit lane where the action is a plain function.
- Run Playwright against the PRODUCTION build (`next build && next start`), never the dev server.
- All locators must be **semantic**: `page.getByRole('button', { name: /submit/i })`. Never use CSS selectors or XPath.
- Launch Playwright's **bundled Chromium** (`channel: 'chromium'`) — stable Chrome/Edge removed the `--load-extension` / `--disable-extensions-except` side-load flags (Chrome 137/139), so those args only work under bundled Chromium, never installed stable Chrome.
- Run `@axe-core/playwright` with **`bypassCSP: true`** (the non-relaxable extension CSP otherwise makes axe throw on `chrome-extension://` pages); keep `@axe-core/playwright` a **dev-dependency only** (MPL-2.0 — never bundled into the shipped artifact). Gate bundle size with `size-limit` **per surface** (popup / side-panel / content-script). Full loop: `chrome-ext/70-chrome-ext.md` § Testing & UI Verification.
- Keep the generated types committed and re-generate on schema changes (`uv run python -c "import json; from <package>.main import app; print(json.dumps(app.openapi()))" > openapi.json` — the scaffold emits `src/<package>/main.py`, never a flat `src/main.py`, so `src.main` imports nothing).
**BANNED in tests:**
| A GUARD proven only by the ONE spelling of the defect you already fixed | Write the guard's subject five LEGITIMATE ways — five a DIFFERENT author would plausibly write, not five typos of yours — and count how many it still catches; one of five means it is keyed on your fix, not on the class — and one of five is the FLOOR of the failure, never its definition: four of five is a partial class and is reported as four of five. This is IN ADDITION to red-on-revert below, not a rival bar: that one proves the guard fires at all, this one proves it fires on the class. ⚠️ Cheapest ways to satisfy it WITHOUT the outcome (`CLAUDE.md` § UNIVERSAL governance markers, the entry whose anchor is **you get the behavior you measure** — search the ANCHOR, not the rule name: the project-facing contract lists that section by anchor alone and carries the name `cobra-effect` nowhere): (i) write five near-identical spellings and count 5/5; (ii) ship at 2/5 and REPORT it, needing no fabrication at all, in the hope that a reported count reads as a passed one — it does not: under 5/5 is a finding; (iii) claim the exercise and record nothing, since the five are never committed. So the bar is TWO things and needs both: **the five go IN the test file as executable CASES**, never a comment — a comment cannot go RED, so nothing can falsify it, and that is the objection, not that it records nothing — **and anything under 5/5 is a finding, not a pass**. ⚠️ Two paths this row does NOT close, stated rather than pretended away: you can shrink the SUBJECT until five legitimate spellings all land inside what the guard already catches (nothing is fabricated; the claim narrowed, not the guard), and an honest 4/5 — real information, 80% of the class — costs the author something to report, so the cheapest response to it is silence. Report the count you got either way — a 4/5 with the miss NAMED is a finding someone can act on, and a 5/5 nobody can execute is not a pass at all. Measured 4× in one day across 2 repos (01M1S4D78KRM0ZSYDNGTHS9HYQ), and once more the day this row landed: a contract-parity grader that read the LIVE file instead of the tree under test stayed green under the exact drift it existed to catch |
| A test THIS change adds/modifies that was never seen red (no fail-first, no red-on-revert proof) | Watch it fail first, or neuter the change → prove red → restore → re-run green |
- [ ] Destructive DB tests call `require_throwaway(TEST_DATABASE_URL)` before connecting — never point them at a dev/shared DB.

### core/55-observability.md  (hit: docs/infrastructure/glitchtip-sdk-integration-setup.md, docs/reference/health-monitoring.md, infra/vps1/monitoring/compose.yaml)
- ⚠️ **The shipper is Promtail today and Promtail reached END OF LIFE (2026-03-02)** — no updates, no support. Grafana Alloy is the successor (`alloy convert` migrates the config). Fleet migration is an infra action, not a per-project one; until it lands, nothing about the rules below changes.
- **The label set is the PIPELINE's, not yours** — live: `container_name`, `filename`, `host`, `job`, `service_name`, `stream`. An app cannot add labels by logging a field; a JSON field is queried with `| json`, never as a label.
- > *"A twelve-factor app never concerns itself with routing or storage of its output stream. It should not attempt to write to or manage logfiles."*
**Mandate.** The app writes structured events, unbuffered, to `stdout` and **nothing else**. The app MUST NEVER write, rotate, append to, truncate, compress, age out, or otherwise manage a logfile, and MUST NEVER decide where logs are stored, how long they are kept, or how they are routed. Routing, rotation, retention, and storage are exclusively the **execution environment's** concern.
**BANNED in app code:**
- The scaffolded logger (structlog / pino — see § Pre-Scaffolded Logging) writes to stdout. Do not add a second handler, sink, or transport alongside the stdout one.
- ❌ **BANNED — in-app file logging:**
- > **⚠️ THE SERVER'S OWN LOGGERS ARE NOT YOURS — and they leak plain text by default.**
**Chrome extension frontend:** Use `chrome.storage.local` buffer pattern per the Chrome Extension Telemetry section below. Do not use pino directly in service workers.
- Every `python-api` and `node-api` scaffold emits a pre-configured `/metrics` endpoint. DO NOT create custom metrics modules. **A VENDORED module (fabrik-lib copies) never constructs its own `Counter`/`Histogram` either:** the scaffold serves `/metrics` from a PRIVATE `CollectorRegistry` (`scaffold.py::metrics_app`), so a module-made metric on the global default registry is invisible on most `/metrics` surfaces and the module cannot know which registry its host scrapes. A module exposes an injectable callback (`on_<event>: Callable | None`) and a structured log-once; the HOST wires the callback to the registry it owns in one line. Precedent: fabrik-lib `async-http-client` (01M1GVYN, 01M1GY91).
- Name metrics with `snake_case` and a **base-unit** suffix (`_seconds`, `_bytes`); `_total` is the COUNTER suffix and composes with units (`process_cpu_seconds_total`). ⚠️ `prometheus_client` appends `_total` to a Counter itself — declare `Counter("requests", …)`, never `Counter("requests_total", …)`, and never `_count` (an OpenMetrics reserved suffix).
- ⚠️ **Know which failure YOUR stack gives you — they are not the same.** Under an OTel SDK, a metric that overflows its cardinality limit fails SILENTLY: totals stay correct while queries that *filter or group by* an attribute UNDERCOUNT, so dashboards and SLOs keep rendering numbers that are quietly too low. **Our scaffolded stack is `prometheus_client`, which has no such limit** — here a blowup is memory/TSDB growth, and Prometheus's own `sample_limit` fails the whole scrape LOUDLY (`up=0`) rather than skewing a breakdown. Loud is survivable; the reason to care about both is that a service moving to OTel inherits the silent one.
- is named, never dropped because someone remembered to remove it — and `_keep()` additionally enforces LEAF SHAPE: an allowlisted key holding an unexpected container is nulled. That last rule is what closes a channel nobody enumerated, which is the whole reason this is a shape rather than a list.
- `include_local_variables=False`, `max_request_body_size="never"`, `include_source_context=False`, `max_breadcrumbs=0`, and the fleet logging default `LoggingIntegration(event_level=logging.ERROR, level=None)` (D-126).
- ⚠️ **That last one is COUPLED to the allowlist and the two must move together.** The upstream reference uses `event_level=None`, which closes the log channel by never creating an event. The fleet keeps ERROR records as events — we want them in GlitchTip — so the channel is open, and what closes it is `_ALLOWED_LOGENTRY_KEYS == {"message"}`: the message TEMPLATE survives, `params` and `formatted` (the interpolated text) do not. Verified: `logger.error("otp=%s", secret)` yields one event with `logentry == {'message': 'otp=%s'}` and no secret. Widening that allowlist turns the fleet default into a leak where the upstream default would not.
- Every `sentry_sdk.init` / `Sentry.init` in the fleet MUST still set both:
| `max_request_body_size="never"` | **n/a — see below** | the request BODY, attached irrespective of `send_default_pii` (that flag gates COOKIES). Every auth, payments-webhook and token-exchange route is exposed the moment it logs an error while handling its request. **PYTHON ONLY** |
- ⚠️ **The two SDKs are NOT symmetric.** `maxRequestBodySize` is a PYTHON option name; `@sentry/node` has no such init key, so a project that dutifully added it got a silently-ignored unknown key — a line that reads like a fix and does nothing. In `@sentry/node` the body channel is already closed by `sendDefaultPii: false`, which makes the SDK report body **size only, never content**. If a project wants it structural regardless of PII, the real control is `httpIntegration({ maxIncomingRequestBodySize: 'none' })` — note `'none'`, not `'never'`. `includeLocalVariables: false` IS correct and needed for Node (locals default ON for Node runtimes).
**Never port an option name across SDKs by symmetry; check that SDK's own docs.**
- `api_key`/`token`/`secret` BY KEY. ⚠️ **This section used to conclude "so the HTTP-header channel is closed out of the box". That was wrong and is corrected here.** The scrubber matches a FIXED list of NAMES — 37 in sentry-sdk 2.68.1 (`DEFAULT_DENYLIST` 33 + `DEFAULT_PII_DENYLIST` 4), of which about a dozen are header-shaped (`authorization`, `cookie`, `token`, `api_key`, `secret`, `x_csrftoken`, …) — so a header the fleet invents sails straight through it. Measured, not assumed: `X-Signing-Secret` matches nothing in that list. Sentry maintaining the list does not help when the name is ours. The header channel is closed by the vendored scrubber's header ALLOWLIST, not by the SDK: unknown header names are … (wrapped further — read the pack)
- message, or a span name is the residual, and it ships. Never interpolate a secret into either. That is the honest boundary — not "only free-text remains after two flags", which was the claim that left four channels open.
**Verify on the CAPTURED EVENT, never the init kwarg.** Swap the SDK transport in a test, make a real dependency raise, and assert on what the event actually contains — asserting the kwarg was passed proves you configured it, not that nothing leaks. The hub's own guard is the pattern to copy: `tests/test_scaffold_glitchtip_security.py` swaps `capture_envelope`, raises inside a real request with six secrets in play, and substring-searches everything the transport would ship — never a field list — asserting the TRANSACTION event as well as the error, since `before_send` never sees it.
- ⚠️ **A project scaffolded before 2026-09-05 has the OLD init — the two flags at best, and the four channels above open.** Nothing back-fills it. Vendor `templates/scaffold/python/glitchtip_init.py` from the hub over your own `src/{package}/glitchtip_init.py`, keeping your `{pkg}` import line and your service name, then prove it with the captured-event guard rather than by reading the diff.
- This is intentional: services without DSN configured never pay for SDK runtime cost
- ⚠️ **Outside that set nothing captures it.** A deliberate 401/403/429 you WANT audited reaches GlitchTip never — widen `failed_request_status_codes` in the init rather than sprinkling `capture_exception` through handlers.
- For `chrome-extension`: use `@sentry/browser` in the popup/options/side-panel (trusted extension pages). **In content scripts, never call the global `Sentry.init`** — a content script shares the host page's `window`, so global-state integrations hijack host-page errors. Build an isolated `BrowserClient` + `Scope` (drop `GlobalHandlers` / `Breadcrumbs`) and wrap with `makeBrowserOfflineTransport` (IndexedDB buffer/flush). Service workers use the `chrome.storage.local` buffer pattern (see Chrome Extension Telemetry below).
- **Caught-and-handled** exceptions: log with stack traces via `exc_info=True` in Python (dedicated JSON attribute, never raw multi-line text). **Unhandled** exceptions (FastAPI 500s, uncaught throws): do NOT log tracebacks — GlitchTip auto-captures them. Log a short event name + `correlation_id` only. See § Error Reporting above.
- In FastAPI: use `contextvars` + ASGI middleware to bind the ID to `structlog` context. Never use `threading.local()` in async code.
- ⚠️ **Why this fleet stops at a correlation ID, and what to name the field.** Probed across ALL THREE fleet hosts (vps1/vps2/vps3): Loki + Prometheus + Grafana only — **no DEDICATED trace backend (Tempo/Jaeger) and no OTel collector on any of them**, and Grafana carries exactly two datasources (loki, prometheus). ⚠️ Not "no spans at all": Sentry-SDK services already emit performance transactions to GlitchTip at `GLITCHTIP_TRACES_SAMPLE_RATE` (§ config above) — that is the only span-shaped signal here, and it is not a queryable trace store. So do NOT instrument distributed tracing here: spans with nowhere to go are cost without a consumer, and "add OpenTelemetry" is over-engineering until a backend exists. A request-scoped correlation ID … (wrapped further — read the pack)
- Never rely on downstream log processors (Promtail, Logstash) for redaction — unredacted data may persist in transport buffers.
- **Never** use high-cardinality values as Loki stream labels. `request_id`, `user_id`, `session_id`, `client_ip` must remain inside the JSON payload only.
- ⚠️ **The label set is the PIPELINE's — an app cannot create one by logging a field.** See § Loki above for the LIVE set; `service`, `environment` and `level` are *not* labels on this fleet, they are JSON fields queried with `| json`.
- `/health` is Authelia-bypassed on all services. The bypass is **resource-based, not domain-bound** — `/health`, `/healthz`, `/metrics`, `/api/health` are bypassed on every domain routed through Authelia (hub direct + spokes via `authelia-vps1@file`). Never protect these paths.
- Never use UUID or timestamp-suffixed container names in Gatus configs or inter-service URLs — they drift per redeploy.
- MV3 service workers are ephemeral (terminated after ~30s idle). Do not hold logs in memory waiting for a batch window.
- Do not propose OTel instrumentation for a fleet service without new evidence. Measured against this stack: OTel **logs** remain the weakest-maturity signal in both Python and JS — exactly the one Loki already serves well — and adoption would mean a stateful Collector on memory-constrained VPSes plus re-instrumenting every project to gain distributed tracing nobody has asked for. The logs + metrics + errors triad stays.
- GlitchTip DSN comes from `GLITCHTIP_DSN` env var injected by the orchestrator from the GlitchTip registrar — do NOT hardcode the DSN in the repo.

### core/57-external-data-sourcing.md  (hit: docs/reference/apis/EXTERNAL_SYSTEMS.md)
- API clients, connectors, webhook handlers). ⚠️ `58-resilience` does NOT auto-load on `connectors/`, `ingest/`, `webhooks/` or `scrapers/` paths — when this pack fires, read 58 explicitly; every rule below that says "the 58 contract" assumes you have.
**Never scrape when an API exists** — an API is a contract you can PROFILE (limits, resume, deprecation channel) and be authorised under; a scraper has no contract, breaks on markup change, and may violate ToS. (APIs still deprecate and break — field 10 exists because they do.)
- ⚠️ **Two lanes, and conflating them is the mistake this ladder invites.** An MCP server is an
- ⚠️ **Check the roster before naming one — do not cite from memory**: the roster is SPLIT (user-level + per-repo `.mcp.json`), canonical at `/opt/fabrik/docs/workstation/mcp-roster.md`, probed by `python3 /opt/fabrik/scripts/sysadmin/mcp_health.py`.
- (pluggable, Anti-Captcha — ⚠️ a BYPASS capability, not a default; see § Hard constraints, "the bypass line") · `adaptive-dispatch` (learns which fetch strategy works per domain) · `web-tools` (env-keyed Exa/Brave/Firecrawl executors — the RUNTIME answer to rung 1) · `proxy-pool` (Postgres-backed proxy pool — ⚠️ same caveat as `captcha-solve`: a bypass capability, never a default) · `api-quota` (`QuotaTracker` parses rate-limit headers, persists quota state and gates calls at the cap; `KeyPool` rotates across many keys — the RUNTIME half of profile fields 1, 2, 7 and 9) · `webhooks` (**outgoing** delivery with HMAC signing — it does … (wrapped further — read the pack)
- (⚠️ OpenRouter-only, see § Hard constraints), `ai-image`, `ai-audio`, `ai-translate`, `search`, `scrape`, `captcha`, `proxy`, `domains`, `email`, `storage`, `backup`, `research-data`, `media-stock`, `infra-platform`, `comms`, `dev-tools`, `unidentified`.
**Derive the count and the category set from the FILE, never from this list** — the file has a non-dict `_README` key, so the guard is not optional: `python3 -c "import json,collections;d=json.load(open('scripts/service_catalog.json'));print(collections.Counter(v['category'] for v in d.values() if isinstance(v,dict)))"`. Grep it by `category` before adding any new vendor; detailed contracts live in `docs/reference/apis/**`. Key via env var, never in code.
**An UNKNOWN never waives the design decision — design to the conservative reading**: unknown cap behaviour ⇒ assume silent truncation and verify counts yourself; unknown idempotency ⇒ assume non-idempotent; unknown resume ⇒ checkpoint on your side; unknown health signal ⇒ treat every 5xx burst as *possibly them* and pause rather than hammer; unknown key expiry ⇒ rotate on a schedule anyway; unknown deprecation channel ⇒ watch the headers; unknown schema stability ⇒ validate strictly at the boundary.
| 4 | **Identity posture** — limits per-key, per-account or per-IP? does the ToS permit multiple accounts/orgs — **cite the clause + URL, or UNKNOWN** | decides whether horizontal scale is even available — see the ⚠️ below |
| 9 | **Credential lifecycle** — does the key/token EXPIRE, on what schedule; can it be rotated with an overlap (two keys valid at once) or only by a hard cut; what does an expired key LOOK like (401? 403? a silent empty 200?) | decides whether rotation can be automated at all, and whether the connector can even tell a dead credential from a dead vendor — an expired key is the failure a retry loop can never fix |
| 11 | **Data contract + EXPECTED YIELD** — the response schema pinned at profile time, and the yield the surface must return; what the vendor changes WITHOUT a version bump (nullable flips, new enum values, added fields, pagination shape); freshness/lag and eventual-consistency window; how deletion shows (tombstone vs vanish); a sample kept for diffing | decides the validation posture: a `200` with a different shape is the failure that corrupts silently — outages page you, drift does not ⚠️ **and the EXPECTED YIELD per page** — a number, or `0 is terminal` — and terminal is a POSITION, never a surface. Zero rows is the contract only where a predecessor proves you are past the data: page N+1 after page N returned rows, a delta past a non-empty cursor, a section index that listed N items. Zero on the FIRST page or a cold cursor is a failed fetch ONLY where the surface also states a `≥1` floor for that position — a listing whose first page always has rows. It is NOT a failure on a search or a filtered section, where an empty first page is the honest answer; those declare `0 is terminal` and nothing else. The incident this closes is the listing case: a challenge page on page 1 of a surface that promised rows, read as "crawl complete, 0 rows". A zero-row page is only a failure against a stated `≥1`; undeclared, it is not one (the scraper-failure-classes bullet under § The Capability Profile). |
- ⚠️ **Field 4 is where an operational question becomes a legal one.** Asking "are multiple accounts permitted, and are limits per-key or per-IP?" is ordinary capacity planning, and the answer is sometimes an explicit yes (separate billing orgs, per-project keys). Provisioning extra accounts or rotating IPs **in order to evade a cap the vendor set** is the circumvention shape from § Hard constraints, and it is an operator decision with the ToS quoted — never an engineering convenience. (That exit is legitimate here on the contractual-gate ground — an authorisation, not a menu.) Record what the ToS actually says; do not infer permission from the absence of a block.
- expiry never happens in production; the `58` last-resort rung that died of an expired credential is this row unfilled.
- model (pydantic `strict=True` / zod `.strict()`, unknown keys rejected deliberately), never silently drop an invalid record, and export the invalid-record RATE as a metric — a spike is the upstream change announcing itself, and a `missing` cluster on one field says which one.
- signature outside the timestamp tolerance. ⚠️ **And it runs a reconciliation poll** — a scheduled pull of "what did you send since <cursor>" against the vendor's list endpoint — because a delivery the provider gave up on during your deploy is otherwise unrecoverable by construction. No list endpoint in field 12 ⇒ say so, and treat every missed webhook as a known gap in §9.
- row 22 alarms on, never the fetch count. A **bot-block** (`403`, a challenge page) is a pause condition, not a retry and not a bypass: `58` says never retry a 403, and § Hard constraints says never solve the challenge — the legal move is `adaptive-dispatch`'s strategy switch (static → rendered), then a pause, then an operator decision.
- ONCE, never hot-looping, and named as human-gated in §2b so nobody expects the queue to wake itself.
- ⚠️ **One subject, one home.** The profile records the VENDOR's contract (measured, dated). YOUR handling of it — timeout/retry config, fallback, pause keys — stays in the per-dependency detail card in `docs/RESILIENCE.md`; that card LINKS the profile and never copies its numbers.
- ⚠️ **Not gate-enforced yet, deliberately — and measured 2026-09-02: 0 of the 6 hub vendor docs in `docs/reference/apis/` carry a profile.** This is a new obligation; per the FIX directive a detector ships after its fire rate is measured, not before. Until then the profile's teeth are the `Profile:` line on the dependency's card in `docs/RESILIENCE.md` — **§2b where the doc has one, otherwise the project's equivalent per-dependency row or section** (the scaffold template does carry the slot, verified at `templates/scaffold/docs/RESILIENCE_TEMPLATE.md:63` § 2b Detail Card Per Dependency, whose first field is `Profile`; but a project scaffolded before it, or one whose … (wrapped further — read the pack)
- **LLM data = OpenRouter ONLY** — never a direct vendor LLM SDK (`openai`, `@anthropic-ai/sdk`). Non-LLM vendor APIs are fine directly.
- **Vendor keys are env vars** (`os.getenv`), never constants; the repo must stay open-sourceable (12F-III).
- Honour a TDM reservation even when your own UA is not the one named. ⚠️ **The token set churns and vendors now run SEVERAL bots each** — Anthropic retired `anthropic-ai` and `Claude-Web` for `ClaudeBot` (training) / `Claude-User` (user-initiated fetch) / `Claude-SearchBot` (indexing), and OpenAI/Perplexity document their user-initiated fetchers (`ChatGPT-User`, `Perplexity-User`) as *not* governed by robots.txt. Read a site's file for the group matching YOUR token, not a 2024 block-list. The machine-readable successor is the IETF AIPREF `Content-Usage` rule (robots.txt directive + HTTP header, a draft that updates RFC 9309 if approved) — honour it … (wrapped further — read the pack)
- **⚠️ THE BYPASS LINE IS THE LEGAL LINE, and it runs straight through our own toolbox.** Reading a logged-out public page is a different act from defeating a control. The moment a pipeline solves a CAPTCHA, replays a session, rotates IPs to beat a block, or evades a hard rate limit, it leaves "public data" territory — and the live litigation wave targets the
- catalog's `proxy` and `captcha` categories are therefore **capabilities, never defaults**: reach for them only where a human operator has decided the specific source warrants it, and say so in the plan.
- on a page you never agreed to are weak against a logged-out fetcher; terms you click through, or accept by creating an account, are an ordinary contract and scraping in breach of them is a straightforward claim. So "we have an account there" changes the answer — check before assuming the public-page reasoning applies.
- ⚠️ **Where the profile lives differs between hub and project** — `EXTERNAL_SYSTEMS.md` is a hub-only index; do not send a project at it.
- `cost` · `capability` · `url` · `status` · `match` · `hosts` · `merged_match`), never the envelope — the twelve profile fields live in the vendor doc, dated and re-verifiable.
- the handler, never onto Authelia. It does not ride the health-path bypass either. **The mechanism is the spec, not a hope:** route the receiver under the service's `shape.bearer_bypass_prefix` (a path-regex, default `^/api/` for `has_bearer_api` services, narrowable) — that IS the explicit public route; there is no per-path bypass field to invent. An UNSIGNED provider that must write cross-tenant is the `needs_payments_ingest` shape.

### core/58-resilience.md  (hit: docs/reference/health-monitoring.md)
- indexed here, never restated; "can actually suffer" is decided by § Per-Scaffold Applicability above. An N/A with a reason is a complete answer, a silent gap is not.
- ⚠️ **Rows 9 and 22 make "autorecovery" honest.** Everything else recovers a *call*; row 9 recovers the
- **`httpx.AsyncClient`** is the only HTTP client for async FastAPI. Never use `requests` (sync, blocks the event loop).
**`wait_random_exponential` / `wait_exponential_jitter`, never bare `wait_exponential`**. Not a style preference: tenacity's own docstring says `wait_exponential`'s intervals "are fixed (i.e. there is no jitter) … *not* suitable for resolving contention between multiple processes for a shared resource". N workers that fail together retry in lockstep and re-hammer the dependency exactly as it recovers — the thundering herd. Every worker fleet here is that "multiple processes" case.
- 400/401/403/404/422 — a permanent client error retried is just load. ⚠️ **`429` and `408` are the exceptions and they matter most**: `429` is the commonest retryable response from a rate-limited vendor and `408` is transient by definition, so a flat "never retry 4xx" makes an agent give up on precisely the failure backoff exists for.
- curve does. ⚠️ **Two legal formats**: delay-seconds (`120`) *or* an HTTP-date (`Wed, 21 Oct 2026 07:28:00 GMT`). Parse both, **clamp both ends** (a hostile `86400` must not park a worker for a day; a hostile `-1` must not raise out of your retry machinery), and fall back to jittered backoff when absent or unparseable. `tenacity.wait_exception` exposes the response for this.
- **⚠️ Inline retry vs PAUSE — and `429` is where they meet.** An inline retry handles a **blip**; a pause handles a **condition**, where every job will hit the same wall and retrying inline just multiplies load across the queue. The test is not the status code but **whether the next job would fail for the same reason**: a single `429` with a short `Retry-After` → honour it inline; repeated `429`s, or a `Retry-After` beyond your inline budget → `set_pause(key, ttl)` so one worker's discovery spares the whole queue. ⚠️ **Clamp that TTL too** (§7a): the inline cap stops a hostile `86400` parking ONE worker for a day; the same unvalidated value in a pause key parks the ENTIRE … (wrapped further — read the pack)
- **⚠️ Retry at ONE layer.** Retries compose multiplicatively: tenacity ×3 in a job, a queue retry ×3 around it, your caller ×3 = up to **27** upstream calls per logical operation, long before a breaker sees a pattern. Pick the owning layer; make the inner ones fail fast. For worker jobs the queue retry IS the retry — do not also wrap the call in `@retry`.
- **⚠️ Retrying a non-idempotent write can double-charge, double-send or double-create.** A `POST` (or non-idempotent `PATCH`) needs an `Idempotency-Key` before it gets a retry — otherwise retrying after a timeout you never saw the response to is a second real mutation. `PUT`/`DELETE` are idempotent by HTTP semantics. `15-api-contracts` owns the SERVING side; this pack owns the caller's question —
- **Graceful fallback** — cached data, a default, or a clear error. Never let an external failure crash your endpoint. ⚠️ That includes the *parse*: a `200` with malformed JSON raises `JSONDecodeError`, which is not an `httpx.HTTPError` and will sail straight past the `except` above.
- Clients call a **self-hosted FastAPI backend** (Pattern A — `fabrik-lib/fastapi-user-auth`), never a database-as-a-service SDK directly. Browser `fetch` / mobile HTTP clients have no built-in timeout or retry — wire them explicitly:
- **Backend outage fallback:** cached data (MMKV on mobile, localStorage on web) or a clear error state — never a blank screen or crash.
- **Auth token refresh:** the app's auth client owns the refresh flow (`35-security-auth.md` Pattern A). Never scatter ad-hoc refresh logic across service calls.
| **`open` returns the fallback IMMEDIATELY**, never a queued timeout wait | you re-pay the read timeout on every call to a dead dependency |
- distributed breaker: never back it with Redis to "share" state. ⚠️ Corollary: with N workers, up to `N × failure_threshold` calls hit a dead dependency first. When that matters the fleet-wide stop is a
- **Never auto-run migrations at startup** — a one-shot deploy step (`30-ops` § Release & Admin).
- ⚠️ **The "fail readiness first, then drain" step in every Kubernetes guide does NOT apply here by default** — it lets a load balancer deregister one replica while its siblings serve, and this stack does not set `deploy.replicas` on app services (`30-ops`). Add it only with real multi-replica Traefik routing; unconditionally it buys a longer outage per deploy, not a shorter one.
- **The signal must arrive.** Shell-form `CMD` makes `/bin/sh` PID 1, which never forwards SIGTERM — exec-form, or `sh -c "exec ..."` (`30-ops`).
- stampedes the origin — a herd from your own cache, not a retry loop, so jitter and backoff never touch it. Coalesce behind a single-flight lock, or refresh before expiry.
| **Backblaze B2** (S3 API, `boto3`) | 30s connect / 120s read | return an error; never block a request on an upload |
- B2 uploads go async via the job queue, never inline in a handler. **boto3 is sync** — keep it in the worker or a thread executor, never inside an `async def` route.
- B2 downloads use server-side presigned URLs (generation is local, no I/O — safe in async). Never proxy file bytes through FastAPI.
- ⚠️ **Never point `HEALTHCHECK` at the dependency-checking endpoint** — one `postgres-main` blip would flip every container on the fleet to `unhealthy` at once. A DB blip degrades readiness; it must never mark the container unhealthy.
- Both endpoints are Authelia-bypassed on all services. Never protect them.
- ⚠️ **Docker does NOT restart an unhealthy container.** `restart: unless-stopped` acts on process EXIT only; health status feeds `up --wait`, `depends_on: service_healthy` and Traefik routing — never a restart. A process that is **wedged but alive** is recovered by nothing in compose: that is the watchdog's Tier A `restart_container` (`60-watchdog`), and it is why the watchdog exists. Never design as if the daemon will do it.
- see pause state without it firing Gatus alerts. ⚠️ That deliberate green is exactly why a long pause must escalate on its own (§ The Four Properties, property 2).
- 1. **Detection is proactive AND reactive.** Beat tasks poll vendor balance APIs *before* workers fail; error classifiers map exceptions to pause keys on the way through. Never one without the other for a critical dependency.
- ⚠️ **So a pause carries its FIRST-set time and escalates exactly once past N× its TTL** (`self-healing` row 4). ⚠️ **`fabrik-lib/alerting/` does NOT give you that property, and the provider-death row 3 of § Provider-death resilience points here rather than repeating it** — NOT the coverage map's row 3, which is the circuit-breaker row. Read at `/opt/fabrik-lib/alerting/__init__.py`, its dedup is a module-level `_last_sent` dict, so it is per-process — and a forked child INHERITS the parent's, rather than starting clean. Four things it is not. (1) Not a latch: the window is `ALERT_MIN_INTERVAL` … (wrapped further — read the pack)
- boot). Sliding TTL: every detection event calls `set_pause(...)` with a fresh TTL — never `setnx`, never permanent. Scope (§2c of the project's RESILIENCE.md):
- your dependencies, never inline at a call site.
- The classifier maps transient signals → pause. Its mirror-image rule is just as load-bearing: **an operational failure must never be written as a terminal *content* verdict.** Model the outcome on two axes — **(transport outcome) × (content evidence)** — and record a content terminal (`deleted`, `private`, `unavailable`…) only on **positive content evidence**. Everything else is transient.
| 1 | **No single point of death** — one model or endpoint dying must not stop the loop | **Declare** the mechanism in §2b. Outage-aware routing is step 1 of OpenRouter's default strategy and a `models` array falls back on **any** error. ⚠️ **The trap: setting `sort` or `order` DISABLES load balancing, and the outage step is *part of* it** — pinning silently opts you out of the protection you think you have (claims row `openrouter-pin-disables-failover`); if you pin, you owe the `models` array explicitly | **Build it**: probe the quality-ordered candidates **once at run start** (never per item) and rebuild the chain from live survivors, best first, so it self-restores on recovery. Base it on `fabrik-lib/health-probe/`; the chain-rebuild helper is `health_probe.live_chain()` (fabrik-lib `health-probe/`, vendored to projects as `libs/health_probe/` by the governance sync). Needs **intra-provider** (2+ models of one provider) AND **cross-provider** diversity |
| 3 | **Absence of progress is alarmed** — N minutes of zero progress fires ONE alert, cleared on recovery | No gateway provides this. Export a monotonically-increasing **progress** counter (rows done, items classified) and alert on *it*, not on error codes. Threshold ≥ 2 full loop runs, a §7a knob. ⚠️ The exactly-one half is YOURS to build — `fabrik-lib/alerting/` does not provide it; see the pause-escalation bullet under § Advanced: Autonomous Pause-State Pipeline → The Four Properties for what it actually does and why — this file's own section, not `RESILIENCE.md` §7 | Same |
| Worker clears `dispatched:<id>` flag when paused | Worker MUST keep the flag on pause-skip (queue bloat) |
| Backup that has never been restored to staging | Run §10 drill within 30 days or it doesn't exist |
| A fallback chain whose **bottom rung has never been executed** | Exercise the last resort on a schedule — an untested fallback is a silently-dead one, and the chain is a rung shorter than its author believes |
- one-shot migration step boot must never do
- [ ] Retries use **jittered** backoff (`wait_random_exponential`/`wait_exponential_jitter`, never bare `wait_exponential`) on transient errors only.
- naming only `TimeoutException`/`ConnectError` never retries a 429.
- state — never a blank screen.

### core/90-bootstrap-scripts.md  (hit: docs/infrastructure/vps-bootstrap-plan.md, docs/infrastructure/vps-hub-rebuild.md, docs/infrastructure/vps-spoke-rebuild.md)
**If you see this message, switch to `ozgur@<ip>` and re-run. Do not retry with `root@<ip>`.**
- `ozgur@<ip>`. Do not test root first.
- the single-quoted remote program as one string literal and never parses it, so the remote-bash syntax error WILL NOT be caught by `bash -n` of the local script — only by an actual ssh execution.
- Every dependency-install step (apt, npm, pip, systemd-unit creation) MUST be a no-op when its outcome is already present. Probe with `command -v` (the POSIX builtin, which looks a name up the way the shell will) — not `which`, which is non-standard:
- already-bootstrapped VPS — every step should print `already installed` or `already configured`, never re-do work.
- higher unused number). Do not use `vps-drill` or other free-form names — the script will reject them.
**Prevention:** fail2ban never bans an address in `ignoreip`. Adding the operator's IP and the mesh range in a `/etc/fail2ban/jail.d/*.local` drop-in (or at runtime with `sudo fail2ban-client set sshd addignoreip <ip>`) retires this whole lockout class; the bootstrap scripts do not do it yet.
- the log, the script never runs, and the absent log looks like "it ran and printed nothing". Cron runs the line with `/bin/sh`; the shell's error goes to cron's mail (the crontab owner, or `MAILTO`), and on a box with no mail agent cron discards it. The journal (`journalctl -t CRON`) then shows only that the job ran and that its output was discarded — never the shell's error — so the writability probe below is the diagnostic, not the log.
- Founding incident: `scripts/sysadmin/liveness_audit.py:10-11` — the Claude-config DR backup had never once run from cron for exactly this reason. Reproduced again 2026-08-29 (`touch /var/log/x` → `Permission denied` for the WSL user), when a plan copied an existing `>> /var/log/…` line verbatim from a working precedent and shipped the same defect; only a native Opus reviewer caught it.
- naming — letters, digits, underscores and hyphens only), so a template installed as `vps-sysadmin.cron` never runs.
- ⚠️ **Not mechanically gated, deliberately.** Dozens of `>> /var/log/` redirects exist across this repo's docs, scripts and templates, and most are correct — VPS root cron writing pre-created files. A check flagging all of them would fire mostly on legitimate lines, and a rule that is routinely waived teaches agents that the gate's findings are advisory. Writability depends on the user and the host; only the author can resolve it, which is why this is a rule you apply rather than a check that fires.

### core/self-healing.md  (hit: docs/reference/health-monitoring.md)
- AGENT USAGE: Pick the failure class, walk the ladder top-to-bottom, stop at the first step that resolves. Never invent a step. Never skip a step. -->
- [`60-watchdog`](60-watchdog.md) — the escalation engine and the owner of its tiers. Tier A acts automatically (it registers `restart_container`, `clear_file_cache`, `scale_concurrency`, `pause_worker`); Tier B is opt-in; Tier C escalates — and carries the **approved-write lane** (`drop_queue_items`, `rotate_locks`), off by default; **Tier D** (opt-in, Telegram-gated) applies a tested code fix with auto-rollback. ⚠️ Registered is not runnable — see **What the sidecar can execute today** below.
- Each row reads left-to-right: **Symptom** (an observable signal) → **First response** (a `58-resilience` primitive or the module that implements it) → **Fallback** (another primitive or a `60-watchdog` action) → **Escalate** (operator-bound). The agent picks the row matching the active failure, walks left-to-right, and **stops at the first step that resolves**. Never skip rightward.
**⚠️ Row 10 is NOT the deadman timer, and the difference is the whole point.** The Tier-C deadman below (`spec.watchdog.deadman_timeout_seconds`, 60–3600, default 300 s, rendered as `WATCHDOG_DEADMAN_TIMEOUT`) measures **operator silence** — it arms only
- **What the sidecar can execute today:** the model returns each action with its params, and `check_proposal` refuses anything off the offered menu, or with a bad or missing param, before a side effect (fabrik-lib D-412). The model's menu is `restart_container` + `escalate_apprise` until the spec lists more in `watchdog.llm_actions` (fabrik-lib D-412): `clear_file_cache` and `pause_worker` (Tier A) run once listed; `wipe_redis_cache` and `reset_db_pool` (Tier B, port defaulting to 8000) run once listed AND `auto_tier_b: true`. `scale_concurrency`, `drop_queue_items`, `rotate_locks` and `install_log_drop_rule` are never offered, and `create_fix_pr` has its own lane (`propose_fix_prs`) — this ladder names three of the never-offered ones (`scale_concurrency` and `drop_queue_items` in row 2, `rotate_locks` in row 8): in those rows the watchdog step resolves to Tier C escalate plus the deadman restart. Treat each row's first response as the step that actually heals.
- If a failure class doesn't appear in the table above, the rule is: **add the row to this pack first, then the response logic to the code.** Never silently invent a self-healing response — it'll diverge from the operator's mental model and break the ladder's discipline.
- 4. **Self-healing without a visible signal.** A pause flag, breaker, or rate-limit reject that doesn't increment a counter and emit a structured log line is invisible — when it misfires, you can't tell. Every ladder step MUST emit a counter AND a `structlog.info()` (or `pino.info()`) row carrying the resource name + reason; without that, the next operator audit has no way to tell the difference between "step fired and recovered" and "step never ran". **Tier-D steps (stabilize / remediate / apply / rollback) are held to the same bar:** each MUST emit a counter + structured log AND write the `incidents` / `approvals` / `deploys` tables — an unaudited or irreversible code-remediation is not self-healing, it's an unreviewed deploy.
- 2. **Fallback — `pause-state` (Redis-backed).** When `signups_per_ip_per_minute` for a specific IP stays high after the first defense's per-IP cap fires, the worker emits an incident; the watchdog sidecar reads the inbox and proposes Tier A `pause_worker` with `resource=signup_<ip_hash>` (the action accepts `^[a-z][a-z0-9_]{0,31}$` and a TTL of 5–3600 s, so truncate the hash to fit — and it is unreachable today, above, so until upstream carries parameters the app sets this pause itself with `pause_state.set_global_pause(...)`). Every signup-handling worker checks `pause_state.is_paused("signup_<ip_hash>")` from the vendored fabrik-lib `pause-state` (the scaffold's own `pause_state.py` has no `is_paused`), with `PAUSE_KEY_PREFIX` equal to `<project_id>:pause:`, and bails without touching the DB. Never gate other workers on `is_globally_paused()` while per-IP keys share the prefix — it reports ANY key under it, so one IP would stop them all.
- [ ] The per-project ladder does not count on a watchdog step that is never offered (`scale_concurrency`, `drop_queue_items`, `rotate_locks`): each such row's healing step is the app's own first response, and the doc says the watchdog step escalates. If the approved-write lane is wanted once it is reachable, the project `.env` sets `WATCHDOG_ALLOW_DB_WRITES=true` and the RW DSN is provisioned.

# promote-to-check_* tail elided (the full mandates are above)
```

| Class | Status |
|---|---|
| FLOOR core/35-security-auth.md | CLEAN — no auth, secret or credential surface in any Touches path (digest row; pass 1 slice A) |
| FLOOR core/25-data-postgres.md | CLEAN — no database, schema or migration path in any Touches list (digest row; pass 1 slice A) |
| FLOOR core/30-ops.md | FIXED — every alloy service carries a memory limit (T02, T03 V10 rows); pass 1 added the V10 cite to T02 (C12) |
| FLOOR 12-FACTOR | FIXED — the digest lacked the row; pass 1 added it (C7): no app config or backing-service binding changes |
| MATCHED core/10-python.md | CLEAN — T04b's Python edits are set members and strings; no logging path changes (digest row) |
| MATCHED core/40-documentation.md | FIXED — pass 2 N1: a rename and every inbound link now share one ticket (T05c), so each whole-tree `check_doc_links.py` Gate is satisfiable; pass 1 C-1/C-2 added the missing link and EXTERNAL_SYSTEMS rows |
| MATCHED core/45-testing-strategy.md | FIXED — pass 1 C-3 graded V6 and the Gate S list in T06; B5 added the image-absent skip in T01 |
| MATCHED core/55-observability.md | FIXED — pass 1 B1: `loki_write_*` exists only after a push, so T04b's probe pushes to a throwaway Loki (reproduced live by slice B, pass 2) |
| MATCHED core/57-external-data-sourcing.md | CLEAN — T07 edits the existing EXTERNAL_SYSTEMS.md rows; no new vendor profile |
| MATCHED core/58-resilience.md | CLEAN — matched by a doc name only; no resilience mechanism changes |
| MATCHED core/90-bootstrap-scripts.md | FIXED — pass 1 C5: `bash -n` on every edited script in the T02, T03 and T04b Gates (each parses clean at the pin, slice B pass 2) |
| MATCHED core/self-healing.md | CLEAN — matched by a doc name only; no ladder step changes |
| Recurrence: fail-open vs fail-closed on every gate/guard | FIXED — pass 2 N1 (a Gate that could never go green); T01's docker/image skip states its reason instead of passing silently (B5) |
| Recurrence: cost/quota/limit accounting edges (unknown≠0, per-call vs batch) | CLEAN — READ budgets re-measured per doc ticket (spine § Evidence); `check_plan_tickets` 0 findings; slice A's T04b size estimate REFUTED by the canonical budget model |
| Recurrence: boundary/sentinel/prefix collisions | FIXED — pass 1 C9 carved the throwaway rehearsal projects out of the no-host constraint; port 12345 checked with `ss -ltn` in T06 preflight |
| Recurrence: behavior-without-a-test | FIXED — pass 1 C-2/C-3 added rows for EXTERNAL_SYSTEMS, V6 and Gate S; BC roll-up 44 = 44, verbatim |

## Pass Ledger

Combined hash = `find <plan-dir> -name '*.md' -print0 | sort -z | xargs -0 md5sum | md5sum` (first 12), taken before
each row is written.

| Pass | Seats | Counters | Method | md5(start) → md5(end) |
|---|---|---|---|---|
| Pass 1 | opus×1 (A spine) + sonnet×1 (B T01–T04b) + sonnet×1 (C T05a–T07) · full partitioned pass | found: 22, new: 22, confirmed: 20, fixed: 20, unexecuted: 0, edits: 20 | method: re-derivation — every path:line re-read at 0a3f55377, the Promtail sweep re-run, B1 measured on a cold `alloy run`; C-4 REFUTED (the row already says "each" doc), C-5 RECORDED — by design (I14: the infra mail is a superset of § Lifecycle) | 3414167114de → 341073a2a915 |
| Pass 2 | opus×1 + sonnet×2 (the round-1 owners) · delta over 0a3f55377..50f16b917 + one hop | found: 4, new: 4, confirmed: 2, fixed: 2, unexecuted: 0, edits: 2 | method: re-derivation — all 20 claims re-verified; N1 executed in a scratch copy (`git mv` then `check_doc_links.py` names DEPLOYMENT_ARCHITECTURE.md); persona mismatch read against spec § Personas :18-21; slice A's T04b budget REFUTED by `check_plan_tickets` (0 findings); slice C's "tell" channel RECORDED — measured (wording; changes no behaviour) · own-fix: 2 (round 1) | 341073a2a915 → 165a86fc2d8c |
| Pass 3 | opus×1 + sonnet×1 (round-1 owners of A and C; B verified clean in pass 2) · closing round over 50f16b917..ad76234bd | found: 0, new: 0, confirmed: 0, fixed: 0, unexecuted: 0, edits: 0 | method: re-derivation — the persona fix and N1 re-verified against the pin; no new defect | 165a86fc2d8c → 165a86fc2d8c |

## Residual unknowns

- Resolved: which file deploys the hub compose (none; spec U1); the spoke volume classification home (condition 4).
- Open: U2, whether port 12345 is free on each spoke host network. Resolution: the runbook's preflight `ss -ltn`.
  On a clash, the spoke flag and the Prometheus targets take another free port.
- Open: Alloy's exact metric names for the observability audit. Resolution: T04b reads them from a local
  `alloy run`'s `/metrics` (spec ledger cv-04).
