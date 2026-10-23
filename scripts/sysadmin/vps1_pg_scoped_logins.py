#!/usr/bin/env python3
# AFTER-EDIT: docs/reference/vps1-postgres-admin-rotation-runbook.md
"""vps1 Postgres rotation, runbook steps 1-3 only: scoped logins for GlitchTip and postgres_exporter.

Operator-run (W-80983d8c; D-1176 go, D-1177 no-TTY verifier route). Run from the hub main checkout:

    cd /opt/fabrik && python3 -I scripts/sysadmin/vps1_pg_scoped_logins.py

Every block prints what it will do and waits for a typed `yes`; anything else stops the run with nothing further
changed. Step 4 (the `postgres` password) is NOT here: it waits for the spoke sweep and the day-long watch.

D-1177 conditions, all enforced below:
1. The verifier is built as libpq does (PBKDF2-HMAC-SHA-256, iterations from `show scram_iterations`, >= 4096,
   16-byte `secrets` salt, StoredKey/ServerKey).
2. No cleartext password or verifier in argv, an env var, an echo or the output: both travel only on ssh stdin.
3. SQL goes on stdin to `psql -X -v ON_ERROR_STOP=1`, never `-c` with a secret. The one staged file (the login
   probe's pgpass) is umask 077, removed, then `test ! -e`.
4. Per role: assert `rolpassword = <verifier>` in pg_authid, then one real TCP login on the scram host line.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import re
import secrets
import shlex
import string
import subprocess
import sys
import time
from pathlib import Path

SSH = ["ssh", "-o", "ProxyJump=vps2", "-o", "ConnectTimeout=20", "vps"]
PSQL = "sudo docker exec -i postgres-main psql -X -q -U postgres -v ON_ERROR_STOP=1 -tA"
HUB = Path("/opt/fabrik")
STAMP = time.strftime("%Y%m%d-%H%M%S")
SECRETS_DIR = HUB / "backups" / f"pg-rotation-{STAMP}"

# (role, database, live compose dir, env key, old literal in the live compose, its expected count, services)
SERVICES = [
    ("glitchtip", "glitchtip", "/opt/glitchtip", "GLITCHTIP_DATABASE_URL",
     "postgresql://postgres:postgres@postgres-main:5432/glitchtip", 2, ["glitchtip-web", "glitchtip-worker"]),
    ("postgres_exporter", "postgres", "/opt/monitoring", "POSTGRES_EXPORTER_DSN",
     "postgresql://postgres:postgres@postgres-main:5432/postgres?sslmode=disable", 1, ["postgres-exporter"]),
]
HUB_ENV_KEYS = {"glitchtip": "VPS1_PG_GLITCHTIP_PASSWORD", "postgres_exporter": "VPS1_PG_POSTGRES_EXPORTER_PASSWORD"}

_DSN_SECRET = re.compile(r"(://[^:/@\s]+):[^@\s]*@")
_VERIFIER = re.compile(r"SCRAM-SHA-256\$[^'\s]+")
_SPOKE_PATTERN = r"postgres(ql)?://postgres:[^@]*@(10\.99\.0\.1|postgres-main)|PGUSER=postgres"
_SPOKE_SKIP = r"/node_modules/|\.md$|\.j2$|\.example$|\.bak|backup"
_GLITCHTIP_STATUS = """import urllib.request as u, urllib.error as e
try:
    print(u.urlopen('http://localhost:8000/api/0/').status)
except e.HTTPError as x:
    print(x.code)
