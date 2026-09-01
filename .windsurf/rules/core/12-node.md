---
activation: glob
globs: ["**/*.js", "**/*.mjs", "**/*.cjs", "**/*.ts", "**/package.json", "**/package-lock.json"]
description: Node.js production backend patterns (current LTS) — Fastify/Express, ESM, pino + ALS, graceful drain, npm hygiene, helmet, CVE-aware
trigger: glob
---
<!-- CONSUMER: Coding agents (Claude Code + dispatched subagents)
     GOAL: Node.js backend service patterns for Fabrik VPS deployment — framework, runtime, observability, lifecycle, security, supply chain
     TRAYCER USAGE: Injects as Context File for tickets on node-api / file-api scaffolds or any .js/.ts backend.
     AGENT USAGE: Follow verbatim. Research basis: docs/reference/research/Node Backend Practices Research 2026.md (cited). -->

# Node.js Backend Rules

**Activation:** Glob `**/*.{js,mjs,cjs,ts}`, `**/package.json`, `**/package-lock.json`
**Purpose:** current-LTS Node production backend services on Fabrik's shared VPS fleet — framework, runtime, lifecycle, observability, security, supply chain
**Scope:** `node-api` + `file-api` scaffolds; any project that adopts Node. Research basis: [`docs/reference/research/Node Backend Practices Research 2026.md`](../../../docs/reference/research/Node%20Backend%20Practices%20Research%202026.md)

---

## Framework Selection

| Framework | Pick when | Throughput | Schema validation |
| --- | --- | --- | --- |
| **Fastify** | **Default for greenfield services.** | ~4× Express | Built-in JSON Schema (ajv) |
| **Express** | Legacy maintenance / extending existing scaffold | baseline | None (manual) |
| Hono / Elysia | **Banned for Fabrik VPS containers** — optimized for edge runtimes (Vercel/Cloudflare/Bun); thin plugin ecosystem for VPS Node | — | — |

- New services: Fastify — its plugin encapsulation isolates blast radius and the schema-first pattern eliminates a class of validation bugs.
- Existing Express scaffolds: stay on the major they run. Migration is owner-approved only.
- New Express code (extending an existing Express family): target npm `latest` — the current major has been the default install since 2025; the legacy major is maintenance-only. Legacy scaffolds must pin their major explicitly in `package.json` — a bare `npm i express` now installs the current major with its breaking changes.

## ESM is the default (not CommonJS)

- **Every greenfield package.json must declare `"type": "module"`.** CommonJS breaks tree-shaking, blocks top-level await, and is incompatible with the growing set of ESM-only packages (`chalk`, `execa`, …). Node TSC consensus: ESM is the definitive default.
- Use explicit `.js` extensions on all local imports: `import { util } from './util.js'` (NOT `'./util'`).
- Never mix `require()` and `import` in the same package — dual-package hazard.
- Existing CJS projects: stay CJS until a planned migration. Don't half-switch.

## Runtime + Docker

- **New services target the current Active LTS line** (`node:<!--v:node_lts-->24<!--/v-->`). The previous LTS line is maintenance-only — existing services may ride it to its EOL, new services never target it. `node-api` + `file-api` scaffolds declare the floor `engines.node: ">=<!--v:node_engines_floor-->22<!--/v-->.0.0"`.
- Base image: `node:<!--v:node_lts-->24<!--/v-->-<!--v:debian_codename-->trixie<!--/v-->-slim` (services pinned to the previous LTS keep their existing pin until EOL). **Alpine is banned fleet-wide** (musl-libc breaks native C++ bindings unpredictably).
- Dockerfile build step: `RUN npm ci --ignore-scripts` (NOT `npm install`).
  - `npm ci`: deterministic from lockfile.
  - `--ignore-scripts`: blocks install-script payloads — the dominant npm supply-chain vector (the Shai-Hulud worm class; the Mastra `easy-day-js` typosquat backdoored 140+ package versions via postinstall in under 90 minutes). npm's current major now blocks dependency install scripts by default; the explicit flag keeps builds safe on every npm version and in CI images that lag.
- If a dep genuinely needs its postinstall, run it explicitly + audited in a separate `RUN npm rebuild <pkg>` step.

## Configuration

