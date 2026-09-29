"""The test session must never touch the box's REAL resume-mesh lock dir.

Measured 2026-09-07 (the relief-wake plan's docs-review): a reader ran the rotate suites and three
LIVE sessions' `<sid>.holdlifted` files appeared in `/tmp/claude-sound-locks-<uid>/` with the tests'
fixed clock (`1800000000` — 2027-01-15) as the lift epoch, and the author's own freshly-armed
self-watch printed a bogus `RESUME: the fleet-quota hold LIFTED at 11:00` line. Cause: every fleet
test that reaches the relief/dwell unlink of `_fleet_active_wall_advisory` now calls
`_wake_held_sessions`, which enumerates `_selfwatch_lock_dir()` — the REAL dir unless
`CLAUDE_SOUND_LOCKDIR` is set — so the plan's own seven tests that set it (two setenv sites in the fleet suite,
three in rotate_v2) were the exception, not the rule.
The class fix is the autouse fixture in `tests/conftest.py` (same shape as its git-env scrub):
every test, existing and future, runs with the variable pinned to a per-test tmp dir. This grader
asserts that pin is in force for an arbitrary test and that the tick's resolver honours it.
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
from pathlib import Path

# read at IMPORT (collection) time: proves the fleet guard is installed before collection
_MODULE_LEVEL_POPEN = subprocess.Popen
_REAL_LOCK_DIR = Path(f"/tmp/claude-sound-locks-{os.getuid()}")


def _load_rotate():
    src = Path(__file__).resolve().parents[1] / "scripts" / "sysadmin" / "claude_rotate.py"
    spec = importlib.util.spec_from_file_location("claude_rotate_isolation_probe", src)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def test_every_test_runs_with_an_isolated_sound_lock_dir(tmp_path_factory):
    pinned = os.environ.get("CLAUDE_SOUND_LOCKDIR")
    assert pinned, "CLAUDE_SOUND_LOCKDIR is unset inside a test — the conftest autouse pin is gone"
    assert Path(pinned).resolve() != _REAL_LOCK_DIR.resolve(), pinned
    assert Path(pinned).resolve().is_relative_to(tmp_path_factory.getbasetemp().resolve()), pinned


def test_the_tick_resolves_the_lock_dir_to_the_pin_not_the_box(tmp_path_factory):
    cr = _load_rotate()
    resolved = cr._selfwatch_lock_dir().resolve()
    assert resolved != _REAL_LOCK_DIR.resolve(), resolved
    assert resolved.is_relative_to(tmp_path_factory.getbasetemp().resolve()), resolved


def test_every_bare_mkdtemp_lands_under_pytest_basetemp(tmp_path_factory):
    """Measured 2026-09-07: four hub tests call `tempfile.mkdtemp()` with no cleanup, and the
    suites run by three sessions and their readers left 4,072 `/tmp/tmp*` dirs (2.2 GB) in one
    day. The class fix is the conftest autouse pin of `tempfile.tempdir` under pytest's basetemp,
    which pytest prunes (it keeps the last three sessions) — no per-test edit, every existing and
    future bare `mkdtemp()`/`NamedTemporaryFile()` covered."""
    import tempfile

    made = Path(tempfile.mkdtemp())
    assert made.resolve().is_relative_to(tmp_path_factory.getbasetemp().resolve()), made
    with tempfile.NamedTemporaryFile() as fh:
        assert Path(fh.name).resolve().is_relative_to(tmp_path_factory.getbasetemp().resolve()), (
            fh.name
        )


def test_kaizen_events_dir_is_pinned_under_basetemp(tmp_path):
    """F349: a test that spawns command_run.py with a hand-built env inherits this pin, so no
    fabricated event reaches ~/.claude/state/events/<live sid>.jsonl."""
    import os
    from pathlib import Path

    d = os.environ.get("KAIZEN_EVENTS_DIR")
    assert d, "KAIZEN_EVENTS_DIR is not pinned"
    assert Path(d).resolve().is_relative_to(tmp_path.resolve().parent), d
    # the invariant, not the fixture (round-17 Opus finding): a hand-built env inherits the pin
    # and the writer honours it at call time — the event lands under tmp, nowhere else
    import subprocess
    import sys

    env = dict(os.environ, COMMAND_RUN_DIR=str(tmp_path / "runs"), CLAUDE_SESSION_ID="pin-probe")
    script = Path(__file__).resolve().parents[1] / "scripts" / "command_run.py"
    # the pin is already inherited (`dict(os.environ)`); what the grader's own RED path must sandbox
    # is the writer's FALLBACK — a child that ignores KAIZEN_EVENTS_DIR falls back to
    # `Path.home()/.claude/state/events`, so HOME goes under tmp too (D-191 review round 19: with a
    # writer mutated to ignore the env, the old explicit line still deposited pin-probe.jsonl in the
    # real dir before the assertion fired). HOME also relocates `.active-account`; the other two
    # seams a hand-built env must force are the transcript and an ambient CLAUDE_AGENT.
    env["HOME"] = str(tmp_path / "home")
    (tmp_path / "home").mkdir(exist_ok=True)
    env["COMMAND_RUN_TRANSCRIPT"] = str(tmp_path / "no-transcript.jsonl")
    env.pop("CLAUDE_AGENT", None)
    cp = subprocess.run(
        [
            sys.executable,
            str(script),
            "start",
            "--command",
            "fabrik-features",
            "--phases",
            "1",
            "--terminal",
            "t",
        ],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert cp.returncode == 0, cp.stderr
    written = list(Path(d).glob("*.jsonl"))
    assert written and any("pin-probe" in w.name for w in written), written


def test_the_suite_never_reads_the_operators_live_run_record(tmp_path) -> None:
    """Round 3 (B3-S1): the graders read the session's own run record, so the conftest pins a
    scratch COMMAND_RUN_DIR and a fixed fake session id for every test — a suite run inside a live
    Claude session must never grade fixtures against the operator's real record."""
    d = os.environ.get("COMMAND_RUN_DIR", "")
    assert d and Path(d).resolve().is_relative_to(tmp_path.resolve().parent), d  # under basetemp
    assert os.environ.get("CLAUDE_SESSION_ID") == "pytest-isolated"
    assert "CLAUDE_CODE_SESSION_ID" not in os.environ
    # the CONSUMER, not the fixture (round 5): command_run resolves its state dir and sid from
    # exactly these — a renamed env read in the script would send in-process calls to the
    # operator's live record while this assertion on the fixture stayed green
    import importlib.util

    # closing seat 6 (2026-09-17): the recorder reads the operator's live `~/.claude/.active-account`
    # on every `start` unless this is pinned — a READ, but the invariant here is that nothing reaches
    # live state, and the hand-built env of the recorder-agreement grader inherits this pin.
    acct = os.environ.get("COMMAND_RUN_ACCOUNT_FILE", "")
    # the same relationship COMMAND_RUN_DIR is held to above — a substring "pytest" only held under
    # the DEFAULT basetemp and went false-red under an explicit --basetemp (Delta 8 seat D)
    assert acct and Path(acct).resolve().is_relative_to(tmp_path.resolve().parent), (
        f"COMMAND_RUN_ACCOUNT_FILE not pinned under the suite tmp: {acct!r}"
    )

    spec = importlib.util.spec_from_file_location(
        "cr_pin_probe", Path(__file__).resolve().parents[1] / "scripts" / "command_run.py"
    )
    cr = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cr)
    assert Path(cr._state_dir()).resolve() == Path(d).resolve()
    assert cr._session_id(None) == "pytest-isolated"


