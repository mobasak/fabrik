# AFTER-EDIT: claude_price_ratios.json (the ① price source) · tests/test_price_ratios_current.py
"""Three-number subscription-run cost model for claude -p benchmark scoring.

① api_equiv     — cache-aware API-equivalent USD (the RANKING axis), from a run's raw per-type tokens at
                  Anthropic list prices. NOT ccusage's dollar, NOT the CLI total_cost_usd.
② amortized_rate — the real out-of-pocket $/token: total subscription $ ÷ global ~monthly raw tokens.
③ quota_snapshot — the weekly-quota proxy: statusline sevenDay.usedPercent (caller deltas before/after).

Grounded 2026-07-20 (spec docs/superpowers/specs/2026-07-20-claude-p-first-class-scoring-design.md):
prices from platform.claude.com/docs/en/about-claude/pricing; usage-history/statusline structures from
~/.claude/.claude-manager/ (days[date].byModel[model]={input,output,cacheRead,cacheCreation} camelCase;
rateLimits.sevenDay.usedPercent).
"""

from __future__ import annotations

import datetime
import json
import os
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_RATIOS = _HERE / "claude_price_ratios.json"
_USAGE_HISTORY = Path.home() / ".claude" / ".claude-manager" / "usage-history.json"
_STATUSLINE = Path.home() / ".claude" / ".claude-manager" / "statusline.json"
_MANAGER_ACCOUNTS = Path.home() / ".claude" / "manager-accounts"


def _env_float(name: str, default: float) -> float:
    """A malformed override must NOT crash the whole module at import time — fall back to default."""
    try:
        return float(os.getenv(name, default))
    except (ValueError, TypeError):
        return default


# Max 20x, grounded 2026-07-20 support.claude.com/.../11049741 — env-overridable (not a secret; a
# real-world price Anthropic can change) so a price update doesn't need a code edit + gate + commit.
_SUBSCRIPTION_USD_PER_ACCOUNT = _env_float("CLAUDE_MAX_PRICE_USD", 200.0)
_ANCHOR_USD_PER_TOKEN = 9.3e-8  # research "typical" $0.093/M fallback when history is empty
_MONTHLY_DAYS = (
    30  # most-recent N calendar-days in usage-history = the "monthly throughput" denominator
)


def _load_ratios(ratios_path: str | Path | None = None) -> dict:
    return json.loads(Path(ratios_path or _RATIOS).read_text(encoding="utf-8"))


def _is_iso_date(s: object) -> bool:
    """True iff s is a real YYYY-MM-DD date string — guards a non-date key (e.g. 'latest') from a
    lexicographic `>= cutoff` compare that would pollute the monthly denominator."""
    try:
        datetime.date.fromisoformat(s)  # type: ignore[arg-type]
        return True
    except (ValueError, TypeError):
        return False


def api_equiv(usage: dict, model: str, ratios_path: str | Path | None = None) -> float:
    """① Cache-aware API-equivalent USD for one run's raw per-type tokens (the ranking axis).

    `usage` uses the CLI snake_case keys. The flat cache_creation count carries no 5m/1h split, so the
    write is priced at the ×1.25 (5-minute) default. Raises KeyError for an unpriced model.
    """
    r = _load_ratios(ratios_path)
    if model not in r:
        raise KeyError(f"no price ratios for model {model!r}")
    p_in = r[model]["in"]
    p_out = r[model]["out"]
    c = r["_cache"]
    inp = usage.get("input_tokens", 0) or 0
    out = usage.get("output_tokens", 0) or 0
    cr = usage.get("cache_read_input_tokens", 0) or 0
    cc = usage.get("cache_creation_input_tokens", 0) or 0
    per_mtok = inp * p_in + out * p_out + cr * p_in * c["read"] + cc * p_in * c["write_5m"]
    return per_mtok / 1_000_000.0


