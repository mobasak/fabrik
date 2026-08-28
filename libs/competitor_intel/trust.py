"""Trust rails — the programmatic checks that keep the LLM-driven synthesis honest.

These are PURE functions (no LLM, no network), applied to every claim the synthesis tail produces:
(a) a verbatim quote must be a real substring of a fetched source (drops hallucinated evidence);
(b) a BEAT / white-space finding needs cross-source corroboration (one voice is not a market signal);
(c) source-weighting discounts vendor-sponsored / generic sources and the extreme 1★/5★ fake-review band,
    trusting the 2–4★ independent band — NOT a fake-review classifier (2026 research: LLM-written fakes are
    machine-undetectable, so weight sources, don't try to detect fakes).
"""

from __future__ import annotations

import re
from collections.abc import Collection, Iterable, Sequence

#: Minimum normalized-quote length to count as grounded — blocks a trivial common substring ("the", "app",
#: "audit") from grounding a hallucinated claim. A real verbatim review/pricing quote is a phrase, not a token.
_MIN_QUOTE = 8

#: The sentinel a synthesis stage emits when a value cannot be verified from the sources.
UNVERIFIED = "❓"

#: Prompt preamble injected into every synthesis LLM call — constrain the model to the given sources.
CONSTRAIN_TO_SOURCES = (
    "Use ONLY the sources provided below. Every claim must carry a verbatim quote copied exactly from a "
    "source plus that source's URL. If the sources do not support a value, output the string \"❓\" for it "
    "— never guess, never use outside knowledge."
)

_WS = re.compile(r"\s+")


def _normalize(text: str) -> str:
    """Collapse whitespace + lowercase so a quote matches a source across reflowed spacing/case."""
    return _WS.sub(" ", text or "").strip().lower()


def quote_grounded(quote: str, sources: Iterable[str]) -> bool:
    """True iff ``quote`` (non-trivial, ≥ ``_MIN_QUOTE`` chars) appears as a substring of at least one
    source text (whitespace- and case-normalized). The hallucination gate: a claim whose 'verbatim quote'
    is not actually in any source is dropped."""
    q = _normalize(quote)
    if len(q) < _MIN_QUOTE:
        return False
    return any(q in _normalize(src) for src in sources if src)


def grounded_source(quote: str, sources: Sequence[tuple[str, str]]) -> str | None:
    """The REAL source URL that grounds ``quote`` — the url of the first ``(text, url)`` source whose text
    contains the quote — or None if ungrounded. This is how a synthesis stage attaches provenance: the URL
    comes from the source the quote was actually found in, NEVER from a URL the LLM emits (which it can
    hallucinate). Corroboration + attribution then run on these real URLs."""
    q = _normalize(quote)
    if len(q) < _MIN_QUOTE:
        return None
    for text, url in sources:
        if text and q in _normalize(text):
            return url
    return None


def corroborated(source_urls: Iterable[str], *, min_sources: int = 2) -> bool:
    """True iff the finding is backed by at least ``min_sources`` DISTINCT source URLs. A weakness raised by
    one page is not yet a BEAT finding — it must repeat across independent sources."""
    distinct = {u.strip() for u in source_urls if u and u.strip()}
    return len(distinct) >= min_sources


# Domains/markers that indicate a vendor-controlled or generic/aggregated source → down-weight.
_LOW_TRUST_MARKERS = ("press", "prnewswire", "businesswire", "sponsored", "partner", "/blog/", "medium.com")


def source_weight(
    source_url: str,
    *,
    rating: float | None = None,
    subject_domain: str | Collection[str] | None = None,
) -> float:
    """A 0.0–1.0 trust weight for a review source. Heuristic, documented, NOT a fake-review classifier:

    - a source on the SUBJECT's own domain (self-published) → heavily discounted (0.2);
    - a vendor press-release / sponsored / generic-blog marker → discounted (0.4);
    - an extreme rating (≤1★ or ≥5★, the band most polluted by fakes/astroturf) → discounted (0.6);
    - the independent 2–4★ band → full weight (1.0);
    - everything else → 0.8.

    ``subject_domain`` accepts ONE domain or a collection of them, and the discount fires if ANY
    matches. The collection form exists because two discovered rivals can share a display name, and
    the caller must not have to pick which one's domain to keep — see the orchestrator's
    ``subject_domains`` build. Passing several domains can only ever *lower* the weight, never raise
    it, so the ambiguous case fails toward distrust rather than toward fabricated trust.
    """
    url = (source_url or "").lower()
    # ⚠️ THE `str` BRANCH MUST COME FIRST. `str` is itself a `Collection[str]`, so falling through to
    # the iterating branch with a bare domain would test each CHARACTER against the url — `"acme.com"`
    # would match any url containing "a". This is the classic str-is-a-sequence trap, and here it would
    # silently collapse EVERY source to the 0.2 self-published weight instead of raising.
    if isinstance(subject_domain, str):
        domains: tuple[str, ...] = (subject_domain,)
    elif isinstance(subject_domain, Iterable):
        # ⚠️ `Iterable`, NOT a bare `else`. Widening this parameter INVITED a shape the old `str | None`
        # could not express, and the bare `else` assumed everything non-str is iterable: a caller passing
        # `subject_domains={"Acme": 7}` — a well-typed Mapping with one bad VALUE — raised
        # `TypeError: 'int' object is not iterable` straight out of `gap_synthesis`, which this module
        # documents as a never-raise pure function. `synth.py` type-checks the outer Mapping for exactly
        # that reason; the check has to reach the values too, and it lives HERE because this is where the
        # value is finally used. `Iterable` rather than `Collection` on purpose — a generator is Iterable
        # but not a Collection, and silently ignoring one would be a quieter version of the same bug.
        domains = tuple(d for d in subject_domain if isinstance(d, str))
    else:
        domains = ()  # None, or a scalar we cannot interpret → no self-published discount, never a raise
    if any(d and d.lower() in url for d in domains):
        return 0.2
    if any(m in url for m in _LOW_TRUST_MARKERS):
        return 0.4
    if rating is not None and (rating <= 1.0 or rating >= 5.0):
        return 0.6
    if rating is not None and 2.0 <= rating <= 4.0:
        return 1.0
    return 0.8
