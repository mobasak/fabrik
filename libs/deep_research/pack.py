"""The injected worldview — a :class:`PackData` (immutable) that makes the generic engine research a
specific domain. Everything domain-specific is DATA here: the stage prompts, the card schema, the leg set
(names/caps/args/free-reallocation-target), the fallback query templates, and the brief-field access. Swap
the pack (or its YAML) and the engine researches a different domain with NO engine edit.

Loaded from YAML via :func:`load_pack`. Mirrors the health-probe / visual-brief engine+pack idiom: an
immutable pack passed as a PARAMETER — no plugin registry, no module-global state.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped, unused-ignore]


@dataclass(frozen=True)
class CardField:
    """One field of the closed output-card shape: its name, its coerced type, and a default."""

    name: str
    type: str  # 'str' | 'bool' | 'list'
    default: Any = None


@dataclass(frozen=True)
class LegConfig:
    """One search leg: the name (the key into ResearchDeps.legs/leg_estimates), the per-run call cap,
    whether it is the FREE reallocation target, and which args the engine builds for it."""

    name: str
    cap: int
    is_free: bool = False
    include_market: bool = False
    num_results: int | None = None


@dataclass(frozen=True)
class PackData:
    """The immutable pack. Satisfies the engine's ``Pack`` Protocol structurally."""

    query_plan_prompt: str
    shortlist_prompt: str
    verify_prompt: str
    shortlist_cap: int
    verify_cap: int
    legs: tuple[LegConfig, ...]
    card_schema: tuple[CardField, ...]
    fallback_templates: Mapping[str, tuple[str, ...]]
    brief_keys: tuple[str, ...]
    subject_name_key: str
    demote_rule: tuple[str, str] | None = None  # (gate_field, evidence_field)

    def subject(self, brief: Mapping[str, Any]) -> str:
        """The research subject — the first non-empty of ``brief_keys`` (the engine's ``brief`` is opaque;
        THIS is the only brief-field access, and it lives in the pack)."""
        for key in self.brief_keys:
            value = brief.get(key)
            if value:
                return str(value)
        return ""

    def subject_name(self, brief: Mapping[str, Any]) -> str:
        value = brief.get(self.subject_name_key)
        return str(value) if value else self.subject(brief)

    def fallback_plan(self, brief: Mapping[str, Any], market: str) -> dict[str, list[str]]:
        # a targeted token replace, NOT str.format — a template may contain a literal brace (a `site:`/
        # JSON operator) that .format would choke on (same reason the engine avoids .format for prompts).
        subject = self.subject(brief)
        return {
            leg: [t.replace("{subject}", subject).replace("{market}", market).strip() for t in templates]
            for leg, templates in self.fallback_templates.items()
        }

    def coerce_card(self, raw: Mapping[str, Any]) -> dict[str, Any]:
        """Force the closed card shape from ``card_schema``; apply the optional demote rule (the generic
        form of 'verified requires evidence' — a gate field is set False unless its evidence field is
        non-empty). NEVER raises on a garbage LLM value (a scalar for a list field coerces to [])."""
        card: dict[str, Any] = {}
        for f in self.card_schema:
            value = raw.get(f.name, f.default)
            if f.type == "bool":
                card[f.name] = bool(value)
            elif f.type == "list":
                card[f.name] = [str(x) for x in value] if isinstance(value, list) else []
            else:
                card[f.name] = str(value) if value is not None else ""
        if self.demote_rule is not None:
            gate, evidence = self.demote_rule
            ev = card.get(evidence)
            # empty covers "" (str), [] (list), and any falsy — works whatever the evidence field's type.
            empty = (not ev) or (isinstance(ev, str) and not ev.strip())
            if card.get(gate) and empty:
                card[gate] = False
        return card


class PackError(ValueError):
    """A malformed pack (missing/invalid required keys)."""


def _require(data: Mapping[str, Any], key: str) -> Any:
    if key not in data:
        raise PackError(f"pack is missing required key {key!r}")
    return data[key]


def _pack_int(value: Any, ctx: str) -> int:
    """int() that raises the documented ``PackError`` (not a bare ValueError/TypeError) on a bad value."""
    try:
        return int(value)
    except (ValueError, TypeError) as exc:
        raise PackError(f"{ctx} must be an integer, got {value!r}") from exc


