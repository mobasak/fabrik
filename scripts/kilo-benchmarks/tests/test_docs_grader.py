"""Phase C Behavior Contract — the docs grader (docs_grader.docs_grade).

Bidirectional git-grounded recall/precision, scored against a controlled temp codebase (no network,
no torch, no real repo). Covers the four load-bearing behaviors:

  (a) [TDD, FIRST] a patch adding a HALLUCINATED symbol     → precision < 1
  (b) a patch OMITTING a required edit                       → recall < 1
  (c) a patch leaving a REMOVED symbol still present         → recall < 1
  (d) the ground-truth patch itself                          → score5 ≈ 5 (grade A+)
"""

import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent.parent  # scripts/kilo-benchmarks
sys.path.insert(0, str(SCRIPT_DIR))

import docs_grader as dg  # noqa: E402
import microbench_judged as mj  # noqa: E402

# The stale doc names `old_endpoint`; the human's fix swaps it to `new_endpoint`, keeping `keep_symbol`.
_STALE = "The API exposes `old_endpoint` for data.\nUse `keep_symbol` always.\n"
_GROUND_TRUTH = "The API exposes `new_endpoint` for data.\nUse `keep_symbol` always.\n"


def _root(tmp_path: Path) -> Path:
    """A tiny real codebase: `new_endpoint` + `keep_symbol` exist in code; `old_endpoint` does NOT
    (the code change that removed it is exactly what makes the doc stale)."""
    (tmp_path / "code.py").write_text(
        "def new_endpoint():\n    return keep_symbol\nkeep_symbol = 1\n"
    )
    (tmp_path / "notes.md").write_text(
        "this .md must be ignored — `phantom_md_only` lives only here\n"
    )
    return tmp_path


def _grade_one(patch: str, tmp_path: Path) -> mj.TaskScore:
    item = {"stale_doc": _STALE, "ground_truth": _GROUND_TRUTH, "root": str(_root(tmp_path))}
    gen = mj._Gen(text=patch, cost_usd=0.0, latency_s=1.0, out_tokens=5, error=None)
    return dg.docs_grade({"m/x": [gen]}, [item])["m/x"]


# ── (a) TDD, FIRST — a hallucinated added symbol tanks precision ───────────────────────────────
def test_hallucinated_added_symbol_lowers_precision(tmp_path):
    patch = (
        "--- a/doc.md\n+++ b/doc.md\n@@ -1,2 +1,2 @@\n"
        "-The API exposes `old_endpoint` for data.\n"
        "+The API exposes `fake_symbol_zzz` for data.\n"
        " Use `keep_symbol` always.\n"
    )
    s = _grade_one(patch, tmp_path)
    assert (
        s.precision is not None and s.precision < 1.0
    )  # `fake_symbol_zzz` resolves in no code file
    assert s.n_graded == 1


# ── (b) an omitted required edit tanks recall ──────────────────────────────────────────────────
def test_omitted_required_edit_lowers_recall(tmp_path):
    # Touches only the unrelated `keep_symbol` line — never adds the required `new_endpoint`, never
    # removes the stale `old_endpoint`.
    patch = (
        "--- a/doc.md\n+++ b/doc.md\n@@ -2,1 +2,1 @@\n"
        "-Use `keep_symbol` always.\n"
        "+Use `keep_symbol` daily.\n"
    )
    s = _grade_one(patch, tmp_path)
    assert s.recall is not None and s.recall < 1.0  # required `new_endpoint` never added


# ── (c) a removed symbol left present tanks recall ─────────────────────────────────────────────
def test_removed_symbol_left_present_lowers_recall(tmp_path):
    # Adds the required `new_endpoint` but never DELETES the stale `old_endpoint` line → it survives.
    patch = (
        "--- a/doc.md\n+++ b/doc.md\n@@ -1,2 +1,3 @@\n"
        " The API exposes `old_endpoint` for data.\n"
        "+It also exposes `new_endpoint`.\n"
        " Use `keep_symbol` always.\n"
    )
    s = _grade_one(patch, tmp_path)
    assert (
        s.recall is not None and s.recall < 1.0
    )  # `old_endpoint` still present in the reconciled doc
    assert s.precision == 1.0  # `new_endpoint` is real — isolates the failure to recall


# ── (d) the ground-truth patch scores a perfect A+ ─────────────────────────────────────────────
def test_ground_truth_patch_scores_perfect(tmp_path):
    patch = (
        "--- a/doc.md\n+++ b/doc.md\n@@ -1,2 +1,2 @@\n"
        "-The API exposes `old_endpoint` for data.\n"
        "+The API exposes `new_endpoint` for data.\n"
        " Use `keep_symbol` always.\n"
    )
    s = _grade_one(patch, tmp_path)
    assert s.recall == 1.0 and s.precision == 1.0
    assert s.score5 >= 4.9 and s.clamped_score5 == 5.0 and s.grade == "A+"


def test_ground_truth_patches_score_high_on_real_corpus():
    """REGRESSION for the whole-doc-tokenization bug (reviewer finding 1): grading each corpus pair's
    OWN ground_truth_patch — the human's real fix, definitionally A+ — must score ~5. Before the
    line-scoped fix, cross-line backtick mispairing scored items 0.00/0.24/0.00. Guards against a
    revert to feeding whole docs into doc_reconcile._extract_tokens."""
    import json

    import docs_grader as dg

    corpus = json.loads((dg.SCRIPT_DIR / "corpora" / "docs_pairs.json").read_text())
    for i, item in enumerate(corpus):
        gtp = item.get("ground_truth_patch") or item.get("diff")
        r, p = dg._grade_item(gtp, item, item.get("root") or dg._REPO_ROOT)
        assert r >= 0.9, f"item {i}: the human's own patch must have high recall, got {r}"
        assert dg._f1(r, p) * 5 >= 4.5, (
            f"item {i}: ground-truth patch must grade ~A+, got {dg._f1(r, p) * 5}"
        )


def test_multiline_doc_with_odd_backticks_tokenizes_per_line():
    """A multi-line doc with an ODD stray backtick would MISPAIR across lines under the whole-doc
    _extract_tokens (sweeping prose into a fake symbol) — _line_tokens confines each pairing to one
    line, so it does NOT. This is the exact fix for reviewer finding 1/2."""
    import docs_grader as dg

    # 5 backticks (odd): `db_host` (2) · a bare stray ` (1) · `db_port` (2). Whole-doc pairing captures
    # "db_host", then the cross-line span "... in prose\nthe ..." (→ "prose"), leaving db_port unpaired.
    doc = "config `db_host` here\nnote: a bare ` in prose\nthe `db_port` value\n"
    line_toks = dg._line_tokens(doc)
    whole_toks = dg._dr._extract_tokens(doc)  # the OLD (buggy) path
    assert {"db_host", "db_port"} <= line_toks  # per-line: both real idents, cleanly
    assert "prose" not in line_toks  # line-scoping does NOT sweep cross-line prose
    assert "prose" in whole_toks  # ...but the whole-doc path DOES — proves why the fix is needed
