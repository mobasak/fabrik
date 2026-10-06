# PostgreSQL 16 → 18 — the fleet database upgrade

Status: DRAFT (/fabrik-spec, 2026-10-06 — awaiting /fabrik-spec-review)
Profile: delta — every IN intake item maps to something that runs today (one production cluster, the WSL dev
cluster, the hub's CI generator and test containers, the version registry and the rule packs that read it, and
the project pins measured below). The delta changes the server major and re-points every statement of it; it
adds no service and no table.

Work item: W-fd1c7f7a. Operator ruling: D-612 (gate W-498d906a). Research ledger:
`docs/reference/research/2026-10-06-postgresql-18-upgrade-ledger.md` (`check_research_ledger` green). Supersedes
`docs/development/plans/archived/2026-05-25-postgresql-18-upgrade.md` (planned 2026-05-25, never started; it
predates the spoke fleet, the Docker image's PG18 layout change and today's 45 projects).

## Personas

- **The operator** owns the two windows: the WSL window (local; a dev outage only) and the hub window (a
  production outage of every service that uses `postgres-main`). Step budget for the hub window: one write
  freeze, one dump, one container swap, one restore, one battery to read; rollback is one compose revert and one
  `up`, with the old volume untouched.
- **The fleet agent** writes the plan, lands every hub repo change on its branch, proves each locally against a
  scratch PG18 container, and never touches a VPS or a live database outside a window the operator opened.
- **Infra** (merge owner, owner of `.windsurf/rules/` and the command corpus) merges the hub branch and renders
  the rule packs; the pack edits are drafted here and handed over.
- **The 45 project repos** receive their pin and doc edits as fabrik-mail requests (a hub agent never edits
  another repo, `CLAUDE.md` § HARD STOPS); each project's own agent applies and gates them.
- **Every service on `postgres-main`** sees one reconnect at the cutover and nothing else: same host name, same
  port, same database names, same roles and passwords.

## Goal

Every PostgreSQL the fleet runs is major 18 — the WSL dev cluster, `postgres-main` on the hub, and every image,
CI service and test container a repo pins — and every rule, claim and doc that states the major says 18. No data
is lost, every database's contents verify after the move, and the old 16 data stays on disk until the operator
releases it.

## Why this exists

The operator ruled it (D-612, verbatim): "yes it must be done in all opt projects, wsl, all vps servers and our
rules must be updated in .windsurf/rules". PG16 is supported until 2028-11-09; PG18 until 2030-11-14 (ledger
pg-02), so this buys two more years before the next forced move. PG18 also ships native `uuidv7()` (pg-41),
which today's rule packs work around app-side (`core/25-data-postgres.md:163`). And the registry already
anticipates the flip: `.windsurf/rules/versions.yaml:17` carries `postgres_major: "16"` with the note "flip =
fleet DB upgrade".

## What exists today (grounded)

### The production cluster — one, on the hub

- `infra/vps1/postgres/compose.yaml:3` — `image: postgres:16-alpine`, a floating 16 tag; data on the external
  named volume `postgres-data` mounted at `/var/lib/postgresql/data` (`:8`, `:24-26`); 2G memory limit
  (`:11-14`); `pg_isready` healthcheck (`:15-21`); published only on the mesh, `10.99.0.1:5432` (`:22-23`). No
  init scripts, no `command:` override.
- **The spokes run no Postgres.** `infra/vps2/` and `infra/vps3/` hold backrest, monitoring-agent and traefik
  only; the one spec that targets a spoke (`specs/services/spoke-canary.yaml:8`) has `needs_database: false`.
  Spoke services reach the hub over the mesh: `_rewrite_shared_infra_host`
  (`src/fabrik/orchestrator/infrastructure.py:134-152`) rewrites `@postgres-main:` to `10.99.0.1` for any
  `target_vps != vps1`. No other Postgres server exists in the repo (ocoron-com runs MariaDB; Authelia uses
  `redis-main`). "All VPS servers" (D-612) is therefore one cluster plus a reconnect check on the spokes.
