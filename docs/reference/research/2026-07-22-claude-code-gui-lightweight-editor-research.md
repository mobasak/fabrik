# Claude Code GUI + Lightweight Editor — Gemini Deep Research (2026-07-22)

**Source:** Gemini Deep Research · **Date:** 2026-07-22 · **Status:** external research, claims NOT independently verified by the hub (see § Verification caveats at the end).

**Question researched:** Is there an editor that is BOTH lightweight AND hosts a rich GUI chat wrapper for
Claude Code, given the operator does not hand-write code (AI agents author; operator reviews/operates),
works on Windows 11 + WSL2 Ubuntu with ~44 repos under `/opt`, and requires session history to stay
addressable by ID in `~/.claude/projects/<path>/<uuid>.jsonl`.

---

## Headline answer

**The Electron/webview constraint is CONFIRMED for 2026.** Truly lightweight editors (Zed, Lapce, Helix)
ship no browser engine, so they structurally cannot host the official Claude Code extension (an HTML/React
webview). Zed's extension API is WASM/WIT-based and restricted to safe native components; its "Custom
Preview API" is read-only and explicitly forbids arbitrary webviews or external JavaScript.

**The resolution is a DECOUPLED STACK:** a headless native editor for review + a standalone desktop GUI for
Claude Code orchestration. This satisfies both requirements simultaneously.

---

## Recommended architecture — the Decoupled Stack

1. **Zed** as the code-review surface. Launch via `zed <path>` from inside the WSL2 terminal so it traverses
   the Ubuntu filesystem natively (no proprietary remote daemon, unlike VS Code).
2. **Opcode** on the Windows 11 host as the Claude Code orchestration GUI. Open-source (MIT), built on
   **Tauri 2 + Rust** — uses the OS-native webview (WebView2 on Windows) rather than bundling Chromium.

### Why Opcode specifically
- Auto-detects `~/.claude` and parses existing sessions; reads/writes the standard `.jsonl` format, so
  external analytics (`ccusage`, `getburnd`) keep working.
- Custom agents with distinct system prompts; usage/token/cost analytics; local MCP server management.
- Visual timeline with session versioning — checkpoint and branch new sessions from a point in history.
- **WSL bridge:** a `claude.bat` bridge translates Windows UI calls into WSL2, spawning the real Claude Code
  subprocess inside Ubuntu with correct Linux paths; stdout/stderr are wrapped in JSON and streamed over
  WebSockets to the Windows frontend. This preserves native Linux FS performance for `/opt` and keeps the
  `.jsonl` audit trail intact.

### Standalone GUI alternatives considered
- **Claude Code Desktop (Anthropic, official):** live file-structure sidebar, split-pane execution view,
  Plan Mode sidebar, first-class MCP GUI. Closed-source; heavier; weaker parallel multi-agent execution.
- **Nimbalyst:** up to 6 parallel agent sessions, Kanban orchestration, iOS remote monitoring, native git
  worktree isolation per session. More a project-management suite than a CLI wrapper.
- **Claudeck:** browser-based via `npx claudeck`, fully local. Lacks native OS window management (poor for
  dual-monitor operator layouts).

---

## Zed ACP vs the VS Code extension

**Parity achieved:**
- **Diffs** — agent file modifications arrive as `DiffUpdate`; Zed renders them in its native inline diff
  viewer (stacked or split).
- **Permissions** — `session/request_permission` surfaces as a native GPUI modal with
  Always Allow / Allow Once / Reject.
- **MCP** — first-class; local tool sets/DB connections/API access are forwarded during the handshake.

**Critical failures (why ACP is NOT trustworthy as the primary orchestration layer):**
- **Plan Mode inaccessible** — the ACP adapter does not reliably expose the CLI's `--plan` flag, and does
  not expose context-window utilization metrics.
- **State-synchronization crisis on `.jsonl`** — Zed spawns `claude-code-acp`, which spawns the real CLI.
  If that subprocess dies (rate limit → exit 143/SIGTERM, or a crash), the adapter loses the transport but
  keeps the session ID in memory and the UI keeps accepting prompts. Those prompts are **silently dropped**
  and session data is **never flushed to disk** — zero `.jsonl` files for the orphaned session.
