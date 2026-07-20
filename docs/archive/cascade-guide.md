# Cascade Guide

**Last Updated:** 2026-05-21

Comprehensive guide to Windsurf's Cascade AI assistant — the agentic pane that edits code, calls tools, and manages multi-step workflows.

---

## What Cascade Is

An agentic AI that lives next to the editor. It can:
- Edit multiple files in one run
- Call tools (MCP servers, shell, web search)
- Stage edits as a reviewable diff with per-step approval
- Show plan preview before execution
- Break complex tasks into multi-step reasoning chains (Flows)

Each Flow step is explainable, reversible, and transparent.

---

## Opening Cascade

- `Cmd/Ctrl + L` or click Cascade icon (top right)
- Selected text in editor/terminal automatically included as context

---

## Modes

| Mode | Purpose | Tool access |
|------|---------|-------------|
| **Code** | Creates and modifies codebase | Full — file edit, terminal, MCP, web search |
| **Chat** | Questions about code, general coding | Read-only — proposes code you can accept |

---

## Memories & Rules

Two mechanisms for persistent context across conversations:

### Memories (auto-generated)

Cascade creates memories automatically when it encounters useful context. You can also prompt "create a memory of...".

- **Storage:** `~/.codeium/windsurf/memories/` (local, workspace-scoped)
- **Not committed** to repository, not shared with team
- **Free** — no credit consumption
- **Reliability:** For durable, team-shared knowledge, use Rules instead

### Rules (user-defined)

| Scope | Location | Activation | Limit |
|---|---|---|---|
| **Global** | `~/.codeium/windsurf/memories/global_rules.md` | Always active, all workspaces | 6,000 chars |
| **Workspace** | `.windsurf/rules/**/*.md` | Per-file trigger (see below) | 12,000 chars/file |
| **AGENTS.md** | Any directory | Root = always-on; subdirectory = auto-glob | No limit |
| **System (Enterprise)** | `/etc/windsurf/rules/*.md` (Linux/WSL) | Always active, IT-managed, read-only | — |

### Workspace Rule Frontmatter

```markdown
---
trigger: always_on|model_decision|glob|manual
globs: ["**/*.test.ts", "**/auth/**"]
---
Rule content here...
```

### Trigger Modes

| Trigger | When loaded | Context cost |
|---|---|---|
| `always_on` | Every message — full content in system prompt | High |
| `model_decision` | Description shown always; full content on relevance | Low until triggered |
| `glob` | When matching files are edited/read | Matching files only |
| `manual` | Via `@rule-name` mention in chat | On-demand |

### Fabrik Convention

- `.windsurf/rules/` contains numbered rule packs (10-python, 25-data-postgres, 30-ops, etc.)
- Most use `glob` trigger — loaded only when relevant files are touched
- `.windsurfrules` file at project root = legacy single-file format (still supported)
- `AGENTS.md` at root = always-on cross-executor instructions (Cascade, Kilo, Traycer)

**Best practice for rules:** Keep concise, use bullet points, avoid vague statements. Use XML tags to group related guidelines.

---

## Plans and Todo Lists

Cascade has built-in planning for complex tasks:

- Background planning agent refines long-term plan
- Selected model handles short-term actions
- Creates Todo list within conversation
- Plan auto-updates when new information (like Memories) is discovered
- Ask Cascade to update the plan as needed

---

## Tool Calling

Cascade has access to: **Search, Analyze, Web Search, MCP servers, Terminal**

### Limits

- **20 tool calls per prompt** (mainstream), **100 MCP tools max** connected at once
- If stops, press **Continue** to resume
- Each continue = new prompt credit

### Auto-Continue

Configure to automatically continue if tool call limit hit (consumes credits).

---

## MCP (Model Context Protocol)

Extends Cascade with external tools — databases, APIs, browsers, custom services.

### Configuration

File: `~/.codeium/windsurf/mcp_config.json`

```json
{
  "mcpServers": {
    "postgres": {
      "command": "npx",
      "args": ["-y", "@pgedge/mcp-server-postgres"],
      "env": {
        "DATABASE_URL": "${env:DATABASE_URL}"
      }
    },
    "github": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"],
      "env": {
        "GITHUB_PERSONAL_ACCESS_TOKEN": "${env:GITHUB_TOKEN}"
      }
    }
  }
}
```

