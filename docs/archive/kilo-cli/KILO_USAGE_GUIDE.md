# Kilo CLI Usage Guide

**Last Updated:** 2026-05-20

How to use Kilo CLI as an agentic platform — skills, MCP, workflows, autonomous mode, serve mode, sessions. CLI-focused, not GUI.

> For code review specifically, see [KILO_REVIEW_GUIDE.md](KILO_REVIEW_GUIDE.md).
> For model selection, see [KILO_MODEL_SELECTION.md](KILO_MODEL_SELECTION.md).
> For all use cases beyond coding, see [KILO_USE_CASES.md](KILO_USE_CASES.md).

---

## Quick Start

```bash
# Interactive TUI
cd /opt/myproject && kilo

# One-shot autonomous (no human interaction)
kilo run --auto "Extract all email addresses from data/*.csv and write to output.json"

# With specific model and agent
kilo run -m kilo/google/gemini-3-flash-preview --agent ask --variant high "Summarize this file" --file report.pdf

# Continue last session
kilo --continue

# Start headless API server
kilo serve --port 4096
```

---

## Skills

Skills are domain-specific instruction packages that teach Kilo how to do specific tasks. They're the primary way to extend Kilo beyond generic coding.

### What a skill is

A folder with a `SKILL.md` file containing YAML frontmatter + markdown instructions:

```
~/.kilo/skills/api-design/
└── SKILL.md
```

```markdown
---
name: api-design
description: REST API design — URL structure, HTTP methods, response codes, pagination
---

# API Design Guidelines

## URL Structure
- Use plural nouns: /users, /orders
- Use kebab-case: /order-items
- Nest related resources: /users/{id}/orders
...
```

### Skill locations

| Location | Scope | Priority |
|---|---|---|
| `.kilo/skills/` (in project) | Project only | Highest (overrides global) |
| `~/.kilo/skills/` | All projects | Default |
| `.claude/skills/` | Claude Code compat | Loaded alongside |
| `.agents/skills/` | Open agent standard | Loaded alongside |
| Custom paths in `kilo.jsonc` | Configurable | As configured |
| Remote URLs | Fetched on demand | As configured |

### Custom paths and remote skills

```jsonc
// kilo.jsonc
{
  "skills": {
    "paths": ["/opt/fabrik/shared-skills", "~/my-skills"],
    "urls": ["https://example.com/skills/data-extraction/SKILL.md"]
  }
}
```

### How skills work

1. **Discovery** — Skills are scanned at session start. Only metadata (name, description) is loaded.
2. **Matching** — When the agent sees a task matching a skill description, it loads the full SKILL.md.
3. **Execution** — The agent follows the skill's instructions using its available tools.

Skills can bundle scripts, templates, and reference docs alongside SKILL.md:

```
my-skill/
├── SKILL.md          # Required
├── scripts/          # Executable code the agent can run
├── references/       # Docs the agent can read
└── assets/           # Templates, configs
```

### Frontmatter fields

| Field | Required | Max | Description |
|---|---|---|---|
| `name` | Yes | 64 chars | Must match directory name. Lowercase, numbers, hyphens. |
| `description` | Yes | 1024 chars | What the skill does. This is what the agent reads to decide whether to use it. |
| `license` | No | — | License name or file reference |
| `metadata` | No | — | Key-value pairs (author, version, etc.) |

### Verifying a skill loaded

```
You: "What skills do you have available?"
You: "Do you have access to the api-design skill?"
```

Look for `skill` tool invocations in the conversation to confirm usage.

### Key gotcha

**Description wording matters.** The agent matches tasks to skills by reading descriptions. A vague description = the skill never triggers. Be specific about when the skill should be used.

---

## MCP (Model Context Protocol)

MCP connects Kilo to external tools — databases, APIs, browsers, file systems, custom services. It's how Kilo becomes more than a text generator.

### Configuration

```jsonc
// ~/.config/kilo/kilo.json (global) or ./kilo.json (project)
{
  "mcp": {
    "postgres": {
      "type": "local",
      "command": ["npx", "-y", "@pgedge/mcp-server-postgres"],
      "environment": {
        "DATABASE_URL": "{env:DATABASE_URL}"
      }
    },
    "context7": {
      "type": "remote",
      "url": "https://mcp.context7.com/mcp",
      "headers": {
        "Authorization": "Bearer {env:CONTEXT7_API_KEY}"
      }
    }
  }
}
```

