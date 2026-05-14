# Claude Desktop wsl-shell MCP — Complete Setup

**Status:** ✅ Working (2026-05-08)
**Where it runs:** Local Windows workstation (not VPS)
**Purpose:** Lets Claude Desktop execute shell commands inside WSL Ubuntu, which can then `ssh vps` for VPS operations

---

## What This Solves

Claude Desktop's `wsl-shell` MCP server provides the `shell_execute` tool. Without this tool, Claude can't run any command in the WSL environment — making it impossible to develop or operate Fabrik from Claude Desktop. SSH from WSL to VPS works inside this tool.

The default install of `@mako10k/mcp-shell-server` v2.7.1 has a **schema validation bug** that causes 100% of Claude Desktop's `shell_execute` calls to fail. This document captures the complete working setup including the patch.

## The Bug (Root Cause)

The server's Zod schema at `dist/types/schemas.js` line 84 has this `refine` validator:

```javascript
.refine(
  (data) => data.execution_mode !== 'adaptive' ||
            (data.foreground_timeout_seconds ?? 15) <= (data.timeout_seconds ?? 60),
  { message: 'foreground_timeout_seconds must be less than or equal to timeout_seconds in adaptive mode.' }
)
```

Defaults: `execution_mode='adaptive'`, `foreground_timeout_seconds=15`, `timeout_seconds=60`.

When Claude Desktop sends `{"command":"...","timeout_seconds":10}` (with no `execution_mode`):
1. Schema fills defaults: `execution_mode='adaptive'`, `foreground_timeout_seconds=15`
2. Validator: `15 <= 10` → **false** → request rejected
3. Claude Desktop sees: `Tool execution failed`

Every Claude tool call that sets `timeout_seconds` below 15 hits this. Below 15 is the default Claude uses for short commands.

## The Fix

Patch the schema to default `execution_mode` to `'foreground'` instead of `'adaptive'`. The validator's first clause (`data.execution_mode !== 'adaptive'`) becomes true, short-circuiting the foreground_timeout check entirely.

## Reproducible Setup

### 1. Install Node.js (in WSL Ubuntu)

```bash
# Verify Node.js 18+ is installed
node --version
```

If missing, install via the Ubuntu repository or nvm.

### 2. Install the MCP shell server globally

```bash
sudo npm install -g @mako10k/mcp-shell-server
```

This installs to `/usr/local/lib/node_modules/@mako10k/mcp-shell-server/`.

### 3. Apply the schema patch

Run the idempotent patch script:

```bash
cat > /home/ozgur/patch-mcp-shell.sh << 'PATCH'
#!/bin/bash
# Re-apply mcp-shell-server schema patch after npm updates.
# Without this patch, Claude's `shell_execute` calls fail with:
#   "foreground_timeout_seconds must be less than or equal to timeout_seconds"

set -e
SCHEMA=/usr/local/lib/node_modules/@mako10k/mcp-shell-server/dist/types/schemas.js

if [ ! -f "$SCHEMA" ]; then
  echo "ERROR: $SCHEMA not found"
  exit 1
fi

if grep -q 'ExecutionModeSchema.default("foreground")' "$SCHEMA"; then
  echo "Patch already applied"
  exit 0
fi

sudo sed -i 's|ExecutionModeSchema.default(.adaptive.)|ExecutionModeSchema.default("foreground")|' "$SCHEMA"

if grep -q 'ExecutionModeSchema.default("foreground")' "$SCHEMA"; then
  echo "Patch applied successfully"
else
  echo "ERROR: patch failed"
  exit 1
fi
PATCH

chmod +x /home/ozgur/patch-mcp-shell.sh
/home/ozgur/patch-mcp-shell.sh
```

Re-run this script after any `npm install -g @mako10k/mcp-shell-server` (updates clobber the patch).

### 4. Create the launch script

