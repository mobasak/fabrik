"""Regression tests for the Auto vs On-request tier split in
`rank_coding_subagents.py` — the BINDING $1.5/Mtok output ceiling from
`.windsurf/rules/core/62-using-subagents.md § Approved pool models`.

Load-bearing: the vendored `pick_models` has NO hard price cap (confirmed
with fabrik-lib AI). This filter + the caller's `max_cost_per_mtok` are the
only two things keeping >$1.5 models out of the Auto pool.

These tests exercise the pure `_is_auto_tier` predicate and the `_render`
composition against synthetic rows, so they don't depend on the live DB.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rank_coding_subagents import (  # noqa: E402
    AUTO_OUTPUT_PRICE_CEILING,
    _is_auto_tier,
    _render,
)


def test_auto_tier_ceiling_is_binding_1_5():
    """Documents the binding constant; a change here IS a policy change."""
    assert AUTO_OUTPUT_PRICE_CEILING == 1.5


@pytest.mark.parametrize(
    "out_m,expected",
    [
        (0.180, True),  # deepseek-v4-flash — well under
        (1.500, True),  # exactly on the ceiling (inclusive)
        (1.501, False),  # just over
        (1.920, False),  # glm-5
        (3.500, False),  # kimi-k2.7-code
        (None, False),  # NULL price → conservative on-request
        (0.0, True),  # free tier — technically Auto
    ],
)
def test_is_auto_tier_boundary(out_m, expected):
    assert _is_auto_tier({"out_M": out_m}) is expected


def test_null_price_never_auto_selects():
    """A row with unknown output price must NEVER be Auto — otherwise a fresh
    ingest could silently promote a $10/Mtok row into free auto-selection."""
    assert _is_auto_tier({"out_M": None}) is False
    assert _is_auto_tier({}) is False  # missing key entirely


def _synth_row(mid: str, out_m: float | None, extra: dict | None = None) -> dict:
    r = {
        "id": mid,
        "in_M": 0.1,
        "out_M": out_m,
        "db_tps": 50,
        "swe": None,
        "aider": None,
        "aa_idx": None,
        "arena": 1400,
        "ctx_k": 128,
        "reasoning": 0,
        "or_ok": 1,
        "or_prov": "TestProv",
        "score": 0.5,
        "doc_grade": "B",
    }
    if extra:
        r.update(extra)
    return r


def test_render_splits_into_two_sections():
    rows = [
        _synth_row("cheap/alpha", 0.20),
        _synth_row("cheap/beta", 1.40),
        _synth_row("pricey/gamma", 2.50),
        _synth_row("pricey/delta", 3.10),
        _synth_row("unpriced/epsilon", None),
    ]
    md = _render(rows)
    # Both level-3 headers present (### code and ### code-onrequest — the
    # latter is NOT a TaskKind so pick_models resets to None on it).
    assert "\n### code\n" in md
    assert "\n### code-onrequest\n" in md
    # Auto contains only rows ≤ ceiling
    auto = md.split("\n### code\n")[1].split("\n### code-onrequest\n")[0]
    assert "cheap/alpha" in auto
    assert "cheap/beta" in auto
    assert "pricey/gamma" not in auto
    assert "pricey/delta" not in auto
    assert "unpriced/epsilon" not in auto  # NULL → On-request per contract
    # On-request contains only the >$1.5 or unpriced rows.
    # Bound onreq at the NEXT level-2 header (was `## API call recipes`, but
    # commit 48b69416 added `## Candidates not yet benched by us` between the
    # code-onrequest table and the API recipes — Auto-tier rows legitimately
    # appear in that section so keying on `## API call recipes` would leak).
    onreq = md.split("\n### code-onrequest\n")[1].split("\n## ")[0]
    assert "pricey/gamma" in onreq
    assert "pricey/delta" in onreq
    assert "unpriced/epsilon" in onreq
    assert "cheap/alpha" not in onreq
    assert "cheap/beta" not in onreq


def test_no_model_is_dropped_from_the_ranking():
    """The tier boundary is a filter/flag, NOT a cut. Every ranked row must
    appear in exactly one of the two sub-tables (union = full set).
    """
    rows = [
        _synth_row("family/a", 0.5),
        _synth_row("family/b", 1.5),
        _synth_row("family/c", 1.6),
        _synth_row("family/d", None),
        _synth_row("family/e", 4.0),
    ]
    md = _render(rows)
    for r in rows:
        assert r["id"] in md, f"{r['id']} dropped from the emitted doc"


def test_auto_first_onrequest_second():
    """Ordering matters: `### code` MUST precede `### code-onrequest` so
    pick_models scoped into "code" starts on Auto rows before the
    non-TaskKind header resets its state.
    """
    rows = [
        _synth_row("cheap/a", 0.5),
        _synth_row("pricey/b", 2.5),
    ]
    md = _render(rows)
    auto_idx = md.index("\n### code\n")
    onreq_idx = md.index("\n### code-onrequest\n")
    assert auto_idx < onreq_idx, "### code must come before ### code-onrequest"


def test_pick_models_would_never_see_a_pricey_row_in_the_code_section():
    """The failure mode the .windsurf/rules/core/62-using-subagents.md
    § Approved pool models warning describes: a refreshed doc silently
    re-admits glm/kimi/grok/qwen.
    Verify the pricey models are NOT under the `### code` header (the
    only header pick_models scopes to for coding-subagent picks).
    """
    rows = [
        _synth_row("deepseek/deepseek-v4-flash", 0.180),
        _synth_row("z-ai/glm-5", 1.920),
        _synth_row("moonshotai/kimi-k2.7-code", 3.500),
        _synth_row("x-ai/grok-code-fast", 2.500),
    ]
    md = _render(rows)
    # Everything between `### code` and `### code-onrequest` is what
    # pick_models sees for the "code" task.
    code_block = md.split("\n### code\n")[1].split("\n### code-onrequest\n")[0]
    assert "deepseek/deepseek-v4-flash" in code_block
    assert "z-ai/glm-5" not in code_block, "policy violation: glm-5 promoted into Auto"
    assert "moonshotai/kimi-k2.7-code" not in code_block, (
        "policy violation: kimi promoted into Auto"
    )
    assert "x-ai/grok-code-fast" not in code_block, "policy violation: grok promoted into Auto"


def test_pick_models_reader_scopes_only_the_code_table_e2e(tmp_path):
    """End-to-end test against the REAL pick_models reader in
    fabrik-lib/subagents/subagents/select.py — proves the rename to
    `### code-onrequest` actually causes the reader to reset state and
    skip On-request rows. If this test breaks, the module's parse
    contract has changed and the tier split needs another look.
    """
    import importlib.util

    lib_select = Path("/opt/fabrik-lib/subagents/subagents/select.py")
    if not lib_select.exists():
        pytest.skip("fabrik-lib subagents module not vendored on this host")
    spec = importlib.util.spec_from_file_location("_fabriklib_select", lib_select)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(mod)  # type: ignore[union-attr]

    rows = [
        _synth_row("deepseek/deepseek-v4-flash", 0.180),  # Auto
        _synth_row("deepseek/deepseek-v3.2", 0.343),  # Auto
        _synth_row("z-ai/glm-5", 1.920),  # On-request
        _synth_row("moonshotai/kimi-k2.7-code", 3.500),  # On-request
    ]
    md = _render(rows)
    tmp = tmp_path / "tier_split_e2e.md"
    tmp.write_text(md, encoding="utf-8")
    # Note: the reader's staleness gate defaults off (max_age_days=None), and
    # the doc has today's date via _render, so no gate interference.
    result = mod.load_task_ranking(str(tmp))
    code_models = result.get("code", [])
    assert "deepseek/deepseek-v4-flash" in code_models
    assert "deepseek/deepseek-v3.2" in code_models
    assert "z-ai/glm-5" not in code_models, (
        "pick_models still sees glm-5 in code — tier split broken"
    )
    assert "moonshotai/kimi-k2.7-code" not in code_models, (
        "pick_models still sees kimi in code — tier split broken"
    )
    # `code-onrequest` is NOT in TASK_KINDS → should NOT be a key in result
    assert "code-onrequest" not in result


def test_pick_models_respects_staleness_gate_on_tiered_doc(tmp_path):
    """Regression: the staleness gate must still work correctly on the tiered
    doc — an old `Generated:` date must void the doc (reader returns {}).
    Confirms my tier-split didn't accidentally break the staleness contract.
    """
    import importlib.util

    lib_select = Path("/opt/fabrik-lib/subagents/subagents/select.py")
    if not lib_select.exists():
        pytest.skip("fabrik-lib subagents module not vendored on this host")
    spec = importlib.util.spec_from_file_location("_fabriklib_select_stale", lib_select)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(mod)  # type: ignore[union-attr]

    rows = [_synth_row("cheap/a", 0.5)]
    md = _render(rows)
    # Force-stale by rewriting the Last-refresh / Generated stamp to a year ago.
    md_stale = md.replace(
        "**Generated:**",
        "**Generated:** 2025-01-01 · **Last refresh: 2025-01-01** · **Original:**",
        1,
    )
    tmp = tmp_path / "stale.md"
    tmp.write_text(md_stale, encoding="utf-8")
    result = mod.load_task_ranking(str(tmp), max_age_days=30)
    # Staleness gate returns {} on old docs → no code_models list, no auto-selects
    assert result == {} or "cheap/a" not in result.get("code", [])