### Transport types

| Type | Config | Use case |
|---|---|---|
| **Local (stdio)** | `"type": "local", "command": [...]` | Tools running on your machine — Postgres, filesystem, Playwright |
| **Remote (HTTP)** | `"type": "remote", "url": "..."` | Cloud services — Context7, Figma, custom APIs |

### Managing MCP servers

```bash
# List configured servers
kilo mcp list

# Add a server interactively
kilo mcp add

# Set up authentication
kilo mcp auth

# Toggle in interactive session
/mcps
```

### MCP tool permissions

MCP tools follow the same Allow/Ask/Deny model as built-in tools:

```jsonc
{
  "permission": {
    "postgres_query": "ask",       // Prompt before SQL execution
    "postgres_*": "allow",         // Auto-approve all postgres tools
    "playwright_navigate": "deny"  // Block navigation
  }
}
```

Permission keys use the format `{servername}_{toolname}`.

### Useful MCP servers

| Server | What it gives Kilo | Use case |
|---|---|---|
| **pgEdge Postgres** | Read/write SQL against PostgreSQL | ETL, data cleaning, natural-language queries |
| **Playwright** | Control headless browser, navigate DOMs | Web scraping, form automation, UI testing |
| **Context7** | Documentation search across libraries | Research, API lookups |
| **Sequential Thinking** | Forced reflective reasoning loops | Deep research, reducing hallucinations |
| **Memory** | Persistent knowledge graph | Long-term context, entity extraction |
| **Filesystem** | Sandboxed file access | Safe file operations outside project |
| **Figma Desktop** | Read Figma design files | Design review, accessibility audits |

### Warning

> MCP servers add tokens to every request. Enable only what you need. Too many servers = context overflow.

---

## Workflows (Custom Commands)

Workflows are reusable prompt templates triggered by `/command-name` in chat.

### Creating a workflow

```
# Global (all projects)
~/.config/kilo/commands/submit-pr.md

# Project-specific
.kilo/commands/deploy-check.md
```

### Format

```markdown
---
description: Submit a pull request with full checks
agent: code
model: kilo/anthropic/claude-sonnet-4.6
subtask: true
---

# Submit PR Workflow

1. Use `grep` to check for TODOs and console.log statements
2. Run `bash` with `npm test`
3. Stage and commit with descriptive messages
4. Push and create PR via `bash` with `gh pr create`
```

### Frontmatter options

| Field | Description |
|---|---|
| `description` | Shown in command picker |
| `agent` | Which agent executes (code, ask, debug, etc.) |
| `model` | Model override for this workflow |
| `subtask` | `true` = runs as isolated sub-agent session |

### Invoking

```
/submit-pr
/deploy-check
```

Type `/` in chat to see all available commands.

---

## Autonomous Mode

Run Kilo without human interaction — for CI/CD, cron jobs, batch processing.

```bash
# Basic autonomous run
kilo run --auto "Refactor all Python files to use type hints"

# With JSON output for parsing
kilo run --auto --format json "Extract data from reports/*.pdf"

# With file attachment
kilo run --auto --file data.csv "Normalize this CSV and output as JSON"

# With specific model and timeout
kilo run --auto -m kilo/google/gemini-3-flash-preview "Generate test cases for src/auth.py"
```

### Exit codes

| Code | Meaning |
|---|---|
| `0` | Task completed successfully |
| `124` | Timeout |
| `1` | Error |

### Permission config for autonomous mode

```jsonc
// opencode.json — auto-approve tools for headless execution
{
  "permission": {
    "bash": {
      "*": "allow",
      "rm *": "deny",
      "sudo *": "deny"
    },
    "edit": "allow",
    "read": "allow",
    "glob": "allow",
    "grep": "allow"
  }
}
```

### CI/CD integration

```yaml
# GitHub Actions
- name: AI Code Review
  run: |
    kilo run --auto --format json "Review the changes in this PR for security issues" \
      --file <(git diff origin/main)
    echo "Exit code: $?"
```

---

