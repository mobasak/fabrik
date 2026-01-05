#!/usr/bin/env python3
"""
Droid Model Auto-Updater

Automatically fetches model rankings from Factory docs and updates local config.
Runs unattended - no human intervention required.

Usage:
  python3 scripts/droid_model_updater.py          # Check and update if needed
  python3 scripts/droid_model_updater.py --force  # Force update even if cached
  python3 scripts/droid_model_updater.py --dry-run # Show what would change

Automation:
  Add to crontab for daily updates:
  0 9 * * * cd /opt/fabrik && python3 scripts/droid_model_updater.py >> .tmp/model-updates.log 2>&1
"""

import json
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

try:
    import yaml

    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False

# Paths
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
CONFIG_FILE = PROJECT_ROOT / "config" / "models.yaml"
CACHE_FILE = SCRIPT_DIR / ".model_update_cache.json"
CACHE_TTL_HOURS = 24

# Factory docs URLs
FACTORY_RANKING_URL = "https://docs.factory.ai/cli/user-guides/choosing-your-model.md"
FACTORY_PRICING_URL = "https://docs.factory.ai/pricing.md"

# Dynamic model name map - populated from pricing.md
# Format: display_name_lower -> model_id
MODEL_NAME_MAP: dict[str, str] = {}


def fetch_url(url: str) -> str | None:
    """Fetch content from a URL."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Fabrik/1.0 (model-updater)"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.read().decode("utf-8")
    except Exception as e:
        print(f"ERROR: Failed to fetch {url}: {e}")
        return None


def parse_pricing_table(content: str) -> dict[str, dict]:
    """
    Parse the pricing table from pricing.md to get exact Model IDs.

    Returns: {display_name_lower: {"model_id": "...", "multiplier": "..."}}
    """
    models = {}

    # Pattern matches: | Model Name | `model-id` | 0.5× |
    # The model ID is wrapped in backticks
    table_pattern = r"\|\s*([^|]+)\s*\|\s*`([^`]+)`\s*\|\s*([0-9.]+)×?\s*\|"

    matches = re.findall(table_pattern, content)

    for display_name, model_id, multiplier in matches:
        clean_name = display_name.strip().lower()
        models[clean_name] = {
            "model_id": model_id.strip(),
            "multiplier": float(multiplier),
            "display_name": display_name.strip(),
        }

    return models


def build_model_name_map(pricing_models: dict[str, dict]) -> dict[str, str]:
    """Build the display name -> model ID mapping from pricing data."""
    name_map = {}

    for display_name_lower, info in pricing_models.items():
        model_id = info["model_id"]
        name_map[display_name_lower] = model_id

        # Also add variations for matching
        # e.g., "claude opus 4.5" -> "claude-opus-4-5-20251101"
        # Also handle "(default)" suffix in rankings
        name_map[display_name_lower.replace("(default)", "").strip()] = model_id

        # Add the model_id itself as a key (for exact matches)
        name_map[model_id.lower()] = model_id

    return name_map


def normalize_model_name(display_name: str) -> str:
    """Convert display name to API model name using the dynamic map."""
    # Clean up the display name
    clean = display_name.lower().strip()
    clean = re.sub(r"\*\*", "", clean)  # Remove markdown bold
    clean = re.sub(r"\(default\)", "", clean).strip()
    clean = re.sub(r"\(glm-[\d.]+\)", "", clean).strip()

    # Try direct lookup
    if clean in MODEL_NAME_MAP:
        return MODEL_NAME_MAP[clean]

    # Try partial match
    for key, value in MODEL_NAME_MAP.items():
        if key in clean or clean in key:
            return value

    # Fallback: convert to API format (best guess)
    fallback = clean.replace(" ", "-").lower()
    print(f"  WARNING: Unknown model '{display_name}' -> guessing '{fallback}'")
    return fallback


def parse_stack_rankings(content: str) -> list[dict]:
    """Parse the stack rank table from markdown content."""
    rankings = []

    # Find the stack rank table
    # Pattern: | Rank | Model | Why we reach for it |
    table_pattern = r"\|\s*(\d+)\s*\|\s*\*\*([^|*]+)\*\*[^|]*\|\s*([^|]+)\|"

    matches = re.findall(table_pattern, content)

    for rank, model, why in matches:
        api_name = normalize_model_name(model)
        rankings.append(
            {
                "rank": int(rank),
                "model": api_name,
                "display_name": model.strip(),
                "why": why.strip(),
            }
        )

    return rankings


def parse_scenarios(content: str) -> dict:
    """Parse the scenario recommendations from markdown content."""
    scenarios = {}

    # Find the "Match the model to the job" section
    scenario_patterns = [
        (r"Deep planning.*?architecture.*?specs", "deep_planning"),
        (r"Full-feature development.*?refactors", "full_feature_dev"),
        (r"Repeatable edits.*?boilerplate", "repeatable_edits"),
        (r"CI/CD.*?automation loops", "ci_cd"),
        (r"High-volume automation", "high_volume"),
    ]

    # Find table rows
    row_pattern = r"\|\s*\*\*([^|*]+)\*\*\s*\|\s*([^|]+)\|"
    matches = re.findall(row_pattern, content)

    for scenario_desc, recommendation in matches:
        # Match to our scenario keys
        for pattern, key in scenario_patterns:
            if re.search(pattern, scenario_desc, re.IGNORECASE):
                # Extract primary model (first bold model mentioned)
                primary_match = re.search(r"\*\*([^*]+)\*\*", recommendation)
                if primary_match:
                    primary = normalize_model_name(primary_match.group(1))
                    scenarios[key] = {
                        "description": scenario_desc.strip(),
                        "primary": primary,
                        "notes": recommendation.strip()[:100],
                    }
                break

    return scenarios


def get_last_update_date(content: str) -> str | None:
    """Extract the last update date from Factory docs."""
    # Look for "December 2025" or similar patterns
    match = re.search(r"(\w+ \d{4})", content)
    if match:
        return match.group(1)
    return None


def load_cache() -> dict | None:
    """Load cached update info."""
    if not CACHE_FILE.exists():
        return None

    try:
        data = json.loads(CACHE_FILE.read_text())
        cached_time = datetime.fromisoformat(data.get("timestamp", ""))
        if datetime.now() - cached_time < timedelta(hours=CACHE_TTL_HOURS):
            return data
    except Exception:
        pass

    return None


def save_cache(data: dict):
    """Save update cache."""
    data["timestamp"] = datetime.now().isoformat()
    CACHE_FILE.write_text(json.dumps(data, indent=2))


def update_yaml_config(rankings: list[dict], scenarios: dict, doc_date: str) -> bool:
    """Update config/models.yaml with new rankings."""
    if not YAML_AVAILABLE:
        print("ERROR: PyYAML not installed. Run: pip install pyyaml")
        return False

    if not CONFIG_FILE.exists():
        print(f"ERROR: Config file not found: {CONFIG_FILE}")
        return False

    try:
        with open(CONFIG_FILE) as f:
            config = yaml.safe_load(f)
    except Exception as e:
        print(f"ERROR: Failed to read config: {e}")
        return False

    # Update version
    old_version = config.get("version", "unknown")
    new_version = datetime.now().strftime("%Y-%m-%d")
    config["version"] = new_version
    config["factory_docs_date"] = doc_date

    # Update stack rankings
    new_stack_rank = {}
    for r in rankings:
        new_stack_rank[r["rank"]] = {
            "model": r["model"],
            "why": r["why"],
        }

    old_stack_rank = config.get("stack_rank", {})
    config["stack_rank"] = new_stack_rank

    # Check for changes
    changes = []
    for rank, info in new_stack_rank.items():
        old_info = old_stack_rank.get(rank, {})
        if old_info.get("model") != info["model"]:
            old_model = old_info.get("model", "none")
            changes.append(f"  Rank {rank}: {old_model} → {info['model']}")

    # Update scenarios if we parsed any
    if scenarios:
        for key, info in scenarios.items():
            if key in config.get("scenarios", {}):
                old_primary = config["scenarios"][key].get("primary")
                if old_primary != info["primary"]:
                    config["scenarios"][key]["primary"] = info["primary"]
                    changes.append(f"  Scenario {key}: {old_primary} → {info['primary']}")

    if not changes:
        print(f"✓ No changes needed (config version: {old_version})")
        return False

    # Write updated config
    try:
        with open(CONFIG_FILE, "w") as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

        print("✓ Updated config/models.yaml")
        print(f"  Version: {old_version} → {new_version}")
        print(f"  Factory docs date: {doc_date}")
        print("Changes:")
        for change in changes:
            print(change)

        return True
    except Exception as e:
        print(f"ERROR: Failed to write config: {e}")
        return False


def sync_all_files():
    """Sync model names to all Fabrik files."""
    try:
        from droid_models import sync_all_models

        print("\nSyncing to all Fabrik files...")
        results = sync_all_models()
        for file, result in results.items():
            status = result.get("status", "unknown")
            if status == "updated":
                print(f"  ✓ {file}: Updated")
            elif status == "no_changes":
                print(f"  • {file}: No changes")
            else:
                print(f"  ✗ {file}: {result.get('errors', 'unknown error')}")
    except ImportError:
        print("  (Skipping sync - run manually: python3 scripts/droid_models.py sync)")


def update_if_stale() -> bool:
    """
    Check if models need updating and update if stale.

    Called automatically by droid_tasks.py and droid_runner.py before each exec.
    Uses cache to avoid repeated fetches (24-hour TTL).

    Returns:
        True if updated or cache valid, False on error
    """
    cache = load_cache()
    if cache and cache.get("status") == "up_to_date":
        return True  # Cache still valid

    # Stale - run quiet update
    try:
        pricing_content = fetch_url(FACTORY_PRICING_URL)
        if not pricing_content:
            return False

        pricing_models = parse_pricing_table(pricing_content)
        if pricing_models:
            global MODEL_NAME_MAP
            MODEL_NAME_MAP = build_model_name_map(pricing_models)

        # Save cache to prevent repeated fetches
        save_cache({"status": "up_to_date", "models_found": len(pricing_models)})
        return True
    except Exception:
        return False


def main():
    global MODEL_NAME_MAP

    args = sys.argv[1:]
    force = "--force" in args
    dry_run = "--dry-run" in args

    print("=" * 60)
    print("Droid Model Auto-Updater")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # Check cache unless forced
    if not force:
        cache = load_cache()
        if cache and cache.get("status") == "up_to_date":
            print(f"✓ Checked recently ({cache.get('timestamp', 'unknown')[:10]})")
            print("  Use --force to check again")
            return 0

    # Step 1: Fetch pricing.md to get exact Model IDs
    print(f"\n1. Fetching pricing table: {FACTORY_PRICING_URL}")
    pricing_content = fetch_url(FACTORY_PRICING_URL)
    if not pricing_content:
        return 1

    pricing_models = parse_pricing_table(pricing_content)
    print(f"   Found {len(pricing_models)} models with exact IDs:")
    for name, info in pricing_models.items():
        print(f"     {info['display_name']:<20} -> {info['model_id']}")

    # Build the dynamic name map from pricing data
    MODEL_NAME_MAP = build_model_name_map(pricing_models)

    # Step 2: Fetch choosing-your-model.md to get rankings
    print(f"\n2. Fetching rankings: {FACTORY_RANKING_URL}")
    ranking_content = fetch_url(FACTORY_RANKING_URL)
    if not ranking_content:
        return 1

    print(f"   Received {len(ranking_content)} bytes")

    # Parse rankings (now using dynamic MODEL_NAME_MAP)
    rankings = parse_stack_rankings(ranking_content)
    if not rankings:
        print("ERROR: Failed to parse stack rankings from docs")
        return 1

    print(f"   Parsed {len(rankings)} model rankings")

    # Parse scenarios
    scenarios = parse_scenarios(ranking_content)
    print(f"   Parsed {len(scenarios)} scenarios")

    # Get doc date
    doc_date = get_last_update_date(ranking_content) or "Unknown"
    print(f"   Factory docs date: {doc_date}")

    if dry_run:
        print("\n[DRY RUN] Would update:")
        for r in rankings:
            print(f"  {r['rank']}. {r['model']}")
        return 0

    # Update YAML config
    print()
    updated = update_yaml_config(rankings, scenarios, doc_date)

    # Save cache
    save_cache(
        {
            "status": "up_to_date" if not updated else "updated",
            "factory_docs_date": doc_date,
            "rankings_count": len(rankings),
        }
    )

    # Sync to all files if updated
    if updated:
        sync_all_files()

    print("\n" + "=" * 60)
    print("Complete")
    return 0


if __name__ == "__main__":
    sys.exit(main())
