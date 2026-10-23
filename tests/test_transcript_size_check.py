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


# --- W-f975fee0 slice 1 (D-1119, D-1123): the CONTEXT sensor — ROTATE-DUE / COMPACT-DUE, stamped per step ---


def _usage(inp=0, create=0, read=0, *, model="claude-opus-5-5", sidechain=False):
    usage = {
        "input_tokens": inp,
        "cache_creation_input_tokens": create,
        "cache_read_input_tokens": read,
    }
    return {
        "type": "assistant",
        "isSidechain": sidechain,
        "message": {"model": model, "usage": usage},
    }


def _transcript(path: Path, rows: list[dict], *, pad_mb: int = 0) -> None:
    """A transcript whose LAST rows are `rows`; `pad_mb` of junk first makes its leading line split by the tail read."""
    with path.open("wb") as fh:
        if pad_mb:
            fh.write(b"x" * (pad_mb * MB) + b"\n")
        for r in rows:
            fh.write(json.dumps(r).encode() + b"\n")


@pytest.fixture
def ctxbox(box, tmp_path, monkeypatch):
    transcript, stamps = box
    cache = tmp_path / "statusline.json"
    cache.write_text(json.dumps({"sessions": {"sid-1": {"model": {"id": "claude-opus-5-5[1m]"}}}}))
    monkeypatch.setenv("STATUSLINE_CACHE_FILE", str(cache))
    monkeypatch.delenv("ROTATE_CONTEXT_WINDOW", raising=False)
    return transcript, stamps, cache


def _ctx(transcript, rows, monkeypatch, capsys, **kw):
    _transcript(transcript, rows, **kw)
    return _run({"session_id": "sid-1", "transcript_path": str(transcript)}, monkeypatch, capsys)


def test_ctx_line_at_forty_percent_names_the_boundary_and_the_coordinator(
    ctxbox, monkeypatch, capsys
):
    transcript, _, _ = ctxbox
    rc, out = _ctx(
        transcript, [_usage(2, 1_000, 409_000)], monkeypatch, capsys
    )  # 410,002 of 1M, a tiny file
    lines = out.splitlines()
    assert rc == 0 and len(lines) == 1, out
    line = lines[0]
    assert line.startswith(
        "ROTATE-DUE at your next item boundary: ctx 41% (410k of 1000k tokens)"
    ), line
    assert "start no new item" in line and "message your coordinator `rotate fleet`" in line
    assert "no run record running, no seat in flight, the worktree clean" in line
    assert "`NEXT: none — terminal; awaiting the rotation`" in line
    assert "COMPACT-DUE" not in line and "ROTATE:" not in line
    _rc, out = _ctx(
        transcript, [_usage(0, 0, 399_999)], monkeypatch, capsys
    )  # 39.99% floors below the line
    assert out == ""


def test_ctx_stamp_prints_once_per_step_and_rearms_after_a_drop(ctxbox, monkeypatch, capsys):
    transcript, stamps, _ = ctxbox

    def at(pct):
        return _ctx(transcript, [_usage(0, 0, pct * 10_000)], monkeypatch, capsys)[1]

    assert at(70) != "" and at(72) == "" and at(79) == ""  # one line per step
    assert at(80) != ""
    assert at(8) == ""  # a compaction: a sub-40 reading re-arms silently
    assert (stamps / ".ctx" / "sid-1").read_text().strip() == "0"
    assert "ctx 41%" in at(41)  # the 40 line is told again after the drop
    assert at(90) != "" and "ctx 45%" in at(45)  # a drop that lands at 40+ is told once
    assert at(45) == "" and at(48) == ""


def test_ctx_line_at_eighty_five_percent_is_compact_due(ctxbox, monkeypatch, capsys):
    transcript, _, _ = ctxbox
    _rc, out = _ctx(transcript, [_usage(0, 0, 870_000)], monkeypatch, capsys)
    assert out.startswith("COMPACT-DUE mid-item: ctx 87% (870k of 1000k tokens)"), out
    assert "message your coordinator `compact fleet <one-line focus on the item in hand>`" in out
    assert "if you are at an item boundary now, `rotate fleet` instead" in out
    assert (
        _ctx(transcript, [_usage(0, 0, 890_000)], monkeypatch, capsys)[1] == ""
    )  # 85-89 is one step
    assert _ctx(transcript, [_usage(0, 0, 900_000)], monkeypatch, capsys)[1].startswith(
        "COMPACT-DUE"
    )


