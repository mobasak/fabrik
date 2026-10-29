"""Behaviours of scripts/sysadmin/vps1_cpu_limits.py that hold without vps1 (W-91a4a715 follow-up, D-1324).

The ssh transport is replaced by a fake that answers each remote command; the two shell scripts the apply sends
(the write and the restore) are run for real against local files, since `sh`, `sha256sum`, `stat` and `mktemp`
are the same tools vps1 runs.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import subprocess
from decimal import Decimal
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "sysadmin" / "vps1_cpu_limits.py"
_spec = importlib.util.spec_from_file_location("vps1_cpu_limits_under_test", SCRIPT)
m = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(m)

BLOCK = """services:
  web:
    image: x
    container_name: web-c
    deploy:
      resources:
        limits:
          memory: 64M  # keep this comment
"""
WANT = {"web": ("web-c", Decimal("0.5"), "0.5")}


def _hub(tmp_path: Path, files: dict[str, str]) -> Path:
    for rel, text in files.items():
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text(text)
    return tmp_path


def _capped(name: str, container: str, cpus: str) -> str:
    return (
        f"services:\n  {name}:\n    container_name: {container}\n"
        f"    deploy:\n      resources:\n        limits:\n          memory: 64M\n          cpus: {cpus}\n"
    )


# 1 — the table


def test_table_reads_the_real_hub_composes() -> None:
    """Given the repo's infra/vps1, when the table is built, then it holds D-1324's services with their text."""
    table = m.load_table()
    assert table["postgres-main"] == (Decimal("2.0"), "2.0")
    assert table["watchdog-test"] == (Decimal("0.25"), "0.25")
    assert table["n8n"] == (Decimal("1.0"), "1.0")  # double-quoted in its compose
    assert len(table) >= 22


@pytest.mark.parametrize("cpus", ["0_5", "yes", "'2.5'", "0", "'1e0'"])
def test_table_refuses_a_bad_cpus_text(tmp_path: Path, cpus: str) -> None:
    """Given a hub cpus that is not a plain decimal in (0, 2.0], when the table is built, then it is refused."""
    root = _hub(tmp_path, {"a/compose.yaml": _capped("a", "a-c", cpus)})
    with pytest.raises(m.RefusedError, match="not a plain decimal"):
        m.load_table(root)


def test_table_refuses_a_missing_or_repeated_container_name(tmp_path: Path) -> None:
    """Given a capped service without container_name, or two using one name, when built, then it is refused."""
    no_name = _capped("a", "a-c", "'1.0'").replace("    container_name: a-c\n", "")
    with pytest.raises(m.RefusedError, match="no container_name"):
        m.load_table(_hub(tmp_path / "1", {"a/compose.yaml": no_name}))
    twice = {
        "a/compose.yaml": _capped("a", "same", "'1.0'"),
        "b/compose.yaml": _capped("b", "same", "'1.0'"),
    }
    with pytest.raises(m.RefusedError, match="used twice"):
        m.load_table(_hub(tmp_path / "2", twice))


# 2 — the plans


def _record(
    name: str, nano: int = 0, quota: int = 0, period: int = 0, config: str | None = None
) -> dict:
    labels = {"com.docker.compose.service": name.removesuffix("-c")}
    if config is not None:
        labels["com.docker.compose.project.config_files"] = config
    return {
        "Name": f"/{name}",
        "HostConfig": {"NanoCpus": nano, "CpuQuota": quota, "CpuPeriod": period},
        "Config": {"Labels": labels},
    }


def test_plan_classifies_every_runtime_state() -> None:
    """Given unlimited, capped-equal, capped-other, quota-set, period-set and absent containers, when planned,
    then each reads UPDATE, OK, DIFFERS, DIFFERS, DIFFERS and MISSING."""
    table = {n: (Decimal("0.5"), "0.5") for n in ("u", "ok", "other", "quota", "period", "gone")}
    stdout = json.dumps(
        [
            _record("u"),
            _record("ok", nano=500_000_000),
            _record("other", nano=1_000_000_000),
            _record("quota", quota=50_000),
            _record("period", period=100_000),
        ]
    ).encode()
    states = {n: s for n, (s, _r) in m.runtime_plan(table, stdout).items()}
    assert states == {
        "u": "UPDATE",
        "ok": "OK",
        "other": "DIFFERS",
        "quota": "DIFFERS",
        "period": "DIFFERS",
        "gone": "MISSING",
    }


def test_plan_reads_an_all_missing_inspect_and_refuses_no_json() -> None:
    """Given docker's `[]` for all-missing names (rc 1, measured), then all are MISSING; given no JSON, refused."""
    assert m.runtime_plan({"a": (Decimal(1), "1")}, b"[]\n")["a"][0] == "MISSING"
    with pytest.raises(m.RefusedError):
        m.runtime_plan({"a": (Decimal(1), "1")}, b"Error: permission denied\n")


