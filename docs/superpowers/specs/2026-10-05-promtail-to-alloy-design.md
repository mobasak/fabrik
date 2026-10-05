# Promtail → Grafana Alloy — the fleet log shipper migration

Status: CONVERGED (/fabrik-spec-review, 2026-10-05, 5 passes: confirmed 20 → 10 → 5 → 4 → 0)
Profile: delta — every IN intake item maps to code that exists today (the three Promtail services, their two
configs, the bootstrap step that renders the spoke stack, the Prometheus job and the Gatus check that watch
them); the delta swaps the shipper binary and keeps the pipeline. The two OUT-OF-SCOPE items (I8, I13) point at
their own work items. The constraints digest is written in full because the delta touches a pack-relevant
surface (`core/55-observability.md` describes the shipper).

Work item: W-aec7365b (mail 01M1EQ3NCA98EF178ZY366V47T). Research ledger:
`docs/reference/research/2026-10-05-promtail-to-alloy-ledger.md` (`check_research_ledger` green).

## Personas

- **The operator** opens the maintenance window and runs the cutover per host; step budget per host: one file
  placement, one stop, one start, one battery to read; rollback is one file restore and one `up`. The operator
  also runs the Gate S cleanup window (D6), which is a VPS change too.
- **The fleet agent** (author of the plan) lands every repo change and proves it locally; never touches a VPS.
  It also holds the two duties that outlive the window: it reads V9 daily until Gate S and authors the cleanup
  change when Gate S is reached, and it sends infra the rule-pack and command-corpus edits once the window has
  passed its battery (§ Lifecycle).
- **Log consumers** — `fabrik logs <service>` (`src/fabrik/cli.py:846`, LogQL `{container_name=~".*{service}.*"}`),
  the audit scripts (`scripts/audit/05-observability.sh:77-78`), and any agent querying Loki through Grafana.
  They see the same labels and streams before and after; nothing they run changes.

## Goal

Replace Promtail 3.4.2 with Grafana Alloy on all three fleet hosts, with the same Loki labels, the same streams,
no lost lines at the switch, and Promtail kept defined-but-stopped with a one-step rollback until Alloy is
proven.

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

