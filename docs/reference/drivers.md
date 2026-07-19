# Fabrik Drivers

**Last Updated:** 2026-04-22

> **⚠️ Pre-migration vintage.** The "CoolifyClient — primary deploy driver"
> section below describes the deploy path before the 2026-05 SSH+Compose
> migration. Today the primary deploy driver is `orchestrator/deployer_ssh.py`
> (SSH + Docker Compose, no Coolify API). `drivers/coolify.py` and
> `drivers/compose_updater.py` are retained as legacy for the few CLI
> commands (`fabrik status`, `fabrik logs`, `fabrik reconcile-all`) that
> still talk to the Coolify API for services that were never migrated.
> Other drivers in this document (postgres, redis, gatus, backrest,
> glitchtip, grafana, authelia, meilisearch, prometheus, cloudflare, dns,
> ssh, r2, supabase) are unchanged and current.

Fabrik drivers (`src/fabrik/drivers/`) are the **only place that talks to external APIs or the VPS**. Every deploy mutation goes through exactly one driver — no ad-hoc HTTP/SSH calls allowed in the orchestrator or CLI.

**Canonical catalog** (with shape gates and contract details) lives in `docs/DEPLOYMENT_ARCHITECTURE.md` §2.4. This file is the module reference with usage examples.

---

## All Drivers (27 modules, 2026-07-19)

| File | Lines | Used during deploy for | Shape gate |
|---|---:|---|---|
| `ssh.py` | 138 | `ssh(cmd, timeout, dry_run)`, `scp_to_vps()` — host alias `vps` (override via `FABRIK_VPS_SSH_HOST`) | always |
| `locks.py` | 165 | `run_locked(resource, script, timeout)`, `git_commit_config(path)` — VPS `flock -x -w` + whitelisted git commits | always |
| `coolify.py` | 934 | `CoolifyClient` — legacy Coolify v4 API client (Coolify decommissioned 2026-05-30; retained for `reconcile-all`/legacy paths only) | legacy |
| `dns.py` | 689 | `DNSClient` — site-provisioner service at `provision.vps1.ocoron.com`; domain registration, A/CNAME/TXT records, Cloudflare zone provisioning | always when `domain` set |
| `cloudflare.py` | 368 | `CloudflareClient` — direct Cloudflare API fallback when site-provisioner is down | fallback |
| `postgres.py` | 1380 | `create_database()`, `drop_database()` — per-service DB + role on `postgres-main` (registrar injects `DATABASE_URL` on first create); watchdog/subagent roles, allocations, analytics DB; SQL identifier validation; drops deferred to operator | `shape.needs_database` |
| `gatus.py` | 398 | `add_endpoint()`, `remove_endpoint()` — git-repo edit of `/opt/monitoring/configs/gatus/config.yaml` + commit via `git_commit_config()` | `shape.is_public` + `domain` |
| `backrest.py` | 408 | `add_backup_plan()`, `remove_backup_plan()` — Restic policy via Backrest API; atomic `.tmp` → `json.tool` validate → `mv` | `shape.has_persistent_data` |
| `glitchtip.py` | 501 | `create_project()`, `delete_project()`, `verify_dsn_injection()` — Sentry-compatible; **DSN verification via `docker inspect`** (Lesson 31) | `shape.kind in {service, worker, wordpress}` |
| `grafana.py` | 291 | `post_deployment_annotation()`, `delete_annotation()` — global annotations; non-fatal (decorative) | always (universal) |
| `authelia.py` | 592 | `add_access_rule()`, `remove_access_rule()` — `docker exec` into Authelia + `run_locked()`; supports `insert_before_twofactor=True` for `^/api/` bypass | `shape.is_admin_dashboard` + `domain` (+ bypass when `shape.has_bearer_api`) |
| `redis.py` | 293 | `acquire_db_index()`, `release_db_index()` — per-service Redis DB index on `redis-main` via `assignments.json`; registrar injects `REDIS_URL` | `shape.needs_cache` |
| `prometheus.py` | 521 | `add_scrape_target()`, `remove_scrape_target()` — scrape config for `/metrics` | `shape.exposes_metrics` + `domain` |
| `meilisearch.py` | 262 | `create_index()`, `delete_index()` — container-scoped `sh -c` evaluates `$MEILI_MASTER_KEY` inside container (no secret on SSH wire) | `shape.has_search_feature` |
| `compose_updater.py` | 451 | `update_compose_service()` — surgical YAML patching of Coolify's `docker_compose_raw` (used for env-var plumbing, label additions) | on demand |
| `preflight.py` | 312 | Readiness probes invoked before deploy (DNS resolves, Coolify reachable, required secrets present) | always |
| `supabase.py` | 437 | `SupabaseClient` — Auth + DB when `spec.infrastructure.database == supabase` | on demand |
| `r2.py` | 408 | `R2Client` — Cloudflare R2 (S3-compatible) when `spec.storage.type == r2` | on demand |
| ~~`wordpress.py`~~ | — | **Removed** — WP-CLI client extracted to `/opt/wpf/` (May 2026) | WordPress sites (legacy) |
| ~~`wordpress_api.py`~~ | — | **Removed** — WordPress REST client extracted to `/opt/wpf/` (May 2026) | WordPress content (legacy) |
| `image_broker.py` | 176 | `ImageBrokerClient` — stock image fetching (**not deploy** — content pipeline) | content |
| `seo.py` | 384 | `SEOClient` — keyword research (**not deploy** — content pipeline) | content |
| `tco.py` | 114 | `TCOClient` — content generation (**not deploy** — content pipeline) | content |
| `uptime_kuma.py` | 193 | `UptimeKumaClient` — **superseded by Gatus**; kept for old projects only | legacy |
| `modal_provider.py` | 731 | Modal serverless GPU provider (`fabrik gpu` auto/modal path) | GPU rental |
| `runpod.py` | 380 | `RunPodClient` — RunPod pods + serverless endpoints (rest.runpod.io / api.runpod.ai) | GPU rental |
| `vast_provider.py` | 825 | Vast.ai spot/interruptible + serverless GPU provider | GPU rental |
| `vultr.py` | 298 | Vultr provisioning for `fabrik vultr` (DR drills, disposable spokes) | provisioning |
| `watchdog.py` | 1284 | Watchdog sidecar registrar — config emission, `WATCHDOG_TRIGGER_SOURCES`, RO/RW DSNs | `watchdog.enabled` |

