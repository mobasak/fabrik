"""The output shapes — :class:`Signal` (a tier-tagged review/demand signal) and :class:`Dossier` (the
returned match-then-beat document).

Both are defined here in Phase A so ``Signal`` exists before its Phase-A consumer (the reviews stage) and
its Phase-C producers (the adapters import it). Phase B EXTENDS ``Dossier`` (feature matrix, MATCH/BEAT
lists, optional pricing/white-space blocks + ``to_markdown``); the Phase-A skeleton stays valid.
"""

from __future__ import annotations

import operator
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


def _inline(value: object) -> str:
    """⚠️ TAKES `object`, NOT `str`, AND COERCES — this is the CHOKE POINT for the whole class.

    Ten review rounds found the same shape at successively finer grain: wrong-typed CONTAINERS, then
    nested LISTS, then — round 10 — scalar `str` fields (`MatchItem.feature`, `BeatItem.theme`,
    `UnmetNeed.need`) and list ELEMENTS (`Matrix.rows`/`.columns`) that reached these helpers without a
    `str()` wrapper and crashed on `.translate`. Most call sites wrapped `str(...)`; three did not.
    Patching those three would have invited an eleventh round at the next finer grain.
    So the coercion moves HERE, where every rendered value already passes: a call site cannot forget
    what it no longer has to remember.

    Untrusted text for an INLINE position (a bullet, a heading, a quote).

    Collapses the newline family so a field cannot break out of its bullet and forge a section;
    neutralises the backslash+backtick pair so it cannot open a code span that swallows the rest; and
    escapes `[`/`]` so untrusted text cannot construct a LINK or an IMAGE. The image case is the one
    with teeth: a scraped `positioning` of `![](https://tracker.example/p.png)` renders as a tracking
    beacon that fires — revealing the reader's IP and the fact that they are researching this market —
    the moment anyone opens the brief. Links are built by :func:`_link`, never by the text itself.

    Deliberately NOT a full markdown escaper: this is a human brief, and escaping every `*` and `_`
    would make ordinary product copy unreadable for no security gain.
    """
    text = _text(value)
    cleaned = text.translate(_LINE_BREAKS).replace("\\", "＼").replace("`", "'")
    # `<`/`>` BEFORE the bracket escaping: markdown passes raw HTML straight through, so escaping only
    # the `![]()` image form left its strictly more powerful twin untouched — `<img src=https://tracker/…>`
    # fires the same beacon, and `<script>` is stored XSS in any renderer that emits HTML. As entities they
    # stay VISIBLE to the reader (a renderer prints `<script>`) while being inert.
    cleaned = cleaned.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return cleaned.replace("[", "\\[").replace("]", "\\]").strip()


#: Max nesting `to_dict()` will walk. Beyond it the payload is truncated with a visible
#: marker rather than recursing — a consumer's malformed graph must not become our crash.
_MAX_JSON_DEPTH: Final = 40

#: Upper magnitude for any number this module will render. Beyond it the value is not a plausible
#: count or weight, and — the load-bearing half — Python 3.11+ caps int→str at
#: ``sys.get_int_max_str_digits()`` (4300), so rendering a big enough int RAISES instead of printing.
_MAX_RENDERED_NUMBER: Final = 10**12

#: What a number that cannot be rendered honestly becomes. Not ``"0"`` — that would be a false claim
#: in place of an absent one.
_UNRENDERABLE_NUMBER: Final = "n/a"


def _items(value: object, *attrs: str) -> list[Any]:
    """The elements of a consumer-supplied list that actually LOOK like what the renderer expects.

    ⚠️ `_seq` validates the CONTAINER and says nothing about what is inside it. Round 12: elements of
    `match_list`/`beat_list`/`pricing.models`/`white_space.needs` came through `_seq` and then had
    `.universal`/`.theme`/`.source_url`/`.need` read straight off them, so one wrong element raised
    `AttributeError` out of BOTH channels. `_competitor_lines` had guarded its elements with
    `isinstance(c, dict)` since long before — the precedent existed and the sibling lists never got it.

    Duck-typed on the attributes the renderer will touch, matching `_obj`, so a consumer's own
    compatible shape keeps working. An element that does not fit is DROPPED rather than crashing the
    brief — and a drop here is a render-time shape mismatch, not lost research, so it is not a
    `degrade_causes` event.
    """
    return [e for e in _seq(value) if all(_has(e, a) for a in attrs)]


def _card(value: object, key: str) -> Any:
    """A value out of a competitor card — never raising, whatever the card is.

    ⚠️ `competitors` is `list[dict[str, Any]]`, not a dataclass, so round 12's `_truthy`/`_items`
    sweep never reached it: the generator could only replace the whole list or a whole element, never
    one KEY's value inside an otherwise well-formed card. Every `c.get(...) or ""` in
    `_competitor_lines` was therefore a raw `bool()` on consumer data. And `.get` itself is
    overridable — a `dict` SUBCLASS whose `get()` raises defeats the `isinstance(c, dict)` check,
    which is round 13's "presence is not function" lesson arriving one type over.
    """
    if not isinstance(value, dict):
        return None
    try:
        return value.get(key)
    except Exception:  # noqa: BLE001 — the render must never raise after the money is spent
        return None


def _card_text(value: object, key: str) -> str:
    """A card value as renderable text, or ``""`` — the `x.get(k) or ""` idiom, made safe."""
    got = _card(value, key)
    return _text(got) if _truthy(got) else ""


def _has(obj: object, attr: str) -> bool:
    """`hasattr` that CANNOT raise — the guard the duck-typing guards were built on.

    ⚠️ ROUND 13's CLASS, and the one my generated property test could not see because its own
    vocabulary had no word for it. Python's `hasattr()` swallows ONLY `AttributeError`; an object whose
    `__getattr__` — or a `@property` — raises anything else propagates straight through. So EVERY
    duck-type guard in this module (`_obj`, `_items`, and the `hasattr` sweeps in `stages.py`) was
    itself unguarded, and a hostile `pricing`/`feature_matrix`/list element took down both channels
    through the very code that exists to stop that.

    The lesson is about the test, not the code: `_HOSTILE` had archetypes for a raising `__str__`,
    `__bool__`, `__len__`, `__iter__` and `__eq__`, and none for a raising ATTRIBUTE READ — so a
    cross-product that was otherwise exhaustive could not express the failure. A generator is only as
    complete as its vocabulary.
    """
    try:
        return hasattr(obj, attr)
    except Exception:  # noqa: BLE001 — the render must never raise after the money is spent
        return False


def _attr(obj: object, attr: str, default: Any = None) -> Any:
    """`getattr(obj, attr, default)` that cannot raise — `getattr`'s own default only covers
    `AttributeError`, so a raising property defeats it exactly as it defeats `hasattr`."""
    try:
        return getattr(obj, attr, default)
    except Exception:  # noqa: BLE001 — the render must never raise after the money is spent
        return default


