"""Behavior contract for the spend calendar's MONTH AXIS and the subscription fee schedule.

Two operator directives of 2026-09-05, both about what the Usage tab is allowed to show:

1. *"remove the months which does not have data"* — the calendar zero-fills every date from the
   first recorded day to today so a quiet day keeps its cell. That is right WITHIN a month and wrong
   ACROSS months: a gap in the history longer than a month painted whole empty blocks. It is not
   hypothetical — a phantom `2025-08-01` row (a test writing to the live store) dragged the axis back
   through THIRTEEN blank months. The invariant is therefore asymmetric on purpose, and both halves
   are pinned below: a month with no data at all disappears; a quiet day inside a live month stays.

2. *"from now on if i dont state otherwise we will pay 800"* — $800/month is the STANDING default and
   `_MONTHLY_SPEND` holds only the exceptions to it. A future month must price at $800 with no edit;
   the recorded $600 months must keep their own fee forever.

Fixture dates are RELATIVE (the calendar runs to `today`), except where a test pins a real historical
fee — those months are facts and a fixed date is correct there.
"""

from __future__ import annotations

import datetime
import importlib.util
import json
from pathlib import Path

import pytest

_MOD = Path(__file__).resolve().parent.parent / "scripts" / "claude_p_cost.py"
_spec = importlib.util.spec_from_file_location("claude_p_cost_calendar", _MOD)
cpc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cpc)


def _day(offset: int) -> str:
    return (datetime.date.today() - datetime.timedelta(days=offset)).isoformat()


@pytest.fixture
def store(tmp_path, monkeypatch):
    """Isolate every SOURCE: our store goes to tmp, and both upstream readers are aimed at nothing.

    `per_model_spend` calls `merge_usage_store`, which WRITES. A rig that leaves either path pointing
    at the real box mutates live history — that is exactly how the phantom row this suite guards
    against got into the store in the first place.
    """
    monkeypatch.setenv("CLAUDE_USAGE_DAILY", str(tmp_path / "store.json"))
    monkeypatch.setattr(cpc, "_USAGE_HISTORY", tmp_path / "no-such-usage-history.json")
    monkeypatch.setattr(cpc, "_MANAGER_ACCOUNTS", tmp_path / "no-such-accounts")
    # THIRD end, added 2026-09-06 with `collect_from_transcripts`: `merge_usage_store` now also
    # walks ~/.claude/projects (8.8 GB on this box). An unpatched root makes every test here read
    # the operator's real usage — slow (118s), and its result depends on what the box did today.
    monkeypatch.setattr(cpc, "_TRANSCRIPT_ROOT", tmp_path / "no-such-transcripts")

    def _write(days: dict[str, dict[str, int]]) -> None:
        (tmp_path / "store.json").write_text(json.dumps({"days": days}), encoding="utf-8")

    return _write


def _months(daily: list[dict]) -> dict[str, int]:
    """Month → total tokens across the emitted calendar rows."""
    out: dict[str, int] = {}
    for row in daily:
        out[row["date"][:7]] = out.get(row["date"][:7], 0) + (row["tokens"] or 0)
    return out


def test_a_month_with_no_data_at_all_is_absent_from_the_calendar(store):
    # A 70-day hole guarantees at least one calendar month with no recorded day, whatever today is.
    store({_day(70): {"claude-opus-5": 5_000_000}, _day(0): {"claude-opus-5": 7_000_000}})
    months = _months(cpc.per_model_spend()["daily"])
    empty = [m for m, tok in months.items() if tok == 0]
    assert not empty, f"empty month blocks emitted: {empty} (months seen: {sorted(months)})"
    # …and the two months that DO hold data are still there — the guard must not eat the axis.
    assert _day(70)[:7] in months and _day(0)[:7] in months


