#!/usr/bin/env python3
"""
Scrape Windsurf Cascade model data from docs.windsurf.com.

Extracts models from all provider tabs with their credit multipliers.
Follows principles from scrape_benchmarks.py for consistency.

Uses Selenium for JavaScript-rendered content.

Usage:
    python scripts/kilo-benchmarks/scrape_windsurf_models.py

Requirements:
    pip install selenium
"""

import json
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.support.ui import WebDriverWait

SCRIPT_DIR = Path(__file__).parent
OUTPUT_DIR = SCRIPT_DIR / "cache"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# Tab names to scrape
TABS = ["Recommended", "Windsurf", "Anthropic", "OpenAI", "Google", "xAI", "Open Source"]


@dataclass
class WindsurfModel:
    name: str
    credits: str  # e.g., "0", "2", "4", "0 🎁"
    provider: str  # Tab name
    credits_numeric: float  # Parsed numeric value

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "credits": self.credits,
            "provider": self.provider,
            "credits_numeric": self.credits_numeric,
        }


def log(msg: str) -> None:
    print(f"[windsurf-scrape] {msg}")


def parse_credits(credits_str: str) -> float:
    """Parse credit string to numeric value."""
    # Remove emoji and extra text
    clean = credits_str.replace("🎁", "").strip()

    # Handle "Free" or "0"
    if clean.lower() == "free" or clean == "0":
        return 0.0

    try:
        return float(clean)
    except ValueError:
        return 0.0


def get_browser():
    """Create headless Chrome browser instance."""
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument(f"user-agent={HEADERS['User-Agent']}")

    # Try to use system chromedriver
    driver = webdriver.Chrome(options=chrome_options)
    return driver


def scrape_tab_models(driver, tab_id: str) -> list[WindsurfModel]:
    """Scrape models from a specific tab."""
    models = []

    try:
        # Find the tab button
        tab_button = WebDriverWait(driver, 10).until(
            expected_conditions.presence_of_element_located((By.ID, tab_id))
        )

        # Scroll into view and use JavaScript click to avoid interception
        driver.execute_script("arguments[0].scrollIntoView(true);", tab_button)
        time.sleep(0.5)
        driver.execute_script("arguments[0].click();", tab_button)

        # Wait for content to load
        time.sleep(2)

        # Get page HTML after JavaScript renders
        html = driver.page_source
        soup = BeautifulSoup(html, "html.parser")

        # Find tables in the active tab panel
        tables = soup.find_all("table")

        for table in tables:
            # Check if this table has Model and Credits columns
            headers = table.find_all("th")
            header_text = [h.get_text(strip=True) for h in headers]

            if "Model" not in header_text or "Credits" not in header_text:
                continue

            # Parse table rows
            rows = table.find_all("tr")[1:]  # Skip header row

            for row in rows:
                cols = row.find_all("td")
                if len(cols) >= 2:
                    model_name = cols[0].get_text(strip=True)
                    credits_str = cols[1].get_text(strip=True)

                    if model_name:
                        credits_numeric = parse_credits(credits_str)
                        models.append(
                            WindsurfModel(
                                name=model_name,
                                credits=credits_str,
                                provider=tab_id.capitalize(),
                                credits_numeric=credits_numeric,
                            )
                        )

    except Exception as e:
        log(f"  Error scraping tab {tab_id}: {e}")

    return models


def scrape_windsurf_models() -> dict[str, list[WindsurfModel]]:
    """
    Scrape Windsurf model data from all tabs using Selenium.
    Returns dict mapping tab name -> list of models.
    """
    log("Fetching Windsurf models page...")
    url = "https://docs.windsurf.com/plugins/cascade/models"

    try:
        driver = get_browser()
        driver.get(url)

        # Wait for page to load
        WebDriverWait(driver, 10).until(
            expected_conditions.presence_of_element_located((By.TAG_NAME, "table"))
        )

        # Save raw HTML for debugging
        html = driver.page_source
        (OUTPUT_DIR / "windsurf_raw.html").write_text(html)

        models_by_tab = {}

        # The page has tab navigation - need to find tab IDs dynamically
        soup = BeautifulSoup(html, "html.parser")
        tab_elements = soup.find_all("li", {"role": "tab"})

        log(f"  Found {len(tab_elements)} tabs")

        # Extract tab IDs
        tab_ids = []
        for tab_elem in tab_elements:
            tab_id = tab_elem.get("id")
            if tab_id:
                tab_ids.append(tab_id)
                log(f"    Tab: {tab_id}")

        # Scrape each tab
        for tab_id in tab_ids:
            log(f"  Scraping tab: {tab_id}")
            models = scrape_tab_models(driver, tab_id)
            if models:
                models_by_tab[tab_id.capitalize()] = models
                log(f"    Found {len(models)} models")

        driver.quit()

        # Log results
        total_models = sum(len(models) for models in models_by_tab.values())
        log(f"  Extracted {total_models} models from {len(models_by_tab)} tabs")

        # Save parsed data
        output = {
            "source": "docs.windsurf.com",
            "url": url,
            "scraped_at": datetime.now().isoformat(),
            "total_models": total_models,
            "tabs": {tab: [m.to_dict() for m in models] for tab, models in models_by_tab.items()},
        }
        (OUTPUT_DIR / "windsurf_parsed.json").write_text(json.dumps(output, indent=2))

        return models_by_tab

    except Exception as e:
        log(f"  Error scraping Windsurf models: {e}")
        import traceback

        traceback.print_exc()
        return {}


