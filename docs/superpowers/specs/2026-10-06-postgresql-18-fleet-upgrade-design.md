# PostgreSQL 16 → 18 — the fleet database upgrade

Status: CONVERGED (/fabrik-spec-review, 2026-10-06 — 5 rounds, closing round confirmed 0; awaiting operator design approval)
Profile: delta — every IN intake item maps to something that runs today (one production cluster, the WSL dev
cluster, the hub's CI generator and test containers, the version registry and the rule packs that read it, the
disaster-recovery chain that names the data volume, and the project pins measured below). The delta changes the
server major and re-points every statement of it; it adds no service and no table.

Work item: W-fd1c7f7a. Operator ruling: D-612 (gate W-498d906a). Research ledger:
`docs/reference/research/2026-10-06-postgresql-18-upgrade-ledger.md` (`check_research_ledger` green). Supersedes
`docs/development/plans/archived/2026-05-25-postgresql-18-upgrade.md` (planned 2026-05-25, never started; it
predates the spoke fleet, the Docker image's PG18 layout change and today's project set).

## Personas

- **The operator** owns the two windows: the WSL window (local; a dev outage only) and the hub window (a
  production outage of every service that uses `postgres-main`). Step budget for the hub window: one deploy and
  write freeze, one dump, one container swap, one restore, one manifest diff, one battery to read. Rollback is one
  compose revert and one `up` — available only until services restart on 18 (D1 step 7).
- **The fleet agent** writes the plan, lands every hub repo change on its branch, proves each locally against a
  scratch PG18 container, and never touches a VPS or a live database outside a window the operator opened.
- **Infra** (merge owner, owner of `.windsurf/rules/` and the command corpus) merges the hub branch and renders
  the rule packs; the pack edits are drafted here and handed over.
- **The project repos** receive their pin and doc edits as fabrik-mail requests (a hub agent never edits another
  repo, `CLAUDE.md` § HARD STOPS); each project's own agent applies and gates them.
- **Every service on `postgres-main`** is stopped for the hub window and restarted against the same DSN: same host
  name, same port, same database names, same roles and passwords.

## Goal

Every PostgreSQL the fleet runs is major 18 — the WSL dev cluster, `postgres-main` on the hub, and every image,
CI service and test container a repo pins — and every rule, claim and live doc that states the major says 18. No
data is lost, every database's contents verify against a manifest taken before the move, the disaster-recovery
chain backs up and restores the new cluster, and the old 16 data stays on disk until the operator releases it.

## Why this exists

The operator ruled it (D-612, verbatim): "yes it must be done in all opt projects, wsl, all vps servers and our
rules must be updated in .windsurf/rules". PG16 is supported until 2028-11-09; PG18 until 2030-11-14 (ledger
pg-02), so this buys two more years before the next forced move. PG18 also ships native `uuidv7()` (pg-41),
which today's rule packs work around app-side (`core/25-data-postgres.md:163`). The registry already anticipates
the flip: `.windsurf/rules/versions.yaml:17` carries `postgres_major: "16"` with the note "flip = fleet DB
upgrade".

## What exists today (grounded)

### The production cluster — one, on the hub

- `infra/vps1/postgres/compose.yaml:3` — `image: postgres:16-alpine`, a floating 16 tag; data on the external
  named volume `postgres-data` mounted at `/var/lib/postgresql/data` (`:8`, `:24-26`); 2G memory limit
  (`:11-14`); `pg_isready` healthcheck (`:15-21`); published only on the mesh, `10.99.0.1:5432` (`:22-23`). No
  init scripts, no `command:` override. `data_checksums` is off on a 16-alpine cluster (measured on a scratch
  container in review).
- **The spokes run no Postgres.** `infra/vps2/` and `infra/vps3/` hold backrest, monitoring-agent and traefik
  only; the one spec that targets a spoke (`specs/services/spoke-canary.yaml:8`, `target_vps: vps2`) has
  `needs_database: false` (`:14`). Spoke services reach the hub over the mesh: `_rewrite_shared_infra_host`
  (`src/fabrik/orchestrator/infrastructure.py:134-152`) rewrites `@postgres-main:` to `10.99.0.1` for any
  `target_vps != vps1`. No other Postgres server exists in the repo (ocoron-com runs MariaDB; Authelia uses
  `redis-main`). "All VPS servers" (D-612) is therefore one cluster plus a reconnect check on the spokes.
- **Databases.** 69 specs in `specs/services/`; 22 with `needs_database: true` name 19 distinct databases
  (registrar naming: `depends.postgres` if set, else the spec id with `-`→`_`,
  `src/fabrik/orchestrator/infrastructure.py:744-749`), plus `glitchtip` (`infra/vps1/glitchtip/compose.yaml:7`),
  `fabrik_analytics` (created on every apply, `infrastructure.py:690-715`) and the system `postgres` database.
  The authoritative list lives on the hub at `/opt/monitoring/configs/postgres/allocations.json`
  (`src/fabrik/drivers/postgres.py:72`), not in the repo — the hub window's first step reads `\l` live (U1).
- **Extensions in use:** `plpgsql` everywhere; `pg_trgm` installed in one database (probe 2026-09-22,
  `.windsurf/rules/core/65-rag-search.md:61`); `vector` is not available on the image. Nothing on the hub uses
  pg_cron or PostGIS (both REJECTED in the ledger, pg-39/pg-40).
- **All SQL and dumps run inside the container.** `_run_sql` pipes into `docker exec -i postgres-main psql`
  (`src/fabrik/drivers/postgres.py:111-137`); the nightly `pg_dumpall` in `/opt/backups/pre-backup.sh` (host cron
  `30 1 * * *`, `scripts/bootstrap/bootstrap-hub.sh:89`) and the per-database `pg_dump -Fc` loop
  (`docs/operations/deployment.md:538`) are `docker exec postgres-main …` — the client always matches the
  server. `pre-backup.sh` itself is not in the repo (U2).
