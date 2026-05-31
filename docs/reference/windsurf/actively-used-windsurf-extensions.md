# Windsurf Extensions

**Last Updated:** 2026-05-31 12:50
**Total:** 11 extensions

## Quick Install (All Extensions)

```bash
windsurf --install-extension bpruitt-goddard.mermaid-markdown-syntax-highlighting
windsurf --install-extension codeium.windsurfpyright
windsurf --install-extension kilocode.kilo-code
windsurf --install-extension ms-python.debugpy
windsurf --install-extension ms-python.python
windsurf --install-extension ms-python.vscode-python-envs
windsurf --install-extension ms-vscode-remote.remote-ssh-edit
windsurf --install-extension ms-vscode.powershell
windsurf --install-extension ms-vscode.remote-explorer
windsurf --install-extension tomoki1207.pdf
windsurf --install-extension traycer.traycer-vscode
```

## Extensions by Category

### AI & Copilot
- `codeium.windsurfpyright`
- `traycer.traycer-vscode`

### Python Development
- `ms-python.debugpy`
- `ms-python.python`
- `ms-python.vscode-python-envs`

### Docker & Containers
- ``

### Git & GitHub
- ``

### Markdown & Documentation
- `bpruitt-goddard.mermaid-markdown-syntax-highlighting`

### Web Development
- ``

### Other
- `kilocode.kilo-code`
- `ms-vscode.powershell`
- `ms-vscode.remote-explorer`
- `ms-vscode-remote.remote-ssh-edit`
- `tomoki1207.pdf`

---

## How This File Is Updated

This file is automatically updated daily by `scripts/sync_extensions.sh` via the WSL startup hook.

To manually update:
```bash
./scripts/sync_extensions.sh
```

To install all extensions on a new machine:
```bash
# Copy the install commands above, or run:
cat docs/reference/EXTENSIONS.md | grep "windsurf --install-extension" | bash
```
