"""Behaviour graders for the coordinator wait guard in .claude/hooks/seat_guard.py (W-e57d2481, D-1296).

D-1296 (operator, 2026-10-27): no coordinator, in any repo, blocks its turn on a long wait — the
operator cannot reach it meanwhile. For the session bound as its repo's merge owner, the PreToolUse
Bash hook refuses a foreground call whose tool timeout exceeds 120 s, or that runs a `sleep` inside
a loop under a timeout over 60 s, and points at run_in_background.

Every case drives the real hook as a subprocess with a JSON payload on stdin (the transport Claude
Code uses), against a tmp git repo whose docs/DECISIONS.md declares the merge owner, a tmp identity
store and THIS checkout's scripts/decisions.py as the resolver — never the live hub tree or the
developer's real identity store. Invariant the other seat_guard suites rely on: none of them sends
a lead payload with a timeout over 120000 or a sleep loop, so none of them reaches the identity
lookup (and the real store).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import pytest

REPO = Path(__file__).resolve().parent.parent
HOOK = REPO / ".claude" / "hooks" / "seat_guard.py"
DECISIONS_PY = REPO / "scripts" / "decisions.py"
COORD = "sid-coord"
BUILDER = "sid-builder"
LONG_WAITS = [
    # the measured shapes (measure.md §2) and other legitimate spellings of a sleep loop
    "for i in $(seq 1 28); do pgrep -f 'merge_request.py merge' >/dev/null || break; sleep 20; done",
    "while kill -0 3764331 2>/dev/null; do sleep 10; done; tail -10 /tmp/x.output",
    "until grep -qE 'passed|failed' /tmp/x.output; do sleep 5; done",
    "timeout 590 bash -c 'until grep -qE \"passed|failed\" /tmp/x.output; do sleep 5; done'",
    "bash -lc 'for n in a b; do for i in $(seq 1 30); do echo $n; sleep 10; done; done'",
    "{ while kill -0 12345; do sleep 5; done; } 2>/dev/null",
    "if [ -f /tmp/x ]; then while kill -0 12345; do sleep 5; done; fi",
    "! while kill -0 12345; do sleep 5; done",
    "time while kill -0 12345; do sleep 5; done",
    "select x in a b; do sleep 5; done",
    # a nested double `done` must not unbalance the count for a LATER loop
    "for a in 1 2; do for b in 1 2; do echo $a$b; done; done; while true; do sleep 5; done",
    # untokenisable (an unclosed quote): the regex fallback still sees loop, `do`, sleep
    "while true; do sleep 5; done; echo 'unterminated",
    # a stray `done` first must clamp at 0, never hide the loop after it
    "done; while true; do sleep 5; done",
    # the `function NAME {` form: the name is no keyword
    "function f { while true; do sleep 5; done; }; f",
]


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout.strip()


@pytest.fixture
def box(tmp_path: Path) -> dict:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    (repo / "docs").mkdir()
    (repo / "docs" / "DECISIONS.md").write_text(
        "# Decisions\n\n| ID | When | Who | What | Why | Where |\n|---|---|---|---|---|---|\n"
        "| D-001 | 2026-10-27 | operator | MERGE OWNER: coordinator — merges | test | here |\n"
    )
    store = tmp_path / "agent-identity.jsonl"
    common = str(repo / ".git")
    rows = [
        {"session_id": COORD, "name": "coordinator", "toplevel": common, "at": int(time.time())},
        {"session_id": BUILDER, "name": "infra", "toplevel": common, "at": int(time.time())},
    ]
    store.write_text("".join(json.dumps(r) + "\n" for r in rows))
    state = tmp_path / "state"
    state.mkdir()
    env = {k: v for k, v in os.environ.items() if not k.startswith(("CLAUDE_", "BASH_"))}
    env.update(
        {
            "AGENT_IDENTITY_FILE": str(store),
            "CLAUDE_PROJECT_DIR": str(repo),
            "QUOTA_STOP_DECISIONS_PY": str(DECISIONS_PY),
            "ROTATE_STATE_DIR": str(state),
        }
    )
    return {"repo": repo, "env": env, "tmp": tmp_path}


def _run(box: dict, command: str, *, sid: str = COORD, **tool: object) -> dict | None:
    payload: dict = {
        "session_id": sid,
        "cwd": str(box["repo"]),
        "hook_event_name": "PreToolUse",
        "tool_name": "Bash",
        "tool_input": {"command": command, **tool},
    }
    if "agent_id" in tool:
        payload["agent_id"] = tool.pop("agent_id")
        payload["agent_type"] = "general-purpose"
        payload["tool_input"].pop("agent_id", None)
    r = subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=30,
        env=box["env"],
        cwd=str(box["repo"]),
    )
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)["hookSpecificOutput"] if r.stdout.strip() else None


def _denied(out: dict | None) -> bool:
    return out is not None and out.get("permissionDecision") == "deny"


def test_a_coordinator_long_timeout_is_denied(box: dict) -> None:
    """The measured web-ecommerce-factory shape: one long foreground call, no loop, no sleep."""
    out = _run(
        box, "timeout 590 python3 scripts/merge_request.py merge 2>&1 | tail -2", timeout=600000
    )
    assert out is not None and _denied(out)
    reason = out["permissionDecisionReason"]
    for needle in ("D-1296", "coordinator", "run_in_background", "600 s", "end the turn"):
        assert needle in reason, (needle, reason)


def test_a_background_call_is_allowed(box: dict) -> None:
    out = _run(
        box, "python3 scripts/merge_request.py merge", timeout=600000, run_in_background=True
    )
    assert not _denied(out)


@pytest.mark.parametrize("command", LONG_WAITS)
def test_a_sleep_loop_is_denied_in_many_spellings(box: dict, command: str) -> None:
    """Under the DEFAULT timeout (absent → 120 s) a sleep loop still blocks up to two minutes."""
    out = _run(box, command)
    assert out is not None and _denied(out), command
    assert "loop" in out["permissionDecisionReason"]


def test_nested_loops_keep_the_seat_checks(box: dict) -> None:
    """The loop count never raises inside the scan: a seat's git write inside a nested loop is still
    denied by the SEAT check (an exception there would have failed the whole guard open)."""
    # three `done`s for two loops, all BEFORE the git write: the stray close is counted (clamped,
    # never raising) before the seat check reaches the commit
    cmd = "for a in 1 2; do for b in 1 2; do :; done; done; done; git -C /opt/fabrik commit -m x"
    payload = {
        "session_id": "sid-seat",
        "cwd": str(box["repo"]),
        "agent_id": "agent-1",
        "agent_type": "fabrik-reviewer",
        "hook_event_name": "PreToolUse",
        "tool_name": "Bash",
        "tool_input": {"command": cmd},
    }
    r = subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=30,
        env=box["env"],
    )
    assert r.returncode == 0, r.stderr
    seat_out = json.loads(r.stdout)["hookSpecificOutput"]
    assert seat_out.get("permissionDecision") == "deny"
    assert "seat guard" in seat_out["permissionDecisionReason"]


@pytest.mark.parametrize(
    "command",
    [
        "systemctl --user start x.path; sleep 3; systemctl --user is-active x.path",
        "sleep 2",
        "for f in a b c; do echo $f; done",
        "until grep -q x /tmp/f; do :; done",
        "echo 'while true; do sleep 5; done'",
        "cat <<'EOF'\nwhile true; do sleep 5; done\nEOF",
        # untokenisable prose naming a loop word and a sleep, with no `do` between them
        'echo "for the record" \'x; sleep 3',
    ],
)
def test_a_lone_sleep_or_a_sleepless_loop_is_allowed(box: dict, command: str) -> None:
    assert not _denied(_run(box, command))


@pytest.mark.parametrize(
    ("command", "timeout"),
    [
        ("for i in 1 2 3; do curl -sf http://x/health && break; sleep 2; done", 60000),
        ("while kill -0 1; do sleep 5; done", 30000),
        ("python3 scripts/merge_request.py merge", 120000),
        ("python3 scripts/merge_request.py merge", None),
    ],
)
def test_short_caps_are_allowed(box: dict, command: str, timeout: int | None) -> None:
    tool: dict[str, Any] = {} if timeout is None else {"timeout": timeout}
    assert not _denied(_run(box, command, **tool))


def test_the_timeout_is_read_strictly(box: dict) -> None:
    """One strict parse for the tool's timeout and BASH_DEFAULT_TIMEOUT_MS: a positive number or a
    plain ASCII digit string counts; anything else (bool, zero, negative, NaN, inf, `²`, text) is no
    value and falls to the next source — and nothing raises, so the guard never fails open by error."""
    loop = "while kill -0 1; do sleep 5; done"
    plain = "python3 scripts/merge_request.py merge"
    # junk tool timeouts fall to the default 120000: a loop is denied, a plain call is not
    for junk in (True, 0, -5, float("nan"), float("inf"), "abc", "1.5", "²"):
        assert _denied(_run(box, loop, timeout=junk)), junk
        assert not _denied(_run(box, plain, timeout=junk)), junk
    # a digit string counts as its number; a huge int is over every cap and never raises
    for big in ("150000", " 600000 ", 10**400):
        out = _run(box, plain, timeout=big)
        assert out is not None and _denied(out), big
    # the strict edges, one past each cap
    assert _denied(_run(box, plain, timeout=120001))
    assert _denied(_run(box, loop, timeout=60001))
    # the deny text states the exact seconds
    out = _run(box, loop, timeout=90000)
    assert out is not None and "90 s" in out["permissionDecisionReason"]
    out = _run(box, plain, timeout=120000.5)
    assert out is not None and "120.0005 s" in out["permissionDecisionReason"]
    # junk env values are no default either: the Bash tool's own 120000 applies
    for junk_env in ("²", "abc", "0", "1.5", "9" * 5000):
        box["env"]["BASH_DEFAULT_TIMEOUT_MS"] = junk_env
        assert not _denied(_run(box, plain)), junk_env
        assert _denied(_run(box, loop)), junk_env
    box["env"]["BASH_DEFAULT_TIMEOUT_MS"] = "30000"
    assert not _denied(_run(box, loop))
    box["env"]["BASH_DEFAULT_TIMEOUT_MS"] = "300000"
    assert _denied(_run(box, plain))


def test_non_coordinators_are_not_judged(box: dict) -> None:
    cmd = "while kill -0 1; do sleep 10; done"
    assert not _denied(_run(box, cmd, sid=BUILDER, timeout=600000))  # bound, not the merge owner
    assert not _denied(_run(box, cmd, sid="sid-unbound", timeout=600000))  # no binding
    assert not _denied(
        _run(box, cmd, timeout=600000, agent_id="agent-9")
    )  # the coordinator's subagent


def test_identity_failure_fails_open(box: dict) -> None:
    # a worktree of a BARE repo: its common dir is `bare.git`, not `.git`, so there is no main
    # checkout to judge; the ledger planted beside bare.git must never be read as this repo's
    _git(
        box["repo"],
        "-c",
        "user.name=t",
        "-c",
        "user.email=t@t",
        "commit",
        "-q",
        "--allow-empty",
        "-m",
        "x",
    )
    bare = box["tmp"] / "bare.git"
    _git(box["tmp"], "clone", "-q", "--bare", str(box["repo"]), str(bare))
    wt = box["tmp"] / "bare-wt"
    _git(bare, "worktree", "add", "-q", "--detach", str(wt))
    (box["tmp"] / "docs").mkdir()
    (box["tmp"] / "docs" / "DECISIONS.md").write_text(
        (box["repo"] / "docs" / "DECISIONS.md").read_text()
    )
    with Path(box["env"]["AGENT_IDENTITY_FILE"]).open("a") as fh:
        row = {"session_id": COORD, "name": "coordinator", "toplevel": str(bare)}
        fh.write(json.dumps({**row, "at": int(time.time())}) + "\n")
    box["env"]["CLAUDE_PROJECT_DIR"] = str(wt)
    assert not _denied(_run(box, "sleep 1", timeout=600000))
    box["env"]["CLAUDE_PROJECT_DIR"] = str(box["repo"])
    # no ledger at all
    (box["repo"] / "docs" / "DECISIONS.md").unlink()
    assert not _denied(_run(box, "sleep 1", timeout=600000))
    # a resolver that hangs past quota_stop's 2 s cap: allowed, and the hook stays inside its 5 s budget
    hang = box["tmp"] / "hang.py"
    hang.write_text("import time\ntime.sleep(30)\n")
    (box["repo"] / "docs" / "DECISIONS.md").write_text(
        "| D-001 | x | y | MERGE OWNER: coordinator | z | w |\n"
    )
    box["env"]["QUOTA_STOP_DECISIONS_PY"] = str(hang)
    t0 = time.monotonic()
    out = _run(box, "sleep 1", timeout=600000)
    assert not _denied(out)
    assert time.monotonic() - t0 < 5.0
