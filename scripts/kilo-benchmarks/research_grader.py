# AFTER-EDIT: scripts/kilo-benchmarks/corpora/research_qa.json | scripts/kilo-benchmarks/tests/test_research_grader.py
"""Research-task grader for microbench_judged — normalized EM / token-F1 + a near-miss tiebreak.

Scores each pool model's short free-text answer against a fabrik-private Q&A corpus, LOCALLY ($0):

  * EM   — HotpotQA `normalize_answer` (lowercase → strip punctuation → strip a/an/the → collapse
           whitespace) then a string compare vs the gold and any aliases → item_score 1.0.
  * F1   — otherwise token-overlap F1 vs the best-matching gold/alias → item_score.
  * tiebreak — when a non-EM answer lands in the near-miss band (`NEAR_MISS_BAND`, default
           0.5 ≤ F1 < 1.0), escalate JUST those items to a claude-evaluator (subscription npx,
           $0 on OpenRouter). An item the evaluator `.abstained` on (or fails to score) FALLS BACK
           to its objective F1 — never dropped, never scored 0 — so an abstention can't silently
           un-measure a model below MIN_MEASURED.

The normalize/EM/F1 helpers are vendored from the HotpotQA official evaluator
(https://github.com/hotpotqa/hotpot/blob/master/hotpot_evaluate_v1.py) — the grader, not the
questions. The evaluator is INJECTABLE (`research_grade(..., evaluator=...)`) so tests never shell
out to `npx`; the default is built lazily only when a near-miss actually fires.
"""

from __future__ import annotations

import os
import re
import string
import sys
from collections import Counter
from pathlib import Path
from typing import Protocol

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:  # flat sibling import, like the other kilo scripts
    sys.path.insert(0, str(SCRIPT_DIR))

from microbench_judged import TaskScore, _Gen, register_grader  # noqa: E402

# Near-miss band: a non-EM answer whose best F1 falls in [lo, hi) is escalated to the tiebreak.
# Overridable so an operator can widen/narrow the paid-tiebreak surface without a code edit.
NEAR_MISS_BAND: tuple[float, float] = (
    float(os.getenv("RESEARCH_TIEBREAK_LOW", "0.5")),
    float(os.getenv("RESEARCH_TIEBREAK_HIGH", "1.0")),
)
_TIEBREAK_MODEL = os.getenv("RESEARCH_TIEBREAK_MODEL", "haiku")


# ── HotpotQA-vendored normalize / EM / F1 (stdlib only) ─────────────────────────────────────────
def normalize_answer(s: str) -> str:
    """Lowercase, strip punctuation, drop articles (a/an/the), collapse whitespace (HotpotQA)."""

    def remove_articles(text: str) -> str:
        return re.sub(r"\b(a|an|the)\b", " ", text)

    def white_space_fix(text: str) -> str:
        return " ".join(text.split())

    def remove_punc(text: str) -> str:
        exclude = set(string.punctuation)
        return "".join(ch for ch in text if ch not in exclude)

    return white_space_fix(remove_articles(remove_punc(s.lower())))


def exact_match_score(prediction: str, ground_truth: str) -> bool:
    """True iff the two answers are identical after `normalize_answer` (order-sensitive on the string)."""
    return normalize_answer(prediction) == normalize_answer(ground_truth)


def f1_score(prediction: str, ground_truth: str) -> float:
    """Token-overlap F1 in [0, 1] after normalization (HotpotQA; yes/no/noanswer mismatch → 0)."""
    norm_pred = normalize_answer(prediction)
    norm_gt = normalize_answer(ground_truth)

    # HotpotQA guard: a yes/no/noanswer answer only matches its exact counterpart (no partial credit).
    for special in ("yes", "no", "noanswer"):
        if special in (norm_pred, norm_gt) and norm_pred != norm_gt:
            return 0.0

    pred_tokens = norm_pred.split()
    gt_tokens = norm_gt.split()
    common = Counter(pred_tokens) & Counter(gt_tokens)
    num_same = sum(common.values())
    if num_same == 0:
        return 0.0
    precision = num_same / len(pred_tokens)
    recall = num_same / len(gt_tokens)
    return (2 * precision * recall) / (precision + recall)


# ── tiebreak seam (injectable — the default builds a vendored ClaudeEvaluator lazily) ────────────
class _Evaluator(Protocol):
    """Anything with the vendored ClaudeEvaluator's `.evaluate_sync(items) -> EvalResult` shape."""

    def evaluate_sync(self, items: list[dict], extra_prompt: str = "") -> object: ...


_TIEBREAK_SYSTEM = (
    "You are a strict grader for short factual answers about a private infrastructure codebase. "
    "For each item you are given the question, the reference gold answer, and a candidate answer. "
    "Decide whether the candidate conveys the SAME fact as the gold (ignore wording/formatting). "
    "Return ONLY a JSON array; one object per item with keys: "
    '"id" (echo it), "score" (1.0 if the candidate is correct, 0.0 if wrong, a fraction if partly), '
    'and "confidence" (integer 1-5 of how sure you are). Do not add prose.'
)
_TIEBREAK_TEMPLATE = "Grade these candidate answers:\n{items}"