- **Databases.** 69 specs in `specs/services/`; 22 with `needs_database: true` name 19 distinct databases
  (registrar naming: `depends.postgres` if set, else the spec id with `-`→`_`,
  `src/fabrik/orchestrator/infrastructure.py:744-749`), plus `glitchtip` (`infra/vps1/glitchtip/compose.yaml:7`),
  `fabrik_analytics` (created on every apply, `infrastructure.py:690-715`) and the system `postgres` database.
  The authoritative list lives on the hub at `/opt/monitoring/configs/postgres/allocations.json`
  (`src/fabrik/drivers/postgres.py:72`), not in the repo — the plan's first window step reads `\l` live.
- **Extensions in use:** `plpgsql` everywhere; `pg_trgm` installed in one database (probe 2026-09-22,
  `.windsurf/rules/core/65-rag-search.md:61`); `vector` is not available on the image. Nothing uses pg_cron or
  PostGIS (both REJECTED in the ledger, pg-39/pg-40).
- **All SQL and dumps run inside the container.** `_run_sql` pipes into `docker exec -i postgres-main psql`
  (`src/fabrik/drivers/postgres.py:111-137`); the nightly `pg_dumpall` in `/opt/backups/pre-backup.sh` (host cron
  `30 1 * * *`, `scripts/bootstrap/bootstrap-hub.sh:89`) and the per-database `pg_dump -Fc` loop
  (`docs/operations/deployment.md:538`) are `docker exec postgres-main …` — the client always matches the
  server, so no host binary is version-coupled.
- **Version-sensitive role code.** The app-role grant batch uses `GRANT … WITH INHERIT FALSE, SET TRUE` and
  reads `pg_auth_members.inherit_option/set_option` (`src/fabrik/drivers/postgres.py:1174`, `:1244`) — PG16+, so
  valid on 18. Two behaviours were *measured on PG16* (`:1090`, `:1102`: a superuser's `REVOKE … GRANTED BY`
  removes nothing, so the code revokes as the grantor) — re-measured on 18 in the plan.
- **Monitoring.** `prometheuscommunity/postgres-exporter:v0.15.0` (`infra/vps1/monitoring/compose.yaml:178`)
  queries `pg_stat_bgwriter`, whose `buffers_backend*` columns moved in PG17 (pg-13) — see § Compatibility.

### The WSL dev cluster

Native apt PostgreSQL 16 at `localhost:5432`, one `{project}_dev` database per project
(`.windsurf/rules/core/25-data-postgres.md:34-39`, `scripts/create_pg_dev_db.sh:17-30`); the parity rule
requires the same major as `postgres-main` (`.windsurf/rules/core/30-ops.md:311-321`). It also hosts
`fabrik_analytics` (`docs/superpowers/specs/2026-07-26-catalog-extraction-design.md:144`) and session-recall's
database (`specs/services/session-recall.yaml:14`).

### The hub's own pins (2,047 files scanned)

| What | Where | Today |
|---|---|---|
| version registry | `.windsurf/rules/versions.yaml:17` | `postgres_major: "16"` |
| rule-pack spans the renderer fills | `core/25-data-postgres.md:36,163`, `core/65-rag-search.md:61` (×3) | 5 spans of `<!--v:postgres_major-->` |
| rule-pack literals the renderer cannot see | `core/25-data-postgres.md:23`, `core/30-ops.md:320` | `postgres:16-alpine` in dated probes |
| claims rows | `.windsurf/rules/CLAIMS.yaml` `pg-fleet-major`, `fleet-postgres-main-no-pgvector`, and the musl row | state major 16 |
| CI generator for scaffolded projects | `src/fabrik/ci_scaffold.py:33-34` | `postgres:16`, `pgvector/pgvector:pg16` (bypasses the registry) |
| production image | `infra/vps1/postgres/compose.yaml:3` | `postgres:16-alpine` (bypasses the registry) |
| real-PG test container | `tests/test_app_role_real_pg.py:30` (also used by `tests/test_payments_ingest_real_pg.py:19`) | `postgres:16` |
| tests pinning the CI images | `tests/test_ci_scaffold.py:29-30,42` | assert `pg16` / `postgres:16` |
| docs stating the major | `agents-fabrik.md:170,186,188`, `README.md:859`, `docs/infrastructure/vps-complete-inventory.md:120,168`, `docs/operations/disaster-recovery.md:74`, `docs/reference/technology-stack-decision-guide.md:21,518`, `docs/reference/prebuilt-app-containers.md:87`, `docs/traycer/fabrik-workflow.md:412` and ~4 more | "PostgreSQL 16" |
| scripts | `scripts/generate_vps_inventory.py:72`, `scripts/container_images.py:565` | 16 |

