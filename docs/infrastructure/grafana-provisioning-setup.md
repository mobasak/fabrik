# Grafana Datasource Provisioning — Setup

**Last Updated:** 2026-06-06 (no change to datasource provisioning — Prometheus + Loki datasources already cover the new `aro-wake` job's metrics; aro-wake series appear under the existing Prometheus datasource without any reconfiguration)
**Status:** ✅ Live
**Container:** `grafana` (stable name; no UUID suffix)
**Compose file:** `/opt/monitoring/compose.yaml` (services block under `grafana:`)
**Provisioning files:** `/opt/monitoring/configs/grafana/provisioning/` (host bind mount)

---

## Goal

Make Grafana datasources persist as code. Without provisioning, datasources are stored only in Grafana's SQLite (`/var/lib/grafana/grafana.db`) and are lost when the data volume is wiped or Grafana is freshly redeployed. Provisioning files are read by Grafana at every startup and create datasources idempotently.

This sets up `Prometheus` and `Loki` as provisioned, read-only datasources.

## Critical Detail

**Grafana reads provisioning from `/etc/grafana/provisioning`, NOT from the data volume `/var/lib/grafana`.**

Writing provisioning files into `/var/lib/docker/volumes/<grafana-volume>/_data/provisioning/` has zero effect — Grafana never looks there. The bind mount must target `/etc/grafana/provisioning` inside the container.

## Prerequisites

- Grafana running in `/opt/monitoring/compose.yaml` as the `grafana` service
- Prometheus reachable at `http://prometheus:9090` from `fabrik` network
- Loki reachable at `http://loki:3100` from `fabrik` network

## Reproducible Setup

### 1. Create host directory structure

```bash
ssh vps "sudo mkdir -p /opt/monitoring/configs/grafana/provisioning/datasources && \
         sudo mkdir -p /opt/monitoring/configs/grafana/provisioning/dashboards"
```

### 2. Write the datasources provisioning file

```bash
ssh vps "sudo tee /opt/monitoring/configs/grafana/provisioning/datasources/fabrik.yaml > /dev/null << 'YAML'
apiVersion: 1
# Provisioned by Fabrik — do not edit manually.
# Source: /opt/monitoring/configs/grafana/provisioning/datasources/fabrik.yaml
# Survives Grafana redeployments via host bind mount in /opt/monitoring/compose.yaml.

datasources:
  - name: Prometheus
    type: prometheus
    uid: prometheus
    url: http://prometheus:9090
    access: proxy
    isDefault: true
    editable: false
    jsonData:
      httpMethod: POST

  - name: Loki
    type: loki
    uid: loki
    url: http://loki:3100
    access: proxy
    isDefault: false
    editable: false
    jsonData:
      maxLines: 1000
YAML"
```

### 3. Add bind mount to `/opt/monitoring/compose.yaml`

If the mount isn't already there, add it via Python + yaml (safer than sed for nested dicts):

```bash
ssh vps "sudo python3 <<'PY'
import yaml
path = '/opt/monitoring/compose.yaml'
cfg = yaml.safe_load(open(path).read())
svc = cfg['services']['grafana']
mount = '/opt/monitoring/configs/grafana/provisioning:/etc/grafana/provisioning:ro'
volumes = svc.get('volumes', [])
if mount not in volumes:
    volumes.append(mount)
    svc['volumes'] = volumes
    open(path, 'w').write(yaml.safe_dump(cfg, sort_keys=False, default_flow_style=False))
    print('mount added')
else:
    print('already present')
PY"
```

### 4. Recreate Grafana with the new mount

```bash
ssh vps "cd /opt/monitoring && sudo docker compose up -d grafana"
```

Brief restart (~10 s). The grafana-data named volume is unchanged, so dashboards, users, and API keys persist.

### 5. Verify provisioning loaded

```bash
ssh vps 'sudo docker logs grafana 2>&1 | grep -iE "provisioning.*datasource|datasource.*provisioning" | tail -5'
```

Expected: log lines like `provisioning.datasources ... msg="inserting datasource from configuration" name=Prometheus` and same for Loki.

Verify via Grafana API (internal):

```bash
ssh vps 'sudo docker exec grafana wget -qO- "http://admin:$GF_PASS@localhost:3000/api/datasources"' \
  | python3 -c "import json,sys; [print(d['name'],'|',d['type'],'|',d['url']) for d in json.load(sys.stdin)]"
```

Expected output:

```text
Loki | loki | http://loki:3100
Prometheus | prometheus | http://prometheus:9090
```

Verify via UI: open <https://monitor.vps1.ocoron.com/datasources> — Prometheus and Loki should be listed and marked "Read-only" (gray lock icon).

## How to Add Another Datasource

Append to `/opt/monitoring/configs/grafana/provisioning/datasources/fabrik.yaml` under `datasources:`. Then restart Grafana so it re-reads provisioning:

```bash
ssh vps "sudo docker restart grafana"
```

To remove a datasource, set a `deleteDatasources` block in the same file (see [Grafana provisioning docs](https://grafana.com/docs/grafana/latest/administration/provisioning/#example-data-source-config-file)) — simply removing it from `datasources:` does not delete it from SQLite.

## Why `editable: false`

Provisioned datasources should be read-only in the UI. If a user edits a provisioned datasource in the UI:

- Their changes are saved to SQLite (`grafana.db`)
- On next Grafana restart, provisioning re-applies the file values, overwriting UI edits
- This causes confusion ("I changed the URL but it reset?")

`editable: false` makes the UI lock the fields, signaling that the datasource is config-managed.

## Relationship to the API-Based Provisioning Script

`scripts/provision_grafana.sh` (documented in `grafana-dashboards-setup.md`) creates datasources via the Grafana HTTP API. With file-based provisioning live, **datasources are now provisioned twice** — once from YAML at startup, then the API calls in the script become idempotent no-ops (Grafana rejects duplicate UIDs).

The script remains useful for **dashboard provisioning** of community gcom dashboards (the script imports them via API).

### File-provisioned dashboards (custom Fabrik)

Dashboard file-based provisioning is already live. The provider config at `/opt/monitoring/configs/grafana/provisioning/dashboards/fabrik.yaml` reads JSON dashboards from the sibling `json-dashboards/` directory (5 custom Fabrik dashboards). To add a new dashboard:

1. Export or create the JSON dashboard file
2. Place it in `/opt/monitoring/configs/grafana/provisioning/json-dashboards/` on the VPS (and mirror in `configs/grafana/dashboards/` in the repo)
3. Grafana auto-reads within 30 s (configured `updateIntervalSeconds` in the provider), or restart: `ssh vps "sudo docker restart grafana"`

The 3 community dashboards (grafana.com IDs 1860, 193, 2) are still API-imported via `provision_grafana.sh` — they could be exported to JSON and moved here for full offline reproducibility.

## Multi-host considerations

Grafana itself runs only on vps1. Spoke metrics + logs flow back to vps1 via the Wireguard mesh:

- Spoke `node-exporter` / `cadvisor` / `promtail` bind to their mesh IPs (`10.99.0.2:9100`, etc.)
- vps1's Prometheus scrapes them via mesh
- Spoke `promtail` pushes logs to vps1's Loki at `10.99.0.1:3100`
- Every series carries a `host: vpsN` label set at scrape time

Provisioned datasources don't need any change for multi-host: they still point at `http://prometheus:9090` and `http://loki:3100` on the local `fabrik` Docker network, which holds all the fleet data anyway.

For per-host dashboard filtering, see `grafana-dashboards-setup.md § host template variable`.

## Troubleshooting

| Symptom | Cause | Fix |
| :--- | :--- | :--- |
| Datasource doesn't appear in UI after restart | Bind mount not effective | `docker inspect grafana --format '{{range .Mounts}}{{.Source}} {{.Destination}}{{println}}{{end}}'` — must show the provisioning path |
| Grafana logs `error="open /etc/grafana/provisioning/datasources: permission denied"` | File not readable by Grafana (uid 472) | `sudo chmod -R a+r /opt/monitoring/configs/grafana/provisioning`. If that fails: `sudo chown -R 472:472 /opt/monitoring/configs/grafana/provisioning` |
| Datasource appears but URL is wrong | Network DNS not resolving | Both Grafana and target service must be on `fabrik` network. Verify: `docker inspect grafana --format '{{json .NetworkSettings.Networks}}'` |
| Bind mount disappeared after a compose edit | Manual yaml munging | Re-apply step 3 (the Python yaml helper) and step 4 (`docker compose up -d grafana`). The mount is intended to be persistent in `/opt/monitoring/compose.yaml` — version-control the file. |
| Provisioning file ignored entirely | Wrong filename or extension | Must end in `.yaml` or `.yml` and be under `/etc/grafana/provisioning/datasources/` |

## File Manifest

| Path | Purpose |
| :--- | :--- |
| `/opt/monitoring/configs/grafana/provisioning/datasources/fabrik.yaml` | Datasource definitions (Prometheus, Loki) |
| `/opt/monitoring/configs/grafana/provisioning/dashboards/fabrik.yaml` | Dashboard provider config — reads JSON from `json-dashboards/`, auto-refreshes every 30 s |
| `/opt/monitoring/configs/grafana/provisioning/json-dashboards/*.json` | 5 custom Fabrik dashboards (infra overview, databases, containers, authelia, meilisearch) |
| `/opt/monitoring/compose.yaml` | Hub-side compose that contains the `grafana:` service with the bind mount |
| `/var/lib/docker/volumes/monitoring_grafana-data/_data/grafana.db` | SQLite — dashboards, users, API keys (NOT datasources anymore) |

## References

- Grafana provisioning: <https://grafana.com/docs/grafana/latest/administration/provisioning/>
- Datasource YAML schema: <https://grafana.com/docs/grafana/latest/administration/provisioning/#datasources>
- Sister doc: [`grafana-dashboards-setup.md`](grafana-dashboards-setup.md) (community dashboard imports + host filter variable)
