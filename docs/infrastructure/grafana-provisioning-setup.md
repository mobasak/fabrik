# Grafana Datasource Provisioning — Setup

> **⚠️ Container name is pre-migration.** The container name shown below
> (`grafana-loc484owg8gsw04owo0go8kc`) was Coolify's UUID-suffix naming.
> Post-migration the container is named `grafana` (set via `container_name:`
> in the compose stack). All paths and provisioning file behavior are
> unchanged — Grafana still reads `/etc/grafana/provisioning/` from a host
> bind mount at `/opt/monitoring/configs/grafana/provisioning/`.

**Status:** ✅ Live on VPS (2026-05-08)
**Container:** `grafana` (post-migration; was `grafana-loc484owg8gsw04owo0go8kc` under Coolify)
**Provisioning files:** `/opt/monitoring/configs/grafana/provisioning/` (host bind mount)

---

## Goal

Make Grafana datasources persist as code. Without provisioning, datasources are stored only in Grafana's SQLite (`/var/lib/grafana/grafana.db`) and are lost when the data volume is wiped or Grafana is freshly redeployed. Provisioning files are read by Grafana at every startup and create datasources idempotently.

This sets up `Prometheus` and `Loki` as provisioned, read-only datasources.

## Critical Detail

**Grafana reads provisioning from `/etc/grafana/provisioning`, NOT from the data volume `/var/lib/grafana`.**

Writing provisioning files into `/var/lib/docker/volumes/<grafana-volume>/_data/provisioning/` has zero effect — Grafana never looks there. The bind mount must target `/etc/grafana/provisioning` inside the container.

## Prerequisites

- Grafana running as a Coolify service (already deployed)
- Coolify service compose file editable: `/data/coolify/services/loc484owg8gsw04owo0go8kc/docker-compose.yml`
- Prometheus reachable at `http://prometheus:9090` from `coolify` network
- Loki reachable at `http://loki:3100` from `coolify` network

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
# Survives Grafana redeployments via host bind mount in Coolify service compose.

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

### 3. Add bind mount to Coolify service compose

Coolify regenerates this compose file on certain operations, but adding a volume to the existing list survives normal redeploys. Use Python+yaml for safe editing:

```bash
ssh vps "sudo python3 -c \"
import yaml
path = '/data/coolify/services/loc484owg8gsw04owo0go8kc/docker-compose.yml'
cfg = yaml.safe_load(open(path).read())
svc = cfg['services']['grafana']
mount = '/opt/monitoring/configs/grafana/provisioning:/etc/grafana/provisioning:ro'
volumes = svc.get('volumes', [])
if mount not in volumes:
    volumes.append(mount)
    svc['volumes'] = volumes
    open(path, 'w').write(yaml.dump(cfg, default_flow_style=False))
    print('mount added')
else:
    print('already present')
\""
```

### 4. Recreate Grafana with the new mount

`docker compose up -d` recreates only what changed (compose file diff):

```bash
ssh vps "cd /data/coolify/services/loc484owg8gsw04owo0go8kc && sudo docker compose up -d"
```

Brief restart (~10 seconds). Grafana logs in `/var/lib/grafana/grafana.db` are preserved (the data volume is unchanged).

### 5. Verify provisioning loaded

```bash
ssh vps "sudo docker logs grafana-loc484owg8gsw04owo0go8kc 2>&1 | grep -iE 'provisioning.*datasource|datasource.*provisioning' | tail -5"
```

Expected: log lines like `provisioning.datasources ... msg="inserting datasource from configuration" name=Prometheus` and same for Loki.

Verify via Grafana API (internal):

```bash
ssh vps "sudo docker exec grafana-loc484owg8gsw04owo0go8kc \
  wget -qO- http://admin:\$GF_PASS@localhost:3000/api/datasources" | \
  python3 -c "import json,sys; [print(d['name'],'|',d['type'],'|',d['url']) for d in json.load(sys.stdin)]"
```

Expected output:

```
Loki | loki | http://loki:3100
Prometheus | prometheus | http://prometheus:9090
```

Verify via UI: open `https://monitor.vps1.ocoron.com/datasources` — Prometheus and Loki should be listed and marked as "Read-only" (the gray lock icon).

## How to Add Another Datasource

Append to `/opt/monitoring/configs/grafana/provisioning/datasources/fabrik.yaml` under `datasources:`. Then restart Grafana so it re-reads provisioning:

