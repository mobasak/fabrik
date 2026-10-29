"""The MCP server: one tool, `scrape`, over the pure contract in `scrape.py`.

`mcp` (the Python SDK, `mcp>=2.3,<3`, whose server class is `MCPServer`) is imported only inside `build_server`, so
the contract and its tests need no SDK. The consumer's entrypoint builds `Deps` from ITS vendored copies of
`web_scrape` and `doc_crawl` and calls `build_server(deps).run(...)` — see the README's `serve.py`.
"""

from __future__ import annotations

from typing import Any, Literal

from .scrape import Deps
from .scrape import scrape as _scrape

INSTRUCTIONS = (
    "Raw-page fetch. `scrape(url)` returns the page as markdown with its HTTP status, final URL and fetch time, or "
    "{blocked: true, reason, status} when it cannot be read: robots, scope (a non-public address), http-<status>, "
    "bot-wall, empty, render-unavailable, unsupported. A blocked page is reported, never fetched another way that "
    "evades the block. Long pages: pass start_index to read the next chunk, and max_age_s > 0 from the second chunk "
    "on so every chunk comes from one fetch."
)


def build_server(deps: Deps, *, name: str = "fabrik-scrape") -> Any:
    """An `MCPServer` with the `scrape` tool bound to `deps`. Run it with
    `build_server(deps).run(transport="streamable-http", host=..., port=...)`."""
    from mcp.server.mcpserver import MCPServer
    from mcp.server.mcpserver.exceptions import ToolError as tool_error

    server = MCPServer(name, instructions=INSTRUCTIONS)

    @server.tool()  # type: ignore[untyped-decorator,unused-ignore]  # untyped where the SDK is absent or v1
    def scrape(
        url: str,
        render: Literal["auto", "always", "never"] = "auto",
        max_length: int = 20_000,
        start_index: int = 0,
        max_age_s: int = 0,
    ) -> dict[str, Any]:
        """Fetch one page as markdown (markdown first, then static HTML converted; rendering is off in this release).

        Returns {status, final_url, content_type, title, markdown, truncated, short, path, fetched_at}, or
        {blocked: true, reason, status}. `short: true` marks a page with under 800 characters of text.
        `max_age_s=0` re-fetches live; a larger value accepts a cached copy no older than that.
        """
        try:
            return _scrape(
                url,
                deps=deps,
                render=render,
                max_length=max_length,
                start_index=start_index,
                max_age_s=max_age_s,
            )
        except ValueError as exc:
            # A ToolError keeps its message for the agent; any other exception reaches it only as the SDK's
            # "Error executing tool scrape", so "start_index past the end" would read like a broken server.
            raise tool_error(str(exc)) from exc

    return server
