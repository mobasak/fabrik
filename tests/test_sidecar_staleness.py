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
import json
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


def _at(hours_old: float, monkeypatch) -> str:
    """Render with the clock FROZEN, so the boundary is exact rather than wall-clock-fuzzy.

    Probing `_stamp(1 day)` against a live `now()` measures 24h-plus-however-long-the-test-took, which
    silently lands on the far side of the boundary and makes `>` indistinguishable from `>=`.
    """
    frozen = datetime.datetime(2026, 9, 5, 12, 0, 0, tzinfo=datetime.UTC)
    built = frozen - datetime.timedelta(hours=hours_old)

    class _FrozenDateTime(datetime.datetime):
        @classmethod
        def now(cls, tz=None):
            # AWARE even when tz is None: the code calls `.now().astimezone()`, and `.astimezone()`
            # on a NAIVE value re-interprets it as local, shifting the instant by the UTC offset —
            # which silently moved the boundary by 3 hours on this box and made the test lie.
            return frozen.astimezone(tz) if tz else frozen.astimezone()

    _timedelta, _timezone = datetime.timedelta, datetime.timezone

    class _FrozenModule:
        datetime = _FrozenDateTime
        timedelta = _timedelta
        timezone = _timezone

    monkeypatch.setitem(sys.modules, "datetime", _FrozenModule)
    try:
        return rts._sidecar_window(_derived(built_at=built.isoformat(timespec="seconds")))
    finally:
        monkeypatch.undo()


def test_the_staleness_boundary_is_exactly_the_rebuild_cadence(monkeypatch):
    """The comparison is STRICTLY greater: at exactly the cadence the rebuild is due, not overdue.

    The previous version of this test probed ±1 hour and never the boundary itself, so `>` vs `>=` —
    the canonical off-by-one on this line — survived as a silent mutation while the docstring claimed
    "off-by-one here is the whole signal". It does now, because the clock is frozen.
    """
    h = rts._SIDECAR_STALE_AFTER_HOURS
    assert "STALE" not in _at(h - 0.01, monkeypatch), "just inside the cadence must be quiet"
    assert "STALE" not in _at(h, monkeypatch), "AT the cadence the rebuild is due, not yet overdue"
    assert "STALE" in _at(h + 0.01, monkeypatch), "just past the cadence must be loud"


def test_small_counts_and_singulars_render_correctly():
    """The small-count branch and both pluralisation ternaries had ZERO coverage.

    Every fixture used 106.9B tokens and 4 accounts, so `tokens < 5e7`, `tokens == 1` and
    `accounts == 1` were never exercised — three independent mutations survived the whole suite.
    """
    assert "1 token over 1 account)" in rts._sidecar_window(_derived(tokens=1, accounts=1))
    assert "2 tokens over 2 accounts)" in rts._sidecar_window(_derived(tokens=2, accounts=2))
    assert "49,999,999 tokens" in rts._sidecar_window(_derived(tokens=49_999_999))  # just under 5e7
    assert "0.1B tokens" in rts._sidecar_window(_derived(tokens=50_000_000))  # at the switch


@pytest.mark.parametrize("value", [float("inf"), float("-inf"), float("nan")])
def test_a_non_finite_count_does_not_crash_the_renderer(value):
    """`int(nan)` raises ValueError and `int(inf)` raises OverflowError — both inside a doc renderer."""
    out = rts._sidecar_window(_derived(tokens=value))
    assert "2026-08-07→2026-09-05" in out
    assert "inf" not in out and "nan" not in out


def test_a_present_but_unreadable_built_at_is_not_called_absent():
    """ "no built_at" is false when the key is there — it is there and the reader cannot read it."""
    for value in (1757000000, {"a": 1}, [1, 2]):
        out = rts._sidecar_window(_derived(built_at=value))
        assert "not a timestamp" in out
        assert "carries no date at all" not in out


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
    # NOT `"3.0 days" in out`: that is a SUBSTRING of "-3.0 days", so flipping the sign in the
    # f-string rendered "in the FUTURE by -3.0 days" and passed. Third instance in this file of
    # "the assertion is adjacent to the behaviour" — anchor on the space that precedes the number.
    assert "by 3.0 days" in out
    assert "-3.0" not in out
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


# ── graders the Phase-C author-blind mutation pass proved were missing ────────────────────────
#
# 23 mutations, 9 survivors. Every one below reds a mutation that previously passed the whole suite.


def test_the_staleness_threshold_is_pinned_to_the_literal_cadence():
    """`_SIDECAR_STALE_AFTER_HOURS = 48 | 12 | 1` each survived the entire suite.

    Every existing test read the constant back (`h = rts._SIDECAR_STALE_AFTER_HOURS`, then probed
    `h ± 0.01`) so the assertions moved WITH the mutation — a relative test cannot pin an absolute.
    The value is not arbitrary: it is the cron cadence `0 6 * * *` that Phase C wired, so it is
    pinned here against a literal, and a deliberate change to the cadence must change this line too.
    """
    assert rts._SIDECAR_STALE_AFTER_HOURS == 24


