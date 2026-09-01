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
- **Watched-fail-first** (for tests this change adds or modifies; trivia stays skipped per the Behavior Contract): a non-trivial behavior's test proves something only if it has been SEEN RED — either write it first and watch it fail, or (after the fact) neuter the fix/feature, prove the test goes red, then RESTORE and re-run to green. The neutered state is never staged, committed, or left in the tree. A green test never seen red is unverified — a suite can pass with its guard deleted.

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
- **Run tests**: `uv run pytest tests/` (never bare `pytest` — Fabrik uses `uv`) — **when the project has
  a `pyproject.toml`/`uv.lock`**. ⚠️ **Gate this on the manifest, because this line is FLOOR-injected into
  finder prompts and a vendored fabrik-lib MODULE has neither by design**: the module recipe ships
  `requirements.txt` (`fabrik-lib/README.md` § Creating a Reference Implementation), so `uv run` cannot
  resolve it and `python3 -m pytest` is the only thing that works. Telling a finder the sole working
  command is banned is a project-scaffold rule leaking into a library review — reported by fabrik-lib
  (`01M15081Q5`) after it fired on `health-probe/` and `subagents/`, neither of which has a
  `pyproject.toml`. Check for the manifest before applying this mandate.
- **Zero-mock database policy**: never mock SQLAlchemy, SQLModel, or database sessions. All backend tests execute against a real PostgreSQL instance.
- **The async-fixture example below requires `asyncio_mode = "auto"`** (the scaffold emits it in `pyproject.toml`) — pytest-asyncio's DEFAULT is strict mode, where a plain `@pytest.fixture async def` yields an unawaited generator and the suite breaks. A no-pyproject fabrik-lib module (the carve-out above) has no such config: decorate fixtures `@pytest_asyncio.fixture` there.
- **`ASGITransport` never runs lifespan** — anything the app initializes at startup (scaffolded apps are lifespan-based) silently does not exist in tests; wrap with `asgi-lifespan`'s `LifespanManager` when a test needs startup state.
- Override `get_db` via `app.dependency_overrides` to inject a test session.
- Use **transactional rollbacks** for speed and isolation: open a transaction in the fixture, yield the session, rollback on teardown.

```python
import os
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

# From env — localhost in WSL dev, postgres-main in CI/container. Never hardcoded.
# The default MUST end in _test — the require_throwaway guard (below) refuses
# any other suffix before destructive suites run.
test_engine = create_async_engine(os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://postgres@localhost:5432/myproject_test"  # WSL dev default
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

For multi-tenant projects using `postgres-main` RLS with `tenant_id` (RLS is owned by `fabrik-lib/fastapi-user-auth` on the `auth` schema; `auth.uid()` reads `request.jwt.claims`). Legacy Supabase-RLS projects run the same tests unchanged after migrating to `postgres-main` — see `agents-fabrik.md § Supabase`:

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

- **Async Server Components and full user flows: Playwright ONLY.** Vitest/Jest/RTL cannot render an async RSC — by design, not by gap (no test runner provides the async server render pipeline); the official guidance is E2E for those. Playwright boots the actual Next.js server — Server Components, hydration, and API routes execute as in production.
- **The narrow unit lane that IS legitimate**: server-action LOGIC as plain functions, zod schemas, utilities, and synchronous/props-only components may use Vitest + RTL where a unit test genuinely pays — the Trophy still biases E2E, and the `await` in a component is the hard line (fetches its own data → Playwright's job). Enzyme stays banned outright.
- **Never stub a server action from Playwright** — the server is the E2E boundary; stubbing belongs in the unit lane where the action is a plain function.
- Run Playwright against the PRODUCTION build (`next build && next start`), never the dev server.
- All locators must be **semantic**: `page.getByRole('button', { name: /submit/i })`. Never use CSS selectors or XPath.

## React Native (Mobile)

- **Framework**: Maestro (YAML-driven, black-box). See `80-mobile.md` § Testing for Maestro setup, `.maestro/` directory structure, and `testID` conventions.
- **Banned**: Detox (fragile native hooks, heavy Xcode/Android Studio maintenance), Appium.
- Maestro interacts via the native accessibility layer with built-in smart waits — near-zero maintenance overhead.
- Every `[PRIMARY PATH]` flow in Core Flows gets a Maestro YAML in `.maestro/`.

## Chrome Extension (MV3)

- **Framework**: Playwright with `chromium.launchPersistentContext`. Use a CURRENT `@playwright/test` — the MV3 service-worker-restart flake was fixed upstream (the runner keeps the same SW handle across a restart); an old pin without that fix reintroduces the flake.
- **Banned**: Puppeteer standard headless mode (cannot load extensions).
- Launch Playwright's **bundled Chromium** (`channel: 'chromium'`) — stable Chrome/Edge removed the `--load-extension` / `--disable-extensions-except` side-load flags (Chrome 137/139), so those args only work under bundled Chromium, never installed stable Chrome.
- Extract the MV3 service worker dynamically from `context.serviceWorkers()` to get the extension ID, then navigate to `chrome-extension://<id>/popup.html` for UI verification.
- Run `@axe-core/playwright` with **`bypassCSP: true`** (the non-relaxable extension CSP otherwise makes axe throw on `chrome-extension://` pages); keep `@axe-core/playwright` a **dev-dependency only** (MPL-2.0 — never bundled into the shipped artifact). Gate bundle size with `size-limit` **per surface** (popup / side-panel / content-script). Full loop: `chrome-ext/70-chrome-ext.md` § Testing & UI Verification.

