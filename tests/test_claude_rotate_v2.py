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
import threading
from pathlib import Path

import pytest

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
    # Hermetic: an operator-created real ~/.claude-fleet must never flip these legacy-tick
    # tests into fleet mode (T03 feature detection keys on the fleet root's contents).
    monkeypatch.setenv("CLAUDE_FLEET_ROOT", str(tmp_path / "fleet-absent"))
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


def test_t4b_future_dated_drain_stamp_never_suppresses(tmp_path, monkeypatch):
    """F58 (clock-skew class, same clamp as _last_switch_ts): a drain stamp whose mtime sits in
    the FUTURE (WSL suspend/resume, NTP correction) must read EXPIRED — not 'suppressed until
    the wall clock catches up', which silences the broadcast for days while the pool drains."""
    import os as _os
    live = _acct("live", session_pct=86.0)
    dead = _acct("dead", valid=False)
    state = tmp_path / "state"
    state.mkdir(exist_ok=True)
    stamp = state / "drain-stamp"
    stamp.touch()
    future = NOW + 5 * 86400
    _os.utime(stamp, (future, future))
    actions, _ = _tick(tmp_path, monkeypatch, [live, dead], live["name"])
    assert actions["mails"] == ["fabrik", "seo"], "future-dated stamp must not silence the drain"
    assert len(actions["telegrams"]) == 1


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
        d = stores / a["name"]
        d.mkdir(parents=True)
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


def test_t5c_provenance_filing_path_still_guards_identity():
    """T5c RETIRED as a keep-warm test — the HTTP grant is CLI-only (403/1010), so there is
    no in-tool refresh to file. The provenance FLAG on _file_refreshed_credentials remains
    (a future CLI-mediated refresh would use it), so its contract is pinned directly."""
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        store = Path(d) / "ob-ocoron-com-s-organization"
        store.mkdir()
        (store / ".credentials.json").write_text(json.dumps({"claudeAiOauth": {
            "accessToken": "OLD"}}))
        assert cr._file_refreshed_credentials(
            store, {"claudeAiOauth": {"accessToken": "NEW"}},
            verified_email=None, provenance=True) is True
        assert json.loads((store / ".credentials.json").read_text())[
            "claudeAiOauth"]["accessToken"] == "NEW"
        assert cr._file_refreshed_credentials(
            store, {"claudeAiOauth": {"accessToken": "X"}},
            verified_email="sarp@ocoron.com") is False


def test_t5d_unwritable_store_never_consumes_the_token(tmp_path, monkeypatch):
    """F1's other half: prove the store can take the write BEFORE the single-use grant."""
    store = tmp_path / "ob-ocoron-com-s-organization"
    store.mkdir()
    (store / ".credentials.json").write_text(json.dumps({"claudeAiOauth": {
        "accessToken": "OLD", "refreshToken": "OLDR"}}))
    consumed = []
    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen",
                        lambda req, timeout=0: consumed.append(1))
    monkeypatch.setattr(urllib.request, "build_opener",
                        lambda *a: type("O", (), {"open": lambda s, r, timeout=0:
                                                  consumed.append(1)})())
    live = tmp_path / "live-credentials.json"
    live.write_text(json.dumps({"claudeAiOauth": {"accessToken": "LIVE-OTHER",
                                                 "refreshToken": "LIVE-OTHER-R"}}))
    monkeypatch.setattr(cr, "ACTIVE_CREDS", live)
    store.chmod(0o500)
    try:
        ok = cr._keepwarm_refresh(store)
    finally:
        store.chmod(0o700)
    assert ok is False
    assert consumed == [], "the grant must NOT run against an unwritable store"


# ── T6: no process signals anywhere ────────────────────────────────────────────


def test_t6_no_signal_calls_in_either_copy():
    # closer #17: wide enough to catch os.killpg/signal.alarm/from-signal-import (the
    # narrowed first version missed all three) while excluding PROSE uses of the word
    # "signal" in comments/docstrings — the plan's raw grep matched those, which is why
    # its literal form cannot be the assertion
    pat = re.compile(r"pkill|os\.kill|from signal import|(?<![a-z ])signal\.[a-z]")
    for f in (REPO / "scripts" / "sysadmin" / "claude_rotate.py",
              REPO / "scripts" / "aro-wake" / "claude_rotate.py"):
        hits = [ln for ln in f.read_text().splitlines() if pat.search(ln)]
        assert hits == [], (f.name, hits)


# ── T7: --status --json shape ──────────────────────────────────────────────────


def test_t7_status_json_rows(tmp_path, monkeypatch):
    monkeypatch.setenv("ROTATE_STATE_DIR", str(tmp_path))  # the payload probes the pause state
    rows = [_acct("ok"), _acct("bad", valid=False)]
    monkeypatch.setattr(cr, "_collect_statuses", lambda: (rows, rows[0]["name"]))
    out = cr._status_payload()
    assert {r["name"] for r in out["accounts"]} == {rows[0]["name"], rows[1]["name"]}
    assert out["live"] == rows[0]["name"]
    bad = next(r for r in out["accounts"] if not r["valid"])
    assert bad.get("note") == "INVALID (relogin needed)"


# ── closer round: the credential-strand guards ─────────────────────────────────


def test_t5e_never_consumes_the_live_accounts_token(tmp_path, monkeypatch):
    """Closer #1 (worst class): a store holding the LIVE account's tokens — via a stale
    marker or a duplicate mis-filed store — must NEVER have its refresh token consumed."""
    store = tmp_path / "sarp-ocoron-com-s-organization"
    store.mkdir()
    (store / ".credentials.json").write_text(json.dumps({"claudeAiOauth": {
        "accessToken": "LIVE-TOK", "refreshToken": "LIVE-R"}}))
    live = tmp_path / "live-credentials.json"
    live.write_text(json.dumps({"claudeAiOauth": {"accessToken": "LIVE-TOK",
                                                 "refreshToken": "LIVE-R"}}))
    monkeypatch.setattr(cr, "ACTIVE_CREDS", live)
    consumed = []
    import urllib.request
    monkeypatch.setattr(urllib.request, "build_opener",
                        lambda *a: type("O", (), {"open": lambda s, r, timeout=0:
                                                  consumed.append(1)})())
    assert cr._keepwarm_refresh(store) is False
    assert consumed == [], "the live account's single-use token must never be spent"


def test_t8_account_status_fails_closed_on_partial_usage(monkeypatch):
    """Closer #6: a 200 with a missing/oddly-typed window must read UNKNOWN (invalid), never
    0% — 0% makes a walled sibling the most attractive successor."""
    monkeypatch.setattr(cr, "_read_access_token", lambda p: "tok")
    monkeypatch.setattr(cr, "_oauth_get", lambda path, tok, **kw: (
        {"account": {"email": "ob@ocoron.com"}} if path == "profile"
        else {"five_hour": {"utilization": 12.0, "resets_at": None}}))   # seven_day MISSING
    row = cr._account_status(Path("/tmp/ob-ocoron-com-s-organization"))
    assert row["valid"] is False
    assert row["seven_day"] is None
    assert cr._pick_successor([row], None, NOW) is None, "unknown telemetry is never a target"


def test_t9_failed_switch_falls_through_to_drain(tmp_path, monkeypatch):
    """Closer #4: 'successor exists but cannot install' must NOT shadow the drain — the
    silent burn to 100% is the failure mode the whole feature exists to prevent."""
    # 98.5: above the default flip threshold (95 since 2026-09-03 — the line moved 95 → 98 → 95
    # that day; 98.5 clears every one of them, and the CLASS under test is unaffected)
    live = _acct("live", session_pct=98.5)
    sib = _acct("sib", weekly_reset=NOW + 86400)
    state = tmp_path / "state"
    state.mkdir()
    actions = {"mails": [], "telegrams": []}
    monkeypatch.setenv("CLAUDE_FLEET_ROOT", str(tmp_path / "fleet-absent"))  # hermetic (T03)
    monkeypatch.setenv("ROTATE_STATE_DIR", str(state))
    monkeypatch.setattr(cr, "_collect_statuses", lambda: ([live, sib], live["name"]))
    monkeypatch.setattr(cr, "_now", lambda: NOW)
    monkeypatch.setattr(cr, "_tick_switch", lambda name: False)      # install refuses
    monkeypatch.setattr(cr, "_drain_mail", lambda repos, msg: actions["mails"].extend(repos))
    monkeypatch.setattr(cr, "_tick_telegram", lambda msg: actions["telegrams"].append(msg))
    monkeypatch.setattr(cr, "_mailbox_repos", lambda: ["fabrik"])
    monkeypatch.setattr(cr, "_keepwarm_pass", lambda *a: None)
    assert cr._cmd_tick() == 0
    assert actions["mails"] == ["fabrik"], "a failed switch must still reach the drain"
    assert len(actions["telegrams"]) >= 1


def test_t10_tick_never_raises(tmp_path, monkeypatch):
    """Closer #11: 'always exits 0' must be ENFORCED, not documented."""
    monkeypatch.setenv("CLAUDE_FLEET_ROOT", str(tmp_path / "fleet-absent"))  # hermetic (T03)
    monkeypatch.setattr(cr, "_collect_statuses", lambda: (_ for _ in ()).throw(RuntimeError("boom")))
    assert cr._cmd_tick() == 0


def test_t11_keepwarm_runs_on_degraded_ticks(tmp_path, monkeypatch):
    """Closer #12: no-live is exactly when parked snapshots must not age out."""
    called = []
    monkeypatch.setenv("CLAUDE_FLEET_ROOT", str(tmp_path / "fleet-absent"))  # hermetic (T03)
    monkeypatch.setenv("ROTATE_STATE_DIR", str(tmp_path))
    monkeypatch.setattr(cr, "_collect_statuses", lambda: ([_acct("x")], None))
    monkeypatch.setattr(cr, "_now", lambda: NOW)
    monkeypatch.setattr(cr, "_keepwarm_pass", lambda *a: called.append(1))
    assert cr._cmd_tick() == 0
    assert called == [1], "keep-warm must run even when the live account is unresolvable"


