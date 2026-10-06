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
import os
import subprocess
import threading
import time

from tests.test_claude_fleet import (
    FLEET_NOW,
    _canonical,
    _caps,
    _fake_oauth,
    _fleet_creds,
    _fleet_tick_spies,
    _fleet_two_accounts,
    _pin,
    _point,
    _usage_blob,
    cr,
)

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


def test_r3_a_pretty_printed_result_followed_by_a_trailer_fails_open():
    """Not a shape `--output-format json` prints (it writes one single-line result). The classifier
    keeps no heuristic for it — round 3 measured the span and scan heuristics as the defects — so it
    finds no result and fails open: never `refused`, never a crash."""
    out = json.dumps(_refusal(), indent=2) + "\nwarn: telemetry disabled\n"
    assert cr._capability_verdict(1, out) == "inconclusive"


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


def test_r8_the_last_result_line_wins_and_neither_a_nested_nor_an_embedded_object_counts():
    """The result is the LAST line that begins with `{` and parses as `type: result`; a dict nested
    inside it, or a JSON object embedded mid-way in a log line, is never read on its own."""
    early_healthy = json.dumps({"type": "result", "is_error": False, "result": "x"})
    assert cr._capability_verdict(1, early_healthy + "\n" + REFUSAL) == "refused"
    assert cr._capability_verdict(0, REFUSAL + "\n" + HEALTHY) == "ok"
    nested = json.dumps(
        {
            "type": "result",
            "is_error": False,
            "result": "Hi.",
            "echo": {"type": "result", "is_error": True, "result": "oauth_org_not_allowed"},
        }
    )
    assert cr._capability_verdict(0, "warn: x\n" + nested) == "ok"
    assert cr._capability_verdict(0, HEALTHY + "\nlog: " + REFUSAL) == "ok"


def test_r10_the_classifier_is_linear_on_a_long_stdout_full_of_unmatched_braces():
    """Round 3 measured the raw_decode scan as quadratic (≈30 s at 400 kB); the line reader is not."""
    started = time.monotonic()
    assert cr._capability_verdict(1, "{" * 400_000) == "inconclusive"
    assert cr._capability_verdict(1, "{x\n" * 100_000) == "inconclusive"
    assert time.monotonic() - started < 5.0


def test_r9_a_park_that_could_not_be_written_never_shows_as_parked(tmp_path, monkeypatch):
    """The row is walled for this tick either way, but the board's `parked` flag waits for the write."""
    fleet = _fleet_one(tmp_path, monkeypatch)
    _probe_script(monkeypatch, [(1, REFUSAL)])
    _alerts(monkeypatch)
    (fleet / "parked.json").write_bytes(b"{broken")
    row = {"email": "a@ocoron.com", "weekly_cap": None, "parked": False}
    assert cr._auto_park("a@ocoron.com", source="active", cfg_dir=fleet / "d0", row=row) is False
    assert row["weekly_cap"] == 0 and row["parked"] is False


# ── Phase B: the wiring — probe on promote (D2), active re-check (D6), session marker (D7),
#    the wrapper (D4b) ───────────────────────────────────────────────────────────────────────────


def _fleet_b(tmp_path, monkeypatch, *, active="seo"):
    """Two accounts — seo/youtube are sarp@, intel is ob@ — both with live, cool readings."""
    fleet = _fleet_two_accounts(tmp_path, monkeypatch)
    _fleet_creds(fleet, "seo", "tok-seo", age_s=60.0)
    _fleet_creds(fleet, "intel", "tok-intel", age_s=60.0)
    _fake_oauth(
        monkeypatch,
        usages={"tok-seo": _usage_blob(10.0, 10.0), "tok-intel": _usage_blob(10.0, 10.0)},
    )
    _fleet_tick_spies(monkeypatch)
    monkeypatch.setattr(cr, "_mailbox_repos", lambda: [])
    monkeypatch.setattr(cr, "OPT_DIR", tmp_path / "opt")
    monkeypatch.setattr(cr, "_selfwatch_lock_dir", lambda: tmp_path / "locks")
    _point(fleet, active)
    return fleet


