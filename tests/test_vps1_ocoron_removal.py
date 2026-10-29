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
        self.keep_networks = False  # the down leaves its project's network behind
        self.volume_labels: dict[str, str] = {}  # volume -> compose project label
        self.mountpoints: dict[str, str] = {}  # volume -> a Mountpoint other than the default
        self.inspect_drop = (
            0  # inspect returns this many fewer records, rc 1 (a container vanished)
        )
        self.data_dir_symlink = False
        self.delete_rc = 0
        self.image_rm_err = ""

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
            found = [c for c in self.containers if c["Id"] in a[4:]]
            if self.inspect_drop:
                return self._r(
                    1, json.dumps(found[self.inspect_drop :]), "Error: No such container"
                )
            return self._r(0, json.dumps(found))
        if a[:3] == ["docker", "network", "ls"]:
            return self._r(
                0, "".join(n + "\n" for n in self.networks.get(a[4].partition("project=")[2], []))
            )
        if a[:4] == ["docker", "volume", "ls", "--filter"]:
            project = a[4].partition("project=")[2]
            return self._r(
                0, "".join(v + "\n" for v, p in self.volume_labels.items() if p == project)
            )
        if a == ["docker", "volume", "ls", "--format", "{{.Name}}"]:
            return self._r(0, "".join(v + "\n" for v in self.volumes))
        if a == ["docker", "info", "--format", "{{.DockerRootDir}}"]:
            return self._r(0, ROOTDIR + "\n")
        if a[:3] == ["docker", "volume", "inspect"]:
            return self._r(
                0,
                json.dumps(
                    [
                        {
                            "Name": v,
                            "Mountpoint": self.mountpoints.get(v, f"{ROOTDIR}/volumes/{v}/_data"),
                        }
                        for v in a[3:]
                    ]
                ),
            )
        if a[:2] == ["du", "-sb"]:
            return self._r(0, f"4096\t{a[2]}\n")
        if a[0] == "find":
            if a[1] == m.DATA_DIR:
                return self._r(0, "d \n" + (self.data_dir or ""))
            name = a[1].split("/")[-2]
            if name not in self.volumes:
                return self._r(1, "", f"find: '{a[1]}': No such file or directory")
            return self._r(0, "d \n" + self.volumes[name])
        if a == ["test", "-L", m.DATA_DIR]:
            return self._r(0 if self.data_dir_symlink else 1)
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
            if not self.keep_networks:
                self.networks.pop(a[3], None)
            return self._r(0)
        if a[:2] == ["sh", "-c"]:
            if self.rename_rc == 4:
                return self._r(4)
            if self.rename_rc:
                return self._r(self.rename_rc, "", "not a regular file")
            self.compose = False
            return self._r(0, m.COMPOSE + ".removed-x\n")
        if a[:3] == ["docker", "image", "rm"]:
            used = any(c["Image"] == a[3] for c in self.containers)
            err = "image is being used" if used else self.image_rm_err
            return self._r(1 if err else 0, "", err)
        if a[:3] == ["docker", "volume", "rm"]:
            if self.delete_rc:
                return self._r(self.delete_rc, "", "volume is in use")
            self.volumes.pop(a[3])
            return self._r(0)
        if a[:2] == ["rm", "-rf"]:
            if self.delete_rc:
                return self._r(self.delete_rc, "", "Device or resource busy")
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
        ["grep", "-rlIF", "--", "/opt", *m.CONFIG_ROOTS],
        ["docker", "image", "rm", "wordpress:6"],
        ["docker", "inspect", "--type", "container", "not-hex"],
        ["docker", "volume", "rm", "ocoron-com_db_data", "n8n_data"],
        ["find", m.DATA_DIR, "-maxdepth", "2", "-delete"],
        ["du", "-sb", "/var/lib/docker/volumes/ocoron-com_db_data"],
        ["docker", "compose", "-p", "-rf", "down"],
        ["docker", "volume", "ls", "--filter", "label=x=y", "--format", "{{.Name}}"],
        ["test", "-L", "/opt"],
    ],
)
def test_allowlist_refuses_unlisted_shapes(argv: list[str]) -> None:
    """Given a mutating or widened spelling the script never sends, when checked as the root command it would be,
    then it is refused."""
    assert not m.allowed(shlex.join(["sudo", "-n", *argv]))


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
        ("server ocoron.com.;", True),
        ("ocoron.com.", True),
        ("ocoron.com.br", False),
        ("ocoron-community-bot", False),
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
    err = capsys.readouterr().err
    assert "rename refused: not a regular file" in err
    assert "the stack is DOWN but /opt/ocoron-com/compose.yaml may still be in the boot glob" in err


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