def test_the_anchor_branch_carries_the_age_marker_too(tmp_path):
    """Dropping `{age}` from the ANCHOR return survived, though the DERIVED return was guarded.

    This is the highest-traffic case there is: a PRE-Phase-A sidecar has `built_at` and no window
    keys, so a months-old rate lands on exactly this branch — the originating incident. Every anchor
    test used a FRESH stamp, so the branch that most needs the STALE marker was the one never
    checked with an old one.
    """
    out = rts._sidecar_window({"built_at": _stamp(26), "window_start": None, "window_end": None})
    assert "research ANCHOR" in out
    assert "STALE" in out and "26.0 days ago" in out


def test_a_half_populated_window_is_not_reported_as_the_anchor():
    """`and` -> `or` survived. With one bound set, the old code claimed "this is the research
    ANCHOR, not a measured rate" about a sidecar that plainly carries a derived bound."""
    out = rts._sidecar_window(
        {"built_at": _stamp(1 / 24), "window_start": "2026-08-07", "window_end": None}
    )
    assert "research ANCHOR" not in out
    assert "partial window" in out


@pytest.mark.parametrize(
    # ⚠️ `"2026-08-07\rX"` is NOT redundant with the `\r\n` case: that one is killed by the `\n`
    # clause alone, so a lone interior CR is the only input the `"\r"` clause actually owns — and
    # deleting that clause survived the suite until this case existed.
    "bound",
    [
        ["2026-08-07"],
        {"a": 1},
        20260807,
        "2026-08-07\nHEADING",
        "2026-08-07\r\n#",
        "2026-08-07\rX",
        "  ",
    ],
)
def test_a_window_bound_that_is_not_a_single_line_string_is_refused(bound):
    """The bounds took raw `str()` while the denominators were rigorously validated.

    The newline case is the real break, not a curiosity: this string is interpolated into a
    single-line italic markdown block, so an embedded newline splits the emphasis run and corrupts
    TASK_SUBAGENT_SELECTION.md — the document `pick_models` parses.
    """
    out = rts._sidecar_window(
        {"built_at": _stamp(1 / 24), "window_start": bound, "window_end": "2026-09-05"}
    )
    assert "unreadable" in out or "partial window" in out
    assert "\n" not in out and "\r" not in out
    assert "HEADING" not in out


def test_a_fractional_token_count_is_still_refused():
    """`v == int(v)` dropped from `_count` survived: `tokens=1.5` then rendered ", 1 token" —
    verbatim the "fabricated denominator that reads perfectly" an earlier round named."""
    out = rts._sidecar_window(
        {
            "built_at": _stamp(1 / 24),
            "window_start": "2026-08-07",
            "window_end": "2026-09-05",
            "tokens": 1.5,
        }
    )
    assert "token" not in out


def test_a_real_account_count_survives_an_unusable_token_count():
    """Nesting `if accounts:` under `if tokens:` silently discarded a VALID denominator whenever the
    token count was null, zero or nonsense. The test that should have caught it only asserted that
    "token" was absent, and never noticed `accounts` had gone with it."""
    for bad in (None, 0, "lots", float("nan")):
        out = rts._sidecar_window(
            {
                "built_at": _stamp(1 / 24),
                "window_start": "2026-08-07",
                "window_end": "2026-09-05",
                "tokens": bad,
                "accounts": 4,
            }
        )
        assert "4 accounts" in out, f"accounts vanished with tokens={bad!r}"
        assert "token" not in out.replace("tokens", "")


def test_an_unrenderable_token_count_is_refused_at_the_validator_not_caught_downstream(
    tmp_path, monkeypatch
):
    """The 401-digit `tokens` that started this: JSON permits arbitrary-precision integers, `_count`
    accepted them exactly, and `tokens / 1e9` raised OverflowError out of a doc generator.

    The FIRST fix wrapped the call site. That is a net, not a root: `_count` is the denominator
    validator and a number it cannot render is not a valid denominator. Refused there, the reader
    still gets its window and its STALE marker — it simply omits the count it cannot state.
    """
    out = rts._sidecar_window(
        _derived(built_at=_stamp(26), tokens=int("1" + "0" * 400), accounts=4)
    )
    assert "token" not in out.replace("tokens", "")  # the count is omitted, not fabricated
    assert "STALE" in out and "26.0 days ago" in out  # and the freshness signal survives
    assert "4 accounts" in out  # as does the denominator that IS renderable


def test_the_context_line_can_never_kill_the_document_it_annotates(tmp_path, monkeypatch):
    """THE HIGH FINDING, kept as a net even though the root is now closed.

    `_sidecar_window` was called one line BELOW the fail-soft `except`, so anything it raised escaped
    `_claude_p_preamble` — and the ranking regen runs as `_step … || echo (non-fatal)`, so the raise
    aborted the whole doc and left YESTERDAY'S copy standing. The specific payload that did it is now
    refused at the validator above, so this test forces the general case instead: whatever
    `_sidecar_window` does, the preamble still returns.
    """
    sidecar = tmp_path / "claude_p_cost.json"
    sidecar.write_text(
        json.dumps({"amortized_per_mtok": 0.0074, "quota_draw_pct": 0.0, "built_at": _stamp(0)}),
        encoding="utf-8",
    )
    monkeypatch.setattr(rts, "__file__", str(tmp_path / "rank_task_subagents.py"))

    def _explode(_d):
        raise RuntimeError("a future edit raises something nobody enumerated")

    monkeypatch.setattr(rts, "_sidecar_window", _explode)
    lines = rts._claude_p_preamble()  # must not raise
    assert lines, "the preamble should still render — only the window clause degrades"
    assert "window unreadable" in "\n".join(lines)
