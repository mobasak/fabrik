"""Behaviour tests for the kaizen M1 coroner (T05) — duplex fixtures per death class.

The duplex law: every parsing predicate is proven BOTH ways — a fixture that must fire
(errparked record; each of the five mid-stream death texts; the structural api_error
retries-exhausted key) AND a negative control that must NOT (a still-retrying api_error;
a live busy session — both stay untouched).

Sources are SIMULATED in tmp dirs — the live sound system (its lock dirs, its logs) is
READ-ONLY, always, and no test touches the operator's real ``~/.claude/state``: both
``KAIZEN_EVENTS_DIR`` and ``COMMAND_RUN_DIR`` are isolated to tmp in an autouse fixture.
"""

from __future__ import annotations

import contextlib
import dataclasses
import datetime as dt
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
MODULE = REPO / "scripts" / "sysadmin" / "kaizen_coroner.py"
HOOK = REPO / ".claude" / "hooks" / "final_gate_stop.py"
sys.path.insert(0, str(REPO / "scripts" / "sysadmin"))
sys.path.insert(0, str(REPO / "scripts"))

import command_run  # noqa: E402
import kaizen_coroner as kc  # noqa: E402
import kaizen_events  # noqa: E402

# The five mid-stream death texts — docs/workstation/hooks-index.md:31 (the authority),
# one construction site in the CLI 2.1.219 string table.
FIVE_TEXTS = (
    "Response stalled mid-stream",
    "Server error mid-response",
    "Connection closed mid-response",
    "Response stalled while thinking",
    "Connection closed while thinking",
)

SID = "aaaa1111-2222-3333-4444-555566667777"


@pytest.fixture(autouse=True)
def _isolated_state(tmp_path, monkeypatch):
    """No test may touch the operator's real ~/.claude/state (plan pollution incident)."""
    monkeypatch.setenv("KAIZEN_EVENTS_DIR", str(tmp_path / "events"))
    monkeypatch.setenv("COMMAND_RUN_DIR", str(tmp_path / "runs"))
    monkeypatch.delenv("CLAUDE_SESSION_ID", raising=False)
    monkeypatch.delenv("KAIZEN_RUN_TTL_H", raising=False)
    kaizen_events.reset_cache()
    yield
    kaizen_events.reset_cache()


@pytest.fixture()
def sources(tmp_path) -> kc.Sources:
    """A full simulated source tree — never the live mesh paths."""
    lock = tmp_path / "locks"
    lock.mkdir()
    projects = tmp_path / "projects" / "-opt-fabrik"
    projects.mkdir(parents=True)
    log = tmp_path / "sound-debug.log"
    log.write_text("")
    (tmp_path / "events").mkdir(exist_ok=True)
    (tmp_path / "runs").mkdir(exist_ok=True)
    return kc.Sources(
        lock_dir=lock,
        mesh_log=log,
        transcripts_dir=tmp_path / "projects",
        events_dir=tmp_path / "events",
        runs_dir=tmp_path / "runs",
    )


# ── fixture builders ─────────────────────────────────────────────────────────────────


def _project_repo(sources: kc.Sources) -> Path:
    """A tmp checkout the Stop hook would instrument: it holds scripts/final_gate.py."""
    repo = sources.transcripts_dir.parent / "repo"
    (repo / "scripts").mkdir(parents=True, exist_ok=True)
    (repo / "scripts" / "final_gate.py").touch()
    return repo


def _write_transcript(
    sources: kc.Sources, sid: str, rows: list[dict], cwd: str | None = None
) -> Path:
    """A transcript with a REAL head: no transcript carries `cwd` on row 1 (0 of 814
    measured 2026-10-06) — a cwd-less queue row first, then the row that records the
    session's cwd (a tmp project by default; `cwd=""` writes none)."""
    if cwd is None:
        cwd = str(_project_repo(sources))
    head: list[dict] = [{"type": "queue-operation", "operation": "enqueue"}]
    if cwd:
        head.append({"type": "attachment", "cwd": cwd})
    path = sources.transcripts_dir / "-opt-fabrik" / f"{sid}.jsonl"
    path.write_text("".join(json.dumps(r) + "\n" for r in head + rows))
    return path


def _stall_row(text: str) -> dict:
    return {
        "type": "assistant",
        "isApiErrorMessage": True,
        "timestamp": "2026-08-20T10:00:00.000Z",
        "message": {
            "role": "assistant",
            "content": [{"type": "text", "text": f"API Error: {text}."}],
        },
    }


def _normal_assistant_row() -> dict:
    return {
        "type": "assistant",
        "message": {"role": "assistant", "content": [{"type": "text", "text": "done."}]},
    }


def _api_error_row(attempt: int, max_retries: int, code: str = "ECONNRESET") -> dict:
    return {
        "type": "system",
        "subtype": "api_error",
        "timestamp": "2026-08-20T10:00:00.000Z",
        "error": {"connection": {"code": code}},
        "retryAttempt": attempt,
        "maxRetries": max_retries,
    }


def _write_marker(sources: kc.Sources, sid: str, cls: str, epoch: int | None = None) -> Path:
    marker = sources.lock_dir / f"{kc._mesh_safe(sid)}.errparked"
    marker.write_text(f"{cls} {epoch or int(time.time())}\n")
    return marker


def _write_record(
    sources: kc.Sources, sid: str, state: str = "running", age_s: float = 60.0
) -> Path:
    now = time.time()
    rec = {
        "session_id": sid,
        "command": "fabrik-review",
        "phases": 3,
        "phase": 2,
        "state": state,
        "started_at": "2026-08-20T00:00:00+0000",
        "started_epoch": now - age_s - 10,
        "rounds": [],
        "classes": {},
        "stack": [],
        "updated_at": "2026-08-20T00:00:00+0000",
        "updated_ts": now - age_s,
    }
    path = sources.runs_dir / f"{sid}.json"
    path.write_text(json.dumps(rec, indent=2))
    return path


def _events(sources: kc.Sources, sid: str) -> list[dict]:
    path = sources.events_dir / f"{sid}.jsonl"
    if not path.is_file():
        return []
    return [json.loads(ln) for ln in path.read_text().splitlines() if ln.strip()]


def _record(sources: kc.Sources, sid: str) -> dict:
    return json.loads((sources.runs_dir / f"{sid}.json").read_text())


# ── death classes: each fires (duplex positive arm) ─────────────────────────────────


def test_errparked_marker_reconstructs_death(sources):
    _write_marker(sources, SID, "rate_limit")
    _write_record(sources, SID)

    report = kc.sweep(sources)

    events = _events(sources, SID)
    kinds = [e["event"] for e in events]
    assert "death" in kinds and "session_end" in kinds
    death = next(e for e in events if e["event"] == "death")
    assert death["class"] == "rate_limit"
    assert death["reconstructed"] is True
    assert SID in report.deaths_reconstructed


@pytest.mark.parametrize("text", FIVE_TEXTS)
def test_each_mid_stream_death_text_reconstructs_death(sources, text):
    _write_transcript(sources, SID, [_normal_assistant_row(), _stall_row(text)])

    kc.sweep(sources)

    events = _events(sources, SID)
    death = next(e for e in events if e["event"] == "death")
    assert death["class"] == "api_error_stalled"
    assert death["reconstructed"] is True
    assert "session_end" in [e["event"] for e in events]


def test_structural_retries_exhausted_is_a_death(sources):
    _write_transcript(sources, SID, [_normal_assistant_row(), _api_error_row(10, 10)])

    kc.sweep(sources)

    death = next(e for e in _events(sources, SID) if e["event"] == "death")
    assert death["class"] == "api_error_stalled"
    assert "retries_exhausted" in death["key"]


# ── the negative controls (duplex negative arm) ──────────────────────────────────────


