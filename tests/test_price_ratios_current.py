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

RATIOS = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "kilo-benchmarks" / "claude_price_ratios.json"


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


def test_the_fable_cache_read_blind_spot_is_documented() -> None:
    """The family table CANNOT express Fable 5.1's cache read, so it must SAY so.

    `_cache.read` is one global multiplier (0.1 × base input). That is correct for Fable 5 — $1.00 on a
    $10 input — and 4x too high for Fable 5.1, whose real rate is $0.25 (2.5%). A family key cannot hold
    both, so until the shape changes the only defence is that the next reader is told. This test fails if
    the warning is dropped.
    """
    r = _ratios()
    assert r["_cache"]["read"] == 0.1, "the global multiplier changed — re-check every family"
    comment = r["_comment"]
    assert "fable-5-1" in comment.lower() or "fable 5.1" in comment.lower(), (
        "the Fable 5.1 cache-read exception is undocumented; a reader will assume 0.1x applies to it"
    )
    assert "0.25" in comment, "the real Fable 5.1 cache-read rate ($0.25/MTok) is not stated"
