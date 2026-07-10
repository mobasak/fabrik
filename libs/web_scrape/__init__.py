"""web-scrape — deterministic web-scrape primitive (vendor this folder, don't import).

Relative imports only, so it works under any package name after
`cp -r web-scrape/ src/web_scrape/`.
"""

from .webscrape import (
    FetchError,
    ParseError,
    RobotsError,
    WebScrapeError,
    WebScraper,
    extract_apollo_state,
    extract_nextjs_data,
    extract_react_props,
    is_bot_wall,
)

__all__ = [
    "FetchError",
    "ParseError",
    "RobotsError",
    "WebScrapeError",
    "WebScraper",
    "extract_apollo_state",
    "extract_nextjs_data",
    "extract_react_props",
    "is_bot_wall",
]
