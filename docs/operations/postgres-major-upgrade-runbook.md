# PostgreSQL major upgrade runbook — 16 → 18 (WSL and hub windows)

**Status:** ready for the operator's windows · **Owner:** fleet · **Date:** 2026-10-06
**Design:** [`docs/superpowers/specs/2026-10-06-postgresql-18-fleet-upgrade-design.md`](../superpowers/specs/2026-10-06-postgresql-18-fleet-upgrade-design.md) (approved, D-617; operator ruling D-612)
**Plan:** [`docs/development/plans/2026-10-06-plan-1-postgresql-18-upgrade/`](../development/plans/2026-10-06-plan-1-postgresql-18-upgrade/2026-10-06-plan-1-postgresql-18-upgrade.md), ticket T05

This runbook is executed by the OPERATOR, in two windows: the WSL window (spec § The delta › D2) and, within 7 days
of it, the hub window (spec § The delta › D1; a Gate 2 class step — production data). It serves the next major too:
the steps are written against "the old major" and "the new major", with 16 and 18 as today's values.

Order of the whole move (spec § Lifecycle): § 1 pre-window probes → appendix A1 (brand-identiy-creator, BEFORE the
WSL window) → § 2 WSL window → § 3 hub window → the rest of the appendix → the soak → § 4 release.

Rules that bind every step:

- **Every step is idempotent** — re-running it after an interruption is a no-op where its outcome is already present
  (`.windsurf/rules/core/90-bootstrap-scripts.md:169-170`); tools are probed with `command -v` (`:143`).
- **Every step has a command block, a `Verify:` line and a `Rollback:` line.** A red `Verify:` stops the window
  at that step; take its `Rollback:` and stop.
- **Nothing removes a docker volume or a cluster without the operator's explicit word** — volumes are data
  (`CLAUDE.md` § HARD STOPS). Such a step carries an **Operator's explicit word** line and is never run on momentum.
  The old `postgres-data` volume and the WSL 16 cluster survive until § 4, which starts with the V8 DR drill.
- **No secret value is printed or pasted.** The superuser password is typed into `read -rs` as `$PGPW` and reaches
  containers only through a mode-600 env file; restic credentials are read by name from `/opt/fabrik/.env` inside
  a root shell, the way `scripts/bootstrap/bootstrap-hub.sh:286-300` does.
- **Every SQL and dump on the hub runs inside a container** — `_run_sql` is `docker exec -i postgres-main psql -U
  postgres` (`src/fabrik/drivers/postgres.py:136`), and the dump client is the NEW major's image.

## 0. Conventions and helpers

Each block's first line names its host: `# on: hub` (vps1, `ssh vps`, as the sudo user), `# on: wsl`, or
`# on: vps2 and vps3`. Paste the helper block below into EVERY hub and WSL shell you open for a window (it
defines functions only; it changes nothing).

```bash
# on: hub AND wsl — paste into every window shell; it defines functions, it changes nothing.
# PSQL is set per host: hub → PSQL=(sudo docker exec -i postgres-main psql -U postgres)
#                       wsl → PSQL=(sudo -u postgres psql -p 5432)

dbs() {   # every database that accepts connections (template0 is skipped by datallowconn)
  "${PSQL[@]}" -X -At -d postgres -c "SELECT datname FROM pg_database WHERE datallowconn ORDER BY 1"
}

pg_manifest_cluster() {   # cluster-wide part of the D1 step 2 manifest (spec § The delta › D1 step 2)
  "${PSQL[@]}" -X -At -v ON_ERROR_STOP=1 -d postgres -f - <<'SQL'
SELECT 'db|' || d.datname || '|' || pg_encoding_to_char(d.encoding) || '|' || d.datcollate || '|' || d.datctype
       || '|' || d.datlocprovider::text || '|' || coalesce(to_jsonb(d) ->> 'datlocale', to_jsonb(d) ->> 'daticulocale', '')
       || '|' || d.datconnlimit || '|' || d.datdba::regrole
  FROM pg_database d ORDER BY d.datname;
SELECT 'role|' || rolname || '|' || rolsuper || '|' || rolinherit || '|' || rolcreaterole || '|' || rolcreatedb
       || '|' || rolcanlogin || '|' || rolreplication || '|' || rolbypassrls || '|' || rolconnlimit
       || '|' || coalesce(left(rolpassword, 14), '')
  FROM pg_authid WHERE rolname NOT LIKE 'pg\_%' ORDER BY rolname;
SELECT 'member|' || m.roleid::regrole || '|' || m.member::regrole || '|' || m.grantor::regrole || '|' || m.admin_option
       || '|' || m.inherit_option || '|' || m.set_option
  FROM pg_auth_members m
 WHERE NOT (m.roleid::regrole::text LIKE 'pg\_%' AND m.member::regrole::text LIKE 'pg\_%')
 ORDER BY 1;
SELECT 'setting|' || name || '|' || setting || '|' || source || '|' || coalesce(regexp_replace(sourcefile, '^.*/', ''), '')
  FROM pg_settings WHERE source NOT IN ('default', 'override', 'client', 'session') ORDER BY name;
SELECT 'hba|' || type || '|' || array_to_string(database, ',') || '|' || array_to_string(user_name, ',')
       || '|' || coalesce(address, '') || '|' || coalesce(netmask, '') || '|' || coalesce(auth_method, '')
       || '|' || coalesce(array_to_string(options, ','), '')
  FROM pg_hba_file_rules ORDER BY rule_number;
SELECT 'ident|' || map_name || '|' || sys_name || '|' || pg_username FROM pg_ident_file_mappings ORDER BY map_number;
SQL
}

pg_manifest_db() {   # per-database part: extensions, sequences, ACLs, default ACLs, exact count + content hash per table
  "${PSQL[@]}" -X -At -v ON_ERROR_STOP=1 -d "$1" -f - <<'SQL'
SELECT 'ext|' || extname || '|' || extversion FROM pg_extension ORDER BY extname;
SELECT 'seq|' || schemaname || '.' || sequencename || '|' || coalesce(last_value::text, 'not-called')
  FROM pg_sequences ORDER BY 1;
SELECT 'nspacl|' || nspname || '|' || coalesce(nspacl::text, '')
  FROM pg_namespace WHERE nspname NOT LIKE 'pg\_%' AND nspname <> 'information_schema' ORDER BY 1;
SELECT 'acl|' || n.nspname || '.' || c.relname || '|' || c.relkind::text || '|' || coalesce(c.relacl::text, '')
  FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
 WHERE n.nspname NOT LIKE 'pg\_%' AND n.nspname <> 'information_schema' AND c.relkind IN ('r', 'p', 'v', 'm', 'S', 'f')
 ORDER BY 1;
SELECT 'defacl|' || defaclrole::regrole || '|' || coalesce(nullif(defaclnamespace, 0)::regnamespace::text, 'global')
       || '|' || defaclobjtype::text || '|' || defaclacl::text
  FROM pg_default_acl ORDER BY 1;
SELECT format('SELECT %L || count(*) || %L || md5(coalesce(string_agg(t::text, E''\n'' ORDER BY %s), '''')) FROM %I.%I t',
              'table|' || n.nspname || '.' || c.relname || '|', '|',
              coalesce((SELECT string_agg(format('t.%I', a.attname), ', ' ORDER BY k.ord)
                          FROM pg_index i
                          CROSS JOIN LATERAL unnest(i.indkey) WITH ORDINALITY AS k(attnum, ord)
                          JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = k.attnum
                         WHERE i.indrelid = c.oid AND i.indisprimary), 't::text'),
              n.nspname, c.relname)
  FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
 WHERE c.relkind = 'r' AND n.nspname NOT LIKE 'pg\_%' AND n.nspname <> 'information_schema'
 ORDER BY n.nspname, c.relname
\gexec
SQL
}

pg_manifest() {   # [--retake] <dir>. A BEFORE reading (no --retake) is taken once and kept. An AFTER reading passes
                  # --retake: it is taken fresh into <dir>.new and swapped in only when complete (the old one moves to
                  # <dir>.prev-<time>), so a re-run after a fix never compares stale data. A failed reading is moved aside.
  local retake=0 out db new
  [ "$1" = --retake ] && { retake=1; shift; }
  out="$1"
  if [ "$retake" = 0 ] && [ -s "$out/COMPLETE" ]; then echo "manifest $out already taken — kept (a BEFORE reading)"; return 0; fi
  new="$out.new"; [ -e "$new" ] && mv "$new" "$out.partial-$(date -u +%H%M%S)"
  mkdir -p "$new"
  pg_manifest_cluster > "$new/cluster.txt" || { mv "$new" "$out.failed-$(date -u +%H%M%S)"; echo "MANIFEST FAILED (cluster)"; return 1; }
  for db in $(dbs); do
    pg_manifest_db "$db" > "$new/db-$db.txt" || { mv "$new" "$out.failed-$(date -u +%H%M%S)"; echo "MANIFEST FAILED ($db)"; return 1; }
  done
  echo "$(ls "$new" | wc -l) files" > "$new/COMPLETE"
  [ -e "$out" ] && mv "$out" "$out.prev-$(date -u +%H%M%S)"
  mv "$new" "$out"
  echo "manifest $out: $(ls "$out" | wc -l) files, $(cat "$out"/db-*.txt | grep -c '^table|') tables"
}

manifest_norm() {   # PG17 adds MAINTAIN (m) to every owner's ACL on restore; step 1's read-only flag is expected on the old side only;
                    # PG18's initdb writes autovacuum_worker_slots into postgresql.conf (new in 18 — measured on a 16-alpine/18.6-alpine pair)
  sed -E '/^(acl|nspacl|defacl)\|/ s/(=[A-Za-z*]*)m/\1/g' "$1" | grep -vE '^setting\|(default_transaction_read_only|autovacuum_worker_slots)\|'
}

manifest_diff() {   # $1 = before dir, $2 = after dir; per-file diffs land in $2.diffs/; rc 1 on ANY difference
  local a="$1" b="$2" f rc=0
  [ -s "$a/COMPLETE" ] && [ -s "$b/COMPLETE" ] || { echo "DIFF: $a or $b is not a COMPLETE reading"; return 1; }
  [ -e "$b.diffs" ] && mv "$b.diffs" "$b.diffs.prev-$(date -u +%H%M%S)"   # diffs always belong to the latest reading
  mkdir -p "$b.diffs"
  diff <(ls "$a") <(ls "$b") > "$b.diffs/_file-list" || { echo "DIFF: file list"; rc=1; }
  for f in $(ls "$a"); do
    diff <(manifest_norm "$a/$f") <(manifest_norm "$b/$f") > "$b.diffs/$f" || { echo "DIFF: $f"; rc=1; }
  done
  [ "$rc" = 0 ] && echo "manifest_diff: $a == $b ($(ls "$a" | wc -l) files)"
  return "$rc"
}

pg_compat_checks() {   # spec § Compatibility checks — restore blockers, pg_trgm index validity, SCRAM roles
  local db
  for db in $(dbs); do
    "${PSQL[@]}" -X -At -v ON_ERROR_STOP=1 -d "$db" -f - <<'SQL'
SELECT 'BLOCKER adminpack|' || current_database() FROM pg_extension WHERE extname = 'adminpack';
SELECT DISTINCT 'BLOCKER nondeterministic-key|' || current_database() || '|' || c.conrelid::regclass || '|' || c.conname
  FROM pg_constraint c
  JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = ANY (c.conkey)
  JOIN pg_collation co ON co.oid = a.attcollation
 WHERE c.contype IN ('p', 'f', 'u') AND NOT co.collisdeterministic;
SELECT 'BLOCKER unlogged-partitioned|' || current_database() || '|' || oid::regclass
  FROM pg_class WHERE relkind = 'p' AND relpersistence = 'u';
SELECT 'INVALID index|' || current_database() || '|' || indexrelid::regclass FROM pg_index WHERE NOT indisvalid OR NOT indisready;
SELECT DISTINCT 'trgm index|' || current_database() || '|' || i.indexrelid::regclass || '|valid=' || i.indisvalid
  FROM pg_index i JOIN pg_opclass o ON o.oid = ANY (i.indclass::oid[])
 WHERE o.opcname IN ('gin_trgm_ops', 'gist_trgm_ops');
SQL
  done
  "${PSQL[@]}" -X -At -d postgres -c "SELECT 'NON-SCRAM login|' || rolname FROM pg_authid WHERE rolcanlogin AND rolpassword IS NOT NULL AND rolpassword NOT LIKE 'SCRAM-SHA-256\$%'"
}

hub_restic() {   # on: hub only. Mirrors scripts/bootstrap/bootstrap-hub.sh:286-300; the three values never leave the root shell.
  # repo URI: scripts/bootstrap/bootstrap-config.sh:97. Optional HUB_RESTIC_MOUNT=<host>:<container> for a restore target.
  sudo bash -c '
    set -euo pipefail
    mount="$1"; shift
    export AWS_ACCESS_KEY_ID="$(grep "^B2_KEY_ID=" /opt/fabrik/.env | cut -d= -f2-)"
    export AWS_SECRET_ACCESS_KEY="$(grep "^B2_APPLICATION_KEY=" /opt/fabrik/.env | cut -d= -f2-)"
    export RESTIC_PASSWORD="$(grep "^BACKREST_RESTIC_PASSWORD=" /opt/fabrik/.env | cut -d= -f2-)"
    export RESTIC_REPOSITORY="s3:https://s3.us-west-004.backblazeb2.com/vps1-ocoron-backups"
    exec docker run --rm -e AWS_ACCESS_KEY_ID -e AWS_SECRET_ACCESS_KEY -e RESTIC_PASSWORD -e RESTIC_REPOSITORY \
      ${mount:+-v "$mount"} restic/restic:0.18.1 "$@"
  ' _ "${HUB_RESTIC_MOUNT:-}" "$@"
}
```

