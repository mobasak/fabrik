# Deployment Orchestrator

**Last Updated:** 2026-02-22

The orchestrator module (`src/fabrik/orchestrator/`) provides unified end-to-end deployment automation.

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

| File | Purpose |
|------|---------|
| `__init__.py` | `DeploymentOrchestrator` main class |
| `states.py` | State machine with valid transitions |
| `context.py` | `DeploymentContext` shared state |
| `exceptions.py` | Typed exceptions (`ValidationError`, `DeployError`, etc.) |
| `secrets.py` | `SecretsManager` (env → .env → generate) |
| `validator.py` | `SpecValidator` with SSRF prevention |
| `deployer.py` | `ServiceDeployer` (idempotent Coolify deploy) |
| `verifier.py` | `DeploymentVerifier` (health check with retries) |
| `rollback.py` | `RollbackManager` (LIFO resource cleanup) |

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
# Dry run (simulates all steps)
fabrik apply --dry-run specs/my-app.yaml

# Full deployment with orchestrator
fabrik apply --use-orchestrator specs/my-app.yaml
```

---

## Spec Format

```yaml
name: my-api
template: python-api
domain: api.example.com
server: vps1

env:
  PORT: "8000"
  LOG_LEVEL: "info"

secrets:
  required:
    - DATABASE_URL
  from_env:
    - API_KEY
  from_file:
    GOOGLE_CREDENTIALS: /path/to/credentials.json

healthcheck:
  path: /health
  timeout: 30
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
# Run all orchestrator tests
pytest tests/orchestrator/ -q

# Run specific test file
pytest tests/orchestrator/test_validator.py -q
```

**Test coverage:** 73 tests covering states, secrets, validation, deployment, verification, rollback, and integration.

---

## Related

- [Roadmap](roadmap.md)
- [Drivers Reference](drivers.md)
- [CLI Reference](fabrik-cli-reference.md)
