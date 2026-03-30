#!/usr/bin/env python3
"""
Scrape benchmark data from tbench.ai and openlm.ai.

Extracts ALL agents with their rankings, not just pattern-matched ones.
Uses proper HTML parsing similar to /opt/web-scraper tools.

Usage:
    python scripts/scrape_benchmarks.py
    python scripts/scrape_benchmarks.py --tbench-only
    python scripts/scrape_benchmarks.py --arena-only
"""

import json
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from functools import wraps
from pathlib import Path

import requests
from bs4 import BeautifulSoup

SCRIPT_DIR = Path(__file__).parent
OUTPUT_DIR = SCRIPT_DIR / "cache"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


@dataclass
class BenchmarkEntry:
    rank: int
    model: str
    score: float
    provider: str = ""
    extra: dict = None

    def to_dict(self) -> dict:
        return {
            "rank": self.rank,
            "model": self.model,
            "score": self.score,
            "provider": self.provider,
            "extra": self.extra or {},
        }


def retry_on_network_error(max_attempts=3, delay=2, backoff=2):
    """Retry decorator for network operations with exponential backoff."""

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            attempt = 1
            current_delay = delay
            while attempt <= max_attempts:
                try:
                    return func(*args, **kwargs)
                except (requests.exceptions.RequestException, ConnectionError) as e:
                    if attempt == max_attempts:
                        log(f"  Error scraping {func.__name__}: {e}")
                        raise
                    log(
                        f"  Attempt {attempt}/{max_attempts} failed, retrying in {current_delay}s..."
                    )
                    time.sleep(current_delay)
                    current_delay *= backoff
                    attempt += 1
            return func(*args, **kwargs)

        return wrapper

    return decorator


def log(msg: str) -> None:
    print(f"[scrape] {msg}")


@retry_on_network_error(max_attempts=3, delay=2, backoff=2)
def scrape_terminal_bench() -> list[BenchmarkEntry]:
    """
    Scrape Terminal Bench 2.0 leaderboard from tbench.ai.
    Returns list of all agents with accuracy scores.
    """
    log("Fetching Terminal Bench 2.0...")
    url = "https://www.tbench.ai/leaderboard/terminal-bench/2.0"

    try:
        response = requests.get(url, headers=HEADERS, timeout=30)
        response.raise_for_status()
        html = response.text

        # Save raw HTML for debugging
        (OUTPUT_DIR / "tbench_raw.html").write_text(html)

        entries = []
        import re

        # Terminal Bench embeds data as escaped JSON in Next.js script tags
        # The JSON uses escaped quotes: \"agent\":\"SWE-Agent\"
        # Pattern to extract each entry block
        entry_pattern = re.compile(
            r'\\?"agent\\?":\s*\\?"([^"\\]+)\\?".*?'
            r'\\?"model\\?":\s*\[\\?"([^"\\]+)\\?"\].*?'
            r'\\?"accuracy\\?":\s*([\d.]+)',
            re.DOTALL,
        )

        matches = entry_pattern.findall(html)

        # Parse matches into entries
        seen = set()
        for match in matches:
            agent_name, model_name, accuracy_str = match
            accuracy = float(accuracy_str) * 100  # Convert to percentage

            # Create unique key to avoid duplicates
            key = f"{agent_name}_{model_name}"
            if key in seen:
                continue
            seen.add(key)

            # Clean up model name (remove quotes if present)
            model_name = model_name.strip('"').strip("'")

            entries.append(
                BenchmarkEntry(
                    rank=0,  # Will be set after sorting
                    model=model_name,
                    score=round(accuracy, 1),
                    provider=agent_name,
                    extra={"metric": "accuracy_percent", "agent": agent_name},
                )
            )

        # Sort by accuracy descending and assign ranks
        entries.sort(key=lambda x: x.score, reverse=True)
        for i, entry in enumerate(entries):
            entry.rank = i + 1

        log(f"  Found {len(entries)} Terminal Bench entries")

        # Save parsed data
        output = {
            "source": "tbench.ai",
            "url": url,
            "scraped_at": datetime.now().isoformat(),
            "total_entries": len(entries),
            "entries": [e.to_dict() for e in entries],
        }
        (OUTPUT_DIR / "tbench_parsed.json").write_text(json.dumps(output, indent=2))

        return entries

    except Exception as e:
        log(f"  Error scraping Terminal Bench: {e}")
        return []


