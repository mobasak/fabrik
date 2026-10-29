"""Behaviours of scripts/sysadmin/vps1_ocoron_removal.py that hold without vps1 (W-80a1f9fd, D-1333).

The ssh transport is replaced by a fake vps1 that answers each allowlisted command from a small state model; the
rename snippet runs for real through `sh` on local files, and the site regex runs through GNU grep, the tool vps1 runs.
"""

from __future__ import annotations

import importlib.util
import json
import shlex
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "sysadmin" / "vps1_ocoron_removal.py"
_spec = importlib.util.spec_from_file_location("vps1_ocoron_removal_under_test", SCRIPT)
m = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(m)

ROOTDIR = "/var/lib/docker"
MUTATING = ("down", "image rm", "volume rm", "rm -rf", m.RENAME_SH.splitlines()[0])


def _cid(n: int) -> str:
    return f"{n:064x}"


def _container(
    n: int, name: str, project: str | None, image: str, mounts: list[dict], route: str | None = None
) -> dict:
    labels = {}
    if project:
        labels["com.docker.compose.project"] = project
    if route:
        labels["traefik.http.routers.x.rule"] = route
    return {
        "Id": _cid(n),
        "Name": "/" + name,
        "Created": "2026-10-20T03:00:00Z",
        "Image": image,
        "State": {"Status": "running"},
        "Config": {"Labels": labels},
        "Mounts": mounts,
    }


def _vol(name: str, dest: str = "/data") -> dict:
    return {
        "Type": "volume",
        "Name": name,
        "Source": f"{ROOTDIR}/volumes/{name}/_data",
        "Destination": dest,
    }


IMG = {k: "sha256:" + c * 64 for k, c in (("wp", "a"), ("db", "b"), ("redis", "c"), ("nginx", "d"))}