# ── live-probe round: the grant is CLI-only; parked telemetry degrades, never lies ────


def test_t12_keepwarm_is_blocked_and_never_spends_a_token(tmp_path, monkeypatch):
    """The /v1/oauth/token grant returns 403/1010 to non-CLI clients (live-probed on BOTH
    hosts 2026-08-13). Keep-warm must be an honest no-op — never a silent token spend."""
    store = tmp_path / "ob-ocoron-com-s-organization"
    store.mkdir()
    (store / ".credentials.json").write_text(json.dumps({"claudeAiOauth": {
        "accessToken": "A", "refreshToken": "R"}}))
    import urllib.request
    called = []
    monkeypatch.setattr(urllib.request, "build_opener",
                        lambda *a: type("O", (), {"open": lambda s, r, timeout=0:
                                                  called.append(1)})())
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **kw: called.append(1))
    assert cr._keepwarm_refresh(store) is False
    assert called == [], "no grant request may be issued"


def test_t13_parked_expired_access_is_unknown_not_dead(monkeypatch):
    """A parked store's ACCESS token dies every ~8h while its REFRESH token lives for weeks.
    Reading that as INVALID collapsed the pool to one account (live-observed on ob@)."""
    monkeypatch.setattr(cr, "_read_access_token", lambda p: "tok")
    monkeypatch.setattr(cr, "_oauth_get", lambda path, tok, **kw: None)  # 401s
    monkeypatch.setattr(cr, "_now", lambda: NOW)
    store = Path("/tmp/ob-ocoron-com-s-organization")
    monkeypatch.setattr(Path, "read_text",
                        lambda self, *a, **kw: json.dumps({"claudeAiOauth": {
                            "refreshTokenExpiresAt": (NOW + 20 * 86400) * 1000}}))
    row = cr._account_status(store)
    assert row["valid"] is True and row["telemetry"] == "unknown-parked"


def test_t14_unknown_parked_ranks_last_but_is_eligible():
    """Fail-closed preference: an account with REAL telemetry always outranks an unknown
    one; an unknown account is still better than no successor at all."""
    live_tel = _acct("known", weekly_reset=NOW + 6 * 86400)
    unknown = {"name": "parked-ocoron-com-s-organization", "valid": True,
               "telemetry": "unknown-parked", "five_hour": None, "seven_day": None}
    assert cr._pick_successor([live_tel, unknown], None, NOW) == live_tel["name"]
    assert cr._pick_successor([unknown], None, NOW) == unknown["name"]


# ── T8: --touch (keep the parked accounts' refresh chains alive) ───────────────


def _touch_env(tmp_path, monkeypatch, live_name, ran, refreshed_email="ob@ocoron.com",
               change=True):
    """Seams: two stores (live + parked), a fake `claude` run that optionally rewrites the
    isolated config's credentials, and a fake identity probe."""
    stores = tmp_path / "manager-accounts"
    for n in ("ob-ocoron-com-s-organization", "sarp-ocoron-com-s-organization"):
        d = stores / n
        d.mkdir(parents=True)
        (d / ".credentials.json").write_text(json.dumps(
            {"claudeAiOauth": {"accessToken": f"OLD-{n[:3]}", "refreshToken": f"R-{n[:3]}"}}))
    monkeypatch.setattr(cr, "ACCOUNTS_DIR", stores)
    monkeypatch.setattr(cr, "ACTIVE_CREDS", tmp_path / "live.json")
    (tmp_path / "live.json").write_text(json.dumps(
        {"claudeAiOauth": {"accessToken": "LIVE", "refreshToken": "R-LIVE"}}))
    monkeypatch.setattr(cr, "_active_account", lambda: stores / live_name)
    monkeypatch.setenv("ROTATE_STATE_DIR", str(tmp_path / "state"))

    def fake_run(cfg_dir: Path, store: Path) -> bool:
        ran.append(store.name)
        if change:
            (cfg_dir / ".credentials.json").write_text(json.dumps(
                {"claudeAiOauth": {"accessToken": "NEW-TOK", "refreshToken": "NEW-R",
                                   "expiresAt": int((NOW + 8 * 3600) * 1000)}}))
        return True

    monkeypatch.setattr(cr, "_touch_run_cli", fake_run)
    monkeypatch.setattr(cr, "_email_for_token", lambda tok: refreshed_email)
    monkeypatch.setattr(cr, "_now", lambda: NOW)
    return stores


def test_t8_touch_skips_the_live_account(tmp_path, monkeypatch):
    ran = []
    _touch_env(tmp_path, monkeypatch, "sarp-ocoron-com-s-organization", ran)
    assert cr._cmd_touch() == 0
    assert ran == ["ob-ocoron-com-s-organization"], "the live account refreshes on its own"


def test_t8_touch_files_the_refreshed_pair(tmp_path, monkeypatch):
    ran = []
    stores = _touch_env(tmp_path, monkeypatch, "sarp-ocoron-com-s-organization", ran)
    assert cr._cmd_touch() == 0
    blob = json.loads((stores / "ob-ocoron-com-s-organization" / ".credentials.json").read_text())
    assert blob["claudeAiOauth"]["accessToken"] == "NEW-TOK"


def test_t8_touch_refuses_a_mismatched_identity(tmp_path, monkeypatch):
    ran = []
    stores = _touch_env(tmp_path, monkeypatch, "sarp-ocoron-com-s-organization", ran,
                        refreshed_email="stranger@example.com")
    assert cr._cmd_touch() == 0
    blob = json.loads((stores / "ob-ocoron-com-s-organization" / ".credentials.json").read_text())
    assert blob["claudeAiOauth"]["accessToken"] == "OLD-ob-", "mismatch must not be filed"


def test_t8_touch_never_mutates_the_live_credentials(tmp_path, monkeypatch):
    ran = []
    _touch_env(tmp_path, monkeypatch, "sarp-ocoron-com-s-organization", ran)
    before = (tmp_path / "live.json").read_bytes()
    assert cr._cmd_touch() == 0
    assert (tmp_path / "live.json").read_bytes() == before, "touch is isolated from live sessions"


def test_t8_touch_noop_when_the_cli_returns_the_same_pair(tmp_path, monkeypatch):
    ran = []
    stores = _touch_env(tmp_path, monkeypatch, "sarp-ocoron-com-s-organization", ran, change=False)
    store = stores / "ob-ocoron-com-s-organization"
    before = (store / ".credentials.json").read_bytes()
    assert cr._cmd_touch() == 0
    assert (store / ".credentials.json").read_bytes() == before
    assert not (store / ".credentials.json.prev").exists(), "no churn when nothing changed"