def normalize_model_name(name: str) -> str:
    """Normalize model name for matching with benchmarks."""
    return name.lower().replace(" ", "-").replace("(", "").replace(")", "").replace(".", "-")


def get_benchmark_scores(model_name: str) -> tuple[int | None, float | None]:
    """
    Get Arena ELO and TBench accuracy for a model from cached benchmark data.

    Returns:
        (arena_elo, tbench_accuracy) or (None, None) if not found
    """
    import sqlite3

    db_path = SCRIPT_DIR / "kilo_agents.db"
    if not db_path.exists():
        return (None, None)

    conn = sqlite3.connect(db_path)

    # Try 1: Exact name match (after removing provider prefix)
    cursor = conn.execute(
        "SELECT arena_elo, tbench_accuracy FROM agents WHERE name LIKE ?", (f"%{model_name}%",)
    )
    row = cursor.fetchone()
    if row and (row[0] is not None or row[1] is not None):
        conn.close()
        return (row[0], row[1])

    # Try 2: Match by key parts (Claude Opus 4.6, GPT-5.4, etc.)
    # Extract model family and version
    parts = model_name.split()
    if len(parts) >= 2:
        search_pattern = f"%{parts[0]}%{parts[1]}%"
        if len(parts) >= 3:
            search_pattern = f"%{parts[0]}%{parts[1]}%{parts[2]}%"

        cursor = conn.execute(
            "SELECT arena_elo, tbench_accuracy FROM agents WHERE name LIKE ?", (search_pattern,)
        )
        row = cursor.fetchone()
        if row and (row[0] is not None or row[1] is not None):
            conn.close()
            return (row[0], row[1])

    conn.close()
    return (None, None)


def update_cascade_models_md(
    models_by_tab: dict[str, list[WindsurfModel]], include_benchmarks: bool = True
) -> None:
    """Update cascade-models.md with scraped data organized by tabs."""
    md_path = (
        Path(__file__).parent.parent.parent
        / "docs"
        / "reference"
        / "windsurf"
        / "cascade-models.md"
    )

    if not md_path.parent.exists():
        log("Creating docs/reference/windsurf directory")
        md_path.parent.mkdir(parents=True, exist_ok=True)

    # Build markdown content
    lines = [
        "# Cascade Models and Credits",
        "",
        f"**Last Updated:** {datetime.now().strftime('%Y-%m-%d')}",
        "",
        "> 📋 **Source:** Automatically extracted from https://docs.windsurf.com/plugins/cascade/models",
        ">",
        "> Models are selected directly in Windsurf Cascade via the dropdown menu.",
        ">",
        "> Benchmark scores (Arena ELO, TBench) are matched from openlm.ai and tbench.ai data.",
        "",
        "---",
        "",
    ]

    # Add overview
    total_models = sum(len(models) for models in models_by_tab.values())
    lines.extend(
        [
            "## Overview",
            "",
            f"**Total Models:** {total_models} across {len(models_by_tab)} provider categories",
            "",
            "---",
            "",
        ]
    )

    # Deduplicate models across tabs
    seen_models = set()
    unique_models_by_tab = {}

    for tab, models in models_by_tab.items():
        unique_models = []
        for model in models:
            if model.name not in seen_models:
                seen_models.add(model.name)
                unique_models.append(model)
        if unique_models:
            unique_models_by_tab[tab] = unique_models

    # Add each tab as a section (only showing first occurrence)
    for tab in ["Self-serve", "Enterprise"]:
        if tab not in unique_models_by_tab:
            continue

        models = unique_models_by_tab[tab]
        if not models:
            continue

        lines.extend(
            [
                f"## {tab}",
                "",
            ]
        )

        if include_benchmarks:
            lines.extend(
                [
                    "| Model | Credits | Arena ELO | TBench | Notes |",
                    "|-------|---------|-----------|--------|-------|",
                ]
            )
        else:
            lines.extend(
                [
                    "| Model | Credits |",
                    "|-------|---------|",
                ]
            )

        # Sort by credits (free first, then ascending)
        sorted_models = sorted(models, key=lambda m: m.credits_numeric)

        for model in sorted_models:
            if include_benchmarks:
                elo, tbench = get_benchmark_scores(model.name)
                elo_str = str(elo) if elo else "—"
                tbench_str = f"{tbench:.1f}%" if tbench else "—"

                # Add notes for promo pricing
                notes = ""
                if "Promo" in model.credits:
                    notes = "Promo pricing"

                lines.append(
                    f"| {model.name} | {model.credits_numeric} | {elo_str} | {tbench_str} | {notes} |"
                )
            else:
                lines.append(f"| {model.name} | {model.credits} |")

        lines.extend(["", "---", ""])

    # Add footer
    lines.extend(
        [
            "",
            "## See Also",
            "",
            "- [Cascade Guide](cascade-guide.md)",
            "- [Features](features.md)",
            "",
        ]
    )

    # Write file
    content = "\n".join(lines)
    md_path.write_text(content)
    log(f"Updated {md_path}")


def main() -> int:
    log("=" * 50)
    log(f"Windsurf Model Scraper - {datetime.now().isoformat()}")
    log("=" * 50)

    models_by_tab = scrape_windsurf_models()

    if models_by_tab:
        update_cascade_models_md(models_by_tab)
        log("Scraping complete!")
        return 0
    else:
        log("No models extracted - check logs")
        return 1


if __name__ == "__main__":
    sys.exit(main())
