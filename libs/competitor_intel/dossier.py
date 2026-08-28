"""The output shapes — :class:`Signal` (a tier-tagged review/demand signal) and :class:`Dossier` (the
returned match-then-beat document).

Both are defined here in Phase A so ``Signal`` exists before its Phase-A consumer (the reviews stage) and
its Phase-C producers (the adapters import it). Phase B EXTENDS ``Dossier`` (feature matrix, MATCH/BEAT
lists, optional pricing/white-space blocks + ``to_markdown``); the Phase-A skeleton stays valid.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Final, Literal

if TYPE_CHECKING:  # annotations only — avoids the runtime cycle (synth/stages import dossier)
    from .stages import PricingBlock, WhiteSpaceBlock
    from .synth import BeatItem, MatchItem, Matrix

#: Link schemes `to_markdown` will emit. Everything else — `javascript:`, `data:`, `vbscript:`, `file:` —
#: is rendered as inert text, because a competitor `url` comes from an LLM reading a scraped page and the
#: dossier is routinely pasted into a markdown viewer that turns links into clickable HTML.
_SAFE_URL_SCHEMES: Final = ("https://", "http://")

#: Characters that must never survive into rendered output un-escaped. `|` corrupts a markdown TABLE
#: silently (see the renderer note below); the newline family escapes a bullet and can forge headings.
#: ⚠️ ALL TEN codepoints `str.splitlines()` treats as a line boundary — not just the four obvious
#: ones. The module's own structural safety oracle (`tests/test_render_safety.py`) is `splitlines()`-based,
#: so the six that used to survive (`\v \f \x1c \x1d \x1e \x85`) could forge a degraded banner or a
#: heading that the very suite proving this renderer safe could not see. CommonMark does not end lines
#: on them, so an HTML render was never affected — the exposure is every LINE-BASED consumer, ours included.
_LINE_BREAKS: Final = str.maketrans(
    dict.fromkeys("\n\r\v\f\x1c\x1d\x1e\x85\u2028\u2029", " ")
)

#: A dangling head-of-entity left by truncation (`&`, `&a`, `&am`, `&amp`, `&l`, `&lt`, …) — i.e. an `&`
#: plus up to a few name chars with no closing `;` at the end of a string.
_PARTIAL_ENTITY: Final = re.compile(r"&[a-zA-Z]{0,5}$")


def _inline(text: str) -> str:
    """Untrusted text for an INLINE position (a bullet, a heading, a quote).

    Collapses the newline family so a field cannot break out of its bullet and forge a section;
    neutralises the backslash+backtick pair so it cannot open a code span that swallows the rest; and
    escapes `[`/`]` so untrusted text cannot construct a LINK or an IMAGE. The image case is the one
    with teeth: a scraped `positioning` of `![](https://tracker.example/p.png)` renders as a tracking
    beacon that fires — revealing the reader's IP and the fact that they are researching this market —
    the moment anyone opens the brief. Links are built by :func:`_link`, never by the text itself.

    Deliberately NOT a full markdown escaper: this is a human brief, and escaping every `*` and `_`
    would make ordinary product copy unreadable for no security gain.
    """
    cleaned = text.translate(_LINE_BREAKS).replace("\\", "＼").replace("`", "'")
    # `<`/`>` BEFORE the bracket escaping: markdown passes raw HTML straight through, so escaping only
    # the `![]()` image form left its strictly more powerful twin untouched — `<img src=https://tracker/…>`
    # fires the same beacon, and `<script>` is stored XSS in any renderer that emits HTML. As entities they
    # stay VISIBLE to the reader (a renderer prints `<script>`) while being inert.
    cleaned = cleaned.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return cleaned.replace("[", "\\[").replace("]", "\\]").strip()


#: Upper magnitude for any number this module will render. Beyond it the value is not a plausible
#: count or weight, and — the load-bearing half — Python 3.11+ caps int→str at
#: ``sys.get_int_max_str_digits()`` (4300), so rendering a big enough int RAISES instead of printing.
_MAX_RENDERED_NUMBER: Final = 10**12

#: What a number that cannot be rendered honestly becomes. Not ``"0"`` — that would be a false claim
#: in place of an absent one.
_UNRENDERABLE_NUMBER: Final = "n/a"


def _seq(value: object) -> list[Any]:
    """A consumer-supplied "list" field, as a real list — or empty. Never a raise.

    ⚠️ THE SIBLING MISS, THIRD OCCURRENCE IN ONE PHASE, so this sweeps the CLASS instead of the
    instance. `af2c18f` gave `review_signal`, `rivals_having` and `source_urls` a `len()` guard and
    left `competitors` THREE LINES AWAY unguarded — `d.competitors = None` then crashed
    `to_markdown()` with `TypeError`, and that is not even an adversarial input: an upstream stage
    assigning `None` on an error path produces it. Every list-annotated field on this dataclass is a
    HINT, not enforcement, and the render must never blow up after the money is already spent.
    """
    return list(value) if isinstance(value, (list, tuple)) else []


def _obj(value: object, attr: str) -> Any:
    """A consumer-supplied composite field, or ``None`` if it is not the shape the renderer expects.

    Same class as :func:`_seq`, for the Optional composite fields: `feature_matrix`, `pricing`,
    `white_space`. Each was gated only on TRUTHINESS (`if self.pricing and self.pricing.wedge`), so a
    truthy wrong-typed value — a leftover string, a dict from a hand-rolled deserializer — reached the
    attribute access and raised `AttributeError` mid-render. Duck-typing on the one attribute the
    renderer needs keeps a consumer's own compatible shape working, which an `isinstance` check
    against our concrete class would have broken for no gain.
    """
    return value if hasattr(value, attr) else None


def _count_any(value: object) -> int:
    """``len()`` of a consumer-supplied sequence, or 0 — never a raise.

    The fields these render (``source_urls``, ``rivals_having``, ``review_signal``) are annotated
    ``list[...]`` and not enforced. ``len()`` on a non-``Sized`` raises unconditionally, and
    ``__len__`` is overridable besides — same class as the numeric guards, different function. A count
    the data cannot support is reported as 0 rather than taking down a render the caller has already
    paid for.
    """
    try:
        n = len(value)  # type: ignore[arg-type]
    except Exception:  # noqa: BLE001 — the render must never raise
        return 0
    return n if isinstance(n, int) and not isinstance(n, bool) and 0 <= n <= _MAX_RENDERED_NUMBER else 0


def _plain_int(value: object) -> int | None:
    """A BUILTIN ``int`` from an ``int`` (or subclass), touching no dunder on the object itself.

    ⚠️ THIS IS THE THIRD VERSION OF THIS GUARD, and the first two failed the same way in different
    places: they trusted a method the untrusted object controls.

    v1 checked ``isinstance`` and returned the ORIGINAL object — f-string formatting then called the
    instance's ``__str__``, so an ``int`` subclass injected markdown straight through the guard.
    v2 coerced with ``int(value)`` and bounded the magnitude with ``value <= 0`` / ``abs(value)`` —
    but ``__int__``, ``__abs__``, ``__gt__`` and ``__le__`` are ALL overridable, so a subclass could
    lie about its size to slip past the bound (then blow up on the very ``str()`` the bound protected)
    or make the coercion itself raise. Review reproduced both.

    ``int.__int__(value)`` is the BASE class's implementation applied to the instance: a subclass
    override cannot intercept it, and the result is a plain ``int`` whose comparisons are then the
    real ones. The ``try`` is the belt to that braces — this module's invariant is that the render
    must never raise after the money is already spent, and an unrenderable number is worth silence,
    never an exception.
    """
    try:
        return int.__int__(value)  # type: ignore[arg-type]
    except Exception:  # noqa: BLE001 — the render must never raise; see the docstring
        return None


def _plain_float(value: object) -> float | None:
    """The ``float`` twin of :func:`_plain_int` — same reasoning, same base-class technique."""
    try:
        return float.__float__(value)  # type: ignore[arg-type]
    except Exception:  # noqa: BLE001 — the render must never raise
        return None


def _count(value: object) -> int:
    """A rendered COUNT must be a real non-negative ``int``, or no count is rendered at all.

    ⚠️ Numbers were the one rendered category with NO sanitizer. Every text field in this file goes
    through :func:`_inline` / :func:`_cell` / :func:`_code_span`; the counts and weights went out raw
    on the assumption that a dataclass annotated ``int`` holds an ``int``. Python does not enforce
    that, and ``BeatItem`` / ``UnmetNeed`` are EXPORTED — the README explicitly tells consumers they
    may construct them. Review reproduced a hand-built ``quotes_omitted`` of
    ``"3)\n\n![x](javascript:alert(1))\n\n("`` breaking clean out of its list item and injecting an
    image tag, in a module whose entire `test_render_safety.py` exists to stop exactly that.

    COERCION, not escaping: an escaped non-number would still render the attacker's string as a count.
    A value that is not a usable count supports no claim, so the correct output is silence.
    ``bool`` is excluded deliberately — it is an ``int`` subclass, and "True quotes omitted" is not a
    count either.
    """
    if isinstance(value, bool) or not isinstance(value, int):
        return 0
    plain = _plain_int(value)
    if plain is None or plain <= 0 or plain > _MAX_RENDERED_NUMBER:
        return 0
    return plain


def _number(value: object) -> str:
    """Render a numeric field (a weight) for an INLINE position.

    The twin of :func:`_count`, and the reason it exists: ``BeatItem.weight`` sits in the same rendered
    line as ``quotes_omitted`` and carries the identical hand-built-injection gap. It is pre-existing
    rather than new, but a one-twin fix is how this class of defect keeps coming back here. A real
    number renders as itself; anything else falls back to the inline escaper rather than going out raw.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return _inline(str(value))
    if isinstance(value, int):
        plain = _plain_int(value)
        if plain is None or abs(plain) > _MAX_RENDERED_NUMBER:
            return _UNRENDERABLE_NUMBER
        return str(plain)
    plain_f = _plain_float(value)
    if plain_f is None:
        return _UNRENDERABLE_NUMBER
    # NaN / ±inf are not weights. `x != x` is the NaN test that does not depend on the object.
    if plain_f != plain_f or plain_f in (float("inf"), float("-inf")):
        return _UNRENDERABLE_NUMBER
    if abs(plain_f) > _MAX_RENDERED_NUMBER:
        return _UNRENDERABLE_NUMBER
    return str(plain_f)


