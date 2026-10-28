# AFTER-EDIT: scripts/whoami_agent.py, scripts/command_run.py
"""Graders for the self-naming identity channel (D-267/D-268).

Every one of these exists because a review pass found the opposite behaviour in the spec that
preceded the code: a pid-keyed liveness check that made every binding inert at birth, a collision
check a plain `cd` defeated, a name alphabet three validators disagreed on, and a Cobra
counter-measure that did not exist. They are written to kill those specific mutants.
"""

from __future__ import annotations

import contextlib
import fcntl
import importlib.util
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import pytest

FABRIK = Path(__file__).resolve().parents[1]
WHOAMI = FABRIK / "scripts/whoami_agent.py"
AGENTS_UP = FABRIK / "scripts/sysadmin/agents_up.sh"

# Fresh lowercase UUIDs for the spawner-only binding (agents_up.sh's SID shape).
U1 = "1b1b1b1b-1b1b-4b1b-8b1b-1b1b1b1b1b1b"
U2 = "2c2c2c2c-2c2c-4c2c-8c2c-2c2c2c2c2c2c"
U3 = "3d3d3d3d-3d3d-4d3d-8d3d-3d3d3d3d3d3d"
U4 = "4e4e4e4e-4e4e-4e4e-8e4e-4e4e4e4e4e4e"
U5 = "5f5f5f5f-5f5f-4f5f-8f5f-5f5f5f5f5f5f"


def _mod():
    spec = importlib.util.spec_from_file_location("whoami_agent_under_test", WHOAMI)
    assert spec is not None and spec.loader is not None
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


@pytest.fixture
def store(tmp_path, monkeypatch):
    p = tmp_path / "agent-identity.jsonl"
    monkeypatch.setenv("AGENT_IDENTITY_FILE", str(p))
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "sid-alpha")
    monkeypatch.delenv("CLAUDE_AGENT", raising=False)
    # The real claude process exports CLAUDE_PID into every shell; the predecessor rule reads it, so
    # an ambient value must never decide a grader (W-34cb1ef9 review B-S2).
    monkeypatch.delenv("CLAUDE_PID", raising=False)
    return p


def test_a_live_session_binds_and_the_binding_resolves(store):
    m = _mod()
    assert m.bind("agent-2")[0] == 0
    assert m.resolve_agent_name() == "agent-2"


def test_the_binding_resolves_after_the_writer_process_is_gone(store):
    # THE defect that killed the first design: the writer recorded its OWN pid and exited, so a
    # liveness-gated resolution made every binding inert at birth. Resolution must not consult
    # liveness at all — proven by resolving from a SEPARATE process.
    subprocess.run(
        [sys.executable, str(WHOAMI), "--as", "agent-2"],
        check=True,
        capture_output=True,
        text=True,
        env={**os.environ},
    )
    out = subprocess.run(
        [sys.executable, str(WHOAMI), "--who"],
        check=False,
        capture_output=True,
        text=True,
        env={**os.environ},
    )
    assert out.stdout.strip() == "agent-2"


