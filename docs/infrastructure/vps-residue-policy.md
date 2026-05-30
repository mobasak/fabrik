# VPS Residue Policy — Lean Hygiene

> Mandate (2026-05-06): never leave residue on the VPS from Fabrik test, throwaway, or deprecated work. Keep it lean.
>
> **⚠️ Partially pre-migration vintage.** Rows that describe residue as
> "orphan Coolify app" / "Gatus alias pinned to Coolify UUID hostname" /
> "destroy via Coolify UI" are historical. Post-migration the equivalent
> residue is an orphan `/opt/<app>/` Compose directory; cleanup is
> `cd /opt/<app> && sudo docker compose down -v && sudo rm -rf /opt/<app>`
> (which `fabrik destroy` does via the SSH deployer's `delete()`). Gatus
> alias drift is no longer a concern — `container_name:` in compose files
> guarantees stable Docker DNS. Other policy items (memory limits,
> Authelia rules, DNS records, .env hygiene) are unchanged.

## TL;DR

```bash
# Before declaring any VPS task complete:
fabrik vps-sync --verify
# Exit 0 = clean. Exit 1 = drift found. Exit 2 = scan failed.
```

Implementation: `scripts/vps_sync.py::verify_residue()` (full 12-point audit) + `verify_gatus_aliases()` (stale Coolify hostnames) + `verify_limits()` (memory-limit drift after reboot).

## Pre-action discipline

1. **Always use `fabrik destroy --drop-data -y`** for throwaway test specs. Reverses the 7-registrar provision chain in inverse order (DEPLOYMENT.md §9.4: meilisearch → authelia → glitchtip → backrest → gatus → postgres → coolify → DNS → files).
2. **Never use long-lived test names** like `fabrik-test`, `proxy-test`. Use timestamped throwaways (e.g. `fabrik-e2e-2026-05-17`).
3. **After ANY `fabrik destroy`, run `fabrik vps-sync --verify`** to confirm orphans are zero across all registrars.

## What the verifier checks

`fabrik vps-sync --verify` calls three scanners. Combined coverage:

| # | Surface | What it flags |
|---|---|---|
| 1 | Coolify apps | `fabrik-*-test*`, `*-e2e-*`, `integration-test*`, any `_is_test_name` match |
| 2 | GlitchTip projects | `GET /api/0/organizations/ocoron/projects/` returning test/e2e slugs |
| 3 | Gatus configs | `*.bak.*` files in `/opt/monitoring/configs/gatus/apps/`; duplicate endpoints |
| 4 | Authelia rules | Orphan `access_control` entries for domains with no live Coolify app |
| 5 | Postgres DBs | `fabrik_*_test*` or `*_e2e_*` databases on `postgres-main` |
| 6 | Meilisearch indexes | Test indexes |
| 7 | DNS A records | Records pointing to destroyed services |
| 8 | Docker volumes | `docker volume ls -f dangling=true`; especially `<svc>_postgres_data` after migration to `postgres-main` |
| 9 | Dangling images | `docker images -f dangling=true` non-empty |
| 10 | `/tmp` locks | Stale `/tmp/fabrik-*-test-*.lock` files (`run_locked` should clean; verify) |
| 11 | `/opt/` | `test-*`, `*-test`, `wp-test` ad-hoc files / orphan project trees |
| 12 | Backrest | Test repos at `/srv/backrest/repos/<test-name>/` |
| 13 | Gatus aliases | URLs pinned to Coolify auto-generated container hostnames (`<svc>-<24chars>-<13digits>`) — break on every redeploy |
| 14 | Memory limits | Containers with `HostConfig.Memory=0` (limits reset on reboot; rerun `vps_apply_limits.sh`) |

## Manual recovery if `--verify` exits 1

The script prints exact remediation commands per finding. Common patterns:

| Finding | Fix |
|---|---|
| Stale Gatus alias | Update `/opt/monitoring/configs/gatus/apps/<svc>.yaml` to use stable Docker DNS name (compose service name or registered alias from `scripts/vps_apply_limits.sh`); restart Gatus |
| Orphan Coolify app | `fabrik destroy specs/services/<id>.yaml --drop-data -y` if spec exists, else delete via `fabrik apply` (SSH + Docker Compose) UI + manual DB drop |
| Dangling Docker volume | `ssh vps 'sudo docker volume rm <name>'` after confirming no live container references it |
| Memory limit reset | `ssh vps 'bash /opt/fabrik/scripts/vps_apply_limits.sh'` |
| `/tmp` lock | `ssh vps 'rm /tmp/fabrik-*-test-*.lock'` after confirming no live process holds it |

## Cross-references

- Destroy mechanics: `docs/DEPLOYMENT.md` §9.4 (Tear down a service)
- e2e validation playbook (which generates throwaway state): `docs/DEPLOYMENT.md` §9.6
- Coolify alias persistence: `docs/reference/coolify-stable-aliases.md` + `scripts/vps_apply_limits.sh`
- 7-registrar provisioner inverse: `src/fabrik/orchestrator/destroyer.py::destroy_deployment()`

## Why this matters

Every residue item is silent cost: orphan Postgres DBs eat disk, dangling Docker volumes eat inodes, stale Gatus targets emit false-positive alerts, orphan Authelia rules expand the attack surface. A 30-second `fabrik vps-sync --verify` after each destroy keeps the VPS in a state that matches `data/projects.yaml`.
