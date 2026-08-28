---
activation: glob
globs: ["**/routes/**", "**/api/**", "**/route.ts", "**/router.py", "**/lib/api*", "**/lib/client/**", "**/*api-client*", "**/*.api.ts", "**/*client.ts"]
description: API contract discipline — OpenAPI-first, error schema, pagination, idempotency, versioning
trigger: glob
---
<!-- CONSUMER: Coding agents (all) building API endpoints
     GOAL: API contract discipline — OpenAPI-first, error schema, pagination, idempotency, versioning
     TRAYCER USAGE: Injects as Context File in tickets that add or modify API endpoints.
     AGENT USAGE: Follow verbatim when writing API routes. Activated by glob on routes/api files. -->

# API Contract Rules

Apply when working on API routes, endpoints, or client integration. Skip for pure UI, Docker, or infrastructure files.

## OpenAPI Contract

- FastAPI path operations + Pydantic models are the sole source of truth for the API schema. Never manually edit `openapi.json`.
- TypeScript clients (Next.js, React Native, Chrome Extension) must be auto-generated from `openapi.json` via `@hey-api/openapi-ts` or equivalent codegen. Manual typing of API responses in TypeScript is banned.
- Run `oasdiff breaking --fail-on ERR` against the main-branch `openapi.json` before merge. Any
  ERR-level breaking change without a version bump is a defect. ⚠️ **This is an obligation on the
  AUTHOR, not a build that fails for you** — `oasdiff` is wired into no CI and no `final_gate` check
  anywhere in the fleet (`grep -rn oasdiff scripts/ .github/` → 0 hits, hub and projects alike). It
  read as a guarantee and functioned as prose: a live run removed two `/api/v1` paths and dropped a
  field from a response model's `required` array — both ERR-level — and nothing challenged it
  (transdoc, 2026-08-28). Run it yourself, or the check does not happen.
- **A breaking change does NOT always mean `/api/v2`.** For a PRE-RELEASE product retiring a surface
  its own frozen contract deleted, a version bump is ceremony — and an agent facing only that option
  either violates the rule silently or ships an absurd `v2`. The sanctioned third path is a
  **RECORDED EXCEPTION**: state in the PR/plan what broke, who consumes it (verify — a surface with
  zero consumers is not a breaking change to anyone), and why no bump. An exception you wrote down is
  reviewable; a silent violation is not.

## Authentication — every endpoint declares which of the three kinds it is

FastAPI is the API runtime for every Fabrik service, and its auth is **not optional or per-project**.
Full definition: `35-security-auth.md` § API-based systems. The contract-level obligations here:

- **Every path operation carries an explicit dependency** — `Depends(get_current_user)` (a human's
  JWT, minted by `fastapi-user-auth`, including via the passwordless flow),
  `Depends(require_internal_token)` (service-to-service), or a documented public exemption. An
  endpoint with NO auth dependency is a defect unless it is on the public list below.
- **The only endpoints that are public by default** are `/health`, `/healthz`, `/metrics`,
  `/api/health` (Authelia-bypassed on every domain, per `30-ops.md`). Anything else public is a
  DELIBERATE, reviewed decision — write it down; "nobody would call that" is not a decision.
- **It must show up in `openapi.json`.** Declare the schemes (`HTTPBearer` for the user JWT,
  `APIKeyHeader(name="X-Internal-Token")` for M2M) so the generated TypeScript clients and the
  `oasdiff` breaking-change review (author-run — see above) see auth as part of the contract. An endpoint whose auth changes
  is an API change.
- **Never hand-roll the M2M check.** `from internal_auth import require_internal_token` — inline
  `APIKeyHeader` / `require_api_key`, and per-service key names (`SERVICE_API_KEY`, `PROXY_API_KEY`),
  are banned by `35-security-auth.md`.
- **Network position is not authorization.** No host `ports:` and a private Docker network are
  deployment facts; they do not authenticate a caller.

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

## Error Schema (RFC 9457 — Problem Details)

All HTTP 4xx/5xx responses must conform to RFC 9457 (supersedes RFC 7807, backward-compatible). Override FastAPI's default exception handlers at the application level. Responses must carry `Content-Type: application/problem+json`.

```python
class ProblemDetails(BaseModel):
    type: str           # URI identifying the problem type
    title: str          # Short human-readable summary (stable across occurrences)
    status: int         # HTTP status code
    detail: str         # Human-readable explanation of this occurrence
    instance: str | None = None  # URI identifying this specific occurrence
```

