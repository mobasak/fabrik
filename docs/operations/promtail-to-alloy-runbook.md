# Promtail → Grafana Alloy — the operator's window runbook

**What:** the live switch of the fleet's log shipper from Promtail (end of life 2026-03-02) to Grafana Alloy
`v1.20.1`, one host at a time: vps3, then vps2, then vps1.
**Who:** the operator runs every step. The single exception is the close (§ 5): once all three hosts pass their
battery, the operator tells the fleet agent, and the fleet agent sends the merge request and the infra mail.
**Where:** run from the `fleet-alloy` branch worktree, `/opt/fabrik/.claude/worktrees/fleet-alloy`, on the WSL
box. `ssh vps` is the hub (vps1); `ssh vps2` and `ssh vps3` are the spokes.
**Design:** `docs/superpowers/specs/2026-10-05-promtail-to-alloy-design.md` (D-651) and its plan
`docs/development/plans/2026-10-08-plan-1-promtail-to-alloy/` (D-656). Every step below cites the decision it
carries out.
**Budget:** about 30 minutes for the three hosts, plus 15 minutes of battery reading per host.

Never run `docker compose --profile rollback up` while Alloy runs: compose profiles ADD services, so it starts
Promtail beside Alloy and both ship the same files (spec § The delta › D2). Rollback is § 4, a file restore.

## 0. Preflight

Run on the WSL box from the branch worktree. Set the window stamp once:

```bash
cd /opt/fabrik/.claude/worktrees/fleet-alloy
TS=$(date -u +%Y%m%dT%H%MZ); echo "$TS"
git fetch -q origin && git status -sb | head -1   # must show fleet-alloy, nothing to pull
```

**Port check (spec § Open / blocking unknowns U2).** Port 12345 must be free on each spoke's mesh IP. Pass
condition: no line for `:12345`. On a clash, pick a free port, change the spoke template's
`--server.http.listen-addr` and the two spoke targets in `configs/prometheus/prometheus.yml` on the branch, and
re-run this check before going on.

```bash
for h in vps2 vps3; do echo "== $h"; ssh "$h" 'sudo ss -ltn | grep -E ":12345\b" || echo "12345 free"'; done
```

**Alertmanager silence on the old spoke job (spec § The delta › D3).** The spokes switch first, so their old
`promtail-spokes` targets read `up == 0` until the watcher push in § 3; the silence keeps `ServiceUnhealthy` quiet.

```bash
ssh vps "sudo docker exec alertmanager amtool silence add --alertmanager.url=http://localhost:9093 \
  --duration=3h --author=operator --comment='alloy-window-$TS' 'job=\"promtail-spokes\"'"
```

**Expected noise.** The sysadmin bot's proactive check queries Prometheus directly
(`scripts/sysadmin/proactive-check.sh:147-148`, `max_over_time(up[10m])==0`), so it reports `target_down` for each
switched spoke until the watcher push. That is expected in this window; nothing else is.

**The canary (spec § Validation V6).** Start it on every host before that host's step (a). It must be
long-running and must NOT use `--rm`: its json-file log is what Promtail and then Alloy tail.

```bash
for h in vps3 vps2 vps; do ssh "$h" 'sudo docker run -d --name alloy-canary --restart no alpine:3.20 sleep infinity'; done
```

**Loki query helper.** Every battery read below goes through Loki's HTTP API from a throwaway curl container on
the hub's `fabrik` network:

```bash
loki() { ssh vps "sudo docker run --rm --network fabrik curlimages/curl:latest -sG http://loki:3100$1 $2"; }
```

## 1. vps3

Spoke. Files are rendered on the WSL box exactly the way bootstrap step 11 renders them
(`scripts/bootstrap/bootstrap-vps.sh` `step_11_install_monitoring_agents`, the same three `sed` substitutions),
but step 11 itself is NOT run: it keeps no `compose.yaml.pre-alloy` copy (so § 4's rollback would have nothing to
restore) and it removes Promtail and starts Alloy in one go, with no point between the stop and the start to
write the V6 switch marker (spec § The delta › D2, D6).

