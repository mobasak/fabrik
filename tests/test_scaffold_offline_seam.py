"""The scaffold tests run offline: no venv, no pip, no sudo, no hub registry sync (W-b0c1b4fc).

Every `create_project` in the suite used to build a real venv and pip-install over the network
(~25 s each, 725 s for the scaffold files), probe the local Postgres with `sudo`, and run
scripts/sync_projects.py against the HUB, rewriting data/projects.yaml and docs/PROJECT_CATALOG.md
from inside a test. FABRIK_SCAFFOLD_OFFLINE=1, pinned for every test by tests/conftest.py, keeps
every written file and skips those four side effects.
"""

import os
import subprocess
from pathlib import Path

import pytest

import fabrik.scaffold as scaffold

_SIDE_EFFECTS = ("venv", "pip", "sudo", "sync_projects", "mcp_emitter")


def _classify(cmd) -> str | None:
    argv = [str(c) for c in cmd] if isinstance(cmd, list | tuple) else [str(cmd)]
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
    return None


@pytest.fixture
def spawned(monkeypatch):
    """Record every side-effect command create_project spawns, and FAKE it rather than run it,
    so even a red run on the old code cannot touch the hub or the network."""
    seen: list[str] = []
    real_run = subprocess.run

    def recording_run(cmd, *a, **kw):
        kind = _classify(cmd)
        if kind:
            seen.append(kind)
            return subprocess.CompletedProcess(cmd, 0, "", "")
        return real_run(cmd, *a, **kw)

    monkeypatch.setattr(scaffold.subprocess, "run", recording_run)
    # `pre-commit install` only writes a hook into the new repo's .git: local, not a side effect here
    monkeypatch.setattr(scaffold, "_install_pre_commit", lambda *_a, **_k: True)
    return seen


@pytest.fixture(scope="module")
def _switch_seen_by_a_module_fixture():
    """Module-scoped fixtures run before function-scoped ones; one that scaffolds must be offline."""
    return os.environ.get("FABRIK_SCAFFOLD_OFFLINE")


def test_the_suite_runs_with_the_offline_switch_pinned(_switch_seen_by_a_module_fixture):
    assert os.environ.get("FABRIK_SCAFFOLD_OFFLINE") == "1"
    assert _switch_seen_by_a_module_fixture == "1", "a module-scoped scaffold fixture ran online"


@pytest.mark.parametrize(
    ("value", "offline"),
    [
        ("1", True),
        ("true", True),
        ("YES", True),
        (" on ", True),
        ("0", False),
        ("", False),
        ("no", False),
    ],
)
def test_the_switch_values(monkeypatch, value, offline):
    monkeypatch.setenv("FABRIK_SCAFFOLD_OFFLINE", value)
    assert scaffold._scaffold_offline() is offline


@pytest.mark.parametrize("project_type", ["python-api", "chrome-extension"])
def test_create_project_spawns_no_env_setup_or_hub_sync_offline(
    tmp_path, spawned, project_type, capsys
):
    project = scaffold.create_project(
        name="offline-probe",
        description="offline seam grader",
        base=tmp_path,
        project_type=project_type,
        generate_spec=False,
        use_database=True,
    )

    assert project.exists()
    assert (project / "project.yaml").exists(), "offline mode must still write every file"
    assert spawned == [], f"offline scaffold still spawned: {spawned}"
    assert "Offline scaffold: python -m venv .venv" in capsys.readouterr().out


def test_the_switch_is_what_skips_them(tmp_path, spawned, monkeypatch):
    """Mirror: with the switch off, the same scaffold reaches every side effect again (all faked)."""
    monkeypatch.delenv("FABRIK_SCAFFOLD_OFFLINE", raising=False)

    scaffold.create_project(
        name="online-probe",
        description="offline seam grader",
        base=tmp_path,
        project_type="python-api",
        generate_spec=False,
        use_database=True,
    )

    # sync_projects is reachable only for a project under /opt (see the scan-root tests below)
    assert set(_SIDE_EFFECTS) - {"sync_projects"} <= set(spawned), spawned


def test_a_scaffold_outside_the_scan_root_never_syncs_the_hub(tmp_path, spawned, monkeypatch):
    """W-ddf409c0: scripts/sync_projects.py scans /opt only, so running it after a scaffold anywhere
    else registers nothing and only rewrites the hub's catalog. Online, a tmp-dir scaffold must not
    spawn it."""
    monkeypatch.delenv("FABRIK_SCAFFOLD_OFFLINE", raising=False)

    scaffold.create_project(
        name="elsewhere-probe", description="d", base=tmp_path, generate_spec=False
    )

    assert "sync_projects" not in spawned, spawned


