# Plan: SSH Deployer — Replace Coolify API with SSH + Docker Compose

## Context

Coolify has been removed from the VPS (Phases 0-10, 13 of `docs/development/plans/2026-05-27-coolify-migration.md`). All 31 containers run on standalone Docker Compose. But `fabrik apply/deploy/redeploy/destroy` are broken — the deployer (`src/fabrik/orchestrator/deployer.py`) talks to Coolify API which no longer exists.

This plan implements Phase 11-1: replace the Coolify deployer with an SSH+Docker Compose deployer. The registrar pipeline (postgres, gatus, authelia, glitchtip, backrest, meilisearch, prometheus, grafana, redis) stays intact — only the "how to get a container running" part changes.

## Rule Pack Constraints (from `.windsurf/rules/`)

The deployer generates and validates compose files. These constraints from the rule packs are **hard requirements** that the deployer must enforce or respect:

### Compose Structure (30-ops.md)

- `platform: linux/amd64` — mandatory on every service
- `deploy.resources.limits.memory` — mandatory
- `deploy.resources.limits.cpus` — recommended alongside memory
- No `ports:` section — all traffic routes through Traefik on `coolify` network
- `restart: unless-stopped` — on every service
- `networks: [coolify]` with `coolify` as `external: true`
- No `depends_on: postgres-main` or `redis-main` — external services on coolify network
- `container_name: {name}` — **mandatory** (was forbidden under Coolify; now required for stable `docker exec`/`docker inspect` targeting — Lesson 22)

### Traefik Labels (30-ops.md)

