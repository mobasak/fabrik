# **Node.js 22 Production Backend Rules (2026)**

## **1\. Framework Selection: Express 4 vs Fastify vs Hono**

* Maintain Express 4 strictly for legacy scaffolding extensions to avoid unnecessary migration costs1. Why: The Express middleware ecosystem remains the largest, but its synchronous middleware stack and lack of connection multiplexing create bottlenecks under heavy database I/O1.
* Adopt Fastify 5 for all greenfield microservices3. Why: Fastify delivers up to 3x higher throughput (\~45k req/sec) through aggressive JSON schema serialization, making it ideal for a strictly constrained 12 GB shared VPS2.
* Reject Hono and Elysia for Node.js VPS container workloads1. Why: Hono is optimized for Vercel/Cloudflare edge runtimes with minimal cold starts, while Elysia relies on Bun's architecture; neither provides the deep plugin ecosystem necessary for standard Node.js deployments1.

| Framework | 2026 Primary Use Case | Node 22 Throughput | Schema Validation | Architecture |
| :---- | :---- | :---- | :---- | :---- |
| **Express 4** | Legacy maintenance | \~10k req/sec | None (Manual) | Global Middleware2 |
| **Fastify 5** | New VPS Microservices | \~45k req/sec | Built-in (JSON Schema) | Encapsulated Plugins2 |
| **Hono 4** | Edge/Serverless deployments | \~25k req/sec | Middleware (Zod) | Chain Inference2 |

## **2\. ESM vs CommonJS in 2026**

* Enforce "type": "module" in package.json for all services5. Why: CommonJS is synchronous and breaks tree-shaking; the Node TSC consensus now treats ESM as the definitive default5.
* Append explicit file extensions (e.g., import { util } from './util.js') for all local imports6.
* Avoid dual-package hazards by sticking purely to ESM; do not mix require() and import6.

## **3\. Pino Patterns & Observability (v9+)**

* Initialize pino with pino-http to output structured JSON to stdout, allowing Promtail to ingest logs into Loki8.
* Configure redact: \['req.headers.authorization', 'req.headers\["x-internal-token"\]', 'password'\] at the transport level9. Why: Explicit redaction prevents Supabase JWTs and M2M tokens from leaking into Loki and violating security policies8.
* Route unhandled errors and critical application failures to GlitchTip via the Sentry Node SDK (@sentry/node)11.
* Expose a /metrics endpoint serving prom-client default metrics in Prometheus format12.

JavaScript
import pino from 'pino';
import \* as Sentry from '@sentry/node';
Sentry.init({ dsn: process.env.GLITCHTIP\_DSN });
export const logger \= pino({
  level: process.env.LOG\_LEVEL || 'info',
  redact: \['req.headers.authorization', 'req.headers\["x-internal-token"\]'\]
});

## **4\. Context Propagation (AsyncLocalStorage)**

* Instantiate AsyncLocalStorage to inject x-correlation-id into all logs13. Why: ALS utilizes Node 24/22's AsyncContextFrame, allowing correlation IDs to automatically propagate across async boundaries with a negligible \~7% overhead, eliminating the need to prop-drill Pino child loggers13.

JavaScript
import { AsyncLocalStorage } from 'node:async\_hooks';
export const asyncCtx \= new AsyncLocalStorage();
// Middleware usage:
asyncCtx.run({ traceId: req.headers\['x-request-id'\] || crypto.randomUUID() }, () \=\> next());

## **5\. Graceful Shutdown & Lifecycle**

* Intercept Docker's SIGTERM signal to trigger a controlled drainage procedure16.
* Instantly return 503 Service Unavailable on /health upon receiving SIGTERM17. Why: Traefik must actively drop the node from its routing pool before the server stops accepting connections to prevent dropped requests17.
* Execute server.closeIdleConnections() and server.closeAllConnections() for Node 18+ immediately after health check flip19. Why: Legacy server.close() hangs indefinitely if upstream keep-alive connections are maintained19.
* Teardown shared resources (Postgres, Redis) strictly *after* the HTTP server confirms closure, enforcing a 20-second hard exit timeout18.