def _probe_by_dir(monkeypatch, refused=()):
    """`claude` answers the refusal for any dir named in *refused*, healthy otherwise."""
    calls = []

    def fake_run(argv, **kw):
        name = os.path.basename(kw["env"]["CLAUDE_CONFIG_DIR"])
        calls.append({"dir": name, "timeout": kw.get("timeout")})
        return (
            subprocess.CompletedProcess(argv, 1, REFUSAL, "")
            if name in refused
            else (subprocess.CompletedProcess(argv, 0, HEALTHY, ""))
        )

    monkeypatch.setattr(cr.subprocess, "run", fake_run)
    return calls


def _flips(tmp_path):
    return [r for r in _ledger_rows(tmp_path) if r.get("event") == "flip"]


def _cache_ok(email, age_s):
    cr._probe_cache_path().write_text(
        json.dumps({email: {"verdict": "ok", "ts": FLEET_NOW - age_s}})
    )


def test_b5_a_refused_active_account_is_parked_and_flipped_away_on_the_same_tick(
    tmp_path, monkeypatch
):
    """D6: the active account, holding no fresh verdict, refuses — it is parked and the pointer
    leaves it on THIS tick, flip kind `refused`."""
    fleet = _fleet_b(tmp_path, monkeypatch)
    _probe_by_dir(monkeypatch, refused={"seo"})
    assert cr._cmd_tick() == 0
    assert os.readlink(fleet / "active") == "intel"
    assert json.loads((fleet / "parked.json").read_text()) == ["sarp@ocoron.com"]
    parks = [r for r in _ledger_rows(tmp_path) if r.get("event") == "auto-park"]
    assert [p["source"] for p in parks] == ["active"]
    assert [f.get("kind") for f in _flips(tmp_path)] == ["refused"]


def test_b5b_a_fresh_active_verdict_spends_no_probe(tmp_path, monkeypatch):
    """Cost: an `ok` younger than the active window means no probe on this tick."""
    fleet = _fleet_b(tmp_path, monkeypatch)
    calls = _probe_by_dir(monkeypatch)
    _cache_ok("sarp@ocoron.com", 5 * 60.0)
    assert cr._cmd_tick() == 0
    assert calls == []
    assert os.readlink(fleet / "active") == "seo"


def test_b5c_an_operator_parked_active_account_with_no_reading_is_flipped_and_not_probed(
    tmp_path, monkeypatch
):
    """D6 + D-443: any parked active account is flipped away, even with no quota reading, and is
    never re-probed (its weekly_cap reads 0)."""
    fleet = _fleet_b(tmp_path, monkeypatch)
    _fake_oauth(
        monkeypatch,
        usages={"tok-seo": _usage_blob(None, None), "tok-intel": _usage_blob(10.0, 10.0)},
    )
    _caps(fleet, {"sarp@ocoron.com": 0})
    calls = _probe_by_dir(monkeypatch)
    assert cr._cmd_tick() == 0
    assert os.readlink(fleet / "active") == "intel"
    assert [f.get("kind") for f in _flips(tmp_path)] == ["parked"]
    # D6's own probe is the 45 s one; a 150 s call on seo is today's stale-reading refresh ping (D4)
    assert not [c for c in calls if c["dir"] == "seo" and c["timeout"] == 45], calls


def test_b5d_a_withheld_flip_away_alerts_nothing_and_says_withheld(tmp_path, monkeypatch, capsys):
    fleet = _fleet_b(tmp_path, monkeypatch)
    _probe_by_dir(monkeypatch, refused={"seo"})
    sent = _alerts(monkeypatch)
    monkeypatch.setattr(cr, "_flip_active", lambda *a, **k: False)
    capsys.readouterr()
    assert cr._cmd_tick() == 0
    assert os.readlink(fleet / "active") == "seo"
    assert "withheld" in capsys.readouterr().out
    assert not [m for m, _k in sent if "flipped" in m.lower()]


