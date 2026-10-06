"""Behavior-Contract tests — the rotation capability probe (plan 2026-10-06-plan-2, spec D1-D7, D-614/D-616).

An account whose organisation refuses Claude Code (`oauth_org_not_allowed`, the 2026-09-29/30 billing
lapse) passes a usage reading and a refresh-chain check, so the picker promoted it and no tick flipped
away. These tests pin the classifier, the confirmed auto-park, the parked-list lock, and the wiring
that runs the probe before a promotion, on the active account, from a session's refusal marker and in
the CLI wrapper.

Everything is tmp_path-isolated through the fleet suite's harness; the `claude` binary is a
monkeypatched `subprocess.run`, never the real CLI.
"""

from __future__ import annotations

import json
import subprocess
import threading
import time

from tests.test_claude_fleet import FLEET_NOW, _canonical, _fleet_creds, _pin, cr

# The shapes `claude -p --output-format json` prints (G1, G3). NOT_LOGGED_IN is the verbatim failure
# captured in the plan's Evidence (an empty config dir); HEALTHY carries the keys of the one real call.
NOT_LOGGED_IN = json.dumps(
    {
        "type": "result",
        "subtype": "success",
        "is_error": True,
        "api_error_status": None,
        "terminal_reason": "api_error",
        "result": "Not logged in · Please run /login",
    }
)
HEALTHY = json.dumps(
    {
        "type": "result",
        "subtype": "success",
        "is_error": False,
        "api_error_status": None,
        "terminal_reason": "completed",
        "num_turns": 1,
        "result": "Hi.",
    }
)


def _refusal(**over) -> dict:
    obj = {
        "type": "result",
        "subtype": "success",
        "is_error": True,
        "api_error_status": 403,
        "result": "API Error: 403 oauth_org_not_allowed",
    }
    obj.update(over)
    return obj


REFUSAL = json.dumps(_refusal())


# ── A1-A4: the classifier ─────────────────────────────────────────────────────────────────────


def test_a1_five_legitimate_spellings_of_the_refusal_are_all_refused():
    """D1: `refused` only with `is_error` true AND the code or the incident's text anywhere in the
    result object. Five spellings a different author would plausibly meet — 5/5 or it is a finding."""
    spellings = {
        "code in result": REFUSAL,
        "incident text, no code": json.dumps(
            _refusal(
                result="Your organization has disabled Claude subscription access for Claude Code",
                api_error_status=None,
            )
        ),
        "code in an error field": json.dumps(
            _refusal(result="API Error", error={"type": "oauth_org_not_allowed"})
        ),
        "pretty-printed": json.dumps(_refusal(), indent=2),
        "mixed case": json.dumps(_refusal(result="API Error: 403 OAuth_Org_Not_Allowed")),
    }
    got = {name: cr._capability_verdict(1, out) for name, out in spellings.items()}
    assert got == dict.fromkeys(spellings, "refused"), got


def test_a1b_the_two_framings_are_refused_too():
    """A warning line before the result, and an `api_error_status` of null (spec U2)."""
    assert cr._capability_verdict(1, "Ignoring 3 entries: not trusted\n" + REFUSAL) == "refused"
    assert cr._capability_verdict(1, json.dumps(_refusal(api_error_status=None))) == "refused"


def test_a2_a_healthy_result_and_a_non_json_success_are_ok():
    """D1: exit 0 with no `is_error` result is `ok` — including a non-JSON stdout, which keeps the
    old ping's exit-0-is-success semantics."""
    assert cr._capability_verdict(0, HEALTHY) == "ok"
    assert cr._capability_verdict(0, "�� bad\n") == "ok"


def test_a3_every_other_failure_is_inconclusive():
    """Lifecycle: a timeout, an error for another cause, a non-zero exit with no result, and a
    refusal printed only on stderr (empty stdout) all fail open."""
    assert cr._capability_verdict(None, "") == "inconclusive"
    assert cr._capability_verdict(1, NOT_LOGGED_IN) == "inconclusive"
    assert cr._capability_verdict(1, "") == "inconclusive"
    assert cr._capability_verdict(1, "boom") == "inconclusive"
    assert cr._capability_verdict(0, NOT_LOGGED_IN) == "inconclusive"