```bash
ssh vps "sudo docker restart grafana-loc484owg8gsw04owo0go8kc"
```

To remove a datasource, set `deleteDatasources` block in the same file (see [Grafana provisioning docs](https://grafana.com/docs/grafana/latest/administration/provisioning/#example-data-source-config-file)) — simply removing it from `datasources:` does not delete it from SQLite.

## Why `editable: false`

Provisioned datasources should be read-only in the UI. If a user edits a provisioned datasource in the UI:
- Their changes are saved to SQLite (`grafana.db`)
- On next Grafana restart, provisioning re-applies the file values, overwriting UI edits
- This causes confusion ("I changed the URL but it reset?")

`editable: false` makes the UI lock the fields, signaling that the datasource is config-managed.

## Relationship to Existing API-Based Provisioning

`scripts/provision_grafana.sh` (documented in `grafana-dashboards-setup.md`) creates datasources via the Grafana HTTP API. With file-based provisioning live, **datasources are now provisioned twice** — once from YAML at startup, then API calls in the script become idempotent no-ops (Grafana rejects duplicate UIDs).

The script remains useful for **dashboard provisioning** (dashboards still go via API in that script).

Dashboard file-based provisioning is already live. The provider config at `/opt/monitoring/configs/grafana/provisioning/dashboards/fabrik.yaml` reads JSON dashboards from the sibling `json-dashboards/` directory (5 custom Fabrik dashboards). To add a new dashboard:

1. Export or create the JSON dashboard file
2. Place it in `/opt/monitoring/configs/grafana/provisioning/json-dashboards/` on the VPS (and mirror in `configs/grafana/dashboards/` in the repo)
3. Grafana auto-reads within 30s (configured `updateIntervalSeconds` in the provider), or restart: `ssh vps "sudo docker restart grafana-loc484owg8gsw04owo0go8kc"`

The 3 community dashboards (grafana.com IDs 1860, 193, 2) are still API-imported via `provision_grafana.sh` — they could be exported to JSON and moved here for full offline reproducibility.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Datasource doesn't appear in UI after restart | Bind mount not effective | `docker inspect <grafana> --format '{{range .Mounts}}{{.Source}} {{.Destination}}{{println}}{{end}}'` — must show the provisioning path |
| Grafana logs `error="open /etc/grafana/provisioning/datasources: permission denied"` | File not readable by Grafana (uid 472) | Ensure files are world-readable: `sudo chmod -R a+r /opt/monitoring/configs/grafana/provisioning`. If that fails, set ownership: `sudo chown -R 472:472 /opt/monitoring/configs/grafana/provisioning` |
| Datasource appears but URL is wrong | Network DNS not resolving | Both Grafana and target service must be on `coolify` network. Verify: `docker inspect <grafana> --format '{{json .NetworkSettings.Networks}}'` |
| Coolify redeployed Grafana and the bind mount disappeared | Coolify regenerated the compose | Re-run step 3 (`yaml`-edit script) and step 4 (`docker compose up -d`) |
| Provisioning file ignored entirely | Wrong filename or extension | Must end in `.yaml` or `.yml` and be under `/etc/grafana/provisioning/datasources/` |

## File Manifest

| Path | Purpose |
|---|---|
| `/opt/monitoring/configs/grafana/provisioning/datasources/fabrik.yaml` | Datasource definitions (Prometheus, Loki) |
| `/opt/monitoring/configs/grafana/provisioning/dashboards/fabrik.yaml` | Dashboard provider config — reads JSON from `json-dashboards/`, auto-refreshes every 30s |
| `/opt/monitoring/configs/grafana/provisioning/json-dashboards/*.json` | 5 custom Fabrik dashboards (infra overview, databases, containers, authelia, meilisearch) |
| `/data/coolify/services/loc484owg8gsw04owo0go8kc/docker-compose.yml` | VPS-managed Grafana service compose; contains the bind mount |
| `/var/lib/docker/volumes/loc484owg8gsw04owo0go8kc_grafana-data/_data/grafana.db` | SQLite — dashboards, users, API keys (NOT datasources anymore) |

## References

- Grafana provisioning: https://grafana.com/docs/grafana/latest/administration/provisioning/
- Datasource YAML schema: https://grafana.com/docs/grafana/latest/administration/provisioning/#datasources