def test_b1_a_refused_top_candidate_is_parked_and_the_next_is_picked(tmp_path, monkeypatch):
    """D2: the picker's top candidate refuses — it is parked, walled for this tick, and the next
    healthy candidate is returned."""
    _fleet_b(tmp_path, monkeypatch)
    _probe_by_dir(monkeypatch, refused={"intel"})
    accounts = [
        {"email": "ob@ocoron.com", "slugs": ["intel"], "weekly_cap": None, "parked": False},
        {"email": "sarp@ocoron.com", "slugs": ["seo"], "weekly_cap": None, "parked": False},
    ]
    picks = iter([("intel", "ob@ocoron.com"), ("seo", "sarp@ocoron.com")])
    monkeypatch.setattr(cr, "_validated_pick_reading", lambda acc, ex, verbose=False: next(picks))
    assert cr._validated_pick(accounts, set(), probe=True) == ("seo", "sarp@ocoron.com")
    assert accounts[0]["weekly_cap"] == 0
    parks = [r for r in _ledger_rows(tmp_path) if r.get("event") == "auto-park"]
    assert [(p["email"], p["source"]) for p in parks] == [("ob@ocoron.com", "promote")]


def test_b2_a_fresh_candidate_verdict_spends_no_probe_and_a_stale_one_spends_one(
    tmp_path, monkeypatch
):
    _fleet_b(tmp_path, monkeypatch)
    calls = _probe_by_dir(monkeypatch)
    _cache_ok("ob@ocoron.com", 3600.0)
    assert cr._probe_account("ob@ocoron.com", "intel") == "ok"
    assert calls == []
    _cache_ok("ob@ocoron.com", cr._probe_trust_s() + 60.0)
    assert cr._probe_account("ob@ocoron.com", "intel") == "ok"
    assert len(calls) == 1


def test_b3_an_inconclusive_candidate_is_picked_as_today(tmp_path, monkeypatch, capsys):
    _fleet_b(tmp_path, monkeypatch)

    def timeout_run(argv, **kw):
        raise subprocess.TimeoutExpired(argv, kw["timeout"])

    monkeypatch.setattr(cr.subprocess, "run", timeout_run)
    accounts = [{"email": "ob@ocoron.com", "slugs": ["intel"], "weekly_cap": None}]
    monkeypatch.setattr(
        cr, "_validated_pick_reading", lambda acc, ex, verbose=False: ("intel", "ob@ocoron.com")
    )
    capsys.readouterr()
    assert cr._validated_pick(accounts, set(), probe=True) == ("intel", "ob@ocoron.com")
    assert "capability probe inconclusive" in capsys.readouterr().out
    assert not (tmp_path / "fleet" / "parked.json").exists()


def test_b4_the_advisory_and_a_manual_switch_never_probe(tmp_path, monkeypatch):
    """D2: only the flip leg probes; the relief advisory and the operator's --switch never do, and
    the switch still lands on a refusing account (D-443's escape hatch)."""
    fleet = _fleet_b(tmp_path, monkeypatch)
    calls = _probe_by_dir(monkeypatch, refused={"intel"})
    monkeypatch.setattr(
        cr, "_validated_pick_reading", lambda acc, ex, verbose=False: ("intel", "ob@ocoron.com")
    )
    assert cr._validated_pick([], set()) == ("intel", "ob@ocoron.com")
    assert calls == []
    assert cr.main(["--switch", "intel"]) == 0
    assert calls == []
    assert os.readlink(fleet / "active") == "intel"


