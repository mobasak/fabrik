# AFTER-EDIT: .claude/hooks/mcp_watch.py | none
"""D-041 per-message MCP forcing layer — staleness + cached-liveness banners."""
import importlib.util
import json
import os
import sys
import time
from datetime import UTC
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "mcp_watch", Path(__file__).resolve().parent.parent / ".claude/hooks/mcp_watch.py")
watch = importlib.util.module_from_spec(_spec)
sys.modules["mcp_watch"] = watch
_spec.loader.exec_module(watch)


def test_stale_config_detected(tmp_path):
    (tmp_path / ".mcp.json").write_text("{}")
    past = time.time() - 3600
    assert watch.stale_configs(str(tmp_path), past) and "repo .mcp.json" in watch.stale_configs(str(tmp_path), past)[0]
    future = time.time() + 3600
    assert all("repo" not in s for s in watch.stale_configs(str(tmp_path), future))


def test_cache_read_shapes(tmp_path, monkeypatch):
    monkeypatch.setattr(watch, "_CACHE_DIR", tmp_path)
    f = watch._cache_file("/opt/x")
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps({"ts": time.time(), "report": {"exa": "CONNECTED", "serena": "DEAD"}}))
    c = watch.read_cache("/opt/x")
    assert c and c["report"]["serena"] == "DEAD"
    f.write_text("garbage{")
    assert watch.read_cache("/opt/x") is None


# ── session start = when the TOOL UNIVERSE was loaded (2026-09-02, wef finding 01M1GE3PWBPKZWETCANJXWGGRC) ──

def _write_jsonl(tmp_path, lines):
    p = tmp_path / "session.jsonl"
    p.write_text("\n".join(lines) + "\n")
    return str(p)


class _Stdin:
    def __init__(self, text):
        self._text = text

    def read(self):
        return self._text


def test_session_start_immune_to_appends(tmp_path, monkeypatch):
    """THE bug: min(ctime, mtime) is 'last write' on Linux (ctime moves on every append),
    so the staleness verdict was decided by write ordering — silent on genuinely stale
    sessions whenever the transcript flushed last. The computed start must not move when
    the harness appends a turn."""
    monkeypatch.setattr(watch, "_claude_ancestor_start", lambda: None)
    ts = "2026-09-01T06:00:00.000Z"
    p = _write_jsonl(tmp_path, [json.dumps({"type": "user", "timestamp": ts})])
    first = watch._session_start(p)
    time.sleep(0.05)
    with open(p, "a") as fh:
        fh.write(json.dumps({"type": "assistant", "timestamp": "2026-09-02T09:00:00.000Z"}) + "\n")
    assert watch._session_start(p) == first, "start moved on append — that is the last-write bug"
    assert abs(first - 1788242400.0) < 1, "start must be the first EVENT timestamp, not a stat time"


def test_first_event_ts_skips_unparseable_and_ts_less_head(tmp_path):
    p = _write_jsonl(tmp_path, [
        "not json at all",
        json.dumps({"type": "file-history-snapshot"}),  # no timestamp
        json.dumps({"type": "user", "timestamp": "2026-09-01T06:00:00Z"}),
    ])
    got = watch._first_event_ts(p)
    assert got is not None and abs(got - 1788242400.0) < 1


def test_first_event_ts_all_garbage_is_none(tmp_path):
    p = _write_jsonl(tmp_path, ["garbage"] * 3)
    assert watch._first_event_ts(p) is None
    assert watch._first_event_ts(str(tmp_path / "missing.jsonl")) is None


def test_session_start_prefers_process_start(tmp_path, monkeypatch):
    """Tool universes are loaded at HARNESS PROCESS start. A months-old resumed
    conversation (live case: a 2026-05-13 first line on a session running 2026-09-02)
    must not pin 'start' to May — that fires the banner forever and no reload clears it."""
    monkeypatch.setattr(watch, "_claude_ancestor_start", lambda: 1788400000.0)
    p = _write_jsonl(tmp_path, [json.dumps({"timestamp": "2026-05-13T09:57:00Z"})])
    assert watch._session_start(p) == 1788400000.0


def test_claude_ancestor_start_is_plausible_when_found():
    """Live-environment tolerance: under a claude harness the walk finds the ancestor and
    its start is in the past; under cron/CI there is no claude ancestor and None is fine.
    ⚠️ Unfalsifiable ALONE (a `return None` mutant passes) — the synthetic-tree test below
    is what actually pins the walk."""
    got = watch._claude_ancestor_start()
    assert got is None or (0 < got <= time.time() + 5)


def _fake_stat(pid, comm, ppid, ticks=0):
    return f"{pid} ({comm}) S {ppid} " + " ".join(["0"] * 17) + f" {ticks} " + " ".join(["0"] * 30)