### Variable Interpolation

- `${env:VAR_NAME}` — environment variable
- `${file:/path/to/file}` — file contents (tilde paths supported)

### Transport Types

| Type | Config | Use case |
|---|---|---|
| **Stdio** | `"command": "npx", "args": [...]` | Local tools |
| **Streamable HTTP** | `"serverUrl": "https://server/mcp"` | Cloud services |
| **SSE** | Server-Sent Events | Real-time streaming |

### Popular MCP Servers

| Server | Purpose |
|---|---|
| GitHub | Repos, issues, PRs, file operations |
| PostgreSQL | Read-only DB access with schema inspection |
| Filesystem | Sandboxed file operations |
| Brave Search | Web search |
| Memory | Persistent knowledge graph |
| Slack | Channel management, messaging |

### Install Methods

1. **UI:** Click "MCPs" icon in Cascade top-right → browse MCP Marketplace
2. **Deeplink:** `windsurf://windsurf-mcp-registry?serverName=github-mcp-server`
3. **Manual:** Edit `~/.codeium/windsurf/mcp_config.json`

---

## Workflows

Named, reusable agentic recipes — prompt template + tools + scope.

**Four archetypes:** scaffolder, refactor, audit, review.

Stored in `.windsurf/workflows/*.md`. Invoked via Cascade command palette or `@workflow-name`.

Fabrik ships 11 workflows: auto-review, bug-fix, deploy, kilo, local-coder, local-docs, local-fixer, local-review, new-feature, registrar-audit, review.

---

## Checkpoints and Reverts

### Revert Changes

1. Hover over original prompt → click revert arrow
2. Or revert from table of contents

**Reverts are irreversible.**

### Named Checkpoints

Create named snapshots of current project state from within conversation.

---

## Queued Messages

While Cascade is working:

1. Type message → press Enter to queue
2. **Send immediately:** Press Enter again on empty box
3. **Delete:** Remove from queue before sent

---

## Real-time Awareness

Cascade monitors your actions in real-time — file edits, terminal output, cursor position. No need to re-explain context. Say "Continue" to pick up.

---

## Simultaneous Cascades

Run multiple Cascade instances via dropdown (top left of panel).

**Warning:** If two edit the same file simultaneously, the second edit may fail. Use git worktrees for isolation.

---

## Ignoring Files (.codeiumignore)

Prevent Cascade from viewing, editing, or creating certain files:

```
# .codeiumignore at workspace root
.env
secrets/
*.key
node_modules/
```

**Global (Enterprise):** `~/.codeium/.codeiumignore` — applies to all workspaces.

---

## Linter Integration

- Auto-fixes linting errors on generated code
- **Default:** On
- **Free:** Lint fixes don't consume credits
- Disable: Click "Auto-fix" on tool call → "Disable"

---

## Other Features

| Feature | Description |
|---|---|
| **Voice Input** | Transcribes speech to text |
| **Send Problems** | Problems panel → "Send to Cascade" → adds as @mention |
| **Explain and Fix** | Highlight error → "Explain and Fix" |
| **Share Conversations** | Teams/Enterprise only — click `...` → "Share Conversation" |
| **@-mention Conversations** | Reference previous conversations (retrieves summaries, not full text) |
| **App Deploys** | One-click deploy from Cascade |

---

## Fabrik Configuration

### Turbo Mode

**Status:** Enabled. All commands execute without permission prompts (except deny list).

### .codeiumignore

**Status:** Not used — Cascade has full read/write access to all project files.

### Loaded Context Hierarchy

1. `.windsurfrules` (root) — always loaded
2. `.windsurf/rules/**/*.md` — loaded per trigger mode (glob/always_on/model_decision)
3. `AGENTS.md` (root) — always loaded by Cascade
4. `.windsurf/workflows/*.md` — loaded on invocation

---

## See Also

- [Cascade Models](cascade-models.md) — model selection and credits
- [Windsurf Docs](https://docs.windsurf.com/windsurf/cascade) — official documentation
- [MCP Docs](https://docs.windsurf.com/windsurf/cascade/mcp) — MCP server configuration
- [Memories Docs](https://docs.windsurf.com/windsurf/cascade/memories) — rules and memory management