- Every required env var validated at startup; throw BEFORE the server listens:

  ```js
  const REQUIRED = ['DATABASE_URL', 'REDIS_URL', 'SERVICE_INTERNAL_SECRET_KEY'];
  for (const k of REQUIRED) {
    if (!process.env[k]) throw new Error(`Missing required env: ${k}`);
  }
  ```

- **Never** `process.env.X || 'default'` for secrets/tokens/DSNs — silent defaults are the #1 source of "works locally, fails in prod".
- For complex config: Zod schema validation at boot, typed `config` object exported, never reach `process.env` from business code.

## Observability — pino + AsyncLocalStorage + GlitchTip + Prometheus

### Structured logging (pino)

> **12-Factor XI (Logs), verbatim:** *"each running process writes its event stream, unbuffered, to `stdout`"* — and *"A twelve-factor app never concerns itself with routing or storage of its output stream. It should not attempt to write to or manage logfiles."*
>
> **BANNED: any file transport.** `pino.destination('/path/app.log')`, `winston.transports.File`, `winston-daily-rotate-file`, `fs.createWriteStream` for logs, any `*.log` write, any in-app log rotation/retention. The app logs JSON to `stdout` and nothing else; **Docker → Promtail → Loki owns routing and retention.** Full rule: `55-observability.md` § Logs.

- Use `pino` for application logs; `pino-http` for request logs. NEVER `console.log` outside bootstrap (breaks Loki/Promtail parsing + wastes GlitchTip).
- **Mandatory redact paths** to prevent token leakage to Loki:

  ```js
  import pino from 'pino';
  export const logger = pino({
    level: process.env.LOG_LEVEL || 'info',
    redact: [
      'req.headers.authorization',
      'req.headers["x-internal-token"]',
      'req.body.password',
      'req.body.token',
      '*.access_token',
      '*.refresh_token',
    ],
  });
  ```

- Output is JSON to stdout — Promtail tails Docker logs → Loki.

### Correlation IDs via AsyncLocalStorage

- Use Node's built-in `AsyncLocalStorage` for ambient correlation context — the `AsyncContextFrame` implementation (default in current LTS) makes the overhead negligible. Banned: prop-drilling child loggers through business code.

  ```js
  import { AsyncLocalStorage } from 'node:async_hooks';
  import crypto from 'node:crypto';

  export const asyncCtx = new AsyncLocalStorage();

  // Middleware (Fastify hook or Express middleware):
  app.addHook('onRequest', (req, reply, done) => {
    asyncCtx.run({
      traceId: req.headers['x-request-id'] || crypto.randomUUID(),
    }, done);
  });

  // Anywhere in the request lifecycle:
  logger.info({ ...asyncCtx.getStore() }, 'processing');
  ```

### Error reporting → GlitchTip

- Initialize `@sentry/node` at process start with `dsn: process.env.GLITCHTIP_DSN`. The Sentry SDK is GlitchTip-compatible (no separate GlitchTip SDK exists).
- Unhandled errors auto-report. DO NOT also `logger.exception(e)` with full stack in production paths — duplicates the Loki record.
- Use `Sentry.captureException(e)` only for caught-then-rethrown control flow where you want explicit reporting.

### `/metrics` (Prometheus format)

- Required when `shape.exposes_metrics: true` in the spec. Use `prom-client`:

  ```js
  import client from 'prom-client';
  client.collectDefaultMetrics();
  app.get('/metrics', async (_, res) => {
    res.type(client.register.contentType);
    res.send(await client.register.metrics());
  });
  ```

## Graceful Shutdown (SIGTERM)

The drain sequence below is the only correct one. Skipping any step drops in-flight requests.

```js
let isShuttingDown = false;

// /health returns 503 the instant SIGTERM lands → Traefik removes the pod from rotation
app.get('/health', async (req, res) => {
  if (isShuttingDown) return res.status(503).json({ status: 'draining' });
  try {
    await db.query('SELECT 1');
    await redis.ping();
    res.json({ status: 'ok' });
  } catch (e) {
    res.status(503).json({ status: 'degraded', error: e.message });
  }
});

process.on('SIGTERM', async () => {
  isShuttingDown = true;
  // Hard exit if drain hangs (20s — must stay BELOW compose stop_grace_period, see note)
  setTimeout(() => process.exit(1), 20_000).unref();

  // 1. Stop accepting new connections + close idle keep-alives
  if (server.closeIdleConnections) server.closeIdleConnections();
  // 2. server.close() callback fires once active requests finish
  server.close(async () => {
    // 3. ONLY after HTTP is closed: tear down DB + Redis
    await Promise.all([pgPool.end(), redisClient.quit()]);
    process.exit(0);
  });
  // 4. Force-close remaining active connections after Traefik has had time to re-route
  setTimeout(() => server.closeAllConnections?.(), 5_000).unref();
});
```