## Serve Mode (Headless API)

Run Kilo as a persistent HTTP server. Any application can call it.

```bash
# Start server
kilo serve --port 4096

# With authentication
OPENCODE_SERVER_PASSWORD=secret kilo serve --port 4096

# With mDNS discovery
kilo serve --mdns --mdns-domain my-kilo.local

# Open web interface
kilo web
```

### Key endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/global/health` | Health check |
| POST | `/session` | Create session |
| POST | `/session/:id/message` | Send message |
| GET | `/session/:id/event` | SSE stream |
| POST | `/session/:id/abort` | Abort generation |
| GET | `/doc` | OpenAPI 3.1 spec |

### Connecting from another terminal

```bash
kilo attach http://localhost:4096
kilo run --attach http://localhost:4096 "Fix the bug"
```

### Python client

```python
import httpx

BASE = "http://localhost:4096"
session = httpx.post(f"{BASE}/session").json()
sid = session["id"]

resp = httpx.post(f"{BASE}/session/{sid}/message", json={
    "model": "kilo/google/gemini-3-flash-preview",
    "agent": "ask",
    "parts": [{"type": "text", "text": "Analyze this data..."}]
})
```

---

## Sessions

Sessions give Kilo memory across messages.

```bash
# Resume last session
kilo --continue
kilo -c

# Fork a session (branch from a point)
kilo run --session ses_abc123 --fork "Try a different approach"

# Export / import
kilo export ses_abc123 > session.json
kilo import session.json
```

### In-session commands

| Command | What it does |
|---|---|
| `/sessions` | Switch between sessions |
| `/new` | Start fresh |
| `/timeline` | Jump to specific message |
| `/fork` | Branch from current point |
| `/compact` | Summarize and compress context |
| `/share` / `/unshare` | Control visibility |
| `/export` | Save transcript |

---

## Local Code Reviews

Built-in review commands — no scripts needed:

```bash
# Review current branch vs base
/local-review

# Review uncommitted changes (staged + unstaged)
/local-review-uncommitted
```

For the full cost-aware review pipeline with escalation, see [KILO_REVIEW_GUIDE.md](KILO_REVIEW_GUIDE.md).

---

## Remote Connections

Let Cloud Agents web UI control your local CLI session:

```bash
# Toggle remote mode in session
/remote

# Enable by default
# Add to ~/.config/kilo/kilo.json:
# { "remote_control": true }
```

Requires Kilo Gateway connection. Same account on CLI and Cloud Agent.

---

## Fabrik Integration Patterns

How fabrik uses Kilo CLI programmatically:

| Pattern | Script | What it does |
|---|---|---|
| **Auto-route by ticket** | `kilo_auto_route.py` | Classify ticket → pick model → `kilo run --auto` |
| **Dispatch to specific agent** | `kilo_dispatch.py` | Build prompt with AGENTS-compact.md + rules → execute |
| **Code review pipeline** | `kilo_code_review.py` | Risk-based routing, liveness monitoring, JSONL parsing |
| **Q&A with session** | `kilo_consult.py` | File-scoped questions with session continuity |
| **Doc enforcement** | `kilo_docs_enforcer.py` | Detect doc gaps from git diff → auto-generate |
| **Kilo as MCP tool** | `mcp_kilo_server.py` | Expose Kilo agents as MCP tools for Traycer |
| **Cost reporting** | `kilo_cost_report.py` | Usage analysis by model and file type |

---

## See Also

- [KILO_CLI_REFERENCE.md](KILO_CLI_REFERENCE.md) — Complete command reference + programmatic integration patterns
- [KILO_REVIEW_GUIDE.md](KILO_REVIEW_GUIDE.md) — Cost-aware code review pipeline
- [KILO_MODEL_SELECTION.md](KILO_MODEL_SELECTION.md) — Model selection strategies
- [KILO_USE_CASES.md](KILO_USE_CASES.md) — 11 non-coding use case domains with economics
- [KILO_MODEL_CAPABILITIES.md](KILO_MODEL_CAPABILITIES.md) — Full model catalog (auto-generated)
- [KILO_AGENT_SELECTION_GUIDE.md](KILO_AGENT_SELECTION_GUIDE.md) — DB-driven agent selection
