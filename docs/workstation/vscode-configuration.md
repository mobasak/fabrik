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

### code-server — the same excludes, plus the agent trees (hub default since 2026-10-27)

The operator's coordinator windows run in **code-server** (VS Code in the browser, inside WSL), whose
user settings are a separate file: `~/.local/share/code-server/User/settings.json`. Its file watcher
draws on the **per-user inotify watch budget** (`/proc/sys/fs/inotify/max_user_watches`, 524,288 on
this box), which every other watcher of this user shares, the systemd user manager's path units
included. On 2026-10-27 code-server's three watcher processes held 523,576 of the 524,288 watches,
because it watched every file under `/opt`, the ~90 builder worktrees under `.claude/worktrees/`
among them. `fabrik-rotate.path` failed at 11:12 with `Failed to enter waiting state: No space left
on device` (result `resources`), and no builder could be rotated until it was restarted (W-09957e81).
With the list below and a window reload, the watches fell to 290,735, and to ~14,600 once the
windows were reopened.

The hub default for code-server, kept in that file:

```jsonc
"files.watcherExclude": {
    "**/.claude/worktrees/**": true,
    "**/node_modules/**": true,
    "**/.tmp/**": true,
    "**/.venv/**": true,
    "**/.git/objects/**": true
}
```

`.claude/worktrees` and `.tmp` are the two the VS Code list above lacks; they are the agent trees and
run scratch, which change constantly and are never edited by hand in the editor. A ballooned watcher
never shrinks in place: reload the window after an edit. The 5-minute rotation tick watches the
budget (`scripts/sysadmin/box_budget_check.py`, AMBER at 85%: one mail to the coordinator per
episode, or when a canary watch is refused) and restarts a failed `fabrik-rotate.path`, logging to
`~/.claude/state/box-budget.log`; `python3 scripts/sysadmin/box_budget_check.py --report` prints the
readings and the top holders on demand. This list is documented, not enforced: the alert is the guard.

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
- **The remote extension host's heap cannot be raised from `~/.vscode-server/server-env-setup`** — measured
  2026-10-15 for W-99a835ca (D-896); a `NODE_OPTIONS=--max-old-space-size=8192` block there was added,
  reviewed and removed the same day.
  - Why: the VS Code server deletes `NODE_OPTIONS` from every process it forks —
    `function pv(r){r&&(delete r.DEBUG,delete r.NODE_OPTIONS,…)}` in `~/.vscode-server/bin/<commit>/out/server-main.js`,
    applied to the extension host's environment right after "Starting extension host process..." and to the
    ptyHost, fileWatcher and agent-host forks — and gives the extension host the server's own `execArgv` (empty:
    `bin/code-server` starts node with no flags) plus `--dns-result-order=ipv4first`.
    A probe forking the same way read 8,384 MiB in the parent and 4,288 MiB (node's default here)
    in the child. The extension host keeps that default whatever that file says.
  - What it costs: every Claude tab of one window shares that ONE host, and the extension parses a restored
    tab's transcript whole when its compact boundaries carry a preserved segment; the host died with
    "JavaScript heap out of memory" at 4,088.5 MiB on 2026-10-15 11:13 (`remoteagent.log`).
  - What works: keep large transcripts out of VS Code — the hub agents run as plain `claude` CLIs in the tmux
    session `hub` (D-884) — and restore at most one large-transcript tab per window, since each window is its
    own host. Sending the upstream report of the loader bug is the operator gate W-49a8280d.

<!-- BEGIN related-scripts: generated by scripts/render_doc_script_links.py — do not hand-edit -->
## Related scripts

Scripts that declare this document in their `# AFTER-EDIT:` header — editing one of them
means updating this page in the same change. This list is generated from those headers
(`python3 scripts/render_doc_script_links.py`); add the doc to a script's header, not here.

- `scripts/sysadmin/box_budget_check.py`
<!-- END related-scripts -->
