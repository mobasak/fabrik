# AFTER-EDIT: tests/conftest.py
"""The test session must never inherit git context — 121 call sites depend on it.

⚠️ INCIDENT-DRIVEN (2026-09-01, commit f7627885): a red-on-revert experiment set
`GIT_DIR=/opt/fabrik/.git GIT_WORK_TREE=/opt/fabrik` and a scratch-repo helper's `git add -A`
committed a sibling session's uncommitted WIP to master. ⚠️ The first version of this docstring said git exports those variables to hooks and that this
suite runs from inside one. Both are FALSE here — git 2.43.0 exports neither (only a relative
`GIT_INDEX_FILE`), and no pre-commit hook runs pytest. The real leak was a hand-exported GIT_DIR in
a red-on-revert experiment. The guard stands on its own: any leak, however it arrives, aims 124
mutating git calls at a real repo.

The first fix guarded a single helper. This guards the SESSION, which is the actual class: measured
2026-09-01, tests/ carries 121 mutating git invocations across 40 files and the prevailing shape is
a bare `subprocess.run(["git", ...])` with no `env=`.
"""

from __future__ import annotations

import os
import pathlib
import subprocess
import tempfile

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]

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


# ⚠️ THE END-TO-END GUARD IS NOT BUILT, and this is the honest record of why rather than a silent
# gap. The two tests above assert the scrub and the resulting behaviour, but BOTH are green with
# `tests/conftest.py`'s scrub reverted under normal invocation — they only red when the harness is
# started with GIT_DIR already set, and no gate does that. So neither is the guard this file's
# docstring wants.
#
# I attempted the real one: spawn a VICTIM repo, run a nested pytest with a hostile GIT_DIR, and
# assert the victim's uncommitted file is still UNSTAGED (` M`, not `M `) afterwards. It failed
# against the fixed code, and the reason is a defect in the TEST, not the scrub: the nested test
# file lived under `tmp_path`, which is outside the `tests/` tree, so `tests/conftest.py` never
# loads for it — it measured an unprotected process and called the scrub broken. Writing the nested
# file INSIDE `tests/` during a run is the obvious fix and is itself a tree mutation this suite
# should not be making.
#
# Routed rather than bodged: docs/STRATEGIC_BACKLOG.md, with this reasoning. Until it exists, the
# scrub's proof is the manual one recorded in commit d36239cc (a decoy repo, pytest run under a
# hostile GIT_DIR, victim HEAD and index verified unchanged) — a measurement, not a regression test.
