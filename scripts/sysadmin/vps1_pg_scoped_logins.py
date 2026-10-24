#!/usr/bin/env python3
# AFTER-EDIT: docs/reference/vps1-postgres-admin-rotation-runbook.md
"""vps1 Postgres rotation, runbook steps 2-3 (with step 1's stop checks and spoke sweep): scoped logins.

Scoped logins for GlitchTip and postgres_exporter. Step 1's sweep of vps1 itself is not here (fleet ran it
read-only on 2026-10-23).

Operator-run (W-80983d8c; D-1176 go, D-1177 no-TTY verifier route). Run from the hub main checkout:

    cd /opt/fabrik && python3 -I scripts/sysadmin/vps1_pg_scoped_logins.py

Every block prints what it will do and waits for a typed `yes`; anything else stops the run. Step 4 (the
`postgres` password) is NOT here: it waits for the day-long watch the runbook asks for.

D-1177 conditions, all enforced below:
1. The verifier is built as libpq does (PBKDF2-HMAC-SHA-256, iterations from `show scram_iterations`, >= 4096,
   16-byte `secrets` salt, StoredKey/ServerKey). tests/test_vps1_pg_scoped_logins.py checks it against a verifier
   PostgreSQL itself made.
2. No cleartext password or verifier in argv, an env var, an echo or the output: both travel only on ssh stdin.
   The pg_authid assert compares sha256 digests, so only the ALTER ROLE statement carries the verifier — the same
   statement psql's `\\password` sends.
3. SQL goes on stdin to `psql -X -v ON_ERROR_STOP=1`, never `-c`. The one staged file (the login probe's pgpass)
   is umask 077, removed, then `test ! -e`.
4. Per role: assert the stored verifier, then one real TCP login on the scram host line — and a wrong password
   that must be refused, so the login proves a password was checked.

Re-runnable: each run makes new passwords and re-applies them everywhere (both roles, the hub .env, each moved
service's .env), so a run stopped half-way is finished by running it again. A failure inside a service move
restores that service's compose.yaml from this run's backup and brings it back up. For a service still on the old
DSN it restores the .env too; for one an earlier run moved it keeps the new .env, because step 3b already gave the
role this run's password.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
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
STAMP = f"{time.strftime('%Y%m%d-%H%M%S')}-{os.getpid()}"
SECRETS_DIR = HUB / "backups" / f"pg-rotation-{STAMP}"

# (role, database, live compose dir, env key, old literal in the live compose, its expected count, services)
SERVICES = [
    (
        "glitchtip",
        "glitchtip",
        "/opt/glitchtip",
        "GLITCHTIP_DATABASE_URL",
        "postgresql://postgres:postgres@postgres-main:5432/glitchtip",
        2,
        ["glitchtip-web", "glitchtip-worker"],
    ),
    (
        "postgres_exporter",
        "postgres",
        "/opt/monitoring",
        "POSTGRES_EXPORTER_DSN",
        "postgresql://postgres:postgres@postgres-main:5432/postgres?sslmode=disable",
        1,
        ["postgres-exporter"],
    ),
]
HUB_ENV_KEYS = {
    "glitchtip": "VPS1_PG_GLITCHTIP_PASSWORD",
    "postgres_exporter": "VPS1_PG_POSTGRES_EXPORTER_PASSWORD",
}

# The runbook's step-1 sweep pattern (runbook § 1), applied to the spokes; file names only.
SWEEP_PATTERN = r"postgres(ql)?://postgres:|user=postgres|-U postgres|PGPASSWORD|POSTGRES_PASSWORD"
_SWEEP_NOISE = re.compile(r"(/node_modules/|\.(md|j2|example)$|\.(bak|backup)[^/]*$)")

_DSN_SECRET = re.compile(r"(://[^:/@\s]+):[^@\s]*@")
_VERIFIER = re.compile(r"SCRAM-SHA-256\$[^'\s]+")
_LOOPBACK = {("127.0.0.1", "255.255.255.255"), ("::1", "ffff:ffff:ffff:ffff:ffff:ffff:ffff:ffff")}
_STATUS_PROBE = """import urllib.request as u, urllib.error as e
try:
    print(u.urlopen('http://localhost:8000/api/0/', timeout=10).status)
