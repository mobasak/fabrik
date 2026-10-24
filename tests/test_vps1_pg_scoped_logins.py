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
