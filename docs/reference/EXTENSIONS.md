# Windsurf Extensions

**Last Updated:** 2026-01-14 09:59
**Total:** 21 extensions

## Quick Install (All Extensions)

```bash
windsurf --install-extension anthropic.claude-code
windsurf --install-extension bierner.markdown-mermaid
windsurf --install-extension bpruitt-goddard.mermaid-markdown-syntax-highlighting
windsurf --install-extension bradlc.vscode-tailwindcss
windsurf --install-extension charliermarsh.ruff
windsurf --install-extension codeium.windsurfpyright
windsurf --install-extension davidanson.vscode-markdownlint
windsurf --install-extension eamodio.gitlens
windsurf --install-extension factory.factory-vscode-extension
windsurf --install-extension github.vscode-github-actions
windsurf --install-extension github.vscode-pull-request-github
windsurf --install-extension ms-azuretools.vscode-containers
windsurf --install-extension ms-azuretools.vscode-docker
windsurf --install-extension ms-python.debugpy
windsurf --install-extension ms-python.python
windsurf --install-extension ms-python.vscode-python-envs
windsurf --install-extension ms-vscode.makefile-tools
windsurf --install-extension prettier.prettier-vscode
windsurf --install-extension redhat.vscode-yaml
windsurf --install-extension traycer.traycer-vscode
windsurf --install-extension vstirbu.vscode-mermaid-preview
```

## Extensions by Category

### AI & Copilot
- `anthropic.claude-code`
- `codeium.windsurfpyright`
- `factory.factory-vscode-extension`
- `traycer.traycer-vscode`

### Python Development
- `charliermarsh.ruff`
- `ms-python.debugpy`
- `ms-python.python`
- `ms-python.vscode-python-envs`

### Docker & Containers
- `ms-azuretools.vscode-containers`
- `ms-azuretools.vscode-docker`

### Git & GitHub
- `eamodio.gitlens`
- `github.vscode-github-actions`
- `github.vscode-pull-request-github`

### Markdown & Documentation
- `bierner.markdown-mermaid`
- `bpruitt-goddard.mermaid-markdown-syntax-highlighting`
- `davidanson.vscode-markdownlint`
- `vstirbu.vscode-mermaid-preview`

### Web Development
- `bradlc.vscode-tailwindcss`
- `prettier.prettier-vscode`

### Other
- `ms-vscode.makefile-tools`
- `redhat.vscode-yaml`

---

## How This File Is Updated

This file is automatically updated by the `sync-extensions` pre-commit hook.

To manually update:
```bash
./scripts/sync_extensions.sh
```

To install all extensions on a new machine:
```bash
# Copy the install commands above, or run:
cat docs/reference/EXTENSIONS.md | grep "windsurf --install-extension" | bash
```
