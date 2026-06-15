# Grafana Provisioning & Dashboards

**Last Updated:** 2026-06-15 (corrected Data Freshness: Prometheus global scrape interval is 15 s, not 30 s — `fabrik-services` is the per-job 30 s override. **Prior 2026-06-07:** post-multi-host setup unchanged; aro-wake SLI metrics LIVE on full fleet since 2026-06-06 — `aro_wake_requests_total` gained `status="rate_limited"` value 2026-06-07. Dashboard for `aro_wake_*` series is deliberately deferred per `docs/STRATEGIC_BACKLOG.md` Later tier. PromQL + the 2 alert rules `AroWakeLowSuccessRate` + `AroWakeCostBurnHigh` cover operator needs today; a Grafana panel can be added when ad-hoc PromQL gets tedious. See [`prometheus-app-metrics-setup.md`](prometheus-app-metrics-setup.md#aro-wake-sli-metrics-added-2026-06-06--full-fleet) for the SLI series + scrape pattern.)
**Status:** ✅ Live
**Grafana URL:** <https://monitor.vps1.ocoron.com> (Authelia 2FA required for UI)
**Automation:** `scripts/provision_grafana.sh` — idempotent, re-runnable

---

## What's Provisioned

> **Note:** Datasources are file-provisioned via bind mount — see [`grafana-provisioning-setup.md`](grafana-provisioning-setup.md). The API-based datasource creation in `provision_grafana.sh` is now a redundant no-op for datasources (idempotent) but the script remains the canonical mechanism for **dashboard** imports.

### Datasources (2)

| Name | Type | Internal URL | Notes |
| :--- | :--- | :--- | :--- |
| Prometheus | `prometheus` | `http://prometheus:9090` | Default datasource |
| Loki | `loki` | `http://loki:3100` | Container-stdout aggregator |

Both are created with `access: proxy`.

### Dashboards (8 total)

**3 community dashboards** (imported from grafana.com via `provision_grafana.sh`, tagged `gcom-<id>` for idempotent re-import):

| grafana.com ID | Title | Purpose |
| :--- | :--- | :--- |
| [1860](https://grafana.com/grafana/dashboards/1860) | Node Exporter Full | Host metrics (CPU, RAM, disk, network) from `node-exporter` |
| [193](https://grafana.com/grafana/dashboards/193) | Docker monitoring | Per-container CPU/RAM/net from `cAdvisor` |
| [2](https://grafana.com/grafana/dashboards/2) | Prometheus Stats | Prometheus self-monitoring |

**5 custom Fabrik dashboards** (file-provisioned from `configs/grafana/dashboards/`, tagged `fabrik` — see [`grafana-provisioning-setup.md`](grafana-provisioning-setup.md)):

| File | Title | Purpose |
| :--- | :--- | :--- |
| `00-infrastructure-overview.json` | Fabrik Infrastructure Overview | Fleet-wide CPU, memory, disk, network, container count |
| `10-databases.json` | Fabrik Databases | Postgres + Redis health, connections, query rates |
| `20-containers.json` | Fabrik Container View | Per-container CPU/RAM/net with name filter |
| `30-authelia.json` | Fabrik Authelia | Auth requests, session counts, failed logins |
| `40-meilisearch.json` | Fabrik Meilisearch | Index sizes, search latency, document counts |

### `host` template variable (added 2026-05-31)

Every Fabrik dashboard now has a `host` template variable at the top:

- **Query:** `label_values(up, host)`
- **Regex:** `/^vps/` (filters out residual non-vps values like the loki push-address)
- **Multi-select + Include All:** enabled
- **Refresh:** on time range change

Use it to filter dashboards by host:

- Select **All** → fleet-wide view (default)
- Select **vps1** → only the LA hub
- Select **vps2** → only the Coventry UK spoke
- Select **vps2, vps3** → both spokes side by side

For the variable to work, panels must include `{host=~"$host"}` in their PromQL. The variable is in place on all 5 Fabrik dashboards; panel-level filtering is added incrementally as panels are touched. Until then, panels show fleet-wide data regardless of variable selection — flat-out OK behavior, just less filterable than possible.

The `host` label is added at Prometheus scrape time via per-target labels in `/opt/monitoring/configs/prometheus/prometheus.yml`. vps1-local jobs use `host: vps1`. The `aro-wake` job (live, 3 targets) carries `host=vps1|vps2|vps3`. **Note (verified 2026-06-07T20:20Z):** the previously documented `node-spokes` / `cadvisor-spokes` / `promtail-spokes` scrape jobs are **NOT in current prometheus.yml** — so node/container metrics filtered by `host=vps2` or `host=vps3` return empty in Grafana right now (the host-variable dropdown still shows the values because they exist in the `aro-wake` job's series, but spoke node/container panels will show no data). Loki side is unaffected: Promtail on each spoke pushes to `loki:3100` with `host: vpsN` labels and ALL three values (vps1, vps2, vps3) are present in live Loki (verified 2026-06-07T20:20Z) — `{host="vps2"}` filters work in Loki-backed dashboards.

---

## How It Works

### Architecture constraint

Grafana's API sits behind Authelia's forward-auth middleware on `monitor.vps1.ocoron.com`. External API calls with a service-account token are intercepted by Authelia (302 → login). Therefore **Grafana HTTP API must be called from inside the VPS**, over the `fabrik` Docker network, on the internal hostname `http://grafana:3000`.

### The provisioning script

`scripts/provision_grafana.sh` runs **on the VPS** and:

1. Reaches `grafana` directly on Docker DNS (stable container name; no UUID-suffix lookup needed any more).
2. For HTTP calls from outside containers, spawns a throwaway `curlimages/curl` container attached to the `fabrik` network.
3. Creates datasources if not present (checked via `GET /api/datasources/name/{name}`).
4. Imports community dashboards tagged `gcom-<id>`; skips if a dashboard with that tag already exists.
5. Prints final state.

The service-account token is stored in `/opt/fabrik/.env` as `GRAFANA_SERVICE_ACCOUNT_TOKEN` and passed via environment variable — **never hardcoded**.

### Run the script

```bash
# From WSL, push + execute on VPS:
TOKEN=$(grep '^GRAFANA_SERVICE_ACCOUNT_TOKEN=' /opt/fabrik/.env | cut -d= -f2-)
scp /opt/fabrik/scripts/provision_grafana.sh vps:/tmp/
ssh vps "GRAFANA_SERVICE_ACCOUNT_TOKEN='$TOKEN' bash /tmp/provision_grafana.sh"
```

Re-run at any time — idempotent. Use after any Grafana redeploy that wipes the SQLite (rare; the bind-mounted file provisioner restores datasources + custom dashboards automatically anyway).

---

## Adding New Dashboards

### Community (gcom)

Edit `scripts/provision_grafana.sh` — add one line per dashboard:

```bash
import_dashboard <gcom-id> "prometheus" "Prometheus"
```

Or for Loki-based dashboards:

```bash
import_dashboard <gcom-id> "loki" "Loki"
```

Popular additions to consider:

| ID | Title | Datasource |
| :--- | :--- | :--- |
| 13639 | Logs / App | Loki |
| 14282 | Traefik 2 | Prometheus |
| 9614 | Nginx | Prometheus |
| 13946 | cAdvisor exporter | Prometheus |

### Custom Fabrik dashboard

Drop a `.json` file into `/opt/monitoring/configs/grafana/provisioning/json-dashboards/` on the VPS (or the WSL equivalent if you have a mirror) and Grafana picks it up within ~30s. Use the existing 5 as reference. Two conventions:

1. **Add a `host` template variable** matching the existing pattern so the dashboard fits the fleet model. Lifting one from `00-infrastructure-overview.json` is the easiest way.
2. **Include `{host=~"$host"}` selectors in PromQL** for any panel that should respect the variable.

---

## Multi-host considerations

### Logs (Loki)

Promtail on each host sets a `host: vpsN` label. Queries:

```logql
{host="vps2"}                    # all logs from vps2
{host="vps2", container_name="n8n"}  # n8n container logs from vps2
{host=~"vps[23]"}                # both spokes
```

### Metrics (Prometheus)

Every scrape target carries `host` label:

```promql
node_load5{host="vps2"}                      # load on vps2 only
container_memory_usage_bytes{host=~"vps[23]"} # all containers across both spokes
```

### Cross-host comparison panels

Single panel showing CPU per host:

```promql
sum(rate(node_cpu_seconds_total{mode!="idle"}[5m])) by (host)
```

Grafana legends like `{{host}}` make this useful immediately.

---

## Verify

```bash
# From WSL (needs token)
TOKEN=$(grep '^GRAFANA_SERVICE_ACCOUNT_TOKEN=' /opt/fabrik/.env | cut -d= -f2-)

# List via VPS (bypasses Authelia)
ssh vps "sudo docker run --rm --network fabrik curlimages/curl:latest \
  -sf -H 'Authorization: Bearer $TOKEN' \
  http://grafana:3000/api/search?type=dash-db"
```

Or open <https://monitor.vps1.ocoron.com> in a browser, complete Authelia 2FA, and browse **Dashboards → Browse**.

---

## Data Freshness

- **Prometheus scrape interval:** 15 s globally (`global.scrape_interval` in `prometheus.yml`); overridden per-job where needed — the `fabrik-services` job uses 30 s
- **Node Exporter Full:** data appears within ~30 s of dashboard open
- **Docker monitoring (cAdvisor):** data appears within ~30 s
- **Prometheus Stats:** data appears immediately

---

## Troubleshooting

### Dashboard shows "No data"

1. Check the Prometheus target is UP:

   ```bash
   ssh vps 'sudo docker exec prometheus wget -qO- http://localhost:9090/api/v1/targets?state=active' \
     | python3 -c "import json,sys; [print(t['labels']['job'], t['health']) for t in json.load(sys.stdin)['data']['activeTargets']]"
   ```

2. Check the dashboard's `host` variable selection — if it's set to a specific host that has no data, the panels will be empty. Try **All**.
3. Check the panel's PromQL — if it includes `{host=~"$host"}` and the target's series don't have a `host` label, the query returns nothing. Verify with `up{host=~"vps.*"}` in the Explore tab.
4. Confirm the datasource name matches what the dashboard expects (usually `Prometheus`).

### Script fails: "Permission denied"

Re-run with `bash`, not `sh`. The script uses bash-only features (`local`, `<<'PY'`, etc.).

### Need to re-import a dashboard (force)

1. Delete the existing dashboard in Grafana UI (or via API `DELETE /api/dashboards/uid/{uid}`).
2. Re-run the script.

### `host` label missing on some series

Some legacy series (especially the `loki` self-scrape) still have residual `host` values that aren't `vpsN`. The Grafana variable regex `/^vps/` filters these out. If a NEW scrape target appears without a `host` label, edit its `static_configs` block in `/opt/monitoring/configs/prometheus/prometheus.yml` to add one, then SIGHUP Prometheus.

---

## Notes

- **Dashboards as code:** The 5 custom Fabrik dashboards are version-controlled in `configs/grafana/dashboards/*.json` and file-provisioned via bind mount (see `grafana-provisioning-setup.md`). The 3 community dashboards (gcom-1860, 193, 2) are still API-imported from grafana.com by the provisioner script — they could be exported to local JSON if full offline reproducibility is needed.
- **Authelia bypass for Grafana API:** Currently we do NOT bypass Authelia for `/api/` paths from outside. Internal-network access is the canonical path.
- **Service account:** `GRAFANA_SERVICE_ACCOUNT_TOKEN` is an Admin-role token in the Main Org. Rotate via Grafana UI → Administration → Service accounts if compromised; update `.env`.
- **Network rename:** The shared Docker network was renamed from `coolify` to `fabrik` on 2026-05-31 (commit `89879e4`). Any script or doc that still references `--network coolify` is stale and must be updated to `--network fabrik`.
