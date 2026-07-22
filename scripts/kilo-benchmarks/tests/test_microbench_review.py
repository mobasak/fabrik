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


# ── HARD corpus (hand-planted logic bugs) — soundness proven by EXECUTION, never by eye ──────────
# Every rule below is a lesson bought this week: the operator-flip corpus shipped 4 unkillable
# (semantically equivalent) mutants that scored every correct "no bug" answer as a miss, flattening
# all frontier models to an identical score. Hard items are therefore (a) kill-proven differentially
# on concrete probe inputs, (b) single-line-diff verified so truth_line is exact, and (c) contract-
# documented so ground truth never depends on guessing intent.


def _sole_fn(src: str):
    """Compile a hard-case snippet and return its single top-level function."""
    import ast as _ast

    tree = _ast.parse(src)
    fns = [n for n in tree.body if isinstance(n, _ast.FunctionDef)]
    assert len(fns) == 1, f"hard snippet must define exactly ONE top-level function, got {len(fns)}"
    ns: dict = {}
    exec(compile(src, "<hard-case>", "exec"), ns)  # noqa: S102 — fixed in-repo corpus source
    return ns[fns[0].name]


def test_hard_corpus_builds_with_derived_truth_lines():
    corpus = mr.build_hard_corpus()
    mutants = [i for i in corpus if i.truth_line is not None]
    controls = [i for i in corpus if i.truth_line is None]
    assert len(mutants) == len(mr.HARD_CASES) == 10
    assert len(controls) == len(mr.HARD_CASES) == 10
    assert len({i.item_id for i in corpus}) == len(corpus), "item ids must be unique"


def test_hard_every_bug_is_kill_proven_by_execution():
    """For EVERY hard case, at least one probe input must produce a DIFFERENT result from the
    buggy version than from the clean one. A case failing this is an unkillable (invalid) item —
    the exact defect class that invalidated the operator-flip corpus."""
    for case in mr.HARD_CASES:
        clean_fn = _sole_fn(case["clean"])
        buggy_fn = _sole_fn(case["buggy"])
        outcomes = []
        for args in case["probes"]:
            try:
                c = ("OK", clean_fn(*args))
            except Exception as e:  # noqa: BLE001 — outcome comparison, not error handling
                c = ("EXC", type(e).__name__)
            try:
                b = ("OK", buggy_fn(*args))
            except Exception as e:  # noqa: BLE001
                b = ("EXC", type(e).__name__)
            outcomes.append((c, b))
        assert any(c != b for c, b in outcomes), (
            f"hard case {case['name']!r}: NO probe distinguishes buggy from clean — unkillable item"
        )


def test_hard_clean_versions_run_without_error():
    """Controls must be genuinely clean: every probe runs the clean version without raising."""
    for case in mr.HARD_CASES:
        clean_fn = _sole_fn(case["clean"])
        for args in case["probes"]:
            clean_fn(*args)  # raises = the control itself is broken


def test_hard_truth_line_is_the_single_differing_line():
    """truth_line must be derivable as the EXACT one line (rstrip-compared, indentation counts)
    where buggy differs from clean — same line count, no second difference."""
    for case in mr.HARD_CASES:
        line = mr._hard_truth_line(case["clean"], case["buggy"])
        c_lines = case["clean"].splitlines()
        b_lines = case["buggy"].splitlines()
        assert len(c_lines) == len(b_lines)
        diffs = [
            i + 1
            for i, (a, b) in enumerate(zip(c_lines, b_lines, strict=True))
            if a.rstrip() != b.rstrip()
        ]
        assert diffs == [line]


def test_hard_truth_line_rejects_multi_line_diffs():
    with __import__("pytest").raises(ValueError):
        mr._hard_truth_line("a\nb\nc\n", "x\nb\ny\n")  # two differing lines
    with __import__("pytest").raises(ValueError):
        mr._hard_truth_line("a\nb\n", "a\nb\nc\n")  # different line counts


def test_hard_task_template_used_for_hard_items_only():
    hard_item = mr.build_hard_corpus()[0]
    std_item = mr.build_corpus()[0]
    assert "docstring states its intended CONTRACT" in mr._task_for(hard_item)
    assert "docstring states its intended CONTRACT" not in mr._task_for(std_item)
    # both keep the same JSON answer contract the grader parses
    assert '"line"' in mr._task_for(hard_item) and '"line"' in mr._task_for(std_item)


def test_hard_persist_goes_to_hard_table_never_standard(tmp_path, monkeypatch):
    """--hard persistence must land in HARD_TABLE and leave model_review_metrics untouched, and
    the hard resume-gate must read the hard table only (a standard-corpus measurement today must
    NOT resume-skip a hard run of the same model)."""
    import sqlite3 as _sq

    db = tmp_path / "kilo_agents.db"
    monkeypatch.setattr(mr, "DB_PATH", db)
    monkeypatch.setattr(mr, "ensure_table", lambda _p: None)
    s = mr.ModelScore(
        "claude-code/haiku",
        n_mut=10,
        caught=7,
        n_ctrl=10,
        ctrl_flagged=0,
        latencies=[1.0],
        out_tokens=10,
        cost=0.01,
    )
    mr.persist_metrics({s.model: s}, table=mr.HARD_TABLE)
    with _sq.connect(db) as c:
        tables = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert mr.HARD_TABLE in tables
    assert "model_review_metrics" not in tables, "--hard must not create/touch the standard table"
    # resume separation: hard table sees the model, the standard gate does not
    assert mr._measured_review_models(db_path=db, table=mr.HARD_TABLE) == {"claude-code/haiku"}
    assert mr._measured_review_models(db_path=db) == set()


