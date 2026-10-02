# The payments fulfilment-worker role in the hub registrar — design spec

Status: CONVERGED (/fabrik-spec-review, 2026-09-30/10-01, 6 passes; D-464)
Profile: delta — every intake item maps to code that exists today: the ingest-role path in
`src/fabrik/drivers/postgres.py:905-975`, its orchestrator block in
`src/fabrik/orchestrator/infrastructure.py:849-885`, its shape flag in `src/fabrik/spec_loader.py:333-345`
Work item: W-5985e74a (and W-7ba06610, folded in) · Request: fabrik-lib mail 01M3Q1QP9Z part (b); the
module side shipped at fabrik-lib D-337 (mail 01M3QTVA07)
Research ledger: `docs/reference/research/2026-09-30-payments-fulfilment-role-ledger.md` (25 rows)

## Personas

- **Primary — the payments consumer's fulfilment worker, and the project agent wiring it.** In the
  requester's words (fabrik-lib, 01M3Q1QP9Z part (b)): *"mint a `<db>_payments_fulfilment` role
  (NOBYPASSRLS, not a member of the owner) behind a shape flag. Then either inject
  `PAYMENTS_FULFILMENT_DATABASE_URL` or call `payments_grant_fulfilment`, whichever you prefer."* The worker
  claims a job from the project's `jobs` queue across tenants, reads its `org_id`, scopes its transaction to
  that org with the transaction-local tenant GUC, then writes `customers`, `subscriptions`, `purchases` and
  `payments_audit_log` (fabrik-lib `payments/README.md:458-470`; research row bp-04). The operator's standing
  instruction for this queue: work the fleet items one after another.
  **Step budget — the primary's loop, counted:**
  1. The project sets `shape.needs_payments_fulfilment: true` beside `needs_database: true` in
     `specs/services/<id>.yaml`.
  2. The hub runs `fabrik apply`. The registrar mints `<db>_payments_fulfilment`, injects
     `PAYMENTS_FULFILMENT_DATABASE_URL`, and reports `pending`, because there is no schema yet.
  3. The project applies fabrik-lib's `db/schema.sql` (a fresh install) or its scoped-roles migration (an
     existing one).
  4. The project creates its `jobs` queue table in `public`.
  5. The hub runs `fabrik apply` again, and the registrar grants the role through
     `payments_grant_fulfilment`.
  6. The worker is (re)deployed and reads the DSN from its `.env`.
  7. The worker calls `verify_service_role(conn, lane="fulfilment")` at boot.

  **7 steps.** Steps 3 and 4 belong to the project, and none of the seven is the hub's to skip.
- **The hub registrar (automated consumer, `fabrik apply`)** holds every duty this spec creates: it mints the
  role, runs the grant, injects the DSN, drops the role at decommission, and reports the grant path. No other
  role holds any of them.
- **fabrik-lib's `payments` module (automated, the grant's owner)** holds the grant logic and its refusals
  (`payments/db/migrations/2026-09-29-scoped-service-roles.sql:460-640`). The hub never re-implements it.
- **The webhook-ingest role `<db>_payments_ingest`** is a sibling, never a member: the fulfilment grant
  refuses a role that holds the ingest lane (migration :523-537), and the hub grants no membership between
  the two.
- **The operator** reads the apply summary: one warning line per payments role left `pending` (§ The delta
  item 5). The operator also approves this design.
- Out of the loop by construction: the app's tenant-scoped request role (unchanged), and every project that
  sets neither flag. Today that is all 72 service specs: `grep -l "needs_payments_ingest: *true"
  specs/services/*.yaml` returns none. The only `/opt` project carrying a vendored copy is youtube
  (`ls -d /opt/*/libs/payments` → `/opt/youtube/libs/payments`), and its spec sets no payments flag.

## Goal

A project that vendors fabrik-lib `payments` and runs its fulfilment worker gets a per-project
`LOGIN NOSUPERUSER NOBYPASSRLS` role, granted by the module's own `payments_grant_fulfilment`, with its DSN
injected once — through `fabrik apply`, like the ingest role, and never through a role that bypasses RLS.

