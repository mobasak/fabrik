"""Behaviour tests for the kaizen M1 event emitter (T01).

The three laws under test, each with a failure injected rather than assumed:

1. **Fail-open** — a raising emitter must never raise into its caller and must never
   leave a torn half-line behind. A session that cannot be measured still runs.
2. **One atomic append per event** — a single ``O_APPEND`` ``write()`` of a whole line
   to a regular file cannot interleave with another writer's; a torn line would become
   the unclassified-rate that red-instruments the loop. Proven here with real processes
   appending to ONE file, not threads sharing one interpreter.
3. **Honesty** — an unresolvable session is the literal ``unknown`` (never merged into
   a neighbour's stream), and an unmeasurable exposure field is ``unknown``/``—``,
   never a guess and never an exception.
"""

from __future__ import annotations

import json
import multiprocessing
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
MODULE = REPO / "scripts" / "sysadmin" / "kaizen_events.py"
sys.path.insert(0, str(REPO / "scripts" / "sysadmin"))

import kaizen_events  # noqa: E402


@pytest.fixture(autouse=True)
def _isolated_events_dir(tmp_path, monkeypatch):
    """Every test writes into its own events dir and never the operator's real one."""
    d = tmp_path / "events"
    monkeypatch.setenv("KAIZEN_EVENTS_DIR", str(d))
    monkeypatch.delenv("CLAUDE_SESSION_ID", raising=False)
    kaizen_events.reset_cache()
    yield d
    kaizen_events.reset_cache()


def _lines(path: Path) -> list[dict]:
    return [json.loads(ln) for ln in path.read_text().splitlines() if ln.strip()]


# ── the emitted line ─────────────────────────────────────────────────────────────────


def test_emit_writes_one_parseable_json_line(_isolated_events_dir):
    assert kaizen_events.emit("session_start", sid="abc123", project="fabrik") is True

    rows = _lines(_isolated_events_dir / "abc123.jsonl")
    assert len(rows) == 1
    row = rows[0]
    assert row["schema"] == kaizen_events.SCHEMA
    assert row["event"] == "session_start"
    assert row["sid"] == "abc123"
    assert row["sid_source"] == "explicit"
    assert row["project"] == "fabrik"
    assert isinstance(row["ts"], str) and row["ts"].startswith("20")
    # exposure rides EVERY event — attribution is impossible after the fact
    for key in ("commit", "account", "model", "project", "headless", "plan_era"):
        assert key in row["exposure"], key


def test_emit_appends_never_truncates(_isolated_events_dir):
    for i in range(3):
        assert kaizen_events.emit("phase", sid="s1", n=i) is True
    rows = _lines(_isolated_events_dir / "s1.jsonl")
    assert [r["n"] for r in rows] == [0, 1, 2]


def test_two_sids_write_two_files(_isolated_events_dir):
    """Per-session files are the anti-tearing design, not a nicety."""
    kaizen_events.emit("session_start", sid="alpha")
    kaizen_events.emit("session_start", sid="beta")

    names = sorted(p.name for p in _isolated_events_dir.glob("*.jsonl"))
    assert names == ["alpha.jsonl", "beta.jsonl"]
    assert len(_lines(_isolated_events_dir / "alpha.jsonl")) == 1
    assert len(_lines(_isolated_events_dir / "beta.jsonl")) == 1


def test_line_never_exceeds_pipe_buf(_isolated_events_dir):
    """MAX_LINE_BYTES is the defensive bound on one event — no payload, however large,
    may push a line past it (the atomicity itself comes from O_APPEND, not the size)."""
    kaizen_events.emit(
        "gate_run",
        sid="s1",
        checks=[{"name": f"check_{i}_" + "x" * 60, "outcome": "pass"} for i in range(200)],
        note="y" * 20000,
    )
    raw = (_isolated_events_dir / "s1.jsonl").read_bytes()
    assert raw.endswith(b"\n")
    assert len(raw) <= kaizen_events.MAX_LINE_BYTES


