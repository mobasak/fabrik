"""The ① ranking axis must price the CURRENT models, and the family table's blind spot must stay visible.

`scripts/kilo-benchmarks/claude_price_ratios.json` feeds `derive_cost.api_equiv`, which is the axis
`rank_task_subagents.py` sorts models on — so a stale price silently re-ranks the pool.

Grounded 2026-09-05 (re-verified live) against https://platform.claude.com/docs/en/about-claude/models/overview.md:
  "Claude Sonnet 5 … $2 / input MTok, $10 / output MTok"  (no expiring introductory rate is noted)
  "prompt cache reads cost 10% of the base input price (2.5% on Claude Fable 5.1 and Claude Mythos 5.1)"

The file carried $3/$15 for sonnet behind a comment saying the $2/$10 intro ran "through 2026-08-31";
that rate is current with no expiry, so the comment's instruction to edit was overdue by four days.
Reported by fleet in mail 01M1PTQ5QXJR0AAGW3YYG3HHWE and verified against the live page before this
test was written.
"""

from __future__ import annotations

import json
import pathlib

RATIOS = (
    pathlib.Path(__file__).resolve().parents[1]
    / "scripts"
    / "kilo-benchmarks"
    / "claude_price_ratios.json"
)


def _ratios() -> dict:
    return json.loads(RATIOS.read_text())


def test_sonnet_is_priced_at_the_current_rate() -> None:
    """Sonnet 5 is $2/$10, not the superseded $3/$15 that Sonnet 4.6 carried."""
    sonnet = _ratios()["claude-code/sonnet"]
    assert sonnet["in"] == 2.0, f"sonnet input is {sonnet['in']}, live list price is 2.0"
    assert sonnet["out"] == 10.0, f"sonnet output is {sonnet['out']}, live list price is 10.0"


def test_every_family_price_matches_the_live_list() -> None:
    """The other three families, so a future edit cannot quietly move one."""
    r = _ratios()
    assert (r["claude-code/opus"]["in"], r["claude-code/opus"]["out"]) == (5.0, 25.0)
    assert (r["claude-code/haiku"]["in"], r["claude-code/haiku"]["out"]) == (1.0, 5.0)
    assert (r["claude-code/fable"]["in"], r["claude-code/fable"]["out"]) == (10.0, 50.0)


def test_the_fable_5_1_cache_read_exception_is_expressed_not_merely_documented() -> None:
    """The family table cannot hold two cache rates, so the exception is keyed on the MODEL id.

    `_cache.read` is the DEFAULT multiplier (0.1 × base input) and stays correct for Fable 5 — $1.00 on
    a $10 input. Fable 5.1's real rate is 2.5% ($0.25), and the `claude-code/fable` family key covers
    BOTH models, so the rate cannot live on the family. `_model_cache` holds the per-model-id override
    that `api_equiv` prefers; this test fails if the override is dropped and the blind spot returns.
    """
    r = _ratios()
    assert r["_cache"]["read"] == 0.1, "the DEFAULT multiplier changed — re-check every family"
    override = r["_model_cache"]["claude-fable-5-1"]
    assert override["read"] == 0.025, (
        f"claude-fable-5-1 cache-read multiplier is {override['read']}, the live rate is 2.5% of base input"
    )
    # No assertion on the `_comment` prose: it was the only defence while the rate was
    # undocumentable, and it is wallpaper now the override is executable and asserted above.
    # `"0.25" in comment` passes on "the 0.25 figure was withdrawn" and taxes every honest reword.


def test_no_override_sits_on_a_family_key() -> None:
    """The 0.025 must never move onto a FAMILY key — that is the 4x underprice, not the fix.

    In the live 30-day window this box ran 76.3% of its fable-tier tokens on `claude-fable-5` and
    23.7% on `claude-fable-5-1`, so a family-level 0.025 would trade a 4x overprice on the smaller
    share for a 4x UNDERprice on the larger one. The previous version of this test asserted only that
    the string "claude-fable-5" was absent from `_model_cache` — which permitted exactly the
    configuration it forbids in prose (`_model_cache["claude-code/fable"]`) and forbade a harmless one.
    """
    overrides = _ratios().get("_model_cache", {})
    family_keys = [
        k
        for k in overrides
        if k.startswith("claude-code/") or k in {"fable", "opus", "sonnet", "haiku"}
    ]
    assert not family_keys, (
        f"cache overrides on family keys mis-price the whole tier: {family_keys}"
    )