def test_a4_a_quoted_code_in_a_successful_result_never_refuses():
    """The class `run_claude` admits at :796-798: a conversation that merely mentions the code."""
    quoted = json.dumps(
        {
            "type": "result",
            "is_error": False,
            "result": "the docs say oauth_org_not_allowed means a server-side setting",
        }
    )
    assert cr._capability_verdict(0, quoted) == "ok"


def test_a1c_the_probe_runs_the_documented_argv_and_honours_its_timeout(tmp_path, monkeypatch):
    """D1: the probe argv, the dir-bound env, and an explicit timeout overriding KEEPALIVE_TIMEOUT."""
    seen = {}

    def fake_run(argv, **kw):
        seen["argv"], seen["env"], seen["timeout"] = list(argv), dict(kw["env"]), kw["timeout"]
        return subprocess.CompletedProcess(argv, 1, REFUSAL, "")

    monkeypatch.setattr(cr.subprocess, "run", fake_run)
    assert cr._capability_probe(tmp_path, timeout=45) == "refused"
    assert seen["argv"] == [
        "claude",
        "-p",
        "ok",
        "--output-format",
        "json",
        "--max-turns",
        "1",
        "--tools",
        "",
    ]
    assert seen["env"]["CLAUDE_CONFIG_DIR"] == seen["env"]["CLAUDE_QUOTA_HOME"] == str(tmp_path)
    assert seen["timeout"] == 45

    def timeout_run(argv, **kw):
        raise subprocess.TimeoutExpired(argv, kw["timeout"])

    monkeypatch.setattr(cr.subprocess, "run", timeout_run)
    assert cr._capability_probe(tmp_path) == "inconclusive"


# ── A5-A9: the confirmed auto-park, the lock, the ping path ─────────────────────────────────


def _fleet_one(tmp_path, monkeypatch, slug="d0", email="a@ocoron.com"):
    fleet, *_ = _canonical(tmp_path, monkeypatch)
    assert cr.main(["--new-dir", slug, email]) == 0
    _pin(fleet, slug, email)
    _fleet_creds(fleet, slug, f"tok-{slug}", age_s=600.0)
    monkeypatch.setattr(cr, "_now", lambda: FLEET_NOW)
    return fleet


def _probe_script(monkeypatch, outs):
    """Each `claude` call answers the next (rc, stdout) in `outs`; returns the call list."""
    calls = []

    def fake_run(argv, **kw):
        calls.append({"dir": kw["env"]["CLAUDE_CONFIG_DIR"], "timeout": kw.get("timeout")})
        rc, out = outs[min(len(calls) - 1, len(outs) - 1)]
        return subprocess.CompletedProcess(argv, rc, out, "")

    monkeypatch.setattr(cr.subprocess, "run", fake_run)
    return calls


def _alerts(monkeypatch):
    sent = []
    monkeypatch.setattr(
        cr, "_tick_telegram", lambda msg, key="quota-rotation": sent.append((msg, key)) or True
    )
    return sent


def _ledger_rows(tmp_path):
    path = tmp_path / "state" / "rotate-ledger.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def test_a5_a_confirmed_refusal_parks_logs_and_alerts_billing_first(tmp_path, monkeypatch, capsys):
    """D3: two refusals in a row park the account, write one `auto-park` ledger row, send one alert
    that leads with the billing check — and print nothing on stdout."""
    fleet = _fleet_one(tmp_path, monkeypatch)
    calls = _probe_script(monkeypatch, [(1, REFUSAL)])
    sent = _alerts(monkeypatch)
    row = {"email": "a@ocoron.com", "weekly_cap": None}
    capsys.readouterr()  # drop the fixture's --new-dir output

    assert cr._auto_park("a@ocoron.com", source="promote", cfg_dir=fleet / "d0", row=row) is True

    assert json.loads((fleet / "parked.json").read_text()) == ["a@ocoron.com"]
    events = [r for r in _ledger_rows(tmp_path) if r.get("event") == "auto-park"]
    assert len(events) == 1 and events[0]["email"] == "a@ocoron.com"
    assert events[0]["source"] == "promote" and events[0]["cause"] == "oauth_org_not_allowed"
    assert "result" not in events[0], "the probe's result text is never logged"
    assert len(sent) == 1 and sent[0][1] == "capability-a@ocoron.com"
    assert sent[0][0].lower().startswith("check this account's billing")
    assert "--unpark a@ocoron.com" in sent[0][0]
    assert row["weekly_cap"] == 0 and row["capability_refused"] is True
    assert len(calls) == 1, "the confirmation is the one probe _auto_park itself runs"
    assert capsys.readouterr().out == ""


