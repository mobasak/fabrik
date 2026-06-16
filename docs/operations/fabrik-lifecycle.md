# Fabrik Lifecycle — Runtime Behavior & Data Safety

**Last reviewed:** 2026-06-15 (added the `--target-vps` / multi-host section; verified against `cli.py` + `deployer_ssh.py` + `context.py`)
**Purpose:** What happens to running containers, data, volumes, and env vars during each Fabrik operation. Read this before running any command on a system with live data.

---

## Quick Safety Matrix

| Operation | Containers | Volumes | Database (postgres-main) | .env on VPS | VPS directory |
|---|---|---|---|---|---|
| `fabrik redeploy <app>` | Rebuilt + restarted | Untouched | Untouched | Untouched | Git pulled (git source) or unchanged (non-git) |
| `fabrik apply <spec>` (new) | Created | Created | Created by registrar | Written fresh | Created |
| `fabrik apply <spec>` (existing) | Recreated if config changed | Untouched | Untouched | Read-merged | Updated |
| `fabrik redeploy --refresh-infra` | Untouched (unless registrar injects env) | Untouched | Untouched | May be updated by registrars | Untouched |
| `fabrik destroy <spec>` | Removed | **Preserved** (plain `down`; `-v` only with `--drop-data`) | **NOT dropped** (manual only) | Removed with directory | **Removed** (`rm -rf`) |
| `fabrik destroy --drop-data` | Removed | **Removed** | **Dropped** | Removed | **Removed** |
| Rollback (automatic) | Removed | **Removed** (`-v`) | **NOT dropped** (logged) | Removed | **Removed** |

---

## Redeploy — The Common Case

`fabrik redeploy <app>` is the most frequent operation. Here's exactly what happens on the VPS:

### Git-sourced apps

```
Step 0: ssh: cd /opt/<app> && sudo git rev-parse HEAD     ← captures current commit as rollback point
Step 1: ssh: cd /opt/<app> && sudo git pull               ← pulls from GitHub remote
Step 2: ssh: cd /opt/<app> && sudo docker compose build   ← rebuilds image from new code
Step 3: ssh: cd /opt/<app> && sudo docker compose up -d --wait  ← restarts, blocks until healthy
```

**Health-check rollback (git sources):** if Step 3 fails (`up -d --wait` exits non-zero because the container never becomes healthy), the deployer automatically reverts: `git reset --hard <captured-sha>` → rebuild → `up -d --wait` to restore the last-known-good container, then raises `DeployError`. New code is *not* left live. For non-git sources there is no recoverable image, so the deployer fails loudly without an automatic revert.

**With `--force`:** Step 2 adds `--no-cache` (full rebuild, ignoring Docker layer cache). For non-git sources, `--force` adds `--force-recreate` to `docker compose up -d --wait` instead.

### What `docker compose up -d --wait` actually does

Docker Compose compares the running container's config against the compose.yaml:

- **Config changed** (new image, env change, label change) → stops old container, removes it, creates new one, starts it. This is a **stop-then-start** sequence, not rolling. There are a few seconds where the container is down.
- **Config unchanged** → does nothing. Container keeps running.
- **Volumes are NEVER touched** by `up -d --wait`. Named volumes persist across container recreates.
- **Network stays** — the container rejoins the `fabrik` network automatically.

### Downtime window

From the moment Docker stops the old container to when the new one passes its healthcheck and Traefik routes traffic to it:

- **Typical:** 3-15 seconds (depending on image build time and app startup)
- **Worst case:** up to `start_period` (usually 30-40s, per project type) if the app is slow to boot
- **During this window:** Traefik returns 502 for requests to this service
- **In-flight requests:** terminated when the old container stops (TCP RST)

This is inherent to Docker Compose on a single node. Zero-downtime rolling deploys require Swarm/K8s. For a solo-dev VPS this is acceptable.

### What redeploy does NOT touch

- **`.env` file** — redeploy never reads or writes `.env`. Only `fabrik apply` and `inject_env()` touch it.
- **Database** — postgres-main is a separate container. App database tables, data, and schema are untouched.
- **Redis** — redis-main is a separate container. Cached data persists.
- **Other containers** — only the target app's container is affected.
- **Volumes** — named volumes survive container recreation.
- **DNS records** — unchanged.
- **Infrastructure registrars** — Gatus, Authelia, Backrest, GlitchTip configs are not re-run.

---

## Apply (Update) — Existing Service

When `fabrik apply` targets a service that already exists (`/opt/<name>/compose.yaml` found on VPS):