## Why this exists

fabrik-lib's three-role model runs webhook ingest and the fulfilment worker as two separate NOBYPASSRLS
logins, with no BYPASSRLS role anywhere (`payments/README.md:395-409`). The hub mints only the first of the
two (`create_payments_ingest_role`). A project cannot mint the second itself: only the hub's registrar holds
`CREATE ROLE` on the shared `postgres-main`, running as the container superuser (`drivers/postgres.py`
`_run_sql`, `psql -U postgres`). So today a consumer's worker has no role. It either runs on a BYPASSRLS role,
which `95-multi-tenant-saas.md:150` bans for the request path and fabrik-lib now deprecates
(`README.md:437-454`), or it does not run. Row-level security then denies a NOBYPASSRLS non-owner every row
of `purchases` that no policy grants (research row pg-10), so there is no third option.

## What exists today (grounded)

- `src/fabrik/spec_loader.py:333-345` — `needs_payments_ingest`, requiring `needs_database`
  (`:394-404`).
- `src/fabrik/orchestrator/infrastructure.py:198-245` — `resolve_applicability`; the ingest row at
  `:234-245`. `:849-885` — the ingest provisioning block: create the role, inject
  `PAYMENTS_INGEST_DATABASE_URL` on a fresh password only, record the `payments-ingest-role` resource
  (`provisioned`, or `failed` inside a non-fatal handler).
- `src/fabrik/drivers/postgres.py:851-975` — since hub D-459: `_payments_grant_ingest_block` (delegate to
  `payments_grant_ingest`; raise when the payments tables exist but `jobs` does not; defer while the schema is
  absent), `_payments_grant_path_sql` (the batch's last line names `legacy`, `module` or `pending`), and
  `create_payments_ingest_role` returning `grants`.
- `src/fabrik/drivers/postgres.py:1691` — `drop_database`, which also drops the ingest role
  (`:1756`, `:1779`).
- W-7ba06610 — the orchestrator ignores `grants`, so a `pending` ingest step still reads `provisioned`.

## The delta — chosen approach (A: a new flag, delegate-only)

1. **`shape.needs_payments_fulfilment: bool = False`** in `spec_loader.Shape`, requiring
   `needs_database` (the same validator shape as `:394-404`). The flag is independent of
   `needs_payments_ingest`: ingest serves unsigned-provider webhooks, the worker serves every consumer with a
   job queue.
2. **Mint, deliver, THEN grant — for BOTH payments roles.** Today `create_payments_ingest_role` creates the
   role with a fresh password and then runs a grant batch that can raise. A raise loses the password before
   the orchestrator injects it, so every later apply sees an existing role and never delivers a DSN (executed
   in review round 1 on the live driver). The driver is therefore split into two calls:
   - `mint_payments_role(db_name, lane)` runs `CREATE ROLE … LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE
     NOBYPASSRLS` with a CSPRNG password on create only (research row bp-05). It grants `CONNECT` on the
     database and `USAGE` on schema `public`, grants no membership, and returns `{user, password|None,
     status}`.
   - `grant_payments_role(db_name, lane)` runs the grant batch and returns `grants`.

   The orchestrator injects the DSN between the two calls, so a failing GRANT no longer strands the
   credential. An `inject_env` failure still can, exactly as it can for every DSN the registrar injects
   today. No role is stranded by the old ordering: no service spec has ever set `needs_payments_ingest:
   true` (`git log --all -S "needs_payments_ingest: true" -- specs/services` finds no commit).
   `lane` is `ingest` or `fulfilment`. The role is `{db_name}_payments_ingest` or
   `{db_name}_payments_fulfilment`, each with the 63-character guard.
3. **The fulfilment grant is one DO block, evaluated in this order:**
   1. No function named `payments_grant_fulfilment` exists in a schema on the session's search_path
      (`pg_catalog.pg_proc` joined to `pg_catalog.pg_namespace`, `nspname = ANY (current_schemas(false))`).
      A same-named function outside the search path counts as absent, because `to_regprocedure` would not
      resolve it either.
      - All six payments tables resolve: RAISE, naming fabrik-lib's migration file (a pre-migration install).
      - Otherwise: path `pending` (no schema yet).
   2. A function of that name exists, but `to_regprocedure('payments_grant_fulfilment(pg_catalog.regrole)')`
      is NULL: RAISE, naming the signature the hub calls. fabrik-lib changed it, and the hub constant must
      follow (see § Lifecycle). An additive parameter lands here too (review round 2 executed it:
      `to_regprocedure` of the one-argument form is NULL against a `(regrole, text DEFAULT '')` function).
   3. The function is present, but not all six payments tables resolve: path `pending` (a partial schema).
   4. All six resolve but `jobs` does not: RAISE, naming `jobs`.
   5. Otherwise: `PERFORM payments_grant_fulfilment('"<role>"'::pg_catalog.regrole)`, path `module`.

   Notes on the block:
   - "The six payments tables" means exactly `plans`, `customers`, `subscriptions`, `webhook_events`,
     `purchases` and `payments_audit_log`, the function's own list (migration :485-486), with `jobs` as the
     seventh.
   - The probes return NULL for a missing object (pg-08) and resolve through the registrar session's
     search_path (pg-09). In a Fabrik project database that is `public`. The registrar grants `USAGE` on
     `public` only, so the design requires `jobs` in `public`. A `jobs` elsewhere reads as missing (item
     3.4) and fails the step by name; it is never granted half-way.
   - The quoted role literal keeps the exact name (pg-06). The role is minted before the cast runs, so the
     cast cannot raise (pg-07).
   - There is no hub-written fallback grant. Without the function there is no fulfilment policy to extend,
     and writing one would fork the module's core.
4. **The path is read, never assumed.** A final SELECT prints the path as the batch's last stdout line (the
   measured parse of D-459: ps-01, ps-03, ps-06, ps-07). Anything else is `unknown`, and the driver RAISES
   on `unknown`, because an unverified grant is a failure, not a deferral.
