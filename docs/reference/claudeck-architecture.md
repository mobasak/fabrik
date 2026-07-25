# Claudeck architecture — how the Windows GUI drives Claude Code inside WSL

**Last Updated:** 2026-07-23 · verified live on this machine (WSL2 Ubuntu 24.04, Claudeck v1.4.x,
claude CLI v2.1.217). Companion research: `research/2026-07-22-claude-code-wsl-gui-boundary-research.md`.

## The one-line model

Claudeck does not "connect to" WSL — **it lives entirely inside WSL**. The only thing crossing the
Windows→Linux boundary is the browser viewing a webpage (Client-Server Inversion, the same architecture
as VS Code Remote-WSL).

```
┌─ Windows 11 ────────────────┐   ┌─ WSL2 Ubuntu ────────────────────────────┐
│                             │   │                                          │
│  Browser tab                │   │  node claudeck (npx cache)               │
│  http://localhost:9009  ────┼───┼──▶ listening on *:9009                   │
│                             │   │        │ SDK query() call (in-process)   │
│  (HTTP + WebSocket only —   │   │        ▼                                 │
│   no files, no processes)   │   │  claude — Linux ELF, ~/.local/bin/claude │
│                             │   │        │ native ext4 I/O                 │
└─────────────────────────────┘   │        ▼                                 │
                                  │  /opt/<44 repos>                         │
                                  │  ~/.claude/projects/<id>/<uuid>.jsonl    │
                                  └──────────────────────────────────────────┘
```

## The three load-bearing facts

1. **The server is a Linux process.** `npx -y claudeck@latest` runs a Node server from the npx cache
   (`~/.npm/_npx/*/node_modules/claudeck` — plain unminified JS, ~2.4 MB). It binds port **9009**.
2. **It drives the same Linux `claude` binary as the terminal and the VS Code extension**
   (`~/.local/bin/claude`). No spawn of a CLI subprocess with `--model` flags — it imports
   `@anthropic-ai/claude-code` and calls `query()` in-process (`server/agent-loop.js`). Auth is the
   existing subscription OAuth in `~/.claude`; nothing re-authenticates.
3. **All file I/O is native ext4.** Repos under `/opt`, transcripts under
   `~/.claude/projects/<encoded-path>/<uuid>.jsonl` — same paths, same OS namespace as every other
   Claude session, so terminal↔GUI resume-by-ID works. The slow Windows↔WSL 9P file protocol is never
   touched.

## The single boundary crossing

The Windows browser hits `localhost:9009`; WSL2's built-in **localhost forwarding** relays it into the
Linux VM transparently. Only HTTP requests + one WebSocket stream cross — JSON messages and rendered
chat, never file contents or process control. Closing the tab does NOT stop agents: the work lives in
the WSL server process; the tab is a viewport. ("Install as PWA" in Chrome just pins a chromeless
window — nothing is installed on Windows.)

## Where its state lives

| Path | What |
|---|---|
| `~/.claudeck/config/prompts.json` | The `/` menu. Read per-request (no restart needed). Seeded 2026-07-22 with the operator's 16 commands + 30 skills (titles = `/name`, prompt = the literal slash command — Claudeck inserts it; the real CLI parses/executes it). Backup: `prompts.json.bak`. |
| `~/.claudeck/config/agents.json` | Its 4 built-in agents (bug-hunter, review-pr, test-writer, refactor) — **goal prompt + maxTurns/timeout only, no model pin**. |
| `~/.claudeck/config/workflows.json` | DAG workflows (agent steps with dependencies, deterministic order). |
| `~/.claudeck/data.db` | SQLite: its own session mappings, cost analytics. It does NOT import pre-existing `~/.claude/projects` transcripts — only sessions it created. |
| `~/claudeck.log` | Server stdout/stderr. |

## Model resolution (the trap)

`server/agent-loop.js` → `if (model) opts.model = resolveModel(model)`; unknown names pass through
verbatim (`MODEL_MAP[name] || name`).

- **Picker untouched** → `opts.model` never set → falls through `settingSources:["user","project","local"]`
  to `~/.claude/settings.json` → the operator's default (**Fable 5**). This is the right choice.
- **Picker's hardcoded shortnames are STALE**: `opus`→`claude-opus-4-6`, `sonnet`→`claude-sonnet-4-6`
  (both superseded); only `haiku` is current. Picking "opus" is a silent downgrade.
- **Fix in place (historical):** a hub patcher script briefly added a "Fable 5" entry to the menu of
  the live npx cache; the script was removed 2026-07-26 — if the entry vanishes after a claudeck update, leave the picker untouched (the unset default resolves to the operator's settings.json model).

## Operations

```bash
# start (WSL)                          # health
printf '\n\n\n\n\n' | npx -y claudeck@latest > ~/claudeck.log 2>&1 &
curl -s localhost:9009/api/prompts | python3 -c 'import json,sys;print(len(json.load(sys.stdin)))'

# register a project                   # restart = kill the node process, re-run start
curl -s -X POST localhost:9009/api/projects -H 'content-type: application/json' \
  -d '{"path":"/opt/<name>","name":"<name>"}'
```

- 44 `/opt` repos registered via `/api/projects` (2026-07-22).
- Footprint ≈ 190 MB RSS (two node processes) + 932 MB npx cache.
- After a config/server change, **hard-refresh the browser tab** (`Ctrl+Shift+R`) — the frontend caches
  the prompt list at page load.

## Known limits (verified)

- `/api/sessions` lists only Claudeck-created sessions — 26 pre-existing project transcript dirs are
  invisible to its UI (no import/scan endpoint). Resume of an old terminal session must start from the CLI.
- `/` autocomplete lists `prompts.json` only — it has no knowledge of `~/.claude/commands|skills`
  (hence the seeding above). Typing a real slash command still executes even if unlisted.
- `/api/mcp/servers` is Claudeck's own (empty) registry; the 13+ MCP servers in `~/.claude.json` are
  inherited by the spawned SDK session itself, not mirrored in that endpoint.

## Why the alternatives lost (short form — full analysis in the research doc)

- **opcode**: Windows-native wrapper reaching *into* WSL — path mismatch, broken PTY, fractured
  session state. Architecture cannot work across this boundary.
- **Claude Code Desktop (WSL mode)**: correct bridge, but strips the terminal pane, file browser and
  `@`-mentions in WSL mode.
- **VS Code Remote-WSL**: the same inversion done heavier (~1.9 GB Electron + server) — the fallback
  when full IDE density is wanted.
