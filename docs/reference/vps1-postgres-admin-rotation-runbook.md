# vps1 Postgres: scoped logins for GlitchTip and postgres_exporter, then rotate the admin password

The runbook W-a2ee211b must run through (D-1104: "approved in principle, executed only through a fleet runbook that
lists every admin-login consumer, rotation before the PG18 hub window, new password handed to the operator"). Item:
W-d87073c2. **Gate: credentials.** Every step that changes a password or a live service runs only on the operator's
go, relayed by the coordinator. Every `.env` or script edited on vps1 is backed up first
(`cp <f> <f>.backup.$(date +%Y%m%d-%H%M%S)`).

## Why

`postgres-main` on vps1 serves every project's database, and its superuser `postgres` still has the password
`postgres`. That password is committed in git, inline in two tracked composes:

- `infra/vps1/glitchtip/compose.yaml:11` and `:39` (web and worker): `DATABASE_URL: postgresql://postgres:postgres@postgres-main:5432/glitchtip`
- `infra/vps1/monitoring/compose.yaml:185` (postgres-exporter): `DATA_SOURCE_NAME: postgresql://postgres:postgres@postgres-main:5432/postgres?sslmode=disable`

Neither service needs the superuser. Each gets its own login first, so that rotating the admin password breaks
neither.

## Consumers of the admin login

The fourth column says whether a rotation breaks the consumer.

| # | Consumer | Where | Uses the password? |
|---|---|---|---|
| 1 | GlitchTip web + worker | `infra/vps1/glitchtip/compose.yaml:11`, `:39` | yes, until step 3 moves it to its own login |
| 2 | postgres_exporter | `infra/vps1/monitoring/compose.yaml:185` | yes, until step 3 moves it to its own login |
| 3 | `postgres-main` itself | `infra/vps1/postgres/compose.yaml:7` reads the untracked `infra/vps1/postgres/.env` (`POSTGRES_PASSWORD`, line 2) | only at first init of an empty data directory; a running cluster ignores it, but the file must still match, so that a rebuild does not resurrect the old password |
| 4 | Hub `.env`, `POSTGRES_HOST=postgres-main` / `POSTGRES_USER=postgres` / `POSTGRES_PASSWORD` | `/opt/fabrik/.env` | the value is updated in step 5. Nothing in `src/` reads it (`scripts/gather_envs.py:161,190` only lists the names). The `PG_*` keys point at the WSL `localhost` database and are out of scope |
| 5 | The hub registrars | `src/fabrik/drivers/postgres.py:136`: `sudo docker exec -i postgres-main psql -U postgres` | **no, if** `pg_hba.conf` trusts local socket connections. Step 1 verifies this; if it does not hold, stop |
| 6 | site-provisioner `DATABASE_URL` | the vps1 `.env` beside `infra/vps1/site-provisioner/compose.yaml` (untracked) | yes if it names `postgres:` (step 1 reads it) |
| 7 | `/opt/backups/pre-backup.sh` | on vps1 | yes if it connects over TCP as `postgres`; no if it uses `docker exec … pg_dumpall` (step 1 reads it) |
| 8 | Anything else connecting as `postgres` | found only live | step 1's `pg_stat_activity` and `.env` sweep |

## Steps

### 1. Inventory: read-only, any time

On vps1, run as the deploy user. Nothing changes.

```bash
# 5: local-socket trust, so the registrars need no password
sudo docker exec postgres-main sh -c 'grep -vE "^\s*(#|$)" "$PGDATA/pg_hba.conf"'      # expect: local all all trust
# 6, 7, 8: every file on the box naming the superuser with a password (names only, values masked)
sudo grep -rIlE 'postgres(ql)?://postgres:' /opt --include='*.env' --include='.env' --include='*.sh' --include='*.yaml' --include='*.yml' 2>/dev/null
sudo grep -nE 'psql|pg_dump|PGPASSWORD' /opt/backups/pre-backup.sh
# 8: live sessions by login, over a day (re-run a few times; a cron consumer shows only when it runs)
sudo docker exec postgres-main psql -U postgres -tAc "select usename, application_name, client_addr, count(*) from pg_stat_activity where usename is not null group by 1,2,3 order by 1"
```

Add every hit outside rows 1-7 to the table before going on. **Stop** if `pg_hba.conf` has no `local … trust` line
for `postgres`, because then step 4 would break every registrar.

### 2. Generate the passwords

There are three passwords, all 32 characters from `[a-zA-Z0-9]` via `secrets.choice()` (the password policy):
`glitchtip`, `postgres_exporter`, and the new admin password. Generate them on the hub and keep them in
`backups/` (gitignored) until step 6.

### 3. Scoped logins, then move the two services to them (gate: credentials)

```sql
-- GlitchTip: owns its own database, because it runs its own migrations
CREATE ROLE glitchtip LOGIN PASSWORD '<glitchtip pw>';
ALTER DATABASE glitchtip OWNER TO glitchtip;
\c glitchtip
ALTER SCHEMA public OWNER TO glitchtip;
DO $$ DECLARE r record; BEGIN
  FOR r IN SELECT format('ALTER %s %I.%I OWNER TO glitchtip',
             CASE c.relkind WHEN 'r' THEN 'TABLE' WHEN 'p' THEN 'TABLE' WHEN 'S' THEN 'SEQUENCE'
                            WHEN 'v' THEN 'VIEW' WHEN 'm' THEN 'MATERIALIZED VIEW' END,
             n.nspname, c.relname) AS q
           FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
           WHERE n.nspname = 'public' AND c.relkind IN ('r','p','S','v','m')
             AND NOT EXISTS (SELECT 1 FROM pg_depend d WHERE d.objid = c.oid AND d.deptype = 'a')
  LOOP EXECUTE r.q; END LOOP; END $$;
-- postgres_exporter: read-only monitoring, no ownership
\c postgres
CREATE ROLE postgres_exporter LOGIN PASSWORD '<exporter pw>';
GRANT pg_monitor TO postgres_exporter;
```

The `pg_depend` filter skips sequences owned by a column; they follow their table.

Then move the two compose files off inline credentials. The DSNs go into an untracked `.env` beside each compose,
read as `${GLITCHTIP_DATABASE_URL}` / `${POSTGRES_EXPORTER_DSN}`, so no password stays in git. This is a hub change
committed and merged like any other, then `fabrik apply` / `docker compose up -d` for each service.

Verify before step 4:
- GlitchTip's `/api/0/` answers and a test event lands.
- `pg_up 1` from postgres-exporter in Prometheus.
- `pg_stat_activity` shows `glitchtip` and `postgres_exporter`, and no `postgres` session from either container.

### 4. Rotate the admin password (gate: credentials) — before the PG18 hub window

```bash
# the old password stays on record for rollback; today it is the literal 'postgres'
sudo docker exec -i postgres-main psql -U postgres -c "ALTER ROLE postgres PASSWORD '<new admin pw>'"
```

### 5. Update every consumer that holds the password

- Row 3: `infra/vps1/postgres/.env` `POSTGRES_PASSWORD`.
- Row 4: the hub `/opt/fabrik/.env` `POSTGRES_PASSWORD`.
- Rows 6 and 7, and anything step 1 added, if they use it.

Back up each file first. Then re-run step 1's `pg_stat_activity` query and a registrar dry run
(`fabrik plan specs/services/<any db spec>.yaml`) to prove nothing still authenticates with the old password.

### 6. Hand the operator the new admin password

Give it through the coordinator, never in git, mail or a commit message. Delete the `backups/` copy once the
operator confirms they hold it.

## Rollback

| Undo | How |
|---|---|
| step 4 | `ALTER ROLE postgres PASSWORD 'postgres'`, then restore each `.env` from its step-5 backup |
| step 3 | point each service back at its backed-up `.env` or compose and redeploy. The scoped roles can stay; they own nothing the superuser cannot reach |

## Order constraint

Steps 3 to 5 run before the PG18 hub window. A dump and restore into PG18 carries roles and passwords over, so the
upgrade then starts from the rotated state and never re-introduces `postgres:postgres`.
