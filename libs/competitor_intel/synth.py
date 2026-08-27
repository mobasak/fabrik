"""The synthesis tail — the genuinely-new core: turn per-rival evidence into a feature matrix + a ranked
MATCH / BEAT gap analysis, with the trust rails wired into every step.

LLM stages (``extract_features`` / ``align_features``) go through :class:`LlmMeter` — a budget gate that
charges the shared orchestrator total per call, skips (→ degrade) when exhausted, and NEVER raises. Pure
stages (``build_matrix`` / ``gap_synthesis``) do trust-gated assembly with no LLM. ``us`` is OPTIONAL:
absent → a rival-vs-rival category landscape + category table-stakes MATCH.
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Final

from .dossier import Signal, Us
from .protocols import SynthLlm
from .trust import CONSTRAIN_TO_SOURCES, UNVERIFIED, corroborated, grounded_source, source_weight

logger = logging.getLogger(__name__)

# cell states
HAS = "✅"
MISSING = "❌"
PARTIAL = "⚠️"
UNKNOWN = UNVERIFIED  # "❓"


@dataclass
class LlmMeter:
    """Budget-gated, never-raising wrapper around the injected synthesis LLM. ``remaining``/``charge`` are
    the shared orchestrator ``_Budget``'s methods (passed as callables so this module stays decoupled)."""

    llm: SynthLlm
    remaining: Callable[[], Decimal]
    charge: Callable[[Decimal], None]
    estimate: Decimal
    degraded: bool = False  # set True when a call FAILED (LLM raised) — distinct from a budget-exhausted skip
    #: Exception CLASS NAMES (never messages) of the failures behind ``degraded``, so the orchestrator can
    #: put them on the Dossier. The synthesis tail is where a ONE-arity mis-wiring actually breaks (it
    #: calls ``llm(prompt)``), so a bare boolean here loses the most diagnostic signal the module has.
    causes: list[str] = field(default_factory=list)

    async def call(self, prompt: str) -> str | None:
        """Return the LLM's text, or None to signal 'skip/degrade' — when the budget is exhausted (before
        spending) or the call fails. Charges the per-call estimate against the shared total. A FAILURE
        (LLM raised) sets ``degraded`` so the orchestrator can flag the dossier partial; a budget-exhausted
        skip does NOT (that is ``truncated``, a different signal)."""
        if self.remaining() <= 0:
            return None
        self.charge(self.estimate)
        try:
            return await self.llm(prompt)
        except Exception as exc:  # noqa: BLE001 — a failed synthesis call degrades, never raises
            # The TYPE only (never the message — it can carry scraped text or a client-echoed key).
            # A wiring bug reads as `cause=TypeError` and is instantly separable from a network blip.
            name = type(exc).__name__
            logger.warning("competitor_intel.synth_llm_degraded cause=%s", name)
            self.degraded = True
            if name not in self.causes:
                self.causes.append(name)
            return None


_FENCE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.IGNORECASE)


def _parse_json(text: str | None) -> Any:
    """Best-effort JSON from an LLM reply (tolerates ```json fences / surrounding prose). None on failure."""
    if not text:
        return None
    body = _FENCE.sub("", text.strip())
    try:
        return json.loads(body)
    except (ValueError, TypeError):
        # last resort: grab the first {...} or [...] block
        m = re.search(r"(\{.*\}|\[.*\])", body, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(1))
            except (ValueError, TypeError):
                return None
        return None


# ── feature extraction ────────────────────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class Feature:
    name: str
    state: str  # HAS / MISSING / PARTIAL / UNKNOWN
    evidence: str  # verbatim quote (grounded) or "" when unverified
    source_url: str  # the REAL url the quote was found in (via grounded_source), "" when unverified
    freshness: str = ""  # ISO date if the extraction supplied one, else ""


@dataclass
class FeatureSet:
    competitor: str
    features: list[Feature] = field(default_factory=list)


