"""The Commands view — the command catalogue as a searchable list with per-command detail, and the
command x service matrix as its own APG tab (plan 2026-10-17-plan-1, T06).

The catalogue is read live from ``commands/_sources/`` by the collector, so this view carries no
freshness cadence: its stamp is the render time and never goes stale. The pool credits and the
search-API quotas are NOT here (D-176): they live in the Services view.

Cobra check (D-253): the cheapest way to satisfy "the matrix says how many rows did not come from
the rendered corpus" without the outcome is a constant caveat; the count is computed from each
row's ``rendered`` flag and the caveat is absent when every row came from the corpus.
"""

# AFTER-EDIT: docs/workstation/quota-dashboard.md

from __future__ import annotations

import os
from pathlib import Path

from .. import fmt
from ..components import (
    badge,
    card,
    clamp,
    disclosure,
    field,
    fragment,
    freshness,
    group,
    region_state,
    slug,
    table,
    tabs,
)
from ..strings import t
from . import ViewContext, ViewResult

_STAGE_SEVERITY = {"crit": "warning", "stale": "neutral", "cap": "info"}  # fmt.stage_tone's words
_UNRENDERED_SHOWN = 6


def _rendered_root(given: object = None) -> str:
    """The server's ``RENDERED_COMMANDS`` (``data["rendered_root"]``); today's computation only when absent."""
    if given:
        return str(given)
    return os.getenv("QUOTA_DASH_RENDERED_COMMANDS") or str(Path.home() / ".claude" / "commands")


def _text(x: object) -> str:
    return "" if x is None else str(x)


def _natives(natives: object, rule: object) -> str:
    if not natives:
        return t("commands.none")
    parts = []
    for item in natives:
        name, models = (tuple(item) + ((),))[:2] if isinstance(item, (list, tuple)) else (item, ())
        parts.append(f"{name} ({', '.join(map(str, models))})" if models else str(name))
    floor, units = (
        (tuple(rule) + (False, ()))[:2] if isinstance(rule, (list, tuple)) else (False, ())
    )
    units = [str(u) for u in (units or ())]
    count = []
    if floor:
        count.append(t("commands.floor_opus"))
    if units and units[0].startswith("!"):
        count.append(units[0][1:])  # a FIXED floor, not a per-unit rule
    elif units:
        count.append(
            t("commands.per_unit", units=", ".join(units[:3]) + ("…" if len(units) > 3 else ""))
        )
    return f"{' + '.join(count) if count else t('commands.no_rule')} · {', '.join(parts)}"


def _tiers(tiers: object) -> str:
    return " · ".join(map(str, tiers)) if tiers else t("commands.none")


def _row_find(r: dict) -> str:
    return f"{_text(r.get('name'))} {_text(r.get('purpose'))}".strip()


def _stage(stage: object):
    s = _text(stage)
    return badge(
        _STAGE_SEVERITY.get(fmt.stage_tone(s), "info") if s else "neutral", s or t("commands.none")
    )


