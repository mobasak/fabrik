"""The prompt block is printed only when it changed (W-25f6b2a3 slice 2).

Every copy a UserPromptSubmit hook prints stays in the session's context for the rest of its life, so
`thread_anchor.py line --hook` prints an unchanged block as ONE pointer line naming the command that
reprints it. Driven end to end as the hook runs: the script as a subprocess, the payload on stdin, the
state dir pinned to tmp. The block here is the anchor block (no `cwd`, so no work store is read).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "thread_anchor.py"
POINTER = "work: unchanged since the last full block above — reprint: python3 scripts/thread_anchor.py line --session {s} --repo ."


def _run(args: list[str], d: Path, stdin: str = "") -> str:
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        input=stdin,
        capture_output=True,
        text=True,
        timeout=60,
        env={
            "PATH": os.environ.get("PATH", ""),
            "THREAD_ANCHOR_DIR": str(d),
            "FABRIK_WORK_PROC": os.environ.get("FABRIK_WORK_PROC", ""),  # conftest pin
        },
    )
    assert proc.returncode == 0, proc.stderr
    return proc.stdout


def _hook(d: Path, event: str = "UserPromptSubmit", session: str = "s1") -> str:
    payload = {"session_id": session, "hook_event_name": event, "prompt": "go on"}
    return _run(["line", "--hook"], d, json.dumps(payload))


def _anchor(d: Path, text: str, session: str = "s1") -> None:
    _run(["harvest", "--session", session], d, f"done\nNEXT: {text}")


def test_unchanged_block_prints_pointer_and_change_reprints(tmp_path):
    _anchor(tmp_path, "the corpus audit — command 14 of 31 — /fabrik-user-test")
    full = _hook(tmp_path, event="SessionStart")
    assert "14 of 31" in full
    # the start printed it and stored it: the first prompt points back at it
    assert _hook(tmp_path).strip() == POINTER.format(s="s1")
    assert _hook(tmp_path).strip() == POINTER.format(s="s1")
    # a real change reprints in full
    _anchor(tmp_path, "the corpus audit — command 15 of 31 — /fabrik-user-test")
    changed = _hook(tmp_path)
    assert "15 of 31" in changed and "unchanged since" not in changed
    # a full block older than the refresh bound reprints though unchanged
    digest = tmp_path / "s1.prompt-digest"
    rec = json.loads(digest.read_text())
    rec["at"] -= 1800
    digest.write_text(json.dumps(rec))
    assert _hook(tmp_path) == changed
    assert _hook(tmp_path).strip() == POINTER.format(s="s1")
    # SessionStart always prints in full, even unchanged
    assert "15 of 31" in _hook(tmp_path, event="SessionStart")
    # and the pointer's own reprint command prints the block in full
    assert "15 of 31" in _run(["line", "--session", "s1"], tmp_path)


def test_no_pointer_without_a_session_a_block_or_a_readable_digest(tmp_path):
    # an empty block prints nothing and stores nothing, as before
    assert _hook(tmp_path) == ""
    assert not (tmp_path / "s1.prompt-digest").exists()
    # "nosession" (no session id in the payload) never dedups
    _anchor(tmp_path, "the bare thread — step 1 — x", session="nosession")
    blank = json.dumps({"hook_event_name": "UserPromptSubmit"})
    first = _run(["line", "--hook"], tmp_path, blank)
    assert "the bare thread" in first
    assert _run(["line", "--hook"], tmp_path, blank) == first
    # a corrupt or foreign digest file prints the full block
    _anchor(tmp_path, "the real thread — step 2 — y")
    full = _hook(tmp_path)
    for junk in ("{not json", '{"digest": 3, "at": "x"}', "[]"):
        (tmp_path / "s1.prompt-digest").write_text(junk)
        assert _hook(tmp_path) == full
    # the digest file is not a session-state json: `*.json` scans never read it
    assert not list(tmp_path.glob("*.prompt-digest*.json"))
