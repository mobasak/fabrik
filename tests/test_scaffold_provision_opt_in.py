"""Scaffold code provisions only inside an explicit opt-in (W-e2f0b6e5).

A review seat called create_project directly and left two real databases on the WSL dev cluster: the venv, the dev
database, the hub registry sync, the MCP emit and the hub deploy spec all ran for any caller that had not set
FABRIK_SCAFFOLD_OFFLINE. Now they run only inside ``create_project(provision=True)`` or ``scaffold.provisioning()``.

Input domain: every scaffold type create_project emits (wordpress is refused), with use_database=True so the three
types that have a dev-database step reach it. Every command scaffold code spawns goes through ``subprocess.run``; the
``spawned`` fixture fakes it, so nothing here can create a database, a venv or touch the hub even on a broken tree.
A default call may spawn only git and the hub's ``work.py --repo <the new repo> init`` (``pre-commit install`` is
stubbed): the coordinator model (D-1305) makes the new repo's own work store with it, a write inside the new repo
like git's, never provisioning. Any other command, known kind or not, is a leak.
"""

from __future__ import annotations

import threading
from pathlib import Path

import pytest
from click.testing import CliRunner

import fabrik.scaffold as scaffold
from fabrik.scaffold import SCAFFOLD_TYPES

TYPES = sorted(t for t in SCAFFOLD_TYPES if t != "wordpress")
DB_TYPES = {"python-api", "python-api-gpu", "chrome-extension"}
LOCAL = {"git", "work_init"}  # what a default call may spawn: writes inside the new repo only


def _kind(argv: list[str]) -> str:
    if argv[:1] == ["git"]:
        return "git"
    if (
        len(argv) == 7
        and Path(argv[1]).name == "work.py"
        and argv[2] == "--repo"
        and Path(argv[3]).name.startswith("pv-")
        and argv[4:6] == ["init", "--distributor"]
    ):
        return "work_init"
    if argv[:1] == ["sudo"]:
        return "sudo"
    if argv[1:3] == ["-m", "venv"]:
        return "venv"
    if argv and Path(argv[0]).name.startswith("pip"):
        return "pip"
    if any(Path(a).name == "sync_projects.py" for a in argv):
        return "sync_projects"
    if any(Path(a).name == "emit_mcp_project_config.py" for a in argv):
        return "mcp_emitter"
    return "other:" + " ".join(argv[:3])