def test_still_retrying_api_error_is_not_a_death(sources):
    """attempt < max: the CLI may recover on its own — hooks-index.md:31."""
    _write_transcript(sources, SID, [_api_error_row(3, 10)])
    _write_record(sources, SID)

    report = kc.sweep(sources)

    assert _events(sources, SID) == []
    assert _record(sources, SID)["state"] == "running"
    assert report.deaths_reconstructed == []


def test_live_busy_session_stays_untouched(sources):
    """A busy session (normal assistant tail, fresh record) is nobody's corpse."""
    _write_transcript(sources, SID, [_stall_row(FIVE_TEXTS[0]), _normal_assistant_row()])
    _write_record(sources, SID, age_s=30)

    kc.sweep(sources)

    assert _events(sources, SID) == []
    rec = _record(sources, SID)
    assert rec["state"] == "running"
    assert "closed_by" not in rec


def test_operator_input_after_stall_is_recovery_not_death(sources):
    rows = [
        _stall_row(FIVE_TEXTS[0]),
        {"type": "user", "message": {"role": "user", "content": "carry on please"}},
    ]
    _write_transcript(sources, SID, rows)

    kc.sweep(sources)

    assert _events(sources, SID) == []


def test_marker_overruled_by_recovered_transcript(sources):
    """A stale marker for a session whose transcript shows recovery must not kill it."""
    _write_marker(sources, SID, "server_error")
    _write_transcript(sources, SID, [_normal_assistant_row()])
    _write_record(sources, SID)

    kc.sweep(sources)

    assert _events(sources, SID) == []
    assert _record(sources, SID)["state"] == "running"


# ── exposure joining ─────────────────────────────────────────────────────────────────


def test_exposure_joined_from_sessions_own_last_trusted_event(sources):
    joined = {
        "commit": "abc123",
        "account": "can",
        "model": "claude-fable-5",
        "project": "fabrik",
        "headless": False,
        "plan_era": "2026-08-19-plan-1",
    }
    (sources.events_dir / f"{SID}.jsonl").write_text(
        json.dumps(
            {"schema": 1, "ts": "x", "sid": SID, "event": "session_start", "exposure": joined}
        )
        + "\n"
    )
    _write_marker(sources, SID, "rate_limit")

    kc.sweep(sources)

    death = next(e for e in _events(sources, SID) if e["event"] == "death")
    assert death["exposure"] == joined


def test_unjoinable_exposure_fields_are_literal_unknown(sources):
    _write_marker(sources, SID, "rate_limit")

    kc.sweep(sources)

    death = next(e for e in _events(sources, SID) if e["event"] == "death")
    assert death["exposure"] == dict.fromkeys(kc.EXPOSURE_KEYS, "unknown")


# ── session_end / idempotence ────────────────────────────────────────────────────────


def test_existing_session_end_skips_reconstruction(sources):
    (sources.events_dir / f"{SID}.jsonl").write_text(
        json.dumps({"schema": 1, "sid": SID, "event": "session_end"}) + "\n"
    )
    _write_marker(sources, SID, "rate_limit")

    kc.sweep(sources)

    assert [e["event"] for e in _events(sources, SID)] == ["session_end"]


def test_partial_prior_pass_gets_its_session_end_without_a_duplicate_death(sources):
    """A crash between the death append and the session_end must self-heal next sweep:
    no second death, but the close-out still lands."""
    _write_marker(sources, SID, "rate_limit")
    (sources.events_dir / f"{SID}.jsonl").write_text(
        json.dumps(
            {"schema": 1, "sid": SID, "event": "death", "reconstructed": True, "exposure": {}}
        )
        + "\n"
    )

    kc.sweep(sources)

    kinds = [e["event"] for e in _events(sources, SID)]
    assert kinds.count("death") == 1
    assert kinds.count("session_end") == 1


def test_sweep_is_idempotent(sources):
    _write_marker(sources, SID, "rate_limit")
    _write_record(sources, SID)

    kc.sweep(sources)
    first_events = _events(sources, SID)
    first_rec = _record(sources, SID)
    kc.sweep(sources)

    assert _events(sources, SID) == first_events
    assert _record(sources, SID) == first_rec


# ── revival ──────────────────────────────────────────────────────────────────────────


def test_revival_event_where_the_mesh_log_shows_one(sources):
    _write_marker(sources, SID, "server_error")
    sources.mesh_log.write_text(
        "2026-08-20 04:30:00  arg=failure   event=StopFailure   "
        f"verdict=autoresume-spawned error=server_error | cwd=/opt/fabrik sess={SID[:8]}\n"
    )

    kc.sweep(sources)

    events = _events(sources, SID)
    revival = next(e for e in events if e["event"] == "revival")
    assert revival["reconstructed"] is True
    assert revival["class"] == "server_error"


def test_no_revival_without_log_evidence(sources):
    _write_marker(sources, SID, "server_error")

    kc.sweep(sources)

    assert all(e["event"] != "revival" for e in _events(sources, SID))


# ── record closure (the load/save API; never any other mutation) ─────────────────────


def test_death_closes_running_record_died_by_coroner(sources):
    _write_marker(sources, SID, "rate_limit")
    before = json.loads(_write_record(sources, SID).read_text())

    report = kc.sweep(sources)

    rec = _record(sources, SID)
    assert rec["state"] == "died"
    assert rec["closed_by"] == "coroner"
    assert SID in report.records_died
    # NEVER any other record mutation: only state/closed_by/updated_* may differ.
    changed = {k for k in set(before) | set(rec) if before.get(k) != rec.get(k)}
    assert changed <= {"state", "closed_by", "updated_at", "updated_ts"}


def test_stale_running_record_with_no_death_expires_by_ttl(sources):
    _write_record(sources, SID, age_s=13 * 3600)  # past the 12h default TTL

    report = kc.sweep(sources)

    rec = _record(sources, SID)
    assert rec["state"] == "expired"
    assert rec["closed_by"] == "ttl"
    assert SID in report.records_expired


def test_fresh_running_record_with_no_death_stays_running(sources):
    _write_record(sources, SID, age_s=3600)

    kc.sweep(sources)

    assert _record(sources, SID)["state"] == "running"


def test_ttl_env_override(sources, monkeypatch):
    monkeypatch.setenv("KAIZEN_RUN_TTL_H", "1")
    _write_record(sources, SID, age_s=2 * 3600)

    kc.sweep(sources)

    assert _record(sources, SID)["state"] == "expired"


def test_closed_record_is_never_mutated(sources):
    """`done`/`blocked` records are terminal — the coroner never resurrects or restamps."""
    _write_marker(sources, SID, "rate_limit")
    path = _write_record(sources, SID, state="done")
    before = path.read_text()

    kc.sweep(sources)

    assert path.read_text() == before


def test_closure_goes_through_the_load_save_api(sources, monkeypatch):
    """The coroner closes records via command_run.load/save (the T03 seam), not raw IO."""
    calls: list[str] = []
    real_save = command_run.save

    def spy(sid, rec):
        calls.append(sid)
        return real_save(sid, rec)

    monkeypatch.setattr(kc, "_command_run_save", spy, raising=True)
    _write_marker(sources, SID, "rate_limit")
    _write_record(sources, SID)

    kc.sweep(sources)

    assert calls and _record(sources, SID)["state"] == "died"


# ── the Stop hook contract ───────────────────────────────────────────────────────────