The window directory holds every reading, dump and list the steps write. It is under `/opt/backups/`, so the
Backrest `postgres-dumps` plan carries it off the host (`docs/operations/disaster-recovery.md:45`):

```bash
# on: hub — at the start of the hub window, and in every later hub shell of the same window
PSQL=(sudo docker exec -i postgres-main psql -U postgres)
[ -s /opt/backups/pg18-window.ts ] || date -u +%Y%m%dT%H%MZ | sudo tee /opt/backups/pg18-window.ts >/dev/null
TS=$(cat /opt/backups/pg18-window.ts); W=/opt/backups/pg18-window-$TS
[ -d "$W" ] || sudo install -d -o "$USER" -m 700 "$W"
echo "window $TS → $W"
```

## 1. Pre-window probes

Run these on a normal day, at least 24 h before the hub window; they change nothing. Record the outputs in
`/opt/backups/pg18-probes/` (`P` below). U1 and U2 are the spec's open unknowns (spec § Open / blocking unknowns).

```bash
# on: hub
PSQL=(sudo docker exec -i postgres-main psql -U postgres)
P=/opt/backups/pg18-probes; [ -d "$P" ] || sudo install -d -o "$USER" -m 700 "$P"
```

### P1 — The backup schedules the window must avoid

The root cron runs `/opt/backups/pre-backup.sh` at 01:30 (`scripts/bootstrap/bootstrap-hub.sh:89`), and the four
Backrest plans run 02:00–03:30 (`docs/operations/disaster-recovery.md:43`). Backrest runs in `Europe/Istanbul`
(`infra/vps1/backrest/compose.yaml:13`); the cron runs in the host's zone — read both.

```bash
# on: hub
sudo crontab -u root -l | tee "$P/root-crontab.txt"
timedatectl | grep 'Time zone'
command -v jq >/dev/null || { echo "jq missing — sudo apt-get install -y jq"; }
sudo jq '.plans[] | {id, schedule}' /opt/backrest/config/config.json | tee "$P/backrest-schedules.json"
```

**Verify:** the window's start and end, converted to both zones, sit outside 01:30–03:30 — or hub step 1 comments the
01:30 line for the window (its conditional block).
**Rollback:** none — read-only.

### P2 — Disk headroom and the live database list with sizes (U1)

```bash
# on: hub
"${PSQL[@]}" -X -c "SELECT datname, pg_size_pretty(pg_database_size(datname)) AS size, datconnlimit FROM pg_database ORDER BY pg_database_size(datname) DESC" | tee "$P/databases.txt"
"${PSQL[@]}" -X -At -c "SELECT sum(pg_database_size(datname)) FROM pg_database" | tee "$P/cluster-bytes.txt"
df -h /var/lib/docker /opt | tee "$P/df.txt"
for db in $(dbs); do "${PSQL[@]}" -X -At -d "$db" -c "SELECT current_database() || '|' || extname || '|' || extversion FROM pg_extension ORDER BY 1"; done | tee "$P/extensions.txt"
pg_compat_checks | tee "$P/compat-16.txt"
```

**Verify:** the hub disk gate (§ 3) would pass today with margin; `compat-16.txt` has no `BLOCKER`/`INVALID`/`NON-SCRAM`
line (a blocker found now is fixed BEFORE the window, never inside it); `extensions.txt` names no extension the 18
image lacks (`vector` is absent from the image — spec § What exists today).
**Rollback:** none — read-only.

### P3 — `$PGPW` proven

The dump authenticates over TCP as the live superuser (spec § The delta › D1 step 3); prove the password now.

The password file lives in RAM (`/dev/shm`), never under `/opt` — `/opt/backups` is carried to B2 by the
`postgres-dumps` plan (`docs/operations/disaster-recovery.md:45`).

```bash
# on: hub
read -rsp 'postgres superuser password (not echoed): ' PGPW; echo
PGENV_DIR=$(mktemp -d /dev/shm/pg18.XXXXXX); PGENV="$PGENV_DIR/pgpass.env"
( umask 077; printf 'PGPASSWORD=%s\n' "$PGPW" > "$PGENV" ); unset PGPW
sudo docker run --rm --network fabrik --env-file "$PGENV" postgres:18.6-alpine psql -h postgres-main -U postgres -XAtc 'SELECT 1'
shred -u "$PGENV"; rmdir "$PGENV_DIR"
```

**Verify:** prints `1`; `ls /dev/shm/pg18.*` finds nothing afterwards.
**Rollback:** none — read-only; a wrong password means the window does not open until the right one is found.

### P4 — `pre-backup.sh` read (U2)

`/opt/backups/pre-backup.sh` is not in the repo (spec U2). Read its retention and its per-database loop
(`docs/operations/deployment.md:535-540` shows the expected loop shape; per-DB Backrest plans read
`/opt/backups/postgres/<db>/`, `docs/operations/deployment.md:514`).

```bash
# on: hub
sudo cat /opt/backups/pre-backup.sh | tee "$P/pre-backup.sh.txt"
sudo grep -nE 'find|-mtime|rm |delete|pg_dumpall|pg_dump' /opt/backups/pre-backup.sh
```

**Verify:** no retention line can delete anything under `/opt/backups/pg18-window-*/` (a `find /opt/backups … -delete`
without a name filter can) — if one can, the window keeps its dumps elsewhere under `/opt/backups/` that the line
cannot reach, and hub step 8.8's 7-day hold names that place.
**Rollback:** none — read-only.

### P5 — The hub compose against the repo

Hub step 4 writes `/opt/postgres/compose.yaml` from the repo's PG18 file (`infra/vps1/postgres/compose.yaml`). The
live 16 file must differ from it ONLY in the image, the mount and the volume key.

```bash
# on: wsl, in the fleet checkout that carries this runbook
ssh vps 'sudo cat /opt/postgres/compose.yaml' > /tmp/pg16-live-compose.yaml
diff /tmp/pg16-live-compose.yaml infra/vps1/postgres/compose.yaml
```