def test_ctx_reading_skips_compaction_sidechains_and_bad_rows(ctxbox, monkeypatch, capsys):
    transcript, _, _ = ctxbox
    good = _usage(0, 0, 600_000)
    compact = {"type": "system", "subtype": "compact_boundary"}
    cases = [
        [good, compact],  # a compaction after the reading: stale-high, no line
        [_usage(0, 0, 600_000, sidechain=True)],  # sidechain only
        [_usage(0, 0, 600_000, model="<synthetic>")],
        [_usage(0, 0, 0)],
        [{"type": "assistant", "message": "not a dict"}],
        [{"type": "assistant", "isSidechain": False, "message": {"usage": "nope"}}],
    ]
    for rows in cases:
        assert _ctx(transcript, rows, monkeypatch, capsys)[1] == "", rows
    # a bool or a string field skips THAT row, and the reading falls back to the row before it
    out = _ctx(transcript, [good, _usage(0, 0, True), _usage("5", 0, 0)], monkeypatch, capsys)[1]
    assert "ctx 60%" in out, out
    # a missing cache key reads 0, a non-JSON line is skipped, the split first line of the 2 MB tail is dropped
    row = {"type": "assistant", "message": {"usage": {"cache_read_input_tokens": 500_000}}}
    _transcript(transcript, [], pad_mb=3)
    with transcript.open("ab") as fh:
        fh.write(b"{not json\n" + json.dumps(row).encode() + b"\n")
    _rc, out = _run(
        {"session_id": "sid-1", "transcript_path": str(transcript)}, monkeypatch, capsys
    )
    assert "ctx 50%" in out and "ROTATE:" not in out, out  # 3 MB: under the MB threshold


def test_ctx_line_for_a_coordinator_and_for_an_unbound_window(
    ctxbox, tmp_path, monkeypatch, capsys
):
    transcript, _, _ = ctxbox
    monkeypatch.setenv("CLAUDE_AGENT", "coordinator")
    out = _ctx(transcript, [_usage(0, 0, 500_000)], monkeypatch, capsys)[1]
    assert (
        "tell the operator once" in out
        and "/clear coordinator-" in out
        and "message your coordinator" not in out
    )
    monkeypatch.setenv("CLAUDE_AGENT", "fabrik-lib-coordinator")
    out = _ctx(transcript, [_usage(0, 0, 870_000)], monkeypatch, capsys)[1]
    assert "tell the operator once" in out and "/compact <" in out
    monkeypatch.delenv("CLAUDE_AGENT")
    Path(os.environ["AGENT_IDENTITY_FILE"]).write_text("")
    monkeypatch.setenv("ROTATE_STAMP_DIR", str(tmp_path / "fresh-stamps"))
    out = _ctx(transcript, [_usage(0, 0, 600_000)], monkeypatch, capsys)[1]
    assert (
        "yourself" in out
        and "this window has no bound agent" in out
        and "message your coordinator" not in out
    )
    monkeypatch.setenv("CLAUDE_AGENT", "fleet")
    monkeypatch.setenv("ROTATE_STAMP_DIR", str(tmp_path / "fresh-stamps-2"))
    out = _ctx(transcript, [_usage(0, 0, 600_000)], monkeypatch, capsys)[1]
    assert "a repo's only agent: tell the operator once instead" in out


def test_mb_line_names_the_boundary_and_the_actor(box, monkeypatch, capsys):
    transcript, _ = box
    _grow(transcript, 210)
    out = _run({"session_id": "sid-1", "transcript_path": str(transcript)}, monkeypatch, capsys)[1]
    assert out.startswith(
        "ROTATE: this session's transcript is 210 MB — at your next item boundary"
    ), out
    assert (
        "message your coordinator `rotate fleet`" in out
        and "/clear fleet-" in out
        and "--as fleet --force" in out
    )
    assert "and one resume prompt; a coordinator tells the operator" in out
    assert "now, then" not in out


