# Coolify API Reference (historical — Coolify removed 2026-05)

> **⚠️ Historical.** Coolify was removed from the VPS in May 2026. This API
> reference is preserved for the handful of legacy CLI commands (`fabrik
> status`, `fabrik logs`, `fabrik reconcile-all`) still targeting Coolify-era
> endpoints for services that were never migrated. New deploys go through
> `orchestrator/deployer_ssh.py` (SSH + Docker Compose). See
> [docs/operations/deployment.md](../operations/deployment.md).

**Last Updated:** 2026-04-27 (verified live against `coolify.vps1.ocoron.com` running Coolify v4.0.0-beta.459 — host removed post-migration)
**Authoritative source:** https://coolify.io/docs/api-reference/

This document records the **subset Fabrik actually uses**. For the full API, see Coolify's docs. Every endpoint listed here was probed live before publication.

## Base URL

```
https://coolify.vps1.ocoron.com/api/v1
```

## Authentication

Bearer token in `Authorization` header. Tokens are created in Coolify UI under `Keys & Tokens` / `API tokens`.

## Endpoint Map (Verified Live, Coolify v4.0.0-beta.459)

| Endpoint | Status | Purpose |
|----------|--------|---------|
| `GET /applications` | ✅ 200 | List all applications |
| `GET /applications/{uuid}` | ✅ 200 | Get application details (incl. `status`, `fqdn`) |
| `POST /applications` | ❌ 404 | **Removed.** Use one of the typed create endpoints below. |
| `POST /applications/public` | ✅ 201 | Create app from public git repo |
| `POST /applications/private-deploy-key` | ✅ exists | Create app from private git repo (deploy-key auth) |
| `POST /applications/private-github-app` | ✅ exists | Create app from private git repo (GitHub App auth) |
| `POST /applications/dockerimage` | ✅ exists | Create app from a Docker registry image |
| `POST /applications/dockercompose` | ✅ exists | Create app from inline (base64) Docker Compose YAML |
| `POST /applications/dockerfile` | ✅ exists | Create app from a Dockerfile string |
| `DELETE /applications/{uuid}` | ✅ exists | Queue application deletion |
| `POST /applications/{uuid}/deploy` (or `/deploy?uuid=...&force=...`) | ✅ exists | Trigger deploy |
| `GET /applications/{uuid}/deployments` | ✅ exists | List deployments |
| `GET /applications/{uuid}/logs` | ✅ exists | Container logs |
| `PATCH /applications/{uuid}/envs` | ✅ exists | Update env vars |
| `POST /services/...` | — | Coolify treats `dockercompose` apps as **services** internally; some operations resolve under `/services/{uuid}` |
| `GET /services` | ✅ 200 | List one-click stacks (separate table from Applications) |
| `GET /services/{uuid}` | ✅ 200 | Get service incl. `docker_compose_raw` field |
| `PATCH /services/{uuid}` | ✅ 200 | Update service. **`docker_compose_raw` must be base64-encoded** (HTTP 422 if you send raw YAML — see Gotcha below) |

The previous version of this doc claimed `POST /applications/private-deploy-key` was removed — that was wrong. All three typed git-create endpoints exist in v4.0.0+.

## Create Application from Public Git Repo

**Endpoint:** `POST /applications/public`

**Required fields:**
- `project_uuid` (string)
- `server_uuid` (string)
- `environment_uuid` (string) — preferred; `environment_name` also accepted
- `git_repository` (string) — HTTPS URL for public repos (e.g. `https://github.com/user/repo.git`)
- `git_branch` (string)
- `build_pack` (string) — one of `dockercompose`, `dockerfile`, `nixpacks`, `static`
- `ports_exposes` (string) — space-separated port list, e.g. `"8000"` or `"3000 8000"`

**High-impact optional fields (Fabrik should send most of these):**

