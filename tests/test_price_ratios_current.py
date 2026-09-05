"""The ① ranking axis must price the CURRENT models, and the family table's blind spot must stay visible.

`scripts/kilo-benchmarks/claude_price_ratios.json` feeds `derive_cost.api_equiv`, which is the axis
`rank_task_subagents.py` sorts models on — so a stale price silently re-ranks the pool.

Grounded 2026-09-04 against https://platform.claude.com/docs/en/about-claude/models/overview.md:
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
    comment = r["_comment"]
    assert "fable-5-1" in comment.lower() or "fable 5.1" in comment.lower(), (
        "the Fable 5.1 cache-read exception is undocumented; a reader will assume 0.1x applies to it"
    )
    assert "0.25" in comment, "the real Fable 5.1 cache-read rate ($0.25/MTok) is not stated"


def test_the_family_default_still_prices_fable_5() -> None:
    """The override must not become the family rate: `claude-fable-5` bills cache reads at 10%.

    In the live 30-day window this box ran 76.3% of its fable-tier tokens on `claude-fable-5` and
    23.7% on `claude-fable-5-1`. Moving 0.025 onto the family key would trade a 4x overprice on the
    smaller share for a 4x UNDERprice on the larger one.
    """
    r = _ratios()
    assert "claude-fable-5" not in r.get("_model_cache", {}), (
        "claude-fable-5 must fall through to the 0.1 default, not carry an override"
    )
