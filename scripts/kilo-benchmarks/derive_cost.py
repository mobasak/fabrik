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


def _model_key(model: str) -> str:
    """The `_model_cache` key space — byte-for-byte the same rule as `claude_p_cost._model_key`.

    Vendor prefix dropped, dots folded to dashes, lowercased. Omitting this WAS a real divergence:
    `claude-fable-5.1` and `anthropic/claude-fable-5-1` priced their cache reads 4x apart between the
    two modules, inside a function whose docstring asserted they could not.
    """
    return model.lower().strip().rsplit("/", 1)[-1].replace(".", "-")


def _cache_for(ratios: dict, model_id: str) -> dict:
    """`_cache` defaults with the longest-prefix `_model_cache` override for a real model id applied.

    Mirrors `scripts/claude_p_cost.py::_cache_multipliers` — the two modules must price a cache read
    identically or the ranking axis and the per-call meter disagree on the same tokens. Asserted by
    `tests/test_price_ratios_current.py`, not merely stated here.
    """
    c = dict(ratios.get("_cache") or {})
    m = _model_key(str(model_id))
    best: str | None = None
    for prefix in ratios.get("_model_cache") or {}:
        # BOTH sides through `_model_key` — mirrors `claude_p_cost._cache_multipliers`.
        key = _model_key(prefix)
        rest = m[len(key) :] if m.startswith(key) else None
        # SEGMENT boundary, not a bare prefix: `claude-fable-5-1` must not swallow a future
        # `claude-fable-5-10`, which would hand a different model Fable 5.1's 2.5% rate — a 4x
        # UNDERprice, the exact mirror of the bug the override closed. A real suffix always begins
        # with a separator (`-20260815`, `[1m]`); a different model number begins with a digit.
        if rest is not None and (rest == "" or not rest[0].isalnum()):
            if best is None or len(prefix) > len(best):
                best = prefix
    if best is not None:
        override = (ratios.get("_model_cache") or {}).get(best)
        if isinstance(override, dict):
            c.update(override)
    return c


def api_equiv(usage: dict, model: str, ratios_path: str | Path | None = None) -> float:
    """① Cache-aware API-equivalent USD for one run's raw per-type tokens (the ranking axis).

    `usage` uses the CLI snake_case keys. The flat cache_creation count carries no 5m/1h split, so the
    write is priced at the ×1.25 (5-minute) default. Raises KeyError for an unpriced model.

    ⚠️ FAMILY-KEYED BY CONSTRUCTION: `model` must be a `claude-code/<tier>` key, so a per-model
    `_model_cache` override can never reach this function — a fable-tier figure from here is an UPPER
    BOUND if the tier ran Fable 5.1 (2.5% cache reads, not 10%). `amortized_by_family` below has the
    real model id and DOES apply the override. Closing this one needs a signature change, not a row.
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
        # INCLUSIVE bounds must span exactly `_MONTHLY_DAYS` dates: `today - _MONTHLY_DAYS` spans 31,
        # dividing ONE month of subscription $ by 31 days of tokens (~1.3% low). Mirrors
        # `claude_p_cost._live_usage_window` — both producers must use the same denominator.
        cutoff = (datetime.date.today() - datetime.timedelta(days=_MONTHLY_DAYS - 1)).isoformat()
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
    fallback of amortized_rate).

    ⚠️ PER-FAMILY no-traffic case: a family with priced VALUE but zero RAW tokens in the
    window is omitted from the returned map entirely (the `raw.get(fam, 0) > 0` guard below,
    which exists because it is the divisor). So an absent family key means "no measured
    traffic this window", never "rate zero" — a reader that defaults a missing key to 0.0
    prices that family free. The whole-map empty case ({}) is the different, documented one
    above."""
    r = _load_ratios(ratios_path)
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
        # INCLUSIVE bounds must span exactly `_MONTHLY_DAYS` dates: `today - _MONTHLY_DAYS` spans 31,
        # dividing ONE month of subscription $ by 31 days of tokens (~1.3% low). Mirrors
        # `claude_p_cost._live_usage_window` — both producers must use the same denominator.
        cutoff = (datetime.date.today() - datetime.timedelta(days=_MONTHLY_DAYS - 1)).isoformat()
        for dk in (k for k in days if _is_iso_date(k) and cutoff <= k <= today_iso):
            for model, m in (days[dk].get("byModel") or {}).items():
                fam = _family(str(model))
                if fam is None or f"claude-code/{fam}" not in r:
                    continue
                p = r[f"claude-code/{fam}"]
                c = _cache_for(r, model)  # the real model id is in hand HERE — use its own rate
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
    """Write the ②/③ sidecar the ranker preamble reads: ② amortized $/M + ③ weekly-quota-draw %.

    ⚠️ ORPHANED IN THIS REPO — zero CODE call sites. Verify with
    `git grep -n write_cost_sidecar -- '*.py'`: every hit outside this `def` is a docstring. (A raw
    `git grep -- .` also sweeps the plan, the reviews and the ledger, so its count moves whenever one
    of those is edited — this docstring stated such a count twice and was wrong both times.)
    Its callers left with the catalog-engine excision (`73bde59a`) and now live in `/opt/ai-model-catalog/`,
    whose copy resolves `_COST_SIDECAR` relative to ITS OWN directory and never writes the hub's file.
    The hub's sidecar is written by `scripts/claude_p_cost.py::refresh()` — change THAT one. Editing the
    catalog repo from here is a cross-repo HARD STOP; this note exists so the next reader does not spend
    a plan revision on the wrong producer, as one did on 2026-09-05.

    ⚠️ AND DO NOT RUN IT AGAINST THE HUB'S SIDECAR TO "REFRESH THE FAMILY SPLIT": it writes FOUR keys
    with a full overwrite, so it silently annihilates `window_start`, `window_end`, `accounts`,
    `spend_usd` and `tokens` while restamping `built_at` — the file then looks current and has lost the
    window. That is the exact failure the windowed-sidecar plan was rewritten to avoid."""
    built = (when or datetime.datetime.now()).isoformat(timespec="seconds")
    data = {
        "amortized_per_mtok": amortized_rate() * 1_000_000.0,
        "amortized_per_mtok_by_family": amortized_by_family(),
        "quota_draw_pct": max(0.0, quota_after - quota_before),
        "built_at": built,
    }
    Path(path or _COST_SIDECAR).write_text(json.dumps(data, indent=2), encoding="utf-8")
    return data
