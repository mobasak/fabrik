#!/usr/bin/env python3
"""
Update Kilo agent benchmarks from openlm.ai and tbench.ai.

Runs on WSL startup to keep agent rankings current.
Uses scrape_benchmarks.py for proper data extraction.

Updates:
  - docs/traycer/kilo_selected_agents.md (readable table)
  - scripts/kilo_selected_agents.json (benchmark fields)
  - .tmp/benchmarks/ (raw scraped data)

Usage:
    python scripts/update_kilo_benchmarks.py [--force]
"""

import json
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Import the scraper functions
from scrape_benchmarks import scrape_chatbot_arena, scrape_terminal_bench

SCRIPT_DIR = Path(__file__).parent
FABRIK_ROOT = SCRIPT_DIR.parent.parent
MASTER_MD = FABRIK_ROOT / "docs" / "traycer" / "kilo_selected_agents.md"
AGENTS_JSON = SCRIPT_DIR / "kilo_selected_agents.json"
CACHE_FILE = SCRIPT_DIR / "cache" / "benchmark_cache.json"
UPDATE_INTERVAL_HOURS = 20  # Don't update if last update was within this window


def log(msg: str) -> None:
    print(f"[kilo-bench] {msg}")


def should_update(force: bool = False) -> bool:
    """Check if we should update based on last update time."""
    if force:
        return True

    if not CACHE_FILE.exists():
        return True

    try:
        cache = json.loads(CACHE_FILE.read_text())
        last_update = datetime.fromisoformat(cache.get("last_update", "2000-01-01"))
        if datetime.now() - last_update > timedelta(hours=UPDATE_INTERVAL_HOURS):
            return True
        log(f"Skipping update - last update was {last_update.isoformat()}")
        return False
    except (json.JSONDecodeError, ValueError):
        return True


def normalize_model_name(name: str) -> str:
    """Normalize model name for matching."""
    return name.lower().replace(" ", "-").replace("_", "-")


def build_elo_map(arena_entries: list) -> dict[str, int]:
    """Build model -> Elo mapping from arena entries."""
    elo_map = {}
    for entry in arena_entries:
        model = entry.model
        elo = int(entry.score)
        normalized = normalize_model_name(model)
        elo_map[normalized] = elo
        # Also store original name
        elo_map[model.lower()] = elo
    return elo_map


def build_tbench_map(tbench_entries: list) -> dict[str, float]:
    """Build model -> accuracy mapping from tbench entries."""
    tbench_map = {}
    for entry in tbench_entries:
        model = entry.model
        accuracy = entry.score
        normalized = normalize_model_name(model)
        tbench_map[normalized] = accuracy
        tbench_map[model.lower()] = accuracy
    return tbench_map


def update_agents_json(elo_map: dict[str, int], tbench_map: dict[str, float]) -> None:
    """Update kilo_selected_agents.json with new benchmark data."""
    log("Updating agents JSON...")

    agents_data = json.loads(AGENTS_JSON.read_text())
    elo_updated = 0
    tbench_updated = 0

    for agent in agents_data.get("agents", []):
        model = agent.get("model_name", "")
        model_lower = model.lower()
        model_normalized = normalize_model_name(model)

        # Update Elo
        for key in [model_lower, model_normalized]:
            if key in elo_map:
                old_elo = agent.get("arena_elo")
                new_elo = elo_map[key]
                if old_elo != new_elo:
                    agent["arena_elo"] = new_elo
                    elo_updated += 1
                break

        # Update TBench
        for key in [model_lower, model_normalized]:
            if key in tbench_map:
                old_tbench = agent.get("tbench_accuracy")
                new_tbench = tbench_map[key]
                if old_tbench != new_tbench:
                    agent["tbench_accuracy"] = new_tbench
                    tbench_updated += 1
                break

    if elo_updated > 0 or tbench_updated > 0:
        agents_data["benchmark_date"] = datetime.now().strftime("%Y-%m-%d")
        AGENTS_JSON.write_text(json.dumps(agents_data, indent=2))
        log(f"  Updated {elo_updated} Elo + {tbench_updated} TBench scores")
    else:
        log("  No changes detected")


def update_master_md(elo_map: dict[str, int], tbench_map: dict[str, float]) -> None:
    """Update the master markdown table with new data."""
    if not MASTER_MD.exists():
        log("Master MD not found, skipping")
        return

    log("Updating master markdown...")

    content = MASTER_MD.read_text()

    # Update the timestamp
    now = datetime.now().isoformat()
    content = re.sub(
        r"\*\*Last Updated:\*\* .+",
        f"**Last Updated:** {now}",
        content,
    )

    # Update individual Elo values in the table
    for model, elo in elo_map.items():
        # Match: | model_name | old_elo |
        pattern = rf"(\| \*?\*?{re.escape(model)}\*?\*? \| )~?\d+( \|)"
        replacement = rf"\g<1>{elo}\g<2>"
        content = re.sub(pattern, replacement, content, flags=re.IGNORECASE)

    # Add update history entry
    today = datetime.now().strftime("%Y-%m-%d")
    history_entry = f"\n- **{today}:** Auto-updated from benchmarks"
    if history_entry.strip() not in content:
        content = content.rstrip() + history_entry + "\n"

    MASTER_MD.write_text(content)
    log("  Master MD updated")


def save_cache(elo_map: dict[str, int], tbench_map: dict[str, float]) -> None:
    """Save update cache."""
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    cache = {
        "last_update": datetime.now().isoformat(),
        "arena_count": len(elo_map),
        "tbench_count": len(tbench_map),
    }
    CACHE_FILE.write_text(json.dumps(cache, indent=2))


def main() -> int:
    force = "--force" in sys.argv

    log("=" * 50)
    log(f"Kilo Benchmark Updater - {datetime.now().isoformat()}")
    log("=" * 50)

    if not should_update(force):
        return 0

    # Fetch latest benchmarks using proper scrapers
    log("Running benchmark scrapers...")
    arena_entries = scrape_chatbot_arena()
    tbench_entries = scrape_terminal_bench()

    log(f"  Arena: {len(arena_entries)} entries")
    log(f"  TBench: {len(tbench_entries)} entries")

    # Build lookup maps
    elo_map = build_elo_map(arena_entries)
    tbench_map = build_tbench_map(tbench_entries)

    if elo_map or tbench_map:
        update_agents_json(elo_map, tbench_map)
        update_master_md(elo_map, tbench_map)
        save_cache(elo_map, tbench_map)
        log("Update complete!")
    else:
        log("No updates applied (fetch failed or no data)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