**Verify:** every `<`/`>` line is the `image:` line, the `- postgres-data:/var/lib/postgresql/data` /
`- postgres18-data:/var/lib/postgresql` mount line, or the top-level volume key; any other difference is folded
into `infra/vps1/postgres/compose.yaml` (and so into hub step 4's block) BEFORE the window.
**Rollback:** none — read-only.

### P6 — Pool sizes against `max_connections`

```bash
# on: hub
"${PSQL[@]}" -X -At -c "SHOW max_connections" | tee "$P/max-connections.txt"
"${PSQL[@]}" -X -c "SELECT datname, usename, count(*) FROM pg_stat_activity WHERE backend_type = 'client backend' GROUP BY 1, 2 ORDER BY 3 DESC" | tee "$P/connections.txt"
for c in $(sudo docker ps --format '{{.Names}}'); do
  sudo docker inspect -f '{{range .Config.Env}}{{println .}}{{end}}' "$c" | grep -E '^[A-Z_]*(POOL|MAX_CONN|MAX_OVERFLOW)[A-Z_]*=' | sed "s/^/$c: /"
done | tee "$P/pool-env.txt"
```

**Verify:** the sum of the declared pool sizes (plus overflow) and the peak in `connections.txt` stays below
`max_connections` with room for the superuser and the exporter; hub step 5 re-checks it on 18.
**Rollback:** none — read-only.

### P7 — Backrest's `docker-volumes` plan scope

The spec calls the plan "an explicit volume list" (spec § What exists today); the repo's inventory says its scope is
`/var/lib/docker/volumes/` with excludes (`docs/operations/hub-restore-inventory.md:112`), and Backrest mounts the
whole directory (`infra/vps1/backrest/compose.yaml:25`). Read which it is now; hub step 8.2 re-reads it.

```bash
# on: hub
sudo jq '.plans[] | select(.id == "docker-volumes") | {id, paths, excludes, iexcludes, retention}' /opt/backrest/config/config.json | tee "$P/docker-volumes-plan.json"
sudo jq '.plans[] | select(.id == "postgres-dumps") | {id, paths, retention}' /opt/backrest/config/config.json | tee "$P/postgres-dumps-plan.json"
```

**Verify:** both plans print; their `paths`, `excludes` and `retention` are recorded (an empty output means the plan id
or the config path differs — find the real one in the Backrest UI at `backup.vps1.ocoron.com`,
`infra/vps1/backrest/compose.yaml:40`, before the window).
**Rollback:** none — read-only.

## 2. WSL window (D2)

The rehearsal (spec § The delta › D2), run before the hub window. WSL runs native apt PostgreSQL 16 on 5432 with one
dedicated `{project_name}_dev` database per project (`.windsurf/rules/core/25-data-postgres.md:37`; the name is built
at `scripts/create_pg_dev_db.sh:12`). Before it opens: appendix A1 has been sent
and brand-identiy-creator's D7 branch is ready (spec § The delta › D7).

```bash
# on: wsl — every WSL-window shell
PSQL=(sudo -u postgres psql -p 5432)
WW=$HOME/pg18-wsl; mkdir -p "$WW"; [ -s "$WW/ts" ] || date -u +%Y%m%dT%H%MZ > "$WW/ts"; WTS=$(cat "$WW/ts")
command -v pg_lsclusters >/dev/null || echo "postgresql-common missing — stop"
```

### WSL step 0 — Extension inventory

```bash
# on: wsl
for db in $(dbs); do "${PSQL[@]}" -X -At -d "$db" -c "SELECT current_database() || '|' || extname || '|' || extversion FROM pg_extension ORDER BY 1"; done | tee "$WW/extensions-16.txt"
grep '|pg_uuidv7|' "$WW/extensions-16.txt" | grep -v '^brand_identiy_creator_dev|' || echo "no pg_uuidv7 outside brand-identiy-creator"
grep '|vector|' "$WW/extensions-16.txt" | cut -d'|' -f1 | tee "$WW/vector-dbs.txt"
```

**Verify:** the second command prints `no pg_uuidv7 outside brand-identiy-creator`; any other `pg_uuidv7` row is a
KILL until handled (`pg_upgradecluster` fails on it, spec D2 step 0). `vector-dbs.txt` names the databases
`postgresql-18-pgvector` must serve.
**Rollback:** none — read-only.

### WSL step 1 — PGDG repository and the four packages

PGDG's `postgresql-common` replaces Ubuntu's and its `16.15-1.pgdg24.04+1` sorts newer than the installed Ubuntu build,
so the 16 pair moves to PGDG in the same step and the 16 cluster restarts once (spec D2 step 1). Repository setup per
<https://www.postgresql.org/download/linux/ubuntu/> (manual configuration, signed-by key).

```bash
# on: wsl
if ! grep -rqs 'apt.postgresql.org' /etc/apt/sources.list.d/; then
  sudo install -d /usr/share/postgresql-common/pgdg
  sudo curl -fsSo /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc https://www.postgresql.org/media/keys/ACCC4CF8.asc
  echo "deb [signed-by=/usr/share/postgresql-common/pgdg/apt.postgresql.org.asc] https://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" | sudo tee /etc/apt/sources.list.d/pgdg.list
fi
sudo apt-get update
sudo apt-get install -y postgresql-18 postgresql-18-pgvector postgresql-16 postgresql-16-pgvector
pg_lsclusters
```

**Verify:** `pg_lsclusters` shows `16 main 5432 online` and `18 main 5433`; `dpkg -l postgresql-16 postgresql-16-pgvector
| grep pgdg` lists both.
**Rollback:** `sudo apt-get remove postgresql-18 postgresql-18-pgvector` (binaries only — the 16 cluster's data is untouched;
the 16 pair stays on PGDG's build, which serves the same data directory).

### WSL step 2 — Drop the auto-created, EMPTY 18/main

The install creates `18/main` on 5433; `pg_upgradecluster` refuses while it exists (spec D2 step 2). The guard reads
the cluster's REAL port from `pg_lsclusters`, refuses outright when 18/main is on 5432 (after step 3 it IS the upgraded
cluster), refuses when it holds any non-template database (after step 6 it holds the upgraded copies on 5433), and
treats a failed query as a refusal, never as "empty".

**Operator's explicit word:** required before the drop block — it removes ONLY the EMPTY cluster the step-1 install
created; every other state is refused by the guard and nothing is dropped.

```bash
# on: wsl
line=$(pg_lsclusters -h | awk '$1 == 18 && $2 == "main"')
if [ -z "$line" ]; then
  echo "no 18/main — nothing to drop"
else
  port=$(echo "$line" | awk '{print $3}')
  if [ "$port" = 5432 ]; then
    echo "REFUSED: 18/main is on 5432 — it is the upgraded cluster; nothing dropped"
  elif ! n=$(sudo -u postgres psql -p "$port" -X -At -v ON_ERROR_STOP=1 -c "SELECT count(*) FROM pg_database WHERE datname NOT IN ('postgres', 'template0', 'template1')"); then
    echo "REFUSED: could not query 18/main on port $port (start it with: sudo pg_ctlcluster 18 main start); nothing dropped"
  elif [ "$n" != 0 ]; then
    echo "REFUSED: 18/main on port $port holds $n databases; nothing dropped"
  else
    if sudo pg_dropcluster 18 main --stop; then echo "dropped the empty 18/main (port $port)"; else echo "pg_dropcluster FAILED — read its error above"; fi
  fi
fi
pg_lsclusters
```

**Verify:** the block prints `dropped the empty 18/main …` or `no 18/main`; `pg_lsclusters` lists `16 main 5432 online`
and no 18 cluster. Any `REFUSED` line stops the window at this step.
**Rollback:** `sudo pg_createcluster 18 main` recreates the empty cluster (nothing else needs it).

### WSL step 2a — brand-identiy-creator's dev database out of the way

Its hand-built `pg_uuidv7` has no 18 build here (spec D2 step 2a, D7). Take a data-only dump (minus the two tables its
migrations populate) and a full `-Fc` copy, outside the repo, then drop the database. A dump counts as taken only when
`pg_dump` EXITED 0 — its `.ok` marker; pg_dump 16.15 ends a plain dump with `\unrestrict <key>`, so a "dump complete"
trailer grep is not a test. The `-Fc` copy is also read in full (`pg_restore -f /dev/null`), which a truncated
archive fails.

**Operator's explicit word:** required before `dropdb` — both `.ok` markers must exist and the full read must pass first.

```bash
# on: wsl
B=brand_identiy_creator_dev; D1="$WW/$B-data-$WTS.sql"; D2="$WW/$B-full-$WTS.dump"
if "${PSQL[@]}" -X -At -d postgres -c "SELECT 1 FROM pg_database WHERE datname = '$B'" | grep -q 1; then
  [ -f "$D1.ok" ] || { sudo -u postgres pg_dump -p 5432 --data-only --exclude-table=alembic_version --exclude-table=worker_pool_state "$B" > "$D1" && touch "$D1.ok"; }
  [ -f "$D2.ok" ] || { sudo -u postgres pg_dump -p 5432 -Fc "$B" > "$D2" && touch "$D2.ok"; }
  if [ -f "$D1.ok" ] && [ -f "$D2.ok" ] && pg_restore -f /dev/null < "$D2"; then
    sudo -u postgres dropdb -p 5432 "$B"
  else
    echo "REFUSED: a dump is missing its .ok marker or failed the full read — $B NOT dropped"
  fi
fi
"${PSQL[@]}" -X -At -d postgres -c "SELECT count(*) FROM pg_database WHERE datname = '$B'"
```

**Verify:** prints `0`; both `.ok` markers exist; no `REFUSED` line.
**Rollback:** `sudo -u postgres pg_restore -p 5432 --create -d postgres < "$D2"` (stdin, because the postgres user cannot
read a 0750 home; on 16, where the extension exists).

### WSL step 3 — Stop the local writers, then `pg_upgradecluster`

The stop list (spec D2 step 3 plus the writers the grounding found):

- **session-recall** — every Claude Code session spawns its stdio MCP `server.py`, which self-heals freshness, i.e.
  writes (`docs/workstation/session-recall.md:162`); and the shell-open hook runs its incremental reindex
  (`scripts/wsl_startup_hook.sh:231`). Close every Claude Code session and open no new shell until step 4.
- **youtube financials** — the Monday cron `update_financials.py --write` (`docs/operations/wsl-environment.md:52`),
  and the youtube services `start_all.sh ensure` keeps alive every 5 minutes (`docs/operations/wsl-environment.md:65`).
- **trade-intelligence GTIP refresh** — the 05:30 cron `run_refresh_once.sh` (`docs/operations/wsl-environment.md:66`).
- any local watchdog or cost-ledger writer to `fabrik_analytics` (spec D2 step 3).

The whole user crontab is commented for the window with a marker, so step 6 / step 4's restore is exact.

```bash
# on: wsl — close every Claude Code session first
[ -s "$WW/crontab.before" ] || crontab -l > "$WW/crontab.before"
crontab -l | sed -E 's/^([^#].*)$/#PG18# \1/' | crontab -
pgrep -af 'update_financials\.py|run_refresh_once\.sh|ingest\.reindex|session-recall.*server\.py|start_all\.sh' || echo "no local writer running"
"${PSQL[@]}" -X -At -d postgres -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE backend_type = 'client backend' AND pid <> pg_backend_pid()" >/dev/null
"${PSQL[@]}" -X -At -d postgres -c "SELECT count(*) FROM pg_stat_activity WHERE backend_type = 'client backend' AND pid <> pg_backend_pid()"
pg_manifest "$WW/manifest-16"
if ! pg_lsclusters -h | awk '$1 == 18 && $2 == "main" && $3 == 5432' | grep -q .; then sudo pg_upgradecluster -v 18 16 main; fi
pg_lsclusters; cat /etc/postgresql/16/main/start.conf | grep -v '^#'
```

**Verify:** `no local writer running`, then `0` client backends; `pg_lsclusters` shows `18 main 5432 online` and
`16 main 5433 down`; 16's `start.conf` reads `manual`. On a failed upgrade `pg_upgradecluster` drops the new cluster and
restarts 16 itself — fix the cause and re-run this block.
**Rollback:** WSL step 6's procedure; the user crontab comes back with `crontab "$WW/crontab.before"`.

### WSL step 4 — Verify every database on 18, then every project's suite

The D1 manifest method on WSL, `fabrik_analytics` and session-recall's database included (spec D2 step 4), with the
§ Compatibility checks the spec runs "once on WSL". brand-identiy-creator's database is recreated from its rewritten
migrations (D7) once its branch is merged.

```bash
# on: wsl
pg_manifest --retake "$WW/manifest-18"
manifest_diff "$WW/manifest-16" "$WW/manifest-18"
pg_compat_checks | tee "$WW/compat-18.txt" | grep -E '^(BLOCKER|INVALID|NON-SCRAM)' || echo "compat: clean"
"${PSQL[@]}" -X -At -d postgres -c "SELECT version(), current_setting('server_version_num'), uuidv7() IS NOT NULL"
grep -E '^setting\|(old_snapshot_threshold|db_user_namespace|ssl_ecdh_curve)\|' "$WW/manifest-16/cluster.txt" || echo "no removed/renamed setting in use"
# brand-identiy-creator, after its D7 branch merged: recreate and migrate on 18; reload the data dump only if its rows are not regenerable
"${PSQL[@]}" -X -At -d postgres -c "SELECT 1 FROM pg_database WHERE datname = 'brand_identiy_creator_dev'" | grep -q 1 || sudo -u postgres createdb -p 5432 brand_identiy_creator_dev
# every project suite against 18, logs per project; driver versions measured too (spec pg-48)
for p in /opt/*/; do
  [ -x "$p/.venv/bin/python" ] && [ -d "$p/tests" ] || continue
  n=$(basename "$p")
  "$p/.venv/bin/python" -m pip list 2>/dev/null | grep -iE '^(asyncpg|psycopg|psycopg2|psycopg-binary|sqlalchemy) ' > "$WW/drivers-$n.txt"
  ( cd "$p" && timeout 1800 .venv/bin/python -m pytest -q -x ) > "$WW/suite-$n.log" 2>&1 && echo "PASS $n" || echo "FAIL $n"
done | tee "$WW/suites.txt"
```

**Verify:** `manifest_diff` prints `manifest_diff: … == …` (brand-identiy-creator's database was dropped in step 2a,
before step 3's reading, so no diff is expected); `compat: clean`; version `18.x` with `server_version_num >= 180000`; `no removed/renamed
setting in use`; every `FAIL` line in `suites.txt` is read and traced — a failure caused by 18 is a step 5 KILL, a
failure that also fails on 16 is recorded and does not block.
**Rollback:** WSL step 6's procedure.

### WSL step 5 — KILL check

A WSL verification that fails stops the hub window until fixed (D-612's KILL clause, spec D2 step 5).

```bash
# on: wsl
manifest_diff "$WW/manifest-16" "$WW/manifest-18" >/dev/null; echo "manifest rc=$?"
grep -c '^FAIL' "$WW/suites.txt"
crontab "$WW/crontab.before" && crontab -l | grep -c '#PG18#'
```

**Verify:** `manifest rc=0`, the `FAIL` count is the 16-baseline count, and the
crontab is restored (`0` markers). Then — and only then — schedule the hub window within 7 days.
**Rollback:** WSL step 6's procedure.

### WSL step 6 — Parity gap, bounded to 7 days

Between the windows WSL runs 18 and production 16. Past 7 days without a hub window, WSL rolls back (spec D2 step 6):
16 back on 5432, 18 kept on 5433 for brand-identiy-creator alone (its D7 code calls native `uuidv7()`), whose dev DSN is
repointed to 5433. Dev writes made on 18 in the gap by every other project are lost (dev data).

```bash
# on: wsl — ONLY when day 7 passes with no hub window scheduled
sudo pg_ctlcluster 18 main stop || true; sudo pg_ctlcluster 16 main stop || true
sudo sed -i -E 's/^port = [0-9]+/port = 5432/' /etc/postgresql/16/main/postgresql.conf
sudo sed -i -E 's/^port = [0-9]+/port = 5433/' /etc/postgresql/18/main/postgresql.conf
echo auto | sudo tee /etc/postgresql/16/main/start.conf >/dev/null
sudo pg_ctlcluster 16 main start; sudo pg_ctlcluster 18 main start
pg_lsclusters
```

**Verify:** `16 main 5432 online` and `18 main 5433 online`; brand-identiy-creator's dev DSN names port 5433 (its own
repo's change, carried by its request).
**Rollback:** reverse the two `port` lines and set 16's `start.conf` to `manual` — the step-3 state.

## 3. Hub window (D1)

Gate 2 class (production data). Infra, the merge owner, is on call for the window and merges the DR-chain branch at
step 8.3 (spec § Lifecycle step 4). Paste the § 0 helpers and the window-directory block first.

### Hub disk gate

The hub (108 GB, `docs/infrastructure/vps-complete-inventory.md:108`) holds the old volume, the new one, the
`pg_dumpall` file, the per-database dumps and the nightly dumps at once through the soak. The window opens only with
free space of at least four times the cluster size plus 10 GB (spec D1 › Disk gate).

```bash
# on: hub
size=$("${PSQL[@]}" -X -At -c "SELECT sum(pg_database_size(datname)) FROM pg_database")
need=$(( 4 * size + 10 * 1024 * 1024 * 1024 ))
for m in /var/lib/docker /opt; do
  avail=$(df -B1 --output=avail "$m" | tail -n 1)
  [ "$avail" -ge "$need" ] && echo "PASS $m avail=$avail need=$need" || echo "FAIL $m avail=$avail need=$need"
done | tee "$W/disk-gate.txt"
```

**Verify:** both lines read `PASS`. The second copy of every dump goes OFF the host (step 3's Backrest snapshot), never the
same disk.
**Rollback:** none — read-only; a `FAIL` means the window does not open.

### Hub step 1 — Notice, silence, freeze deploys and writes

The archived plan's operator steps the spec left implicit — a Telegram maintenance notice and an alert silence
(`docs/development/plans/archived/2026-05-25-postgresql-18-upgrade.md:105`) — open the freeze. Then, in the spec's
order (D1 step 1): the WSL MCP tunnel (it reaches the HUB cluster, `scripts/wsl_startup_hook.sh:227`), the
`fabrik-compose-boot` unit (it runs `docker compose up -d` for every `/opt/*/compose.yaml` on boot,
`scripts/bootstrap/bootstrap-hub.sh:1410`), every `*-watchdog` sidecar FIRST (a sidecar restarts its main container
when it exits — its container-state check, `docs/infrastructure/vps-complete-inventory.md:733`; one sidecar exists
today, `:742`), then every container that reaches `postgres-main`, spokes included — glitchtip and the exporter log in
as the superuser, so stopping them is the only thing that keeps them out. Then the freeze inside the database.

The shell-open hook re-opens the tunnel on the FIRST shell of every UTC day: its daily block runs only when
`/tmp/.fabrik_daily_<UTC date>` is absent (`scripts/wsl_startup_hook.sh:62`, `:134-135`), and the tunnel line is in
that block (`:227`). The block below pre-creates the lock for the window's dates — which also skips that day's daily
pipeline on WSL — and records which locks it created, so 8.6 removes exactly those. The tunnel is re-checked before
step 7 and before 8.4.

```bash
# on: wsl — the deploy freeze for agents, the tunnel, and the hook's daily lock
HW=$HOME/pg18-hub-window; mkdir -p "$HW"
python3 scripts/mail.py send --to fabrik --broadcast --ack no --kind request <<'EOF'
DEPLOY FREEZE — PostgreSQL 18 hub window in progress. No `fabrik apply`, no compose up on vps1/vps2/vps3, no writes to postgres-main until the all-clear. Runbook: docs/operations/postgres-major-upgrade-runbook.md § 3.
EOF
for d in "$(date -u +%Y%m%d)" "$(date -u -d '+1 day' +%Y%m%d)"; do
  [ -e "/tmp/.fabrik_daily_$d" ] || { touch "/tmp/.fabrik_daily_$d"; echo "/tmp/.fabrik_daily_$d" >> "$HW/locks-created.txt"; }
done
pkill -f '15432:10\.99\.0\.1:[5]432' || true
pgrep -af '15432:10\.99\.0\.1:[5]432' || echo "tunnel stopped"
```

```bash
# on: hub — notice and silence (Apprise route: docs/infrastructure/vps-complete-inventory.md:512; alertmanager: infra/vps1/monitoring/compose.yaml:76)
sudo docker exec prometheus wget -qO- --post-data "title=Maintenance window&body=PostgreSQL 18 upgrade on vps1 ($TS): database-backed services are DOWN until the all-clear." http://apprise:8000/notify/alerts
window_silences() { sudo docker exec alertmanager amtool silence query --alertmanager.url=http://localhost:9093 -o json | jq -r --arg c "pg18-window-$TS" '.[] | select(.comment == $c and .status.state == "active") | .id'; }
window_silences | grep -q . || \
  sudo docker exec alertmanager amtool silence add --alertmanager.url=http://localhost:9093 --duration=6h --author=operator --comment="pg18-window-$TS" 'alertname=~".+"'
OVERLAP=no   # set to yes when P1 showed the window overlaps 01:30–03:30; every rollback path restores the crontab
if [ "$OVERLAP" = yes ]; then
  [ -s "$W/root-crontab.before" ] || sudo crontab -u root -l > "$W/root-crontab.before"
  sudo crontab -u root -l | sed -E 's|^([^#].*pre-backup\.sh.*)$|#PG18# \1|' | sudo crontab -u root -
fi
sudo systemctl disable --now fabrik-compose-boot.service
sudo docker ps --format '{{.Names}}' | grep -E -- '-watchdog$' >> "$W/stopped-watchdogs.txt"; sort -u -o "$W/stopped-watchdogs.txt" "$W/stopped-watchdogs.txt"
xargs -r sudo docker stop < "$W/stopped-watchdogs.txt"
for c in $(sudo docker ps --format '{{.Names}}'); do
  [ "$c" = postgres-main ] && continue
  sudo docker inspect -f '{{range .Config.Env}}{{println .}}{{end}}' "$c" | grep -q 'postgres-main' && echo "$c"
done >> "$W/stopped-services.txt"
sort -u -o "$W/stopped-services.txt" "$W/stopped-services.txt"; cat "$W/stopped-services.txt"
xargs -r sudo docker stop < "$W/stopped-services.txt"
```

```bash
# on: wsl (ssh to vps2/vps3) — spoke services reach the hub at 10.99.0.1 (src/fabrik/orchestrator/infrastructure.py:134-152); the lists live on WSL in $HW
HW=$HOME/pg18-hub-window; mkdir -p "$HW"
for h in vps2 vps3; do
  ssh "$h" 'for c in $(sudo docker ps --format "{{.Names}}"); do sudo docker inspect -f "{{range .Config.Env}}{{println .}}{{end}}" "$c" | grep -q "10\.99\.0\.1" && echo "$c"; done' >> "$HW/stopped-$h.txt"
  sort -u -o "$HW/stopped-$h.txt" "$HW/stopped-$h.txt"
  xargs -r ssh "$h" sudo docker stop < "$HW/stopped-$h.txt"
done
```

The freeze inside the database. First the limits; then every client still connected is, by construction, a writer
the stop list missed — record each one (address, user, application, database), map its address to a container on
the `fabrik` network, and report it BEFORE terminating; then watch the count for a minute, not one moment.

```bash
# on: hub — never ALLOW_CONNECTIONS false: pg_dumpall silently skips such a database
[ -s "$W/pre-freeze-connlimits.txt" ] || "${PSQL[@]}" -X -At -c "SELECT datname || '|' || datconnlimit FROM pg_database ORDER BY 1" > "$W/pre-freeze-connlimits.txt"
"${PSQL[@]}" -X -v ON_ERROR_STOP=1 -f - <<'SQL'
SET default_transaction_read_only = off;
SELECT format('ALTER DATABASE %I CONNECTION LIMIT 0', datname) FROM pg_database WHERE datname NOT IN ('postgres', 'template0', 'template1') \gexec
ALTER SYSTEM SET default_transaction_read_only = on;
SELECT pg_reload_conf();
SQL
"${PSQL[@]}" -X -At -c "SELECT coalesce(host(client_addr), 'local') || '|' || usename || '|' || coalesce(application_name, '') || '|' || datname FROM pg_stat_activity WHERE backend_type = 'client backend' AND pid <> pg_backend_pid()" | tee -a "$W/clients-at-freeze.txt"
sudo docker network inspect fabrik -f '{{range .Containers}}{{.IPv4Address}} {{.Name}}{{println}}{{end}}' | sed -E 's#/[0-9]+##' > "$W/fabrik-net-ips.txt"
while IFS='|' read -r addr user app db; do
  c=$(awk -v a="$addr" '$1 == a {print $2}' "$W/fabrik-net-ips.txt")
  echo "WRITER NOT ON THE STOP LIST: addr=$addr container=${c:-unknown (mesh 10.99.0.x = a spoke; local = a docker exec session)} user=$user app=$app db=$db"
done < "$W/clients-at-freeze.txt"
"${PSQL[@]}" -X -At -c "SELECT count(pg_terminate_backend(pid)) FROM pg_stat_activity WHERE backend_type = 'client backend' AND pid <> pg_backend_pid()"
for i in $(seq 12); do "${PSQL[@]}" -X -At -c "SELECT count(*) FROM pg_stat_activity WHERE backend_type = 'client backend' AND pid <> pg_backend_pid()"; sleep 5; done | sort | uniq -c
```

**Verify:** `sudo docker ps --format '{{.Names}}' | grep -Fxf "$W/stopped-services.txt"` and the same for
`stopped-watchdogs.txt` print nothing (none came back); `systemctl is-enabled fabrik-compose-boot` reads `disabled`;
every `WRITER NOT ON THE STOP LIST` line is traced to its container and that container is stopped and appended to
`stopped-services.txt` (or the spoke list) before going on; the one-minute watch prints only `12 0`;
`"${PSQL[@]}" -X -At -c "SHOW default_transaction_read_only"` prints `on`; `pre-freeze-connlimits.txt` holds the
ORIGINAL limits (it is written once, before any limit changes). The `postgres` database is left outside the
`CONNECTION LIMIT 0` freeze on purpose: it is the admin database every superuser session (this runbook's included)
connects to, no service's DSN names it (spec § What exists today › Databases), and `default_transaction_read_only`
binds the superuser in it too.
**Rollback:** in a session that first runs `SET default_transaction_read_only = off`: `ALTER SYSTEM RESET
default_transaction_read_only` + `SELECT pg_reload_conf()`; restore the limits with step 8.1's block; restore the root
crontab and the glitchtip compose (`[ -s "$W/root-crontab.before" ] && sudo crontab -u root "$W/root-crontab.before";
[ -s "$W/glitchtip-compose.yaml.orig" ] && sudo cp -p "$W/glitchtip-compose.yaml.orig" /opt/glitchtip/compose.yaml`);
start the lists back (`xargs -r sudo docker start < "$W/stopped-services.txt"`, then the watchdogs, then the spokes'
lists in `$HW`); `sudo systemctl enable fabrik-compose-boot.service`; restart the tunnel and remove the created locks
(step 8.6); expire the silence and post an all-clear.

### Hub step 2 — The manifest on 16

Exact `count(*)` and a content hash of every table in every database, sequences, extensions, database
encoding/collation/locale/owner, role attributes and `rolpassword` prefix, `pg_auth_members`, `pg_default_acl`, table
and schema ACLs, the non-default server settings, `pg_hba`/`pg_ident` rules (spec D1 step 2) — the § 0 helpers — plus
copies of the three configuration files a dump does not carry.

```bash
# on: hub
pg_manifest "$W/manifest-16-a"
mkdir -p "$W/conf16"
for f in postgresql.auto.conf pg_hba.conf pg_ident.conf; do
  [ -s "$W/conf16/$f" ] || sudo docker exec postgres-main sh -c "cat \"\$PGDATA/$f\"" > "$W/conf16/$f"
done
ls -l "$W/conf16"
```

**Verify:** `pg_manifest` prints its `manifest … files, … tables` line (one `db-*.txt` per database `dbs` lists,
plus `cluster.txt` and the `COMPLETE` marker — a `MANIFEST FAILED` line moves the partial reading aside); the three conf copies are
non-empty; `grep -c '^setting|default_transaction_read_only|on|' "$W/manifest-16-a/cluster.txt"` prints `1` (the
freeze is in the reading).
**Rollback:** none — read-only.

### Hub step 3 — Dump with the 18 client, bracket it, ship it off the host, stop 16

The PG18 client dumps over TCP as the live superuser (pg-06; the image trusts only its local socket, so a TCP client
needs the password — spec D1 step 3). The password file is created fresh in RAM (`/dev/shm`) on every run — never under
`/opt`, which the `postgres-dumps` plan and the 01:30 dump carry to B2 — proven with a test connection, deleted at once
when the proof fails (so a typo never sticks), and shredded right after the last dump. A dump counts as taken only when
its `pg_dump`/`pg_dumpall` EXITED 0 (the `.ok` marker); every `-Fc` dump is also read in full (`pg_restore -f
/dev/null`), which a truncated archive fails — `pg_restore -l` does not. When any dump is (re)taken, the bracketing
second manifest is retaken too.

```bash
# on: hub
F="$W/pg16-final-$TS.sql"; need=0
[ -f "$F.ok" ] || need=1
for db in $(dbs); do [ -f "$W/pg16-final-$TS-$db.dump.ok" ] || need=1; done
if [ "$need" = 1 ]; then
  read -rsp 'postgres superuser password (not echoed): ' PGPW; echo
  PGENV_DIR=$(mktemp -d /dev/shm/pg18.XXXXXX); PGENV="$PGENV_DIR/pgpass.env"
  ( umask 077; printf 'PGPASSWORD=%s\n' "$PGPW" > "$PGENV" ); unset PGPW
  if ! sudo docker run --rm --network fabrik --env-file "$PGENV" postgres:18.6-alpine psql -h postgres-main -U postgres -XAtc 'SELECT 1' | grep -qx 1; then
    shred -u "$PGENV"; rmdir "$PGENV_DIR"; echo "password REJECTED — nothing dumped; re-run this block"
  else
    [ -f "$F.ok" ] || { sudo docker run --rm --network fabrik --env-file "$PGENV" postgres:18.6-alpine pg_dumpall -h postgres-main -U postgres > "$F" && touch "$F.ok"; }
    for db in $(dbs); do
      D="$W/pg16-final-$TS-$db.dump"
      [ -f "$D.ok" ] || { sudo docker run --rm --network fabrik --env-file "$PGENV" postgres:18.6-alpine pg_dump -h postgres-main -U postgres -Fc "$db" > "$D" && touch "$D.ok"; }
    done
    shred -u "$PGENV"; rmdir "$PGENV_DIR"
    pg_manifest --retake "$W/manifest-16-b"
  fi
fi
for d in "$W"/pg16-final-"$TS"-*.dump; do
  [ -f "$d.ok" ] && sudo docker run --rm -i postgres:18.6-alpine pg_restore -f /dev/null < "$d" || echo "BAD DUMP $d"
done
[ -s "$W/manifest-16-b/COMPLETE" ] || pg_manifest "$W/manifest-16-b"   # an interrupted run: 16 is still up here
manifest_diff "$W/manifest-16-a" "$W/manifest-16-b"
```

Now trigger a manual run of the Backrest `postgres-dumps` plan (Backrest UI, `backup.vps1.ocoron.com` → Plans →
`postgres-dumps` → Backup now) and confirm the dump is in the snapshot, then stop 16:

```bash
# on: hub
hub_restic snapshots --tag plan:postgres-dumps --latest 1
hub_restic ls latest --tag plan:postgres-dumps "$W" | grep -cE "pg16-final-$TS(-.*\.dump|\.sql)$"
sudo docker stop postgres-main
```

**Verify:** `ls "$W"/*.ok | wc -l` equals 1 + the number of databases (every dump exited 0); the full-read loop prints
no `BAD DUMP` line; `ls /dev/shm/pg18.*` finds nothing (the password file is gone); `manifest_diff` prints
`manifest-16-a == manifest-16-b` (the dump is bracketed by two identical readings); the restic count equals 1 + the number of databases; `sudo docker inspect -f '{{.State.Running}}'
postgres-main` prints `false`.
**Rollback:** `sudo docker start postgres-main`, then hub step 1's rollback.

### Hub step 4 — Swap the container to 18 on a new volume

`docker volume create` first — the compose declares its volume `external: true` (`infra/vps1/postgres/compose.yaml:25-27`).
The 18 image refuses any volume at `/var/lib/postgresql/data` (pg-36), so the mount moves to `/var/lib/postgresql`
(PGDATA `/var/lib/postgresql/18/docker`, pg-35). The old `postgres-data` volume is untouched. From here to step 8.4 the 18 cluster runs WITHOUT
`default_transaction_read_only` (a fresh cluster; the flag is not ported): it is protected only by the dump-carried
`CONNECTION LIMIT 0` and the stopped containers, so nothing but a superuser session can write — keep it that way. The block writes the
repo's file verbatim (`infra/vps1/postgres/compose.yaml:1-30`; P5 proved the live file differs only there).

```bash
# on: hub
sudo docker volume inspect postgres18-data >/dev/null 2>&1 || sudo docker volume create postgres18-data
[ -s "$W/compose.yaml.pg16" ] || sudo cp -p /opt/postgres/compose.yaml "$W/compose.yaml.pg16"
sudo tee /opt/postgres/compose.yaml >/dev/null <<'YAML'
services:
  postgres-main:
    image: postgres:18.6-alpine
    platform: linux/amd64
    container_name: postgres-main
    restart: unless-stopped
    env_file: .env
    volumes:
    - postgres18-data:/var/lib/postgresql
    networks:
    - fabrik
    deploy:
      resources:
        limits:
          memory: 2G
    healthcheck:
      test:
      - CMD-SHELL
      - pg_isready -U postgres
      interval: 30s
      timeout: 5s
      retries: 3
    ports:
    - 10.99.0.1:5432:5432
volumes:
  postgres18-data:
    external: true
networks:
  fabrik:
    external: true
YAML
(cd /opt/postgres && sudo docker compose up -d)
for i in $(seq 60); do sudo docker exec postgres-main pg_isready -U postgres -q && break; sleep 2; done
```

**Verify:** `"${PSQL[@]}" -X -At -c "SELECT current_setting('server_version') || '|' || current_setting('data_directory') || '|' || current_setting('data_checksums')"`
prints `18.6|/var/lib/postgresql/18/docker|on`; `sudo docker inspect -f '{{range .Mounts}}{{.Name}}:{{.Destination}} {{end}}' postgres-main`
prints `postgres18-data:/var/lib/postgresql`; `sudo docker volume inspect postgres-data` still succeeds.
**Rollback:** step 7's one-step rollback (nothing was written to 18).

### Hub step 5 — Restore into the empty 18 cluster and port the server configuration

Without `ON_ERROR_STOP`, stderr captured: exactly one error is allowed — `role "postgres" already exists` (spec D1
step 5). The dump carries step 1's `CONNECTION LIMIT 0`, which stays until step 8.1. Then port every non-default
setting from `postgresql.auto.conf` — except step 1's own `default_transaction_read_only` and the parameters PG17
removed (`old_snapshot_threshold`, `db_user_namespace`; pg-08, pg-10), with `ssl_ecdh_curve` renamed `ssl_groups`
(pg-30) — and every `pg_hba`/`pg_ident` rule, check `max_connections` against P6, then `ANALYZE`. The settings are
ported FAITHFULLY: the 16 cluster's own `postgresql.auto.conf` lines (kept in `$W/port-auto.conf`) are appended to
the 18 one exactly once — a FILE marker, `$W/port-auto.applied`, records the append, because any `ALTER SYSTEM` rewrites
`postgresql.auto.conf` and strips comments, so a comment inside it cannot be the guard — and the 18 file is saved first
to `$W/auto18.orig`. A list setting
(`shared_preload_libraries`, `search_path`, `*_preload_libraries`, `temp_tablespaces`) keeps its list form — re-issuing
it as `ALTER SYSTEM SET x = 'a, b'` would make it ONE item and 18 would refuse to start. `pg_file_settings` is read for
errors before the restart.

Edits made by hand to the 16 cluster's `postgresql.conf` (not `postgresql.auto.conf`) are NOT ported: the 18 image
writes its own `postgresql.conf`. V1 catches them — a `setting|…|postgresql.conf` row that differs in step 6's
`cluster.txt` diff — and the remedy is `ALTER SYSTEM SET` of that value on 18, a reload (or a restart when
`pending_restart`), and step 6 again. Step 5's port is NOT re-applied over such a remedy: the `port-auto.applied` marker
makes a re-run of step 5 skip the append. To change a PORTED value instead, edit `$W/port-auto.conf`, take step 5's
Rollback (which restores `auto18.orig` and clears the marker), and re-run step 5.

**Operator's explicit word:** the restore runs ONLY into an empty cluster; the guard refuses otherwise. Redoing a
failed restore means removing the PG18 volume this window created and repeating step 4 — that removal needs the
operator's word, and it never touches `postgres-data`.

```bash
# on: hub
n=$("${PSQL[@]}" -X -At -c "SELECT count(*) FROM pg_database WHERE datname NOT IN ('postgres', 'template0', 'template1')")
if [ "$n" = 0 ] && [ ! -s "$W/restore.err" ]; then
  sudo docker exec -i postgres-main psql -U postgres -X -f - < "$W/pg16-final-$TS.sql" > "$W/restore.out" 2> "$W/restore.err"
else
  echo "cluster already holds $n databases — restore NOT re-run (read $W/restore.err)"
fi
grep -c 'ERROR' "$W/restore.err"; grep 'ERROR' "$W/restore.err" | grep -v 'role "postgres" already exists' || echo "only the allowed error"
if [ ! -f "$W/port-auto.applied" ]; then
  [ -s "$W/auto18.orig" ] || sudo docker exec postgres-main sh -c 'cat "$PGDATA/postgresql.auto.conf"' > "$W/auto18.orig"
  [ -s "$W/port-auto.conf" ] || { echo "# pg18-window port from the 16 cluster ($TS)"
    awk -v skip='^(default_transaction_read_only|old_snapshot_threshold|db_user_namespace)$' '
      /^[[:space:]]*(#|$)/ { next }
      { n = $0; sub(/^[[:space:]]*/, "", n); sub(/[[:space:]]*=.*$/, "", n)
        if (n ~ skip) next
        if (n == "ssl_ecdh_curve") sub(/ssl_ecdh_curve/, "ssl_groups")
        print }' "$W/conf16/postgresql.auto.conf"; } > "$W/port-auto.conf"
  cat "$W/port-auto.conf"
  sudo docker exec -i -u postgres postgres-main sh -c 'cat >> "$PGDATA/postgresql.auto.conf"' < "$W/port-auto.conf" && date -u +%FT%TZ > "$W/port-auto.applied"
