"""Behavior Contract for pick_models(require_reachable=True) — plan-1 Phase B."""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from libs.subagents.select import _reachable_set_from_doc, pick_models  # noqa: E402


def _write_doc(tmp_path: Path, reachable_ids: list[str]) -> Path:
    """Write a minimal SELECTION.md with the reachable-set comment + one `### review`
    section listing all reachable_ids plus a bonus 'unreachable/x' at position 2."""
    p = tmp_path / "SELECTION.md"
    reach_line = ", ".join(reachable_ids) if reachable_ids else ""
    body = f"""# Task subagent selection

Last refresh: 2026-07-09
<!-- reachable: {len(reachable_ids)}/{len(reachable_ids) + 1} -->
<!-- reachable-set: {reach_line} -->

## Ranked table

### review

| # | Model | Provider | n |
|---:|---|:-:|---:|
| 1 | `{reachable_ids[0] if reachable_ids else 'noop/x'}` | X | 10 |
| 2 | `unreachable/x` | X | 8 |
"""
    if len(reachable_ids) >= 2:
        body += (
            f"| 3 | `{reachable_ids[1]}` | X | 5 |\n"
        )
    p.write_text(body, encoding="utf-8")
    return p


def test_B1_default_filters_unreachable(tmp_path, monkeypatch):
    """B1: default require_reachable=True → unreachable/x is filtered out."""
    doc = _write_doc(tmp_path, ["minimax/minimax-m3", "deepseek/deepseek-v3.2"])
    monkeypatch.setenv("SUBAGENT_SELECTION_DOC", str(doc))
    monkeypatch.delenv("FABRIK_SUBAGENT_REQUIRE_REACHABLE", raising=False)

    picks = pick_models("review", n=3)
    assert "minimax/minimax-m3" in picks
    assert "deepseek/deepseek-v3.2" in picks
    assert "unreachable/x" not in picks


def test_B2_opt_out_returns_everything(tmp_path, monkeypatch):
    """B2: require_reachable=False → unreachable/x is IN the returned list.

    `allow_above_cap=True` isolates this test from the ≤$1.5 fleet cap which
    drops unpriced models (`unreachable/x` has no known price, so the cap
    would drop it too — that's a separate concern from reachability).
    """
    doc = _write_doc(tmp_path, ["minimax/minimax-m3", "deepseek/deepseek-v3.2"])
    monkeypatch.setenv("SUBAGENT_SELECTION_DOC", str(doc))
    monkeypatch.delenv("FABRIK_SUBAGENT_REQUIRE_REACHABLE", raising=False)

    picks = pick_models("review", n=3, require_reachable=False, allow_above_cap=True)
    assert "unreachable/x" in picks


def test_B3_env_override_zero_disables_filter(tmp_path, monkeypatch):
    """B3: FABRIK_SUBAGENT_REQUIRE_REACHABLE=0 matches opt-out behavior.

    (Same rationale as B2 for the price-cap isolation.)
    """
    doc = _write_doc(tmp_path, ["minimax/minimax-m3"])
    monkeypatch.setenv("SUBAGENT_SELECTION_DOC", str(doc))
    monkeypatch.setenv("FABRIK_SUBAGENT_REQUIRE_REACHABLE", "0")

    picks = pick_models("review", n=3, allow_above_cap=True)
    assert "unreachable/x" in picks


def test_B4_kwarg_wins_over_env(tmp_path, monkeypatch):
    """B4: explicit require_reachable=True overrides
    FABRIK_SUBAGENT_REQUIRE_REACHABLE=0 (kwarg-first precedence, plan B.4).

    Uses `allow_above_cap=True` to isolate the reachability filter from the
    ≤$1.5 price cap that would otherwise drop `unreachable/x` for a
    different reason (unknown price). Without this, the assertion passes
    trivially and doesn't prove the kwarg-precedence fix.
    """
    doc = _write_doc(tmp_path, ["minimax/minimax-m3"])
    monkeypatch.setenv("SUBAGENT_SELECTION_DOC", str(doc))
    monkeypatch.setenv("FABRIK_SUBAGENT_REQUIRE_REACHABLE", "0")

    # kwarg=True should filter EVEN with env=0.
    picks = pick_models("review", n=3, require_reachable=True, allow_above_cap=True)
    assert "unreachable/x" not in picks, (
        "kwarg=True must override env=0 (plan B.4 kwarg-first precedence)"
    )
    assert "minimax/minimax-m3" in picks


def test_reachable_set_parse_missing_doc_returns_none(tmp_path):
    """Doc without the comment → None (no filter available)."""
    doc = tmp_path / "no-comment.md"
    doc.write_text("# empty\n\n### review\n\n| # | Model | n |\n|--|--|--|\n| 1 | `x/y` | 3 |\n")
    assert _reachable_set_from_doc(str(doc)) is None


def test_reachable_set_parse_empty_comment_returns_none(tmp_path):
    """`<!-- reachable-set: -->` (empty) → None (treated as no info)."""
    doc = tmp_path / "empty-set.md"
    doc.write_text("<!-- reachable-set:  -->\n")
    assert _reachable_set_from_doc(str(doc)) is None
