# Cross-SaaS SSO — the hub `product_entitlements_bridge` module + integration reference

Status: EXECUTED 2026-08-29
Whole-plan review: docs/development/reviews/2026-08-29-plan-1-cross-saas-sso-bridge-review.md (found: 0, fixed: 0 — native Opus ×6 across phases + pool breadth ×3, all refuted)
Epic: docs/development/epics/2026-08-27-epic-2-cross-saas-sso-integration.md (epic_n 2, depends_on [1])
Source of truth: docs/superpowers/specs/2026-08-27-umbrella-sso-infrastructure-decisions.md
Shape: MONOLITH — one cohesive hub library module (`libs/product_entitlements_bridge/`) + one reference doc; its files overlap, so a spine+ticket set would serialize on shared paths (a monolith is the correct shape).

## Scope of THIS plan (hub-executable only)

Epic-2 is **cross-repo**. This plan builds ONLY the two hub-owned artifacts from the epic's `owned_paths`:
1. **`libs/product_entitlements_bridge/`** — the ocoron-specific composition every relying-party (RP) vendors:
   a Zitadel **Authorization v2** `GrantSource` adapter (feeding the fabrik-lib `product-entitlements` gate) +
   an **idempotent billing→grant reconciler** + a **revocation→live-session teardown** hook.
2. **`docs/reference/umbrella-sso-integration.md`** — the reference the per-RP agents follow.

**NOT in this plan (dispatched cross-repo follow-ups — the hub cannot write these files, HARD STOP):** the
per-RP `LocalAuthBridge` implementations, `shape.needs_cache: true` on each RP spec, and the reconciler/teardown
WIRING live in `youtube` / `transdoc` / `web-ecommerce-factory` (+ future) — each dispatched to that project's
own agents against this plan's reference doc. They are listed under `## Residual unknowns → dispatched follow-ups`,
never executed here.

**External deps are BUILT (grounded this run):** fabrik-lib `oauth-login/` (Active) supplies `VerifiedIdentity`
+ the `LocalAuthBridge` protocol; `product-entitlements/` (Active) supplies the `has_access`/`entitlements_for`/
`revoke` gate + the injected `GrantSource`/`BillingSource`/`AuditSink` protocols + the short-TTL `redis-main`
`GrantCache` (fail-CLOSED). This plan does NOT build them — it vendors them and supplies the Zitadel `GrantSource`.

## Global Constraints (every phase inherits — verbatim from the binding sources)