def test_oversize_field_is_truncated_and_line_still_parses(_isolated_events_dir):
    """Values are clipped BEFORE serialization — the line is always valid JSON."""
    kaizen_events.emit("round", sid="s1", note="z" * 50000)

    row = _lines(_isolated_events_dir / "s1.jsonl")[0]
    assert row["truncated"] is True
    assert row["event"] == "round"
    assert len(row["note"]) < 50000
    assert row["note"].startswith("z")


def test_unfittable_payload_falls_back_to_a_labelled_envelope(_isolated_events_dir):
    """Clipping VALUES cannot save a payload with hundreds of long KEYS — the envelope
    (with its real exposure) still lands, honestly labelled, inside PIPE_BUF."""
    fields = {f"key{i}_" + "k" * 50: i for i in range(500)}
    assert kaizen_events.emit("gate_run", sid="s1", **fields) is True

    raw = (_isolated_events_dir / "s1.jsonl").read_bytes()
    assert len(raw) <= kaizen_events.MAX_LINE_BYTES
    row = json.loads(raw)
    assert row["event"] == "gate_run"
    assert row["truncated"] is True
    assert row["fields_dropped"] is True
    assert isinstance(row["exposure"], dict)  # exposure is kept REAL, never fabricated


def test_caller_field_cannot_shadow_the_envelope(_isolated_events_dir):
    """A caller passing schema=/ts=/exposure=/truncated= must not be able to forge the
    envelope the collector trusts (`event`/`sid` are positional, so they cannot even be
    sent). `truncated`/`fields_dropped` are envelope-owned too, even though the emitter
    adds them AFTER the caller's fields are merged — a sensor claiming `truncated: false`
    on a clipped line would make the instrument lie about itself."""
    kaizen_events.emit(
        "death",
        sid="s1",
        schema=99,
        ts="1999-01-01",
        exposure={"commit": "forged"},
        truncated=False,
        fields_dropped=False,
    )

    row = _lines(_isolated_events_dir / "s1.jsonl")[0]
    assert row["schema"] == kaizen_events.SCHEMA
    assert row["event"] == "death"
    assert not row["ts"].startswith("1999")
    assert row["exposure"]["commit"] != "forged"
    assert "truncated" not in row  # nothing was clipped, so the envelope says nothing
    assert "fields_dropped" not in row
    assert row["f_schema"] == 99
    assert row["f_exposure"] == {"commit": "forged"}
    assert row["f_truncated"] is False
    assert row["f_fields_dropped"] is False


def test_shadow_rescue_prefix_loops_until_free(_isolated_events_dir):
    """`f_` is a rescue, not an overwrite: a caller sending BOTH `schema` and
    `f_schema` must lose neither. Order matters — a single-shot prefix silently
    overwrites the already-placed `f_schema` when `schema` is merged last."""
    kaizen_events.emit("phase", sid="s1", **{"f_f_schema": 3, "f_schema": 2, "schema": 1})

    row = _lines(_isolated_events_dir / "s1.jsonl")[0]
    assert row["schema"] == kaizen_events.SCHEMA
    assert {row["f_schema"], row["f_f_schema"], row["f_f_f_schema"]} == {1, 2, 3}


def test_exposure_override_replaces_the_resolved_exposure(_isolated_events_dir):
    """The coroner reconstructs events post-hoc: its exposure is joined from the dead
    session's own last trusted events, so it REPLACES the live one instead of stamping
    the coroner's process. Producer-restricted — never a caller field."""
    override = {"commit": "deadbeef", "account": "mob", "model": "claude-opus-5"}
    assert (
        kaizen_events.emit("death", sid="s1", exposure_override=override, reconstructed=True)
        is True
    )

    row = _lines(_isolated_events_dir / "s1.jsonl")[0]
    assert row["exposure"] == override
    assert row["reconstructed"] is True
    assert "f_exposure_override" not in row


