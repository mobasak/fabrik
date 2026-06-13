# Prometheus configs (source-controlled)

This tree mirrors `/opt/monitoring/configs/prometheus/` on vps1. The Prometheus
container bind-mounts `/opt/monitoring/configs/prometheus/` as `/etc/prometheus`
(ro). 2026-06-13: closed a multi-week drift where `prometheus.yml` here didn't
match vps1's live file (the driver wrote live, never git). Companion fix to
the same Gatus asymmetry closed earlier the same day.

## Layout

| Path | Purpose |
| :--- | :--- |
| [`prometheus.yml`](prometheus.yml) | Main config — scrape jobs, rule file refs, global settings |
| [`rules/alerts.yml`](rules/alerts.yml) | Active alert rules (5 groups: `aro_wake`, `container_health`, `host_health`, `service_health` — plus historical groups documented elsewhere) |
| [`rules/fabrik-drift.yml`](rules/fabrik-drift.yml) | The `fabrik-registrar-drift` rule group (separate file because the registrar audit cron writes it) |

## Secrets

`prometheus.yml` declares Bearer tokens via `credentials_file:` paths
(NOT inline `credentials:` values). Secret values live ONLY on vps1 under
`/opt/monitoring/configs/prometheus/secrets/`, mode `0640 root:nogroup` so
the `nobody`-running container can read them. They are **never** snapshotted
to git.

Today's live secrets:

| Path inside container | Used by | Source |
| :--- | :--- | :--- |
| `/etc/prometheus/secrets/meilisearch-key` | `meilisearch` scrape job | Meilisearch master key (same value the meilisearch container itself uses) |

To verify every declared secret file is actually present + readable inside
the container:

```bash
scripts/sync_prometheus_to_vps.sh --verify-secrets
```

## Sync workflow

```bash
# Read-only drift check (exit 1 if git != vps1)
scripts/sync_prometheus_to_vps.sh --diff

# Push git → vps1 (idempotent; reloads prometheus only if any file changed)
scripts/sync_prometheus_to_vps.sh

# Same, dry-run
scripts/sync_prometheus_to_vps.sh --dry-run

# Verify all credentials_file: paths resolve
scripts/sync_prometheus_to_vps.sh --verify-secrets
```

## Driver-driven writes (dual-write)

[`src/fabrik/drivers/prometheus.py`](../../src/fabrik/drivers/prometheus.py)
mutates `prometheus.yml` for every call to:

- `add_scrape_target(name, ...)` — called by `fabrik apply` for any spec with
  `shape.exposes_metrics: true`
- `add_aro_wake_target(spoke, mesh_ip)` — called by `fabrik vultr provision`
  (PR1 c48f3c0)

Since 2026-06-13, `_write_config()` writes to **both** vps1 AND this directory
atomically:

1. Build YAML body once.
2. scp + sudo install into `/opt/monitoring/configs/prometheus/prometheus.yml`
   (the runtime gate — reload failure surfaces here).
3. Mirror the same body to `configs/prometheus/prometheus.yml` (best-effort —
   a read-only FS or missing dir does not fail the runtime write).

After the driver runs, your `git status` will surface the diff; commit it as
part of the same change that added the service. **Drift can no longer
accumulate silently.**

## Restore path

If vps1's `/opt/monitoring/configs/prometheus/` is lost:

```bash
scripts/sync_prometheus_to_vps.sh                 # push tree from git
# Then on vps1, restore the secrets/ directory contents from a separate
# secrets backup (NOT from git) — see configs/prometheus/secrets isn't
# tracked; the operator's DR plan ships secrets via a separate channel.
```

## Backup files

`.bak-*` files exist on vps1 (operator-side snapshots from past edits) but
are intentionally **not** tracked here. The sync script filters them out;
the operator can prune them on vps1 when comfortable.
