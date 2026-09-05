"""Behavior contract for the cost sidecar's PRODUCER — `scripts/claude_p_cost.py::refresh()`.

`refresh()` is the function that rewrites the hub's `claude_p_cost.json`. (`derive_cost.py`'s
`write_cost_sidecar()` is NOT: it has zero code call sites here, its callers left with the
catalog-engine excision at `73bde59a`, and running it would destroy the window keys this file guards.)

Every test below was written against a MUTANT that the previous version of this suite let through.
The Phase-A review ran five mutations — window bounds hardcoded to 2020, `window_start` published as
365 days while the rate used 30, `_MONTHLY_DAYS` collapsed to 1, `built_at` frozen at 2020, and the
0.025 override moved onto the family key — and the suite stayed green on all five. Presence-and-
non-null assertions do not constrain a producer; these tie each published value to what produced it.

Fixture dates are RELATIVE on purpose: the window counts only days inside
`cutoff = today - (_MONTHLY_DAYS - 1)`, so a hardcoded date falls out of the window and reds this
suite about a month after it is written.
"""

from __future__ import annotations

import datetime
import importlib.util
import json
from pathlib import Path

import pytest

_MOD = Path(__file__).resolve().parent.parent / "scripts" / "claude_p_cost.py"
_spec = importlib.util.spec_from_file_location("claude_p_cost_producer", _MOD)
cpc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cpc)

_ACCOUNTS = 3
_SUBSCRIPTION = 200.0
_WINDOW_KEYS = ("window_start", "window_end", "accounts", "spend_usd", "tokens")

_IN_WINDOW = 1_000  # tokens on a day inside the window
_OUT_OF_WINDOW = 999_999_999  # tokens on a day outside it — unmissable if wrongly counted


def _day(offset: int) -> str:
    return (datetime.date.today() - datetime.timedelta(days=offset)).isoformat()


def _model_usage(total: int) -> dict:
    return {"input": total, "output": 0, "cacheRead": 0, "cacheCreation": 0}


def _write_history(path: Path, days: dict[str, int]) -> None:
    path.write_text(
        json.dumps(
            {"days": {d: {"byModel": {"claude-opus-5": _model_usage(t)}} for d, t in days.items()}}
        ),
        encoding="utf-8",
    )


@pytest.fixture
def rig(tmp_path, monkeypatch):
    """Producer pointed at a fixture history + accounts dir, writing to a tmp sidecar."""
    history = tmp_path / "usage-history.json"
    _write_history(history, {_day(1): _IN_WINDOW, _day(10): _IN_WINDOW})
    accounts = tmp_path / "manager-accounts"
    accounts.mkdir()
    for name in ("acct-a", "acct-b", "acct-c"):
        (accounts / name).mkdir()
    (accounts / ".hidden").mkdir()  # dotted entries are not accounts

    out = tmp_path / "claude_p_cost.json"
    monkeypatch.setattr(cpc, "_USAGE_HISTORY", history)
    monkeypatch.setattr(cpc, "_MANAGER_ACCOUNTS", accounts)
    monkeypatch.setattr(cpc, "_SUBSCRIPTION_USD_PER_ACCOUNT", _SUBSCRIPTION)
    monkeypatch.setenv("CLAUDE_P_COST", str(out))
    return out


# ─── the window is DERIVED, not decorative ───────────────────────────────────────────────────────
def test_the_published_bounds_are_the_bounds_the_producer_actually_used(rig):
    """Kills the mutant that publishes a fixed window beside a live rate — the fossil, inverted."""
    data = cpc.refresh()
    today = datetime.date.today()
    assert data["window_end"] == today.isoformat()
    assert (
        data["window_start"] == (today - datetime.timedelta(days=cpc._MONTHLY_DAYS - 1)).isoformat()
    )


def test_the_window_spans_exactly_one_subscription_month(rig):
    """`spend_usd` is ONE month, so the token denominator must be `_MONTHLY_DAYS` dates — not 31."""
    data = cpc.refresh()
    start = datetime.date.fromisoformat(data["window_start"])
    end = datetime.date.fromisoformat(data["window_end"])
    assert (end - start).days + 1 == cpc._MONTHLY_DAYS  # inclusive


def test_days_outside_the_window_are_not_counted(rig, tmp_path, monkeypatch):
    """The window LENGTH is load-bearing and was previously unguarded: `_MONTHLY_DAYS = 1` passed."""
    history = tmp_path / "usage-history.json"
    _write_history(
        history,
        {
            _day(0): _IN_WINDOW,  # today — the upper bound, inclusive
            _day(cpc._MONTHLY_DAYS - 1): _IN_WINDOW,  # the cutoff itself — inclusive
            _day(cpc._MONTHLY_DAYS): _OUT_OF_WINDOW,  # one day past it — must be excluded
            _day(400): _OUT_OF_WINDOW,
        },
    )
    monkeypatch.setattr(cpc, "_USAGE_HISTORY", history)
    data = cpc.refresh()
    assert data["tokens"] == 2 * _IN_WINDOW, (
        f"expected only the two in-window days; got {data['tokens']} — a bound is wrong"
    )


