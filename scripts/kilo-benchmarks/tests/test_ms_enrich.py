"""Behavior Contract for scripts/kilo-benchmarks/ms_enrich.py.

Plan-2 (ModelScope new-row ingest) — Phases A/B/C populate this file.
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def test_a1_web_scrape_public_api_importable():
    """Vendored web-scrape module exposes the API Phase C consumes."""
    from libs.web_scrape import (  # noqa: F401
        FetchError,
        ParseError,
        WebScraper,
        extract_nextjs_data,
    )


def test_a2_web_scrape_scraper_constructs(tmp_path):
    """WebScraper(cache_dir, browserless_url, browserless_token) constructs."""
    from libs.web_scrape import WebScraper

    scraper = WebScraper(
        cache_dir=tmp_path / "cache",
        browserless_url="https://browser.example.com",
        browserless_token="fake-token",
    )
    assert scraper is not None


def test_a3_module_imports():
    """Scaffold sanity — module exists and imports cleanly."""
    import ms_enrich  # noqa: F401