def test_stop_hook_blocks_only_on_state_running():
    """Verified on the merged hook file 2026-08-20:

    - .claude/hooks/final_gate_stop.py:482 — "Only state == \"running\" on a returned
      record ever blocks."
    - .claude/hooks/final_gate_stop.py:1029 — `run_active = bool(run) and
      (run or {}).get("state") == "running"`
    - .claude/hooks/final_gate_stop.py:1263 — `_run_live = (_run_record(sid) or
      {}).get("state") == "running"`

    So a coroner-closed record (`died`/`expired`) can never block a stop, and never
    pins its project.
    """
    text = HOOK.read_text(encoding="utf-8", errors="replace")
    assert 'Only state == "running" on a returned record ever blocks.' in text  # :482
    assert 'run_active = bool(run) and (run or {}).get("state") == "running"' in text  # :1029
    assert '_run_live = (_run_record(sid) or {}).get("state") == "running"' in text  # :1263
    for closed in ("died", "expired"):
        assert {"state": closed}.get("state") != "running"  # the hook's exact predicate shape
        assert command_run.pinned_line({"state": closed, "command": "x"}) == ""


# ── the hole metric ──────────────────────────────────────────────────────────────────


def test_holes_is_transcripts_with_activity_minus_session_ends(sources):
    other = "bbbb1111-2222-3333-4444-555566667777"
    _write_transcript(sources, SID, [_normal_assistant_row()])
    _write_transcript(sources, other, [_normal_assistant_row()])
    # subagent sidecars never count as sessions
    (sources.transcripts_dir / "-opt-fabrik" / "agent-deadbeef.jsonl").write_text("{}\n")
    (sources.events_dir / f"{SID}.jsonl").write_text(
        json.dumps({"schema": 1, "sid": SID, "event": "session_end"}) + "\n"
    )

    assert kc.holes(sources) == 1  # two active sessions, one closed


def test_report_holes_today_is_the_pre_repair_reading(sources):
    """A session dying today counts as today's hole in the SAME sweep that closes it
    (spine Behavior Contract) — the report reads holes BEFORE appending session_ends."""
    _write_transcript(sources, SID, [_stall_row(FIVE_TEXTS[0])])

    report = kc.sweep(sources)

    assert report.holes_today == 1
    assert kc.holes(sources) == 0  # after the sweep the coroner has closed it


def test_holes_zero_when_every_active_session_is_closed(sources):
    _write_transcript(sources, SID, [_normal_assistant_row()])
    (sources.events_dir / f"{SID}.jsonl").write_text(
        json.dumps({"schema": 1, "sid": SID, "event": "session_end"}) + "\n"
    )

    assert kc.holes(sources) == 0


def test_holes_missing_transcripts_dir_is_unmeasurable(sources):
    """W2-F3: a coroner that cannot SEE the transcripts is a blind instrument —
    it returns None (unmeasurable), never a perfect 0."""
    import dataclasses  # noqa: PLC0415

    blind = dataclasses.replace(sources, transcripts_dir=sources.transcripts_dir / "nope")
    assert kc.holes(blind) is None


def test_holes_empty_but_readable_transcripts_dir_is_zero(sources, tmp_path):
    """W2-F3: an empty-but-readable dir is a MEASURED zero — no transcripts, no
    holes; only unreadability dashes."""
    import dataclasses  # noqa: PLC0415

    empty = tmp_path / "empty-projects"
    empty.mkdir()
    src = dataclasses.replace(sources, transcripts_dir=empty)
    assert kc.holes(src) == 0


def test_holes_internal_error_is_unmeasurable(sources, monkeypatch):
    """W2-F3: any internal error is an unmeasurable None, never a fabricated 0."""
    _write_transcript(sources, SID, [_normal_assistant_row()])

    def _boom(*a: object) -> tuple:
        raise RuntimeError("stream state exploded")

    monkeypatch.setattr(kc, "_stream_state", _boom)
    assert kc.holes(sources) is None


# ── read-only sound-system boundary + fail-open ──────────────────────────────────────


def test_sweep_never_writes_the_sound_systems_files(sources):
    """The lock dir, its markers and the mesh log are byte-identical after a sweep —
    the coroner consumes them READ-ONLY, never deletes or truncates (spine Global
    Constraints: the sound system is UNTOUCHABLE)."""
    marker = _write_marker(sources, SID, "rate_limit")
    sources.mesh_log.write_text("2026-08-20 04:30:00  arg=done verdict=delegated\n")
    marker_before = marker.read_bytes()
    log_before = sources.mesh_log.read_bytes()
    listing_before = sorted(p.name for p in sources.lock_dir.iterdir())

    kc.sweep(sources)

    assert marker.read_bytes() == marker_before
    assert sources.mesh_log.read_bytes() == log_before
    assert sorted(p.name for p in sources.lock_dir.iterdir()) == listing_before


def test_malformed_marker_and_transcript_lines_are_skipped_never_guessed(sources):
    (sources.lock_dir / "garbage.errparked").write_bytes(b"\xff\xfe\x00!!")
    path = sources.transcripts_dir / "-opt-fabrik" / f"{SID}.jsonl"
    path.write_bytes(b'{"broken json\n\xff\xfe\n' + json.dumps(_api_error_row(2, 10)).encode())

    report = kc.sweep(sources)  # must not raise

    assert report.deaths_reconstructed == []
    assert _events(sources, SID) == []
    assert _events(sources, "garbage") == []


def test_sweep_fails_open_on_missing_sources(tmp_path):
    ghost = kc.Sources(
        lock_dir=tmp_path / "nope",
        mesh_log=tmp_path / "nope.log",
        transcripts_dir=tmp_path / "nope-projects",
        events_dir=tmp_path / "events",
        runs_dir=tmp_path / "runs",
    )
    report = kc.sweep(ghost)  # must not raise
    assert report.deaths_reconstructed == []


# ── acceptance round 1 (native finder, 2026-08-20) ──────────────────────────────────


def test_record_closure_holds_the_record_lock_across_reload_and_save(sources, monkeypatch):
    """Fix 1: the close is lock-held — command_run._record_lock spans the re-load AND
    the save, so a sibling's flocked mutation can never interleave."""
    order: list[tuple[str, str]] = []
    real_lock = command_run._record_lock
    real_load = command_run.load
    real_save = command_run.save

    @contextlib.contextmanager
    def spy_lock(sid):
        order.append(("lock_enter", sid))
        with real_lock(sid):
            yield
        order.append(("lock_exit", sid))

    monkeypatch.setattr(command_run, "_record_lock", spy_lock)
    monkeypatch.setattr(command_run, "load", lambda s: (order.append(("load", s)), real_load(s))[1])
    monkeypatch.setattr(
        command_run, "save", lambda s, r: (order.append(("save", s)), real_save(s, r))[1]
    )
    _write_marker(sources, SID, "rate_limit")
    _write_record(sources, SID)

    kc.sweep(sources)

    assert ("lock_enter", SID) in order, "the close never took the record lock"
    enter = order.index(("lock_enter", SID))
    exit_ = order.index(("lock_exit", SID))
    inside = order[enter + 1 : exit_]
    assert ("load", SID) in inside, "the record was not RE-loaded inside the lock"
    assert ("save", SID) in inside, "the save happened outside the lock"


def test_concurrent_mutation_between_scan_and_close_survives(sources, monkeypatch):
    """Fix 1: a sibling's `step` landing between the coroner's scan and its close must
    survive — the close re-loads inside the lock, never trusting a pre-lock read.
    Deterministic: the sibling mutation is injected at the coroner's FIRST load."""
    real_load = command_run.load
    fired = {"done": False}

    def racing_load(sid):
        rec = real_load(sid)
        if sid == SID and not fired["done"] and rec.get("state") == "running":
            fired["done"] = True
            sibling = real_load(sid)
            sibling["phase"] = 5  # the sibling's flocked step, landing NOW
            command_run.save(sid, sibling)
        return rec

    monkeypatch.setattr(command_run, "load", racing_load)
    _write_marker(sources, SID, "rate_limit")
    _write_record(sources, SID)

    kc.sweep(sources)

    rec = _record(sources, SID)
    assert rec["state"] == "died"
    assert rec["phase"] == 5, "the coroner clobbered a concurrent mutation"


