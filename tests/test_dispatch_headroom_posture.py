"""Phase C, C12: the seat budget reads the SAME posture the prompt line does.

`dispatch_headroom.quota()` shells out to `claude_rotate.py --status --json`, which since Phase B
carries the posture beside the picture. When the posture is FRESH its band and hottest reading win,
so the seat budget and the `QUOTA:` line every prompt carries can never name two different bands
for one box. Stale or absent, the picture's own values stand — today's behaviour, unchanged.
"""

from __future__ import annotations

import importlib.util
import json
import os
import time
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parents[1] / "scripts" / "sysadmin" / "dispatch_headroom.py"


def _load():
    spec = importlib.util.spec_from_file_location("dispatch_headroom_posture_probe", _SRC)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def _payload(*, posture_ts, hot=92.0, band="RED", picture_hot=60.0, posture_slug="ozgurbasak"):
    """A `--status --json` payload whose PICTURE is cool and whose POSTURE is hot, so any
    assertion below distinguishes which one the budget actually read."""
    doc = {
        "picture": {
            "active": "ozgurbasak@ocoron.com",
            "accounts": [
                {
                    "email": "ozgurbasak@ocoron.com",
                    "slugs": ["ozgurbasak"],
                    "state": "active",
                    "session_pct": picture_hot,
                    "weekly_pct": 10.0,
                    "in_drain_band": False,
                },
                {
                    "email": "mob@ocoron.com",
                    "state": "eligible",
                    "session_pct": 1.0,
                    "weekly_pct": 1.0,
                    "in_drain_band": False,
                },
            ],
            "thresholds": {"drain_band": 85.0},
            "hold": None,
        },
    }
    if posture_ts is not None:
        doc["posture"] = {
            "schema": 1,
            "ts": posture_ts,
            "active": {
                "slug": posture_slug,
                "windows": {"five_hour": {"utilization": hot}, "seven_day": {"utilization": 10.0}},
                "hottest": "five_hour",
                "band": band,
                # the account's OWN reading beside the fleet's (D-275); the two can disagree by design
                "band_account": "RED" if band == "GREEN" else band,
            },
        }
    return json.dumps(doc)


def _pin(mod, monkeypatch, raw):
    class _Proc:
        stdout = raw

    monkeypatch.setattr(mod.subprocess, "run", lambda *a, **k: _Proc())


def test_dispatch_headroom_prefers_a_fresh_posture_band(monkeypatch):
    """C12 — a fresh posture overwrites `hottest_pct` and adds `band`."""
    mod = _load()
    _pin(mod, monkeypatch, _payload(posture_ts=time.time()))
    q = mod.quota()
    assert q["ok"] is True
    assert q["hottest_pct"] == 92.0, "the picture's 60 was used — the posture was ignored"
    assert q["band"] == "RED"
    assert q["band_account"] == "RED", "the account's own band travels beside the fleet's"


def test_a_stale_posture_leaves_the_picture_in_charge(monkeypatch):
    """C12b — stale is ABSENT, and absent changes nothing: the picture's values stand."""
    mod = _load()
    _pin(mod, monkeypatch, _payload(posture_ts=time.time() - 901.0))
    q = mod.quota()
    assert q["hottest_pct"] == 60.0, "a stale posture must not steer the seat budget"
    assert "band" not in q

    _pin(mod, monkeypatch, _payload(posture_ts=None))
    q = mod.quota()
    assert q["hottest_pct"] == 60.0 and "band" not in q


@pytest.mark.parametrize("ts", ["soon", None, float("nan"), float("inf"), True])
def test_a_malformed_posture_timestamp_is_absent_never_fresh(monkeypatch, ts):
    """C12c — a `ts` that is not a finite number is ABSENT. `True` is in this list on purpose:
    `isinstance(True, int)` is True in Python, so a bool would otherwise read as epoch 1."""
    mod = _load()
    doc = json.loads(_payload(posture_ts=time.time()))
    doc["posture"]["ts"] = ts
    _pin(mod, monkeypatch, json.dumps(doc) if ts is not True else json.dumps(doc))
    q = mod.quota()
    assert q["hottest_pct"] == 60.0, (ts, q)
    assert "band" not in q


