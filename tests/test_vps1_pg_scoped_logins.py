"""Behaviours of scripts/sysadmin/vps1_pg_scoped_logins.py that hold without a server (W-80983d8c, D-1177)."""

from __future__ import annotations

import base64
import importlib.util
import os
import stat
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "sysadmin" / "vps1_pg_scoped_logins.py"
_spec = importlib.util.spec_from_file_location("vps1_pg_scoped_logins_under_test", SCRIPT)
m = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(m)

# A verifier PostgreSQL 16.15 itself stored for the public RFC 7677 test password "pencil" (CREATE ROLE … PASSWORD).
PG_PENCIL = (
    "SCRAM-SHA-256$4096:sAobBWNjoAP3eYdfJ8T+Ag==$k8FLa++L0VNU1IxAkfdV5HAAun4dHU5D2UloeZPhcfQ="
    ":ffuB4a5706wV3YNnXbokyGs2NTn9buEncBSYjJUOnBE="
)

GT_OLD, GT_KEY = m.SERVICES[0][4], m.SERVICES[0][3]
EX_OLD, EX_KEY = m.SERVICES[1][4], m.SERVICES[1][3]


def test_the_verifier_equals_the_one_postgres_stores():
    salt = base64.b64decode(PG_PENCIL.split("$")[1].split(":")[1])
    assert m.verifier("pencil", 4096, salt) == PG_PENCIL


def test_the_verifier_salts_with_sixteen_fresh_bytes_and_the_given_iterations():
    a, b = m.verifier("pencil", 8192), m.verifier("pencil", 8192)
    assert a != b and a.startswith("SCRAM-SHA-256$8192:")
    assert len(base64.b64decode(a.split("$")[1].split(":")[1])) == 16


def test_mask_hides_dsn_passwords_and_verifiers():
    out = m.mask(
        f"ERROR at ALTER ROLE x PASSWORD '{PG_PENCIL}'; DSN postgresql://glitchtip:s3cr3t@postgres-main:5432/g"
    )
    assert "s3cr3t" not in out and "k8FLa" not in out and "sAobB" not in out
    assert m.mask("postgresql://u@h/db") == "postgresql://u@h/db"


def test_die_masks_its_message(capsys):
    with pytest.raises(SystemExit):
        m.die("failed: postgresql://glitchtip:s3cr3t@postgres-main:5432/glitchtip")
    assert "s3cr3t" not in capsys.readouterr().err


def test_new_password_is_32_alphanumerics():
    pw = m.new_password()
    assert len(pw) == 32 and pw.isalnum() and pw.isascii()


def _rule(t, db, user, addr, mask, method, err=""):
    return [t, db, user, addr, mask, method, err]


LIVE_HBA = [
    _rule("local", "all", "all", "", "", "trust"),
    _rule("host", "all", "all", "127.0.0.1", "255.255.255.255", "trust"),
    _rule("host", "all", "all", "::1", "ffff:ffff:ffff:ffff:ffff:ffff:ffff:ffff", "trust"),
    _rule("local", "replication", "all", "", "", "trust"),
    _rule("host", "all", "all", "", "", "scram-sha-256"),
    _rule("host", "all", "all", "172.16.0.0", "255.240.0.0", "md5"),
]


def test_the_live_vps1_hba_passes():
    assert m.hba_problem(LIVE_HBA) is None


@pytest.mark.parametrize("kind", ["host", "hostssl", "hostnossl", "hostgssenc"])
def test_a_non_loopback_trust_rule_of_any_host_type_stops(kind):
    assert "non-loopback" in m.hba_problem(
        [*LIVE_HBA, _rule(kind, "all", "all", "10.0.0.0", "255.0.0.0", "trust")]
    )


def test_a_local_rule_shadowing_trust_for_postgres_stops():
    shadow = [_rule("local", "all", "postgres", "", "", "peer"), *LIVE_HBA]
    assert "first `local` rule" in m.hba_problem(shadow)


def test_an_unparsable_hba_rule_stops():
    assert "unparsable" in m.hba_problem(
        [*LIVE_HBA, _rule("host", "", "", "", "", "", "invalid IP")]
    )


