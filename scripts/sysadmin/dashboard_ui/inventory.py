"""The external-services inventory — one reader and one renderer for the board and the static file
(plan 2026-10-18-plan-1, T02; spec docs/superpowers/specs/2026-10-18-external-services-page-design.md).

``load(conn, *, before_query=None)`` reads the registry through a connection the CALLER owns (it never
connects, commits, rolls back or closes). ``render(rows, *, now, synced_at, classified_at, interactive)``
builds the section from components only, body-only: no page shell, no file, database or environment
read. Every time argument and row time is an epoch float; a value that is not a finite, non-negative
number reads as unknown (``None``), never as an error.

This module imports neither ``registry_db`` nor ``psycopg2`` (the board's process stays stdlib) and
never ``quota_dashboard``.

Cobra check (D-253): the cheapest way to pass "the attention list shows what needs action" without
the outcome is to list everything (or nothing). The rules are the four provider rules and the two
data-source rules of spec § The design item 3, each pinned in both directions (49 h in, 47 h out, the
healthy and the paid-without-credential rows out); a reason with more than ``_NAMED_LIMIT`` rows
collapses to a count that still lists every name, so collapsing never hides a provider.
"""

# AFTER-EDIT: docs/workstation/quota-dashboard.md docs/reference/external-services-registry.md

from __future__ import annotations

import math
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from urllib.parse import urlsplit

from .components import (
    Safe,
    badge,
    card,
    disclosure,
    field,
    fragment,
    freshness,
    group,
    link,
    region_state,
    select,
    slug,
    status_text,
    table,
)
from .strings import t

STALE_AFTER_H = 48  # the chain fetches daily; two missed laps (a revoked key, a renamed vendor field, an outage) is stale
_REGISTRY_CADENCE_S = 86400.0
_NAMED_LIMIT = 5  # a reason with more rows than this collapses into one counted entry
_USED_BY_SHOWN = 3
_UNTRIAGED = "?"
_UNIDENTIFIED = "unidentified"
_RULES = ("stale_credit", "unattributed", "unidentified", "retiring")
_COSTS = {
    "free": "services.inv.cost.free",
    "freemium": "services.inv.cost.freemium",
    "paid": "services.inv.cost.paid",
    "self-host": "services.inv.cost.self_host",
    "?": "services.inv.unknown",
}
_STATUSES = {
    "active": "services.inv.status.active",
    "unidentified": "services.inv.status.unidentified",
    "retired": "services.inv.status.retired",
    "retiring": "services.inv.status.retiring",
    "?": "services.inv.unknown",
}
_FILTER_GROUP = "inventory"
_UNSAFE_URL = re.compile(r"[\x00-\x20\x7f-\x9f\\\s]")  # control, whitespace, backslash
_EDGE_S = (
    253402300799 - 2 * 86400
)  # past this a local-zone conversion can leave year 9999 (zones are within a day)


# ---------------------------------------------------------------- numbers and times
def _epoch(x: object) -> float | None:
    """An epoch float for a finite, non-negative number or a datetime; ``None`` for anything else."""
    if isinstance(x, datetime):
        try:
            x = x.timestamp()
        except (OverflowError, OSError, ValueError):
            return None
    if isinstance(x, bool) or not isinstance(x, (int, float)):
        return None
    try:
        v = float(x)
        if not (math.isfinite(v) and v >= 0):
            return None
        if v > _EDGE_S:  # only the far edge can fail; the check is the formatters' own round-trip
            datetime.fromtimestamp(v, tz=UTC)  # a time no calendar holds cannot be stamped or aged
            datetime.fromtimestamp(v).astimezone()  # nor one the local zone pushes past year 9999
    except (OverflowError, OSError, ValueError):
        return None
    return v + 0.0  # + 0.0: -0.0 is 0, as `_balance` has it


