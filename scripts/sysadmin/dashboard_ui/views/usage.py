"""The Usage view — the tier-weighted subscription spend and the daily token calendar (plan
2026-10-17-plan-1, T06). It carries every datum the old `_spend_panel` showed, as real tables: the
tier table, the reconciliation, the priced-against sentence, the unclassified-token warning and one
table per month. It reads the cost sidecar from ``data["spend"]`` and never recomputes.

Cobra check (D-253): the cheapest way to satisfy "every datum survives" without the outcome is a view
that renders the headline and drops the per-day rows; the tests assert the day rows, the per-tier
split and the fee note by text. The unclassified warning is rendered even when the tier table is
empty, because tokens no tier claims are exactly what empties it.
"""

# AFTER-EDIT: docs/workstation/quota-dashboard.md

from __future__ import annotations

import calendar
import datetime as dt
import math
from datetime import datetime

from ..components import badge, card, fragment, freshness, region_state, slug, table
from ..fmt import read_ts
from ..strings import t
from . import ViewContext, ViewResult

CADENCE_S = 86400.0  # the sidecar is rebuilt by the 06:00 cron


def _num(x: object) -> float:
    if isinstance(x, bool) or not isinstance(x, (int, float)):
        return 0.0
    try:
        return float(x) if math.isfinite(x) else 0.0  # NaN and inf are not figures
    except OverflowError:  # 10**400 is neither a figure nor a float
        return 0.0


def _built_ts(built: object) -> float | None:
    try:
        return datetime.fromisoformat(str(built)).timestamp()
    except (TypeError, ValueError, OverflowError, OSError):
        return None


def _unclassified(p: dict):
    unc = p.get("unweighted")
    if not isinstance(unc, dict):
        return None
    total = sum(_num(v) for v in unc.values())
    tok = int(total) if math.isfinite(total) else 0  # two huge finite terms can still sum to inf
    if not tok:
        return None
    return card(
        t("usage.unclassified_title"),
        t("usage.unclassified", tokens=f"{tok:,}", names=", ".join(sorted(map(str, unc)))),
        badge=badge("critical", t("sev.critical")),
    )


def _fee_note(p: dict, spend: float) -> str:
    """The priced-against sentence; a window or fee it cannot derive drops the breakdown, keeps the number."""
    try:
        ws = dt.date.fromisoformat(str(p.get("window_start")))
        we = dt.date.fromisoformat(str(p.get("window_end")))
        fees = p.get("monthly_spend") or {}
        days = (we - ws).days + 1
        per_month: dict[str, int] = {}
        for n in range(days):
            ym = (ws + dt.timedelta(days=n)).strftime("%Y-%m")
            per_month[ym] = per_month.get(ym, 0) + 1
        fee_now = float(fees.get(we.strftime("%Y-%m")) or 0.0)
        parts = []
        for ym, n in sorted(per_month.items()):
            fee = fees.get(ym)
            if fee is None:
                parts = []
                break
            y, m = int(ym[:4]), int(ym[5:7])
            dim = (dt.date(y + (m == 12), (m % 12) + 1, 1) - dt.date(y, m, 1)).days
            parts.append(
                t("usage.fee_part", n=n, month=calendar.month_name[m], fee=f"{fee:,.0f}", dim=dim)
            )
        if fee_now and days and parts:
            return t(
                "usage.priced_fee",
                spend=f"{spend:,.2f}",
                fee=f"{fee_now:,.0f}",
                days=days,
                note=" + ".join(parts),
            )
    except (ValueError, TypeError, AttributeError, OverflowError):
        pass
    return t("usage.priced_plain", spend=f"{spend:,.2f}")