except e.HTTPError as x:
    print(x.code)
"""
_secrets_written = False


def mask(text: str) -> str:
    """Hide DSN passwords and SCRAM verifiers (psql echoes a failing statement in its error text)."""
    return _VERIFIER.sub("SCRAM-SHA-256$***", _DSN_SECRET.sub(r"\1:***@", text))


def die(msg: str) -> None:
    where = (
        (
            f"\nThe new passwords are in {SECRETS_DIR}/ (mode 0600). Running the script again re-applies fresh "
            "ones everywhere."
        )
        if _secrets_written
        else ""
    )
    print(f"\nSTOP: {mask(msg)}{where}", file=sys.stderr)
    sys.exit(1)


def gate(title: str, plan: str) -> None:
    print(f"\n=== {title} ===\n{plan}")
    try:
        answer = input("Type yes to run this block: ").strip()
    except EOFError:
        answer = ""
    if answer != "yes":
        die(f"not confirmed: {title} — nothing in this block ran")


def run(
    cmd: str, stdin: str | None = None, host: list[str] | None = None, timeout: int = 300
) -> subprocess.CompletedProcess[str]:
    """Run cmd on vps1 (or host). Secrets only ever ride on stdin; output is returned, never printed here."""
    try:
        return subprocess.run(
            (host or SSH) + [cmd], input=stdin, capture_output=True, text=True, timeout=timeout
        )
    except subprocess.TimeoutExpired:
        die(f"remote command timed out after {timeout}s: {cmd}")
    except OSError as exc:
        die(f"could not start ssh: {exc}")
    raise AssertionError("unreachable")


def remote(cmd: str, stdin: str | None = None, timeout: int = 300) -> str:
    r = run(cmd, stdin=stdin, timeout=timeout)
    if r.returncode != 0:
        die(f"remote command failed (rc {r.returncode}): {cmd}\n{r.stderr.strip()}")
    return r.stdout.strip()


def sql(text: str, db: str = "postgres") -> str:
    return remote(f"{PSQL} -d {shlex.quote(db)}", stdin=text)


def verifier(password: str, iterations: int, salt: bytes | None = None) -> str:
    salt = salt if salt is not None else secrets.token_bytes(16)
    salted = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations)
    client_key = hmac.new(salted, b"Client Key", hashlib.sha256).digest()
    stored_key = hashlib.sha256(client_key).digest()
    server_key = hmac.new(salted, b"Server Key", hashlib.sha256).digest()
    b64 = lambda b: base64.b64encode(b).decode()  # noqa: E731
    return f"SCRAM-SHA-256${iterations}:{b64(salt)}${b64(stored_key)}:{b64(server_key)}"


def new_password() -> str:
    return "".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(32))


def hba_problem(rules: list[list[str]]) -> str | None:
    """Judge pg_hba_file_rules rows [type, database, user_name, address, netmask, auth_method, error], rule order.

    The server parsed them, so no file path or line syntax is assumed. Returns the stop reason, or None.
    """
    for r in rules:
        if r[6]:
            return f"pg_hba has an unparsable rule: {r[6]}"
    first_local = next(
        (
            r
            for r in rules
            if r[0] == "local" and ({"all", "postgres"} & set(r[2].strip("{}").split(",")))
        ),
        None,
    )
    if first_local is None or first_local[5] != "trust" or first_local[1].strip("{}") != "all":
        return "the first `local` rule for postgres is not `local all … trust` — row 8's passwordless callers would break"
    for r in rules:
        if r[0].startswith("host") and r[5] == "trust" and (r[3], r[4]) not in _LOOPBACK:
            return f"a non-loopback `{r[0]} … trust` rule exists ({r[3]}/{r[4]}) — a different fix first"
    return None


def sweep_hits(listing: str) -> list[str]:
    return [p for p in listing.splitlines() if p.strip() and not _SWEEP_NOISE.search(p)]


def scoped_count(rendered: str, role: str, db: str) -> int:
    """How many DSNs in a rendered compose log in as role to database db on postgres-main."""
    return len(
        re.findall(
            rf"://{re.escape(role)}:[^@\s]+@postgres-main:5432/{re.escape(db)}(?![\w-])", rendered
        )
    )


def sweep_sh() -> str:
    """The sweep under sudo; its last line is `__grep_rc=<n>`, so a sudo that never ran grep prints no such line."""
    return f"grep -rIlE {shlex.quote(SWEEP_PATTERN)} /opt; echo __grep_rc=$?"


def sweep_result(out: str) -> list[str] | None:
    """The hits of a completed sweep (grep rc 0 or 1), or None when grep did not run or failed."""
    lines = out.splitlines()
    if not lines or lines[-1] not in ("__grep_rc=0", "__grep_rc=1"):
        return None
    return sweep_hits("\n".join(lines[:-1]))


def scoped_dsn(old: str, role: str, password: str) -> str:
    return old.replace("postgres:postgres@", f"{role}:{password}@", 1)


def sed_expr(old: str, key: str) -> str:
    """A GNU sed s/// replacing the literal old DSN with ${key}. BRE: `.` and `/` escaped; `?` is literal."""
    return "s/" + re.sub(r"([./])", r"\\\1", old) + "/${" + key + "}/g"