```bash
cat > /home/ozgur/start-mcp-shell.sh << 'LAUNCH'
#!/bin/bash
export MCP_SHELL_ENHANCED_MODE=false
export MCP_SHELL_ALLOWED_WORKDIRS="/home/ozgur,/opt,/tmp,/root,/data,/"
export MCP_SHELL_DEFAULT_WORKDIR=/home/ozgur

cd /home/ozgur
mkdir -p /home/ozgur/logs

exec /usr/bin/node /usr/local/lib/node_modules/@mako10k/mcp-shell-server/dist/index.js
LAUNCH

chmod +x /home/ozgur/start-mcp-shell.sh
mkdir -p /home/ozgur/logs
```

Why each env var:

| Env var | Why |
|---|---|
| `MCP_SHELL_ENHANCED_MODE=false` | Disables features that need extra dependencies |
| `MCP_SHELL_ALLOWED_WORKDIRS="..."` | Comma-separated allowlist. Without `/home/ozgur`, the server rejects calls with `Working directory not allowed` |
| `MCP_SHELL_DEFAULT_WORKDIR=/home/ozgur` | Where commands run when `working_directory` is unspecified |
| `cd /home/ozgur` before exec | The server writes `./logs/mcp_server.log` relative to cwd. Without this `cd`, cwd is `/mnt/c/Users/user` (where wsl.exe was launched from on Windows) and that path isn't writable from WSL |

### 5. Configure Claude Desktop

Edit `%APPDATA%\Claude\claude_desktop_config.json` (Windows-side):

```json
{
  "mcpServers": {
    "wsl-shell": {
      "command": "wsl.exe",
      "args": [
        "-d",
        "Ubuntu-24.04",
        "-u",
        "ozgur",
        "--",
        "/home/ozgur/start-mcp-shell.sh"
      ]
    }
  }
}
```

Replace `Ubuntu-24.04` with your WSL distro name (`wsl -l -v` to list) and `ozgur` with your WSL username.

### 6. Restart Claude Desktop

Fully quit (system tray → Quit) and relaunch. Claude Desktop spawns the MCP server fresh on startup; running servers from a previous launch will not be detected.

### 7. Verify

In a Claude Desktop conversation, ask Claude to run:

```
echo "alive: $(whoami)@$(hostname)"
```

Expected output through `wsl-shell:shell_execute`:

```json
{
  "stdout": "alive: ozgur@<your-hostname>\n",
  "exit_code": 0,
  "status": "completed"
}
```

If you see `Tool execution failed` instead, the patch didn't take effect — see Troubleshooting.

## Direct End-to-End Test (Without Claude Desktop)

This PowerShell script simulates exactly what Claude Desktop sends. Use it to verify the server independently:

```powershell
$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName = "wsl.exe"
$psi.Arguments = "-d Ubuntu-24.04 -u ozgur -- /home/ozgur/start-mcp-shell.sh"
$psi.UseShellExecute = $false
$psi.RedirectStandardInput = $true
$psi.RedirectStandardOutput = $true
$psi.RedirectStandardError = $true
$psi.WorkingDirectory = "C:\Users\$env:USERNAME"
$p = [System.Diagnostics.Process]::Start($psi)
Start-Sleep -Milliseconds 500

# Initialize
$p.StandardInput.WriteLine('{"jsonrpc":"2.0","method":"initialize","id":1,"params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"claude","version":"1"}}}')
$p.StandardInput.Flush()
Start-Sleep -Milliseconds 300
$null = $p.StandardOutput.ReadLine()

# Initialized notification
$p.StandardInput.WriteLine('{"jsonrpc":"2.0","method":"notifications/initialized","params":{}}')
$p.StandardInput.Flush()
Start-Sleep -Milliseconds 200

# Tool call — exact shape Claude sends with timeout_seconds=10
$p.StandardInput.WriteLine('{"jsonrpc":"2.0","method":"tools/call","id":3,"params":{"name":"shell_execute","arguments":{"command":"echo working","timeout_seconds":10}}}')
$p.StandardInput.Flush()
Start-Sleep -Milliseconds 5000

$response = $p.StandardOutput.ReadLine()
Write-Host "Has 'error' field: $($response -like '*\"error\"*')"
Write-Host "Has 'working' in stdout: $($response -like '*working*')"
if (!$p.HasExited) { $p.Kill() }
```