def test_b7_inconclusive_is_held_off_and_a_d4_ok_seeds_the_cache(tmp_path, monkeypatch):
    _fleet_b(tmp_path, monkeypatch)
    calls = _probe_script(monkeypatch, [(1, "boom")])
    assert cr._probe_account("ob@ocoron.com", "intel") == "inconclusive"
    assert cr._probe_account("ob@ocoron.com", "intel") == "inconclusive"
    assert len(calls) == 1, "an inconclusive verdict is not re-probed within _PROBE_RETRY_S"
    cr._record_probe("ob@ocoron.com", "ok")  # what the D4 ping writes after an `ok`
    calls.clear()
    assert cr._probe_account("ob@ocoron.com", "intel", window=cr._active_probe_s()) == "ok"
    assert calls == []


def test_b7b_an_unwritable_state_dir_never_stops_the_tick(tmp_path, monkeypatch):
    fleet = _fleet_b(tmp_path, monkeypatch)
    _probe_by_dir(monkeypatch, refused={"seo"})
    monkeypatch.setattr(cr, "_record_probe", lambda e, v: None)  # nothing can be cached
    ro = tmp_path / "ro-state"
    ro.mkdir()
    monkeypatch.setenv("ROTATE_STATE_DIR", str(ro))
    ro.chmod(0o500)
    try:
        assert cr._cmd_tick() == 0
    finally:
        ro.chmod(0o700)
    assert os.readlink(fleet / "active") == "intel"


def test_b8_a_sessions_refusal_marker_expires_the_active_verdict(tmp_path, monkeypatch):
    """D7: an `.errparked` record of class oauth_org_not_allowed newer than the active `ok` makes
    this tick probe the active account; another class, an older record or a malformed one do not;
    a record more than 60 s in the future is skipped."""
    _fleet_b(tmp_path, monkeypatch)
    locks = tmp_path / "locks"
    locks.mkdir()
    cases = [
        ("oauth_org_not_allowed", FLEET_NOW - 60, 1),
        ("rate_limit", FLEET_NOW - 60, 0),
        ("oauth_org_not_allowed", FLEET_NOW - 3600, 0),
        ("garbage!!", FLEET_NOW - 60, 0),
        ("oauth_org_not_allowed", FLEET_NOW + 3600, 0),
    ]
    for cls, epoch, want in cases:
        for f in locks.glob("*.errparked"):
            f.unlink()
        (locks / "sess1.errparked").write_text(f"{cls} {int(epoch)}\n")
        _cache_ok("sarp@ocoron.com", 5 * 60.0)  # fresh: only a marker can expire it
        calls = _probe_by_dir(monkeypatch)
        cr._fleet_flip_leg(cr._fleet_dirs(), *(cr._fleet_account_rows(cr._fleet_dirs())[:1]), 98.0)
        assert len([c for c in calls if c["dir"] == "seo"]) == want, (cls, epoch, calls)


def test_b9_the_active_window_is_thirty_minutes_and_its_probes_are_bounded(tmp_path, monkeypatch):
    _fleet_b(tmp_path, monkeypatch)
    for age, want in ((31 * 60.0, 1), (29 * 60.0, 0)):
        _cache_ok("sarp@ocoron.com", age)
        calls = _probe_by_dir(monkeypatch)
        cr._fleet_flip_leg(cr._fleet_dirs(), *(cr._fleet_account_rows(cr._fleet_dirs())[:1]), 98.0)
        active = [c for c in calls if c["dir"] == "seo"]
        assert len(active) == want, (age, calls)
        assert all(c["timeout"] == 45 for c in active)
    _cache_ok("ob@ocoron.com", 31 * 60.0)
    assert cr._probe_account("ob@ocoron.com", "intel") == "ok"  # standby: 6 h window