- **The /health 503 flip BEFORE drain is non-negotiable.** Traefik must drop the node from rotation before `server.close()` starts refusing connections.
- **The 20s backstop only works because scaffold composes set `stop_grace_period: 45s`** — Docker's bare default grace is 10s, under which SIGKILL would win before the backstop fires. Manual composes MUST set `stop_grace_period` longer than the backstop.
- `server.closeIdleConnections()` + `server.closeAllConnections()` replace the legacy `server.close()`-callback-only drain that hangs indefinitely on upstream keep-alives.
- Teardown order: HTTP first, then DB/Redis. Reversing this loses in-flight queries.

## Security

**Run the current patch release of your LTS line.** The CVEs cited below were fixed in Node security releases — an unpatched runtime, not code style, is the primary exposure. The code rules below additionally remove the same bug classes from our own code.

### Helmet

- Apply globally; for pure JSON APIs (no HTML render path), disable CSP to skip needless processing:

  ```js
  import helmet from 'helmet';
  app.use(helmet({ contentSecurityPolicy: false }));
  ```

- HTML-serving services (admin UIs, error pages): leave CSP enabled, configure `directives:` explicitly.
- Fastify services use `@fastify/helmet` (same options, plugin-encapsulated).

### Token comparison

- Auth tokens, HMAC signatures, webhook secrets — **always** `crypto.timingSafeEqual(Buffer.from(a), Buffer.from(b))`. Never `==` or `===`. (The bug class Node itself shipped as CVE-2026-21713 — HMAC verification through a non-constant-time compare, a timing side channel leaking MAC values; the runtime fix is the patch floor above, this rule keeps the class out of OUR code.)

### Prototype pollution / CVE-2026-21710

- A crafted `__proto__` header name crashes an unpatched Node via `req.headersDistinct` (CVE-2026-21710 — uncaught TypeError, process-down DoS). Mitigation is the patched-runtime floor above. **Coding agents:** never read raw header maps without an explicit allowlist.

### TLS termination

- Always terminate TLS at Traefik, never in Node. CVE-2026-21637 (unhandled exception in the TLS SNI-callback path → remote DoS) is avoided entirely by Traefik handling TLS.

### `helmet` is not enough

- Bodies bounded: `app.use(express.json({ limit: '1mb' }))` or Fastify's `bodyLimit: 1_048_576`. Uncapped JSON parse is a DoS surface.
- CORS: explicit `origin:` array per environment. Never `cors({ origin: '*' })` on a service with auth.

## Streams + backpressure

- Always use `pipeline` from `node:stream/promises`:

  ```js
  import { pipeline } from 'node:stream/promises';
  await pipeline(readStream, transform, writeStream);
  ```

- Legacy `.pipe()` doesn't propagate errors or clean up on destination close — banned.
- Web Streams interop (e.g., OpenRouter SDK): `Readable.toWeb(nodeStream)` / `Readable.fromWeb(webStream)`.

## Concurrency

| Module | Verdict | Use case |
| --- | --- | --- |
| `worker_threads` | **Recommended for CPU-bound** | Crypto, image processing, JSON→CSV at scale, data parsing |
| `child_process` | **Situational** | Spawning isolated external binaries (e.g., `pdftotext`) |
| `cluster` | **BANNED** | Replaced by deploying multiple Docker container replicas behind Traefik. Cluster in a containerized environment doubles process count without observable scaling. |

For I/O parallelism the event loop is enough. For background jobs see `75-workers-jobs.md`.

## TypeScript

- **Local development: run `.ts` files directly — `node index.ts`.** Type stripping is stable and enabled by default in current Node; ts-node and tsx are obsolete for dev (opt-out flag `--no-experimental-strip-types` exists, never use it).
- **Production Docker build:** `esbuild` or `swc` for transpile (millisecond-fast). `tsc --noEmit` runs in CI for type-checking only — never as a build step.
- **Banned TS features (incompatible with native type stripping):** `enum`, `namespace`, parameter properties on constructors, JSX without explicit jsx pragma. These require runtime JS generation; erasable-syntax-only stripping refuses them.