"""


def mask(text: str) -> str:
    """Hide DSN passwords and SCRAM verifiers (psql echoes a failing statement in its error text)."""
    return _VERIFIER.sub("SCRAM-SHA-256$***", _DSN_SECRET.sub(r"\1:***@", text))


def die(msg: str) -> None:
    print(f"\nSTOP: {msg}\nNothing after this point ran.", file=sys.stderr)
    sys.exit(1)


def gate(title: str, plan: str) -> None:
    print(f"\n=== {title} ===\n{plan}")
    if input("Type yes to run this block: ").strip() != "yes":
        die(f"not confirmed: {title}")


def remote(cmd: str, stdin: str | None = None, host: list[str] | None = None, check: bool = True) -> str:
    """Run cmd on vps1 (or host); secrets only ever ride on stdin. Output is returned unprinted."""
    r = subprocess.run((host or SSH) + [cmd], input=stdin, capture_output=True, text=True, timeout=300)
    if check and r.returncode != 0:
        die(f"remote command failed (rc {r.returncode}): {mask(cmd)}\n{mask(r.stderr.strip())}")
    return r.stdout.strip()


def sql(text: str, db: str = "postgres") -> str:
    return remote(f"{PSQL} -d {shlex.quote(db)}", stdin=text)


def verifier(password: str, iterations: int) -> str:
    salt = secrets.token_bytes(16)
    salted = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations)
    client_key = hmac.new(salted, b"Client Key", hashlib.sha256).digest()
    stored_key = hashlib.sha256(client_key).digest()
    server_key = hmac.new(salted, b"Server Key", hashlib.sha256).digest()
    b64 = lambda b: base64.b64encode(b).decode()  # noqa: E731
    return f"SCRAM-SHA-256${iterations}:{b64(salt)}${b64(stored_key)}:{b64(server_key)}"


def new_password() -> str:
    return "".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(32))


def block0_spoke_sweep() -> None:
    gate("Block 0 — spoke sweep (read-only, gate W-6610ceac)",
         "On vps2 and vps3: list files under /opt that hold a superuser DSN to the hub (file NAMES only).")
    find = f"sudo grep -rIlE {shlex.quote(_SPOKE_PATTERN)} /opt 2>/dev/null | grep -vE {shlex.quote(_SPOKE_SKIP)} || true"
    for name in ("vps2", "vps3"):
        out = remote(find, host=["ssh", "-o", "ConnectTimeout=20", name])
        print(f"  {name}: {out or 'no hits'}")
        if out:
            die(f"{name} holds a superuser DSN to the hub — add it to the runbook's consumer table first")


def block1_settings() -> int:
    gate("Block 1 — vps1 settings and stop checks (read-only)",
         "server_version, scram_iterations, password_encryption, pg_hba stop rules, live DSN lines (masked).")
    print("  server_version:", sql("show server_version;"))
    iterations = int(sql("show scram_iterations;"))
    enc = sql("show password_encryption;")
    print(f"  scram_iterations: {iterations}  password_encryption: {enc}")
    if iterations < 4096 or enc != "scram-sha-256":
        die("scram_iterations < 4096 or password_encryption is not scram-sha-256")
    hba = remote("sudo docker exec postgres-main sh -c 'grep -vE \"^\\s*(#|$)\" \"$PGDATA/pg_hba.conf\"'")
    rows = [r.split() for r in hba.splitlines()]
    if not any(r[:3] == ["local", "all", "all"] and r[-1] == "trust" for r in rows):
        die("the `local all all` line is not trust — row 8's passwordless callers would break")
    loopback = {"127.0.0.1/32", "::1/128"}
    if any(r[0] == "host" and r[-1] == "trust" and r[3] not in loopback for r in rows if len(r) >= 5):
        die("a non-loopback `host … trust` line exists — a different fix first")
    print("  pg_hba: local trust; host trust on loopback only — OK")
    for _role, _db, cdir, _key, old, count, _svcs in SERVICES:
        seen = int(remote(f"sudo grep -cF {shlex.quote(old)} {cdir}/compose.yaml || true") or 0)
        print(f"  {cdir}/compose.yaml: old superuser DSN occurs {seen}x (expected {count})")
        if seen != count:
            die(f"{cdir}/compose.yaml does not hold the expected DSN lines — inspect it by hand")
    return iterations


def step2_passwords() -> dict[str, str]:
    gate("Step 2 — generate the two scoped passwords",
         f"32 chars [a-zA-Z0-9] via secrets.choice, written mode 0600 under {SECRETS_DIR}/ (gitignored). "
         "The admin password is step 4's, not generated here.")
    SECRETS_DIR.mkdir(mode=0o700, parents=True)
    pws = {}
    for role in HUB_ENV_KEYS:
        pws[role] = new_password()
        f = SECRETS_DIR / f"{role}.pw"
        f.touch(mode=0o600)
        f.write_text(pws[role] + "\n")
    print(f"  written: {', '.join(p.name for p in sorted(SECRETS_DIR.iterdir()))}")
    return pws


OWNERSHIP_SQL = r"""
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'glitchtip') THEN CREATE ROLE glitchtip LOGIN; END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'postgres_exporter') THEN CREATE ROLE postgres_exporter LOGIN; END IF;
END $$;
GRANT pg_monitor TO postgres_exporter;
ALTER DATABASE glitchtip OWNER TO glitchtip;
\c glitchtip
BEGIN;
ALTER SCHEMA public OWNER TO glitchtip;
DO $$ DECLARE r record; BEGIN
  FOR r IN SELECT format('ALTER %s %I.%I OWNER TO glitchtip',
             CASE c.relkind WHEN 'S' THEN 'SEQUENCE' WHEN 'v' THEN 'VIEW' WHEN 'm' THEN 'MATERIALIZED VIEW'
                            WHEN 'f' THEN 'FOREIGN TABLE' WHEN 'c' THEN 'TYPE' ELSE 'TABLE' END, n.nspname, c.relname) AS q
           FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
           WHERE n.nspname = 'public' AND c.relkind IN ('r','p','S','v','m','f','c')
             AND NOT EXISTS (SELECT 1 FROM pg_depend d WHERE d.classid = 'pg_class'::regclass AND d.objid = c.oid AND d.deptype = 'e')
             AND NOT (c.relkind = 'S' AND EXISTS (SELECT 1 FROM pg_depend d
                       WHERE d.classid = 'pg_class'::regclass AND d.objid = c.oid
                         AND d.refclassid = 'pg_class'::regclass AND d.deptype IN ('a','i')))
  LOOP EXECUTE r.q; END LOOP;
  FOR r IN SELECT format('ALTER ROUTINE %s OWNER TO glitchtip', p.oid::regprocedure) AS q
           FROM pg_proc p WHERE p.pronamespace = 'public'::regnamespace
             AND NOT EXISTS (SELECT 1 FROM pg_depend d WHERE d.classid = 'pg_proc'::regclass AND d.objid = p.oid AND d.deptype = 'e')
  LOOP EXECUTE r.q; END LOOP;
  FOR r IN SELECT format('ALTER %s %s OWNER TO glitchtip', CASE t.typtype WHEN 'd' THEN 'DOMAIN' ELSE 'TYPE' END,
                         t.oid::regtype) AS q
           FROM pg_type t WHERE t.typnamespace = 'public'::regnamespace AND t.typtype IN ('e','d','r','m')
             AND NOT EXISTS (SELECT 1 FROM pg_depend d WHERE d.classid = 'pg_type'::regclass AND d.objid = t.oid AND d.deptype = 'e')
  LOOP EXECUTE r.q; END LOOP;
