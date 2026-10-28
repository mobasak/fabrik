"""A scaffolded repo is born coordinator-ready (W-a02d1c86, operator 2026-10-28: "i want these mechanism for
all repos not only fabrik."): its initial commit carries the MERGE OWNER row, the work store with the
coordinator keys, and the coordinator charter. Builders, their registry and their charters are infra-3's
spawn verb (W-b9ad80ae), so nothing here asserts them.

Input domain: a python-api scaffold into tmp (FABRIK_SCAFFOLD_OFFLINE pinned by conftest), the real
scripts/decisions.py and scripts/work.py run as subprocesses against it; the failure cases stub the
work.py path or delete the seeded ledger.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from fabrik import scaffold

HUB = Path(__file__).resolve().parents[1]


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=True
    ).stdout


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("FABRIK_SCAFFOLD_OFFLINE", "1")
    return scaffold.create_project(
        name="coord-probe",
        description="d",
        base=tmp_path,
        project_type="python-api",
        generate_spec=False,
    )


def test_the_seeded_ledger_names_the_coordinator_as_merge_owner(project: Path) -> None:
    out = subprocess.run(
        [sys.executable, str(HUB / "scripts" / "decisions.py"), "--merge-owner", str(project)],
        capture_output=True,
        text=True,
    )
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip() == "coordinator"
    check = subprocess.run(
        [sys.executable, str(HUB / "scripts" / "decisions.py"), "--root", str(project), "--check"],
        capture_output=True,
        text=True,
    )
    assert check.returncode == 0, check.stdout + check.stderr


def test_the_store_config_carries_the_coordinator_keys_in_work_py_shape(project: Path) -> None:
    raw = (project / ".fabrik" / "work" / "config.json").read_text()
    cfg = json.loads(raw)
    assert cfg["base_branch"] == "mobasak/coord-probe"
    assert cfg["distributor"] == "coordinator"
    assert cfg["coordinator_mode"] is True
    assert cfg["queue_floor"] == 1
    assert cfg["autonomy"] is True
    assert "feedback_owner" in cfg and cfg["feedback_owner"] is None
    # byte-identical to work.py's own writer, so its next write is no churn
    assert raw == json.dumps(cfg, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    assert (project / ".fabrik" / "work" / ".gitignore").read_text() == "*.tmp\n"


def test_the_coordinator_charter_is_rendered(project: Path) -> None:
    charter = (project / "docs" / "reference" / "agents" / "coordinator.md").read_text()
    assert charter.startswith("# Agent charter")  # agent_role.py ignores any other first line
    assert "coord-probe" in charter
    assert "[Project Name]" not in charter
    assert "whoami_agent.py --as coordinator" in charter


def test_all_three_are_tracked_in_the_initial_commit(project: Path) -> None:
    _git(project, "rev-parse", "--verify", "HEAD")
    tracked = set(_git(project, "ls-files").splitlines())
    assert {
        "docs/DECISIONS.md",
        ".fabrik/work/config.json",
        ".fabrik/work/.gitignore",
        "docs/reference/agents/coordinator.md",
    } <= tracked
    assert _git(project, "status", "--porcelain", "--", ".fabrik", "docs") == ""


def _bare_repo(tmp_path: Path, *, ledger: bool = True) -> Path:
    repo = tmp_path / "bare"
    (repo / "docs").mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "checkout", "-q", "-b", "mobasak/bare"], check=True)
    if ledger:
        src = HUB / "templates" / "scaffold" / "docs" / "DECISIONS_TEMPLATE.md"
        (repo / "docs" / "DECISIONS.md").write_text(src.read_text())
    return repo


@pytest.mark.parametrize(
    "work_py",
    [
        "missing",  # no script at all
        "exit2",  # init refuses
        "empty",  # rc 0 but no distributor recorded
    ],
)
def test_an_init_failure_warns_and_does_not_raise(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    work_py: str,
) -> None:
    repo = _bare_repo(tmp_path)
    stub = tmp_path / "stub_work.py"
    if work_py == "exit2":
        stub.write_text("import sys\nsys.exit(2)\n")
    elif work_py == "empty":
        stub.write_text(
            "import json, sys, pathlib\n"
            "repo = pathlib.Path(sys.argv[sys.argv.index('--repo') + 1])\n"
            "d = repo / '.fabrik' / 'work'\n"
            "d.mkdir(parents=True)\n"
            "(d / 'config.json').write_text(json.dumps({'base_branch': 'x', 'distributor': ''}))\n"
        )
    monkeypatch.setattr(scaffold, "_work_py", lambda: stub if work_py != "missing" else None)
    scaffold._emit_coordinator_model(repo, "bare", "2026-10-28")
    assert "WARNING: coordinator model" in capsys.readouterr().out


def test_a_missing_ledger_warns_and_does_not_raise(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo = _bare_repo(tmp_path, ledger=False)
    scaffold._emit_coordinator_model(repo, "bare", "2026-10-28")
    assert "WARNING: coordinator model" in capsys.readouterr().out
