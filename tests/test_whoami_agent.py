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
    assert m.bind("agent-a")[0] == 0
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
