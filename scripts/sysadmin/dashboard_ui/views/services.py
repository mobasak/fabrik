"""The Services view — the OpenRouter pool balance (shown once, here), the search-API quotas moved
from Commands (D-176) and the external-services inventory, rendered in place by ``inventory.render`` from
a registry read the board runs in a child process (plan 2026-10-18-plan-1, T04).

Cobra check (D-253): the cheapest way to satisfy "an unconfigured pool says so" without the outcome
is an empty region; ``pool=None`` renders the catalogue's not-configured sentence, and a collector
that failed renders its own error while the other regions still render.
"""

# AFTER-EDIT: docs/workstation/quota-dashboard.md

from __future__ import annotations

import math
import os
from datetime import datetime

from .. import inventory
from ..components import badge, card, fragment, freshness, region_state, slug, table
from ..fmt import read_ts
from ..strings import t
from . import ViewContext, ViewResult

POOL_CADENCE_S = 300.0  # CREDITS_TTL_S
APIS_CADENCE_S = 1800.0  # API_QUOTAS_TTL_S
_PROVIDERS = (("brave", "Brave Search"), ("firecrawl", "Firecrawl"), ("exa", "Exa"))


def _real(x: object) -> float | None:
    if isinstance(x, bool) or not isinstance(x, (int, float)):
        return None
    try:
        return float(x) if math.isfinite(x) else None
    except OverflowError:  # 10**400 is neither a figure nor a float
        return None


def _count(x: object) -> str | None:
    v = _real(x)
    if v is None:
        return None
    return f"{v:,.0f}" if v == int(v) else f"{v:,.2f}"


def _warn_usd(given: object = None) -> float:
    """The server's ``CREDITS_WARN_USD`` (``data["warn_usd"]``); today's env read only when absent."""
    try:
        v = float(given if given is not None else os.getenv("POOL_CREDITS_WARN_USD", "5"))
    except (ValueError, TypeError, OverflowError):
        return 5.0
    return v if math.isfinite(v) else 5.0


def _pool(pool: object, warn_usd: object = None):
    if isinstance(pool, dict) and "error" in pool:
        return region_state(
            "error", t("services.pool.error", error=pool["error"]), retry=True
        ), None
    if not pool or not isinstance(pool, dict):
        return region_state("empty", t("services.pool.unconfigured")), None
    stamp = freshness(read_ts(pool.get("ts")), POOL_CADENCE_S)
    if pool.get("unreadable"):
        return region_state("error", t("services.pool.unreadable", why=pool["unreadable"])), stamp
    remaining = _real(pool.get("remaining"))
    if remaining is None:  # unknown is not zero: never a false EXHAUSTED
        return region_state("error", t("services.pool.unknown")), stamp
    granted = _real(pool.get("granted")) or 0.0
    warn = _warn_usd(warn_usd)
    if remaining <= 0:
        sev, note = "critical", t("services.pool.exhausted")
    elif remaining <= warn:
        sev, note = "warning", t("services.pool.low", warn=f"{warn:,.0f}")
    else:
        sev, note = "ok", ""
    age = (
        t("services.pool.stale", age=f"{_real(pool.get('age_s')) or 0.0:.0f}")
        if pool.get("stale")
        else ""
    )
    line = t(
        "services.pool.line",
        remaining=f"{remaining:,.2f}",
        granted=f"{granted:,.2f}",
        age=age,
        note=note,
    )
    return fragment(badge(sev, line)), stamp


def _renewal(epoch: object, now: float):
    ts = _real(epoch)
    if not ts:
        return "—"
    try:
        when = datetime.fromtimestamp(ts).astimezone().strftime("%d %b")
    except (OverflowError, OSError, ValueError):
        return "—"
    days = (ts - now) / 86400.0
    if days < 0:  # a renewal in the PAST is a stale reading, not a renewal
        return fragment(when + " ", badge("warning", t("services.apis.overdue")))
    return f"{when} ({days:.0f}d)"


