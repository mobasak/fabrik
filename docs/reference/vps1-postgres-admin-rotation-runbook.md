# vps1 Postgres: scoped logins for GlitchTip and postgres_exporter, then rotate the admin password

The runbook W-a2ee211b must run through (D-1104: "approved in principle, executed only through a fleet runbook that
lists every admin-login consumer, rotation before the PG18 hub window, new password handed to the operator"). Item:
W-d87073c2. **Gate: credentials.** Every step that changes a password or a live service runs only on the operator's
go, relayed by the coordinator. Every file edited on vps1 is backed up first
(`cp <f> <f>.backup.$(date +%Y%m%d-%H%M%S)`).

## Why

`postgres-main` on vps1 serves every project's database, and its superuser `postgres` still has the password
`postgres`. That password is committed in git, inline in two tracked composes:

- `infra/vps1/glitchtip/compose.yaml:11` and `:39` (web and worker): `DATABASE_URL: postgresql://postgres:postgres@postgres-main:5432/glitchtip`
- `infra/vps1/monitoring/compose.yaml:185` (postgres-exporter): `DATA_SOURCE_NAME: postgresql://postgres:postgres@postgres-main:5432/postgres?sslmode=disable`

Both files are MIRRORS. GlitchTip's live stack is the hand-maintained `/opt/glitchtip/compose.yaml` on vps1
(`infra/vps1/glitchtip/compose.yaml:2`). The monitoring compose is a mirror too (`src/fabrik/drivers/prometheus.py:91-92`
names the mirror only), and its live path is found in step 1. No deployer applies these mirrors, so every edit below
lands on the live file first and is mirrored in git after.

## Consumers of the admin login

The fourth column says whether a rotation breaks the consumer.

| # | Consumer | Where | Uses the password? |
|---|---|---|---|
| 1 | GlitchTip web + worker | live `/opt/glitchtip/compose.yaml` on vps1; mirror `infra/vps1/glitchtip/compose.yaml:11`, `:39` | yes, until step 3 moves it to its own login |
| 2 | postgres_exporter | live monitoring compose on vps1 (path found in step 1); mirror `infra/vps1/monitoring/compose.yaml:185` | yes, until step 3 moves it to its own login |
| 3 | `postgres-main` itself | `infra/vps1/postgres/compose.yaml:7` reads the untracked `infra/vps1/postgres/.env` (`POSTGRES_PASSWORD`, line 2) | only at first init of an empty data directory; the file must still match, so that a rebuild does not resurrect the old password |
| 4 | Hub `.env`, `POSTGRES_HOST=postgres-main` / `POSTGRES_USER=postgres` / `POSTGRES_PASSWORD` | `/opt/fabrik/.env` | the value is updated in step 5. Nothing in `src/` reads it; `scripts/gather_envs.py:173` only classifies the name. The `PG_*` keys point at the WSL `localhost` database and are out of scope |
| 5 | Every scaffolded app whose `.env` lacks `DATABASE_URL` | the fallback `DATABASE_URL=${DATABASE_URL:-postgresql://postgres:${POSTGRES_PASSWORD}@postgres-main:5432/…}` in `templates/python-api/compose.yaml.j2:46`, `templates/node-api/compose.yaml.j2:29`, `templates/saas-skeleton/compose.yaml.j2:25`, `templates/chrome-extension/compose.yaml.j2:31`, `templates/_partials/_companion_service.yaml.j2:40`, `apps/example-api/compose.yaml:21` | yes, for any deployed app that relies on the fallback. Step 1 lists them |
| 6 | site-provisioner `DATABASE_URL` | the vps1 `.env` beside `infra/vps1/site-provisioner/compose.yaml` (untracked) | yes if it names `postgres` (step 1 reads it) |
| 7 | `/opt/backups/pre-backup.sh` | on vps1 | yes if it connects over TCP as `postgres`; no if it uses `docker exec` (step 1 reads it) |
| 8 | Hub callers over the container's local socket | `src/fabrik/drivers/postgres.py:136`, `src/fabrik/audit.py:183`, `scripts/vps_sync.py:453`, `scripts/audit/06-backup.sh:103`, `scripts/bootstrap/bootstrap-hub.sh:1217,1232,1286,1330,1343,1765`, `docs/operations/deployment.md:537` — all `docker exec … psql -U postgres` or `pg_dump -U postgres` | **no, as long as** the `local` line for `postgres` is `trust`: they send no password. Under `scram-sha-256`, `md5` or `password` they would break after step 4, and `peer` already fails because `docker exec` runs as root. Step 1 stops on anything but `trust` |
| 9 | Anything else connecting as `postgres` over TCP | vps1 itself, the hub and the spokes over WireGuard (`infra/vps1/postgres/compose.yaml:24` binds `10.99.0.1:5432`) | found only live: step 1's file sweep and `pg_stat_activity` with `client_addr` |

## Steps

Steps 2-3 are scripted for the operator: `cd /opt/fabrik && python3 -I scripts/sysadmin/vps1_pg_scoped_logins.py`
(W-80983d8c), one typed `yes` per block. From step 1 it runs the sweep of the spokes and the pg_hba and SCRAM-setting
stop checks. It does not run step 1's sweep of vps1 itself or its `pg_stat_activity` survey; fleet ran both read-only
on 2026-10-23. It differs from the text below in four ways:
- In place of step 3's `\password` prompts it sends a SCRAM verifier on ssh stdin (D-1177).
- It grants CONNECT on every database where PUBLIC lacks it.
- It gates on the verify bullets except the test event and the per-database metrics, which stay manual.
- It records both logins in the hub `.env` (D-1176).
The mirror commit in `infra/vps1/` and step 4 are not in it.

### 1. Inventory: read-only, any time

On vps1, as the deploy user. Nothing changes, and every grep prints file names or masks values.

```bash
sudo docker exec postgres-main psql -U postgres -tAc 'show server_version'
# auth rules: the local lines (row 8), and STOP on any non-loopback "host … trust" line
sudo docker exec postgres-main sh -c 'grep -vE "^\s*(#|$)" "$PGDATA/pg_hba.conf"'
# rows 5, 6, 7, 9: every file on the box that can log in as the superuser (names only)
sudo grep -rIlE 'postgres(ql)?://postgres:|user=postgres|-U postgres|PGPASSWORD|POSTGRES_PASSWORD' /opt 2>/dev/null
sudo grep -rIl 'postgres-exporter' /opt --include='*compose*.y*ml' 2>/dev/null   # the live monitoring compose (row 2)
sudo sed -E "s/((PG)?PASSWORD=|[Pp]assword *= *|:\/\/[^:]+:)(\"[^\"]*\"|'[^']*'|[^@ \"']*)/\1***/g" /opt/backups/pre-backup.sh | grep -niE 'psql|pg_dump|password'
# row 9: live TCP sessions by login. Re-run across a day; a cron consumer shows only when it runs
sudo docker exec postgres-main psql -U postgres -tAc "select usename, application_name, client_addr, count(*) from pg_stat_activity where client_addr is not null group by 1,2,3 order by 1"
# the exporter's reach: databases where PUBLIC lost CONNECT (each needs a GRANT in step 3)
sudo docker exec postgres-main psql -U postgres -tAc "select datname from pg_database where not datistemplate and not has_database_privilege('public', oid, 'CONNECT')"
# GlitchTip's own schema: partitions and objects step 3 must re-own
sudo docker exec postgres-main psql -U postgres -d glitchtip -tAc "select relkind, count(*) from pg_class where relnamespace='public'::regnamespace group by 1"
```

Add every hit outside rows 1-8 to the table before going on.

**Stop if:**
- The `local` line that matches `postgres` (`local all all`, or `local all postgres`) is anything but `trust`.
  Row 8's passwordless callers would break at step 4.
- `pg_hba.conf` has a `host … trust` line for a non-loopback address. The password would then protect nothing, and
  that is a different fix.
- Any consumer is found that step 5 cannot update.

### 2. Generate the passwords

There are three passwords, all 32 characters from `[a-zA-Z0-9]` via `secrets.choice()` (the password policy):
`glitchtip`, `postgres_exporter`, and the new admin password. Write them on the hub under `backups/` (gitignored)
with `umask 077`, so the files are mode 0600. Keep them until step 6.

### 3. Scoped logins, then move the two services to them (gate: credentials)

A password never goes on a command line, into the SQL text, or into the server log:
- A failing statement is logged verbatim (`log_min_error_statement`).
- promtail mounts the Docker container logs (`infra/vps1/monitoring/compose.yaml:35`) and ships them to Loki.

So roles are created without a password, and each password is set at psql's no-echo prompt, which sends only a
SCRAM hash. Feed the SQL file on stdin from a `chmod 600` copy on vps1, then delete the copy:

```sql
-- run: sudo docker exec -i postgres-main psql -U postgres -v ON_ERROR_STOP=1 < step3.sql
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'glitchtip') THEN CREATE ROLE glitchtip LOGIN; END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'postgres_exporter') THEN CREATE ROLE postgres_exporter LOGIN; END IF;
END $$;
GRANT pg_monitor TO postgres_exporter;
-- one line per database step 1 listed (none listed: no line):
-- GRANT CONNECT ON DATABASE <db> TO postgres_exporter;
ALTER DATABASE glitchtip OWNER TO glitchtip;
\c glitchtip
-- One object per transaction (each ALTER … OWNER locks its table, indexes and TOAST until COMMIT; GlitchTip's log
-- partitions overflow max_locks_per_transaction in one transaction), a busy table fails within lock_timeout instead
-- of queueing GlitchTip's queries behind an ACCESS EXCLUSIVE request, and what glitchtip already owns is skipped, so a
-- re-run locks only the leftovers. The DO block must not run inside an open transaction (no BEGIN around it): a
-- COMMIT inside DO then fails with "invalid transaction termination".
SET lock_timeout = '5s';
ALTER SCHEMA public OWNER TO glitchtip;
DO $$ DECLARE r record; BEGIN
  -- tables, partitions, foreign tables, views, matviews, and every sequence a column does not own
  FOR r IN SELECT format('ALTER %s IF EXISTS %I.%I OWNER TO glitchtip',
             CASE c.relkind WHEN 'S' THEN 'SEQUENCE' WHEN 'v' THEN 'VIEW' WHEN 'm' THEN 'MATERIALIZED VIEW'
                            WHEN 'f' THEN 'FOREIGN TABLE' ELSE 'TABLE' END, n.nspname, c.relname) AS q
           FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
           WHERE n.nspname = 'public' AND c.relkind IN ('r','p','S','v','m','f')
             AND c.relowner <> 'glitchtip'::regrole
             AND NOT EXISTS (SELECT 1 FROM pg_depend d WHERE d.classid = 'pg_class'::regclass AND d.objid = c.oid AND d.deptype = 'e')
             AND NOT (c.relkind = 'S' AND EXISTS (SELECT 1 FROM pg_depend d
                       WHERE d.classid = 'pg_class'::regclass AND d.objid = c.oid
                         AND d.refclassid = 'pg_class'::regclass AND d.deptype IN ('a','i')))
           ORDER BY c.oid
  LOOP EXECUTE r.q; COMMIT; END LOOP;
  -- composite types (ALTER TYPE has no IF EXISTS)
  FOR r IN SELECT format('ALTER TYPE %I.%I OWNER TO glitchtip', n.nspname, c.relname) AS q
           FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
           WHERE n.nspname = 'public' AND c.relkind = 'c' AND c.relowner <> 'glitchtip'::regrole
             AND NOT EXISTS (SELECT 1 FROM pg_depend d WHERE d.classid = 'pg_class'::regclass AND d.objid = c.oid AND d.deptype = 'e')
           ORDER BY c.oid
  LOOP EXECUTE r.q; COMMIT; END LOOP;
  -- functions and procedures, extension members excluded
  FOR r IN SELECT format('ALTER ROUTINE %s OWNER TO glitchtip', p.oid::regprocedure) AS q
           FROM pg_proc p WHERE p.pronamespace = 'public'::regnamespace AND p.proowner <> 'glitchtip'::regrole
             AND NOT EXISTS (SELECT 1 FROM pg_depend d WHERE d.classid = 'pg_proc'::regclass AND d.objid = p.oid AND d.deptype = 'e')
           ORDER BY p.oid
  LOOP EXECUTE r.q; COMMIT; END LOOP;
  -- enums, domains, ranges, multiranges
  FOR r IN SELECT format('ALTER %s %s OWNER TO glitchtip', CASE t.typtype WHEN 'd' THEN 'DOMAIN' ELSE 'TYPE' END,
                         t.oid::regtype) AS q
           FROM pg_type t WHERE t.typnamespace = 'public'::regnamespace AND t.typtype IN ('e','d','r','m')
             AND t.typowner <> 'glitchtip'::regrole
             AND NOT EXISTS (SELECT 1 FROM pg_depend d WHERE d.classid = 'pg_type'::regclass AND d.objid = t.oid AND d.deptype = 'e')
           ORDER BY t.oid
  LOOP EXECUTE r.q; COMMIT; END LOOP;
END $$;
```

The re-own commits after every object (the operator's 2026-10-28 run of the script overflowed
`max_locks_per_transaction` re-owning GlitchTip's log partitions in one transaction), waits at most 5 s for a busy
table, and skips what `glitchtip` already owns, so a run stopped by a lock timeout is finished by running it again
(`tests/test_vps1_pg_scoped_logins.py` runs it on a local PostgreSQL 16 cluster with a 100-slot lock table, over
300 partitions, a composite type, an enum, a domain, a range and a function). Never wrap it in BEGIN: a COMMIT
inside the DO block then fails.

Afterwards every public object is owned by `glitchtip` (a range's multirange with it), and `ALTER TABLE` on the
partitioned parent succeeds as `glitchtip`. Identity and serial sequences follow their table. Extension members
(`pg_trgm`, `citext`) stay with their extension, and the checks below exclude them.

Then set the two passwords at the prompt, in `sudo docker exec -it postgres-main psql -U postgres`:
`\password glitchtip`, then `\password postgres_exporter`.

**Verify the ownership before any service moves.** All three counts must be 0:

```sql
\c glitchtip
select count(*) from pg_class c where relnamespace='public'::regnamespace and relowner <> 'glitchtip'::regrole
  and not exists (select 1 from pg_depend d where d.classid='pg_class'::regclass and d.objid=c.oid and d.deptype='e');
select count(*) from pg_proc p  where pronamespace='public'::regnamespace and proowner <> 'glitchtip'::regrole
  and not exists (select 1 from pg_depend d where d.classid='pg_proc'::regclass and d.objid=p.oid and d.deptype='e');
select count(*) from pg_type t  where typnamespace='public'::regnamespace and typtype in ('e','d','r','m') and typowner <> 'glitchtip'::regrole
  and not exists (select 1 from pg_depend d where d.classid='pg_type'::regclass and d.objid=t.oid and d.deptype='e');
```

**Move the two services.** Edit the LIVE composes on vps1, after backing them up. Each DSN goes into an untracked
`.env` beside its compose, read as `${GLITCHTIP_DATABASE_URL}` / `${POSTGRES_EXPORTER_DSN}`.

Stop unless `docker compose config` resolves each DSN to the scoped user and the right database (GlitchTip:
`glitchtip@…/glitchtip`). An empty or wrong DSN detaches GlitchTip's live error history
(`infra/vps1/glitchtip/compose.yaml:4`). Then run `docker compose up -d`, and mirror both composes, with the
`${…}` references and no credentials, into `infra/vps1/` in a hub commit.

Verify before step 4:
- GlitchTip's `/api/0/` answers and a test event lands.
- `pg_up 1` from postgres-exporter in Prometheus, and per-database metrics for every database.
- `pg_stat_activity` shows `glitchtip` and `postgres_exporter`, and no `postgres` session from either container.

### 4. Rotate the admin password (gate: credentials)

1. Save the exact current credential for rollback, on vps1, into a 0600 file:
   `(umask 077; sudo docker exec postgres-main psql -U postgres -tAc "select rolpassword from pg_authid where rolname='postgres'" > ~/pg-verifier)`.
   This is the stored SCRAM verifier. It contains `$`, so it never passes through a shell string again.
2. List the live TCP sessions as `postgres` (step 1's query). These are the consumers that must change in step 5.
3. In `sudo docker exec -it postgres-main psql -U postgres`, run `\password postgres` and enter the new admin
   password at the prompt.
4. `ALTER ROLE` does not end open sessions. A password is checked only at connect, so a pooled consumer still on
   the old password keeps working until it reconnects. That re-check is forced in step 5, after the consumers are
   updated, never before (terminating first would drop every not-yet-updated consumer).

### 5. Update every consumer that holds the password, then prove it

- Row 3: `infra/vps1/postgres/.env` `POSTGRES_PASSWORD`.
- Row 4: the hub `/opt/fabrik/.env` `POSTGRES_PASSWORD`.
- Row 5: each app `.env` that relies on the fallback. Better, give it its own `DATABASE_URL` (its app role).
- Rows 6 and 7, and anything step 1 added.

Back up each file first. Then force every TCP `postgres` session to reconnect with the new password, inside the window:
`select pg_terminate_backend(pid) from pg_stat_activity where usename='postgres' and client_addr is not null`. Then prove it.

- **Watch for stale credentials:** follow
  `sudo docker logs --since <step-4 time> postgres-main 2>&1 | grep 'password authentication failed for user "postgres"'`
  for at least one full cron cycle (a day covers the nightly backup). **Any line is a stop.** Find that consumer, or
  roll back.
- **Do not use `fabrik plan` or a registrar dry run as proof.** Neither sends SQL (`src/fabrik/drivers/postgres.py:132-134`).
  The registrars also go through the local socket (row 8), which never checks a password under the `trust` line step 1 requires.

### 6. Hand the operator the new admin password

Give it through the coordinator, never in git, mail or a commit message. Delete the `backups/` copies once the
operator confirms they hold it. Once no rollback is wanted, `rm ~/pg-verifier` on vps1.

## Rollback

| Undo | How |
|---|---|
| step 4 | `sudo docker cp ~/pg-verifier postgres-main:/tmp/pg-verifier`, then in `sudo docker exec -it postgres-main psql -U postgres`: `\set v \`cat /tmp/pg-verifier\`` and `ALTER ROLE postgres PASSWORD :'v';` (PostgreSQL stores a pre-hashed value as is). Assert `select rolpassword = :'v' from pg_authid where rolname='postgres'` returns `t`; `sudo docker exec postgres-main rm /tmp/pg-verifier` and `rm ~/pg-verifier`; then restore each step-5 file from its backup |
| step 3, services | restore each live compose and `.env` from its backup and `docker compose up -d`; revert the mirror commit in the hub, or the next sync re-applies it |
| step 3, ownership | kept on purpose: a superuser still reaches every object, and the scoped roles do no harm. To drop them, first run the step-3 ownership block with every `OWNER TO glitchtip` changed to `OWNER TO postgres` and every `<> 'glitchtip'::regrole` skip filter changed to `<> 'postgres'::regrole` (the database name `glitchtip` stays), or `DROP ROLE` fails with "owns objects"; and revoke each CONNECT grant
step 3 made (`REVOKE CONNECT ON DATABASE <db> FROM postgres_exporter`), or it fails with "privileges for database" |

## Before and after the rotation

- **PG18:** the item and D-1104 name a "PG18 hub window", but the tracked `infra/vps1/postgres/compose.yaml:3`
  already pins `postgres:18.6-alpine`. Step 1's `server_version` says which state vps1 is in.
  - If a major upgrade is still ahead, rotate first.
  - Make that window carry the roles: `pg_dumpall --globals-only`, or `pg_upgrade`. The per-database `pg_dump`
    backups do not, so a per-database restore would lose `glitchtip`, `postgres_exporter` and their ownership.
- **Git history:** the literal `postgres` stays in the history of the two mirrors after the rotation. That is
  harmless once the password is rotated, and the mirror commit in step 3 removes it from the current tree.

<!-- BEGIN related-scripts: generated by scripts/render_doc_script_links.py — do not hand-edit -->
## Related scripts

Scripts that declare this document in their `# AFTER-EDIT:` header — editing one of them
means updating this page in the same change. This list is generated from those headers
(`python3 scripts/render_doc_script_links.py`); add the doc to a script's header, not here.

- `scripts/sysadmin/vps1_pg_scoped_logins.py`
<!-- END related-scripts -->
