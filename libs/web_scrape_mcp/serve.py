import os
from pathlib import Path

import httpx
from doc_crawl.readability import html_to_markdown
from web_scrape import FetchError, RobotsError, ScopeError, SsrfSafeTransport, WebScraper, is_bot_wall
from web_scrape_mcp import Deps, build_server

scraper = WebScraper(
    Path(os.getenv("WEB_SCRAPE_MCP_CACHE_DIR", ".tmp/web-scrape-mcp")),
    transport=SsrfSafeTransport(),  # refuses loopback/private/link-local/metadata on EVERY hop
)
deps = Deps(
    fetch=scraper.fetch_static_result,
    to_markdown=html_to_markdown,
    is_bot_wall=is_bot_wall,
    robots_error=RobotsError,
    scope_error=ScopeError,
    fetch_error=FetchError,
    url_errors=(httpx.InvalidURL, httpx.UnsupportedProtocol, UnicodeError),
)
if __name__ == "__main__":
    build_server(deps).run(
        transport="streamable-http",
        host=os.getenv("WEB_SCRAPE_MCP_HOST", "127.0.0.1"),
        port=int(os.environ["WEB_SCRAPE_MCP_PORT"]),  # required: take it from your PORTS registry
    )
