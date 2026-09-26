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

    assert set(_SIDE_EFFECTS) <= set(spawned), spawned