def test_a_tests_own_monkeypatch_undo_cannot_unpin_the_box_state_seams(
    monkeypatch, tmp_path_factory
):
    """The autouse pins ride a PRIVATE `MonkeyPatch`, so a test's own `monkeypatch.undo()` — eleven
    calls across eight hub test files — undoes the test's patches and nothing else. Before, undo
    consumed the shared stack, every seam went unset for the rest of the test, and the fleet suite
    mkdir'd and read the operator's real `~/.claude/state` (Delta 20 seat A, F2)."""
    base = tmp_path_factory.getbasetemp().resolve()
    monkeypatch.setenv("PROBE_ONLY_UNDO", "1")
    monkeypatch.undo()
    assert os.environ.get("PROBE_ONLY_UNDO") is None, "the test's OWN patch is undone"
    for var in (
        "ROTATE_STATE_DIR",
        "FABRIK_OPT_DIR",
        "CLAUDE_FLEET_ROOT",
        "COMMAND_RUN_DIR",
        "KAIZEN_EVENTS_DIR",
        "CLAUDE_SOUND_LOCKDIR",  # the sixth pin, missed by the first cut (Delta 21 seat B)
    ):
        val = os.environ.get(var)
        assert val and Path(val).resolve().is_relative_to(base), (var, val)
    assert os.environ.get("CLAUDE_SESSION_ID") == "pytest-isolated"