def _balance(x: object) -> float | None:
    """A usable balance or price: finite and not negative. NUMERIC accepts NaN and Infinity and a
    backfilled row bypasses the fetchers' guard, so the reader refuses them (FD7/FE1/FF1)."""
    if x is None or isinstance(x, bool):
        return None
    try:
        v = float(x)
    except (TypeError, ValueError, OverflowError):
        return None
    return v + 0.0 if math.isfinite(v) and v >= 0 else None  # + 0.0: -0.0 is 0


def _plain(v: float) -> str:
    """``v`` as the shortest decimal that round-trips: never scientific notation, never rounded."""
    out = format(Decimal(repr(v)), "f")
    return out.rstrip("0").rstrip(".") if "." in out else out


def _age_h(at: object, now: float) -> float | None:
    ts = _epoch(at)
    return None if ts is None else (now - ts) / 3600


def _credit_stale(balance: object, credit_at: object, now: float) -> bool:
    """Strictly past ``STALE_AFTER_H``; a credit with no usable time, or one in the future, is not stale."""
    if _balance(balance) is None:
        return False
    age = _age_h(credit_at, now)
    return age is not None and age > STALE_AFTER_H


def _source_stale(at: object, now: float) -> bool:
    """A data source (the registry, the classifier) with no usable time, or strictly past 48 h."""
    age = _age_h(at, now)
    return age is None or age > STALE_AFTER_H


def credit_cell(balance: object, unit: object, credit_at: object, now: float) -> str:
    """The balance, flagged with its age once the LAST successful fetch is older than two laps. A
    fetch that fails inserts no snapshot, so without the flag a revoked key and a healthy one were the
    same cell (FB9). ``""`` for a balance that is missing, NaN, Infinity or negative."""
    bal = _balance(balance)
    if bal is None:
        return ""
    text = f"{_plain(bal)} {unit or ''}".strip()
    if _credit_stale(bal, credit_at, now):  # the one definition of stale
        return t("services.inv.credit_stale", text=text, days=f"{_age_h(credit_at, now) / 24:.0f}")
    return text


def _plural(key: str, n: int, **fields: object) -> str:
    """The catalogue's ``.one`` or ``.other`` form of ``key``: the words live in the catalogue."""
    return t(f"{key}.{'one' if n == 1 else 'other'}", n=n, **fields)


def _when(ts: float) -> str:
    try:
        d = datetime.fromtimestamp(ts).astimezone()
    except (OverflowError, OSError, ValueError):
        return t("services.inv.unknown")
    off = d.strftime("%z")
    return f"{d:%Y-%m-%d %H:%M} {off[:3]}:{off[3:]}"