def _make_default_evaluator() -> _Evaluator:
    """Build the vendored ClaudeEvaluator (subscription npx; imported lazily so tests never need it)."""
    from vendor.claude_evaluator import ClaudeEvaluator, EvalConfig

    cfg = EvalConfig(
        system_prompt=_TIEBREAK_SYSTEM,
        user_prompt_template=_TIEBREAK_TEMPLATE,
        model=_TIEBREAK_MODEL,
        confidence_field="confidence",
        confidence_threshold=3,
    )
    return ClaudeEvaluator(cfg)


def _best(prediction: str, golds: list[str]) -> tuple[bool, float]:
    """Best (is_exact_match, best_f1) of `prediction` over gold + aliases."""
    is_em = any(exact_match_score(prediction, g) for g in golds)
    best_f1 = max((f1_score(prediction, g) for g in golds), default=0.0)
    return is_em, best_f1


def _golds(item: dict) -> list[str]:
    golds = [str(item.get("gold", ""))]
    golds.extend(str(a) for a in (item.get("aliases") or []))
    return [g for g in golds if g]


# ── the grader ───────────────────────────────────────────────────────────────────────────────
def research_grade(
    gens: dict[str, list[_Gen]],
    corpus: list[dict],
    *,
    evaluator: _Evaluator | None = None,
) -> dict[str, TaskScore]:
    """Grade every model's generations against `corpus` → `{model: TaskScore}` (score5 in 0–5).

    Per (model, item): normalized EM vs gold/aliases → 1.0; else token-F1. A non-EM answer whose
    best F1 lands in `NEAR_MISS_BAND` is deferred to ONE batched claude-evaluator tiebreak (across
    all models). A tiebreak-scored item takes the evaluator's (clamped) score; a tiebreak-ABSTAINED
    (or tiebreak-failed) item falls back to its objective F1. `n_graded` counts every graded item;
    `n_err` counts errored/empty generation slots. The evaluator is built lazily only if a
    near-miss actually fires — a corpus with no near-miss never touches npx.
    """
    item_scores: dict[str, list[float]] = {m: [] for m in gens}
    n_err: dict[str, int] = dict.fromkeys(gens, 0)
    # near-miss items to escalate: id "model||i" → (model, i, best_f1)
    pending: dict[str, tuple[str, int, float]] = {}

    for model, glist in gens.items():
        for i, g in enumerate(glist):
            if i >= len(corpus):  # defensive: never index past the corpus
                break
            if not g.text:  # None or "" — an errored/unreachable slot, never scored 0
                n_err[model] += 1
                continue
            golds = _golds(corpus[i])
            is_em, best_f1 = _best(g.text, golds)
            if is_em:
                item_scores[model].append(1.0)
            elif NEAR_MISS_BAND[0] <= best_f1 < NEAR_MISS_BAND[1]:
                pending[f"{model}||{i}"] = (model, i, best_f1)
            else:
                item_scores[model].append(best_f1)

    if pending:
        _resolve_tiebreak(pending, gens, corpus, evaluator, item_scores)

    scores: dict[str, TaskScore] = {}
    for model in gens:
        vals = item_scores[model]
        mean = sum(vals) / len(vals) if vals else 0.0
        scores[model] = TaskScore(
            model=model,
            score5=mean * 5.0,
            n_graded=len(vals),
            n_err=n_err[model],
        )
    return scores


def _resolve_tiebreak(
    pending: dict[str, tuple[str, int, float]],
    gens: dict[str, list[_Gen]],
    corpus: list[dict],
    evaluator: _Evaluator | None,
    item_scores: dict[str, list[float]],
) -> None:
    """Escalate the near-miss items to the (injected or lazily-built) evaluator, in one batch.

    scored → the evaluator's `score` (clamped to [0,1]); abstained/failed → fall back to the item's
    objective F1 (NOT dropped). Falling back rather than excluding keeps `n_graded` up (a model whose
    near-misses all abstain is never silently un-measured below MIN_MEASURED) and keeps the score
    deterministic. On any evaluator error the whole batch falls back to F1 (fail-soft, $0)."""
    items = [
        {
            "id": key,
            "question": str(corpus[i].get("question", "")),
            "gold": " | ".join(_golds(corpus[i])),
            "candidate": gens[model][i].text,
        }
        for key, (model, i, _f1) in pending.items()
    ]
    try:
        ev = evaluator or _make_default_evaluator()
        result = ev.evaluate_sync(items)
        scored = dict(getattr(result, "scored", {}) or {})
    except Exception:  # noqa: BLE001 — tiebreak unavailable → fail-soft to F1, never crash the bench
        for _key, (model, _i, f1) in pending.items():
            item_scores[model].append(f1)
        return

    for key, (model, _i, f1) in pending.items():
        if key in scored:
            rec = scored[key]
            try:
                s = float(rec.get("score", f1))
            except (TypeError, ValueError):
                s = f1
            item_scores[model].append(
                max(0.0, min(1.0, s))
            )  # clamp judge score to [0,1] (reviewer F7)
        else:
            # abstained OR dropped OR failed → fall back to the objective F1, never silently un-measure
            # the item (keeps n_graded up + deterministic; reviewer F4/F6/F8). `abstained` unused now.
            item_scores[model].append(f1)


register_grader("research", research_grade)
