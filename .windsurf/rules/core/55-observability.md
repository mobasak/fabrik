---
activation: glob
globs: ["**/health*", "**/logging*", "**/logger*", "**/metrics*", "**/middleware/**", "**/monitoring/**", "**/glitchtip*", "**/sentry*"]
description: Observability discipline — structured logs (stdout only, no logfiles), correlation IDs, health/readiness, metrics, alert thresholds, crash reporting
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

Not every scaffold type gets every observability feature. **Ground each row against what the scaffolder actually emits** (`scaffold.py::SCAFFOLD_TYPES` is the registry) — a row claiming a capability the type has no machinery for (a worker with no HTTP server cannot serve `/health`) is worse than no row:

| Scaffold | Structured logging | `/health` | `/metrics` | GlitchTip | Crash reporting | Gatus monitor |
|---|---|---|---|---|---|---|
| `python-api` | structlog (scaffolded) | Yes (scaffolded) | Yes (scaffolded) | Yes (scaffolded) | Server-side auto | Yes |
| `node-api` | pino (scaffolded) | Yes (scaffolded) | Yes (scaffolded) | Yes (scaffolded) | Server-side auto | Yes |
| `file-api` | pino (scaffolded) | Yes (scaffolded) | Yes (scaffolded) | Yes (scaffolded) | Server-side auto | Yes |
| `file-worker` | structlog (scaffolded) | **No — no HTTP server exists** | **No** | Per ticket | Server-side auto | Via its own liveness signal, not HTTP |
| `saas-skeleton` | pino (scaffolded) | Yes (scaffolded) | Yes (scaffolded) | Yes (scaffolded) | Server-side auto | Yes |
| `chrome-extension` | Backend: structlog; Frontend: `chrome.storage.local` buffer | Backend only | Backend only | Backend only | Frontend: Sentry browser SDK | Backend only |
| `mobile-app` | Backend: structlog; Client: Sentry RN SDK | Backend only | Backend only | Backend only | Client: Sentry React Native SDK | Backend only |
| `desktop-app` | Backend: structlog; Client: per ticket | Backend only | Backend only | Backend only | Client: Sentry Electron SDK | Backend only |
| `wordpress` | WP debug log + Cloudflare analytics | Gatus checks site URL | N/A | N/A | N/A | Yes (site URL) |
| `docusaurus` | N/A (static site) | Nginx responds on `/` | N/A | N/A | N/A | Yes (site URL) |
| `static-site` | N/A (static site) | Nginx responds on `/` | N/A | N/A | N/A | Yes (site URL) |
| `python-api-gpu` | as `python-api` | as `python-api` | as `python-api` | as `python-api` | Server-side auto | Yes |
| `office-extension` | Backend: structlog; Client: per ticket | Backend only | Backend only | Backend only | Client: per ticket | Backend only |

**Two-faced types** (mobile-app, desktop-app, chrome-extension): the backend lane gets full observability (logging + health + metrics + GlitchTip). The client lane gets crash reporting (Sentry SDK for the platform) **plus product analytics** where the product needs it — for `chrome-extension`, the GA4 Measurement Protocol or PostHog's core/no-external build behind a `chrome.storage` queue + `chrome.alarms` flush (see § Chrome Extension Telemetry). Consent-gated per the product's opt-out state.

---

## Log Pipeline (how it flows)

Understanding the pipeline prevents agents from breaking it:

```
App (structlog/pino) → JSON to stdout → Docker json-file logs
  → the log shipper (tails /var/lib/docker/containers/*/*log)
  → Loki (indexes by the SIX pipeline labels below) → Grafana (LogQL queries)
```

⚠️ **The shipper is Promtail today and Promtail reached END OF LIFE (2026-03-02)** — no
updates, no support. Grafana Alloy is the successor (`alloy convert` migrates the config).
Fleet migration is an infra action, not a per-project one; until it lands, nothing about the
rules below changes.