# ---------------------------------------------------------------- the reader
def load(conn, *, before_query: Callable | None = None) -> tuple[list[dict], float | None]:
    """``(rows, synced_at)`` read through ``conn``: the five queries of today plus ``max(last_seen)``.

    ``before_query(cur)`` runs before each query when given (the live read's deadline hook); with none,
    no other SQL runs. Rows are sorted by category, then provider; each keeps its keys (``provider``,
    ``category``, ``cost``, ``url``, ``status``, ``keys``, ``unattributed``, ``projects`` sorted,
    ``account``, ``renews``, ``price``) plus ``balance`` (float or None), ``unit`` and ``credit_at``
    (epoch or None). ``synced_at`` is ``max(api_keys.last_seen)`` as an epoch, or None for no row."""

    def run(cur, sql: str) -> None:
        if before_query is not None:
            before_query(cur)
        cur.execute(sql)

    with conn.cursor() as cur:
        run(cur, "SELECT id, provider, category, cost_tier, url, status FROM services")
        svc = {
            r[0]: {
                "provider": r[1],
                "category": r[2] or "?",
                "cost": r[3] or "?",
                "url": r[4] or "",
                "status": r[5] or "?",
                "keys": 0,
                "unattributed": 0,
                "projects": set(),
                "account": "",
                "balance": None,
                "unit": "",
                "credit_at": None,
                "renews": "",
                "price": "",
            }
            for r in cur.fetchall()
        }
        run(
            cur,
            "SELECT 1 FROM information_schema.columns WHERE table_schema=current_schema() "
            "AND table_name='api_keys' AND column_name='kind'",
        )
        has_kind = cur.fetchone() is not None  # a registry never synced by the new registry_sync
        run(
            cur,
            "SELECT service_id, used_by_projects, account_email, "
            + ("kind" if has_kind else "'credential'")
            + " FROM api_keys ORDER BY service_id, id",  # insertion order: the FIRST email wins
        )
        for sid, projects, email, kind in cur.fetchall():
            s = svc.get(sid)
            if not s:
                continue
            if kind == "credential":  # a code call-site row proves USE, never a key
                s["keys"] += 1
            elif (
                kind == "credential-unattributed"
            ):  # visible on the row, never counted as a key (BM9)
                s["unattributed"] += 1
            s["projects"].update(p for p in projects or [] if p is not None)  # a NULL element
            if email and not s["account"]:
                s["account"] = email
        run(
            cur,
            "SELECT DISTINCT ON (service_id) service_id, balance, unit, fetched_at "
            "FROM credit_snapshots ORDER BY service_id, fetched_at DESC, id DESC",  # a tie-break: two backfilled rows at one timestamp published an arbitrary one (FC4)
        )
        for sid, bal, unit, fetched in cur.fetchall():
            s = svc.get(sid)
            value = _balance(bal)
            if s is not None and value is not None:
                s["balance"], s["unit"], s["credit_at"] = value, unit or "", _epoch(fetched)
        run(
            cur,
            "SELECT DISTINCT ON (service_id) service_id, price, currency, renews_on "
            "FROM subscriptions ORDER BY service_id, id DESC",
        )
        planned: set = set()
        for sid, price, curr, renews in cur.fetchall():
            s = svc.get(sid)
            # the last-added plan WHOLE (highest id — a re-declared plan keeps its id, and the table
            # holds no recency column): never one plan's price beside another's renewal
            if not s or sid in planned:
                continue
            planned.add(sid)
            if renews:
                s["renews"] = str(renews)
            cost = _balance(
                price
            )  # a NaN, Infinity or NEGATIVE price is refused like a balance (FE1/FF1)
            if cost is not None:
                s["price"] = f"{_plain(cost)} {curr or ''}".strip()
        run(cur, "SELECT max(last_seen) FROM api_keys")
        newest = cur.fetchone()  # None (a fake) or (None,) (Postgres over an empty table): no row
        synced_at = _epoch(newest[0]) if newest else None
    rows = sorted(svc.values(), key=lambda r: (r["category"], r["provider"]))
    for r in rows:
        r["projects"] = sorted(r["projects"])
    return rows, synced_at


# ---------------------------------------------------------------- the renderer
@dataclass(slots=True)
class _Row:
    idx: int
    provider: str
    category: str
    cost: str
    url: str
    status: str
    keys: int
    unattributed: int
    projects: list[str]
    account: str
    balance: object
    unit: str
    credit_at: object
    renews: str
    price: str
    credit: str = ""  # credit_cell at render time
    stale: bool = False  # its balance is older than STALE_AFTER_H

    @property
    def find(self) -> str:
        return " ".join([self.provider, *self.projects, self.account])