fi
"${PSQL[@]}" -X -At -c "SELECT coalesce(name, '?') || ' — ' || error FROM pg_file_settings WHERE error IS NOT NULL AND error <> 'setting could not be applied'" | tee "$W/port-errors.txt"   # 'could not be applied' = needs the restart below, not an error
for f in pg_hba.conf pg_ident.conf; do
  if ! diff -q <(grep -vE '^\s*(#|$)' "$W/conf16/$f") <(sudo docker exec postgres-main sh -c "grep -vE '^\s*(#|$)' \"\$PGDATA/$f\"") >/dev/null; then
    sudo docker exec -i -u postgres postgres-main sh -c "cat > \"\$PGDATA/$f\"" < "$W/conf16/$f"
  fi
done
"${PSQL[@]}" -X -At -c "SELECT pg_reload_conf()"
"${PSQL[@]}" -X -At -c "SELECT name FROM pg_settings WHERE pending_restart" | grep -q . && sudo docker restart postgres-main && sleep 5
for i in $(seq 60); do sudo docker exec postgres-main pg_isready -U postgres -q && break; sleep 2; done
"${PSQL[@]}" -X -At -c "SHOW max_connections"
sudo docker exec postgres-main vacuumdb -U postgres --all --analyze-only 2> "$W/analyze.err"; grep -i error "$W/analyze.err" || echo "analyze clean"
```

**Verify:** `restore.err` holds exactly one `ERROR` and it is `role "postgres" already exists`; `port-errors.txt` is
empty and the container came back after any restart; every ported line reads back (`SHOW <name>` equals the 16 value —
a list setting shows its items comma-separated, e.g. `pg_stat_statements, auto_explain`); `max_connections` covers P6's pool sum; `analyze clean` — an error there is
the `search_path` change (pg-07): an expression index or matview on a non-default schema that must set its own.
**Rollback:** the port is undone by putting back the saved 18 file while the container is down —
`sudo docker run --rm -i -v postgres18-data:/var/lib/postgresql --entrypoint sh postgres:18.6-alpine -c 'cat > /var/lib/postgresql/18/docker/postgresql.auto.conf' < "$W/auto18.orig" && rm -f "$W/port-auto.applied"`
(it touches the PG18 copy only; the truncate-and-write keeps the file's owner), then `sudo docker start postgres-main`;
otherwise step 7's one-step rollback.

### Hub step 6 — Diff the manifest on 18 (V1) and the compatibility checks

V1 (spec § Validation): the 18 reading must equal step 3's second 16 reading after normalising PG17's `m` (MAINTAIN)
ACL letter and dropping step 1's own `default_transaction_read_only`; `datconnlimit` is the frozen 0 on both sides. Then
spec § Compatibility checks on the restored cluster before the point of no return: the restore blockers, the
`pg_trgm` indexes, and roles and grants re-measured (the manifest's `role|`/`member|` rows, SCRAM prefixes, and the
real-PG role test — spec V4, `tests/test_app_role_real_pg.py:30` runs `postgres:18.6-alpine`).

```bash
# on: hub
pg_manifest --retake "$W/manifest-18"
manifest_diff "$W/manifest-16-b" "$W/manifest-18"; echo "V1 rc=$?"
pg_compat_checks | tee "$W/compat-18.txt" | grep -E '^(BLOCKER|INVALID|NON-SCRAM)' || echo "compat: clean"
grep '^trgm index|' "$W/compat-18.txt"
grep -E '^setting\|(old_snapshot_threshold|db_user_namespace)\|' "$W/manifest-16-a/cluster.txt" || echo "no removed setting in the 16 config"
diff <(grep -E '^(role|member)\|' "$W/manifest-16-b/cluster.txt") <(grep -E '^(role|member)\|' "$W/manifest-18/cluster.txt") && echo "roles and grants equal"
```

```bash
# on: wsl, in the fleet checkout — the PG16-measured revoke behaviours re-measured on 18 (spec § Compatibility checks › Roles)
/opt/fabrik/.venv/bin/python -m pytest tests/test_app_role_real_pg.py -q
```

**Verify:** `V1 rc=0` (every file in `manifest-18.diffs/` empty); against spec § Compatibility checks — `compat: clean`
(no restore blockers: no `adminpack`, no key on a non-deterministic collation, no unlogged partitioned table, no
invalid index), every `pg_trgm` index line reads `valid=true`, `no removed setting in the 16 config`, `roles and grants
equal` with every login role SCRAM, and the real-PG role test passes.
**Rollback:** step 7's one-step rollback.

### Hub step 6a — glitchtip first

glitchtip (`glitchtip/glitchtip:latest`, Django and Celery, `infra/vps1/glitchtip/compose.yaml:3,7`) is the one
application with no WSL rehearsal. Pin its image digest for the window, start `glitchtip-web` alone against 18, check
its health and `manage.py migrate --check`. If it wrote, re-restore the `glitchtip` database from its per-database dump
before step 7 (spec D1 step 6a).

Its outcome is a marker step 7's GO reads: `glitchtip-6a.ok` is written only when one health path answered 200,
`migrate --check` exited 0, and the `glitchtip` database is byte-for-byte the restored one (it wrote nothing, or it was
re-restored and re-read equal).

```bash
# on: hub
rm -f "$W/glitchtip-6a.ok"
[ -s "$W/glitchtip-compose.yaml.orig" ] || sudo cp -p /opt/glitchtip/compose.yaml "$W/glitchtip-compose.yaml.orig"
DIGEST=$(sudo docker image inspect glitchtip/glitchtip:latest --format '{{index .RepoDigests 0}}'); echo "$DIGEST" | tee "$W/glitchtip-digest.txt"
sudo sed -i "s#image: glitchtip/glitchtip:latest#image: $DIGEST#" /opt/glitchtip/compose.yaml
pg_manifest_db glitchtip > "$W/glitchtip-before.txt"
(cd /opt/glitchtip && sudo docker compose up -d --no-deps glitchtip-web)
sleep 30
health=$(for p in /_health/ /health; do curl -sS -o /dev/null -w "%{http_code}\n" "http://10.99.0.1:8000$p"; done | grep -c '^200$')
sudo docker exec glitchtip-web ./manage.py migrate --check; mig=$?
pg_manifest_db glitchtip > "$W/glitchtip-after.txt"
sudo docker stop glitchtip-web
echo "health200=$health migrate=$mig" | tee "$W/glitchtip-6a-checks.txt"
if [ "$health" -ge 1 ] && [ "$mig" = 0 ] && diff -q "$W/glitchtip-before.txt" "$W/glitchtip-after.txt" >/dev/null; then
  echo "glitchtip wrote nothing" | tee "$W/glitchtip-6a.ok"