def test_built_at_is_a_fresh_offset_aware_stamp(rig):
    """Kills the frozen-stamp mutant: `built_at > '2000-01-01'` proved nothing.

    OFFSET-AWARE, not UTC: round 3 moved the stamp onto the same clock as the window bounds so it can
    never predate its own data, which means the offset is the box's, not `+00:00`. Awareness is what
    the rule pack's mandate is actually about — naive is the defect class — and it is what makes the
    comparison below sound. (This test was still named `..._utc_stamp` after that change; the final
    round caught the mirror.)
    """
    before = datetime.datetime.now(datetime.UTC)
    data = cpc.refresh()
    stamped = datetime.datetime.fromisoformat(data["built_at"])
    assert stamped.tzinfo is not None, "built_at must be unambiguous — a naive stamp has no clock"
    assert before - datetime.timedelta(seconds=5) <= stamped <= datetime.datetime.now(datetime.UTC)


def test_the_published_rate_is_the_published_denominators(rig):
    """② reconciles against the denominators shipped beside it (catches a wrong divisor)."""
    data = cpc.refresh()
    assert data["amortized_per_mtok"] == pytest.approx(
        data["spend_usd"] / data["tokens"] * 1_000_000.0, rel=1e-9
    )


def test_accounts_and_spend_reflect_the_measured_count(rig):
    data = cpc.refresh()
    assert data["accounts"] == _ACCOUNTS  # three real dirs; the dotted one is not an account
    assert data["spend_usd"] == pytest.approx(_SUBSCRIPTION * _ACCOUNTS)


@pytest.mark.parametrize("state", ["empty", "missing"])
def test_an_unmeasurable_account_count_is_null_not_one(rig, tmp_path, monkeypatch, state):
    """`max(1, n)` floors the RATE; publishing `accounts: 1` would state a guess as fact."""
    acct = tmp_path / "accounts-none"
    if state == "empty":
        acct.mkdir()
    monkeypatch.setattr(cpc, "_MANAGER_ACCOUNTS", acct)
    data = cpc.refresh()
    assert data["accounts"] is None
    assert data["spend_usd"] is None
    assert data["tokens"] > 0  # the measured half is still published


def test_window_is_null_when_the_rate_is_the_research_anchor(rig, tmp_path, monkeypatch):
    """The anchor was derived from NO window, so publishing bounds beside it would be a fiction."""
    history = tmp_path / "empty-history.json"
    history.write_text(json.dumps({"days": {}}), encoding="utf-8")
    monkeypatch.setattr(cpc, "_USAGE_HISTORY", history)
    data = cpc.refresh()
    assert data["amortized_per_mtok"] == pytest.approx(cpc._ANCHOR_USD_PER_TOKEN * 1_000_000.0)
    for key in _WINDOW_KEYS:
        assert key in data, f"{key} must be present even when null — absence reads as an old file"
        assert data[key] is None, f"{key} = {data[key]!r} fabricates a window the anchor never had"


# ─── the carry-forward: the data-loss fix, and its own honesty ───────────────────────────────────
def test_every_key_this_producer_did_not_author_survives(rig):
    """THE DATA-LOSS GUARD. An allowlist would re-create the bug for the next key someone adds."""
    rig.write_text(
        json.dumps(
            {
                "amortized_per_mtok_by_family": {"opus": 0.0054},
                "quota_draw_pct": 4.2,
                "built_at": "2026-08-10T07:17:23",
                "some_future_key": {"written": "by another producer"},
            }
        ),
        encoding="utf-8",
    )
    data = cpc.refresh()
    assert data["amortized_per_mtok_by_family"] == {"opus": 0.0054}
    assert data["some_future_key"] == {"written": "by another producer"}
    assert data["quota_draw_pct"] == pytest.approx(4.2)
    on_disk = json.loads(rig.read_text(encoding="utf-8"))
    assert on_disk["some_future_key"] == {"written": "by another producer"}


def test_a_carried_family_split_is_flagged_as_carried_not_computed(rig):
    """The split is carried, never recomputed — the file must say so, without inventing a date.

    Two earlier revisions stamped `prev["built_at"]`, which is the previous REFRESH's clock rather than
    the split's build time: after one cron tick the stamp claimed today for a map weeks old. The
    lineage is unrecoverable from this file, so the flag states the one thing the producer knows.
    """
    rig.write_text(
        json.dumps(
            {"amortized_per_mtok_by_family": {"opus": 0.0054}, "built_at": "2026-08-10T07:17:23"}
        ),
        encoding="utf-8",
    )
    data = cpc.refresh()
    assert data["amortized_per_mtok_by_family_carried"] is True
    assert "amortized_per_mtok_by_family_built_at" not in data, "a superseded stamp key survived"
    assert "amortized_per_mtok_by_family_carried_from" not in data


def test_the_carried_flag_is_absent_when_there_is_no_split(rig):
    """Absence means "this producer computed nothing to carry", which is different from `false`."""
    rig.write_text(json.dumps({"quota_draw_pct": 1.0}), encoding="utf-8")
    data = cpc.refresh()
    assert "amortized_per_mtok_by_family_carried" not in data