def test_a_posture_about_another_account_never_steers_the_seat_budget(monkeypatch):
    """C12e — WHOSE posture is it? The posture is keyed by SLUG and the picture by EMAIL.

    Right after a flip the previous tick's posture is still inside the staleness window, so a
    fresh-but-stale-pointer posture would hand the budget a band for the account we just LEFT.
    Both directions are graded, and the dangerous one is the second: a hot active account reported
    GREEN would license a heavy fan-out on the very account that is nearly out of quota.
    """
    mod = _load()

    # over-restrictive: cool active account, RED posture about someone else
    _pin(mod, monkeypatch, _payload(posture_ts=time.time(), posture_slug="someone-else"))
    q = mod.quota()
    assert q["hottest_pct"] == 60.0, q
    assert "band" not in q, "a posture about another account must not set the band"
    assert "band_account" not in q, "nor the account's own band — it is about someone else"

    # fail-OPEN, the one that matters: hot active account, cool posture about someone else
    _pin(
        mod,
        monkeypatch,
        _payload(
            posture_ts=time.time(),
            posture_slug="someone-else",
            hot=5.0,
            band="GREEN",
            picture_hot=96.0,
        ),
    )
    q = mod.quota()
    assert q["hottest_pct"] == 96.0, f"the picture's hot reading was overwritten by a cool one: {q}"
    assert "band" not in q

    # and the matching slug still wins, or the check would have broken the feature
    _pin(mod, monkeypatch, _payload(posture_ts=time.time()))
    assert mod.quota()["band"] == "RED"

    # ⚠️ a STRING `slugs` would make `in` a SUBSTRING test, so a posture for `ob` would match a row
    # listing `sarp-ob-x` — defence in depth, since the picture always emits a list today
    doc = json.loads(_payload(posture_ts=time.time(), posture_slug="ob", hot=5.0, band="GREEN"))
    doc["picture"]["accounts"][0]["slugs"] = "sarp-ob-x"
    doc["picture"]["accounts"][0]["session_pct"] = 96.0
    _pin(mod, monkeypatch, json.dumps(doc))
    q = mod.quota()
    assert q["hottest_pct"] == 96.0 and "band" not in q, q


def test_the_seat_budget_never_reads_the_operators_real_run_records(tmp_path, monkeypatch):
    """The run-record dir is resolved AT CALL TIME from `COMMAND_RUN_DIR`, the key the conftest pins.

    ⚠️ It was a module constant bound to `Path.home()` at import, which no fixture could pin — so a
    suite run inside a live Claude session read the OPERATOR'S REAL seat reservations and sized its
    budget against them. Read-only, so smaller than the `/opt` constant of the same shape that let a
    grader mail 49 live project mailboxes on 2026-09-16, but the same defect. Pre-existing: 1b971416
    (D-189), not this plan.
    """
    mod = _load()
    pinned = os.environ.get("COMMAND_RUN_DIR")
    assert pinned, "COMMAND_RUN_DIR is unset inside a test — the conftest autouse pin is gone"
    assert mod._runs_dir() == Path(pinned)
    assert mod._runs_dir() != Path.home() / ".claude" / "state" / "command-runs"

    # and the CONSUMER honours it: a record in the pinned dir is seen, and the real dir is not read
    runs = Path(pinned)
    runs.mkdir(parents=True, exist_ok=True)
    (runs / "other.json").write_text(
        json.dumps({"state": "running", "dispatch": {"seats": 3, "ts": time.time()}}),
        encoding="utf-8",
    )
    seen = mod.siblings(exclude_sid="not-this-one")
    assert seen["seats"] >= 3, seen


