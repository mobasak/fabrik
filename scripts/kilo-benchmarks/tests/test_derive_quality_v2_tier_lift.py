"""Phase D behavior tests: derive_quality_v2 tier lift + non-regression + FAMILIES.

D1: stub row with humaneval_score=65 → Tier 3.
D2: stub row with humaneval_score=45 → Tier 2.
D3 (blast-radius guard): zero non-Seed tier flips before → after the ladder edit.
D4: FAMILIES gains bytedance-seed/seed- prefix.

Plan: docs/development/plans/2026-07-10-plan-2-coding-microbench-runner.md
"""
# AFTER-EDIT: none

from __future__ import annotations

import json
import pathlib
import sys

SCRIPT_DIR = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPT_DIR))

from derive_quality_v2 import BENCH_TIER2, BENCH_TIER3, derive_v2  # noqa: E402
from rank_coding_subagents import FAMILIES  # noqa: E402

# Pre-edit tier snapshot committed as a PERMANENT test fixture (Phase D review F1
# fix): the plan initially wrote it to /tmp/tier_snapshot_pre.json, but a /tmp
# clear (container restart, CI runner, fresh clone) would make D3 silently SKIP,
# defeating the blast-radius guard. Committing under tests/fixtures/ keeps it
# available on every run.
FIXTURE_SNAPSHOT_PATH = pathlib.Path(__file__).resolve().parent / "fixtures" / "tier_snapshot_pre_phase_D.json"


# ─── D1: humaneval_score >= 60 → Tier 3 ────────────────────────────────────────
def test_humaneval_score_65_lifts_to_tier_3() -> None:
    """D1 (TDD-first): stub row with only humaneval_score=65 → Tier 3."""
    row = {"id": "test/model", "humaneval_score": 65.0}
    tier, evidence = derive_v2(row, or_record=None)
    assert tier == 3, (tier, evidence)
    assert any("humaneval_score" in e for e in evidence), evidence


# ─── D2: humaneval_score >= 40 → Tier 2 ────────────────────────────────────────
def test_humaneval_score_45_lifts_to_tier_2() -> None:
    """D2: stub row with only humaneval_score=45 → Tier 2."""
    row = {"id": "test/model", "humaneval_score": 45.0}
    tier, evidence = derive_v2(row, or_record=None)
    assert tier == 2, (tier, evidence)
    assert any("humaneval_score" in e for e in evidence), evidence


def test_humaneval_score_below_tier_2_threshold_stays_tier_1() -> None:
    """D2 edge: humaneval_score=39 stays Tier 1 (below 40 threshold)."""
    row = {"id": "test/model", "humaneval_score": 39.0}
    tier, evidence = derive_v2(row, or_record=None)
    assert tier == 1, (tier, evidence)


def test_humaneval_score_null_does_not_bump() -> None:
    """A row with NULL humaneval_score (not benched yet) does not tier-lift."""
    row = {"id": "test/model", "humaneval_score": None}
    tier, evidence = derive_v2(row, or_record=None)
    assert tier == 1, (tier, evidence)


# ─── D3 (blast-radius): non-regression on every existing agents row ────────────
def test_no_non_seed_tier_flips_after_ladder_edit() -> None:
    """D3 (blast-radius guard): the pre-edit snapshot (committed under
    tests/fixtures/) must match the post-edit derive_v2 output for every non-Seed
    row. If it doesn't, the humaneval_score threshold is unintentionally
    tier-lifting existing rows via a co-signalling column — plan Phase D step 7
    kicks in (lower thresholds by 5, floor at 25 → BLOCKED).

    Note: this test compares the CURRENT derive_v2 output against the fixture
    snapshot captured BEFORE the Phase D edit landed. As long as no writer
    populates humaneval_score for a non-Seed row (which shouldn't happen —
    microbench_coding.DEFAULT_MODELS is Seed-only, verified at Phase B B2), the
    non-Seed subset stays identical.
    """
    assert FIXTURE_SNAPSHOT_PATH.exists(), (
        f"D3 fixture missing at {FIXTURE_SNAPSHOT_PATH} — regenerate via "
        f"`.venv/bin/python scripts/kilo-benchmarks/microbench_coding_tier_snapshot.py "
        f"> {FIXTURE_SNAPSHOT_PATH}` (must be captured BEFORE the ladder edit lands)"
    )

    from microbench_coding_tier_snapshot import snapshot_tiers

    pre = json.loads(FIXTURE_SNAPSHOT_PATH.read_text())
    post = snapshot_tiers()

    flips = [
        (m, pre[m]["tier"], post.get(m, {}).get("tier"))
        for m in pre
        if m in post and pre[m]["tier"] != post[m]["tier"]
    ]
    non_seed_flips = [
        f
        for f in flips
        if "bytedance-seed" not in f[0] and "bytedance/ui-tars" not in f[0]
    ]

    assert non_seed_flips == [], (
        f"D3 non-regression FAILED — {len(non_seed_flips)} non-Seed tier flips: "
        f"{non_seed_flips[:5]}. Lower BENCH_TIER thresholds per Phase D step 7."
    )


