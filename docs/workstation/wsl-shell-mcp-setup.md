# Claude Desktop wsl-shell MCP — Complete Setup

**Status:** ✅ Working (re-verified against the live box 2026-07-19; launch script + auto-heal re-grounded 2026-07-03; Node v22)
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

The live script (every knob grounded against the installed `dist/` on 2026-07-03 — the old
`MCP_SHELL_FOREGROUND_TIMEOUT` / `MCP_SHELL_TIMEOUT` / `MCP_SHELL_DEFAULT_EXECUTION_MODE` vars were
dead, never read by this version, and are removed):

```bash
cat > /home/ozgur/start-mcp-shell.sh << 'LAUNCH'
#!/bin/bash
# wsl-shell MCP server (@mako10k/mcp-shell-server) — FULL WSL access, no restriction.
export MCP_SHELL_SECURITY_MODE=permissive          # least-restrictive preset: allow all commands
export MCP_SHELL_ENHANCED_MODE=false               # no AI safety pre-check
export MCP_SHELL_ELICITATION=false                 # no interactive confirmation prompts
export MCP_SHELL_SKIP_SAFE_COMMANDS=true           # skip re-evaluating known-safe commands
export MCP_SHELL_BASIC_SAFE_CLASSIFICATION=false   # disable the command-classification gate
export MCP_SHELL_ENABLE_NETWORK=true               # allow network
export MCP_SHELL_ENABLE_STREAMING=true             # full streaming output
export MCP_SHELL_MAX_EXECUTION_TIME=2000000        # ~23 days (default 300s); safe under setTimeout overflow
export MCP_SHELL_MAX_MEMORY_MB=131072              # 128 GB (default 1024)
export MCP_SHELL_DEFAULT_WORKDIR=/home/ozgur
# Full-tree workdir access. NB: ALLOWED_WORKDIRS="/" is a FOOTGUN — the matcher does
# startsWith(dir + path.sep), so "/" becomes "//" and matches nothing under root. Instead
# enumerate every real top-level dir at launch (covers all Linux dirs + /mnt/c Windows drives).
export MCP_SHELL_ALLOWED_WORKDIRS="$(ls -d /*/ 2>/dev/null | sed 's#/$##' | paste -sd, -)"

cd /home/ozgur
mkdir -p /home/ozgur/logs

# Preflight: the node-pty native addon must load under the current Node. A Node major
# upgrade changes the ABI and breaks the compiled addon — the apt hook (§ Auto-heal below)
# heals it proactively; if anything slips through, surface a clear error in Claude
# Desktop's mcp-server-wsl-shell.log instead of a raw node-pty stack trace.
_PTY=/usr/local/lib/node_modules/@mako10k/mcp-shell-server/node_modules/node-pty/build/Release/pty.node
if ! /usr/bin/node -e "require('$_PTY')" >/dev/null 2>&1; then
  echo "start-mcp-shell: node-pty native addon failed to load (likely a Node ABI change after an upgrade)." >&2
  echo "start-mcp-shell: heal it with ->  sudo /usr/local/bin/rebuild-mcp-node-pty" >&2
fi

exec /usr/bin/node /usr/local/lib/node_modules/@mako10k/mcp-shell-server/dist/index.js
LAUNCH

chmod +x /home/ozgur/start-mcp-shell.sh
mkdir -p /home/ozgur/logs
```

Key knobs:

| Env var | Why |
|---|---|
| `MCP_SHELL_SECURITY_MODE=permissive` | Least-restrictive preset — single-operator workstation, full trust |
| `MCP_SHELL_ENHANCED_MODE=false` | Disables features that need extra dependencies |
| `MCP_SHELL_ALLOWED_WORKDIRS=$(ls -d /*/ …)` | Computed at launch: every real top-level dir. A literal `/` is a footgun — the matcher does `startsWith(dir + path.sep)`, so `/` becomes `//` and matches nothing |
| `MCP_SHELL_MAX_EXECUTION_TIME` / `MAX_MEMORY_MB` | Raised from the tiny defaults (300 s / 1 GB) so long builds don't get killed |
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

## Auto-heal — node-pty ABI breakage on Node upgrades

The server's `node-pty` native addon is compiled against one Node ABI. A Node **major** upgrade
(apt) changes `NODE_MODULE_VERSION` / the libnode soname and the addon stops loading — the MCP
server then dies at startup. Two-layer defense, installed 2026-07-03:

1. **`/usr/local/bin/rebuild-mcp-node-pty`** — idempotent healer: probes whether `pty.node` loads
   under the current Node; only when broken, runs `npm rebuild node-pty` inside the server dir
   (log: `/tmp/mcp-node-pty-rebuild.log`). Safe to run anytime.
2. **`/etc/apt/apt.conf.d/99-rebuild-mcp-node-pty`** — `DPkg::Post-Invoke` hook that runs the
   healer after every apt operation, so a Node upgrade self-heals before Claude Desktop next
   launches. The launch script's preflight (§4) is the last-resort layer: it prints the manual
   command into Claude Desktop's log if the addon is still broken.

Manual heal: `sudo /usr/local/bin/rebuild-mcp-node-pty`, then fully quit + relaunch Claude Desktop.

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
| Server dies at startup after a Node upgrade; stderr shows a node-pty load error | Node major upgrade changed the ABI — compiled `pty.node` no longer loads | `sudo /usr/local/bin/rebuild-mcp-node-pty`, restart Claude Desktop (see § Auto-heal) |

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
| `/usr/local/bin/rebuild-mcp-node-pty` | Idempotent node-pty ABI healer (§ Auto-heal) |
| `/etc/apt/apt.conf.d/99-rebuild-mcp-node-pty` | apt Post-Invoke hook — runs the healer after every apt operation |
| `/tmp/mcp-node-pty-rebuild.log` | Healer's rebuild log |
| `%APPDATA%\Claude\claude_desktop_config.json` | Claude Desktop MCP config |
| `%APPDATA%\Claude\logs\mcp.log` | Claude Desktop's MCP communication log — invaluable for debugging |

## How to Find Future Issues

The `mcp.log` file at `%APPDATA%\Claude\logs\mcp.log` shows every JSON-RPC message between Claude Desktop and the MCP server. When a tool call fails:

```powershell
Get-Content "$env:APPDATA\Claude\logs\mcp.log" | Select-String "wsl-shell" | Select-Object -Last 20
```

Look for `"error"` in the server's responses. The error message tells you exactly what the server rejected. This was how the foreground_timeout_seconds bug was finally identified — the error was visible in the log all along.
