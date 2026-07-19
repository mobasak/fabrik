# AFTER-EDIT: none
"""Docs grader for the judged benchmark — bidirectional git-grounded recall/precision (torch-free).

The docs task hands a model a STALE doc + a code diff and asks it to reconcile the doc; the model's
answer IS a unified-diff doc PATCH. We grade that patch against the human's real doc update (the git
`ground_truth`) on TWO axes, reusing the proven ``doc_reconcile`` symbol plumbing verbatim (no fork):

  precision — every backtick identifier the patch ADDS must resolve in the CODEBASE
              (``_codebase_haystack(root, skip_md=True)``). This is a COARSE hallucination filter: it
              catches a symbol that exists NOWHERE in the repo, not a plausible-but-wrong one that
              happens to appear somewhere (symbol-existence against a monorepo can't distinguish those).
  recall    — the human's REQUIRED edits are actually MADE by the model's patch: of the symbols the
              human ADDED to the doc, how many did the model's patch add; of the symbols the human
              REMOVED, how many did the model's patch remove (measured vs the git ``ground_truth`` doc,
              so it is grounded truth). This directly compares the two EDITS, not a reconstructed doc —
              so a symbol removed on one line but surviving on another is not falsely credited.

  score5 = f1(recall, precision) * 5     (same 0–5 scale + letter cuts as the sibling benches)

⚠️ Backtick identifiers are extracted PER LINE (``_line_tokens``): ``doc_reconcile._extract_tokens`` was
built for short ``+``-line patch SNIPPETS and its ```[^`]+``` spans newlines, so on a whole multi-line
doc its backticks pair SEQUENTIALLY across the file and sweep prose between an even→odd tick into a fake
"symbol". Line-scoping pairs ticks within a line — the only correct way to tokenize a full document.

Deterministic, local, $0 — no network, no torch, no AlignScore. ``doc_reconcile`` lives one level ABOVE
this dir (``scripts/``), so it is added to ``sys.path`` alongside the flat sibling ``microbench_judged``.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent  # scripts/kilo-benchmarks
# sibling harness (microbench_judged) is flat here; doc_reconcile is one level UP (scripts/) — add both.
for _p in (str(SCRIPT_DIR), str(SCRIPT_DIR.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import doc_reconcile as _dr  # noqa: E402 — scripts/doc_reconcile.py (parent dir); IMPORT, never fork
from microbench_judged import (  # noqa: E402 — flat sibling harness
    SCALE,
    TaskScore,
    _Gen,
    register_grader,
)

_REPO_ROOT = (
    SCRIPT_DIR.parent.parent
)  # default codebase haystack root when an item carries no `root`
_HAY_CACHE: dict[
    str, str
] = {}  # one haystack scan per root (57 models × N items would re-scan otherwise)


def _haystack(root: Path | str) -> str:
    """Cached ``doc_reconcile._codebase_haystack(root, skip_md=True)`` — CODE/config only, no .md, so a
    doc symbol can never self-validate against another (possibly stale) doc's prose."""
    key = str(root)
    if key not in _HAY_CACHE:
        _HAY_CACHE[key] = _dr._codebase_haystack(root, skip_md=True)
    return _HAY_CACHE[key]


def _line_tokens(text: str) -> set[str]:
    """Backtick identifiers in ``text``, extracted PER LINE then unioned. ``doc_reconcile._extract_tokens``
    pairs backticks with ```[^`]+```, which spans newlines — correct for a short ``+``-line snippet, but
    on a whole multi-line doc it pairs ticks SEQUENTIALLY across the file and captures the prose between an
    even→odd tick as a fake symbol. Splitting on lines first confines each pairing to one line."""
    toks: set[str] = set()
    for line in text.splitlines():
        toks |= _dr._extract_tokens(line)
    return toks


def _removed_lines(patch: str) -> str:
    """The REMOVED content lines of a unified diff (a leading '-' INSIDE a hunk) — the structural mirror
    of ``doc_reconcile._added_lines`` (which we reuse for the '+' side). The file header (``--- a/path``,
    which precedes the first ``@@``) is skipped by hunk position, so it is never mistaken for content."""
    removed: list[str] = []
    in_hunk = False
    for line in patch.splitlines():
        if line.startswith("@@"):
            in_hunk = True  # a hunk body follows (possibly several @@ hunks for one file)
            continue
        if not in_hunk or not line:
            continue  # diff --git / index / --- / +++ headers that precede the first hunk
        marker = line[0]
        if marker == "-":
            removed.append(line[1:])
        elif marker not in (" ", "+", "\\"):
            in_hunk = False  # left the hunk body → the next file's header block has begun
    return "\n".join(removed)