JavaScript
process.on('SIGTERM', async () \=\> {
  isShuttingDown \= true; // /health now returns 503
  setTimeout(() \=\> process.exit(1), 20000).unref();
  if (server.closeIdleConnections) server.closeIdleConnections();
  server.close(async () \=\> {
    await Promise.all(\[pgPool.end(), redisClient.quit()\]);
    process.exit(0);
  });
});

## **6\. npm Hygiene & Supply Chain Security**

* Define the Docker base strictly as FROM node:22-bookworm-slim; strictly avoid Alpine due to unpredictable musl-libc compatibility issues with native C++ bindings.
* Execute npm ci \--ignore-scripts in the Dockerfile24. Why: Prevents malicious postinstall scripts (such as the 2026 Mastra easy-day-js attack) from exfiltrating environment variables or executing payloads during the CI/CD build phase25.
* Integrate npm audit into the CI pipeline to fail builds on High/Critical vulnerabilities26.

## **7\. Security Headers (Helmet 7+)**

* Implement helmet() middleware globally28.
* Pass helmet({ contentSecurityPolicy: false }) for pure JSON APIs30. Why: CSP mitigates XSS by restricting executable scripts in HTML documents, adding unnecessary processing overhead for headless backend services that return no HTML31.
* Ensure Traefik drops the \_\_proto\_\_ header before it reaches Node.js33. Why: Mitigates CVE-2026-21710 where req.headersDistinct crashes the process due to prototype pollution33.

## **8\. Streams & Backpressure**

* Import pipeline from node:stream/promises for all stream operations35. Why: The legacy .pipe() method fails to automatically propagate errors or clean up memory when a destination closes prematurely35.
* Bridge Node.js streams to the Web Streams API using Readable.toWeb() when interacting with modern APIs (e.g., OpenRouter SDKs)37.

## **9\. Concurrency Models**

| Module | 2026 Best Practice | Use Case |
| :---- | :---- | :---- |
| worker\_threads | **Recommended** | Offloading heavy cryptography, image processing, or data parsing39. |
| child\_process | **Situational** | Invoking external system binaries requiring isolated memory39. |
| cluster | **Banned** | Replaced by deploying multiple Docker container replicas behind Traefik39. |

## **10\. TypeScript Strategy**

* Execute local development scripts using node \--experimental-strip-types41. Why: Node 22.18+ natively strips TypeScript type annotations, eliminating the need for ts-node or tsx during local execution41.
* Prohibit the use of TypeScript enum and namespace41. Why: Native type stripping cannot execute TypeScript features that require generating new JavaScript runtime code42.
* Transpile production Docker builds using esbuild or swc, retaining tsc \--noEmit solely for CI type-checking44.

## **11\. Testing Ecosystem**

* Adopt vitest for all comprehensive testing suites46. Why: Vitest natively understands ESM and Vite tooling, providing up to 20x faster feedback loops than Jest on modern codebases46.
* Utilize the native node:test module for isolated scripts or zero-dependency health checks48.

## **12\. Turkish Ecosystem Constraints (Payments & LLMs)**

* Route all LLM gateway calls exclusively through OpenRouter.
* Implement PayTR or Iyzico Node.js SDKs for transaction processing; completely avoid Stripe SDK implementations49. *Why: The operating LLC is based in Türkiye, where Stripe is not legally available to resident entities.*

## **Banned Patterns**