- **Backing services:** `postgres-main:5432` / `redis-main:6379` — never `localhost`; the external `fabrik` network; no host `ports:`; per-service `deploy.resources.limits.memory` (agents-fabrik-core.md).
- **Cache is fail-CLOSED:** coarse product-access is source-checked per boundary via the short-TTL `redis-main` grant cache and is **NEVER a long-lived JWT claim**; a Redis/GrantSource error DENIES (product-entitlements/README §"Access is fail-CLOSED", cache.py). Fine plan/features fail-OPEN to a default tier.
- **`needs_cache: true`** on every consuming RP spec or `fabrik apply` skips the Redis registrar (infra-decisions § Shared Shape Decisions). Enforced per-RP downstream, asserted here in the reference doc.
- **Reconciler:** idempotent + re-runnable without double-granting; runs async on each RP's PostgreSQL job queue (`core/75-workers-jobs.md`), **never inline >10s** in a request handler; on SIGTERM the job requeues (12-Factor IX), handler idempotent (infra-decisions § Background Processing).
- **Zitadel machine auth:** a service user via **Private-Key JWT** (or Client Credentials), token MUST request the reserved scope `urn:zitadel:iam:org:project:id:zitadel:aud` or the API rejects it; the service user needs `user.grant.write`/`read`/`delete` **AND `session.read` + `session.delete`** (the latter two for the revocation session-teardown loop). Config = granular env, no secrets in code (12-Factor III): `ZITADEL_ISSUER`, `ZITADEL_BRIDGE_SA_KEY` (JWT-profile key JSON), `ZITADEL_PROJECT_ID`, `ZITADEL_ORG_ID`, `REDIS_URL`.
- **Audit:** every grant mutation + revocation writes the hash-chained audit log via the fabrik-lib audit-log module (infra-decisions § Auth Strategy, universal cat #12) — wired through `product-entitlements`' optional `AuditSink`.
- **Logs:** unbuffered JSON to stdout only, never a logfile (12-Factor XI). **Migrations:** none (the module owns no DB table — product-entitlements is "no owned DB table"; grants live in Zitadel, cache in redis).
- **Security:** federation is auth-code + PKCE + full ID-token/JWKS validation, keyed on provider subject never email (oauth-login blocks nOAuth); `core/35-security-auth.md`.

## Context Ledger

| Source | What binds | Grounded ref |
|---|---|---|
| `core/35-security-auth.md` (ACTIVE) | auth-code+PKCE, JWKS validation, subject-keyed federation | pack; oauth-login/README:5-7 |
| `core/85-payments-billing.md` (ACTIVE) | billing→grant convergence, no double-grant — the RP resolves billing and passes a precomputed `entitled_products` set to the reconciler (the reconciler does NOT inject `BillingSource`; that Protocol is the RP's own seam) | pack + product-entitlements/product_entitlements/protocols.py `BillingSource` :33 |
| `core/58-resilience.md` (ACTIVE) | timeout+retry+circuit-breaker+classifier on the Zitadel API call; provider-death | pack; infra-decisions § External Services |
| `core/75-workers-jobs.md` (ACTIVE) | reconciler on PG job queue, idempotent, requeue-on-SIGTERM, never inline >10s | pack; infra-decisions § Background Processing |
| `core/45-testing-strategy.md` (ACTIVE) | one test per behavior, risk-ordered, TDD the risky | pack |
| `saas/95-multi-tenant-saas.md` (AVAILABLE→matches) | per-tenant isolation; LocalAuthBridge sets tenant GUC | pack; oauth-login/README:179 |
| fabrik-lib `oauth-login/` (VENDOR) | `VerifiedIdentity` + `LocalAuthBridge` protocol (`create_or_get_user_from_verified_identity` + `mint_app_session`) — RP mints its session | `/opt/fabrik-lib/oauth-login/oauth_login/protocols.py:35` (LocalAuthBridge), `identity.py` (VerifiedIdentity) |
| fabrik-lib `product-entitlements/` (VENDOR) | the gate + `GrantSource`/`BillingSource`/`AuditSink` protocols (all **async**) + `GrantCache` (Null/Redis, fail-closed) | `/opt/fabrik-lib/product-entitlements/product_entitlements/protocols.py:19` (GrantSource.`product_access`→`frozenset[str]` :25), :33 (BillingSource), :49 (AuditSink); `cache.py` |
| fabrik-lib `app-audit-log/` (VENDOR) | hash-chained audit of grant mutations — feeds `product-entitlements`' `AuditSink` | `/opt/fabrik-lib/app-audit-log/` (README §API `record_event(conn, …)` is **sync + connection-based**; the RP's `AuditSink.record` is **async** → impedance, see Phase C) |
| fabrik-lib `async-http-client/` (VENDOR) | timeout+retry+circuit-breaker for the Zitadel HTTP calls — do NOT hand-roll | `/opt/fabrik-lib/async-http-client/circuit_breaker.py`, `client_pool.py` |
| Zitadel Authorization v2 API (EXTERNAL, grounded) | `CreateAuthorization`/`DeleteAuthorization`/`ListAuthorizations`/`UpdateAuthorization` — Connect paths `POST /zitadel.authorization.v2.AuthorizationService/{Method}` (NOT `/v2/authorizations`), plain JSON-over-HTTP (`Connect-Protocol-Version: 1`) | zitadel.com/docs/reference/api/authorization/… (fetched 2026-08-29) |
| Zitadel Session v2 API (EXTERNAL, grounded) | teardown loop: `ListSessions{user_id_query}` (`POST /v2/sessions/search`, `session.read`) → `DeleteSession` (`DELETE /v2/sessions/{id}`, `session.delete`, machine-callable) — each Delete fires back-channel logout | zitadel.com/docs/apis/resources/session_service_v2/… (fetched 2026-08-29) |
| Zitadel back-channel logout (EXTERNAL, grounded) | `backchannel_logout_uri` per RP; logout token carries `sid`/`aud`/`events`; **DeleteAuthorization is NOT a session-termination event** — teardown must run the Session-v2 delete loop | zitadel.com/docs/guides/integrate/back-channel-logout (2026-08-29) |
| live Zitadel deploy | issuer LIVE — `https://auth.ocoron.com` OIDC discovery 200, backchannel_logout_supported=true | specs/services/zitadel.yaml; /fabrik-deploy-verify this session |

**🆕 fabrik-lib candidate:** `product_entitlements_bridge` is reused by ≥3 RP types (youtube/transdoc/web-ecommerce-factory) with a small clean interface (a `GrantSource` impl + a reconciler fn + a teardown fn). It clears the new-module bar. It is built in the hub per the epic's `owned_paths`, but **flagged for promotion to a fabrik-lib module** so RPs vendor it like the other three (surfaced in the handoff; propose-only — never write into fabrik-lib from here).

## Execution Discipline

- **Review floor:** every phase ends by running `/fabrik-review` on its changed surface to a coverage-adjudicated exit before commit; no phase commits on a first-pass green.
- **Dispatch policy:** pool-default (`fanout("code"/"research"/"docs", …)`, records to the flywheel + `set_quality` back-fill) for gradeable per-behavior tests + doc reconciliation; native Opus for the authoritative auth/concurrency review (the GrantSource + reconciler idempotency + the session-teardown correctness are high-risk) + the decide/merge.
- **Parallelism:** the per-behavior test authoring in each phase fans out to the pool (disjoint test files); the module code itself is sequential (A→B→C, real data dependency). Merge/dedupe at each phase's `/fabrik-review`.

---

## Phase A — Zitadel Authorization-v2 `GrantSource` adapter + service-user auth client ✅ EXECUTED 2026-08-29

**One responsibility:** a `product-entitlements` `GrantSource` implementation backed by Zitadel's Authorization v2 API, plus the machine-auth client the adapter (and Phase B/C) use.

**Interfaces — Produces:**
- `libs/product_entitlements_bridge/zitadel_client.py`: `class ZitadelClient(issuer:str, sa_key:dict, project_id:str, org_id:str)` with **async** methods `create_authorization(user_id, role_keys=None) -> str` (returns authorization id), `delete_authorization(auth_id) -> None` (idempotent — not-found = success), `list_authorizations(user_id) -> list[Authorization]`, `update_authorization(auth_id, role_keys) -> None`, and `terminate_user_sessions(user_id) -> None`. Async because the `GrantSource` Protocol it feeds is async (`product_entitlements/protocols.py:25`).
  - **Transport (grounded, was ambiguous):** raw **`httpx.AsyncClient`** POST-JSON to the Connect paths (Connect protocol = plain JSON-over-HTTP with header `Connect-Protocol-Version: 1`; no generated gRPC stub) — so tests mock the httpx layer via `respx`/`MockTransport`. **Resilience:** vendor fabrik-lib **`async-http-client/`** (`circuit_breaker.py` + `client_pool.py`) rather than hand-rolling timeout/retry/circuit-breaker (`core/58-resilience.md`) — do NOT rebuild it.
  - **Auth:** Private-Key JWT (RS256 over `ZITADEL_BRIDGE_SA_KEY` JSON) requesting scope `urn:zitadel:iam:org:project:id:zitadel:aud`, access-token cached to expiry. **Deps the module needs (authorize before adding to a `requirements.txt`):** `httpx`, a JWT lib (`PyJWT` or `authlib`). Authorization paths: `CreateAuthorization`/`DeleteAuthorization`/`ListAuthorizations`/`UpdateAuthorization` under `POST /zitadel.authorization.v2.AuthorizationService/{Method}`.
  - **`terminate_user_sessions` (GROUNDED — the criterion-#3 linchpin, 2026-08-29):** Zitadel has NO single "terminate all sessions for a user" call. The real mechanism is a **Session Service v2 loop**: `ListSessions{user_id_query}` (`POST /v2/sessions/search`, perm `session.read`) → `DeleteSession{session_id}` (`DELETE /v2/sessions/{id}`, perm `session.delete`, **no per-session token needed for a machine caller with the org/instance `session.delete` permission**) for each. Each `DeleteSession` IS a session-termination → fires the RP's back-channel logout. So the service user needs `session.read` + `session.delete` **in addition to** `user.grant.write/read/delete`. Caveat: back-channel logout reaches only RPs registered with a `backchannel_logout_uri` (the RP's own wiring).
- `libs/product_entitlements_bridge/grant_source.py`: `class ZitadelGrantSource(GrantSource)` — implements the product-entitlements `GrantSource` Protocol's real method **`async def product_access(self, user_id: str) -> frozenset[str]`** (`/opt/fabrik-lib/product-entitlements/product_entitlements/protocols.py:25`) by mapping `ZitadelClient.list_authorizations` project ids → product keys. This is the method the gate calls on every boundary for the fail-closed coarse-access check.

**Steps:**
1. `mkdir libs/product_entitlements_bridge`; read `/opt/fabrik-lib/product-entitlements/product_entitlements/protocols.py` to ground the exact `GrantSource` method (`async def product_access(self, user_id) -> frozenset[str]`, :25). **Author `libs/product_entitlements_bridge/README.md`** — the module's vendoring contract (what it does · how an RP vendors + wires it · its deps httpx+JWT+async-http-client), mirroring the fabrik-lib module-README shape, since RPs vendor this module cross-repo (Residual #1).
2. **[TDD — highest risk] Write `tests/test_bridge_grant_source.py` FIRST** (fanout `fanout("code", …)` for the per-behavior tests): mock the Connect HTTP layer; assert `await product_access(user_id)` maps `ListAuthorizations(in_user_ids=[u], project_id=...)` results → a `frozenset[str]` of products; assert a Zitadel/HTTP error RAISES (so the gate fails CLOSED, never returns ∅-as-allowed). Run → RED.
3. Implement `zitadel_client.py` (raw `httpx.AsyncClient` JSON-over-Connect to the four Authorization-v2 methods + the `ListSessions`→`DeleteSession` teardown loop for `terminate_user_sessions` + Private-Key-JWT token mint with the reserved aud scope; wrap the calls with the vendored `async-http-client` circuit-breaker per `core/58-resilience.md` — do NOT hand-roll) and `grant_source.py`. Run tests → GREEN.
4. **Gate:** `python -m pytest tests/test_bridge_grant_source.py -q` → pass.
5. `python scripts/enforcement/check_doc_sync.py` + note the new module for `INDEX.md` (Phase C owns the doc writes).
6. **`/fabrik-review`** on the changed surface (native Opus for the auth/JWKS/fail-closed correctness) → coverage-adjudicated exit.
7. Commit (explicit paths + provenance trailers).

**Behavior Contract:**
- **Given** a user with two Zitadel authorizations, **When** `await ZitadelGrantSource.product_access(user_id)` runs, **Then** it returns exactly the two mapped products as a `frozenset` via `ListAuthorizations` (libs/product_entitlements_bridge/grant_source.py).
- **Given** the Zitadel API errors or times out, **When** `product_access` runs, **Then** it RAISES (the gate denies — fail-closed), never returns an empty-as-allowed set (libs/product_entitlements_bridge/grant_source.py).
- **Given** a service call, **When** the client mints its token, **Then** the token request carries scope `urn:zitadel:iam:org:project:id:zitadel:aud` (libs/product_entitlements_bridge/zitadel_client.py).

## Phase B — Idempotent billing→grant reconciler ✅ EXECUTED 2026-08-29

**One responsibility:** a re-runnable function that converges Zitadel authorizations to what billing says a user is entitled to — no paid-but-locked-out user, no double-grant.

**Interfaces — Consumes:** `ZitadelClient` (Phase A). **Produces:**
- `libs/product_entitlements_bridge/reconciler.py`: `async def reconcile_user_grants(client: ZitadelClient, user_id: str, entitled_products: set[str], role_map: dict[str, list[str]], audit: AuditSink|None=None) -> ReconcileResult` — the idempotent List→(Create|Update|Delete) convergence: `ListAuthorizations` → create missing, `UpdateAuthorization` (full role replace) where roles drift, `DeleteAuthorization` where billing no longer entitles. A pure unit the RP enqueues on its PG job queue. Every mutation → `audit`.
  - **Both inputs are the RP's to supply (grounded seam, was under-specified):** `entitled_products` = the product keys billing entitles (the RP resolves `payments`/`credits`/`revenuecat`); `role_map` = **product key → Zitadel role_keys[]**, a per-RP CONFIG constant (which Zitadel roles each product grants — e.g. `{"pro": ["pro_user"]}`), NOT derived here. The reference doc (Phase C) defines both as the two values every RP passes; the reconciler is config-agnostic. `ReconcileResult` reports counts (created/updated/deleted/unchanged) for the idempotency assertion.

**Steps:**
1. **[TDD — highest risk: idempotency] Write `tests/test_bridge_reconciler.py` FIRST** (pool fanout): (a) first run creates the missing grant; (b) **second run with unchanged billing makes ZERO mutations** (idempotent — the criterion #4 proof); (c) a create that initially failed is repaired on re-run (no paid-but-locked-out); (d) role drift → `UpdateAuthorization` converges, not a duplicate; (e) billing downgrade → `DeleteAuthorization`. Run → RED.
2. Implement `reconciler.py` using the List-then-Create/Update/Delete pattern (grounded: Create is non-idempotent → List first). Wire `AuditSink`. Run → GREEN.
3. **Gate:** `python -m pytest tests/test_bridge_reconciler.py -q` → pass.
4. `check_doc_sync.py`.
5. **`/fabrik-review`** (native Opus for the idempotency/concurrency reasoning) → adjudicated exit.
6. Commit.

**Behavior Contract:**
- **Given** a user entitled to product X with no Zitadel authorization, **When** `reconcile_user_grants` runs, **Then** exactly one `CreateAuthorization` is issued and audited (libs/product_entitlements_bridge/reconciler.py).
- **Given** the same call runs twice with unchanged billing, **When** the second run executes, **Then** it issues ZERO Zitadel mutations (idempotent) (libs/product_entitlements_bridge/reconciler.py).
- **Given** billing no longer entitles product Y, **When** the reconciler runs, **Then** it `DeleteAuthorization`s Y's grant and audits it (libs/product_entitlements_bridge/reconciler.py).

## Phase C — Revocation→live-session teardown + the integration reference doc + final gate ✅ EXECUTED 2026-08-29

**One responsibility:** the teardown hook that makes a revoke kill LIVE sessions (not just the next login), and the reference doc the per-RP agents build against.

**Interfaces — Consumes:** `ZitadelClient` (A), the product-entitlements gate `revoke()` + `GrantCache`. **Produces:**
- `libs/product_entitlements_bridge/teardown.py`: `def revoke_and_teardown(client, gate, user_id, product) -> None` — (1) `DeleteAuthorization`; (2) `gate.revoke(user_id, product)` to invalidate the short-TTL cache (next boundary check denies within the TTL window); (3) **`client.terminate_user_sessions(user_id)`** — the grounded gotcha: DeleteAuthorization is NOT a session-termination event, so back-channel logout only fires when the session is actually terminated. This is what makes criterion #3 ("tears down LIVE product sessions") true.
- `docs/reference/umbrella-sso-integration.md`: the per-RP pattern the dispatched agents follow, self-sufficient — each item concrete:
  - **Vendor** `oauth-login`, `product-entitlements`, `app-audit-log`, `async-http-client` via `cp -r /opt/fabrik-lib/<mod> <rp>/vendored/`. **The bridge itself:** until it is promoted to fabrik-lib (see Residual/decision #1), vendor it cross-repo from the hub — `cp -r /opt/fabrik/libs/product_entitlements_bridge <rp>/vendored/` (same box; the module ships a README per its own `libs/product_entitlements_bridge/README.md` — the vendoring contract).
  - **Set `shape.needs_cache: true`** on the RP spec (`fabrik apply` then fires the Redis registrar → `REDIS_URL`).
  - **`LocalAuthBridge`:** implement `create_or_get_user_from_verified_identity` + `mint_app_session` (mint the RP's `fastapi-user-auth` session + set the tenant GUC) from the umbrella `VerifiedIdentity`.
  - **Enqueue seam (#5, was hand-waved):** on each billing event (the `payments`/`credits`/`revenuecat` webhook handler), ENQUEUE a job on the RP's PG job queue (fabrik-lib `job-queue/` or the RP's existing queue) carrying `{user_id, entitled_products, role_map}`; the worker builds a `ZitadelClient(ZITADEL_ISSUER, ZITADEL_BRIDGE_SA_KEY, ZITADEL_PROJECT_ID, ZITADEL_ORG_ID)` and `await reconcile_user_grants(...)`. Never inline in the request (>10s); idempotent so a retry is safe.
  - **AuditSink (#6, the async↔sync impedance):** `AuditSink.record` is **async** but `app-audit-log`'s `record_event(conn, …)` is **sync + connection-based** — the RP's `AuditSink` impl must inject a DB `conn` and offload the sync call (`await asyncio.to_thread(record_event, conn, …)`) so it does not block the worker's event loop.
  - **Revocation:** register `backchannel_logout_uri` on the RP's Zitadel OIDC app AND validate the logout token (`sid`/`aud`/`events`); wire `revoke_and_teardown` on grant-revoke (it runs the Session-v2 delete loop → back-channel logout fires).
  - **Invariants:** the machine-auth reserved-scope + `session.read`/`session.delete` perms; the fail-closed cache; access is source-checked, never a JWT claim.

**Steps:**
1. **[TDD] Write `tests/test_bridge_teardown.py` FIRST** (pool fanout): assert `revoke_and_teardown` calls DeleteAuthorization AND `gate.revoke` (cache invalidation) AND `terminate_user_sessions` — all three, in order. For the "next `has_access` denies" assertion, the **mock `GrantSource.product_access` MUST drop the product after the delete** (mirroring the real DeleteAuthorization) — otherwise `has_access` re-hits the source, re-grants and re-caches, and the assertion tests the mock not the invariant. Run → RED.
2. Implement `teardown.py`. Run → GREEN.
3. Author `docs/reference/umbrella-sso-integration.md` (pool `fanout("docs", …)` reconciled + native-verified per `doc_reconcile.py`) — the per-RP integration recipe + the two grounded gotchas (session-teardown, reserved-scope) + the `needs_cache` assertion + a per-RP checklist the dispatched agents follow.
4. **Doc Sync Matrix:** `INDEX.md` (new module + new doc), `CHANGELOG.md` (feature), `docs/FEATURES.md` (the bridge capability), `docs/README.md` (docs index — new reference doc). Add `docs/reference/umbrella-sso-integration.md` INDEX row.
5. **Gate (final, whole-plan):** `python scripts/final_gate.py --check --json` → `"status":"success"` AND `python scripts/enforcement/check_convergence.py`. A green gate is **necessary but not sufficient** — the Evidence below is the design proof.
6. **`/fabrik-review`** (native Opus — the teardown correctness is the criterion-#3 linchpin) → adjudicated exit; then **`/fabrik-docs-review`** on the new reference doc; **`/fabrik-features`** (the bridge capability shipped).
7. Commit + push.

**Behavior Contract:**
- **Given** a user with a live RP session and a Zitadel grant, **When** `revoke_and_teardown` runs, **Then** it deletes the authorization, invalidates the grant cache, AND terminates the user's Zitadel session (so back-channel logout fires) (libs/product_entitlements_bridge/teardown.py).
- **Given** a revoked grant, **When** the next boundary `has_access` check runs within the cache TTL, **Then** it DENIES (cache invalidated, source-checked) (libs/product_entitlements_bridge/teardown.py).
- **Given** an RP agent reads `docs/reference/umbrella-sso-integration.md`, **When** they follow it, **Then** they set `shape.needs_cache: true`, register `backchannel_logout_uri`, and wire session-termination-on-revoke (docs/reference/umbrella-sso-integration.md).

## Coverage Checklist

Classes derived from the rubric run over this plan's File Scope + the four standing recurrence classes:

```
$ python scripts/review_rubric.py --changed libs/product_entitlements_bridge/ tests/test_bridge_grant_source.py docs/reference/umbrella-sso-integration.md
# FLOOR: core/35-security-auth (PKCE+JWKS, no NextAuth/Clerk/Auth0, fail-closed auth.uid(), no secrets in code, sticky-sessions BANNED, redis session state), core/25-data-postgres (review migrations) → mapped to the rows below
```

Every known failure class swept this convergence (rubric classes for the File Scope + the four standing recurrence classes):

| Class | Verdict | Evidence |
|---|---|---|
| Claims grounding (fabrik-lib API signatures) | FIXED | pass 1 corrected `products_for`→`product_access(self,user_id)->frozenset[str]` async against `/opt/fabrik-lib/product-entitlements/product_entitlements/protocols.py:25`; gate API `has_access`/`revoke(user_id,product=None)` verified at `entitlements.py`; LocalAuthBridge at `oauth-login/oauth_login/protocols.py:35` |
| Fail-open vs fail-CLOSED (standing) | CLEAN | coarse access is fail-CLOSED — `product_access` RAISES on Zitadel/Redis error (Phase A behavior contract + Global Constraints); confirmed against product-entitlements `entitlements.py:60-64` (error source → deny) |
| Cost / quota limits (standing) | CLEAN — N/A | no paid LLM or metered API in scope (infra-decisions § Cost Guardrails N/A); reconciler + adapter call only self-hosted Zitadel |
| Boundary / sentinel / prefix traps (standing) | CLEAN | grant-cache keys are per-`(user,product)` policy-versioned + percent-encoded (product-entitlements `cache.py` — no delimiter collision); `revoke` invalidation is per-key |
| Behavior-without-a-test (standing) | CLEAN | each phase carries a Behavior Contract with watched-fail-first RED (grant-source fail-closed, reconciler zero-mutation-on-rerun, teardown three-call + deny) |
| Security / auth (rubric core/35) | CLEAN | federation = auth-code+PKCE+JWKS via oauth-login (subject-keyed, blocks nOAuth); machine auth = Private-Key JWT + reserved aud scope; zero secrets in code (env-only, Global Constraints) |
| Idempotency / no double-grant (rubric core/85) | CLEAN | reconciler = List→Create/Update (Create is non-idempotent, grounded); Phase B behavior contract asserts a second unchanged run makes ZERO mutations |
| Revocation → LIVE-session teardown | FIXED | grounded gotcha baked into Phase C: DeleteAuthorization is NOT a session-termination event, so `revoke_and_teardown` also calls `terminate_user_sessions` (the criterion-#3 linchpin) |
| Scope / cross-repo leak | CLEAN | File Scope hub-only (verified by the author-blind finder); per-RP work parked as dispatched follow-ups, not executed |
| Session-teardown realizability (re-review #3) | FIXED | `terminate_user_sessions` grounded to Session-v2 `ListSessions`→`DeleteSession` loop (machine-callable, `session.read`/`session.delete`; each Delete fires back-channel logout) — 2026-08-29 researcher |
| Ungrounded params: role_map / entitled_products (re-review #2) | FIXED | both defined as RP-supplied in the reference doc; `role_map` = per-RP product→role_keys config; reconciler is config-agnostic |
| Transport + deps unspecified (re-review #4) | FIXED | raw httpx JSON-over-Connect (mock via respx); `async-http-client` vendored for circuit-breaker; JWT dep named; deps-authorization flagged |
| Enqueue seam + audit async↔sync (re-review #5,#6) | FIXED | reference doc specifies queue+trigger+payload+worker-builds-client; `app-audit-log` named + the async `AuditSink.record`→sync `record_event` offload (`asyncio.to_thread`) documented |
| Module vendorability / home (re-review #1) | RECOMMENDATION | module README added (vendoring contract); cross-repo vendor path documented; the fabrik-lib-vs-hub-libs home is an operator recommendation (Residual #1), option (a) is the executable default — not a CONVERGED blocker |

## Evidence

```
$ ls /opt/fabrik-lib/oauth-login /opt/fabrik-lib/product-entitlements
# both exist (Active in fabrik-lib/README.md); oauth-login → VerifiedIdentity+LocalAuthBridge, product-entitlements → GrantSource/BillingSource/AuditSink gate
$ curl -sS --resolve auth.ocoron.com:443:172.93.160.197 https://auth.ocoron.com/.well-known/openid-configuration | python3 -c 'import sys,json;d=json.load(sys.stdin);print(d["issuer"], d["backchannel_logout_supported"])'
https://auth.ocoron.com True    # issuer LIVE, back-channel logout advertised (Epic-1 dependency satisfied)
```

- **Phase A** — `/opt/fabrik-lib/product-entitlements/product_entitlements/protocols.py:19,25` (`GrantSource` Protocol, real method `async def product_access(self, user_id: str) -> frozenset[str]` — the signature the adapter implements); Zitadel v2 `CreateAuthorization`/`ListAuthorizations` grounded at `zitadel.com/docs/reference/api/authorization/…` (fetched 2026-08-29, Connect paths, NOT `/v2/authorizations`); machine-auth reserved scope `urn:zitadel:iam:org:project:id:zitadel:aud` (`zitadel.com/docs/guides/integrate/zitadel-apis/access-zitadel-apis`, 2026-08-29).
- **Phase B** — `/opt/fabrik-lib/product-entitlements/product_entitlements/protocols.py:33,49` (`BillingSource.plan_features`, `AuditSink.record`); idempotency pattern grounded: `CreateAuthorization` is non-idempotent → `ListAuthorizations`-first, `UpdateAuthorization` is a full role-replace (zitadel docs, 2026-08-29).
- **Phase C** — the load-bearing gotcha: `DeleteAuthorization` is NOT a session-termination event → back-channel logout does not auto-fire on grant-revoke → teardown must call the Session API (`zitadel.com/docs/guides/integrate/back-channel-logout`, 2026-08-29); product-entitlements `revoke()` invalidates the fail-closed `GrantCache` (cache.py).

## Self-audit

- **Coverage (Phase-0 agreements → phase):** #5 LocalAuthBridge → the reference doc (Phase C) documents the per-RP impl (cross-repo, not hub-built); #6 reconciler → Phase B; #7 revocation teardown → Phase C `revoke_and_teardown`; #8 standalone coexistence → the doc states the RP keeps its `fastapi-user-auth` login and product-entitlements gates either way; needs_cache:true → asserted in the reference doc + per-RP follow-ups; Authorization v2 (not v1 AddUserGrant) → Phase A adapter. **Success criteria:** #1 (deploy/gate) per-RP; #2 (one login → entitled products) the LocalAuthBridge + gate pattern; #3 (revocation kills LIVE session) Phase C's session-termination — the corrected linchpin; #4 (idempotent reconciler) Phase B; #5 (cache never a JWT claim) fail-closed GrantCache; #6 (standalone) doc; #7 (federation security) oauth-login's PKCE+JWKS; #8 (audit) AuditSink. Gap check: criteria #2/#6/#7 are realized in per-RP code (cross-repo) — this plan delivers the SHARED pattern + reference they build against, which is the epic's hub scope.
- **Cross-phase signatures:** `ZitadelClient` (A) is consumed verbatim by B (`reconcile_user_grants(client, …)`) and C (`revoke_and_teardown(client, …)`); `terminate_user_sessions` is introduced in A and only C calls it — consistent.
- **Grounding passes:** read the two fabrik-lib module READMEs + the infra-decisions spec + the epic; one native-Opus researcher confirmed the Zitadel Authorization-v2 API live (corrected my `/v2/authorizations` guess to the Connect paths, and surfaced the session-termination gotcha). Fixed-point not yet claimed — that is `/fabrik-plan-review`'s job.

## Residual unknowns

**Resolved (this review's independent pass):** fabrik-lib deps exist (Active); Zitadel Authorization-v2 + **Session-v2 teardown loop** grounded (the criterion-#3 linchpin — `terminate_user_sessions` = `ListSessions`→`DeleteSession`, perms `session.read`/`session.delete`); the audit-log module IS `app-audit-log/` (name known now, + the async↔sync impedance documented in Phase C); `role_map` + `entitled_products` provenance defined (both RP-supplied, in the reference doc); the Connect transport specified (raw httpx JSON) + `async-http-client` vendored for resilience; Epic-1 issuer live.

**Still-open — ONE architecture recommendation the operator weighs BEFORE execution (#1, raised by the independent re-review). It does NOT block CONVERGED: option (a) below is the executable default the plan is written to, so the plan is build-ready as-is:**
- **Where the bridge lives: hub `libs/` vs a fabrik-lib module.** The epic's `owned_paths` place it in hub `libs/product_entitlements_bridge/`, but hub `libs/` is where the hub vendors modules IN for its own use — it is NOT a source RPs vendor FROM (the other three modules live in fabrik-lib and RPs `cp -r` from there). Consequences of the epic-literal path: RPs must vendor the bridge cross-repo from `/opt/fabrik/libs/` (works on the shared box, but inconsistent with the fabrik-lib pattern), and the **hub agent cannot create a fabrik-lib module** (cross-repo HARD STOP), so the "promote to fabrik-lib" is an unowned prerequisite, not a step this plan runs. **The plan builds it in hub `libs/` + a module README so it is at least self-describing + vendorable cross-repo — but the architecturally-correct home is a fabrik-lib `product-entitlements-bridge` module.** OPERATOR DECISION: (a) keep hub `libs/` (build here now, promote to fabrik-lib later — the plan is executable as-is); or (b) the module should be authored in fabrik-lib from the start → this plan's build shrinks to the reference doc + the fabrik-lib-module work dispatches to fabrik-lib's own agent (cross-repo). Recommend (b) for consistency; (a) is the no-block default.

**Dispatched cross-repo follow-ups (NOT executed here — each to its project's agents against the reference doc):**
- `youtube` · `transdoc` · `web-ecommerce-factory`: vendor the 4 modules; set `shape.needs_cache: true` + `fabrik apply`; implement the `LocalAuthBridge`; enqueue `reconcile_user_grants` on the PG job queue on billing events; register `backchannel_logout_uri` + validate the logout token; wire `revoke_and_teardown`.

## File Scope (owned paths)

- libs/product_entitlements_bridge/
- tests/test_bridge_grant_source.py
- tests/test_bridge_zitadel_client.py
- tests/test_bridge_reconciler.py
- tests/test_bridge_teardown.py
- docs/reference/umbrella-sso-integration.md

(Governance shared-append surfaces CHANGELOG.md / INDEX.md / docs/README.md / docs/FEATURES.md / docs/LESSONS_LEARNT.md are updated per the Doc Sync Matrix but stay OUT of File Scope — orchestrator-applied, outside the plan lock. Per-RP paths are cross-repo, owned by each RP.)