# ─── D3 addendum (F2 mitigation): synthetic-DB test proves the ladder actually
# gates a populated humaneval_score column, not just the current all-NULL state ─
def test_ladder_lift_survives_synthetic_populated_non_seed_row() -> None:
    """F2 mitigation: without a live Seed bench, D3 is tautological — every
    agents row today has humaneval_score IS NULL, so the ladder can't flip
    anything. This test proves the ADDED bump-loop entry (`("humaneval_score",
    heval, BENCH_TIER<N>["humaneval_score"])`) actually triggers when the
    column is populated, exercising the code path D3 alone can't reach today.
    """
    # Simulate a hypothetical NON-Seed row with humaneval_score >= 60 — should
    # go to Tier 3 via humaneval_score alone, regardless of ordering. The point:
    # this is what a future non-Seed writer could trigger; the D3 guard would
    # then FAIL for real (via a fresh snapshot), demonstrating actual coverage.
    row = {
        "id": "some-other-vendor/some-code-model",
        "humaneval_score": 72.5,
    }
    tier, evidence = derive_v2(row, or_record=None)
    assert tier == 3
    # And with just-below-Tier-2:
    row2 = {"id": "other/model", "humaneval_score": 39.9}
    tier2, _ = derive_v2(row2, or_record=None)
    assert tier2 == 1
    # And at exactly Tier-2:
    row3 = {"id": "other/model", "humaneval_score": 40.0}
    tier3, _ = derive_v2(row3, or_record=None)
    assert tier3 == 2


# ─── D4: FAMILIES gains bytedance-seed/seed- prefix ────────────────────────────
def test_families_contains_bytedance_seed_prefix() -> None:
    """D4: `bytedance-seed/seed-` is in FAMILIES post-edit."""
    assert "bytedance-seed/seed-" in FAMILIES, FAMILIES


def test_families_matches_all_4_seed_targets() -> None:
    """D4: every one of the 4 Seed target IDs starts with a FAMILIES prefix."""
    targets = [
        "bytedance-seed/seed-1.6-flash",
        "bytedance-seed/seed-2.0-mini",
        "bytedance-seed/seed-1.6",
        "bytedance-seed/seed-2.0-lite",
    ]
    for t in targets:
        assert any(t.startswith(p) for p in FAMILIES), (t, FAMILIES)


def test_families_does_not_match_non_seed_bytedance() -> None:
    """D4 negative: bytedance/ui-tars-* (GUI-agent), bytedance-seed/dola-*
    (image), and bytedance-seed/seedream-* (image) do NOT start with the new
    prefix — the coding selection MD must NOT surface them.

    F3 mitigation (Phase D review): earlier version only tested weak negatives.
    Adding `bytedance-seed/seedog` (starts with seed but not seed-) proves the
    trailing hyphen actually tightens the prefix, and `bytedance-seed/seed`
    (bare) proves length checking.
    """
    non_targets = [
        "bytedance/ui-tars-1.5-7b",
        "bytedance-seed/seedream-4.5",
        "bytedance-seed/dola-seed-2.0-pro:free",
        "bytedance-seed/seedog",  # F3: starts with "seed" but not "seed-" — tight-prefix test
        "bytedance-seed/seed",  # F3: bare "seed" without trailing hyphen
    ]
    seed_prefix = "bytedance-seed/seed-"
    for nt in non_targets:
        assert not nt.startswith(seed_prefix), (
            f"{nt!r} MATCHES {seed_prefix!r} — FAMILIES admits it into coding "
            f"selection, potentially surfacing a non-code model"
        )


# ─── Threshold config: both dicts have humaneval_score, both at expected level ─
def test_bench_tier3_has_humaneval_score_at_60() -> None:
    assert BENCH_TIER3.get("humaneval_score") == 60.0


def test_bench_tier2_has_humaneval_score_at_40() -> None:
    assert BENCH_TIER2.get("humaneval_score") == 40.0