def _remaining(q: dict):
    if q.get("unlimited"):
        return t("services.apis.nocap")
    total, rem = q.get("total"), q.get("remaining")
    text = _count(rem) or "—"
    rem, total = _real(rem), _real(total)
    if rem is not None and total is not None and total > 0:
        # a provider can report remaining > total (a plan upgrade) or negative (permitted overage):
        # the count is shown and the percentage dropped, never invented
        if 0 <= rem <= total:
            pct = 100.0 * rem / total
            return badge(
                "critical" if pct < 10 else "warning" if pct < 25 else "neutral",
                f"{text} ({pct:.0f}%)",
            )
        return badge("warning", text)
    return text


def _apis(quotas: object, now: float):
    if isinstance(quotas, dict) and "error" in quotas:
        return region_state(
            "error", t("services.apis.error", error=quotas["error"]), retry=True
        ), None
    if not quotas or not isinstance(quotas, dict):
        return region_state("empty", t("services.apis.empty")), None
    rows = []
    for key, label in _PROVIDERS:
        q = quotas.get(key)
        q = q if isinstance(q, dict) else {}
        state = q.get("state")
        stale = (
            badge("warning", t("services.apis.stale"))
            if q.get("stale") or quotas.get("stale")
            else None
        )
        if state == "ok":
            if q.get("unlimited"):
                plan = t("services.apis.unlimited")
            else:
                total = q.get("total")
                plan = _count(total) or "—"
            extra = f" · {q['per_second']}/s" if q.get("per_second") else ""
            plan = f"{plan} {q.get('unit') or ''}{extra}".strip()
            remaining, renews = _remaining(q), _renewal(q.get("renews_at"), now)
        else:
            why = (
                t(f"services.apis.why.{state}", error=q.get("error", "?"))
                if state in ("unconfigured", "no-headers", "no-data", "error")
                else q.get("why") or t("services.apis.why.unavailable")
                if state == "unavailable"
                else t("services.apis.why.unread")
            )
            plan, remaining, renews = why, "—", "—"
        rows.append([fragment(label, " ", stale), plan, remaining, renews])
    age = _real(quotas.get("age_s"))
    stamp = (
        t("services.apis.stamp_none")
        if age is None
        else t("services.apis.stamp_future")
        if age < 0
        else t("services.apis.stamp_age", min=f"{age / 60:.0f}")
    )
    body = fragment(
        t("services.apis.intro", stamp=stamp, min=f"{APIS_CADENCE_S / 60:.0f}"),
        table(
            "services-apis",
            t("services.apis.table"),
            [
                t("services.apis.col.service"),
                t("services.apis.col.plan"),
                t("services.apis.col.remaining"),
                t("services.apis.col.renews"),
            ],
            rows,
        ),
    )
    return body, freshness(read_ts(quotas.get("ts")), APIS_CADENCE_S)


def _inventory(inv: object, now: float):
    """The external-services section (``inventory.render``, live). A failed or missing read is this
    section's error state in words, with Retry, inside its own titled card; the other cards still render."""
    if not isinstance(inv, dict) or "error" in inv:
        why = inv["error"] if isinstance(inv, dict) else t("services.inv.error.none")
        return card(
            t("services.inv.title"),
            region_state("error", t("services.inv.error", error=why), retry=True),
        )
    return inventory.render(
        inv.get("rows") or [],
        now=now,
        synced_at=inv.get("synced_at"),
        interactive=True,
    )


def render(data: dict, ctx: ViewContext) -> ViewResult:
    now = ctx.now
    pool_body, pool_age = _pool(data.get("pool"), data.get("warn_usd"))
    apis_body, apis_age = _apis(data.get("apis"), now)
    return ViewResult(
        fragment(
            card(t("services.pool.title"), pool_body, age=pool_age, id=slug("pool", "services")),
            card(t("services.apis.title"), apis_body, age=apis_age, id=slug("apis", "services")),
            _inventory(data.get("inventory"), now),
        )
    )
