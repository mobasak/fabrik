"""doc-crawl — framework-free doc/site crawl layer (vendor this folder, don't import).

Composes an injected `fetch_fn` (e.g. web-scrape's `fetch_static`): sitemap discovery
+ scoped BFS + incremental SHA256 dedup + LLM-free page classification + HTML→markdown.
Relative imports only, so it works under any package name after `cp -r`.
"""

from .classify import classify_page
from .crawler import Crawler
from .dedup import IncrementalIndex, content_hash
from .readability import html_to_markdown, strip_chrome
from .sitemap import discover_sitemap_urls, parse_sitemap
from .types import ClassifyResult, CrawlProfile, DocPage, PageType

__all__ = [
    "Crawler",
    "CrawlProfile",
    "DocPage",
    "PageType",
    "ClassifyResult",
    "IncrementalIndex",
    "content_hash",
    "classify_page",
    "html_to_markdown",
    "strip_chrome",
    "discover_sitemap_urls",
    "parse_sitemap",
]
