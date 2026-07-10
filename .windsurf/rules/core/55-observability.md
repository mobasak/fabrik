---
activation: glob
globs: ["**/health*", "**/logging*", "**/logger*", "**/metrics*", "**/middleware/**", "**/monitoring/**", "**/glitchtip*", "**/sentry*"]
description: Observability discipline — structured logs, correlation IDs, health/readiness, metrics, alert thresholds, crash reporting
trigger: glob
---
<!-- CONSUMER: Coding agents (all) + Traycer (tech-plan step)
     GOAL: Structured logging, /health, /metrics, GlitchTip, alerts, per-scaffold observability matrix
     TRAYCER USAGE: Injects observability requirements per scaffold type into ticket ACs.
     AGENT USAGE: Follow the per-scaffold matrix. Use structlog (Python) or pino (Node). No print/console.log. -->

# Observability Rules

Apply when working on logging, health endpoints, metrics, monitoring, alerting, crash reporting, or middleware instrumentation. Skip for pure UI layout or business logic without I/O.

---

## Per-Scaffold Observability Matrix

Not every scaffold type gets every observability feature. This matrix is the source of truth:

| Scaffold | Structured logging | `/health` | `/metrics` | GlitchTip | Crash reporting | Gatus monitor |
|---|---|---|---|---|---|---|
| `python-api` | structlog (scaffolded) | Yes (scaffolded) | Yes (scaffolded) | Yes (scaffolded) | Server-side auto | Yes |
| `node-api` | pino (scaffolded) | Yes (scaffolded) | Yes (scaffolded) | Yes (scaffolded) | Server-side auto | Yes |
| `file-api` | pino (scaffolded) | Yes (scaffolded) | Yes (scaffolded) | Yes (scaffolded) | Server-side auto | Yes |
| `file-worker` | structlog (scaffolded) | Yes (scaffolded) | Yes (scaffolded) | Yes (scaffolded) | Server-side auto | Yes |
| `saas-skeleton` | pino (scaffolded) | Yes (scaffolded) | Per ticket | Yes (scaffolded) | Server-side auto | Yes |
| `chrome-extension` | Backend: structlog; Frontend: `chrome.storage.local` buffer | Backend only | Backend only | Backend only | Frontend: Sentry browser SDK | Backend only |
| `mobile-app` | Backend: structlog; Client: Sentry RN SDK | Backend only | Backend only | Backend only | Client: Sentry React Native SDK | Backend only |
| `desktop-app` | Backend: structlog; Client: per ticket | Backend only | Backend only | Backend only | Client: Sentry Electron SDK | Backend only |
| `wordpress` | WP debug log + Cloudflare analytics | Gatus checks site URL | N/A | N/A | N/A | Yes (site URL) |
| `docusaurus` | N/A (static site) | Nginx responds on `/` | N/A | N/A | N/A | Yes (site URL) |
| `static-site` | N/A (static site) | Nginx responds on `/` | N/A | N/A | N/A | Yes (site URL) |

**Two-faced types** (mobile-app, desktop-app, chrome-extension): the backend lane gets full observability (logging + health + metrics + GlitchTip). The client lane gets crash reporting (Sentry SDK for the platform) **plus product analytics** where the product needs it — for `chrome-extension`, GA4 Measurement Protocol v2 or PostHog-core behind a `chrome.storage` queue + `chrome.alarms` flush (see § Chrome Extension Telemetry). Consent-gated per the product's opt-out state.

---

## Log Pipeline (how it flows)

Understanding the pipeline prevents agents from breaking it:

```
App (structlog/pino) → JSON to stdout → Promtail (auto-discovers via docker.sock)
  → Loki (indexes by service/env/level labels) → Grafana (LogQL queries)
```

- **Apps emit JSON to stdout.** This is WHY JSON format is mandatory and `print()` is banned — Promtail parses JSON; raw text breaks field extraction.
- **Promtail auto-discovers ALL containers.** No per-service config needed. The lifecycle doc confirms: "auto-discovers ALL containers via docker.sock. No labels or config changes needed per service."
- **Loki indexes by low-cardinality labels only.** High-cardinality labels (request_id, user_id) cause OOM. Keep them in the JSON payload.
- **Grafana queries via LogQL** with JSON field extraction: `{service="myservice"} | json | level="error"`.