# pass 1 of the /fabrik-review (W-80a1f9fd): one test per confirmed finding


def test_stack_identity_needs_the_name_separator_or_the_label_or_the_route(vps: FakeVps) -> None:
    """A-1 (name half): a name like ocoron-community-bot is not the stack; each identity branch counts alone."""
    vps.containers = [
        _container(10, "ocoron-community-bot", "community", IMG["wp"], []),
        _container(11, "ocoron-com-web-1", None, IMG["wp"], []),
        _container(12, "web-1", "ocoron-com", IMG["db"], []),
        _container(13, "edge-1", "edge", IMG["nginx"], [], route="Host(`a.example`, `OCORON.com`)"),
    ]
    stack = {c["Name"].lstrip("/") for c in vps.containers if m.in_stack(c)}
    assert stack == {"ocoron-com-web-1", "web-1", "edge-1"}


def test_apply_stops_on_a_mixed_project_before_any_down(
    vps: FakeVps, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A-1: a stack container in a project that also runs other containers stops --apply before the gate."""
    vps.containers.append(_container(14, "edge-proxy", "ocoron-site", IMG["nginx"], []))
    _answer(monkeypatch)
    assert m.main(["--apply"]) == 1
    assert _mutations(vps) == []
    assert "ocoron-site (also runs edge-proxy)" in capsys.readouterr().err


def test_apply_stops_on_a_container_from_another_compose_file(
    vps: FakeVps, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A-8: a stack container created from a compose file the rename does not move stops --apply."""
    vps.containers[0]["Config"]["Labels"]["com.docker.compose.project.config_files"] = (
        "/opt/other/compose.yaml"
    )
    _answer(monkeypatch)
    assert m.main(["--apply"]) == 1
    assert _mutations(vps) == []
    assert "/opt/other/compose.yaml" in capsys.readouterr().err


def test_apply_stops_on_an_unlabelled_stack_container(
    vps: FakeVps, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """B-4: a stack container outside any compose project stops --apply before any down."""
    vps.containers.append(_container(15, "ocoron-com-stray", None, IMG["wp"], []))
    _answer(monkeypatch)
    assert m.main(["--apply"]) == 1
    assert _mutations(vps) == []
    assert "outside any compose project: ocoron-com-stray" in capsys.readouterr().err


def test_apply_downs_an_orphan_network_and_rechecks_every_project(
    vps: FakeVps, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A-2: with no container left, a leftover project network is downed; a network that survives stops the run."""
    vps.containers = [c for c in vps.containers if c["Name"] == "/n8n"]
    vps.networks = {"ocoron-com": ["ocoron-com_default"]}
    _answer(monkeypatch, "yes")
    assert m.main(["--apply"]) == 0
    assert m.sudo("docker", "compose", "-p", "ocoron-com", "down") in vps.sent
    vps2 = FakeVps()
    monkeypatch.setattr(m.subprocess, "run", vps2)
    vps2.keep_networks = True
    _answer(monkeypatch, "yes")
    assert m.main(["--apply"]) == 1
    assert "still present after the down: ocoron-com_ocoron-com-internal, ocoron-site_default" in (
        capsys.readouterr().err
    )


def test_apply_stops_when_the_file_is_still_in_the_glob_after_an_ok_rename(
    vps: FakeVps, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """B-3 and B-7: rename rc 4 (already aside) while test -f still finds the file stops the run; rc 4 itself is
    reported as already aside."""
    vps.rename_rc = 4
    _answer(monkeypatch, "yes")
    assert m.main(["--apply"]) == 1
    captured = capsys.readouterr()
    assert "compose.yaml: already aside" in captured.out
    assert (
        "still present after the down: /opt/ocoron-com/compose.yaml in the boot glob"
        in captured.err
    )


def test_apply_with_nothing_left_runs_no_gate(
    vps: FakeVps, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """B-7: a second --apply after a clean removal asks nothing and sends nothing mutating."""
    vps.containers = [c for c in vps.containers if c["Name"] == "/n8n"]
    vps.networks = {}
    vps.compose = False
    _answer(monkeypatch)
    assert m.main(["--apply"]) == 0
    assert _mutations(vps) == []
    assert "nothing to take down" in capsys.readouterr().out


def test_apply_says_what_ran_when_a_later_step_fails(
    vps: FakeVps, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A-4: an ssh failure at the rename, after the downs ran, says the stack may be down and still in the glob."""
    vps.rc[m.RENAME_SH.splitlines()[0]] = 255
    _answer(monkeypatch, "yes")
    assert m.main(["--apply"]) == 1
    err = capsys.readouterr().err
    assert "ssh failed (rc 255)" in err
    assert "downs that ran: " + m.sudo("docker", "compose", "-p", "ocoron-com", "down") in err
    assert "may still be in the boot glob" in err


def test_apply_reports_a_kept_image_and_orders_rename_before_images(
    vps: FakeVps, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """B-5, B-11: images go after the rename, and an image docker refuses is reported as kept."""
    vps.image_rm_err = "conflict: unable to remove repository reference"
    _answer(monkeypatch, "yes")
    assert m.main(["--apply"]) == 0
    rename = next(i for i, c in enumerate(vps.sent) if m.RENAME_SH.splitlines()[0] in c)
    assert all(i > rename for i, c in enumerate(vps.sent) if " image rm " in c)
    assert f"image {IMG['wp']}: kept — conflict" in capsys.readouterr().out


def test_a_volume_named_otherwise_is_found_by_its_project_label_after_the_down(
    vps: FakeVps, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A-3, B-5: a stack volume whose name lacks the ocoron-com_ prefix stays in the data list after the down."""
    vps.volumes["ocoron_db"] = "f ibdata1\n"
    vps.volume_labels["ocoron_db"] = "ocoron-com"
    _answer(monkeypatch, "yes")
    assert m.main(["--apply"]) == 0
    assert "ocoron_db" in capsys.readouterr().out.split("--delete-volumes")[-1]


def test_a_volume_mounted_by_a_stack_container_is_listed_whatever_its_name(
    vps: FakeVps, capsys: pytest.CaptureFixture[str]
) -> None:
    """B-5: a stack container's volume with no ocoron-com_ prefix and no project label is still data to list."""
    vps.volumes["wpdata"] = "f wp-config.php\n"
    vps.containers[0]["Mounts"].append(_vol("wpdata", "/srv"))
    assert m.main([]) == 0
    assert "wpdata  class wordpress" in capsys.readouterr().out


def test_the_quoted_rename_command_runs_as_rename_sh_under_a_real_shell(tmp_path: Path) -> None:
    """B-13: the exact remote string the script sends (minus sudo -n) moves the file through a real `sh -c`."""
    f = tmp_path / "compose.yaml"
    f.write_text("services: {}\n")
    remote = shlex.split(m.sudo("sh", "-c", m.RENAME_SH, "sh", str(f), "S"))[2:]
    r = subprocess.run(["sh", "-c", shlex.join(remote)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert not f.exists() and (tmp_path / "compose.yaml.removed-S").read_text() == "services: {}\n"


def test_a_partial_inspect_read_stops_instead_of_reading_none(
    vps: FakeVps, capsys: pytest.CaptureFixture[str]
) -> None:
    """A-6: inspect rc 1 with fewer records than ids is a STOP, never a smaller stack."""
    vps.inspect_drop = 1
    assert m.main([]) == 1
    assert "returned 4 of 5 containers" in capsys.readouterr().err


def test_users_count_a_volume_mount_by_another_container(
    removed: FakeVps, monkeypatch: pytest.MonkeyPatch
) -> None:
    """B-5: a stopped non-stack container mounting a stack volume makes it used."""
    holder = _container(
        16, "holder", "other", "sha256:" + "f" * 64, [_vol("ocoron-com_redis_data")]
    )
    holder["State"] = {"Status": "exited"}
    removed.containers.append(holder)
    _answer(monkeypatch)
    assert m.main(["--delete-volumes", "ocoron-com_redis_data"]) == 1
    assert _mutations(removed) == []


def test_delete_volumes_runs_nothing_without_yes(
    removed: FakeVps, monkeypatch: pytest.MonkeyPatch
) -> None:
    """B-1: the delete gate's no, wrong case, empty and EOF answers delete nothing."""
    for answer in ("no", "YES", ""):
        _answer(monkeypatch, answer)
        assert m.main(["--delete-volumes", "ocoron-com_db_data"]) == 1

    def eof(_prompt: str = "") -> str:
        raise EOFError

    monkeypatch.setattr("builtins.input", eof)
    assert m.main(["--delete-volumes", "ocoron-com_db_data"]) == 1
    assert _mutations(removed) == []


def test_delete_volumes_exits_1_when_a_delete_fails(
    removed: FakeVps, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """B-2: a refused volume rm prints FAILED and exits 1."""
    removed.delete_rc = 1
    _answer(monkeypatch, "yes")
    assert m.main(["--delete-volumes", "ocoron-com_backup_data"]) == 1
    captured = capsys.readouterr()
    assert "ocoron-com_backup_data: FAILED — volume is in use" in captured.out
    assert "not deleted: ocoron-com_backup_data" in captured.err


def test_delete_volumes_refuses_unclassified_data(
    removed: FakeVps, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A-9, B-6: a foreign mountpoint or a symlinked data dir is UNREADABLE and never deleted."""
    removed.mountpoints["ocoron-com_db_data"] = "/mnt/elsewhere/_data"
    removed.data_dir_symlink = True
    _answer(monkeypatch)
    assert m.main(["--delete-volumes", "ocoron-com_db_data", "/opt/ocoron-com"]) == 1
    assert _mutations(removed) == []
    captured = capsys.readouterr()
    assert "ocoron-com_db_data  class UNREADABLE" in captured.out
    assert "/opt/ocoron-com  class UNREADABLE" in captured.out
    assert "not classified" in captured.err


def test_delete_volumes_names_its_boot_glob_refusal(
    vps: FakeVps, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """B-9: with the stack gone but compose.yaml still in the glob, the refusal names the glob."""
    vps.containers = [c for c in vps.containers if c["Name"] == "/n8n"]
    vps.networks = {}
    _answer(monkeypatch)
    assert m.main(["--delete-volumes", "ocoron-com_backup_data"]) == 1
    assert "is in the boot glob, so a reboot would recreate the volumes" in capsys.readouterr().err


@pytest.mark.parametrize(
    "exc", [subprocess.TimeoutExpired(cmd="ssh", timeout=1), OSError("no ssh")]
)
def test_a_timeout_or_missing_ssh_stops(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], exc: Exception
) -> None:
    """B-8: a timeout or an ssh that cannot start is a STOP with its reason, never a traceback."""

    def boom(*_a: object, **_kw: object) -> subprocess.CompletedProcess[str]:
        raise exc

    monkeypatch.setattr(m.subprocess, "run", boom)
    assert m.main([]) == 1
    assert (
        "timed out after" if isinstance(exc, subprocess.TimeoutExpired) else "could not start ssh"
    ) in (capsys.readouterr().err)


def test_an_unreadable_grep_with_empty_stderr_still_reads_unreadable(
    vps: FakeVps, capsys: pytest.CaptureFixture[str]
) -> None:
    """A-7: grep rc 2 with no stderr is printed as UNREADABLE, never as none."""
    vps.rc["grep -rnIoE"] = 2
    real = vps._r
    vps._r = lambda rc, out="", err="": real(rc, out, "" if rc == 2 else err)  # type: ignore[method-assign]
    assert m.main([]) == 0
    assert "UNREADABLE: grep rc 2" in capsys.readouterr().out
