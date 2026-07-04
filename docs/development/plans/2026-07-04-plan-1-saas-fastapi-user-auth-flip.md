# Flip saas-skeleton (and mobile-app) from Supabase Auth (Pattern B) to self-hosted fastapi-user-auth (Pattern A)

Status: EXECUTED 2026-07-04 — Phases A–E done (4b7b09db, 4a5e9b5b, 73b0e1b5, + Phase E). All plan-scoped checks pass (ruff, mypy no-new-errors, generated-backend smoke, doc_sync, One-Test Rule). The whole-tree `final_gate.py --check` shows ONE remaining failure — Project Structure flags `scripts/kilo-benchmarks/cache/*.md` (the kilo-benchmarks sibling agent's untracked files), which is OUT of this plan's File Scope and must not be touched (shared-master discipline). Nothing of this plan's surface fails.
Owner: primary (AI)
Created: 2026-07-04
Converged: 2026-07-04 (grounding fixed point — every path:line re-read; final verification pass made zero edits)
Execution started: 2026-07-04

**fabrik-lib module assessment (2026-07-04) — NO module changes required.** Evaluated `fastapi-user-auth` against `.windsurf/rules` + infra: it already encodes our conventions — `core/25` (UUIDv7 `router.py:95`, asyncpg, citext), `core/35` (Argon2, jti denylist, refresh rotation, Pattern-A `access_ttl=900` `settings.py:18`), `saas/95` (native-mode RLS via `app.tenant_id`/`app.user_id` GUCs + `SET LOCAL`, fail-closed `rls/native.sql` — **identical** to the scaffold's own `current_tenant_id()` at `scaffold.py:1766`), env-driven (`env_prefix="AUTH_"`), no hardcoded infra. Its only Supabase references are in `rls/compat.sql` — the deliberate Pattern-B→A migration surface (keep it). All integration is scaffold-side. **Native-mode wiring for Phase B:** (a) vendor `fastapi_user_auth/` + apply `schema.sql` then `rls/native.sql`; (b) scaffold `current_tenant_id()` is redundant with native.sql's (identical) — apply native.sql's; (c) construct `Settings(database_url=os.getenv("DATABASE_URL"), redis_url=os.getenv("REDIS_URL"), jwt_secret=os.getenv("JWT_SECRET"))` explicitly in the emitted `auth.py` (our infra injects unprefixed vars; the module's `AUTH_` prefix stays generic — no module change); (d) `tenant.py` decodes the app's own access token (module `decode_access_token`) and sets both `app.user_id` + `app.tenant_id` (native mode), replacing `decode_supabase_jwt`.

**Phase-B resolution (2026-07-04) — schema reconciliation, blocker dissolved.**

The Phase-B blocker (raised: "scaffold's non-superuser role can't `CREATE EXTENSION citext`") was based on the scaffold's **outdated** comment at `scaffold.py:1744`. Verified: `citext.control` → `trusted = true`, and `postgres.py:409` (`ALTER DATABASE … OWNER TO "{db_user}"`) confirms the fabrik role **owns** the DB → a DB owner can create **trusted** extensions without superuser (PG13+; fleet is PG16). So `CREATE EXTENSION IF NOT EXISTS citext` succeeds. User initially chose "adapt schema to TEXT", but its precondition ("module doesn't hard-depend on citext") **failed** — `router.py:102,143` do `WHERE email = :e` on the **raw** email (no `lower()`), so citext is load-bearing for case-insensitive auth; a TEXT swap would force a module-code fork + risk duplicate accounts. **Resolved approach: keep the module's citext `users.email`, code-free vendor.** Reconciliation: keep the scaffold's richer `tenants` (slug/created_at/`gen_random_uuid`) + `widgets`/`jobs`/`current_tenant_id()` RLS untouched; ADD `CREATE EXTENSION citext`, `users` (citext email), `refresh_tokens`, `email_verify_tokens`, `password_reset_tokens`; point `memberships.user_id` at `users(id)`. User id is app-supplied UUIDv7 (`router.py:95`) so a `gen_random_uuid()` DDL default is a harmless fallback; `uuid_utils` is a pip dep (not an extension). Also fix the stale `:1744` comment.
Scaffold surface: `src/fabrik/scaffold.py`, `src/fabrik/spec_loader.py`, `templates/saas-skeleton/**`, `templates/mobile-app/**`

## Goal

Make **Pattern A** (the app is the sole IdP and issues its own JWTs, backed by the proven
`/opt/fabrik-lib/fastapi-user-auth` module — 55 tests, 9 projects) the **default** end-user
auth for the `saas-skeleton` scaffold, demote Supabase Auth (Pattern B) to a legacy/migration
opt-in, and scrub the `mobile-app` scaffold's client of direct-Supabase references (it must talk
only to the backend API). This is the code half of the org-wide Supabase retirement (docs already
reframed in `92df7be3`, `4e08eb2d`, `b7a50fca`; `.windsurf/rules/core/35-security-auth.md` already
names Pattern A the DEFAULT). Today the scaffold still *emits* Pattern B unconditionally, so a fresh
`saas-skeleton` contradicts the governance that says self-host is default.