| Pattern | Use Instead | Reason |
| :---- | :---- | :---- |
| require('module') | import mod from 'module' | CommonJS breaks with modern 2026 ecosystem packages (e.g., chalk v5)5. |
| stream.pipe() | await pipeline(a, b, c) | .pipe() does not handle error propagation or automatic cleanup35. |
| req.headersDistinct\['\_\_proto\_\_'\] | WAF/Traefik filtering | Triggers synchronous unhandled TypeError crashing the app (CVE-2026-21710)33. |
| process.exit(1) on SIGTERM | server.closeAllConnections() | Dropping connections mid-flight corrupts database states and client flows16. |
| ts-node / tsc for build | esbuild or swc | Modern AST transformers are milliseconds fast; tsc is only for typechecking45. |
| helmet default on APIs | helmet({ contentSecurityPolicy: false }) | CSP adds unnecessary processing overhead for headless JSON APIs30. |
| \== for token checks | crypto.timingSafeEqual(a, b) | Standard equality operators leak timing data, leading to signature forgery (CVE-2026-21713)27. |
| Passing child loggers | AsyncLocalStorage | Prop-drilling clutters business logic; ALS provides ambient context natively13. |
| Uncaught TLS callbacks | Traefik TLS Termination | Node.js TLS SNICallback crashes (CVE-2026-21637) are avoided by terminating TLS at the proxy53. |

## **Related Rule Packs**

* .windsurf/rules/core/13-docker-vps.md (Traefik, shared 12 GB limits, container definitions)
* .windsurf/rules/core/14-postgres-redis.md (Database pooling, Docker network DNS)

## **Done When**

* \[ \] No CommonJS require statements exist in application code.
* \[ \] Application successfully parses and type-strips using node \--experimental-strip-types locally.
* \[ \] SIGTERM triggers a structured graceful drain, terminating server, Postgres, and Redis within 20 seconds.
* \[ \] pino outputs structured JSON, and sensitive headers/tokens are explicitly redacted.
* \[ \] The /health endpoint dynamically tests postgres-main:5432 and redis-main:6379, returning 503 during teardown.
* \[ \] The /metrics endpoint exposes Prometheus data.
* \[ \] GlitchTip (Sentry) integration is active for unhandled errors.
* \[ \] Dockerfile uses node:22-bookworm-slim and npm ci \--ignore-scripts.

#### **Works cited**