def _cell(text: str) -> str:
    """Untrusted text for a markdown TABLE CELL — `_inline` plus the pipe, which is the load-bearing one.

    A `|` inside a cell ends that cell: the row grows a column, every value after it shifts left, and the
    reader sees a well-formed table containing the WRONG answers. That is strictly worse than a broken
    table, which is why this is escaped rather than stripped.
    """
    return _inline(text).replace("|", "\\|")


def _link(label: str, url: str) -> str:
    """A markdown link, or inert text when the url is absent or its scheme is not http(s).

    Two hazards, both from LLM-derived urls: a `javascript:`/`data:` target becomes a live XSS vector the
    moment the brief is rendered to HTML, and a `)` in the url terminates the markdown link early,
    spilling the remainder into the document as text. Angle-bracket form fixes the second; the scheme
    allowlist fixes the first. ``label`` must already be `_inline`-escaped.
    """
    # `|` percent-encoded in BOTH branches: this helper's output goes into the pricing table's Source
    # cell, so an unescaped pipe in an LLM-derived url corrupts the row exactly as `_cell` exists to
    # prevent — and `_cell` is never applied to a link (it would escape the markdown syntax itself).
    if not url.lower().startswith(_SAFE_URL_SCHEMES):
        return f"{label} (`{_inline(url).replace('|', '%7C')}`)" if url else label
    # BOTH angle brackets percent-encoded: the `<...>` link-destination form is terminated by an
    # unescaped `>` AND is invalid with an unescaped `<`, so encoding only one still lets a crafted url
    # break out of the destination.
    safe = (
        url.translate(_LINE_BREAKS).replace("<", "%3C").replace(">", "%3E").replace("|", "%7C")
    )
    return f"[{label}](<{safe}>)"


