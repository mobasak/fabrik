# AFTER-EDIT: tests/conftest.py
"""The test session must never inherit git context — 121 call sites depend on it.

⚠️ INCIDENT-DRIVEN (2026-09-01, commit f7627885): a red-on-revert experiment set
`GIT_DIR=/opt/fabrik/.git GIT_WORK_TREE=/opt/fabrik` and a scratch-repo helper's `git add -A`
committed a sibling session's uncommitted WIP to master. Git exports those variables to hooks and
this suite runs from inside one, so the leak is a normal operating condition, not an exotic one.

The first fix guarded a single helper. This guards the SESSION, which is the actual class: measured
2026-09-01, tests/ carries 121 mutating git invocations across 40 files and the prevailing shape is
a bare `subprocess.run(["git", ...])` with no `env=`.
"""

from __future__ import annotations

import os
import pathlib
import subprocess
import tempfile

GIT_VARS = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR")


def test_no_git_context_survives_into_the_test_session() -> None:
    """The scrub itself — asserted on the live environment the tests actually run in."""
    leaked = [v for v in GIT_VARS if v in os.environ]
    assert not leaked, f"git context leaked into the session: {leaked}"


def test_a_bare_git_call_targets_its_own_scratch_repo() -> None:
    """The BEHAVIOUR, in the exact shape the 121 call sites use — no `env=`, no helper.

    This is the assertion that would have prevented f7627885. If it fails, every `git add -A` in
    tests/ is pointed at a real repository.
    """
    with tempfile.TemporaryDirectory() as td:
        d = pathlib.Path(td)
        subprocess.run(["git", "init", "-q", str(d)], check=True)
        resolved = subprocess.run(
            ["git", "-C", str(d), "rev-parse", "--absolute-git-dir"],
            capture_output=True,
            text=True,
        ).stdout.strip()
        assert pathlib.Path(resolved).resolve() == (d / ".git").resolve(), (
            f"a bare git call resolved to {resolved!r} instead of the scratch repo — an inherited "
            f"GIT_DIR is leaking and every mutating git call in tests/ would hit a real repo"
        )
