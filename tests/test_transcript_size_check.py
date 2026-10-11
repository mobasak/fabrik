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
import os
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


# ── review round 1 (2026-10-11) regression guards ─────────────────────────────────────────────


def test_env_file_quoted_value_with_trailing_comment_and_export_prefix_parse_like_the_archiver(
    box, monkeypatch, capsys, tmp_path
):
    """hook-S1/H1 + wiring-docs-H4: `ROTATE_ADVISE_MB="50" # note` read 200 (the stray quote
    broke int()); `export ROTATE_ADVISE_MB=…` is in the regex but was never exercised."""
    transcript, _ = box
    monkeypatch.delenv("ROTATE_ADVISE_MB")
    env_file = tmp_path / "hub.env"
    monkeypatch.setenv("SESSION_ARCHIVE_ENV_FILE", str(env_file))
    for body in (
        'ROTATE_ADVISE_MB="50" # small\n',
        "export ROTATE_ADVISE_MB='50'\r\n",
        "ROTATE_ADVISE_MB=50\n",
    ):
        env_file.write_text(body)
        assert tsc._threshold_mb() == 50, body
    env_file.write_text("ROTATE_ADVISE_MB=abc\n")
    assert tsc._threshold_mb() == tsc.DEFAULT_THRESHOLD_MB
    env_file.write_text("ROTATE_ADVISE_MB=50\nROTATE_ADVISE_MB=70\n")
    assert tsc._threshold_mb() == 70  # the last line wins, as dotenv does


def test_the_real_proc_walk_finds_the_claude_ancestor_and_stops_at_init(tmp_path, monkeypatch):
    """hook-S3: every other test mocks `_session_pid`; this one runs the walk over a fake proc
    tree — self → bash → claude (found), and self → bash → init (None)."""
    proc = tmp_path / "proc"
    me = os.getpid()

    def status(pid: int, name: str, ppid: int) -> None:
        (proc / str(pid)).mkdir(parents=True)
        (proc / str(pid) / "status").write_text(f"Name:\t{name}\nUmask:\t0022\nPPid:\t{ppid}\n")

    status(me, "python3", 5000)
    status(5000, "bash", 4000)
    status(4000, "claude", 1)
    assert tsc._session_pid(proc_root=proc) == 4000
    (proc / "4000" / "status").write_text("Name:\tnode\nPPid:\t1\n")
    assert tsc._session_pid(proc_root=proc) is None
    assert tsc._session_pid(proc_root=tmp_path / "absent") is None  # no tree: None, never a raise


def test_an_ambiguous_registry_join_tags_nothing(box, monkeypatch, capsys, tmp_path):
    """hook-S4: two registry entries for one session id joining to DIFFERENT agents — a stale
    file beside a live one — must not pick whichever globs first."""
    transcript, _ = box
    _grow(transcript, 250)
    identity = Path(os.environ["AGENT_IDENTITY_FILE"])
    identity.write_text(
        json.dumps({"session_id": "old-a", "name": "alpha", "pid": 1111, "pid_start": 10, "at": 1})
        + "\n"
        + json.dumps({"session_id": "old-b", "name": "beta", "pid": 2222, "pid_start": 20, "at": 2})
        + "\n"
    )
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    (sessions / "1111.json").write_text(
        json.dumps({"pid": 1111, "sessionId": "sid-x", "procStart": "10"})
    )
    (sessions / "2222.json").write_text(
        json.dumps({"pid": 2222, "sessionId": "sid-x", "procStart": "20"})
    )
    assert tsc._agent_name("sid-x") == ""
    rc, out = _run({"session_id": "sid-x", "transcript_path": str(transcript)}, monkeypatch, capsys)
    assert out.startswith("ROTATE:") and "/clear <agent>-" in out
    # the same two entries agreeing on one name is NOT ambiguous
    (sessions / "2222.json").write_text(
        json.dumps({"pid": 1111, "sessionId": "sid-y", "procStart": "10"})
    )
    (sessions / "1111.json").write_text(
        json.dumps({"pid": 1111, "sessionId": "sid-y", "procStart": "10"})
    )
    assert tsc._agent_name("sid-y") == "alpha"


def test_dot_and_dotdot_and_separator_session_ids_are_refused_before_any_stamp_path(
    box, monkeypatch, capsys
):
    """hook-S5: `..` resolved the stamp to the dir's parent; `/` was already refused."""
    transcript, stamps = box
    _grow(transcript, 250)
    for bad in (".", "..", "a/b", "", "../x"):
        rc, out = _run({"session_id": bad, "transcript_path": str(transcript)}, monkeypatch, capsys)
        assert rc == 0 and out == "", bad
    assert not stamps.exists() or not any(stamps.iterdir())


def test_two_concurrent_prompts_of_one_session_print_one_line_for_one_step(
    box, monkeypatch, tmp_path
):
    """hook-S2/wiring-docs-H2: the stamp's read-compare-write is under an flock — of N racing
    claims for the same step exactly one wins."""
    import threading

    transcript, stamps = box
    _grow(transcript, 250)
    wins = []
    barrier = threading.Barrier(8)

    def claim():
        barrier.wait()
        wins.append(tsc._claim_step(stamps, "sid-1", 200))

    threads = [threading.Thread(target=claim) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert wins.count(True) == 1 and wins.count(False) == 7
    assert (stamps / "sid-1").read_text().strip() == "200"