def test_resolution_never_consults_liveness(store):
    # THE grader for the defect that killed the first design. The one above it does NOT prove this:
    # it resolves a row whose pid is the live `claude` ancestor, so a liveness-gated resolver passes
    # it too (executed — that mutant survived). Only a row whose pid is DEAD separates the two.
    m = _mod()
    store.write_text(
        json.dumps(
            {
                "session_id": "sid-alpha",
                "name": "agent-2",
                "pid": 999_999_999,
                "toplevel": "",
                "at": 9_999_999_999,
                "force": False,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    assert m.resolve_agent_name() == "agent-2", "resolution is gated on liveness — inert at birth"
    store.write_text(
        json.dumps(
            {
                "session_id": "sid-alpha",
                "name": "agent-3",
                "pid": None,
                "toplevel": "",
                "at": 9_999_999_999,
                "force": False,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    assert m.resolve_agent_name() == "agent-3", "a row with no pid must still resolve"


def test_the_recorded_pid_is_the_session_not_the_writer(store):
    # `_session_pid` walks /proc ancestry for comm == claude. Under pytest there is no claude
    # ancestor, so it must return None rather than guess — and it must NEVER be os.getpid().
    m = _mod()
    assert m.bind("agent-2")[0] == 0
    row = json.loads(store.read_text().splitlines()[-1])
    assert row["pid"] != os.getpid(), "recorded the writer's own pid — dead the instant it exits"


def test_a_well_formed_env_var_wins_over_a_binding(store, monkeypatch):
    m = _mod()
    assert m.bind("agent-2")[0] == 0
    monkeypatch.setenv("CLAUDE_AGENT", "infra")
    assert m.resolve_agent_name() == "infra"


def test_a_malformed_env_var_falls_through_to_the_binding(store, monkeypatch):
    # A malformed value already resolved to "" before this channel existed, so falling through
    # changes nothing for anyone actually named.
    m = _mod()
    assert m.bind("agent-2")[0] == 0
    monkeypatch.setenv("CLAUDE_AGENT", "Not A Name!")
    assert m.resolve_agent_name() == "agent-2"


def test_an_unbound_session_resolves_to_empty(store):
    assert _mod().resolve_agent_name() == ""


def test_a_name_outside_the_strict_alphabet_is_refused(store):
    m = _mod()
    for bad in ("Agent-2", "agent_2", "agent.2", "a" * 33, ""):
        code, msg = m.bind(bad)
        assert code == 2, f"{bad!r} was accepted"
        assert "not a valid agent name" in msg


def test_the_alphabet_matches_its_two_sibling_validators(store):
    # ⚠️ Assert the COMPILED regex of the module under test, not raw-text containment: the pattern
    # string also appears in `bind()`'s refusal message, so a text-containment pin passed even
    # after a mutant changed the live `_NAME_RE` (proven by a review seat).
    m = _mod()
    assert m._NAME_RE.pattern == "[a-z0-9-]{1,32}"
    assert m._NAME_RE.fullmatch("agent-2") and not m._NAME_RE.fullmatch("Agent-2")
    # the two siblings this file may not import, pinned by the behaviour they must share
    for rel, const in (
        ("scripts/command_run.py", "_AGENT_NAME_RE"),
        (".claude/hooks/agent_role.py", "_NAME_RE"),
    ):
        spec = importlib.util.spec_from_file_location(f"sib_{const}", FABRIK / rel)
        sib = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(sib)
        rx = getattr(sib, const)
        for good in ("agent-2", "infra", "a"):
            assert rx.match(good) or rx.fullmatch(good), f"{rel} rejects {good!r}"
        for bad in ("Agent-2", "agent_2", "agent.2", "a" * 33):
            assert not rx.fullmatch(bad), f"{rel} accepts {bad!r} — the alphabets drifted"


def test_rebinding_one_session_to_a_different_name_needs_force(store):
    # A Task subagent INHERITS its dispatcher's CLAUDE_CODE_SESSION_ID, so without this a seat
    # could silently re-identify the session that dispatched it.
    m = _mod()
    assert m.bind("agent-2")[0] == 0
    code, msg = m.bind("reviewer")
    assert code == 1 and "already bound" in msg
    assert m.bind("reviewer", force=True)[0] == 0
    assert m.resolve_agent_name() == "reviewer"


def test_a_name_held_by_a_live_session_in_this_repo_is_refused(store, monkeypatch):
    m = _mod()
    store.write_text(
        json.dumps(
            {
                "session_id": "sid-other",
                "name": "agent-2",
                "pid": os.getpid(),
                "toplevel": m._toplevel(),
                "at": 9_999_999_999,
                "force": False,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    code, msg = m.bind("agent-2")
    assert code == 1 and "held by a LIVE session" in msg
    assert m.bind("agent-2", force=True)[0] == 0
    assert m.resolve_agent_name() == "agent-2", "the force override had no effect"


def test_a_dead_holder_does_not_block_the_name(store, monkeypatch):
    m = _mod()
    store.write_text(
        json.dumps(
            {
                "session_id": "sid-other",
                "name": "agent-2",
                "pid": 999_999_999,
                "toplevel": m._toplevel(),
                "at": 9_999_999_999,
                "force": False,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    assert m.bind("agent-2")[0] == 0
    # ⚠️ rc 0 alone is satisfied by a bind() that does nothing. Assert the effect.
    assert m.resolve_agent_name() == "agent-2"


def test_rows_older_than_the_trim_window_are_dropped_on_write(store):
    m = _mod()
    store.write_text(
        json.dumps(
            {
                "session_id": "sid-ancient",
                "name": "old",
                "pid": None,
                "toplevel": "",
                "at": 1,
                "force": False,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    assert m.bind("agent-2")[0] == 0
    ids = {
        json.loads(line)["session_id"] for line in store.read_text().splitlines() if line.strip()
    }
    assert "sid-ancient" not in ids, "nothing else prunes ~/.claude/state — the writer must"


def test_an_uncoercible_timestamp_never_aborts_a_bind(store):
    # `int("abc")` raises ValueError and `int([1])` raises TypeError — both executed. An exception
    # in the trim path would abort a BIND, which is the one operation the operator runs by hand.
    m = _mod()
    for bad in ("abc", None, -1, 1.5, True, [1], {"a": 1}):
        store.write_text(
            json.dumps({"session_id": "sid-old", "name": "old", "at": bad}) + "\n",
            encoding="utf-8",
        )
        code, msg = m.bind("agent-9")
        assert code == 0, f"at={bad!r} aborted the bind: {msg}"


def test_a_fifo_at_the_store_does_not_hang_the_resolver(store, tmp_path, monkeypatch):
    # `read_text` on a FIFO blocks forever with no writer (executed: timed out past 6 s), and this
    # path is reached from a fleet-synced close gate, where a hang STALLS the turn.
    # ⚠️ Run it in a SUBPROCESS with a timeout. In-process, a regression here does not fail this
    # test — it HANGS it, and a hanging grader blocks the suite instead of reporting. Executed:
    # removing the regular-file guard made the in-process form run past a 5-minute limit.
    fifo = tmp_path / "fifo.jsonl"
    os.mkfifo(fifo)
    env = {**os.environ, "AGENT_IDENTITY_FILE": str(fifo), "CLAUDE_CODE_SESSION_ID": "sid-alpha"}
    env.pop("CLAUDE_AGENT", None)
    try:
        out = subprocess.run(
            [sys.executable, str(WHOAMI), "--who"],
            capture_output=True,
            text=True,
            env=env,
            timeout=15,
        )
    except subprocess.TimeoutExpired:
        pytest.fail("the resolver HANGS on a FIFO — read_text blocks forever with no writer")
    assert out.stdout.strip() == ""


def test_a_directory_at_the_store_resolves_empty(store, tmp_path, monkeypatch):
    d = tmp_path / "adir.jsonl"
    d.mkdir()
    monkeypatch.setenv("AGENT_IDENTITY_FILE", str(d))
    assert _mod().resolve_agent_name() == ""


def test_a_corrupt_row_is_skipped_not_fatal(store):
    m = _mod()
    store.write_text('{"session_id": "sid-alpha", "name": "agent-2"}\nNOT JSON\n', encoding="utf-8")
    assert m.resolve_agent_name() == "agent-2"


def test_an_unreadable_store_degrades_to_empty(store, monkeypatch):
    monkeypatch.setenv("AGENT_IDENTITY_FILE", str(store.parent / "nope" / "x.jsonl"))
    assert _mod().resolve_agent_name() == ""


def test_no_argument_can_set_the_session_id(store):
    # The structural half of the Cobra counter-measure: a process cannot name a session it is not
    # part of, because there is no input that sets the id. The ONE exception is the spawner-only
    # `--session-id`, which is refused outside `--spawned` (and `--spawned` demands the held agents
    # lock — the caller-proof graders below); no other spelling exists.
    out = subprocess.run(
        [sys.executable, str(WHOAMI), "--help"],
        check=True,
        capture_output=True,
        text=True,
    )
    for forbidden in (r"--session(?!-id)", r"--sid\b"):
        assert not re.search(forbidden, out.stdout), (
            f"{forbidden} would let one session name another"
        )
    env = {**os.environ}
    for argv in (
        ("--as", "agent-2", "--session-id", U1),
        ("--session-id", U1),
        ("--who", "--session-id", U1),
    ):
        r = subprocess.run(
            [sys.executable, str(WHOAMI), *argv],
            capture_output=True,
            text=True,
            env=env,
            timeout=30,
        )
        assert r.returncode == 2, f"{argv} set a session id outside --spawned"
    assert not store.exists() or U1 not in store.read_text(), (
        "a row was written for the argument id"
    )


def test_command_run_resolves_the_binding_and_the_env_still_wins(store, monkeypatch):
    spec = importlib.util.spec_from_file_location(
        "cr_under_test", FABRIK / "scripts/command_run.py"
    )
    cr = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cr)
    assert _mod().bind("agent-2")[0] == 0
    assert cr._agent_name() == "agent-2"
    monkeypatch.setenv("CLAUDE_AGENT", "infra")
    assert cr._agent_name() == "infra"


def test_conftest_pins_the_store_so_graders_never_touch_the_live_one(tmp_path):
    # ⚠️ Assert the MECHANISM, not the token. A substring check passed with the `setenv` call
    # commented out (proven by a review seat) — the word survives in the comment.
    assert os.environ.get("AGENT_IDENTITY_FILE"), "the autouse pin is not in effect"
    live = Path.home() / ".claude" / "state" / "agent-identity.jsonl"
    assert Path(os.environ["AGENT_IDENTITY_FILE"]) != live, "graders are pointed at the real store"
    text = (FABRIK / "tests/conftest.py").read_text(encoding="utf-8")
    active = [
        ln
        for ln in text.splitlines()
        if "AGENT_IDENTITY_FILE" in ln and "setenv" in ln and not ln.strip().startswith("#")
    ]
    assert active, "no ACTIVE monkeypatch.setenv for AGENT_IDENTITY_FILE"


def test_command_run_does_not_leak_sys_path_entries(store):
    # `_agent_name()` runs on every start/step/round/dispatch/done. An unguarded
    # `sys.path.insert` grew sys.path by 1000 over 1000 calls (executed) — every entry slows each
    # later import and widens what a same-named module could shadow.
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "cr_syspath_probe", FABRIK / "scripts/command_run.py"
    )
    cr = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cr)
    before = len(sys.path)
    for _ in range(50):
        cr._agent_name()
    assert len(sys.path) - before <= 1, "sys.path leaked one entry per call"


def test_the_trim_cannot_destroy_a_concurrent_binding(store, monkeypatch):
    # The 30-day trim REWRITES the store from a snapshot, so without serialization a row a sibling
    # appended between the read and the write is destroyed — inevitable once the store ages.
    # ⚠️ The sibling must be a REAL separate process. Two earlier cuts of this grader were wrong:
    # a 24-way subprocess race passed against an unlocked build (startup serialized them by luck),
    # and simulating the sibling's append INSIDE the locked section bypassed the lock entirely and
    # failed against the FIXED build. Here the parent holds its window open deterministically and
    # the sibling contends for real: with the lock it waits its turn, without it lands mid-window.
    m = _mod()
    store.write_text(
        json.dumps({"session_id": "sid-ancient", "name": "old", "at": 1}) + "\n", encoding="utf-8"
    )
    env = {**os.environ, "AGENT_IDENTITY_FILE": str(store), "CLAUDE_CODE_SESSION_ID": "sid-B"}
    env.pop("CLAUDE_AGENT", None)
    proc: list = []
    real_pid = m._session_pid

    def widen_the_window():
        # called inside the locked read-modify-write, after the snapshot is taken
        if not proc:
            proc.append(
                subprocess.Popen(
                    [sys.executable, str(WHOAMI), "--as", "agent-b"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    env=env,
                )
            )
            time.sleep(2.0)
        return real_pid()

    monkeypatch.setattr(m, "_session_pid", widen_the_window)
    try:
        assert m.bind("agent-a")[0] == 0
    finally:
        # the sibling must be reaped even when the assertion above fails, or a failing run leaks it
        if proc:
            proc[0].wait(timeout=60)
    sids = {
        json.loads(line)["session_id"] for line in store.read_text().splitlines() if line.strip()
    }
    assert "sid-B" in sids, "the trim rewrite destroyed a concurrent sibling's binding"
    assert "sid-alpha" in sids, "our own binding must be there too"
    assert "sid-ancient" not in sids, "the trim must still happen"


def test_the_store_is_written_private(store):
    m = _mod()
    assert m.bind("agent-2")[0] == 0
    assert oct(store.stat().st_mode)[-3:] == "600", "a store of session ids must not be readable"


def test_the_cli_exit_codes_are_the_contract(store):
    # `--who` unbound -> 1; bound -> 0. A refused bind -> non-zero. Nothing graded these.
    env = {**os.environ, "AGENT_IDENTITY_FILE": str(store), "CLAUDE_CODE_SESSION_ID": "sid-alpha"}
    env.pop("CLAUDE_AGENT", None)
    run = lambda *a: subprocess.run(  # noqa: E731
        [sys.executable, str(WHOAMI), *a], capture_output=True, text=True, env=env, timeout=30
    )
    assert run("--who").returncode == 1, "--who on an unbound session must be non-zero"
    assert run("--as", "agent-2").returncode == 0
    assert run("--who").returncode == 0
    assert run("--as", "Bad_Name").returncode == 2, "an invalid name must be non-zero"
    assert run("--as", "other").returncode == 1, "a refused re-bind must be non-zero"
    assert "usage" in run("--help").stdout.lower(), "a no-op arg parser would pass the sid test"


def test_a_name_with_a_newline_is_refused(store):
    # `$` matches BEFORE a trailing newline, so `re.match` accepted "infra\n" — and a newline in
    # an `Agent-Name:` trailer makes git parse the WHOLE block as nothing, reproducing the very
    # failure this feature exists to fix. Shell `$(...)` strips trailing newlines, so this must go
    # through argv directly or it tests nothing.
    env = {**os.environ, "AGENT_IDENTITY_FILE": str(store), "CLAUDE_CODE_SESSION_ID": "sid-nl"}
    env.pop("CLAUDE_AGENT", None)
    for bad in ("infra\n", "\ninfra", "infra\n\n", "in fra", "infra\t"):
        r = subprocess.run(
            [sys.executable, str(WHOAMI), "--as", bad],
            capture_output=True,
            text=True,
            env=env,
            timeout=30,
        )
        assert r.returncode == 2, f"{bad!r} was accepted"
    assert (
        subprocess.run(
            [sys.executable, str(WHOAMI), "--as", "infra"],
            capture_output=True,
            text=True,
            env=env,
            timeout=30,
        ).returncode
        == 0
    )


def test_the_collision_scope_is_the_common_dir_not_the_toplevel(store):
    # A worktree and its main checkout are ONE repo with two toplevels, so a toplevel scope lets
    # two sessions committing into one history hold one name. This repo has 18 worktrees.
    m = _mod()
    scope = m._toplevel()
    assert scope.endswith(".git"), f"scope {scope!r} is a toplevel, not a common dir"


def test_an_unknown_scope_is_its_own_scope_not_a_wildcard(store):
    # Before: a holder scoped "" was invisible to any checker inside a repo, and a checker scoped
    # "" matched every holder everywhere. `_toplevel()` returns "" on a git-less dir AND on its
    # timeout, so a transient git failure silently downgraded a binding into the unprotected half.
    m = _mod()
    store.write_text(
        json.dumps(
            {
                "session_id": "sid-other",
                "name": "agent-2",
                "pid": os.getpid(),
                "pid_start": m._pid_start(os.getpid()),
                "toplevel": "",
                "at": 9_999_999_999,
                "force": False,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    code, _ = m.bind("agent-2")  # our scope is this repo's common dir, the holder's is ""
    assert code == 0, "a holder in a DIFFERENT scope must not block"
    assert m.resolve_agent_name() == "agent-2"  # rc 0 alone passes a bind() that does nothing


def test_a_recycled_pid_does_not_cause_a_false_refusal(store):
    # Rows live 30 days and pid_max is 4194304, so a stale row's pid is reusable. Without the
    # start-time a row carrying `pid: 1` refused a legitimate bind with "held by a LIVE session".
    m = _mod()
    store.write_text(
        json.dumps(
            {
                "session_id": "sid-other",
                "name": "agent-2",
                "pid": 1,
                "pid_start": 123456789,
                "toplevel": m._toplevel(),
                "at": 9_999_999_999,
                "force": False,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    code, _ = m.bind("agent-2")
    assert code == 0, "a recycled pid impersonated the original holder"
    assert m.resolve_agent_name() == "agent-2"


def test_an_empty_name_and_a_mixed_mode_are_refused_not_silent(store):
    # `--as ""` is the live shape of an unset shell variable. It used to fall into the --who branch
    # and print the OLD name at rc 0 — a silent no-op that reads as success.
    env = {**os.environ, "AGENT_IDENTITY_FILE": str(store), "CLAUDE_CODE_SESSION_ID": "sid-alpha"}
    env.pop("CLAUDE_AGENT", None)
    run = lambda *a: subprocess.run(  # noqa: E731
        [sys.executable, str(WHOAMI), *a], capture_output=True, text=True, env=env, timeout=30
    )
    assert run("--as", "").returncode == 2, "--as '' must refuse, not no-op"
    assert run("--who", "--as", "fleet").returncode == 2, "--who with --as must refuse"


def test_a_binding_with_no_session_pid_says_it_is_unprotected(store, monkeypatch):
    # A row with no pid reserves nothing. That is a GAP, and the success message must not imply a
    # protection it does not have.
    m = _mod()
    monkeypatch.setattr(m, "_session_pid", lambda: None)
    code, msg = m.bind("agent-2")
    assert code == 0
    assert "does NOT reserve" in msg


def test_an_unavailable_lock_is_loud_and_auditable(store, tmp_path):
    # A SILENT fail-soft re-opens the very race the lock exists to close: a lock path that is a
    # DIRECTORY double-bound 7 of 10 trials at rc 0 with a success message. The module already
    # warns when the session pid is unknown; a lost lock is strictly worse.
    (tmp_path / (store.name + ".lock")).mkdir()
    m = _mod()
    code, msg = m.bind("agent-2")
    assert code == 0
    assert "NOT serialized" in msg, "a degraded bind must say so"
    row = json.loads(store.read_text().splitlines()[-1])
    assert row.get("unlocked") is True, "the row must record that it was written unserialized"


def test_a_held_lock_does_not_block_forever(store, tmp_path):
    # `LOCK_EX` alone is BLOCKING, so the fail-soft covered only error cases and never contention
    # — executed, a bind blocked past 12 s behind a stopped holder, unbounded.
    import fcntl

    lock = tmp_path / (store.name + ".lock")
    fd = os.open(str(lock), os.O_CREAT | os.O_RDWR, 0o600)
    fcntl.flock(fd, fcntl.LOCK_EX)
    try:
        t0 = time.monotonic()
        m = _mod()
        code, msg = m.bind("agent-2")
        elapsed = time.monotonic() - t0
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)
    assert code == 0
    assert elapsed < 20, f"bind blocked {elapsed:.1f}s behind a held lock"
    assert "NOT serialized" in msg


def test_the_lock_path_is_resolved_not_spelled(store):
    # Two spellings of one store must produce ONE lock, or there is no mutual exclusion at all.
    m = _mod()
    assert m.bind("agent-2")[0] == 0
    import inspect

    src = inspect.getsource(m._locked)
    assert ".resolve()" in src, "the lock name is derived from an unresolved path"


def test_a_live_holder_with_a_correct_start_time_actually_blocks(store):
    # ⚠️ THE grader for the whole point of the feature. Every other pid test is a NEGATIVE case
    # (a recycled pid must not block) or uses the legacy `pid_start is None` fallback — so a
    # mutant making `_pid_start` return a random int silently disabled the entire anti-double-bind
    # protection and survived every grader. This one fails the moment `_pid_start` stops agreeing
    # with itself for a live process.
    m = _mod()
    me = os.getpid()
    start = m._pid_start(me)
    assert isinstance(start, int) and start > 0, "_pid_start must read a real start time"
    store.write_text(
        json.dumps(
            {
                "session_id": "sid-other",
                "name": "agent-2",
                "pid": me,
                "pid_start": start,
                "toplevel": m._toplevel(),
                "at": 9_999_999_999,
                "force": False,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    code, msg = m.bind("agent-2")
    assert code == 1 and "held by a LIVE session" in msg, "a live holder failed to block"
    # and it is stable: two reads of the same live process must agree, or nothing can ever match
    assert m._pid_start(me) == start, "_pid_start is not stable for one live process"


def test_the_rewrite_path_is_also_private_and_atomic(store):
    # `test_the_store_is_written_private` only exercises the fresh-store APPEND path; the trim
    # REWRITE had no mode grader, and a 0644 mutant on it survived.
    m = _mod()
    store.write_text(
        json.dumps({"session_id": "sid-ancient", "name": "old", "at": 1}) + "\n", encoding="utf-8"
    )
    assert m.bind("agent-2")[0] == 0  # forces the trim/rewrite branch
    assert oct(store.stat().st_mode)[-3:] == "600", "the rewrite path loosened the mode"
    import inspect

    src = inspect.getsource(m._write_rows)
    assert "os.replace" in src, "the rewrite must be atomic, not an in-place truncate"


def test_the_append_path_uses_o_append(store):
    # The docstring claims 30 concurrent writers x 400 rows with 0 torn rows; nothing graded the
    # flag that makes it true, and a seek-to-end mutant survived every test.
    import inspect

    # ⚠️ Search the BODY, not the whole source: "O_APPEND" also appears in the docstring, so the
    # obvious `in inspect.getsource(...)` passed a mutant that removed the flag from the os.open
    # call (executed) — the same vacuity class as a raw-text regex pin.
    src = inspect.getsource(_mod()._append_row)
    body = src.split('"""')[-1]
    assert "O_APPEND" in body, "concurrent appends are only atomic under O_APPEND"


def _holder(m, pid, start, sid="sid-other", name="agent-2"):
    return json.dumps(
        {
            "session_id": sid,
            "name": name,
            "pid": pid,
            "pid_start": start,
            "toplevel": m._toplevel(),
            "at": 9_999_999_999,
            "force": False,
        }
    )


def _own_process(m, monkeypatch, pid=None):
    """Pretend this test process is the window's claude process (its pid is live and readable)."""
    pid = os.getpid() if pid is None else pid
    monkeypatch.setattr(m, "_session_pid", lambda: pid)
    monkeypatch.delenv("CLAUDE_PID", raising=False)
    return pid, m._pid_start(pid)


def test_a_clear_successor_binds_its_own_window_name_without_force(store, monkeypatch):
    """W-34cb1ef9: /clear mints a new session id in the SAME claude process; its own earlier row
    is a predecessor, not a holder, so the bind needs no --force and says who it succeeded."""
    m = _mod()
    pid, start = _own_process(m, monkeypatch)
    store.write_text(
        _holder(m, pid, start, sid="sid-old")
        + "\n"
        + _holder(m, pid, start, sid="sid-older")
        + "\n",
        encoding="utf-8",
    )
    code, msg = m.bind("agent-2")
    assert code == 0, msg
    assert m.resolve_agent_name() == "agent-2"
    last = m._rows(store)[-1]
    assert last["predecessor"] == "sid-older" and "sid-older" in msg  # the most recent matching row
    assert last["force"] is False


def test_a_forced_rotation_still_records_its_predecessor(store, monkeypatch):
    m = _mod()
    pid, start = _own_process(m, monkeypatch)
    store.write_text(_holder(m, pid, start, sid="sid-old") + "\n", encoding="utf-8")
    assert m.bind("agent-2", force=True)[0] == 0
    last = m._rows(store)[-1]
    assert last["predecessor"] == "sid-old" and last["force"] is True


def test_a_predecessor_never_excuses_a_live_foreign_holder(store, monkeypatch):
    m = _mod()
    pid, start = _own_process(m, monkeypatch)
    other = os.getppid()
    store.write_text(
        _holder(m, pid, start, sid="sid-old")
        + "\n"
        + _holder(m, other, m._pid_start(other), sid="sid-foreign")
        + "\n",
        encoding="utf-8",
    )
    code, msg = m.bind("agent-2")
    assert code == 1 and "held by a LIVE session" in msg


def test_a_live_holder_in_another_process_still_refuses(store, monkeypatch):
    m = _mod()
    _own_process(m, monkeypatch, pid=os.getppid())
    me = os.getpid()
    store.write_text(_holder(m, me, m._pid_start(me)) + "\n", encoding="utf-8")
    code, msg = m.bind("agent-2")
    assert code == 1 and "held by a LIVE session" in msg


def test_an_unknown_start_time_never_makes_a_predecessor(store, monkeypatch):
    """A legacy row (pid_start None) on our own pid, and our own start unreadable: (pid, None) ==
    (pid, None) must not read as 'the same window'."""
    m = _mod()
    pid, _start = _own_process(m, monkeypatch)
    monkeypatch.setattr(m, "_pid_start", lambda _pid: None)
    store.write_text(_holder(m, pid, None) + "\n", encoding="utf-8")
    code, msg = m.bind("agent-2")
    assert code == 1 and "held by a LIVE session" in msg


def test_a_walk_that_disagrees_with_claude_pid_claims_no_predecessor(store, monkeypatch):
    """A nested claude the /proc walk passes through reaches the OUTER window's pid; CLAUDE_PID,
    exported by the real claude process, names the mismatch and the bind stays refused."""
    m = _mod()
    pid, start = _own_process(m, monkeypatch)
    monkeypatch.setenv("CLAUDE_PID", str(os.getppid()))
    store.write_text(_holder(m, pid, start, sid="sid-old") + "\n", encoding="utf-8")
    code, msg = m.bind("agent-2")
    assert code == 1 and "held by a LIVE session" in msg


def test_a_hand_edited_row_with_digit_strings_is_still_this_windows_predecessor(store, monkeypatch):
    m = _mod()
    pid, start = _own_process(m, monkeypatch)
    store.write_text(_holder(m, str(pid), str(start), sid="sid-old") + "\n", encoding="utf-8")
    code, msg = m.bind("agent-2")
    assert code == 0, msg
    assert m._rows(store)[-1]["predecessor"] == "sid-old"


def test_a_live_foreign_holder_with_a_string_start_time_still_refuses(store, monkeypatch):
    """A start time stored as a digit string must not read as a DEAD holder: before the review this
    compared int to str, so any session could take a live name with no refusal."""
    m = _mod()
    _own_process(m, monkeypatch, pid=os.getppid())
    me = os.getpid()
    store.write_text(_holder(m, me, str(m._pid_start(me))) + "\n", encoding="utf-8")
    code, msg = m.bind("agent-2")
    assert code == 1 and "held by a LIVE session" in msg


def test_a_boolean_pid_is_never_a_process(store, monkeypatch):
    """JSON `true` equals 1 in Python; a corrupted row must not match a claude running as pid 1."""
    m = _mod()
    monkeypatch.setattr(m, "_session_pid", lambda: 1)
    monkeypatch.setattr(m, "_pid_start", lambda _pid: 7)
    store.write_text(_holder(m, True, 7, sid="sid-old") + "\n", encoding="utf-8")
    code, msg = m.bind("agent-2")
    assert code == 0, msg
    assert "predecessor" not in m._rows(store)[-1]


def test_trim_keeps_each_names_newest_binding(store):
    # W-89474fc1: a repo with no registry gets its launcher's builders from these bindings, and a quiet repo binds
    # nothing for 30 days — so each (repo, name)'s NEWEST row survives the trim, while its older rows, a row of no
    # repo, and the row this bind supersedes still go.
    m = _mod()
    rows = [
        {"session_id": "sid-b1-old", "name": "b1", "toplevel": "/opt/shop/.git", "at": 1},
        {"session_id": "sid-b1-new", "name": "b1", "toplevel": "/opt/shop/.git", "at": 2},
        {"session_id": "sid-b2", "name": "b2", "toplevel": "/opt/shop/.git", "at": 3},
        {"session_id": "sid-norepo", "name": "b3", "toplevel": "", "at": 4},
        {"session_id": "sid-other", "name": "b1", "toplevel": "/opt/else/.git", "at": 5},
    ]
    store.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    assert m.bind("agent-2")[0] == 0
    ids = {
        json.loads(line)["session_id"] for line in store.read_text().splitlines() if line.strip()
    }
    assert {"sid-b1-new", "sid-b2", "sid-other"} <= ids, ids
    assert "sid-b1-old" not in ids and "sid-norepo" not in ids, ids


def test_the_trim_never_resurrects_a_renamed_session_or_aborts_on_a_bad_row(store, monkeypatch):
    # Review round 1: (a) a session force-renamed alice -> bob keeps its OLD alice row only while that row is still
    # the session's last, so the trim cannot hand the session back to alice; (b) the pair this bind supersedes goes;
    # (c) a hand-edited row with a list for a name, or an `at` of Infinity, never aborts the bind. The bind's own
    # scope is pinned, so (b) is exercised from any cwd — outside a repo `_toplevel()` is "" and (b) would pass vacuously.
    m = _mod()
    top = "/opt/mine/.git"
    monkeypatch.setattr(m, "_toplevel", lambda: top)
    rows = [
        {"session_id": "s1", "name": "alice", "toplevel": "/opt/shop/.git", "at": 1},
        {"session_id": "s1", "name": "bob", "toplevel": "/opt/shop/.git", "at": 2, "force": True},
        {"session_id": "s2", "name": "bob", "toplevel": "/opt/shop/.git", "at": 3},
        {"session_id": "s-mine-old", "name": "agent-2", "toplevel": top, "at": 4},
        {"session_id": "s-list", "name": ["x"], "toplevel": "/opt/shop/.git", "at": 5},
    ]
    store.write_text(
        "".join(json.dumps(r) + "\n" for r in rows)
        + '{"session_id": "s-inf", "name": "z", "at": Infinity}\n',
        encoding="utf-8",
    )
    code, msg = m.bind("agent-2")
    assert code == 0, msg
    kept = [json.loads(line) for line in store.read_text().splitlines() if line.strip()]
    owner = {r["session_id"]: r["name"] for r in kept}
    assert owner.get("s1") != "alice", kept  # never resurrected: s1's last row named bob
    assert "s2" in owner, kept  # bob's newest binding survives
    assert "s-mine-old" not in owner, kept  # superseded by this bind's own row


# --- W-b9ad80ae T01: the spawner-only binding (`--spawned`), proven by the held agents lock --------------------------

_GIT_LOCATION = ("GIT_DIR", "GIT_COMMON_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE")


def _clean_env(**extra: str) -> dict[str, str]:
    """The caller's environment without git's location variables (a hook-run pytest would inherit them)."""
    env = {k: v for k, v in os.environ.items() if k not in _GIT_LOCATION}
    env.update(extra)
    return env


def _spawn_repo(tmp: Path, name: str = "shop") -> Path:
    repo = (tmp / name).resolve()
    repo.mkdir(parents=True)
    subprocess.run(
        ["git", "init", "-q", str(repo)], check=True, capture_output=True, env=_clean_env()
    )
    return repo


def _lock_of(repo: Path) -> Path:
    return repo / ".git" / "fabrik-agents.lock"


@contextlib.contextmanager
def _held(path: Path, flags: int = os.O_RDWR):
    """Hold `path`'s flock the way `agents_spawn.py` will: open, LOCK_EX, keep the descriptor."""
    fd = os.open(str(path), flags | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield fd
    finally:
        os.close(fd)


@contextlib.contextmanager
def _other_process_holds(path: Path):
    """A CHILD process holds `path`'s flock until the block ends."""
    code = (
        "import fcntl, os, sys\n"
        "fd = os.open(sys.argv[1], os.O_RDWR | os.O_CREAT, 0o600)\n"
        "fcntl.flock(fd, fcntl.LOCK_EX)\n"
        "print('ready', flush=True)\n"
        "sys.stdin.read()\n"
    )
    child = subprocess.Popen(
        [sys.executable, "-c", code, str(path)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
    )
    try:
        assert child.stdout is not None and child.stdout.readline().strip() == "ready"
        yield child
    finally:
        assert child.stdin is not None
        child.stdin.close()
        child.wait(timeout=10)


def _spawned(
    name: str, sid: str, repo: object, fd: object, *, pass_fds: tuple[int, ...] = (), env=None
) -> subprocess.CompletedProcess[str]:
    argv = [sys.executable, str(WHOAMI), "--spawned", name, "--session-id", sid]
    argv += ["--repo", str(repo), "--lock-fd", str(fd)]
    return subprocess.run(
        argv,
        capture_output=True,
        text=True,
        env=_clean_env() if env is None else env,
        pass_fds=pass_fds,
        timeout=30,
    )


def _store_rows(store: Path) -> list[dict]:
    if not store.exists():
        return []
    return [json.loads(ln) for ln in store.read_text(encoding="utf-8").splitlines() if ln.strip()]


def test_a_spawner_holding_the_agents_lock_binds_a_fresh_id_with_no_pid(store, tmp_path):
    """The row names the NEW session, carries `spawned: true` and a null pid — never the caller's process."""
    repo = _spawn_repo(tmp_path)
    with _held(_lock_of(repo)) as fd:
        r = _spawned("b-1", U1, repo, fd, pass_fds=(fd,))
    assert r.returncode == 0, r.stderr
    last = _store_rows(store)[-1]
    assert {
        k: last.get(k) for k in ("session_id", "name", "toplevel", "spawned", "pid", "pid_start")
    } == {
        "session_id": U1,
        "name": "b-1",
        "toplevel": str(repo / ".git"),
        "spawned": True,
        "pid": None,
        "pid_start": None,
    }, last
    assert "predecessor" not in last and last["force"] is False, last


def test_the_lock_proof_accepts_every_legitimate_holder(store, tmp_path):
    """Five legitimate callers of the guard's class pass it: the main checkout, a subdirectory, a trailing slash, a
    LINKED worktree (one repo, one lock, one scope), and a read-only descriptor — each binds at rc 0."""
    repo = _spawn_repo(tmp_path)
    git = ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t"]
    subprocess.run([*git, "commit", "-q", "--allow-empty", "-m", "x"], check=True, env=_clean_env())
    wt = repo / ".claude" / "worktrees" / "b-4"
    subprocess.run(
        [*git, "worktree", "add", "-q", "-b", "w4", str(wt)], check=True, env=_clean_env()
    )
    (repo / "sub" / "deep").mkdir(parents=True)
    cases = [
        ("b-1", U1, str(repo), os.O_RDWR),
        ("b-2", U2, str(repo / "sub" / "deep"), os.O_RDWR),
        ("b-3", U3, f"{repo}/", os.O_RDWR),
        ("b-4", U4, str(wt), os.O_RDWR),
        ("b-5", U5, str(repo), os.O_RDONLY),
    ]
    for name, sid, where, flags in cases:
        with _held(_lock_of(repo), flags) as fd:
            r = _spawned(name, sid, where, fd, pass_fds=(fd,))
        assert r.returncode == 0, (name, where, r.stderr)
        assert _store_rows(store)[-1]["toplevel"] == str(repo / ".git"), (name, where)


def test_no_descriptor_another_file_or_an_unheld_lock_refuses(store, tmp_path):
    """Each failed condition of the caller proof exits 2, names that condition, and writes no row."""
    repo = _spawn_repo(tmp_path)
    other = tmp_path / "other.lock"
    # (a) no open descriptor at that number
    r = _spawned("b-1", U1, repo, 97)
    assert r.returncode == 2 and "not an open descriptor" in r.stderr, r.stderr
    # (a) a descriptor, locked, on another file
    with _held(other) as fd:
        r = _spawned("b-1", U1, repo, fd, pass_fds=(fd,))
    assert r.returncode == 2 and "not the agents lock" in r.stderr, r.stderr
    # (b) the right lock path, and nobody holds it
    fd = os.open(str(_lock_of(repo)), os.O_RDWR | os.O_CREAT, 0o600)
    try:
        r = _spawned("b-1", U1, repo, fd, pass_fds=(fd,))
    finally:
        os.close(fd)
    assert r.returncode == 2 and "nobody holds" in r.stderr, r.stderr
    assert _store_rows(store) == []


def test_an_unlocked_descriptor_on_the_lock_refuses_whoever_holds_it(store, tmp_path):
    """A descriptor OPEN on the lock but not locked is no proof: while another process holds the lock the passed copy
    cannot take it (c), and while nobody holds it the fresh probe succeeds (b) — and is released, never kept."""
    repo = _spawn_repo(tmp_path)
    lock = _lock_of(repo)
    with _other_process_holds(lock):
        fd = os.open(str(lock), os.O_RDWR)
        try:
            r = _spawned("b-1", U1, repo, fd, pass_fds=(fd,))
        finally:
            os.close(fd)
    assert r.returncode == 2 and "does not hold it" in r.stderr, r.stderr
    fd = os.open(str(lock), os.O_RDWR)
    try:
        r = _spawned("b-1", U1, repo, fd, pass_fds=(fd,))
    finally:
        os.close(fd)
    assert r.returncode == 2 and "nobody holds" in r.stderr, r.stderr
    assert _store_rows(store) == []
    probe = os.open(str(lock), os.O_RDWR)
    try:
        fcntl.flock(
            probe, fcntl.LOCK_EX | fcntl.LOCK_NB
        )  # raises if the refusal left the lock held
    finally:
        os.close(probe)


def test_a_known_or_malformed_session_id_is_refused(store, tmp_path):
    """A session id any row already carries, and every id that is not a lowercase UUID, exits 2 naming it."""
    repo = _spawn_repo(tmp_path)
    store.write_text(
        json.dumps(
            {"session_id": U1, "name": "elsewhere", "toplevel": "/opt/x/.git", "at": 9_999_999_999}
        )
        + "\n",
        encoding="utf-8",
    )
    before = store.read_text()
    bad = [U1, U2.upper(), U2.replace("-", ""), "sid-alpha", U2 + "0", " " + U2]
    with _held(_lock_of(repo)) as fd:
        for sid in bad:
            r = _spawned("b-1", sid, repo, fd, pass_fds=(fd,))
            assert r.returncode == 2, (sid, r.stderr)
            assert repr(sid) in r.stderr or sid in r.stderr, (sid, r.stderr)
    assert store.read_text() == before


def test_a_live_holder_refuses_with_1_and_a_crash_exits_3(store, tmp_path, monkeypatch):
    """The holder scan stays: a LIVE pid-bearing row of b-1 in this scope refuses at rc 1. An exception inside the
    spawned bind exits 3, never the 1 a collision returns."""
    m = _mod()
    repo = _spawn_repo(tmp_path)
    scope = str(repo / ".git")
    store.write_text(
        json.dumps(
            {
                "session_id": "sid-live",
                "name": "b-1",
                "pid": os.getpid(),
                "pid_start": m._pid_start(os.getpid()),
                "toplevel": scope,
                "at": 9_999_999_999,
                "force": False,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    with _held(_lock_of(repo)) as fd:
        r = _spawned("b-1", U1, repo, fd, pass_fds=(fd,))
        assert r.returncode == 1 and "LIVE session" in r.stderr, r.stderr
        assert U1 not in store.read_text()
        # the live holder refuses only its own name: b-2 binds beside it
        assert _spawned("b-2", U2, repo, fd, pass_fds=(fd,)).returncode == 0

        def boom(_path):
            raise RuntimeError("injected")

        monkeypatch.setattr(m, "_rows", boom)
        argv = ["whoami_agent.py", "--spawned", "b-3", "--session-id", U3, "--repo", str(repo)]
        assert m.main([*argv, "--lock-fd", str(fd)]) == 3
    # --as keeps its old shape: the exception reaches the `__main__` catch-all (exit 1), never a 3
    with pytest.raises(RuntimeError):
        m.main(["whoami_agent.py", "--as", "agent-2"])


def test_an_inherited_git_dir_never_redirects_the_spawned_scope(store, tmp_path):
    """`GIT_DIR` naming another repo in the caller's environment: the row's scope is still `--repo`'s common dir."""
    repo = _spawn_repo(tmp_path)
    other = _spawn_repo(tmp_path, "other")
    env = _clean_env(GIT_DIR=str(other / ".git"), GIT_WORK_TREE=str(other))
    with _held(_lock_of(repo)) as fd:
        r = _spawned("b-1", U1, repo, fd, pass_fds=(fd,), env=env)
    assert r.returncode == 0, r.stderr
    assert _store_rows(store)[-1]["toplevel"] == str(repo / ".git")


def test_the_spawner_flags_are_scoped_to_spawned(store, tmp_path):
    """`--spawned` beside `--as`/`--who`, a spawner flag without `--spawned`, or `--spawned` missing one: usage, rc 2."""
    repo = _spawn_repo(tmp_path)
    full = ["--spawned", "b-1", "--session-id", U1, "--repo", str(repo), "--lock-fd", "3"]
    cases = [
        [*full, "--as", "agent-2"],
        [*full, "--who"],
        ["--session-id", U1],
        ["--repo", str(repo)],
        ["--lock-fd", "3"],
        ["--as", "agent-2", "--repo", str(repo)],
        ["--spawned", "b-1", "--session-id", U1, "--repo", str(repo)],
        ["--spawned", "b-1", "--repo", str(repo), "--lock-fd", "3"],
        ["--spawned", "b-1", "--session-id", U1, "--lock-fd", "3"],
        [*full, "--force"],
    ]
    for argv in cases:
        r = subprocess.run(
            [sys.executable, str(WHOAMI), *argv],
            capture_output=True,
            text=True,
            env=_clean_env(),
            timeout=30,
        )
        assert r.returncode == 2 and "usage" in r.stderr.lower(), (argv, r.stderr)
    assert _store_rows(store) == []


def test_the_launcher_reads_the_spawned_row_as_a_builder(store, tmp_path):
    """Cross-ticket (IF1 → T02): the spawned row, written through the real CLI, is what a registry-less repo's
    `agents_up.sh --print` resolves into a pane for b-1 — against TODAY's launcher, untouched."""
    repo = _spawn_repo(tmp_path)
    wt = repo / ".claude" / "worktrees" / "b-1"
    wt.mkdir(parents=True)
    (wt / ".git").write_text(f"gitdir: {repo}/.git/worktrees/b-1\n", encoding="utf-8")
    with _held(_lock_of(repo)) as fd:
        assert _spawned("b-1", U1, repo, fd, pass_fds=(fd,)).returncode == 0
    home = tmp_path / "home"
    (home / "proc").mkdir(parents=True)
    (home / "proc" / "meminfo").write_text(
        "MemTotal: 28311552 kB\nMemAvailable: 1 kB\n", encoding="utf-8"
    )
    out = subprocess.run(
        ["bash", str(AGENTS_UP), "--print", str(repo)],
        capture_output=True,
        text=True,
        timeout=30,
        env={
            "PATH": "/usr/bin:/bin",
            "HOME": str(home),
            "FABRIK_PROC_ROOT": str(home / "proc"),
            "AGENT_IDENTITY_FILE": str(store),
        },
    )
    panes = [ln for ln in out.stdout.splitlines() if ln.startswith("pane ")]
    assert any(ln.startswith(f"pane b-1 {U1} ") for ln in panes), (out.stdout, out.stderr)