def _code_span(text: str, limit: int = 0) -> str:
    r"""Sanitize CALLER text for a markdown CODE SPAN — a different job from :func:`_inline`.

    ⚠️ A code span is NOT an inline position, and using the inline escaper here was wrong in a way the
    reader sees. CommonMark honours neither entity references nor backslash escapes inside `` ` ``, so
    `_inline`'s output rendered LITERALLY: a model label of ``gpt-4 & claude`` displayed as
    ``gpt-4 &amp; claude``, and ``sonnet[v2]`` as ``sonnet\[v2\]``. For a field whose whole purpose is
    tracing a brief back to what produced it, showing a value that is not the value supplied defeats it.

    What a code span actually needs is narrower: nothing may CLOSE it and nothing may end the line.
    Backticks become `'` (the same substitution `_inline` uses) and every one of the ten codepoints
    `str.splitlines()` breaks on collapses to a space. No entity escaping — inside the span there is
    nothing to escape.

    ``limit`` of 0 means DO NOT CLIP. An identifier is not an evidence quote: clipping a 134-character
    `job_id` produced a brief whose job line could not be grepped back to the run it names, which is the
    one thing that field is for.
    """
    out = text.translate(_LINE_BREAKS).replace("`", "'").strip()
    return _clip(out, limit) if limit > 0 else out


def _clip(text: str, limit: int) -> str:
    """Truncate with a VISIBLE marker.

    A silent cut is a correctness problem, not a cosmetic one: an evidence quote clipped mid-sentence can
    invert its meaning (``"does not support bulk export"`` cut early reads as a capability claim), and the
    reader has no way to know text was removed.
    """
    if len(text) <= limit:
        return text
    cut = text[: limit - 1].rstrip()
    # Never end on a trailing backslash. `_inline` has already replaced every literal backslash with a
    # fullwidth `＼`, so the only backslashes left are the escapes it emits (`\[`, `\]`) — always single
    # and always followed by a bracket. A trailing one is therefore always an orphan half-escape, which
    # would escape the ellipsis instead of the bracket it was written for.
    cut = cut.removesuffix("\\")
    # …and never end mid-ENTITY. `_inline` emits `&amp;`/`&lt;`/`&gt;`, and clipping between the `&` and
    # the `;` is not merely cosmetic: **`&lt` without its semicolon is in HTML5's legacy named-reference
    # list**, so a lenient renderer turns the truncated escape back into a literal `<` — re-enabling the
    # character the escaper had just neutralised. Drop any dangling head-of-entity.
    return _PARTIAL_ENTITY.sub("", cut) + "…"


def _state_glyph(state: Any) -> str:
    """A matrix cell's state, or ❓ when it is not a renderable string.

    ``MatrixCell.state`` is typed ``str``, but ``Matrix``/``MatrixCell`` are exported — a consumer can
    hand-build or deserialize one. Rendering the literal text ``"None"`` would read as a real verdict;
    ❓ is the module's own "unknown", which is what an unrenderable state actually means.
    """
    return state if isinstance(state, str) and state else "❓"