Two variables per host: `S` is the ssh alias, `H` is the `host` label the host's logs carry in Loki
(`configs/alloy/config.alloy` and the spoke template set it). They differ only on the hub (`S=vps`, `H=vps1`).

```bash
S=vps3; H=vps3; SPOKE_NAME=vps3; SPOKE_MESH_IP=10.99.0.3; HUB_MESH_IP=10.99.0.1
```

**V6 pre-markers — 5 to 10 minutes before step (b).** Write five numbered pre-markers to the canary's stdout;
Promtail ships them and records them in its positions file.

```bash
for n in 1 2 3 4 5; do ssh "$S" "sudo docker exec alloy-canary sh -c 'echo alloy-pre-$TS-$H-$n > /proc/1/fd/1'"; done
```

### (a) Keep the old file, place the new files

```bash
R=$(mktemp -d)
for t in monitoring-agent.compose.yaml promtail.yaml alloy.alloy; do
  sed -e "s|{{SPOKE_NAME}}|$SPOKE_NAME|g" -e "s|{{SPOKE_MESH_IP}}|$SPOKE_MESH_IP|g" -e "s|{{HUB_MESH_IP}}|$HUB_MESH_IP|g" \
    "scripts/bootstrap/templates/$t.template" > "$R/$t"
done
mv "$R/monitoring-agent.compose.yaml" "$R/compose.yaml"
scp -q "$R/compose.yaml" "$R/promtail.yaml" "$R/alloy.alloy" "$S:/tmp/"
ssh "$S" 'cd /opt/monitoring-agent && sudo cp compose.yaml compose.yaml.pre-alloy && \
  sudo mv /tmp/compose.yaml compose.yaml && sudo mv /tmp/promtail.yaml promtail.yaml && sudo mv /tmp/alloy.alloy alloy.alloy && \
  sudo chown root:root compose.yaml promtail.yaml alloy.alloy && sudo chmod 644 compose.yaml promtail.yaml alloy.alloy && \
  sudo docker compose config -q && echo PLACED'
```

Pass condition: `PLACED`. Nothing is started or stopped in this step.

### (b) Stop Promtail

Note the time of step (b): every 15-minute window of the battery is anchored on it.

```bash
B=$(date -u +%s); echo "step (b) at $(date -u -d @$B)"
ssh "$S" 'cd /opt/monitoring-agent && sudo docker compose stop promtail'
ssh "$S" "sudo docker exec alloy-canary sh -c 'echo alloy-switch-$TS-$H > /proc/1/fd/1'"   # the V6 switch marker, between (b) and (c)
```

A graceful stop writes Promtail's positions file (spec § The delta › D2, D4).

### (c) Start Alloy

```bash
ssh "$S" 'cd /opt/monitoring-agent && sudo docker compose up -d alloy && sudo docker ps --filter name=^alloy$ --format "{{.Names}} {{.Status}}"'
C=$(date -u +%s)
```

Pass condition: `alloy Up` (the anchored filter keeps `alloy-canary` out of the answer). Alloy imports Promtail's positions from the read-only `promtail-positions` mount
(spec § The delta › D4). There is no plain `up -d` anywhere between (a) and (c).

### (d) Battery

Read each check; a FAIL stops the window and goes to § 4. Windows are anchored on step (b): the 15 minutes
before step (b) and the 15 minutes after step (b).

- **V8 — Alloy answers on its own endpoint.** From vps1 over the mesh (the watchers have not moved yet).

  ```bash
  ssh vps "curl -s -o /dev/null -w '%{http_code}\n' http://$SPOKE_MESH_IP:12345/-/ready; curl -s http://$SPOKE_MESH_IP:12345/metrics | grep -c '^loki_'"
  ```
  Pass: `200`, and a count above 0.