def env_upsert_sh(key: str) -> str:
    """sh that sets KEY=<the line on stdin> in ./.env (mode 0600), replacing any old KEY line, keeping the rest.

    `grep -v` ends every line it prints with a newline, so a .env whose last line has none is mended by the copy.
    """
    return (
        "set -e; umask 077; touch .env; chmod 600 .env; t=$(mktemp ./.env.XXXXXX); trap 'rm -f \"$t\"' EXIT; "
        f"grep -v '^{key}=' .env > \"$t\" || true; "
        'cat >> "$t"; cat "$t" > .env; rm -f "$t"'
    )


def pg_up_values(body: str) -> list[str]:
    try:
        return [r["value"][1] for r in json.loads(body)["data"]["result"]]
    except (ValueError, KeyError, TypeError, IndexError):
        return []


def verify_problems(logins: str, left: str, code: str, up: list[str]) -> list[str]:
    """Each verify-before-step-4 check the readings fail (runbook § 3, the bullets before step 4)."""
    problems = []
    if logins != "glitchtip,postgres_exporter":
        problems.append(f"scoped logins connected: {logins or 'none'}")
    if left != "0":
        problems.append(f"superuser sessions from the three containers: {left}")
    if not code.isdigit() or int(code) >= 500:
        problems.append(f"GlitchTip /api/0/ answered {code or 'nothing'}")
    if not up or any(v != "1" for v in up):
        problems.append(f"pg_up: {up or 'no series'}")
    return problems


def service_state(old_count: int, ref_count: int, expected: int) -> str | None:
    """'fresh' (still on the superuser DSN), 'moved' (an earlier run moved it), or None (neither: stop)."""
    if old_count == expected and ref_count == 0:
        return "fresh"
    if old_count == 0 and ref_count == expected:
        return "moved"
    return None


def block0_spoke_sweep() -> None:
    gate(
        "Block 0 — spoke sweep (read-only, gate W-6610ceac)",
        "On vps2 and vps3: list files under /opt matching the runbook's step-1 superuser pattern (NAMES only).",
    )
    for name in ("vps2", "vps3"):
        r = run(
            f"sudo -n sh -c {shlex.quote(sweep_sh())}",
            host=["ssh", "-o", "ConnectTimeout=20", name],
        )
        hits = sweep_result(r.stdout)
        if hits is None:
            die(f"{name}: the sweep did not complete (rc {r.returncode}): {r.stderr.strip()[:300]}")
        print(f"  {name}: {len(hits)} hit(s)" + "".join(f"\n    {h}" for h in hits))
        if hits:
            die(
                f"{name} holds files that can log in as the superuser — add them to the runbook's consumer table "
                "and decide each one before going on"
            )


