# Deployment Orchestrator

**Last Updated:** 2026-04-22

> **⚠️ Partially pre-migration vintage.** Lines mentioning `ServiceDeployer` /
> "Coolify mutations" / "Coolify status" describe the pre-2026-05 deploy path
> (`deployer_coolify.py`, which defined `ServiceDeployer`, was removed at 9c02e8c86).
> Today `deployer_ssh.py` (SSH + Docker Compose) is the active deployer; the
> orchestrator's overall structure (shape-driven registrars, verifier, rollback)
> is unchanged. See [docs/operations/deployment.md](../../operations/deployment.md)
> for the current flow.

The orchestrator module (`src/fabrik/orchestrator/`) provides unified end-to-end deployment automation. The pipeline is **shape-driven**: the `shape.*` flags on a spec decide which registrars run — 10 in order: postgres, redis, gatus, backrest, glitchtip, grafana, authelia, meilisearch, prometheus, watchdog (`infrastructure.py:136-147`).

---

## Overview

```text
fabrik apply --dry-run spec.yaml   # Simulate deployment (orchestrator, no mutations)
fabrik apply spec.yaml              # Full deployment — the orchestrator is the only path
```

---

## Architecture

```text
┌─────────────────────────────────────────────────────────────┐
│                  DeploymentOrchestrator                      │
├─────────────────────────────────────────────────────────────┤
│  PENDING → VALIDATING → PROVISIONING → DEPLOYING            │
│                                          ↓                   │
│                         VERIFYING → COMPLETE                 │
│                              ↓                               │
│                    ROLLING_BACK → ROLLED_BACK / FAILED       │
└─────────────────────────────────────────────────────────────┘
```

---

## Components

| File | Lines | Purpose |
|------|------:|---------|
| `__init__.py` | 513 | `DeploymentOrchestrator` main class — drives the state machine; calls each stage; wires `RollbackManager` on error |
| `states.py` | 54 | `DeploymentState` enum + `can_transition()` (illegal transitions raise `InvalidStateTransitionError`) |
| `context.py` | 83 | `DeploymentContext`, `ResourceRecord` — shared state across stages; every rollback-able resource calls `ctx.add_resource(...)` |
| `exceptions.py` | 64 | Typed exceptions (`ValidationError`, `ProvisioningError`, `DeployError`, `VerificationError`, `RollbackError`, `InvalidStateTransitionError`) |
| `secrets.py` | 137 | `SecretsManager` — `get()` precedence: env vars → project `.env` → CSPRNG generate (`secrets.choice()`, 32-char alphanumeric). (NB the orchestrator `from_env` path reads `.env` before env vars — the two paths differ.) |
| `validator.py` | 343 | `SpecValidator.validate(spec)`, `validate_domain_security()`, `compute_spec_hash()` — pydantic + SSRF check + idempotency hash |
| `../env_file.py` | — | The `.env` codec (`format_env`, `parse_env`, `EnvTemplate`) — compose's dotenv grammar for every Fabrik `.env` writer and reader (see Secrets Management) |
| `deployer_ssh.py` | — | **`SSHDeployer.deploy(ctx)` (current)** — idempotent `docker compose up -d` over SSH; validates compose for template/docker/git sources; waits for container Up |
| `infrastructure.py` | 1002 | `InfrastructureProvisioner.provision(ctx)`, `resolve_applicability(shape)`, `format_resolved_summary()` — shape-driven dispatcher invoked between Deploy and Verify; runs postgres (+`DATABASE_URL` inject) → redis (+`REDIS_URL`) → gatus → backrest → glitchtip+DSN → grafana annotation → authelia rules (+ `^/api/` bypass) → meilisearch → prometheus → watchdog; a `depends.postgres`/`depends.postgres_seed`/`depends.redis` beside a false or absent flag is named in the skip reason and logged at WARNING (`depends_contradiction`, W-81524f52) |
| `verifier.py` | 542 | `DeploymentVerifier.verify(ctx)` — HTTP 200 on the path declared in `spec["health"]["path"]` (see Lesson 32 — was previously hardcoded to `/health` via a silent fallback that masked all non-`/health` deploys as 404s; fixed B23, 2026-04-28), DNS resolves, Authelia-middleware + api-bypass checks. Workers (no HTTP) skip the HTTP probe — the compose healthcheck is the proof (B35). DSN verification lives in the glitchtip registrar, not here; `check_ssl()` exists as a standalone helper, not called by `verify()`. |
| `rollback.py` | 452 | `RollbackManager.rollback(ctx)` — LIFO reverse-order cleanup. DB drops are **logged for operator, not auto-executed**; config mutations and ephemeral resources (annotations, projects, DNS records) are auto-cleaned |
| `destroyer.py` | 813 | `destroy_from_state()` + per-registrar `_destroy_*` teardown (reverse order) — the `fabrik destroy` path |
| `vultr_drill.py` / `vultr_provision.py` / `vultr_state.py` | — | The `fabrik vultr` DR-drill + permanent-spoke provisioning subsystem (see `docs/reference/fabrik-vultr.md`) |
| `gpu_rent.py` + `gpu_*.py` (5 modules) | — | On-demand GPU rental across RunPod/Modal/Vast (see `docs/operations/gpu-rent.md`) |
| `sysadmin_tokens.py` | — | Spoke sysadmin token pool |