def test_ctx_window_env_cache_and_fallback(ctxbox, tmp_path, monkeypatch, capsys):
    transcript, _, cache = ctxbox
    rows = [_usage(0, 0, 90_000)]  # 90k: 45% of a 200k window, 9% of 1M

    def fresh(name):
        monkeypatch.setenv("ROTATE_STAMP_DIR", str(tmp_path / name))

    fresh("a")  # the tap's top-level size, for the same model id, is the window (W-25f6b2a3)
    cache.write_text(
        json.dumps(
            {
                "model": {"id": "claude-haiku-5-5"},
                "context": {"usedPercent": 3, "size": 200_000},
                "sessions": {"sid-1": {"model": {"id": "claude-haiku-5-5"}}},
            }
        )
    )
    assert "ctx 45% (90k of 200k tokens)" in _ctx(transcript, rows, monkeypatch, capsys)[1]
    for top in (
        {"model": {"id": "claude-opus-5-5"}, "context": {"size": 200_000}},  # another model's size
        {"model": {"id": "claude-haiku-5-5"}, "context": {"size": "200000"}},  # not an int
        {"model": {"id": "claude-haiku-5-5"}, "context": {"size": True}},  # a bool is not a size
        {"model": {"id": "claude-haiku-5-5"}, "context": {"size": 0}},
        {"model": {"id": "claude-haiku-5-5"}, "context": None},
        {"model": "claude-haiku-5-5", "context": {"size": 200_000}},
    ):
        fresh(f"a{len(json.dumps(top))}")
        cache.write_text(json.dumps(dict(top, sessions={"sid-1": {"model": {"id": "claude-haiku-5-5"}}})))
        assert _ctx(transcript, rows, monkeypatch, capsys)[1] == "", top  # no usable size: 1M
    fresh("b")
    cache.write_text(json.dumps({"sessions": {"sid-1": {"model": {"id": "claude-opus-5-5[1m]"}}}}))
    assert _ctx(transcript, rows, monkeypatch, capsys)[1] == ""
    fresh("c")
    cache.write_text("{broken")
    assert _ctx(transcript, rows, monkeypatch, capsys)[1] == ""  # no readable cache: 1M
    fresh("d")
    monkeypatch.setenv("ROTATE_CONTEXT_WINDOW", "200000")
    assert "of 200k tokens" in _ctx(transcript, rows, monkeypatch, capsys)[1]
    cache.write_text(json.dumps({"sessions": {"sid-1": {"model": {"id": "claude-opus-5-5[1m]"}}}}))
    for junk in ("0", "-5", "abc", ""):
        fresh(f"e{junk or 'empty'}")
        monkeypatch.setenv("ROTATE_CONTEXT_WINDOW", junk)
        assert _ctx(transcript, rows, monkeypatch, capsys)[1] == "", (
            junk
        )  # junk falls through to the cache's 1M
    fresh("f")
    monkeypatch.delenv("ROTATE_CONTEXT_WINDOW")
    env = tmp_path / "hub.env"
    env.write_text("ROTATE_CONTEXT_WINDOW=200000\n")
    monkeypatch.setenv("SESSION_ARCHIVE_ENV_FILE", str(env))
    assert "of 200k tokens" in _ctx(transcript, rows, monkeypatch, capsys)[1]


def test_ctx_edges_the_review_found(ctxbox, tmp_path, monkeypatch, capsys):
    """Round 1 of the W-f975fee0 review: each case below survived a mutant."""
    transcript, stamps, cache = ctxbox
    good = _usage(0, 0, 500_000)

    def fresh(name):
        monkeypatch.setenv("ROTATE_STAMP_DIR", str(tmp_path / name))

    # a negative field skips the row; a zero row after a good row leaves the good reading
    fresh("neg")
    assert "ctx 50%" in _ctx(transcript, [good, _usage(-1, 0, 0)], monkeypatch, capsys)[1]
    fresh("zero")
    assert "ctx 50%" in _ctx(transcript, [good, _usage(0, 0, 0)], monkeypatch, capsys)[1]
    # 100 is its own step after a stamped 90, and a reading past the window stays on it
    fresh("hundred")
    assert _ctx(transcript, [_usage(0, 0, 900_000)], monkeypatch, capsys)[1] != ""
    assert "ctx 100%" in _ctx(transcript, [_usage(0, 0, 1_000_000)], monkeypatch, capsys)[1]
    assert _ctx(transcript, [_usage(0, 0, 1_200_000)], monkeypatch, capsys)[1] == ""
    # the split first line of the 2 MB tail is DROPPED even when its fragment parses as a usage row: the cut lands
    # exactly at the start of a valid 90% row glued to a prefix, and that row is the file's only usage row
    fresh("split")
    row90 = json.dumps(_usage(0, 0, 900_000)).encode()
    head = b'{"type":"user","t":"'
    fill = tsc.TAIL_BYTES - len(row90) - 1 - len(head) - len(b'"}')
    user = head + b"a" * fill + b'"}'
    transcript.write_bytes(b"z" * (3 * MB) + b"PREFIX" + row90 + b"\n" + user)
    assert transcript.read_bytes()[-tsc.TAIL_BYTES :].startswith(
        row90
    )  # the tail starts inside that line
    assert (
        _run({"session_id": "sid-1", "transcript_path": str(transcript)}, monkeypatch, capsys)[1]
        == ""
    )
    # a deeply nested line skips itself, never the check
    fresh("deep")
    _transcript(transcript, [good])
    with transcript.open("ab") as fh:
        fh.write(b"[" * 100_000 + b"\n")
    assert (
        "ctx 50%"
        in _run({"session_id": "sid-1", "transcript_path": str(transcript)}, monkeypatch, capsys)[1]
    )
    # a stale cache row naming a 200k model cannot hold a reading past 200k: the window is 1M
    fresh("stale")
    cache.write_text(json.dumps({"sessions": {"sid-1": {"model": {"id": "claude-opus-5-5"}}}}))
    assert (
        "ctx 45% (450k of 1000k tokens)"
        in _ctx(transcript, [_usage(0, 0, 450_000)], monkeypatch, capsys)[1]
    )
    # a session id that looks like the stamp dir cannot collide with it
    assert not tsc._SID_RE.fullmatch(".ctx")