5. **The orchestrator** (`infrastructure.py`):
   - It gains a `payments_fulfilment` applicability row, asserted by `resolve_applicability` unit tests like
     the ingest row. Neither row is printed, since `_REGISTRAR_ORDER` names neither.
   - The fulfilment block is placed AFTER the ingest block, for the upgrade case. An install first granted
     by the legacy ingest block still gives the ingest role table-level SELECT until `payments_grant_ingest`
     revokes it (migration :354). `payments_grant_fulfilment`'s postcondition refuses while any role on
     `payments_ingest_sel` can read a column beyond the three (migration :592-638). Running ingest first
     clears that state in the same apply. On a fresh install either order succeeds (review round 1 executed
     both).
   - Each block injects its DSN on a fresh password only, rewritten for spokes like the ingest DSN
     (`PAYMENTS_FULFILMENT_DATABASE_URL` for the new role).
   - Each block records its resource from the path, for BOTH payments roles (folding in W-7ba06610):
     - `module` or `legacy` records `provisioned`.
     - `pending` records `pending`, logs a WARNING, and appends one line to a new
       `DeploymentContext.registrar_warnings` list (`src/fabrik/orchestrator/context.py`, beside
       `registrar_failures`). `cli.py` prints those lines as `⚠` in every summary a completed run prints:
       the `fabrik apply` exit-0 branch (the success banner), its exit-2 branch (the `registrar_failures`
       list), and the `fabrik refresh` summary. A `pending` lane is therefore never hidden by another
       registrar's failure. `pending` is not a registrar failure, so it alone leaves the apply at exit 0: a
       first apply before the schema is the expected case.
     - A raise (the pre-migration, changed-signature and missing-`jobs` states, a refusal, `unknown`) records `failed` through
       the existing non-fatal handler, which enters `ctx.registrar_failures` and makes the apply exit 2.
     - A dry run keeps `dry_run`.
