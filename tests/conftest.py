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


# ---------------------------------------------------------------------------------------------
# The resume-mesh lock dir is BOX STATE — pin it to a per-test tmp dir for every test (2026-09-07).
#
# `claude_rotate._selfwatch_lock_dir()` (and `claude-selfwatch.sh`, `selfwatch_check.py`) resolve
# `${CLAUDE_SOUND_LOCKDIR:-/tmp/claude-sound-locks-<uid>}`. Since the relief wake, every fleet test
# that reaches the stamp's relief/dwell unlink calls `_wake_held_sessions`, which ENUMERATES that dir
# and writes `<sid>.holdlifted` for every live armed session it finds. Measured: three live sessions
# received lift files stamped with the tests' fixed clock (epoch 1800000000 → 2027-01-15) and one
# self-watch printed a bogus RESUME line, because — at the time of this fix — only the plan's own seven tests (two setenv sites in the fleet suite,
# three in rotate_v2) set the variable themselves.
# Same shape as the git-env scrub above: session-wide, autouse, no opt-in — a test that wants the
# real dir does not exist, and one that wants a specific dir sets it after this pin (monkeypatch
# fixtures compose; the test's own setenv wins). Grader: tests/test_conftest_isolation.py.
# ---------------------------------------------------------------------------------------------
import pytest  # noqa: E402 — placed with the rule it serves


@pytest.fixture(autouse=True)
def _isolated_sound_lock_dir(tmp_path, monkeypatch):
    locks = tmp_path / "sound-locks"
    locks.mkdir(exist_ok=True)
    monkeypatch.setenv("CLAUDE_SOUND_LOCKDIR", str(locks))
    yield locks


@pytest.fixture(autouse=True)
def _isolated_kaizen_events_dir(tmp_path, monkeypatch):
    """Five tests built their own `dict(os.environ, …)` without `KAIZEN_EVENTS_DIR`, so a suite
    run wrote fabricated round/run events into the operator's REAL per-session events log under
    the live sid (D-191 review round 16, F349). Same class as the two pins above: one autouse
    pin, composable — a test that wants a specific dir still sets it after this."""
    events = tmp_path / "kaizen-events"
    events.mkdir(exist_ok=True)
    monkeypatch.setenv("KAIZEN_EVENTS_DIR", str(events))
    yield events


@pytest.fixture(autouse=True)
def _isolated_command_run_dir(tmp_path, monkeypatch):
    """The convergence and coverage graders read the SESSION'S OWN run record (T4.1/T4.5 —
    `CLAUDE_SESSION_ID` or the harness's `CLAUDE_CODE_SESSION_ID`, under `COMMAND_RUN_DIR` or the
    operator's live `~/.claude/state/command-runs`): a suite run inside a live Claude session
    would otherwise grade fixtures against whatever plan the operator's real record names
    (mail-triage Phase B review, round 3). Same class as the two pins above — one autouse pin,
    composable: a test that wants a specific record still sets its own dir and sid after this."""
    runs = (
        tmp_path / "isolated-command-runs"
    )  # not `command-runs`: test_command_run's own fixture name
    runs.mkdir(exist_ok=True)
    monkeypatch.setenv("COMMAND_RUN_DIR", str(runs))
    # a FIXED fake sid, never an unset one: two `done` tests key one record across a cwd change,
    # which the repo-scoped nosession fallback would split into two records
    monkeypatch.setenv("CLAUDE_SESSION_ID", "pytest-isolated")
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID", raising=False)
    yield runs


# ---------------------------------------------------------------------------------------------
# Bare `tempfile.mkdtemp()` / `NamedTemporaryFile()` land under pytest's basetemp (2026-09-07).
#
# Four hub tests create scratch with `tempfile.mkdtemp()` and never remove it; the suites run by
# three sessions and their review readers left 4,072 `/tmp/tmp*` dirs (2.2 GB) in ONE day, and
# /tmp is the same disk the pool sandboxes, pytest and the Claude scratch share. Pinning
# `tempfile.tempdir` (and TMPDIR for subprocesses) to the session basetemp makes every such dir
# part of the `pytest-<n>` tree pytest itself prunes (it keeps the last three sessions) — the
# class fix, no per-test edit. Session-scoped: one directory per pytest process.
# Grader: tests/test_conftest_isolation.py::test_every_bare_mkdtemp_lands_under_pytest_basetemp.
# ---------------------------------------------------------------------------------------------
@pytest.fixture(autouse=True, scope="session")
def _tempfile_under_basetemp(tmp_path_factory):
    import tempfile

    scratch = tmp_path_factory.getbasetemp() / "mkdtemp"
    scratch.mkdir(exist_ok=True)
    previous_dir, previous_env = tempfile.tempdir, os.environ.get("TMPDIR")
    tempfile.tempdir = str(scratch)
    os.environ["TMPDIR"] = str(scratch)
    yield scratch
    tempfile.tempdir = previous_dir
    if previous_env is None:
        os.environ.pop("TMPDIR", None)
    else:
        os.environ["TMPDIR"] = previous_env
