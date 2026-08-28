"""The element-ingestion seam: ONE predicate for "did we drop something, and does it matter?".

Every filtering comprehension in this module discards elements. Before this seam each one decided,
independently and usually silently, whether that discard was worth telling anyone about — and a
mechanical enumeration found 62 such candidate sites across 10 files. The failure that motivated the
seam is not any single drop; it is that a drop and a genuinely empty market produced **identical**
output: ``partial=False``, ``degrade_causes=[]``, ``status="ok"``.

**The split that makes this work, and that one `keep` predicate could not express:**

``shape``
    *Is this element well-formed?* A failure here is **real evidence loss** — a non-dict where a card
    belongs, a string where a `Signal` belongs. Counted as ``n_malformed``. Something was destroyed.

``want``
    *Do we want this well-formed element?* A failure here is a **business rule** — a card with nothing
    quotable, a non-negative sentiment in a negative-only view. Counted as ``n_filtered``. Nothing was
    destroyed; a rule declined it.

Conflating them is what killed the first design. ``deep_research``'s engine coerces every card through
the pack's closed schema and defaults a missing ``str`` field to ``""`` (``pack.py:85-91``), so
``{"snippet": "", "source_url": "..."}`` is a NORMAL, healthy extraction that simply found a page it
could not quote. A rule of "any drop degrades the run" fires on routine data — and since nothing in
this module ever resets ``partial`` (17 assignments, every one ``= True``), that false alarm is
PERMANENT for the job id. The seam therefore reports two numbers and lets each caller decide, rather
than deciding for all of them.

Both predicates are optional and **at least one is required** — a call with neither is a no-op dressed
as a filter, and it is a ``ValueError`` at the call rather than a silent identity function.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from typing import Any

__all__ = ["Taken", "take"]


@dataclass(frozen=True)
class Taken:
    """What survived, what did not, and which of the two kinds of "did not" it was."""

    #: The survivors, in the SAME container kind as the input (or a ``dict`` when ``key`` is given).
    #: ⚠️ NOT always a ``list``. An earlier design typed this ``list`` and could not express 8 of the
    #: 35 filtering comprehensions in this module, which build a ``dict`` or a ``set`` — including the
    #: two money-path sites where the checkpoint ledger and the per-leg review flags are rebuilt.
    kept: Any
    #: Elements that failed ``shape`` — REAL EVIDENCE LOSS. Something the caller could have used is gone.
    n_malformed: int
    #: Elements that failed ``want`` — a BUSINESS RULE declined them. Nothing was destroyed.
    n_filtered: int
    #: Where this happened, for the log line. A stable identifier, not a message.
    site: str
    #: The ``degrade_causes`` token to report, or ``None``. Set only when ``n_malformed`` is non-zero:
    #: a business-rule filter is not a degradation and must never manufacture a cause.
    #: ⚠️ A CLASS NAME or a fixed token, NEVER a message — this value is persisted into the resume
    #: checkpoint and restored forever, and ``degrade_causes`` is documented as an enumerated list.
    #: Interpolating an LLM-derived aspect or a scraped title here would store unbounded text.
    cause: str | None

    @property
    def n_dropped(self) -> int:
        """Total elements discarded, of either kind. Convenience for a log line — do NOT branch on
        this to decide whether to degrade: that is the conflation the seam exists to prevent."""
        return self.n_malformed + self.n_filtered


def take(
    raw: Any,
    *,
    site: str,
    shape: Callable[[Any], bool] | None = None,
    want: Callable[[Any], bool] | None = None,
    key: Callable[[Any], Any] | None = None,
    value: Callable[[Any], Any] | None = None,
    cause: str | None = None,
) -> Taken:
    """Filter ``raw``, counting SHAPE failures and WANT failures separately.

    ``raw`` may be a list, a tuple, a set, or a mapping. For a mapping the elements handed to the
    predicates are ``(key, value)`` PAIRS, which is what lets a dict-building comprehension keep its
    key-aware condition (``if isinstance(k, str) and k``) instead of being rewritten.

    ``key``/``value`` are the mapper half. 9 of this module's 35 filtering comprehensions filter AND
    map in one expression, so a seam that only filtered would have forced them to grow a second pass
    over the survivors — a second pass being exactly where a normalization divergence gets introduced.

    Output container mirrors the input: list/tuple → ``list``, set → ``set``, mapping → ``dict``.
    Passing ``key`` forces a ``dict`` regardless of input kind.

    Raises ``ValueError`` if neither predicate is given, and ``TypeError`` for a ``str``/``bytes`` or a
    non-iterable ``raw`` — see the notes on both below.
    """
    if shape is None and want is None:
        raise ValueError(
            f"take(site={site!r}) needs `shape` or `want` (or both): with neither it is an identity "
            "function wearing a filter's name, and every counter it returns would be a truthful zero "
            "about a question nobody asked."
        )

    # ⚠️ `str`/`bytes` are Iterable, so a caller passing one gets it silently shredded into characters
    # and a `kept` of single letters. This is the same str-is-a-sequence trap that `trust.source_weight`
    # had to be fixed for in this module; refusing it loudly is cheaper than the debugging session.
    if isinstance(raw, (str, bytes)):
        raise TypeError(f"take(site={site!r}) got {type(raw).__name__}; iterating it yields characters")

    is_mapping = isinstance(raw, Mapping)
    if is_mapping:
        elements: list[Any] = list(raw.items())
        kind = "dict"
    elif isinstance(raw, (set, frozenset)):
        elements = list(raw)
        kind = "set"
    elif isinstance(raw, Iterable):
        elements = list(raw)
        kind = "list"
    else:
        # ⚠️ DELIBERATELY A RAISE, not an empty result with a cause. `raw` not being a container at all
        # is a CONTAINER-level loss, which is a different lane with its own (still unwired) reporting —
        # and swallowing it here would CREATE a silent site inside the very seam built to remove them.
        # The caller type-checks its container and reports that itself; this seam only speaks about
        # elements.
        raise TypeError(
            f"take(site={site!r}) got a non-iterable {type(raw).__name__}; a missing CONTAINER is not "
            "an element loss and must be reported by the caller, not silently absorbed here"
        )

    if key is None and is_mapping:
        key = _pair_key
    if value is None:
        value = _pair_value if is_mapping else _identity

    survivors: list[Any] = []
    n_malformed = 0
    n_filtered = 0
    for element in elements:
        # SHAPE first, always: `want` may legitimately assume a well-formed element (it reads fields),
        # so running it on a malformed one is how a filter predicate learns to raise.
        if shape is not None and not shape(element):
            n_malformed += 1
            continue
        if want is not None and not want(element):
            n_filtered += 1
            continue
        survivors.append(element)

    kept: Any
    if key is not None:
        kept = {key(e): value(e) for e in survivors}
    elif kind == "set":
        kept = {value(e) for e in survivors}
    else:
        kept = [value(e) for e in survivors]

    return Taken(
        kept=kept,
        n_malformed=n_malformed,
        n_filtered=n_filtered,
        site=site,
        # a cause ONLY for real loss — a `want` filter is a rule doing its job, not a degradation
        cause=cause if n_malformed else None,
    )


def _identity(element: Any) -> Any:
    return element


def _pair_key(element: Any) -> Any:
    return element[0]


def _pair_value(element: Any) -> Any:
    return element[1]
