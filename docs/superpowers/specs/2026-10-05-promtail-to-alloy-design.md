# Promtail → Grafana Alloy — the fleet log shipper migration

Status: DRAFT
Profile: delta — every intake item maps to code that exists today (the three Promtail services, their two
configs, the Prometheus job and the Gatus check that watch them); the delta swaps the shipper binary and keeps
the pipeline. The constraints digest is written in full because the delta touches a pack-relevant surface
(`core/55-observability.md` describes the shipper).

Work item: W-aec7365b (mail 01M1EQ3NCA98EF178ZY366V47T). Research ledger:
`docs/reference/research/2026-10-05-promtail-to-alloy-ledger.md` (41 rows, `check_research_ledger` green).

## Personas

- **The operator** opens one maintenance window and runs the cutover per host; step budget: one command per
  host to switch, one to roll back, one battery to read.
- **The fleet agent** (author of the plan) lands every repo change and proves it locally; never touches a VPS.
- **Log consumers** — `fabrik logs <service>` (`src/fabrik/cli.py:846`, LogQL `{container_name=~".*{service}.*"}`),
  the audit scripts (`scripts/audit/05-observability.sh:77-78`), and any agent querying Loki through Grafana.
  They see the same labels and streams before and after; nothing they run changes.

## Goal

Replace Promtail 3.4.2 with Grafana Alloy on all three fleet hosts, with the same Loki labels, the same streams,
no gap and no duplicate burst at the switch, and Promtail kept defined-but-stopped as a one-command rollback
until Alloy is proven.

## Why this exists

Promtail is end of life: "Promtail is end of life (EOL) as of March 2, 2026. Commercial support has ended. No
future support or updates will be provided." (ledger eol-01). Security fixes stopped with the LTS phase
(eol-02); the last release carrying Promtail binaries is Loki v3.6.11 of 2026-05-13 (eol-06), and Loki removed
Promtail as of 3.7.3 (eol-03) — so any future Loki upgrade has no Promtail to pair with. Every host on the fleet
runs it today.

## What exists today (grounded)

| Host | Where | Shape |
|---|---|---|
| vps1 (hub) | `infra/vps1/monitoring/compose.yaml:26-45` (mirror of the live `/opt/monitoring/compose.yaml`; `infra/README.md:6-7` — nothing deploys from `infra/`) | `grafana/promtail:3.4.2`, `fabrik` net, `promtail-positions:/run/promtail`, `/var/lib/docker/containers` ro, mem 256M |
| vps2 / vps3 (spokes) | `infra/vps2/monitoring-agent/compose.yaml:68-88` (vps3 identical bar the IP), rendered by `scripts/bootstrap/bootstrap-vps.sh:704-738` from `scripts/bootstrap/templates/monitoring-agent.compose.yaml.template` | same image, `network_mode: host`, positions volume, mem 96M, cpus 0.25 |

Two more copies of the hub compose sit in the repo: `configs/monitoring-compose.yaml:29-44` (Coolify-era header,
no memory limit on promtail) and `specs/infrastructure/monitoring-stack.yaml:28-38`.

Configs: hub `configs/promtail/promtail-config.yaml`, spokes `scripts/bootstrap/templates/promtail.yaml.template`
(binds `{{SPOKE_MESH_IP}}:9080`, pushes to `{{HUB_MESH_IP}}:3100`). Both: one static job on
`/var/lib/docker/containers/*/*log`, labels `job=containerlogs`, `host=<vpsN>`; stages json → json(attrs.tag) →
regex `container_name` → labels `container_name`,`stream` → (hub only) drop `^ocoron-com-backup-1$` → output.

