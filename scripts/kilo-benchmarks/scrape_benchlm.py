#!/usr/bin/env python3
"""
Scrape BenchLM coding benchmark data from their API.

Fetches coding benchmark data from benchlm.ai/api/data/leaderboard?category=coding
including SWE-bench Pro, Weighted Coding, and LiveCodeBench scores.

Usage:
    python scripts/kilo-benchmarks/scrape_benchlm.py
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import requests

SCRIPT_DIR = Path(__file__).parent
CACHE_FILE = SCRIPT_DIR / "cache" / "benchlm_cache.json"


def log(msg: str) -> None:
    print(f"[benchlm] {msg}")


def fetch_benchlm_coding() -> list[dict[str, Any]]:
    """Fetch coding leaderboard data from BenchLM API."""
    log("Fetching BenchLM coding leaderboard...")

    url = "https://benchlm.ai/api/data/leaderboard?category=coding&format=json"

    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        data = response.json()

        # The API returns {"lastUpdated": "...", "mode": "...", "models": [...]}
        # Extract the models array
        if isinstance(data, dict) and "models" in data:
            entries = data["models"]
        elif isinstance(data, list):
            entries = data
        else:
            log(f"  Unexpected API response structure: {type(data)}")
            return []

        log(f"  Fetched {len(entries)} entries from BenchLM")
        return entries

    except requests.RequestException as e:
        log(f"  Error fetching BenchLM data: {e}")
        return []
    except json.JSONDecodeError as e:
        log(f"  Error parsing BenchLM JSON: {e}")
        return []


def parse_benchlm_entry(entry: dict[str, Any]) -> dict[str, Any]:
    """Parse a single BenchLM entry into a normalized format."""
    model_name = entry.get("model", "")
    source = entry.get("sourceType", "Unknown")

    # Extract benchmark scores from categoryScores
    category_scores = entry.get("categoryScores", {})

    # The API provides a single "coding" score which is the weighted score
    # Map it to weighted_coding (primary metric)
    weighted_coding = category_scores.get("coding")

    # SWE-bench Pro and LiveCodeBench are not in this API endpoint
    # They are only available on the web page, not the JSON API
    swe_bench_pro = None
    livecodebench = None

    return {
        "model_name": model_name,
        "source": source,
        "swe_bench_pro": swe_bench_pro,
        "weighted_coding": weighted_coding,
        "livecodebench": livecodebench,
    }


def parse_percentage(value: Any) -> float | None:
    """Parse percentage value from BenchLM entry."""
    if value is None or value == "" or value == "—":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        # Remove % sign and convert
        cleaned = value.strip().replace("%", "")
        try:
            return float(cleaned)
        except ValueError:
            return None
    return None


def build_benchlm_map(entries: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Build a lookup map from model name to benchmark data."""
    benchlm_map = {}

    for entry in entries:
        parsed = parse_benchlm_entry(entry)
        model_name = parsed["model_name"].lower()

        # Store with lowercase key for case-insensitive matching
        benchlm_map[model_name] = parsed

        # Also store with common variations
        # e.g., "claude opus 4.6" -> "claude-opus-4-6"
        normalized = model_name.replace(" ", "-").replace("_", "-")
        benchlm_map[normalized] = parsed

    log(f"  Built map with {len(benchlm_map)} entries")
    return benchlm_map


def save_cache(benchlm_map: dict[str, dict[str, Any]]) -> None:
    """Save BenchLM data to cache."""
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)

    cache = {
        "last_update": datetime.now().isoformat(),
        "count": len(benchlm_map),
        "data": benchlm_map,
    }

    CACHE_FILE.write_text(json.dumps(cache, indent=2))
    log(f"  Saved cache to {CACHE_FILE}")


def load_cache() -> dict[str, dict[str, Any]] | None:
    """Load BenchLM data from cache."""
    if not CACHE_FILE.exists():
        return None

    try:
        cache = json.loads(CACHE_FILE.read_text())
        return cache.get("data", {})
    except (json.JSONDecodeError, KeyError):
        return None


def main() -> int:
    log("=" * 50)
    log(f"BenchLM Scraper - {datetime.now().isoformat()}")
    log("=" * 50)

    # Try to fetch fresh data
    entries = fetch_benchlm_coding()

    if not entries:
        log("  No entries fetched, trying cache...")
        benchlm_map = load_cache()
        if benchlm_map:
            log(f"  Using cached data ({len(benchlm_map)} entries)")
        else:
            log("  No cache available")
            return 1
    else:
        benchlm_map = build_benchlm_map(entries)
        save_cache(benchlm_map)

    # Print top 10 by SWE-bench Pro
    log("\nTop 10 models by SWE-bench Pro:")
    sorted_by_swe = sorted(
        [(k, v) for k, v in benchlm_map.items() if v["swe_bench_pro"] is not None],
        key=lambda x: x[1]["swe_bench_pro"],
        reverse=True,
    )

    for i, (name, data) in enumerate(sorted_by_swe[:10], 1):
        log(
            f"  {i}. {name}: SWE-bench Pro={data['swe_bench_pro']}%, Weighted={data['weighted_coding']}%"
        )

    log("\nDone!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