def _call_to_dict(obj: object) -> Any:
    """`obj.to_dict()` or ``None`` — because `_has(x, "to_dict")` says the method EXISTS, not that it
    works. Round 13: a well-formed `.to_dict()`-shaped object whose body raises still took down the
    payload after the presence check passed."""
    try:
        return obj.to_dict()  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001 — the render must never raise after the money is spent
        return None


def _truthy(value: object) -> bool:
    """`bool(value)` that CANNOT raise — a truthiness GATE is a render decision, not a read.

    ⚠️ Round 12's class. `if self.partial:`, `if self.truncated:`, `if flags or self.degrade_causes:`,
    `if not m.rows`, `if m.has_us` all ask a consumer-supplied value whether it is true — and
    `__bool__` is as overridable as `__str__`. The coercion helpers protected everything that got
    RENDERED while the decisions about WHETHER to render stayed unguarded, which is the same class one
    step earlier in the pipeline.
    """
    try:
        return bool(value)
    except Exception:  # noqa: BLE001 — the render must never raise after the money is spent
        return False


#: Causes that are ADVISORY — true and worth surfacing, but NOT a degradation. The run completed and
#: nothing was lost. Two consumers need this distinction and only one of them had it: the orchestrator's
#: pair invariant (a flag must never be "explained" by an advisory cause) AND this renderer, which was
#: printing them under a "Degraded by:" banner at `partial=False, status="ok"`. Round 19 taught the
#: first and forgot the second — the mirror of a contract change, unpropagated. It lives HERE rather
#: than in the orchestrator because the renderer is the lower module and cannot import upward.
ADVISORY_CAUSES: Final = frozenset({"RivalNameCollision", "SynthesisRebilled"})


def _text(value: object) -> str:
    """`str(value)` that CANNOT raise — the guard under the guards.

    ⚠️ THE CHOKE POINT ITSELF COULD RAISE, and I had already learned this exact lesson one layer over.
    `_plain_int`/`_plain_float` were rewritten TWICE to stop trusting an overridable dunder, ending at
    `int.__int__(value)` inside a `try` — and then I built the string coercion beside them as a bare
    `str(value)`, which calls a fully overridable `__str__`. A consumer dataclass whose `__str__`
    raises took down BOTH channels, through all six coercion helpers at once, defeating the very
    thesis those helpers exist to establish ("the render must never raise after the money is spent").

    There is no base-class trick here — `str.__str__` needs a real `str` — so the fallback is a
    try/except, and the value becomes a visible marker rather than a crash: a reader sees that a field
    could not be rendered, which is the honest report of an unrenderable field.
    """
    # ⚠️ `type(...) is str`, NOT `isinstance`. `isinstance()` honours an object's `__class__`
    # attribute, so `x.__class__ = str` on a non-str passes the check and is returned AS-IS —
    # skipping the try/except that protects every other branch, and crashing downstream on
    # `.translate`. `json.dumps` is fooled the same way and then fails. Exact-type identity cannot
    # be spoofed, and the only thing it costs is that a genuine `str` SUBCLASS now takes the
    # coercion path, which returns an equal plain `str`.
    if type(value) is str:
        return value
    try:
        return str(value)
    except Exception:  # noqa: BLE001 — the render must never raise after the money is spent
        return f"<unrenderable {type(value).__name__}>"


def _json_number(value: object) -> Any:
    """A JSON-safe NUMBER from a numeric-ish value, or ``None`` if it is not one.

    ⚠️ THIS IS THE REPAIR OF MY OWN ROUND-15 FIX, and it is the mirror rule in miniature: hardening
    against a hostile subclass broke the honest one. Round 15 replaced `int(value)` with the
    base-class dunder `int.__int__(value)` because a spoofed `__class__ = int` made the plain call
    RAISE. Correct against the liar — and `numpy.int64` is NOT a subtype of `int`, so it stopped
    converting and fell through to `str()`. A weight of `np.int64(3)` silently became the JSON STRING
    `"3"`. Trading a crash for silent type corruption is the exact swap this module keeps having to
    un-make.

    `operator.index` is the resolution: CPython requires `__index__` to return a REAL `int` and
    raises otherwise, so an honest duck-typed integer converts losslessly while an object merely
    claiming `__class__ = int` (with no `__index__`) still raises and degrades to text. The same
    logic reads `__float__` off the TYPE rather than the instance, because the instance's `__class__`
    is precisely what cannot be trusted.

    ⚠️ THE MAGNITUDE BOUND BELONGS HERE TOO, and its absence was a separate raise. `_number`/`_count`
    have bounded against `_MAX_RENDERED_NUMBER` all along — Python 3.11+ caps int→str at
    `sys.get_int_max_str_digits()` (4300), so a big enough int makes `json.dumps` raise `ValueError`
    even though nothing is hostile. `Signal(rating=10**5000)` and an `element_drops` count restored
    from a hand-edited checkpoint both reached it. The bound was wired into the markdown helpers and
    never into this one, so the two channels disagreed about what a renderable number is.

    ⚠️ ACCEPTED AND STATED: a `numpy.bool_` serializes as `1`/`0`, not `true`/`false`. The exact-type
    guard `type(value) is bool` that protects a real `bool` does not match it, so it takes the honest
    integer path. Both twins agree, so it is not drift — it is a fidelity loss with no clean generic
    repair: nothing distinguishes a boolean-ish scalar from an `int8` without special-casing a library
    this module does not depend on, and guessing wrong would mis-type real integers. The value is
    preserved and only its JSON type is coarser, which is the milder of the two failures.

    ⚠️ MIRROR, named rather than left to be discovered: a `Decimal` now serializes as a FLOAT where it
    previously became a string, losing precision beyond float's range. `json.dumps` cannot emit a
    `Decimal` at all, so the only choice was which lossy form to pick, and a number-typed field is
    more useful to a consumer than a string that has to be re-parsed.
    """
    if isinstance(value, (str, bytes, bytearray)) or isinstance(value, bool):
        return None
    try:
        # `type: ignore[arg-type]` is the POINT: `value` is deliberately not statically a
        # SupportsIndex, and the try/except is what separates an honest integer from an object
        # merely claiming to be one.
        as_int = operator.index(value)  # type: ignore[arg-type]
    except Exception:  # noqa: BLE001 — not an integer; try the float lane
        pass
    else:
        return as_int if abs(as_int) <= _MAX_RENDERED_NUMBER else _UNRENDERABLE_NUMBER
    to_float = getattr(type(value), "__float__", None)  # the TYPE, never the instance
    if to_float is None:
        return None
    try:
        as_float = to_float(value)
    except Exception:  # noqa: BLE001 — a raising __float__ is not a number
        return None
    if type(as_float) is not float:
        return None
    if as_float != as_float or as_float in (float("inf"), float("-inf")):
        return str(as_float)  # bare NaN/Infinity is not valid JSON
    return as_float if abs(as_float) <= _MAX_RENDERED_NUMBER else _UNRENDERABLE_NUMBER