- **Apps emit JSON, unbuffered, to stdout — and nothing else.** This is WHY JSON format is mandatory and `print()` is banned — the shipper parses JSON; raw text breaks field extraction. See § Logs (12-Factor Factor XI) for the full ban on logfiles.
- **The shipper picks up ALL containers by filesystem glob** (`/var/lib/docker/containers/*/*log`), not via docker.sock — no per-service config needed, and a drop rule filters known noise. Debug missing logs at the glob + drop stages, not at a socket.
- **Loki indexes by low-cardinality labels only.** High-cardinality labels (request_id, user_id) cause OOM. Keep them in the JSON payload — or, when a field must be queryable without becoming a stream, in structured metadata (enabled on this fleet).
- **The label set is the PIPELINE's, not yours** — live: `container_name`, `filename`, `host`, `job`, `service_name`, `stream`. An app cannot add labels by logging a field; a JSON field is queried with `| json`, never as a label.
- **Grafana queries via LogQL** with JSON field extraction: `{service_name="myservice"} | json | level="error"` (verify label names against the live set before writing a query — `service`, `environment` and `level` are NOT labels here).

---

## Logs (12-Factor Factor XI) — stdout only, no logfiles (CRITICAL)

> 12factor.net, verbatim:
> *"each running process writes its event stream, unbuffered, to `stdout`"*
> *"A twelve-factor app never concerns itself with routing or storage of its output stream. It should not attempt to write to or manage logfiles."*

**Mandate.** The app writes structured events, unbuffered, to `stdout` and **nothing else**. The app MUST NEVER write, rotate, append to, truncate, compress, age out, or otherwise manage a logfile, and MUST NEVER decide where logs are stored, how long they are kept, or how they are routed. Routing, rotation, retention, and storage are exclusively the **execution environment's** concern.

**The split is 12-Factor-correct:**

```
App:       JSON → stdout (unbuffered)   ← app's only job
Runtime:   Docker captures stdout
Platform:  shipper → Loki → Grafana      → routing/retention lives here
```

**BANNED in app code:**

- `logging.FileHandler` (Python stdlib)
- `logging.handlers.RotatingFileHandler`
- `logging.handlers.TimedRotatingFileHandler`
- `watchedfiles`, `concurrent-log-handler`, `loguru` file sinks, or any third-party file sink
- Direct file writes for log output: `open("/var/log/...", "a")`, `Path("/var/log/...").write_text(...)`, or any `*.log` file under `/var/log/`, `/tmp/`, the project tree, a mounted volume, or a sidecar path
- Any in-app log rotation, retention, GC, archival, compression, or cleanup task
- `docker-compose` `volumes:` that mount a host directory for the app to write logs into (the app does not own a log path)

**Required behaviour:**

- The scaffolded logger (structlog / pino — see § Pre-Scaffolded Logging) writes to stdout. Do not add a second handler, sink, or transport alongside the stdout one.
- Python: `sys.stdout` is line-buffered for ttys but **block-buffered when piped** — flush after every record (the scaffolded `structlog` config already does this; do not add a `buffering=` or wrapper that batches).
- Node: `pino` defaults to flush-on-write; do not set `pino.destination()` to a file path, and do not introduce a worker-thread file transport in app code.
- Container stdout is captured by the Docker daemon and tailed by the log shipper — that is the entire delivery path. The app has no business knowing any of that.

❌ **BANNED — in-app file logging:**

```python
import logging
from logging.handlers import RotatingFileHandler

logger = logging.getLogger(__name__)
logger.addHandler(RotatingFileHandler("/var/log/myapp/app.log", maxBytes=10_000_000, backupCount=5))
logger.info("user_login")  # writes to /var/log — app owns routing/rotation
```

✅ **CORRECT — stdout only, unbuffered:**

```python
from myapp.logger import get_logger  # scaffolded structlog — see § Pre-Scaffolded Logging
logger = get_logger(__name__)
logger.info("user_login", user_id=user.id)  # JSON to stdout; the shipper picks it up
```

Local development may tee stdout to a terminal pane; that is a developer-machine concern, not an app concern, and is not wired in production code paths.

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