def test_every_autouse_pin_keeps_its_docstring():
    """The private-instance refactor inserted `monkeypatch = _private_monkeypatch` ABOVE one
    fixture's docstring, demoting the record of why that pin exists to a dead expression that no
    linter flags (Delta 21 seats A A4 / B)."""
    import ast

    tree = ast.parse((Path(__file__).resolve().parent / "conftest.py").read_text(encoding="utf-8"))
    fixtures = {
        n.name: n
        for n in tree.body
        if isinstance(n, ast.FunctionDef) and n.name.startswith("_isolated_")
    }
    assert len(fixtures) >= 4, sorted(fixtures)
    for name in ("_isolated_kaizen_events_dir", "_isolated_opt_dir", "_isolated_command_run_dir"):
        assert ast.get_docstring(fixtures[name]), name


def test_no_test_can_reach_the_real_opt_or_mail_a_real_repo(tmp_path_factory):
    """A test must not be able to enumerate the real `/opt` — that is how a suite SENT REAL MAIL.

    On 2026-09-16 a rotation grader drove `_cmd_tick()` into the fleet-exhausted branch with
    fixture data; `_mailbox_repos()` walked the real `/opt` and `_drain_mail()` delivered roughly a
    thousand "stop gracefully until 2027-01-22" notices into 49 live project mailboxes. The date
    was the fixture's own `_usage_blob` weekly reset, mailed as fact.

    Graded through the CONSUMER and through a FRESHLY LOADED module, because that is the load order
    that beat the first fix: patching the import-time `OPT_DIR` constant left a module imported
    during the test still bound to the real `/opt`. `_opt_dir()` reads `FABRIK_OPT_DIR` at call
    time, so the pin holds whatever the order.
    """
    pinned = os.environ.get("FABRIK_OPT_DIR")
    assert pinned, "FABRIK_OPT_DIR is unset inside a test — the conftest autouse pin is gone"
    assert Path(pinned).resolve() != Path("/opt").resolve(), pinned
    assert Path(pinned).resolve().is_relative_to(tmp_path_factory.getbasetemp().resolve()), pinned
    cr = _load_rotate()
    assert cr._opt_dir().resolve() == Path(pinned).resolve(), cr._opt_dir()
    # the real /opt holds ~49 mailbox-bearing repos; the pinned one is empty, so a fleet-exhausted
    # tick inside a test has nobody to mail
    assert cr._mailbox_repos() == [], cr._mailbox_repos()
    state = os.environ.get("ROTATE_STATE_DIR")
    assert state, "ROTATE_STATE_DIR is unset inside a test — the same pin is gone"
    assert Path(state).resolve().is_relative_to(tmp_path_factory.getbasetemp().resolve()), state
    assert Path(state).resolve() != (Path.home() / ".claude" / "state").resolve()
    # ⚠️ BOTH sinks, because the branch fires two and the first cut of this guard checked one. The
    # Telegram notifier goes out BEFORE the mail, and `_drain_mail`'s SENDER was hardcoded, so the
    # mailbox pin held only while the pinned dir happened to be empty — and populating it is the
    # natural way to grade `_mailbox_repos()` positively.
    assert (
        cr._sound_script().resolve()
        != (Path.home() / ".claude" / "bin" / "claude-sound.sh").resolve()
    )
    assert not cr._sound_script().is_file(), "a test must not be able to run the real notifier"
    populated = Path(pinned) / "somerepo" / ".claude" / "hooks"
    populated.mkdir(parents=True, exist_ok=True)
    (populated / "mail_notify.py").write_text("", encoding="utf-8")
    assert cr._mailbox_repos() == ["somerepo"], "the pinned opt dir is what gets enumerated"
    sender = Path(str(cr._opt_dir())) / "fabrik" / "scripts" / "mail.py"
    assert not sender.is_file(), "the mail SENDER must resolve inside the pin, not to the real one"
    # ⚠️ THE THIRD SINK, and the only WRITE among them: the tick's flip leg `os.replace`s the
    # `active` symlink under the fleet root, repointing which account every window on this box uses.
    # Nothing pinned it, so containment rested on each fleet test remembering to — and on the day
    # this was found the operator had to switch accounts by hand while off-cadence flip rows sat in
    # the live ledger during this plan's own test runs.
    root = os.environ.get("CLAUDE_FLEET_ROOT")
    assert root, "CLAUDE_FLEET_ROOT is unset inside a test — the tick could repoint the live fleet"
    assert Path(root).resolve() != (Path.home() / ".claude-fleet").resolve(), root
    assert Path(root).resolve().is_relative_to(tmp_path_factory.getbasetemp().resolve()), root
    assert cr._fleet_root().resolve() == Path(root).resolve(), cr._fleet_root()
    assert cr._active_pointer_path().resolve().is_relative_to(Path(root).resolve())
    settings = os.environ.get("QUOTA_POSTURE_SETTINGS")
    assert settings and Path(settings).resolve().is_relative_to(
        tmp_path_factory.getbasetemp().resolve()
    ), settings


