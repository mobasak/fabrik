"""Tests for the code-review quality benchmark — the pure (free) layer: corpus integrity + grader.

The pool dispatch (`run`) is a metered live call and is NOT unit-tested here; these cover the two
things that make the *score trustworthy*: (1) every mutant changes exactly its labeled line, so a
"caught" is real, and (2) the grader maps model output to lines the way scoring assumes.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import microbench_review as mr  # noqa: E402  (needs sys.path insert above)


def test_corpus_has_mutants_and_controls():
    corpus = mr.build_corpus()
    mutants = [i for i in corpus if i.truth_line is not None]
    controls = [i for i in corpus if i.truth_line is None]
    assert len(controls) == len(mr.VICTIMS), "one clean control per victim"
    assert len(mutants) >= 2 * len(mr.VICTIMS), "several planted defects per victim"


def test_every_mutant_changes_exactly_its_truth_line():
    """Ground-truth integrity — a mutant must differ from the unparsed original at ONLY truth_line."""
    for name, src in mr.VICTIMS.items():
        base = ast.unparse(ast.parse(src)).splitlines()
        for it in mr._mutants_for(name, src):
            mutant = [
                ln.split(": ", 1)[1] if ": " in ln else "" for ln in it.numbered_code.splitlines()
            ]
            diffs = [
                i + 1
                for i, (a, b) in enumerate(zip(base, mutant, strict=False))
                if a.strip() != b.strip()
            ]
            assert diffs == [it.truth_line], (
                f"{it.item_id}: changed {diffs}, labeled {it.truth_line}"
            )


def test_control_is_unmutated_original():
    corpus = mr.build_corpus()
    for it in corpus:
        if it.truth_line is None:
            original = ast.unparse(ast.parse(mr.VICTIMS[it.victim])).splitlines()
            control = [
                ln.split(": ", 1)[1] if ": " in ln else "" for ln in it.numbered_code.splitlines()
            ]
            assert [c.strip() for c in control] == [o.strip() for o in original]


def test_grader_parses_json_array():
    assert mr.cited_lines('[{"line": 8, "bug": "off by one"}]') == {8}
    assert mr.cited_lines('[{"line": 3, "bug": "x"}, {"line": 7, "bug": "y"}]') == {3, 7}


def test_grader_empty_array_is_no_flag():
    assert mr.cited_lines("[]") == set()


def test_grader_prose_no_bug_is_no_flag():
    assert mr.cited_lines("The code looks correct to me.") == set()


def test_grader_regex_fallback_for_models_that_ignore_format():
    assert mr.cited_lines("I think line 8 is wrong, and line 12 too") == {8, 12}


def test_grader_prefers_json_over_regex():
    # a model that emits BOTH a JSON array and prose — JSON is authoritative
    assert mr.cited_lines('Here: [{"line": 5, "bug": "z"}] (see line 99 discussion)') == {5}


def test_f1_edges():
    assert mr.f1(1.0, 1.0) == 1.0
    assert mr.f1(0.0, 0.0) == 0.0
    assert abs(mr.f1(0.5, 1.0) - 2 / 3) < 1e-9


def test_modelscore_metrics():
    s = mr.ModelScore(
        "m",
        n_mut=4,
        caught=3,
        n_ctrl=2,
        ctrl_flagged=1,
        latencies=[2.0, 4.0, 6.0],
        out_tokens=100,
        cost=0.01,
    )
    assert s.recall == 0.75
    assert s.precision == 0.5  # 1 - 1/2
    assert s.median_latency == 4.0
    assert 0 <= s.score5 <= 5


def test_perfect_recall_zero_precision_is_penalized():
    """A 'flag everything' model: catches all mutants but flags every control -> score must be low."""
    s = mr.ModelScore(
        "noise",
        n_mut=5,
        caught=5,
        n_ctrl=5,
        ctrl_flagged=5,
        latencies=[1.0],
        out_tokens=0,
        cost=0.0,
    )
    assert s.recall == 1.0 and s.precision == 0.0
    assert s.score5 == 0.0, "no precision credit => F1 collapses to 0"


class _Res:
    def __init__(self, text="", error=None, out_tokens=0, cost_usd=0.0, latency_s=1.0):
        self.text, self.error = text, error
        self.out_tokens, self.cost_usd, self.latency_s = out_tokens, cost_usd, latency_s


def _spec():
    return mr.AgentSpec(task="t", model="m", task_type="review")


def test_grade_excludes_errored_calls_not_scored_as_miss():
    """A 404/timeout must NOT count as a missed bug — it is excluded from recall entirely."""
    mut = mr.Item("m:1", "v", "1: x", truth_line=1, operator="op")
    specs = [_spec(), _spec()]
    meta = [("m", mut), ("m", mut)]
    results = [
        _Res(error="HTTP 404: no endpoints"),  # errored — must be excluded, not recall=0
        _Res(text='[{"line": 1, "bug": "x"}]', out_tokens=10, cost_usd=0.001),  # real catch
    ]
    scores, rows = mr.grade(specs, meta, results)
    s = scores["m"]
    assert s.n_err == 1 and s.n_mut == 1 and s.caught == 1
    assert s.recall == 1.0, "the one real call caught the bug; the 404 is not a miss"
    assert len(rows) == 1, "only the successful call feeds the flywheel"


def test_fully_errored_model_is_unmeasured_not_f():
    """All calls 404 => is_measured False => never persisted/ranked as an F."""
    mut = mr.Item("m:1", "v", "1: x", truth_line=1, operator="op")
    specs = [_spec() for _ in range(4)]
    meta = [("dead", mut) for _ in range(4)]
    results = [_Res(error="HTTP 404") for _ in range(4)]
    scores, _ = mr.grade(specs, meta, results)
    s = scores["dead"]
    assert s.n_err == 4 and s.n_mut == 0
    assert not s.is_measured, "a model we never reached is unmeasured, not graded"


def test_measured_requires_control_evidence_not_just_mutants():
    """A model with plenty of mutants but too FEW controls must be UNMEASURED — else precision is a
    vacuous 1.0 (0 controls flagged / 0 controls) computed on no evidence."""
    no_ctrls = mr.ModelScore(
        "x", n_mut=8, caught=6, n_ctrl=0, ctrl_flagged=0, latencies=[1.0], out_tokens=1, cost=0.0
    )
    assert no_ctrls.precision == 1.0, "vacuous precision when n_ctrl==0"
    assert not no_ctrls.is_measured, "n_ctrl=0 must not be measured despite good mutants"
    # ≥1 control is enough (smoke mode has only 2 controls; the floor must not exceed that)
    one_ctrl = mr.ModelScore(
        "y", n_mut=8, caught=6, n_ctrl=1, ctrl_flagged=0, latencies=[1.0], out_tokens=1, cost=0.0
    )
    assert one_ctrl.is_measured


def test_measured_requires_min_successful_mutants():
    below = mr.ModelScore(
        "x", n_mut=2, caught=2, n_ctrl=8, ctrl_flagged=0, latencies=[1.0], out_tokens=1, cost=0.0
    )
    at = mr.ModelScore(
        "y", n_mut=3, caught=3, n_ctrl=8, ctrl_flagged=0, latencies=[1.0], out_tokens=1, cost=0.0
    )
    assert not below.is_measured and at.is_measured


# ── equivalent-mutant filter (a mutant with no observable defect is not a valid test item) ────────


def test_no_equivalent_mutants_survive_corpus_build():
    """Every shipped mutant MUST be behaviorally distinguishable from its original over the victim's
    input domain. An equivalent mutant (e.g. `<`->`<=` where the branch outcome is provably identical)
    is UNKILLABLE: the reviewer correctly answers "no bug", we score it a miss, and every model loses
    the same point — compressing all scores toward an artificial tie.

    Proven live (2026-07-22): 5 of 22 mutants were equivalent, and all 4 claude tiers "missed" exactly
    those 5 on 20/20 repeated trials each, manufacturing identical recall across models.
    """
    for it in mr.build_corpus():
        if it.truth_line is None:
            continue
        assert not mr._is_equivalent_mutant(mr.VICTIMS[it.victim], it), (
            f"equivalent (unkillable) mutant shipped in the corpus: {it.item_id}"
        )


def test_equivalence_checker_flags_a_known_equivalent_mutant():
    """The checker must POSITIVELY identify a hand-built equivalent mutant — otherwise the filter
    above could pass vacuously (e.g. if the checker always returned False).

    Fixture: binary_search's `items[mid] < target` -> `<=`. It is UNCONDITIONALLY equivalent — the
    preceding line already returned on `items[mid] == target`, so `items[mid] != target` is an
    invariant by the time this branch runs and `<` / `<=` cannot diverge. Verified exhaustively
    (3,600 list/target combinations, zero differences).
    """
    src = mr.VICTIMS["binary_search"]
    equivalent_src = src.replace("if items[mid] < target:", "if items[mid] <= target:")
    assert equivalent_src != src, "fixture failed to mutate"
    item = mr.Item(
        item_id="binary_search:equiv-fixture",
        victim="binary_search",
        numbered_code=mr._number(ast.unparse(ast.parse(equivalent_src))),
        truth_line=7,
        operator="<->=<",
    )
    assert mr._is_equivalent_mutant(src, item), "known-equivalent mutant was not detected"


def test_equivalence_domain_covers_contract_violating_ranges():
    """A domain that only exercises the SANE precondition can miss a flip that diverges solely on a
    degenerate one — and would then wrongly certify a killable mutant as 'equivalent'.

    Real near-miss (2026-07-22): clamp's `value < low` -> `<=` is identical for every valid range
    (low <= high) and differs ONLY when low > high (an inverted range) at value == low. The first
    domain used low in (0,5) / high in (5,10), so low > high never occurred and the mutant was
    wrongly filtered. Assert the domain still reaches the degenerate case.
    """
    assert any(lo > hi for _v, lo, hi in mr._EQUIV_DOMAINS["clamp"]), (
        "clamp domain no longer covers an inverted (low > high) range — equivalence verdicts for "
        "boundary flips become unsound"
    )
    # ...and that the checker consequently classifies that flip as KILLABLE, not equivalent.
    src = mr.VICTIMS["clamp"]
    killable_src = src.replace("if value < low:", "if value <= low:")
    item = mr.Item(
        item_id="clamp:2:<->=<",
        victim="clamp",
        numbered_code=mr._number(ast.unparse(ast.parse(killable_src))),
        truth_line=2,
        operator="<->=<",
    )
    assert not mr._is_equivalent_mutant(src, item), (
        "clamp `<`->`<=` diverges on an inverted range — it must NOT be filtered as equivalent"
    )


def test_equivalence_checker_keeps_a_real_bug():
    """A genuinely killable mutant must NOT be filtered out (guards against over-eager exclusion)."""
    src = mr.VICTIMS["within_budget"]
    # `spent + incoming` -> `spent - incoming`: changes the result for any nonzero incoming.
    real_bug_src = src.replace("spent + incoming", "spent - incoming")
    item = mr.Item(
        item_id="within_budget:real-fixture",
        victim="within_budget",
        numbered_code=mr._number(ast.unparse(ast.parse(real_bug_src))),
        truth_line=2,
        operator="+->-",
    )
    assert not mr._is_equivalent_mutant(src, item), "a real bug was wrongly filtered as equivalent"