## Contract Testing

- The TypeScript compiler is the most robust frontend-backend integration test.
- FastAPI auto-generates `openapi.json` at `/openapi.json`. TS types are auto-generated from it via `@hey-api/openapi-ts` (per `15-api-contracts.md`).
- If a backend schema change breaks the frontend TS compilation, the contract is violated — caught by static analysis with zero test code.
- Keep the generated types committed and re-generate on schema changes (`uv run python -c "import json; from <package>.main import app; print(json.dumps(app.openapi()))" > openapi.json` — the scaffold emits `src/<package>/main.py`, never a flat `src/main.py`, so `src.main` imports nothing).

---

## Backing-service parity in tests (12-Factor X) (CRITICAL)

> 12factor.net, verbatim: *"Differences between backing services mean that tiny incompatibilities crop up, causing code that worked and passed tests in development or staging to fail in production."*

Tests run against the **same backing services as production** — real PostgreSQL, real Redis. This pack's globs (`**/tests/**`, `**/test_*`) are the only ones that fire on test files, so the rule lives here.

**BANNED in tests:**

- `sqlite:///` or `:memory:` standing in for PostgreSQL.
- `fakeredis` / `mockredis` standing in for Redis.
- Any in-memory substitute for a real backing service.

**A test suite that passes on SQLite and fails on Postgres has tested nothing.** The behaviours that matter are exactly the ones SQLite does not have: `JSONB`, `RETURNING`, `FOR UPDATE SKIP LOCKED` (the job queue depends on it), partial indexes, real transaction isolation, RLS. Integration / contract / e2e tests use a dedicated real Postgres test database (see § FastAPI + PostgreSQL (async)).

**Scope:** this is about **server-side** backing services. `desktop-app` / `mobile-app` client-local SQLite stores are exempt — there SQLite *is* the production engine.

---

## Banned Patterns

