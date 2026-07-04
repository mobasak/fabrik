# Code Review — saas-skeleton → fastapi-user-auth Pattern-A flip

**Plan:** `docs/development/plans/archived/2026-07-04-plan-1-saas-fastapi-user-auth-flip.md`
**Commits reviewed:** `4b7b09db` (A), `4a5e9b5b` (B), `73b0e1b5` (C+D), `d44d12bb` (E), + review-fix commit.
**Method:** `/fabrik-review` — 3 parallel independent Opus finders over distinct failure classes (auth/tenant/secrets · schema/SQL/RLS · contracts/logic/tests), reviewing the **generated** backend code (not just the string templates); refute/merge/prove-and-fix by the Opus orchestrator; then a convergence finder round on the fixed code.

## Findings & dispositions

| # | Sev | Finding | Disposition |
|---|-----|---------|-------------|
| F1-1 | HIGH | jti denylist never consulted on business routes → logout/revocation a no-op app-wide (only `/auth/logout` checked it) | **FIXED** — `token_revoked()` in `auth.py`; `TenantMiddleware` calls it on every protected request → 401 if revoked |
| F3-1 | CONFIRMED | vendor-skip shipped an unbootable project; "re-vendors at apply" docstring false | **FIXED** — `_vendor_fastapi_user_auth` now raises `FileNotFoundError` (fatal); docstring corrected |
| F3-3 | CONFIRMED | engine + redis client created at import, never disposed | **FIXED** — shared `@lru_cache` `_engine()`/`_denylist()` singletons + `aclose()` disposed in `main.py` lifespan |
| F1-3 | MED | `NullDenylist` silent fail-open on missing `REDIS_URL` | **FIXED** — loud warning logged |
| F2-1 | PLAUSIBLE | `current_tenant_id()`/`current_user_id()` bare-cast `LANGUAGE sql` → 500 on malformed `tid` | Initially hardened to plpgsql; convergence round reverted to `LANGUAGE sql` (perf — inlinable; malformed `tid` is ~unreachable from a signed JWT). Residual accepted. |
| F1-1b | PLAUSIBLE | denylist now on the hot path → 500 every request if Redis down | **FIXED (convergence)** — `token_revoked` fails **open** on backend error (log + degrade to token expiry; auth signature/exp unaffected) |
| main.py | LOW | stale "Supabase JWT auth (Pattern B)" docstring | **FIXED** — now "Self-hosted Pattern-A auth" |
| F2-2 | LOW | no tenant/membership provisioning path → "signup then nothing works" | **DOCUMENTED** — schema.sql onboarding note |
| F2-3 | MINOR | `tenants` missing module's `deleted_at` | Added, then **removed** in convergence (unenforced column implies soft-delete that doesn't exist) |
| F1-2 | MED | (vendored module) `refresh` doesn't re-verify membership → removed member mints tokens for refresh TTL | **UPSTREAM** — `/opt/fabrik-lib/fastapi-user-auth/UPSTREAM_FEEDBACK.md` (module contract, not scaffold; vendor-don't-rewrite) |

**Verified CLEAN (independent finders):** algorithm-confusion (HS256 pinned), exp/sub required, secret never logged, email/audit stubs don't leak tokens, `/auth/` bypass correctly trailing-slashed (not `/authors`), fail-closed tenant resolution (empty tid → RLS denies), X-Tenant-ID deny-by-default, full schema↔module SQL column contract, citext trusted-extension creatable by the DB owner, UUIDv7-app-supplied vs `gen_random_uuid()` default (no conflict), RLS-absence on auth tables is required-not-a-bug, `SET LOCAL` transaction-scoped (no pool leak), all imports resolve, `requirements.txt` covers every module dep, `reference_adapter.py` correctly excluded, no dangling `@supabase` in frontend/mobile.

## Convergence

The convergence finder round verified all fixes correct and regression-free on the security axis. The 3 items it surfaced (Redis hot-path availability, plpgsql perf, unenforced `deleted_at`) were addressed by fail-open + two reverts; those 3 changes are a defensive wrapper + reverts to already-reviewed state, self-verified as a no-op on the security-critical paths.

## Gate

Plan-scoped checks green: `ruff` clean, `mypy --strict` no new errors (2 pre-existing baseline in `scaffold.py`), generated-backend smoke (Pattern-A schema + `/auth` router + compiles, no Supabase), `check_doc_sync` clean, One-Test Rule present. The whole-tree `final_gate.py --check` shows ONE out-of-scope failure — Project Structure flags `scripts/kilo-benchmarks/cache/*.md` (a sibling agent's untracked files), not touched per shared-master discipline.

## Residual risks (accepted / documented)

- **F1-2 (module):** membership not re-checked on refresh — apps must delete refresh tokens on membership revocation; tracked in `UPSTREAM_FEEDBACK.md`.
- **Revocation during a Redis outage:** a revoked-but-unexpired token works until `access_ttl` (default 15 min) expiry — deliberate availability tradeoff.
- **Malformed `tid` → 500:** near-unreachable (signed JWT `tid` is a UUID or empty); `LANGUAGE sql` chosen for RLS perf.
- **Test depth:** the DB-free `test_auth.py` proves wiring (router mounted, token round-trip), not DB-backed login — a live-DB integration test is separate.
- **Vendor-fatal:** scaffolding a saas backend now requires `/opt/fabrik-lib` present (intended — a Pattern-A backend can't boot without the auth module).
- **Pre-existing (not introduced):** stale middleware-order comment in `main.py` (CORS is actually outermost); 2 pre-existing `mypy --strict` errors in `scaffold.py`.