---

## Usage

### Programmatic

```python
from pathlib import Path
from fabrik.orchestrator import DeploymentOrchestrator, DeploymentState

orchestrator = DeploymentOrchestrator()
ctx = orchestrator.deploy(Path("spec.yaml"), dry_run=False)

if ctx.state == DeploymentState.COMPLETE:
    print(f"Deployed: {ctx.deployed_url}")
elif ctx.state == DeploymentState.ROLLED_BACK:
    print(f"Failed and rolled back: {ctx.error}")
else:
    print(f"Failed: {ctx.error}")
```

### CLI

```bash
# Dry run (simulates all steps — always uses orchestrator)
fabrik apply --dry-run specs/my-app.yaml

# Full deployment — the orchestrator pipeline is the only path
fabrik apply specs/my-app.yaml

# Project-based deploy (reads /opt/<name>/project.yaml, routes by type)
cd /opt/my-app && fabrik apply
```

The orchestrator pipeline is the only path for every `fabrik apply` invocation (dry-run included); the former `--legacy` and `--use-orchestrator` flags were removed in the Coolify retirement.

---

## Spec Format

Canonical pydantic model: `src/fabrik/spec_loader.py::Spec` (`model_config = {"extra": "forbid"}`).

```yaml
id: my-api
kind: service
template: python-api
domain: api.example.com

shape:                       # drives InfrastructureProvisioner dispatch
  kind: service              # service | worker | wordpress | static
  is_public: true            # → Gatus endpoint
  is_admin_dashboard: false  # → Authelia forward-auth rule
  has_bearer_api: false      # → Authelia ^/api/ bypass
  has_persistent_data: true  # → Backrest backup plan
  needs_database: true       # → Postgres database
  has_search_feature: false  # → MeiliSearch index

source:
  type: docker
  image: my/image:tag
  image_port: 8000


env:
  PORT: "8000"
  LOG_LEVEL: "info"

secrets:
  required: [DATABASE_URL]
  from_env: [API_KEY]
  from_file:
    GOOGLE_CREDENTIALS: /path/to/credentials.json

health:                      # not `healthcheck:` — see Health model
  path: /health
  disabled: false            # set true for scratch/distroless images (Lesson 30)

backup:
  enabled: true
  frequency: daily
  retention: 30
```

---

## Security Features

- **Domain validation**: Blocks localhost, private IPs, internal TLDs (SSRF prevention)
- **DNS resolution for SSRF**: `is_private_ip()` resolves hostnames via `socket.getaddrinfo()` before checking private ranges — catches DNS-rebinding attacks (e.g., `internal.corp` → `10.0.0.1`)
- **Path traversal prevention**: Template paths are validated with `.resolve().relative_to()` to prevent directory escape (e.g., `../../etc/passwd`)
- **HTTPS enforcement**: Health checks only allow `https://` URLs
- **CSPRNG secrets**: Auto-generated secrets use `secrets` module (32 char alphanumeric)
- **Rollback safety**: Only resources created in current run are rolled back

## Secrets Management

The orchestrator automatically loads secrets from the project's `.env` file during deployment.

**Secret Loading Precedence** (orchestrator `from_env` path):
1. Command-line `-s` flags (highest)
2. Project `.env` file at `/opt/{spec_id}/.env`
3. Environment variables

