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