## Testing

- **`vitest`** for all new test suites. ESM-native, materially faster feedback than Jest on modern codebases.
- **`node:test`** (built-in) for zero-dependency standalone scripts or health-check probes.
- Jest is acceptable only in legacy code paths.
- Integration tests hit a real Postgres per `45-testing-strategy.md` (mock DB banned).

## Turkish constraints

- LLM gateway: **OpenRouter only.** Never import vendor SDKs (`openai`, `@anthropic-ai/sdk`) directly. See `core/65-rag-search.md`.
- Payment processing: **iyzico** for TR domestic SaaS subscriptions; **Paddle Billing** (international MoR) for cross-border. PayTR applies only to WooCommerce / physical D2C (see `85-payments-billing.md:16`), not to Node SaaS backends. **Stripe is unavailable to a TR-resident LLC** — never wire the `stripe` npm SDK. Per-flow detail: `core/85-payments-billing.md`.

## M2M authentication — `X-Internal-Token` (Node implementation)

The Fabrik M2M pattern is canonical (see `core/35-security-auth.md` § Internal Service Auth). Python services use the scaffolded `internal_auth.py`; Node services replicate the same constant-time comparison:

```js
import crypto from 'node:crypto';

const SECRET = process.env.SERVICE_INTERNAL_SECRET_KEY;
if (!SECRET) throw new Error('Missing SERVICE_INTERNAL_SECRET_KEY');
const SECRET_BUF = Buffer.from(SECRET);

export function requireInternalToken(req, res, next) {
  const token = req.headers['x-internal-token'];
  if (!token) return res.status(401).json({ error: 'missing token' });

  const tokenBuf = Buffer.from(String(token));
  // Length check FIRST — timingSafeEqual throws on length mismatch
  if (tokenBuf.length !== SECRET_BUF.length ||
      !crypto.timingSafeEqual(tokenBuf, SECRET_BUF)) {
    return res.status(401).json({ error: 'invalid token' });
  }
  next();
}
```

- Never inline `APIKeyHeader` middleware patterns or per-service key names (`SERVICE_API_KEY`, `PROXY_API_KEY`) — single shared secret per-fleet.
- The same `SERVICE_INTERNAL_SECRET_KEY` env var is written by `deployer_ssh` into every deployed service's `.env` on the VPS.

---

## Banned Patterns

| Pattern | Use Instead | Reason |
| --- | --- | --- |
| `require('mod')` in new code | `import mod from 'mod'` | CommonJS breaks the ESM-only package set (chalk, execa, …) |
| `stream.pipe()` | `await pipeline(...)` from `node:stream/promises` | No error propagation, no cleanup on close |
| `req.headersDistinct['__proto__']` | patched runtime + allowlisted header reads | CVE-2026-21710 crafted-header process crash |
| `process.exit(1)` on SIGTERM | `server.closeAllConnections()` + DB drain | Drops in-flight requests, corrupts DB state |
| `ts-node` / `tsx` / `tsc` for build | run `.ts` natively (dev) / `esbuild`/`swc` (prod) | Type stripping is stable + default; tsc is type-check only |
| `helmet()` default on JSON APIs | `helmet({ contentSecurityPolicy: false })` | CSP overhead for non-HTML responses |
| `==` / `===` for token / signature comparison | `crypto.timingSafeEqual(Buffer.from(a), Buffer.from(b))` | Timing-leak CVE-2026-21713 |
| Passing pino child loggers through call stack | `AsyncLocalStorage` with ambient context | Prop-drilling clutters business logic |
| Custom TLS / SNI / `pskCallback` in Node | Traefik TLS termination | CVE-2026-21637 callback DoS |
| `cluster` module | Multiple Docker container replicas behind Traefik | Cluster adds OS-level process count without observable scaling in containers. **This is 12-Factor VIII (Concurrency): scale OUT via the process model, not up** |
| `pino.destination('*.log')` / `winston.transports.File` / any log file write or rotation | JSON → `stdout` only; Docker → Promtail → Loki routes | 12-Factor XI: the app must never write or manage a logfile |
| `npm install` in CI/Dockerfile | `npm ci --ignore-scripts` | Non-deterministic + install-script supply-chain risk (Shai-Hulud worm class) |
| `node_modules/` committed | `.gitignored`; `npm ci` rebuilds | Always |
| `console.log` in production paths | `pino` with structured fields | Breaks Loki query model + wastes GlitchTip |
| Alpine base image | the current-LTS `-slim` base per § Runtime + Docker | musl-libc compatibility issues with native modules |
| Buffered payload > 10 MB in memory | streamed via `pipeline()` | OOM on shared 12 GB VPS |
| `process.env.X \|\| 'default'` for secrets | Startup throw on missing | Silent prod misconfig |
| `npm install` of vendor SDK (`stripe`, `openai`, `@anthropic-ai/sdk`) | OpenRouter for LLM, PayTR/iyzico/Paddle for billing | TR entity rules; gateway abstraction rule |