- **The disaster-recovery chain names the volume.** `scripts/bootstrap/bootstrap-config.sh:201`
  (`FABRIK_HUB_VOLUMES_TO_RESTORE=( postgres-data …)`), `scripts/bootstrap/bootstrap-hub.sh:78,83,1170,1315-1334`
  (step 12 volume restore, step 12c core boot, step 14 dump fallback), `src/fabrik/orchestrator/vultr_drill.py:310`,
  `docs/operations/hub-restore-inventory.md:97,186,193`, `docs/operations/disaster-recovery.md:74,266`, and the
  Backrest `docker-volumes` plan on the hub (an explicit volume list in its `config.json`, not in the repo;
  Backrest mounts `/var/lib/docker/volumes:ro`, `infra/vps1/backrest/compose.yaml:25`).
- **Clients of `postgres-main` beyond the service containers:** the WSL postgres-MCP tunnel `localhost:15432` →
  `10.99.0.1:5432` (`scripts/wsl_startup_hook.sh:226`); any agent's `fabrik apply` (creates databases and roles
  through `docker exec`, `postgres.py:111-137`); `scripts/provision_watchdog_ro.py:96`; the watchdog's
  `fabrik_analytics` writes (`src/fabrik/drivers/watchdog.py:558`); the 01:30 backup cron; glitchtip and the
  postgres-exporter, which log in as the superuser (`infra/vps1/glitchtip/compose.yaml:7`,
  `infra/vps1/monitoring/compose.yaml:183`).
- **Version-sensitive role code.** The app-role grant batch uses `GRANT … WITH INHERIT FALSE, SET TRUE` and
  reads `pg_auth_members.inherit_option/set_option` (`src/fabrik/drivers/postgres.py:1174`, `:1244`) — PG16+, so
  valid on 18. Two behaviours were *measured on PG16* (`:1090`, `:1102`) — re-measured on 18 in the plan.
- **Monitoring.** `prometheuscommunity/postgres-exporter:v0.15.0` (`infra/vps1/monitoring/compose.yaml:178`)
  runs a fixed `pg_stat_bgwriter` query that fails on PG17+ (ex-06) — see § Compatibility.

### The WSL dev cluster

Native apt PostgreSQL 16 at `localhost:5432`, one `{project}_dev` database per project
(`.windsurf/rules/core/25-data-postgres.md:34-39`, `scripts/create_pg_dev_db.sh:17-30`); the parity rule
requires the same major as `postgres-main` (`.windsurf/rules/core/30-ops.md:311-321`). Measured in review on this
box: `pg_lsclusters` → `16 main 5432 online`; packages from the Ubuntu archive, not PGDG (`postgresql-16
16.15-0ubuntu0.24.04.1`, `postgresql-common 257build1.1`); `postgresql-16-pgvector 0.6.0-1` installed (WSL has
`vector`, production does not — a pre-existing parity gap); and `pg_uuidv7` hand-installed for 16 only
(`/usr/lib/postgresql/16/lib/pg_uuidv7.so`, no package). It also hosts `fabrik_analytics`
(`docs/superpowers/specs/2026-07-26-catalog-extraction-design.md:144`) and session-recall's database
(`specs/services/session-recall.yaml:14`).

### The hub's own pins

Scope of the count: `src/fabrik` (83 files), `templates/` (335), `.windsurf/rules/` (59), `docs/` excluding
`docs/archive` and `docs/development/plans/archived` (1,035 — the reviews are inside this number), `tests/` (502), `infra/` (33) — 2,047 files — plus targeted greps of `scripts/`,
`specs/` and the root markdown.