@dataclass(frozen=True)
class Us:
    """*Our* product, as the caller describes it — a shipped feature list, a hypothesis, or the category
    to enter. OPTIONAL at the entrypoint: absent (``us=None``) is the greenfield / run-before-``/fabrik-spec``
    mode (category-landscape matrix + category-table-stakes MATCH, Phase B). ``category`` seeds competitor
    discovery; ``features`` seed the us-vs-them alignment."""

    name: str = ""
    category: str = ""
    features: tuple[str, ...] = ()
    positioning: str = ""


#: The provenance tier of a signal — the reliability/legal posture of the source that produced it.
#: ``A`` official/clean feed (Apple RSS, HN Algolia) · ``B`` grey scraper (opt-in, health-gated) ·
#: ``C`` search-excerpt (the ToS-clean default the core ships). Every emitted signal carries its tier so
#: the consumer knows how much to trust it.
Tier = Literal["A", "B", "C"]


@dataclass(frozen=True)
class Signal:
    """One review/demand signal about a competitor: an aspect + sentiment + the verbatim quote that
    grounds it + the source URL + the tier that produced it. ``competitor`` names which rival it is about
    (empty for a category-wide demand signal)."""

    competitor: str
    aspect: str
    sentiment: str  # 'positive' | 'negative' | 'neutral' | 'mixed'
    quote: str
    source_url: str
    tier: Tier
    rating: float | None = None  # a star rating when the source carries one (Apple RSS) — feeds source_weight

    def to_dict(self) -> dict[str, Any]:
        return {
            "competitor": self.competitor,
            "aspect": self.aspect,
            "sentiment": self.sentiment,
            "quote": self.quote,
            "source_url": self.source_url,
            "tier": self.tier,
            "rating": self.rating,
        }


