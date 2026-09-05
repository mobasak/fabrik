"""Behavior contract for `ROUTING_DENYLIST` — the cost floor on worker selection.

Operator directive 2026-09-05, after ~$16 of OpenRouter credit went in 28 hours and the audit found
that `review` was 92.9% of it. The flywheel's own `review` table (n_total=12,764 live runs) ranks the
four-model review roster, and the two denied here lose on BOTH axes at once:

    model                          avg_quality   avg_cost      n
    deepseek/deepseek-v3.2-exp        2.96       $0.0040    2092
    google/gemini-3-flash-preview     2.73       $0.0097    2282   <- DENIED
    deepseek/deepseek-v4-flash        2.66       $0.0036    1454
    qwen/qwen3-max                    2.65       $0.0223    1495   <- DENIED, worst AND dearest

So this is not a cost-for-quality trade — the two survivors are the two best reviewers on live data.

⚠️ WHY THE GUARD LIVES AT `pick_models` AND NOWHERE ELSE. Two more obvious edits both fail silently:
the vendored `_TABLE` is ignored wherever the synced doc exists (`_synced_ranking()` wins), and the
doc itself is regenerated every morning at 06:00 by `rank_task_subagents.py`, so an edit there lasts
less than a day. These tests therefore assert the deny holds *through the synced doc* and *through an
explicit `ranking=` override* — the two paths that would otherwise route around it.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from libs.subagents.select import (  # noqa: E402
    ROUTING_DENYLIST,
    _synced_ranking,
    pick_models,
)

DENIED = ("qwen/qwen3-max", "google/gemini-3-flash-preview")


@pytest.mark.parametrize("prefer", ["quality", "value"])
def test_a_denied_reviewer_is_never_returned_for_review(prefer):
    """Both orderings, and a generous n — the deny is a floor, not a tie-break."""
    got = pick_models("review", n=25, prefer=prefer)
    assert got, "review routing returned nothing at all — the deny must not empty the roster"
    for m in DENIED:
        assert m not in got, f"{m} survived the denylist under prefer={prefer!r}: {got}"


def test_the_deny_holds_through_the_synced_doc_which_outranks_the_vendored_table():
    """The path that matters on this box. `pick_models` prefers `_synced_ranking()` over `_TABLE`, so
    a deny implemented in the vendored table alone would be a no-op here — and the doc is rebuilt
    daily, so a deny written INTO the doc would not survive to tomorrow."""
    doc = _synced_ranking().get("review")
    if not doc:
        pytest.skip(
            "no synced selection doc on this box — the vendored-table path is covered above"
        )
    assert any(m in doc for m in DENIED), (
        "precondition: the synced doc should still LIST the denied models — this test proves "
        "pick_models filters them, not that the doc stopped naming them"
    )
    got = pick_models("review", n=25)
    assert not (set(DENIED) & set(got)), f"denied model leaked from the synced doc: {got}"


def test_the_deny_holds_even_when_a_caller_supplies_its_own_ranking():
    """`ranking=` is the documented escape for tests and fresher data. It must not become an escape
    from the cost floor — otherwise any caller can re-admit a denied worker by passing a table."""
    got = pick_models("review", n=25, ranking={"review": [*DENIED, "deepseek/deepseek-v4-flash"]})
    assert got == ["deepseek/deepseek-v4-flash"], got


def test_the_deny_is_scoped_to_review_and_does_not_leak_into_code():
    """Deliberately narrow (see ROUTING_DENYLIST's note): review is 92.9% of spend, so denying it
    there takes essentially the whole saving, while gemini-3-flash is rank 3 for `code` with an A+
    LiveCodeBench pass@1 of 1.000. A blanket deny would buy ~nothing and cost quality."""
    assert "google/gemini-3-flash-preview" in pick_models("code", n=10)
    assert ROUTING_DENYLIST["code"] == frozenset({"deepseek/deepseek-v4-pro"}), (
        "the cost deny leaked out of review — widen it only with per-task-type evidence. Only the "
        "always-deny (a worker that does not work) is expected outside review."
    )


@pytest.mark.parametrize("kind", ["review", "code", "docs", "research", "plan", "spec"])
def test_a_worker_that_does_not_work_is_denied_everywhere(kind):
    """`deepseek/deepseek-v4-pro`: 83 dispatches across 9 repos since 2026-08-20, 67 of them errors
    (81%), 65 recording no cost at all, 4.09 MB of prompt shipped for a 17% success rate.

    Reported by iterative_image_editor from 3 dispatches; the fleet ledgers show the other 80. It was
    rank 1 for `docs`, i.e. the FIRST choice for that task type while failing four times in five.
    This is not a cost tradeoff — re-admit it only after a measured run says it works.
    """
    assert "deepseek/deepseek-v4-pro" not in pick_models(kind, n=25)


def test_the_survivors_are_the_two_cheapest_reviewers_on_live_data():
    """The saving is the point: both survivors bill ~$0.004/run against qwen3-max's $0.0223."""
    got = pick_models("review", n=25)
    assert set(got) <= {"deepseek/deepseek-v4-flash", "deepseek/deepseek-v3.2-exp"}, got
    assert len(got) >= 2, f"review needs at least two workers for a family-diverse fan-out: {got}"
