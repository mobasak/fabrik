"""Behavior contract for the completion gate's advisory `Work items (sync)` row (ticket T06).

The row runs `scripts/work.py sync --check` in the Tier-2 block with `advisory=True`: stdout kept
on exit 0 (the drift is named on a green row), a real red once the repo is past its migration
window and `sync --check` exits 1. A repo without `scripts/work.py`, or without a store, passes.

Each test builds a throwaway git repo under `tmp_path`, points the gate's `PROJECT_ROOT` at it,
and runs `run_consistency_checks(tier=2)` with every OTHER row stubbed — so the row under test
executes the real `work.py` (copied into the fixture repo) through the real `run_optional_check`
and `run_cmd`, never the hub's own `.fabrik/work/`.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

HUB = Path(__file__).resolve().parents[1]
GATE = HUB / "scripts" / "final_gate.py"
WORK = HUB / "scripts" / "work.py"
ROW = "Work items (sync)"
PLAN = "2026-09-24-plan-in-progress"
PLAN_REL = f"docs/development/plans/{PLAN}/{PLAN}.md"


@pytest.fixture
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    """Hermetic git identity + HOME; `run_cmd` copies `os.environ`, so it is set there too."""
    (tmp_path / "home").mkdir()
    values = {
        "HOME": str(tmp_path / "home"),
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@example.invalid",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@example.invalid",
    }
    for key in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR"):
        monkeypatch.delenv(key, raising=False)
    for key, val in values.items():
        monkeypatch.setenv(key, val)
    return {"PATH": "/usr/bin:/bin", **values}


def _sh(cmd: list[str], cwd: Path, env: dict[str, str]) -> str:
    r = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, (cmd, r.stdout, r.stderr)
    return r.stdout


def _repo(tmp_path: Path, env: dict[str, str], *, with_work: bool = True) -> Path:
    repo = tmp_path / "repo"
    _sh(["git", "init", "-q", "-b", "main", str(repo)], tmp_path, env)
    (repo / "README").write_text("seed\n", encoding="utf-8")
    _sh(["git", "add", "README"], repo, env)
    _sh(["git", "commit", "-q", "-m", "seed"], repo, env)
    if with_work:
        (repo / "scripts").mkdir()
        shutil.copy2(WORK, repo / "scripts" / "work.py")
    return repo.resolve()


def _init_store(repo: Path, env: dict[str, str]) -> None:
    _sh([sys.executable, "scripts/work.py", "init", "--distributor", "intel"], repo, env)


def _class3_plan(repo: Path) -> None:
    """An IN-PROGRESS plan spine with no active lock — drift class 3 (blocking class)."""
    d = repo / "docs" / "development" / "plans" / PLAN
    d.mkdir(parents=True)
    (d / f"{PLAN}.md").write_text(f"# {PLAN}\n\nStatus: IN-PROGRESS\nOwner: infra\n", "utf-8")


def _past_migration_window(repo: Path) -> None:
    """`migrated_at` 10 days ago plus 7 consecutive clean daily readings after it."""
    cfg_path = repo / ".fabrik" / "work" / "config.json"
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    migrated = datetime.now(UTC) - timedelta(days=10)
    fmt = "%Y-%m-%dT%H:%M:%S.%fZ"
    cfg["migrated_at"] = migrated.strftime(fmt)
    cfg_path.write_text(json.dumps(cfg), encoding="utf-8")
    readings = repo / ".git" / "fabrik-work" / "readings.jsonl"
    readings.parent.mkdir(parents=True, exist_ok=True)
    with readings.open("a", encoding="utf-8") as f:
        for i in range(1, 8):
            row = {
                "at": (migrated + timedelta(days=i, hours=1)).strftime(fmt),
                "kind": "sync",
                "counts": {str(n): 0 for n in range(1, 9)},
                "blocking_active": False,
            }
            f.write(json.dumps(row) + "\n")


def _gate(repo: Path) -> Any:
    spec = importlib.util.spec_from_file_location("fg_work_row", GATE)
    assert spec and spec.loader
    mod: Any = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.PROJECT_ROOT = repo
    mod.PYTHON = sys.executable
    return mod


def _rows(mod: Any, tier: int = 2) -> list[tuple[str, bool, str]]:
    """Every row the tier builds; only the row under test runs for real."""
    real_check, real_cmd = mod.run_optional_check, mod.run_cmd

    def check(sp: str, cn: str, *a: str, **k: object) -> tuple[str, bool, str]:
        return real_check(sp, cn, *a, **k) if cn == ROW else (cn, True, "")

    def cmd(c: list[str], cwd: Path | None = None, timeout: int | None = None):
        return real_cmd(c, cwd, timeout) if any("work.py" in p for p in c) else (0, "")

    mod.run_optional_check, mod.run_cmd = check, cmd
    try:
        return mod.run_consistency_checks(tier=tier, changed_files=set())
    finally:
        mod.run_optional_check, mod.run_cmd = real_check, real_cmd


def _row(rows: list[tuple[str, bool, str]]) -> tuple[str, bool, str]:
    found = [r for r in rows if r[0] == ROW]
    assert len(found) == 1, f"expected one {ROW!r} row, got {[r[0] for r in rows]}"
    return found[0]


def test_a_non_blocking_store_with_class_3_drift_passes_and_names_the_drift(tmp_path, env):
    repo = _repo(tmp_path, env)
    _init_store(repo, env)
    _class3_plan(repo)
    mod = _gate(repo)

    rows = _rows(mod)
    _name, ok, out = _row(rows)

    assert ok, out
    assert f"DRIFT 3 (blocking)  {PLAN_REL}" in out  # advisory=True kept stdout on exit 0
    assert ROW not in mod.WARN_ONLY_CHECKS  # it CAN fail, so it is not declared warn_only


def test_a_blocking_store_with_class_3_drift_fails_the_row_and_the_gate(tmp_path, env):
    repo = _repo(tmp_path, env)
    _init_store(repo, env)
    _class3_plan(repo)
    _past_migration_window(repo)
    mod = _gate(repo)

    rows = _rows(mod)
    _name, ok, out = _row(rows)

    assert not ok
    assert f"DRIFT 3 (blocking)  {PLAN_REL}" in out
    failed = [r for r in rows if not r[1]]  # the gate's own status rule: any red row → failure
    assert [r[0] for r in failed] == [ROW]


def test_a_repo_with_no_store_passes_with_the_one_line_message(tmp_path, env):
    repo = _repo(tmp_path, env)
    mod = _gate(repo)

    _name, ok, out = _row(_rows(mod))

    assert ok
    assert out == f"no work store in {repo} — nothing to sync"
    assert not (repo / ".fabrik").exists()
    assert not (repo / ".git" / "fabrik-work").exists()


def test_a_repo_without_work_py_passes_with_the_not_present_row(tmp_path, env):
    repo = _repo(tmp_path, env, with_work=False)
    mod = _gate(repo)

    _name, ok, out = _row(_rows(mod))

    assert ok
    assert out == "⚠ check not present, skipping: scripts/work.py"


@pytest.mark.parametrize("tier", [1, 3])
def test_the_row_is_tier_2_only(tmp_path, env, tier):
    repo = _repo(tmp_path, env, with_work=False)
    mod = _gate(repo)

    assert ROW not in [r[0] for r in _rows(mod, tier)]
