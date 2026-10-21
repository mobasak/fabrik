"""web-scrape-mcp — the `fabrik-scrape` MCP server: a raw-page fetch for AI agents (vendor this folder, don't import).

Relative imports only. The contract (`scrape`) is pure over injected `Deps`; `build_server` imports the MCP SDK
lazily. Nothing here imports `web_scrape` or `doc_crawl`: the consumer's entrypoint injects its own vendored copies.
"""

from .scrape import EMPTY_CHARS, RENDER_MODES, SHORT_CHARS, Deps, FetchedPage, scrape
from .server import INSTRUCTIONS, build_server

__all__ = [
    "EMPTY_CHARS",
    "INSTRUCTIONS",
    "RENDER_MODES",
    "SHORT_CHARS",
    "Deps",
    "FetchedPage",
    "build_server",
    "scrape",
]