- **V6 — every marker exactly once.** Within 2 minutes of step (c), each pre-marker and the switch marker appear
  exactly once for this host. A failed positions import would re-read the log from its start and ship the
  pre-markers a second time. The query reads only the canary's own stream: on the hub, Loki's query log would
  otherwise carry the marker text too.

  ```bash
  for m in alloy-pre-$TS-$H-1 alloy-pre-$TS-$H-2 alloy-pre-$TS-$H-3 alloy-pre-$TS-$H-4 alloy-pre-$TS-$H-5 alloy-switch-$TS-$H; do
    printf '%s ' "$m"; loki /loki/api/v1/query_range "--data-urlencode 'query=count_over_time({host=\"$H\", container_name=\"alloy-canary\"} |= \"$m\" [1h])' --data-urlencode start=$((B-900))000000000 --data-urlencode end=$((C+120))000000000" \
      | python3 -c 'import json,sys; r=json.load(sys.stdin)["data"]["result"]; print(sum(int(v[1]) for s in r for v in s["values"][-1:]) if r else 0)'
  done
  ```
  Pass: every line prints `1`.

- **V4 — this host's label names over the 15 minutes after step (b).** They equal the six live names.

  ```bash
  loki /loki/api/v1/labels "--data-urlencode 'query={host=\"$H\"}' --data-urlencode start=${B}000000000 --data-urlencode end=$((B+900))000000000"
  ```
  Pass: exactly `container_name, filename, host, job, service_name, stream` (ignore `__name__`-style internals
  if any).

- **V5 — the same containers before and after.** The set of `container_name` values with lines for this host
  in the 15 minutes after step (b) equals the set in the 15 minutes before step (b) (the canary is in both).

  ```bash
  for w in "$((B-900)) $B" "$B $((B+900))"; do set -- $w
    loki /loki/api/v1/label/container_name/values "--data-urlencode 'query={host=\"$H\"}' --data-urlencode start=${1}000000000 --data-urlencode end=${2}000000000"; echo
  done
  ```
  Pass: the two lists are equal.

- **V7 — no duplicate burst.** This host's per-minute line count over the first 10 minutes after step (c) stays
  under 3 × its median for the hour before step (b). Read it in Grafana Explore with
  `sum(count_over_time({host="vps3"}[1m]))` over the two ranges — Grafana does not expand shell variables, so type
  this host's label (`vps3`, `vps2` or `vps1`) in place of `vps3`.

- **V11 — `fabrik logs` still answers.** From the WSL box: `fabrik logs <a service on this host>` returns lines
  written after step (c).

When every check passes, go to the next host. When any check fails, stop and roll back this host (§ 4).

## 2. vps2

Same steps as § 1 with:

```bash
S=vps2; H=vps2; SPOKE_NAME=vps2; SPOKE_MESH_IP=10.99.0.2; HUB_MESH_IP=10.99.0.1
```

Write the V6 pre-markers 5 to 10 minutes before step (b), then run (a), (b) with the switch marker, (c) and the
(d) battery exactly as in § 1, every 15-minute window anchored on this host's step (b). Start only after vps3
passed its battery.

## 3. vps1

The hub. Its compose file is the branch's `infra/vps1/monitoring/compose.yaml`, which IS the live
`/opt/monitoring/compose.yaml` plus the `alloy` service (spec § The delta › D8). Start only after vps2 passed its
battery.

```bash
S=vps; H=vps1
```

**V6 pre-markers — 5 to 10 minutes before step (b).**

```bash
for n in 1 2 3 4 5; do ssh "$S" "sudo docker exec alloy-canary sh -c 'echo alloy-pre-$TS-$H-$n > /proc/1/fd/1'"; done
```

### (a) Keep the old file, place the new files

