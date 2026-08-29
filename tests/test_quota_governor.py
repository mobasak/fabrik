"""Behavior-Contract tests for scripts/sysadmin/quota_governor.py (TDD — written FIRST).

The governor is a READER of `claude_rotate.py --status --json` output (fleet shape): it decides,
per call, whether the active ob@ account or the OpenRouter pool runs the work, and never blocks an
incident. These tests inject a `status_fn` (the parsed `--status --json` dict) + a temp cap-state
file + a temp single-flight lock, so nothing touches live rotation state.

Fixtures use the REAL fleet payload shape: {"active": <slug>, "accounts": [{"email","slugs",
"five_hour":{"utilization","resets_at_epoch"}, "seven_day":{…}, "model_windows":{<model>:{…}},
"cap_walled": bool, "weekly_cap": int|None}, …]}.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "quota_governor",
    Path(__file__).resolve().parents[1] / "scripts" / "sysadmin" / "quota_governor.py",
)
quota_governor = importlib.util.module_from_spec(_SPEC)
sys.modules["quota_governor"] = quota_governor  # so string-target monkeypatch resolves in isolation
_SPEC.loader.exec_module(quota_governor)  # type: ignore[union-attr]
QuotaGovernor = quota_governor.QuotaGovernor


def _payload(*, active="ob", five_hour=0.0, seven_day=0.0, model_windows=None, cap_walled=False,
             weekly_cap=None, five_hour_epoch=1.0, seven_day_epoch=1.0):
    """A fleet-shape --status --json dict with a single active ob@ account row."""
    row = {
        "email": "ob@ocoron.com",
        "slugs": [active],
        "five_hour": {"utilization": five_hour, "resets_at_epoch": five_hour_epoch},
        "seven_day": {"utilization": seven_day, "resets_at_epoch": seven_day_epoch},
        "cap_walled": cap_walled,
        "weekly_cap": weekly_cap,
    }
    if model_windows is not None:
        row["model_windows"] = model_windows
    return {"active": active, "accounts": [row]}


def _gov(tmp_path, payload_or_fn, *, now=1000.0, reserve_pct=80.0, cap_ttl_s=21600.0):
    status_fn = payload_or_fn if callable(payload_or_fn) else (lambda: payload_or_fn)
    return QuotaGovernor(
        reserve_pct=reserve_pct,
        cap_ttl_s=cap_ttl_s,
        status_fn=status_fn,
        now_fn=lambda: now,
        cap_state_path=tmp_path / "cap.json",
        lock_path=tmp_path / "incident.lock",
        alert_fn=lambda *a, **k: None,
    )


# (a) routine sheds to pool when 5h util >= reserve even though weekly is low — multi-window
def test_routine_sheds_on_five_hour_wall(tmp_path):
    gov = _gov(tmp_path, _payload(five_hour=85.0, seven_day=10.0))
    assert gov.route("routine") == "pool"


# (a2) routine sheds when ONLY a model_windows entry (Opus/model-weekly) >= reserve
def test_routine_sheds_on_model_window_wall(tmp_path):
    gov = _gov(tmp_path, _payload(five_hour=0.0, seven_day=10.0,
                                  model_windows={"Opus": {"utilization": 85.0, "resets_at_epoch": 1.0}}))
    assert gov.route("routine") == "pool"


# (b) routine runs on ob@ below the reserve
def test_routine_runs_on_obat_below_reserve(tmp_path):
    gov = _gov(tmp_path, _payload(five_hour=10.0, seven_day=20.0,
                                  model_windows={"Fable": {"utilization": 40.0, "resets_at_epoch": 1.0}}))
    assert gov.route("routine") == "ob@"


# (c) incident returns ob@ when not capped
def test_incident_runs_on_obat_when_not_capped(tmp_path):
    gov = _gov(tmp_path, _payload(five_hour=50.0, seven_day=50.0))
    assert gov.route("incident") == "ob@"


# (d) incident returns pool-diagnose when ob@ is capped (cap_walled)
def test_incident_pool_diagnose_when_capped(tmp_path):
    gov = _gov(tmp_path, _payload(seven_day=95.0, weekly_cap=90, cap_walled=True))
    assert gov.route("incident") == "pool-diagnose"


# (e) --status failure / unparseable row → routine=pool, incident=ob@ (fail-SAFE)
def test_fail_safe_on_status_failure(tmp_path):
    def boom():
        raise RuntimeError("claude_rotate --status failed")
    gov = _gov(tmp_path, boom)
    assert gov.route("routine") == "pool"
    assert gov.route("incident") == "ob@"


def test_fail_safe_on_unparseable_row(tmp_path):
    # active slug names no account → no row → fail-safe
    gov = _gov(tmp_path, {"active": "nope", "accounts": [_payload()["accounts"][0]]})
    assert gov.route("routine") == "pool"
    assert gov.route("incident") == "ob@"


# (f) a reactive is_usage_limit marks ob@ capped until the window reset
def test_reactive_cap_from_usage_limit(tmp_path):
    payload = _payload(five_hour=10.0, seven_day=10.0, seven_day_epoch=2000.0)
    gov = _gov(tmp_path, payload, now=1000.0)
    assert gov.route("incident") == "ob@"  # not capped yet
    gov.mark_capped("Claude usage limit reached. Your limit will reset at ...")
    # now capped until seven_day reset (2000 > now 1000)
    assert gov.route("incident") == "pool-diagnose"
    assert gov.route("routine") == "pool"


def test_reactive_cap_expires_after_reset(tmp_path):
    payload = _payload(five_hour=10.0, seven_day=10.0, seven_day_epoch=1500.0)
    gov = _gov(tmp_path, payload, now=1000.0)
    gov.mark_capped("usage limit reached")
    assert gov.route("incident") == "pool-diagnose"  # now 1000 < reset 1500
    # a fresh governor at now=1600 (past the reset) sees the cap expired
    gov2 = _gov(tmp_path, payload, now=1600.0)
    assert gov2.route("incident") == "ob@"


# (f2) a window with resets_at_epoch = None never raises and un-caps after CAP_TTL_S
def test_none_epoch_never_raises_and_uncaps_after_ttl(tmp_path):
    payload = _payload(five_hour=10.0, seven_day=10.0, seven_day_epoch=None)
    gov = _gov(tmp_path, payload, now=1000.0, cap_ttl_s=600.0)
    gov.mark_capped("usage limit reached")  # None epoch → capped_until = now + CAP_TTL_S = 1600
    assert gov.route("incident") == "pool-diagnose"  # 1000 < 1600, no now>=None comparison
    gov2 = _gov(tmp_path, payload, now=1700.0, cap_ttl_s=600.0)  # past the TTL
    assert gov2.route("incident") == "ob@"


def test_none_epoch_in_window_does_not_crash_routing(tmp_path):
    # a live-shaped payload where five_hour.resets_at_epoch is None (as ob@ shows live)
    payload = _payload(five_hour=0.0, five_hour_epoch=None, seven_day=50.0)
    gov = _gov(tmp_path, payload)
    assert gov.route("routine") == "ob@"  # utilization drives shedding; None epoch never compared
    assert gov.route("incident") == "ob@"


# fail-OPEN guard: a row PRESENT but with NO parseable utilization window (schema drift) must NOT
# be read as 0% headroom — routine sheds to pool; an incident still runs on ob@ (never dropped).
def test_routine_sheds_when_utilization_unparseable(tmp_path):
    drifted = {
        "active": "ob",
        "accounts": [{
            "email": "ob@ocoron.com", "slugs": ["ob"],
            "five_hour": {"utilization": "N/A"},   # string, not numeric
            "seven_day": {"pct": 90},              # renamed key → no 'utilization'
            "cap_walled": False, "weekly_cap": None,
        }],
    }
    gov = _gov(tmp_path, drifted)
    assert gov.route("routine") == "pool"      # headroom unknown → shed, never assume 0%
    assert gov.route("incident") == "ob@"      # the fix still runs on ob@ (fail-safe, never dropped)


# reactive cap with a PAST/zero seven_day epoch must fall back to a bounded now+CAP_TTL_S, not write
# an already-expired (no-op) cap.
def test_mark_capped_past_epoch_falls_back_to_ttl(tmp_path):
    payload = _payload(five_hour=10.0, seven_day=10.0, seven_day_epoch=500.0)  # 500 < now 1000
    gov = _gov(tmp_path, payload, now=1000.0, cap_ttl_s=600.0)
    gov.mark_capped("usage limit reached")
    # would be a no-op if it used the past epoch 500; the fallback caps until 1000+600=1600
    assert gov.route("incident") == "pool-diagnose"
    gov2 = _gov(tmp_path, payload, now=1700.0, cap_ttl_s=600.0)  # past the bounded TTL
    assert gov2.route("incident") == "ob@"


# a malformed env var must fall back to the default, never crash construction (fail-safety).
def test_malformed_env_falls_back_to_default(tmp_path, monkeypatch):
    monkeypatch.setenv("QUOTA_RESERVE_PCT", "80%")   # garbage
    monkeypatch.setenv("QUOTA_CAP_TTL_S", "six-hours")
    payload = _payload(five_hour=85.0, seven_day=10.0)
    # built with reserve_pct=None so it reads the (garbage) env → must default, not crash
    gov = QuotaGovernor(
        status_fn=lambda: payload, now_fn=lambda: 1000.0,
        cap_state_path=tmp_path / "cap.json", lock_path=tmp_path / "incident.lock",
        alert_fn=lambda *a, **k: None,
    )
    assert gov.reserve_pct == 80.0
    assert gov.cap_ttl_s == 21600.0
    assert gov.route("routine") == "pool"  # 85 >= default 80


# a NON-FINITE env value (inf/nan) parses without ValueError but would silently disable shedding /
# wedge the cap — it must fall back to the default like any garbage.
def test_nonfinite_env_falls_back_to_default(tmp_path, monkeypatch):
    monkeypatch.setenv("QUOTA_RESERVE_PCT", "inf")   # would make max>=inf always False → no shed
    monkeypatch.setenv("QUOTA_CAP_TTL_S", "nan")     # would make now<nan always False → no cap
    payload = _payload(five_hour=85.0, seven_day=10.0)
    gov = QuotaGovernor(
        status_fn=lambda: payload, now_fn=lambda: 1000.0,
        cap_state_path=tmp_path / "cap.json", lock_path=tmp_path / "incident.lock",
        alert_fn=lambda *a, **k: None,
    )
    assert gov.reserve_pct == 80.0
    assert gov.cap_ttl_s == 21600.0
    assert gov.route("routine") == "pool"  # shedding still works (85 >= 80)
    gov.mark_capped("usage limit reached")
    assert gov.route("incident") == "pool-diagnose"  # cap holds (now+21600), not a nan no-op


# a lock-infra OSError (unmakeable state dir) must DEGRADE, never raise — the incident is not blocked.
def test_incident_lock_oserror_degrades_to_pool_diagnose(tmp_path):
    (tmp_path / "blocker").write_text("i am a file, not a dir")
    payload = _payload(five_hour=10.0, seven_day=10.0)
    gov = _gov(tmp_path, payload)
    # lock_path parent is under a FILE → mkdir(parents=True) raises NotADirectoryError (OSError)
    gov._lock_path = tmp_path / "blocker" / "sub" / "incident.lock"
    assert gov.route("incident") == "pool-diagnose"  # degraded, not raised


# two concurrent mark_capped() (distinct pids) must write DISTINCT, pid-bearing tmp paths so the
# rename never races (red-on-revert: a shared tmp path makes both writes use the same name).
def test_mark_capped_pid_unique_tmp_no_race(tmp_path, monkeypatch):
    payload = _payload(five_hour=10.0, seven_day=10.0, seven_day_epoch=9999.0)
    cap = tmp_path / "cap.json"
    seen_tmps: list[str] = []
    real_replace = quota_governor.os.replace

    def spy_replace(src, dst):
        seen_tmps.append(str(src))
        return real_replace(src, dst)

    monkeypatch.setattr(quota_governor.os, "replace", spy_replace)
    for pid in (111, 222):
        monkeypatch.setattr(quota_governor.os, "getpid", lambda pid=pid: pid)
        gov = QuotaGovernor(
            status_fn=lambda: payload, now_fn=lambda: 1000.0,
            cap_state_path=cap, lock_path=tmp_path / "incident.lock",
            alert_fn=lambda *a, **k: None,
        )
        gov.mark_capped("usage limit reached")
    # the two writes used DISTINCT, pid-bearing tmp names — the whole point of the fix
    assert len(seen_tmps) == 2
    assert seen_tmps[0] != seen_tmps[1]
    assert "111" in seen_tmps[0] and "222" in seen_tmps[1]
    # and the final state is valid + the cap holds
    gov_read = _gov(tmp_path, payload, now=1000.0)
    assert gov_read.route("incident") == "pool-diagnose"


# (f3) cap_walled True but max(windows) < RESERVE_PCT → routine=pool AND incident=pool-diagnose
def test_cap_walled_honored_below_reserve(tmp_path):
    # weekly_cap 40 (operator-set below RESERVE_PCT 80); seven_day 45 >= 40 → cap_walled True
    payload = _payload(five_hour=10.0, seven_day=45.0, weekly_cap=40, cap_walled=True)
    gov = _gov(tmp_path, payload, reserve_pct=80.0)
    # max utilization (45) is below RESERVE_PCT (80), so ONLY cap_walled can shed it
    assert gov.route("routine") == "pool"
    assert gov.route("incident") == "pool-diagnose"


# (g) single-flight: lock held → a second incident returns pool-diagnose; the first keeps ob@
def test_single_flight_second_incident_pool_diagnose(tmp_path):
    payload = _payload(five_hour=10.0, seven_day=10.0)
    gov1 = _gov(tmp_path, payload)
    gov2 = _gov(tmp_path, payload)
    assert gov1.route("incident") == "ob@"          # acquires + holds the incident lock
    assert gov2.route("incident") == "pool-diagnose"  # lock held → non-blocking shed
    gov1.release_incident()
    assert gov2.route("incident") == "ob@"          # lock freed → the next incident gets ob@


def test_single_flight_routine_never_takes_the_lock(tmp_path):
    payload = _payload(five_hour=10.0, seven_day=10.0)
    gov1 = _gov(tmp_path, payload)
    gov1.route("incident")  # holds the lock
    # a routine call must NOT be blocked by the incident lock — it routes on headroom alone
    gov2 = _gov(tmp_path, payload)
    assert gov2.route("routine") == "ob@"


# the CLI (used by claude-run.sh + shell consumers) prints the routing destination on stdout
def test_cli_route_prints_shed_destination(tmp_path, capsys):
    gov = _gov(tmp_path, _payload(five_hour=85.0, seven_day=10.0))  # over reserve → shed
    rc = quota_governor._main(["route", "--kind", "routine", "--caller", "morning-report"], governor=gov)
    assert rc == 0
    assert capsys.readouterr().out.strip() == "pool"


def test_cli_route_incident_runs_on_obat(tmp_path, capsys):
    gov = _gov(tmp_path, _payload(five_hour=10.0, seven_day=10.0))
    rc = quota_governor._main(["route", "--kind", "incident"], governor=gov)
    assert rc == 0
    assert capsys.readouterr().out.strip() == "ob@"


# capped() is the LOCK-FREE check for the interactive bot — no single-flight side effect.
def test_capped_true_when_cap_walled(tmp_path):
    gov = _gov(tmp_path, _payload(seven_day=95.0, weekly_cap=90, cap_walled=True))
    assert gov.capped() is True
    # and it did NOT take the incident lock — a real incident can still get ob@
    other = _gov(tmp_path, _payload(five_hour=10.0, seven_day=10.0))
    assert other.route("incident") == "ob@"


def test_capped_false_below_wall_and_on_status_failure(tmp_path):
    assert _gov(tmp_path, _payload(five_hour=50.0, seven_day=50.0)).capped() is False

    def boom():
        raise RuntimeError("status down")
    assert _gov(tmp_path, boom).capped() is False  # fail-safe: no row → not capped (bot runs)
