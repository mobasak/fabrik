#!/usr/bin/env python3
# AFTER-EDIT: kilo-benchmarks/claude_price_ratios.json (the ① price source incl. `_model_cache`) · tests/test_claude_p_cost.py · tests/test_claude_p_cost_refresh.py · tests/test_spend_calendar_months.py · tests/test_usage_collector.py
"""Per-call `claude -p` cost measurement for ANY project — self-contained, no engine import.

Two lenses, per model (fable/opus/sonnet/haiku), from a run's own `claude -p --output-format json`:
  ① api_equiv  — cache-aware Anthropic-list-price valuation of the run's tokens (comparable to the pool).
  ② real       — real subscription-derived $: run tokens × the fleet's current amortized $/token.

WHY a standalone copy (not `import derive_cost`): `derive_cost.py` is engine-internal (benchmark ranking)
and relocated with the AI-model-catalog extraction; this file is the FLEET consumer copy that stays.
Different lifecycles → vendor-the-math, don't import (fabrik "vendor, don't import" pattern). ⚠️ It is NOT
in `fabrik_synced_manifest.py`, and only the hub carries it — 1 of 57 `/opt` dirs by `ls -1d /opt/*/`,
59 if hidden dirs are counted, so the denominator depends on the method while the fact does not. An
earlier version of this header claimed it "is synced to every project"; it never was.

DATA FILES (resolved in order: env override → co-located with this script → hub kilo-benchmarks):
  • prices     — `claude_price_ratios.json` (per-model in/out list price + cache multipliers). MANUAL,
                 grounded from platform.claude.com/docs/en/about-claude/pricing.
  • amortized  — `claude_p_cost.json`. `--refresh` AUTHORS eight keys unconditionally: the rate
                 `amortized_per_mtok`, the window it came from (`window_start`, `window_end`,
                 `accounts`, `spend_usd`, `tokens`), `quota_draw_pct` and `built_at` — so a FRESH box
                 with no previous file has exactly eight. It CARRIES FORWARD every other key the
                 previous file had, and where that includes `amortized_per_mtok_by_family` (owned by
                 `derive_cost.amortized_by_family`, never recomputed here) it authors a ninth,
                 `amortized_per_mtok_by_family_carried: true` — TEN in total on this box today. That
                 flag is deliberately NOT a date: the split's build time is not recoverable from this
                 file, and `built_at` describes ② only. Nothing
                 past the eight is guaranteed; a reader must `.get`. Window keys are `null` when the
                 rate fell back to the research anchor (which came from no window), and
                 `accounts`/`spend_usd` are `null` when the account count could not be measured.

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
import math
import os
import sys
import tempfile
from pathlib import Path


def _env_float(name: str, default: float) -> float:
    """Read a float env knob, falling back on anything unparseable. Mirrors `derive_cost._env_float`.

    A malformed operator override must NOT crash the module at IMPORT — `python claude_p_cost.py
    --refresh` would then die before `refresh()` runs, and Phase C puts that on a 06:00 cron where an
    import-time raise means the rate silently fossilises. `derive_cost` has guarded this knob all
    along; its vendored twin called bare `float()` and did not.
    """
    try:
        return float(os.environ.get(name) or default)
    except (TypeError, ValueError):
        return default


_HERE = Path(__file__).resolve().parent
# Env overrides let a consumer point at its own copies without editing code (see _find).
# Nothing is synced here (see the header) — the override exists for a checkout that keeps its data
# somewhere else, not because copies are distributed.
_SUBSCRIPTION_USD_PER_ACCOUNT = _env_float("CLAUDE_MAX_PRICE_USD", 200.0)
_ANCHOR_USD_PER_TOKEN = 9.3e-8  # $0.093/M research fallback when usage history is empty
_MONTHLY_DAYS = 30
_USAGE_HISTORY = Path.home() / ".claude" / ".claude-manager" / "usage-history.json"
_MANAGER_ACCOUNTS = Path.home() / ".claude" / "manager-accounts"
#: Claude Code's OWN append-only transcripts — the PRIMARY source of token usage, and the one that
#: survives the Claude Manager extension. Every assistant message carries `message.usage` (input,
#: output, cache read, cache creation), `message.model` and a `timestamp`, plus `message.id` +
#: `requestId` to deduplicate a message replayed across resumed/compacted session files.
_TRANSCRIPT_ROOT = Path.home() / ".claude" / "projects"
#: Bumped whenever a COUNTING RULE in `collect_from_transcripts` changes (day bucketing, dedup,
#: which fields are summed). A store stamped below this has its TRANSCRIPT-sourced days dropped
#: and re-derived once, so an old rule's numbers cannot survive behind the never-shrinks guard.
#: Extension-sourced days are never touched by it — they cannot be re-derived from anything.
#: v2 = local-day bucketing + max-wins dedup (2026-09-06).
#: v3 = a call books to its EARLIEST sighting's day, so the walk no longer depends on the order
#: `rglob` happens to return files in (2026-09-06).
_COLLECTOR_VERSION = 3
_USAGE_KEYS = (
    "input_tokens",
    "output_tokens",
    "cache_read_input_tokens",
    "cache_creation_input_tokens",
)


def _find(name: str, env: str) -> Path:
    """env override → next to this script → hub kilo-benchmarks (dev). No sync is involved: the
    co-located branch exists for a checkout that carries its own copy, not because one is distributed."""
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

    This closed a real divergence: a vendor-qualified or dotted id got the right family PRICE and
    silently missed its cache override — correct on the small term, 4x wrong on the dominant one.

    ⚠️ SCOPE, stated because an earlier docstring and its commit message overclaimed "ONE key space":
    this canonicalises the CACHE key space only. Price lookup still goes through `_norm_model`, which
    scans the WHOLE string (vendor prefix included) for a tier word and returns `claude-code/<tier>`.
    Two alphabets, deliberately, and they CAN disagree: a vendor path containing a tier word
    (`opus-labs/claude-sonnet-5`) would price as opus while its cache resolved off sonnet. No such
    prefix exists in this fleet's vocabulary — named here as latent rather than "fixed" with a
    normalisation no caller needs.
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
        # BOTH sides through `_model_key`: folding only the query left a table key written in the
        # natural marketing form (`claude-fable-5.1`) matching nothing at all — not even the
        # byte-identical query — and silently returning the 0.1 default. The file's own header calls
        # it MANUAL, so the next hand-added row is exactly where that would have bitten.
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
    """② the pre-computed fleet rate a CONSUMER reads from the sidecar (fail-soft to the anchor).

    Not "the rate a PROJECT uses from the synced sidecar": this module is in no sync manifest and the
    sidecar exists in one `/opt` dir, so there is no project reading a synced copy. The header retracts
    that claim; these three comments were its surviving mirrors, caught by the closing verification pass.
    """
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
    """Take a full `claude -p --output-format json` object (or its bare `usage` block) → ①+② + tokens.

    Raises `TypeError` on a payload that is valid JSON but not an object — an error envelope, a
    stream-style message LIST, a truncated response. `refresh()` was hardened against exactly that
    shape on the sidecar it reads; this is the module's OWN documented primary invocation
    (`claude -p … | python scripts/claude_p_cost.py`) and it was still dying with a bare
    `AttributeError`, bypassing `main()`'s stated `exit 2` contract for unusable stdin.
    """
    if not isinstance(claude_json, dict):
        raise TypeError(
            f"expected a JSON object from `claude -p --output-format json`, got {type(claude_json).__name__}"
        )
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
#: What the Claude subscription ACTUALLY COST, per calendar month (operator, 2026-09-05: "may june
#: july we paid 600$ august and september we are paying 800$"). Authoritative over any per-account
#: arithmetic: the fee is the fee, and it changed when the account count did.
#:
#: ⚠️ A SCHEDULE, NOT A CONSTANT, because the previous flat $800 silently rewrote history — it priced
#: May, June and July at a fee that was not paid until August, overstating three months by 33%.
#:
#: ⚠️ EXCEPTIONS ONLY. **$800/month is the STANDING default** (operator, 2026-09-05: "from now on if i
#: dont state otherwise we will pay 800"), so a month is listed here ONLY where the fee differed.
#: Every unlisted month — including every future one — prices at :data:`_CURRENT_MONTHLY_SPEND` with
#: no edit. When the fee changes again, pin the months at the OLD fee here before changing the
#: default, and every past month keeps its own truth. A row equal to the default is not a fact; it
#: teaches the next reader that months must be listed to be priced, which is the opposite of the
#: contract — `tests/test_spend_calendar_months.py` refuses one.
_MONTHLY_SPEND: dict[str, float] = {
    "2026-05": 600.0,
    "2026-06": 600.0,
    "2026-07": 600.0,
}
_CURRENT_MONTHLY_SPEND = _env_float("CLAUDE_MONTHLY_SPEND_USD", 800.0)


def _spend_for_month(ym: str) -> float:
    """The fee paid for `YYYY-MM`; the current rate for any month not in the schedule.

    ⚠️ **Changing `_CURRENT_MONTHLY_SPEND` RETROACTIVELY REPRICES every unlisted past month**, because
    an unlisted month has no fee of its own — it borrows today's. So the order is fixed: PIN the
    months that were paid at the old fee into `_MONTHLY_SPEND` first, in the same change that moves
    the default. Deliberately not mechanised (FIX DIRECTIVE 5): the fee has changed once in five
    months, by the operator, and a detector for a twice-a-year manual step is wallpaper. Raised by an
    author-blind finder 2026-09-05 and adjudicated as a documented order-of-operations, not a guard.
    """
    return _MONTHLY_SPEND.get(ym, _CURRENT_MONTHLY_SPEND)


def _days_in_month(ym: str) -> int:
    y, m = int(ym[:4]), int(ym[5:7])
    nxt = datetime.date(y + (m == 12), (m % 12) + 1, 1)
    return (nxt - datetime.date(y, m, 1)).days


def _prorated_spend(start: datetime.date, end: datetime.date) -> float:
    """Fee for an arbitrary INCLUSIVE date span, pro-rated across the months it crosses.

    The 30-day rolling window straddles two months, so charging it one month's whole fee is wrong in
    both directions depending on where the window sits. Each day carries its own month's daily rate.
    """
    total, d = 0.0, start
    while d <= end:
        ym = d.strftime("%Y-%m")
        total += _spend_for_month(ym) / _days_in_month(ym)
        d += datetime.timedelta(days=1)
    return total


#: Relative price weight per Claude tier — an OPERATOR ASSUMPTION, recorded 2026-09-05, not a
#: measurement. Stated as: "haiku price is 1x, sonnet 2x, opus 5x, fable 10x. ok save this as
#: assumption." It matches the live Anthropic list prices exactly ($1/$2/$5/$10 per input MTok, so
#: 1:2:5:10), which is why it is a sound proxy — but it is carried as an ASSUMPTION because the
#: subscription is a flat fee with no per-model billing to verify against. If list prices move, the
#: ratio moves and this constant must be re-derived; `tests/test_tier_weights.py` pins it to the
#: live price file so a divergence fails loudly instead of silently re-weighting the split.
_TIER_WEIGHT: dict[str, float] = {"haiku": 1.0, "sonnet": 2.0, "opus": 5.0, "fable": 10.0}


def _tier_of(model_id: str) -> str | None:
    """`claude-opus-5` / `claude-haiku-4-5-20251001` → the tier key in :data:`_TIER_WEIGHT`."""
    m = (model_id or "").lower()
    for tier in _TIER_WEIGHT:  # no substring collisions among these four
        if tier in m:
            return tier
    return None


def _usage_store_path() -> Path:
    """Our OWN daily usage store — the thing that outlives the Claude Manager extension."""
    return _find("claude_usage_daily.json", "CLAUDE_USAGE_DAILY")


def _transcript_root() -> Path:
    env = os.getenv("CLAUDE_TRANSCRIPTS")
    return Path(env) if env else _TRANSCRIPT_ROOT


def _local_day(ts: object) -> str:
    """A transcript timestamp → the LOCAL calendar day it belongs to. "" when unusable.

    ⚠️ LOCAL, not UTC, and the difference is not cosmetic. Transcripts stamp UTC (`…Z`); this box runs
    +03:00, and 14.2% of usage records fall in UTC 21:00–23:59 — which is already tomorrow where the
    operator lives. Slicing `timestamp[:10]` therefore files roughly a seventh of every evening's
    tokens under the previous day's calendar cell, on a page whose every other date (the fee months,
    `built_at`, "today") is local. The extension's days were local too, so UTC bucketing also added
    noise to the very comparison that decided history is not re-derived — re-measured both ways, the
    median 0.54x holds under either, so that conclusion never rested on this.

    Costs ~1.1s per full walk over 1.2M records against ~50s of I/O — measured, not assumed.

    A NAIVE-BUT-VALID stamp falls back to the leading date slice — better the UTC day than no day,
    since dropping the record would lose real spend. ⚠️ The fallback is not unconditional, and an
    earlier version of this paragraph said it was: a stamp whose DATE is itself invalid
    (`2026-02-30`, `2026-13-01`) fails the slice too and returns `""`, and its caller then skips the
    record entirely. That is the only correct answer — a record with no derivable day cannot be
    booked anywhere — but it is a DROP, not a fallback, and the difference matters to whoever next
    reasons about where a missing token went. Never raises, either way.
    """
    text = str(ts or "")
    if len(text) < 10:
        return ""
    try:
        parsed = datetime.datetime.fromisoformat(text.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        parsed = None
    if parsed is not None and parsed.tzinfo is not None:
        return parsed.astimezone().date().isoformat()
    try:
        return datetime.date.fromisoformat(text[:10]).isoformat()
    except (ValueError, TypeError):
        return ""


def collect_from_transcripts(root: Path | None = None) -> dict[str, dict[str, int]]:
    """Per-day, per-model token totals read from Claude Code's OWN transcripts. Never raises.

    WHY THIS EXISTS. The store was backfilled from `~/.claude/.claude-manager/usage-history.json`,
    which the Claude Manager EXTENSION writes. That file stopped being written on 2026-09-04 17:31
    while usage continued, so the store simply froze — the failure mode a derived observer always
    has and a primary record does not. These transcripts ARE the primary record: Claude Code appends
    every assistant message with its own `usage` block, and it does so whether or not any extension
    is installed.

    ⚠️ THE TWO SOURCES DO NOT MEASURE THE SAME THING, AND WHICH IS RIGHT IS NOT SETTLED. Measured on
    the 111 days both hold (2026-09-06): this walk's DEDUPED totals are a median 0.54x the extension's,
    while the same records UNDEDUPED are a median 1.13x. The extension's number therefore sits BETWEEN
    them — consistent with it summing replays that this walk collapses, since 55% of usage records are
    repeats of a call already counted.

    ⚠️ An earlier version of this paragraph asserted the gap was TRANSCRIPT PRUNING — "session files
    age out" — as established fact, and repeated it in the tests, the changelog and two ledger rows.
    It is not established: the tree spans 2026-05-16..today, essentially the whole recorded period, so
    files are not aging out wholesale. Some older days do hold less even undeduped, so loss is real
    somewhere; the 0.54x is not explained by it alone. Recorded as UNKNOWN rather than re-explained,
    because a plausible story repeated five times is how a guess becomes a premise.

    What that leaves is the design, on the honest ground: history is NOT re-derived from here because
    we cannot say which source is right, and the extension's 111 days cannot be rebuilt if we are
    wrong. Refusing to overwrite an irreplaceable record under uncertainty needs no theory of WHY the
    two disagree. This collector must also run DAILY — whatever the explanation, it can only capture a
    day while that day's transcripts still hold it. See :func:`merge_usage_store` (D-143, D-145).

    DEDUPLICATION is on `(message.id, requestId)`, MAX-WINS. A session that was resumed or compacted
    replays earlier messages into new files, and a message is re-serialised as its usage accrues:
    measured on this box, 1,240,230 usage records collapse to 554,811 keys, and 153,400 of the
    repeats DISAGREE on their totals. First-wins banks the partial sighting — 159,866,901 tokens lost
    across the tree — so the largest sighting is taken instead. Every record measured carries both
    keys (0 of 13,113 on the probe day lacked them); one that lacks both is COUNTED rather than
    dropped, since losing real spend is the worse error.

    SIDECHAIN (subagent) messages are COUNTED. They are billed to the same subscription, and the
    question this store answers is what the subscription was spent on — not what the operator typed.

    Cost of a full walk: ~50s over 14,090 files / 8.8 GB (measured 2026-09-06), which is why it runs
    on the daily cron and not per page view.
    """
    root = root or _transcript_root()
    out: dict[str, dict[str, int]] = {}
    seen: dict[tuple, tuple[str, str, int]] = {}  # (id, requestId) -> (day, model, best tokens)
    try:
        paths = sorted(root.rglob("*.jsonl"))
    except OSError:
        return {}
    for path in paths:
        try:
            handle = path.open(encoding="utf-8", errors="replace")
        except OSError:
            continue
        with handle:
            for line in handle:
                # Cheap reject before the JSON parse: most transcript lines are user turns and tool
                # results, and parsing 1.2M of them to discard them costs more than the walk itself.
                if '"usage"' not in line:
                    continue
                try:
                    rec = json.loads(line)
                except (ValueError, TypeError):
                    continue
                if not isinstance(rec, dict):
                    continue
                msg = rec.get("message")
                usage = msg.get("usage") if isinstance(msg, dict) else None
                if not isinstance(usage, dict):
                    continue
                day = _local_day(rec.get("timestamp"))
                if not day:
                    continue
                tok = 0
                # the SAME four fields `measure()` already sums — one vocabulary for what a token is.
                # ⚠️ `math.isfinite` and the bool exclusion are not fussiness: `json.loads` accepts a
                # bare `NaN`/`Infinity`, `isinstance(v, (int, float))` admits both, and `int()` then
                # raises — killing the WHOLE walk on one poisoned line. Because the line stays on
                # disk, every later run dies too and the store freezes silently: the exact failure
                # this collector exists to prevent, and the docstring promises "never raises". A bool
                # is likewise not a token count (`True` would add 1). Found by two independent
                # author-blind finders, 2026-09-06.
                for f in _USAGE_KEYS:
                    v = usage.get(f)
                    if isinstance(v, bool) or not isinstance(v, (int, float)):
                        continue
                    if not math.isfinite(v):
                        continue
                    tok += int(v)
                model = msg.get("model")
                if tok <= 0 or not isinstance(model, str) or not model:
                    continue
                # DEDUP, MAX-WINS — not first-wins, and the difference is measured, not aesthetic.
                # 1,240,230 usage records on this box collapse to 554,811 keys: 55% are repeats, and
                # 153,400 of those repeats DISAGREE on their totals (largest gap 1,008,284 tokens),
                # because a message is re-serialised as its usage accrues. Keeping the first sighting
                # therefore banks a PARTIAL: measured at 159,866,901 tokens lost across the tree.
                # Usage for a call can only be discovered, never un-happen, so the largest sighting is
                # the true one — and where duplicates agree, max is first-wins by another name.
                key = (msg.get("id"), rec.get("requestId"))
                if not all(k is None or isinstance(k, (str, int, float)) for k in key):
                    # An unhashable id (a dict, a list) would raise on `seen.get(key)` and take the
                    # whole walk with it — every LATER file included, since the walk is one loop.
                    # Count the record without deduping it: losing one call to a double-count is a
                    # rounding error, losing every day after it is the outage.
                    out.setdefault(day, {})[model] = out.setdefault(day, {}).get(model, 0) + tok
                    continue
                if key == (None, None):
                    # No key to dedup on: COUNT it. Dropping would lose real spend, and duplicates
                    # without keys are unmeasured rather than known (0 of 13,113 on the probe day).
                    out.setdefault(day, {})[model] = out.setdefault(day, {}).get(model, 0) + tok
                    continue
                prior = seen.get(key)
                if prior is None:
                    seen[key] = (day, model, tok)
                    out.setdefault(day, {})[model] = out.setdefault(day, {}).get(model, 0) + tok
                    continue
                p_day, p_model, p_tok = prior
                # THE BOOKING IS (earliest day, model of the LARGEST sighting, largest tokens), and
                # every part of that triple must be order-independent or two boxes reading the same
                # tree disagree. Day: `min`, since a call belongs where it started. Tokens: `max`,
                # since usage accrues and the first sighting is often a partial. MODEL: the largest
                # sighting's, because that is the sighting the tokens came from — an earlier version
                # kept the tokens and DISCARDED that model, booking (measured) 1,000,000 opus tokens
                # as haiku, and 68 of 300 randomised trials lost the max sighting's model while 65
                # of 300 were order-dependent. Ties break lexicographically so a tie cannot depend
                # on traversal order either. Found by an author-blind arithmetic finder, 2026-09-06;
                # latent on today's tree (0 of 12,190 sampled keys carry two models) and a real
                # per-model $ error the moment it fires, since every consumer prices per model.
                best_day = min(p_day, day)
                if tok > p_tok:
                    best_model, best_tok = model, tok
                elif tok == p_tok:
                    best_model, best_tok = min(model, p_model), p_tok
                else:
                    best_model, best_tok = p_model, p_tok
                if (best_day, best_model, best_tok) == prior:
                    continue
                # Withdraw the old booking whole, then place the new one — never patch a delta
                # across a changed day or model, which is where the arithmetic used to drift.
                cell = out.get(p_day, {})
                cell[p_model] = cell.get(p_model, 0) - p_tok
                if cell.get(p_model, 0) <= 0:
                    cell.pop(p_model, None)
                if not cell:
                    out.pop(p_day, None)
                out.setdefault(best_day, {})[best_model] = (
                    out.setdefault(best_day, {}).get(best_model, 0) + best_tok
                )
                seen[key] = (best_day, best_model, best_tok)
    return out


def merge_usage_store() -> dict:
    """Upsert every day of `usage-history.json` into our own store, and return the merged store.

    WHY A SECOND STORE AT ALL. `~/.claude/.claude-manager/usage-history.json` is the EXTENSION'S
    output. The operator intends to remove that extension, and the moment it goes the file stops
    being written — so a view that reads it directly goes stale silently and 111 days of recorded
    history become unreadable the day the extension is uninstalled. This store is ours: once a day
    has been merged it is kept, whatever happens upstream.

    MERGE-FORWARD, NOT COPY. Days are upserted by date, so the FIRST run is the backfill (all 111
    days the extension has recorded, 2026-05-13 onward) and every later run simply adds the new ones.
    That means there is no separate one-shot script to remember to run, and re-running is harmless —
    which is the property a backfill most needs, because a backfill that can only be run once
    correctly is a backfill nobody dares re-run.

    ⚠️ A day already in the store is REFRESHED from the source while the source still has it, not
    skipped: the extension writes a day's totals as the day progresses, so an early merge would
    otherwise freeze a partial day forever. Once the source drops a day (or the extension goes), the
    stored copy simply stands — last known good, never silently zeroed.

    Stores RAW per-model tokens, not tiered totals: the tier weights are an assumption that may be
    re-derived, and a store that has already collapsed models into tiers cannot be re-weighted.
    """
    path = _usage_store_path()
    # ⚠️ SERIALISE THE WHOLE READ-MODIFY-WRITE, not just the write. `os.replace` already makes the
    # write atomic, which prevents a TORN file and does nothing at all about a LOST UPDATE: two
    # processes both read 112 days, each adds a different day, and the second `replace` erases the
    # first one's. That is not hypothetical here — the 06:00 cron and any session running `--refresh`
    # are exactly two such processes, and I ran one by hand while the cron was armed. The store is the
    # only durable copy of 112 days of usage, so the lock covers from the read to the rename.
    # Fail-open by design: a platform without `fcntl`, or a lock file we cannot create, must not stop
    # the merge — an unlocked merge is the status quo, a refused one loses the day entirely.
    lock = None
    try:
        import fcntl

        lock = open(str(path) + ".lock", "w")  # noqa: SIM115 — released in the finally below
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
    except (ImportError, OSError):
        if lock is not None:
            lock.close()
        lock = None
    try:
        return _merge_usage_store_locked(path)
    finally:
        if lock is not None:
            lock.close()  # closing the fd releases the flock


def _is_iso_day(value: object) -> bool:
    """True when `value` is a `YYYY-MM-DD` string a date can be built from."""
    try:
        datetime.date.fromisoformat(str(value))
    except (TypeError, ValueError):
        return False
    return True


def int_or_zero(value: object) -> int:
    """`int(value)`, or 0 for anything that will not convert. A corrupt version stamp migrates
    rather than killing the 06:00 refresh — `int("two")` used to raise straight out of the merge."""
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


class StoreUnwritableError(RuntimeError):
    """The merged store could not be written — recording has STOPPED and must not read as success.

    ⚠️ This is a `RuntimeError` on purpose. The write already raised `OSError`, and the comment above
    it called that "deliberately loud" — but the only production caller, `per_model_spend`, catches
    `(OSError, ValueError, TypeError, AttributeError)` around its merge, so the loudness died one
    frame up: an unwritable store directory left `refresh()` returning normally, the sidecar written,
    the cron step GREEN, and the day unrecorded. The store and the sidecar live in different
    directories, so one can be unwritable while the other is fine. A distinct exception the caller
    does not catch is what makes the failure reach the operator. Found by an author-blind data-loss
    finder, 2026-09-06.
    """


class StoreUnreadableError(RuntimeError):
    """The store file EXISTS and cannot be parsed — so it must not be overwritten."""


def _merge_usage_store_locked(path: Path) -> dict:
    """The body of :func:`merge_usage_store`, run while the store lock is held.

    ⚠️ AN UNPARSEABLE STORE IS REFUSED, NOT DEGRADED — the asymmetry that matters most in this file.
    An earlier version caught every read failure and continued with `days = {}`, then wrote that back:
    a truncated or hand-broken file therefore REPLACED 113 days and 298 BILLION tokens with an empty
    object, and with the extension dead and transcripts pruned there was nothing left to rebuild it
    from. Reproduced before this guard existed: 28 seeded days in, 0 days on disk out.

    The distinction is ABSENCE versus DAMAGE, and only the first is a legitimate empty start:
      • no file at all      → a fresh box's first run; proceed with no history and write.
      • a file that is there but will not parse → raise. The old bytes stay on disk for repair, and
        the 06:00 cron fails LOUDLY, which is the only way anyone learns the store needs attention.
    Losing one day's merge is recoverable; overwriting the only copy is not.
    """
    days: dict = {}
    store: dict = {}
    unusable: dict = {}
    if path.exists():
        try:
            store = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise StoreUnreadableError(f"{path} exists but does not parse: {exc}") from exc
        if not isinstance(store, dict):
            raise StoreUnreadableError(f"{path} exists but is not a JSON object")
        raw = store.get("days")
        if raw is not None and not isinstance(raw, dict):
            raise StoreUnreadableError(f"{path} has a 'days' key that is not an object")
        # Per-DAY damage is different again: one bad entry must not refuse the whole merge, and it
        # must not be DELETED either. Unusable entries are held aside and written back untouched —
        # sanitise for USE, preserve for STORAGE — so a day this code cannot interpret survives for
        # a human to repair instead of vanishing on the next cron run.
        for k, v in (raw or {}).items():
            if isinstance(v, dict):
                clean = {
                    m: t
                    for m, t in v.items()
                    if isinstance(t, (int, float)) and not isinstance(t, bool)
                }
                if len(clean) == len(v):
                    days[k] = clean
                else:
                    days[k] = clean
                    unusable[k] = {m: t for m, t in v.items() if m not in clean}
            else:
                unusable[k] = v
    src_by: dict = (
        store.get("source_by_day") if isinstance(store.get("source_by_day"), dict) else {}
    )
    added = 0
    try:
        src = (json.loads(_USAGE_HISTORY.read_text(encoding="utf-8")).get("days")) or {}
    except (OSError, ValueError, TypeError, AttributeError):
        src = {}
    for k, day in src.items():
        try:
            datetime.date.fromisoformat(k)
        except (ValueError, TypeError):
            continue
        by = {}
        if not isinstance(day, dict):
            continue
        for mid, m in (day.get("byModel") or {}).items():
            # THE THIRD PARSE PATH, and the last one still unguarded. The transcripts and the store
            # both tolerate a poisoned value now; this one did not, so a single non-numeric field in
            # the extension's file raised straight out of the merge and stopped recording — the same
            # outage class, reached through the one door left open. Found by a round-10 finder.
            if not isinstance(m, dict):
                continue
            tok = 0
            for x in ("input", "output", "cacheRead", "cacheCreation"):
                v = m.get(x)
                if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
                    continue
                tok += int(v)
            if tok > 0:
                by[mid] = tok
        if not by:
            continue
        if k not in days:
            added += 1
            days[k] = by
        else:
            # PER-MODEL max here too, for the same reason as the transcript branch below: the source
            # is re-read every run so a partial day keeps growing, and that same re-read shrinks the
            # day if the upstream file is ever truncated, reset or restored from an older copy. One
            # invariant for the whole store — a stored day never shrinks, whatever wrote it.
            for mid, tok in by.items():
                days[k][mid] = max(int(days[k].get(mid, 0)), int(tok))
        src_by[k] = "extension"

    # ── the transcripts: FILL-FORWARD ONLY, never a rewrite of recorded history ──────────────────
    # The extension's file stopped on 2026-09-04 17:31 while usage carried on, so without this the
    # store simply freezes. `collect_from_transcripts` reads Claude Code's own primary record, which
    # is written whether or not any extension is.
    #
    # ⚠️ IT NEVER OVERWRITES A RECORDED DAY, and the measurement says so louder than caution would:
    # across the 111 days BOTH sources hold the transcripts have a MEDIAN 0.54x the extension's tokens
    # (186.8B against 298.1B in total), because session files are PRUNED as they age. Re-deriving
    # history from them would not enrich the past, it would DELETE about 111B tokens of it. So a day
    # is written from transcripts only when NO extension record exists for it, or when the day was
    # itself transcript-sourced (today's partial day must keep refreshing), and a day carrying no
    # source marker reads as history — the fail direction that protects data. `_discrepancy`
    # publishes the overlap so the two sources stay comparable on their own evidence.
    # ⚠️ RULE CHANGES RE-DERIVE THE TRANSCRIPT DAYS, ONCE — but only where a replacement EXISTS.
    # The drop used to run BEFORE the walk and the version stamp was written regardless, so a rule
    # bump on a day whose transcripts had since pruned deleted it outright: reproduced at 13 BILLION
    # tokens lost, and one-shot, so the next run could not repair it. The premise "a transcript day
    # is re-derivable by construction" is contradicted by this module's own pruning measurement —
    # 0.54x median. Collect FIRST, then swap in the re-derived value only for days the tree still
    # holds; anything it no longer holds keeps its recorded value and its marker. Found by an
    # author-blind data-loss finder, 2026-09-06.
    tdays = collect_from_transcripts()
    pending = [k for k, v in src_by.items() if v == "transcripts"]
    migrating = int_or_zero(store.get("collector_version")) < _COLLECTOR_VERSION
    # ⚠️ A BLIND RUN MIGRATES NOTHING — not a drop, not a freeze. An empty walk means "could not
    # look", and concluding "unreachable, freeze it" from that would convert a transient unmounted
    # tree into a permanent verdict about somebody's data.
    if migrating and tdays:
        for k in pending:
            if k in tdays:  # a replacement is in hand
                days.pop(k, None)
                src_by.pop(k, None)
            elif k == datetime.date.today().isoformat():
                # NEVER freeze TODAY. Today's transcripts may simply not exist yet at 06:00, and
                # "no data at this instant" is not "no data ever" — freezing it would lock a partial
                # day at whatever it held before the sun came up.
                continue
            else:
                # NO replacement, and for a past day there never will be one — its transcripts are
                # gone. Say so: `frozen` means "came from transcripts, no longer re-derivable". It
                # keeps its recorded value, stops being pending, and is never dropped by a later
                # migration. Without this the two failure modes are a straight trade — leave it
                # pending and one unreachable day blocks every future migration, or advance anyway
                # and the stamp claims a migration that skipped 99 days. Naming the state ends the
                # trade. Raised as two separate defects by a confirming-round finder.
                src_by[k] = "frozen"
    # ⚠️ THE STAMP ADVANCES ONLY IF THE WALK COULD SEE. A one-shot migration that consumes itself on a
    # run where the transcript root was unmounted, unreadable or empty would silently skip the
    # re-derivation FOREVER — the next run reads an up-to-date stamp and never retries. `tdays` empty
    # while days are pending means "could not look", not "nothing to do", and those are opposite
    # answers. Retrying costs one walk we were doing anyway. Found by a closing-pass finder.
    stamp_ok = bool(tdays) or not pending
    # `pending` is now exactly the days that were re-derivable or newly frozen, so an advance here
    # means every transcript-marked day was ACTUALLY handled — not that one day happened to be in
    # the tree while the rest were skipped.

    t_added = t_refreshed = 0
    for k, by in tdays.items():
        if not by:
            continue
        if k not in days:
            days[k], src_by[k] = by, "transcripts"
            t_added += 1
        elif src_by.get(k) == "transcripts":
            # A STORED DAY NEVER SHRINKS. Today is partial all day, so a transcript-sourced day must
            # keep refreshing — but the same re-read is what erodes it later: once that day's session
            # files are pruned the walk returns LESS, and a plain assignment would quietly write the
            # smaller number over a total that was once measured in full. Usage cannot un-happen, so
            # the larger sighting stands and this store keeps being the durable aggregate the
            # transcripts are not.
            # PER-MODEL max, not a total comparison. A whole-day total can be larger while having
            # LOST a model — one session's transcript prunes while another grows — and replacing on
            # the total would drop that model from the day's tier split entirely. Each model's daily
            # total can only be discovered, so the best observation of each is kept.
            merged = dict(days[k])
            for mid, tok in by.items():
                merged[mid] = max(int(merged.get(mid, 0)), int(tok))
            if merged != days[k]:
                days[k] = merged
                t_refreshed += 1
    overlap = sorted(k for k in tdays if src_by.get(k) == "extension")
    # BOUNDED ON PURPOSE — the last 7 overlapping days, not the whole overlap, so the store does not
    # grow a second copy of itself. `_discrepancy_days` states the population the sample came from,
    # because a 7-row sample with no denominator reads as the whole comparison.
    disc = {
        k: {"extension": sum(days[k].values()), "transcripts": sum(tdays[k].values())}
        for k in overlap[-7:]
    }

    # Write the merged days back, then RESTORE anything this run could not interpret. A day (or a
    # single model entry) whose shape the arithmetic cannot use is still somebody's recorded spend:
    # dropping it silently would mean the next cron run erases data no other copy holds. It rides
    # along untouched, under `_unusable`, where a human can see it and repair it.
    out_days = dict(sorted(days.items()))
    for k, v in unusable.items():
        if isinstance(v, dict) and isinstance(out_days.get(k), dict):
            # ⚠️ PRESERVED, never PREFERRED. `{**merged, **unusable}` let the unusable value win, so a
            # model whose stored value was corrupt AND which the transcripts now supply correctly was
            # clobbered straight back to the corrupt one — reproduced: a stored `"corrupt"` survived
            # over a real 900,000. Restoration exists so damaged data is not silently deleted; it must
            # never outrank a value this run actually measured. Found by a round-6 finder.
            out_days[k] = {**v, **out_days[k]}
        elif k not in out_days:
            out_days[k] = v
    store["days"] = dict(sorted(out_days.items()))
    # LIST ONLY WHAT ACTUALLY SURVIVED. A scalar day the extension has since supplied properly is
    # SUPERSEDED rather than preserved — the good value replaces it, which is the outcome we want —
    # but listing that day here would claim the file still carries something uninterpretable when it
    # does not. Same class as the day counter and the staleness signal: a diagnostic that overstates
    # is a diagnostic that lies. Raised by a round-11 finder.
    still_unusable = sorted(
        k
        for k, v in unusable.items()
        if (isinstance(v, dict) and any(mid in out_days.get(k, {}) for mid in v))
        or (not isinstance(v, dict) and out_days.get(k) is v)
    )
    store["_unusable"] = (
        {
            "days": still_unusable,
            "note": "shapes this collector cannot interpret, preserved verbatim in `days`",
        }
        if still_unusable
        else {}
    )
    store["source_by_day"] = dict(sorted(src_by.items()))
    store["_discrepancy"] = disc
    store["_discrepancy_days"] = len(overlap)
    if stamp_ok:
        store["collector_version"] = _COLLECTOR_VERSION
    # ⚠️ THE RUN COUNTERS MUST BE SET BEFORE THE WRITE. They used to be attached to `store` AFTER
    # `os.replace`, so the file never carried them and a reader saw the PREVIOUS run's values — on a
    # producer whose only in-file signal of what it did is exactly these numbers, and which nobody
    # watches because it runs at 06:00. `extension_source_present` is here for the same reason: it is
    # how a reader learns that source 1 has stopped, which is the event that made this collector
    # necessary and which nothing else in the file records. Found by a closing-pass finder.
    # `_total_days` describes THE FILE, not the working dict — they diverge by exactly the
    # preserved-but-unusable days, which are restored into `out_days` after `kept` was taken. A
    # counter that disagrees with the thing it counts is a diagnostic that lies, which is the same
    # defect class as the staleness signal two rounds ago. Raised (via a wrong line-order claim) by a
    # round-8 finder; the claim was wrong and the adjacent discrepancy was real.
    store["_added"], store["_total_days"] = added, len(out_days)
    store["_transcript_added"], store["_transcript_refreshed"] = t_added, t_refreshed
    # ⚠️ The LAST DAY, not `.exists()`. My first version of this signal asked whether the file was
    # there — and it is there, five days after it stopped being written, so it answered True and told
    # a reader nothing. The question that matters for an unattended producer is whether source 1 is
    # still ADVANCING, and only its newest day answers that. Caught by running the real production
    # path and reading the value, which is the check a proxy would have passed.
    # `max` over VALIDATED keys: `src` is the extension's raw dict, so a junk key would win the
    # comparison and be published as the source's newest day — a diagnostic that lies is worse than
    # one that is absent. Raised by a round-7 finder.
    _src_days = [k for k in src if _is_iso_day(k)]
    store["extension_last_day"] = max(_src_days, default=None)
    store["source"] = str(_USAGE_HISTORY)
    store["transcript_source"] = str(_transcript_root())
    store["merged_at"] = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
    # ATOMIC — three sessions and a cron share this box; a torn write here loses history that the
    # upstream file may no longer be able to replace. ⚠️ A write failure here is DELIBERATELY LOUD:
    # an unwritable store path (a mis-set `CLAUDE_USAGE_DAILY`, a missing parent directory, a full
    # disk) means usage has stopped being recorded, which is the exact failure this whole collector
    # exists to prevent. Swallowing it would hide the outage behind a green cron.
    try:
        fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp")
    except OSError as exc:
        raise StoreUnwritableError(f"cannot create a temp file beside {path}: {exc}") from exc
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(store, indent=2) + "\n")
            fh.flush()
            # fsync before the rename: `os.replace` is journaled while the tmp file's DATA may not
            # be, so a power loss can otherwise leave a zero-length store — on the only durable copy.
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except OSError as exc:
        Path(tmp).unlink(missing_ok=True)
        raise StoreUnwritableError(f"cannot write {path}: {exc}") from exc
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
    return store


def per_model_spend(days_back: int = _MONTHLY_DAYS) -> dict:
    """Split the flat subscription across TIERS by weighted token share, plus a daily series.

    THE PROBLEM. `amortized_per_mtok` is one flat rate — the subscription over every token the box
    ran — so an Opus token and a Haiku token price identically. It can say what the fleet spends,
    never where.

    THE FORMULATION. With weights w (:data:`_TIER_WEIGHT`) and per-tier token totals T::

        b = SPEND / Σ(T_t × w_t)        rate_t = b × w_t        cost_t = T_t × rate_t

    so `Σ cost_t == SPEND` EXACTLY. That identity is the audit: an allocation that does not sum to
    the money actually paid is arithmetic, not accounting.

    ⚠️ AGGREGATED BY TIER, NOT BY MODEL VERSION (operator directive 2026-09-05: *"i did not tell you
    to separate model versions ... opus, fable, sonnet, haiku, as the multipliers are same"*). Every
    Opus generation shares one weight because they share one list price — verified live: Opus 5 and
    Opus 4.8 are both $5/$25, Fable 5 and Fable 5.1 both $10/$50. Splitting them added rows without
    adding information. `models` is kept BESIDE `tiers` as the audit trail — which concrete ids rolled
    into each tier — because a tier total whose members you cannot see is unverifiable.

    `daily` carries per-day per-tier tokens for the calendar view: one entry per date in the window,
    zero-filled, so a gap renders as a real quiet day rather than vanishing from the axis.
    """
    today_d = datetime.date.today()
    today = today_d.isoformat()
    cutoff_d = today_d - datetime.timedelta(days=days_back - 1)
    cutoff = cutoff_d.isoformat()
    try:
        counted: int | None = sum(
            1 for p in _MANAGER_ACCOUNTS.iterdir() if p.is_dir() and not p.name.startswith(".")
        )
    except OSError:
        counted = None
    # `counted` is now REPORTING ONLY: the fee comes from the schedule, not from multiplying an
    # account count by a per-seat price. The two used to be the same number by coincidence (4 x $200)
    # and stopped being so the moment the fee changed independently of the seat count.
    # PRO-RATED across the months the window crosses — see `_prorated_spend`. The old
    # `_SUBSCRIPTION_USD_PER_ACCOUNT * accounts` assumed one flat fee for all time and so priced
    # May-July at a rate that was not paid until August.
    spend = _prorated_spend(cutoff_d, today_d)

    tier_tok: dict[str, int] = {}
    model_tok: dict[str, int] = {}
    unweighted: dict[str, int] = {}
    per_day: dict[str, dict[str, int]] = {}
    try:
        # OUR store, merged forward from the extension's file (see `merge_usage_store`). Reading the
        # store rather than the extension's file is what keeps this working once that is removed.
        days = (merge_usage_store().get("days")) or {}
        for k, by_model in days.items():
            if not (cutoff <= k <= today):
                continue
            if not isinstance(by_model, dict):
                continue  # a preserved unusable DAY — see `merge_usage_store`'s `_unusable`
            for mid, raw in by_model.items():
                # ⚠️ SKIP THE ENTRY, NEVER ABANDON THE WALK. `int("abc")` raises, and the `except`
                # below wipes tier_tok/model_tok/unweighted/per_day wholesale — so ONE preserved
                # corrupt value blanked the ENTIRE Usage tab: 1,000,000 real opus tokens on the same
                # day vanished with it, tiers `{}` and daily `[]`, reproduced. That is the same
                # poisoned-record class the collector fixed one layer down, and the store now
                # PRESERVES such values by design (they are somebody's data), which is exactly what
                # made this reachable. Raised by two round-9 finders as "unusable values are
                # re-introduced"; the re-introduction is intended — the consumer's reaction was not.
                if isinstance(raw, bool) or not isinstance(raw, (int, float)):
                    continue
                if not math.isfinite(raw):
                    continue
                tok = int(raw)
                if tok <= 0:
                    continue
                tier = _tier_of(mid)
                if not tier:
                    unweighted[mid] = unweighted.get(mid, 0) + tok
                    continue
                tier_tok[tier] = tier_tok.get(tier, 0) + tok
                model_tok[mid] = model_tok.get(mid, 0) + tok
                per_day.setdefault(k, {})[tier] = per_day.setdefault(k, {}).get(tier, 0) + tok
    except (OSError, ValueError, TypeError, AttributeError):
        tier_tok, model_tok, unweighted, per_day = {}, {}, {}, {}

    weighted_total = sum(t * _TIER_WEIGHT[k] for k, t in tier_tok.items())
    if weighted_total <= 0:
        return {
            "window_start": None,
            "window_end": None,
            "spend_usd": None,
            "accounts": counted if (counted or 0) > 0 else None,
            "base_rate_per_mtok": None,
            "tiers": {},
            "models": {},
            "daily": [],
            "unweighted": unweighted,
        }
    base = spend / weighted_total * 1_000_000.0  # $/Mtok at weight 1.0 (haiku)
    total_tok = sum(tier_tok.values())
    tiers = {}
    for tier, tok in sorted(tier_tok.items(), key=lambda kv: -kv[1]):
        rate = base * _TIER_WEIGHT[tier]
        tiers[tier] = {
            "weight": _TIER_WEIGHT[tier],
            "tokens": tok,
            "share": tok / total_tok,
            "rate_per_mtok": rate,
            "cost_usd": tok / 1_000_000.0 * rate,
            "models": sorted(
                (m for m in model_tok if _tier_of(m) == tier), key=lambda m: -model_tok[m]
            ),
        }
    # Zero-filled so the calendar has a cell for EVERY date: a missing key would silently shorten
    # the axis and make a quiet day indistinguishable from a day the history never recorded.
    # ⚠️ TWO DIFFERENT WINDOWS, deliberately. The SPEND split above is 30 days because the
    # subscription is billed monthly — a rate computed over 111 days against one month's fee would be
    # nonsense. The CALENDAR below spans ALL recorded history (backfilled from the extension,
    # 2026-05-13 onward) because "what did we consume, and when" is a different question from "what
    # did this month cost", and truncating it to the billing window throws away the only
    # month-over-month comparison we have. Daily cost is therefore priced at the CURRENT base rate —
    # it answers "what would this day cost at today's rate", not "what was billed that month".
    cal_tier: dict[str, dict[str, int]] = {}
    for k, by_model in (days or {}).items():
        if not isinstance(by_model, dict):
            continue  # a preserved unusable DAY
        for mid, raw in by_model.items():
            # The SAME guard as the window loop above, and it needs saying twice because this loop
            # sits OUTSIDE that try — so an `int("abc")` here escaped `per_model_spend` entirely
            # rather than merely emptying it. Two unguarded `int()` calls on the same preserved data,
            # one of which no exception handler covered at all.
            if isinstance(raw, bool) or not isinstance(raw, (int, float)) or not math.isfinite(raw):
                continue
            t, tok = _tier_of(mid), int(raw)
            if t and tok > 0:
                cal_tier.setdefault(k, {})[t] = cal_tier.setdefault(k, {}).get(t, 0) + tok
    cal_start = datetime.date.fromisoformat(min(cal_tier)) if cal_tier else cutoff_d
    # Each MONTH gets its own base rate from its OWN fee and its OWN tokens, so a month block sums to
    # what that month actually cost — May-July at $600, August onward at $800. A single global rate
    # would restate history at today's price, which is the defect this schedule exists to end.
    # ROLLING, not calendar-month bucketed (operator, 2026-09-05: "rolling"). Each day D is priced
    # by the 30-day window ENDING on D: the fee pro-rated across the months that window crosses,
    # over the weighted tokens actually run in it. So a day in June is priced by June-era usage at
    # the $600 fee, and a day in September by September usage at $800 — historically faithful
    # without inventing month boundaries.
    #
    # WHY THIS BEAT CALENDAR BUCKETS. Month buckets forced a coverage fudge: September is 5 days
    # lived of 30 and May's history starts on the 13th, so charging each its whole fee made their
    # cells 5-6x darker than a complete month — an artefact of the bucket, not of usage. A trailing
    # window has no boundaries to be partial against, so that entire correction disappears.
    #
    # EARLY DAYS: the window is clamped to the first day we hold, and the fee is pro-rated over the
    # SAME clamped span — so a short window is not charged a full 30 days of subscription.
    wtok_by_day = {
        k: sum(tok * _TIER_WEIGHT[ti] for ti, tok in by.items()) for k, by in cal_tier.items()
    }
    day_rate: dict[str, float] = {}
    for k in cal_tier:
        d_end = datetime.date.fromisoformat(k)
        d_start = max(cal_start, d_end - datetime.timedelta(days=_MONTHLY_DAYS - 1))
        wt = sum(w for kk, w in wtok_by_day.items() if d_start.isoformat() <= kk <= k)
        fee = _prorated_spend(d_start, d_end)
        day_rate[k] = (fee / wt * 1_000_000.0) if wt > 0 else 0.0
    # ⚠️ The zero-fill is asymmetric ON PURPOSE (operator, 2026-09-05: "remove the months which does
    # not have data"). WITHIN a month every date gets a cell, so a quiet day stays visible and the
    # grid keeps lining up with its weekdays. ACROSS months a block holding no classifiable day is
    # dropped entirely — it would render all-empty either way, it carries no information, and a long
    # gap paints a wall of them: one phantom row dated nine months before the real history once
    # produced THIRTEEN blank blocks. Keyed on `cal_tier`, so "has data" means what the calendar can
    # actually SHOW (tiered tokens); a day of purely unrecognised models surfaces in `unweighted`.
    live_months = {k[:7] for k in cal_tier}
    daily = []
    d = cal_start
    while d <= today_d:
        k = d.isoformat()
        if k[:7] not in live_months:
            d += datetime.timedelta(days=1)
            continue
        by = cal_tier.get(k, {})
        rate = day_rate.get(k, base)
        cost = sum(t / 1_000_000.0 * rate * _TIER_WEIGHT[ti] for ti, t in by.items())
        daily.append(
            {
                "date": k,
                "tokens": sum(by.values()),
                "cost_usd": cost,
                "by_tier": {ti: by.get(ti, 0) for ti in _TIER_WEIGHT},
            }
        )
        d += datetime.timedelta(days=1)
    return {
        "window_start": cutoff,
        "window_end": today,
        "spend_usd": spend,
        "accounts": counted if (counted or 0) > 0 else None,
        "base_rate_per_mtok": base,
        "tiers": tiers,
        "models": model_tok,
        "daily": daily,
        "monthly_spend": {ym: _spend_for_month(ym) for ym in sorted({k[:7] for k in cal_tier})},
        "unweighted": unweighted,
    }


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
    # LOCAL calendar dates: they are compared against `usage-history.json`'s own day keys, which the CLI
    # writes in local time. `built_at` is stamped on the SAME clock (aware-local, never naive) — a UTC
    # stamp beside local bounds lets the build time fall a day BEHIND the window it describes, which on
    # this UTC+03:00 box happens for three hours every night.
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
        # ⚠️ When `measured` is None the rate still divides by the max(1, n) FLOOR, so
        # `amortized_per_mtok != spend_usd / tokens` on that branch — the published denominators cannot
        # reconstruct the published rate, which is precisely why they are null rather than plausible.
        "amortized_per_mtok": spend / total * 1_000_000.0,
        "window_start": cutoff,
        "window_end": today,
        "accounts": measured,
        "spend_usd": None if measured is None else _SUBSCRIPTION_USD_PER_ACCOUNT * measured,
        "tokens": total,
    }


class UnmeasurableWindowError(RuntimeError):
    """`refresh()` could not measure a window and refused to overwrite a MEASURED rate.

    Raised only when BOTH hold: this run fell back to the research anchor (no usage history, no
    readable account set), AND the file on disk already carries a rate derived from a real window.
    Phase C put this function on a 06:00 cron whose output is auto-committed and PUSHED, which turned
    a harmless fallback into a fleet-wide hazard: with `~/.claude` usage history unreadable — an
    account rotation, a moved home, a cleared file — the anchor (0.093/Mtok) went over a measured
    0.00748 with a FRESH `built_at`, a 12.4x jump published as current. Phase B's staleness marker is
    structurally blind to it: that marker makes an OLD stamp loud, and this failure mints a new one.

    So the refusal is the honest answer. The last measured rate stands, untouched; the caller exits
    non-zero so the cron step is seen to fail; and the file ages into Phase B's STALE marking, which
    is exactly what "we could not measure today" should look like to a reader. A fresh box with
    nothing to preserve still bootstraps from the anchor — there the anchor IS the best answer.
    """


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
    # ⚠️ CAPTURE BEFORE YOU REFUSE — the ordering is load-bearing and it was a dated time bomb.
    # `_live_usage_window()` REFUSES when the extension's `usage-history.json` cannot be measured, and
    # that refusal used to fire BEFORE `per_model_spend()`, which is the only production caller of
    # `merge_usage_store()`. The extension died on 2026-09-04, `_live_usage_window` looks back 30 days,
    # so from ~2026-10-04 every `--refresh` would have exited 3 and THE TRANSCRIPT COLLECTOR WOULD
    # NEVER HAVE RUN AGAIN — the death of source 1 silently stopping source 2, on a cron, with an
    # alert that talks about a stale RATE and never mentions that recording has stopped. Merging is
    # independent of the rate: it reads transcripts and writes the store, and it must happen whether
    # or not ② can be re-derived today. Found by an author-blind data-loss finder, 2026-09-06.
    #
    # ⚠️ ONE walk, not two. `per_model_spend()` merges as its first act, so calling `merge_usage_store()`
    # here as well and `per_model_spend()` again below walked 8.8 GB TWICE per cron run — ~100s where
    # 50s does. Computing the split HERE gets the capture-before-refuse ordering and a single walk;
    # the result is carried down to the output rather than re-derived. (My own scoped re-check of the
    # capture-before-refuse fix, which is why middle passes exist: the fix diff is the least-reviewed
    # code in the loop.)
    spend_split = per_model_spend()
    w = _live_usage_window()
    # THE REFUSAL (see UnmeasurableWindowError). `window_start is None` IS the anchor branch — the same
    # sentinel the reader in rank_task_subagents keys its "no window" rendering on, so the two agree
    # by reading one field rather than by re-deriving the condition twice.
    # ⚠️ `is not None` was WRONG here, and wrong in the direction that cannot self-heal: it treated
    # `""`, `0` and a junk object as "a measured rate worth protecting", so a sidecar carrying any
    # of those would refuse EVERY subsequent refresh and the box could never recover on its own.
    # The test is now the same one the READER applies (`rank_task_subagents._bound`): a measured
    # window bound is a non-empty single-line string. Producer and consumer agreeing on one
    # definition is the point — two definitions of "has a window" is how the halves drift apart.
    prev_bound = prev.get("window_start")
    prev_measured = (
        isinstance(prev_bound, str)
        and bool(prev_bound.strip())
        # the newline clause is NOT decoration: without it the producer and the reader disagreed on
        # exactly the shape the reader rejects, so a bound like "2026-08-07\nHEADING" was "measured"
        # to the producer (refuse, protect it) and "unreadable" to the reader — and that sidecar
        # then refused EVERY refresh and could not self-heal, which is the precise failure the
        # refusal's own test was written to prevent. Claiming parity is not the same as having it.
        and "\n" not in prev_bound
        and "\r" not in prev_bound
    )
    if w["window_start"] is None and prev_measured:
        raise UnmeasurableWindowError(
            f"refusing to overwrite a measured rate ({prev.get('amortized_per_mtok')!r} over "
            f"{prev.get('window_start')}..{prev.get('window_end')}) with the research anchor "
            f"({w['amortized_per_mtok']!r}): this run could not measure a window. The previous "
            "sidecar is left untouched and will read as STALE once it passes 24h."
        )
    data = dict(prev)  # carry forward EVERY key this function did not author
    # A carried map must not inherit the fresh window's authority: `window_start`/`window_end` and
    # `built_at` describe ② only. Measured 2026-09-05: the carried split is 79.6% off a live recompute
    # under a same-day window — 88.0% against the PRE-fix `amortized_by_family` that this same change
    # replaced. Quote either WITH its as-of; never the pre-fix number as though it still reproduces.
    #
    # ⚠️ A FLAG, not a date. Two earlier revisions of this block tried to stamp the split's age from
    # `prev["built_at"]` — first as `..._built_at`, then as `..._carried_from`. Both were wrong the same
    # way: `prev["built_at"]` is the previous REFRESH's clock, never the split's build time, so after a
    # single cron tick the stamp claimed today for a map last computed weeks earlier. The lineage is not
    # recoverable from this file, and a value you cannot derive must not be invented — so the honest
    # statement is the one thing this function actually knows: it carried the map, it did not compute it.
    # EVERY provenance key this function has ever authored is dropped first, the CURRENT one included:
    # otherwise a previous file carrying the flag but no split rides it forward through `dict(prev)`
    # and the sidecar asserts a carried split that is not there — the same orphan class the loop
    # exists to close, reintroduced by the fix for it.
    for authored in (
        "amortized_per_mtok_by_family_built_at",
        "amortized_per_mtok_by_family_carried_from",
        "amortized_per_mtok_by_family_carried",
    ):
        data.pop(authored, None)  # authored HERE in some revision; never a foreign key
    if "amortized_per_mtok_by_family" in prev:
        data["amortized_per_mtok_by_family_carried"] = True
    data.update(
        {
            "amortized_per_mtok": w["amortized_per_mtok"],
            "quota_draw_pct": quota,
            "window_start": w["window_start"],
            "window_end": w["window_end"],
            "accounts": w["accounts"],
            "spend_usd": w["spend_usd"],
            "tokens": w["tokens"],
            # The tier-weighted per-model split (operator directive 2026-09-05). AUTHORED here, so
            # it is refreshed by the same 06:00 cron as the flat rate rather than going stale beside
            # it — a second fossil next to the one this plan existed to end would be the same defect
            # wearing a new key. `per_model_spend` reconciles to `spend_usd` exactly by construction.
            "per_model_spend": spend_split,
            "built_at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
        }
    )
    # ATOMIC: this file is now the SOLE store of `amortized_per_mtok_by_family`, which nothing in
    # this repo can regenerate (`derive_cost.amortized_by_family` is reachable only from the orphaned
    # `write_cost_sidecar`). A torn write would lose it permanently, and Phase C puts this on a cron.
    # Unique temp per invocation: three agent sessions and a cron share this box, and a shared
    # `<name>.tmp` lets two producers interleave their writes into one file before either replaces it.
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(data, indent=2) + "\n")
        os.replace(tmp_name, path)
    except BaseException:
        Path(tmp_name).unlink(missing_ok=True)  # never leave debris behind a failed write
        raise
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
        try:
            print(json.dumps(refresh(), indent=2))
        except UnmeasurableWindowError as e:
            # exit 3, distinct from the exit 2 a malformed stdin payload uses: this is not bad input,
            # it is a deliberate no-write, and the cron step's `||` branch must be able to say so.
            print(f"error: {e}", file=sys.stderr)
            return 3
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
    try:
        measured = measure(obj, args.model)
    except TypeError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    print(json.dumps(measured, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