def test_a_quiet_day_inside_a_live_month_keeps_its_cell(store):
    # The 1st and the 4th of the CURRENT month — always the same month, since no month is shorter
    # than 28 days. An earlier version used today-3 and today and skipped when that pair straddled a
    # boundary, which silently deleted this test on the first three days of every month; a finder
    # priced that at ~3 days in 30, and a test that is absent 10% of the time is absent on exactly
    # the days when boundary behaviour is most likely to break.
    first = datetime.date.today().replace(day=1)
    a, b = first.isoformat(), (first + datetime.timedelta(days=3)).isoformat()
    store({a: {"claude-opus-5": 1_000_000}, b: {"claude-opus-5": 1_000_000}})
    dates = [r["date"] for r in cpc.per_model_spend()["daily"]]
    between = [(first + datetime.timedelta(days=n)).isoformat() for n in (1, 2)]
    # The two silent days between them are still emitted: a quiet day must stay distinguishable from
    # an unrecorded one, and the grid must keep lining up with its weekdays.
    assert between == [d for d in dates if a < d < b]


def test_the_calendar_still_runs_to_today(store):
    # Seeded on the 1st so the current month is always the live one, whatever today's date is: the
    # axis must fill forward to today even when nothing has been recorded since.
    today = datetime.date.today()
    first = today.replace(day=1)
    store({first.isoformat(): {"claude-opus-5": 1_000_000}})
    dates = [r["date"] for r in cpc.per_model_spend()["daily"]]
    # Bounds and CONTIGUITY, not a length arithmetic on today's date. `len(daily) == today.day` was
    # true only because this fixture puts `cal_start` on the 1st; three finders each read it as a
    # defect in the code rather than a fixture-coupled assertion. Stating first, last and "no gaps"
    # says what the axis must actually be, and stays true whatever the fixture seeds.
    assert dates[0] == first.isoformat() and dates[-1] == today.isoformat()
    assert dates == [
        (first + datetime.timedelta(days=n)).isoformat() for n in range((today - first).days + 1)
    ]


def test_an_unlisted_month_prices_at_the_standing_800_default():
    # The operator's standing rule: unless stated otherwise, the fee is $800. A month nobody has
    # edited the schedule for must therefore price at $800 — including months yet to happen.
    assert cpc._spend_for_month("2027-03") == 800.0
    assert cpc._spend_for_month("2026-10") == 800.0
    assert cpc._spend_for_month("2026-09") == 800.0


def test_the_recorded_600_months_keep_their_own_fee():
    # May-July 2026 were paid at $600. History does not get restated at today's price.
    for ym in ("2026-05", "2026-06", "2026-07"):
        assert cpc._spend_for_month(ym) == 600.0


def test_the_schedule_carries_only_exceptions_to_the_default():
    # A row equal to the default is not a fact, it is a maintenance burden that misleads the next
    # reader into thinking the month must be listed to be priced.
    redundant = [ym for ym, fee in cpc._MONTHLY_SPEND.items() if fee == cpc._CURRENT_MONTHLY_SPEND]
    assert not redundant, (
        f"schedule rows equal to the ${cpc._CURRENT_MONTHLY_SPEND:.0f} default: {redundant}"
    )


def test_a_span_crossing_into_an_unlisted_month_prorates_at_the_default():
    got = cpc._prorated_spend(datetime.date(2026, 8, 31), datetime.date(2026, 9, 1))
    assert got == pytest.approx(800.0 / 31 + 800.0 / 30)


def test_a_span_crossing_from_a_listed_month_into_an_unlisted_one_uses_both_fees():
    # The interesting boundary is the one where the fee actually CHANGES — July ($600, listed) into
    # August (unlisted, so the $800 standing default). A span that crosses two unlisted months would
    # pass with the schedule ignored entirely.
    got = cpc._prorated_spend(datetime.date(2026, 7, 31), datetime.date(2026, 8, 1))
    assert got == pytest.approx(600.0 / 31 + 800.0 / 31)
    assert got != pytest.approx(2 * 800.0 / 31), "the listed month must not price at the default"
