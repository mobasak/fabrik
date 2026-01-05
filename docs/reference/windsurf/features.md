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

### Fabrik Recommended Lists

**Allow:**
```
git
npm
pip
python
pytest
docker compose
ls
cat
```

**Deny:**
```
rm -rf
sudo
dd
mkfs
shutdown
```

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

## Quick Reference

| Feature | Shortcut | Credits |
|---------|----------|---------|
| **Command** | `Cmd/Ctrl + I` | Free |
| **Accept** | `Cmd/Ctrl + Enter` | - |
| **Reject** | `Cmd/Ctrl + Delete` | - |
| **Send to Cascade** | `Cmd/Ctrl + L` | - |
| **Cascade Chat** | `Cmd/Ctrl + Shift + L` | Model-dependent |

---

## See Also

- [Cascade Models](cascade-models.md)
- [Recommended Extensions](recommended-extensions.md)
- [Windsurf Overview](overview.md)