class FakeVps:
    """A vps1 the script can only reach through allowlisted command shapes."""

    def __init__(self) -> None:
        self.containers = [
            _container(
                1,
                "ocoron-com-wordpress-1",
                "ocoron-com",
                IMG["wp"],
                [
                    _vol("ocoron-com_wp_html", "/var/www/html"),
                    {
                        "Type": "bind",
                        "Source": "/opt/ocoron-com/php-fpm/zz.conf",
                        "Destination": "/x",
                    },
                ],
            ),
            _container(
                2,
                "ocoron-com-db-1",
                "ocoron-com",
                IMG["db"],
                [_vol("ocoron-com_db_data", "/var/lib/mysql")],
            ),
            _container(
                3, "ocoron-com-redis-1", "ocoron-com", IMG["redis"], [_vol("ocoron-com_redis_data")]
            ),
            # found only by its Traefik route: another project name, another container name
            _container(
                4,
                "site-nginx-1",
                "ocoron-site",
                IMG["nginx"],
                [],
                route="Host(`ocoron.com`) || Host(`www.ocoron.com`)",
            ),
            _container(5, "n8n", "n8n", "sha256:" + "e" * 64, [_vol("n8n_data")]),
        ]
        self.networks = {
            "ocoron-com": ["ocoron-com_ocoron-com-internal"],
            "ocoron-site": ["ocoron-site_default"],
        }
        self.volumes = {
            "ocoron-com_db_data": "d mysql\nf ibdata1\nf mysql/user.frm\n",
            "ocoron-com_wp_html": "f wp-config.php\nd wp-content\n",
            "ocoron-com_redis_data": "f dump.rdb\n",
            "ocoron-com_backup_data": "",
            "n8n_data": "f database.sqlite\n",
        }
        self.data_dir: str | None = "d php-fpm\nf php-fpm/zz.conf\nf compose.yaml\n"
        self.compose = True
        self.prompt_lines = 0
        self.refs = "/opt/backrest/config/config.json:12:ocoron-com_\n"
        self.named = {"ocoron-com_db_data": "/opt/backrest/config/config.json\n"}
        self.rc: dict[str, int] = {}
        self.sent: list[str] = []
        self.down_rc = 0
        self.rename_rc = 0
        self.leave_after_down: list[int] = []

    def _r(self, rc: int, out: str = "", err: str = "") -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess([], rc, out, err)

    def __call__(self, argv: list[str], **_kw: object) -> subprocess.CompletedProcess[str]:
        cmd = argv[-1]
        assert argv[:-1] == m.SSH
        self.sent.append(cmd)
        a = shlex.split(cmd)[2:]
        for key, rc in self.rc.items():
            if key in cmd:
                return self._r(rc, "", f"forced rc {rc}")
        if a == ["docker", "ps", "-aq", "--no-trunc"]:
            return self._r(0, "".join(c["Id"] + "\n" for c in self.containers))
        if a[:4] == ["docker", "inspect", "--type", "container"]:
            return self._r(0, json.dumps([c for c in self.containers if c["Id"] in a[4:]]))
        if a[:3] == ["docker", "network", "ls"]:
            return self._r(
                0, "".join(n + "\n" for n in self.networks.get(a[4].partition("project=")[2], []))
            )
        if a == ["docker", "volume", "ls", "--format", "{{.Name}}"]:
            return self._r(0, "".join(v + "\n" for v in self.volumes))
        if a == ["docker", "info", "--format", "{{.DockerRootDir}}"]:
            return self._r(0, ROOTDIR + "\n")
        if a[:3] == ["docker", "volume", "inspect"]:
            return self._r(
                0,
                json.dumps(
                    [{"Name": v, "Mountpoint": f"{ROOTDIR}/volumes/{v}/_data"} for v in a[3:]]
                ),
            )
        if a[:2] == ["du", "-sb"]:
            return self._r(0, f"4096\t{a[2]}\n")
        if a[0] == "find":
            if a[1] == m.DATA_DIR:
                return self._r(0, "d \n" + (self.data_dir or ""))
            name = a[1].split("/")[-2]
            return self._r(0, "d \n" + self.volumes[name])
        if a == ["test", "-d", m.DATA_DIR]:
            return self._r(0 if self.data_dir is not None else 1)
        if a == ["test", "-f", m.COMPOSE]:
            return self._r(0 if self.compose else 1)
        if a[:2] == ["grep", "-rnIoE"]:
            return self._r(0 if self.refs else 1, self.refs)
        if a[:2] == ["grep", "-cE"]:
            return self._r(0 if self.prompt_lines else 1, f"{self.prompt_lines}\n")
        if a[:2] == ["grep", "-rlIF"]:
            out = self.named.get(a[3], "")
            return self._r(0 if out else 1, out)
        if a == ["uptime", "-s"]:
            return self._r(0, "2026-10-01 04:00:00\n")
        if a[:3] == ["docker", "compose", "-p"]:
            if self.down_rc:
                return self._r(self.down_rc, "", "down failed")
            self.containers = [
                c
                for c in self.containers
                if c["Config"]["Labels"].get("com.docker.compose.project") != a[3]
                or int(c["Id"], 16) in self.leave_after_down
            ]
            self.networks.pop(a[3], None)
            return self._r(0)
        if a[:2] == ["sh", "-c"]:
            if self.rename_rc:
                return self._r(self.rename_rc, "", "not a regular file")
            self.compose = False
            return self._r(0, m.COMPOSE + ".removed-x\n")
        if a[:3] == ["docker", "image", "rm"]:
            used = any(c["Image"] == a[3] for c in self.containers)
            return self._r(1 if used else 0, "", "image is being used" if used else "")
        if a[:3] == ["docker", "volume", "rm"]:
            self.volumes.pop(a[3])
            return self._r(0)
        if a[:2] == ["rm", "-rf"]:
            self.data_dir = None
            return self._r(0)
        raise AssertionError(f"the fake has no answer for an allowlisted shape: {cmd}")


@pytest.fixture
def vps(monkeypatch: pytest.MonkeyPatch) -> FakeVps:
    fake = FakeVps()
    monkeypatch.setattr(m.subprocess, "run", fake)
    return fake


def _answer(monkeypatch: pytest.MonkeyPatch, *answers: str) -> None:
    it = iter(answers)
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(it))


def _mutations(vps: FakeVps) -> list[str]:
    return [c for c in vps.sent if any(word in c for word in MUTATING)]


# 1 — the dry run


def test_dry_run_reads_only_and_prints_the_inventory(
    vps: FakeVps, capsys: pytest.CaptureFixture[str]
) -> None:
    """Given the stack running (one container found only by its Traefik route), when the dry run runs, then nothing
    mutating is sent and the stack, projects, networks, boot glob, prompt count, data and REVIEW hits are printed."""
    assert m.main([]) == 0
    out = capsys.readouterr().out
    assert _mutations(vps) == []
    for name in ("ocoron-com-wordpress-1", "ocoron-com-db-1", "ocoron-com-redis-1", "site-nginx-1"):
        assert name in out
    assert "n8n " not in out.split("projects:")[0]
    assert "projects: ocoron-com, ocoron-site" in out
    assert "ocoron-com_ocoron-com-internal" in out and "ocoron-site_default" in out
    assert "in the boot glob: YES" in out
    assert "vps1 booted: 2026-10-01 04:00:00" in out and "created 2026-10-20T03:00:00Z" in out
    assert "naming ocoron-com- containers: 0" in out
    assert "ocoron-com_db_data  class mysql" in out
    assert "ocoron-com_wp_html  class wordpress" in out
    assert "ocoron-com_backup_data  class empty" in out
    assert "/opt/ocoron-com  class unknown" in out
    assert "/opt/backrest/config/config.json:12:ocoron-com_" in out
    assert "n8n_data" not in out