def test_record_closed_between_scan_and_close_is_not_overwritten(sources, monkeypatch):
    """Fix 1: a record that closed itself (`done`) between scan and close keeps its
    close — state is re-checked INSIDE the lock before any mutation."""
    real_load = command_run.load
    fired = {"done": False}

    def racing_load(sid):
        rec = real_load(sid)
        if sid == SID and not fired["done"] and rec.get("state") == "running":
            fired["done"] = True
            sibling = real_load(sid)
            sibling["state"] = "done"
            sibling["closed_by"] = "agent"
            sibling["evidence"] = "the agent's own close"
            command_run.save(sid, sibling)
        return rec

    monkeypatch.setattr(command_run, "load", racing_load)
    _write_marker(sources, SID, "rate_limit")
    _write_record(sources, SID)

    report = kc.sweep(sources)

    rec = _record(sources, SID)
    assert rec["state"] == "done"
    assert rec["closed_by"] == "agent"
    assert rec["evidence"] == "the agent's own close"
    assert SID not in report.records_died


def test_marker_overruled_by_recovered_transcript_older_than_lookback(sources):
    """Fix 2a: the recovery-overrule law holds at ANY transcript age — the marker loop
    resolves the transcript directly by sid, not through the lookback filter."""
    _write_marker(sources, SID, "server_error")  # fresh marker
    tpath = _write_transcript(sources, SID, [_normal_assistant_row()])
    old = time.time() - 60 * 3600  # transcript aged out of the 48h lookback
    os.utime(tpath, (old, old))
    _write_record(sources, SID)

    kc.sweep(sources)

    assert _events(sources, SID) == []
    assert _record(sources, SID)["state"] == "running"


def test_marker_older_than_lookback_is_skipped_entirely(sources):
    """Fix 2b: a death older than the sweep's horizon is not this sweep's business —
    an aged marker must not fire forever."""
    _write_marker(sources, SID, "rate_limit", epoch=int(time.time() - 60 * 3600))

    report = kc.sweep(sources)

    assert _events(sources, SID) == []
    assert report.deaths_reconstructed == []


def test_oversized_recovery_line_still_overrules_the_marker(sources):
    """Fix 3: a recovery message bigger than the 256 KiB window must not vanish —
    the window grows geometrically until a complete line lands."""
    big_row = {
        "type": "assistant",
        "message": {
            "role": "assistant",
            "content": [{"type": "text", "text": "recovered " * 40_000}],  # ~400 KiB
        },
    }
    _write_marker(sources, SID, "server_error")
    _write_transcript(sources, SID, [_stall_row(FIVE_TEXTS[0]), big_row])
    _write_record(sources, SID)

    kc.sweep(sources)

    assert _events(sources, SID) == []
    assert _record(sources, SID)["state"] == "running"


def test_unreadable_tail_at_the_cap_fails_toward_alive(sources):
    """Fix 3: at the hard cap with no complete line the verdict is UNKNOWN, and
    UNKNOWN fails toward ALIVE — no death without readable evidence."""
    huge_row = {
        "type": "assistant",
        "message": {
            "role": "assistant",
            "content": [{"type": "text", "text": "x" * (5 * 1024 * 1024)}],  # > 4 MiB cap
        },
    }
    _write_marker(sources, SID, "server_error")
    _write_transcript(sources, SID, [huge_row])

    kc.sweep(sources)

    assert _events(sources, SID) == []


def test_walk_stops_at_a_newer_still_retrying_record(sources):
    """Fix 4: the walk stops at the FIRST conclusive record newest-first — a newer
    still-retrying record proves the session was alive after an older exhausted
    episode, which must never be returned as the death."""
    rows = [_api_error_row(10, 10), _api_error_row(2, 10)]  # old exhausted, NEWER retrying
    _write_transcript(sources, SID, rows)
    _write_record(sources, SID)

    kc.sweep(sources)

    assert _events(sources, SID) == []
    assert _record(sources, SID)["state"] == "running"


def test_coroner_emissions_carry_sid_source_join(sources):
    """Fix 5: the coroner INFERRED these ids from marker/transcript filenames — every
    emission is labelled sid_source: join (kaizen_events.SID_SOURCES validates it),
    never `explicit`."""
    _write_marker(sources, SID, "server_error")
    sources.mesh_log.write_text(
        "2026-08-20 04:30:00  arg=failure   event=StopFailure   "
        f"verdict=autoresume-spawned error=server_error | cwd=/opt/fabrik sess={SID[:8]}\n"
    )

    kc.sweep(sources)

    events = _events(sources, SID)
    assert {e["event"] for e in events} == {"death", "revival", "session_end"}
    for event in events:
        assert event["sid_source"] == "join", f"{event['event']} claims {event['sid_source']}"


# ── review fix-wave: adjudicated findings, red-first ─────────────────────────────────


def test_holes_excludes_sessions_with_stop_pass(sources):
    """H4: a normally-ended session (stop_pass events, no session_end) is NOT a hole
    — liveliness is the last stop_pass (kaizen-event-stream.md); a hole is a session
    with activity but NO stop_pass AND no session_end."""
    _write_transcript(sources, "normal-1", [_normal_assistant_row()])
    _write_transcript(sources, "lost-1", [_normal_assistant_row()])
    assert kaizen_events.emit("stop_pass", sid="normal-1", outcome="clean")
    assert kc.holes(sources) == 1, "only the stop_pass-less session is a hole"


def test_weird_sid_sweep_is_idempotent(sources):
    """M2: the emitter digests a sanitized sid into its filename — the coroner's
    stream reads must use the SAME resolution or every sweep re-appends the death."""
    sid = "sess.weird"
    _write_transcript(sources, sid, [_stall_row(FIVE_TEXTS[0])])
    for _ in range(3):
        kc.sweep(sources, now=time.time())
    fname = kaizen_events._safe_sid(sid)
    assert fname != sid, "precondition: the sanitized filename differs from the raw sid"
    path = sources.events_dir / f"{fname}.jsonl"
    rows = [json.loads(ln) for ln in path.read_text().splitlines() if ln.strip()]
    deaths = [r for r in rows if r.get("event") == "death"]
    ends = [r for r in rows if r.get("event") == "session_end"]
    assert (len(deaths), len(ends)) == (1, 1), "a triple sweep must stabilize (M2)"


def test_ttl_expiry_emits_session_end_with_cause_ttl(sources):
    """M3: a TTL closure must leave an event trail — session_end, closed_by ttl —
    idempotently (a later sweep never re-emits for a no-longer-running record)."""
    stale = "stale-ttl-1"
    _write_record(sources, stale, age_s=13 * 3600)
    report = kc.sweep(sources, now=time.time())
    assert stale in report.records_expired
    ends = [r for r in _events(sources, stale) if r.get("event") == "session_end"]
    assert len(ends) == 1, "the TTL close must emit exactly one session_end"
    assert ends[0].get("closed_by") == "ttl"
    assert ends[0].get("sid_source") == "join"
    kc.sweep(sources, now=time.time())
    ends = [r for r in _events(sources, stale) if r.get("event") == "session_end"]
    assert len(ends) == 1, "a second sweep must not re-emit"


