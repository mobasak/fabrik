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
    assert "[Project Name]" not in charter and "[Project Dir]" not in charter
    assert f"`{project}`" in charter  # the real checkout path, never a hard-coded /opt
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


_STUBS = {
    "exit2": "import sys\nsys.exit(2)\n",
    "empty": (
        "import json, sys, pathlib\n"
        "repo = pathlib.Path(sys.argv[sys.argv.index('--repo') + 1])\n"
        "d = repo / '.fabrik' / 'work'\n"
        "d.mkdir(parents=True)\n"
        "(d / 'config.json').write_text(json.dumps({'base_branch': 'x', 'distributor': ''}))\n"
    ),
    "list": (
        "import sys, pathlib\n"
        "repo = pathlib.Path(sys.argv[sys.argv.index('--repo') + 1])\n"
        "d = repo / '.fabrik' / 'work'\n"
        "d.mkdir(parents=True)\n"
        "(d / 'config.json').write_text('[]')\n"
    ),
    "badjson": (
        "import sys, pathlib\n"
        "repo = pathlib.Path(sys.argv[sys.argv.index('--repo') + 1])\n"
        "d = repo / '.fabrik' / 'work'\n"
        "d.mkdir(parents=True)\n"
        "(d / 'config.json').write_text('{')\n"
    ),
}


def _untouched(repo: Path, ledger_before: str) -> None:
    """All or nothing: a failure leaves no MERGE OWNER row, no charter and no store behind."""
    assert (repo / "docs" / "DECISIONS.md").read_text() == ledger_before
    assert not (repo / "docs" / "reference" / "agents" / "coordinator.md").exists()
    assert not (repo / ".fabrik" / "work").exists()


@pytest.mark.parametrize(
    ("work_py", "reason"),
    [
        ("missing", "the hub's scripts/work.py was not found"),  # no script at all
        ("exit2", "work.py init exited 2"),  # init refuses
        ("empty", "work.py init recorded distributor ''"),  # rc 0, no distributor
        ("list", "work.py init recorded distributor []"),  # rc 0, config not an object
        ("badjson", "Expecting property name"),  # rc 0, config not JSON
    ],
)
def test_an_init_failure_warns_and_writes_nothing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    work_py: str,
    reason: str,
) -> None:
    repo = _bare_repo(tmp_path)
    before = (repo / "docs" / "DECISIONS.md").read_text()
    stub = tmp_path / "stub_work.py"
    if work_py in _STUBS:
        stub.write_text(_STUBS[work_py])
    monkeypatch.setattr(scaffold, "_work_py", lambda: stub if work_py != "missing" else None)
    scaffold._emit_coordinator_model(repo, "bare", "2026-10-28")
    out = capsys.readouterr().out
    assert f"WARNING: coordinator model not emitted: {reason}" in out  # the cause, not any warning
    assert "Coordinator: open it as" not in out  # no launch line after a failure
    _untouched(repo, before)


def test_a_timed_out_init_warns_and_writes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    repo = _bare_repo(tmp_path)
    before = (repo / "docs" / "DECISIONS.md").read_text()
    real_run = subprocess.run

    def timeout(args, **kw):  # type: ignore[no-untyped-def]
        if "init" in args:
            raise subprocess.TimeoutExpired(args, 60)
        return real_run(args, **kw)

    monkeypatch.setattr(scaffold.subprocess, "run", timeout)
    scaffold._emit_coordinator_model(repo, "bare", "2026-10-28")
    assert "WARNING: coordinator model not emitted: Command" in capsys.readouterr().out
    _untouched(repo, before)


def test_a_missing_template_warns_and_writes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    repo = _bare_repo(tmp_path)
    before = (repo / "docs" / "DECISIONS.md").read_text()
    monkeypatch.setattr(scaffold, "_COORDINATOR_CHARTER", Path("docs") / "agents" / "NOPE.md")
    scaffold._emit_coordinator_model(repo, "bare", "2026-10-28")
    assert "WARNING: coordinator model not emitted: templates/scaffold/docs/agents/NOPE.md" in (
        capsys.readouterr().out
    )
    _untouched(repo, before)


