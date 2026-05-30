# Grafana Provisioning & Dashboards

> **Note:** "Coolify network" / "Coolify redeploys" references below
> describe the pre-migration era. The shared Docker network is still
> named `coolify` (kept for compatibility) but Coolify itself no longer
> runs. Container is now `grafana` (stable via `container_name:`), so the
> `docker inspect` IP-lookup pattern still works and is more reliable than
> ever.

**Status:** ✅ Complete (2026-04-18)
**Grafana URL:** `https://monitor.vps1.ocoron.com` (Authelia 2FA required for UI)
**Automation:** `scripts/provision_grafana.sh` — idempotent, re-runnable

---

## What's Provisioned

> **Note (2026-05-08):** Datasources are now ALSO file-provisioned via bind mount — see [`grafana-provisioning-setup.md`](grafana-provisioning-setup.md). The API-based datasource creation in `provision_grafana.sh` is now redundant for datasources (idempotent no-op on re-run) but the script remains the canonical mechanism for **dashboard** imports.



### Datasources (2)

| Name | Type | Internal URL |
|------|------|--------------|
| Prometheus | `prometheus` | `http://prometheus:9090` |
| Loki | `loki` | `http://loki:3100` |

Both are created with `access: proxy`. Prometheus is the default datasource.

### Dashboards (8 total)

**3 community dashboards** (imported from grafana.com via `provision_grafana.sh`, tagged `gcom-<id>` for idempotent re-import):

| grafana.com ID | Title | Purpose |
|---|---|---|
| [1860](https://grafana.com/grafana/dashboards/1860) | **Node Exporter Full** | Host metrics (CPU, RAM, disk, network) from `node-exporter` |
| [193](https://grafana.com/grafana/dashboards/193) | **Docker monitoring** | Per-container CPU/RAM/net from `cAdvisor` |
| [2](https://grafana.com/grafana/dashboards/2) | **Prometheus Stats** | Prometheus self-monitoring |

**5 custom Fabrik dashboards** (file-provisioned from `configs/grafana/dashboards/`, tagged `fabrik` — see [`grafana-provisioning-setup.md`](grafana-provisioning-setup.md)):

| File | Title | Purpose |
|---|---|---|
| `00-infrastructure-overview.json` | **Fabrik Infrastructure Overview** | VPS-wide CPU, memory, disk, network, container count |
| `10-databases.json` | **Fabrik Databases** | Postgres + Redis health, connections, query rates |
| `20-containers.json` | **Fabrik Container View** | Per-container CPU/RAM/net with name filter |
| `30-authelia.json` | **Fabrik Authelia** | Auth requests, session counts, failed logins |
| `40-meilisearch.json` | **Fabrik Meilisearch** | Index sizes, search latency, document counts |

---

## How It Works

### Architecture constraint

Grafana's API sits behind Authelia's forward-auth middleware on `monitor.vps1.ocoron.com`. External API calls with a service-account token are intercepted by Authelia (302 → login). Therefore **Grafana HTTP API must be called from inside the VPS**, over the `coolify` Docker network, on the internal hostname `http://grafana:3000`.

### The provisioning script

`scripts/provision_grafana.sh` runs **on the VPS** and:

1. Resolves the `grafana` container's IP on the `coolify` network via `docker inspect` (survives Coolify redeploys that change container UUIDs).
2. Spawns a throwaway `curlimages/curl` container attached to the `coolify` network for each HTTP call — a pattern chosen because the `coolify` Docker DNS often does not serve IPv4 records to just-restarted containers (see `LESSONS_LEARNT.md` → Lesson 25 §5 for the root cause of this Docker DNS quirk).
3. Creates datasources if not present (checked via `GET /api/datasources/name/{name}`).
4. Imports dashboards tagged `gcom-<id>`; skips if a dashboard with that tag already exists.
5. Prints final state.

The service-account token is stored in `/opt/fabrik/.env` as `GRAFANA_SERVICE_ACCOUNT_TOKEN` and passed via environment variable — **never hardcoded**.

### Run the script

```bash
# From WSL, push + execute on VPS:
TOKEN=$(grep '^GRAFANA_SERVICE_ACCOUNT_TOKEN=' /opt/fabrik/.env | cut -d= -f2-)
scp /opt/fabrik/scripts/provision_grafana.sh vps:/tmp/
ssh vps "GRAFANA_SERVICE_ACCOUNT_TOKEN='$TOKEN' bash /tmp/provision_grafana.sh"
```

Re-run at any time — idempotent. Use after any Grafana redeploy that wipes the SQLite.

---

## Adding New Dashboards

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
|---|---|---|
| 13639 | Logs / App | Loki |
| 14282 | Traefik 2 | Prometheus |
| 9614 | Nginx | Prometheus |
| 13946 | cAdvisor exporter | Prometheus |

---

## Verify

```bash
# From WSL (needs token)
TOKEN=$(grep '^GRAFANA_SERVICE_ACCOUNT_TOKEN=' /opt/fabrik/.env | cut -d= -f2-)

# list via VPS (bypasses Authelia)
ssh vps "sudo docker run --rm --network coolify curlimages/curl:latest \
  -sf -H 'Authorization: Bearer $TOKEN' \
  http://grafana:3000/api/search?type=dash-db"
```

Or open `https://monitor.vps1.ocoron.com` in a browser, complete Authelia 2FA, and browse **Dashboards → Browse**.

---

## Data Freshness

- **Prometheus scrape interval:** 15s (see `configs/prometheus/prometheus.yml`)
- **Node Exporter Full:** data appears within ~30s of dashboard open
- **Docker monitoring (cAdvisor):** data appears within ~30s
- **Prometheus Stats:** data appears immediately

---

## Troubleshooting

### Dashboard shows "No data"

1. Check the Prometheus target is UP:
   ```bash
   ssh vps "sudo docker exec \$(sudo docker ps --format '{{.Names}}' | grep '^prometheus') \
     wget -qO- http://localhost:9090/api/v1/targets?state=active" \
     | python3 -c "import json,sys; [print(t['labels']['job'], t['health']) for t in json.load(sys.stdin)['data']['activeTargets']]"
   ```
2. Check the dashboard's variable selectors (some variables default to `None`).
3. Confirm the datasource name matches what the dashboard expects (usually `Prometheus`).

### Script fails: "Permission denied"

Re-run with `bash`, not `sh`. The script uses bash-only features (`local`, `<<'PY'`, etc.).

### Need to re-import a dashboard (force)

1. Delete the existing dashboard in Grafana UI (or via API `DELETE /api/dashboards/uid/{uid}`).
2. Re-run the script.

---

## Notes

- **Dashboards as code:** The 5 custom Fabrik dashboards are already version-controlled in `configs/grafana/dashboards/*.json` and file-provisioned via bind mount (see `grafana-provisioning-setup.md`). The 3 community dashboards (gcom-1860, 193, 2) are still API-imported from grafana.com by the provisioner script — these could be exported to local JSON if full offline reproducibility is needed.
- **Authelia bypass for Grafana API:** Currently we do NOT bypass Authelia for `/api/` paths from outside. Internal-network access is the canonical path.
- **Service account:** `GRAFANA_SERVICE_ACCOUNT_TOKEN` is an Admin-role token in the Main Org. Rotate via Grafana UI → Administration → Service accounts if compromised; update `.env`.