| Pattern | Use Instead |
|---------|-------------|
| Mocking SQLAlchemy / DB sessions | Real PostgreSQL + async transactional rollback fixtures |
| Sync `TestClient` with async FastAPI app | `httpx.AsyncClient` with `ASGITransport` |
| Bare `pytest` command **in a project with a `pyproject.toml`/`uv.lock`** | `uv run pytest` (a fabrik-lib module ships `requirements.txt` and has neither — `python3 -m pytest` is correct there) |
| `print()` in test files | `structlog` logger or remove |
| Jest / Vitest / RTL for ASYNC Server Components or full flows | Playwright E2E (sync/props-only components + server-action logic may unit-test via Vitest where it pays) |
| Detox for React Native | Maestro YAML |
| Puppeteer headless for extensions | Playwright `launchPersistentContext` |
| CSS class / XPath selectors in E2E | Semantic `getByRole` locators |
| Static JSON fixture files for test data | Programmatic factory functions |
| Testing implementation details (internal method calls) | Testing user-visible outcomes |
| Targeting 100% line coverage | One high-value integration test per feature |
| A test THIS change adds/modifies that was never seen red (no fail-first, no red-on-revert proof) | Watch it fail first, or neuter the change → prove red → restore → re-run green |
| Raw `dict.get()` / `body.get()` / `body.foo` value reads standing in for wire-contract assertions | Validate through the DECLARED response schema (Pydantic `Model.model_validate(body)` · zod `parse` · the generated TS type) **and assert the key set for rename/casing coverage** (`"job_id" in body`): schema validation alone has holes — an optional field still yields `None`/`undefined` on a missing key, and `populate_by_name=True` silently accepts the wrong casing. Legit `get()` uses stay: asserting a key ABSENT by design (`"password" not in body`), probing third-party/schema-less bodies, passthrough blobs |
| Skipping tenant isolation tests in multi-tenant projects | Test both positive and negative per tenant-scoped endpoint |
| Hardcoded test DB URL | `TEST_DATABASE_URL` from env — `localhost` in WSL dev, `postgres-main` in CI |
| Destructive test (DROP SCHEMA/TABLE, TRUNCATE, migration re-apply) connecting unguarded | Call `require_throwaway(url)` (scaffold-emitted `tests/conftest.py`) FIRST — fail-closed: only DB names ending `_test`/`throwaway`/`scratch` (case-insensitive; CI uses `ci_test`), or `CI=true` **against a localhost DB**, may proceed; a mispointed URL errors instead of wiping a dev DB |

---

## Related Rule Packs

- `10-python.md` — async patterns, Pydantic Settings (TEST_DATABASE_URL)
- `15-api-contracts.md` — `@hey-api/openapi-ts` codegen for contract testing
- `25-data-postgres.md` — canonical session (get_db override target), asyncpg
- `55-observability.md` — structlog in tests, no `print()`
- `mobile-app/80-mobile.md` — Maestro E2E setup, `.maestro/` directory
- `saas/95-multi-tenant-saas.md` — RLS patterns for tenant isolation tests

---

## Done When

- [ ] Every distinct user-observable behavior the feature adds has a test (Behavior Contract) — one per behavior, risk-ordered, not one per ticket.
- [ ] Every bugfix has a regression test that fails before the fix.
- [ ] Backend tests run against real PostgreSQL — no DB mocks in test files.
- [ ] Test session uses `join_transaction_mode="create_savepoint"` — inner commits don't leak past rollback.
- [ ] Test DB URL from `TEST_DATABASE_URL` env var — not hardcoded.
- [ ] Destructive DB tests call `require_throwaway(TEST_DATABASE_URL)` before connecting — never point them at a dev/shared DB.
- [ ] Backend tests use `httpx.AsyncClient` + `ASGITransport` — not sync `TestClient`.
- [ ] Tests run via `uv run pytest` — not bare `pytest`.
- [ ] Multi-tenant projects have tenant isolation tests (query as A, verify B invisible).
- [ ] Playwright tests use only semantic locators (`getByRole`, `getByLabel`, `getByText`).
- [ ] No Vitest/RTL rendering of ASYNC Server Components (unit lane only for sync/props-only components + action logic); no Enzyme anywhere.
- [ ] No Detox dependency in React Native projects — Maestro flows in `.maestro/`.
- [ ] Chrome extension tests use `launchPersistentContext` with extension loading flags.
- [ ] Test data uses factory functions, not static JSON fixtures.
- [ ] No `print()` statements in test files.
- [ ] Wire-contract assertions validate through the declared schema AND assert the key set — no raw `dict.get()`/`body.foo` value read standing in for a contract check (optional fields + `populate_by_name` make those pass green on a broken wire).
- [ ] Every test this change adds/modifies was SEEN red (fail-first or neuter→red→restore→green).

## Behavior-Contract test accompaniment (plan windows)

A plan-execution window that ships user-observable behaviour shows its Behavior-Contract tests in
the same window — the declared `- **Given** …` rows are a commitment, not decoration.
Gate-observed: `check_phase_tests.py` WARNs (advisory, plan-window-scoped: an ACTIVE plan lock's
`baseline_commit..HEAD` with declared rows, source changes, and zero test changes). Per-row
coverage is the phase-boundary `/fabrik-review`'s to adjudicate; this pack is the rule the WARN
cites — the always-loaded twin lives in `CLAUDE.md` § Completion Contract item 1.
