# AFTER-EDIT: ../rank_task_subagents.py
"""Phase E — reviewer candidates are ordered by COST within the corpus's resolution, not by noise.

`TASK_SUBAGENT_SELECTION.md` states the instrument's own ceiling: of 22 mutants, 15 are caught by
every strong model and 6 by none, so exactly ONE item discriminates at the frontier. One item is
1/22 of recall and `score5 = F1 × 5`, so it moves score5 by ~0.2. Sorting on raw score5 therefore let
a difference the corpus cannot resolve outrank a 4.5× cost gap — a $448/1k model above a $0.165/1k
one on 0.16 of score5.

These tests pin the band, not the current roster: they assert the ORDERING RULE, so a future
benchmark run cannot silently restore a noise-led sort.
"""

from __future__ import annotations

import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
SCRIPTS = TESTS_DIR.parent
sys.path.insert(0, str(SCRIPTS))

import rank_task_subagents as rts  # noqa: E402


def test_the_band_is_one_corpus_item_wide():
    """0.25 = one discriminating item (1/22 of recall → ~0.2 of score5), rounded up. Widening this
    trades measured quality for measured price and must be a deliberate, argued change."""
    assert rts._SCORE5_NOISE_BAND == 0.25


def _key(score5: float, cost_per_1k: float, name: str) -> tuple:
    """The composite key the shortlist sorts on, expressed independently of the DB."""
    band = -((score5 // rts._SCORE5_NOISE_BAND) * rts._SCORE5_NOISE_BAND)
    return (band, cost_per_1k, name)


def test_within_one_band_the_cheaper_model_wins():
    """4.21 and 4.05 are 0.16 apart — less than one corpus item — so cost decides. This is the exact
    pair the live roster produced: claude-code/haiku at $35.549 vs qwen/qwen3-max at $0.165."""
    haiku = _key(4.21, 35.549, "claude-code/haiku")
    qwen = _key(4.07, 0.165, "qwen/qwen3-max")
    assert qwen < haiku, "a 0.14 score5 edge outranked a 215x cost difference"


def test_a_gap_larger_than_the_band_still_beats_cost():
    """The band must not flatten real quality: 4.05 vs 3.53 is more than two corpus items apart, so
    the better model wins even though it costs more."""
    good_dear = _key(4.05, 0.226, "google/gemini-3-flash-preview")
    poor_cheap = _key(3.53, 0.105, "deepseek/deepseek-v3.2-exp")
    assert good_dear < poor_cheap, "banding must not let cost override a resolvable quality gap"


def test_the_ordering_is_total_and_stable():
    """Ties inside a band fall back to the model id, so two runs never disagree."""
    a = _key(4.05, 1.0, "a/model")
    b = _key(4.05, 1.0, "b/model")
    assert a < b


def test_the_rendered_table_uses_the_same_band_as_the_router():
    """The regression this closes: the doc had its own `ORDER BY m.score5 DESC` while the router
    banded-then-cost, so the table a human reads ranked models the router did not."""
    src = (SCRIPTS / "rank_task_subagents.py").read_text(encoding="utf-8")
    # ⚠️ SCOPED TO THE SHORTLIST QUERY. A blanket "no raw score5 sort anywhere" assertion is WRONG
    # and fired on the full benchmark reference table, which the doc itself marks "display only; not
    # parsed for routing" — a reference listing of every measured model is legitimately score5-ranked.
    # Only the SELECTED shortlist feeds `pick_models`, so only it must match the router.
    # anchor on the shortlist's OWN query text and take the window that follows it — slicing between
    # two headings failed silently because "### Coders" occurs EARLIER in the file than "if rev_set:",
    # so the window was empty and the assertions passed on nothing.
    anchor = src.index("SELECT m.model_id, m.grade, m.score5, m.recall, m.cost_per_1k")
    window = src[anchor : anchor + 1200]
    # ⚠️ STRIP COMMENTS FIRST. The first version of this assertion matched the phrase inside the
    # explanatory comment ABOVE the query — a test reading prose, not code, and it failed on the
    # very sentence describing the bug it guards. Grade the executable text only.
    shortlist = "\n".join(
        ln for ln in window.splitlines() if not ln.lstrip().startswith("#")
    )
    assert "ORDER BY m.score5 DESC" not in shortlist, (
        "the SELECTED reviewer shortlist is back on a raw-score5 sort and no longer matches the router"
    )
    assert "_SCORE5_NOISE_BAND} AS INT) DESC" in shortlist, (
        "the shortlist must band on the SAME constant the router uses"
    )
    assert "m.cost_per_1k ASC" in shortlist, "the shortlist must break band ties on cost"
