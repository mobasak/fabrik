"""Phase B Behavior Contract — research grader (HotpotQA normalize/EM/F1 + tiebreak).

Covers the four load-bearing behaviors:
  (a) normalize_answer / exact_match_score — article/punct/case invariance, order-sensitivity.
  (b) partial answer → token-F1 strictly inside (0, 1).
  (c) the claude-evaluator tiebreak fires ONLY on near-miss items; an abstained item FALLS BACK
      to its objective F1 (kept, never dropped). The evaluator is INJECTED — no real npx subprocess.
  (d) end-to-end research_grade on a 3-item stub-gens corpus → a measured TaskScore.

All local, $0, no network. The evaluator is a fake with the real .evaluate_sync/EvalResult shape.
"""

import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPT_DIR))

import research_grader as rg  # noqa: E402
from microbench_judged import _Gen  # noqa: E402
from vendor.claude_evaluator import EvalResult  # noqa: E402


# ── fakes ────────────────────────────────────────────────────────────────────────────────────
class FakeEvaluator:
    """Records the ids it was asked to judge; returns a pre-canned EvalResult. No subprocess."""

    def __init__(
        self, scored: dict[str, dict] | None = None, abstained: dict[str, dict] | None = None
    ) -> None:
        self.seen_ids: list[str] = []
        self._scored = scored or {}
        self._abstained = abstained or {}

    def evaluate_sync(self, items: list[dict], extra_prompt: str = "") -> EvalResult:
        self.seen_ids.extend(str(it.get("id", "")) for it in items)
        return EvalResult(scored=dict(self._scored), abstained=dict(self._abstained), failed=[])


def _gen(text: str | None) -> _Gen:
    return _Gen(
        text=text, cost_usd=0.0, latency_s=0.1, out_tokens=5, error=None if text else "empty"
    )


# ── (a) normalize / exact match ────────────────────────────────────────────────────────────────
def test_normalize_strips_articles_punct_case():
    assert rg.normalize_answer("A Test, Case!") == "test case"
    assert rg.normalize_answer("The White House") == "white house"


def test_exact_match_is_case_and_punct_insensitive():
    assert rg.exact_match_score("Barack Obama", "barack obama.") is True
    assert rg.exact_match_score("The White House", "white house") is True


def test_exact_match_is_order_sensitive():
    # EM compares the normalized STRING, so reordered list answers are NOT equal.
    assert rg.exact_match_score("Sasha and Malia", "Malia and Sasha") is False


# ── (b) partial → token-F1 in (0, 1) ───────────────────────────────────────────────────────────
def test_partial_answer_gives_f1_strictly_between_zero_and_one():
    f1 = rg.f1_score("Barack Hussein Obama", "Barack Obama")
    assert 0.0 < f1 < 1.0


def test_no_token_overlap_is_zero_f1():
    assert rg.f1_score("totally unrelated", "postgres-main") == 0.0


def test_full_overlap_is_one_f1():
    assert rg.f1_score("postgres-main 5432", "postgres-main 5432") == 1.0


# ── (c) tiebreak fires only in the near-miss band; abstained falls back to F1 ───────────────────
def _near_miss_corpus() -> list[dict]:
    # gold chosen so the model answer lands in each intended F1 region.
    return [
        {"question": "q0", "gold": "postgres main"},  # EM after normalize
        {
            "question": "q1",
            "gold": "shared postgres host postgres-main container",
        },  # near-miss band
        {"question": "q2", "gold": "shared redis host redis-main service index"},  # near-miss band
        {"question": "q3", "gold": "something totally different here"},  # low F1 (< band)
    ]