def load_pack(path: str | Path) -> PackData:
    """Load + VALIDATE a pack from YAML → an immutable :class:`PackData`. Fails LOUD (``PackError``) on a
    malformed pack rather than shipping a silent partial one."""
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise PackError("pack YAML must be a mapping at the top level")

    legs_raw = _require(raw, "legs")
    if not isinstance(legs_raw, list) or not legs_raw:
        raise PackError("pack 'legs' must be a non-empty list")
    legs: list[LegConfig] = []
    for entry in legs_raw:
        if not isinstance(entry, dict) or "name" not in entry or "cap" not in entry:
            raise PackError(f"each leg needs 'name' and 'cap': {entry!r}")
        legs.append(
            LegConfig(
                name=str(entry["name"]),
                cap=_pack_int(entry["cap"], f"leg {entry['name']!r} cap"),
                is_free=bool(entry.get("is_free", False)),
                include_market=bool(entry.get("include_market", False)),
                num_results=(
                    _pack_int(entry["num_results"], f"leg {entry['name']!r} num_results")
                    if entry.get("num_results") is not None
                    else None
                ),
            )
        )
    if sum(1 for leg in legs if leg.is_free) != 1:
        raise PackError("exactly ONE leg must be is_free (the reallocation target)")
    leg_names = {leg.name for leg in legs}

    schema_raw = _require(raw, "card_schema")
    if not isinstance(schema_raw, list) or not schema_raw:
        raise PackError("pack 'card_schema' must be a non-empty list")
    card_schema: list[CardField] = []
    for f in schema_raw:
        if not isinstance(f, dict) or "name" not in f or "type" not in f:
            raise PackError(f"each card field needs 'name' and 'type': {f!r}")
        if f["type"] not in ("str", "bool", "list"):
            raise PackError(f"card field 'type' must be str|bool|list, got {f['type']!r}")
        card_schema.append(CardField(name=str(f["name"]), type=str(f["type"]), default=f.get("default")))
    schema_names = {f.name for f in card_schema}

    fb_raw = _require(raw, "fallback_templates")
    if not isinstance(fb_raw, dict):
        raise PackError("pack 'fallback_templates' must be a mapping of leg -> [templates]")
    fallback: dict[str, tuple[str, ...]] = {}
    for leg, tmpls in fb_raw.items():
        if str(leg) not in leg_names:
            raise PackError(f"fallback_templates references unknown leg {leg!r} (legs: {sorted(leg_names)})")
        if not isinstance(tmpls, list):
            raise PackError(f"fallback_templates[{leg!r}] must be a list of query templates, got {tmpls!r}")
        fallback[str(leg)] = tuple(str(t) for t in tmpls)

    demote = _require(raw, "demote_rule") if "demote_rule" in raw else None
    demote_rule: tuple[str, str] | None = None
    if demote is not None:
        if not isinstance(demote, list) or len(demote) != 2:
            raise PackError("pack 'demote_rule' must be a [gate_field, evidence_field] pair")
        demote_rule = (str(demote[0]), str(demote[1]))
        missing = [fld for fld in demote_rule if fld not in schema_names]
        if missing:
            raise PackError(f"demote_rule fields {missing} are not in card_schema {sorted(schema_names)}")

    brief_keys = _require(raw, "brief_keys")
    if not isinstance(brief_keys, list) or not brief_keys:
        raise PackError("pack 'brief_keys' must be a non-empty list")

    return PackData(
        query_plan_prompt=str(_require(raw, "query_plan_prompt")),
        shortlist_prompt=str(_require(raw, "shortlist_prompt")),
        verify_prompt=str(_require(raw, "verify_prompt")),
        shortlist_cap=_pack_int(_require(raw, "shortlist_cap"), "shortlist_cap"),
        verify_cap=_pack_int(_require(raw, "verify_cap"), "verify_cap"),
        legs=tuple(legs),
        card_schema=tuple(card_schema),
        fallback_templates=fallback,
        brief_keys=tuple(str(k) for k in brief_keys),
        subject_name_key=str(_require(raw, "subject_name_key")),
        demote_rule=demote_rule,
    )
