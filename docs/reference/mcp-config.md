# MCP Server Configuration

**Last Updated:** 2026-02-19

Configuration reference for Model Context Protocol (MCP) servers used by Factory CLI.

## Purpose

MCP servers extend AI assistant capabilities by providing structured access to external resources (filesystem, databases, APIs). Factory CLI automatically discovers and connects to servers defined in `~/.factory/mcp.json`.

## Available Servers

| Server | Purpose | Security Level | Scope |
|--------|---------|----------------|-------|
| `filesystem` | Read project files and directory structure | Read-only | `/opt/fabrik`, `/opt` |
| `postgres` | Query PostgreSQL databases | Credential-protected | Connection string from env var |

## Security Model

**Principles:**
- **No hardcoded credentials** — All secrets via environment variables
- **Filesystem scoped** — Only `/opt/*` accessible; no `/home`, `/etc`, `/usr`
- **Read-only by default** — `filesystem` server has `readOnly: true`
- **Env var substitution** — Use `${VAR_NAME}` syntax in config

**Config location:** `/home/ozgur/.factory/mcp.json`

## Required Environment Variables

| Variable | Description | Where to Set |
|----------|-------------|--------------|
| `DB_CONNECTION_STRING` | PostgreSQL connection URL | `.env` file or shell profile (`~/.bashrc`) |

**Format:** `postgresql://user:password@host:port/database`

**Example:**
```bash
# In .env or ~/.bashrc
export DB_CONNECTION_STRING="postgresql://fabrik:secret@localhost:5432/fabrik_dev"
```

## Setup Instructions

### Filesystem Server

No additional setup required. Factory CLI automatically starts `@anthropic-ai/mcp-server-filesystem` via npx.

**Scoped paths:** `/opt/fabrik`, `/opt`

### Postgres Server

1. Ensure `DB_CONNECTION_STRING` is set in your environment
2. Factory CLI starts `@anthropic-ai/mcp-server-postgres` via npx
3. Server connects using the provided connection string

**Prerequisites:**
- Node.js and npm installed
- Network access to PostgreSQL instance

## Rollback

If configuration causes issues, restore the backup:

```bash
cp /home/ozgur/.factory/mcp.json.bak /home/ozgur/.factory/mcp.json
```

## Troubleshooting

| Issue | Cause | Solution |
|-------|-------|----------|
| **Invalid JSON** | Syntax error in `mcp.json` | Validate with `python -c "import json; json.load(open('/home/ozgur/.factory/mcp.json'))"` or restore backup |
| **Server not installed** | npx cannot find package | Run `npx -y @anthropic-ai/mcp-server-filesystem --version` to pre-cache |
| **Env var not set** | `DB_CONNECTION_STRING` missing | Export in `.env` or shell profile |
| **Permission denied** | Filesystem server accessing blocked path | Check `args` array only contains `/opt/*` paths |
| **Port conflict** | Another process using MCP port | Check `lsof -i :PORT` and stop conflicting process |
| **Factory CLI lacks MCP support** | CLI version does not support MCP servers | Document as blocker, set status DEFER; restore backup with `cp /home/ozgur/.factory/mcp.json.bak /home/ozgur/.factory/mcp.json` if needed |

## Configuration Reference

```json
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@anthropic-ai/mcp-server-filesystem", "/opt/fabrik", "/opt"],
      "env": {},
      "readOnly": true
    },
    "postgres": {
      "command": "npx",
      "args": ["-y", "@anthropic-ai/mcp-server-postgres"],
      "env": {
        "POSTGRES_CONNECTION_STRING": "${DB_CONNECTION_STRING}"
      }
    }
  }
}
```

## See Also

- `docs/reference/global-gates.md` — Global gate commands and exit codes
- `AGENTS.md` — Agent execution protocol