def _calendar(p: dict):
    daily = [
        d
        for d in (p.get("daily") or [])
        if isinstance(d, dict) and _iso_date(d.get("date")) is not None
    ]
    peak = max((_num(d.get("tokens")) for d in daily), default=0.0)
    by_month: dict[str, list[dict]] = {}
    for d in daily:
        by_month.setdefault(str(d["date"])[:7], []).append(d)
    fees = p.get("monthly_spend") if isinstance(p.get("monthly_spend"), dict) else {}
    cards = []
    for ym in sorted(by_month, reverse=True):
        entries = sorted(by_month[ym], key=lambda e: str(e["date"]))
        first = _iso_date(entries[0]["date"])
        label = f"{calendar.month_name[first.month]} {first.year}"
        m_tok = sum(_num(e.get("tokens")) for e in entries)
        m_cost = sum(_num(e.get("cost_usd")) for e in entries)
        fee = fees.get(ym)
        fee_txt = t("usage.cal.fee", fee=f"{_num(fee):,.0f}") if fee else ""
        rows = []
        for e in entries:
            tok = _num(e.get("tokens"))
            by = e.get("by_tier") if isinstance(e.get("by_tier"), dict) else {}
            detail = " | ".join(f"{k} {_num(v) / 1e9:.2f}B" for k, v in by.items() if v) or t(
                "usage.cal.no_usage"
            )
            share = f"{tok / peak * 100:.0f}%" if peak else "—"
            rows.append(
                [e["date"], f"{tok:,.0f}", f"${_num(e.get('cost_usd')):,.2f}", share, detail]
            )
        cards.append(
            card(
                t(
                    "usage.cal.month",
                    label=label,
                    tokens=f"{m_tok / 1e9:,.1f}",
                    cost=f"{m_cost:,.2f}",
                    fee=fee_txt,
                ),
                table(
                    slug(ym, "usage-month"),
                    t("usage.cal.caption", label=label),
                    [
                        t("usage.cal.col.date"),
                        t("usage.cal.col.tokens"),
                        t("usage.cal.col.cost"),
                        t("usage.cal.col.peak"),
                        t("usage.cal.col.tiers"),
                    ],
                    rows,
                ),
                id=slug(ym, "usage-card"),
            )
        )
    return peak, cards


def _iso_date(x: object):
    try:
        return dt.date.fromisoformat(str(x))
    except ValueError:
        return None


def render(data: dict, ctx: ViewContext) -> ViewResult:
    spend = data.get("spend")
    if not isinstance(spend, dict) or "error" in spend:
        err = spend.get("error") if isinstance(spend, dict) else "no data"
        return ViewResult(fragment(region_state("error", t("usage.error", error=err), retry=True)))
    stamp = freshness(read_ts(_built_ts(spend.get("built_at"))), CADENCE_S)
    p = spend.get("per_model_spend") if isinstance(spend.get("per_model_spend"), dict) else {}
    tiers = p.get("tiers") if isinstance(p.get("tiers"), dict) else {}
    total_spend, base = p.get("spend_usd"), p.get("base_rate_per_mtok")
    unclassified = _unclassified(p)
    peak, months = _calendar(p)
    cal = card(t("usage.cal.title"), t("usage.cal.intro", peak=f"{peak:,.0f}")) if months else None
    if not tiers or not total_spend or not base:
        # never a zeroed table (it would read as "$0 spent"); the unclassified warning and the
        # calendar (every datum survives) stay
        return ViewResult(
            fragment(
                unclassified,
                card(t("usage.title"), region_state("empty", t("usage.empty")), age=stamp),
                cal,
                *months,
            )
        )
    spend_usd = _num(total_spend)
    ordered = sorted(
        tiers.items(), key=lambda kv: -_num(kv[1].get("cost_usd") if isinstance(kv[1], dict) else 0)
    )
    rows, cost_sum, tok = [], 0.0, 0
    for name, v in ordered:
        v = v if isinstance(v, dict) else {}
        cost_sum += _num(v.get("cost_usd"))
        tok += int(_num(v.get("tokens")))
        rows.append(
            [
                name,
                f"{_num(v.get('weight')):.0f}x",
                f"{_num(v.get('tokens')):,.0f}",
                f"{_num(v.get('share')) * 100:.1f}%",
                f"${_num(v.get('rate_per_mtok')):.5f}",
                f"${_num(v.get('cost_usd')):,.2f}",
            ]
        )
    recon = (
        t("usage.recon_ok", spend=f"{spend_usd:,.2f}")
        if abs(cost_sum - spend_usd) < 0.01
        else t("usage.recon_bad", total=f"{cost_sum:,.2f}", spend=f"{spend_usd:,.2f}")
    )
    intro = t(
        "usage.intro",
        window=(
            f"{p.get('window_start')} to {p.get('window_end')}"
            if p.get("window_start") and p.get("window_end")
            else t("usage.window_unknown")
        ),
        tokens=f"{tok:,}",
        priced=_fee_note(p, spend_usd),
        base=f"{_num(base):.6f}",
        recon=recon,
        built=spend.get("built_at") or "-",
    )
    headline = card(
        t("usage.title"),
        fragment(
            intro,
            table(
                "usage-tiers",
                t("usage.table"),
                [
                    t("usage.col.tier"),
                    t("usage.col.weight"),
                    t("usage.col.tokens"),
                    t("usage.col.share"),
                    t("usage.col.rate"),
                    t("usage.col.cost"),
                ],
                rows,
            ),
        ),
        age=stamp,
    )
    return ViewResult(fragment(headline, unclassified, cal, *months))