6. **Decommission:** `drop_database` drops `{db}_payments_fulfilment` beside the ingest role, in both of its
   branches (`:1756`, `:1779`).
7. **A refusal from the function is loud:** psql exits 3 under `ON_ERROR_STOP` (ps-04), `_run_sql` raises,
   and the step records `failed` with fabrik-lib's message.

The superuser caller is valid. `payments_grant_fulfilment` is SECURITY INVOKER (pg-02) and checks the
GRANTEE, not the caller. The superuser bypasses the table-owner requirement on policies and grants (pg-03,
pg-04, pg-05, pg-13). This is the same caller D-459 proved for ingest.

**1c grounding — why a separate least-privilege login per duty:** AWS directs *"Make sure the login is not
the table owner or defined with BYPASSRLS"* (bp-01). PostgreSQL: superusers and BYPASSRLS roles *"always
bypass the row security system"* (bp-02). Crunchy Data: *"give out role privileges based on the least amount
of privilege the role should have"* (bp-03).

**Judge panel (3 Sonnet seats, handed the approaches without a recommendation):** all three ranked A first
and killed B, C and D. None split, so no split verdict is carried to the approval.

## Contract deltas

- `specs/services/*.yaml` gains an optional `shape.needs_payments_fulfilment` (default false, requires
  `needs_database`). An additive field; no existing spec changes meaning.
- A new auto-injected env var `PAYMENTS_FULFILMENT_DATABASE_URL`, documented in `docs/CONFIGURATION.md`
  beside `PAYMENTS_INGEST_DATABASE_URL`. fabrik-lib names no DSN variable for either lane
  (`grep _DATABASE_URL /opt/fabrik-lib/payments/README.md` matches only `TEST_DATABASE_URL`), so the hub's
  ingest name sets the convention.
- The driver's public functions change: `create_payments_ingest_role` is replaced by
  `mint_payments_role(db_name, lane)` and `grant_payments_role(db_name, lane)` (§ The delta item 2).
  The build updates every caller and test that names it. `git grep -n create_payments_ingest_role c0a4a44aa --
  src tests docs | wc -l` prints 30 tracked lines at c0a4a44aa; frozen plans and specs among them keep the
  old name as history.
- `DeploymentContext` gains `registrar_warnings: list[str]`, read by `cli.py`'s apply summary.
- No data contract or UI change: the hub has no `docs/data-contract.md` for this surface, and no GUI.

## Rejected alternatives

- **B — extend `needs_payments_ingest` to mint both roles.** One flag would carry two independent
  capabilities. A project that needs only the worker would get an unused cross-tenant ingest role, which
  breaks least privilege (bp-03), and the flag's own description (unsigned-provider webhooks) would become
  false. Killed by all three judges.
- **C — a hub-authored fulfilment grant block for installs without the function.** It re-implements the
  module's grants, policy shape and leak postcondition, all security-critical, in a second copy that drifts
  with every fabrik-lib release. That is the drift class D-459 retired for ingest, and a fork of a vendored
  core. Killed by all three.
- **D — no registrar role; each project mints its own worker login.** Infeasible: projects hold no
  `CREATE ROLE` on `postgres-main`. Killed by all three.
- **Adjacent variants, each also rejected:**
  - Call the function but inject no DSN (the project builds its own URL): a role with no credential
    delivery is unusable.
  - Inject the DSN but skip the grant: a NOBYPASSRLS login with no grant reaches nothing (pg-10).
  - One shared worker+ingest login: refused by the module (migration :523-537).
  - Grant membership in the ingest role: refused at boot by `verify_service_role` step 6b (01M3QTVA07).

## Lifecycle

- **Adoption / first run:** zero specs set either payments flag today, so adoption starts when the first
  payments consumer sets the flag. Its first apply usually lands before the schema, so it reads `pending` and
  a later apply grants.