def test_ctx_unwritable_stamp_dir_still_tells_and_mb_line_comes_first(
    ctxbox, tmp_path, monkeypatch, capsys
):
    transcript, _, _ = ctxbox
    blocker = tmp_path / "not-a-dir"
    blocker.write_text("")
    monkeypatch.setenv("ROTATE_STAMP_DIR", str(blocker))  # mkdir of <file>/.ctx fails
    out = _ctx(transcript, [_usage(0, 0, 500_000)], monkeypatch, capsys)[1]
    assert out.startswith("ROTATE-DUE"), out  # the advice repeats rather than going silent
    assert tsc._claim_ctx_step(blocker, "sid-1", 0) is False
    # both checks firing: the MB line first, then the context line
    monkeypatch.setenv("ROTATE_STAMP_DIR", str(tmp_path / "both"))
    _transcript(transcript, [_usage(0, 0, 500_000)], pad_mb=210)
    lines = _run({"session_id": "sid-1", "transcript_path": str(transcript)}, monkeypatch, capsys)[
        1
    ].splitlines()
    assert (
        len(lines) == 2 and lines[0].startswith("ROTATE: ") and lines[1].startswith("ROTATE-DUE")
    ), lines


def test_ctx_tail_cut_on_a_line_start_and_a_failing_lock(ctxbox, tmp_path, monkeypatch, capsys):
    """Round 2 of the W-f975fee0 review: a cut landing exactly on a row start keeps that row; a stamp lock that
    cannot be opened still tells a non-zero step (the advice repeats rather than going silent)."""
    transcript, _, _ = ctxbox
    row = json.dumps(_usage(0, 0, 900_000)).encode()
    pad = tsc.TAIL_BYTES - len(row) - 1
    tail = row + b"\n" + b" " * pad  # whitespace-only last line: no other usage row
    transcript.write_bytes(b"z" * (3 * MB) + b"\n" + tail)
    assert transcript.read_bytes()[-tsc.TAIL_BYTES :].startswith(row)
    out = _run({"session_id": "sid-1", "transcript_path": str(transcript)}, monkeypatch, capsys)[1]
    assert "ctx 90%" in out, out
    locked = tmp_path / "locked"
    (locked / ".lock").mkdir(parents=True)  # opening a directory for append raises
    assert tsc._claim_ctx_step(locked, "sid-1", 50) is True
    assert tsc._claim_ctx_step(locked, "sid-1", 0) is False


def test_ctx_a_bare_model_id_is_not_a_200k_window(ctxbox, monkeypatch, capsys):
    """W-25f6b2a3: this box runs claude-opus-5-5 and claude-fable-5-1 at 1M under the bare id (32 of 153 and 8 of 8
    transcripts read past 200k with no compaction), so a bare id in the statusline cache is no evidence of 200k: this
    session's own second reading, 126k, read `ctx 63% (126k of 200k tokens)` and ordered a rotation at birth."""
    transcript, _, cache = ctxbox
    cache.write_text(json.dumps({"sessions": {"sid-1": {"model": {"id": "claude-opus-5-5"}}}}))
    born = [_usage(2, 90_726, 29_885), _usage(0, 0, 126_000)]
    assert _ctx(transcript, born, monkeypatch, capsys)[1] == ""
    # the tap's live record for the same id names the real window, and the 40% line is where D-1123 put it
    cache.write_text(
        json.dumps(
            {
                "model": {"id": "claude-opus-5-5"},
                "context": {"usedPercent": 27, "size": 1_000_000},
                "sessions": {"sid-1": {"model": {"id": "claude-opus-5-5"}}},
            }
        )
    )
    assert _ctx(transcript, [_usage(0, 0, 399_999)], monkeypatch, capsys)[1] == ""
    assert "ctx 40% (400k of 1000k tokens)" in _ctx(transcript, [_usage(0, 0, 400_000)], monkeypatch, capsys)[1]