@pytest.mark.parametrize(
    ("project_path", "syncs"),
    [
        ("/opt/probe-x", True),
        ("/tmp/../opt/probe-x", True),  # a spelling that resolves into /opt
        ("/opt/group/probe-x", False),  # nested: the sync lists /opt's children only
        ("/opt-elsewhere/probe-x", False),  # a string-prefix match is not the root
    ],
)
def test_the_sync_gate_is_the_resolved_direct_parent(spawned, monkeypatch, project_path, syncs):
    monkeypatch.delenv("FABRIK_SCAFFOLD_OFFLINE", raising=False)

    scaffold._post_scaffold_sync(Path(project_path))

    assert (spawned == ["sync_projects"]) is syncs, spawned


def test_the_scan_root_matches_sync_projects():
    """The gate copies sync_projects.scan_projects' default root; this keeps the two equal."""
    import importlib.util
    import inspect

    path = Path(__file__).resolve().parents[1] / "scripts" / "sync_projects.py"
    spec = importlib.util.spec_from_file_location("sync_projects_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    default = inspect.signature(module.scan_projects).parameters["root"].default
    assert Path(default) == scaffold._SYNC_SCAN_ROOT
    assert "scan_projects()" in inspect.getsource(module.main), "main() must use the default root"


def test_a_scaffold_under_the_scan_root_still_syncs(spawned, monkeypatch):
    """Mirror: a project created under /opt is still registered (the spawn is faked)."""
    monkeypatch.delenv("FABRIK_SCAFFOLD_OFFLINE", raising=False)

    scaffold._post_scaffold_sync(Path("/opt") / "never-created-sync-probe")

    assert spawned == ["sync_projects"]


def test_a_symlinked_scan_root_still_matches(spawned, monkeypatch, tmp_path):
    """If the scan root is a symlink, a project in its real directory must still sync: the gate
    resolves both sides."""
    monkeypatch.delenv("FABRIK_SCAFFOLD_OFFLINE", raising=False)
    real = tmp_path / "real-opt"
    real.mkdir()
    link = tmp_path / "opt-link"
    link.symlink_to(real)
    monkeypatch.setattr(scaffold, "_SYNC_SCAN_ROOT", link)

    scaffold._post_scaffold_sync(real / "probe-x")

    assert spawned == ["sync_projects"]


@pytest.fixture
def spec_dirs(monkeypatch):
    """Where create_project asked the spec writer to put the deploy spec. The writer is faked, so
    nothing is written: a routing test that reaches the hub branch must never touch the hub's
    tracked specs/services (the 2026-08-27 incident class). Every spec-destination test uses this."""
    seen = []
    monkeypatch.setattr(
        scaffold,
        "generate_and_save_spec",
        lambda _name, _type, _dir, specs_dir, **_kw: seen.append(specs_dir) or specs_dir / "x.yaml",
    )
    return seen


@pytest.mark.parametrize("spelling", ["direct", "dotdot", "symlink", "relative"])
def test_the_spec_destination_follows_the_same_scan_root_test(
    tmp_path, monkeypatch, spec_dirs, spelling
):
    """W-b522ed2e: the deploy spec goes to the hub exactly when the sync would register the project;
    a literal `base == /opt` comparison split the two for any other spelling of the root."""
    root = tmp_path / "scan-root"
    root.mkdir()
    monkeypatch.setattr(scaffold, "_SYNC_SCAN_ROOT", root)
    if spelling == "direct":
        base = root
    elif spelling == "dotdot":
        base = root / ".." / root.name
    elif spelling == "symlink":
        base = tmp_path / "root-link"
        base.symlink_to(root)
    else:
        monkeypatch.chdir(tmp_path)
        base = Path(root.name)

    scaffold.create_project(name="spec-probe", description="d", base=base)

    assert spec_dirs == [scaffold.FABRIK_ROOT / "specs" / "services"], spec_dirs


def test_a_scaffold_outside_the_root_keeps_its_spec_under_its_base(tmp_path, spec_dirs):
    scaffold.create_project(name="spec-probe", description="d", base=tmp_path)

    assert spec_dirs == [tmp_path / "specs" / "services"], spec_dirs


def test_a_string_base_is_accepted(tmp_path, spec_dirs):
    """A str base (as a CLI or script passes it) scaffolds like a Path; it used to raise TypeError."""
    scaffold.create_project(name="spec-probe", description="d", base=str(tmp_path))

    assert (tmp_path / "spec-probe").is_dir()
    assert spec_dirs == [tmp_path / "specs" / "services"], spec_dirs
