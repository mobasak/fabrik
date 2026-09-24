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
    "GIT_CONFIG_PARAMETERS",
    "GIT_EXEC_PATH",
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


@pytest.fixture
def _private_monkeypatch():
    """A `MonkeyPatch` of its OWN for the autouse box-state pins below. The function-scoped
    `monkeypatch` fixture is SHARED with the test, so a test's `monkeypatch.undo()` — eleven calls
    across eight hub test files when measured, and this probe file's own call keeps it at eleven —
    consumed the whole stack and unpinned every seam
    for the rest of that test: the fleet suite then mkdir'd and read the operator's real
    `~/.claude/state` (Delta 20 seat A, F2). A private instance is out of any test's reach;
    `tests/test_conftest_isolation.py` grades it."""
    mp = pytest.MonkeyPatch()
    yield mp
    mp.undo()


@pytest.fixture(autouse=True)
def _isolated_sound_lock_dir(tmp_path, _private_monkeypatch):
    monkeypatch = _private_monkeypatch
    locks = tmp_path / "sound-locks"
    locks.mkdir(exist_ok=True)
    monkeypatch.setenv("CLAUDE_SOUND_LOCKDIR", str(locks))
    yield locks


@pytest.fixture(autouse=True)
def _isolated_kaizen_events_dir(tmp_path, _private_monkeypatch):
    """Five tests built their own `dict(os.environ, …)` without `KAIZEN_EVENTS_DIR`, so a suite
    run wrote fabricated round/run events into the operator's REAL per-session events log under
    the live sid (D-191 review round 16, F349). Same class as the two pins above: one autouse
    pin, composable — a test that wants a specific dir still sets it after this."""
    monkeypatch = _private_monkeypatch
    events = tmp_path / "kaizen-events"
    events.mkdir(exist_ok=True)
    monkeypatch.setenv("KAIZEN_EVENTS_DIR", str(events))
    yield events


@pytest.fixture(autouse=True)
def _isolated_opt_dir(tmp_path, _private_monkeypatch):
    """`claude_rotate`'s `/opt` seam and its state dir, pinned for EVERY test — autouse, no opt-in.

    ⚠️ This pin exists because a test SENT REAL MAIL. On 2026-09-16 a Phase B grader drove
    `_cmd_tick()` into the fleet-exhausted branch with fixture data (a capped account with no
    eligible successor — exactly the state that branch exists for). That branch calls
    `_mailbox_repos()`, which enumerated the real `/opt` and
    handed every repo it found to `_drain_mail()`. About a thousand "URGENT fleet quota — stop
    gracefully" notices landed in 49 live project mailboxes (mailboxes holding one, inbox and archive together; 48 received one in the six hours before the sweep), ordering every repo on the box to stop
    until 2027-01-22: the fixture's own `_usage_blob` weekly reset, mailed as fact.

    The seam was always advertised ("so tests have ONE seam") and nothing pinned it, so the first
    fixture to reach that branch walked straight out to production. `FABRIK_OPT_DIR` is read at
    CALL time by `_opt_dir()`, so this pin holds whatever order the module is loaded in — patching
    the old import-time module constant did NOT, because a module loaded during the test rebinds it
    to the real `/opt` after this fixture has run, which is exactly what the probe in
    `test_conftest_isolation.py` does.

    `ROTATE_STATE_DIR` is pinned in the same fixture because that branch also writes the
    `fleet-exhausted` stamp, the drain latch and the rotate ledger; a test must never be able to
    latch — or silence — the operator's live fleet warning.
    """
    monkeypatch = _private_monkeypatch
    opt = tmp_path / "isolated-opt"
    opt.mkdir(exist_ok=True)
    state = tmp_path / "isolated-rotate-state"
    state.mkdir(exist_ok=True)
    monkeypatch.setenv("FABRIK_OPT_DIR", str(opt))
    monkeypatch.setenv("ROTATE_STATE_DIR", str(state))
    # ⚠️ The SECOND sink, and the one that fires FIRST: the fleet-exhausted branch calls
    # `_tick_telegram` before `_drain_mail`, and the notifier is resolved from `Path.home()`, which
    # nothing here pins. The first cut of this fixture closed only the mailbox half, leaving a test
    # able to send the operator a Telegram carrying fixture text. `_tick_telegram` returns False for
    # an absent notifier, so a path that does not exist is complete isolation — and the sound system
    # itself is untouched, which it must be: it is production and read-only by standing rule.
    monkeypatch.setenv("CLAUDE_SOUND_SH", str(tmp_path / "no-notifier-in-tests.sh"))
    # ⚠️ THE THIRD SINK, and the only one that WRITES to the operator's live fleet. The tick's flip
    # leg calls `_flip_active`, which `os.replace`s the `active` SYMLINK under `_fleet_root()` —
    # repointing which account every window on this box uses. Containment rested entirely on each
    # fleet test remembering to set this itself, which is the "a seam only a lucky fixture can pin
    # is not a seam" shape that let a grader mail 49 live mailboxes on 2026-09-16. On that same day
    # the operator reported having to switch accounts by hand while off-cadence flip rows appeared
    # in the live ledger during this plan's test runs — consistent with exactly this hole.
    fleet = tmp_path / "isolated-fleet"
    fleet.mkdir(exist_ok=True)
    monkeypatch.setenv("CLAUDE_FLEET_ROOT", str(fleet))
    # and the settings list the installer and the tick's advisory walk, so neither reads the
    # operator's real per-account files
    monkeypatch.setenv("QUOTA_POSTURE_SETTINGS", str(tmp_path / "isolated-settings.json"))
    yield opt


