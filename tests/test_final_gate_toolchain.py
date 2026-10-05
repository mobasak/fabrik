"""transdoc finding 1.2: the gate must not return a TREE verdict chosen by the interpreter."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("fg_toolchain", REPO / "scripts" / "final_gate.py")
fg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fg)


def test_probe_names_the_module_the_interpreter_cannot_import(monkeypatch) -> None:
    """transdoc 1.2: `PYTHON` silently falls back to whatever invoked the gate when
    the venv has no ruff, so the SAME tree returned "failure" under one interpreter
    and "success" under another, same second. status:"failure" must mean the tree is
    bad, never that the toolchain is missing — otherwise an agent learns to prefer
    whichever invocation passes, the worst thing a completion gate can teach."""
    monkeypatch.setattr(fg, "REQUIRED_TOOLS", ("a_module_that_does_not_exist_xyz",))
    assert fg._toolchain_missing(sys.executable) == "a_module_that_does_not_exist_xyz"


def test_probe_is_silent_on_a_healthy_interpreter(monkeypatch) -> None:
    """It must not cry setup-error on a working toolchain — that would be the same
    false-verdict failure pointing the other way."""
    monkeypatch.setattr(fg, "REQUIRED_TOOLS", ("json", "pathlib"))
    assert fg._toolchain_missing(sys.executable) == ""


def test_a_broken_interpreter_path_is_reported_not_crashed(monkeypatch) -> None:
    """A nonexistent interpreter must surface as the missing tool, never an OSError
    escaping the gate's own entry point. Probed via pytest since the interpreter/ruff
    decoupling (transdoc 01M171R8): ruff is a resolved BINARY probe and legitimately
    ignores the interpreter now — pytest is the interpreter-bound tool."""
    monkeypatch.setattr(fg, "REQUIRED_TOOLS", ("pytest",))
    assert fg._toolchain_missing("/nonexistent/python") == "pytest"


def test_the_setup_error_names_the_remedy_that_works() -> None:
    """W-2cfa7b8e: the payload said the interpreter "cannot import" ruff and offered "invoke the
    gate with one that has it" — ruff is a resolved BINARY, and with a `.venv` present the gate
    runs `.venv/bin/python` whichever interpreter invoked it, so that remedy changes nothing."""
    ruff_error, ruff_fix = fg._setup_error("ruff")
    assert "import" not in ruff_error and fg.RUFF in ruff_error
    assert "PATH" in ruff_fix and ".venv" in ruff_fix
    py_error, py_fix = fg._setup_error("pytest")
    assert fg.PYTHON in py_error and "import 'pytest'" in py_error
    assert ".venv" in py_fix
    for fix in (ruff_fix, py_fix):
        assert "invoke the gate with" not in fix


def test_with_no_venv_the_setup_error_says_to_create_one(monkeypatch, tmp_path) -> None:
    """Without a `.venv`, "install pytest into .venv" names a directory that does not exist."""
    monkeypatch.setattr(fg, "VENV_PYTHON", tmp_path / "absent" / "bin" / "python")
    _, fix = fg._setup_error("pytest")
    assert "python3 -m venv .venv" in fix


def test_an_absent_mypy_is_a_labelled_skip_not_a_red() -> None:
    """W-2cfa7b8e: bandit's leg had the NOT INSTALLED skip and mypy's did not, so a `.venv`
    without mypy failed the gate red while every contract said an absent tool is SKIPPED."""
    name, ok, detail = fg._mypy_row(1, "/p/.venv/bin/python: No module named mypy")
    assert (name, ok) == ("mypy (NOT INSTALLED — skipped)", True)
    assert "NOT INSTALLED" in detail
    assert fg._mypy_row(1, "src/a.py:1: error: boom") == ("mypy", False, "src/a.py:1: error: boom")
    assert fg._mypy_row(0, "Success") == ("mypy", True, "")


def test_a_broken_install_is_not_read_as_an_absent_one() -> None:
    """W-2cfa7b8e closing pass: a mypy package with no `__main__` prints "No module named
    mypy.__main__", which the bare substring check read as NOT INSTALLED — a green skip over a
    broken toolchain. Every "No module named <tool>" site shares the matcher."""
    broken = "/p/.venv/bin/python: No module named mypy.__main__; 'mypy' is a package and cannot be directly executed"
    assert not fg._module_absent(broken, "mypy")
    assert fg._mypy_row(1, broken)[:2] == ("mypy", False)
    assert fg._module_absent("/p/.venv/bin/python: No module named mypy", "mypy")
    assert not fg._module_absent("No module named mypy_extensions", "mypy")
    for tool in ("bandit", "pytest", "sqlfluff", "vulture"):
        assert fg._module_absent(f"/p/python: No module named {tool}\n", tool)
        assert not fg._module_absent(f"/p/python: No module named {tool}.__main__", tool)
