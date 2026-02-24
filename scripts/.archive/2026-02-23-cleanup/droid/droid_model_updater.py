#!/usr/bin/env python3
"""
Droid Model Auto-Updater

Automatically fetches available models from `droid exec -m listmodels` and updates local config.
Uses TTL-based caching (24h) to avoid slowing down every droid exec call.

Usage:
  python3 scripts/droid_model_updater.py          # Check and update if needed
  python3 scripts/droid_model_updater.py --force  # Force update even if cached
  python3 scripts/droid_model_updater.py --dry-run # Show what would change
  python3 scripts/droid_model_updater.py --check-deprecations  # Check for deprecated models in use

In-Code Usage:
  from droid_model_updater import ensure_models_fresh, check_deprecations
  ensure_models_fresh()  # Called before droid exec, uses 24h cache
  warnings = check_deprecations()  # Returns list of deprecated model warnings

Caching Strategy:
  - First droid exec of day: refresh cache (4-5s)
  - Subsequent calls: use cache (0ms overhead)
  - Model not found: refresh and retry
  - Deprecation: warn when configured model no longer available
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
DEPRECATION_FILE = SCRIPT_DIR / ".model_deprecations.json"
CACHE_TTL_HOURS = 24

# Factory docs URLs (fallback)
FACTORY_RANKING_URL = "https://docs.factory.ai/cli/user-guides/choosing-your-model.md"
FACTORY_PRICING_URL = "https://docs.factory.ai/pricing.md"

# Dynamic model name map - populated from pricing.md
# Format: display_name_lower -> model_id
MODEL_NAME_MAP: dict[str, str] = {}

# Cache for available models from droid exec
_AVAILABLE_MODELS_CACHE: list[str] | None = None


def fetch_models_from_droid_cli() -> list[str]:
    """
    Fetch available models from droid exec by triggering the "invalid model" error.

    When you pass an invalid model to `droid exec -m invalid_model`, it returns
    the list of available models in the error output. This is the authoritative
    source for available models.

    Returns:
        List of available model IDs
    """
    import subprocess

    try:
        # Use an invalid model name to trigger the error that lists available models
        result = subprocess.run(
            ["droid", "exec", "-m", "__list_models__", "echo test"],
            capture_output=True,
            text=True,
            timeout=10,
        )

        # Parse the error output which contains the available models
        # Format: "Available built-in models:\n  model1, model2, model3, ..."
        output = result.stdout + result.stderr
        models = []

        for line in output.split("\n"):
            line = line.strip()
            # Look for the line with comma-separated model names
            if line.startswith("gpt-") or line.startswith("claude-") or line.startswith("gemini-"):
                # This line contains model names
                for part in line.split(","):
                    model = part.strip()
                    if model:
                        models.append(model)
            elif "Available built-in models:" in line:
                continue
            elif line and not line.startswith("Invalid") and not line.startswith("No custom"):
                # Check if line contains models after colon
                if ":" in line:
                    after_colon = line.split(":", 1)[1].strip()
                    for part in after_colon.split(","):
                        model = part.strip()
                        if model and (
                            model.startswith("gpt-")
                            or model.startswith("claude-")
                            or model.startswith("gemini-")
                            or model.startswith("glm-")
                            or model.startswith("kimi-")
                        ):
                            models.append(model)

        return list(set(models))  # Deduplicate
    except subprocess.TimeoutExpired:
        print("WARNING: droid exec timed out", file=sys.stderr)
        return []
    except FileNotFoundError:
        print("WARNING: droid command not found", file=sys.stderr)
        return []
    except Exception as e:
        print(f"WARNING: Failed to fetch models from droid CLI: {e}", file=sys.stderr)
        return []


def get_models_in_use() -> list[str]:
    """
    Get list of models currently configured in our YAML and scripts.

    Returns:
        List of model IDs that we're using
    """
    models_in_use = set()

    if not YAML_AVAILABLE or not CONFIG_FILE.exists():
        return []

    try:
        with open(CONFIG_FILE) as f:
            config = yaml.safe_load(f)

        # Get default model
        if "default_model" in config:
            models_in_use.add(config["default_model"])

        # Get models from stack rankings
        for rank_info in config.get("stack_rank", {}).values():
            if "model" in rank_info:
                models_in_use.add(rank_info["model"])

        # Get models from scenarios
        for scenario in config.get("scenarios", {}).values():
            if "primary" in scenario:
                models_in_use.add(scenario["primary"])
            for alt in scenario.get("alternatives", []):
                models_in_use.add(alt)
            for model in scenario.get("models", []):
                models_in_use.add(model)

        # Get models from model details
        for model_name in config.get("models", {}):
            models_in_use.add(model_name)

    except Exception as e:
        print(f"WARNING: Failed to read models in use: {e}", file=sys.stderr)

    return list(models_in_use)


def check_deprecations(available_models: list[str] | None = None) -> list[dict]:
    """
    Check if any models we're using have been deprecated.

    Args:
        available_models: List of currently available models (fetched if not provided)

    Returns:
        List of deprecation warnings: [{"model": "...", "message": "..."}]
    """
    if available_models is None:
        cache = load_cache()
        if cache and "available_models" in cache:
            available_models = cache["available_models"]
        else:
            available_models = fetch_models_from_droid_cli()

    if not available_models:
        return []  # Can't check without available models list

    models_in_use = get_models_in_use()
    available_lower = {m.lower() for m in available_models}

    deprecations = []
    for model in models_in_use:
        if model.lower() not in available_lower:
            deprecations.append(
                {
                    "model": model,
                    "message": f"Model '{model}' is no longer available. Update config/models.yaml",
                    "severity": "warning",
                }
            )

    # Save deprecations to file for tracking
    if deprecations:
        try:
            existing = []
            if DEPRECATION_FILE.exists():
                existing = json.loads(DEPRECATION_FILE.read_text())

            # Add new deprecations with timestamp
            for dep in deprecations:
                dep["detected_at"] = datetime.now().isoformat()
                if dep not in existing:
                    existing.append(dep)

            DEPRECATION_FILE.write_text(json.dumps(existing, indent=2))
        except Exception:
            pass  # Non-critical

    return deprecations


def fetch_model_prices() -> dict[str, float]:
    """
    Fetch model price multipliers from Factory docs.

    Parses the pricing table from https://docs.factory.ai/pricing.md

    Returns:
        Dict mapping model_id -> cost_multiplier
    """
    pricing_url = "https://docs.factory.ai/pricing.md"

    try:
        content = fetch_url(pricing_url)
        if not content:
            return {}

        pricing_data = parse_pricing_table(content)

        # Convert to model_id -> multiplier
        prices = {}
        for info in pricing_data.values():
            model_id = info.get("model_id", "")
            multiplier = info.get("multiplier", 1.0)
            if model_id:
                prices[model_id] = multiplier

        return prices
    except Exception as e:
        print(f"WARNING: Failed to fetch model prices: {e}", file=sys.stderr)
        return {}


def ensure_models_fresh(force: bool = False) -> dict:
    """
    Ensure model list is fresh. Called before droid exec.

    Uses 24-hour cache to avoid delay on every call.
    Fetches both model names (from droid CLI) and prices (from Factory docs).

    Args:
        force: Force refresh even if cache is valid

    Returns:
        dict with status, available_models, model_prices, and deprecation warnings
    """
    global _AVAILABLE_MODELS_CACHE

    result = {
        "status": "ok",
        "from_cache": False,
        "available_models": [],
        "model_prices": {},
        "deprecations": [],
    }

    # Check cache first (unless forced)
    if not force:
        cache = load_cache()
        if cache and cache.get("status") in ("up_to_date", "updated"):
            cache_time = datetime.fromisoformat(cache.get("timestamp", "2000-01-01"))
            if datetime.now() - cache_time < timedelta(hours=CACHE_TTL_HOURS):
                result["from_cache"] = True
                result["available_models"] = cache.get("available_models", [])
                result["model_prices"] = cache.get("model_prices", {})
                _AVAILABLE_MODELS_CACHE = result["available_models"]

                # Check deprecations using cached models
                result["deprecations"] = check_deprecations(result["available_models"])
                return result

    # Cache stale or forced - fetch fresh data
    print("Refreshing model list from droid CLI...", file=sys.stderr)
    available_models = fetch_models_from_droid_cli()

    if not available_models:
        # Fallback: try to use existing cache even if stale
        cache = load_cache()
        if cache and "available_models" in cache:
            result["available_models"] = cache["available_models"]
            result["status"] = "using_stale_cache"
            print("WARNING: Using stale model cache (refresh failed)", file=sys.stderr)
        else:
            result["status"] = "error"
            result["error"] = "Failed to fetch models and no cache available"
        return result

    # Update cache
    _AVAILABLE_MODELS_CACHE = available_models
    result["available_models"] = available_models

    # Fetch model prices from Factory docs
    print("Fetching model prices from Factory docs...", file=sys.stderr)
    model_prices = fetch_model_prices()
    result["model_prices"] = model_prices
    if model_prices:
        print(f"   Found prices for {len(model_prices)} models", file=sys.stderr)

    # Check for deprecations
    result["deprecations"] = check_deprecations(available_models)

    # Print deprecation warnings
    for dep in result["deprecations"]:
        print(f"⚠️  DEPRECATED: {dep['message']}", file=sys.stderr)

    # Save to cache (including prices)
    save_cache(
        {
            "status": "up_to_date",
            "available_models": available_models,
            "models_count": len(available_models),
            "model_prices": model_prices,
            "deprecations": result["deprecations"],
        }
    )

    return result


def get_model_price(model_name: str) -> float | None:
    """
    Get price multiplier for a model.

    Uses cache if available, otherwise fetches fresh data.

    Args:
        model_name: Model ID to check

    Returns:
        Price multiplier (e.g., 0.5, 1.0, 2.0) or None if not found
    """
    cache = load_cache()
    if cache and "model_prices" in cache:
        prices = cache["model_prices"]
        # Try exact match first
        if model_name in prices:
            return prices[model_name]
        # Try case-insensitive
        for name, price in prices.items():
            if name.lower() == model_name.lower():
                return price
    return None


def is_model_available(model_name: str) -> bool:
    """
    Check if a model is available.

    Uses cache if available, otherwise fetches fresh list.

    Args:
        model_name: Model ID to check

    Returns:
        True if model is available
    """
    global _AVAILABLE_MODELS_CACHE

    if _AVAILABLE_MODELS_CACHE is None:
        result = ensure_models_fresh()
        _AVAILABLE_MODELS_CACHE = result.get("available_models", [])

    return model_name.lower() in {m.lower() for m in _AVAILABLE_MODELS_CACHE}


def is_model_safe_for_auto(model_name: str) -> tuple[bool, str]:
    """
    Check if a model is safe for automatic use.

    A model is safe for auto-use only if:
    1. It is available (in droid exec model list)
    2. It has a known price multiplier (from Factory docs)

    Models without price multipliers require explicit user approval.

    Args:
        model_name: Model ID to check

    Returns:
        Tuple of (is_safe, reason)
    """
    if not is_model_available(model_name):
        return False, f"Model '{model_name}' is not available (deprecated or invalid)"

    price = get_model_price(model_name)
    if price is None:
        return (
            False,
            f"Model '{model_name}' has no known price multiplier - requires explicit approval",
        )

    return True, f"Model '{model_name}' is available with {price}x multiplier"


def get_models_without_prices() -> list[str]:
    """
    Get list of available models that don't have price multipliers.

    These models require explicit user approval for use.

    Returns:
        List of model IDs without known prices
    """
    available = set(get_available_models())
    cache = load_cache()
    prices = set(cache.get("model_prices", {}).keys()) if cache else set()

    return sorted(available - prices)


def get_available_models() -> list[str]:
    """
    Get list of available models.

    Uses cache if available, otherwise fetches fresh list.

    Returns:
        List of available model IDs
    """
    global _AVAILABLE_MODELS_CACHE

    if _AVAILABLE_MODELS_CACHE is None:
        result = ensure_models_fresh()
        _AVAILABLE_MODELS_CACHE = result.get("available_models", [])

    return _AVAILABLE_MODELS_CACHE


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
    check_deps = "--check-deprecations" in args
    use_cli = "--from-cli" in args or not any(a.startswith("--") for a in args)

    print("=" * 60)
    print("Droid Model Auto-Updater")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # Handle --check-deprecations
    if check_deps:
        print("\nChecking for deprecated models...")
        result = ensure_models_fresh(force=force)
        deprecations = result.get("deprecations", [])
        if deprecations:
            print(f"\n⚠️  Found {len(deprecations)} deprecated model(s):")
            for dep in deprecations:
                print(f"   - {dep['model']}: {dep['message']}")
            return 1
        else:
            print("✓ All configured models are available")
            return 0

    # Use droid CLI as primary source (faster, more accurate)
    if use_cli or force:
        print("\n1. Fetching models from droid CLI...")
        result = ensure_models_fresh(force=force)
        if result["status"] == "ok":
            print(f"   Found {len(result['available_models'])} models")
            if result.get("from_cache"):
                print("   (from cache)")
            if result.get("deprecations"):
                print("\n⚠️  Deprecation warnings:")
                for dep in result["deprecations"]:
                    print(f"   - {dep['model']}")
            print("\n" + "=" * 60)
            print("Complete")
            return 0
        elif result["status"] == "using_stale_cache":
            print("   WARNING: Using stale cache (CLI failed)")
        else:
            print(f"   ERROR: {result.get('error', 'Unknown error')}")
            # Fall through to Factory docs method

    # Check cache unless forced
    if not force:
        cache = load_cache()
        if cache and cache.get("status") == "up_to_date":
            print(f"✓ Checked recently ({cache.get('timestamp', 'unknown')[:10]})")
            print("  Use --force to check again")
            return 0

    # Fallback: Fetch from Factory docs
    print(f"\n2. Fetching pricing table: {FACTORY_PRICING_URL}")
    pricing_content = fetch_url(FACTORY_PRICING_URL)
    if not pricing_content:
        return 1

    pricing_models = parse_pricing_table(pricing_content)
    print(f"   Found {len(pricing_models)} models with exact IDs:")
    for info in pricing_models.values():
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
