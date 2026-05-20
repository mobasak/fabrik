# Windsurf Recommended Extensions

**Last Updated:** 2026-05-21

Curated extensions for Fabrik's workflow: Python + TypeScript + Docker + PostgreSQL. No hype, no bloat.

> **Live list:** [actively-used-windsurf-extensions.md](actively-used-windsurf-extensions.md) is auto-generated daily from `windsurf --list-extensions`. This file explains WHY each extension is there.

---

## Essential (do not remove)

### Python Development

| Extension | ID | Why |
|---|---|---|
| **Python** | `ms-python.python` | Core Python: IntelliSense, linting, debugging, venv |
| **Debugpy** | `ms-python.debugpy` | Python debugger with breakpoints |
| **Python Envs** | `ms-python.vscode-python-envs` | Virtual environment management (.venv) |
| **Windsurf Pyright** | `codeium.windsurfpyright` | Fast type checking (Pylance equivalent, Windsurf-native) |
| **Ruff** | `charliermarsh.ruff` | Python linter + formatter — replaces black, isort, flake8 in one tool |

### Docker & Containers

| Extension | ID | Why |
|---|---|---|
| **Docker** | `ms-azuretools.vscode-docker` | Dockerfile editing, image management, compose support |
| **Dev Containers** | `ms-azuretools.vscode-containers` | Open projects inside Docker containers |

### Git & GitHub

| Extension | ID | Why |
|---|---|---|
| **GitLens** | `eamodio.gitlens` | Git blame, file history, authorship — improves Cascade context |
| **GitHub Actions** | `github.vscode-github-actions` | Edit/debug CI workflows |
| **GitHub PRs** | `github.vscode-pull-request-github` | Review PRs directly in IDE |

### Code Quality

| Extension | ID | Why |
|---|---|---|
| **Markdown Lint** | `davidanson.vscode-markdownlint` | Catches broken markdown in docs |
| **Prettier** | `prettier.prettier-vscode` | JS/TS/JSON/CSS/HTML formatter |
| **YAML** | `redhat.vscode-yaml` | YAML IntelliSense — critical for compose.yaml, specs/*.yaml |

### AI Agents (our 3 executors)

| Extension | ID | Why |
|---|---|---|
| **Claude Code** | `anthropic.claude-code` | Claude Code integration (this tool) |
| **Traycer** | `traycer.traycer-vscode` | Spec-to-ticket planning, outer-loop verification |
| **Kilo Code** | `kilocode.kilo-code` | 500+ model gateway, code review, agent orchestration |

---

## Useful (keep installed)

| Extension | ID | Why |
|---|---|---|
| **Tailwind CSS** | `bradlc.vscode-tailwindcss` | IntelliSense for Tailwind classes (SaaS UI projects) |
| **Mermaid Preview** | `bierner.markdown-mermaid` | Render Mermaid diagrams in markdown preview |
| **Mermaid Syntax** | `bpruitt-goddard.mermaid-markdown-syntax-highlighting` | Syntax highlighting for Mermaid code blocks |
| **Makefile Tools** | `ms-vscode.makefile-tools` | Makefile support (used by some projects) |
| **Office Viewer** | `cweijan.vscode-office` | View Excel/PDF/images in IDE (occasional use) |

---

## Review needed (installed but questionable)

These are installed but may not add value. Review periodically:

| Extension | ID | Concern |
|---|---|---|
| **Claude Forever** | `aamiramin.claudeforever` | Third-party Claude wrapper — may conflict with official `anthropic.claude-code` |
| **Claude Automator** | `peterbulyaki.claude-automator` | Third-party automation — unclear benefit alongside Traycer |
| **Claude Manager** | `vishalguptax.claude-manager` | Third-party session manager — unclear benefit |
| **Mermaid Preview (vstirbu)** | `vstirbu.vscode-mermaid-preview` | Third mermaid extension — `bierner.markdown-mermaid` already handles preview |
| **PowerShell** | `ms-vscode.powershell` | We use bash on WSL, not PowerShell |

---

## Not installed (intentionally)

| Extension | Why NOT |
|---|---|
| REST Client / Thunder Client | We test APIs via pytest + scripts, not IDE GUI |
| GitHub Copilot | We use Claude Code + Kilo + Traycer instead |
| Factory | Deprecated — replaced by Kilo Code |
| Remote SSH (Microsoft) | Conflicts with Windsurf's built-in SSH |
| ESLint | Ruff handles Python; Prettier handles JS/TS |
| Any Java/C#/.NET | Not our stack |

---

## How Cascade Benefits from Extensions

| Extension | What it gives Cascade |
|---|---|
| **GitLens** | Git blame context — Cascade understands who wrote what and when |
| **Ruff** | Shows lint errors Cascade can auto-fix (free, no credits) |
| **YAML** | Better parsing of compose.yaml, specs/*.yaml — fewer config errors |
| **Prettier** | Clean formatting = better context comprehension |
| **GitHub PRs** | Cascade can review PRs with full diff context |
| **Pyright** | Type errors visible to Cascade before you ask |

---

## Settings

```json
{
  "editor.formatOnSave": true,
  "[python]": {
    "editor.defaultFormatter": "charliermarsh.ruff"
  },
  "[typescript][typescriptreact]": {
    "editor.defaultFormatter": "esbenp.prettier-vscode"
  },
  "gitlens.codeLens.enabled": true,
  "gitlens.currentLine.enabled": true,
  "tailwindCSS.includeLanguages": {
    "typescript": "javascript",
    "typescriptreact": "javascript"
  }
}
```

---

## See Also

- [actively-used-windsurf-extensions.md](actively-used-windsurf-extensions.md) — auto-generated current list
- [windsurf_features.md](windsurf_features.md) — IDE feature guide
- [cascade-guide.md](cascade-guide.md) — Cascade configuration