| Field | Purpose |
|-------|---------|
| `name` | Application name in Coolify UI |
| `description` | Short description |
| `domains` | **CRITICAL.** FQDN(s) for Traefik routing, e.g. `"https://app.vps1.ocoron.com"`. Without it, Coolify auto-generates a `<uuid>.<server-ip>.sslip.io` domain. **Fabrik MUST set this** so the spec's `domain` matches what Traefik routes. |
| `docker_compose_location` | Path to compose file in repo. Default: `/compose.yaml`. |
| `docker_compose_domains` | `[{ "name": "service", "domain": "app.example.com" }]` — per-service domain mapping for compose apps with multiple exposed services. |
| `is_force_https_enabled` | Force HTTPS redirect at Traefik. |
| `autogenerate_domain` | When `false`, prevents the sslip.io fallback if `domains` is missing. |
| `instant_deploy` | If `true`, Coolify deploys immediately after create. Set `false` if you need to PATCH env vars first. |
| `health_check_*` | Coolify-managed healthcheck (separate from Docker healthcheck in the compose). |
| `limits_memory`, `limits_cpus` | Resource caps. |

**Response (201):** `{"uuid": "<application_uuid>"}`

**Verified payload pattern (Fabrik):**

```json
{
  "project_uuid": "lww8g0oc48cg4gw08oc8k40k",
  "server_uuid": "jk4wskkcks8csg4gcokwgw8s",
  "environment_uuid": "fo8084scow0s0wg4wwgg00cw",
  "git_repository": "https://github.com/mobasak/fabrik-test-python-api.git",
  "git_branch": "main",
  "build_pack": "dockercompose",
  "docker_compose_location": "/compose.yaml",
  "ports_exposes": "8000",
  "name": "fabrik-test-python-api",
  "domains": "https://fabrik-test-python-api.vps1.ocoron.com",
  "instant_deploy": false
}
```

## Create Application from Private Git (Deploy-Key)

**Endpoint:** `POST /applications/private-deploy-key`

Same payload as public, plus:
- `private_key_uuid` (string) — UUID of an SSH key registered in Coolify (Keys & Tokens → Private Keys).
- `git_repository` should be the SSH URL (e.g. `git@github.com:user/repo.git`).

## Create Inline Docker Compose Application

**Endpoint:** `POST /applications/dockercompose`

```json
{
  "name": "string",
  "project_uuid": "string",
  "server_uuid": "string",
  "environment_name": "production",
  "docker_compose_raw": "<base64-encoded-compose-yaml>",
  "instant_deploy": false
}
```

**Hard constraints:**
- `docker_compose_raw` MUST be base64-encoded.
- Coolify's validator silently rejects any non-ASCII byte in the **decoded** payload with a misleading `"docker_compose_raw should be base64 encoded"` error. Fabrik's `coolify.py::create_dockercompose_application` raises `ValueError` pre-flight to surface this. (See B5 in CHANGELOG, 2026-04-27.)
- The inline path has **no source tree** — `build:` directives in the compose will silently never run because there is no build context. Use one of the git-create endpoints when the compose has `build:`.

## Create Application from Docker Image

**Endpoint:** `POST /applications/dockerimage`

```json
{
  "project_uuid": "string",
  "server_uuid": "string",
  "environment_name": "production",
  "docker_registry_image_name": "image:tag",
  "name": "application-name",
  "domains": "https://app.vps1.ocoron.com",
  "ports_exposes": "3000",
  "ports_mappings": "3000:3000",
  "health_check_enabled": true,
  "health_check_path": "/",
  "health_check_port": "3000",
  "health_check_start_period": 15,
  "limits_memory": "512M",
  "limits_cpus": "1.0",
  "instant_deploy": true
}
```

**Notes:**
- `ports_mappings` is `host:container` format.
- For heavy images (Browserless, etc.) bump `health_check_start_period` to 60+ and `limits_memory` to ≥2G.
- Port 3000 on the VPS is already occupied by Gotenberg — pick another for new image-based apps.

## Get Application

**Endpoint:** `GET /applications/{uuid}`

Returns the full application object. Fields Fabrik relies on:

| Field | Type | Notes |
|-------|------|-------|
| `uuid` | string | |
| `name` | string | |
| `status` | string | `running:healthy` / `running:unhealthy` / `exited:unhealthy` / `degraded:exited` / etc. — uuid-based polling key (see `deployer.py::_wait_for_app_status`). |
| `fqdn` | string\|null | Coolify-resolved FQDN. May be sslip.io fallback if `domains` was not set on create. |
| `git_repository` | string | |
| `git_branch` | string | |
| `build_pack` | string | |
| `docker_compose` | string | The compose YAML Coolify cloned from the repo. |
| `custom_labels` | string (base64) | Traefik labels Coolify computed from the compose. |

## Trigger Deploy