def _norm(i: int, r: dict, now: float) -> _Row:
    """Every key is read by index, so a row missing one raises ``KeyError`` (the chain suite's guard)."""
    name = r["provider"]
    name = "" if name is None else str(name).strip()
    row = _Row(
        idx=i,
        provider=name or t("services.inv.unnamed"),
        category=str(r["category"] or _UNTRIAGED),
        cost=str(r["cost"] or "?"),
        url=str(r["url"] or ""),
        status=str(r["status"] or "?"),
        keys=int(r["keys"]),
        unattributed=int(r["unattributed"]),
        projects=[str(p) for p in (r["projects"] or [])],
        account=str(r["account"] or ""),
        balance=r["balance"],
        unit=str(r["unit"] or ""),
        credit_at=r["credit_at"],
        renews=str(r["renews"] or ""),
        price=str(r["price"] or ""),
    )
    row.credit = credit_cell(row.balance, row.unit, row.credit_at, now)
    row.stale = _credit_stale(row.balance, row.credit_at, now)
    return row


class _Ids:
    """Distinct, valid element ids (``slug`` of the text, re-slugged with a counter on a collision),
    and the per-render labels every row repeats, read from the catalogue once."""

    def __init__(self) -> None:
        self._seen: set[str] = set()
        self.cost = {tok: t(key) for tok, key in _COSTS.items()}
        self.status = {tok: t(key) for tok, key in _STATUSES.items()}
        self.detail = t("services.inv.detail")

    def make(self, text: str, prefix: str) -> str:
        n, key = 0, text
        while (ident := slug(key, prefix)) in self._seen:
            n += 1
            key = f"{text}\x00{n}"
        self._seen.add(ident)
        return ident


def _name(row: _Row) -> object:
    """The provider, linked or not, by ONE rule over its URL:

    1. whitespace, a control character or a backslash anywhere: never a link, nothing of the URL shown;
    2. else ``urlsplit`` it: if that raises, the scheme is not exactly ``http``/``https`` (as written),
       ``.port`` raises, the authority ends in ``:``, or the host is empty once its dots are
       stripped: never a link, nothing of the URL shown;
    3. else userinfo (``.username``/``.password`` set): never a link; the name and the raw URL with the
       userinfo cut out of its authority, the rest byte for byte (no credential is ever rendered);
    4. else a link only if ``link()`` accepts the whole string."""
    url = row.url
    if _UNSAFE_URL.search(url):
        return row.provider
    try:
        parts = urlsplit(url)
        authority = parts.netloc
        host = parts.hostname
        parts.port  # noqa: B018 — reading it raises ValueError for a malformed or out-of-range port
    except ValueError:
        return row.provider
    if (
        parts.scheme not in ("http", "https")
        or not url.startswith(f"{parts.scheme}://")
        or authority.endswith(":")
        or not (host or "").strip(".")
    ):
        return row.provider
    if parts.username is not None or parts.password is not None:
        start = len(parts.scheme) + 3
        bare = url[:start] + authority.rpartition("@")[2] + url[start + len(authority) :]
        return fragment(row.provider, " ", bare)
    try:
        return link(row.provider, url, new_tab=True)
    except ValueError:
        return row.provider


def _label(known: dict[str, str], token: str) -> str:
    return known.get(token, token)


def _by_provider(rows: list[_Row]) -> list[_Row]:
    return sorted(rows, key=lambda r: (r.provider.casefold(), r.provider, r.idx))


def _reasons(row: _Row, now: float) -> list[str]:
    out = []
    if row.stale:
        out.append("stale_credit")
    if row.unattributed > 0:
        out.append("unattributed")
    if row.status == _UNIDENTIFIED:
        out.append("unidentified")
    if row.status == "retiring":
        out.append("retiring")
    return out


def _li(body: object, data: dict | None = None) -> Safe:
    return group(body, tag="li", data=data)