END $$;
COMMIT;
"""

OWNERSHIP_CHECK = r"""
select count(*) from pg_class c where relnamespace='public'::regnamespace and relowner <> 'glitchtip'::regrole
  and not exists (select 1 from pg_depend d where d.classid='pg_class'::regclass and d.objid=c.oid and d.deptype='e');
select count(*) from pg_proc p  where pronamespace='public'::regnamespace and proowner <> 'glitchtip'::regrole
  and not exists (select 1 from pg_depend d where d.classid='pg_proc'::regclass and d.objid=p.oid and d.deptype='e');
select count(*) from pg_type t  where typnamespace='public'::regnamespace and typtype in ('e','d','r','m') and typowner <> 'glitchtip'::regrole
  and not exists (select 1 from pg_depend d where d.classid='pg_type'::regclass and d.objid=t.oid and d.deptype='e');
"""


def step3a_roles() -> None:
    gate("Step 3a — create the two roles (no password yet) and re-own GlitchTip's schema",
         "Runs the runbook's step-3 SQL on stdin, then asserts the three ownership counts are 0.")
    sql(OWNERSHIP_SQL)
    counts = sql(OWNERSHIP_CHECK, db="glitchtip").split()
    print(f"  ownership counts (class, routine, type): {counts}")
    if counts != ["0", "0", "0"]:
        die("an object in glitchtip.public is still not owned by glitchtip")


def step3b_set_passwords(pws: dict[str, str], iterations: int) -> None:
    gate("Step 3b — set both passwords from a verifier, assert, and log in once over TCP",
         "ALTER ROLE … PASSWORD '<SCRAM verifier>' on stdin; assert pg_authid holds it; one TCP login per role "
         "via a umask-077 pgpass that is removed and checked gone.")
    for role, pw in pws.items():
        v = verifier(pw, iterations)
        sql(f"ALTER ROLE {role} PASSWORD '{v}';")
        same = sql(f"select rolpassword = '{v}' from pg_authid where rolname = '{role}';")
        if same != "t":
            die(f"pg_authid does not hold the verifier just set for {role}")
        db = "glitchtip" if role == "glitchtip" else "postgres"
        probe = ("umask 077; f=$(mktemp); cat > \"$f\"; "
                 f"PGPASSFILE=\"$f\" psql -X -w -h postgres-main -U {role} -d {db} -tAc 'select current_user'; "
                 "rc=$?; rm -f \"$f\"; test ! -e \"$f\" || rc=9; exit $rc")
        who = remote(f"sudo docker exec -i postgres-main sh -c {shlex.quote(probe)}",
                     stdin=f"postgres-main:5432:{db}:{role}:{pw}\n")
        if who != role:
            die(f"TCP login as {role} did not return {role}")
        print(f"  {role}: verifier stored, TCP login OK, probe pgpass removed")


def step3c_move(pws: dict[str, str]) -> None:
    for role, db, cdir, key, old, count, svcs in SERVICES:
        gate(f"Step 3c — move {', '.join(svcs)} onto `{role}`",
             f"Back up {cdir}/compose.yaml and {cdir}/.env; append {key} to {cdir}/.env (0600); replace the {count} "
             f"old superuser DSN(s) with ${{{key}}}; assert `docker compose config` resolves to {role}@…/{db}; "
             f"then `docker compose up -d {' '.join(svcs)}`.")
        q = shlex.quote
        remote(f"cd {cdir} && sudo cp -p compose.yaml compose.yaml.backup.{STAMP} && "
               f"if sudo test -e .env; then sudo cp -p .env .env.backup.{STAMP}; fi")
        if remote(f"cd {cdir} && sudo grep -c '^{key}=' .env 2>/dev/null || true") not in ("", "0"):
            die(f"{cdir}/.env already defines {key}")
        dsn = old.replace("postgres:postgres@", f"{role}:{pws[role]}@").replace("/postgres?", f"/{db}?")
        remote(f"cd {cdir} && sudo sh -c 'umask 077; touch .env; chmod 600 .env; cat >> .env'", stdin=f"{key}={dsn}\n")
        sed_old = re.sub(r"([./])", r"\\\1", old)  # GNU BRE: `?` is literal; `\?` would be an operator
        remote(f"cd {cdir} && sudo sed -i {q('s/' + sed_old + '/${' + key + '}/g')} compose.yaml")
        rendered = remote(f"cd {cdir} && sudo docker compose config")
        scoped = len(re.findall(rf"://{role}:[^@\s]+@postgres-main:5432/{db}\b", rendered))
        if scoped != count or old in rendered:
            remote(f"cd {cdir} && sudo cp -p compose.yaml.backup.{STAMP} compose.yaml && "
                   f"if sudo test -e .env.backup.{STAMP}; then sudo cp -p .env.backup.{STAMP} .env; "
                   "else sudo rm -f .env; fi")
            die(f"{cdir}: compose config resolves {scoped} scoped DSN(s), expected {count} — files restored")
        print(f"  {cdir}: compose config resolves {scoped}x {role}@postgres-main:5432/{db} — OK")
        remote(f"cd {cdir} && sudo docker compose up -d {' '.join(svcs)}")
        print(f"  {', '.join(svcs)} recreated. Rollback: restore compose.yaml.backup.{STAMP} (and .env) then up -d.")


def step3d_verify() -> None:
    gate("Step 3d — verify before step 4", "pg_stat_activity logins, GlitchTip /api/0/, Prometheus pg_up.")
    for _ in range(12):
        logins = sql("select string_agg(distinct usename, ',' order by usename) from pg_stat_activity "
                     "where client_addr is not null and usename in ('glitchtip','postgres_exporter');")
        if logins == "glitchtip,postgres_exporter":
            break
        time.sleep(10)
    print(f"  scoped TCP logins seen: {logins or 'none'}")
    left = sql("select count(*) from pg_stat_activity where usename = 'postgres' and client_addr is not null;")
    print(f"  TCP sessions still as postgres (should drain to 0 for these two services): {left}")
    code = remote("sudo docker exec -i glitchtip-web python -", stdin=_GLITCHTIP_STATUS, check=False)
    pg_up = remote("sudo docker exec prometheus wget -qO- 'http://localhost:9090/api/v1/query?query=pg_up'", check=False)
    values = re.findall(r'"value":\[[^]]*\]', pg_up) or [pg_up[:120]]
    print(f"  GlitchTip /api/0/: {code or 'no answer'}   pg_up: {values}")
    if logins != "glitchtip,postgres_exporter":
        die("not both scoped logins are connected — check the services' logs before going on")
    print("  Manual: send one test event to GlitchTip and confirm it lands; check per-database pg_* metrics.")


def step3e_hub_env(pws: dict[str, str]) -> None:
    env = HUB / ".env"
    gate("Step 3e — record both logins in the hub .env (D-1176)",
         f"cp {env} → {HUB}/backups/.env.backup.{STAMP}; append {', '.join(HUB_ENV_KEYS.values())}; chmod 600.")
    text = env.read_text()
    for k in HUB_ENV_KEYS.values():
        if re.search(rf"^{k}=", text, re.M):
            die(f"{env} already defines {k}")
    backup = HUB / "backups" / f".env.backup.{STAMP}"
    backup.touch(mode=0o600)
    backup.write_bytes(env.read_bytes())
    with env.open("a") as fh:
        if not text.endswith("\n"):
            fh.write("\n")
        for role, k in HUB_ENV_KEYS.items():
            fh.write(f"{k}={pws[role]}\n")
    env.chmod(0o600)
    print(f"  {env}: appended {', '.join(HUB_ENV_KEYS.values())} (values not shown); backup {backup}")


def main() -> None:
    if Path.cwd() != HUB:
        die(f"run from {HUB} (the hub main checkout), not {Path.cwd()}")
    block0_spoke_sweep()
    iterations = block1_settings()
    pws = step2_passwords()
    step3a_roles()
    step3b_set_passwords(pws, iterations)
    step3c_move(pws)
    step3d_verify()
    step3e_hub_env(pws)
    print("\nSteps 1-3 done. STOP: step 4 (the `postgres` password) waits for the weekly reset and the day-long watch.")


if __name__ == "__main__":
    main()