Total: 27 driver modules + `__init__.py`.

---

## Usage examples (most common)

### CoolifyClient — legacy deploy driver (decommissioned)

> **Legacy (Coolify decommissioned 2026-05-30).** `drivers/coolify.py` is retained on disk but non-functional. The primary deploy path is now `orchestrator/deployer_ssh.py` (`docker compose up -d` over SSH). The example below is historical.

```python
from fabrik.drivers.coolify import CoolifyClient

c = CoolifyClient()  # reads COOLIFY_API_URL, COOLIFY_API_TOKEN from env

# Discover
servers = c.list_servers()
projects = c.list_projects()
apps = c.list_applications()

# Create a dockercompose application (base64-encoded compose)
app = c.create_dockercompose_application(
    name="my-api",
    project_uuid=projects[0]["uuid"],
    server_uuid=servers[0]["uuid"],
    docker_compose_raw=compose_yaml,  # client base64-encodes internally
)

# Set env vars (Coolify v4 API: key/value; HTTP 409 if key exists → use PATCH)
c.bulk_update_env_vars(app["uuid"], {"SENTRY_DSN": dsn, "LOG_LEVEL": "info"})

# Deploy
c.deploy(app["uuid"], force=True)

# Lifecycle
c.stop_application(uuid); c.start_application(uuid); c.restart_application(uuid)
c.delete_application(uuid)
```

### DNSClient — all DNS/domain ops

```python
from fabrik.drivers.dns import DNSClient, add_dns_record

# Most common: add a subdomain under an existing zone
add_dns_record("ocoron.com", "myapp.vps1", "172.93.160.197")

# Full API via context manager
with DNSClient() as dns:
    dns.add_subdomain("ocoron.com", "api.vps1", "172.93.160.197")
    records = dns.get_records("ocoron.com")
    dns.check_availability("new-domain.com")
    dns.register_domain("new-domain.com", contact={...})
```

`DNSClient` routes through site-provisioner at `provision.vps1.ocoron.com`; falls back to `drivers/cloudflare.py` if the service is unreachable.

### GlitchTip — error tracking (shape-gated)

```python
from fabrik.drivers.glitchtip import create_project, verify_dsn_injection

result = create_project("my-api")  # {status: "created"|"exists", dsn: "http://..."}

# Inject DSN into Coolify app env, then verify container picks it up
# verify_dsn_injection uses `docker inspect` — works on scratch/distroless (Lesson 31)
ok = verify_dsn_injection("my-api", expected_dsn=result["dsn"], max_wait=60)
```

### Authelia — SSO/2FA forward-auth

```python
from fabrik.drivers.authelia import add_access_rule, remove_access_rule

# Admin dashboard: two_factor
add_access_rule(domain="dashboard.vps1.ocoron.com", policy="two_factor")

# Admin dashboard with a bearer-token API: add ^/api/ bypass FIRST
add_access_rule(
    domain="dashboard.vps1.ocoron.com",
    policy="bypass",
    resources=["^/api/"],
    insert_before_twofactor=True,   # critical: ordering matters (Lesson 25 §8.11)
)
add_access_rule(domain="dashboard.vps1.ocoron.com", policy="two_factor")
```

### Gatus — uptime monitoring

```python
from fabrik.drivers.gatus import add_endpoint, remove_endpoint

add_endpoint(
    project_name="my-api",
    domain="my-api.vps1.ocoron.com",   # bare hostname — no scheme/path
    health_path="/health",
    interval="60s",
)
```

Config edits auto-commit via `drivers/locks.py::git_commit_config()` (only `/opt/monitoring/configs/gatus` is whitelisted).

### Backrest — restic-based backups

```python
from fabrik.drivers.backrest import add_backup_plan, remove_backup_plan

add_backup_plan(
    plan_id="my-api-data",
    paths=["/opt/my-api/data"],
    schedule_cron="0 3 * * *",     # daily 03:00
)
```