async def extract_features(
    competitor: str, *, meter: LlmMeter, sources: Sequence[tuple[str, str]]
) -> FeatureSet:
    """Schema-first per-rival feature extraction from the available ``(text, url)`` sources, quote-grounded.
    The feature's ``source_url`` is the REAL url the quote was found in (via ``grounded_source``), never a
    url the LLM emits. An unverifiable feature (quote not in the sources) is emitted as ``❓`` with no
    evidence/url, never dropped. Degrades to an empty set when the budget is exhausted or the LLM fails."""
    if not sources:
        return FeatureSet(competitor=competitor)
    prompt = (
        f"{CONSTRAIN_TO_SOURCES}\n\n"
        f"Extract the product features of '{competitor}' from the sources. Output ONLY a JSON array, each "
        f'{{"name": .., "state": "has"|"missing"|"partial", "evidence": "<verbatim quote>", '
        f'"date": "<ISO date if the source states one, else empty>"}}.\n\nSOURCES:\n'
        + "\n---\n".join(t for t, _ in sources)
    )
    parsed = _parse_json(await meter.call(prompt))
    if not isinstance(parsed, list):
        return FeatureSet(competitor=competitor)
    _state_map = {"has": HAS, "missing": MISSING, "partial": PARTIAL}
    features: list[Feature] = []
    for item in parsed:
        if not isinstance(item, dict) or not str(item.get("name") or "").strip():
            continue
        evidence = str(item.get("evidence") or "")
        url = grounded_source(evidence, sources)  # the REAL url, or None if ungrounded
        grounded = url is not None
        state = _state_map.get(str(item.get("state") or "").lower(), UNKNOWN)
        features.append(
            Feature(
                name=str(item["name"]).strip(),
                state=state if grounded else UNKNOWN,  # ungrounded → cannot verify
                evidence=evidence if grounded else "",
                source_url=url or "",
                freshness=str(item.get("date") or "") if grounded else "",
            )
        )
    return FeatureSet(competitor=competitor, features=features)


# ── alignment (canonical taxonomy) ──────────────────────────────────────────────────────────────────
@dataclass
class CanonicalTaxonomy:
    canonical: list[str]
    mapping: dict[str, str]  # raw feature name -> canonical name

    def canon(self, raw: str) -> str:
        return self.mapping.get(raw, raw)


def _identity_taxonomy(raw_names: Iterable[str]) -> CanonicalTaxonomy:
    uniq = list(dict.fromkeys(n for n in raw_names if n))
    return CanonicalTaxonomy(canonical=uniq, mapping={n: n for n in uniq})


async def align_features(
    rivals: Sequence[FeatureSet], us: Us | None, *, meter: LlmMeter
) -> CanonicalTaxonomy:
    """Cluster feature names across rivals (+ us) into a canonical taxonomy via lean LLM semantic
    clustering. Degrades to an identity taxonomy (each name its own canonical) when the budget is exhausted
    or the LLM fails — so the matrix still builds, just without synonym merging."""
    raw_names = [f.name for r in rivals for f in r.features]
    if us:
        # stripped + str-guarded, to MATCH build_matrix's `taxonomy.canon(uf.strip())` lookup (a padded or
        # non-str us feature must not desync the two) and to stay never-raise on a bad caller tuple.
        raw_names += [uf.strip() for uf in us.features if isinstance(uf, str) and uf.strip()]
    raw_names = list(dict.fromkeys(n for n in raw_names if n))
    if not raw_names:
        return CanonicalTaxonomy(canonical=[], mapping={})

    prompt = (
        "Cluster these product-feature names into canonical features (merge synonyms like 'SSO' and "
        "'single sign-on'). Output ONLY JSON {\"canonical\": [..], \"mapping\": {\"<raw>\": \"<canonical>\"}}. "
        "Every input name must appear as a key in mapping.\n\nNAMES:\n" + "\n".join(raw_names)
    )
    parsed = _parse_json(await meter.call(prompt))
    if not isinstance(parsed, dict):
        return _identity_taxonomy(raw_names)
    canonical = parsed.get("canonical")
    mapping = parsed.get("mapping")
    if not isinstance(canonical, list) or not isinstance(mapping, dict):
        return _identity_taxonomy(raw_names)
    # every raw name must resolve; fall back to itself if the LLM dropped it
    clean_map = {n: str(mapping.get(n, n)) for n in raw_names}
    # BOTH branches deduped: the `clean_map.values()` fallback (taken when the LLM returns an empty
    # `canonical`) maps several raw names onto one canonical, so an un-deduped fallback rendered the
    # SAME feature as two identical matrix rows and two identical MATCH items.
    canon_list = list(dict.fromkeys(str(c) for c in canonical if c)) or list(dict.fromkeys(clean_map.values()))
    return CanonicalTaxonomy(canonical=canon_list, mapping=clean_map)


