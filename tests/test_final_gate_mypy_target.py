"""Regression: detect_src_package() must never target a nonexistent src/ for flat-layout
projects (the bug that silently disabled mypy for every flat repo — youtube, captcha, …).
See final_gate.py detect_src_package / run_mypy_with_recovery."""
from __future__ import annotations

import importlib

import pytest

import_gate = lambda: importlib.import_module("scripts.final_gate")  # noqa: E731


@pytest.fixture
def fg(monkeypatch, tmp_path):
    mod = import_gate()
    monkeypatch.setattr(mod, "PROJECT_ROOT", tmp_path)
    return mod, tmp_path


def test_src_layout_single_package(fg):
    mod, root = fg
    (root / "src" / "myapp").mkdir(parents=True)
    assert mod.detect_src_package() == "src/myapp"


def test_src_layout_multi_package(fg):
    mod, root = fg
    (root / "src" / "a").mkdir(parents=True)
    (root / "src" / "b").mkdir(parents=True)
    assert mod.detect_src_package() == "src/"


def test_flat_layout_no_config_returns_dot_not_nonexistent_src(fg):
    # THE bug: used to return "src/" → mypy "Cannot read file 'src'" → mypy never ran.
    mod, root = fg
    (root / "main.py").write_text("x = 1\n")
    assert mod.detect_src_package() == "."  # never "src/"


def test_flat_layout_with_mypy_files_returns_empty_for_self_discovery(fg):
    mod, root = fg
    (root / "pyproject.toml").write_text('[tool.mypy]\nfiles = ["pkg"]\n')
    (root / "pkg").mkdir()
    assert mod.detect_src_package() == ""


def test_run_mypy_argv_shape(fg, monkeypatch):
    """--exclude only for the flat "." fallback; the target is appended only when non-empty
    (empty "" → mypy self-discovers via [tool.mypy] files=)."""
    import subprocess

    mod, _ = fg
    seen: dict[str, list[str]] = {}

    def cap(cmd, **kw):
        seen["cmd"] = list(cmd)
        raise subprocess.TimeoutExpired("mypy", 1)  # bail before real mypy; inspect argv only

    monkeypatch.setattr(subprocess, "run", cap)
    for target, want_exclude, want_target in [(".", True, True), ("src/foo", False, True), ("", False, False)]:
        seen.clear()
        mod.run_mypy_with_recovery(target, timeout=1)
        cmd = seen["cmd"]
        assert ("--exclude" in cmd) == want_exclude, (target, cmd)
        if want_target:
            assert target in cmd, (target, cmd)
        else:  # empty target: no path appended at all
            assert "" not in cmd and cmd[-1].startswith("--"), (target, cmd)
