# Cascade Guide

**Last Updated:** 2026-01-05

Comprehensive guide to Windsurf's Cascade AI assistant.

---

## Opening Cascade

- `Cmd/Ctrl + L` or click Cascade icon (top right)
- Selected text in editor/terminal automatically included

---

## Modes

| Mode | Purpose |
|------|---------|
| **Code** | Creates and modifies codebase |
| **Chat** | Questions about code, general coding principles |

Chat mode can propose code you can accept and insert.

---

## Plans and Todo Lists

Cascade has built-in planning for longer tasks:

- Specialized planning agent refines long-term plan in background
- Selected model handles short-term actions
- Creates Todo list within conversation
- Ask Cascade to update the plan as needed
- Plan auto-updates when new information (like Memories) is discovered

---

## Queued Messages

While Cascade is working, you can queue additional messages:

1. Type message while Cascade is busy
2. Press Enter to queue
3. **Send immediately:** Press Enter again on empty box
4. **Delete:** Remove message from queue before sent

---

## Tool Calling

Cascade has access to: Search, Analyze, Web Search, MCP, Terminal

### Limits

- **20 tool calls per prompt**
- If stops, press **Continue** to resume
- Each continue = new prompt credit

### Auto-Continue

Configure to automatically continue if limit hit (consumes credits).

---

## Voice Input

Use voice to interact - transcribes speech to text.

---

## Named Checkpoints and Reverts

### Revert Changes

1. Hover over original prompt
2. Click revert arrow (right side)
3. Or revert from table of contents

⚠️ **Reverts are irreversible!**

### Named Checkpoints

Create named snapshots of current project state from within conversation.

---

## Real-time Awareness

Cascade is aware of your real-time actions - no need to re-explain context.

Just say "Continue" to pick up where you left off.

---

## Send Problems to Cascade

Problems panel (bottom of editor) → Click **"Send to Cascade"** → Adds as @mention

---

## Explain and Fix

Highlight error in editor → Click **"Explain and Fix"** → Cascade fixes it

---

## Ignoring Files (.codeiumignore)

Prevent Cascade from viewing, editing, or creating certain files.

### Project-Level

Create `.codeiumignore` at workspace root (same format as `.gitignore`):

```
# Example .codeiumignore
.env
secrets/
*.key
node_modules/
```

### Global (Enterprise)

Place global `.codeiumignore` in `~/.codeium/` - applies to all workspaces.

---

## Linter Integration

Cascade auto-fixes linting errors on generated code.

- **Default:** On
- **Disable:** Click "Auto-fix" on tool call → "Disable"
- **Free:** Lint fixes don't consume credits

---

## Sharing Conversations

**Teams/Enterprise only** (not Hybrid)

Click `...` → "Share Conversation"

---

## @-mention Previous Conversations

Reference previous conversations via `@mention`:

- Retrieves relevant summaries and checkpoints
- Queries specific parts of conversation
- Does NOT retrieve full conversation (avoids context overflow)

---

## Simultaneous Cascades

Run multiple Cascades at once:

- Navigate via dropdown (top left of panel)
- ⚠️ If two edit same file simultaneously, second edit may fail

---

## Quick Links

| Feature | Description |
|---------|-------------|
| [Web Search](features.md) | Search web for references |
| [Memories & Rules](features.md) | Customize behavior |
| [MCP](features.md) | Extend capabilities |
| [Terminal](features.md#terminal-features) | Upgraded terminal |
| [Workflows](features.md) | Automate trajectories |
| [App Deploys](features.md) | One-click deploy |

---

## Fabrik Notes

### Turbo Mode

**Status:** ✅ Enabled

All commands execute without permission prompts (except deny list).

### .codeiumignore

**Status:** Not used - Cascade has full read/write access to all files.

---

## See Also

- [Cascade Models](cascade-models.md)
- [Features Guide](features.md)
- [Recommended Extensions](recommended-extensions.md)