def test_ancestor_walk_finds_claude_and_walks_past_non_matches(monkeypatch):
    """A `return None` mutant of the whole walk passed the suite — the fleet-wide fallback
    that mutant causes is the 'months-old first line fires forever' bug this change kills.
    Drive a SYNTHETIC tree so the walk itself is pinned, environment-independently."""
    tree = {  # hook's parent → wrapper → the harness
        10: _fake_stat(10, "bash", 11),
        11: _fake_stat(11, "sh", 12),
        12: _fake_stat(12, "claude", 1, ticks=500),
    }
    monkeypatch.setattr(watch.os, "getppid", lambda: 10)
    monkeypatch.setattr(watch, "_btime", lambda: 1000.0)
    monkeypatch.setattr(
        watch.Path, "read_text",
        lambda self, *a, **k: tree[int(str(self).split("/")[2])],
    )
    expect = 1000.0 + 500 / os.sysconf("SC_CLK_TCK")
    assert watch._claude_ancestor_start() == expect, "walk must reach claude at depth 2"

    no_claude = {10: _fake_stat(10, "bash", 11), 11: _fake_stat(11, "sh", 1)}
    monkeypatch.setattr(
        watch.Path, "read_text",
        lambda self, *a, **k: no_claude[int(str(self).split("/")[2])],
    )
    assert watch._claude_ancestor_start() is None, "no harness ⇒ None (fallback), never a guess"


def test_start_from_stat_pins_the_field_index_deterministically(monkeypatch):
    """Environment-independent index pin: the [18]/[20] off-by-ones and the always-now
    mutant all produce a different number than btime + ticks/HZ."""
    monkeypatch.setattr(watch, "_btime", lambda: 1000.0)
    raw = _fake_stat(42, "claude", 1, ticks=700)
    assert watch._start_from_stat(raw) == 1000.0 + 700 / os.sysconf("SC_CLK_TCK")


def test_proc_start_epoch_pins_the_field_index_both_directions():
    """The /proc math is the highest-risk new code and had no DIRECT test — a mutant that
    made it `return time.time()` (session always 'starts now' ⇒ nothing is ever stale, the
    exact fleet-wide bug this change fixes) shipped green. Pin BOTH directions: self is
    ~now, init (pid 1) is materially older — a strictly-past, strictly-ordered pair the
    off-by-one and always-now mutants both fail."""
    import os

    me = watch._proc_start_epoch(os.getpid())
    assert me is not None and me <= time.time() + 1, "self start must be at or before now"
    assert time.time() - me < 3600, "self start must be RECENT, not the boot epoch (off-by-one guard)"
    init = watch._proc_start_epoch(1)
    if init is not None:  # pid 1 stat may be unreadable in some sandboxes — then skip the ordering half
        assert init < me, "init started before this test process — index/always-now mutants break this"


def test_btime_is_the_boot_epoch():
    b = watch._btime()
    assert b is None or (0 < b < time.time()), "boot epoch is in the past"


def test_main_emits_stale_banner_and_never_raises(tmp_path, monkeypatch, capsys):
    """main() had ZERO coverage — the stale_banner wiring and fail-open were unguarded."""
    monkeypatch.setattr(watch, "_claude_ancestor_start", lambda: 1000.0)  # ancient start
    monkeypatch.setattr(watch, "_refresh_detached", lambda cwd: None)  # no real subprocess/tmp leak
    (tmp_path / ".mcp.json").write_text("{}")  # exists, mtime = now > 1000 ⇒ stale
    monkeypatch.setattr("sys.stdin", _Stdin(json.dumps({"cwd": str(tmp_path), "transcript_path": ""})))
    assert watch.main() == 0
    assert "CHECK YOUR ASSIGNED MCPs" in capsys.readouterr().out


def test_main_over_warns_when_session_start_is_undetermined(tmp_path, monkeypatch, capsys):
    """The most policy-loaded line of the change had ZERO assertions: a mutant that SKIPS
    the staleness block when start is None (the silent-stale direction the change bans)
    passed the suite. Pin the over-warn AND that the banner admits it is undetermined."""
    monkeypatch.setattr(watch, "_claude_ancestor_start", lambda: None)
    monkeypatch.setattr(watch, "_first_event_ts", lambda p: None)  # ⇒ start undetermined
    monkeypatch.setattr(watch, "_refresh_detached", lambda cwd: None)
    (tmp_path / ".mcp.json").write_text("{}")
    monkeypatch.setattr("sys.stdin", _Stdin(json.dumps({"cwd": str(tmp_path), "transcript_path": ""})))
    assert watch.main() == 0
    out = capsys.readouterr().out
    assert "OUTDATED" in out, "undetermined start must OVER-WARN, never go silent"
    assert "could not be determined" in out, "and must not assert a comparison it never made"