def test_sweep_hits_drop_only_docs_templates_examples_and_backups():
    listing = "\n".join(
        [
            "/opt/a/.env",
            "/opt/a/README.md",
            "/opt/a/x.j2",
            "/opt/a/.env.example",
            "/opt/a/compose.yaml.bak-1",
            "/opt/a/compose.yaml.backup.2",
            "/opt/backup-runner/.env",
            "/opt/a/node_modules/p/x.js",
            "",
        ]
    )
    assert m.sweep_hits(listing) == ["/opt/a/.env", "/opt/backup-runner/.env"]


def test_scoped_dsn_swaps_only_the_credentials():
    assert (
        m.scoped_dsn(EX_OLD, "postgres_exporter", "pw")
        == "postgresql://postgres_exporter:pw@postgres-main:5432/postgres?sslmode=disable"
    )
    assert (
        m.scoped_dsn(GT_OLD, "glitchtip", "pw")
        == "postgresql://glitchtip:pw@postgres-main:5432/glitchtip"
    )


def test_the_sed_expression_rewrites_each_mirror_dsn_with_real_sed(tmp_path):
    for mirror, old, key, n in (
        ("glitchtip", GT_OLD, GT_KEY, 2),
        ("monitoring", EX_OLD, EX_KEY, 1),
    ):
        f = tmp_path / f"{mirror}.yaml"
        f.write_text((ROOT / "infra" / "vps1" / mirror / "compose.yaml").read_text())
        subprocess.run(["sed", "-i", m.sed_expr(old, key), str(f)], check=True)
        text = f.read_text()
        assert old not in text and text.count("${" + key + "}") == n


def _upsert(tmp_path: Path, key: str, line: str) -> None:
    subprocess.run(
        ["sh", "-c", m.env_upsert_sh(key)], input=line, text=True, cwd=tmp_path, check=True
    )


def test_env_upsert_replaces_the_key_keeps_the_rest_and_fixes_a_missing_newline(tmp_path):
    env = tmp_path / ".env"
    env.write_text(f"A=1\n{GT_KEY}=old\nB=2")  # no final newline
    env.chmod(0o644)
    _upsert(tmp_path, GT_KEY, f"{GT_KEY}=new\n")
    assert env.read_text() == f"A=1\nB=2\n{GT_KEY}=new\n"
    assert stat.S_IMODE(env.stat().st_mode) == 0o600
    assert not list(tmp_path.glob(".env.*"))  # the mktemp file is gone


def test_env_upsert_creates_a_missing_env_mode_0600(tmp_path):
    _upsert(tmp_path, EX_KEY, f"{EX_KEY}=v\n")
    env = tmp_path / ".env"
    assert env.read_text() == f"{EX_KEY}=v\n" and stat.S_IMODE(env.stat().st_mode) == 0o600


def test_service_state_reads_fresh_moved_or_mixed():
    assert m.service_state(2, 0, 2) == "fresh"
    assert m.service_state(0, 2, 2) == "moved"
    assert m.service_state(1, 1, 2) is None and m.service_state(0, 0, 2) is None


def test_pg_up_values_reads_the_prometheus_answer():
    body = '{"status":"success","data":{"result":[{"metric":{},"value":[1.0,"1"]},{"metric":{},"value":[1.0,"0"]}]}}'
    assert m.pg_up_values(body) == ["1", "0"]
    assert m.pg_up_values("not json") == [] and m.pg_up_values('{"data":{}}') == []


class _Fake:
    """Stands in for ssh: records each remote command and fails the first one containing `fail_on`.

    `docker compose config` renders the service's own two (glitchtip) or one (exporter) scoped DSNs.
    """

    def __init__(self, fail_on: str):
        self.calls: list[str] = []
        self.fail_on = fail_on

    def __call__(self, cmd, stdin=None, host=None, timeout=300):
        self.calls.append(cmd)
        failed = self.fail_on in cmd and not any(self.fail_on in c for c in self.calls[:-1])
        out = ""
        if "compose config" in cmd:
            out = (
                "a: postgresql://glitchtip:p@postgres-main:5432/glitchtip\nb: postgresql://glitchtip:p@postgres-main:5432/glitchtip\n"
                if "/opt/glitchtip" in cmd
                else "c: postgresql://postgres_exporter:q@postgres-main:5432/postgres?sslmode=disable\n"
            )
        return subprocess.CompletedProcess(cmd, 1 if failed else 0, out, "boom" if failed else "")