@pytest.fixture(autouse=True)
def _isolated_command_run_dir(tmp_path, _private_monkeypatch):
    """The convergence and coverage graders read the SESSION'S OWN run record (T4.1/T4.5 —
    `CLAUDE_SESSION_ID` or the harness's `CLAUDE_CODE_SESSION_ID`, under `COMMAND_RUN_DIR` or the
    operator's live `~/.claude/state/command-runs`): a suite run inside a live Claude session
    would otherwise grade fixtures against whatever plan the operator's real record names
    (mail-triage Phase B review, round 3). Same class as the two pins above — one autouse pin,
    composable: a test that wants a specific record still sets its own dir and sid after this."""
    monkeypatch = _private_monkeypatch
    runs = (
        tmp_path / "isolated-command-runs"
    )  # not `command-runs`: test_command_run's own fixture name
    runs.mkdir(exist_ok=True)
    monkeypatch.setenv("COMMAND_RUN_DIR", str(runs))
    # ⚠️ the recorder's `_active_account()` reads `~/.claude/.active-account` on every `start` — a READ, but
    # the file's own invariant is that nothing here reaches the operator's live state (closing seat 6)
    monkeypatch.setenv("COMMAND_RUN_ACCOUNT_FILE", str(tmp_path / "active-account"))
    # a FIXED fake sid, never an unset one: two `done` tests key one record across a cwd change,
    # which the repo-scoped nosession fallback would split into two records
    monkeypatch.setenv("CLAUDE_SESSION_ID", "pytest-isolated")
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID", raising=False)
    # The identity BINDING store (D-267/D-268). The READ side is already safe — the delenv above
    # means a grader resolves "" by default and cannot pick up a live binding — but the WRITER
    # graders would otherwise append to the operator's real ~/.claude/state/agent-identity.jsonl.
    # Same class as the three pins above: one autouse pin, no opt-in.
    monkeypatch.setenv("AGENT_IDENTITY_FILE", str(tmp_path / "agent-identity.jsonl"))
    yield runs


# ---------------------------------------------------------------------------------------------
# The app-role registrar step never reaches the live fleet from a test (audit-log-everywhere T04).
#
# `_provision_postgres` now calls `_provision_app_role`, which runs `ensure_app_role` (CREATE ROLE,
# GRANT/REVOKE on the named database) and `read_env` (ssh). A dozen existing suites drive
# `_provision_postgres` with only `create_database` patched — unpatched, the new step would ssh to
# the real postgres-main and could mint `<db>_app` on a real database (the db_name tests use
# `depends.postgres: main`). The step is stubbed for every test; a module that exercises it sets
# `LIVE_APP_ROLE_STEP = True` and patches the drivers itself (tests/test_app_role_provision.py) —
# and there `_run_sql` and every reachable `ssh` binding fail loud by default, so forgetting a
# patch raises instead of reaching postgres-main (the cheapest way to game the opt-in, closed).
# ---------------------------------------------------------------------------------------------
def _fail_loud(name):
    def _refuse(*_a, **_k):
        raise RuntimeError(f"test reached the live fleet: {name}")

    return _refuse


@pytest.fixture(autouse=True)
def _no_live_app_role_step(request, _private_monkeypatch):
    if getattr(request.module, "LIVE_APP_ROLE_STEP", False):
        # An opted-in module still cannot reach the fleet by OMISSION: every binding the
        # step can reach fails loud unless the test patches it (its patches win, being
        # applied later). `fabrik.drivers.postgres` binds `ssh` at import; deployer_ssh
        # and the other callers import `fabrik.drivers.ssh.ssh` lazily at call time.
        import fabrik.drivers.postgres as _pg
        import fabrik.drivers.ssh as _ssh_mod

        _private_monkeypatch.setattr(_ssh_mod, "ssh", _fail_loud("fabrik.drivers.ssh.ssh"))
        _private_monkeypatch.setattr(_pg, "ssh", _fail_loud("fabrik.drivers.postgres.ssh"))
        _private_monkeypatch.setattr(
            _pg, "_run_sql", _fail_loud("fabrik.drivers.postgres._run_sql")
        )
        return
    try:
        from fabrik.orchestrator.infrastructure import InfrastructureProvisioner
    except ImportError:
        return
    _private_monkeypatch.setattr(
        InfrastructureProvisioner, "_provision_app_role", lambda *a, **k: None, raising=False
    )


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
