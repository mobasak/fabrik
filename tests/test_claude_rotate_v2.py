"""Behavior-Contract tests — quota rotation v2 (plan 2026-08-13-plan-2, spec dd79fe9a).

T1 perishable-first successor · T2 threshold trigger · T3 hysteresis · T4 graceful drain +
suppress · T5 expiry-keyed keep-warm + identity-gated atomic filing · T6 no-signals guard ·
T7 --status --json shape. All seams injected (fake usage/profile, fake clock, tmp state dir);
no network, no real credentials, no process signals.
"""

from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

spec = importlib.util.spec_from_file_location(
    "claude_rotate_v2", REPO / "scripts" / "sysadmin" / "claude_rotate.py")
cr = importlib.util.module_from_spec(spec)
sys.modules["claude_rotate_v2"] = cr
spec.loader.exec_module(cr)

NOW = 1_800_000_000.0


def _acct(name, weekly_pct=10.0, weekly_reset=NOW + 5 * 86400, session_pct=10.0,
          session_reset=NOW + 3600, valid=True):
    return {
        "name": f"{name}-ocoron-com-s-organization", "email": f"{name}@ocoron.com",
        "valid": valid,
        "five_hour": {"utilization": session_pct, "resets_at_epoch": session_reset},
        "seven_day": {"utilization": weekly_pct, "resets_at_epoch": weekly_reset},
    }


# ── T1: perishable-first successor ─────────────────────────────────────────────


def test_t1_soonest_weekly_reset_wins():
    cands = [_acct("a", weekly_reset=NOW + 4 * 86400),
             _acct("b", weekly_reset=NOW + 1 * 86400),
             _acct("c", weekly_reset=NOW + 2 * 86400)]
    pick = cr._pick_successor(cands, current_name=None, now=NOW)
    assert pick == "b-ocoron-com-s-organization"


def test_t1_tiebreak_lower_weekly_then_session():
    cands = [_acct("a", weekly_reset=NOW + 86400, weekly_pct=50),
             _acct("b", weekly_reset=NOW + 86400, weekly_pct=20, session_pct=30),
             _acct("c", weekly_reset=NOW + 86400, weekly_pct=20, session_pct=10)]
    assert cr._pick_successor(cands, None, NOW) == "c-ocoron-com-s-organization"


def test_t1_excludes_walled_invalid_and_current():
    cands = [_acct("a", weekly_pct=100.0, weekly_reset=NOW + 100),        # weekly-walled
             _acct("b", session_pct=100.0, weekly_reset=NOW + 200),      # session-walled
             _acct("c", valid=False, weekly_reset=NOW + 300),            # dead snapshot
             _acct("d", weekly_reset=NOW + 4 * 86400)]                   # current
    assert cr._pick_successor(cands, "d-ocoron-com-s-organization", NOW) is None


# ── tick harness ───────────────────────────────────────────────────────────────


def _tick(tmp_path, monkeypatch, statuses, live_name, now=NOW, ledger_pre=None,
          threshold="95", drain="85", dwell_min="30"):
    """Run _cmd_tick with every seam faked; returns (actions dict, state dir)."""
    state = tmp_path / "state"
    state.mkdir(exist_ok=True)
    if ledger_pre:
        (state / "rotate-ledger.jsonl").write_text(
            "".join(json.dumps(e) + "\n" for e in ledger_pre))
    actions = {"switched_to": [], "mails": [], "telegrams": [], "refreshed": []}
    monkeypatch.setenv("ROTATE_STATE_DIR", str(state))
    monkeypatch.setenv("ROTATE_THRESHOLD", threshold)
    monkeypatch.setenv("ROTATE_DRAIN_THRESHOLD", drain)
    monkeypatch.setenv("ROTATE_DWELL_MIN", dwell_min)
    monkeypatch.setattr(cr, "_collect_statuses", lambda: (statuses, live_name))
    monkeypatch.setattr(cr, "_now", lambda: now)
    monkeypatch.setattr(cr, "_tick_switch",
                        lambda name: actions["switched_to"].append(name) or True)
    monkeypatch.setattr(cr, "_drain_mail", lambda repos, msg: actions["mails"].extend(repos))
    monkeypatch.setattr(cr, "_tick_telegram", lambda msg: actions["telegrams"].append(msg))
    monkeypatch.setattr(cr, "_keepwarm_refresh",
                        lambda store: actions["refreshed"].append(store.name) or True)
    monkeypatch.setattr(cr, "_mailbox_repos", lambda: ["fabrik", "seo"])
    rc = cr._cmd_tick()
    assert rc == 0
    return actions, state


# ── T2: threshold ──────────────────────────────────────────────────────────────


def test_t2_below_threshold_noop(tmp_path, monkeypatch):
    live = _acct("live", session_pct=94.0)
    sib = _acct("sib", weekly_reset=NOW + 86400)
    actions, _ = _tick(tmp_path, monkeypatch, [live, sib], live["name"])
    assert actions["switched_to"] == []


def test_t2_either_window_triggers_exactly_one_switch(tmp_path, monkeypatch):
    live = _acct("live", weekly_pct=96.0)   # weekly window crosses, session fine
    sib = _acct("sib", weekly_reset=NOW + 86400)
    actions, _ = _tick(tmp_path, monkeypatch, [live, sib], live["name"])
    assert actions["switched_to"] == [sib["name"]]