# ── No test reaches the live fleet (fabrik-mail 01M39XVS, 2026-09-24) ──────────────────────────
# Suites that patched only some drivers ran real SQL on postgres-main (CREATE ROLE on
# fabrik_analytics) and real watchdog builds over ssh. The guard sits at `subprocess.Popen`, the
# one constructor every ssh/scp/rsync path reaches, whatever name a module imported it under.


def _assert_refused(call, layer: str = "") -> None:
    import pytest

    with pytest.raises(RuntimeError, match=f"test reached the live fleet: .*{layer}"):
        call()


def _assert_shim_refused(cmd, **kw) -> None:
    """A process the Popen guard cannot see still meets the PATH shim: exit 255 and its message."""
    import subprocess

    r = subprocess.run(cmd, capture_output=True, text=True, timeout=30, **kw)
    assert r.returncode == 255, (cmd, r.returncode, r.stderr)
    assert "test reached the live fleet" in r.stderr and "PATH shim" in r.stderr, r.stderr


def test_the_ssh_driver_cannot_reach_the_fleet():
    from fabrik.drivers import ssh as ssh_mod

    _assert_refused(lambda: ssh_mod.ssh("true", timeout=5))
    _assert_refused(lambda: ssh_mod.scp_to_vps("/etc/hostname", "/tmp/x"))


def test_the_postgres_driver_cannot_run_sql_on_postgres_main():
    from fabrik.drivers import postgres

    _assert_refused(lambda: postgres._run_sql("SELECT 1", "postgres-main"))


def test_every_subprocess_shape_of_ssh_scp_rsync_is_refused():
    import subprocess

    guard = "subprocess guard"
    h = "unroutable.invalid"  # a missing guard fails locally and never reaches the real VPS
    shapes = [
        lambda: subprocess.run(["ssh", h, "true"], capture_output=True),
        lambda: subprocess.run(["/usr/bin/scp", "a", f"{h}:b"], capture_output=True),
        lambda: subprocess.check_output(["rsync", "-a", "x", f"{h}:y"]),
        lambda: subprocess.run(f"ssh {h} true", shell=True, capture_output=True),
        lambda: subprocess.run(["bash", "-c", f"cd / && ssh {h} true"], capture_output=True),
        lambda: subprocess.run(["bash", "-lc", f"ssh {h} true"], capture_output=True),
        lambda: subprocess.run(f"true;ssh {h} true", shell=True, capture_output=True),
        lambda: subprocess.run(f"echo $(ssh {h} true)", shell=True, capture_output=True),
        lambda: subprocess.run(f"echo `ssh {h} true`", shell=True, capture_output=True),
        lambda: subprocess.run(f"FOO=1 ssh {h} true", shell=True, capture_output=True),
        lambda: subprocess.run([f"cd / && ssh {h} true"], shell=True, capture_output=True),
        lambda: subprocess.run(["x", h, "true"], executable="/usr/bin/ssh", capture_output=True),
        lambda: subprocess.Popen(["x", h], -1, "/usr/bin/ssh"),  # executable passed positionally
        # a wrapper or keyword runs its arguments; sudo's secure_path would bypass the PATH shim
        lambda: subprocess.run(["sudo", "-n", "-u", "root", "ssh", h], capture_output=True),
        lambda: subprocess.run(["env", "-i", "ssh", h], capture_output=True),
        lambda: subprocess.run(f"exec /usr/bin/ssh {h} true", shell=True, capture_output=True),
        lambda: subprocess.run(f"2>/dev/null ssh {h} true", shell=True, capture_output=True),
        lambda: subprocess.run(f'echo "$(ssh {h} true)"', shell=True, capture_output=True),
        lambda: subprocess.run(f"true\n/usr/bin/ssh {h} true", shell=True, capture_output=True),
        lambda: subprocess.run(["bash", "-o", "pipefail", "-c", f"ssh {h}"], capture_output=True),
        lambda: subprocess.run(
            f"if false; then :; elif /usr/bin/ssh {h}; then :; fi", shell=True, capture_output=True
        ),
        lambda: subprocess.run(["flock", "/tmp/x.lock", "ssh", h], capture_output=True),
    ]
    for shape in shapes:
        _assert_refused(shape, guard)
    # controls: a local command still runs, and "ssh" as an ARGUMENT is not a fleet call
    assert subprocess.run(["true"]).returncode == 0
    assert subprocess.run(["echo", "ssh"], capture_output=True, text=True).stdout.strip() == "ssh"
    assert subprocess.run("echo ssh", shell=True, capture_output=True, text=True).stdout == "ssh\n"
    quoted = subprocess.run('echo "a; ssh x"', shell=True, capture_output=True, text=True)
    assert quoted.stdout == "a; ssh x\n"  # an operator inside quotes is text, not a new command
    # a -c after the script operand belongs to the script, not to bash
    assert subprocess.run(["bash", "/nonexistent.sh", "-c", "ssh"], capture_output=True).returncode


