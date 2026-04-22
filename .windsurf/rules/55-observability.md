---
activation: glob
globs: ["**/health*", "**/logging*", "**/middleware/**", "**/monitoring/**"]
description: Observability discipline — structured logs, correlation IDs, health/readiness, alert thresholds
trigger: glob
---

# Observability Rules

Apply when working on logging, health endpoints, monitoring, alerting, or middleware instrumentation. Skip for pure UI layout or business logic without I/O.

## Pre-Scaffolded Logging

Every Fabrik project ships with a ready-to-use logging module. DO NOT create custom logging setups.

**Python projects** (`python-api`, `file-worker`, `chrome-extension` backend):

```python
from {package}.logger import get_logger
logger = get_logger(__name__)
logger.info("event_name", key="value")
```

- Module: `src/{package}/logger.py` — structlog, JSON output, service name from `SERVICE_NAME` env var
- Middleware: `src/{package}/middleware.py` — X-Request-ID correlation (python-api only)
- Config: always JSON. No human-readable mode.

**Node projects** (`node-api`, `file-api`):

```javascript
const logger = require('./logger');
logger.info({ event: 'event_name', key: 'value' });
```

- Module: `src/logger.js` — pino, JSON output, service name from `SERVICE_NAME` env var

**Next.js projects** (`saas-skeleton`):

```typescript
import logger from '@/lib/logger';
logger.info({ event: 'event_name', key: 'value' });
```

- Module: `lib/logger.ts` — pino, JSON output

**No scaffold logging:** `mobile-app`, `desktop-app`, `wordpress`, `docusaurus`, `static-site` — set up per ticket using the rules below.

**Chrome extension frontend:** Use `chrome.storage.local` buffer pattern per the Chrome Extension Telemetry section below. Do not use pino directly in service workers.

## Structured Logging

- All production logs must be **JSON-formatted**. Human-readable colorised output is for local development only.
- Use `structlog` for Python and `pino` for Node.js/Next.js. No other logging libraries.
- `print()` in Python and `console.log()` / `console.error()` in JavaScript are **banned** in production code paths. Route all output through the structured logger.
- Log event names must be machine-parseable `snake_case` (e.g. `user_authenticated`, `db_connection_failed`). No conversational prose or dynamic string interpolation in event names.
- Exceptions must be logged with stack traces as a dedicated JSON attribute (`exc_info=True` in Python), never as raw multi-line text.

## Required Log Fields

Every JSON log entry must include these core fields:

| Field | Type | Source |
|-------|------|--------|
| `timestamp` | ISO 8601 UTC string | Logger core |
| `level` | Lowercase string (`debug`, `info`, `warn`, `error`, `fatal`) | Logger core |
| `event` | `snake_case` action description | Developer |
| `service` | Originating service name | Env var `SERVICE_NAME` |
| `correlation_id` | UUID v4 linking to request lifecycle | Middleware |
| `duration_ms` | Float (optional) | Application logic |

## Request Correlation

- Every ingress request must carry an `X-Request-ID` header (UUID v4). If the client does not provide one, the first receiving service generates it.
- The correlation ID must propagate across all service boundaries via the `X-Request-ID` header and be attached to every log entry for that request.
- In FastAPI: use `contextvars` + ASGI middleware to bind the ID to `structlog` context. Never use `threading.local()` in async code.
- In Next.js: extract in `middleware.ts`, propagate via `AsyncLocalStorage` or explicit child logger passing.
- Return the `X-Request-ID` in the response headers so clients can reference it in bug reports.

## PII & Secret Redaction

- PII (emails, SSNs, credit card numbers), auth tokens, passwords, and API keys must be redacted **at the application edge** before log emission.
- Implement redaction via regex filters in the logger configuration (`structlog` processors in Python, `pino` redact paths in Node.js).
- Never rely on downstream log processors (Promtail, Logstash) for redaction — unredacted data may persist in transport buffers.
- Replace matched values with static tokens (e.g. `[REDACTED_EMAIL]`, `[REDACTED_TOKEN]`).

