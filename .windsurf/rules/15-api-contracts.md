---
activation: glob
globs: ["**/routes/**", "**/api/**", "**/route.ts", "**/router.py"]
description: API contract discipline — OpenAPI-first, error schema, pagination, idempotency, versioning
trigger: glob
---

# API Contract Rules

Apply when working on API routes, endpoints, or client integration. Skip for pure UI, Docker, or infrastructure files.

## OpenAPI Contract

- FastAPI path operations + Pydantic models are the sole source of truth for the API schema. Never manually edit `openapi.json`.
- TypeScript clients (Next.js, React Native, Chrome Extension) must be auto-generated from `openapi.json` via `@hey-api/openapi-ts` or equivalent codegen. Manual typing of API responses in TypeScript is banned.
- Run `oasdiff breaking --fail-on ERR` against the main-branch `openapi.json` before merge. Any ERR-level breaking change without a version bump fails the build.

## Casing Boundary

All internal Python and database columns use `snake_case`. All JSON payloads use `camelCase`. Enforce globally via a shared Pydantic base model:

```python
from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

class FabrikBaseModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )
```

Never write manual `snake_case` → `camelCase` mapping functions.

## Error Schema (RFC 7807)

All HTTP 4xx/5xx responses must conform to RFC 7807 Problem Details. Override FastAPI's default exception handlers at the application level.

```python
class ProblemDetails(BaseModel):
    type: str           # URI identifying the problem type
    title: str          # Short human-readable summary (stable across occurrences)
    status: int         # HTTP status code
    detail: str         # Human-readable explanation of this occurrence
    instance: str | None = None  # URI identifying this specific occurrence
```

Raw strings, `{"error": "..."}`, or arbitrary dicts as error responses are banned.

## Idempotency

All state-mutating endpoints (POST, PUT, PATCH, DELETE) must accept an `X-Idempotency-Key` header (UUIDv4, client-generated). Backend flow:

1. Missing key on mutative endpoint → reject with 400.
2. Key exists + COMPLETED in Redis → return cached response, skip logic.
3. Key exists + PROCESSING → return 409 Conflict.
4. Key absent → set PROCESSING in Redis, execute handler, cache response as COMPLETED with 24h TTL.

Use Redis-backed middleware (e.g. `idemptx`) to keep business logic clean.

## Pagination

- **Cursor (keyset) pagination is the only permitted mechanism** for collection endpoints. `OFFSET`/`LIMIT` is banned — it causes O(n) scan-and-discard under PostgreSQL MVCC and data drift under concurrent writes.
- Cursor queries filter with `WHERE sort_col < :cursor ORDER BY sort_col DESC LIMIT :size` instead of offsetting.
- When sorting on a non-unique column (`created_at`, `price`), always append a unique tiebreaker (`id`) to the `ORDER BY` clause to guarantee deterministic B-Tree traversal.

## Versioning

- All endpoints must be mounted under an explicit URI version prefix: `/api/v1/...`.
- Versionless endpoints and header-based or query-param versioning are banned.
- Never introduce a breaking change to an existing version. If the contract must break, create a new version prefix (`/api/v2/`) and share core logic via the service layer.
- Deprecated endpoints must emit the `Deprecation` HTTP header and set `deprecated: true` in the OpenAPI spec.

## Service Layer

- Business logic belongs in dedicated service modules (`services/`), not in route handlers.
- Route handlers validate input (Pydantic), call a service function, and return the result. This enables sharing logic across API versions without duplication.
- Data validation occurs at the Pydantic boundary only. Service functions trust their typed inputs — no manual `if/else` dict validation inside business logic.

## Async Discipline

- Use `async def` for I/O-bound route handlers (database, network, Redis).
- Use plain `def` for CPU-bound work — FastAPI offloads these to a thread pool automatically.
- Never call synchronous blocking libraries (`requests`, sync SQLAlchemy sessions) inside an `async def` handler. Use `httpx`, `asyncpg`, or `AsyncSession`.

---

## Banned Patterns

| Pattern | Use Instead |
|---------|-------------|
| Manual `snake_case`→`camelCase` mapping | Pydantic `alias_generator=to_camel` |
| `OFFSET`/`LIMIT` pagination | Cursor (keyset) pagination |
| `{"error": "..."}` or raw string errors | RFC 7807 `ProblemDetails` schema |
| Header-based or query-param versioning | URI path versioning (`/api/v1/`) |
| `requests` / sync DB in `async def` | `httpx` / `AsyncSession` / `asyncpg` |
| Logic in route handlers | Service layer functions |
| Manual TS types for API responses | Auto-generated from `openapi.json` |
| Mutating existing version contract | New version prefix (`/v2/`) |
| gRPC / GraphQL (unless explicitly required) | RESTful JSON over HTTP described by OpenAPI |
| HATEOAS link traversal complexity | Simple, predictable endpoint structure |

---

## Done When

- [ ] All error responses conform to RFC 7807 schema (type, title, status, detail).
- [ ] Pydantic base model uses `alias_generator=to_camel` with `populate_by_name=True`.
- [ ] No `OFFSET` keyword in any SQLAlchemy query or raw SQL for collection endpoints.
- [ ] All mutative endpoints accept and enforce `X-Idempotency-Key`.
- [ ] All endpoints mounted under `/api/v1/` (or appropriate version prefix).
- [ ] `openapi.json` generated from code, never manually edited.
- [ ] TS clients generated from `openapi.json` — no manual API type definitions.
- [ ] `oasdiff` runs against main branch with no unversioned ERR-level breaks.