def test_the_staleness_bound_is_the_one_env_key_the_hook_reads(monkeypatch):
    """C12d — three readers, ONE env key and one default. A second hardcoded 900 is how two
    readers come to disagree about whether the same file is stale."""
    mod = _load()
    hook_spec = importlib.util.spec_from_file_location(
        "quota_posture_hook_stale_probe",
        _SRC.parent / "quota_posture_hook.py",
    )
    hook = importlib.util.module_from_spec(hook_spec)
    hook_spec.loader.exec_module(hook)
    for raw, expect in (
        (None, 900.0),
        ("120", 120.0),
        ("nonsense", 900.0),
        ("0", 900.0),
        ("-5", 900.0),
        ("nan", 900.0),
        ("inf", 900.0),
    ):
        if raw is None:
            monkeypatch.delenv("QUOTA_POSTURE_STALE_S", raising=False)
        else:
            monkeypatch.setenv("QUOTA_POSTURE_STALE_S", raw)
        assert mod._posture_stale_s() == expect, raw
        assert hook._stale_s() == expect, raw
        assert mod._posture_stale_s() == hook._stale_s(), raw


def test_a_fresh_posture_publishes_the_fleet_band_and_the_accounts_own_band_distinctly(monkeypatch):
    """Delta 8 seat C: `band_account` shipped without a grader. Since D-275 `band` is the FLEET's and
    can legitimately read GREEN beside a hot account; the account's own band travels with it so no
    reader has to infer which axis a number belongs to — and dropping the field must red."""
    mod = _load()
    _pin(mod, monkeypatch, _payload(posture_ts=time.time(), band="GREEN"))
    q = mod.quota()
    assert q["ok"] is True
    assert q["band"] == "GREEN" and q["band_account"] == "RED", q


@pytest.mark.parametrize(
    ("hold", "walls"),
    [
        (None, False),
        ({"tier": "urgent-90"}, False),
        ({"tier": "walled"}, True),
        ({}, True),  # a pre-tier hold fails closed, like `_stamp_tier`
        ({"tier": "nonsense"}, True),
        ("unreadable", True),  # a hold this reader cannot read fails closed (D-699 item 7)
    ],
)
def test_dispatch_headroom_urgent_tier_is_not_a_wall(monkeypatch, hold, walls):
    """W-37003fa1 — only the `walled` tier holds every session's tools (D-306). At `urgent-90`
    quota_stop.py runs the D-1113 lane — it parks builders but lets a coordinator_mode merge owner
    and an open-P0 owner continue — and the posture hook allows Agent with a live run, so a seat
    budget of 0 there would stall the very sessions the lane keeps working; the band decides the
    cap instead. `_hold_is_wall`'s
    semantics (claude_rotate.py), mirrored."""
    mod = _load()
    doc = json.loads(_payload(posture_ts=None))
    doc["picture"]["hold"] = hold
    _pin(mod, monkeypatch, json.dumps(doc))
    q = mod.quota()
    assert q["ok"] is True, q
    assert q["hold"] is walls, (hold, q["hold"])


def test_dispatch_headroom_hold_predicate_matches_the_tick(monkeypatch):
    """The seat budget's `_hold_is_wall` is a hand MIRROR of `claude_rotate.py::_hold_is_wall` —
    this script shells out to the tick and imports none of it. Grade both against one corpus, so
    a third tier added to the tick cannot silently desync the seat budget (review B-S3)."""
    import importlib.util as _iu

    mod = _load()
    spec = _iu.spec_from_file_location(
        "rotate_hold_probe",
        Path(__file__).resolve().parents[1] / "scripts/sysadmin/claude_rotate.py",
    )
    tick = _iu.module_from_spec(spec)
    spec.loader.exec_module(tick)
    corpus = (
        None,
        {},
        {"tier": None},
        {"tier": "walled"},
        {"tier": "urgent-90"},
        {"tier": "URGENT-90"},
        {"tier": "x"},
        "s",
        0,
        [],
        [{"tier": "urgent-90"}],
    )
    for hold in corpus:
        assert mod._hold_is_wall(hold) is tick._hold_is_wall(hold), hold


# ── W-3e924ccb: a session on an Anthropic API key is not sized against the PLAN quota ────────────

