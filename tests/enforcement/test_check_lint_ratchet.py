"""Behavior contract for scripts/enforcement/check_lint_ratchet.py.

The ratchet's whole value is a per-repo baseline that can only shrink, so every test builds a REAL git
repo with REAL ruff errors and runs the check as a SUBPROCESS — exactly how `final_gate` invokes it. The
error count, the baseline file, and git staging are the things under test; none can be faked with mocks.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

CHECK = Path(__file__).resolve().parents[2] / "scripts" / "enforcement" / "check_lint_ratchet.py"


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=tmp_path, check=True)
    (tmp_path / "src").mkdir()
    dest = tmp_path / "scripts" / "enforcement"
    dest.mkdir(parents=True)
    shutil.copy2(CHECK, dest / CHECK.name)
    return tmp_path


def _run(repo: Path, *args: str) -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, str(repo / "scripts" / "enforcement" / CHECK.name), *args],
        cwd=repo,
        capture_output=True,
        text=True,
        env={**os.environ},
        check=False,
    )
    return proc.returncode, proc.stdout + proc.stderr


def _set_errors(repo: Path, n: int) -> None:
    """Write a src file with exactly ``n`` ruff errors (n unused imports — code F401)."""
    mods = ["os", "sys", "json", "re", "io", "abc", "csv", "gc", "ssl", "pdb"]
    assert n <= len(mods)
    (repo / "src" / "a.py").write_text("".join(f"import {m}\n" for m in mods[:n]))
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "x"], cwd=repo, check=True)


def _baseline(repo: Path) -> int | None:
    f = repo / ".fabrik" / "lint-baseline.json"
    return json.loads(f.read_text())["ruff_errors"] if f.exists() else None


def test_first_run_seeds_the_baseline_and_passes(repo: Path) -> None:
    """Nothing is ever blocked on the run that establishes the floor."""
    _set_errors(repo, 2)
    rc, out = _run(repo)
    assert rc == 0, out
    assert "SEEDED at 2" in out
    assert _baseline(repo) == 2


def test_a_rise_fails_the_gate(repo: Path) -> None:
    """The core promise: an agent can never ADD a new lint error."""
    _set_errors(repo, 2)
    _run(repo)  # seed at 2
    _set_errors(repo, 3)  # +1
    rc, out = _run(repo)
    assert rc == 1, out
    assert "ROSE 2 → 3" in out


def test_check_mode_fails_on_a_rise_but_never_rewrites(repo: Path) -> None:
    """CI/read-only: still blocks a rise, but must not mutate the tracked baseline."""
    _set_errors(repo, 2)
    _run(repo)  # seed at 2
    _set_errors(repo, 4)
    rc, out = _run(repo, "--check")
    assert rc == 1, out
    assert _baseline(repo) == 2, "--check must not tighten OR loosen the baseline"


def test_a_drop_ratchets_the_baseline_down(repo: Path) -> None:
    """The floor can only shrink — a run that lowers the count commits the new, tighter floor."""
    _set_errors(repo, 3)
    _run(repo)  # seed at 3
    _set_errors(repo, 1)
    rc, out = _run(repo)
    assert rc == 0, out
    assert "ratcheted DOWN 3 → 1" in out
    assert _baseline(repo) == 1


def test_a_later_rise_back_to_the_old_count_is_blocked(repo: Path) -> None:
    """After a ratchet-down, the OLD count is now new debt — the floor does not spring back up."""
    _set_errors(repo, 3)
    _run(repo)
    _set_errors(repo, 1)
    _run(repo)  # ratchet to 1
    _set_errors(repo, 3)  # back up — was fine before, is debt now
    rc, out = _run(repo)
    assert rc == 1, out
    assert "ROSE 1 → 3" in out


def test_zero_is_locked(repo: Path) -> None:
    """A clean repo seeds at 0 and stays there — zero-tolerance, permanently."""
    _set_errors(repo, 0)
    _run(repo)  # seed at 0
    rc, out = _run(repo)
    assert rc == 0, out
    assert "LOCKED" in out
    # and adding a single error now fails
    _set_errors(repo, 1)
    rc2, _ = _run(repo)
    assert rc2 == 1


def test_ratchet_down_stages_the_baseline(repo: Path) -> None:
    """The tightened floor must ride along with the change that lowered it (auto-staged)."""
    _set_errors(repo, 3)
    _run(repo)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "seed"], cwd=repo, check=True)
    _set_errors(repo, 1)
    _run(repo)  # ratchet down
    staged = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert ".fabrik/lint-baseline.json" in staged


def test_a_linter_version_change_reseeds_loudly_instead_of_redding_forever(
    tmp_path, monkeypatch, capsys
):
    """01M1H0D5 (youtube, 2026-09-02): the baseline's own seeding commit measured 390 under a newer
    ruff while the file said 388 — an unpinned linter under an absolute count is a permanent red no
    code change can clear. The baseline now carries the ruff version; a version change re-seeds."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("lint_ratchet_mod", CHECK)
    lr = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(lr)
    monkeypatch.setattr(lr, "ROOT", tmp_path)
    monkeypatch.setattr(lr, "BASELINE", tmp_path / ".fabrik" / "lint-baseline.json")
    monkeypatch.setattr(lr, "_baseline_is_gitignored", lambda: False)
    monkeypatch.setattr(lr, "_ruff_version", lambda: "0.15.12")
    monkeypatch.setattr(lr, "_ruff_count", lambda: 390)
    monkeypatch.setattr(sys, "argv", ["check_lint_ratchet.py"])
    (tmp_path / ".fabrik").mkdir()
    (tmp_path / ".fabrik" / "lint-baseline.json").write_text(
        '{"ruff_errors": 388, "ruff_version": "0.14.0"}\n'
    )
    rc = lr.main()
    out = capsys.readouterr().out
    assert rc == 0 and "re-seed" in out.lower() and "0.14.0" in out and "0.15.12" in out
    assert json.loads((tmp_path / ".fabrik" / "lint-baseline.json").read_text()) == {
        "ruff_errors": 390,
        "ruff_version": "0.15.12",
    }
    monkeypatch.setattr(lr, "_ruff_count", lambda: 391)  # same version, more errors → a regression
    assert lr.main() != 0