@retry_on_network_error(max_attempts=3, delay=2, backoff=2)
def scrape_chatbot_arena() -> list[BenchmarkEntry]:
    """
    Scrape Chatbot Arena leaderboard from openlm.ai.
    Returns list of all models with Elo ratings.
    """
    log("Fetching Chatbot Arena...")
    url = "https://openlm.ai/chatbot-arena/"

    try:
        response = requests.get(url, headers=HEADERS, timeout=30)
        response.raise_for_status()
        html = response.text

        # Save raw HTML for debugging
        (OUTPUT_DIR / "arena_raw.html").write_text(html)

        soup = BeautifulSoup(html, "html.parser")
        entries = []

        # The Arena page shows model names with Elo scores
        # Format: [Model Name] followed by code blocks with numbers
        # e.g., [Gemini-3.1-Pro] \n ``` \n 1505 \n ```

        import re

        # Get all text content
        text = soup.get_text(separator="\n")
        lines = [line.strip() for line in text.split("\n") if line.strip()]

        # Pattern: Model name (link text) followed by Elo score in code block
        # Look for 4-digit numbers (Elo scores are typically 1200-1600)
        elo_pattern = re.compile(r"^(\d{4})$")

        current_rank = 0
        i = 0

        while i < len(lines):
            line = lines[i]

            # Check if this is an Elo score
            match = elo_pattern.match(line)
            if match:
                elo = int(match.group(1))

                # Look backwards for the model name
                model_name = ""
                for j in range(i - 1, max(0, i - 10), -1):
                    candidate = lines[j]
                    # Skip pure numbers and short strings
                    if (
                        len(candidate) > 3
                        and not candidate.isdigit()
                        and not candidate.startswith("```")
                    ):
                        # Check if it looks like a model name
                        if any(c.isalpha() for c in candidate) and not candidate.startswith("http"):
                            model_name = candidate
                            break

                if model_name and 1100 <= elo <= 1700:
                    current_rank += 1
                    # Extract provider from model name
                    provider = ""
                    if "claude" in model_name.lower():
                        provider = "Anthropic"
                    elif "gpt" in model_name.lower() or model_name.lower().startswith("o"):
                        provider = "OpenAI"
                    elif "gemini" in model_name.lower():
                        provider = "Google"
                    elif "grok" in model_name.lower():
                        provider = "xAI"
                    elif "qwen" in model_name.lower():
                        provider = "Alibaba"
                    elif "glm" in model_name.lower():
                        provider = "Zhipu"
                    elif "deepseek" in model_name.lower():
                        provider = "DeepSeek"
                    elif "llama" in model_name.lower():
                        provider = "Meta"
                    elif "mistral" in model_name.lower() or "codestral" in model_name.lower():
                        provider = "Mistral"

                    entries.append(
                        BenchmarkEntry(
                            rank=current_rank,
                            model=model_name,
                            score=elo,
                            provider=provider,
                            extra={"metric": "elo_rating"},
                        )
                    )
            i += 1

        # Sort by Elo descending and re-rank
        entries.sort(key=lambda x: x.score, reverse=True)
        for i, entry in enumerate(entries):
            entry.rank = i + 1

        # Remove duplicates (same model name)
        seen = set()
        unique_entries = []
        for entry in entries:
            model_lower = entry.model.lower()
            if model_lower not in seen:
                seen.add(model_lower)
                unique_entries.append(entry)

        log(f"  Found {len(unique_entries)} Chatbot Arena entries")

        # Save parsed data
        output = {
            "source": "openlm.ai",
            "url": url,
            "scraped_at": datetime.now().isoformat(),
            "total_entries": len(unique_entries),
            "entries": [e.to_dict() for e in unique_entries],
        }
        (OUTPUT_DIR / "arena_parsed.json").write_text(json.dumps(output, indent=2))

        return unique_entries

    except Exception as e:
        log(f"  Error scraping Chatbot Arena: {e}")
        return []


def main() -> int:
    log("=" * 50)
    log(f"Benchmark Scraper - {datetime.now().isoformat()}")
    log("=" * 50)

    tbench_only = "--tbench-only" in sys.argv
    arena_only = "--arena-only" in sys.argv

    results = {}

    if not arena_only:
        tbench = scrape_terminal_bench()
        results["terminal_bench"] = {
            "count": len(tbench),
            "top_5": [e.to_dict() for e in tbench[:5]] if tbench else [],
        }

    if not tbench_only:
        arena = scrape_chatbot_arena()
        results["chatbot_arena"] = {
            "count": len(arena),
            "top_5": [e.to_dict() for e in arena[:5]] if arena else [],
        }

    log("=" * 50)
    log("Results Summary:")
    for source, data in results.items():
        log(f"  {source}: {data['count']} entries")
        if data["top_5"]:
            log(f"    Top: {data['top_5'][0]['model']} ({data['top_5'][0]['score']})")

    # Save combined results
    combined = {
        "scraped_at": datetime.now().isoformat(),
        "results": results,
    }
    (OUTPUT_DIR / "combined_results.json").write_text(json.dumps(combined, indent=2))

    log(f"Output saved to: {OUTPUT_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