def _attention(
    rows: list[_Row], now: float, synced_at, classified_at, queue: int, ids: _Ids, interactive: bool
) -> tuple[Safe, int]:
    entries: list[Safe] = []
    if _source_stale(synced_at, now):
        key = "registry_never" if _epoch(synced_at) is None else "registry_stale"
        entries.append(_li(badge("warning", t(f"services.inv.attn.{key}", hours=STALE_AFTER_H))))
    if queue > 0 and _source_stale(classified_at, now):
        key = "classifier_never" if _epoch(classified_at) is None else "classifier_stale"
        entries.append(
            _li(badge("warning", _plural(f"services.inv.attn.{key}", queue, hours=STALE_AFTER_H)))
        )
    by_rule: dict[str, list[_Row]] = {rule: [] for rule in _RULES}
    flagged: set[int] = set()
    for row in rows:
        for rule in _reasons(row, now):
            by_rule[rule].append(row)
            flagged.add(row.idx)
    for rule in _RULES:
        hit = by_rule[rule]
        if len(hit) > _NAMED_LIMIT:
            names = group(fragment(*[_li(r.provider) for r in hit]), tag="ul")
            summary = t(f"services.inv.attn.many.{rule}", n=len(hit), hours=STALE_AFTER_H)
            entries.append(_li(disclosure(summary, names, id=ids.make(rule, "attn"))))
        else:
            for r in hit:
                text = t(f"services.inv.attn.named.{rule}", name=r.provider, hours=STALE_AFTER_H)
                entries.append(_li(badge("warning", text)))
    body = (
        group(fragment(*entries), tag="ul")
        if entries
        else region_state("empty", t("services.inv.attn.none"))
    )
    note = group(t("services.inv.attn.note"), tag="div") if interactive else None
    return card(t("services.inv.attn.title"), fragment(note, body)), len(flagged)


def _detail(row: _Row, ids: _Ids) -> Safe:
    dash = "—"
    lines = [
        t("services.inv.detail.account", value=row.account or dash),
        t("services.inv.detail.price", value=row.price or dash),
        t("services.inv.detail.renews", value=row.renews or dash),
        t("services.inv.detail.projects", value=", ".join(row.projects) or dash),
        t("services.inv.detail.unattributed", n=row.unattributed),
    ]
    return disclosure(
        ids.detail,
        group(fragment(*[_li(x) for x in lines]), tag="ul"),
        id=ids.make(f"{row.category}\x00{row.provider}", "row"),
    )


def _funding(row: _Row, now: float) -> str:
    if row.credit:
        return row.credit
    parts = [row.price] if row.price else []
    if row.renews:
        parts.append(t("services.inv.renews", date=row.renews))
    return " · ".join(parts) or "—"


def _used_by(row: _Row) -> str:
    if not row.projects:
        return "—"
    shown = ", ".join(row.projects[:_USED_BY_SHOWN])
    rest = len(row.projects) - _USED_BY_SHOWN
    return f"{shown} {t('services.inv.more_names', n=rest)}" if rest > 0 else shown


def _item_data(row: _Row) -> dict:
    return {"filter-item": "", "f-find": row.find, "f-cost": row.cost, "f-status": row.status}


def _count_span(shown: int, interactive: bool) -> object:
    if not interactive:
        return None
    return group(
        t("filter.group_count", n=shown, total=shown), tag="span", data={"filter-count": ""}
    )


def _unattributed(row: _Row) -> object:
    return (
        badge("warning", t("services.inv.unattributed", n=row.unattributed))
        if row.unattributed
        else None
    )


def _group_table(
    name: str, display: str, members: list[_Row], now: float, ids: _Ids, interactive: bool
) -> Safe:
    body = []
    for r in members:
        label = _label(ids.status, r.status)
        status = badge("warning", label) if r.status in ("unidentified", "retiring") else label
        keys = fragment(str(r.keys), " ", _unattributed(r)) if r.unattributed else str(r.keys)
        body.append(
            [
                fragment(_name(r), _detail(r, ids)),
                _label(ids.cost, r.cost),
                status,
                keys,
                _funding(r, now),
                _used_by(r),
            ]
        )
    paid = sum(1 for r in members if r.cost == "paid")
    cred = sum(1 for r in members if r.keys > 0)
    heads = [
        t(f"services.inv.col.{c}")
        for c in ("provider", "cost", "status", "keys", "funding", "used_by")
    ]
    grid = table(
        ids.make(name, "tbl"),
        t("services.inv.table", category=display),
        heads,
        body,
        row_data=[_item_data(r) for r in members] if interactive else None,
        align=[None, None, None, "right", None, None],
    )
    summary = fragment(
        display,
        " · ",
        _plural("services.inv.group.counts", len(members), paid=paid, cred=cred),
        " · " if interactive else None,
        _count_span(len(members), interactive),
    )
    return disclosure(
        summary,
        grid,
        id=ids.make(name, "grp"),
        data={"filter-section": ""} if interactive else None,
    )