def test_inconclusive_transcript_never_kills_a_marker(sources):
    """L3: a marker whose transcript EXISTS but is inconclusive must not close a
    possibly-live session — skipped with a counted reason. A marker with no
    transcript at all stays explicit evidence (the selftest's synthetic arm)."""
    sid = "inconclusive-1"
    _write_marker(sources, sid, "rate_limit")
    _write_record(sources, sid)
    # Newest record: an api-error assistant row OUTSIDE the five-text death family —
    # the walk stops inconclusive (verdict None), the session may still be live.
    _write_transcript(sources, sid, [_stall_row("Some other transient error")])
    report = kc.sweep(sources, now=time.time())
    assert sid not in report.deaths_reconstructed
    assert sid in report.inconclusive, "the skip must be counted, never silent"
    assert _record(sources, sid)["state"] == "running", "a possibly-live record stays open"


# ── CLI: the duplex selftest canary ──────────────────────────────────────────────────


def test_cli_selftest_is_green(tmp_path):
    import os

    env = {
        **os.environ,
        "KAIZEN_EVENTS_DIR": str(tmp_path / "events"),
        "COMMAND_RUN_DIR": str(tmp_path / "runs"),
    }
    out = subprocess.run(
        [sys.executable, str(MODULE), "--selftest"],
        capture_output=True,
        text=True,
        timeout=60,
        env=env,
    )
    assert out.returncode == 0, out.stdout + out.stderr
    assert "selftest" in out.stdout


# ── fix-wave 3 (S10: a crashed sweep must not report a measured-looking zero) ────────


def test_holes_today_is_none_when_the_sweep_fails_open(tmp_path, monkeypatch):
    """S10: the fail-open path never reaches holes() — the report must say
    UNMEASURED (None), not print a fabricated 0 holes."""

    def _boom(*args: object, **kwargs: object) -> list:
        raise RuntimeError("gather exploded")

    monkeypatch.setattr(kc, "_gather_deaths", _boom)
    ghost = kc.Sources(
        lock_dir=tmp_path / "locks",
        mesh_log=tmp_path / "log",
        transcripts_dir=tmp_path / "projects",
        events_dir=tmp_path / "events",
        runs_dir=tmp_path / "runs",
    )
    report = kc.sweep(ghost)
    assert report.errors, "the fail-open path must record the error"
    assert report.holes_today is None, "a crashed sweep must not report holes=0"


# ── W-97de2aa3: the hole denominator is the Stop hook's instrumented population ─────


def test_non_project_session_is_not_a_hole(sources, tmp_path):
    """A headless `claude -p` from a directory with no scripts/final_gate.py never gets a
    stop_pass (the hook returns at its project check) — it is not a lost session."""
    (tmp_path / "home").mkdir()
    _write_transcript(sources, "ping-1", [_normal_assistant_row()], cwd=str(tmp_path / "home"))
    assert kc.holes(sources) == 0


def test_project_session_with_realistic_head_is_a_hole(sources):
    """The cwd row sits after cwd-less leading rows; a project session with no pass is a hole."""
    _write_transcript(sources, "lost-1", [_normal_assistant_row()])
    assert kc.holes(sources) == 1


def test_quota_hold_exit_is_not_a_hole(sources):
    """The quota hold ends the turn with stop_allowed_quota_hold, a legitimate hook pass."""
    _write_transcript(sources, "held-1", [_normal_assistant_row()])
    assert kaizen_events.emit("stop_allowed_quota_hold", sid="held-1")
    assert kc.holes(sources) == 0


def test_transcript_without_cwd_is_not_counted(sources, tmp_path, monkeypatch):
    """No absolute cwd in the head: the instrument cannot say the hook covered it. The
    relative cwd DOES resolve to a project from the process cwd, so only the isabs guard
    keeps it out."""
    (tmp_path / "relative" / "dir" / "scripts").mkdir(parents=True)
    (tmp_path / "relative" / "dir" / "scripts" / "final_gate.py").touch()
    monkeypatch.chdir(tmp_path)
    _write_transcript(sources, "nocwd-1", [_normal_assistant_row()], cwd="")
    _write_transcript(sources, "relcwd-1", [_normal_assistant_row()], cwd="relative/dir")
    assert kc.holes(sources) == 0


def test_hole_count_is_version_4(monkeypatch):
    """The population change ships with its owed version bump (S5) — a new series file, so
    the probe-inflated v3 history never averages with the instrumented v4 one."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "kc2_v4", REPO / "scripts" / "sysadmin" / "kaizen_collect_v2.py"
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    # its dataclasses resolve their module through sys.modules — scoped to this test
    monkeypatch.setitem(sys.modules, "kc2_v4", mod)
    spec.loader.exec_module(mod)
    rows = [d for d in mod.METRIC_DEFS if d["id"] == "hole_count"]
    assert len(rows) == 1 and rows[0]["version"] == 4
    assert "scripts/final_gate.py" in rows[0]["formula"]


# ── W-97de2aa3 part 2: the coroner's own sweep log ───────────────────────────────────


def _with_log(sources: kc.Sources, tmp_path: Path) -> kc.Sources:
    return dataclasses.replace(sources, sweeps_log=tmp_path / "state" / "coroner-sweeps.jsonl")


def test_sweep_appends_its_line(sources, tmp_path):
    """Behaviour 1: one bounded line per sweep, carrying what the collector checks."""
    src = _with_log(sources, tmp_path)
    kc.sweep(src)
    lines = src.sweeps_log.read_text().splitlines()
    assert len(lines) == 1 and len(lines[0]) < kc.SWEEP_LINE_MAX
    row = json.loads(lines[0])
    for key in (
        "ts",
        "deaths",
        "session_ends",
        "inconclusive",
        "markers_seen",
        "holes_today",
        "errors",
        "lookback_h",
        "blind",
    ):
        assert key in row, key
    assert row["errors"] == 0 and row["blind"] is False and row["lookback_h"] > 0
    assert dt.datetime.fromisoformat(row["ts"]).tzinfo is not None


def test_fixture_sweep_writes_no_line(sources, tmp_path, monkeypatch):
    """Behaviour 2: a Sources without sweeps_log (every fixture, --selftest) writes nothing —
    even with KAIZEN_STATE_DIR pointing somewhere writable."""
    monkeypatch.setenv("KAIZEN_STATE_DIR", str(tmp_path / "live"))
    assert sources.sweeps_log is None
    kc.sweep(sources)
    assert not (tmp_path / "live").exists()


def test_inconclusive_counts_instrumented_only(sources, tmp_path):
    """Behaviour 3: an undecidable marker on an instrumented session makes the line
    unclean; the same marker on a probe ping from a non-project directory does not."""
    undecided = {
        "type": "assistant",
        "isApiErrorMessage": True,
        "message": {
            "role": "assistant",
            "content": [{"type": "text", "text": "API Error: 403 org not allowed."}],
        },
    }
    _write_transcript(sources, SID, [undecided])
    _write_marker(sources, SID, "oauth_org_not_allowed")
    src = _with_log(sources, tmp_path)
    kc.sweep(src)
    assert json.loads(src.sweeps_log.read_text().splitlines()[-1])["inconclusive"] == 1
    (tmp_path / "home").mkdir()
    other = "bbbb1111-2222-3333-4444-555566667777"
    _write_transcript(sources, other, [undecided], cwd=str(tmp_path / "home"))
    _write_marker(sources, other, "oauth_org_not_allowed")
    (sources.transcripts_dir / "-opt-fabrik" / f"{SID}.jsonl").unlink()
    (sources.lock_dir / f"{kc._mesh_safe(SID)}.errparked").unlink()
    kc.sweep(src)
    last = json.loads(src.sweeps_log.read_text().splitlines()[-1])
    assert last["inconclusive"] == 0 and last["markers_seen"] == 1


def test_a_failed_record_close_is_counted_in_the_line(sources, tmp_path, monkeypatch):
    """A-S1/A-S4: a record-closure failure used to only warn, so the sweep line read
    errors 0 after an error; it is counted now, which keeps that sweep from evidencing."""
    _write_record(sources, "stale-1", age_s=13 * 3600.0)

    def boom(*_a, **_k):
        raise OSError("disk full")

    monkeypatch.setattr(kc, "_command_run_save", boom)
    src = _with_log(sources, tmp_path)
    report = kc.sweep(src)
    assert any("record close" in e for e in report.errors)
    assert json.loads(src.sweeps_log.read_text().splitlines()[-1])["errors"] >= 1


# ── run-bound scratch (scratch lifecycle plan P11, row A7) ───────────────────────────────────────


def _run_folder(tmp_path: Path, name: str) -> Path:
    folder = tmp_path / "harness" / "-opt-x" / SID / "scratchpad" / name
    folder.mkdir(parents=True)
    (folder / ".owner").write_text(json.dumps({"state": "running", "closed_at": None}))
    return folder


def _with_run_folders(sources: kc.Sources, tmp_path: Path, age_s: int = 3600) -> tuple[Path, Path]:
    """A running record whose own run folder and a parked parent's folder are both `running`."""
    path = _write_record(sources, SID, age_s=age_s)
    rec = json.loads(path.read_text())
    child, parent = (
        _run_folder(tmp_path, "run-child-aaa111"),
        _run_folder(tmp_path, "run-parent-bbb222"),
    )
    rec["run_scratch"] = str(child)
    rec["stack"] = [
        {"command": "fabrik-execute-plan", "state": "running", "run_scratch": str(parent)}
    ]
    path.write_text(json.dumps(rec, indent=2))
    return child, parent