- **Growth:** each consumer adds one login and one DSN on `postgres-main`. Roles carry no practical count
  limit. The load that grows is the worker's connection pool, which counts against `postgres-main`
  exactly as every service's `DATABASE_URL` pool already does. This design adds no new growth threshold of
  its own.
- **Degradation:**
  - A failed step is a `failed` resource in `ctx.registrar_failures`, and the apply exits 2.
  - A `pending` step is a WARNING line in the apply summary, and the apply exits 0 (§ The delta item 5).
  - A fabrik-lib change to the function's signature, additive or not, fails the step with the
    changed-signature error (§ The delta item 3.2). The fix is a hub change: the signature constant
    (`_PAYMENTS_GRANT_FULFILMENT_FN`, beside the ingest one at `postgres.py:776`) is hand-maintained
    against fabrik-lib's migration. That is the one ongoing maintenance cost this design carries.
  - The ingest role and the app role are unaffected by a failed fulfilment step, which runs in its own
    non-fatal handler.
- **Retirement / supersession:** `drop_database` removes the role. If fabrik-lib ever ships a platform-side
  grant, the flag is retired by a D-row and its validator.

## External dependencies

- **fabrik-lib `payments`** (vendored library; internal ground truth): `payments_grant_fulfilment`
  (migration :460-640), the three-role model (`README.md:395-454`), the worker's claim-then-scope order
  (`README.md:458-470`).
- **PostgreSQL 16 documentation**, every page fetched 2026-09-30 (the research ledger holds each verbatim
  quote):
  - `ALTER POLICY` replaces the role list when given one; changing a policy needs table ownership (pg-01,
    pg-04): https://www.postgresql.org/docs/16/sql-alterpolicy.html
  - SECURITY INVOKER runs as the caller (pg-02): https://www.postgresql.org/docs/16/sql-createfunction.html
  - A superuser's GRANT acts as the owner's (pg-03): https://www.postgresql.org/docs/16/sql-grant.html
  - A superuser bypasses permission checks (pg-05): https://www.postgresql.org/docs/16/role-attributes.html
  - The quoted reg* input keeps case, and the lookup follows the schema path (pg-06, pg-09):
    https://www.postgresql.org/docs/16/datatype-oid.html
  - `to_regclass` and `to_regprocedure` return NULL for a missing object; a `::regrole` cast raises instead
    (pg-07, pg-08): https://www.postgresql.org/docs/16/functions-info.html
  - Row security defaults to deny (pg-10), and adding a policy is the table owner's privilege (pg-13):
    https://www.postgresql.org/docs/16/ddl-rowsecurity.html
  - psql's `-t` and `-A`, and exit status 3 under `ON_ERROR_STOP` (ps-01, ps-03, ps-04):
    https://www.postgresql.org/docs/16/app-psql.html
- **Best-practice sources** (1c), each fetched 2026-09-30:
  - AWS Database Blog (bp-01, found by exa search):
    https://aws.amazon.com/blogs/database/multi-tenant-data-isolation-with-postgresql-row-level-security/
  - PostgreSQL row security (bp-02): https://www.postgresql.org/docs/current/ddl-rowsecurity.html
  - Crunchy Data (bp-03, found by exa search):
    https://www.crunchydata.com/developers/playground/postgres-users-and-roles

## fabrik-lib verdict

| Capability | Verdict | Module | Why |
|---|---|---|---|
| The fulfilment grant, its policy and its refusals | VENDOR as-is | `payments` (`payments_grant_fulfilment`) | the module owns the only copy; the hub calls it |
| Role minting, DSN injection, decommission | BUILD (hub) | — | registrar-only by construction: only the hub holds `CREATE ROLE` |

No `🆕 fabrik-lib candidate`: the build half is hub infrastructure, not a reusable module.

## Constraints digest

