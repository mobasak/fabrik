# Plan — the payments fulfilment-worker role in the hub registrar

Status: CONVERGED
Profile: small
**Owner:** —
Spec: `docs/superpowers/specs/2026-09-30-payments-fulfilment-role-design.md` (CONVERGED, D-464; approved for planning by D-652 item 4)
Work items: W-5985e74a (the build), W-7ba06610 (folded in by the spec), W-4b1dfd76 (folded in here)

## Goal

Implements spec § Goal: a project that vendors fabrik-lib `payments` and sets
`shape.needs_payments_fulfilment` gets a per-project `LOGIN NOSUPERUSER NOBYPASSRLS` fulfilment role,
granted by the module's own `payments_grant_fulfilment`, with `PAYMENTS_FULFILMENT_DATABASE_URL`
injected once by `fabrik apply`.

## What we already agreed

- The approach: spec § The delta — chosen approach (A: a new flag, delegate-only), items 1-7.
- The rejected alternatives B, C and D and their variants: spec § Rejected alternatives.
- The contract deltas: spec § Contract deltas (the optional flag, the new DSN variable, the driver's
  `mint_payments_role` / `grant_payments_role` split replacing `create_payments_ingest_role`,
  `DeploymentContext.registrar_warnings`).
- Lifecycle and the one ongoing maintenance cost (the hand-maintained signature constant): spec
  § Lifecycle.
- The validation battery: spec § Validation.
- The decisions already taken: spec § Decisions taken, recorded in D-464; the planning approval is
  D-652 item 4.
- From this run's brief (the operator's standing instruction to work the fleet queue, D-558/D-650):
  - (b1) fabrik-lib's open SB-096 (fabrik-lib D-399) will rework how `payments_grant_fulfilment` refuses
    a tenant-facing role. Phase A's first step re-checks the function's signature against fabrik-lib's
    then-current migration, and the spec's item 3.2 raise is the runtime tripwire.
  - (b2) The registrar mints auth roles, which is a heavy surface (lane row 1b), so each code phase
    boundary (A and B) takes the full `/fabrik-review`, and the whole-plan diff takes one more at Finish.
  - (b3) No step writes to a VPS. A live grant happens only at a consuming project's own next
    `fabrik apply`, behind that project's deploy gate.
- W-4b1dfd76, folded in: the refresh run's (`fabrik redeploy --refresh-infra`, `src/fabrik/cli.py:1220-1249`) failure (exit-2) branch also prints `registrar_warnings`,
  so a `pending` lane is never hidden by another registrar's failure (spec § The delta item 5's
  intent, applied to the fourth summary branch).

Grounding branch: **RICH** — a CONVERGED, approved spec pins the goal and the approach.

## Global Constraints

- Config is granular env vars only; no secret or constant in code (`.windsurf/rules/core/35-security-auth.md:267`).
- The generated password is 32 characters, `[a-zA-Z0-9]`, from `secrets.choice(string.ascii_letters + string.digits)` (`core/35-security-auth.md:322-323`); the existing driver helper already does this.
- One complete DSN per variable, never discrete host/port/user parts (`core/10-python.md:133`); the host is `postgres-main:5432`, rewritten for spokes exactly as the ingest DSN is, never `localhost`.
- Logs are structured, to stdout only; no file handler (`core/10-python.md:293-294`, Factor XI).
- Same backing services in dev and test: real PostgreSQL, never SQLite or a mocked session (`core/45-testing-strategy.md:58`, Factor X).
- Every test this plan adds is seen red first or red-on-revert (`core/45-testing-strategy.md:22`, `:237`).
- The minted role is never BYPASSRLS, never a member of a role that is, never the app or ingest role (`.windsurf/rules/saas/95-multi-tenant-saas.md:150`, `core/85-payments-billing.md:45`).
- No hub-written fallback grant; the module owns the grant (spec § Rejected alternatives, C).
- No VPS write, no live database, no ssh in any step or test.
- Factor XII: no migration runs from `lifespan` or startup; this plan adds none.

## Constraints Digest

| Quote | Source | Effect |
|---|---|---|
| "the owner runs `payments_grant_fulfilment('<worker role>'::regrole)` (fabrik-lib D-337) for a `LOGIN NOSUPERUSER NOBYPASSRLS` role." | `.windsurf/rules/core/85-payments-billing.md:45` | the role attributes the mint uses and the function the grant calls |
| "The worker login is never `<db>_app` or any tenant-facing role (the grant does not refuse one, and would hand the request path cross-org `jobs` access and `purchases` `INSERT` — the forgery `purchases` exists to stop), never the ingest role (the grant refuses it), never `BYPASSRLS`." | `.windsurf/rules/core/85-payments-billing.md:45` | a dedicated `<db>_payments_fulfilment` role, never an alias of an existing one (SB-096 is the module-side refusal still to come) |
| "so on BOTH connections also require `SELECT rolbypassrls, rolsuper FROM pg_roles WHERE rolname = current_user` to return false, false." | `.windsurf/rules/core/85-payments-billing.md:28` | the real-PG test asserts `rolbypassrls, rolsuper` false on the fulfilment login |
| "Keep `jobs` without RLS beyond what the module's grant functions provision (module README § Gotchas)" | `.windsurf/rules/core/85-payments-billing.md:27` | the test schema keeps `jobs` without extra RLS |
| "The request path's login role holds no `BYPASSRLS` and is a member of no role that does." | `.windsurf/rules/saas/95-multi-tenant-saas.md:150` | no membership is granted between the payments roles |
| "The fulfilment worker never uses it: it runs as its OWN scoped login granted by the module's `payments_grant_fulfilment` — never the tenant app role — and claims each job before scoping to its `org_id`" | `.windsurf/rules/saas/95-multi-tenant-saas.md:151` | the real-PG test claims a `jobs` row with no tenant GUC, then scopes |
| "=> Mandate: config via env vars only (`os.getenv("KEY", "default")`); **ZERO secrets/constants in code**." | `.windsurf/rules/core/35-security-auth.md:267` | the password is generated at mint time and delivered through `.env` only |
| "**32 characters**, charset `[a-zA-Z0-9]` only (no symbols — survives `.env` round-trip + shell quoting)." | `.windsurf/rules/core/35-security-auth.md:322` | the mint reuses the driver's existing CSPRNG helper |
| "**A credential GENERATED during init goes stale the instant it is generated.**" | `.windsurf/rules/core/30-ops.md:230` | mint, deliver, then grant: the DSN is injected before the grant can raise (spec § The delta item 2) |
| "Discrete `DB_HOST`/`DB_PORT`/`DB_NAME`/`DB_USER`/`DB_PASSWORD` for the app to assemble are **banned**." | `.windsurf/rules/core/10-python.md:133` | one complete `PAYMENTS_FULFILMENT_DATABASE_URL` |
| "**BANNED:** `logging.FileHandler`, `logging.handlers.RotatingFileHandler`, `TimedRotatingFileHandler`, `loguru` file sinks, any `*.log` file write" | `.windsurf/rules/core/10-python.md:294` | the pending warning is a stdout log line plus the CLI summary line, never a file |
| "- **Zero-mock database policy**: never mock SQLAlchemy, SQLModel, or database sessions. All backend tests execute against a real PostgreSQL instance." | `.windsurf/rules/core/45-testing-strategy.md:58` | the grant behaviours are proven on real PostgreSQL through `scratch_pg()`; unit tests mock only the driver boundary the orchestrator calls |
| "a non-trivial behavior's test proves something only if it has been SEEN RED" | `.windsurf/rules/core/45-testing-strategy.md:22` | every phase's new tests are seen red before the code lands |
| "is never the only thing between the agent and an irreversible act." | `.windsurf/rules/ai/50-agentic.md:49` | matched by glob on `orchestrator/` only: this change adds no agent loop and no model call, so the pack binds nothing here |
| "**Tier-1 (author → verify → converge; the author leg is NATIVE while the pool is OFF, D-181 — `scripts/doc_reconcile.py`'s pool author cannot dispatch):**" | `.windsurf/rules/core/40-documentation.md:56` | Phase C's `docs/CONFIGURATION.md` edit is reconciled through `scripts/doc_reconcile.py` with a native author leg, verify before apply |

## Context Ledger