Watchers: Prometheus job `promtail-spokes` scrapes `10.99.0.2:9080` and `10.99.0.3:9080`
(`configs/prometheus/prometheus.yml:70-80`; the hub's own Promtail is not scraped); Gatus endpoint `promtail`
checks `http://promtail:9080/ready` (`configs/gatus/apps/observability-agents.yaml:5-14`). The memory ceiling
table carries `promtail 256` (`scripts/vps_apply_limits.sh:56`, D-119/D-122/D-124). The boot reconciler runs a
plain `docker compose up -d` per stack (`scripts/systemd/fabrik-compose-boot.sh:33`).

Live readings (read-only, 2026-10-05): Loki label names over 24 h = `container_name, filename, host, job,
service_name, stream` (ms-05); fleet ingest 1,068.6 B/s total, spokes ≈ 50 B/s each (ms-06); 7-day max memory:
hub Promtail 151 MiB working set, spoke Promtail 35 MiB RSS (ms-07); the hub runs Docker Compose 2.40.3 (ms-07,
cadvisor label). No Grafana dashboard or alert rule queries a `promtail_*` metric or `job="promtail-spokes"`
(`command grep -rn -i promtail configs/prometheus configs/grafana configs/alertmanager` → only the job block).

## The delta — chosen approach (B: Alloy running the converter's output, file tailing)

**D1 — The config is the converter's output, committed.** `alloy convert --source-format=promtail` (grafana/alloy
v1.20.1) was run on both configs: rc 0, only the two generic warnings (tracing; metric names), and a 1:1
component map — `loki.source.file` on the same glob with the same static labels, `loki.process` with
`stage.json` ×2, `stage.regex`, `stage.labels`, (hub) `stage.drop`, `stage.output`, and `loki.write` to the same
push URL (ms-01, ms-02, cv-03, cv-05). The plan commits that output as `configs/alloy/config.alloy` (hub) and
`scripts/bootstrap/templates/alloy.alloy.template` (spokes, the same `{{…}}` placeholders the Promtail template
uses), plus a test that re-runs the converter and diffs it against the committed file, so a hand edit to the
pipeline is a visible change, never drift. The only edits on top of the converter's output are the ones D3 and
D4 name.

**D2 — The switch is an ordered stop → start per host, never a parallel run.** The official migration page does
not address gaps or duplicates (mp-02). The field pattern of running Alloy alongside Promtail against a null
sink (mp-04) does not fit here: a second shipper on the same host tails its own container's stdout through the
same glob, and both shippers would read the same files. Instead, per host, in one window:
`docker compose stop promtail` (Promtail flushes its positions on a graceful stop) → `docker compose up -d alloy`
(Alloy imports those positions, D4) → battery. Order: vps3, then vps2 (spokes, ≈ 50 B/s each, lowest blast
radius), then vps1. Each host passes its battery before the next starts. The gap is the seconds between the two
commands, and the lines written in it are not lost: they sit in the json-file logs and Alloy reads them from the
imported offset.

**D3 — Alloy's HTTP server replaces Promtail's port, and the watchers move with it.** Alloy serves `/metrics` and
`/-/ready` (cv-06) on `--server.http.listen-addr`, default `127.0.0.1:12345` (cv-07); the converter does not
carry Promtail's `http_listen_address` (ms-02). Hub: `0.0.0.0:12345` inside the container on the `fabrik`
network, no host port (Traefik is not involved; nothing outside the net calls it). Spokes:
`<SPOKE_MESH_IP>:12345` on the host network, reachable from vps1 because UFW already allows the whole mesh subnet
(`scripts/bootstrap/bootstrap-vps.sh:404-408`). Watchers, in the same change: Prometheus job `promtail-spokes` →
`alloy`, targets `alloy:12345` (hub, newly scraped) + `10.99.0.2:12345` + `10.99.0.3:12345`; Gatus `promtail` →
`alloy`, `http://alloy:12345/-/ready`. Alloy's metric names differ from Promtail's (cv-04, the converter's own
warning); the only consumer is `scripts/audit/05-observability.sh:77-78`, rewritten to Alloy's names in the same
change.