Atomic write pattern: `.tmp` → `json.tool` validate → `mv`. Lock held for the full script via `run_locked("backrest-config", ...)`.

### MeiliSearch — search index

```python
from fabrik.drivers.meilisearch import create_index, delete_index

create_index("my_api_documents", primary_key="id")
```

Inside the container, the shell evaluates `$MEILI_MASTER_KEY` from env — secret never leaves the container.

### Grafana — deployment annotations (decorative, non-fatal)

```python
from fabrik.drivers.grafana import post_deployment_annotation

post_deployment_annotation(
    project_name="my-api",
    git_sha=spec_hash,
    extra_tags=["prod"],
)
```

Failure is logged but does not fail the deploy.

### Postgres — per-service DB

```python
from fabrik.drivers.postgres import create_database

create_database("my_api_prod", owner="postgres")
# SQL identifiers validated upstream; drop_database() is deferred to operator
```

### SSH & locks — the low-level primitives

```python
from fabrik.drivers.ssh import ssh, scp_to_vps
from fabrik.drivers.locks import run_locked, git_commit_config

# Fire-and-parse SSH
uptime = ssh("uptime").strip()
ssh("sudo systemctl restart foo", timeout=30)

# Whole-script locking (NOT per-SSH-call — that pattern is broken, see module docstring)
run_locked("authelia-config", """
    docker exec authelia-... cat /config/configuration.yml > /tmp/cfg.yml
    # edit /tmp/cfg.yml ...
    docker cp /tmp/cfg.yml authelia-...:/config/configuration.yml
    docker restart authelia-...
""", timeout=60)

# Git-commit whitelisted VPS configs
git_commit_config("/opt/monitoring/configs/gatus")
```

### Supabase & R2 — optional infra

Used only when `spec.infrastructure.database == supabase` or `spec.storage.type == r2`. See DEPLOYMENT_ARCHITECTURE.md §2.4 for shape-gate details.

---

## Environment variables

Canonical source: `/opt/fabrik/.env` (git-ignored; `.env.example` is tracked). Required for deploy:

| Driver | Variables |
|---|---|
| `coolify` | `COOLIFY_API_URL`, `COOLIFY_API_TOKEN` |
| `dns` | `SITE_PROVISIONER_URL` (defaults to `https://provision.vps1.ocoron.com`), `SITE_PROVISIONER_API_KEY` |
| `cloudflare` | `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`, `CLOUDFLARE_ZONE_ID_OCORON` |
| `glitchtip` | `GLITCHTIP_AUTH_TOKEN`, `GLITCHTIP_ORG_SLUG`, `GLITCHTIP_TEAM_SLUG`, `GLITCHTIP_ADMIN_EMAIL`, `GLITCHTIP_ADMIN_PASSWORD` |
| `grafana` | `GRAFANA_SERVICE_ACCOUNT_TOKEN` |
| `backrest` | `BACKREST_URL`, `BACKREST_AUTH` |
| `meilisearch` | `MEILI_MASTER_KEY` (read inside container, never on wire) |
| `supabase` | `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY` |
| `r2` | `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET`, `R2_PUBLIC_URL` |
| `ssh`, `locks` | `FABRIK_VPS_SSH_HOST` (default `vps`) |

Never commit `.env`. Never `source` a `.env` file — values can contain shell metacharacters (Lesson 25 §8.14); use `python-dotenv` in Python, `grep | cut` in shell.

---

## Tests

```bash
# All driver tests (377 tests as of 2026-07-19, across 17 driver test modules)
pytest tests/drivers/ -q

# One driver
pytest tests/drivers/test_glitchtip.py -q
```

Test files: `test_authelia.py`, `test_backrest.py`, `test_compose_updater.py`, `test_coolify.py`, `test_dns_client.py`, `test_gatus.py`, `test_gatus_aro_wake.py`, `test_glitchtip.py`, `test_grafana.py`, `test_locks.py`, `test_meilisearch.py`, `test_postgres.py`, `test_preflight.py`, `test_prometheus_aro_wake.py`, `test_ssh.py`, `test_vultr_client.py`, `test_watchdog_peer_map.py`.

---

## Live contract probes

Contract tests against live services — run before shipping driver changes. Also serve as living API documentation.

| Script | Tests |
|---|---|
| `scripts/probes/glitchtip_probe.sh` | Create project → fetch DSN → delete. Contract captured in `docs/reference/glitchtip-api.md`. |
| `scripts/probes/grafana_token_check.sh` | `/api/annotations` write + delete. Validates `GRAFANA_SERVICE_ACCOUNT_TOKEN` scope. |

---

## Related

- [DEPLOYMENT_ARCHITECTURE.md](../DEPLOYMENT_ARCHITECTURE.md) — canonical deploy reference with full driver catalog (§2.4) and shape gates
- [Orchestrator](orchestrator.md) — how drivers are invoked during a deploy
- [CLI Reference](fabrik-cli-reference.md)
- [Templates](templates.md)
- [glitchtip-api.md](glitchtip-api.md) — live-captured GlitchTip API contract