> **⚠️ THE SERVER'S OWN LOGGERS ARE NOT YOURS — and they leak plain text by default.**
> Configuring structlog covers only what YOUR code logs. `uvicorn`, `uvicorn.access`,
> `uvicorn.error`, `gunicorn` and SQLAlchemy keep their own stdlib handlers and emit
> unstructured lines like `INFO:     127.0.0.1:54012 - "GET /health HTTP/1.1" 200 OK` into the
> same stdout — so a service that looks "properly logging" ships a MIX, and every unstructured
> line is one Loki cannot label, filter or alert on. Measured live on this fleet (2026-09-01):
> the scaffolded `site-provisioner` emits textbook structlog JSON *and* raw uvicorn access lines
> side by side.
> **The fix is THREE steps and all three are load-bearing** (the scaffold is being updated to emit
> them; a service that predates it backfills):
> 1. **Route, don't just configure** — `structlog.stdlib.LoggerFactory()` + end the chain with
>    `ProcessorFormatter.wrap_for_formatter`, then one root `StreamHandler` whose formatter is
>    `ProcessorFormatter(foreign_pre_chain=…, processors=[remove_processors_meta, JSONRenderer()])`.
>    That is what makes THIRD-PARTY records render as JSON.
> 2. **`uvicorn`/`uvicorn.error`: clear handlers AND set `propagate = True`** so they reach root.
>    (`uvicorn.access` is different — it ships `propagate: False`, so clearing its handlers
>    SILENCES it rather than routing it. Silence is the right choice once your X-Request-ID
>    middleware logs each request; just know which of the two you are doing.)
> 3. **Stop uvicorn re-applying its own dictConfig over yours** — `log_config=None` (or a
>    neutralising `--log-config`); without this the first two steps are undone at startup.
>
> **A service is not "properly logging" until EVERY line on its stdout is JSON** — verify by eye:
> `docker logs <container> --tail 20 | grep -v '^{'` must print nothing.

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

- Name metrics with `snake_case` and a **base-unit** suffix (`_seconds`, `_bytes`); `_total` is the COUNTER suffix and composes with units (`process_cpu_seconds_total`). ⚠️ `prometheus_client` appends `_total` to a Counter itself — declare `Counter("requests", …)`, never `Counter("requests_total", …)`, and never `_count` (an OpenMetrics reserved suffix).
- Use Counter for monotonic values, Gauge for current state, Histogram for distributions.
- Keep cardinality bounded — label values must be from a small, known set. The test: **if a label
  value can differ per request, it is not a metric label** (`user_id`, `request_id`, `order_id`,
  raw URLs, raw error messages). Route templates, status codes, methods and bounded error
  categories are safe. Put the unbounded ones in LOGS, where high cardinality is fine.
- ⚠️ **Know which failure YOUR stack gives you — they are not the same.** Under an OTel SDK, a
  metric that overflows its cardinality limit fails SILENTLY: totals stay correct while queries
  that *filter or group by* an attribute UNDERCOUNT, so dashboards and SLOs keep rendering numbers
  that are quietly too low. **Our scaffolded stack is `prometheus_client`, which has no such
  limit** — here a blowup is memory/TSDB growth, and Prometheus's own `sample_limit` fails the
  whole scrape LOUDLY (`up=0`) rather than skewing a breakdown. Loud is survivable; the reason to
  care about both is that a service moving to OTel inherits the silent one.
- **What the scaffold actually emits** (read `{package}/metrics.py` before importing): `REQUEST_COUNT` = Counter `fabrik_requests_total` labelled `["endpoint","status"]` (no `method`), `ERROR_COUNT` + `PROCESSING_COUNT` = Counters, `REQUEST_DURATION` + `ACTIVE_JOBS` = **Histograms** — calling `.set()` on them raises. Import the names; do not assume their types.

**Node projects:** no metrics module is scaffolded today — wire the Prometheus client yourself if `shape.exposes_metrics` is set, and do not set that flag until `/metrics` genuinely serves.