1. **Compose.yaml** — for template/docker source: regenerated and written to VPS via SCP (**overwritten**). For git source: updated by `git pull` from the repo (deployer does not write compose.yaml). For local source: untouched (already exists at `source.path`)
2. **`.env`** is read-merged:
   - Reads existing `/opt/<name>/.env` from VPS
   - Layers spec `env:` block values on top
   - Layers `ctx.secrets` on top (highest priority)
   - Writes merged result back
   - **Registrar-injected vars (SENTRY_DSN, GLITCHTIP_DSN, REDIS_URL) and spec-sourced vars (DATABASE_URL) are preserved** because they exist in the old .env and aren't overwritten unless the spec explicitly declares them
3. **`sudo docker compose up -d --wait`** — for git source, `sudo docker compose build` runs first (same as redeploy), then `up -d --wait` recreates only if config changed and blocks until healthy
4. **Infrastructure registrars** run again — they are idempotent (CREATE IF NOT EXISTS, add-if-missing patterns)
5. **Resource tracking** — no new `compose` resource tracked (only new deploys get tracked for rollback)

---

## Apply (New) — First Deploy

1. Directory created on VPS: for template/docker source, `mkdir -p /opt/<name>/`. For git source, `git clone` creates the directory. For local source, directory must already exist at `source.path`.
2. Files written to VPS: for template source, compose.yaml + .env (+ Dockerfile if rendered) via SCP. For docker source, a generated compose.yaml + .env via SCP. For git source, `git clone` pulls compose.yaml + Dockerfile from the repo, deployer only writes .env via SCP. For local source, compose.yaml already exists at `source.path`, deployer only writes .env
3. For git source: `sudo docker compose build` (builds image from Dockerfile in repo), then `sudo docker compose up -d --wait`. For other sources: `sudo docker compose up -d --wait` directly (image already specified in compose.yaml or pre-built)
4. Resource tracked: `ctx.add_resource("compose", name, name=name)` — enables rollback if later phases fail
5. Infrastructure registrars run (create DB, Gatus endpoint, GlitchTip project, etc.)
6. Health check verification
7. If any phase fails → automatic rollback tears down everything created

---

## Destroy

`fabrik destroy specs/services/<name>.yaml` tears down in reverse order of provisioning:

### What gets destroyed

1. **Infrastructure registrars** (in destroyer order — approximately reverse of provisioning):
   - Prometheus scrape job removed (first down, last up)
   - MeiliSearch index deleted (only with `--drop-data`)
   - Authelia access rule removed, authelia restarted
   - GlitchTip project deleted
   - Grafana annotations skipped (informational, auto-expire)
   - Backrest backup plan removed
   - Gatus endpoint removed, gatus restarted
   - Postgres database skipped (preserved; dropped only with `--drop-data`)
   - Redis index slot released (data NOT flushed; flushed with `--drop-data`)
2. **App container + volumes:**
   - `sudo docker compose down` — stops container and removes it. Adds `-v` (also removes named volumes) **only with `--drop-data`**; a plain destroy preserves app-local volumes.
   - `sudo rm -rf /opt/<name>` — removes all files (compose.yaml, .env, source code, Dockerfile)
   - `sudo docker image prune -f` — removes dangling images
3. **DNS record** removed (unless `--keep-dns`)

### What is deliberately NOT destroyed (without `--drop-data`)

- **Postgres database** — skipped with message "database preserved (pass --drop-data to drop)". Use `--drop-data` to actually DROP DATABASE.
- **Redis data** — index slot is released (freed for next service), but data is NOT flushed. Use `--drop-data` to FLUSHDB.
- **MeiliSearch index** — skipped with message "index preserved (pass --drop-data to delete)". Use `--drop-data` to delete the index.

### The `-v` flag in `docker compose down`

The destroyer runs `docker compose down -v` **only when `--drop-data` is passed**; a plain `fabrik destroy` runs `docker compose down` (no `-v`), preserving app-local named volumes. This mirrors the postgres/redis/meilisearch contract — nothing data-bearing is removed without `--drop-data`. (Automatic rollback is the exception: `SSHDeployer.delete()` always uses `down -v`, since a half-created app being rolled back has no data worth keeping.)

For most Fabrik services this distinction rarely matters — app containers are stateless (data lives in postgres-main, redis-main, or Backrest-managed volumes). But if a service declares a local volume with important data, `--drop-data` will delete it.

---

## Database Migrations