def _projects_line(row: _Row, ids: _Ids) -> object:
    if not row.projects:
        return t("services.inv.untriaged.none")
    shown = ", ".join(row.projects[:_USED_BY_SHOWN])
    rest = len(row.projects) - _USED_BY_SHOWN
    if rest <= 0:
        return t("services.inv.untriaged.projects", value=shown)
    more = t("services.inv.more_names", n=rest)
    return disclosure(
        t("services.inv.untriaged.projects", value=f"{shown} {more}"),
        t("services.inv.untriaged.projects", value=", ".join(row.projects)),
        id=ids.make(row.provider, "untr"),
    )


def _queue(members: list[_Row], ids: _Ids, interactive: bool) -> Safe:
    items = []
    for r in members:
        items.append(
            _li(
                fragment(
                    _name(r),
                    " · ",
                    _plural("services.inv.untriaged.keys", r.keys),
                    " " if r.unattributed else None,
                    _unattributed(r),
                    " · ",
                    _projects_line(r, ids),
                ),
                _item_data(r) if interactive else None,
            )
        )
    summary = fragment(
        t("services.inv.untriaged.title", n=len(members)),
        " · " if interactive else None,
        _count_span(len(members), interactive),
    )
    return disclosure(
        summary,
        fragment(t("services.inv.untriaged.help"), group(fragment(*items), tag="ul")),
        id=ids.make("untriaged", "queue"),
        data={"filter-section": ""} if interactive else None,
    )


def _filter_bar(total: int) -> Safe:
    costs = [("", t("services.inv.filter.all_costs"))] + [
        (token, t(key)) for token, key in _COSTS.items()
    ]
    statuses = [("", t("services.inv.filter.all_statuses"))] + [
        (token, t(key)) for token, key in _STATUSES.items()
    ]
    return fragment(
        field(
            t("services.inv.filter.find"),
            name="find",
            kind="search",
            id="inventory-find",
            data={"filter": "find"},
        ),
        select(
            t("services.inv.filter.cost"),
            name="cost",
            id="inventory-cost",
            options=costs,
            data={"filter": "cost", "filter-mode": "token"},
        ),
        select(
            t("services.inv.filter.status"),
            name="status",
            id="inventory-status",
            options=statuses,
            data={"filter": "status", "filter-mode": "token"},
        ),
        status_text(t("filter.shown", n=total, total=total), data={"filter-status": ""}),
    )


def _more_counts(rows: list[_Row], ntables: int, now: float, ids: _Ids) -> Safe:
    tracked = stale = 0
    for r in rows:
        if r.stale:
            stale += 1
        elif r.credit:
            tracked += 1
    counts = [
        ("categories", ntables),
        ("projects", len({p for r in rows for p in r.projects})),
        ("credit_tracked", tracked),
        ("credit_stale", stale),
        ("renewals", sum(1 for r in rows if r.renews)),
        ("credentials", sum(1 for r in rows if r.keys > 0)),
        ("unattributed", sum(r.unattributed for r in rows)),
    ]
    grid = table(
        "inventory-more-table",
        t("services.inv.more.table"),
        [t("services.inv.more.col.count"), t("services.inv.more.col.value")],
        [[t(f"services.inv.more.{name}"), n] for name, n in counts],
        row_data=[{"count": name} for name, _ in counts],
        align=[None, "right"],
    )
    return disclosure(t("services.inv.more.title"), grid, id=ids.make("more", "more"))