def _f1(recall: float, precision: float) -> float:
    return (2 * recall * precision / (recall + precision)) if (recall + precision) > 0 else 0.0


def _grade_item(patch: str, item: dict, root: Path | str) -> tuple[float, float]:
    """Grade ONE reconciliation patch → (recall, precision), both in [0, 1].

    Recall directly compares the two EDITS (model's patch vs the human's git ``ground_truth``), not a
    reconstructed doc: ``required`` = symbols the human ADDED (in gt, not stale), ``removed`` = symbols the
    human DELETED (in stale, not gt). Credit is (of the required additions, how many the model's patch also
    ADDED) + (of the required removals, how many the model's patch also REMOVED). Tokenization is PER LINE
    (see ``_line_tokens``). NOTE: the removal check is set-based, so if a stale symbol occurs on ≥2 lines
    and the model removes only one occurrence, it is still credited (the token appears in ``patch_removed``)
    — a known imprecision, acceptable because doc symbols are near-always unique; a multiset model would
    be needed to catch a partial removal."""
    stale_tok = _line_tokens(str(item.get("stale_doc", "")))
    gt_tok = _line_tokens(str(item.get("ground_truth", "")))
    required = gt_tok - stale_tok  # symbols the human ADDED to the doc (the required additions)
    removed = stale_tok - gt_tok  # symbols the human REMOVED from the doc (must be removed)

    added = _line_tokens(_dr._added_lines(patch))  # symbols the MODEL's patch adds
    patch_removed = _line_tokens(_removed_lines(patch))  # symbols the MODEL's patch removes

    # ── precision: no hallucinated symbols (every ADDED backtick ident resolves in real code) ──
    if not added:
        precision = (
            1.0  # nothing added → nothing to hallucinate (mirrors _default_verify's empty case)
        )
    else:
        hay = _haystack(root)
        resolved = sum(1 for t in added if re.search(r"\b" + re.escape(t) + r"\b", hay))
        precision = resolved / len(added)

    # ── recall: did the model make the human's required additions AND removals? ──
    denom = len(required) + len(removed)
    if denom == 0:
        recall = 1.0  # the doc needed no symbol change → a truthful no-op is perfect recall
    else:
        req_added = sum(1 for t in required if t in added)  # model added what the human added
        req_removed = sum(
            1 for t in removed if t in patch_removed
        )  # model removed what the human removed
        recall = (req_added + req_removed) / denom
    return recall, precision


def docs_grade(gens: dict[str, list[_Gen]], corpus: list[dict]) -> dict[str, TaskScore]:
    """Score each model's doc-reconciliation patches: ``score5 = mean(f1(recall, precision)) * 5``.

    Sets ``recall``/``precision`` on each TaskScore (the docs-family leaderboard axes). An errored /
    unreachable slot (``text is None``) is counted as ``n_err`` and never graded (never scored 0 — a
    404 is not a wrong answer). Deterministic + local; the harness overlays cost/latency downstream."""
    scores: dict[str, TaskScore] = {}
    for model, glist in gens.items():
        recalls: list[float] = []
        precisions: list[float] = []
        f1s: list[float] = []
        n_err = 0
        for i, item in enumerate(corpus):
            gen = glist[i] if i < len(glist) else None
            if gen is None or gen.text is None:
                n_err += 1
                continue
            root = item.get("root") or _REPO_ROOT
            recall, precision = _grade_item(gen.text, item, root)
            recalls.append(recall)
            precisions.append(precision)
            f1s.append(_f1(recall, precision))
        n_graded = len(f1s)
        scores[model] = TaskScore(
            model=model,
            score5=(sum(f1s) / n_graded * SCALE) if n_graded else 0.0,
            n_graded=n_graded,
            n_err=n_err,
            recall=round(sum(recalls) / len(recalls), 4) if recalls else None,
            precision=round(sum(precisions) / len(precisions), 4) if precisions else None,
        )
    return scores


register_grader("docs", docs_grade)