@pytest.mark.parametrize(
    ("label", "ok"),
    [
        ("/opt/gatus/compose.yaml", True),
        ("/opt/gatus/compose.yml", False),
        ("/opt/gatus/compose.yaml,/opt/gatus/compose.override.yaml", False),
        ("/opt/.hidden/compose.yaml", False),
        ("/opt/../compose.yaml", False),
        ("/opt/a/b/compose.yaml", False),
        ("/srv/gatus/compose.yaml", False),
        ("/opt/gatus/compose.yaml\n", False),
        (None, False),
    ],
)
def test_plan_marks_manual_every_label_the_boot_does_not_read(label: str | None, ok: bool) -> None:
    """Given a config_files label, when judged, then only one /opt/<non-dot dir>/compose.yaml is editable."""
    assert (m.boot_file(_record("x", config=label)) is not None) is ok


# 3 — insert_cpus


def test_insert_puts_the_line_under_memory_and_keeps_every_other_byte() -> None:
    """Given a block-style limits, when inserted, then `cpus: '0.5'` sits right under memory at its indent."""
    new, inserted = m.insert_cpus(BLOCK.encode(), WANT)
    assert inserted == ["web"]
    assert new.decode() == BLOCK + "          cpus: '0.5'\n"


def test_insert_handles_a_memory_line_with_no_trailing_newline() -> None:
    """Given a file whose last byte ends the memory line, when inserted, then a newline precedes the cpus line."""
    new, _ = m.insert_cpus(BLOCK.rstrip("\n").encode(), WANT)
    assert new.decode() == BLOCK + "          cpus: '0.5'"


def test_insert_is_a_no_op_on_an_equal_decimal() -> None:
    """Given cpus already `0.50`, when the table says 0.5, then nothing changes and nothing is reported."""
    data = (BLOCK + "          cpus: 0.50\n").encode()
    assert m.insert_cpus(data, WANT) == (data, [])


def test_insert_edits_two_services_of_one_file() -> None:
    """Given two services in one file, when both are wanted, then both get their own line."""
    text = (
        BLOCK
        + "  db:\n    container_name: db-c\n    deploy:\n      resources:\n        limits:\n          memory: 1G\n"
    )
    want = {**WANT, "db": ("db-c", Decimal("2.0"), "2.0")}
    new, inserted = m.insert_cpus(text.encode(), want)
    assert sorted(inserted) == ["db", "web"]
    assert new.decode().count("cpus: '") == 2
    assert new.decode().endswith("          memory: 1G\n          cpus: '2.0'\n")


@pytest.mark.parametrize(
    ("text", "reason"),
    [
        (BLOCK + "          cpus: '1.0'\n", "already has cpus"),
        (BLOCK + "          cpus: 0_5\n", "already has cpus"),
        (
            BLOCK.replace(
                "          memory: 64M  # keep this comment\n", "          {memory: 64M}\n"
            ).replace(
                "        limits:\n          {memory: 64M}\n", "        limits: {memory: 64M}\n"
            ),
            "flow mapping",
        ),
        (BLOCK.replace("memory: 64M  # keep this comment", "reservations: 1"), "no memory"),
        (BLOCK.replace("memory: 64M  # keep this comment", "memory:\n            64M"), "one-line"),
        (
            BLOCK.replace("memory: 64M  # keep this comment", "memory: >-\n            64M"),
            "one-line",
        ),
        (
            BLOCK.replace("    image: x\n", "    image: x\n    cpu_quota: 50000\n"),
            "service-level cpu_quota",
        ),
        (BLOCK.replace("    image: x\n", "    image: x\n    cpus: 1.5\n"), "service-level cpus"),
        (BLOCK.replace("container_name: web-c", "container_name: other"), "stale label"),
        (BLOCK.replace("  web:", "  api:"), "stale label"),
        (BLOCK.replace("\n", "\r\n"), "line breaks"),
        (BLOCK + "  web:\n    image: y\n", "duplicate key"),
        (BLOCK.replace("          memory", "          <<: {x: 1}\n          memory"), "merge key"),
    ],
)
def test_insert_refuses_what_it_cannot_prove_safe(text: str, reason: str) -> None:
    """Given each refused shape, when inserted, then the file is refused naming why."""
    with pytest.raises(m.RefusedError, match=reason):
        m.insert_cpus(text.encode(), WANT)