def test_the_longest_prefix_wins_and_only_at_a_segment_boundary() -> None:
    """The tie-break and the boundary rule, neither of which the live one-key file can exercise.

    `_model_cache` holds exactly one key today, so the longest-prefix comparison never fires against
    real data: inverting it to SHORTEST left the whole suite green. And a bare prefix would let a
    future `claude-fable-5-10` inherit Fable 5.1's 2.5% — a 4x underprice, the mirror of the bug the
    override closed. Both are asserted here against a synthetic two-key table.
    """
    import importlib.util
    import pathlib as _pl

    spec = importlib.util.spec_from_file_location(
        "cpc_prefix", _pl.Path(__file__).resolve().parents[1] / "scripts" / "claude_p_cost.py"
    )
    cpc = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cpc)

    ratios = {
        "_cache": {"read": 0.1, "write_5m": 1.25},
        "_model_cache": {"claude-fable-5": {"read": 0.5}, "claude-fable-5-1": {"read": 0.025}},
    }
    # longest wins — under a shortest-first tie-break this would be 0.5
    assert cpc._cache_multipliers(ratios, "claude-fable-5-1")["read"] == 0.025
    assert cpc._cache_multipliers(ratios, "claude-fable-5-1-20260815")["read"] == 0.025
    # the shorter key still applies to its own model
    assert cpc._cache_multipliers(ratios, "claude-fable-5")["read"] == 0.5
    # SEGMENT boundary: a different model number is not a suffix of this one
    assert cpc._cache_multipliers(ratios, "claude-fable-5-10")["read"] == 0.5
    assert cpc._cache_multipliers(ratios, "claude-fable-5-15")["read"] == 0.5


def test_both_producers_price_a_cache_read_identically() -> None:
    """`derive_cost._cache_for` claims in its docstring to mirror `claude_p_cost._cache_multipliers`.

    It did not: it omitted the key normalisation, so `claude-fable-5.1` and
    `anthropic/claude-fable-5-1` resolved 4x apart between the two modules. A docstring cannot hold
    that invariant — this does.
    """
    import importlib.util
    import pathlib as _pl
    import sys as _sys

    root = _pl.Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location(
        "cpc_mirror", root / "scripts" / "claude_p_cost.py"
    )
    cpc = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cpc)
    _sys.path.insert(0, str(root / "scripts" / "kilo-benchmarks"))
    import derive_cost as dc

    r = _ratios()
    for form in (
        "claude-fable-5-1",
        "claude-fable-5.1",
        "anthropic/claude-fable-5-1",
        "claude-fable-5-1[1m]",
        "claude-fable-5-1-20260815",
        "claude-fable-5",
        "claude-fable-5-10",
        "claude-opus-5",
        "  CLAUDE-Fable-5-1  ",
    ):
        assert cpc._cache_multipliers(r, form) == dc._cache_for(r, form), (
            f"the two producers disagree on {form!r} — the ranking axis and the per-call meter "
            f"would price the same tokens differently"
        )


