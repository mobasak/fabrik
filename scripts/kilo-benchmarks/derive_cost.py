# AFTER-EDIT: claude_price_ratios.json (the ① price source) | none else
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
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_RATIOS = _HERE / "claude_price_ratios.json"
_USAGE_HISTORY = Path.home() / ".claude" / ".claude-manager" / "usage-history.json"
_STATUSLINE = Path.home() / ".claude" / ".claude-manager" / "statusline.json"
_MANAGER_ACCOUNTS = Path.home() / ".claude" / "manager-accounts"

_SUBSCRIPTION_USD_PER_ACCOUNT = 200.0  # Max 20x, grounded 2026-07-20 support.claude.com/.../11049741
_ANCHOR_USD_PER_TOKEN = 9.3e-8  # research "typical" $0.093/M fallback when history is empty
_MONTHLY_DAYS = 30  # most-recent N calendar-days in usage-history = the "monthly throughput" denominator


def _load_ratios(ratios_path: str | Path | None = None) -> dict:
    return json.loads(Path(ratios_path or _RATIOS).read_text(encoding="utf-8"))


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


def amortized_rate(
    usage_history_path: str | Path | None = None, accounts_dir: str | Path | None = None
) -> float:
    """② Real out-of-pocket $/token: (subscription $ × live accounts) ÷ ~monthly global raw tokens.

    Sums the most-recent 30 calendar-days present in usage-history (the monthly-throughput denominator).
    Fail-soft to the research anchor ($0.093/M) when history is missing/empty.
    """
    ad = Path(accounts_dir or _MANAGER_ACCOUNTS)
    try:
        n_accounts = sum(1 for p in ad.iterdir() if p.is_dir())
    except OSError:
        n_accounts = 1
    n_accounts = max(1, n_accounts)
    try:
        d = json.loads(Path(usage_history_path or _USAGE_HISTORY).read_text(encoding="utf-8"))
        days = d.get("days") or {}
        # A real 30-CALENDAR-day window (ISO date-string >= cutoff), NOT the 30 most-recent present keys —
        # a gapped history must not sum arbitrarily-old days into the "monthly" denominator (which would
        # skew the amortized rate). No recent usage → total 0 → fail-soft to the anchor below.
        cutoff = (datetime.date.today() - datetime.timedelta(days=_MONTHLY_DAYS)).isoformat()
        recent = [k for k in days if k >= cutoff]
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


def quota_snapshot(statusline_path: str | Path | None = None) -> float:
    """③ Weekly-quota proxy: statusline rateLimits.sevenDay.usedPercent (caller deltas before/after)."""
    try:
        d = json.loads(Path(statusline_path or _STATUSLINE).read_text(encoding="utf-8"))
        sd = (d.get("rateLimits") or {}).get("sevenDay") or {}
        return float(sd.get("usedPercent", 0.0) or 0.0)
    except (OSError, ValueError, TypeError, AttributeError):  # AttributeError: malformed non-object json
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
        "quota_draw_pct": max(0.0, quota_after - quota_before),
        "built_at": built,
    }
    Path(path or _COST_SIDECAR).write_text(json.dumps(data, indent=2), encoding="utf-8")
    return data
