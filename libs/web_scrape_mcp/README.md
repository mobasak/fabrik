# libs/web_scrape_mcp — the vendored `fabrik-scrape` MCP server

VENDORED_FROM: fabrik-lib main 5e428214 (contains a3ef7fad, fabrik-lib D-537 — web-scrape-mcp and web-scrape G5/G6/G7/G10/G11)

Three fabrik-lib modules, copied byte-identical, plus the consumer entrypoint fabrik-lib's README prescribes:

| Path | From fabrik-lib | Role |
|---|---|---|
| `web_scrape_mcp/` | `web-scrape-mcp/web_scrape_mcp/` | the MCP server and the `scrape` contract |
| `web_scrape/` | `web-scrape/web_scrape/` | the fetcher, `SsrfSafeTransport`, `is_bot_wall` |
| `doc_crawl/` | `doc-crawl/doc_crawl/` | `readability.html_to_markdown` |
| `tests/` | `web-scrape-mcp/tests/` | the module's own tests (not collected by the hub suite) |
| `serve.py` | the README's `serve.py`, copied whole | wires the three; run with this folder on `sys.path` |

The three packages sit together here, apart from the hub's older `libs/web_scrape/` (kilo-db's copy), so the server
always imports the 2026-10-21 web-scrape it needs.

Run, from the hub root: `PYTHONPATH=libs/web_scrape_mcp WEB_SCRAPE_MCP_PORT=8034
libs/web_scrape_mcp/.venv/bin/python libs/web_scrape_mcp/serve.py`. Its own venv is built from `requirements.txt`.
How it runs as a service, its port and its `blocked` reasons: `docs/reference/fabrik-scrape-mcp.md`.

Never edit these files here: a fix goes to fabrik-lib (mail), then re-vendor.