**Endpoint:** `POST /deploy?uuid={uuid}&force={true|false}` or `POST /applications/{uuid}/deploy`

`force=true` rebuilds even when no commit changed (used after a PATCH to env vars).

## Update Env Vars

**Endpoint:** `PATCH /applications/{uuid}/envs`

Body:
```json
{ "data": [{ "key": "SENTRY_DSN", "value": "https://...", "is_preview": false }] }
```

Coolify returns success **before** the new env vars land in the running container — the container is recreated by the next deploy. Always follow with `POST /deploy?force=true` and a ground-truth verification (Fabrik uses `verify_dsn_injection` which polls `docker inspect` env on the actual container).

### ⚠️ Single-row PATCH: match by `(key, is_preview)`, not by env_uuid (Lesson 57)

Coolify v4 matches the row to update by the `(key, is_preview)` tuple in the body — there is **no per-env-row endpoint**. The driver's `CoolifyClient.update_env_var(uuid, env_uuid, ...)` PATCHes `/applications/{uuid}/envs/{env_uuid}` which returns **HTTP 404** in Coolify v4.0.0-beta.459 — that endpoint does not exist. Always use the bulk endpoint:

```python
coolify._request("PATCH", f"/applications/{app_uuid}/envs", json={
    "key": "DATABASE_URL",
    "value": new_value,
    "is_preview": False,   # REQUIRED — disambiguates prod from preview row
    "is_literal": True,
})
```

Every key in Coolify v4 has TWO rows (one `is_preview=False` = prod, one `is_preview=True` = preview). Omitting `is_preview` defaults to `False` (prod), leaving the preview row stale — the "Webshare gotcha" from `vps-urls.md`. Update both rows independently to keep preview deploys correct (Lesson 58). The fixed pattern is canonicalized in `scripts/migrate_db_rename.py` — use it as the reference implementation until `CoolifyClient.update_env_var()` is fixed.

## Delete Application

**Endpoint:** `DELETE /applications/{uuid}`

Returns immediately; deletion is queued. The container is removed asynchronously (~10-30s).

## Application Status Values (Observed Live)

| Status | Meaning |
|--------|---------|
| `running:healthy` | Container up, healthcheck passing |
| `running:unhealthy` | Container up, healthcheck failing |
| `exited:unhealthy` | Container exited (build failed, app crashed, or healthcheck killed it). Terminal. |
| `degraded:exited` | Multi-service app: at least one service exited. Terminal. |
| `degraded:unhealthy` | Multi-service app: at least one service unhealthy. |
| `restarting:*` | Mid-restart cycle. |

Treat `exited:*`, `degraded:exited`, and `killed` as terminal failure states — no point waiting for them to recover. Polling logic should bail early on these.

## Known Operational Gotchas

### Coolify treats compose apps as Services internally

`POST /applications/dockercompose` returns a UUID, but the resource is sometimes reachable under `/services/{uuid}` rather than `/applications/{uuid}`. Fabrik's `coolify.py::_resolve_resource_base` probes both.

### Container naming is driven by compose service name, NOT Coolify app name

A compose with `services: { app: ... }` produces containers named `app-<coolify-uuid>-<timestamp>`, **not** `<coolify-app-name>-...`. Polling logic that greps by app name will silently miss the container forever. Use `_wait_for_app_status` (uuid-based, queries Coolify API) instead. (See B11 in CHANGELOG, 2026-04-27.)

### Traefik routing requires either `domains` field OR labels in compose

For a compose-deployed app to be reachable at `https://app.vps1.ocoron.com`, **one** of these must be true:
- The `domains` field on the create call is set (Coolify injects Traefik labels).
- The `compose.yaml` itself contains explicit `traefik.http.routers.<name>.rule=Host(...)` labels.

The scaffolded `compose.yaml` Fabrik emits via `templates/scaffold/docker/compose.yaml.template` historically had **neither**, which is why deployed-but-unrouted apps would 404 on the spec domain even when the container itself was healthy. (See B16 in CHANGELOG, 2026-04-27.)

### `POST /applications` returns 404

The legacy unified endpoint was removed in Coolify v4 in favor of the typed family (`/public`, `/private-deploy-key`, `/private-github-app`, `/dockerimage`, `/dockercompose`, `/dockerfile`). Drivers must dispatch on auth/source type.

