"""W-83ff5917: a test run imports `fabrik` from the tree it runs in, never the main checkout.

Every hub worktree shares /opt/fabrik/.venv, whose editable install puts /opt/fabrik/src on
sys.path; without the root conftest.py putting this tree's src first, a worktree's tests graded
master's code. Both the test process and a subprocess that inherits os.environ are checked. In the
main checkout both pass with or without the fix by construction; the grader bites in a worktree.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import fabrik

TREE_SRC = Path(__file__).resolve().parents[1] / "src"


def test_the_test_process_imports_this_trees_fabrik() -> None:
    assert Path(fabrik.__file__).resolve().is_relative_to(TREE_SRC), fabrik.__file__


def test_a_subprocess_imports_this_trees_fabrik() -> None:
    out = subprocess.run(
        [sys.executable, "-c", "import fabrik; print(fabrik.__file__)"],
        capture_output=True,
        text=True,
        check=True,
        cwd="/",
        env=dict(os.environ),
    ).stdout.strip()
    assert Path(out).resolve().is_relative_to(TREE_SRC), out