**D4 — Positions hand over, then live in Alloy's own volume.** The converter emits `legacy_positions_file =
"/run/promtail/positions.yaml"` (ms-01, cv-08). The alloy service mounts the existing `promtail-positions`
volume read-only at `/run/promtail` for that import and a new named volume `alloy-data` at
`/var/lib/alloy/data` as `--storage.path` (cv-07), where `loki.source.file` keeps its own positions from then on.
Both services sit in the same compose file, because a named volume belongs to its compose project.

**D5 — Memory ceilings from measurement.** Alloy's sizing rule is about 120 MiB per 1 MiB/s ingested (cv-09);
the fleet ingests about 1 KB/s (ms-06), so the ceiling is set by Alloy's fixed overhead, measured: tailing 18
container logs locally under a 96 MiB cgroup cap, Alloy ran at 83.18 MiB with no OOM (ms-08). That is 87 % of
96 MiB, too close. Ceilings: hub **256M** (unchanged; the hub has more containers and Promtail already peaks at
151 MiB there, ms-07); spokes **128M**, cpus 0.25 kept (spoke ingest ≈ 50 B/s). `scripts/vps_apply_limits.sh`
gains an `alloy 256` row beside `promtail 256`; its test (`tests/test_vps_apply_limits.py`) follows. Battery row
V9 re-reads the real working set after 24 h; a reading above 75 % of the ceiling raises it in a follow-up change.

**D6 — Rollback is one command, and Promtail stays defined until Gate S.** Promtail stays in each compose file
under `profiles: [rollback]`. Measured on Compose 2.40.3, the hub's version: a stopped service under an inactive
profile is neither started nor removed by `docker compose up -d --remove-orphans` (ms-03), and the boot
reconciler runs plain `up -d` (`fabrik-compose-boot.sh:33`), so nothing resurrects it. Rollback:
`docker compose stop alloy && docker compose --profile rollback up -d promtail`. Promtail resumes from its own
positions file, which Alloy only read, so it re-ships the lines Alloy already sent since the switch; Loki keeps
the first of two identical lines in a stream (lk-01), so the re-ship does not double the stream. A roll-forward
after a rollback does NOT re-import (Alloy's own positions now exist) and re-ships from Alloy's last offset —
absorbed the same way. **Gate S** (the soak: 14 days of V8 and V9 green on all three hosts) is when a follow-up
change removes the promtail service, the `promtail-positions` volume, the two Promtail configs and the
`promtail 256` ceiling row.

**D7 — Image pinned, platform declared.** `grafana/alloy:v1.20.1` (cv-01), `platform: linux/amd64` (cv-02),
`restart: unless-stopped`, like every other monitoring service.

**D8 — All four compose copies move together.** The live hub compose is rendered by `fabrik apply` of the
monitoring stack; the plan names which repo copy that is (`specs/infrastructure/monitoring-stack.yaml` or
`configs/monitoring-compose.yaml`) by reading the deploy path, edits that one as the source, and brings the
other copy and the `infra/` mirrors in line in the same change, so no copy keeps describing Promtail as the
running shipper.

## Contract deltas

None. No data contract, UI design or `spec.shape` changes: the shipper is fleet infrastructure, not a service
spec, and the Loki label set — the only contract consumers read — is held identical (Validation V4).

## Rejected alternatives

- **A — Alloy with `discovery.docker` + `loki.source.docker`** (Grafana's Docker tutorial, mp-05): needs
  `/var/run/docker.sock` mounted, polls for new containers every 30 s (mp-07), has no file path to produce the
  live `filename` label, and contradicts `core/55-observability.md:59` (the shipper reads the glob, "not via
  docker.sock"). Panel: killed by 3 of 3 judges.
- **C — Fluent Bit** (and Vector, mp-12 to mp-14): lean and maintained, but no converter exists, so the stage
  chain and labels are re-authored and re-proven by hand in a new config language, and it is not the successor
  the pack names (`core/55-observability.md:54`). Panel: killed by 3 of 3 judges.
- **D — the Docker Loki logging driver** (mp-11): keeps logs in memory and drops them when Loki is unreachable,
  and replaces json-file, so `docker logs` stops working. Cut before the panel.
- **`alloy run --config.format=promtail`** (mp-01): runs the old YAML as a transition step. It keeps the EOL
  config format alive and still needs every change in D3 to D7, so it saves nothing over committing the
  converted file.
- **A parallel shadow run** (mp-04): see D2.

## Lifecycle

The repo change lands on `worktree-fleet` and merges through infra like any other branch; nothing deploys from a
merge. The live switch is the operator's maintenance window (D2) — a VPS change the spec and its plan never make.
Gate S (D6) is the soak, followed by the cleanup change. Rule-pack wording that names Promtail
(`core/55-observability.md:49-56,59`, `core/12-node.md:71,89,290`, `core/60-watchdog.md:101`) is infra's beat:
the plan mails infra the exact edits once the window has passed its battery, so each pack keeps describing the
live fleet.

## External dependencies

`loki.write` pushes to `/loki/api/v1/push`, the push API Promtail uses (mp-10); Loki 3.4's release notes merge
Promtail into Alloy without a push-API break (mp-08), and its structured-metadata extraction is a server-side
feature that needs no change here (mp-09). Loki's dedup of identical lines (lk-01) is what makes D6's re-ship
harmless.

## fabrik-lib verdict

Nothing to vendor: no fabrik-lib module ships logs. One dormant interface touches the subject: the watchdog
sidecar's `install_log_drop_rule` posts to `WATCHDOG_PROMTAIL_UPDATE_URL`
(`/opt/fabrik-lib/watchdog/watchdog_sidecar/actions.py:392-413`), wired from `src/fabrik/drivers/watchdog.py:396,
598,1024`; no spec sets it, so the action refuses everywhere today. OUT-OF-SCOPE (Intake I13).

## Constraints digest

| Rule | Verbatim | Where | Effect here |
|---|---|---|---|
| Alloy is the successor via the converter | "Grafana Alloy is the successor (`alloy convert` migrates the config)." | `.windsurf/rules/core/55-observability.md:54` | selects B (D1) |
| Glob, not socket | "(`/var/lib/docker/containers/*/*log`), not via docker.sock — no per-service config needed" | `.windsurf/rules/core/55-observability.md:59` | kills A |
| The label set is the pipeline's | "live: `container_name`, `filename`, `host`, `job`, `service_name`, `stream`." | `.windsurf/rules/core/55-observability.md:61` | V4 holds it identical |
| Low-cardinality labels only | "Loki indexes by low-cardinality labels only." | `.windsurf/rules/core/55-observability.md:60` | no label added |
| Migration is an infra action | "Fleet migration is an infra action, not a per-project one" | `.windsurf/rules/core/55-observability.md:55` | no project repo changes |
| Memory limit mandatory | "`deploy.resources.limits.memory` is mandatory." | `.windsurf/rules/core/30-ops.md:149` | D5 |
| Limits + cpus declared | "compose.yaml has `deploy.resources.limits.memory` + `cpus`" | `.windsurf/rules/core/30-ops.md:187` | spokes keep cpus 0.25 |
| Bootstrap idempotency | "Every dependency-install step (apt, npm, pip, systemd-unit creation) MUST be a no-op when its outcome is already" | `.windsurf/rules/core/90-bootstrap-scripts.md:142` | the bootstrap step that renders the spoke stack stays re-runnable |
| Remote-block verification | "run `bash -n scripts/bootstrap/bootstrap-vps.sh` (catches LOCAL parser" | `.windsurf/rules/core/90-bootstrap-scripts.md:135` | V2 runs it on every bootstrap edit |

`core/35-security-auth.md` and `core/25-data-postgres.md` (FLOOR): unconstrained — no auth, secret or database
surface changes. The image is amd64 Debian-based upstream, not ours to build (`core/30-ops.md:24` governs images
we build).

## Shape / infra implications

No `specs/services/*.yaml` changes. New named volume `alloy-data` per host (bootstrap's volume classification
`scripts/bootstrap/bootstrap-config.sh:217` gains `monitoring_alloy-data` as recomputable, beside
`monitoring_promtail-positions`). No new host port on the hub; a new mesh-bound port `12345` on each spoke.

## Documentation landing sites

`docs/SERVICES.md`, `docs/DEPLOYMENT_ARCHITECTURE.md`, `docs/infrastructure/vps-complete-inventory.md`,
`docs/infrastructure/vps-fleet-architecture.md`, `docs/reference/architecture.md`,
`docs/reference/health-monitoring.md`, `docs/infrastructure/promtail-noise-filter-setup.md` (renamed for Alloy,
INDEX row moved), `docs/infrastructure/vps-spoke-rebuild.md`, `docs/infrastructure/vps-hub-rebuild.md`,
`docs/operations/{spoke,hub}-restore-inventory.md`, `scripts/bootstrap/README.md`,
`templates/scaffold/docs/RESILIENCE_TEMPLATE.md:568` (synced — one table cell), the audit prompts under
`docs/infrastructure/audit-prompts/`. The plan enumerates them from `command grep -rln -i promtail docs/ scripts/
templates/` at plan time and dispositions every hit (current-state claim → rewrite; history → leave).

## Cost

No money: Alloy is free and replaces a free binary. Memory: +32 MiB ceiling per spoke (96 → 128M), hub
unchanged. One operator window of about 30 minutes for three hosts.

## Validation

Local, before the window (the plan's build phases):
- **V1** the committed `config.alloy` and the spoke template equal a fresh `alloy convert` of the Promtail
  configs, plus the D3/D4 edits (test).
- **V2** `alloy run` loads both configs without error in a container with no network (rendered spoke template
  included); `bash -n` on every edited bootstrap script; `docker compose config` on every edited compose file.
- **V3** positions import: a Promtail-format `positions.yaml` naming a real local log file at a known offset,
  mounted read-only; Alloy's own positions file afterwards carries that offset for that path and the read-only
  mount raised no error.
- **V4a** label parity, locally: Alloy tailing local containers into a throwaway Loki 3.4.2 produces exactly
  the label names `container_name, filename, host, job, service_name, stream`.
- **V5a** rollback rehearsal on the real compose files (local copies, a throwaway project name): stop alloy,
  `--profile rollback up -d promtail`, plain `up -d --remove-orphans` leaves promtail stopped and alloy running.
- **V10** every compose service carries `deploy.resources.limits.memory` (`tests/test_vps_apply_limits.py`
  extended to the alloy service).

In the window, per host (read-only reads through Grafana and `docker ps`):
- **V4** Loki label names over the 15 minutes after the switch equal the six live names (ms-05).
- **V5** the set of `container_name` values with lines in the 15 minutes after equals the set in the 15 minutes
  before, for that `host`.
- **V6** no gap: `sum by (host) (count_over_time({host="<h>"}[1m]))` is non-zero for every minute across the
  switch.
- **V7** no duplicate burst: that host's per-minute line count in the first 10 minutes stays under 3× its median
  of the hour before.
- **V8** Alloy `/-/ready` returns 200, Prometheus target `alloy` is up for the host, Gatus `alloy` green.
- **V11** `fabrik logs <a service on that host>` returns lines written after the switch.

After: **V9** Alloy working set after 24 h under 75 % of its ceiling on each host; V8 and V9 green for 14 days
is Gate S.

## Decisions taken

- B over A, C and D: 3-seat judge panel, unanimous for B (A and C each killed on three reality challenges and a
  rule-pack line; see § Rejected alternatives).
- Ordered stop → start per host over a parallel shadow run (D2).
- Port 12345 everywhere, watchers renamed to `alloy` (D3).
- Spoke ceiling 128M from a measured 83 MiB under a 96 MiB cap (D5, ms-08).
- Promtail kept under `profiles: [rollback]` until Gate S, then removed in a follow-up change (D6).
- The node-api `exposes_metrics` question is its own fix, not this spec (Intake I8).

## Open / blocking unknowns

- **U1** which repo copy of the hub monitoring compose `fabrik apply` deploys (D8) — read from the deploy path at
  plan time; it changes which file is the source, not the design.
- **U2** whether anything else binds `12345` on a spoke's host network — a read-only `ss -ltn` in the window's
  preflight; on a clash, the spoke flag takes another free port and the Prometheus targets follow.

## Review record

None yet — `/fabrik-spec-review` is next.

## Intake Inventory

| I# | Item (anchored) | Disposition | Where |
|---|---|---|---|
| I1 | "convert the existing Promtail config (`alloy convert`)" | IN | § The delta D1; V1 |
| I2 | "keep the promtail service defined and stopped until Alloy is proven shipping (rollback)" | IN | D6; V5a |
| I3 | "cover every VPS that runs the shipper (hub vps1 and spokes vps2/vps3 if they ship to Loki over WireGuard)" | IN | § What exists today (all three ship); D2 order |
| I4 | "the Loki labels/streams the dashboards and alerts depend on" | IN | § What exists today (no dashboard or alert reads Promtail metrics; the consumers are `fabrik logs` and the audits); V4, V5 |
| I5 | "the compose memory limit invariant" | IN | D5; V10 |
| I6 | "a verification battery (Loki receives the same streams, Grafana panels and alerts unchanged)" | IN | § Validation V4–V9, V11 |
| I7 | "The live switch is a VPS change that needs the operator's window — the spec and plan must not touch a VPS" | IN | § Lifecycle; D2 |
| I8 | "`templates/node-api/defaults.yaml:14` sets `exposes_metrics: true` while no Node metrics module is scaffolded — ground and decide whether it belongs in this spec or its own fix" | OUT-OF-SCOPE | independent of the shipper (a scaffold default, not log shipping); filed as its own item W-c81379ef |
| I9 | "Ground every claim in the live repo … and every external fact … live" | IN | every `path:line` above; the research ledger (41 rows) |
| I10 | "Promtail EOL date, Alloy image/version, `alloy convert` behaviour, Loki push compatibility" | IN | § Why this exists (eol-01..06); D7 (cv-01); D1 (ms-01, ms-02); § External dependencies (mp-08..10) |
| I11 | "Pool OFF (D-181): native seats only" | IN | research and panel seats were native Task seats |
| I12 | "finished work → scripts/merge_request.py" | IN | § Lifecycle |
| I13 | (surfaced) the watchdog's `install_log_drop_rule` targets a Promtail update URL no spec sets | OUT-OF-SCOPE | dormant today and cross-repo (fabrik-lib); filed as backlog item W-1feb4dfa |
| I14 | (surfaced) rule packs that name Promtail as the live shipper | IN | § Lifecycle — infra mailed the exact edits after the window's battery |
| I15 | (surfaced) a spoke ceiling of 96M is below Alloy's measured footprint | IN | D5 |
