"""Pytest configuration and Hypothesis profiles."""

import os
import re
import shutil
import subprocess
import tempfile
from datetime import timedelta
from pathlib import Path

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


def pytest_configure(config):
    """Strip inherited git-context variables before ANY test runs.

    `pytest_configure` rather than a fixture: it fires before collection, so even a module-level or
    collection-time git call is covered.
    """
    config.addinivalue_line(
        "markers", "live_fleet: reaches the real fleet; runs only when a person opts in"
    )
    for var in _GIT_ENV_LEAKS:
        os.environ.pop(var, None)
    # GIT_CONFIG_KEY_n / GIT_CONFIG_VALUE_n come in numbered pairs with no fixed bound.
    for key in [k for k in os.environ if k.startswith(("GIT_CONFIG_KEY_", "GIT_CONFIG_VALUE_"))]:
        os.environ.pop(key, None)
    _install_fleet_guard()


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
    # a refused rotate-ledger row goes to a fallback file in the system temp dir (W-16ebba0a)
    monkeypatch.setenv("ROTATE_LEDGER_FALLBACK", str(state / "ledger-fallback.jsonl"))
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
    (mail-triage Phase B review, round 3). Same class as the pins above — one autouse pin,
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
    # The caller's ROLE (`CLAUDE_AGENT`, the first source `whoami_agent.resolve_agent_name` reads):
    # a hub window runs with it set, and mail.py stamps it into every sent message's `from-agent:`
    # and reply addressing (01M3PT248G7A) — so a grader's verdict would depend on which window ran
    # the suite. A test that needs a role sets it itself.
    monkeypatch.delenv("CLAUDE_AGENT", raising=False)
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
# No test reaches the live fleet over ssh, scp or rsync (fabrik-mail 01M39XVS, 2026-09-24).
#
# Suites that patched only some drivers ran real SQL on postgres-main — `ensure_shared_analytics_db`
# and `create_subagent_ins_role` (CREATE ROLE on fabrik_analytics) — and real watchdog image builds
# over `ssh vps`, on every run. The driver-by-driver stubs above cannot close that class: 14 modules
# bind `ssh` at import and ~25 call sites import it lazily, and vultr/dns/coolify/audit/watchdog
# shell out to `ssh` themselves. Two layers, both installed in `pytest_configure` (before collection,
# so a module-level or decorator-time call is covered) and removed in `pytest_unconfigure`:
#   1. `subprocess.Popen` becomes `_NoFleetPopen`, which refuses a fleet binary named directly —
#      argv[0], `executable=`, the command at the head of each segment of a shell string (`;`, `&&`,
#      `|`, `$(`, backtick) and of a `sh|bash -…c` payload. `run`, `check_output`, `call` and
#      asyncio's transport all construct it at call time, whatever name a module imported them under.
#   2. A PATH shim: a dir of fake `ssh`/`scp`/… that print the refusal and exit 255, prepended to
#      PATH. It catches what layer 1 cannot see — a wrapper (`env ssh`, `timeout 30 ssh`), a script
#      that runs ssh itself (vultr's bootstrap-*.sh), `os.system` — without scanning arguments, so
#      `echo ssh` still runs.
# Residual, stated: a SCRIPT that runs an absolute `/usr/bin/ssh`, or one started with PATH dropped
# (`env -i`, sudo's secure_path) that runs ssh by name, bypasses both layers; no src/ call site does
# that today. After a wrapper (sudo, env, timeout, exec, …) any word naming a fleet binary is refused. A test's own mock of `subprocess.run`/`Popen` still wins.
# `FABRIK_TEST_ALLOW_FLEET=1` lets a PERSON run a deliberate live check (layer 1 reads it at call
# time; layer 2 is not installed when it is set at start). COBRA (D-253): the cheapest bypass is a
# test that sets it, so tests/test_conftest_isolation.py::test_no_test_opts_itself_into_the_live_fleet
# refuses any test file naming it. Graders: the `*fleet*` tests in that file.
# ---------------------------------------------------------------------------------------------
_FLEET_BINARIES = frozenset({"ssh", "scp", "rsync", "sftp", "sshpass"})
_SHELLS = frozenset({"sh", "bash", "dash", "zsh"})
# a command that runs ANOTHER command from its arguments: after one of these, a fleet binary
# anywhere in the words is refused (`sudo -u root ssh`, `env -i ssh`, `timeout 30 ssh`, `exec ssh`)
_WRAPPERS = frozenset(
    {
        "sudo",
        "doas",
        "env",
        "timeout",
        "nice",
        "nohup",
        "setsid",
        "stdbuf",
        "xargs",
        "strace",
        "command",
        "builtin",
        "exec",
        "time",
        "!",
        "if",
        "then",
        "else",
        "do",
        "while",
        "until",
        "{",
        "elif",
        "eval",
        "coproc",
        "flock",
        "ionice",
        "chroot",
        "su",
        "unbuffer",
        "busybox",
        "script",
    }
)
_SHELL_C_FLAG = re.compile(r"^-[A-Za-z]*c[A-Za-z]*$")
_REDIRECTION = re.compile(r"^\d*[<>]")
_FLEET_REFUSAL = "test reached the live fleet"


