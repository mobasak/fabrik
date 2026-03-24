# Health Checker Workflow

**Last Updated:** 2026-03-24
**Status:** PRODUCTION
**Script:** `scripts/health_checker.py`

## Overview

Validates service health by probing HTTP `/health` endpoints and testing database TCP reachability. Designed for cron jobs, CI pipelines, and manual spot-checks.

---

## Exit Codes

| Code | Constant | Meaning |
|------|----------|---------|
| 0 | `EXIT_OK` | All checks passed |
| 1 | `EXIT_UNEXPECTED` | Unexpected error (exception) |
| 2 | `EXIT_CONFIG` | Missing configuration (no checks requested or invalid env vars) |
| 3 | `EXIT_HTTP_UNHEALTHY` | HTTP health check failed |
| 4 | `EXIT_DB_UNREACHABLE` | Database TCP connection failed |

---

## CLI Usage

```bash
# Check HTTP health endpoint
python scripts/health_checker.py --health-url http://localhost:8000/health

# Check database reachability (uses DATABASE_URL or DB_HOST/DB_PORT)
python scripts/health_checker.py --check-db

# Both checks with custom timeout
python scripts/health_checker.py --health-url http://localhost:8000/health --check-db --timeout 10

# No arguments shows config error
python scripts/health_checker.py
# Output: No checks requested. Use --health-url and/or --check-db.
# Exit code: 2
```

---

## HTTP Health Check

### Expected Response

```json
{
  "status": "ok"
}
```

### Validation Rules

1. HTTP status must be `200`
2. Response must be valid JSON
3. JSON must have `status` field equal to `"ok"` (case-insensitive)

### Failure Cases

| Output | Meaning |
|--------|---------|
| `http: request_failed: <error>` | Network/connection error |
| `http: status_code=<N> body=...` | Non-200 HTTP status |
| `http: invalid_json` | Response not valid JSON |
| `http: status=<value>` | Status field not "ok" |
| `http: unexpected_json_shape` | Response not a dict |

---

## Database Reachability Check

### Environment Variables

Uses one of:
- `DATABASE_URL` — Full connection string (e.g., `postgresql://user:pass@host:5432/db`)
- `DB_HOST` + `DB_PORT` — Separate host and port

### Check Method

Simple TCP socket connection — validates network reachability, not authentication.

### Output

```
db: reachable: localhost:5432      # Success
db: unreachable: db:5432 (...)     # Failure with error
db: missing/invalid DATABASE_URL   # Config error
```

---

## Cron Integration

Add to crontab for periodic monitoring:

```bash
# Check every 5 minutes
*/5 * * * * /opt/fabrik/.venv/bin/python /opt/fabrik/scripts/health_checker.py --health-url http://localhost:8000/health --check-db >> /var/log/health_check.log 2>&1
```

---

## CI/CD Integration

```yaml
# GitHub Actions example
- name: Health Check
  run: |
    python scripts/health_checker.py \
      --health-url http://localhost:8000/health \
      --check-db \
      --timeout 30
```

---

## Docker Compose Integration

Use in compose.yaml health checks:

```yaml
services:
  api:
    healthcheck:
      test: ["CMD", "python", "/app/scripts/health_checker.py", "--health-url", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 10s
```

---

## Environment Loading

The script automatically loads `/opt/fabrik/.env` if:
1. `FABRIK_ROOT` environment variable is set
2. The `.env` file exists

This supports both local development (with `.env`) and containerized deployments (env vars injected directly).

---

## Examples

### Local Development

```bash
# Start service
uvicorn app:app --port 8000 &

# Check health
python scripts/health_checker.py --health-url http://localhost:8000/health
# Output: http: ok
# Exit: 0
```

### Production Check

```bash
python scripts/health_checker.py \
  --health-url https://captcha.vps1.ocoron.com/health \
  --timeout 5

# Output: http: ok
# Exit: 0
```

### Combined Check

```bash
export DATABASE_URL="postgresql://user:pass@localhost:5432/mydb"
python scripts/health_checker.py --health-url http://localhost:8000/health --check-db

# Output:
# http: ok
# db: reachable: localhost:5432
# Exit: 0
```

---

## Related Workflows

- [Final Gate Workflow](FINAL_GATE_WORKFLOW.md) — Runs health checks as part of enforcement
- [Dev Tracker Workflow](DEV_TRACKER_WORKFLOW.md) — Logs health check failures