| Rule | Verbatim | file:line | Effect on this design |
|---|---|---|---|
| no BYPASSRLS on the request path | "The request path's login role holds no `BYPASSRLS` and is a member of no role that does." | `.windsurf/rules/saas/95-multi-tenant-saas.md:150` | the worker login is NOBYPASSRLS and granted no membership |
| cross-tenant payments is not an admin case | "**Cross-tenant payments ingest is not an admin case** — never route webhook ingest through `fabrik_admin` (it is `NOLOGIN`) or any `BYPASSRLS` role." | `.windsurf/rules/saas/95-multi-tenant-saas.md:151` | the sibling lane gets the same treatment: a scoped login, never an admin role |
| the queue | "**Queue:** fulfilment INSERTs into a `jobs` table — vendor `fabrik-lib/job-queue` alongside it (`75-workers-jobs.md`)." | `.windsurf/rules/core/85-payments-billing.md:27` | a missing `jobs` fails the step, naming it |
| the ingest precedent | "**Cross-tenant webhook writes:** set `shape.needs_payments_ingest: true` (with `needs_database: true`) in the service spec; `fabrik apply` mints the scoped `NOBYPASSRLS` ingest role and injects `PAYMENTS_INGEST_DATABASE_URL`" | `.windsurf/rules/core/85-payments-billing.md:28` | the new flag and DSN mirror this shape |
| shape contract | "The shape contract is canonical: code MUST match it." | `CLAUDE.md` § Spec contract awareness | the role exists only when the spec declares the flag |

## Shape / infra implications

Scaffold type: none (hub registrar). Shape: one new optional flag, `needs_payments_fulfilment`, requiring
`needs_database`. Registrars: postgres only. No port, no compose change, no new container.

## Documentation landing sites

- `docs/CONFIGURATION.md` — a `PAYMENTS_FULFILMENT_DATABASE_URL` section beside the ingest one. The
  ingest section's sentence at `:216` ("the fulfilment WORKER does NOT use this role — … runs as the
  ordinary tenant role with `SET app.current_org`") is rewritten to point at the new role.
- `docs/reference/modules/drivers.md:31` — the `postgres.py` row names `mint_payments_role` and
  `grant_payments_role` in place of `create_payments_ingest_role`.
- `.windsurf/rules/core/85-payments-billing.md:28` and `.windsurf/rules/saas/95-multi-tenant-saas.md:151` —
  these name the ingest flag only. That is infra's beat (the rules packs), so it is mailed to infra with the
  build, never edited by fleet.
- `CHANGELOG.md`, `docs/DECISIONS.md` (the build's D-row), and `INDEX.md` for any new test file.

## Cost

About 120 lines in `drivers/postgres.py`, about 40 in `infrastructure.py`, about 15 in `spec_loader.py`,
about 5 in `orchestrator/context.py` and about 10 in `cli.py`, plus tests. No runtime cost: one role per opted-in project, and one DO block per apply.

## Validation

- **Real PostgreSQL 16 over fabrik-lib's schema** (the `scratch_pg()` pattern of
  `tests/test_payments_ingest_real_pg.py`):
  - The function path grants. The fulfilment role then does its whole duty from a real login session: it
    claims a `jobs` row with `SELECT … FOR UPDATE SKIP LOCKED` and `UPDATE`, with no tenant GUC set. It
    scopes with `set_config('app.tenant_id', …, true)`. It inserts a `purchases` row through
    `payments_fulfilment_ins`.
  - `verify_service_role(conn, lane="fulfilment")` passes on that connection. It is imported from the box's
    fabrik-lib checkout under the same skip rule as the schema.
  - The payments tables without `jobs` fail the step, naming `jobs`.
  - No schema, and a partial schema, both read `pending`.
  - A pre-migration install (function dropped, tables present) fails the step, naming the migration.
  - A PUBLIC `payments_fulfilment_ins` refuses.
  - Upgrade ordering: an install first granted by the legacy ingest block, then migrated, grants both lanes
    in one apply with ingest first.
  - The fulfilment role is not a member of the ingest role.
  - A failing grant still delivers the DSN, for both lanes: the item 2 regression.