### `instant_deploy: true` on `/applications/dockercompose` is unreliable

Inline-compose creations sometimes leave the service at `status=exited` even with `instant_deploy: true`. Fabrik always follows the create with an explicit `POST /deploy?force=true`. (See `deployer.py::_create_deployment` post-create hook.)

### `PATCH /services/{uuid}` requires `docker_compose_raw` to be **base64-encoded** (F5, Lesson 62)

Sending raw YAML in the `docker_compose_raw` field of a PATCH to `/api/v1/services/{uuid}` returns:

```text
HTTP 422
{"message": "Validation failed.", "errors": {"docker_compose_raw": "The docker_compose_raw should be base64 encoded."}}
```

The fix is to base64-encode the YAML string before sending:

```python
import base64
encoded = base64.b64encode(new_compose_yaml.encode()).decode()
patch_body = {"docker_compose_raw": encoded}
```

GET on the same endpoint returns the compose **decoded** (plain YAML) — the encoding requirement is asymmetric (write only).

This affects any tool mutating Coolify Services compose programmatically; see `scripts/coolify_services_f5.py` for a reference implementation that uses this pattern to inject `deploy.resources.limits` into 12 services.

### Coolify Service compose on disk is REGENERATED from `docker_compose_raw` on every redeploy

`/data/coolify/services/<uuid>/docker-compose.yaml` is a render artifact of the DB field, not source of truth. Editing the file directly is silently reverted on the next redeploy. Always mutate via `PATCH /services/{uuid}`. This is the key difference from Coolify Applications, where the compose lives in an external git repo that Coolify clones.

### Silent build-trigger failure for `dockercompose` apps (2026-05-16, Coolify #9161)

Coolify sometimes creates the application, writes the rewritten `docker-compose.yaml` to `/data/coolify/applications/<uuid>/`, sets the `image:` tag in the compose — but **never clones the git repo, never builds the image, never starts the container.** The API reports `exited:unhealthy` indefinitely. No build logs exist (the deployment status is `failed` with an empty log body).

**Root cause:** Coolify's orchestration step between "write compose" and "docker compose build && up" silently fails. Confirmed on v4.0.0-beta.459. Matches GitHub issue #9161.

**Workaround implemented in `deployer.py::_ssh_fallback_build`:** after the `terminal_grace_period` (300s) expires with `exited:unhealthy`, the deployer SSHs into the VPS, clones the git repo into the app dir, builds using Coolify's `docker-compose.yaml` (NOT the repo's `compose.yaml`), and starts the container. The key distinction: Coolify's compose has the UUID-based `container_name` that Coolify monitors — using the repo's compose would create a differently-named container that Coolify can't see.

**Additional precondition (Fix 3):** Coolify injects `env_file: .env` into the compose but doesn't create the file before `docker compose config` runs during the build step. The deployer now pre-seeds `touch /data/coolify/applications/<uuid>/.env` via SSH immediately after app creation, before triggering the deploy.

### `GET /applications/{uuid}/deployments` returns 404 for `dockercompose` apps

Confirmed Coolify v4 bug. The per-app deployments sub-resource endpoint 404s for `build_pack=dockercompose` applications. The driver (`coolify.py::get_deployments`) falls back to the global `GET /deployments` endpoint and filters by UUID in Python.

### Destroy must SSH-stop containers started by the SSH fallback

When `_ssh_fallback_build` starts a container via `docker compose up -d`, Coolify doesn't own the container lifecycle. A subsequent `DELETE /applications/{uuid}` removes the DB record but does NOT stop the running container. `_destroy_coolify` now runs `docker compose -f docker-compose.yaml down` via SSH BEFORE the API delete, then `rm -rf` the app directory.

## Observability

For real-time deploy debugging:
- `GET /applications/{uuid}/logs` — container stdout/stderr
- `GET /applications/{uuid}/deployments` — deployment history with build logs (may 404 for dockercompose apps; use global `/deployments` endpoint)
- SSH `docker logs <container>` on VPS as ground truth

## Related Files

- `@/opt/fabrik/src/fabrik/drivers/coolify.py` — driver (uses these endpoints)
- `@/opt/fabrik/src/fabrik/orchestrator/deployer.py` — orchestration around create + deploy
- `@/opt/fabrik/scripts/snapshot_vps_state.py` — leak-detection over Coolify resources