def _move(monkeypatch, fail_on, state):
    fake = _Fake(fail_on)
    monkeypatch.setattr(m, "run", fake)
    monkeypatch.setattr(m, "gate", lambda *a: None)
    pws = {"glitchtip": "p", "postgres_exporter": "q"}
    m.step3d_move(pws, {"glitchtip": state, "postgres_exporter": state})
    return fake


@pytest.mark.parametrize(
    "fail_on", ["sh -c", "sed -i", "compose config", "compose up -d glitchtip-web glitchtip-worker"]
)
def test_a_failed_fresh_move_restores_both_files_and_restarts(monkeypatch, fail_on):
    with pytest.raises(SystemExit):
        _move(monkeypatch, fail_on, "fresh")
    fake = m.run
    restore = [c for c in fake.calls if "cp -p compose.yaml.backup." in c]
    assert len(restore) == 1 and restore[0].startswith("cd /opt/glitchtip")
    assert "sudo cp -p .env.backup." in restore[0]
    assert restore[0].endswith("docker compose up -d glitchtip-web glitchtip-worker")
    assert not any("/opt/monitoring" in c for c in fake.calls)


def test_a_failed_moved_rerun_keeps_the_new_env(monkeypatch):
    with pytest.raises(SystemExit):
        _move(monkeypatch, "compose config", "moved")
    restore = [c for c in m.run.calls if "cp -p compose.yaml.backup." in c]
    assert len(restore) == 1 and ".env.backup" not in restore[0].split("compose.yaml && ", 1)[1]
    assert restore[0].endswith("docker compose up -d glitchtip-web glitchtip-worker")


def test_a_successful_move_restores_nothing_and_skips_sed_when_moved(monkeypatch):
    fake = _move(monkeypatch, "never-matches", "moved")
    assert not any("cp -p compose.yaml.backup." in c for c in fake.calls)
    assert not any("sed -i" in c for c in fake.calls)
    assert sum("docker compose up -d" in c for c in fake.calls) == 2


def test_no_secret_reaches_any_remote_command_line(monkeypatch):
    fake = _Fake("never-matches")
    monkeypatch.setattr(m, "run", fake)
    monkeypatch.setattr(m, "gate", lambda *a: None)
    pws = {"glitchtip": "GTSECRETGTSECRET", "postgres_exporter": "EXSECRETEXSECRET"}
    m.step3d_move(pws, {"glitchtip": "fresh", "postgres_exporter": "fresh"})
    assert fake.calls and not any(s in c for c in fake.calls for s in pws.values())


def test_scoped_count_checks_role_and_database():
    r = "postgresql://glitchtip:x@postgres-main:5432/glitchtip\npostgresql://glitchtip:x@postgres-main:5432/glitchtip_old\n"
    assert m.scoped_count(r, "glitchtip", "glitchtip") == 1
    assert (
        m.scoped_count(
            "postgresql://postgres_exporter:x@postgres-main:5432/postgres?sslmode=disable",
            "postgres_exporter",
            "postgres",
        )
        == 1
    )
    assert (
        m.scoped_count(
            "postgresql://glitchtip:x@postgres-main:5432/other", "glitchtip", "glitchtip"
        )
        == 0
    )


def test_the_sweep_needs_its_sentinel_and_a_grep_rc_of_0_or_1():
    assert m.sweep_result("/opt/a/.env\n__grep_rc=0") == ["/opt/a/.env"]
    assert m.sweep_result("__grep_rc=1") == []
    assert m.sweep_result("") is None  # sudo refused: grep never ran
    assert m.sweep_result("/opt/a/.env\n__grep_rc=2") is None
    out = subprocess.run(
        ["sh", "-c", m.sweep_sh().replace("/opt", "/nonexistent-sweep-probe")],
        capture_output=True,
        text=True,
    ).stdout
    assert m.sweep_result(out) is None  # grep rc 2 on a missing directory


