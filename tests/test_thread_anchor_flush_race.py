"""The harvest must survive the harness's transcript flush race.

Measured live 2026-08-29 (anchor_harvest telemetry, same session, 10 minutes apart): a
mid-turn Stop extracted 3749 chars; the turn-final Stop extracted 0 — while the 4KB final
message was on disk minutes later. The harness can fire the Stop hook BEFORE the final
assistant text entry is flushed, so at that moment the transcript tail ends in a
tool_use-only assistant entry whose text is empty. Two consequences fixed here, red-first:

1. Extractors must SKIP textless assistant entries instead of returning their empty join —
   the last flushed text is the best available message at Stop time.
2. The prompt-side hook (`line --hook`) must ALSO harvest from the payload's transcript —
   at prompt time the previous turn's final message is always flushed, so this pass is
   race-free by construction and catches everything the Stop-side one missed.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

_spec = importlib.util.spec_from_file_location("thread_anchor", REPO / "scripts" / "thread_anchor.py")
ta = importlib.util.module_from_spec(_spec)
sys.modules["thread_anchor"] = ta
_spec.loader.exec_module(ta)

_fspec = importlib.util.spec_from_file_location(
    "final_gate_stop", REPO / ".claude" / "hooks" / "final_gate_stop.py"
)
fgs = importlib.util.module_from_spec(_fspec)
sys.modules["final_gate_stop"] = fgs
_fspec.loader.exec_module(fgs)


def _race_transcript(tmp_path: Path) -> Path:
    """The measured Stop-time shape: final text entry followed by a tool_use-only
    assistant entry (the close call) and harness metadata lines."""
    tp = tmp_path / "transcript.jsonl"
    entries = [
        {"type": "user", "message": {"content": [{"type": "text", "text": "go"}]}},
        {
            "type": "assistant",
            "message": {
                "content": [
                    {"type": "text", "text": "closing.\nNEXT: probe race — item 2 of 9 — keep going"}
                ]
            },
        },
        {
            "type": "assistant",
            "message": {"content": [{"type": "tool_use", "id": "t1", "name": "Bash", "input": {}}]},
        },
        {"type": "last-prompt"},
        {"type": "mode"},
    ]
    tp.write_text("\n".join(json.dumps(e) for e in entries) + "\n", encoding="utf-8")
    return tp


def test_stop_hook_extractor_skips_textless_assistant_entries(tmp_path):
    tp = _race_transcript(tmp_path)
    text = fgs._final_message_text(str(tp))
    assert "NEXT: probe race — item 2 of 9" in text, (
        "a trailing tool_use-only entry must not blank the extraction"
    )


def test_prompt_side_line_hook_harvests_from_the_transcript(tmp_path):
    """`line --hook` receives the hook JSON (session_id + transcript_path) and must
    harvest the final message BEFORE printing — the race-free second pass."""
    tp = _race_transcript(tmp_path)
    home = tmp_path / "home"
    home.mkdir()
    payload = json.dumps({"session_id": "probe-race", "transcript_path": str(tp)})
    subprocess.run(
        [sys.executable, str(REPO / "scripts" / "thread_anchor.py"), "line", "--hook"],
        input=payload,
        text=True,
        capture_output=True,
        timeout=30,
        env={"HOME": str(home), "PATH": "/usr/bin:/bin"},
    )
    reg = home / ".claude" / "state" / "threads" / "probe-race.json"
    assert reg.exists(), "line --hook must harvest, not just print"
    state = json.loads(reg.read_text(encoding="utf-8"))
    assert "probe race — item 2 of 9" in state.get("last_next", {}).get("text", "")


def test_harvest_hook_uses_transcript_when_nothing_is_piped(tmp_path):
    """The --hook help has promised this since the flag shipped; the code must deliver it."""
    tp = _race_transcript(tmp_path)
    home = tmp_path / "home2"
    home.mkdir()
    payload = json.dumps({"session_id": "probe-race2", "transcript_path": str(tp)})
    subprocess.run(
        [sys.executable, str(REPO / "scripts" / "thread_anchor.py"), "harvest", "--hook"],
        input=payload,
        text=True,
        capture_output=True,
        timeout=30,
        env={"HOME": str(home), "PATH": "/usr/bin:/bin"},
    )
    reg = home / ".claude" / "state" / "threads" / "probe-race2.json"
    assert reg.exists()
    state = json.loads(reg.read_text(encoding="utf-8"))
    assert "probe race — item 2 of 9" in state.get("last_next", {}).get("text", "")