def test_b6_the_wrapper_parks_the_account_its_call_was_bound_to(tmp_path, monkeypatch, capsys):
    """D4b: the refusal parks the account of the fleet dir the call was bound to AT CALL TIME —
    never the pointer's when it moved meanwhile; unbound calls park nothing."""
    fleet = _fleet_b(tmp_path, monkeypatch, active="seo")
    _alerts(monkeypatch)

    def run_and_repoint(argv, **kw):
        if argv and argv[0] == "claude" and "-p" in argv and "ok" in argv:
            return subprocess.CompletedProcess(argv, 1, REFUSAL, "")  # the confirmation
        _point(fleet, "intel")  # a tick flips the pointer during the long call
        return subprocess.CompletedProcess(argv, 1, REFUSAL, "")

    monkeypatch.setattr(cr.subprocess, "run", run_and_repoint)
    capsys.readouterr()
    env = {"CLAUDE_CONFIG_DIR": str(fleet / "active"), "PATH": os.environ.get("PATH", "")}
    result = cr.run_claude(["claude", "-p", "do the thing"], 30, str(tmp_path), env)
    assert result.stdout == REFUSAL
    assert json.loads((fleet / "parked.json").read_text()) == ["sarp@ocoron.com"]
    assert capsys.readouterr().out == ""

    (fleet / "parked.json").unlink()
    unbound = {"PATH": os.environ.get("PATH", "")}
    cr.run_claude(["claude", "-p", "do the thing"], 30, str(tmp_path), unbound)
    assert not (fleet / "parked.json").exists()
    assert "capability refused outside the fleet" in capsys.readouterr().err

    healthy_quote = json.dumps(
        {"type": "result", "is_error": False, "result": "it said oauth_org_not_allowed"}
    )
    monkeypatch.setattr(
        cr.subprocess,
        "run",
        lambda argv, **kw: subprocess.CompletedProcess(argv, 0, healthy_quote, ""),
    )
    cr.run_claude(["claude", "-p", "x"], 30, str(tmp_path), env)
    assert not (fleet / "parked.json").exists()


# ── Phase B scoped review, round 1 ──────────────────────────────────────────────────────────────


def test_br1_a_fifo_a_huge_file_or_a_non_ascii_digit_never_stalls_the_marker_read(
    tmp_path, monkeypatch
):
    locks = tmp_path / "locks"
    locks.mkdir()
    monkeypatch.setattr(cr, "_selfwatch_lock_dir", lambda: locks)
    monkeypatch.setattr(cr, "_now", lambda: FLEET_NOW)
    os.mkfifo(locks / "fifo.errparked")  # an open() without O_NONBLOCK would block here forever
    (locks / "sup.errparked").write_text("oauth_org_not_allowed ²³\n")
    (locks / "big.errparked").write_text(
        f"oauth_org_not_allowed {int(FLEET_NOW - 60)}\n" + "x" * 5_000_000
    )
    started = time.monotonic()
    assert cr._session_refusal_epoch() == FLEET_NOW - 60
    assert time.monotonic() - started < 2.0


def test_br2_a_rotation_that_lands_on_a_refusal_is_not_reported_recovered(tmp_path, monkeypatch):
    """Legacy host: a 401, a rotation, and the standby answers with the org refusal — the 401
    alert must not claim the call recovered."""
    monkeypatch.setenv("CLAUDE_ROTATE_NO_USAGE_CAPTURE", "1")
    monkeypatch.setenv("CLAUDE_FLEET_ROOT", str(tmp_path / "no-fleet"))
    answers = iter(
        [
            subprocess.CompletedProcess(["claude"], 1, "", "API Error: 401 authentication_error"),
            subprocess.CompletedProcess(["claude"], 1, REFUSAL, ""),
        ]
    )
    monkeypatch.setattr(cr.subprocess, "run", lambda *a, **k: next(answers))
    monkeypatch.setattr(cr, "_list_accounts", lambda: [tmp_path / "a", tmp_path / "b"])
    monkeypatch.setattr(cr, "_active_account", lambda: tmp_path / "a")
    monkeypatch.setattr(cr, "_rotate_active_account", lambda avoid=frozenset(): "b")
    monkeypatch.setattr(cr, "_should_alert_401", lambda: True)
    sent = []
    monkeypatch.setattr(cr, "_notify_telegram", lambda text: sent.append(text) or True)
    cr.run_claude(["claude", "-p", "x"], 30, str(tmp_path), {"PATH": os.environ.get("PATH", "")})
    assert sent and not any("recovered" in t for t in sent), sent


