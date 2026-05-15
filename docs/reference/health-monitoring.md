# Health Monitoring

**Version:** 1.3.0
**Last Updated:** 2026-04-28 (monitoring migrated to Coolify 2026-04-17; verifier-key alignment fix [B23, Lesson 32] noted in `docs/reference/orchestrator.md:47` — this doc covers Fabrik's own `/health` endpoint and the observability stack, NOT the deploy verifier)

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

**Compose file:** ~~`/opt/monitoring/compose.yaml` (standalone)~~ → all 7 services migrated to Coolify management 2026-04-17. Manage start/stop via the Coolify dashboard.
**Local source:** `specs/infrastructure/monitoring-stack.yaml` + `configs/` in Fabrik (mirror; production state lives in Coolify)

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

## Registrar Coverage Audit (T2-02, 2026-05-15)

The HTTP `/health` endpoint covered by this doc verifies a SINGLE service's runtime liveness. T2-02 adds a complementary primitive that verifies the SETUP — every shape-applicable registrar (Postgres DB, Redis slot, Gatus endpoint, Backrest plan, GlitchTip project, Authelia rule, Meilisearch index, Prometheus scrape job) is actually live on the VPS:

```bash
fabrik audit-registrars                       # pivot table across all specs
fabrik audit-registrars --spec <path>         # one spec
fabrik audit-registrars --spec <path> --json  # machine-readable
```

Plus a postcondition gate that pairs cleanly with the HTTP `/health` check:

```bash
fabrik verify <domain> --spec deploy          # HTTP /health + SSL + Coolify status
fabrik verify <domain> --spec registrars      # registrar coverage
```

Run both in sequence after `fabrik apply` to verify the full Stage 3/Stage 4 chain — service is up AND every auto-registration the orchestrator was supposed to perform actually landed. Exit codes propagate so shell `&&` chaining works:

```bash
fabrik apply <spec> \
  && fabrik verify <domain> --spec deploy \
  && fabrik verify <domain> --spec registrars
```

Implementation: `src/fabrik/audit.py` mirrors each driver's transport (SSH for 7 of 9 registrars; `requests` for glitchtip; `n/a` for grafana which has no driftable state). State file persisted at `.fabrik/state/<spec.id>.json` (T2-01) feeds future state-aware destroy (T4-01).

## Weekly Authelia Drift Cron (T2-03 G-G4, 2026-05-15)

Companion to the on-demand `audit-registrars` check above — `scripts/audit_authelia_gates.py` runs every Monday 06:00 via WSL cron, hits the live Traefik API over SSH, and verifies every admin-dashboard router still has the `authelia-forward@docker` middleware attached (the policy-vs-enforcement drift class from Lesson 32 / the 2026-04-18 GlitchTip incident).

```cron
0 6 * * 1 PYTHONPATH=/opt/fabrik/src /opt/fabrik/.venv/bin/python /opt/fabrik/scripts/audit_authelia_gates.py >> /var/log/fabrik-audit.log 2>&1
```

Log lives at `/var/log/fabrik-audit.log` (writable by `ozgur:ozgur`). Each run appends a block ending in `SUMMARY: N OK, M GAP, K MISSING`. Manual smoke: `PYTHONPATH=/opt/fabrik/src /opt/fabrik/.venv/bin/python /opt/fabrik/scripts/audit_authelia_gates.py`.

**Known follow-up:** the script's expected inventory predates T2-08 Part A's decision to gate `errors.vps1.ocoron.com`. Every Monday's run prints `1 GAP` against `errors`; cosmetic (exit 0) until the inventory is updated.

## Stable Docker DNS Aliases (T2-04 G-J3, 2026-05-15)

Adjacent to the audit/verify primitives above — the alias-watcher keeps friendly Docker DNS names alive for Gatus monitors and inter-service URLs that target Coolify Application containers. Coolify renames Application containers on every redeploy (`<24-char-uuid>-<10-digit-timestamp>`); without the watcher, `gatus:8080 → meilisearch:7700` resolution would break after each redeploy of the meilisearch container.

The watcher service (`/opt/coolify-alias-watcher/`) is event-driven (listens to `docker events --filter event=start`), reads the prefix→alias map from `/opt/coolify-alias-watcher/aliases.json`, and re-applies aliases within ~1s. WSL mirror in repo at `ops/coolify-alias-watcher/`.

**Orchestrator integration:** new services that need stable DNS opt in by setting `coolify.alias: <name>` in their spec's `CoolifyConfig` block. `fabrik apply` calls `src/fabrik/orchestrator/coolify_alias.py::add_alias(ctx.coolify_uuid, alias)` after the Coolify create-app step, which writes atomically to aliases.json and restarts the watcher. Non-fatal: alias-watcher failure logs a warning but never aborts deploy.

**Why this matters for monitoring:** Gatus endpoint configs at `/opt/monitoring/configs/gatus/apps/<svc>.yaml` reference services by friendly name (`http://meilisearch:7700/health`). If a Coolify redeploy renames the underlying container and the watcher hasn't re-attached the alias yet, that Gatus check would 503 until the next watcher cycle (sub-second window). Across all 4 baseline aliases (meilisearch, gotenberg, browserless, glitchtip-web) this has been silent-correct since 2026-04-16.

---

## See also

- `src/fabrik/health_app.py` - FastAPI health endpoint implementation
- `src/fabrik/audit.py` - per-registrar audit module (T2-02)
- `scripts/audit_authelia_gates.py` - weekly Authelia-Traefik drift audit (T2-03 G-G4)
- `src/fabrik/orchestrator/coolify_alias.py` - Coolify alias-watcher write side (T2-04 G-J3)
- `ops/coolify-alias-watcher/` - WSL mirror of the VPS-side `/opt/coolify-alias-watcher/`
- `docs/reference/drivers.md` - Coolify + DNS driver configuration
- `.env.example` - authoritative environment variable reference