def amortized_cost(usage: dict, ratios_path: str | Path | None = None) -> float:
    """② REAL out-of-pocket USD for one run's raw tokens: amortized_rate() × total tokens.

    `usage` uses the same snake_case keys as `api_equiv` — the 4 CLI usage fields, summed (matching
    how `amortized_rate`'s own denominator is computed). This is the actual subscription-derived cost
    per row — NOT a list-price valuation (①) and NOT a single blended fleet-wide figure; each row's
    own token volume × the current fleet rate. `ratios_path` is unused (kept for signature symmetry
    with `api_equiv`; the rate has no per-model price component).
    """
    total = sum(
        usage.get(k, 0) or 0
        for k in (
            "input_tokens",
            "output_tokens",
            "cache_read_input_tokens",
            "cache_creation_input_tokens",
        )
    )
    return amortized_rate() * total


def amortized_rate(
    usage_history_path: str | Path | None = None, accounts_dir: str | Path | None = None
) -> float:
    """② Real out-of-pocket $/token: (subscription $ × live accounts) ÷ ~monthly global raw tokens.

    Sums the most-recent 30 calendar-days present in usage-history (the monthly-throughput denominator).
    Fail-soft to the research anchor ($0.093/M) when history is missing/empty.
    """
    ad = Path(accounts_dir or _MANAGER_ACCOUNTS)
    try:
        # skip dotdirs (.git, stray tmp dirs) — a real account dir never starts with "." — so a stray
        # non-account subdir doesn't inflate n_accounts (which would over-state ②'s subscription fee).
        n_accounts = sum(1 for p in ad.iterdir() if p.is_dir() and not p.name.startswith("."))
    except OSError:
        n_accounts = 1
    n_accounts = max(1, n_accounts)
    try:
        d = json.loads(Path(usage_history_path or _USAGE_HISTORY).read_text(encoding="utf-8"))
        days = d.get("days") or {}
        # A real 30-CALENDAR-day window (ISO date-string >= cutoff), NOT the 30 most-recent present keys —
        # a gapped history must not sum arbitrarily-old days into the "monthly" denominator (which would
        # skew the amortized rate). No recent usage → total 0 → fail-soft to the anchor below.
        today_iso = datetime.date.today().isoformat()
        cutoff = (datetime.date.today() - datetime.timedelta(days=_MONTHLY_DAYS)).isoformat()
        # upper-bound at today too — a clock-skewed source could carry a future-dated key, which
        # would otherwise inflate the denominator (k >= cutoff alone never excludes k > today).
        recent = [k for k in days if _is_iso_date(k) and cutoff <= k <= today_iso]
        total = 0
        for dk in recent:
            for m in (days[dk].get("byModel") or {}).values():
                total += sum(
                    int(m.get(k, 0) or 0) for k in ("input", "output", "cacheRead", "cacheCreation")
                )
    except (OSError, ValueError, TypeError, AttributeError):
        # AttributeError guards a malformed non-object top level / null day / null byModel entry
        # (`.get` on a non-dict) — fail-soft to the anchor, never crash the benchmark on corrupt history.
        total = 0
    if total <= 0:
        return _ANCHOR_USD_PER_TOKEN
    return (_SUBSCRIPTION_USD_PER_ACCOUNT * n_accounts) / total


_FAMILIES = ("opus", "sonnet", "haiku", "fable")


def _family(model_key: str) -> str | None:
    """claude-opus-4-8 → opus; '<synthetic>'/unknown → None (excluded from family math)."""
    low = model_key.lower()
    for f in _FAMILIES:
        if f in low:
            return f
    return None