# ── matrix ────────────────────────────────────────────────────────────────────────────────────────────
#: The separator joining ``(feature, column)`` into the flat string key ``to_dict()`` emits — U+241F
#: SYMBOL FOR UNIT SEPARATOR. Deliberately a character that cannot occur in a feature or competitor name
#: (unlike ``|`` or ``:``, which routinely do), so the key round-trips unambiguously through JSON.
#:
#: **Exported because guessing it fails QUIETLY.** A consumer that assumes ``"<row>|<col>"`` gets a miss on
#: every lookup, and since a missing cell legitimately means ``❓ UNKNOWN``, the result is a full grid of
#: ❓ that reads as "we learned nothing about this market" rather than "your key is wrong". Build keys with
#: :func:`cell_key`, or split on this constant. (Reported by a consumer, 2026-08-26.)
CELL_KEY_SEP: Final = "␟"

#: The reserved column key for *our* product. Pre-claimed in `build_matrix` so no rival can take it.
_US_COLUMN: Final = "us"


def cell_key(feature: str, column: str) -> str:
    """The flat ``to_dict()['feature_matrix']['cells']`` key for one cell. Use this instead of formatting
    the separator by hand — see :data:`CELL_KEY_SEP` for why a guessed separator fails silently."""
    return f"{feature}{CELL_KEY_SEP}{column}"


def key_safe(name: str) -> str:
    """Strip :data:`CELL_KEY_SEP` out of a feature or competitor name, so :func:`cell_key` is genuinely
    unambiguous.

    ⚠️ This ENFORCES an invariant the README states. Without it the claim was merely a hope: feature names
    come from LLM JSON over scraped text and competitor names come from discovery cards, so a page can
    publish a U+241F and produce ``cell_key("a", "b␟C") == cell_key("a␟b", "C")`` — two distinct cells
    collapsing to ONE in ``to_dict()``, silently losing the other. Applied at ingest (:func:`build_matrix`)
    rather than inside ``cell_key``, so the sanitized name is what appears in ``rows``/``columns`` too and
    a consumer's lookup of the name they can SEE always hits.
    """
    return name.replace(CELL_KEY_SEP, " ")


@dataclass(frozen=True)
class MatrixCell:
    state: str  # HAS / MISSING / PARTIAL / UNKNOWN
    freshness: str = ""  # ISO date if known, else ""


@dataclass
class Matrix:
    columns: list[str]  # competitor names (+ "us" when us is defined)
    rows: list[str]  # canonical feature names
    cells: dict[tuple[str, str], MatrixCell] = field(default_factory=dict)
    has_us: bool = False

    def cell(self, feature: str, column: str) -> MatrixCell:
        return self.cells.get((feature, column), MatrixCell(state=UNKNOWN))

    def to_dict(self) -> dict[str, Any]:
        return {
            "columns": self.columns,
            "rows": self.rows,
            "has_us": self.has_us,
            "cells": {
                cell_key(feat, col): {"state": c.state, "freshness": c.freshness}
                for (feat, col), c in self.cells.items()
            },
        }