```bash
scp -q infra/vps1/monitoring/compose.yaml vps:/tmp/compose.yaml
scp -q configs/alloy/config.alloy vps:/tmp/config.alloy
ssh vps 'cd /opt/monitoring && sudo cp compose.yaml compose.yaml.pre-alloy && sudo mkdir -p configs/alloy && \
  sudo mv /tmp/config.alloy configs/alloy/config.alloy && sudo mv /tmp/compose.yaml compose.yaml && \
  sudo chown root:root compose.yaml configs/alloy/config.alloy && sudo chmod 644 compose.yaml configs/alloy/config.alloy && \
  sudo docker compose config -q && echo PLACED'
```

Pass condition: `PLACED`.

### D3 read-only checks — before step (b)

Both are PASS CONDITIONS. They prove that the two `--push` runs right after step (c) change only the watcher
files (spec § The delta › D3; W-332b562c note 2).

```bash
git diff --stat master HEAD -- configs/prometheus configs/gatus
FABRIK_ROOT=/opt/fabrik/.claude/worktrees/fleet-alloy bash scripts/sync_prometheus_to_vps.sh --diff
FABRIK_ROOT=/opt/fabrik/.claude/worktrees/fleet-alloy bash scripts/sync_gatus_to_vps.sh --diff
```

- Pass: the two-dot `git diff master HEAD` lists `configs/prometheus/prometheus.yml`,
  `configs/gatus/apps/observability-agents.yaml` and `configs/gatus/README.md` and nothing else. It is two-dot on
  purpose: the three-dot form diffs from the merge-base and hides what master changed since the branch point,
  which is exactly what a push from the branch would revert.
- Pass: the Prometheus `--diff` lists only `prometheus.yml`, and the Gatus `--diff` lists only
  `apps/observability-agents.yaml` (the scripts compare per-file md5s against vps1, so they confirm the file set).
- **STOP on any other DRIFT or ORPHAN line.** Do not push. Merge master into `fleet-alloy`, re-run both checks,
  and continue only when they pass. vps1 is still on Promtail at this point, so stopping costs nothing.

### (b) Stop Promtail

```bash
B=$(date -u +%s); echo "step (b) at $(date -u -d @$B)"
ssh vps 'cd /opt/monitoring && sudo docker compose stop promtail'
ssh "$S" "sudo docker exec alloy-canary sh -c 'echo alloy-switch-$TS-$H > /proc/1/fd/1'"
```

### (c) Start Alloy

```bash
ssh vps 'cd /opt/monitoring && sudo docker compose up -d alloy && sudo docker ps --filter name=^alloy$ --format "{{.Names}} {{.Status}}"'
C=$(date -u +%s)
```

Pass condition: `alloy Up`.

### Watcher push — right after step (c)

Only these two runs remain, so the Gatus switch beats its 3 × 60 s failure threshold (spec § The delta › D3).

```bash
FABRIK_ROOT=/opt/fabrik/.claude/worktrees/fleet-alloy bash scripts/sync_prometheus_to_vps.sh --push
FABRIK_ROOT=/opt/fabrik/.claude/worktrees/fleet-alloy bash scripts/sync_gatus_to_vps.sh --push
```

