# Deployment Orchestrator

**Last Updated:** 2026-04-22

The orchestrator module (`src/fabrik/orchestrator/`) provides unified end-to-end deployment automation. The pipeline is **shape-driven**: the `shape.*` flags on a spec decide which registrars run (Postgres DB, Gatus endpoint, Backrest backup plan, GlitchTip project, Grafana annotation, Authelia rule, MeiliSearch index).

---

## Overview

```text
fabrik apply --dry-run spec.yaml   # Simulate deployment
fabrik apply spec.yaml              # Full deployment (legacy path)
fabrik apply --use-orchestrator spec.yaml  # Use new orchestrator
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
| `__init__.py` | 320 | `DeploymentOrchestrator` main class — drives the state machine; calls each stage; wires `RollbackManager` on error |
| `states.py` | 54 | `DeploymentState` enum + `can_transition()` (illegal transitions raise `InvalidStateTransitionError`) |
| `context.py` | 59 | `DeploymentContext`, `ResourceRecord` — shared state across stages; every rollback-able resource calls `ctx.add_resource(...)` |
| `exceptions.py` | 59 | Typed exceptions (`ValidationError`, `ProvisioningError`, `DeployError`, `VerificationError`, `RollbackError`, `InvalidStateTransitionError`) |
| `secrets.py` | 137 | `SecretsManager` — precedence: `-s` flags → project `.env` → `/opt/fabrik/.env` → env vars; CSPRNG generate (`secrets.choice()`, 32-char alphanumeric) |
| `validator.py` | 318 | `SpecValidator.validate(spec)`, `validate_domain_security()`, `compute_spec_hash()` — pydantic + SSRF check + idempotency hash |
| `deployer.py` | 278 | `ServiceDeployer.deploy(ctx)`, `find_existing(name)` — idempotent Coolify mutations (PATCH existing by name or POST new `dockercompose` app + `deploy(force=True)`), waits up to 90s for container Up |
| `infrastructure.py` | 510 | `InfrastructureProvisioner.provision(ctx)`, `resolve_applicability(shape)`, `format_resolved_summary()` — shape-driven dispatcher invoked between Deploy and Verify; runs postgres → gatus → backrest → glitchtip+DSN → grafana annotation → authelia rules (+ `^/api/` bypass) → meilisearch |
| `verifier.py` | 372 | `DeploymentVerifier.verify(ctx)` — HTTP 200 on `/health`, DNS resolves, SSL valid, `SENTRY_DSN` in container env via `docker inspect` (see Lesson 31) |
| `rollback.py` | 382 | `RollbackManager.rollback(ctx)` — LIFO reverse-order cleanup. DB drops are **logged for operator, not auto-executed**; config mutations and ephemeral resources (annotations, projects, DNS records) are auto-cleaned |
| `content_publisher.py` | 613 | **Not deploy** — SEO → TCO → Image → WordPress content pipeline; reuses the context/state pattern |

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

# Full deployment with orchestrator (opt-in today; default after Phase 4 completion)
fabrik apply --use-orchestrator specs/my-app.yaml

# Legacy path (no orchestrator) — default today
fabrik apply specs/my-app.yaml

# Project-based deploy (reads /opt/<name>/project.yaml, routes by type)
fabrik deploy --project /opt/my-app
```

`--dry-run` always uses the orchestrator (see `cli.py:284`); otherwise the flag `--use-orchestrator` is required until Phase 4 flips the default.

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

coolify: {project: default, server: localhost}

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

**Secret Loading Precedence:**
1. Command-line `-s` flags (highest)
2. Project `.env` file at `/opt/{spec_id}/.env`
3. Environment variables (lowest)

**How It Works:**
1. `fabrik scaffold` auto-detects secrets from `.env.example` and adds them to the spec's `from_env` field
2. During deployment, the orchestrator reads from the project's `.env` file before checking system environment variables
3. Only secrets listed in `spec.secrets.from_env` are loaded from the `.env` file

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
# Run all orchestrator tests (144 tests as of 2026-04-22)
pytest tests/orchestrator/ -q

# Run specific test file
pytest tests/orchestrator/test_validator.py -q
```

**Test files (9):** `test_deployer.py`, `test_e2e_rollback.py`, `test_infrastructure.py`, `test_integration.py`, `test_rollback.py`, `test_secrets.py`, `test_states.py`, `test_validator.py`, `test_verifier.py`.

**Related:** `tests/drivers/` has 331 additional tests across the 12 driver modules used by `InfrastructureProvisioner`.

## End-to-End Validation

See `docs/DEPLOYMENT.md` §9.6 for the canonical **maximal-shape E2E test** procedure — scaffold → deploy → verify 9 registrars → idempotency → teardown. Expected wall time ~63s (measured 2026-04-22).

---

## Related

- [DEPLOYMENT.md](../DEPLOYMENT.md) — canonical deploy reference (read this first)
- [Drivers Reference](drivers.md)
- [CLI Reference](fabrik-cli-reference.md)
- [Templates](templates.md)
- [Roadmap](roadmap.md)
