"""Behavior contract for Phase B — the reader makes a STALE cost sidecar loud.

`rank_task_subagents._claude_p_preamble` renders the ② amortized rate into
`docs/reference/kilo/TASK_SUBAGENT_SELECTION.md`, the doc `pick_models` reads. Before Phase B it
printed the rate with NO date, so a 26-day-old figure was typographically identical to one built that
morning — which is exactly how a 17%-low rate was rendered as current for weeks.

Three states must stay distinguishable, and the first is the one an over-eager staleness marker would
break: a MISSING sidecar (a project checkout that has none) must keep failing SOFT and render nothing
at all, never a warning.
"""

from __future__ import annotations

import datetime
import importlib.util
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
_KB = _ROOT / "scripts" / "kilo-benchmarks"
sys.path.insert(0, str(_KB))
_spec = importlib.util.spec_from_file_location("rts_staleness", _KB / "rank_task_subagents.py")
rts = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rts)


def _stamp(days_ago: float) -> str:
    return (datetime.datetime.now().astimezone() - datetime.timedelta(days=days_ago)).isoformat(
        timespec="seconds"
    )


def _derived(**over):
    base = {
        "window_start": "2026-08-07",
        "window_end": "2026-09-05",
        "tokens": 106_922_715_198,
        "accounts": 4,
        "built_at": _stamp(0),
    }
    base.update(over)
    return base


def test_a_fresh_rate_shows_its_window_and_says_nothing_alarming():
    out = rts._sidecar_window(_derived())
    assert "2026-08-07→2026-09-05" in out
    assert "106.9B tokens over 4 accounts" in out
    assert "STALE" not in out


def test_a_stale_rate_is_loud_and_says_how_old():
    """The whole point: a rate older than the rebuild cadence cannot look like a fresh one."""
    out = rts._sidecar_window(_derived(built_at=_stamp(26)))
    assert "STALE" in out
    assert "26.0 days ago" in out
    assert str(rts._SIDECAR_STALE_AFTER_HOURS) in out


def test_the_staleness_boundary_is_the_rebuild_cadence():
    """Just inside the window is silent; just outside is loud. Off-by-one here is the whole signal."""
    hours = rts._SIDECAR_STALE_AFTER_HOURS
    assert "STALE" not in rts._sidecar_window(_derived(built_at=_stamp((hours - 1) / 24)))
    assert "STALE" in rts._sidecar_window(_derived(built_at=_stamp((hours + 1) / 24)))


def test_the_anchor_fallback_never_claims_a_window():
    """Null bounds mean the rate is a research constant — printing a window would assert a fiction."""
    out = rts._sidecar_window(
        _derived(window_start=None, window_end=None, tokens=None, accounts=None)
    )
    assert "no window" in out
    assert "ANCHOR" in out
    assert "2026-08-07" not in out


@pytest.mark.parametrize(
    ("built_at", "expected"),
    [(None, "no `built_at`"), ("", "no `built_at`"), ("garbage", "unparseable")],
)
def test_an_undated_or_unparseable_stamp_is_called_out(built_at, expected):
    d = _derived()
    if built_at is None:
        d.pop("built_at")
    else:
        d["built_at"] = built_at
    assert expected in rts._sidecar_window(d)


def test_a_naive_built_at_is_not_treated_as_infinitely_old():
    """Older producers wrote naive local stamps; comparing one to an aware `now` raises, and a
    fail-open `except` would then mark every legacy sidecar STALE forever."""
    naive = datetime.datetime.now().replace(tzinfo=None).isoformat(timespec="seconds")
    assert "STALE" not in rts._sidecar_window(_derived(built_at=naive))


def test_a_missing_sidecar_still_renders_nothing_at_all(monkeypatch, tmp_path):
    """B3's load-bearing half: MISSING and STALE are different states.

    A project checkout without a sidecar must render no line at all — not a staleness warning about a
    file that was never supposed to be there. Proven by pointing the reader at an empty directory.
    """
    missing = tmp_path / "nowhere" / "rank_task_subagents.py"
    missing.parent.mkdir(parents=True)
    missing.write_text("", encoding="utf-8")
    monkeypatch.setattr(rts, "__file__", str(missing))
    assert rts._claude_p_preamble() == []


def test_the_rendered_preamble_actually_carries_the_window(monkeypatch, tmp_path):
    """The helper being right is not the same as the LINE using it.

    Dropping `{window}` from the f-string left every other test in this file green — the same
    helper-tested/call-site-unguarded class this plan's review found three times. This asserts the
    text a reader of TASK_SUBAGENT_SELECTION.md actually sees.
    """
    import json

    sidecar = tmp_path / "claude_p_cost.json"
    sidecar.write_text(
        json.dumps(
            {
                "amortized_per_mtok": 0.00748,
                "quota_draw_pct": 0.0,
                "window_start": "2026-08-07",
                "window_end": "2026-09-05",
                "tokens": 106_922_715_198,
                "accounts": 4,
                "built_at": _stamp(26),
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(rts, "__file__", str(tmp_path / "rank_task_subagents.py"))
    lines = rts._claude_p_preamble()
    assert len(lines) == 1
    rendered = lines[0]
    assert "2026-08-07→2026-09-05" in rendered, "the rendered line carries no window"
    assert "STALE" in rendered, "a 26-day-old rate renders without its staleness marker"
    assert "106.9B tokens over 4 accounts" in rendered


def test_a_future_built_at_is_called_out_rather_than_read_as_fresh():
    """A negative age is below every threshold, so clock skew would render as freshly built.

    Silently passing a future stamp is the same blindness this phase exists to end, in reverse: the
    reader would see no warning at all on a file whose date is nonsense.
    """
    out = rts._sidecar_window(_derived(built_at=_stamp(-3)))
    assert "FUTURE" in out
    assert "3.0 days" in out
    assert "STALE" not in out


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("accounts", True),  # isinstance(True, int) is True in Python — a bool passes a naive check
        ("tokens", True),
        ("tokens", -5),
        ("accounts", -2),
        ("tokens", "lots"),
        ("accounts", None),
    ],
)
def test_a_nonsensical_count_is_omitted_never_rendered_raw(field, value):
    """A nonsensical count must be OMITTED, not coerced into a plausible-looking one.

    Asserting merely that `True` does not appear in the text is too weak: without the bool guard,
    `int(True)` is 1, so `accounts=True` renders "over 1 account" — a fabricated denominator that
    reads perfectly. The assertion has to be that the field is ABSENT.
    """
    out = rts._sidecar_window(_derived(**{field: value}))
    assert "True" not in out
    assert "-5" not in out and "-2" not in out and "lots" not in out
    assert "2026-08-07→2026-09-05" in out  # the window itself still renders
    if field == "accounts":
        assert "account" not in out, f"a bogus account count was rendered anyway: {out}"
    else:
        assert "token" not in out, f"a bogus token count was rendered anyway: {out}"


def test_a_float_token_count_from_json_still_renders():
    """JSON numbers arrive as floats; dropping the denominator for that alone would lose real data."""
    out = rts._sidecar_window(_derived(tokens=1.5e11))
    assert "150.0B tokens" in out