def test_verify_problems_names_each_failed_check():
    assert m.verify_problems("glitchtip,postgres_exporter", "0", "200", ["1", "1"]) == []
    assert m.verify_problems("glitchtip,postgres_exporter", "0", "401", ["1"]) == []
    assert len(m.verify_problems("glitchtip", "2", "", [])) == 4
    assert m.verify_problems("glitchtip,postgres_exporter", "0", "502", ["1", "0"]) == [
        "GlitchTip /api/0/ answered 502",
        "pg_up: ['1', '0']",
    ]


def test_step2_writes_each_password_file_mode_0600(monkeypatch, tmp_path):
    monkeypatch.setattr(m, "SECRETS_DIR", tmp_path / "s")
    monkeypatch.setattr(m, "gate", lambda *a: None)
    old = os.umask(0)
    try:
        pws = m.step2_passwords()
    finally:
        os.umask(old)
    for role, pw in pws.items():
        f = tmp_path / "s" / f"{role}.pw"
        assert f.read_text() == pw + "\n" and stat.S_IMODE(f.stat().st_mode) == 0o600


def test_step3c_strands_nothing_in_the_hub_root_when_the_replace_fails(monkeypatch, tmp_path):
    """The new .env is staged under the gitignored backups/, so a crash never strands a secret in the hub root."""
    hub = tmp_path / "hub"  # tmp_path itself also holds the conftest's state dirs
    (hub / "backups").mkdir(parents=True)
    (hub / ".env").write_text("A=1\n")
    monkeypatch.setattr(m, "HUB", hub)
    monkeypatch.setattr(m, "gate", lambda *a: None)

    def boom(*a):
        raise OSError("replace failed")

    monkeypatch.setattr(m.os, "replace", boom)
    pws = dict.fromkeys(m.HUB_ENV_KEYS, "x" * 32)
    with pytest.raises(OSError):
        m.step3c_record_hub(pws)
    assert sorted(p.name for p in hub.iterdir()) == [".env", "backups"]
    assert (hub / ".env").read_text() == "A=1\n"


# Step 3a's re-own run against a real PostgreSQL 16 (vps1 runs 16.11): a throwaway cluster whose lock table is far too
# small for one transaction over GlitchTip's log partitions — the operator's 2026-10-28 run died there ("out of shared
# memory", W-80983d8c). max_locks_per_transaction=10 × max_connections=10 holds ~100 locks; 300 partitions with an index
# each need ~900 in one transaction.
PG_BIN = Path("/usr/lib/postgresql/16/bin")
PARTITIONS = 300


@pytest.fixture
def small_lock_cluster(tmp_path):
    if not (PG_BIN / "initdb").exists():
        pytest.skip("PostgreSQL 16 server binaries are not installed")
    data = tmp_path / "data"
    # an abstract socket (PostgreSQL >= 14, Linux): a socket FILE under a long pytest basetemp passes sun_path's
    # 107-byte limit and the server refuses to start
    sock = f"@pgtest-{os.getpid()}-{abs(hash(str(tmp_path)))}"
    subprocess.run(
        [PG_BIN / "initdb", "-U", "postgres", "-A", "trust", "-D", data],
        check=True,
        capture_output=True,
    )
    opts = (
        f"-c listen_addresses='' -c unix_socket_directories={sock} "
        "-c max_locks_per_transaction=10 -c max_connections=10"
    )
    subprocess.run(
        [PG_BIN / "pg_ctl", "-D", data, "-o", opts, "-w", "-l", tmp_path / "log", "start"],
        check=True,
        capture_output=True,
    )
    base = ["psql", "-X", "-q", "-h", sock, "-U", "postgres", "-v", "ON_ERROR_STOP=1", "-tA", "-d"]

    def psql(db: str, text: str, timeout: float = 120) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [*base, db], input=text, capture_output=True, text=True, timeout=timeout
        )

    try:
        assert psql("postgres", "CREATE DATABASE glitchtip;").returncode == 0
        ddl = [
            "CREATE TABLE logs (id bigserial, ts date NOT NULL, msg text) PARTITION BY RANGE (ts);"
        ]
        for i in range(PARTITIONS):
            ddl.append(
                f"CREATE TABLE logs_p{i} PARTITION OF logs "
                f"FOR VALUES FROM ('2000-01-01'::date + {i}) TO ('2000-01-01'::date + {i + 1});"
            )
            ddl.append(f"CREATE INDEX ON logs_p{i} (ts);")
        made = psql("glitchtip", "\n".join(ddl))
        assert made.returncode == 0, made.stderr
        yield psql, [*base, "glitchtip"]
    finally:
        subprocess.run(
            [PG_BIN / "pg_ctl", "-D", data, "-m", "immediate", "stop"], capture_output=True
        )


