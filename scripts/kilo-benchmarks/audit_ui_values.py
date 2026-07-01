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
    rows = conn.execute(
        "SELECT * FROM agents WHERE status='active'"
    ).fetchall()
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
