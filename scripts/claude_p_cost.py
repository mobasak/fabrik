#!/usr/bin/env python3
# AFTER-EDIT: kilo-benchmarks/claude_price_ratios.json (the ① price source incl. `_model_cache`) · tests/test_claude_p_cost.py · tests/test_claude_p_cost_refresh.py
"""Per-call `claude -p` cost measurement for ANY project — self-contained, no engine import.

Two lenses, per model (fable/opus/sonnet/haiku), from a run's own `claude -p --output-format json`:
  ① api_equiv  — cache-aware Anthropic-list-price valuation of the run's tokens (comparable to the pool).
  ② real       — real subscription-derived $: run tokens × the fleet's current amortized $/token.

WHY a standalone copy (not `import derive_cost`): `derive_cost.py` is engine-internal (benchmark ranking)
and relocated with the AI-model-catalog extraction; this file is the FLEET consumer copy that stays.
Different lifecycles → vendor-the-math, don't import (fabrik "vendor, don't import" pattern). ⚠️ It is NOT
in `fabrik_synced_manifest.py` and exists in 1 of 57 `/opt` dirs — the hub's own. An earlier version of
this header claimed it "is synced to every project"; it never was. The two numbers agree with
`derive_cost` by construction (same formulas below).

DATA FILES (resolved in order: env override → co-located with this script → hub kilo-benchmarks):
  • prices     — `claude_price_ratios.json` (per-model in/out list price + cache multipliers). MANUAL,
                 grounded from platform.claude.com/docs/en/about-claude/pricing.
  • amortized  — `claude_p_cost.json`. `--refresh` AUTHORS eight keys: the rate `amortized_per_mtok`,
                 the window it came from (`window_start`, `window_end`, `accounts`, `spend_usd`,
                 `tokens`), `quota_draw_pct` and `built_at`. It CARRIES FORWARD every other key the
                 previous file had, so a box that has one also carries `amortized_per_mtok_by_family`
                 (owned by `derive_cost.amortized_by_family`, never recomputed here) — nine in total.
                 A fresh box with no previous file has eight; the family key is not guaranteed and a
                 reader must `.get` it. Window keys are `null` when the rate fell back to the research
                 anchor (no window) and `accounts`/`spend_usd` are `null` when the account count could
                 not be measured. Rebuilt by `--refresh` (hub/operator box — needs ~/.claude history).

USAGE
  # measure one call (project or hub): pipe the CLI's JSON in, name the model
  claude -p "..." --model opus --output-format json | python scripts/claude_p_cost.py --model opus
  # rebuild the amortized sidecar (hub/operator box, daily cron):
  python scripts/claude_p_cost.py --refresh
  # as a library:
  from claude_p_cost import measure, api_equiv, real_usd
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
# Env overrides let a project point at its synced copies without editing code (see _find).
_SUBSCRIPTION_USD_PER_ACCOUNT = float(os.getenv("CLAUDE_MAX_PRICE_USD", "200") or 200)
_ANCHOR_USD_PER_TOKEN = 9.3e-8  # $0.093/M research fallback when usage history is empty
_MONTHLY_DAYS = 30
_USAGE_HISTORY = Path.home() / ".claude" / ".claude-manager" / "usage-history.json"
_STATUSLINE = Path.home() / ".claude" / ".claude-manager" / "statusline.json"
_MANAGER_ACCOUNTS = Path.home() / ".claude" / "manager-accounts"
_USAGE_KEYS = (
    "input_tokens",
    "output_tokens",
    "cache_read_input_tokens",
    "cache_creation_input_tokens",
)


def _find(name: str, env: str) -> Path:
    """env override → next to this script (project-synced) → hub kilo-benchmarks (dev)."""
    if os.getenv(env):
        return Path(os.environ[env])
    for cand in (_HERE / name, _HERE / "kilo-benchmarks" / name):
        if cand.exists():
            return cand
    return _HERE / name  # last resort; a read will fail-soft


def _prices_path() -> Path:
    return _find("claude_price_ratios.json", "CLAUDE_P_PRICES")


def _cost_path() -> Path:
    return _find("claude_p_cost.json", "CLAUDE_P_COST")


def _norm_model(model: str) -> str:
    """Accept 'opus' | 'claude-code/opus' | 'claude-opus-5' → the price-file key 'claude-code/<tier>'."""
    m = model.lower().strip()
    if m.startswith("claude-code/"):
        return m
    for tier in ("fable", "opus", "sonnet", "haiku"):
        if tier in m:
            return f"claude-code/{tier}"
    return m  # unknown → let api_equiv raise a clear KeyError


def _model_key(model: str) -> str:
    """Normalise a model string into the `_model_cache` key space: `anthropic/claude-fable-5.1` and
    `claude-fable-5-1` land on the same key. Vendor prefix dropped, dots folded to dashes, lowercased.

    Price lookup (`_norm_model`) and cache lookup used to run on DIFFERENT key spaces, so a
    vendor-qualified or dotted id got the right family PRICE and silently missed its cache override —
    correct on the small term, 4x wrong on the dominant one.
    """
    return model.lower().strip().rsplit("/", 1)[-1].replace(".", "-")


def _cache_multipliers(ratios: dict, model: str) -> dict:
    """Cache multipliers for one model: the `_cache` default, overridden by LONGEST-PREFIX model id.

    Cache reads bill at 10% of base input on every model EXCEPT Claude Fable 5.1 (2.5%). A FAMILY key
    cannot hold both, because `claude-code/fable` covers `claude-fable-5` AND `claude-fable-5-1` and
    both run live here — so the exception is keyed on the model id in `_model_cache`.

    Longest-PREFIX, not exact equality (the pattern `kilo-benchmarks/audit_usage_cost.py::price_for`
    already uses on the same vocabulary): live ids carry suffixes — `claude-haiku-4-5-20251001` in the
    usage history, `claude-opus-5[1m]` as a session id — and an exact match silently returns the 0.1
    default for every one of them, which is the 4× overprice wearing a fix.

    ⚠️ STANDING LIMIT, not an oversight: a bare TIER ALIAS (`fable`, and `claude-code/fable`) is
    genuinely ambiguous — it names a tier that runs both models — so it resolves to the 0.1 default and
    a fable-tier figure computed from an alias remains an UPPER BOUND. Every caller in this repo passes
    an alias today (`main()`'s `--model`, `rivals_run.CLAUDE_P_MODELS`), so closing that half needs the
    callers to carry real model ids; a price row cannot do it.
    """
    c = dict(ratios.get("_cache") or {})
    m = _model_key(model)
    best: str | None = None
    for prefix in ratios.get("_model_cache") or {}:
        if m.startswith(prefix.lower()) and (best is None or len(prefix) > len(best)):
            best = prefix
    if best is not None:
        override = (ratios.get("_model_cache") or {}).get(best)
        if isinstance(override, dict):
            c.update(override)
    return c


def api_equiv(usage: dict, model: str) -> float:
    """① Cache-aware Anthropic-list-price USD for one call's raw per-type tokens."""
    r = json.loads(_prices_path().read_text(encoding="utf-8"))
    key = _norm_model(model)
    if key not in r:
        raise KeyError(f"no price ratios for model {model!r} (looked up {key!r})")
    p_in, p_out, c = r[key]["in"], r[key]["out"], _cache_multipliers(r, model)
    inp = usage.get("input_tokens", 0) or 0
    out = usage.get("output_tokens", 0) or 0
    cr = usage.get("cache_read_input_tokens", 0) or 0
    cc = usage.get("cache_creation_input_tokens", 0) or 0
    return (
        inp * p_in + out * p_out + cr * p_in * c["read"] + cc * p_in * c["write_5m"]
    ) / 1_000_000.0


def cached_amortized_per_mtok() -> float:
    """② rate a PROJECT uses — the pre-computed fleet rate from the synced sidecar (fail-soft to anchor)."""
    try:
        d = json.loads(_cost_path().read_text(encoding="utf-8"))
        v = float(d.get("amortized_per_mtok", 0.0) or 0.0)
        return v if v > 0 else _ANCHOR_USD_PER_TOKEN * 1_000_000.0
    except (OSError, ValueError, TypeError, AttributeError):
        return _ANCHOR_USD_PER_TOKEN * 1_000_000.0


def real_usd(usage: dict) -> float:
    """② Real subscription-derived $ for one call = call tokens × the fleet's current amortized rate."""
    total = sum(usage.get(k, 0) or 0 for k in _USAGE_KEYS)
    return total * cached_amortized_per_mtok() / 1_000_000.0


def measure(claude_json: dict, model: str) -> dict:
    """Take a full `claude -p --output-format json` object (or its bare `usage` block) → ①+② + tokens."""
    nested = claude_json.get("usage")
    usage: dict = nested if isinstance(nested, dict) else claude_json
    tokens = {k: int(usage.get(k, 0) or 0) for k in _USAGE_KEYS}
    tokens["total"] = sum(tokens.values())
    return {
        "model": _norm_model(model),
        "tokens": tokens,
        "api_equiv_usd": round(api_equiv(usage, model), 6),  # ①
        "real_usd": round(real_usd(usage), 6),  # ②
        "amortized_per_mtok": round(cached_amortized_per_mtok(), 6),
        "cli_total_cost_usd": claude_json.get(
            "total_cost_usd"
        ),  # Claude Code's own ① figure, if present
    }


# ─── producer side (hub / operator box only — needs ~/.claude) ───────────────────────────────
def _live_usage_window() -> dict:
    """② and the WINDOW it was derived from: (subscription $ × live accounts) ÷ last-30d global tokens.

    Returns `amortized_per_mtok` plus the five things a reader needs to judge it — `window_start`,
    `window_end`, `accounts`, `spend_usd`, `tokens`. A rate with no window is indistinguishable from
    a fossil, which is the whole reason this returns a dict instead of a float.

    ⚠️ On an empty/unreadable usage history the rate falls back to `_ANCHOR_USD_PER_TOKEN`, a
    research constant that was derived from NO window — every denominator is then `None`, never a
    plausible-looking zero. Publishing bounds beside the anchor would assert a derivation that never
    happened.

    ⚠️ `accounts`/`spend_usd` are `None` for the same reason when the account directory is unreadable
    or empty. The RATE still prices as one account (the historical `max(1, n)` floor, unchanged), but
    publishing `accounts: 1` would state an unmeasured count as fact — the fabricated denominator this
    reshape exists to end. Null there means "the rate rests on an assumed single account and cannot be
    re-derived from these denominators".
    """
    try:
        counted: int | None = sum(
            1 for p in _MANAGER_ACCOUNTS.iterdir() if p.is_dir() and not p.name.startswith(".")
        )
    except OSError:
        counted = None  # unmeasurable — NOT the same as "one account"
    n = max(1, counted or 0)  # the RATE floor, unchanged: an unknown count still prices as one
    measured = counted if (counted or 0) > 0 else None
    # INCLUSIVE bounds spanning exactly `_MONTHLY_DAYS` dates. `today - _MONTHLY_DAYS` spans THIRTY-ONE,
    # which divided ONE month of subscription $ by 31 days of tokens and understated the rate ~1.3%.
    # LOCAL calendar dates, deliberately: they are compared against `usage-history.json`'s own day keys,
    # which the CLI writes in local time. `built_at` is UTC-aware; these are a different clock on purpose
    # and must not be merged. A consumer computing staleness reads `built_at`, never these.
    today = datetime.date.today().isoformat()
    cutoff = (datetime.date.today() - datetime.timedelta(days=_MONTHLY_DAYS - 1)).isoformat()
    try:
        d = json.loads(_USAGE_HISTORY.read_text(encoding="utf-8"))
        days = d.get("days") or {}

        def _iso(s: object) -> bool:
            try:
                datetime.date.fromisoformat(s)  # type: ignore[arg-type]
                return True
            except (ValueError, TypeError):
                return False

        total = 0
        for k in days:
            if _iso(k) and cutoff <= k <= today:
                for m in (days[k].get("byModel") or {}).values():
                    total += sum(
                        int(m.get(x, 0) or 0)
                        for x in ("input", "output", "cacheRead", "cacheCreation")
                    )
    except (OSError, ValueError, TypeError, AttributeError):
        total = 0
    if total <= 0:
        return {
            "amortized_per_mtok": _ANCHOR_USD_PER_TOKEN * 1_000_000.0,
            "window_start": None,
            "window_end": None,
            "accounts": None,
            "spend_usd": None,
            "tokens": None,
        }
    spend = _SUBSCRIPTION_USD_PER_ACCOUNT * n
    return {
        "amortized_per_mtok": spend / total * 1_000_000.0,
        "window_start": cutoff,
        "window_end": today,
        "accounts": measured,
        "spend_usd": None if measured is None else _SUBSCRIPTION_USD_PER_ACCOUNT * measured,
        "tokens": total,
    }


def refresh() -> dict:
    """Rebuild `claude_p_cost.json` from live ~/.claude usage, with the window ② came from.

    CARRIES FORWARD EVERY KEY IT DID NOT AUTHOR (`data = dict(prev)`), rather than an allowlist of the
    two it knows. This function used to DESTROY `amortized_per_mtok_by_family` on every run by writing
    three keys over the file with a full `write_text`; an allowlist would have re-created that exact
    bug for the next key some other producer adds. It re-derives ② and the window and nothing else —
    the per-family split is owned by `derive_cost.amortized_by_family()`, which this module
    deliberately does not import (see the header).

    No `rate` key: `amortized_per_mtok` already IS the rate, and renaming it would break every reader
    for cosmetics. The window keys sit BESIDE the existing ones — additive, so no reader is forced to
    change in the same release.
    """
    path = _cost_path()
    prev: dict = {}
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            prev = loaded  # valid JSON that is a list/str/number is NOT a sidecar
    except (OSError, ValueError):
        pass
    try:
        quota = float(prev.get("quota_draw_pct", 0.0) or 0.0)
    except (TypeError, ValueError):
        quota = 0.0  # a non-numeric ③ must not crash the producer off its cron
    w = _live_usage_window()
    data = dict(prev)  # carry forward EVERY key this function did not author
    # A carried map must not inherit the fresh window's authority: stamp it with the `built_at` of the
    # file it came from, so `window_start`/`window_end` are never read as vouching for it. Measured
    # 2026-09-05: the carried split was up to 88% off a live recompute under a same-day window.
    if "amortized_per_mtok_by_family" in prev and prev.get("built_at"):
        data.setdefault("amortized_per_mtok_by_family_built_at", prev["built_at"])
    data.update(
        {
            "amortized_per_mtok": w["amortized_per_mtok"],
            "quota_draw_pct": quota,
            "window_start": w["window_start"],
            "window_end": w["window_end"],
            "accounts": w["accounts"],
            "spend_usd": w["spend_usd"],
            "tokens": w["tokens"],
            "built_at": datetime.datetime.now(datetime.UTC).isoformat(timespec="seconds"),
        }
    )
    # ATOMIC: this file is now the SOLE store of `amortized_per_mtok_by_family`, which nothing in
    # this repo can regenerate (`derive_cost.amortized_by_family` is reachable only from the orphaned
    # `write_cost_sidecar`). A torn write would lose it permanently, and Phase C puts this on a cron.
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)
    return data


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Per-call claude -p cost (① api-equivalent + ② real).")
    ap.add_argument(
        "--refresh",
        action="store_true",
        help="rebuild claude_p_cost.json from ~/.claude (hub only)",
    )
    ap.add_argument("--model", default="opus", help="fable|opus|sonnet|haiku (default: opus)")
    args = ap.parse_args(argv)
    if args.refresh:
        print(json.dumps(refresh(), indent=2))
        return 0
    raw = sys.stdin.read().strip()
    if not raw:
        print("error: pipe a `claude -p ... --output-format json` object on stdin", file=sys.stderr)
        return 2
    try:
        obj = json.loads(raw)
    except ValueError as e:
        print(f"error: stdin is not valid JSON ({e})", file=sys.stderr)
        return 2
    print(json.dumps(measure(obj, args.model), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