def test_main_fail_open_on_numeric_timestamp_and_null_path(tmp_path, monkeypatch, capsys):
    """The bug the Opus finder caught: a numeric-epoch timestamp made fromisoformat raise
    ValueError out of _session_start → main() aborted before the LIVENESS banner (both
    banners silently suppressed). A null transcript_path did the same via open(None)."""
    monkeypatch.setattr(watch, "_claude_ancestor_start", lambda: None)  # force the transcript path
    monkeypatch.setattr(watch, "_refresh_detached", lambda cwd: None)
    p = tmp_path / "session.jsonl"
    p.write_text(json.dumps({"type": "user", "timestamp": 1788242400}) + "\n")  # numeric, not ISO
    monkeypatch.setattr("sys.stdin", _Stdin(json.dumps({"cwd": str(tmp_path), "transcript_path": str(p)})))
    assert watch.main() == 0  # must not raise
    assert "OUTDATED" in capsys.readouterr().out  # …and the banner still reaches the agent
    monkeypatch.setattr("sys.stdin", _Stdin(json.dumps({"cwd": str(tmp_path), "transcript_path": None})))
    assert watch.main() == 0  # open(None) must not raise either


def test_main_survives_non_dict_payload_and_bad_cache(tmp_path, monkeypatch):
    """A list/str payload and a truncated cache (report as list, ts as string) each raised
    out of main(), suppressing BOTH banners."""
    monkeypatch.setattr(watch, "_refresh_detached", lambda cwd: None)
    monkeypatch.setattr(watch, "_CACHE_DIR", tmp_path / "cache")
    (tmp_path / ".mcp.json").write_text("{}")
    for payload in ("[]", '"a string"', json.dumps({"cwd": 123})):
        monkeypatch.setattr("sys.stdin", _Stdin(payload))
        assert watch.main() == 0, f"main raised on payload {payload}"
    f = watch._cache_file(str(tmp_path))
    f.parent.mkdir(parents=True, exist_ok=True)
    for bad in ({"ts": time.time(), "report": ["a"]}, {"ts": "not-a-number", "report": {"x": "DEAD"}}):
        f.write_text(json.dumps(bad))
        assert watch.read_cache(str(tmp_path)) is None, f"bad cache must be rejected: {bad}"


def test_first_event_ts_skips_a_bad_ts_and_continues_to_the_next_line(tmp_path):
    """The inner `except ValueError: continue` is masked by the outer handler — its only
    distinct behavior is CONTINUING to a later line, which was untested."""
    p = _write_jsonl(tmp_path, [
        json.dumps({"timestamp": 1788242400}),  # numeric epoch — unparseable
        json.dumps({"timestamp": "2026-09-01T06:00:00Z"}),  # the real one
    ])
    assert abs(watch._first_event_ts(p) - 1788242400.0) < 1


def test_a_large_head_line_still_yields_its_own_timestamp(tmp_path):
    """`readline(65536)` TRUNCATES without advancing: the next iteration returned the
    REMAINDER of the same line, so the function answered with a LATER line's timestamp —
    start moves later ⇒ suppression (measured: 80KB line 1 → line 2's ts). Skipping the
    long line instead gives the SAME wrong answer, so the guard must be the real one:
    line 1 is parsed and ITS timestamp returned."""
    from datetime import datetime

    p = tmp_path / "big.jsonl"
    big = json.dumps({"pad": "x" * 80000, "timestamp": "2026-01-01T00:00:00Z"})
    p.write_text(big + "\n" + json.dumps({"timestamp": "2026-02-02T00:00:00Z"}) + "\n")
    got = watch._first_event_ts(str(p))
    line1 = datetime(2026, 1, 1, tzinfo=UTC).timestamp()
    assert got is not None and abs(got - line1) < 1, (
        "the TRUE session start is line 1's ts; answering with line 2 is the suppression bug"
    )


def test_rotation_of_a_symlinked_ancestor_is_seen(tmp_path, monkeypatch):
    """An account rotation re-points `active -> <account>`; the roster FILE and its target dir
    keep their old mtimes. `Path.lstat()` only spares the FINAL component, so lstat-ing the file
    is a no-op for this class (measured on the live roster: stat == lstat, is_symlink False) —
    the ancestor components must be walked, or a whole tool-universe swap is invisible."""
    real = tmp_path / "acct_a"
    real.mkdir()
    roster = real / ".claude.json"
    roster.write_text("{}")
    old = time.time() - 86400
    os.utime(roster, (old, old))  # file itself is OLD
    os.utime(real, (old, old))  # target dir is OLD too
    link = tmp_path / "active"
    link.symlink_to(real)  # the symlink is NEW (the rotation)
    monkeypatch.setattr(watch, "_ROSTER", link / ".claude.json")
    monkeypatch.setattr(watch, "_CACHE_DIR", tmp_path / "cache")
    session_start = time.time() - 3600  # session began an hour ago, before the rotation
    assert "account pointer" in watch.stale_configs(str(tmp_path / "norepo"), session_start), (
        "a rotation that re-pointed the symlink must read as stale"
    )