Expected: `Has 'error' field: False`, `Has 'working' in stdout: True`.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `Tool execution failed` immediately on every call | Schema patch not applied | Run `/home/ozgur/patch-mcp-shell.sh` and restart Claude Desktop |
| `Server disconnected` at Claude Desktop startup | Server crashed on launch | Run `/home/ozgur/start-mcp-shell.sh` manually in WSL — read stderr for the actual error |
| `EACCES: permission denied, open './logs/mcp_server.log'` (in stderr) | cwd not writable | Confirm `cd /home/ozgur` and `mkdir -p /home/ozgur/logs` are in the launch script |
| `Working directory not allowed: /home/ozgur` (in tool response) | `MCP_SHELL_ALLOWED_WORKDIRS` doesn't include `/home/ozgur` | Edit launch script; the value `/` alone is treated as exact match, not "allow all" |
| 4-minute timeout (`No result received from the Claude Desktop app`) | MCP server died, Claude Desktop did NOT auto-respawn it | Restart Claude Desktop |
| Tool calls timeout but server appears running (`pgrep -f mcp-shell`) | Old server process from a prior session — pipes broken | Kill old process: `pkill -f mcp-shell-server`, restart Claude Desktop |
| `require() of ES Module ... not supported` (in stderr) | Trying to wrap with CommonJS `require()` | Server is ESM-only — use direct `exec node` or dynamic `import()`, not `require()` |
| Patch reverts after `npm update` | Patch file lives in node_modules which gets regenerated | Always re-run `/home/ozgur/patch-mcp-shell.sh` after any update |

## What I Tried That Did NOT Work

These are recorded so the next person doesn't waste time:

| Attempt | Why it failed |
|---|---|
| `while true` shell loop with `grep "^\{"` | Race condition between pipe reconnects allowed partial output through |
| `mcp-wrapper.mjs` filtering on `'jsonrpc'` substring | Filtered correctly but added ~1s startup delay → Claude Desktop timeout |
| Node JSON gate intercepting `process.stdout.write` with `JSON.parse` validation | Gate worked, but the SDK's `_stdout` reference held the original write method via `bind`, not the patched one — actually was working but added unnecessary complexity |
| Setting `MCP_SHELL_ALLOWED_WORKDIRS=/` | Server treats this as exact path match, not "allow everything starting with /" |
| Setting env vars to override `foreground_timeout_seconds` defaults | The defaults are hardcoded in the Zod schema, not env-configurable |
| Writing provisioning files to Grafana data volume | Grafana reads `/etc/grafana/provisioning`, not `/var/lib/grafana/provisioning` (related lesson) |

The actual root cause was a Zod `refine()` validation, not protocol noise, not working directories, not anything we initially suspected. **Lesson: always read the server's response error message before patching the wrapper. The response was telling us the answer the entire time.**

## File Manifest

| Path | Purpose |
|---|---|
| `/home/ozgur/start-mcp-shell.sh` | Launch script — env vars, cwd, exec node |
| `/home/ozgur/patch-mcp-shell.sh` | Idempotent schema patch |
| `/home/ozgur/logs/mcp_server.log` | Server's own log file |
| `/usr/local/lib/node_modules/@mako10k/mcp-shell-server/dist/types/schemas.js` | Patched (line ~14) |
| `%APPDATA%\Claude\claude_desktop_config.json` | Claude Desktop MCP config |
| `%APPDATA%\Claude\logs\mcp.log` | Claude Desktop's MCP communication log — invaluable for debugging |

## How to Find Future Issues

The `mcp.log` file at `%APPDATA%\Claude\logs\mcp.log` shows every JSON-RPC message between Claude Desktop and the MCP server. When a tool call fails:

```powershell
Get-Content "$env:APPDATA\Claude\logs\mcp.log" | Select-String "wsl-shell" | Select-Object -Last 20
```

Look for `"error"` in the server's responses. The error message tells you exactly what the server rejected. This was how the foreground_timeout_seconds bug was finally identified — the error was visible in the log all along.