| Source | What binds | Grounded ref |
|---|---|---|
| `.windsurf/rules/core/85-payments-billing.md` (AVAILABLE, names this feature) | the role shape, the grant call, the `rolbypassrls/rolsuper` check | `:27`, `:28`, `:45` |
| `.windsurf/rules/saas/95-multi-tenant-saas.md` | no BYPASSRLS, no membership, worker claims then scopes | `:150`, `:151` |
| `.windsurf/rules/core/35-security-auth.md` (FLOOR) | secrets and generated passwords | `:267`, `:322-323` |
| `.windsurf/rules/core/25-data-postgres.md` (FLOOR) | the postgres registrar creates the project's database and roles on `fabrik apply`; the pack's Alembic rule (`:94`) governs a project's schema, and this plan adds no schema change. Treating the role DDL as registrar work, as the ingest role already is, is this plan's reading, not a quoted carve-out | `:336-338` (§ Spec contract — postgres registrar) |
| `.windsurf/rules/core/30-ops.md` (FLOOR) | credential propagation | `:230-232` |
| `.windsurf/rules/core/10-python.md` (MATCHED) | stdout logging, one complete DSN | `:133`, `:293-294` |
| `.windsurf/rules/core/45-testing-strategy.md` | real PostgreSQL, red first | `:22`, `:58`, `:237` |
| `.windsurf/rules/ai/50-agentic.md` (MATCHED by glob on `orchestrator/`) | not applicable: no agent loop or model call in this change | glob match only |
| fabrik-lib `payments` (vendored by consumers, called by the hub) | `payments_grant_fulfilment(r pg_catalog.regrole)`; the six tables plus `jobs`; refusals; the `payments_fulfilment_ins` policy — **vendor, don't build** | `/opt/fabrik-lib/payments/db/migrations/2026-09-29-scoped-service-roles.sql:462-463` (signature), `:485-486` (tables), `:523-537` (lane refusal), `:575-590` (policy), `:592-638` (leak postcondition); `schema.sql:838-1018` identical |
| fabrik-lib `verify_service_role` | `lane="fulfilment"` supported | `/opt/fabrik-lib/payments/payments/store.py:412-417` |
| `agents-fabrik.md` infra invariant | `postgres-main:5432` on the `fabrik` network; spokes reach it over the mesh | `agents-fabrik-core.md` § Fleet; the ingest block's spoke rewrite at `src/fabrik/orchestrator/infrastructure.py:871-907` |
| `specs/services/<id>.yaml` `shape.*` | one new optional flag; 0 of 69 specs set either payments flag today | spec § Personas (counted 2026-09-30); no spec changes in this plan |
| `docs/data-contract.md` / `docs/ui-design.md` | none for this surface (spec § Contract deltas) | — |

fabrik-lib consult: the grant is vendored behaviour (the module's function), and the hub builds only the
role minting, DSN delivery and status reporting, which only the hub can do (spec § fabrik-lib verdict).
No `🆕 fabrik-lib candidate`.

## Execution Discipline (binding on /fabrik-execute-plan)

- **Size and shape** — the estimated code diff is about 250 lines over 5 code files (`postgres.py` ~150,
  `infrastructure.py` ~60, `cli.py` ~20, `spec_loader.py` ~15, `context.py` ~2; tests excluded), inside
  the `Profile: small` bound of ~400 lines and 5 files. The appetite total (280 minutes) is past the
  profile's one-hour floor, so the shape decision was taken here, not skipped. The plan stays a monolith of three
  sequential phases: one interface chain runs A → B → C, so a ticket set would add an Integration ticket
  and nothing could run in parallel. The review weight goes up instead (next bullet).
- **Review floor** — Phases A and B (the auth-role code) each run the full `/fabrik-review` on their
  changed surface before their commit, to a closing pass that confirms zero (brief item b2, lane row
  1b). Phase C (docs only) runs `/fabrik-review-scoped`. The Finish runs one more full `/fabrik-review`
  over the whole-plan diff, with its receipt at
  `docs/development/reviews/2026-10-08-plan-2-payments-fulfilment-role-review.md`. No phase commits on a
  first-pass green.
- **Dispatch policy** — native Claude seats for every fan-out (the pool is OFF, D-181): for Phases A and B
  and the Finish, the full review's seats from `dispatch_headroom.py` (its file-partition form, or
  `--units <groups>` for the D7 floor at Finish); for Phase C the scoped review's three-reader floor, all, stamped with `command_run.py dispatch` before it
  goes out. Coding is inline by the orchestrator (`Profile: small`); Haiku never codes.