def test_what_the_popen_guard_cannot_see_meets_the_path_shim(tmp_path):
    """A script that runs ssh itself, a name computed at runtime, or os.system never names ssh to
    Popen; the PATH shim still refuses them."""
    h = "unroutable.invalid"
    script = tmp_path / "deploy.sh"  # the shape of vultr's bootstrap-*.sh
    script.write_text(f"#!/bin/sh\nssh {h} true\n", encoding="utf-8")
    script.chmod(0o755)
    _assert_shim_refused([str(script)])
    _assert_shim_refused(["sh", "-c", f'x=ssh; "$x" {h} true'])
    assert os.WEXITSTATUS(os.system(f"ssh {h} true 2>/dev/null")) == 255
    from shutil import which

    assert which("ssh") and "fabrik-fleet-shim-" in which("ssh"), which("ssh")


def test_the_guard_is_in_place_before_collection():
    """Installed by pytest_configure, so module-level and decorator-time calls are covered too."""
    import subprocess

    from tests import conftest

    assert subprocess.Popen is conftest._NoFleetPopen
    assert _MODULE_LEVEL_POPEN is conftest._NoFleetPopen


def test_a_tests_own_subprocess_mock_still_wins(monkeypatch):
    """The guard must not break the suites that already mock the transport correctly."""
    from types import SimpleNamespace

    from fabrik.drivers import ssh as ssh_mod

    monkeypatch.setattr(
        ssh_mod.subprocess,
        "run",
        lambda *a, **k: SimpleNamespace(returncode=0, stdout="mocked\n", stderr=""),
    )
    assert ssh_mod.ssh("true") == "mocked"


def test_no_test_opts_itself_into_the_live_fleet():
    """COBRA (D-253): the cheapest way past the guard is a test that sets the human-only escape.
    `FABRIK_TEST_ALLOW_FLEET` exists for a person deliberately running a live check; no test or
    conftest may name it — under tests/ at any depth, or among the scripts/ tests pytest also runs."""
    here = Path(__file__).resolve().parent
    exempt = {here / "conftest.py", Path(__file__).resolve()}
    candidates = list(here.rglob("*.py")) + [
        p
        for p in (here.parent / "scripts").rglob("*.py")
        if p.name.startswith("test_") or p.name == "conftest.py"
    ]
    hits = [
        str(p)
        for p in candidates
        if p.resolve() not in exempt
        and "FABRIK_TEST_ALLOW_FLEET" in p.read_text(encoding="utf-8", errors="replace")
    ]
    assert hits == [], hits


def test_a_live_fleet_test_is_skipped_unless_a_person_opts_in(monkeypatch):
    """A deliberate live check (`@pytest.mark.live_fleet`) is skipped unless a person opted in —
    before the guard such a test ran against the real VPS every run; after it, it would only fail."""
    import pytest

    from tests import conftest
    from tests.drivers import test_locks

    marks = [m.name for m in test_locks.test_run_locked_concurrency_proof_live_vps.pytestmark]
    assert "live_fleet" in marks, marks

    class _Item:
        def __init__(self, live: bool):
            self.live, self.added = live, []

        def get_closest_marker(self, name):
            return object() if (name == "live_fleet" and self.live) else None

        def add_marker(self, mark):
            self.added.append(mark)

    live, plain = _Item(True), _Item(False)
    monkeypatch.delenv("FABRIK_TEST_ALLOW_FLEET", raising=False)
    conftest.pytest_collection_modifyitems(None, [live, plain])
    assert [m.name for m in live.added] == ["skip"] and plain.added == []
    assert isinstance(live.added[0], pytest.MarkDecorator)

    opted = _Item(True)
    monkeypatch.setenv("FABRIK_TEST_ALLOW_FLEET", "1")
    conftest.pytest_collection_modifyitems(None, [opted])
    assert opted.added == []