def block1_settings() -> tuple[int, dict[str, str]]:
    gate(
        "Block 1 — vps1 settings and stop checks (read-only)",
        "server_version, scram_iterations, password_encryption, pg_hba rules, each live compose's state.",
    )
    print("  server_version:", sql("show server_version;"))
    iterations = int(sql("show scram_iterations;"))
    enc = sql("show password_encryption;")
    print(f"  scram_iterations: {iterations}  password_encryption: {enc}")
    if iterations < 4096 or enc != "scram-sha-256":
        die("scram_iterations < 4096 or password_encryption is not scram-sha-256")
    raw = sql(
        "select type, array_to_string(database, ','), array_to_string(user_name, ','), coalesce(address, ''), "
        "coalesce(netmask, ''), coalesce(auth_method, ''), coalesce(error, '') "
        "from pg_hba_file_rules order by rule_number;"
    )
    problem = hba_problem([line.split("|") for line in raw.splitlines() if line])
    if problem:
        die(problem)
    print("  pg_hba: first local rule for postgres is trust; host trust on loopback only — OK")
    states = {}
    for role, _db, cdir, key, old, count, _svcs in SERVICES:
        if remote(f"sudo test -f {cdir}/compose.yaml && echo ok || echo missing") != "ok":
            die(f"{cdir}/compose.yaml does not exist on vps1")
        old_n = int(remote(f"sudo grep -oF {shlex.quote(old)} {cdir}/compose.yaml | wc -l"))
        ref_n = int(
            remote(f"sudo grep -oF {shlex.quote('${' + key + '}')} {cdir}/compose.yaml | wc -l")
        )
        state = service_state(old_n, ref_n, count)
        print(
            f"  {cdir}/compose.yaml: old DSN {old_n}x, ${{{key}}} {ref_n}x (expected {count}) — {state or 'MIXED'}"
        )
        if state is None:
            die(f"{cdir}/compose.yaml is neither on the old DSN nor moved — inspect it by hand")
        states[role] = state
    return iterations, states