## What we already agreed (source of truth — not invented)

- **One plan, three coupled sub-items** — user: *"One plan via /fabrik-plan-after-chat, scoped to all three sub-items … because they share the enum + the `_SAAS_AUTH_PY` generator — splitting them races on the same files."*
- **Vendor, don't rewrite** — user: *"the Pattern A backend already exists and is proven (/opt/fabrik-lib/fastapi-user-auth, 55 tests). The scaffold change is: swap `_SAAS_AUTH_PY` to vendor that module … drop `@supabase/*`."*
- **Acceptance = the scaffold's own output** — user: *"after generating a saas project from the changed scaffold, its generated test suite + a scaffold smoke test … must go green. That's the acceptance proof, not my say-so."* (Realized CLI-free — see Phase E; the review rules bar `fabrik …` in gates.)
- **Keep Supabase as legacy/migration-only** — `AuthType.SUPABASE` + `decode_supabase_jwt` stay, emitted only when a spec opts into Pattern B.
- **Rejected:** rewriting an auth backend from scratch (the module exists); flipping the *global* `Infrastructure.auth` default (G1).

## Grounding corrections (Phase-1 findings — the `Scope:` arg was materially off in five places)

- **G1 — no data-driven saas auth default exists; the default is hardcoded at generation time.** `src/fabrik/scaffold.py` contains **zero** `AuthType`/`infrastructure.auth` references (`grep` empty), and `templates/saas-skeleton/defaults.yaml` has **no `auth:` field** — only a `shape:` block whose *comments* mention Supabase. `spec_loader.py:199` (`Infrastructure.auth = AuthType.NONE`) is the **global** default for all 11 scaffolds — flipping it there is wrong. So "make Pattern A the saas default" = **change which `auth.py` the saas generator hardcodes** (Phase B), not set a config default. Global `Infrastructure.auth` stays `NONE`.
- **G2 — `auth.py` is written UNCONDITIONALLY; there is no branch to modify.** `scaffold.py:2681` → `(pkg_dir / "auth.py").write_text(_sub(_SAAS_AUTH_PY))` inside `_scaffold_saas_backend` (`:2648`), always Pattern B. The `_SAAS_AUTH_PY` string is `scaffold.py:1947-2042`. The plan **adds** a three-way selection (net-new), it does not edit an existing `if`.
- **G3 — the only apply-time auth branch is in compose, keyed on the spec.** The sole `infrastructure.auth` use is `templates/saas-skeleton/compose.yaml.j2:30` (`{% if infrastructure.auth.value == 'supabase' %}`), rendered by `fabrik apply` from the operator's `specs/services/<id>.yaml`. Scaffold-time `auth.py` and apply-time compose are **decoupled**; both must change.
- **G4 — the "inline package.json @3143" is FILE-API, not saas → out of scope.** `scaffold.py:3143` (`"@supabase/supabase-js": "^2.38.0"`) lives in `_scaffold_file_api` (`:3065`), not any saas/mobile path. The file-api Supabase migration is a **separate** effort; this plan does not touch it. The saas frontend's only `package.json` is `templates/saas-skeleton/package.json` (Phase C).
- **G5 — mobile-app has no auth feature and no `@supabase` SDK dep.** Only feature is `src/features/files`; `package.json` has no `@supabase` (`grep` empty). Its Supabase surface is `EXPO_PUBLIC_SUPABASE_*` in `.env.example:4-5` (a client-exposed key — itself a smell to remove) plus stale comments in `types.ts:6`, `fileService.ts:13,54,117`, and `AGENTS.md.j2:5`. Phase D is **env + comment cleanup**, not an auth-client rebuild.
- **G6 — `build_auth_router` needs three app-supplied collaborators (unchanged from DRAFT).** `build_auth_router(*, settings, sessionmaker, email: EmailSender, audit: AuditLogger, denylist: Denylist)` (`router.py:61-68`). Scaffold ships: a **Redis `Denylist`** (`async contains(jti)->bool`, `tokens.py:73`; `REDIS_URL` already wired in `compose.yaml.j2:27-28`), a minimal **`EmailSender`** (stdout/log stub, TODO→`email-transport`), and a minimal **`AuditLogger`** (structlog) — the module's `reference_adapter.py` impls depend on other fabrik-lib modules and are examples, not runtime deps (`requirements.txt` comment).
- **G7 — schema reconciliation.** Scaffold inline SQL (`scaffold.py:1754+`) has `tenants`, `memberships` (`user_id` = "Supabase auth.users.id"), `current_tenant_id()` RLS resolver. Module `schema.sql:7-44` has `tenants`, `users`, `memberships`, `refresh_tokens`, `email_verify_tokens`, `password_reset_tokens`. Pattern A means the app **owns `users`** → add `users` + three token tables, re-comment `memberships.user_id` → `users.id`, keep tenants/RLS.

