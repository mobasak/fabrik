"""The Stop hook's coordinator cause (W-83021827, D-521): one `work.py queue --stop` line, acted on.

Every case drives the REAL hook (`main`) over a throwaway clean main checkout, so no earlier cause
can speak. The `work.py` call is stubbed by argv (`_COORD_ARGV`) with the JSON line it would print;
`work.py`'s own decisions are graded in tests/test_work_coordinator.py.
"""

from __future__ import annotations

import importlib.util
import io
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

_TREE = Path(__file__).resolve().parents[1]
_HOOK = _TREE / ".claude" / "hooks" / "final_gate_stop.py"


def _load(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


hook = _load("fgs_coordinator", _HOOK)
SID = "sid-coordinator"
CLAIM = {
    "agent": "w1",
    "role": "worker",
    "action": "claim",
    "fp": "claim:few",
    "text": "1 item(s) are queued for you (w1) — claim W-00000001",
}


def _line(obj: dict) -> tuple[str, ...]:
    """A `work.py queue --stop` stub printing `obj` (extra argv is ignored)."""
    return (sys.executable, "-c", f"print({json.dumps(json.dumps(obj))})")


@pytest.fixture(autouse=True)
def _isolated(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("CLAUDE_MESH_HEADLESS", raising=False)
    monkeypatch.delenv("CLAUDE_AGENT", raising=False)
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", "/dev/null")
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("THREAD_ANCHOR_DIR", str(tmp_path / "threads"))
    monkeypatch.setenv("COMMAND_RUN_DIR", str(tmp_path / "runs"))
    monkeypatch.setenv("KAIZEN_EVENTS_DIR", str(tmp_path / "events"))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("AGENT_IDENTITY_FILE", str(tmp_path / "identity.jsonl"))
    monkeypatch.setenv("FABRIK_MAIL_ROOT", str(tmp_path / "mail"))
    monkeypatch.setattr(hook.tempfile, "gettempdir", lambda: str(tmp_path))
    monkeypatch.setattr(hook, "_merge_owner_duty", lambda root, sid: None)
    monkeypatch.setattr(hook, "_coord_band", lambda transcript: None)
    monkeypatch.setattr(hook, "_COORD_ARGV", _line(CLAIM))


def _repo(tmp_path: Path) -> Path:
    main = tmp_path / "repo"
    subprocess.run(["git", "init", "-q", "-b", "master", str(main)], check=True, timeout=30)
    for cfg in (("user.email", "t@t"), ("user.name", "t"), ("commit.gpgsign", "false")):
        subprocess.run(["git", "-C", str(main), "config", *cfg], check=True, timeout=30)
    (main / "scripts").mkdir()
    (main / "scripts" / "final_gate.py").write_text("", encoding="utf-8")
    (main / ".gitignore").write_text(".fabrik/\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(main), "add", "-A"], check=True, timeout=30)
    subprocess.run(["git", "-C", str(main), "commit", "-qm", "base"], check=True, timeout=30)
    return main


def _drive(monkeypatch, cwd: Path, lam: str | None = None) -> tuple[dict | None, str]:
    payload: dict = {"cwd": str(cwd), "session_id": SID}
    if lam is not None:
        payload["last_assistant_message"] = lam
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    out, err = io.StringIO(), io.StringIO()
    monkeypatch.setattr(sys, "stdout", out)
    monkeypatch.setattr(sys, "stderr", err)
    assert hook.main([]) == 0
    text = out.getvalue().strip()
    return (json.loads(text) if text else None), err.getvalue()


def test_an_action_blocks_with_its_text_then_warns_through_once_and_stays_silent(
    monkeypatch, tmp_path
):
    main = _repo(tmp_path)
    for attempt in range(1, hook.CAP + 1):
        out, _ = _drive(monkeypatch, main)
        assert out is not None and out["decision"] == "block", attempt
        assert "W-00000001" in out["reason"] and f"attempt {attempt}/{hook.CAP}" in out["reason"]
    out, err = _drive(monkeypatch, main)
    assert out is None and "queued" in err, "the fourth Stop warns through"
    out, err = _drive(monkeypatch, main)
    assert out is None and err == "", "the same fingerprint stays silent after the warn-through"


def test_a_new_fingerprint_blocks_again_and_a_null_action_resets(monkeypatch, tmp_path):
    main = _repo(tmp_path)
    for _ in range(hook.CAP + 1):
        _drive(monkeypatch, main)
    monkeypatch.setattr(hook, "_COORD_ARGV", _line({**CLAIM, "fp": "claim:many"}))
    out, _ = _drive(monkeypatch, main)
    assert out is not None and "attempt 1/" in out["reason"]
    monkeypatch.setattr(hook, "_COORD_ARGV", _line({**CLAIM, "action": None, "fp": ""}))
    assert _drive(monkeypatch, main)[0] is None
    assert not hook._coord_state_path(SID).exists(), "a null action clears the state"
    monkeypatch.setattr(hook, "_COORD_ARGV", _line({**CLAIM, "fp": "claim:many"}))
    out, _ = _drive(monkeypatch, main)
    assert out is not None and "attempt 1/" in out["reason"]


@pytest.mark.parametrize(
    "lam",
    [
        "DECISION NEEDED (ground: gate)\n- Question: Deploy now?\n- Why it is yours: gate — Gate 2, "
        "a deploy.\n- Options: A — deploy · B — hold\n- Recommendation: A — certified.",
        "BLOCKED: the store — searched: work.py — missing: the item file\n\nSTATE: blocked\nNEXT: none",
    ],
)
def test_a_decision_or_blocked_ending_is_exempt(monkeypatch, tmp_path, lam):
    main = _repo(tmp_path)
    out, _ = _drive(monkeypatch, main, lam=lam)
    assert out is None


def test_a_red_band_or_a_running_record_is_exempt(monkeypatch, tmp_path):
    main = _repo(tmp_path)
    monkeypatch.setattr(hook, "_coord_band", lambda transcript: "RED")
    assert _drive(monkeypatch, main)[0] is None
    monkeypatch.setattr(hook, "_coord_band", lambda transcript: None)
    monkeypatch.setattr(hook, "_run_record", lambda sid: {"state": "running", "command": "x"})
    out, _ = _drive(monkeypatch, main)
    assert (
        out is None
        or "coordinator" not in out.get("reason", "").lower()
        and "W-00000001" not in out.get("reason", "")
    )


def test_the_cause_never_writes_the_seven_slot_counter(monkeypatch, tmp_path):
    main = _repo(tmp_path)
    out, _ = _drive(monkeypatch, main)
    assert out is not None
    counter = Path(hook._counter_path(SID))
    assert not counter.exists(), (
        "a clean repo's 7-slot counter is unlinked at the pass-through; the coordinator cause "
        f"must not recreate it: {counter.read_text() if counter.exists() else ''}"
    )
    assert hook._coord_state_path(SID).exists()


def test_a_failed_or_garbled_queue_call_is_silent(monkeypatch, tmp_path):
    main = _repo(tmp_path)
    monkeypatch.setattr(hook, "_COORD_ARGV", (sys.executable, "-c", "print('not json')"))
    assert _drive(monkeypatch, main)[0] is None
    monkeypatch.setattr(hook, "_COORD_ARGV", (sys.executable, "-c", "import sys; sys.exit(3)"))
    assert _drive(monkeypatch, main)[0] is None


def test_the_queue_call_runs_as_this_session(monkeypatch, tmp_path):
    main = _repo(tmp_path)
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "some-other-session")
    stub = (
        "import json, os; print(json.dumps({'action': 'claim', 'fp': 'claim:few', "
        "'text': 'as ' + os.environ.get('CLAUDE_CODE_SESSION_ID', '')}))"
    )
    monkeypatch.setattr(hook, "_COORD_ARGV", (sys.executable, "-c", stub))
    out, _ = _drive(monkeypatch, main)
    assert out is not None and f"as {SID}" in out["reason"], out


def test_a_corrupt_state_file_restarts_the_count_instead_of_crashing(tmp_path):
    hook._coord_state_path(SID).write_text('{"fp": "claim:few", "att": "oops"}', encoding="utf-8")
    duty = hook._coordinator_duty(tmp_path, SID, tmp_path)
    assert duty is not None and "attempt 1/" in duty[0]


def test_a_garbled_line_is_handled_inside_the_cause(monkeypatch, tmp_path):
    hook._coord_state_path(SID).write_text('{"fp": "claim:few", "att": 1}', encoding="utf-8")
    monkeypatch.setattr(hook, "_COORD_ARGV", (sys.executable, "-c", "print('not json')"))
    assert hook._coordinator_duty(tmp_path, SID, tmp_path) is None
    assert not hook._coord_state_path(SID).exists(), "a garbled line clears the state like a null"