def test_br3_the_promote_probe_is_bounded_at_45_seconds(tmp_path, monkeypatch):
    _fleet_b(tmp_path, monkeypatch)
    calls = _probe_by_dir(monkeypatch)
    monkeypatch.setattr(
        cr, "_validated_pick_reading", lambda acc, ex, verbose=False: ("intel", "ob@ocoron.com")
    )
    assert cr._validated_pick([], set(), probe=True) == ("intel", "ob@ocoron.com")
    assert [c["timeout"] for c in calls] == [45]


def test_br4_the_wrapper_parks_by_the_dirs_account_when_no_identity_is_pinned(
    tmp_path, monkeypatch
):
    fleet = _fleet_b(tmp_path, monkeypatch)
    table = json.loads((fleet / "assignments.json").read_text())
    table["intel"]["identity"] = "pending-login"
    table["intel"]["account"] = "ob@ocoron.com"
    (fleet / "assignments.json").write_text(json.dumps(table))
    _probe_by_dir(monkeypatch, refused={"intel"})
    _alerts(monkeypatch)
    cr._wrapper_park("intel")
    assert json.loads((fleet / "parked.json").read_text()) == ["ob@ocoron.com"]


def test_br5_the_operators_pause_holds_the_whole_active_re_check(tmp_path, monkeypatch):
    fleet = _fleet_b(tmp_path, monkeypatch)
    calls = _probe_by_dir(monkeypatch, refused={"seo"})
    monkeypatch.setattr(cr, "_switch_paused", lambda: True)
    cr._fleet_flip_leg(cr._fleet_dirs(), cr._fleet_account_rows(cr._fleet_dirs())[0], 98.0)
    assert [c for c in calls if c["timeout"] == 45] == []
    assert not (fleet / "parked.json").exists()


def test_br6_a_refused_candidate_is_skipped_for_the_rest_of_the_call_even_unparked(
    tmp_path, monkeypatch
):
    """An unknown identity refuses — nothing can be parked or walled — and the loop must still move
    on to the next candidate rather than re-pick it."""
    _fleet_b(tmp_path, monkeypatch)
    _probe_by_dir(monkeypatch, refused={"intel"})
    seen = []

    def reading(acc, ex, verbose=False):
        seen.append(set(ex))
        assert len(seen) < 5, "the refused candidate was re-picked"
        for slug, email in (("intel", "stranger@x.com"), ("seo", "sarp@ocoron.com")):
            if email not in ex:
                return slug, email
        return None

    monkeypatch.setattr(cr, "_validated_pick_reading", reading)
    assert cr._validated_pick([], set(), probe=True) == ("seo", "sarp@ocoron.com")


def test_br7_a_marker_inside_the_skew_tolerance_counts_and_the_flip_alert_has_its_own_key(
    tmp_path, monkeypatch
):
    fleet = _fleet_b(tmp_path, monkeypatch)
    locks = tmp_path / "locks"
    locks.mkdir()
    (locks / "s.errparked").write_text(f"oauth_org_not_allowed {int(FLEET_NOW + 30)}\n")
    _cache_ok("sarp@ocoron.com", 5 * 60.0)
    _probe_by_dir(monkeypatch, refused={"seo"})
    sent = _alerts(monkeypatch)
    assert cr._cmd_tick() == 0
    assert os.readlink(fleet / "active") == "intel"
    assert "capability-flip-sarp@ocoron.com" in [k for _m, k in sent]


# ── Phase B scoped review, pass 2 ───────────────────────────────────────────────────────────────


