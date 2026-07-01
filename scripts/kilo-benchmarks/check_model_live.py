#!/usr/bin/env python3
"""Live-truth oracle for a specific model ID.

Fetches OpenRouter /api/v1/models, OR /models/<slug>/endpoints, and
Kilo `kilo models --verbose` for a given model AND compares each against
the DB. Prints a per-field verdict.

Why this exists: my DB-first recommendations were burned by a stale
`x-ai/grok-4-fast` row (delisted upstream but not in the DB) and by
`has_reasoning=0` on models that DO support reasoning as a toggle
(gemini-2.5-flash, qwen3.5-flash-02-23, grok-4.20). Before answering
ANY question that names a specific OR/Kilo model ID, run this tool
and quote LIVE values, not DB values.

Usage:
    python check_model_live.py <model_id>              # human-readable
    python check_model_live.py <model_id> --json       # machine-readable
    python check_model_live.py --list-candidates       # print a shortlist
                                                         # of "safe-to-quote"
                                                         # non-thinking models
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from urllib.request import Request, urlopen

SCRIPT_DIR = Path(__file__).parent
DB_PATH = SCRIPT_DIR / "kilo_agents.db"
OR_MODELS = "https://openrouter.ai/api/v1/models"
OR_ENDPOINTS = "https://openrouter.ai/api/v1/models/{slug}/endpoints"


def _get(url: str) -> dict:
    req = Request(url, headers={"User-Agent": "fabrik-truth-oracle/1.0"})
    with urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))


def _fetch_kilo() -> dict[str, dict]:
    # Reuse the verifier's tested parser (brace-depth counting)
    sys.path.insert(0, str(SCRIPT_DIR))
    from verify_openrouter_catalog import _fetch_kilo as fk

    return fk()


def check_model(model_id: str) -> dict:
    """Return a per-field truth-vs-DB report for the given model."""
    # Live OR catalog
    or_catalog = {m["id"]: m for m in _get(OR_MODELS).get("data", [])}
    live_or = or_catalog.get(model_id)

    # Live OR endpoints
    live_endpoints = None
    if live_or:
        try:
            live_endpoints = _get(OR_ENDPOINTS.format(slug=model_id)).get("data")
        except Exception as e:  # noqa: BLE001
            live_endpoints = {"error": str(e)}

    # Live Kilo
    kilo_catalog = _fetch_kilo()
    live_kilo = kilo_catalog.get(model_id)

    # DB row
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    db_row = conn.execute("SELECT * FROM agents WHERE id=?", (model_id,)).fetchone()
    conn.close()
    db_dict = dict(db_row) if db_row else None

    report = {
        "id": model_id,
        "exists_live_or": live_or is not None,
        "exists_live_kilo": live_kilo is not None,
        "exists_db": db_dict is not None,
        "live_or": {
            "input_cost_per_m": _price_per_m(live_or, "prompt") if live_or else None,
            "output_cost_per_m": _price_per_m(live_or, "completion") if live_or else None,
            "cache_read_cost_per_m": _price_per_m(live_or, "input_cache_read") if live_or else None,
            "cache_write_cost_per_m": _price_per_m(live_or, "input_cache_write")
            if live_or
            else None,
            "context_length": (live_or or {}).get("context_length"),
            "top_provider_context_length": ((live_or or {}).get("top_provider") or {}).get(
                "context_length"
            ),
            "max_completion_tokens": ((live_or or {}).get("top_provider") or {}).get(
                "max_completion_tokens"
            ),
            "canonical_slug": (live_or or {}).get("canonical_slug"),
            "supported_parameters": (live_or or {}).get("supported_parameters"),
            "reasoning_supported": _has_reasoning(live_or) if live_or else None,
            "reasoning_mandatory": (
                ((live_or or {}).get("reasoning") or {}).get("mandatory") if live_or else None
            ),
            "reasoning_supported_efforts": (
                ((live_or or {}).get("reasoning") or {}).get("supported_efforts")
                if live_or
                else None
            ),
        }
        if live_or
        else None,
        "live_or_endpoints_summary": _endpoints_summary(live_endpoints),
        "live_kilo": {
            "input": ((live_kilo or {}).get("cost") or {}).get("input"),
            "output": ((live_kilo or {}).get("cost") or {}).get("output"),
            "cache_read": (((live_kilo or {}).get("cost") or {}).get("cache") or {}).get("read"),
            "cache_write": (((live_kilo or {}).get("cost") or {}).get("cache") or {}).get("write"),
            "family": (live_kilo or {}).get("family"),
            "providerID": (live_kilo or {}).get("providerID"),
            "release_date": (live_kilo or {}).get("release_date"),
        }
        if live_kilo
        else None,
        "db": {
            k: db_dict[k]
            for k in (
                "status",
                "input_cost_per_m",
                "output_cost_per_m",
                "context_window_k",
                "has_reasoning",
                "reasoning_mandatory",
                "reasoning_supported_efforts",
                "has_vision",
                "has_tools",
                "via_openrouter",
                "via_kilo",
                "kilo_input_cost_per_m",
                "kilo_output_cost_per_m",
                "kilo_family",
                "cheapest_gateway",
                "cheapest_provider",
                "endpoints_last_scraped",
            )
            if k in db_dict
        }
        if db_dict
        else None,
    }
    report["verdict"] = _verdict(report)
    return report


def _price_per_m(rec: dict | None, field: str) -> float | None:
    if not rec:
        return None
    p = (rec.get("pricing") or {}).get(field)
    if p is None:
        return None
    try:
        val = float(p)
    except (TypeError, ValueError):
        return None
    if val < 0:
        return 0.0  # BYOK sentinel — we treat as $0 direct
    return round(val * 1_000_000, 6)


def _has_reasoning(rec: dict) -> bool:
    """OR-authoritative: reasoning block OR reasoning-in-supported_parameters."""
    reasoning = rec.get("reasoning") or {}
    params = rec.get("supported_parameters") or []
    return bool(
        reasoning.get("mandatory") or reasoning.get("supported_efforts") or "reasoning" in params
    )


def _endpoints_summary(payload: dict | list | None) -> dict | None:
    """Compact per-provider summary from OR /endpoints."""
    if not payload:
        return None
    if isinstance(payload, dict) and "error" in payload:
        return payload
    eps = (payload or {}).get("endpoints") if isinstance(payload, dict) else None
    if not eps:
        return {"count": 0, "in_service": 0, "providers": []}
    summary = {"count": len(eps), "in_service": 0, "providers": []}
    for e in eps:
        st = e.get("status", 0)
        try:
            st = int(st)
        except (TypeError, ValueError):
            st = 999
        in_service = st >= 0
        if in_service:
            summary["in_service"] += 1
        pr = e.get("pricing") or {}
        summary["providers"].append(
            {
                "name": e.get("provider_name") or e.get("name"),
                "in_service": in_service,
                "status": st,
                "prompt_per_m": (float(pr.get("prompt")) * 1_000_000) if pr.get("prompt") else None,
                "quant": pr.get("quantization") or e.get("quantization"),
            }
        )
    summary["providers"].sort(key=lambda p: (p["prompt_per_m"] or 9999))
    return summary


def _verdict(report: dict) -> dict:
    """Machine-friendly summary: is this model SAFE TO RECOMMEND?"""
    v = {"safe_to_recommend": False, "warnings": [], "reasoning_state": None}
    if not report["exists_live_or"] and not report["exists_live_kilo"]:
        v["warnings"].append("NOT_ROUTABLE: not in live OR or Kilo — do not recommend.")
        return v
    if not report["exists_db"]:
        v["warnings"].append("DB_MISSING: model exists upstream but not in local DB.")
    if report["exists_db"] and report["db"].get("status") == "deprecated":
        v["warnings"].append("DB_DEPRECATED: local row is deprecated even though upstream exists.")
    if report["live_or"]:
        v["reasoning_state"] = (
            "mandatory"
            if report["live_or"]["reasoning_mandatory"]
            else ("optional" if report["live_or"]["reasoning_supported"] else "none")
        )
    # DB vs live drift check
    if report["exists_db"] and report["live_or"]:
        db = report["db"]
        live = report["live_or"]
        if abs((db.get("input_cost_per_m") or 0) - (live["input_cost_per_m"] or 0)) > 0.005:
            v["warnings"].append(
                f"PRICE_DRIFT: DB says ${db.get('input_cost_per_m')}/M in, "
                f"live says ${live['input_cost_per_m']}/M"
            )
        if bool(db.get("has_reasoning")) != bool(live["reasoning_supported"]):
            v["warnings"].append(
                f"REASONING_FLAG_DRIFT: DB has_reasoning={db.get('has_reasoning')}, "
                f"live={'yes' if live['reasoning_supported'] else 'no'}"
            )
    v["safe_to_recommend"] = report["exists_live_or"] and not any(
        w.startswith(("NOT_ROUTABLE", "DB_DEPRECATED")) for w in v["warnings"]
    )
    return v


def _print_human(report: dict) -> None:
    print(f"\n=== {report['id']} ===")
    print(
        f"exists: OR={report['exists_live_or']}  Kilo={report['exists_live_kilo']}  DB={report['exists_db']}"
    )
    v = report["verdict"]
    tag = "✓ SAFE TO RECOMMEND" if v["safe_to_recommend"] else "✗ DO NOT RECOMMEND"
    print(f"{tag}  reasoning={v['reasoning_state']}")
    if v["warnings"]:
        print("Warnings:")
        for w in v["warnings"]:
            print(f"  ⚠ {w}")

    if report["live_or"]:
        lo = report["live_or"]
        print("\nLIVE OR:")
        print(f"  price: ${lo['input_cost_per_m']}/M in · ${lo['output_cost_per_m']}/M out")
        print(
            f"  cache: read=${lo['cache_read_cost_per_m']}/M · write=${lo['cache_write_cost_per_m']}/M"
        )
        print(
            f"  context: model={lo['context_length']}  top_provider={lo['top_provider_context_length']}"
        )
        print(f"  max_out: {lo['max_completion_tokens']}")
        print(f"  canonical: {lo['canonical_slug']}")
        print(
            f"  reasoning: supported={lo['reasoning_supported']}  mandatory={lo['reasoning_mandatory']}  efforts={lo['reasoning_supported_efforts']}"
        )
    if report["live_or_endpoints_summary"]:
        s = report["live_or_endpoints_summary"]
        print(f"\nOR /endpoints: {s['count']} total, {s['in_service']} in-service")
        for p in s["providers"][:5]:
            tag = "✓" if p["in_service"] else "✗"
            print(f"  {tag} {p['name']:22s}  ${p['prompt_per_m']}/M  quant={p['quant']}")
    if report["live_kilo"]:
        lk = report["live_kilo"]
        print(
            f"\nLIVE Kilo: ${lk['input']}/M in · ${lk['output']}/M out  family={lk['family']!r}  provider={lk['providerID']}"
        )
    if report["db"]:
        d = report["db"]
        print("\nDB row:")
        for k, v in d.items():
            print(f"  {k}: {v}")


LIVE_NON_THINKING_SHORTLIST_MIN_CTX_K = 128
LIVE_NON_THINKING_SHORTLIST_MAX_INPUT_PER_M = 1.0


def list_safe_non_thinking() -> list[dict]:
    """Return the current list of TRULY non-thinking OR-live models
    (no reasoning param in supported_parameters, no reasoning block)
    at reasonable price/context — safe to recommend for
    JSON-extraction / instruction-following workloads."""
    catalog = _get(OR_MODELS).get("data", [])
    picks = []
    for m in catalog:
        if _has_reasoning(m):
            continue
        pi = _price_per_m(m, "prompt")
        if pi is None or pi <= 0 or pi > LIVE_NON_THINKING_SHORTLIST_MAX_INPUT_PER_M:
            continue
        ctx = m.get("context_length") or 0
        if ctx < LIVE_NON_THINKING_SHORTLIST_MIN_CTX_K * 1000:
            continue
        picks.append(
            {
                "id": m["id"],
                "input_per_m": pi,
                "output_per_m": _price_per_m(m, "completion"),
                "context_length": ctx,
                "supported_parameters_count": len(m.get("supported_parameters") or []),
            }
        )
    picks.sort(key=lambda p: p["input_per_m"])
    return picks


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("model_id", nargs="?")
    p.add_argument("--json", action="store_true")
    p.add_argument(
        "--list-candidates",
        action="store_true",
        help=(
            "Print a shortlist of TRULY non-thinking OR-live models "
            "(no reasoning param at all) at input <= $1/M with >= 128k context. "
            "Safe to recommend for instruction-following / JSON-extraction."
        ),
    )
    args = p.parse_args()

    if args.list_candidates:
        picks = list_safe_non_thinking()
        if args.json:
            print(json.dumps(picks, indent=2))
        else:
            print("\n=== TRULY non-thinking OR-live shortlist ===")
            print("(no reasoning param at all; input <= $1/M; ctx >= 128k)")
            print(f"{'model':40s}  in$/M  out$/M  ctx")
            for p in picks:
                print(
                    f"{p['id']:40s}  {p['input_per_m']:6.3f}  {p['output_per_m']:6.3f}  {p['context_length'] // 1000:6d}k"
                )
            print(f"\n{len(picks)} candidates.")
        return 0

    if not args.model_id:
        p.error("model_id required (or use --list-candidates)")
    report = check_model(args.model_id)
    if args.json:
        print(json.dumps(report, indent=2, default=str))
    else:
        _print_human(report)
    return 0 if report["verdict"]["safe_to_recommend"] else 2


if __name__ == "__main__":
    sys.exit(main())
