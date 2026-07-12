# VPS Residue Policy — Lean Hygiene

**Last Updated:** 2026-07-12 (`/fabrik-docs-review` reconciliation vs live fleet: Alertmanager sends to Telegram **natively** — it does NOT route via Apprise; Prometheus is **15 active jobs / 20 targets / 20 up** with spoke federation LIVE; Backrest hook + Apprise `alerts` config **fixed** (Apprise was 204-ing every alert); `fabrik-compose-boot.service` reboot-race unit added fleet-wide; spoke `DOCKER-USER` drift recorded.) **Prior:** 2026-06-16 (added "Known outstanding residue" note — two items the policy is designed to catch that currently exist live, flagged pending cleanup. Prior 2026-06-15: added Vultr disposable-drill residue + `fabrik vultr reconcile`/`cleanup` auto-destroy hygiene; corrected the destroy chain to 8 teardown steps + state archive per `destroyer.py`; `fabrik destroy --target-vps` is now shipped, not pending. Prior 2026-06-07 post-aro-wake fleet rollout context follows — policy unchanged; today's new residue surfaces to watch: `/etc/systemd/system/aro-wake.service.d/*.conf` drop-in units created for `ARO_WAKE_STORM_THRESHOLD=0` test runs must be removed after the test (see `vps-status.md` 2026-06-06 entry for the cleanup pattern); `/var/lib/aro-wake/pending.jsonl` may accumulate suppressed-but-not-dropped entries if a real loop is suppressed for >24h — TTL handles the bulk but `sudo truncate -s 0 /var/lib/aro-wake/pending.jsonl` is the manual clean if needed. **New residue surface to watch 2026-06-07**: stale Prometheus scrape jobs in `prometheus.yml` for retired containers will trigger the Phase 4 Alertmanager→aro-wake wire's `repeat_interval: 30m` and flood Telegram. Caught live this round — the `netdata` job had been orphaned since 2026-05-30 retirement and ran the 24× flood overnight. Whenever a container is retired, the corresponding scrape job MUST be removed from `prometheus.yml` AND `alerts.yml` in the same edit.)
**Last probe report:** [`probe-reports/infra-probe-2026-06-07T20-20Z.yaml`](probe-reports/infra-probe-2026-06-07T20-20Z.yaml)
**Mandate (2026-05-06):** never leave residue on the VPS from Fabrik test, throwaway, or deprecated work. Keep it lean.

## Known outstanding residue (2026-06-16)

Two residue items that this policy is designed to catch currently exist live — **flagged, pending cleanup** (not yet fixed):

