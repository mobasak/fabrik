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
   - `/orchestrator` - Switch to Orchestrator mode
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

#### Orchestrator Mode

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
Coordination → Orchestrator mode (delegates to specialists)
Quality → Review mode (feedback-focused, limited edits)
```

**Cost optimization by mode:**

| Mode | Typical Cost | Optimization Strategy |
|------|--------------|----------------------|
| Ask | Low | Use free/budget models (no file operations) |
| Architect | Low-Medium | Budget models for planning, premium for complex design |
| Code | High | Start budget, escalate to premium for complex tasks |
| Debug | High | Premium models for complex issues, budget for simple bugs |
| Orchestrator | Medium | Budget for coordination, premium for complex delegation |
| Review | Medium-High | Premium for critical code review, budget for standards checks |

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