---

## Error Reporting (GlitchTip)

Every Fabrik project ships with a pre-scaffolded GlitchTip / Sentry SDK init module.
DO NOT create custom Sentry init code or use a different DSN library.

### ⚠️ Two init flags are MANDATORY, and `send_default_pii=False` covers NEITHER

Every `sentry_sdk.init` / `Sentry.init` in the fleet MUST set both:

| Python | Node | Closes |
|---|---|---|
| `include_local_variables=False` | `includeLocalVariables: false` | frame LOCALS — the SDK default is `True`, so with `LoggingIntegration`'s ERROR level any `logger.error/exception` in a function holding a settings object ships its **repr**: `DATABASE_URL`, the JWT signing secret, everything |
| `max_request_body_size="never"` | **n/a — see below** | the request BODY, attached irrespective of `send_default_pii` (that flag gates COOKIES). Every auth, payments-webhook and token-exchange route is exposed the moment it logs an error while handling its request. **PYTHON ONLY** |

⚠️ **The two SDKs are NOT symmetric, and the Node column originally said otherwise — that was my
error, corrected 2026-08-28 by fleet.** `maxRequestBodySize` is a PYTHON option name;
`@sentry/node` has no such init key, so a project that dutifully added it got a silently-ignored
unknown key — a line that reads like a fix and does nothing. In `@sentry/node` the body channel is
already closed by `sendDefaultPii: false`, which makes the SDK report body **size only, never
content**. If a project wants it structural regardless of PII, the real control is
`httpIntegration({ maxIncomingRequestBodySize: 'none' })` — note `'none'`, not `'never'`.
`includeLocalVariables: false` IS correct and needed for Node (locals default ON for Node runtimes).
**Never port an option name across SDKs by symmetry; check that SDK's own docs.**

**Python's `EventScrubber()` is ON by default regardless of `send_default_pii`**, and its
`DEFAULT_DENYLIST` (plus a small `DEFAULT_PII_DENYLIST`) already scrubs the `Authorization` header plus
`api_key`/`token`/`secret` BY KEY. So the HTTP-header channel is closed out of the box — that is the
one name-based path that works, precisely because Sentry ships and maintains the list rather than a
project guessing at it.

**A `before_send` denylist is NOT an acceptable substitute — it is the thing that already failed.**
Sentry scrubs BY VARIABLE NAME: a live probe filtered a local named `token`, missed one named
`code`, and could not see the signing secret at all because it sat inside a `Settings(...)` repr
STRING, which name matching cannot look into (transdoc, 2026-08-28: a real one-time passcode and
JWT secret reached GlitchTip from a scaffolded service). Both flags remove the data
**structurally**; a denylist only removes the names somebody remembered.

**Verify on the CAPTURED EVENT, never the init kwarg.** Swap the SDK transport in a test, make a
real dependency raise, and assert on what the event actually contains — asserting the kwarg was
passed proves you configured it, not that nothing leaks.

⚠️ The scaffold emits both flags as of 2026-08-28. **A project scaffolded BEFORE that date still
has the old init** — grep your own `glitchtip_init.*` and add them; nothing back-fills it.

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
- DO NOT call `capture_exception` for an `HTTPException` whose status is in `failed_request_status_codes` — the integration already captures it (default: **all 5xx**, matched duck-typed on `.status_code`, recorded as `handled: True` rather than an unhandled crash).
- ⚠️ **Outside that set nothing captures it.** A deliberate 401/403/429 you WANT audited reaches GlitchTip never — widen `failed_request_status_codes` in the init rather than sprinkling `capture_exception` through handlers.

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