def test_exposure_override_ignored_when_not_a_dict(_isolated_events_dir):
    kaizen_events.emit("death", sid="s1", exposure_override="not-a-dict")

    row = _lines(_isolated_events_dir / "s1.jsonl")[0]
    assert isinstance(row["exposure"], dict)
    assert "commit" in row["exposure"]


def test_unserializable_field_still_emits(_isolated_events_dir):
    kaizen_events.emit("phase", sid="s1", obj=object())
    row = _lines(_isolated_events_dir / "s1.jsonl")[0]
    assert isinstance(row["obj"], str)


# ── sid honesty ──────────────────────────────────────────────────────────────────────


def test_resolve_sid_precedence(monkeypatch):
    monkeypatch.setenv("CLAUDE_SESSION_ID", "from-env")
    assert kaizen_events.resolve_sid("explicit-one") == "explicit-one"
    assert kaizen_events.resolve_sid(None) == "from-env"
    monkeypatch.setenv("CLAUDE_SESSION_ID", "")  # Bash-tool shells carry it empty
    assert kaizen_events.resolve_sid(None) == kaizen_events.UNKNOWN
    monkeypatch.delenv("CLAUDE_SESSION_ID")
    assert kaizen_events.resolve_sid(None) == kaizen_events.UNKNOWN


def test_unresolvable_sid_lands_in_its_own_unknown_stream(_isolated_events_dir):
    """`unknown` is the collector's unclassified-rate input — never a shared bucket
    merged into a real session's stream."""
    assert kaizen_events.emit("stop_block", cause="gate-red") is True

    row = _lines(_isolated_events_dir / "unknown.jsonl")[0]
    assert row["sid"] == "unknown"
    assert row["sid_source"] == "none"


def test_sid_is_sanitized_no_path_escape(_isolated_events_dir):
    kaizen_events.emit("phase", sid="../../etc/evil")

    written = list(_isolated_events_dir.glob("*.jsonl"))
    assert len(written) == 1
    assert written[0].parent == _isolated_events_dir
    assert "/" not in written[0].name.removesuffix(".jsonl")


def test_sanitization_is_injective_distinct_sids_never_collide():
    """Sanitization maps many raw sids onto one safe name — `a/b` and `a.b` both become
    `a_b`, and any two sids sharing a 64-char prefix become the same stem. Merging two
    live sessions into one stream is exactly the honesty failure `unknown` exists to
    prevent, so a mangled sid carries a digest of its raw form."""
    assert kaizen_events.resolve_sid("a/b") != kaizen_events.resolve_sid("a.b")

    prefix = "s" * 64
    assert kaizen_events.resolve_sid(prefix + "-one") != kaizen_events.resolve_sid(prefix + "-two")

    # a clean sid is passed through untouched — no digest noise on the common path
    assert kaizen_events.resolve_sid("019a2f7c-1b2d-4e3a") == "019a2f7c-1b2d-4e3a"


def test_env_sid_of_literal_unknown_is_not_an_attributed_session(monkeypatch):
    """`unknown` in the env is the ABSENCE of an id, not an id — counting it as
    `sid_source: env` would launder unclassified events into attributed ones."""
    monkeypatch.setenv("CLAUDE_SESSION_ID", "unknown")
    assert kaizen_events.resolve_sid_with_source(None) == (kaizen_events.UNKNOWN, "none")


# ── fail-open ────────────────────────────────────────────────────────────────────────


def test_emit_returns_false_and_never_raises_when_open_fails(monkeypatch):
    real_open = os.open

    def boom(path, *a, **kw):
        if str(path).endswith(".jsonl"):
            raise OSError(28, "No space left on device")
        return real_open(path, *a, **kw)

    monkeypatch.setattr(kaizen_events.os, "open", boom)
    assert kaizen_events.emit("session_start", sid="s1") is False