def _json_safe(value: Any, _depth: int = 0, _seen: frozenset[int] = frozenset()) -> Any:
    """Make a `to_dict()` payload JSON-serializable — the MIRROR of the `_inline` choke point.

    The text helpers coerce everything reaching RENDERED output. `to_dict()` deliberately emits values
    RAW, which is what makes it machine-readable — and also what let a non-serializable element
    through. Measured: `object()`, a `set` and a lambda in `BeatItem.quotes` /
    `MatchItem.rivals_having` / a competitor card each made `json.dumps(d.to_dict())` raise
    `TypeError`. The README promises this method "serializes it all", and serializing is exactly what
    a consumer does with it, so this is a contract break rather than an exotic edge.

    ⚠️ Applied ONCE, over the finished payload, deliberately. Patching the fields a reviewer names is
    what bought this module ten rounds of finer and finer grains; a walk over the whole structure has
    no grains left, and covers fields that do not exist yet.

    Lossless wherever JSON has a type. `set`/`tuple` become lists (JSON has no set); a NON-FINITE
    float becomes its repr, because `json.dumps` emits bare `Infinity`/`NaN` by default and those are
    NOT valid JSON — a consumer with a strict parser would fail on OUR output, not their input; a
    non-str dict key becomes `str(k)`; anything else becomes `str(value)`, visible rather than fatal.
    """
    # ⚠️ CYCLES AND DEPTH. The walk recursed with neither, so a SELF-REFERENTIAL competitor card —
    # `c["self"] = c`, which a hand-rolled deserializer or a buggy upstream stage can produce — sent
    # `to_dict()` into unbounded recursion and `RecursionError` straight out of the never-raise
    # machine-readable channel. A guard that walks a structure must assume the structure is a graph.
    if _depth > _MAX_JSON_DEPTH:
        return f"<truncated at depth {_MAX_JSON_DEPTH}>"
    if isinstance(value, (dict, list, tuple, set, frozenset)):
        # ⚠️ REDUNDANT WITH THE DEPTH BOUND for any reachable input, and kept anyway — a mutation
        # sweep proved the redundancy rather than my assuming it. A cycle has infinite depth, so the
        # bound above always catches it first and deleting this branch kills no test. It stays because
        # the two guards fail differently: the bound truncates at an arbitrary point and says
        # "truncated", while this names the ACTUAL shape ("circular reference") — and if the bound is
        # ever raised or removed, this is the only thing between a self-referential card and a
        # RecursionError out of the never-raise channel.
        if id(value) in _seen:
            return "<circular reference>"
        _seen = _seen | {id(value)}
    # exact-type identity, for the same reason `_text` uses it: `isinstance` honours a lying
    # `__class__`, so a spoofed "str" was returned raw and then broke `json.dumps` — which is
    # fooled by the same attribute and fails one layer later.
    if value is None or type(value) is str or type(value) is bool:
        return value
    # ⚠️ THE SAME SPOOF, THREE BRANCHES LOWER — and this file already had the cure 120 lines down.
    # `str`/`bool` were fixed above with exact-type identity; `int`/`float` and the dict-KEY branch
    # kept `isinstance`, which an object declaring `__class__ = int` passes. It was then returned RAW
    # and `json.dumps` — fooled by the same attribute on the way in, unfooled on the way out — failed
    # with "Object of type int is not JSON serializable". `_plain_int`/`_plain_float` are the guards
    # that already solve this (base-class dunders: a real int subclass converts, a liar raises), so
    # this routes through them instead of inventing a fourth technique.
    as_number = _json_number(value)
    if as_number is not None:
        return as_number
    if isinstance(value, dict):
        return {
            # a dict KEY is the one position `json.dumps` type-checks separately, and it accepts
            # only real str/int/float/bool/None — a spoofed key raises "keys must be str…"
            (k if type(k) is str else _text(k)): _json_safe(v, _depth + 1, _seen)
            for k, v in value.items()
        }
    if isinstance(value, (list, tuple, set, frozenset, range)):
        return [_json_safe(v, _depth + 1, _seen) for v in value]
    return _text(value)


def _seq(value: object) -> list[Any]:
    """A consumer-supplied "list" field, as a real list — or empty. Never a raise.

    ⚠️ THE SIBLING MISS — and I had to be told about it FIVE times before the sweep was complete.
    Round 9 found that this helper guarded the TOP-LEVEL composites (`competitors`, `beat_list`,
    `match_list`, `pricing`, `white_space`) and stopped one field short on the NESTED lists inside
    them: `BeatItem.quotes`, `MatchItem.rivals_having`, `PricingBlock.models`/`.wedge`,
    `WhiteSpaceBlock.needs`, `Matrix.rows`/`.columns` — all on EXPORTED, consumer-constructible types,
    all crashing `to_markdown()`. The sharpest one: `MatchItem.rivals_having`'s COUNT already went
    through `_count_any` while the ITERATION on the SAME LINE did not. Half a line hardened.
    So this sweeps the CLASS instead of the instance. `af2c18f` gave `review_signal`, `rivals_having` and `source_urls` a `len()` guard and
    left `competitors` THREE LINES AWAY unguarded — `d.competitors = None` then crashed
    `to_markdown()` with `TypeError`, and that is not even an adversarial input: an upstream stage
    assigning `None` on an error path produces it. Every list-annotated field on this dataclass is a
    HINT, not enforcement, and the render must never blow up after the money is already spent.
    """
    # ⚠️ RE-ITERABLE containers only, and the exclusions are each for a different reason.
    # `list`/`tuple` were the original accept-set, and it silently rendered NOTHING for a `set`, a
    # `frozenset` or a `range` — legitimate containers a consumer can hold a `list[str]`-annotated
    # field in. Dropping them is data loss, which is the exact class this module exists to prevent, so
    # they are accepted now.
    # `str`/`bytes` stay refused: they are iterable, and accepting them explodes a name into
    # CHARACTERS — the same str-is-a-sequence trap `trust.source_weight` had to be fixed for.
    # ⚠️ A GENERATOR OR ITERATOR IS ALSO REFUSED, and that is deliberate rather than an oversight.
    # These guards are called MORE THAN ONCE on the same field (a truthiness gate, then the loop that
    # renders it), so consuming a one-shot iterator in the gate would leave the render empty — a
    # guard that destroys the data it was added to protect. Refusing is honest; half-rendering is not.
    # ⚠️ REDUNDANT TODAY, KEPT DELIBERATELY — a mutation sweep proved it so rather than my assuming
    # it. Deleting this branch kills no test, because the POSITIVE accept-list below already excludes
    # `str`/`bytes`. It stays because the day someone widens that list to `Iterable` — which is the
    # natural next edit, and would be correct-looking — this line is the only thing standing between a
    # rival name and being rendered one character per entry.
    if isinstance(value, (str, bytes)):
        return []
    # ⚠️ `list(value)` IS ITSELF A CALL INTO THE CONSUMER'S TYPE. CPython pre-sizes the result from
    # `__len__`, so a real `list` SUBCLASS with a raising `__len__` raised from INSIDE this guard —
    # the helper written to make the render never raise was the thing raising. It passes every check
    # above honestly: it IS a list. Nothing about the element types was ever the problem.
    # So the materialization is itself guarded, and a partial read keeps what it got: losing the tail
    # of a hostile container beats losing the whole render.
    if isinstance(value, (list, tuple, set, frozenset, range)):
        try:
            return list(value)
        except Exception:  # noqa: BLE001 — the render must never raise after the money is spent
            out: list[Any] = []
            try:
                for item in value:
                    out.append(item)
            except Exception:  # noqa: BLE001 — keep the prefix we successfully read
                pass
            return out
    return []