⚠️ **Why this fleet stops at a correlation ID, and what to name the field.** Probed 2026-09-01 across
ALL THREE fleet hosts (vps1/vps2/vps3): Loki + Prometheus + Grafana only — **no DEDICATED trace
backend (Tempo/Jaeger) and no OTel collector on any of them**, and Grafana carries exactly two
datasources (loki, prometheus). ⚠️ Not "no spans at all": Sentry-SDK services already emit
performance transactions to GlitchTip at `GLITCHTIP_TRACES_SAMPLE_RATE` (§ config above) — that is
the only span-shaped signal here, and it is not a queryable trace store.
So do NOT instrument distributed tracing here: spans with nowhere to go are cost without a consumer,
and "add OpenTelemetry" is over-engineering until a backend exists. A request-scoped correlation ID
is the correct ceiling for our topology.
**But name the field as though the backend will arrive**, because renaming later means touching
every service: when a span context IS available, log `trace_id` and `span_id` (the OTel semantic
convention names) rather than inventing a bespoke key — an OTel-integrated logger injects them for
free. Costs nothing today; saves a fleet-wide migration. The upgrade path, if a trace backend is
ever adopted, is metric → trace → log: the alert points at a metric, the metric's exemplar points at
a trace, the trace's `trace_id` points at the log lines. Until then, the correlation ID carries the
last link alone.

## PII & Secret Redaction

- PII (emails, SSNs, credit card numbers), auth tokens, passwords, and API keys must be redacted **at the application edge** before log emission.
- Implement redaction via regex filters in the logger configuration (`structlog` processors in Python, `pino` redact paths in Node.js).
- Never rely on downstream log processors (Promtail, Logstash) for redaction — unredacted data may persist in transport buffers.
- Replace matched values with static tokens (e.g. `[REDACTED_EMAIL]`, `[REDACTED_TOKEN]`).

## Loki Label Discipline

- **Never** use high-cardinality values as Loki stream labels. `request_id`, `user_id`, `session_id`, `client_ip` must remain inside the JSON payload only.
- ⚠️ **The label set is the PIPELINE's — an app cannot create one by logging a field.** See § Loki
  above for the LIVE set; `service`, `environment` and `level` are *not* labels on this fleet, they
  are JSON fields queried with `| json`.
- High-cardinality labels cause index bloat and OOM crashes on constrained VPS.

---

## Health Endpoint Semantics