def test_insert_refuses_a_limits_shared_through_an_anchor() -> None:
    """Given a `limits: &l` reused by another service, or a shared `deploy: &d`, then the file is refused."""
    shared_limits = (
        "services:\n  web:\n    container_name: web-c\n    deploy:\n      resources:\n        limits: &l\n"
        "          memory: 64M\n  other:\n    deploy:\n      resources:\n        limits: *l\n"
    )
    shared_deploy = (
        "services:\n  other:\n    deploy: &d\n      resources:\n        limits:\n          memory: 64M\n"
        "  web:\n    container_name: web-c\n    deploy: *d\n"
    )
    for text in (shared_limits, shared_deploy):
        with pytest.raises(m.RefusedError, match="anchor or alias"):
            m.insert_cpus(text.encode(), WANT)


def test_insert_refuses_bytes_that_are_not_utf8() -> None:
    with pytest.raises(m.RefusedError, match="UTF-8"):
        m.insert_cpus(BLOCK.encode() + b"# \xff\n", WANT)


# the fake vps1


class FakeVps:
    """Answers the script's remote commands from a dict of live files and containers; records every command."""

    def __init__(self, tmp_path: Path, files: dict[str, str], records: list[dict]) -> None:
        self.root = tmp_path / "vps"
        self.root.mkdir()
        self.records = records
        self.commands: list[str] = []
        self.config_break: str | None = None  # path whose AFTER config should differ
        self.config_fail: set[str] = set()
        self.configs = 0
        self.config_timeout_at = 0  # the Nth config call raises a transport error
        self.drop_after_write = False  # the write lands, then ssh drops before the answer
        for path, text in files.items():
            local = self.local(path)
            local.parent.mkdir(parents=True, exist_ok=True)
            local.write_text(text)

    def local(self, path: str) -> Path:
        return self.root / path.lstrip("/")

    def __call__(self, cmd: str, stdin: bytes | None = None, timeout: int = 120):
        self.commands.append(cmd)
        argv = __import__("shlex").split(cmd)
        assert argv[:2] == ["sudo", "-n"], cmd
        argv = argv[2:]
        if argv[:2] == ["docker", "inspect"]:
            assert argv[2:4] == ["--type", "container"], cmd
            found = [r for r in self.records if r["Name"].lstrip("/") in argv[4:]]
            return subprocess.CompletedProcess(
                cmd, 1 if len(found) < len(argv) - 2 else 0, json.dumps(found).encode(), b""
            )
        if argv[:2] == ["docker", "update"]:
            name, cpus = argv[-1], Decimal(argv[3])
            for r in self.records:
                if r["Name"] == f"/{name}":
                    r["HostConfig"]["NanoCpus"] = int(cpus * 10**9)
            return subprocess.CompletedProcess(cmd, 0, name.encode(), b"")
        if argv[0] == "cat":
            return subprocess.CompletedProcess(cmd, 0, self.local(argv[1]).read_bytes(), b"")
        if argv[0] == "sha256sum":
            digest = hashlib.sha256(self.local(argv[1]).read_bytes()).hexdigest()
            return subprocess.CompletedProcess(cmd, 0, f"{digest}  {argv[1]}\n".encode(), b"")
        if argv[:3] == ["docker", "compose", "-f"]:
            path = argv[3]
            self.configs += 1
            if path in self.config_fail:
                return subprocess.CompletedProcess(
                    cmd, 1, b"", b"invalid hostPort: sup3rS3cretValue"
                )
            if self.configs == self.config_timeout_at:
                raise m.TransportError("timed out after 120s: config")
            import yaml

            doc = yaml.safe_load(self.local(path).read_text())
            for svc in doc["services"].values():
                lim = svc.get("deploy", {}).get("resources", {}).get("limits", {})
                if "cpus" in lim:
                    lim["cpus"] = float(lim["cpus"])
            if path == self.config_break and any(
                "cpus" in c for c in self.local(path).read_text().split("\n")
            ):
                doc["extra"] = 1
            return subprocess.CompletedProcess(cmd, 0, json.dumps(doc).encode(), b"")
        if argv[:2] == ["sh", "-c"]:
            script, args = argv[2], argv[4:]
            args = [str(self.local(a)) if a.startswith("/opt/") else a for a in args]
            r = subprocess.run(["sh", "-c", script, "sh", *args], input=stdin, capture_output=True)
            if self.drop_after_write and script == m.WRITE_SH:
                raise m.TransportError("ssh failed (rc 255): connection reset")
            return r
        raise AssertionError(f"unexpected remote command: {cmd}")


