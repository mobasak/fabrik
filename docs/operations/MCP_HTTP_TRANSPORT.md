# Fabrik Citation Verifier — MCP HTTP Transport

Status: **PRIMARY** (2026-05-09 onward). The stdio entrypoint remains in the codebase as fallback but is no longer used.

**Last Updated:** 2026-06-16 (verified accurate — fabrik-mcp-http + citation-verifier services active locally; 5 MCP tools; streamable-http transport)

## Why HTTP, not stdio

The original architecture was Claude Code (Windows) → stdio → `wsl.exe` → Python MCP server. Verified working via direct probes (`claude mcp list` showed `✓ Connected`, externally-driven `initialize` + `tools/list` handshake completed in <500ms with 5 tools).

But interactive Claude Code sessions failed to register fabrik's tools at session boot. Confirmed via the live session transcript at `~/.claude/projects/<project>/<session>.jsonl`: the `deferred_tools_delta` attachment emitted at session start listed **3 of 4** local stdio MCPs (exa, firecrawl, pubchem — all `npx`-based) but skipped fabrik (the only `wsl.exe`-based one). Two different stdio spawn shapes were tried (`bash -lc "PYTHONPATH=... python -m ..."` and `env PYTHONPATH=... python -u -m ...`); both worked externally but neither registered in-session reliably.

`wsl.exe`-based stdio MCP servers appear fragile during Claude Code's session-boot window. HTTP transport bypasses the entire Windows→WSL stdio path — Claude Code (a Windows process) does a TCP connect to `127.0.0.1:8033`, which hits the WSL2 forwarded port, which lands directly on the Python `streamable-http` server. No `wsl.exe` invocation involved.

## Architecture

```
Claude Code (Windows)
    │  HTTP POST /mcp  (streamable-http MCP transport)
    ▼
127.0.0.1:8033  ←── systemd unit: fabrik-mcp-http.service
    │
    │  in-process FastMCP `mcp` instance
    │  (same instance used by stdio entrypoint)
    ▼
httpx client
    │  HTTP
    ▼
127.0.0.1:8032  ←── systemd unit: citation-verifier.service
    │
    ▼
PostgreSQL + 12 resolver backends
```

Two services. `fabrik-mcp-http` `Requires=citation-verifier`, so they start/stop together. Both are managed by systemd with `Restart=on-failure RestartSec=5`.

## Files

| Path | Role |
|---|---|
| `/opt/fabrik-citation-verifier/mcp_server/server.py` | Original stdio entrypoint (still works, kept as fallback) |
| `/opt/fabrik-citation-verifier/mcp_server/server_http.py` | NEW. HTTP entrypoint. Imports `mcp` from `server.py`, calls `mcp.run(transport="streamable-http")` |
| `/etc/systemd/system/fabrik-mcp-http.service` | NEW. systemd unit. Listens on `127.0.0.1:8033/mcp`, logs to `/var/log/fabrik/mcp-http.log` |
| `/etc/systemd/system/citation-verifier.service` | UNCHANGED. Backend at `127.0.0.1:8032`. |

## Claude Code config

`.claude.json` `mcpServers` entry:

```json
"fabrik-citation-verifier": {
  "type": "http",
  "url": "http://127.0.0.1:8033/mcp"
}
```

## Operations

```bash
# Status
systemctl status fabrik-mcp-http.service

# Restart (e.g. after a code change)
sudo systemctl restart fabrik-mcp-http.service

# Live logs
sudo journalctl -u fabrik-mcp-http.service -f
# or
tail -f /var/log/fabrik/mcp-http.log

# Verify external handshake
curl -sS -X POST http://127.0.0.1:8033/mcp \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1"}}}'

# Verify Claude Code sees it (run from any project dir)
claude mcp list | grep fabrik
# Expected: fabrik-citation-verifier: http://127.0.0.1:8033/mcp (HTTP) - ✓ Connected
```

## Diagnostic: a session is missing fabrik tools

If a Claude Code session reports no `mcp__fabrik-citation-verifier__*` namespace:

1. **Check the systemd unit is running.** `systemctl is-active fabrik-mcp-http`. If not, start it.
2. **Check the port is bound.** `ss -tlnp | grep ':8033'`. If absent, restart the service and inspect logs.
3. **Hit the URL.** The curl one-liner above. If it doesn't return a JSON `result`, the wrapper is broken — read `/var/log/fabrik/mcp-http.log`.
4. **Check `.claude.json`.** The fabrik entry must be `{"type":"http","url":"http://127.0.0.1:8033/mcp"}`.
5. **Check the live session transcript.** Path is `~/.claude/projects/<project-path-mangled>/<session-id>.jsonl`. The first few lines contain a `deferred_tools_delta` attachment listing every MCP tool that registered at boot. If `mcp__fabrik-citation-verifier__verify_citation` (or any of the 5 fabrik tools) is in that list, the session has fabrik — the AI assistant inside the session may simply be misreporting. If the tool is absent from the delta, the session genuinely failed to register fabrik at boot.
6. **If still absent after 1-5:** restart the Claude Code session. MCP tools register at session boot only. Mid-session config changes don't take effect.

## Reverting to stdio (if HTTP transport breaks)

```bash
# Stop the HTTP service
sudo systemctl stop fabrik-mcp-http
sudo systemctl disable fabrik-mcp-http
```

Then in `.claude.json`, replace the fabrik entry with:

```json
"fabrik-citation-verifier": {
  "type": "stdio",
  "command": "wsl.exe",
  "args": [
    "-d", "Ubuntu-24.04", "--",
    "env", "PYTHONPATH=/opt/fabrik-citation-verifier",
    "/opt/fabrik-citation-verifier/mcp_server/.venv/bin/python",
    "-u", "-m", "mcp_server.server"
  ],
  "env": {"PYTHONPATH": "/opt/fabrik-citation-verifier"}
}
```

Restart Claude Code session. Note: this will reproduce the original session-boot registration failure on some boots; not recommended unless HTTP transport itself fails.

## Change history

- **2026-05-09** — HTTP transport introduced as primary. stdio kept as fallback. Root cause was `wsl.exe`-based stdio MCP servers failing to register during Claude Code session boot, while NPX-based stdio servers and HTTP servers (cloud connectors) registered cleanly.