- Every service exposes `/health` that actively verifies critical dependencies (e.g. `SELECT 1` against PostgreSQL, Redis `PING`) before returning 200.
- A `/health` that returns 200 without checking dependencies creates "zombie" containers — Traefik routes traffic to broken services.
- Docker Compose `HEALTHCHECK` must include `start_period` (15-20s) to allow framework boot and DB migrations before the container is marked unhealthy.
- `/health` is Authelia-bypassed on all services. The bypass is **resource-based, not domain-bound** — `/health`, `/healthz`, `/metrics`, `/api/health` are bypassed on every domain routed through Authelia (hub direct + spokes via `authelia-vps1@file`). Never protect these paths.
- Enforcement: **none mechanical.** `check_health.py` exists but is WARN-only and deliberately UNWIRED from the gate (its heuristic cannot distinguish a service with no dependencies from one that skips probing them). The real-deps invariant is enforced by REVIEW — do not read a green gate as proof the health endpoint probes anything.

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
- **Product analytics** (GA4 Measurement Protocol or PostHog's core/no-external build) use the same discipline: enqueue events to a `chrome.storage` queue and flush on a **`chrome.alarms`** tick — a fire-and-forget request from the SW dies with the worker. GA4-MP is pure HTTP (MV3-safe); PostHog needs the core/no-external build with session-replay/rrweb stripped.
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
| Adding a NEW cause-based alert without a symptom it explains | Prefer RED symptoms (errors, latency, saturation-of-the-user-visible-thing). The fleet DOES ship resource alerts (container/host CPU, memory, disk) as early-warning — extend those rather than minting per-service CPU rules |
| Logging PII/secrets then relying on downstream redaction | Redact at application edge before emission |
| Synchronous `console.log` for heavy objects in Node.js | `pino` with worker thread transport |
| Custom metrics module from scratch (Python) | Extend the scaffolded `{package}/metrics.py` — read its real types first |
| Hardcoded GlitchTip DSN in repo | `GLITCHTIP_DSN` env var, injected by registrar |
| `logging.FileHandler` / `RotatingFileHandler` / `TimedRotatingFileHandler` in app code | Scaffolded `structlog` / `pino` to stdout — see § Logs (12-Factor Factor XI) |
| Writing logs to `/var/log/**`, a mounted volume, or a `*.log` file in app code | JSON to stdout only — routing/rotation is the execution environment's job |
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
- [ ] No app-invented Loki labels — the label set is the pipeline's; verify against the LIVE set in § Loki (high-cardinality values stay in the JSON payload).
- [ ] New alert rules target RED symptoms; resource alerts stay in the shared fleet rule set, not per service.
- [ ] Gatus configured for external synthetic monitoring of all public endpoints.
- [ ] GlitchTip DSN provisioned and injected via env var (not hardcoded).
- [ ] App emits logs to stdout only — no `FileHandler` / `RotatingFileHandler` / `TimedRotatingFileHandler`, no writes to `/var/log/**`, no in-app rotation/retention (see § Logs).
- [ ] (WordPress) Gatus monitors site URL; `WP_DEBUG` off in production.

---

## Related Rule Packs

- `10-python.md` — scaffolded logger import (`from {package}.logger import get_logger`), error logging discipline
- `20-typescript.md` — pino logger, `console.log` ban
- `30-ops.md` — container HEALTHCHECK targets the **dep-free `/healthz`** (liveness); this pack's `/health` is the **readiness** probe Gatus consumes. Two endpoints, two jobs — a service that ships only `/health` fails 30-ops's deploy checklist
- `58-resilience.md` — `/health` endpoint contract (dep checks, not static 200)
- `60-watchdog.md` + `core/self-healing.md` — the AI watchdog SIDECAR every project gets (D-052); distinct from the retired per-service bash scripts discussed above
- `mobile-app/80-mobile.md` — Sentry React Native SDK, crash-free target >= 99.5%

---

## OpenTelemetry — deliberately NOT adopted at the instrumentation layer (measured, 2026-09-01)

Do not propose OTel instrumentation for a fleet service without new evidence. Measured against
this stack: OTel **logs** remain the weakest-maturity signal in both Python and JS — exactly the
one Loki already serves well — and adoption would mean a stateful Collector on memory-constrained
VPSes plus re-instrumenting every project to gain distributed tracing nobody has asked for. The
logs + metrics + errors triad stays.
**The nuance that DOES bind:** the Promtail→Alloy migration above is itself OTel-Collector-based,
so the fleet adopts OTel at the COLLECTION layer by necessity. Collection: yes, forced.
Instrumentation: deferred until a real cross-service tracing need appears — then re-open this
with a spec, not from vibes.

---

## Spec Contract — Observability Registrars

- Service should expose `/metrics` only when `shape.exposes_metrics: true` (Prometheus registrar will add the scrape target on `fabrik apply`).
- Service should expose `/health` always (Gatus registrar depends on it when `shape.is_public: true`).
- GlitchTip DSN comes from `GLITCHTIP_DSN` env var injected by the orchestrator from the GlitchTip registrar — do NOT hardcode the DSN in the repo.
- Scaffolder does NOT emit Prometheus/Promtail/cAdvisor labels or configs per service — those are handled by the registrar system, or picked up automatically by the log shipper's container glob and cAdvisor. compose.yaml is the build/deploy contract; observability config is the registrar's domain.

---

## Legacy Note: Watchdog Scripts

`scripts/enforcement/check_watchdog.py` exists but is UNWIRED from the gate (runnable by hand). Its subject — per-service **bash** `watchdog*.sh` scripts — is **legacy** and distinct from the AI watchdog SIDECAR that D-052 gives every project (`60-watchdog.md`, `self-healing.md`). For bash scripts: Gatus + Docker `restart: unless-stopped` + Prometheus alerting provide three independent monitoring/restart layers, making per-service watchdog scripts redundant. New projects should NOT create watchdog scripts. Existing projects that have them can keep them but they are not required for new services.