_BOX = {"ok": True, "mem_available_gb": 64.0, "mem_total_gb": 64.0, "cores": 16, "load1": 0.0}
_COOL_Q = {
    "ok": True,
    "active": "a@x",
    "hottest_pct": 10.0,
    "eligible": 1,
    "eligible_raw": 1,
    "active_in_band": False,
    "hold": False,
    "drain_band": 85.0,
}


def _walled_quota(mod, monkeypatch, tmp_path, line2, *, tier="walled", picture_hot=60.0):
    """`quota()` over a picture whose hold reads `tier` (the picture folds `battery` into `walled`)
    and a real `fleet-exhausted` stamp whose line 2 is `line2` (None: no stamp at all), in a tmp
    ROTATE_STATE_DIR."""
    monkeypatch.setenv("ROTATE_STATE_DIR", str(tmp_path))
    if line2 is not None:
        (tmp_path / "fleet-exhausted").write_text(f"0\n{line2}\n", encoding="utf-8")
    doc = json.loads(_payload(posture_ts=None, picture_hot=picture_hot))
    doc["picture"]["hold"] = {"tier": tier}
    _pin(mod, monkeypatch, json.dumps(doc))
    return mod.quota()


@pytest.mark.parametrize(
    ("line2", "tier", "picture_hot"),
    [
        ("walled", "walled", 60.0),  # the wall: base caps at 0
        ("urgent-90", "urgent-90", 92.0),  # the lane in the drain band: base holds the floor of 3
    ],
)
def test_an_api_key_session_is_not_capped_by_the_plan_wall(
    monkeypatch, tmp_path, line2, tier, picture_hot
):
    """An API-key session's seats draw the key, not the plan (D-1243): at a plain quota-tier stamp
    the budget is the box's — no `quota_cap` at all — and a reason line says why."""
    import sys

    mod = _load()
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-api03-x")
    q = _walled_quota(mod, monkeypatch, tmp_path, line2, tier=tier, picture_hot=picture_hot)
    assert q["api_key_free"] is True, q
    r = mod.budget(4, False, _BOX, q)
    assert "quota_cap" not in r["caps"], r["caps"]
    # exactly what a cool, holdless plan picture would allow — not a partial cap
    assert r["seats"] == mod.budget(4, False, _BOX, _COOL_Q)["seats"] > 3, r
    assert any("Anthropic API key" in line for line in r["reasons"]), r["reasons"]
    # the hook is loaded under a private name and never registered (critique: Opus 3, Fable C5)
    assert "_dispatch_headroom_posture_hook" not in sys.modules
    assert "quota_posture_hook" not in sys.modules or sys.modules["quota_posture_hook"] is not (
        next(iter(mod._hook_cache.values()))
    )


def test_a_hold_with_no_stamp_where_the_hook_looks_keeps_the_cap(monkeypatch, tmp_path):
    """The picture's hold can come from the tick's TMP fallback stamp
    (`claude_rotate._fleet_exhaustion_stamp`), which the hook never reads — and the hook answers
    'free' when it finds no stamp. A hold the hook cannot see is never exempted."""
    mod = _load()
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-api03-x")
    q = _walled_quota(mod, monkeypatch, tmp_path, None)
    assert q["api_key_free"] is False and "different files" in q.get("api_key_why", ""), q
    r = mod.budget(1, False, _BOX, q)
    assert r["caps"]["quota_cap"] == 0 and r["seats"] == 0, r


