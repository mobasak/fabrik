"""Behavior Contract — C.1.3 of the session-history retention plan (D-736, D-737).

`scripts/sysadmin/transcript_size_check.py` is a USER-level `UserPromptSubmit` hook: it reads the
hook JSON, stats the transcript and prints ONE `ROTATE:` line when the file has crossed a new
100 MB step at or above `ROTATE_ADVISE_MB`. It is fail-open (any error ⇒ exit 0, no output) and
STAMPED — the per-prompt shape was measured and rejected as wallpaper (`install_user_hooks.py`,
D-184/D-187), so the same step never prints twice for one session.
"""

from __future__ import annotations

import importlib.util
import io
import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "sysadmin" / "transcript_size_check.py"

spec = importlib.util.spec_from_file_location("transcript_size_check", SCRIPT)
tsc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tsc)

MB = 1024 * 1024


@pytest.fixture
def box(tmp_path, monkeypatch):
    """A fake transcript, a fake identity file and registry, a stamp dir, the threshold at 200."""
    transcript = tmp_path / "projects" / "-opt-x" / "sid-1.jsonl"
    transcript.parent.mkdir(parents=True)
    stamps = tmp_path / "state" / "rotate-advised"
    identity = tmp_path / "state" / "agent-identity.jsonl"
    identity.parent.mkdir(parents=True, exist_ok=True)
    identity.write_text(
        json.dumps({"session_id": "sid-1", "name": "fleet", "pid": 4242, "pid_start": 99, "at": 1})
        + "\n"
    )
    monkeypatch.setenv("ROTATE_ADVISE_MB", "200")
    monkeypatch.setenv("ROTATE_STAMP_DIR", str(stamps))
    monkeypatch.setenv("AGENT_IDENTITY_FILE", str(identity))
    monkeypatch.setenv("CLAUDE_SESSIONS_DIR", str(tmp_path / "sessions"))
    monkeypatch.delenv("CLAUDE_AGENT", raising=False)
    monkeypatch.setenv("SESSION_ARCHIVE_ENV_FILE", str(tmp_path / "no-such.env"))
    monkeypatch.setattr(tsc, "_session_pid", lambda: 4242)
    return transcript, stamps


def _run(payload: dict, monkeypatch, capsys) -> tuple[int, str]:
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))
    rc = tsc.main()
    return rc, capsys.readouterr().out


def _grow(path: Path, mb: int) -> None:
    with path.open("wb") as fh:
        fh.truncate(mb * MB)


def test_below_the_threshold_prints_nothing(box, monkeypatch, capsys):
    transcript, _ = box
    _grow(transcript, 150)
    rc, out = _run({"session_id": "sid-1", "transcript_path": str(transcript)}, monkeypatch, capsys)
    assert rc == 0 and out == ""


def test_at_the_threshold_prints_one_rotate_line_naming_size_clear_rebind_and_pid(
    box, monkeypatch, capsys
):
    transcript, _ = box
    _grow(transcript, 201)
    rc, out = _run({"session_id": "sid-1", "transcript_path": str(transcript)}, monkeypatch, capsys)
    assert rc == 0
    lines = [line for line in out.splitlines() if line.strip()]
    assert len(lines) == 1 and lines[0].startswith("ROTATE:"), out
    line = lines[0]
    assert "201 MB" in line
    assert "/clear fleet-" in line  # the agent name from the identity row, dated
    assert "whoami_agent.py --as fleet --force" in line
    assert "pid 4242" in line  # the holder is this window's own claude process


def test_the_same_step_never_prints_twice_but_a_new_step_does(box, monkeypatch, capsys):
    transcript, stamps = box
    _grow(transcript, 210)
    payload = {"session_id": "sid-1", "transcript_path": str(transcript)}
    rc, first = _run(payload, monkeypatch, capsys)
    assert first.startswith("ROTATE:")
    assert (stamps / "sid-1").read_text().strip() == "200"
    _grow(transcript, 260)
    rc, again = _run(payload, monkeypatch, capsys)
    assert again == "", "the 200 step was already advised for this session"
    _grow(transcript, 305)
    rc, third = _run(payload, monkeypatch, capsys)
    assert third.startswith("ROTATE:") and "305 MB" in third
    assert (stamps / "sid-1").read_text().strip() == "300"


def test_fail_open_on_a_missing_path_bad_json_or_unwritable_stamp(box, monkeypatch, capsys):
    transcript, stamps = box
    rc, out = _run(
        {"session_id": "sid-1", "transcript_path": str(transcript) + ".nope"}, monkeypatch, capsys
    )
    assert rc == 0 and out == ""
    monkeypatch.setattr("sys.stdin", io.StringIO("not json"))
    assert tsc.main() == 0 and capsys.readouterr().out == ""
    _grow(transcript, 250)
    stamps.parent.mkdir(parents=True, exist_ok=True)
    stamps.write_text("a file where the dir should be")  # the stamp dir cannot be created
    rc, out = _run({"session_id": "sid-1", "transcript_path": str(transcript)}, monkeypatch, capsys)
    assert rc == 0  # an unwritable stamp still prints the advice once, never a traceback
    assert out.startswith("ROTATE:")


def test_without_an_identity_row_the_agent_comes_from_the_registry_join_else_a_placeholder(
    box, monkeypatch, capsys, tmp_path
):
    transcript, _ = box
    _grow(transcript, 250)
    # a /clear'd window: new session id, no identity row, but the registry carries the new id
    # under the SAME pid+procStart as the identity row for the old id
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    (sessions / "4242.json").write_text(
        json.dumps({"pid": 4242, "sessionId": "sid-2", "procStart": "99"})
    )
    rc, out = _run({"session_id": "sid-2", "transcript_path": str(transcript)}, monkeypatch, capsys)
    assert "/clear fleet-" in out and "--as fleet --force" in out
    # neither: the line still prints, with the placeholder the operator fills in
    (sessions / "4242.json").write_text(
        json.dumps({"pid": 4242, "sessionId": "sid-3", "procStart": "77"})
    )
    rc, out = _run({"session_id": "sid-9", "transcript_path": str(transcript)}, monkeypatch, capsys)
    assert out.startswith("ROTATE:") and "/clear <agent>-" in out


def test_the_threshold_is_read_from_the_env_file_when_the_process_env_lacks_it(
    box, monkeypatch, capsys, tmp_path
):
    transcript, _ = box
    monkeypatch.delenv("ROTATE_ADVISE_MB")
    env_file = tmp_path / "hub.env"
    env_file.write_text("SESSION_ARCHIVE_B2_BUCKET=x\nROTATE_ADVISE_MB=50  # small for the test\n")
    monkeypatch.setenv("SESSION_ARCHIVE_ENV_FILE", str(env_file))
    _grow(transcript, 60)
    rc, out = _run({"session_id": "sid-1", "transcript_path": str(transcript)}, monkeypatch, capsys)
    assert out.startswith("ROTATE:") and "60 MB" in out
