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
        input=json.dumps({"session_id": "s", "cwd": str(cwd)}),
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