def _command_names(words: list[str]) -> list[str]:
    """Basenames that may be EXECUTED by one simple command: its head, or every word after a wrapper."""
    words = [w for w in words if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", w)]
    words = [w for w in words if not _REDIRECTION.match(w)]
    if not words:
        return []
    head = os.path.basename(words[0])
    if head in _WRAPPERS:
        return [head] + [os.path.basename(w) for w in words[1:]]
    if head in _SHELLS:
        flag = None
        takes_arg = False
        for k, w in enumerate(words[1:], 1):
            if takes_arg:  # the argument of -o/-O/+o/+O (`bash -o pipefail -c …`)
                takes_arg = False
                continue
            if w in ("-o", "-O", "+o", "+O"):
                takes_arg = True
                continue
            if not w.startswith(("-", "+")):
                break  # the script operand: a later -c belongs to the script, not the shell
            if _SHELL_C_FLAG.match(w):
                flag = k
                break
        if flag is not None and flag + 1 < len(words):
            return [head] + _shell_heads(words[flag + 1])
    return [head]


def _shell_heads(text: str) -> list[str]:
    """What a shell command line may execute: each simple command, quote-aware, plus substitutions."""
    import shlex

    names: list[str] = []
    for sub in re.findall(r"\$\(([^()]*)\)|`([^`]*)`", text):  # $(…) and `…`, quoted or not
        names += _shell_heads(sub[0] or sub[1])
    try:
        # a newline separates commands like `;` (shlex treats it as whitespace)
        lexer = shlex.shlex(text.replace("\n", ";"), posix=True, punctuation_chars=True)
        lexer.whitespace_split = True
        tokens = list(lexer)
    except ValueError:
        tokens = text.split()
    segment: list[str] = []
    target = False  # the word after a redirection operator is its target, never a command
    for tok in [*tokens, ";"]:
        if tok and set(tok) <= set("();<>|&\n"):
            if tok.strip("<>"):  # an operator ends the simple command
                names += _command_names(segment)
                segment, target = [], False
            else:  # a redirection: drop an fd number glued before it, skip its target
                if segment and segment[-1].isdigit():
                    segment.pop()
                target = True
            continue
        if target:
            target = False
            continue
        segment.append(tok.lstrip("`$("))
    return names


def _fleet_binary_in(args, shell: bool, executable=None) -> str | None:
    """The fleet binary this Popen call would start directly, or None."""
    if executable is not None:
        name = os.path.basename(os.fsdecode(executable))
        if name in _FLEET_BINARIES:
            return name
    if isinstance(args, (bytes, os.PathLike)):
        args = os.fsdecode(args)
    if isinstance(args, str):
        argv = [args]
    else:
        argv = [os.fsdecode(a) if isinstance(a, (bytes, os.PathLike)) else str(a) for a in args]
    if not argv:
        return None
    # a shell=True LIST runs its first element as the command line
    names = _shell_heads(argv[0]) if shell else _command_names(argv)
    return next((n for n in names if n in _FLEET_BINARIES), None)


_REAL_POPEN = subprocess.Popen


class _NoFleetPopen(_REAL_POPEN):  # type: ignore[misc, valid-type]
    """subprocess.Popen that refuses a fleet binary unless a person opted in."""

    def __init__(self, args, *a, **k):
        # Popen(args, bufsize, executable, stdin, stdout, stderr, preexec_fn, close_fds, shell, ...)
        executable = k.get("executable", a[1] if len(a) > 1 else None)
        shell = bool(k.get("shell", a[7] if len(a) > 7 else False))
        binary = _fleet_binary_in(args, shell, executable)
        if binary and os.environ.get("FABRIK_TEST_ALLOW_FLEET") != "1":
            raise RuntimeError(f"{_FLEET_REFUSAL}: {binary} (subprocess guard)")
        super().__init__(args, *a, **k)


_FLEET_SHIM_DIR: str | None = None


def _install_fleet_guard() -> None:
    global _FLEET_SHIM_DIR
    subprocess.Popen = _NoFleetPopen  # type: ignore[misc]
    if os.environ.get("FABRIK_TEST_ALLOW_FLEET") == "1" or _FLEET_SHIM_DIR:
        return
    _FLEET_SHIM_DIR = tempfile.mkdtemp(prefix="fabrik-fleet-shim-")
    for name in _FLEET_BINARIES:
        shim = Path(_FLEET_SHIM_DIR) / name
        shim.write_text(
            f'#!/bin/sh\necho "{_FLEET_REFUSAL}: {name} (PATH shim)" >&2\nexit 255\n',
            encoding="utf-8",
        )
        shim.chmod(0o755)
    os.environ["PATH"] = _FLEET_SHIM_DIR + os.pathsep + os.environ.get("PATH", "")


def _remove_fleet_guard() -> None:
    global _FLEET_SHIM_DIR
    subprocess.Popen = _REAL_POPEN  # type: ignore[misc]
    if _FLEET_SHIM_DIR:
        parts = os.environ.get("PATH", "").split(os.pathsep)
        os.environ["PATH"] = os.pathsep.join(p for p in parts if p != _FLEET_SHIM_DIR)
        shutil.rmtree(_FLEET_SHIM_DIR, ignore_errors=True)
        _FLEET_SHIM_DIR = None


def pytest_unconfigure(config):  # noqa: ARG001 - pytest hook signature
    _remove_fleet_guard()


def pytest_collection_modifyitems(config, items):  # noqa: ARG001 - pytest hook signature
    """A `live_fleet`-marked test is a deliberate live check: it runs only when a PERSON opted in."""
    if os.environ.get("FABRIK_TEST_ALLOW_FLEET") == "1":
        return
    skip = pytest.mark.skip(
        reason="live_fleet: reaches the real fleet (set FABRIK_TEST_ALLOW_FLEET=1)"
    )
    for item in items:
        if item.get_closest_marker("live_fleet"):
            item.add_marker(skip)


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


# Every scaffold a test runs is OFFLINE (W-b0c1b4fc): files written, but no venv, no pip install, no
# `sudo -u postgres` probe, no .mcp.json emitter and no scripts/sync_projects.py run against the hub.
# Those cost ~25 s per `create_project` (725 s for the scaffold files) and rewrote the hub's
# data/projects.yaml and docs/PROJECT_CATALOG.md from inside tests. SESSION-scoped on purpose: a
# function-scoped pin runs AFTER module-scoped fixtures, and tests/test_scaffold_saas_backend.py
# builds its project in one, so it scaffolded online. Read at call time by
# `scaffold._scaffold_offline()`; a test that wants the real steps deletes the variable with its own
# monkeypatch, which restores it afterwards. Grader: tests/test_scaffold_offline_seam.py.
@pytest.fixture(autouse=True, scope="session")
def _offline_scaffold():
    previous = os.environ.get("FABRIK_SCAFFOLD_OFFLINE")
    os.environ["FABRIK_SCAFFOLD_OFFLINE"] = "1"
    yield
    if previous is None:
        os.environ.pop("FABRIK_SCAFFOLD_OFFLINE", None)
    else:
        os.environ["FABRIK_SCAFFOLD_OFFLINE"] = previous
