# Windsurf Features Guide

**Last Updated:** 2026-05-21

All Windsurf IDE features beyond Cascade chat. For Cascade itself, see [cascade-guide.md](cascade-guide.md).

---

## Tab (Autocomplete)

AI-powered code completion that goes beyond snippets.

| Feature | What it does |
|---|---|
| **Autocomplete** | Generates code as you type — single keystroke to accept |
| **Supercomplete** | Predicts your next action, not just the next code token |
| **Tab to Jump** | Predicts where your cursor should go next — Tab navigates to it |

All three work together: type → Supercomplete suggests → Tab accepts and jumps to next logical position.

**Credits:** Free — does NOT consume premium credits.

---

## Command (Cmd/Ctrl + I)

In-line code generation and edits via natural language. **Does NOT consume premium credits.**

| Shortcut | Action |
|---|---|
| `Cmd/Ctrl + I` | Invoke Command at cursor |
| `Cmd/Ctrl + Enter` | Accept generation |
| `Cmd/Ctrl + Delete` | Reject generation |

**Behavior:**
- No selection → generates new code at cursor
- Code highlighted → edits the selected lines
- Works in terminal too — generates CLI syntax from natural language

**Model:** Windsurf Fast (optimized for file-scoped edits).

---

## Editor Code Lenses

Shortcuts at top of functions/classes:

| Lens | Action | Uses |
|---|---|---|
| **Explain** | Explains what the code does | Cascade |
| **Refactor** | Dropdown of refactoring options | Command |
| **Docstring** | Generates docstring | Command |

---

## Terminal Features

| Feature | How |
|---|---|
| **Command in Terminal** | `Cmd/Ctrl + I` → natural language to CLI syntax |
| **Send to Cascade** | Highlight stack trace → `Cmd/Ctrl + L` → sends to Cascade |
| **@terminal mention** | Chat with Cascade about active terminal output |
| **Dedicated terminal** | Cascade uses separate zsh terminal (uses your `.zshrc`) |

### Auto-Execute Modes

| Mode | Behavior |
|---|---|
| **Default** | Asks permission for each command |
| **Auto** | Cascade decides based on risk (premium models only) |
| **Turbo** | Always executes unless in deny list |

Configure allow/deny lists via `windsurf.cascadeCommandsAllowList` / `windsurf.cascadeCommandsDenyList`.

**Fabrik:** Turbo mode enabled — all commands execute without prompt (except deny list).

---

## Devin Integration (2026)

Devin cloud agent runs directly inside Windsurf. Included with every self-serve plan.

| Feature | What it does |
|---|---|
| **Devin delegate** | One-click delegation from local Cascade session to Devin (runs on its own VM) |
| **Devin Review** | AI code review on PRs — available for all self-serve users |
| **Quick Review** | Faster lightweight review |
| **Devin Terminal** | CLI agent available to all Windsurf users |

Devin handles: debugging, testing, deployment, refactoring — tasks that benefit from autonomous cloud execution.

---

## Agent Command Center (2026)

Kanban-style dashboard to manage all agent sessions — local Cascade and cloud Devin.

- View all sessions organized by status
- Group sessions into **Spaces** (bundle agent sessions, PRs, files, and shared context around a single task)
- Track progress across multiple parallel agents

---

## Adaptive Model (2026)

Auto-selects the best model for each task from the model picker. Helps quota last longer by avoiding premium models on simple tasks.

Alternative to manually switching between Sonnet/Opus/Flash.

---

## Windsurf Previews

View local deployment of your app in the IDE with hot reload.

- Ask Cascade to "preview your site" or click Web icon in toolbar
- Click **"Send element"** → select UI element → appears as `@mention` in Cascade
- Optimized for Chrome/Arc/Chromium browsers

---

## AI Commit Messages

Generate git commit messages with one click. **Available to all paid users with no limits.**

1. Stage files in Git panel
2. Click **sparkle (✨) icon** next to commit message field
3. Review/edit → commit

---

## DeepWiki

Detailed explanations of code symbols — better than basic hover cards.

| Action | How |
|---|---|
| Open DeepWiki | `Cmd/Ctrl + Shift + Click` on symbol |
| Send to Cascade | Click `⋮` → "Add to Cascade" |

---

## Codemaps (Beta)

Hierarchical maps showing execution order and component relationships.

- Maps how everything works together
- Click any node → jump to that file/function
- `@mention` a Codemap to include as context in Cascade
- Share as links (Teams/Enterprise: requires opt-in)

Access: Activity Bar or Command Palette → "Focus on Codemaps View"