How each host's stack is changed: the hub's monitoring compose is a hand-maintained standalone stack on vps1
(`docs/reference/health-monitoring.md:45-46`; `scripts/vps_apply_limits.sh:8-10` — "The hand-composed monitoring
and ingress stack never does" pass through `fabrik apply`), and `infra/vps1/monitoring/compose.yaml` is its
repo-of-record (`tests/test_vps_apply_limits.py:400,416`). The scripted hub syncs are
`scripts/sync_prometheus_to_vps.sh` and `scripts/sync_gatus_to_vps.sh` (`--diff` read-only, `--push` to vps1);
both push from `FABRIK_ROOT`, default `/opt/fabrik`, the master checkout (`sync_prometheus_to_vps.sh:31`,
`sync_gatus_to_vps.sh:35`). Spokes are changed by re-rendering bootstrap step 11's
templates (`bootstrap-vps.sh:704-738`), which today ships exactly two files, `compose.yaml` and `promtail.yaml`.
Two more copies of the hub compose sit in the repo — `configs/monitoring-compose.yaml:29-44` and
`specs/infrastructure/monitoring-stack.yaml:28-38` — with no deploy role, no memory limits and missing services;
their retirement is W-589865a0.

Configs: hub `configs/promtail/promtail-config.yaml`, spokes `scripts/bootstrap/templates/promtail.yaml.template`
(binds `{{SPOKE_MESH_IP}}:9080`, pushes to `{{HUB_MESH_IP}}:3100`). Both: one static job on
`/var/lib/docker/containers/*/*log`, labels `job=containerlogs`, `host=<vpsN>`; stages json → json(attrs.tag) →
regex `container_name` → labels `container_name`,`stream` → (hub only) drop `^ocoron-com-backup-1$` → output. No
stage sets the timestamp, so every entry is stamped when the shipper reads it (ms-11).

Watchers: Prometheus job `promtail-spokes` scrapes `10.99.0.2:9080` and `10.99.0.3:9080`
(`configs/prometheus/prometheus.yml:70-80`; the hub's own Promtail is not scraped), and the generic alert
`ServiceUnhealthy` fires on `up == 0` for 2 minutes (`configs/prometheus/rules/alerts.yml:117-120`); Gatus
endpoint `promtail` checks `http://promtail:9080/ready` with failure-threshold 3 at a 60 s interval
(`configs/gatus/apps/observability-agents.yaml:5-14`). The memory ceiling table carries `promtail 256`
(`scripts/vps_apply_limits.sh:56`, D-119/D-122/D-124), derived in
`docs/superpowers/specs/2026-09-04-vps1-container-memory-limits-design.md` (the script's AFTER-EDIT target,
`:2`, and "Change a number THERE first", `:15`). The boot reconciler runs a plain `docker compose up -d` per
stack (`scripts/systemd/fabrik-compose-boot.sh:33`).

Other code that names the Promtail container, port or config: `scripts/audit/05-observability.sh:77-78,146`,
`scripts/audit/06-backup.sh:88`, `scripts/bootstrap/bootstrap-vps.sh:738` (`--filter name=promtail`),
`scripts/vps_sync.py:154,673`, `scripts/generate_vps_inventory.py:67,73`, `scripts/sysadmin/proactive-check.sh`,
`scripts/bootstrap/bootstrap-config.sh:120,217`, `configs/gatus/README.md`, `agents-fabrik.md`,
`.windsurf/rules/CLAIMS.yaml:732`, six sources under `commands/_sources/`, and 10 lines in 4 rule packs
(`command grep -n -i promtail .windsurf/rules/core/*.md`).

Live readings (read-only, 2026-10-05): Loki label names over 24 h = `container_name, filename, host, job,
service_name, stream` (ms-05); fleet ingest 1,068.6 B/s total, spokes ≈ 50 B/s each (ms-06); 7-day max memory:
hub Promtail 151 MiB working set, spoke Promtail 35 MiB RSS (ms-07); the hub runs Docker Compose 2.40.3 (ms-07,
cadvisor label). No Grafana dashboard or alert rule queries a `promtail_*` metric or names `job="promtail-spokes"`
(`command grep -rn -i promtail configs/prometheus configs/grafana configs/alertmanager` → only the job block);
the generic `up == 0` rule above covers every job.

## The delta — chosen approach (B: Alloy running the converter's output, file tailing)

**D1 — The config is the converter's output, committed.** `alloy convert --source-format=promtail` (grafana/alloy
v1.20.1) was run on the hub config and on the spoke template rendered for vps2: rc 0, only the two generic
warnings (tracing; metric names), and a 1:1 component map — `loki.source.file` on the same glob with the same
static labels, `loki.process` with `stage.json` ×2, `stage.regex`, `stage.labels`, (hub) `stage.drop`,
`stage.output`, and `loki.write` to the same push URL (ms-01, ms-02, cv-03, cv-05). The plan commits that output
as `configs/alloy/config.alloy` (hub) and `scripts/bootstrap/templates/alloy.alloy.template` (spokes, the
rendered output with the `{{…}}` placeholders put back — the Promtail template is not loadable YAML until
rendered, ms-11). V1 proves the committed files equal the converter's output; after Gate S the Promtail configs
are deleted and the Alloy files are the source. The committed files carry no hand edits: D3's listen address and
D4's storage path are `alloy run` flags in each compose `command:`, and the legacy positions path is the
converter's own.

**D2 — The switch is an ordered stop → start per host, never a parallel run.** The official migration page does
not address gaps or duplicates (mp-02). Running Alloy alongside Promtail against a null sink (mp-04) does not fit
here: both shippers would read the same files through the same glob. Per host, in one sequence with no plain
`up -d` in between: (a) keep the current compose file as `compose.yaml.pre-alloy` and place the new compose and
Alloy config; (b) `docker compose stop promtail` — a graceful stop writes Promtail's positions file (pt-01);
(c) `docker compose up -d alloy` — Alloy imports those positions (D4); (d) battery. Order: vps3, then vps2
(spokes, ≈ 50 B/s each, lowest blast radius), then vps1; each host passes its battery before the next starts.
The lines written between (b) and (c) are not lost: they stay in the json-file logs and Alloy reads them from
the imported offset — stamped at read time like every line (ms-11), so they land seconds late, not missing. On a
spoke the window renders the files the way bootstrap step 11 does but does not run step 11 itself: step 11 ends
in `up -d --remove-orphans`, which would start Alloy while the running Promtail container keeps running.

**D3 — Alloy's HTTP server replaces Promtail's port, and the watchers move after the last host.** Alloy serves
`/metrics` and `/-/ready` (cv-06) on `--server.http.listen-addr`, default `127.0.0.1:12345` (cv-07); the
converter does not carry Promtail's `http_listen_address` (ms-02). Hub: `0.0.0.0:12345` inside the container on
the `fabrik` network, no host port. Spokes: `<SPOKE_MESH_IP>:12345` on the host network (the flag goes in the
compose template's `command:`), reachable from vps1 because UFW allows the whole mesh subnet
(`scripts/bootstrap/bootstrap-vps.sh:404-408`). The watcher change — Prometheus job `promtail-spokes` → `alloy`
with targets `alloy:12345` (hub, newly scraped), `10.99.0.2:12345`, `10.99.0.3:12345`; Gatus `promtail` →
`alloy`, `http://alloy:12345/-/ready` — is pushed with the two sync scripts run with `FABRIK_ROOT=<the branch worktree>`. Before vps1's
step (b), two read-only checks: the two-dot `git diff master HEAD -- configs/prometheus configs/gatus` in the
branch shows the watcher hunks and the `configs/gatus/README.md` rename and nothing else — two-dot, because the
three-dot form diffs from the merge-base and hides what master changed since the branch point, which is exactly
what a push from the branch would revert; and the Prometheus script's `--diff` lists only `prometheus.yml` and
the Gatus script's only `apps/observability-agents.yaml` (the scripts' `--diff` compares per-file md5s against
vps1, `sync_prometheus_to_vps.sh:87-101`, so it confirms the file set, not the content). Right after vps1's step (c), only the two `--push` runs remain, so the Gatus
switch beats its 3 × 60 s failure threshold. While the spokes are switched first, their old
`promtail-spokes` targets read `up == 0` and `ServiceUnhealthy` would fire after 2 minutes: the window opens with
an Alertmanager silence on `job="promtail-spokes"` and closes it after the watcher change, and the per-host V8
reads Alloy's endpoints directly until then. The sysadmin bot's proactive check queries Prometheus directly
(`scripts/sysadmin/proactive-check.sh:147-148`, `max_over_time(up[10m])==0`), so its `target_down` for a
switched spoke is expected until the watcher change; the window's runbook names it as expected noise. Every other consumer named in § What exists today moves to the
`alloy` name, port 12345 and Alloy's metric names (cv-04 — metric names differ) in the same change: the two
audit scripts, the bootstrap verify filter, `vps_sync.py`'s classification sets, the inventory generator,
`proactive-check.sh`, `bootstrap-config.sh` (D7) and `configs/gatus/README.md`; `agents-fabrik.md`,
`.windsurf/rules/`, `CLAIMS.yaml` and `commands/_sources/` go to infra (§ Lifecycle).

**D4 — Positions hand over, then live in Alloy's own volume.** The converter emits `legacy_positions_file =
"/run/promtail/positions.yaml"` (ms-01). The doc names Grafana Agent Static Mode, and says the conversion "only
occurs if the new positions file doesn't exist" (cv-11); Alloy's source reads the legacy path and never writes
it (cv-11). Executed locally: from a read-only mount, Alloy converted a Promtail-format file and shipped only the
lines after the stored offset, and after a restart it did not re-import (ms-09). The alloy service mounts the
existing `promtail-positions` volume read-only at `/run/promtail` and a new named volume `alloy-data` at
`/var/lib/alloy/data` as `--storage.path` (cv-07), where `loki.source.file` keeps its own positions from then
on. Both services sit in the same compose file, because a named volume belongs to its compose project.

**D5 — Memory ceilings from measurement.** Alloy's sizing rule is about 120 MiB per 1 MiB/s ingested (cv-09);
the fleet ingests about 1 KB/s (ms-06), so the ceiling is set by Alloy's fixed overhead, measured locally against
this box's 19 container log directories: 83.18 MiB under a 96 MiB cgroup cap, no OOM (ms-08). That is 87 % of
96 MiB, too close. Ceilings: hub **256M** (unchanged; Promtail already peaks at 151 MiB there, ms-07); spokes
**128M**, cpus 0.25 kept (spoke ingest ≈ 50 B/s). The hub ceiling row `alloy 256` is added to
`docs/superpowers/specs/2026-09-04-vps1-container-memory-limits-design.md` first and then to
`scripts/vps_apply_limits.sh` beside `promtail 256`, as the script's header requires; `tests/test_vps_apply_limits.py`
follows for the hub compose. The spoke ceiling lives in the compose template, which that test does not read, so
V10 checks it.

**D6 — Rollback is one file restore, and Promtail stays defined until Gate S.** The new compose files keep the
promtail service under `profiles: [rollback]`, so it is defined and stopped and its `promtail-positions` volume
stays declared: a stopped service under an inactive profile is neither started nor removed by `docker compose up
-d --remove-orphans` (ms-03), and the boot reconciler runs plain `up -d` (`fabrik-compose-boot.sh:33`). Rollback
restores the previous file: `cp compose.yaml.pre-alloy compose.yaml && docker compose up -d --remove-orphans`,
which starts Promtail and removes the alloy container as an orphan. A stop-and-start rollback that leaves the
new file in place is NOT used: a plain `up -d` at the next boot starts the stopped alloy again beside Promtail
(ms-10). Promtail resumes from its own positions file, which Alloy only read (cv-11, ms-09), so it re-ships the
lines Alloy sent since the switch; because entries are stamped at read time (ms-11), those re-shipped lines get
new timestamps and Loki keeps both copies (lk-03 dedups only identical timestamps). The duplicate span is
bounded by how long Alloy ran before the rollback, and a roll-forward after a rollback (no re-import, ms-09)
duplicates the rollback span the same way. **Gate S** (V8 and V9 green on all three hosts for 14 days, read by
the fleet agent) triggers a follow-up change, applied in an operator window, that removes the promtail service,
the `promtail-positions` volume, the `.pre-alloy` files and the two Promtail configs, and retires the
`promtail 256` ceiling the way D5 adds one — the memory-limits spec row first, then `scripts/vps_apply_limits.sh`,
the `"promtail"` entry of `tests/test_vps_apply_limits.py:402` and the `monitoring_promtail-positions` row of
`scripts/bootstrap/bootstrap-config.sh:217`.

**D7 — Image pinned, platform declared, volume classified.** `grafana/alloy:v1.20.1` (cv-01),
`platform: linux/amd64` (cv-02), `restart: unless-stopped`, like every other monitoring service. Bootstrap's
volume classification (`scripts/bootstrap/bootstrap-config.sh:217`) gains `monitoring_alloy-data` as
recomputable beside `monitoring_promtail-positions`.

**D8 — The repo changes and the mirrors land after the window.** Nothing deploys from a merge (§ What exists
today), and the `infra/` mirrors are "Pulled from the live" files (`infra/README.md:3-4`). So the branch carries
the new hub compose (as the `infra/vps1/monitoring/compose.yaml` change), the spoke templates and bootstrap step
11, the configs, the consumers of D3 and the docs; the window copies the hub compose and config from that
branch; the branch merges after the window's battery, when every changed mirror and doc describes the live
fleet. If the window rolls back, the branch is held until a later window passes. Bootstrap step 11 is extended in
the same change to render and ship `alloy.alloy` beside the compose file and to verify `name=alloy`, so a
rebuilt spoke comes up on Alloy.

## Contract deltas

None. No data contract, UI design or `spec.shape` changes: the shipper is fleet infrastructure, not a service
spec, and the Loki label set — the only contract consumers read — is held identical (Validation V4).

## Rejected alternatives

- **A — Alloy with `discovery.docker` + `loki.source.docker`** (Grafana's Docker tutorial, mp-05): needs
  `/var/run/docker.sock` mounted, refreshes its container list once a minute by default (dd-01), has no file
  path to produce the live `filename` label, and contradicts `core/55-observability.md:59` (the shipper reads
  the glob, "not via docker.sock"). Panel: killed by 3 of 3 judges.
- **C — Fluent Bit** (and Vector, mp-12 to mp-14): lean and maintained, but no converter exists, so the stage
  chain and labels are re-authored and re-proven by hand in a new config language, and it is not the successor
  the pack names (`core/55-observability.md:54`). Panel: killed by 3 of 3 judges.
- **D — the Docker Loki logging driver**: keeps logs in memory and drops them when Loki is unreachable (mp-11).
  Cut before the panel.
- **`alloy run --config.format=promtail`** (mp-01): runs the old YAML as a transition step. It keeps the EOL
  config format alive and still needs every change in D3 to D8, so it saves nothing over committing the
  converted file.
- **A parallel shadow run** (mp-04): see D2.

## Lifecycle

The repo change is built and proven on `worktree-fleet`; the live switch is the operator's maintenance window
(D2), a VPS change the spec and its plan never make; the branch merges through infra after the window's battery
(D8). Gate S (D6) is the soak, read daily by the fleet agent, followed by the cleanup change in a second operator
window. The text infra owns that names Promtail — the 10 lines in 4 rule packs that `command grep -n -i promtail
.windsurf/rules/core/*.md` prints, `.windsurf/rules/CLAIMS.yaml:732`, `agents-fabrik.md` and the six
`commands/_sources/` files — is mailed to infra by the fleet agent, with the exact edits, once the window has
passed its battery, so each describes the live fleet.

## External dependencies

`loki.write` pushes to `/loki/api/v1/push`, the push API Promtail uses (mp-10); the Loki 3.4 release notes merge
Promtail into Alloy (mp-08), and Loki 3.4's structured-metadata extraction is a server-side feature that needs no
change here (mp-09). Loki ignores a line only when it matches the previous line's timestamp and text, and the
querier dedups only entries with the same nanosecond timestamp, labels and text (lk-03); neither applies to a
re-ship stamped at read time, which is why D6 counts rollback duplicates instead of assuming them away.

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
| Bootstrap idempotency | "Every dependency-install step (apt, npm, pip, systemd-unit creation) MUST be a no-op when its outcome is already" | `.windsurf/rules/core/90-bootstrap-scripts.md:142` | the extended step 11 stays re-runnable on a fresh spoke |
| Remote-block verification | "run `bash -n scripts/bootstrap/bootstrap-vps.sh` (catches LOCAL parser" | `.windsurf/rules/core/90-bootstrap-scripts.md:135` | V2 runs it on every bootstrap edit |

`core/35-security-auth.md` and `core/25-data-postgres.md` (FLOOR): unconstrained — no auth, secret or database
surface changes. The image is amd64 upstream, not ours to build (`core/30-ops.md:24` governs images we build).

## Shape / infra implications

No `specs/services/*.yaml` changes. New named volume `alloy-data` per host (D7). No new host port on the hub; a
new mesh-bound port `12345` on each spoke.

## Documentation landing sites

The plan enumerates every hit of `command grep -rln -i promtail docs/ scripts/ templates/ configs/` at plan time
and dispositions each one (a current-state claim → rewrite, history → leave); the infra-owned text of § Lifecycle
is listed in the infra mail instead. Current-state docs it will find include `docs/SERVICES.md`,
`docs/DEPLOYMENT_ARCHITECTURE.md`, `docs/infrastructure/vps-complete-inventory.md`,
`docs/infrastructure/vps-status.md`, `docs/infrastructure/vps-urls.md`,
`docs/infrastructure/prometheus-app-metrics-setup.md`, `docs/infrastructure/grafana-dashboards-setup.md`,
`docs/infrastructure/vps-fleet-architecture.md`, `docs/reference/architecture.md`,
`docs/reference/health-monitoring.md`, `docs/infrastructure/promtail-noise-filter-setup.md` (renamed for Alloy,
INDEX row moved), `docs/infrastructure/vps-spoke-rebuild.md`, `docs/infrastructure/vps-hub-rebuild.md`,
`docs/operations/{spoke,hub}-restore-inventory.md`, `scripts/bootstrap/README.md`,
`templates/scaffold/docs/RESILIENCE_TEMPLATE.md:568` (synced — one table cell) and the audit prompts under
`docs/infrastructure/audit-prompts/`.

## Cost

No money: Alloy is free and replaces a free binary. Memory: +32 MiB ceiling per spoke (96 → 128M), hub
unchanged. One operator window of about 30 minutes for three hosts, and a second short one at Gate S.

## Validation

Local, before the window (the plan's build phases):
- **V1** render `promtail.yaml.template` with fixed values, run `alloy convert` on it and on
  `configs/promtail/promtail-config.yaml`, and diff each output against the committed Alloy file (the spoke
  template rendered with the same values); the diff is empty.
- **V2** `alloy run` loads both configs without error in a container with no network (rendered spoke template
  included); `bash -n` on every edited bootstrap script; `docker compose config` on every edited compose file.
- **V3** positions import on the real shape: a Promtail positions file naming a real local container log at a
  known offset, mounted read-only — only the lines after the offset are shipped, the conversion log line
  appears, and a restart ships nothing already shipped (the method of ms-09).
- **V4a** label parity, locally: Alloy tailing local containers into a throwaway Loki 3.4.2 produces exactly
  the label names `container_name, filename, host, job, service_name, stream`.
- **V5a** rollback rehearsal on the real compose files (local copies, a throwaway project name): forward switch,
  then the D6 rollback, then a plain `up -d` (the boot reconciler's command) — Promtail runs and no alloy
  container exists.
- **V10** every compose service carries `deploy.resources.limits.memory`: `tests/test_vps_apply_limits.py`
  extended to the hub's alloy service, and a check on `monitoring-agent.compose.yaml.template` for the spoke
  alloy service's 128M.

In the window, per host (read-only reads through Grafana and `docker ps`):
- **V4** Loki label names over the 15 minutes after the switch equal the six live names (ms-05).
- **V5** the set of `container_name` values with lines in the 15 minutes after equals the set in the 15 minutes
  before, for that `host` (the V6 canary writes its pre-markers 5 to 10 minutes before step (b), inside that window, so it is in both).
- **V6** no lost and no re-shipped lines on the handover path: before step (a) of D2 the operator starts a
  long-running canary container (no `--rm`), and 5 to 10 minutes before step (b) writes numbered pre-markers to
  its stdout (`docker exec <canary> sh -c 'echo <pre-n> > /proc/1/fd/1'`), which Promtail ships and records in its
  positions; between steps (b) and (c) a
  unique marker is written the same way; after (c), within 2 minutes, Loki holds the marker exactly once and
  each pre-marker still exactly once for that `host` — a failed import would re-read the file from its start
  (no stored position) and ship the pre-markers a second time. The canary is removed after the battery.
- **V7** no duplicate burst: that host's per-minute line count in the first 10 minutes stays under 3× its median
  of the hour before.
- **V8** Alloy `/-/ready` returns 200 and `/metrics` answers, read directly (`alloy:12345` on the hub net,
  `<mesh-ip>:12345` from vps1); after the watcher change, Prometheus target `alloy` is up for all three hosts
  and Gatus `alloy` is green.
- **V11** `fabrik logs <a service on that host>` returns lines written after the switch.

After: **V9** each host's alloy container shows `OOMKilled=false` and a restart count of 0 after 24 h
(`docker inspect`); V8 and V9 green for 14 days is Gate S.

## Decisions taken

- B over A and C: 3-seat judge panel, unanimous for B (A and C each killed on three reality challenges and a
  rule-pack line); D cut before the panel (§ Rejected alternatives).
- Ordered stop → start per host over a parallel shadow run (D2).
- Port 12345 everywhere, watchers renamed to `alloy` after the last host, under an Alertmanager silence (D3).
- Spoke ceiling 128M from a measured 83 MiB under a 96 MiB cap (D5, ms-08).
- Rollback restores the previous compose file; Promtail stays under `profiles: [rollback]` until Gate S, then a
  follow-up change removes it (D6).
- The branch merges after the window passes, so mirrors and docs land true (D8).
- The node-api `exposes_metrics` question is its own fix, not this spec (Intake I8).

## Open / blocking unknowns

- **U2** whether anything else binds `12345` on a spoke's host network — a read-only `ss -ltn` in the window's
  preflight; on a clash, the spoke flag takes another free port and the Prometheus targets follow.
- Resolved in review: U1 (which repo file deploys the hub compose) — none; the hub stack is hand-maintained and
  `infra/vps1/monitoring/compose.yaml` is its repo-of-record (§ What exists today, D8).

## Review record

`/fabrik-spec-review`, 2026-10-05 — Pass Ledger below. Passes 2 to 4 were delta rounds; the scope-growth stop fired after pass 3 (two of three rounds at or above two-thirds own-fix), pass 4 re-verified the fixed set with a rule-3 rewrite, and pass 5 closed it.

| Pass | seats · axes re-checked (intake · personas · facts · vendor · approach · completeness · constraints) | counters | method | spec md5 (start → end) |
|-----:|---|---|---|---|
| Pass 1 | opus×1 (D-sections, digest, Validation, Lifecycle, Decisions) + sonnet×1 (header, personas, grounding, intake) + sonnet×1 fabrik-researcher (external facts) · all axes | found: 25, new: 22, confirmed: 20, fixed: 20, unexecuted: 0, edits: 20 | method: citation — full pass by section; every candidate executed by the orchestrator: D8 deploy path (no repo file deploys the hub stack), read-time timestamps (grep 0), reboot after rollback (ms-10), watcher order vs `up == 0`, template not YAML, spoke step 11 ships two files, consumer and pack enumerations, ceiling-spec AFTER-EDIT, V6 cannot fail, 18 vs 19, Decisions vs D, Profile vs I8/I13, persona duties, docs sweep scope, Promtail stop flush (pt-01), mp-07, mp-08, mp-11; refuted 2 (positions keyed by labels — ms-09 shipped from the offset with no read-only error; `stop` under an inactive profile — ms-03 ran it); U1 resolved | 02e5ce54… → 729cc892… (taken with this row's md5 cell reading `(below)`; the closing pin differs by that cell alone) |
| Pass 2 | opus×1 + sonnet×1 + sonnet×1 fabrik-researcher (the round-1 slice owners) · delta over the round-1 fix hunks + one hop | found: 13, new: 12, confirmed: 10, fixed: 10, unexecuted: 0, edits: 10 | method: re-derivation — all 20 round-1 confirmed defects re-checked closed; inside the fix hunks, executed: the sync scripts push from `FABRIK_ROOT` = master (`sync_prometheus_to_vps.sh:31`, `sync_gatus_to_vps.sh:35`) so D3 names the branch root and a `--diff` first, `sync_gatus_to_vps.sh` exists, `THERE first` is `:15`, `proactive-check.sh:147` bypasses Alertmanager, V6 tested file discovery not the handover, the Gate S list skipped the spec/test/volume rows, the committed configs carry no hand edits, the Loki driver declares `ReadLogs: true` (ld-01) so the dual-logging clause was removed, pt-01 repinned to v3.6.11, ledger rows lk-01/cv-08 re-dispositioned; refuted 1 (found ≠ new on Pass 1: 20 confirmed + 2 refuted = 22 distinct, 3 in-round re-raises); recorded 1 (health-monitoring.md:46 also says "mirror" — measured, supports the claim); 1 duplicate (the lk-01/lk-03 ledger record, folded into the ledger re-disposition); own-fix: 10 of 10, round 1 | 729cc892… → 0830c080… (taken with this cell reading `(below)` and "all 21"; corrected to 20 after the hash) |
| Pass 3 | opus×1 + sonnet×1 + sonnet×1 fabrik-researcher (the round-1 slice owners) · delta over the round-2 fix hunks + one hop | found: 7, new: 7, confirmed: 5, fixed: 5, unexecuted: 0, edits: 5 | method: re-derivation — all 10 round-2 confirmed defects re-checked closed (V6's partial closure reopened as C2); executed: the scripts' `--diff` compares md5s against vps1 only (`sync_prometheus_to_vps.sh:87-101`), so D3's guard is a `git diff master...HEAD` over configs/prometheus and configs/gatus run before vps1's step (b) (C1, and C4 — only the pushes remain after (c)); `tail_from_end` defaults to false (cv-12), so a canary with no stored position passes V6 whether or not the import worked — V6 now ships pre-markers first and asserts each once (C2), which also keeps the canary in V5's before-set (C3); the Pass 2 row counted 13 found and 12 dispositions — new corrected to 12, the lk-01/lk-03 record a duplicate; refuted 0; recorded 2 (sync_prometheus_to_vps.sh:60 find precedence — outside the spec, the script owner's; the spoke volume `monitoring-agent_promtail-positions` is absent from bootstrap-config.sh:217 — pre-existing, one hop out, for the plan); own-fix: 5 of 5, round 2 — with round 2 at 10 of 10, two of the last three rounds are at or above two-thirds own-fix: SCOPE-GROWTH STOP — hunting suspended, the remainder round re-verifies this fixed set only | 0830c080… → 9914c2d6… (taken before the found/recorded counts were corrected from 6/1 to 7/2) |
| Pass 4 | opus×1 + sonnet×1 (the round-1 owners of the two slices with open claims; the facts slice restated at 6/6) · remainder round under the scope-growth stop: the round-3 fixed set only | found: 5, new: 5, confirmed: 4, fixed: 4, unexecuted: 0, edits: 3 | method: re-derivation — C2, C4 and the Pass 2 recount closed; executed: the three-dot `git diff` diffs from the merge-base and showed nothing for a master-only change that the two-dot form shows (A); the branch's configs/gatus diff legitimately carries the README rename (B); each sync script lists only its own file (B, wording); pre-markers written 15 minutes or more before the switch fall outside V5's before-window (C); recorded 1 (the file-set check is forward-looking until the branch carries the change); own-fix: 4 of 4, round 3; class rewrite — D3 guard sentence and V5/V6 timing, rewritten in one batch (rule 3), so the next round is the closing round | c3944c8f… (the round-4 pin) → f5c10783… (taken with this cell reading `9914c2d6… → (below)`) |
| Pass 5 | opus×1 + sonnet×1 (round-1 slice owners) · closing round over the rule-3 rewrite and the Pass 4 row | found: 2, new: 2, confirmed: 0, fixed: 0, unexecuted: 0, edits: 0 | method: re-derivation — the four rewritten items re-executed closed: the two-dot form shows a master-only change the three-dot form hides, 3 of the 22 files under configs/prometheus and configs/gatus name promtail (the README among them), each script's LOCAL_DIR holds only its own file, V5 and V6 agree on 5 to 10 minutes before step (b); the Pass 4 row's dispositions, edits, own-fix and md5 chain re-derived consistent; refuted 1 ("lists only" read as an unconditional claim — it is the pass condition of one of the "two read-only checks", and a stray DRIFT or ORPHAN line correctly fails it); recorded 1 — measured (V5's "the switch" not tied to a step; D2 keeps (b) to (c) to seconds, so no behaviour changes); both wording notes routed to W-332b562c for the plan; standing clean since their last full pass: every other class | 791764db… → 791764db… ✓ (the closing pin; this row and the Status line are the only later edits) → **CONVERGED** |

## Intake Inventory

| I# | Item (anchored) | Disposition | Where |
|---|---|---|---|
| I1 | "convert the existing Promtail config (`alloy convert`)" | IN | § The delta D1; V1 |
| I2 | "keep the promtail service defined and stopped until Alloy is proven shipping (rollback)" | IN | D6; V5a |
| I3 | "cover every VPS that runs the shipper (hub vps1 and spokes vps2/vps3 if they ship to Loki over WireGuard)" | IN | § What exists today (all three ship); D2 order |
| I4 | "the Loki labels/streams the dashboards and alerts depend on" | IN | § What exists today (no dashboard or alert reads Promtail metrics; the generic `up == 0` rule is handled in D3; the consumers are `fabrik logs` and the audits); V4, V5 |
| I5 | "the compose memory limit invariant" | IN | D5; V10 |
| I6 | "a verification battery (Loki receives the same streams, Grafana panels and alerts unchanged)" | IN | § Validation V4–V9, V11 |
| I7 | "The live switch is a VPS change that needs the operator's window — the spec and plan must not touch a VPS" | IN | § Lifecycle; D2, D8 |
| I8 | "`templates/node-api/defaults.yaml:14` sets `exposes_metrics: true` while no Node metrics module is scaffolded — ground and decide whether it belongs in this spec or its own fix" | OUT-OF-SCOPE | independent of the shipper (a scaffold default, not log shipping); filed as its own item W-c81379ef |
| I9 | "Ground every claim in the live repo … and every external fact … live" | IN | every `path:line` above; the research ledger |
| I10 | "Promtail EOL date, Alloy image/version, `alloy convert` behaviour, Loki push compatibility" | IN | § Why this exists (eol-01..06); D7 (cv-01); D1 (ms-01, ms-02); § External dependencies (mp-08..10, lk-03) |
| I11 | "Pool OFF (D-181): native seats only" | IN | research, panel and review seats were native Task seats |
| I12 | "finished work → scripts/merge_request.py" | IN | § Lifecycle; D8 |
| I13 | (surfaced) the watchdog's `install_log_drop_rule` targets a Promtail update URL no spec sets | OUT-OF-SCOPE | dormant today and cross-repo (fabrik-lib); filed as backlog item W-1feb4dfa |
| I14 | (surfaced) rule packs, command sources and other infra-owned text that name Promtail as the live shipper | IN | § Lifecycle — infra mailed the exact edits after the window's battery |
| I15 | (surfaced) a spoke ceiling of 96M is below Alloy's measured footprint | IN | D5 |
| I16 | (surfaced in review) two stale repo copies of the hub monitoring compose claim a `fabrik apply` deploy | OUT-OF-SCOPE | not part of the shipper switch; filed as W-589865a0 |