The deployer has **no built-in migration step**. This is deliberate — the deployer deploys containers, it doesn't know app internals.

### How migrations work

Apps that use Alembic (or any migration framework) must handle migrations in their **container entrypoint**:

```dockerfile
# Dockerfile entrypoint pattern
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8000"]
```

Or via a startup script:

```bash
#!/bin/bash
set -e
alembic upgrade head
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Migration safety

- Migrations run **inside the container** on the same `postgres-main:5432` connection the app uses
- They run **before** the app starts accepting traffic (sequential in entrypoint)
- If a migration fails, the container crashes → Docker marks it unhealthy → Gatus alerts
- **Destructive migrations** (DROP TABLE, DROP COLUMN) need manual review — the deployer can't protect against data loss from bad migration code

### What the deployer guarantees

- The **database server** (postgres-main) is never stopped, restarted, or modified during deploy
- The **database** (CREATE DATABASE) is only created once by the postgres registrar — never dropped unless `fabrik destroy --drop-data` is explicitly used
- The **connection string** (`DATABASE_URL`) is preserved across deploys via .env read-merge
- The **container** runs migrations at startup, before handling traffic

---

## .env Injection Flow

Understanding when `.env` is written helps predict whether your env vars will survive:

| Event | .env touched? | Strategy | Registrar vars preserved? |
|---|---|---|---|
| `fabrik apply` (new) | Yes — written fresh | No existing file to read | N/A (first deploy) |
| `fabrik apply` (existing) | Yes — read-merged | Read existing → layer spec → layer secrets | Yes |
| `inject_env()` (redis/glitchtip registrar) | Yes — read-merged | Read existing → add new vars → write back + restart | Yes |
| `fabrik redeploy` | **No** | .env not touched | Yes (untouched) |
| `fabrik redeploy --refresh-infra` | Maybe — only if registrar calls `inject_env()` | Read-merge | Yes |
| `fabrik destroy` | N/A — file deleted with directory | — | — |

### Merge precedence (highest wins)

```
ctx.secrets          ← from SecretsManager (env vars, .env, generated). CLI -s flags are injected into os.environ, then read as env vars.
ctx.spec["env"]      ← from spec YAML env: block
existing .env on VPS ← registrar-injected vars, previous deploy values
```

If both the spec and the existing .env define `FOO=bar`, the spec's value wins. If only the existing .env has `SENTRY_DSN=...` (injected by glitchtip registrar), it's preserved.

---

## Failed Deploys and Recovery

### Container crashes after redeploy

**Symptom:** Container restarts in a loop, Gatus goes red, Traefik returns 502.

**What happened:** New code has a bug that crashes at startup. Docker restarts it (`restart: unless-stopped`), it crashes again.

**Note (git sources):** if the container never passes its healthcheck during the redeploy itself, `up -d --wait` fails and the deployer auto-reverts to the previous commit (see "Health-check rollback" above) — so a *fresh* git `fabrik redeploy` won't leave you in this loop; it restores the last-good build and reports the failure. This crash-loop scenario applies when a bug only surfaces *after* a deploy that did pass its healthcheck (e.g. crashes on first real request), or for non-git sources which have no automatic revert.

**Recovery:**
```bash
# Option A: revert the commit (run locally in WSL, not on VPS)
cd /opt/<service>
git revert HEAD && git push
fabrik redeploy <service>

