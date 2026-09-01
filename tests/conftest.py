"""Pytest configuration and Hypothesis profiles."""

import os
from datetime import timedelta

from hypothesis import Phase, settings

settings.register_profile(
    "ci",
    max_examples=100,
    deadline=None,
    phases=[Phase.generate, Phase.target, Phase.shrink],
)

settings.register_profile(
    "dev",
    max_examples=10,
    deadline=timedelta(milliseconds=5000),
)

settings.register_profile(
    "thorough",
    max_examples=1000,
    deadline=None,
)

settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "dev"))


# ── git isolation: session-wide, because the class is 121 call sites wide ───────────────
#
# ⚠️ INCIDENT-DRIVEN (2026-09-01, commit f7627885). `tests/` helpers build scratch repos with
# `git init` / `git add -A` / `git commit`.
#
# ⚠️ MECHANISM, corrected after being asserted wrong. The first version of this
# comment said "git EXPORTS GIT_DIR/GIT_WORK_TREE to hooks and pre-commit runs pytest here".
# BOTH halves are false on this box and I only checked after a finder pushed back: git 2.43.0
# exports NEITHER to hooks (only a relative `GIT_INDEX_FILE=.git/index`, which resolves
# harmlessly against each subprocess's own cwd), and `grep -c pytest .pre-commit-config.yaml`
# is 0. The ACTUAL cause of f7627885 was a HAND-EXPORTED GIT_DIR in my own red-on-revert
# experiment. The guard is still right — any leak, however it arrives, points 124 mutating
# git calls at a real repo — but inventing a mechanism and presenting it as measurement is
# the defect this whole review kept finding, committed inside the fix for it — so an inherited `GIT_DIR`
# silently redirects every one of those calls at the REAL repository. It happened: a red-on-revert
# experiment that disabled a per-helper env scrub and set
# `GIT_DIR=/opt/fabrik/.git GIT_WORK_TREE=/opt/fabrik` caused `add -A` to commit a sibling
# session's uncommitted WIP to master under author `t <t@fabrik.local>`. Nothing was lost, but a
# peer's in-flight work landed in history with a meaningless author and message.
#
# The first fix guarded ONE helper. Measured afterwards: **121 mutating git invocations across 40
# test files** (`grep -rn '"git"' tests/ --include=*.py | grep -E '"(init|add|commit|merge|…)"'`),
# and the common shape is a BARE `subprocess.run(["git", ...])` with no `env=` — so a per-helper
# guard closes an instance and leaves the class wide open. This closes it once, for the whole
# session, for every existing and future test: autouse by construction, no opt-in.
#
# Deliberately SCRUBBED rather than pinned: a test that genuinely wants one of these sets it on its
# own subprocess call via `env=`, which is explicit and local.
_GIT_ENV_LEAKS = (
    "GIT_DIR",
    "GIT_WORK_TREE",
    "GIT_INDEX_FILE",
    "GIT_OBJECT_DIRECTORY",
    "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    "GIT_COMMON_DIR",
    "GIT_CONFIG_GLOBAL",
    "GIT_CONFIG_SYSTEM",
    "GIT_CONFIG_COUNT",
    "GIT_PREFIX",
    "GIT_AUTHOR_NAME",
    "GIT_AUTHOR_EMAIL",
    "GIT_COMMITTER_NAME",
    "GIT_COMMITTER_EMAIL",
)


def pytest_configure(config):  # noqa: ARG001 - pytest hook signature
    """Strip inherited git-context variables before ANY test runs.

    `pytest_configure` rather than a fixture: it fires before collection, so even a module-level or
    collection-time git call is covered.
    """
    for var in _GIT_ENV_LEAKS:
        os.environ.pop(var, None)
    # GIT_CONFIG_KEY_n / GIT_CONFIG_VALUE_n come in numbered pairs with no fixed bound.
    for key in [k for k in os.environ if k.startswith(("GIT_CONFIG_KEY_", "GIT_CONFIG_VALUE_"))]:
        os.environ.pop(key, None)
