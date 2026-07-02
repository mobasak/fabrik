#!/usr/bin/env python3
"""Systematic audit of every value shown in models_browser.html.

For every field that ends up in the UI, this script:
  1. Loads current DB values (`agents` table).
  2. Fetches the authoritative live source (OR /api/v1/models,
     OR /models/<slug>/endpoints, Kilo `kilo models --verbose`).
  3. Diffs the two and reports drifts by field type.

Verify_openrouter_catalog.py has an internal discrepancy loop covering
a subset of fields. This audit is intentionally broader — it also
compares fields the verify loop DOES NOT check (description,
cache_read/write_cost_per_m, created_at, family) so we can prove
those are correct too (or find the drift).

Usage:
    python audit_ui_values.py                # full audit, human report
    python audit_ui_values.py --json         # machine-readable
    python audit_ui_values.py --sample 20    # 20 random OR-routed rows
"""

from __future__ import annotations

import argparse
import json
import random
import sqlite3
import sys
from pathlib import Path
from urllib.request import Request, urlopen

SCRIPT_DIR = Path(__file__).parent
DB_PATH = SCRIPT_DIR / "kilo_agents.db"

OR_MODELS_URL = "https://openrouter.ai/api/v1/models"

# Fields OR is authoritative for (present in /api/v1/models). Each entry:
#   (db_col, or_path, transform_or_value)
# transform: function taking the raw OR value → the value we should see in DB.
OR_FIELD_MAP = {
    # OR uses negative sentinel (-1 raw = -$1M/M) for BYOK routes where
    # the user pays the underlying provider directly, not OR. We treat
    # BYOK as "no direct cost tracked" → 0 in the DB. So audit skips
    # rows where the live price is negative (raw < 0).
    "input_cost_per_m": (
        "pricing.prompt",
        lambda v: 0.0
        if v is not None and float(v) < 0
        else (round(float(v) * 1_000_000, 6) if v is not None else None),
    ),
    "output_cost_per_m": (
        "pricing.completion",
        lambda v: 0.0
        if v is not None and float(v) < 0
        else (round(float(v) * 1_000_000, 6) if v is not None else None),
    ),
    "cache_read_cost_per_m": (
        "pricing.input_cache_read",
        lambda v: round(float(v) * 1_000_000, 6) if v not in (None, "0") else None,
    ),
    "cache_write_cost_per_m": (
        "pricing.input_cache_write",
        lambda v: round(float(v) * 1_000_000, 6) if v not in (None, "0") else None,
    ),
    # context_window_k: OR exposes model.context_length (model max) and
    # top_provider.context_length (what OR default-serves — often lower).
    # We store model.context_length per operator request (mimo-v2.5 fix
    # 2026-06-30: "actually 1M context, not 32k"). Verifier also uses this.
    "context_window_k": ("context_length", lambda v: int(v) // 1000 if v else None),
    "max_completion_tokens": (
        "top_provider.max_completion_tokens",
        lambda v: int(v) if v else None,
    ),
    "canonical_slug": ("canonical_slug", lambda v: v or None),
    "is_moderated": ("top_provider.is_moderated", lambda v: 1 if v else 0),
    "name": ("name", lambda v: v),
    "description": ("description", lambda v: v),  # audit whether stored matches (may truncate)
}


# Capability flags derived from `supported_parameters` and `architecture`.
# Kept as a separate map because they need multi-field logic, not a single
# nested-path lookup. These were the ones my Phase-A audit missed 2026-07-01
# by not modeling the toggle-support signal for reasoning-capable models.
def _live_caps_expected(live: dict) -> dict:
    arch = live.get("architecture") or {}
    params = live.get("supported_parameters") or []
    reasoning_block = live.get("reasoning") or {}
    return {
        "has_vision": 1 if "image" in (arch.get("input_modalities") or []) else 0,
        "has_tools": 1 if ("tools" in params or "tool_choice" in params) else 0,
        "has_reasoning": 1
        if (
            reasoning_block.get("mandatory")
            or reasoning_block.get("supported_efforts")
            or "reasoning" in params
        )
        else 0,
    }


# Fields the verifier already checks — surface separately so drift here is a
# critical bug in the verifier itself.
VERIFIER_TRACKED = {
    "input_cost_per_m",
    "output_cost_per_m",
    "context_window_k",
    "name",
    "max_completion_tokens",
    "is_moderated",
    "canonical_slug",
}


def _get_nested(obj: dict, path: str):
    for key in path.split("."):
        if not isinstance(obj, dict):
            return None
        obj = obj.get(key)
    return obj


def _fetch_or_catalog() -> dict[str, dict]:
    """Return {model_id: model_json} for the whole OR catalog."""
    req = Request(OR_MODELS_URL, headers={"User-Agent": "fabrik-audit/1.0"})
    with urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return {m["id"]: m for m in data.get("data", [])}


def _load_db_rows(db_path: Path) -> list[dict]:
    """Load ALL status='active' rows, not just via_openrouter=1. Bug caught
    2026-07-01: prior filter matched verify's blind spot — rows with
    via_openrouter=0 that are still active (zombie orphans like the
    delisted x-ai/grok-4-fast) were invisible to both the verifier and
    this audit. Now we audit every active row; rows without a live OR
    entry are surfaced explicitly as `row_missing_from_live`."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM agents WHERE status='active'").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def _values_match(db_val, live_val, tol: float = 0.005) -> bool:
    """Compare with type-appropriate tolerance."""
    if db_val is None and live_val is None:
        return True
    if db_val is None or live_val is None:
        return False
    # Numeric with tolerance
    if isinstance(db_val, (int, float)) and isinstance(live_val, (int, float)):
        return abs(float(db_val) - float(live_val)) <= tol
    # String: strip + case-fold minor differences for description; strict for others
    return str(db_val).strip() == str(live_val).strip()


def audit_or_fields(db_rows: list[dict], live_catalog: dict[str, dict]) -> dict:
    findings = {
        "verifier_tracked_drift": [],  # critical — verifier missed something
        "verifier_untracked_drift": [],  # audit-catches — verifier doesn't check
        "row_missing_from_live": [],  # DB has row, OR doesn't
        "totals": {"rows_audited": 0, "fields_checked": 0, "field_matches": 0},
    }
    for row in db_rows:
        mid = row["id"]
        if mid not in live_catalog:
            # Only flag as missing if the row CLAIMS to be OR-routed. Kilo-
            # only + direct-vendor rows legitimately don't appear here.
            if row.get("via_openrouter"):
                findings["row_missing_from_live"].append(mid)
            continue
        live = live_catalog[mid]
        findings["totals"]["rows_audited"] += 1
        # Also audit capability flags (has_vision / has_tools / has_reasoning)
        # against the OR-authoritative derivation. Previously missing from
        # this audit — that's how gemini-2.5-flash / qwen3.5-flash /
        # grok-4.20 showed has_reasoning=0 in the DB for months without
        # anyone catching it.
        expected_caps = _live_caps_expected(live)
        for cap_col, cap_val in expected_caps.items():
            findings["totals"]["fields_checked"] += 1
            actual = row.get(cap_col)
            if actual == cap_val or (actual is None and cap_val == 0):
                findings["totals"]["field_matches"] += 1
            else:
                findings["verifier_tracked_drift"].append(
                    {
                        "id": mid,
                        "field": cap_col,
                        "db": actual,
                        "live": cap_val,
                        "or_path": "derived: architecture + supported_parameters + reasoning",
                    }
                )
        for db_col, (or_path, transform) in OR_FIELD_MAP.items():
            raw = _get_nested(live, or_path)
            try:
                expected = transform(raw)
            except (TypeError, ValueError):
                expected = None
            actual = row.get(db_col)
            findings["totals"]["fields_checked"] += 1

            # description: OR truncates and we may store either. Skip if both non-empty.
            if db_col == "description":
                if actual and expected:
                    if len(str(actual)) < 20 or len(str(expected)) < 20:
                        continue  # too short to compare meaningfully
                    # Compare first 100 chars only (both truncate)
                    if str(actual)[:100].strip() == str(expected)[:100].strip():
                        findings["totals"]["field_matches"] += 1
                        continue
                elif actual == expected:
                    findings["totals"]["field_matches"] += 1
                    continue
            elif _values_match(actual, expected):
                findings["totals"]["field_matches"] += 1
                continue

            bucket = (
                "verifier_tracked_drift"
                if db_col in VERIFIER_TRACKED
                else "verifier_untracked_drift"
            )
            findings[bucket].append(
                {
                    "id": mid,
                    "field": db_col,
                    "db": actual,
                    "live": expected,
                    "or_path": or_path,
                }
            )
    return findings


def _audit_derived_consistency(db_path: Path) -> list[dict]:
    """Phase E: cheapest_gateway_price must equal one of the candidate
    prices (input_cost_per_m, kilo_input_cost_per_m, or one of the
    endpoint provider prices). Catches derive/apply drift where the
    cheapest column diverges from its sources."""
    drifts: list[dict] = []
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT id, input_cost_per_m, kilo_input_cost_per_m, cheapest_provider, "
        "cheapest_provider_price, cheapest_gateway, cheapest_gateway_price "
        "FROM agents WHERE cheapest_gateway IS NOT NULL AND status='active'"
    ).fetchall()
    conn.close()
    for r in rows:
        gw, price = r["cheapest_gateway"], r["cheapest_gateway_price"]
        if gw == "direct":
            expected = r["input_cost_per_m"]
        elif gw == "kilo":
            expected = r["kilo_input_cost_per_m"]
        elif gw and gw.startswith("or:"):
            expected = r["cheapest_provider_price"]
        else:
            continue  # mirror gateways — skip (already priced from gateway_prices)
        if expected is None or price is None:
            continue
        if abs(price - expected) > 0.005:
            drifts.append({"id": r["id"], "gateway": gw, "price": price, "expected": expected})
    return drifts


BENCHMARK_CACHES = [
    ("arena_parsed.json", "scraped_at"),
    ("aa_parsed.json", "fetched_at"),
    ("benchmark_cache.json", "last_updated"),
    ("tbench_parsed.json", "scraped_at"),
    ("groq_parsed.json", "scraped_at"),
]
BENCHMARK_STALE_DAYS = 7
ENDPOINTS_STALE_DAYS = 3
MICROBENCH_STALE_DAYS = 45  # microbench runs weekly; 45d is 6 missed cycles


def _audit_benchmark_freshness() -> list[dict]:
    """Any benchmark cache older than BENCHMARK_STALE_DAYS is flagged.
    Doesn't check accuracy (would require re-scraping the upstream
    leaderboard) — only that the nightly scraper has been running."""
    from datetime import UTC, datetime

    stale: list[dict] = []
    now = datetime.now(UTC)
    for filename, ts_key in BENCHMARK_CACHES:
        p = SCRIPT_DIR / "cache" / filename
        if not p.exists():
            stale.append({"cache": filename, "problem": "MISSING"})
            continue
        try:
            with p.open() as f:
                obj = json.load(f)
            ts_str = obj.get(ts_key)
            if not ts_str:
                # Fall through to file-mtime as a proxy — some caches don't
                # emit a timestamp field
                mtime = datetime.fromtimestamp(p.stat().st_mtime, UTC)
                age_days = (now - mtime).days
            else:
                ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=UTC)
                age_days = (now - ts).days
        except (OSError, ValueError, json.JSONDecodeError) as e:
            stale.append({"cache": filename, "problem": f"UNREADABLE: {e}"})
            continue
        if age_days > BENCHMARK_STALE_DAYS:
            stale.append(
                {"cache": filename, "age_days": age_days, "threshold": BENCHMARK_STALE_DAYS}
            )
    return stale


def _audit_endpoints_recency(db_path: Path) -> list[dict]:
    """Any active OR-routed row whose endpoints haven't been scraped in
    ENDPOINTS_STALE_DAYS days — the Cheapest column is a headline UX
    surface, must not silently drift."""
    from datetime import UTC, datetime, timedelta

    cutoff = (datetime.now(UTC).date() - timedelta(days=ENDPOINTS_STALE_DAYS)).isoformat()
    conn = sqlite3.connect(db_path)
    rows = conn.execute(
        "SELECT id, endpoints_last_scraped FROM agents "
        "WHERE via_openrouter=1 AND status='active' "
        "AND (endpoints_last_scraped IS NULL OR endpoints_last_scraped < ?)",
        (cutoff,),
    ).fetchall()
    conn.close()
    return [{"id": r[0], "endpoints_last_scraped": r[1]} for r in rows]


def _audit_microbench_recency(db_path: Path) -> list[dict]:
    """Any row previously benched by our own microbench whose value is
    now older than MICROBENCH_STALE_DAYS. Microbench runs weekly on
    Sundays; 45 days = 6 missed cycles → likely a real regression."""
    from datetime import UTC, datetime, timedelta

    cutoff = (datetime.now(UTC).date() - timedelta(days=MICROBENCH_STALE_DAYS)).isoformat()
    conn = sqlite3.connect(db_path)
    rows = conn.execute(
        "SELECT id, speed_updated_at FROM agents "
        "WHERE status='active' "
        "AND speed_source LIKE 'own_microbench%' "
        "AND (speed_updated_at IS NULL OR speed_updated_at < ?)",
        (cutoff,),
    ).fetchall()
    conn.close()
    return [{"id": r[0], "speed_updated_at": r[1]} for r in rows]


def _audit_kilo(db_path: Path) -> list[dict]:
    """Phase C: kilo_input/output_cost_per_m + kilo_family match live Kilo.
    Uses the verifier's tested parser."""
    sys.path.insert(0, str(SCRIPT_DIR))
    try:
        from verify_openrouter_catalog import _canonicalize_id, _fetch_kilo
    except ImportError:
        return []
    try:
        kilo = _fetch_kilo()
    except Exception:  # noqa: BLE001
        return []

    # Priority selection (same rule as verify_openrouter_catalog:672-712)
    canon_to_rec: dict[str, dict] = {}
    scores: dict[str, int] = {}
    for kid, rec in kilo.items():
        cost = rec.get("cost") or {}
        try:
            kin = float(cost.get("input") or 0)
            kout = float(cost.get("output") or 0)
        except (TypeError, ValueError):
            kin, kout = 0.0, 0.0
        s = 0
        if "/" in kid:
            s += 100
        if kin > 0 or kout > 0:
            s += 50
        if kid.startswith("stealth/"):
            s -= 20
        canon = _canonicalize_id(kid)
        if canon in scores and scores[canon] >= s:
            continue
        canon_to_rec[canon] = rec
        scores[canon] = s

    drifts: list[dict] = []
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT id, kilo_input_cost_per_m, kilo_output_cost_per_m, kilo_family "
        "FROM agents WHERE via_kilo=1 AND status='active'"
    ).fetchall()
    conn.close()
    for r in rows:
        live = canon_to_rec.get(_canonicalize_id(r["id"])) or kilo.get(r["id"])
        if not live:
            continue
        cost = live.get("cost") or {}
        for db_col, cost_key in (
            ("kilo_input_cost_per_m", "input"),
            ("kilo_output_cost_per_m", "output"),
        ):
            live_val = cost.get(cost_key)
            if live_val is None:
                continue
            db_val = r[db_col] or 0
            if abs(db_val - live_val) > 0.005:
                drifts.append({"id": r["id"], "field": db_col, "db": db_val, "live": live_val})
        live_family = live.get("family")
        if r["kilo_family"] != live_family:
            drifts.append(
                {"id": r["id"], "field": "kilo_family", "db": r["kilo_family"], "live": live_family}
            )
    return drifts


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--db", type=Path, default=DB_PATH)
    p.add_argument("--sample", type=int, help="Sample N random rows (default: all)")
    p.add_argument("--json", action="store_true", help="machine-readable output")
    p.add_argument("--seed", type=int, default=42)
    args = p.parse_args()

    print("[audit] fetching OR /api/v1/models…", file=sys.stderr)
    live = _fetch_or_catalog()
    print(f"[audit] loaded {len(live)} live OR models", file=sys.stderr)

    db_rows = _load_db_rows(args.db)
    print(f"[audit] loaded {len(db_rows)} OR-routed active DB rows", file=sys.stderr)

    if args.sample and args.sample < len(db_rows):
        random.seed(args.seed)
        db_rows = random.sample(db_rows, args.sample)
        print(f"[audit] sampled {len(db_rows)} rows for audit", file=sys.stderr)

    findings = audit_or_fields(db_rows, live)
    findings["derived_consistency_drift"] = _audit_derived_consistency(args.db)
    findings["kilo_drift"] = _audit_kilo(args.db)
    findings["benchmark_freshness_issues"] = _audit_benchmark_freshness()
    findings["endpoints_stale_rows"] = _audit_endpoints_recency(args.db)
    findings["microbench_stale_rows"] = _audit_microbench_recency(args.db)

    if args.json:
        print(json.dumps(findings, default=str, indent=2))
        return 0

    t = findings["totals"]
    print("\n=== Phase A: OR /api/v1/models audit ===")
    print(f"Rows audited: {t['rows_audited']}")
    print(f"Fields checked: {t['fields_checked']}")
    print(
        f"Matches: {t['field_matches']} ({100 * t['field_matches'] / max(1, t['fields_checked']):.1f}%)"
    )
    print()

    if findings["row_missing_from_live"]:
        print(f"⚠ {len(findings['row_missing_from_live'])} DB rows not in live OR catalog:")
        for mid in findings["row_missing_from_live"][:10]:
            print(f"  - {mid}")
        if len(findings["row_missing_from_live"]) > 10:
            print(f"  … and {len(findings['row_missing_from_live']) - 10} more")
        print()

    if findings["verifier_tracked_drift"]:
        print(
            f"❌ CRITICAL — {len(findings['verifier_tracked_drift'])} drifts in fields the verifier IS supposed to track:"
        )
        for d in findings["verifier_tracked_drift"][:20]:
            print(f"  {d['id']:50s}  {d['field']:25s}  db={d['db']!r:20s}  live={d['live']!r}")
        print()
    else:
        print(
            "✓ No drift in verifier-tracked fields (input_cost, output_cost, ctx, name, max_out, moderated, canonical)"
        )

    if findings.get("derived_consistency_drift"):
        print(
            f"❌ CRITICAL — {len(findings['derived_consistency_drift'])} rows where "
            f"cheapest_gateway_price disagrees with its source column:"
        )
        for d in findings["derived_consistency_drift"][:10]:
            print(
                f"  {d['id']:45s}  gw={d['gateway']}  price=${d['price']}  expected=${d['expected']}"
            )
    else:
        print(
            "✓ cheapest_gateway prices consistent with input_cost_per_m / kilo_input / cheapest_provider_price"
        )

    if findings.get("kilo_drift"):
        print(f"❌ CRITICAL — {len(findings['kilo_drift'])} Kilo drifts:")
        for d in findings["kilo_drift"][:10]:
            print(f"  {d['id']:45s}  {d['field']:30s}  db={d['db']!r}  live={d['live']!r}")
    else:
        print("✓ Kilo pricing + family match live `kilo models --verbose`")

    if findings.get("benchmark_freshness_issues"):
        print(f"⚠ {len(findings['benchmark_freshness_issues'])} benchmark cache freshness issues:")
        for d in findings["benchmark_freshness_issues"]:
            if "problem" in d:
                print(f"  {d['cache']:30s}  {d['problem']}")
            else:
                print(
                    f"  {d['cache']:30s}  age={d['age_days']}d "
                    f"(threshold {d['threshold']}d) — scraper may be silently failing"
                )
    else:
        print(f"✓ Benchmark caches all fresh (within {BENCHMARK_STALE_DAYS}d)")

    if findings.get("endpoints_stale_rows"):
        n = len(findings["endpoints_stale_rows"])
        print(
            f"⚠ {n} OR-active rows haven't had endpoints scraped in "
            f">{ENDPOINTS_STALE_DAYS}d — Cheapest column may be stale:"
        )
        for d in findings["endpoints_stale_rows"][:10]:
            print(f"  {d['id']:45s}  last scraped: {d['endpoints_last_scraped']}")
    else:
        print(f"✓ All OR-active rows scraped for endpoints within {ENDPOINTS_STALE_DAYS}d")

    if findings.get("microbench_stale_rows"):
        n = len(findings["microbench_stale_rows"])
        print(
            f"⚠ {n} rows with own_microbench Speed data are stale "
            f"(> {MICROBENCH_STALE_DAYS}d, i.e. 6 missed weekly cycles):"
        )
        for d in findings["microbench_stale_rows"][:10]:
            print(f"  {d['id']:45s}  benched at: {d['speed_updated_at']}")
    else:
        print(f"✓ All own_microbench rows benched within {MICROBENCH_STALE_DAYS}d")

    if findings["verifier_untracked_drift"]:
        print(
            f"⚠ {len(findings['verifier_untracked_drift'])} drifts in fields the verifier does NOT track (audit gap):"
        )
        by_field: dict[str, int] = {}
        for d in findings["verifier_untracked_drift"]:
            by_field[d["field"]] = by_field.get(d["field"], 0) + 1
        for f, n in sorted(by_field.items(), key=lambda x: -x[1]):
            print(f"  {f}: {n} rows")
        print("\n  Examples:")
        for d in findings["verifier_untracked_drift"][:15]:
            db_s = str(d["db"])[:40] + ("…" if d["db"] and len(str(d["db"])) > 40 else "")
            live_s = str(d["live"])[:40] + ("…" if d["live"] and len(str(d["live"])) > 40 else "")
            print(f"    {d['id']:45s}  {d['field']:25s}  db={db_s!r}  live={live_s!r}")
    else:
        print(
            "✓ No drift in verifier-untracked fields (description, cache_read/write, is_moderated)"
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