def test_both_producers_use_the_same_window_length() -> None:
    """The ~1.3% money bug lived in TWO producers; fixing one left the other divisible by 31.

    `claude_p_cost._live_usage_window` and `derive_cost.amortized_rate` / `amortized_by_family` each
    divide ONE month of subscription spend by the tokens in their own window. A 31-date span against a
    30-date spend understates the rate — and when the two disagree, the sidecar ships a 30-date
    `amortized_per_mtok` beside a 31-date `amortized_per_mtok_by_family` under one window pair that
    describes only the former. Asserted by feeding both an identical fixture with a day placed exactly
    one past the cutoff.
    """
    import datetime
    import importlib.util
    import json as _json
    import pathlib as _pl
    import sys as _sys
    import tempfile

    root = _pl.Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location(
        "cpc_window", root / "scripts" / "claude_p_cost.py"
    )
    cpc = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cpc)
    _sys.path.insert(0, str(root / "scripts" / "kilo-benchmarks"))
    import derive_cost as dc

    assert cpc._MONTHLY_DAYS == dc._MONTHLY_DAYS

    def day(offset: int) -> str:
        return (datetime.date.today() - datetime.timedelta(days=offset)).isoformat()

    inside, outside = 1_000, 999_999_999
    history = {
        "days": {
            day(0): {
                "byModel": {
                    "claude-opus-5": {
                        "input": inside,
                        "output": 0,
                        "cacheRead": 0,
                        "cacheCreation": 0,
                    }
                }
            },
            day(cpc._MONTHLY_DAYS - 1): {
                "byModel": {
                    "claude-opus-5": {
                        "input": inside,
                        "output": 0,
                        "cacheRead": 0,
                        "cacheCreation": 0,
                    }
                }
            },
            day(cpc._MONTHLY_DAYS): {
                "byModel": {
                    "claude-opus-5": {
                        "input": outside,
                        "output": 0,
                        "cacheRead": 0,
                        "cacheCreation": 0,
                    }
                }
            },
        }
    }
    with tempfile.TemporaryDirectory() as td:
        tdp = _pl.Path(td)
        hist = tdp / "usage-history.json"
        hist.write_text(_json.dumps(history), encoding="utf-8")
        accounts = tdp / "accounts"
        accounts.mkdir()
        (accounts / "a").mkdir()

        approx = __import__("pytest").approx
        expected_tokens = 2 * inside

        # (a) derive_cost.amortized_rate — the rate is spend / tokens, so an over-wide window collapses it
        rate = dc.amortized_rate(usage_history_path=hist, accounts_dir=accounts)
        expected = dc._SUBSCRIPTION_USD_PER_ACCOUNT / expected_tokens
        assert rate == approx(expected, rel=1e-9), (
            f"amortized_rate counted {dc._SUBSCRIPTION_USD_PER_ACCOUNT / rate:.0f} tokens, expected "
            f"{expected_tokens} — its window spans a different number of dates than claude_p_cost's"
        )

        # (b) derive_cost.amortized_by_family — the SECOND site, and the one that produces the sidecar's
        # family split. Round 5 changed both lines and graded only (a); reverting THIS one to the 31-date
        # window left 43 of 43 tests green, which is how the same bug survived a round in the first place.
        fam = dc.amortized_by_family(usage_history_path=hist, accounts_dir=accounts)
        assert set(fam) == {"opus"}, fam
        # value/raw for a single priced family collapses to the effective rate x discount, and the
        # discount's denominator is the window's api-equiv value — an extra day changes it measurably.
        wide_history = dict(history["days"])
        narrow = {"days": {k: v for k, v in wide_history.items() if k != day(cpc._MONTHLY_DAYS)}}
        hist_narrow = tdp / "narrow.json"
        hist_narrow.write_text(_json.dumps(narrow), encoding="utf-8")
        fam_narrow = dc.amortized_by_family(usage_history_path=hist_narrow, accounts_dir=accounts)
        assert fam["opus"] == approx(fam_narrow["opus"], rel=1e-9), (
            "amortized_by_family counted the out-of-window day: dropping it changed the result, so its "
            "cutoff spans a different number of dates than claude_p_cost's"
        )

        # (c) claude_p_cost's own window, so the test's name is true of BOTH producers
        import os as _os

        monkey_out = tdp / "sidecar.json"
        _os.environ["CLAUDE_P_COST"] = str(monkey_out)
        try:
            cpc._USAGE_HISTORY, cpc._MANAGER_ACCOUNTS = hist, accounts
            assert cpc._live_usage_window()["tokens"] == expected_tokens
        finally:
            _os.environ.pop("CLAUDE_P_COST", None)
