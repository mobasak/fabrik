# Health Monitoring

**Version:** 1.0.0
**Last Updated:** 2026-03-08

---

## Purpose

Provide a dependency-aware health check surface that:

- returns non-200 when upstream dependencies are degraded (for Coolify healthchecks and external uptime monitors)
- exposes which dependency failed (Coolify vs DNS manager) in a stable JSON shape
- supports command-line probing for automation (CI, cron, or ad-hoc debugging)

---

## Usage

### FastAPI `/health` endpoint

**Location:** `src/fabrik/health_app.py`

Run the minimal health app locally:

```bash
uvicorn fabrik.health_app:app --reload --port 8000
```

Probe the endpoint:

```bash
curl -fsS http://localhost:8000/health | python -m json.tool
```

**Response body shape** (always JSON):

```json
{
  "service": "fabrik",
  "status": "ok" | "degraded",
  "checks": {
    "coolify": {
      "status": "healthy" | "unhealthy",
      "details": { "status": "...", "...": "..." },
      "error": "..."
    },
    "dns": {
      "status": "healthy" | "unhealthy",
      "details": { "status": "...", "...": "..." },
      "error": "..."
    }
  }
}
```

Notes:

- `checks.coolify` and `checks.dns` always include a top-level `status`.
- `details` is present when the underlying dependency returns a structured payload.
- `error` is present when the dependency check raises an exception.

**HTTP status codes**:

- `200 OK` when **all** dependency checks report `status=healthy`
- `503 Service Unavailable` when **any** dependency check reports `status=unhealthy`

**Dependency checks**:

- Coolify: `CoolifyClient.health()` via `check_coolify()`
- DNS manager: `DNSClient.health()` via `check_dns()`

Each dependency payload is normalized by `_normalize_status()` to map common upstream statuses
(`ok`, `healthy`, `pass`, `success`) into `healthy`.

---

### `scripts/health_checker.py`

`scripts/health_checker.py` is a CLI utility for probing health and (optionally) database reachability.

Basic usage (HTTP health probe):

```bash
python scripts/health_checker.py --health-url http://localhost:8000/health
```

Database reachability probe (TCP connect to host:port):

```bash
# Uses DATABASE_URL if set, otherwise DB_HOST/DB_PORT
python scripts/health_checker.py --check-db
```

Run both checks:

```bash
python scripts/health_checker.py --health-url http://localhost:8000/health --check-db
```

**Exit codes**:

- `0` - all requested checks passed
- `1` - unexpected error (uncaught exception)
- `2` - configuration error (required inputs missing)
- `3` - HTTP health check failed (non-200, invalid JSON, or degraded status)
- `4` - database host/port unreachable (TCP connect failed)

---

## Configuration

`src/fabrik/health_app.py` depends on the Coolify and DNS client configuration (see their driver docs).

`scripts/health_checker.py` uses the following environment variables for database targeting:

- `DATABASE_URL` - preferred; parsed for host and port (e.g. `postgresql://user:pass@localhost:5432/dbname`)
- `DB_HOST` - used when `DATABASE_URL` is not set
- `DB_PORT` - used when `DATABASE_URL` is not set
- `DB_NAME` - optional (not required for TCP reachability)
- `DB_USER` - optional (not required for TCP reachability)
- `DB_PASSWORD` - optional (not required for TCP reachability)

---

## See also

- `src/fabrik/health_app.py` - FastAPI health endpoint implementation
- `docs/reference/drivers.md` - Coolify + DNS driver configuration
- `.env.example` - authoritative environment variable reference
