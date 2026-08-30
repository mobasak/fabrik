# AFTER-EDIT: none
"""Behavior tests for detect_reversals.py's host-action collector.

Live crash (all 3 hosts, every 5 minutes, found 2026-08-30 during the sysadmin
way-of-working audit): bot.py writes ``"ts": datetime.now().isoformat()`` (ISO
string) into sysadmin-actions.jsonl, while collect_host_sysadmin_actions()
compared ``entry.get("ts", 0) < cutoff`` (float) → TypeError on the FIRST
bot-written entry → the reversal detector (a safety layer) has been dead for as
long as the formats disagreed, filling the proactive log with tracebacks.
"""

from __future__ import annotations

import json
import time

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "sysadmin"))
import detect_reversals  # noqa: E402 — lives in scripts/sysadmin/, collected from tests/ (gate-visible)


def _write_log(tmp_path, entries):
    p = tmp_path / "actions.jsonl"
    p.write_text("".join(json.dumps(e) + "\n" for e in entries))
    return p


def test_entry_epoch_accepts_float_iso_and_rejects_garbage():
    now = time.time()
    assert detect_reversals._entry_epoch(now) == now
    assert detect_reversals._entry_epoch(int(now)) == float(int(now))
    iso = "2026-08-30T20:15:00+03:00"
    ep = detect_reversals._entry_epoch(iso)
    assert isinstance(ep, float) and ep > 1.7e9
    # naive ISO (bot.py's datetime.now().isoformat() carries no tz) still parses
    assert isinstance(detect_reversals._entry_epoch("2026-08-30T20:15:00.123456"), float)
    assert detect_reversals._entry_epoch("not-a-time") is None
    assert detect_reversals._entry_epoch(None) is None
    assert detect_reversals._entry_epoch({"nested": 1}) is None


def test_collect_host_actions_survives_iso_ts_entries(tmp_path, monkeypatch):
    # the exact crash shape: a bot-written ISO-ts entry present in the log
    log = _write_log(tmp_path, [
        {"ts": "2026-08-30T20:15:00", "message": "chat", "response_preview": "x"},  # bot entry (no action)
        {"ts": time.time(), "action_name": "docker restart", "target": "n8n"},      # actionable float-ts
        {"ts": "garbage", "action_name": "docker restart", "target": "ghost"},      # unparseable → skipped
    ])
    monkeypatch.setattr(detect_reversals, "ACTIONS_LOG_PATH", log)
    rows = detect_reversals.collect_host_sysadmin_actions()  # must NOT raise
    targets = [r["target"] for r in rows]
    assert "n8n" in targets
    assert "ghost" not in targets


def test_iso_entry_is_collected_with_local_epoch(tmp_path, monkeypatch):
    # POSITIVE control (mutation guard): a fresh bot-style naive-local ISO entry WITH an action
    # must be collected, and its parsed epoch must be ≈ now. A mutation that reads naive ISO as
    # UTC shifts the epoch by the host's UTC offset (hours) — failing both assertions on any
    # non-UTC host and the approx assertion's intent everywhere.
    import datetime as dt
    log = _write_log(tmp_path, [
        {"ts": dt.datetime.now().isoformat(), "action_name": "docker restart", "target": "fresh"},
    ])
    monkeypatch.setattr(detect_reversals, "ACTIONS_LOG_PATH", log)
    rows = detect_reversals.collect_host_sysadmin_actions()
    assert [r["target"] for r in rows] == ["fresh"], "a fresh ISO-ts action must be collected"
    assert abs(rows[0]["ts"] - time.time()) < 30, "naive ISO must parse as LOCAL time (epoch ≈ now)"


def test_collect_host_actions_honors_cutoff_for_iso_entries(tmp_path, monkeypatch):
    import datetime as dt
    old_iso = (dt.datetime.now() - dt.timedelta(days=30)).isoformat()
    log = _write_log(tmp_path, [
        {"ts": old_iso, "action_name": "docker restart", "target": "ancient"},
    ])
    monkeypatch.setattr(detect_reversals, "ACTIONS_LOG_PATH", log)
    rows = detect_reversals.collect_host_sysadmin_actions()
    assert all(r["target"] != "ancient" for r in rows), "30-day-old entry is past the cutoff"
