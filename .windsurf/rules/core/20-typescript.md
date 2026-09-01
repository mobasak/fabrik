---
activation: glob
globs: ["**/*.ts", "**/*.tsx"]
description: TypeScript language discipline — strict mode, type safety, module patterns, error handling
trigger: glob
---
<!-- CONSUMER: Coding agents (Claude Code + dispatched subagents)
     GOAL: TypeScript language discipline — strict mode, type safety, module patterns, logging, Docker
     TRAYCER USAGE: Injects as Context File in tickets touching TypeScript code.
     AGENT USAGE: Follow verbatim when writing TypeScript. Activated by glob on *.ts/*.tsx files. -->

# TypeScript Core Rules

Apply when working on any TypeScript project (Next.js, Node.js, Chrome Extension, Desktop, Mobile, Static Site). Skip for Python-only or infrastructure files. For React/UI-specific guidance, see `saas/60-saas-ui.md`. For API error schemas, see `15-api-contracts.md`.

**Compiler currency:** the current `typescript` package ships the native compiler as `tsc` (order-of-magnitude faster builds, same syntax and flags — `tsc --noEmit` works verbatim). Toolchains that need the compiler's programmatic API (typescript-eslint, framework plugins) may pin the previous major until the API port lands.

---

## Strict Mode

All TypeScript projects must use strict compiler settings:

```json
{
  "compilerOptions": {
    "strict": true,
    "noUncheckedIndexedAccess": true,
    "noImplicitOverride": true,
    "verbatimModuleSyntax": true,
    "erasableSyntaxOnly": true
  }
}
```

Never loosen `strict` mode. If a library lacks types, write a `.d.ts` declaration file rather than using `any`.

`erasableSyntaxOnly` + `verbatimModuleSyntax` are Node's own recommended settings for natively-run TypeScript: they turn `12-node.md` § TypeScript's prose ban (`enum`, `namespace` with runtime code, constructor parameter properties — ALL of them, not just numeric enums) into a compiler error instead of a runtime surprise at `node index.ts`.

---

## Type Safety

- Prefer `interface` for object shapes that may be extended; use `type` for unions, intersections, and mapped types.
- Use `unknown` instead of `any` for values of uncertain type. Narrow with type guards before use.
- Use `as const` for literal objects and arrays that should not be widened.
- Use discriminated unions for state machines and variant types.

```typescript
// CORRECT — discriminated union
type Result<T> =
  | { ok: true; data: T }
  | { ok: false; error: Error };

// WRONG — loose typing
type Result = { data?: any; error?: string };
```

- Export types alongside their functions. Consumers should not need to reverse-engineer types from implementation.

---

## Environment Variables

Parse and validate environment variables **once at boot** via a typed Zod schema — the TypeScript analog to Python's Pydantic `BaseSettings`. Never scatter raw `process.env.X` access across the codebase.

```typescript
// src/env.ts — parse & validate once, import the typed object everywhere
import { z } from 'zod';

const env = z.object({
  DATABASE_URL: z.string(),                             // required — full URL from compose/env
  REDIS_URL: z.string().default('redis://redis-main:6379/0'),
  PORT: z.coerce.number().default(3000),
  SERVICE_INTERNAL_SECRET_KEY: z.string().min(1),
}).parse(process.env);

export default env;
// env.PORT is typed `number`, validated, not scattered
```

```typescript
// Usage — import the validated object, never raw process.env
import env from '@/env';
// DATABASE_URL is the full connection string (same convention as 10-python / 30-ops)
```

**CRITICAL:** Default DB host is `postgres-main`, not `localhost`. Default Redis host is `redis-main`. `localhost` inside a container points to the container itself, not the shared database.

For Next.js projects, prefix client-exposed variables with `NEXT_PUBLIC_`. Server-only variables must not use this prefix.

---

## Module Patterns

- Use ES module syntax (`import`/`export`). CommonJS `require()` is banned in new code.
- Use path aliases (`@/`) configured via `paths` in `tsconfig.json` to avoid deep relative imports — WITHOUT `baseUrl`, which is a hard error in the current TS major (`paths` works standalone with relative mappings).
- Barrel files (`index.ts`) are permitted for public API boundaries only — not for every directory.

```typescript
// CORRECT — path alias
import { formatDate } from '@/utils/date';

// WRONG — deep relative
import { formatDate } from '../../../utils/date';
```

---

## Error Handling

- Never swallow errors silently. At minimum, log with context.
- Use typed error classes for domain errors. Avoid throwing raw strings.
- For API error responses, defer to `15-api-contracts.md` (RFC 9457 Problem Details). Do not define ad-hoc error shapes like `{ error: "..." }` in TypeScript code.

```typescript
// CORRECT — typed error
class NotFoundError extends Error {
  constructor(resource: string, id: string) {
    super(`${resource} not found: ${id}`);
    this.name = 'NotFoundError';
  }
}

// WRONG — raw string
throw 'Item not found';
```

---

## Logging

Use `pino` for all structured logging. The scaffold emits a pre-configured logger module (`src/logger.js` or `lib/logger.ts`). Import from there — do not create your own.

```typescript
import { logger } from '@/lib/logger';

logger.info({ userId, action: 'signup' }, 'User signed up');
logger.error({ err, orderId }, 'Payment failed');
```

`console.log()` and `console.error()` are **banned** in production code paths. Route all output through the structured logger. See `55-observability.md` for full logging rules.

---

## Async Patterns

- Prefer `async`/`await` over raw `.then()` chains.
- Always handle promise rejections — unhandled rejections crash Node.js processes.
- Use `Promise.allSettled()` when multiple independent promises should not fail together.

---

## Running in Production

Node.js / Next.js services run via their respective start commands in the Dockerfile. Base image is always the current-LTS `-slim` image on `linux/amd64`. Never use Alpine.

```dockerfile
FROM node:<!--v:node_lts-->24<!--/v-->-<!--v:debian_codename-->bookworm<!--/v-->-slim
# ...
CMD ["node", "dist/server.js"]
```

For Next.js:

```dockerfile
FROM node:<!--v:node_lts-->24<!--/v-->-<!--v:debian_codename-->bookworm<!--/v-->-slim
# ...
CMD ["npm", "start"]
```

Never ship `ts-node` or `tsx` in the production image. Compile TypeScript at build time (`esbuild`/`swc`), run JavaScript at runtime. In DEV, `.ts` runs natively via built-in type stripping — ts-node/tsx are obsolete there too; see `12-node.md` § TypeScript.

---

## Port Range

Frontend / Node.js apps: **3000-3099**. Register in `PORTS.md`.

---

## Quality

```bash
npm run lint          # ESLint
npm run type-check    # tsc --noEmit
npm run build         # Production build
```

---

## Banned Patterns

| Pattern | Use Instead |
|---------|-------------|
| `any` type annotation | `unknown` + type guard narrowing |
| CommonJS `require()` in new code | ES module `import` / `export` |
| Deep relative imports (`../../../`) | Path alias (`@/`) via `tsconfig.json` |
| Raw string `throw 'error'` | Typed `Error` subclass |
| `{ error: "..." }` ad-hoc error shape | RFC 9457 via `15-api-contracts.md` |
| Scattered raw `process.env.X` access | Zod-validated `src/env.ts` module (parse once at boot) |
| `as` type assertion to bypass checks | Type guard, `satisfies`, or proper narrowing |
| Implicit `any` from untyped libraries | `.d.ts` declaration file |
| `enum` (any kind), `namespace` with runtime code, constructor parameter properties | `as const` object or string literal union; plain modules; explicit field assignment — enforced by `erasableSyntaxOnly` (native type stripping refuses ALL of these, per `12-node.md`) |
| `@ts-ignore` | `@ts-expect-error` with explanation comment |
| `console.log()` / `console.error()` in production | `pino` logger via `55-observability.md` |
| `localhost` as default host in env fallbacks | Service name (`postgres-main`, `redis-main`) |
| `ts-node` / `tsx` in production image | Compile at build, run JS at runtime |
| Alpine base image | the current-LTS `-slim` base per § Running in Production |

---

## Related Rule Packs

- `10-python.md` — Python sibling (same env/Docker/port philosophy)
- `12-node.md` — Node runtime co-owner (dev type stripping vs prod compile, erasable-syntax ban)
- `15-api-contracts.md` — API contract discipline, RFC 9457 error schema, idempotency
- `30-ops.md` — Dockerfile, compose, Traefik, resource limits, SSH+Compose deploy (`fabrik apply`)
- `55-observability.md` — pino setup, `/health` + `/metrics`, GlitchTip
- `saas/60-saas-ui.md` — SaaS frontend patterns (Next.js/React)

---

## Done When

- [ ] `tsconfig.json` has `"strict": true`, `"noUncheckedIndexedAccess": true`, and `"erasableSyntaxOnly": true` (no `enum`/`namespace`-with-runtime-code/parameter properties).
- [ ] No `any` annotations — `unknown` + narrowing used where type is uncertain.
- [ ] All imports use ES module syntax and path aliases.
- [ ] Domain errors use typed `Error` subclasses, not raw strings or ad-hoc objects.
- [ ] Environment variables parsed via Zod-validated `src/env.ts` — no scattered `process.env` access.
- [ ] Logging via `pino` — no `console.log()` in production code paths.
- [ ] Production Dockerfile uses the current-LTS `-slim` base per § Running in Production, not Alpine.
- [ ] No `ts-node` / `tsx` in production image — TypeScript compiled at build time.
- [ ] `npm run lint` and `npm run type-check` pass with zero warnings.
- [ ] Port registered in `PORTS.md` (3000-3099 range).
