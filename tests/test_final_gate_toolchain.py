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
