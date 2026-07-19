---
activation: glob
globs: ["**/*.js", "**/*.mjs", "**/*.cjs", "**/*.ts", "**/package.json", "**/package-lock.json"]
description: Node.js 22 production backend patterns (2026-current) — Fastify/Express, ESM, pino + ALS, graceful drain, npm hygiene, helmet, CVE-aware
trigger: glob
---
<!-- CONSUMER: Coding agents (Claude Code, Windsurf Cascade, Kilo CLI)
     GOAL: Node.js 22 backend service patterns for Fabrik VPS deployment — framework, runtime, observability, lifecycle, security, supply chain
     TRAYCER USAGE: Injects as Context File for tickets on node-api / file-api scaffolds or any .js/.ts backend.
     AGENT USAGE: Follow verbatim. Research basis: docs/reference/research/Node Backend Practices Research 2026.md (cited). -->

# Node.js Backend Rules (2026)

**Activation:** Glob `**/*.{js,mjs,cjs,ts}`, `**/package.json`, `**/package-lock.json`
**Purpose:** Node 22+/24 LTS production backend services on Fabrik's shared VPS fleet — framework, runtime, lifecycle, observability, security, supply chain
**Scope:** `node-api` + `file-api` scaffolds; any project that adopts Node. Research basis: [`docs/reference/research/Node Backend Practices Research 2026.md`](../../../docs/reference/research/Node%20Backend%20Practices%20Research%202026.md)

---

## Framework Selection

| Framework | Pick when | Throughput | Schema validation |
| --- | --- | --- | --- |
| **Fastify 5** | **Default for greenfield services.** | ~45k req/sec | Built-in JSON Schema (ajv) |
| **Express 4** | Legacy maintenance / extending existing scaffold | ~10k req/sec | None (manual) |
| Hono / Elysia | **Banned for Fabrik VPS containers** — optimized for edge runtimes (Vercel/Cloudflare/Bun); thin plugin ecosystem for VPS Node | — | — |

- New services: Fastify 5 — its plugin encapsulation isolates blast radius and the schema-first pattern eliminates a class of validation bugs.
- Existing Express 4 scaffolds: stay on Express 4. Migration is owner-approved only.
- Express 5: not yet auto-adoptable; evaluate per project once it stabilises post-2026.

## ESM is the default (not CommonJS)

- **Every greenfield package.json must declare `"type": "module"`.** CommonJS breaks tree-shaking, blocks top-level await, and is incompatible with key 2026 packages (e.g., `chalk` v5+, modern ESM-only libraries). Node TSC consensus: ESM is the definitive default.
- Use explicit `.js` extensions on all local imports: `import { util } from './util.js'` (NOT `'./util'`).
- Never mix `require()` and `import` in the same package — dual-package hazard.
- Existing CJS projects: stay CJS until a planned migration. Don't half-switch.

## Runtime + Docker

- **Node 22 LTS minimum; Node 24 LTS preferred for new services.** Both are active LTS (22 → Apr 2027; 24 → Apr 2028). New services should use the current LTS (24); the 22 floor exists so existing services don't have to upgrade. `node-api` + `file-api` scaffolds currently declare `engines.node: ">=22.0.0"`. `30-ops.md` carries the canonical `node:<current-LTS>-bookworm-slim` placeholder; other packs (`20-typescript.md`, `42-docusaurus.md`) use `node:24-bookworm-slim` in Dockerfile examples to reflect current LTS.
- Base image: `node:24-bookworm-slim` (or `node:22-bookworm-slim` if pinned to 22). **Alpine is banned fleet-wide** (musl-libc breaks native C++ bindings unpredictably).
- Dockerfile build step: `RUN npm ci --ignore-scripts` (NOT `npm install`).
  - `npm ci`: deterministic from lockfile.
  - `--ignore-scripts`: blocks malicious `postinstall` payloads. The 2026 Mastra `easy-day-js` typosquat attack backdoored 140+ packages via postinstall — this flag is now non-negotiable.
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

### Structured logging (pino v9+)

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

- Use Node 22's built-in `AsyncLocalStorage` for ambient correlation context (~7% overhead per Node 24 AsyncContextFrame benchmarks). Banned: prop-drilling child loggers through business code.

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
  // Hard exit if drain hangs (20s — matches Docker's default stop grace period)
  setTimeout(() => process.exit(1), 20_000).unref();

  // 1. Stop accepting new connections + close idle keep-alives
  if (server.closeIdleConnections) server.closeIdleConnections();   // Node 18+
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
- `server.closeIdleConnections()` (Node 18+) + `server.closeAllConnections()` (Node 18+) replace the legacy `server.close()` callback that hangs indefinitely on upstream keep-alives.
- Teardown order: HTTP first, then DB/Redis. Reversing this loses in-flight queries.

## Security

### Helmet 7+

- Apply globally; for pure JSON APIs (no HTML render path), disable CSP to skip needless processing:

  ```js
  import helmet from 'helmet';
  app.use(helmet({ contentSecurityPolicy: false }));
  ```

- HTML-serving services (admin UIs, error pages): leave CSP enabled, configure `directives:` explicitly.

### Token comparison

- Auth tokens, HMAC signatures, webhook secrets — **always** `crypto.timingSafeEqual(Buffer.from(a), Buffer.from(b))`. Never `==` or `===`. (CVE-2026-21713 — equality-comparison timing leak enabling signature forgery.)

### Prototype pollution / CVE-2026-21710

