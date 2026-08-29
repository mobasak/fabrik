"""The thread-anchor harvest must survive a drifted Stop payload.

Live blackout, 2026-08-29: after a context compaction, one observed Stop ran the hook
(nothing blocked, nothing was owed) yet the session's thread register never updated and
`final_block_emitted` never fired — both consumers of the payload's transcript/cwd went
dark together while the hook's other work proceeded. The structural defect is that the
harvest block sat BELOW the `scripts/final_gate.py` eligibility early-return and resolved
`thread_anchor.py` ONLY from the payload's cwd: any cwd drift silently disabled durable
memory, though harvest needs no enforcement eligibility at all. The hook file's own
location names its repo when the payload's cannot.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
HOOK = REPO / ".claude" / "hooks" / "final_gate_stop.py"


def _fake_transcript(tmp_path: Path, next_line: str) -> Path:
    tp = tmp_path / "transcript.jsonl"
    entries = [
        {"type": "user", "message": {"content": [{"type": "text", "text": "go"}]}},
        {
            "type": "assistant",
            "message": {"content": [{"type": "text", "text": f"done.\n{next_line}"}]},
        },
    ]
    tp.write_text("\n".join(json.dumps(e) for e in entries) + "\n", encoding="utf-8")
    return tp


def _run_stop(tmp_path: Path, cwd: Path, sid: str) -> Path:
    """Fire a synthetic Stop through the real hook with HOME sandboxed; return the
    register path the harvest should have written."""
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    tp = _fake_transcript(tmp_path, "NEXT: probe thread — item 1 of 3 — continue the sweep")
    payload = json.dumps(
        {
            "session_id": sid,
            "transcript_path": str(tp),
            "cwd": str(cwd),
            "hook_event_name": "Stop",
        }
    )
    subprocess.run(
        [sys.executable, str(HOOK)],
        input=payload,
        text=True,
        capture_output=True,
        timeout=180,
        env={"HOME": str(home), "PATH": "/usr/bin:/bin", "CLAUDE_MESH_HEADLESS": "1"},
    )
    return home / ".claude" / "state" / "threads" / f"{sid}.json"


def test_harvest_survives_a_drifted_cwd(tmp_path):
    """cwd points somewhere with NO scripts/final_gate.py (the observed post-compact
    shape). The eligibility early-return must not swallow the harvest: the hook derives
    its own repo from __file__ and still persists the NEXT line."""
    drifted = tmp_path / "nowhere"
    drifted.mkdir()
    reg = _run_stop(tmp_path, cwd=drifted, sid="probe-drift")
    assert reg.exists(), "harvest must run even when the payload cwd is not a fabrik repo"
    state = json.loads(reg.read_text(encoding="utf-8"))
    assert "probe thread — item 1 of 3" in state.get("last_next", {}).get("text", "")


def test_harvest_still_prefers_the_payload_repo(tmp_path):
    """The normal shape must keep working after the reorder (regression guard): a repo
    that carries its own thread_anchor.py is resolved from the payload cwd, fallback
    untouched. The repo is a stub so the test never pays for the hub's real gate."""
    fake = tmp_path / "repo" / "scripts"
    fake.mkdir(parents=True)
    (fake / "final_gate.py").write_text(
        'import json; print(json.dumps({"status": "success", "checks": []}))\n',
        encoding="utf-8",
    )
    (fake / "thread_anchor.py").write_text(
        (REPO / "scripts" / "thread_anchor.py").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    reg = _run_stop(tmp_path, cwd=fake.parent, sid="probe-normal")
    assert reg.exists()
    state = json.loads(reg.read_text(encoding="utf-8"))
    assert "probe thread — item 1 of 3" in state.get("last_next", {}).get("text", "")