def test_a_baseline_without_a_version_is_a_plain_ratchet_and_check_mode_never_writes(
    tmp_path, monkeypatch, capsys
):
    """Every existing repo's baseline predates the version field: no re-seed, the ordinary ratchet
    applies; and `--check` must never rewrite the baseline even on a version change."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("lint_ratchet_mod2", CHECK)
    lr = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(lr)
    monkeypatch.setattr(lr, "ROOT", tmp_path)
    monkeypatch.setattr(lr, "BASELINE", tmp_path / ".fabrik" / "lint-baseline.json")
    monkeypatch.setattr(lr, "_baseline_is_gitignored", lambda: False)
    monkeypatch.setattr(lr, "_ruff_version", lambda: "0.15.12")
    monkeypatch.setattr(lr, "_ruff_count", lambda: 390)
    (tmp_path / ".fabrik").mkdir()
    (tmp_path / ".fabrik" / "lint-baseline.json").write_text('{"ruff_errors": 388}\n')
    monkeypatch.setattr(sys, "argv", ["check_lint_ratchet.py"])
    assert lr.main() != 0  # 390 > 388 under an unversioned baseline is a regression, not a re-seed
    (tmp_path / ".fabrik" / "lint-baseline.json").write_text(
        '{"ruff_errors": 388, "ruff_version": "0.14.0"}\n'
    )
    monkeypatch.setattr(sys, "argv", ["check_lint_ratchet.py", "--check"])
    assert lr.main() == 0
    assert json.loads((tmp_path / ".fabrik" / "lint-baseline.json").read_text()) == {
        "ruff_errors": 388,
        "ruff_version": "0.14.0",
    }