@pytest.fixture
def spawned(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Every command scaffold code spawns, by kind; faked, never run."""
    seen: list[str] = []

    def fake_run(cmd, *_a, **_kw):
        argv = [str(c) for c in cmd] if isinstance(cmd, list | tuple) else [str(cmd)]
        seen.append(_kind(argv))
        return scaffold.subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(scaffold.subprocess, "run", fake_run)
    monkeypatch.setattr(scaffold, "_install_pre_commit", lambda *_a, **_k: True)
    monkeypatch.delenv("FABRIK_SCAFFOLD_OFFLINE", raising=False)
    return seen


def _scaffold(tmp_path: Path, kind: str, **kw) -> Path:
    return scaffold.create_project(
        name=f"pv-{kind}"[:30],
        description="provision opt-in grader",
        base=tmp_path,
        project_type=kind,
        generate_spec=False,
        use_database=True,
        **kw,
    )


@pytest.mark.parametrize("kind", TYPES)
def test_default_call_provisions_nothing(tmp_path, spawned, kind) -> None:
    project = _scaffold(tmp_path, kind)
    assert (project / "project.yaml").exists(), "a default call still writes every file"
    assert set(spawned) <= LOCAL, spawned


def test_direct_helper_call_provisions_nothing(tmp_path, spawned) -> None:
    """The pattern the incident used: a scaffold step called directly, outside create_project."""
    scaffold._create_local_dev_database("pv_direct_dev")
    project = tmp_path / "direct"
    project.mkdir()
    scaffold._scaffold_shared(project, "direct", "d", "2026-10-18", 8099)
    scaffold._scaffold_python_api(project, "direct", "d", use_database=True)
    scaffold._emit_mcp_config(project)
    scaffold._post_scaffold_sync(Path("/opt") / "never-created-provision-probe")
    assert set(spawned) <= LOCAL, spawned


@pytest.mark.parametrize("kind", TYPES)
def test_opt_in_reaches_provisioning(tmp_path, spawned, kind) -> None:
    _scaffold(tmp_path, kind, provision=True)
    expected = {"sudo", "venv", "pip", "mcp_emitter"} if kind in DB_TYPES else {"mcp_emitter"}
    assert set(spawned) - LOCAL == expected, spawned


def test_env_switch_beats_opt_in(tmp_path, spawned, monkeypatch) -> None:
    monkeypatch.setenv("FABRIK_SCAFFOLD_OFFLINE", "1")
    _scaffold(tmp_path, "python-api", provision=True)
    assert set(spawned) <= LOCAL, spawned


def test_opt_in_is_scoped(tmp_path, spawned, monkeypatch) -> None:
    seen_in_thread: list[bool] = []
    real = scaffold._scaffold_python_api

    def scaffolder_with_a_thread(*a, **kw):
        t = threading.Thread(target=lambda: seen_in_thread.append(scaffold._scaffold_offline()))
        t.start()
        t.join()
        return real(*a, **kw)

    monkeypatch.setitem(scaffold._TYPE_SCAFFOLDERS, "python-api", scaffolder_with_a_thread)
    _scaffold(tmp_path, "python-api", provision=True)
    assert seen_in_thread == [True], "a thread started inside the opt-in is not opted in"
    assert scaffold._scaffold_offline() is True, "the opt-in ends with the call"

    def boom(*_a, **_kw):
        raise RuntimeError("mid-scaffold failure")

    monkeypatch.setitem(scaffold._TYPE_SCAFFOLDERS, "python-api", boom)
    with pytest.raises(RuntimeError):
        scaffold.create_project(
            name="pv-raise",
            description="d",
            base=tmp_path / "r",
            generate_spec=False,
            provision=True,
        )
    assert scaffold._scaffold_offline() is True, "the opt-in ends when the call raises"

    spawned.clear()
    monkeypatch.setitem(scaffold._TYPE_SCAFFOLDERS, "python-api", real)
    for not_true in (0, None, "", "no", 1):
        _scaffold(tmp_path / f"f{not_true!r}", "python-api", provision=not_true)
    assert set(spawned) <= LOCAL, spawned


@pytest.fixture
def spec_dirs(monkeypatch: pytest.MonkeyPatch) -> list[Path]:
    """Where create_project asked the spec writer to put the deploy spec; the writer is faked."""
    seen: list[Path] = []
    monkeypatch.setattr(
        scaffold,
        "generate_and_save_spec",
        lambda _name, _type, _dir, specs_dir, **_kw: seen.append(specs_dir) or specs_dir / "x.yaml",
    )
    return seen


@pytest.mark.parametrize(("provision", "hub"), [(False, False), (True, True)])
def test_hub_spec_needs_the_opt_in(
    tmp_path, spawned, spec_dirs, monkeypatch, provision, hub
) -> None:
    root = tmp_path / "scan-root"
    root.mkdir()
    monkeypatch.setattr(scaffold, "_SYNC_SCAN_ROOT", root)
    project = scaffold.create_project(
        name="pv-spec", description="d", base=root, provision=provision
    )
    if hub:
        assert spec_dirs == [scaffold.FABRIK_ROOT / "specs" / "services"], spec_dirs
    else:
        # without the opt-in no spec at all: never the hub, never <base>/specs, never an untracked copy
        # inside the new repo after its initial commit
        assert spec_dirs == [], spec_dirs
        assert not (project / "specs").exists()


def test_registry_sync_needs_the_opt_in(spawned) -> None:
    """A project directly under the sync's scan root reaches the sync gate; without the opt-in it skips."""
    scaffold._post_scaffold_sync(Path("/opt") / "never-created-provision-probe")
    assert spawned == [], spawned
    with scaffold.provisioning():
        scaffold._post_scaffold_sync(Path("/opt") / "never-created-provision-probe")
    assert spawned == ["sync_projects"], spawned


def test_cli_opts_in(monkeypatch, tmp_path) -> None:
    """`fabrik scaffold` is the one production caller that wants provisioning."""
    from fabrik import cli

    calls: list[dict] = []

    def fake_create_project(*a, **kw):
        calls.append(kw)
        raise SystemExit(0)

    monkeypatch.setattr(scaffold, "create_project", fake_create_project)
    result = CliRunner().invoke(cli.cli, ["scaffold", "pv-cli", "-d", "d", "--no-github"])
    assert calls and calls[0].get("provision") is True, (calls, result.output)


def test_chrome_extension_venv_installs_the_dev_requirements(tmp_path, monkeypatch, capsys) -> None:
    """The scaffold-time venv installs requirements-dev.txt (the test deps live there, out of the image's
    requirements.txt, W-4d6a37c8); the offline hint names the same file."""
    calls: list[tuple[list[str], object]] = []

    def fake_run(cmd, *_a, **kw):
        argv = [str(c) for c in cmd]
        calls.append((argv, kw.get("cwd")))
        if argv[1:4] == ["-m", "venv", ".venv"]:  # what the real venv step leaves behind
            (Path(kw["cwd"]) / ".venv" / "bin").mkdir(parents=True)
        return scaffold.subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(scaffold.subprocess, "run", fake_run)
    monkeypatch.setattr(scaffold, "_install_pre_commit", lambda *_a, **_k: True)
    monkeypatch.delenv("FABRIK_SCAFFOLD_OFFLINE", raising=False)
    project = _scaffold(tmp_path, "chrome-extension", provision=True)
    pip = [
        (argv, Path(cwd)) for argv, cwd in calls if argv and Path(argv[0]).name.startswith("pip")
    ]
    assert len(pip) == 1, calls
    # the project's own venv pip, from the project dir: never the system or hub pip
    assert pip == [
        ([str(project / ".venv" / "bin" / "pip"), "install", "-r", "requirements-dev.txt"], project)
    ], pip

    _scaffold(tmp_path / "offline", "chrome-extension")
    assert "pip install -r requirements-dev.txt" in capsys.readouterr().out