## Context Ledger (binding sources — a fresh executor inherits full awareness here)

| Source | What binds | Grounded ref |
|---|---|---|
| `.windsurf/rules/core/35-security-auth.md` (ACTIVE) | Pattern A = DEFAULT self-host IdP; jti denylist, refresh rotation, Argon2, CORS never `*`+creds, generated-password policy | reframed in `92df7be3`; emitted backend must conform |
| `.windsurf/rules/saas/95-multi-tenant-saas.md` (ACTIVE) | tenant isolation via Postgres RLS, `app.tenant_id` propagation, cross-tenant deny-by-default | `scaffold.py:1766` `current_tenant_id()`; module `fastapi_user_auth/rls/` |
| `.windsurf/rules/core/15-api-contracts.md` (ACTIVE) | `/auth` routes: error schema, idempotency, versioning | `router.py:69` prefix `/auth` |
| `.windsurf/rules/core/25-data-postgres.md` (ACTIVE) | single async driver (asyncpg, psycopg2 banned), migrations/indexing, `postgres-main` not localhost | module `requirements.txt` (`asyncpg`, comment "psycopg2 is banned"); `schema.sql` |
| `.windsurf/rules/core/45-testing-strategy.md` (ACTIVE) | one test per highest-risk path; the generated suite is the acceptance gate | scaffold ships `tests/test_health.py` (`scaffold.py:1633`); Phase B adds `tests/test_auth.py` |
| **fabrik-lib `fastapi-user-auth/`** (VENDOR — don't build) | app-issued JWT auth + dual-mode tenant RLS. Public API `__init__.py:6-40`; `build_auth_router` `router.py:61-68`; `Settings.jwt_secret` required ≥32 chars `settings.py:17,23-28`; `Denylist` `tokens.py:73`; `schema.sql:7-44`. Runtime deps `requirements.txt`: `fastapi>=0.110`, `sqlalchemy[asyncio]>=2.0`, `asyncpg>=0.29`, `pyjwt>=2.8`, `argon2-cffi>=23.1`, `pydantic-settings>=2.2`, `pydantic[email]>=2.6`, `uuid-utils>=0.10`, optional `redis>=5.0` | read in full this turn |
| `AGENTS.md` infra invariant | shared `postgres-main`/`redis-main`, external `fabrik` net, per-service memory limit, no host `ports:`, stable DNS | compose gates assert unchanged |
| `templates/saas-skeleton/defaults.yaml` `shape:` | `is_admin_dashboard:false` (end-user auth ≠ Authelia), `needs_database:true`, `needs_cache:true` (denylist), `exposes_metrics:true` — **no `shape.*` flag flips** (Pattern A reuses the same DB+Redis); the sole Supabase-mentioning **comment** (line 9) updates; line 13's "token denylist" comment is already Pattern-A-compatible | `defaults.yaml:9` |

**fabrik-lib consult (mandatory):** `/opt/fabrik-lib/README.md` `fastapi-user-auth/` row = `Active`, exactly this capability → **vendor + adapt**. If Phase B uncovers a module bug, append to `/opt/fabrik-lib/fastapi-user-auth/UPSTREAM_FEEDBACK.md` (create if absent).

---

## Phase A — `AuthType` enum + legacy demotion (foundation; imported by B/C/D) — ✅ EXECUTED 2026-07-04

**Files:** `src/fabrik/spec_loader.py`. **Subagents:** none (single small file).

**Steps**
1. Add `FASTAPI_USER_AUTH = "fastapi_user_auth"` to `AuthType` (`spec_loader.py:75-79`); keep `NONE`, `SUPABASE` (its comment → "legacy / migration-only").
2. Leave the **global** `Infrastructure.auth = AuthType.NONE` (`:199`) untouched (G1). The saas default is enforced in Phase B (which `auth.py` is generated), not here.

**Gate (runnable from `/opt/fabrik`):**
```
python -c "from fabrik.spec_loader import AuthType, Infrastructure; assert AuthType.FASTAPI_USER_AUTH.value=='fastapi_user_auth'; assert AuthType.SUPABASE.value=='supabase'; assert Infrastructure().auth is AuthType.NONE; print('enum OK, global default still NONE')"
python -m mypy --strict src/fabrik/spec_loader.py   # Success
python -m ruff check src/fabrik/spec_loader.py       # All checks passed
```

**Phase boundary → BLOCKING `/fabrik-review`:** run the full `/fabrik-review` methodology (independent finder subagents in parallel for recall → refute → prove-before-fix with a kept test → correctness/security vs style → re-run gate after each fix) on the `spec_loader.py` diff **plus every caller of `AuthType`/`Infrastructure.auth`** (grep-enumerated). Phase B does not start until a demonstrably-thorough pass yields zero new correctness/security findings.

## Phase B — Backend flip in `scaffold.py` (vendor the module; the hard half) — ✅ EXECUTED 2026-07-04

**Files:** `src/fabrik/scaffold.py` — `_SAAS_AUTH_PY` (`1947-2042`), `_SAAS_SERVER_REQUIREMENTS` (`1720-1730`), membership SQL (`1754+`), `_scaffold_saas_backend` (`2648`, `auth.py` write `2681`), server-reqs write (`2662`). **Subagents:** dispatch three in parallel where independent — (i) the Pattern-A `auth.py` generator, (ii) schema reconciliation (`schema.sql`), (iii) the `tests/test_auth.py` generator — merged before the phase gate.

**Steps**
1. **Vendor the module.** In `_scaffold_saas_backend`, copy `/opt/fabrik-lib/fastapi-user-auth/fastapi_user_auth/` into the generated project's `server/` tree (vendored, not cross-imported — `fabrik-lib/README.md` rule). Merge the module's `requirements.txt` deps into `_SAAS_SERVER_REQUIREMENTS` (add `sqlalchemy[asyncio]>=2.0`, `argon2-cffi>=23.1`, `pydantic-settings>=2.2`, `pydantic[email]>=2.6`, `uuid-utils>=0.10`, `redis>=5.0`; `fastapi`/`asyncpg`/`pyjwt` already present).
2. **Replace the unconditional Pattern-B `auth.py` (G2) with a Pattern-A default.** New default `auth.py`: build `Settings`/`get_settings` (require `JWT_SECRET` ≥32 chars, no default — `settings.py:23-28`), `make_engine`/`make_sessionmaker` off `DATABASE_URL` (`postgres-main`), mount `build_auth_router(...)` at `/auth`, inject a **Redis `Denylist`** (`REDIS_URL`→`redis-main`), a stdout/log **`EmailSender`** (TODO→`email-transport`), a structlog **`AuditLogger`** (U3 resolved). Emit the legacy Pattern-B module as `auth_supabase.py` **only** when the (future) opt-in is set; keep `decode_supabase_jwt` + JWKS there.
3. **Reconcile schema (G7).** Emit the module `schema.sql` (tenants/users/memberships/refresh_tokens/email_verify_tokens/password_reset_tokens) as `server/db/schema.sql`, merged with `current_tenant_id()` RLS + the tenant-scoped example; re-comment `memberships.user_id` → `users.id`.
4. **Ship `tests/test_auth.py`** in the generated project (alongside `test_health.py`) — a smoke test that signs up + logs in + hits a `/auth`-gated route (the acceptance suite must actually exercise Pattern A, per `45-testing-strategy`).

**Gate (runnable from `/opt/fabrik`, CLI-free):**
```
python -m ruff check src/fabrik/scaffold.py          # All checks passed
python -m mypy --strict src/fabrik/scaffold.py        # Success (or no new errors vs baseline)
python - <<'PY'
import tempfile, pathlib
from fabrik.scaffold import _scaffold_saas_skeleton   # entrypoint @2687 (ground exact call signature in exec)
d = pathlib.Path(tempfile.mkdtemp())/"smoke"
_scaffold_saas_skeleton(d, "smoke", "smoke test")     # adjust kwargs to the real signature
srv = d/"server"
assert (srv/"fastapi_user_auth").is_dir(), "module not vendored"
sql = (srv/"db"/"schema.sql").read_text()
assert "users" in sql and "refresh_tokens" in sql, "schema not reconciled"
assert "supabase" not in (srv/"auth.py").read_text().lower(), "default auth.py still Supabase"
print("Pattern-A backend generated OK")
PY
```
Expected: vendored `server/fastapi_user_auth/`, reconciled schema, default `auth.py` is Pattern A (no Supabase), `/auth` mounted.

**Phase boundary → BLOCKING `/fabrik-review`** on the `scaffold.py` diff + the generated backend surface (parallel finder subagents; prove-before-fix; zero new correctness/security findings before Phase C/D).

## Phase C ∥ Phase D — run in PARALLEL after B (independent surfaces, disjoint files) — ✅ EXECUTED 2026-07-04 (inline; small disjoint template edits)

Phases C and D touch disjoint file sets (`templates/saas-skeleton/**` vs `templates/mobile-app/**`) and both depend only on A+B → **dispatch as two parallel subagent streams; merge at the Phase-E gate.**

### Phase C — saas-skeleton frontend templates (small, per G2)

**Files:** `templates/saas-skeleton/{package.json, .env.example, compose.yaml, compose.yaml.j2, defaults.yaml, app/api/health/route.ts, README.md, AGENTS.md}`.

**Steps**
1. `package.json:19-20` — remove `@supabase/supabase-js` + `@supabase/ssr`.
2. `app/api/health/route.ts` — replace the `supabase.from("profiles")` probe with a fetch to the backend health endpoint (real dep check, no `@supabase`).
3. `.env.example` + `README.md` — replace the Supabase block with `JWT_SECRET` (≥32), `DATABASE_URL=…postgres-main…`, `REDIS_URL=…redis-main…`; drop `NEXT_PUBLIC_SUPABASE_*`/`SUPABASE_SERVICE_ROLE_KEY`.
4. `compose.yaml` + `compose.yaml.j2:30-32` — replace the `auth=='supabase'` env branch with a three-way (`fastapi_user_auth`→`JWT_SECRET`/`REDIS_URL`; `supabase`→legacy `NEXT_PUBLIC_SUPABASE_*`; `none`→neither).
5. `defaults.yaml:9` — comment: end-user auth is **Pattern A (fastapi-user-auth)**; `is_admin_dashboard` stays false; no `shape` flag flips (line 13's "token denylist" comment already fits Pattern A).
6. `AGENTS.md:127` — "Supabase RLS policies" → app-owned Postgres RLS (`current_tenant_id()`).

**Gate:**
```
python -c "import json; d=json.load(open('templates/saas-skeleton/package.json')); assert not any('supabase' in k for k in d.get('dependencies',{})), d['dependencies']; print('no supabase deps')"
! grep -rIn 'NEXT_PUBLIC_SUPABASE\|SUPABASE_SERVICE_ROLE\|@supabase' templates/saas-skeleton/ ; echo "clean exit=$?"   # expect: no matches (the ! inverts so exit=0 means clean)
```

### Phase D — mobile-app: strip client-side Supabase (env + comments; G5)

**Files:** `templates/mobile-app/{.env.example, AGENTS.md.j2, src/features/files/types.ts, src/features/files/services/fileService.ts}`.

**Steps**
1. `.env.example:4-5` — remove `EXPO_PUBLIC_SUPABASE_URL` / `EXPO_PUBLIC_SUPABASE_ANON_KEY` (client must not hold DB creds); the app already talks to the backend API only.
2. `types.ts:6`, `fileService.ts:13,54,117`, `AGENTS.md.j2:5` — reword the "Supabase" comments to "the backend API (Pattern A) / Postgres record" (no behavior change; the client never called Supabase directly).

**Gate:**
```
! grep -rIn 'supabase\|Supabase\|SUPABASE\|@supabase' templates/mobile-app/ ; echo "clean exit=$?"   # expect no matches
```

**Phase boundary (C and D each) → BLOCKING `/fabrik-review`** on the respective template diff before Phase E consumes them.

## Phase E — Full gate + docs convergence (final; merges C∥D) — ✅ EXECUTED 2026-07-04

**Steps**
1. **Scaffold smoke (acceptance proof, CLI-free):** via `python` import of `_scaffold_saas_skeleton` (and the mobile entrypoint), generate real projects into temp dirs, run **their** `pytest` (`tests/test_health.py` + new `tests/test_auth.py`) + the generated project's `scripts/final_gate.py --lean --json`. Expected: `pytest` green + generated-project gate `"status":"success"`. (No `fabrik` CLI — the review rules bar it in gates; the scaffold Python API is the runnable path.)
2. **Doc Sync Matrix** (compute + do here): `CHANGELOG.md` (always); `docs/FEATURES.md` (auth capability change); env-var changes → `.env.example` + `docs/CONFIGURATION.md`; `templates/saas-skeleton/README.md` + `AGENTS.md` (done in C). No new compose service, no new port, no schema-in-this-repo → `docs/SERVICES.md`/`PORTS.md`/`db/schema.sql` untouched. `INDEX.md` only if a scaffold file is added/removed (the new `auth_supabase.py`/`test_auth.py` are *generated*, not repo files → no `INDEX.md` change).
3. **Fabrik-side gate:**
```
python scripts/final_gate.py --check --json      # Tier 2 (mypy+bandit+semgrep) — expect "status":"success"
python scripts/enforcement/check_convergence.py  # expect pass
```
4. **`/fabrik-docs-review`** to converge the touched docs to a truthful fixed point.

**A green gate is necessary, not sufficient** — the real proof is step 1 (a generated project boots Pattern A and its own tests pass).

---

## One-Test Rule

**Why:** The highest-risk path is the generated Pattern-A auth wiring. A scaffold that emits a broken `/auth` router, an unmountable app, or a token the tenant middleware can't decode would ship broken authentication to **every** new saas project — a silent, fleet-wide failure. The generated `tests/test_auth.py` guards exactly this seam.

**Contract:**
- **Given:** a saas backend generated from the flipped `scaffold.py`, with `JWT_SECRET` (≥32 chars) set and no live DB/Redis.
- **When:** the app builds the vendored `/auth` router (`build_saas_auth_router()`) and issues then decodes an access token (`issue_access_token` → `decode_token`).
- **Then:** the router exposes `/auth/login` + `/auth/signup`, and `decode_token` round-trips the `sub`/`tid` claims.
- **Mocked:** DB + Redis are NOT connected — `create_async_engine` is lazy and `REDIS_URL` unset → `NullDenylist`; the test asserts the *wiring* (router mounted, token round-trip), not DB persistence. DB-backed signup/login is a separate integration test needing a live `DATABASE_URL`.

## File Scope (owned paths)

- `src/fabrik/spec_loader.py`
- `src/fabrik/scaffold.py`
- `templates/saas-skeleton/{package.json,.env.example,compose.yaml,compose.yaml.j2,defaults.yaml,app/api/health/route.ts,README.md,AGENTS.md}`
- `templates/mobile-app/{.env.example,AGENTS.md.j2,src/features/files/types.ts,src/features/files/services/fileService.ts}`
- `CHANGELOG.md`, `docs/FEATURES.md`, `docs/CONFIGURATION.md`, `.env.example` (doc-sync, Phase E)
- **Explicitly OUT of scope (do not touch):** `_scaffold_file_api`/file-api Supabase (`scaffold.py:3065,3143` — separate migration, G4); `.windsurf/rules/**` (Fabrik-synced, already reframed); `scripts/kilo-benchmarks/**` + `.windsurf/rules/ai/**` (sibling agents' in-flight work); `/opt/fabrik-lib/fastapi-user-auth/**` except appending `UPSTREAM_FEEDBACK.md`.
- **Disjointness:** C-owned (`templates/saas-skeleton/**`) and D-owned (`templates/mobile-app/**`) are non-overlapping → safe to run in parallel. A/B own `src/fabrik/**` and must land before C/D.

## Evidence

**Phase A** — `spec_loader.py:75-79` (`AuthType` = `NONE`,`SUPABASE` only), `:199` (`auth: AuthType = AuthType.NONE`, global):
```
$ grep -n "class AuthType\|NONE\|SUPABASE\|auth: AuthType" src/fabrik/spec_loader.py
75:class AuthType(str, Enum):
78:    NONE = "none"
79:    SUPABASE = "supabase"  # Supabase Auth (Phase 1b)
199:    auth: AuthType = AuthType.NONE
```

**Phase B** — module API + deps; unconditional Pattern-B write:
```
$ grep -nA7 'def build_auth_router' /opt/fabrik-lib/fastapi-user-auth/fastapi_user_auth/router.py
61:def build_auth_router(*, settings, sessionmaker, email: EmailSender, audit: AuditLogger, denylist: Denylist)
$ sed -n '2648,2681p' src/fabrik/scaffold.py | grep -n 'auth.py\|_SAAS_AUTH_PY'
34:    (pkg_dir / "auth.py").write_text(_sub(_SAAS_AUTH_PY))    # scaffold.py:2681 — unconditional
$ grep -n "^_SAAS_AUTH_PY" src/fabrik/scaffold.py            # 1947 … closes 2042
$ sed -n '1,20p' /opt/fabrik-lib/fastapi-user-auth/requirements.txt   # sqlalchemy[asyncio], argon2-cffi, pydantic-settings, pydantic[email], uuid-utils, redis(opt)
```

**Phase C** — Supabase surface is deps+health+config only (no auth flow):
```
$ grep -rn 'createServerClient\|createBrowserClient' templates/saas-skeleton/    # (empty)
$ grep -n '@supabase' templates/saas-skeleton/package.json    # 19,20
$ grep -n "infrastructure.auth" templates/saas-skeleton/compose.yaml.j2    # 30 (only occurrence repo-wide in saas)
```

**Phase D** — mobile-app: no auth feature, no `@supabase` dep, only env+comments:
```
$ ls templates/mobile-app/src/features/           # files
$ grep -rn 'supabase\|Supabase\|SUPABASE' templates/mobile-app/
.env.example:4:EXPO_PUBLIC_SUPABASE_URL=...
.env.example:5:EXPO_PUBLIC_SUPABASE_ANON_KEY=...
src/features/files/types.ts:6:/** ... matching the Supabase schema */
src/features/files/services/fileService.ts:13,54,117: (comments)
AGENTS.md.j2:5: (comment)
```

**G4 (out of scope)** — `@supabase` @3143 is file-api:
```
$ awk 'NR<=3143 && /^def /{l=NR": "$0} END{print l}' src/fabrik/scaffold.py
3065: def _scaffold_file_api(...)
```

## Self-audit

- Grounding passes this turn (solo — surface already mapped; direct reads beat cold subagents on cost/accuracy): read `spec_loader.py:58-97,190-208`; `scaffold.py:1720-1730,1750-1770,1947-2042,2648-2687,3065,3108-3150`; module `__init__.py`/`router.py`/`settings.py`/`tokens.py`/`protocols.py`/`dependencies.py`/`reference_adapter.py`/`schema.sql`/`requirements.txt`; grepped saas-skeleton + mobile-app Supabase surface, compose branches, defaults.yaml, spec_generator.py; `select_rules.py` (ACTIVE packs), `fabrik-lib/README.md`.
- Corrected **seven** grounding items (G1–G7); the DRAFT's Phase B "inline package.json @3143" was a misattribution (file-api) and is removed; Phase D downgraded from "auth-client rebuild" to env+comment cleanup; Phase A stripped of the false "set saas default at line 199/defaults.yaml".
- Convergence: rewrite pass corrected G1–G7 (edits); a following pass fixed one `defaults.yaml:9,15`→`:9` citation (edit); the **final verification pass re-read every remaining `path:line` (`current_tenant_id@1766`, req-write@2662, `router.py:69`, membership@1754, backend@2648) and made ZERO edits** → fixed point reached. Every citation in this plan was opened and confirmed this turn.

## Residual unknowns

**Resolved:** module API + required env (`jwt_secret`≥32), Denylist/EmailSender/AuditLogger contracts + chosen impls (redis / stdout-stub / structlog — U3), Redis availability, schema delta, saas + mobile Supabase surface, file-api out-of-scope boundary, scaffold Python entrypoints for CLI-free smoke (`_scaffold_saas_skeleton@2687`).

**Still open — NON-BLOCKING (execution-time micro-decisions, not design gaps; each has a stated resolution):**
- **U1 — exact `_scaffold_saas_skeleton` / mobile entrypoint call signatures** (kwargs) for the Phase-B/E smoke harness. *Resolve:* read `scaffold.py:2687` + the dispatch table at `:140` in execution; adjust the `python -c` harness to the real signature (the gate is otherwise runnable). Does not block build — the entrypoint exists and is grounded.
- **U2 — the legacy Pattern-B opt-in mechanism.** With no data-driven auth selector today (G1), how an operator opts back into Supabase (spec field consumed at scaffold time vs a post-scaffold flag) is a one-line decision. *Resolve (already specified):* default = emit Pattern-A `auth.py`; emit `auth_supabase.py` + wire it when `infrastructure.auth == supabase` is threaded into `_scaffold_saas_backend` (add the kwarg) — decide during Phase B. The **default** path (Pattern A) is fully specified, so this does not block execution.

---

Converged. Next: **`/fabrik-execute-plan docs/development/plans/2026-07-04-plan-1-saas-fastapi-user-auth-flip.md`** (user-triggered — it mutates code, so it stays your call). U1/U2 are non-blocking execution-time decisions resolved in Phase B.