(NB `SecretsManager.get()` itself checks env vars FIRST, then `.env`, then CSPRNG-generates — the two code paths order env vs `.env` differently; `secrets.py:87-97`.)

**How It Works:**
1. `fabrik scaffold` auto-detects secrets from `.env.example` and adds them to the spec's `from_env` field
2. During deployment, the orchestrator reads from the project's `.env` file before checking system environment variables
3. Only secrets listed in `spec.secrets.from_env` are loaded from the `.env` file
4. A `from_file` secret is the file's text minus ONE trailing newline (`echo secret > file`)

**The `.env` format** (`src/fabrik/env_file.py`, W-2ae286e2). The hub `from_env` reader, the
deployed `.env`/`.env.owner` writer and reader, and `.env.example` all use one codec built to docker
compose's dotenv grammar. A spec `env:` value keeps its `$` as a compose interpolation
(`LOG_LEVEL=${LOG_LEVEL:-INFO}`); in every other value — a secret, a registrar value — a `$` is
literal. A value is written bare unless it holds a space, `#`, a quote, `\`, a TAB, a line break or a
literal `$`; a literal holding `$` is single-quoted (`API_KEY='a$b'`) when it holds no `'`, `\` or line
break, and every other quoted value is double-quoted with `\$`, `\\`, `\"`, `\n`, `\r`, `\t` escapes.
The reader follows compose: single quotes are literal, a
` #` ends an unquoted value, text after a closing quote is ignored, and an unterminated quote or a
second quoted word after the closing quote aborts the read (compose refuses the same file); the error
names the key and line, never the value, and a malformed hub `.env` stops the deploy. A hand-written template is written back unchanged. The
deployed `.env` and `.env.owner` are read in one ssh call and parsed apart.

**Example:**
```yaml
# spec.yaml
secrets:
  from_env:
    - API_KEY
    - DATABASE_PASSWORD
```

```bash
# /opt/my-api/.env
API_KEY=your_actual_key
DATABASE_PASSWORD=your_actual_password

# Deploy - secrets auto-loaded
fabrik apply spec.yaml
```

**Benefits:**
- No manual environment variable setting needed
- Secrets are isolated per project
- Works seamlessly across WSL dev and VPS Docker environments
- Easy to override with `-s` flags when needed

---

## State Machine

| From State | Valid Transitions |
|------------|-------------------|
| PENDING | VALIDATING |
| VALIDATING | PROVISIONING, FAILED |
| PROVISIONING | DEPLOYING, FAILED, ROLLING_BACK |
| DEPLOYING | VERIFYING, FAILED, ROLLING_BACK |
| VERIFYING | COMPLETE, FAILED, ROLLING_BACK |
| ROLLING_BACK | ROLLED_BACK, FAILED |
| COMPLETE | (terminal) |
| FAILED | (terminal) |
| ROLLED_BACK | (terminal) |

Invalid transitions raise `InvalidStateTransitionError`.

---

## Tests

```bash
# Run all orchestrator tests (~411 tests across 22 files, 2026-07-19)
pytest tests/orchestrator/ -q

# Run specific test file
pytest tests/orchestrator/test_validator.py -q
```

**Test files (22):** the original 9 (`test_deployer.py`, `test_e2e_rollback.py`, `test_infrastructure.py`, `test_integration.py`, `test_rollback.py`, `test_secrets.py`, `test_states.py`, `test_validator.py`, `test_verifier.py`) plus `test_deployer_ssh.py`, `test_destroyer.py`, `test_refresh_infrastructure.py`, `test_spoke_dsn_mesh.py`, `test_sysadmin_tokens.py`, `test_template_defaults.py`, `test_plan1_defects.py`, and the `test_gpu_*` / `test_vultr_*` sets.

**Related:** `tests/drivers/` has 331 additional tests across the 12 driver modules used by `InfrastructureProvisioner`.

## End-to-End Validation

See `docs/DEPLOYMENT_ARCHITECTURE.md` §9.6 for the canonical **maximal-shape E2E test** procedure — scaffold → deploy → verify 9 registrars → idempotency → teardown. Expected wall time ~63s (measured 2026-04-22).

---

## Related

- [DEPLOYMENT_ARCHITECTURE.md](../../DEPLOYMENT_ARCHITECTURE.md) — canonical deploy reference (read this first)
- [Drivers Reference](drivers.md)
- [CLI Reference](../fabrik-cli-reference.md)
- [Templates](templates.md)