1. Hono vs Express vs Fastify vs Elysia — 2026 Node.js/Bun Framework Comparison Guide | Oflight Inc. \- 株式会社オブライト, [https://www.oflight.co.jp/en/columns/hono-vs-express-fastify-elysia-comparison-2026](https://www.oflight.co.jp/en/columns/hono-vs-express-fastify-elysia-comparison-2026)
2. Hono vs Express vs Fastify vs Elysia 2026 — PkgPulse Guides, [https://www.pkgpulse.com/guides/hono-vs-express-vs-fastify-vs-elysia-2026](https://www.pkgpulse.com/guides/hono-vs-express-vs-fastify-vs-elysia-2026)
3. NestJS vs Fastify vs Hono: The 2026 Node.js Comparison \- Encore Cloud, [https://encore.dev/articles/nestjs-vs-fastify-vs-hono](https://encore.dev/articles/nestjs-vs-fastify-vs-hono)
4. Fastify vs Express vs Hono \- Node.js Frameworks | Better Stack Community, [https://betterstack.com/community/guides/scaling-nodejs/fastify-vs-express-vs-hono/](https://betterstack.com/community/guides/scaling-nodejs/fastify-vs-express-vs-hono/)
5. Node.js ES Modules vs CommonJS: Migration Guide 2026 \- jsmanifest, [https://jsmanifest.com/nodejs-esm-commonjs-migration-2026](https://jsmanifest.com/nodejs-esm-commonjs-migration-2026)
6. ESM vs CJS — Why Your import Still Breaks in 2026 and How to Finally Fix It, [https://sandeepbansod.medium.com/esm-vs-cjs-why-your-import-still-breaks-in-2026-and-how-to-finally-fix-it-9a16c318a291](https://sandeepbansod.medium.com/esm-vs-cjs-why-your-import-still-breaks-in-2026-and-how-to-finally-fix-it-9a16c318a291)
7. JavaScript Modules: The 2026 Guide (ESM vs CommonJS) \- DEV Community, [https://dev.to/armorbreak/javascript-modules-the-2026-guide-esm-vs-commonjs-21fn](https://dev.to/armorbreak/javascript-modules-the-2026-guide-esm-vs-commonjs-21fn)
8. Pino Logger: Node.js Logging Guide & Best Practices | SigNoz, [https://signoz.io/guides/pino-logger-nodejs-logging-library/](https://signoz.io/guides/pino-logger-nodejs-logging-library/)
9. pino/docs/redaction.md at main · pinojs/pino \- GitHub, [https://github.com/pinojs/pino/blob/main/docs/redaction.md](https://github.com/pinojs/pino/blob/main/docs/redaction.md)
10. Production Logging in Node.js with Pino.js — A Complete Guide | by Nannuri Manoj, [https://medium.com/@nannurimanoj26/production-logging-in-node-js-with-pino-js-a-complete-guide-b69f5576603b](https://medium.com/@nannurimanoj26/production-logging-in-node-js-with-pino-js-a-complete-guide-b69f5576603b)
11. Support \`pino\` for Sentry Structured Logs · Issue \#15952 \- GitHub, [https://github.com/getsentry/sentry-javascript/issues/15952](https://github.com/getsentry/sentry-javascript/issues/15952)
12. Node.js Application Servers in 2026: Express, Fastify, Hono, and Modern Alternatives Compared \- DeployHQ, [https://www.deployhq.com/blog/node-application-servers-in-2025-from-express-to-modern-solutions](https://www.deployhq.com/blog/node-application-servers-in-2025-from-express-to-modern-solutions)
13. AsyncLocalStorage in Node.js 24 — What it is, why it matters, and how to use it in production, [https://www.usamaamjid.com/blog/async-local-storage-nodejs-24](https://www.usamaamjid.com/blog/async-local-storage-nodejs-24)
14. Zero-Boilerplate Request ID Tracing in Node.js with pino-correlation-id \- DEV Community, [https://dev.to/axiom\_agent/zero-boilerplate-request-id-tracing-in-nodejs-with-pino-correlation-id-3lob](https://dev.to/axiom_agent/zero-boilerplate-request-id-tracing-in-nodejs-with-pino-correlation-id-3lob)
15. The Hidden Cost of Async Context in Node.js \- Platformatic Blog, [https://blog.platformatic.dev/the-hidden-cost-of-context](https://blog.platformatic.dev/the-hidden-cost-of-context)
16. After building 30+ Node.js microservices, here are the mistakes I wish I'd learned earlier, [https://www.reddit.com/r/node/comments/1rhssnj/after\_building\_30\_nodejs\_microservices\_here\_are/](https://www.reddit.com/r/node/comments/1rhssnj/after_building_30_nodejs_microservices_here_are/)
17. How to Create Scale-Down Policies \- OneUptime, [https://oneuptime.com/blog/post/2026-01-30-scale-down-policies/view](https://oneuptime.com/blog/post/2026-01-30-scale-down-policies/view)
18. I did a deep dive into graceful shutdowns in node.js express since everyone keeps asking this once a week. Here's what I found... \- Reddit, [https://www.reddit.com/r/node/comments/1qz7htp/i\_did\_a\_deep\_dive\_into\_graceful\_shutdowns\_in/](https://www.reddit.com/r/node/comments/1qz7htp/i_did_a_deep_dive_into_graceful_shutdowns_in/)
19. Why is server.close callback never invoked? \- node.js \- Stack Overflow, [https://stackoverflow.com/questions/28053659/why-is-server-close-callback-never-invoked](https://stackoverflow.com/questions/28053659/why-is-server-close-callback-never-invoked)
20. HTTPS | Node.js v26.3.0 Documentation, [https://nodejs.org/api/https.html](https://nodejs.org/api/https.html)
21. How to properly close Node.js Express server? \- Stack Overflow, [https://stackoverflow.com/questions/14515954/how-to-properly-close-node-js-express-server](https://stackoverflow.com/questions/14515954/how-to-properly-close-node-js-express-server)
22. Graceful Shutdown in Node.js Applications \- Library \- Grizzly Peak Software, [https://www.grizzlypeaksoftware.com/library/graceful-shutdown-in-nodejs-applications-4rmcu5d5](https://www.grizzlypeaksoftware.com/library/graceful-shutdown-in-nodejs-applications-4rmcu5d5)
23. How to Configure SDK Shutdown Procedures in Node.js with SIGTERM \- OneUptime, [https://oneuptime.com/blog/post/2026-02-06-otel-sdk-shutdown-nodejs-kubernetes/view](https://oneuptime.com/blog/post/2026-02-06-otel-sdk-shutdown-nodejs-kubernetes/view)
24. lirantal/awesome-nodejs-security: Awesome Node.js Security resources \- GitHub, [https://github.com/lirantal/awesome-nodejs-security](https://github.com/lirantal/awesome-nodejs-security)
25. Mastra npm Supply Chain Attack: 140+ Packages Backdoored via easy-day-js Typosquat, [https://www.stepsecurity.io/blog/mastra-npm-packages-compromised-using-easy-day-js](https://www.stepsecurity.io/blog/mastra-npm-packages-compromised-using-easy-day-js)
26. Node.js Vulnerabilities: Top Risks & How to Secure Apps In 2026, [https://tuxcare.com/blog/node-js-vulnerabilities/](https://tuxcare.com/blog/node-js-vulnerabilities/)
27. Building authentication in Node.js applications: The complete guide for 2026 \- WorkOS, [https://workos.com/blog/nodejs-authentication-guide-2026](https://workos.com/blog/nodejs-authentication-guide-2026)
28. Production Best Practices: Security \- Express.js, [https://expressjs.com/en/advanced/best-practice-security/](https://expressjs.com/en/advanced/best-practice-security/)
29. Using Helmet in Node.js to secure your application \- LogRocket Blog, [https://blog.logrocket.com/using-helmet-node-js-secure-application/](https://blog.logrocket.com/using-helmet-node-js-secure-application/)
30. GitHub \- helmetjs/helmet: Help secure Express apps with various HTTP headers, [https://github.com/helmetjs/helmet](https://github.com/helmetjs/helmet)
31. Securing Your Node.js API Backend Services with Helmet | KTree, [https://ktree.com/blog/securing-your-node-js-api-backend-services-with-helmet.html](https://ktree.com/blog/securing-your-node-js-api-backend-services-with-helmet.html)
32. API with NestJS \#145. Securing applications with Helmet \- Marcin Wanago Blog, [https://wanago.io/2024/02/12/api-nestjs-helmet-security/](https://wanago.io/2024/02/12/api-nestjs-helmet-security/)
33. CVE-2026-21710: Node.js HTTP DOS Vulnerability \- SentinelOne, [https://www.sentinelone.com/vulnerability-database/cve-2026-21710/](https://www.sentinelone.com/vulnerability-database/cve-2026-21710/)
34. \[Vulnerability\] nodejs/node: Multiple: Timing Attack, Prototype Pollution, Permission Bypass, DoS, TLS Error Handling \#108 \- GitHub, [https://github.com/spaceraccoon/vulnerability-spoiler-alert/issues/108](https://github.com/spaceraccoon/vulnerability-spoiler-alert/issues/108)
35. Stream | Node.js v26.3.0 Documentation, [https://nodejs.org/api/stream.html](https://nodejs.org/api/stream.html)
36. Understanding Node.js Streams, [https://www.dennisokeeffe.com/blog/2024-07-05-understanding-nodejs-streams](https://www.dennisokeeffe.com/blog/2024-07-05-understanding-nodejs-streams)
37. Bun vs Node: 7 edge cases that surprise HTTP code | by Quaxel \- Medium, [https://medium.com/@Quaxel/bun-vs-node-7-edge-cases-that-surprise-http-code-7fe818c3adaa](https://medium.com/@Quaxel/bun-vs-node-7-edge-cases-that-surprise-http-code-7fe818c3adaa)
38. Web Streams API | Node.js 24.14.1 Documentation, [https://beta.docs.nodejs.org/webstreams.html](https://beta.docs.nodejs.org/webstreams.html)
39. Node.js Is Not Single-Threaded: Unleashing Multi-Core Power in 2024 \- Medium, [https://medium.com/@hiadeveloper/node-js-is-not-single-threaded-unleashing-multi-core-power-in-2024-f117677b3c3b](https://medium.com/@hiadeveloper/node-js-is-not-single-threaded-unleashing-multi-core-power-in-2024-f117677b3c3b)
40. Top NodeJs Interview Questions and Answers for Experienced Developers. \- Medium, [https://medium.com/@rvislive/top-nodejs-interview-questions-and-answers-for-experienced-developers-05c03b05d7bc](https://medium.com/@rvislive/top-nodejs-interview-questions-and-answers-for-experienced-developers-05c03b05d7bc)
41. Node.js v23 Natively Supports TypeScript | by Mingxuan Wang | Medium, [https://medium.com/@lennondotw/node-js-v23-natively-supports-typescript-65ae8932d4f5](https://medium.com/@lennondotw/node-js-v23-natively-supports-typescript-65ae8932d4f5)
42. Running TypeScript Natively | Node.js Learn, [https://nodejs.org/learn/typescript/run-natively](https://nodejs.org/learn/typescript/run-natively)
43. Documentation \- TypeScript 5.8, [https://www.typescriptlang.org/docs/handbook/release-notes/typescript-5-8.html](https://www.typescriptlang.org/docs/handbook/release-notes/typescript-5-8.html)
44. TypeScript vs JavaScript in 2026: Which Should You Use? \- Groovy Web, [https://www.groovyweb.co/blog/typescript-vs-javascript-comparison-2026](https://www.groovyweb.co/blog/typescript-vs-javascript-comparison-2026)
45. JavaScript Build Tools Comparison 2026: Vite vs Webpack vs esbuild \- Reintech, [https://reintech.io/blog/javascript-build-tools-comparison-2026](https://reintech.io/blog/javascript-build-tools-comparison-2026)
46. Testing in 2026: Jest, React Testing Library, and Full Stack Testing Strategies, [https://www.nucamp.co/blog/testing-in-2026-jest-react-testing-library-and-full-stack-testing-strategies](https://www.nucamp.co/blog/testing-in-2026-jest-react-testing-library-and-full-stack-testing-strategies)
47. Testing \- State of JavaScript 2025, [https://2025.stateofjs.com/en-US/libraries/testing/](https://2025.stateofjs.com/en-US/libraries/testing/)
48. Bun vs Node.js in 2026: Performance Benchmarks, Features, & Migration Guide \- Strapi, [https://strapi.io/blog/bun-vs-nodejs-performance-comparison-guide](https://strapi.io/blog/bun-vs-nodejs-performance-comparison-guide)
49. Node.js API Best Practices in 2026 \- OpenReplay Blog, [https://blog.openreplay.com/nodejs-api-best-practices-2026/](https://blog.openreplay.com/nodejs-api-best-practices-2026/)
50. paytr · GitHub Topics, [https://github.com/topics/paytr](https://github.com/topics/paytr)
51. The State of TypeScript Tooling in 2026 \- PkgPulse, [https://www.pkgpulse.com/guides/state-of-typescript-tooling-2026](https://www.pkgpulse.com/guides/state-of-typescript-tooling-2026)
52. Node.js Security Bulletin: CVE-2026-21637 and Other Fixes Explained | SecPod, [https://www.secpod.com/blog/node-js-security-bulletin-cve-2026-21637-and-other-fixes-explained](https://www.secpod.com/blog/node-js-security-bulletin-cve-2026-21637-and-other-fixes-explained)
53. March 2026 Node.js Security Release: Eight CVEs Patched, Including Two High-Severity Process Crashes \- HeroDevs, [https://www.herodevs.com/blog-posts/march-2026-node-js-security-release-eight-cves-patched-including-two-high-severity-process-crashes](https://www.herodevs.com/blog-posts/march-2026-node-js-security-release-eight-cves-patched-including-two-high-severity-process-crashes)
54. CVE-2026-21637 Node.js TLS Callback DoS: pskCallback and ALPNCallback Fixes, [https://windowsforum.com/threads/cve-2026-21637-node-js-tls-callback-dos-pskcallback-and-alpncallback-fixes.412918/](https://windowsforum.com/threads/cve-2026-21637-node-js-tls-callback-dos-pskcallback-and-alpncallback-fixes.412918/)