---

## Related Rule Packs

- `20-typescript.md` — TS-specific patterns (auto-loads on `.ts`)
- `15-api-contracts.md` — request/response shape, error format, idempotency
- `25-data-postgres.md` — pgvector, pg pool, Docker network DNS (`postgres-main:5432`)
- `30-ops.md` — Dockerfile, Traefik labels, base images, network membership
- `35-security-auth.md` — Authelia, M2M `X-Internal-Token`, secrets policy
- `55-observability.md` — `/health` real-dep check, `/metrics` exposure, Gatus endpoint pattern
- `58-resilience.md` — timeout / retry / circuit breaker for external calls
- `65-rag-search.md` — OpenRouter LLM gateway (no vendor SDKs)
- `67-file-api.md` — file-handling discipline (companion pack for `file-api` scaffolds)
- `75-workers-jobs.md` — background processing
- `85-payments-billing.md` — Paddle / iyzico / PayTR; Stripe ban

---

## Done When

- [ ] `"type": "module"` in `package.json` (greenfield) OR documented decision to stay CJS.
- [ ] `engines.node` floor pinned per the scaffold; Dockerfile uses the current-LTS `-slim` base image per § Runtime + Docker and `30-ops.md`.
- [ ] `npm ci --ignore-scripts` in Dockerfile + CI (never `npm install`).
- [ ] `helmet({ contentSecurityPolicy: false })` for JSON-only APIs; explicit CSP for HTML responses.
- [ ] Required env vars validated at startup; no silent defaults for secrets (composes with `35-security-auth.md` § Secrets).
- [ ] `pino` with redact paths covering `authorization`, `x-internal-token`, password/token body fields (extends `55-observability.md` § Structured logging).
- [ ] `AsyncLocalStorage` carries `traceId` per request; logger pulls from ambient context.
- [ ] `@sentry/node` initialised with `GLITCHTIP_DSN` for unhandled errors.
- [ ] `/health` tests real deps (`SELECT 1`, `PING`) AND returns 503 when `isShuttingDown=true` (real-dep mandate per `55-observability.md`).
- [ ] `/metrics` mounted if `shape.exposes_metrics: true`.
- [ ] SIGTERM handler: 503 flip → `closeIdleConnections()` → `server.close()` → `pgPool.end()` + `redisClient.quit()` → 20s backstop.
- [ ] All async streams use `pipeline()` from `node:stream/promises`.
- [ ] No `cluster` usage (replicas via Docker Compose instead).
- [ ] M2M `X-Internal-Token` middleware uses `crypto.timingSafeEqual()` with length-check guard (canonical pattern per `35-security-auth.md`).
- [ ] All token/signature comparisons use `crypto.timingSafeEqual()`.
- [ ] TLS terminated at Traefik; no `pskCallback` / `ALPNCallback` / `SNICallback` in Node.
- [ ] TypeScript dev: `.ts` run natively via built-in type stripping; no `ts-node`/`tsx` in scripts (overlaps `20-typescript.md` prod-image ban).
- [ ] TypeScript prod build: `esbuild`/`swc`; `tsc --noEmit` only in CI.
- [ ] Tests: `vitest` (or `node:test` for stand-alone scripts); integration tests hit a real Postgres per `45-testing-strategy.md`.
- [ ] No vendor LLM SDK imports (OpenRouter only per `65-rag-search.md`); no Stripe SDK; iyzico for TR SaaS, Paddle for international (per `85-payments-billing.md`).
- [ ] `node_modules/` gitignored; `"private": true` in `package.json`.
