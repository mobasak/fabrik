---
activation: glob
globs: ["**/tests/**", "**/test_*", "**/*_test.*", "**/*.test.*", "**/*.spec.*"]
description: Testing strategy — what to test per ticket type, smoke vs integration, regression rules
trigger: glob
---
<!-- CONSUMER: Coding agents (all) + Traycer (ticket-breakdown test criteria)
     GOAL: What to test per ticket type, framework per scaffold, tenant isolation testing
     TRAYCER USAGE: Injects test requirements into ticket ACs (Behavior Contract — one test per user-observable behavior; regression test for bugfix).
     AGENT USAGE: Write tests per the minimum test table. Use specified framework per scaffold. -->

# Testing Strategy Rules

Apply when writing, reviewing, or generating tests. Covers all scaffold types: FastAPI, Next.js, Chrome Extension, React Native.

## Core Philosophy

- **Testing Trophy model**: integration and E2E tests are the primary source of truth. Unit tests are reserved exclusively for complex pure algorithms or data transformations.
- **Behavior Contract**: every ticket enumerates its distinct **user-observable behaviors / acceptance criteria** and tests **each one** — one high-value integration/E2E test per behavior, risk-ordered, TDD for the risky ones. Skip trivia (getters / framework glue / config): **lean-but-complete, NOT 100%-line-coverage dogma**. Do not chase line coverage — ensure every behavior has a test that would fail if that behavior regressed. (Cheap pool subagents can author the per-behavior tests — the suggest→curate→author→fix workflow in `62-using-subagents.md` § Dispatch policy + `~/.claude/commands/fabrik-review.md`.)
- **No cosmetic assertions**: never assert against CSS classes, Tailwind utility strings, pixel measurements, or snapshot hashes. Assert application state and user-visible outcomes only.

## Test type by ticket type (one PER behavior, per the Behavior Contract)

The table gives the test **kind** per ticket type; author one of these **per user-observable behavior** the ticket adds (the Behavior Contract), not one per ticket.

| Ticket Type | Test kind (per behavior) |
|-------------|-------------|
| **New Feature (Backend)** | One pytest integration test via `httpx.AsyncClient` against real PostgreSQL. Verify HTTP status + response schema. |
| **New Feature (Frontend)** | One Playwright E2E test verifying the user happy path. Use semantic locators (`getByRole`). |
| **Bugfix** | One regression test. Write a test that **fails first** reproducing the bug, then implement the fix. |
| **Refactor** | Zero new tests. Existing integration/E2E tests must pass. Replace brittle unit tests with integration tests if encountered. |
| **Chore / Infrastructure** | Zero new tests. Existing smoke tests verify stability. |

## When one test per behavior is not enough

The Behavior Contract goes beyond one-test-per-behavior for these high-risk domains — exhaustive permutation testing is required:

- **Auth / RBAC boundaries** — test both positive access and negative (401/403) for each role.
- **Financial transactions / payment webhooks** — test edge cases, race conditions, idempotent retries.
- **Data deletion / cascades** — verify foreign key constraints and orphan prevention.
- **Multi-tenant isolation (SaaS/mobile with `postgres-main` RLS)** — query as tenant A, verify tenant B's data is invisible. See Tenant Isolation Testing below.

## FastAPI + PostgreSQL (async)

- **Framework**: `pytest` + `pytest-asyncio` + `httpx.AsyncClient`.
- **Run tests**: `uv run pytest tests/` (never bare `pytest` — Fabrik uses `uv`).
- **Zero-mock database policy**: never mock SQLAlchemy, SQLModel, or database sessions. All backend tests execute against a real PostgreSQL instance.
- Override `get_db` via `app.dependency_overrides` to inject a test session.
- Use **transactional rollbacks** for speed and isolation: open a transaction in the fixture, yield the session, rollback on teardown.

