# Claude Code GUI across the Windows→WSL2 boundary — Gemini Deep Research (2026-07-22, round 2)

**Source:** Gemini Deep Research · **Date:** 2026-07-22 · **Status:** external research; claims verified
selectively (see § Hub verification at the end). Supersedes the WSL-related claims in
`2026-07-22-claude-code-gui-lightweight-editor-research.md`, which contained a **fabricated** "claude.bat
WSL bridge" for opcode.

**Question:** Which standalone Claude Code GUI apps actually work when the GUI runs on Windows 11 but the
`claude` binary, the ~44 repos under `/opt`, and all session history live **inside WSL2 Ubuntu**?

---

## Why the boundary is the whole problem

WSL2 is a Hyper-V utility VM with a real Linux kernel, not a translation layer. A Windows-native app
reaching into WSL files goes over the **9P protocol**, which is high-latency and breaks `inotify`
file-watching. So the agent **must** execute Linux-native inside WSL; `/opt` must be touched by a Linux
`claude` process.

Session state lives at `~/.claude/projects/<hash>/<uuid>.jsonl` on the Linux ext4 filesystem. Any GUI must
read/write that same path in the same OS namespace, or resume-by-ID breaks.

**Only two architectures survive this:**
1. **Remote Execution** — GUI on Windows spawns the Linux `claude` via a bridge, captures stdio through PTY
   emulation; the Linux binary owns the JSONL.
2. **Client-Server Inversion** — the GUI *backend* runs inside WSL next to the CLI and serves its UI over
   localhost to a browser/thin client on Windows.

Naive Windows wrappers fail because they assume shared env vars, PATH, and filesystem namespace — they hunt
for a Windows `claude.exe`, read state from the Windows user profile, and pass Windows paths to the agent.

---

## Verdicts

### Claudeck — **COMPLETE SUCCESS** (Client-Server Inversion)
- No Windows install. Run `npx claudeck` **inside WSL**; it starts a local web server + WebSocket host
  (default **port 9009**).
- Open `localhost` in any Windows browser and **install it as a PWA** → chromeless taskbar app that looks
  native but executes entirely in Linux.
- Boundary friction eliminated: native `/opt` paths, native ext4 file watching, no 9P.
- **State parity is exact** — reads/writes `~/.claude/projects/` via normal Linux I/O, so terminal↔GUI
  resume-by-ID works both directions.
- Features: real-time WebSocket streaming, fork a conversation mid-stream (branching timelines), parallel
  background sessions that keep running with the window closed, knowledge extraction + cost analytics in a
  local SQLite DB.

### Anthropic Claude Code Desktop — **PARTIAL SUCCESS**
- Ships real Windows installers (x64 + ARM64). Electron.
- Has an **Environment picker** at session start: local / cloud / SSH / **WSL distro** — enumerates installed
  distros, and the folder picker then browses the Linux namespace directly (`/opt/<repo>`), bypassing 9P.
- State parity is correct — the CLI runs inside WSL, so JSONL lands in the Linux `~/.claude/projects`.
- Enterprise policy inheritance from the Windows host into WSL processes is deliberate → the bridge is
  engineered, not accidental.
- ⚠️ **But WSL mode disables**: the integrated terminal pane, the visual file-browser pane, `@`-file
  mentions in the composer, and external connectors/plugins. The "rich" parts are stripped exactly where you
  need them.

### opcode (+ forks) — **ABSOLUTE FAILURE**
- Official releases: macOS + Linux only. Windows = build from source (Rust + Bun + MSVC).
- Codebase expects a **Windows-native** `claude`; path resolution fails for a WSL-isolated binary.
- Issue tracker shows login loops, auth failures, "cannot locate the CLI" for Windows/WSL users.
- The "WSL support" exists only as community hacks (Gist v4.2, `QudraLabs/Claude-Code-Windows`): patch the
  Rust backend to bypass version detection, hand-write a `claude.bat` containing `wsl.exe claude %*`, then
  recompile. That wrapper strips ANSI codes, breaks interactive PTY prompts, and freezes on confirmation
  menus.
- **State fractures** — the Tauri UI still reads/writes Windows-side state, so GUI sessions can't read
  terminal-created JSONL. Resumability destroyed.

### Codeman — works, but terminal-flavored
Web server inside WSL spawning Claude in **tmux** PTYs, rendered in-browser via SSE + a terminal emulator.
Survives window close; strong at rate-limit handling, multi-agent orchestration, cron scheduling. Feels like
a multi-pane terminal, not a chat-first GUI.

### VS Code + Remote-WSL — the pragmatic fallback
Succeeds because it is the *most sophisticated* Client-Server Inversion: the Windows app becomes a thin
client and installs a headless **VS Code Server inside WSL**; workspace extensions (including the Claude
extension) run in the **Linux** Node runtime. Hence flawless paths, correct POSIX state I/O, no 9P for
AST/diff work. Cost: the Electron + extension-host + server memory overhead.

---

## Requirements matrix

| Criterion | Claude Code Desktop | opcode (+forks) | Claudeck | VS Code + Remote-WSL |
|---|---|---|---|---|
| Windows installer | ✅ x64/ARM64 | ❌ build from source | n/a (PWA) | ✅ |
| Invokes WSL-side `claude` | ✅ env picker | ❌ | ✅ runs in WSL | ✅ server in WSL |
| Reads WSL JSONL / resume-by-ID | ✅ | ❌ fractured | ✅ exact parity | ✅ |
| Actively maintained 2026 | ✅ | ⚠️ core yes, WSL abandoned to forks | ✅ | ✅ |
| Verdict | **PARTIAL** (features disabled) | **FAIL** | **SUCCESS** | **SUCCESS (heavy)** |

---

## Recommendations (as given)

1. **Disqualify opcode** for this topology — unsupported source patching, broken PTY, fractured state.
2. **Lightest viable: Claudeck** — `npx claudeck` in WSL + install the PWA on Windows.
3. **Official compromise: Claude Code Desktop** — safest supported binary, but no integrated terminal /
   file browser / `@`-mentions in WSL mode.
4. **Pragmatic fallback: keep VS Code + Remote-WSL** if you want uncompromising feature density; the
   architecture is objectively correct, the weight is the price.

---

## Hub verification (not from the research)

- ✅ **opcode's failure independently confirmed here** before this report: releases carry only Linux/macOS
  assets (v0.2.0, 2025-08-31), the README never mentions WSL, repo last pushed 2025-10-16. The earlier
  report's "claude.bat bridge" was not in the project.
- ⚠️ **Claudeck's specifics were NOT verified** (port 9009, PWA install, SQLite analytics, conversation
  forking). Given round 1 fabricated an opcode feature, confirm the package exists and is maintained before
  relying on it.
- ⚠️ **Claude Code Desktop's WSL environment picker and its disabled-feature list were NOT verified.**
- Locally measured on this machine: VS Code 1.9 GB (Chromium artifacts present), Zed 390 MB (none),
  Windsurf 958 MB.
- The source report ended with an unrelated boilerplate medical disclaimer — a generation artifact, ignored.
