#!/usr/bin/env python3
"""Verify every row in kilo_agents.db.agents against the live OpenRouter
catalog. Produce a per-row diff for pricing, context window, capability
flags, and name; flag delisted rows; optionally apply fixes.

Usage:
    python verify_openrouter_catalog.py                # report only
    python verify_openrouter_catalog.py --apply        # write fixes to DB
    python verify_openrouter_catalog.py --json out.json # machine-readable

Live source: https://openrouter.ai/api/v1/models
Fields cross-checked: input_cost_per_m, output_cost_per_m,
context_window_k, has_vision, has_tools, name. Delisted rows (in DB
but absent from live catalog) get status='deprecated' under --apply.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import urllib.request
from datetime import date
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
DB_PATH = SCRIPT_DIR / "kilo_agents.db"
OR_URL = "https://openrouter.ai/api/v1/models"
CACHE_PATH = SCRIPT_DIR / "cache" / "openrouter_live_catalog.json"


def _fetch_live() -> dict[str, dict]:
    """Hit OpenRouter, return id → full record map. Also persists the
    response to cache for inspection."""
    req = urllib.request.Request(OR_URL, headers={"User-Agent": "fabrik-verifier/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.loads(resp.read())
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(payload, indent=2))
    return {m["id"]: m for m in payload.get("data", [])}


def _live_pricing(record: dict) -> tuple[float, float]:
    """OpenRouter encodes pricing as dollars-per-token strings (e.g.
    '0.000003' = $3 per million). Returns (input_per_m, output_per_m)."""
    p = record.get("pricing", {}) or {}
    try:
        inp = float(p.get("prompt", 0) or 0) * 1_000_000
    except (TypeError, ValueError):
        inp = 0.0
    try:
        outp = float(p.get("completion", 0) or 0) * 1_000_000
    except (TypeError, ValueError):
        outp = 0.0
    return inp, outp


def _live_caps(record: dict) -> dict[str, int]:
    """Vision flag from architecture.input_modalities; tools from
    supported_parameters."""
    arch = record.get("architecture", {}) or {}
    mods = arch.get("input_modalities", []) or []
    has_vision = 1 if "image" in mods else 0
    params = record.get("supported_parameters", []) or []
    has_tools = 1 if ("tools" in params or "tool_choice" in params) else 0
    return {"has_vision": has_vision, "has_tools": has_tools}


def _approx_eq(a, b, tol=0.005) -> bool:
    """Compare floats with small tolerance — OpenRouter occasionally
    returns prices like '5.999999...e-06' so exact equality is fragile."""
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    return abs(float(a) - float(b)) <= tol


def verify(db_path: Path = DB_PATH) -> dict:
    """Cross-check every active row. Returns:
    {
      "summary": {...counts...},
      "discrepancies": [{"id":..., "field": price_in, "db": X, "live": Y}, ...],
      "delisted": ["id1", "id2", ...],
      "live_only": ["id1", ...],   # in OpenRouter but not our DB
      "matched_clean": ["id", ...],
    }
    """
    live = _fetch_live()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    db_rows = {
        r["id"]: dict(r)
        for r in conn.execute("SELECT * FROM agents WHERE status='active'").fetchall()
    }
    conn.close()

    delisted: list[str] = []
    matched_clean: list[str] = []
    discrepancies: list[dict] = []

    for mid, row in db_rows.items():
        live_rec = live.get(mid)
        if not live_rec:
            delisted.append(mid)
            continue

        live_inp, live_out = _live_pricing(live_rec)
        live_ctx = (live_rec.get("context_length") or 0) // 1000
        live_caps = _live_caps(live_rec)
        live_name = live_rec.get("name") or ""

        row_disc: list[dict] = []
        if not _approx_eq(row.get("input_cost_per_m"), live_inp, tol=0.01):
            row_disc.append(
                {
                    "field": "input_cost_per_m",
                    "db": row.get("input_cost_per_m"),
                    "live": live_inp,
                }
            )
        if not _approx_eq(row.get("output_cost_per_m"), live_out, tol=0.01):
            row_disc.append(
                {
                    "field": "output_cost_per_m",
                    "db": row.get("output_cost_per_m"),
                    "live": live_out,
                }
            )
        if row.get("context_window_k") != live_ctx and live_ctx > 0:
            row_disc.append(
                {
                    "field": "context_window_k",
                    "db": row.get("context_window_k"),
                    "live": live_ctx,
                }
            )
        if (row.get("has_vision") or 0) != live_caps["has_vision"]:
            row_disc.append(
                {
                    "field": "has_vision",
                    "db": row.get("has_vision"),
                    "live": live_caps["has_vision"],
                }
            )
        if (row.get("has_tools") or 0) != live_caps["has_tools"]:
            row_disc.append(
                {
                    "field": "has_tools",
                    "db": row.get("has_tools"),
                    "live": live_caps["has_tools"],
                }
            )
        if live_name and row.get("name") != live_name:
            row_disc.append(
                {
                    "field": "name",
                    "db": row.get("name"),
                    "live": live_name,
                }
            )

        if row_disc:
            discrepancies.append({"id": mid, "diffs": row_disc})
        else:
            matched_clean.append(mid)

    live_only = [mid for mid in live if mid not in db_rows]

    return {
        "summary": {
            "db_active": len(db_rows),
            "live_total": len(live),
            "matched_clean": len(matched_clean),
            "matched_with_discrepancy": len(discrepancies),
            "delisted_in_db_only": len(delisted),
            "missing_from_db": len(live_only),
        },
        "discrepancies": discrepancies,
        "delisted": delisted,
        "live_only": live_only,
        "matched_clean": matched_clean,
    }


def ingest_new(report: dict, db_path: Path = DB_PATH) -> dict:
    """Pull rows that are in OpenRouter but missing from our DB."""
    live = json.loads(CACHE_PATH.read_text())
    live_by_id = {m["id"]: m for m in live.get("data", [])}
    today_iso = date.today().isoformat()
    inserted = 0

    conn = sqlite3.connect(db_path)
    try:
        conn.execute("BEGIN")
        for mid in report["live_only"]:
            rec = live_by_id.get(mid)
            if not rec:
                continue
            provider = mid.split("/")[0] if "/" in mid else mid
            inp, outp = _live_pricing(rec)
            ctx = (rec.get("context_length") or 0) // 1000
            caps = _live_caps(rec)
            conn.execute(
                "INSERT INTO agents (id, api_id, name, provider, "
                "input_cost_per_m, output_cost_per_m, context_window_k, "
                "has_vision, has_tools, status, last_verified) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?)",
                (
                    mid,
                    mid,
                    rec.get("name") or mid,
                    provider,
                    inp,
                    outp,
                    ctx,
                    caps["has_vision"],
                    caps["has_tools"],
                    today_iso,
                ),
            )
            inserted += 1
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return {"inserted": inserted}


def apply_fixes(report: dict, db_path: Path = DB_PATH) -> dict:
    """For each discrepancy, UPDATE the DB column to live value.
    Delisted rows get status='deprecated'. Returns counts."""
    conn = sqlite3.connect(db_path)
    today_iso = date.today().isoformat()
    counts = {"rows_updated": 0, "rows_deprecated": 0, "fields_updated": 0}

    try:
        conn.execute("BEGIN")
        for entry in report["discrepancies"]:
            mid = entry["id"]
            for diff in entry["diffs"]:
                conn.execute(
                    f"UPDATE agents SET {diff['field']} = ?, last_verified = ? WHERE id = ?",
                    (diff["live"], today_iso, mid),
                )
                counts["fields_updated"] += 1
            counts["rows_updated"] += 1

        for mid in report["delisted"]:
            conn.execute(
                "UPDATE agents SET status = 'deprecated', "
                "discard_reason = COALESCE(discard_reason, 'delisted by OpenRouter (verifier)'), "
                "last_verified = ? WHERE id = ?",
                (today_iso, mid),
            )
            counts["rows_deprecated"] += 1
        # Bump last_verified for cleanly-matching rows too — we DID verify
        # them against the live catalog today, the columns just didn't
        # need to change. Without this, downstream consumers might still
        # mark them stale.
        if report.get("matched_clean"):
            placeholders = ",".join("?" * len(report["matched_clean"]))
            conn.execute(
                f"UPDATE agents SET last_verified = ? WHERE id IN ({placeholders})",
                (today_iso, *report["matched_clean"]),
            )
            counts["rows_clean_touched"] = len(report["matched_clean"])
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return counts


def _print_report(report: dict, verbose: bool = False) -> None:
    s = report["summary"]
    print("=" * 70)
    print(f"  OpenRouter catalog verification @ {date.today().isoformat()}")
    print("=" * 70)
    print(f"  DB active rows:                {s['db_active']:>4}")
    print(f"  Live OpenRouter rows:          {s['live_total']:>4}")
    print(f"  ✓  matched cleanly:            {s['matched_clean']:>4}")
    print(f"  ~  matched w/ discrepancy:     {s['matched_with_discrepancy']:>4}")
    print(f"  ⚠  delisted in DB only:        {s['delisted_in_db_only']:>4}")
    print(f"  +  in OpenRouter, not in DB:   {s['missing_from_db']:>4}")
    print()
    if report["discrepancies"]:
        print(f"=== Discrepancies (top {min(40, len(report['discrepancies']))}) ===")
        for entry in report["discrepancies"][:40]:
            print(f"\n  {entry['id']}")
            for d in entry["diffs"]:
                f = d["field"]
                db, live = d["db"], d["live"]
                if isinstance(db, float) or isinstance(live, float):
                    print(f"    {f:<25} DB={db}  LIVE={live}")
                else:
                    print(f"    {f:<25} DB={db!r}  LIVE={live!r}")
    if report["delisted"]:
        print()
        print(f"=== Delisted (top 20 of {len(report['delisted'])}) ===")
        for mid in report["delisted"][:20]:
            print(f"  - {mid}")
    if verbose and report["live_only"]:
        print()
        print(f"=== Missing from DB (top 20 of {len(report['live_only'])}) ===")
        for mid in report["live_only"][:20]:
            print(f"  + {mid}")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--db", type=Path, default=DB_PATH)
    p.add_argument("--apply", action="store_true", help="apply fixes to DB")
    p.add_argument(
        "--ingest-new",
        action="store_true",
        help="INSERT rows present in OpenRouter but missing from DB",
    )
    p.add_argument("--json", type=Path, help="write full report as JSON")
    p.add_argument("--verbose", action="store_true")
    args = p.parse_args()

    if not args.db.exists():
        print(f"ERROR: {args.db} does not exist.", file=sys.stderr)
        sys.exit(1)

    report = verify(args.db)
    _print_report(report, verbose=args.verbose)

    if args.json:
        args.json.write_text(json.dumps(report, indent=2, default=str))
        print(f"\nFull report written to {args.json}")

    if args.apply:
        print()
        print("Applying fixes...")
        counts = apply_fixes(report, args.db)
        print(f"  fields updated:  {counts['fields_updated']}")
        print(f"  rows updated:    {counts['rows_updated']}")
        print(f"  rows deprecated: {counts['rows_deprecated']}")

    if args.ingest_new:
        print()
        print("Ingesting new rows from OpenRouter...")
        c = ingest_new(report, args.db)
        print(f"  rows inserted:   {c['inserted']}")


if __name__ == "__main__":
    main()