---

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
import logger from './logger.js';
logger.info({ event: 'event_name', key: 'value' });
```

- Module: `src/logger.js` — pino, JSON output, service name from `SERVICE_NAME` env var

**Next.js projects** (`saas-skeleton`):

```typescript
import logger from '@/lib/logger';
logger.info({ event: 'event_name', key: 'value' });
```

- Module: `lib/logger.ts` — pino, JSON output

**No scaffold logging on the client side:** `mobile-app`, `desktop-app`, `wordpress`, `docusaurus`, `static-site` — set up per ticket using the rules below. Note: `mobile-app` and `desktop-app` backends (python-api) DO get scaffold logging; only the client binary is unscaffolded.

**Chrome extension frontend:** Use `chrome.storage.local` buffer pattern per the Chrome Extension Telemetry section below. Do not use pino directly in service workers.

---

## `/metrics` Endpoint (Prometheus)

Every `python-api` and `node-api` scaffold emits a pre-configured `/metrics` endpoint. DO NOT create custom metrics modules.

**What the scaffold emits** (Python — `src/{package}/metrics.py`):

```python
from prometheus_client import Counter, Gauge

REQUEST_COUNT = Counter("request_count", "Total requests", ["method", "endpoint", "status"])
ERROR_COUNT = Counter("error_count", "Total errors", ["type"])
ACTIVE_JOBS = Gauge("active_jobs", "Currently running jobs")
PROCESSING_COUNT = Gauge("processing_count", "Items being processed")
```

- The `/metrics` endpoint is Authelia-bypassed. The bypass is **resource-based, not domain-bound** — `/health`, `/healthz`, `/metrics`, `/api/health` are bypassed on every domain routed through Authelia (hub direct + spokes via `authelia-vps1@file`).
- Prometheus scrapes it when the spec has `shape.exposes_metrics: true` — the Prometheus registrar adds the scrape target on `fabrik apply`.

**Adding custom business metrics:**

```python
from {package}.metrics import REQUEST_COUNT  # import scaffolded counters
from prometheus_client import Histogram

# Add domain-specific metrics alongside scaffolded ones
PROCESSING_DURATION = Histogram("processing_duration_seconds", "Time to process item", ["item_type"])
```

- Name metrics with `snake_case` and a unit suffix (`_seconds`, `_bytes`, `_total`).
- Use Counter for monotonic values, Gauge for current state, Histogram for distributions.
- Keep cardinality bounded — label values must be from a small, known set.

**Node projects:** Use `prom-client` with the same naming conventions. The scaffold emits the setup in `src/metrics.js`.

---

## Error Reporting (GlitchTip)

Every Fabrik project ships with a pre-scaffolded GlitchTip / Sentry SDK init module.
DO NOT create custom Sentry init code or use a different DSN library.

**Python projects** (`python-api`, `file-worker`):

- Module: `src/{package}/glitchtip_init.py` — `init_glitchtip()` with `FastApiIntegration`
- Wired in `main.py` BEFORE `app = FastAPI(...)` (the SDK must instrument the framework before app construction)
- Dependency: `sentry-sdk[fastapi]>=2.18.0` (in `pyproject.toml`)

**Node projects** (`node-api`, `file-api`):

- Module: `src/glitchtip_init.js` — `Sentry.init()` from `@sentry/node`
- Wired via `import './glitchtip_init.js'` at the top of `src/index.js`, BEFORE other imports
- Dependency: `@sentry/node` (in `package.json`)

**No-op semantics (BOTH platforms):**

- If `GLITCHTIP_DSN` env var is unset/empty → init returns early, ZERO overhead, ZERO crashes
- If the SDK package itself is missing (rare) → init still no-ops, does NOT crash the service
- This is intentional: services without DSN configured never pay for SDK runtime cost

**Capture discipline — when DSN is set, errors auto-report:**

- Unhandled exceptions (FastAPI 500s, uncaught Node throws, unhandled promise rejections) → AUTO-CAPTURED. Do nothing extra.
- DO NOT call `logger.exception()` / `logger.error()` with full tracebacks for unhandled errors — that duplicates the GlitchTip event AND wastes Loki storage. Log a short event name with correlation_id; let GlitchTip carry the stacktrace.
- Use `sentry_sdk.capture_exception(e)` (Python) or `Sentry.captureException(e)` (Node) ONLY for **caught-then-rethrown** control flow where the exception would otherwise be swallowed (e.g., catch in a worker loop to keep the worker alive, log the event, then continue).
- DO NOT call `capture_exception` from inside a FastAPI handler that re-raises `HTTPException` — the integration already handles it.

**Provisioning a project + DSN:**

```bash
# From WSL — auto-extracts creds from /opt/fabrik/.env, re-execs on VPS via SSH.
bash /opt/fabrik/scripts/provision_glitchtip_project.sh <service-name>