Then expire the silence. `amtool silence query` filters by matcher (the silence's own `job="promtail-spokes"`),
and `-q` prints only the IDs. Pass condition: the second query lists no active silence.

```bash
ssh vps "sudo docker exec alertmanager amtool silence query --alertmanager.url=http://localhost:9093 -q 'job=\"promtail-spokes\"' \
  | xargs -r sudo docker exec alertmanager amtool silence expire --alertmanager.url=http://localhost:9093"
ssh vps "sudo docker exec alertmanager amtool silence query --alertmanager.url=http://localhost:9093 'job=\"promtail-spokes\"'"
```

### (d) Battery

Run the § 1 (d) V6, V4, V5 and V7 blocks unchanged: `S=vps` and `H=vps1` are set, and every 15-minute window is
anchored on this host's step (b). V8 and V11 differ on the hub:

- **V8 — Alloy answers, and the watchers see it.** The hub's alloy has no host port, so read it from the
  `fabrik` network; then, after the watcher push, Prometheus target `alloy` is up for all three hosts.

  ```bash
  ssh vps "sudo docker run --rm --network fabrik curlimages/curl:latest -s -o /dev/null -w '%{http_code}\n' http://alloy:12345/-/ready"
  prom() { ssh vps "sudo docker run --rm --network fabrik curlimages/curl:latest -sG http://prometheus:9090$1 $2"; }
  prom /api/v1/query "--data-urlencode 'query=up{job=\"alloy\"}'"
  ```
  Pass: `200`; three series, each with value `1`; and Gatus shows `alloy` green.

- **V11 — `fabrik logs <a hub service>`** returns lines written after step (c).

When the battery passes on all three hosts, remove the canaries:

```bash
for h in vps3 vps2 vps; do ssh "$h" 'sudo docker rm -f alloy-canary'; done
```

## 4. Rollback

Per host, in reverse order of the switch (spec § The delta › D6): restore the previous compose file and run
`up -d --remove-orphans`, which starts Promtail and removes the alloy container as an orphan.

```bash
# spoke (H=vps3 or vps2)
ssh "$S" 'cd /opt/monitoring-agent && sudo cp compose.yaml.pre-alloy compose.yaml && sudo docker compose up -d --remove-orphans'
# hub
ssh vps 'cd /opt/monitoring && sudo cp compose.yaml.pre-alloy compose.yaml && sudo docker compose up -d --remove-orphans'
```

Never roll back by stopping Alloy and starting Promtail with the new file in place: the boot reconciler's plain
`up -d` would start the stopped alloy again beside Promtail. If the watchers were already pushed, push the
master versions back with the same two scripts and `FABRIK_ROOT=/opt/fabrik`.

**Duplicate span.** Promtail resumes from its own positions file, which Alloy only read, so it re-ships the
lines Alloy sent since step (c). They are stamped at read time and Loki keeps both copies. The duplicate span is
as long as Alloy ran before the rollback, and a later roll-forward duplicates the rollback span the same way.
Note both spans in the window's notes. After a rollback the branch is held until a later window passes.

## 5. The close

The operator's one act: tell the fleet agent that all three hosts passed their battery.

Then the fleet agent, and only after that signal, runs the one step of this document an agent runs (spec
§ Personas; § The delta › D8; § Lifecycle):

```bash
cd /opt/fabrik/.claude/worktrees/fleet-alloy
python3 scripts/merge_request.py request --review docs/development/reviews/2026-10-08-plan-1-promtail-to-alloy-review.md --item W-aec7365b
```

It sends the live message the command prints, then sends the infra mail of the appendix
(`python3 scripts/mail.py send --to fabrik --to-agent infra --kind finding`, the appendix body on stdin).

## 6. V9 daily and Gate S

**V9, read daily by the fleet agent.** On each host, the alloy container shows `OOMKilled=false` and restart
count 0, and V8 stays green:

```bash
for h in vps3 vps2 vps; do ssh "$h" "sudo docker inspect -f '{{.Name}} oom={{.State.OOMKilled}} restarts={{.RestartCount}}' alloy"; done
```

**Gate S** is V8 and V9 green on all three hosts for 14 days. It triggers a follow-up change, applied in a
second operator window, that removes:

1. the `promtail` service from the hub compose and the spoke template (and its rendered mirrors);
2. the `promtail-positions` volume — classified first (content and size read-only, its row in
   `docs/operations/spoke-restore-inventory.md` and `scripts/bootstrap/bootstrap-config.sh`), deleted only by an
   explicit name on the operator's word;
3. the `compose.yaml.pre-alloy` files on each host;
4. the two Promtail configs (`configs/promtail/promtail-config.yaml`,
   `scripts/bootstrap/templates/promtail.yaml.template`);
5. the `promtail 256` ceiling, retired the way D5 added one: the memory-limits spec row first, then
   `scripts/vps_apply_limits.sh`, the `"promtail"` entry of `tests/test_vps_apply_limits.py`, and the
   `monitoring_promtail-positions` row of `scripts/bootstrap/bootstrap-config.sh`.

## Appendix — the infra mail

Sent by the fleet agent at the close (§ 5), once the window passed its battery. The body below is the mail as
sent; `scripts/mail.py`'s D-035 check reads every section.

<!-- infra-mail:begin -->
WHAT: The fleet's log shipper is now Grafana Alloy v1.20.1 on vps1, vps2 and vps3 (Promtail reached end of life on 2026-03-02). Infra-owned text still names Promtail as the running shipper and needs the edits below.

WHERE: .windsurf/rules/core/55-observability.md:53, :476, :604 and :616; .windsurf/rules/core/12-node.md:69, :71, :89 and :291; .windsurf/rules/core/10-python.md:294; .windsurf/rules/core/60-watchdog.md:101; .windsurf/rules/CLAIMS.yaml (the claim that names Promtail, near :740); agents-fabrik.md:30, :143, :209 and :223; docs/reference/prebuilt-app-containers.md:85 (governance-synced); and six command sources: commands/_sources/fabrik-deploy-verify.md, fabrik-plan-after-chat.md, fabrik-review.md, fabrik-spec.md, fabrik-spec-review.md and fabrik-vision.md.

WHEN: The switch window passed its battery on all three hosts; Promtail stays defined under the compose profile `rollback`, stopped, until Gate S (V8 and V9 green for 14 days).

WHO: fleet (sender, plan 2026-10-08-plan-1-promtail-to-alloy, D-651, D-656) to infra (owner of .windsurf/rules, CLAIMS.yaml, agents-fabrik.md, commands/_sources and the governance-synced docs).

WHY: Root cause — the shipper changed (spec docs/superpowers/specs/2026-10-05-promtail-to-alloy-design.md, D1-D8), and these files are infra's beat, so the plan could not edit them; until they change, the rule packs tell every project that Promtail tails its logs and that `promtail` is a container to expect.

HOW: In each place, name Alloy as the running shipper: container `alloy`, HTTP port 12345 (`/metrics`, `/-/ready`), hub config `configs/alloy/config.alloy`, spoke config `/opt/monitoring-agent/alloy.alloy`, metrics `loki_write_sent_entries_total`, `loki_write_dropped_entries_total`, `loki_source_file_files_active_total`. In core/55-observability.md:53, replace the end-of-life warning with a dated note that the migration landed (Alloy v1.20.1, file tailing of /var/lib/docker/containers, not docker.sock). Keep `promtail` only where a line describes the rollback profile or the history. In docs/reference/prebuilt-app-containers.md:85 replace `grafana/promtail:3.4.2` with `grafana/alloy:v1.20.1`. In the six command sources, rename the shipper in the form each file uses: `Promtail→Loki` (fabrik-plan-after-chat.md, fabrik-spec.md, fabrik-spec-review.md), `Promtail → Loki` (fabrik-review.md:289, fabrik-vision.md:192), `promtail/loki` (fabrik-deploy-verify.md:189, :207) and the bare `Promtail` in fabrik-vision.md:397's core/55 table row all become Alloy.

SYSTEMIC: Any fleet-infrastructure swap leaves infra-owned prose behind, because the plan that makes the swap may not edit those files. The class fix is that a plan which renames a running fleet component lists every infra-owned mention in its spec's Lifecycle section and mails it at the close, which this plan did; re-grep `command grep -rn -i promtail .windsurf/rules agents-fabrik.md commands/_sources docs/reference/prebuilt-app-containers.md` after the edits to confirm only rollback and history mentions remain.
<!-- infra-mail:end -->
