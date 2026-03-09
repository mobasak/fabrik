#!/usr/bin/env python3
"""
Kilo Model Sync - Semi-automatic model discovery and sync.

Compares Kilo CLI models against local cache, reports differences,
and optionally updates agents and regenerates scripts.

Usage:
    python scripts/kilo_model_sync.py              # Report only
    python scripts/kilo_model_sync.py --sync       # Update kilo_all_models.json
    python scripts/kilo_model_sync.py --plan       # Generate proposed agent changes
    python scripts/kilo_model_sync.py --apply      # Apply changes (update agents, regenerate scripts)

Workflow:
    1. Daily cron runs --sync to update model cache
    2. Review with --plan to see proposed agent changes
    3. Apply with --apply after human review

Schedule daily via cron:
    59 11 * * * cd /opt/fabrik && python scripts/kilo_model_sync.py --sync >> .droid/model_sync.log 2>&1
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
PLAN_FILE = SCRIPT_DIR.parent / ".droid" / "kilo_agent_plan.json"

# Tier thresholds (input cost per 1M tokens)
TIER_THRESHOLDS = [
    (0.00, "Free"),
    (0.30, "Economy"),
    (1.00, "Standard"),
    (3.00, "Pro"),
    (10.00, "Expert"),
    (float("inf"), "Apex"),
]


def find_kilo_executable() -> str | None:
    """Find kilo executable."""
    for path in ["/home/ozgur/.npm-global/bin/kilo", "/home/ozgur/.kilo/bin/kilo", "kilo"]:
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


def determine_tier(input_per_1m: float) -> str:
    """Determine tier based on input cost per 1M tokens."""
    for threshold, tier_name in TIER_THRESHOLDS:
        if input_per_1m <= threshold:
            return tier_name
    return "Apex"


def determine_role(caps: dict[str, Any]) -> str:
    """Determine role based on capabilities."""
    if caps.get("reasoning"):
        return "review"
    return "code"


def determine_variant(caps: dict[str, Any]) -> str:
    """Determine variant based on capabilities."""
    if caps.get("reasoning"):
        return "max"
    return "high"


def suggest_agents(new_models: list[str], remote: list[dict[str, Any]]) -> list[dict]:
    """Suggest agents for new models based on capabilities and pricing."""
    suggestions = []
    remote_lookup = {m["id"]: m for m in remote}

    for model_id in new_models:
        m = remote_lookup.get(model_id, {})
        cost = m.get("cost", {})
        inp = cost.get("input", 0) * 1_000_000
        out = cost.get("output", 0) * 1_000_000
        caps = m.get("capabilities", {})

        # Only suggest if it has useful capabilities for coding
        if not (caps.get("toolcall") or caps.get("reasoning")):
            continue

        tier = determine_tier(inp)
        role = determine_role(caps)
        variant = determine_variant(caps)

        # Extract provider and model name from ID (format: provider/model)
        parts = model_id.split("/")
        provider = parts[0] if len(parts) > 1 else "unknown"
        model_name = parts[-1]

        suggestions.append(
            {
                "model_id": model_id,
                "full_name": f"kilo/{model_id}",
                "provider": provider,
                "model_name": model_name,
                "tier": tier,
                "role": role,
                "variant": variant,
                "input_per_1m": inp,
                "output_per_1m": out,
                "capabilities": caps,
                "reason": f"Has {'reasoning' if caps.get('reasoning') else 'toolcall'}",
            }
        )

    return suggestions


def load_current_agents() -> dict[str, Any]:
    """Load current agent definitions."""
    if not AGENTS_FILE.exists():
        return {"agents": [], "total_agents": 0}
    with open(AGENTS_FILE) as f:
        return json.load(f)


def generate_plan(suggestions: list[dict], price_changes: list[dict]) -> dict[str, Any]:
    """Generate a plan for agent updates."""
    plan = {
        "timestamp": datetime.now().isoformat(),
        "new_agents": [],
        "price_updates": [],
        "summary": {},
    }

    # Load current agents to check for duplicates
    current = load_current_agents()
    current_models = {a.get("full_name") for a in current.get("agents", [])}

    # Filter out models already in agents
    for s in suggestions:
        if s["full_name"] not in current_models:
            plan["new_agents"].append(
                {
                    "agent_id": f"{s['tier'].lower()}-{s['model_name']}-{s['role']}-{s['variant']}",
                    "model_name": s["model_name"],
                    "full_name": s["full_name"],
                    "provider": s["provider"],
                    "use_case": s["role"],
                    "variant": s["variant"],
                    "specialty": "general",
                    "input_per_1m": s["input_per_1m"],
                    "output_per_1m": s["output_per_1m"],
                    "tier": s["tier"],
                    "reason": s["reason"],
                }
            )

    # Price updates for existing agents
    for p in price_changes:
        model_id = p["id"]
        full_name = f"kilo/{model_id}"
        if full_name in current_models:
            old_in = p["old"].get("input", 0) * 1_000_000
            new_in = p["new"].get("input", 0) * 1_000_000
            old_out = p["old"].get("output", 0) * 1_000_000
            new_out = p["new"].get("output", 0) * 1_000_000
            plan["price_updates"].append(
                {
                    "full_name": full_name,
                    "old_input": old_in,
                    "new_input": new_in,
                    "old_output": old_out,
                    "new_output": new_out,
                }
            )

    plan["summary"] = {
        "new_agents_count": len(plan["new_agents"]),
        "price_updates_count": len(plan["price_updates"]),
    }

    return plan


def save_plan(plan: dict[str, Any]) -> None:
    """Save plan to file for review."""
    PLAN_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(PLAN_FILE, "w") as f:
        json.dump(plan, f, indent=2)
    print(f"✓ Plan saved to {PLAN_FILE}")


def load_plan() -> dict[str, Any] | None:
    """Load existing plan."""
    if not PLAN_FILE.exists():
        return None
    with open(PLAN_FILE) as f:
        return json.load(f)


def apply_plan(plan: dict[str, Any]) -> bool:
    """Apply the plan: update agents JSON and regenerate scripts."""
    if not plan.get("new_agents") and not plan.get("price_updates"):
        print("Nothing to apply.")
        return True

    # Load current agents
    current = load_current_agents()
    agents = current.get("agents", [])
    modified = False

    # Add new agents
    for new_agent in plan.get("new_agents", []):
        agent_entry = {
            "agent_id": new_agent["agent_id"],
            "model_name": new_agent["model_name"],
            "full_name": new_agent["full_name"],
            "provider": new_agent["provider"],
            "use_case": new_agent["use_case"],
            "variant": new_agent["variant"],
            "specialty": new_agent["specialty"],
            "input_per_1m": new_agent["input_per_1m"],
            "output_per_1m": new_agent["output_per_1m"],
        }
        agents.append(agent_entry)
        print(f"  + Added: {new_agent['full_name']} ({new_agent['tier']})")
        modified = True

    # Apply price updates
    for update in plan.get("price_updates", []):
        for agent in agents:
            if agent.get("full_name") == update["full_name"]:
                agent["input_per_1m"] = update["new_input"]
                agent["output_per_1m"] = update["new_output"]
                print(f"  ~ Updated pricing: {update['full_name']}")
                modified = True
                break

    if not modified:
        print("No changes applied.")
        return True

    # Save updated agents
    current["agents"] = agents
    current["total_agents"] = len(agents)
    current["timestamp"] = datetime.now().isoformat()

    with open(AGENTS_FILE, "w") as f:
        json.dump(current, f, indent=2)
    print(f"✓ Updated {AGENTS_FILE} with {len(agents)} agents")

    # Regenerate agent scripts
    print("\nRegenerating agent scripts...")
    result = subprocess.run(
        [sys.executable, str(SCRIPT_DIR / "generate_kilo_agents.py")],
        capture_output=True,
        text=True,
        cwd=SCRIPT_DIR.parent,
    )
    if result.returncode == 0:
        print("✓ Agent scripts regenerated")
    else:
        print(f"✗ Failed to regenerate scripts: {result.stderr}")
        return False

    # Clean up plan file
    if PLAN_FILE.exists():
        PLAN_FILE.unlink()
        print("✓ Plan file cleaned up")

    return True


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
    do_plan = "--plan" in args
    do_apply = "--apply" in args

    print(f"Kilo Model Sync - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # Handle --apply: load existing plan and apply it
    if do_apply:
        print("\n--- Applying Plan ---")
        plan = load_plan()
        if not plan:
            print("✗ No plan found. Run with --plan first.")
            return 1
        print(f"Plan from: {plan.get('timestamp', 'unknown')}")
        print(f"  New agents: {plan['summary'].get('new_agents_count', 0)}")
        print(f"  Price updates: {plan['summary'].get('price_updates_count', 0)}")
        if apply_plan(plan):
            print("\n✓ Plan applied successfully")
            return 0
        return 1

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
        for m in diff["new"][:20]:
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

    # Generate plan if requested
    if do_plan:
        print("\n--- Generating Plan ---")
        suggestions = suggest_agents(diff["new"], remote)
        plan = generate_plan(suggestions, diff["price_changes"])

        if plan["new_agents"]:
            print(f"\n📋 PROPOSED NEW AGENTS ({len(plan['new_agents'])}):")
            for a in plan["new_agents"]:
                print(f"  + [{a['tier']}] {a['full_name']}")
                print(f"      Role: {a['use_case']}, Variant: {a['variant']}")
                print(f"      Pricing: ${a['input_per_1m']:.2f}/${a['output_per_1m']:.2f}")

        if plan["price_updates"]:
            print(f"\n💰 PROPOSED PRICE UPDATES ({len(plan['price_updates'])}):")
            for u in plan["price_updates"]:
                print(f"  ~ {u['full_name']}: ${u['old_input']:.2f} → ${u['new_input']:.2f}")

        if plan["new_agents"] or plan["price_updates"]:
            save_plan(plan)
            print("\n💡 Review the plan, then run with --apply to execute")
        else:
            print("  No agent changes needed ✓")

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

    if not do_sync and not do_plan and not do_apply:
        print("\n💡 Commands:")
        print("  --sync   Update local model cache")
        print("  --plan   Generate agent update plan")
        print("  --apply  Apply existing plan")

    return 0


if __name__ == "__main__":
    sys.exit(main())
