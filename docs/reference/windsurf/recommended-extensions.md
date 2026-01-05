# Windsurf Recommended Extensions

**Last Updated:** 2026-01-05

Curated list of extensions for Fabrik development workflow.

---

## Currently Installed

### Core Development

| Extension | Publisher | Purpose |
|-----------|-----------|---------|
| `ms-python.python` | Microsoft | Core Python support: IntelliSense, linting, debugging |
| `ms-python.debugpy` | Microsoft | Python debugging with breakpoints |
| `ms-python.vscode-python-envs` | Microsoft | Virtual environment management |
| `codeium.windsurfpyright` | Codeium | Fast Pylance-like type checking |

### Docker & Containers

| Extension | Publisher | Purpose |
|-----------|-----------|---------|
| `ms-azuretools.vscode-docker` | Microsoft | Docker file editing, image management |
| `ms-azuretools.vscode-containers` | Microsoft | Dev containers support |

### Git & GitHub

| Extension | Publisher | Purpose |
|-----------|-----------|---------|
| `github.vscode-github-actions` | GitHub | GitHub Actions workflow editing |
| `eamodio.gitlens` | GitKraken | Git blame, history, authorship visualization |
| `github.vscode-pull-request-github` | GitHub | PR review directly in IDE |

### Code Quality

| Extension | Publisher | Purpose |
|-----------|-----------|---------|
| `davidanson.vscode-markdownlint` | David Anson | Markdown linting |
| `charliermarsh.ruff` | Charlie Marsh | Python linter and formatter |
| `esbenp.prettier-vscode` | Prettier | JavaScript/TypeScript formatter |

### Web Development

| Extension | Publisher | Purpose |
|-----------|-----------|---------|
| `bradlc.vscode-tailwindcss` | Brad Cornes | Tailwind CSS IntelliSense |
| `redhat.vscode-yaml` | Red Hat | YAML language support |

### AI & Automation

| Extension | Publisher | Purpose |
|-----------|-----------|---------|
| `factory.factory-vscode-extension` | Factory | Factory.ai / droid exec integration |
| `traycer.traycer-vscode` | Traycer | Traycer AI assistant |
| `anthropic.claude-code` | Anthropic | Claude AI integration |

### Build Tools

| Extension | Publisher | Purpose |
|-----------|-----------|---------|
| `ms-vscode.makefile-tools` | Microsoft | Makefile support |

---

## Windsurf Official Recommendations

From [Windsurf Docs - Recommended Extensions](https://docs.windsurf.com):

### General

| Extension | Purpose | Fabrik Status |
|-----------|---------|---------------|
| GitLens | Code authorship visualization | ✅ Installed |
| GitHub Pull Requests | PR management in IDE | ✅ Installed |
| GitLab Workflow | GitLab integration | ⬜ Not needed |
| Mermaid Markdown Preview | Diagram rendering | ✅ Installed |
| Visual Studio Keybindings | VS keyboard shortcuts | ⬜ Personal pref |
| Eclipse Keymap | Eclipse shortcuts | ⬜ Personal pref |

### Python

| Extension | Purpose | Fabrik Status |
|-----------|---------|---------------|
| ms-python.python | Core Python | ✅ Installed |
| Windsurf Pyright | Type checking | ✅ Installed |
| Ruff | Linter/formatter | ✅ Installed |
| Python Debugger | Debugging | ✅ Installed |

### Java / Visual Basic / C#

Not applicable to Fabrik stack.

---

## Installation Commands

Install all recommended extensions via command palette (`Ctrl+Shift+P`):

```
Extensions: Install Extension
```

Or search by extension ID:

```
eamodio.gitlens
github.vscode-pull-request-github
charliermarsh.ruff
esbenp.prettier-vscode
bradlc.vscode-tailwindcss
redhat.vscode-yaml
```

---

## Cascade Benefits

Extensions that improve Cascade AI context:

| Extension | How It Helps Cascade |
|-----------|---------------------|
| **GitLens** | Cascade sees git blame, understands code history |
| **GitHub PRs** | Cascade can help review PRs with full context |
| **Ruff** | Shows lint errors Cascade can auto-fix |
| **YAML** | Better parsing of compose.yaml, config files |
| **Prettier** | Cleaner code = better context for Cascade |

---

## Settings Recommendations

Add to Windsurf settings.json for optimal experience:

```json
{
  // Format on save
  "editor.formatOnSave": true,
  "editor.defaultFormatter": "esbenp.prettier-vscode",

  // Python-specific formatter
  "[python]": {
    "editor.defaultFormatter": "charliermarsh.ruff"
  },

  // GitLens settings
  "gitlens.codeLens.enabled": true,
  "gitlens.currentLine.enabled": true,

  // Tailwind
  "tailwindCSS.includeLanguages": {
    "typescript": "javascript",
    "typescriptreact": "javascript"
  }
}
```

---

## See Also

- [Windsurf Documentation](https://docs.windsurf.com)
- [Open VSX Registry](https://open-vsx.org)
- [Factory.ai Integration](../droid-exec-usage.md)