def test_emit_leaves_no_partial_line_when_write_fails(_isolated_events_dir, monkeypatch):
    kaizen_events.emit("session_start", sid="s1")
    before = (_isolated_events_dir / "s1.jsonl").read_bytes()

    def boom(fd, data):
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(kaizen_events.os, "write", boom)
    assert kaizen_events.emit("phase", sid="s1") is False
    assert (_isolated_events_dir / "s1.jsonl").read_bytes() == before


def test_emit_returns_false_when_events_dir_is_unusable(monkeypatch, tmp_path):
    blocker = tmp_path / "notadir"
    blocker.write_text("i am a file\n")
    monkeypatch.setenv("KAIZEN_EVENTS_DIR", str(blocker))
    assert kaizen_events.emit("session_start", sid="s1") is False


def test_short_write_terminates_the_torn_line_so_the_next_event_survives(
    _isolated_events_dir, monkeypatch
):
    """A short write cannot be undone — bytes after ours belong to concurrent appenders,
    so truncating would eat THEIR events. Terminating the fragment with a newline
    confines the damage to ONE unclassified line instead of gluing the next event onto
    it and losing two."""
    real_write = os.write
    state = {"shorted": False}

    def short_once(fd, data):
        if not state["shorted"] and len(data) > 1:
            state["shorted"] = True
            return real_write(fd, data[: len(data) // 2])
        return real_write(fd, data)

    monkeypatch.setattr(kaizen_events.os, "write", short_once)
    assert kaizen_events.emit("phase", sid="s1", note="a" * 200) is False
    monkeypatch.setattr(kaizen_events.os, "write", real_write)
    assert kaizen_events.emit("round", sid="s1", findings=0) is True

    raw = (_isolated_events_dir / "s1.jsonl").read_bytes()
    lines = raw.splitlines()
    assert len(lines) == 2, "the torn fragment must be terminated, not glued to the next"
    with pytest.raises(ValueError):
        json.loads(lines[0])  # the fragment fails ALONE — one unclassified line
    assert json.loads(lines[1])["event"] == "round"  # the next event is intact


def test_symlinked_session_file_is_refused(_isolated_events_dir, tmp_path):
    """An event file is a data store the collector trusts; a symlink planted at that
    path would redirect appends anywhere the process can write. O_NOFOLLOW turns that
    into an ordinary fail-open."""
    _isolated_events_dir.mkdir(parents=True, exist_ok=True)
    elsewhere = tmp_path / "elsewhere.jsonl"
    elsewhere.write_text("")
    (_isolated_events_dir / "s1.jsonl").symlink_to(elsewhere)

    assert kaizen_events.emit("session_start", sid="s1") is False
    assert elsewhere.read_text() == ""


# ── exposure ─────────────────────────────────────────────────────────────────────────


def test_exposure_outside_a_repo_is_unknown_not_a_guess(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.delenv("CLAUDE_MODEL", raising=False)
    monkeypatch.delenv("ANTHROPIC_MODEL", raising=False)

    monkeypatch.delenv("CLAUDE_MESH_HEADLESS", raising=False)

    exp = kaizen_events.exposure(refresh=True)
    assert exp["commit"] == "unknown"
    assert exp["account"] == "unknown"
    assert exp["model"] == "unknown"
    assert exp["plan_era"] == "—"
    assert exp["headless"] is False


def test_exposure_reads_the_fleet_active_symlink(tmp_path, monkeypatch):
    home = tmp_path / "home"
    (home / ".claude-fleet" / "can").mkdir(parents=True)
    (home / ".claude-fleet" / "active").symlink_to("can")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.chdir(tmp_path)

    assert kaizen_events.exposure(refresh=True)["account"] == "can"


def test_exposure_survives_a_missing_git_binary(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PATH", str(tmp_path / "empty-bin"))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))

    assert kaizen_events.exposure(refresh=True)["commit"] == "unknown"


def test_exposure_inside_this_repo_reports_the_head_commit(monkeypatch):
    monkeypatch.chdir(REPO)
    exp = kaizen_events.exposure(refresh=True)
    assert len(exp["commit"]) >= 7 and exp["commit"] != "unknown"
    assert exp["project"] == "fabrik"


def test_exposure_plan_era_picks_the_newest_in_progress_plan(tmp_path, monkeypatch):
    """Both status forms count: the plan corpus writes `Status:` AND the bold
    `**Status:**` (the plan-set spines use the bold form) — reading only one silently
    reports the WRONG era, which mis-attributes every event of the run."""
    plans = tmp_path / "docs" / "development" / "plans"
    plans.mkdir(parents=True)
    (plans / "2026-01-01-plan-1-old.md").write_text("Status: IN-PROGRESS\n")
    (plans / "2026-08-05-plan-1-bold.md").write_text("# Plan\n\n**Status:** IN-PROGRESS\n")
    (plans / "2026-09-01-plan-1-later.md").write_text("Status: EXECUTED\n")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))

    assert kaizen_events.exposure(refresh=True)["plan_era"] == "2026-08-05-plan-1-bold"


def test_exposure_plan_era_reads_only_the_first_4096_bytes(tmp_path, monkeypatch):
    """The probe is on every session's cold path — each candidate is bounded to one
    4 KiB read, so a status buried past the header is deliberately not seen (and a
    100 KiB plan never costs a full read)."""
    plans = tmp_path / "docs" / "development" / "plans"
    plans.mkdir(parents=True)
    (plans / "2026-08-01-plan-1-real.md").write_text("Status: IN-PROGRESS\n")
    (plans / "2026-09-09-plan-1-buried.md").write_text("x" * 5000 + "\nStatus: IN-PROGRESS\n")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))

    assert kaizen_events.exposure(refresh=True)["plan_era"] == "2026-08-01-plan-1-real"


