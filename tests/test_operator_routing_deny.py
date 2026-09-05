"""Behavior contract for the hub's operator routing denies.

The denies are applied in `scripts/kilo-benchmarks/rank_task_subagents.py`, which GENERATES
`docs/reference/kilo/TASK_SUBAGENT_SELECTION.md` — the doc `libs/subagents.select.pick_models`
prefers over its vendored table. A model omitted from the emitted routing section is not routed to.

⚠️ WHY NOT IN `libs/subagents/select.py`, where the mechanism would be simpler. That module is
VENDORED from fabrik-lib (`fabrik_synced_manifest.VENDORED_DIRS`; the hub copy is contractually kept
byte-identical to `/opt/fabrik-lib/subagents` by re-vendoring). Editing it is an unauthorised fork of
another repo's code AND gets reverted by the next re-vendor. This was learned the expensive way on
2026-09-05: a deny was implemented there, force-synced to 46 project copies, and reverted three times
by the re-vendor — which I then misread as a defect rather than as the boundary working. The generator
is hub-owned; that is the whole point of this file's existence.

The root causes that argue for an upstream fix were mailed to fabrik-lib (01M1S7QACGEP66JM891E9B4CCQ).
If they adopt the denies in canonical, these entries become redundant — the intended end state.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
_KB = _ROOT / "scripts" / "kilo-benchmarks"
_DOC = _ROOT / "docs" / "reference" / "kilo" / "TASK_SUBAGENT_SELECTION.md"

sys.path.insert(0, str(_KB))
sys.path.insert(0, str(_ROOT))
_spec = importlib.util.spec_from_file_location("rank_deny", _KB / "rank_task_subagents.py")
rank = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rank)

from libs.subagents.select import pick_models  # noqa: E402

REVIEW_DENIED = ("qwen/qwen3-max", "google/gemini-3-flash-preview")
ALWAYS_DENIED = "deepseek/deepseek-v4-pro"


def test_the_denies_are_declared_in_hub_owned_code_not_the_vendored_module():
    """The placement IS the contract. If someone moves these back into `libs/subagents`, the deny
    becomes an unauthorised fork that the next re-vendor silently reverts."""
    assert set(rank.OPERATOR_DENY["review"]) == set(REVIEW_DENIED)
    assert ALWAYS_DENIED in rank.OPERATOR_DENY_ALWAYS
    vendored = (_ROOT / "libs" / "subagents" / "select.py").read_text(encoding="utf-8")
    assert "ROUTING_DENYLIST" not in vendored, (
        "a routing deny is back inside the VENDORED fabrik-lib module — that is not the hub's code "
        "to edit, and the next re-vendor reverts it. Put policy in rank_task_subagents.py."
    )


@pytest.mark.parametrize("model", REVIEW_DENIED)
def test_a_denied_reviewer_is_absent_from_the_emitted_review_section(model):
    """The doc is what routing reads, so absence FROM THE DOC is the deny."""
    doc = _DOC.read_text(encoding="utf-8")
    section = doc.split("### review (n_total=")[1].split("###")[0]
    assert f"`{model}`" not in section, f"{model} is still routable for review:\n{section}"


def test_the_broken_worker_is_absent_from_every_routing_section():
    """`deepseek/deepseek-v4-pro`: 83 dispatches across 9 repos since 2026-08-20, 67 errors (81%),
    65 recording no cost, 4.09 MB of prompt shipped. It ranked FIRST for `docs`."""
    # ⚠️ Bound each section to its OWN table rows. Splitting on "\n### " alone lets a routing
    # section run past the next "## " heading and swallow the display-only benchmark leaderboards
    # further down the doc — which DO list denied models legitimately ("display only; not parsed for
    # routing"). The first version of this test did exactly that and reported a routing defect that
    # did not exist.
    kind = None
    offenders = []
    for line in _DOC.read_text(encoding="utf-8").splitlines():
        if line.startswith("### ") and "(n_total=" in line:
            kind = line[4:].split(" ")[0]
            continue
        if line.startswith("#"):
            kind = None  # any other heading ends the routing section
            continue
        if kind and line.startswith("|") and f"`{ALWAYS_DENIED}`" in line:
            offenders.append((kind, line.strip()))
    assert not offenders, f"{ALWAYS_DENIED} is still routable: {offenders}"


@pytest.mark.parametrize("kind", ["review", "docs"])
def test_pick_models_end_to_end_honours_the_deny(kind):
    """The invariant that actually matters: what a dispatching agent gets back. Runs the REAL
    `pick_models` against the REAL doc — no fixture, because the doc is the coupling under test."""
    got = pick_models(kind, n=25)
    assert got, f"{kind} routing returned nothing — a deny must not empty a roster"
    assert ALWAYS_DENIED not in got
    if kind == "review":
        for m in REVIEW_DENIED:
            assert m not in got, f"{m} came back from pick_models({kind!r}): {got}"


def test_the_benchmark_supplement_cannot_reintroduce_a_denied_model():
    """The deny has to be applied at BOTH injection points. Filtering only the fleet-rows loop left
    qwen3-max and gemini-3-flash at ranks 3-4 of the review section as n=0 benchmark rows — where no
    amount of live evidence would ever have removed them, because they had no live rows to judge."""
    src = (_KB / "rank_task_subagents.py").read_text(encoding="utf-8")
    supplement = src.split("review_benchmark: list[str] = [")[1].split("]")[0]
    assert "OPERATOR_DENY" in supplement, (
        "the benchmark supplement no longer applies the operator deny — denied models will reappear "
        "as n=0 rows in the emitted review section"
    )