def test_roster_mtime_alone_is_not_staleness(tmp_path, monkeypatch):
    """The roster is Claude Code's global STATE file — the harness rewrites it every few
    seconds (measured: mtime advanced 3× in one minute of unrelated work), so comparing its
    mtime to any session start was unconditionally true: the banner fired on every prompt in
    every repo, forever. Only its mcpServers SLICE means the tool universe changed."""
    monkeypatch.setattr(watch, "_CACHE_DIR", tmp_path / "cache")
    roster = tmp_path / "roster.json"
    roster.write_text(json.dumps({"mcpServers": {"exa": {}}, "changelogLastFetched": 1}))
    monkeypatch.setattr(watch, "_ROSTER", roster)
    started = time.time() - 3600
    norepo = str(tmp_path / "norepo")  # no .mcp.json, no account pointer ⇒ roster half only
    watch.stale_configs(norepo, started)  # baseline this session (through the REAL wiring)
    # the harness rewrites unrelated state — mtime moves, tools do NOT
    roster.write_text(json.dumps({"mcpServers": {"exa": {}}, "changelogLastFetched": 999}))
    assert roster.stat().st_mtime > started, "precondition: mtime did move"
    assert "user roster MCP servers" not in watch.stale_configs(norepo, started), (
        "state churn is NOT staleness"
    )
    # now the MCP slice really changes
    roster.write_text(json.dumps({"mcpServers": {"exa": {}, "serena": {}}}))
    assert "user roster MCP servers" in watch.stale_configs(norepo, started), (
        "a real tool-universe change MUST fire"
    )


def test_first_event_ts_naive_is_utc(tmp_path, monkeypatch):
    """A naive timestamp (no Z, no offset) must be read as UTC, not the box's local TZ —
    on a UTC-negative host local-time parsing shifts start LATER ⇒ silent suppression.
    ⚠️ Forces a non-UTC TZ: on this +03 box the guard's mutant passes, so the test would
    only catch the bug by accident of where it runs."""
    from datetime import datetime

    monkeypatch.setenv("TZ", "America/New_York")
    time.tzset()
    try:
        p = _write_jsonl(tmp_path, [json.dumps({"timestamp": "2026-09-01T06:00:00"})])  # naive
        got = watch._first_event_ts(p)
        expect = datetime(2026, 9, 1, 6, 0, tzinfo=UTC).timestamp()
        assert got is not None and abs(got - expect) < 1
    finally:
        monkeypatch.undo()
        time.tzset()


def test_stale_banner_leads_with_fix_first():
    """Operator ruling (2026-09-02): the banner leads with the duty the AGENT can act on —
    check assigned MCPs, fix-first — not with a window-reload ask addressed to a human."""
    b = watch.stale_banner(["user roster"])
    assert b.index("CHECK YOUR ASSIGNED MCPs") < b.index("reload"), b
    assert "fix" in b.lower() and "user roster" in b


# ── the banner is a RATIO shown to every session; both halves must mean the same ──

def test_skipped_excluded_from_both_halves_of_the_ratio():
    """Live shape (2026-08-30): 15 assigned, grafana SKIPPED (docker-run, unprobed),
    maestro genuinely dead. The banner said '1/15' — numerator over 14 measured
    servers, denominator over 15 assigned. Unprobed is not dead, and it is not a
    denominator either."""
    report = {f"s{i}": "CONNECTED" for i in range(13)}
    report["grafana"] = "SKIPPED (docker-run entry — probe would launch a live container)"
    report["maestro"] = "TIMEOUT"
    b = watch.liveness_banner(report, 5)
    assert "1/14 probed" in b, f"denominator must exclude the unprobed entry: {b}"
    assert "grafana" not in b, "an unprobed server is never named as dead"
    assert "maestro" in b


def test_all_connected_plus_a_skip_raises_no_banner():
    """A skip alone must never fire the fix-first mandate — that was the false alarm."""
    report = {"exa": "CONNECTED", "grafana": "SKIPPED (docker-run entry)"}
    assert watch.liveness_banner(report, 1) is None


def test_a_real_death_still_banners():
    assert "1/1 probed" in watch.liveness_banner({"serena": "DEAD"}, 0)