def test_metrics_table_allowlist_is_enforced_not_advisory(tmp_path, monkeypatch):
    """The table name is f-string-interpolated into SQL (sqlite can't parametrize identifiers), so
    membership in _METRICS_TABLES must be a REAL check — an unknown table raises before any SQL runs
    (review finding 2026-07-23: the allowlist existed only as a comment)."""
    import pytest as _pt

    monkeypatch.setattr(mr, "DB_PATH", tmp_path / "kilo_agents.db")
    monkeypatch.setattr(mr, "ensure_table", lambda _p: None)
    with _pt.raises(ValueError, match="unknown metrics table"):
        mr._measured_review_models(db_path=tmp_path / "kilo_agents.db", table="evil; DROP TABLE x")
    with _pt.raises(ValueError, match="unknown metrics table"):
        mr.persist_metrics({}, table="evil; DROP TABLE x")
    # both legitimate tables still accepted
    assert mr._measured_review_models(db_path=tmp_path / "kilo_agents.db") == set()
    assert (
        mr._measured_review_models(db_path=tmp_path / "kilo_agents.db", table=mr.HARD_TABLE)
        == set()
    )


def test_main_hard_never_touches_baseline_or_flywheel(monkeypatch, tmp_path):
    """The load-bearing isolation guarantee lives in main()'s `if args.hard:` persist branch — test
    it AT THE main() LEVEL, not just persist_metrics in isolation: a future refactor dropping the
    guard must turn this red (review finding 2026-07-23: the branch was correct but uncovered)."""
    calls = {"persist": 0, "flywheel": 0, "metrics": []}
    monkeypatch.setattr(mr, "persist", lambda s: calls.__setitem__("persist", calls["persist"] + 1))
    monkeypatch.setattr(
        mr, "record_flywheel", lambda r: calls.__setitem__("flywheel", calls["flywheel"] + 1)
    )
    monkeypatch.setattr(
        mr,
        "persist_metrics",
        lambda s, table="model_review_metrics": calls["metrics"].append(table)
        or (tmp_path / "art.json"),
    )
    monkeypatch.setattr(mr, "_measured_review_models", lambda **k: set())
    monkeypatch.setattr(mr, "run_direct", lambda m, c, mt, cc: ([], [], []))
    rc = mr.main(["--hard", "--direct", "--persist", "--models", "claude-code/haiku"])
    assert rc == 0
    assert calls["persist"] == 0, "--hard must NEVER write model_task_baseline"
    assert calls["flywheel"] == 0, "--hard must NEVER record flywheel rows"
    assert calls["metrics"] == [mr.HARD_TABLE], "--hard metrics go to HARD_TABLE only"


def test_main_hard_rejects_smoke(monkeypatch):
    """--hard --smoke must fail loud (SystemExit), not silently dispatch a full 24-model x 20-item
    run when the operator asked for a cheap slice."""
    import pytest as _pt

    with _pt.raises(SystemExit):
        mr.main(["--hard", "--smoke", "--models", "claude-code/haiku"])


def test_build_hard_corpus_refuses_unkillable_case(monkeypatch):
    """Runtime enforcement: an unkillable case (buggy==clean on every probe) must abort the BUILD —
    dispatch of an invalid item is never reachable, independent of whether the test suite ran."""
    import pytest as _pt

    bad = {
        "name": "unkillable_fixture",
        "clean": "def f(x):\n    return x + 1\n",
        "buggy": "def f(x):\n    return 1 + x\n",  # semantically identical for ints
        "probes": [(1,), (0,), (-5,)],
    }
    monkeypatch.setattr(mr, "HARD_CASES", [bad])
    with _pt.raises(ValueError, match="not kill-proven"):
        mr.build_hard_corpus()


def test_hard_template_applies_to_clean_controls_too():
    """Both the mutant AND its clean control must get the SAME hard template — a divergence would be
    a formatting 'tell' letting a model infer mutant-vs-control from the prompt itself."""
    corpus = mr.build_hard_corpus()
    mutant = next(i for i in corpus if i.truth_line is not None)
    control = next(i for i in corpus if i.truth_line is None)
    assert "docstring states its intended CONTRACT" in mr._task_for(mutant)
    assert "docstring states its intended CONTRACT" in mr._task_for(control)


def test_main_hard_rejects_report(monkeypatch):
    """--hard --report must fail loud — report_stored() reads ONLY the standard tables, so silently
    printing standard-corpus numbers for a --hard ask would misrepresent their corpus."""
    import pytest as _pt

    with _pt.raises(SystemExit):
        mr.main(["--hard", "--report"])


def test_main_explicit_empty_models_dispatches_nothing(monkeypatch, capsys):
    """`--models` with ZERO values is an explicit empty request — it must dispatch NOTHING, never
    silently fall through to the full pick_models pool ([] is falsy; the old `or` pattern did)."""
    called = []
    monkeypatch.setattr(mr, "pick_models", lambda *a, **k: called.append(1) or ["m"])
    monkeypatch.setattr(mr, "run_direct", lambda *a, **k: called.append("dispatch") or ([], [], []))
    rc = mr.main(["--direct", "--models"])
    assert rc == 0
    assert not called, "explicit empty --models must neither pick_models nor dispatch"


def test_kill_proven_rejects_snippet_without_single_function():
    """_kill_proven's snippet loader must fail with the module's own clear ValueError, not an
    opaque IndexError, when a case snippet doesn't define exactly one top-level function."""
    import pytest as _pt

    bad = {
        "name": "no_fn_fixture",
        "clean": "X = 1\n",
        "buggy": "X = 2\n",
        "probes": [()],
    }
    with _pt.raises(ValueError, match="exactly ONE top-level function"):
        mr._kill_proven(bad)