def step2_passwords() -> dict[str, str]:
    global _secrets_written
    gate(
        "Step 2 — generate the two scoped passwords",
        f"32 chars [a-zA-Z0-9] via secrets.choice, written mode 0600 under {SECRETS_DIR}/ (gitignored). "
        "The admin password is step 4's, not generated here.",
    )
    SECRETS_DIR.mkdir(mode=0o700, parents=True)
    pws = {}
    for role in HUB_ENV_KEYS:
        pws[role] = new_password()
        fd = os.open(SECRETS_DIR / f"{role}.pw", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as fh:
            fh.write(pws[role] + "\n")
    _secrets_written = True
    print(f"  written: {', '.join(p.name for p in sorted(SECRETS_DIR.iterdir()))}")
    return pws


OWNERSHIP_SQL = r"""
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'glitchtip') THEN CREATE ROLE glitchtip LOGIN; END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'postgres_exporter') THEN CREATE ROLE postgres_exporter LOGIN; END IF;
END $$;
GRANT pg_monitor TO postgres_exporter;
SELECT format('GRANT CONNECT ON DATABASE %I TO postgres_exporter', datname)
  FROM pg_database WHERE NOT datistemplate AND NOT has_database_privilege('public', oid, 'CONNECT') \gexec
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
    gate(
        "Step 3a — create the two roles (no password yet), grant the exporter, re-own GlitchTip's schema",
        "Runs the runbook's step-3 SQL on stdin (CONNECT granted on every database PUBLIC lacks it on), then "
        "asserts the three ownership counts are 0.",
    )
    sql(OWNERSHIP_SQL)
    counts = sql(OWNERSHIP_CHECK, db="glitchtip").split()
    print(f"  ownership counts (class, routine, type): {counts}")
    if counts != ["0", "0", "0"]:
        die("an object in glitchtip.public is still not owned by glitchtip")


def _login(role: str, db: str, password: str) -> subprocess.CompletedProcess[str]:
    """One TCP login to postgres-main as role (a non-loopback address, so the scram host line). The pgpass line
    arrives on stdin's first line; the query is the rest of stdin."""
    probe = (
        'umask 077; f=$(mktemp); IFS= read -r line; printf \'%s\\n\' "$line" > "$f"; '
        f'PGPASSFILE="$f" psql -X -w -q -tA -h postgres-main -U {role} -d {db}; '
        'rc=$?; rm -f "$f"; test ! -e "$f" || rc=9; exit $rc'
    )
    return run(
        f"sudo docker exec -i postgres-main sh -c {shlex.quote(probe)}",
        stdin=f"postgres-main:5432:{db}:{role}:{password}\nselect current_user;\n",
    )


def step3b_set_passwords(pws: dict[str, str], iterations: int) -> None:
    gate(
        "Step 3b — set both passwords from a verifier, assert, and prove a TCP login",
        "ALTER ROLE … PASSWORD '<SCRAM verifier>' on stdin; assert pg_authid holds it (sha256 compare); one TCP "
        "login per role must succeed and one with a wrong password must be refused.",
    )
    for role, pw in pws.items():
        v = verifier(pw, iterations)
        sql(f"ALTER ROLE {role} PASSWORD '{v}';")
        digest = hashlib.sha256(v.encode()).hexdigest()
        same = sql(
            f"select encode(sha256(convert_to(rolpassword, 'UTF8')), 'hex') = '{digest}' "
            f"from pg_authid where rolname = '{role}';"
        )
        if same != "t":
            die(f"pg_authid does not hold the verifier just set for {role}")
        db = "glitchtip" if role == "glitchtip" else "postgres"
        ok = _login(role, db, pw)
        if ok.returncode != 0 or ok.stdout.strip() != role:
            die(f"TCP login as {role} failed (rc {ok.returncode}): {ok.stderr.strip()[:300]}")
        bad = _login(role, db, new_password())
        if bad.returncode == 0 or "password authentication failed" not in bad.stderr:
            die(
                f"a WRONG password for {role} was not refused — the TCP login does not check passwords"
            )
        print(
            f"  {role}: verifier stored, TCP login OK, wrong password refused, probe pgpass removed"
        )


def step3c_record_hub(pws: dict[str, str]) -> None:
    env = HUB / ".env"
    gate(
        "Step 3c — record both logins in the hub .env (D-1176)",
        f"cp {env} → {HUB}/backups/.env.backup.{STAMP} (0600); set {', '.join(HUB_ENV_KEYS.values())} "
        "(replacing an earlier run's values); chmod 600.",
    )
    text = env.read_text()
    backup = HUB / "backups" / f".env.backup.{STAMP}"
    fd = os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as fh:
        fh.write(text)
    kept = [
        ln
        for ln in text.splitlines()
        if not any(ln.startswith(f"{k}=") for k in HUB_ENV_KEYS.values())
    ]
    kept += [f"{k}={pws[role]}" for role, k in HUB_ENV_KEYS.items()]
    # staged under the gitignored backups/ (same filesystem): a crash strands no secret in the hub root
    tmp = HUB / "backups" / f".env.tmp.{STAMP}"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as fh:
        fh.write("\n".join(kept) + "\n")
    os.replace(tmp, env)  # atomic: a crash leaves the old .env or the new one, never half of it
    print(f"  {env}: set {', '.join(HUB_ENV_KEYS.values())} (values not shown); backup {backup}")


def step3d_move(pws: dict[str, str], states: dict[str, str]) -> None:
    for role, db, cdir, key, old, count, svcs in SERVICES:
        fresh = states[role] == "fresh"
        gate(
            f"Step 3d — move {', '.join(svcs)} onto `{role}` ({states[role]})",
            f"Back up {cdir}/compose.yaml and {cdir}/.env; set {key} in {cdir}/.env (0600)"
            + (f"; replace the {count} old superuser DSN(s) with ${{{key}}}" if fresh else "")
            + f"; assert `docker compose config` resolves to {role}@…/{db}; `docker compose up -d {' '.join(svcs)}`. "
            + (
                "On any failure both files are restored and the services brought back up on them."
                if fresh
                else "On any failure compose.yaml is restored and the services brought back up on the NEW .env: "
                "step 3b already gave the role this run's password, so the old .env would be refused."
            ),
        )
        bak = f".backup.{STAMP}"
        remote(
            f"cd {cdir} && sudo cp -p compose.yaml compose.yaml{bak} && "
            f"if sudo test -e .env; then sudo cp -p .env .env{bak}; fi"
        )
        up = f"cd {cdir} && sudo docker compose up -d {' '.join(svcs)}"
        done = False
        try:
            remote(
                f"cd {cdir} && sudo sh -c {shlex.quote(env_upsert_sh(key))}",
                stdin=scoped_dsn(old, role, pws[role]) + "\n",
            )
            if fresh:
                remote(f"cd {cdir} && sudo sed -i {shlex.quote(sed_expr(old, key))} compose.yaml")
            rendered = remote(f"cd {cdir} && sudo docker compose config")
            scoped = scoped_count(rendered, role, db)
            if scoped != count or old in rendered:
                die(
                    f"{cdir}: compose config resolves {scoped} scoped DSN(s) to {role}@…/{db}, expected {count}"
                )
            print(
                f"  {cdir}: compose config resolves {scoped}x {role}@postgres-main:5432/{db} — OK"
            )
            remote(up, timeout=900)
            done = True
        finally:
            if not done:
                restore_env = (
                    f"if sudo test -e .env{bak}; then sudo cp -p .env{bak} .env; else sudo rm -f .env; fi && "
                    if fresh
                    else ""
                )
                r = run(
                    f"cd {cdir} && sudo cp -p compose.yaml{bak} compose.yaml && {restore_env}"
                    f"sudo docker compose up -d {' '.join(svcs)}",
                    timeout=900,
                )
                print(
                    f"  RESTORED {cdir} ({'compose.yaml and .env' if fresh else 'compose.yaml; .env kept'}) from "
                    f"*{bak} and brought {', '.join(svcs)} back up: "
                    f"{'OK' if r.returncode == 0 else 'FAILED rc ' + str(r.returncode) + ' — restore by hand'}",
                    file=sys.stderr,
                )
        print(f"  {', '.join(svcs)} recreated; backups {cdir}/*{bak}")


def step3e_verify() -> None:
    gate(
        "Step 3e — verify before step 4",
        "scoped logins, no superuser session from the three containers, "
        "GlitchTip /api/0/ answers, Prometheus pg_up is 1.",
    )
    ips = remote(
        "sudo docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}} {{end}}' "
        "glitchtip-web glitchtip-worker postgres-exporter"
    ).split()
    ips = [ip for ip in ips if re.fullmatch(r"[0-9a-f.:]+", ip)]
    if len(ips) != 3:
        die(f"expected one address for each of the three containers, got {len(ips)}")
    ip_list = ",".join(f"'{ip}'" for ip in ips)
    for _ in range(18):
        logins = sql(
            "select string_agg(distinct usename, ',' order by usename) from pg_stat_activity "
            "where client_addr is not null and usename in ('glitchtip','postgres_exporter');"
        )
        left = sql(
            f"select count(*) from pg_stat_activity where usename = 'postgres' and host(client_addr) in ({ip_list});"
        )
        code = run(
            "sudo docker exec -i glitchtip-web sh -c 'python3 - 2>/dev/null || python -'",
            stdin=_STATUS_PROBE,
        ).stdout.strip()
        up = pg_up_values(
            run(
                "sudo docker exec prometheus wget -qO- 'http://localhost:9090/api/v1/query?query=pg_up'"
            ).stdout
        )
        problems = verify_problems(logins, left, code, up)
        if not problems:
            break
        time.sleep(10)
    print(
        f"  scoped TCP logins: {logins or 'none'}; superuser sessions from the three containers: {left}; "
        f"GlitchTip /api/0/: HTTP {code or 'no answer'}; pg_up: {up or 'no series'}"
    )
    if problems:
        die("verify failed after 3 minutes: " + "; ".join(problems))
    print(
        "  Manual before step 4: send one test event to GlitchTip and confirm it lands; check per-database pg_* "
        "metrics in Prometheus for every database."
    )


def main() -> None:
    if Path.cwd() != HUB:
        die(f"run from {HUB} (the hub main checkout), not {Path.cwd()}")
    block0_spoke_sweep()
    iterations, states = block1_settings()
    pws = step2_passwords()
    step3a_roles()
    step3b_set_passwords(pws, iterations)
    step3c_record_hub(pws)
    step3d_move(pws, states)
    step3e_verify()
    print("\nSteps 1-3 done. STOP: step 4 (the `postgres` password) waits for the day-long watch.")


if __name__ == "__main__":
    main()