The renderer (`scripts/sysadmin/rules_render_versions.py`, `_SPAN` at `:34`, `--check` at `:86`) rewrites spans
only; its loose-literal warning (`_LOOSE`, `:36-50`) has no `postgres:N-alpine` shape. `version_registry.py:26`
(`REQUIRED_KEYS`) omits `postgres_major`, so no code reads it.

### The project pins (45 project directories scanned under /opt, worktree copies excluded)

Every pin and every current doc states **16**; nothing is on 17 or 18; no `postgres:latest`.

- **Images and CI services (22 locations, 8 projects):** fabrik (above), tryton-crm `compose.dev.yaml:71`
  (`postgres:16-bookworm`), tojlo-mail `docker/docker-compose.local.yml:38` and two test notes,
  trade-intelligence (CI `pgvector/pgvector:pg16` and three scripts/tests), gmail-account-creator and
  fabrik-claim-validator (CI + `scripts/ci_local.sh:8`), youtube (CI `.github/workflows/test.yml:15`),
  site-provisioner (a fixture string).
- **Client tooling:** calendar-orchestration-engine `Dockerfile.scheduler:12` installs an unpinned
  `postgresql-client` on a Debian base; youtube and the hub spec mention `apt install postgresql-16-pgvector`;
  trade-intelligence and session-recall assert `pg_dump >= 16.x`; four committed `schema.sql` files carry
  "Dumped by pg_dump version 16.x" headers.
- **Docs:** ~70 lines across 27 projects, plus the baseline every project carries a copy of (`agents-fabrik.md`,
  `CLAIMS.yaml`, the technology guide), which the governance sync refreshes from the hub.
- **UUIDs:** 0 projects call native `uuidv7()`; 17 use `uuid_utils` app-side; **brand-identiy-creator** calls
  `uuid_generate_v7()` from the `pg_uuidv7` extension (`/opt/brand-identiy-creator/db/schema.sql:14`, migrations
  0001/0008/0010/0018), which `postgres-main` does not offer — a pre-existing deploy blocker this upgrade can
  retire (§ The delta, D7).
- **trade-intelligence's production database is Supabase**, on Postgres 17 (pg-45) and on Supabase's cadence.

## The delta — chosen approach (A: dump and restore into a fresh PG18 volume)

### D1 — The hub cluster: dump/restore into a new volume, the old one kept

1. **Freeze writes**: stop every service container that holds a `postgres-main` connection (the plan derives
   the list from `docker ps` + the spec inventory at window start); `postgres-main` itself stays up.
