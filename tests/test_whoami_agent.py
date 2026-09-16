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


def test_the_alphabet_matches_its_two_sibling_validators():
    # None of these three files may import another, so the copies are pinned here. A one-sided
    # edit — the class that lets a name bind and then be silently dropped downstream — fails this.
    pat = "^[a-z0-9-]{1,32}$"
    for rel in ("scripts/whoami_agent.py", "scripts/command_run.py", ".claude/hooks/agent_role.py"):
        text = (FABRIK / rel).read_text(encoding="utf-8")
        assert pat in text or pat.strip("^$") in text, f"{rel} drifted from the shared alphabet"


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


def test_conftest_pins_the_store_so_graders_never_touch_the_live_one():
    text = (FABRIK / "tests/conftest.py").read_text(encoding="utf-8")
    assert "AGENT_IDENTITY_FILE" in text, "writer graders would append to the operator's real store"