```python
import os
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

# From env — localhost in WSL dev, postgres-main in CI/container. Never hardcoded.
test_engine = create_async_engine(os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://postgres@localhost:5432/testdb"  # WSL dev default
))
TestSessionLocal = async_sessionmaker(test_engine, expire_on_commit=False)

@pytest.fixture
async def db_session():
    async with test_engine.connect() as connection:
        transaction = await connection.begin()
        # join_transaction_mode="create_savepoint" — inner commit() lands on a
        # savepoint instead of ending the outer transaction. Without this, any
        # session.commit() in the code under test leaks rows past the rollback.
        session = TestSessionLocal(
            bind=connection,
            join_transaction_mode="create_savepoint",
        )
        yield session
        await session.close()
        await transaction.rollback()

@pytest.fixture
async def client(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()

# Example test
@pytest.mark.asyncio
async def test_create_item(client: AsyncClient):
    resp = await client.post("/items/", json={"name": "test"})
    assert resp.status_code == 201
    assert resp.json()["name"] == "test"
```

- Use **programmatic test data factories** — not static JSON fixture files. Factories adapt automatically as schemas evolve.
- Use `structlog` in test helpers if logging is needed — never `print()`. See `55-observability.md`.

## Tenant Isolation Testing (SaaS / Mobile with RLS)

For multi-tenant projects using `postgres-main` RLS with `tenant_id` (RLS is owned by `fabrik-lib/fastapi-user-auth` on the `auth` schema; `auth.uid()` reads `request.jwt.claims`). Legacy Supabase-RLS projects run the same tests unchanged after migrating to `postgres-main` — see `AGENTS.md § Supabase`:

```python
@pytest.mark.asyncio
async def test_tenant_isolation(client_tenant_a: AsyncClient, client_tenant_b: AsyncClient):
    # Tenant A creates a resource
    resp = await client_tenant_a.post("/items/", json={"name": "secret"})
    item_id = resp.json()["id"]

    # Tenant B cannot see it
    resp = await client_tenant_b.get(f"/items/{item_id}")
    assert resp.status_code == 404  # RLS blocks cross-tenant access
```