def _safe_cell(matrix: Any, row: object, col: object) -> Any:
    """``matrix.cell(row, col).state``, or ``None`` — never a raise.

    The cells mapping is keyed by the row/column VALUES, so an unhashable element (a consumer putting
    a list in `Matrix.rows`) raises `TypeError: unhashable type` inside the lookup itself — upstream
    of every render guard, so the choke-point coercion cannot help. `None` is returned rather than a
    glyph because :func:`_state_glyph` already renders a non-string state as ❓, which is precisely
    what an unaddressable cell means: unknown, exactly like a missing one.
    """
    try:
        return matrix.cell(row, col).state
    except Exception:  # noqa: BLE001 — the render must never raise after the money is spent
        return None


#: The reserved `us` column key, mirrored from `synth._US_COLUMN`. Named here rather than repeating the
#: literal, because `to_markdown` already learned once that gating on the STRING "us" and gating on
#: `has_us` are different questions (a greenfield run with a rival literally named "us").
_US_KEY: Final = "us"


#: :func:`_raw_state` could not read a cell at all. Distinct from a state we read and did not recognise.
_UNREADABLE_CELL: Final = object()


def _raw_state(matrix: object, row: object, col: object) -> Any:
    """A cell's state as the grid holds it, or :data:`_UNREADABLE_CELL`. Never a raise, never coerced.

    ⚠️ RAW, NOT THROUGH `_text`. The version this replaces routed cell states through `_text` before
    testing them — and `_text(None)` is the string ``'None'``, which is neither `UNKNOWN` nor `""`, so an
    UNREADABLE cell read as a DETERMINATE verdict. That inverts the fail direction this file states four
    times ("must never report more certainty than the grid can support"), and the `""` guard written to
    catch it was DEAD: a mutation collapsing `in ("", UNKNOWN)` to `== UNKNOWN` survived the whole suite.
    """
    try:
        cell = matrix.cell(row, col)  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001 — an unaddressable cell is unreadable, never a crash
        return _UNREADABLE_CELL
    if cell is None:
        return _UNREADABLE_CELL
    try:
        return cell.state
    except Exception:  # noqa: BLE001
        return _UNREADABLE_CELL


def _unresolved_rows(matrix: object) -> tuple[int, int, int, int]:
    """``(rows, rival columns, UNRESOLVED rows, rows excluded only because a rival is ⚠️ PARTIAL)``.

    ⚠️ TWO COUNTS, NOT ONE, AND THE SECOND IS NOT A "CASE" — it is a different true statement. A row
    whose only rival verdict is `PARTIAL` IS resolved by the MATCH rule: `gap_synthesis` requires a
    confirmed `HAS`, so it is deterministically EXCLUDED. Calling that "unresolved" would make the
    sentence false. But the exclusion is a judgement the operator may not share — a capability a rival
    ships partially can still be a gap worth closing — and round 19 measured it as a silent one. So it
    is counted and stated separately, and each count is derived rather than classified.

    ⚠️ ONE PREDICATE, DERIVED FROM THE MATCH RULE ITSELF — a deliberate SCOPE decision after six review
    rounds, recorded so the next reader does not "improve" it back into a taxonomy.

    This section began as one sentence and grew into eight case-specific ones. Rounds 15-20 each found a
    defect in it and in nothing else: a branch swallowing a co-occurring truth; the branch added to fix
    that breaking the rule written for it; a clause pinned in one direction only; `PARTIAL` falling
    between two predicates; greenfield unreachable; a CAUSE claimed that the grid cannot know. Several
    of those PUBLISHED FALSE STATEMENTS to the operator, which is worse than saying less.

    The root is that *"which KIND of incomplete is this grid?"* is a DESIGN question. It was never
    specced, and adversarial review is the wrong instrument for designing one — this repo's own rule is
    that a new capability or a design question goes to `/fabrik-spec`, never arrives inside a bugfix. So
    the taxonomy is ROUTED THERE, and what ships is the single claim that can be derived and proven:

        a row is UNRESOLVED when `gap_synthesis` could not decide whether it belongs in MATCH.

    That is checkable directly against the MATCH rule rather than against a story about the grid, and it
    is all the brief needs for an empty MATCH to stop reading as "no gaps found".
    """
    from .synth import HAS, MISSING, PARTIAL, _US_COLUMN

    _DETERMINATE = (HAS, MISSING, PARTIAL)
    rows = _seq(_attr(matrix, "rows", ()))
    raw_cols = _attr(matrix, "columns", None)
    cols = [c for c in _seq(raw_cols) if _text(c) != _US_KEY]
    has_us = _truthy(_attr(matrix, "has_us", False))
    # An unreadable `columns` cannot be enumerated, so nothing here was checked against a rival — fail
    # toward SAYING SO. `_count_any` gives the length a refused-but-Sized container still knows.
    if not cols and (_count_any(raw_cols) or 0) > (1 if has_us else 0):
        return (len(rows), 1, len(rows), 0)

    def _det(value: Any) -> bool:
        # `isinstance` FIRST: `==` on a hostile state calls its `__eq__`, which is overridable.
        return isinstance(value, str) and value in _DETERMINATE

    # ⚠️ A GRID-LEVEL FACT THE ROW-LEVEL PREDICATE STRUCTURALLY CANNOT SEE. `rows` come from
    # `taxonomy.canonical`, which `align_features` seeds with OUR OWN feature names too — so when a rival
    # yields nothing, the grid still HAS rows, every one of them ours, and every one resolves honestly to
    # "we have it, never a gap". MATCH is then correctly empty, and the brief is still misleading:
    # the row set cannot CONTAIN a rival capability we lack, because none was ever extracted. The
    # incompleteness is in the ROWS, not in any row. Measured: `rows=['sso','audit log'] us=✅✅
    # rival cells=0  MATCH=[] partial=False causes=[] status='ok'` and no header at all.
    rival_verdicts = 0
    unresolved = partial_only = 0
    for r in rows:
        if not cols:
            unresolved += 1          # no rival column at all — nothing to compare this row against
            continue
        rival = [_raw_state(matrix, r, c) for c in cols]
        rival_verdicts += sum(1 for v in rival if _det(v))
        any_has = any(isinstance(v, str) and v == HAS for v in rival)
        all_det = all(_det(v) for v in rival)
        if has_us:
            us = _raw_state(matrix, r, _US_COLUMN)
            if _det(us) and us != MISSING:
                continue             # we HAVE it — never a gap, whatever the rival says
            if any_has and _det(us):
                continue             # decided: a rival has it and our verdict is known
            if all_det and not any_has:
                # DECIDED, and excluded — but say so when the exclusion rests on a ⚠️ PARTIAL rather
                # than on a denial, because "a rival partly ships this and you do not" is a finding the
                # MATCH rule structurally cannot carry.
                if _det(us) and us == MISSING and any(
                    isinstance(v, str) and v == PARTIAL for v in rival
                ):
                    partial_only += 1
                continue
            unresolved += 1
        elif not all_det:
            # ⚠️ "ANY unread cell can flip it" IS FALSE FOR A MAJORITY TALLY, and this predicate said it.
            # `_gap_synthesis_inner` admits a greenfield row iff `len(having) * 2 >= n_rivals`. Once more
            # than half the rivals have returned a determinate NON-`HAS` verdict, flipping every unread
            # cell to `HAS` still cannot reach that threshold — the row is DECIDED-OUT, and counting it
            # published "the table-stakes tally could not decide them" about a tally that did decide.
            # Measured: 3 rivals, two ❌ and one ❓ — MATCH is `[]` whether the ❓ is absent or ✅, so the
            # cell is irrelevant to the outcome. An exhaustive oracle over 420 grids put the cost at 12
            # greenfield grids reported loud-but-decided; this closes all 12 and leaves
            # `undecidable_but_silent` at 0.
            _n_has = sum(1 for v in rival if isinstance(v, str) and v == HAS)
            _n_unread = sum(1 for v in rival if not _det(v))
            if (_n_has + _n_unread) * 2 >= len(cols):
                unresolved += 1
    if cols and rows and not rival_verdicts:
        # nothing at all is known about any rival, so no row here could ever have revealed a gap
        unresolved = len(rows)
    return (len(rows), len(cols), unresolved, partial_only)


