"""The user-level self-watch ARM hook (scripts/sysadmin/claude_selfwatch_orient.sh).

It exists for the repos the hub's session_orient.py never reaches (sync-excluded: fabrik-lib),
whose panes therefore never armed a watch — 3 of the 4 unarmed /opt sessions on
2026-09-03. Every gate is a behavior a wrong emission would break: a duplicate order in a
hub-hooked repo breeds two arms; an order in a /tmp one-shot helper arms a watch with no
pane; an order on source=compact breeds a duplicate watcher; a headless run has no pane.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

HOOK = Path(__file__).resolve().parents[1] / "scripts/sysadmin/claude_selfwatch_orient.sh"


def _run(payload: object, home: Path, project_dir: str | None = None, **env: str) -> str:
    e = {
        k: v
        for k, v in os.environ.items()
        if k not in ("CLAUDE_PROJECT_DIR", "CLAUDE_MESH_HEADLESS")
    }
    e["HOME"] = str(home)
    if project_dir is not None:
        e["CLAUDE_PROJECT_DIR"] = project_dir
    e.update(env)
    text = payload if isinstance(payload, str) else json.dumps(payload)
    return subprocess.run(
        ["bash", str(HOOK)], input=text, capture_output=True, text=True, env=e, timeout=20
    ).stdout


def _home_with_watch(tmp_path: Path) -> Path:
    home = tmp_path / "home"
    (home / ".claude/bin").mkdir(parents=True)
    (home / ".claude/bin/claude-selfwatch.sh").write_text("#!/bin/bash\n")
    return home


def test_emits_the_arm_order_with_the_real_sid_for_an_unhooked_opt_repo(tmp_path: Path) -> None:
    home = _home_with_watch(tmp_path)
    out = _run({"session_id": "sid-42-abc", "cwd": "/opt/fabrik-lib", "source": "startup"}, home)
    assert 'command: "bash ~/.claude/bin/claude-selfwatch.sh sid-42-abc"' in out
    assert "STANDING watch" in out and "never re-arm" in out
    assert "nohup bash" not in out


def test_silent_when_the_project_carries_the_hub_orient_hook(tmp_path: Path) -> None:
    home = _home_with_watch(tmp_path)
    proj = tmp_path / "proj"
    (proj / ".claude/hooks").mkdir(parents=True)
    (proj / ".claude/hooks/session_orient.py").write_text("")
    # cwd inside a worktree of the project: the project dir decides, not the cwd
    out = _run(
        {"session_id": "s1", "cwd": "/opt/x/.claude/worktrees/a"}, home, project_dir=str(proj)
    )
    assert out == ""


def test_silent_outside_opt_headless_on_compact_and_without_the_watch_script(
    tmp_path: Path,
) -> None:
    home = _home_with_watch(tmp_path)
    assert _run({"session_id": "s1", "cwd": "/tmp"}, home) == ""  # the VS Code one-shot helpers
    assert _run({"session_id": "s1", "cwd": "/opt/fabrik-lib", "source": "compact"}, home) == ""
    assert (
        _run({"session_id": "s1", "cwd": "/opt/fabrik-lib"}, home, CLAUDE_MESH_HEADLESS="1") == ""
    )
    assert _run({"cwd": "/opt/fabrik-lib"}, home) == ""  # no sid → nothing to arm
    bare = tmp_path / "bare"
    bare.mkdir()
    assert _run({"session_id": "s1", "cwd": "/opt/fabrik-lib"}, bare) == ""


def test_fails_open_on_garbage_payloads_and_sanitizes_the_sid(tmp_path: Path) -> None:
    home = _home_with_watch(tmp_path)
    assert _run("not json", home) == ""
    assert _run([1, 2], home) == ""
    out = _run({"session_id": "x;rm -rf /", "cwd": "/opt/fabrik-lib"}, home)
    assert "claude-selfwatch.sh x_rm_-rf__" in out