# 2 — the allowlist and the site regex


@pytest.mark.parametrize(
    "argv",
    [
        ["docker", "compose", "-p", "ocoron-com", "down", "-v"],
        ["docker", "volume", "rm", "-f", "ocoron-com_db_data"],
        ["docker", "volume", "prune", "-f"],
        ["rm", "-rf", "/opt/ocoron-com/"],
        ["rm", "-rf", "--one-file-system", "--", "/opt"],
        ["docker", "image", "rm", "-f", "sha256:" + "a" * 64],
        ["docker", "rm", "-f", "ocoron-com-db-1"],
        ["du", "-sb", "/var/lib/docker/volumes/../../etc/_data"],
        ["find", "/", "-maxdepth", "2", "-printf", "%y %P\n"],
        ["grep", "-rlIF", "--", "x;reboot", *m.CONFIG_ROOTS],
    ],
)
def test_allowlist_refuses_unlisted_shapes(argv: list[str]) -> None:
    """Given a mutating spelling the script never sends, when checked, then it is refused (with and without sudo)."""
    assert not m.allowed(shlex.join(["sudo", "-n", *argv]))
    assert not m.allowed(shlex.join(argv))


def test_allowlist_refuses_a_glued_second_command_and_takes_its_own_shapes() -> None:
    """Given a listed shape with `; reboot` glued on, then refused; the shapes the script builds pass."""
    down = m.sudo("docker", "compose", "-p", "ocoron-com", "down")
    assert m.allowed(down)
    assert not m.allowed(down + "; reboot")
    assert not m.allowed(down + " && reboot")
    assert m.allowed(m.sudo("sh", "-c", m.RENAME_SH, "sh", m.COMPOSE, m.STAMP))
    assert not m.allowed(m.sudo("sh", "-c", m.RENAME_SH + "rm -rf /\n", "sh", m.COMPOSE, m.STAMP))
    assert m.allowed(m.sudo("du", "-sb", "/srv/docker/volumes/ocoron-com_db_data/_data"))
    # the remote shell runs the RAW string: only the canonical quoting of the checked tokens is sent
    assert not m.allowed("sudo -n docker ps -aq '--no-trunc'")
    assert not m.allowed("sudo  -n docker ps -aq --no-trunc")


@pytest.mark.parametrize(
    ("line", "hit"),
    [
        ("url: https://ocoron.com/", True),
        ("rule: Host(`ocoron.com`)", True),
        ("rule: Host(`www.ocoron.com`)", True),
        ("domain: ocoron.com", True),
        ("- /var/lib/docker/volumes/ocoron-com_db_data/_data", True),
        ("container: ocoron-com-wordpress-1", True),
        ("ocoron.com", True),
        ("url: https://auth.vps1.ocoron.com/", False),
        ("to: admin@ocoron.com", False),
        ("notocoron.com", False),
        ("ocoron.company", False),
        ("ocoron.com.tr", False),
    ],
)
def test_site_ere_matches_the_site_only(tmp_path: Path, line: str, hit: bool) -> None:
    """Given a config line, when GNU grep runs SITE_ERE over it, then only the apex, www and the stack match."""
    f = tmp_path / "c.txt"
    f.write_text(line + "\n")
    assert (subprocess.run(["grep", "-qE", m.SITE_ERE, str(f)]).returncode == 0) is hit


# 3 — --apply


