---
activation: glob
globs: ["**/tests/**", "**/test_*", "**/*_test.*", "**/*.test.*", "**/*.spec.*"]
description: Testing strategy — what to test per ticket type, smoke vs integration, regression rules
trigger: glob
---

# Testing Strategy Rules

Apply when writing, reviewing, or generating tests. Covers all scaffold types: FastAPI, Next.js, Chrome Extension, React Native.

## Core Philosophy

- **Testing Trophy model**: integration and E2E tests are the primary source of truth. Unit tests are reserved exclusively for complex pure algorithms or data transformations.
- **One-Test Rule**: every new feature ticket requires exactly **one** high-value happy-path integration or E2E test. Do not chase line coverage — ensure critical-path behavioral coverage.
- **No cosmetic assertions**: never assert against CSS classes, Tailwind utility strings, pixel measurements, or snapshot hashes. Assert application state and user-visible outcomes only.

## Minimum Test by Ticket Type

| Ticket Type | Minimum Test |
|-------------|-------------|
| **New Feature (Backend)** | One pytest integration test via `TestClient` against real PostgreSQL. Verify HTTP status + response schema. |
| **New Feature (Frontend)** | One Playwright E2E test verifying the user happy path. Use semantic locators (`getByRole`). |
| **Bugfix** | One regression test. Write a test that **fails first** reproducing the bug, then implement the fix. |
| **Refactor** | Zero new tests. Existing integration/E2E tests must pass. Replace brittle unit tests with integration tests if encountered. |
| **Chore / Infrastructure** | Zero new tests. Existing smoke tests verify stability. |

## When One Test Is Not Enough

The One-Test Rule does not apply to these high-risk domains — exhaustive permutation testing is required:

- **Auth / RBAC boundaries** — test both positive access and negative (401/403) for each role.
- **Financial transactions / payment webhooks** — test edge cases, race conditions, idempotent retries.
- **Data deletion / cascades** — verify foreign key constraints and orphan prevention.

## FastAPI + PostgreSQL

- **Framework**: `pytest` + `httpx` (`TestClient`).
- **Zero-mock database policy**: never mock SQLAlchemy, SQLModel, or database sessions. All backend tests execute against a real PostgreSQL 16 instance.
- Override `get_db` via `app.dependency_overrides` to inject a test session.
- Use **transactional rollbacks** for speed and isolation: open a transaction in the fixture, yield the session, rollback on teardown.

```python
@pytest.fixture(scope="function")
def db_session():
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)
    yield session
    session.close()
    transaction.rollback()
    connection.close()

@pytest.fixture(scope="function")
def client(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
```

- Use **programmatic test data factories** — not static JSON fixture files. Factories adapt automatically as schemas evolve.

## Next.js (App Router)

- **Framework**: Playwright only.
- **Banned**: Jest, Vitest, React Testing Library, Enzyme for UI component tests. These tools cannot natively handle async React Server Components and produce highly coupled tests.
- Playwright boots the actual Next.js server — Server Components, hydration, and API routes execute as in production.
- All locators must be **semantic**: `page.getByRole('button', { name: /submit/i })`. Never use CSS selectors or XPath.

## React Native (Mobile)

- **Framework**: Maestro (YAML-driven, black-box).
- **Banned**: Detox (fragile native hooks, heavy Xcode/Android Studio maintenance), Appium.
- Maestro interacts via the native accessibility layer with built-in smart waits — near-zero maintenance overhead.

## Chrome Extension (MV3)

- **Framework**: Playwright with `chromium.launchPersistentContext`.
- **Banned**: Puppeteer standard headless mode (cannot load extensions).
- Pass `--disable-extensions-except` and `--load-extension` flags pointing to the built extension directory.
- Extract the MV3 service worker dynamically from `context.serviceWorkers()` to get the extension ID, then navigate to `chrome-extension://<id>/popup.html` for UI verification.

## Contract Testing

- The TypeScript compiler is the most robust frontend-backend integration test. Pydantic generates `openapi.json`; TS types are auto-generated from it.
- If a backend schema change breaks the frontend TS compilation, the contract is violated — this is caught by static analysis with zero test code.

---

## Banned Patterns

| Pattern | Use Instead |
|---------|-------------|
| Mocking SQLAlchemy / DB sessions | Real PostgreSQL + transactional rollback fixtures |
| Jest / Vitest / RTL for Next.js Server Components | Playwright E2E |
| Detox for React Native | Maestro YAML |
| Puppeteer headless for extensions | Playwright `launchPersistentContext` |
| CSS class / XPath selectors in E2E | Semantic `getByRole` locators |
| Static JSON fixture files for test data | Programmatic factory functions |
| Testing implementation details (internal method calls) | Testing user-visible outcomes |
| Targeting 100% line coverage | One high-value integration test per feature |

---

## Done When

- [ ] Every new feature has at least one integration or E2E test (One-Test Rule).
- [ ] Every bugfix has a regression test that fails before the fix.
- [ ] Backend tests run against real PostgreSQL — no DB mocks in test files.
- [ ] Playwright tests use only semantic locators (`getByRole`, `getByLabel`, `getByText`).
- [ ] No Jest/Vitest/RTL imports in Next.js app directory.
- [ ] No Detox dependency in React Native projects.
- [ ] Chrome extension tests use `launchPersistentContext` with extension loading flags.
- [ ] Test data uses factory functions, not static JSON fixtures.
