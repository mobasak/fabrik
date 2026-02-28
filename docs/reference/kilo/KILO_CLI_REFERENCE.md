# Kilo CLI Complete Reference

**Last Updated:** 2026-02-28

This document provides comprehensive reference for Kilo Code CLI features, covering installation, configuration, interactive mode, autonomous mode, permissions, and session management.

---

## Table of Contents

1. [Installation](#installation)
2. [Getting Started](#getting-started)
3. [Interactive Mode](#interactive-mode)
4. [Autonomous Mode](#autonomous-mode)
5. [Slash Commands](#slash-commands)
6. [Configuration](#configuration)
7. [Permissions](#permissions)
8. [Session Management](#session-management)
9. [CLI Commands](#cli-commands)
10. [Environment Variables](#environment-variables)

---

## Installation

### Install via npm

```bash
npm install -g @kilocode/cli
```

### Older CPUs (No AVX Support)

If running on older CPUs without AVX support (e.g., Intel Xeon Nehalem, AMD Bulldozer), download the baseline variant from [Kilo Releases](https://github.com/Kilo-Org/kilocode/releases):

- Linux x64: `kilo-linux-x64-baseline.tar.gz`
- macOS x64: `kilo-darwin-x64-baseline.zip`
- Windows x64: `kilo-windows-x64-baseline.zip`

### Verify Installation

```bash
kilo --version
```

### First-Time Setup

Use `/connect` command to add provider credentials:

```bash
kilo
# In TUI, type: /connect
```

### Update

```bash
# Via Kilo CLI
kilo upgrade

# Via npm
npm update -g @kilocode/cli
```

---

## Getting Started

### Start Interactive TUI

```bash
cd /path/to/project
kilo
```

### Run with Message (Non-Interactive)

```bash
kilo run "Implement feature X"
```

### Attach to Running Server

```bash
kilo attach http://localhost:4096
```

### Start Headless Server

```bash
kilo serve
```

### Start Web Interface

```bash
kilo web
```

---

## Interactive Mode

Interactive mode is the default when running `kilo` without `--auto` flag.

### Command Approval

When Kilo requests command approval, hierarchical options appear:

```
[!] Action Required:
> ✓ Run Command (y)
  ✓ Always run git (1)
  ✓ Always run git status (2)
  ✓ Always run git status --short --branch (3)
  ✗ Reject (n)
```

Selecting "Always run" options:
- Approves and executes current command
- Adds pattern to `execute.allowed` list
- Auto-approves matching commands in future

### Progressive Auto-Approval

Build auto-approval rules without manually editing config by approving commands in the TUI.

---

## Autonomous Mode

Run Kilo in automated environments (CI/CD) without user interaction.

### Basic Usage

```bash
kilo run --auto "Implement feature X"
```

### Behavior

- **No user interaction** - All approvals handled automatically
- **Auto-approval/rejection** - Based on configuration
- **Follow-up questions** - Responded with autonomous decision instruction
- **Automatic exit** - Exits when task completes or times out

### Exit Codes

- `0` - Success (task completed)
- `124` - Timeout (task exceeded time limit)
- `1` - Error (initialization or execution failure)

### CI/CD Integration Example

```yaml
# GitHub Actions
- name: Run Kilo Code
  run: |
    kilo run "Implement the new feature" --auto
```

---

## Slash Commands

### Session Commands

| Command | Aliases | Description |
|---------|---------|-------------|
| `/sessions` | `/resume`, `/continue` | Switch session |
| `/new` | `/clear` | New session |
| `/share` | - | Share session |
| `/unshare` | - | Unshare session |
| `/rename` | - | Rename session |
| `/timeline` | - | Jump to message |
| `/fork` | - | Fork from message |
| `/compact` | `/summarize` | Compact/summarize session |
| `/undo` | - | Undo previous message |
| `/redo` | - | Redo message |
| `/copy` | - | Copy session transcript |
| `/export` | - | Export session transcript |
| `/timestamps` | `/toggle-timestamps` | Show/hide timestamps |
| `/thinking` | `/toggle-thinking` | Show/hide thinking blocks |

### Agent & Model Commands

| Command | Description |
|---------|-------------|
| `/models` | Switch model |
| `/agents` | Switch agent |
| `/mcps` | Toggle MCPs |

### Provider Commands

| Command | Description |
|---------|-------------|
| `/connect` | Connect/add a provider (interactive credential setup) |

### System Commands

| Command | Aliases | Description |
|---------|---------|-------------|
| `/status` | - | View status |
| `/themes` | - | Switch theme |
| `/help` | - | Show help |
| `/editor` | - | Open external editor |
| `/exit` | `/quit`, `/q` | Exit the app |

### Kilo Gateway Commands

| Command | Aliases | Description |
|---------|---------|-------------|
| `/profile` | `/me`, `/whoami` | View Kilo Gateway profile |
| `/teams` | `/team`, `/org`, `/orgs` | Switch Kilo Gateway teams |

### Built-in Commands

| Command | Description |
|---------|-------------|
| `/init` | Create/update AGENTS.md file |
| `/local-review` | Review current branch changes vs base branch |
| `/local-review-uncommitted` | Review uncommitted changes (staged + unstaged) |

---

## Configuration

Kilo CLI is a fork of OpenCode and supports the same configuration options.

### Config File Location

| Scope | Path |
|-------|------|
| Global | `~/.config/kilo/opencode.json` or `opencode.jsonc` |
| Project | `./opencode.json` or `./.opencode/` in project root |

Project-level configuration takes precedence over global settings.

### Basic Configuration

```json
{
  "$schema": "https://app.kilo.ai/config.json",
  "model": "anthropic/claude-sonnet-4-20250514",
  "provider": {
    "anthropic": {
      "options": {
        "apiKey": "{env:ANTHROPIC_API_KEY}"
      }
    }
  }
}
```

### Common Options

- `model` - Default model to use
- `provider` - Provider-specific settings (API keys, base URLs, custom models)
- `mcp` - MCP server configuration
- `permission` - Tool permission settings
- `instructions` - Paths to instruction files (e.g., `["CONTRIBUTING.md", ".cursor/rules/*.md"]`)
- `formatter` - Code formatter configuration
- `disabled_providers` / `enabled_providers` - Control available providers

### Environment Variables in Config

Use `{env:VARIABLE_NAME}` syntax:

```json
{
  "provider": {
    "openai": {
      "options": {
        "apiKey": "{env:OPENAI_API_KEY}"
      }
    }
  }
}
```

---

## Permissions

Kilo uses permission config to decide whether actions should run automatically, prompt, or be blocked.

### Actions

Each permission resolves to:

- `"allow"` - Run without approval
- `"ask"` - Prompt for approval
- `"deny"` - Block the action

### Global Permission

```json
{
  "$schema": "https://kilo.ai/config.json",
  "permission": {
    "*": "ask",
    "bash": "allow",
    "edit": "deny"
  }
}
```

Or set all at once:

```json
{
  "$schema": "https://kilo.ai/config.json",
  "permission": "allow"
}
```

### Granular Rules (Object Syntax)

```json
{
  "$schema": "https://app.kilo.ai/config.json",
  "permission": {
    "bash": {
      "*": "ask",
      "git *": "allow",
      "npm *": "allow",
      "rm *": "deny",
      "grep *": "allow"
    },
    "edit": {
      "*": "deny",
      "packages/web/src/content/docs/*.mdx": "allow"
    }
  }
}
```

Rules are evaluated by pattern match, with the last matching rule winning.

### Wildcards

- `*` - Matches zero or more of any character
- `?` - Matches exactly one character

### Home Directory Expansion

Use `~` or `$HOME` at the start of patterns:

```json
{
  "permission": {
    "external_directory": {
      "~/projects/personal/**": "allow"
    }
  }
}
```

### External Directories

Allow tool calls outside working directory:

```json
{
  "$schema": "https://kilo.ai/config.json",
  "permission": {
    "external_directory": {
      "~/projects/personal/**": "allow"
    },
    "edit": {
      "~/projects/personal/**": "deny"
    }
  }
}
```

---

## Session Management

### Session Continuation

Resume your last conversation from current workspace:

```bash
# Resume most recent session
kilo --continue
kilo -c
```

Features:
- Automatically finds most recent session from workspace
- Loads full conversation history
- Cannot be used with autonomous mode or prompt argument

Limitations:
- Cannot be combined with autonomous mode
- Cannot be used with prompt argument
- Only works when previous sessions exist

### Session Commands

```bash
# List sessions
kilo session list

# Export session
kilo export [sessionID]

# Import session
kilo import <file>
```

---

## CLI Commands

### Top-Level Commands

| Command | Description |
|---------|-------------|
| `kilo [project]` | Start the TUI |
| `kilo run [message..]` | Run with message (non-interactive) |
| `kilo attach <url>` | Attach to running server |
| `kilo serve` | Start headless server |
| `kilo web` | Start server and open web interface |
| `kilo auth` | Manage credentials (login, logout, list) |
| `kilo agent` | Manage agents (create, list) |
| `kilo mcp` | Manage MCP servers (list, add, auth) |
| `kilo models [provider]` | List available models |
| `kilo stats` | Show token usage and cost statistics |
| `kilo session` | Manage sessions (list) |
| `kilo export [sessionID]` | Export session as JSON |
| `kilo import <file>` | Import session from JSON |
| `kilo upgrade [target]` | Upgrade to latest or specific version |
| `kilo uninstall` | Uninstall and remove related files |
| `kilo pr <number>` | Fetch and checkout GitHub PR branch |
| `kilo github` | Manage GitHub agent (install, run) |
| `kilo debug` | Debugging and troubleshooting tools |
| `kilo completion` | Generate shell completion script |

### Global Options

| Flag | Description |
|------|-------------|
| `--help`, `-h` | Show help |
| `--version`, `-v` | Show version |
| `--print-logs` | Print logs to stderr |
| `--log-level` | Log level: DEBUG, INFO, WARN, ERROR |

### `kilo run` Options

| Flag | Description |
|------|-------------|
| `-c`, `--continue` | Continue last session |
| `-s`, `--session` | Session ID to continue |
| `--fork` | Fork session before continuing |
| `--share` | Share the session |
| `-m`, `--model` | Model to use (provider/model format) |
| `--agent` | Agent to use |
| `--format` | Format: default or json |
| `-f`, `--file` | File(s) to attach |
| `--title` | Session title |
| `--attach` | Attach to running server |
| `--dir` | Directory to run in |
| `--port` | Local server port |
| `--variant` | Model variant (minimal, low, high, max) |
| `--thinking` | Show thinking blocks |
| `--auto` | Auto-approve all permissions |

---

## Environment Variables

### Supported Environment Variables

- `KILO_PROVIDER` - Override active provider ID
- For kilocode provider: `KILOCODE_<FIELD_NAME>` (e.g., `KILOCODE_MODEL`)
- For other providers: `KILO_<FIELD_NAME>` (e.g., `KILO_API_KEY`)

### Usage

```bash
# Override model
export KILO_MODEL="anthropic/claude-opus-4.6"
kilo run "Fix the bug"

# Override API key
export KILO_API_KEY="sk-..."
kilo
```

---

## Local Code Reviews

Review code locally before pushing.

### Commands

```bash
# Review current branch vs base
/local-review

# Review uncommitted changes
/local-review-uncommitted
```

Features:
- AI-powered feedback on changes
- Catch issues before PR creation
- Works on uncommitted and branch changes

---

## MCP (Model Context Protocol)

Manage MCP servers for extended capabilities.

### Commands

```bash
# List MCP servers
kilo mcp list

# Add MCP server
kilo mcp add

# Authenticate MCP server
kilo mcp auth
```

### Configuration

MCP servers are configured in `opencode.json`:

```json
{
  "mcp": {
    "servers": {
      "filesystem": {
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-filesystem", "/path/to/allowed"]
      }
    }
  }
}
```

---

## Switching Organizations

Use `/teams` command to switch between organizations:

```bash
# In TUI
/teams
```

The process is the same for Team or Enterprise organizations.

---

## See Also

- **[KILO_AGENT_NAMING.md](KILO_AGENT_NAMING.md)** - Tier-based agent naming convention
- **[KILO_AGENT_SELECTION_GUIDE.md](KILO_AGENT_SELECTION_GUIDE.md)** - Model selection guide
- **[README.md](README.md)** - Kilo system overview
- **[OpenCode Config Documentation](https://github.com/Kilo-Org/kilocode)** - Comprehensive config reference
