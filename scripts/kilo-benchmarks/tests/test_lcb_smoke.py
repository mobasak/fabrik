"""Phase A Behavior Contract — the LiveCodeBench grading harness actually grades.

Given a 1-problem sample with a correct and a wrong solution, When codegen_metrics runs (via the
.lcb-venv subprocess in microbench_coding_direct.grade), Then pass@1 == 1.0 for correct, 0.0 for wrong.
Skips cleanly when .lcb-venv is absent so CI without the vendored tool stays green.
Mocked: nothing — exercises the REAL lcb_runner evaluator.
"""

import json
import sys
from pathlib import Path

import pytest

SCRIPT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPT_DIR))

import microbench_coding_direct as m  # noqa: E402

pytestmark = pytest.mark.skipif(
    not m.LCB_VENV_PY.exists(), reason=".lcb-venv absent (Phase-A provisioning not run)"
)


def _sample() -> dict:
    return {"input_output": json.dumps({"inputs": ["5\n"], "outputs": ["6\n"], "fn_name": None})}


def test_correct_solution_scores_pass_at_1_one():
    corpus = [m.Problem("q1", "read n, print n+1", "", _sample())]
    gens = {"good": [m._Gen("n=int(input())\nprint(n+1)", 0.001, 1.0, 10, None)]}
    scores = m.grade(gens, corpus)
    assert scores["good"].pass_at_1 == 1.0
    assert scores["good"].grade == "A+"


def test_wrong_solution_scores_pass_at_1_zero():
    corpus = [m.Problem("q1", "read n, print n+1", "", _sample())]
    gens = {"bad": [m._Gen("n=int(input())\nprint(n+2)", 0.001, 1.0, 10, None)]}
    scores = m.grade(gens, corpus)
    assert scores["bad"].pass_at_1 == 0.0
    assert scores["bad"].grade == "F"