- **Unit:**
  - The Shape validator refuses the flag without `needs_database`.
  - `resolve_applicability` reports the `payments_fulfilment` row.
  - The DSN is injected only on a fresh password, and before the grant runs.
  - The resource status follows the path for both roles (`pending` warns; `unknown`, and every raise, records
    `failed`), and the apply summary prints the `registrar_warnings` line, which closes W-7ba06610.
  - A function present under a changed signature fails the step with the changed-signature error, never
    the pre-migration one.
  - `drop_database` drops the new role in both branches.
- **Red-on-revert** for each new behaviour; the mutation battery on copies, never the tree.

## Decisions taken

- **Approach A, over B, C and D** (judge panel 3/3). Reversible: an additive flag touching 0 of 72 specs.
  The build mints its D-row.
- **The DSN name `PAYMENTS_FULFILMENT_DATABASE_URL`**, by the hub's own ingest convention. fabrik-lib names
  none.
- **No fallback grant without the function**; a pre-migration install fails the step, loudly.
- **W-7ba06610 folded in:** the resource status follows the grant path for both payments roles, because
  the orchestrator block is edited here anyway. `pending` warns and exits 0; `unknown` is a failure.
- **Mint, deliver, then grant, for both roles.** This fixes the credential loss that D-459's missing-`jobs`
  raise made reachable for ingest, found in this spec's review round 1.

## Open / blocking unknowns

- **Resolved:**
  - The superuser caller (pg-02, pg-03, pg-05; proven for ingest under D-459).
  - The last-line parse with a NOTICE present (ps-06, measured).
  - The function's refusals and requirements (migration :460-640).
- **Open, with a resolution step:** fabrik-lib's README (`:413-418`) still says the hub's ingest registrar
  does "only PART" of the grant, which was stale since D-459 merged (c0a4a44aa). Resolution: fabrik-lib
  was told in reply 01M3S2DM02, and its README edit is theirs.

## Review record

`/fabrik-spec-review`, native seats partitioned by section (pool off, D-181): Opus on the rule and grammar
sections, Sonnet on the rest, and a Sonnet `fabrik-researcher` on the cited facts, with one refuter per slice
executing every candidate.