def amortized_by_family(
    usage_history_path: str | Path | None = None,
    accounts_dir: str | Path | None = None,
    ratios_path: str | Path | None = None,
) -> dict[str, float]:
    """② split by model family: per-family amortized $/Mtok over the same 30-day window.

    Allocation rule (the only meaningful one for a pooled subscription): allocate the
    subscription $ across families by API-EQUIVALENT VALUE (cache-aware list prices), never
    by raw token share — token share would price every family identically. Collapses to:
    family_rate = family_effective_list_rate × discount, where
    discount = (subscription $ × accounts) ÷ Σ family api-equiv $. `<synthetic>` and
    unpriced model rows are excluded from BOTH numerator and denominator. Fail-soft: no
    priced usage in the window → {} (callers treat as unavailable, mirroring the anchor
    fallback of amortized_rate)."""
    r = _load_ratios(ratios_path)
    c = r["_cache"]
    ad = Path(accounts_dir or _MANAGER_ACCOUNTS)
    try:
        n_accounts = sum(1 for p in ad.iterdir() if p.is_dir() and not p.name.startswith("."))
    except OSError:
        n_accounts = 1
    n_accounts = max(1, n_accounts)
    value: dict[str, float] = {}  # family -> api-equiv USD in window
    raw: dict[str, int] = {}  # family -> raw tokens in window
    try:
        d = json.loads(Path(usage_history_path or _USAGE_HISTORY).read_text(encoding="utf-8"))
        days = d.get("days") or {}
        today_iso = datetime.date.today().isoformat()
        cutoff = (datetime.date.today() - datetime.timedelta(days=_MONTHLY_DAYS)).isoformat()
        for dk in (k for k in days if _is_iso_date(k) and cutoff <= k <= today_iso):
            for model, m in (days[dk].get("byModel") or {}).items():
                fam = _family(str(model))
                if fam is None or f"claude-code/{fam}" not in r:
                    continue
                p = r[f"claude-code/{fam}"]
                inp = int(m.get("input", 0) or 0)
                out = int(m.get("output", 0) or 0)
                cr = int(m.get("cacheRead", 0) or 0)
                cc = int(m.get("cacheCreation", 0) or 0)
                value[fam] = (
                    value.get(fam, 0.0)
                    + (
                        inp * p["in"]
                        + out * p["out"]
                        + cr * p["in"] * c["read"]
                        + cc * p["in"] * c["write_5m"]
                    )
                    / 1_000_000.0
                )
                raw[fam] = raw.get(fam, 0) + inp + out + cr + cc
    except (OSError, ValueError, TypeError, AttributeError):
        return {}
    total_value = sum(value.values())
    if total_value <= 0:
        return {}
    discount = (_SUBSCRIPTION_USD_PER_ACCOUNT * n_accounts) / total_value
    return {
        fam: (value[fam] / raw[fam]) * 1_000_000.0 * discount
        for fam in value
        if raw.get(fam, 0) > 0
    }


def quota_snapshot(statusline_path: str | Path | None = None) -> float:
    """③ Weekly-quota proxy: statusline rateLimits.sevenDay.usedPercent (caller deltas before/after)."""
    try:
        d = json.loads(Path(statusline_path or _STATUSLINE).read_text(encoding="utf-8"))
        sd = (d.get("rateLimits") or {}).get("sevenDay") or {}
        return float(sd.get("usedPercent", 0.0) or 0.0)
    except (
        OSError,
        ValueError,
        TypeError,
        AttributeError,
    ):  # AttributeError: malformed non-object json
        return 0.0


_COST_SIDECAR = _HERE / "claude_p_cost.json"


def out_price_mtok(model: str, ratios_path: str | Path | None = None) -> float:
    """The $/M output list price for a claude-code/* model — the `_DirectResult.out_price_mtok` reference."""
    return float(_load_ratios(ratios_path)[model]["out"])


def write_cost_sidecar(
    quota_before: float,
    quota_after: float,
    path: str | Path | None = None,
    *,
    when: datetime.datetime | None = None,
) -> dict:
    """Write the ②/③ sidecar the ranker preamble reads: ② amortized $/M + ③ weekly-quota-draw %."""
    built = (when or datetime.datetime.now()).isoformat(timespec="seconds")
    data = {
        "amortized_per_mtok": amortized_rate() * 1_000_000.0,
        "amortized_per_mtok_by_family": amortized_by_family(),
        "quota_draw_pct": max(0.0, quota_after - quota_before),
        "built_at": built,
    }
    Path(path or _COST_SIDECAR).write_text(json.dumps(data, indent=2), encoding="utf-8")
    return data