def test_exposure_plan_era_ignores_ticket_files_in_a_plan_set(tmp_path, monkeypatch):
    """A set's `T##` ticket stem sorts ABOVE every dated stem — only the SPINE counts."""
    plans = tmp_path / "docs" / "development" / "plans"
    (plans / "2026-08-01-plan-1-set").mkdir(parents=True)
    (plans / "2026-08-01-plan-1-set" / "2026-08-01-plan-1-set.md").write_text(
        "Status: IN-PROGRESS\n"
    )
    (plans / "2026-08-01-plan-1-set" / "T01-thing.md").write_text("Status: IN-PROGRESS\n")
    (plans / "archived").mkdir()
    (plans / "archived" / "2026-12-31-plan-1-old.md").write_text("Status: IN-PROGRESS\n")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))

    assert kaizen_events.exposure(refresh=True)["plan_era"] == "2026-08-01-plan-1-set"


def test_exposure_model_from_env(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.delenv("ANTHROPIC_MODEL", raising=False)
    monkeypatch.setenv("CLAUDE_MODEL", "claude-opus-5")

    assert kaizen_events.exposure(refresh=True)["model"] == "claude-opus-5"


def test_exposure_headless_is_env_driven_both_ways(tmp_path, monkeypatch):
    """`headless` must SPLIT the corpus. An isatty() fallback cannot: hooks, cron and
    every subprocess sensor read a pipe, so stdin is never a TTY and the flag would be
    constant-true — pooling the two distributions the stratification exists to separate.
    The mesh contract is the only honest signal: every headless dispatch exports the env
    var, so its ABSENCE means human."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))

    monkeypatch.setenv("CLAUDE_MESH_HEADLESS", "1")
    assert kaizen_events.exposure(refresh=True)["headless"] is True

    monkeypatch.delenv("CLAUDE_MESH_HEADLESS")
    # pytest runs with stdin captured (never a TTY) — an isatty() fallback would keep
    # this True and the assertion below is exactly what catches it.
    assert kaizen_events.exposure(refresh=True)["headless"] is False


def test_exposure_cwd_pins_the_probes_to_the_callers_directory(tmp_path, monkeypatch):
    """T02 amendment: a SUBPROCESS sensor (every hook) has no guarantee its own process
    cwd is the session's project. Unpinned, it stamps project A's events with project
    B's commit — silently, and unfixably after the fact."""
    other = tmp_path / "other"
    (other / "scripts").mkdir(parents=True)
    (other / "scripts" / "x.py").write_text("x")
    for args in (
        ["init", "-q", "-b", "master"],
        ["add", "scripts/x.py"],
        ["-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "other"],
    ):
        subprocess.run(["git", *args], cwd=other, check=True, timeout=30, capture_output=True)
    other_head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=other, capture_output=True, text=True, timeout=30
    ).stdout.strip()

    monkeypatch.chdir(REPO)  # the process cwd is THIS repo — the contaminating value
    assert kaizen_events.exposure(refresh=True, cwd=str(other))["commit"] == other_head
    assert kaizen_events.exposure(refresh=True, cwd=str(other))["project"] == UNKNOWN_PROJECT
    # ...and a pinned answer must never be served from, or poison, the shared cache.
    assert kaizen_events.exposure(refresh=True)["project"] == "fabrik"


UNKNOWN_PROJECT = "unknown"


@pytest.mark.parametrize("bad", [0, -1, float("nan"), float("inf"), "2", None, True])
def test_probe_timeout_rejects_anything_unusable(bad):
    """A caller on a hot path passes a small bound; garbage must fall back to the
    default, never to 0 (which subprocess reads as "time out immediately") and never to
    a bool (which is an int and would silently mean 1 second)."""
    assert kaizen_events._probe_timeout(bad) == kaizen_events.DEFAULT_PROBE_TIMEOUT_S


def test_probe_timeout_keeps_a_usable_bound():
    assert kaizen_events._probe_timeout(2.0) == 2.0


# ── concurrency + the module's own canary ────────────────────────────────────────────


_WRITERS = 6
_EVENTS_EACH = 40


def _hammer(events_dir: str, writer: int) -> None:
    """One real process appending to the SHARED session file (module-level so the
    `fork` context can run it)."""
    os.environ["KAIZEN_EVENTS_DIR"] = events_dir
    kaizen_events.reset_cache()
    # 7 x 400 chars keeps every value under the clipper's 512-char first pass while
    # pushing the line to ~3 KB — big enough that a non-atomic write would interleave.
    pad = {f"pad{k}": "p" * 400 for k in range(7)}
    for i in range(_EVENTS_EACH):
        kaizen_events.emit("round", sid="shared", writer=writer, findings=i, **pad)


def test_concurrent_processes_append_to_one_file_without_tearing(_isolated_events_dir):
    """The real hazard is N OS processes (hooks, gate, run-record, coroner) appending to
    the same session file — not threads inside one interpreter, which the GIL alone
    would serialize. Every line must parse and no two writers' bytes may interleave."""
    ctx = multiprocessing.get_context("fork")
    procs = [
        ctx.Process(target=_hammer, args=(str(_isolated_events_dir), w)) for w in range(_WRITERS)
    ]
    for p in procs:
        p.start()
    for p in procs:
        p.join(timeout=120)
        assert p.exitcode == 0

    raw = (_isolated_events_dir / "shared.jsonl").read_bytes().splitlines()
    assert len(raw) == _WRITERS * _EVENTS_EACH
    seen: set[tuple[int, int]] = set()
    for line in raw:
        row = json.loads(line)  # a torn/interleaved line fails HERE
        assert row["sid"] == "shared"
        assert len(line) <= kaizen_events.MAX_LINE_BYTES
        assert row["pad6"] == "p" * 400  # a spliced line would corrupt the payload
        assert "truncated" not in row  # nothing should have been clipped at this size
        seen.add((row["writer"], row["findings"]))
    assert seen == {(w, i) for w in range(_WRITERS) for i in range(_EVENTS_EACH)}


def test_selftest_cli_is_green(tmp_path):
    env = {**os.environ, "KAIZEN_EVENTS_DIR": str(tmp_path / "cli-events")}
    proc = subprocess.run(
        [sys.executable, str(MODULE), "--selftest"],
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_selftest_restores_every_env_var_it_mutates(_isolated_events_dir, monkeypatch):
    """The canary is importable, so it runs INSIDE other processes. Leaking its
    `CLAUDE_SESSION_ID` deletion would silently re-attribute every later emit in that
    process to `unknown` — the instrument corrupting its own measurement."""
    monkeypatch.setenv("CLAUDE_SESSION_ID", "caller-session")
    events_dir = os.environ["KAIZEN_EVENTS_DIR"]

    assert kaizen_events.selftest() == 0

    assert os.environ["CLAUDE_SESSION_ID"] == "caller-session"
    assert os.environ["KAIZEN_EVENTS_DIR"] == events_dir
    assert kaizen_events.resolve_sid_with_source(None) == ("caller-session", "env")


# --- T03 acceptance round: sid_source override + a bounded exposure probe -----


def _row(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8").splitlines()[-1])


def test_sid_source_override_labels_a_joined_sid(_isolated_events_dir, monkeypatch):
    """A sid recovered by joining the stream is neither `explicit` (nobody passed it) nor
    `env` (it was not there). Without a fourth value the join has to lie about its own
    provenance, and the collector cannot tell a real id from a reconstructed one."""
    monkeypatch.delenv("CLAUDE_SESSION_ID", raising=False)
    assert kaizen_events.emit("run_open", "sessA", sid_source="join", command="fabrik-probe")
    row = _row(Path(os.environ["KAIZEN_EVENTS_DIR"]) / "sessA.jsonl")
    assert row["sid"] == "sessA" and row["sid_source"] == "join", row


def test_sid_source_override_is_validated_against_the_vocabulary(_isolated_events_dir):
    """An unknown label would silently become a new bucket in every collector query."""
    assert kaizen_events.emit("run_open", "sessB", sid_source="telepathy")
    row = _row(Path(os.environ["KAIZEN_EVENTS_DIR"]) / "sessB.jsonl")
    assert row["sid_source"] == "explicit", "an invalid label falls back to the resolved one"


def test_sid_source_override_of_none_resolves_as_before(_isolated_events_dir, monkeypatch):
    monkeypatch.setenv("CLAUDE_SESSION_ID", "from-env")
    assert kaizen_events.emit("run_open")
    row = _row(Path(os.environ["KAIZEN_EVENTS_DIR"]) / "from-env.jsonl")
    assert row["sid_source"] == "env", row


def test_probe_timeout_is_forwarded_to_the_git_probes(_isolated_events_dir, monkeypatch):
    """`exposure()` shells out to git. Sensors on an agent's hot path must be able to
    bound that: the default 10s is a latency budget nobody chose."""
    seen: list[float] = []
    real = kaizen_events.subprocess.run

    def _spy(*a, **kw):
        seen.append(kw.get("timeout"))
        return real(*a, **kw)

    monkeypatch.setattr(kaizen_events.subprocess, "run", _spy)
    kaizen_events.reset_cache()
    kaizen_events.exposure(probe_timeout_s=2.0)
    assert seen and set(seen) == {2.0}, seen

    seen.clear()
    kaizen_events.reset_cache()
    assert kaizen_events.emit("run_open", "sessC", probe_timeout_s=3.0)
    assert seen and set(seen) == {3.0}, seen
    assert "probe_timeout_s" not in _row(Path(os.environ["KAIZEN_EVENTS_DIR"]) / "sessC.jsonl")


def test_probe_timeout_defaults_to_the_previous_bound(_isolated_events_dir, monkeypatch):
    seen: list[float] = []
    real = kaizen_events.subprocess.run

    def _spy(*a, **kw):
        seen.append(kw.get("timeout"))
        return real(*a, **kw)

    monkeypatch.setattr(kaizen_events.subprocess, "run", _spy)
    kaizen_events.reset_cache()
    kaizen_events.exposure()
    assert seen and set(seen) == {10.0}, seen