def test_a9_an_unconfirmed_refusal_parks_nothing_and_caches_its_verdict(tmp_path, monkeypatch):
    """D3: a refusal whose confirmation is `ok` or `inconclusive` parks, walls, logs and alerts
    nothing; the confirmation verdict is cached so the next probe is held off by its window."""
    fleet = _fleet_one(tmp_path, monkeypatch)
    sent = _alerts(monkeypatch)
    row = {"email": "a@ocoron.com", "weekly_cap": None}

    _probe_script(monkeypatch, [(0, HEALTHY)])
    assert cr._auto_park("a@ocoron.com", source="promote", cfg_dir=fleet / "d0", row=row) is False
    assert not (fleet / "parked.json").exists()
    assert row["weekly_cap"] is None and "capability_refused" not in row
    assert sent == [] and not [r for r in _ledger_rows(tmp_path) if r.get("event") == "auto-park"]

    calls = _probe_script(monkeypatch, [(1, "boom")])
    assert cr._auto_park("a@ocoron.com", source="promote", cfg_dir=fleet / "d0") is False
    assert len(calls) == 1
    assert cr._probe_account("a@ocoron.com", "d0") == "inconclusive"
    assert len(calls) == 1, "the cached inconclusive confirmation holds the next probe off"


def test_a6_two_racing_park_writers_both_land(tmp_path, monkeypatch):
    """D5: the read-modify-write of parked.json is locked — without the lock the slower writer's
    stale read drops the faster one's email."""
    fleet, *_ = _canonical(tmp_path, monkeypatch)
    for slug, email in (("d0", "a@ocoron.com"), ("d1", "b@ocoron.com")):
        assert cr.main(["--new-dir", slug, email]) == 0
        _pin(fleet, slug, email)
    real_write = cr._write_json_atomic

    def slow_write(dst, data, mode=0o600):
        time.sleep(0.2)  # widen the read→write window
        real_write(dst, data, mode=mode)

    monkeypatch.setattr(cr, "_write_json_atomic", slow_write)
    threads = [
        threading.Thread(target=cr._parked_update, args=(email, True), kwargs={"repair": False})
        for email in ("a@ocoron.com", "b@ocoron.com")
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(json.loads((fleet / "parked.json").read_text())) == [
        "a@ocoron.com",
        "b@ocoron.com",
    ]


def test_a7_the_stale_reading_ping_parks_a_refusal_and_keeps_ping_failed_for_the_rest(
    tmp_path, monkeypatch
):
    """D4: a refusal from the stale-reading ping parks the account and does NOT mark the chain dead;
    a ping that fails any other way still sets `ping_failed`, as today."""
    fleet = _fleet_one(tmp_path, monkeypatch)
    state = tmp_path / "state"
    state.mkdir(exist_ok=True)
    stale = {
        "a@ocoron.com": {
            "ts": FLEET_NOW - 5 * 3600.0,
            "five_hour": {"utilization": 10.0, "resets_at_epoch": FLEET_NOW + 3600},
            "seven_day": {"utilization": 10.0, "resets_at_epoch": FLEET_NOW + 86400},
        }
    }
    (state / "fleet-usage-cache.json").write_text(json.dumps(stale))
    from tests.test_claude_fleet import _fake_oauth

    _fake_oauth(monkeypatch)
    _alerts(monkeypatch)
    _probe_script(monkeypatch, [(1, REFUSAL)])

    accounts, _ = cr._fleet_account_rows(cr._fleet_dirs(), allow_pings=True)
    assert accounts[0].get("capability_refused") is True
    assert not accounts[0].get("ping_failed")
    assert json.loads((fleet / "parked.json").read_text()) == ["a@ocoron.com"]


def test_a7b_a_ping_that_fails_another_way_still_marks_the_chain_dead(tmp_path, monkeypatch):
    fleet = _fleet_one(tmp_path, monkeypatch)
    state = tmp_path / "state"
    state.mkdir(exist_ok=True)
    (state / "fleet-usage-cache.json").write_text(
        json.dumps(
            {"a@ocoron.com": {"ts": FLEET_NOW - 5 * 3600.0, "five_hour": {}, "seven_day": {}}}
        )
    )
    from tests.test_claude_fleet import _fake_oauth

    _fake_oauth(monkeypatch)
    _probe_script(monkeypatch, [(1, "boom")])
    accounts, _ = cr._fleet_account_rows(cr._fleet_dirs(), allow_pings=True)
    assert accounts[0]["ping_failed"] is True
    assert not (fleet / "parked.json").exists()


def test_a8_a_broken_parked_list_is_never_overwritten_by_an_automated_park(tmp_path, monkeypatch):
    """Constraints digest: a broken parked.json parks NOTHING — the automated park leaves its bytes
    alone and walls only the in-tick row, while the operator's --park still repairs it."""
    fleet = _fleet_one(tmp_path, monkeypatch)
    _probe_script(monkeypatch, [(1, REFUSAL)])
    _alerts(monkeypatch)
    broken = b"{not json"
    (fleet / "parked.json").write_bytes(broken)
    row = {"email": "a@ocoron.com", "weekly_cap": None}

    assert cr._auto_park("a@ocoron.com", source="active", cfg_dir=fleet / "d0", row=row) is False
    assert (fleet / "parked.json").read_bytes() == broken
    assert row["weekly_cap"] == 0, "the row is walled for this tick even when the write is refused"

    assert cr.main(["--park", "a@ocoron.com"]) == 0
    assert json.loads((fleet / "parked.json").read_text()) == ["a@ocoron.com"]


def test_a8b_an_unknown_or_pending_identity_is_never_written(tmp_path, monkeypatch):
    fleet = _fleet_one(tmp_path, monkeypatch)
    calls = _probe_script(monkeypatch, [(1, REFUSAL)])
    for email in ("stranger@x.com", "pending-login"):
        assert cr._auto_park(email, source="wrapper", cfg_dir=fleet / "d0") is False
    assert not (fleet / "parked.json").exists()
    assert calls == [], "an unknown identity is refused before any probe is spent"
    assert cr._auto_park("A@Ocoron.COM ", source="wrapper", cfg_dir=fleet / "d0") is True
    assert json.loads((fleet / "parked.json").read_text()) == ["a@ocoron.com"]


# ── Phase A scoped review, round 1: one regression guard per confirmed defect ──────────────────


def test_r1_a_non_result_object_never_refuses_and_a_timeout_decides_nothing():
    """Only a `type: result` object is read, on every path; a timeout (`rc is None`) is
    inconclusive whatever was printed."""
    other = json.dumps({"type": "system", "is_error": True, "message": "oauth_org_not_allowed"})
    assert cr._capability_verdict(1, other) == "inconclusive"
    assert cr._capability_verdict(None, REFUSAL) == "inconclusive"


def test_r2_deeply_nested_stdout_is_inconclusive_not_a_crash():
    deep = "[" * 100_000 + "]" * 100_000
    assert cr._capability_verdict(1, deep) == "inconclusive"


def test_r3_a_pretty_printed_refusal_with_a_trailer_line_is_still_refused():
    out = json.dumps(_refusal(), indent=2) + "\nwarn: telemetry disabled\n"
    assert cr._capability_verdict(1, out) == "refused"


def test_r4_a_lock_that_cannot_be_taken_writes_nothing_and_never_raises(
    tmp_path, monkeypatch, capsys
):
    fleet = _fleet_one(tmp_path, monkeypatch)

    def no_lock(fd, op):
        if op == cr.fcntl.LOCK_EX:
            raise BlockingIOError(11, "Resource temporarily unavailable")

    monkeypatch.setattr(cr.fcntl, "flock", no_lock)
    assert cr._parked_update("a@ocoron.com", True, repair=False) is None
    assert not (fleet / "parked.json").exists()
    capsys.readouterr()
    assert cr.main(["--park", "a@ocoron.com"]) == 1
    err = capsys.readouterr().err
    assert err.count("\n") == 1 and "cannot lock" in err, err


def test_r5_the_parked_lock_never_creates_a_missing_fleet_root(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_FLEET_ROOT", str(tmp_path / "no-fleet"))
    assert cr._parked_update("a@ocoron.com", True, repair=True) is None
    assert not (tmp_path / "no-fleet").exists()


def test_r6_a_bool_infinite_or_future_cache_ts_is_re_probed(tmp_path, monkeypatch):
    _fleet_one(tmp_path, monkeypatch)
    calls = _probe_script(monkeypatch, [(0, HEALTHY)])
    for ts in (True, "Infinity", FLEET_NOW + 3600.0):
        raw = json.dumps({"a@ocoron.com": {"verdict": "ok", "ts": ts}})
        if ts == "Infinity":
            raw = raw.replace(
                '"Infinity"', "Infinity"
            )  # the bare JSON token json.loads reads as inf
        cr._probe_cache_path().write_text(raw)
        before = len(calls)
        assert cr._probe_account("a@ocoron.com", "d0") == "ok"
        assert len(calls) == before + 1, f"ts={ts!r} was trusted"


def test_r7_the_confirmation_is_bounded_at_45_seconds_and_the_board_flag_is_set(
    tmp_path, monkeypatch
):
    fleet = _fleet_one(tmp_path, monkeypatch)
    calls = _probe_script(monkeypatch, [(1, REFUSAL)])
    _alerts(monkeypatch)
    row = {"email": "a@ocoron.com", "weekly_cap": None, "parked": False}
    assert cr._auto_park("a@ocoron.com", source="ping", cfg_dir=fleet / "d0", row=row) is True
    assert calls[0]["timeout"] == 45
    assert row["parked"] is True


# ── Phase A scoped review, round 2 ──────────────────────────────────────────────────────────────


def test_r8_the_last_top_level_result_wins_and_a_nested_dict_is_never_read_alone():
    """The result is the LAST top-level `type: result` object, one-line or pretty-printed."""
    early_healthy = json.dumps({"type": "result", "is_error": False, "result": "x"})
    late_refusal = json.dumps(_refusal(), indent=2)
    assert cr._capability_verdict(1, early_healthy + "\n" + late_refusal) == "refused"
    early_refusal = REFUSAL
    late_healthy = json.dumps(json.loads(HEALTHY), indent=2)
    assert cr._capability_verdict(0, early_refusal + "\n" + late_healthy) == "ok"
    nested = json.dumps(
        {
            "type": "result",
            "is_error": False,
            "result": "Hi.",
            "echo": {"type": "result", "is_error": True, "result": "oauth_org_not_allowed"},
        },
        indent=2,
    )
    assert cr._capability_verdict(0, nested + "\nwarn: trailer\n") == "ok"


def test_r9_a_park_that_could_not_be_written_never_shows_as_parked(tmp_path, monkeypatch):
    """The row is walled for this tick either way, but the board's `parked` flag waits for the write."""
    fleet = _fleet_one(tmp_path, monkeypatch)
    _probe_script(monkeypatch, [(1, REFUSAL)])
    _alerts(monkeypatch)
    (fleet / "parked.json").write_bytes(b"{broken")
    row = {"email": "a@ocoron.com", "weekly_cap": None, "parked": False}
    assert cr._auto_park("a@ocoron.com", source="active", cfg_dir=fleet / "d0", row=row) is False
    assert row["weekly_cap"] == 0 and row["parked"] is False