@dataclass
class Dossier:
    """The match-then-beat dossier (Phase-A skeleton). ``competitors`` are the discovered rival cards
    (deep-research's closed card shape); ``review_signal`` is the mined per-competitor signal. ``partial``
    flags any degraded sub-call; ``truncated`` flags money-ceiling exhaustion (whatever completed is
    returned — never overspent, never raised). Phase B folds in the feature matrix + MATCH/BEAT + optional
    blocks."""

    market: str
    product_type: str
    competitors: list[dict[str, Any]] = field(default_factory=list)
    review_signal: list[Signal] = field(default_factory=list)
    # Phase B — the synthesis tail (None/empty until synthesis runs)
    feature_matrix: Matrix | None = None
    match_list: list[MatchItem] = field(default_factory=list)
    beat_list: list[BeatItem] = field(default_factory=list)
    pricing: PricingBlock | None = None  # optional price-wedge stage
    white_space: WhiteSpaceBlock | None = None  # optional white-space stage
    truncated: bool = False
    partial: bool = False
    spend_usd: Decimal = Decimal("0")
    status: str = "ok"  # 'ok' | 'partial' | 'empty'
    #: Exception CLASS NAMES (never messages) of everything that degraded this run, de-duplicated in
    #: first-seen order. This is the SECOND LINE of defence behind the wiring pre-flight, and it exists
    #: because the pre-flight provably cannot catch every mis-wiring: it introspects a signature, so a
    #: `(*a, **k)` wrapper forwarding to a narrow inner — or a `def` where an `async def` belongs — sails
    #: through and then raises inside the never-raise boundary. Without this, the ONLY evidence was a log
    #: line, and a consumer with logs off could not tell a wiring bug from an empty market. A run whose
    #: `degrade_causes` contains `TypeError` is a wiring bug essentially every time.
    degrade_causes: list[str] = field(default_factory=list)
    #: PROVENANCE — who produced this dossier and under what budget posture. All three are OPTIONAL and
    #: caller-supplied: the engine never invents them, because only the caller knows which model it drove
    #: and whether it restricted itself to free legs. They exist because a consumer reported having to
    #: hand-append `job_id`, `model` and free-legs status into every rendered brief to satisfy its own
    #: contract — a manual step on EVERY run, easy to forget, and invisible when forgotten.
    #: ⚠️ `model` is a free-form label (e.g. `claude -p --model sonnet`), NOT a routing key: nothing in
    #: this module dispatches on it. It is recorded so a brief can be traced back to what produced it.
    #: ⚠️ `free_legs_only` is read with `is True` / `is False`, NEVER `is not None` — an earlier draft of
    #: this very comment said `is not None` was correct, which is true for the STRING "no" and would
    #: reintroduce the inverted budget claim the render path was hardened against. Both channels agree:
    #: a non-bool is reported as `None` by `to_dict` and renders nothing.
    job_id: str | None = None
    model: str | None = None
    free_legs_only: bool | None = None  # tri-state ON PURPOSE: None = "the caller did not say"
    #: ELEMENT DROPS the synthesis tail could not report any other way: ``"<site>:<subject>" -> count``.
    #: ⚠️ This exists because `degrade_causes` deliberately holds only fixed CLASS NAMES, so it can say
    #: THAT elements were dropped but never WHICH rival lost them — and one `LlmMeter` is shared across
    #: the whole per-rival loop, so without a per-subject key rival #1 losing two features and rival #3
    #: losing none are byte-identical. A thin matrix row then reads as "nothing found" when it was
    #: actually "we dropped it", which is the exact ambiguity this seam exists to end.
    #: Keys are ``"<site>:<subject>"``. The site is code-controlled. ⚠️ The SUBJECT is not always a
    #: rival name — an earlier version of this docstring said it was, and that was false for two of the
    #: four producers: `beat_theme_collapsed` carries a `Signal.aspect` and `white_space_collapsed` an
    #: LLM-proposed need phrase, both raw model output over scraped text, and both fire on ordinary
    #: synthesis rather than on an edge case. Since this field is persisted, restored and sticky — the
    #: same reasons `degrade_causes` is restricted to fixed class names — the subject is bounded and
    #: newline-flattened where the key is built (`orchestrator._drop_subject`), so no producer can
    #: route unbounded text into permanent storage.
    element_drops: dict[str, int] = field(default_factory=dict)

    def note_degraded(self, exc: BaseException) -> None:
        """Record the CLASS NAME of a degradation. Never the message — it can carry scraped page text or
        an API key echoed by a client library, and this field is returned to the caller and serialized."""
        name = type(exc).__name__
        if name not in self.degrade_causes:
            self.degrade_causes.append(name)

    def to_dict(self) -> dict[str, Any]:
        return {
            "market": self.market,
            "product_type": self.product_type,
            "competitors": _seq(self.competitors),
            # ⚠️ `to_dict()` gets the SAME guards as `to_markdown()`. Hardening only the rendered
            # brief would repeat this phase's recurring miss one level up: `to_dict()` is the
            # machine-readable channel a consumer parses, and it crashed on exactly the inputs the
            # markdown path was just taught to survive.
            "review_signal": [s.to_dict() for s in _seq(self.review_signal) if hasattr(s, "to_dict")],
            "feature_matrix": (
                _obj(self.feature_matrix, "to_dict").to_dict()
                if _obj(self.feature_matrix, "to_dict") is not None
                else None
            ),
            "match_list": [
                {"feature": m.feature, "rivals_having": m.rivals_having, "universal": m.universal}
                for m in _seq(self.match_list)
            ],
            "beat_list": [
                {
                    "theme": b.theme,
                    "weight": b.weight,
                    "source_urls": b.source_urls,
                    "quotes": b.quotes,
                    "quotes_omitted": b.quotes_omitted,
                }
                for b in _seq(self.beat_list)
            ],
            "pricing": (
                _obj(self.pricing, "to_dict").to_dict() if _obj(self.pricing, "to_dict") is not None else None
            ),
            "white_space": (
                _obj(self.white_space, "to_dict").to_dict()
                if _obj(self.white_space, "to_dict") is not None
                else None
            ),
            "truncated": self.truncated,
            "partial": self.partial,
            "spend_usd": str(self.spend_usd),
            "status": self.status,
            "degrade_causes": [str(c) for c in _seq(self.degrade_causes)],
            "element_drops": dict(self.element_drops) if isinstance(self.element_drops, dict) else {},
            # Provenance — always PRESENT (possibly null) so a renderer can emit the field without a
            # signature change and without probing for its existence. `free_legs_only` is tri-state:
            # null means the caller did not say, which is NOT the same as False.
            "job_id": self.job_id,
            "model": self.model,
            # ⚠️ NORMALIZED, not raw. `to_markdown` was hardened against a non-bool inverting the
            # budget claim; `to_dict` was not — and the dict is a KNOWN renderer input (a consumer
            # wrote their own renderer off it). A raw `"no"` here makes their `if d["free_legs_only"]:`
            # print "free legs only" for a run that spent money — the same inversion, through the
            # other channel. The two channels now agree: a non-bool is `None` in both.
            "free_legs_only": self.free_legs_only
            if isinstance(self.free_legs_only, bool)
            else None,
        }

    def to_markdown(self) -> str:
        """The rendered 'match-then-beat' brief — the HUMAN deliverable, and a full rendering of the
        dossier rather than a summary of it.

        **Provenance, stated precisely** (the blanket "every claim carries its quote + source URL" this
        docstring used to open with was not true of the COMPETITORS section it now renders): feature,
        pricing and white-space claims are RE-GROUNDED — the quote must be a verbatim substring of a real
        fetched source and the url comes from that source. Discovery cards are NOT re-grounded, so the
        COMPETITORS section renders the card's own ``source_urls`` and its ``verified`` flag and asks the
        reader to weigh them; BEAT is Tier-C (corroboration-gated, see the README).

        ⚠️ It renders the RIVALS, the feature matrix and the pricing models as well as MATCH/BEAT. It did
        not until 2026-08-26: a consumer measured **404 bytes** on a 12-rival scan whose ``to_dict()``
        payload was 8.9 KB, and wrote their own renderer off the dict. A deliverable that silently omits
        the thing it was commissioned to produce is worse than no deliverable — the reader cannot tell
        "12 rivals, none noteworthy" from "the rivals are in the payload and nobody printed them".

        ``to_dict()`` remains the complete machine-readable form; this is complete for a READER, which
        means it truncates per-item detail (quotes, source lists) rather than dropping whole sections.
        """
        # ⚠️ `str(...)` — `market` is the ONE field this renderer passes through uncoerced, and a
        # non-str value (a consumer building it from a list, a config read) does not raise at
        # entry: the whole run completes and is BILLED, then `to_markdown()` dies on
        # `.translate`. That is the failure this file guards every other field against.
        lines: list[str] = [f"# Competitor dossier — {_inline(str(self.market))}", ""]
        # PROVENANCE LINE — emitted only for the fields the caller actually supplied, so a caller that
        # sets none gets byte-identical output to before this was added. Reported by a consumer who was
        # hand-appending job_id/model/free-legs into every brief to satisfy its own contract: a manual
        # step on every run, and silent when skipped. `free_legs_only` is tri-state, so `is not None`
        # is the correct test — `if self.free_legs_only` would hide an explicit False, which is exactly
        # the case a reader most wants stated (this run COULD have spent and chose not to).
        prov: list[str] = []
        # ⚠️ Guard on the ESCAPED, CLIPPED value — not the raw one. A whitespace-only `job_id` is truthy,
        # strips to "" inside `_inline`, and rendered an EMPTY code span; two of them then paired across
        # the separator and swallowed it (`_job `` · model ``_` reads "job · model", both values gone).
        # Clipped for the reason every other free-text field is: a caller recording a full CLI invocation
        # produced a 100,010-character header line dwarfing the brief it heads.
        for label, raw, limit in (("job", self.job_id, 0), ("model", self.model, 120)):
            safe = _code_span(str(raw), limit) if raw is not None else ""
            if safe:
                prov.append(f"{label} `{safe}`")
        # ⚠️ `is True` / `is False`, NEVER truthiness — the doctrine this same file states below for
        # `verified`, which the first draft of this block failed to apply to its own new field. Drivers
        # assign these post-hoc from YAML/JSON/`os.getenv`, where `"no"` is the natural shape — and
        # `"no"` is TRUTHY, so a truthiness test rendered "free legs only" for a run that spent money.
        # Inverting a budget claim is the one error this line must not make; a non-bool renders NOTHING
        # rather than a guess.
        if self.free_legs_only is True:
            prov.append("free legs only")
        elif self.free_legs_only is False:
            prov.append("paid legs enabled")
        if prov:
            lines += [f"_{' · '.join(prov)}_", ""]
        flags = []
        if self.partial:
            flags.append("partial (some sources degraded)")
        if self.truncated:
            flags.append("truncated (budget ceiling reached)")
        if flags or self.degrade_causes:
            if flags:
                lines.append(f"> ⚠️ {'; '.join(flags)}")
            if _seq(self.degrade_causes):
                # Naming the cause in the BRIEF, not only the logs: "partial" alone is what a consumer
                # could not distinguish from "this market has no competitors".
                causes = ", ".join(f"`{_inline(str(c))}`" for c in _seq(self.degrade_causes))
                lines.append(">")
                lines.append(f"> Degraded by: {causes}. A `TypeError` here is almost always a `deps` "
                             f"wiring bug, not an empty market.")
            lines.append("")
        # `isinstance` guard, not a bare `.get`: a malformed card must not crash the RENDER after the
        # money is already spent. `_competitor_lines` flags it visibly rather than dropping it.
        # `is True`, not truthiness: `verified` is produced by the INJECTED engine, and a JSON/YAML
        # round-trip that yields the STRING "false" is truthy — which would both inflate this count and
        # drop the ❓ *unverified* flag below, on the one field that states evidentiary confidence.
        _competitors = _seq(self.competitors)
        verified = sum(1 for c in _competitors if isinstance(c, dict) and c.get("verified") is True)
        lines.append(
            f"**Competitors found:** {len(_competitors)} ({verified} verified)  ·  "
            # ⚠️ `spend_usd` was the ONE field on this dataclass going out through no sanitizer
            # at all — not `_inline`, not `str()`. `Dossier` is exported and consumer-buildable, and
            # `spend_usd: Decimal` is a HINT, not enforcement: setting it to a string containing
            # newlines injected a full image tag. Pre-existing, surfaced by a sweep rather than by
            # the fix that prompted the sweep — which is the argument for sweeping.
            f"**Signals:** {_count_any(self.review_signal)}  ·  **Spend:** ${_inline(str(self.spend_usd))}"
        )
        lines.append("")
        lines.extend(self._competitor_lines())
        lines.extend(self._matrix_lines())

        if _seq(self.match_list):
            lines.append("## MATCH — table-stakes rivals have")
            for m in _seq(self.match_list):
                star = " ★ universal gap" if m.universal else ""
                rivals = ", ".join(_inline(str(r)) for r in m.rivals_having)
                lines.append(f"- **{_inline(m.feature)}**{star} — {_count_any(m.rivals_having)} rival(s): {rivals}")
            lines.append("")
        if _seq(self.beat_list):
            lines.append("## BEAT — rivals' corroborated weaknesses (your openings)")
            for b in _seq(self.beat_list):
                lines.append(
                    f"- **{_inline(b.theme)}** (weight {_number(b.weight)}, "
                    f"{_count_any(b.source_urls)} sources)"
                )
                for q in b.quotes[:2]:
                    lines.append(f"  - \"{_clip(_inline(str(q)), 300)}\"")
                # ⚠️ TWO DIFFERENT RESIDUALS, and conflating them is what made this line a false
                # promise. `in to_dict()` is only true for quotes the payload actually still holds;
                # `quotes_omitted` were cut by the `[:5]` bound upstream and are in NEITHER channel.
                # Saying "+N more in to_dict()" over a payload that never held them sent readers to
                # look for evidence that no longer exists anywhere.
                in_payload = max(0, len(b.quotes) - 2)
                omitted = _count(b.quotes_omitted)
                if in_payload or omitted:
                    parts = []
                    if in_payload:
                        parts.append(f"+{in_payload} more in `to_dict()`")
                    if omitted:
                        parts.append(f"{omitted} not retained")
                    lines.append(f"  - *({'; '.join(parts)})*")
            lines.append("")
        _pricing = _obj(self.pricing, "wedge")
        if _pricing is not None and (_pricing.wedge or _pricing.models):
            lines.append("## PRICING")
            # The MODELS are the evidence the wedge is derived FROM; rendering only the wedge asked the
            # reader to trust a conclusion whose inputs were in the payload they were not shown.
            if _pricing.models:
                lines.append("")
                lines.append("| Rival | Model | Free tier | Source |")
                lines.append("|---|---|---|---|")
                for pm in _pricing.models:
                    src = _link("link", str(pm.source_url or "")) if pm.source_url else "—"
                    # `free_tier` is a display STRING ("yes"/"no"/"❓"), never a bool — and it is never
                    # empty (`stages.py:88` defaults it to ❓). A truthiness test therefore printed "yes"
                    # on EVERY row, including the rivals the wedge two lines below correctly called
                    # free-tier-less: the table and the wedge contradicted each other in one section, and
                    # the table was the wrong one. Render the value.
                    lines.append(
                        f"| {_cell(str(pm.competitor))} | {_cell(str(pm.model or '')) or '❓'} | "
                        f"{_cell(str(pm.free_tier or '')) or '❓'} | {src} |"
                    )
                lines.append("")
            if _pricing.wedge:
                lines.append("**Wedge:**")
                for w in _pricing.wedge:
                    lines.append(f"- {_inline(str(w))}")
                lines.append("")
        _white_space = _obj(self.white_space, "needs")
        if _white_space is not None and _white_space.needs:
            lines.append("## WHITE SPACE — corroborated unmet demand")
            for n in _white_space.needs:
                # ⚠️ THE SIBLING I MISSED. I fixed `BeatItem.weight` explicitly invoking the
                # sibling-pair rule ("fixing one twin and leaving the other is how this class keeps
                # coming back here") and then left `UnmetNeed.weight` — the same field, on the same
                # kind of exported hand-constructible dataclass, rendered by the same file, twenty
                # lines away. Review found it. Naming a rule is not applying it: the twin has to be
                # SEARCHED FOR, not recalled.
                lines.append(
                    f"- **{_inline(n.need)}** (weight {_number(n.weight)}, "
                    f"{_count_any(n.source_urls)} sources)"
                )
            lines.append("")
        return "\n".join(lines).rstrip() + "\n"

    # ── to_markdown section renderers ────────────────────────────────────────────────────────────────
    #
    # ⚠️ EVERYTHING rendered below is UNTRUSTED. Competitor names, feature names, positioning, evidence,
    # price tiers and every url originate from an LLM reading SCRAPED WEB PAGES — i.e. text an adversary
    # can influence by publishing a page. Two consequences, both proven against this renderer:
    #
    #   * a `|` in a name silently CORRUPTS a markdown table (the header claims one column count, the
    #     separator declares another, and every cell after it shifts into the wrong column — the reader
    #     sees a plausible table with the wrong answers, which is worse than no table);
    #   * a newline in any field escapes its bullet and can forge headings/sections beneath it.
    #
    # So no untrusted value reaches the output un-escaped. `_cell` for table cells, `_inline` for inline
    # text, `_link` for urls.

    def _competitor_lines(self) -> list[str]:
        """The rivals themselves. Unverified ones are RENDERED, flagged ❓ — never dropped: the discovery
        pack ships them deliberately ("Unverifiable candidates ship with verified=false — never dropped"),
        and hiding them here would silently re-impose the filter the pack refuses to apply."""
        if not _seq(self.competitors):
            return []
        # Display names go through the SAME sanitize+de-duplicate pipeline the matrix uses, so all three
        # sections (COMPETITORS / FEATURE MATRIX / MATCH) name a rival identically. Rendering the raw card
        # name here while the matrix showed "Acme (2)" left the reader — and any consumer joining the
        # sections by string off `to_dict()` — unable to tell which rival was which.
        # Imported locally: `synth` imports `dossier`, so a top-level import is a cycle.
        from .synth import _US_COLUMN, _uniquify, key_safe

        # ⚠️ `.strip()` AND `reserved=` — the two guards `build_matrix` applies that this call did not,
        # despite the comment above claiming the SAME pipeline. Both were measured at HEAD:
        #   · no `.strip()`: the orchestrator seeds the matrix from a STRIPPED name, so two scraped
        #     rivals `" Acme "` and `"Acme"` become `Acme` / `Acme (2)` as columns — while here they
        #     stayed two distinct raw strings, collided with neither, and both rendered as the IDENTICAL
        #     heading `### Acme`. The suffixing exists to keep rivals distinguishable; skipping the strip
        #     produced two indistinguishable sections and no way to map either to its column.
        #   · no `reserved=`: a rival literally named `us` is `us (2)` in the matrix and `### us` here —
        #     and with a real `Us` wired the matrix then carries BOTH `us (2)` (the rival) and `us` (our
        #     own column), so the heading names our product and the rival identically.
        # Reserved unconditionally because `build_matrix` reserves unconditionally; matching it only when
        # `us` is set would reintroduce the divergence on exactly the greenfield path.
        display = _uniquify(
            (
                key_safe(str(c.get("name") or "").strip()) if isinstance(c, dict) else ""
                for c in _seq(self.competitors)
            ),
            reserved=(_US_COLUMN,),
        )
        lines = ["## COMPETITORS", ""]
        for display_name, c in zip(display, _seq(self.competitors), strict=True):
            # A card that is not a dict is degenerate input, not a reason to crash a RENDER — the whole
            # module is never-raise, and `to_markdown()` blowing up would take the dossier down after the
            # money was already spent.
            if not isinstance(c, dict):
                lines.extend([f"### {_inline(str(c))} ❓ *malformed card*", ""])
                continue
            name = _inline(display_name) or "❓ unnamed"
            mark = "" if c.get("verified") is True else " ❓ *unverified*"
            lines.append(f"### {_link(name, str(c.get('url') or ''))}{mark}")
            if pos := _inline(str(c.get("positioning") or "")):
                lines.append(f"- *\"{pos}\"*")
            if tier := _inline(str(c.get("price_tier") or "")):
                lines.append(f"- **Price tier:** {tier}")
            presence = c.get("market_presence")
            if isinstance(presence, list) and presence:
                joined = ", ".join(_inline(str(p)) for p in presence[:5])
                more = f" (+{len(presence) - 5} more)" if len(presence) > 5 else ""
                lines.append(f"- **Presence:** {joined}{more}")
            if ev := _inline(str(c.get("evidence") or "")):
                lines.append(f"- **Evidence:** {_clip(ev, 300)}")
            # Discovery evidence is NOT re-grounded (the trust rails cover feature-extraction, pricing
            # and white-space — the sections where this module holds the source text). Rendering the
            # card's own `source_urls` is what keeps this section attributable rather than a bare
            # unattributed claim; without them it was the one rendered claim with no provenance at all.
            srcs = c.get("source_urls")
            if isinstance(srcs, list) and srcs:
                shown = ", ".join(_link(f"[{i + 1}]", str(u)) for i, u in enumerate(srcs[:3]))
                more = f" (+{len(srcs) - 3})" if len(srcs) > 3 else ""
                lines.append(f"- **Sources:** {shown}{more}")
            lines.append("")
        return lines

    def _matrix_lines(self) -> list[str]:
        """The feature matrix as a real markdown table. ``us`` (when present) is rendered LAST so the
        us-vs-them read is a single left-to-right scan ending on our own column."""
        m = _obj(self.feature_matrix, "rows")
        if m is None or not m.rows or not m.columns:
            return []
        # Gate the reorder on `has_us`, NOT on the mere presence of the string "us" in `columns`.
        # `gap_synthesis` already guards this way (`synth.py` `not (matrix.has_us and c == "us")`). On a
        # GREENFIELD run (`us=None`, `has_us=False`) a rival literally NAMED "us" would otherwise be
        # promoted into the final column that this section labels "our own" — presenting a rival's
        # feature states as the caller's.
        if m.has_us and "us" in m.columns:
            cols = [c for c in m.columns if c != "us"] + ["us"]
        else:
            cols = list(m.columns)
        lines = ["## FEATURE MATRIX", ""]
        lines.append("| Feature | " + " | ".join(_cell(c) for c in cols) + " |")
        lines.append("|---" * (len(cols) + 1) + "|")
        for row in m.rows:
            # `MatrixCell.state` is TYPED `str`, but `Matrix`/`MatrixCell` are PUBLIC — a consumer can
            # hand-build or deserialize one with a None/empty state, and a render must not raise on it
            # (proven: `" | ".join` over a None state → TypeError). An unrenderable state degrades to the
            # module's own ❓ rather than the literal text "None", which would read as a real verdict.
            cells = " | ".join(_cell(_state_glyph(m.cell(row, col).state)) for col in cols)
            lines.append(f"| {_cell(row)} | {cells} |")
        lines.append("")
        # Imported HERE, not at module scope: synth imports dossier, so a top-level import is a cycle.
        # Derived rather than hardcoded so the legend cannot drift from the glyphs actually rendered —
        # a hand-written legend claiming "🟡 partial" against a "⚠️" cell is a quiet lie to the reader.
        from .synth import HAS, MISSING, PARTIAL, UNKNOWN

        lines.append(
            f"Legend: {HAS} has · {MISSING} missing · {PARTIAL} partial · {UNKNOWN} unknown/unverified"
        )
        lines.append("")
        return lines