@pytest.fixture
def vps(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> FakeVps:
    table = {"web-c": (Decimal("0.5"), "0.5"), "db-c": (Decimal("2.0"), "2.0")}
    monkeypatch.setattr(m, "load_table", lambda: dict(table))
    db = "services:\n  db:\n    container_name: db-c\n    deploy:\n      resources:\n        limits:\n          memory: 1G\n"
    fake = FakeVps(
        tmp_path,
        {"/opt/web/compose.yaml": BLOCK, "/opt/db/compose.yaml": db},
        [
            _record("web-c", config="/opt/web/compose.yaml"),
            _record("db-c", config="/opt/db/compose.yaml"),
        ],
    )
    monkeypatch.setattr(m, "run", fake)
    monkeypatch.setattr(m, "STAMP", "test")
    return fake


def _answer(monkeypatch: pytest.MonkeyPatch, *answers: str) -> None:
    it = iter(answers)
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(it))


# 4 — dry run


def test_dry_run_sends_only_reads(vps: FakeVps, capsys: pytest.CaptureFixture[str]) -> None:
    """Given the default run, when it ends, then no update, write or restore was sent and both files are as they
    were, while the plan names both edits."""
    before = {p: p.read_bytes() for p in vps.root.rglob("*.yaml")}
    assert m.main([]) == 0
    assert not [c for c in vps.commands if "docker update" in c or "sh -c" in c or "config" in c]
    assert {p: p.read_bytes() for p in vps.root.rglob("*.yaml")} == before
    out = capsys.readouterr().out
    assert "/opt/web/compose.yaml: inserts cpus for web" in out and "Dry run" in out


# 5 — the file apply


