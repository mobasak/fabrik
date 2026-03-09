#!/usr/bin/env python3
"""
Kilo Model Sync - Semi-automatic model discovery and sync.

Compares Kilo CLI models against local cache, reports differences,
and optionally updates the model catalog.

Usage:
    python scripts/kilo_model_sync.py              # Report only
    python scripts/kilo_model_sync.py --sync       # Update kilo_all_models.json
    python scripts/kilo_model_sync.py --suggest    # Suggest new agents

Schedule daily via cron:
    0 6 * * * cd /opt/fabrik && python scripts/kilo_model_sync.py --sync >> .droid/model_sync.log 2>&1
"""

import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).parent
MODELS_FILE = SCRIPT_DIR / "kilo_all_models.json"
AGENTS_FILE = SCRIPT_DIR / "kilo_47_agents_final.json"
SYNC_LOG = SCRIPT_DIR.parent / ".droid" / "kilo_model_sync.log"


def find_kilo_executable() -> str | None:
    """Find kilo executable."""
    for path in ["/home/ozgur/.kilo/bin/kilo", "kilo"]:
        try:
            subprocess.run([path, "--version"], capture_output=True, timeout=5)
            return path
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            continue
    return None


def fetch_kilo_models() -> list[dict[str, Any]]:
    """Fetch all models from Kilo CLI."""
    kilo_path = find_kilo_executable()
    if not kilo_path:
        print("ERROR: Kilo CLI not found", file=sys.stderr)
        sys.exit(1)

    result = subprocess.run(
        [kilo_path, "models", "--verbose", "--refresh"],
        capture_output=True,
        text=True,
        timeout=60,
    )

    if result.returncode != 0:
        print(f"ERROR: kilo models failed: {result.stderr}", file=sys.stderr)
        sys.exit(1)

    # Parse verbose output - each model is a JSON object
    models = []
    json_pattern = re.compile(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", re.DOTALL)

    for match in json_pattern.finditer(result.stdout):
        try:
            model = json.loads(match.group())
            if "id" in model:
                models.append(model)
        except json.JSONDecodeError:
            continue

    return models


def load_local_models() -> dict[str, Any]:
    """Load local model cache."""
    if not MODELS_FILE.exists():
        return {"total_models": 0, "models": []}

    with open(MODELS_FILE) as f:
        data = json.load(f)

    # Handle both list and dict formats for models
    models = data.get("models", [])
    if isinstance(models, list):
        # Convert list to dict keyed by full_name or short_name
        models_dict = {}
        for m in models:
            if isinstance(m, dict):
                key = m.get("full_name") or m.get("short_name") or str(m)
                models_dict[key] = m
            else:
                models_dict[m] = {"id": m}
        data["models"] = models_dict

    return data


def compare_models(local: dict[str, Any], remote: list[dict[str, Any]]) -> dict[str, Any]:
    """Compare local cache with remote models."""
    # Normalize local IDs (strip kilo/ prefix if present)
    local_ids_raw = set(local.get("models", {}).keys())
    local_ids = {k.replace("kilo/", "") for k in local_ids_raw}

    remote_ids = {m["id"] for m in remote}

    new_models = remote_ids - local_ids
    removed_models = local_ids - remote_ids

    # Check for pricing changes
    price_changes = []
    for m in remote:
        if m["id"] in local.get("models", {}):
            local_m = local["models"][m["id"]]
            remote_cost = m.get("cost", {})
            local_cost = local_m.get("cost", {})

            if remote_cost != local_cost:
                price_changes.append(
                    {
                        "id": m["id"],
                        "old": local_cost,
                        "new": remote_cost,
                    }
                )

    return {
        "new": sorted(new_models),
        "removed": sorted(removed_models),
        "price_changes": price_changes,
        "total_remote": len(remote),
        "total_local": local.get("total_models", 0),
    }


def suggest_agents(new_models: list[str], remote: list[dict[str, Any]]) -> list[dict]:
    """Suggest agents for new models based on capabilities and pricing."""
    suggestions = []

    # Tier thresholds (input cost per 1M)
    tier_map = [
        (0.00, "free"),
        (0.30, "econ"),
        (1.00, "std"),
        (3.00, "pro"),
        (10.00, "expert"),
        (float("inf"), "apex"),
    ]

    remote_lookup = {m["id"]: m for m in remote}

    for model_id in new_models:
        m = remote_lookup.get(model_id, {})
        cost = m.get("cost", {})
        inp = cost.get("input", 0) * 1_000_000
        out = cost.get("output", 0) * 1_000_000
        caps = m.get("capabilities", {})

        # Determine tier
        tier = "econ"
        for threshold, tier_name in tier_map:
            if inp <= threshold:
                tier = tier_name
                break

        # Determine role based on capabilities
        role = "code"
        if caps.get("reasoning"):
            role = "review"

        # Only suggest if it has useful capabilities
        if caps.get("toolcall") or caps.get("reasoning"):
            suggestions.append(
                {
                    "model_id": model_id,
                    "suggested_tier": tier,
                    "suggested_role": role,
                    "input_per_1m": inp,
                    "output_per_1m": out,
                    "capabilities": caps,
                    "reason": f"Has {'reasoning' if caps.get('reasoning') else 'toolcall'}",
                }
            )

    return suggestions


def update_local_cache(remote: list[dict[str, Any]]) -> None:
    """Update local model cache."""
    models_dict = {m["id"]: m for m in remote}

    data = {
        "timestamp": datetime.now().isoformat(),
        "total_models": len(remote),
        "models": models_dict,
    }

    with open(MODELS_FILE, "w") as f:
        json.dump(data, f, indent=2)

    print(f"✓ Updated {MODELS_FILE} with {len(remote)} models")


def main() -> int:
    """Main entry point."""
    args = sys.argv[1:]
    do_sync = "--sync" in args
    do_suggest = "--suggest" in args

    print(f"Kilo Model Sync - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # Fetch remote models
    print("Fetching models from Kilo CLI...")
    remote = fetch_kilo_models()
    print(f"  Found {len(remote)} models")

    # Load local cache
    local = load_local_models()
    print(f"  Local cache: {local.get('total_models', 0)} models")

    # Compare
    diff = compare_models(local, remote)

    print("\n--- Changes Detected ---")

    if diff["new"]:
        print(f"\n🆕 NEW MODELS ({len(diff['new'])}):")
        for m in diff["new"][:20]:  # Limit output
            print(f"  + {m}")
        if len(diff["new"]) > 20:
            print(f"  ... and {len(diff['new']) - 20} more")

    if diff["removed"]:
        print(f"\n❌ REMOVED MODELS ({len(diff['removed'])}):")
        for m in diff["removed"][:10]:
            print(f"  - {m}")

    if diff["price_changes"]:
        print(f"\n💰 PRICE CHANGES ({len(diff['price_changes'])}):")
        for p in diff["price_changes"][:10]:
            old_in = p["old"].get("input", 0) * 1_000_000
            new_in = p["new"].get("input", 0) * 1_000_000
            print(f"  ~ {p['id']}: ${old_in:.3f} → ${new_in:.3f}")

    if not diff["new"] and not diff["removed"] and not diff["price_changes"]:
        print("  No changes detected ✓")

    # Suggest agents for new models
    if do_suggest and diff["new"]:
        print("\n--- Agent Suggestions ---")
        suggestions = suggest_agents(diff["new"], remote)
        for s in suggestions[:10]:
            print(
                f"  {s['suggested_tier']}: {s['model_id']} ({s['suggested_role']}) - ${s['input_per_1m']:.2f}/${s['output_per_1m']:.2f}"
            )
            print(f"       Reason: {s['reason']}")

    # Update cache if requested
    if do_sync:
        print("\n--- Syncing ---")
        update_local_cache(remote)

    # Summary
    print("\n--- Summary ---")
    print(f"  Remote: {diff['total_remote']} models")
    print(f"  Local:  {diff['total_local']} models")
    print(f"  New:    {len(diff['new'])}")
    print(f"  Removed: {len(diff['removed'])}")
    print(f"  Price Δ: {len(diff['price_changes'])}")

    if diff["new"] and not do_sync:
        print("\n💡 Run with --sync to update local cache")
        print("💡 Run with --suggest to see agent recommendations")

    return 0


if __name__ == "__main__":
    sys.exit(main())
