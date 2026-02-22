# Kilo AI Complete Reference

> Comprehensive documentation for Kilo AI CLI - agents, models, variants, and costs.

**Last Updated:** 2026-02-20

> ⚠️ **Version Notice:** This documentation applies only to Kilo version 1.0 and later. Users running versions below 1.0 should upgrade before proceeding.

**Source:** [Kilo-Org/kilo](https://github.com/Kilo-Org/kilo) · [Report an issue](https://github.com/Kilo-Org/kilo/issues)

---

### Raw Model Data

Full verbose specs for **all 628 Kilo models** are stored in:
- **File:** [`kilo-models-raw.json`](./kilo-models-raw.json)
- **Update command:** `python scripts/update_kilo_models.py`
- **Contains:** id, name, cost (input/output/cache), limits (context/output), capabilities (reasoning, toolcall, attachment, input/output types), variants, description

---

## Table of Contents

1. [Overview](#overview)
2. [Installation](#installation)
3. [CLI Reference](#cli-reference)
4. [Interactive Slash Commands](#interactive-slash-commands)
5. [Agents](#agents)
6. [Variants](#variants)
7. [Models](#models)
8. [Cost Reference](#cost-reference)
9. [Configuration](#configuration)
10. [Permissions](#permissions)
11. [Interactive Mode](#interactive-mode)
12. [Autonomous Mode](#autonomous-mode)
13. [Session Management](#session-management)
14. [Python Integration](#python-integration)

---

## Overview

Kilo is an AI CLI tool that provides access to multiple AI providers (Google, OpenAI, Anthropic, etc.) through a unified interface. The Kilo Code CLI uses the same underlying technology that powers the IDE extensions, so you can expect the same workflow to handle agentic coding tasks from start to finish.

It supports:

- **Multiple providers** via `kilo/provider/model` format
- **Agents** for different task types (code, ask, debug, etc.)
- **Variants** for controlling reasoning effort (minimal, low, high, max)
- **Sessions** for maintaining conversation context
- **Pay-per-use pricing** with cost tracking

### What You Can Do with Kilo CLI

- **Plan and execute code changes** without leaving your terminal
- **Switch between hundreds of LLMs** without constraints
- **Choose the right mode** for the task (Architect, Ask, Debug, Orchestrator, or custom agents)
- **Automate tasks** with AI assistance for shell scripts
- **Extend capabilities** with Agent Skills for domain expertise

### Quick Start

```bash
# Simple query
kilo run "What is the capital of France?"

# With specific model
kilo run --model kilo/google/gemini-3-flash-preview "Explain recursion"

# With agent and variant
kilo run --agent ask --variant high --model kilo/anthropic/claude-sonnet-4-5 "Review this code"

# Pipeline mode (auto-approve)
kilo run --auto --format json --model kilo/google/gemini-3-flash-preview "Extract data from this text"
```

---

## Installation

### Install via npm

```bash
npm install -g @kilocode/cli
```

### Verify Installation

```bash
kilo --version
```

### Basic Usage

```bash
# Start the TUI (Terminal User Interface)
kilo

# Check the version
kilo --version

# Get help
kilo --help
```

### First-Time Setup with /connect

After installation, run `kilo` and use the `/connect` command to add your first provider credentials. This is the interactive way to configure API keys for model providers.

### Update

```bash
# Upgrade via kilo
kilo upgrade

# Or use npm
npm update -g @kilocode/cli
```

---

## CLI Reference

### Top-Level CLI Commands

| Command | Description |
|---------|-------------|
| `kilo [project]` | Start the TUI (Terminal User Interface) |
| `kilo run [message..]` | Run with a message (non-interactive mode) |
| `kilo attach <url>` | Attach to a running kilo server |
| `kilo serve` | Start a headless server |
| `kilo web` | Start server and open web interface |
| `kilo auth` | Manage credentials (login, logout, list) |
| `kilo agent` | Manage agents (create, list) |
| `kilo mcp` | Manage MCP servers (list, add, auth) |
| `kilo models [provider]` | List available models |
| `kilo stats` | Show token usage and cost statistics |
| `kilo session` | Manage sessions (list) |
| `kilo export [sessionID]` | Export session data as JSON |
| `kilo import <file>` | Import session data from JSON file or URL |
| `kilo upgrade [target]` | Upgrade kilo to latest or specific version |
| `kilo uninstall` | Uninstall kilo and remove related files |
| `kilo pr <number>` | Fetch and checkout a GitHub PR branch |
| `kilo github` | Manage GitHub agent (install, run) |
| `kilo debug` | Debugging and troubleshooting tools |
| `kilo completion` | Generate shell completion script |

### Global Options

| Flag | Description |
|------|-------------|
| `--help, -h` | Show help |
| `--version, -v` | Show version number |
| `--print-logs` | Print logs to stderr |
| `--log-level` | Log level: DEBUG, INFO, WARN, ERROR |

### Run Command Options

| Flag | Description |
|------|-------------|
| `-m, --model` | Model to use (format: `provider/model` or `kilo/provider/model`) |
| `--agent` | Agent to use (ask, code, debug, etc.) |
| `--variant` | Model variant (minimal, low, high, max) |
| `-c, --continue` | Continue the last session |
| `-s, --session` | Session ID to continue |
| `--fork` | Fork the session when continuing |
| `--format` | Output format: `default` or `json` |
| `-f, --file` | File(s) to attach to message |
| `--title` | Title for the session |
| `--auto` | Auto-approve all permissions (autonomous mode) |
| `--thinking` | Show thinking blocks |
| `--share` | Share the session |

---

## Interactive Slash Commands

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
| `/connect` | Connect/add a provider - entry point for new users to add API credentials |

### System Commands

| Command | Aliases | Description |
|---------|---------|-------------|
| `/status` | - | View status |
| `/themes` | - | Switch theme |
| `/help` | - | Show help |
| `/editor` | - | Open external editor |
| `/exit` | `/quit`, `/q` | Exit the app |

### Kilo Gateway Commands (when connected)

| Command | Aliases | Description |
|---------|---------|-------------|
| `/profile` | `/me`, `/whoami` | View your Kilo Gateway profile |
| `/teams` | `/team`, `/org`, `/orgs` | Switch between Kilo Gateway teams |

### Built-in Commands

| Command | Description |
|---------|-------------|
| `/init` | Create/update AGENTS.md file for the project |
| `/local-review` | Review current branch changes vs base branch |
| `/local-review-uncommitted` | Review uncommitted changes (staged + unstaged) |

---

## Agents

Agents define the AI's behavior, permissions, and capabilities for specific task types.

### Built-in Agents

| Agent | Type | Description | Permissions |
|-------|------|-------------|-------------|
| **ask** | primary | Read-only Q&A, analysis, explanations | read, grep, glob, list, codesearch |
| **code** | primary | Full coding agent with file edit capabilities | read, write, edit, bash, all tools |
| **debug** | primary | Debugging and troubleshooting | read, grep, bash, diagnostics |
| **plan** | primary | Planning and task breakdown | read, question, plan_exit |
| **summary** | primary | Summarization tasks | read only |
| **title** | primary | Generate titles for sessions | read only |
| **orchestrator** | primary | Multi-agent coordination | read, grep, glob, task, bash, websearch |
| **compaction** | primary | Context compaction | limited |
| **general** | subagent | General-purpose subagent | all except question, plan |

### Agent Permissions

```
read           - Read files
edit           - Modify files
bash           - Execute shell commands
grep           - Search file contents
glob           - Find files by pattern
list           - List directory contents
codesearch     - Semantic code search
websearch      - Web search
webfetch       - Fetch URL content
task           - Create subtasks
question       - Ask user questions
todoread       - Read todo list
todowrite      - Modify todo list
external_directory - Access directories outside project
```

### Agent Selection by Use Case

| Use Case | Recommended Agent | Why |
|----------|-------------------|-----|
| CV Extraction | `ask` | Read-only, no file modifications needed |
| Code Review | `ask` or `code` | `ask` for analysis, `code` if suggesting edits |
| Bug Fixing | `code` or `debug` | Need file edit permissions |
| Refactoring | `code` | Full edit capabilities |
| Documentation | `ask` | Analysis and generation |
| Planning | `plan` | Specialized for task breakdown |

### Using Agents

```bash
# CLI
kilo run --agent ask "Explain this function"
kilo run --agent code "Fix the bug in main.py"
kilo run --agent debug "Why is this test failing?"

# Python (via _run_kilo)
result = await _run_kilo(
    prompt="Extract skills from CV",
    model="kilo/google/gemini-3-flash-preview",
    agent="ask",
    timeout=120,
)
```

---

## Variants

Variants control the **reasoning effort** - how much "thinking" the model does before responding.

### Valid Variants

| Variant | Reasoning Effort | Use Case | Token Impact |
|---------|------------------|----------|--------------|
| **minimal** | Lowest | Quick, simple tasks | Lowest cost |
| **low** | Below average | Routine operations | Low cost |
| **high** | Above average | Complex analysis, quality matters | Higher cost |
| **max** | Maximum | Most difficult problems | Highest cost |

> ⚠️ **Note:** The standard Kilo variants are `minimal`, `low`, `high`, `max`. Some providers (OpenAI) support additional variants like `medium` - see provider-specific notes below.

### Variant Behavior by Provider

Different providers implement variants differently:

**OpenAI (o1, o3, o4 series):**
- Supports additional variant: `medium` (maps to `reasoningEffort: medium`)
```json
{
  "low": {"reasoningEffort": "low"},
  "medium": {"reasoningEffort": "medium"},
  "high": {"reasoningEffort": "high"}
}
```

**Google/Anthropic:**
- Variants affect internal prompt construction and sampling parameters
- Higher variants may trigger chain-of-thought reasoning

### CV Extraction Test Results (variant comparison)

| Variant | Duration | Input Tokens | Output Tokens | Cost | Skills | Certificates |
|---------|----------|--------------|---------------|------|--------|--------------|
| default | 36.1s | 7,409 | 1,382 | $0.0129 | 30 | 21 |
| **high** | 24.4s | 7,409 | 1,393 | $0.0157 | 30 | **22** |
| max | 19.5s | 3,607 | 1,259 | $0.0109 | 30 | 17 |

**Recommendation:** Use `variant=high` for CV extraction - best quality-to-cost ratio.

### Using Variants

```bash
# CLI
kilo run --variant high "Analyze this complex algorithm"

# Python
result = await _run_kilo(
    prompt="Extract CV data",
    model="kilo/google/gemini-3-flash-preview",
    variant="high",
    agent="ask",
    timeout=120,
)
```

---

## Models

Kilo provides access to 200+ models across multiple providers.

### Model Format

```
kilo/{provider}/{model-name}
```

Examples:
- `kilo/google/gemini-3-flash-preview`
- `kilo/anthropic/claude-sonnet-4-5`
- `kilo/openai/gpt-4o`

### Model Specifications Schema

Each model has the following specification structure:

```json
{
  "id": "provider/model-name",
  "providerID": "kilo",
  "name": "Display Name",
  "cost": {
    "input": 0.0000005,    // Cost per token (input)
    "output": 0.000003,    // Cost per token (output)
    "cache": {
      "read": 0.00000005,  // Cache read cost (typically 10% of input)
      "write": 0.0         // Cache write cost
    }
  },
  "limit": {
    "context": 1048576,    // Max context window (tokens)
    "output": 65535        // Max output tokens
  },
  "capabilities": {
    "temperature": true,   // Supports temperature control
    "reasoning": true,     // Has reasoning/thinking capability
    "attachment": true,    // Supports file attachments
    "toolcall": true,      // Supports function/tool calling
    "input": {
      "text": true,
      "audio": true,
      "image": true,
      "video": true,
      "pdf": false
    },
    "output": {
      "text": true,
      "audio": false,
      "image": false,
      "video": false,
      "pdf": false
    }
  },
  "variants": {
    "minimal": {"reasoningEffort": "minimal"},
    "low": {"reasoningEffort": "low"},
    "high": {"reasoningEffort": "high"},
    "max": {"reasoningEffort": "max"}
  }
}
```

---

### Google Models (Detailed Specs)

#### `kilo/google/gemini-3-flash-preview` ⭐ RECOMMENDED

| Property | Value |
|----------|-------|
| **Context** | 1,048,576 tokens (1M) |
| **Output** | 65,535 tokens |
| **Cost (Input)** | $0.50 / 1M tokens |
| **Cost (Output)** | $3.00 / 1M tokens |
| **Cache Read** | $0.05 / 1M tokens (10%) |
| **Reasoning** | ✅ Yes (variants: minimal, low, high, max) |
| **Tool Call** | ✅ Yes |
| **Attachments** | ✅ Yes |
| **Input: Text** | ✅ |
| **Input: Image** | ✅ |
| **Input: Audio** | ✅ |
| **Input: Video** | ✅ |
| **Input: PDF** | ❌ |

**Description:** High speed, high value thinking model for agentic workflows, multi-turn chat, and coding. Near Pro-level reasoning with lower latency.

#### `kilo/google/gemini-3-pro-preview`

| Property | Value |
|----------|-------|
| **Context** | 1,048,576 tokens (1M) |
| **Output** | 65,535 tokens |
| **Cost (Input)** | $1.25 / 1M tokens |
| **Cost (Output)** | $5.00 / 1M tokens |
| **Reasoning** | ✅ Yes |
| **Tool Call** | ✅ Yes |
| **Attachments** | ✅ Yes |
| **Input: Image/Audio/Video** | ✅ All |

#### `kilo/google/gemini-2.5-flash`

| Property | Value |
|----------|-------|
| **Context** | 1,048,576 tokens (1M) |
| **Output** | 65,535 tokens |
| **Cost (Input)** | $0.075 / 1M tokens |
| **Cost (Output)** | $0.30 / 1M tokens |
| **Reasoning** | ✅ Yes |
| **Tool Call** | ✅ Yes |

#### `kilo/google/gemini-2.5-flash-lite`

| Property | Value |
|----------|-------|
| **Context** | 1,048,576 tokens (1M) |
| **Output** | 65,535 tokens |
| **Cost (Input)** | $0.02 / 1M tokens |
| **Cost (Output)** | $0.08 / 1M tokens |
| **Reasoning** | ❌ No |
| **Tool Call** | ✅ Yes |

**Note:** Ultra cheap, good for simple tasks.

---

### Anthropic Models (Detailed Specs)

#### Claude Sonnet Family (4.0+)

##### `kilo/anthropic/claude-sonnet-4` ⭐ RECOMMENDED

| Property | Value |
|----------|-------|
| **Context** | 1,000,000 tokens (1M) |
| **Output** | 64,000 tokens |
| **Cost (Input)** | $3.00 / 1M tokens |
| **Cost (Output)** | $15.00 / 1M tokens |
| **Cache Read** | $0.30 / 1M tokens (10%) |
| **Cache Write** | $3.75 / 1M tokens |
| **Reasoning** | ✅ Yes |
| **Tool Call** | ✅ Yes |
| **Attachments** | ✅ Yes |
| **Input: Image** | ✅ |
| **Variants** | none |

**Description:** SWE-bench 72.7%, improved autonomous codebase navigation, reduced error rates in agent-driven workflows.

##### `kilo/anthropic/claude-sonnet-4.5`

| Property | Value |
|----------|-------|
| **Context** | 1,000,000 tokens (1M) |
| **Output** | 64,000 tokens |
| **Cost (Input)** | $3.00 / 1M tokens |
| **Cost (Output)** | $15.00 / 1M tokens |
| **Cache Read** | $0.30 / 1M tokens |
| **Reasoning** | ✅ Yes |
| **Tool Call** | ✅ Yes |
| **Attachments** | ✅ Yes |
| **Input: Image** | ✅ |

**Description:** Most advanced Sonnet, state-of-the-art on SWE-bench Verified. Improved tool orchestration, speculative parallel execution.

##### `kilo/anthropic/claude-sonnet-4.6` ⭐ LATEST

| Property | Value |
|----------|-------|
| **Context** | 1,000,000 tokens (1M) |
| **Output** | 128,000 tokens |
| **Cost (Input)** | $3.00 / 1M tokens |
| **Cost (Output)** | $15.00 / 1M tokens |
| **Cache Read** | $0.30 / 1M tokens |
| **Reasoning** | ✅ Yes |
| **Tool Call** | ✅ Yes |
| **Attachments** | ✅ Yes |
| **Input: Image** | ✅ |

**Description:** Most capable Sonnet-class model. Frontier performance on coding, agents, professional work. 128K output limit.

---

#### Claude Opus Family (4.5+)

##### `kilo/anthropic/claude-opus-4.5`

| Property | Value |
|----------|-------|
| **Context** | 200,000 tokens |
| **Output** | 64,000 tokens |
| **Cost (Input)** | $5.00 / 1M tokens |
| **Cost (Output)** | $25.00 / 1M tokens |
| **Cache Read** | $0.50 / 1M tokens (10%) |
| **Cache Write** | $6.25 / 1M tokens |
| **Reasoning** | ✅ Yes |
| **Tool Call** | ✅ Yes |
| **Attachments** | ✅ Yes |
| **Input: Image** | ✅ |

**Description:** Frontier reasoning model for complex software engineering, agentic workflows, long-horizon computer use. Supports verbosity parameter (low/medium/high).

##### `kilo/anthropic/claude-opus-4.6` ⭐ LATEST

| Property | Value |
|----------|-------|
| **Context** | 1,000,000 tokens (1M) |
| **Output** | 128,000 tokens |
| **Cost (Input)** | $5.00 / 1M tokens |
| **Cost (Output)** | $25.00 / 1M tokens |
| **Cache Read** | $0.50 / 1M tokens |
| **Reasoning** | ✅ Yes |
| **Tool Call** | ✅ Yes |
| **Attachments** | ✅ Yes |
| **Input: Image** | ✅ |

**Description:** Strongest Anthropic model for coding and long-running professional tasks. 1M context, 128K output. Ideal for large codebases, complex refactors, multi-step debugging.

---

### OpenAI Models (Detailed Specs)

#### GPT-5 Family

##### `kilo/openai/gpt-5` ⭐ FLAGSHIP

| Property | Value |
|----------|-------|
| **Context** | 400,000 tokens |
| **Output** | 128,000 tokens |
| **Cost (Input)** | $1.25 / 1M tokens |
| **Cost (Output)** | $10.00 / 1M tokens |
| **Cache Read** | $0.125 / 1M tokens (10%) |
| **Reasoning** | ✅ Yes |
| **Tool Call** | ✅ Yes |
| **Attachments** | ✅ Yes |
| **Input: Image** | ✅ |
| **Variants** | none, minimal, low, medium, high, xhigh |

**Description:** OpenAI's most advanced model. Major improvements in reasoning, code quality, reduced hallucination. Test-time routing, "think hard about this" prompts.

##### `kilo/openai/gpt-5-codex` ⭐ CODING

| Property | Value |
|----------|-------|
| **Context** | 400,000 tokens |
| **Output** | 128,000 tokens |
| **Cost (Input)** | $1.25 / 1M tokens |
| **Cost (Output)** | $10.00 / 1M tokens |
| **Cache Read** | $0.125 / 1M tokens |
| **Reasoning** | ✅ Yes |
| **Tool Call** | ✅ Yes |
| **Attachments** | ✅ Yes |
| **Input: Image** | ✅ |
| **Variants** | none, minimal, low, medium, high, xhigh |

**Description:** Specialized for software engineering. Building projects, feature dev, debugging, large-scale refactoring. More steerable than GPT-5, cleaner code outputs. Multi-hour runs supported.

##### `kilo/openai/gpt-5-mini`

| Property | Value |
|----------|-------|
| **Context** | 400,000 tokens |
| **Output** | 128,000 tokens |
| **Cost (Input)** | $0.25 / 1M tokens |
| **Cost (Output)** | $2.00 / 1M tokens |
| **Cache Read** | $0.025 / 1M tokens |
| **Reasoning** | ✅ Yes |
| **Tool Call** | ✅ Yes |
| **Attachments** | ✅ Yes |
| **Input: Image** | ✅ |
| **Variants** | none, minimal, low, medium, high, xhigh |

**Description:** Compact version of GPT-5 for lighter reasoning tasks. Successor to o4-mini. Same safety-tuning, reduced latency and cost.

##### `kilo/openai/gpt-5-nano`

| Property | Value |
|----------|-------|
| **Context** | 400,000 tokens |
| **Output** | 128,000 tokens |
| **Cost (Input)** | $0.05 / 1M tokens |
| **Cost (Output)** | $0.40 / 1M tokens |
| **Cache Read** | $0.005 / 1M tokens |
| **Reasoning** | ✅ Yes |
| **Tool Call** | ✅ Yes |
| **Attachments** | ✅ Yes |
| **Input: Image** | ✅ |
| **Variants** | none, minimal, low, medium, high, xhigh |

**Description:** Smallest/fastest GPT-5 variant. Ultra-low latency, cost-sensitive apps. Successor to GPT-4.1-nano.

##### `kilo/openai/gpt-5-chat`

| Property | Value |
|----------|-------|
| **Context** | 128,000 tokens |
| **Output** | 16,384 tokens |
| **Cost (Input)** | $1.25 / 1M tokens |
| **Cost (Output)** | $10.00 / 1M tokens |
| **Reasoning** | ❌ No |
| **Tool Call** | ❌ No |
| **Input: Image** | ✅ |

**Description:** Designed for advanced, natural, multimodal conversations for enterprise applications.

---

#### GPT-5.2 Family (Latest)

##### `kilo/openai/gpt-5.2` ⭐ LATEST FRONTIER

| Property | Value |
|----------|-------|
| **Context** | 400,000 tokens |
| **Output** | 128,000 tokens |
| **Cost (Input)** | $1.75 / 1M tokens |
| **Cost (Output)** | $14.00 / 1M tokens |
| **Cache Read** | $0.175 / 1M tokens (10%) |
| **Reasoning** | ✅ Yes |
| **Tool Call** | ✅ Yes |
| **Attachments** | ✅ Yes |
| **Input: Image** | ✅ |
| **Variants** | none, minimal, low, medium, high, xhigh |

**Description:** Latest frontier-grade model. Stronger agentic and long context performance vs GPT-5.1. Adaptive reasoning allocates computation dynamically. Consistent gains across math, coding, science, tool calling.

##### `kilo/openai/gpt-5.2-codex` ⭐ CODING

| Property | Value |
|----------|-------|
| **Context** | 400,000 tokens |
| **Output** | 128,000 tokens |
| **Cost (Input)** | $1.75 / 1M tokens |
| **Cost (Output)** | $14.00 / 1M tokens |
| **Cache Read** | $0.175 / 1M tokens |
| **Reasoning** | ✅ Yes |
| **Tool Call** | ✅ Yes |
| **Attachments** | ✅ Yes |
| **Input: Image** | ✅ |
| **Variants** | none, minimal, low, medium, high, xhigh |

**Description:** Upgraded from GPT-5.1-Codex. More steerable, cleaner code outputs. Supports multi-hour runs for large projects. Structured code reviews, UI development from screenshots.

##### `kilo/openai/gpt-5.2-pro`

| Property | Value |
|----------|-------|
| **Context** | 400,000 tokens |
| **Output** | 128,000 tokens |
| **Cost (Input)** | $21.00 / 1M tokens |
| **Cost (Output)** | $168.00 / 1M tokens |
| **Reasoning** | ✅ Yes |
| **Tool Call** | ✅ Yes |
| **Attachments** | ✅ Yes |
| **Input: Image** | ✅ |
| **Variants** | none, minimal, low, medium, high, xhigh |

**Description:** Most advanced OpenAI model. Optimized for complex step-by-step reasoning, instruction following, high-stakes use cases. Reduced hallucination, sycophancy.

##### `kilo/openai/gpt-5.2-chat`

| Property | Value |
|----------|-------|
| **Context** | 128,000 tokens |
| **Output** | 16,384 tokens |
| **Cost (Input)** | $1.75 / 1M tokens |
| **Cost (Output)** | $14.00 / 1M tokens |
| **Cache Read** | $0.175 / 1M tokens |
| **Reasoning** | ❌ No |
| **Tool Call** | ✅ Yes |
| **Input: Image** | ✅ |

**Description:** Fast, lightweight for low-latency chat. Adaptive reasoning on harder queries. Warmer, more conversational. Better instruction following.

---

#### GPT-5.3 Family (Preview)

> **Note:** GPT-5.3 models are visible in Kilo CLI UI but not yet in `kilo models --verbose` output. Specs below are estimates based on GPT-5.2 patterns.

##### `kilo/openai/gpt-5.3-codex` ⭐ PREVIEW

| Property | Value |
|----------|-------|
| **Context** | 400,000 tokens (est.) |
| **Output** | 128,000 tokens (est.) |
| **Cost** | TBD |
| **Reasoning** | ✅ Yes |
| **Tool Call** | ✅ Yes |
| **Variants** | none, minimal, low, medium, high, xhigh (est.) |

**Description:** Next-gen coding model. Successor to GPT-5.2-Codex with improved agentic performance.

##### `kilo/openai/gpt-5.3-codex-spark`

| Property | Value |
|----------|-------|
| **Context** | 400,000 tokens (est.) |
| **Output** | 128,000 tokens (est.) |
| **Cost** | TBD (likely cheaper than Codex) |
| **Reasoning** | ✅ Yes |
| **Tool Call** | ✅ Yes |

**Description:** Lightweight variant of GPT-5.3 Codex for faster iteration cycles.

---

#### Legacy OpenAI Models

| Model | Context | Output | Cost (In/Out) | Reasoning | Tool Call |
|-------|---------|--------|---------------|-----------|-----------|
| `gpt-4o` | 128K | 16K | $2.50 / $10.00 | ❌ | ✅ |
| `gpt-4o-mini` | 128K | 16K | $0.15 / $0.60 | ❌ | ✅ |
| `o4-mini` | 200K | 100K | $1.10 / $4.40 | ✅ | ✅ |
| `o3-mini` | 200K | 100K | $1.10 / $4.40 | ✅ | ✅ |

---

### Other Providers (Summary)

| Provider | Model | Context | Output | Cost (In/Out per 1M) | Reasoning | Tool Call |
|----------|-------|---------|--------|---------------------|-----------|-----------|
| **xAI** | `grok-4` | 131K | 131K | $3.00 / $15.00 | ✅ | ✅ |
| **xAI** | `grok-4-fast` | 131K | 131K | $5.00 / $15.00 | ✅ | ✅ |
| **Meta** | `llama-4-maverick` | 256K | 256K | $0.50 / $0.77 | ✅ | ✅ |
| **Qwen** | `qwen3-coder` | 256K | 65K | $0.80 / $2.40 | ✅ | ✅ |
| **Qwen** | `qwen3-max` | 131K | 8K | $1.60 / $6.40 | ✅ | ✅ |
| **Mistral** | `mistral-large-2512` | 128K | 128K | $2.00 / $6.00 | ❌ | ✅ |
| **Mistral** | `devstral-medium` | 128K | 128K | $0.80 / $2.40 | ✅ | ✅ |
| **DeepSeek** | `deepseek-r1` | 164K | 164K | $0.55 / $2.19 | ✅ | ❌ |
| **Z.ai** | `glm-5` | 204K | 131K | $0.30 / $2.55 | ✅ | ✅ |
| **Arcee** | `coder-large` | 32K | 6K | $0.50 / $0.80 | ❌ | ❌ |

---

### Free Models (Recommended)

**Top 3 free models** for production use:

| Model | Context | Output | Best For |
|-------|---------|--------|----------|
| `kilo/z-ai/glm-5:free` | 202K | 131K | CV extraction, complex coding |
| `kilo/minimax/minimax-m2.5:free` | 204K | 131K | Coding (SWE-Bench 80.2%) |
| `kilo/stepfun/step-3.5-flash:free` | 256K | 256K | Long documents, speed |

#### All Free Models

| Model | Context | Output | Reasoning | Tool Call | Image | Description |
|-------|---------|--------|-----------|-----------|-------|-------------|
| `kilo/z-ai/glm-5:free` | 202K | 131K | ✅ | ✅ | ❌ | Flagship open-source, production-grade coding |
| `kilo/minimax/minimax-m2.5:free` | 204K | 131K | ✅ | ✅ | ❌ | SWE-Bench 80.2%, Excel/Word/PPT |
| `kilo/stepfun/step-3.5-flash:free` | 256K | 256K | ✅ | ✅ | ❌ | MoE 196B params, extremely fast |
| `kilo/arcee-ai/trinity-large-preview:free` | 131K | 26K | ❌ | ✅ | ❌ | Creative writing, role-play |
| `kilo/corethink:free` | 78K | 8K | ❌ | ✅ | ❌ | Lightweight reasoning |
| `kilo/openrouter/free` | 200K | 40K | ✅ | ✅ | ✅ | Auto-router, supports images |

#### Free Model Limitations

- **No image input** (except `openrouter/free`)
- **No audio/video** input or output
- **Rate limits** may apply during high traffic
- **Logging notice**: Some free endpoints log prompts to improve models

#### Using Free Models

```bash
# CLI
kilo run --model kilo/z-ai/glm-5:free "Explain this code"

# Python
result = await _run_kilo(
    prompt="Extract CV data",
    model="stepfun/step-3.5-flash:free",
    timeout=120,
)
```

#### Free Model CV Extraction — NOT RECOMMENDED

**Baseline:** `kilo/google/gemini-3-flash-preview` (variant=high) — 30 skills, 17 certs, $0.0109, **19.5s**

**Free Model Test Results:**

| Model | Time | Skills | Certs | Viable? |
|-------|------|--------|-------|---------|
| `step-3.5-flash:free` (default) | 20s | 30 | **1** | ❌ Quality gap |
| `step-3.5-flash:free` (high) | 65s | 39 | **1** | ❌ Too slow + quality gap |
| `step-3.5-flash:free` (optimized prompt) | **133s** | 30 | 17 | ❌ Exceeds 60s limit |
| `minimax-m2.5:free` | 36s | 24 | **1** | ❌ Quality gap |
| `glm-5:free` | 44s | 23 | **1** | ❌ Not actually free ($0.019) |

**Conclusion:** Free models are **NOT viable** for production CV extraction because:
1. Fast variants (<60s) extract only **1 certificate** vs 17
2. Quality-matching prompts require **133s** (exceeds 60s limit)
3. Optimization techniques require pre-knowledge of cert count (impossible at upload time)

**Recommendation:** Use `kilo/google/gemini-3-flash-preview` — $0.0109 per extraction is acceptable cost for reliable quality.

### Recommended Models by Use Case

| Use Case | Primary Model | Fallback |
|----------|---------------|----------|
| **CV Extraction** | `kilo/google/gemini-3-flash-preview` | `gemini-3-pro-preview` |
| **Code Review** | `kilo/anthropic/claude-sonnet-4-5` | `kilo/openai/gpt-5.1-codex` |
| **Quick Tasks** | `kilo/google/gemini-2.5-flash-lite` | `kilo/openai/gpt-4o-mini` |
| **Complex Reasoning** | `kilo/openai/o3-mini` | `kilo/anthropic/claude-opus-4` |
| **Budget Conscious** | `kilo/z-ai/glm-5:free` | `kilo/google/gemini-2.5-flash-lite` |

---

## Cost Reference

### Pricing Structure

Kilo uses **pay-per-use** pricing based on token consumption:

```
Total Cost = (Input Tokens × Input Rate) + (Output Tokens × Output Rate)
```

Cache reads are typically 50% of input cost.

### Cost Comparison: Kilo vs Factory (droid exec)

| Provider | Pricing Model | Cost per 1M Tokens |
|----------|---------------|-------------------|
| **Factory (droid exec)** | Subscription | $1.00 (flat rate) |
| **Kilo** | Pay-per-use | Varies by model |

**Factory:** $200 for 200M tokens = **$1.00 per 1M tokens**

### Per-Operation Cost Examples

Based on CV extraction test (same prompt, same model family):

| Provider | Model | Tokens Used | Cost |
|----------|-------|-------------|------|
| Droid Exec | gemini-3-flash-preview | 18,862 | $0.0189 |
| Kilo (high) | kilo/google/gemini-3-flash-preview | 8,802 | $0.0157 |

**Kilo advantage:** 17% cheaper, 53% fewer tokens, better quality

### Budget Planning

| Operation | Est. Cost (Kilo) | Est. Cost (Factory) |
|-----------|------------------|---------------------|
| 1 CV extraction | $0.015 | $0.019 |
| 100 CV extractions | $1.50 | $1.90 |
| 1000 job evaluations | $0.50 | $0.60 |
| Daily usage (light) | $0.10-0.50 | $0.15-0.75 |
| Daily usage (heavy) | $1.00-5.00 | $1.50-7.50 |

### Monitoring Costs

```bash
# View usage statistics
kilo stats

# Output includes:
# - Total cost
# - Average cost per day
# - Token usage breakdown
# - Tool usage distribution
```

---

## CLI Usage

### Basic Commands

```bash
# Run with message
kilo run "Your prompt here"

# Continue last session
kilo run --continue "Follow up question"

# Use specific session
kilo run --session ses_abc123 "Continue this conversation"

# Fork a session (branch off)
kilo run --session ses_abc123 --fork "Try different approach"
```

### Model & Agent Selection

```bash
# Specify model
kilo run -m kilo/google/gemini-3-flash-preview "Query"

# Specify agent
kilo run --agent ask "Explain this code"
kilo run --agent code "Fix the bug"

# Specify variant
kilo run --variant high "Complex analysis"

# All together
kilo run -m kilo/anthropic/claude-sonnet-4-5 --agent code --variant max "Refactor this module"
```

### Pipeline Mode (Automation)

```bash
# Auto-approve all actions
kilo run --auto "Create a new file called test.py"

# JSON output format (for parsing)
kilo run --format json --auto "Extract data"

# With file attachment
kilo run --file document.pdf "Summarize this document"
```

### Session Management

```bash
# List sessions
kilo session

# Export session
kilo export ses_abc123 > session.json

# Import session
kilo import session.json
```

### Model Discovery

```bash
# List all models
kilo models

# List models for specific provider
kilo models kilo

# Verbose output (includes costs)
kilo models --verbose openai

# Refresh cache
kilo models --refresh
```

### Debugging

```bash
# Show configuration
kilo debug config

# Show agent details
kilo debug agent ask

# Show paths
kilo debug paths

# List available skills
kilo debug skill
```

---

## Integration Guide

### Python Integration

```python
from src.linkedin_plugin.backend.services.droid_wrapper import (
    _run_kilo,
    call_droid_exec_with_session,
)

# Direct Kilo call
result = await _run_kilo(
    prompt="Extract skills from this CV: ...",
    model="kilo/google/gemini-3-flash-preview",
    timeout=120,
    variant="high",
    agent="ask",
    session_id="optional-session-id",
)

# Result structure
{
    "result": "The extracted text response",
    "input_tokens": 7409,
    "output_tokens": 1393,
    "reasoning_tokens": 0,
    "total_tokens": 8802,
    "cost": 0.0157,
    "session_id": "ses_abc123",
    "model": "kilo/google/gemini-3-flash-preview",
}

# Session-aware call (recommended)
result = await call_droid_exec_with_session(
    prompt="Extract CV data",
    call_type="cv_extraction",
    user_id=user_id,
    variant_id=variant_id,
    model="kilo/google/gemini-3-flash-preview",  # Kilo model
    kilo_variant="high",
    kilo_agent="ask",
)
```

### Default Configuration

In `src/linkedin_plugin/backend/services/models.py`:

```python
KILO_CALL_TYPE_DEFAULTS = {
    "cv_extraction": {"variant": "high", "agent": "ask"},
    "cv_generation": {"variant": "high", "agent": "ask"},
    "job_evaluation": {"variant": None, "agent": "ask"},
    "answer_gen": {"variant": None, "agent": "ask"},
}
```

### Error Handling

```python
from src.linkedin_plugin.backend.services.droid_wrapper import (
    DroidExecError,
    DroidExecTimeout,
)

try:
    result = await _run_kilo(...)
except DroidExecTimeout as e:
    logger.error(f"Kilo timed out: {e}")
    # Fallback to droid exec
except DroidExecError as e:
    logger.error(f"Kilo failed: {e}")
    # Handle error
```

---

## Appendix

### Valid Variants Reference

```python
VALID_VARIANTS = {"minimal", "low", "high", "max"}
```

### Valid Agents Reference

```python
VALID_AGENTS = {
    "ask",
    "code",
    "compaction",
    "debug",
    "general",
    "orchestrator",
    "plan",
    "summary",
    "title",
}
```

### Environment Variables

| Variable | Description |
|----------|-------------|
| `KILO_API_KEY` | API key for Kilo service |
| `KILO_MODEL` | Default model to use |
| `DROID_MODEL_CV_EXTRACTION` | Override model for CV extraction |

### Troubleshooting

**Kilo command not found:**
```bash
# Check installation
where kilo  # Windows
which kilo  # Linux/Mac

# Common paths on Windows
%APPDATA%\npm\kilo.cmd
%LOCALAPPDATA%\Programs\kilo\kilo.exe
```

**Model not available:**
```bash
# Refresh model cache
kilo models --refresh

# Check if model exists
kilo models kilo | findstr "model-name"
```

**Session errors:**
```bash
# List recent sessions
kilo session

# Clear session state
kilo session clear
```

---

## Configuration

### Config File Locations

| Scope | Path |
|-------|------|
| **Global** | `~/.config/kilo/opencode.json` or `opencode.jsonc` |
| **Project** | `./opencode.json` or `./.opencode/` in project root |

Project-level configuration takes precedence over global settings.

### Basic Configuration Example

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

### Common Configuration Options

| Option | Description |
|--------|-------------|
| `model` | Default model to use |
| `provider` | Provider-specific settings (API keys, base URLs, custom models) |
| `mcp` | MCP server configuration |
| `permission` | Tool permission settings (allow or ask) |
| `instructions` | Paths to instruction files (e.g., `["CONTRIBUTING.md", ".cursor/rules/*.md"]`) |
| `formatter` | Code formatter configuration |
| `disabled_providers` / `enabled_providers` | Control which providers are available |

### Environment Variables in Config

Use `{env:VARIABLE_NAME}` syntax to reference environment variables:

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

### Environment Variable Overrides

| Variable | Description |
|----------|-------------|
| `KILO_PROVIDER` | Override the active provider ID |
| `KILOCODE_<FIELD_NAME>` | For kilocode provider (e.g., `KILOCODE_MODEL`) |
| `KILO_<FIELD_NAME>` | For other providers (e.g., `KILO_API_KEY`) |

---

## Permissions

Kilo Code uses the permission config to decide whether a given action should run automatically, prompt you, or be blocked.

### Permission Actions

| Action | Description |
|--------|-------------|
| `"allow"` | Run without approval |
| `"ask"` | Prompt for approval |
| `"deny"` | Block the action |

### Basic Permission Configuration

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

### Set All Permissions at Once

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

Rules are evaluated by pattern match, with the **last matching rule winning**.

### Wildcards

| Pattern | Description |
|---------|-------------|
| `*` | Matches zero or more of any character |
| `?` | Matches exactly one character |

### Home Directory Expansion

Use `~` or `$HOME` at the start of a pattern:
- `~/projects/*` → `/Users/username/projects/*`
- `$HOME/projects/*` → `/Users/username/projects/*`

### External Directories

Allow tool calls that touch paths outside the working directory:

```json
{
  "$schema": "https://kilo.ai/config.json",
  "permission": {
    "external_directory": {
      "~/projects/personal/**": "allow"
    }
  }
}
```

Block edits while keeping reads:

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

## Interactive Mode

Interactive mode is the default when running Kilo Code without the `--auto` flag.

### Features

- Requests approval for operations not auto-approved
- Allows review before execution
- Option to add operations to auto-approval list

### Interactive Command Approval

When running in interactive mode, command approval requests show hierarchical options:

```
[!] Action Required:
> ✓ Run Command (y)
  ✓ Always run git (1)
  ✓ Always run git status (2)
  ✓ Always run git status --short --branch (3)
  ✗ Reject (n)
```

Selecting an "Always run" option will:
1. Approve and execute the current command
2. Add the pattern to your `execute.allowed` list in config
3. Auto-approve matching commands in the future

---

## Autonomous Mode

Autonomous mode allows Kilo Code to run in automated environments like CI/CD pipelines without user interaction.

### Usage

```bash
# Run in autonomous mode with a message
kilo run --auto "Implement feature X"
```

### Behavior

| Feature | Description |
|---------|-------------|
| **No User Interaction** | All approval requests handled automatically |
| **Auto-Approval/Rejection** | Based on your auto-approval settings |
| **Follow-up Questions** | AI instructed to make autonomous decisions |
| **Automatic Exit** | CLI exits when task completes or times out |

### Auto-Approval

Autonomous mode respects your auto-approval configuration. Operations not auto-approved will not be allowed.

### Follow-up Questions Response

In autonomous mode, when the AI asks a follow-up question, it receives:

> "This process is running in non-interactive autonomous mode. The user cannot make decisions, so you should make the decision autonomously."

### Exit Codes

| Code | Description |
|------|-------------|
| `0` | Success (task completed) |
| `124` | Timeout (task exceeded time limit) |
| `1` | Error (initialization or execution failure) |

### CI/CD Integration Example

```yaml
# GitHub Actions example
- name: Run Kilo Code
  run: |
    kilo run "Implement the new feature" --auto
```

---

## Session Management

### Session Continuation

Resume your last conversation using `--continue` or `-c`:

```bash
# Resume the most recent session from this workspace
kilo --continue
kilo -c
```

Features:
- Automatically finds the most recent session from the current workspace
- Loads the full conversation history
- Cannot be used with autonomous mode or with a prompt argument
- Exits with an error if no previous sessions are found

### Example Workflow

```bash
# Start a session
kilo
# > "Create a REST API"
# ... work on the task ...
# Exit with /exit

# Later, resume the same session
kilo --continue
# Conversation history is restored, ready to continue
```

### Session Commands

```bash
# List sessions
kilo session

# Export session
kilo export ses_abc123 > session.json

# Import session
kilo import session.json
```

### Limitations

- Cannot combine with autonomous mode (`--auto`)
- Cannot use with a prompt argument
- Only works when there's at least one previous session in the workspace

### Switching Teams/Organizations

Use the `/teams` command to see and switch between organizations:

```
/teams
```

Select a team to switch teams. Works for both Team and Enterprise organizations.

---

## Changelog

- **2026-02-20**: Added official Kilo documentation (CLI reference, permissions, modes)
- **2026-02-20**: Initial comprehensive reference
- **2026-02-20**: Added variant comparison test results
- **2026-02-20**: Set Kilo as primary for CV extraction with variant=high