# For Node services use the matching platform tag:
bash /opt/fabrik/scripts/provision_glitchtip_project.sh <service-name> --platform javascript-node
```

Under `fabrik apply`, the GlitchTip registrar provisions the project and injects
the DSN automatically — `infrastructure.py` calls `deployer.inject_env(ctx, {"SENTRY_DSN": dsn, "GLITCHTIP_DSN": dsn})`, which writes the var into the service
`.env` over SSH and restarts the container (`deployer_ssh.inject_env`). The
standalone script above is for manual/out-of-band provisioning only.

The script is idempotent (re-runs return the same DSN). The DSN host is rewritten
to `glitchtip-web:8000` (stable Docker DNS alias on the `fabrik` network) so events
flow through the internal network without Authelia or TLS overhead.

Environment variables consumed by the init modules (injected into the service `.env` by `fabrik apply`, not in `.env.example`):

| Variable | Default | Notes |
|---|---|---|
| `SENTRY_DSN` / `GLITCHTIP_DSN` | (unset → no-op) | The DSN returned by the provisioner (Fabrik injects `SENTRY_DSN`; `GLITCHTIP_DSN` kept as fallback alias) |
| `ENVIRONMENT` | `production` | Tags events; useful for prod vs staging filtering |
| `GIT_SHA` | (unset) | Release tag — falls back to legacy `COOLIFY_DEPLOYMENT_UUID` if present |
| `GLITCHTIP_TRACES_SAMPLE_RATE` | `0.05` | Keep low; perf events flood the shared GlitchTip |
| `GLITCHTIP_PROFILES_SAMPLE_RATE` | `0` | Profiling off by default — adds native deps |

Runbook: `docs/infrastructure/glitchtip-sdk-integration-setup.md`

---

## Mobile Client Crash Reporting

For `mobile-app` projects, the backend gets GlitchTip (above). The **client app** uses the Sentry React Native SDK:

- **SDK:** `@sentry/react-native` — wraps the native crash reporters (iOS + Android) with JS error boundary.
- **Init:** in app entry point (before `registerRootComponent`). DSN from env/config, not hardcoded.
- **What it captures:** JS exceptions, native crashes, ANR (Application Not Responding), unhandled promise rejections.
- **Privacy:** no PII in breadcrumbs or tags. Strip user email/name from Sentry context. See `80-mobile.md` § Compliance.
- **Crash-free rate target:** >= 99.5% (store ranking factor).
- **Source maps:** upload via `@sentry/react-native/expo` plugin + Sentry Metro plugin in EAS build config for readable stack traces. `sentry-expo` is deprecated since Expo SDK 50 — do not use it.

For `desktop-app`: use `@sentry/electron`. Same principles.

For `chrome-extension`: use `@sentry/browser` in the popup/options/side-panel (trusted extension pages). **In content scripts, never call the global `Sentry.init`** — a content script shares the host page's `window`, so global-state integrations hijack host-page errors. Build an isolated `BrowserClient` + `Scope` (drop `GlobalHandlers` / `Breadcrumbs`) and wrap with `makeBrowserOfflineTransport` (IndexedDB buffer/flush). Service workers use the `chrome.storage.local` buffer pattern (see Chrome Extension Telemetry below).

---

## WordPress Observability

WordPress projects don't get scaffold logging or `/metrics`. Observability is simpler:

- **Health monitoring:** Gatus checks the site URL (HTTP 200). Configured by the Gatus registrar on `fabrik apply`.
- **Error logging:** WP debug log (`WP_DEBUG_LOG`) for development only — disable in production (`define('WP_DEBUG', false)`).
- **Analytics:** Cloudflare analytics (built into CDN, no plugin needed) + GA4 if configured per the domain module.
- **Uptime alerting:** Gatus → Apprise notification on consecutive failures.
- **Backups:** Backrest → B2 (DB + uploads). Verification via Backrest's built-in health check.
- **Security monitoring:** Cloudflare WAF logs + security plugin alerts (from the approved plugin manifest).

No GlitchTip, no Prometheus, no structlog — WordPress is a pre-built runtime, not custom code.

---

## Structured Logging

- All production logs must be **JSON-formatted**. Human-readable colorised output is for local development only.
- Use `structlog` for Python and `pino` for Node.js/Next.js. No other logging libraries.
- `print()` in Python and `console.log()` / `console.error()` in JavaScript are **banned** in production code paths. Route all output through the structured logger.
- Log event names must be machine-parseable `snake_case` (e.g. `user_authenticated`, `db_connection_failed`). No conversational prose or dynamic string interpolation in event names.
- **Caught-and-handled** exceptions: log with stack traces via `exc_info=True` in Python (dedicated JSON attribute, never raw multi-line text). **Unhandled** exceptions (FastAPI 500s, uncaught throws): do NOT log tracebacks — GlitchTip auto-captures them. Log a short event name + `correlation_id` only. See § Error Reporting above.

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

---

## Health Endpoint Semantics

- Every service exposes `/health` that actively verifies critical dependencies (e.g. `SELECT 1` against PostgreSQL, Redis `PING`) before returning 200.
- A `/health` that returns 200 without checking dependencies creates "zombie" containers — Traefik routes traffic to broken services.
- Docker Compose `HEALTHCHECK` must include `start_period` (15-20s) to allow framework boot and DB migrations before the container is marked unhealthy.
- `/health` is Authelia-bypassed on all services. The bypass is **resource-based, not domain-bound** — `/health`, `/healthz`, `/metrics`, `/api/health` are bypassed on every domain routed through Authelia (hub direct + spokes via `authelia-vps1@file`). Never protect these paths.
- Enforcement: `scripts/enforcement/check_health.py` verifies that health endpoints contain real dependency checks (regex for `SELECT 1`, `.ping()`, etc.). Superficial health endpoints fail the gate.

```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:${PORT:-8000}/health"]
  interval: 30s
  timeout: 5s
  retries: 3
  start_period: 20s