def test_apply_file_writes_backs_up_and_checks_with_config(
    vps: FakeVps, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Given --apply and two yeses, when it ends, then both files carry their cpus line, each has a byte-equal
    backup, and compose config ran before and after each write."""
    _answer(monkeypatch, "yes", "yes")
    assert m.main(["--apply"]) == 0
    web = vps.local("/opt/web/compose.yaml")
    assert web.read_text() == BLOCK + "          cpus: '0.5'\n"
    assert vps.local("/opt/web/compose.yaml.cpu-bak-test").read_text() == BLOCK
    assert "cpus: '2.0'" in vps.local("/opt/db/compose.yaml").read_text()
    assert "cpus" not in vps.local("/opt/db/compose.yaml.cpu-bak-test").read_text()
    assert sum("config --format json" in c for c in vps.commands) == 4
    assert not list(vps.root.rglob(".compose.yaml.*"))


def test_apply_file_restores_when_config_changes_beyond_cpus(
    vps: FakeVps, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Given compose's AFTER config differing beyond the cpus key, then the file is restored and the run exits 1."""
    vps.config_break = "/opt/web/compose.yaml"
    _answer(monkeypatch, "yes", "yes")
    assert m.main(["--apply"]) == 1
    assert vps.local("/opt/web/compose.yaml").read_text() == BLOCK
    assert "cpus: '2.0'" in vps.local("/opt/db/compose.yaml").read_text()


def test_apply_file_refuses_when_the_before_config_fails(
    vps: FakeVps, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Given a file whose BEFORE config fails, then it is not written and counts toward exit 1."""
    vps.config_fail.add("/opt/web/compose.yaml")
    _answer(monkeypatch, "yes", "yes")
    assert m.main(["--apply"]) == 1
    assert vps.local("/opt/web/compose.yaml").read_text() == BLOCK
    assert not vps.local("/opt/web/compose.yaml.cpu-bak-test").exists()


def _write(f: Path, new: bytes, old_sha: str | None = None) -> subprocess.CompletedProcess[bytes]:
    old_sha = old_sha or hashlib.sha256(f.read_bytes()).hexdigest()
    new_sha = hashlib.sha256(new).hexdigest()
    return subprocess.run(
        ["sh", "-c", m.WRITE_SH, "sh", str(f), old_sha, new_sha, "t"],
        input=new,
        capture_output=True,
    )


def test_apply_file_write_script_refuses_a_changed_file_a_link_and_short_bytes(
    tmp_path: Path,
) -> None:
    """Given the write script, when F changed since it was read, is a symlink or hard link, or the bytes that
    arrive are not the bytes hashed, then it exits non-zero, F is untouched and no temp file is left."""
    tmp_path = tmp_path / "stack"
    tmp_path.mkdir()
    f = tmp_path / "compose.yaml"
    f.write_text("a: 1\n")
    assert _write(f, b"a: 2\n", old_sha="0" * 64).returncode == 3
    good_sha = hashlib.sha256(b"a: 2\n").hexdigest()
    r = subprocess.run(
        [
            "sh",
            "-c",
            m.WRITE_SH,
            "sh",
            str(f),
            hashlib.sha256(b"a: 1\n").hexdigest(),
            good_sha,
            "t",
        ],
        input=b"a: 2",
        capture_output=True,
    )
    assert r.returncode == 4
    link = tmp_path / "link.yaml"
    link.symlink_to(f)
    assert _write(link, b"a: 2\n", hashlib.sha256(b"a: 1\n").hexdigest()).returncode == 5
    os.link(f, tmp_path / "hard.yaml")
    assert _write(f, b"a: 2\n").returncode == 5
    assert f.read_text() == "a: 1\n"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["compose.yaml", "hard.yaml", "link.yaml"]


def test_apply_file_write_script_keeps_mode_and_backs_up(tmp_path: Path) -> None:
    """Given a 0640 file, when written, then it holds the new bytes, keeps 0640, and the backup holds the old."""
    f = tmp_path / "compose.yaml"
    f.write_text("a: 1\n")
    f.chmod(0o640)
    r = _write(f, b"a: 2\n")
    assert r.returncode == 0, r.stderr
    assert f.read_bytes() == b"a: 2\n" and (f.stat().st_mode & 0o777) == 0o640
    assert Path(r.stdout.decode().strip()).read_bytes() == b"a: 1\n"


# 6 — the runtime apply


def test_apply_runtime_updates_reads_back_and_never_recreates(
    vps: FakeVps, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Given --apply, when it ends, then each UPDATE container reads NanoCpus = cpus*1e9 and no command up,
    restarted, stopped, removed, created or killed a container."""
    _answer(monkeypatch, "yes", "yes")
    assert m.main(["--apply"]) == 0
    nano = {r["Name"]: r["HostConfig"]["NanoCpus"] for r in vps.records}
    assert nano == {"/web-c": 500_000_000, "/db-c": 2_000_000_000}
    assert vps.commands and all(m.allowed(c) for c in vps.commands)
    assert not [
        c
        for c in vps.commands
        if re.search(r"\b(up|restart|stop|rm|create|kill|down|run|start)\b", c) and "sh -c" not in c
    ]


def test_apply_runtime_stops_when_the_cap_does_not_read_back(
    vps: FakeVps, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Given a docker update that leaves NanoCpus at 0, then the run stops before any file is written."""
    real = vps.__call__

    def lazy(cmd: str, stdin: bytes | None = None, timeout: int = 120):
        if "docker update" in cmd:
            vps.commands.append(cmd)
            return subprocess.CompletedProcess(cmd, 0, b"", b"")
        return real(cmd, stdin, timeout)

    monkeypatch.setattr(m, "run", lazy)
    _answer(monkeypatch, "yes", "yes")
    with pytest.raises(SystemExit):
        m.main(["--apply"])
    assert vps.local("/opt/web/compose.yaml").read_text() == BLOCK


def test_apply_runtime_never_touches_a_differs_container(
    vps: FakeVps, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Given a container with a CpuQuota, when applied, then it is not updated, its file is not edited, exit 1."""
    vps.records[0]["HostConfig"]["CpuQuota"] = 50_000
    _answer(monkeypatch, "yes", "yes")
    assert m.main(["--apply"]) == 1
    assert not [c for c in vps.commands if "docker update" in c and "web-c" in c]
    assert vps.local("/opt/web/compose.yaml").read_text() == BLOCK


@pytest.mark.parametrize(
    "cmd",
    [
        "sudo -n docker restart x",
        "sudo -n docker compose -f /opt/a/compose.yaml up -d",
        "docker rm x",
        "sudo -n docker compose up -d",
        "sudo -n docker compose -p x -f /opt/a/compose.yaml up",
        "sudo -n docker compose --file /opt/a/compose.yaml up",
        "sudo -n docker compose -f /opt/a/compose.yaml down",
        "sudo -n docker container rm x",
        "sudo -n docker  restart x",
        "sudo -n docker -H tcp://x restart y",
        "sudo -n docker run --rm alpine",
        "sudo -n docker start x",
        "sudo -n docker update --cpus 6 x",
        "sudo -n docker update --cpus 0.5 --restart always x",
        "sudo -n docker inspect x",
        "sudo -n sh -c 'docker restart x' sh",
        "sudo -n cat /opt/a/compose.yaml; docker restart x",
    ],
)
def test_the_transport_refuses_every_command_outside_its_allowlist(
    cmd: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Given any command shape this gate never sends (each spelling of up, restart, rm, down, run, start, a
    too-large cap, an extra flag, an ad-hoc shell script), when sent, then run() stops before ssh starts."""
    monkeypatch.setattr(m.subprocess, "run", lambda *a, **k: pytest.fail("ssh was started"))
    with pytest.raises(SystemExit):
        m.run(cmd)


# 7 — summary and exit


def test_summary_prints_the_acceptance_query_and_exits_1_on_manual(
    vps: FakeVps, capsys: pytest.CaptureFixture[str]
) -> None:
    """Given one container whose label is not a boot file, when dry-run, then it is MANUAL, the query names both
    containers, and the run exits 1."""
    vps.records[1]["Config"]["Labels"]["com.docker.compose.project.config_files"] = (
        "/home/x/compose.yaml"
    )
    assert m.main([]) == 1
    out = capsys.readouterr().out
    assert 'container_spec_cpu_quota{name=~"db-c|web-c"}' in out
    assert "db-c: MANUAL" in out


def test_summary_counts_a_missing_container(vps: FakeVps) -> None:
    """Given a table container absent on vps1 (docker inspect rc 1 with partial JSON), then exit 1."""
    vps.records.pop()
    assert m.main([]) == 1


# pass-1 review regressions


def test_apply_file_restores_when_the_after_config_drops(
    vps: FakeVps, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Given the write landed and the AFTER compose config times out, then the file is restored and exit is 1."""
    vps.config_timeout_at = 2  # /opt/db sorts first: its BEFORE is config call 1, its AFTER call 2
    _answer(monkeypatch, "yes", "yes")
    assert m.main(["--apply"]) == 1
    assert "cpus" not in vps.local("/opt/db/compose.yaml").read_text()
    assert vps.local("/opt/web/compose.yaml").read_text() == BLOCK + "          cpus: '0.5'\n"


def test_apply_file_carries_on_when_ssh_drops_after_the_write_landed(
    vps: FakeVps, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Given the write landed but ssh dropped before its answer, then the file's hash shows the new bytes and the
    AFTER check still runs, so the file is kept, not reported as unchanged."""
    vps.drop_after_write = True
    _answer(monkeypatch, "yes", "yes")
    assert m.main(["--apply"]) == 0
    assert vps.local("/opt/web/compose.yaml").read_text() == BLOCK + "          cpus: '0.5'\n"


def test_a_failed_config_never_prints_its_stderr(
    vps: FakeVps, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Given compose config failing with an interpolated .env value in its stderr, then the value is not printed."""
    vps.config_fail.add("/opt/web/compose.yaml")
    _answer(monkeypatch, "yes", "yes")
    assert m.main(["--apply"]) == 1
    captured = capsys.readouterr()
    assert "sup3rS3cretValue" not in captured.out + captured.err
    assert "docker compose config failed (rc 1)" in captured.out


def test_apply_file_refuses_a_service_that_resolves_a_cpu_key(
    vps: FakeVps, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Given compose's resolved config showing a service-level cpu_quota the raw text hides, then not written."""
    real = vps.__call__

    def with_quota(cmd: str, stdin: bytes | None = None, timeout: int = 120):
        r = real(cmd, stdin, timeout)
        if "config --format json" in cmd and "/opt/web/" in cmd:
            doc = json.loads(r.stdout)
            doc["services"]["web"]["cpu_quota"] = 50000
            r = subprocess.CompletedProcess(cmd, 0, json.dumps(doc).encode(), b"")
        return r

    monkeypatch.setattr(m, "run", with_quota)
    _answer(monkeypatch, "yes", "yes")
    assert m.main(["--apply"]) == 1
    assert vps.local("/opt/web/compose.yaml").read_text() == BLOCK


def test_the_result_table_is_printed_after_the_apply(
    vps: FakeVps, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Given a clean apply, then the closing table reads updated / written for each container."""
    _answer(monkeypatch, "yes", "yes")
    assert m.main(["--apply"]) == 0
    result = capsys.readouterr().out.split("Result:")[1]
    assert "web-c                    updated   written" in result


def test_plan_reads_a_record_without_hostconfig_as_missing() -> None:
    """Given an inspect record that is not a container (a network of the same name), then MISSING, never UPDATE."""
    stdout = json.dumps([{"Name": "web-c", "Driver": "bridge"}]).encode()
    assert m.runtime_plan({"web-c": (Decimal("0.5"), "0.5")}, stdout)["web-c"][0] == "MISSING"


@pytest.mark.parametrize(
    ("text", "reason"),
    [
        (
            "x-base: &base\n  cpu_quota: 50000\nservices:\n  web:\n    <<: *base\n    container_name: web-c\n"
            "    deploy:\n      resources:\n        limits:\n          memory: 64M\n",
            "service has a << merge key",
        ),
        (
            "x-r: &r\n  limits:\n    cpus: '1'\nservices:\n  web:\n    container_name: web-c\n    deploy:\n"
            "      resources:\n        <<: *r\n        limits:\n          memory: 64M\n",
            "resources has a << merge key",
        ),
        (
            "services:\n  web:\n    container_name: web-c\n    deploy:\n      resources:\n        limits: &ll\n"
            "          memory: 64M\n  other:\n    image: x\n    x-lim: *ll\n",
            "anchor or alias",
        ),
        (BLOCK.replace("memory: 64M  # keep this comment", "memory:"), "one-line value"),
    ],
)
def test_insert_refuses_merges_aliases_and_a_null_memory(text: str, reason: str) -> None:
    """Given a merge key at service or resources level, a limits aliased anywhere in the file, or a null memory,
    when inserted, then the file is refused."""
    with pytest.raises(m.RefusedError, match=reason):
        m.insert_cpus(text.encode(), WANT)


@pytest.mark.parametrize("text", ["0.3333333333", "1.0000000001"])
def test_a_cpus_text_finer_than_a_nanocpu_is_refused(text: str) -> None:
    """Given a cpus text docker cannot hold exactly in NanoCpus, then it is not a usable cap."""
    assert m.cpus_value(text) is None


def test_apply_file_write_script_refuses_a_taken_backup_name(tmp_path: Path) -> None:
    """Given a backup name already on disk, when written, then exit 5 and F untouched."""
    stack = tmp_path / "stack"
    stack.mkdir()
    f = stack / "compose.yaml"
    f.write_text("a: 1\n")
    (stack / "compose.yaml.cpu-bak-t").write_text("older\n")
    assert _write(f, b"a: 2\n").returncode == 5
    assert f.read_text() == "a: 1\n"