def test_step3a_reowns_every_partition_when_one_transaction_could_not_hold_their_locks(
    small_lock_cluster,
):
    psql, _ = small_lock_cluster
    run = psql("postgres", m.OWNERSHIP_SQL)
    assert run.returncode == 0, run.stderr
    assert psql("glitchtip", m.OWNERSHIP_CHECK).stdout.split() == ["0", "0", "0"]


def test_step3a_stops_on_a_busy_table_instead_of_queueing_glitchtip_and_a_rerun_finishes(
    small_lock_cluster,
):
    """A table GlitchTip holds open makes the re-own fail within lock_timeout (never a hang that queues every
    GlitchTip query behind an ACCESS EXCLUSIVE request); what it re-owned before stays, and a re-run finishes."""
    psql, holder_argv = small_lock_cluster
    holder = subprocess.Popen(holder_argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    try:
        holder.stdin.write("BEGIN;\nSELECT count(*) FROM logs_p150;\n")
        holder.stdin.flush()
        assert holder.stdout.readline().strip() == "0"  # the lock is held from here on
        run = psql("postgres", m.OWNERSHIP_SQL, timeout=60)
        assert run.returncode != 0 and "lock timeout" in run.stderr, run.stderr
        left = int(psql("glitchtip", m.OWNERSHIP_CHECK).stdout.split()[0])
        assert 0 < left < 2 * PARTITIONS + 2  # some objects were re-owned and committed, not all
    finally:
        holder.stdin.write("ROLLBACK;\n")
        holder.stdin.close()
        holder.wait(timeout=30)
    rerun = psql("postgres", m.OWNERSHIP_SQL)
    assert rerun.returncode == 0, rerun.stderr
    assert psql("glitchtip", m.OWNERSHIP_CHECK).stdout.split() == ["0", "0", "0"]


def test_step3a_rerun_on_an_owned_schema_locks_nothing(small_lock_cluster):
    """A re-run skips what glitchtip already owns, so a busy table that is already done (here the partitioned
    parent every GlitchTip query goes through) costs no lock wait and no failure."""
    psql, holder_argv = small_lock_cluster
    assert psql("postgres", m.OWNERSHIP_SQL).returncode == 0
    holder = subprocess.Popen(holder_argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    try:
        holder.stdin.write("BEGIN;\nLOCK TABLE ONLY logs IN ACCESS SHARE MODE;\nSELECT 1;\n")
        holder.stdin.flush()
        assert holder.stdout.readline().strip() == "1"  # the parent is held from here on
        rerun = psql("postgres", m.OWNERSHIP_SQL, timeout=60)
        assert rerun.returncode == 0, rerun.stderr
        assert psql("glitchtip", m.OWNERSHIP_CHECK).stdout.split() == ["0", "0", "0"]
    finally:
        holder.stdin.write("ROLLBACK;\n")
        holder.stdin.close()
        holder.wait(timeout=30)


def test_the_runbook_quotes_the_scripts_reown_block_word_for_word():
    """An operator running step 3 by hand from the runbook gets the same lock-safe re-own as the script."""
    runbook = (ROOT / "docs" / "reference" / "vps1-postgres-admin-rotation-runbook.md").read_text()
    block = m.OWNERSHIP_SQL[m.OWNERSHIP_SQL.index("\\c glitchtip\n") :]
    assert block in runbook