def build_matrix(taxonomy: CanonicalTaxonomy, rivals: Sequence[FeatureSet], us: Us | None) -> Matrix:
    """The comparison matrix. With ``us`` → us-vs-them (a ``us`` column of ✅/❌ per canonical feature,
    computed by canonicalizing ``us.features`` through the SAME taxonomy — exact set membership, no fragile
    substring match); without ``us`` → the rival-vs-rival category landscape. Cells default to ``❓`` (a
    rival that never mentioned a feature is unverified, not 'missing')."""
    # `key_safe` at ingest: rows/columns/cells all carry the sanitized name, so `cell_key` is
    # unambiguous and a consumer looking up the name they can SEE in `rows` always hits.
    # Rows are DE-DUPLICATED, not suffixed — see the warning on `_uniquify`. Cells are keyed by
    # `key_safe(taxonomy.canon(...))`, so a suffixed row is unreachable by construction: it renders as an
    # all-❓ phantom while both real features collapse into the first row and become one ★ universal gap.
    rows = list(dict.fromkeys(key_safe(c) for c in taxonomy.canonical))
    # `columns[i]` is the rendered name of `rivals[i]`; the per-rival cell key below uses the SAME entry,
    # so a suffixed duplicate keeps its own cells instead of resolving to the first rival's.
    # `"us"` is reserved BEFORE rivals claim names: it is appended below, and without this a rival
    # literally named `us` produced a duplicate column whose lookup resolved to the us-cell — rendering
    # our ❌ in place of that rival's ✅ and dropping the rival from the matrix entirely.
    columns = _uniquify((key_safe(r.competitor) for r in rivals), reserved=(_US_COLUMN,))
    cells: dict[tuple[str, str], MatrixCell] = {}
    for column, r in zip(columns, rivals, strict=True):
        # a rival may list several raw features mapping to one canonical; strongest state wins.
        best: dict[str, str] = {}
        fresh: dict[str, str] = {}
        for feat in r.features:
            canon = key_safe(taxonomy.canon(feat.name))
            if canon not in rows:
                rows.append(canon)
            prev = best.get(canon, UNKNOWN)
            new_state = _stronger(prev, feat.state)
            if new_state != prev:  # this feat strictly improved the state → ITS freshness wins (set OR clear)
                fresh[canon] = feat.freshness
            best[canon] = new_state
        for canon, state in best.items():
            cells[(canon, column)] = MatrixCell(state=state, freshness=fresh.get(canon, ""))
    has_us = us is not None
    if us is not None:
        # "us" is the reserved us-column key. A rival literally named "us" would fold into it (a silent
        # treat-as-us on a degenerate input — no crash, no money error, no fabricated data).
        columns.append(_US_COLUMN)
        # canonicalize us features through the taxonomy → exact membership (a blank feature is skipped,
        # so it can't mark every cell HAS and silently empty the MATCH list).
        us_canon = {key_safe(taxonomy.canon(uf.strip())) for uf in us.features if isinstance(uf, str) and uf.strip()}
        for canon in rows:
            cells[(canon, _US_COLUMN)] = MatrixCell(state=HAS if canon in us_canon else MISSING)
    return Matrix(columns=columns, rows=rows, cells=cells, has_us=has_us)


_STATE_RANK = {UNKNOWN: 0, MISSING: 1, PARTIAL: 2, HAS: 3}


def _uniquify(names: Iterable[str], *, reserved: Iterable[str] = ()) -> list[str]:
    """De-duplicate a name list by SUFFIXING repeats — never by dropping them.

    Use this ONLY where each position keeps its own identity downstream (the matrix COLUMNS, which are
    zipped 1:1 with ``rivals`` so a suffixed column still keys its own cells). ``reserved`` pre-claims
    names that must not be taken — the ``"us"`` column is appended later and would otherwise collide with
    a rival literally named ``us``, converting that rival's ✅ into our ❌ and dropping its column.

    ⚠️ NOT for the matrix ROWS. A row's cells are keyed by ``key_safe(taxonomy.canon(name))``, which has no
    notion of "the second one" — so suffixing a row produced a PHANTOM row that nothing could ever
    populate, while both real features merged into the first. Rows are de-duplicated instead (see
    :func:`build_matrix`): two canonicals that sanitize to one string are genuinely indistinguishable
    downstream, and the honest rendering of that is one row, not two.
    """
    used: set[str] = set(reserved)
    out: list[str] = []
    for name in names:
        if name not in used:
            used.add(name)
            out.append(name)
            continue
        # The suffix must not collide with a REAL name. Naively appending `(n)` reintroduced the exact
        # duplicate this function removes: `["A", "A", "A (2)"]` produced `["A", "A (2)", "A (2)"]`,
        # because a rival can legitimately be called "A (2)". Advance until the candidate is genuinely
        # unused — and track EVERY emitted name, not just the originals.
        n = 2
        while f"{name} ({n})" in used:
            n += 1
        candidate = f"{name} ({n})"
        used.add(candidate)
        out.append(candidate)
    return out


def _stronger(a: str, b: str) -> str:
    return a if _STATE_RANK.get(a, 0) >= _STATE_RANK.get(b, 0) else b