def test_a_ledger_without_one_d000_row_warns_and_writes_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo = _bare_repo(tmp_path)
    ledger = repo / "docs" / "DECISIONS.md"
    ledger.write_text("# Decisions\n")
    scaffold._emit_coordinator_model(repo, "bare", "2026-10-28")
    assert "exactly one D-000 row" in capsys.readouterr().out
    _untouched(repo, "# Decisions\n")


def test_a_missing_ledger_warns_and_does_not_raise(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo = _bare_repo(tmp_path, ledger=False)
    scaffold._emit_coordinator_model(repo, "bare", "2026-10-28")
    assert "WARNING: coordinator model not emitted: docs/DECISIONS.md was not seeded" in (
        capsys.readouterr().out
    )
    assert not (repo / ".fabrik").exists()
    assert not (repo / "docs" / "reference").exists()


def test_a_read_only_ledger_warns_and_writes_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo = _bare_repo(tmp_path)
    ledger = repo / "docs" / "DECISIONS.md"
    before = ledger.read_text()
    ledger.chmod(0o444)
    try:
        scaffold._emit_coordinator_model(repo, "bare", "2026-10-28")
    finally:
        ledger.chmod(0o644)
    assert "Permission denied" in capsys.readouterr().out
    _untouched(repo, before)
    assert not (repo / ".fabrik").exists() and not (repo / "docs" / "reference").exists()


def test_a_charter_write_failure_restores_the_ledger(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    repo = _bare_repo(tmp_path)
    before = (repo / "docs" / "DECISIONS.md").read_text()
    real_write = Path.write_text

    def failing(self: Path, *a: object, **kw: object) -> int:
        if self.name == "coordinator.md":
            raise OSError("disk full (probe)")
        return real_write(self, *a, **kw)  # type: ignore[arg-type]

    monkeypatch.setattr(Path, "write_text", failing)
    scaffold._emit_coordinator_model(repo, "bare", "2026-10-28")
    monkeypatch.undo()
    assert "disk full (probe)" in capsys.readouterr().out
    _untouched(repo, before)  # the ledger row written first is taken back
    assert not (repo / ".fabrik").exists() and not (repo / "docs" / "reference").exists()


def test_a_pre_existing_store_and_charter_dir_survive_a_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    repo = _bare_repo(tmp_path)
    (repo / ".fabrik" / "work").mkdir(parents=True)
    (repo / ".fabrik" / "work" / "keep.json").write_text("{}")
    (repo / "docs" / "reference" / "agents").mkdir(parents=True)
    stub = tmp_path / "stub_work.py"
    stub.write_text(_STUBS["exit2"])
    monkeypatch.setattr(scaffold, "_work_py", lambda: stub)
    scaffold._emit_coordinator_model(repo, "bare", "2026-10-28")
    assert "work.py init exited 2" in capsys.readouterr().out
    assert (repo / ".fabrik" / "work" / "keep.json").exists()
    assert (repo / "docs" / "reference" / "agents").is_dir()


def test_a_deeply_nested_config_warns_and_does_not_raise(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    repo = _bare_repo(tmp_path)
    before = (repo / "docs" / "DECISIONS.md").read_text()
    stub = tmp_path / "stub_work.py"
    stub.write_text(
        "import sys, pathlib\n"
        "repo = pathlib.Path(sys.argv[sys.argv.index('--repo') + 1])\n"
        "d = repo / '.fabrik' / 'work'\n"
        "d.mkdir(parents=True)\n"
        "(d / 'config.json').write_text('[' * 100000 + ']' * 100000)\n"
    )
    monkeypatch.setattr(scaffold, "_work_py", lambda: stub)
    scaffold._emit_coordinator_model(repo, "bare", "2026-10-28")
    assert "WARNING: coordinator model not emitted" in capsys.readouterr().out
    _untouched(repo, before)