# ─── the producer must never crash off its cron ──────────────────────────────────────────────────
@pytest.mark.parametrize(
    "payload",
    [
        "[1, 2, 3]",
        '"a string"',
        "5",
        "null",
        "true",
        '{"quota_draw_pct": "abc"}',
        '{"quota_draw_pct": [1]}',
    ],
)
def test_a_hostile_previous_sidecar_does_not_crash_the_producer(rig, payload):
    """Phase C puts this on a 06:00 cron: an uncaught raise means the rate silently fossilises."""
    rig.write_text(payload, encoding="utf-8")
    data = cpc.refresh()
    assert data["amortized_per_mtok"] > 0
    assert data["quota_draw_pct"] == 0.0


def test_a_truncated_sidecar_is_replaced_rather_than_crashing(rig):
    rig.write_text('{"amortized_per_mtok": 0.007, "acc', encoding="utf-8")
    data = cpc.refresh()
    assert data["window_end"] == datetime.date.today().isoformat()


def test_built_at_is_never_behind_the_window_it_describes(rig, monkeypatch):
    """ONE clock. A UTC stamp beside LOCAL bounds puts the build a day behind its own data.

    The clock is FROZEN into the danger band on purpose. Asserting this against the real clock is
    green for the wrong reason for 21 hours a day — it only reds between 21:00 and 24:00 UTC on a
    UTC+03:00 box, which is precisely the wall-clock time bomb this suite exists to refuse.
    """
    tz = datetime.timezone(datetime.timedelta(hours=3))
    frozen_local = datetime.datetime(2026, 9, 6, 1, 0, 0, tzinfo=tz)  # == 2026-09-05T22:00Z

    class _FrozenDateTime(datetime.datetime):
        @classmethod
        def now(cls, tz_=None):
            return frozen_local.astimezone(tz_) if tz_ else frozen_local.replace(tzinfo=None)

    class _FrozenDate(datetime.date):
        @classmethod
        def today(cls):
            return datetime.date(2026, 9, 6)

    # Aliases captured OUTSIDE the class body: inside it, `datetime = ...` shadows the module for
    # every following line, so `datetime.timedelta` would resolve against the class being defined.
    _timedelta, _timezone, _utc = datetime.timedelta, datetime.timezone, datetime.UTC

    class _FrozenModule:
        datetime = _FrozenDateTime
        date = _FrozenDate
        timedelta = _timedelta
        timezone = _timezone
        UTC = _utc

    monkeypatch.setattr(cpc, "datetime", _FrozenModule)
    data = cpc.refresh()
    built = datetime.datetime.fromisoformat(data["built_at"])
    assert built.tzinfo is not None, "a naive stamp has no clock at all"
    assert built.date() >= datetime.date.fromisoformat(data["window_end"]), (
        f"built_at {data['built_at']} predates window_end {data['window_end']} — two clocks"
    )


def test_concurrent_producers_do_not_share_a_temp_file(rig):
    """A predictable `<name>.tmp` lets two refreshes interleave into one file before either replaces it.

    Three agent sessions and a cron share this box. Proven by fingerprinting the temp path the writer
    chooses: two calls must never pick the same name.
    """
    seen = []
    real_mkstemp = cpc.tempfile.mkstemp

    def spy(*a, **kw):
        fd, name = real_mkstemp(*a, **kw)
        seen.append(name)
        return fd, name

    cpc.tempfile.mkstemp = spy
    try:
        cpc.refresh()
        cpc.refresh()
    finally:
        cpc.tempfile.mkstemp = real_mkstemp
    assert len(seen) == 2 and seen[0] != seen[1], f"temp names collided: {seen}"


def test_the_target_is_only_ever_reached_by_an_atomic_rename(rig):
    """A torn write loses the family split permanently — nothing in this repo can regenerate it.

    The previous version of this test asserted only that no `*.tmp` was left behind, which a plain
    `path.write_text` satisfies trivially: deleting the entire atomic write left all 36 tests green.
    This asserts the MECHANISM — the sidecar is only ever created by `os.replace`, never written in
    place — which is the only thing that makes a concurrent reader safe.
    """
    replaced: list[tuple] = []
    real_replace = cpc.os.replace

    def spy_replace(src, dst, *a, **kw):
        replaced.append((str(src), str(dst)))
        return real_replace(src, dst, *a, **kw)

    monkey = cpc.os
    monkey.replace = spy_replace
    try:
        rig.unlink(missing_ok=True)
        cpc.refresh()
    finally:
        monkey.replace = real_replace

    assert replaced, "the sidecar was written in place — a torn write is now possible"
    assert replaced[-1][1] == str(rig)
    assert replaced[-1][0] != str(rig), "source and destination are the same path"
    assert json.loads(rig.read_text(encoding="utf-8"))["tokens"] > 0
    assert not list(rig.parent.glob("*.tmp")), "a temp file survived the write"