# Option B: manual rollback on VPS (faster, no git history change)
ssh vps "cd /opt/<service> && sudo git checkout HEAD~1 && sudo docker compose build && sudo docker compose up -d --wait"
# WARNING: This puts the VPS repo in detached HEAD state. Next `fabrik redeploy`
# (which runs `git pull`) will fail until you fix it:
#   ssh vps "cd /opt/<service> && sudo git checkout main"
# Then fix the code locally, commit, push, redeploy properly
```

**Note:** The previous Docker image is still cached on the VPS. Docker doesn't delete old layers immediately — `docker image prune` only runs during `fabrik destroy` and automatic rollback (via `SSHDeployer.delete()`), not redeploy.

### Apply fails mid-way (automatic rollback)

If `fabrik apply` fails at any phase, the rollback manager automatically unwinds:

- Phase 3 (DNS) fails → DNS record removed
- Phase 4 (deploy) fails → compose app removed (`sudo docker compose down -v` + `sudo rm -rf`)
- Phase 4b (registrar) fails → each registrar rolled back in reverse order
- Phase 5 (verify) fails → everything rolled back

**Exception:** Postgres databases and MeiliSearch indexes are NEVER auto-dropped during rollback. They're logged as manual actions.

**`--keep-on-failure`** skips rollback entirely — leaves everything in place for debugging. Manual cleanup required afterward.

### SSH connection failure

If SSH to the VPS fails during deploy:
- `RuntimeError` from `ssh()` driver → propagates up to orchestrator's generic `except Exception` handler (not wrapped in `DeployError`)
- Rollback attempts to clean up (but may also fail if SSH is down)
- Check VPS health separately: `ping vps1.ocoron.com`, direct SSH

---

## Targeting a host — `--target-vps` (multi-host)

Fabrik is a 3-host fleet (vps1 hub + vps2/vps3 spokes), so every lifecycle command resolves **which host** it acts on. `apply`, `redeploy`, and `destroy` all accept `--target-vps <vpsN>`; everything in the sections above (the `ssh:` / `cd /opt/<app>` steps, the safety matrix, the recovery commands) runs **on the resolved host**.

**Resolution order (highest wins):**

```text
--target-vps  <CLI flag>
  > state file   .fabrik/state/<id>.json :: target_vps   (where the service was last deployed)
  > spec field   target_vps:
  > vps1         (default if nothing else set)
```

> **`redeploy <app>` has no spec argument**, so it skips the spec-field tier — its order is `CLI > state file > vps1`. The spec-field tier applies only to `apply` and `destroy`, which take a spec path.

- **Get it right on multi-host.** If a service lives on vps2 and a `redeploy` resolves to vps1, you act on the wrong box. The state file records where each service was last deployed, so re-runs target the same host without re-passing the flag.
- **Spokes are full deploy targets.** `fabrik apply <spec> --target-vps vps2` deploys on vps2 (its own Traefik); the spec's `shape:` registrars still wire to the **shared vps1 data plane** — `postgres-main:5432` / `redis-main:6379` over the mesh, Gatus/Prometheus on vps1. `destroy --target-vps vps2` tears down on vps2.
- **Not the same as Vultr drills.** Throwaway drill droplets are created/destroyed by `fabrik vultr drill`, never by `apply` / `destroy --target-vps`.

## Operational Gotchas

### Authelia restarts

Every Authelia rule change (add/remove access rule) triggers `sudo docker restart authelia`. If you deploy 3 services with `is_admin_dashboard: true` in quick succession, that's 3+ Authelia restarts, causing brief 502s on all Authelia-protected routes.

**Mitigation:** The rollback deduplicates Authelia calls per-domain (authelia + authelia_bypass → one `remove_access_rule` call). But successive deploys don't coordinate.

### Gatus restarts

Similar to Authelia — each `add_endpoint` / `remove_endpoint` restarts gatus. Brief monitoring gaps during rapid sequential deploys.

### Container name stability

All compose files must declare `container_name: <name>`. Without it, Docker generates names like `<project>-<service>-1` which change unpredictably. The `ComposeLinter` warns if `container_name` is missing; the deployer's `_validate_compose()` treats it as an error (blocks deployment) — but only for **template** and **docker** source types. Git and local sources manage their own compose files and skip `_validate_compose()`, so a missing `container_name` there is caught only by `ComposeLinter` (a warning), not blocked at deploy.

### The `fabrik` network name

The Docker network is named `fabrik` (renamed from `coolify` 2026-05-31). All services join this external network for inter-container communication and Traefik routing — it's a standard Docker bridge network. `fabrik apply` rejects a compose still declaring the old `coolify` network.

---

## Summary: What's Safe and What's Not

| Action | Safe for live data? | Notes |
|---|---|---|
| `fabrik redeploy` | **Yes** | Only rebuilds + restarts the app container. DB/Redis/volumes untouched. |
| `fabrik apply` (existing) | **Yes** | .env read-merged, container recreated only if changed. DB untouched. |
| `fabrik apply` (new) | **Yes** | Creates new resources only. Nothing existing is modified. |
| `fabrik redeploy --refresh-infra` | **Yes** | Registrars are idempotent. May inject new env vars. |
| `fabrik destroy` | **Partially** | App removed; app-local volumes preserved (removed only with `--drop-data`). DB deliberately preserved unless `--drop-data`. |
| `fabrik destroy --drop-data` | **No** | Drops everything including the database. |
| VPS reboot | **Yes** | `restart: unless-stopped` auto-recovers all containers. |
| Failed deploy (auto-rollback) | **Yes** | Cleans up created resources. DB never auto-dropped. |