def _state(folder: Path) -> str:
    return json.loads((folder / ".owner").read_text())["state"]


def test_coroner_marks_run_folders_done(sources, tmp_path):
    """A7: a `died` close marks the record's folder AND every parked parent's folder `done`."""
    child, parent = _with_run_folders(sources, tmp_path)
    _write_marker(sources, SID, "rate_limit")
    kc.sweep(sources)
    assert _record(sources, SID)["state"] == "died"
    assert _state(child) == "done" and _state(parent) == "done"


def test_coroner_expired_marks_nothing(sources, tmp_path):
    """A7 (P11): `expired` is no death evidence — a live operator away overnight keeps the folders."""
    child, parent = _with_run_folders(sources, tmp_path, age_s=13 * 3600)
    kc.sweep(sources)
    assert _record(sources, SID)["state"] == "expired"
    assert _state(child) == "running" and _state(parent) == "running"


def test_coroner_tolerates_a_command_run_without_the_mark(sources, tmp_path, monkeypatch):
    """A7: a synced command_run.py older than the plan (no `_mark_run_scratch`) still closes the
    record `died`; the folders stay as they are and the sweep records no error."""
    child, parent = _with_run_folders(sources, tmp_path)
    _write_marker(sources, SID, "rate_limit")
    monkeypatch.delattr(command_run, "_mark_run_scratch")
    report = kc.sweep(sources)
    assert _record(sources, SID)["state"] == "died"
    assert _state(child) == "running" and _state(parent) == "running"
    assert not any("run folder mark" in e or "record close" in e for e in report.errors), (
        report.errors
    )


def test_coroner_marks_only_after_a_successful_save(sources, tmp_path, monkeypatch):
    """A7: a `died` close whose save fails leaves both folders `running`."""
    child, parent = _with_run_folders(sources, tmp_path)
    _write_marker(sources, SID, "rate_limit")
    monkeypatch.setattr(kc, "_command_run_save", lambda sid, rec: False)
    kc.sweep(sources)
    assert _state(child) == "running" and _state(parent) == "running"


@pytest.mark.parametrize("missing", ["kaizen_events", "command_run"])
def test_a_sweep_with_a_failed_import_exits_nonzero_naming_it(monkeypatch, capsys, missing):
    """W-4bd4ea3c: a failed import of either module was swallowed (`except Exception: ... = None`)
    and `--sweep` still exited 0, so the daily job stamped a sweep that closed no records (no
    `command_run`) or emitted no events (no `kaizen_events`) as done, and nothing retried it.
    It now exits 3, naming the module and its import error; the report still prints."""
    monkeypatch.setattr(kc, "sweep", lambda *a, **k: kc.CoronerReport())
    monkeypatch.setattr(kc, missing, None)
    monkeypatch.setattr(kc, "_IMPORT_ERRORS", {missing: "ImportError: boom"})
    assert kc.main(["--sweep"]) == 3
    captured = capsys.readouterr()
    assert missing in captured.err and "ImportError: boom" in captured.err, captured.err
    assert '"holes_today"' in captured.out  # the report is still printed


def test_a_sweep_with_both_modules_exits_zero(monkeypatch, capsys):
    """A CONTROL: a sweep whose imports succeeded exits 0, as before."""
    monkeypatch.setattr(kc, "sweep", lambda *a, **k: kc.CoronerReport())
    assert kc.main(["--sweep"]) == 0


@pytest.mark.parametrize("missing", ["kaizen_events", "command_run"])
def test_a_real_failed_import_is_kept_and_the_module_still_loads(missing):
    """The import-time capture itself, not an injected dict: a fresh interpreter whose `missing`
    import fails still loads the module (its read-only callers need it), keeps the error under
    that module's name, and `--sweep` exits 3 naming it. The sweep is stubbed inside the child, so
    nothing reads or writes the real state."""
    child = (
        "import sys\n"
        f"sys.path[:0] = [{str(REPO / 'scripts' / 'sysadmin')!r}, {str(REPO / 'scripts')!r}]\n"
        f"sys.modules[{missing!r}] = None\n"
        "import kaizen_coroner as kc\n"
        f"assert getattr(kc, {missing!r}) is None\n"
        f"print('KEPT', kc._IMPORT_ERRORS.get({missing!r}, ''))\n"
        "kc.sweep = lambda *a, **k: kc.CoronerReport()\n"
        "sys.exit(kc.main(['--sweep']))\n"
    )
    r = subprocess.run(
        [sys.executable, "-c", child], capture_output=True, text=True, timeout=60, check=False
    )
    assert r.returncode == 3, (r.stdout, r.stderr)
    assert "KEPT ModuleNotFoundError" in r.stdout, r.stdout
    assert f"ran without {missing} (ModuleNotFoundError" in r.stderr, r.stderr


def test_a_sweep_that_counted_an_error_exits_nonzero(monkeypatch, capsys):
    """Both modules imported, but the sweep itself counted an error (a crashed pass, a record
    close that raised): the same blind day, so the same exit 3, naming the first error."""
    report = kc.CoronerReport()
    report.errors.append("OSError('home gone')")
    monkeypatch.setattr(kc, "sweep", lambda *a, **k: report)
    assert kc.main(["--sweep"]) == 3
    err = capsys.readouterr().err
    assert "counted 1 error(s)" in err and "OSError('home gone')" in err, err


# ── W-6f46cebd: every sweep failure path counts an error, so --sweep exits 3 ────────────────────


def _failing_emit(
    monkeypatch: pytest.MonkeyPatch, event: str, closed_by: str | None = None
) -> None:
    """`kaizen_events.emit` returning False for ONE event only, so the death emit (counted since
    W-4bd4ea3c) lands and the path under test is the one that fails."""
    real = kaizen_events.emit

    def emit(ev, *a, **k):
        if ev == event and (closed_by is None or k.get("closed_by") == closed_by):
            return False
        return real(ev, *a, **k)

    monkeypatch.setattr(kaizen_events, "emit", emit)


def test_a_record_save_that_fails_counts_an_error(sources, monkeypatch):
    """W-6f46cebd: `_command_run_save` returning False left the record running and counted
    nothing, so the sweep exited 0; a retry recovers it, so it must exit 3."""
    _write_record(sources, "stale-1", age_s=13 * 3600.0)
    monkeypatch.setattr(kc, "_command_run_save", lambda sid, rec: False)
    report = kc.sweep(sources)
    assert "record close for stale-1 not persisted" in report.errors, report.errors


