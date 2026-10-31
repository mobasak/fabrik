# fabrik-scrape — the research seats' raw-page fetch

`fabrik-scrape` is a local MCP server with one tool, `scrape(url)`. It returns a web page as markdown, or says why it
could not read it. Research seats use it for a raw page read (an exact quote, a live re-fetch) before exa or Firecrawl.
It replaces Firecrawl for that job, which is metered and ran out of credits on 2026-10-21. Firecrawl stays a fallback,
pinned to its basic proxy. Design: `docs/superpowers/specs/2026-10-21-own-scrape-tools-design.md` (D-1100); plan:
`docs/development/plans/2026-10-21-plan-3-own-scrape-slice-1a.md`; its universal wiring: D-1102.

## What it is

| Part | Where |
|---|---|
| Code (vendored, never edited here) | `libs/web_scrape_mcp/` — three fabrik-lib modules (`web_scrape_mcp`, `web_scrape`, `doc_crawl`) and `serve.py`; provenance in its README's `VENDORED_FROM` line; its `ruff.toml` keeps the vendored code out of lint and format |
| Service | `fabrik-scrape-mcp.service` (source `scripts/sysadmin/systemd/fabrik-scrape-mcp.service`, installed in `/etc/systemd/system/`) |
| Endpoint | `http://127.0.0.1:8034/mcp`, streamable HTTP, loopback only (`PORTS.md`) |
| Python | its own venv, `libs/web_scrape_mcp/.venv`, built from `libs/web_scrape_mcp/requirements.txt` (the MCP SDK v2; the hub `.venv` pins v1) |
| Registration | `scripts/sysadmin/mcp_defs.json` entry `fabrik-scrape`; in the emitter's universal set (`scripts/sysadmin/emit_mcp_project_config.py`), so every repo's `.mcp.json` carries it (D-1102) — once the unit is installed and enabled: until then the emitter withholds it and `mcp_health.py` names it withheld (W-07298e38) |
| Cache | `/var/cache/fabrik-scrape-mcp` (web-scrape's on-disk cache; systemd creates it; besides its private `/tmp`, the unit's only writable path) |
| Credentials | none — rendering is off in slice 1a, so the server never calls browserless |

## The `scrape` tool

`scrape(url, render="auto", max_length=20000, start_index=0, max_age_s=0)` returns either a page —
`{status, final_url, content_type, title, markdown, truncated, short, path, fetched_at}` — or
`{blocked: true, reason, status}`. The full contract and its classification table are in fabrik-lib's
`/opt/fabrik-lib/web-scrape-mcp/README.md` § The `scrape` tool.

What a caller does with each `blocked` reason (spec § Fallback contract):

| Reason | Meaning | What the caller does |
|---|---|---|
| `robots` | the site's robots.txt forbids it | report the page unreadable; no other fetcher, `WebFetch` and exa included |
| `scope` | not http(s), or a non-public address on any hop | report it; never fetched by anyone |
| `http-404`, `http-410`, another `http-4xx` | the server said no | report the page unreadable; no fallback |
| `http-429` | rate-limited after retries | report it rate-limited; never exa or Firecrawl |
| `http-5xx`, `render-unavailable` | a server error, or a JS-only page | exa, else Firecrawl while its rows are open |
| `empty` | no readable text, an unrecognised wall included | exa at most; never Firecrawl |
| `bot-wall` | a known bot wall (Cloudflare, DataDome …) | report it and cite another source; never exa or `WebFetch`, and Firecrawl only for a source the operator has cleared by name in the plan or work item |
| `unsupported` | a PDF, an image, a binary | Firecrawl while its rows are open, or report it |

Rendering (`render="always"`) answers `render-unavailable` until slice 1c; a PDF is `unsupported` until slice 1b.

## Run and check it

- Status: `systemctl status fabrik-scrape-mcp`; logs: `journalctl -u fabrik-scrape-mcp`.
- Health: `/opt/fabrik/libs/web_scrape_mcp/.venv/bin/python scripts/scrape_ledger.py --probe http://127.0.0.1:8034/mcp`
  prints `serverInfo` and the tool list; exit 0 when `scrape` is listed. A bare `curl` GET answers 406 on a healthy
  server, so it is never the check.
- Capability ledger: `scripts/scrape_ledger.py <input.json> --out <result.json>`. Each input row fixes its `expected`
  outcome and its fact strings before the run; the input is refused whole when a row lacks a field, names an unknown
  outcome, or expects `pass` with no fact. Facts match case-insensitively and a page is read to its end; both measures
  are the spec's `ledger2_run.py`. A fact split by inline markup (`**bold**`, a link) is not found, so take facts from
  one plain run of text.
- Researcher URLs: `scripts/scrape_ledger.py --harvest --since <date> --out <urls.json>` lists the URLs
  `fabrik-researcher` seats fetched, from subagent transcripts.

## Build, install, update

All of these run from the main checkout (`/opt/fabrik`) after the code merges. The install and the emitter run are an
operator gate.

1. Venv: `uv venv --python /usr/bin/python3 libs/web_scrape_mcp/.venv` (the system Python: the sandboxed unit cannot see
   `/home`, where uv keeps its own Pythons) then `uv pip install --python libs/web_scrape_mcp/.venv/bin/python -r
   libs/web_scrape_mcp/requirements.txt`.
2. Service: `sudo install -m 644 scripts/sysadmin/systemd/fabrik-scrape-mcp.service /etc/systemd/system/`,
   `sudo systemctl daemon-reload`, `sudo systemctl enable --now fabrik-scrape-mcp`.
3. Wiring: `python3 scripts/sysadmin/emit_mcp_project_config.py --check` (it reports and writes nothing), then the same
   without `--check`. That rewrites the generated `.mcp.json` of every repo under `/opt`. A session picks the server
   up only after it restarts.
4. Re-vendor after a fabrik-lib change: copy the three packages again from fabrik-lib main as its README says, update
   the `VENDORED_FROM` line, run `libs/web_scrape_mcp/tests` with the server venv, then
   `sudo systemctl restart fabrik-scrape-mcp`.

## Gotchas

- Keep the bind on loopback: the server has no authentication and fetches any public URL for whoever reaches it.
- The address guard is web-scrape's `SsrfSafeTransport`, passed by `serve.py`. Removing it lets a model-driven fetch
  reach local services, a redirect to `127.0.0.1` included.
- The unit is sandboxed (`ProtectSystem=strict`, `ProtectHome=true`, a private `/tmp`): apart from that private
  `/tmp`, the cache directory is its only writable path. A server that will not start after an edit usually needs a
  path it cannot see — read `journalctl -u fabrik-scrape-mcp` before loosening a setting.
- A 429's `Retry-After` is not honoured yet (slice 1b).
- `blocked: empty` includes a wall the tool does not recognise, so it never escalates to Firecrawl.

<!-- BEGIN related-scripts: generated by scripts/render_doc_script_links.py — do not hand-edit -->
## Related scripts

Scripts that declare this document in their `# AFTER-EDIT:` header — editing one of them
means updating this page in the same change. This list is generated from those headers
(`python3 scripts/render_doc_script_links.py`); add the doc to a script's header, not here.

- `scripts/scrape_ledger.py`
<!-- END related-scripts -->