def _catalogue(rows: list[dict]):
    body, details = [], []
    for i, r in enumerate(rows, 1):
        name = _text(r.get("name"))
        nat = _natives(r.get("natives"), r.get("rule"))
        tie = _tiers(r.get("tiers"))
        body.append(
            [
                i,
                f"/{name}",
                _stage(r.get("stage")),
                clamp(_text(r.get("purpose")) or t("commands.none"), 2),
                clamp(_text(r.get("when")) or t("commands.none"), 2),
                clamp(_text(r.get("skip")) or t("commands.none"), 2),
                _text(r.get("next")) or t("commands.none"),
                nat,
                tie,
            ]
        )
        dtable = table(
            slug(name, "cmd-detail-table"),
            t("commands.detail", name=name),
            [t("commands.col.command"), t("commands.col.purpose")],
            [
                [t("commands.col.purpose"), _text(r.get("purpose")) or t("commands.none")],
                [t("commands.col.when"), _text(r.get("when")) or t("commands.none")],
                [t("commands.col.skip"), _text(r.get("skip")) or t("commands.none")],
                [t("commands.col.next"), _text(r.get("next")) or t("commands.none")],
                [t("commands.col.natives"), nat],
                [t("commands.col.tiers"), tie],
            ],
        )
        details.append(
            disclosure(
                t("commands.detail", name=name),
                dtable,
                id=slug(name, "cmd-detail"),
                data={"f-find": _row_find(r)},
            )
        )
    heads = [
        t("commands.col.n"), t("commands.col.command"), t("commands.col.stage"), t("commands.col.purpose"),
        t("commands.col.when"), t("commands.col.skip"), t("commands.col.next"),
        t("commands.col.natives"), t("commands.col.tiers"),
    ]  # fmt: skip
    return fragment(
        group(
            fragment(
                field(
                    t("commands.find"),
                    name="find",
                    kind="search",
                    id="commands-find",
                    data={"filter": "find"},
                ),
                table(
                    "commands-table",
                    t("commands.table"),
                    heads,
                    body,
                    row_data=[{"f-find": _row_find(r)} for r in rows],
                ),
                disclosure(
                    t("commands.col.natives"),
                    t("commands.natives.help"),
                    id="commands-help-natives",
                ),
                disclosure(
                    t("commands.col.tiers"), t("commands.tiers.help"), id="commands-help-tiers"
                ),
                group(fragment(*details), tag="div"),
            ),
            tag="section",
            data={"filter-group": "commands"},
        ),
    )


def _matrix(rows: list[dict], ext: list[dict], root: object = None):
    n = len(rows)
    unrendered = [_text(r.get("name")) for r in rows if not r.get("rendered")]
    caveat = ""
    if unrendered:
        caveat = " " + t(
            "commands.matrix.caveat",
            k=len(unrendered),
            n=n,
            names=", ".join(unrendered[:_UNRENDERED_SHOWN]),
            more=", …" if len(unrendered) > _UNRENDERED_SHOWN else "",
        )
    intro = (
        t("commands.matrix.intro", rendered=n - len(unrendered), n=n, root=_rendered_root(root))
        + caveat
    )
    keys = [(_text(e.get("key")), _text(e.get("label")), _text(e.get("title"))) for e in ext]
    body = []
    for r in rows:
        used = r.get("services") or ()
        body.append(
            [f"/{_text(r.get('name'))}"]
            + [f"● {t('commands.matrix.dot')}" if k in used else "·" for k, _l, _t in keys]
        )
    body.append(
        [t("commands.matrix.total", n=n)]
        + [str(sum(1 for r in rows if k in (r.get("services") or ()))) for k, _l, _t in keys]
    )
    legend = "; ".join(f"{label}: {title}" for _k, label, title in keys)
    return card(
        t("commands.tab.matrix"),
        fragment(
            clamp(intro, 4),
            table(
                "commands-matrix-table",
                t("commands.matrix.table"),
                [t("commands.matrix.col.command")] + [label for _k, label, _t in keys],
                body,
            ),
            clamp(legend, 2) if legend else None,
        ),
    )


def render(data: dict, ctx: ViewContext) -> ViewResult:
    rows = data.get("commands")
    stamp = freshness(fmt.read_ts(ctx.now), None)  # read live: never stale
    if isinstance(rows, dict) and "error" in rows:
        return ViewResult(
            fragment(
                stamp, region_state("error", t("commands.error", error=rows["error"]), retry=True)
            )
        )
    rows = [r for r in rows if isinstance(r, dict)] if isinstance(rows, list) else []
    if not rows:
        return ViewResult(
            fragment(stamp, region_state("error", t("commands.unreadable", root=_fabrik_root(ctx))))
        )
    ext = data.get("ext_services") if isinstance(data.get("ext_services"), list) else []
    ext = [e for e in ext if isinstance(e, dict)]
    listing = card(
        t("commands.title"),
        fragment(t("commands.intro", n=len(rows)), _catalogue(rows)),
        age=stamp,
    )
    return ViewResult(
        tabs(
            t("commands.tabs"),
            [
                ("commands-list", t("commands.tab.list"), listing),
                (
                    "commands-matrix",
                    t("commands.tab.matrix"),
                    _matrix(rows, ext, data.get("rendered_root")),
                ),
            ],
        )
    )


def _fabrik_root(ctx: ViewContext) -> str:
    return str(ctx.fabrik_root)