fi
```

If it wrote (health and migrate green, the database changed) — re-restore it. The DROP is refused unless the
glitchtip dump exited 0 (its `.ok` marker) AND passes a full read:

```bash
# on: hub — re-restore the glitchtip database (nothing else is up, so this costs minutes)
G="$W/pg16-final-$TS-glitchtip.dump"
if [ -f "$G.ok" ] && sudo docker run --rm -i postgres:18.6-alpine pg_restore -f /dev/null < "$G"; then
  sudo docker stop glitchtip-web
  "${PSQL[@]}" -X -c "DROP DATABASE IF EXISTS glitchtip WITH (FORCE)"
  sudo docker exec -i postgres-main pg_restore -U postgres --create -d postgres < "$G"
  pg_manifest_db glitchtip > "$W/glitchtip-rerestored.txt"
  grep -qx 'health200=[1-9] migrate=0' "$W/glitchtip-6a-checks.txt" && diff -q "$W/manifest-18/db-glitchtip.txt" "$W/glitchtip-rerestored.txt" >/dev/null && echo "glitchtip re-restored" | tee "$W/glitchtip-6a.ok"
else
  echo "REFUSED: $G has no .ok marker or fails the full read — glitchtip NOT dropped; NO-GO"
fi
```

**Verify:** `glitchtip-6a.ok` exists (glitchtip-web listens on `10.99.0.1:8000`, `infra/vps1/glitchtip/compose.yaml:26-27`)
and `glitchtip-web` is stopped (`sudo docker ps --format '{{.Names}}' | grep -x glitchtip-web` prints nothing); a
`health200=0` or `migrate=` other than 0 is a NO-GO at step 7.
**Rollback:** `sudo docker stop glitchtip-web`, re-restore as above, `sudo cp -p "$W/glitchtip-compose.yaml.orig"
/opt/glitchtip/compose.yaml`; or step 7's one-step rollback, which restores that file too.

### Hub step 7 — The rollback cut-off

Until services restart, rollback is one step and nothing was written to 18. After step 8.4 it is a `pg_dumpall` from 18
restored into 16 by hand, the writes since restart carried manually — so the restart is the point of no return, and
V1 must be green before it (spec D1 step 7).

```bash
# on: wsl — the tunnel must still be closed (the hook can re-open it, scripts/wsl_startup_hook.sh:227)
pgrep -af '15432:10\.99\.0\.1:[5]432' && echo "NO-GO: the MCP tunnel is open again" || echo "tunnel closed"
```

```bash
# on: hub — the GO check: every input must EXIST and be the LATEST reading, or it is a NO-GO
go=GO; nogo() { echo "NO-GO: $*"; go=NO-GO; }
[ -s "$W/manifest-18/COMPLETE" ] || nogo "manifest-18 is not a complete reading"
[ -d "$W/manifest-18.diffs" ] || nogo "no V1 diff for manifest-18 (run step 6)"
[ "$W/manifest-18.diffs" -nt "$W/manifest-18/COMPLETE" ] || nogo "the V1 diff is older than the latest manifest-18"
[ -d "$W/manifest-18.diffs" ] && [ "$(cat "$W"/manifest-18.diffs/* | wc -c)" = 0 ] || nogo "V1 diffs are not empty"
[ -s "$W/restore.err" ] || nogo "no restore.err"
[ "$(grep -c 'ERROR' "$W/restore.err" 2>/dev/null)" = 1 ] && grep -q 'role "postgres" already exists' "$W/restore.err" || nogo "restore errors are not exactly the allowed one"
[ -f "$W/compat-18.txt" ] && [ "$W/compat-18.txt" -nt "$W/manifest-18/COMPLETE" ] || nogo "compat-18.txt missing or older than manifest-18"
grep -qE '^(BLOCKER|INVALID|NON-SCRAM)' "$W/compat-18.txt" 2>/dev/null && nogo "compat-18.txt has a blocker"
grep '^trgm index|' "$W/compat-18.txt" 2>/dev/null | grep -qv 'valid=true$' && nogo "a pg_trgm index is not valid"
[ -s "$W/glitchtip-6a.ok" ] || nogo "step 6a did not pass"
[ -z "$(sudo docker ps --format '{{.Names}}' | grep -Fxf "$W/stopped-services.txt")" ] || nogo "a stopped service is running"
echo "$go"
```

If the hub check prints `NO-GO`, or the WSL check printed `NO-GO` — the one-step rollback:

```bash
# on: hub — NO-GO only
sudo docker stop postgres-main
sudo cp -p "$W/compose.yaml.pg16" /opt/postgres/compose.yaml
(cd /opt/postgres && sudo docker compose up -d)
for i in $(seq 60); do sudo docker exec postgres-main pg_isready -U postgres -q && break; sleep 2; done
"${PSQL[@]}" -X -v ON_ERROR_STOP=1 -f - <<'SQL'
SET default_transaction_read_only = off;
ALTER SYSTEM RESET default_transaction_read_only;
SELECT pg_reload_conf();
SQL
[ -s "$W/root-crontab.before" ] && sudo crontab -u root "$W/root-crontab.before"
[ -s "$W/glitchtip-compose.yaml.orig" ] && sudo cp -p "$W/glitchtip-compose.yaml.orig" /opt/glitchtip/compose.yaml
sudo crontab -u root -l | grep pre-backup
# then hub step 8.1's limit restore, and the rest of hub step 1's rollback (services, watchdogs, spokes, compose-boot, tunnel, locks, silence)
```

**Verify:** GO = the WSL check prints `tunnel closed` and the hub check prints `GO` with no `NO-GO:` line. After a NO-GO:
`SELECT version()` reports 16, the root crontab carries the `pre-backup.sh` line uncommented, `/opt/glitchtip/compose.yaml`
names `glitchtip/glitchtip:latest` again, and the services' health is green.
**Rollback:** the NO-GO block above IS the rollback; past step 8.4 rollback is the forward path of spec D1 step 7, never a
volume revert.

### Hub step 8 — Restart

Spec D1 step 8, with one ordering change from the wave-1 review: the Backrest snapshot that holds `postgres18-data`
(8.2) is taken BEFORE infra merges the DR-chain branch `fleet-pg18-dr` (8.3). Merged first, the repo's DR chain would
restore `postgres18-data` while no snapshot yet held it — a disaster recovery in that gap would find nothing.

#### 8.1 Reset the connection limits

```bash
# on: hub
while IFS='|' read -r db lim; do
  case "$db" in template0) continue ;; esac
  printf 'ALTER DATABASE "%s" CONNECTION LIMIT %s;\n' "$db" "$lim"
