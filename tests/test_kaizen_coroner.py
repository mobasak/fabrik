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


def _write_transcript(sources: kc.Sources, sid: str, rows: list[dict]) -> Path:
    path = sources.transcripts_dir / "-opt-fabrik" / f"{sid}.jsonl"
    path.write_text("".join(json.dumps(r) + "\n" for r in rows))
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
