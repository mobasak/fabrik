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
    live = _acct("live", session_pct=97.0)
    sib = _acct("sib", weekly_reset=NOW + 86400)
    state = tmp_path / "state"
    state.mkdir()
    actions = {"mails": [], "telegrams": []}
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
    monkeypatch.setattr(cr, "_collect_statuses", lambda: (_ for _ in ()).throw(RuntimeError("boom")))
    assert cr._cmd_tick() == 0


def test_t11_keepwarm_runs_on_degraded_ticks(tmp_path, monkeypatch):
    """Closer #12: no-live is exactly when parked snapshots must not age out."""
    called = []
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
