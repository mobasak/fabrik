# VS Code Configuration — Workstation Reference

**Date:** 2026-08-03
**Status:** ✅ CURRENT
**Affects:** Local Windows host + WSL Remote (`Ubuntu-24.04`). NOT the VPS fleet.
**Settings file:** `C:\Users\user\AppData\Roaming\Code\User\settings.json` (user scope — applies to all windows, incl. WSL Remote). Every edit is backed up first to `~/backups/vscode-settings.json.backup.*`.

The operating premise for every choice below: **the operator does not hand-write code — AI agents do.**
VS Code's job here is: terminal host for AI sessions, file/diff/image viewing, git auditing of agent
commits, and hosting the AI extensions. Anything that exists to help a *human typist* is dead weight.

---

## 1. Extensions — 14 kept, 6 removed

**Kept (by role):**

| Role | Extensions | Why |
|---|---|---|
| AI agents | `anthropic.claude-code` · `vishalguptax.claude-manager` | Claude Code is the coder; claude-manager wraps session/account management |
| Retired stack, still installed | `traycer.traycer-vscode` · `kilocode.kilo-code` | Kilo CLI and Windsurf/Cascade were retired 2026-07-19 (LLM access = Claude Max OAuth + OpenRouter). The extensions and their `settings.json` keys are still on disk — prune candidates, not active surfaces |
| Agent auditing | `eamodio.gitlens` | Inline blame + Commit Graph = "which agent changed this line and why" (reads the `Agent-Role`/`Agent-Context` commit trailers) |
| CI visibility | `github.vscode-github-actions` | CI genuinely runs on GitHub; failures surface here |
| Viewing | `cweijan.vscode-office` · `vscode-infra.image-viewer` · `vstirbu.vscode-mermaid-preview` | xlsx/docx, generated images (image pipelines), mermaid in 11+ fabrik docs |
| Diagnostics the AI can see | `ms-python.python` · `ms-python.vscode-pylance` · `ms-python.vscode-python-envs` · `charliermarsh.ruff` · `redhat.vscode-yaml` | In-editor errors on open files; env/interpreter management; `specs/*.yaml` validation |

**Removed (all were manual-typing aids or dead weight):**

| Extension | Why removed |
|---|---|
| `codeium.codeium` | Type-as-you-go AI autocomplete from the retired Windsurf stack; competed with Claude Code |
| `esbenp.prettier-vscode` | Format-on-save for human typing; AI formats its output, the gate enforces style |
| `davidanson.vscode-markdownlint` | Lint-while-writing; docs are AI-written and gate-checked |
| `bradlc.vscode-tailwindcss` | Class autocomplete — only helps a human typing classes |
| `ms-python.debugpy` | Interactive breakpoint debugging; AI debugs via tests/logs in the terminal |
| `github.vscode-pull-request-github` | Operator does not review PRs in-editor (direct-to-master flow; AI uses `gh` CLI) |

**Open decision:** Pylance costs a few hundred MB per workspace even scoped down (was 1.35 GB across
two windows before scoping). Since quality is enforced by `final_gate.py` (ruff+mypy) in the terminal,
removing Pylance entirely (`"python.languageServer": "None"`) recovers ~1 GB at the cost of red
underlines in Python files opened for reading. Currently KEPT, scoped down (see §3).

---

## 2. AI surface

```jsonc
"chat.disableAIFeatures": true
```

Disables VS Code's built-in Copilot/AI chat surface. Claude Code is the AI surface on this machine;
the built-in one is redundant UI + background service.

---

## 3. Performance settings — and the measurements behind them

Baseline measured 2026-07-26, **before** these settings: `vscode-server` on WSL = **7.9 GB RSS across
32 processes**, dominated by a **3.0 GB** extension-host/watcher node (plus an 846 MB second window),
**1.35 GB** of Pylance (two workspaces), ~1.2 GB Claude Code sessions (live agents — untouchable),
~0.8 GB Kilo serve (kept by choice).

```jsonc
// PERF: don't watch/search generated trees (was: no excludes -> 3GB watcher bloat)
"files.watcherExclude": {
    "**/.git/objects/**": true,
    "**/.git/subtree-cache/**": true,
    "**/node_modules/**": true,
    "**/.venv/**": true,
    "**/venv/**": true,
    "**/__pycache__/**": true,
    "**/.mypy_cache/**": true,
    "**/.ruff_cache/**": true,
    "**/.pytest_cache/**": true,
    "**/logs/**": true,
    "**/output/**": true,
    "**/dist/**": true,
    "**/build/**": true
},
"search.exclude": {
    "**/node_modules/**": true,
    "**/.venv/**": true,
    "**/venv/**": true,
    "**/__pycache__/**": true,
    "**/.mypy_cache/**": true,
    "**/.ruff_cache/**": true,
    "**/dist/**": true,
    "**/build/**": true
},

// PERF: no background type downloads; no update polling; no telemetry
"typescript.disableAutomaticTypeAcquisition": true,
"extensions.autoCheckUpdates": false,
"update.mode": "manual",
"telemetry.telemetryLevel": "off",

// PERF: Pylance scoped — diagnostics for open files only, no workspace indexing
"python.analysis.diagnosticMode": "openFilesOnly",
"python.analysis.indexing": false,
"python.analysis.exclude": ["**/.venv/**", "**/node_modules/**", "**/__pycache__/**"]
```

**Why each:**

- **`files.watcherExclude` — the load-bearing one.** There were *no* excludes, so the file watcher
  inotify-watched every `.venv`, `node_modules`, `__pycache__`, log and output tree across the
  workspaces — the classic cause of a multi-GB watcher/extension-host process, plus constant CPU
  wakeups every time an agent or the pipeline writes a file. Effect appears after a window reload
  (a ballooned process never deflates in place).
- **`search.exclude`** — same trees out of Ctrl+Shift+F and background indexing.
- **Pylance scoping** — diagnostics only for files actually open; no whole-workspace indexing of
  multi-thousand-file repos whose correctness is already gate-enforced.
- **Type acquisition / update polling / telemetry** — background network + CPU with zero value on
  an AI-driven workstation (updates are applied deliberately, not polled).

---

## 4. Pre-existing settings kept (context, not changed by this pass)

Terminal-first workflow settings that predate this configuration and remain correct: terminals in
editor area, 20 000-line scrollback, copy-on-select, bracketed paste for Zellij, Alt passthrough to
the shell (`sendKeybindingsToShell` + menu-bar mnemonics off), minimap off, non-ASCII highlight off
(Turkish text), `claudeCode.preferredLocation: "panel"`, workspace-trust relaxations, Traycer/Kilo
extension settings, and `remote.SSH` config for the VPS.

---

## 5. Operational notes

- **After any settings change: reload the window** (`Ctrl+Shift+P` → Reload Window). Watcher/host
  memory only shrinks on restart.
- Removed-extension leftovers are purged from `~/.vscode-server/extensions/` (288 MB reclaimed);
  VS Code server logs >1 day and the VSIX cache are pruned weekly by `cache-prune.sh`
  (see [cleanup-automation.md](cleanup-automation.md)).
- The WSL-side server (`~/.vscode-server`) is the live Remote-WSL backend — never delete it wholesale;
  its caches are handled by the weekly cleaner.