def test_br2b_a_rotation_onto_a_refusal_alerts_billing_not_dead_credentials(tmp_path, monkeypatch):
    """The standby's credentials work — its organisation refuses. The alert must name the billing
    check, never the all-dead 're-capture a fresh account' advice."""
    monkeypatch.setenv("CLAUDE_ROTATE_NO_USAGE_CAPTURE", "1")
    monkeypatch.setenv("CLAUDE_FLEET_ROOT", str(tmp_path / "no-fleet"))
    answers = iter(
        [
            subprocess.CompletedProcess(["claude"], 1, "", "API Error: 401 authentication_error"),
            subprocess.CompletedProcess(["claude"], 1, REFUSAL, ""),
        ]
    )
    monkeypatch.setattr(cr.subprocess, "run", lambda *a, **k: next(answers))
    monkeypatch.setattr(cr, "_list_accounts", lambda: [tmp_path / "a", tmp_path / "b"])
    monkeypatch.setattr(cr, "_active_account", lambda: tmp_path / "a")
    monkeypatch.setattr(cr, "_rotate_active_account", lambda avoid=frozenset(): "b")
    monkeypatch.setattr(cr, "_should_alert_401", lambda: True)
    sent = []
    monkeypatch.setattr(cr, "_notify_telegram", lambda text: sent.append(text) or True)
    cr.run_claude(["claude", "-p", "x"], 30, str(tmp_path), {"PATH": os.environ.get("PATH", "")})
    assert len(sent) == 1, sent
    assert "billing" in sent[0] and "'b'" in sent[0], sent
    assert "all credentials are dead" not in sent[0], sent


def test_br8_the_pause_holds_every_candidate_probe_even_with_the_active_already_parked(
    tmp_path, monkeypatch
):
    """With the operator's pause marker set and the active account already parked, the tick
    withholds the flip — and spends no probe on, and parks nothing of, the successor."""
    fleet = _fleet_b(tmp_path, monkeypatch)
    (fleet / "parked.json").write_text(json.dumps(["sarp@ocoron.com"]))
    cr._rotate_state_dir().mkdir(parents=True, exist_ok=True)
    (cr._rotate_state_dir() / "switch-paused").write_text("paused\n")
    calls = _probe_by_dir(monkeypatch, refused={"intel"})
    sent = _alerts(monkeypatch)
    assert cr._cmd_tick() == 0
    assert os.readlink(fleet / "active") == "seo"
    assert [c for c in calls if c["timeout"] == 45] == []
    assert json.loads((fleet / "parked.json").read_text()) == ["sarp@ocoron.com"]
    assert not any(k.startswith("capability-") for _m, k in sent), sent


def test_br9_a_marker_inside_the_skew_tolerance_is_clamped_to_now(tmp_path, monkeypatch):
    """A marker up to the skew tolerance in the future counts — as NOW, so it cannot expire a
    verdict the tick records after the refusal it reports."""
    locks = tmp_path / "locks"
    locks.mkdir()
    monkeypatch.setattr(cr, "_selfwatch_lock_dir", lambda: locks)
    monkeypatch.setattr(cr, "_now", lambda: FLEET_NOW)
    (locks / "s.errparked").write_text(f"oauth_org_not_allowed {int(FLEET_NOW + 30)}\n")
    assert cr._session_refusal_epoch() == FLEET_NOW


def test_br10_an_unreadable_pause_state_holds_the_probe_and_never_raises(tmp_path, monkeypatch):
    """A state dir that cannot be read fails CLOSED like the install it guards: the pick is
    returned unprobed, nothing is parked, and nothing escapes into the tick."""
    _fleet_b(tmp_path, monkeypatch)
    calls = _probe_by_dir(monkeypatch, refused={"intel"})

    def unreadable():
        raise PermissionError(13, "state dir unreadable")

    monkeypatch.setattr(cr, "_rotate_state_dir", unreadable)
    monkeypatch.setattr(
        cr, "_validated_pick_reading", lambda acc, ex, verbose=False: ("intel", "ob@ocoron.com")
    )
    assert cr._validated_pick([], set(), probe=True) == ("intel", "ob@ocoron.com")
    assert calls == []


