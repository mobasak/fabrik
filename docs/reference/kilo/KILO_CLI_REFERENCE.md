# Kilo CLI Complete Reference

**Last Updated:** 2026-05-20

This document provides comprehensive reference for Kilo Code CLI features, covering installation, configuration, interactive mode, autonomous mode, HTTP server API, custom agents, plugins, permissions, and session management.

> **Kilo CLI version:** 7.3.1 (built on OpenCode, MIT-licensed). Installed at `/usr/local/bin/kilo` on WSL.
> **500+ models** via Kilo Gateway. Pay-as-you-go (zero markup) or BYOK.

---

## Table of Contents

1. [Installation](#installation)
2. [Getting Started](#getting-started)
3. [Interactive Mode](#interactive-mode)
4. [Autonomous Mode](#autonomous-mode)
5. [Slash Commands](#slash-commands)
6. [Configuration](#configuration)
7. [Custom Agents](#custom-agents)
8. [Custom Commands](#custom-commands)
9. [Plugins](#plugins)
10. [HTTP Server API](#http-server-api)
11. [Permissions](#permissions)
12. [Session Management](#session-management)
13. [CLI Commands](#cli-commands)
14. [Environment Variables](#environment-variables)

---

## Kilo as AI Infrastructure

Kilo CLI is not a coding tool — it's a **programmable AI platform** with 500+ models, tool execution, session memory, and a full HTTP API. The built-in coding agents are one use case. The platform supports any task an LLM can do.

**See:** [KILO_USE_CASES.md](KILO_USE_CASES.md) — comprehensive use case analysis across 11 domains (content generation, translation, data extraction, research, vision/OCR, audio pipelines, business automation, marketing, legal, multi-modal pipelines) with economics, architecture patterns, and ROI rankings.

**Verified on 2026-05-20:** `kilo serve` → OpenAPI 3.1 REST API (`/global/health` healthy, `/session` 100+ sessions, `/agent` 10 agents). `kilo run --auto` → autonomous agent with exit codes. Custom agents, MCP integration, 500+ models, SSE streaming, remote control all confirmed working.

---

## April 2026 Changes (v7.2+)

Major features added since v7.0:

| Feature | Description |
|---------|-------------|
| **Snapshots** | Git-based working directory snapshots before/after agent edits. Revert any message's changes from the chat. Replaces old checkpoint system. |
| **Agent Manager** | Run multiple agents simultaneously within the interface (VS Code / Cloud). |
| **Subagents** | Agents with full tool access can now delegate to subagents automatically. Replaces Orchestrator mode for most use cases. |
| **Granular Permissions** | Per-tool Allow/Ask/Deny system replaces old auto-confirm UI. Supports bash, read, edit, glob, grep individually. |
| **Context Progress Graph** | Visual timeline at top of chat showing session activity and token usage. |
| **Diff Viewer** | Click diff badges in chat to review file changes. |
| **Local Code Reviews** | `/local-review` and `/local-review-uncommitted` for AI-powered branch/uncommitted analysis. |
| **Model Cost Display** | Pricing info (input/output per million tokens) visible in model picker. |
| **Model Favoriting** | Star preferred models in the selector. |
| **`kilo roll-call`** | Batch connectivity and latency testing for models. |
| **`kilo github`** | Install and run GitHub agent for PR workflows. |
| **`kilo db`** | Database management tools. |

**Deprecated in v7.2+:**

| Deprecated | Replacement |
|---|---|
| Orchestrator Mode | Automatic subagent delegation (agents delegate on their own) |
| Profiles | Model favoriting (starring) |
| Code Indexing | Temporarily unavailable, under active development |
| Checkpoints | Renamed to Snapshots (git-based) |
| Auto-confirm UI | Granular per-tool permission system |

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

## Modes

**Modes** in Kilo Code are specialized personas that tailor the assistant's behavior to your current task. Each mode offers different capabilities, expertise, and access levels.

### Why Use Different Modes?

**Benefits:**
- **Task specialization** - Get precisely the type of assistance you need
- **Safety controls** - Prevent unintended file modifications when planning or learning
- **Focused interactions** - Responses optimized for your current activity
- **Workflow optimization** - Seamlessly transition between planning, implementing, debugging, and learning

### Switching Between Modes

**Four ways to switch:**

1. **Dropdown menu** - Click the selector to the left of the chat input
2. **Slash commands** - Type mode name in chat:
   - `/code` - Switch to Code mode
   - `/ask` - Switch to Ask mode
   - `/architect` - Switch to Architect mode
   - `/debug` - Switch to Debug mode
   - `/orchestrator` - Switch to Orchestrator mode **(deprecated — use subagents)**
   - `/review` - Switch to Review mode
3. **Keyboard shortcut** - Toggle through modes:
   - **macOS:** `⌘ + .`
   - **Windows/Linux:** `Ctrl + .`
4. **Accept suggestions** - Click on mode switch suggestions that Kilo Code offers

### Understanding /newtask vs /smol

| Command | Purpose | When to Use |
|---------|---------|-------------|
| `/newtask` | Creates new task with context from current task | Start something new while carrying over context |
| `/smol` | Condenses your current context window | Conversation getting too long, need to summarize |

---

### Built-in Modes

#### Code Mode (Default)

| Aspect | Details |
|--------|---------|
| **Description** | Skilled software engineer with expertise in programming languages, design patterns, best practices |
| **Tool Access** | **Full access:** read, edit, browser, command, mcp |
| **Ideal For** | Writing code, implementing features, debugging, general development |
| **Special Features** | No tool restrictions—full flexibility for all coding tasks |

**When to use:**
- Writing new code or features
- Implementing changes to existing code
- General development tasks
- Running commands and tests

---

#### Ask Mode

| Aspect | Details |
|--------|---------|
| **Description** | Knowledgeable technical assistant focused on answering questions without changing your codebase |
| **Tool Access** | **Limited:** read, browser, mcp only (cannot edit files or run commands) |
| **Ideal For** | Code explanation, concept exploration, technical learning |
| **Special Features** | Optimized for informative responses without modifying your project |

**When to use:**
- Understanding existing code
- Learning new concepts
- Exploring architecture without changes
- Technical questions and explanations

**Safety:** Cannot accidentally modify files or run commands.

---

#### Architect Mode

| Aspect | Details |
|--------|---------|
| **Description** | Experienced technical leader and planner who helps design systems and create implementation plans |
| **Tool Access** | **Restricted:** read, browser, mcp, edit (markdown files only) |
| **Ideal For** | System design, high-level planning, architecture discussions |
| **Special Features** | Follows structured approach from information gathering to detailed planning |

**When to use:**
- Designing new systems or features
- Creating implementation plans
- Architecture discussions
- High-level planning documents

**Safety:** Can only edit markdown files (e.g., design docs, plans).

---

#### Debug Mode

| Aspect | Details |
|--------|---------|
| **Description** | Expert problem solver specializing in systematic troubleshooting and diagnostics |
| **Tool Access** | **Full access:** read, edit, browser, command, mcp |
| **Ideal For** | Tracking down bugs, diagnosing errors, resolving complex issues |
| **Special Features** | Uses methodical approach of analyzing, narrowing possibilities, and fixing issues |

**When to use:**
- Tracking down bugs
- Diagnosing errors
- Performance issues
- System troubleshooting

**💡 Tip:** Keep debugging separate from main tasks:
```
"Start a new task in Debug mode with all necessary context to figure out X"
```
This uses a separate context window and doesn't pollute the main task.

---

#### Orchestrator Mode (DEPRECATED — v7.2+)

> **Deprecated:** Orchestrator mode is replaced by automatic subagent delegation in v7.2+. Agents with full tool access now delegate to subagents on their own without a dedicated orchestrator. The section below is retained for reference only.

**Formerly known as:** Boomerang Tasks

| Aspect | Details |
|--------|---------|
| **Description** | Strategic workflow orchestrator who coordinates complex tasks by delegating to specialized modes |
| **Tool Access** | **Limited:** create new tasks (`new_task` tool), coordinate workflows, receive completion summaries |
| **Ideal For** | Breaking down complex projects into manageable subtasks assigned to specialized modes |
| **Special Features** | Uses `new_task` tool to delegate work, `attempt_completion` tool for subtask results |

### Why Use Orchestrator Mode?

**Tackle Complexity**
- Break large, multi-step projects (e.g., building a full feature) into focused subtasks
- Each subtask handles a specific piece (e.g., design, implementation, documentation)

**Use Specialized Modes**
- Automatically delegate subtasks to the mode best suited for that work
- Leverage specialized capabilities for optimal results
- Example: Architect mode for design → Code mode for implementation → Review mode for quality checks

**Maintain Focus & Efficiency**
- Each subtask operates in its own **isolated context** with separate conversation history
- Parent (orchestrator) task stays clutter-free (no code diffs, file analysis details)
- Parent focuses on high-level workflow management
- Only concise summaries from completed subtasks return to parent

**Streamline Workflows**
- Results from one subtask automatically pass to the next
- Create smooth flow: architectural decisions → coding task → testing task
- Maintain continuity across specialized work

### How It Works

**Step-by-step workflow:**

1. **Analysis** - Orchestrator mode analyzes complex task and suggests breaking it down
2. **Subtask Creation** - Parent task pauses, new subtask begins in different mode
3. **Execution** - Subtask runs in isolation with its own context
4. **Completion** - When goal achieved, Kilo signals completion via `attempt_completion` tool
5. **Resume** - Parent task resumes with only the summary from subtask
6. **Continue** - Parent uses summary to continue main workflow

**Tools involved:**

```
new_task tool:
  - message: Context passed DOWN to subtask (initial instructions)
  - mode: Which mode to use for subtask (code, architect, debug, etc.)

attempt_completion tool:
  - result: Summary passed UP to parent when subtask finishes
```

### Key Considerations

#### Approval Required

**Default behavior:**
- You must approve creation of each subtask
- You must approve completion of each subtask

**Auto-approval option:**
- Can be automated via "Auto-Approving Actions" settings
- Use with caution - ensures you maintain control

#### Context Isolation and Transfer

**Complete isolation:**
- Each subtask operates with its own conversation history
- Subtask does NOT automatically inherit parent's context
- Information must be explicitly passed

**Context transfer mechanisms:**

| Direction | Mechanism | Tool Parameter | Content |
|-----------|-----------|----------------|---------|
| **DOWN** (Parent → Subtask) | Initial instructions | `new_task.message` | What subtask needs to know |
| **UP** (Subtask → Parent) | Final summary | `attempt_completion.result` | What parent needs to know |

**⚠️ Important:** Only the summary returns to parent. Detailed execution steps, code diffs, and file analysis stay in subtask context.

#### Navigation

**Task hierarchy:**
- Kilo's interface shows parent-child relationships
- Navigate between active and paused tasks
- See which task is parent, which are children
- Resume paused parent tasks after subtask completion

### Example Workflow

**Scenario:** Build a new authentication feature

```
1. Orchestrator Mode (Parent)
   ├─ Analyzes: "Build authentication feature"
   ├─ Suggests subtasks:
   │
   ├─ Subtask 1: Architect Mode
   │  ├─ Context DOWN: "Design auth system with JWT, user roles, session management"
   │  ├─ Execution: Creates architecture document, API design
   │  └─ Summary UP: "Designed JWT-based auth with 3 roles, session timeout 30min"
   │
   ├─ Subtask 2: Code Mode
   │  ├─ Context DOWN: "Implement auth based on architecture: [summary from Subtask 1]"
   │  ├─ Execution: Writes auth middleware, user routes, token validation
   │  └─ Summary UP: "Implemented JWT auth, 5 endpoints, middleware, tests passing"
   │
   └─ Subtask 3: Review Mode
      ├─ Context DOWN: "Review auth implementation for security issues"
      ├─ Execution: Analyzes code for vulnerabilities, checks best practices
      └─ Summary UP: "Found 2 minor issues (fixed), security best practices applied"
```

### Best Practices

**💡 Keep Tasks Focused**
- Use subtasks to maintain clarity
- If request significantly shifts focus or requires different expertise (mode), create a subtask
- Don't overload the current task

**When to create subtasks:**
- Task requires multiple modes (design + code + review)
- Task has distinct phases (planning → implementation → testing)
- Context is becoming cluttered with implementation details
- Different expertise levels needed for different parts

**When NOT to create subtasks:**
- Simple, single-mode tasks
- Quick changes or bug fixes
- Tasks where context continuity is critical
- When overhead of subtask management exceeds benefits

### Cost Optimization with Orchestrator Mode

**Token efficiency:**
- Parent context stays small (only summaries)
- Detailed work happens in isolated subtask contexts
- Reduces token waste from carrying forward large contexts

**Model selection:**
- Use **budget models** for orchestrator coordination ($0.20-0.50/M)
- Use **specialized models** for subtasks based on mode
- Example: Free model for orchestration, premium for complex code subtasks

---

#### Review Mode

| Aspect | Details |
|--------|---------|
| **Description** | Expert code reviewer specializing in analyzing changes to provide structured feedback on quality, security, best practices |
| **Tool Access** | **Restricted:** read, browser, mcp, edit (when permitted) |
| **Ideal For** | Catching issues early, enforcing code standards, accelerating PR turnaround |
| **Special Features** | Code review before committing, surfacing feedback across performance, security, style, test coverage |

**When to use:**
- Pre-commit code review
- Security analysis
- Code quality checks
- Best practices enforcement
- PR review acceleration

**Review categories:**
- Performance optimization
- Security vulnerabilities
- Code style and standards
- Test coverage
- Best practices compliance

---

#### Custom Modes

Create your own specialized assistants by defining:
- Tool access permissions
- File permissions
- Behavior instructions

**Use cases:**
- Team-specific standards enforcement
- Domain-specific assistants
- Custom workflow optimization
- Project-specific constraints

**See:** Custom Modes documentation for setup instructions.

---

### Mode Selection Best Practices

**Start with restricted modes, escalate when needed:**

```
Planning → Architect mode (safe, markdown-only edits)
Learning → Ask mode (read-only, no accidental changes)
Debugging → Debug mode (full access, focused troubleshooting)
Implementation → Code mode (full access, general development)
Quality → Review mode (feedback-focused, limited edits)
```

**Cost optimization by mode:**

| Mode | Typical Cost | Optimization Strategy |
|------|--------------|----------------------|
| Ask | Low | Use free/budget models (no file operations) |
| Architect | Low-Medium | Budget models for planning, premium for complex design |
| Code | High | Start budget, escalate to premium for complex tasks |
| Debug | High | Premium models for complex issues, budget for simple bugs |
| Review | Medium-High | Premium for critical code review, budget for standards checks |

---

## Configuration

Kilo CLI is built on OpenCode (MIT-licensed) and supports the same configuration options.

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
- `lsp` - Language server configuration
- `disabled_providers` / `enabled_providers` - Control available providers
- `experimental` - Experimental features (e.g., `openTelemetry`)

For comprehensive configuration documentation including compaction, file watchers, plugins, and experimental features, see the [OpenCode Config documentation](https://opencode.ai/docs/config).

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

### Global Instructions Configuration

The global configuration at `~/.config/kilo/opencode.json` controls which instruction files are passed to all Kilo CLI agents system-wide:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "instructions": [
    "AGENTS-compact.md"
  ]
}
```

**Important Notes:**
- **Global scope**: This configuration affects all Kilo CLI agents run from any directory
- **Project override**: Project-level `opencode.json` takes precedence over global settings
- **Fabrik convention**: Only `AGENTS-compact.md` should be used for Kilo CLI agents
- **AGENTS.md restriction**: The full `AGENTS.md` is intended for Traycer only and should NOT be in global config

**Why only AGENTS-compact.md?**
- Kilo CLI agents need concise, actionable instructions
- `AGENTS-compact.md` contains the essential rules and directives
- `AGENTS.md` includes planning context and workflow details meant for Traycer
- Prevents confusion and reduces token usage for CLI agents

**Configuration Precedence:**
1. Project-level `./opencode.json` (highest priority)
2. Global `~/.config/kilo/opencode.json`
3. Default Kilo CLI behavior (lowest)

### Setting Up Free Providers

#### OpenRouter (Free Tier Models)

OpenRouter offers several free models including Qwen3 Coder, DeepSeek R1, and GLM 4.5 Air.

**Setup:**
1. Visit [openrouter.ai](https://openrouter.ai)
2. Create free account
3. Get API key from dashboard
4. Configure in `opencode.json`:

```json
{
  "provider": {
    "openrouter": {
      "options": {
        "apiKey": "{env:OPENROUTER_API_KEY}"
      }
    }
  }
}
```

5. Set environment variable:
```bash
export OPENROUTER_API_KEY="your-key-here"
```

#### Groq (Free Fast Inference)

Groq provides free fast inference for supported models.

**Setup:**
1. Visit [groq.com](https://groq.com)
2. Create account
3. Get API key
4. Configure in `opencode.json`:

```json
{
  "provider": {
    "groq": {
      "options": {
        "apiKey": "{env:GROQ_API_KEY}"
      }
    }
  }
}
```

5. Set environment variable:
```bash
export GROQ_API_KEY="your-key-here"
```

#### Kilo Gateway (Free Models)

Kilo Gateway provides free models directly without additional setup:
- MiniMax M2.1
- Z.AI GLM 4.7
- MoonshotAI Kimi K2.5
- Giga Potato
- Arcee AI Trinity Large Preview

**No configuration needed** - available immediately through Kilo Code.

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
| `kilo serve` | Start headless HTTP server (OpenAPI 3.1) |
| `kilo web` | Start server and open web interface |
| `kilo acp` | Start ACP (Agent Client Protocol) server |
| `kilo auth` | Manage credentials (login, logout, list) |
| `kilo agent` | Manage agents (create, list) |
| `kilo config` | View/edit configuration |
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
| `kilo remote` | Manage remote connections |
| `kilo plugin <module>` | Load a plugin module |
| `kilo db` | Database tools |
| `kilo debug` | Debugging and troubleshooting tools |
| `kilo roll-call <filter>` | Batch test model connectivity and latency |
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
| `-m`, `--model` | Model to use (`kilo/provider/model` format) |
| `--agent` | Agent to use (built-in or custom) |
| `--format` | Format: `default` (formatted) or `json` (raw JSON events) |
| `-f`, `--file` | File(s) to attach to message |
| `--title` | Session title |
| `--attach` | Attach to running server (e.g., `http://localhost:4096`) |
| `--dir` | Directory to run in (path on remote server if attaching) |
| `--port` | Local server port (random if not set) |
| `--variant` | Model variant / reasoning effort (e.g., `minimal`, `low`, `high`, `max`) |
| `--thinking` | Show thinking blocks |
| `--auto` | Auto-approve all permissions (for autonomous/pipeline usage) |
| `--command` | The command to run (use message for args) |
| `--prompt` | Prompt to use |

---

## Environment Variables

### Supported Environment Variables

- `KILO_PROVIDER` - Override active provider ID
- For kilocode provider: `KILOCODE_<FIELD_NAME>` (e.g., `KILOCODE_MODEL`)
- For other providers: `KILO_<FIELD_NAME>` (e.g., `KILO_API_KEY`)
- `KILO_ORG_ID` - Organization ID for non-interactive and CI environments (best for automated usage)
- `OPENCODE_SERVER_PASSWORD` - Enable HTTP basic auth on `kilo serve` / `kilo web`
- `OPENCODE_SERVER_USERNAME` - Override basic auth username (default: `opencode`)
- `OPENCODE_TUI_CONFIG` - Custom path to TUI config file

### Usage

```bash
# Override model
export KILO_MODEL="anthropic/claude-opus-4.6"
kilo run "Fix the bug"

# Override API key
export KILO_API_KEY="sk-..."
kilo

# Set organization for non-interactive usage
export KILO_ORG_ID="org_12345"
kilo run "Implement feature" --auto
```

---

## Remote Connections

Remote mode allows Cloud Agents to connect to your local CLI session for remote control.

### Enabling Remote Mode

**Toggle during a session:**
```bash
/remote
```

Requires connection to Kilo Gateway. The `/remote` command appears only when authenticated.

**Enable by default:**
Add to `~/.config/kilo/config.json`:
```json
{
  "remote_control": true
}
```

### Using Remote Mode

Once enabled, start a CLI session and open Cloud Agents. Your local session appears in the dashboard. See [Cloud Agent Remote Connections](https://kilo.ai/docs/code-with-ai/platforms/cloud-agent) for details.

### Requirements

- Connection to Kilo Gateway
- Same Kilo account on CLI and Cloud Agent
- CLI must remain running with internet connection

**Security Note:** Anyone with access to your Kilo account can send messages to your computer when remote mode is enabled.

---

## Windows-Specific Configuration

### TUI Keybindings on Windows

The TUI gives Ctrl+Z to input undo on Windows because native Windows terminals do not support POSIX terminal suspend. On Windows, `input_undo` defaults to `ctrl+z,ctrl+-,super+z` and `terminal_suspend` is disabled. On macOS and Linux, `terminal_suspend` defaults to `ctrl+z`.

### Enabling Shift+Enter in Windows Terminal

Some terminals don't send modifier keys with Enter by default. Windows Terminal requires a one-time configuration to forward Shift+Enter as an escape sequence that Kilo can read.

Open your settings.json at:
```
%LOCALAPPDATA%\Packages\Microsoft.WindowsTerminal_8wekyb3d8bbwe\LocalState\settings.json
```

Add this entry to the root-level `actions` array:
```json
"actions": [
  {
    "command": {
      "action": "sendInput",
      "input": "\u001b[13;2u"
    },
    "id": "User.sendInput.ShiftEnterCustom"
  }
]
```

Add this entry to the root-level `keybindings` array:
```json
"keybindings": [
  {
    "keys": "shift+enter",
    "id": "User.sendInput.ShiftEnterCustom"
  }
]
```

Save the file and restart Windows Terminal or open a new tab. Shift+Enter will now insert a newline in the Kilo prompt instead of submitting the message.

---

## OpenTelemetry Export

Kilo telemetry is enabled by default and exports traces to OpenTelemetry-compatible backends for observability and monitoring.

### Disable Telemetry

To disable OpenTelemetry export, add to `opencode.json`:
```json
{
  "experimental": {
    "openTelemetry": false
  }
}
```

### Export to OTLP Endpoint

If `OTEL_EXPORTER_OTLP_ENDPOINT` is set, the CLI exports OpenTelemetry traces and logs to that OTLP HTTP endpoint. Request spans include:
- `http.method` - HTTP method
- `http.path` - Request path
- Route params such as `session.id` and `message.id`
- Internal params under the `opencode.*` namespace

### Environment Variables

- `OTEL_EXPORTER_OTLP_ENDPOINT` - OTLP HTTP endpoint URL
- `OTEL_EXPORTER_OTLP_HEADERS` - Comma-separated key=value pairs for headers
- `OTEL_RESOURCE_ATTRIBUTES` - Comma-separated resource attributes

### Usage

```bash
# Export to OTLP endpoint
export OTEL_EXPORTER_OTLP_ENDPOINT="http://localhost:4318/v1/traces"
export OTEL_EXPORTER_OTLP_HEADERS="Authorization=Bearer token,X-Custom-Header=value"
kilo run "Debug the issue"

# Disable telemetry via config
# Add to opencode.json: {"experimental": {"openTelemetry": false}}
```

---

## Built-in Agents

| Agent | Type | Description | Key Permissions |
|-------|------|-------------|-----------------|
| **code** | primary | Full coding agent — default for implementation | read, write, edit, bash, all tools |
| **ask** | primary | Read-only Q&A, analysis, explanations | read, grep, glob, list, codesearch |
| **debug** | primary | Debugging and troubleshooting | read, grep, bash, diagnostics |
| **plan** | primary | Planning and task breakdown | read, question, plan_exit |
| **summary** | primary | Summarization tasks | read only |
| **title** | primary | Generate titles for sessions | read only |
| **compaction** | primary | Context compaction | limited |
| **general** | subagent | General-purpose subagent (auto-delegated) | all except question, plan |

### Agent Permissions Reference

```
read               - Read files
edit               - Modify files
bash               - Execute shell commands
grep               - Search file contents
glob               - Find files by pattern
list               - List directory contents
codesearch         - Semantic code search
websearch          - Web search
webfetch           - Fetch URL content
task               - Create subtasks
question           - Ask user questions
todoread           - Read todo list
todowrite          - Modify todo list
external_directory - Access directories outside project
```

### Agent Selection by Use Case

| Use Case | Recommended Agent | Why |
|----------|-------------------|-----|
| Code implementation | `code` | Full edit + bash permissions |
| Code review | `ask` or `code` | `ask` for read-only analysis, `code` if suggesting edits |
| Bug fixing | `code` or `debug` | Need file edit + diagnostics |
| Refactoring | `code` | Full edit capabilities |
| Documentation | `ask` | Analysis and generation without file edits |
| Planning | `plan` | Specialized for task breakdown |
| Complex multi-step | automatic subagent | Agents delegate to `general` subagent as needed |

---

## Variants (Reasoning Effort)

Variants control how much "thinking" the model does before responding.

| Variant | Reasoning Effort | Use Case | Token Impact |
|---------|------------------|----------|--------------|
| **minimal** | Lowest | Quick, simple tasks | Lowest cost |
| **low** | Below average | Routine operations | Low cost |
| **high** | Above average | Complex analysis, quality matters | Higher cost |
| **max** | Maximum | Most difficult problems | Highest cost |

### Provider-Specific Behavior

**OpenAI (o1, o3, o4 series):** Supports additional `medium` variant mapping to `reasoningEffort: medium`.

**Google/Anthropic:** Variants affect internal prompt construction and sampling parameters. Higher variants may trigger chain-of-thought reasoning.

### Using Variants

```bash
kilo run --variant high "Complex analysis task"
kilo run -m kilo/anthropic/claude-sonnet-4-5 --variant max "Refactor this module"
```

---

## Model Discovery & Debugging

```bash
# List all models
kilo models

# List models for specific provider (with costs)
kilo models --verbose openai

# Refresh model cache
kilo models --refresh

# Test model connectivity and latency
kilo roll-call openai

# Debug: show configuration
kilo debug config

# Debug: show agent details
kilo debug agent ask

# Debug: show paths
kilo debug paths

# Debug: list available skills
kilo debug skill
```

---

## Custom Agents

Define specialized agents with specific models, system prompts, and tool restrictions.

### Via Configuration

```json
{
  "$schema": "https://kilo.ai/config.json",
  "agent": {
    "aro-reasoner": {
      "description": "Alert reasoning agent for ARO Brain",
      "model": "anthropic/claude-haiku-4.5",
      "prompt": "You are an infrastructure alert analyst. Given Prometheus metrics and Loki logs, determine severity and suggest remediation. Respond with structured JSON.",
      "tools": {
        "write": false,
        "edit": false,
        "bash": false
      }
    },
    "code-reviewer": {
      "description": "Reviews code for best practices and potential issues",
      "model": "anthropic/claude-sonnet-4.5",
      "prompt": "You are a code reviewer. Focus on security, performance, and maintainability.",
      "tools": {
        "write": false,
        "edit": false
      }
    }
  }
}
```

### Via Markdown Files

Place agent definitions in `~/.config/opencode/agents/` (global) or `.opencode/agents/` (project-level):

```markdown
---
name: aro-reasoner
description: Alert reasoning agent
model: anthropic/claude-haiku-4.5
---

You are an infrastructure alert analyst...
```

### Using Custom Agents

```bash
# CLI
kilo run --agent aro-reasoner "Analyze this alert context"

# HTTP API
POST /session/:id/message
{"agent": "aro-reasoner", "parts": [{"type": "text", "text": "..."}]}
```

### Default Agent

```json
{
  "default_agent": "plan"
}
```

The default agent must be a primary agent (not a subagent). Built-in options: `"build"`, `"plan"`.

---

## Custom Commands

Reusable prompt templates for repetitive tasks.

### Via Configuration

```json
{
  "$schema": "https://kilo.ai/config.json",
  "command": {
    "test": {
      "template": "Run the full test suite with coverage report and show any failures.\nFocus on the failing tests and suggest fixes.",
      "description": "Run tests with coverage",
      "agent": "build",
      "model": "anthropic/claude-haiku-4.5"
    },
    "component": {
      "template": "Create a new React component named $ARGUMENTS with TypeScript support.\nInclude proper typing and basic structure.",
      "description": "Create a new component"
    }
  }
}
```

### Via Markdown Files

Place command definitions in `~/.config/opencode/commands/` or `.opencode/commands/`.

### Usage

```bash
# In TUI
/test
/component MyButton

# Via CLI
kilo run --command test
```

---

## Plugins

Extend Kilo with custom tools, hooks, and integrations.

### Plugin Locations

- **Project-level:** `.opencode/plugins/`
- **Global:** `~/.config/opencode/plugins/`
- **npm packages:** via `plugin` config option

### Configuration

```json
{
  "$schema": "https://kilo.ai/config.json",
  "plugin": ["opencode-helicone-session", "@my-org/custom-plugin"]
}
```

---

## HTTP Server API

Kilo exposes a full **OpenAPI 3.1** REST API when running as a server. This is the same API that the TUI, desktop app, and IDE extensions use internally.

### Starting the Server

```bash
# Headless server (default port: random, or specify)
kilo serve --port 4096 --hostname 127.0.0.1

# With authentication
OPENCODE_SERVER_PASSWORD=your-password kilo serve

# Web interface (opens browser)
kilo web
```

### OpenAPI Spec

Browse the spec at `http://localhost:4096/doc` after starting the server.

### Key Endpoints

#### Global

| Method | Path | Description |
|--------|------|-------------|
| GET | `/global/health` | Server health check |
| GET | `/global/event` | SSE stream for system-wide events |
| GET | `/global/config` | Get configuration |
| PUT | `/global/config` | Update configuration |
| POST | `/global/dispose` | Shutdown server |

#### Sessions

| Method | Path | Description |
|--------|------|-------------|
| GET | `/session` | List all sessions |
| POST | `/session` | Create new session |
| GET | `/session/:id` | Get session details |
| DELETE | `/session/:id` | Delete session |
| PATCH | `/session/:id` | Update session (e.g., title) |
| POST | `/session/:id/abort` | Abort in-progress generation |
| POST | `/session/:id/fork` | Fork session from a message |
| POST | `/session/:id/summarize` | Summarize session |
| GET | `/session/:id/diff` | Get file diffs for session |
| GET | `/session/:id/event` | SSE stream for session events |
| GET | `/session/:id/todo` | Get session todo list |
| POST | `/session/:id/revert` | Revert a message/part |

#### Messages (Core Chat)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/session/:id/message` | List messages |
| POST | `/session/:id/message` | Send message (with model/agent/tools control) |
| GET | `/session/:id/message/:msgID` | Get specific message |
| POST | `/session/:id/prompt_async` | Send message async (returns 204) |
| POST | `/session/:id/command` | Run a custom command |
| POST | `/session/:id/shell` | Run a shell command |

**Message body** (`POST /session/:id/message`):

```json
{
  "model": "anthropic/claude-haiku-4.5",
  "agent": "aro-reasoner",
  "system": "Optional system prompt override",
  "tools": {"bash": false, "edit": false},
  "noReply": false,
  "parts": [
    {"type": "text", "text": "Analyze this alert..."}
  ]
}
```

#### Files & Search

| Method | Path | Description |
|--------|------|-------------|
| GET | `/find?pattern=<pat>` | Ripgrep search |
| GET | `/find/file?query=<q>` | Fuzzy file search |
| GET | `/find/symbol?query=<q>` | Symbol search |
| GET | `/file?path=<path>` | List directory tree |
| GET | `/file/content?path=<p>` | Read file content |
| GET | `/file/status` | Git status of files |

#### Agents, Tools & MCP

| Method | Path | Description |
|--------|------|-------------|
| GET | `/agent` | List available agents |
| GET | `/experimental/tool/ids` | List tool IDs |
| GET | `/experimental/tool` | List tools (with provider/model) |
| GET | `/mcp` | MCP server status |
| POST | `/mcp` | Add MCP server |
| GET | `/lsp` | LSP server status |
| GET | `/formatter` | Formatter status |

#### Auth & Events

| Method | Path | Description |
|--------|------|-------------|
| PUT | `/auth/:id` | Set provider credentials |
| GET | `/event` | SSE stream (`server.connected`) |

### SSE Event Streaming

Real-time events via Server-Sent Events:

- **`GET /global/event`** — system-wide events (e.g., `installation.updated`)
- **`GET /session/:id/event`** — per-session events (e.g., `message.updated`, token streaming)

### JSON Output Format (`kilo run --format json`)

When using `--format json`, each line is a JSON event:

```json
{"type":"step_start","timestamp":1776189961522,"sessionID":"ses_...","part":{...}}
{"type":"text","timestamp":1776189961614,"sessionID":"ses_...","part":{"type":"text","text":"4",...}}
{"type":"step_finish","timestamp":1776189961620,"sessionID":"ses_...","part":{"type":"step-finish","reason":"stop","cost":0.0016839,"tokens":{"total":12726,"input":337,"output":5,"reasoning":0,"cache":{"read":12384,"write":0}}}}
```

Each `step_finish` event includes cost and token breakdown.

### Programmatic Access from Python

The HTTP API can be called from any language. Example with Python `httpx`:

```python
import httpx

BASE = "http://localhost:4096"

# Create session
session = httpx.post(f"{BASE}/session").json()
sid = session["id"]

# Send message with model/agent control
resp = httpx.post(f"{BASE}/session/{sid}/message", json={
    "model": "anthropic/claude-haiku-4.5",
    "agent": "aro-reasoner",
    "parts": [{"type": "text", "text": "Analyze: container memory at 92%"}]
})
result = resp.json()
```

### Connecting to a Running Server

```bash
# From another terminal or machine
kilo attach http://localhost:4096

# Or use kilo run with --attach
kilo run --attach http://localhost:4096 "Fix the bug"
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

## Programmatic Integration (Python)

Fabrik calls Kilo from Python in `scripts/kilo_code_review.py` (5600+ lines). Key patterns — use these, don't reinvent:

### Calling Kilo from Python

```python
# Basic call (from kilo_code_review.py::run_kilo)
result = await run_kilo(
    prompt="Review this code for security issues",
    config=KiloReviewConfig(
        model="kilo/google/gemini-3-flash-preview",
        variant="high",
        session_id=None,  # new session
    ),
    agent="ask",
    file_paths=[Path("src/auth.py")],
    timeout=300,
)

# Result structure
{
    "result": "The review text...",
    "session_id": "ses_2fa04657affervfKa7bqDLCufy",
    "input_tokens": 7409,
    "output_tokens": 1393,
    "cost": 0.0157,
}
```

### Liveness-Based Process Monitoring (not blind timeouts)

**Never use `subprocess.run(timeout=N)`.** Kilo sessions can be long but active. The liveness monitor kills only if truly hung:

```python
# _monitor_process() pattern:
# - Reader threads on stdout + stderr (non-blocking)
# - Tracks "last_output_time" — ANY output resets the idle clock
# - Idle timeout: kill if no output for N seconds (default 120s)
# - Hard timeout: absolute max regardless of output (default 1200s)
# - Both stdout AND stderr count as progress (Kilo logs to stderr during tool calls)
stdout, stderr, returncode = _monitor_process(
    proc, idle_timeout=120, hard_timeout=1200, poll_interval=2, stream_output=True
)
```

### JSONL Stream Parsing (step_finish detection)

Kilo `--format json` outputs concatenated JSON objects. Parse them correctly:

```python
# parse_kilo_jsonl() pattern:
# - Uses json.JSONDecoder.raw_decode() for concatenated JSON (not newline-delimited)
# - Accumulates text events into result string
# - Accumulates tokens/cost across MULTIPLE step_finish events (multi-step agent runs)
# - Rejects incomplete runs: raises RuntimeError if no step_finish event received
# - OOM protection: rejects output > 5MB
# - Attack protection: aborts after 10 consecutive parse errors
```

### Retry with Exponential Backoff

```python
# run_kilo() retries on:
# 1. Transient exit codes (network errors, rate limits)
# 2. Retryable parse failures (incomplete JSONL, garbled output)
# 3. Timeouts (idle or hard)
#
# Backoff: 2^attempt seconds (1s, 2s, 4s)
# Max retries: 3 (configurable via MAX_RETRIES)
# Failed models tracked in a set — same model never retried in same escalation chain
```

### Command Injection Prevention

```python
# build_kilo_command() validates ALL inputs:
# - Model: regex whitelist [a-zA-Z0-9/_.\-:]+ with kilo/ prefix
# - Variant: must be in VALID_VARIANTS set
# - Agent: must be in VALID_AGENTS set
# - Session ID: regex [a-zA-Z0-9_-]{1,64}, only passed if starts with "ses_"
# - File paths: resolved, validated within project root, symlink targets checked, max size enforced
```

### Risk-Based Model Routing

```python
# select_model_for_diff() / should_escalate_to_opus():
# - Default: cheap model (Gemini Flash)
# - Escalate to premium (Opus) ONLY if diff touches high-risk paths
# - High-risk: src/, auth/, migrations/, compose.yaml, .env, manifest.json
# - Customizable via KILO_HIGH_RISK_PATHS env var
# - Docs-only changes always use cheapest model
```

### Tiered Escalation

```python
# get_escalation_model():
# economy → balanced → premium → apex
# Each tier has a cost estimate. If cost cap is set, expensive tiers are skipped.
# Failed models tracked — same model never retried in same escalation chain.
```

### Issue Fingerprinting (deduplication across iterations)

```python
# get_issue_fingerprint() hashes (file, line, category, severity)
# filter_repeated_issues() removes issues already reported in prior iterations
# Prevents review loops from reporting the same bug on every pass
```

### Secret Redaction

```python
# _redact_secrets() strips API keys, tokens, passwords from error messages
# Applied to all error output before logging or reporting to user
# Pattern: regex on common secret formats (sk-..., token=..., password=...)
```

---

## See Also

- **[KILO_AGENT_NAMING.md](KILO_AGENT_NAMING.md)** - Tier-based agent naming convention
- **[KILO_AGENT_SELECTION_GUIDE.md](KILO_AGENT_SELECTION_GUIDE.md)** - Model selection guide
- **[README.md](README.md)** - Kilo system overview
- **[Kilo CLI Docs](https://kilo.ai/docs/code-with-ai/platforms/cli)** - Official CLI documentation
- **[Kilo GitHub](https://github.com/Kilo-Org/kilocode)** - Source code and releases
- **[What's New](https://kilo.ai/docs/code-with-ai/platforms/vscode/whats-new)** - Latest feature announcements