| What | Where | Today |
|---|---|---|
| version registry | `.windsurf/rules/versions.yaml:17` | `postgres_major: "16"`; no pgvector key |
| rule-pack spans the renderer fills | `core/25-data-postgres.md:36,163`, `core/65-rag-search.md:61` (×2) | 4 spans of `<!--v:postgres_major-->` |
| rule-pack literals the renderer cannot see | `core/25-data-postgres.md:23`, `core/30-ops.md:320` | `postgres:16-alpine` in dated probes |
| claims rows | `.windsurf/rules/CLAIMS.yaml` `pg-fleet-major` (its `verify:` greps `'PostgreSQL 16'`), `pgvector-not-installed`, `fleet-postgres-main-no-pgvector` | state major 16 |
| CI generator for scaffolded projects | `src/fabrik/ci_scaffold.py:33-34` | `postgres:16`, `pgvector/pgvector:pg16` (bypasses the registry) |
| production image | `infra/vps1/postgres/compose.yaml:3` | `postgres:16-alpine` (bypasses the registry) |
| real-PG test container | `tests/test_app_role_real_pg.py:30` (also used by `tests/test_payments_ingest_real_pg.py:19`) | `postgres:16` |
| tests pinning the CI images | `tests/test_ci_scaffold.py:29-30,42` | assert `pg16` / `postgres:16` |
| live docs stating the major | 29 files (`rg -il` over `agents-fabrik.md`, `README.md`, `docs/` excluding archives and reviews), among them `agents-fabrik.md:170,186,188`, `README.md:859`, `docs/infrastructure/vps-complete-inventory.md:120,168`, `docs/operations/disaster-recovery.md:74`, `docs/reference/technology-stack-decision-guide.md:21,518`, `docs/reference/prebuilt-app-containers.md:87`, `docs/traycer/fabrik-workflow.md:412`, `docs/workstation/session-recall.md:3,15`, `docs/STRATEGIC_BACKLOG.md:131` (this upgrade's backlog row) | "PostgreSQL 16" |
| scripts | `scripts/generate_vps_inventory.py:72`, `scripts/container_images.py:565` | 16 |

The renderer (`scripts/sysadmin/rules_render_versions.py`, `_SPAN` at `:34`, `--check` at `:86`) rewrites spans
only; its loose-literal warning (`_LOOSE`, `:36-50`) already flags `pgvector:pgN` (`:49`) but has no
`postgres:N-alpine` or `pgvector:X.Y.Z-pgN` shape. `version_registry.py:26` (`REQUIRED_KEYS`) omits
`postgres_major`, so no code reads it.

### The project pins

Scope: the 45 directories `/opt/<name>` that carry a `.git` or a compose file — the hub itself plus 44 projects
(39 with a compose file, obsidian-agents' nested one included; 5 repo-only: fabrik-dr-store, fabrik-lib,
fabrik-lib-account, fabrik-lib-review, meb) — every `<project>/.claude/worktrees/**` copy excluded; counted with `rg --no-ignore --hidden`. Every pin and every
current doc states **16**; nothing is on 17 or 18; no `postgres:latest`.

- **Images and CI services:** fabrik (above); tryton-crm `compose.dev.yaml:71` (`postgres:16-bookworm`, data
  mounted at `/var/lib/postgresql/data`, `:93`), plus `.env.example:49` and `trytond.conf:4`; tojlo-mail
  `docker/docker-compose.local.yml:38` (mount at `:44`) and two test notes; trade-intelligence
  `.github/workflows/ci.yml:25`, `scripts/verify_fresh_bootstrap.py:58`, `scripts/run_db_suite_clean.sh:32`,
  `tests/db/test_roles_sql_attributes.py:95`, `.env.example:29`, `web/playwright.r21-write.config.ts:13`;
  gmail-account-creator and fabrik-claim-validator (`.github/workflows/ci.yml:12` — generated: its line 1 says
  "fabrik-managed — regenerate via fabrik scaffold" — and `scripts/ci_local.sh:8`); youtube
  `.github/workflows/test.yml:15`. site-provisioner's `tests/test_glitchtip_init.py:2338` is a fixture string,
  not a pin.
- **Client tooling:** calendar-orchestration-engine `Dockerfile.scheduler:12` installs an unpinned
  `postgresql-client` on a Debian base; youtube and the hub spec mention `apt install postgresql-16-pgvector`;
  trade-intelligence and session-recall assert `pg_dump >= 16.x`; four committed `schema.sql` files carry
  "Dumped by pg_dump version 16.x" headers.
- **fabrik-lib** (and its -account and -review copies): `fastapi-user-auth/README.md:791` (`postgres:16`) and the
  vendored `fastapi_user_auth/schema.sql:3` comment ("PG16 has no native uuidv7()").
- **Docs:** ~70 lines across 27 projects, plus the synced baseline every project carries (`agents-fabrik.md`,
  `CLAIMS.yaml`, the rule packs, `final_gate.py` and `check_docker.py` comments), which the governance sync
  refreshes from the hub.
- **UUIDs:** 0 projects call native `uuidv7()`; 17 use `uuid_utils` app-side; **brand-identiy-creator** calls
  `uuid_generate_v7()` from the `pg_uuidv7` extension in 24 files (`grep -rl` over py, sql and md; the D7 request
  re-measures) — model `server_default`s
  (e.g. `src/brand_identity/models/tenant.py:27`), raw INSERTs (`services/checkpoints.py:137,219`), migrations
  0001 (`CREATE EXTENSION "pg_uuidv7"`, `migrations/versions/0001_initial_schema.py:20`) /0008/0010/0018, tests —
  an extension `postgres-main` does not offer (a pre-existing deploy blocker, D7).
- **trade-intelligence has left Supabase.** "All services connect to a self-hosted PostgreSQL (`postgres-main:5432`
  …; a local Postgres in WSL dev) … Supabase has been dropped as a runtime target" (`/opt/trade-intelligence/README.md:165`);
  its hub spec stays `.draft` only "until the project's DATABASE_URL is repointed to postgres-main"
  (`specs/services/trade-intelligence.yaml.draft:1-3`).

## The delta — chosen approach (A: dump and restore into a fresh PG18 volume)

### D1 — The hub cluster: dump/restore into a new volume, the old one kept

The window runs clear of 01:30–03:30 (the backup cron and the Backrest snapshots it feeds,
`docs/operations/disaster-recovery.md:43`), or the cron is commented out for its duration.

**Disk gate, before the window.** The hub (108 GB, `docs/infrastructure/vps-complete-inventory.md:108`) holds
the old volume, the new one, the `pg_dumpall` file, the per-database dumps and the nightly dumps at once through
the soak. Measure `sum(pg_database_size(datname))` and `df` on `/var/lib/docker` and `/opt`; the window opens only
with free space of at least four times the cluster size plus 10 GB. The second copy of every dump (step 3) goes
OFF the host — into the Backrest B2 repository `b2-vps1` (`docs/operations/disaster-recovery.md:28`), never the same disk.

