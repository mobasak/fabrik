# Verification Framework

**Last Updated:** 2026-01-04

A 3-lane verification system for ensuring deployment safety despite AI model limitations (~65% accuracy on terminal tasks per Terminal-Bench).

---

## Overview

The verification framework provides:
- **Static guarantees** (Lane A): Types, linting, security scanning
- **Dynamic guarantees** (Lane B): Postcondition checks after deployment
- **Runtime fail-closed** (Lane C): Auto-rollback on failure

## Quick Start

```bash
# Run static verification (before commit)
./scripts/verify.sh

# Run dynamic verification (after deploy)
fabrik verify api.example.com

# Run with specific spec
fabrik verify api.example.com --spec dns
```

---

## Lane A: Static Verification

Run before every commit via `scripts/verify.sh`:

| Check | Tool | Purpose |
|-------|------|---------|
| Linting | ruff | Code style, common bugs |
| Type checking | mypy | Type safety |
| Secret scanning | secret-scanner.py | No hardcoded secrets |
| Unit tests | pytest | Function correctness |
| Contract tests | pytest tests/contracts/ | Postcondition logic |

```bash
./scripts/verify.sh
```

---

## Lane B: Dynamic Verification

Run after deployment via `fabrik verify`:

### Postcondition Specs

Located in `specs/verification/`:

| Spec | Purpose |
|------|---------|
| `deploy.yaml` | Service deployment checks |
| `dns.yaml` | DNS record checks |

### Available Checks

| Check Type | Description |
|------------|-------------|
| `http_get` | HTTP endpoint responds with expected status |
| `ssl_verify` | SSL certificate valid with min days remaining |
| `dns_lookup` | Domain resolves to expected IP |

### Example Spec

```yaml
# specs/verification/deploy.yaml
operation: deploy

postconditions:
  health_check:
    check: http_get
    url: "https://${DOMAIN}/health"
    expect: 200
    timeout: 30
    retries: 3
    backoff: exponential

  ssl_valid:
    check: ssl_verify
    domain: "${DOMAIN}"
    min_days_remaining: 7

rollback:
  default: auto  # or manual
```

### CLI Usage

```bash
# Basic verification
fabrik verify api.example.com

# Use DNS spec
fabrik verify api.example.com --spec dns

# Disable auto-rollback
fabrik verify api.example.com --no-rollback

# Custom app name
fabrik verify api.example.com --app-name my-api
```

---

## Lane C: Runtime Fail-Closed

### Auto-Rollback

When postconditions fail and `rollback.default: auto`:
1. Log failure details
2. Trigger Coolify rollback (if available)
3. Notify via webhook (if configured)

### Manual Override

For irreversible operations, set in spec:

```yaml
rollback:
  default: manual
  manual_required:
    - database_migration
    - breaking_schema_change
```

---

## Decorator Usage

Apply postcondition checks to functions:

```python
from fabrik.verify import verify_postconditions

@verify_postconditions(spec_name="deploy", auto_rollback=True)
def deploy_service(spec):
    # Deploy logic here
    return {"domain": spec.domain, "app_name": spec.id}
```

---

## Adding New Checks

1. Add check type to `src/fabrik/verify.py`:

```python
def check_custom(self, name: str) -> PostconditionResult:
    config = self._get_check_config(name)
    # Implementation
    return PostconditionResult(name, CheckResult.PASS, "message")
```

2. Register in `run_all()`:

```python
elif check_type == "custom_check":
    self.results.append(self.check_custom(name))
```

3. Add to spec:

```yaml
postconditions:
  my_check:
    check: custom_check
    # config options
```

---

## Multi-Model Review (Optional)

For high-risk changes, use multi-model review:

```bash
# Implementation review
droid exec -m gpt-5.2 "Review changes in src/fabrik/..."

# Security review
droid exec -m claude-sonnet-4-5-20250929 "Red-team review..."

# Test generation
droid exec -m gemini-3-flash-preview "Generate edge case tests..."
```

This is **optional** and manual - not enforced in CI.

---

## Consensus Decision

This framework was designed through multi-model consensus (GPT-5.2, Claude Sonnet, Gemini Flash):

**Agreed:**
- Skip mutation testing, formal proofs, heavy fuzzing (overkill for internal automation)
- Default to auto-rollback with manual override option
- Use retry with exponential backoff for transient failures

**Rationale:** Fast feedback loops > exhaustive proofs for internal tooling.

---

## See Also

- [DEPLOYMENT.md](../DEPLOYMENT.md) - Deployment process
- [TROUBLESHOOTING.md](../TROUBLESHOOTING.md) - Common issues
- [PROJECT_WORKFLOW.md](../guides/PROJECT_WORKFLOW.md) - Project workflow
