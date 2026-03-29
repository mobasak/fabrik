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

# Provider tabs under Enterprise
PROVIDER_TABS = ["Recommended", "Windsurf", "Anthropic", "OpenAI", "Google", "xAI", "Open Source"]


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
    """Parse credit string to numeric value.

    Returns float value for sorting. Returns -1.0 for unavailable (—).
    Handles cases like "2Promo pricing..." by extracting leading numeric value.
    """
    import re

    # Remove emoji
    clean = credits_str.replace("🎁", "").strip()

    # Handle unavailable credits (em-dash)
    if clean == "—" or clean == "-":
        return -1.0

    # Handle "Free" or explicit "0"
    if clean.lower() == "free" or clean == "0":
        return 0.0

    # Extract leading numeric value (handles "2Promo..." -> "2")
    match = re.match(r"^(\d+\.?\d*)", clean)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            return -1.0

    # If no numeric prefix found, treat as unavailable
    return -1.0


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
    Scrape Windsurf model data from all provider tabs using Selenium.
    Returns dict mapping provider name -> list of models.
    """
    log("Fetching Windsurf models page...")
    url = "https://docs.windsurf.com/plugins/cascade/models#enterprise"

    try:
        driver = get_browser()
        driver.get(url)

        # Wait for page to load
        time.sleep(3)

        # Save raw HTML for debugging
        html = driver.page_source
        (OUTPUT_DIR / "windsurf_raw.html").write_text(html)

        models_by_provider = {}

        # Click each provider tab button (class="models-tab-button")
        for provider_name in PROVIDER_TABS:
            log(f"  Scraping provider: {provider_name}")
            try:
                # Find the specific button by class and text content
                js_click_script = f"""
                const buttons = document.querySelectorAll('button.models-tab-button');
                let targetButton = null;

                for (const btn of buttons) {{
                    if (btn.textContent.trim() === '{provider_name}') {{
                        targetButton = btn;
                        break;
                    }}
                }}

                if (targetButton) {{
                    targetButton.click();
                    return true;
                }}
                return false;
                """

                clicked = driver.execute_script(js_click_script)

                if not clicked:
                    log(f"    No tab button found for {provider_name}")
                    continue

                log(f"    Clicked {provider_name} tab")

                # Wait for the active class to change and content to load
                time.sleep(2)

                # Extract from the updated DOM
                current_html = driver.page_source
                soup = BeautifulSoup(current_html, "html.parser")

                tables = soup.find_all("table")
                models = []

                for table in tables:
                    headers = table.find_all("th")
                    header_text = [h.get_text(strip=True) for h in headers]

                    if "Model" not in header_text or "Credits" not in header_text:
                        continue

                    rows = table.find_all("tr")[1:]

                    for row in rows:
                        cells = row.find_all("td")
                        if len(cells) >= 2:
                            model_name = cells[0].get_text(strip=True)
                            credits_str = cells[1].get_text(strip=True)

                            if model_name:
                                credits_numeric = parse_credits(credits_str)
                                models.append(
                                    WindsurfModel(
                                        name=model_name,
                                        credits=credits_str,
                                        provider=provider_name,
                                        credits_numeric=credits_numeric,
                                    )
                                )

                    if models:
                        break

                if models:
                    models_by_provider[provider_name] = models
                    preview = ", ".join([m.name for m in models[:3]])
                    log(f"    Found {len(models)} models: {preview}")
                else:
                    log(f"    No models found for {provider_name}")

            except Exception as e:
                log(f"  Error scraping {provider_name}: {e}")
                import traceback

                traceback.print_exc()

        driver.quit()

        # Log results
        total_models = sum(len(models) for models in models_by_provider.values())
        log(f"  Extracted {total_models} models from {len(models_by_provider)} providers")

        # Save parsed data
        output = {
            "source": "docs.windsurf.com",
            "url": url,
            "scraped_at": datetime.now().isoformat(),
            "total_providers": len(models_by_provider),
            "total_models": total_models,
            "providers": {
                provider: [m.to_dict() for m in models]
                for provider, models in models_by_provider.items()
            },
        }
        (OUTPUT_DIR / "windsurf_parsed.json").write_text(json.dumps(output, indent=2))

        return models_by_provider

    except Exception as e:
        log(f"  Error scraping Windsurf models: {e}")
        import traceback

        traceback.print_exc()
        return {}


def normalize_model_for_benchmark(model_name: str) -> str:
    """
    Strip variant suffixes to get base model name for benchmark lookup.

    Benchmark scores belong to base models, not variants (reasoning levels,
    thinking modes, speed tiers, context sizes).

    PROTECTED model tiers (never stripped):
        Mini, Pro, Flash, Turbo, Codex, Max, Spark
        These are distinct models, not variants.

    STRIPPED suffixes:
        Thinking, Fast, Slow, reasoning levels, context sizes

    Examples:
        Claude Opus 4.6 (Thinking) → Claude Opus 4.6
        GPT-5.4 Mini (Medium Reasoning) → GPT-5.4 Mini (Mini preserved!)
        GPT-5.4 (Low Reasoning) → GPT-5.4
        Claude Opus 4.6 Fast Thinking → Claude Opus 4.6
        Gemini 3 Flash High → Gemini 3 Flash (Flash preserved!)
        Claude Opus 4.6 1M → Claude Opus 4.6
    """
    import re

    # Protected model tiers - NEVER strip these
    protected = {"Mini", "Pro", "Flash", "Turbo", "Codex", "Max", "Spark", "Ultra"}

    # Strip patterns in order (most specific to least specific)
    # Apply repeatedly until stable
    for _ in range(5):
        prev = model_name

        # 1. Strip context size suffixes (1M, 200K, etc.)
        model_name = re.sub(r"\s+\d+[MK]$", "", model_name, flags=re.IGNORECASE).strip()

        # 2. Strip parenthesized suffixes (Thinking, reasoning levels)
        model_name = re.sub(r"\s*\([^)]*\)$", "", model_name).strip()

        # 3. Strip speed/mode suffixes (Thinking, Fast, Slow)
        # Only strip if the suffix itself is NOT a protected term
        for suffix in ["Thinking", "Fast", "Slow"]:
            if suffix not in protected:
                model_name = re.sub(rf"\s+{suffix}$", "", model_name, flags=re.IGNORECASE).strip()

        # 4. Strip tier suffixes (Minimal, Low, Medium, High, Extra High)
        # Only strip if the suffix itself is NOT a protected term
        for tier in ["Extra High", "High", "Medium", "Low", "Minimal"]:
            if tier not in protected:
                model_name = re.sub(rf"\s+{tier}$", "", model_name, flags=re.IGNORECASE).strip()

        if model_name == prev:
            break

    return model_name


def get_benchmark_scores(model_name: str) -> tuple[int | None, float | None]:
    """
    Get Arena ELO and TBench accuracy for a model from cached benchmark data.

    Fallback hierarchy:
    1. Exact base model (e.g., GPT-5.4 Mini)
    2. Normalized name match (handle formatting differences)
    3. Model family match (first 2-3 words)

    Returns:
        (arena_elo, tbench_accuracy) or (None, None) if not found
    """
    import sqlite3

    db_path = SCRIPT_DIR / "kilo_agents.db"
    if not db_path.exists():
        return (None, None)

    conn = sqlite3.connect(db_path)

    # Normalize to base model (strip variant suffixes)
    base_model = normalize_model_for_benchmark(model_name)

    # Try 1: Direct match with base model name
    cursor = conn.execute(
        "SELECT arena_elo, tbench_accuracy FROM agents WHERE name LIKE ?", (f"%{base_model}%",)
    )
    row = cursor.fetchone()
    if row and (row[0] is not None or row[1] is not None):
        conn.close()
        return (row[0], row[1])

    # Try 2: Match by normalized name (handle different formatting)
    normalized = base_model.lower().replace(" ", "").replace("-", "").replace(".", "")
    cursor = conn.execute("SELECT name, arena_elo, tbench_accuracy FROM agents")
    for db_row in cursor.fetchall():
        db_name = db_row[0].lower().replace(" ", "").replace("-", "").replace(".", "")
        if normalized in db_name or db_name in normalized:
            if db_row[1] is not None or db_row[2] is not None:
                conn.close()
                return (db_row[1], db_row[2])

    # Try 4: Match by model family (first 2-3 words)
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

    # Add each provider as a section (show all providers, even with duplicate models)
    for provider in PROVIDER_TABS:
        if provider not in models_by_tab:
            continue

        models = models_by_tab[provider]
        if not models:
            continue

        lines.extend(
            [
                f"## {provider}",
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