| Pass | seats · axes re-checked | counters | method | spec md5 (start → end) |
|-----:|---|---|---|---|
| Pass 1 | opus×1 + sonnet×1 + researcher sonnet×1 (+ refuter×3) · all axes | found: 21, new: 21, confirmed: 15, fixed: 15, unexecuted: 0, edits: 15 | method: citation — full partitioned pass; 2 refuted (the youtube evidence); rules-O1 re-executed on the live driver, and the upgrade-ordering claim executed on real PG16 | b124cf77 → b782cbfa |
| Pass 2 | the round-1 slice owners (opus×1 + sonnet×1 + researcher sonnet×1, + refuter×3) · delta over the pass-1 hunks + one hop | found: 6, new: 6, confirmed: 4, fixed: 4, unexecuted: 0, edits: 5 | method: re-derivation — 18 of 19 claims NOW_FALSE; rest-S5 refuted (the fresh-install either-order evidence is round 1's rules-O6 run); the reference count re-derived to 30 | b782cbfa → a53d422d |
| Pass 3 | the round-1 slice owners (opus×1 + sonnet×1, + refuter×2) · delta over the pass-2 hunks + one hop | found: 2, new: 2, confirmed: 2, fixed: 2, unexecuted: 0, edits: 2 | method: re-derivation — 5 of 5 claims NOW_FALSE; the scope-growth stop fired (two of the last three rounds all own-fix); the one-hop ingest signature gap recorded to W-d8505af5 | a53d422d → 736c681a |
| Pass 4 | the round-1 rules owner (opus×1, + refuter×1) · remainder round over rules-O20, rules-O21 | found: 1, new: 1, confirmed: 0, fixed: 0, unexecuted: 0, edits: 0 | method: re-derivation — both NOW_FALSE; rules-O22 (refresh's exit-2 branch unnamed) RECORDED — measured onto W-4b1dfd76 under the scope-growth stop. Then the flip gate (check_spec_convergence on a flipped scratch copy) reported SILENT-1a: the spec carried no URLs of its own; the dated URLs were added to § External dependencies from the research ledger | 736c681a → 736c681a, then 7cde8cf0 after the gate fix |
| Pass 5 | the round-1 facts owner (researcher sonnet×1, + refuter×1) · the § External dependencies hunk | found: 1, new: 1, confirmed: 1, fixed: 1, unexecuted: 0, edits: 1 | method: re-derivation — 10 of 11 URL/claim pairs match their ledger rows; the ddl-rowsecurity bullet cited pg-13 for a bypass claim, and the unsupported half was deleted. The orchestrator status-probed 10 URLs at 200 and read the AWS page through exa (the box's DNS cannot resolve aws.amazon.com) | 7cde8cf0 → 34908517 |
| Pass 6 | the round-1 facts owner (researcher sonnet×1, + refuter×1) · the corrected bullet | found: 0, new: 0, **confirmed: 0**, fixed: 0, unexecuted: 0, edits: 0 | method: re-derivation — facts-S1 NOW_FALSE, both halves match pg-10 and pg-13 verbatim; standing clean since pass 1: every other class | 34908517 → 34908517 ✓ → **CONVERGED** |

## Intake Inventory

| I# | Item (anchored) | Disposition | Where |
|---|---|---|---|
| I1 | Operator, standing: handle the fleet items one after another | IN | this run takes the next claimed item, W-5985e74a |
| I2 | W-5985e74a: "mint fabrik-lib payments' fulfilment-worker role (INSERT+SELECT on purchases plus its two RLS policies) once fabrik-lib defines it … and the ingest role must NOT get the grant" | IN, CHANGED | § The delta items 2-3. What shipped differs from the item's wording: the module creates ONE policy, `payments_fulfilment_ins` (INSERT, migration :575-590), and SELECT on `purchases` comes from the tenant policies once the worker scopes. The ingest role never gets the grant, and the module refuses a lane-holder |
| I3 | Mail 01M3Q1QP9Z (b): "mint a `<db>_payments_fulfilment` role (NOBYPASSRLS, not a member of the owner) behind a shape flag" | IN | § The delta items 1-2 |
| I4 | Mail (b): "either inject PAYMENTS_FULFILMENT_DATABASE_URL or call payments_grant_fulfilment, whichever you prefer" | IN | both: the call grants, the DSN delivers the credential (§ Rejected alternatives, adjacent variants) |
| I5 | Mail 01M3QTVA07: "the order is payments_grant_ingest FIRST … then payments_grant_fulfilment" | IN | § The delta item 3 |
| I6 | Mail 01M3QTVA07: "never grant the minted fulfilment role membership in the ingest role, or the reverse" | IN | § The delta item 2 (no membership) |
| I7 | W-5985e74a next: "a test that loads the vendored schema and records a purchase as that role" | IN | § Validation, first bullet |
| I8 | W-7ba06610: the orchestrator records provisioned whatever `grants` says | IN | § The delta item 4 |
| I9 | Mail 01M3Q1QP9Z (c): pack 85's `verify_service_role` lines and the PayTR blocker | OUT-OF-SCOPE | infra's beat, still in infra's queue on that mail (confirmed by infra 2026-09-30); the pack edits for the new flag go to infra with the build (§ Documentation landing sites) |
| I10 | fabrik-lib README's stale "only PART" sentence about the hub | OUT-OF-SCOPE | fabrik-lib's repo; told in reply 01M3S2DM02 |
| I11 | Review round 1 (executed on the live driver): a raising grant batch loses the ingest role's one-time password (D-459's missing-`jobs` raise made it reachable) | IN | § The delta item 2 (mint, deliver, then grant, for both roles) |

Intake: 11 items — 9 IN, 2 OUT-OF-SCOPE (each named above), 0 ASK.