def test_br11_an_unreadable_pause_state_says_the_active_re_check_is_held(
    tmp_path, monkeypatch, capsys
):
    """Fail closed, but never silently: the operator never asked for this hold, so the tick names
    it — and still spends no probe and parks nothing."""
    fleet = _fleet_b(tmp_path, monkeypatch)
    calls = _probe_by_dir(monkeypatch, refused={"seo"})
    monkeypatch.setattr(cr, "_pause_state", lambda: cr._PAUSE_ERROR)
    cr._fleet_flip_leg(cr._fleet_dirs(), cr._fleet_account_rows(cr._fleet_dirs())[0], 98.0)
    assert "capability re-check HELD — pause state unreadable" in capsys.readouterr().out
    assert [c for c in calls if c["timeout"] == 45] == []
    assert not (fleet / "parked.json").exists()


# ── Finish review (whole plan), pass 1 ──────────────────────────────────────────────────────────


def test_br12_a_text_mode_call_that_is_refused_parks_its_account_after_the_json_confirmation(
    tmp_path, monkeypatch
):
    """rest-S1/S2: most wrapped callers run claude in TEXT mode, so the refusal arrives as text, not
    a JSON result. A failed call carrying the code parks — through `_auto_park`'s own JSON probe,
    so a call that merely quotes the code (rc 0) or a false positive the probe answers healthy
    parks nothing."""
    fleet = _fleet_b(tmp_path, monkeypatch, active="seo")
    _alerts(monkeypatch)
    text_refusal = 'API Error: 403 {"error":{"type":"oauth_org_not_allowed"}}\n'
    env = {"CLAUDE_CONFIG_DIR": str(fleet / "active"), "PATH": os.environ.get("PATH", "")}

    def wrapped(call_rc, call_out, probe_out):
        def run(argv, **kw):
            if "--output-format" in argv:  # _auto_park's confirmation probe
                return subprocess.CompletedProcess(
                    argv, 1 if probe_out is REFUSAL else 0, probe_out, ""
                )
            return subprocess.CompletedProcess(argv, call_rc, call_out, "")

        return run

    monkeypatch.setattr(cr.subprocess, "run", wrapped(1, text_refusal, REFUSAL))
    cr.run_claude(["claude", "-p", "do the thing"], 30, str(tmp_path), env)
    assert json.loads((fleet / "parked.json").read_text()) == ["sarp@ocoron.com"]

    (fleet / "parked.json").unlink()
    monkeypatch.setattr(
        cr.subprocess, "run", wrapped(0, "it said oauth_org_not_allowed\n", REFUSAL)
    )
    cr.run_claude(["claude", "-p", "do the thing"], 30, str(tmp_path), env)
    assert not (fleet / "parked.json").exists(), "a successful call quoting the code never parks"

    monkeypatch.setattr(cr.subprocess, "run", wrapped(1, text_refusal, HEALTHY))
    cr.run_claude(["claude", "-p", "do the thing"], 30, str(tmp_path), env)
    assert not (fleet / "parked.json").exists(), "the confirmation probe stops a false positive"


def test_br13_a_401_that_quotes_the_refusal_code_still_rotates(monkeypatch):
    """Finish review pass 2, rest-S3: the text fallback never outranks a rotation signal — a 401 or a
    usage limit whose text happens to carry the code is a 401 or a limit, not a refusal."""
    quoted = "API Error: 401 authentication_error (earlier output mentioned oauth_org_not_allowed)"
    assert cr.is_auth_401(quoted)
    assert not cr._call_refused(subprocess.CompletedProcess(["claude"], 1, "", quoted))
    plain = 'API Error: 403 {"error":{"type":"oauth_org_not_allowed"}}'
    assert cr._call_refused(subprocess.CompletedProcess(["claude"], 1, plain, ""))
    assert cr._call_refused(subprocess.CompletedProcess(["claude"], 1, "", plain)), "stderr counts"
    assert not cr._call_refused(subprocess.CompletedProcess(["claude"], None, plain, "")), "timeout"