# ── gap synthesis: MATCH + BEAT ───────────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class MatchItem:
    feature: str
    rivals_having: list[str]
    universal: bool  # ★ ALL rivals have it (highest-leverage table-stakes gap)


@dataclass(frozen=True)
class BeatItem:
    theme: str
    weight: float  # source-weighted, corroboration-gated ranking score
    source_urls: list[str]
    quotes: list[str]


def gap_synthesis(
    matrix: Matrix,
    review_signal: Sequence[Signal],
    us: Us | None,
    *,
    subject_domains: Mapping[str, str] | None = None,
) -> tuple[list[MatchItem], list[BeatItem]]:
    """MATCH: features rivals have that ``us`` lacks (or, ``us``-absent, the category table-stakes most
    rivals share) — flagged ``universal`` when ALL rivals have it. BEAT: rivals' negative-review themes,
    **cross-source-corroborated** and ranked by **source-weighted** frequency — the source-weight discounts
    a self-published source (``subject_domains[competitor]``) and the fake-polluted extreme-rating band
    (``Signal.rating``), trusting the independent 2–4★ band. Pure — no LLM."""
    rival_cols = [c for c in matrix.columns if not (matrix.has_us and c == "us")]
    n_rivals = len(rival_cols) or 1

    match: list[MatchItem] = []
    for feature in matrix.rows:
        having = [c for c in rival_cols if matrix.cell(feature, c).state == HAS]
        if not having:
            continue
        if us is not None:
            # MATCH = a feature rivals have but WE lack (us cell not ✅)
            if matrix.cell(feature, "us").state != HAS:
                match.append(MatchItem(feature=feature, rivals_having=having, universal=len(having) == n_rivals))
        else:
            # greenfield: category table-stakes = a feature the MAJORITY of rivals share
            if len(having) * 2 >= n_rivals:
                match.append(MatchItem(feature=feature, rivals_having=having, universal=len(having) == n_rivals))
    # universal gaps first (highest leverage), then by breadth
    match.sort(key=lambda m: (not m.universal, -len(m.rivals_having)))

    # BEAT: group negative signals by aspect (the theme), corroboration-gate, source-weight rank.
    by_theme: dict[str, list[Signal]] = {}
    for s in review_signal:
        # ⚠️ `.strip().lower()`, matching `orchestrator._signal_key` EXACTLY. The key normalizes with
        # `.strip()`, so `"negative "` and `"negative"` merge into one entry there — and if the survivor
        # kept the stray whitespace, a bare `.lower()` here FILTERED IT OUT, dropping the corroborating
        # source and collapsing the whole BEAT theme below `min_sources=2`. `partial=False`, no cause.
        # A dedupe key and the filter it feeds must normalize identically or the merge silently deletes
        # evidence; matching the field name is not enough (see the key's docstring).
        if (s.sentiment or "").strip().lower() != "negative":
            continue
        aspect = (s.aspect or "").strip().lower()
        if not aspect:
            continue  # no aspect → no coherent theme; don't collapse unrelated complaints into "general"
        by_theme.setdefault(aspect, []).append(s)
    beat: list[BeatItem] = []
    for theme, sigs in by_theme.items():
        # normalize the url ONCE (stripped) so every rail — corroboration, weight, source_urls, quotes —
        # counts the SAME set. A whitespace-only url is not attribution (matches corroborated()'s strip).
        entries = [(s, s.source_url.strip()) for s in sigs]
        urls = [u for _, u in entries if u]
        if not corroborated(urls, min_sources=2):
            continue  # one voice is not a BEAT finding
        # rating + self-published domain feed the weighting so the extreme-band / vendor discounts actually
        # fire (a rating-bearing source e.g. Apple; a Tier-C signal has rating=None → url-marker weighting).
        doms = subject_domains or {}
        weight = sum(
            source_weight(u, rating=s.rating, subject_domain=doms.get(s.competitor.strip())) for s, u in entries if u
        )
        beat.append(
            BeatItem(
                theme=theme,
                weight=round(weight, 4),
                source_urls=sorted(set(urls)),
                # only ATTRIBUTED quotes (a real, non-blank url) — the trust-rail promise that every
                # rendered claim carries its source.
                quotes=[s.quote for s, u in entries if s.quote and u][:5],
            )
        )
    beat.sort(key=lambda b: -b.weight)
    return match, beat
