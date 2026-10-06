# wsl-mcp — Claude Desktop ↔ WSL bridge (HTTP, systemd, no `wsl.exe` spawn)

**Status:** ✅ LIVE 2026-10-06 (D-616). Supersedes `wsl-shell-mcp-setup.md` (the `@mako10k/mcp-shell-server` stdio bridge) and the `wsl-filesystem` stdio entry.
**Where it runs:** the local WSL2 dev box; Claude Desktop (Windows) and Claude Code connect to it.

## Why this replaces the stdio bridge

Every stdio entry Desktop spawned through `wsl.exe` had three failure classes, all seen live:
1. **Spawn fragility** — `wsl.exe`-based stdio servers register unreliably at client boot (already measured for Claude Code in `MCP_HTTP_TRANSPORT.md`); Desktop spawned each server **twice** (two `mcp-shell-server` + two `mcp-server-filesystem` processes, 1 s apart, measured 2026-10-06 11:15).
2. **Relay timeouts** — a tool call reached the server, was answered in 0.3 s, and Desktop still reported "No result received after 4 minutes" (2026-10-06, `write_file`). Any Desktop restart (incl. every Store auto-update of the MSIX build `Claude_2.19675.1.0`) tears down the spawned processes and their pipes.
3. **Server quirks** — mcp-shell-server's Zod bug needed a patch after every npm update, rejected `description`, and node-pty broke on every Node ABI change.

Now the server is a **systemd service inside WSL** (`wsl-mcp.service`, streamable-HTTP on `127.0.0.1:8040/mcp`). Desktop reaches it through a **Windows-native** `npx mcp-remote` stdio bridge — the same spawn shape as the `c-drive` / `vault-write` entries that have never failed. A Desktop update only restarts the bridge; the WSL side keeps running. `fabrik-citation-verifier` uses the same shape against its existing `:8033`.

## Pieces

| Where | Path | Role |
|---|---|---|
| WSL | `/opt/fabrik/tools/wsl-mcp/server.py` | FastMCP (mcp 1.30, pinned `<2`) — tools `bash`, `read_file`, `write_file`, `edit_file`, `list_dir` |
| WSL | `/opt/fabrik/tools/wsl-mcp/.venv` | venv (gitignored); `requirements.txt` pins `mcp==1.30.0` |
| WSL | `/etc/systemd/system/wsl-mcp.service` (copy of `tools/wsl-mcp/wsl-mcp.service`) | `Restart=always`, user `ozgur`, log `/var/log/fabrik/wsl-mcp.log` |
| Windows | `%APPDATA%\Claude\claude_desktop_config.json` → `"wsl"` | `npx.cmd -y mcp-remote@0.14.3 http://127.0.0.1:8040/mcp --allow-http` |
| Windows | Scheduled task `WSL-KeepAlive` (at logon) | `wsl.exe -d Ubuntu-24.04 -u ozgur --exec /bin/sleep infinity` — keeps the distro (and systemd) up so `:8040` is reachable before Desktop starts |
| Windows | `%APPDATA%\Claude\claude_desktop_config.backup-20261006-pre-wsl-mcp.json` | config as it was before the switch |

## `bash` tool contract (the old quirk is gone)

`bash(command, description?, comment?, timeout_seconds=120 (max 3600), working_directory?, stdin?, env?)`
→ `{stdout, stderr, exit_code, timed_out, cwd}`. Runs `/bin/bash -lc` as `ozgur` (full login PATH: docker, ssh vps, fabrik, node, python). Both `description` and `comment` are accepted and ignored. Output is clipped to 200 000 chars per stream (head+tail). Jobs longer than the timeout: `setsid nohup … &` and poll.

## Verify (run any time)

```bash
systemctl is-active wsl-mcp && ss -tlnp | grep ':8040'
curl -sS -X POST http://127.0.0.1:8040/mcp -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' -d '{"jsonrpc":"2.0","id":2,"method":"tools/list"}' \
  | python3 -c "import sys,json;print([t['name'] for t in json.load(sys.stdin)['result']['tools']])"
# expected: ['bash', 'read_file', 'write_file', 'edit_file', 'list_dir']
```
From Windows (PowerShell): `Invoke-WebRequest http://127.0.0.1:8040/mcp -Method POST -ContentType application/json -Headers @{Accept="application/json, text/event-stream"} -Body '{"jsonrpc":"2.0","id":2,"method":"tools/list"}'` → 200.
In Desktop: ask for `echo alive $(whoami)@$(hostname)` through `wsl:bash`.

## Operations

```bash
sudo systemctl restart wsl-mcp        # after editing server.py
tail -f /var/log/fabrik/wsl-mcp.log
```
Desktop logs moved (since the MSIX build) to `%LOCALAPPDATA%\Claude\Logs\mcp-server-wsl.log` — NOT `%APPDATA%\Claude\logs` any more.

## Failure map

| Symptom | Cause | Fix |
|---|---|---|
| Desktop shows `wsl` disconnected right after Windows login | WSL not up yet / keepalive task not running | `Start-ScheduledTask WSL-KeepAlive`; check `Get-ScheduledTask WSL-KeepAlive` |
| `:8040` not bound in WSL | unit down | `sudo systemctl status wsl-mcp`; read `/var/log/fabrik/wsl-mcp.log` |
| npx cannot fetch `mcp-remote` (offline first run) | npm cache empty | run once online: `npx -y mcp-remote@0.14.3 --help` on Windows |
| tool returns `timed_out: true` | command exceeded `timeout_seconds` | raise it (≤3600) or detach the job |

## Rollback

Restore the backup config, `sudo systemctl disable --now wsl-mcp`, restart Desktop. The old scripts (`/home/ozgur/start-mcp-shell.sh`, patch, healer) are untouched.