def test_tiebreak_only_on_near_miss_and_abstain_excluded():
    corpus = _near_miss_corpus()
    gens = {
        "m": [
            _gen("postgres main"),  # item0 → EM, no tiebreak
            _gen("shared postgres host postgres-main"),  # item1 → near-miss → tiebreak
            _gen("shared redis host redis-main"),  # item2 → near-miss → tiebreak (abstained)
            _gen("apples oranges bananas"),  # item3 → low F1, no tiebreak
        ]
    }
    # Confirm the intended F1 regions so the test asserts the grader's routing, not luck.
    band_lo, band_hi = rg.NEAR_MISS_BAND
    assert rg.exact_match_score(gens["m"][0].text, corpus[0]["gold"]) is True
    assert band_lo <= rg.f1_score(gens["m"][1].text, corpus[1]["gold"]) < band_hi
    assert band_lo <= rg.f1_score(gens["m"][2].text, corpus[2]["gold"]) < band_hi
    assert rg.f1_score(gens["m"][3].text, corpus[3]["gold"]) < band_lo

    ev = FakeEvaluator(
        scored={"m||1": {"id": "m||1", "score": 1.0, "confidence": 5}},
        abstained={"m||2": {"id": "m||2", "confidence": 1}},
    )
    scores = rg.research_grade(gens, corpus, evaluator=ev)
    ts = scores["m"]

    # Only the two near-miss items were escalated — not the EM item nor the low-F1 item.
    assert sorted(ev.seen_ids) == ["m||1", "m||2"]
    # item2 abstained → FALLS BACK to its objective F1 (never dropped, never un-measured): ALL 4 items
    # graded (item0 EM=1, item1 judge=1.0, item2 F1-fallback, item3 F1). Keeps n_graded up (reviewer F4).
    assert ts.n_graded == 4
    assert ts.n_err == 0
    f1_2 = rg.f1_score(gens["m"][2].text, corpus[2]["gold"])  # item2's fallback score
    f1_3 = rg.f1_score(gens["m"][3].text, corpus[3]["gold"])
    expected = (1.0 + 1.0 + f1_2 + f1_3) / 4 * 5  # mean over all 4 items × 5
    assert abs(ts.clamped_score5 - round(expected, 3)) < 1e-6


def test_no_evaluator_needed_when_no_near_miss():
    # All EM → grader must never construct/needs an evaluator (pass None, no vendor/npx).
    corpus = [{"question": "q", "gold": "fabrik"}]
    gens = {"m": [_gen("fabrik"), _gen("fabrik"), _gen("fabrik")]}
    scores = rg.research_grade(gens, corpus * 3, evaluator=None)
    assert scores["m"].clamped_score5 == 5.0


# ── (d) end-to-end on a 3-item stub-gens corpus → measured TaskScore ────────────────────────────
def test_end_to_end_three_item_measured():
    corpus = [
        {"question": "net?", "gold": "fabrik", "aliases": ["fabrik network"]},
        {"question": "pg?", "gold": "postgres-main:5432", "aliases": []},
        {"question": "port?", "gold": "8889", "aliases": [":8889"]},
    ]
    gens = {
        "good/model": [_gen("fabrik network"), _gen("postgres-main:5432"), _gen(":8889")],
        "bad/model": [_gen("no idea"), _gen(None), _gen("wrong")],
    }
    scores = rg.research_grade(gens, corpus, evaluator=FakeEvaluator())

    good = scores["good/model"]
    assert good.n_graded == 3
    assert good.is_measured is True
    assert good.clamped_score5 == 5.0  # all three hit an alias/gold EM

    bad = scores["bad/model"]
    assert bad.n_err == 1  # the None slot
    assert bad.clamped_score5 < 5.0


def test_grader_is_registered():
    from microbench_judged import GRADERS

    assert GRADERS.get("research") is rg.research_grade


def test_judge_score_is_clamped_to_unit_interval():
    """A judge that misreads the 0–1 scale and returns score=3 must be CLAMPED to 1.0, not inflate the
    mean (reviewer F7). One near-miss item, judged 3.0 → clamps to 1.0 → item score 1.0."""
    corpus = [
        {"question": "q0", "gold": "postgres-main", "aliases": []},
        {"question": "q1", "gold": "shared postgres host", "aliases": []},
    ]
    gens = {
        "m": [
            _gen("postgres-main"),  # item0 → EM = 1.0
            _gen("shared postgres host postgres-main"),  # item1 → near-miss → tiebreak
        ]
    }
    band_lo, band_hi = rg.NEAR_MISS_BAND
    assert band_lo <= rg.f1_score(gens["m"][1].text, corpus[1]["gold"]) < band_hi
    ev = FakeEvaluator(
        scored={"m||1": {"id": "m||1", "score": 3.0, "confidence": 5}}
    )  # out of range
    ts = rg.research_grade(gens, corpus, evaluator=ev)["m"]
    assert ts.n_graded == 2
    assert ts.clamped_score5 == 5.0  # (EM 1.0 + clamped 1.0) / 2 × 5 = 5.0 — NOT inflated past 5