def _obj(value: object, *attrs: str) -> Any:
    """A consumer-supplied composite field, or ``None`` if it is not the shape the renderer expects.

    Same class as :func:`_seq`, for the Optional composite fields: `feature_matrix`, `pricing`,
    `white_space`. Each was gated only on TRUTHINESS (`if self.pricing and self.pricing.wedge`), so a
    truthy wrong-typed value — a leftover string, a dict from a hand-rolled deserializer — reached the
    attribute access and raised `AttributeError` mid-render. Duck-typing on the one attribute the
    renderer needs keeps a consumer's own compatible shape working, which an `isinstance` check
    against our concrete class would have broken for no gain.
    """
    # ⚠️ EVERY attribute the renderer will touch, not just one. Checking a single attr and then
    # reading others is a guard that validates the door and not the room: a duck-typed `pricing` with
    # `.wedge` but no `.models`, or a `feature_matrix` with `.rows` but no `.columns`/`.cell`, passed
    # the check and crashed two lines later. Review reproduced both.
    return value if all(_has(value, a) for a in attrs) else None


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
        return _inline(value)
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


def _cell(value: object) -> str:
    """⚠️ Takes `object` and coerces — see :func:`_inline` for the choke-point reasoning.

    Untrusted text for a markdown TABLE CELL — `_inline` plus the pipe, which is the load-bearing one.

    A `|` inside a cell ends that cell: the row grows a column, every value after it shifts left, and the
    reader sees a well-formed table containing the WRONG answers. That is strictly worse than a broken
    table, which is why this is escaped rather than stripped.
    """
    text = _text(value)
    return _inline(text).replace("|", "\\|")


def _link(label_value: object, url_value: object) -> str:
    """⚠️ Takes `object` and coerces — see :func:`_inline` for the choke-point reasoning.

    A markdown link, or inert text when the url is absent or its scheme is not http(s).

    Two hazards, both from LLM-derived urls: a `javascript:`/`data:` target becomes a live XSS vector the
    moment the brief is rendered to HTML, and a `)` in the url terminates the markdown link early,
    spilling the remainder into the document as text. Angle-bracket form fixes the second; the scheme
    allowlist fixes the first. ``label`` must already be `_inline`-escaped.
    """
    label = _text(label_value)
    url = _text(url_value)
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


