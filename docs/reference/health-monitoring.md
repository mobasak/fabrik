# Health Monitoring

**Version:** 1.2.0
**Last Updated:** 2026-04-14

---

## Monitoring Infrastructure Overview

### Stack Components

| Tool | Role | What it does |
|------|------|-------------|
| **Netdata** | Real-time metrics dashboard | Built-in, zero config. Shows CPU/RAM/disk/network/Docker stats instantly. Best for "what's happening right now on my server." |
| **Prometheus** | Metrics collector & storage | Scrapes metrics from apps/services and stores them as time-series data. Doesn't visualize — just collects and stores. |
| **Grafana** | Visualization layer | Connects to Prometheus (and other sources including Netdata) and builds custom dashboards, alerts, and graphs. Best for "show me trends over the last 30 days." |
| **Loki** | Log aggregator | Collects logs from all containers/services into one searchable place. Prometheus but for logs instead of metrics. |
| **Promtail** | Log shipper | Reads Docker container logs and sends them to Loki. |
| **Gatus** | Uptime monitoring | External availability checks, status page, alerting. |

### Current Stack (Single VPS)

The full observability stack is deployed and operational. Netdata provides real-time metrics; Prometheus + Grafana handle alerting, dashboards, and long-term trend analysis; Loki + Promtail aggregate container logs.

### Deployed Services (Verified 2026-04-14)

| Service | URL | Status |
|---------|-----|--------|
| Gatus | status.vps1.ocoron.com | ✅ Running |
| Netdata | netdata.vps1.ocoron.com | ✅ Running |
| Grafana | monitor.vps1.ocoron.com | ✅ Running |
| Prometheus | (internal :9090) | ✅ Running |
| Alertmanager | (internal :9093) | ✅ Running |
| Loki | (internal :3100) | ✅ Running |
| Promtail | (internal) | ✅ Running |
| cAdvisor | (internal :8080) | ✅ Running |
| node-exporter | (internal :9100) | ✅ Running |

**Compose file:** `/opt/monitoring/compose.yaml` on VPS (7 services)
**Local source:** `specs/infrastructure/monitoring-stack.yaml` + `configs/` in Fabrik

### Notification Chain

```
Prometheus (rules) → Alertmanager → Telegram (native telegram_configs)
```

> **Why not Apprise?** Apprise's stateless `/notify` endpoint expects `{body,title,type}`
> JSON and returns HTTP 400 on Alertmanager's native webhook schema. Alertmanager →
> Apprise is not a valid chain. Gatus → Apprise still works because Gatus posts the
> Apprise-compatible shape.
>
> **ARO Brain (planned):** LLM-based alert triage. When deployed, add as a primary
> receiver routed before `telegram`, with `telegram` as the fallback.

### Prometheus Alert Rules (9 total)

Source of truth: `configs/prometheus/rules/alerts.yml`

| # | Alert | Severity | Threshold | For |
|---|-------|----------|-----------|-----|
| 1 | ContainerDown | critical | not seen >2min | 2m |
| 2 | ContainerHighCPU | warning | >80% | 5m |
| 3 | ContainerHighMemory | warning | >85% limit | 5m |
| 4 | ContainerOOMKilled | critical | any OOM in 5m | 0m |
| 5 | ContainerRestarting | critical | >3 in 15m | 0m |
| 6 | HostHighCPU | warning | >85% | 10m |
| 7 | HostHighMemory | critical | >90% | 5m |
| 8 | HostDiskFull | critical | >85% | 5m |
| 9 | ServiceUnhealthy | critical | target down | 2m |

All applicable rules include `value` annotations for ARO Brain quantitative reasoning.

**Key config files (local mirror in Fabrik `configs/`):**
- `configs/alertmanager/alertmanager.yml` — routing, receivers, inhibit rules
- `configs/prometheus/prometheus.yml` — scrape targets, alerting config
- `configs/prometheus/rules/alerts.yml` — alert rules

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