**Bridge with `10-python.md`:** agents raise `HTTPException(status_code=404, detail="...")` in route handlers per `10-python.md`. A global exception handler converts `HTTPException` into the `ProblemDetails` schema above. Both patterns are correct — `HTTPException` is the trigger, `ProblemDetails` is the wire format.

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
- Cursor queries filter with a **composite row comparison** — the tiebreaker must be in the filter, not just the ordering:
  ```sql
  WHERE (sort_col, id) < (:last_sort_col, :last_id)
  ORDER BY sort_col DESC, id DESC
  LIMIT :size
  ```
  In SQLAlchemy: `.where(tuple_(Model.sort_col, Model.id) < (last_sort, last_id))`. Without the composite filter, rows sharing a `sort_col` value at the page boundary get skipped or duplicated.
- When sorting on a non-unique column (`created_at`, `price`), always append a unique tiebreaker (`id`) to **both** `WHERE` and `ORDER BY`.

## Versioning

- All endpoints must be mounted under an explicit URI version prefix: `/api/v1/...`.
- Versionless endpoints and header-based or query-param versioning are banned.
- Never introduce a breaking change to an existing version. If the contract must break, create a new version prefix (`/api/v2/`) and share core logic via the service layer.
- Deprecated endpoints must emit the `Deprecation` HTTP header and set `deprecated: true` in the OpenAPI spec.

## API Documentation

- **`python-api` / `node-api` scaffolds:** FastAPI's built-in `/docs` (Swagger UI) and `/redoc` are the default API documentation. No separate docs site needed.
- **Enrich OpenAPI metadata in code:** Add `tags`, `summary`, `description`, and `response_model` to every endpoint. Add `Field(description=...)` to Pydantic models. Add `examples` to request/response schemas. This makes `/docs` and `/redoc` production-quality developer docs.
- **Separate Docusaurus site:** Only when the API has external third-party consumers who need a developer portal (guides, tutorials, auth quickstart). Use `42-docusaurus.md` + Scalar (`@scalar/docusaurus`) to embed interactive API reference from `openapi.json`.
- **Never duplicate:** The OpenAPI spec generated from FastAPI code is the single source of truth. Docusaurus (if used) reads from it — never maintain parallel documentation.

## Service Layer

- Business logic belongs in dedicated service modules (`services/`), not in route handlers.
- Route handlers validate input (Pydantic), call a service function, and return the result. This enables sharing logic across API versions without duplication.
- Data validation occurs at the Pydantic boundary only. Service functions trust their typed inputs — no manual `if/else` dict validation inside business logic.

## Async Discipline (API-specific)

- Use `async def` for I/O-bound route handlers (database, network, Redis).
- Use plain `def` for CPU-bound work — FastAPI offloads these to a thread pool automatically.
- For the general async rule (no sync IO in async, `httpx.AsyncClient` over `requests`), see `10-python.md` § Banned Patterns.

---

## Banned Patterns

| Pattern | Use Instead |
|---------|-------------|
| Manual `snake_case`→`camelCase` mapping | Pydantic `alias_generator=to_camel` |
| `OFFSET`/`LIMIT` pagination | Cursor (keyset) pagination |
| `{"error": "..."}` or raw string errors | RFC 9457 `ProblemDetails` schema with `application/problem+json` |
| Header-based or query-param versioning | URI path versioning (`/api/v1/`) |
| `requests` / sync DB in `async def` | See `10-python.md` § Banned Patterns |
| Logic in route handlers | Service layer functions |
| Manual TS types for API responses | Auto-generated from `openapi.json` |
| Mutating existing version contract | New version prefix (`/v2/`) |
| gRPC / GraphQL (unless explicitly required) | RESTful JSON over HTTP described by OpenAPI |
| HATEOAS link traversal complexity | Simple, predictable endpoint structure |

---

## Related Rule Packs

- `10-python.md` — FastAPI patterns, Pydantic Settings, async discipline
- `20-typescript.md` — TypeScript client consuming these APIs
- `25-data-postgres.md` — database patterns behind the service layer
- `58-resilience.md` — timeout/retry for external API calls
- `95-multi-tenant-saas.md` — tenant-scoped API endpoints

---

## Done When

- [ ] All error responses conform to RFC 9457 schema (type, title, status, detail) with `Content-Type: application/problem+json`.
- [ ] Pydantic base model uses `alias_generator=to_camel` with `populate_by_name=True`.
- [ ] No `OFFSET` keyword in any SQLAlchemy query or raw SQL for collection endpoints.
- [ ] All mutative endpoints accept and enforce `X-Idempotency-Key`.
- [ ] All endpoints mounted under `/api/v1/` (or appropriate version prefix).
- [ ] `openapi.json` generated from code, never manually edited.
- [ ] TS clients generated from `openapi.json` — no manual API type definitions.
- [ ] `oasdiff` RUN BY YOU against the main branch — no unversioned ERR-level breaks, or a recorded exception. Nothing runs it automatically.