def test_apply_downs_then_moves_compose_aside(
    vps: FakeVps, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Given the stack up and the prompt synced, when --apply is confirmed, then each project is downed, compose.yaml
    leaves the boot glob, unused images go, and the next --delete-volumes line names every data id."""
    _answer(monkeypatch, "yes")
    assert m.main(["--apply"]) == 0
    sent = _mutations(vps)
    downs = [c for c in sent if " down" in c]
    assert [shlex.split(c)[5] for c in downs] == ["ocoron-com", "ocoron-site"]
    rename = next(i for i, c in enumerate(vps.sent) if m.RENAME_SH.splitlines()[0] in c)
    assert rename > vps.sent.index(downs[-1])
    assert sum(" image rm " in c for c in sent) == 4
    out = capsys.readouterr().out
    assert "stack removed: 0 containers, 0 networks" in out
    assert (
        "--delete-volumes ocoron-com_backup_data ocoron-com_db_data ocoron-com_redis_data ocoron-com_wp_html "
        "/opt/ocoron-com"
    ) in out


def test_apply_stops_while_the_prompt_still_claims_the_stack(
    vps: FakeVps, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Given vps1's prompt still names ocoron-com- containers, when --apply runs, then it stops before any gate."""
    vps.prompt_lines = 2
    _answer(monkeypatch)  # any input() would raise StopIteration
    assert m.main(["--apply"]) == 1
    assert _mutations(vps) == []
    assert "sync-vps-sysadmin.sh" in capsys.readouterr().err


@pytest.mark.parametrize("answer", ["no", "YES", ""])
def test_apply_runs_nothing_without_yes(
    vps: FakeVps, monkeypatch: pytest.MonkeyPatch, answer: str
) -> None:
    _answer(monkeypatch, answer)
    assert m.main(["--apply"]) == 1
    assert _mutations(vps) == []


def test_apply_stops_before_the_rename_when_down_fails(
    vps: FakeVps, monkeypatch: pytest.MonkeyPatch
) -> None:
    vps.down_rc = 1
    _answer(monkeypatch, "yes")
    assert m.main(["--apply"]) == 1
    assert not any(m.RENAME_SH.splitlines()[0] in c for c in vps.sent)


def test_apply_says_down_but_in_the_glob_when_the_rename_is_refused(
    vps: FakeVps, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    vps.rename_rc = 5
    _answer(monkeypatch, "yes")
    assert m.main(["--apply"]) == 1
    assert (
        "DOWN but /opt/ocoron-com/compose.yaml is still in the boot glob" in capsys.readouterr().err
    )


def test_apply_stops_when_a_container_survives_the_down(
    vps: FakeVps, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    vps.leave_after_down = [2]
    _answer(monkeypatch, "yes")
    assert m.main(["--apply"]) == 1
    assert "still present after the down: ocoron-com-db-1" in capsys.readouterr().err


# 4 — the rename snippet, run for real


def _rename(path: Path, stamp: str = "S") -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["sh", "-c", m.RENAME_SH, "sh", str(path), stamp], capture_output=True, text=True
    )


def _boot_glob(root: Path) -> list[str]:
    """fabrik-compose-boot.sh's selection: the glob, then up_stack's `[ -f compose.yaml ]`."""
    script = 'shopt -s nullglob; for f in "$1"/*/compose.yaml; do [ -f "$f" ] && echo "$(dirname "$f")"; done'
    return subprocess.run(
        ["bash", "-c", script, "bash", str(root)], capture_output=True, text=True
    ).stdout.split()


def test_rename_script_takes_compose_out_of_the_boot_glob(tmp_path: Path) -> None:
    stack = tmp_path / "ocoron-com"
    stack.mkdir()
    (stack / "compose.yaml").write_text("services: {}\n")
    assert _boot_glob(tmp_path) == [str(stack)]
    r = _rename(stack / "compose.yaml")
    assert r.returncode == 0 and r.stdout.strip() == str(stack / "compose.yaml.removed-S")
    assert _boot_glob(tmp_path) == []
    assert _rename(stack / "compose.yaml").returncode == 4  # already aside


def test_rename_script_refuses_a_symlink_and_a_taken_target(tmp_path: Path) -> None:
    real = tmp_path / "real.yaml"
    real.write_text("x\n")
    link = tmp_path / "compose.yaml"
    link.symlink_to(real)
    assert _rename(link).returncode == 5 and link.is_symlink()
    link.unlink()
    link.write_text("y\n")
    (tmp_path / "compose.yaml.removed-S").write_text("taken\n")
    assert _rename(link).returncode == 5 and link.read_text() == "y\n"


# 5 — --delete-volumes


@pytest.fixture
def removed(vps: FakeVps, monkeypatch: pytest.MonkeyPatch) -> FakeVps:
    """The state after a confirmed --apply."""
    _answer(monkeypatch, "yes")
    assert m.main(["--apply"]) == 0
    vps.sent.clear()
    return vps


def test_delete_volumes_deletes_only_the_exact_ids(
    removed: FakeVps, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _answer(monkeypatch, "yes")
    assert (
        m.main(["--delete-volumes", "ocoron-com_db_data", "/opt/ocoron-com", "ocoron-com_db_data"])
        == 0
    )
    deletes = _mutations(removed)
    assert deletes == [
        m.sudo("docker", "volume", "rm", "ocoron-com_db_data"),
        m.sudo("rm", "-rf", "--one-file-system", "--", "/opt/ocoron-com"),
    ]
    assert "ocoron-com_wp_html" in removed.volumes
    assert "WARN still named in: /opt/backrest/config/config.json" in capsys.readouterr().out


@pytest.mark.parametrize(
    "ids", [["ocoron-com_nope"], ["n8n_data"], ["/opt"], ["ocoron-com_db_data", "x"]]
)
def test_delete_volumes_refuses_an_id_outside_the_inventory(
    removed: FakeVps, monkeypatch: pytest.MonkeyPatch, ids: list[str]
) -> None:
    _answer(monkeypatch)
    assert m.main(["--delete-volumes", *ids]) == 1
    assert _mutations(removed) == []


def test_delete_volumes_refuses_a_used_id_a_sub_path_bind_included(
    removed: FakeVps, monkeypatch: pytest.MonkeyPatch
) -> None:
    removed.containers.append(
        _container(
            9,
            "other",
            "other",
            "sha256:" + "f" * 64,
            [{"Type": "bind", "Source": "/opt/ocoron-com/backup/x.sh", "Destination": "/y"}],
        )
    )
    _answer(monkeypatch)
    assert m.main(["--delete-volumes", "/opt/ocoron-com"]) == 1
    assert _mutations(removed) == []


def test_delete_volumes_refuses_while_the_stack_is_up_or_in_the_boot_glob(
    vps: FakeVps, monkeypatch: pytest.MonkeyPatch
) -> None:
    _answer(monkeypatch)
    assert m.main(["--delete-volumes", "ocoron-com_backup_data"]) == 1
    vps.containers = [c for c in vps.containers if c["Name"] == "/n8n"]
    vps.networks = {}
    assert (
        m.main(["--delete-volumes", "ocoron-com_backup_data"]) == 1
    )  # compose.yaml still in the glob
    assert _mutations(vps) == []


# 6 — classes


@pytest.mark.parametrize(
    ("find_out", "cls"),
    [
        ("d \nd mysql\nf ibdata1\n", "mysql"),
        ("d \nf aria_log_control\n", "mysql"),
        ("d \nf wp-config.php\nf index.php\n", "wordpress"),
        ("d \nd wp-content\nd wp-content/uploads\n", "wordpress"),
        ("d \nf appendonly.aof\n", "redis"),
        ("d \nf 2026-10-01.sql.gz\n", "backup"),
        ("d \n", "empty"),
        ("", "empty"),
        ("d \nf notes.txt\n", "unknown"),
    ],
)
def test_volume_class_from_signatures(find_out: str, cls: str) -> None:
    assert m.classify(find_out)[0] == cls


# 7 — unreadable is never none


def test_ssh_failure_stops_with_the_reason(
    vps: FakeVps, capsys: pytest.CaptureFixture[str]
) -> None:
    vps.rc["docker ps"] = 255
    assert m.main([]) == 1
    assert "ssh failed (rc 255)" in capsys.readouterr().err


def test_unreadable_reads_are_printed_as_unreadable(
    vps: FakeVps, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    vps.rc["find /var/lib/docker/volumes/ocoron-com_db_data"] = 1
    vps.rc["grep -cE"] = 2
    assert m.main([]) == 0
    out = capsys.readouterr().out
    assert "ocoron-com_db_data  class UNREADABLE" in out
    assert "naming ocoron-com- containers: UNREADABLE" in out
    _answer(monkeypatch)
    assert m.main(["--apply"]) == 1  # an unreadable prompt is a STOP, never "synced"
    assert _mutations(vps) == []


def test_grep_rc2_keeps_its_hits_beside_unreadable(
    vps: FakeVps, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    real = vps.__call__

    def partial(argv: list[str], **kw: object) -> subprocess.CompletedProcess[str]:
        r = real(argv, **kw)
        if "-rnIoE" in argv[-1]:
            return subprocess.CompletedProcess(
                [], 2, r.stdout, "grep: /etc/logrotate.d: Permission denied"
            )
        return r

    monkeypatch.setattr(m.subprocess, "run", partial)
    assert m.main([]) == 0
    out = capsys.readouterr().out
    assert "/opt/backrest/config/config.json:12:ocoron-com_" in out
    assert "UNREADABLE: grep: /etc/logrotate.d: Permission denied" in out