@pytest.mark.parametrize("case", ["ttl-session-end", "revival", "coroner-session-end"])
def test_a_lost_event_counts_an_error(sources, monkeypatch, case):
    """W-6f46cebd: an emit() returning False is a lost event (it returns False only on failure),
    and the ttl session_end, the revival and the coroner session_end each counted nothing."""
    if case == "ttl-session-end":
        _write_record(sources, "stale-1", age_s=13 * 3600.0)
        _failing_emit(monkeypatch, "session_end", closed_by="ttl")
        expected = "ttl session_end emit failed for stale-1"
    else:
        _write_marker(sources, SID, "server_error")
        if case == "revival":
            sources.mesh_log.write_text(
                "2026-08-20 04:30:00  arg=failure   event=StopFailure   "
                f"verdict=autoresume-spawned error=server_error | cwd=/opt/fabrik sess={SID[:8]}\n"
            )
            _failing_emit(monkeypatch, "revival")
            expected = f"revival emit failed for {kc._mesh_safe(SID)}"
        else:
            _failing_emit(monkeypatch, "session_end", closed_by="coroner")
            expected = f"session_end emit failed for {kc._mesh_safe(SID)}"
    report = kc.sweep(sources)
    assert expected in report.errors, report.errors


_ROOT = hasattr(os, "geteuid") and os.geteuid() == 0


@contextlib.contextmanager
def _unreadable(path: Path):
    """`path` at mode 000 for the block, restored after (tmp_path cleanup needs it back)."""
    path.chmod(0)
    try:
        yield
    finally:
        path.chmod(0o755)


@pytest.mark.skipif(_ROOT, reason="root reads a mode-000 dir")
def test_an_unreadable_runs_dir_counts_an_error(sources):
    """W-6f46cebd: `Path.glob` returns [] for an unreadable dir (it never raises), so a runs dir
    the sweep could not list closed no record and counted nothing. A REAL mode-000 dir."""
    _write_record(sources, "stale-1", age_s=13 * 3600.0)
    with _unreadable(sources.runs_dir):
        report = kc.sweep(sources)
    assert any(e.startswith("runs dir unreadable") for e in report.errors), report.errors


@pytest.mark.skipif(_ROOT, reason="root searches a mode-000 dir")
def test_a_transcripts_dir_under_an_unsearchable_parent_is_blind_and_still_repairs(
    sources, tmp_path
):
    """W-6f46cebd review: `Path.exists()` RAISES PermissionError under an unsearchable parent,
    which aborted the sweep before any record closed; the stale record still expires now, and
    the blind reading is counted."""
    parent = tmp_path / "locked"
    (parent / "projects").mkdir(parents=True)
    src = dataclasses.replace(sources, transcripts_dir=parent / "projects")
    _write_record(src, "stale-1", age_s=13 * 3600.0)
    with _unreadable(parent):
        report = kc.sweep(src)
    assert "holes() unmeasurable (blind)" in report.errors, report.errors
    assert "stale-1" in report.records_expired, report


def test_a_transcripts_dir_under_a_regular_file_is_blind_not_absent(sources, tmp_path):
    """ENOTDIR (`~/.claude` is a file) reads absent to `Path.exists()`; it is a broken
    installation, so the blind reading is counted (W-6f46cebd review round 2)."""
    blocker = tmp_path / "claude-is-a-file"
    blocker.write_text("")
    report = kc.sweep(dataclasses.replace(sources, transcripts_dir=blocker / "projects"))
    assert report.holes_today is None
    assert "holes() unmeasurable (blind)" in report.errors, report.errors


def test_a_dangling_transcripts_symlink_is_blind_not_absent(sources, tmp_path):
    """A `~/.claude/projects` symlink to nothing is a broken installation, not no installation."""
    link = tmp_path / "dangling-projects"
    link.symlink_to(tmp_path / "nowhere")
    report = kc.sweep(dataclasses.replace(sources, transcripts_dir=link))
    assert report.holes_today is None
    assert "holes() unmeasurable (blind)" in report.errors, report.errors


def test_a_missing_runs_dir_is_no_records_not_an_error(sources):
    """The control: a box that has never run a command has no runs dir — no error."""
    report = kc.sweep(dataclasses.replace(sources, runs_dir=sources.runs_dir / "never-made"))
    assert not any("runs dir" in e for e in report.errors), report.errors


def test_a_lost_sweep_line_counts_an_error(sources, tmp_path):
    """W-6f46cebd: a sweep line that could not be written only warned, and the sweep exited 0."""
    log_dir = tmp_path / "state" / "coroner-sweeps.jsonl"
    log_dir.mkdir(parents=True)  # a directory where the log file should be
    report = kc.sweep(dataclasses.replace(sources, sweeps_log=log_dir))
    assert any(e.startswith("sweep log write failed") for e in report.errors), report.errors


def test_a_blind_sweep_counts_an_error(sources, monkeypatch):
    """W-6f46cebd: holes() returning None over a PRESENT transcripts dir (unreadable, or its own
    error) marked the line blind but exited 0."""
    monkeypatch.setattr(kc, "holes", lambda *a, **k: None)
    report = kc.sweep(sources)
    assert "holes() unmeasurable (blind)" in report.errors, report.errors


def test_a_missing_transcripts_dir_is_not_an_error(sources):
    """The control: a host with no ~/.claude/projects is not an installation to measure."""
    gone = dataclasses.replace(sources, transcripts_dir=sources.transcripts_dir.parent / "absent")
    report = kc.sweep(gone)
    assert report.holes_today is None
    assert "holes() unmeasurable (blind)" not in report.errors, report.errors


def test_a_counted_sweep_error_exits_3_through_main(sources, monkeypatch, capsys):
    """The real main() over a real sweep (tmp sources): a counted failure exits 3."""
    monkeypatch.setattr(kc.Sources, "default", classmethod(lambda cls: sources))
    monkeypatch.setattr(kc, "holes", lambda *a, **k: None)
    assert kc.main(["--sweep"]) == 3
    assert "holes() unmeasurable (blind)" in capsys.readouterr().err


# ── W-3cdc8bd6 / W-a14fd24f / W-4c526386: retried events, counted unreadable inputs ─────────────


def _kinds(sources: kc.Sources, sid: str) -> list[str]:
    return [e["event"] for e in _events(sources, sid)]


def _revival_log(sources: kc.Sources) -> None:
    sources.mesh_log.write_text(
        "2026-08-20 04:30:00  arg=failure   event=StopFailure   "
        f"verdict=autoresume-spawned error=server_error | cwd=/opt/fabrik sess={SID[:8]}\n"
    )


def test_a_lost_ttl_session_end_is_retried_on_the_next_sweep(sources, monkeypatch):
    """W-3cdc8bd6: the record used to be saved `expired` before the ttl session_end emit, so a lost
    emit was one-shot. Now the record stays `running`, its updated_ts untouched (a bumped ts would
    read fresh and never be retried), and the next sweep emits once and expires it."""
    _write_record(sources, "stale-1", age_s=13 * 3600.0)
    before = _record(sources, "stale-1")["updated_ts"]
    real = kaizen_events.emit
    _failing_emit(monkeypatch, "session_end", closed_by="ttl")
    first = kc.sweep(sources)
    assert "ttl session_end emit failed for stale-1" in first.errors, first.errors
    assert not any("not persisted" in e for e in first.errors), first.errors
    rec = _record(sources, "stale-1")
    assert rec["state"] == "running" and rec["updated_ts"] == before
    assert first.records_expired == []
    monkeypatch.setattr(kaizen_events, "emit", real)
    second = kc.sweep(sources)
    assert second.records_expired == ["stale-1"], second
    assert _record(sources, "stale-1")["state"] == "expired"
    assert _kinds(sources, "stale-1").count("session_end") == 1


