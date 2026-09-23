"""The Stop decider must not count the self-watch arm (D-356) as a pending waker.

Measured 2026-09-23: the arm is a background Bash task that never completes while the watch stands. The
decider counted it as pending (`busy-task` → the park chime silenced), armed a recheck at TASK_STALE_S+120,
then declared it "provably lost" and wrote a `waker_lost` death record — which the armed watch consumed and
woke the session with a false "resume the interrupted task" about an hour after every idle turn end. The
persistent Monitor arm it replaced was excluded for the same reason (2026-08-09).
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path


def _load_decider(lock_dir: Path):
    os.environ["CLAUDE_SOUND_LOCKDIR"] = str(lock_dir)
    src = Path.home() / ".claude" / "bin" / "claude-stop-decider.py"
    spec = importlib.util.spec_from_file_location("claude_stop_decider_selfwatch_probe", src)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules.pop("claude_stop_decider_selfwatch_probe", None)
    spec.loader.exec_module(mod)
    return mod


def _dispatch(tool_id: str, task_id: str, command: str) -> list[dict]:
    """The two transcript rows a background Bash dispatch writes, in the live 2.1.280 shape."""
    ts = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    return [
        {
            "type": "assistant",
            "timestamp": ts,
            "message": {
                "role": "assistant",
                "content": [
                    {
                        "type": "tool_use",
                        "id": tool_id,
                        "name": "Bash",
                        "input": {"command": command, "run_in_background": True},
                    }
                ],
            },
        },
        {
            "type": "user",
            "timestamp": ts,
            "message": {
                "role": "user",
                "content": [
                    {
                        "tool_use_id": tool_id,
                        "type": "tool_result",
                        "content": f"running as {task_id}",
                    }
                ],
            },
            "toolUseResult": {"stdout": "", "stderr": "", "backgroundTaskId": task_id},
        },
    ]


def test_the_self_watch_arm_is_not_a_pending_waker_but_other_background_tasks_are(
    tmp_path: Path,
) -> None:
    mod = _load_decider(tmp_path / "locks")
    rows = _dispatch(
        "toolu_arm", "barm00001", "bash /opt/fabrik/scripts/sysadmin/selfwatch_arm.sh dd3c06d1-41b1"
    ) + _dispatch("toolu_job", "bjob00001", "pytest tests/ -q")
    transcript = tmp_path / "t.jsonl"
    transcript.write_text("".join(json.dumps(r) + "\n" for r in rows))
    pending = mod.pending_shell_tasks(transcript, now=time.time())
    assert "barm00001" not in pending, (
        "the standing self-watch arm counted as a waker — the false waker_lost class"
    )
    assert "bjob00001" in pending, "a real background job must still count as pending"


def test_a_command_that_merely_names_the_arm_script_is_still_a_waker(tmp_path: Path) -> None:
    """The exclusion is the arm invocation, never any command mentioning the file."""
    mod = _load_decider(tmp_path / "locks")
    rows = _dispatch(
        "toolu_x", "bcat00001", "sleep 60; cat /opt/fabrik/scripts/sysadmin/selfwatch_arm.sh"
    )
    transcript = tmp_path / "t.jsonl"
    transcript.write_text("".join(json.dumps(r) + "\n" for r in rows))
    assert "bcat00001" in mod.pending_shell_tasks(transcript, now=time.time())


def test_every_real_arm_shape_is_excluded(tmp_path: Path) -> None:
    """Review of the exclusion, A-S1/A-S2: a quoted path, another shell, a `cd` prefix, `bash -c`, a trailing
    comment and a long sid are all the arm — a narrower match re-opens the false waker_lost."""
    mod = _load_decider(tmp_path / "locks")
    arm = "/opt/fabrik/scripts/sysadmin/selfwatch_arm.sh"
    shapes = [
        f'bash "{arm}" dd3c06d1',
        f"/bin/bash {arm} dd3c06d1",
        "cd /opt/fabrik && bash scripts/sysadmin/selfwatch_arm.sh dd3c06d1",
        f"bash -c 'bash {arm} dd3c06d1'",
        f"bash {arm} dd3c06d1  # re-arm",
        f"bash {arm} " + "a" * 120,
        f"bash -x {arm} dd3c06d1",
        f"bash -- {arm} dd3c06d1",
    ]
    rows = []
    for n, cmd in enumerate(shapes):
        rows += _dispatch(f"toolu_{n}", f"barm{n:05d}", cmd)
    transcript = tmp_path / "t.jsonl"
    transcript.write_text("".join(json.dumps(r) + "\n" for r in rows))
    pending = mod.pending_shell_tasks(transcript, now=time.time())
    assert not [p for p in pending if p.startswith("barm")], pending


def test_the_exclusion_holds_whatever_the_row_order(tmp_path: Path) -> None:
    """Review, A-H1: the result row read before its assistant row must still be excluded."""
    mod = _load_decider(tmp_path / "locks")
    a, u = _dispatch(
        "toolu_arm", "barm00001", "bash /opt/fabrik/scripts/sysadmin/selfwatch_arm.sh s1"
    )
    transcript = tmp_path / "t.jsonl"
    transcript.write_text(json.dumps(u) + "\n" + json.dumps(a) + "\n")
    assert "barm00001" not in mod.pending_shell_tasks(transcript, now=time.time())


def test_an_arm_row_without_an_id_excludes_nothing(tmp_path: Path) -> None:
    """Review, A-H2: a tool_use with no id must not seed the literal 'None' and exempt a real job."""
    mod = _load_decider(tmp_path / "locks")
    a, _ = _dispatch(
        "toolu_arm", "barm00001", "bash /opt/fabrik/scripts/sysadmin/selfwatch_arm.sh s1"
    )
    del a["message"]["content"][0]["id"]
    _, job = _dispatch("None", "bjob00001", "pytest -q")
    transcript = tmp_path / "t.jsonl"
    transcript.write_text(json.dumps(a) + "\n" + json.dumps(job) + "\n")
    assert "bjob00001" in mod.pending_shell_tasks(transcript, now=time.time())


def test_a_command_that_only_reads_or_edits_the_arm_script_stays_a_waker(tmp_path: Path) -> None:
    """Review pass 2, A-N1: the arm is the script RUN by a shell (or as the command), never grep/vim/sed/python3
    over it with a trailing argument — excluding those would silence a real pending job."""
    mod = _load_decider(tmp_path / "locks")
    arm = "/opt/fabrik/scripts/sysadmin/selfwatch_arm.sh"
    readers = [
        f"grep -n pattern {arm} foo",
        "vim selfwatch_arm.sh x",
        f"sed -n 1p {arm} 2",
        f"python3 {arm} sid",
        f"ssh host {arm} sid",
    ]
    rows = []
    for n, cmd in enumerate(readers):
        rows += _dispatch(f"toolu_{n}", f"bjob{n:05d}", cmd)
    rows += _dispatch("toolu_direct", "barm00001", f"{arm} sid")
    transcript = tmp_path / "t.jsonl"
    transcript.write_text("".join(json.dumps(r) + "\n" for r in rows))
    pending = mod.pending_shell_tasks(transcript, now=time.time())
    assert sorted(p for p in pending if p.startswith("bjob")) == [
        f"bjob{n:05d}" for n in range(5)
    ], pending
    assert "barm00001" not in pending, "the script run directly as the command is the arm"
