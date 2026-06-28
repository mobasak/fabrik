"""Translation quality metric — chrF++ via sacrebleu.

Why chrF++ and not BLEU / word-overlap:
  - BLEU is brittle on morphologically-rich languages (TR, AR, RU, HI, KO);
    a perfectly correct translation can score 0 BLEU if a verb is conjugated
    differently from the reference.
  - Word-overlap (what fabrik-lib v1 used) doesn't tokenize CJK correctly
    and ignores morphology entirely.
  - chrF++ is the WMT-standard since 2020: character n-gram F-score with a
    word n-gram weight. Handles all scripts uniformly, gives partial credit
    for morphologically-close-but-not-identical output.

Reference: Popović, Maja (2017). "chrF++: words helping character n-grams."
Proceedings of the Second Conference on Machine Translation, Volume 2.

Usage:
    from metric import chrf_plus_plus
    score = chrf_plus_plus(hypothesis="Hello world", references=["Hello earth"])
    # → float in 0..100, higher is better

For sentence-level scoring we use the sentence_chrf helper. For corpus-level
aggregation (what we actually report) we use corpus_chrf which weights by
length.
"""

from __future__ import annotations

from sacrebleu.metrics import CHRF


# CHRF++ = chrf with word_order=2 (mixes char n-grams with word 1-grams + 2-grams).
# beta=2 gives recall double weight vs precision — the WMT 2020+ default.
_chrf_metric = CHRF(char_order=6, word_order=2, beta=2)


def chrf_plus_plus(hypothesis: str, references: list[str]) -> float:
    """Sentence-level chrF++ for a single hypothesis vs one or more references.
    Returns a 0..100 float (higher = better)."""
    if not hypothesis or not references:
        return 0.0
    score = _chrf_metric.sentence_score(hypothesis, references)
    return float(score.score)


def corpus_chrf_plus_plus(
    hypotheses: list[str],
    references: list[list[str]],
) -> float:
    """Corpus-level chrF++ aggregating across many sentences.

    `references` is a list where each inner list is the reference(s) for the
    SAME sentence. Length must match `hypotheses`. Each inner list typically
    has 1 entry (one human translation per source).
    """
    if not hypotheses:
        return 0.0
    # sacrebleu's corpus_score expects references transposed: per-reference-rank,
    # so a single-reference setup is `[[ref1_s1, ref1_s2, ...]]`.
    refs_transposed = [[refs[0] for refs in references]]
    score = _chrf_metric.corpus_score(hypotheses, refs_transposed)
    return float(score.score)