- `req.headersDistinct['__proto__']` crashes Node via prototype pollution. Mitigation lives at the proxy: Traefik strips `__proto__` headers before they reach Node. **Coding agents:** never read raw header maps without explicit allowlist.

### TLS termination

- Always terminate TLS at Traefik, never in Node. CVE-2026-21637 (TLS `pskCallback` / `ALPNCallback` DoS) is avoided entirely by Traefik handling SNI.

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

- **Local development:** `node --experimental-strip-types index.ts`. Node 22.18+ strips type annotations natively; ts-node and tsx are obsolete for dev.
- **Production Docker build:** `esbuild` or `swc` for transpile (millisecond-fast). `tsc --noEmit` runs in CI for type-checking only — never as a build step.
- **Banned TS features (incompatible with native strip-types):** `enum`, `namespace`, parameter properties on constructors, JSX without explicit jsx pragma. These require runtime JS generation; native strip-types refuses them.

## Testing

- **`vitest`** for all new test suites. ESM-native, ~20x faster feedback than Jest on modern codebases.
- **`node:test`** (built-in since Node 20) for zero-dependency standalone scripts or health-check probes.
- Jest is acceptable only in legacy code paths.
- Integration tests hit a real Postgres per `45-testing-strategy.md` (mock DB banned).

## Turkish constraints

- LLM gateway: **OpenRouter only.** Never import vendor SDKs (`openai`, `@anthropic-ai/sdk`) directly. See `core/65-rag-search.md`.
- Payment processing: **iyzico** for TR domestic SaaS subscriptions; **Paddle Billing v2** (international MoR) for cross-border. PayTR applies only to WooCommerce / physical D2C (see `85-payments-billing.md:16`), not to Node SaaS backends. **Stripe is unavailable to a TR-resident LLC** — never wire `@stripe/stripe-node`. Per-flow detail: `core/85-payments-billing.md`.

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
| `require('mod')` in new code | `import mod from 'mod'` | CommonJS breaks 2026 ESM-only packages (chalk v5+, etc.) |
| `stream.pipe()` | `await pipeline(...)` from `node:stream/promises` | No error propagation, no cleanup on close |
| `req.headersDistinct['__proto__']` | Traefik filtering + allowlisted header reads | CVE-2026-21710 prototype-pollution crash |
| `process.exit(1)` on SIGTERM | `server.closeAllConnections()` + DB drain | Drops in-flight requests, corrupts DB state |
| `ts-node` / `tsx` / `tsc` for build | `node --experimental-strip-types` (dev) / `esbuild`/`swc` (prod) | Modern AST transformers are ms-fast; tsc is type-check only |
| `helmet()` default on JSON APIs | `helmet({ contentSecurityPolicy: false })` | CSP overhead for non-HTML responses |
| `==` / `===` for token / signature comparison | `crypto.timingSafeEqual(Buffer.from(a), Buffer.from(b))` | Timing-leak CVE-2026-21713 |
| Passing pino child loggers through call stack | `AsyncLocalStorage` with ambient context | Prop-drilling clutters business logic |
| Custom TLS / SNI / `pskCallback` in Node | Traefik TLS termination | CVE-2026-21637 callback DoS |
| `cluster` module | Multiple Docker container replicas behind Traefik | Cluster adds OS-level process count without observable scaling in containers. **This is 12-Factor VIII (Concurrency): scale OUT via the process model, not up** |
| `pino.destination('*.log')` / `winston.transports.File` / any log file write or rotation | JSON → `stdout` only; Docker → Promtail → Loki routes | 12-Factor XI: the app must never write or manage a logfile |
| `npm install` in CI/Dockerfile | `npm ci --ignore-scripts` | Non-deterministic + postinstall supply-chain risk (Mastra `easy-day-js` 2026) |
| `node_modules/` committed | `.gitignored`; `npm ci` rebuilds | Always |
| `console.log` in production paths | `pino` with structured fields | Breaks Loki query model + wastes GlitchTip |
| Alpine base image | `node:24-bookworm-slim` (or `node:22` for 22-pinned) | musl-libc compatibility issues with native modules |
| Buffered payload > 10 MB in memory | streamed via `pipeline()` | OOM on shared 12 GB VPS |
| `process.env.X \|\| 'default'` for secrets | Startup throw on missing | Silent prod misconfig |
| `npm install` of vendor SDK (`@stripe/stripe-node`, `openai`, `@anthropic-ai/sdk`) | OpenRouter for LLM, PayTR/iyzico/Paddle for billing | TR entity rules; gateway abstraction rule |

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
- [ ] Node 22+ pinned in `engines.node` (24+ preferred); Dockerfile uses `node:<current-LTS>-bookworm-slim` per `30-ops.md` base-image rule.
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
- [ ] TypeScript dev: `node --experimental-strip-types`; no `ts-node`/`tsx` in scripts (overlaps `20-typescript.md` prod-image ban).
- [ ] TypeScript prod build: `esbuild`/`swc`; `tsc --noEmit` only in CI.
- [ ] Tests: `vitest` (or `node:test` for stand-alone scripts); integration tests hit a real Postgres per `45-testing-strategy.md`.
- [ ] No vendor LLM SDK imports (OpenRouter only per `65-rag-search.md`); no Stripe SDK; iyzico for TR SaaS, Paddle for international (per `85-payments-billing.md`).
- [ ] `node_modules/` gitignored; `"private": true` in `package.json`.