1. **Stale Gatus endpoints `coolify` + `coolify-public`** — defined in `core/infra.yaml` + `external/public.yaml`, still pointing at the decommissioned Coolify. These are exactly the "endpoints pointing at deleted services" the Gatus scanner (#3) flags; remove the two endpoint blocks from those config files (Gatus auto-reloads within 30 s).
2. ~~**Orphan DNS `*.vps4.ocoron.com` + `vps4.ocoron.com`**~~ — **RESOLVED 2026-06-17** (re-verified live 2026-07-12: both resolve NXDOMAIN). The two A records → `45.77.68.63` (DR-drill residue, no live vps4 droplet) were deleted via the Cloudflare API; CF zone `ocoron.com` is back to 18 A records.

## TL;DR

```bash
# Before declaring any VPS task complete:
fabrik vps-sync --verify
# Exit 0 = clean. Exit 1 = drift found. Exit 2 = scan failed.
```

Implementation: `scripts/vps_sync.py::verify_residue()` (multi-point audit) + `verify_limits()` (memory-limit drift after reboot). Gatus alias drift is no longer a separate concern — stable `container_name:` in compose files guarantees Docker DNS stability.

## Pre-action discipline

1. **Always use `fabrik destroy --drop-data -y`** for throwaway test specs. Reverses the provision chain in strict inverse order — 8 teardown steps then state archive (per `src/fabrik/orchestrator/destroyer.py`: meilisearch → authelia → glitchtip → backrest → gatus → postgres → app/compose stack → DNS record → local project files, then state-file archive). Shape-gated steps (prometheus, redis) and informational ones (grafana) run only when applicable.
2. **Never use long-lived test names** like `fabrik-test`, `proxy-test`. Use timestamped throwaways (e.g. `fabrik-e2e-2026-05-17`).
3. **After ANY `fabrik destroy`, run `fabrik vps-sync --verify`** to confirm orphans are zero across all registrars.

## What the verifier checks

`fabrik vps-sync --verify` calls the residue scanners. Combined coverage on **vps1**:

| # | Surface | What it flags |
| :--- | :--- | :--- |
| 1 | Compose stacks | `/opt/fabrik-*-test*/`, `/opt/*-e2e-*/`, `/opt/integration-test*/`, any `_is_test_name` match — orphan compose directories left behind by partial destroys |
| 2 | GlitchTip projects | `GET /api/0/organizations/ocoron/projects/` returning test/e2e slugs |
| 3 | Gatus configs | `*.bak.*` files in `/opt/monitoring/configs/gatus/apps/`; duplicate endpoints; endpoints pointing at deleted services |
| 4 | Authelia rules | Orphan `access_control` entries for domains with no live service |
| 5 | Postgres DBs | `fabrik_*_test*` or `*_e2e_*` databases on `postgres-main` |
| 6 | Meilisearch indexes | Test indexes |
| 7 | DNS A records | Records pointing to destroyed services |
| 8 | Docker volumes | `docker volume ls -f dangling=true`; especially `<svc>_postgres_data` left behind after moving to shared `postgres-main`; pre-migration legacy (`coolify-db`, `coolify-redis`, etc.) |
| 9 | Dangling images | `docker images -f dangling=true` non-empty |
| 10 | `/tmp` locks | Stale `/tmp/fabrik-*-test-*.lock` files (`run_locked` should clean; verify) |
| 11 | `/opt/` | `test-*`, `*-test`, `wp-test` ad-hoc files / orphan project trees |
| 12 | Backrest | 4 live plans on hub + 2 per spoke (W2/W11). Watch for stray test-named plans (`test-*`, `*-tmp`) and abandoned repos under `/srv/backrest/repos/<test-name>/` left over from one-off experiments. |
| 13 | Memory limits | Containers with `HostConfig.Memory=0` (limits reset on reboot; rerun `vps_apply_limits.sh`) |

## Multi-host residue (vps2 / vps3, added 2026-05-31)

The mandate now extends to spokes. Same rules apply: never leave residue from test workloads. Per-spoke residue check:

```bash
for spoke in vps2 vps3; do
  echo "=== $spoke ==="
  ssh $spoke 'sudo ls /opt/ | grep -E "test|e2e|integration" || true'
  ssh $spoke 'sudo docker ps -a --filter status=exited --format "{{.Names}}" || true'
  ssh $spoke 'sudo docker volume ls -f dangling=true --format "{{.Name}}"'
done
```

Spokes currently host only `/opt/monitoring-agent/` + `/opt/traefik/` (no tenants yet). Any other `/opt/*` directory on a spoke is by definition residue from a test or partial deploy.

`fabrik destroy --target-vps <spokeN> specs/services/<id>.yaml` is implemented (`src/fabrik/cli.py` resolves the target host: CLI flag > state-file `target_vps` > spec `target_vps` > vps1, then env-swaps `FABRIK_VPS_SSH_HOST`). Use it to tear a spec down on a spoke and leave no compose dir behind. Manual fallback only when no spec exists:

```bash
ssh vpsN 'cd /opt/<svc> && sudo docker compose down -v && sudo rm -rf /opt/<svc>'
```

## Vultr disposable-drill residue (added 2026-06-15)

DR drills and ad-hoc capacity tests provision real Vultr droplets. Residue here is a **billed instance left running**, not just disk clutter — the hygiene is in `src/fabrik/orchestrator/vultr_state.py` + `vultr_drill.py` + the `fabrik vultr` CLI:

- **Auto-destroy is the default.** `fabrik vultr drill <bare|spoke|hub|spoke-restore>` always destroys the droplet on exit, even on failure (`--keep-on-failure` opts out for debugging). On destroy it calls `vultr_state.mark_destroyed(name)` so local state matches the live account.
- **`fabrik vultr reconcile`** — compares local state to the live Vultr account and prints the drift report (`matched` / `in_state_not_live` / `in_live_not_state` / live vs tracked-active counts). Run this if a drill was killed mid-run or you suspect an orphaned droplet.
- **`fabrik vultr cleanup [--yes]`** — destroys any **disposable** instance past its `destroy_after` deadline (orphan recovery; dry-run by default). After destroying overdue instances it runs `vultr_state.gc_old_disposables()` to drop disposable records destroyed longer than the retention window ago, keeping `vultr_state` lean.
- Drill reports append to `logs/dr-drill-history.jsonl` (gitignored, local-only).

Permanent spokes (`fabrik vultr provision`) are `mode=permanent` and are NOT touched by `cleanup` — only `mode=disposable` records are eligible for auto-GC.

## Manual recovery if `--verify` exits 1

The script prints exact remediation commands per finding. Common patterns:

| Finding | Fix |
| :--- | :--- |
| Orphan compose stack at `/opt/<svc>` | `fabrik destroy specs/services/<id>.yaml --drop-data -y` if spec exists; else manual: `cd /opt/<svc> && sudo docker compose down -v && sudo rm -rf /opt/<svc>` |
| Orphan Postgres DB | `ssh vps "sudo docker exec postgres-main psql -U postgres -c 'DROP DATABASE <name>;'"` |
| Orphan Authelia rule | edit `/opt/authelia/config/configuration.yml` (working copy); `authelia-config-sync.service` propagates to volume + restarts container |
| Orphan Gatus endpoint | delete the file under `/opt/monitoring/configs/gatus/apps/<svc>.yaml`; Gatus auto-reloads within 30 s |
| Dangling Docker volume | `ssh vps 'sudo docker volume rm <name>'` after confirming no live container references it |
| Memory limit reset (post-reboot) | `ssh vps 'bash /opt/fabrik/scripts/vps_apply_limits.sh'` |
| `/tmp` lock | `ssh vps 'rm /tmp/fabrik-*-test-*.lock'` after confirming no live process holds it |

## Pre-migration residue still on disk (vps1)

Items intentionally retained for historical reference, not residue per the policy:

- `/opt/.archive/` — archived configs from W1 cleanup (apprise plugin volumes, prometheus.yml backups, etc.)
- `/opt/backups/` — postgres dumps + Coolify env backups in `/opt/.archive/coolify-env-backups/` (preserved)
- ~~`/opt/prometheus/`~~ — stale standalone Prometheus compose from pre-rename era. **Deleted 2026-05-31 evening** during the residue sweep; real Prometheus runs from `/opt/monitoring/compose.yaml`.
- `coolify-db` / `coolify-redis` Docker volumes — pre-migration legacy. Deleted on 2026-05-30 cleanup; verify with `ssh vps 'sudo docker volume ls'` (should not appear).

### Other residue items cleared 2026-05-31 evening (one-pass sweep)

- 6 stale CF DNS A records (`coolify`, `control`, `dns`, `fabrik-e2e-timing`, `images`, `netdata`.vps1.ocoron.com) — deleted
- Authelia rule #6 trimmed from 10 hosts (5 were dead microservices + 1 stale alias) to 4 alive
- Authelia rule #7 dropped `coolify.vps1.ocoron.com`
- Orphan Postgres role `proxy_user` — dropped
- UFW rules 6001/tcp + 6002/tcp (Coolify Realtime) — deleted
- `/opt/opt.code-workspace` stray file — deleted
- 6 orphan `.fabrik/state/*.json` files — moved to `.fabrik/state/_destroyed/`
- 2 `.bak` Gatus config files — deleted

Net: post-sweep, the only "residue still on disk" entries are `/opt/.archive/` and `/opt/backups/`, both intentionally preserved.

## Cross-references

- Deploy + destroy mechanics: `docs/operations/deployment.md`
- DR (full restore from B2): `docs/operations/disaster-recovery.md`
- Provisioner / destroyer: `src/fabrik/orchestrator/infrastructure.py` (provision side) + `src/fabrik/orchestrator/destroyer.py::destroy_deployment()` (inverse — 8 teardown steps + state archive, see destroyer module docstring for canonical order)
- Backups status: [`vps-complete-inventory.md § Backups`](vps-complete-inventory.md) — 4 hub plans + 2 plans per spoke shipped 2026-06-01 (W2 + W11)

## Why this matters

Every residue item is silent cost: orphan Postgres DBs eat disk, dangling Docker volumes eat inodes, stale Gatus targets emit false-positive alerts, orphan Authelia rules expand the attack surface, leftover `/opt/<svc>` compose dirs confuse `fabrik audit-registrars`. A 30-second `fabrik vps-sync --verify` after each destroy keeps the VPS fleet in a state that matches `data/projects.yaml`.