done < "$W/pre-freeze-connlimits.txt" | "${PSQL[@]}" -X -v ON_ERROR_STOP=1 -f -
diff <(grep -v '^template0|' "$W/pre-freeze-connlimits.txt") <("${PSQL[@]}" -X -At -c "SELECT datname || '|' || datconnlimit FROM pg_database WHERE datname <> 'template0' ORDER BY 1") && echo "limits restored"
```

**Verify:** `limits restored` (every database back to its pre-freeze limit, `-1` unless step 1 recorded another; never
`template0`, which keeps `datallowconn = false`). Databases created only by the dump (none expected) are read by hand.
**Rollback:** re-run hub step 1's `CONNECTION LIMIT 0` block.

#### 8.2 Backrest — verify the plan covers postgres18-data, then snapshot

The spec says "add `postgres18-data` to the docker-volumes plan"; the plan's real scope decides whether that is a
no-op. VERIFY, never assume: print the plan's `paths` and `excludes` from Backrest's own config
(`/opt/backrest/config/config.json`, mounted at `infra/vps1/backrest/compose.yaml:17`) and show which path covers the
new volume. Edit the plan only when nothing covers it or an exclude hides it; keep `postgres-data` in it until § 4.

```bash
# on: hub
sudo jq '.plans[] | select(.id == "docker-volumes") | {id, paths, excludes, iexcludes}' /opt/backrest/config/config.json
sudo jq -r '.plans[] | select(.id == "docker-volumes") | .paths[]' /opt/backrest/config/config.json | while read -r p; do
  case /var/lib/docker/volumes/postgres18-data/ in "${p%/}"/*) echo "COVERED by $p" ;; esac
done
sudo jq -r '.plans[] | select(.id == "docker-volumes") | ((.excludes // []) + (.iexcludes // []))[]' /opt/backrest/config/config.json | grep -n 'postgres' || echo "no exclude names a postgres path"
# ONLY when nothing printed COVERED, or an exclude hides postgres18-data: back up the config, add the path in the
# Backrest UI (Plans → docker-volumes → Paths → /var/lib/docker/volumes/postgres18-data), then:
# [ -s "$W/backrest-config.json.orig" ] || sudo cp -p /opt/backrest/config/config.json "$W/backrest-config.json.orig"; sudo docker restart backrest
```

Then trigger the snapshot (Backrest UI → Plans → `docker-volumes` → Backup now) and wait for it to finish:

```bash
# on: hub
hub_restic snapshots --tag plan:docker-volumes --latest 1
hub_restic ls latest --tag plan:docker-volumes /var/lib/docker/volumes/postgres18-data/_data/18/docker/PG_VERSION
```

**Verify:** a `COVERED by …` line and `no exclude names a postgres path` (or the edit made and re-read); the latest
`docker-volumes` snapshot is newer than `$TS` and `ls` prints
`/var/lib/docker/volumes/postgres18-data/_data/18/docker/PG_VERSION` — production never runs a night without a volume
snapshot (spec D1 step 8, V5).
**Rollback:** an edited plan goes back with `sudo cp -p "$W/backrest-config.json.orig" /opt/backrest/config/config.json &&
sudo docker restart backrest`; a snapshot needs no rollback.

#### 8.3 Infra merges fleet-pg18-dr (the DR-chain hunk)

**Precondition:** step 8.2's `Verify:` is green — the `PG_VERSION` line printed. Infra does not merge on any other
evidence.

T03's DR chain lives on its own branch `fleet-pg18-dr`, cut from master, and merges ALONE inside the window (spine
§ Merge Order; spec D3): `scripts/bootstrap/bootstrap-config.sh:201` restores `postgres18-data`, the
`bootstrap-hub.sh` step 12/12c/14 comments and probes follow it, and step 12c's probe reads `SELECT datname FROM
pg_database` and requires both `glitchtip` and `site_provisioner` (`scripts/bootstrap/bootstrap-hub.sh:1232-1236`).

```bash
# on: hub — the precondition, re-checked at the moment of the request
hub_restic ls latest --tag plan:docker-volumes /var/lib/docker/volumes/postgres18-data/_data/18/docker/PG_VERSION | grep -q PG_VERSION && echo "8.2 PRECONDITION MET"
```

```bash
# on: wsl — only after "8.2 PRECONDITION MET"
python3 scripts/mail.py send --to fabrik --to-agent infra --kind request --ack required <<'EOF'
Hub window step 8.3: merge branch fleet-pg18-dr to master NOW, alone (spine § Merge Order). Precondition met: the docker-volumes snapshot holds postgres18-data/_data/18/docker/PG_VERSION (runbook step 8.2). Reply when pushed.
EOF
git -C /opt/fabrik fetch -q origin
git -C /opt/fabrik show origin/master:scripts/bootstrap/bootstrap-config.sh | grep -n 'postgres18-data'
```

**Verify:** the last command prints the `FABRIK_HUB_VOLUMES_TO_RESTORE` line naming `postgres18-data` — master's DR chain
and the hub's volume now agree.
**Rollback:** only with a full-window rollback: infra reverts the merge (`git revert -m 1 <merge>`), and the chain names
`postgres-data` again.

#### 8.4 Start the services

The point of no return (step 7). The tunnel is re-checked first: the shell-open hook can re-open it
(`scripts/wsl_startup_hook.sh:227`), and it must stay closed until 8.6.

```bash
# on: wsl
pgrep -af '15432:10\.99\.0\.1:[5]432' && echo "STOP: the MCP tunnel is open again — pkill it before 8.4" || echo "tunnel closed"
```

```bash
# on: hub
xargs -r sudo docker start < "$W/stopped-services.txt"
sudo docker ps --format '{{.Names}}' | grep -Fxf "$W/stopped-services.txt" | wc -l; wc -l < "$W/stopped-services.txt"
```

```bash
# on: wsl (ssh to vps2/vps3) — the lists step 1 wrote to $HW on WSL
HW=$HOME/pg18-hub-window
for h in vps2 vps3; do
  xargs -r ssh "$h" sudo docker start < "$HW/stopped-$h.txt"
  ssh "$h" 'sudo docker ps --format "{{.Names}}"' | grep -Fxf "$HW/stopped-$h.txt" | wc -l; wc -l < "$HW/stopped-$h.txt"
done
```

**Verify:** `tunnel closed`; the two hub counts are equal, and for each spoke its two counts are equal.
**Rollback:** the forward path of spec D1 step 7 — a `pg_dumpall` from 18 into a 16 cluster, by hand.

#### 8.5 Start the watchdog sidecars

```bash
# on: hub
xargs -r sudo docker start < "$W/stopped-watchdogs.txt"
sudo docker ps --format '{{.Names}}' | grep -Fxf "$W/stopped-watchdogs.txt"
```

**Verify:** every name on the list prints.
**Rollback:** `xargs -r sudo docker stop < "$W/stopped-watchdogs.txt"`.

#### 8.6 Re-enable compose-boot, lift the freeze, restore the tunnel

```bash
# on: hub
sudo systemctl enable fabrik-compose-boot.service; systemctl is-enabled fabrik-compose-boot.service
[ -s "$W/root-crontab.before" ] && sudo crontab -u root "$W/root-crontab.before"; sudo crontab -u root -l
sudo cp -p "$W/glitchtip-compose.yaml.orig" /opt/glitchtip/compose.yaml
```

```bash
# on: wsl — the tunnel exactly as scripts/wsl_startup_hook.sh:227 starts it, then the all-clear to the agents
HW=$HOME/pg18-hub-window
[ -s "$HW/locks-created.txt" ] && xargs -r rm -f < "$HW/locks-created.txt" && mv "$HW/locks-created.txt" "$HW/locks-removed.txt"
pgrep -f '15432:10\.99\.0\.1:[5]432' >/dev/null || nohup ssh -N -o ExitOnForwardFailure=yes -o ServerAliveInterval=30 -o ServerAliveCountMax=3 -L 15432:10.99.0.1:5432 vps >/dev/null 2>&1 &
python3 scripts/mail.py send --to fabrik --broadcast --ack no --kind request <<'EOF'
DEPLOY FREEZE LIFTED — postgres-main now runs PostgreSQL 18.6. Report anything database-shaped to fleet.
EOF
```

**Verify:** `enabled`; the root crontab carries the `pre-backup.sh` line uncommented; the daily-hook locks step 1
created are gone (only those — `locks-removed.txt` lists them); `pgrep -af '15432:10\.99\.0\.1:[5]432'`
prints the tunnel.
**Rollback:** `sudo systemctl disable fabrik-compose-boot.service` and re-announce the freeze.

#### 8.7 The battery (V2–V6) and the operator checks

Spec § Validation V2–V6, plus the archived plan's checks (`docs/development/plans/archived/2026-05-25-postgresql-18-upgrade.md:120-127`):
`fabrik audit-registrars` (`src/fabrik/cli.py:1370`), a GlitchTip error check, one API call per service.

```bash
# on: hub
"${PSQL[@]}" -X -At -c "SELECT version(), current_setting('server_version_num')"
"${PSQL[@]}" -X -At -c "SELECT count(*) FROM pg_authid WHERE rolcanlogin AND rolpassword IS NOT NULL AND rolpassword NOT LIKE 'SCRAM-SHA-256\$%'"
sudo docker exec prometheus wget -qO- http://postgres-exporter:9187/metrics | grep -E '^pg_up |^pg_exporter_last_scrape_error '
sudo docker logs --since "$(date -u -d '-15 min' +%Y-%m-%dT%H:%M:%SZ)" postgres-exporter 2>&1 | grep -ci error
```

```bash
# on: wsl, in /opt/fabrik
.venv/bin/fabrik audit-registrars
.venv/bin/python - <<'PY' > /tmp/pg18-db-domains.txt
import glob, yaml
for f in sorted(glob.glob("specs/services/*.yaml")):
    s = yaml.safe_load(open(f)) or {}
    if (s.get("shape") or {}).get("needs_database") and s.get("domain"):
        print(s["domain"])
PY
while read -r d; do curl -sS -o /dev/null -m 15 -w "%{http_code} $d\n" "https://$d/health"; done < /tmp/pg18-db-domains.txt
```

**Verify:** V2 `PostgreSQL 18.6` and `180006` or higher; V4 `0` non-SCRAM login roles; V6 `pg_up 1`,
`pg_exporter_last_scrape_error 0` and `0` exporter errors; `audit-registrars` reports every registrar healthy; V3 every
domain answers `200` (a non-200 is retried on that spec's own health path) and Gatus (`status.vps1.ocoron.com`) is green
for every database-backed endpoint, spokes included; GlitchTip (`errors.vps1.ocoron.com`,
`infra/vps1/glitchtip/compose.yaml:16`) shows no new database-shaped issue since `$TS`. V5 is read the next morning: the
first nightly `pg_dumpall` ends with its trailer (`sudo ls -1t /opt/backups/pg_dump_*.sql | head -1 | xargs sudo tail -n 1`)
and the nightly `docker-volumes` snapshot holds the 8.2 `PG_VERSION` path.
**Rollback:** a red battery line is fixed forward (the service, its pool, its query); a red that implicates the
cluster itself is the forward path of spec D1 step 7.

#### 8.8 Close the window — silence off, all-clear, 7-day dump hold

```bash
# on: hub
window_silences() { sudo docker exec alertmanager amtool silence query --alertmanager.url=http://localhost:9093 -o json | jq -r --arg c "pg18-window-$TS" '.[] | select(.comment == $c and .status.state == "active") | .id'; }
window_silences | xargs -r sudo docker exec alertmanager amtool silence expire --alertmanager.url=http://localhost:9093
sudo docker exec prometheus wget -qO- --post-data "title=Maintenance complete&body=postgres-main runs PostgreSQL 18.6 ($TS). Services are back." http://apprise:8000/notify/alerts
date -u -d '+7 days' +%F | sudo tee "$W/HOLD-UNTIL" >/dev/null; cat "$W/HOLD-UNTIL"
for d in /dev/shm/pg18.*; do [ -d "$d" ] || continue; [ -f "$d/pgpass.env" ] && shred -u "$d/pgpass.env"; rmdir "$d"; done
ls -d /dev/shm/pg18.* 2>/dev/null || echo "no password file left"
```

**Verify:** no active silence carries the window's comment; the all-clear arrived on Telegram; `HOLD-UNTIL` reads today + 7
days — the final dump (`pg16-final-$TS.sql` and its per-database dumps) is kept at least until then
(`docs/development/plans/archived/2026-05-25-postgresql-18-upgrade.md:132`), in `$W` and in the step-3 snapshot; no
password file remains (`no password file left` printed — the RAM directories steps P3 and 3 created are gone).
**Rollback:** none — closing actions.

## 4. Release after the soak

After the soak — by default 7 days of green nightly backups and a green battery (spec § Lifecycle step 6). The V8 DR
drill comes FIRST; nothing in this section is removed before its `Verify:` is green, and every removal waits for the
operator's explicit word.

### Release step R1 — V8 DR drill, with an independent content check

`fabrik vultr drill hub` restores the latest snapshots onto a throwaway droplet and boots `postgres-main` from the
restored `postgres18-data` (step 12c, `--drill-start-core-only`, `src/fabrik/orchestrator/vultr_drill.py:308-312`;
spec V8). Do NOT take the script's own success as the content proof: step 12 counts a restic exit code 0 as
"restored" (`scripts/bootstrap/bootstrap-hub.sh:972`, the `restored N/N` line at `:977`), step 14 reads a failed psql
as an empty volume (`|| true`, `scripts/bootstrap/bootstrap-hub.sh:1330`), and step 12c's probe — `SELECT datname FROM
pg_database`, requiring both `glitchtip` and `site_provisioner` (`scripts/bootstrap/bootstrap-hub.sh:1232-1236`) — only
warns. The drill droplet is destroyed when the drill succeeds (`src/fabrik/orchestrator/vultr_drill.py:531-534`), so
the content check restores the SAME snapshot's `postgres18-data` into a scratch directory on the hub and boots a
network-less `postgres:18.6-alpine` on it.

```bash
# on: wsl, in /opt/fabrik — the drill
.venv/bin/fabrik vultr drill hub --dry-run
.venv/bin/fabrik vultr drill hub --keep-on-failure --max-cost 2
grep -E 'step_12 done|step_12c|postgres-main:|step_14' "$(ls -1t logs/drill-*.bootstrap.log | head -1)"
```

```bash
# on: hub — the independent content check (needs free space of one cluster size: re-run the disk-gate df first)
SNAP=$(hub_restic snapshots --tag plan:docker-volumes --latest 1 --json | jq -r '.[-1].short_id'); echo "snapshot $SNAP"
V=/opt/backups/pg18-drill-verify-$SNAP
[ -d "$V/var/lib/docker/volumes/postgres18-data/_data/18/docker" ] || { sudo install -d -m 700 "$V"; HUB_RESTIC_MOUNT="$V:/restore" hub_restic restore "$SNAP" --target /restore --include /var/lib/docker/volumes/postgres18-data; }
state=$(sudo docker inspect -f '{{.State.Status}}' pg18-drill-verify 2>/dev/null || echo absent); echo "pg18-drill-verify: $state"
# a leftover that is not running is a scratch container over the scratch COPY in $V — never the live volume — so it is removed and recreated
case "$state" in running | absent) ;; *) sudo docker rm pg18-drill-verify ;; esac
[ "$state" = running ] || sudo docker run -d --name pg18-drill-verify --network none -v "$V/var/lib/docker/volumes/postgres18-data/_data:/var/lib/postgresql" postgres:18.6-alpine
for i in $(seq 60); do sudo docker exec pg18-drill-verify pg_isready -U postgres -q && break; sleep 2; done
sudo docker exec pg18-drill-verify pg_isready -U postgres || echo "STOP: pg18-drill-verify is not ready — read: sudo docker logs pg18-drill-verify"
DRILL=(sudo docker exec -i pg18-drill-verify psql -U postgres)
diff <("${PSQL[@]}" -X -At -c "SELECT datname FROM pg_database ORDER BY 1") <("${DRILL[@]}" -X -At -c "SELECT datname FROM pg_database ORDER BY 1") && echo "database list equal"
counts() { local -n q=$1; local db; for db in $("${q[@]}" -X -At -d postgres -c "SELECT datname FROM pg_database WHERE datallowconn ORDER BY 1"); do
  "${q[@]}" -X -At -d "$db" -f - <<'SQL'
SELECT format('SELECT %L || count(*) FROM %I.%I', current_database() || '|' || n.nspname || '.' || c.relname || '|', n.nspname, c.relname)
  FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
 WHERE c.relkind = 'r' AND n.nspname NOT LIKE 'pg\_%' AND n.nspname <> 'information_schema' ORDER BY 1
\gexec
SQL
done; }
counts PSQL > "$V.live-counts.txt"; counts DRILL > "$V.drill-counts.txt"
join -t'|' -j1 <(awk -F'|' '{print $1"/"$2"|"$3}' "$V.live-counts.txt" | sort) <(awk -F'|' '{print $1"/"$2"|"$3}' "$V.drill-counts.txt" | sort) \
  | awk -F'|' '$3 == 0 && $2 > 0 {print "EMPTY IN DRILL: " $1} {l += $2; d += $3} END {print "rows live=" l " drill=" d}'
wc -l < "$V.live-counts.txt"; wc -l < "$V.drill-counts.txt"
sudo docker rm -f pg18-drill-verify
```

**Verify:** the drill reports `success=True` and its log shows step 12c's `glitchtip + site_provisioner databases present`;
the content check prints `database list equal`, the two table counts are equal, no `EMPTY IN DRILL` line, and the drill's
total rows sit at or just below the live total (the snapshot is hours older than the live reading — the drift is the
writes since the nightly run, never a missing database or an emptied table). A red here stops § 4: nothing is released.
**Rollback:** none for the live hub — the check is read-only against it; `pg18-drill-verify` is already removed by the
block. The scratch directory `$V` is a copy and is removed on the operator's word only, by the block below.

**Operator's explicit word:** required before the block below runs `sudo rm -rf` on `$V` — the scratch copy of the
restored volume and its two count files; never a docker volume. The path guard refuses anything else.

```bash
# on: hub — ONLY on the operator's explicit word, after R1's Verify is green
case "$V" in
  /opt/backups/pg18-drill-verify-?*) sudo rm -rf -- "$V" "$V.live-counts.txt" "$V.drill-counts.txt"; ls -d "$V" 2>/dev/null || echo "scratch copy removed" ;;
  *) echo "REFUSED: \$V is '$V', not a pg18-drill-verify scratch path — nothing removed" ;;
esac
```

### Release step R2 — Remove postgres-data from the Backrest plan

Only when 8.2 found an explicit volume list naming `postgres-data`. When the plan's scope is the whole
`/var/lib/docker/volumes/` directory, there is nothing to edit: `postgres-data` stops being backed up when R3 removes it.

```bash
# on: hub
sudo jq -r '.plans[] | select(.id == "docker-volumes") | .paths[]' /opt/backrest/config/config.json | grep -n 'postgres-data' || echo "no explicit postgres-data path — nothing to edit"
# ONLY when the line above named it: [ -s "$W/backrest-config.json.pre-release" ] || sudo cp -p /opt/backrest/config/config.json "$W/backrest-config.json.pre-release"
# then remove the path in the Backrest UI (Plans → docker-volumes → Paths) and: sudo docker restart backrest
```

**Verify:** the plan's `paths` no longer name `postgres-data` (or never did), and the next `docker-volumes` snapshot still
holds the 8.2 `PG_VERSION` path.
**Rollback:** `sudo cp -p "$W/backrest-config.json.pre-release" /opt/backrest/config/config.json && sudo docker restart backrest`.

#### Restoring a pre-window snapshot (manual)

Snapshots taken before the window hold `postgres-data` (the PG16 layout at `/var/lib/postgresql/data`), and after 8.3
the DR chain restores only `postgres18-data` (`scripts/bootstrap/bootstrap-config.sh:201`). `bootstrap-hub.sh` pointed
at such a snapshot would create an EMPTY `postgres18-data` and boot nothing useful. Restoring one is therefore manual,
with the old volume name and the 16 compose (`$W/compose.yaml.pg16`, which rides in the `postgres-dumps` snapshots
because `$W` is under `/opt/backups`):

```bash
# on: the host being restored — SNAP is the pre-window docker-volumes snapshot id
sudo docker volume inspect postgres-data >/dev/null 2>&1 || sudo docker volume create postgres-data
HUB_RESTIC_MOUNT="/:/host" hub_restic restore "$SNAP" --target /host --include /var/lib/docker/volumes/postgres-data
sudo cp -p /opt/backups/pg18-window-<TS>/compose.yaml.pg16 /opt/postgres/compose.yaml
(cd /opt/postgres && sudo docker compose up -d)
sudo docker exec postgres-main psql -U postgres -XAtc "SELECT version()"
```

**Verify:** `version()` reports 16; the databases are the pre-window set.
**Rollback:** stop `postgres-main` and put the 18 compose back (hub step 4's block).

### Release step R3 — Remove the old postgres-data volume

**Operator's explicit word:** required — the operator names this step and this volume in the session before the last
line runs. A dry-run comes first and is read.

```bash
# on: hub — dry run: nothing uses it, and what it holds
sudo docker ps -a --filter volume=postgres-data --format '{{.Names}} {{.Status}}'
sudo docker volume inspect postgres-data
sudo du -sh /var/lib/docker/volumes/postgres-data
# ONLY on the operator's explicit word, after R1 is green and the 7-day dump hold has passed:
sudo docker volume rm postgres-data
```

**Verify:** the dry run lists no container; after the word, `sudo docker volume inspect postgres-data` fails and
`postgres18-data` still serves (`"${PSQL[@]}" -X -At -c "SELECT version()"` reports 18.6).
**Rollback:** none after removal — the pre-window snapshots (R2's manual restore) are the only copy left, which is why R1
and the operator's word come first.

### Release step R4 — Remove the WSL 16 cluster

**Operator's explicit word:** required — this deletes the WSL 16 cluster's data directory (kept on 5433 since WSL step 3).

```bash
# on: wsl — dry run first
pg_lsclusters
sudo du -sh /var/lib/postgresql/16/main
# ONLY on the operator's explicit word, after the hub release (R3) or the operator's ruling to release WSL alone:
sudo pg_dropcluster 16 main --stop
```

**Verify:** `pg_lsclusters` lists `18 main 5432 online` only (plus brand-identiy-creator's 5433 arrangement if WSL step 6
ran).
**Rollback:** none after removal — the step-3 `manifest-16` and each project's own dumps are the only record.

## 5. Appendix — project requests (D5, D6, D7)

Sent from the hub's main checkout with `scripts/mail.py send` (body on stdin), AFTER the hub window passes — a project
CI on 16 against an 18 production fails closed, the reverse fails open (spec D5) — except A1, which goes out BEFORE the
WSL window (spec D7). Every request names its lines from spec § What exists today and asks the project to run its suite
against the WSL 18 cluster before committing. A hub agent never edits another repo (`CLAUDE.md` § HARD STOPS); these
are requests. Each item's `**Send:**` line says WHEN: `BEFORE-WSL-WINDOW`, `AFTER-HUB-WINDOW` or `NONE`.

### A1 — brand-identiy-creator (D7)

**Send:** BEFORE-WSL-WINDOW — D7: the change is prepared before the WSL window and merged after it.

```bash
# on: wsl, in /opt/fabrik
python3 scripts/mail.py send --to brand-identiy-creator --kind request --ack required <<'BODY'
PostgreSQL 18 fleet upgrade (hub spec docs/superpowers/specs/2026-10-06-postgresql-18-fleet-upgrade-design.md, D7).
WHAT: replace the pg_uuidv7 extension with native uuidv7(), on a branch prepared NOW and merged only after the WSL window.
WHY: postgres-main does not offer pg_uuidv7, and the WSL dev database is dropped before pg_upgradecluster (it has no 18 build).
WHERE (re-measure: grep -rl uuid_generate_v7 --include=*.py --include=*.sql --include=*.md — 24 files when measured):
- model server_defaults, e.g. src/brand_identity/models/tenant.py:27
- raw INSERTs: services/checkpoints.py:137,219
- migrations/versions/0001_initial_schema.py:20 (CREATE EXTENSION "pg_uuidv7") — rewrite so it no longer creates it; also 0008, 0010, 0018
- tests; db/schema.sql:3,14; README.md:117
HOW: call native uuidv7() (or create, on 18 only, the shim CREATE OR REPLACE FUNCTION uuid_generate_v7() RETURNS uuid LANGUAGE sql VOLATILE AS 'SELECT uuidv7()'). Gate the branch against a scratch postgres:18.6-alpine container (no pg_uuidv7 there — the target condition). Merge after the WSL window, when your suite runs against the WSL 18 cluster; your dev database is recreated on 18 from the rewritten migrations. Production deploy (still .draft) happens only on the 18 hub.
BODY
```

### A2 — tryton-crm and tojlo-mail

**Send:** AFTER-HUB-WINDOW — a project CI on 16 against an 18 production fails closed (spec D5).

```bash
# on: wsl, in /opt/fabrik
cat > /tmp/pg18-a2.txt <<'BODY'
PostgreSQL 18 fleet upgrade (hub spec docs/superpowers/specs/2026-10-06-postgresql-18-fleet-upgrade-design.md, D5). postgres-main now runs 18.6.
WHAT: move your dev Postgres image to postgres:18.6-* (same variant you use today; probe the tag with docker manifest inspect first) AND its data mount to /var/lib/postgresql — an image-only bump fails to start (the 18 image refuses a volume at /var/lib/postgresql/data).
WHERE:
- tryton-crm: compose.dev.yaml:71 (postgres:16-bookworm), the mount at compose.dev.yaml:93, .env.example:49, trytond.conf:4
- tojlo-mail: docker/docker-compose.local.yml:38, the mount at docker/docker-compose.local.yml:44, and the two test notes that name 16
HOW: pg_dump your dev data from the 16 container, switch image and mount (a NEW volume), restore into 18; run your suite against the WSL 18 cluster before committing.
BODY
for r in tryton-crm tojlo-mail; do python3 scripts/mail.py send --to "$r" --kind request --ack required --body-file /tmp/pg18-a2.txt; done
```

### A3 — trade-intelligence (D6)

**Send:** AFTER-HUB-WINDOW — a project CI on 16 against an 18 production fails closed (spec D5).

```bash
# on: wsl, in /opt/fabrik
python3 scripts/mail.py send --to trade-intelligence --kind request --ack required <<'BODY'
PostgreSQL 18 fleet upgrade (hub spec docs/superpowers/specs/2026-10-06-postgresql-18-fleet-upgrade-design.md, D5/D6). postgres-main and the WSL dev cluster now run 18.
WHAT: trade-intelligence follows the fleet — you left Supabase for postgres-main (README.md:165), so your cutover lands on an 18 cluster and nothing stays on 17.
WHERE — the six pins to 18:
- .github/workflows/ci.yml:25
- scripts/verify_fresh_bootstrap.py:58
- scripts/run_db_suite_clean.sh:32
- tests/db/test_roles_sql_attributes.py:95
- .env.example:29
- web/playwright.r21-write.config.ts:13
and the pg_dump >= 16.x assertion. Run your suite against the WSL 18 cluster before committing.
BODY
```

### A4 — gmail-account-creator and fabrik-claim-validator

**Send:** AFTER-HUB-WINDOW — a project CI on 16 against an 18 production fails closed (spec D5).

```bash
# on: wsl, in /opt/fabrik
cat > /tmp/pg18-a4.txt <<'BODY'
PostgreSQL 18 fleet upgrade (hub spec docs/superpowers/specs/2026-10-06-postgresql-18-fleet-upgrade-design.md, D5). The hub's CI generator now derives its Postgres images from the version registry (18).
WHAT: regenerate your CI — .github/workflows/ci.yml:12 is generated ("fabrik-managed — regenerate via fabrik scaffold", its line 1), so do not hand-edit it: re-run the hub's scripts/backfill_ci.py / the scaffold for your repo — and move scripts/ci_local.sh:8 to the same postgres:18 image.
Run your suite against the WSL 18 cluster before committing.
BODY
for r in gmail-account-creator fabrik-claim-validator; do python3 scripts/mail.py send --to "$r" --kind request --ack required --body-file /tmp/pg18-a4.txt; done
```

### A5 — youtube

**Send:** AFTER-HUB-WINDOW — a project CI on 16 against an 18 production fails closed (spec D5).

```bash
# on: wsl, in /opt/fabrik
python3 scripts/mail.py send --to youtube --kind request --ack required <<'BODY'
PostgreSQL 18 fleet upgrade (hub spec docs/superpowers/specs/2026-10-06-postgresql-18-fleet-upgrade-design.md, D5). postgres-main and the WSL dev cluster now run 18.
WHERE: .github/workflows/test.yml:15 — the CI service image to postgres:18; your docs' "apt install postgresql-16-pgvector" lines to postgresql-18-pgvector (the WSL cluster now has postgresql-18-pgvector from PGDG).
Run your suite against the WSL 18 cluster before committing.
BODY
```

### A6 — calendar-orchestration-engine

**Send:** AFTER-HUB-WINDOW — a project CI on 16 against an 18 production fails closed (spec D5).

```bash
# on: wsl, in /opt/fabrik
python3 scripts/mail.py send --to calendar-orchestration-engine --kind request --ack required <<'BODY'
PostgreSQL 18 fleet upgrade (hub spec docs/superpowers/specs/2026-10-06-postgresql-18-fleet-upgrade-design.md, D5). postgres-main now runs 18.6.
WHERE: Dockerfile.scheduler:12 installs an unpinned postgresql-client; on its node:22-bookworm-slim base that is client 15.
WHAT: pin postgresql-client-18. That line installs curl but not ca-certificates/gnupg, so add those two, then the PGDG keyring and apt source, then the package (PGDG offers 18.6-1.pgdg12+2 for bookworm, measured in the hub's review).
Run your suite against the WSL 18 cluster before committing.
BODY
```

### A7 — fabrik-lib

**Send:** AFTER-HUB-WINDOW — a project CI on 16 against an 18 production fails closed (spec D5).

```bash
# on: wsl, in /opt/fabrik
python3 scripts/mail.py send --to fabrik-lib --kind request --ack required <<'BODY'
PostgreSQL 18 fleet upgrade (hub spec docs/superpowers/specs/2026-10-06-postgresql-18-fleet-upgrade-design.md, D5). postgres-main now runs 18, which ships native uuidv7().
WHERE: fastapi-user-auth/README.md:791 (postgres:16) and the vendored fastapi_user_auth/schema.sql:3 comment ("PG16 has no native uuidv7()").
Your copies flow to fabrik-lib-account, fabrik-lib-review and the projects that vendor fastapi_user_auth — refresh them the usual way.
BODY
```

### A8 — the 27 doc-only projects (one broadcast)

**Send:** AFTER-HUB-WINDOW — a project CI on 16 against an 18 production fails closed (spec D5).

One body for all of them, one line per project naming its files (spec D5). The spec counted ~70 lines across 27 projects
without listing them; the body's project lines are re-measured at send time with the spec's own scope rule (every
`/opt/<name>` with a `.git` or a compose file, `.claude/worktrees` excluded, `rg --no-ignore --hidden`), minus the
projects A1–A7 address and the synced baseline the governance sync refreshes (A9).

```bash
# on: wsl, in /opt/fabrik
command -v rg >/dev/null || { echo "rg missing — install ripgrep"; }
skip='^(fabrik|brand-identiy-creator|tryton-crm|tojlo-mail|trade-intelligence|gmail-account-creator|fabrik-claim-validator|youtube|calendar-orchestration-engine|fabrik-lib|fabrik-lib-account|fabrik-lib-review)$'
: > /tmp/pg18-a8-lines.txt
for p in /opt/*/; do
  n=$(basename "$p"); [ -d "$p/.git" ] || [ -f "$p/compose.yaml" ] || continue
  echo "$n" | grep -qE "$skip" && continue
  files=$(cd "$p" && rg --no-ignore --hidden -l -i -t md -e 'postgres(ql)?[ -]?16' -e 'pg ?16' -g '!.claude/worktrees/**' -g '!.git/**' -g '!.windsurf/**' -g '!agents-fabrik.md' . 2>/dev/null | sed 's|^\./||' | sort | paste -sd, -)
  [ -n "$files" ] && echo "- $n: $files" >> /tmp/pg18-a8-lines.txt
