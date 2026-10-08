# Plan — the payments fulfilment-worker role in the hub registrar

Status: DRAFT
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
  - (b2) The registrar mints auth roles, which is a heavy surface (lane row 1b), so the whole-plan diff
    takes the full `/fabrik-review` at Finish.
  - (b3) No step writes to a VPS. A live grant happens only at a consuming project's own next
    `fabrik apply`, behind that project's deploy gate.
- W-4b1dfd76, folded in: `fabrik refresh`'s failure (exit-2) branch also prints `registrar_warnings`,
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
| "The owner runs `payments_grant_fulfilment('<worker role>'::regrole)` (fabrik-lib D-337) for a `LOGIN NOSUPERUSER NOBYPASSRLS` role." | `.windsurf/rules/core/85-payments-billing.md:45` | the role attributes the mint uses and the function the grant calls |
| "The worker login is never `<db>_app` or any tenant-facing role (the grant does not refuse one, and would hand the request path cross-org `jobs` access and `purchases` `INSERT`...), never the ingest role (the grant refuses it), never `BYPASSRLS`." | `.windsurf/rules/core/85-payments-billing.md:45` | a dedicated `<db>_payments_fulfilment` role, never an alias of an existing one (SB-096 is the module-side refusal still to come) |
| "This release the lane check only WARNS on a `BYPASSRLS` or superuser role ... so on BOTH connections also require `SELECT rolbypassrls, rolsuper FROM pg_roles WHERE rolname = current_user` to return false, false." | `.windsurf/rules/core/85-payments-billing.md:28` | the real-PG test asserts `rolbypassrls, rolsuper` false on the fulfilment login |
| "Keep `jobs` without RLS beyond what the module's grant functions provision (module README § Gotchas)" | `.windsurf/rules/core/85-payments-billing.md:27` | the test schema keeps `jobs` without extra RLS |
| "The request path's login role holds no `BYPASSRLS` and is a member of no role that does." | `.windsurf/rules/saas/95-multi-tenant-saas.md:150` | no membership is granted between the payments roles |
| "The fulfilment worker never uses it: it runs as its OWN scoped login granted by the module's `payments_grant_fulfilment` — never the tenant app role — and claims each job before scoping to its `org_id`" | `.windsurf/rules/saas/95-multi-tenant-saas.md:151` | the real-PG test claims a `jobs` row with no tenant GUC, then scopes |
| "=> Mandate: config via env vars only (`os.getenv("KEY", "default")`); **ZERO secrets/constants in code**." | `.windsurf/rules/core/35-security-auth.md:267` | the password is generated at mint time and delivered through `.env` only |
| "**32 characters**, charset `[a-zA-Z0-9]` only (no symbols — survives `.env` round-trip + shell quoting)." | `.windsurf/rules/core/35-security-auth.md:322` | the mint reuses the driver's existing CSPRNG helper |
| "**A credential GENERATED during init goes stale the instant it is generated.**" | `.windsurf/rules/core/30-ops.md:230` | mint, deliver, then grant: the DSN is injected before the grant can raise (spec § The delta item 2) |
| "**Config convention:** apps read a complete `DATABASE_URL` ... Discrete `DB_HOST`/`DB_PORT`/`DB_NAME`/`DB_USER`/`DB_PASSWORD` for the app to assemble are **banned**." | `.windsurf/rules/core/10-python.md:133` | one complete `PAYMENTS_FULFILMENT_DATABASE_URL` |
| "**BANNED:** `logging.FileHandler`, `logging.handlers.RotatingFileHandler`, `TimedRotatingFileHandler`, `loguru` file sinks, any `*.log` file write" | `.windsurf/rules/core/10-python.md:294` | the pending warning is a stdout log line plus the CLI summary line, never a file |
| "- **Zero-mock database policy**: never mock SQLAlchemy, SQLModel, or database sessions. All backend tests execute against a real PostgreSQL instance." | `.windsurf/rules/core/45-testing-strategy.md:58` | the grant behaviours are proven on real PostgreSQL through `scratch_pg()`; unit tests mock only the driver boundary the orchestrator calls |
| "**Watched-fail-first** ... A green test never seen red is unverified" | `.windsurf/rules/core/45-testing-strategy.md:22` | every phase's new tests are seen red before the code lands |

## Context Ledger

| Source | What binds | Grounded ref |
|---|---|---|
| `.windsurf/rules/core/85-payments-billing.md` (AVAILABLE, names this feature) | the role shape, the grant call, the `rolbypassrls/rolsuper` check | `:27`, `:28`, `:45` |
| `.windsurf/rules/saas/95-multi-tenant-saas.md` | no BYPASSRLS, no membership, worker claims then scopes | `:150`, `:151` |
| `.windsurf/rules/core/35-security-auth.md` (FLOOR) | secrets and generated passwords | `:267`, `:322-323` |
| `.windsurf/rules/core/25-data-postgres.md` (FLOOR) | the registrar's DDL is hub-operational, outside any project's Alembic chain, as the ingest role already is | `:94` |
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