def _code_span(value: object, limit: int = 0) -> str:
    r"""⚠️ Takes `object` and coerces — see :func:`_inline` for the choke-point reasoning.

    Sanitize CALLER text for a markdown CODE SPAN — a different job from :func:`_inline`.

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
    text = _text(value)
    out = text.translate(_LINE_BREAKS).replace("`", "'").strip()
    return _clip(out, limit) if limit > 0 else out


def _clip(value: object, limit: int) -> str:
    """⚠️ Takes `object` and coerces — see :func:`_inline` for the choke-point reasoning.

    Truncate with a VISIBLE marker.

    A silent cut is a correctness problem, not a cosmetic one: an evidence quote clipped mid-sentence can
    invert its meaning (``"does not support bulk export"`` cut early reads as a capability claim), and the
    reader has no way to know text was removed.
    """
    text = _text(value)
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


@dataclass(frozen=True)
class Seed:
    """A vendor the operator PINS into a run — it BYPASSES discovery ranking and joins the roster as a
    first-class member, mined + synthesized like any discovered rival. The mechanism behind the command's
    own trigger, "how do we beat X": discovery ranks *adjacent* rivals and by construction demotes the
    subject you already named, so a named vendor can only reach the roster by being seeded.

    ``positioning``/``evidence`` are optional one-liners the operator may assert; they feed feature
    extraction exactly as a discovered card's own fields do. There is deliberately **no ``verified``
    field** — pinning a vendor asserts "look at this", not "this is a real competitor with quoted
    evidence"; the seed card ships ``verified=False`` and the trust rails still require a real quote to
    render ✅."""

    name: str
    url: str
    positioning: str = ""
    evidence: str = ""


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
            # ⚠️ `Signal` is exported and serializes ITSELF, and round 13's exported-types test did
            # not even list it — only matrix/pricing/white_space. A consumer calling
            # `signal.to_dict()` directly got no `_json_safe` sweep, so one wrong scalar broke the
            # payload. The gap was in the test's PARAMETRIZE LIST, which is its own kind of blind spot.
            "competitor": _json_safe(self.competitor),
            "aspect": _json_safe(self.aspect),
            "sentiment": _json_safe(self.sentiment),
            "quote": _json_safe(self.quote),
            "source_url": _json_safe(self.source_url),
            "tier": _json_safe(self.tier),
            "rating": _json_safe(self.rating),
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
        payload: dict[str, Any] = {
            "market": self.market,
            "product_type": self.product_type,
            "competitors": _seq(self.competitors),
            # ⚠️ `to_dict()` gets the SAME guards as `to_markdown()`. Hardening only the rendered
            # brief would repeat this phase's recurring miss one level up: `to_dict()` is the
            # machine-readable channel a consumer parses, and it crashed on exactly the inputs the
            # markdown path was just taught to survive.
            "review_signal": [_call_to_dict(s) for s in _seq(self.review_signal) if _has(s, "to_dict")],
            "feature_matrix": (
                _call_to_dict(_obj(self.feature_matrix, "to_dict"))
                if _obj(self.feature_matrix, "to_dict") is not None
                else None
            ),
            "match_list": [
                {"feature": m.feature, "rivals_having": _seq(m.rivals_having), "universal": m.universal}
                for m in _items(self.match_list, "feature", "rivals_having", "universal")
            ],
            "beat_list": [
                {
                    "theme": b.theme,
                    "weight": b.weight,
                    "source_urls": _seq(b.source_urls),
                    "quotes": _seq(b.quotes),
                    "quotes_omitted": b.quotes_omitted,
                }
                for b in _items(self.beat_list, "theme", "weight", "source_urls", "quotes", "quotes_omitted")
            ],
            "pricing": (
                _call_to_dict(_obj(self.pricing, "to_dict")) if _obj(self.pricing, "to_dict") is not None else None
            ),
            "white_space": (
                _call_to_dict(_obj(self.white_space, "to_dict"))
                if _obj(self.white_space, "to_dict") is not None
                else None
            ),
            "truncated": self.truncated,
            "partial": self.partial,
            "spend_usd": _text(self.spend_usd),  # a raising __str__ must not break the payload
            "status": self.status,
            "degrade_causes": [_text(c) for c in _seq(self.degrade_causes)],
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
        # the ONE place the machine-readable payload leaves this module
        return _json_safe(payload)  # type: ignore[no-any-return]

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
        lines: list[str] = [f"# Competitor dossier — {_inline(self.market)}", ""]
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
            safe = _code_span(raw, limit) if raw is not None else ""
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
        if _truthy(self.partial):
            flags.append("partial (some sources degraded)")
        if _truthy(self.truncated):
            flags.append("truncated (budget ceiling reached)")
        all_causes = [c for c in _seq(self.degrade_causes)]
        # ⚠️ SPLIT. Every cause used to print under "Degraded by:", so a COMPLETE run carrying only an
        # advisory cause was announced to the reader as degraded. `SynthesisRebilled` fires on every
        # resume, which made that false banner routine rather than rare.
        explanatory = [c for c in all_causes if _text(c) not in ADVISORY_CAUSES]
        advisory = [c for c in all_causes if _text(c) in ADVISORY_CAUSES]
        if flags or all_causes:
            if flags:
                lines.append(f"> ⚠️ {'; '.join(flags)}")
            if explanatory:
                # Naming the cause in the BRIEF, not only the logs: "partial" alone is what a consumer
                # could not distinguish from "this market has no competitors".
                causes = ", ".join(f"`{_inline(c)}`" for c in explanatory)
                lines.append(">")
                # ⚠️ CAUSE-NEUTRAL. This line used to append one cause's diagnosis — "A `TypeError`
                # here is almost always a `deps` wiring bug, not an empty market" — to EVERY
                # explanatory cause. That advice is true for an LLM-wiring failure and misleading for
                # the others: `TaxonomyDegraded` means the budget ran out before synthesis or the model
                # answered badly, and sending the reader to hunt a `deps` bug costs them the actual
                # diagnosis. The cause NAMES are a documented enumeration (README § degrade causes);
                # point at that instead of guessing which one fired.
                lines.append(f"> Degraded by: {causes}. Each name is a class, not a message — see the "
                             f"module README's cause list for what it means and what to do. A "
                             f"`TypeError` cause is almost always a `deps` wiring bug, not an empty "
                             f"market.")
            if advisory:
                notes = ", ".join(f"`{_inline(c)}`" for c in advisory)
                lines.append(">")
                lines.append(f"> Note (not a degradation): {notes}. The run completed and nothing was "
                             f"lost — these flag a repeated charge or an ambiguous attribution.")
            lines.append("")
        # `isinstance` guard, not a bare `.get`: a malformed card must not crash the RENDER after the
        # money is already spent. `_competitor_lines` flags it visibly rather than dropping it.
        # `is True`, not truthiness: `verified` is produced by the INJECTED engine, and a JSON/YAML
        # round-trip that yields the STRING "false" is truthy — which would both inflate this count and
        # drop the ❓ *unverified* flag below, on the one field that states evidentiary confidence.
        _competitors = _seq(self.competitors)
        verified = sum(1 for c in _competitors if _card(c, "verified") is True)
        lines.append(
            f"**Competitors found:** {len(_competitors)} ({verified} verified)  ·  "
            # ⚠️ `spend_usd` was the ONE field on this dataclass going out through no sanitizer
            # at all — not `_inline`, not `str()`. `Dossier` is exported and consumer-buildable, and
            # `spend_usd: Decimal` is a HINT, not enforcement: setting it to a string containing
            # newlines injected a full image tag. Pre-existing, surfaced by a sweep rather than by
            # the fix that prompted the sweep — which is the argument for sweeping.
            f"**Signals:** {_count_any(self.review_signal)}  ·  **Spend:** ${_inline(self.spend_usd)}"
        )
        lines.append("")
        lines.extend(self._competitor_lines())
        lines.extend(self._matrix_lines())

        # ⚠️ AN EMPTY MATCH LIST IS TWO DIFFERENT ANSWERS, and OMITTING the section conflated them.
        # "You are at parity" and "we could not compute this" rendered identically — as nothing at all.
        # The degrade banner at the top does say which, but it sits above the COMPETITORS, MATRIX,
        # pricing and white-space sections, and a reader skimming a long brief to the part they came for
        # never sees it. The breadcrumb belongs WHERE THE ABSENCE IS. Emitted only when the run is
        # actually degraded, so a genuine parity result still renders as before.
        # ⚠️ GATED ON THE TAXONOMY CAUSE, NOT ON `partial` — the first version of this section keyed on
        # `partial` alone and so traded one conflation for its exact MIRROR. `ElementDropped`,
        # `MalformedSignalRestored`, `CheckpointFieldDropped`, `LedgerReset` and `SpendTotalUnreadable`
        # all set `partial` without touching the `us` column, so a run whose comparison WAS computed and
        # whose honest answer is "no gaps" got a banner asserting it "could not be completed". And in
        # greenfield (`has_us=False`) it asserted a us-vs-them comparison the run never attempted — MATCH
        # there means "table-stakes rivals share", not "you lack this".
        # ⚠️ DERIVED, NOT ORDERED — and this is a STRUCTURAL fix, applied after ordering failed four
        # rounds running. The section was six `elif` branches with two conditional clauses, and every
        # round that added one, the next round found an interaction nobody enumerated:
        #   r16  a branch swallowed the all-❓ case          → wrote the rule "two true statements…"
        #   r17  the branch added NEXT broke that rule       → a 2-of-3 failure reported as "1"
        #   r18  the clause fixing THAT was pinned one way   → and its own fix repeated the gap
        #   r19  `PARTIAL` fell between two predicates; greenfield got no branch at all
        # Ordering is the wrong shape for this. There is no single "which case is it" — a grid can be
        # several kinds of incomplete at once, and picking one and implying the rest are false is the
        # defect, not a wording slip. So: compute every TRUE statement about the grid, and print them
        # all. A new kind of incompleteness becomes a new independent fact, not a new place in a
        # sequence where it can be swallowed — and each fact is individually present or absent, so it
        # can be pinned in BOTH directions by construction.
        # ⚠️ TWO STATEMENTS, EACH UNCONDITIONALLY TRUE WHEN EMITTED — see `_unresolved_rows` for why this
        # is one derived count rather than the eight-case taxonomy it replaced, and where that taxonomy
        # went. Both are independently derived, so neither can imply the other is false, and each is
        # individually present or absent, so each is pinnable in BOTH directions.
        _n_rows, _n_rivals, _unresolved, _partial_only = _unresolved_rows(self.feature_matrix)
        _has_us_col = _truthy(_attr(self.feature_matrix, "has_us", False))
        _degraded = "TaxonomyDegraded" in [_text(c) for c in _seq(self.degrade_causes)]
        _facts: list[str] = []
        if _unresolved:
            # ⚠️ GREENFIELD SAYS SOMETHING DIFFERENT, because MATCH MEANS something different there:
            # "table-stakes rivals share", not "you lack this". The derivation was given a greenfield
            # arm and the SENTENCE was not, so a `run(None, …)` — the documented default entry — was
            # told "the grid does not say whether a rival has them AND YOU DO NOT" with no `us` column,
            # no `us` argument, and no comparison ever attempted. That is verbatim the failure the gate
            # comment above claims to have fixed, surviving in the prose after the logic was corrected.
            _facts.append(
                f"{_unresolved} of {_n_rows} feature row(s) could not be RESOLVED either way — the grid "
                + (
                    "does not say whether a rival has them and you do not, so they could not enter "
                    "MATCH. " if _has_us_col else
                    "does not say whether enough rivals have them, so the table-stakes tally could not "
                    "decide them. "
                )
                + "Read the ❓ and ⚠️ cells in the matrix above."
            )
        elif not _n_rows and _n_rivals:
            _facts.append(
                "A rival was discovered but **no feature rows were built at all**, so there was nothing "
                "to compare and nothing was measured about the rival."
            )
        if _partial_only:
            _facts.append(
                f"{_partial_only} feature(s) you do **not** ship are only ⚠️ PARTIALLY supported by a "
                "rival. MATCH lists a feature only when a rival is CONFIRMED to have it, so a partial "
                "capability is excluded by that rule — which is a judgement you may not share."
            )
        if _degraded:
            # ⚠️ SAY ONLY WHAT THE CAUSE GUARANTEES. `TaxonomyDegraded` is now appended for THREE
            # conditions, including the per-NAME `taxonomy.unmapped` that this very change introduced to
            # stop the coarse flag over-claiming. "Synonyms were never merged" is the whole-taxonomy
            # claim and is FALSE for the per-name case — measured on a grid where one rival name of four
            # went unmapped while `single sign-on` and `SSO` merged correctly into `sso`, every cell
            # decided, MATCH legitimately empty: the brief told the operator to distrust a correct
            # parity result, which is the MIRROR of the defect this change exists to fix.
            _facts.append(
                "The feature taxonomy is incomplete (`TaxonomyDegraded` in the banner above): at least "
                "one feature name could not be clustered, so a synonym pair may have stayed separate — "
                "a row may be a duplicate of another, and a rival capability may sit in a row of its own."
            )
        if not _items(self.match_list, "feature", "rivals_having", "universal") and _facts:
            lines.append("## MATCH — not computed")
            lines.append(
                # ⚠️ THE LEAD IS A CLAIM TOO. Fix #2 gave the derived FACTS a greenfield arm and left
                # the sentence that introduces them saying "you have no gaps" — a us-vs-them claim in a
                # mode with no `us` column, where MATCH means "most rivals share this". The greenfield
                # test's forbid-list (`"and you do not"`, `"you lack"`) missed it because it lists
                # PHRASINGS; this is the same claim in words the list does not contain. Fifth instance.
                "_An empty MATCH list is **not evidence that "
                + ("you have no gaps" if _has_us_col else
                   "no capability is table-stakes in this market")
                + "** here. "
                + " ".join(_facts)
                + "_"
            )
            lines.append("")

        if _items(self.match_list, "feature", "rivals_having", "universal"):
            lines.append("## MATCH — table-stakes rivals have")
            for m in _items(self.match_list, "feature", "rivals_having", "universal"):
                star = " ★ universal gap" if _truthy(_attr(m, "universal")) else ""
                rivals = ", ".join(_inline(r) for r in _seq(m.rivals_having))
                lines.append(f"- **{_inline(m.feature)}**{star} — {_count_any(m.rivals_having)} rival(s): {rivals}")
            lines.append("")
        if _items(self.beat_list, "theme", "weight", "source_urls", "quotes"):
            lines.append("## BEAT — rivals' corroborated weaknesses (your openings)")
            for b in _items(self.beat_list, "theme", "weight", "source_urls", "quotes"):
                lines.append(
                    f"- **{_inline(b.theme)}** (weight {_number(b.weight)}, "
                    f"{_count_any(b.source_urls)} sources)"
                )
                for q in _seq(b.quotes)[:2]:
                    lines.append(f"  - \"{_clip(_inline(q), 300)}\"")
                # ⚠️ TWO DIFFERENT RESIDUALS, and conflating them is what made this line a false
                # promise. `in to_dict()` is only true for quotes the payload actually still holds;
                # `quotes_omitted` were cut by the `[:5]` bound upstream and are in NEITHER channel.
                # Saying "+N more in to_dict()" over a payload that never held them sent readers to
                # look for evidence that no longer exists anywhere.
                in_payload = max(0, len(_seq(b.quotes)) - 2)
                omitted = _count(b.quotes_omitted)
                if in_payload or omitted:
                    parts = []
                    if in_payload:
                        parts.append(f"+{in_payload} more in `to_dict()`")
                    if omitted:
                        parts.append(f"{omitted} not retained")
                    lines.append(f"  - *({'; '.join(parts)})*")
            lines.append("")
        _pricing = _obj(self.pricing, "wedge", "models")
        if _pricing is not None and (_seq(_pricing.wedge) or _seq(_pricing.models)):
            lines.append("## PRICING")
            # The MODELS are the evidence the wedge is derived FROM; rendering only the wedge asked the
            # reader to trust a conclusion whose inputs were in the payload they were not shown.
            if _seq(_pricing.models):
                lines.append("")
                lines.append("| Rival | Model | Free tier | Source |")
                lines.append("|---|---|---|---|")
                for pm in _items(_pricing.models, "competitor", "model", "free_tier", "source_url"):
                    src = _link("link", pm.source_url or "") if _truthy(pm.source_url) else "—"
                    # `free_tier` is a display STRING ("yes"/"no"/"❓"), never a bool — and it is never
                    # empty (`stages.py:88` defaults it to ❓). A truthiness test therefore printed "yes"
                    # on EVERY row, including the rivals the wedge two lines below correctly called
                    # free-tier-less: the table and the wedge contradicted each other in one section, and
                    # the table was the wrong one. Render the value.
                    lines.append(
                        # ⚠️ `x or ''` is a TRUTHINESS test, so a raising `__bool__` crashes here
                        # exactly as it did at the other gates round 12 fixed. `_truthy` decides,
                        # `_cell` renders — the two jobs stay separate.
                        f"| {_cell(pm.competitor)} | "
                        f"{(_cell(pm.model) if _truthy(pm.model) else '') or '❓'} | "
                        f"{(_cell(pm.free_tier) if _truthy(pm.free_tier) else '') or '❓'} | {src} |"
                    )
                lines.append("")
            if _seq(_pricing.wedge):
                lines.append("**Wedge:**")
                for w in _seq(_pricing.wedge):
                    lines.append(f"- {_inline(w)}")
                lines.append("")
        _white_space = _obj(self.white_space, "needs")
        if _white_space is not None and _seq(_white_space.needs):
            lines.append("## WHITE SPACE — corroborated unmet demand")
            for n in _items(_white_space.needs, "need", "weight", "source_urls"):
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
                key_safe(_card_text(c, "name").strip())
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
                lines.extend([f"### {_inline(c)} ❓ *malformed card*", ""])
                continue
            name = _inline(display_name) or "❓ unnamed"
            mark = "" if _card(c, "verified") is True else " ❓ *unverified*"
            # A caller-PINNED vendor (seeded into the run) is marked so the reader sees the pin was
            # honored — orthogonal to `verified` (a seed ships verified=False; the pin is not a claim of
            # a real competitor, only that the run looked at it). A fixed token, never untrusted text.
            pin = " 📌 *pinned*" if _card(c, "seeded") is True else ""
            lines.append(f"### {_link(name, _card_text(c, 'url'))}{pin}{mark}")
            if pos := _inline(_card_text(c, "positioning")):
                lines.append(f"- *\"{pos}\"*")
            if tier := _inline(_card_text(c, "price_tier")):
                lines.append(f"- **Price tier:** {tier}")
            presence = _card(c, "market_presence")
            if isinstance(presence, list) and _truthy(presence):
                joined = ", ".join(_inline(p) for p in presence[:5])
                more = f" (+{len(presence) - 5} more)" if len(presence) > 5 else ""
                lines.append(f"- **Presence:** {joined}{more}")
            if ev := _inline(_card_text(c, "evidence")):
                lines.append(f"- **Evidence:** {_clip(ev, 300)}")
            # Discovery evidence is NOT re-grounded (the trust rails cover feature-extraction, pricing
            # and white-space — the sections where this module holds the source text). Rendering the
            # card's own `source_urls` is what keeps this section attributable rather than a bare
            # unattributed claim; without them it was the one rendered claim with no provenance at all.
            srcs = _card(c, "source_urls")
            if isinstance(srcs, list) and _truthy(srcs):
                shown = ", ".join(_link(f"[{i + 1}]", u) for i, u in enumerate(srcs[:3]))
                more = f" (+{len(srcs) - 3})" if len(srcs) > 3 else ""
                lines.append(f"- **Sources:** {shown}{more}")
            lines.append("")
        return lines

    def _matrix_lines(self) -> list[str]:
        """The feature matrix as a real markdown table. ``us`` (when present) is rendered LAST so the
        us-vs-them read is a single left-to-right scan ending on our own column."""
        m = _obj(self.feature_matrix, "rows", "columns", "has_us", "cell")
        if m is None or not _seq(m.rows) or not _seq(m.columns):
            return []
        # Gate the reorder on `has_us`, NOT on the mere presence of the string "us" in `columns`.
        # `gap_synthesis` already guards this way (`synth.py` `not (matrix.has_us and c == "us")`). On a
        # GREENFIELD run (`us=None`, `has_us=False`) a rival literally NAMED "us" would otherwise be
        # promoted into the final column that this section labels "our own" — presenting a rival's
        # feature states as the caller's.
        if _truthy(m.has_us) and "us" in _seq(m.columns):
            cols = [c for c in _seq(m.columns) if c != "us"] + ["us"]
        else:
            cols = list(_seq(m.columns))
        lines = ["## FEATURE MATRIX", ""]
        lines.append("| Feature | " + " | ".join(_cell(c) for c in cols) + " |")
        lines.append("|---" * (len(cols) + 1) + "|")
        for row in _seq(m.rows):
            # `MatrixCell.state` is TYPED `str`, but `Matrix`/`MatrixCell` are PUBLIC — a consumer can
            # hand-build or deserialize one with a None/empty state, and a render must not raise on it
            # (proven: `" | ".join` over a None state → TypeError). An unrenderable state degrades to the
            # module's own ❓ rather than the literal text "None", which would read as a real verdict.
            # ⚠️ GUARDED LOOKUP. An UNHASHABLE row/column element (a consumer putting a list in
            # `Matrix.rows`) raises `TypeError: unhashable type` inside the cells dict lookup — BEFORE
            # any render helper is reached, so the choke-point coercion above cannot save it. A row we
            # cannot look up is exactly what `❓ UNKNOWN` already means for a missing cell, so the
            # honest degrade is the documented default rather than a crash.
            cells = " | ".join(_cell(_state_glyph(_safe_cell(m, row, col))) for col in cols)
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
