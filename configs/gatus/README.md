# Gatus configs (source-controlled)

This tree mirrors `/opt/monitoring/configs/gatus/` on vps1. The Gatus container
(compose at `/opt/gatus/compose.yaml` on vps1) bind-mounts that path as
`/config` read-only, so what's here is the runtime source-of-truth — once
synced. Pulled into source control 2026-06-13 closing the audit asymmetry
flagged in `STRATEGIC_BACKLOG.md` (every other monitoring config — prometheus,
alertmanager, loki, grafana, promtail — was already in `configs/`; gatus was
the outlier).

## Layout

| Path | Purpose |
| :--- | :--- |
| [`_base.yaml`](_base.yaml) | Connectivity checker + storage + UI + the shared Apprise alerting envelope all endpoint files reference |
| [`apps/`](apps/) | Per-service endpoint definitions (13 files at snapshot). Adding a new spec normally drops a file here via `drivers/gatus.py` |
| [`core/infra.yaml`](core/infra.yaml) | Infra-level probes |
| [`data/databases.yaml`](data/databases.yaml) | Database health probes |
| [`external/public.yaml`](external/public.yaml) | Public-internet endpoints |
| [`observability/stack.yaml`](observability/stack.yaml) | Probes for the monitoring stack itself |

## Sync workflow

```bash
# Read-only drift check (exit 1 if git != vps1)
scripts/sync_gatus_to_vps.sh --diff

# Push git → vps1 (idempotent; restarts gatus only if any file changed)
scripts/sync_gatus_to_vps.sh

# Same, but don't actually scp or restart
scripts/sync_gatus_to_vps.sh --dry-run
```

## Known drift sources (NOT fixed by this commit)

The drivers under [`src/fabrik/drivers/gatus.py`](../../src/fabrik/drivers/gatus.py)
write to **vps1 live, not to git**. So a fresh endpoint added via:

- `add_endpoint(project, domain, ...)` — called by `fabrik apply` registrar
- `add_aro_wake_endpoint(spoke, mesh_ip)` — called by `fabrik vultr provision`
  (PR1 c48f3c0)

…lands in `/opt/monitoring/configs/gatus/apps/<name>.yaml` on vps1 but NOT in
this directory. The drift-check (`--diff`) surfaces this on the next sync;
the operator manually `cp`s the new file in + commits.

Two follow-ups, neither in scope here:

1. **Driver-side mirror.** `add_endpoint` could write to both vps1 AND this
   tree (with a `git add` reminder in the log). Same shape as a corresponding
   prometheus fix.
2. **Reverse symmetry for prometheus / alertmanager / loki.** Spot-checked
   2026-06-13: `configs/prometheus/prometheus.yml` md5 ≠ vps1's. Same kind of
   silent drift, larger blast radius (scrape targets), same root cause
   (drivers write live, never git). Not in this commit because the prometheus
   sync needs more thought (scrape jobs are accumulated, not snapshot-replaced
   like gatus endpoint files).

## Restore path

If vps1's `/opt/monitoring/configs/gatus/` is lost (disk failure pre-Backrest
restore, accidental `rm -rf`, etc.):

```bash
scripts/sync_gatus_to_vps.sh             # push the whole tree from git
```

That's it. Gatus restarts and picks up every endpoint. The runtime container's
mount target (`/opt/gatus/compose.yaml`'s `volumes:`) is unchanged.