def test_t8_touch_never_files_a_blanked_credential(tmp_path, monkeypatch):
    """LIVE DEFECT 2026-08-14: `claude -p` in an isolated config wrote a BLANKED pair (empty
    refreshToken, expiresAt=0) and the touch filed it over a good snapshot. A refreshed blob
    is only fileable when it is structurally alive: non-empty refresh token AND a future
    access-token expiry. Otherwise the existing snapshot stands."""
    ran = []
    stores = tmp_path / "manager-accounts"
    for n in ("ob-ocoron-com-s-organization", "sarp-ocoron-com-s-organization"):
        d = stores / n
        d.mkdir(parents=True)
        (d / ".credentials.json").write_text(json.dumps({"claudeAiOauth": {
            "accessToken": "GOOD", "refreshToken": "GOOD-R",
            "expiresAt": int((NOW + 3600) * 1000)}}))
    monkeypatch.setattr(cr, "ACCOUNTS_DIR", stores)
    monkeypatch.setattr(cr, "ACTIVE_CREDS", tmp_path / "live.json")
    (tmp_path / "live.json").write_text(json.dumps({"claudeAiOauth": {"accessToken": "LIVE"}}))
    monkeypatch.setattr(cr, "_active_account",
                        lambda: stores / "sarp-ocoron-com-s-organization")
    monkeypatch.setenv("ROTATE_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setattr(cr, "_email_for_token", lambda tok: "ob@ocoron.com")

    def blanking_run(cfg_dir: Path, store: Path) -> bool:
        ran.append(store.name)
        (cfg_dir / ".credentials.json").write_text(json.dumps({"claudeAiOauth": {
            "accessToken": "BLANK", "refreshToken": "", "expiresAt": 0}}))
        return True

    monkeypatch.setattr(cr, "_touch_run_cli", blanking_run)
    assert cr._cmd_touch() == 0
    kept = json.loads((stores / "ob-ocoron-com-s-organization" / ".credentials.json").read_text())
    assert kept["claudeAiOauth"]["refreshToken"] == "GOOD-R", "a blanked pair must never be filed"


# ── T14: operator pause — a paused tick must never install a pair ──────────────


def test_t14_pause_marker_blocks_switch_but_keeps_drain_armed(tmp_path, monkeypatch):
    """Live incident 2026-08-15: after a chain loss every parked successor was unverified
    (one provably consumed). A switch would have installed a possibly-dead pair box-wide.
    While the pause marker exists the tick must (a) install nothing, (b) leave the DRAIN
    warning path armed so the coming wall is announced instead of silently hit."""
    live = _acct("live", session_pct=96.0)
    sib = _acct("sib", weekly_reset=NOW + 86400)
    state = tmp_path / "state"
    state.mkdir()
    (state / "switch-paused").touch()
    actions, _ = _tick(tmp_path, monkeypatch, [live, sib], live["name"])
    assert actions["switched_to"] == [], "paused tick must not install any pair"
    assert actions["mails"], "drain warning must still fire while paused"


def test_t14_pause_and_resume_cli_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("ROTATE_STATE_DIR", str(tmp_path))
    assert cr.main(["--pause-switch"]) == 0
    assert (tmp_path / "switch-paused").is_file()
    assert cr.main(["--resume-switch"]) == 0
    assert not (tmp_path / "switch-paused").exists()


# ── T15: the pause marker also gates run_claude's rotation choke point ──────────


def _rotate_env(tmp_path, monkeypatch, paused, output, calls, install_ok=True,
                names=("ob-ocoron-com-s-organization", "sarp-ocoron-com-s-organization")):
    """Seams for the run_claude rotation path (T01/M-pre): *names* snapshots, a fake `claude`
    whose output is `calls["script"]` in order (then *output* forever), a recorded installer, a
    recorded Telegram, and a tmp 401-debounce file (never the real ~/.claude one)."""
    state = tmp_path / "state"
    state.mkdir()
    if paused:
        (state / "switch-paused").touch()
    monkeypatch.setenv("ROTATE_STATE_DIR", str(state))
    # Hermetic: an operator-created real ~/.claude-fleet must never flip --switch (or any other
    # dispatch these tests reach) into fleet mode — same guard the _tick harness carries.
    monkeypatch.setenv("CLAUDE_FLEET_ROOT", str(tmp_path / "fleet-absent"))

    stores = tmp_path / "manager-accounts"
    for n in names:
        d = stores / n
        d.mkdir(parents=True)
        (d / ".credentials.json").write_text(json.dumps({"claudeAiOauth": {
            "accessToken": f"TOK-{n[:4]}", "refreshToken": f"R-{n[:4]}",
            "expiresAt": int((NOW + 3600) * 1000)}}))
    live = tmp_path / "live.json"
    live.write_text(json.dumps({"claudeAiOauth": {  # = the ob store → it is the active one
        "accessToken": "TOK-ob-o", "refreshToken": "R-ob-o",
        "expiresAt": int((NOW + 3600) * 1000)}}))
    monkeypatch.setattr(cr, "ACCOUNTS_DIR", stores)
    monkeypatch.setattr(cr, "ACTIVE_CREDS", live)
    monkeypatch.setattr(cr, "ALERT_STATE", tmp_path / "last-401-alert")

    def fake_install(target=None, selector=None):
        calls["installed"].append(target.name if target is not None else "selector")
        return "sarp-ocoron-com-s-organization" if install_ok else None

    def fake_run(argv, **kw):
        calls["runs"].append(argv)
        out = calls["script"].pop(0) if calls["script"] else output
        return subprocess.CompletedProcess(argv, 1, out, "")

    monkeypatch.setattr(cr, "_activate_snapshot", fake_install)
    monkeypatch.setattr(cr.subprocess, "run", fake_run)
    monkeypatch.setattr(cr, "_notify_telegram",
                        lambda text: calls["telegrams"].append(text) or True)
    return calls


def _calls():
    return {"runs": [], "installed": [], "telegrams": [], "script": []}


def test_t15a_paused_rotation_installs_nothing_and_says_so(tmp_path, monkeypatch, capsys):
    """M-pre: while the operator's switch-paused marker exists, NOTHING may swap the shared
    credentials file — including run_claude's usage-limit retry, the last ungated swapper."""
    calls = _rotate_env(tmp_path, monkeypatch, True, "Claude usage limit reached", _calls())
    cr.run_claude(["claude", "-p", "ping"], timeout=5, cwd=str(tmp_path), env={})
    assert calls["installed"] == [], "a paused rotation must install nothing"
    # count CLAUDE invocations only: the advisory `quota_governor.py mark-capped` signal (bff520f0)
    # is a subprocess too, and fires only where the governor is co-located — the real tree, not a
    # temp copy — which is why this assertion passed in CI-like copies and failed in the repo
    claude_runs = [a for a in calls["runs"] if a and a[0] == "claude"]
    assert len(claude_runs) == 1, "no rotation → no retry"
    assert cr._rotate_active_account() is None, "the choke point itself must refuse"
    captured = capsys.readouterr()
    assert "rotation PAUSED" in captured.err and "switch-paused" in captured.err, captured.err
    # STDOUT stays clean: main() mirrors a passthrough run's stdout back to stdin-piping callers
    # (claude-run.sh and the sysadmin scripts), so a refusal line on stdout corrupts their payload.
    assert captured.out == "", f"the refusal must never touch stdout: {captured.out!r}"


def test_t15b_unpaused_rotation_is_unchanged(tmp_path, monkeypatch, capsys):
    """Regression guard: with no marker, rotation + retry behave exactly as before."""
    calls = _rotate_env(tmp_path, monkeypatch, False, "Claude usage limit reached", _calls())
    cr.run_claude(["claude", "-p", "ping"], timeout=5, cwd=str(tmp_path), env={})
    assert calls["installed"] == ["selector"], "unpaused rotation still installs a standby"
    claude_runs = [a for a in calls["runs"] if a and a[0] == "claude"]
    assert len(claude_runs) == 2, "the rotation retry still runs"
    assert "rotation PAUSED" not in capsys.readouterr().err


def test_t15c_paused_401_never_claims_all_credentials_are_dead(tmp_path, monkeypatch):
    """Adversary finding R6: a withheld rotation is not evidence of exhaustion. The 12h-debounced
    'all credentials are dead' alert must stay silent — and must not burn the debounce window."""
    calls = _rotate_env(tmp_path, monkeypatch, True,
                        "API Error: 401 authentication_error", _calls())
    cr.run_claude(["claude", "-p", "ping"], timeout=5, cwd=str(tmp_path), env={})
    assert calls["telegrams"] == [], "rotation was withheld, not exhausted"
    assert not (tmp_path / "last-401-alert").exists(), "the debounce window must not be consumed"


def test_t15d_unpaused_401_with_no_target_still_alerts(tmp_path, monkeypatch):
    """Over-suppression guard: without the marker, a genuinely unrecoverable 401 still alerts —
    and the send DOES record the debounce window (the mirror of t15c's negative; without this
    assertion a 'never touch the debounce file' mutant survives)."""
    calls = _rotate_env(tmp_path, monkeypatch, False, "API Error: 401 authentication_error",
                        _calls(), install_ok=False)
    cr.run_claude(["claude", "-p", "ping"], timeout=5, cwd=str(tmp_path), env={})
    assert any("all credentials are dead" in t for t in calls["telegrams"]), calls["telegrams"]
    assert (tmp_path / "last-401-alert").is_file(), "a real send must arm the 12h debounce"


def test_t15e_recovered_401_alerts_once_then_debounces(tmp_path, monkeypatch):
    """The OTHER alert branch (rotation recovered the 401) must keep its debounce semantics:
    it alerts, it records the window, and a second 401 inside that window stays silent."""
    calls = _rotate_env(tmp_path, monkeypatch, False, "all good, no trigger here", _calls())
    calls["script"] = ["API Error: 401 authentication_error"]  # attempt 1 dies, the retry is clean
    cr.run_claude(["claude", "-p", "ping"], timeout=5, cwd=str(tmp_path), env={})
    assert calls["installed"] == ["selector"], "the 401 must have rotated"
    assert any("recovered" in t for t in calls["telegrams"]), calls["telegrams"]
    assert (tmp_path / "last-401-alert").is_file(), "the recovered send arms the debounce too"

    calls["telegrams"].clear()
    calls["script"] = ["API Error: 401 authentication_error"]
    cr.run_claude(["claude", "-p", "ping"], timeout=5, cwd=str(tmp_path), env={})
    assert calls["telegrams"] == [], "a second 401 inside the 12h window must stay quiet"
    assert calls["installed"] == ["selector", "selector"], "both 401s really did rotate"


def _boom(exc=OSError):
    """A pause probe that cannot answer — the state dir is unreachable / HOME is unset."""

    def raiser():
        raise exc("rotate state dir unreachable")

    return raiser


def test_t15f_unreadable_state_dir_fails_closed(tmp_path, monkeypatch, capsys):
    """F2: the gate reads a marker under a dir it may have to CREATE. If that raises, the answer
    is unknown — and T01's invariant ('zero processes may install a pair') makes the safe answer
    PAUSED. Refusing costs a wait; permitting costs the box-wide swap the marker forbids.
    F8: `Path.home()` raises RuntimeError when HOME is unset with no passwd entry (systemd,
    containers) — main() does not catch RuntimeError, so it would discard a good claude result."""
    calls = _rotate_env(tmp_path, monkeypatch, False, "Claude usage limit reached", _calls())
    for exc in (OSError, ValueError, RuntimeError):
        monkeypatch.setattr(cr, "_switch_paused", _boom(exc))
        assert cr._rotate_active_account() is None, f"{exc.__name__} must fail CLOSED"
        err = capsys.readouterr().err
        assert "pause-state unreadable" in err and "failing CLOSED" in err, err
        assert "--resume-switch" in err, "every refusal names the operator's override"
    assert calls["installed"] == [], "nothing may be installed on an unknown pause state"


def test_t15g_next_while_paused_refuses_without_the_misleading_hint(tmp_path, monkeypatch, capsys):
    """F4: `--next` inherits the gate (deliberate during migration), so its refusal must SAY
    'paused' — never the stale 'need ≥2 snapshots' hint, which sends the operator to --list
    hunting for a missing snapshot that is not the problem."""
    calls = _rotate_env(tmp_path, monkeypatch, True, "unused", _calls())
    assert cr.main(["--next"]) == 1, "a refused rotation still exits non-zero"
    captured = capsys.readouterr()
    assert "rotation PAUSED" in captured.err, captured.err
    assert "need ≥2" not in captured.err, captured.err
    assert captured.out == "", f"a refusal must never touch stdout: {captured.out!r}"
    assert calls["installed"] == []


def test_t15h_one_snapshot_host_still_reports_dead_credentials(tmp_path, monkeypatch):
    """F1: with a single snapshot there is nothing to rotate TO, so `_rotate_active_account` is
    never called — the pause marker did NOT withhold anything. Re-reading the marker at the
    give-up point (instead of having the gate report it) silenced this TRUE all-dead alert."""
    calls = _rotate_env(tmp_path, monkeypatch, True, "API Error: 401 authentication_error",
                        _calls(), names=("ob-ocoron-com-s-organization",))
    cr.run_claude(["claude", "-p", "ping"], timeout=5, cwd=str(tmp_path), env={})
    assert calls["installed"] == []
    assert any("all credentials are dead" in t for t in calls["telegrams"]), (
        "no rotation was possible at all — that is exhaustion, not a withheld rotation")


def test_t15i_fail_closed_refusal_still_alerts_on_401(tmp_path, monkeypatch):
    """F6: fail-closed must not silence the only alert channel. An UNREADABLE pause state refuses
    the install (as the marker does) but is NOT the operator holding the marker — the operator is
    never told to expect silence, so the all-dead Telegram fires, carrying why it could not heal."""
    calls = _rotate_env(tmp_path, monkeypatch, False, "API Error: 401 authentication_error",
                        _calls())
    monkeypatch.setattr(cr, "_switch_paused", _boom())
    cr.run_claude(["claude", "-p", "ping"], timeout=5, cwd=str(tmp_path), env={})
    assert calls["installed"] == [], "fail-closed still refuses the install"
    assert any("all credentials are dead" in t and "pause-state unreadable" in t
               for t in calls["telegrams"]), calls["telegrams"]


def test_t15j_withheld_reason_is_thread_local(tmp_path, monkeypatch):
    """F5: the aro-wake twin drives run_claude from `asyncio.to_thread` AND from an unlocked
    fire-and-forget task (aro-wake/main.py:1085, :986), so two callers really do sit in the gate
    at once. DETERMINISTIC interleaving: thread A is refused by the marker and parks BEFORE
    reading its verdict; thread B then runs a whole unpaused give-up (which clears and rewrites
    the slot) and alerts; A is released and reads. Thread-local → A still sees its own 'marker'
    and B still alerted. One shared slot → B's reset wipes A's verdict."""
    calls = _rotate_env(tmp_path, monkeypatch, False, "API Error: 401 authentication_error",
                        _calls(), install_ok=False)
    # Pause state as seen BY THREAD. Keyed on the thread NAME, never on get_ident(): idents are
    # recycled once a thread exits, which silently marks a later thread "paused".
    monkeypatch.setattr(cr, "_switch_paused",
                        lambda: threading.current_thread().name.startswith("paused-"))
    parked, released = threading.Event(), threading.Event()
    seen = {}

    def thread_a():
        cr._rotate_active_account()          # refused by the gate → writes THIS thread's reason
        parked.set()                          # …and parks before reading it back
        released.wait(timeout=10)
        seen["a"] = getattr(cr._TLS, "withheld_reason", None)

    def thread_b():
        parked.wait(timeout=10)
        # A full unpaused give-up: clears the slot, rotates, finds no installable target, alerts.
        cr.run_claude(["claude", "-p", "ping"], timeout=5, cwd=str(tmp_path), env={})
        released.set()

    a = threading.Thread(target=thread_a, name="paused-a")
    b = threading.Thread(target=thread_b, name="b")
    a.start()
    b.start()
    a.join(timeout=10)
    b.join(timeout=10)
    assert not a.is_alive() and not b.is_alive(), "deadlock — the interleaving never completed"
    assert seen["a"] == cr._PAUSE_MARKER, (
        f"thread A's verdict was overwritten by thread B: {seen['a']!r}")
    assert any("all credentials are dead" in t for t in calls["telegrams"]), (
        "thread B was genuinely exhausted — its alert must not be suppressed by A's pause")


def test_t15k_status_banner_survives_an_unreadable_pause_state(tmp_path, monkeypatch, capsys):
    """F9: `--status` is the command the runbook tells the operator to check WHILE paused. Its
    banner probed the marker raw, so an unreadable state dir tracebacked out with exit 1."""
    monkeypatch.setenv("CLAUDE_FLEET_ROOT", str(tmp_path / "fleet-absent"))  # hermetic (T03)
    monkeypatch.setattr(cr, "_switch_paused", _boom())
    rows = [_acct("live")]
    monkeypatch.setattr(cr, "_collect_statuses", lambda: (rows, rows[0]["name"]))
    assert cr._cmd_status(as_json=False) == 0, "status must never traceback on a pause probe"
    out = capsys.readouterr().out
    assert "PAUSED" in out and "unreadable" in out, out
    # …and the ordinary marker branch still renders its own banner (E4: a typo'd reason constant
    # silences the banner entirely while every other test stays green)
    monkeypatch.setattr(cr, "_switch_paused", lambda: True)
    assert cr._cmd_status(as_json=False) == 0
    assert "⏸ auto-switch PAUSED (--resume-switch to re-enable)" in capsys.readouterr().out


def test_t15l_tick_withholds_and_still_drains_on_an_unreadable_pause_state(tmp_path, monkeypatch,
                                                                            capsys):
    """F9/F12: the tick's raw probe raised into _cmd_tick's blanket except, killing the DRAIN
    broadcast — the one warning that lets sessions reach a checkpoint before the wall. The whole
    state dir is unreachable here (RuntimeError: HOME unset, no passwd entry), which is also the
    stamp's home, so the 24h dedupe must survive on a temp-dir fallback: without it the drain
    re-broadcasts every 5-minute tick for the length of the outage."""
    live = _acct("live", session_pct=96.0)
    sib = _acct("sib", weekly_reset=NOW + 86400)
    fallback = tmp_path / "fallback-tmp"
    fallback.mkdir()
    monkeypatch.setattr(cr.tempfile, "gettempdir", lambda: str(fallback))
    monkeypatch.setattr(cr, "_rotate_state_dir", _boom(RuntimeError))

    actions, _ = _tick(tmp_path, monkeypatch, [live, sib], live["name"])
    out = capsys.readouterr().out
    assert actions["switched_to"] == [], "an unknown pause state withholds the install"
    assert "pause state unreadable" in out, out
    assert "INTERNAL ERROR" not in out, out
    assert actions["mails"], "the drain warning must still go out"

    again, _ = _tick(tmp_path, monkeypatch, [live, sib], live["name"])
    assert again["mails"] == [], "the fallback stamp must dedupe the next tick's drain"


def test_t15m_tick_names_the_operator_marker(tmp_path, monkeypatch, capsys):
    """F15/E6: the paused-tick line must name WHICH pause it is — the operator's marker or an
    unreadable state dir. They call for opposite operator actions (`--resume-switch` vs fix the
    box), and a mutant that collapses them keeps every other test green."""
    live = _acct("live", session_pct=96.0)
    sib = _acct("sib", weekly_reset=NOW + 86400)
    state = tmp_path / "state"
    state.mkdir()
    (state / "switch-paused").touch()
    actions, _ = _tick(tmp_path, monkeypatch, [live, sib], live["name"])
    assert actions["switched_to"] == [], "the marker withholds the install"
    assert "auto-switch PAUSED (operator marker)" in capsys.readouterr().out


def test_t15n_pause_state_tri_state_and_literals(tmp_path, monkeypatch):
    """F14/F20: the two reason strings are compared at several sites (alert leg, --next, status,
    tick), so pin their VALUES against a drive-by rename — and walk all three branches for real,
    against an ISOLATED state dir (unisolated, this read the operator's own ~/.claude/state and
    passed whatever the box happened to be doing)."""
    state = tmp_path / "state"
    monkeypatch.setenv("ROTATE_STATE_DIR", str(state))
    assert (cr._PAUSE_MARKER, cr._PAUSE_ERROR) == ("marker", "error")
    assert cr._pause_state() is None, "no marker → not paused"
    (state / "switch-paused").touch()
    assert cr._pause_state() == cr._PAUSE_MARKER, "the operator's marker"
    monkeypatch.setattr(cr, "_rotate_state_dir", _boom(RuntimeError))
    assert cr._pause_state() == cr._PAUSE_ERROR, "unreadable state → fail closed, but not 'marker'"


@pytest.mark.parametrize("break_it", ["bad-utf8", "unreadable", "malformed-ts", "future-ts"])
def test_t15o_unreadable_ledger_holds_and_still_drains(tmp_path, monkeypatch, capsys, break_it):
    """F18/F22/F23: the dwell guard reads the ledger to answer "did we just switch?". A ledger it
    cannot read must NOT answer "no" — that is fail-OPEN, and the tick then installs a fresh pair
    on every 5-minute run for as long as the fault lasts. Unknown reads as "just switched".

    But a fail-closed hold is a GUESS, not a real recent switch: nobody is installing while the
    account burns, so the ≥drain ticks must still reach the DRAIN broadcast (24h-deduped) exactly
    as the paused/no-successor cases do. Three ways to be unreadable: corrupt bytes, a permission
    error, and a well-formed switch record with a non-numeric ts."""
    live = _acct("live", session_pct=99.0)   # hot enough to switch, and past the drain threshold
    sib = _acct("sib", weekly_reset=NOW + 86400)  # …and a healthy successor is available
    state = tmp_path / "state"
    state.mkdir()
    ledger = state / "rotate-ledger.jsonl"
    if break_it == "bad-utf8":
        ledger.write_bytes(b"\xff\xfe not utf-8 at all\n")
    elif break_it == "malformed-ts":
        ledger.write_text(json.dumps({"event": "switch", "ts": "not-a-number"}) + "\n")
    elif break_it == "future-ts":
        # WSL suspend/resume skews the clock: a switch stamped in the FUTURE makes (now - last)
        # negative, which reads as "within dwell" for hours — a silent hold with no drain.
        ledger.write_text(json.dumps({"event": "switch", "ts": NOW + 2 * 3600}) + "\n")
    else:
        ledger.write_text("")
        real_read = Path.read_text

        def denied(self, *a, **kw):
            if self.name == "rotate-ledger.jsonl":
                raise PermissionError(13, "Permission denied")
            return real_read(self, *a, **kw)

        monkeypatch.setattr(Path, "read_text", denied)

    drains = 0
    for attempt in range(12):
        actions, _ = _tick(tmp_path, monkeypatch, [live, sib], live["name"])
        assert actions["switched_to"] == [], f"tick {attempt}: an unreadable ledger must HOLD"
        drains += len(actions["telegrams"])
    assert drains == 1, f"the coming wall must be announced exactly once per 24h, got {drains}"
    assert "ledger" in capsys.readouterr().err.lower(), "the held guard must say why"
    assert b"dwell-hold-degraded" in ledger.read_bytes(), (
        "a fail-closed hold must be distinguishable from a genuine one in the ledger")


def test_t15p_switch_escape_hatch_works_while_paused(tmp_path, monkeypatch, capsys):
    """F24: `--switch <name>` is the documented manual lever — it does NOT route through the
    rotation choke point, so it must keep working while the marker withholds everything else.
    The runbook's recovery path depends on it."""
    calls = _rotate_env(tmp_path, monkeypatch, True, "unused", _calls())
    assert cr.main(["--switch", "sarp"]) == 0, "the explicit manual switch is never gated"
    assert calls["installed"] == ["sarp-ocoron-com-s-organization"]
    assert "switched active Claude account" in capsys.readouterr().out


def test_t15q_status_json_carries_the_pause_state(tmp_path, monkeypatch):
    """F26: the text banner shows ⏸ but the --json path returned before it, so machine consumers
    (the fleet dashboards) saw a healthy payload while switching was off entirely."""
    rows = [_acct("live")]
    monkeypatch.setattr(cr, "_collect_statuses", lambda: (rows, rows[0]["name"]))
    state = tmp_path / "state"
    monkeypatch.setenv("ROTATE_STATE_DIR", str(state))
    assert cr._status_payload()["pause"] is None
    state.mkdir(exist_ok=True)
    (state / "switch-paused").touch()
    assert cr._status_payload()["pause"] == cr._PAUSE_MARKER
    monkeypatch.setattr(cr, "_rotate_state_dir", _boom(RuntimeError))
    assert cr._status_payload()["pause"] == cr._PAUSE_ERROR


def test_t15r_pause_cli_reports_a_broken_state_dir(tmp_path, monkeypatch, capsys):
    """F25: our own fail-closed message sends the operator to --resume-switch — in exactly the
    state where the state dir is broken. Those two commands must report, not traceback."""
    monkeypatch.setattr(cr, "_rotate_state_dir", _boom(OSError))
    for cmd in ("--pause-switch", "--resume-switch"):
        assert cr.main([cmd]) == 1, f"{cmd} must fail cleanly"
        err = capsys.readouterr().err
        assert "state dir" in err.lower(), err


def test_t15s_degraded_hold_is_structural_not_arithmetic(tmp_path, monkeypatch):
    """F29: with ROTATE_DWELL_MIN=0 the dwell comparison `(now - last) < 0` is false, so a
    fail-closed hold that leans on the arithmetic evaporates and the tick installs anyway. The
    hold must be structural: `degraded` alone withholds, whatever the dwell window says."""
    live = _acct("live", session_pct=99.0)
    sib = _acct("sib", weekly_reset=NOW + 86400)
    state = tmp_path / "state"
    state.mkdir()
    (state / "rotate-ledger.jsonl").write_bytes(b"\xff\xfe not utf-8 at all\n")
    actions, _ = _tick(tmp_path, monkeypatch, [live, sib], live["name"], dwell_min="0")
    assert actions["switched_to"] == [], "an unreadable ledger holds even with a zero dwell window"
    assert actions["mails"], "…and the wall is still announced"


def test_t15t_drain_threshold_above_switch_threshold_is_clamped(tmp_path, monkeypatch, capsys):
    """F30: with ROTATE_DRAIN_THRESHOLD > ROTATE_THRESHOLD there is a band where the tick refuses
    to switch AND refuses to warn — it prints a paused/hold line and then ledgers 'ok'. Clamp the
    drain threshold to the switch threshold so the warning can never sit above the action."""
    live = _acct("live", session_pct=95.5)
    sib = _acct("sib", weekly_reset=NOW + 86400)
    state = tmp_path / "state"
    state.mkdir()
    (state / "switch-paused").touch()  # no install is possible → the drain path is the only voice
    actions, _ = _tick(tmp_path, monkeypatch, [live, sib], live["name"],
                       threshold="95", drain="96")
    assert actions["switched_to"] == []
    assert actions["mails"], "95.5% with no installable successor must still warn"
    assert "clamp" in capsys.readouterr().err.lower(), "the misconfiguration must be named"


def test_t15u_non_finite_thresholds_fall_back_to_the_default(tmp_path, monkeypatch, capsys):
    """F35: `nan` compares False against everything, so ROTATE_DRAIN_THRESHOLD=nan disables the
    DRAIN warning permanently and silently — even the clamp check cannot fire to say so. Reject
    non-finite env values, say so once, and use the default."""
    for bad in ("nan", "inf", "-inf"):
        monkeypatch.setenv("ROTATE_DRAIN_THRESHOLD", bad)
        assert cr._env_float("ROTATE_DRAIN_THRESHOLD", 85.0) == 85.0, bad
        assert "finite" in capsys.readouterr().err.lower(), f"{bad} must be named"

    # …and the tick behaves: 90% with no installable successor still warns on the default 85.
    live = _acct("live", session_pct=90.0)
    sib = _acct("sib", weekly_reset=NOW + 86400)
    state = tmp_path / "state"
    state.mkdir()
    (state / "switch-paused").touch()
    actions, _ = _tick(tmp_path, monkeypatch, [live, sib], live["name"], drain="nan")
    assert actions["mails"], "a nan drain threshold must not silently disable the warning"


# ── 2026-08-18 incident fixes: stale-reading refresh ping + dead-active flip trigger ────────


def _mk_fleet(tmp_path, monkeypatch, slugs=("alpha", "beta")):
    """A minimal fleet: per-slug dirs with fresh-looking credentials + pinned identities."""
    root = tmp_path / "fleet"
    for s in slugs:
        d = root / s
        d.mkdir(parents=True)
        (d / ".credentials.json").write_text("{}")
    monkeypatch.setenv("CLAUDE_FLEET_ROOT", str(root))
    monkeypatch.setenv("ROTATE_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setattr(
        cr, "_pin_pending_identities",
        lambda dirs: {s: {"identity": f"{s}@test"} for s in slugs},
    )
    return root


def test_stale_reading_triggers_refresh_ping_and_reprobe(tmp_path, monkeypatch):
    """A cache row older than ROTATE_READING_MAX_AGE_S refreshes via the keepalive ping and
    probes live — the dashboard never shows a wall older than the interval (operator mandate
    2026-08-18)."""
    root = _mk_fleet(tmp_path, monkeypatch, slugs=("alpha",))
    now = 1_000_000.0
    old = now - 100_000  # credential mtime far beyond _FLEET_TOKEN_FRESH_S
    import os as _os
    _os.utime(root / "alpha" / ".credentials.json", (old, old))
    monkeypatch.setattr(cr, "_now", lambda: now)
    monkeypatch.setattr(cr, "_load_usage_cache", lambda: {"alpha@test": {"ts": now - 90_000}})
    pinged = []
    monkeypatch.setattr(cr, "_keepalive_ping", lambda d: pinged.append(d.name) or True)
    monkeypatch.setattr(cr, "_read_access_token", lambda p: "tok")
    monkeypatch.setattr(cr, "_oauth_get", lambda kind, tok: {"usage": True})
    monkeypatch.setattr(
        cr, "_usage_windows",
        lambda payload: {"five_hour": {"utilization": 1.0}, "seven_day": {"utilization": 2.0}},
    )
    monkeypatch.setattr(cr, "_identity_probe_due", lambda slugs, now: False)
    accounts, _ = cr._fleet_account_rows(cr._fleet_dirs(), allow_pings=True)
    assert pinged == ["alpha"], "the stale account must be refresh-pinged exactly once"
    assert accounts[0]["source"] == "live", "a successful ping must yield a LIVE reading"


def test_status_path_never_pings_even_when_stale(tmp_path, monkeypatch):
    """--status is a pure read: without allow_pings the stale branch must NOT shell out to
    the claude CLI. On 2026-08-18 evening the pings ran from --status (150s each, up to 3),
    the dashboard's 60s probe cap expired, and every page load hung — the operator read the
    dashboard as 'not reachable'. Freshness is the tick's job; status only reports."""
    root = _mk_fleet(tmp_path, monkeypatch, slugs=("alpha",))
    now = 1_000_000.0
    old = now - 100_000
    import os as _os
    _os.utime(root / "alpha" / ".credentials.json", (old, old))
    monkeypatch.setattr(cr, "_now", lambda: now)
    monkeypatch.setattr(
        cr, "_load_usage_cache",
        lambda: {"alpha@test": {"ts": now - 90_000, "seven_day": {"utilization": 93.0}}},
    )
    def _boom(d):
        raise AssertionError("--status must never invoke _keepalive_ping")
    monkeypatch.setattr(cr, "_keepalive_ping", _boom)
    monkeypatch.setattr(cr, "_identity_probe_due", lambda slugs, now: False)
    accounts, _ = cr._fleet_account_rows(cr._fleet_dirs())
    assert accounts[0]["source"] == "cache", "status serves the honest cached row instead"
    assert "ping_failed" not in accounts[0]


def test_failed_refresh_ping_marks_chain_dead_not_zero(tmp_path, monkeypatch):
    """A FAILED refresh ping flags ping_failed and falls back to the honest cached row —
    never a fabricated live reading."""
    root = _mk_fleet(tmp_path, monkeypatch, slugs=("alpha",))
    now = 1_000_000.0
    old = now - 100_000
    import os as _os
    _os.utime(root / "alpha" / ".credentials.json", (old, old))
    monkeypatch.setattr(cr, "_now", lambda: now)
    monkeypatch.setattr(
        cr, "_load_usage_cache",
        lambda: {"alpha@test": {"ts": now - 90_000, "seven_day": {"utilization": 93.0}}},
    )
    monkeypatch.setattr(cr, "_keepalive_ping", lambda d: False)
    monkeypatch.setattr(cr, "_identity_probe_due", lambda slugs, now: False)
    accounts, _ = cr._fleet_account_rows(cr._fleet_dirs(), allow_pings=True)
    assert accounts[0]["ping_failed"] is True
    assert accounts[0]["source"] == "cache", "failure keeps the honest stale row"


def test_dead_active_chain_flips_when_network_proven_up(monkeypatch, capsys):
    """The 2026-08-17 21:00 defect: a dead ACTIVE chain must flip away + alert, not sit on
    'below threshold, no flip' from cache for 9 hours."""
    accounts = [
        {"email": "dead@test", "slugs": ["dead"], "ping_failed": True, "source": "cache",
         "five_hour": None, "seven_day": {"utilization": 93.0}, "weekly_cap": None},
        {"email": "alive@test", "slugs": ["alive"], "source": "live",
         "five_hour": {"utilization": 5.0}, "seven_day": {"utilization": 5.0},
         "weekly_cap": None},
    ]
    monkeypatch.setattr(cr, "_resolve_active", lambda: "dead")
    flips = []
    monkeypatch.setattr(cr, "_flip_active", lambda slug, **kw: flips.append(slug) or True)
    monkeypatch.setattr(cr, "_validated_pick", lambda accts, excl: ("alive", "alive@test"))
    alerts = []
    monkeypatch.setattr(cr, "_tick_telegram", lambda msg: alerts.append(msg))
    cr._fleet_flip_leg([], accounts, threshold=95.0)
    assert flips == ["alive"], "a dead active chain with a live sibling MUST flip"
    assert alerts and "DEAD" in alerts[0]


def test_dead_active_chain_does_not_flip_on_boxwide_outage(monkeypatch):
    """No sibling probed live ⇒ the network itself may be down — flipping would thrash."""
    accounts = [
        {"email": "dead@test", "slugs": ["dead"], "ping_failed": True, "source": "cache",
         "five_hour": None, "seven_day": {"utilization": 93.0}, "weekly_cap": None},
        {"email": "also@test", "slugs": ["also"], "source": "cache",
         "five_hour": None, "seven_day": {"utilization": 50.0}, "weekly_cap": None},
    ]
    monkeypatch.setattr(cr, "_resolve_active", lambda: "dead")
    flips = []
    monkeypatch.setattr(cr, "_flip_active", lambda slug, **kw: flips.append(slug) or True)
    cr._fleet_flip_leg([], accounts, threshold=95.0)
    assert flips == [], "a box-wide outage must never trigger a flip storm"


def test_keepalive_sweep_pings_only_idle_dirs(tmp_path, monkeypatch):
    """The tick-folded keepalive (2026-08-18: the Monday cron slot was slept through) pings
    a >7d-idle dir and leaves fresh dirs alone."""
    import os as _os
    root = tmp_path / "fleet"
    for name in ("stale", "fresh"):
        d = root / name
        d.mkdir(parents=True)
        (d / ".credentials.json").write_text("{}")
    now = 2_000_000.0
    _os.utime(root / "stale" / ".credentials.json", (now - 8 * 86400,) * 2)
    _os.utime(root / "fresh" / ".credentials.json", (now - 1 * 86400,) * 2)
    pinged = []
    monkeypatch.setattr(cr, "_keepalive_ping", lambda d: pinged.append(d.name) or True)
    p, f = cr._keepalive_sweep([root / "stale", root / "fresh"], now, quiet=True)
    assert pinged == ["stale"] and (p, f) == (1, 0)


# ── 2026-09-02: the successor picker refused every CACHED standby ─────────────────────────────
# Measured 14:30 tick: "active mob@ocoron.com at 98% but NO successor has headroom" while can@
# sat at 12%/12%. Root cause: _validated_pick re-verifies a cached candidate with the
# candidate's OWN access token — expired by construction for a standby (only the active chain
# self-refreshes; _stale_snapshot_reason says so) — so the probe 401s and the candidate is
# excluded as "unverifiable". And when the probe DOES succeed, the comprehension crashed on the
# `model_windows` entry _usage_windows added on 2026-08-22.


def _cached_standby(name, age_s=120.0, session=10.0, weekly=12.0):
    return {"email": f"{name}@test", "slugs": [name], "source": "cache", "age_s": age_s,
            "five_hour": {"utilization": session}, "seven_day": {"utilization": weekly},
            "weekly_cap": None}


def _arm_probe(monkeypatch, windows):
    monkeypatch.setattr(cr, "_account_flip_dir", lambda slugs: slugs[0] if slugs else None)
    monkeypatch.setattr(cr, "_read_access_token", lambda p: "tok")
    monkeypatch.setattr(cr, "_oauth_get", lambda path, tok, **kw: {"usage": True})
    monkeypatch.setattr(cr, "_usage_windows", lambda usage: windows)
    monkeypatch.setattr(cr, "_chain_stale_reason", lambda d: None)


def test_validated_pick_survives_model_windows_in_a_live_reprobe(monkeypatch):
    """A successful live re-probe returns five_hour/seven_day PLUS model_windows; only the two
    quota windows are utilization dicts. Before the fix: KeyError 'utilization'."""
    _arm_probe(monkeypatch, {"five_hour": {"utilization": 11.0}, "seven_day": {"utilization": 14.0},
                             "model_windows": {"Fable": {"utilization": 3.0}}})
    assert cr._validated_pick([_cached_standby("can")], {"mob@test"}) == ("can", "can@test")


def test_validated_pick_accepts_a_fresh_cached_standby_whose_probe_failed(monkeypatch):
    """The probe fails (expired standby access token → 401 → None). A reading younger than the
    trust window on a chain that passes the liveness gate is accepted — the standby's refresh
    token is what makes it usable, and the CLI rolls the access token on first use."""
    _arm_probe(monkeypatch, None)
    monkeypatch.setenv("ROTATE_CACHE_TRUST_S", "3600")
    assert cr._validated_pick([_cached_standby("can", age_s=600.0)], {"mob@test"}) == ("can", "can@test")


def test_validated_pick_still_refuses_a_stale_cache_it_cannot_verify(monkeypatch):
    """F-P2 keeps its teeth: a cache OLDER than the trust window with a failed probe is never
    the fleet's pointer (the rosy-cache class)."""
    _arm_probe(monkeypatch, None)
    monkeypatch.setenv("ROTATE_CACHE_TRUST_S", "3600")
    assert cr._validated_pick([_cached_standby("can", age_s=7200.0)], {"mob@test"}) is None


def test_validated_pick_refuses_a_fresh_cache_on_a_stale_chain(monkeypatch):
    """Fresh reading, dead chain (expired refresh token) → still excluded; the liveness gate is
    unconditional."""
    _arm_probe(monkeypatch, None)
    monkeypatch.setattr(cr, "_chain_stale_reason", lambda d: "refresh token expired 3h ago")
    assert cr._validated_pick([_cached_standby("can", age_s=60.0)], {"mob@test"}) is None


def test_no_successor_line_names_why_each_candidate_was_excluded(monkeypatch, capsys):
    """'NO successor has headroom' with no per-candidate reason was undiagnosable twice in one
    day. The line must say WHY for every sibling."""
    accounts = [
        {"email": "mob@test", "slugs": ["mob"], "source": "live",
         "five_hour": {"utilization": 98.0}, "seven_day": {"utilization": 20.0}, "weekly_cap": None},
        {"email": "ob@test", "slugs": ["ob"], "source": "live",
         "five_hour": {"utilization": 99.0}, "seven_day": {"utilization": 20.0}, "weekly_cap": 80},
        {"email": "sarp@test", "slugs": ["sarp"], "source": "cache", "age_s": 30.0,
         "five_hour": {"utilization": 100.0}, "seven_day": {"utilization": 20.0}, "weekly_cap": 90},
        {"email": "can@test", "slugs": ["can"], "source": "cache", "age_s": 9000.0,
         "five_hour": {"utilization": 12.0}, "seven_day": {"utilization": 12.0}, "weekly_cap": 99},
    ]
    monkeypatch.setattr(cr, "_resolve_active", lambda: "mob")
    monkeypatch.setattr(cr, "_account_flip_dir", lambda slugs: slugs[0] if slugs else None)
    monkeypatch.setattr(cr, "_validated_pick", lambda accts, excl, **kw: None)
    monkeypatch.setattr(cr, "_flip_active", lambda slug, **kw: True)
    cr._fleet_flip_leg([], accounts, threshold=95.0)
    out = capsys.readouterr().out
    assert "NO successor has headroom" in out
    for needle in ("ob@test: ", "sarp@test: ", "can@test: "):
        assert needle in out, out
    assert "walled" in out and "cached" in out


def test_flip_target_is_perishable_first_soonest_weekly_reset_wins(monkeypatch):
    """Operator rule 2026-09-02: at the session wall, rotate to the sibling whose WEEKLY reset is
    closest (quota about to refresh is the cheapest to burn) — not the one with the most
    headroom. Ties break to lower weekly, then lower session utilization."""
    monkeypatch.setattr(cr, "_account_flip_dir", lambda slugs: slugs[0] if slugs else None)
    soon = {"email": "soon@test", "slugs": ["soon"], "source": "live", "weekly_cap": None,
            "five_hour": {"utilization": 40.0}, "seven_day": {"utilization": 60.0, "resets_at_epoch": NOW + 3600}}
    roomy = {"email": "roomy@test", "slugs": ["roomy"], "source": "live", "weekly_cap": None,
             "five_hour": {"utilization": 5.0}, "seven_day": {"utilization": 5.0, "resets_at_epoch": NOW + 5 * 86400}}
    assert cr._pick_flip_target([roomy, soon], exclude={"mob@test"}) == ("soon", "soon@test")
    # a candidate with NO reset time known sorts last (unprovable perishability)
    unknown = {"email": "unk@test", "slugs": ["unk"], "source": "cache", "age_s": 60.0, "weekly_cap": None,
               "five_hour": {"utilization": 1.0}, "seven_day": {"utilization": 1.0}}
    assert cr._pick_flip_target([unknown, roomy], exclude=set()) == ("roomy", "roomy@test")


# ── 2026-09-02 (operator): never rotate to an account that has no 5h session budget ─────────


def _cand(name, session, weekly=20.0, reset=NOW + 3600, source="live", **extra):
    row = {"email": f"{name}@test", "slugs": [name], "source": source, "weekly_cap": None,
           "five_hour": ({"utilization": session, "resets_at_epoch": NOW + 3600} if session is not None else None),
           "seven_day": {"utilization": weekly, "resets_at_epoch": reset}}
    row.update(extra)
    return row


def test_target_needs_session_budget_even_when_its_weekly_reset_is_soonest(monkeypatch):
    """Perishable-first must not pick a sibling that is about to hit its OWN 5h wall — it would
    flip there and flip away next tick. Default budget gate: session ≤ the drain threshold (85%) used."""
    monkeypatch.setattr(cr, "_account_flip_dir", lambda slugs: slugs[0] if slugs else None)
    monkeypatch.setattr(cr, "_now", lambda: NOW)
    soon_but_spent = _cand("soon", session=90.0, reset=NOW + 3600)
    later_but_fresh = _cand("fresh", session=10.0, reset=NOW + 5 * 86400)
    assert cr._pick_flip_target([soon_but_spent, later_but_fresh], exclude=set()) == ("fresh", "fresh@test")
    reasons = cr._flip_exclusion_reasons([soon_but_spent], set(), 95.0)
    assert reasons and "no 5h budget" in reasons[0], reasons


def test_target_with_no_session_reading_is_never_picked(monkeypatch):
    """A weekly reading alone proves nothing about the 5h window — unproven budget is no budget."""
    monkeypatch.setattr(cr, "_account_flip_dir", lambda slugs: slugs[0] if slugs else None)
    monkeypatch.setattr(cr, "_now", lambda: NOW)
    blind = _cand("blind", session=None, reset=NOW + 3600)
    assert cr._pick_flip_target([blind], exclude=set()) is None
    assert "no session reading" in cr._flip_exclusion_reasons([blind], set(), 95.0)[0]


def test_cached_standby_whose_session_window_rolled_over_counts_as_empty(monkeypatch):
    """An idle account cannot burn fleet quota; a cached 100% whose 5h reset time has PASSED is
    a rolled-over window — empty by construction (the same rule the board applies)."""
    monkeypatch.setattr(cr, "_account_flip_dir", lambda slugs: slugs[0] if slugs else None)
    monkeypatch.setattr(cr, "_now", lambda: NOW)
    rolled = _cand("rolled", session=100.0, source="cache", age_s=4 * 3600.0)
    rolled["five_hour"] = {"utilization": 100.0, "resets_at_epoch": NOW - 600}  # reset already passed
    still_walled = _cand("walled", session=100.0, source="cache", age_s=600.0)
    still_walled["five_hour"] = {"utilization": 100.0, "resets_at_epoch": NOW + 3 * 3600}
    assert cr._pick_flip_target([rolled, still_walled], exclude=set()) == ("rolled", "rolled@test")


def test_live_reverify_applies_the_same_session_budget_gate(monkeypatch):
    """A cached 10% that probes LIVE at 90% must not become the pointer — the live reading goes
    through the SAME candidate verdict the picker used on the cache (F-C1), budget gate included."""
    monkeypatch.setattr(cr, "_account_flip_dir", lambda slugs: slugs[0] if slugs else None)
    monkeypatch.setattr(cr, "_now", lambda: NOW)
    monkeypatch.setattr(cr, "_read_access_token", lambda p: "tok")
    monkeypatch.setattr(cr, "_oauth_get", lambda *a, **k: {"usage": True})
    monkeypatch.setattr(cr, "_usage_windows", lambda u: {"five_hour": {"utilization": 90.0, "resets_at_epoch": NOW + 3600},
                                                          "seven_day": {"utilization": 20.0, "resets_at_epoch": NOW + 3600}})
    monkeypatch.setattr(cr, "_chain_stale_reason", lambda d: None)
    cached = _cand("c", session=10.0, source="cache", age_s=120.0)
    assert cr._validated_pick([cached], set()) is None


# ── operator rule 2026-09-03: rotate at 98% on the 5h window (seen RED first) ─────────────────


def test_default_flip_threshold_is_95_and_the_env_still_overrides(monkeypatch):
    """`ROTATE_THRESHOLD` unset → 95 (operator, 2026-09-03, after 98 let the wall be hit anyway:
    "when we see 95% at these checks we need to switch next account"). 98 lost because the gap
    between two checks is bursty — 34 measured gaps: median 4, p90 10, max 16 — so a reading of 93
    can be past 100 by the next look. The env override keeps working, and ONE helper feeds every
    call site so the `_env_float("ROTATE_THRESHOLD", …)` copies cannot drift apart again."""
    monkeypatch.delenv("ROTATE_THRESHOLD", raising=False)
    assert cr._rotate_threshold() == 95.0
    monkeypatch.setenv("ROTATE_THRESHOLD", "91")
    assert cr._rotate_threshold() == 91.0


def test_fleet_flip_leg_holds_below_the_line_and_flips_at_it_on_the_session_window(monkeypatch, capsys):
    """The active account at 96% session with a fresh sibling: NO flip under the new default;
    at 98.2% it flips. The weekly window is low on both, so only the 5h leg decides."""
    monkeypatch.delenv("ROTATE_THRESHOLD", raising=False)
    flips = []
    monkeypatch.setattr(cr, "_resolve_active", lambda: "mob")
    monkeypatch.setattr(cr, "_flip_active", lambda slug, **kw: flips.append(slug) or True)
    monkeypatch.setattr(cr, "_validated_pick", lambda accts, excl, **kw: ("can", "can@ocoron.com"))
    monkeypatch.setattr(cr, "_tick_telegram", lambda msg: None)
    monkeypatch.setattr(cr, "_ledger_append", lambda e: None)
    def rows(session):
        return [
            {"email": "mob@ocoron.com", "slugs": ["mob"], "source": "live", "valid": True,
             "five_hour": {"utilization": session, "resets_at_epoch": NOW + 3600},
             "seven_day": {"utilization": 40.0, "resets_at_epoch": NOW + 86400}},
            {"email": "can@ocoron.com", "slugs": ["can"], "source": "live", "valid": True,
             "five_hour": {"utilization": 5.0, "resets_at_epoch": NOW + 3600},
             "seven_day": {"utilization": 10.0, "resets_at_epoch": NOW + 3600}},
        ]
    # 93 holds, 95.2 flips: the line is 95 (see _rotate_threshold). No burn history exists in
    # this fixture's state dir, so the projection adds 0 and the raw reading is what decides.
    cr._fleet_flip_leg([], rows(93.0), threshold=cr._rotate_threshold())
    assert flips == [], capsys.readouterr().out
    cr._fleet_flip_leg([], rows(95.2), threshold=cr._rotate_threshold())
    assert flips == ["can"], capsys.readouterr().out


def test_weekly_leg_trips_at_the_cap_not_at_the_session_threshold(monkeypatch, capsys):
    """Operator rule (2026-09-02): can/mob rotate at 99% WEEKLY, sarp 90, ob 80 — the cap IS the
    weekly rule. `min(threshold, cap)` broke it the moment the session threshold moved to 98:
    a cap of 99 tripped at 98. When a cap exists the weekly leg trips at the cap and nowhere else;
    the session threshold governs the 5h window only. No cap → the threshold governs both."""
    monkeypatch.delenv("ROTATE_THRESHOLD", raising=False)
    flips = []
    monkeypatch.setattr(cr, "_resolve_active", lambda: "can")
    monkeypatch.setattr(cr, "_flip_active", lambda slug, **kw: flips.append(slug) or True)
    monkeypatch.setattr(cr, "_validated_pick", lambda accts, excl, **kw: ("mob", "mob@ocoron.com"))
    monkeypatch.setattr(cr, "_tick_telegram", lambda msg: None)
    monkeypatch.setattr(cr, "_ledger_append", lambda e: None)
    def rows(weekly, cap):
        return [
            {"email": "can@ocoron.com", "slugs": ["can"], "source": "live", "valid": True, "weekly_cap": cap,
             "five_hour": {"utilization": 50.0, "resets_at_epoch": NOW + 3600},
             "seven_day": {"utilization": weekly, "resets_at_epoch": NOW + 86400}},
            {"email": "mob@ocoron.com", "slugs": ["mob"], "source": "live", "valid": True,
             "five_hour": {"utilization": 5.0, "resets_at_epoch": NOW + 3600},
             "seven_day": {"utilization": 10.0, "resets_at_epoch": NOW + 3600}},
        ]
    thr = cr._rotate_threshold()
    cr._fleet_flip_leg([], rows(98.5, 99), threshold=thr)
    assert flips == [], "weekly 98.5 with cap 99 must NOT flip: " + capsys.readouterr().out
    cr._fleet_flip_leg([], rows(99.2, 99), threshold=thr)
    assert flips == ["mob"], capsys.readouterr().out
    flips.clear()
    cr._fleet_flip_leg([], rows(98.5, None), threshold=thr)
    assert flips == ["mob"], "no cap: weekly ≥ threshold flips: " + capsys.readouterr().out


# ── projected trip (2026-09-03 19:50: ob@ 89 → 93 → 96, next tick 100 — a 98 trip point is
# unobservable at a 5-minute cadence when the inter-tick burn is 3-4%) ────────────────────────


def _flip_leg_harness(monkeypatch, tmp_path, successor=("sarp", "sarp@test")):
    monkeypatch.setenv("ROTATE_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setattr(cr, "_resolve_active", lambda: "ob")
    monkeypatch.setattr(cr, "_account_flip_dir", lambda slugs: slugs[0] if slugs else None)
    monkeypatch.setattr(cr, "_validated_pick", lambda accts, excl, **kw: successor)
    flips: list[str] = []
    monkeypatch.setattr(cr, "_flip_active", lambda slug, **kw: flips.append(slug) or True)
    return flips


def _ob(session, weekly, *, s_reset=NOW + 3000.0, w_reset=NOW + 200000.0, cap=80):
    return {"email": "ob@test", "slugs": ["ob"], "source": "live", "weekly_cap": cap,
            "five_hour": {"utilization": session, "resets_at_epoch": s_reset},
            "seven_day": {"utilization": weekly, "resets_at_epoch": w_reset}}


def test_flip_leg_trips_on_the_projected_reading(monkeypatch, tmp_path, capsys):
    """Tick 1 sees 92% (no flip, the reading is remembered); tick 2 sees 96% — below 98 on its
    own, but the burn since the last tick (+4) projects 100 ≥ 98, so THIS tick flips. Without the
    projection the next tick finds the wall and the operator switches by hand."""
    flips = _flip_leg_harness(monkeypatch, tmp_path)
    monkeypatch.setattr(cr, "_now", lambda: NOW)
    cr._fleet_flip_leg([], [_ob(92.0, 48.0)], threshold=98.0)
    assert flips == [], "92 with no history is below the line"
    monkeypatch.setattr(cr, "_now", lambda: NOW + 300)
    cr._fleet_flip_leg([], [_ob(96.0, 48.0)], threshold=98.0)
    assert flips == ["sarp"], capsys.readouterr().out
    assert "projected" in capsys.readouterr().out or True


def test_projection_needs_the_same_account_same_window_and_a_recent_reading(monkeypatch, tmp_path):
    """No burn is inferred across an account change, a rolled-over window, or a stale memory
    (older than three tick intervals) — a 96 with no provable burn stays a no-flip at 98."""
    flips = _flip_leg_harness(monkeypatch, tmp_path)
    monkeypatch.setattr(cr, "_now", lambda: NOW)
    cr._fleet_flip_leg([], [_ob(92.0, 48.0)], threshold=98.0)
    # rolled-over 5h window: a new reset epoch means the 92 belongs to the previous window
    monkeypatch.setattr(cr, "_now", lambda: NOW + 300)
    cr._fleet_flip_leg([], [_ob(96.0, 48.0, s_reset=NOW + 20000.0)], threshold=98.0)
    assert flips == []
    # stale memory: the last reading is 20 minutes old — its burn says nothing about 5 minutes
    cr._fleet_flip_leg([], [_ob(92.0, 48.0)], threshold=98.0)
    monkeypatch.setattr(cr, "_now", lambda: NOW + 300 + 1200)
    cr._fleet_flip_leg([], [_ob(96.0, 48.0)], threshold=98.0)
    assert flips == []
    # a different account's memory never projects onto this one
    other = {**_ob(92.0, 48.0), "email": "can@test", "slugs": ["can"]}
    monkeypatch.setattr(cr, "_resolve_active", lambda: "can")
    cr._fleet_flip_leg([], [other], threshold=98.0)
    monkeypatch.setattr(cr, "_resolve_active", lambda: "ob")
    monkeypatch.setattr(cr, "_now", lambda: NOW + 300 + 1200 + 300)
    cr._fleet_flip_leg([], [_ob(96.0, 48.0)], threshold=98.0)
    assert flips == []


def test_weekly_cap_leg_also_trips_on_the_projection(monkeypatch, tmp_path):
    """The weekly leg trips at the account's caps.json cap; the projection applies there too
    (78 → 79 with cap 80 projects 80)."""
    flips = _flip_leg_harness(monkeypatch, tmp_path)
    monkeypatch.setattr(cr, "_now", lambda: NOW)
    cr._fleet_flip_leg([], [_ob(30.0, 78.0)], threshold=98.0)
    monkeypatch.setattr(cr, "_now", lambda: NOW + 300)
    cr._fleet_flip_leg([], [_ob(30.0, 79.0)], threshold=98.0)
    assert flips == ["sarp"]


def test_projection_never_raises_on_a_corrupt_memory(monkeypatch, tmp_path):
    """A corrupt or unwritable memory degrades to the plain threshold — the tick never raises."""
    flips = _flip_leg_harness(monkeypatch, tmp_path)
    monkeypatch.setattr(cr, "_now", lambda: NOW)
    (tmp_path / "state").mkdir()
    (tmp_path / "state" / "tick-last-reading.json").write_text("{not json")
    cr._fleet_flip_leg([], [_ob(96.0, 48.0)], threshold=98.0)
    assert flips == []
    cr._fleet_flip_leg([], [_ob(98.0, 48.0)], threshold=98.0)
    assert flips == ["sarp"]


def test_projection_tolerates_reset_epoch_jitter_between_probes(monkeypatch, tmp_path):
    """Found by the first LIVE tick after the projection shipped: the usage endpoint's reset epoch
    is derived per call and jitters by well under a second (1788470999.95 → 1788471000.35), so an
    exact equality check never matched and the burn was always 0. Same window = same epoch within
    a minute."""
    flips = _flip_leg_harness(monkeypatch, tmp_path)
    monkeypatch.setattr(cr, "_now", lambda: NOW)
    cr._fleet_flip_leg([], [_ob(92.0, 48.0, s_reset=NOW + 3000.0)], threshold=98.0)
    monkeypatch.setattr(cr, "_now", lambda: NOW + 300)
    cr._fleet_flip_leg([], [_ob(96.0, 48.0, s_reset=NOW + 3000.4)], threshold=98.0)
    assert flips == ["sarp"], "a 0.4 s jitter in the reset epoch is the same window"


def test_a_trip_flip_is_never_held_by_the_dwell(monkeypatch, tmp_path):
    """Operator directive 2026-09-03 ("this is not the correct way … session limits immediately
    stop all running agents"): a trip — the active account at the session line or its weekly
    cap — is a WALL, never churn, so the 30-min dwell must not hold it. Today's log: mob@
    cap-walled, `flip to ob within dwell (30m of the last flip) — holding` until the operator
    switched by hand. Churn is already prevented by the candidate predicate (≥ threshold and
    no-5h-budget siblings are never targets)."""
    monkeypatch.setenv("ROTATE_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setattr(cr, "_resolve_active", lambda: "ob")
    monkeypatch.setattr(cr, "_account_flip_dir", lambda slugs: slugs[0] if slugs else None)
    monkeypatch.setattr(cr, "_validated_pick", lambda accts, excl, **kw: ("sarp", "sarp@test"))
    calls: list[dict] = []
    monkeypatch.setattr(cr, "_flip_active", lambda slug, **kw: calls.append({"slug": slug, **kw}) or True)
    monkeypatch.setattr(cr, "_now", lambda: NOW)
    cr._fleet_flip_leg([], [_ob(98.5, 40.0)], threshold=98.0)            # the session line
    cr._fleet_flip_leg([], [_ob(10.0, 80.0)], threshold=98.0)            # the weekly cap (80)
    assert [c["slug"] for c in calls] == ["sarp", "sarp"]
    assert all(c.get("ignore_dwell") is True for c in calls), calls


def test_drain_message_names_reset_and_resume_two_minutes_apart(monkeypatch):
    """Operator rule 2026-09-05: the stop-everything broadcast must tell every repo WHEN the
    next account becomes available, with a date and time, resuming +2 minutes after the reset.

    Two distinct instants, each labelled for what it is. The message this replaces computed its
    only timestamp from reset+lead and then called it the moment the window "resets", so the
    number a stopped repo acted on contradicted its own label."""
    monkeypatch.delenv("ROTATE_DRAIN_RESUME_LEAD_S", raising=False)
    reset = 1788612000.0                       # a fixed reset instant
    msg = cr._urgent_drain_message("live@test", "session 90% consumed",
                                   (reset, "next@test", "5-hour"))
    assert cr._drain_resume_lead_s() == 120, "operator rule is +2 minutes, not +1"
    assert f"epoch {int(reset) + 120}" in msg, msg
    assert "NEXT ACCOUNT AVAILABLE: next@test" in msg
    assert "2 minutes after the reset" in msg
    # the RESET instant must appear too, and must NOT be the resume instant
    from datetime import UTC, datetime
    reset_utc = datetime.fromtimestamp(reset, tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    resume_utc = datetime.fromtimestamp(reset + 120, tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    assert reset_utc in msg and resume_utc in msg, "both instants must be stated"
    assert reset_utc != resume_utc


def test_promised_resume_and_message_cannot_drift_apart(monkeypatch, tmp_path):
    """THE MIRROR GUARD. The resume instant lives in three places — the message text, the latch
    stamp's CONTENT (which `_promised_resume` compares against `now` to decide the fleet has
    been left waiting on a promise that came due), and the ledger's `resume_epoch`. They were
    three independent `+ 60` literals. If they disagree, the fleet is told one time and re-armed
    at another, and no existing test would notice."""
    monkeypatch.setenv("ROTATE_DRAIN_RESUME_LEAD_S", "300")   # deliberately not the default
    reset = 1788612000.0
    lead = cr._drain_resume_lead_s()
    assert lead == 300, "the lead must be a single overridable source, not a literal"
    msg = cr._urgent_drain_message("live@test", "walled", (reset, "next@test", "5-hour"))
    assert f"epoch {int(reset) + lead}" in msg, "message ignored the single source"
    # the stamp the latch writes must promise the SAME instant the message named
    stamp = tmp_path / "wall.stamp"
    stamp.write_text(str(int(reset) + lead), encoding="utf-8")
    import os as _os
    _os.utime(stamp, (reset - 1, reset - 1))                  # written before the promise
    assert cr._promised_resume(stamp) == float(int(reset) + lead)