- **Resume-by-ID broken** — resuming by UUID through ACP frequently fails to locate backing data
  ("ProcessTransport is not ready for writing").

→ If a rigorous, universally readable `.jsonl` audit trail is a hard requirement, ACP cannot be the
orchestration layer.

---

## Editor configuration for the review surface (Zed)

- **WSL2:** run `zed <path>` from inside WSL; native filesystem traversal indexes the `/opt` repos without
  network-share latency.
- **Python diagnostics:** `language_servers: ["basedpyright", "ruff"]`.
  - `basedpyright.analysis.diagnosticMode: "workspace"` — evaluate the whole repo for cascading errors from
    the agent's edits, not just the open file.
  - `typeCheckingMode: "standard"` or `"strict"` per repo baseline.
- **Zero-generation constraint:**
  - `autoImportCompletions: false` — stops completion bloat; manual code-action auto-import still available.
  - `"format_on_save": "off"` — prevents ruff from mutating AI-generated files on save, so the agent's diff
    stays exactly as generated until formatting is explicitly invoked.
- **Git review:** native tree-sitter-backed inline blame, multi-repo support, gutter indicators, and
  responsive unified/split diffs — no GitLens/GitKraken weight.

---

## Claimed 2026 benchmarks

| Metric | Zed (Rust/GPUI) | VS Code + Copilot | Cursor | Windsurf |
|---|---|---|---|---|
| Cold start | 0.4 s | 3.0 s | 3.1 s | 3.4 s |
| Idle memory (10 files) | 180 MB | 650 MB | 690 MB | 720 MB |
| Peak memory (AI active) | 340 MB | 980 MB | 1.1 GB | 1.2 GB |
| Typing latency | 2 ms | 12 ms | 12 ms | 14 ms |
| 50k-line file | smooth 60fps+ | stuttering | stuttering | stuttering |

*Attributed to a "DevToolReviews standardized benchmark report, May 2026."*

**Aggregate:** Zed (~180 MB) + Opcode (<100 MB, native webview) ≈ **280–300 MB combined** — roughly 800 MB
less than Cursor or Windsurf alone.

---

## Requirements matrix

| Requirement | VS Code / Cursor / Windsurf | Zed via ACP | Decoupled (Zed + Opcode) |
|---|---|---|---|
| Lightweight (<400 MB) | ❌ ~1 GB peak | ✅ ~180 MB | ✅ ~280 MB |
| Rich Claude GUI | ✅ Chromium webview | ❌ native dialogs only | ✅ Tauri desktop app |
| WSL2 access to `/opt` | ✅ remote daemon | ✅ native traversal | ✅ `claude.bat` bridge |
| `.jsonl` session history | ✅ native CLI | ❌ **transport death orphans files** | ✅ native CLI via bridge |
| Resume-by-ID | ✅ | ❌ **fails to locate data** | ✅ |
| Plan Mode | ✅ | ❌ **flag inaccessible** | ✅ |
| ruff + basedpyright | ✅ via extensions | ✅ native LSP | ✅ native LSP |
| Zero-generation | ⚠️ manual config | ✅ settings.json | ✅ isolated from GUI |

---

## What would change the recommendation

If Anthropic + Zed refactor `@agentclientprotocol/claude-agent-acp` to guarantee 1:1 state sync with the
CLI — robust handling of subprocess transport death, guaranteed `.jsonl` persistence regardless of rate
limits/crashes, and native Plan Mode exposure — the standalone GUI becomes unnecessary and Zed alone
suffices.

---

## Verification caveats (hub note, not from the research)

Claims below are relayed from the Gemini report and have **not** been independently verified here. Verify
before acting on them:
1. **Opcode's maturity, licence, and `claude.bat` WSL bridge** — confirm the repo is active and the bridge
   works against WSL2 Ubuntu 24.04.
2. **The benchmark table** — the cited "DevToolReviews May 2026" source was not checked; treat the exact
   numbers as indicative, not measured. (Locally verified on this machine: VS Code install 1.9 GB with
   Chromium artifacts present; Zed 390 MB with none; Windsurf 958 MB.)
3. **The ACP `.jsonl` orphaning + resume-by-ID failures** — plausible and matches known Zed issues
   (conversation loss after `/clear` on restart; sessions wedging after usage limits), but the specific
   failure mechanism described was not reproduced here.
