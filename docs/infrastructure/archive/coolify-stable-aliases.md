# Coolify Stable Aliases for Single-Image Applications (historical)

> **📌 ARCHIVED 2026-06-06.** Historical document preserved as-is for context. Frozen at the time of original ship. For current fleet state see [`vps-status.md`](../vps-status.md), [`vps-complete-inventory.md`](../vps-complete-inventory.md), and [`vps-fleet-architecture.md`](../vps-fleet-architecture.md). Do NOT update the content below — that would defeat the archive.

> **⚠️ Historical — no longer needed post-migration.** With Coolify removed
> and `compose.yaml` files now emitting `container_name: <name>` directly
> (enforced by `compose_linter.py`), container names are stable across
> redeploys by construction. The alias-watcher mechanism described below
> ran during the Coolify era to compensate for UUID-suffix container names;
> it is retained here as the historical record of why `container_name:` is
> now a hard requirement.

**Purpose:** Coolify's single-image Applications get container names like
`<app-uuid>-<timestamp>`. The **timestamp** changes on every redeploy, so any
Gatus monitor or inter-service URL keyed on the UUID container name breaks
silently after the next deploy.

The fix is to install a **stable DNS alias** on the container's `coolify`
network attachment. That alias persists through Coolify-managed redeploys
(via compose file) and through VPS reboots (via `vps_apply_limits.sh`).

## When this applies

- **Service stacks** (`/data/coolify/services/<uuid>/`): NOT affected.
  Container name is `<service>-<uuid>` and the UUID is the Coolify service ID
  (stable across redeploys). Use the container name directly.
- **Single-image Applications** (`/data/coolify/applications/<uuid>/`):
  AFFECTED. Container name has a timestamp suffix that changes per redeploy.
  Must install a stable alias.

## Install procedure (one-time per single-image App)

```bash
# 1. Add stable alias to the app's compose (persists through Coolify redeploys)
sudo python3 -c "
import yaml
path = '/data/coolify/applications/<app-uuid>/docker-compose.yaml'
cfg = yaml.safe_load(open(path).read())
svc = cfg['services']['<uuid-name>']
svc['networks']['coolify']['aliases'].append('<stable-name>')
open(path, 'w').write(yaml.dump(cfg, default_flow_style=False))
"

# 2. Apply alias to the live container (zero-downtime)
sudo docker network disconnect coolify <uuid-name>
sudo docker network connect --alias <stable-name> --alias <uuid-name> coolify <uuid-name>

# 3. Persist through VPS reboots — add to scripts/vps_apply_limits.sh
#    Add line: apply_alias <uuid-name> <stable-name>

# 4. Use stable name in Gatus config
#    url: "tcp://<stable-name>:<port>"
```

Replace `<app-uuid>`, `<uuid-name>`, and `<stable-name>` with the actual
values. The `<uuid-name>` is the existing container name (e.g.
`vckgs8c00o40o884k48cgow8-220643454460`); `<stable-name>` is the new
alias you want to use (e.g. `browserless`).

## Currently registered stable aliases

| Stable name | UUID container | Service |
|---|---|---|
| `browserless` | `vckgs8c00o40o884k48cgow8-220643454460` | Chromium headless |
| `gotenberg` | `e04k4sco44ow04ccc0o0k00k-151256201601` | PDF (Gotenberg) |
| `meilisearch` | `bs0wo48k4gwo440gcowscoc8-150802066640` | MeiliSearch |
| `glitchtip-web` | `glitchtip-web-z00kkck8c8cwo800kk440csk` | GlitchTip web |

This table is authoritative — `scripts/vps_apply_limits.sh` re-applies these
on every VPS boot. Keep them in sync.

## Why UUID-only naming breaks

Coolify rewrites the single-image App's `docker-compose.yaml` on every
redeploy with a fresh timestamp in the container name (the `-220643454460`
suffix is the timestamp). Internal DNS resolves that exact name. Anything
querying the old name returns NXDOMAIN until you update every consumer.

The alias workaround pins a name we control on the container side, so
consumer URLs stay stable across redeploys.

## See also

- `.windsurf/rules/core/55-observability.md` § "Gatus — Stable DNS Names" — the
  "never UUID names" rule that points here
- `scripts/vps_apply_limits.sh` — the boot-time reapply script (contains
  the canonical alias pair list)
