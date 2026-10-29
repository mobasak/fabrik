# AFTER-EDIT: scripts/whoami_agent.py, scripts/command_run.py
"""Graders for the self-naming identity channel (D-267/D-268).

Every one of these exists because a review pass found the opposite behaviour in the spec that
preceded the code: a pid-keyed liveness check that made every binding inert at birth, a collision
check a plain `cd` defeated, a name alphabet three validators disagreed on, and a Cobra
counter-measure that did not exist. They are written to kill those specific mutants.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

FABRIK = Path(__file__).resolve().parents[1]
WHOAMI = FABRIK / "scripts/whoami_agent.py"


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
    # part of, because there is no input that sets the id.
    out = subprocess.run(
        [sys.executable, str(WHOAMI), "--help"],
        check=True,
        capture_output=True,
        text=True,
    )
    for forbidden in ("--session", "--sid", "--session-id"):
        assert forbidden not in out.stdout, f"{forbidden} would let one session name another"


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


# ── W-a77742db: a session resumed into a new claude process is re-recorded under it ────────────
def _bound_elsewhere(m, sid="sid-alpha", name="agent-2", pid=9_999_999, start=1, top=None):
    """A row for `sid` written under ANOTHER claude process (a dead pid by default) — the shape
    every session resumed into a new process carries (measured 2026-10-28: 10 of 15 bound live
    windows)."""
    row = json.loads(_holder(m, pid, start, sid=sid, name=name))
    if top is not None:
        row["toplevel"] = top
    row["at"] = 100
    return json.dumps(row)


def test_refresh_records_a_resumed_session_under_its_new_process(store, monkeypatch):
    """Behaviour 1: the one case refresh writes — this session's last in-scope row names a valid
    name, still the newest row of that name, under a dead process — appends ONE row with the same
    session, name and scope under THIS process, marked as a refresh, never forced; a passed
    `top` is the scope (the SessionStart hook passes its own, so no second git runs)."""
    m = _mod()
    pid, start = _own_process(m, monkeypatch)
    store.write_text(_bound_elsewhere(m) + "\n", encoding="utf-8")
    assert m.refresh() == "agent-2"
    rows = m._rows(store)
    assert len(rows) == 2
    new = rows[-1]
    assert (new["session_id"], new["name"], new["toplevel"]) == ("sid-alpha", "agent-2", m._toplevel())
    assert (new["pid"], new["pid_start"]) == (pid, start)
    assert new["refresh"] is True and new["force"] is False and new["unlocked"] is False
    assert m.resolve_agent_name() == "agent-2"
    store.write_text(_bound_elsewhere(m, top="/given/.git") + "\n", encoding="utf-8")
    monkeypatch.setattr(m, "_toplevel", lambda: pytest.fail("a passed scope runs no git"))
    assert m.refresh(top="/given/.git") == "agent-2"
    assert m._rows(store)[-1]["toplevel"] == "/given/.git"


def test_refresh_writes_nothing_outside_its_one_case(store, monkeypatch):
    """Behaviour 2: every guard of the design's input table writes nothing — and a second call
    after a refresh writes nothing (idempotent per process)."""
    import fcntl

    m = _mod()
    pid, start = _own_process(m, monkeypatch)
    other = os.getppid()  # a LIVE process that is not this window

    def unchanged(text: str, **kw: object) -> bool:
        store.write_text(text, encoding="utf-8")
        before = store.read_bytes()
        got = m.refresh(**kw)
        return got == "" and store.read_bytes() == before

    assert unchanged("")  # no binding for this session
    assert unchanged(_bound_elsewhere(m, sid="sid-other") + "\n")  # another session's row only
    assert unchanged(_bound_elsewhere(m, name="Bad Name") + "\n")  # invalid name
    assert unchanged(_bound_elsewhere(m, top="/elsewhere/.git") + "\n")  # only in another scope
    assert unchanged(_bound_elsewhere(m, top="") + "\n")  # an unknown scope is never ours
    assert unchanged(_bound_elsewhere(m) + "\n", top="")  # nor an unknown current scope
    assert unchanged(_holder(m, pid, start, sid="sid-alpha") + "\n")  # already under this process
    # the sid is live in ANOTHER process (`claude --resume <sid>` in a second terminal)
    assert unchanged(_bound_elsewhere(m, pid=other, start=m._pid_start(other)) + "\n")
    lock = os.open(str(store) + ".lock", os.O_CREAT | os.O_RDWR, 0o600)
    fcntl.flock(lock, fcntl.LOCK_EX)  # a writer holds the store: one try, then nothing
    t0 = time.monotonic()
    assert unchanged(_bound_elsewhere(m) + "\n")
    assert time.monotonic() - t0 < 1.0, "a busy store must not hold SessionStart"
    fcntl.flock(lock, fcntl.LOCK_UN)
    os.close(lock)
    monkeypatch.setenv("CLAUDE_PID", "31337")  # a nested claude: the walk reached the outer one
    assert unchanged(_bound_elsewhere(m) + "\n")
    monkeypatch.delenv("CLAUDE_PID")
    monkeypatch.setattr(m, "_session_pid", lambda: None)  # no claude ancestor
    assert unchanged(_bound_elsewhere(m) + "\n")
    _own_process(m, monkeypatch)
    real_start = m._pid_start
    monkeypatch.setattr(m, "_pid_start", lambda _pid: None)  # start tick unreadable
    assert unchanged(_bound_elsewhere(m) + "\n")
    monkeypatch.setattr(m, "_pid_start", real_start)
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "")
    assert unchanged(_bound_elsewhere(m) + "\n")  # no session id
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "sid-alpha")
    store.write_text(_bound_elsewhere(m) + "\n", encoding="utf-8")
    assert m.refresh() == "agent-2"  # the positive control under the same patches
    once = store.read_bytes()
    assert m.refresh() == "" and store.read_bytes() == once  # idempotent


def test_refresh_never_takes_back_a_name_re_taken_since(store, monkeypatch):
    """Behaviour 3: once another session bound the name after this one, a refresh would make this
    window the name's newest live holder again — a silent take-back; it writes nothing. And the
    last row is chosen PER SCOPE: a sid holding the name here and elsewhere refreshes here."""
    m = _mod()
    _own_process(m, monkeypatch)
    store.write_text(
        _bound_elsewhere(m) + "\n" + _bound_elsewhere(m, sid="sid-new", pid=9_999_998) + "\n",
        encoding="utf-8",
    )
    before = store.read_bytes()
    assert m.refresh() == "" and store.read_bytes() == before
    # this session re-bound the name after the other one took it: its own again, refreshed
    store.write_text(
        _bound_elsewhere(m, name="agent-3")
        + "\n"
        + _bound_elsewhere(m, sid="sid-new", name="agent-3", pid=9_999_998)
        + "\n"
        + _bound_elsewhere(m, name="agent-2")
        + "\n",
        encoding="utf-8",
    )
    assert m.refresh() == "agent-2"
    # the session's LAST row overall sits in another repo; its last row HERE still refreshes
    store.write_text(
        _bound_elsewhere(m) + "\n" + _bound_elsewhere(m, top="/elsewhere/.git") + "\n",
        encoding="utf-8",
    )
    assert m.refresh() == "agent-2"
    assert m._rows(store)[-1]["toplevel"] == m._toplevel()


def test_refresh_never_changes_what_the_session_resolves_to(store, monkeypatch):
    """Review round 1 (A-haiku-1): the session's LAST row overall decides its name
    (`resolve_agent_name`); a session forced to another name in another repo must not get its old
    name here re-recorded as its newest row, or its identity flips. A refresh writes only the name
    the session resolves to now."""
    m = _mod()
    _own_process(m, monkeypatch)
    store.write_text(
        _bound_elsewhere(m, name="alpha")
        + "\n"
        + _bound_elsewhere(m, name="beta", top="/elsewhere/.git")
        + "\n",
        encoding="utf-8",
    )
    assert m.resolve_agent_name() == "beta"
    before = store.read_bytes()
    assert m.refresh() == "" and store.read_bytes() == before
    assert m.resolve_agent_name() == "beta"


def test_refresh_leaves_a_session_live_in_another_process_alone(store, monkeypatch):
    """Review round 1 (A-haiku-5): the sid is live in another process even when that process's row
    is not the sid's last one (a later `--force` re-bind under a process since gone); any live row
    of this sid under another process leaves it alone."""
    m = _mod()
    _own_process(m, monkeypatch)
    other = os.getppid()
    store.write_text(
        _bound_elsewhere(m, pid=other, start=m._pid_start(other)) + "\n" + _bound_elsewhere(m) + "\n",
        encoding="utf-8",
    )
    before = store.read_bytes()
    assert m.refresh() == "" and store.read_bytes() == before


def test_refresh_is_not_blocked_by_this_windows_own_row_in_another_repo(store, monkeypatch):
    """Review round 2 (A-haiku-p2-1): the live-process refusal is about ANOTHER process holding the
    session; this window's own live row in another repo is not that, and must not block the row
    here (the lane here keys on a row of this process in this repo)."""
    m = _mod()
    pid, start = _own_process(m, monkeypatch)
    store.write_text(
        _bound_elsewhere(m) + "\n" + _holder(m, pid, start, sid="sid-alpha").replace(
            json.dumps(m._toplevel()), json.dumps("/elsewhere/.git")
        )
        + "\n",
        encoding="utf-8",
    )
    assert m.refresh() == "agent-2"
    assert m._rows(store)[-1]["toplevel"] == m._toplevel()
    # review r3 (A-haiku-p3-1): only THIS window's row elsewhere is exempt — another live process's
    # row in another repo still leaves the session alone
    other = os.getppid()
    store.write_text(
        _bound_elsewhere(m)
        + "\n"
        + _bound_elsewhere(m, pid=other, start=m._pid_start(other), top="/elsewhere/.git")
        + "\n",
        encoding="utf-8",
    )
    before = store.read_bytes()
    assert m.refresh() == "" and store.read_bytes() == before


def test_refresh_with_no_store_creates_nothing(tmp_path, monkeypatch):
    """Review round 1 (A-sonnet-2): every SessionStart in every repo calls refresh; with nothing
    ever bound there is no store, and refresh must not create its directory or a lock file."""
    store = tmp_path / "state" / "agent-identity.jsonl"
    monkeypatch.setenv("AGENT_IDENTITY_FILE", str(store))
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "sid-alpha")
    m = _mod()
    _own_process(m, monkeypatch)
    assert m.refresh(top="/some/repo/.git") == ""
    assert not (tmp_path / "state").exists()


def test_refresh_matches_the_scope_by_realpath_and_never_by_an_empty_one(store, monkeypatch, tmp_path):
    """Review round 1 (A-sonnet-1, A-haiku-2): the hook passes a realpath'd common dir while `bind`
    stored git's string — a symlinked spelling of the same repo is the same scope, and the new row
    keeps the binding's own spelling; an empty scope is never this one, even where the store holds
    a row whose scope is the current directory (realpath("") is the cwd)."""
    m = _mod()
    _own_process(m, monkeypatch)
    real = tmp_path / "repo-real" / ".git"
    real.mkdir(parents=True)
    link = tmp_path / "repo-link"
    link.symlink_to(tmp_path / "repo-real")
    store.write_text(_bound_elsewhere(m, top=str(link / ".git")) + "\n", encoding="utf-8")
    assert m.refresh(top=str(real)) == "agent-2"
    assert m._rows(store)[-1]["toplevel"] == str(link / ".git")
    monkeypatch.chdir(tmp_path)
    store.write_text(_bound_elsewhere(m, top=os.path.realpath(".")) + "\n", encoding="utf-8")
    before = store.read_bytes()
    assert m.refresh(top="") == "" and store.read_bytes() == before