2. **Dump with the PG18 client** (pg-06): `docker run --rm --network fabrik postgres:18.6-alpine pg_dumpall -h
   postgres-main -U postgres` into `/opt/backups/pg16-final-<ts>.sql`, plus a per-database `pg_dump -Fc` of each
   database for a granular restore. Record per-database row counts (`pg_stat_user_tables` sums plus an exact
   `count(*)` on each database's largest tables) and the role list into a manifest.
3. **Swap the container**: compose image → `postgres:18.6-alpine` (pg-34), volume → a NEW external volume
   `postgres18-data` mounted at `/var/lib/postgresql` (the PG18 image's VOLUME and PGDATA
   `/var/lib/postgresql/18/docker`, pg-35). The old `postgres-data` volume is untouched — the PG18 image refuses
   to start on a volume at `/var/lib/postgresql/data` (pg-36), so the bare image bump is never an option.
4. **Restore** the `pg_dumpall` into the empty PG18 cluster (initdb with checksums on, the PG18 default, pg-05),
   then `ANALYZE` every database.
5. **Verify** against the manifest (§ Validation), then restart the services and run the battery.

### D2 — WSL first, as the rehearsal

The WSL cluster moves first, with the same dump → fresh cluster → restore → verify sequence, using Debian's
`pg_upgradecluster` tooling from the PGDG apt repo (16 and 18 side by side; the old cluster kept stopped until
released). Every project's own test suite then runs against the WSL 18 cluster — this is where driver versions
(pg-48), the `search_path` change (pg-07) and any removed feature surface, before production.

### D3 — The hub repo changes (one branch, merged only after the hub window passes)

- `.windsurf/rules/versions.yaml:17` → `postgres_major: "18"`; the renderer re-fills the 5 spans.
- `src/fabrik/version_registry.py`: add `postgres_major` to `REQUIRED_KEYS`; `src/fabrik/ci_scaffold.py:33-34`
  derives `postgres:<major>` and `pgvector/pgvector:<pgvector>-pg<major>` from the registry (pg-37/pg-47: pin
  `0.8.6-pg18`, a released build), so the next flip is one registry edit.
- `infra/vps1/postgres/compose.yaml`: image + volume as D1.
- `infra/vps1/monitoring/compose.yaml:178`: `postgres-exporter:v0.15.0` → `v0.20.1`, with `--collector.stat_checkpointer`.
- `tests/test_app_role_real_pg.py:30`, `tests/test_ci_scaffold.py:29-30,42`: follow the registry.
- `scripts/sysadmin/rules_render_versions.py`: teach `_LOOSE` the `postgres:N-alpine` / `pgvector:pgN` image
  shape, so a hard-coded major in a pack is flagged.
- Docs and scripts in the table above → 18 (dated historical records — reviews, research ledgers, DECISIONS rows
  — stay as written).

### D4 — The rule packs (drafted here, handed to infra)

- `core/25-data-postgres.md` § Primary Keys: the "postgres-main … predates it — generate app-side" sentence
  becomes "PG18 ships native `uuidv7()` — `DEFAULT uuidv7()` at schema level is the default for new tables;
  services that also talk to Supabase (17) keep the app-side generator" (pg-41, pg-45). § Generated columns:
  note PG18's VIRTUAL default; write `STORED` explicitly (pg-26).
- The two unmarked literals (`25-data-postgres.md:23`, `30-ops.md:320`) become registry spans or are re-dated as
  history.
- `65-rag-search.md:61`: re-run the dated probe on the PG18 hub and rewrite its observation.
- `CLAIMS.yaml` rows `pg-fleet-major`, `fleet-postgres-main-no-pgvector` and the musl row: re-verify on 18; fix
  the stale `agents-fabrik.md:165` cite (the line is now `:170`).

### D5 — The 45 projects (fabrik-mail requests, one per project that has its own pin)

Eight projects pin an image or CI service; 27 state the major in docs. Each gets one request naming its exact
lines (§ What exists today), the target (`postgres:18.6-alpine` / `pgvector/pgvector:0.8.6-pg18` / the
`postgres:18` CI service), and "run your suite against the WSL 18 cluster before committing". The baseline
copies (`agents-fabrik.md`, `CLAIMS.yaml`) update through the governance sync when D3/D4 merge. Requests go out
after the hub window passes, so no project's CI moves to 18 while its production database is still on 16.

### D6 — trade-intelligence follows its production, not the fleet

Its production database is Supabase's (Postgres 17, pg-45). The parity rule (`30-ops.md:311-321`, dev = prod)
outranks the fleet major: its CI and test images move to `17`, matching Supabase, and to 18 only when Supabase
offers it. Its request says so.

### D7 — brand-identiy-creator's `pg_uuidv7` dependency

Its schema calls `uuid_generate_v7()` from an extension `postgres-main` cannot load. On PG18 the native
`uuidv7()` replaces it; its request asks for a migration from `DEFAULT uuid_generate_v7()` to `DEFAULT uuidv7()`
and dropping the extension, landed before its first deploy (the spec is still `.draft`).

## Compatibility checks (from the PG17 and PG18 migration notes)

Run on the WSL 18 cluster (D2) and again on the hub's restored cluster before services restart:

- **Monitoring breaks first.** `pg_stat_bgwriter.buffers_backend*` moved to `pg_stat_checkpointer` (pg-13),
  `pg_stat_wal` lost `wal_write`/`wal_sync` (pg-28), `pg_stat_io.op_bytes` is gone (pg-27), and
  pg_stat_statements renamed `blk_*_time` (pg-14). postgres-exporter v0.15.0 runs a fixed
  `pg_stat_bgwriter` query that fails on PG17+ (ex-06); v0.17.0 added the PG17 handling (ex-02) and v0.19.0 is
  the first CI-tested against 18 (ex-05). The exporter moves to `v0.20.1` in the same window (ex-01 — its
  `replication_slot` flag rename is applied) with `--collector.stat_checkpointer` on (ex-03); it reads no
  `pg_stat_wal` columns (ex-04). The Grafana Postgres dashboard panels are re-checked against the renamed views.
- **Restore blockers:** no `adminpack` in any database (pg-09); no `old_snapshot_threshold` or
  `db_user_namespace` in the server config (pg-08, pg-10; the compose sets none); primary/foreign keys on
  deterministic collations (pg-25).
- **Behaviour changes:** maintenance commands run with a safe `search_path` — any expression index or matview
  using a non-default schema must set its own (pg-07); VACUUM/ANALYZE now include inheritance children (pg-18);
  AFTER triggers run as the queuing role (pg-21); `interval` literals with a mid-string `ago` fail (pg-11).
- **pg_trgm indexes** are rebuilt after restore (pg-24) — a restore rebuilds every index anyway, so D1 covers it.
- **Roles:** passwords are created with the server default (SCRAM), so the MD5 deprecation (pg-16) does not fire;
  the plan asserts `rolpassword LIKE 'SCRAM%'` for every login role. The two PG16-measured revoke behaviours
  (`postgres.py:1090,1102`) are re-measured on 18 with the existing real-PG test.
- **Drivers:** asyncpg ("9.5 to 18", pg-42), psycopg 3 ("10 to 18", pg-43) and SQLAlchemy 2.0 (pg-44) support
  18; the WSL run measures each project's pinned driver version (pg-48).
- **Client tools:** older `psql` `\copy` may mishandle CSV `\.` against an 18 server (pg-19) — every admin path
  already runs the in-container client (§ What exists today).

## Rejected alternatives

- **B — pg_upgrade (in place, `--link` or `--swap`).** Faster for large clusters and keeps statistics (pg-04),
  but in Docker it needs both majors' binaries in one container (a third-party upgrade image), a checksum-off new
  cluster to match the old one (pg-05), and `--swap`/`--link` consume the old cluster — the one-command rollback
  D1 keeps is lost. The hub cluster is small enough (the plan measures it; the 2026-05-31 snapshot held two app
  databases) that a dump/restore window is minutes, so B's speed buys nothing worth the rollback.
- **C — logical replication blue/green.** Near-zero downtime, but per-database publications, sequence syncing
  and a replica container for a fleet whose services tolerate a short window — rejected as heavier than the
  outage it saves.
- **Stay on 16 until EOL (2028-11).** Recommended in the gate; overruled by D-612.
- **A 17 hop.** pg_dump/pg_restore and pg_upgrade both go 16 → 18 directly (pg-03); a hop doubles the windows.

## Lifecycle

1. Spec → /fabrik-spec-review → operator design approval → /fabrik-plan-after-chat → /fabrik-plan-review.
2. Hub branch changes land and are proven against a scratch PG18 container (no VPS).
3. **WSL window** (operator) — D2, then every project suite against 18.
4. **Hub window** (operator, Gate 2 class: production data) — D1 and the battery; spokes' reconnect checked.
5. Merge the hub branch (infra), render the packs, governance sync; send the D5 project requests.
6. **Release** — after a soak (default 7 days of green backups and battery), the operator releases the old
   `postgres-data` volume and the WSL 16 cluster. Until then both stay untouched.

## External dependencies

`postgres:18.6-alpine` (pg-34), `pgvector/pgvector:0.8.6-pg18` (pg-37, pg-47), the PGDG apt repository for WSL,
`prometheuscommunity/postgres-exporter:v0.20.1` (ex-01, ex-05). No new service, no new secret.

## fabrik-lib verdict

No module needed. The vendored `fastapi_user_auth/schema.sql:3` comment ("PG16 has no native uuidv7()") is
fabrik-lib's to refresh — a mail to fabrik-lib in D5.

## Constraints digest

- Same code in both environments: WSL and the hub move to the same major (`30-ops.md:311-321`).
- `postgres-main:5432` stays the DSN host; nothing in any `.env` changes.
- Every service keeps its memory limit; the PG18 container keeps 2G.
- Destructive operations: dry-run first, the old volume kept, deletion only on the operator's explicit word
  (`CLAUDE.md` § HARD STOPS — volumes are data).
- A hub agent never edits another repo: project changes are requests (D5).
- Pack edits are infra's to render and merge (`CLAUDE.md` § Merge-time render only).

## Shape / infra implications

No spec `shape:` changes. One new external volume (`postgres18-data`) on vps1; the old one retained until release.

## Documentation landing sites

`agents-fabrik.md` (§ Database, § Infra), `README.md`, `docs/infrastructure/vps-complete-inventory.md`,
`docs/operations/disaster-recovery.md` (restore now targets the PG18 volume path), the technology guide,
`docs/reference/prebuilt-app-containers.md`, `docs/traycer/fabrik-workflow.md`, `CHANGELOG.md`, a D-row for the
executed upgrade.

## Cost

Agent time for the plan and the hub branch; two operator windows (WSL ~1 h, hub ~1 h including the battery); no
money.

## Validation

- **V1 — contents:** for every database, the manifest's row counts and role list match after restore; the
  `pg_dumpall` of the new cluster restores cleanly into a scratch container (round-trip).
- **V2 — version:** `SELECT version()` reports 18.6 on the hub and 18.x on WSL; `server_version_num >= 180000`.
- **V3 — services:** every service's `/health` (which runs a real `SELECT 1`) is green; Gatus green for all
  database-backed endpoints; spoke services' health green over the mesh.
- **V4 — roles:** the app-role batch re-applied on a test database passes `tests/test_app_role_real_pg.py`
  against `postgres:18.6`; every login role is SCRAM.
- **V5 — backups:** the first nightly `pg_dumpall` after the window completes with its trailer and the Backrest
  plans snapshot it.
- **V6 — monitoring:** the exporter reports `pg_up 1` with no collector errors.
- **V7 — registry:** `rules_render_versions.py --check` exits 0 with `postgres_major: "18"`; `grep` finds no
  live `postgres:16` pin in the hub outside dated history.

## Decisions taken

- D-612 — the operator's go (verbatim above), one-way, with its Binding block.
- Approach A over B and C (§ Rejected alternatives).
- trade-intelligence follows Supabase's 17 (D6), from the parity rule.

## Open / blocking unknowns

- U1 — the hub cluster's size and exact database list (read live at the window's first step; sizes the window).
- U2 — whether `pre-backup.sh` (not in the repo) needs any change for the new volume path — it runs
  `docker exec postgres-main pg_dumpall`, which is path-independent, but the script is read on the hub in the
  plan.