---

## Web and Docs Search

Cascade browses the internet — search, evaluate, skim, read relevant chunks.

| Method | When to use |
|---|---|
| **Natural question** | "What's new in React 19?" — auto-detects need |
| **@web** | Force web search |
| **@docs** | Query supported documentation (high quality) |
| **Paste URL** | Direct page read (skips search) |

**Credits:** Typical task: 3-6 credits (search + read + generate).

**Optimize:** Be specific → fewer chunks read. Prefer URLs when you know the source.

---

## App Deploys (Beta)

Deploy web apps directly from Cascade to public URLs.

- Deploy to **Netlify** → URL: `<SUBDOMAIN>.windsurf.build`
- Supported: Next.js, React, Vue, Svelte, static HTML
- Rate limits: Free 1/day, Pro 10/day

| Plan | Deploys/day | Max unclaimed |
|---|---|---|
| Free | 1 | 1 |
| Pro | 10 | 5 |

**Fabrik note:** For production, use `fabrik apply` (SSH + Docker Compose) on the VPS — Coolify was decommissioned 2026-05-30. App Deploys for quick previews/demos only.

---

## Vibe and Replace

AI-powered find and replace — search for text matches, apply an AI prompt to each replacement.

| Mode | Description |
|---|---|
| **Smart** | Slower model, more careful |
| **Fast** | Faster model, quick changes |

---

## MCP (Model Context Protocol)

Connect Cascade to external tools — databases, APIs, browsers.

Config: `~/.codeium/windsurf/mcp_config.json` — max 100 tools across all servers.

See [cascade-guide.md](cascade-guide.md#mcp-model-context-protocol) for full configuration details.

---

## Memories, Rules & Workflows

- **Memories:** Auto-generated context Cascade remembers across conversations
- **Rules:** User-defined instructions in `.windsurf/rules/**/*.md` with trigger modes (always_on, glob, model_decision, manual)
- **Workflows:** Reusable agentic recipes in `.windsurf/workflows/*.md`

See [cascade-guide.md](cascade-guide.md#memories--rules) for full details.

---

## SSH Support

Windsurf's own SSH implementation (not Microsoft's).

- Command Palette → **Remote-SSH** or click **Open a Remote Window** (bottom left)
- **Linux remote hosts only**
- Don't install Microsoft "Remote - SSH" extension (conflicts)

---

## Dev Containers

Supports Development Containers on Mac, Windows, Linux (local and remote via SSH).

| Command | Description |
|---|---|
| `Dev Containers: Open Folder in Container` | Open with devcontainer.json |
| `Dev Containers: Reopen in Container` | Reopen current workspace in container |
| `Dev Containers: Attach to Running Container` | Attach to existing Docker container |

Requires: Docker installed (local) or Docker on remote host (SSH).

---

## WSL Support

Windows Subsystem for Linux — click **Open a Remote Window** or Command Palette → **Remote-WSL**.

**Fabrik:** All development happens in WSL Ubuntu 24.04.

---

## Windsurf Pyright

Fast, Pylance-like Python language server. **Already installed in Fabrik.**

---

## Advanced Settings

Access: **Windsurf Settings** (top right dropdown or `Cmd/Ctrl + Shift + P` → "Open Windsurf Settings Page")

- **Cascade Gitignore Access:** Allow/deny access to .gitignore'd files (default: off)
- **Custom App Icons:** Mac only, beta (paying users)
- **Settings Tab:** Opens in dedicated tab with searchable sidebar (2026 update)

---

## Quick Reference

| Feature | Shortcut | Credits |
|---|---|---|
| **Tab / Supercomplete** | Type → Tab to accept | Free |
| **Command** | `Cmd/Ctrl + I` | Free |
| **Accept** | `Cmd/Ctrl + Enter` | — |
| **Reject** | `Cmd/Ctrl + Delete` | — |
| **Send to Cascade** | `Cmd/Ctrl + L` | — |
| **Cascade Chat** | `Cmd/Ctrl + Shift + L` | Model-dependent |
| **DeepWiki** | `Cmd/Ctrl + Shift + Click` | — |
| **AI Commit** | Click ✨ in Git panel | Paid users |
| **Vibe and Replace** | Find/Replace panel | — |

---

## See Also

- [Cascade Guide](cascade-guide.md) — Cascade features, memories, rules, MCP, workflows
- [Cascade Models](cascade-models.md) — model selection and credits
- [Windsurf Changelog](https://windsurf.com/changelog) — latest updates
- [Windsurf Docs](https://docs.windsurf.com) — official documentation