- Entrypoints: `websecure` (NOT `http`/`https` — Coolify's labels were wrong)
- TLS: `tls=true`, `tls.certresolver=letsencrypt`
- Middleware per service category:
  - Admin dashboard: `authelia-forward@docker,gzip@docker`
  - API service: `gzip@docker`
  - Public: none
- `loadbalancer.server.port` must match the app's CMD port

### Health Checks (55-observability.md, 58-resilience.md)

- `/health` must verify real deps (`SELECT 1`, Redis `PING`) — not static 200
- Docker `HEALTHCHECK` must include `start_period: 20s`
- `/health` is Authelia-bypassed globally — never protect it
- Distroless images: `healthcheck: disable: true` in compose (no shell to run checks)

### Container Images (30-ops.md)

- Base images: `slim-bookworm` / `bookworm-slim` (NOT Alpine)
- CMD exec form or `sh -c "exec ..."` for SIGTERM safety

### Networking & DNS (30-ops.md)

- Connection strings use Docker DNS: `postgres-main:5432`, `redis-main:6379`
- Never `localhost` in `DATABASE_URL` or `REDIS_URL`
- Internal service calls: `http://<service>:<port>` on coolify network

### Security (35-security-auth.md)

- M2M auth: `X-Internal-Token` header with `SERVICE_INTERNAL_SECRET_KEY`
- Authelia protects admin dashboards via Traefik forward-auth
- API services bypass Authelia, use token auth
- Generated passwords: 32-char `[a-zA-Z0-9]` via `secrets.choice()`

### Observability (55-observability.md)

- GlitchTip DSN from `GLITCHTIP_DSN` env var — injected by registrar, not hardcoded
- Promtail auto-discovers all containers via docker.sock — no per-service config
- Prometheus scrapes `/metrics` when `shape.exposes_metrics: true`

### Resilience (58-resilience.md)

- SSH calls from deployer ARE external calls — need timeout (already in `ssh()` driver)
- Graceful fallback on SSH failure — raise `DeployError`, don't swallow

### VPS Command Convention

- All `docker` commands via SSH must use `sudo` prefix (`sudo docker compose`, `sudo docker inspect`, etc.) — consistent with all existing Fabrik drivers (glitchtip.py, destroyer.py, postgres.py, etc.)
- `rm -rf` on VPS directories also requires `sudo` (root-owned paths)
- File writes to `/opt/` use the scp-to-tmp-then-sudo-mv pattern (same as gatus.py:197-200, redis.py:119-123): `scp_to_vps(local_tmp, "/tmp/...")` → `ssh("sudo mv /tmp/... /opt/... && sudo chown root:root /opt/...")`. Clean up local temp files in `finally` block.

### Lessons Learnt (cross-cutting)

- **Lesson 22**: Container names must be stable — `container_name:` in compose (replaces Coolify UUID-suffix names)
- **Lesson 30**: Healthcheck validation — distroless images need `health.disabled: true`; Jinja2 templates use positive logic
- **Lesson 31**: Env-var verification MUST use `docker inspect`, NEVER `docker exec printenv` — distroless/scratch images have no shell
- **Lesson 32**: Silent fallbacks — never use `dict.get(key, default)` on contract data without presence check
- **Lesson 36**: Git-sourced redeploy — `git pull` pulls from the remote configured in `.git/config`, not local filesystem
- **Lesson 50**: `SourceType.LOCAL` exists (9 production specs use it) — deployer must handle explicitly, not silently coerce to TEMPLATE
- **Lesson 62**: Coolify had 3 deployment types with different fix paths — now 1 type (compose), confirmed simplification
- **Lesson 64**: Live-state probes are authoritative — after implementation, must do live VPS verification

---

## What Changes

### Step 1: New `src/fabrik/orchestrator/deployer_ssh.py` (~300 lines)

```python
class SSHDeployer:
    """Deploy services via SSH + Docker Compose.

    Replaces ServiceDeployer (Coolify API). Same interface contract:
    deploy() returns app identifier, find_existing() checks VPS state.
    """

    def deploy(self, ctx: DeploymentContext) -> str
    def find_existing(self, name: str) -> dict[str, Any] | None
    def delete(self, name: str, dry_run: bool = False) -> bool
    def inject_env(self, ctx: DeploymentContext, env_vars: dict[str, str]) -> None
    def restart(self, name: str, dry_run: bool = False) -> None
    def redeploy(self, name: str, source_type: str, force: bool = False, dry_run: bool = False) -> None
```

#### `deploy(ctx) -> str`

Dispatches by `source.type` from the spec. `ctx.spec` is a **dict** (not a `Spec` object) — read source type via `ctx.spec.get("source", {}).get("type", "template")` and map to `SourceType` enum. Unlike the old deployer's `type_map` (which omitted `"local"` → Lesson 50 bug), the new deployer maps all 4 types: `{"template": TEMPLATE, "git": GIT, "docker": DOCKER, "local": LOCAL}`.

**Dry-run convention**: All `ssh()` and `scp_to_vps()` calls in the deployer MUST pass `dry_run=ctx.dry_run`. The SSH driver's `dry_run=True` mode logs the command at INFO and returns empty string without executing. The deployer should check `ctx.dry_run` early and short-circuit (log + return dummy name) before any SSH calls, matching the old deployer pattern (line 73-75).

**Name validation** (first, always): `_validate_name(name)` — strict `^[a-z0-9][a-z0-9-]{0,62}$` regex. Raises `DeployError` if invalid. This is a **shell injection prevention** gate — the name is interpolated into SSH commands.

**Template source** (`SourceType.TEMPLATE`):

1. Build `Spec` object from `ctx.spec` dict (same pattern as old deployer lines 492-514: convert `source` dict → `Source()`, set `id`, build `Spec(**spec_dict)`). Then `TemplateRenderer.render(spec_obj, ctx.secrets, dry_run=True)` → `{"compose.yaml": content}` (compose content only — no `.env`). **IMPORTANT**: Always pass `dry_run=True` regardless of `ctx.dry_run` — we need the rendered content strings (not file paths) so we can scp them to the VPS. When `dry_run=False`, `render()` writes files to the local `apps/` directory and returns file paths instead of content, which is not what we want.
2. Validate rendered compose against rule pack constraints (see `_validate_compose()` below)
3. Generate `.env` content via `_write_env_file(ctx, name)` — merges `ctx.spec.get("env", {})` with `ctx.secrets` overlay
4. `ssh("sudo mkdir -p /opt/{name}")` — create app directory (root-owned)
5. Write files using scp-to-tmp-then-sudo-mv pattern: `scp_to_vps(local_tmp, "/tmp/{name}-compose.yaml")` → `ssh("sudo mv /tmp/{name}-compose.yaml /opt/{name}/compose.yaml && sudo chown root:root /opt/{name}/compose.yaml")`. Same for `.env`. Clean up local temp files in `finally` block.
6. `ssh("cd /opt/{name} && sudo docker compose up -d")` — timeout 120s (image pull can be slow)
7. `ssh("cd /opt/{name} && sudo docker compose ps --format json")` — verify container started
8. Return `name` (stored in `ctx.coolify_uuid` for backward compat)

**Git source** (`SourceType.GIT`):

1. Check if repo exists: `ssh("test -d /opt/{name}/.git && echo exists")`
2. New: `ssh("sudo git clone {source.repository} /opt/{name}")` — timeout 120s
3. Existing: `ssh("cd /opt/{name} && sudo git pull")` — timeout 60s
4. Write `.env` from spec env + secrets via `_write_env_file()` → scp-to-tmp-then-sudo-mv pattern
5. `ssh("cd /opt/{name} && sudo docker compose build")` — timeout 300s (build can be slow)
6. `ssh("cd /opt/{name} && sudo docker compose up -d")` — timeout 120s
7. Return `name`

**Note on git source**: `git pull` pulls from the remote configured in the repo's `.git/config` (typically GitHub). Per Lesson 36, the local `/opt/{name}` is a clone, not the source of truth. For the initial clone, `source.repository` from the spec is used.

**Docker source** (`SourceType.DOCKER`):

1. Generate minimal compose.yaml from spec (image, env, labels, healthcheck, resources, `container_name: {name}`)
2. Validate against rule pack constraints
3. Write compose.yaml + .env to `/opt/{name}/` via scp-to-tmp-then-sudo-mv pattern
4. `ssh("cd /opt/{name} && sudo docker compose up -d")` — timeout 120s
5. Return `name`

**Local source** (`SourceType.LOCAL`):

1. Read path from `ctx.spec.get("source", {}).get("path")` (raw dict access — no Spec object needed for LOCAL). Falls back to `/opt/{name}` if `path` is None.
2. Verify compose exists: `ssh("test -f {path}/compose.yaml && echo exists")`
3. Write/merge `.env` from spec secrets via `_write_env_file()` → scp-to-tmp-then-sudo-mv pattern
4. `ssh("cd {path} && sudo docker compose up -d")` — timeout 120s
5. Return `name`

This wires the 9 production specs (image-broker, translator, seo, job-agent, etc.) that use `source.type: local` — per Lesson 50, they were silently coerced to TEMPLATE in the old deployer.

**Note**: `source.path` is used in spec YAML files (e.g., `image-broker.yaml` has `source.path: /opt/image-broker`) but the `Source` Pydantic model currently lacks this field — it's silently ignored during parsing. Step 1b adds it.

**Resource tracking**: `ctx.add_resource("compose", name, name=name)` for new deploys only (not updates). The `add_resource` signature is `(resource_type: str, resource_id: str, **metadata)`.

#### `_validate_compose(content: str) -> list[str]`

Parse rendered compose YAML and check rule pack constraints. Returns list of errors. Per Lesson 32, uses explicit key presence checks (`if "platform" not in service:`), not `.get(key, default)`.

Checks:

- Every service has `platform: linux/amd64`
- Every service has `deploy.resources.limits.memory`
- No service has `ports:` section
- Network `coolify` declared as `external: true`
- Every service has `restart: unless-stopped`
- Traefik labels use `websecure` entrypoint (not `http`/`https`)
- `loadbalancer.server.port` present when `traefik.enable=true`
- No `depends_on` referencing `postgres-main` or `redis-main`
- No `localhost` in environment values for `DATABASE_URL` or `REDIS_URL`
- `container_name` is present (required for stable naming)

Validation is **advisory in dry-run** (log warnings), **fatal in real deploy** (raise `DeployError`).

#### `_write_env_file(ctx, name) -> str`

Generates `.env` content from `ctx.spec.get("env", {})` with `ctx.secrets` overlaid (secrets take precedence, matching old deployer line 807-809). Returns the content string.

**Update vs. new deploy**: For updates (when `/opt/{name}/.env` already exists on VPS), the deployer MUST read the existing `.env` first and merge — preserving registrar-injected keys (`SENTRY_DSN`, `GLITCHTIP_DSN`, `REDIS_URL`) that are not in the spec. Merge order: `existing .env` < `spec.env` < `ctx.secrets` (rightmost wins). This prevents injected secrets from being lost on redeploy. The `inject_env()` method already implements this read-merge pattern; `_write_env_file()` in `deploy()` should use the same logic when updating.

This replaces the two `bulk_update_env_vars` calls that were inside the old `ServiceDeployer`:

- `deployer.py:451` — git-sourced app pre-deploy env push
- `deployer.py:813` — update existing app env vars

Validation:

- No `localhost` in `DATABASE_URL`/`REDIS_URL` values (30-ops.md)
- Ensures `SERVICE_INTERNAL_SECRET_KEY` present if spec has M2M auth needs (35-security-auth.md)

**Parsing**: handles `#` comments, preserves quoted values. Simple line-by-line `key=value` parser — `.env` files in this system are all single-line key=value (no multiline).

#### `find_existing(name) -> dict | None`

```python
_validate_name(name)
try:
    result = ssh(f"test -f /opt/{name}/compose.yaml && echo exists", timeout=10)
except RuntimeError:
    return None  # SSH failed = does not exist or unreachable
if "exists" in result:
    status = ssh(f"cd /opt/{name} && sudo docker compose ps --format json", timeout=15)
    return {"name": name, "status": status, "path": f"/opt/{name}"}
return None
```

**Note**: `find_existing()` raises `RuntimeError` when `test -f` fails (non-zero exit). Catch it and return `None`.

#### `delete(name, dry_run) -> bool`

1. `_validate_name(name)` — shell injection prevention (also in rollback paths — Lesson review finding)
2. `ssh("cd /opt/{name} && sudo docker compose down -v")` — stop + remove volumes
3. `ssh("sudo rm -rf /opt/{name}")` — remove app directory
4. `ssh("sudo docker image prune -f")` — clean dangling images
5. Return `True`

#### `inject_env(ctx, env_vars) -> None`

Replaces `coolify.bulk_update_env_vars()`. Used by GlitchTip and Redis registrars (infrastructure.py:446, infrastructure.py:574).

1. Read name from `ctx.coolify_uuid` (which now stores the app name)
2. `_validate_name(name)`
3. `ssh("sudo cat /opt/{name}/.env 2>/dev/null || echo ''")` — read current .env (may not exist yet; root-owned)
4. Parse into dict (handle `#` comments, preserve order of existing keys)
5. Merge new `env_vars` (overwrite existing keys, append new ones)
6. Write merged content to local temp file → scp-to-tmp-then-sudo-mv: `scp_to_vps(local_tmp, f"/tmp/{name}.env")` → `ssh("sudo mv /tmp/{name}.env /opt/{name}/.env && sudo chown root:root /opt/{name}/.env")`
7. `ssh("cd /opt/{name} && sudo docker compose up -d")` — restart with new env

#### `restart(name, dry_run) -> None`

`ssh("cd /opt/{name} && sudo docker compose up -d")` — recreates changed containers.

#### `redeploy(name, source_type, force, dry_run) -> None`

- **Git source**: `sudo git pull` → `sudo docker compose build` (+ `--no-cache` if force) → `up -d`
- **Template/Docker/Local**: `sudo docker compose up -d --force-recreate` (+ `--build --no-cache` if force)

### Step 1b: Add `path` field to `Source` model in `src/fabrik/spec_loader.py`

The `Source` model (line 103-113) is missing a `path` field. Specs with `source.type: local` declare `source.path: /opt/<name>` in YAML, but the Pydantic model silently discards it (no `extra="forbid"` on `Source`). The deployer needs this field to know where the compose directory lives on the VPS.

```python
class Source(BaseModel):
    """Application source configuration."""

    type: SourceType = SourceType.TEMPLATE
    repository: str | None = Field(default=None, description="Git repo URL")
    branch: str = "main"
    path: str | None = Field(default=None, description="VPS path for local source deployments")
    image: str | None = Field(default=None, description="Docker image")
    image_port: int | None = Field(default=None, description="Container port for image deployments")
    image_command: str | None = Field(
        default=None, description="Override container command for image deployments"
    )
```

One line added. No other changes to spec_loader.py.

### Step 2: Archive `deployer.py` → `deployer_coolify.py`

`git mv src/fabrik/orchestrator/deployer.py src/fabrik/orchestrator/deployer_coolify.py`

No content changes. Available for reference and legacy state-file cleanup.

### Step 3: Modify `src/fabrik/orchestrator/__init__.py`

**Import change:**

```python
# WAS:
from fabrik.orchestrator.deployer import ServiceDeployer
# NOW:
from fabrik.orchestrator.deployer_ssh import SSHDeployer
```

**Constructor change:**

```python
self.deployer = deployer or SSHDeployer()  # was: ServiceDeployer()
self.infrastructure_provisioner = infrastructure_provisioner or InfrastructureProvisioner(deployer=self.deployer)
```

**`refresh_infrastructure()` (line 283-365)** — currently:

```python
# Lines 321, 340-351: imports CoolifyClient, calls list_applications(), matches by name
from fabrik.drivers.coolify import CoolifyClient
coolify = CoolifyClient()
apps = coolify.list_applications()
candidate_names = {spec_name, f"fabrik-{spec_name}"}
match = next((a for a in apps if a.get("name") in candidate_names), None)
ctx.coolify_uuid = match.get("uuid")
```

Replace with:

```python
# Try exact name first, then fabrik- prefix fallback
existing = self.deployer.find_existing(spec_name)
if not existing:
    existing = self.deployer.find_existing(f"fabrik-{spec_name}")
if not existing:
    raise ProvisioningError(
        f"No compose app found at /opt/{spec_name}/ or /opt/fabrik-{spec_name}/",
        resource_type="infrastructure",
    )
ctx.coolify_uuid = existing["name"]  # stores app name, not UUID
```

**Remove** `_maybe_register_coolify_alias()` method (line 367-384) and both call sites (line 134, line 363) — stable container names from compose `container_name:`, no alias watcher needed.

### Step 4: Modify `src/fabrik/orchestrator/infrastructure.py`

Add `deployer` parameter to `InfrastructureProvisioner.__init__()`:

```python
def __init__(self, deployer=None):
    self._deployer = deployer

@property
def deployer(self):
    if self._deployer is None:
        from fabrik.orchestrator.deployer_ssh import SSHDeployer
        self._deployer = SSHDeployer()
    return self._deployer
```

**GlitchTip registrar** (line ~446):

```python
# WAS:
coolify = CoolifyClient()
coolify.bulk_update_env_vars(ctx.coolify_uuid, {"SENTRY_DSN": dsn, "GLITCHTIP_DSN": dsn})
coolify.deploy(ctx.coolify_uuid, force=True)

# NOW:
self.deployer.inject_env(ctx, {"SENTRY_DSN": dsn, "GLITCHTIP_DSN": dsn})
# inject_env already does docker compose up -d, which replaces the coolify.deploy() call
```

**Redis registrar** (line ~574):

```python
# WAS:
coolify = CoolifyClient()
coolify.bulk_update_env_vars(ctx.coolify_uuid, {"REDIS_URL": redis_url})

# NOW:
self.deployer.inject_env(ctx, {"REDIS_URL": redis_url})
```

**GlitchTip DSN verification** (line ~455) — keep calling `verify_dsn_injection()` (updated in Step 8), just remove the `coolify_app_uuid` kwarg:

```python
# WAS:
if not verify_dsn_injection(name, dsn, max_wait=240, coolify_app_uuid=ctx.coolify_uuid):

# NOW:
if not verify_dsn_injection(name, dsn, max_wait=240):
```

### Step 5: Modify `src/fabrik/orchestrator/rollback.py`

**Constructor**: add deployer reference (same lazy pattern as infrastructure.py):

```python
def __init__(self, coolify_client=None, dns_client=None, deployer=None):
    self._coolify_client = coolify_client
    self._dns_client = dns_client
    self._deployer = deployer  # NEW
```

Add `_rollback_compose(resource)`:

```python
def _rollback_compose(self, resource: ResourceRecord) -> None:
    from fabrik.orchestrator.deployer_ssh import SSHDeployer
    deployer = self._deployer or SSHDeployer()
    name = resource.resource_id
    deployer.delete(name)  # validates name internally, runs docker compose down + rm -rf
```

Update `_rollback_resource()` dispatch (line ~137):

```python
if resource.resource_type == "compose":
    self._rollback_compose(resource)
elif resource.resource_type == "coolify":
    self._rollback_coolify(resource)  # keep for legacy state files
```

### Step 6: Modify `src/fabrik/orchestrator/destroyer.py`

Add `_destroy_compose()` as a module-level function (matches existing pattern — `_destroy_coolify` is module-level, not a method):

```python
def _destroy_compose(name: str, dry_run: bool) -> ActionResult:
    """Destroy a compose-deployed app via SSH."""
    from fabrik.drivers.ssh import ssh as _ssh

    try:
        if dry_run:
            return ActionResult("compose", "dry_run", detail=f"app {name}")

        # Validate name (shell injection prevention)
        import re
        if not re.match(r'^[a-z0-9][a-z0-9-]{0,62}$', name):
            return ActionResult("compose", "error", error=f"invalid app name: {name!r}")

        # Check directory exists
        try:
            _ssh(f"test -d /opt/{name}", timeout=10)
        except RuntimeError:
            return ActionResult("compose", "not_found", detail=f"app {name}")

        # Stop containers + remove volumes
        _ssh(f"cd /opt/{name} && sudo docker compose down -v", timeout=60)
        # Remove app directory
        _ssh(f"sudo rm -rf /opt/{name}", timeout=30)
        # Prune dangling images
        _ssh("sudo docker image prune -f", timeout=30)

        return ActionResult("compose", "removed", detail=f"app {name}")
    except Exception as e:  # noqa: BLE001
        return ActionResult("compose", "error", error=repr(e))
```

Update `destroy_deployment()` (line 598):

```python
# WAS:
report.actions.append(_destroy_coolify(name, dry_run))

# NOW:
report.actions.append(_destroy_compose(name, dry_run))
```

Update `destroy_from_state()` (line 759) — **state file dispatch issue**: The state file's `registrars_applied` is filtered by `_REGISTRAR_ORDER` (line 402 of `__init__.py`), which excludes "compose". So the state file does NOT track the deployment type. The destroy function must infer it:

```python
# At line 759 (Phase 2: app destruction):
# Try compose first (new SSH-deployed apps), fall back to Coolify (legacy)
compose_result = _destroy_compose(spec.id, dry_run)
if compose_result.status == "not_found":
    # Legacy Coolify app — try Coolify API
    compose_result = _destroy_coolify_legacy(spec.id, dry_run)
report.actions.append(compose_result)
```

Keep `_destroy_coolify` renamed to `_destroy_coolify_legacy` — called only as fallback when no compose directory exists at `/opt/{name}/` (pre-migration deployments).

**Note on state file tracking**: The `ctx.add_resource("compose", name)` call in the deployer adds a resource record, but `_persist_state()` filters resources by `_REGISTRAR_ORDER` before writing to state. Since "compose" is not a registrar, it won't appear in the state file. This is acceptable because:
1. The deploy type can be inferred at destroy time (check `/opt/{name}/compose.yaml` exists)
2. Adding "compose" to `_REGISTRAR_ORDER` would conflate deployment with registration
3. The fallback chain (compose → Coolify legacy) handles both cases gracefully

### Step 7: Modify `src/fabrik/cli.py` — redeploy command + top-level imports

**Top-level import fix** (CRITICAL — without this, the CLI won't load at all):

```python
# REMOVE (line 16 — deploy_to_coolify is used by the 'deploy' command at line 567, also broken):
from fabrik.deploy import deploy_to_coolify
# REMOVE (line 19 — used by 'status' at line 641 and 'logs' at line 692, also broken):
from fabrik.drivers.coolify import CoolifyClient
```

These commands (`deploy`, `status`, `logs`) are broken and out of scope (listed in "Known Broken" section), but their top-level imports block the entire CLI module from loading. Convert them to lazy imports inside each command function so that only the broken commands fail, not the whole CLI.

**`--refresh-infra` path** (line 1151-1180): calls `orch.refresh_infrastructure()` which we already updated in Step 3. No additional changes needed here except removing the stale lazy import:

```python
# REMOVE (line 1149):
from fabrik.drivers.coolify import CoolifyClient
```

**Standard redeploy path** (line 1186-1207): replace Coolify API call with SSH-based:

```python
# WAS:
coolify = CoolifyClient()
apps = coolify.list_applications()
target = next((a for a in apps if ...), None)
result = coolify.deploy(target["uuid"], force=force)

# NOW:
from fabrik.drivers.ssh import ssh as _ssh
from fabrik.orchestrator.deployer_ssh import SSHDeployer

deployer = SSHDeployer()
existing = deployer.find_existing(app)
if not existing:
    click.echo(f"✗ App '{app}' not found at /opt/{app}/compose.yaml", err=True)
    raise SystemExit(1)

# Determine source type by checking for .git directory
try:
    _ssh(f"test -d /opt/{app}/.git", timeout=10)
    is_git = True
except RuntimeError:
    is_git = False

if is_git:
    _ssh(f"cd /opt/{app} && sudo git pull", timeout=60)
    build_flags = " --no-cache" if force else ""
    _ssh(f"cd /opt/{app} && sudo docker compose build{build_flags}", timeout=300)
    _ssh(f"cd /opt/{app} && sudo docker compose up -d", timeout=120)
else:
    recreate_flags = " --force-recreate" if force else ""
    _ssh(f"cd /opt/{app} && sudo docker compose up -d{recreate_flags}", timeout=120)
```

**Important**: git-sourced apps pull from their configured remote (typically GitHub) when `git pull` runs. The Lesson 36 rule still applies: code must be pushed to the remote before `fabrik redeploy`. However, since Coolify is gone, the deployer no longer *requires* GitHub access — if the git remote is configured as a local path, `git pull` works locally. The standard workflow remains `commit → push → redeploy`.

### Step 8: Modify `src/fabrik/drivers/glitchtip.py` — `verify_dsn_injection()`

The function already uses `docker inspect` (Lesson 31 was previously applied). Changes needed:

1. **Remove `coolify_app_uuid` parameter** — no longer needed for container matching. With stable `container_name:` in compose, the container is found by exact name match, not by Coolify UUID prefix search.
2. **Simplify container lookup**: replace the `grep -E '^{project_name}(-|$)|-{coolify_app_uuid}-'` pattern with direct `sudo docker inspect {project_name}` — the container name IS the project name (from `container_name: {{ spec.id }}` in compose).
3. **Update caller** in infrastructure.py (line ~455): remove `coolify_app_uuid=ctx.coolify_uuid` kwarg.

Note: For apps with `-backend` suffix (chrome-extension template uses `container_name: {{ spec.id }}-backend`), the caller must pass the full container name, not just the spec id. This is already handled — the caller passes `name` which is `spec["name"]`, and the compose template uses `{{ spec.id }}` which equals `spec["name"]`.

### Step 9: Update `src/fabrik/orchestrator/context.py` — docstring only

```python
coolify_uuid: str | None = None
# Docstring change: "Stores app name (compose deploy) or Coolify UUID (legacy).
# Despite the name, this field now holds the compose app name (== directory name
# under /opt/) for SSH-deployed services. Field name preserved for minimal churn
# across 20+ files that reference it."
```

### Step 9b: Update `src/fabrik/orchestrator/exceptions.py` — `DeployError` docstring

The class docstring says "Coolify deployment failed" and the constructor has `coolify_error` param. Update:

```python
class DeployError(DeploymentError):
    """Deployment failed."""

    def __init__(self, message: str, detail: str | None = None):
        super().__init__(message, step="deploying")
        self.detail = detail
```

Note: `coolify_error` → `detail` is a rename. Check all callers — grep shows only `deployer.py` (being archived) passes `coolify_error=` kwarg. No test references.

### Step 10: Update `src/fabrik/compose_linter.py` — reverse container_name rule

The linter currently **rejects** `container_name` (line 68-73):

```python
# Rule 2.1: Reject container_name
if "container_name" in svc_config:
    errors.append(
        f"Service '{svc_name}': 'container_name' is forbidden "
        "(breaks Coolify naming/scaling)"
    )
```

This conflicts with all 10 compose templates (which all emit `container_name: {{ spec.id }}`) and the scaffold's `_write_canonical_compose()` (which emits `container_name: {name}`). Now that Coolify is gone, `container_name` is **required** for stable naming.

**Change**: reverse the rule — **require** `container_name`, don't reject it:

```python
# Rule 2.1: Require container_name for stable Docker naming
if "container_name" not in svc_config:
    warnings.append(
        f"Service '{svc_name}': missing 'container_name' "
        "(required for stable docker exec/inspect targeting)"
    )
```

Also update the class docstring from "Validates docker-compose YAML for Coolify compatibility" to "Validates docker-compose YAML for Fabrik deployment".

### NOT Modified

- All 9 registrar drivers (postgres.py, gatus.py, authelia.py, backrest.py, etc.) — they call the orchestrator/deployer, not Coolify directly
- Template renderer (`template_renderer.py`) — produces compose content, deployer consumes it. Already emits `container_name: {{ spec.id }}`
- Spec loader — `SourceType.LOCAL` already exists; only change is adding `path` field to `Source` model (Step 1b)
- Validator — unchanged interface
- Verifier — already Coolify-agnostic (probes HTTPS + health directly)
- DNS driver (Cloudflare) — unchanged
- SSH driver primitives (`ssh()`, `scp_to_vps()`) — consumed as-is
- `state.py` — semantics shift (stores app name instead of UUID), no code change

### Known Broken — Out of Scope (separate Phase 11-2 ticket)

These CLI commands also import `CoolifyClient` and are broken now that Coolify is gone. They are **not** part of this deployer replacement — they need their own migration:

- `fabrik status` (cli.py:641) — queries `coolify.list_applications()` to show app status
- `fabrik logs` (cli.py:692) — queries Coolify to find container for log streaming
- `fabrik reconcile-all` (cli.py:1319-1331) — queries all Coolify apps for fleet reconciliation
- `fabrik registry --sync` (cli.py:1389) — syncs registry with Coolify app list
- `health_app.py:17` — health check endpoint queries CoolifyClient
- `deploy.py:6` — standalone deploy script uses CoolifyClient
- `provisioner.py:195` — old provisioner uses CoolifyClient
- `portability.py:236` — export/import uses CoolifyClient
- `drivers/compose_updater.py:66` — compose updater uses CoolifyClient
- `cli.py:19` — top-level import (converted to lazy in Step 7 so CLI loads, but commands still broken)
- `cli.py:16` — top-level `from fabrik.deploy import deploy_to_coolify` (converted to lazy in Step 7)
- `drivers/__init__.py:12` — re-exports CoolifyClient; breaks `from fabrik.drivers import CoolifyClient`

---

## Implementation Order

| Step | File(s) | Action | Est. Lines |
|------|---------|--------|-----------|
| 1 | `deployer_ssh.py` | Create new file | ~300 |
| 1b | `spec_loader.py` | Add `path` field to `Source` model | ~1 |
| 2 | `deployer.py` → `deployer_coolify.py` | `git mv` | 0 |
| 3 | `__init__.py` | Swap import, wire deployer, update `refresh_infrastructure()`, remove alias watcher | ~40 changed |
| 4 | `infrastructure.py` | Add deployer param, replace 2 Coolify calls + DSN verification | ~30 changed |
| 5 | `rollback.py` | Add `_rollback_compose`, update dispatch | ~20 added |
| 6 | `destroyer.py` | Add `_destroy_compose`, update 2 call sites, rename `_destroy_coolify` | ~40 changed |
| 7 | `cli.py` | Convert 2 top-level Coolify imports to lazy + update redeploy command | ~35 changed |
| 8 | `drivers/glitchtip.py` | Simplify `verify_dsn_injection()` container lookup | ~15 changed |
| 9 | `context.py` | Docstring update | ~3 changed |
| 9b | `exceptions.py` | Rename `DeployError.coolify_error` → `detail`, update docstring | ~4 changed |
| 10 | `compose_linter.py` | Reverse `container_name` rule (reject → require) | ~8 changed |
| 11 | Tests | New tests for SSH deployer, update mocks | ~150 |

---

## `bulk_update_env_vars` — Complete Migration Map

The old deployer had 4 call sites for `coolify.bulk_update_env_vars()`. All 4 must be accounted for:

| Location | Old Behavior | New Behavior |
|----------|-------------|-------------|
| `deployer.py:451` (git pre-deploy env push) | Push env vars to Coolify app before initial build | `SSHDeployer.deploy()` writes `.env` via `_write_env_file()` + scp before `docker compose build` |
| `deployer.py:813` (update existing app) | Bulk update env vars on existing Coolify app | `SSHDeployer.deploy()` detects existing, writes updated `.env` via `_write_env_file()` |
| `infrastructure.py:446` (GlitchTip registrar) | Inject `SENTRY_DSN` + `GLITCHTIP_DSN` | `self.deployer.inject_env(ctx, {"SENTRY_DSN": dsn, "GLITCHTIP_DSN": dsn})` |
| `infrastructure.py:574` (Redis registrar) | Inject `REDIS_URL` | `self.deployer.inject_env(ctx, {"REDIS_URL": redis_url})` |

The first two are handled internally by `SSHDeployer.deploy()` — they don't need separate `inject_env` calls because the `.env` file is written as part of the deploy flow. The last two are post-deploy registrar injections handled by `inject_env()`.

---

## Full SaaS Deployment Flow (post-implementation)

`fabrik apply specs/services/my-saas.yaml` with `needs_database + needs_cache + has_search_feature + is_admin_dashboard + exposes_metrics`:

1. **Validate** — SpecValidator checks YAML structure, shape flags
2. **Secrets** — SecretsManager resolves from .env + env vars + generates (32-char `[a-zA-Z0-9]` per 35-security-auth.md)
3. **DNS** — Cloudflare creates `my-saas.vps1.ocoron.com` A record
4. **Deploy** — SSHDeployer:
   - `TemplateRenderer.render()` produces compose.yaml with:
     - `container_name: my-saas`
     - `platform: linux/amd64`
     - `deploy.resources.limits.memory: 512M`
     - `restart: unless-stopped`
     - `networks: [coolify]` (external)
     - Traefik labels: `websecure`, `letsencrypt`, `authelia-forward@docker,gzip@docker` (admin)
     - `HEALTHCHECK` with `start_period: 20s`
     - No `ports:` section
   - `.env` with `DATABASE_URL=postgresql+asyncpg://...@postgres-main:5432/...`, `REDIS_URL=redis://redis-main:6379/N`, `SERVICE_INTERNAL_SECRET_KEY=...`
   - `_validate_compose()` checks all constraints
   - SSH: `sudo mkdir -p /opt/my-saas/`, scp files via tmp+mv, `sudo docker compose up -d`
   - `ctx.add_resource("compose", "my-saas", name="my-saas")`
5. **Registrars** (shape-driven, post-deploy, order from `_REGISTRAR_ORDER`):
   - **postgres** → `CREATE DATABASE` + `CREATE USER` on `postgres-main`
   - **redis** → allocate index, `deployer.inject_env(ctx, {"REDIS_URL": ...})` → container restarts with new env
   - **gatus** → write endpoint config monitoring `https://my-saas.vps1.ocoron.com/health`, restart gatus
   - **backrest** → add backup plan for DB + volumes
   - **glitchtip** → create project + DSN, `deployer.inject_env(ctx, {"SENTRY_DSN": dsn, "GLITCHTIP_DSN": dsn})` → verify via `docker inspect my-saas` env check (Lesson 31)
   - **grafana** → deployment annotation
   - **authelia** → add access rule for `my-saas.vps1.ocoron.com` (admin dashboard), `docker restart authelia`
   - **meilisearch** → create search index
   - **prometheus** → add scrape target for `/metrics`
6. **Verify** — HTTPS health check (`/health` returns 200 with real dep checks), Authelia middleware check, API bypass check

---

## Error Handling

| Scenario | Behavior |
|----------|----------|
| SSH command fails | `RuntimeError` from `ssh()` → caught, wrapped in `DeployError` |
| Compose validation fails | `DeployError` with list of constraint violations |
| Container fails to start | Check `docker compose ps` output → `DeployError` with container logs |
| `inject_env` fails | `DeployError` → registrar logs warning, non-fatal (except glitchtip DSN verify) |
| Name validation fails | `DeployError("Invalid app name: must match ^[a-z0-9][a-z0-9-]{0,62}$")` |
| Rollback triggered | `_rollback_compose`: validates name, `sudo docker compose down` + `sudo rm -rf /opt/{name}/` |
| VPS unreachable | SSH timeout → `subprocess.TimeoutExpired` → `DeployError` |
| `find_existing` on non-existent app | `ssh("test -f ...")` raises `RuntimeError` → caught, returns `None` |
| Unknown `SourceType` | Explicit check: `if source.type not in (TEMPLATE, GIT, DOCKER, LOCAL): raise DeployError(...)` — no silent fallback (Lesson 32) |

---

## Verification Plan

1. `fabrik apply specs/services/image-broker.yaml --dry-run` — should show SSH commands, not "Calling Coolify API"
2. `pytest tests/orchestrator/ -x` — all tests pass with mocked SSH
3. `fabrik redeploy image-broker --dry-run` — shows `cd /opt/image-broker && sudo docker compose up -d`
4. `fabrik destroy specs/services/fabrik-e2e-test.yaml --dry-run` — shows `sudo docker compose down -v`
5. Live smoke test: `fabrik redeploy image-broker` on VPS — container restarts, health check passes, Gatus stays green
6. Registrar smoke: `fabrik apply` a test spec with `needs_cache: true` → verify `REDIS_URL` injected via `docker inspect <name>` env check (NOT `docker exec`)
7. Per Lesson 64: live-state verification on VPS after implementation — `docker ps`, `docker inspect`, Gatus dashboard

---

## Cross-Reference: Mobile Deployment Design

The mobile deployment design (`docs/superpowers/specs/2026-05-28-mobile-deployment-design.md`) layers on top of this SSH deployer plan. It introduces a `has_vps_backend` shape flag that conditionally skips deployer/DNS/verify steps. Implementers should be aware of:

1. **Orchestrator deploy flow**: The `deploy()` method's calls to DNS, deployer, and verify (Step 3) should be structured as a clear block that can be wrapped with a `has_vps_backend` check. The mobile design adds this check after the SSH deployer is implemented.
2. **GlitchTip registrar**: Step 4's `inject_env()` + `verify_dsn_injection()` calls will gain a second code path for `has_vps_backend: false` — create GlitchTip project + output DSN to state/stdout instead of injecting into a container. Keep the registrar method structured so this fork is easy to add.
3. **CLI redeploy**: Step 7's redeploy command will gain a guard that loads the spec YAML to check `has_vps_backend` before calling `find_existing()`.

These are additive changes — the SSH deployer implementation does not need to implement them, but should not make them harder to add.

---

## Post-Implementation Cleanup (Phase 14 items, separate tickets)

These are NOT part of this implementation but noted for tracking:

- Remove `coolify-alias-watcher` systemd service (no longer needed — stable container names)
- Update `scripts/vps_apply_limits.sh` — remove alias re-application, keep resource limits
- Clean up UUID-named Docker volumes from old Coolify apps
- Update docs: AGENTS.md, PORTS.md, CONFIGURATION.md, CHANGELOG.md
- Update 30-ops.md rule pack: remove Coolify references, update redeploy flow, change `container_name` from banned to required