## Loki Label Discipline

- **Never** use high-cardinality values as Loki stream labels. `request_id`, `user_id`, `session_id`, `client_ip` must remain inside the JSON payload only.
- Valid labels: `service`, `environment`, `level`. These have bounded cardinality.
- High-cardinality labels cause index bloat and OOM crashes on constrained VPS.

## Health Endpoint Semantics

- Every service exposes `/health` that actively verifies critical dependencies (e.g. `SELECT 1` against PostgreSQL) before returning 200.
- A `/health` that returns 200 without checking dependencies creates "zombie" containers — Traefik routes traffic to broken services.
- Docker Compose `HEALTHCHECK` must include `start_period` (15–20s) to allow framework boot and DB migrations before Coolify kills the container.

```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:${PORT:-8000}/health"]
  interval: 30s
  timeout: 5s
  retries: 3
  start_period: 20s
```

## Alert Thresholds (SLO-Lite)

Alert only on **user-facing symptoms** using the RED method (Rate, Errors, Duration). Infrastructure metrics are for dashboards, not pager alerts.

| Metric | Source | Threshold | Action |
|--------|--------|-----------|--------|
| External availability | Gatus | 3 consecutive failures / 60s | Push notification |
| HTTP 5xx error rate | Grafana Loki (LogQL) | > 5% of requests over 5 min | Push notification |
| P95 latency | Grafana Loki (LogQL) | > 2.0s sustained over 5 min | Push notification |
| CPU / RAM spikes | Netdata | N/A — do not page | Dashboard only |

## Synthetic Monitoring

- Gatus provides black-box availability checks completely decoupled from the internal logging pipeline. If Loki is down, Gatus still detects application failure.

## Chrome Extension Telemetry

- MV3 service workers are ephemeral (terminated after ~30s idle). Do not hold logs in memory waiting for a batch window.
- Buffer logs to `chrome.storage.local` or `chrome.storage.session`, then flush asynchronously to the backend via `navigator.sendBeacon()` or non-blocking `fetch` when network permits.
- Handle `chrome.runtime.lastError` during I/O to prevent unhandled promise rejections from crashing the worker.

---

## Banned Patterns

| Pattern | Use Instead |
|---------|-------------|
| `print()` in Python production code | `structlog` logger |
| `console.log()` / `console.error()` in JS production code | `pino` logger |
| High-cardinality Loki labels (`request_id`, `user_id`, `ip`) | Embed in JSON payload, query via LogQL parsers |
| Superficial `/health` returning static 200 | Verify DB connection + critical deps before 200 |
| `HEALTHCHECK` without `start_period` | Add `start_period: 20s` for boot tolerance |
| Alerting on CPU/RAM spikes | Alert on RED symptoms only (errors, latency) |
| Logging PII/secrets then relying on downstream redaction | Redact at application edge before emission |
| Synchronous `console.log` for heavy objects in Node.js | `pino` with worker thread transport |

---

## Done When

- [ ] All services emit JSON-structured logs via `structlog` (Python) or `pino` (Node.js).
- [ ] No `print()` or `console.log()` in production code paths.
- [ ] `X-Request-ID` middleware present in FastAPI (using `contextvars`) — correlation ID in every log entry.
- [ ] PII/secret redaction configured in logger (regex filters for emails, tokens, passwords).
- [ ] `/health` endpoint verifies actual dependencies (DB, Redis) before returning 200.
- [ ] Docker Compose `HEALTHCHECK` includes `start_period`.
- [ ] Loki labels limited to low-cardinality values (`service`, `environment`, `level`).
- [ ] Alert rules target RED symptoms only — no infrastructure cause-based paging.
- [ ] Gatus configured for external synthetic monitoring of all public endpoints.