- **Parallelism + merge** — phases are sequential (B consumes A's driver interface, C documents both).
  Inside a phase the review seats run in parallel and merge in the orchestrator's adjudication; the real-PG
  tests and unit tests of a phase run together in one pytest call.

## Phase A — Driver: mint, deliver, grant for both payments lanes; the flag

Appetite: 120
Implements spec § The delta items 1, 2, 3, 4, 6.

**Interfaces**
- Consumes: `_run_sql` (`src/fabrik/drivers/postgres.py:111`); `_PAYMENTS_GRANT_INGEST_FN`
  (`:776`); `_payments_grant_ingest_block` (`:851`); `_payments_grant_path_sql` (`:886`);
  `drop_database` (`:1691`, ingest drops at `:1756`, `:1779`).
- Produces:
  - `mint_payments_role(db_name: str, lane: Literal["ingest", "fulfilment"], dry_run: bool = False) -> dict` returning `{"user": str, "password": str | None, "status": str}`.
  - `grant_payments_role(db_name: str, lane: Literal["ingest", "fulfilment"], dry_run: bool = False) -> dict` returning `{"grants": "module" | "legacy" | "pending"}` and raising on `unknown`, a refusal, or the pre-migration, changed-signature and missing-`jobs` states.
  - `_PAYMENTS_GRANT_FULFILMENT_FN = "payments_grant_fulfilment(pg_catalog.regrole)"`, beside the ingest constant.
  - `Shape.needs_payments_fulfilment: bool = False` in `src/fabrik/spec_loader.py`, with a validator requiring `needs_database` (beside `:340-352` and `:401-411`).
  - `create_payments_ingest_role` is removed; its 17 references in 6 `.py` files under `src/` and `tests/` move to the new pair.

**Steps**
1. Tripwire for SB-096 (brief item b1). Run
   `grep -n "CREATE OR REPLACE FUNCTION payments_grant_fulfilment" /opt/fabrik-lib/payments/db/migrations/*.sql`.
   Expect exactly one hit, at `2026-09-29-scoped-service-roles.sql:462`, with the argument `r pg_catalog.regrole`.
   If a newer migration redefines it, or the signature differs, STOP: that is an unresolvable contradiction
   with spec § The delta item 3.2. Report `BLOCKED:` naming the new migration, and do not code against a stale constant.
2. Write the failing tests first (TDD for the risky path), in a new
   `tests/test_payments_fulfilment_real_pg.py` on the `scratch_pg()` pattern
   (`tests/test_app_role_real_pg.py:100-113`, the same skip rule) over fabrik-lib's real schema. One test per spec § Validation first bullet:
   - the function path grants, and the fulfilment login then claims a `jobs` row (`FOR UPDATE SKIP LOCKED`, `UPDATE`) with no tenant GUC, scopes with `set_config('app.tenant_id', …, true)`, and inserts `purchases`;
   - `verify_service_role(conn, lane="fulfilment")` passes on that connection, and `SELECT rolbypassrls, rolsuper` returns `false, false`;
   - payments tables without `jobs` raise, naming `jobs`;
   - no schema, and a partial schema, both return `pending`;
   - a pre-migration install (function dropped, tables present) raises, naming the migration;
   - a function present under a changed signature raises the changed-signature error, never the pre-migration one;
   - a PUBLIC `payments_fulfilment_ins` refuses;
   - upgrade ordering: a legacy-granted ingest install, migrated, grants both lanes in one run with ingest first;
   - the fulfilment role is not a member of the ingest role;
   - a failing grant still returns the minted password from `mint_payments_role` for both lanes (the item 2 regression).
   Gate: `.venv/bin/python -m pytest -q tests/test_payments_fulfilment_real_pg.py` → every test FAILS (the
   functions do not exist yet); record the red output.
3. Add the flag and its validator to `src/fabrik/spec_loader.py`, following `needs_payments_ingest`
   (`:340-352`, `:401-411`). Add two unit tests to `tests/test_payments_ingest_role.py` (the file keeps its name): "the Shape
   validator refuses the flag without `needs_database`", and "the 63-character guard refuses an over-long
   database name for the fulfilment role name, whose suffix is 4 characters longer than the ingest one, at
   the boundary length", beside `test_role_name_and_63_char_guard`.
4. Implement in `src/fabrik/drivers/postgres.py`:
   - `mint_payments_role` (CREATE ROLE … LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS, a password
     on create only, CONNECT and USAGE on `public`, no membership; spec item 2);
   - `grant_payments_role` dispatching on `lane`: the ingest batch keeps `_payments_grant_ingest_block`;
     the fulfilment batch is the one DO block in spec item 3's order (3.1-3.5), both ending in the path
     SELECT, parsed as the last stdout line, with `unknown` raising (spec item 4);
   - the 63-character role-name guard for both names;
   - `drop_database` drops `{db}_payments_fulfilment` beside the ingest role in both branches (spec item 6).
   Gate: `.venv/bin/python -m pytest -q tests/test_payments_fulfilment_real_pg.py tests/test_payments_ingest_real_pg.py` → all pass.
5. Move every caller and test of `create_payments_ingest_role` to the new pair. Expect 17 lines in 6
   files today: `src/fabrik/orchestrator/infrastructure.py` (2), `src/fabrik/spec_loader.py` (1, a
   docstring), `src/fabrik/drivers/postgres.py` (3), `tests/test_payments_ingest_real_pg.py` (1),
   `tests/test_app_role_provision.py` (1), `tests/test_payments_ingest_role.py` (9). The orchestrator call
   becomes mint then grant, with no behaviour change yet (Phase B adds the fulfilment block).
   Gate: `grep -rn --include='*.py' create_payments_ingest_role src tests | wc -l` → `0`.
6. Red-on-revert for each new behaviour, in a throwaway worktree (`git worktree add <scratch>/probe HEAD`,
   never the shared checkout): neuter each guard (the `jobs` raise, the changed-signature branch, the
   `unknown` raise, the fulfilment drop, the mint-before-grant ordering) and watch its test fail; remove the worktree.
7. Closing sequence:
   1. `.venv/bin/python -m pytest -q tests/test_payments_fulfilment_real_pg.py tests/test_payments_ingest_real_pg.py tests/test_payments_ingest_role.py tests/test_app_role_provision.py tests/test_app_role_driver.py` → all pass;
   2. `python3 scripts/enforcement/check_doc_sync.py` → no missing doc for this phase's paths (the docs land in Phase C; record any reported pair for C);
   3. the full `/fabrik-review` on Phase A's changed surface plus its callers, to a closing pass that confirms zero;
   4. commit the phase with explicit paths and the provenance trailers.

**Behavior Contract**
- **Given** fabrik-lib's schema and `jobs` in `public`, **When** `grant_payments_role(db, "fulfilment")` runs, **Then** it returns `module` and the fulfilment login can claim a job without a tenant GUC, scope, and insert a purchase (`tests/test_payments_fulfilment_real_pg.py`, new; spec § Validation)
- **Given** the payments tables but no `jobs`, **When** the fulfilment grant runs, **Then** it raises naming `jobs` (spec § The delta item 3.4)
- **Given** no payments schema or a partial one, **When** the fulfilment grant runs, **Then** it returns `pending` (spec § The delta items 3.1, 3.3)
- **Given** a function of that name under a different signature, **When** the fulfilment grant runs, **Then** it raises the changed-signature error, never the pre-migration one (spec § The delta item 3.2)
- **Given** a grant batch that raises, **When** `mint_payments_role` ran first, **Then** the caller already holds the password for either lane (spec § The delta item 2)
- **Given** a spec with `needs_payments_fulfilment: true` and no `needs_database`, **When** it loads, **Then** validation fails (a new validator beside the ingest one at `src/fabrik/spec_loader.py:401-411`)
- **Given** the granted fulfilment login, **When** `verify_service_role(conn, lane="fulfilment")` and `SELECT rolbypassrls, rolsuper` run on it, **Then** the check passes and both read `false` (`.windsurf/rules/core/85-payments-billing.md:28`)
- **Given** the granted fulfilment role, **When** its role memberships are read, **Then** it is not a member of the ingest role (spec § The delta item 2, no membership; spec § Validation)
- **Given** a `payments_fulfilment_ins` policy widened to PUBLIC, **When** the fulfilment grant runs, **Then** it refuses (spec § Validation)
- **Given** a legacy-granted ingest install with the migration applied, **When** one apply runs, **Then** both lanes grant, ingest first (spec § The delta item 5; migration `:592-638`)
- **Given** a database name at the boundary length, **When** the fulfilment role name is built, **Then** the 63-character guard refuses the over-long name (spec § The delta item 2)
- **Given** a database with both payments roles, **When** `drop_database` runs, **Then** both roles are dropped in either branch (`src/fabrik/drivers/postgres.py:1756`, `:1779`)

## Phase B — Orchestrator, context and CLI: inject before grant, status from the path, warnings shown

Appetite: 100
Implements spec § The delta item 5; folds in W-7ba06610 and W-4b1dfd76.

**Interfaces**
- Consumes: Phase A's `mint_payments_role`, `grant_payments_role` and `Shape.needs_payments_fulfilment`;
  `resolve_applicability` (`src/fabrik/orchestrator/infrastructure.py:216`, ingest row `:250-263`);
  the ingest block (`:871-907`); `ctx.add_resource`; `self._nonfatal`; `DeploymentContext`
  (`src/fabrik/orchestrator/context.py:22`, `registrar_failures` at `:66`); the CLI summaries
  (`src/fabrik/cli.py:530-546` apply, `:1282-1292` refresh).
- Produces:
  - `DeploymentContext.registrar_warnings: list[str]` (default empty).
  - a `payments_fulfilment` row from `resolve_applicability`, unprinted (`_REGISTRAR_ORDER` at `:156-167` names neither payments row).
  - the fulfilment block after the ingest block, each injecting its DSN on a fresh password only and BEFORE its grant, each recording its resource from the grant path.
  - `PAYMENTS_FULFILMENT_DATABASE_URL`, rewritten for spokes exactly as `PAYMENTS_INGEST_DATABASE_URL` is.

**Steps**
1. Failing unit tests first, in `tests/test_app_role_provision.py` (the existing ingest-block harness at `:113-143`), mocking only the driver boundary:
   - `resolve_applicability` reports the `payments_fulfilment` row for the flag with `needs_database`, and not without it;
   - the DSN is injected only on a fresh password, and before the grant is called (assert call order);
   - for both roles: `module`/`legacy` record `provisioned`; `pending` records `pending`, logs a WARNING and appends one `registrar_warnings` line; `unknown` and every raise record `failed` through `_nonfatal`; a dry run records `dry_run`;
   - the ingest block runs before the fulfilment block.
   Gate: `.venv/bin/python -m pytest -q tests/test_app_role_provision.py` → the new tests FAIL; record the red.
2. Add `registrar_warnings` to `src/fabrik/orchestrator/context.py` beside `registrar_failures`.
3. In `src/fabrik/orchestrator/infrastructure.py`: the applicability row; the fulfilment block after
   the ingest block; for both blocks, mint, inject, then grant, and record the resource from the path
   (this closes W-7ba06610, whose unconditional `provisioned` sits at `:895-899`).
4. In `src/fabrik/cli.py`, print each `registrar_warnings` line as `⚠ <line>` in every summary a completed
   run prints: the `fabrik apply` exit-0 branch (`:546`), its exit-2 branch (`:537-545`), the
   `fabrik redeploy --refresh-infra` ✅ branch (`:1293`), and its exit-2 branch at `:1282-1292`
   (W-4b1dfd76). Unit tests for all four branches go in
   `tests/orchestrator/test_registrar_failures_not_green.py`, which already asserts the four summaries
   (`✅ Deployment complete` at `:179`/`:185`, `✅ Infrastructure refreshed` at `:212`/`:218`).
5. Red-on-revert in a throwaway worktree: neuter the inject-before-grant order, the `pending` → warning
   path, and each of the four print sites; watch each test fail; remove the worktree.
6. Closing sequence:
   1. `.venv/bin/python -m pytest -q tests/test_app_role_provision.py tests/test_payments_ingest_role.py tests/test_payments_fulfilment_real_pg.py tests/orchestrator/test_registrar_failures_not_green.py` → all pass;
   2. `python3 scripts/enforcement/check_doc_sync.py` → record pairs for Phase C;
   3. the full `/fabrik-review` on Phase B's changed surface plus one hop, to a closing pass that confirms zero;
   4. commit the phase with explicit paths and the provenance trailers.

**Behavior Contract**
- **Given** a spec with `needs_payments_fulfilment` and `needs_database`, **When** `resolve_applicability` runs, **Then** it reports the `payments_fulfilment` row (`src/fabrik/orchestrator/infrastructure.py:250-263`)
- **Given** a freshly minted fulfilment role, **When** the block runs, **Then** `PAYMENTS_FULFILMENT_DATABASE_URL` is injected before the grant is attempted (`src/fabrik/orchestrator/infrastructure.py:871-907`)
- **Given** a grant path of `pending` for either role, **When** the block records its resource, **Then** it records `pending` and adds one `registrar_warnings` line, and the apply exits 0 (spec § The delta item 5)
- **Given** a grant that raises or returns `unknown`, **When** the block records its resource, **Then** it records `failed` and the apply exits 2 (spec § The delta item 5)
- **Given** a `registrar_warnings` line, **When** `fabrik apply` or `fabrik redeploy --refresh-infra` ends on success or on registrar failure, **Then** the line is printed as `⚠` in that summary (`src/fabrik/cli.py:546`, `:537-545`, `:1293`, `:1282-1292`)

## Phase C — Docs, the build's decision row, and the Finish

Appetite: 60
Implements spec § Documentation landing sites, § Contract deltas (the docs half).

**Interfaces**
- Consumes: Phases A and B's names, exactly as produced above.
- Produces: the documentation, the build's D-row, the infra mail, the Finish receipt.

**Steps**
1. `docs/CONFIGURATION.md`: add a `PAYMENTS_FULFILMENT_DATABASE_URL` section beside the ingest section
   (`:231-235`), and rewrite the sentence at `:237` ("The fulfilment WORKER does NOT use this role …") to
   point at the new role. Reconciled through `scripts/doc_reconcile.py` (native author leg, the pool is OFF), verify before apply.
2. `docs/reference/modules/drivers.md:31`: the `postgres.py` row names `mint_payments_role` and
   `grant_payments_role` in place of `create_payments_ingest_role`.
3. Orchestrator-applied ledgers (outside File Scope by rule): `CHANGELOG.md` (one entry), the build's
   `docs/DECISIONS.md` row (minted with `python3 scripts/decisions.py --reserve-id .` inside the commit
   shell, citing D-464 and D-652), `INDEX.md` rows for `tests/test_payments_fulfilment_real_pg.py`.
4. Mail infra (its beat; never edited by fleet) with the new flag, variable and commit, naming the
   lines that go stale when this lands: `.windsurf/rules/core/85-payments-billing.md:28` (the ingest flag
   only), `:45` (already names `shape.needs_payments_fulfilment` and `PAYMENTS_FULFILMENT_DATABASE_URL`, but
   says the login "does not exist yet" and is "awaiting design approval"), and
   `.windsurf/rules/saas/95-multi-tenant-saas.md:151`. The spec's landing-site list names `:28` only; `:45`
   is added here because its qualifier goes stale.
5. `/fabrik-docs-review` over the plan's changed docs, to a truthful fixed point.
6. The Finish heavy round: the full `/fabrik-review` over the whole-plan diff (D7 floor via
   `dispatch_headroom.py --units <groups>`, stamped first), receipt at
   `docs/development/reviews/2026-10-08-plan-2-payments-fulfilment-role-review.md`, every class
   CLEAN/FIXED/REFUTED/RECORDED and a closing pass that confirms zero.
7. Close W-5985e74a, W-7ba06610 and W-4b1dfd76 with `work.py done <id> --evidence <the commit naming it>`.
8. Final step: `.venv/bin/python scripts/final_gate.py --check --json` → `"status": "success"`, and
   `python3 scripts/enforcement/check_convergence.py` → clean. A green gate is necessary but not
   sufficient: it proves format and citations, not the design; the Evidence and the review receipt carry the proof.
9. Closing sequence:
   1. the gate above → green;
   2. `python3 scripts/enforcement/check_doc_sync.py` → clean;
   3. `/fabrik-review-scoped` on Phase C's own doc changes (the Finish heavy round covers the code), to a closing pass that confirms zero;
   4. commit with explicit paths and the provenance trailers; push; `scripts/merge_request.py request --review <the receipt>`.

**Behavior Contract**
- **Given** the new variable, **When** an operator reads `docs/CONFIGURATION.md`, **Then** it documents `PAYMENTS_FULFILMENT_DATABASE_URL` and no longer says the worker has no role (`docs/CONFIGURATION.md:237`)
- **Given** the driver change, **When** a reader opens `docs/reference/modules/drivers.md:31`, **Then** it names `mint_payments_role` and `grant_payments_role`

## Coverage Checklist

Armed from this run over the File Scope entries (the changed-path set):

```
$ python3 scripts/review_rubric.py --changed <the File Scope entries>
# REVIEW RUBRIC — inject into EVERY finder prompt (generated by review_rubric.py)
# Honesty (L1): this arms the review — it raises compliance probability, it does not guarantee it.

## FLOOR — always injected, regardless of glob (spec L3; SERVICE surface)

### core/35-security-auth.md
**The default for ALL new projects, including user-facing SaaS + mobile.** Vendor `fabrik-lib/fastapi-user-auth`: the app issues its own JWTs — **Argon2id** (the vendored argon2-cffi defaults meet OWASP minimums; never Argon2i) + timing-equalized login, atomic refresh-token rotation (`DELETE … RETURNING`), JWT `jti` denylist revocation, and dual-mode tenant-isolation RLS. Supabase is retired as a default (see `agents-fabrik.md § Supabase`); reach for Pattern B only for a project that *already* runs on Supabase Auth.
- Do not use NextAuth.js, Clerk, Auth0, or Firebase Auth.
- ADDITIONAL affordance a project justifies, never the default door.
- project files the fabrik-lib request FIRST, never hand-rolls WebAuthn.
| `chrome-extension` | ✅ **use this** | ⚠️ only via `chrome.identity.launchWebAuthFlow` + the `https://<ext-id>.chromiumapp.org/` redirect the pack already mandates; a bare mailed link lands in a TAB that cannot reach `chrome.storage.session` |
| `desktop-app` | ✅ **use this** | ⚠️ needs a registered custom protocol handler; the token then goes to `safeStorage` (`desktop-app/72-desktop.md`) |
- service MUST be able to say which:
| **Another Fabrik service** (Docker-to-Docker on the `fabrik` network) | `X-Internal-Token` + `internal_auth.py`, `hmac.compare_digest`, 403 on reject | § Internal Service Auth (M2M) below — **never** an inline `APIKeyHeader`, never a per-service key name |
- An approval link opened somewhere the user did not start must never mint a session silently.
- > **Fail-closed invariant (hard, every mode).** `auth.uid()` and `current_tenant_id()` MUST return `NULL` (→ the policy denies) on unset, empty, or malformed claims — wrap the body in `EXCEPTION WHEN OTHERS THEN RETURN NULL`. **Never** raise and never default to a value: a default turns one bad/empty JWT into a cross-tenant read, and a raise turns a deny into a 500. This is the single most security-critical line in the build — verify it explicitly with a no-context probe (`SELECT auth.uid()` → `NULL`).
- The JWT signing secret must be at least 256 bits, generated via `openssl rand -hex 32`, and injected via Pydantic Settings. Never hardcode it.
- **Pin the algorithm in the VERIFIER** — pass an explicit allow-list (`algorithms=["HS256"]`), never let the library dispatch on the token header's `alg`. Header-driven dispatch is the classic confusion attack (an RS256 public key replayed as an HS256 HMAC secret); `alg: none` is rejected unconditionally.
- "Sticky sessions are a violation of twelve-factor and should never be used or relied upon."
- => Mandate: processes are stateless/share-nothing. **STICKY SESSIONS ARE BANNED** (not just file-based sessions). Session state goes to `redis-main` (Redis) with a TTL. Never in-process memory, never on local disk. Any design that assumes "the same user hits the same process" is a violation.
- **Pattern B (legacy / migration-only):** The Supabase client SDK handles token storage. On mobile, wrap with `expo-secure-store` (never AsyncStorage or MMKV for tokens). See `80-mobile.md` § Backend Integration.
- **Both patterns:** Never store JWTs in `localStorage` or `sessionStorage` on web. Never store JWTs in AsyncStorage or MMKV on mobile.
- **Chrome Extension (MV3) specifics:** `chrome.storage.session` defaults to `TRUSTED_CONTEXTS`, so **content scripts cannot read the token** — keep it in the SW / extension-page context and have content scripts fetch it via SW-mediated messaging (`chrome.runtime.sendMessage`), not a direct read. For social login use `chrome.identity.launchWebAuthFlow` with **PKCE** (`code_verifier` via `crypto.subtle`, held in `storage.session`, redirect `https://<ext-id>.chromiumapp.org/`); the **backend** does the code-for-token exchange. **Never a heavy browser auth SDK** (Auth0-SPA-JS, `oidc-client-ts`) — they assume DOM/`localStorage`/iframes and break in the service worker. Pin a manifest `key` so the extension ID (and thus the `chrome-extension://<id>` CORS origin) is stable across machines. Full detail: `chrome-ext/70-chrome-ext.md`.
- **Never rely solely on the framework's request-shaping layer for access control.** CVE-2025-29927 (the `x-middleware-subrequest` bypass) proved COMPLETE middleware bypass via one crafted header; it is long patched upstream, but the rule outlives the patch — current Next.js even RENAMED the file to say so: `middleware.ts` became **`proxy.ts`**, explicitly repositioned as request-shaping, not a security boundary. ⚠️ **On current majors a leftover `middleware.ts` is SILENTLY IGNORED at build** — nonce injection and redirects stop executing with no error; rename it when upgrading.
- `CORSMiddleware` in FastAPI must populate `allow_origins` from environment variables (Pydantic Settings). Never hardcode origins.
- `X-Frame-Options: DENY` — kept as the legacy fallback only; formally obsoleted by `frame-ancestors`, never ship it ALONE
**Never** write inline `APIKeyHeader` / `require_api_key`. **Never** use per-service key names (`SERVICE_API_KEY`, `PROXY_API_KEY`). Scaffold `python-api` auto-emits `internal_auth.py`, `metrics.py` (REQUEST_COUNT / ERROR_COUNT / ACTIVE_JOBS / PROCESSING_COUNT), `/metrics` endpoint (Authelia-bypassed), and `SERVICE_INTERNAL_SECRET_KEY` in `.env.example`.
- => Mandate: config via env vars only (`os.getenv("KEY", "default")`); **ZERO secrets/constants in code**. Apply the open-source litmus test to every change. **BANNED**: grouped/named env config sets (e.g. a `config/production.yml` or a `settings.production` group) — env vars are granular and orthogonal, set per deploy. (The pack already covers secret handling — cross-reference existing secret patterns and extend with config orthogonality.)
- [ ] Mobile tokens stored in `expo-secure-store` — never AsyncStorage or MMKV.
- > **⚠️ Bearer bypass scope — security-critical.** The bypass defaults to `^/api/`, which makes the **entire** `/api/*` surface public (un-2FA'd). If the application authenticates only a **sub-prefix** (e.g. `/api/v1` carries the bearer/internal-token check) while OTHER `/api/*` routes are unauthenticated (legacy / admin / destructive), you **MUST** narrow the bypass with `shape.bearer_bypass_prefix: "^/api/v1"` — otherwise `fabrik apply` exposes those routes to the public internet. **Bypass ONLY the path the app itself authenticates.** Value must start with `^/`; the verifier (`orchestrator/verifier.check_api_bypass`) probes the configured prefix on deploy. When unsure whether a service has un-auth'd `/api/*` routes, ask the app owner before relying on the `^/api/` default.

### core/25-data-postgres.md
| Vector search | pgvector on `postgres-main` + `fabrik-lib/rag` — ⚠️ the extension is NOT currently installed there (probed 2026-09-01: the plain upstream PostgreSQL Alpine image, `plpgsql` only — `CLAIMS.yaml` row `fleet-postgres-main-no-pgvector`); a project needing vectors REQUESTS the fleet infra change first, never assumes it | same `postgres-main` DSN |
**"Own database" means a DATABASE on `postgres-main`, never a database SERVER.** Per-project isolation is a separate database (its own name, its own role) on the shared container — isolation, quota and backup are all satisfied at that grain. A dedicated Postgres instance is a decision, not a default: it needs its own `docs/DECISIONS.md` row naming what the shared server cannot serve (web-ecommerce-factory 01M1Q8X9, 2026-09-05: "one DB per store" read naively as one server per customer).
- Use Pydantic `BaseSettings` (per `10-python.md` § Config Loading) — never raw `os.getenv` **for an APPLICATION's settings surface**:
- ⚠️ **Scope, stated here because this LINE is what `review_rubric.py` injects — without its section.** The rubric FLOOR-injects this mandate *and* `35-security-auth`'s "config via env vars only (`os.getenv("KEY", "default")`)" into every finder prompt on every review, so a finder reading both literally has two rules it cannot both satisfy, and files a false positive on whichever it applies. The carve-out: `BaseSettings` governs a SERVICE's config surface (a `Settings` object, DB/Redis DSNs, secrets). A **vendored fabrik-lib module** has no settings object by design — it reads its own knobs with bare `os.getenv("KEY", "default")`, which is `35-security-auth`'s mandate being satisfied, not this … (wrapped further — read the pack)
- Never blindly trust `--autogenerate`. Always review `upgrade()` and `downgrade()` for unintended column drops, rename misinterpretations, and ENUM alterations before committing.
- > **Older pythons only** (services pinned below stdlib-uuid7 — which today includes SCAFFOLDED services: the scaffold still emits an older interpreter and ships `uuid-utils`; alignment tracked in the backlog): import `uuid7` from `uuid_utils.compat`, never `uuid_utils.uuid7()` directly — the latter returns `uuid_utils.UUID`, which asyncpg rejects (not a stdlib `uuid.UUID`). **DB-side:** newer PostgreSQL majors ship native `uuidv7()` (probe: `SELECT uuidv7()`); prefer `DEFAULT uuidv7()` at schema level where it exists. `postgres-main` currently runs major <!--v:postgres_major-->16<!--/v-->, which predates it — generate app-side on the fleet.
- Foreign keys must declare `ON DELETE` behaviour explicitly — `CASCADE` if children cannot exist without the parent, `RESTRICT` to protect audit trails. Never rely on the implicit default.
- This section owns the **canonical** engine, session, and `get_db`. `10-python.md` imports from here — never redefines its own.
- Database `AsyncSession` must be scoped to the route handler via `Depends()`. Never open sessions or transactions in global middleware — this holds connections during serialisation and I/O, exhausting the pool.
**BANNED as a server-side backing service** (dev, test, and prod alike):
**⚠️ SCOPE — this ban is about BACKING SERVICES, not client-local storage.** It does **NOT** apply to:
- **`desktop-app`** — SQLite is the **mandated** engine there (`desktop-app/72-desktop.md` § Local Persistence: `better-sqlite3` + SQLCipher; *"Production builds MUST encrypt the local SQLite file"*).
**12-Factor IV (Backing Services) — generalised:** swapping ANY attached backing service (DB, cache, object storage) is a **config change, never a code change**. The handle lives in `DATABASE_URL` / `REDIS_URL` / storage env — the code *reads* it, the code does not *decide* it. Never `if ENV == "prod":` branching to pick a host. (See § PostgreSQL Host Selection, which already mandates this for the DB.)
- [ ] All primary keys use UUIDv7 — stdlib `uuid.uuid7` on current Python (older pythons: `uuid_utils.compat.uuid7`, never direct `uuid_utils.uuid7()`); no `uuid4()`.

### core/30-ops.md
- the pinned release leaves full security support, never per-pack.
- All services deploy via `fabrik apply` (SSH + Docker Compose) on the `fabrik` network. Traefik routes external traffic — services do NOT bind host ports.
- **No `ports:` section.** All external traffic routes through Traefik. Never bind host ports. See Docker Port Security below. **12‑Factor VII (Port binding):** "the app is self‑contained and exports HTTP by binding to a port; it does not rely on runtime injection of a webserver" — which is exactly WHY no host `ports:`.
- **`container_name: <name>` is mandatory.** Same `_validate_compose()` gate refuses any service without it. Stable names are required so Gatus endpoints, inter-service URLs, and `docker exec`/`docker inspect` keys don't drift per redeploy. Use the bare service name (`browserless`, `gotenberg`, `meilisearch`, `glitchtip-web`, `site-provisioner`, etc.) — never UUID-suffixed names.
- gets one (ruling D-052) — see `core/60-watchdog.md`. Do not author a `watchdog: { enabled: false }` opt-out; if a project genuinely cannot host the sidecar, that is a ruling to obtain, not a default to flip.
- path before the flag goes in the spec, and assert target health (`/api/v1/targets` → `up`), never a bare `curl` of a path you assumed.
- remove it` on the hub) names a plan that protects nothing. Never add a service-named plan.
- health-enabled service can NEVER pass `up -d --wait` on a fresh database, and the deploy hangs to timeout.  An init the deploy cannot perform itself is a runbook step the plan MUST own.
- `fabrik redeploy <app>` SSHes to the VPS and runs `git pull` + `docker compose up -d --wait` against the **GitHub remote**, NOT the local `/opt/<app>` clone. Skipping `git push` redeploys the previous remote commit — the VPS never sees local changes.
**Mandate:** build → release → run are strictly separated. Releases are IMMUTABLE; the git SHA is the release ID. NEVER hot‑patch a running container (no `docker exec` to edit code/config in place, no in‑place code mutation on the VPS). Any change = a new build + a new release via `fabrik apply` / `fabrik redeploy`.
- Runtime database migrations that modify the app container (migrations MUST be run as separate deploy‑time steps)
**Place a service next to its data.** A spoke-hosted service reaches `postgres-main`/`redis-main` over the WireGuard mesh, and that hop is cross-Atlantic (Coventry ↔ LA) on EVERY query — a per-request chatty service pays it hundreds of times per page. So a DB-chatty service targets vps1; a spoke earns a service whose data traffic is light, batched or cached; a service PINNED to a spoke by hardware (GPU) batches or caches its data access — the data never moves off vps1. Measure before choosing (`ping 10.99.0.1` from the spoke, and the request's query count), never assume — the correctness rule ("container DNS, never localhost") says nothing about latency.
**Mandate:** WSL dev and the VPS run the SAME backing services (PostgreSQL + Redis), same major version. NEVER substitute a different backing service in dev (no SQLite standing in for Postgres, no in‑memory dict standing in for Redis). The same code must run unmodified in both environments.
- WSL runs PostgreSQL + Redis at the SAME MAJOR as the VPS containers — probe the live truth, never copy a tag from a doc: `ssh vps "sudo docker inspect postgres-main redis-main --format '{{.Config.Image}}'"` (probed 2026-09-01: the plain upstream PostgreSQL Alpine image at the fleet major recorded in `CLAIMS.yaml` row `pg-fleet-major` · `redis:7-alpine` — upstream official images, outside OUR-image Alpine ban per § Banned Patterns)
**Invariant:** Never use `ports:` in compose.yaml to expose internal services to the host. All external traffic must go through Traefik.
**Health endpoints (`/health`, `/healthz`, `/metrics`, `/api/health`) bypass Authelia on all services** — required for Gatus and Prometheus monitoring. The bypass is **resource-based, not domain-bound** — applies on every domain routed through Authelia (hub direct + spokes via `authelia-vps1@file` middleware). Never protect these paths.
**CRITICAL:** Use `web`/`websecure` in Traefik labels — never `http`/`https` (those entrypoints do not exist). The scaffolder emits the correct entrypoint names; if you hand-write labels, match these exactly.
**Mandate:** migrations and admin tasks run as a ONE‑OFF process against the DEPLOYED image + env — identical environment to regular processes. NEVER run admin tasks from a laptop against prod, NEVER via `docker exec` into a live container, and **ABSOLUTELY NEVER auto-run migrations from app startup/`lifespan`** (concurrent replicas race the Alembic version table → wedged deploy).
- > **`fabrik run` and `.fabrik/hooks/post-deploy/` do NOT exist** — the real CLI answers `Error: No such command 'run'`, the hook path appears nowhere in the platform, and `_post_deploy_sync()` (`cli.py:64`) only refreshes `data/projects.yaml`; an agent following either ships a deploy where migrations never run. Do not re-add either without a `path:line` in `src/fabrik/` that executes it.
**Processes are share-nothing:** any state shared across requests MUST go to Redis (`redis-main`) with a TTL. A project using Redis for sessions MUST declare `shape.needs_cache: true` in `specs/services/<id>.yaml`, or `fabrik apply` skips the Redis registrar and the deploy is silently broken.
- "A twelve-factor app never relies on implicit existence of system-wide packages"
**Mandate:** any binary the app shells out to (ffmpeg, yt-dlp, poppler, tesseract…) MUST be `apt-get install`-ed in the Dockerfile, with a `shutil.which()` startup probe that fails fast. **The pinned base image is the version boundary** — exact `=version` apt pins are banned: they break on every Debian point release as old debs leave the mirrors (the "works then mysteriously breaks" class this section exists to prevent); the codename pin + image digest give the reproducibility. Never assume `curl`/ImageMagick/ffmpeg exist in the image — they don't by default.

### 12-FACTOR (all twelve axes)
- I codebase: shared code → fabrik-lib, never two apps in one repo
- II deps: every shelled-out binary installed + pinned in the Dockerfile
- III config: granular env vars; no secrets in code; no grouped env sets
- IV backing services: swappable by DSN/config change only
- V build/release/run: releases immutable; never hot-patch a container
- VI processes: stateless; session state → redis-main; no sticky sessions
- VII port binding: bind in-container; Traefik routes; no host ports:
- VIII concurrency: scale out; never daemonize or write PID files
- IX disposability: SIGTERM returns in-flight jobs to the queue; jobs idempotent
- X dev/prod parity: same backing services everywhere; no SQLite-for-Postgres
- XI logs: unbuffered stdout only; the app never writes/rotates a logfile
- XII admin: migrations/one-offs run against the deployed release, never startup

## MATCHED — packs whose globs hit the changed paths

### ai/50-agentic.md  (hit: src/fabrik/orchestrator/context.py, src/fabrik/orchestrator/infrastructure.py, tests/orchestrator/test_registrar_failures_not_green.py)
- is never the only thing between the agent and an irreversible act.
- **Auth boundary.** Agents run on the subscription's OAuth through the unmodified CLI, never `ANTHROPIC_API_KEY` (ai/00). Never pass `bare=True` on that lane: bare mode never reads OAuth credentials and fails with "Not logged in". A deployed service declares `shape.uses_claude_cli` and mounts the rotated `~/.claude`, never a static token. Anthropic's terms say subscription OAuth is for ordinary, individual use of Claude Code and its own apps; developers building products or services, including with the Agent SDK, should use an API key, and Anthropic does not permit routing requests through Free, Pro or Max credentials on behalf of their users, reserving the right to enforce that without notice. The operator's own development and automation through the unmodified CLI is the closest fit to that … (wrapped further — read the pack)
- output, and some models never return them. Pick the rate per model from the bake-off browser (hub-only), using its tools chip.

### core/10-python.md  (hit: src/fabrik/cli.py, src/fabrik/drivers/postgres.py, src/fabrik/orchestrator/context.py)
**`uv`** is the mandated Python package manager. Never use raw `pip`, `pip install`, `poetry`, or `pipenv`.
- Dependencies live in `pyproject.toml` + `uv.lock`. Do not modify these files unless the ticket authorises it.
- its own reviewed commit, never as a side effect of unrelated work.
- The one RULE: use SQLAlchemy async consistently — never mix `async def` with sync `.query().all()` (the Banned table row; the full session pattern is `25-data-postgres.md`'s).
- The canonical `engine`, `async_session`, and `get_db` are defined in `src/database.py` — owned by `25-data-postgres.md`. Import from there, never redefine:
**Config convention:** apps read a complete `DATABASE_URL` (`postgresql+asyncpg://user:pass@host:port/db`) and `REDIS_URL` from env. Discrete `DB_HOST`/`DB_PORT`/`DB_NAME`/`DB_USER`/`DB_PASSWORD` for the app to assemble are **banned**. The env supplies the complete URL — `localhost` in WSL, `postgres-main` on VPS — so the host concern is an env-layer responsibility, never code logic. See `30-ops.md` compose template for how discrete vars are interpolated into `DATABASE_URL` at the compose level.
- volume** (`30-ops.md` § Volumes), never in `.tmp` and never in `/tmp`.
**GlitchTip discipline:** unhandled exceptions (FastAPI 500s) are auto-captured by GlitchTip with full stacktraces. In the `except Exception` branch, log a **short event name + correlation_id** — never `logger.exception()` (that duplicates the traceback in Loki AND GlitchTip). See `55-observability.md` § Error Reporting for the full rule.
**Note:** Use the scaffolded logger: `from {package}.logger import get_logger` (see `55-observability.md` § Pre-Scaffolded Logging). Do not use `structlog.get_logger()` directly or `logging.getLogger(__name__)`.
- **Never a bare `asyncio.create_task()`** — an unreferenced task is silently garbage-collected and its exceptions vanish. Hold the reference and await it, or use `asyncio.TaskGroup`.
- **`datetime.now(UTC)`, never `datetime.utcnow()`** — deprecated and naive; naive datetimes are a real cross-service defect class.
- Type the package, never `.`: the root walks the hub-synced `scripts/`, where mypy finds the same file under two module names and stops on every fresh project. file-worker types `mypy --explicit-package-bases worker`; a `server/` backend (saas-skeleton, static-site, office-extension, chrome-extension, mobile-app) runs `mypy src` from `server/` (D-605).
- Ruff's selected rule-sets MUST include `ASYNC` (blocking IO in async code — machine-enforces this pack's hardest-to-review rule), `B` (bugbear) and `S` (bandit) alongside the defaults; configured in `pyproject.toml`, emitted by the scaffolder.
- Production services run via `uvicorn` CLI in the Dockerfile, not `uvicorn.run()` in code. Base image is always the pinned Debian `-slim` variant on `linux/amd64` (the variant is pinned fleet-wide in `30-ops.md` § Container Base Images — change it THERE, never per-repo). Never use Alpine — musllinux wheels exist now (PEP 656) but coverage is still partial, source builds are dramatically slower, and musl's allocator/stack defaults degrade CPython; the trade never pays on this fleet.
- `uvicorn.run()` is for local development only. Never ship it in production code.
- a fleet scaling decision (more containers), never a per-app flag.
**BANNED: grouped/named env config sets.** 12F is explicit — *"env vars are granular controls, each fully orthogonal to other env vars"* — so a `config/production.yml`, a `settings.production` group, or a `config/{dev,staging,prod}.yaml` tree is a violation. Env vars are granular and set **per deploy**, never batched into a named "environment".
**BANNED:** `logging.FileHandler`, `logging.handlers.RotatingFileHandler`, `TimedRotatingFileHandler`, `loguru` file sinks, any `*.log` file write, any in-app log rotation/retention/cleanup. The app never decides where logs are stored or routed — Docker → Promtail → Loki does. Full rule: `55-observability.md` § Logs.
**Factor XII — Admin processes. NEVER migrate from app startup.**
**BANNED: `alembic upgrade head` in FastAPI's `lifespan`, in an `@app.on_event("startup")`, or as an import side-effect.** With more than one replica (or a restart storm) two containers run `upgrade head` **concurrently** → they race the Alembic version table → duplicate DDL → **wedged deploy**. Migrations are a **one-off admin process against the deployed release**: `docker compose run --rm <svc> alembic upgrade head` (see `30-ops.md` § Release & Admin Processes).

### core/40-documentation.md  (hit: docs/CONFIGURATION.md, docs/development/reviews/2026-10-08-plan-2-payments-fulfilment-role-review.md, docs/reference/modules/drivers.md)
- > **⚠️ `docs/OPERATIONS.md` + `docs/DEPLOYMENT.md` are FLEET-AI INTERFACES, not just docs (D-065).**
- **Tier-1 (author → verify → converge; the author leg is NATIVE while the pool is OFF, D-181 — `scripts/doc_reconcile.py`'s pool author cannot dispatch):** for each **mechanically-detectable** doc whose Doc-Sync trigger fired (`docs/QUICKSTART.md` · `docs/CONFIGURATION.md` · `docs/data-contract.md` · `docs/SERVICES.md` · `docs/OPERATIONS.md` — the reliable-signal subset), `scripts/doc_reconcile.py` dispatches a cheap OpenRouter-pool author (`libs.subagents`, `pick_models("docs")`) to emit a **minimal structured patch**, **verifies it before applying** (a symbol cross-check catches invented endpoints; the orchestrator injects a higher-assurance native-Claude verify), and loops to a zero-edit round. Runs per phase in `/fabrik-execute-plan`; never blocks (fail-safe). The other docs (CHANGELOG, INDEX, FEATURES, RESILIENCE, PORTS, the READMEs, `db/schema.sql`, …) have no reliable mechanical content-signal → they rely on the touch-on-change backstop below + your own edit (force-update, not force-correct).
- The SSOT is the type-aware registry (`scripts/enforcement/_doc_registry.py::PROJECT_DOCS`) — this table is its project-facing rendering, kept in step, never a second truth. `/fabrik-plan-after-chat` (the plan set's spine + tickets — the ticket-format authority) injects these rows per ticket as its `Docs:` line.
- Standalone work (not plan execution) → `Agent-Role: primary`. Trailers go below a blank line, above `Co-Authored-By`. ⚠️ The trailer block must be its OWN paragraph with NO blank line inside it: git parses only the LAST paragraph, and only if it is all-trailers. A blank line before `Co-Authored-By:` demotes everything above it to prose; so does a prose line glued to the top of the block. Measured 2026-08-15: 200 of the last 200 hub commits carried `Agent-Role:` and only 10 parsed, because the old example here shipped the blank line.
- **⚠️ Link it or it is decoration.** *Measured:* requests for files that do NOT exist came ~zero from AI bots — agents never go looking. It follows (inference, not measurement) that a file only gets read when something points at it: reference it from the docs index or README.
- ⚠️ **In the hub (`/opt/fabrik`) `llms.txt` is GENERATED** (`scripts/generate_capability_index.py`, refreshed daily) — never hand-edit it there; change the generator. A project has no such generator; an `llms.txt` it ships, hand-written or built by its own code, is its own.
- either way. Cheap and reversible — never at the expense of `OPERATIONS.md`/`DEPLOYMENT.md`, which are the load-bearing agent interfaces (D-065).
- **No skipped heading levels** — `##` to `###`, never `##` to `####`
- **Fenced code blocks only** — never indented code (AI treats it inconsistently)

### core/45-testing-strategy.md  (hit: tests/orchestrator/test_registrar_failures_not_green.py, tests/test_app_role_provision.py, tests/test_payments_fulfilment_real_pg.py)
- **Behavior Contract**: every ticket enumerates its distinct **user-observable behaviors / acceptance criteria** and tests **each one** — one high-value integration/E2E test per behavior, risk-ordered, TDD for the risky ones. Skip trivia (getters / framework glue / config): **lean-but-complete, NOT 100%-line-coverage dogma**. Do not chase line coverage — ensure every behavior has a test that would fail if that behavior regressed. (Cheap pool subagents can author the per-behavior tests — the suggest→curate→author→fix workflow in `62-using-subagents.md` § Dispatch policy + `~/.claude/commands/fabrik-review.md`.)
- **No cosmetic assertions**: never assert against CSS classes, Tailwind utility strings, pixel measurements, or snapshot hashes. Assert application state and user-visible outcomes only.
- **Watched-fail-first** (for tests this change adds or modifies; trivia stays skipped per the Behavior Contract): a non-trivial behavior's test proves something only if it has been SEEN RED — either write it first and watch it fail, or (after the fact) neuter the fix/feature, prove the test goes red, then RESTORE and re-run to green. The neutered state is never staged, committed, or left in the tree. A green test never seen red is unverified — a suite can pass with its guard deleted.
- **Run tests**: `uv run pytest tests/` (never bare `pytest` — Fabrik uses `uv`) — **when the project has a `pyproject.toml`/`uv.lock`**. A `requirements.txt`-only project (no manifest) runs `.venv/bin/python -m pytest tests/` — the manifest clause chooses the RUNNER, it never disarms the mandate to run the suite (web-ecommerce-factory 01M1QEY5, 2026-09-05: the clause read as "does not apply here"). ⚠️ **Gate this on the manifest, because this line is FLOOR-injected into finder prompts and a vendored fabrik-lib MODULE has neither by design**: the module recipe ships `requirements.txt` (`fabrik-lib/README.md` § Creating a Reference Implementation), so `uv run` cannot resolve it and `python3 -m pytest` is the only thing that works. Telling a finder the sole working … (wrapped further — read the pack)
- **Zero-mock database policy**: never mock SQLAlchemy, SQLModel, or database sessions. All backend tests execute against a real PostgreSQL instance.
- **`ASGITransport` never runs lifespan** — anything the app initializes at startup (scaffolded apps are lifespan-based) silently does not exist in tests; wrap with `asgi-lifespan`'s `LifespanManager` when a test needs startup state.
- Use `structlog` in test helpers if logging is needed — never `print()`. See `55-observability.md`.
- **Never stub a server action from Playwright** — the server is the E2E boundary; stubbing belongs in the unit lane where the action is a plain function.
- Run Playwright against the PRODUCTION build (`next build && next start`), never the dev server.
- All locators must be **semantic**: `page.getByRole('button', { name: /submit/i })`. Never use CSS selectors or XPath.
- Launch Playwright's **bundled Chromium** (`channel: 'chromium'`) — stable Chrome/Edge removed the `--load-extension` / `--disable-extensions-except` side-load flags (Chrome 137/139), so those args only work under bundled Chromium, never installed stable Chrome.
- Run `@axe-core/playwright` with **`bypassCSP: true`** (the non-relaxable extension CSP otherwise makes axe throw on `chrome-extension://` pages); keep `@axe-core/playwright` a **dev-dependency only** (MPL-2.0 — never bundled into the shipped artifact). Gate bundle size with `size-limit` **per surface** (popup / side-panel / content-script). Full loop: `chrome-ext/70-chrome-ext.md` § Testing & UI Verification.
- Keep the generated types committed and re-generate on schema changes (`uv run python -c "import json; from <package>.main import app; print(json.dumps(app.openapi()))" > openapi.json` — the scaffold emits `src/<package>/main.py`, never a flat `src/main.py`, so `src.main` imports nothing).
**BANNED in tests:**
| A GUARD proven only by the ONE spelling of the defect you already fixed | Write the guard's subject five LEGITIMATE ways — five a DIFFERENT author would plausibly write, not five typos of yours — and count how many it still catches; one of five means it is keyed on your fix, not on the class — and one of five is the FLOOR of the failure, never its definition: four of five is a partial class and is reported as four of five. This is IN ADDITION to red-on-revert below, not a rival bar: that one proves the guard fires at all, this one proves it fires on the class. ⚠️ Cheapest ways to satisfy it WITHOUT the outcome (`CLAUDE.md` § UNIVERSAL governance markers, the entry whose anchor is **you get the behavior you measure** — search the ANCHOR, not the rule name: the project-facing contract lists that section by anchor alone and carries the name `cobra-effect` nowhere): (i) write five near-identical spellings and count 5/5; (ii) ship at 2/5 and REPORT it, needing no fabrication at all, in the hope that a reported count reads as a passed one — it does not: under 5/5 is a finding; (iii) claim the exercise and record nothing, since the five are never committed. So the bar is TWO things and needs both: **the five go IN the test file as executable CASES**, never a comment — a comment cannot go RED, so nothing can falsify it, and that is the objection, not that it records nothing — **and anything under 5/5 is a finding, not a pass**. ⚠️ Two paths this row does NOT close, stated rather than pretended away: you can shrink the SUBJECT until five legitimate spellings all land inside what the guard already catches (nothing is fabricated; the claim narrowed, not the guard), and an honest 4/5 — real information, 80% of the class — costs the author something to report, so the cheapest response to it is silence. Report the count you got either way — a 4/5 with the miss NAMED is a finding someone can act on, and a 5/5 nobody can execute is not a pass at all. Measured 4× in one day across 2 repos (01M1S4D78KRM0ZSYDNGTHS9HYQ), and once more the day this row landed: a contract-parity grader that read the LIVE file instead of the tree under test stayed green under the exact drift it existed to catch |
| A test THIS change adds/modifies that was never seen red (no fail-first, no red-on-revert proof) | Watch it fail first, or neuter the change → prove red → restore → re-run green |
- [ ] Destructive DB tests call `require_throwaway(TEST_DATABASE_URL)` before connecting — never point them at a dev/shared DB.
# promote-to-check_* tail elided here (83 greppable literals; the full mandates are above)
```

| Class | Source | Where it bites in this plan | Status |
|---|---|---|---|
| secrets, generated passwords, no hardcoded fallback | core/35-security-auth.md (FLOOR) | the minted password is delivered once through `.env` and never logged | CLEAN |
| role privileges, migrations discipline | core/25-data-postgres.md (FLOOR) | the registrar's DDL stays hub-operational; no project schema change | FIXED (R-1: the pack citation now names § Spec contract) |
| credential propagation, deploy invariants | core/30-ops.md (FLOOR) | mint, deliver, then grant; no VPS write | CLEAN |
| 12-Factor (all twelve) | the FLOOR block | config as env vars, stdout logs, no startup migration | CLEAN |
| agent loops | ai/50-agentic.md (MATCHED) | no agent loop in this change | CLEAN (not applicable) |
| Python discipline, DSN convention, logging | core/10-python.md (MATCHED) | one complete DSN; stdout warning lines | CLEAN |
| doc reconciliation | core/40-documentation.md (MATCHED) | Phase C's CONFIGURATION and drivers edits | CLEAN |
| real PostgreSQL, red first | core/45-testing-strategy.md (MATCHED) | the real-PG battery and the unit tests | FIXED (A-3: four Behavior Contract rows added) |
| fail-open vs fail-closed on every gate and guard | standing | `unknown` and every refusal record `failed`; `pending` never reads `provisioned` | CLEAN |
| cost / quota / limit accounting edges | standing | the 63-character role-name guard; the last-line path parse with NOTICE output present | FIXED (A-4: the 63-character guard has a test) |
| boundary / sentinel / prefix collisions | standing | no schema, partial schema, tables without `jobs`, changed signature, pre-migration install; the `_payments_fulfilment` suffix beside `_payments_ingest` | CLEAN |
| behaviour without a test | standing | every Behavior Contract row has its test, seen red | FIXED (A-3, A-4) |

## File Scope (owned paths)

- src/fabrik/spec_loader.py
- src/fabrik/drivers/postgres.py
- src/fabrik/orchestrator/infrastructure.py
- src/fabrik/orchestrator/context.py
- src/fabrik/cli.py
- tests/test_payments_fulfilment_real_pg.py
- tests/test_payments_ingest_real_pg.py
- tests/test_payments_ingest_role.py
- tests/test_app_role_provision.py
- tests/orchestrator/test_registrar_failures_not_green.py
- docs/CONFIGURATION.md
- docs/reference/modules/drivers.md
- docs/development/reviews/2026-10-08-plan-2-payments-fulfilment-role-review.md

## Evidence

**Phase A** — the driver symbols the phase edits, and fabrik-lib's function signature it calls:

```
$ grep -n "^_PAYMENTS_GRANT_INGEST_FN\|^def _payments_grant_ingest_block\|^def _payments_grant_path_sql\|^def create_payments_ingest_role\|^def drop_database\|_payments_ingest_drop_role_sql(db_name)" src/fabrik/drivers/postgres.py
776:_PAYMENTS_GRANT_INGEST_FN = "payments_grant_ingest(pg_catalog.regrole)"
851:def _payments_grant_ingest_block(role: str) -> str:
886:def _payments_grant_path_sql() -> str:
905:def create_payments_ingest_role(
1691:def drop_database(
1756:            + _payments_ingest_drop_role_sql(db_name)
1779:    sql += _payments_ingest_drop_role_sql(db_name)
$ grep -n "CREATE OR REPLACE FUNCTION payments_grant_fulfilment" /opt/fabrik-lib/payments/db/migrations/2026-09-29-scoped-service-roles.sql
462:CREATE OR REPLACE FUNCTION payments_grant_fulfilment(r pg_catalog.regrole) RETURNS pg_catalog.void
$ grep -rn --include='*.py' create_payments_ingest_role src tests | wc -l
17
$ grep -n "needs_payments_ingest: bool\|def _payments_ingest_needs_database" src/fabrik/spec_loader.py
340:    needs_payments_ingest: bool = Field(
402:    def _payments_ingest_needs_database(self) -> "Shape":
```

fabrik-lib's `payments` tree was last changed at `9b3df676` (2026-09-30), so SB-096 (fabrik-lib
`docs/STRATEGIC_BACKLOG.md:102`, D-399 at `docs/DECISIONS.md:385`) has not landed; the migration and
`schema.sql:838-1018` define the function identically (grounding seat, read line by line).

**Phase B** — the orchestrator, context and CLI sites:

```
$ grep -n "out\[\"payments_ingest\"\]\|if provision_payments_ingest:\|\"payments-ingest-role\"" src/fabrik/orchestrator/infrastructure.py
253:        out["payments_ingest"] = (True, "shape.needs_payments_ingest=true")
255:        out["payments_ingest"] = (
260:        out["payments_ingest"] = (
876:            if provision_payments_ingest:
896:                        "payments-ingest-role",
901:                    self._nonfatal(ctx, "payments-ingest-role", e)
907:                    ctx.add_resource("payments-ingest-role", db_name, status="failed")
$ grep -n "registrar_failures: list" src/fabrik/orchestrator/context.py
66:    registrar_failures: list[str] = field(default_factory=list)
$ grep -n "Deployment complete\|raise SystemExit(2)" src/fabrik/cli.py | head -2
545:                raise SystemExit(2)
546:            click.echo(f"✅ Deployment complete: {ctx.deployed_url or ctx.spec.get('domain')}")
```

`src/fabrik/cli.py:1282-1292` prints `Refresh finished but {n} registrar(s) FAILED` (grounding seat).

**Phase C** — the doc landing sites: `docs/CONFIGURATION.md:231` (the ingest section heading),
`:237` (the fulfilment-worker sentence), `docs/reference/modules/drivers.md:31` (the `postgres.py` row);
`.env.example` carries no `PAYMENTS_INGEST_DATABASE_URL` line, so the auto-injected fulfilment variable is
documented in `docs/CONFIGURATION.md` only, by the same convention:

```
$ grep -n "PAYMENTS_INGEST" .env.example docs/CONFIGURATION.md | cut -c1-80
docs/CONFIGURATION.md:231:### Payments webhook ingest — `PAYMENTS_INGEST_DATABASE_URL` (auto-inj
docs/CONFIGURATION.md:233:For a project with `shape.needs_payments_ingest` (vendors fabrik-lib `pa
docs/CONFIGURATION.md:235:**Consuming-project wiring** (the project's job, NOT built by the regis
```

## Self-audit

Grounding passes run this session (three native seats in one message, pool OFF):
- Opus `fabrik-researcher` over fabrik-lib: every spec citation into fabrik-lib holds (migration `:460-640`,
  `:485-486`, `:523-537`, `:575-590`, `:592-638`; README `:395-409`, `:413-418`, `:437-454`, `:458-470`;
  hub `postgres.py:776`); SB-096 has not landed; no drift.
- Sonnet `Explore` over the hub: spec lines drifted (spec_loader +7, infrastructure +22, CONFIGURATION
  `:216` split into `:231` and `:237`); this plan cites the current lines. W-7ba06610 is still open at
  `infrastructure.py:895-899`. Its caller count (17) was re-executed here; its file count (5) was wrong
  and is 6.
- Sonnet `Explore` over the seven packs: the Constraints Digest above, every quote verbatim with its line.

(a) Coverage — each agreed item to its phase:
- spec item 1 (the flag) → Phase A step 3; items 2, 3, 4, 6 → Phase A step 4; item 5 → Phase B; item 7 (a loud refusal) → Phase A's refusal test;
- the contract deltas → Phases A and B (code), Phase C (docs);
- § Validation → Phase A step 2 (real PG) and Phase B step 1 (unit);
- (b1) the SB-096 tripwire → Phase A step 1; (b2) the full review → Phase A step 7.3, Phase B step 6.3 and Phase C step 6; (b3) no VPS write → Global Constraints;
- W-7ba06610 → Phase B step 3; W-4b1dfd76 → Phase B step 4; the infra pack mail → Phase C step 4.

(b) Cross-phase signatures: Phase B consumes `mint_payments_role(db_name, lane, dry_run)` and
`grant_payments_role(db_name, lane, dry_run)` exactly as Phase A produces them, and
`Shape.needs_payments_fulfilment` by that name; Phase C documents the same three names and
`PAYMENTS_FULFILMENT_DATABASE_URL`, `registrar_warnings`.

Fixed point: reached by `/fabrik-plan-review` in three passes (Pass Ledger below); its closing pass confirmed zero with the plan md5 unchanged.

## Residual unknowns

- Resolved: fabrik-lib's function signature and body are unchanged since the spec (grounded); the hub's
  current lines (grounded); the auto-injected-variable doc convention (grounded); the CLI test module for
  the four summaries is `tests/orchestrator/test_registrar_failures_not_green.py` (plan review pass 1).
- Open, with a resolution step:
  - SB-096 may land before execution and change the function's refusals or signature. Resolution: Phase A
    step 1 re-checks the signature; a changed signature is a `BLOCKED:` spec contradiction, and a
    same-signature refusal change needs only the real-PG tests re-run against the new migration.

## Intake Inventory

| I# | Item (anchored) | Disposition | Where |
|---|---|---|---|
| I1 | the spec's nine IN items (spec § Intake Inventory I1-I8, I11) | IN | Phases A-C, per (a) above |
| I2 | brief: "fabrik-lib's open SB-096 reworks the refusal signal of payments_grant_fulfilment … the plan must name that tripwire" | IN | Phase A step 1; Residual unknowns |
| I3 | brief: "the spec touches the registrar (auth roles, a heavy surface: lane row 1b) … every phase boundary owes the full /fabrik-review" | IN | the full `/fabrik-review` at the Phase A and Phase B boundaries and at Finish; Phase C (docs only) takes the scoped review (Execution Discipline) |
| I4 | brief: "no VPS write in any step" | IN | Global Constraints |
| I5 | W-4b1dfd76: "print registrar_warnings in fabrik refresh's exit-2 branch (cli.py:1282) as well as its ✅ branch" | IN | Phase B step 4 |
| I6 | W-d8505af5: "ingest lane has no changed-signature guard" | OUT-OF-SCOPE | not in spec § The delta; stays on W-d8505af5 |
| I7 | spec § Intake I9-I10: pack 85's lines and fabrik-lib's README sentence | OUT-OF-SCOPE | infra's beat (mailed in Phase C step 4) and fabrik-lib's repo (spec reply 01M3S2DM02) |

Intake: 7 items — 5 IN, 2 OUT-OF-SCOPE (each named above), 0 ASK.

## Pass Ledger

| Pass | seats · axes re-checked (claims · gates · interfaces · completeness) | counters | method | plan md5 (start → end) |
|-----:|---|---|---|---|
| 1 | 3 (Opus: header to Execution Discipline, Coverage Checklist, File Scope · Sonnet: Phase A · Sonnet: Phases B and C, Evidence to Intake) · claims · gates · interfaces · completeness | 14 found · 14 confirmed · 0 refuted (R-1 to R-7, A-1 to A-4, B-1 to B-3) | method: re-derivation — each seat re-derived its slice's anchors, counts and quotes from the primary source | 8428900b → 38d31210 |
| 2 | 3 (the round-1 seats on their own slices plus one hop) · claims · gates · interfaces · completeness | 7 found · 7 confirmed · 0 refuted: R-8 (a Coverage row credited to an unrelated fix) and six from the flip-gate trial (five Constraints Digest quotes carried an elision or a case change check_rule_grounding cannot match; this ledger's method cell lacked its label); 2 of the 7 were introduced by pass-1 fixes; 14 of 14 round-1 claims FIXED | method: re-derivation — each seat re-ran its round-1 commands against the pass-2 pin | 38d31210 → the pass-3 pin |
| 3 | 1 (the Opus slice-R seat; slices A and B were verified clean in pass 2 and carried no pass-2 edit) · claims · gates | 0 found · 0 confirmed · R-8 and the six trial fixes FIXED; 15 of 15 digest quotes found on their cited lines | method: re-derivation — the seat re-ran the quote check line by line against the rule packs and re-counted row 2 | ff83e873 → ff83e873 (unchanged; this row and the Status flip are the only edits after it) |