def _static_stamps(synced_at, now: float) -> Safe:
    """What the static file prints in place of the ticking stamp, beside the heading."""
    ts = _epoch(synced_at)
    synced = (
        t("services.inv.static.synced", when=_when(ts))
        if ts is not None
        else t("services.inv.static.never")
    )
    return group(
        fragment(_li(synced), _li(t("services.inv.static.written", when=_when(now)))), tag="ul"
    )


def _static_legend() -> Safe:
    return group(_li(t("services.inv.static.legend", hours=STALE_AFTER_H)), tag="ul")


def render(
    rows: list[dict],
    *,
    now: float,
    synced_at: float | None,
    classified_at: float | None,
    interactive: bool,
) -> Safe:
    """The inventory section (body-only). ``interactive`` adds the filter bar and its wire for the
    board; without it the section has no control, no button and no script dependency, and prints the
    registry's own date, the snapshot's date and the legend the live stamp would otherwise carry."""
    if not isinstance(interactive, bool):
        raise ValueError(f"render interactive must be True or False, not {interactive!r}")
    if isinstance(now, bool) or not isinstance(now, (int, float)) or not math.isfinite(now):
        raise ValueError(f"now {now!r} is not a finite number")
    now = float(now)
    recs = _by_provider([_norm(i, r, now) for i, r in enumerate(rows)])
    ids = _Ids()
    queue = [r for r in recs if r.category == _UNTRIAGED]
    cats: dict[str, list[_Row]] = {}
    for r in recs:
        if r.category != _UNTRIAGED:
            cats.setdefault(r.category, []).append(r)
    order = sorted((c for c in cats if c != _UNIDENTIFIED), key=lambda c: (c.casefold(), c))
    if _UNIDENTIFIED in cats:
        order.append(_UNIDENTIFIED)

    attention, needing = _attention(
        recs, now, synced_at, classified_at, len(queue), ids, interactive
    )
    paid = sum(1 for r in recs if r.cost in ("paid", "freemium"))
    free = sum(1 for r in recs if r.cost in ("free", "self-host"))
    summary = group(
        fragment(
            _li(t("services.inv.sum.attention", n=needing), {"count": "attention"}),
            _li(t("services.inv.sum.paid", n=paid), {"count": "paid"}),
            _li(t("services.inv.sum.free", n=free), {"count": "free"}),
            _li(t("services.inv.sum.untriaged", n=len(queue)), {"count": "untriaged"}),
            _li(t("services.inv.sum.total", n=len(recs)), {"count": "total"}),
        ),
        tag="ul",
        label=t("services.inv.sum.label"),
    )
    more = _more_counts(recs, len(order), now, ids)

    tables = [
        _group_table(
            c,
            t("services.inv.cat.unidentified") if c == _UNIDENTIFIED else c,
            cats[c],
            now,
            ids,
            interactive,
        )
        for c in order
    ]
    inventory = fragment(*tables) if tables else region_state("empty", t("services.inv.empty"))
    waiting = (
        _queue(queue, ids, interactive)
        if queue
        else region_state("empty", t("services.inv.untriaged.empty"))
    )
    listing = fragment(inventory, waiting)
    if interactive:
        listing = group(
            fragment(_filter_bar(len(recs)), listing),
            tag="div",
            data={"filter-group": _FILTER_GROUP},
        )
    body = fragment(
        group(_plural("services.inv.providers", len(recs)), tag="div"),
        None if interactive else _static_stamps(synced_at, now),
        summary,
        more,
        attention,
        listing,
        None if interactive else _static_legend(),
    )
    age = freshness(_epoch(synced_at), _REGISTRY_CADENCE_S) if interactive else None
    return card(t("services.inv.title"), body, age=age)