```

---

## Alert Thresholds (SLO-Lite)

Alert only on **user-facing symptoms** using the RED method (Rate, Errors, Duration). Infrastructure metrics are for dashboards, not pager alerts.

| Metric | Source | Threshold | Action |
|--------|--------|-----------|--------|
| External availability | Gatus | 3 consecutive failures / 60s | Push notification |
| HTTP 5xx error rate | Grafana Loki (LogQL) | > 5% of requests over 5 min | Push notification |
| P95 latency | Grafana Loki (LogQL) | > 2.0s sustained over 5 min | Push notification |
| Registrar drift | Prometheus (`fabrik_audit_drift_total`) | Any drift for > 10 min | Alertmanager → Telegram |
| CPU / RAM spikes | cAdvisor / node-exporter → Prometheus (Netdata removed 2026-05-30) | N/A — do not page | Dashboard only |

---

## Synthetic Monitoring

- Gatus provides black-box availability checks completely decoupled from the internal logging pipeline. If Loki is down, Gatus still detects application failure.
- Container restart is handled by the Docker daemon (`restart: unless-stopped`). Per-service watchdog scripts are **not required** — Gatus + Docker restart policy + Prometheus alerting provides three independent layers.

## Gatus — Stable DNS Names (CRITICAL)

Never use UUID or timestamp-suffixed container names in Gatus configs or inter-service URLs — they drift per redeploy.

- **`fabrik apply` services** (`/opt/<name>/compose.yaml`): set an explicit, stable `container_name:` in compose and reference it directly. Docker DNS resolves it on the `fabrik` network.
- **Legacy single-image containers** without a fixed name: install a stable network alias on the `fabrik` network so DNS doesn't break silently.

Install procedure + currently-registered alias pairs (`browserless`, `gotenberg`, `meilisearch`, `glitchtip-web`) live in `docs/infrastructure/archive/coolify-stable-aliases.md` (historical) and the live `apply_alias` section of `scripts/vps_apply_limits.sh`. Boot-time reapply: `scripts/vps_apply_limits.sh`.

---

## Chrome Extension Telemetry

- MV3 service workers are ephemeral (terminated after ~30s idle). Do not hold logs in memory waiting for a batch window.
- Buffer logs to `chrome.storage.local` or `chrome.storage.session`, then flush asynchronously to the backend via `navigator.sendBeacon()` or non-blocking `fetch` when network permits.
- **Product analytics** (GA4 Measurement Protocol v2 or PostHog-core) use the same discipline: enqueue events to a `chrome.storage` queue and flush on a **`chrome.alarms`** tick — a fire-and-forget request from the SW dies with the worker. GA4-MP is pure HTTP (MV3-safe); PostHog-core needs `module.no-external` with rrweb stripped.
- Handle `chrome.runtime.lastError` during I/O to prevent unhandled promise rejections from crashing the worker.

---

## Banned Patterns

| Pattern | Use Instead |
|---------|-------------|
| `print()` in Python production code | `structlog` logger |
| `console.log()` / `console.error()` in JS production code | `pino` logger |
| CommonJS `require()` for logger/glitchtip | ES module `import` |
| High-cardinality Loki labels (`request_id`, `user_id`, `ip`) | Embed in JSON payload, query via LogQL parsers |
| Superficial `/health` returning static 200 | Verify DB connection + critical deps before 200 |
| `HEALTHCHECK` without `start_period` | Add `start_period: 20s` for boot tolerance |
| Alerting on CPU/RAM spikes | Alert on RED symptoms only (errors, latency) |
| Logging PII/secrets then relying on downstream redaction | Redact at application edge before emission |
| Synchronous `console.log` for heavy objects in Node.js | `pino` with worker thread transport |
| Custom metrics module from scratch | Extend scaffolded `metrics.py` / `metrics.js` |
| Hardcoded GlitchTip DSN in repo | `GLITCHTIP_DSN` env var, injected by registrar |
| Per-service watchdog bash scripts | Gatus + Docker `restart: unless-stopped` |
| `sentry-expo` for source maps | `@sentry/react-native/expo` plugin (sentry-expo deprecated since SDK 50) |
| `logger.exception()` for unhandled errors | Short event + correlation_id — GlitchTip auto-captures the traceback |

---

## Done When

- [ ] All services emit JSON-structured logs via `structlog` (Python) or `pino` (Node.js).
- [ ] No `print()` or `console.log()` in production code paths.
- [ ] `X-Request-ID` middleware present in FastAPI (using `contextvars`) — correlation ID in every log entry.
- [ ] PII/secret redaction configured in logger (regex filters for emails, tokens, passwords).
- [ ] `/health` endpoint verifies actual dependencies (DB, Redis, consumed APIs) before returning 200.
- [ ] `/metrics` endpoint exposes scaffolded counters + any custom business metrics (when `shape.exposes_metrics: true`).
- [ ] Docker Compose `HEALTHCHECK` includes `start_period`.
- [ ] Loki labels limited to low-cardinality values (`service`, `environment`, `level`).
- [ ] Alert rules target RED symptoms only — no infrastructure cause-based paging.
- [ ] Gatus configured for external synthetic monitoring of all public endpoints.
- [ ] GlitchTip DSN provisioned and injected via env var (not hardcoded).
- [ ] (Mobile) Sentry React Native SDK init'd in app entry point; crash-free >= 99.5%.
- [ ] (WordPress) Gatus monitors site URL; `WP_DEBUG` off in production.

---

## Related Rule Packs

- `10-python.md` — scaffolded logger import (`from {package}.logger import get_logger`), error logging discipline
- `20-typescript.md` — pino logger, `console.log` ban
- `30-ops.md` — HEALTHCHECK `start_period: 20s`, `/health` Authelia bypass
- `58-resilience.md` — `/health` endpoint contract (dep checks, not static 200)
- `80-mobile.md` — Sentry React Native SDK, crash-free target >= 99.5%

---

## Spec Contract — Observability Registrars

- Service should expose `/metrics` only when `shape.exposes_metrics: true` (Prometheus registrar will add the scrape target on `fabrik apply`).
- Service should expose `/health` always (Gatus registrar depends on it when `shape.is_public: true`).
- GlitchTip DSN comes from `GLITCHTIP_DSN` env var injected by the orchestrator from the GlitchTip registrar — do NOT hardcode the DSN in the repo.
- Scaffolder does NOT emit Prometheus/Promtail/cAdvisor labels or configs per service — those are handled by the registrar system or by auto-discovery (Promtail, cAdvisor via docker.sock). compose.yaml is the build/deploy contract; observability config is the registrar's domain.

---

## Legacy Note: Watchdog Scripts

`scripts/enforcement/check_watchdog.py` exists in the systemic gate (Tier 3) and checks for `scripts/watchdog*.sh` in service projects. This check is **legacy** — Gatus + Docker `restart: unless-stopped` + Prometheus alerting provide three independent monitoring/restart layers, making per-service watchdog scripts redundant. New projects should NOT create watchdog scripts. Existing projects that have them can keep them but they are not required for new services.
