# Windsurf Features Guide

**Last Updated:** 2026-01-05

Core features of Windsurf IDE beyond Cascade chat.

---

## Command (Cmd/Ctrl + I)

In-line code generation and edits via natural language. **Does NOT consume premium credits.**

### Usage

| Shortcut | Action |
|----------|--------|
| `Cmd/Ctrl + I` | Invoke Command at cursor |
| `Cmd/Ctrl + Enter` | Submit prompt / Accept generation |
| `Cmd/Ctrl + Delete` | Reject generation |

### Behavior

- **No selection** → Generates new code at cursor position
- **Code highlighted** → Edits the selected lines

### Models

Command uses its own optimized models:
- **Windsurf Fast** - Fastest, most accurate for file-scoped edits

### Best Practices

1. **Simple prompts work** - "Fix this", "Refactor" leverage Windsurf's context awareness
2. **Specific prompts help** - "Write a function that takes two inputs of type Diffable and implements the Myers diff algorithm"
3. **Highlight for edits** - Select code before invoking to edit rather than generate

---

## Editor Code Lenses

Shortcuts at top of functions/classes:

| Lens | Action | Invokes |
|------|--------|---------|
| **Explain** | Explains what the code does | Cascade |
| **Refactor** | Dropdown of refactoring options | Command |
| **Docstring** | Generates docstring | Command |

### Docstring Behavior

- Python: Generates docstring correctly under function header
- Other languages: Above function header

---

## Terminal Features

### Command in Terminal

`Cmd/Ctrl + I` in terminal generates CLI syntax from natural language prompts.

### Send to Cascade

Highlight stack trace → `Cmd/Ctrl + L` → Sends selection to Cascade for debugging.

### @-mention Terminal

Chat with Cascade about your active terminals using `@terminal`.

---

## Auto-Execute Terminal Commands

Cascade can run terminal commands with permission. Configure auto-execution:

### Modes

| Mode | Behavior |
|------|----------|
| **Default** | Asks permission for each command |
| **Auto** | Cascade decides based on command risk (premium models only) |
| **Turbo** | Always executes unless in deny list |

Toggle via: **Windsurf Settings** (bottom right corner)

### Allow List

Commands that always auto-execute.

**Setting:** `windsurf.cascadeCommandsAllowList`

Example: Add `git` → `git add -A` always runs without prompt.

### Deny List

Commands that never auto-execute.

**Setting:** `windsurf.cascadeCommandsDenyList`

Example: Add `rm` → `rm index.py` always asks permission.

---

## Dedicated Terminal (Wave 13+)

Cascade uses a dedicated terminal separate from your default, always using `zsh`.

### Configuration

- Uses your `.zshrc` configuration
- Aliases and environment variables available

### Shared Config with Other Shells

If using bash/fish/etc., create a shared config file both shells can source:

```bash
# ~/.shell_common
export PATH="$HOME/.local/bin:$PATH"
export FABRIK_ROOT="/opt/fabrik"
```

Then in `.bashrc` and `.zshrc`:
```bash
source ~/.shell_common
```

### Troubleshooting

If issues with dedicated terminal:
1. Enable **Legacy Terminal Profile** in Windsurf settings

---

## Windsurf Previews

View local deployment of your app in IDE or browser with listeners for rapid iteration.

### Usage

- Ask Cascade to "preview your site"
- Or click **Web icon** in Cascade toolbar

### Send Elements to Cascade

1. Click **"Send element"** button (bottom right of Preview)
2. Select element in the preview
3. Element appears as `@mention` in Cascade prompt
4. Add multiple elements to same prompt

### Browser Support

Optimized for: **Chrome, Arc, Chromium-based browsers**

### Disable

Windsurf Settings → Disable Windsurf Previews

---

## AI Commit Messages

Generate git commit messages with one click. **Available to all paid users with no limits.**

### Usage

1. Stage files in Git panel
2. Click **sparkle (✨) icon** next to commit message field
3. Review/edit generated message
4. Complete commit

### Best Practices

- Group small, meaningful units of changes
- Review message before committing

### Privacy

Code and commit messages remain private. Not stored or used for training.

---

## DeepWiki

Get detailed explanations of code symbols - better than basic hover cards.

### Usage

| Action | How |
|--------|-----|
| Open DeepWiki | `Cmd/Ctrl + Shift + Click` on symbol |
| Send to Cascade | Click `⋮` → "Add to Cascade" |

### Location

Found in **Primary Side Bar / Activity Bar**

---

## Codemaps (Beta)

Hierarchical maps for codebase understanding. Shows execution order and component relationships.

### What It Does

- Maps how everything works together
- Shows execution order of code/files
- Shows component relationships
- Click any node → jump to that file/function

### Access

| Method | How |
|--------|-----|
| Activity Bar | Left side panel |
| Command Palette | `Cmd/Ctrl + Shift + P` → "Focus on Codemaps View" |

### Creating a Codemap

1. Open Codemaps panel
2. Select suggested topic OR type custom prompt
3. Or generate from bottom of Cascade conversation

### Sharing

- Share as links viewable in browser
- Enterprise: Requires opt-in (stored on servers)
- Team Codemaps require authentication to view

### Use with Cascade

`@mention` a Codemap to include as context in conversations.

---

## Quick Reference

| Feature | Shortcut | Credits |
|---------|----------|---------|
| **Command** | `Cmd/Ctrl + I` | Free |
| **Accept** | `Cmd/Ctrl + Enter` | - |
| **Reject** | `Cmd/Ctrl + Delete` | - |
| **Send to Cascade** | `Cmd/Ctrl + L` | - |
| **Cascade Chat** | `Cmd/Ctrl + Shift + L` | Model-dependent |
| **DeepWiki** | `Cmd/Ctrl + Shift + Click` | - |
| **AI Commit** | Click ✨ in Git panel | Paid users |

---

## See Also

- [Cascade Models](cascade-models.md)
- [Recommended Extensions](recommended-extensions.md)
- [Windsurf Overview](overview.md)