## Intake Inventory

| I# | Item (anchored) | Disposition | Where |
|---|---|---|---|
| I1 | "it must be done in … wsl" | IN | D2, Lifecycle step 3 |
| I2 | "all vps servers" | IN — one cluster on vps1; the spokes run none (measured), so a reconnect check | D1, What exists today |
| I3 | "all opt projects" | IN — 8 projects with pins, 27 with doc lines, the baseline via sync | D5, D6, D7 |
| I4 | "our rules must be updated in .windsurf/rules" | IN | D3 (registry), D4 (packs) |
| I5 | the stale 2026-05-25 plan | IN — superseded | header |
| I6 | backups stay continuous through the move | IN | D1 step 2, V5 |
| I7 | registrar and watchdog roles keep working | IN | Compatibility § Roles, V4 |
| I8 | extensions in use survive | IN | What exists today, Compatibility |
| I9 | Supabase keeps its own cadence (trade-intelligence) | IN | D6 |
| I10 | `postgres:postgres` superuser hard-coded in `infra/vps1/glitchtip/compose.yaml:7,35` and `infra/vps1/monitoring/compose.yaml:183` (found while grounding) | OUT-OF-SCOPE — a credentials fix, not the upgrade | W-a3dd3cb6 |
| I11 | five specs claim the shared `main` database; four specs set `depends.postgres` with no `shape:` (found while grounding) | OUT-OF-SCOPE — registrar naming hygiene; the upgrade moves whatever databases exist | W-2f54dfd4 |
| I12 | `fabrik_analytics` documented on WSL but also created on the hub (found while grounding) | OUT-OF-SCOPE — a placement question the upgrade does not change | W-b7661cd1 |

Intake: 12 items — 9 IN, 3 OUT-OF-SCOPE (W-a3dd3cb6, W-2f54dfd4, W-b7661cd1), 0 ASK.