def test_an_api_key_session_skips_the_unknown_quota_floor(monkeypatch, tmp_path):
    """A key session's seats do not depend on the plan picture, so an unreadable picture does not
    hold it at the floor (deliberate: Opus critique 4) — when the hook's own stamp shows a plain
    quota tier. An unreadable picture may HIDE a hold (review pass 1: the tick's stamp may sit in
    its tmp fallback), so with no stamp where the hook looks the floor stands."""
    mod = _load()
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-api03-x")
    monkeypatch.setenv("ROTATE_STATE_DIR", str(tmp_path))
    _pin(mod, monkeypatch, "not json")
    (tmp_path / "fleet-exhausted").write_text("0\nwalled\n", encoding="utf-8")
    q = mod.quota()
    assert q["ok"] is False and q["api_key_free"] is True, q
    r = mod.budget(4, False, _BOX, q)
    assert "quota_cap" not in r["caps"] and r["seats"] > 3, r

    (tmp_path / "fleet-exhausted").unlink()
    q = mod.quota()
    assert q["ok"] is False and q["api_key_free"] is False, q
    assert "different files" in q["api_key_why"], q
    r = mod.budget(4, False, _BOX, q)
    assert r["caps"]["quota_cap"] == 3 == r["seats"], r


@pytest.mark.parametrize(
    ("line2", "extra"),
    [
        ("battery", {}),  # the battery hold protects the box, never plan quota (D-898)
        ("garbage", {}),  # an unknown tier fails closed
        ("walled", {"CLAUDE_CODE_OAUTH_TOKEN": "sk-ant-oat01-x"}),  # a second credential holds
    ],
)
def test_battery_or_a_second_credential_keeps_the_wall_cap(monkeypatch, tmp_path, line2, extra):
    mod = _load()
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-api03-x")
    for k, v in extra.items():
        monkeypatch.setenv(k, v)
    q = _walled_quota(mod, monkeypatch, tmp_path, line2)
    assert q["api_key_free"] is False, q
    # the operator is told why the key did not lift the cap (review pass 1, Opus F1)
    why = q.get("api_key_why", "")
    assert why.startswith("the API key does not lift the plan caps"), q
    assert ("another credential" in why) is bool(extra), why
    r = mod.budget(1, False, _BOX, q)
    assert r["caps"]["quota_cap"] == 0 and r["seats"] == 0, r


@pytest.mark.parametrize(
    ("line2", "shown"),
    [
        ("walled", "api key: exempt"),
        ("battery", "api key: the API key does not lift the plan caps"),
    ],
)
def test_the_cli_prints_the_exemption_state(monkeypatch, tmp_path, capsys, line2, shown):
    """The human output names the exemption beside `hold=` (review pass 1: Sonnet F3, Opus F2,
    Haiku F3), and the `--json` payload carries `quota.api_key_free`."""
    mod = _load()
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-api03-x")
    q = _walled_quota(mod, monkeypatch, tmp_path, line2)
    monkeypatch.setattr(mod, "box", lambda: dict(_BOX))
    monkeypatch.setattr(mod, "quota", lambda: dict(q))
    monkeypatch.setattr(mod, "siblings", lambda **_k: {"ok": True, "seats": 0, "sessions": 0})
    assert mod.main(["--units", "1"]) == 0
    out = capsys.readouterr().out
    assert f"api_key_free={q['api_key_free']}" in out and shown in out, out
    assert mod.main(["--units", "1", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["quota"]["api_key_free"] is q["api_key_free"], payload["quota"]


@pytest.mark.parametrize("hook_src", [None, "raises"])
def test_a_failed_exemption_read_keeps_the_plan_caps(monkeypatch, tmp_path, hook_src):
    """The predicate is the posture hook's; if it cannot be loaded or raises, the plan caps stand
    (fail toward fewer seats, never an over-dispatch on a plan account) and the payload says why."""
    mod = _load()
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-api03-x")
    hook = tmp_path / "hook.py"
    if hook_src == "raises":
        hook.write_text(
            "from pathlib import Path\n"
            "def _rotate_state_dir():\n    return Path('/nonexistent')\n"
            "def _api_key_free():\n    raise RuntimeError('boom')\n",
            encoding="utf-8",
        )
    monkeypatch.setattr(mod, "_POSTURE_HOOK", hook)
    q = _walled_quota(mod, monkeypatch, tmp_path, "walled")
    assert q["api_key_free"] is False and q.get("api_key_why"), q
    r = mod.budget(1, False, _BOX, q)
    assert r["seats"] == 0, r
