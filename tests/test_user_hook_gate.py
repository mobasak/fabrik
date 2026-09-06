"""Behavior Contract — `scripts/sysadmin/user_hook_gate.py`.

Closes the fabrik-lib gap WITHOUT editing a fleet-synced hook or the sync exclusion: the hub's
`mcp_watch.py` and `quota_stop.py` are registered at USER level (every window) through this
gate, which runs them only when the project at `cwd` does NOT already wire that hook itself.
In the 42 synced repos the project copy fires and this exits silently (no double banner, no
double deny); in fabrik-lib and any non-project cwd the hub copy fires. One registration,
zero duplication, the synced files untouched.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
GATE = REPO / "scripts" / "sysadmin" / "user_hook_gate.py"


def _fake_hook(tmp_path: Path) -> Path:
    h = tmp_path / "fake_hook.py"
    h.write_text(
        "import sys,json; d=json.loads(sys.stdin.read()); print('FAKE-HOOK-RAN', d.get('cwd'))\n"
    )
    return h


def _run(hook: Path, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(GATE), str(hook)],
        input=json.dumps(
            {"session_id": "s", "cwd": str(cwd), "hook_event_name": "UserPromptSubmit"}
        ),
        capture_output=True,
        text=True,
        timeout=30,
        env={**os.environ},
    )


def test_runs_the_hook_when_the_project_does_not_wire_it(tmp_path):
    proj = tmp_path / "fabrik-lib"
    (proj / ".claude").mkdir(parents=True)
    (proj / ".claude" / "settings.json").write_text(json.dumps({"hooks": {"Stop": []}}))
    p = _run(_fake_hook(tmp_path), proj)
    assert p.returncode == 0 and "FAKE-HOOK-RAN" in p.stdout, p.stdout + p.stderr


def test_defers_when_the_project_already_wires_the_same_hook(tmp_path):
    """The synced repos: the project copy fires; this one must NOT — two banners / two denies."""
    proj = tmp_path / "synced"
    (proj / ".claude").mkdir(parents=True)
    (proj / ".claude" / "settings.json").write_text(
        json.dumps(
            {
                "hooks": {
                    "UserPromptSubmit": [
                        {
                            "hooks": [
                                {
                                    "command": 'python3 "$CLAUDE_PROJECT_DIR/.claude/hooks/fake_hook.py"'
                                }
                            ]
                        }
                    ]
                }
            }
        )
    )
    p = _run(_fake_hook(tmp_path), proj)
    assert p.returncode == 0 and "FAKE-HOOK-RAN" not in p.stdout


def test_runs_when_there_is_no_project_settings_at_all(tmp_path):
    proj = tmp_path / "bare"
    proj.mkdir()
    assert "FAKE-HOOK-RAN" in _run(_fake_hook(tmp_path), proj).stdout


def test_passes_the_hooks_exit_code_through(tmp_path):
    """quota_stop DENIES with a non-zero exit; the gate must not launder it into an allow."""
    h = tmp_path / "deny.py"
    h.write_text("import sys; print('DENY'); sys.exit(2)\n")
    proj = tmp_path / "bare"
    proj.mkdir()
    p = _run(h, proj)
    assert p.returncode == 2 and "DENY" in p.stdout


def test_unreadable_settings_fails_open_to_running_the_hook(tmp_path):
    proj = tmp_path / "broken"
    (proj / ".claude").mkdir(parents=True)
    (proj / ".claude" / "settings.json").write_text("{not json")
    assert "FAKE-HOOK-RAN" in _run(_fake_hook(tmp_path), proj).stdout


# --- review pass 1 (2026-09-06), Finder B: B1 B2 B3 B8 B9 ----------------------------------------

HUB_QUOTA_STOP = REPO / ".claude" / "hooks" / "quota_stop.py"


def _payload(cwd, event="PreToolUse", tool="Edit"):
    return json.dumps(
        {
            "session_id": "s",
            "cwd": str(cwd),
            "hook_event_name": event,
            "tool_name": tool,
            "tool_input": {"file_path": str(cwd / "x.py")},
        }
    )


def _run_p(hook, cwd, payload=None, env=None):
    return subprocess.run(
        [sys.executable, str(GATE), str(hook)],
        input=payload or _payload(cwd),
        capture_output=True,
        text=True,
        timeout=30,
        env={**os.environ, **(env or {})},
    )


def test_the_real_quota_stop_deny_passes_through_byte_identical(tmp_path):
    """B1: the docstring claimed quota_stop DENIES with a non-zero exit — it exits 0 and denies via
    stdout JSON (hookSpecificOutput.permissionDecision). The old grader asserted a contract no
    wrapped hook uses. This runs the REAL hook under a temp state dir with a stamp and a FRESH tick."""
    state = tmp_path / "state"
    state.mkdir()
    (state / "fleet-exhausted").write_text("0")
    tick = state / "rotate-tick.log"
    tick.write_text("tick\n")
    env = {"ROTATE_STATE_DIR": str(state), "QUOTA_STOP_TICK_LOG": str(tick)}
    proj = tmp_path / "bare"
    proj.mkdir()
    direct = subprocess.run(
        [sys.executable, str(HUB_QUOTA_STOP)],
        input=_payload(proj),
        capture_output=True,
        text=True,
        timeout=30,
        env={**os.environ, **env},
    )
    gated = _run_p(HUB_QUOTA_STOP, proj, env=env)
    assert '"permissionDecision": "deny"' in direct.stdout, direct.stdout[:300]
    assert gated.stdout == direct.stdout and gated.returncode == direct.returncode == 0


def test_defers_only_on_a_real_registration_under_the_same_event(tmp_path):
    """B2: substring detection deferred on a mention in permissions.deny, on a wiring under the
    WRONG event, on a disabled leftover — silently stripping a window of its hold."""
    proj = tmp_path / "p"
    (proj / ".claude").mkdir(parents=True)
    h = _fake_hook(tmp_path)
    wrong_event = {
        "hooks": {"Stop": [{"hooks": [{"type": "command", "command": f"python3 x/{h.name}"}]}]},
        "permissions": {"deny": [f"Bash(python3 {h.name})"]},
    }
    (proj / ".claude" / "settings.json").write_text(json.dumps(wrong_event))
    assert "FAKE-HOOK-RAN" in _run_p(h, proj).stdout, "a wrong-event wiring must NOT defer"
    disabled = {
        "disableAllHooks": True,
        "hooks": {
            "PreToolUse": [
                {"matcher": ".*", "hooks": [{"type": "command", "command": f"python3 x/{h.name}"}]}
            ]
        },
    }
    (proj / ".claude" / "settings.json").write_text(json.dumps(disabled))
    assert "FAKE-HOOK-RAN" in _run_p(h, proj).stdout, (
        "disableAllHooks means the project copy never runs"
    )
    real = {
        "hooks": {
            "PreToolUse": [
                {"matcher": ".*", "hooks": [{"type": "command", "command": f"python3 x/{h.name}"}]}
            ]
        }
    }
    (proj / ".claude" / "settings.json").write_text(json.dumps(real))
    assert "FAKE-HOOK-RAN" not in _run_p(h, proj).stdout, "a real same-event wiring defers"


def test_a_subdirectory_cwd_resolves_to_the_project_root(tmp_path):
    """B3: cwd=/opt/x/scripts found no .claude/settings.json and ran the hook a second time —
    two banners per prompt, two denies per call, exactly what the gate exists to prevent."""
    proj = tmp_path / "p"
    (proj / ".claude").mkdir(parents=True)
    (proj / "scripts").mkdir()
    h = _fake_hook(tmp_path)
    (proj / ".claude" / "settings.json").write_text(
        json.dumps(
            {
                "hooks": {
                    "PreToolUse": [
                        {
                            "matcher": ".*",
                            "hooks": [{"type": "command", "command": f"python3 x/{h.name}"}],
                        }
                    ]
                }
            }
        )
    )
    assert "FAKE-HOOK-RAN" not in _run_p(h, proj / "scripts").stdout


def test_a_hanging_hook_fails_open_with_a_line_on_stderr(tmp_path):
    """B8: TimeoutExpired was uncaught (traceback, exit 1) and the inner timeout (120 s) exceeded the
    registration's (30 s), so the harness killed the gate first and orphaned the child."""
    h = tmp_path / "hang.py"
    h.write_text("import time; time.sleep(30)\n")
    proj = tmp_path / "bare"
    proj.mkdir()
    p = _run_p(h, proj, env={"USER_HOOK_GATE_TIMEOUT_S": "1"})
    assert p.returncode == 0 and "timed out" in p.stderr.lower()


def test_a_missing_hook_says_so_on_stderr(tmp_path):
    """B9: a renamed/moved hub hook silently removed the fleet-wide hold from every window."""
    proj = tmp_path / "bare"
    proj.mkdir()
    p = _run_p(tmp_path / "nope.py", proj)
    assert p.returncode == 0 and "nope.py" in p.stderr