1. **Freeze deploys and writes.** Announce a deploy freeze (no `fabrik apply`), stop the WSL MCP tunnel,
   `systemctl disable --now` the `fabrik-compose-boot` unit for the window (it runs `docker compose up -d` for
   every `/opt/*/compose.yaml` on boot, `scripts/bootstrap/bootstrap-hub.sh:1409-1410`, so a reboot mid-window
   would restart everything), stop every `*-watchdog` sidecar FIRST (a sidecar restarts its main container when it
   exits, `docs/infrastructure/vps-complete-inventory.md:742`, and logs in itself as `watchdog`), then stop
   every service container that uses `postgres-main` (the plan derives the list from the spec inventory and the
   hub's `docker ps`, spokes included; glitchtip and the postgres-exporter log in as the superuser, so stopping
   their containers is the only thing that keeps them out) and assert with a `docker ps` filter that none came
   back, then enforce the freeze in the database: first
   record every database's `datname, datconnlimit` (the pre-freeze limits), then `ALTER DATABASE … CONNECTION
   LIMIT 0` for every non-system database, terminate any remaining client backend,
   and assert `SELECT count(*) FROM pg_stat_activity WHERE backend_type = 'client backend' AND pid <>
   pg_backend_pid()` is 0. Never `ALLOW_CONNECTIONS false`: `pg_dumpall` silently leaves such a database out of
   the dump (exit 0) and `pg_dump` and the manifest cannot connect to it (measured in review); a connection
   limit still dumps and still admits the superuser. Because every host-side admin path is a superuser
   (`_run_sql` is `docker exec … psql -U postgres`, `src/fabrik/drivers/postgres.py:136`), the freeze is closed in
   the database too: `ALTER SYSTEM SET default_transaction_read_only = on` and `SELECT pg_reload_conf()`, which
   binds superusers; the operator's own session runs `SET default_transaction_read_only = off` for the freeze
   statements, and `pg_dumpall` reads only (its script also sets the parameter off for the restore session).
2. **Take the manifest** on the 16 cluster: exact `count(*)` of every table in every database; every sequence's
   `last_value`/`is_called`; `pg_extension` names and versions; `pg_database` encoding, collation, ctype, locale
   provider and owner (PG17 renamed `daticulocale` to `datlocale`, pg-15 — the manifest query names each side's
   column); `pg_roles` attributes and `rolpassword` prefix; `pg_auth_members` rows; `pg_default_acl`;
   table and schema ACLs; a per-table content hash (`md5(string_agg(t::text, E'\n' ORDER BY <primary key>))`, or
   every column where there is no key), because D-612's TRIPWIRE is row counts OR checksums; and the server
   configuration a dump does not carry — `pg_settings` rows whose `source` is not `default`, `override`,
   `client` or `session` (with `sourcefile`), `pg_hba_file_rules`, `pg_ident_file_mappings`, and copies of
   `postgresql.auto.conf`, `pg_hba.conf` and `pg_ident.conf` (an
   `ALTER SYSTEM` such as a raised `max_connections` is absent from `pg_dumpall` and silently reverts to the
   image default, measured in review).
3. **Dump with the PG18 client** (pg-06), authenticating as the live superuser:
   `docker run --rm --network fabrik -e PGPASSWORD="$PGPW" postgres:18.6-alpine pg_dumpall -h postgres-main -U
   postgres > /opt/backups/pg16-final-<ts>.sql` (the official image trusts only local socket connections, so a
   TCP client without a password fails — measured), plus a per-database `pg_dump -Fc` with the same client for a
   granular restore. `$PGPW` is the superuser's live password; the plan proves it with a test connection before
   the window. A copy of every dump also goes off the host (the disk gate above), out of reach of any retention
   in `pre-backup.sh`. Then re-run the step-2 manifest on 16 and require it to equal step 2's, so the dump is
   bracketed by two identical readings. Trigger a manual Backrest `postgres-dumps` snapshot and confirm the dump
   files are in it, so their off-host copy exists before anything is swapped (the nightly run is outside the
   window). Stop the 16 container (`docker stop postgres-main`) the moment that check
   passes: `CONNECTION LIMIT 0` still admits the
   superuser (`docker exec postgres-main psql`), so no write may land between the dump and the swap.
4. **Swap the container**: `docker volume create postgres18-data` first (the compose declares its volume
   `external: true`, `infra/vps1/postgres/compose.yaml:24-26`, so `up` fails without it); compose image →
   `postgres:18.6-alpine` (pg-34), volume → the NEW external volume
   `postgres18-data` mounted at `/var/lib/postgresql` (the PG18 image's VOLUME; PGDATA
   `/var/lib/postgresql/18/docker`, pg-35 — confirmed by `docker image inspect` in review). The old
   `postgres-data` volume is untouched. The PG18 image refuses to start on any volume at
   `/var/lib/postgresql/data` (pg-36, reproduced in review), so a bare image bump is never an option. The hub's
   `/opt/postgres/compose.yaml` is edited by hand for the window; no sync or `fabrik apply` touches it until D3
   merges.
5. **Restore** into the empty PG18 cluster (initdb with checksums on, the PG18 default, pg-05):
   `docker exec -i postgres-main psql -U postgres -X -f - < pg16-final-<ts>.sql`, without `ON_ERROR_STOP`,
   stderr captured. Exactly one error is expected and allowed — `role "postgres" already exists`; any other error
   fails the window. The dump carries step 1's `CONNECTION LIMIT 0`, which stays in force on 18 until step 8, so
   nothing but the superuser can write before the cut-off. Port every non-default server setting and
   `pg_hba`/`pg_ident` rule from the manifest (`ALTER SYSTEM` on 18, then a reload) — except step 1's own
   `default_transaction_read_only`, and except any parameter PG17 removed (pg-08, pg-10), and with PG18's renamed `ssl_groups` for `ssl_ecdh_curve` (pg-30) — and check
   `max_connections` against the sum of the services' pool sizes; then `ANALYZE`. The superuser keeps its old password (the dump's `ALTER ROLE postgres … PASSWORD`
   overrides the new container's `POSTGRES_PASSWORD`).
6. **Diff the manifest** on 18 (V1). ACLs are compared after normalising PG17's new `m` (MAINTAIN) privilege,
   which every owner's ACL gains on restore; `datconnlimit` is still the frozen 0 on both sides; server settings
   and `pg_hba` rules are compared after step 5's port, except step 1's own `default_transaction_read_only`,
   which is expected on 16 and absent on 18.
6a. **glitchtip first.** glitchtip (`glitchtip/glitchtip:latest`, Django and Celery,
   `infra/vps1/glitchtip/compose.yaml:3,7`) is the one application with no WSL rehearsal. Pin its image digest
   for the window, start glitchtip-web alone against 18, and check `/health` and `manage.py migrate --check`.
   If it wrote, re-restore the `glitchtip` database before step 7: stop glitchtip-web, `DROP DATABASE glitchtip WITH (FORCE)`, then
   `pg_restore --create -d postgres` from its per-database `-Fc` dump; while nothing else is up this costs
   minutes.
7. **The rollback cut-off.** Until services restart, rollback is one step: revert the compose image and mount to
   `postgres-data`, `up`, `ALTER SYSTEM RESET default_transaction_read_only` and reload, and restore step 1's
   pre-freeze limits on the 16 cluster — nothing was written to 18. Once services restart, rollback means a `pg_dumpall` from
   18 restored into 16, with hand edits where the dump uses 18-only syntax, and the writes since restart are
   carried manually; the plan treats the restart as the point of no return and requires V1 green before it.
8. **Restart.** Reset each database the manifest lists as non-system to its recorded pre-freeze limit (`-1` unless
   step 1 recorded another value; never `template0`, which keeps `datallowconn = false`), merge the D3 DR-chain
   hunk (below), start the services, then the watchdog sidecars, re-enable `fabrik-compose-boot`, lift the deploy
   freeze, and run the battery (V2–V6). Before the window closes, add `postgres18-data` to the Backrest
   `docker-volumes` plan (keep `postgres-data` until release), restart Backrest, trigger a manual snapshot and
   confirm it holds `postgres18-data/_data/18/docker/PG_VERSION` — production never runs a night without a
   volume snapshot.

### D2 — WSL first, as the rehearsal

0. Before anything is installed, list `datname, extname, extversion` from `pg_extension` in every
   `datallowconn` database. A `pg_uuidv7` row outside brand-identiy-creator's database is a KILL until handled
   (`pg_upgradecluster` fails on any database that has it); the `vector` rows name the databases
   `postgresql-18-pgvector` must serve.
1. Add the PGDG apt repository and install `postgresql-18` and `postgresql-18-pgvector`. PGDG's
   `postgresql-common` replaces Ubuntu's, and PGDG's `16.15-1.pgdg24.04+1` sorts newer than the installed
   `16.15-0ubuntu0.24.04.1` (`dpkg --compare-versions`, measured). The step names all four packages —
   `apt install postgresql-18 postgresql-18-pgvector postgresql-16 postgresql-16-pgvector` — so the 16 pair
   (pgvector 0.6.0 → 0.8.x) moves to PGDG's build in the same step, and the running 16 cluster restarts once (a
   short dev outage).
2. The install auto-creates an `18/main` cluster on 5433; drop it (`pg_dropcluster 18 main --stop`), because
   `pg_upgradecluster` refuses while it exists.
2a. brand-identiy-creator's dev database has the hand-built `pg_uuidv7` extension, which has no build for 18 on
   this box and would fail the upgrade: take `pg_dump --data-only --exclude-table=alembic_version
   --exclude-table=worker_pool_state` of it (the two tables the migrations themselves populate — migration
   0005 seeds `worker_pool_state` id 1 — so a reload never collides with them) to a dated file outside the repo,
   then drop it. It is recreated on 18 in step 4 from its rewritten migrations (D7), and the dump reloads its rows if
   they turn out not to be regenerable.
3. Stop the local writers first — the session-recall service and any local watchdog or cost-ledger writer to
   `fabrik_analytics` — and assert no client backend is connected, as D1 step 1 does. Then
   `pg_upgradecluster 16 main` — its default method is dump/restore. On failure it drops the new cluster and
   restarts 16 itself (`--keep-on-error` keeps the new one for diagnosis); fix the cause and run it again. Afterwards 18 owns port 5432 (every
   `{project}_dev` DSN keeps working) and 16 moves to 5433 with `start.conf` set to manual, kept until release.
4. Verify every database, `fabrik_analytics` and session-recall's included, with the D1 manifest method; then run
   every project's suite against 18. This is where driver versions (pg-48), the `search_path` change (pg-07)
   and removed features surface. brand-identiy-creator's database, dropped in step 2a, is recreated here on 18
   from its rewritten migrations (D7), and step 2a's dump is reloaded if needed.
5. **KILL** (D-612): a WSL verification that fails stops the hub window until fixed.
6. **Parity gap, bounded:** between the windows WSL runs 18 and production 16. The hub window follows within 7
   days of the WSL window; past that, WSL rolls back until a hub window is scheduled: stop both clusters
   (`pg_ctlcluster`), set `port` in each `postgresql.conf` (16 back to 5432, 18 to 5433), set 16's `start.conf`
   to auto and leave 18's on auto, then start both (`pg_ctlcluster 16 main start`, `pg_ctlcluster 18 main
   start`). 18 stays running at 5433 for brand-identiy-creator alone: its D7 code calls native `uuidv7()`, absent
   on 16, so that project's dev DSN is repointed to port 5433 until the hub window. Every other project's DSN
   reaches 16 at 5432; their dev writes made on 18 in the gap are lost (dev data).

### D3 — The hub repo changes (one branch, merged only after the hub window passes — except its DR-chain hunk)

The DR-chain hunk (`scripts/bootstrap/bootstrap-config.sh:201`, the `bootstrap-hub.sh` comments,
`src/fabrik/orchestrator/vultr_drill.py:310`) merges inside the hub window at D1 step 8, after V1 is green.
Otherwise Backrest restores the hand-edited `/opt/postgres/compose.yaml` that names `postgres18-data` while the
repo's DR volume list still restores `postgres-data`, and a DR in that gap cannot boot postgres-main.

- `.windsurf/rules/versions.yaml`: `postgres_major: "18"` and a new `pgvector_version: "0.8.6"` key (pg-37,
  pg-47: a released build, never the floating `pg18`); rewrite the `:17` comment. The renderer re-fills the 4
  spans.
- `src/fabrik/ci_scaffold.py:33-34`: derive `postgres:<major>` and `pgvector/pgvector:<pgvector_version>-pg<major>`
  from the registry, lazily inside `pg_image()` — never at import, because `scripts/backfill_ci.py:31` and
  `scaffold.py:1142` import the module and must not fail on a registry problem. `ci_scaffold` validates its own
  two keys; `version_registry.py`'s `REQUIRED_KEYS` is left alone (adding `postgres_major` there gates every
  `load_versions()` caller, the docusaurus scaffold and the template renderer included, and turned 9 existing
  tests red when tried in review).
- `infra/vps1/postgres/compose.yaml`: image + volume as D1.
- `infra/vps1/monitoring/compose.yaml:178`: `postgres-exporter:v0.15.0` → `v0.20.1`, with
  `--collector.stat_checkpointer` (ex-01, ex-03).
- The disaster-recovery chain: `scripts/bootstrap/bootstrap-config.sh:201` (`postgres-data` → `postgres18-data`),
  `scripts/bootstrap/bootstrap-hub.sh` steps 12/12c/14 and their comments (`:78,83,1170,1315-1334`),
  `src/fabrik/orchestrator/vultr_drill.py:310`, `docs/operations/hub-restore-inventory.md:97,186,193`,
  `docs/operations/disaster-recovery.md:74,266`. The Backrest `docker-volumes` plan's volume list on the hub
  gains `postgres18-data` — D1 step 8, proven by a manual snapshot before the window closes.
- `tests/test_app_role_real_pg.py:30` and `tests/test_ci_scaffold.py:29-30,42` follow the registry; the real-PG
  test uses `postgres:18.6-alpine`, matching production.
- `scripts/sysadmin/rules_render_versions.py`: add the `postgres:N(.N)?-alpine` and `pgvector:X.Y.Z-pgN` shapes to
  `_LOOSE` (the `pgvector:pgN` shape already exists).
- The 29 live docs and the two scripts in the table → 18; `docs/STRATEGIC_BACKLOG.md:131` closes with a pointer to
  this spec. Frozen artifacts stay as written: reviews, research ledgers, DECISIONS rows, LESSONS_LEARNT entries,
  and executed or archived plans.

### D4 — The rule packs (drafted here, handed to infra)

- `core/25-data-postgres.md` § Primary Keys: the "postgres-main … predates it — generate app-side" sentence
  becomes: "postgres-main runs 18, which ships native `uuidv7()` (pg-41). App-side generation (`uuid_utils`)
  stays the scaffold default; `DEFAULT uuidv7()` at schema level is permitted for new tables once the project's CI
  and dev run 18." The scaffold's
  emitted schema (`src/fabrik/scaffold.py:2221,2230`) and `templates/scaffold/docs/data-contract-template.md:17`
  keep app-side generation, so pack and scaffold agree and no project's CI is asked to support a default its 16
  CI image lacks. § Generated columns: note PG18's VIRTUAL default; write `STORED` explicitly (pg-26).
- The two unmarked literals (`25-data-postgres.md:23`, `30-ops.md:320`) are re-dated as history, the registry
  spans carrying the current major.
- `65-rag-search.md:61`: re-run the dated probe on the PG18 hub and rewrite its observation, including the
  sentence calling the span-rendered image "the same image the CI scaffold already uses" (after D3 the scaffold
  pins `0.8.6-pg18`).
- `CLAIMS.yaml` row `pg-fleet-major` is rewritten, because its tripwire demands the opposite of the decision above
  ("DEFAULT uuidv7() becomes the fleet default"). New claim: "postgres-main runs major 18 (agents-fabrik.md:170;
  EOL 2030-11), which ships native uuidv7(); app-side generation stays the scaffold default and DEFAULT uuidv7() is
  permitted once a project's CI and dev run 18. TRIPWIRE: when every project CI image runs >=18, revisit making
  DEFAULT uuidv7() the scaffold default." New `verify:` grep: `'PostgreSQL 18'` in `agents-fabrik.md`. Rows
  `pgvector-not-installed` and `fleet-postgres-main-no-pgvector`: re-verify on 18.

### D5 — The projects (fabrik-mail requests)

Each request names its exact lines from § What exists today and asks the project to run its suite against the
WSL 18 cluster before committing. Requests go out after the hub window passes: a project CI on 16 while
production runs 18 fails closed (an 18-only construct reds CI and never deploys), whereas a CI on 18 against a 16
production fails open.

- **brand-identiy-creator** — the exception: its request goes out BEFORE the WSL window, its change prepared
  against a scratch 18 container and merged and applied after it (D7).
- **tryton-crm, tojlo-mail** — image to `postgres:18.6-*` AND the mount to `/var/lib/postgresql` (an image-only
  bump fails to start, pg-36), with a local dump/restore of their dev data.
- **trade-intelligence** — its six pins to 18 (D6).
- **gmail-account-creator, fabrik-claim-validator** — regenerate the CI via `scripts/backfill_ci.py` / the scaffold
  after D3 merges (the files are generated), plus `scripts/ci_local.sh:8`.
- **youtube** — CI service to `postgres:18`; docs' `postgresql-16-pgvector` → 18.
- **calendar-orchestration-engine** — pin `postgresql-client-18` in `Dockerfile.scheduler:12`: its
  `node:22-bookworm-slim` base defaults to client 15, and that line installs `curl` but not
  `ca-certificates`/`gnupg`, so the request adds those two, then the PGDG keyring and source, then the package (PGDG offers `18.6-1.pgdg12+2` for bookworm, measured
  in review).
- **fabrik-lib** — README `postgres:16` and the vendored `schema.sql:3` comment; its copies flow to -account,
  -review and the projects that vendor `fastapi_user_auth`.
- **The 27 doc-only projects** — one line each in a single broadcast naming their files.
- The synced baseline (`agents-fabrik.md`, `CLAIMS.yaml`, packs, gate comments) updates through the governance
  sync when D3/D4 merge.

### D6 — trade-intelligence follows the fleet

It has left Supabase for `postgres-main` (§ What exists today), and its dev database is the shared WSL cluster
(`README.md:204`). Its CI, scripts and tests move to 18 with everyone else; its cutover to `postgres-main` lands on
an 18 cluster. No project stays on 17.

### D7 — brand-identiy-creator's `pg_uuidv7` dependency: prepared before the WSL window, merged and applied after

`uuid_generate_v7()` (extension) and native `uuidv7()` both return `uuid` (pg-41), but a SQL function body is
checked at creation and `uuidv7()` exists only on 18, so the change cannot be applied on a 16 cluster (measured in
review: `ERROR: function uuidv7() does not exist`). The request asks for code that targets 18 only: every call
moved to native `uuidv7()` (or a shim `CREATE OR REPLACE FUNCTION uuid_generate_v7() RETURNS uuid LANGUAGE sql
VOLATILE AS 'SELECT uuidv7()'`, created on 18 where the extension is absent); migration 0001 rewritten so it no
longer creates `pg_uuidv7`; the model defaults, raw SQL and tests updated; `db/schema.sql:3,14` and
`README.md:117`. The project prepares it on a branch before the WSL window and gates it against a scratch
`postgres:18.6-alpine` container, which has no `pg_uuidv7` (the target condition). It merges after the WSL
upgrade, when its suite can run against the WSL 18 cluster as every request requires: the dev database is
dropped before `pg_upgradecluster` (D2 step 2a) and recreated on 18 from the rewritten migrations (D2 step 4). Its production deploy, still
`.draft`, happens only on the 18 hub.

## Compatibility checks (from the PG17 and PG18 migration notes)

Run on the WSL 18 cluster (D2) and on the hub's restored cluster before services restart:

- **Monitoring breaks first.** PG17 removed `buffers_backend` and `buffers_backend_fsync` from `pg_stat_bgwriter`
  as redundant to `pg_stat_io`, and moved the checkpoint columns to the new `pg_stat_checkpointer` (or-01);
  renamed `pg_stat_progress_vacuum` (or-02) and `pg_stat_slru` (or-03) columns and the pg_stat_statements
  `blk_*_time` columns (pg-14). PG18 removed `pg_stat_io.op_bytes` (pg-27) and `pg_stat_wal`'s write/sync columns
  (pg-28). postgres-exporter v0.15.0's fixed `pg_stat_bgwriter` query fails on 17+ (ex-06); v0.17.0 added the
  PG17 handling (ex-02), v0.19.0 is the first CI-tested on 18 (ex-05), and it reads no `pg_stat_wal` columns
  (ex-04). The exporter moves to `v0.20.1` (ex-01, its `replication_slot` flag rename applied) with
  `--collector.stat_checkpointer` (ex-03). Any dashboard panel or alert on `buffers_backend` moves to `pg_stat_io`;
  whether v0.20.1 exposes a `pg_stat_io` collector is checked in the plan.
- **Restore blockers:** no `adminpack` in any database (pg-09); no `old_snapshot_threshold` or
  `db_user_namespace` in the server config (pg-08, pg-10; the compose sets none); primary/foreign keys on
  deterministic collations (pg-25).
- **Smaller changes, checked once on WSL:** `SET SESSION AUTHORIZATION` checks superuser status at command time
  (pg-12); time-zone abbreviations resolve against the session zone first (pg-17); unlogged partitioned tables are
  disallowed (pg-20); rule privileges are gone from GRANT/REVOKE (pg-22); `pg_backend_memory_contexts` changed
  (pg-23); `EXPLAIN ANALYZE` shows BUFFERS by default (pg-29); `ssl_ecdh_curve` is now `ssl_groups` (pg-30);
  CREATE SUBSCRIPTION streams in parallel by default (pg-31); `io_method` defaults to `worker` and the I/O
  concurrency defaults rise to 16 (pg-32, defaults kept); nothing changes the `public` schema between 16 and 18
  (pg-33); pg_trgm and uuid-ossp ship in PG18's contrib (pg-38); 18.6 is the target minor (pg-01).
- **Behaviour changes:** maintenance commands run with a safe `search_path` — an expression index or matview
  using a non-default schema must set its own (pg-07); VACUUM/ANALYZE include inheritance children (pg-18); AFTER
  triggers run as the queuing role (pg-21); `interval` literals with a mid-string `ago` fail (pg-11); default
  statistics targets read as NULL (or-04); a few removed columns and settings (or-05) and the WAL file-name
  boundary change (or-06) matter only to tooling that reads them.
- **pg_trgm indexes** are rebuilt by the restore (pg-24) and checked valid.
- **Roles:** passwords are SCRAM (the server default), so the MD5 deprecation (pg-16) does not fire. A review
  rehearsal (16-alpine → 18.6-alpine) showed SCRAM hashes, ownership, `INHERIT FALSE` memberships (re-emitted as
  `WITH INHERIT FALSE GRANTED BY postgres`, SET TRUE being the default), non-superuser grantor chains, default
  ACLs, sequences, extensions, encodings and pg_trgm indexes all surviving. The two PG16-measured revoke behaviours
  (`postgres.py:1090,1102`) are re-measured on 18 with the real-PG test.
- **Drivers:** asyncpg ("9.5 to 18", pg-42), psycopg 3 ("10 to 18", pg-43) and SQLAlchemy 2.0 (pg-44) support
  18; the WSL run measures each project's pinned driver version (pg-48).
- **Client tools:** older `psql` `\copy` may mishandle CSV `\.` against an 18 server (pg-19) — every hub admin path
  runs the in-container client; calendar's unpinned client is pinned (D5).

## Rejected alternatives

- **B — pg_upgrade.** Keeps statistics (pg-04), and its default `--copy`/`--clone` modes leave the old cluster
  intact, so rollback survives. Rejected for the image and the checksums: in Docker it needs both majors'
  binaries in one container (a third-party upgrade image), and the 16 cluster has checksums off (measured) while
  PG18's initdb turns them on (pg-05), so B would initdb the new cluster with `--no-data-checksums` and keep a
  checksum-less cluster. A dump/restore gets checksums for free; the window length B would save depends on the
  cluster's size (U1).
- **C — logical replication blue/green.** Near-zero downtime, but per-database publications, sequence syncing and
  a replica container for a fleet whose services tolerate a short window — heavier than the outage it saves.
- **Stay on 16 until EOL (2028-11).** Recommended in the gate; overruled by D-612.
- **A 17 hop.** Both dump/restore and pg_upgrade go 16 → 18 directly (pg-03); a hop doubles the windows.
- **trade-intelligence on 17.** Drafted on the premise that its production was Supabase's 17; its own docs show
  it has left Supabase (D6).

## Lifecycle

1. Spec → /fabrik-spec-review → operator design approval → /fabrik-plan-after-chat → /fabrik-plan-review.
2. Hub branch changes land and are proven against a scratch PG18 container (no VPS). The D7 request goes out.
3. **WSL window** (operator) — D2, then every project suite against 18. KILL on a failed verification.
4. **Hub window** (operator, Gate 2 class: production data), within 7 days of step 3 — D1, the battery, the
   Backrest plan step; spokes' reconnect checked. Infra (the merge owner) is on call for the window and merges
   the D3 DR-chain hunk at D1 step 8.
5. Merge the rest of the hub branch (infra), render the packs, governance sync; send the D5 project requests.
6. **Release** — after a soak (default 7 days of green backups and battery), the operator releases the old
   `postgres-data` volume and the WSL 16 cluster. Rollback after step 4's restart is the forward path of D1 step 7,
   not a volume revert.

## External dependencies

`postgres:18.6-alpine` (pg-34); `pgvector/pgvector:0.8.6-pg18` (pg-37, pg-47); the PGDG apt repository with
`postgresql-18`, `postgresql-18-pgvector` and `postgresql-client-18`; `prometheuscommunity/postgres-exporter:v0.20.1`
(ex-01, ex-05). No new service, no new secret.

## fabrik-lib verdict

No module needed. The vendored `fastapi_user_auth/schema.sql:3` comment and the README pin are fabrik-lib's to
refresh — its D5 request.

## Constraints digest

- Same code in both environments: WSL and the hub move to the same major (`30-ops.md:311-321`); the gap between
  the windows is bounded (D2 step 6).
- `postgres-main:5432` stays the DSN host; nothing in any project's `.env` changes.
- Every service keeps its memory limit; the PG18 container keeps 2G.
- Destructive operations: dry-run first, the old volume kept, deletion only on the operator's explicit word
  (`CLAUDE.md` § HARD STOPS — volumes are data).
- A hub agent never edits another repo: project changes are requests (D5).
- Pack edits are infra's to render and merge (`CLAUDE.md` § Merge-time render only).

## Shape / infra implications

No spec `shape:` changes. One new external volume (`postgres18-data`) on vps1, added to the Backrest volume plan;
the old one retained until release.

## Documentation landing sites

The 29 live docs of the hub-pins table (`agents-fabrik.md` § Database and § Infra, `README.md`,
`docs/infrastructure/vps-complete-inventory.md`, `docs/operations/disaster-recovery.md`,
`docs/operations/hub-restore-inventory.md`, `docs/workstation/session-recall.md`, the technology guide,
`docs/reference/prebuilt-app-containers.md`, `docs/traycer/fabrik-workflow.md`, `docs/STRATEGIC_BACKLOG.md`, and
the rest of the measured set), `CHANGELOG.md`, and a D-row for the executed upgrade.

## Cost

Agent time for the plan and the hub branch; two operator windows (WSL ~1 h; hub ~1 h plus the manifest diff and
the battery, sized by U1); no money.

## Validation

- **V1 — contents:** on every database the D1 step 2 manifest matches after restore — exact row counts per table,
  sequence values, extensions and versions, database encoding/collation/owner, role attributes and SCRAM prefixes,
  `pg_auth_members`, `pg_default_acl`, ACLs normalised for `m`, every table's content hash (D-612's checksum
  tripwire), and the non-default server settings and `pg_hba` rules (less step 1's own
  `default_transaction_read_only`). The restore's stderr holds exactly the one allowed
  error. A `pg_dumpall` of the new cluster restores into a scratch PG18 container under the same rule.
- **V2 — version:** `SELECT version()` reports 18.6 on the hub and 18.x on WSL; `server_version_num >= 180000`.
- **V3 — services:** every service's `/health` (a real `SELECT 1`) is green; Gatus green for every
  database-backed endpoint; spoke services' health green over the mesh.
- **V4 — roles, live:** on the hub, every `pg_auth_members` row and every login role's `rolpassword LIKE 'SCRAM%'`
  matches the manifest; `tests/test_app_role_real_pg.py` passes against `postgres:18.6-alpine`.
- **V5 — backups:** the first nightly `pg_dumpall` after the window completes with its trailer; the Backrest
  `docker-volumes` snapshot contains `postgres18-data/_data/18/docker/PG_VERSION`.
- **V6 — monitoring:** the exporter reports `pg_up 1` with no collector errors.
- **V7 — registry:** `rules_render_versions.py --check` exits 0 with `postgres_major: "18"`; a `command grep`
  finds no live `postgres:16` pin in the hub outside the frozen artifacts.
- **V8 — disaster recovery:** a DR drill (`vultr_drill.py`, step 12c core boot) restores `postgres18-data` and
  boots it.

## Decisions taken

- D-612 — the operator's go (verbatim above), one-way, with its Binding block; its KILL clause is D2 step 5.
- Approach A over B and C (§ Rejected alternatives).
- trade-intelligence follows the fleet (D6) — derived from its own docs; no project stays behind.
- App-side UUIDv7 stays the scaffold default; native `uuidv7()` is permitted (D4).
- D3 lands as one branch after the hub window, except its DR-chain hunk, which merges inside the window so no
  disaster recovery runs against a repo that still lists `postgres-data` (D3, D1 step 8).

## Open / blocking unknowns

- U1 — the hub cluster's size and exact database list, and the hub's free disk (read live before the window; they
  size the window and decide the disk gate).
- U2 — `pre-backup.sh` (not in the repo): it runs `docker exec postgres-main pg_dumpall`, which is
  path-independent, but its retention and per-database loop are read on the hub in the plan.

## Intake Inventory

| I# | Item (anchored) | Disposition | Where |
|---|---|---|---|
| I1 | "it must be done in … wsl" | IN | D2, Lifecycle step 3 |
| I2 | "all vps servers" | IN — one cluster on vps1; the spokes run none (measured), so a reconnect check | D1, What exists today |
| I3 | "all opt projects" | IN — every pin and live doc measured; requests per project | D5, D6, D7 |
| I4 | "our rules must be updated in .windsurf/rules" | IN | D3 (registry), D4 (packs) |
| I5 | the stale 2026-05-25 plan | IN — superseded | header |
| I6 | backups and disaster recovery stay continuous through the move | IN | D1, D3 (DR chain), V5, V8 |
| I7 | registrar and watchdog roles keep working | IN | Compatibility § Roles, V4 |
| I8 | extensions in use survive | IN | What exists today, Compatibility |
| I9 | trade-intelligence's database (found: it has left Supabase for postgres-main) | IN | D6 |
| I10 | `postgres:postgres` superuser hard-coded in `infra/vps1/glitchtip/compose.yaml:7,35` and `infra/vps1/monitoring/compose.yaml:183` (found while grounding) | OUT-OF-SCOPE — a credentials fix, not the upgrade | W-a3dd3cb6 |
| I11 | five specs claim the shared `main` database; four specs set `depends.postgres` with no `shape:` (found while grounding) | OUT-OF-SCOPE — registrar naming hygiene; the upgrade moves whatever databases exist | W-2f54dfd4 |
| I12 | `fabrik_analytics` documented on WSL but also created on the hub (found while grounding) | OUT-OF-SCOPE — a placement question the upgrade does not change | W-b7661cd1 |
| I13 | brand-identiy-creator's `pg_uuidv7` dependency (found while grounding) | IN | D7 |
| I14 | WSL's hand-installed `pg_uuidv7` and `postgresql-16-pgvector` (found in review) | IN | D2 steps 1 and 4 |
| I15 | fabrik-lib's README pin and vendored schema comment | IN | D5 |
| I16 | calendar-orchestration-engine's unpinned `postgresql-client` | IN | D5 |
| I17 | the PG18 image's new data path in two project dev composes (tryton-crm, tojlo-mail) | IN | D5 |

Intake: 17 items — 14 IN, 3 OUT-OF-SCOPE (W-a3dd3cb6, W-2f54dfd4, W-b7661cd1), 0 ASK.