done
wc -l < /tmp/pg18-a8-lines.txt
cat > /tmp/pg18-a8.txt <<'BODY'
PostgreSQL 18 fleet upgrade (hub spec docs/superpowers/specs/2026-10-06-postgresql-18-fleet-upgrade-design.md, D5). postgres-main and the WSL dev cluster now run PostgreSQL 18.6.
WHAT: your docs still say PostgreSQL 16 — update the lines below (current-state docs only; dated plans, specs and logs are history and stay as written). No code change is asked. Your synced baseline (agents-fabrik.md, CLAIMS.yaml, the rule packs) is refreshed by the governance sync, not by you.
WHERE — every doc-only project in this broadcast, one line each (find yours):
BODY
cat /tmp/pg18-a8-lines.txt >> /tmp/pg18-a8.txt
for r in $(sed -E 's/^- ([^:]+):.*/\1/' /tmp/pg18-a8-lines.txt); do python3 scripts/mail.py send --to "$r" --kind request --ack no --body-file /tmp/pg18-a8.txt; done
```

Read the count before the loop sends: it should be 27; a different count means the fleet moved since the spec measured —
read the lines, drop any false hit (a dated plan, a changelog entry), and send to what remains.

### A9 — the synced baseline (no request)

**Send:** NONE — the governance sync carries it; no mail.

`agents-fabrik.md`, `CLAIMS.yaml`, the rule packs and the gate comments every project carries update through the
governance sync when D3 and D4 merge (spec D5, last bullet); no project is asked to touch them.