- Create separate test fixtures per tenant with different `tenant_id` values set in the session context.
- Test both positive (own data visible) and negative (other tenant's data invisible) for every tenant-scoped endpoint.
- Reference `95-multi-tenant-saas.md` for RLS patterns.

## Next.js (App Router)

- **Framework**: Playwright only.
- **Banned**: Jest, Vitest, React Testing Library, Enzyme for UI component tests. These tools cannot natively handle async React Server Components and produce highly coupled tests.
- Playwright boots the actual Next.js server — Server Components, hydration, and API routes execute as in production.
- All locators must be **semantic**: `page.getByRole('button', { name: /submit/i })`. Never use CSS selectors or XPath.

## React Native (Mobile)

- **Framework**: Maestro (YAML-driven, black-box). See `80-mobile.md` § Testing for Maestro setup, `.maestro/` directory structure, and `testID` conventions.
- **Banned**: Detox (fragile native hooks, heavy Xcode/Android Studio maintenance), Appium.
- Maestro interacts via the native accessibility layer with built-in smart waits — near-zero maintenance overhead.
- Every `[PRIMARY PATH]` flow in Core Flows gets a Maestro YAML in `.maestro/`.

## Chrome Extension (MV3)

- **Framework**: Playwright with `chromium.launchPersistentContext`. Pin `@playwright/test` **≥1.59** (PR #39476 — keeps the same service-worker handle across an MV3 restart; the SW-restart flake fix).
- **Banned**: Puppeteer standard headless mode (cannot load extensions).
- Launch Playwright's **bundled Chromium** (`channel: 'chromium'`) — stable Chrome/Edge removed the `--load-extension` / `--disable-extensions-except` side-load flags (Chrome 137/139), so those args only work under bundled Chromium, never installed stable Chrome.
- Extract the MV3 service worker dynamically from `context.serviceWorkers()` to get the extension ID, then navigate to `chrome-extension://<id>/popup.html` for UI verification.
- Run `@axe-core/playwright` with **`bypassCSP: true`** (the non-relaxable extension CSP otherwise makes axe throw on `chrome-extension://` pages); keep `@axe-core/playwright` a **dev-dependency only** (MPL-2.0 — never bundled into the shipped artifact). Gate bundle size with `size-limit` **per surface** (popup / side-panel / content-script). Full loop: `chrome-ext/70-chrome-ext.md` § Testing & UI Verification.

## Contract Testing

- The TypeScript compiler is the most robust frontend-backend integration test.
- FastAPI auto-generates `openapi.json` at `/openapi.json`. TS types are auto-generated from it via `@hey-api/openapi-ts` (per `15-api-contracts.md`).
- If a backend schema change breaks the frontend TS compilation, the contract is violated — caught by static analysis with zero test code.
- Keep the generated types committed and re-generate on schema changes (`uv run python -c "import json; from src.main import app; print(json.dumps(app.openapi()))" > openapi.json`).

---

## Banned Patterns

| Pattern | Use Instead |
|---------|-------------|
| Mocking SQLAlchemy / DB sessions | Real PostgreSQL + async transactional rollback fixtures |
| Sync `TestClient` with async FastAPI app | `httpx.AsyncClient` with `ASGITransport` |
| Bare `pytest` command | `uv run pytest` |
| `print()` in test files | `structlog` logger or remove |
| Jest / Vitest / RTL for Next.js Server Components | Playwright E2E |
| Detox for React Native | Maestro YAML |
| Puppeteer headless for extensions | Playwright `launchPersistentContext` |
| CSS class / XPath selectors in E2E | Semantic `getByRole` locators |
| Static JSON fixture files for test data | Programmatic factory functions |
| Testing implementation details (internal method calls) | Testing user-visible outcomes |
| Targeting 100% line coverage | One high-value integration test per feature |
| Skipping tenant isolation tests in multi-tenant projects | Test both positive and negative per tenant-scoped endpoint |
| Hardcoded test DB URL | `TEST_DATABASE_URL` from env — `localhost` in WSL dev, `postgres-main` in CI |

---

## Related Rule Packs

- `10-python.md` — async patterns, Pydantic Settings (TEST_DATABASE_URL)
- `15-api-contracts.md` — `@hey-api/openapi-ts` codegen for contract testing
- `25-data-postgres.md` — canonical session (get_db override target), asyncpg
- `55-observability.md` — structlog in tests, no `print()`
- `80-mobile.md` — Maestro E2E setup, `.maestro/` directory
- `95-multi-tenant-saas.md` — RLS patterns for tenant isolation tests

---

## Done When

- [ ] Every distinct user-observable behavior the feature adds has a test (Behavior Contract) — one per behavior, risk-ordered, not one per ticket.
- [ ] Every bugfix has a regression test that fails before the fix.
- [ ] Backend tests run against real PostgreSQL — no DB mocks in test files.
- [ ] Test session uses `join_transaction_mode="create_savepoint"` — inner commits don't leak past rollback.
- [ ] Test DB URL from `TEST_DATABASE_URL` env var — not hardcoded.
- [ ] Backend tests use `httpx.AsyncClient` + `ASGITransport` — not sync `TestClient`.
- [ ] Tests run via `uv run pytest` — not bare `pytest`.
- [ ] Multi-tenant projects have tenant isolation tests (query as A, verify B invisible).
- [ ] Playwright tests use only semantic locators (`getByRole`, `getByLabel`, `getByText`).
- [ ] No Jest/Vitest/RTL imports in Next.js app directory.
- [ ] No Detox dependency in React Native projects — Maestro flows in `.maestro/`.
- [ ] Chrome extension tests use `launchPersistentContext` with extension loading flags.
- [ ] Test data uses factory functions, not static JSON fixtures.
- [ ] No `print()` statements in test files.