def test_a_lost_revival_is_repaired_after_the_session_revives(sources, monkeypatch):
    """W-3cdc8bd6 (Opus + Fable critiques, executed): a revived session reads alive on the next
    sweep and drops out of `deaths`, so a revival lost on sweep 1 is repaired from the event
    stream, not from re-gathered evidence; the session_end is never held back."""
    _write_marker(sources, SID, "server_error")
    transcript = _write_transcript(sources, SID, [_normal_assistant_row(), _api_error_row(10, 10)])
    _revival_log(sources)
    real = kaizen_events.emit
    _failing_emit(monkeypatch, "revival")
    first = kc.sweep(sources)
    assert f"revival emit failed for {kc._mesh_safe(SID)}" in first.errors, first.errors
    assert _kinds(sources, SID) == ["death", "session_end"]
    monkeypatch.setattr(kaizen_events, "emit", real)
    with transcript.open("a") as fh:  # the revival: the model speaks again
        fh.write(json.dumps(_normal_assistant_row()) + "\n")
    second = kc.sweep(sources)
    assert second.errors == [], second.errors
    kinds = _kinds(sources, SID)
    assert kinds.count("revival") == 1 and kinds.count("session_end") == 1, kinds
    kc.sweep(sources)
    assert _kinds(sources, SID) == kinds  # idempotent


def test_a_lost_session_end_is_repaired_from_the_stream(sources, monkeypatch):
    """W-3cdc8bd6: a coroner session_end lost on sweep 1 is repaired after the death evidence is
    gone (the marker cleared), from the stream's reconstructed death."""
    marker = _write_marker(sources, SID, "server_error")
    real = kaizen_events.emit
    _failing_emit(monkeypatch, "session_end", closed_by="coroner")
    first = kc.sweep(sources)
    assert f"session_end emit failed for {kc._mesh_safe(SID)}" in first.errors, first.errors
    assert _kinds(sources, SID) == ["death"]
    monkeypatch.setattr(kaizen_events, "emit", real)
    marker.unlink()
    second = kc.sweep(sources)
    assert second.errors == [], second.errors
    assert _kinds(sources, SID) == ["death", "session_end"]


@pytest.mark.skipif(_ROOT, reason="root reads a mode-000 dir")
def test_an_unreadable_lock_dir_counts_an_error(sources):
    """W-a14fd24f: an unreadable lock dir read as zero markers and exited 0; a missing one stays
    no markers and no error."""
    _write_marker(sources, SID, "server_error")
    with _unreadable(sources.lock_dir):
        report = kc.sweep(sources)
    assert any(e.startswith("lock dir unreadable") for e in report.errors), report.errors
    missing = kc.sweep(dataclasses.replace(sources, lock_dir=sources.lock_dir / "never-made"))
    assert not any("lock dir" in e for e in missing.errors), missing.errors


@pytest.mark.skipif(_ROOT, reason="root reads a mode-000 file")
def test_an_unreadable_marker_counts_an_error(sources):
    """W-a14fd24f's class (Fable critique): a mode-000 marker in a readable lock dir was skipped as
    if absent — a death never judged, exit 0."""
    marker = _write_marker(sources, SID, "server_error")
    with _unreadable(marker):
        report = kc.sweep(sources)
    assert any(e.startswith(f"marker {marker.name} unreadable") for e in report.errors), (
        report.errors
    )


@pytest.mark.timeout(20)
@pytest.mark.skipif(_ROOT, reason="root reads a mode-000 file")
@pytest.mark.parametrize("shape", ["mode-000", "corrupt", "fifo"])
def test_an_unjudgeable_record_counts_an_error(sources, shape):
    """W-4c526386 (+ Opus/Fable critiques): command_run.load returns {} for an unreadable or corrupt
    record, so a running record was skipped as silently as a closed one; a FIFO named *.json
    blocked the sweep in load's read. Each now counts an error and is not closed."""
    path = sources.runs_dir / "stale-1.json"
    if shape == "fifo":
        os.mkfifo(path)
        expected = "record stale-1 not a regular file"
    else:
        _write_record(sources, "stale-1", age_s=13 * 3600.0)
        if shape == "corrupt":
            path.write_text('{"state": "running", ')
            expected = "record stale-1 unparseable"
        else:
            expected = "record stale-1 unreadable"
    if shape == "mode-000":
        with _unreadable(path):
            report = kc.sweep(sources)
    else:
        report = kc.sweep(sources)
    assert any(e.startswith(expected) for e in report.errors), report.errors
    assert "stale-1" not in report.records_expired


# ── W-3cdc8bd6 review pass 1: every input the repair, the markers and the records read ──────────


def _open_death_stream(sources: kc.Sources, sid: str = SID) -> Path:
    """A stream holding a reconstructed death and no session_end — the repair's subject."""
    path = sources.events_dir / f"{sid}.jsonl"
    row = {"event": "death", "reconstructed": True, "sid": sid, "class": "server_error"}
    path.write_text(json.dumps(row) + "\n")
    return path


@pytest.mark.timeout(20)
def test_a_fifo_event_stream_counts_an_error_and_never_hangs(sources):
    """Review pass 1 (sonnet, executed): the repair opened every recent *.jsonl with a blocking
    read, so a FIFO hung the sweep."""
    os.mkfifo(sources.events_dir / "fifo.jsonl")
    report = kc.sweep(sources)
    assert any(e.startswith("event stream fifo.jsonl not a regular file") for e in report.errors), (
        report.errors
    )


@pytest.mark.skipif(_ROOT, reason="root reads a mode-000 file")
def test_an_unreadable_event_stream_counts_an_error(sources):
    """Review pass 1: `_tail_lines` reads an unreadable stream as empty — a death the repair never
    saw, uncounted."""
    path = _open_death_stream(sources)
    with _unreadable(path):
        report = kc.sweep(sources)
    assert any(e.startswith(f"event stream {path.name} unreadable") for e in report.errors), (
        report.errors
    )


def test_the_repair_skips_a_stream_older_than_the_lookback(sources):
    """Review pass 1 (sonnet, mutant survived): the lookback horizon bounds the repair; a stream
    untouched for longer is left alone, so the repair never rescans every stream ever written."""
    path = _open_death_stream(sources)
    old = time.time() - kc._lookback_s() - 3600
    os.utime(path, (old, old))
    kc.sweep(sources)
    assert _kinds(sources, SID) == ["death"]
    os.utime(path, None)
    kc.sweep(sources)
    assert _kinds(sources, SID) == ["death", "session_end"]


def test_a_dangling_marker_counts_an_error(sources):
    """Review pass 1 (haiku, executed): a dangling-symlink marker read as 'cleared mid-sweep' — a
    death hidden, exit 0."""
    link = sources.lock_dir / f"{kc._mesh_safe(SID)}.errparked"
    link.symlink_to(sources.lock_dir / "nowhere")
    report = kc.sweep(sources)
    assert any(e.startswith(f"marker {link.name}") for e in report.errors), report.errors


def test_an_empty_or_misaddressed_record_counts_an_error(sources):
    """Review pass 1 (both finders): a 0-byte record and a record whose stem command_run would
    rewrite (so `load` reads another path) were skipped silently."""
    (sources.runs_dir / "empty.json").write_text("")
    _write_record(sources, "dotted.stem", age_s=13 * 3600.0)
    report = kc.sweep(sources)
    assert any(e.startswith("record empty unparseable") for e in report.errors), report.errors
    assert any(e.startswith("record dotted.stem not addressable") for e in report.errors), (
        report.errors
    )