- **Review floor** — every phase, before its commit, runs `/fabrik-review-scoped` on its changed surface
  to a closing pass that confirms zero; the Finish runs ONE full `/fabrik-review` over the whole-plan diff
  (the `Profile: small` heavy round, which also discharges lane row 1b for the auth-role surface), with
  its receipt at `docs/development/reviews/2026-10-08-plan-2-payments-fulfilment-role-review.md`. No phase
  commits on a first-pass green.
- **Dispatch policy** — native Claude seats for every fan-out (the pool is OFF, D-181): per phase the
  scoped review's three-reader floor (Sonnet, Haiku, and Opus on the riskiest unit); at Finish the D7
  floor from `dispatch_headroom.py --units <groups>`, stamped with `command_run.py dispatch` before it
  goes out. Coding is inline by the orchestrator (`Profile: small`); Haiku never codes.
- **Parallelism + merge** — phases are sequential (B consumes A's driver interface, C documents both).
  Inside a phase the review seats run in parallel and merge in the orchestrator's adjudication; the real-PG
  tests and unit tests of a phase run together in one pytest call.

## Phase A — Driver: mint, deliver, grant for both payments lanes; the flag

Appetite: 90
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
   (`:340-352`, `:401-411`). Add the unit test "the Shape validator refuses the flag without
   `needs_database`" to `tests/test_payments_ingest_role.py` (renamed in step 5 if the file name no longer fits).
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
   3. `/fabrik-review-scoped` on Phase A's changed surface plus its callers, to a closing pass that confirms zero;
   4. commit the phase with explicit paths and the provenance trailers.

**Behavior Contract**
- **Given** fabrik-lib's schema and `jobs` in `public`, **When** `grant_payments_role(db, "fulfilment")` runs, **Then** it returns `module` and the fulfilment login can claim a job without a tenant GUC, scope, and insert a purchase (`src/fabrik/drivers/postgres.py:905`; spec § Validation)
- **Given** the payments tables but no `jobs`, **When** the fulfilment grant runs, **Then** it raises naming `jobs` (spec § The delta item 3.4)
- **Given** no payments schema or a partial one, **When** the fulfilment grant runs, **Then** it returns `pending` (spec § The delta items 3.1, 3.3)
- **Given** a function of that name under a different signature, **When** the fulfilment grant runs, **Then** it raises the changed-signature error, never the pre-migration one (spec § The delta item 3.2)
- **Given** a grant batch that raises, **When** `mint_payments_role` ran first, **Then** the caller already holds the password for either lane (spec § The delta item 2)
- **Given** a spec with `needs_payments_fulfilment: true` and no `needs_database`, **When** it loads, **Then** validation fails (`src/fabrik/spec_loader.py:401-411`)
- **Given** a database with both payments roles, **When** `drop_database` runs, **Then** both roles are dropped in either branch (`src/fabrik/drivers/postgres.py:1756`, `:1779`)

## Phase B — Orchestrator, context and CLI: inject before grant, status from the path, warnings shown

Appetite: 75
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
   run prints: the `fabrik apply` exit-0 branch (`:546`), its exit-2 branch (`:537-545`), the `fabrik refresh`
   ✅ branch, and its exit-2 branch at `:1282-1292` (W-4b1dfd76). Unit tests for all four branches in the
   existing CLI test module for apply and refresh (locate it with `grep -ln "Deployment complete" tests/`).
5. Red-on-revert in a throwaway worktree: neuter the inject-before-grant order, the `pending` → warning
   path, and each of the four print sites; watch each test fail; remove the worktree.
6. Closing sequence:
   1. `.venv/bin/python -m pytest -q tests/test_app_role_provision.py tests/test_payments_ingest_role.py tests/test_payments_fulfilment_real_pg.py` plus the CLI test module → all pass;
   2. `python3 scripts/enforcement/check_doc_sync.py` → record pairs for Phase C;
   3. `/fabrik-review-scoped` on Phase B's changed surface plus one hop, to a closing pass that confirms zero;
   4. commit the phase with explicit paths and the provenance trailers.

**Behavior Contract**
- **Given** a spec with `needs_payments_fulfilment` and `needs_database`, **When** `resolve_applicability` runs, **Then** it reports the `payments_fulfilment` row (`src/fabrik/orchestrator/infrastructure.py:250-263`)
- **Given** a freshly minted fulfilment role, **When** the block runs, **Then** `PAYMENTS_FULFILMENT_DATABASE_URL` is injected before the grant is attempted (`src/fabrik/orchestrator/infrastructure.py:871-907`)
- **Given** a grant path of `pending` for either role, **When** the block records its resource, **Then** it records `pending` and adds one `registrar_warnings` line, and the apply exits 0 (spec § The delta item 5)
- **Given** a grant that raises or returns `unknown`, **When** the block records its resource, **Then** it records `failed` and the apply exits 2 (spec § The delta item 5)
- **Given** a `registrar_warnings` line, **When** `fabrik apply` or `fabrik refresh` ends on success or on registrar failure, **Then** the line is printed as `⚠` in that summary (`src/fabrik/cli.py:546`, `:1282-1292`)

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
4. Mail infra (its beat; never edited by fleet): `.windsurf/rules/core/85-payments-billing.md:28` and
   `:45`, and `.windsurf/rules/saas/95-multi-tenant-saas.md:151`, name the ingest flag only and say the
   fulfilment login "does not exist yet"; send the new flag, variable and commit.
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

The Finish `/fabrik-review` is armed with this rubric (run at plan time; re-run at review time over the real diff):

```
# REVIEW RUBRIC — inject into EVERY finder prompt (generated by review_rubric.py)
## FLOOR — always injected, regardless of glob (spec L3; SERVICE surface)
### core/35-security-auth.md
### core/25-data-postgres.md
### core/30-ops.md
### 12-FACTOR (all twelve axes)
## MATCHED — packs whose globs hit the changed paths
### ai/50-agentic.md  (hit: src/fabrik/orchestrator/context.py, src/fabrik/orchestrator/infrastructure.py)
### core/10-python.md  (hit: src/fabrik/cli.py, src/fabrik/drivers/postgres.py, src/fabrik/orchestrator/context.py)
```

| Class | Where it bites in this plan |
|---|---|
| fail-open / fail-closed | `unknown` and every refusal must record `failed`; `pending` must never read `provisioned` |
| cost / limit edges | the 63-character role-name guard; the path parse's last-line rule with NOTICE output present |
| boundary / sentinel | no schema, partial schema, tables without `jobs`, changed signature, pre-migration install |
| behaviour without a test | every Behavior Contract row above has its test, seen red |
| secrets and credentials (core/35) | the password is minted once and delivered before the grant; never logged |
| role privileges (core/85, saas/95) | NOBYPASSRLS, NOCREATEROLE, no membership, never the app or ingest role |
| SQL identifier quoting | role names are validated and quoted; the regrole literal keeps the exact name |

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
- tests/test_app_role_driver.py
- docs/CONFIGURATION.md
- docs/reference/modules/drivers.md
- docs/development/reviews/2026-10-08-plan-2-payments-fulfilment-role-review.md

The CLI test module Phase B step 4 locates is added to this list when it is identified (one file, by grep).

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
- (b1) the SB-096 tripwire → Phase A step 1; (b2) the heavy round → Phase C step 6; (b3) no VPS write → Global Constraints;
- W-7ba06610 → Phase B step 3; W-4b1dfd76 → Phase B step 4; the infra pack mail → Phase C step 4.

(b) Cross-phase signatures: Phase B consumes `mint_payments_role(db_name, lane, dry_run)` and
`grant_payments_role(db_name, lane, dry_run)` exactly as Phase A produces them, and
`Shape.needs_payments_fulfilment` by that name; Phase C documents the same three names and
`PAYMENTS_FULFILMENT_DATABASE_URL`, `registrar_warnings`.

Fixed point: not claimed. `/fabrik-plan-review` converges it.

## Residual unknowns

- Resolved: fabrik-lib's function signature and body are unchanged since the spec (grounded); the hub's
  current lines (grounded); the auto-injected-variable doc convention (grounded).
- Open, with a resolution step:
  - SB-096 may land before execution and change the function's refusals or signature. Resolution: Phase A
    step 1 re-checks the signature; a changed signature is a `BLOCKED:` spec contradiction, and a
    same-signature refusal change needs only the real-PG tests re-run against the new migration.
  - The CLI test module for the apply and refresh summaries is not yet named. Resolution: Phase B step 4
    locates it by `grep -ln "Deployment complete" tests/` and adds it to File Scope before editing.

## Intake Inventory

| I# | Item (anchored) | Disposition | Where |
|---|---|---|---|
| I1 | the spec's nine IN items (spec § Intake Inventory I1-I8, I11) | IN | Phases A-C, per (a) above |
| I2 | brief: "fabrik-lib's open SB-096 reworks the refusal signal of payments_grant_fulfilment … the plan must name that tripwire" | IN | Phase A step 1; Residual unknowns |
| I3 | brief: "the spec touches the registrar (auth roles, a heavy surface: lane row 1b) … every phase boundary owes the full /fabrik-review" | IN, adjusted | `Profile: small` puts the one full `/fabrik-review` at Finish over the whole-plan diff, with scoped reviews per phase; that heavy round covers lane row 1b |
| I4 | brief: "no VPS write in any step" | IN | Global Constraints |
| I5 | W-4b1dfd76: "print registrar_warnings in fabrik refresh's exit-2 branch (cli.py:1282) as well as its ✅ branch" | IN | Phase B step 4 |
| I6 | W-d8505af5: "ingest lane has no changed-signature guard" | OUT-OF-SCOPE | not in spec § The delta; stays on W-d8505af5 |
| I7 | spec § Intake I9-I10: pack 85's lines and fabrik-lib's README sentence | OUT-OF-SCOPE | infra's beat (mailed in Phase C step 4) and fabrik-lib's repo (spec reply 01M3S2DM02) |

Intake: 7 items — 5 IN, 2 OUT-OF-SCOPE (each named above), 0 ASK.