# ── T3: hysteresis ─────────────────────────────────────────────────────────────


def test_t3_dwell_blocks_then_allows(tmp_path, monkeypatch):
    live = _acct("live", session_pct=97.0)
    sib = _acct("sib", weekly_reset=NOW + 86400)
    recent = [{"event": "switch", "ts": NOW - 10 * 60, "to": live["name"]}]
    actions, _ = _tick(tmp_path, monkeypatch, [live, sib], live["name"], ledger_pre=recent)
    assert actions["switched_to"] == [], "switch within dwell must be blocked"
    old = [{"event": "switch", "ts": NOW - 31 * 60, "to": live["name"]}]
    actions, _ = _tick(tmp_path, monkeypatch, [live, sib], live["name"], ledger_pre=old)
    assert actions["switched_to"] == [sib["name"]], "past dwell must switch"


# ── T4: graceful drain ─────────────────────────────────────────────────────────


def test_t4_drain_broadcast_and_suppress(tmp_path, monkeypatch):
    live = _acct("live", session_pct=86.0)   # over drain threshold, under switch threshold
    dead = _acct("dead", valid=False)
    actions, state = _tick(tmp_path, monkeypatch, [live, dead], live["name"])
    assert actions["mails"] == ["fabrik", "seo"], "drain must mail every mailbox repo"
    assert len(actions["telegrams"]) == 1
    actions2, _ = _tick(tmp_path, monkeypatch, [live, dead], live["name"])
    assert actions2["mails"] == [] and actions2["telegrams"] == [], "stamp must suppress"


def test_t4_no_drain_when_sibling_available(tmp_path, monkeypatch):
    live = _acct("live", session_pct=86.0)
    sib = _acct("sib", weekly_reset=NOW + 86400)
    actions, _ = _tick(tmp_path, monkeypatch, [live, sib], live["name"])
    assert actions["mails"] == [] and actions["telegrams"] == []


# ── T5: keep-warm ──────────────────────────────────────────────────────────────


def test_t5_expiring_snapshot_refreshes_fresh_does_not(tmp_path, monkeypatch):
    live = _acct("live")
    exp = _acct("exp")
    exp["refresh_expires_at_epoch"] = NOW + 47 * 3600      # inside 48h → refresh
    fresh = _acct("fresh")
    fresh["refresh_expires_at_epoch"] = NOW + 30 * 86400   # far out → leave alone
    stores = tmp_path / "stores"
    for a in (exp, fresh):
        d = stores / a["name"]; d.mkdir(parents=True)
        a["store"] = str(d)
    actions, _ = _tick(tmp_path, monkeypatch, [live, exp, fresh], live["name"])
    assert actions["refreshed"] == [exp["name"]]


def test_t5_identity_mismatch_never_filed(tmp_path, monkeypatch):
    """_file_refreshed_credentials refuses a payload whose profile email doesn't match the
    store — the misattribution class (2026-08-13) must be impossible on the refresh path."""
    store = tmp_path / "ob-ocoron-com-s-organization"
    store.mkdir()
    (store / ".credentials.json").write_text(json.dumps({"claudeAiOauth": {
        "accessToken": "OLD", "refreshToken": "OLDR"}}))
    ok = cr._file_refreshed_credentials(
        store, {"claudeAiOauth": {"accessToken": "NEW", "refreshToken": "NEWR"}},
        verified_email="sarp@ocoron.com")
    assert ok is False
    assert json.loads((store / ".credentials.json").read_text())[
        "claudeAiOauth"]["accessToken"] == "OLD", "mismatch must leave the store untouched"
    ok = cr._file_refreshed_credentials(
        store, {"claudeAiOauth": {"accessToken": "NEW", "refreshToken": "NEWR"}},
        verified_email="ob@ocoron.com")
    assert ok is True
    blob = json.loads((store / ".credentials.json").read_text())
    assert blob["claudeAiOauth"]["accessToken"] == "NEW"
    assert (store / ".credentials.json.prev").exists(), ".prev must be retained"


# ── T6: no process signals anywhere ────────────────────────────────────────────


def test_t6_no_signal_calls_in_either_copy():
    pat = re.compile(r"\bpkill\b|os\.kill\(|import signal|signal\.SIG|raise_signal")
    for f in (REPO / "scripts" / "sysadmin" / "claude_rotate.py",
              REPO / "scripts" / "aro-wake" / "claude_rotate.py"):
        hits = [ln for ln in f.read_text().splitlines() if pat.search(ln)]
        assert hits == [], (f.name, hits)


# ── T7: --status --json shape ──────────────────────────────────────────────────


def test_t7_status_json_rows(tmp_path, monkeypatch):
    rows = [_acct("ok"), _acct("bad", valid=False)]
    monkeypatch.setattr(cr, "_collect_statuses", lambda: (rows, rows[0]["name"]))
    out = cr._status_payload()
    assert {r["name"] for r in out["accounts"]} == {rows[0]["name"], rows[1]["name"]}
    assert out["live"] == rows[0]["name"]
    bad = next(r for r in out["accounts"] if not r["valid"])
    assert bad.get("note") == "INVALID (relogin needed)"
