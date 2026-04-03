---
activation: glob
globs: ["**/*.ts", "**/*.tsx"]
description: TypeScript language discipline — strict mode, type safety, module patterns, error handling
trigger: glob
---

# TypeScript Core Rules

Apply when working on any TypeScript project (Next.js, Node.js, Chrome Extension, Desktop, Mobile, Static Site). Skip for Python-only or infrastructure files. For React/UI-specific guidance, see `SAAS_UI` pack. For API error schemas, see `API_CONTRACTS` pack.

---

## Strict Mode

All TypeScript projects must use strict compiler settings:

```json
{
  "compilerOptions": {
    "strict": true,
    "noUncheckedIndexedAccess": true,
    "noImplicitOverride": true,
    "forceConsistentCasingInFileNames": true,
    "verbatimModuleSyntax": true
  }
}
```

Never loosen `strict` mode. If a library lacks types, write a `.d.ts` declaration file rather than using `any`.

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

Access environment variables at runtime via `process.env`. Never hardcode hosts, ports, API keys, or secrets.

```typescript
// CORRECT — runtime access with fallback
const apiUrl = process.env.API_URL ?? 'http://localhost:8000';
const port = parseInt(process.env.PORT ?? '3000', 10);

// WRONG — hardcoded
const apiUrl = 'http://localhost:8000';
```

For Next.js projects, prefix client-exposed variables with `NEXT_PUBLIC_`. Server-only variables must not use this prefix.

---

## Module Patterns

- Use ES module syntax (`import`/`export`). CommonJS `require()` is banned in new code.
- Use path aliases (`@/`) configured in `tsconfig.json` to avoid deep relative imports.
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
- For API error responses, defer to `API_CONTRACTS` pack (RFC 7807 Problem Details). Do not define ad-hoc error shapes like `{ error: "..." }` in TypeScript code.

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

## Async Patterns

- Prefer `async`/`await` over raw `.then()` chains.
- Always handle promise rejections — unhandled rejections crash Node.js processes.
- Use `Promise.allSettled()` when multiple independent promises should not fail together.

---

## Port Range

Frontend / Node.js apps: **3000–3099**. Register in `PORTS.md`.

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
| `{ error: "..." }` ad-hoc error shape | RFC 7807 via `API_CONTRACTS` pack |
| `as` type assertion to bypass checks | Type guard, `satisfies`, or proper narrowing |
| Implicit `any` from untyped libraries | `.d.ts` declaration file |
| Numeric `enum` (implicit values) | `as const` object or string literal union |
| `@ts-ignore` | `@ts-expect-error` with explanation comment |

---

## Done When

- [ ] `tsconfig.json` has `"strict": true` and `"noUncheckedIndexedAccess": true`.
- [ ] No `any` annotations — `unknown` + narrowing used where type is uncertain.
- [ ] All imports use ES module syntax and path aliases.
- [ ] Domain errors use typed `Error` subclasses, not raw strings or ad-hoc objects.
- [ ] No hardcoded hosts, ports, or secrets — all via `process.env` with fallbacks.
- [ ] `npm run lint` and `npm run type-check` pass with zero warnings.
